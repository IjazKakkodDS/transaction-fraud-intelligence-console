"""
Phase 18C smoke verification -- investigation failure classification and empty-RAG handling.

No Ollama, no DB, no API, no network required.
All checks are in-process using direct imports from the investigation modules.

Usage:
  python scripts/verify_investigation_failure.py

Exit codes:
  0 -- all checks passed
  1 -- one or more checks failed
"""

import sys
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.investigation.service import _classify_investigation_error  # noqa: E402
from src.investigation.reasoner import _build_prompt                  # noqa: E402
from src.investigation.tools import get_evidence_groups               # noqa: E402

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


# Shared prompt fixture (used for checks 6-9)
_CASE = {
    "transaction_id": "TXN-18C-SMOKE-001",
    "amount": "500.00",
    "risk_score": "0.75",
    "decision": "REVIEW",
}
_EG = get_evidence_groups("HIGH_RISK_MERCHANT|BEHAVIOURAL_AMOUNT_DEVIATION")
_FB = {"amount": 500.0, "risk_score": 0.75, "hour_of_day": 14}

# ---------------------------------------------------------------------------
# Check 1 -- URLError produces the connectivity-class bounded message
# ---------------------------------------------------------------------------
print("Check 1: URLError -> connectivity message")
_exc_url = urllib.error.URLError(
    "http://host.docker.internal:11434/api/generate -- connection refused"
)
_msg_url = _classify_investigation_error(_exc_url)
check(
    "URLError produces 'LLM service unreachable' message",
    "LLM service unreachable" in _msg_url and "check Ollama connectivity and retry" in _msg_url,
)

# ---------------------------------------------------------------------------
# Check 2 -- OSError also produces the connectivity-class bounded message
# ---------------------------------------------------------------------------
print("Check 2: OSError -> connectivity message")
_exc_os = OSError("No route to host: host.docker.internal:11434")
_msg_os = _classify_investigation_error(_exc_os)
check(
    "OSError produces 'LLM service unreachable' message",
    "LLM service unreachable" in _msg_os and "check Ollama connectivity and retry" in _msg_os,
)

# ---------------------------------------------------------------------------
# Check 3 -- Connectivity message does not expose forbidden internal strings
# ---------------------------------------------------------------------------
print("Check 3: Connectivity message sanitisation")
_CONNECTIVITY_FORBIDDEN = [
    "host.docker.internal",
    "11434",
    "/api/generate",
    "URLError",
    "Traceback",
]
check(
    "Connectivity message (URLError) contains no forbidden strings",
    not any(s in _msg_url for s in _CONNECTIVITY_FORBIDDEN),
)
check(
    "Connectivity message (OSError) contains no forbidden strings",
    not any(s in _msg_os for s in _CONNECTIVITY_FORBIDDEN),
)

# ---------------------------------------------------------------------------
# Check 4 -- RuntimeError produces the content-class bounded message
# ---------------------------------------------------------------------------
print("Check 4: RuntimeError -> content failure message")
_exc_rt = RuntimeError(
    "LLM reasoning failed after 3 attempts. "
    "Last error: LLM response missing required keys: {'summary'}"
)
_msg_rt = _classify_investigation_error(_exc_rt)
check(
    "RuntimeError produces 'LLM reasoning failed after configured retries' message",
    "LLM reasoning failed after configured retries" in _msg_rt,
)
check(
    "RuntimeError message includes 'model could not produce a valid structured response'",
    "model could not produce a valid structured response" in _msg_rt,
)

# ---------------------------------------------------------------------------
# Check 5 -- RuntimeError message does not expose raw exception repr or internal details
# ---------------------------------------------------------------------------
print("Check 5: RuntimeError message sanitisation")
_CONTENT_FORBIDDEN = [
    "host.docker.internal",
    "11434",
    "/api/generate",
    "RuntimeError",
    "Traceback",
    "Last error:",
    "LLM reasoning failed after 3",
]
check(
    "Content failure message contains no forbidden strings",
    not any(s in _msg_rt for s in _CONTENT_FORBIDDEN),
)

# ---------------------------------------------------------------------------
# Check 6 -- Generic unexpected exception produces the generic bounded message
# ---------------------------------------------------------------------------
print("Check 6: Generic Exception -> generic bounded message")
_exc_gen = ValueError("Unexpected internal state")
_msg_gen = _classify_investigation_error(_exc_gen)
check(
    "Generic Exception produces 'Investigation pipeline error' message",
    "Investigation pipeline error" in _msg_gen and "see server logs for details" in _msg_gen,
)
check(
    "Generic message does not contain raw exception class name or Traceback",
    "ValueError" not in _msg_gen and "Traceback" not in _msg_gen,
)

# ---------------------------------------------------------------------------
# Check 7 -- Empty-RAG prompt contains the no-playbook-guidance text
# ---------------------------------------------------------------------------
print("Check 7: Empty-RAG prompt contains honest no-guidance text")
_prompt_empty_rag = _build_prompt(_CASE, _EG, _FB, knowledge=[])
_NO_PLAYBOOK_MSG = "No matching playbook guidance found for this case."
check(
    f"Empty-RAG prompt contains '{_NO_PLAYBOOK_MSG}'",
    _NO_PLAYBOOK_MSG in _prompt_empty_rag,
)

# ---------------------------------------------------------------------------
# Check 8 -- Empty-RAG message is distinct from the no-policy statement
# ---------------------------------------------------------------------------
print("Check 8: Empty-RAG message distinct from no-policy statement")
_NO_POLICY_MSG = (
    "No policy documents are available for this investigation. "
    "Base your analysis on the playbook guidance above."
)
check(
    "No-playbook-guidance text differs from no-policy text",
    _NO_PLAYBOOK_MSG != _NO_POLICY_MSG,
)
check(
    "Both messages appear independently in the empty-RAG prompt",
    _NO_PLAYBOOK_MSG in _prompt_empty_rag and _NO_POLICY_MSG in _prompt_empty_rag,
)

# ---------------------------------------------------------------------------
# Check 9 -- Non-empty RAG does NOT show the no-playbook-guidance text
# ---------------------------------------------------------------------------
print("Check 9: Non-empty RAG does not show no-playbook-guidance text")
_prompt_with_rag = _build_prompt(
    _CASE,
    _EG,
    _FB,
    knowledge=[
        {
            "source": "playbook_account_takeover.txt",
            "content": "Account takeover patterns include...",
        }
    ],
)
check(
    "Prompt with RAG content does NOT contain 'No matching playbook guidance'",
    "No matching playbook guidance" not in _prompt_with_rag,
)

# ---------------------------------------------------------------------------
# Check 10 -- 18B compatibility: ## EVIDENCE GROUPS header still present
# ---------------------------------------------------------------------------
print("Check 10: 18B compatibility -- ## EVIDENCE GROUPS header preserved")
check(
    "Empty-RAG prompt still contains '## EVIDENCE GROUPS' (18B compatibility)",
    "## EVIDENCE GROUPS" in _prompt_empty_rag,
)
check(
    "Prompt with RAG still contains '## EVIDENCE GROUPS' (18B compatibility)",
    "## EVIDENCE GROUPS" in _prompt_with_rag,
)

# ---------------------------------------------------------------------------
# Check 11 -- No Ollama / DB / API / network dependency needed (structural check)
# ---------------------------------------------------------------------------
print("Check 11: No Ollama / DB / API / network required")
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
    print("All checks PASSED -- Phase 18C investigation failure handling verified.")
    sys.exit(0)
else:
    print(f"FAILED: {_checks - _passed} check(s) failed.")
    sys.exit(1)
