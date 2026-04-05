/**
 * Drill “AI Explanation” — What / Why / Do built only from structured payload fields + strict i18n.
 * No narrative prose ingestion, no global text reconstruction, no raw-backend sentence rewriting here.
 */
import { formatCompactForLang, formatPctForLang, formatSignedPctForLang } from './numberFormat.js'

const MAX = 3

function sliceTitle(t, n = 96) {
  const s = String(t || '').trim()
  if (!s) return ''
  return s.length > n ? `${s.slice(0, n - 1)}…` : s
}

function normLine(s) {
  return String(s || '')
    .trim()
    .toLowerCase()
}

function dedupeCap(items, n = MAX) {
  const seen = new Set()
  const out = []
  for (const it of items) {
    const text = it && typeof it.text === 'string' ? it.text.trim() : ''
    if (!text) continue
    const k = normLine(text)
    if (seen.has(k)) continue
    seen.add(k)
    out.push({ ...it, text })
    if (out.length >= n) break
  }
  return out
}

/** Drop lines that already appeared in an earlier section (What → Why → Do). */
function dedupeAcrossSections(what, why, doSection, n = MAX) {
  const seen = new Set()
  function take(items) {
    const out = []
    for (const it of items) {
      const k = normLine(it.text)
      if (!k || seen.has(k)) continue
      seen.add(k)
      out.push(it)
      if (out.length >= n) break
    }
    return out
  }
  return {
    what: take(what),
    why: take(why),
    do: take(doSection),
  }
}

function hasDigitIn(lines) {
  return lines.some((l) => l && /\d/.test(l.text || ''))
}

/** @param {(k: string, p?: Record<string, unknown>) => string} t */
function firstKpiSnapshotLine(kpis, t, lang) {
  const order = ['revenue', 'expenses', 'net_profit', 'net_margin']
  for (const k of order) {
    const row = kpis?.[k]
    if (row?.value == null || !Number.isFinite(Number(row.value))) continue
    const v =
      k === 'net_margin'
        ? formatPctForLang(row.value, 1, lang)
        : formatCompactForLang(Number(row.value), lang)
    return { text: t('drill_intel_kpi_level', { label: t(`kpi_label_${k}`), v }) }
  }
  return null
}

function pickExpenseCausalLine(items) {
  if (!Array.isArray(items)) return ''
  const hit = items.find((it) => String(it.id || '').toLowerCase().includes('expense'))
  const row = hit || items[0]
  if (!row) return ''
  return String(row.action_text || row.change_text || '').trim()
}

/**
 * @param {object | null | undefined} primaryResolution
 * @param {(k: string, p?: Record<string, unknown>) => string} t
 * @param {object[] | undefined} realizedCausalItems — executive `realized_causal_items`
 */
export function primaryDecisionTieLine(primaryResolution, t, realizedCausalItems) {
  if (!primaryResolution) return null
  if (primaryResolution.kind === 'expense') {
    const ex = primaryResolution.expense
    if (ex.decision_id === '_cmd_baseline') return null
    const line =
      String(ex?.causal_realized?.action_text || ex?.causal_realized?.change_text || '').trim() ||
      pickExpenseCausalLine(realizedCausalItems)
    if (!line) return null
    return t('drill_intel_follow_primary', { title: sliceTitle(line, 100) })
  }
  const d = primaryResolution.decision
  const line =
    String(d?.causal_realized?.action_text || d?.causal_realized?.change_text || '').trim() ||
    pickExpenseCausalLine(realizedCausalItems)
  if (!line) return null
  return t('drill_intel_follow_primary', { title: sliceTitle(line, 100) })
}

function resolveKpis(bundle, extra) {
  return (
    bundle.kpis ||
    extra?.execChartBundle?.kpi_block?.kpis ||
    {}
  )
}

function momWord(t) {
  return t('mom_label')
}

function pushRevenueMom(kpis, t, arr, lang) {
  const r = kpis?.revenue?.mom_pct
  if (r == null || !Number.isFinite(Number(r))) return
  const n = Number(r)
  if (n > 0)
    arr.push({ text: t('drill_sig_rev_mom_up', { pct: formatPctForLang(n, 1, lang), mom_word: momWord(t) }) })
  else if (n < 0)
    arr.push({
      text: t('drill_sig_rev_mom_down', { pct: formatPctForLang(Math.abs(n), 1, lang), mom_word: momWord(t) }),
    })
  else arr.push({ text: t('drill_sig_rev_mom_flat') })
}

