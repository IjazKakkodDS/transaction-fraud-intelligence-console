"""
Feature engineering for transaction data.
"""

import numbers
import pandas as pd

from src.config.config import (
    HIGH_AMOUNT_THRESHOLD,
    HIGH_RISK_MERCHANT_CATEGORIES,
    HIGH_RISK_PAYMENT_METHODS,
    LOW_RISK_COUNTRIES,
)

# ---------------------------------------------------------------------------
# Scenario-family reason labels (Phase 12F-3)
# Maps scenario_family values from rich CSVs to analyst-facing reason text.
# Absent from legacy CSVs; safe to ignore when scenario_family not present.
# ---------------------------------------------------------------------------
_SCENARIO_REASON_LABELS: dict = {

    "account_takeover":             "Account takeover pattern detected",
    "card_testing":                 "Card testing velocity pattern",
    "high_velocity_spend":          "High-velocity spend pattern",
    "unusual_geography":            "Unusual geographic pattern",
    "new_payee_transfer":           "New payee transfer risk",
    "merchant_risk_spike":          "Merchant risk spike",
    "mule_account_behaviour":       "Mule account behaviour pattern",
    "refund_chargeback_abuse":      "Refund and chargeback abuse pattern",
    "dormant_account_reactivation": "Dormant account reactivation detected",
    "cross_border_high_value":      "Cross-border high-value transaction",
    "device_mismatch":              "Device mismatch detected",
    "suspicious_repeated_attempts": "Suspicious repeated attempts detected",
}

# ---------------------------------------------------------------------------
# Graph indicator thresholds (Phase 15C)
# Provisional values validated in Phase 15B. To be reviewed and calibrated
# during Phase 15D when graph_boost is integrated into the scoring formula.
# These thresholds do not affect risk_score in Phase 15C.
# ---------------------------------------------------------------------------
_GRAPH_SHARED_DEVICE_THRESHOLD: int = 2   # >= N distinct accounts per device
_GRAPH_FAN_IN_THRESHOLD: int        = 3   # > N distinct accounts per counterparty
_GRAPH_FAN_OUT_THRESHOLD: int       = 3   # > N distinct counterparties per account


def _coerce_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _normalize_str(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip()


def _parse_optional_bool(series: pd.Series) -> pd.Series:
    normalized = _normalize_str(series).str.lower()
    truthy = normalized.isin(["true", "1", "yes", "y"])
    falsy = normalized.isin(["false", "0", "no", "n"])
    return pd.Series(pd.NA, index=series.index).where(~truthy, True).where(~falsy, False)


def _safe_float(value) -> float:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, numbers.Number) and not pd.isna(value):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return False


def _as_bool(value) -> bool:
    try:
        return bool(value)
    except Exception:
        return False


def _clean_entity_id(series: pd.Series) -> pd.Series:
    """
    Normalise an entity ID column for graph groupby operations.

    Strips whitespace and converts absent values (NaN, None, empty string,
    "nan", "NaN", "None", "null") to pd.NA so that groupby drops them rather
    than grouping absent IDs together. Rows with absent entity IDs contribute
    0 / False to all graph indicators.
    """
    s = series.fillna("").astype(str).str.strip()
    return s.replace({"": pd.NA, "nan": pd.NA, "NaN": pd.NA, "None": pd.NA, "null": pd.NA})


