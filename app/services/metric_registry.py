"""
metric_registry.py — Metric Definition Registry (Resolver foundation).

Purpose:
- Provide formal, canonical definitions for every metric key used by MetricResolver.
- Centralize: unit, rounding, sign semantics, source preference, allowed scopes/windows.

Rules:
- Read-only registry (no DB, no HTTP).
- No API coupling; used by resolver + shadow-mode comparisons + evidence layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional

Scope = Literal["company", "consolidated", "branch"]
Window = Literal["1M", "3M", "6M", "12M", "YTD", "ALL"]
Unit = Literal["currency", "pct", "ratio", "days", "count", "score", "bool", "string"]
SignRule = Literal["can_be_negative", "non_negative", "pct_0_100", "ratio_non_negative"]


@dataclass(frozen=True)
class RoundingRule:
    mode: Literal["round"] = "round"
    decimals: int = 2


@dataclass(frozen=True)
class MetricDefinition:
    key: str
    family: str
    unit: Unit
    description: str
    rounding: RoundingRule
    sign_rule: SignRule
    source_preference: tuple[str, ...]
    allowed_scopes: tuple[Scope, ...]
    allowed_windows: tuple[Window, ...]
    notes: tuple[str, ...] = ()


_ALL_SCOPES: tuple[Scope, ...] = ("company", "consolidated", "branch")
_ALL_WINDOWS: tuple[Window, ...] = ("1M", "3M", "6M", "12M", "YTD", "ALL")


def _m(
    *,
    key: str,
    family: str,
    unit: Unit,
    description: str,
    decimals: int,
    sign_rule: SignRule,
    source_preference: list[str],
    allowed_scopes: tuple[Scope, ...] = _ALL_SCOPES,
    allowed_windows: tuple[Window, ...] = _ALL_WINDOWS,
    notes: Optional[list[str]] = None,
) -> MetricDefinition:
    return MetricDefinition(
        key=key,
        family=family,
        unit=unit,
        description=description,
        rounding=RoundingRule(decimals=decimals),
        sign_rule=sign_rule,
        source_preference=tuple(source_preference),
        allowed_scopes=allowed_scopes,
        allowed_windows=allowed_windows,
        notes=tuple(notes or []),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Canonical metric catalog (keys used across evidence layer)
# ══════════════════════════════════════════════════════════════════════════════

_DEFS: dict[str, MetricDefinition] = {
    # Period/meta
    "period": _m(
        key="period",
        family="period.meta",
        unit="string",
        description="Statement period identifier (e.g., 2025-02).",
        decimals=0,
        sign_rule="non_negative",
        source_preference=["statement.period"],
        notes=["String metric; rounding/sign are not applicable."],
    ),

    # Income levels
    "revenue": _m(
        key="revenue",
        family="income.level",
        unit="currency",
        description="Revenue total for the period.",
        decimals=2,
        sign_rule="non_negative",
        source_preference=["statement.income_statement.revenue.total"],
    ),
    "cogs": _m(
        key="cogs",
        family="income.level",
        unit="currency",
        description="Cost of Goods Sold total for the period.",
        decimals=2,
        sign_rule="non_negative",
        source_preference=["statement.income_statement.cogs.total"],
    ),
    "operating_expenses": _m(
        key="operating_expenses",
        family="income.level",
        unit="currency",
        description="Operating expenses total for the period (OpEx).",
        decimals=2,
        sign_rule="non_negative",
        source_preference=["statement.income_statement.expenses.total"],
    ),
    "unclassified_pnl_debits": _m(
        key="unclassified_pnl_debits",
        family="income.level",
        unit="currency",
        description="Unclassified P&L debit total (if present) for the period.",
        decimals=2,
        sign_rule="non_negative",
        source_preference=["statement.income_statement.unclassified_pnl_debits.total"],
        notes=["May be missing from some statement sets; treat absent as 0 in derived ratios only."],
    ),
    "gross_profit": _m(
        key="gross_profit",
        family="income.level",
        unit="currency",
        description="Gross profit value for the period.",
        decimals=2,
        sign_rule="can_be_negative",
        source_preference=["statement.income_statement.gross_profit"],
    ),
    "operating_profit": _m(
        key="operating_profit",
        family="income.level",
        unit="currency",
        description="Operating profit value for the period.",
        decimals=2,
        sign_rule="can_be_negative",
        source_preference=["statement.income_statement.operating_profit"],
    ),
    "net_profit": _m(
        key="net_profit",
        family="income.level",
        unit="currency",
        description="Net profit value for the period.",
        decimals=2,
        sign_rule="can_be_negative",
        source_preference=["statement.income_statement.net_profit"],
    ),

    # Income ratios (% 0-100)
    "gross_margin_pct": _m(
        key="gross_margin_pct",
        family="income.ratio_pct",
        unit="pct",
        description="Gross margin percentage (0–100). Can be negative if gross profit is negative.",
        decimals=2,
        sign_rule="can_be_negative",
        source_preference=["statement.income_statement.gross_margin_pct", "analysis.latest.profitability.gross_margin_pct"],
    ),
    "operating_margin_pct": _m(
        key="operating_margin_pct",
        family="income.ratio_pct",
        unit="pct",
        description="Operating margin percentage (0–100). Can be negative.",
        decimals=2,
        sign_rule="can_be_negative",
        source_preference=["statement.income_statement.operating_margin_pct", "analysis.latest.profitability.operating_margin_pct"],
    ),
    "net_margin_pct": _m(
        key="net_margin_pct",
        family="income.ratio_pct",
        unit="pct",
        description="Net margin percentage (0–100). Can be negative.",
        decimals=2,
        sign_rule="can_be_negative",
        source_preference=["statement.income_statement.net_margin_pct", "analysis.latest.profitability.net_margin_pct"],
    ),
    "cogs_ratio_pct": _m(
        key="cogs_ratio_pct",
        family="income.ratio_pct",
        unit="pct",
        description="COGS as % of revenue (0–100).",
        decimals=2,
        sign_rule="pct_0_100",
        source_preference=["statement.income_statement.cogs_ratio_pct"],
    ),
    "opex_ratio_pct": _m(
        key="opex_ratio_pct",
        family="income.ratio_pct",
        unit="pct",
        description="Operating expenses as % of revenue (0–100).",
        decimals=2,
        sign_rule="pct_0_100",
        source_preference=["statement.income_statement.opex_ratio_pct"],
    ),
    "total_cost_ratio_pct": _m(
        key="total_cost_ratio_pct",
        family="income.ratio_pct",
        unit="pct",
        description="(COGS + OpEx + unclassified P&L debits) as % of revenue (0–100).",
        decimals=2,
        sign_rule="pct_0_100",
        source_preference=["statement.income_statement.total_cost_ratio_pct"],
        notes=["Canonical 'expense_ratio' in older layers maps to this metric."],
    ),

    # Balance sheet levels
    "current_assets": _m(
        key="current_assets",
        family="balance.level",
        unit="currency",
        description="Current assets for the period.",
        decimals=2,
        sign_rule="non_negative",
        source_preference=["statement.balance_sheet.current_assets"],
    ),
    "current_liabilities": _m(
        key="current_liabilities",
        family="balance.level",
        unit="currency",
        description="Current liabilities for the period.",
        decimals=2,
        sign_rule="non_negative",
        source_preference=["statement.balance_sheet.current_liabilities"],
    ),
    "working_capital": _m(
        key="working_capital",
        family="balance.level",
        unit="currency",
        description="Working capital for the period (current assets - current liabilities).",
        decimals=2,
        sign_rule="can_be_negative",
        source_preference=["statement.balance_sheet.working_capital"],
    ),
    "total_assets": _m(
        key="total_assets",
        family="balance.level",
        unit="currency",
        description="Total assets for the period.",
        decimals=2,
        sign_rule="non_negative",
        source_preference=["statement.balance_sheet.assets.total"],
    ),
    "total_liabilities": _m(
        key="total_liabilities",
        family="balance.level",
        unit="currency",
        description="Total liabilities for the period.",
        decimals=2,
        sign_rule="non_negative",
        source_preference=["statement.balance_sheet.liabilities.total"],
    ),
    "total_equity": _m(
        key="total_equity",
        family="balance.level",
        unit="currency",
        description="Total equity for the period.",
        decimals=2,
        sign_rule="can_be_negative",
        source_preference=["statement.balance_sheet.equity.total"],
    ),

    # Liquidity ratios
    "current_ratio": _m(
        key="current_ratio",
        family="liquidity.ratio",
        unit="ratio",
        description="Current ratio (current assets / current liabilities).",
        decimals=4,
        sign_rule="ratio_non_negative",
        source_preference=["analysis.latest.liquidity.current_ratio"],
    ),
    "quick_ratio": _m(
        key="quick_ratio",
        family="liquidity.ratio",
        unit="ratio",
        description="Quick ratio ((current assets - inventory) / current liabilities).",
        decimals=4,
        sign_rule="ratio_non_negative",
        source_preference=["analysis.latest.liquidity.quick_ratio"],
    ),
    "liquidity_approximated": _m(
        key="liquidity_approximated",
        family="liquidity.flag",
        unit="bool",
        description="True when liquidity ratios are approximated/unreliable due to missing BS inputs.",
        decimals=0,
        sign_rule="non_negative",
        source_preference=["analysis.latest.liquidity.liquidity_approximated", "statement.balance_sheet.current_assets_approximated"],
    ),

    # Efficiency
    "inventory_turnover": _m(
        key="inventory_turnover",
        family="efficiency.ratio",
        unit="ratio",
        description="Inventory turnover ratio.",
        decimals=4,
        sign_rule="ratio_non_negative",
        source_preference=["analysis.latest.efficiency.inventory_turnover"],
    ),
    "dio_days": _m(
        key="dio_days",
        family="efficiency.days",
        unit="days",
        description="Days inventory outstanding (DIO).",
        decimals=2,
        sign_rule="ratio_non_negative",
        source_preference=["analysis.latest.efficiency.dio_days"],
    ),
    "dso_days": _m(
        key="dso_days",
        family="efficiency.days",
        unit="days",
        description="Days sales outstanding (DSO).",
        decimals=2,
        sign_rule="ratio_non_negative",
        source_preference=["analysis.latest.efficiency.dso_days"],
    ),
    "dpo_days": _m(
        key="dpo_days",
        family="efficiency.days",
        unit="days",
        description="Days payable outstanding (DPO).",
        decimals=2,
        sign_rule="ratio_non_negative",
        source_preference=["analysis.latest.efficiency.dpo_days"],
    ),
    "ccc_days": _m(
        key="ccc_days",
        family="efficiency.days",
        unit="days",
        description="Cash conversion cycle (CCC).",
        decimals=2,
        sign_rule="ratio_non_negative",
        source_preference=["analysis.latest.efficiency.ccc_days"],
    ),

    # Leverage
    "debt_to_equity": _m(
        key="debt_to_equity",
        family="leverage.ratio",
        unit="ratio",
        description="Debt-to-equity ratio (total liabilities / total equity).",
        decimals=4,
        sign_rule="ratio_non_negative",
        source_preference=["analysis.latest.leverage.debt_to_equity"],
    ),

    # Cashflow
    "operating_cashflow": _m(
        key="operating_cashflow",
        family="cashflow.level",
        unit="currency",
        description="Operating cashflow (OCF) for the period.",
        decimals=2,
        sign_rule="can_be_negative",
        source_preference=["cashflow.operating_cashflow", "cashflow.series.operating_cashflow"],
    ),
    "working_capital_change": _m(
        key="working_capital_change",
        family="cashflow.level",
        unit="currency",
        description="Net working capital change used in cashflow computation (if available).",
        decimals=2,
        sign_rule="can_be_negative",
        source_preference=["cashflow.working_capital_change.net"],
    ),
}


def get_metric_definition(key: str) -> Optional[MetricDefinition]:
    return _DEFS.get(key)


def list_metric_definitions(prefix: str | None = None, family: str | None = None) -> list[MetricDefinition]:
    out = list(_DEFS.values())
    if prefix:
        out = [d for d in out if d.key.startswith(prefix)]
    if family:
        out = [d for d in out if d.family == family or d.family.startswith(family)]
    out.sort(key=lambda d: d.key)
    return out


def validate_key(key: str) -> bool:
    return key in _DEFS


def family_of(key: str) -> Optional[str]:
    d = _DEFS.get(key)
    return d.family if d else None

