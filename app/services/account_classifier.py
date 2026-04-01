"""
account_classifier.py — Phase 3 (Fixed)

Key fix: When code prefix returns a WEAK type (OTHER),
the name keyword is allowed to override it rather than
treating it as a conflict where code always wins.

This correctly handles:
  - 8010 ضريبة الدخل → code=OTHER (weak), name=TAX (strong) → TAX ✓
  - 8xxx intercompany → code=OTHER (weak), name=OTHER → OTHER ✓
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from app.services.account_rules import (
    ALL_TYPES,
    CODE_PREFIX_RULES,
    CONF_CODE_AND_NAME,
    CONF_CODE_ONLY,
    CONF_NAME_STRONG,
    CONF_NAME_WEAK,
    CONF_UNKNOWN,
    NAME_KEYWORD_RULES,
    OTHER,
    WEAK_CODE_TYPES,
)


@dataclass
class ClassificationResult:
    mapped_type:  str
    confidence:   float
    match_reason: str


# ── Step 1: Code-based classification ─────────────────────────────────────────

def _classify_by_code(code: str) -> Optional[str]:
    clean = code.strip().lstrip("0") if code else ""
    for candidate in {code.strip(), clean}:
        for prefix, mapped_type in CODE_PREFIX_RULES:
            if candidate.startswith(prefix):
                return mapped_type
    return None


# ── Step 2: Name-based classification ─────────────────────────────────────────

def _classify_by_name(name: str) -> tuple[Optional[str], bool]:
    lower = name.lower().strip() if name else ""
    if not lower:
        return None, False

    # Strong keywords first
    for keyword, mapped_type, is_strong in NAME_KEYWORD_RULES:
        if is_strong and keyword in lower:
            return mapped_type, True

    # Weak keywords second
    for keyword, mapped_type, is_strong in NAME_KEYWORD_RULES:
        if not is_strong and keyword in lower:
            return mapped_type, False

    return None, False


# ── Main classify function ─────────────────────────────────────────────────────

def classify_account(
    account_code: str,
    account_name: str,
) -> ClassificationResult:
    """
    Priority logic:

    1. Code + Name AGREE          → high confidence (0.95)
    2. Code is WEAK (OTHER range) AND name has a match
                                  → name wins (avoids burying tax in "other")
    3. Code match, no name match  → code wins (0.75)
    4. Code + Name CONFLICT       → code wins (0.75), note conflict
    5. Name only                  → name wins (0.65 strong / 0.40 weak)
    6. Nothing                    → OTHER, 0.0
    """
    code_str = str(account_code).strip() if account_code else ""
    name_str = str(account_name).strip() if account_name else ""

    type_by_code               = _classify_by_code(code_str)
    type_by_name, name_strong  = _classify_by_name(name_str)

    # ── Case 1: both agree ────────────────────────────────────────────────────
    if type_by_code and type_by_name and type_by_code == type_by_name:
        return ClassificationResult(
            mapped_type  = type_by_code,
            confidence   = CONF_CODE_AND_NAME,
            match_reason = f"code_prefix+name_keyword ({type_by_code})",
        )

    # ── Case 2: code is WEAK → name overrides ────────────────────────────────
    if type_by_code in WEAK_CODE_TYPES and type_by_name:
        conf = CONF_NAME_STRONG if name_strong else CONF_NAME_WEAK
        return ClassificationResult(
            mapped_type  = type_by_name,
            confidence   = conf,
            match_reason = f"name_override_weak_code ({type_by_name}, code_was_{type_by_code})",
        )

    # ── Case 3: code only (no name match) ────────────────────────────────────
    if type_by_code and not type_by_name:
        return ClassificationResult(
            mapped_type  = type_by_code,
            confidence   = CONF_CODE_ONLY,
            match_reason = f"code_prefix_only ({type_by_code})",
        )

    # ── Case 4: conflict → code wins ─────────────────────────────────────────
    if type_by_code and type_by_name and type_by_code != type_by_name:
        return ClassificationResult(
            mapped_type  = type_by_code,
            confidence   = CONF_CODE_ONLY,
            match_reason = f"code_prefix ({type_by_code}), name_conflict ({type_by_name})",
        )

    # ── Case 5: name only ─────────────────────────────────────────────────────
    if type_by_name:
        conf = CONF_NAME_STRONG if name_strong else CONF_NAME_WEAK
        return ClassificationResult(
            mapped_type  = type_by_name,
            confidence   = conf,
            match_reason = f"name_keyword ({'strong' if name_strong else 'weak'}) ({type_by_name})",
        )

    # ── Case 6: nothing matched ───────────────────────────────────────────────
    return ClassificationResult(
        mapped_type  = OTHER,
        confidence   = CONF_UNKNOWN,
        match_reason = "no_match",
    )


# ── Batch classification ───────────────────────────────────────────────────────

def classify_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    results = [
        classify_account(
            row.get("account_code", ""),
            row.get("account_name", ""),
        )
        for row in df.to_dict(orient="records")
    ]
    df["mapped_type"]  = [r.mapped_type            for r in results]
    df["confidence"]   = [round(r.confidence, 2)   for r in results]
    df["match_reason"] = [r.match_reason            for r in results]
    return df


# ── Summary builder ────────────────────────────────────────────────────────────

def build_classification_summary(df: pd.DataFrame) -> dict:
    total = len(df)
    if total == 0:
        return {"classified_ratio": 0.0, "unknown_accounts": [], "type_breakdown": {}}

    unknown_mask = df["confidence"] == 0.0
    classified   = total - unknown_mask.sum()

    unknown_accounts = df[unknown_mask][
        ["account_code", "account_name"]
    ].to_dict(orient="records")

    type_breakdown = {}
    for mtype, group in df.groupby("mapped_type"):
        type_breakdown[mtype] = {
            "count":        int(len(group)),
            "total_debit":  round(float(group["debit"].sum()),  2),
            "total_credit": round(float(group["credit"].sum()), 2),
        }

    return {
        "classified_ratio": round(float(classified) / total, 4),
        "unknown_accounts": unknown_accounts,
        "type_breakdown":   type_breakdown,
    }
