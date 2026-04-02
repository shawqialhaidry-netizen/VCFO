/**
 * buildExecutiveNarrative — executive column narrative (presentation only; same /executive payload).
 * Bullets only: max 3 per column, compact money, CFO-readable.
 */

import { formatCompact, formatMultiple } from './numberFormat.js'

const MAX_COL = 3

/** Period label: one word, language-consistent (numbers stay Western). */
function momWord(lang) {
  const l = (lang || 'en').toLowerCase()
  if (l === 'ar') return 'شهريًا'
  if (l === 'tr') return 'Aylık'
  return 'MoM'
}

/** Arabic action line — imperative prefix when source text is Latin-heavy. */
function arActionLine(title) {
  const t = String(title || '').trim()
  if (!t) return t
  if (/[A-Za-z]{4,}/.test(t)) return `نفّذ سريعًا: ${t}`
  return t
}

/** @param {string} lang */
function lex(lang) {
  const l = (lang || 'en').toLowerCase()
  if (l === 'ar') {
    return {
      revenue: 'الإيرادات',
      expenses: 'المصروفات',
      margin: 'الهامش',
      contributing: (cat, amt) => `أبرز مساهمة: ${cat} بمقدار ${amt}`,
      branchPct: (name, pct) => `${name} تمثّل ${pct}% من زيادة التكلفة`,
      branchPressure: (name, amt) => `${name}: زيادة مصروفات بمقدار ${amt} شهريًا`,
      actionFrom: (title) => arActionLine(title),
      stableWhat: 'الأداء مستقر دون انحرافات جوهرية.',
      whyOcf: (amt) => `التدفق النقدي التشغيلي: ${amt}.`,
      whyOcfMom: (p) => `مقارنة بالشهر السابق: ${p}.`,
      whyWc: (amt) => `رأس المال العامل: ${amt}.`,
      whyCr: (r) => `النسبة الجارية ${r} — السيولة ضمن المتابعة.`,
      whyNp: (amt) => `صافي الربح (سياق الفترة): ${amt}.`,
      whyNoNumber: 'لا سائد واحد؛ تابع اتجاهات الفترة.',
      doDefault: 'حافظ على الانضباط التشغيلي وراقب التدفق النقدي عن كثب.',
      healthMarginDown: (pp, cat, branch) =>
        branch && cat
          ? `انخفض الهامش ${pp} بفعل تكلفة ${cat} في ${branch}`
          : cat
            ? `انخفض الهامش ${pp} بفعل تكلفة ${cat}`
            : branch
              ? `انخفض الهامش ${pp} — أعلى ضغط في ${branch}`
              : `انخفض الهامش ${pp}`,
      healthMarginUp: (pp, cat, branch) =>
        branch && cat
          ? `ارتفع الهامش ${pp} مع تكلفة ${cat} في ${branch}`
          : cat
            ? `ارتفع الهامش ${pp} مع تكلفة ${cat}`
            : branch
              ? `ارتفع الهامش ${pp}؛ أعلى ضغط في ${branch}`
              : `ارتفع الهامش ${pp}`,
      actionPrefix: 'إجراء:',
    }
  }
  if (l === 'tr') {
    return {
      revenue: 'Gelir',
      expenses: 'Giderler',
      margin: 'Marj',
      contributing: (cat, amt) => `${cat}: ${amt} katkı`,
      branchPct: (name, pct) => `${name} maliyet artışının %${pct}'ini sürüklüyor`,
      branchPressure: (name, amt) => `${name} maliyet baskısı ${amt} Aylık`,
      actionFrom: (title) => String(title || '').trim(),
      stableWhat: 'Performans, önemli sapma olmadan istikrarlı.',
      whyOcf: (amt) => `İşletme nakdi: ${amt}.`,
      whyOcfMom: (p) => `Önceki aya göre: ${p}.`,
      whyWc: (amt) => `İşletme sermayesi: ${amt}.`,
      whyCr: (r) => `Cari oran ${r} — likidite takipte.`,
      whyNp: (amt) => `Net kâr (dönem bağlamı): ${amt}.`,
      whyNoNumber: 'Tek bir sürükleyici yok; dönem eğilimlerini izleyin.',
      doDefault: 'Mevcut operasyon disiplinini koruyun ve nakdi yakından izleyin.',
      healthMarginDown: (pp, cat, branch) =>
        branch && cat
          ? `Marj ${pp} düştü; ${branch}'de ${cat} maliyeti sürüklüyor`
          : cat
            ? `Marj ${pp} düştü; ${cat} maliyeti belirleyici`
            : branch
              ? `Marj ${pp} düştü; en yüksek baskı ${branch}`
              : `Marj ${pp} düştü`,
      healthMarginUp: (pp, cat, branch) =>
        branch && cat
          ? `Marj ${pp} arttı; ${branch}'de ${cat} maliyeti öne çıkıyor`
          : cat
            ? `Marj ${pp} arttı; ${cat} maliyeti öne çıkıyor`
            : branch
              ? `Marj ${pp} arttı; en yüksek baskı ${branch}`
              : `Marj ${pp} arttı`,
      actionPrefix: 'EYLEM:',
    }
  }
  return {
    revenue: 'Revenue',
    expenses: 'Expenses',
    margin: 'Margin',
    contributing: (cat, amt) => `${cat} contributing ${amt}`,
    branchPct: (name, pct) => `${name} driving ${pct}% of cost increase`,
    branchPressure: (name, amt) => `${name} adding ${amt} expense MoM`,
    actionFrom: (title) => String(title || '').trim(),
    stableWhat: 'Performance stable with no material deviations.',
    whyOcf: (amt) => `Operating cash flow: ${amt}.`,
    whyOcfMom: (p) => `Vs prior month: ${p}.`,
    whyWc: (amt) => `Working capital: ${amt}.`,
    whyCr: (r) => `Current ratio ${r} — liquidity in view.`,
    whyNp: (amt) => `Net profit (period context): ${amt}.`,
    whyNoNumber: 'No single driver dominates; keep monitoring period trends.',
    doDefault: 'Maintain current operational discipline and monitor cash flow closely.',
    healthMarginDown: (pp, cat, branch) =>
      branch && cat
        ? `Margin dropped ${pp} driven by ${cat} cost in ${branch}`
        : cat
          ? `Margin dropped ${pp} driven by ${cat} cost`
          : branch
            ? `Margin dropped ${pp} with ${branch} as highest pressure`
            : `Margin dropped ${pp}`,
    healthMarginUp: (pp, cat, branch) =>
      branch && cat
        ? `Margin rose ${pp} with ${cat} cost in ${branch}`
        : cat
          ? `Margin rose ${pp} with ${cat} cost mix`
          : branch
            ? `Margin rose ${pp}; ${branch} highest pressure`
            : `Margin rose ${pp}`,
    actionPrefix: 'ACTION:',
  }
}

