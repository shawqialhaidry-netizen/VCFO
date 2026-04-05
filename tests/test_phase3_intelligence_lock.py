"""
Phase 3 — intelligence path wiring (static + decision summary shape).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.cfo_decision_engine import build_cfo_decisions


def test_analysis_module_has_no_legacy_alerts_helper_name():
    text = Path(__file__).resolve().parents[1] / "app" / "api" / "analysis.py"
    src = text.read_text(encoding="utf-8")
    assert "_build_alerts_for_decisions" not in src


def test_product_windowed_helper_exists():
    from app.api import analysis as analysis_api

    assert callable(getattr(analysis_api, "_product_windowed_statements", None))


def test_cfo_decisions_summary_includes_insufficient_evidence_flag():
    minimal_intel = {
        "ratios": {
            "profitability": {"net_margin_pct": {"value": 5.0, "status": "good"}},
            "liquidity": {"current_ratio": {"value": 2.0, "status": "good"}},
            "efficiency": {},
            "leverage": {},
            "growth": {},
        },
        "trends": {"revenue": {}, "net_profit": {}},
        "anomalies": [],
        "health_score_v2": 72,
    }
    out = build_cfo_decisions(minimal_intel, [], lang="en", n_periods=3, analysis={})
    assert "insufficient_evidence" in (out.get("summary") or {})
    assert isinstance(out["summary"]["insufficient_evidence"], bool)
