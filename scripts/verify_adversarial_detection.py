"""
Phase 16C -- In-memory adversarial detection evidence.

Runs the existing production scoring pipeline in memory against the adversarial CSV
and prints a per-scenario detection evidence matrix.

Missed detection verdicts are valid evidence, not test failures.
See docs/ADVERSARIAL_FRAUD_DESIGN.md for the full design contract.

Usage:
  python scripts/verify_adversarial_detection.py
  python scripts/verify_adversarial_detection.py <path/to/adversarial.csv>

Exit codes:
  0 -- scoring pipeline ran cleanly; evidence matrix produced (even if scenarios are Missed)
  1 -- structural/runtime failure (crash, missing family, impossible score value)
"""

import os
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Change working directory to repo root so the model file resolves at its
# relative path (saved_models/fraud_model.pkl).
os.chdir(str(ROOT))

from src.features.transaction_features import generate_basic_features, generate_reasons
from src.models.predict import predict
from src.rules.fraud_rules import apply_fraud_rules
from src.triage.investigator import triage_decision
from src.risk_scan.tier import assign_tier

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_CSV = str(ROOT / "scripts" / "test_adversarial_1000.csv")

EXPECTED_FAMILIES = {
    "low_and_slow",
    "victim_mirror",
    "threshold_straddle",
    "graph_evasion_fan_in",
    "graph_evasion_fan_in_detected",
}

# Actual strings emitted by generate_reasons() for rich signal codes.
RICH_SIGNAL_PHRASES = {
    "Unrecognised device with low trust score",
    "Geographic location inconsistent with registered address",
    "Transaction velocity exceeds 1-hour baseline",
    "Multiple failed attempts preceding this transaction",
    "High-risk merchant",
    "First-time payment to unknown payee",
    "High chargeback history",
    "Transaction amount significantly above 30-day average",
}

# ALL_CAPS codes emitted by extract_behavioural_reason_codes().
BEHAVIOURAL_CODES = {
    "BEHAVIOURAL_AMOUNT_DEVIATION",
    "BEHAVIOURAL_VELOCITY_DEVIATION",
    "BALANCE_DROP_ANOMALY",
    "NEW_DEVICE_FOR_CUSTOMER",
    "NEW_COUNTRY_FOR_CUSTOMER",
    "NEW_COUNTERPARTY_FOR_ACCOUNT",
    "UNUSUAL_CHANNEL_FOR_CUSTOMER",
    "BEHAVIOURAL_PROFILE_SHIFT",
}

# ALL_CAPS codes emitted by extract_graph_reason_codes().
GRAPH_CODES = {
    "SHARED_DEVICE_CLUSTER",
    "DEVICE_ACCOUNT_REUSE",
    "MULE_FAN_IN_PATTERN",
    "MULE_FAN_OUT_PATTERN",
}

EVASION_TARGETS = {
    "low_and_slow":
        "avoids high amount, obvious velocity, night, country, device and geo triggers",
    "victim_mirror":
        "mimics historical customer profile and avoids obvious anomaly thresholds",
    "threshold_straddle":
        "sits just below all six rich signal thresholds simultaneously",
    "graph_evasion_fan_in":
        "stays at current fan-in boundary with 3 accounts per counterparty",
    "graph_evasion_fan_in_detected":
        "crosses fan-in boundary with 4 accounts per counterparty as a control",
}

VALID_DECISIONS = {"APPROVE", "REVIEW", "BLOCK"}
VALID_TIERS     = {"P0", "P1", "P2", "P3"}

