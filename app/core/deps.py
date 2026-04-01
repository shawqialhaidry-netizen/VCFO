"""
app/core/deps.py — Multi-tenant access control (membership-based).

Every company-scoped operation must verify an active row in `memberships`.
There is no superuser / email bypass: access requires an explicit membership.

FastAPI dependency:
  get_current_company_access (= require_company_access alias)
    → Validates JWT via get_current_user, loads Company, requires membership.

Imperative helper (branch routes, body company_id, uploads, etc.):
  require_active_membership(db, user_id, company_id) → Membership
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Path, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.company import Company
from app.models.membership import Membership
from app.models.user import User

MEMBERSHIP_DENIED_DETAIL = "Access denied: no active membership for this company"


def active_membership(
    db: Session,
    user_id: str,
    company_id: str,
) -> Optional[Membership]:
    """Return active membership or None. Does not raise."""
    return (
        db.query(Membership)
        .filter(
            Membership.user_id == user_id,
            Membership.company_id == company_id,
            Membership.is_active == True,  # noqa: E712
        )
        .first()
    )


def require_active_membership(
    db: Session,
    user_id: str,
    company_id: str,
) -> Membership:
    """
    Require an active membership for (user_id, company_id).
    Used by branch helpers, JSON-body company_id, upload checks, etc.
    """
    m = active_membership(db, user_id, company_id)
    if not m:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=MEMBERSHIP_DENIED_DETAIL,
        )
    return m


def get_current_company_access(
    company_id: str = Path(..., description="Company UUID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Company:
    """
    Production gate for path parameters `{company_id}`:
      1) Authenticated user (Bearer JWT)
      2) Company exists and is active
      3) User has an active membership for that company

    No implicit access: is_superuser alone does not grant company access.
    """
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
    require_active_membership(db, current_user.id, company_id)
    return company


# Backward-compatible name (analysis, statements, and other routers)
require_company_access = get_current_company_access


def require_role(*allowed_roles: str):
    """
    Returns a FastAPI dependency that checks the current user has one of
    the allowed roles for the company in the request path.

    Usage:
        @router.delete("/{company_id}/something")
        def handler(..., _role = Depends(require_role("owner"))):
            ...
    """

    def _check(
        company_id: str = Path(...),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        mem = require_active_membership(db, current_user.id, company_id)
        if mem.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{mem.role}' not permitted. Required: {list(allowed_roles)}",
            )
        return mem

    return _check


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Returns the authenticated User if a valid Bearer token is present.
    Returns None if no token or token is invalid — never raises.
    Used by endpoints that work for both authenticated and anonymous requests.
    """
    auth_header: Optional[str] = request.headers.get("Authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header[7:].strip()
    if not token:
        return None
    try:
        from jose import jwt
        from app.core.config import settings

        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=["HS256"],
        )
        user_id: Optional[str] = payload.get("sub")
        if not user_id:
            return None
    except Exception:
        return None

    from app.models.user import User as UserModel

    return (
        db.query(UserModel)
        .filter(UserModel.id == user_id, UserModel.is_active == True)  # noqa: E712
        .first()
    )
