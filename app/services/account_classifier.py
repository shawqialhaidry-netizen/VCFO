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

LOW_CONFIDENCE_THRESHOLD = CONF_CODE_ONLY


@dataclass
class ClassificationResult:
    mapped_type:  str
    confidence:   float
    match_reason: str
    classification_source: str


def _normalized_account_code(value: str) -> str:
    return "".join(str(value or "").split())


def _normalized_account_name(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


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
            classification_source = "rule",
        )

    # ── Case 2: code is WEAK → name overrides ────────────────────────────────
    if type_by_code in WEAK_CODE_TYPES and type_by_name:
        conf = CONF_NAME_STRONG if name_strong else CONF_NAME_WEAK
        return ClassificationResult(
            mapped_type  = type_by_name,
            confidence   = conf,
            match_reason = f"name_override_weak_code ({type_by_name}, code_was_{type_by_code})",
            classification_source = "rule",
        )

    # ── Case 3: code only (no name match) ────────────────────────────────────
    if type_by_code and not type_by_name:
        return ClassificationResult(
            mapped_type  = type_by_code,
            confidence   = CONF_CODE_ONLY,
            match_reason = f"code_prefix_only ({type_by_code})",
            classification_source = "rule",
        )

    # ── Case 4: conflict → code wins ─────────────────────────────────────────
    if type_by_code and type_by_name and type_by_code != type_by_name:
        return ClassificationResult(
            mapped_type  = type_by_code,
            confidence   = CONF_CODE_ONLY,
            match_reason = f"code_prefix ({type_by_code}), name_conflict ({type_by_name})",
            classification_source = "rule",
        )

    # ── Case 5: name only ─────────────────────────────────────────────────────
    if type_by_name:
        conf = CONF_NAME_STRONG if name_strong else CONF_NAME_WEAK
        return ClassificationResult(
            mapped_type  = type_by_name,
            confidence   = conf,
            match_reason = f"name_keyword ({'strong' if name_strong else 'weak'}) ({type_by_name})",
            classification_source = "rule",
        )

    # ── Case 6: nothing matched ───────────────────────────────────────────────
    return ClassificationResult(
        mapped_type  = OTHER,
        confidence   = CONF_UNKNOWN,
        match_reason = "no_match",
        classification_source = "fallback",
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
    df["classification_source"] = [r.classification_source for r in results]
    return df


def classify_dataframe_for_company(
    df: pd.DataFrame,
    company_id: str | None,
    db=None,
) -> pd.DataFrame:
    """
    Apply company-specific account-code overrides first, then fall back to the
    current rule-based classifier. Override identity is exact:
    company_id + normalized account_code.
    """
    if df is None:
        return df

    override_code_map: dict[str, str] = {}
    override_name_map: dict[str, str] = {}
    if company_id and db is not None:
        from app.models.account_mapping_override import AccountMappingOverride

        rows = (
            db.query(AccountMappingOverride)
            .filter(AccountMappingOverride.company_id == company_id)
            .all()
        )
        for row in rows:
            normalized_code = _normalized_account_code(row.account_code)
            normalized_name = _normalized_account_name(getattr(row, "account_name_hint", ""))
            if normalized_code:
                override_code_map[normalized_code] = row.mapped_type
            if normalized_name:
                override_name_map[normalized_name] = row.mapped_type

    df = df.copy()
    results: list[ClassificationResult] = []
    for row in df.to_dict(orient="records"):
        account_code = _normalized_account_code(row.get("account_code", ""))
        account_name = _normalized_account_name(row.get("account_name", ""))
        if account_code and account_code in override_code_map:
            results.append(
                ClassificationResult(
                    mapped_type=override_code_map[account_code],
                    confidence=1.0,
                    match_reason="company_override_code",
                    classification_source="override",
                )
            )
            continue
        if account_name and account_name in override_name_map:
            results.append(
                ClassificationResult(
                    mapped_type=override_name_map[account_name],
                    confidence=1.0,
                    match_reason="company_override_name",
                    classification_source="override",
                )
            )
            continue
        results.append(
            classify_account(
                account_code,
                row.get("account_name", ""),
            )
        )

    df["mapped_type"] = [r.mapped_type for r in results]
    df["confidence"] = [round(r.confidence, 2) for r in results]
    df["match_reason"] = [r.match_reason for r in results]
    df["classification_source"] = [r.classification_source for r in results]
    return df


# ── Summary builder ────────────────────────────────────────────────────────────

def build_classification_summary(df: pd.DataFrame) -> dict:
    total = len(df)
    if total == 0:
        return {
            "classified_ratio": 0.0,
            "unknown_accounts": [],
            "type_breakdown": {},
            "classification_source_breakdown": {},
            "override_accounts": [],
            "rule_accounts": [],
            "fallback_accounts": [],
            "low_confidence_accounts": [],
            "review_accounts": [],
            "qa_summary": {
                "low_confidence_threshold": round(float(LOW_CONFIDENCE_THRESHOLD), 2),
                "override_count": 0,
                "rule_count": 0,
                "fallback_count": 0,
                "low_confidence_count": 0,
                "review_count": 0,
            },
        }

    unknown_mask = df["confidence"] == 0.0
    classified   = total - unknown_mask.sum()

    unknown_accounts_df = df[unknown_mask][["account_code", "account_name"]].copy()
    if "account_code" in unknown_accounts_df.columns:
        unknown_accounts_df["account_code"] = unknown_accounts_df["account_code"].fillna("").astype(str)
    if "account_name" in unknown_accounts_df.columns:
        unknown_accounts_df["account_name"] = unknown_accounts_df["account_name"].fillna("").astype(str)
    unknown_accounts = unknown_accounts_df.to_dict(orient="records")

    type_breakdown = {}
    for mtype, group in df.groupby("mapped_type"):
        type_breakdown[mtype] = {
            "count":        int(len(group)),
            "total_debit":  round(float(group["debit"].sum()),  2),
            "total_credit": round(float(group["credit"].sum()), 2),
        }

    source_series = (
        df["classification_source"]
        if "classification_source" in df.columns
        else pd.Series(["fallback" if bool(x) else "rule" for x in unknown_mask], index=df.index)
    )

    def _account_records(mask: pd.Series) -> list[dict]:
        cols = [
            "account_code",
            "account_name",
            "mapped_type",
            "confidence",
            "match_reason",
            "classification_source",
        ]
        available_cols = [c for c in cols if c in df.columns]
        records = df.loc[mask, available_cols].copy()
        for text_col in (
            "account_code",
            "account_name",
            "mapped_type",
            "match_reason",
            "classification_source",
        ):
            if text_col in records.columns:
                records[text_col] = records[text_col].fillna("").astype(str)
        if "confidence" in records.columns:
            records["confidence"] = pd.to_numeric(records["confidence"], errors="coerce").fillna(0.0).round(2)
        return records.to_dict(orient="records")

    override_mask = source_series.astype(str).str.strip().str.lower() == "override"
    rule_mask = source_series.astype(str).str.strip().str.lower() == "rule"
    fallback_mask = source_series.astype(str).str.strip().str.lower() == "fallback"
    low_confidence_mask = (~fallback_mask) & (
        pd.to_numeric(df["confidence"], errors="coerce").fillna(0.0) < LOW_CONFIDENCE_THRESHOLD
    )
    review_mask = fallback_mask | low_confidence_mask

    classification_source_breakdown = {}
    for source in ("override", "rule", "fallback"):
        mask = source_series.astype(str).str.strip().str.lower() == source
        classification_source_breakdown[source] = {
            "count": int(mask.sum()),
        }

    return {
        "classified_ratio": round(float(classified) / total, 4),
        "unknown_accounts": unknown_accounts,
        "type_breakdown":   type_breakdown,
        "classification_source_breakdown": classification_source_breakdown,
        "override_accounts": _account_records(override_mask),
        "rule_accounts": _account_records(rule_mask),
        "fallback_accounts": _account_records(fallback_mask),
        "low_confidence_accounts": _account_records(low_confidence_mask),
        "review_accounts": _account_records(review_mask),
        "qa_summary": {
            "low_confidence_threshold": round(float(LOW_CONFIDENCE_THRESHOLD), 2),
            "override_count": int(override_mask.sum()),
            "rule_count": int(rule_mask.sum()),
            "fallback_count": int(fallback_mask.sum()),
            "low_confidence_count": int(low_confidence_mask.sum()),
            "review_count": int(review_mask.sum()),
        },
    }