function pushExpenseMom(kpis, t, arr, lang) {
  const e = kpis?.expenses?.mom_pct
  if (e == null || !Number.isFinite(Number(e))) return
  const n = Number(e)
  if (n > 0)
    arr.push({ text: t('drill_sig_exp_mom_up', { pct: formatPctForLang(n, 1, lang), mom_word: momWord(t) }) })
  else if (n < 0)
    arr.push({
      text: t('drill_sig_exp_mom_down', { pct: formatPctForLang(Math.abs(n), 1, lang), mom_word: momWord(t) }),
    })
  else arr.push({ text: t('drill_sig_exp_mom_flat') })
}

function pushExpenseOutpacesRevenue(kpis, t, arr) {
  const r = kpis?.revenue?.mom_pct
  const e = kpis?.expenses?.mom_pct
  if (r == null || e == null || !Number.isFinite(Number(r)) || !Number.isFinite(Number(e))) return
  if (Number(e) > Number(r)) arr.push({ text: t('drill_sig_expense_faster_than_revenue') })
}

function pushNetProfitLoss(kpis, t, arr) {
  const v = kpis?.net_profit?.value
  if (v == null || !Number.isFinite(Number(v))) return
  if (Number(v) < 0) arr.push({ text: t('drill_sig_operating_loss') })
}

function pushNetProfitMom(kpis, t, arr, lang) {
  const m = kpis?.net_profit?.mom_pct
  if (m == null || !Number.isFinite(Number(m))) return
  const n = Number(m)
  if (n > 0)
    arr.push({ text: t('drill_sig_np_mom_up', { pct: formatPctForLang(n, 1, lang), mom_word: momWord(t) }) })
  else if (n < 0)
    arr.push({
      text: t('drill_sig_np_mom_down', { pct: formatPctForLang(Math.abs(n), 1, lang), mom_word: momWord(t) }),
    })
}

function pushExpenseIntelWhy(expenseIntel, t, arr, lang) {
  if (expenseIntel?.top_category?.name && expenseIntel?.available === true) {
    const name = String(expenseIntel.top_category.name)
    const amt =
      expenseIntel.top_category.amount != null && Number.isFinite(Number(expenseIntel.top_category.amount))
        ? formatCompactForLang(Number(expenseIntel.top_category.amount), lang)
        : '—'
    const sh = expenseIntel.top_category.share_of_cost_pct
    if (sh != null && Number.isFinite(Number(sh))) {
      arr.push({
        text: t('drill_intel_top_expense_share', {
          name,
          amt,
          share: formatPctForLang(Number(sh), 1, lang),
        }),
      })
    } else {
      arr.push({ text: t('drill_intel_top_expense_short', { name, amt }) })
    }
  }
}

function pushTopBranchWhy(ci, t, arr, lang) {
  const topBr = ci?.efficiency_ranking?.by_expense_pct_of_revenue_desc?.[0]
  if (topBr?.branch_name == null || topBr.expense_pct_of_revenue == null) return
  if (!Number.isFinite(Number(topBr.expense_pct_of_revenue))) return
  arr.push({
    text: t('drill_intel_branch_expense_line', {
      name: String(topBr.branch_name),
      pct: formatPctForLang(Number(topBr.expense_pct_of_revenue), 1, lang),
    }),
  })
}

function pushRatioRisk(ratioObj, ratioKey, t, arr) {
  const r = ratioObj?.[ratioKey]
  if (r?.status !== 'risk') return
  arr.push({
    text: t('drill_sig_ratio_pressure', { label: t(`ratio_${ratioKey}`) }),
  })
}

/** First N ratios in `obj` with status risk — label from ratio_<key> i18n when present. */
function pushRiskRatiosFromObject(obj, t, arr, max = 2) {
  let n = 0
  for (const [k, r] of Object.entries(obj || {})) {
    if (r?.status !== 'risk') continue
    arr.push({
      text: t('drill_sig_ratio_pressure', { label: t(`ratio_${k}`) }),
    })
    n++
    if (n >= max) break
  }
}

function primaryTitleSnippet(primaryResolution) {
  if (!primaryResolution) return ''
  if (primaryResolution.kind === 'expense') {
    const ex = primaryResolution.expense
    const ax = ex?.causal_realized?.action_text || ex?.causal_realized?.change_text
    if (ax) return sliceTitle(ax, 24).toLowerCase()
    return sliceTitle(ex?.title, 24).toLowerCase()
  }
  const d = primaryResolution.decision
  const ax = d?.causal_realized?.action_text || d?.causal_realized?.change_text
  if (ax) return sliceTitle(ax, 24).toLowerCase()
  return sliceTitle(d?.title, 24).toLowerCase()
}

