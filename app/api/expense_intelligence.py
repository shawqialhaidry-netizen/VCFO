"""
api/expense_intelligence.py — Phase 3 scope-aware expense intelligence (backend only).

GET /api/v1/expense-intelligence?scope_type=company|branch|group&scope_id=<uuid>
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.scope_expense_intelligence import build_scope_expense_intelligence

router = APIRouter(tags=["expense-intelligence"])


@router.get("/expense-intelligence")
def get_expense_intelligence(
    scope_type: str = Query(..., description="company | branch | group"),
    scope_id: str = Query(..., description="UUID of the scope entity"),
    lang: str = Query(default="en", description="en | ar | tr"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return build_scope_expense_intelligence(
        db=db,
        user=current_user,
        scope_type=scope_type,
        scope_id=scope_id,
        lang=lang,
    )

