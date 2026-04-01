# VCFO — System Architecture (Core Stabilization)

## Data Pipeline (MANDATORY ORDER)

```
normalized_tb (CSV from uploads)
    │
    ▼
financial_statements.py  ← SINGLE SOURCE OF TRUTH
    │   build_statements(df) → FinancialStatements
    │   statements_to_dict() → plain dict
    │
    │   Computes (authoritative):
    │     • net_profit          = operating_profit - tax
    │     • gross_profit        = revenue - cogs
    │     • working_capital     = current_assets - current_liabilities
    │     • current_assets      = accounts 1000-1399
    │     • current_liabilities = accounts 2000-2199
    │
    ▼
analysis_engine.py        ← READ ONLY (derives ratios, no raw calculations)
    │   run_analysis(windowed_stmts)
    │   compute_ratios(stmt)  ← reads from stmt, never recomputes values
    │   compute_trends(stmts) ← MoM/YoY from IS values in stmts
    │
    ▼
cashflow_engine.py        ← READ ONLY for NP and WC
    │   build_cashflow(windowed_stmts)
    │   OCF = net_profit(from stmt) + DA - ΔRec - ΔInv + ΔPay
    │
    ▼
decision_engine / cfo_decision_engine.py  ← READ ONLY
    │
    ▼
executive endpoint  ← Consolidates, NEVER recomputes
    /api/v1/analysis/{id}/executive
```

## Rules (Non-Negotiable)

| Rule | Detail |
|------|--------|
| **No duplicate calculations** | If a value exists in statements_to_dict() output, no other module may recompute it |
| **Working Capital** | Always bs["working_capital"] — set by financial_statements.py |
| **Net Profit** | Always is_["net_profit"] — set by financial_statements.py |
| **Ratios** | Computed in analysis_engine using stmt values, NOT raw TB data |
| **Time window** | Applied AFTER all statements are built, in the API layer |
| **Validation** | _validate_pipeline() checks consistency on every request |

## File Roles

| File | Role |
|------|------|
| financial_statements.py | **SOURCE OF TRUTH** — all IS + BS calculations |
| financial_engine.py | **INTERNAL HELPER ONLY** — not in pipeline |
| analysis_engine.py | Reads stmts → derives ratios + trends |
| cashflow_engine.py | Reads stmts → indirect method OCF |
| fin_intelligence.py | Reads analysis → health score |
| financial_ratios.py | Reads analysis["latest"] → card-ready format |
| statement_engine.py | Reads stmts + cashflow + intelligence → UI bundle |
| decision_engine.py | Reads analysis → CFO decisions |
| time_intelligence.py | Window filtering + KPI block |

## I18N

- All strings in app/i18n/{en,ar,tr}.json
- Statement insight keys: stmt_insight_* prefix
- statement_engine._t() calls app.i18n.translate() — no hardcoded text
