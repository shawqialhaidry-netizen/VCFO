"""
canonical_period_statements.py — Phase 2 + Phase 5 (branch reconstruction)

SINGLE entry point for building period statement dicts from TrialBalanceUpload rows.

Canonical accounting path:
  Upload → normalized CSV → classify_dataframe → financial_statements.build_statements
  → statements_to_dict → attach_structured_income_statement

Phase 5 — TB-level merge:
  When multiple uploads contribute to the same calendar period (e.g. several branches),
  normalized rows are merged by (account_code, account_name) with debit/credit summed,
  then the merged TB is classified and built once — same as company truth, no statement-level summing.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Optional

import pandas as pd

from app.services.account_classifier import classify_dataframe
from app.services.financial_statements import build_statements, statements_to_dict
from app.services.structured_income_statement import attach_structured_income_statement

if TYPE_CHECKING:
    from app.models.trial_balance import TrialBalanceUpload


def load_normalized_tb_dataframe(record: Any) -> Optional[pd.DataFrame]:
    """
    Load normalized upload CSV. Requires core TB columns only; ``mapped_type`` optional
    (classification is always re-applied).
    """
    path = getattr(record, "normalized_path", None) or ""
    if not path:
        return None
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    required = {"account_code", "account_name", "debit", "credit"}
    if not required.issubset(set(df.columns)):
        return None
    return df


def _collect_period_upload_slices(uploads: list[Any]) -> dict[str, list[tuple[Any, pd.DataFrame]]]:
    """Map period → list of (upload_record, dataframe_slice) contributing to that period."""
    period_slices: dict[str, list[tuple[Any, pd.DataFrame]]] = defaultdict(list)
    for record in uploads:
        df = load_normalized_tb_dataframe(record)
        if df is None or df.empty:
            continue
        if "period" in df.columns:
            for period, grp in df.groupby("period"):
                period_slices[str(period)].append((record, grp.copy()))
        elif record.period:
            period_slices[record.period].append((record, df.copy()))
    return period_slices


def merge_tb_slices_for_period(slices: list[pd.DataFrame], period: str) -> pd.DataFrame:
    """
    Sum debit/credit by (account_code, account_name) across TB slices (same period).
    """
    need = ("account_code", "account_name", "debit", "credit")
    parts: list[pd.DataFrame] = []
    for g in slices:
        if g is None or g.empty:
            continue
        miss = [c for c in need if c not in g.columns]
        if miss:
            return pd.DataFrame()
        sub = g[list(need)].copy()
        sub["account_code"] = sub["account_code"].astype(str).str.strip()
        sub["account_name"] = sub["account_name"].fillna("").astype(str)
        sub["debit"] = pd.to_numeric(sub["debit"], errors="coerce").fillna(0.0)
        sub["credit"] = pd.to_numeric(sub["credit"], errors="coerce").fillna(0.0)
        parts.append(sub)
    if not parts:
        return pd.DataFrame()
    all_df = pd.concat(parts, ignore_index=True)
    merged = all_df.groupby(["account_code", "account_name"], as_index=False)[["debit", "credit"]].sum()
    merged["period"] = period
    return merged


def _merged_tb_type(records: list[Any]) -> Optional[str]:
    """Single tb_type only if all non-null contributing uploads agree; else None (conservative)."""
    tys = {getattr(r, "tb_type", None) for r in records}
    tys.discard(None)
    if len(tys) == 1:
        return next(iter(tys))
    return None


def build_period_statements_from_uploads(company_id: str, uploads: list[Any]) -> list[dict]:
    """
    Build chronological period statements. For each period, **all** upload slices that
    contain that period are merged at TB row level before classify → build_statements.

    This is the only supported path from uploads to statements (company, single-branch,
    or multi-branch consolidation).
    """
    period_slices = _collect_period_upload_slices(uploads)
    if not period_slices:
        return []

    stmts: list[dict] = []
    for period in sorted(period_slices.keys()):
        entries = period_slices[period]
        records = [e[0] for e in entries]
        dfs = [e[1] for e in entries]
        merged = merge_tb_slices_for_period(dfs, period)
        if merged.empty:
            continue

        tb_type = _merged_tb_type(records)
        classified = classify_dataframe(merged)
        fs = build_statements(
            classified,
            company_id=company_id,
            period=period,
            tb_type=tb_type,
        )
        d = statements_to_dict(fs)
        d["period"] = period

        _net_profit = abs(d.get("income_statement", {}).get("net_profit", 0) or 0)
        _bal_diff = abs(d.get("balance_sheet", {}).get("balance_diff", 0) or 0)
        _pre_closing = (
            _bal_diff > 0.10
            and _net_profit > 0.10
            and abs(_bal_diff - _net_profit) / max(_net_profit, 1) < 0.02
        )
        if _pre_closing:
            d.setdefault("balance_sheet", {})
            d["balance_sheet"]["pre_closing_tb"] = True
            d["balance_sheet"]["is_balanced"] = "pre_closing_expected"
            d["balance_sheet"]["pre_closing_note"] = (
                "Balance sheet imbalance equals net profit — this is expected for a "
                "trial balance before period-end closing entries."
            )
        else:
            d.setdefault("balance_sheet", {})
            d["balance_sheet"]["pre_closing_tb"] = False

        attach_structured_income_statement(d)
        stmts.append(d)

    return stmts


def build_branch_period_statements(company_id: str, branch_id: str, uploads: list[Any]) -> list[dict]:
    """
    Canonical statements for one branch from its TB ``uploads`` (pre-filtered by caller).
    Same pipeline as company uploads; adds branch scope metadata on each period dict.
    """
    stmts = build_period_statements_from_uploads(company_id, uploads)
    for d in stmts:
        d["company_id"] = company_id
        d["data_source"] = "branch_upload"
        d["branch_id"] = branch_id
        d["is_consolidated"] = False
    return stmts
