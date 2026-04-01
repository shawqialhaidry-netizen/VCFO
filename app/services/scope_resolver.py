"""
Financial scope resolution (Phase 2).

Resolves a (scope_type, scope_id) into a stable ResolvedScope for future
unified financial APIs. Does not call statement/analysis/decision engines.

Rules (locked):
- Group: direct group_memberships only; inactive/missing group → 404;
  no membership → 403; active companies in group only; empty group → valid
  empty company_ids.
- Company / branch: same membership gates as existing company-scoped APIs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_active_membership
from app.core.security import get_current_user
from app.models.branch import Branch
from app.models.company import Company
from app.models.group import Group, GroupMembership
from app.models.user import User

ScopeTypeLiteral = Literal["group", "company", "branch"]
_SCOPE_TYPES = frozenset({"group", "company", "branch"})

GROUP_NOT_FOUND_DETAIL = "Group not found"
GROUP_MEMBERSHIP_DENIED_DETAIL = "Access denied: no active membership for this group"


@dataclass(frozen=True)
class ResolvedScope:
    """Normalized financial scope after access checks."""

    scope_type: ScopeTypeLiteral
    scope_id: str
    group_id: Optional[str]
    company_ids: tuple[str, ...]
    branch_id: Optional[str]


def resolve_financial_scope(
    db: Session,
    user: User,
    scope_type: str,
    scope_id: str,
) -> ResolvedScope:
    """
    Resolve and authorize (scope_type, scope_id) for the given user.

    Raises HTTPException: 404 (missing/inactive group or company), 403 (no
    membership), 422 (invalid scope_type).
    """
    st = (scope_type or "").strip().lower()
    sid = (scope_id or "").strip()
    if st not in _SCOPE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid scope_type",
        )
    if not sid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="scope_id is required",
        )

    if st == "group":
        return _resolve_group(db, user, sid)
    if st == "company":
        return _resolve_company(db, user, sid)
    return _resolve_branch(db, user, sid)


def _active_group_membership(
    db: Session,
    user_id: str,
    group_id: str,
) -> Optional[GroupMembership]:
    return (
        db.query(GroupMembership)
        .filter(
            GroupMembership.user_id == user_id,
            GroupMembership.group_id == group_id,
            GroupMembership.is_active == True,  # noqa: E712
        )
        .first()
    )


def _resolve_group(db: Session, user: User, group_id: str) -> ResolvedScope:
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group or not group.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=GROUP_NOT_FOUND_DETAIL)

    if not _active_group_membership(db, user.id, group_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=GROUP_MEMBERSHIP_DENIED_DETAIL,
        )

    rows = (
        db.query(Company.id)
        .filter(
            Company.group_id == group_id,
            Company.is_active == True,  # noqa: E712
        )
        .order_by(Company.id)
        .all()
    )
    company_ids = tuple(r[0] for r in rows)
    return ResolvedScope(
        scope_type="group",
        scope_id=group_id,
        group_id=group_id,
        company_ids=company_ids,
        branch_id=None,
    )


def _resolve_company(db: Session, user: User, company_id: str) -> ResolvedScope:
    company = (
        db.query(Company)
        .filter(
            Company.id == company_id,
            Company.is_active == True,  # noqa: E712
        )
        .first()
    )
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )
    require_active_membership(db, user.id, company_id)
    return ResolvedScope(
        scope_type="company",
        scope_id=company_id,
        group_id=company.group_id,
        company_ids=(company_id,),
        branch_id=None,
    )


def _resolve_branch(db: Session, user: User, branch_id: str) -> ResolvedScope:
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found",
        )

    company = (
        db.query(Company)
        .filter(
            Company.id == branch.company_id,
            Company.is_active == True,  # noqa: E712
        )
        .first()
    )
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    require_active_membership(db, user.id, branch.company_id)
    return ResolvedScope(
        scope_type="branch",
        scope_id=branch_id,
        group_id=company.group_id,
        company_ids=(branch.company_id,),
        branch_id=branch_id,
    )


def get_resolved_financial_scope(
    scope_type: str = Query(..., description="group | company | branch"),
    scope_id: str = Query(..., description="UUID of the scope entity"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResolvedScope:
    """
    FastAPI dependency for future routes: query params scope_type + scope_id.

    Usage: Depends(get_resolved_financial_scope)
    """
    return resolve_financial_scope(db, current_user, scope_type, scope_id)
