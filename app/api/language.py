from fastapi import APIRouter, Depends, HTTPException
from app.i18n import get_supported_languages, translate
from app.core.security import get_current_user

router = APIRouter(prefix="/language", tags=["language"])


@router.get("/list")
def list_languages():
    return {"languages": get_supported_languages()}


@router.get("/translations/{lang}")
def get_translations(lang: str):
    """Return full translation map for a given language — used by frontend."""
    from app.i18n import _SUPPORTED, _load, _DEFAULT
    if lang not in _SUPPORTED:
        lang = _DEFAULT
    return {"lang": lang, "translations": _load(lang)}


@router.post("/cache-clear")
def clear_translation_cache(current_user = Depends(get_current_user)):
    """Clear in-memory translation cache — restricted to superusers only."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not getattr(current_user, "is_superuser", False):
        raise HTTPException(status_code=403, detail="Admin access required")
    from app.i18n import cache_clear
    cache_clear()
    return {"status": "cleared"}
