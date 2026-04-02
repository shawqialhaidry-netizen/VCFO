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


def test_financial_brain_classifies_cost_driven_when_expense_up_revenue_flat():
    company_bundle = _bundle(
        [
            {"period": "2026-02", "revenue": 1000, "total_expense": 700, "expense_pct_of_revenue": 70.0, "categories": {"payroll": 400}},
            {"period": "2026-03", "revenue": 1000, "total_expense": 900, "expense_pct_of_revenue": 90.0, "categories": {"payroll": 600}},
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
    assert out["root_causes"]["classification"] == "cost_driven"


def test_financial_brain_what_changed_mom_aligns_with_why_links():
    company_bundle = _bundle(
        [
            {"period": "2026-02", "revenue": 1000, "total_expense": 500, "expense_pct_of_revenue": 50.0, "categories": {"other": 200}},
            {"period": "2026-03", "revenue": 1100, "total_expense": 600, "expense_pct_of_revenue": 54.55, "categories": {"other": 300}},
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
    mom = out["what_changed"]["mom"]
    links = out["why"]["links"]["expense_vs_revenue"]
    assert links["mom_expense_delta"] == mom["expense_delta"]
    assert links["mom_revenue_delta"] == mom["revenue_delta"]
    assert links["expense_ratio_delta_pp"] == mom["expense_ratio_delta_pp"]


def test_financial_brain_causal_chain_references_mom_deltas():
    company_bundle = _bundle(
        [
            {"period": "2026-02", "revenue": 1000, "total_expense": 500, "expense_pct_of_revenue": 50.0, "categories": {"payroll": 300}},
            {"period": "2026-03", "revenue": 900, "total_expense": 500, "expense_pct_of_revenue": 55.56, "categories": {"payroll": 300}},
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
    chain = " ".join(out["causal_chain"])
    assert str(out["what_changed"]["mom"]["expense_delta"]) in chain
    assert str(out["what_changed"]["mom"]["revenue_delta"]) in chain


def test_financial_brain_no_periods_returns_unavailable():
    out = build_financial_brain_company(
        company_id="c1",
        company_name="Co",
        currency="USD",
        expense_bundle=_bundle([]),
        comparative_intelligence={},
        expense_decisions_v2=[],
        anomalies=[],
        lang="en",
    )
    assert out["available"] is False
    assert out["reason"] == "no_periods"


def test_financial_brain_linked_drivers_include_decisions_and_anomalies():
    company_bundle = _bundle(
        [
            {"period": "2026-02", "revenue": 1000, "total_expense": 700, "expense_pct_of_revenue": 70.0, "categories": {"other": 300}},
            {"period": "2026-03", "revenue": 1000, "total_expense": 900, "expense_pct_of_revenue": 90.0, "categories": {"other": 500}},
        ],
        anomalies=[{"anomaly_id": "anom_x"}],
    )
    decisions = [
        {"decision_id": "dec_a", "priority": "high", "title": "Cut spend", "expected_financial_impact": {"estimated_monthly_savings": 100}},
        {"decision_id": "dec_b", "priority": "low", "title": "Later", "expected_financial_impact": {"estimated_monthly_savings": 1}},
    ]
    comparative = {
        "cost_pressure": {"most_inefficient_branch": {"branch_id": "b1", "branch_name": "Alpha", "expense_pct_of_revenue": 95.0}},
    }
    out = build_financial_brain_company(
        company_id="c1",
        company_name="Co",
        currency="USD",
        expense_bundle=company_bundle,
        comparative_intelligence=comparative,
        expense_decisions_v2=decisions,
        anomalies=company_bundle["expense_anomalies"],
        lang="en",
    )
    ld = out["linked_drivers"]
    assert "anom_x" in ld["anomaly_ids"]
    assert "dec_a" in ld["decision_ids"]
    assert ld["comparative_signals"]["most_inefficient_branch_id"] == "b1"

