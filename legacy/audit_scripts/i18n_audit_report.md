# i18n audit report (whole project)

## Summary counts
- Missing keys (any locale vs union): **0**
- Placeholder mismatches (en/ar/tr): **1**
- Frontend `tr`/`strictT` keys not in en.json: **0** | Python (excl. narrative_engine-only): **18** | narrative_engine `_t` keys (not i18n): **22**
- Suspect hardcoded English strings (heuristic): **1212**
- Fallback marker occurrences: **19**

## a) Missing keys (en / ar / tr parity)

### Severe (missing in 2+ locales): **0**

### Missing in one locale only: **0**

## b) Placeholder mismatches

- `exec_act_dol_sensitivity`
  - en: ['dol']
  - ar: []
  - tr: []

## c) Source-referenced keys missing from en.json

*Static extraction only; dynamic `tr(\`k_${x}\`)` not included.*

### c.1 Frontend - likely blockers

### c.2 Python (excluding keys referenced only from narrative_engine.py)
- **`cashflow_below_profit`** (~2 refs)
  - `app\services\statement_engine.py:330`
  - `app\services\statement_engine.py:331`
- **`cross_margin_liquidity_trap`** (~1 refs)
  - `app\services\cfo_root_cause_engine.py:461`
- **`eff_ccc_long`** (~1 refs)
  - `app\services\cfo_root_cause_engine.py:387`
- **`eff_slow_inventory`** (~1 refs)
  - `app\services\cfo_root_cause_engine.py:408`
- **`growth_revenue_stall`** (~1 refs)
  - `app\services\cfo_root_cause_engine.py:440`
- **`lev_high_de`** (~1 refs)
  - `app\services\cfo_root_cause_engine.py:425`
- **`liq_cr_weak`** (~1 refs)
  - `app\services\cfo_root_cause_engine.py:313`
- **`liq_slow_collections`** (~1 refs)
  - `app\services\cfo_root_cause_engine.py:329`
- **`liq_wc_negative`** (~1 refs)
  - `app\services\cfo_root_cause_engine.py:319`
- **`low_current_ratio`** (~2 refs)
  - `app\services\statement_engine.py:343`
  - `app\services\statement_engine.py:344`
- **`low_net_margin`** (~2 refs)
  - `app\services\statement_engine.py:306`
  - `app\services\statement_engine.py:307`
- **`negative_working_capital`** (~2 refs)
  - `app\services\statement_engine.py:318`
  - `app\services\statement_engine.py:319`
- **`prof_gm_pressure`** (~1 refs)
  - `app\services\cfo_root_cause_engine.py:358`
- **`prof_nm_compression`** (~1 refs)
  - `app\services\cfo_root_cause_engine.py:350`
- **`strong_gross_margin`** (~2 refs)
  - `app\services\statement_engine.py:367`
  - `app\services\statement_engine.py:368`
- **`warn_tax_not_in_source`** (~3 refs)
  - `app\api\analysis.py:3184`
  - `app\api\analysis.py:3194`
  - `app\api\analysis.py:3210`
- **`warn_whatif_clamp_max`** (~1 refs)
  - `app\api\analysis.py:3148`
- **`warn_whatif_clamp_min`** (~1 refs)
  - `app\api\analysis.py:3153`

### c.3 narrative_engine `_t` keys (internal templates - not in app/i18n)
*Count: 22 unique keys (sample first 25)*
- `action_none`
- `fy_complete`
- `fy_partial`
- `prev_comparison_vs_window`
- `reconcile_footnote`
- `reconcile_net_profit_gap`
- `reconcile_revenue_gap`
- `risk_data_gaps`
- `risk_declining_revenue`
- `risk_low_margin`
- `risk_negative_profit`
- `risk_no_prior`
- `risk_partial_basis`
- `tk_gaps`
- `tk_margin_down`
- `tk_margin_flat`
- `tk_margin_up`
- `tk_partial_year`
- `warn_fy_has_gaps`
- `warn_fy_partial_calendar`
- `warn_ytd_missing_months`
- `ytd_no_prior`

