import json
from pathlib import Path

_SUPPORTED = {"en", "ar", "tr"}
_DEFAULT = "en"
_cache: dict[str, dict] = {}

def _load(lang: str) -> dict:
    if lang not in _cache:
        path = Path(__file__).parent / f"{lang}.json"
        if not path.exists():
            path = Path(__file__).parent / f"{_DEFAULT}.json"
        with open(path, encoding="utf-8") as f:
            _cache[lang] = json.load(f)
    return _cache[lang]


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
