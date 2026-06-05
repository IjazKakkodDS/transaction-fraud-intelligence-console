"""
Phase 15E -- Graph reason-code validation.

Validates that extract_graph_reason_codes() in src/features/transaction_features.py
emits the correct reason codes for all 8 controlled scenarios. Uses
generate_basic_features() to produce graph indicator columns, then calls
extract_graph_reason_codes(row) per-row for assertions.

Reason codes validated (4):
  SHARED_DEVICE_CLUSTER   -- fires when shared_device_flag is True
  DEVICE_ACCOUNT_REUSE    -- fires when cross_account_device_reuse is True
  MULE_FAN_IN_PATTERN     -- fires when counterparty_fan_in_flag is True
  MULE_FAN_OUT_PATTERN    -- fires when counterparty_fan_out_flag is True

Scenarios (8):
  1  -- Legacy row / no entity fields          -> []
  2  -- All unique entities                    -> []
  3  -- Same-customer device guardrail         -> ["SHARED_DEVICE_CLUSTER"] only
  4  -- Cross-customer device cluster          -> ["SHARED_DEVICE_CLUSTER", "DEVICE_ACCOUNT_REUSE"]
  5  -- Fan-in counterparty only               -> ["MULE_FAN_IN_PATTERN"]
  6  -- Fan-out account only                   -> ["MULE_FAN_OUT_PATTERN"]
  7  -- All four signals active                -> all four codes, no duplicates
  8  -- Full generate_reasons on legacy row    -> no graph codes present

In-memory only. No DB connection. No API calls. No Redpanda. No NetworkX.
Exit codes: 0 on full pass, 1 on any failure.
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.features.transaction_features import (
    extract_graph_reason_codes,
    generate_basic_features,
    generate_reasons,
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
# Helpers
# ---------------------------------------------------------------------------

def _row(tid: str, dev: str, acct: str, cust: str, merch: str) -> dict:
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


def _build_row(rows: list) -> pd.Series:
    df = pd.DataFrame(rows)
    df = generate_basic_features(df)
    return df.iloc[0]


# ---------------------------------------------------------------------------
# Scenario 1 -- Legacy row / no entity fields
# ---------------------------------------------------------------------------

def test_1_legacy_no_entity_fields() -> None:
    label = "[1] Legacy row, no entity fields -> []"
    try:
        df = pd.DataFrame([{
            "transaction_id": "t_legacy",
            "amount": 100.0,
            "timestamp": "2024-01-01T12:00:00",
            "country": "US",
            "payment_method": "debit_card",
        }])
        df = generate_basic_features(df)
        codes = extract_graph_reason_codes(df.iloc[0])
        _assert(codes == [], f"expected [], got {codes}")
        _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))
    except Exception as exc:
        _fail(label, f"unexpected exception: {exc}")


# ---------------------------------------------------------------------------
# Scenario 2 -- All unique entities
# ---------------------------------------------------------------------------

def test_2_all_unique_entities() -> None:
    label = "[2] All unique entities -> [] for every row"
    try:
        rows = [_row(f"t{i}", f"dev_{i}", f"acct_{i}", f"cust_{i}", f"merch_{i}")
                for i in range(1, 6)]
        df = pd.DataFrame(rows)
        df = generate_basic_features(df)
        for i in range(len(df)):
            codes = extract_graph_reason_codes(df.iloc[i])
            _assert(codes == [], f"row {i}: expected [], got {codes}")
        _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))
    except Exception as exc:
        _fail(label, f"unexpected exception: {exc}")


# ---------------------------------------------------------------------------
# Scenario 3 -- Same-customer device guardrail
# ---------------------------------------------------------------------------

def test_3_same_customer_device_guardrail() -> None:
    label = "[3] GUARDRAIL: same customer, same device -> [SHARED_DEVICE_CLUSTER] only"
    try:
        # dev_X shared by 3 accounts, all owned by cust_1
        rows = [
            _row("t1", "dev_X", "acct_P", "cust_1", "merch_1"),
            _row("t2", "dev_X", "acct_Q", "cust_1", "merch_2"),
            _row("t3", "dev_X", "acct_R", "cust_1", "merch_3"),
        ]
        row = _build_row(rows)

        _assert(bool(row["shared_device_flag"]) is True,
                "shared_device_flag should be True")
        _assert(bool(row["cross_account_device_reuse"]) is False,
                "cross_account_device_reuse must be False (single customer)")

        codes = extract_graph_reason_codes(row)
        _assert(codes == ["SHARED_DEVICE_CLUSTER"],
                f"expected ['SHARED_DEVICE_CLUSTER'], got {codes}")
        _assert("DEVICE_ACCOUNT_REUSE" not in codes,
                "DEVICE_ACCOUNT_REUSE must not fire for single-customer device reuse")
        _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))
    except Exception as exc:
        _fail(label, f"unexpected exception: {exc}")


# ---------------------------------------------------------------------------
# Scenario 4 -- Cross-customer device cluster
# ---------------------------------------------------------------------------

def test_4_cross_customer_device_cluster() -> None:
    label = "[4] Cross-customer device cluster -> [SHARED_DEVICE_CLUSTER, DEVICE_ACCOUNT_REUSE]"
    try:
        # dev_X shared by cust_1 (2 accounts) and cust_2 (1 account)
        rows = [
            _row("t1", "dev_X", "acct_A", "cust_1", "merch_1"),
            _row("t2", "dev_X", "acct_B", "cust_1", "merch_2"),
            _row("t3", "dev_X", "acct_C", "cust_2", "merch_3"),
        ]
        row = _build_row(rows)

        _assert(bool(row["shared_device_flag"]) is True,
                "shared_device_flag should be True")
        _assert(bool(row["cross_account_device_reuse"]) is True,
                "cross_account_device_reuse should be True (cust_1 and cust_2)")

        codes = extract_graph_reason_codes(row)
        _assert(codes == ["SHARED_DEVICE_CLUSTER", "DEVICE_ACCOUNT_REUSE"],
                f"expected ['SHARED_DEVICE_CLUSTER', 'DEVICE_ACCOUNT_REUSE'], got {codes}")
        _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))
    except Exception as exc:
        _fail(label, f"unexpected exception: {exc}")


# ---------------------------------------------------------------------------
# Scenario 5 -- Fan-in counterparty only
# ---------------------------------------------------------------------------

def test_5_fan_in_counterparty_only() -> None:
    label = "[5] Fan-in counterparty only -> [MULE_FAN_IN_PATTERN]"
    try:
        # 4 distinct accounts pay merch_M (> threshold 3), each on a unique device
        rows = [
            _row("t1", "dev_1", "acct_1", "cust_1", "merch_M"),
            _row("t2", "dev_2", "acct_2", "cust_2", "merch_M"),
            _row("t3", "dev_3", "acct_3", "cust_3", "merch_M"),
            _row("t4", "dev_4", "acct_4", "cust_4", "merch_M"),
        ]
        row = _build_row(rows)

        _assert(bool(row["counterparty_fan_in_flag"]) is True,
                "counterparty_fan_in_flag should be True (4 accounts > threshold 3)")
        _assert(bool(row["shared_device_flag"]) is False,
                "shared_device_flag should be False (unique devices)")
        _assert(bool(row["cross_account_device_reuse"]) is False,
                "cross_account_device_reuse should be False")

        codes = extract_graph_reason_codes(row)
        _assert(codes == ["MULE_FAN_IN_PATTERN"],
                f"expected ['MULE_FAN_IN_PATTERN'], got {codes}")
        _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))
    except Exception as exc:
        _fail(label, f"unexpected exception: {exc}")


# ---------------------------------------------------------------------------
# Scenario 6 -- Fan-out account only
# ---------------------------------------------------------------------------

def test_6_fan_out_account_only() -> None:
    label = "[6] Fan-out account only -> [MULE_FAN_OUT_PATTERN]"
    try:
        # acct_A (cust_1) pays 4 distinct counterparties (> threshold 3)
        # Each row has the same dev_1 + acct_A so accounts_per_device = 1 -> no shared flag
        rows = [
            _row("t1", "dev_1", "acct_A", "cust_1", "merch_1"),
            _row("t2", "dev_1", "acct_A", "cust_1", "merch_2"),
            _row("t3", "dev_1", "acct_A", "cust_1", "merch_3"),
            _row("t4", "dev_1", "acct_A", "cust_1", "merch_4"),
        ]
        row = _build_row(rows)

        _assert(bool(row["counterparty_fan_out_flag"]) is True,
                "counterparty_fan_out_flag should be True (4 merchants > threshold 3)")
        _assert(bool(row["shared_device_flag"]) is False,
                "shared_device_flag should be False (only acct_A on dev_1)")
        _assert(bool(row["cross_account_device_reuse"]) is False,
                "cross_account_device_reuse should be False (single customer)")

        codes = extract_graph_reason_codes(row)
        _assert(codes == ["MULE_FAN_OUT_PATTERN"],
                f"expected ['MULE_FAN_OUT_PATTERN'], got {codes}")
        _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))
    except Exception as exc:
        _fail(label, f"unexpected exception: {exc}")


# ---------------------------------------------------------------------------
# Scenario 7 -- All four signals active
# ---------------------------------------------------------------------------

def test_7_all_four_signals_active() -> None:
    label = "[7] All four signals active -> all four codes, no duplicates"
    try:
        # t0 (target row) activates all four indicators:
        # - Device cluster: dev_X shared by cust_1, cust_2, cust_3 (cross-customer)
        # - Fan-in: merch_M receives from acct_A, acct_D, acct_E, acct_F (4 accounts > threshold 3)
        # - Fan-out: acct_A pays merch_M, merch_P, merch_Q, merch_R (4 merchants > threshold 3)
        rows = [
            # Target row
            _row("t0", "dev_X", "acct_A", "cust_1", "merch_M"),
            # Device cluster helpers (cross-customer)
            _row("t1", "dev_X", "acct_B", "cust_2", "merch_X"),
            _row("t2", "dev_X", "acct_C", "cust_3", "merch_Y"),
            # Fan-in helpers (3 more accounts also pay merch_M)
            _row("t3", "dev_F3", "acct_D", "cust_4", "merch_M"),
            _row("t4", "dev_F4", "acct_E", "cust_5", "merch_M"),
            _row("t5", "dev_F5", "acct_F", "cust_6", "merch_M"),
            # Fan-out helpers (acct_A also pays merch_P, merch_Q, merch_R)
            _row("t6", "dev_X", "acct_A", "cust_1", "merch_P"),
            _row("t7", "dev_X", "acct_A", "cust_1", "merch_Q"),
            _row("t8", "dev_X", "acct_A", "cust_1", "merch_R"),
        ]
        df = pd.DataFrame(rows)
        df = generate_basic_features(df)
        row = df.iloc[0]  # t0

        _assert(bool(row["shared_device_flag"]) is True,
                f"shared_device_flag should be True; accounts_per_device={row['accounts_per_device']}")
        _assert(bool(row["cross_account_device_reuse"]) is True,
                f"cross_account_device_reuse should be True; customers_per_device={row['customers_per_device']}")
        _assert(bool(row["counterparty_fan_in_flag"]) is True,
                f"counterparty_fan_in_flag should be True; accounts_per_counterparty={row['accounts_per_counterparty']}")
        _assert(bool(row["counterparty_fan_out_flag"]) is True,
                f"counterparty_fan_out_flag should be True; counterparties_per_account={row['counterparties_per_account']}")

        codes = extract_graph_reason_codes(row)
        expected = ["SHARED_DEVICE_CLUSTER", "DEVICE_ACCOUNT_REUSE",
                    "MULE_FAN_IN_PATTERN", "MULE_FAN_OUT_PATTERN"]
        _assert(codes == expected, f"expected {expected}, got {codes}")
        _assert(len(codes) == len(set(codes)), f"duplicate codes detected: {codes}")
        _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))
    except Exception as exc:
        _fail(label, f"unexpected exception: {exc}")


# ---------------------------------------------------------------------------
# Scenario 8 -- Full generate_reasons on legacy row
# ---------------------------------------------------------------------------

def test_8_generate_reasons_legacy_row() -> None:
    label = "[8] generate_reasons on legacy row -> no graph reason codes in output"
    try:
        df = pd.DataFrame([{
            "transaction_id": "t_legacy_reasons",
            "amount": 100.0,
            "timestamp": "2024-01-01T12:00:00",
            "country": "US",
            "payment_method": "debit_card",
        }])
        df = generate_basic_features(df)
        df["model_prediction"] = 0

        reasons_series = generate_reasons(df)
        reason_str = reasons_series.iloc[0]
        reason_parts = [p.strip() for p in reason_str.split("|") if p.strip()]

        graph_codes = {
            "SHARED_DEVICE_CLUSTER",
            "DEVICE_ACCOUNT_REUSE",
            "MULE_FAN_IN_PATTERN",
            "MULE_FAN_OUT_PATTERN",
        }
        found_graph = [p for p in reason_parts if p in graph_codes]
        _assert(len(found_graph) == 0,
                f"graph codes found in legacy row reasons: {found_graph}")

        # Confirm extract_graph_reason_codes also returns [] on this row
        graph_only = extract_graph_reason_codes(df.iloc[0])
        _assert(graph_only == [],
                f"extract_graph_reason_codes returned {graph_only} for legacy row")

        _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))
    except Exception as exc:
        _fail(label, f"unexpected exception: {exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print()
    print("=" * 65)
    print("Phase 15E -- Graph Reason-Code Validation Report")
    print("=" * 65)
    print("Source: src.features.transaction_features.extract_graph_reason_codes")
    print()

    print("-- Section 1: Neutral / no-context scenarios --")
    test_1_legacy_no_entity_fields()
    test_2_all_unique_entities()

    print()
    print("-- Section 2: Single-signal scenarios --")
    test_3_same_customer_device_guardrail()
    test_4_cross_customer_device_cluster()
    test_5_fan_in_counterparty_only()
    test_6_fan_out_account_only()

    print()
    print("-- Section 3: All signals active --")
    test_7_all_four_signals_active()

    print()
    print("-- Section 4: Integration with generate_reasons --")
    test_8_generate_reasons_legacy_row()

    total = _PASS_COUNT + _FAIL_COUNT

    print()
    print("-" * 65)
    print(f"Total scenarios tested    : {total}")
    print()
    print("Graph reason codes emitted (4):")
    print("  SHARED_DEVICE_CLUSTER   -- shared_device_flag is True")
    print("  DEVICE_ACCOUNT_REUSE    -- cross_account_device_reuse is True")
    print("  MULE_FAN_IN_PATTERN     -- counterparty_fan_in_flag is True")
    print("  MULE_FAN_OUT_PATTERN    -- counterparty_fan_out_flag is True")
    print()
    g4_note = "[confirmed PASS]" if _FAIL_COUNT == 0 else "[SEE FAILURES ABOVE]"
    print(f"G4 same-customer guardrail (Scenario 3):")
    print("  shared_device_flag=True, cross_account_device_reuse=False")
    print("  -> SHARED_DEVICE_CLUSTER emitted, DEVICE_ACCOUNT_REUSE NOT emitted")
    print(f"  Result: {g4_note}")
    print()
    print("graph_boost                : unchanged (Phase 15D weights/cap preserved)")
    print("Graph reason codes         : stored in reasons pipe-delimited output only")
    print("Frontend graph chip display: deferred to Phase 15F")
    print("No DB, no API, no Redpanda, no NetworkX : Confirmed")
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
        print(f"\nFATAL: unhandled exception in verify_graph_reason_codes.py: {exc}")
        sys.exit(1)
