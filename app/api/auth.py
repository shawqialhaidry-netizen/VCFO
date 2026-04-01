from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str | None
    is_active: bool
    is_superuser: bool

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if len(body.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters",
        )
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    user = User(
        email=body.email,
        full_name=body.full_name,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    # Always run bcrypt verification to prevent timing-based user enumeration.
    # If user not found, verify against a dummy hash (constant-time).
    _DUMMY_HASH = "$2b$12$KIXnHrmjFnDqGCBuIBiUje5s4E1JOcVE0NMkjeQ5z9g1oXWsPOKPe"
    _hash_to_check = user.password_hash if user else _DUMMY_HASH
    _password_ok = verify_password(body.password, _hash_to_check)
    if not user or not _password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )
    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/me/memberships")
def my_memberships(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return all active company memberships for the current user.
    Used by frontend to know which companies the user can access and their role.

    Returns:
    [{ company_id, company_name, company_name_ar, role, currency }]
    """
    from app.models.membership import Membership
    from app.models.company import Company

    memberships = (
        db.query(Membership)
        .filter(
            Membership.user_id   == current_user.id,
            Membership.is_active == True,  # noqa: E712
        )
        .all()
    )
    result = []
    for m in memberships:
        co = db.query(Company).filter(
            Company.id == m.company_id,
            Company.is_active == True,  # noqa: E712
        ).first()
        if co:
            result.append({
                "membership_id": m.id,
                "company_id":    co.id,
                "company_name":  co.name,
                "company_name_ar": co.name_ar,
                "currency":      co.currency,
                "role":          m.role,
                "can_write":     m.role in ("owner", "analyst"),
                "can_manage":    m.role == "owner",
            })
    return result
