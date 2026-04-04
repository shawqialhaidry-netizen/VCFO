"""
causal_realize.py — Single realization layer for causal_contract items.

Looks up templates in app/i18n/{lang}.json by key. No silent fallback to English:
missing keys surface as [missing:<key>:<lang>].

Does not modify frontend or Wave 1 number formatting; engines are not wired yet.
"""
from __future__ import annotations

import copy
from typing import Any, Mapping

from app.i18n import _SUPPORTED, _load

from app.services.causal_contract import GENERATOR_VERSION


def _missing_key_placeholder(key: str, lang: str) -> str:
    return f"[missing:{key}:{lang}]"


def _invalid_lang_placeholder(lang: str) -> str:
    return f"[invalid_lang:{lang}]"


def _format_error_placeholder(key: str, lang: str) -> str:
    return f"[format_error:{key}:{lang}]"


def _normalize_lang(lang: str) -> str | None:
    s = (lang or "").strip().lower()
    if s in _SUPPORTED:
        return s
    return None


def realize_ref(ref: Mapping[str, Any] | None, lang: str) -> str:
    """
    Resolve a CausalRef { key, params } to a single string for the given language.

    - Unknown lang → [invalid_lang:<lang>] for any lookup path.
    - Missing ref or empty key → [missing::lang] (empty key segment).
    - Key absent in that language's JSON → [missing:<key>:<lang>] (no EN fallback).
    - .format(**params) failure → [format_error:<key>:<lang>]
    """
    norm = _normalize_lang(lang)
    if norm is None:
        return _invalid_lang_placeholder(lang or "")

    if not ref:
        return _missing_key_placeholder("", norm)

    key = ref.get("key")
    if not key or not isinstance(key, str):
        return _missing_key_placeholder(str(key) if key is not None else "", norm)

    params = ref.get("params") or {}
    if not isinstance(params, dict):
        params = {}

    data = _load(norm)
    if key not in data:
        return _missing_key_placeholder(key, norm)

    template = data[key]
    if not isinstance(template, str):
        return _missing_key_placeholder(key, norm)

    try:
        return template.format(**params)
    except (KeyError, ValueError, TypeError):
        return _format_error_placeholder(key, norm)


def realize_causal_item(item: Mapping[str, Any], lang: str) -> dict[str, Any]:
    """
    Return a shallow copy of item with realized text fields:
    change_text, cause_text, action_text.

    Original nested refs are deep-copied so callers can mutate the result safely.
    """
    base = copy.deepcopy(dict(item))
    base["change_text"] = realize_ref(base.get("change"), lang)
    base["cause_text"] = realize_ref(base.get("cause"), lang)
    base["action_text"] = realize_ref(base.get("action"), lang)
    return base


def realize_causal_items(items: list[Mapping[str, Any]], lang: str) -> list[dict[str, Any]]:
    """Map realize_causal_item over items (empty list if items is None)."""
    if not items:
        return []
    return [realize_causal_item(it, lang) for it in items]


def realize_bundle(bundle: Mapping[str, Any], lang: str | None = None) -> dict[str, Any]:
    """
    Optional helper: realize all items in a CausalBundle-shaped dict.

    If lang is None, uses bundle['meta']['lang'] when present; otherwise effective
    language is empty (realization yields [invalid_lang:] — no default to English).
    """
    b = copy.deepcopy(dict(bundle))
    items = b.get("causal_items") or []
    meta = dict(b.get("meta") or {})
    effective_lang = lang if lang is not None else str(meta.get("lang") or "")
    meta.setdefault("generator_version", GENERATOR_VERSION)
    b["meta"] = meta
    b["causal_items"] = realize_causal_items(list(items), effective_lang)
    return b


__all__ = [
    "realize_ref",
    "realize_causal_item",
    "realize_causal_items",
    "realize_bundle",
]
