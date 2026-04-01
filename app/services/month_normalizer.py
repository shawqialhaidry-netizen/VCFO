"""
month_normalizer.py — Production-grade month detection layer
============================================================
Converts ANY column label that looks like a month → canonical int (1-12).

Resolution order (first match wins):
  1. ISO pattern          "2025-01", "2025/01", "01/2025"
  2. Pure numeric         "1" … "12", "01" … "12"
  3. Exact table lookup   case-insensitive, strip whitespace + invisible chars
  4. Trailing-dot strip   "jan." → "jan"
  5. Prefix match         unambiguous prefix ≥3 chars
  6. Returns None         (not a month — caller decides what to do)

Never raises — always returns int | None.

Public API
----------
  month_number(label)           -> int | None
  is_month_col(label)           -> bool
  detect_month_columns(columns) -> dict[original_col, month_int]
  normalize_column_report(cols) -> dict  (full diagnostic)
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════════════
#  Master month table
#  (month_int, [all known labels — lowercase already])
# ═══════════════════════════════════════════════════════════════════════════════

_MONTH_TABLE: list[tuple[int, list[str]]] = [
    (1, [
        # English
        "jan", "jan.", "january",
        # Arabic (multiple regional variants)
        "يناير", "يناير", "كانون الثاني", "كانون ثاني",
        # Turkish short + full
        "oca", "ocak",
        # German / French bonus
        "januar", "janvier",
    ]),
    (2, [
        "feb", "feb.", "february",
        "فبراير", "شباط",
        "şub", "şub.", "şubat",
        "februar", "février", "fevrier",
    ]),
    (3, [
        "mar", "mar.", "march",
        "مارس", "آذار", "اذار",
        "mart",
        "märz", "marz", "mars",
    ]),
    (4, [
        "apr", "apr.", "april",
        "أبريل", "ابريل", "إبريل", "نيسان",
        "nis", "nis.", "nisan",
        "avril",
    ]),
    (5, [
        "may",
        "مايو", "أيار", "ايار",
        "mayıs", "mayis",
        "mai",
    ]),
    (6, [
        "jun", "jun.", "june",
        "يونيو", "حزيران",
        "haz", "haz.", "haziran",
        "juni", "juin",
    ]),
    (7, [
        "jul", "jul.", "july",
        "يوليو", "تموز",
        "tem", "tem.", "temmuz",
        "juli", "juillet",
    ]),
    (8, [
        "aug", "aug.", "august",
        "أغسطس", "اغسطس", "آب", "اب",
        "ağu", "agu", "ağu.", "ağustos", "agustos",
        "august", "août", "aout",
    ]),
    (9, [
        "sep", "sep.", "sept", "sept.", "september",
        "سبتمبر", "أيلول", "ايلول",
        "eyl", "eyl.", "eylül", "eylul",
        "september", "septembre",
    ]),
    (10, [
        "oct", "oct.", "october",
        "أكتوبر", "اكتوبر", "تشرين الأول", "تشرين أول",
        "eki", "eki.", "ekim",
        "oktober", "octobre",
    ]),
    (11, [
        "nov", "nov.", "november",
        "نوفمبر", "تشرين الثاني", "تشرين ثاني",
        "kas", "kas.", "kasım", "kasim",
        "november", "novembre",
    ]),
    (12, [
        "dec", "dec.", "december",
        "ديسمبر", "كانون الأول", "كانون أول",
        "ara", "ara.", "aralık", "aralik",
        "dezember", "décembre", "decembre",
    ]),
]

# ── Build flat exact lookup ────────────────────────────────────────────────────
_EXACT: dict[str, int] = {}
for _num, _labels in _MONTH_TABLE:
    for _lbl in _labels:
        _EXACT[_lbl.strip().lower()] = _num

# ── Build prefix lookup (≥3 chars) ────────────────────────────────────────────
# prefix → set of month ints that share that prefix
_PREFIX: dict[str, set[int]] = {}
for _num, _labels in _MONTH_TABLE:
    for _lbl in _labels:
        _clean_lbl = _lbl.strip().lower().rstrip(".")
        for _plen in range(3, len(_clean_lbl) + 1):
            _pfx = _clean_lbl[:_plen]
            _PREFIX.setdefault(_pfx, set()).add(_num)

# ── Regex patterns ─────────────────────────────────────────────────────────────
_RE_ISO_DASH = re.compile(r"^(\d{1,4})[-/](\d{1,4})$")
_RE_NUMERIC  = re.compile(r"^(\d{1,2})$")
# Invisible / zero-width characters to strip
_RE_INVISIBLE = re.compile(r"[\u200b-\u200f\u202a-\u202e\ufeff\u00a0]")

# Common column names that are NOT months and should never match
_NON_MONTH_EXACT: frozenset[str] = frozenset({
    "debit", "credit", "dr", "cr", "total", "amount", "balance",
    "code", "name", "description", "account", "acc", "type", "period",
    "year", "quarter", "ytd", "q1", "q2", "q3", "q4",
    "opening", "closing", "note", "ref", "remarks", "currency",
    "مدين", "دائن", "المجموع", "الرصيد", "إجمالي", "اسم",
    "رقم", "الكود", "النوع", "الفترة", "السنة",
    "borç", "alacak", "toplam", "bakiye", "kod", "ad", "açıklama",
})


# ═══════════════════════════════════════════════════════════════════════════════
#  Internal normaliser
# ═══════════════════════════════════════════════════════════════════════════════

def _norm(s: str) -> str:
    """Strip invisible chars, unicode-normalise, lowercase, trim."""
    s = _RE_INVISIBLE.sub("", s)
    s = unicodedata.normalize("NFC", s)
    return s.strip().lower()


# ═══════════════════════════════════════════════════════════════════════════════
#  Public: month_number
# ═══════════════════════════════════════════════════════════════════════════════

def month_number(label: str) -> Optional[int]:
    """
    Return 1-12 if label represents a month, else None.
    Never raises.
    """
    if not label:
        return None
    raw = str(label).strip()
    if not raw:
        return None

    s = _norm(raw)

    # ── Guard: known non-month words ──────────────────────────────────────────
    if s in _NON_MONTH_EXACT:
        return None

    # ── Step 1: ISO / slash patterns ─────────────────────────────────────────
    m = _RE_ISO_DASH.match(s)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        # Figure out which part is year and which is month
        if a > 31:                          # "2025-01" → a=year, b=month
            return b if 1 <= b <= 12 else None
        elif b > 31:                        # "01-2025" → a=month, b=year
            return a if 1 <= a <= 12 else None
        elif a > 12:                        # "25-01" style → b=month
            return b if 1 <= b <= 12 else None
        elif b > 12:                        # "01-25" style → a=month
            return a if 1 <= a <= 12 else None
        else:                               # both ≤12: ISO convention a=year-part
            return b if 1 <= b <= 12 else None

    # ── Step 2: Pure numeric ──────────────────────────────────────────────────
    m = _RE_NUMERIC.match(s)
    if m:
        n = int(m.group(1))
        return n if 1 <= n <= 12 else None

    # ── Step 3: Exact lookup ──────────────────────────────────────────────────
    if s in _EXACT:
        return _EXACT[s]

    # ── Step 4: Trailing dot / punctuation strip ──────────────────────────────
    s_clean = s.rstrip(".,;:")
    if s_clean != s and s_clean in _EXACT:
        return _EXACT[s_clean]

    # ── Step 5: Prefix match (unambiguous only, ≥3 chars) ────────────────────
    # Try from longest prefix down to 3 chars
    candidate = s_clean if s_clean else s
    for plen in range(len(candidate), 2, -1):
        pfx = candidate[:plen]
        hits = _PREFIX.get(pfx, set())
        if len(hits) == 1:
            return next(iter(hits))
        if len(hits) > 1:
            # Ambiguous — don't guess
            break

    return None


def is_month_col(label: str) -> bool:
    return month_number(label) is not None


# ═══════════════════════════════════════════════════════════════════════════════
#  Public: detect_month_columns
# ═══════════════════════════════════════════════════════════════════════════════

def detect_month_columns(columns: list[str]) -> dict[str, int]:
    """
    Returns {original_col_name: month_int} for every detected month column.
    Deduplicates: if two columns map to the same month number, keeps the
    first one encountered (left-to-right).
    """
    result: dict[str, int] = {}
    seen_nums: set[int] = set()
    for col in columns:
        n = month_number(str(col))
        if n is not None and n not in seen_nums:
            result[col] = n
            seen_nums.add(n)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  Public: normalize_column_report
# ═══════════════════════════════════════════════════════════════════════════════

def normalize_column_report(columns: list[str]) -> dict:
    """
    Full diagnostic report — used by parser for structured error messages.

    Returns
    -------
    {
      "detected":         {col: month_int},
      "ordered":          [(col, month_int)],   # sorted by month number
      "unrecognised":     [col],                # couldn't map, not obviously non-month
      "non_month":        [col],                # clearly not a month
      "missing_months":   [1, 2, ...],          # month numbers not present
      "duplicate_months": {month_int: [col]},   # same month covered by multiple cols
      "has_enough":       bool,                 # ≥6 months detected
    }
    """
    detected:    dict[str, int]       = {}
    unrecognised: list[str]           = []
    non_month:   list[str]            = []
    month_to_cols: dict[int, list[str]] = {}

    for col in columns:
        s = _norm(str(col))
        n = month_number(col)
        if n is not None:
            detected[col] = n
            month_to_cols.setdefault(n, []).append(col)
        elif s in _NON_MONTH_EXACT or len(s) > 25:
            non_month.append(col)
        else:
            unrecognised.append(col)

    ordered          = sorted(detected.items(), key=lambda x: (x[1], x[0]))
    covered          = set(detected.values())
    missing_months   = [m for m in range(1, 13) if m not in covered]
    duplicate_months = {
        num: cols for num, cols in month_to_cols.items() if len(cols) > 1
    }

    return {
        "detected":         detected,
        "ordered":          ordered,
        "unrecognised":     unrecognised,
        "non_month":        non_month,
        "missing_months":   missing_months,
        "duplicate_months": duplicate_months,
        "has_enough":       len(detected) >= 6,
    }
