"""
Investigation service — Phase 3 agentic investigation layer.

Consumes from cases.investigate, runs the investigation pipeline
(tool calls + RAG + LLM reasoning), and writes a structured
InvestigationReport to Postgres.
"""

from src.investigation.schemas import (
    InvestigationRequest,
    InvestigationReport,
    InvestigationStatus,
    Recommendation,
    Confidence,
)

__all__ = [
    "InvestigationRequest",
    "InvestigationReport",
    "InvestigationStatus",
    "Recommendation",
    "Confidence",
]
