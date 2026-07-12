"""
Focused unit tests for workflow metrics aggregation helpers.

Tests _classify_source and _is_escalation_action, which document the same
normalization contract that the SQL CASE conditions in get_workflow_metrics()
implement. Keeping both in sync prevents future SQL changes from silently
breaking the frontend classification.
"""

import pytest

from src.db.metrics_helpers import classify_source as _classify_source
from src.db.metrics_helpers import is_escalation_action as _is_escalation_action


class TestEscalationDetection:
    def test_case_escalated_upper(self):
        assert _is_escalation_action("CASE_ESCALATED") is True

    def test_escalate_to_fraud_ops(self):
        assert _is_escalation_action("ESCALATE_TO_FRAUD_OPS") is True

    def test_case_escalated_lower(self):
        assert _is_escalation_action("case_escalated") is True

    def test_case_cleared_not_escalation(self):
        assert _is_escalation_action("CASE_CLEARED") is False

    def test_case_approved_not_escalation(self):
        assert _is_escalation_action("CASE_APPROVED") is False

    def test_stale_reminder_not_escalation(self):
        assert _is_escalation_action("STALE_CASE_REMINDER") is False

    def test_dispatch_failed_not_escalation(self):
        assert _is_escalation_action("WORKFLOW_DISPATCH_FAILED") is False


class TestSourceClassification:
    def test_inspection_dataset_utility(self):
        assert _classify_source("inspection-dataset-utility") == "inspection"

    def test_inspection_case_insensitive(self):
        assert _classify_source("INSPECTION_UTILITY") == "inspection"

    def test_n8n_source(self):
        assert _classify_source("n8n") == "automation"

    def test_automation_keyword(self):
        assert _classify_source("automation-runner") == "automation"

    def test_callback_is_automation(self):
        assert _classify_source("callback-handler") == "automation"

    def test_manual_source(self):
        assert _classify_source("manual") == "manual"

    def test_analyst_source(self):
        assert _classify_source("analyst") == "manual"

    def test_operator_source(self):
        assert _classify_source("operator") == "manual"

    def test_api_source(self):
        assert _classify_source("api") == "api"

    def test_fastapi_source(self):
        assert _classify_source("fastapi") == "api"

    def test_backend_source(self):
        assert _classify_source("backend-service") == "api"

    def test_unknown_source(self):
        assert _classify_source("something-random") == "unknown"

    def test_empty_string_is_unknown(self):
        assert _classify_source("") == "unknown"


class TestSourceDistributionConstraints:
    """Verify the classification is exhaustive and exclusive for known categories."""

    KNOWN_SOURCES = [
        ("inspection-dataset-utility", "inspection"),
        ("n8n", "automation"),
        ("manual", "manual"),
        ("analyst", "manual"),
        ("api", "api"),
        ("fastapi", "api"),
        ("callback", "automation"),
    ]

    def test_all_known_sources_classified(self):
        for source, expected in self.KNOWN_SOURCES:
            assert _classify_source(source) == expected, (
                f"Source '{source}' expected '{expected}', got '{_classify_source(source)}'"
            )

    def test_unknown_source_not_silently_dropped(self):
        result = _classify_source("mystery-origin")
        assert result == "unknown"
        assert result is not None
        assert result != ""