function fmtSignedMoney(v) {
  if (v == null || v === '' || isNaN(Number(v))) return ''
  const n = Number(v)
  if (n > 0) return '+' + formatCompact(n)
  return formatCompact(n)
}

function fmtPct(p) {
  if (p == null || !Number.isFinite(Number(p))) return ''
  const n = Number(p)
  return `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`
}

function fmtPp(p) {
  if (p == null || !Number.isFinite(Number(p))) return ''
  const n = Number(p)
  return `${n >= 0 ? '+' : ''}${n.toFixed(1)}pp`
}

function arrowForDelta(n) {
  if (n == null || !Number.isFinite(Number(n))) return '→'
  if (Number(n) > 0) return '↑'
  if (Number(n) < 0) return '↓'
  return '→'
}

function _dedupePush(arr, line) {
  const t = String(line || '').trim()
  if (!t || arr.includes(t)) return
  arr.push(t)
}

/**
 * Lowercased text of WHY lines only — for deduping Key Signals / Branch intel.
 * @param {{ why?: { lines?: string[] } }} narrative
 */
export function whyTextForDedupe(narrative) {
  const lines = narrative?.why?.lines
  if (!Array.isArray(lines) || !lines.length) return ''
  return lines.join(' ').toLowerCase().replace(/\s+/g, ' ').trim()
}