def extract_graph_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute first-slice graph / mule-network indicators for a transaction batch.

    Indicators are computed across ALL rows in df using entity-level groupby
    aggregations. Each row receives the indicator value for its own entity
    neighborhood within the batch -- e.g. a row's accounts_per_device reflects
    how many distinct accounts share that row's device_id across the full batch.

    Phase 15C: these 9 columns are added to df but do not yet affect risk_score.
    investigator.py does not reference them. Phase 15D will integrate them into
    the graph_boost formula. Thresholds are provisional -- see _GRAPH_* constants.

    All indicators default to 0 / False when required entity fields
    (device_id, account_id, customer_id, merchant_id) are absent or contain
    empty / null values, preserving neutral behavior for legacy 9-field CSVs,
    rich CSVs without entity IDs, and rows with partial entity context.

    Operates in-place on the passed DataFrame and returns it.
    """
    has_device   = "device_id"   in df.columns
    has_account  = "account_id"  in df.columns
    has_customer = "customer_id" in df.columns
    has_merchant = "merchant_id" in df.columns

    # -----------------------------------------------------------------------
    # Device-based indicators
    # -----------------------------------------------------------------------
    if has_device and has_account:
        dev_col  = _clean_entity_id(df["device_id"])
        acct_col = _clean_entity_id(df["account_id"])

        # accounts_per_device -- distinct accounts per device
        tmp = pd.DataFrame({"_dev": dev_col, "_acct": acct_col})
        apd = tmp.groupby("_dev")["_acct"].nunique()
        df["accounts_per_device"] = dev_col.map(apd).fillna(0).astype(int)
        df["shared_device_flag"]  = df["accounts_per_device"] >= _GRAPH_SHARED_DEVICE_THRESHOLD

        if has_customer:
            cust_col = _clean_entity_id(df["customer_id"])
            tmp_c    = pd.DataFrame({"_dev": dev_col, "_cust": cust_col})
            cpd      = tmp_c.groupby("_dev")["_cust"].nunique()
            df["customers_per_device"] = dev_col.map(cpd).fillna(0).astype(int)
            # cross_account_device_reuse -- device shared across DIFFERENT customer entities.
            # Rows where device_id is absent are always False so device absence is never
            # misread as a shared-device signal.
            df["cross_account_device_reuse"] = (
                (df["customers_per_device"] > 1) & dev_col.notna()
            )
        else:
            df["customers_per_device"]       = 0
            df["cross_account_device_reuse"] = False

        df["device_cluster_size"] = (
            df["customers_per_device"].astype(int) + df["accounts_per_device"].astype(int)
        )
    else:
        df["accounts_per_device"]        = 0
        df["shared_device_flag"]         = False
        df["customers_per_device"]       = 0
        df["cross_account_device_reuse"] = False
        df["device_cluster_size"]        = 0

    # -----------------------------------------------------------------------
    # Counterparty fan-in -- accounts per counterparty
    # -----------------------------------------------------------------------
    if has_merchant and has_account:
        merch_col = _clean_entity_id(df["merchant_id"])
        acct_col  = _clean_entity_id(df["account_id"])

        tmp = pd.DataFrame({"_merch": merch_col, "_acct": acct_col})
        apc = tmp.groupby("_merch")["_acct"].nunique()
        df["accounts_per_counterparty"] = merch_col.map(apc).fillna(0).astype(int)
        df["counterparty_fan_in_flag"]  = df["accounts_per_counterparty"] > _GRAPH_FAN_IN_THRESHOLD
    else:
        df["accounts_per_counterparty"] = 0
        df["counterparty_fan_in_flag"]  = False

    # -----------------------------------------------------------------------
    # Account fan-out -- counterparties per account
    # -----------------------------------------------------------------------
    if has_account and has_merchant:
        acct_col  = _clean_entity_id(df["account_id"])
        merch_col = _clean_entity_id(df["merchant_id"])

        tmp = pd.DataFrame({"_acct": acct_col, "_merch": merch_col})
        cpa = tmp.groupby("_acct")["_merch"].nunique()
        df["counterparties_per_account"] = acct_col.map(cpa).fillna(0).astype(int)
        df["counterparty_fan_out_flag"]  = df["counterparties_per_account"] > _GRAPH_FAN_OUT_THRESHOLD
    else:
        df["counterparties_per_account"] = 0
        df["counterparty_fan_out_flag"]  = False

    return df


def extract_behavioural_reason_codes(row: pd.Series) -> list:
    codes = []

    if _safe_float(row.get("amount_deviation_ratio", 0.0)) >= 3.0:
        codes.append("BEHAVIOURAL_AMOUNT_DEVIATION")
    if _safe_float(row.get("velocity_deviation_ratio", 0.0)) >= 3.0:
        codes.append("BEHAVIOURAL_VELOCITY_DEVIATION")
    if _safe_float(row.get("balance_drop_ratio", 0.0)) >= 0.20:
        codes.append("BALANCE_DROP_ANOMALY")

    if _safe_truthy(row.get("new_device_for_customer", 0)):
        codes.append("NEW_DEVICE_FOR_CUSTOMER")
    if _safe_truthy(row.get("new_country_for_customer", 0)):
        codes.append("NEW_COUNTRY_FOR_CUSTOMER")
    if _safe_truthy(row.get("new_counterparty_for_account", 0)):
        codes.append("NEW_COUNTERPARTY_FOR_ACCOUNT")
    if _safe_truthy(row.get("unusual_channel_for_customer", 0)):
        codes.append("UNUSUAL_CHANNEL_FOR_CUSTOMER")
    if _safe_truthy(row.get("unusual_merchant_for_customer", 0)):
        codes.append("BEHAVIOURAL_PROFILE_SHIFT")

    return codes


def extract_graph_reason_codes(row) -> list:
    codes = []
    if _as_bool(row.get("shared_device_flag", False)):
        codes.append("SHARED_DEVICE_CLUSTER")
    if _as_bool(row.get("cross_account_device_reuse", False)):
        codes.append("DEVICE_ACCOUNT_REUSE")
    if _as_bool(row.get("counterparty_fan_in_flag", False)):
        codes.append("MULE_FAN_IN_PATTERN")
    if _as_bool(row.get("counterparty_fan_out_flag", False)):
        codes.append("MULE_FAN_OUT_PATTERN")
    return codes


def generate_reasons(df: pd.DataFrame) -> pd.Series:
    """
    Return a pipe-delimited reasons string for each row in a fully scored DataFrame.

    Expects df to contain the columns produced by generate_basic_features, predict,
    apply_fraud_rules, and triage_decision before this call. Works on both single-row
    and multi-row DataFrames. An empty string is returned for rows with no active
    signals (all conditions false).

    Phase 12F-3: rich signal reason codes are appended when the corresponding
    rich feature columns are present. Legacy rows without rich columns produce
    the same output as before (all rich features default to 0).
    """
    def _row_reasons(row) -> str:
        parts = []

        # --- Legacy reason codes (unchanged) ---
        if row["amount"] > HIGH_AMOUNT_THRESHOLD:
            parts.append("High transaction amount")
        if row["is_night_transaction"] == 1:
            parts.append("Unusual transaction time")
        if row["model_prediction"] == 1:
            parts.append("Model flagged as suspicious")
        if row.get("is_international", 0) == 1 and row.get("is_high_risk_country", 0) == 1:
            parts.append("International transaction from elevated-risk region")
        if row.get("is_high_risk_payment_method", 0) == 1:
            parts.append("High-risk payment method")
        if row.get("is_high_risk_merchant_category", 0) == 1:
            parts.append("High-risk merchant category")
        if row.get("has_device_id", 1) == 0:
            parts.append("No device identifier present")

        # --- Rich signal reason codes (Phase 12F-3) ---
        # These only fire when the corresponding feature column was populated
        # by generate_basic_features() from a rich CSV column. Legacy rows
        # produce 0 for all rich features, so none of these conditions fire.
        if row.get("is_low_trust_device", 0) == 1:
            parts.append("Unrecognised device with low trust score")
        if row.get("is_geo_anomaly", 0) == 1:
            parts.append("Geographic location inconsistent with registered address")
        if row.get("is_high_velocity_1h", 0) == 1:
            parts.append("Transaction velocity exceeds 1-hour baseline")
        if row.get("has_failed_attempts", 0) == 1:
            parts.append("Multiple failed attempts preceding this transaction")
        if row.get("is_high_risk_merchant_score", 0) == 1:
            parts.append("High-risk merchant")
        if row.get("is_new_payee_high_value", 0) == 1:
            parts.append("First-time payment to unknown payee")
        if row.get("has_chargebacks", 0) == 1:
            parts.append("High chargeback history")
        if row.get("is_amount_anomaly", 0) == 1:
            parts.append("Transaction amount significantly above 30-day average")

        # --- Behavioural reason codes (Phase 13E) ---
        parts.extend(extract_behavioural_reason_codes(row))

        # --- Graph reason codes (Phase 15E) ---
        parts.extend(extract_graph_reason_codes(row))

        # --- Scenario-family contextual label ---
        # Appended last so it reads as analyst context, not a primary signal.
        scenario = str(row.get("scenario_family", "") or "").strip().lower()
        if scenario and scenario != "normal":
            label = _SCENARIO_REASON_LABELS.get(scenario, "")
            if label:
                parts.append(label)

        return "|".join(parts)

    return df.apply(_row_reasons, axis=1)


def generate_basic_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract model features and rich signal features from a scored DataFrame.

    Legacy features (unchanged): hour_of_day, is_night_transaction, is_high_amount,
    is_international, is_high_risk_payment_method, is_high_risk_country,
    is_high_risk_merchant_category, has_device_id, is_mobile_device.

    Rich signal features (Phase 12F-3): added from optional rich CSV columns.
    Each uses a column-existence guard — legacy CSVs without these columns
    receive a scalar 0 with no intermediate Series allocation, preserving
    the performance of the 10M benchmark path.
    """
    # --- Legacy features ---
    df["hour_of_day"] = pd.to_datetime(df["timestamp"]).dt.hour
    df["is_night_transaction"] = df["hour_of_day"].apply(lambda h: 1 if h < 6 or h > 22 else 0)
    df["is_high_amount"] = df["amount"].apply(lambda a: 1 if a > HIGH_AMOUNT_THRESHOLD else 0)
    df["is_international"] = (
        df.get("is_international", pd.Series([False] * len(df), index=df.index))
        .fillna(False)
        .astype(int)
    )
    df["is_high_risk_payment_method"] = (
        df.get("payment_method", pd.Series([""] * len(df), index=df.index))
        .fillna("")
        .apply(lambda m: 1 if str(m).lower() in HIGH_RISK_PAYMENT_METHODS else 0)
    )
    df["is_high_risk_country"] = (
        df.get("country", pd.Series(["US"] * len(df), index=df.index))
        .fillna("US")
        .apply(lambda c: 0 if str(c).upper() in LOW_RISK_COUNTRIES else 1)
    )
    df["is_high_risk_merchant_category"] = (
        df.get("merchant_category", pd.Series([None] * len(df), index=df.index))
        .fillna("")
        .apply(lambda c: 1 if str(c).lower() in HIGH_RISK_MERCHANT_CATEGORIES else 0)
    )
    df["has_device_id"] = (
        df.get("device_id", pd.Series([None] * len(df), index=df.index))
        .apply(lambda d: 0 if (d is None or str(d).strip() == "" or str(d).lower() == "none") else 1)
    )
    df["is_mobile_device"] = (
        df.get("device_type", pd.Series([None] * len(df), index=df.index))
        .fillna("")
        .apply(lambda t: 1 if str(t).lower() == "mobile" else 0)
    )

    # --- Behavioural baseline fields (Phase 13B) ---
    if "customer_avg_amount_30d" in df.columns:
        df["customer_avg_amount_30d"] = _coerce_numeric(df["customer_avg_amount_30d"])
    if "customer_avg_amount_90d" in df.columns:
        df["customer_avg_amount_90d"] = _coerce_numeric(df["customer_avg_amount_90d"])
    if "customer_txn_count_24h_baseline" in df.columns:
        df["customer_txn_count_24h_baseline"] = _coerce_numeric(df["customer_txn_count_24h_baseline"])
    if "customer_txn_count_7d_baseline" in df.columns:
        df["customer_txn_count_7d_baseline"] = _coerce_numeric(df["customer_txn_count_7d_baseline"])
    if "account_avg_balance_30d" in df.columns:
        df["account_avg_balance_30d"] = _coerce_numeric(df["account_avg_balance_30d"])
    if "account_failed_attempts_30d" in df.columns:
        df["account_failed_attempts_30d"] = _coerce_numeric(df["account_failed_attempts_30d"])
    if "device_seen_count_90d" in df.columns:
        df["device_seen_count_90d"] = _coerce_numeric(df["device_seen_count_90d"])
    if "device_first_seen_days" in df.columns:
        df["device_first_seen_days"] = _coerce_numeric(df["device_first_seen_days"])
    if "merchant_customer_frequency_90d" in df.columns:
        df["merchant_customer_frequency_90d"] = _coerce_numeric(df["merchant_customer_frequency_90d"])
    if "counterparty_seen_before" in df.columns:
        df["counterparty_seen_before"] = _parse_optional_bool(df["counterparty_seen_before"])
    if "counterparty_first_seen_days" in df.columns:
        df["counterparty_first_seen_days"] = _coerce_numeric(df["counterparty_first_seen_days"])
    if "usual_country" in df.columns:
        df["usual_country"] = _normalize_str(df["usual_country"]).str.upper()
    if "usual_channel" in df.columns:
        df["usual_channel"] = _normalize_str(df["usual_channel"]).str.lower()
    if "usual_payment_method" in df.columns:
        df["usual_payment_method"] = _normalize_str(df["usual_payment_method"]).str.lower()

    # --- Rich signal features (Phase 12F-3) ---
    # Each block guards on column presence so legacy CSVs pay zero overhead.
    # Default values are the safe non-triggering value for each feature.

    # device_trust_score < 0.4 → unrecognised or low-trust device
    # Default 1.0 (fully trusted) when column absent.
    if "device_trust_score" in df.columns:
        df["is_low_trust_device"] = (
            pd.to_numeric(df["device_trust_score"], errors="coerce").fillna(1.0) < 0.4
        ).astype(int)
    else:
        df["is_low_trust_device"] = 0

    # geo_distance_km > 500 → IP location inconsistent with billing address
    if "geo_distance_km" in df.columns:
        df["is_geo_anomaly"] = (
            pd.to_numeric(df["geo_distance_km"], errors="coerce").fillna(0.0) > 500
        ).astype(int)
    else:
        df["is_geo_anomaly"] = 0

    # txn_count_1h > 5 → velocity exceeds 1-hour baseline
    if "txn_count_1h" in df.columns:
        df["is_high_velocity_1h"] = (
            pd.to_numeric(df["txn_count_1h"], errors="coerce").fillna(0) > 5
        ).astype(int)
    else:
        df["is_high_velocity_1h"] = 0

    # failed_attempts_1h >= 4 → multiple failed attempts in the last hour
    if "failed_attempts_1h" in df.columns:
        df["has_failed_attempts"] = (
            pd.to_numeric(df["failed_attempts_1h"], errors="coerce").fillna(0) >= 4
        ).astype(int)
    else:
        df["has_failed_attempts"] = 0

    # merchant_risk_score >= 0.7 → high-risk merchant
    if "merchant_risk_score" in df.columns:
        df["is_high_risk_merchant_score"] = (
            pd.to_numeric(df["merchant_risk_score"], errors="coerce").fillna(0.0) >= 0.7
        ).astype(int)
    else:
        df["is_high_risk_merchant_score"] = 0

    # new_payee_flag = true AND amount > 500 → first-time high-value payee
    if "new_payee_flag" in df.columns:
        _new_payee = (
            df["new_payee_flag"]
            .astype(str).str.strip().str.lower()
            .isin(["true", "1"])
        )
        df["is_new_payee_high_value"] = (
            _new_payee & (df["amount"] > 500)
        ).astype(int)
    else:
        df["is_new_payee_high_value"] = 0

    # chargeback_count_90d >= 2 → elevated chargeback history
    if "chargeback_count_90d" in df.columns:
        df["has_chargebacks"] = (
            pd.to_numeric(df["chargeback_count_90d"], errors="coerce").fillna(0) >= 2
        ).astype(int)
    else:
        df["has_chargebacks"] = 0

    # amount > 3 × avg_transaction_amount_30d → significant amount anomaly
    if "avg_transaction_amount_30d" in df.columns:
        _avg30 = pd.to_numeric(df["avg_transaction_amount_30d"], errors="coerce").fillna(0.0)
        df["is_amount_anomaly"] = (
            (_avg30 > 0) & (df["amount"] > 3 * _avg30)
        ).astype(int)
    else:
        df["is_amount_anomaly"] = 0

    # scenario_family present and not 'normal' → rich fraud scenario record
    if "scenario_family" in df.columns:
        df["is_rich_fraud_scenario"] = (
            ~df["scenario_family"]
            .fillna("").astype(str).str.strip().str.lower()
            .isin(["", "normal"])
        ).astype(int)
    else:
        df["is_rich_fraud_scenario"] = 0

    # --- Behavioural derived features (Phase 13B) ---
    amount = _coerce_numeric(df["amount"]).fillna(0.0)

    if "customer_avg_amount_30d" in df.columns or "customer_avg_amount_90d" in df.columns:
        avg30 = df["customer_avg_amount_30d"] if "customer_avg_amount_30d" in df.columns else None
        avg90 = df["customer_avg_amount_90d"] if "customer_avg_amount_90d" in df.columns else None
        if avg30 is not None and avg90 is not None:
            baseline_amount = avg30.where(avg30 > 0, avg90)
        else:
            baseline_amount = avg30 if avg30 is not None else avg90
        df["amount_deviation_ratio"] = (
            amount / baseline_amount
        ).where(baseline_amount > 0).fillna(0.0)
    else:
        df["amount_deviation_ratio"] = 0.0

    if "txn_count_24h" in df.columns and "customer_txn_count_24h_baseline" in df.columns:
        current_txn_24h = _coerce_numeric(df["txn_count_24h"])
        baseline_txn_24h = df["customer_txn_count_24h_baseline"]
        df["velocity_deviation_ratio"] = (
            current_txn_24h / baseline_txn_24h
        ).where(baseline_txn_24h > 0).fillna(0.0)
    else:
        df["velocity_deviation_ratio"] = 0.0

    if "account_avg_balance_30d" in df.columns and (
        "account_balance_before" in df.columns or "account_balance_after" in df.columns
    ):
        baseline_balance = df["account_avg_balance_30d"]
        if "account_balance_before" in df.columns:
            current_balance = _coerce_numeric(df["account_balance_before"])
        else:
            current_balance = _coerce_numeric(df["account_balance_after"])
        df["balance_drop_ratio"] = (
            amount / baseline_balance
        ).where((baseline_balance > 0) & current_balance.notna()).fillna(0.0)
    else:
        df["balance_drop_ratio"] = 0.0

    if "device_seen_count_90d" in df.columns or "device_first_seen_days" in df.columns:
        new_device = pd.Series(False, index=df.index)
        if "device_seen_count_90d" in df.columns:
            new_device = new_device | (df["device_seen_count_90d"] <= 1)
        if "device_first_seen_days" in df.columns:
            new_device = new_device | (df["device_first_seen_days"] <= 1)
        df["new_device_for_customer"] = new_device.fillna(False).astype(int)
    else:
        df["new_device_for_customer"] = 0

    if "country" in df.columns and "usual_country" in df.columns:
        current_country = _normalize_str(df["country"]).str.upper()
        usual_country = df["usual_country"]
        df["new_country_for_customer"] = (
            (current_country != "")
            & (usual_country != "")
            & (current_country != usual_country)
        ).astype(int)
    else:
        df["new_country_for_customer"] = 0

    if "counterparty_seen_before" in df.columns or "counterparty_first_seen_days" in df.columns:
        new_counterparty = pd.Series(False, index=df.index)
        if "counterparty_seen_before" in df.columns:
            new_counterparty = new_counterparty | (df["counterparty_seen_before"] == False)
        if "counterparty_first_seen_days" in df.columns:
            new_counterparty = new_counterparty | (df["counterparty_first_seen_days"] <= 1)
        df["new_counterparty_for_account"] = new_counterparty.fillna(False).astype(int)
    else:
        df["new_counterparty_for_account"] = 0

    if "channel" in df.columns and "usual_channel" in df.columns:
        current_channel = _normalize_str(df["channel"]).str.lower()
        usual_channel = df["usual_channel"]
        df["unusual_channel_for_customer"] = (
            (current_channel != "")
            & (usual_channel != "")
            & (current_channel != usual_channel)
        ).astype(int)
    else:
        df["unusual_channel_for_customer"] = 0

    if "merchant_customer_frequency_90d" in df.columns:
        df["unusual_merchant_for_customer"] = (
            df["merchant_customer_frequency_90d"].fillna(1) <= 0
        ).astype(int)
    else:
        df["unusual_merchant_for_customer"] = 0

    # --- Graph features (Phase 15C) ---
    # Adds 9 relationship-level indicator columns derived from entity adjacency
    # within the batch. These columns have no effect on risk_score in Phase 15C --
    # investigator.py does not reference them yet. Phase 15D will integrate them
    # into the graph_boost formula when scoring is extended.
    df = extract_graph_features(df)

    return df
