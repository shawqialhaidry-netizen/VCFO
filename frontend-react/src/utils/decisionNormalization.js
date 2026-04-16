import { normalizeFinancialTrust } from './trustNormalization.js'

const CATEGORIES = [
  'liquidity',
  'profitability',
  'expense_control',
  'revenue_quality',
  'balance_sheet_capital',
  'data_trust_governance',
]

const SEVERITY_RANK = { low: 1, medium: 2, high: 3, critical: 4 }
const TRUST_RANK = { good: 1, unavailable: 2, warning: 3, risk: 4 }

function isObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value)
}

function num(value) {
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

function get(obj, path, fallback = undefined) {
  return path.reduce((cur, key) => (isObject(cur) ? cur[key] : undefined), obj) ?? fallback
}

function firstDefined(...values) {
  for (const value of values) {
    if (value !== undefined && value !== null) return value
  }
  return null
}

function severityFromStatus(status, fallback = 'medium') {
  const raw = String(status || '').toLowerCase()
  if (raw === 'critical' || raw === 'risk' || raw === 'high') return 'high'
  if (raw === 'warning' || raw === 'medium' || raw === 'elevated') return 'medium'
  if (raw === 'good' || raw === 'low' || raw === 'ok') return 'low'
  return fallback
}

function confidenceFromTrust(trustStatus) {
  if (trustStatus === 'good') return 'high'
  if (trustStatus === 'warning') return 'medium'
  return 'low'
}

function hasTrustWarning(trust, key) {
  return Array.isArray(trust?.warnings) && trust.warnings.some((item) => item?.key === key)
}

function makeEvidence(source, labelKey, value, extra = {}) {
  return {
    source,
    label_key: labelKey,
    value,
    ...extra,
  }
}

function trustGate(category, trust) {
  const trustStatus = trust?.overall_status || 'unavailable'
  const reconciliationRisk = hasTrustWarning(trust, 'reconciliation_mismatch')
  const partialCashflow = hasTrustWarning(trust, 'cashflow_partial')
  const wcUnavailable = hasTrustWarning(trust, 'working_capital_unavailable')
  const syntheticEquity = hasTrustWarning(trust, 'synthetic_equity_support')

  if (category === 'data_trust_governance') {
    return { trust_status: trustStatus, requires_review: false, blocked_by_trust: false }
  }

  if (category === 'liquidity') {
    return {
      trust_status: trustStatus,
      requires_review: trustStatus !== 'good' || partialCashflow || wcUnavailable,
      blocked_by_trust: reconciliationRisk,
    }
  }

  if (category === 'balance_sheet_capital') {
    return {
      trust_status: trustStatus,
      requires_review: trustStatus !== 'good' || syntheticEquity,
      blocked_by_trust: reconciliationRisk && syntheticEquity,
    }
  }

  return {
    trust_status: trustStatus,
    requires_review: trustStatus === 'warning' || trustStatus === 'risk',
    blocked_by_trust: trustStatus === 'risk' && reconciliationRisk,
  }
}

function makeDecision({
  id,
  category,
  severity = 'medium',
  titleKey,
  summaryKey,
  actionKey,
  rationaleKeys = [],
  evidence = [],
  trust,
}) {
  const gate = trustGate(category, trust)
  return {
    id,
    category,
    severity,
    confidence: gate.blocked_by_trust ? 'low' : confidenceFromTrust(gate.trust_status),
    trust_status: gate.trust_status,
    title_key: titleKey || `decision_${id}_title`,
    summary_key: summaryKey || `decision_${id}_summary`,
    action_key: actionKey || `decision_${id}_action`,
    rationale_keys: rationaleKeys,
    evidence,
    blocked_by_trust: gate.blocked_by_trust,
    requires_review: gate.requires_review,
  }
}

function collectTrustGovernanceDecisions(trust) {
  const warnings = Array.isArray(trust?.warnings) ? trust.warnings : []
  return warnings.map((item) => makeDecision({
    id: `data_trust_${item.key}`,
    category: 'data_trust_governance',
    severity: item.status === 'risk' ? 'high' : 'medium',
    titleKey: `decision_data_trust_${item.key}_title`,
    summaryKey: `decision_data_trust_${item.key}_summary`,
    actionKey: `decision_data_trust_${item.key}_action`,
    rationaleKeys: [item.label_key || `trust_warning_${item.key}`],
    evidence: [makeEvidence(`trust.warnings.${item.key}`, item.label_key || `trust_warning_${item.key}`, item.status)],
    trust,
  }))
}

function collectLiquidityDecision(input, trust) {
  const kpis = input.kpis || input.kpi_block?.kpis || {}
  const statements = input.statements || {}
  const cashflow = input.cashflow || {}
  const ratios = input.intelligence?.ratios || input.analysis?.ratios || {}
  const wc = num(firstDefined(
    kpis.working_capital?.value,
    cashflow.working_capital,
    statements.balance_sheet?.working_capital,
    statements.summary?.working_capital,
    ratios.liquidity?.working_capital?.value,
    ratios.liquidity?.working_capital,
  ))
  const ocf = num(firstDefined(cashflow.operating_cashflow, statements.cashflow?.operating_cashflow, statements.summary?.operating_cashflow))
  const currentRatioStatus = get(ratios, ['liquidity', 'current_ratio', 'status'])
  const evidence = []
  const rationaleKeys = []

  if (wc != null && wc < 0) {
    evidence.push(makeEvidence('working_capital', 'working_capital', wc))
    rationaleKeys.push('decision_reason_negative_working_capital')
  }
  if (ocf != null && ocf < 0) {
    evidence.push(makeEvidence('cashflow.operating_cashflow', 'cashflow_operating', ocf))
    rationaleKeys.push('decision_reason_negative_operating_cashflow')
  }
  if (['warning', 'risk', 'critical'].includes(String(currentRatioStatus || '').toLowerCase())) {
    evidence.push(makeEvidence('intelligence.ratios.liquidity.current_ratio.status', 'intel_current_ratio', currentRatioStatus))
    rationaleKeys.push('decision_reason_current_ratio_pressure')
  }
  if (!evidence.length) return null

  return makeDecision({
    id: 'liquidity_cash_protection',
    category: 'liquidity',
    severity: ocf != null && ocf < 0 && wc != null && wc < 0 ? 'high' : severityFromStatus(currentRatioStatus, 'medium'),
    rationaleKeys,
    evidence,
    trust,
  })
}

function collectProfitabilityDecision(input, trust) {
  const kpis = input.kpis || input.kpi_block?.kpis || {}
  const statements = input.statements || {}
  const ratios = input.intelligence?.ratios || input.analysis?.ratios || {}
  const netProfit = num(firstDefined(kpis.net_profit?.value, statements.income_statement?.net_profit, statements.summary?.net_profit))
  const netProfitMom = num(kpis.net_profit?.mom_pct)
  const netMarginStatus = get(ratios, ['profitability', 'net_margin_pct', 'status'])
  const evidence = []
  const rationaleKeys = []

  if (netProfit != null && netProfit < 0) {
    evidence.push(makeEvidence('net_profit', 'kpi_net_profit', netProfit))
    rationaleKeys.push('decision_reason_negative_net_profit')
  }
  if (netProfitMom != null && netProfitMom < 0) {
    evidence.push(makeEvidence('kpi_block.kpis.net_profit.mom_pct', 'mom_label', netProfitMom))
    rationaleKeys.push('decision_reason_profit_declining')
  }
  if (['warning', 'risk', 'critical'].includes(String(netMarginStatus || '').toLowerCase())) {
    evidence.push(makeEvidence('intelligence.ratios.profitability.net_margin_pct.status', 'net_margin', netMarginStatus))
    rationaleKeys.push('decision_reason_margin_pressure')
  }
  if (!evidence.length) return null

  return makeDecision({
    id: 'profitability_margin_repair',
    category: 'profitability',
    severity: netProfit != null && netProfit < 0 ? 'high' : severityFromStatus(netMarginStatus, 'medium'),
    rationaleKeys,
    evidence,
    trust,
  })
}

function collectExpenseDecision(input, trust) {
  const kpis = input.kpis || input.kpi_block?.kpis || {}
  const expenseIntel = input.expense_intelligence || input.expenseIntelligence || {}
  const expenseMom = num(kpis.expenses?.mom_pct)
  const expenseRatio = num(firstDefined(expenseIntel.expense_ratio, expenseIntel.expense_ratio_pct))
  const anomalies = Array.isArray(expenseIntel.anomalies) ? expenseIntel.anomalies : []
  const evidence = []
  const rationaleKeys = []

  if (expenseMom != null && expenseMom > 0) {
    evidence.push(makeEvidence('kpi_block.kpis.expenses.mom_pct', 'kpi_total_expenses', expenseMom))
    rationaleKeys.push('decision_reason_expenses_rising')
  }
  if (expenseRatio != null && expenseRatio > 0) {
    evidence.push(makeEvidence('expense_intelligence.expense_ratio', 'expense_ratio_short', expenseRatio))
    rationaleKeys.push('decision_reason_expense_ratio_available')
  }
  if (anomalies.length > 0) {
    evidence.push(makeEvidence('expense_intelligence.anomalies', 'expense_alerts_title', anomalies.length))
    rationaleKeys.push('decision_reason_expense_anomalies')
  }
  if (!evidence.length) return null

  return makeDecision({
    id: 'expense_control_review',
    category: 'expense_control',
    severity: anomalies.length > 1 ? 'high' : 'medium',
    rationaleKeys,
    evidence,
    trust,
  })
}

function collectRevenueDecision(input, trust) {
  const kpis = input.kpis || input.kpi_block?.kpis || {}
  const trends = input.intelligence?.trends || input.analysis?.trends || {}
  const revenueMom = num(kpis.revenue?.mom_pct)
  const revenueYoy = num(kpis.revenue?.yoy_pct ?? trends.revenue?.yoy_change)
  const revenueDirection = String(trends.revenue?.direction || '').toLowerCase()
  const evidence = []
  const rationaleKeys = []

  if (revenueMom != null && revenueMom < 0) {
    evidence.push(makeEvidence('kpi_block.kpis.revenue.mom_pct', 'kpi_total_revenue', revenueMom))
    rationaleKeys.push('decision_reason_revenue_mom_decline')
  }
  if (revenueYoy != null && revenueYoy < 0) {
    evidence.push(makeEvidence('revenue.yoy_pct', 'yoy_label', revenueYoy))
    rationaleKeys.push('decision_reason_revenue_yoy_decline')
  }
  if (revenueDirection === 'down') {
    evidence.push(makeEvidence('intelligence.trends.revenue.direction', 'intel_revenue', revenueDirection))
    rationaleKeys.push('decision_reason_revenue_trend_down')
  }
  if (!evidence.length) return null

  return makeDecision({
    id: 'revenue_quality_review',
    category: 'revenue_quality',
    severity: revenueMom != null && revenueMom < 0 && revenueYoy != null && revenueYoy < 0 ? 'high' : 'medium',
    rationaleKeys,
    evidence,
    trust,
  })
}

function collectBalanceSheetDecision(input, trust) {
  const statements = input.statements || {}
  const ratios = input.intelligence?.ratios || input.analysis?.ratios || {}
  const equity = num(firstDefined(
    statements.balance_sheet?.equity?.total,
    statements.balance_sheet?.equity,
    statements.summary?.equity,
  ))
  const debtStatus = firstDefined(
    get(ratios, ['leverage', 'debt_to_equity', 'status']),
    get(ratios, ['leverage', 'debt_ratio', 'status']),
  )
  const syntheticEquity = hasTrustWarning(trust, 'synthetic_equity_support')
  const evidence = []
  const rationaleKeys = []

  if (equity != null && equity < 0) {
    evidence.push(makeEvidence('statements.balance_sheet.equity', 'stmt_hier_equity', equity))
    rationaleKeys.push('decision_reason_negative_equity')
  }
  if (['warning', 'risk', 'critical'].includes(String(debtStatus || '').toLowerCase())) {
    evidence.push(makeEvidence('intelligence.ratios.leverage.status', 'leverage', debtStatus))
    rationaleKeys.push('decision_reason_leverage_pressure')
  }
  if (syntheticEquity) {
    evidence.push(makeEvidence('trust.warnings.synthetic_equity_support', 'trust_warning_synthetic_equity_support', 'risk'))
    rationaleKeys.push('trust_warning_synthetic_equity_support')
  }
  if (!evidence.length) return null

  return makeDecision({
    id: 'balance_sheet_capital_review',
    category: 'balance_sheet_capital',
    severity: syntheticEquity || (equity != null && equity < 0) ? 'high' : severityFromStatus(debtStatus, 'medium'),
    rationaleKeys,
    evidence,
    trust,
  })
}

function sortDecisions(a, b) {
  const blockedDelta = Number(a.blocked_by_trust) - Number(b.blocked_by_trust)
  if (blockedDelta !== 0) return blockedDelta
  const severityDelta = (SEVERITY_RANK[b.severity] || 0) - (SEVERITY_RANK[a.severity] || 0)
  if (severityDelta !== 0) return severityDelta
  return (TRUST_RANK[b.trust_status] || 0) - (TRUST_RANK[a.trust_status] || 0)
}

export function normalizeDecisions(input = {}) {
  const trust = input.trust || normalizeFinancialTrust({
    statements: input.statements,
    cashflow: input.cashflow,
    cross_statement_integrity: input.cross_statement_integrity,
  })

  const candidates = [
    collectLiquidityDecision(input, trust),
    collectProfitabilityDecision(input, trust),
    collectExpenseDecision(input, trust),
    collectRevenueDecision(input, trust),
    collectBalanceSheetDecision(input, trust),
    ...collectTrustGovernanceDecisions(trust),
  ].filter(Boolean)

  const decisions = candidates.sort(sortDecisions)

  return {
    decisions,
    summary: {
      primary_decision_id: decisions[0]?.id || null,
      decision_count: decisions.length,
      high_count: decisions.filter((item) => item.severity === 'high' || item.severity === 'critical').length,
      blocked_count: decisions.filter((item) => item.blocked_by_trust).length,
      trust_limited_count: decisions.filter((item) => item.requires_review || item.blocked_by_trust).length,
      categories: CATEGORIES,
    },
    trust,
  }
}

export default normalizeDecisions
