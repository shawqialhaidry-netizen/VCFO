/**
 * Client-only drill explanations from executive payload + narrative (no API).
 * Produces What / Why / Do bullets for panels and Analysis tabs.
 */
import { formatCompact } from './numberFormat.js'

const MAX = 3

function sliceTitle(t, n = 96) {
  const s = String(t || '').trim()
  if (!s) return ''
  return s.length > n ? `${s.slice(0, n - 1)}…` : s
}

function dedupeCap(items, n = MAX) {
  const seen = new Set()
  const out = []
  for (const it of items) {
    const text = it && typeof it.text === 'string' ? it.text.trim() : ''
    if (!text) continue
    const k = text.toLowerCase()
    if (seen.has(k)) continue
    seen.add(k)
    out.push({ ...it, text })
    if (out.length >= n) break
  }
  return out
}

function hasDigitIn(lines) {
  return lines.some((l) => l && /\d/.test(l.text || ''))
}

/** @param {(k: string, p?: Record<string, unknown>) => string} t */
function firstKpiSnapshotLine(kpis, t) {
  const order = ['revenue', 'expenses', 'net_profit', 'net_margin']
  for (const k of order) {
    const row = kpis?.[k]
    if (row?.value == null || !Number.isFinite(Number(row.value))) continue
    const v = k === 'net_margin' ? `${Number(row.value).toFixed(1)}%` : formatCompact(Number(row.value))
    return { text: t('drill_intel_kpi_level', { label: t(`kpi_label_${k}`), v }) }
  }
  return null
}

/**
 * @param {object | null | undefined} primaryResolution
 * @param {(k: string, p?: Record<string, unknown>) => string} t
 */
export function primaryDecisionTieLine(primaryResolution, t) {
  if (!primaryResolution) return null
  if (primaryResolution.kind === 'expense') {
    const ex = primaryResolution.expense
    if (!ex?.title) return null
    if (ex.decision_id === '_cmd_baseline') return null
    return t('drill_intel_follow_primary', { title: sliceTitle(ex.title, 100) })
  }
  const d = primaryResolution.decision
  if (!d?.title) return null
  return t('drill_intel_follow_primary', { title: sliceTitle(d.title, 100) })
}

function kpiNarrativeMatch(line, kpiType) {
  const s = String(line || '')
  const sl = s.toLowerCase()
  if (kpiType === 'revenue') return /revenue|sales|إيراد|gelir|turnover|top/i.test(s)
  if (kpiType === 'expenses') return /expense|cost|spend|مصروف|gider|overhead|تكلفة|maliyet/i.test(s)
  if (kpiType === 'net_profit') return /profit|ربح|kâr|bottom|earnings|صافي/i.test(s)
  if (kpiType === 'net_margin') return /margin|هامش|marj|ratio|net/i.test(s)
  if (kpiType === 'cashflow') return /cash|نقد|nakit|liquidity|flow|ocf|تشغيل/i.test(s)
  if (kpiType === 'working_capital') return /capital|working|sermaye|عامل|ratio/i.test(s)
  return true
}

function domainNarrativeMatch(line, domain) {
  const s = String(line || '')
  if (domain === 'liquidity') return /cash|liquidity|نقد|nakit|capital|ratio|سيولة|likidite|current|quick/i.test(s)
  if (domain === 'profitability') return /profit|margin|revenue|ربح|kâr|marj|إيراد|gelir|gross|net/i.test(s)
  if (domain === 'efficiency') return /efficien|cost|ratio|كفاءة|verim|expense|asset|turnover/i.test(s)
  if (domain === 'leverage' || domain === 'risk') return /leverage|debt|risk|دين|borç|borç|solvency/i.test(s)
  return true
}

function filterOrAll(lines, fn) {
  const arr = (lines || []).filter(Boolean)
  if (!arr.length) return []
  const hit = arr.filter((ln) => fn(String(ln)))
  return hit.length ? hit : arr
}

/**
 * @param {{
 *   panelType: string,
 *   payload?: Record<string, unknown>,
 *   extra?: Record<string, unknown>,
 *   t: (k: string, p?: Record<string, unknown>) => string,
 * }} p
 * @returns {{ what: Array<{ text: string, serverText?: boolean }>, why: Array<{ text: string, serverText?: boolean }>, do: Array<{ text: string, serverText?: boolean }> }}
 */
