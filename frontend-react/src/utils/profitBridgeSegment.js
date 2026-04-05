/**
 * Profit path bridge segment ↔ structured income statement variance line + KPI trend chart type.
 */

export const PROFIT_BRIDGE_VARIANCE_LINE_BY_KEY = {
  revenue_change: 'revenue',
  cogs_change: 'cogs',
  opex_change: 'opex',
  operating_profit_change: 'operating_profit',
  net_profit_change: 'net_profit',
}

/**
 * @param {string} bridgeKey — e.g. revenue_change
 * @returns {string} kpiType for ExecutiveKpiTrendChart
 */
export function bridgeKeyToKpiTrendType(bridgeKey) {
  const m = {
    revenue_change: 'revenue',
    cogs_change: 'expenses',
    opex_change: 'expenses',
    operating_profit_change: 'net_profit',
    net_profit_change: 'net_profit',
  }
  return m[bridgeKey] || 'net_profit'
}

/**
 * @param {Array<{ delta?: number | null }>} rows — bridge strip rows with finite delta
 * @returns {number}
 */
export function profitBridgeSumAbsDelta(rows) {
  let s = 0
  for (const r of rows) {
    const d = r?.delta
    if (d != null && Number.isFinite(Number(d))) s += Math.abs(Number(d))
  }
  return s > 0 ? s : 1e-9
}

/**
 * @param {{
 *   bridgeKey: string,
 *   labelKey: string,
 *   sense: string,
 *   delta: number | null | undefined,
 *   delta_pct: number | null | undefined,
 *   variance?: Record<string, unknown> | null,
 *   varianceMeta?: Record<string, unknown> | null,
 *   bridgeInterpretation?: Record<string, unknown> | null,
 *   sumAbsDelta: number,
 * }} p
 */
export function buildProfitBridgeSegmentPayload(p) {
  const vk = PROFIT_BRIDGE_VARIANCE_LINE_BY_KEY[p.bridgeKey]
  const vline = vk && p.variance && typeof p.variance === 'object' ? p.variance[vk] || {} : {}
  const absD = Math.abs(Number(p.delta))
  const weightPct = p.sumAbsDelta > 0 ? Math.round((absD / p.sumAbsDelta) * 1000) / 10 : 0
  return {
    bridgeKey: p.bridgeKey,
    varianceLineKey: vk || '',
    labelKey: p.labelKey,
    sense: p.sense,
    delta: p.delta,
    delta_pct: p.delta_pct,
    varianceLine: {
      current: vline.current ?? null,
      previous: vline.previous ?? null,
      delta: vline.delta ?? null,
      delta_pct: vline.delta_pct ?? null,
    },
    latestPeriod: p.varianceMeta?.latest_period ?? null,
    previousPeriod: p.varianceMeta?.previous_period ?? null,
    bridgeInterpretation: p.bridgeInterpretation && typeof p.bridgeInterpretation === 'object' ? p.bridgeInterpretation : null,
    impactWeightPct: weightPct,
    kpiTrendType: bridgeKeyToKpiTrendType(p.bridgeKey),
  }
}
