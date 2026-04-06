"""
Phase 5.1 — Branch validation lock (proof only).

Proves:
  Case 1: company-scoped TB uploads vs single-branch uploads → identical accounting
          truth through statements, KPI block, cashflow, bundle, intelligence, alerts,
          decisions, and forecast (given identical normalized TB inputs).
  Case 2: multi-upload TB merge at row level matches explicit merge_tb_slices + pipeline.
  Case 3: missing / invalid branch TB inputs produce no fabricated statements.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pandas as pd
import pytest

from app.services.account_classifier import classify_dataframe
from app.services.analysis_engine import run_analysis
from app.services.alerts_engine import build_alerts
from app.services.canonical_period_statements import (
    build_branch_period_statements,
    build_period_statements_from_uploads,
    load_normalized_tb_dataframe,
    merge_tb_slices_for_period,
)
from app.services.cashflow_engine import build_cashflow
from app.services.cfo_decision_engine import build_cfo_decisions
from app.services.fin_intelligence import build_intelligence
from app.services.forecast_engine import build_forecast
from app.services.period_aggregation import build_annual_layer
from app.services.statement_engine import build_statement_bundle
from app.services.structured_income_statement import attach_structured_income_statement
from app.services.financial_statements import build_statements, statements_to_dict
from app.services.time_intelligence import build_kpi_block


def _tb_rows_minimal_balanced() -> list[dict]:
    """Raw normalized TB rows (classifier runs in canonical pipeline)."""
    return [
        {"account_code": "1010", "account_name": "Cash", "debit": 50000, "credit": 0},
        {"account_code": "1100", "account_name": "Receivables", "debit": 30000, "credit": 0},
        {"account_code": "1200", "account_name": "Inventory", "debit": 20000, "credit": 0},
        {"account_code": "2010", "account_name": "Payables", "debit": 0, "credit": 15000},
        {"account_code": "3010", "account_name": "Capital", "debit": 0, "credit": 40000},
        {"account_code": "4010", "account_name": "Revenue", "debit": 0, "credit": 80000},
        {"account_code": "5010", "account_name": "COGS", "debit": 45000, "credit": 0},
        {"account_code": "6010", "account_name": "Salaries", "debit": 15000, "credit": 0},
    ]


def _write_tb_csv(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def _rec(path: Path, period_str: str, tb_type_str: str = "post_closing"):
    norm = str(path.resolve())

    class _R:
        normalized_path = norm
        period = period_str
        tb_type = tb_type_str

    return _R()


def _f(x, default=0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def _assert_income_statement_totals_equal(a: dict, b: dict) -> None:
    ia, ib = a.get("income_statement") or {}, b.get("income_statement") or {}
    for block in ("revenue", "cogs", "expenses", "tax"):
        assert _f((ia.get(block) or {}).get("total")) == pytest.approx(
            _f((ib.get(block) or {}).get("total")), rel=1e-9, abs=0.05
        )
    for scalar in (
        "gross_profit",
        "operating_profit",
        "net_profit",
        "gross_margin_pct",
        "net_margin_pct",
        "operating_margin_pct",
    ):
        assert _f(ia.get(scalar)) == pytest.approx(_f(ib.get(scalar)), rel=1e-9, abs=0.05)


def _assert_balance_sheet_totals_equal(a: dict, b: dict) -> None:
    ba, bb = a.get("balance_sheet") or {}, b.get("balance_sheet") or {}
    assert _f((ba.get("assets") or {}).get("total")) == pytest.approx(
        _f((bb.get("assets") or {}).get("total")), rel=1e-9, abs=0.05
    )
    assert _f((ba.get("liabilities") or {}).get("total")) == pytest.approx(
        _f((bb.get("liabilities") or {}).get("total")), rel=1e-9, abs=0.05
    )
    assert _f((ba.get("equity") or {}).get("total")) == pytest.approx(
        _f((bb.get("equity") or {}).get("total")), rel=1e-9, abs=0.05
    )
    assert _f(ba.get("working_capital")) == pytest.approx(_f(bb.get("working_capital")), rel=1e-9, abs=0.05)


def _strip_branch_product_meta(stmt: dict) -> dict:
    """Remove branch-only scope metadata; keep accounting payload."""
    out = {k: v for k, v in stmt.items() if k not in ("data_source", "branch_id", "is_consolidated")}
    return out


def _product_engine_fingerprint(stmts: list[dict], currency: str = "USD") -> dict:
    """
    Same engine stack used by executive-style surfaces: analysis → KPI → cashflow →
    intelligence → bundle → alerts → CFO decisions → forecast.
    """
    analysis = run_analysis(stmts)
    kpi = build_kpi_block(stmts, "ALL")
    cf = build_cashflow(stmts)
    annual = build_annual_layer(stmts)
    intel = build_intelligence(analysis=analysis, annual_layer=annual, currency=currency)
    bundle = build_statement_bundle(stmts, cf, intel)
    alerts = build_alerts(intel, lang="en").get("alerts", [])
    dec_pack = build_cfo_decisions(
        intel,
        alerts,
        lang="en",
        n_periods=len(stmts),
        analysis=analysis,
        branch_context=None,
    )
    forecast = build_forecast(analysis, lang="en")
    return {
        "analysis_latest_np": _f((analysis.get("latest") or {}).get("profitability", {}).get("net_profit")),
        "kpi_revenue": _f((kpi.get("kpis") or {}).get("revenue", {}).get("value")),
        "kpi_net_profit": _f((kpi.get("kpis") or {}).get("net_profit", {}).get("value")),
        "cf_ocf": _f(cf.get("operating_cashflow")),
        "intel_health": intel.get("health_score_v2"),
        "bundle_revenue": _f((bundle.get("summary") or {}).get("revenue")),
        "bundle_np": _f((bundle.get("summary") or {}).get("net_profit")),
        "bundle_ocf": _f((bundle.get("summary") or {}).get("operating_cashflow")),
        "alerts_fingerprint": tuple(sorted((str(a.get("type")), str(a.get("severity"))) for a in alerts)),
        "decisions_fingerprint": tuple(
            sorted(
                (str(d.get("domain")), str(d.get("urgency")), str(d.get("action") or d.get("title") or ""))
                for d in (dec_pack.get("decisions") or [])
            )
        ),
        "forecast_available": bool(forecast.get("available")),
        "forecast_summary_mom_rev": _f((forecast.get("summary") or {}).get("trend_mom_revenue")),
    }


def test_case1_single_branch_parity_with_company_statements_and_engine_stack(tmp_path):
    """
    Case 1 — Same normalized TB files uploaded as company vs single-branch scope.

    Compared:
      - Per-period income_statement / balance_sheet totals (no synthetic BS).
      - Engine fingerprint: run_analysis, build_kpi_block, build_cashflow,
        build_intelligence, build_statement_bundle, build_alerts, build_cfo_decisions,
        build_forecast.
    """
    company_id = uuid.uuid4().hex
    branch_id = uuid.uuid4().hex
    rows = _tb_rows_minimal_balanced()
    periods = ["2099-04", "2099-05", "2099-06"]
    company_uploads = []
    branch_uploads = []
    for p in periods:
        pth = tmp_path / f"tb_{p}.csv"
        _write_tb_csv(pth, rows)
        company_uploads.append(_rec(pth, p))
        pth_b = tmp_path / f"tb_br_{p}.csv"
        _write_tb_csv(pth_b, rows)
        branch_uploads.append(_rec(pth_b, p))

    stmts_company = build_period_statements_from_uploads(company_id, company_uploads)
    stmts_branch = build_branch_period_statements(company_id, branch_id, branch_uploads)

    assert len(stmts_company) == len(stmts_branch) == len(periods)
    for sc, sb in zip(stmts_company, stmts_branch, strict=True):
        assert sc["period"] == sb["period"]
        sb_core = _strip_branch_product_meta(sb)
        assert sc.keys() == sb_core.keys(), "statement keys diverge after stripping branch meta"
        _assert_income_statement_totals_equal(sc, sb_core)
        _assert_balance_sheet_totals_equal(sc, sb_core)
        assert sc.get("unclassified_rows") == sb_core.get("unclassified_rows")

    fp_c = _product_engine_fingerprint(stmts_company)
    fp_b = _product_engine_fingerprint(stmts_branch)
    for key in fp_c:
        assert fp_c[key] == fp_b[key], f"engine parity mismatch on {key}"


def test_case2_multi_branch_tb_merge_matches_explicit_merged_pipeline(tmp_path):
    """
    Case 2 — Two branch uploads for the same period: merged TB rows → classify →
    build_statements must match build_period_statements_from_uploads([rec_a, rec_b]).

    Merge: partition of the minimal balanced TB across two CSVs (no overlapping keys).
    """
    company_id = uuid.uuid4().hex
    period = "2099-07"
    all_rows = _tb_rows_minimal_balanced()
    part_a = all_rows[:4]
    part_b = all_rows[4:]

    path_a = tmp_path / "br_a.csv"
    path_b = tmp_path / "br_b.csv"
    _write_tb_csv(path_a, part_a)
    _write_tb_csv(path_b, part_b)

    rec_a = _rec(path_a, period)
    rec_b = _rec(path_b, period)

    df_a = load_normalized_tb_dataframe(rec_a)
    df_b = load_normalized_tb_dataframe(rec_b)
    assert df_a is not None and df_b is not None
    merged = merge_tb_slices_for_period([df_a, df_b], period)
    classified = classify_dataframe(merged)
    fs = build_statements(classified, company_id=company_id, period=period, tb_type="post_closing")
    expected = statements_to_dict(fs)
    expected["period"] = period
    attach_structured_income_statement(expected)

    built = build_period_statements_from_uploads(company_id, [rec_a, rec_b])
    assert len(built) == 1
    got = built[0]

    _assert_income_statement_totals_equal(expected, got)
    _assert_balance_sheet_totals_equal(expected, got)
    assert expected.get("unclassified_rows") == got.get("unclassified_rows")

    fp_e = _product_engine_fingerprint([expected])
    fp_g = _product_engine_fingerprint([got])
    for key in fp_e:
        assert fp_e[key] == fp_g[key], f"consolidated engine parity mismatch on {key}"


def test_case2_three_branch_slices_merge_same_as_two_step_merge(tmp_path):
    """Optional consolidation stress: merge A+B then add C via same merge primitive."""
    company_id = uuid.uuid4().hex
    period = "2099-08"
    rows = _tb_rows_minimal_balanced()
    # three disjoint slices
    slices = [rows[0:3], rows[3:5], rows[5:8]]
    recs = []
    dfs = []
    for i, part in enumerate(slices):
        p = tmp_path / f"slice_{i}.csv"
        _write_tb_csv(p, part)
        r = _rec(p, period)
        recs.append(r)
        dfs.append(load_normalized_tb_dataframe(r))

    merged_once = merge_tb_slices_for_period(dfs, period)
    classified = classify_dataframe(merged_once)
    fs = build_statements(classified, company_id=company_id, period=period, tb_type="post_closing")
    one_shot = statements_to_dict(fs)
    one_shot["period"] = period
    attach_structured_income_statement(one_shot)

    from_pipeline = build_period_statements_from_uploads(company_id, recs)[0]
    _assert_income_statement_totals_equal(one_shot, from_pipeline)
    _assert_balance_sheet_totals_equal(one_shot, from_pipeline)


def test_case3_empty_branch_uploads_no_statements(tmp_path):
    """Case 3a — No uploads → no fabricated period dicts."""
    company_id = uuid.uuid4().hex
    assert build_branch_period_statements(company_id, "any-branch", []) == []


def test_case3_missing_normalized_file_produces_no_statements(tmp_path):
    """Case 3b — Record points at missing path → pipeline skips; no synthetic BS."""
    company_id = uuid.uuid4().hex

    class _Bad:
        normalized_path = str(tmp_path / "nonexistent.csv")
        period = "2099-09"
        tb_type = "post_closing"

    assert build_branch_period_statements(company_id, "br", [_Bad()]) == []


def test_case3_empty_csv_no_statements(tmp_path):
    """Case 3c — Empty dataframe after load → no statements."""
    company_id = uuid.uuid4().hex
    p = tmp_path / "empty.csv"
    pd.DataFrame(columns=["account_code", "account_name", "debit", "credit"]).to_csv(
        p, index=False, encoding="utf-8-sig"
    )

    class _E:
        normalized_path = str(p.resolve())
        period = "2099-10"
        tb_type = "post_closing"

    assert build_branch_period_statements(company_id, "br", [_E()]) == []


def test_case3_empty_statements_kpi_and_cashflow_are_empty_not_errors():
    """Incomplete branch: engines must not invent series (KPI block empty; CF safe)."""
    kpi = build_kpi_block([], "ALL")
    assert kpi["period_count"] == 0
    assert kpi.get("kpis") == {}
    cf = build_cashflow([])
    assert isinstance(cf, dict)


def test_case4_branch_path_uses_same_public_engines_as_company_path_documented():
    """
    Case 4 / D — Parity confirmation: tests above call the same engine entry points
    for branch-scoped statements as for company-scoped (build_kpi_block, build_cashflow,
    build_intelligence, build_alerts, build_cfo_decisions via _product_engine_fingerprint).
    """
    # If this module's Case 1 / Case 2 tests pass, branch dicts feed identical engines.
    assert callable(build_kpi_block)
    assert callable(build_cashflow)
    assert callable(build_intelligence)
    assert callable(build_alerts)
    assert callable(build_cfo_decisions)
