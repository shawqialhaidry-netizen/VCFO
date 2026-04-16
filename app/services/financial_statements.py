"""
financial_statements.py — SINGLE SOURCE OF TRUTH (Phase 4)

ALL financial values in the system originate here.
No other service may recompute: net_profit, gross_profit, working_capital,
current_assets, current_liabilities, or any balance sheet total.

Pipeline position (mandatory):
  normalized_tb → [this file] → statements_to_dict()
                              → analysis_engine   (reads only)
                              → cashflow_engine   (reads only)
                              → decision_engine   (reads only)
                              → executive endpoint

Contract:
  - Input:  pandas DataFrame with columns produced by classify_dataframe()
            (account_code, account_name, debit, credit, period,
             mapped_type, confidence, match_reason)
  - Output: FinancialStatements dataclass → statements_to_dict() → plain dict

Key outputs guaranteed by this module:
  income_statement.net_profit          = operating_profit - tax
  income_statement.gross_profit        = revenue - cogs
  balance_sheet.working_capital        = current_assets - current_liabilities
  balance_sheet.current_assets         = sum(assets with code 1000-1399)
  balance_sheet.current_liabilities    = sum(liabilities with code 2000-2199)

Design rules:
  - Zero side effects, zero DB access, zero file I/O
  - Phase 3 classification is the ONLY upstream source
  - Does NOT compute forecasts, does NOT build dashboard summary
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from app.services.account_rules import (
    ASSETS, COGS, EQUITY, EXPENSES, LIABILITIES, REVENUE, TAX,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  Data structures
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class LineItem:
    account_code:  str
    account_name:  str
    amount:        float          # positive = normal balance for that type
    mapped_type:   str
    confidence:    float
    provenance:    str = "direct_source_leaf"
    source_row_count: int = 1


@dataclass
class IncomeStatement:
    company_id:       str
    period:           str

    # Revenue
    revenue_items:    list[LineItem] = field(default_factory=list)
    total_revenue:    float = 0.0

    # COGS
    cogs_items:       list[LineItem] = field(default_factory=list)
    total_cogs:       float = 0.0

    # Gross Profit
    gross_profit:     float = 0.0
    gross_margin_pct: float = 0.0   # gross_profit / total_revenue * 100

    # Operating Expenses (mapped_type == EXPENSES only)
    expense_items:    list[LineItem] = field(default_factory=list)
    total_expenses:   float = 0.0

    # Unclassified debit-net P&L suspects (mapped_type == "other", amount > 0)
    # — kept separate from expense_items so category intelligence is not inflated;
    #   deducted in operating_profit so profit is not overstated.
    unclassified_pnl_debit_items: list[LineItem] = field(default_factory=list)
    total_unclassified_pnl_debits: float = 0.0
    unclassified_pnl_impact_excluded: bool = False
    income_statement_warning: str | None = None

    # Operating Profit
    operating_profit: float = 0.0
    operating_margin_pct: float = 0.0

    # Tax
    tax_items:        list[LineItem] = field(default_factory=list)
    total_tax:        float = 0.0

    # Net Profit
    net_profit:       float = 0.0
    net_margin_pct:   float = 0.0


@dataclass
class BalanceSheet:
    company_id:         str
    period:             str

    # Assets
    asset_items:        list[LineItem] = field(default_factory=list)
    total_assets:       float = 0.0

    # Asset breakdown — account code ranges (1000-1399 = current, 1400+ = non-current)
    current_assets:     float | None = 0.0
    noncurrent_assets:  float | None = 0.0

    # Liabilities
    liability_items:    list[LineItem] = field(default_factory=list)
    total_liabilities:  float = 0.0

    # Liability breakdown — (2000-2199 = current, 2200+ = non-current)
    current_liabilities:    float | None = 0.0
    noncurrent_liabilities: float | None = 0.0

    # Equity
    equity_items:       list[LineItem] = field(default_factory=list)
    total_equity:       float = 0.0

    # Working Capital — SINGLE SOURCE OF TRUTH
    # working_capital = current_assets - current_liabilities
    working_capital:    float | None = 0.0

    # Balance check:  assets == liabilities + equity
    liabilities_equity: float = 0.0
    is_balanced:        bool = False
    balance_diff:       float = 0.0
    current_assets_approximated:      bool = False   # retained for backward compatibility; no longer used for "all current" fallback
    current_liabilities_approximated: bool = False   # retained for backward compatibility; no longer used for "all current" fallback
    current_assets_unavailable:       bool = False
    current_liabilities_unavailable:  bool = False
    current_noncurrent_grouping_warning: str | None = None

    # FIX-2.1: TB type metadata
    tb_type:        str | None = None   # "pre_closing"|"post_closing"|"unknown"
    np_injected:    bool = False        # True only when pre_closing NP was added
    balance_warning: str | None = None  # set when tb_type unknown
    synthetic_equity_support: bool = False
    synthetic_equity_support_reason: str | None = None
    retained_earnings_continuity_proven: bool = False
    equity_rollforward_available: bool = False
    equity_integrity_warning: str | None = None


@dataclass
class FinancialStatements:
    company_id:        str
    period:            str
    income_statement:  IncomeStatement
    balance_sheet:     BalanceSheet
    unclassified_rows: int = 0     # rows with mapped_type == 'other' or conf == 0


# Canonicalize mapped_type for both bucketing and line-item metadata.
# Only widen categories for confirmed "expenses" aliases.
_MAPPED_TYPE_ALIASES = {
    # common variants from upstream mappers / legacy normalizers
    "expense": "expenses",
    "operating_expense": "expenses",
    "operating_expenses": "expenses",
    "operating expense": "expenses",
    "operating expenses": "expenses",
    "opex": "expenses",
    "sga": "expenses",
    "sg&a": "expenses",
    "selling_general_admin": "expenses",
    "selling_general_administrative": "expenses",
    "other_expense": "expenses",
    "other_expenses": "expenses",
}


def _canon_mapped_type(v: object) -> str:
    raw = str(v or "other").strip().lower()
    return _MAPPED_TYPE_ALIASES.get(raw, raw)


# ═══════════════════════════════════════════════════════════════════════════════
#  Helper: net amount per account
# ═══════════════════════════════════════════════════════════════════════════════

def _net_amount(row: dict, positive_side: str) -> float:
    """
    Return the net signed amount for a row.
    positive_side: 'debit' → debit-normal accounts (assets, cogs, expenses)
                   'credit' → credit-normal accounts (revenue, liabilities, equity)
    """
    debit  = float(row.get("debit",  0) or 0)
    credit = float(row.get("credit", 0) or 0)
    if positive_side == "debit":
        return round(debit - credit, 2)
    else:
        return round(credit - debit, 2)


def _to_line_item(row: dict, positive_side: str) -> LineItem:
    source_row_count = int(float(row.get("source_row_count", 1) or 1))
    provenance = "merged_source_leaf" if source_row_count > 1 else "direct_source_leaf"
    return LineItem(
        account_code = str(row.get("account_code", "")),
        account_name = str(row.get("account_name", "")),
        amount       = _net_amount(row, positive_side),
        mapped_type  = _canon_mapped_type(row.get("mapped_type", "other")),
        confidence   = float(row.get("confidence", 0)),
        provenance   = provenance,
        source_row_count = source_row_count,
    )


def _round2(v: float) -> float:
    return round(v, 2)


def _safe_pct(numerator: float, denominator: float) -> Optional[float]:
    """Return percentage, or None when denominator is zero.
    Unified zero-revenue behavior: None means 'not meaningful', not zero.
    """
    if not denominator:
        return None
    return _round2(numerator / denominator * 100)


# ═══════════════════════════════════════════════════════════════════════════════
#  Income Statement builder
# ═══════════════════════════════════════════════════════════════════════════════

def _build_income_statement(
    company_id: str,
    period: str,
    df: pd.DataFrame,
) -> IncomeStatement:

    stmt = IncomeStatement(company_id=company_id, period=period)

    for row in df.to_dict(orient="records"):
        mtype = _canon_mapped_type(row.get("mapped_type", "other"))

        if mtype == REVENUE:
            li = _to_line_item(row, "credit")
            stmt.revenue_items.append(li)

        elif mtype == COGS:
            li = _to_line_item(row, "debit")
            stmt.cogs_items.append(li)

        elif mtype == EXPENSES:
            li = _to_line_item(row, "debit")
            stmt.expense_items.append(li)

        elif mtype == TAX:
            li = _to_line_item(row, "debit")
            stmt.tax_items.append(li)

        elif mtype == "other":
            # Unclassified: positive debit-net amounts are P&L suspects — track separately
            # so operating expense *categories* (expense_engine) are not polluted; they
            # still reduce operating profit identically to the old "stuff in opex" rule.
            li = _to_line_item(row, "debit")
            if li.amount > 0:
                stmt.unclassified_pnl_debit_items.append(li)
            # credit-net unclassified: excluded from P&L (not dropped from BS)

    # ── Totals ────────────────────────────────────────────────────────────────
    stmt.total_revenue  = _round2(sum(li.amount for li in stmt.revenue_items))
    stmt.total_cogs     = _round2(sum(li.amount for li in stmt.cogs_items))
    stmt.gross_profit   = _round2(stmt.total_revenue - stmt.total_cogs)
    stmt.gross_margin_pct = _safe_pct(stmt.gross_profit, stmt.total_revenue)

    stmt.total_unclassified_pnl_debits = _round2(
        sum(li.amount for li in stmt.unclassified_pnl_debit_items)
    )
    stmt.unclassified_pnl_impact_excluded = False
    if stmt.total_unclassified_pnl_debits > 0:
        stmt.income_statement_warning = (
            "unclassified_pnl_debits_deducted_from_profit: debit-net unmapped rows were deducted from profit but kept separate from operating expense categories"
        )

    stmt.total_expenses     = _round2(sum(li.amount for li in stmt.expense_items))
    stmt.operating_profit   = _round2(
        stmt.gross_profit - stmt.total_expenses - stmt.total_unclassified_pnl_debits
    )
    stmt.operating_margin_pct = _safe_pct(stmt.operating_profit, stmt.total_revenue)

    stmt.total_tax  = _round2(sum(li.amount for li in stmt.tax_items))
    stmt.net_profit = _round2(stmt.operating_profit - stmt.total_tax)
    stmt.net_margin_pct = _safe_pct(stmt.net_profit, stmt.total_revenue)

    return stmt


# ═══════════════════════════════════════════════════════════════════════════════
#  Balance Sheet builder
# ═══════════════════════════════════════════════════════════════════════════════

def _build_balance_sheet(
    company_id: str,
    period: str,
    df: pd.DataFrame,
    net_profit: float,
    tb_type: str | None = None,  # FIX-2.1
) -> BalanceSheet:

    bs = BalanceSheet(company_id=company_id, period=period)

    for row in df.to_dict(orient="records"):
        mtype = _canon_mapped_type(row.get("mapped_type", "other"))

        if mtype == ASSETS:
            bs.asset_items.append(_to_line_item(row, "debit"))

        elif mtype == LIABILITIES:
            bs.liability_items.append(_to_line_item(row, "credit"))

        elif mtype == EQUITY:
            bs.equity_items.append(_to_line_item(row, "credit"))

    # ── FIX-2.1: Net Profit injection — depends on TB type ────────────────────
    # pre_closing TB: IS accounts are still open → must add NP to equity
    #                 so that Assets = Liabilities + Equity holds.
    # post_closing TB: closing entries already moved NP into retained earnings
#                     → adding it again would double-count and break balance.
    # unknown (None): conservative — do NOT inject, flag as tb_type_unknown.
    bs.tb_type          = tb_type or "unknown"
    bs.np_injected      = False
    bs.balance_warning  = None
    bs.synthetic_equity_support = False
    bs.synthetic_equity_support_reason = None
    bs.retained_earnings_continuity_proven = False
    bs.equity_rollforward_available = False
    bs.equity_integrity_warning = None

    if tb_type == "pre_closing" and net_profit != 0:
        bs.equity_items.append(LineItem(
            account_code = "NET_PROFIT",
            account_name = "Net Profit (Current Period)",
            amount       = _round2(net_profit),
            mapped_type  = EQUITY,
            confidence   = 1.0,
            provenance   = "synthetic_injected",
            source_row_count = 0,
        ))
        bs.np_injected = True
        bs.synthetic_equity_support = True
        bs.synthetic_equity_support_reason = (
            "pre_closing_net_profit_injected_for_balance_support"
        )
        bs.equity_integrity_warning = (
            "equity_rollforward_not_proven: current-period net profit was injected to support pre-closing balance handling"
        )
    elif tb_type == "post_closing":
        # NP already in retained earnings ? do not touch
        bs.equity_integrity_warning = (
            "equity_rollforward_not_proven: post-closing retained earnings continuity is assumed from tb_type but not independently verified"
        )
    else:
        # Unknown tb_type: conservative, no injection, flag warning
        bs.balance_warning = "tb_type_unknown: net_profit not injected into equity"
        bs.equity_integrity_warning = (
            "equity_rollforward_not_proven: tb_type is unknown and retained earnings continuity is not verified"
        )

    # ?? Totals ????????????????????????????????????????????????????????????????
    bs.total_assets      = _round2(sum(li.amount for li in bs.asset_items))
    bs.total_liabilities = _round2(sum(li.amount for li in bs.liability_items))
    bs.total_equity      = _round2(sum(li.amount for li in bs.equity_items))
    bs.liabilities_equity = _round2(bs.total_liabilities + bs.total_equity)

    # ── Current / Non-current breakdown via account code ranges ──────────────
    # Standard Arabic chart of accounts:
    #   1000-1399 → current assets
    #   1400-1999 → non-current (fixed) assets
    #   2000-2199 → current liabilities
    #   2200-2999 → non-current liabilities
    def _split_by_code_range(
        items: list[LineItem],
        current_lo: int,
        current_hi: int,
        noncurrent_lo: int,
        noncurrent_hi: int,
    ) -> tuple[float | None, float | None, bool]:
        current_total = 0.0
        noncurrent_total = 0.0
        has_unknown = False
        for item in items:
            code = str(item.account_code).strip()
            try:
                num = int(code[:4]) if len(code) >= 4 else int(code)
            except (ValueError, TypeError):
                has_unknown = True
                continue

            if current_lo <= num <= current_hi:
                current_total += abs(item.amount)
            elif noncurrent_lo <= num <= noncurrent_hi:
                noncurrent_total += abs(item.amount)
            else:
                has_unknown = True

        if has_unknown:
            return None, None, True
        return _round2(current_total), _round2(noncurrent_total), False

    bs.current_assets_approximated = False
    bs.current_liabilities_approximated = False
    bs.current_noncurrent_grouping_warning = None

    bs.current_assets, bs.noncurrent_assets, asset_grouping_unknown = _split_by_code_range(
        bs.asset_items, 1000, 1399, 1400, 1999
    )
    (
        bs.current_liabilities,
        bs.noncurrent_liabilities,
        liability_grouping_unknown,
    ) = _split_by_code_range(bs.liability_items, 2000, 2199, 2200, 2999)

    bs.current_assets_unavailable = asset_grouping_unknown and bs.total_assets != 0.0
    bs.current_liabilities_unavailable = liability_grouping_unknown and bs.total_liabilities != 0.0
    if bs.current_assets_unavailable and bs.current_liabilities_unavailable:
        bs.current_noncurrent_grouping_warning = (
            "current_noncurrent_grouping_unavailable: asset and liability code ranges are incomplete or nonstandard"
        )
    elif bs.current_assets_unavailable:
        bs.current_noncurrent_grouping_warning = (
            "current_noncurrent_grouping_unavailable: asset code ranges are incomplete or nonstandard"
        )
    elif bs.current_liabilities_unavailable:
        bs.current_noncurrent_grouping_warning = (
            "current_noncurrent_grouping_unavailable: liability code ranges are incomplete or nonstandard"
        )

    # ── Working Capital — SINGLE SOURCE OF TRUTH ─────────────────────────────
    # Formula: Working Capital = Current Assets - Current Liabilities
    if bs.current_assets is None or bs.current_liabilities is None:
        bs.working_capital = None
    else:
        bs.working_capital = _round2(bs.current_assets - bs.current_liabilities)

    # Balance check
    TOLERANCE = 0.10   # allow up to 10 cents rounding difference
    bs.balance_diff = _round2(abs(bs.total_assets - bs.liabilities_equity))
    bs.is_balanced  = bs.balance_diff <= TOLERANCE

    return bs


# ═══════════════════════════════════════════════════════════════════════════════
#  Main entry point
# ═══════════════════════════════════════════════════════════════════════════════

def build_statements(
    df: pd.DataFrame,
    company_id: str,
    period: str,
    tb_type: str | None = None,  # FIX-2.1: "pre_closing"|"post_closing"|None
) -> FinancialStatements:
    """
    Build Income Statement + Balance Sheet from a classified DataFrame.

    Args:
        df:         classified DataFrame (output of classify_dataframe())
        company_id: UUID of the company
        period:     period string e.g. "2026-01"

    Returns:
        FinancialStatements — fully computed, JSON-serialisable via to_dict()
    """
    if df.empty:
        empty_is = IncomeStatement(company_id=company_id, period=period)
        empty_bs = BalanceSheet(company_id=company_id, period=period)
        return FinancialStatements(
            company_id=company_id, period=period,
            income_statement=empty_is, balance_sheet=empty_bs,
        )

    unclassified = int(((df["mapped_type"] == "other") | (df["confidence"] == 0)).sum())

    income_stmt = _build_income_statement(company_id, period, df)
    balance_sheet = _build_balance_sheet(
        company_id, period, df,
        net_profit=income_stmt.net_profit,
        tb_type=tb_type,  # FIX-2.1
    )

    return FinancialStatements(
        company_id        = company_id,
        period            = period,
        income_statement  = income_stmt,
        balance_sheet     = balance_sheet,
        unclassified_rows = unclassified,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Serialiser — converts dataclasses → plain dicts for JSON responses
# ═══════════════════════════════════════════════════════════════════════════════

def _line_items_to_list(items: list[LineItem]) -> list[dict]:
    return [
        {
            "account_code": li.account_code,
            "account_name": li.account_name,
            "amount":       li.amount,
            "mapped_type":  li.mapped_type,
            "confidence":   li.confidence,
            "provenance":   li.provenance,
            "source_row_count": li.source_row_count,
        }
        for li in items
    ]


def statements_to_dict(fs: FinancialStatements) -> dict:
    """Convert FinancialStatements to a plain JSON-serialisable dict."""
    is_ = fs.income_statement
    bs  = fs.balance_sheet

    return {
        "company_id":        fs.company_id,
        "period":            fs.period,
        "unclassified_rows": fs.unclassified_rows,

        "income_statement": {
            "revenue": {
                "items":   _line_items_to_list(is_.revenue_items),
                "total":   is_.total_revenue,
            },
            "cogs": {
                "items":  _line_items_to_list(is_.cogs_items),
                "total":  is_.total_cogs,
            },
            "gross_profit":        is_.gross_profit,
            "gross_margin_pct":    is_.gross_margin_pct,
            "expenses": {
                "items":  _line_items_to_list(is_.expense_items),
                "total":  is_.total_expenses,
            },
            "unclassified_pnl_debits": {
                "items": _line_items_to_list(is_.unclassified_pnl_debit_items),
                "total": is_.total_unclassified_pnl_debits,
                "excluded_from_profit": is_.unclassified_pnl_impact_excluded,
                "deducted_from_profit": is_.total_unclassified_pnl_debits > 0,
            },
            "income_statement_warning": is_.income_statement_warning,
            "operating_profit":        is_.operating_profit,
            "operating_margin_pct":    is_.operating_margin_pct,
            "tax": {
                "items": _line_items_to_list(is_.tax_items),
                "total": is_.total_tax,
            },
            "net_profit":      is_.net_profit,
            "net_margin_pct":  is_.net_margin_pct,
        },

        "balance_sheet": {
            "assets": {
                "items": _line_items_to_list(bs.asset_items),
                "total": bs.total_assets,
                "current":     bs.current_assets,
                "noncurrent":  bs.noncurrent_assets,
            },
            "liabilities": {
                "items": _line_items_to_list(bs.liability_items),
                "total": bs.total_liabilities,
                "current":     bs.current_liabilities,
                "noncurrent":  bs.noncurrent_liabilities,
            },
            "equity": {
                "items": _line_items_to_list(bs.equity_items),
                "total": bs.total_equity,
                "synthetic_equity_support": bs.synthetic_equity_support,
                "synthetic_equity_support_reason": bs.synthetic_equity_support_reason,
                "retained_earnings_continuity_proven": bs.retained_earnings_continuity_proven,
                "equity_rollforward_available": bs.equity_rollforward_available,
                "equity_integrity_warning": bs.equity_integrity_warning,
            },
            # SINGLE SOURCE OF TRUTH for working capital
            "working_capital":        bs.working_capital,
            "current_assets":         bs.current_assets,
            "current_liabilities":    bs.current_liabilities,
            "noncurrent_assets":      bs.noncurrent_assets,
            "noncurrent_liabilities": bs.noncurrent_liabilities,
            "liabilities_and_equity": bs.liabilities_equity,
            "is_balanced":            bs.is_balanced,
            "balance_diff":           bs.balance_diff,
            "current_assets_approximated":      bs.current_assets_approximated,
            "current_liabilities_approximated": bs.current_liabilities_approximated,
            "current_assets_unavailable":       bs.current_assets_unavailable,
            "current_liabilities_unavailable":  bs.current_liabilities_unavailable,
            "current_noncurrent_grouping_warning": bs.current_noncurrent_grouping_warning,
            # FIX-2.1: TB type transparency
            "tb_type":        bs.tb_type,
            "np_injected":    bs.np_injected,
            "balance_warning": bs.balance_warning,
        },
    }
