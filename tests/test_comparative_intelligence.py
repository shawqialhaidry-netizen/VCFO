from app.services.comparative_intelligence import build_comparative_intelligence


def _bundle(rows):
    return {"expense_analysis": {"by_period": rows}}


def test_comparative_intelligence_rankings_and_pressure_are_deterministic():
    company = _bundle(
        [
            {
                "period": "2025-11",
                "revenue": 1000,
                "total_expense": 700,
                "expense_pct_of_revenue": 70.0,
                "categories": {"payroll": 200, "rent": 200, "other": 300},
            },
            {
                "period": "2025-12",
                "revenue": 1200,
                "total_expense": 720,
                "expense_pct_of_revenue": 60.0,
                "categories": {"payroll": 220, "rent": 200, "other": 300},
            },
        ]
    )

    b1 = _bundle(
        [
            {
                "period": "2025-11",
                "revenue": 500,
                "total_expense": 350,
                "expense_pct_of_revenue": 70.0,
                "categories": {"payroll": 150, "other": 200},
            },
            {
                "period": "2025-12",
                "revenue": 600,
                "total_expense": 420,
                "expense_pct_of_revenue": 70.0,
                "categories": {"payroll": 200, "other": 220},
            },
        ]
    )

    b2 = _bundle(
        [
            {
                "period": "2025-11",
                "revenue": 500,
                "total_expense": 350,
                "expense_pct_of_revenue": 70.0,
                "categories": {"rent": 200, "other": 150},
            },
            {
                "period": "2025-12",
                "revenue": 600,
                "total_expense": 300,
                "expense_pct_of_revenue": 50.0,
                "categories": {"rent": 120, "other": 180},
            },
        ]
    )

    out = build_comparative_intelligence(
        company_expense_bundle=company,
        branch_bundles=[
            {"branch_id": "b1", "branch_name": "Alpha", "expense_bundle": b1},
            {"branch_id": "b2", "branch_name": "Beta", "expense_bundle": b2},
        ],
    )

    br = out["branch_rankings"]
    assert br["highest_total_expense"]["branch_id"] == "b1"
    assert br["lowest_total_expense"]["branch_id"] == "b2"
    assert br["highest_expense_pct_of_revenue"]["branch_id"] == "b1"
    assert br["lowest_expense_pct_of_revenue"]["branch_id"] == "b2"

    cp = out["cost_pressure"]
    assert cp["driving_expense_increase_mom"]["branch_id"] == "b1"
    assert cp["most_inefficient_branch"]["branch_id"] == "b1"
    assert cp["most_efficient_branch"]["branch_id"] == "b2"
    assert cp["most_improving_branch"]["branch_id"] == "b2"

    # Contribution is against company latest period (2025-12)
    contrib = {c["branch_id"]: c for c in out["branch_vs_company"]["branch_contributions"]}
    assert contrib["b1"]["branch_contribution_pct_of_company_expense"] == 58.33  # 420/720*100
    assert contrib["b2"]["branch_contribution_pct_of_company_expense"] == 41.67  # 300/720*100

