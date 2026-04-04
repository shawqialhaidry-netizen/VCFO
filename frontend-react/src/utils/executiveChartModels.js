/**
 * Map executive GET /executive `data` fields into chart-ready rows.
 * Only reads kpi_block, cashflow.series, comparative_intelligence — no new formulas beyond period deltas.
 */

export function extractKpiTrendPoints(kpiBlock, cashflow, kpiType) {
  if (kpiType === 'cashflow') {
    const s = cashflow?.series
    if (!s?.periods?.length) return null
    const ocf = s.operating_cashflow || []
    const out = []
    for (let i = 0; i < s.periods.length; i++) {
      const v = ocf[i]
      if (v != null && Number.isFinite(Number(v))) {
        out.push({
          period: String(s.periods[i] || '').slice(0, 7),
          value: Number(v),
        })
      }
    }
    return out.length >= 2 ? out : null
  }
  const kb = kpiBlock || {}
  const periods = kb.periods || []
  const key =
    kpiType === 'revenue'
      ? 'revenue'
      : kpiType === 'expenses'
        ? 'expenses'
        : kpiType === 'net_profit'
          ? 'net_profit'
          : kpiType === 'net_margin'
            ? 'net_margin'
            : null
  if (!key || periods.length < 2) return null
  const ser = kb.series?.[key] || []
  const out = []
  for (let i = 0; i < periods.length; i++) {
    const v = ser[i]
    if (v != null && Number.isFinite(Number(v))) {
      out.push({
        period: String(periods[i] || '').slice(0, 7),
        value: Number(v),
      })
    }
  }
  return out.length >= 2 ? out : null
}

/**
 * Latest vs previous period in kpi_block: revenue Δ, total cost Δ (expenses series), net profit Δ.
 * Residual = dNP - dRev + dExp captures other P&L lines (tax, other income) using only existing series.
 */
export function extractProfitBridge(kpiBlock) {
  const kb = kpiBlock || {}
  const periods = kb.periods || []
  const rev = kb.series?.revenue || []
  const exp = kb.series?.expenses || []
  const np = kb.series?.net_profit || []
  if (periods.length < 2 || rev.length < 2 || exp.length < 2 || np.length < 2) return null
  const i = rev.length - 1
  const dRev = Number(rev[i] ?? 0) - Number(rev[i - 1] ?? 0)
  const dExp = Number(exp[i] ?? 0) - Number(exp[i - 1] ?? 0)
  const dNP = Number(np[i] ?? 0) - Number(np[i - 1] ?? 0)
  const residual = dNP - dRev + dExp
  const steps = [
    { id: 'rev', value: dRev },
    { id: 'cost', value: -dExp },
  ]
  const resAbs = Math.abs(residual)
  const scale = Math.max(Math.abs(dNP), Math.abs(dRev), Math.abs(dExp), 1)
  if (Number.isFinite(residual) && resAbs >= Math.max(1, scale * 0.02)) {
    steps.push({ id: 'other', value: residual })
  }
  steps.push({ id: 'net', value: dNP })
  return {
    steps,
    periodPrev: periods[i - 1],
    periodLast: periods[i],
  }
}

/**
 * Align revenue, expenses (COGS+OpEx), net_profit per period for multi-line chart.
 */
export function extractTripleTrendRows(kpiBlock) {
  const kb = kpiBlock || {}
  const periods = kb.periods || []
  const rev = kb.series?.revenue || []
  const exp = kb.series?.expenses || []
  const np = kb.series?.net_profit || []
  const n = Math.min(periods.length, rev.length, exp.length, np.length)
  if (n < 2) return null
  const out = []
  for (let i = 0; i < n; i++) {
    const r = rev[i]
    const e = exp[i]
    const p = np[i]
    const ok =
      (r == null || Number.isFinite(Number(r))) &&
      (e == null || Number.isFinite(Number(e))) &&
      (p == null || Number.isFinite(Number(p)))
    if (!ok) continue
    if (r == null && e == null && p == null) continue
    out.push({
      period: String(periods[i] || '').slice(0, 7),
      revenue: r != null ? Number(r) : null,
      expenses: e != null ? Number(e) : null,
      net_profit: p != null ? Number(p) : null,
    })
  }
  return out.length >= 2 ? out : null
}

/**
 * Grouped compare: revenue, total_expense, implied profit (rev − expense) per branch.
 */
export function extractBranchGroupedCompareRows(comparativeIntelligence, maxBranches = 8) {
  const eff = comparativeIntelligence?.efficiency_ranking?.by_expense_pct_of_revenue_desc || []
  if (!Array.isArray(eff) || eff.length === 0) return null
  const rows = []
  for (const b of eff.slice(0, maxBranches)) {
    const rev = b.revenue != null && Number.isFinite(Number(b.revenue)) ? Number(b.revenue) : null
    const exp = b.total_expense != null && Number.isFinite(Number(b.total_expense)) ? Number(b.total_expense) : null
    if (rev == null && exp == null) continue
    const profit = rev != null && exp != null ? rev - exp : null
    rows.push({
      name: String(b.branch_name || '—').slice(0, 22),
      revenue: rev,
      expenses: exp,
      profit,
    })
  }
  return rows.length ? rows : null
}

export function extractBranchCompareRows(comparativeIntelligence, metric) {
  const ci = comparativeIntelligence || {}
  const eff = ci.efficiency_ranking?.by_expense_pct_of_revenue_desc || []
  if (!Array.isArray(eff) || eff.length === 0) return []

  if (metric === 'revenue') {
    return [...eff]
      .sort((a, b) => (Number(b.revenue) || 0) - (Number(a.revenue) || 0))
      .slice(0, 12)
      .map((b) => ({
        name: String(b.branch_name || '—').slice(0, 24),
        value: b.revenue != null && Number.isFinite(Number(b.revenue)) ? Number(b.revenue) : null,
        sub: null,
      }))
      .filter((r) => r.value != null)
  }

  return eff.slice(0, 12).map((b) => ({
    name: String(b.branch_name || '—').slice(0, 24),
    value:
      b.expense_pct_of_revenue != null && Number.isFinite(Number(b.expense_pct_of_revenue))
        ? Number(b.expense_pct_of_revenue)
        : null,
    sub: b.revenue != null && Number.isFinite(Number(b.revenue)) ? Number(b.revenue) : null,
  })).filter((r) => r.value != null)
}