function pushDecisionDo(primaryResolution, decisions, t, doRaw, realizedCausalItems) {
  const pd = primaryDecisionTieLine(primaryResolution, t, realizedCausalItems)
  if (pd) doRaw.push({ text: pd })

  if (!Array.isArray(decisions) || !decisions[0]) return
  const d0 = decisions[0]
  const causalLine = String(d0.causal_realized?.action_text || d0.causal_realized?.change_text || '').trim()
  if (causalLine) {
    const title = sliceTitle(causalLine, 90)
    const snippet = primaryTitleSnippet(primaryResolution)
    const head = title.toLowerCase().slice(0, 22)
    if (snippet && head && snippet.includes(head)) return
    if (pd && normLine(pd).includes(normLine(title).slice(0, 18))) return
    doRaw.push({ text: t('drill_intel_ranked_decision', { title }) })
    return
  }
  if (!d0.title) return
  const title = sliceTitle(d0.title, 90)
  const snippet = primaryTitleSnippet(primaryResolution)
  const head = title.toLowerCase().slice(0, 22)
  if (snippet && head && snippet.includes(head)) return
  if (pd && normLine(pd).includes(normLine(title).slice(0, 18))) return

  doRaw.push({ text: t('drill_intel_ranked_decision', { title }) })
}

/**
 * @param {{
 *   panelType: string,
 *   payload?: Record<string, unknown>,
 *   extra?: Record<string, unknown>,
 *   t: (k: string, p?: Record<string, unknown>) => string,
 * }} p
 * @returns {{ what: Array<{ text: string }>, why: Array<{ text: string }>, do: Array<{ text: string }> }}
 */
