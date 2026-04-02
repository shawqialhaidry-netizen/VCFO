from app.services.expense_decisions_upgrade import (
    build_branch_expense_decisions_v2,
    build_company_expense_decisions_v2,
)


def _bundle(rows, anomalies=None):
    return {
        "expense_analysis": {"by_period": rows},
        "expense_anomalies": anomalies or [],
        "expense_decisions": [],
        "expense_explanation": {},
    }


def test_branch_decisions_emit_without_anomalies_when_pressure_strong():
    branch = _bundle(
        [
            {"period": "2026-02", "revenue": 1000, "total_expense": 700, "expense_pct_of_revenue": 70.0, "categories": {"other": 300}},
            {"period": "2026-03", "revenue": 1000, "total_expense": 900, "expense_pct_of_revenue": 90.0, "categories": {"other": 500}},
        ],
        anomalies=[],
    )

    comp = {
        "branch_vs_company": {"branch_contributions": [{"branch_id": "b1", "branch_contribution_pct_of_company_expense": 55.0}]},
        "efficiency_ranking": {"by_expense_pct_of_revenue_desc": [{"branch_id": "b1"}]},
        "category_comparison": {"all_distribution_distances": [{"branch_id": "b1", "distribution_distance_l1": 0.5}]},
    }

    out = build_branch_expense_decisions_v2(
        branch_id="b1",
        branch_name="Alpha",
        company_id="c1",
        company_name="Co",
        currency="USD",
        branch_bundle=branch,
        comparative_intelligence=comp,
        lang="en",
    )

    assert out, "should emit decisions even when anomalies are empty"
    d = out[0]
    assert d["title"]
    assert d["rationale"]
    assert d["action"]["steps"] and all(isinstance(x, str) and x.strip() for x in d["action"]["steps"])
    assert d["expected_financial_impact"]["estimated_monthly_savings"] >= 0
    assert "branch_contribution_pct_of_company_expense" in d["linked_drivers"]["metrics"]


def test_company_decisions_can_emit_from_comparative_signals():
    company = _bundle(
        [
            {"period": "2026-02", "revenue": 2000, "total_expense": 1400, "expense_pct_of_revenue": 70.0, "categories": {"other": 600}},
            {"period": "2026-03", "revenue": 2000, "total_expense": 1700, "expense_pct_of_revenue": 85.0, "categories": {"other": 800}},
        ],
        anomalies=[],
    )
    comparative = {
        "cost_pressure": {"driving_expense_increase_mom": {"branch_id": "b2", "branch_name": "Beta", "expense_pct_of_revenue": 95.0}},
        "branch_vs_company": {"branch_contributions": [{"branch_id": "b2", "branch_contribution_pct_of_company_expense": 45.0}]},
        "category_comparison": {"most_abnormal_category_distribution": {"branch_id": "b2", "distribution_distance_l1": 0.7}},
    }

    out = build_company_expense_decisions_v2(
        company_id="c1",
        company_name="Co",
        currency="USD",
        company_bundle=company,
        comparative_intelligence=comparative,
        lang="en",
    )
    assert out, "should emit company decisions"
    assert any("Contain cost pressure" in d["title"] for d in out)
    assert any(d["expected_financial_impact"]["estimated_monthly_savings"] >= 0 for d in out)

