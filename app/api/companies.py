from datetime import datetime
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_company_access, require_active_membership
from app.core.security import get_current_user
from app.models.account_mapping_override import AccountMappingOverride
from app.models.membership import Membership
from app.models.company import Company
from app.models.trial_balance import TrialBalanceUpload
from app.models.user import User
from app.services.account_classifier import (
    build_classification_summary,
    classify_dataframe_for_company,
)

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


VALID_MAPPED_TYPES = {
    "assets",
    "liabilities",
    "equity",
    "revenue",
    "cogs",
    "expenses",
    "tax",
    "other",
}


class AccountMappingOverrideCreate(BaseModel):
    account_code: str
    account_name_hint: Optional[str] = None
    mapped_type: str
    reason: Optional[str] = None

    @field_validator("account_code")
    @classmethod
    def account_code_required(cls, v: str) -> str:
        if v is None or not str(v).strip():
            raise ValueError("account_code is required")
        return str(v).strip()

    @field_validator("mapped_type")
    @classmethod
    def mapped_type_required(cls, v: str) -> str:
        value = str(v or "").strip().lower()
        if not value:
            raise ValueError("mapped_type is required")
        if value not in VALID_MAPPED_TYPES:
            raise ValueError(f"mapped_type must be one of {sorted(VALID_MAPPED_TYPES)}")
        return value


class AccountMappingOverrideUpdate(BaseModel):
    account_name_hint: Optional[str] = None
    mapped_type: str
    reason: Optional[str] = None

    @field_validator("mapped_type")
    @classmethod
    def mapped_type_required(cls, v: str) -> str:
        value = str(v or "").strip().lower()
        if not value:
            raise ValueError("mapped_type is required")
        if value not in VALID_MAPPED_TYPES:
            raise ValueError(f"mapped_type must be one of {sorted(VALID_MAPPED_TYPES)}")
        return value


class AccountMappingOverrideResponse(BaseModel):
    id: str
    company_id: str
    account_code: str
    account_name_hint: Optional[str]
    mapped_type: str
    reason: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


def _load_classified_review_dataframe(record: TrialBalanceUpload) -> pd.DataFrame:
    if not getattr(record, "normalized_path", None):
        raise HTTPException(status_code=422, detail="No normalized classified data available for review")
    try:
        df = pd.read_csv(record.normalized_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Normalized classified data file not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not read normalized classified data: {exc}")

    required = {
        "account_code",
        "account_name",
        "debit",
        "credit",
    }
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Normalized classified data is missing required columns: {sorted(missing)}",
        )
    return df


def _resolve_review_upload(
    db: Session,
    company_id: str,
    upload_id: str | None = None,
) -> TrialBalanceUpload:
    if upload_id:
        record = (
            db.query(TrialBalanceUpload)
            .filter(
                TrialBalanceUpload.id == upload_id,
                TrialBalanceUpload.company_id == company_id,
                TrialBalanceUpload.status == "ok",
            )
            .first()
        )
        if not record:
            raise HTTPException(status_code=404, detail="Classified upload not found for this company")
        return record

    company_level = (
        db.query(TrialBalanceUpload)
        .filter(
            TrialBalanceUpload.company_id == company_id,
            TrialBalanceUpload.status == "ok",
            TrialBalanceUpload.branch_id.is_(None),
        )
        .order_by(TrialBalanceUpload.uploaded_at.desc())
        .first()
    )
    if company_level:
        return company_level

    record = (
        db.query(TrialBalanceUpload)
        .filter(
            TrialBalanceUpload.company_id == company_id,
            TrialBalanceUpload.status == "ok",
        )
        .order_by(TrialBalanceUpload.uploaded_at.desc())
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="No successful classified upload found for this company")
    return record


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
    company: Company = Depends(get_current_company_access),
):
    return _company_with_trial(company)


