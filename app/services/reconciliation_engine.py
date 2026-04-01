"""
reconciliation_engine.py — Strict Financial Integrity Enforcement

Step 2.5: Upgraded from passive warnings to hard enforcement.

Severity model:
  PASS    — all checks clear
  WARNING — non-blocking anomaly (informational)
  FAIL    — blocking accounting error; data must not be treated as reliable

A validation block with status=FAIL means the financial data has a confirmed
accounting error. Downstream layers must check this flag before presenting data.
"""
from __future__ import annotations
from typing import Optional, List


def _r2(v) -> float:
    return round(float(v or 0), 2)


def _pct_gap(a: float, b: float) -> Optional[float]:
    if not a:
        return None
    return round((b - a) / abs(a) * 100, 2)


# ── Check 1: Trial Balance identity (debits = credits) ───────────────────────

def check_tb_balanced(
    total_debit: float,
    total_credit: float,
    tolerance: float = 0.10,
) -> dict:
    """
    STRICT: debits must equal credits within tolerance.
    Any difference > tolerance → FAIL (not warning).
    """
    diff = _r2(abs(total_debit - total_credit))
    ok   = diff <= tolerance
    return {
        "trial_balance_balanced": ok,
        "total_debit":            _r2(total_debit),
        "total_credit":           _r2(total_credit),
        "tb_diff":                diff,
        "severity":               "PASS" if ok else "FAIL",
        "error": None if ok else (
            f"Trial balance NOT balanced: "
            f"debits={total_debit:,.2f} credits={total_credit:,.2f} diff={diff:,.2f}"
        ),
    }


# ── Check 2: Balance Sheet accounting equation ───────────────────────────────

def check_bs_balanced(stmt: dict, tolerance: float = 1.00) -> dict:
    """
    STRICT: Assets = Liabilities + Equity (closed period)
            OR Assets = Liabilities + Equity + Net Profit (pre-closing TB).
    Both forms checked. Neither satisfied → FAIL.
    """
    bs  = stmt.get("balance_sheet", {})
    is_ = stmt.get("income_statement", {})

    assets = _r2(bs.get("assets",      {}).get("total") or 0)
    liabs  = _r2(bs.get("liabilities", {}).get("total") or 0)
    equity = _r2(bs.get("equity",      {}).get("total") or 0)
    np_    = _r2(is_.get("net_profit") or 0)

    gap_closed  = _r2(abs(assets - (liabs + equity)))
    gap_preclos = _r2(abs(assets - (liabs + equity + np_)))

    is_closed  = gap_closed  <= tolerance
    is_preclos = gap_preclos <= tolerance
    ok         = is_closed or is_preclos

    interp = (
        "closed_period"  if is_closed  else
        "pre_closing_tb" if is_preclos else
        "unbalanced"
    )

    return {
        "balance_sheet_balanced": ok,
        "assets":                 assets,
        "liabilities_equity":     _r2(liabs + equity),
        "net_profit":             np_,
        "gap_closed":             gap_closed,
        "gap_preclosing":         gap_preclos,
        "interpretation":         interp,
        "severity":               "PASS" if ok else "FAIL",
        "error": None if ok else (
            f"Balance sheet does not balance [{stmt.get('period','?')}]: "
            f"assets={assets:,.2f} L+E={liabs+equity:,.2f} NP={np_:,.2f} "
            f"gap_closed={gap_closed:,.2f} gap_pre={gap_preclos:,.2f}"
        ),
    }


# ── Check 3: Account-level continuity across periods ─────────────────────────

def _extract_bs_account_balances(stmt: dict) -> dict[str, dict]:
    """
    Extract per-account closing balances from Balance Sheet sections ONLY.

    Balance Sheet (stock) accounts carry forward between periods.
    Income Statement (flow) accounts reset each period — excluded.

    Returns: {account_code: {amount, account_name, section}}
    Excludes synthetic entries (e.g. NET_PROFIT injected by statement_engine).
    """
    bs = stmt.get("balance_sheet", {})
    result: dict[str, dict] = {}
    for section in ("assets", "liabilities", "equity"):
        for item in bs.get(section, {}).get("items", []):
            code = str(item.get("account_code", "") or "").strip()
            if not code or code == "NET_PROFIT":
                continue   # skip synthetic equity injection
            result[code] = {
                "account_name": item.get("account_name", ""),
                "amount":       _r2(item.get("amount", 0) or 0),
                "section":      section,
            }
    return result


