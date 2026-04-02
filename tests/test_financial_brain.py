from app.services.financial_brain import build_financial_brain_company


def _bundle(rows, anomalies=None):
    return {
        "expense_analysis": {"by_period": rows},
        "expense_anomalies": anomalies or [],
        "expense_decisions": [],
        "expense_explanation": {},
    }


def test_financial_brain_classifies_structural_inefficiency_when_branch_ratio_high():
    company_bundle = _bundle(
        [
            {"period": "2026-02", "revenue": 1000, "total_expense": 700, "expense_pct_of_revenue": 70.0, "categories": {"other": 300}},
            {"period": "2026-03", "revenue": 1000, "total_expense": 900, "expense_pct_of_revenue": 90.0, "categories": {"other": 500}},
        ],
        anomalies=[{"anomaly_id": "a1"}],
    )
    comparative = {
        "cost_pressure": {"most_inefficient_branch": {"branch_id": "b1", "branch_name": "Alpha", "expense_pct_of_revenue": 95.0}},
        "branch_vs_company": {"branch_contributions": [{"branch_id": "b1", "branch_contribution_pct_of_company_expense": 50.0}]},
    }
    decisions_v2 = [{"decision_id": "d1", "priority": "high", "expected_financial_impact": {"estimated_monthly_savings": 0}}]

    out = build_financial_brain_company(
        company_id="c1",
        company_name="Co",
        currency="USD",
        expense_bundle=company_bundle,
        comparative_intelligence=comparative,
        expense_decisions_v2=decisions_v2,
        anomalies=company_bundle["expense_anomalies"],
        lang="en",
    )

    assert out["available"] is True
    assert out["root_causes"]["classification"] == "structural_inefficiency"
    assert "a1" in out["linked_drivers"]["anomaly_ids"]
    assert "d1" in out["linked_drivers"]["decision_ids"]
    assert out["what_changed"]["mom"]["expense_delta"] == 200.0


def test_financial_brain_classifies_revenue_driven_when_revenue_down_expense_flat():
    company_bundle = _bundle(
        [
            {"period": "2026-02", "revenue": 1000, "total_expense": 700, "expense_pct_of_revenue": 70.0, "categories": {"other": 300}},
            {"period": "2026-03", "revenue": 800, "total_expense": 700, "expense_pct_of_revenue": 87.5, "categories": {"other": 300}},
        ]
    )
    out = build_financial_brain_company(
        company_id="c1",
        company_name="Co",
        currency="USD",
        expense_bundle=company_bundle,
        comparative_intelligence={},
        expense_decisions_v2=[],
        anomalies=[],
        lang="en",
    )
    assert out["root_causes"]["classification"] == "revenue_driven"

