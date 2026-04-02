import json
from pathlib import Path

_SUPPORTED = {"en", "ar", "tr"}
_DEFAULT = "en"
# Per-language cache: re-read JSON when file mtime changes (uvicorn --reload does not reload .json).
_cache: dict[str, tuple[float, dict]] = {}


def _load(lang: str) -> dict:
    if lang not in _SUPPORTED:
        lang = _DEFAULT
    path = Path(__file__).parent / f"{lang}.json"
    if not path.exists():
        path = Path(__file__).parent / f"{_DEFAULT}.json"
    mtime = path.stat().st_mtime
    hit = _cache.get(lang)
    if hit is not None and hit[0] == mtime:
        return hit[1]
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    _cache[lang] = (mtime, data)
    return data


def cache_clear() -> None:
    """Clear translation cache so next request re-reads JSON files from disk."""
    _cache.clear()


def translate(key: str, lang: str = _DEFAULT) -> str:
    if lang not in _SUPPORTED:
        lang = _DEFAULT
    data = _load(lang)
    # fallback to English if key missing
    if key not in data:
        data = _load(_DEFAULT)
    return data.get(key, key)


def get_supported_languages() -> list[dict]:
    return [
        {"code": "en", "name": "English", "dir": "ltr"},
        {"code": "ar", "name": "العربية", "dir": "rtl"},
        {"code": "tr", "name": "Türkçe", "dir": "ltr"},
    ]
