"""
CFO-grade period-over-period variance on top of structured_income_statement.

Source of truth: only `structured_income_statement` on each period dict.
If that key is absent, it is computed once via `build_structured_income_statement`
(same layer — not legacy summary fields).
"""
from __future__ import annotations

from typing import Any, Optional

from app.services.structured_income_statement import build_structured_income_statement

LINE_KEYS = (
    "revenue",
    "cogs",
    "gross_profit",
    "opex",
    "operating_profit",
    "net_profit",
)
MARGIN_KEYS = ("gross_margin_pct", "operating_margin_pct", "net_margin_pct")


def _round2(v: float) -> float:
    return round(float(v), 2)


def _structured_slice(period_statement: dict) -> dict[str, Any]:
    """Return the canonical structured IS dict for one period."""
    if not isinstance(period_statement, dict):
        return {}
    s = period_statement.get("structured_income_statement")
    if isinstance(s, dict) and s:
        return s
    return build_structured_income_statement(period_statement)


def _null_line() -> dict[str, Any]:
    return {"current": None, "previous": None, "delta": None, "delta_pct": None}


def _null_margin_line() -> dict[str, Any]:
    return {"current": None, "previous": None, "delta_pp": None}


def _line_variance(current: Optional[float], previous: Optional[float]) -> dict[str, Any]:
    delta: Optional[float] = None
    delta_pct: Optional[float] = None
    if current is not None and previous is not None:
        delta = _round2(float(current) - float(previous))
    if delta is not None and previous is not None and float(previous) != 0:
        delta_pct = _round2(delta / abs(float(previous)) * 100)
    return {
        "current": current,
        "previous": previous,
        "delta": delta,
        "delta_pct": delta_pct,
    }


def _margin_variance(current: Optional[float], previous: Optional[float]) -> dict[str, Any]:
    delta_pp: Optional[float] = None
    if current is not None and previous is not None:
        delta_pp = _round2(float(current) - float(previous))
    return {
        "current": current,
        "previous": previous,
        "delta_pp": delta_pp,
    }


def build_structured_income_statement_variance_bundle_from_window(
    windowed: list[dict],
) -> dict[str, Any]:
    """
    Compare the last two periods in `windowed` (oldest → newest).

    Formulas (per line):
      - current  = structured_income_statement[line] for latest period
      - previous = same for prior period
      - delta    = current - previous (both must be non-null)
      - delta_pct = delta / abs(previous) * 100  if previous is not null and != 0; else null

    Margin block:
      - delta_pp = current - previous (percentage points) when both non-null; else null

    Metadata:
      - latest_period, previous_period
      - completeness: full | partial | none
      - missing_lines: line/margin keys where current or previous is null
    """
    if len(windowed) < 2:
        latest = windowed[-1] if windowed else {}
        lp = latest.get("period") if isinstance(latest, dict) else None
        variance = {k: _null_line() for k in LINE_KEYS}
        margin_var = {k: _null_margin_line() for k in MARGIN_KEYS}
        all_keys = list(LINE_KEYS) + list(MARGIN_KEYS)
        return {
            "structured_income_statement_variance": variance,
            "structured_income_statement_margin_variance": margin_var,
            "structured_income_statement_variance_meta": {
                "latest_period": lp,
                "previous_period": None,
                "completeness": "none",
                "missing_lines": sorted(all_keys),
            },
        }

    latest = windowed[-1]
    prev = windowed[-2]
    cur_s = _structured_slice(latest)
    prev_s = _structured_slice(prev)

    variance: dict[str, Any] = {}
    missing_lines: list[str] = []

    for k in LINE_KEYS:
        c = cur_s.get(k) if isinstance(cur_s, dict) else None
        p = prev_s.get(k) if isinstance(prev_s, dict) else None
        variance[k] = _line_variance(
            float(c) if c is not None else None,
            float(p) if p is not None else None,
        )
        if c is None or p is None:
            missing_lines.append(k)

    margin_var: dict[str, Any] = {}
    for k in MARGIN_KEYS:
        c = cur_s.get(k) if isinstance(cur_s, dict) else None
        p = prev_s.get(k) if isinstance(prev_s, dict) else None
        margin_var[k] = _margin_variance(
            float(c) if c is not None else None,
            float(p) if p is not None else None,
        )
        if c is None or p is None:
            missing_lines.append(k)

    flow_ok = all(
        isinstance(cur_s, dict) and isinstance(prev_s, dict)
        and cur_s.get(k) is not None and prev_s.get(k) is not None
        for k in LINE_KEYS
    )
    margin_ok = all(
        isinstance(cur_s, dict) and isinstance(prev_s, dict)
        and cur_s.get(k) is not None and prev_s.get(k) is not None
        for k in MARGIN_KEYS
    )
    if flow_ok and margin_ok:
        completeness = "full"
    else:
        completeness = "partial"

    return {
        "structured_income_statement_variance": variance,
        "structured_income_statement_margin_variance": margin_var,
        "structured_income_statement_variance_meta": {
            "latest_period": latest.get("period"),
            "previous_period": prev.get("period"),
            "completeness": completeness,
            "missing_lines": sorted(set(missing_lines)),
        },
    }