export function buildDrillIntelligence({ panelType, payload = {}, extra = {}, t, lang = 'en' }) {
  if (panelType === 'causal_item') {
    const c = payload || {}
    const w = []
    const y = []
    const d0 = []
    if (c.change_text) w.push({ text: String(c.change_text) })
    if (c.cause_text) y.push({ text: String(c.cause_text) })
    if (c.action_text) d0.push({ text: String(c.action_text) })
    const merged = dedupeAcrossSections(dedupeCap(w, MAX), dedupeCap(y, MAX), dedupeCap(d0, MAX), MAX)
    return { what: merged.what, why: merged.why, do: merged.do }
  }

  if (panelType === 'profit_bridge_segment') {
    const pl = payload || {}
    const vk = String(pl.varianceLineKey || '')
    const interp = pl.bridgeInterpretation || {}
    const w0 = []
    const y0 = []
    const d0 = []
    if (vk === 'revenue' && interp.revenue_effect) {
      w0.push({ text: t(`cmd_bridge_expl_revenue_${interp.revenue_effect}`) })
    } else if (vk === 'cogs' && interp.cogs_effect) {
      w0.push({ text: t(`cmd_bridge_expl_cogs_${interp.cogs_effect}`) })
    } else if (vk === 'opex' && interp.opex_effect) {
      w0.push({ text: t(`cmd_bridge_expl_opex_${interp.opex_effect}`) })
    } else if (vk === 'operating_profit' || vk === 'net_profit') {
      const nr = String(interp.net_result || '')
      if (nr === 'profit_up' || nr === 'profit_down' || nr === 'flat') {
        w0.push({ text: t(`cmd_bridge_expl_net_${nr}`) })
      }
    }
    const pd = String(interp.primary_driver || '')
    if (pd && vk && pd === vk) {
      y0.push({ text: t('cmd_bridge_expl_primary_driver_match') })
    }
    if (interp.paradox_flags && interp.paradox_flags.revenue_up_profit_down) {
      y0.push({ text: t('cmd_bridge_expl_paradox_growth_loss') })
    }
    const merged = dedupeAcrossSections(dedupeCap(w0, MAX), dedupeCap(y0, MAX), dedupeCap(d0, MAX), MAX)
    return { what: merged.what, why: merged.why, do: merged.do }
  }

  const bundle = extra?.drillIntelBundle || {}
  const kpis = resolveKpis(bundle, extra)
  const primaryResolution = bundle.primaryResolution
  const expenseIntel = bundle.expenseIntel
  const decisions = bundle.decisions || extra?.decisions || []
  const health = bundle.health
  const cashflow = extra?.execChartBundle?.cashflow || bundle.cashflow || {}
  const ci = extra?.execChartBundle?.comparative_intelligence || bundle.comparative_intelligence
  const analysisRatios = extra?.analysisRatios || {}

  const whatRaw = []
  const whyRaw = []
  const doRaw = []

  const analysisTab = panelType === 'analysis_tab' ? String(payload.tab || '') : ''

  // ── KPI drill (Command Center) ─────────────────────────────
  if (panelType === 'kpi' && payload?.type) {
    const ty = String(payload.type)

    if (ty === 'revenue') {
      pushRevenueMom(kpis, t, whatRaw, lang)
      pushNetProfitLoss(kpis, t, whatRaw)
      pushExpenseOutpacesRevenue(kpis, t, whyRaw)
      pushExpenseMom(kpis, t, whyRaw, lang)
    } else if (ty === 'expenses') {
      pushExpenseMom(kpis, t, whatRaw, lang)
      pushExpenseOutpacesRevenue(kpis, t, whyRaw)
      pushRevenueMom(kpis, t, whyRaw, lang)
    } else if (ty === 'net_profit') {
      pushNetProfitLoss(kpis, t, whatRaw)
      pushNetProfitMom(kpis, t, whatRaw, lang)
      pushExpenseOutpacesRevenue(kpis, t, whyRaw)
      pushRevenueMom(kpis, t, whyRaw, lang)
    } else if (ty === 'net_margin') {
      if (payload.mom != null && Number.isFinite(Number(payload.mom))) {
        const label = t('kpi_label_net_margin')
        const pct = formatSignedPctForLang(Number(payload.mom), 1, lang)
        whatRaw.push({ text: t('drill_intel_kpi_momentum', { label, pct, mom_word: momWord(t) }) })
      }
      if (payload.raw != null && Number.isFinite(Number(payload.raw))) {
        whatRaw.push({
          text: t('drill_intel_net_margin_level', { pct: formatPctForLang(Number(payload.raw), 1, lang) }),
        })
      }
      pushExpenseOutpacesRevenue(kpis, t, whyRaw)
      pushTopBranchWhy(ci, t, whyRaw, lang)
      pushExpenseIntelWhy(expenseIntel, t, whyRaw, lang)
    } else if (ty === 'cashflow') {
      if (cashflow?.operating_cashflow != null && Number.isFinite(Number(cashflow.operating_cashflow))) {
        whatRaw.push({
          text: t('drill_intel_ocf_level', { v: formatCompactForLang(Number(cashflow.operating_cashflow), lang) }),
        })
      }
      pushNetProfitLoss(kpis, t, whyRaw)
    } else {
      if (payload.mom != null && Number.isFinite(Number(payload.mom))) {
        const label = t(`kpi_label_${ty}`)
        const pct = formatSignedPctForLang(Number(payload.mom), 1, lang)
        whatRaw.push({ text: t('drill_intel_kpi_momentum', { label, pct, mom_word: momWord(t) }) })
      }
    }
  }

  // ── Domain drill ───────────────────────────────────────────
  if (panelType === 'domain' && payload?.domain != null && payload.score != null) {
    const dom = String(payload.domain)
    whatRaw.push({
      text: t('drill_intel_domain_score_line', {
        domain: t(`domain_${dom}_simple`),
        score: String(Math.round(Number(payload.score))),
      }),
    })
    const sc = Number(payload.score)
    if (Number.isFinite(sc)) {
      if (sc < 40) {
        whyRaw.push({
          text: t('drill_sig_domain_score_stress', {
            domain: t(`domain_${dom}_simple`),
            score: String(Math.round(sc)),
          }),
        })
      } else if (sc < 60) {
        whyRaw.push({
          text: t('drill_sig_domain_score_watch', {
            domain: t(`domain_${dom}_simple`),
            score: String(Math.round(sc)),
          }),
        })
      }
    }
  }

  // ── Branch compare drill ───────────────────────────────────
  if (panelType === 'branch_compare') {
    whatRaw.push({ text: t('drill_sig_branch_panel_context') })
    pushTopBranchWhy(ci, t, whyRaw, lang)
    pushExpenseOutpacesRevenue(kpis, t, whyRaw)
  }

  // ── Alert drill ────────────────────────────────────────────
  if (panelType === 'alert') {
    const sev = String(payload.severity || '').toLowerCase()
    if (sev === 'high') whatRaw.push({ text: t('drill_sig_alert_severity_high') })
    else whatRaw.push({ text: t('drill_sig_alert_severity_watch') })
    if (health != null && Number.isFinite(Number(health))) {
      whyRaw.push({ text: t('drill_intel_health_score', { v: String(Math.round(Number(health))) }) })
    }
    pushExpenseOutpacesRevenue(kpis, t, whyRaw)
  }

  // ── Decision & expense decision drill ──────────────────────
  if (panelType === 'decision' || panelType === 'expense_v2') {
    const snap = firstKpiSnapshotLine(kpis, t, lang)
    if (snap) whatRaw.push(snap)
    else if (health != null && Number.isFinite(Number(health))) {
      whatRaw.push({ text: t('drill_intel_health_score', { v: String(Math.round(Number(health))) }) })
    }
    pushExpenseIntelWhy(expenseIntel, t, whyRaw, lang)
    pushExpenseOutpacesRevenue(kpis, t, whyRaw)
    pushTopBranchWhy(ci, t, whyRaw, lang)
  }

  // ── Analysis tab drill (structured ratios + KPIs) ───────────
  if (analysisTab) {
    const prof = analysisRatios.profitability || {}
    const liq = analysisRatios.liquidity || {}
    const eff = analysisRatios.efficiency || {}

    if (analysisTab === 'profitability') {
      pushRevenueMom(kpis, t, whatRaw, lang)
      pushNetProfitLoss(kpis, t, whatRaw)
      pushNetProfitMom(kpis, t, whatRaw, lang)
      pushExpenseOutpacesRevenue(kpis, t, whyRaw)
      pushExpenseMom(kpis, t, whyRaw, lang)
      pushRatioRisk(prof, 'net_margin_pct', t, whyRaw)
      pushRatioRisk(prof, 'gross_margin_pct', t, whyRaw)
    } else if (analysisTab === 'liquidity') {
      whatRaw.push({ text: t('drill_sig_tab_liquidity_what') })
      pushRatioRisk(liq, 'current_ratio', t, whyRaw)
      pushRatioRisk(liq, 'quick_ratio', t, whyRaw)
      if (!whyRaw.length) {
        whyRaw.push({ text: t('drill_sig_tab_liquidity_why_hint') })
      }
    } else if (analysisTab === 'efficiency') {
      whatRaw.push({ text: t('drill_sig_tab_efficiency_what') })
      pushRiskRatiosFromObject(eff, t, whyRaw, 2)
      pushTopBranchWhy(ci, t, whyRaw, lang)
      if (!whyRaw.length) {
        whyRaw.push({ text: t('drill_sig_tab_efficiency_why_hint') })
      }
    } else if (analysisTab === 'decisions' || analysisTab === 'alerts') {
      const snap = firstKpiSnapshotLine(kpis, t, lang)
      if (snap) whatRaw.push(snap)
      if (analysisTab === 'alerts' && health != null && Number.isFinite(Number(health))) {
        whyRaw.push({ text: t('drill_intel_health_score', { v: String(Math.round(Number(health))) }) })
      }
      if (analysisTab === 'decisions') {
        pushExpenseIntelWhy(expenseIntel, t, whyRaw, lang)
      }
    } else if (analysisTab === 'overview') {
      pushRevenueMom(kpis, t, whatRaw, lang)
      pushNetProfitLoss(kpis, t, whatRaw)
      if (health != null && Number.isFinite(Number(health))) {
        whyRaw.push({ text: t('drill_intel_health_score', { v: String(Math.round(Number(health))) }) })
      }
      pushExpenseOutpacesRevenue(kpis, t, whyRaw)
    }
  }

  pushDecisionDo(primaryResolution, decisions, t, doRaw, bundle.realizedCausalItems)

  let what = dedupeCap(whatRaw, MAX)
  let why = dedupeCap(whyRaw, MAX)
  let doSection = dedupeCap(doRaw, MAX)

  const preCombined = [...what, ...why, ...doSection]
  if (!hasDigitIn(preCombined)) {
    const snap = firstKpiSnapshotLine(kpis, t, lang)
    if (snap) what = dedupeCap([snap, ...what], MAX)
    else if (health != null && Number.isFinite(Number(health))) {
      what = dedupeCap([{ text: t('drill_intel_health_score', { v: String(Math.round(Number(health))) }) }, ...what], MAX)
    }
  }

  const merged = dedupeAcrossSections(what, why, doSection, MAX)

  return {
    what: merged.what,
    why: merged.why,
    do: merged.do,
  }
}
