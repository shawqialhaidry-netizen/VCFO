/**
 * Executive primary decision resolver — ranks CFO + expense candidates using
 * existing executive payload only (no API changes).
 */

const URGENCY_PTS = { high: 62, medium: 38, low: 18 }
const PRIORITY_PTS = { high: 55, medium: 32, low: 14 }
const IMPACT_LEVEL_PTS = { high: 24, medium: 15, low: 7 }

function num(v) {
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

function quantImpactPoints(impacts, decision) {
  if (!impacts || !decision) return 0
  const k = decision.key || decision.domain
  const row = impacts[k]
  const imp = row?.impact
  if (!imp || imp.type === 'qualitative' || imp.value == null) return 0
  const v = Math.abs(num(imp.value))
  if (v == null || v <= 0) return 0
  return Math.min(58, Math.log10(1 + v) * 11.5)
}

/** KPI / cashflow pressure buckets (0–each), used to align domains with real stress. */
function kpiPressureSignals(kpis, cashflow) {
  const revMom = num(kpis?.revenue?.mom_pct)
  const expMom = num(kpis?.expenses?.mom_pct)
  const npMom = num(kpis?.net_profit?.mom_pct)
  const nmMom = num(kpis?.net_margin?.mom_pct)
  const ocf = num(cashflow?.operating_cashflow)
  const ocfMom = num(cashflow?.operating_cashflow_mom)
  const wc =
    num(kpis?.working_capital?.value) ??
    num(cashflow?.working_capital) ??
    null

  let profitability = 0
  if (npMom != null && npMom < -2) profitability += 18
  else if (npMom != null && npMom < 0) profitability += 10
  if (nmMom != null && nmMom < -1) profitability += 12
  else if (nmMom != null && nmMom < 0) profitability += 6
  if (revMom != null && revMom > 0 && npMom != null && npMom < 0) profitability += 14

  let liquidity = 0
  if (wc != null && wc < 0) liquidity += 22
  if (ocf != null && ocf < 0) liquidity += 20
  if (ocfMom != null && ocfMom < -5) liquidity += 12
  else if (ocfMom != null && ocfMom < 0) liquidity += 6

  let efficiency = 0
  if (expMom != null && expMom > 4) efficiency += 18
  else if (expMom != null && expMom > 1.5) efficiency += 10

  let growth = 0
  if (revMom != null && revMom < -3) growth += 16
  else if (revMom != null && revMom < 0) growth += 8

  return {
    profitability: Math.min(40, profitability),
    liquidity: Math.min(40, liquidity),
    efficiency: Math.min(40, efficiency),
    growth: Math.min(35, growth),
  }
}

function branchPressurePoints(comparativeIntelligence) {
  const ci = comparativeIntelligence
  if (!ci || typeof ci !== 'object') return 0
  const eff = ci.efficiency_ranking?.by_expense_pct_of_revenue_desc
  const top = Array.isArray(eff) ? eff[0] : null
  const pct = num(top?.expense_pct_of_revenue)
  if (pct == null) return 0
  return Math.min(36, pct * 0.75)
}

function expenseDriverPoints(expenseIntelligence) {
  const ei = expenseIntelligence
  if (!ei?.available) return 0
  let pts = 0
  const ratio = num(ei.expense_ratio)
  if (ratio != null && ratio > 0.55) pts += 18
  else if (ratio != null && ratio > 0.42) pts += 10
  const mom = ei.mom_change
  const momPct = num(
    mom != null && typeof mom === 'object'
      ? mom.total_expense_pct ?? mom.pct ?? mom.pct_change
      : mom,
  )
  if (momPct != null && momPct > 6) pts += 14
  else if (momPct != null && momPct > 2) pts += 8
  const an = ei.anomalies
  if (Array.isArray(an) && an.length >= 2) pts += 10
  else if (Array.isArray(an) && an.length === 1) pts += 5
  return Math.min(38, pts)
}

function domainAlignmentBonus(domain, kpiSig, branchPts, expPts) {
  const d = String(domain || '').toLowerCase()
  if (d === 'profitability') {
    return kpiSig.profitability * 0.85 + branchPts * 0.45 + expPts * 0.55
  }
  if (d === 'liquidity') {
    return kpiSig.liquidity * 0.95 + branchPts * 0.15 + expPts * 0.12
  }
  if (d === 'efficiency') {
    return kpiSig.efficiency * 0.8 + branchPts * 0.55 + expPts * 0.5
  }
  if (d === 'leverage') {
    return kpiSig.profitability * 0.35 + kpiSig.liquidity * 0.25
  }
  if (d === 'growth') {
    return kpiSig.growth * 0.9 + kpiSig.profitability * 0.25
  }
  return 0
}

function scoreCfoDecision(d, impacts, kpiSig, branchPts, expPts) {
  const u = String(d?.urgency || 'low').toLowerCase()
  const urgencyPts = URGENCY_PTS[u] ?? URGENCY_PTS.low
  const il = String(d?.impact_level || 'low').toLowerCase()
  const levelPts = IMPACT_LEVEL_PTS[il] ?? IMPACT_LEVEL_PTS.low
  const q = quantImpactPoints(impacts, d)
  const align = domainAlignmentBonus(d?.domain, kpiSig, branchPts, expPts)
  return urgencyPts + levelPts + q + align
}

function firstExpenseActionLine(expense) {
  const act = expense?.action
  if (typeof act === 'string' && act.trim()) return act.trim().split('\n')[0]?.trim() || act.trim()
  if (act && typeof act === 'object' && Array.isArray(act.steps) && act.steps.length) {
    return String(act.steps[0] || '').trim()
  }
  return ''
}

function collectExpenseCandidates(expenseDecisionsV2, expenseIntelligence) {
  let list = Array.isArray(expenseDecisionsV2) ? expenseDecisionsV2.filter((d) => d && d.title) : []
  if (
    !list.length &&
    expenseIntelligence?.available &&
    Array.isArray(expenseIntelligence.decisions)
  ) {
    list = expenseIntelligence.decisions
      .filter((d) => d && d.title)
      .map((d) => ({
        decision_id: d.decision_id,
        title: d.title,
        rationale: d.rationale || (typeof d.action === 'string' ? d.action : null),
        priority: d.priority || 'medium',
        expected_financial_impact: d.expected_financial_impact,
        action: typeof d.action === 'object' && d.action != null ? d.action : undefined,
      }))
  }
  return list
}

function scoreExpenseDecision(d, branchPts, expPts) {
  const p = String(d?.priority || 'medium').toLowerCase()
  const pri = PRIORITY_PTS[p] ?? PRIORITY_PTS.medium
  const sav = num(d?.expected_financial_impact?.estimated_monthly_savings)
  const savingsPts = sav != null && sav > 0 ? Math.min(42, Math.log10(1 + sav) * 14) : 0
  return pri + savingsPts + branchPts * 0.5 + expPts * 0.65
}

/**
 * @param {object} data
 * @param {object[]} [data.decisions] — CFO decisions from executive
 * @param {Record<string, object>} [data.impacts] — decision_key/domain → impact row
 * @param {object} [data.kpis] — kpi_block.kpis
 * @param {object} [data.cashflow]
 * @param {object} [data.comparativeIntelligence]
 * @param {object} [data.expenseIntelligence]
 * @param {object[]} [data.expenseDecisionsV2]
 * @returns {{ kind: 'cfo', decision: object, score: number } | { kind: 'expense', expense: object, score: number } | null}
 */
export function selectPrimaryDecision(data) {
  const {
    decisions = [],
    impacts = {},
    kpis = {},
    cashflow = {},
    comparativeIntelligence = null,
    expenseIntelligence = null,
    expenseDecisionsV2 = [],
  } = data || {}

  const kpiSig = kpiPressureSignals(kpis, cashflow)
  const branchPts = branchPressurePoints(comparativeIntelligence)
  const expPts = expenseDriverPoints(expenseIntelligence)

  let best = null

  if (Array.isArray(decisions)) {
    for (const d of decisions) {
      if (!d || !d.domain) continue
      const score = scoreCfoDecision(d, impacts, kpiSig, branchPts, expPts)
      if (!best || score > best.score) {
        best = { kind: 'cfo', decision: d, score }
      }
    }
  }

  const expenseList = collectExpenseCandidates(expenseDecisionsV2, expenseIntelligence).filter(
    (d) => d.decision_id !== '_cmd_baseline',
  )

  for (const d of expenseList) {
    const score = scoreExpenseDecision(d, branchPts, expPts)
    if (!best || score > best.score) {
      best = { kind: 'expense', expense: d, score }
    }
  }

  if (best) return best

  const baseline = collectExpenseCandidates(expenseDecisionsV2, expenseIntelligence).find(
    (d) => d.decision_id === '_cmd_baseline',
  )
  if (baseline) {
    return { kind: 'expense', expense: baseline, score: PRIORITY_PTS.medium }
  }

  return null
}

export { firstExpenseActionLine }