## d) Suspect hardcoded English (heuristic)

**Likely user-visible (jsx/tsx, non-test):**
- `frontend-react\src\components\CommandCenterUnifiedSections.jsx:835` - background 0.18s ease, border-color 0.18s ease, color 0.18s ease
- `frontend-react\src\components\CommandCenterUnifiedSections.jsx:856` - background 0.18s ease, border-color 0.18s ease, color 0.18s ease
- `frontend-react\src\components\ExecutiveChartBlocks.jsx:260` - border-color 0.15s ease, background 0.15s ease
- `frontend-react\src\context\PeriodScopeContext.jsx:179` - usePeriodScope must be used inside PeriodScopeProvider
- `frontend-react\src\pages\Analysis.jsx:114` - box-shadow 0.2s ease, border-color 0.2s ease
- `frontend-react\src\pages\CfoAI.jsx:93` - You are a CFO assistant. No data loaded.
- `frontend-react\src\pages\CfoAI.jsx:421` - m your AI CFO Advisor for **${co}**.\n\nPeriod **${j.period||
- `frontend-react\src\pages\CfoAI.jsx:434` - Session expired. Please log in again.
- `frontend-react\src\pages\CfoAI.jsx:437` - AI service timed out. Please retry.
- `frontend-react\src\pages\CfoAI.jsx:438` - Connection error. Please try again.
- `frontend-react\src\pages\CommandCenter.jsx:194` - transform 0.18s ease, box-shadow 0.18s ease, opacity 0.18s ease
- `frontend-react\src\pages\CommandCenter.jsx:283` - cmd-primary-hero cmd-hero cmd-hero--accent cmd-primary-intro cmd-level-1
- `frontend-react\src\pages\CommandCenter.jsx:290` - transform 0.18s ease, box-shadow 0.18s ease
- `frontend-react\src\pages\CommandCenter.jsx:1512` - transform .15s ease,box-shadow .15s ease
- `frontend-react\src\pages\CommandCenter.jsx:1722` - transform .15s ease, box-shadow .15s ease, border-color .15s ease, color .15s ease
- `frontend-react\src\pages\CommandCenter.jsx:1765` - transform .15s ease, border-color .15s ease
- `frontend-react\src\pages\ExecutiveDashboard.jsx:545` - transform .15s ease,box-shadow .15s ease
- `frontend-react\src\pages\ExecutiveDashboard.jsx:679` - transform 0.2s cubic-bezier(0.4,0,0.2,1), box-shadow 0.2s ease, border-color 0.2s ease
- `frontend-react\src\pages\ExecutiveDashboard.jsx:796` - transform .15s ease,box-shadow .15s ease
- `frontend-react\src\pages\ExecutiveDashboard.jsx:852` - transform .15s ease,box-shadow .15s ease
- `frontend-react\src\pages\Landing.jsx:30` - Income Statement, Balance Sheet, and Cash Flow with period comparison, MoM/YoY variance, and balance status.
- `frontend-react\src\pages\Landing.jsx:42` - Prioritised action list with urgency levels, expected impact, and timeframes — no generic advice, only what your numbers...
- `frontend-react\src\pages\Landing.jsx:48` - Base / optimistic / risk scenarios for Revenue and Net Profit with confidence bands, plus interactive what-if modelling.
- `frontend-react\src\pages\Landing.jsx:53` - Main hub — health, KPIs, signals, branches, decisions; click through to detail views.
- `frontend-react\src\pages\Landing.jsx:60` - Assess whether insight → cause → action → forecast chain is relevant and actionable.
- `frontend-react\src\pages\Landing.jsx:61` - Check that CFO decisions are domain-specific, urgent, and backed by actual ratios.
- `frontend-react\src\pages\Landing.jsx:62` - Review forecast confidence levels, risk labels, and method transparency.
- `frontend-react\src\pages\Landing.jsx:63` - Evaluate ease of navigation, data clarity, and responsiveness of the interface.
- `frontend-react\src\pages\Landing.jsx:147` - VCFO transforms a trial balance into executive decisions powered by AI — no accountant required, no spreadsheets.
- `frontend-react\src\pages\Landing.jsx:219` - Register and create your company profile inside the platform.
- `frontend-react\src\pages\Landing.jsx:223` - Upload a CSV trial balance — monthly (YYYY-MM) or annual (YYYY).
- `frontend-react\src\pages\Landing.jsx:227` - Explore financial statements, ratios, decisions, and forecasts.
- `frontend-react\src\pages\Landing.jsx:231` - Use the AI CFO button (🧠) to ask natural language questions about your data.
- `frontend-react\src\pages\Landing.jsx:300` - VCFO — Virtual CFO Intelligence Platform · Expert Trial Build
- `frontend-react\src\pages\Landing.jsx:339` - Please evaluate each area below and provide your feedback. Focus on financial accuracy, AI insight quality, and usabilit...
- `frontend-react\src\pages\Landing.jsx:367` - Note: Upload your own trial balance to get real analysis. The platform works fully with any accounting data.
- `frontend-react\src\pages\Login.jsx:41` - Connection error — is the server running?
- `frontend-react\src\pages\Statements.jsx:159` - box-shadow 0.2s ease, border-color 0.2s ease
- `frontend-react\src\pages\Upload.jsx:95` - You can replace the current data with the new upload
- `frontend-react\src\pages\Upload.jsx:123` - Current data for this period will be permanently replaced. This cannot be undone.
- `frontend-react\src\pages\Upload.jsx:219` - Deletes all uploads for this period + derived branch data
- `frontend-react\src\pages\Upload.jsx:243` - All uploads for this period and derived data will be permanently deleted
- `frontend-react\src\pages\Upload.jsx:246` - This upload record and its associated file will be permanently deleted
- `frontend-react\src\pages\Upload.jsx:952` - TB balanced: total debits = total credits
- `frontend-react\src\pages\Upload.jsx:953` - TB unbalanced: total debits ≠ total credits

**Likely internal / tests / API (still English prose):**
- `app\api\analysis.py:276` - Difference: {diff}. Branch data may be incomplete.
- `app\api\analysis.py:292` - Branch balance sheets are not individually stored.
- `app\api\analysis.py:480` - Balance sheet imbalance equals net profit — this is expected for a 
- `app\api\analysis.py:480` - trial balance before period-end closing entries.
- `app\api\analysis.py:583` - CF uses NP={cf_np}, stmt NP={stmt_np}
- `app\api\analysis.py:589` - Single period — WC deltas set to zero
- `app\api\analysis.py:595` - tb_type not set on upload — NP not injected into equity
- `app\api\analysis.py:632` - net_profit = revenue - cogs - opex - tax
- `app\api\analysis.py:646` - Optional: run full pipeline on single branch
- `app\api\analysis.py:651` - YYYY   — for basis_type=year or ytd
- `app\api\analysis.py:669` - No financial data for branch {branch_id}.
- `app\api\analysis.py:676` - No financial data uploaded yet (branch consolidation). Upload Trial Balances with a branch selected first.
- `app\api\analysis.py:692` - No financial data uploaded yet. Upload a Trial Balance first.
- `app\api\analysis.py:696` - Could not build statements. Ensure normalized files exist.
- `app\api\analysis.py:962` - No financial data uploaded yet (branch consolidation). Upload Trial Balances with a branch selected first.
- `app\api\analysis.py:1150` - Balance sheet ratios are not available in consolidation mode.
- `app\api\analysis.py:1223` - Analysis window: 3M | 6M | 12M | YTD | ALL
- `app\api\analysis.py:1230` - Locale for alerts, Phase-43 narratives, decisions: en | ar | tr
- `app\api\analysis.py:1271` - No financial data uploaded yet (branch consolidation).
- `app\api\analysis.py:1285` - No financial data uploaded yet. Upload a Trial Balance first.
- `app\api\analysis.py:1903` - Map existing cfo_decision_engine output → canonical V2 decision schema.
- `app\api\analysis.py:1980` - den sektör normuna indirmek net marjı artıracak
- `app\api\analysis.py:1984` - Karlılığa dönmek kritik — şube net marjı şu an %{nm:.1f}
- `app\api\analysis.py:1985` - Returning to profitability is critical — branch net margin currently {nm:.1f}%
- `app\api\analysis.py:1988` - Güçlü marj, gelir büyümesine yatırım için alan sağlıyor
- `app\api\analysis.py:1989` - Strong margin provides room to invest in revenue growth
- `app\api\analysis.py:1992` - Mevcut seyrin korunması portföy performansını destekliyor
- `app\api\analysis.py:1993` - Sustaining current trajectory supports portfolio performance
- `app\api\analysis.py:1996` - Operasyonel iyileştirme şirketin genel performansını destekler
- `app\api\analysis.py:1997` - Operational improvement supports overall company performance
- `app\api\analysis.py:2056` - No financial data uploaded yet (branch consolidation).
- `app\api\analysis.py:2069` - No financial data uploaded yet. Upload a Trial Balance first.
- `app\api\analysis.py:2138` - Gider oranı %{er:.1f} — işletme maliyetlerini hemen gözden geçirin
- `app\api\analysis.py:2139` - Expense ratio at {er:.1f}% — review operating costs immediately
- `app\api\analysis.py:2143` - Branch in loss territory ({n_m:.1f}% net margin) — root cause analysis required
- `app\api\analysis.py:2146` - Gelir {n} ay art arda düştü — piyasa koşullarını gözden geçirin
- `app\api\analysis.py:2147` - Revenue declining {n} consecutive months — review market conditions
- `app\api\analysis.py:2150` - Net marj %{n_m:.1f}, %20 hedefinin altında — fiyatlandırmayı gözden geçirin
- `app\api\analysis.py:2151` - Net margin {n_m:.1f}% below 20% target — review pricing and cost structure
- `app\api\analysis.py:2154` - Güçlü marj (%{n_m:.1f}) ve büyüme ivmesi — kapasite genişletmeyi düşünün
- ... plus 1127 more

## e) Fallback / error markers in source

### User-facing code paths (review)
- `app\services\report_generator.py:81` `[missing:`
- `app\services\report_generator.py:82` `[invalid_lang:`
- `app\services\report_generator.py:83` `[format_error:`

### Internal realization / templates (expected)
- `app\services\causal_realize.py:5` `[missing:`
- `app\services\causal_realize.py:20` `[missing:`
- `app\services\causal_realize.py:24` `[invalid_lang:`
- `app\services\causal_realize.py:28` `[format_error:`
- `app\services\causal_realize.py:42` `[invalid_lang:`
- `app\services\causal_realize.py:43` `[missing:`
- `app\services\causal_realize.py:44` `[missing:`
- `app\services\causal_realize.py:45` `[format_error:`
- `app\services\causal_realize.py:102` `[invalid_lang:`
- `app\services\narrative_engine.py:70` `[narrative_`
- `app\services\narrative_engine.py:73` `[narrative_`
- `app\services\narrative_engine.py:77` `[narrative_`
- `app\services\narrative_engine.py:84` `[narrative_`
- `app\services\vcfo_ai_advisor.py:479` `[missing:`
- `app\services\vcfo_ai_advisor.py:480` `[invalid_lang:`
- `app\services\vcfo_ai_advisor.py:481` `[format_error:`

## Blockers vs non-blocking (audit opinion)

- **Blocker-class:** keys missing in 2+ locales; placeholder mismatches for keys used in UI; 
  frontend `tr()` references to keys absent from `en.json`; user-visible hardcoded English in `.jsx`/`.tsx`.
- **Non-blocking:** keys missing in only one locale (fix parity); Python `_t()` keys that belong to 
  `narrative_engine` templates (not `app/i18n`); markers inside `causal_realize.py` / intentional placeholders; 
  heuristic false positives in hardcoded scan.
