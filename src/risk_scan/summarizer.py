"""
Summary computation for portfolio risk scan results.
"""

from collections import Counter


def compute_summary(all_rows: list[dict]) -> dict:
    """
    Compute portfolio-level summary from a merged list of all row dicts.

    all_rows should contain every row from the scan (VALID, INVALID, SKIPPED).
    VALID rows must include scoring fields (risk_tier, operational_priority,
    reasons, amount) as produced by scanner.score_dataframe. INVALID and
    SKIPPED rows are counted but excluded from tier/exposure/pattern aggregates.

    Returns a dict suitable for direct storage in portfolio_scans.risk_summary
    (as JSON) and for populating the portfolio_scans count columns.
    """
    total_rows = len(all_rows)
    valid_rows = sum(1 for r in all_rows if r["validation_status"] == "VALID")
    invalid_rows = sum(1 for r in all_rows if r["validation_status"] == "INVALID")
    skipped_rows = sum(1 for r in all_rows if r["validation_status"] == "SKIPPED")

    tier_counts: Counter = Counter()
    priority_counts: Counter = Counter()
    total_amount = 0.0
    critical_amount = 0.0
    high_amount = 0.0

    reason_counter: Counter = Counter()
    country_counter: Counter = Counter()
    payment_method_counter: Counter = Counter()
    merchant_category_counter: Counter = Counter()

    for row in all_rows:
        if row["validation_status"] != "VALID":
            continue

        tier = row.get("risk_tier") or "Low"
        priority = row.get("operational_priority") or "P3"
        tier_counts[tier] += 1
        priority_counts[priority] += 1

        amount = row.get("amount")
        if amount is not None:
            try:
                amt = float(amount)
                total_amount += amt
                if tier == "Critical":
                    critical_amount += amt
                elif tier == "High":
                    high_amount += amt
            except (ValueError, TypeError):
                pass

        reasons_str = row.get("reasons") or ""
        for reason in reasons_str.split("|"):
            reason = reason.strip()
            if reason:
                reason_counter[reason] += 1

        country = row.get("country")
        if country:
            country_counter[str(country)] += 1

        pm = row.get("payment_method")
        if pm:
            payment_method_counter[str(pm)] += 1

        mc = row.get("merchant_category")
        if mc and str(mc) not in ("None", ""):
            merchant_category_counter[str(mc)] += 1

    risk_summary = {
        "top_risk_patterns": [
            {"reason": r, "count": c} for r, c in reason_counter.most_common(5)
        ],
        "top_countries": [
            {"country": c, "count": n} for c, n in country_counter.most_common(5)
        ],
        "top_payment_methods": [
            {"payment_method": m, "count": n}
            for m, n in payment_method_counter.most_common(5)
        ],
        "top_merchant_categories": [
            {"merchant_category": mc, "count": n}
            for mc, n in merchant_category_counter.most_common(5)
        ],
    }

    return {
        "total_rows": total_rows,
        "valid_rows": valid_rows,
        "invalid_rows": invalid_rows,
        "skipped_rows": skipped_rows,
        "low_count": tier_counts["Low"],
        "medium_count": tier_counts["Medium"],
        "high_count": tier_counts["High"],
        "critical_count": tier_counts["Critical"],
        "p0_count": priority_counts["P0"],
        "p1_count": priority_counts["P1"],
        "p2_count": priority_counts["P2"],
        "p3_count": priority_counts["P3"],
        "total_amount": round(total_amount, 4),
        "critical_amount": round(critical_amount, 4),
        "high_amount": round(high_amount, 4),
        "risk_summary": risk_summary,
    }