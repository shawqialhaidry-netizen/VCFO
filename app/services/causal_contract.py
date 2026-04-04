"""
causal_contract.py — Wave 2B canonical causal generation contract.

Infrastructure-only: defines shapes and constants. No engines import this yet.
"""
from __future__ import annotations

from typing import Any, TypedDict

GENERATOR_VERSION = "1"

# Topics consumers may emit (extend in later batches; unknown values still allowed in items).
TOPICS = frozenset({
    "revenue",
    "margin",
    "liquidity",
    "cost",
    "branch",
    "risk",
    "forecast",
    "growth",
    "leverage",
    "efficiency",
})

SEVERITIES = frozenset({"low", "medium", "high"})

SOURCES = frozenset({
    "decision",
    "anomaly",
    "narrative",
    "forecast",
    "alert",
    "expense_deep",
    "profitability_deep",
    "annual_narrative",
    "ai_cfo_heuristic",
})


class CausalRef(TypedDict, total=False):
    """Localizable fragment: template key + interpolation params (numbers/facts)."""

    key: str
    params: dict[str, Any]


class CausalEvidence(TypedDict, total=False):
    source_metrics: dict[str, Any]
    template_ids: list[str]
    merged_from: list[str]


class CausalItem(TypedDict, total=False):
    id: str
    topic: str
    change: CausalRef
    cause: CausalRef
    action: CausalRef
    severity: str
    source: str
    evidence: CausalEvidence


class CausalMeta(TypedDict, total=False):
    lang: str
    generator_version: str


class CausalBundle(TypedDict, total=False):
    causal_items: list[CausalItem]
    meta: CausalMeta


def empty_causal_bundle(lang: str) -> CausalBundle:
    """Canonical empty bundle for a request language (no validation of lang code here)."""
    return {
        "causal_items": [],
        "meta": {
            "lang": lang,
            "generator_version": GENERATOR_VERSION,
        },
    }


__all__ = [
    "GENERATOR_VERSION",
    "TOPICS",
    "SEVERITIES",
    "SOURCES",
    "CausalRef",
    "CausalEvidence",
    "CausalItem",
    "CausalMeta",
    "CausalBundle",
    "empty_causal_bundle",
]
