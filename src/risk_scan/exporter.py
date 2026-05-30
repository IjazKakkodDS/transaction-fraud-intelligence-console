"""
CSV export for portfolio risk scan results.
"""

import csv
import io

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
        clean: dict = {}
        for field in EXPORT_FIELDS:
            val = row.get(field)
            if val is None:
                clean[field] = ""
            elif isinstance(val, list):
                clean[field] = "|".join(str(v) for v in val)
            else:
                clean[field] = val
        writer.writerow(clean)

    return buf.getvalue().encode("utf-8")