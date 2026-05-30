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
from collections import Counter
from datetime import datetime, timezone

import pandas as pd

from src.db.postgres_logger import (
    bulk_insert_scan_results,
    update_portfolio_scan_progress,
    update_portfolio_scan_status,
)
from src.risk_scan.scanner import score_dataframe
from src.risk_scan.validator import (
    REQUIRED_COLUMNS,
    RiskScanParseError,
    RiskScanValidationError,
    validate_dataframe,
)

logger = logging.getLogger(__name__)

ASYNC_RISK_SCAN_MAX_ROWS: int = int(os.getenv("RISK_SCAN_MAX_ROWS", "50000"))
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


def _build_risk_summary(
    reasons: Counter,
    countries: Counter,
    payment_methods: Counter,
    merchant_cats: Counter,
) -> dict:
    """
    Build the risk_summary dict from running counters.

    O(k log k) in the number of unique values per counter — effectively
    constant in practice because the counters are bounded by the fixed
    set of reasons/countries/payment-methods/merchant-categories in the data.
    """
    return {
        "top_risk_patterns": [
            {"reason": r, "count": c} for r, c in reasons.most_common(5)
        ],
        "top_countries": [
            {"country": c, "count": n} for c, n in countries.most_common(5)
        ],
        "top_payment_methods": [
            {"payment_method": m, "count": n}
            for m, n in payment_methods.most_common(5)
        ],
        "top_merchant_categories": [
            {"merchant_category": mc, "count": n}
            for mc, n in merchant_cats.most_common(5)
        ],
    }


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

    Progress updates use running aggregate counters maintained per chunk
    rather than re-scanning the full accumulated row list after each chunk.
    This keeps per-chunk overhead O(chunk_size) regardless of total scan size.

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

        # ── Running aggregate state ───────────────────────────────────────────
        # Scalar counts — incremented per row, never re-scanned.
        agg_total = agg_valid = agg_invalid = agg_skipped = 0
        agg_low = agg_medium = agg_high = agg_critical = 0
        agg_p0 = agg_p1 = agg_p2 = agg_p3 = 0
        agg_total_amount = agg_critical_amount = agg_high_amount = 0.0

        # Counters for risk_summary top-N fields — also updated per row.
        agg_reasons: Counter = Counter()
        agg_countries: Counter = Counter()
        agg_payment_methods: Counter = Counter()
        agg_merchant_cats: Counter = Counter()

        seen_transaction_ids: set[str] = set()

        # ── Chunked validation, scoring, and persistence ───────────────────────
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

            # Update running counters from this chunk only — O(chunk_size).
            for row in merged_rows:
                vstatus = row["validation_status"]
                agg_total += 1
                if vstatus == "VALID":
                    agg_valid += 1
                    tier     = row.get("risk_tier") or "Low"
                    priority = row.get("operational_priority") or "P3"

                    if tier == "Critical":
                        agg_critical += 1
                    elif tier == "High":
                        agg_high += 1
                    elif tier == "Medium":
                        agg_medium += 1
                    else:
                        agg_low += 1

                    if priority == "P0":
                        agg_p0 += 1
                    elif priority == "P1":
                        agg_p1 += 1
                    elif priority == "P2":
                        agg_p2 += 1
                    else:
                        agg_p3 += 1

                    amount = row.get("amount")
                    if amount is not None:
                        try:
                            amt = float(amount)
                            agg_total_amount += amt
                            if tier == "Critical":
                                agg_critical_amount += amt
                            elif tier == "High":
                                agg_high_amount += amt
                        except (ValueError, TypeError):
                            pass

                    reasons_str = row.get("reasons") or ""
                    for reason in reasons_str.split("|"):
                        reason = reason.strip()
                        if reason:
                            agg_reasons[reason] += 1

                    country = row.get("country")
                    if country:
                        agg_countries[str(country)] += 1

                    pm = row.get("payment_method")
                    if pm:
                        agg_payment_methods[str(pm)] += 1

                    mc = row.get("merchant_category")
                    if mc and str(mc) not in ("None", ""):
                        agg_merchant_cats[str(mc)] += 1

                elif vstatus == "INVALID":
                    agg_invalid += 1
                else:
                    agg_skipped += 1

            update_portfolio_scan_progress(
                scan_id,
                processed_rows=agg_total,
                valid_rows=agg_valid,
                invalid_rows=agg_invalid,
                skipped_rows=agg_skipped,
                low_count=agg_low,
                medium_count=agg_medium,
                high_count=agg_high,
                critical_count=agg_critical,
                p0_count=agg_p0,
                p1_count=agg_p1,
                p2_count=agg_p2,
                p3_count=agg_p3,
                total_amount=round(agg_total_amount, 4),
                critical_amount=round(agg_critical_amount, 4),
                high_amount=round(agg_high_amount, 4),
                risk_summary=_build_risk_summary(
                    agg_reasons,
                    agg_countries,
                    agg_payment_methods,
                    agg_merchant_cats,
                ),
            )

        # ── Zero-row edge case ────────────────────────────────────────────────
        if total_rows == 0:
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
                risk_summary=_build_risk_summary(
                    Counter(), Counter(), Counter(), Counter()
                ),
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
