/**
 * Derive chart-ready series from existing executive payload only (no API).
 */

export function kpiSeriesForType(kpiType, main) {
  const kb = main?.kpi_block
  const periods = kb?.periods || []
  const series = kb?.series || {}
  const cf = main?.cashflow?.series

  const map = {
    revenue: series.revenue,
    expenses: series.expenses,
    net_profit: series.net_profit,
    net_margin: series.net_margin,
    cashflow: cf?.operating_cashflow,
    working_capital: null,
  }
  const values = map[kpiType]
  if (!values || !periods.length) return { periods: [], values: [], label: kpiType }
  const n = Math.min(periods.length, values.length)
  return {
    periods: periods.slice(-n),
    values: values.slice(-n).map((v) => (v == null || !Number.isFinite(Number(v)) ? null : Number(v))),
    label: kpiType,
  }
}

export function dualSeriesCashflow(main) {
  const cf = main?.cashflow?.series
  if (!cf?.periods?.length) return null
  return {
    periods: cf.periods,
    ocf: (cf.operating_cashflow || []).map((v) => (v == null ? null : Number(v))),
    np: (cf.net_profit || []).map((v) => (v == null ? null : Number(v))),
  }
}

export function branchComparisonBars(comparativeIntelligence) {
  const eff = comparativeIntelligence?.efficiency_ranking?.by_expense_pct_of_revenue_desc
  if (!Array.isArray(eff) || !eff.length) return []
  return eff.slice(0, 8).map((b) => ({
    name: b.branch_name || '—',
    value: Number(b.expense_pct_of_revenue) || 0,
  }))
}

/** Simple P&L bridge from latest statement bundle income_statement. */
export function waterfallFromStatements(statements) {
  const is_ = statements?.income_statement
  if (!is_ || typeof is_ !== 'object') return []
  const rev = Number(is_.revenue?.total ?? is_.revenue ?? 0) || 0
  const cogs = Number(is_.cogs?.total ?? is_.cogs ?? 0) || 0
  const opex = Number(is_.expenses?.total ?? is_.expenses ?? 0) || 0
  const np = Number(is_.net_profit ?? 0) || 0
  if (rev <= 0 && np === 0) return []
  return [
    { key: 'rev', label: 'revenue', amount: rev, type: 'start' },
    { key: 'cogs', label: 'cogs', amount: -cogs, type: 'neg' },
    { key: 'opex', label: 'opex', amount: -opex, type: 'neg' },
    { key: 'np', label: 'net_profit', amount: np, type: 'end' },
  ]
}
