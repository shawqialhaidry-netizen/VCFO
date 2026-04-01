from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.membership import Membership
from app.models.user import User
from app.models.company import Company

router = APIRouter(prefix="/companies", tags=["companies"])


def _company_with_trial(company) -> dict:
    """Serialize company with computed trial_days_left.
    trial_days_left: integer days remaining, 0 if expired, None if not trial or no end date.
    """
    from datetime import timezone
    d = {
        "id":             company.id,
        "name":           company.name,
        "name_ar":        company.name_ar,
        "industry":       company.industry,
        "currency":       company.currency,
        "is_active":      company.is_active,
        "plan":           getattr(company, "plan", "trial") or "trial",
        "trial_ends_at":  getattr(company, "trial_ends_at", None),
        "created_at":     company.created_at,
    }
    ends_at = d["trial_ends_at"]
    if d["plan"] == "trial" and ends_at is not None:
        now = datetime.utcnow()
        delta = (ends_at - now).days
        d["trial_days_left"] = max(0, delta)
    else:
        d["trial_days_left"] = None
    return d


# ── Schemas ──────────────────────────────────────────────────────────────────

class CompanyCreate(BaseModel):
    name: str
    name_ar: Optional[str] = None
    industry: Optional[str] = None
    currency: str = "USD"


class CompanyResponse(BaseModel):
    id: str
    name: str
    name_ar: Optional[str]
    industry: Optional[str]
    currency: str
    is_active: bool
    plan: str = "trial"
    trial_ends_at: Optional[datetime] = None
    trial_days_left: Optional[int] = None   # computed, not stored
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def create_company(
    payload:      CompanyCreate,
    db:           Session = Depends(get_db),
    current_user = Depends(get_current_user),  # FIX-S1: require auth
):
    company = Company(**payload.model_dump())
    db.add(company)
    db.flush()  # get company.id before commit
    # FIX-S1: auto-create owner membership so user can see their company
    mem = Membership(
        user_id    = current_user.id,
        company_id = company.id,
        role       = "owner",
        is_active  = True,
    )
    db.add(mem)
    db.commit()
    db.refresh(company)
    return company


@router.get("", response_model=list[CompanyResponse])
def list_companies(
    request: Request,
    db: Session = Depends(get_db),
):
    from app.core.config import settings
    from jose import JWTError, jwt

    auth_header = request.headers.get("Authorization", "")
    user_id = None
    if auth_header.lower().startswith("bearer "):
        try:
            payload = jwt.decode(
                auth_header[7:], settings.JWT_SECRET_KEY,
                algorithms=["HS256"]
            )
            user_id = payload.get("sub")
        except JWTError:
            pass

    if not user_id:
        return []

    allowed = [
        m.company_id for m in
        db.query(Membership).filter(
            Membership.user_id == user_id,
            Membership.is_active == True,  # noqa: E712
        ).all()
    ]
    companies = db.query(Company).filter(
        Company.id.in_(allowed),
        Company.is_active == True,  # noqa: E712
    ).all()
    return [_company_with_trial(co) for co in companies]


