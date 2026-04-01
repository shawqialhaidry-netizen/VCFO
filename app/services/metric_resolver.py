"""
metric_resolver.py — Metric Resolver (single source of truth access layer).

Provides canonical metric access across:
- root causes
- decisions
- deep intelligence
- branch intelligence

Design rules:
- Read-only: no DB, no HTTP, no side effects.
- Accepts already-windowed statement lists; does not own filtering semantics.
- Uses Metric Definition Registry for unit/rounding/semantics.
- Exposes stable accessors: get/series/delta/direction/trend_quality/quality/meta/snapshot.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional

from app.services.metric_definitions import (
    cogs_ratio_pct,
    opex_ratio_pct,
    total_cost_ratio_pct,
)
from app.services.metric_registry import get_metric_definition

Scope = Literal["company", "consolidated", "branch"]
Window = Literal["1M", "3M", "6M", "12M", "YTD", "ALL"]
Direction = Literal["up", "down", "stable", "insufficient_data"]
TrendQuality = Literal["stable", "volatile", "insufficient_data"]


def _safe_float(v) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _round(v: Any, decimals: int) -> Any:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    try:
        return round(float(v), decimals)
    except Exception:
        return v


def _mom_pct(curr: Optional[float], prev: Optional[float]) -> Optional[float]:
    if curr is None or prev is None:
        return None
    if prev == 0:
        return None
    return round((curr - prev) / abs(prev) * 100, 2)


def _trend_direction(mom_series: list) -> Direction:
    """Shared direction label used across assembly points today."""
    vals = [v for v in (mom_series or []) if v is not None]
    if not vals:
        return "insufficient_data"
    last = vals[-1]
    if last > 0.5:
        return "up"
    if last < -0.5:
        return "down"
    return "stable"


def _trend_quality(mom_series: list) -> TrendQuality:
    vals = [v for v in (mom_series or []) if v is not None]
    if len(vals) < 2:
        return "insufficient_data" if not vals else "stable"
    a, b = vals[-2], vals[-1]
    if (a > 0.5 and b < -0.5) or (a < -0.5 and b > 0.5):
        return "volatile"
    return "stable"


def _granularity_from_period(p: str) -> str:
    p = (p or "").strip()
    if len(p) == 4 and p.isdigit():
        return "year"
    if "Q" in p.upper():
        return "quarter"
    if "-" in p:
        return "month"
    return "unknown"


@dataclass(frozen=True)
class MetricDelta:
    current: Optional[float]
    previous: Optional[float]
    delta: Optional[float]
    delta_pct: Optional[float]
    unit: str
    period_current: Optional[str]
    period_previous: Optional[str]
    source: str


class MetricResolver:
    def __init__(
        self,
        *,
        period_statements: list[dict],
        scope: Scope,
        window: Window,
        currency: str = "",
        analysis: Optional[dict] = None,
        cashflow: Optional[dict] = None,
        branch_portfolio: Optional[dict] = None,
    ) -> None:
        self._stmts = period_statements or []
        self._scope = scope
        self._window = window
        self._currency = currency or ""
        self._analysis = analysis or {}
        self._cashflow = cashflow or {}
        self._branch_portfolio = branch_portfolio or {}

        self._periods = [str(s.get("period") or "") for s in self._stmts if isinstance(s, dict)]
        self._granularity = _granularity_from_period(self._periods[-1] if self._periods else "")

        # Materialize key->series cache lazily
        self._series_cache: dict[str, list] = {}
        self._latest_cache: dict[str, Any] = {}

    @classmethod
    def from_statements(
        cls,
        *,
        period_statements: list[dict],
        scope: Scope,
        window: Window,
        currency: str = "",
        analysis: Optional[dict] = None,
        cashflow: Optional[dict] = None,
        branch_portfolio: Optional[dict] = None,
    ) -> "MetricResolver":
        return cls(
            period_statements=period_statements,
            scope=scope,
            window=window,
            currency=currency,
            analysis=analysis,
            cashflow=cashflow,
            branch_portfolio=branch_portfolio,
        )

    # ── Meta / Quality ───────────────────────────────────────────────────────
    def meta(self) -> dict:
        return {
            "scope": self._scope,
            "window": self._window,
            "currency": self._currency,
            "periods": self._periods,
            "period_granularity": self._granularity,
        }

    def quality(self, key: str | None = None) -> dict:
        missing_points: dict[str, int] = {}
        approximated: list[str] = []
        denom_risks: list[str] = []

        # Denominator risk: revenue near zero in latest period
        rev = self.get("revenue")
        if rev is not None and abs(float(rev)) < 1e-6:
            denom_risks.append("revenue_near_zero")

        # Approximations: liquidity approximated flag
        la = self.get("liquidity_approximated")
        if la:
            approximated.append("liquidity")

        # Missingness counts (only for the requested key family, or small core set)
        keys = [key] if key else [
            "revenue", "net_profit", "net_margin_pct",
            "operating_cashflow", "current_ratio", "working_capital",
        ]
        for k in keys:
            try:
                s = self.series(k)
                missing_points[k] = sum(1 for v in s if v is None)
            except Exception:
                missing_points[k] = len(self._periods) or 0

        return {
            "n_periods": len(self._periods),
            "periods": list(self._periods),
            "missing_points": missing_points,
            "approximated": approximated,
            "denominator_risks": denom_risks,
            "notes": [],
        }

    # ── Accessors ────────────────────────────────────────────────────────────
    def get(self, key: str, *, period: str | None = None, default=None):
        if period:
            try:
                idx = self._periods.index(period)
            except ValueError:
                return default
            s = self.series(key)
            return s[idx] if idx < len(s) else default
        if key in self._latest_cache:
            return self._latest_cache[key]
        s = self.series(key)
        val = s[-1] if s else default
        self._latest_cache[key] = val
        return val

    def series(self, key: str) -> list:
        if key in self._series_cache:
            return self._series_cache[key]

        # Prefer analysis trend series for known metrics
        tr = (self._analysis or {}).get("trends") or {}
        series_key_map = {
            "revenue": "revenue_series",
            "net_profit": "net_profit_series",
            "gross_margin_pct": "gross_margin_series",
            "operating_expenses": "expenses_series",
        }
        if key in series_key_map and series_key_map[key] in tr:
            out = [ _safe_float(v) for v in (tr.get(series_key_map[key]) or []) ]
            self._series_cache[key] = out
            return out

        # Cashflow series
        if key == "operating_cashflow":
            ser = (self._cashflow or {}).get("series") or {}
            out = [ _safe_float(v) for v in (ser.get("operating_cashflow") or []) ]
            self._series_cache[key] = out
            return out

        # Fall back to statement extraction for per-period levels/ratios
        out: list[Any] = []
        for stmt in self._stmts:
            out.append(self._extract_from_statement(stmt, key))

        # Apply registry rounding where relevant
        md = get_metric_definition(key)
        if md and md.unit not in ("string", "bool"):
            out = [_round(v, md.rounding.decimals) for v in out]

        self._series_cache[key] = out
        return out

    def delta(self, key: str) -> dict:
        s = self.series(key)
        cur = s[-1] if len(s) >= 1 else None
        prev = s[-2] if len(s) >= 2 else None

        d = None
        if cur is not None and prev is not None:
            try:
                d = float(cur) - float(prev)
            except Exception:
                d = None

        dp = _mom_pct(_safe_float(cur), _safe_float(prev))
        md = get_metric_definition(key)
        unit = md.unit if md else "unknown"
        src = (md.source_preference[0] if md and md.source_preference else "resolver")
        return MetricDelta(
            current=_safe_float(cur),
            previous=_safe_float(prev),
            delta=_safe_float(d),
            delta_pct=dp,
            unit=unit,
            period_current=self._periods[-1] if self._periods else None,
            period_previous=self._periods[-2] if len(self._periods) >= 2 else None,
            source=src,
        ).__dict__

    def direction(self, key: str) -> Direction:
        # Use analysis MoM series when available
        tr = (self._analysis or {}).get("trends") or {}
        mom_key_map = {
            "revenue": "revenue_mom_pct",
            "net_profit": "net_profit_mom_pct",
            "gross_margin_pct": "gross_margin_mom_pct",
            "operating_expenses": "expenses_mom_pct",
        }
        if key == "operating_cashflow":
            # compute from cashflow series
            s = self.series("operating_cashflow")
            mom = [None]
            for i in range(1, len(s)):
                mom.append(_mom_pct(s[i], s[i - 1]))
            return _trend_direction(mom)
        if key in mom_key_map and mom_key_map[key] in tr:
            return _trend_direction(tr.get(mom_key_map[key]) or [])

        # Fallback: compute MoM from scalar series
        s = [ _safe_float(v) for v in self.series(key) ]
        mom = [None]
        for i in range(1, len(s)):
            mom.append(_mom_pct(s[i], s[i - 1]))
        return _trend_direction(mom)

    def trend_quality(self, key: str) -> TrendQuality:
        tr = (self._analysis or {}).get("trends") or {}
        mom_key_map = {
            "revenue": "revenue_mom_pct",
            "net_profit": "net_profit_mom_pct",
            "gross_margin_pct": "gross_margin_mom_pct",
            "operating_expenses": "expenses_mom_pct",
        }
        if key == "operating_cashflow":
            s = self.series("operating_cashflow")
            mom = [None]
            for i in range(1, len(s)):
                mom.append(_mom_pct(s[i], s[i - 1]))
            return _trend_quality(mom)
        if key in mom_key_map and mom_key_map[key] in tr:
            return _trend_quality(tr.get(mom_key_map[key]) or [])
        s = [ _safe_float(v) for v in self.series(key) ]
        mom = [None]
        for i in range(1, len(s)):
            mom.append(_mom_pct(s[i], s[i - 1]))
        return _trend_quality(mom)

    def snapshot(self) -> dict:
        # Materialize small core set (expand as needed)
        core = [
            "revenue", "net_profit", "net_margin_pct",
            "gross_margin_pct", "operating_expenses",
            "current_ratio", "quick_ratio", "working_capital",
            "total_cost_ratio_pct", "operating_cashflow",
        ]
        series = {k: self.series(k) for k in core}
        deltas = {k: self.delta(k) for k in core}
        directions = {k: self.direction(k) for k in core}
        qualities = {k: self.trend_quality(k) for k in core}
        by_period: dict[str, dict[str, Any]] = {}
        for i, p in enumerate(self._periods):
            by_period[p] = {k: (series[k][i] if i < len(series[k]) else None) for k in core}
        latest = {k: (series[k][-1] if series[k] else None) for k in core}
        return {
            "meta": self.meta(),
            "latest": latest,
            "by_period": by_period,
            "series": series,
            "derived": {
                "deltas": deltas,
                "directions": directions,
                "trend_quality": qualities,
            },
            "quality": self.quality(),
        }

    # ── Statement extraction (single source) ──────────────────────────────────
    def _extract_from_statement(self, stmt: dict, key: str):
        if not isinstance(stmt, dict):
            return None
        is_ = stmt.get("income_statement") or {}
        bs = stmt.get("balance_sheet") or {}

        if key == "period":
            return stmt.get("period")

        # Income levels
        if key == "revenue":
            return _safe_float(((is_.get("revenue") or {}).get("total")))
        if key == "cogs":
            return _safe_float(((is_.get("cogs") or {}).get("total")))
        if key == "operating_expenses":
            return _safe_float(((is_.get("expenses") or {}).get("total")))
        if key == "unclassified_pnl_debits":
            return _safe_float(((is_.get("unclassified_pnl_debits") or {}).get("total")))
        if key in ("gross_profit", "operating_profit", "net_profit"):
            return _safe_float(is_.get(key))

        # Ratios that may already be present
        if key in ("gross_margin_pct", "operating_margin_pct", "net_margin_pct"):
            return _safe_float(is_.get(key))
        if key in ("cogs_ratio_pct", "opex_ratio_pct", "total_cost_ratio_pct"):
            v = _safe_float(is_.get(key))
            if v is not None:
                return v
            # Compute deterministically using metric_definitions
            rev = _safe_float(((is_.get("revenue") or {}).get("total")))
            c = _safe_float(((is_.get("cogs") or {}).get("total")))
            e = _safe_float(((is_.get("expenses") or {}).get("total")))
            u = _safe_float(((is_.get("unclassified_pnl_debits") or {}).get("total"))) or 0.0
            if key == "cogs_ratio_pct":
                return cogs_ratio_pct(c, rev)
            if key == "opex_ratio_pct":
                return opex_ratio_pct(e, rev)
            return total_cost_ratio_pct(c, e, rev, u)

        # Balance sheet levels
        if key in ("current_assets", "current_liabilities", "working_capital"):
            return _safe_float(bs.get(key))
        if key == "total_assets":
            return _safe_float(((bs.get("assets") or {}).get("total")))
        if key == "total_liabilities":
            return _safe_float(((bs.get("liabilities") or {}).get("total")))
        if key == "total_equity":
            return _safe_float(((bs.get("equity") or {}).get("total")))

        # Liquidity approximations flags
        if key == "liquidity_approximated":
            ca_a = bool(bs.get("current_assets_approximated", False))
            cl_a = bool(bs.get("current_liabilities_approximated", False))
            return bool(ca_a or cl_a)

        # Ratios from analysis.latest only (kept centralized)
        latest = (self._analysis or {}).get("latest") or {}
        if key == "current_ratio":
            return _safe_float(((latest.get("liquidity") or {}).get("current_ratio")))
        if key == "quick_ratio":
            return _safe_float(((latest.get("liquidity") or {}).get("quick_ratio")))
        if key == "inventory_turnover":
            return _safe_float(((latest.get("efficiency") or {}).get("inventory_turnover")))
        if key == "dio_days":
            return _safe_float(((latest.get("efficiency") or {}).get("dio_days")))
        if key == "dso_days":
            return _safe_float(((latest.get("efficiency") or {}).get("dso_days")))
        if key == "dpo_days":
            return _safe_float(((latest.get("efficiency") or {}).get("dpo_days")))
        if key == "ccc_days":
            return _safe_float(((latest.get("efficiency") or {}).get("ccc_days")))
        if key == "debt_to_equity":
            return _safe_float(((latest.get("leverage") or {}).get("debt_to_equity")))

        # Cashflow-derived
        if key == "working_capital_change":
            wcc = (self._cashflow or {}).get("working_capital_change") or {}
            return _safe_float(wcc.get("net"))

        return None

