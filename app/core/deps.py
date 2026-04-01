"""
app/core/deps.py — Tenant access control dependency.

ENFORCEMENT MODE (controlled via config):
  - ENFORCE_MEMBERSHIP = False (default):
      Unauthenticated requests pass through.
      Authenticated requests still validate membership.
      Use this while frontend has no auth yet.

  - ENFORCE_MEMBERSHIP = True:
      All requests require a valid Bearer token + active membership.
      Enable this once frontend auth is integrated.
"""
from typing import Optional

from fastapi import Depends, HTTPException, Path, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.company import Company
from app.models.membership import Membership


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
        from jose import JWTError, jwt
        from app.core.config import settings
        payload = jwt.decode(token, settings.JWT_SECRET_KEY,
                             algorithms=["HS256"])
        user_id: Optional[str] = payload.get("sub")
        if not user_id:
            return None
    except Exception:
        return None

    from app.models.user import User
    return db.query(User).filter(User.id == user_id, User.is_active == True).first()  # noqa: E712


def require_company_access(
    company_id: str = Path(...),
    request: Request = None,
    db: Session = Depends(get_db),
) -> Company:
    """
    Verify company exists and enforce membership when a Bearer token is present.

    - No token supplied  → pass through (frontend pre-auth phase)
    - Token supplied     → must have active membership or get 403
    """
    from app.core.config import settings

    company = db.query(Company).filter(
        Company.id == company_id,
        Company.is_active == True,  # noqa: E712
    ).first()

    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    # Extract token from Authorization header if present
    auth_header: Optional[str] = request.headers.get("Authorization") if request else None
    token: Optional[str] = None
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()

    # Authentication is ALWAYS required — no bypass
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    # Token present → validate it and check membership
    from jose import JWTError, jwt
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        user_id: Optional[str] = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    membership = db.query(Membership).filter(
        Membership.user_id == user_id,
        Membership.company_id == company_id,
        Membership.is_active == True,  # noqa: E712
    ).first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: no active membership for this company",
        )

    return company


# ── FIX-S1: Role enforcement helper ──────────────────────────────────────────
from app.models.membership import Membership


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
        request: Request = None,
        db: Session = Depends(get_db),
    ):
        auth_header: Optional[str] = request.headers.get("Authorization") if request else None
        if not auth_header or not auth_header.lower().startswith("bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Authentication required")
        token = auth_header[7:].strip()
        try:
            from jose import JWTError, jwt
            from app.core.config import settings
            payload = jwt.decode(token, settings.JWT_SECRET_KEY,
                                 algorithms=["HS256"])
            user_id: Optional[str] = payload.get("sub")
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Invalid token")

        mem = db.query(Membership).filter(
            Membership.user_id    == user_id,
            Membership.company_id == company_id,
            Membership.is_active  == True,  # noqa: E712
        ).first()

        if not mem:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="No membership for this company")
        if mem.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{mem.role}' not permitted. Required: {list(allowed_roles)}",
            )
        return mem

    return _check
