/**
 * Unified executive snapshot for AI CFO (client-side only; shapes data already fetched).
 */

import { formatCompactForLang, formatPctForLang, formatSignedPctForLang } from './numberFormat.js'

function num(v) {
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

function fmtMoney(v, lang) {
  const n = num(v)
  return n == null ? null : formatCompactForLang(n, lang)
}

function fmtPctRaw(v, lang) {
  const n = num(v)
  return n == null ? null : formatPctForLang(n, 1, lang)
}

function momDir(m) {
  const n = num(m)
  if (n == null) return 'flat'
  if (n > 0.5) return 'up'
  if (n < -0.5) return 'down'
  return 'flat'
}

function fmtMom(m, lang) {
  const n = num(m)
  if (n == null) return null
  return formatSignedPctForLang(n, 1, lang)
}

function primaryBlock(res) {
  if (!res) return null
  if (res.kind === 'expense' && res.expense) {
    const ex = res.expense
    const cr = ex.causal_realized || {}
    const sn = String(cr.action_text || cr.cause_text || cr.change_text || '').trim()
    const head = String(cr.change_text || cr.action_text || '').trim()
    return {
      kind: 'expense',
      title: head,
      domain: 'profitability',
      rationaleSnippet: sn ? sn.slice(0, 140) : '',
      priority: String(ex.priority || 'medium').toLowerCase(),
    }
  }
  if (res.decision) {
    const d = res.decision
    const cr = d.causal_realized || {}
    const sn = String(cr.action_text || cr.cause_text || cr.change_text || '').trim()
    const head = String(cr.change_text || cr.action_text || '').trim()
    return {
      kind: 'cfo',
      title: head,
      domain: d.domain ? String(d.domain).toLowerCase() : '',
      rationaleSnippet: sn ? sn.slice(0, 140) : '',
      urgency: String(d.urgency || 'medium').toLowerCase(),
    }
  }
  return null
}

function riskLines(alerts) {
  if (!Array.isArray(alerts) || !alerts.length) return []
  const hi = alerts.filter((a) => a?.severity === 'high')
  const out = []
  for (const a of hi.slice(0, 2)) {
    const t = a?.title && String(a.title).trim()
    if (t) out.push(t)
  }
  if (out.length) return out
  for (const a of alerts.slice(0, 3)) {
    const t = a?.title && String(a.title).trim()
    if (t) out.push(t)
  }
  return out
}

/**
 * @param {{
 *   kpis?: Record<string, any>,
 *   main?: Record<string, any>,
 *   narrative?: { whatChanged?: { lines?: string[] }, why?: { lines?: string[] }, whatToDo?: { lines?: string[] }, healthHeadline?: string },
 *   decisions?: unknown[],
 *   expenseIntel?: Record<string, any>,
 *   primaryResolution?: Record<string, any>,
 *   health?: number | null,
 *   companyName?: string | null,
 *   scopeLabel?: string | null,
 *   scopeSummary?: string | null,
 *   alerts?: unknown[],
 * }} p
 */
export function buildAiCfoExecutiveContext(p) {
  const lang = p.lang != null ? String(p.lang) : 'en'
  const kpis = p.kpis || {}
  const main = p.main || {}
  const cf = main.cashflow || {}

  const rev = kpis.revenue
  const np = kpis.net_profit
  const nm = kpis.net_margin
  const ex = kpis.expenses

  const expenseTop =
    p.expenseIntel?.available === true && p.expenseIntel?.top_category?.name
      ? {
          name: String(p.expenseIntel.top_category.name),
          amountFmt: fmtMoney(p.expenseIntel.top_category.amount, lang),
          share: num(p.expenseIntel.top_category.share_of_cost_pct),
        }
      : null

  return {
    companyName: p.companyName ? String(p.companyName).trim() : '',
    scopeLabel: p.scopeLabel ? String(p.scopeLabel).trim() : '',
    scopeSummary: p.scopeSummary ? String(p.scopeSummary).trim() : '',
    periodHint: main?.intelligence?.latest_period ? String(main.intelligence.latest_period).slice(0, 12) : '',

    revenue: {
      value: num(rev?.value),
      valueFmt: fmtMoney(rev?.value, lang),
      mom: num(rev?.mom_pct),
      momFmt: fmtMom(rev?.mom_pct, lang),
      momDir: momDir(rev?.mom_pct),
      yoy: num(rev?.yoy_pct),
    },
    profit: {
      value: num(np?.value),
      valueFmt: fmtMoney(np?.value, lang),
      mom: num(np?.mom_pct),
      momFmt: fmtMom(np?.mom_pct, lang),
      momDir: momDir(np?.mom_pct),
    },
    margin: {
      value: num(nm?.value),
      valueFmt: fmtPctRaw(nm?.value, lang),
      mom: num(nm?.mom_pct),
      momFmt: fmtMom(nm?.mom_pct, lang),
      momDir: momDir(nm?.mom_pct),
    },
    expenses: {
      value: num(ex?.value),
      valueFmt: fmtMoney(ex?.value, lang),
      mom: num(ex?.mom_pct),
      momFmt: fmtMom(ex?.mom_pct, lang),
      momDir: momDir(ex?.mom_pct),
      topCategory: expenseTop,
    },
    cashflow: {
      ocf: num(cf?.operating_cashflow),
      ocfFmt: fmtMoney(cf?.operating_cashflow, lang),
      ocfMom: num(cf?.operating_cashflow_mom),
      ocfMomFmt: fmtMom(cf?.operating_cashflow_mom, lang),
      ocfMomDir: momDir(cf?.operating_cashflow_mom),
      wc: num(kpis.working_capital?.value ?? cf?.working_capital),
      wcFmt: fmtMoney(kpis.working_capital?.value ?? cf?.working_capital, lang),
    },
    health_score: p.health != null && Number.isFinite(Number(p.health)) ? Math.round(Number(p.health)) : null,
    primary_decision: primaryBlock(p.primaryResolution),
    top_changes: (p.narrative?.whatChanged?.lines || [])
      .filter((x) => x && String(x).trim())
      .slice(0, 3)
      .map((x) => String(x).trim()),
    risks: riskLines(p.alerts),
    narrative_why: (p.narrative?.why?.lines || [])
      .filter((x) => x && String(x).trim())
      .slice(0, 3)
      .map((x) => String(x).trim()),
    narrative_do: (p.narrative?.whatToDo?.lines || [])
      .filter((x) => x && String(x).trim())
      .slice(0, 3)
      .map((x) => String(x).trim()),
    ranked_decision_titles: (Array.isArray(p.decisions) ? p.decisions : [])
      .filter((d) => d && (d.causal_realized?.change_text || d.causal_realized?.action_text))
      .slice(0, 3)
      .map((d) => String(d.causal_realized.change_text || d.causal_realized.action_text).trim()),
  }
}

/**
 * @param {ReturnType<typeof buildAiCfoExecutiveContext>} cx
 * @param {string} intent
 */
export function primaryDecisionRelevant(cx, intent) {
  const pd = cx.primary_decision
  if (!pd?.title && !pd?.rationaleSnippet) return false
  if (pd.kind === 'expense') {
    return (
      intent === 'WHY_PROFIT' ||
      intent === 'EXPENSE' ||
      intent === 'MARGIN' ||
      intent === 'WHAT_NOW' ||
      intent === 'REVENUE' ||
      intent === 'GENERAL' ||
      intent === 'FORECAST'
    )
  }
  const dom = pd.domain || ''
  if (intent === 'CASH' && (dom.includes('liquid') || dom.includes('cash') || dom === 'liquidity')) return true
  if (intent === 'WHY_PROFIT' || intent === 'MARGIN' || intent === 'EXPENSE') {
    return dom.includes('profit') || dom.includes('expense') || dom.includes('efficiency') || dom === 'profitability'
  }
  if (intent === 'WHAT_NOW' || intent === 'DECISION') return true
  if (intent === 'REVENUE' && (dom.includes('revenue') || dom.includes('growth') || dom.includes('scale'))) return true
  if (intent === 'RISK' || intent === 'HEALTH') return true
  return intent === 'GENERAL' || intent === 'FORECAST'
}
