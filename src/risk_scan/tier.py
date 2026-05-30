"""
Portfolio risk tier assignment for batch scan results.

These thresholds intentionally provide finer granularity than the
APPROVE / REVIEW / BLOCK decision bands used in single-transaction scoring.
They are not derived from REVIEW_THRESHOLD or BLOCK_THRESHOLD.
"""


def assign_tier(risk_score: float) -> tuple[str, str]:
    """Return (risk_tier, operational_priority) for a given risk score."""
    if risk_score >= 0.80:
        return ("Critical", "P0")
    if risk_score >= 0.60:
        return ("High", "P1")
    if risk_score >= 0.30:
        return ("Medium", "P2")
    return ("Low", "P3")