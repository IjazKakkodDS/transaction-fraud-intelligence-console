"""
CSV validation for portfolio risk scan uploads.
"""

import io
from dataclasses import dataclass, field

import pandas as pd

REQUIRED_COLUMNS: set[str] = {
    "transaction_id",
    "amount",
    "timestamp",
    "country",
    "payment_method",
}

MAX_ROWS = 500


def _parse_float(value) -> float | None:
    """Return value as float, or None if missing or unparseable."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


class RiskScanParseError(Exception):
    """Raised when the uploaded file cannot be parsed as CSV."""


class RiskScanValidationError(Exception):
    """Raised when the CSV structure fails validation (missing columns, row limit)."""


@dataclass
class ValidationResult:
    valid_df: pd.DataFrame
    all_rows: list[dict]
    total_rows: int
    valid_rows: int
    invalid_rows: int
    skipped_rows: int


def validate_csv(file_bytes: bytes) -> ValidationResult:
    """
    Parse and validate CSV bytes for a portfolio risk scan upload.

    Returns a ValidationResult containing:
    - valid_df: DataFrame of rows that passed validation, with row_number column added
    - all_rows: metadata list for every row (VALID, INVALID, SKIPPED)
    - row counts by status

    Raises RiskScanParseError if the bytes cannot be parsed as CSV.
    Raises RiskScanValidationError if required columns are missing or row limit exceeded.
    """
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
    if total_rows > MAX_ROWS:
        raise RiskScanValidationError(
            f"CSV exceeds maximum of {MAX_ROWS} data rows. Got {total_rows}."
        )

    all_rows: list[dict] = []
    valid_record_positions: list[int] = []
    seen_transaction_ids: set[str] = set()
    valid_count = invalid_count = skipped_count = 0

    has_merchant_category = "merchant_category" in df.columns
    has_device_id = "device_id" in df.columns

    for pos, (_, row) in enumerate(df.iterrows()):
        row_number = pos + 1  # 1-based, header excluded

        transaction_id = row.get("transaction_id")
        amount_raw = row.get("amount")
        timestamp = row.get("timestamp")
        country = row.get("country")
        payment_method = row.get("payment_method")
        merchant_category = row.get("merchant_category") if has_merchant_category else None
        device_id = row.get("device_id") if has_device_id else None

        errors: list[str] = []

        # transaction_id
        if pd.isna(transaction_id) or str(transaction_id).strip() == "":
            errors.append("Missing required field: transaction_id")

        # amount
        if pd.isna(amount_raw):
            errors.append("Missing required field: amount")
        else:
            try:
                float(amount_raw)
            except (ValueError, TypeError):
                errors.append("Invalid value for field: amount")

        # timestamp
        if pd.isna(timestamp) or str(timestamp).strip() == "":
            errors.append("Missing required field: timestamp")
        else:
            try:
                pd.to_datetime(str(timestamp))
            except Exception:
                errors.append("Invalid value for field: timestamp")

        # country
        if pd.isna(country) or str(country).strip() == "":
            errors.append("Missing required field: country")

        # payment_method
        if pd.isna(payment_method) or str(payment_method).strip() == "":
            errors.append("Missing required field: payment_method")

        if errors:
            validation_status = "INVALID"
            validation_errors: list[str] | None = errors
            invalid_count += 1
        else:
            tid_str = str(transaction_id)
            if tid_str in seen_transaction_ids:
                validation_status = "SKIPPED"
                validation_errors = ["Duplicate transaction_id in uploaded file"]
                skipped_count += 1
            else:
                validation_status = "VALID"
                validation_errors = None
                seen_transaction_ids.add(tid_str)
                valid_count += 1
                valid_record_positions.append(pos)

        all_rows.append({
            "row_number": row_number,
            "transaction_id": None if pd.isna(transaction_id) else transaction_id,
            "amount": _parse_float(amount_raw),
            "timestamp": None if pd.isna(timestamp) else str(timestamp),
            "country": None if pd.isna(country) else str(country),
            "payment_method": None if pd.isna(payment_method) else str(payment_method),
            "merchant_category": (
                None if (merchant_category is None or pd.isna(merchant_category))
                else str(merchant_category)
            ),
            "device_id": (
                None if (device_id is None or pd.isna(device_id))
                else str(device_id)
            ),
            "validation_status": validation_status,
            "validation_errors": validation_errors,
        })

    valid_df = df.iloc[valid_record_positions].copy().reset_index(drop=True)
    valid_df["row_number"] = [all_rows[p]["row_number"] for p in valid_record_positions]

    return ValidationResult(
        valid_df=valid_df,
        all_rows=all_rows,
        total_rows=total_rows,
        valid_rows=valid_count,
        invalid_rows=invalid_count,
        skipped_rows=skipped_count,
    )