"""
Async portfolio scan processor — worker-ready orchestration layer.

Separates scan processing from the API layer so this module can be called
from FastAPI BackgroundTasks today and from a dedicated worker process later
without modification to either the API or the processing logic.

Public surface
--------------
  ASYNC_RISK_SCAN_MAX_ROWS  : int       maximum rows accepted by the async endpoint
  RISK_SCAN_CHUNK_SIZE      : int       rows per processing chunk (env-configurable)
  detect_csv_row_count(file_bytes) -> int
  process_portfolio_scan_job(scan_id, file_bytes, filename, chunk_size) -> None

Invariant
---------
  The scan record for scan_id must already exist in QUEUED state before
  process_portfolio_scan_job() is called.  The function owns the
  PROCESSING -> COMPLETE / FAILED status transition.
"""

import io
import logging
import os
from datetime import datetime, timezone

import pandas as pd

from src.db.postgres_logger import (
    bulk_insert_scan_results,
    update_portfolio_scan_progress,
    update_portfolio_scan_status,
)
from src.risk_scan.scanner import score_dataframe
from src.risk_scan.summarizer import compute_summary
from src.risk_scan.validator import (
    REQUIRED_COLUMNS,
    RiskScanParseError,
    RiskScanValidationError,
    validate_dataframe,
)

logger = logging.getLogger(__name__)

ASYNC_RISK_SCAN_MAX_ROWS: int = 10_000
RISK_SCAN_CHUNK_SIZE: int = max(1, int(os.getenv("RISK_SCAN_CHUNK_SIZE", "500")))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _merge_scored_rows(validation_result, scored_rows: list[dict]) -> list[dict]:
    """Merge scored outputs back into all_rows preserving INVALID/SKIPPED entries."""
    scored_by_row_number = {r["row_number"]: r for r in scored_rows}
    merged: list[dict] = []
    for row in validation_result.all_rows:
        if row["validation_status"] == "VALID":
            scored = scored_by_row_number.get(row["row_number"])
            merged.append(scored if scored is not None else row)
        else:
            merged.append(row)
    return merged


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def detect_csv_row_count(file_bytes: bytes) -> int:
    """
    Best-effort row count for queued scan metadata.

    The background processor is authoritative; this early count is used only
    so clients can show progress immediately after job creation before the
    background task has started.
    """
    try:
        return len(pd.read_csv(io.BytesIO(file_bytes), usecols=[0]))
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def process_portfolio_scan_job(
    scan_id: str,
    file_bytes: bytes,
    filename: str,
    chunk_size: int = RISK_SCAN_CHUNK_SIZE,
) -> None:
    """
    Process an async portfolio scan job end-to-end.

    Reads the uploaded CSV once, then validates, scores, persists, and
    updates progress in chunks so status polling observes durable progress
    after every chunk completes.

    Called from FastAPI BackgroundTasks today; the signature is intentionally
    free of FastAPI types so a dedicated worker can import and call this
    function without modification.

    Parameters
    ----------
    scan_id    : UUID string identifying the scan record in QUEUED state.
    file_bytes : raw bytes of the uploaded CSV file.
    filename   : original filename, used only for logging.
    chunk_size : rows per processing chunk; defaults to RISK_SCAN_CHUNK_SIZE.
    """
    update_portfolio_scan_status(
        scan_id,
        "PROCESSING",
        started_at=_utc_now_iso(),
        error_message="",
    )

    try:
        # ── Parse and validate structure ──────────────────────────────────────
        try:
            df = pd.read_csv(io.BytesIO(file_bytes))
        except Exception as exc:
            raise RiskScanParseError(f"CSV could not be parsed: {exc}") from exc

        missing_cols = REQUIRED_COLUMNS - set(df.columns)
        if missing_cols:
            raise RiskScanValidationError(
                f"Missing required columns: {', '.join(sorted(missing_cols))}"
            )

        total_rows = len(df)
        if total_rows > ASYNC_RISK_SCAN_MAX_ROWS:
            raise RiskScanValidationError(
                f"CSV exceeds maximum of {ASYNC_RISK_SCAN_MAX_ROWS} data rows. Got {total_rows}."
            )

        # Publish authoritative total_rows now that the file is parsed.
        update_portfolio_scan_progress(scan_id, total_rows=total_rows)

        # ── Chunked validation, scoring, and persistence ───────────────────────
        seen_transaction_ids: set[str] = set()
        all_processed_rows: list[dict] = []

        for start in range(0, total_rows, chunk_size):
            chunk_df = df.iloc[start : start + chunk_size].copy().reset_index(drop=True)
            validation_result = validate_dataframe(
                chunk_df,
                seen_transaction_ids=seen_transaction_ids,
                row_offset=start,
            )
            scored_rows = score_dataframe(validation_result.valid_df)
            merged_rows = _merge_scored_rows(validation_result, scored_rows)

            bulk_insert_scan_results(scan_id, merged_rows)
            all_processed_rows.extend(merged_rows)

            summary = compute_summary(all_processed_rows)
            update_portfolio_scan_progress(
                scan_id,
                processed_rows=summary["total_rows"],
                valid_rows=summary["valid_rows"],
                invalid_rows=summary["invalid_rows"],
                skipped_rows=summary["skipped_rows"],
                low_count=summary["low_count"],
                medium_count=summary["medium_count"],
                high_count=summary["high_count"],
                critical_count=summary["critical_count"],
                p0_count=summary["p0_count"],
                p1_count=summary["p1_count"],
                p2_count=summary["p2_count"],
                p3_count=summary["p3_count"],
                total_amount=summary["total_amount"],
                critical_amount=summary["critical_amount"],
                high_amount=summary["high_amount"],
                risk_summary=summary["risk_summary"],
            )

        # ── Zero-row edge case ────────────────────────────────────────────────
        if total_rows == 0:
            empty = compute_summary([])
            update_portfolio_scan_progress(
                scan_id,
                processed_rows=0,
                valid_rows=0,
                invalid_rows=0,
                skipped_rows=0,
                low_count=0,
                medium_count=0,
                high_count=0,
                critical_count=0,
                p0_count=0,
                p1_count=0,
                p2_count=0,
                p3_count=0,
                total_amount=0,
                critical_amount=0,
                high_amount=0,
                risk_summary=empty["risk_summary"],
            )

        update_portfolio_scan_status(
            scan_id,
            "COMPLETE",
            completed_at=_utc_now_iso(),
            error_message="",
        )
        logger.info(
            "Async risk scan completed | scan_id=%s filename=%s rows=%d",
            scan_id,
            filename,
            total_rows,
        )

    except (RiskScanValidationError, RiskScanParseError) as exc:
        logger.warning(
            "Async risk scan failed validation | scan_id=%s error=%s", scan_id, exc
        )
        update_portfolio_scan_status(
            scan_id,
            "FAILED",
            completed_at=_utc_now_iso(),
            error_message=str(exc)[:500],
        )
    except Exception as exc:
        logger.error(
            "Async risk scan failed | scan_id=%s error=%s", scan_id, exc
        )
        update_portfolio_scan_status(
            scan_id,
            "FAILED",
            completed_at=_utc_now_iso(),
            error_message=str(exc)[:500],
        )