export function buildDrillIntelligence({ panelType, payload = {}, extra = {}, t }) {
  const bundle = extra?.drillIntelBundle || {}
  const narrative = bundle.narrative
  const kpis = bundle.kpis || {}
  const primaryResolution = bundle.primaryResolution
  const expenseIntel = bundle.expenseIntel
  const decisions = bundle.decisions || extra?.decisions || []
  const health = bundle.health
  const cashflow = extra?.execChartBundle?.cashflow || bundle.cashflow || {}
  const ci = extra?.execChartBundle?.comparative_intelligence || bundle.comparative_intelligence

  const momWord = () => t('mom_label')

  const whatRaw = []
  const whyRaw = []
  const doRaw = []

  const analysisTab = panelType === 'analysis_tab' ? String(payload.tab || '') : ''

  if (panelType === 'kpi' && payload?.type) {
    const ty = String(payload.type)
    if (payload.mom != null && Number.isFinite(Number(payload.mom))) {
      const label = t(`kpi_label_${ty}`)
      const pct = `${Number(payload.mom) > 0 ? '+' : ''}${Number(payload.mom).toFixed(1)}`
      whatRaw.push({ text: t('drill_intel_kpi_momentum', { label, pct, mom_word: momWord() }) })
    }
    if (ty === 'net_margin' && payload.raw != null && Number.isFinite(Number(payload.raw))) {
      whatRaw.push({ text: t('drill_intel_net_margin_level', { pct: Number(payload.raw).toFixed(1) }) })
    }
    if (ty === 'cashflow' && cashflow?.operating_cashflow != null && Number.isFinite(Number(cashflow.operating_cashflow))) {
      whatRaw.push({
        text: t('drill_intel_ocf_level', { v: formatCompact(Number(cashflow.operating_cashflow)) }),
      })
    }
  }

  if (panelType === 'domain' && payload?.domain != null && payload.score != null) {
    const dom = String(payload.domain)
    whatRaw.push({
      text: t('drill_intel_domain_score_line', {
        domain: t(`domain_${dom}_simple`),
        score: String(Math.round(Number(payload.score))),
      }),
    })
  }

  const nWhat = narrative?.whatChanged?.lines || []
  const nWhy = narrative?.why?.lines || []
  const nDo = narrative?.whatToDo?.lines || []

  if (panelType === 'kpi' && payload?.type) {
    const ty = String(payload.type)
    for (const line of filterOrAll(nWhat, (ln) => kpiNarrativeMatch(ln, ty)).slice(0, 2)) {
      whatRaw.push({ text: line })
    }
    for (const line of filterOrAll(nWhy, (ln) => kpiNarrativeMatch(ln, ty)).slice(0, 2)) {
      whyRaw.push({ text: line })
    }
    for (const line of filterOrAll(nDo, (ln) => kpiNarrativeMatch(ln, ty)).slice(0, 2)) {
      doRaw.push({ text: line })
    }
  } else if (panelType === 'domain' && payload?.domain) {
    const dom = String(payload.domain)
    for (const line of filterOrAll(nWhat, (ln) => domainNarrativeMatch(ln, dom)).slice(0, 2)) {
      whatRaw.push({ text: line })
    }
    for (const line of filterOrAll(nWhy, (ln) => domainNarrativeMatch(ln, dom)).slice(0, 2)) {
      whyRaw.push({ text: line })
    }
    for (const line of filterOrAll(nDo, (ln) => domainNarrativeMatch(ln, dom)).slice(0, 2)) {
      doRaw.push({ text: line })
    }
  } else if (analysisTab) {
    const domMap = { profitability: 'profitability', liquidity: 'liquidity', efficiency: 'efficiency' }
    const dom = domMap[analysisTab]
    if (dom) {
      for (const line of filterOrAll(nWhat, (ln) => domainNarrativeMatch(ln, dom)).slice(0, 2)) {
        whatRaw.push({ text: line })
      }
      for (const line of filterOrAll(nWhy, (ln) => domainNarrativeMatch(ln, dom)).slice(0, 2)) {
        whyRaw.push({ text: line })
      }
      for (const line of filterOrAll(nDo, (ln) => domainNarrativeMatch(ln, dom)).slice(0, 2)) {
        doRaw.push({ text: line })
      }
    } else {
      for (const line of nWhat.slice(0, 2)) whatRaw.push({ text: line })
      for (const line of nWhy.slice(0, 2)) whyRaw.push({ text: line })
      for (const line of nDo.slice(0, 2)) doRaw.push({ text: line })
    }
  } else {
    for (const line of nWhat.slice(0, 2)) whatRaw.push({ text: line })
    for (const line of nWhy.slice(0, 2)) whyRaw.push({ text: line })
    for (const line of nDo.slice(0, 2)) doRaw.push({ text: line })
  }

  if (expenseIntel?.top_category?.name && expenseIntel?.available === true) {
    const name = String(expenseIntel.top_category.name)
    const amt =
      expenseIntel.top_category.amount != null && Number.isFinite(Number(expenseIntel.top_category.amount))
        ? formatCompact(Number(expenseIntel.top_category.amount))
        : '—'
    const sh = expenseIntel.top_category.share_of_cost_pct
    if (sh != null && Number.isFinite(Number(sh))) {
      whyRaw.push({
        text: t('drill_intel_top_expense_share', { name, amt, share: Number(sh).toFixed(1) }),
        serverText: true,
      })
    } else {
      whyRaw.push({ text: t('drill_intel_top_expense_short', { name, amt }), serverText: true })
    }
  }

  const topBr = ci?.efficiency_ranking?.by_expense_pct_of_revenue_desc?.[0]
  if (
    topBr?.branch_name != null &&
    topBr.expense_pct_of_revenue != null &&
    Number.isFinite(Number(topBr.expense_pct_of_revenue)) &&
    (panelType === 'branch_compare' || (panelType === 'kpi' && payload?.type === 'net_margin'))
  ) {
    whyRaw.push({
      text: t('drill_intel_branch_expense_line', {
        name: String(topBr.branch_name),
        pct: Number(topBr.expense_pct_of_revenue).toFixed(1),
      }),
      serverText: true,
    })
  }

  if (panelType === 'domain' && payload?.domain && Array.isArray(extra?.causes)) {
    const dom = String(payload.domain)
    const c = extra.causes.find((x) => x?.domain === dom || x?.domain === 'cross_domain')
    if (c?.description) whyRaw.push({ text: String(c.description), serverText: true })
    else if (c?.title) whyRaw.push({ text: String(c.title), serverText: true })
  }

  const pd = primaryDecisionTieLine(primaryResolution, t)
  if (pd) doRaw.push({ text: pd })

  if (Array.isArray(decisions) && decisions[0]?.title) {
    const title = sliceTitle(decisions[0].title, 90)
    const already = doRaw.some((l) => String(l.text).toLowerCase().includes(title.toLowerCase().slice(0, 18)))
    if (!already) {
      doRaw.push({ text: t('drill_intel_ranked_decision', { title }), serverText: true })
    }
  }

  let what = dedupeCap(whatRaw, MAX)
  let why = dedupeCap(whyRaw, MAX)
  let doSection = dedupeCap(doRaw, MAX)

  const combined = [...what, ...why, ...doSection]
  if (!hasDigitIn(combined)) {
    const snap = firstKpiSnapshotLine(kpis, t)
    if (snap) what = dedupeCap([snap, ...what], MAX)
    else if (health != null && Number.isFinite(Number(health))) {
      what = dedupeCap([{ text: t('drill_intel_health_score', { v: String(Math.round(Number(health))) }) }, ...what], MAX)
    } else if (payload?.mom != null) {
      /* momentum line already attempted */
    }
  }

  if (!what.length) {
    const snap = firstKpiSnapshotLine(kpis, t)
    if (snap) what.push(snap)
    else if (health != null && Number.isFinite(Number(health))) {
      what.push({ text: t('drill_intel_health_score', { v: String(Math.round(Number(health))) }) })
    } else {
      what.push({ text: t('drill_intel_what_fallback') })
    }
  }
  if (!why.length) {
    why.push({ text: t('drill_intel_why_fallback') })
  }
  if (!doSection.length) {
    const tie = primaryDecisionTieLine(primaryResolution, t)
    if (tie) doSection.push({ text: tie })
    else doSection.push({ text: t('drill_intel_do_fallback') })
  }

  return {
    what: dedupeCap(what, MAX),
    why: dedupeCap(why, MAX),
    do: dedupeCap(doSection, MAX),
  }
}
