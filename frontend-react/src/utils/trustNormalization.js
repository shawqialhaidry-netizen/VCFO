const TRUST_STATUSES = ['good', 'warning', 'risk', 'unavailable']

function isObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value)
}

function get(obj, path, fallback = undefined) {
  return path.reduce((cur, key) => (isObject(cur) ? cur[key] : undefined), obj) ?? fallback
}

function normalizeRawStatus(status) {
  const raw = String(status || '').toLowerCase()
  if (raw === 'proven' || raw === 'good' || raw === 'pass' || raw === 'ok') return 'good'
  if (raw === 'partial' || raw === 'estimated' || raw === 'warning') return 'warning'
  if (raw === 'mismatch' || raw === 'failed' || raw === 'fail' || raw === 'error' || raw === 'risk') return 'risk'
  if (raw === 'missing' || raw === 'unavailable' || raw === 'unknown' || raw === 'neutral') return 'unavailable'
  return 'unavailable'
}

function statusRank(status) {
  if (status === 'risk') return 4
  if (status === 'warning') return 3
  if (status === 'good') return 2
  return 1
}

function strongestStatus(statuses) {
  const valid = statuses.filter((status) => TRUST_STATUSES.includes(status))
  if (!valid.length) return 'unavailable'
  return valid.reduce((strongest, status) => (
    statusRank(status) > statusRank(strongest) ? status : strongest
  ), 'unavailable')
}

function check(key, status, source = {}) {
  return {
    key,
    status: TRUST_STATUSES.includes(status) ? status : 'unavailable',
    label_key: `trust_check_${key}`,
    ...source,
  }
}

function warning(key, status = 'warning', source = {}) {
  return {
    key,
    status,
    label_key: `trust_warning_${key}`,
    ...source,
  }
}

function hasText(value, needles) {
  const text = String(value || '').toLowerCase()
  return needles.some((needle) => text.includes(needle))
}

function detectSyntheticEquity(statements, integrity) {
  return Boolean(
    get(integrity, ['net_income', 'income_statement_to_equity_handling', 'synthetic_equity_support']) ||
    get(integrity, ['equity', 'synthetic_equity_support']) ||
    get(statements, ['balance_sheet', 'equity', 'synthetic_equity_support'])
  )
}

function detectEquityWarning(statements, integrity) {
  return (
    get(integrity, ['net_income', 'income_statement_to_equity_handling', 'warning']) ||
    get(integrity, ['equity', 'warning']) ||
    get(statements, ['balance_sheet', 'equity', 'equity_integrity_warning']) ||
    null
  )
}

function detectPartialCashflow(cashflow, integrity) {
  const flags = cashflow?.flags || {}
  const meta = cashflow?.statement_meta || {}
  return Boolean(
    flags.operating_partial ||
    flags.investing_partial ||
    flags.financing_partial ||
    flags.single_period ||
    flags.wc_approximated ||
    flags.da_approximated ||
    hasText(meta.operating_cashflow_basis, ['partial', 'estimated', 'single', 'approx']) ||
    hasText(get(integrity, ['cash', 'opening_to_ending_continuity', 'operating_cashflow_basis']), ['partial', 'estimated', 'single', 'approx'])
  )
}

function detectWorkingCapitalUnavailable(cashflow, integrity) {
  const flags = cashflow?.flags || {}
  const meta = cashflow?.statement_meta || {}
  const integrityBasis = get(integrity, ['cash', 'opening_to_ending_continuity', 'working_capital_basis'])
  return Boolean(
    flags.wc_unavailable ||
    hasText(meta.working_capital_basis, ['unavailable', 'missing', 'no_prior']) ||
    hasText(integrityBasis, ['unavailable', 'missing', 'no_prior'])
  )
}

function detectReconciliationMismatch(cashflow, integrity) {
  const cashToBs = get(integrity, ['cash', 'ending_cash_to_balance_sheet_cash'])
  const continuity = get(integrity, ['cash', 'opening_to_ending_continuity'])
  return Boolean(
    cashflow?.reconciles === false ||
    continuity?.reconciles === false ||
    normalizeRawStatus(cashToBs?.status) === 'risk' ||
    (normalizeRawStatus(cashToBs?.status) === 'warning' && cashToBs?.cashflow_ending_cash != null && cashToBs?.balance_sheet_cash != null) ||
    (normalizeRawStatus(continuity?.status) === 'warning' && continuity?.reconciles === false)
  )
}

export function normalizeFinancialTrust(input = {}) {
  const statements = input?.statements || {}
  const cashflow = input?.cashflow || {}
  const integrity = input?.cross_statement_integrity || statements?.cross_statement_integrity || {}

  const syntheticEquity = detectSyntheticEquity(statements, integrity)
  const equityWarning = detectEquityWarning(statements, integrity)
  const partialCashflow = detectPartialCashflow(cashflow, integrity)
  const workingCapitalUnavailable = detectWorkingCapitalUnavailable(cashflow, integrity)
  const reconciliationMismatch = detectReconciliationMismatch(cashflow, integrity)

  const netIncomeToCashflow = get(integrity, ['net_income', 'income_statement_to_cashflow_start'])
  const incomeToEquity = get(integrity, ['net_income', 'income_statement_to_equity_handling'])
  const endingCashToBalanceSheet = get(integrity, ['cash', 'ending_cash_to_balance_sheet_cash'])
  const openingToEnding = get(integrity, ['cash', 'opening_to_ending_continuity'])
  const equity = get(integrity, ['equity'])

  const cashStatus = reconciliationMismatch
    ? 'risk'
    : strongestStatus([
        normalizeRawStatus(endingCashToBalanceSheet?.status),
        normalizeRawStatus(openingToEnding?.status),
      ])

  const checks = [
    check('net_income_to_cashflow', normalizeRawStatus(netIncomeToCashflow?.status), {
      source_status: netIncomeToCashflow?.status || null,
    }),
    check('income_to_equity', syntheticEquity ? 'risk' : normalizeRawStatus(incomeToEquity?.status), {
      source_status: incomeToEquity?.status || null,
    }),
    check('cash_reconciliation', cashStatus, {
      source_status: {
        ending_cash_to_balance_sheet_cash: endingCashToBalanceSheet?.status || null,
        opening_to_ending_continuity: openingToEnding?.status || null,
      },
    }),
    check('equity_integrity', syntheticEquity ? 'risk' : normalizeRawStatus(equity?.status), {
      source_status: equity?.status || null,
    }),
  ]

  const warnings = []
  if (partialCashflow) warnings.push(warning('cashflow_partial'))
  if (workingCapitalUnavailable) warnings.push(warning('working_capital_unavailable'))
  if (syntheticEquity) warnings.push(warning('synthetic_equity_support', 'risk'))
  if (equityWarning && !syntheticEquity) warnings.push(warning('equity_integrity_warning'))
  if (reconciliationMismatch) warnings.push(warning('reconciliation_mismatch', 'risk'))

  const overallFromChecks = strongestStatus(checks.map((item) => item.status))
  const overallFromWarnings = strongestStatus(warnings.map((item) => item.status))
  const overallStatus = strongestStatus([overallFromChecks, overallFromWarnings])

  return {
    overall_status: overallStatus,
    status: overallStatus,
    source_status: integrity?.status || null,
    checks,
    warnings,
    meta: {
      has_integrity: isObject(integrity) && Object.keys(integrity).length > 0,
      has_cashflow: isObject(cashflow) && Object.keys(cashflow).length > 0,
    },
  }
}

export default normalizeFinancialTrust
