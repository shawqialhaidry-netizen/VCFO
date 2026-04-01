"""
app/api/ai.py — AI CFO Advisor backend endpoint

POST /api/v1/ai/advisor

Receives user message + context inputs, builds system prompt,
calls Anthropic API server-side, returns structured answer.

Security:
  - Requires authenticated user (Bearer token)
  - Validates company membership (403 if not member)
  - ANTHROPIC_API_KEY never leaves the server
  - Raw exceptions never exposed to frontend
"""
from __future__ import annotations
import logging
from typing import Optional

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config   import settings
from app.core.database import get_db
from app.core.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])

ANTHROPIC_URL     = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL   = "claude-sonnet-4-20250514"
ANTHROPIC_VERSION = "2023-06-01"
MAX_TOKENS        = 1200


# ── Request / Response models ─────────────────────────────────────────────────

class MemoryInput(BaseModel):
    lastIntent: Optional[str] = None
    lastBranch: Optional[str] = None
    lastMetric: Optional[str] = None


class AdvisorRequest(BaseModel):
    company_id:  str
    message:     str
    lang:        str  = "ar"
    window:      str  = "ALL"
    consolidate: bool = False
    branch_id:   Optional[str] = None
    memory:      Optional[MemoryInput] = None
    history:     Optional[list[dict]] = None   # last N turns [{role, content}]


class AdvisorResponse(BaseModel):
    ok:        bool
    answer:    Optional[str] = None
    followups: list[str]     = []
    meta:      dict          = {}
    error:     Optional[str] = None


# ── Helper: call Anthropic synchronously ─────────────────────────────────────

def _call_anthropic(system_prompt: str, messages: list[dict]) -> str:
    """
    Call Anthropic /v1/messages synchronously via requests.
    Raises HTTPException(503) if API key missing or call fails.
    Never exposes raw exception text.
    """
    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="AI service not configured"
        )

    try:
        resp = requests.post(
            ANTHROPIC_URL,
            headers={
                "x-api-key":         api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type":      "application/json",
            },
            json={
                "model":      ANTHROPIC_MODEL,
                "max_tokens": MAX_TOKENS,
                "system":     system_prompt,
                "messages":   messages,
            },
            timeout=60,
        )
    except requests.exceptions.Timeout:
        logger.warning("Anthropic call timed out")
        raise HTTPException(status_code=504, detail="AI service timeout")
    except requests.exceptions.RequestException as e:
        logger.error("Anthropic request failed: %s", type(e).__name__)
        raise HTTPException(status_code=503, detail="AI service unavailable")

    if resp.status_code != 200:
        logger.error("Anthropic error %d: %s", resp.status_code,
                     resp.text[:200])
        raise HTTPException(status_code=503, detail="AI service error")

    try:
        data = resp.json()
        return data["content"][0]["text"]
    except Exception:
        logger.error("Anthropic response parse failed")
        raise HTTPException(status_code=503, detail="AI response parse error")


# ── POST /ai/advisor ──────────────────────────────────────────────────────────

@router.post("/advisor", response_model=AdvisorResponse)
def post_advisor(
    body:         AdvisorRequest,
    db:           Session = Depends(get_db),
    current_user            = Depends(get_current_user),
):
    """
    Main AI CFO advisor endpoint.

    1. Validates membership for company_id
    2. Builds full advisor context from existing engines
    3. Builds grounded system prompt
    4. Calls Anthropic server-side
    5. Returns structured answer + follow-up suggestions
    """
    from app.models.membership import Membership

    # ── Membership check ──────────────────────────────────────────────────────
    mem = db.query(Membership).filter(
        Membership.user_id    == current_user.id,
        Membership.company_id == body.company_id,
        Membership.is_active  == True,
    ).first()
    if not mem:
        raise HTTPException(status_code=403, detail="Access denied")

    # ── Build advisor context ──────────────────────────────────────────────────
    try:
        from app.services.vcfo_advisor_context import build_advisor_context
        ctx = build_advisor_context(
            company_id = body.company_id,
            db         = db,
            window     = body.window,
            scope      = "consolidated" if body.consolidate else "company",
            branch_id  = body.branch_id,
            lang       = body.lang,
        )
    except Exception as e:
        logger.error("advisor context failed company=%s: %s", body.company_id, e)
        return AdvisorResponse(ok=False, error="Internal processing error")

    # ── Build system prompt ───────────────────────────────────────────────────
    try:
        from app.services.vcfo_ai_advisor import build_system_prompt, detect_intent, get_followup_suggestions
        memory_dict = body.memory.model_dump() if body.memory else {}
        system_prompt = build_system_prompt(ctx, lang=body.lang, memory=memory_dict)
    except Exception as e:
        logger.error("system prompt build failed: %s", e)
        return AdvisorResponse(ok=False, error="Internal processing error")

    # ── Build message history ─────────────────────────────────────────────────
    safe_history = []
    if body.history:
        # Validate: only role/content, truncate to last 12 turns
        for turn in body.history[-12:]:
            role    = turn.get("role")
            content = turn.get("content", "")
            if role in ("user", "assistant") and isinstance(content, str):
                safe_history.append({"role": role, "content": content})

    messages = safe_history + [{"role": "user", "content": body.message}]

    # ── Call Anthropic ────────────────────────────────────────────────────────
    try:
        answer = _call_anthropic(system_prompt, messages)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Anthropic call unexpected error: %s", type(e).__name__)
        return AdvisorResponse(ok=False, error="AI service error")

    # ── Build follow-up suggestions ───────────────────────────────────────────
    intent   = detect_intent(body.message, memory_dict.get("lastIntent"))
    followups = get_followup_suggestions(intent, body.lang)

    # ── Response meta ─────────────────────────────────────────────────────────
    val  = ctx.get("validation", {})
    decs = ctx.get("decisions",  {})

    return AdvisorResponse(
        ok=True,
        answer=answer,
        followups=followups,
        meta={
            "validation_status": val.get("status", "UNKNOWN"),
            "risk_priority":     decs.get("priority", "UNKNOWN"),
            "period":            ctx.get("period", ""),
            "window":            ctx.get("window", body.window),
            "intent":            intent,
        },
    )