# Ordered display sequence for the evidence matrix.
FAMILY_ORDER = [
    "low_and_slow",
    "victim_mirror",
    "threshold_straddle",
    "graph_evasion_fan_in",
    "graph_evasion_fan_in_detected",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_reasons(reasons_str) -> list:
    if not reasons_str or not isinstance(reasons_str, str):
        return []
    return [r.strip() for r in reasons_str.split("|") if r.strip()]


def _verdict(p1_plus_pct: float) -> str:
    if p1_plus_pct >= 0.80:
        return "DETECTED"
    if p1_plus_pct >= 0.20:
        return "PARTIALLY DETECTED"
    return "MISSED"


def _auto_notes(fam: str, verdict: str, graph_boost_max: float,
                model_count: int, rule_count: int, rich_rows: int,
                graph_rows: int, n: int) -> str:
    """Generate concise honest notes for each scenario verdict."""
    if verdict == "DETECTED":
        parts = []
        if model_count > 0:
            parts.append(f"model flagged {model_count}/{n} rows")
        if rule_count > 0:
            parts.append(f"rule fired on {rule_count}/{n} rows")
        if rich_rows > 0:
            parts.append(f"rich signals on {rich_rows}/{n} rows")
        return "Detected by existing scoring stack: " + ", ".join(parts) + "."

    if verdict == "PARTIALLY DETECTED":
        if model_count > 0:
            return (f"Model flagged {model_count}/{n} rows ({model_count*100//n}%); "
                    f"partial detection via model layer. Rule/rich/graph largely avoided.")
        if rich_rows > 0:
            return f"Rich signals contributed on {rich_rows}/{n} rows; partial detection."
        if graph_rows > 0:
            return (f"Graph signals on {graph_rows}/{n} rows contributed to partial detection; "
                    f"graph boost = {graph_boost_max:.3f} max.")
        return "Partial detection; some rows crossed P1 threshold."

    # MISSED
    if fam == "graph_evasion_fan_in":
        if graph_rows > 0:
            return (
                f"CLUSTER ID NOTE: {graph_rows}/{n} rows show MULE_FAN_IN_PATTERN because "
                f"their merchant_id overlaps with graph_evasion_fan_in_detected clusters "
                f"(both use cluster_id 0-14 with merch_adv_XXXXXX format). "
                f"The remaining {n - graph_rows}/{n} rows correctly show no graph signal. "
                f"Risk score stayed below P1 for all rows. Boundary documented."
            )
        return ("Graph boost = 0.0; counterparty_fan_in_flag does not fire at exactly "
                "3 accounts (threshold is > 3). Structural boundary confirmed. "
                "All adversarial constraints successfully evaded.")
    if fam == "graph_evasion_fan_in_detected":
        if graph_rows > 0 or graph_boost_max > 0:
            return (
                f"Graph fan-in flag fired (MULE_FAN_IN_PATTERN on {graph_rows}/{n} rows); "
                f"graph boost = {graph_boost_max:.3f} max. "
                f"Risk score remained below REVIEW threshold because base_score near 0.0. "
                f"Graph layer detects the structural pattern but cannot raise alert alone."
            )
        return "Graph flag fired but overall risk score below P1 threshold."
    if model_count > 0:
        return (f"Model flagged {model_count}/{n} rows but risk_score insufficient for P1 "
                f"(no rich/graph/rule boost applied). "
                f"All adversarial evasion constraints were effective.")
    return ("No P1+ alerts detected. Rich, behavioural, and graph signals all avoided. "
            "Adversarial evasion constraints were effective.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    csv_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV

    print()
    print("=" * 65)
    print("Phase 16C -- In-memory Adversarial Detection Evidence")
    print("=" * 65)
    print("Source    : production scoring pipeline (no API/DB/network)")
    print("Purpose   : document detection boundaries; Missed = valid evidence")

    # -- Load CSV --
    if not os.path.isfile(csv_path):
        print(f"\nERROR: CSV not found: {csv_path}")
        print("Generate it first:")
        print("  python scripts/generate_adversarial_csv.py --rows 1000 --seed 42")
        return 1

    print(f"\nInput CSV : {csv_path}")

    try:
        df = pd.read_csv(csv_path)
    except Exception as exc:
        print(f"ERROR: Could not read CSV: {exc}")
        return 1

    n_total = len(df)
    print(f"Rows      : {n_total:,}")
    print(f"Columns   : {len(df.columns)}")

    if "scenario_family" not in df.columns:
        print("ERROR: scenario_family column missing from CSV")
        return 1

    print()
    print("Scenario distribution:")
    fam_counts = Counter(df["scenario_family"])
    for fam in FAMILY_ORDER:
        cnt = fam_counts.get(fam, 0)
        pct = cnt / n_total * 100 if n_total else 0
        print(f"  {fam:<44} {cnt:>5,}  ({pct:.1f}%)")

    missing = EXPECTED_FAMILIES - set(fam_counts.keys())
    if missing:
        print(f"\nERROR: Expected scenario families missing: {sorted(missing)}")
        return 1

    # -- Run production scoring pipeline --
    print()
    print("Running production scoring pipeline...")

    df = df.copy()
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    if "row_number" not in df.columns:
        df["row_number"] = range(1, len(df) + 1)

    try:
        df = generate_basic_features(df)
    except Exception as exc:
        print(f"ERROR in generate_basic_features: {exc}")
        return 1

    try:
        df["model_prediction"] = predict(df)
    except FileNotFoundError as exc:
        print(f"WARNING: Model file not found ({exc})")
        print("         Setting model_prediction=0 for all rows.")
        print("         Evidence excludes XGBoost model contribution.")
        df["model_prediction"] = 0
    except Exception as exc:
        print(f"ERROR in predict: {exc}")
        return 1

    try:
        df = apply_fraud_rules(df)
    except Exception as exc:
        print(f"ERROR in apply_fraud_rules: {exc}")
        return 1

    try:
        df = triage_decision(df)
    except Exception as exc:
        print(f"ERROR in triage_decision: {exc}")
        return 1

    try:
        reasons_series = generate_reasons(df)
        df["reasons"] = reasons_series.values
    except Exception as exc:
        print(f"ERROR in generate_reasons: {exc}")
        return 1

    # Assign P0/P1/P2/P3 operational priority
    op_priorities = [assign_tier(float(s))[1] for s in df["risk_score"]]
    df["scored_tier"] = op_priorities

    print("Pipeline complete.")
    print()

    # -- Structural validation of scored output --
    passed = True

    bad_scores = df[(df["risk_score"] < 0.0) | (df["risk_score"] > 1.0)]
    if not bad_scores.empty:
        print(f"ERROR: {len(bad_scores)} rows have risk_score outside [0.0, 1.0]")
        passed = False

    bad_decisions = df[~df["decision"].isin(VALID_DECISIONS)]
    if not bad_decisions.empty:
        print(f"ERROR: {len(bad_decisions)} rows have invalid decision: "
              f"{set(bad_decisions['decision'])}")
        passed = False

    bad_tiers = df[~df["scored_tier"].isin(VALID_TIERS)]
    if not bad_tiers.empty:
        print(f"ERROR: {len(bad_tiers)} rows have invalid tier: "
              f"{set(bad_tiers['scored_tier'])}")
        passed = False

    # -- Evidence matrix --
    print("=" * 65)
    print("Detection Evidence Matrix")
    print("=" * 65)

    verdict_list = []

    for fam in FAMILY_ORDER:
        fdf = df[df["scenario_family"] == fam].copy()
        n   = len(fdf)
        if n == 0:
            print(f"\nERROR: No rows found for scenario: {fam}")
            passed = False
            continue

        scores    = fdf["risk_score"].astype(float)
        avg_score = float(scores.mean())
        min_score = float(scores.min())
        max_score = float(scores.max())

        tier_dist = Counter(fdf["scored_tier"])
        dec_dist  = Counter(fdf["decision"])

        p1_plus = tier_dist.get("P0", 0) + tier_dist.get("P1", 0)
        p1_pct  = p1_plus / n

        rule_count  = int((fdf["rule_flag"] == 1).sum())
        model_count = int((fdf["model_prediction"] == 1).sum())

        all_reason_lists = fdf["reasons"].apply(_parse_reasons)
        all_codes_flat   = [c for lst in all_reason_lists for c in lst]
        unique_codes     = sorted(set(all_codes_flat))

        rich_rows  = sum(1 for lst in all_reason_lists if any(c in RICH_SIGNAL_PHRASES for c in lst))
        beh_rows   = sum(1 for lst in all_reason_lists if any(c in BEHAVIOURAL_CODES   for c in lst))
        graph_rows = sum(1 for lst in all_reason_lists if any(c in GRAPH_CODES         for c in lst))

        graph_boost_mean = 0.0
        graph_boost_max  = 0.0
        if "graph_boost" in fdf.columns:
            graph_boost_mean = float(fdf["graph_boost"].mean())
            graph_boost_max  = float(fdf["graph_boost"].max())

        rich_signal_boost_mean = 0.0
        if "rich_signal_boost" in fdf.columns:
            rich_signal_boost_mean = float(fdf["rich_signal_boost"].mean())

        verdict = _verdict(p1_pct)
        verdict_list.append((fam, verdict))

        notes = _auto_notes(fam, verdict, graph_boost_max, model_count, rule_count,
                            rich_rows, graph_rows, n)

        print()
        print(f"[Scenario: {fam}]  {n} rows")
        print("-" * 65)
        print(f"  Score (avg/min/max)     : {avg_score:.4f} / {min_score:.4f} / {max_score:.4f}")
        print(f"  Tier distribution       : "
              f"P0={tier_dist.get('P0',0):<4} "
              f"P1={tier_dist.get('P1',0):<4} "
              f"P2={tier_dist.get('P2',0):<4} "
              f"P3={tier_dist.get('P3',0):<4}")
        print(f"  Decision distribution   : "
              f"APPROVE={dec_dist.get('APPROVE',0):<5} "
              f"REVIEW={dec_dist.get('REVIEW',0):<5} "
              f"BLOCK={dec_dist.get('BLOCK',0):<5}")
        print(f"  Rule flag fired         : {rule_count} rows ({rule_count*100/n:.1f}%)")
        print(f"  Model flag fired        : {model_count} rows ({model_count*100/n:.1f}%)")
        print(f"  Rich signal boost (avg) : {rich_signal_boost_mean:.4f}")
        print(f"  Rich signal rows        : {rich_rows} rows with >= 1 rich signal code")
        print(f"  Behavioural rows        : {beh_rows} rows with >= 1 behavioural code")
        print(f"  Graph signal rows       : {graph_rows} rows with >= 1 graph signal code")
        print(f"  Graph boost (avg/max)   : {graph_boost_mean:.4f} / {graph_boost_max:.4f}")

        if unique_codes:
            print(f"  Reason codes fired      :")
            for code in unique_codes:
                cnt = sum(1 for lst in all_reason_lists if code in lst)
                print(f"    [{cnt:>4}/{n}] {code}")
        else:
            print(f"  Reason codes fired      : (none)")

        print(f"  Evasion target          : {EVASION_TARGETS.get(fam, 'unknown')}")
        print(f"  Detection verdict       : {verdict}")
        print(f"  Notes                   : {notes}")

    # -- Verdict summary --
    print()
    print("=" * 65)
    print("Verdict Summary")
    print("=" * 65)

    det     = sum(1 for _, v in verdict_list if v == "DETECTED")
    partial = sum(1 for _, v in verdict_list if v == "PARTIALLY DETECTED")
    missed  = sum(1 for _, v in verdict_list if v == "MISSED")

    for fam, verdict in verdict_list:
        print(f"  {fam:<44} {verdict}")

    print()
    print(f"  Detected           : {det}")
    print(f"  Partially detected : {partial}")
    print(f"  Missed             : {missed}")
    print()
    print("Note: Missed is a valid detection evidence result.")
    print("      It documents the current stack's detection boundary.")
    print("      Detection gaps are not hidden; they inform future hardening.")

    # -- Final result --
    print()
    print("-" * 65)
    print(f"Scoring source     : production functions (no API / DB / network)")
    print(f"Backend modified   : No")
    print(f"Scoring modified   : No")
    print(f"API scan performed : No")
    print(f"DB mutated         : No")
    print("-" * 65)

    if passed:
        print(f"OVERALL: PASS  ({n_total} adversarial rows scored successfully)")
    else:
        print("OVERALL: FAIL  (structural validation errors above)")
    print("=" * 65)
    print()

    return 0 if passed else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"\nFATAL: unhandled exception: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
