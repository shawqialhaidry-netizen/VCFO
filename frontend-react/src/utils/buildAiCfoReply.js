/**
 * AI CFO — context-aware, intent-scored replies from executive payload (no API).
 */
import { buildAiCfoExecutiveContext, primaryDecisionRelevant } from './buildAiCfoContext.js'

const MAX_BULLETS = 3

function norm(q) {
  return String(q || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
}

function tSafe(tr, key, params) {
  const line = tr(key, params || {})
  if (!line || typeof line !== 'string' || /\{[a-z_]+\}/.test(line)) return null
  return line
}

function dedupeCap(lines, n = MAX_BULLETS) {
  const seen = new Set()
  const out = []
  for (const ln of lines) {
    const s = String(ln || '').trim()
    if (!s) continue
    const k = s.toLowerCase()
    if (seen.has(k)) continue
    seen.add(k)
    out.push(s)
    if (out.length >= n) break
  }
  return out
}

function na(v) {
  return v != null && String(v).trim() !== '' ? String(v) : '—'
}

/**
 * Weighted intent detection (not single-keyword routing).
 * @returns {{ intent: string, scores: Record<string, number> }}
 */
export function detectAiCfoIntent(question) {
  const s = norm(question)
  const scores = {}
  const add = (k, w) => {
    scores[k] = (scores[k] || 0) + w
  }

  const asksWhy = /\b(why|reason|cause|what drove|what caused|how come|explain)\b/.test(s)
  const asksWhatNow = /\b(what should i|what do i do|next step|priorit|recommend|action|now\?)\b/.test(s)
  const profitWord = /\b(profit|p&l|bottom\s*line|net\s*profit|earnings)\b/.test(s)
  const dropWord = /\b(drop|dropped|fall|fell|down|decline|declined|lower|worse|weak|squeeze)\b/.test(s)
  const riseWord = /\b(rise|rose|up|improv|better|strong|grow)\b/.test(s)

  if ((asksWhy && profitWord) || (dropWord && profitWord) || (riseWord && profitWord)) add('WHY_PROFIT', 6)
  if (asksWhy && /\b(margin|margins)\b/.test(s)) add('WHY_PROFIT', 4)

  if (/\b(cash|cashflow|cash\s*flow|liquidity|ocf|operating\s*cash|working\s*capital)\b/.test(s)) add('CASH', 5)
  if (asksWhatNow) add('WHAT_NOW', 6)
  if (/\b(decision|priorit|ranked|backlog)\b/.test(s)) add('DECISION', 4)
  if (/\b(revenue|sales|top\s*line|turnover)\b/.test(s)) add('REVENUE', 4)
  if (/\b(expense|cost|spend|spending|overhead)\b/.test(s)) add('EXPENSE', 4)
  if (/\b(margin|margins)\b/.test(s) && !scores.WHY_PROFIT) add('MARGIN', 3)
  if (/\b(risk|alert|warning|problem)\b/.test(s)) add('RISK', 4)
  if (/\b(health|score|overall)\b/.test(s)) add('HEALTH', 3)
  if (/\b(branch|branches|store|stores|location|locations|outlet|outlets|site|sites)\b/.test(s)) add('BRANCH', 5)
  if (/\b(forecast|scenario|scenarios|projection|projections|outlook|run\s*rate|runrate)\b/.test(s)) add('FORECAST', 5)

  let best = 'GENERAL'
  let bestScore = 0
  for (const [k, v] of Object.entries(scores)) {
    if (v > bestScore) {
      best = k
      bestScore = v
    }
  }
  if (bestScore === 0) best = 'GENERAL'
  return { intent: best, scores }
}

function pickFollowUpKey(intent) {
  if (intent === 'WHY_PROFIT' || intent === 'EXPENSE') return 'ai_cfo_fu_q_branch'
  if (intent === 'CASH') return 'ai_cfo_fu_q_cash'
  if (intent === 'WHAT_NOW' || intent === 'DECISION') return 'ai_cfo_fu_q_action'
  if (intent === 'REVENUE' || intent === 'MARGIN') return 'ai_cfo_fu_q_deeper'
  if (intent === 'BRANCH') return 'ai_cfo_fu_q_branch'
  if (intent === 'FORECAST') return 'ai_cfo_fu_q_deeper'
  return 'ai_cfo_fu_q_deeper'
}

const DRILL_BY_INTENT = {
  WHY_PROFIT: [
    { path: '/profitability', focus: 'profitability', labelKey: 'ai_cfo_action_profitability_lab' },
    { path: '/expenses', focus: 'efficiency', labelKey: 'ai_cfo_action_expense_intel' },
  ],
  CASH: [
    { path: '/cash', focus: 'liquidity', labelKey: 'ai_cfo_action_cash_liquidity' },
    { path: '/profitability', focus: 'profitability', labelKey: 'ai_cfo_action_profitability_lab' },
  ],
  WHAT_NOW: [
    { path: '/decisions', focus: 'decisions', labelKey: 'ai_cfo_action_decision_center' },
    { path: '/analysis', focus: 'overview', labelKey: 'ai_cfo_action_analysis_overview' },
  ],
  DECISION: [
    { path: '/decisions', focus: 'decisions', labelKey: 'ai_cfo_action_decision_center' },
    { path: '/alerts', focus: 'alerts', labelKey: 'ai_cfo_action_alerts_root' },
  ],
  REVENUE: [
    { path: '/revenue', focus: 'profitability', labelKey: 'ai_cfo_action_revenue_intel' },
    { path: '/expenses', focus: 'efficiency', labelKey: 'ai_cfo_action_expense_intel' },
  ],
  EXPENSE: [
    { path: '/expenses', focus: 'efficiency', labelKey: 'ai_cfo_action_expense_intel' },
    { path: '/decisions', focus: 'decisions', labelKey: 'ai_cfo_action_decision_center' },
  ],
  MARGIN: [
    { path: '/profitability', focus: 'profitability', labelKey: 'ai_cfo_action_profitability_lab' },
    { path: '/revenue', focus: 'profitability', labelKey: 'ai_cfo_action_revenue_intel' },
  ],
  RISK: [
    { path: '/alerts', focus: 'alerts', labelKey: 'ai_cfo_action_alerts_root' },
    { path: '/analysis', focus: 'overview', labelKey: 'ai_cfo_action_analysis_overview' },
  ],
  HEALTH: [
    { path: '/analysis', focus: 'overview', labelKey: 'ai_cfo_action_analysis_overview' },
    { path: '/profitability', focus: 'profitability', labelKey: 'ai_cfo_action_profitability_lab' },
  ],
  BRANCH: [
    { path: '/branches', labelKey: 'ai_cfo_action_branch_intel' },
    { path: '/expenses', focus: 'efficiency', labelKey: 'ai_cfo_action_expense_intel' },
  ],
  FORECAST: [
    { path: '/forecast', focus: 'overview', labelKey: 'ai_cfo_action_forecast' },
    { path: '/profitability', focus: 'profitability', labelKey: 'ai_cfo_action_profitability_lab' },
  ],
  GENERAL: [
    { path: '/analysis', focus: 'overview', labelKey: 'ai_cfo_action_analysis_overview' },
    { path: '/profitability', focus: 'profitability', labelKey: 'ai_cfo_action_profitability_lab' },
  ],
}

function mentionsBranchInQuestion(question) {
  const s = norm(question)
  return /\b(branch|branches|store|stores|location|locations|outlet|outlets|site|sites)\b/.test(s)
}

function dedupeDrillActions(rows) {
  const seen = new Set()
  const out = []
  for (const r of rows) {
    if (!r?.path) continue
    const k = `${r.path}\0${r.focus ?? ''}`
    if (seen.has(k)) continue
    seen.add(k)
    out.push(r)
  }
  return out.slice(0, 2)
}

/**
 * Primary + optional secondary drill targets from the same intent as {@link detectAiCfoIntent}.
 * @param {string} intent
 * @param {string} [question]
 * @returns {Array<{ path: string, focus?: string, labelKey: string }>}
 */
export function buildAiCfoDrillActions(intent, question = '') {
  const base = DRILL_BY_INTENT[intent] || DRILL_BY_INTENT.GENERAL
  let rows = [...base]
  if (mentionsBranchInQuestion(question) && intent !== 'BRANCH' && rows.length >= 2) {
    rows = [rows[0], { path: '/branches', labelKey: 'ai_cfo_action_branch_intel' }]
  }
  return dedupeDrillActions(rows)
}

function profitDriverLine(cx, tr) {
  const { profit, revenue, expenses } = cx
  const npm = profit.mom
  const rm = revenue.mom
  const em = expenses.mom
  if (profit.valueFmt == null && profit.value == null) return null

  const npf = na(profit.valueFmt)
  const npmf = na(profit.momFmt)
  const rmf = na(revenue.momFmt)
  const emf = na(expenses.momFmt)

  if (npm != null && npm < -0.5) {
    if (em != null && em > 0.5 && (rm == null || em > rm + 0.5)) {
      return tSafe(tr, 'ai_cfo_intel_np_pressure_expense', { np: npf, npm: npmf, em: emf, rm: rmf })
    }
    if (rm != null && rm < -0.5) {
      return tSafe(tr, 'ai_cfo_intel_np_pressure_revenue', { np: npf, npm: npmf, rm: rmf, em: emf })
    }
  }
  if (npm != null && npm > 0.5) {
    return tSafe(tr, 'ai_cfo_intel_np_positive', { np: npf, npm: npmf, rm: rmf, em: emf })
  }
  return tSafe(tr, 'ai_cfo_intel_np_neutral', { np: npf, npm: npmf, rm: rmf, em: emf })
}

function scopeLine(cx, tr) {
  const company = cx.companyName || ''
  const scope = cx.scopeSummary || cx.scopeLabel || cx.periodHint
  if (!company && !scope) return null
  return tSafe(tr, 'ai_cfo_context_line', { company: company || '—', scope: scope || '—' })
}

function appendPrimaryDo(cx, intent, tr, doLines) {
  const pd = cx.primary_decision
  if (!pd?.title || !primaryDecisionRelevant(cx, intent)) return doLines
  const tie = tSafe(tr, 'ai_cfo_primary_tie', { title: pd.title.slice(0, 100) })
  if (!tie) return doLines
  const next = [...doLines.filter(Boolean)]
  const withoutDup = next.filter((l) => !l.toLowerCase().includes(pd.title.toLowerCase().slice(0, 24)))
  while (withoutDup.length >= MAX_BULLETS) withoutDup.pop()
  withoutDup.push(tie)
  return dedupeCap(withoutDup, MAX_BULLETS)
}

function ensureDataPoint(what, cx, tr) {
  if (!what.length) {
    const h = cx.health_score != null ? tSafe(tr, 'ai_cfo_fact_health', { v: String(cx.health_score) }) : null
    if (h) return [h]
    const np = cx.profit.valueFmt
    if (np) {
      const l = tSafe(tr, 'ai_cfo_fact_np', { v: np })
      if (l) return [l]
    }
  }
  const hasDigit = what.some((l) => /\d/.test(l))
  if (hasDigit) return what
  const np = cx.profit.valueFmt
  if (np) {
    const l = tSafe(tr, 'ai_cfo_fact_np', { v: np })
    if (l) return dedupeCap([l, ...what], MAX_BULLETS)
  }
  return what
}

function generateForIntent(intent, cx, tr) {
  let what = []
  let why = []
  let todo = []

  const sl = scopeLine(cx, tr)
  if (sl) what.push(sl)

  switch (intent) {
    case 'WHY_PROFIT': {
      const driver = profitDriverLine(cx, tr)
      if (driver) what.push(driver)
      what.push(...cx.top_changes.slice(0, 2))
      why.push(...cx.narrative_why.slice(0, 2))
      const expTop = cx.expenses.topCategory
      if (expTop?.name && expTop.amountFmt) {
        const l = tSafe(tr, 'ai_cfo_intel_top_cost', { name: expTop.name, amt: expTop.amountFmt })
        if (l) why.push(l)
      }
      todo.push(...cx.narrative_do.slice(0, MAX_BULLETS))
      break
    }
    case 'CASH': {
      const ocf = cx.cashflow.ocfFmt
      if (ocf) {
        const l = tSafe(tr, 'ai_cfo_fact_ocf', { v: ocf })
        if (l) what.push(l)
      }
      const om = cx.cashflow.ocfMomFmt
      if (om) {
        const l2 = tSafe(tr, 'ai_cfo_fact_ocf_mom', { p: om.replace('%', '') })
        if (l2) what.push(l2)
      }
      const wc = cx.cashflow.wcFmt
      if (wc) {
        const l3 = tSafe(tr, 'ai_cfo_intel_wc', { v: wc })
        if (l3) what.push(l3)
      }
      const np = cx.profit.valueFmt
      const npm = cx.profit.momFmt
      if (np && npm) {
        const bridge = tSafe(tr, 'ai_cfo_intel_cash_profit_bridge', { np, npm })
        if (bridge) why.push(bridge)
      }
      why.push(...cx.narrative_why.slice(0, 2))
      todo.push(...cx.narrative_do.slice(0, MAX_BULLETS))
      break
    }
    case 'WHAT_NOW':
    case 'DECISION': {
      const pt = cx.primary_decision?.title
      if (pt) {
        const l = tSafe(tr, 'ai_cfo_intel_primary_headline', { title: pt.slice(0, 120) })
        if (l) what.push(l)
      }
      cx.ranked_decision_titles.forEach((title, i) => {
        const line = tSafe(tr, 'ai_cfo_fact_ranked', { n: String(i + 1), title: title.slice(0, 100) })
        if (line) what.push(line)
      })
      const rev = cx.revenue.valueFmt
      const npm = cx.profit.valueFmt
      if (rev && npm) {
        const snap = tSafe(tr, 'ai_cfo_intel_snapshot_rev_np', { rev, np: npm })
        if (snap) what.push(snap)
      }
      why.push(...cx.narrative_why.slice(0, 2))
      todo.push(...cx.narrative_do.slice(0, MAX_BULLETS))
      break
    }
    case 'REVENUE': {
      const v = cx.revenue.valueFmt
      if (v) {
        const l = tSafe(tr, 'ai_cfo_fact_rev', { v })
        if (l) what.push(l)
      }
      if (cx.revenue.momFmt) {
        const l2 = tSafe(tr, 'ai_cfo_fact_rev_mom', { p: cx.revenue.momFmt.replace('%', '') })
        if (l2) what.push(l2)
      }
      const np = cx.profit.valueFmt
      if (np && cx.revenue.mom != null && cx.profit.mom != null) {
        const rel = tSafe(tr, 'ai_cfo_intel_rev_profit_link', {
          rm: na(cx.revenue.momFmt),
          npm: na(cx.profit.momFmt),
          np,
        })
        if (rel) why.push(rel)
      }
      why.push(...cx.narrative_why.slice(0, 2))
      todo.push(...cx.narrative_do.slice(0, MAX_BULLETS))
      break
    }
    case 'EXPENSE': {
      const v = cx.expenses.valueFmt
      if (v) {
        const l = tSafe(tr, 'ai_cfo_fact_exp', { v })
        if (l) what.push(l)
      }
      if (cx.expenses.momFmt) {
        const l2 = tSafe(tr, 'ai_cfo_fact_exp_mom', { p: cx.expenses.momFmt.replace('%', '') })
        if (l2) what.push(l2)
      }
      const top = cx.expenses.topCategory
      if (top?.name && top.amountFmt) {
        const l3 = tSafe(tr, 'ai_cfo_fact_top_expense', { line: `${top.name} · ${top.amountFmt}` })
        if (l3) what.push(l3)
      }
      why.push(...cx.narrative_why.slice(0, 2))
      todo.push(...cx.narrative_do.slice(0, MAX_BULLETS))
      break
    }
    case 'MARGIN': {
      const v = cx.margin.valueFmt
      if (v) {
        const l = tSafe(tr, 'ai_cfo_fact_nm', { v })
        if (l) what.push(l)
      }
      if (cx.margin.momFmt) {
        const l2 = tSafe(tr, 'ai_cfo_fact_nm_mom', { p: cx.margin.momFmt.replace('%', '') })
        if (l2) what.push(l2)
      }
      const bridge = tSafe(tr, 'ai_cfo_intel_margin_bridge', {
        rev: na(cx.revenue.momFmt),
        exp: na(cx.expenses.momFmt),
      })
      if (bridge) why.push(bridge)
      why.push(...cx.narrative_why.slice(0, 2))
      todo.push(...cx.narrative_do.slice(0, MAX_BULLETS))
      break
    }
    case 'RISK': {
      if (cx.health_score != null) {
        const l = tSafe(tr, 'ai_cfo_fact_health', { v: String(cx.health_score) })
        if (l) what.push(l)
      }
      cx.risks.slice(0, 2).forEach((r) => {
        const line = tSafe(tr, 'ai_cfo_intel_risk_item', { item: r.slice(0, 120) })
        if (line) what.push(line)
      })
      why.push(...cx.narrative_why.slice(0, 2))
      todo.push(...cx.narrative_do.slice(0, MAX_BULLETS))
      break
    }
    case 'HEALTH': {
      if (cx.health_score != null) {
        const l = tSafe(tr, 'ai_cfo_fact_health', { v: String(cx.health_score) })
        if (l) what.push(l)
      }
      what.push(...cx.top_changes.slice(0, 2))
      why.push(...cx.narrative_why.slice(0, 2))
      todo.push(...cx.narrative_do.slice(0, MAX_BULLETS))
      break
    }
    case 'BRANCH':
    case 'GENERAL':
    case 'FORECAST':
    default: {
      const np = cx.profit.valueFmt
      const rev = cx.revenue.valueFmt
      if (rev && np) {
        const l = tSafe(tr, 'ai_cfo_intel_snapshot_rev_np', { rev, np })
        if (l) what.push(l)
      } else if (np) {
        const l = tSafe(tr, 'ai_cfo_fact_np', { v: np })
        if (l) what.push(l)
      }
      what.push(...cx.top_changes.slice(0, 2))
      why.push(...cx.narrative_why.slice(0, 2))
      if (!why.length) why.push(tSafe(tr, 'ai_cfo_fallback_why'))
      todo.push(...cx.narrative_do.slice(0, MAX_BULLETS))
      if (!todo.length) todo.push(tSafe(tr, 'ai_cfo_fallback_do'))
    }
  }

  what = dedupeCap(what, MAX_BULLETS)
  why = dedupeCap(why, MAX_BULLETS)
  todo = dedupeCap(todo, MAX_BULLETS)

  what = ensureDataPoint(what, cx, tr)
  what = dedupeCap(what, MAX_BULLETS)

  todo = appendPrimaryDo(cx, intent, tr, todo)

  if (!why.length) why = dedupeCap([tSafe(tr, 'ai_cfo_fallback_why')].filter(Boolean), MAX_BULLETS)
  if (!todo.length) todo = dedupeCap([tSafe(tr, 'ai_cfo_fallback_do')].filter(Boolean), MAX_BULLETS)

  return { what, why, do: todo }
}

/**
 * @param {string} question
 * @param {{
 *   tr: (k: string, params?: Record<string, unknown>) => string,
 *   narrative?: object,
 *   kpis?: Record<string, any>,
 *   main?: Record<string, any>,
 *   decisions?: unknown[],
 *   expenseIntel?: Record<string, any>,
 *   primaryResolution?: Record<string, any>,
 *   health?: number | null,
 *   companyName?: string | null,
 *   scopeLabel?: string | null,
 *   scopeSummary?: string | null,
 *   alerts?: unknown[],
 * }} ctx
 * @returns {{ intent: string, what: string[], why: string[], do: string[], followUp: string | null, followUpFill: string | null, actions: Array<{ path: string, focus?: string, labelKey: string }> }}
 */
export function buildAiCfoReply(question, ctx) {
  const { tr, narrative, kpis = {}, main = {}, decisions = [], expenseIntel, primaryResolution, health } = ctx

  const cx = buildAiCfoExecutiveContext({
    kpis,
    main,
    narrative,
    decisions,
    expenseIntel,
    primaryResolution,
    health,
    companyName: ctx.companyName,
    scopeLabel: ctx.scopeLabel,
    scopeSummary: ctx.scopeSummary,
    alerts: ctx.alerts,
  })

  const { intent } = detectAiCfoIntent(question)
  const { what, why, do: todo } = generateForIntent(intent, cx, tr)
  const actions = buildAiCfoDrillActions(intent, question)

  const fuKey = pickFollowUpKey(intent)
  const followUp = tSafe(tr, fuKey)
  const followUpFill = tSafe(tr, `${fuKey}_fill`)

  return {
    intent,
    what,
    why,
    do: todo,
    followUp,
    followUpFill: followUpFill || followUp,
    actions,
  }
}
