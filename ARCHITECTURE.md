# VCFO — System Architecture (Core Stabilization)

## Phase 1 — Canonical product path (single truth)

**Official endpoints (product UI):**

| Concern | Source |
|--------|--------|
| Primary read model | `GET /api/v1/analysis/{company_id}/executive` |
| Forecast (same object everywhere) | `forecast_engine.build_forecast` — embedded as `data.forecast` on executive; also `GET /api/v1/analysis/{company_id}/forecast` |
| Structured statement bundle | `statement_engine.build_statement_bundle` — root `data` + nested `statements` (structured keys stripped in nest) |
| CFO decisions | `cfo_decision_engine.build_cfo_decisions` — exposed on executive as `data.decisions` |
| Surfaces on canonical path | Command Center (`/`), Statements, CfoPanel (executive payload) |

**Legacy (do not treat as product truth):**

- `GET /api/v1/analysis/{company_id}` — full historical aggregate; `run_intelligence`; flat `statements`; response includes `pipeline_profile.is_canonical_product_path: false`.
- `GET /api/v1/analysis/{company_id}/consolidated` — branch consolidation summary; also `pipeline_profile` flagged non-canonical.
- `deep_intelligence.build_executive_basic_forecast` — unused by APIs; retained for ad-hoc/tests only.

Frontend must not recompute business scoring; use server `intelligence.surface_scores` / `intel_tile_hints` from executive.

---

## Phase 2 — Financial truth lock (TB → statements → KPI)

**Canonical accounting path (company-level uploads):**

1. `app/api/uploads.py` — parse → validate → `classify_dataframe` → normalized CSV on disk  
2. `app/services/canonical_period_statements.py` — `build_period_statements_from_uploads`  
   - load CSV (`load_normalized_tb_dataframe` — requires `account_code`, `account_name`, `debit`, `credit` only)  
   - always `classify_dataframe` before `financial_statements.build_statements`  
   - `statements_to_dict` + pre-closing flags + `attach_structured_income_statement`  
3. All callers use this module: `analysis._build_period_statements`, `portfolio` intelligence, `scope_expense_intelligence`, `vcfo_advisor_context` (company path).

**Statement bundle (product):** `statement_engine.build_statement_bundle(windowed, cashflow_raw, intelligence)` — IS/BS/CF/summary/insights read only from the same `windowed` list + `build_cashflow` + `build_intelligence` (no alternate statement math).

**KPI block:** `time_intelligence.build_kpi_block` on the same windowed statements; flow = SUM over window, rates = last period; WC from BS per period.

**MetricResolver:** diagnostic / evidence only — not used to author executive headline numbers (see `metric_resolver.py` docstring).

**Integrity (GET /executive):** `analysis._validate_pipeline` → `analysis._assess_financial_integrity`.  
- **Blocking:** any validation severity `error` (NP mismatch, WC mismatch, WC formula, unbalanced BS, CF NP mismatch) → `meta.integrity.blocking=true`, governance fields cleared (decisions, root causes, deep intel, tile hints, health score, etc.); raw statements + KPIs + cashflow remain for review.  
- **Warning / info-only:** e.g. `cashflow_estimated`, `tb_type_unknown` — does not block.

---

## Phase 3 — Intelligence / decisions lock

**Canonical product intelligence:** `fin_intelligence.build_intelligence(analysis, annual_layer, currency)` on the same `windowed` statements as `GET /executive`.

**Canonical product decisions:** `cfo_decision_engine.build_cfo_decisions` with **`alerts_engine.build_alerts`** outputs (same pairing everywhere). `GET /analysis/{id}/decisions`, `GET /analysis/{id}/root-causes`, `GET /analysis/{id}/alerts`, and `GET /cfo-decisions` use `analysis._product_windowed_statements` (including `consolidate=`) so scope matches executive.

**Legacy (non-product):** `intelligence_engine.run_intelligence` — only the aggregate `GET /analysis/{id}` path.

**Secondary interpretation (do not override CFO decisions):** `deep_intelligence`, executive `profitability_intelligence`, `trend_analysis`, `financial_brain` — documented under `meta.product_intelligence` on `GET /executive`.

**Scenario ranker (advisory):** `POST /analysis/{id}/decisions` — not the primary CFO decision set.

**Thin / error paths:** `build_cfo_decisions` summary includes `insufficient_evidence` when no decision cards; `GET /cfo-decisions` pipeline errors return `summary.insufficient` + `reason_code` instead of silent empty objects.

---

## Data Pipeline (MANDATORY ORDER)

```
normalized_tb (CSV from uploads)
    │
    ▼
canonical_period_statements.build_period_statements_from_uploads  ← Phase 2 single entry (classify → build)
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
