"""
CSV export for portfolio risk scan results.
"""

import csv
import io
from collections.abc import Generator, Iterator

EXPORT_FIELDS = [
    "row_number",
    "transaction_id",
    "amount",
    "timestamp",
    "country",
    "payment_method",
    "merchant_category",
    "device_id",
    "rule_flag",
    "model_prediction",
    "risk_score",
    "decision",
    "risk_tier",
    "operational_priority",
    "reasons",
    "validation_status",
    "validation_errors",
    "promoted",
]

EXPORT_BATCH_SIZE = 5_000


def _clean_row(row: dict) -> dict:
    clean: dict = {}
    for field in EXPORT_FIELDS:
        val = row.get(field)
        if val is None:
            clean[field] = ""
        elif isinstance(val, list):
            clean[field] = "|".join(str(v) for v in val)
        else:
            clean[field] = val
    return clean


def results_to_csv(results: list[dict]) -> bytes:
    """
    Serialize a list of scan result dicts to CSV bytes.

    - Writes a header row followed by one row per result in input order.
    - None values become empty strings.
    - List values (e.g. validation_errors) are pipe-joined.
    - Does not write to disk.
    """
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=EXPORT_FIELDS,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for row in results:
        writer.writerow(_clean_row(row))
    return buf.getvalue().encode("utf-8")


def stream_scan_csv(
    fetch_page: "callable[[int, int], list[dict]]",
    batch_size: int = EXPORT_BATCH_SIZE,
) -> Generator[bytes, None, None]:
    """
    Yield CSV bytes incrementally: header first, then rows in batches.

    fetch_page(offset, limit) must return a list of result dicts.
    Stops when a page returns fewer rows than batch_size.
    """
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=EXPORT_FIELDS,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    yield buf.getvalue().encode("utf-8")

    offset = 0
    while True:
        buf.seek(0)
        buf.truncate(0)
        rows = fetch_page(offset, batch_size)
        if not rows:
            break
        for row in rows:
            writer.writerow(_clean_row(row))
        yield buf.getvalue().encode("utf-8")
        if len(rows) < batch_size:
            break
        offset += batch_size