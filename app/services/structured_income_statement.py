"""
Canonical flat income statement for CFO-grade analysis.

Source of numeric truth remains financial_statements.build_statements →
statements_to_dict() (or branch consolidation paths that mirror that shape).

This module only *projects* that nested structure into a single object with
explicit nulls when required inputs are absent — no silent defaults for COGS,
OpEx, or tax.
"""
from __future__ import annotations

from typing import Any, Optional


def _round2(v: float) -> float:
    return round(float(v), 2)


def _margin_pct(numerator: Optional[float], revenue: Optional[float]) -> Optional[float]:
    if numerator is None or revenue is None:
        return None
    if revenue == 0:
        return None
    return _round2(numerator / revenue * 100)


def _nested_total(is_: dict, section: str) -> Optional[float]:
    """Read income_statement.{section}.total; None if path invalid or total absent."""
    if not isinstance(is_, dict) or section not in is_:
        return None
    sec = is_[section]
    if not isinstance(sec, dict) or "total" not in sec:
        return None
    raw = sec["total"]
    if raw is None:
        return None
    try:
        return _round2(raw)
    except (TypeError, ValueError):
        return None


def _scalar_if_present(is_: dict, key: str) -> Optional[float]:
    """Float from IS scalar only when key exists; None if missing (not same as 0)."""
    if not isinstance(is_, dict) or key not in is_:
        return None
    raw = is_[key]
    if raw is None:
        return None
    try:
        return _round2(raw)
    except (TypeError, ValueError):
        return None


def _build_parts(period_statement: dict) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Returns (structured_income_statement nine-key dict, meta dict).
    """
    is_ = period_statement.get("income_statement") if isinstance(period_statement, dict) else None
    if not isinstance(is_, dict):
        out = {
            "revenue": None,
            "cogs": None,
            "gross_profit": None,
            "gross_margin_pct": None,
            "opex": None,
            "operating_profit": None,
            "operating_margin_pct": None,
            "net_profit": None,
            "net_margin_pct": None,
        }
        meta = {
            "completeness": "none",
            "missing_inputs": ["income_statement"],
            "net_profit_rule": None,
            "sources": {
                "revenue": None,
                "cogs": None,
                "opex": None,
            },
        }
        return out, meta

    missing: list[str] = []
    sources: dict[str, Optional[str]] = {
        "revenue": "income_statement.revenue.total",
        "cogs": "income_statement.cogs.total",
        "opex": "income_statement.expenses.total + income_statement.unclassified_pnl_debits.total",
    }

    revenue = _nested_total(is_, "revenue")
    if revenue is None:
        missing.append("income_statement.revenue.total")

    cogs = _nested_total(is_, "cogs")
    if cogs is None and "cogs" in is_:
        missing.append("income_statement.cogs.total")
    elif cogs is None and "cogs" not in is_:
        missing.append("income_statement.cogs")

    exp_total = _nested_total(is_, "expenses")
    uncl_total = _nested_total(is_, "unclassified_pnl_debits")
    opex: Optional[float] = None
    if "expenses" not in is_:
        missing.append("income_statement.expenses")
    elif exp_total is None:
        missing.append("income_statement.expenses.total")
    if "unclassified_pnl_debits" not in is_:
        missing.append("income_statement.unclassified_pnl_debits")
    elif uncl_total is None:
        missing.append("income_statement.unclassified_pnl_debits.total")
    if exp_total is not None and uncl_total is not None:
        opex = _round2(exp_total + uncl_total)

    gross_profit: Optional[float] = None
    if revenue is not None and cogs is not None:
        gross_profit = _round2(revenue - cogs)
    else:
        gross_profit = _scalar_if_present(is_, "gross_profit")

    operating_profit: Optional[float] = None
    if gross_profit is not None and opex is not None:
        operating_profit = _round2(gross_profit - opex)
    else:
        operating_profit = _scalar_if_present(is_, "operating_profit")

    net_profit: Optional[float] = None
    net_rule: Optional[str] = None
    tax_section = is_.get("tax")
    has_tax_block = isinstance(tax_section, dict)
    tax_total = _nested_total(is_, "tax") if has_tax_block else None

    if operating_profit is None:
        net_profit = _scalar_if_present(is_, "net_profit")
        net_rule = "published_only" if net_profit is not None else None
    elif has_tax_block:
        if "total" in tax_section:
            if tax_total is None:
                net_profit = _scalar_if_present(is_, "net_profit")
                net_rule = "published_only"
            else:
                net_profit = _round2(operating_profit - tax_total)
                net_rule = "operating_minus_tax"
        else:
            net_profit = _scalar_if_present(is_, "net_profit")
            net_rule = "published_only"
    else:
        net_profit = operating_profit
        net_rule = "operating_only"

    gross_margin_pct = _margin_pct(gross_profit, revenue)
    operating_margin_pct = _margin_pct(operating_profit, revenue)
    net_margin_pct = _margin_pct(net_profit, revenue)

    completeness = "full"
    if missing:
        completeness = "partial"
    elif revenue is None:
        completeness = "partial"
    elif gross_profit is None or operating_profit is None or net_profit is None:
        completeness = "partial"

    out = {
        "revenue": revenue,
        "cogs": cogs,
        "gross_profit": gross_profit,
        "gross_margin_pct": gross_margin_pct,
        "opex": opex,
        "operating_profit": operating_profit,
        "operating_margin_pct": operating_margin_pct,
        "net_profit": net_profit,
        "net_margin_pct": net_margin_pct,
    }
    meta = {
        "completeness": completeness,
        "missing_inputs": sorted(set(missing)),
        "net_profit_rule": net_rule,
        "sources": sources,
    }
    return out, meta


def build_structured_income_statement(period_statement: dict) -> dict[str, Any]:
    """
    Canonical nine-field income statement (nulls when inputs missing).

    Data sources (current model — no separate interest line; tax optional):
      - revenue: income_statement.revenue.total
      - cogs: income_statement.cogs.total
      - opex: expenses.total + unclassified_pnl_debits.total (matches financial_statements bridge)

    Formulas when inputs are complete:
      - gross_profit = revenue - cogs
      - operating_profit = gross_profit - opex
      - net_profit = operating_profit - tax.total if tax block includes total;
        else operating_profit if no tax block; else published net_profit when formula unusable.
    Margins: metric / revenue * 100 (None if revenue missing or zero).
    """
    body, _ = _build_parts(period_statement)
    return body


def build_structured_income_statement_bundle(period_statement: dict) -> dict[str, Any]:
    """Payload-shaped dict: structured_income_statement + structured_income_statement_meta."""
    body, meta = _build_parts(period_statement)
    return {
        "structured_income_statement": body,
        "structured_income_statement_meta": meta,
    }


def attach_structured_income_statement(period_statement: dict) -> None:
    """Mutate period_statement in place with structured IS keys."""
    bundle = build_structured_income_statement_bundle(period_statement)
    period_statement["structured_income_statement"] = bundle["structured_income_statement"]
    period_statement["structured_income_statement_meta"] = bundle["structured_income_statement_meta"]
