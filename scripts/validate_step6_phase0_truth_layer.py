#!/usr/bin/env python3
"""
STEP 6 — Phase 0: validate structured truth layer (no UI).

Prints:
  - structured_income_statement (latest period)
  - structured_profit_bridge
  - structured_profit_story

Checks:
  - structured net_profit vs TB/statement_engine published income_statement.net_profit
  - bridge line deltas vs structured_income_statement_variance (must match by construction)
  - story.summary_type vs classification implied by bridge interpretation + latest NM (same rules as
    structured_profit_story.build_structured_profit_story_from_analysis)

Usage:
  python scripts/validate_step6_phase0_truth_layer.py --synthetic
  python scripts/validate_step6_phase0_truth_layer.py --company-id <uuid>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=False)
except ImportError:
    pass
sys.path.insert(0, str(ROOT))


def _j(obj: Any) -> str:
    return json.dumps(obj, indent=2, default=str, ensure_ascii=False)


def _nm_float(latest: dict | None) -> Optional[float]:
    if not latest or not isinstance(latest, dict):
        return None
    prof = latest.get("profitability") or {}
    nm = prof.get("net_margin_pct")
    if nm is None:
        return None
    try:
        return float(nm)
    except (TypeError, ValueError):
        return None


def expected_summary_type_from_truth(
    *,
    bridge_meta_completeness: str | None,
    interp: dict[str, Any],
    nm_f: Optional[float],
) -> Optional[str]:
    """
    Mirror app.services.structured_profit_story.build_structured_profit_story_from_analysis
    classification only (must stay in sync with that module).
    """
    if (bridge_meta_completeness or "") == "none":
        return None

    paradox = interp.get("paradox_flags") or {}
    net_r = interp.get("net_result")
    pdrv = interp.get("primary_driver")

    if paradox.get("revenue_up_profit_down"):
        return "paradox_growth_loss"
    if net_r == "profit_down" and pdrv == "opex":
        return "cost_pressure"
    if net_r == "profit_down" and pdrv == "cogs":
        return "margin_compression"
    if net_r == "profit_up" and pdrv == "revenue":
        if nm_f is not None and nm_f < 10.0:
            return "profit_recovery"
        return "healthy_growth"
    return "mixed"


def check_np_published_vs_structured(latest_stmt: dict) -> tuple[list[str], dict[str, Any]]:
    issues: list[str] = []
    is_ = latest_stmt.get("income_statement") or {}
    published = is_.get("net_profit")
    sis = latest_stmt.get("structured_income_statement") or {}
    struct_np = sis.get("net_profit") if isinstance(sis, dict) else None
    meta = latest_stmt.get("structured_income_statement_meta") or {}

    detail = {
        "published_net_profit": published,
        "structured_net_profit": struct_np,
        "structured_meta_net_profit_rule": meta.get("net_profit_rule"),
        "structured_meta_completeness": meta.get("completeness"),
    }

    if published is None and struct_np is None:
        return issues, detail
    if published is None or struct_np is None:
        issues.append(
            "net_profit: one of (published, structured) is null — "
            f"published={published!r} structured={struct_np!r}"
        )
        return issues, detail
    try:
        p = float(published)
        s = float(struct_np)
    except (TypeError, ValueError):
        issues.append("net_profit: non-numeric published or structured value")
        return issues, detail

    if round(p - s, 2) != 0.0:
        issues.append(
            f"net_profit: published TB/statement_engine ({p}) != structured ({s}) — "
            "see structured_income_statement_meta.net_profit_rule (formula vs published_only path)"
        )
    return issues, detail


def check_bridge_matches_variance(analysis: dict) -> tuple[list[str], dict[str, Any]]:
    issues: list[str] = []
    var = analysis.get("structured_income_statement_variance") or {}
    bridge = analysis.get("structured_profit_bridge") or {}

    mapping = [
        ("revenue_change", "revenue"),
        ("cogs_change", "cogs"),
        ("gross_profit_change", "gross_profit"),
        ("opex_change", "opex"),
        ("operating_profit_change", "operating_profit"),
        ("net_profit_change", "net_profit"),
    ]
    detail: dict[str, Any] = {}
    for bkey, vkey in mapping:
        b = (bridge.get(bkey) or {}) if isinstance(bridge, dict) else {}
        v = (var.get(vkey) or {}) if isinstance(var, dict) else {}
        bd, bp = b.get("delta"), b.get("delta_pct")
        vd, vp = v.get("delta"), v.get("delta_pct")
        detail[bkey] = {"bridge": {"delta": bd, "delta_pct": bp}, "variance": {"delta": vd, "delta_pct": vp}}
        if bd != vd:
            issues.append(
                f"bridge/{bkey}.delta ({bd!r}) != variance/{vkey}.delta ({vd!r}) — "
                "root: structured_profit_bridge copies from variance; bug or manual mutation"
            )
        if bp != vp:
            issues.append(
                f"bridge/{bkey}.delta_pct ({bp!r}) != variance/{vkey}.delta_pct ({vp!r})"
            )
    return issues, detail


def check_story_vs_interpretation(analysis: dict) -> tuple[list[str], dict[str, Any]]:
    issues: list[str] = []
    story = analysis.get("structured_profit_story") or {}
    interp = analysis.get("structured_profit_bridge_interpretation") or {}
    bmeta = analysis.get("structured_profit_bridge_meta") or {}
    actual = story.get("summary_type")
    nm_f = _nm_float(analysis.get("latest"))
    expected = expected_summary_type_from_truth(
        bridge_meta_completeness=bmeta.get("completeness"),
        interp=interp if isinstance(interp, dict) else {},
        nm_f=nm_f,
    )

    detail = {
        "actual_summary_type": actual,
        "expected_summary_type": expected,
        "bridge_interpretation": interp,
        "latest_net_margin_pct_for_story": nm_f,
        "bridge_meta_completeness": bmeta.get("completeness"),
    }

    if expected != actual:
        issues.append(
            f"story.summary_type ({actual!r}) != expected from interpretation ({expected!r}) — "
            "root: structured_profit_story classification drift vs validator copy, or story built from "
            "different analysis dict than current bridge/interpretation"
        )
    return issues, detail


def run_validation(analysis: dict, windowed: list[dict], label: str) -> int:
    latest = windowed[-1] if windowed else {}
    sis = latest.get("structured_income_statement")
    bridge = analysis.get("structured_profit_bridge")
    story = analysis.get("structured_profit_story")

    print(f"\n{'=' * 72}\nTRUTH LAYER DUMP — {label}\n{'=' * 72}")
    print("\n--- structured_income_statement (latest period) ---\n")
    print(_j(sis))
    print("\n--- structured_profit_bridge ---\n")
    print(_j(bridge))
    print("\n--- structured_profit_story ---\n")
    print(_j(story))

    all_issues: list[str] = []

    np_issues, np_detail = check_np_published_vs_structured(latest)
    print("\n--- check: published net_profit vs structured ---\n")
    print(_j(np_detail))
    all_issues.extend(np_issues)

    br_issues, br_detail = check_bridge_matches_variance(analysis)
    print("\n--- check: bridge deltas vs variance ---\n")
    print(_j(br_detail))
    all_issues.extend(br_issues)

    st_issues, st_detail = check_story_vs_interpretation(analysis)
    print("\n--- check: story.summary_type vs interpretation rules ---\n")
    print(_j(st_detail))
    all_issues.extend(st_issues)

    print(f"\n{'=' * 72}\nCONSISTENCY RESULT — {label}\n{'=' * 72}")
    if not all_issues:
        print("OK — no inconsistencies detected for these checks.")
        return 0

    print("MISMATCHES:")
    for i, msg in enumerate(all_issues, 1):
        print(f"  {i}. {msg}")
    print("\nTrace hints:")
    print("  - net_profit mismatch → app.services.structured_income_statement._build_parts "
          "(net_profit_rule: operating_only | operating_minus_tax | published_only)")
    print("  - bridge vs variance → app.services.structured_profit_bridge._change_block "
          "(should mirror variance lines)")
    print("  - story vs interp → app.services.structured_profit_story "
          "(paradox > profit_down branch > profit_up+revenue+nm threshold)")
    return 1


def synthetic_window() -> list[dict]:
    from tests.test_structured_income_statement_variance import _stmt

    a = _stmt("2026-01", 1000, 400, 600, 200, 50, 50, 300)
    b = _stmt("2026-02", 1100, 400, 700, 200, 50, 50, 400)
    return [a, b]


def load_window_from_db(company_id: str) -> list[dict]:
    from app.api.analysis import _build_period_statements
    from app.core.database import SessionLocal
    from app.models.company import Company
    from app.models.trial_balance import TrialBalanceUpload
    from app.services.time_intelligence import filter_periods

    db = SessionLocal()
    try:
        co = db.query(Company).filter(Company.id == company_id).first()
        if not co:
            raise SystemExit(f"Company not found: {company_id}")
        uploads = (
            db.query(TrialBalanceUpload)
            .filter(
                TrialBalanceUpload.company_id == company_id,
                TrialBalanceUpload.status == "ok",
                TrialBalanceUpload.branch_id.is_(None),
            )
            .order_by(TrialBalanceUpload.uploaded_at.asc())
            .all()
        )
        if not uploads:
            raise SystemExit(f"No OK uploads for company {company_id}")
        stmts = _build_period_statements(company_id, uploads)
        if len(stmts) < 2:
            raise SystemExit(
                f"Need at least 2 periods for bridge/variance; got {len(stmts)}. "
                "Use --synthetic for two-period fixture."
            )
        windowed = filter_periods(stmts, "ALL") or stmts
        return windowed
    finally:
        db.close()


def main() -> int:
    p = argparse.ArgumentParser(description="STEP6 Phase0 truth layer validation")
    p.add_argument("--synthetic", action="store_true", help="Use two-period test fixture")
    p.add_argument("--company-id", type=str, default="", help="Company UUID with 2+ periods")
    args = p.parse_args()

    from app.services.analysis_engine import run_analysis

    if args.synthetic:
        windowed = synthetic_window()
        analysis = run_analysis(windowed)
        return run_validation(analysis, windowed, label="SYNTHETIC (_stmt fixture)")

    if args.company_id:
        windowed = load_window_from_db(args.company_id.strip())
        analysis = run_analysis(windowed)
        return run_validation(analysis, windowed, label=f"DB company {args.company_id}")

    print(
        "Provide --synthetic or --company-id <uuid>.\n"
        "Example: python scripts/validate_step6_phase0_truth_layer.py --synthetic"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