/**
 * True if `factText` is already expressed in narrative WHY (substring or token overlap).
 * @param {{ why?: { lines?: string[] } } | null} narrative
 * @param {string} factText
 */
export function factOverlapsWhy(narrative, factText) {
  const why = whyTextForDedupe(narrative)
  if (!why || !factText) return false
  const f = String(factText).toLowerCase().replace(/\s+/g, ' ').trim()
  if (f.length >= 4 && why.includes(f)) return true
  const tokens = f.split(/[^a-z0-9\u0600-\u06FF]+/i).filter((t) => t.length > 2)
  if (!tokens.length) return false
  const hits = tokens.filter((t) => why.includes(t.toLowerCase()))
  return hits.length >= Math.min(2, tokens.length) || (tokens.length === 1 && hits.length === 1)
}

function buildWhatLines(payload, L, lang = 'en') {
  const lines = []
  const mw = momWord(lang)
  const kpis = payload.kpi_block?.kpis || {}
  const wc = payload.financial_brain?.available ? payload.financial_brain?.what_changed : null
  const mom = wc?.mom || {}

  const revD = mom.revenue_delta
  const expD = mom.expense_delta
  const ratioPp = mom.expense_ratio_delta_pp

  const revMomPct = kpis.revenue?.mom_pct
  const expMomPct = kpis.expenses?.mom_pct
  const nmMomPct = kpis.net_margin?.mom_pct

  if (revD != null && Number.isFinite(Number(revD))) {
    const pct =
      revMomPct != null && Number.isFinite(Number(revMomPct)) ? ` (${fmtPct(revMomPct)})` : ''
    lines.push(`${L.revenue} ${arrowForDelta(revD)} ${fmtSignedMoney(revD)}${pct} ${mw}`)
  } else if (revMomPct != null && Number.isFinite(Number(revMomPct))) {
    lines.push(`${L.revenue} ${arrowForDelta(revMomPct)} (${fmtPct(revMomPct)}) ${mw}`)
  }

  if (expD != null && Number.isFinite(Number(expD))) {
    const pct =
      expMomPct != null && Number.isFinite(Number(expMomPct)) ? ` (${fmtPct(expMomPct)})` : ''
    lines.push(`${L.expenses} ${arrowForDelta(expD)} ${fmtSignedMoney(expD)}${pct} ${mw}`)
  } else if (expMomPct != null && Number.isFinite(Number(expMomPct))) {
    lines.push(`${L.expenses} ${arrowForDelta(expMomPct)} (${fmtPct(expMomPct)}) ${mw}`)
  }

  if (ratioPp != null && Number.isFinite(Number(ratioPp))) {
    const a = Number(ratioPp) > 0 ? '↓' : Number(ratioPp) < 0 ? '↑' : '→'
    lines.push(`${L.margin} ${a} ${fmtPp(ratioPp)} ${mw}`)
  } else if (nmMomPct != null && Number.isFinite(Number(nmMomPct))) {
    lines.push(`${L.margin} ${arrowForDelta(nmMomPct)} (${fmtPct(nmMomPct)}) ${mw}`)
  }

  return lines.slice(0, MAX_COL)
}