@router.get("/{company_id}/classification-review")
def get_classification_review(
    company_id: str,
    upload_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    require_active_membership(db, current_user.id, company_id)

    record = _resolve_review_upload(db, company_id, upload_id)
    df = _load_classified_review_dataframe(record)
    df = classify_dataframe_for_company(df, company_id, db)
    summary = build_classification_summary(df)

    summary_counts = {
        "classified_ratio": summary["classified_ratio"],
        "override_count": summary["qa_summary"]["override_count"],
        "rule_count": summary["qa_summary"]["rule_count"],
        "fallback_count": summary["qa_summary"]["fallback_count"],
        "low_confidence_count": summary["qa_summary"]["low_confidence_count"],
        "review_count": summary["qa_summary"]["review_count"],
        "low_confidence_threshold": summary["qa_summary"]["low_confidence_threshold"],
    }

    return {
        "company_id": company_id,
        "upload": {
            "upload_id": record.id,
            "period": record.period,
            "branch_id": getattr(record, "branch_id", None),
            "uploaded_at": record.uploaded_at.isoformat() if record.uploaded_at else None,
            "original_filename": record.original_filename,
            "format_detected": record.format_detected,
        },
        "summary_counts": summary_counts,
        "classification_source_breakdown": summary["classification_source_breakdown"],
        "accounts_needing_review": summary["review_accounts"],
        "fallback_accounts": summary["fallback_accounts"],
        "low_confidence_accounts": summary["low_confidence_accounts"],
        "override_accounts": summary["override_accounts"],
        "rule_accounts": summary["rule_accounts"],
    }


@router.get(
    "/{company_id}/account-mapping-overrides",
    response_model=list[AccountMappingOverrideResponse],
)
def list_account_mapping_overrides(
    company_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    require_active_membership(db, current_user.id, company_id)
    return (
        db.query(AccountMappingOverride)
        .filter(AccountMappingOverride.company_id == company_id)
        .order_by(AccountMappingOverride.account_code.asc(), AccountMappingOverride.created_at.asc())
        .all()
    )


@router.post(
    "/{company_id}/account-mapping-overrides",
    response_model=AccountMappingOverrideResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_account_mapping_override(
    company_id: str,
    payload: AccountMappingOverrideCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    mem = require_active_membership(db, current_user.id, company_id)
    if mem.role not in ("owner", "analyst"):
        raise HTTPException(status_code=403, detail="Viewer role cannot manage account mapping overrides")

    existing = (
        db.query(AccountMappingOverride)
        .filter(
            AccountMappingOverride.company_id == company_id,
            AccountMappingOverride.account_code == payload.account_code,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Override already exists for this account_code")

    record = AccountMappingOverride(
        company_id=company_id,
        account_code=payload.account_code,
        account_name_hint=payload.account_name_hint,
        mapped_type=payload.mapped_type,
        reason=payload.reason,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.put(
    "/{company_id}/account-mapping-overrides/{override_id}",
    response_model=AccountMappingOverrideResponse,
)
def update_account_mapping_override(
    company_id: str,
    override_id: str,
    payload: AccountMappingOverrideUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    mem = require_active_membership(db, current_user.id, company_id)
    if mem.role not in ("owner", "analyst"):
        raise HTTPException(status_code=403, detail="Viewer role cannot manage account mapping overrides")

    record = (
        db.query(AccountMappingOverride)
        .filter(
            AccountMappingOverride.id == override_id,
            AccountMappingOverride.company_id == company_id,
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Account mapping override not found")

    record.account_name_hint = payload.account_name_hint
    record.mapped_type = payload.mapped_type
    record.reason = payload.reason
    db.commit()
    db.refresh(record)
    return record


@router.delete(
    "/{company_id}/account-mapping-overrides/{override_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_account_mapping_override(
    company_id: str,
    override_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    mem = require_active_membership(db, current_user.id, company_id)
    if mem.role not in ("owner", "analyst"):
        raise HTTPException(status_code=403, detail="Viewer role cannot manage account mapping overrides")

    record = (
        db.query(AccountMappingOverride)
        .filter(
            AccountMappingOverride.id == override_id,
            AccountMappingOverride.company_id == company_id,
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Account mapping override not found")

    db.delete(record)
    db.commit()


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
    require_active_membership(db, current_user.id, company_id)

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
    mem_self = require_active_membership(db, current_user.id, company_id)
    if mem_self.role not in ("owner", "analyst"):
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
    mem_self = require_active_membership(db, current_user.id, company_id)
    if mem_self.role != "owner":
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
    mem_self = require_active_membership(db, current_user.id, company_id)
    if mem_self.role != "owner":
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
    mem = require_active_membership(db, current_user.id, company_id)
    if mem.role != "owner":
        raise HTTPException(status_code=403, detail="Only company owner can delete")
    company.is_active = False
    db.commit()
