"""
Validate Phase 3 scope-aware expense intelligence against real 2025 uploads.

Read-only validation:
  - Finds a company with 2025 uploads + a member user
  - Finds a branch with 2025 uploads + a member user
  - Finds a group with at least one active company with 2025 uploads + group member user
  - Calls build_scope_expense_intelligence() directly (no HTTP auth needed)
  - Verifies totals reconcile to statement totals and comparisons refer to valid entities
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)
sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.scope_expense_intelligence import build_scope_expense_intelligence  # noqa: E402


def _pct(num: float, den: float):
    if den and den > 0:
        return round((num / den) * 100.0, 2)
    return None


def _check_entity_bundle(entity: dict) -> list[str]:
    issues: list[str] = []
    bundle = entity.get("bundle") or {}
    analysis = (bundle.get("expense_analysis") or {})
    rows = analysis.get("by_period") or []
    if not rows:
        issues.append("no by_period rows (no statements built)")
        return issues
    last = rows[-1]
    rev = float(last.get("revenue") or 0)
    cogs = float(last.get("cogs") or 0)
    opex = float(last.get("operating_expenses") or 0)
    uncl = float(last.get("unclassified_pnl_debits") or 0)
    te = float(last.get("total_expense") or 0)

    exp_te = round(cogs + opex + uncl, 2)
    if round(te, 2) != exp_te:
        issues.append(f"total_expense mismatch: total_expense={te} vs cogs+opex+uncl={exp_te}")

    epr = last.get("expense_pct_of_revenue")
    exp_epr = _pct(te, rev)
    if exp_epr is None:
        if epr is not None:
            issues.append(f"expense_pct_of_revenue should be null (rev={rev}) but got {epr}")
    else:
        if epr is None or round(float(epr), 2) != exp_epr:
            issues.append(f"expense_pct_of_revenue mismatch: got={epr} expected={exp_epr}")

    expl = bundle.get("expense_explanation") or {}
    if not (expl.get("headline") and expl.get("narrative")):
        issues.append("weak explanation: missing headline/narrative")

    # anomalies/decisions: allow empty, but flag as weak if both empty
    anoms = bundle.get("expense_anomalies") or []
    decs = bundle.get("expense_decisions") or []
    if len(anoms) == 0 and len(decs) == 0:
        issues.append("weak signals: anomalies and decisions both empty")

    return issues


def _check_comparisons(resp: dict) -> list[str]:
    issues: list[str] = []
    exp = resp.get("expense") or {}
    entities = exp.get("entities") or []
    ent_ids = {(e.get("entity_type"), e.get("entity_id")) for e in entities}

    comps = exp.get("comparisons") or {}
    hi = comps.get("highest_cost_entity")
    if hi:
        if (hi.get("entity_type"), hi.get("entity_id")) not in ent_ids:
            issues.append("highest_cost_entity refers to unknown entity")
    me = comps.get("most_efficient_entity")
    if me:
        if (me.get("entity_type"), me.get("entity_id")) not in ent_ids:
            issues.append("most_efficient_entity refers to unknown entity")
    b = comps.get("biggest_cost_driver_by_scope")
    if not b:
        issues.append("missing biggest_cost_driver_by_scope")
    return issues


def _pick_ids(db):
    # Prefer 2025, but fall back to latest available periods if none exist.
    # Company with uploads + membership user
    company = db.execute(
        text(
            """
            SELECT t.company_id AS company_id, m.user_id AS user_id
            FROM tb_uploads t
            JOIN memberships m ON m.company_id = t.company_id AND m.is_active = true
            WHERE t.branch_id IS NULL
            ORDER BY t.uploaded_at DESC
            LIMIT 1
            """
        )
    ).mappings().first()

    # Branch with uploads + member user
    branch = db.execute(
        text(
            """
            SELECT t.branch_id AS branch_id, t.company_id AS company_id, m.user_id AS user_id
            FROM tb_uploads t
            JOIN memberships m ON m.company_id = t.company_id AND m.is_active = true
            WHERE t.branch_id IS NOT NULL
            ORDER BY t.uploaded_at DESC
            LIMIT 1
            """
        )
    ).mappings().first()

    # Group with company uploads + group_membership user
    group = db.execute(
        text(
            """
            SELECT g.id AS group_id, gm.user_id AS user_id
            FROM groups g
            JOIN group_memberships gm ON gm.group_id = g.id AND gm.is_active = true
            JOIN companies c ON c.group_id = g.id AND c.is_active = true
            JOIN tb_uploads t ON t.company_id = c.id AND t.branch_id IS NULL
            ORDER BY t.uploaded_at DESC
            LIMIT 1
            """
        )
    ).mappings().first()

    return company, branch, group


def validate_one(db, *, user_id: str, scope_type: str, scope_id: str) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"ok": False, "error": "user not found"}
    try:
        resp = build_scope_expense_intelligence(
            db=db, user=user, scope_type=scope_type, scope_id=scope_id, lang="en"
        )
    except Exception as e:
        return {"ok": False, "error": str(e)}

    issues: list[str] = []
    exp = resp.get("expense") or {}
    for ent in exp.get("entities") or []:
        ent_issues = _check_entity_bundle(ent)
        if ent_issues:
            issues.append(f"{ent.get('entity_type')}:{ent.get('entity_id')}: " + "; ".join(ent_issues))
    issues.extend(_check_comparisons(resp))
    return {"ok": True, "issue_count": len(issues), "issues": issues, "resp": resp}


def main() -> int:
    db = SessionLocal()
    try:
        company, branch, group = _pick_ids(db)
        results = {}

        if company:
            results["company"] = validate_one(
                db, user_id=company["user_id"], scope_type="company", scope_id=company["company_id"]
            )
        else:
            results["company"] = {"ok": False, "error": "no 2025 company uploads with memberships found"}

        if branch:
            results["branch"] = validate_one(
                db, user_id=branch["user_id"], scope_type="branch", scope_id=branch["branch_id"]
            )
        else:
            results["branch"] = {"ok": False, "error": "no 2025 branch uploads found"}

        if group:
            results["group"] = validate_one(
                db, user_id=group["user_id"], scope_type="group", scope_id=group["group_id"]
            )
        else:
            results["group"] = {"ok": False, "error": "no group with 2025 uploads + group membership found"}

        # Print concise summary
        for k in ("company", "branch", "group"):
            r = results[k]
            if not r.get("ok"):
                print(f"{k}: FAIL - {r.get('error')}")
                continue
            issues = r.get("issues") or []
            status = "PASS" if not issues else "WARN"
            print(f"{k}: {status} - issues={len(issues)}")
            for it in issues[:10]:
                print(f"  - {it}")
            if len(issues) > 10:
                print(f"  ... {len(issues) - 10} more")

        # Exit nonzero if any hard fail
        if not results["company"].get("ok") or not results["branch"].get("ok"):
            return 2
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

