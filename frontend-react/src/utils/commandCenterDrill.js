/**
 * Maps Command Center drill context → Analysis.jsx tab (`tab` state).
 */

export function analysisTabFromDrill({ type, domain } = {}) {
  const d = String(domain || '')
  if (d === 'liquidity' || d === 'profitability' || d === 'efficiency') return d
  if (d === 'leverage' || d === 'growth') return 'efficiency'
  const t = String(type || '')
  if (
    ['revenue', 'expenses', 'net_profit', 'net_margin', 'cashflow', 'working_capital'].includes(t)
  ) {
    return 'profitability'
  }
  return 'overview'
}
