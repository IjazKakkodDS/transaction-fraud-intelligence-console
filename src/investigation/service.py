"""
Investigation service orchestrator — Phase 3.

process_case() is the single entry point called by the Kafka consumer.
It coordinates the full investigation pipeline:
  1. Base-case fetch  — load the predictions row from Postgres using case_id
  2. Tool calls       — get_rule_explanations and get_feature_breakdown produce
                        deterministic findings from the case data
  3. RAG              — build_query + retrieve_knowledge fetch the most relevant
                        fraud playbooks and SOPs from the local TF-IDF vector store
  4. LLM reasoning    — generate_summary calls a local Ollama instance with the
                        assembled evidence and returns a structured JSON report;
                        enum constraints on recommendation and confidence are
                        validated with up to 2 retries on parse failure
  5. Persistence      — the caller (consumer) writes the returned InvestigationReport
                        to the investigations table via log_investigation()

On LLM failure (all retries exhausted or API error) a FAILED InvestigationReport
is returned with deterministic fields preserved so the analyst has partial context.
"""

import logging

from src.db.postgres_logger import get_prediction_by_id
from src.investigation.schemas import (
    InvestigationReport,
    InvestigationRequest,
    InvestigationStatus,
)
from src.investigation.reasoner import generate_summary
from src.investigation.retriever import (
    build_query,
    retrieve_knowledge,
)
from src.investigation.tools import (
    get_evidence_groups,
    get_feature_breakdown,
    get_rule_explanations,
)

logger = logging.getLogger("investigation-service")

# Increment this whenever a change affects the meaning of report output
# (prompt revision, tool change, model version change).
AGENT_VERSION = "0.2.0"


def process_case(request: InvestigationRequest) -> InvestigationReport:
    """
    Run the full investigation pipeline for a single case and return a
    structured InvestigationReport.

    Returns a FAILED report immediately if the case_id does not exist in
    Postgres. On LLM failure, returns a FAILED report with deterministic
    fields (rules_triggered, feature_breakdown, playbooks_referenced)
    preserved so the analyst retains partial context.
    """
    logger.info(
        "Investigation started | investigation_id=%s case_id=%d",
        request.investigation_id,
        request.case_id,
    )

    # -------------------------------------------------------------------------
    # Step 1 — Fetch base case from Postgres
    # -------------------------------------------------------------------------
    case = get_prediction_by_id(request.case_id)

    if case is None:
        logger.error(
            "Base case not found | investigation_id=%s case_id=%d"
            " — no predictions row exists for this id",
            request.investigation_id,
            request.case_id,
        )
        return InvestigationReport(
            investigation_id=request.investigation_id,
            case_id=request.case_id,
            agent_version=AGENT_VERSION,
            status=InvestigationStatus.FAILED,
            error_message=f"case_id={request.case_id} not found in predictions table",
        )

    logger.info(
        "Base case loaded | investigation_id=%s case_id=%d"
        " transaction_id=%s amount=%s risk_score=%s decision=%s",
        request.investigation_id,
        request.case_id,
        case.get("transaction_id"),
        case.get("amount"),
        case.get("risk_score"),
        case.get("decision"),
    )

    # -------------------------------------------------------------------------
    # Step 2 — Gather evidence (deterministic tools)
    # -------------------------------------------------------------------------
    rule_explanations = get_rule_explanations(
        case.get("rule_flag"),
        case.get("reasons", "").split("|"),
    )

    feature_breakdown = get_feature_breakdown(case)
    evidence_groups = get_evidence_groups(case.get("reasons", ""))

    logger.info(
        "gather_evidence | investigation_id=%s rules_triggered=%d "
        "evidence_groups=%s feature_keys=%s",
        request.investigation_id,
        len(rule_explanations),
        {k: len(v) for k, v in evidence_groups.items() if v},
        list(feature_breakdown.keys()),
    )

    # -------------------------------------------------------------------------
    # Step 3 — Retrieve knowledge (RAG)
    # -------------------------------------------------------------------------
    query = build_query(case, rule_explanations, feature_breakdown)
    knowledge = retrieve_knowledge(query)
    playbooks_referenced = [doc["source"] for doc in knowledge]

    logger.info(
        "retrieval | investigation_id=%s docs=%d",
        request.investigation_id,
        len(knowledge),
    )

    # -------------------------------------------------------------------------
    # Step 4 — LLM reasoning
    # -------------------------------------------------------------------------
    try:
        reasoning = generate_summary(
            case=case,
            evidence_groups=evidence_groups,
            feature_breakdown=feature_breakdown,
            knowledge=knowledge,
        )
    except Exception as exc:
        logger.error(
            "reasoning failed | investigation_id=%s error=%s",
            request.investigation_id,
            exc,
        )
        return InvestigationReport(
            investigation_id=request.investigation_id,
            case_id=request.case_id,
            agent_version=AGENT_VERSION,
            status=InvestigationStatus.FAILED,
            rules_triggered=rule_explanations,
            feature_breakdown=feature_breakdown,
            playbooks_referenced=playbooks_referenced,
            error_message=str(exc),
        )

    logger.info(
        "reasoning | investigation_id=%s recommendation=%s confidence=%s",
        request.investigation_id,
        reasoning["recommendation"],
        reasoning["confidence"],
    )

    # -------------------------------------------------------------------------
    # Report — all fields populated.
    # -------------------------------------------------------------------------
    report = InvestigationReport(
        investigation_id=request.investigation_id,
        case_id=request.case_id,
        agent_version=AGENT_VERSION,
        status=InvestigationStatus.COMPLETE,
        rules_triggered=rule_explanations,
        feature_breakdown=feature_breakdown,
        playbooks_referenced=playbooks_referenced,
        summary=reasoning["summary"],
        risk_factors=reasoning["risk_factors"],
        mitigating_factors=reasoning["mitigating_factors"],
        recommendation=reasoning["recommendation"],
        recommendation_rationale=reasoning["recommendation_rationale"],
        confidence=reasoning["confidence"],
        confidence_rationale=reasoning["confidence_rationale"],
    )

    logger.info(
        "Investigation complete | investigation_id=%s case_id=%d status=%s",
        report.investigation_id,
        report.case_id,
        report.status,
    )

    return report