def check_account_continuity(
    stmts: list[dict],
    tolerance: float = 0.01,
    materiality_threshold: float = 1000.0,
) -> dict:
    """
    Account-level continuity for Balance Sheet accounts between consecutive periods.

    Accounting basis:
    ─────────────────
    VCFO ingests monthly TB snapshots. A TB snapshot shows each account's
    CLOSING BALANCE at the end of that period. In a correctly maintained
    ledger, closing_balance[t] is carried forward as opening_balance[t+1].

    Therefore: closing_balance(account X, period t-1)
               MUST EQUAL
               opening_balance(account X, period t)

    In a TB system, opening_balance[t] is not separately reported — it IS
    closing_balance[t-1]. So we compare the TB amount of account X in
    period t-1 with the TB amount of account X in period t.

    Wait — this is NOT what "opening balance" means in a running ledger.
    In a running ledger: opening[t] + movements[t] = closing[t].
    The TB snapshot at period t shows closing[t], not opening[t].

    Correct continuity check for TB snapshots:
    ─────────────────────────────────────────
    Since we do not have movement data (only snapshots), we cannot verify
    opening + movements = closing algebraically.

    What we CAN verify from two consecutive TB snapshots:
      1. Sign integrity: BS account should not unexpectedly flip sign
         (e.g. asset receivable = +640K in Jan, -50K in Feb is wrong)
      2. Presence consistency: account code in t-1 not in t → "removed" (OK)
         account code in t not in t-1 → "new account" (OK, opening = 0)
      3. Zero-from-nonzero: account had non-zero balance, then zero, then
         non-zero again in t+2 → possible data gap (WARNING, not FAIL)

    Tolerance: abs(diff) <= tolerance → OK (floating-point rounding)

    Materiality: total_difference_amount > materiality_threshold → FAIL
                 otherwise → WARNING (minor rounding acceptable)

    Edge cases:
      - New account (in t but not t-1): opening assumed 0 → NOT an error
      - Removed account (in t-1 but not t): closing assumed 0 → NOT an error
    """
    if len(stmts) < 2:
        return {
            "account_continuity_ok":  True,
            "periods_checked":        len(stmts),
            "mismatch_count":         0,
            "total_difference":       0.0,
            "top_mismatches":         [],
            "continuity_errors":      [],
            "severity":               "PASS",
            "error":                  None,
        }

    mismatches: list[dict] = []

    for i in range(1, len(stmts)):
        prev  = stmts[i - 1]
        curr  = stmts[i]
        pp    = prev.get("period", f"period-{i}")
        cp    = curr.get("period", f"period-{i+1}")

        prev_balances = _extract_bs_account_balances(prev)
        curr_balances = _extract_bs_account_balances(curr)

        all_codes = set(prev_balances) | set(curr_balances)

        for code in sorted(all_codes):
            prev_entry = prev_balances.get(code)
            curr_entry = curr_balances.get(code)

            # New account (not in t-1): opening = 0, current closing = curr amount
            # This is valid — new accounts have zero opening balance.
            if prev_entry is None:
                continue   # opening = 0, no continuity error

            # Removed account (not in t): closing assumed 0
            # This is valid — account was closed/zeroed out.
            if curr_entry is None:
                continue   # closing = 0, no continuity error

            prev_closing  = prev_entry["amount"]
            # In a monthly TB snapshot, curr_entry["amount"] is the CLOSING
            # balance of period t, NOT the opening. We cannot directly compare
            # closing[t-1] to opening[t] without movement data.
            #
            # What we CAN check: sign integrity (unexpected sign flip).
            # A sign flip on a BS account is almost always a data error.
            curr_closing  = curr_entry["amount"]
            section       = prev_entry["section"]

            # Sign integrity check: unexpected sign flip on BS account
            # Assets and liabilities should be non-negative by convention.
            # Equity can legitimately be negative (accumulated losses).
            if section in ("assets", "liabilities"):
                if prev_closing > tolerance and curr_closing < -tolerance:
                    diff = abs(curr_closing - prev_closing)
                    mismatches.append({
                        "account_code":     code,
                        "account_name":     prev_entry["account_name"],
                        "section":          section,
                        "period_from":      pp,
                        "period_to":        cp,
                        "previous_closing": prev_closing,
                        "current_snapshot_balance": curr_closing,   # TB closing balance of current period
                        "difference":       _r2(diff),
                        "type":             "sign_flip",
                        "error": (
                            f"Account {code} ({prev_entry['account_name']}) "
                            f"flipped from +{prev_closing:,.2f} to {curr_closing:,.2f} "
                            f"between {pp} and {cp}"
                        ),
                    })

    mismatch_count    = len(mismatches)
    total_difference  = _r2(sum(m["difference"] for m in mismatches))
    top_mismatches    = sorted(mismatches, key=lambda x: -x["difference"])[:10]

    # Severity based on materiality
    if mismatch_count == 0:
        ok = True; severity = "PASS"; error = None
    elif total_difference > materiality_threshold:
        ok = False; severity = "FAIL"
        error = (
            f"Account sign integrity broken: {mismatch_count} account(s) "
            f"with unexpected sign flip, total diff={total_difference:,.2f}"
        )
    else:
        ok = False; severity = "WARNING"
        error = (
            f"Minor sign anomalies: {mismatch_count} account(s), "
            f"total diff={total_difference:,.2f} (below materiality)"
        )

    return {
        "account_continuity_ok":  ok,
        "periods_checked":        len(stmts) - 1,
        "mismatch_count":         mismatch_count,
        "total_difference":       total_difference,
        "top_mismatches":         top_mismatches,
        "continuity_errors":      [m["error"] for m in mismatches],
        "severity":               severity,
        "error":                  error,
    }


