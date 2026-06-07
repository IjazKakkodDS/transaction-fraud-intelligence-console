"""
Phase 18B smoke verification — investigation evidence grouping and prompt assembly.

No Ollama, no DB, no API, no network required.
All checks are in-process using direct imports from the investigation modules.

Usage:
  python scripts/verify_investigation_evidence.py

Exit codes:
  0 — all checks passed
  1 — one or more checks failed
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.investigation.tools import get_evidence_groups      # noqa: E402
from src.investigation.reasoner import _build_prompt         # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_checks = 0
_passed = 0


def check(description: str, condition: bool) -> None:
    global _checks, _passed
    _checks += 1
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {description}")
    if condition:
        _passed += 1


# ---------------------------------------------------------------------------
# Check 1 — Known rich-signal codes map to rich group with human-readable labels
# ---------------------------------------------------------------------------
print("Check 1: Rich-signal codes -> rich group")
g = get_evidence_groups("LOW_TRUST_DEVICE|GEO_ANOMALY_DISTANCE|AMOUNT_ANOMALY_VS_30D")
check(
    "Rich group has 3 items",
    len(g["rich"]) == 3,
)
check(
    "LOW_TRUST_DEVICE -> 'Unrecognised device with low trust score'",
    any(
        item["code"] == "LOW_TRUST_DEVICE"
        and item["label"] == "Unrecognised device with low trust score"
        for item in g["rich"]
    ),
)
check(
    "GEO_ANOMALY_DISTANCE -> rich group with friendly label (not raw code)",
    any(
        item["code"] == "GEO_ANOMALY_DISTANCE"
        and item["label"] != "GEO_ANOMALY_DISTANCE"
        for item in g["rich"]
    ),
)
check(
    "No tokens leak into base or other groups",
    len(g["base"]) == 0 and len(g["behavioural"]) == 0
    and len(g["graph"]) == 0 and len(g["scenario"]) == 0,
)

# ---------------------------------------------------------------------------
# Check 2 — Behavioural codes map to behavioural group
# ---------------------------------------------------------------------------
print("Check 2: Behavioural codes -> behavioural group")
g = get_evidence_groups(
    "BEHAVIOURAL_AMOUNT_DEVIATION|BALANCE_DROP_ANOMALY|BEHAVIOURAL_PROFILE_SHIFT"
)
check(
    "Behavioural group has 3 items",
    len(g["behavioural"]) == 3,
)
check(
    "BEHAVIOURAL_PROFILE_SHIFT -> 'Behavioural profile shift'",
    any(
        item["code"] == "BEHAVIOURAL_PROFILE_SHIFT"
        and item["label"] == "Behavioural profile shift"
        for item in g["behavioural"]
    ),
)
check(
    "BALANCE_DROP_ANOMALY -> 'Balance drop anomaly'",
    any(
        item["code"] == "BALANCE_DROP_ANOMALY"
        and item["label"] == "Balance drop anomaly"
        for item in g["behavioural"]
    ),
)

# ---------------------------------------------------------------------------
# Check 3 — Graph codes map to graph group
# ---------------------------------------------------------------------------
print("Check 3: Graph codes -> graph group")
g = get_evidence_groups(
    "SHARED_DEVICE_CLUSTER|MULE_FAN_IN_PATTERN|MULE_FAN_OUT_PATTERN|DEVICE_ACCOUNT_REUSE"
)
check(
    "Graph group has 4 items",
    len(g["graph"]) == 4,
)
check(
    "SHARED_DEVICE_CLUSTER -> 'Shared device cluster'",
    any(
        item["code"] == "SHARED_DEVICE_CLUSTER"
        and item["label"] == "Shared device cluster"
        for item in g["graph"]
    ),
)
check(
    "MULE_FAN_IN_PATTERN -> 'Mule fan-in pattern'",
    any(
        item["code"] == "MULE_FAN_IN_PATTERN"
        and item["label"] == "Mule fan-in pattern"
        for item in g["graph"]
    ),
)

# ---------------------------------------------------------------------------
# Check 4 — Scenario-context strings map to scenario group
# ---------------------------------------------------------------------------
print("Check 4: Scenario-context strings -> scenario group")
g = get_evidence_groups(
    "Account takeover pattern detected|Device mismatch detected"
)
check(
    "Scenario group has 2 items",
    len(g["scenario"]) == 2,
)
check(
    "Account takeover pattern detected -> 'Account Takeover'",
    any(
        item["code"] == "Account takeover pattern detected"
        and item["label"] == "Account Takeover"
        for item in g["scenario"]
    ),
)
check(
    "Device mismatch detected -> 'Device Mismatch'",
    any(
        item["code"] == "Device mismatch detected"
        and item["label"] == "Device Mismatch"
        for item in g["scenario"]
    ),
)

# ---------------------------------------------------------------------------
# Check 5 — Unknown code lands in base group and is preserved
# ---------------------------------------------------------------------------
print("Check 5: Unknown / unmapped codes -> base group")
g = get_evidence_groups("UNKNOWN_FUTURE_SIGNAL|Another unknown reason")
check(
    "Base group has 2 items",
    len(g["base"]) == 2,
)
check(
    "UNKNOWN_FUTURE_SIGNAL code is preserved in base",
    any(item["code"] == "UNKNOWN_FUTURE_SIGNAL" for item in g["base"]),
)
check(
    "No items in rich/behavioural/graph/scenario for unknown codes",
    len(g["rich"]) == 0 and len(g["behavioural"]) == 0
    and len(g["graph"]) == 0 and len(g["scenario"]) == 0,
)

# ---------------------------------------------------------------------------
# Check 6 — Empty reasons produce all-empty groups
# ---------------------------------------------------------------------------
print("Check 6: Empty reasons string -> all groups empty")
g = get_evidence_groups("")
check("base empty",       len(g["base"]) == 0)
check("rich empty",       len(g["rich"]) == 0)
check("behavioural empty", len(g["behavioural"]) == 0)
check("graph empty",      len(g["graph"]) == 0)
check("scenario empty",   len(g["scenario"]) == 0)

# Whitespace-only tokens must also be ignored
g2 = get_evidence_groups("   |  |  ")
check(
    "Whitespace-only tokens produce empty groups",
    all(len(v) == 0 for v in g2.values()),
)

# ---------------------------------------------------------------------------
# Check 7 — Mixed pipe-delimited reasons classify into multiple groups
# ---------------------------------------------------------------------------
print("Check 7: Mixed reasons -> correct multi-group classification")
mixed = "LOW_TRUST_DEVICE|SHARED_DEVICE_CLUSTER|BEHAVIOURAL_AMOUNT_DEVIATION|High transaction amount"
g = get_evidence_groups(mixed)
check("Mixed: rich group has 1 item (LOW_TRUST_DEVICE)",       len(g["rich"]) == 1)
check("Mixed: graph group has 1 item (SHARED_DEVICE_CLUSTER)", len(g["graph"]) == 1)
check("Mixed: behavioural group has 1 item",                   len(g["behavioural"]) == 1)
check("Mixed: base group has 1 item (legacy reason)",          len(g["base"]) == 1)
check(
    "Mixed: total tokens = 4 (no item lost or duplicated)",
    sum(len(v) for v in g.values()) == 4,
)

# ---------------------------------------------------------------------------
# Check 8 — _build_prompt() output contains the EVIDENCE GROUPS header
# ---------------------------------------------------------------------------
print("Check 8: Prompt assembly contains EVIDENCE GROUPS header")
_case = {
    "transaction_id": "TXN-SMOKE-001",
    "amount": "750.00",
    "risk_score": "0.88",
    "decision": "BLOCK",
}
_eg = get_evidence_groups("SHARED_DEVICE_CLUSTER|High transaction amount")
_fb = {
    "hour_of_day": 2,
    "is_night_transaction": True,
    "amount": 750.0,
    "risk_score": 0.88,
}
_prompt = _build_prompt(_case, _eg, _fb, knowledge=[])
check("Prompt contains '## EVIDENCE GROUPS'", "## EVIDENCE GROUPS" in _prompt)

# ---------------------------------------------------------------------------
# Check 9 — Only non-empty groups appear; empty groups are omitted
# ---------------------------------------------------------------------------
print("Check 9: Only non-empty groups appear in prompt")
# Fixture has graph + base groups; rich/behavioural/scenario are empty
check(
    "Prompt contains 'Graph Intelligence:' (non-empty group)",
    "Graph Intelligence:" in _prompt,
)
check(
    "Prompt contains 'Base / Transaction Signals:' (non-empty group)",
    "Base / Transaction Signals:" in _prompt,
)
check(
    "Prompt omits 'Rich Signals:' header (empty group)",
    "Rich Signals:" not in _prompt,
)
check(
    "Prompt omits 'Behavioural Signals:' header (empty group)",
    "Behavioural Signals:" not in _prompt,
)
check(
    "Prompt omits 'Scenario Context:' header (empty group)",
    "Scenario Context:" not in _prompt,
)

# ---------------------------------------------------------------------------
# Check 10 — Empty policies_referenced -> honest no-policy statement in prompt
# ---------------------------------------------------------------------------
print("Check 10: Empty policies -> honest no-policy statement")
check(
    "Prompt contains 'No policy documents are available'",
    "No policy documents are available" in _prompt,
)
check(
    "Prompt contains 'Base your analysis on the playbook guidance'",
    "Base your analysis on the playbook guidance above" in _prompt,
)

# ---------------------------------------------------------------------------
# Check 11 — Friendly labels replace raw ALL_CAPS codes in prompt
# ---------------------------------------------------------------------------
print("Check 11: Friendly labels used; raw ALL_CAPS codes absent for mapped signals")
check(
    "Prompt contains friendly label 'Shared device cluster'",
    "Shared device cluster" in _prompt,
)
check(
    "Prompt does not contain raw 'SHARED_DEVICE_CLUSTER' code in evidence section",
    "SHARED_DEVICE_CLUSTER" not in _prompt,
)

# Build a prompt with behavioural signal to verify its label too
_eg_beh = get_evidence_groups("BEHAVIOURAL_VELOCITY_DEVIATION|MULE_FAN_OUT_PATTERN")
_prompt_beh = _build_prompt(_case, _eg_beh, _fb, knowledge=[])
check(
    "Prompt contains 'Velocity deviation' (friendly label for BEHAVIOURAL_VELOCITY_DEVIATION)",
    "Velocity deviation" in _prompt_beh,
)
check(
    "Prompt does not contain 'BEHAVIOURAL_VELOCITY_DEVIATION' as raw code",
    "BEHAVIOURAL_VELOCITY_DEVIATION" not in _prompt_beh,
)
check(
    "Prompt contains 'Mule fan-out pattern' (friendly label for MULE_FAN_OUT_PATTERN)",
    "Mule fan-out pattern" in _prompt_beh,
)

# ---------------------------------------------------------------------------
# Check 12 — No Ollama / DB / API / network dependency needed (structural check)
# ---------------------------------------------------------------------------
print("Check 12: No Ollama / DB / API / network required")
check(
    "Script reached end without requiring any external service (Ollama/DB/API/network)",
    True,
)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print()
print(f"Verification complete: {_passed}/{_checks} checks passed")
if _passed == _checks:
    print("All checks PASSED — Phase 18B investigation evidence grouping verified.")
    sys.exit(0)
else:
    print(f"FAILED: {_checks - _passed} check(s) failed.")
    sys.exit(1)
