"""
Pure helper functions for workflow metrics aggregation.

These functions document the same normalization contract that the SQL CASE
conditions in get_workflow_metrics() implement. Unit tests import from here
directly so they can run without a database connection.
"""


def is_escalation_action(workflow_action: str) -> bool:
    """Return True if the action represents an escalation event (case-insensitive)."""
    return "escalat" in workflow_action.lower()


def classify_source(source: str) -> str:
    """Map a raw workflow event source string to a canonical category.

    Matches the SQL CASE conditions used in get_workflow_metrics(). Update
    both together if the classification logic changes.

    Categories:
      automation  -- n8n, automation, callback origins
      api         -- API, backend, service, fastapi origins
      manual      -- manual, analyst, operator origins
      inspection  -- inspection-dataset-utility and similar
      unknown     -- anything else
    """
    lower = source.lower()
    if any(k in lower for k in ("n8n", "automation", "callback")):
        return "automation"
    if any(k in lower for k in ("api", "backend", "service", "fastapi")):
        return "api"
    if any(k in lower for k in ("manual", "analyst", "operator")):
        return "manual"
    if "inspection" in lower:
        return "inspection"
    return "unknown"
