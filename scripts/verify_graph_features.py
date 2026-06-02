"""
Phase 15C -- Production graph feature extraction verification.

Validates that extract_graph_features() in src/features/transaction_features.py
produces the expected indicator values for all 7 controlled scenarios defined
in Phase 15B. The production function replaces the local compute_graph_indicators()
that was used for in-memory validation in Phase 15B.

This mirrors the Phase 13 pattern: behavioural feature logic was validated in a
standalone script, then moved to transaction_features.py, and the standalone script
was updated to import and test the production function.

Indicators validated (9) -- from src.features.transaction_features.extract_graph_features:
  accounts_per_device           -- distinct account_id count per device_id
  shared_device_flag            -- accounts_per_device >= _GRAPH_SHARED_DEVICE_THRESHOLD (2)
  customers_per_device          -- distinct customer_id count per device_id
  cross_account_device_reuse    -- device shared across DIFFERENT customer_ids
  device_cluster_size           -- customers_per_device + accounts_per_device
  accounts_per_counterparty     -- distinct account_id count per merchant_id
  counterparty_fan_in_flag      -- accounts_per_counterparty > _GRAPH_FAN_IN_THRESHOLD (3)
  counterparties_per_account    -- distinct merchant_id count per account_id
  counterparty_fan_out_flag     -- counterparties_per_account > _GRAPH_FAN_OUT_THRESHOLD (3)

Thresholds are provisional values from _GRAPH_* constants in transaction_features.py.
They are NOT production-calibrated and will be reviewed in Phase 15D.

Scenarios (7):
  N1 -- No entity fields present          -> all indicators neutral
  N2 -- All unique entities               -> no sharing signals
  G1 -- Device cluster (2 customers)      -> shared device + cross-customer reuse
  G2 -- Fan-in counterparty (5 accounts)  -> counterparty fan-in
  G3 -- Fan-out account (4 counterparties)-> account fan-out
  G4 -- Same-customer device guardrail    -> cross_account_device_reuse MUST be False
  G5 -- Mixed scan                        -> risky rows flagged, clean rows neutral

Exit codes: 0 on full pass, 1 on any failure.
graph_boost: NOT implemented in this slice (Phase 15D).
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.features.transaction_features import (
    _GRAPH_FAN_IN_THRESHOLD,
    _GRAPH_FAN_OUT_THRESHOLD,
    _GRAPH_SHARED_DEVICE_THRESHOLD,
    extract_graph_features,
)

# ---------------------------------------------------------------------------
# Reporting state
# ---------------------------------------------------------------------------
_PASS_COUNT = 0
_FAIL_COUNT = 0


def _pass(label: str) -> None:
    global _PASS_COUNT
    _PASS_COUNT += 1
    print(f"[PASS]  {label}")


def _fail(label: str, reason: str) -> None:
    global _FAIL_COUNT
    _FAIL_COUNT += 1
    print(f"[FAIL]  {label}  -- {reason}")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


# ---------------------------------------------------------------------------
# Controlled scenario helpers
# ---------------------------------------------------------------------------

def _row(tid: str, dev: str, acct: str, cust: str, merch: str) -> dict:
    """Build a minimal transaction row with all entity fields."""
    return {
        "transaction_id": tid,
        "amount": 100.0,
        "timestamp": "2024-01-01T10:00:00",
        "country": "US",
        "payment_method": "debit_card",
        "device_id": dev,
        "account_id": acct,
        "customer_id": cust,
        "merchant_id": merch,
    }


# ---------------------------------------------------------------------------
# Scenario N1 -- No entity fields
# ---------------------------------------------------------------------------

def test_n1_no_entity_fields() -> None:
    label = "[N1] No entity fields -> all indicators = 0 / False, no crash"
    try:
        df = pd.DataFrame({
            "transaction_id": ["t1", "t2", "t3"],
            "amount":         [100.0, 200.0, 300.0],
            "timestamp":      ["2024-01-01T10:00:00"] * 3,
            "country":        ["US", "GB", "DE"],
            "payment_method": ["debit_card", "credit_card", "bank_transfer"],
        })
        r = extract_graph_features(df)

        _assert(r["accounts_per_device"].sum() == 0,
                "accounts_per_device not zero without device/account fields")
        _assert(not r["shared_device_flag"].any(),
                "shared_device_flag triggered without entity fields")
        _assert(not r["cross_account_device_reuse"].any(),
                "cross_account_device_reuse triggered without entity fields")
        _assert(r["accounts_per_counterparty"].sum() == 0,
                "accounts_per_counterparty not zero without merchant/account fields")
        _assert(not r["counterparty_fan_in_flag"].any(),
                "counterparty_fan_in_flag triggered without entity fields")
        _assert(r["counterparties_per_account"].sum() == 0,
                "counterparties_per_account not zero without entity fields")
        _assert(not r["counterparty_fan_out_flag"].any(),
                "counterparty_fan_out_flag triggered without entity fields")
        _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))
    except Exception as exc:
        _fail(label, f"unexpected crash: {exc}")


# ---------------------------------------------------------------------------
# Scenario N2 -- All unique entities
# ---------------------------------------------------------------------------

def test_n2_all_unique_entities() -> None:
    label = "[N2] All unique entities -> no sharing signals anywhere"
    try:
        rows = [_row(f"t{i}", f"dev_{i}", f"acct_{i}", f"cust_{i}", f"merch_{i}")
                for i in range(1, 6)]
        r = extract_graph_features(pd.DataFrame(rows))

        _assert((r["accounts_per_device"] == 1).all(),
                f"accounts_per_device != 1 for unique devices: {r['accounts_per_device'].tolist()}")
        _assert(not r["shared_device_flag"].any(),
                "shared_device_flag triggered on unique devices")
        _assert(not r["cross_account_device_reuse"].any(),
                "cross_account_device_reuse triggered on unique entities")
        _assert((r["accounts_per_counterparty"] == 1).all(),
                f"accounts_per_counterparty != 1 for unique counterparties: {r['accounts_per_counterparty'].tolist()}")
        _assert(not r["counterparty_fan_in_flag"].any(),
                "counterparty_fan_in_flag triggered on unique counterparties")
        _assert((r["counterparties_per_account"] == 1).all(),
                f"counterparties_per_account != 1 for unique accounts: {r['counterparties_per_account'].tolist()}")
        _assert(not r["counterparty_fan_out_flag"].any(),
                "counterparty_fan_out_flag triggered on unique accounts")
        _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))


# ---------------------------------------------------------------------------
# Scenario G1 -- Device cluster (2 customers)
# ---------------------------------------------------------------------------

def test_g1_device_cluster() -> None:
    label = "[G1] Device cluster -> shared_device_flag=True, cross_account_device_reuse=True"
    try:
        rows = [
            _row("t1", "dev_X", "acct_A", "cust_1", "merch_1"),  # cust_1, acct_A
            _row("t2", "dev_X", "acct_B", "cust_1", "merch_2"),  # cust_1, acct_B
            _row("t3", "dev_X", "acct_C", "cust_2", "merch_3"),  # cust_2, acct_C  <-- 2nd customer
            _row("t4", "dev_Y", "acct_D", "cust_3", "merch_4"),  # clean row
        ]
        r = extract_graph_features(pd.DataFrame(rows))

        x = r[r["device_id"] == "dev_X"]
        y = r[r["device_id"] == "dev_Y"]

        _assert((x["accounts_per_device"] == 3).all(),
                f"accounts_per_device for dev_X: expected 3, got {x['accounts_per_device'].tolist()}")
        _assert((x["shared_device_flag"] == True).all(),
                "shared_device_flag not True for dev_X (3 accounts)")
        _assert((x["customers_per_device"] == 2).all(),
                f"customers_per_device for dev_X: expected 2, got {x['customers_per_device'].tolist()}")
        _assert((x["cross_account_device_reuse"] == True).all(),
                "cross_account_device_reuse not True for dev_X (2 distinct customers)")
        _assert((x["device_cluster_size"] == 5).all(),  # 2 customers + 3 accounts
                f"device_cluster_size for dev_X: expected 5, got {x['device_cluster_size'].tolist()}")

        # Clean row must not be contaminated
        _assert((y["accounts_per_device"] == 1).all(),
                f"dev_Y accounts_per_device: expected 1, got {y['accounts_per_device'].tolist()}")
        _assert((y["shared_device_flag"] == False).all(),
                "dev_Y: shared_device_flag should be False")
        _assert((y["cross_account_device_reuse"] == False).all(),
                "dev_Y: cross_account_device_reuse should be False")
        _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))


# ---------------------------------------------------------------------------
# Scenario G2 -- Fan-in counterparty (5 accounts)
# ---------------------------------------------------------------------------

def test_g2_fan_in_counterparty() -> None:
    label = "[G2] Fan-in counterparty -> accounts_per_counterparty=5, fan_in_flag=True"
    try:
        rows = [
            # merch_M receives from 5 distinct accounts (4 customers -- cust_1 appears twice)
            _row("t1", "dev_1", "acct_1", "cust_1", "merch_M"),
            _row("t2", "dev_2", "acct_2", "cust_2", "merch_M"),
            _row("t3", "dev_3", "acct_3", "cust_3", "merch_M"),
            _row("t4", "dev_4", "acct_4", "cust_4", "merch_M"),
            _row("t5", "dev_5", "acct_5", "cust_1", "merch_M"),  # cust_1 second account
            # Clean counterparties
            _row("t6", "dev_6", "acct_6", "cust_5", "merch_N"),
            _row("t7", "dev_7", "acct_7", "cust_6", "merch_P"),
        ]
        r = extract_graph_features(pd.DataFrame(rows))

        m_rows  = r[r["merchant_id"] == "merch_M"]
        cln_cps = r[r["merchant_id"].isin(["merch_N", "merch_P"])]

        _assert((m_rows["accounts_per_counterparty"] == 5).all(),
                f"merch_M accounts_per_counterparty: expected 5, got {m_rows['accounts_per_counterparty'].tolist()}")
        _assert((m_rows["counterparty_fan_in_flag"] == True).all(),
                f"counterparty_fan_in_flag not True for merch_M (5 accounts > threshold {_GRAPH_FAN_IN_THRESHOLD})")
        _assert((cln_cps["counterparty_fan_in_flag"] == False).all(),
                "fan_in_flag leaked to clean counterparties merch_N / merch_P")
        _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))


# ---------------------------------------------------------------------------
# Scenario G3 -- Fan-out account (4 counterparties)
# ---------------------------------------------------------------------------

def test_g3_fan_out_account() -> None:
    label = "[G3] Fan-out account -> counterparties_per_account=4, fan_out_flag=True"
    try:
        rows = [
            # acct_A interacts with 4 distinct counterparties
            _row("t1", "dev_1", "acct_A", "cust_1", "merch_1"),
            _row("t2", "dev_1", "acct_A", "cust_1", "merch_2"),
            _row("t3", "dev_1", "acct_A", "cust_1", "merch_3"),
            _row("t4", "dev_1", "acct_A", "cust_1", "merch_4"),
            # acct_B interacts with only 2 counterparties (below threshold)
            _row("t5", "dev_2", "acct_B", "cust_2", "merch_5"),
            _row("t6", "dev_2", "acct_B", "cust_2", "merch_6"),
        ]
        r = extract_graph_features(pd.DataFrame(rows))

        a_rows = r[r["account_id"] == "acct_A"]
        b_rows = r[r["account_id"] == "acct_B"]

        _assert((a_rows["counterparties_per_account"] == 4).all(),
                f"acct_A counterparties_per_account: expected 4, got {a_rows['counterparties_per_account'].tolist()}")
        _assert((a_rows["counterparty_fan_out_flag"] == True).all(),
                f"counterparty_fan_out_flag not True for acct_A (4 > threshold {_GRAPH_FAN_OUT_THRESHOLD})")
        _assert((b_rows["counterparties_per_account"] == 2).all(),
                f"acct_B counterparties_per_account: expected 2, got {b_rows['counterparties_per_account'].tolist()}")
        _assert((b_rows["counterparty_fan_out_flag"] == False).all(),
                f"counterparty_fan_out_flag triggered for acct_B (2 counterparties, threshold {_GRAPH_FAN_OUT_THRESHOLD})")
        _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))


# ---------------------------------------------------------------------------
# Scenario G4 -- Same-customer device guardrail (false-positive guard)
# ---------------------------------------------------------------------------

def test_g4_same_customer_device_guardrail() -> None:
    label = "[G4] GUARDRAIL: same customer, same device -> cross_account_device_reuse=False"
    try:
        rows = [
            # dev_X used by 3 different accounts but ALL belong to the SAME customer (cust_1)
            _row("t1", "dev_X", "acct_P", "cust_1", "merch_1"),
            _row("t2", "dev_X", "acct_Q", "cust_1", "merch_2"),
            _row("t3", "dev_X", "acct_R", "cust_1", "merch_3"),
            _row("t4", "dev_X", "acct_P", "cust_1", "merch_4"),  # repeat of acct_P
        ]
        r = extract_graph_features(pd.DataFrame(rows))

        x = r[r["device_id"] == "dev_X"]

        _assert((x["accounts_per_device"] == 3).all(),
                f"accounts_per_device for dev_X: expected 3, got {x['accounts_per_device'].tolist()}")
        _assert((x["shared_device_flag"] == True).all(),
                "shared_device_flag should be True (3 accounts share dev_X)")
        _assert((x["customers_per_device"] == 1).all(),
                f"customers_per_device for dev_X: expected 1 (all cust_1), got {x['customers_per_device'].tolist()}")

        # KEY GUARDRAIL: a legitimate customer using multiple accounts on one device
        # must NOT trigger the cross-customer reuse signal.
        _assert((x["cross_account_device_reuse"] == False).all(),
                "GUARDRAIL FAILED: cross_account_device_reuse fired for single-customer device reuse")
        _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))


# ---------------------------------------------------------------------------
# Scenario G5 -- Mixed scan
# ---------------------------------------------------------------------------

def test_g5_mixed_scan() -> None:
    label = "[G5] Mixed scan -> risky rows flagged, clean rows remain neutral (no leakage)"
    try:
        rows = [
            # ---- Clean rows (unique entities) ----
            _row("clean_1", "dev_C1", "acct_C1", "cust_C1", "merch_C1"),
            _row("clean_2", "dev_C2", "acct_C2", "cust_C2", "merch_C2"),
            # ---- Device cluster (dev_X, 2 customers) ----
            _row("dev_1", "dev_X", "acct_A", "cust_A", "merch_1"),
            _row("dev_2", "dev_X", "acct_B", "cust_A", "merch_2"),  # cust_A second account
            _row("dev_3", "dev_X", "acct_C", "cust_B", "merch_3"),  # cust_B -- 2nd customer
            # ---- Fan-in counterparty (merch_M, 4 accounts > threshold 3) ----
            _row("fan_1", "dev_F1", "acct_F1", "cust_F1", "merch_M"),
            _row("fan_2", "dev_F2", "acct_F2", "cust_F2", "merch_M"),
            _row("fan_3", "dev_F3", "acct_F3", "cust_F3", "merch_M"),
            _row("fan_4", "dev_F4", "acct_F4", "cust_F4", "merch_M"),
        ]
        r = extract_graph_features(pd.DataFrame(rows))

        clean = r[r["transaction_id"].str.startswith("clean")]
        dev_x = r[r["device_id"] == "dev_X"]
        fan_m = r[r["merchant_id"] == "merch_M"]

        # ---- Clean rows: no sharing signals ----
        _assert((clean["accounts_per_device"] == 1).all(),
                f"clean rows accounts_per_device: {clean['accounts_per_device'].tolist()}")
        _assert((clean["shared_device_flag"] == False).all(),
                "clean rows: shared_device_flag triggered")
        _assert((clean["cross_account_device_reuse"] == False).all(),
                "clean rows: cross_account_device_reuse triggered")
        _assert((clean["counterparty_fan_in_flag"] == False).all(),
                "clean rows: counterparty_fan_in_flag leaked")
        _assert((clean["counterparty_fan_out_flag"] == False).all(),
                "clean rows: counterparty_fan_out_flag leaked")

        # ---- Device cluster rows: correctly detected ----
        _assert((dev_x["accounts_per_device"] == 3).all(),
                f"dev_X accounts_per_device: expected 3, got {dev_x['accounts_per_device'].tolist()}")
        _assert((dev_x["shared_device_flag"] == True).all(),
                "dev_X: shared_device_flag not True")
        _assert((dev_x["customers_per_device"] == 2).all(),
                f"dev_X customers_per_device: expected 2, got {dev_x['customers_per_device'].tolist()}")
        _assert((dev_x["cross_account_device_reuse"] == True).all(),
                "dev_X: cross_account_device_reuse not True (cust_A and cust_B)")

        # ---- Fan-in rows: correctly detected (4 accounts > threshold 3) ----
        _assert((fan_m["accounts_per_counterparty"] == 4).all(),
                f"merch_M accounts_per_counterparty: expected 4, got {fan_m['accounts_per_counterparty'].tolist()}")
        _assert((fan_m["counterparty_fan_in_flag"] == True).all(),
                f"merch_M: counterparty_fan_in_flag not True (4 accounts > threshold {_GRAPH_FAN_IN_THRESHOLD})")

        _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print()
    print("=" * 65)
    print("Phase 15C -- Graph Feature Verification Report")
    print("=" * 65)
    print("Source: src.features.transaction_features.extract_graph_features")
    print(f"Thresholds (provisional -- NOT production-calibrated):")
    print(f"  _GRAPH_SHARED_DEVICE_THRESHOLD : >= {_GRAPH_SHARED_DEVICE_THRESHOLD} distinct accounts per device")
    print(f"  _GRAPH_FAN_IN_THRESHOLD        : >  {_GRAPH_FAN_IN_THRESHOLD} distinct accounts per counterparty")
    print(f"  _GRAPH_FAN_OUT_THRESHOLD       : >  {_GRAPH_FAN_OUT_THRESHOLD} distinct counterparties per account")
    print()

    print("-- Section 1: Neutral / no-context scenarios --")
    test_n1_no_entity_fields()
    test_n2_all_unique_entities()

    print()
    print("-- Section 2: Mule-network signal scenarios --")
    test_g1_device_cluster()
    test_g2_fan_in_counterparty()
    test_g3_fan_out_account()

    print()
    print("-- Section 3: False-positive guardrail --")
    test_g4_same_customer_device_guardrail()

    print()
    print("-- Section 4: Mixed scan --")
    test_g5_mixed_scan()

    total = _PASS_COUNT + _FAIL_COUNT

    print()
    print("-" * 65)
    print(f"Total scenarios tested   : {total}")
    print()
    print("Indicators validated (9) -- production extract_graph_features():")
    print("  accounts_per_device           distinct accounts per device")
    print(f"  shared_device_flag            accounts_per_device >= {_GRAPH_SHARED_DEVICE_THRESHOLD}")
    print("  customers_per_device          distinct customers per device")
    print("  cross_account_device_reuse    device shared across different customers")
    print("  device_cluster_size           customers_per_device + accounts_per_device")
    print("  accounts_per_counterparty     distinct accounts per counterparty")
    print(f"  counterparty_fan_in_flag      accounts_per_counterparty > {_GRAPH_FAN_IN_THRESHOLD}")
    print("  counterparties_per_account    distinct counterparties per account")
    print(f"  counterparty_fan_out_flag     counterparties_per_account > {_GRAPH_FAN_OUT_THRESHOLD}")
    print()
    print("Candidate reason codes demonstrated:")
    print("  SHARED_DEVICE_CLUSTER     G1 (dev_X: 3 accounts, 2 customers), G5")
    print("  DEVICE_ACCOUNT_REUSE      G1 (cross-customer), G5")
    print("  MULE_FAN_IN_PATTERN       G2 (merch_M: 5 accounts), G5 (merch_M: 4 accounts)")
    print("  MULE_FAN_OUT_PATTERN      G3 (acct_A: 4 counterparties)")
    print()
    print("G4 false-positive guardrail:")
    print("  Same customer (cust_1) uses dev_X across 3 personal accounts.")
    print("  cross_account_device_reuse MUST be False -- single-customer device reuse")
    print("  must not trigger the cross-customer coordination signal.")
    g4_note = "[confirmed PASS]" if _FAIL_COUNT == 0 else "[SEE FAILURES ABOVE]"
    print(f"  Result: {g4_note}")
    print()
    print("graph_boost implementation : NOT included in this slice (Phase 15D)")
    print("Thresholds                 : provisional -- to be calibrated in Phase 15D")
    print("Production source changes  : src/features/transaction_features.py")
    print("No DB, no API, no NetworkX : Confirmed")
    print("-" * 65)

    if _FAIL_COUNT == 0:
        print(f"OVERALL: PASS  ({_PASS_COUNT}/{total} scenarios)")
    else:
        print(f"OVERALL: FAIL  ({_FAIL_COUNT} failure(s) out of {total} scenarios)")
    print("=" * 65)
    print()

    return 0 if _FAIL_COUNT == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"\nFATAL: unhandled exception in verify_graph_features.py: {exc}")
        sys.exit(1)
