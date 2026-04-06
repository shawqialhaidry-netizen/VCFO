"""
vcfo_advisor_context.py — VCFO Full Context Engine

Assembles the complete financial context for the AI CFO Advisor.
Reads from existing engines ONLY — no recalculation.

Returns a single structured context dict covering all VCFO screens:
  dashboard, statements, analysis, executive, forecast, branches,
  board_report, validation.
"""
from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _safe(fn, default=None):
    try:
        return fn()
    except Exception as e:
        logger.warning("vcfo_advisor_context: %s", e)
        return default


def build_advisor_context(
    company_id:   str,
    db,
    window:       str  = "ALL",
    scope:        str  = "company",     # "company" | "consolidated"
    branch_id:    Optional[str] = None,
    lang:         str  = "en",
) -> dict:
    """
    Build the complete AI CFO context for one company.

    Reuses existing analysis pipeline — no recalculation.
    All values come from statement_engine → analysis_engine → executive.
    """
    from app.models.company            import Company
    from app.models.trial_balance      import TrialBalanceUpload
    from app.services.canonical_period_statements import build_period_statements_from_uploads
    from app.services.analysis_engine      import run_analysis
    from app.services.cashflow_engine      import build_cashflow
    from app.services.reconciliation_engine import build_validation_block

    def _r2(v): return round(float(v or 0), 2)

    # ── Company metadata ──────────────────────────────────────────────────────
    company = db.query(Company).filter(Company.id == company_id, Company.is_active == True).first()
    if not company:
        return {"error": "Company not found", "company_id": company_id}

    company_ctx = {
        "id":       company.id,
        "name":     company.name,
        "name_ar":  company.name_ar,
        "currency": company.currency or "USD",
    }

    # ── Load statements ───────────────────────────────────────────────────────
    uploads = (
        db.query(TrialBalanceUpload)
        .filter(
            TrialBalanceUpload.company_id == company_id,
            TrialBalanceUpload.status == "ok",
            TrialBalanceUpload.branch_id.is_(None),
        )
        .order_by(TrialBalanceUpload.uploaded_at.asc())
        .all()
    )

    all_stmts: list[dict] = []
    tb_debit = tb_credit = None

    if uploads:
        all_stmts = build_period_statements_from_uploads(company_id, uploads)
        tb_debit  = float(uploads[-1].total_debit  or 0)
        tb_credit = float(uploads[-1].total_credit or 0)

    # Apply window filter
    if all_stmts:
        from app.services.time_intelligence import filter_periods
        _safe_window = window.upper() if window.upper() in ("3M","6M","12M","YTD","ALL") else "ALL"
        _raw = window.upper()
        windowed = filter_periods(all_stmts, _safe_window) or all_stmts
        agg_stmts = [windowed[-1]] if _raw == "1M" else windowed
    else:
        windowed = agg_stmts = []

    # ── Analysis ──────────────────────────────────────────────────────────────
    analysis = _safe(lambda: run_analysis(windowed), {}) if windowed else {}
    latest   = analysis.get("latest", {})
    prof     = latest.get("profitability", {})
    liq      = latest.get("liquidity", {})
    eff      = latest.get("efficiency", {})

    # ── Latest IS/BS snapshots ────────────────────────────────────────────────
    latest_stmt = windowed[-1] if windowed else {}
    is_         = latest_stmt.get("income_statement", {})
    bs          = latest_stmt.get("balance_sheet", {})
    period      = latest_stmt.get("period", "")

    rev  = is_.get("revenue",      {}).get("total", 0) or 0
    np_  = is_.get("net_profit",   0) or 0
    cogs = is_.get("cogs",         {}).get("total", 0) or 0
    exp  = is_.get("expenses",     {}).get("total", 0) or 0
    gp   = is_.get("gross_profit", 0) or 0
    gm   = is_.get("gross_margin_pct")
    nm   = is_.get("net_margin_pct")
    om   = is_.get("operating_margin_pct")
    er   = round((exp + cogs) / rev * 100, 2) if rev else None

    # Windowed totals (sum across periods)
    w_rev = sum(s.get("income_statement",{}).get("revenue",{}).get("total",0) or 0 for s in agg_stmts)
    w_np  = sum(s.get("income_statement",{}).get("net_profit",0) or 0 for s in agg_stmts)

    trends  = analysis.get("trends", {})
    periods = analysis.get("periods", [])

    def _lv(series):
        return next((v for v in reversed(series or []) if v is not None), None)

    rev_mom  = _lv(trends.get("revenue",     {}).get("mom_pct", []))
    np_mom   = _lv(trends.get("net_profit",  {}).get("mom_pct", []))
    rev_dir  = trends.get("revenue",    {}).get("direction", "unknown")
    np_dir   = trends.get("net_profit", {}).get("direction", "unknown")

    # ── Cashflow ──────────────────────────────────────────────────────────────
    cashflow_ctx = {}
    if windowed:
        cf = _safe(lambda: build_cashflow(windowed), {})
        cashflow_ctx = {
            "operating_cashflow":  cf.get("operating_cashflow"),
            "free_cashflow":       cf.get("free_cashflow"),
            "cash_balance":        cf.get("cash_balance"),
            "working_capital":     bs.get("working_capital"),
            "formula":             cf.get("debug", {}).get("formula"),
        }

    # ── Validation block ──────────────────────────────────────────────────────
    validation_ctx = _safe(
        lambda: build_validation_block(windowed, tb_debit, tb_credit),
        {"status": "UNKNOWN", "warnings": [], "errors": []}
    ) if windowed else {"status": "NO_DATA"}

    # ── Canonical CFO decisions (same engine as GET /executive) ────────────────
    _lang_ai = lang if lang in ("en", "ar", "tr") else lang
    _lang_cfo = _lang_ai if _lang_ai in ("en", "ar", "tr") else "en"

    dec_pack: dict = {}

    if windowed and analysis:
        def _pack_cfo_domain():
            from app.api.analysis import _branch_context_for_cfo_decisions
            from app.services.period_aggregation import build_annual_layer
            from app.services.fin_intelligence import build_intelligence
            from app.services.alerts_engine import build_alerts
            from app.services.cfo_decision_engine import build_cfo_decisions

            annual = build_annual_layer(windowed)
            intel = build_intelligence(analysis, annual, company.currency or "")
            alerts = build_alerts(intel, lang=_lang_cfo).get("alerts", [])
            branch_ctx_dec = _branch_context_for_cfo_decisions(db, company_id)
            return build_cfo_decisions(
                intel,
                alerts,
                lang=_lang_cfo,
                n_periods=len(periods) if periods else 3,
                analysis=analysis,
                branch_context=branch_ctx_dec,
            )

        dec_pack = _safe(_pack_cfo_domain, {}) or {}

    # Legacy AI-CFO heuristic pack (isolated — not merged into primary causal/decisions)
    from app.services.ai_cfo_engine import build_company_decision
    from app.services.causal_realize import realize_causal_items

    snapshot = {"revenue": w_rev, "net_profit": w_np, "net_margin_pct": nm, "expense_ratio": er}
    legacy_ai_cfo_decision = _safe(
        lambda: build_company_decision(company.name, analysis, snapshot, period),
        {"decisions": [], "causal_items": [], "risk_score": 50, "priority": "UNKNOWN"},
    ) if analysis else {"decisions": [], "causal_items": [], "risk_score": 50, "priority": "UNKNOWN"}

    # Same merge path as executive realized causal (no deep_intel / profit_intel here)
    from app.api.analysis import _merge_causal_sources_for_realize

    merged_causal_templates = _merge_causal_sources_for_realize(dec_pack or None, None, None)
    realized_causal_advisor = realize_causal_items(merged_causal_templates, _lang_cfo)

    _raw_cfo_causal = (dec_pack or {}).get("causal_items") or []
    _realized_cfo_only = realize_causal_items(_raw_cfo_causal, _lang_cfo)
    decisions_for_ctx: list[dict] = []
    for i, dec in enumerate((dec_pack or {}).get("decisions") or []):
        row = dict(dec)
        if i < len(_realized_cfo_only):
            r = _realized_cfo_only[i]
            row["causal_realized"] = {
                "id": r.get("id"),
                "change_text": r.get("change_text") or "",
                "cause_text": r.get("cause_text") or "",
                "action_text": r.get("action_text") or "",
            }
        decisions_for_ctx.append(row)

    def _urgency_to_priority(u: str | None) -> str:
        ul = (u or "low").lower()
        if ul == "high":
            return "HIGH"
        if ul == "medium":
            return "MEDIUM"
        return "LOW"

    _first = decisions_for_ctx[0] if decisions_for_ctx else {}
    _hs = ((dec_pack or {}).get("summary") or {}).get("health_score")
    if _hs is None:
        _hs = 50

    cfo_decisions_ctx = {
        "decisions": decisions_for_ctx,
        "causal_items": merged_causal_templates,
        "recommendations": (dec_pack or {}).get("recommendations") or [],
        "decisions_summary": (dec_pack or {}).get("summary") or {},
        "domain_scores": (dec_pack or {}).get("domain_scores") or {},
        "risk_score": int(_hs) if isinstance(_hs, (int, float)) else 50,
        "priority": _urgency_to_priority(_first.get("urgency")),
    }

    # ── Branch context ────────────────────────────────────────────────────────
    branch_ctx: dict = {}
    try:
        from app.api import branches as _branches_api
        from app.models.branch import Branch

        branches_active = (
            db.query(Branch)
            .filter(Branch.company_id == company_id, Branch.is_active == True)
            .all()
        )
        branch_summaries = []
        for b in branches_active:
            stmts_b = _branches_api._branch_statements_from_uploads(db, company_id, b.id)
            if not stmts_b:
                continue
            last = stmts_b[-1]
            is_ = last.get("income_statement") or {}
            b_rev = float((is_.get("revenue") or {}).get("total") or 0)
            npv = is_.get("net_profit")
            b_np = float(npv) if npv is not None else 0.0
            b_nm = is_.get("net_margin_pct")
            if b_nm is None and b_rev:
                b_nm = round(b_np / b_rev * 100, 2)
            branch_summaries.append({
                "branch_id":   b.id,
                "branch_name": b.name,
                "period":      last.get("period"),
                "revenue":     b_rev,
                "net_profit":  b_np,
                "net_margin":  b_nm,
                "is_loss":     b_np < 0,
            })
        # Sort by revenue desc
        branch_summaries.sort(key=lambda x: -(x["revenue"] or 0))
        branch_ctx = {
            "branch_count": len(branch_summaries),
            "branches":     branch_summaries,
            "strongest":    branch_summaries[0]["branch_name"]  if branch_summaries else None,
            "weakest":      next((b["branch_name"] for b in reversed(branch_summaries)
                                  if b["is_loss"]), branch_summaries[-1]["branch_name"]
                                 if branch_summaries else None),
        }
    except Exception as e:
        logger.warning("branch context: %s", e)

    _br0 = (cfo_decisions_ctx.get("decisions") or [{}])[0]
    _board_top_action = _br0.get("title") or _br0.get("domain") or "OPTIMIZE"

    # ── Assemble full context ─────────────────────────────────────────────────
    return {
        "company":  company_ctx,
        "window":   window,
        "scope":    scope,
        "branch":   {"id": branch_id} if branch_id else {},
        "period":   period,
        "periods":  periods,

        "dashboard": {
            "revenue":            round(w_rev, 0),
            "net_profit":         round(w_np, 0),
            "revenue_latest":     round(rev, 0),
            "np_latest":          round(np_, 0),
            "gross_profit":       round(gp, 0),
            "expenses_opex":      round(exp, 0),
            "cogs":               round(cogs, 0),
            "revenue_mom_pct":    rev_mom,
            "net_profit_mom_pct": np_mom,
            "revenue_direction":  rev_dir,
            "np_direction":       np_dir,
            "period_count":       len(periods),
            # Series for trend explanation questions
            "revenue_series":     [_r2(s.get("income_statement",{}).get("revenue",{}).get("total",0)) for s in windowed],
            "np_series":          [_r2(s.get("income_statement",{}).get("net_profit",0)) for s in windowed],
            "expense_series":     [_r2(s.get("income_statement",{}).get("expenses",{}).get("total",0)) for s in windowed],
            "periods_list":       periods,
        },

        "statements": {
            "income_statement":   is_,
            "balance_sheet":      bs,
            "gross_margin_pct":   gm,
            "net_margin_pct":     nm,
            "operating_margin_pct": om,
            "expense_ratio":      er,
        },

        "analysis": {
            "profitability":      prof,
            "liquidity":          liq,
            "efficiency":         eff,
            "trends":             {
                "revenue_direction":    rev_dir,
                "np_direction":         np_dir,
                "revenue_mom_pct":      rev_mom,
                "net_profit_mom_pct":   np_mom,
                # Full trend series from analysis_engine
                "revenue_series":       trends.get("revenue",     {}).get("series", []),
                "np_series":            trends.get("net_profit",  {}).get("series", []),
                "margin_series":        trends.get("net_profit",  {}).get("mom_pct", []),
                "revenue_mom_series":   trends.get("revenue",     {}).get("mom_pct", []),
            },
            # Per-period breakdown for comparison questions
            "periods_data": [
                {
                    "period":     s.get("period"),
                    "revenue":    _r2(s.get("income_statement",{}).get("revenue",{}).get("total",0)),
                    "net_profit": _r2(s.get("income_statement",{}).get("net_profit",0)),
                    "net_margin": s.get("income_statement",{}).get("net_margin_pct"),
                    "gross_margin": s.get("income_statement",{}).get("gross_margin_pct"),
                    "expenses":   _r2(s.get("income_statement",{}).get("expenses",{}).get("total",0)),
                }
                for s in windowed
            ],
            "structured_income_statement": analysis.get("structured_income_statement"),
            "structured_income_statement_meta": analysis.get("structured_income_statement_meta"),
            "structured_income_statement_variance": analysis.get("structured_income_statement_variance"),
            "structured_income_statement_margin_variance": analysis.get(
                "structured_income_statement_margin_variance"
            ),
            "structured_income_statement_variance_meta": analysis.get(
                "structured_income_statement_variance_meta"
            ),
            "structured_profit_bridge": analysis.get("structured_profit_bridge"),
            "structured_profit_bridge_interpretation": analysis.get(
                "structured_profit_bridge_interpretation"
            ),
            "structured_profit_bridge_meta": analysis.get("structured_profit_bridge_meta"),
            "structured_profit_story": analysis.get("structured_profit_story"),
        },

        "cashflow":   cashflow_ctx,
        "branches":   branch_ctx,
        "validation": validation_ctx,
        "decisions":  cfo_decisions_ctx,
        "causal_items": merged_causal_templates,
        "realized_causal_items": realized_causal_advisor,
        "legacy_ai_cfo_decision": legacy_ai_cfo_decision,

        # ── Spec-mandated key aliases ─────────────────────────────────────────
        # "executive" = decisions + analysis (same data, different label)
        "executive":  cfo_decisions_ctx,
        # "forecast" = not yet in live pipeline; stub with available trend data
        "forecast":   {
            "available":        False,
            "note":             "Forecast engine not active in current pipeline",
            "revenue_direction": trends.get("revenue", {}).get("direction"),
            "revenue_mom_pct":   rev_mom,
        },
        # "board_report" = summary from available data (lightweight, no full build)
        "board_report": {
            "period":           period,
            "health_summary":   cfo_decisions_ctx.get("priority", "UNKNOWN"),
            "top_action":       _board_top_action,
            "risk_score":       cfo_decisions_ctx.get("risk_score"),
            "summary_available": True,
        },
    }
