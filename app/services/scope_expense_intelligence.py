"""
scope_expense_intelligence.py — Phase 3 (Scope-aware Expense Intelligence)

Defines the JSON schema and builders for expense intelligence across:
  - company
  - branch
  - group (companies; optionally branches under each company)

This module:
  - Reuses statement-derived values only (TB uploads → build_statements → statements_to_dict).
  - Reuses existing expense intelligence engine for per-entity bundles:
      app.services.expense_intelligence_engine.build_expense_intelligence_bundle
  - Adds deterministic rollups and comparisons at the scope level.
  - Performs access via the scope resolver (Phase 2) when used from API layer.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.models.company import Company
from app.models.trial_balance import TrialBalanceUpload
from app.models.user import User
from app.services.account_classifier import classify_dataframe
from app.services.expense_intelligence_engine import build_expense_intelligence_bundle
from app.services.financial_statements import build_statements, statements_to_dict
from app.services.structured_income_statement import attach_structured_income_statement
from app.services.scope_resolver import ResolvedScope, resolve_financial_scope

# ---------------------------------------------------------------------------
# JSON schema (exact shape)
# ---------------------------------------------------------------------------
#
# Response (dict):
# {
#   "status": "success",
#   "scope": {
#     "scope_type": "company" | "branch" | "group",
#     "scope_id": "<uuid>",
#     "group_id": "<uuid>|null",
#     "branch_id": "<uuid>|null",
#     "company_ids": ["<uuid>", ...]
#   },
#   "expense": {
#     "level": "company" | "branch" | "group",
#     "entities": [
#        {
#          "entity_type": "company" | "branch",
#          "entity_id": "<uuid>",
#          "entity_name": "<string>|null",
#          "company_id": "<uuid>|null",   # present for branch
#          "bundle": {  # output of build_expense_intelligence_bundle(...)
#            "expense_analysis": {...},
#            "expense_anomalies": [...],
#            "expense_decisions": [...],
#            "expense_explanation": {...}
#          }
#        }, ...
#     ],
#     "rollups": {
#       # Present only for group level:
#       "group": {
#         "meta": {...},
#         "by_period": [...],   # aligned by YYYY-MM
#         "by_year": [...],
#         "by_category_timeseries": { ... },  # sums
#       }
#     },
#     "comparisons": {
#       "highest_cost_entity": { "entity_type": ..., "entity_id": ..., "period": ..., "metric": ..., "value": ... },
#       "most_efficient_entity": { ... },   # metric = expense_pct_of_revenue (if revenue available) else total_expense
#       "biggest_cost_driver_by_scope": {
#         "driver_type": "category" | "entity",
#         "key": "<category_key>|<entity_id>",
#         "period": "<YYYY-MM>|null",
#         "absolute_change": <number>|null,
#         "pct_change": <number>|null,
#         "contribution_to_total_change_pct": <number>|null
#       }
#     }
#   }
# }


# ---------------------------------------------------------------------------
# TB → statements (reuses financial_statements single source of truth)
# ---------------------------------------------------------------------------

def _load_df(record: TrialBalanceUpload) -> Optional[pd.DataFrame]:
    if not record.normalized_path:
        return None
    try:
        df = pd.read_csv(record.normalized_path)
    except Exception:
        return None
    required = {"account_code", "account_name", "debit", "credit"}
    return df if required.issubset(set(df.columns)) else None


def _build_period_statements_from_uploads(company_id: str, uploads: list[TrialBalanceUpload]) -> list[dict]:
    """
    Minimal statement builder aligned with analysis.py:
      - prefer df.period grouping if present
      - else record.period
      - carry tb_type into build_statements
    """
    period_dfs: dict[str, pd.DataFrame] = {}
    for record in uploads:
        df = _load_df(record)
        if df is None or df.empty:
            continue
        if "period" in df.columns:
            for period, grp in df.groupby("period"):
                period_dfs[str(period)] = grp.copy()
        elif record.period:
            period_dfs[record.period] = df.copy()

    if not period_dfs:
        return []

    # Map tb_type by period (best-effort, same semantics as analysis.py)
    import re as _re

    period_tb_type: dict[str, str | None] = {}
    for record in uploads:
        tt = getattr(record, "tb_type", None)
        if not tt:
            continue
        rp = record.period or ""
        if _re.match(r"^\d{4}-\d{2}$", rp):
            period_tb_type[rp] = tt
        elif _re.match(r"^\d{4}$", rp):
            for p in period_dfs:
                if str(p).startswith(rp + "-"):
                    period_tb_type[p] = tt
        elif rp:
            period_tb_type[rp] = tt

    stmts: list[dict] = []
    for period in sorted(period_dfs.keys()):
        tb_type = period_tb_type.get(period)
        classified = classify_dataframe(period_dfs[period])
        fs = build_statements(classified, company_id=company_id, period=period, tb_type=tb_type)
        d = statements_to_dict(fs)
        d["period"] = period
        attach_structured_income_statement(d)
        stmts.append(d)
    return stmts


# ---------------------------------------------------------------------------
# Deterministic group rollups + comparisons
# ---------------------------------------------------------------------------

def _sum_category_dict(a: dict[str, float], b: dict[str, float]) -> dict[str, float]:
    out = defaultdict(float)
    for k, v in (a or {}).items():
        out[k] += float(v or 0)
    for k, v in (b or {}).items():
        out[k] += float(v or 0)
    return {k: round(v, 2) for k, v in sorted(out.items()) if abs(v) > 1e-9}


def _rollup_group_entities(entities: list[dict]) -> dict[str, Any]:
    """
    Roll up by_period/by_year/category series across company entities.
    Deterministic: periods sorted, categories sorted, numeric rounded to 2dp.
    """
    # Gather by_period rows from each entity bundle
    by_period_map: dict[str, dict[str, Any]] = {}
    for ent in entities:
        if ent.get("entity_type") != "company":
            continue
        b = (ent.get("bundle") or {}).get("expense_analysis") or {}
        for row in (b.get("by_period") or []):
            p = row.get("period")
            if not p:
                continue
            slot = by_period_map.setdefault(
                p,
                {
                    "period": p,
                    "revenue": 0.0,
                    "cogs": 0.0,
                    "operating_expenses": 0.0,
                    "unclassified_pnl_debits": 0.0,
                    "total_expense": 0.0,
                    "categories": {},
                },
            )
            slot["revenue"] += float(row.get("revenue") or 0)
            slot["cogs"] += float(row.get("cogs") or 0)
            slot["operating_expenses"] += float(row.get("operating_expenses") or 0)
            slot["unclassified_pnl_debits"] += float(row.get("unclassified_pnl_debits") or 0)
            slot["total_expense"] += float(row.get("total_expense") or 0)
            slot["categories"] = _sum_category_dict(slot.get("categories") or {}, row.get("categories") or {})

    by_period = []
    for p in sorted(by_period_map.keys()):
        r = by_period_map[p]
        rev = float(r["revenue"] or 0)
        te = float(r["total_expense"] or 0)
        by_period.append(
            {
                "period": p,
                "revenue": round(rev, 2),
                "cogs": round(float(r["cogs"]), 2),
                "operating_expenses": round(float(r["operating_expenses"]), 2),
                "unclassified_pnl_debits": round(float(r["unclassified_pnl_debits"]), 2),
                "total_expense": round(te, 2),
                "expense_pct_of_revenue": round((te / rev) * 100, 2) if rev > 0 else None,
                "categories": r["categories"],
            }
        )

    # by_year: compute from by_period for determinism (no duplicate statement math)
    by_year_map: dict[int, dict[str, Any]] = {}
    for r in by_period:
        y = None
        try:
            y = int(str(r["period"])[:4])
        except Exception:
            continue
        s = by_year_map.setdefault(
            y,
            {
                "year": y,
                "revenue": 0.0,
                "total_expense": 0.0,
                "cogs": 0.0,
                "operating_expenses": 0.0,
                "unclassified_pnl_debits": 0.0,
                "categories": {},
            },
        )
        s["revenue"] += float(r.get("revenue") or 0)
        s["total_expense"] += float(r.get("total_expense") or 0)
        s["cogs"] += float(r.get("cogs") or 0)
        s["operating_expenses"] += float(r.get("operating_expenses") or 0)
        s["unclassified_pnl_debits"] += float(r.get("unclassified_pnl_debits") or 0)
        s["categories"] = _sum_category_dict(s.get("categories") or {}, r.get("categories") or {})

    by_year = []
    for y in sorted(by_year_map.keys()):
        s = by_year_map[y]
        rev = float(s["revenue"] or 0)
        te = float(s["total_expense"] or 0)
        by_year.append(
            {
                "year": y,
                "revenue": round(rev, 2),
                "total_expense": round(te, 2),
                "cogs": round(float(s["cogs"]), 2),
                "operating_expenses": round(float(s["operating_expenses"]), 2),
                "unclassified_pnl_debits": round(float(s["unclassified_pnl_debits"]), 2),
                "expense_pct_of_revenue": round((te / rev) * 100, 2) if rev > 0 else None,
                "categories": s["categories"],
            }
        )

    # category timeseries (sum)
    by_cat_ts: dict[str, list[dict]] = defaultdict(list)
    for r in by_period:
        p = r["period"]
        rev = float(r.get("revenue") or 0)
        for ck, amt in (r.get("categories") or {}).items():
            a = float(amt or 0)
            by_cat_ts[ck].append(
                {
                    "period": p,
                    "amount": round(a, 2),
                    "pct_of_revenue": round((a / rev) * 100, 2) if rev > 0 else None,
                }
            )
    by_cat_ts_out = {k: v for k, v in sorted(by_cat_ts.items())}

    return {
        "meta": {
            "engine": "scope_expense_rollup_v1",
            "entity_count": len([e for e in entities if e.get("entity_type") == "company"]),
        },
        "by_period": by_period,
        "by_year": by_year,
        "by_category_timeseries": by_cat_ts_out,
    }


def _latest_period_row(bundle: dict) -> Optional[dict]:
    rows = ((bundle or {}).get("expense_analysis") or {}).get("by_period") or []
    return rows[-1] if rows else None


def _comparisons(level: str, entities: list[dict]) -> dict[str, Any]:
    """
    Deterministic comparisons based on latest period row where possible.
    """
    # Highest cost: max total_expense
    best = None
    for e in entities:
        row = _latest_period_row(e.get("bundle") or {})
        if not row:
            continue
        val = row.get("total_expense") or 0
        key = (float(val), str(e.get("entity_id") or ""))
        if best is None or key > best[0]:
            best = (key, e, row)

    highest = None
    if best:
        _, e, row = best
        highest = {
            "entity_type": e.get("entity_type"),
            "entity_id": e.get("entity_id"),
            "period": row.get("period"),
            "metric": "total_expense",
            "value": row.get("total_expense"),
        }

    # Most efficient: min expense_pct_of_revenue (fallback total_expense)
    eff_best = None
    for e in entities:
        row = _latest_period_row(e.get("bundle") or {})
        if not row:
            continue
        ratio = row.get("expense_pct_of_revenue")
        if ratio is None:
            continue
        key = (float(ratio), str(e.get("entity_id") or ""))
        if eff_best is None or key < eff_best[0]:
            eff_best = (key, e, row)

    most_eff = None
    if eff_best:
        _, e, row = eff_best
        most_eff = {
            "entity_type": e.get("entity_type"),
            "entity_id": e.get("entity_id"),
            "period": row.get("period"),
            "metric": "expense_pct_of_revenue",
            "value": row.get("expense_pct_of_revenue"),
        }
    elif highest:
        # fallback: pick smallest total expense
        lo = None
        for e in entities:
            row = _latest_period_row(e.get("bundle") or {})
            if not row:
                continue
            val = row.get("total_expense") or 0
            key = (float(val), str(e.get("entity_id") or ""))
            if lo is None or key < lo[0]:
                lo = (key, e, row)
        if lo:
            _, e, row = lo
            most_eff = {
                "entity_type": e.get("entity_type"),
                "entity_id": e.get("entity_id"),
                "period": row.get("period"),
                "metric": "total_expense",
                "value": row.get("total_expense"),
            }

    # Biggest cost driver: for company/branch -> top_movers.increasing[0]; for group -> entity delta leader
    driver = None
    if level in ("company", "branch"):
        # single entity
        if entities:
            ex = (entities[0].get("bundle") or {}).get("expense_explanation") or {}
            tm = (ex.get("top_movers") or {}).get("increasing") or []
            if tm:
                top = tm[0]
                driver = {
                    "driver_type": "category",
                    "key": top.get("category"),
                    "period": (ex.get("headline") or None),
                    "absolute_change": top.get("absolute_change"),
                    "pct_change": top.get("pct_change"),
                    "contribution_to_total_change_pct": top.get("contribution_to_total_change_pct"),
                }
    else:
        # group: choose company with biggest MoM total expense delta
        best_delta = None
        for e in entities:
            row = _latest_period_row(e.get("bundle") or {})
            rows = ((e.get("bundle") or {}).get("expense_analysis") or {}).get("by_period") or []
            if len(rows) < 2 or not row:
                continue
            prev = rows[-2]
            delta = float(row.get("total_expense") or 0) - float(prev.get("total_expense") or 0)
            key = (delta, str(e.get("entity_id") or ""))
            if best_delta is None or key > best_delta[0]:
                best_delta = (key, e, row)
        if best_delta:
            (_, eid), e, row = best_delta
            driver = {
                "driver_type": "entity",
                "key": e.get("entity_id"),
                "period": row.get("period"),
                "absolute_change": round(best_delta[0][0], 2),
                "pct_change": None,
                "contribution_to_total_change_pct": None,
            }

    return {
        "highest_cost_entity": highest,
        "most_efficient_entity": most_eff,
        "biggest_cost_driver_by_scope": driver,
    }


# ---------------------------------------------------------------------------
# Public builder used by API
# ---------------------------------------------------------------------------

def build_scope_expense_intelligence(
    *,
    db: Session,
    user: User,
    scope_type: str,
    scope_id: str,
    lang: str = "en",
) -> dict[str, Any]:
    """
    Build scope-aware expense intelligence output.
    Deterministic ordering and statement-consistent totals.
    """
    safe_lang = lang if lang in ("en", "ar", "tr") else "en"
    rs: ResolvedScope = resolve_financial_scope(db, user, scope_type, scope_id)

    entities: list[dict] = []

    if rs.scope_type == "branch":
        # Branch: use branch-level TB uploads (branch_id set on upload)
        uploads = (
            db.query(TrialBalanceUpload)
            .filter(
                TrialBalanceUpload.company_id == rs.company_ids[0],
                TrialBalanceUpload.branch_id == rs.branch_id,
            )
            .order_by(TrialBalanceUpload.uploaded_at)
            .all()
        )
        stmts = _build_period_statements_from_uploads(rs.company_ids[0], uploads)
        bundle = build_expense_intelligence_bundle(stmts, lang=safe_lang)
        b = db.query(Branch).filter(Branch.id == rs.branch_id).first()
        entities.append(
            {
                "entity_type": "branch",
                "entity_id": rs.branch_id,
                "entity_name": getattr(b, "name", None) if b else None,
                "company_id": rs.company_ids[0],
                "bundle": bundle,
            }
        )
        level = "branch"
        rollups = {}

    elif rs.scope_type == "company":
        uploads = (
            db.query(TrialBalanceUpload)
            .filter(
                TrialBalanceUpload.company_id == rs.company_ids[0],
                TrialBalanceUpload.branch_id.is_(None),
            )
            .order_by(TrialBalanceUpload.uploaded_at)
            .all()
        )
        stmts = _build_period_statements_from_uploads(rs.company_ids[0], uploads)
        bundle = build_expense_intelligence_bundle(stmts, lang=safe_lang)
        c = db.query(Company).filter(Company.id == rs.company_ids[0]).first()
        entities.append(
            {
                "entity_type": "company",
                "entity_id": rs.company_ids[0],
                "entity_name": getattr(c, "name", None) if c else None,
                "company_id": rs.company_ids[0],
                "bundle": bundle,
            }
        )
        level = "company"
        rollups = {}

    else:
        # Group: per-company bundles
        for cid in sorted(rs.company_ids):
            uploads = (
                db.query(TrialBalanceUpload)
                .filter(
                    TrialBalanceUpload.company_id == cid,
                    TrialBalanceUpload.branch_id.is_(None),
                )
                .order_by(TrialBalanceUpload.uploaded_at)
                .all()
            )
            stmts = _build_period_statements_from_uploads(cid, uploads)
            bundle = build_expense_intelligence_bundle(stmts, lang=safe_lang)
            c = db.query(Company).filter(Company.id == cid).first()
            entities.append(
                {
                    "entity_type": "company",
                    "entity_id": cid,
                    "entity_name": getattr(c, "name", None) if c else None,
                    "company_id": cid,
                    "bundle": bundle,
                }
            )

        level = "group"
        rollups = {"group": _rollup_group_entities(entities)} if entities else {"group": {"meta": {"entity_count": 0}, "by_period": [], "by_year": [], "by_category_timeseries": {}}}

    comparisons = _comparisons(level, entities)

    return {
        "status": "success",
        "scope": {
            "scope_type": rs.scope_type,
            "scope_id": rs.scope_id,
            "group_id": rs.group_id,
            "branch_id": rs.branch_id,
            "company_ids": list(rs.company_ids),
        },
        "expense": {
            "level": level,
            "entities": entities,
            "rollups": rollups,
            "comparisons": comparisons,
        },
    }