function buildWhyLines(payload, L, lang) {
  const lines = []
  const fb = payload.financial_brain
  const links = fb?.why?.links || {}
  const cat = links.category_driver_mom
  if (cat?.category != null && cat.delta != null && Number.isFinite(Number(cat.delta))) {
    const amt = fmtSignedMoney(cat.delta)
    _dedupePush(lines, L.contributing(String(cat.category), amt))
  }

  const br = links.branch_driver
  if (br?.branch_name && br.contribution_pct_of_company_expense != null) {
    const pct = Number(br.contribution_pct_of_company_expense)
    if (Number.isFinite(pct)) _dedupePush(lines, L.branchPct(String(br.branch_name), Math.round(pct)))
    else _dedupePush(lines, String(br.branch_name))
  }

  const cp = payload.comparative_intelligence?.cost_pressure
  const momBr = cp?.driving_expense_increase_mom
  if (momBr?.branch_name && momBr.mom_delta_total_expense != null) {
    const amt = fmtSignedMoney(momBr.mom_delta_total_expense)
    _dedupePush(lines, L.branchPressure(String(momBr.branch_name), amt))
  }

  const ineff = cp?.most_inefficient_branch
  if (
    lines.length < MAX_COL &&
    ineff?.branch_name &&
    ineff.expense_pct_of_revenue != null &&
    !lines.some((l) => l.includes(String(ineff.branch_name)))
  ) {
    const tag =
      lang === 'ar'
        ? 'من الإيرادات'
        : lang === 'tr'
          ? 'gelire göre gider payı'
          : 'of revenue'
    _dedupePush(lines, `${ineff.branch_name} · ${ineff.expense_pct_of_revenue}% ${tag}`)
  }

  if (
    lang === 'en' &&
    lines.length < MAX_COL &&
    Array.isArray(payload.root_causes)
  ) {
    for (const rc of payload.root_causes) {
      const t = rc?.title || rc?.key
      if (t) {
        const s = String(t).trim()
        if (s.length > 120) _dedupePush(lines, s.slice(0, 117) + '…')
        else _dedupePush(lines, s)
      }
      if (lines.length >= MAX_COL) break
    }
  }

  return lines.slice(0, MAX_COL)
}

function ratioVal(m) {
  if (m == null) return null
  if (typeof m === 'number' && Number.isFinite(m)) return m
  if (typeof m === 'object' && m.value != null && Number.isFinite(Number(m.value))) return Number(m.value)
  return null
}

/** One WHY line that includes a number when payload exposes metrics (OCF → WC → CR → NP). */
function pickWhyNumberLine(payload, L) {
  const cf = payload.cashflow
  const cfOk = cf && typeof cf === 'object' && cf.error !== 'no data'
  if (cfOk && cf.operating_cashflow != null && Number.isFinite(Number(cf.operating_cashflow))) {
    let s = L.whyOcf(formatCompact(cf.operating_cashflow))
    if (cf.operating_cashflow_mom != null && Number.isFinite(Number(cf.operating_cashflow_mom))) {
      s += ' ' + L.whyOcfMom(fmtPct(cf.operating_cashflow_mom))
    }
    return s
  }
  const stm = payload.statements
  const ocf2 = stm?.summary?.operating_cashflow ?? stm?.cashflow?.operating_cashflow
  if (ocf2 != null && Number.isFinite(Number(ocf2))) return L.whyOcf(formatCompact(ocf2))

  const wc =
    payload.kpi_block?.kpis?.working_capital?.value ??
    stm?.summary?.working_capital ??
    stm?.balance_sheet?.working_capital
  if (wc != null && Number.isFinite(Number(wc))) return L.whyWc(formatCompact(wc))

  const liq = payload.intelligence?.ratios?.liquidity
  const cr = ratioVal(liq?.current_ratio)
  if (cr != null) return L.whyCr(formatMultiple(cr))

  const np =
    payload.kpi_block?.kpis?.net_profit?.point ??
    stm?.summary?.latest_net_profit ??
    stm?.income_statement?.net_profit
  if (np != null && Number.isFinite(Number(np))) return L.whyNp(formatCompact(np))

  return null
}

function lineHasDigit(s) {
  return /\d/.test(String(s || ''))
}