# ── Check 4: Branch rollup reconciliation (STRICT) ───────────────────────────

def check_branch_rollup(
    main_stmts: list[dict],
    branch_stmts_list: list[list[dict]],
    tolerance_pct: float = 1.0,          # Step 2.5: tightened from 10% to 1%
    blocking_threshold_pct: float = 5.0, # above this → blocking=True
) -> dict:
    """
    STRICT: sum(branches) must equal consolidated within tolerance_pct.
    Divergence > tolerance_pct → FAIL.
    Divergence > blocking_threshold_pct → blocking=True.

    Note on multi-legal-entity structures:
      If branches are SEPARATE legal entities (not sub-branches of one ledger),
      divergence is structurally expected and must be documented explicitly via
      the consolidation_note field. The validation still flags it — callers
      must decide if it is expected or an error.
    """
    if not main_stmts or not branch_stmts_list:
        return {
            "branch_rollup_ok": None,
            "branch_count":     0,
            "rollup_gaps":      [],
            "blocking":         False,
            "severity":         "PASS",
            "error":            None,
        }

    m_is     = main_stmts[-1].get("income_statement", {})
    m_rev    = _r2(m_is.get("revenue",      {}).get("total") or 0)
    m_exp    = _r2(m_is.get("expenses",     {}).get("total") or 0)
    m_gp     = _r2(m_is.get("gross_profit") or 0)
    m_np     = _r2(m_is.get("net_profit")   or 0)
    latest_p = main_stmts[-1].get("period", "")

    b_rev = b_exp = b_gp = b_np = 0.0
    matched = 0
    for b_stmts in branch_stmts_list:
        if not b_stmts:
            continue
        b_stmt  = next((s for s in reversed(b_stmts) if s.get("period") == latest_p), b_stmts[-1])
        b_is    = b_stmt.get("income_statement", {})
        b_rev  += _r2(b_is.get("revenue",      {}).get("total") or 0)
        b_exp  += _r2(b_is.get("expenses",     {}).get("total") or 0)
        b_gp   += _r2(b_is.get("gross_profit") or 0)
        b_np   += _r2(b_is.get("net_profit")   or 0)
        matched += 1

    gaps     = []
    blocking = False
    for label, m_v, b_v in [
        ("revenue",      m_rev, b_rev),
        ("expenses",     m_exp, b_exp),
        ("gross_profit", m_gp,  b_gp),
        ("net_profit",   m_np,  b_np),
    ]:
        if not m_v:
            continue
        pct = _pct_gap(m_v, b_v)
        if pct is not None and abs(pct) > tolerance_pct:
            gap_entry = {
                "metric":     label,
                "main":       m_v,
                "branch_sum": _r2(b_v),
                "diff":       _r2(b_v - m_v),
                "pct_gap":    pct,
                "blocking":   abs(pct) > blocking_threshold_pct,
            }
            gaps.append(gap_entry)
            if gap_entry["blocking"]:
                blocking = True

    ok = len(gaps) == 0
    severity = "PASS" if ok else ("FAIL" if blocking else "WARNING")

    return {
        "branch_rollup_ok":    ok,
        "branch_count":        matched,
        "period_compared":     latest_p,
        "rollup_gaps":         gaps,
        "blocking":            blocking,
        "severity":            severity,
        "tolerance_pct":       tolerance_pct,
        "error": None if ok else (
            f"Branch rollup diverges from consolidated [{latest_p}]: "
            + ", ".join(
                f"{g['metric']} {g['pct_gap']:+.1f}% (diff={g['diff']:,.0f})"
                for g in gaps
            )
        ),
    }


# ── Check 5: Approximation detection ─────────────────────────────────────────

