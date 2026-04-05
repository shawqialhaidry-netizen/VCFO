"""
canonical_period_statements.py — Phase 2 (Financial truth lock)

SINGLE entry point for building period statement dicts from TrialBalanceUpload rows.

Canonical accounting path (company-level TB):
  Upload (uploads.py) → parse/validate → classify_dataframe → normalized CSV on disk
  → THIS MODULE: load CSV → classify_dataframe (idempotent re-classify) →
     financial_statements.build_statements → statements_to_dict →
     attach_structured_income_statement

All product surfaces that consume company-level uploads MUST use
``build_period_statements_from_uploads`` — not parallel loaders.

Rationale for re-classifying on read:
  - Same rules as upload-time classification (single classifier version at read time).
  - Avoids drift between code paths that required ``mapped_type`` on CSV vs those that did not.
"""
from __future__ import annotations

import re
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


def build_period_statements_from_uploads(company_id: str, uploads: list[Any]) -> list[dict]:
    """
    Build chronological period statements for a company from upload records.

    Mirrors historical analysis._build_period_statements semantics (period grouping,
    tb_type map, pre-closing flags) with mandatory classify_dataframe before build_statements.
    """
    period_dfs: dict[str, pd.DataFrame] = {}
    for record in uploads:
        df = load_normalized_tb_dataframe(record)
        if df is None or df.empty:
            continue
        if "period" in df.columns:
            for period, grp in df.groupby("period"):
                period_dfs[str(period)] = grp.copy()
        elif record.period:
            period_dfs[record.period] = df.copy()

    if not period_dfs:
        return []

    period_tb_type: dict[str, str | None] = {}
    for record in uploads:
        tt = getattr(record, "tb_type", None)
        if not tt:
            continue
        rp = record.period or ""
        if re.match(r"^\d{4}-\d{2}$", rp):
            period_tb_type[rp] = tt
        elif re.match(r"^\d{4}$", rp):
            for p in period_dfs:
                if str(p).startswith(rp + "-"):
                    period_tb_type[p] = tt
        elif rp:
            period_tb_type[rp] = tt

    stmts: list[dict] = []
    for period in sorted(period_dfs.keys()):
        tb_type = period_tb_type.get(period)
        classified = classify_dataframe(period_dfs[period])
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