function buildHealthHeadline(payload, L) {
  const nmMomPct = payload.kpi_block?.kpis?.net_margin?.mom_pct
  if (nmMomPct == null || !Number.isFinite(Number(nmMomPct))) return ''
  const n = Number(nmMomPct)
  const pp = `${Math.abs(n).toFixed(1)}%`
  const ei = payload.expense_intelligence
  const cat = ei?.top_category?.name ? String(ei.top_category.name) : ''
  const cp = payload.comparative_intelligence?.cost_pressure
  const branch =
    (cp?.driving_expense_increase_mom?.branch_name &&
      String(cp.driving_expense_increase_mom.branch_name)) ||
    (cp?.most_inefficient_branch?.branch_name && String(cp.most_inefficient_branch.branch_name)) ||
    ''
  if (n < 0) return L.healthMarginDown(pp, cat, branch)
  if (n > 0) return L.healthMarginUp(pp, cat, branch)
  return ''
}

function buildDoLines(payload, L, lang = 'en') {
  const lines = []
  const ed2 = payload.expense_decisions_v2
  if (Array.isArray(ed2)) {
    for (const d of ed2) {
      const title = d?.title
      if (!title) continue
      let one = String(title).trim()
      if (one.length > 88) one = `${one.slice(0, 85)}…`
      _dedupePush(lines, L.actionFrom(one))
      if (lines.length >= MAX_COL) break
    }
  }
  if (lines.length < MAX_COL && payload.top_focus) {
    let t = String(payload.top_focus).trim()
    if (t.length > 88) t = `${t.slice(0, 85)}…`
    _dedupePush(lines, L.actionFrom(t))
  }
  if (lines.length < MAX_COL && Array.isArray(payload.decisions) && payload.decisions[0]?.title) {
    let t = String(payload.decisions[0].title).trim()
    if (t.length > 88) t = `${t.slice(0, 85)}…`
    _dedupePush(lines, L.actionFrom(t))
  }
  return lines.slice(0, MAX_COL)
}

/**
 * @param {Record<string, unknown>} payload - Executive `data`
 * @param {{ lang?: string }} [options]
 */
export function buildExecutiveNarrative(payload = {}, options = {}) {
  const lang = options.lang || 'en'
  const L = lex(lang)

  if (!payload || typeof payload !== 'object') {
    return {
      whatChanged: { lines: [L.stableWhat], period: '' },
      why: { lines: [L.whyNoNumber], sources: ['fallback'] },
      whatToDo: { lines: [L.doDefault], sources: ['fallback'] },
      hasContent: true,
      healthHeadline: '',
      actionPrefix: L.actionPrefix,
      actionLine: null,
    }
  }

  const wc = payload.financial_brain?.what_changed
  let whatLines = buildWhatLines(payload, L, lang).slice(0, 2)
  if (!whatLines.length) whatLines = [L.stableWhat]

  const rawWhyLines = buildWhyLines(payload, L, lang)
  const metricWhy = pickWhyNumberLine(payload, L)
  let whyLines = rawWhyLines.slice()
  if (!whyLines.length) {
    whyLines = metricWhy ? [metricWhy] : [L.whyNoNumber]
  } else {
    if (!whyLines.some(lineHasDigit) && metricWhy) _dedupePush(whyLines, metricWhy)
    whyLines = whyLines.slice(0, MAX_COL)
  }

  const rawDoLines = buildDoLines(payload, L, lang)
  let doLines = rawDoLines.length ? rawDoLines.slice(0, MAX_COL) : [L.doDefault]
  const healthHeadline = buildHealthHeadline(payload, L)
  const actionLine = rawDoLines.length ? rawDoLines[0] : null

  const whatChanged = {
    lines: whatLines,
    period: wc?.period ? String(wc.period) : '',
  }

  let whySources = ['structured']
  if (!rawWhyLines.length) {
    whySources = metricWhy ? ['metric_context'] : ['fallback']
  } else if (metricWhy && !rawWhyLines.some(lineHasDigit) && whyLines.includes(metricWhy)) {
    whySources = ['structured', 'metric_context']
  }

  let doSources = ['expense_decisions_v2']
  if (!rawDoLines.length) doSources = ['fallback']

  return {
    whatChanged,
    why: { lines: whyLines, sources: whySources },
    whatToDo: { lines: doLines, sources: doSources },
    hasContent: true,
    healthHeadline,
    actionPrefix: L.actionPrefix,
    actionLine,
  }
}