def check_approximations(stmts: list[dict]) -> dict:
    """
    STRICT: if current_assets or current_liabilities were approximated
    (i.e. fallback to total used), mark as detected and return which periods
    are affected. Callers must null-out current_ratio and quick_ratio.
    """
    affected_periods = []
    ca_approx_periods = []
    cl_approx_periods = []

    for s in stmts:
        bs = s.get("balance_sheet", {})
        p  = s.get("period", "?")
        if bs.get("current_assets_approximated"):
            ca_approx_periods.append(p)
            affected_periods.append(p)
        if bs.get("current_liabilities_approximated"):
            cl_approx_periods.append(p)
            if p not in affected_periods:
                affected_periods.append(p)

    detected = len(affected_periods) > 0
    return {
        "approximation_detected":          detected,
        "current_assets_approx_periods":   ca_approx_periods,
        "current_liabilities_approx_periods": cl_approx_periods,
        "affected_periods":                affected_periods,
        "severity":                        "WARNING" if detected else "PASS",
        "warning": None if not detected else (
            f"Approximated current assets/liabilities in periods: "
            f"{', '.join(affected_periods)}. "
            f"current_ratio and quick_ratio are invalid for these periods."
        ),
    }


# ── Master validation block ───────────────────────────────────────────────────

def build_validation_block(
    stmts:             list[dict],
    tb_debit:          Optional[float]  = None,
    tb_credit:         Optional[float]  = None,
    branch_stmts_list: Optional[list]   = None,
) -> dict:
    """
    Build the complete validation block.

    Severity rules:
      FAIL    → any FAIL check or blocking branch rollup
      WARNING → only non-blocking anomalies (approximations, etc.)
      PASS    → all checks clear

    The 'blocking' flag means the data has a confirmed accounting error
    that must prevent downstream financial conclusions.
    """
    errors:   List[str] = []
    warnings: List[str] = []
    details               = {}

    # ── TB balance ────────────────────────────────────────────────────────────
    if tb_debit is not None and tb_credit is not None:
        tb_chk = check_tb_balanced(tb_debit, tb_credit)
    else:
        tb_chk = {
            "trial_balance_balanced": None,
            "severity": "WARNING",
            "error":    None,
            "warning":  "TB debit/credit totals not provided — check skipped",
        }
    details["tb_balance"] = tb_chk
    if tb_chk.get("error"):    errors.append(tb_chk["error"])
    if tb_chk.get("warning"):  warnings.append(tb_chk["warning"])

    # ── BS equation ───────────────────────────────────────────────────────────
    if stmts:
        bs_chk = check_bs_balanced(stmts[-1])
    else:
        bs_chk = {
            "balance_sheet_balanced": None, "severity": "FAIL",
            "error": "No statements provided",
        }
    details["bs_balance"] = bs_chk
    if bs_chk.get("error"):    errors.append(bs_chk["error"])

    # ── Account continuity ────────────────────────────────────────────────────
    cont_chk = check_account_continuity(stmts)
    details["continuity"] = cont_chk
    if cont_chk.get("error"):  errors.append(cont_chk["error"])

    # ── Branch rollup ─────────────────────────────────────────────────────────
    if branch_stmts_list is not None:
        rollup_chk = check_branch_rollup(stmts, branch_stmts_list)
    else:
        rollup_chk = {
            "branch_rollup_ok": None, "blocking": False,
            "severity": "PASS", "error": None,
        }
    details["branch_rollup"] = rollup_chk
    if rollup_chk.get("error"):   errors.append(rollup_chk["error"])

    # ── Approximation check ───────────────────────────────────────────────────
    approx_chk = check_approximations(stmts)
    details["approximations"] = approx_chk
    if approx_chk.get("warning"): warnings.append(approx_chk["warning"])

    # ── Severity aggregation ──────────────────────────────────────────────────
    tb_ok    = tb_chk.get("trial_balance_balanced")
    bs_ok    = bs_chk.get("balance_sheet_balanced")
    cont_ok  = cont_chk.get("account_continuity_ok")
    rollup_ok= rollup_chk.get("branch_rollup_ok")
    approx   = approx_chk.get("approximation_detected", False)
    blocking = rollup_chk.get("blocking", False) or (tb_ok is False) or (bs_ok is False) or (cont_ok is False)

    if errors or blocking:
        status = "FAIL"
    elif warnings or approx:
        status = "WARNING"
    else:
        status = "PASS"

    all_pass = (
        (tb_ok   is None or tb_ok)   and
        (bs_ok   is None or bs_ok)   and
        (cont_ok is None or cont_ok) and
        (rollup_ok is None or rollup_ok) and
        not approx
    )

    return {
        "status":                   status,
        "blocking":                 blocking,
        "all_pass":                 all_pass,
        "trial_balance_balanced":   tb_ok,
        "balance_sheet_balanced":   bs_ok,
        "account_continuity_ok":    cont_ok,
        "branch_rollup_ok":         rollup_ok,
        "approximation_detected":   approx,
        "errors":                   errors,
        "warnings":                 warnings,
        "details":                  details,
    }