@router.get("/{company_id}", response_model=CompanyResponse)
def get_company(
    company_id:   str,
    db:           Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    # Verify caller has membership
    mem = db.query(Membership).filter(
        Membership.user_id    == current_user.id,
        Membership.company_id == company_id,
        Membership.is_active  == True,  # noqa: E712
    ).first()
    if not mem:
        raise HTTPException(status_code=403, detail="Access denied")
    return _company_with_trial(company)


# ── Membership management ─────────────────────────────────────────────────────

VALID_ROLES = {"owner", "analyst", "viewer"}


class MembershipCreate(BaseModel):
    user_email: str
    role: str = "analyst"


class MembershipResponse(BaseModel):
    id:         str
    user_id:    str
    company_id: str
    role:       str
    is_active:  bool
    created_at: datetime
    user_email: str | None = None
    user_name:  str | None = None

    model_config = {"from_attributes": True}


@router.get("/{company_id}/members", response_model=list[MembershipResponse])
def list_members(
    company_id:   str,
    db:           Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """List all members of a company. Requires membership."""
    mem_self = db.query(Membership).filter(
        Membership.user_id    == current_user.id,
        Membership.company_id == company_id,
        Membership.is_active  == True,  # noqa: E712
    ).first()
    if not mem_self:
        raise HTTPException(status_code=403, detail="Access denied")

    members = db.query(Membership).filter(
        Membership.company_id == company_id,
        Membership.is_active  == True,  # noqa: E712
    ).all()

    result = []
    for m in members:
        user = db.query(User).filter(User.id == m.user_id).first()
        result.append(MembershipResponse(
            id=m.id, user_id=m.user_id, company_id=m.company_id,
            role=m.role, is_active=m.is_active, created_at=m.created_at,
            user_email=user.email if user else None,
            user_name=user.full_name if user else None,
        ))
    return result


@router.post("/{company_id}/members", response_model=MembershipResponse, status_code=201)
def add_member(
    company_id:   str,
    payload:      MembershipCreate,
    db:           Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """Invite a user to a company. Requires owner or analyst role."""
    mem_self = db.query(Membership).filter(
        Membership.user_id    == current_user.id,
        Membership.company_id == company_id,
        Membership.is_active  == True,  # noqa: E712
    ).first()
    if not mem_self or mem_self.role not in ("owner", "analyst"):
        raise HTTPException(status_code=403, detail="Only owners and analysts can invite members")

    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Valid: {sorted(VALID_ROLES)}")

    # Only owner can grant owner role
    if payload.role == "owner" and mem_self.role != "owner":
        raise HTTPException(status_code=403, detail="Only owners can grant owner role")

    target_user = db.query(User).filter(User.email == payload.user_email).first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"User '{payload.user_email}' not found")

    existing = db.query(Membership).filter(
        Membership.user_id    == target_user.id,
        Membership.company_id == company_id,
    ).first()
    if existing:
        if existing.is_active:
            raise HTTPException(status_code=409, detail="User already has access to this company")
        # Re-activate
        existing.is_active = True
        existing.role      = payload.role
        db.commit(); db.refresh(existing)
        return MembershipResponse(
            id=existing.id, user_id=existing.user_id, company_id=existing.company_id,
            role=existing.role, is_active=existing.is_active, created_at=existing.created_at,
            user_email=target_user.email, user_name=target_user.full_name,
        )

    mem = Membership(
        user_id    = target_user.id,
        company_id = company_id,
        role       = payload.role,
        is_active  = True,
    )
    db.add(mem); db.commit(); db.refresh(mem)
    return MembershipResponse(
        id=mem.id, user_id=mem.user_id, company_id=mem.company_id,
        role=mem.role, is_active=mem.is_active, created_at=mem.created_at,
        user_email=target_user.email, user_name=target_user.full_name,
    )


@router.patch("/{company_id}/members/{member_user_id}", response_model=MembershipResponse)
def update_member_role(
    company_id:      str,
    member_user_id:  str,
    payload:         MembershipCreate,
    db:              Session = Depends(get_db),
    current_user   = Depends(get_current_user),
):
    """Change a member's role. Requires owner."""
    mem_self = db.query(Membership).filter(
        Membership.user_id    == current_user.id,
        Membership.company_id == company_id,
        Membership.is_active  == True,  # noqa: E712
    ).first()
    if not mem_self or mem_self.role != "owner":
        raise HTTPException(status_code=403, detail="Only owners can change roles")

    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Valid: {sorted(VALID_ROLES)}")

    target_mem = db.query(Membership).filter(
        Membership.user_id    == member_user_id,
        Membership.company_id == company_id,
        Membership.is_active  == True,  # noqa: E712
    ).first()
    if not target_mem:
        raise HTTPException(status_code=404, detail="Member not found")

    target_mem.role = payload.role
    db.commit(); db.refresh(target_mem)
    user = db.query(User).filter(User.id == member_user_id).first()
    return MembershipResponse(
        id=target_mem.id, user_id=target_mem.user_id, company_id=target_mem.company_id,
        role=target_mem.role, is_active=target_mem.is_active, created_at=target_mem.created_at,
        user_email=user.email if user else None, user_name=user.full_name if user else None,
    )


@router.delete("/{company_id}/members/{member_user_id}", status_code=204)
def remove_member(
    company_id:      str,
    member_user_id:  str,
    db:              Session = Depends(get_db),
    current_user   = Depends(get_current_user),
):
    """Remove a member from a company. Owner required. Cannot remove last owner."""
    mem_self = db.query(Membership).filter(
        Membership.user_id    == current_user.id,
        Membership.company_id == company_id,
        Membership.is_active  == True,  # noqa: E712
    ).first()
    if not mem_self or mem_self.role != "owner":
        raise HTTPException(status_code=403, detail="Only owners can remove members")

    target_mem = db.query(Membership).filter(
        Membership.user_id    == member_user_id,
        Membership.company_id == company_id,
        Membership.is_active  == True,  # noqa: E712
    ).first()
    if not target_mem:
        raise HTTPException(status_code=404, detail="Member not found")

    # Guard: cannot remove the last owner
    if target_mem.role == "owner":
        owner_count = db.query(Membership).filter(
            Membership.company_id == company_id,
            Membership.role       == "owner",
            Membership.is_active  == True,  # noqa: E712
        ).count()
        if owner_count <= 1:
            raise HTTPException(status_code=409, detail="Cannot remove the last owner")

    target_mem.is_active = False
    db.commit()


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(
    company_id:   str,
    db:           Session = Depends(get_db),
    current_user = Depends(get_current_user),  # FIX-S1: require auth
):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    # FIX-S1: only owner can delete
    mem = db.query(Membership).filter(
        Membership.user_id    == current_user.id,
        Membership.company_id == company_id,
        Membership.is_active  == True,
    ).first()
    if not mem or mem.role != "owner":
        raise HTTPException(status_code=403, detail="Only company owner can delete")
    company.is_active = False
    db.commit()
