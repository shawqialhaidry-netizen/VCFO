"""
Trial Balance Parser — Phase 2 (Hardened + Flexible Month Detection)
====================================================================
Supported formats:
  1. standard    — account_code, account_name, debit, credit [, period]
  2. long        — account_code, account_name, type (debit|credit), amount
  3. annual_wide — account_code, account_name, <month cols>
                   Month columns are detected via month_normalizer (flexible).

Output schema (always):
  account_code | account_name | debit | credit | period (YYYY-MM)
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

import pandas as pd

from app.services.month_normalizer import (
    detect_month_columns,
    normalize_column_report,
    month_number,
)

# ── Column alias sets ─────────────────────────────────────────────────────────
_CODE_ALIASES   = {
    "account_code","code","acc_code","hesap_kodu",
    "account","account no","acc","account number","hesap no",
    # Arabic — full phrases as they appear in real files
    "رقم الحساب","رقم حساب","كود الحساب","الرقم","رمز الحساب",
    # Turkish
    "hesap kodu","hesap_no","kod",
}
_NAME_ALIASES   = {
    "account_name","name","acc_name","hesap_adi",
    "description","account name","title","hesap adı",
    # Arabic
    "اسم الحساب","اسم حساب","البيان","الاسم","وصف الحساب",
    # Turkish
    "hesap adı","açıklama","ad",
}
_DEBIT_ALIASES  = {
    "debit","dr","مدين","borç","borc","debit_amount",
    "debit amount","total debit","إجمالي المدين",
}
_CREDIT_ALIASES = {
    "credit","cr","دائن","alacak","credit_amount",
    "credit amount","total credit","إجمالي الدائن",
}
_TYPE_ALIASES   = {
    "type","entry_type","النوع","tur","transaction_type","entry type",
}


def _norm_col(col: str) -> str:
    return str(col).strip().lower().replace(" ", "_").replace("-", "_")


def _find_col(df: pd.DataFrame, aliases: set[str]) -> str | None:
    for col in df.columns:
        raw = str(col).strip().lower()
        # Try both space-preserved and underscore-normalised forms
        if raw in aliases or raw.replace(" ", "_") in aliases or raw.replace("_", " ") in aliases:
            return col
    return None


# ── Auto header detection ─────────────────────────────────────────────────────

def _find_header_and_slice(df: pd.DataFrame, max_scan: int = 20) -> pd.DataFrame:
    """
    Scan the first `max_scan` rows of a raw DataFrame (read with header=None)
    and find the row that looks most like a header row.

    A row qualifies as a header if it contains at least ONE of:
      - a known column alias (account_code, debit, credit, account_name …)
      - a recognised month label (Jan, يناير, Ocak, 2025-01 …)

    Once the header row is found:
      - Use that row as column names
      - Return only the data rows below it
      - If no qualifying row is found in the first max_scan rows,
        return the DataFrame as-is (first row becomes header by pandas convention)
    """
    from app.services.month_normalizer import month_number as _mn

    # All known column aliases flattened to a set of lowercase strings
    _ALL_ALIASES: set[str] = set()
    for alias_set in [_CODE_ALIASES, _NAME_ALIASES, _DEBIT_ALIASES, _CREDIT_ALIASES, _TYPE_ALIASES]:
        for a in alias_set:
            _ALL_ALIASES.add(a.lower().strip())
            _ALL_ALIASES.add(a.lower().strip().replace(" ", "_"))

    def _row_score(row: pd.Series) -> int:
        """How many cells in this row look like column headers?"""
        score = 0
        for val in row:
            if val is None or (isinstance(val, float) and pd.isna(val)):
                continue
            s = str(val).strip().lower()
            if s in _ALL_ALIASES:
                score += 2          # strong hit — known alias
            elif _mn(str(val).strip()) is not None:
                score += 1          # month label — also qualifies
        return score

    scan_limit = min(max_scan, len(df))
    best_row   = -1
    best_score = 0

    for i in range(scan_limit):
        score = _row_score(df.iloc[i])
        if score > best_score:
            best_score = score
            best_row   = i

    # Need at least 1 strong match to commit
    if best_row == -1 or best_score == 0:
        # Fallback: treat row 0 as header (standard pandas behaviour)
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)
        return df

    if best_row > 0:
        print(f"[tb_parser] header auto-detected at row {best_row} "
              f"(skipped {best_row} title/description row(s))")

    df.columns = df.iloc[best_row]
    df = df.iloc[best_row + 1:].reset_index(drop=True)
    return df


# ── Format detectors ──────────────────────────────────────────────────────────

def _is_annual_wide(df: pd.DataFrame) -> bool:
    """
    True if ≥6 month columns are detected AND there are no standalone
    debit + credit columns together (which would indicate standard format).
    """
    mcols = detect_month_columns(list(df.columns))
    if len(mcols) < 6:
        return False
    has_debit  = _find_col(df, _DEBIT_ALIASES)  is not None
    has_credit = _find_col(df, _CREDIT_ALIASES) is not None
    # If BOTH debit AND credit columns exist → not annual wide
    return not (has_debit and has_credit)


def _is_long(df: pd.DataFrame) -> bool:
    type_col = _find_col(df, _TYPE_ALIASES)
    if type_col is None:
        return False
    vals = df[type_col].dropna().astype(str).str.strip().str.lower().unique()
    return any(v in {"debit","credit","dr","cr","مدين","دائن"} for v in vals)


# ── Period helpers ────────────────────────────────────────────────────────────

_ISO_RE = re.compile(r"^(\d{4})[-/](\d{1,2})$")


def _col_to_period(col_label: str, year: int) -> str:
    """Convert a detected month column + year → YYYY-MM."""
    s = str(col_label).strip()
    m = _ISO_RE.match(s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    num = month_number(col_label)
    if num:
        return f"{year}-{num:02d}"
    return f"{year}-00"


def _infer_year_from_cols(cols: list[str], fallback: int) -> int:
    """If any ISO column like '2025-01' is present, extract its year."""
    for c in cols:
        m = _ISO_RE.match(str(c).strip())
        if m:
            return int(m.group(1))
    return fallback


# ── Parsers ───────────────────────────────────────────────────────────────────

def _parse_standard(
    df: pd.DataFrame, period: str | None
) -> tuple[pd.DataFrame, str]:

    code_col   = _find_col(df, _CODE_ALIASES)
    name_col   = _find_col(df, _NAME_ALIASES)
    debit_col  = _find_col(df, _DEBIT_ALIASES)
    credit_col = _find_col(df, _CREDIT_ALIASES)

    missing = []
    if debit_col  is None: missing.append("debit")
    if credit_col is None: missing.append("credit")
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Optional built-in period column
    period_col = next(
        (c for c in df.columns if _norm_col(c) in {"period","month","الفترة","dönem"}),
        None,
    )

    out = pd.DataFrame()
    out["account_code"] = df[code_col].astype(str).str.strip() if code_col else ""
    out["account_name"] = df[name_col].astype(str).str.strip() if name_col else ""
    out["debit"]        = pd.to_numeric(df[debit_col],  errors="coerce").fillna(0.0)
    out["credit"]       = pd.to_numeric(df[credit_col], errors="coerce").fillna(0.0)
    out["period"]       = (
        df[period_col].astype(str).str.strip() if period_col is not None
        else (period or "")
    )
    return out, "standard"


def _parse_long(
    df: pd.DataFrame, period: str | None
) -> tuple[pd.DataFrame, str]:

    code_col = _find_col(df, _CODE_ALIASES)
    name_col = _find_col(df, _NAME_ALIASES)
    type_col = _find_col(df, _TYPE_ALIASES)

    exclude = {c for c in [code_col, name_col, type_col] if c}
    amount_col = next(
        (c for c in df.columns
         if c not in exclude and pd.api.types.is_numeric_dtype(df[c])),
        None,
    )
    if amount_col is None:
        for c in df.columns:
            if c not in exclude:
                converted = pd.to_numeric(df[c], errors="coerce")
                if converted.notna().sum() > 0:
                    df = df.copy()
                    df[c] = converted
                    amount_col = c
                    break

    if type_col is None or amount_col is None:
        raise ValueError("Long format requires a 'type' column and an amount column.")

    _type_map = {
        "debit":"debit","dr":"debit","مدين":"debit","borç":"debit","borc":"debit",
        "credit":"credit","cr":"credit","دائن":"credit","alacak":"credit",
    }
    df = df.copy()
    df["_entry"] = df[type_col].astype(str).str.strip().str.lower().map(_type_map)

    rows = []
    group_col = code_col or df.index
    for code, grp in df.groupby(group_col):
        rows.append({
            "account_code": str(code).strip(),
            "account_name": str(grp[name_col].iloc[0]).strip() if name_col else "",
            "debit":        float(grp.loc[grp["_entry"]=="debit",  amount_col].sum()),
            "credit":       float(grp.loc[grp["_entry"]=="credit", amount_col].sum()),
            "period":       period or "",
        })
    return pd.DataFrame(rows), "long"


def _parse_annual_wide(
    df: pd.DataFrame,
    year: int,
) -> tuple[pd.DataFrame, str, list[str]]:
    """
    Annual wide format: one amount column per month.
    Uses month_normalizer to detect columns — accepts any language/format.

    Convention (standard Arabic/Turkish accounting):
      positive value in month column → debit  (assets, expenses, cogs)
      negative value                 → credit (revenue, liabilities, equity)
    """
    code_col = _find_col(df, _CODE_ALIASES)
    name_col = _find_col(df, _NAME_ALIASES)

    # ── Detect month columns via normalizer ───────────────────────────────────
    report   = normalize_column_report(list(df.columns))
    detected = report["detected"]           # {col: month_int}

    if not detected:
        col_list = ", ".join(f"'{c}'" for c in df.columns[:15])
        raise ValueError(
            f"No month columns detected in annual wide file. "
            f"Columns found: {col_list}. "
            f"Unrecognised columns: {report['unrecognised']}"
        )

    if len(detected) < 2:
        raise ValueError(
            f"Only {len(detected)} month column(s) detected — "
            f"need at least 2 for annual wide format. "
            f"Detected: {list(detected.keys())}"
        )

    # Log for debugging (visible in uvicorn output)
    print(
        f"[tb_parser] annual_wide: detected {len(detected)} month column(s): "
        + ", ".join(f"{col!r}→{num}" for col, num in
                    sorted(detected.items(), key=lambda x: x[1]))
    )
    if report["unrecognised"]:
        print(f"[tb_parser] unrecognised columns (skipped): {report['unrecognised']}")
    if report["missing_months"]:
        print(f"[tb_parser] missing months: {report['missing_months']}")

    # Infer year from ISO-style column headers if possible
    year = _infer_year_from_cols(list(detected.keys()), year)

    # ── Sort month cols by month number ───────────────────────────────────────
    sorted_month_cols = sorted(detected.items(), key=lambda x: x[1])

    rows: list[dict] = []
    generated_periods: list[str] = []

    for col, mon_num in sorted_month_cols:
        period_str = f"{year}-{mon_num:02d}"
        if period_str not in generated_periods:
            generated_periods.append(period_str)

        for _, row in df.iterrows():
            code = str(row[code_col]).strip() if code_col else ""
            name = str(row[name_col]).strip() if name_col else ""

            # Skip metadata / header-like rows
            if not code or code.lower() in {
                "nan","none","","account_code","code","account","acc"
            }:
                continue

            raw_val = pd.to_numeric(row[col], errors="coerce")
            if pd.isna(raw_val):
                raw_val = 0.0
            else:
                raw_val = float(raw_val)

            # Sign convention: positive → debit, negative → credit
            debit  = raw_val  if raw_val >= 0 else 0.0
            credit = abs(raw_val) if raw_val <  0 else 0.0

            rows.append({
                "account_code": code,
                "account_name": name,
                "debit":        debit,
                "credit":       credit,
                "period":       period_str,
            })

    if not rows:
        raise ValueError("Annual wide file parsed to zero rows. Check that account_code column is present.")

    result = pd.DataFrame(rows)
    return result, "annual_wide", generated_periods


# ── Validation ────────────────────────────────────────────────────────────────

BALANCE_TOLERANCE = 0.01

def validate(df: pd.DataFrame, per_period: bool = False) -> dict[str, Any]:
    if df.empty:
        return {
            "ok": False, "error": "validation_empty",
            "total_debit": 0.0, "total_credit": 0.0,
            "diff": 0.0, "balanced": False, "record_count": 0,
        }

    total_debit  = round(float(df["debit"].sum()),  2)
    total_credit = round(float(df["credit"].sum()), 2)
    diff         = round(abs(total_debit - total_credit), 2)
    balanced     = diff <= BALANCE_TOLERANCE

    result: dict[str, Any] = {
        "ok":           True,
        "total_debit":  total_debit,
        "total_credit": total_credit,
        "diff":         diff,
        "balanced":     balanced,
        "record_count": int(len(df)),
    }

    if per_period and "period" in df.columns:
        breakdown: dict[str, dict] = {}
        for period, grp in df.groupby("period"):
            pd_ = round(float(grp["debit"].sum()),  2)
            pc_ = round(float(grp["credit"].sum()), 2)
            d_  = round(abs(pd_ - pc_), 2)
            breakdown[str(period)] = {
                "total_debit":  pd_,
                "total_credit": pc_,
                "diff":         d_,
                "balanced":     d_ <= BALANCE_TOLERANCE,
                "record_count": int(len(grp)),
            }
        result["period_breakdown"] = breakdown

    return result


# ── Public entry point ────────────────────────────────────────────────────────

def parse_file(
    file_bytes:  bytes,
    filename:    str,
    period:      str | None = None,
    upload_mode: str = "monthly",
    year:        int | None = None,
) -> dict[str, Any]:
    """
    Parse an uploaded Trial Balance file.

    Parameters
    ----------
    file_bytes   : raw file bytes
    filename     : original filename (extension used for format detection)
    period       : "YYYY-MM" — used for monthly uploads
    upload_mode  : "monthly" | "annual" | "auto_detect"
                   - "monthly"     → respect user intent; reject if file looks annual
                   - "annual"      → force annual wide parse
                   - "auto_detect" → detector decides (previous behaviour)
    year         : calendar year for annual_wide expansion

    Returns
    -------
    {
      ok, format, upload_mode, df,
      validation, generated_periods,
      column_report,              ← always present, used for debugging
      mode_conflict,              ← True when detector disagrees with explicit choice
      mode_conflict_detail,       ← human-readable explanation
      error                       ← only when ok=False
    }
    """
    ext = Path(filename).suffix.lower()

    try:
        if ext in {".xlsx", ".xls"}:
            df_raw = pd.read_excel(io.BytesIO(file_bytes), header=None, dtype=str)
        elif ext == ".csv":
            _preview = pd.read_csv(
                io.BytesIO(file_bytes), header=None, dtype=str,
                engine="python", nrows=5, encoding_errors="replace",
                on_bad_lines="skip",
            )
            _max_cols = max(len(_preview.columns), 30)
            df_raw = pd.read_csv(
                io.BytesIO(file_bytes), header=None, dtype=str,
                engine="python", names=list(range(_max_cols)),
                encoding_errors="replace", on_bad_lines="skip",
            )
        else:
            return {"ok": False, "error": f"Unsupported file type '{ext}'. Allowed: .xlsx, .xls, .csv"}
    except Exception as e:
        return {"ok": False, "error": f"Could not read file: {e}"}

    df_raw = _find_header_and_slice(df_raw)
    df_raw = df_raw.dropna(how="all").dropna(axis=1, how="all")

    if df_raw.empty:
        return {"ok": False, "error": "File is empty or contains only blank rows/columns."}

    col_report = normalize_column_report(list(df_raw.columns))

    generated_periods: list[str] = []
    resolved_year = year or (
        int(period[:4]) if period and len(period) >= 4 else 2025
    )

    # ── Detect what the file actually looks like ──────────────────────────────
    file_looks_annual = _is_annual_wide(df_raw)
    file_looks_long   = _is_long(df_raw)

    # Normalise upload_mode: treat empty/unknown as auto_detect
    _norm_mode = upload_mode.strip().lower() if upload_mode else "auto_detect"

    # ── Mode conflict detection ───────────────────────────────────────────────
    # Conflict = user explicitly chose monthly but file structure is annual wide.
    # We do NOT silently flip — we return an error with a clear explanation.
    mode_conflict        = False
    mode_conflict_detail = None

    if _norm_mode == "monthly" and file_looks_annual:
        mode_conflict        = True
        month_cols           = detect_month_columns(list(df_raw.columns))
        mode_conflict_detail = (
            f"You selected Monthly mode, but this file appears to be an "
            f"Annual Wide format ({len(month_cols)} month columns detected: "
            f"{', '.join(list(month_cols.keys())[:5])}{'...' if len(month_cols) > 5 else ''}). "
            f"Switch to Annual mode, or verify that your file is a single-period TB."
        )
        return {
            "ok":                  False,
            "error":               mode_conflict_detail,
            "mode_conflict":       True,
            "mode_conflict_detail": mode_conflict_detail,
            "column_report":       col_report,
            "suggested_mode":      "annual",
        }

    try:
        if _norm_mode == "annual":
            # User explicitly chose annual — always parse as annual wide
            df, fmt, generated_periods = _parse_annual_wide(df_raw, resolved_year)
            actual_mode = "annual"

        elif _norm_mode == "monthly":
            # User explicitly chose monthly — respect it, use standard/long parser
            if file_looks_long:
                df, fmt = _parse_long(df_raw, period)
                generated_periods = [period] if period else []
            else:
                df, fmt = _parse_standard(df_raw, period)
                generated_periods = [period] if period else []
            actual_mode = "monthly"

        else:
            # auto_detect: let the file structure decide (original behaviour)
            if file_looks_annual:
                df, fmt, generated_periods = _parse_annual_wide(df_raw, resolved_year)
                actual_mode = "annual"
            elif file_looks_long:
                df, fmt = _parse_long(df_raw, period)
                generated_periods = [period] if period else []
                actual_mode = "monthly"
            else:
                df, fmt = _parse_standard(df_raw, period)
                generated_periods = [period] if period else []
                actual_mode = "monthly"

    except ValueError as e:
        return {
            "ok": False,
            "error": str(e),
            "column_report": col_report,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": f"Parse error: {e}",
            "column_report": col_report,
        }

    # ── Clean up ──────────────────────────────────────────────────────────────
    df = df.copy()
    df["debit"]  = pd.to_numeric(df["debit"],  errors="coerce").fillna(0.0)
    df["credit"] = pd.to_numeric(df["credit"], errors="coerce").fillna(0.0)
    df = df[(df["debit"] != 0) | (df["credit"] != 0)]
    df = df.reset_index(drop=True)

    if df.empty:
        return {
            "ok": False,
            "error": "File parsed successfully but all rows have zero debit and zero credit.",
            "column_report": col_report,
        }

    is_annual  = actual_mode == "annual"
    validation = validate(df, per_period=is_annual)

    return {
        "ok":                True,
        "format":            fmt,
        "upload_mode":       actual_mode,
        "df":                df,
        "validation":        validation,
        "generated_periods": generated_periods,
        "column_report":     col_report,
    }
