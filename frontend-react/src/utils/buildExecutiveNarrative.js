/**
 * buildExecutiveNarrative — executive column narrative (presentation only; same /executive payload).
 * Bullets only: max 3 per column, compact money, CFO-readable.
 */

import {
  formatCompactForLang,
  formatMultipleForLang,
  formatPctForLang,
  formatPpForLang,
  formatSignedPctForLang,
} from './numberFormat.js'
import { normalizeUiLang } from './strictI18n.js'

const MAX_COL = 3

/** Period label: one word, language-consistent (numbers stay Western). */
function momWord(lang) {
  const l = normalizeUiLang(lang)
  if (l === 'ar') return 'شهريًا'
  if (l === 'tr') return 'Aylık'
  return 'MoM'
}

/**
 * Narrative lexicon from i18n (single source; no hardcoded English in ar/tr paths).
 * @param {(key: string, params?: Record<string, string>) => string} t
 * @param {string} mw - momentum label (e.g. mom_label)
 */
function lexFromTranslate(t, mw, lang) {
  return {
    revenue: t('narr_word_revenue'),
    expenses: t('narr_word_expenses'),
    margin: t('narr_word_margin'),
    contributing: (cat, amt) => t('narr_contributing', { cat, amt }),
    branchPct: (name, pct) =>
      t('narr_branch_pct', { name, pct: formatPctForLang(Number(pct), 0, lang) }),
    branchPressure: (name, amt) => t('narr_branch_pressure', { name, amt, mom_word: mw }),
    actionFrom: (title) => t('narr_action_entity', { title }),
    stableWhat: t('narr_stable_what'),
    whyOcf: (amt) => t('narr_why_ocf', { amt }),
    whyOcfMom: (p) => t('narr_why_ocf_mom', { p }),
    whyWc: (amt) => t('narr_why_wc', { amt }),
    whyCr: (r) => t('narr_why_cr', { r }),
    whyNp: (amt) => t('narr_why_np', { amt }),
    whyNoNumber: t('narr_why_no_number'),
    doDefault: t('narr_do_default'),
    healthMarginDown: (pp, cat, branch) => {
      if (branch && cat) return t('narr_hm_down_both', { pp, cat, branch })
      if (cat) return t('narr_hm_down_cat', { pp, cat })
      if (branch) return t('narr_hm_down_branch', { pp, branch })
      return t('narr_hm_down_plain', { pp })
    },
    healthMarginUp: (pp, cat, branch) => {
      if (branch && cat) return t('narr_hm_up_both', { pp, cat, branch })
      if (cat) return t('narr_hm_up_cat', { pp, cat })
      if (branch) return t('narr_hm_up_branch', { pp, branch })
      return t('narr_hm_up_plain', { pp })
    },
    actionPrefix: t('narr_action_prefix'),
    rootCauseLine: (title) => t('narr_root_cause_item', { title }),
  }
}

/**
 * @param {string} lang
 * @param {string} momentumSuffix - MoM wording from i18n `mom_label` (or legacy fallback)
 */
function lex(lang, momentumSuffix) {
  const l = normalizeUiLang(lang)
  const mw =
    momentumSuffix != null && String(momentumSuffix).trim() !== ''
      ? String(momentumSuffix)
      : momWord(lang)
  if (l === 'ar') {
    return {
      revenue: 'الإيرادات',
      expenses: 'المصروفات',
      margin: 'الهامش',
      contributing: (cat, amt) => `أبرز مساهمة: ${cat} بمقدار ${amt}`,
      branchPct: (name, pct) => `${name} تمثّل ${formatPctForLang(Number(pct), 0, lang)} من زيادة التكلفة`,
      branchPressure: (name, amt) => `${name}: زيادة مصروفات بمقدار ${amt} ${mw}`,
      actionFrom: (title) => String(title || '').trim(),
      stableWhat: 'الأداء مستقر دون انحرافات جوهرية.',
      whyOcf: (amt) => `التدفق النقدي التشغيلي: ${amt}.`,
      whyOcfMom: (p) => `مقارنة بالشهر السابق: ${p}.`,
      whyWc: (amt) => `رأس المال العامل: ${amt}.`,
      whyCr: (r) => `النسبة الجارية ${r} — السيولة ضمن المتابعة.`,
      whyNp: (amt) => `صافي الربح (سياق الفترة): ${amt}.`,
      whyNoNumber: 'لا عاملًا واحدًا يهيمن؛ راقب اتجاه الفترة ككل.',
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
      rootCauseLine: (title) => `سبب جذري: ${title}`,
    }
  }
  if (l === 'tr') {
    return {
      revenue: 'Gelir',
      expenses: 'Giderler',
      margin: 'Marj',
      contributing: (cat, amt) => `${cat}: ${amt} katkı`,
      branchPct: (name, pct) => `${name} maliyet artışına ${formatPctForLang(Number(pct), 0, lang)} ile öncülük ediyor`,
      branchPressure: (name, amt) => `${name} maliyet baskısı ${amt} ${mw}`,
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
      rootCauseLine: (title) => `Kök neden: ${title}`,
    }
  }
  return {
    revenue: 'Revenue',
    expenses: 'Expenses',
    margin: 'Margin',
    contributing: (cat, amt) => `${cat} contributing ${amt}`,
    branchPct: (name, pct) => `${name} driving ${formatPctForLang(Number(pct), 0, lang)} of cost increase`,
    branchPressure: (name, amt) => `${name} adding ${amt} expense ${mw}`,
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
    rootCauseLine: (title) => `Root cause: ${title}`,
  }
}

function fmtSignedMoney(v, lang) {
  if (v == null || v === '' || isNaN(Number(v))) return ''
  const n = Number(v)
  const fc = formatCompactForLang(n, lang)
  if (n > 0) return '+' + fc
  return fc
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

function buildWhatLines(payload, L, lang = 'en', mw) {
  const lines = []
  const momentum = mw != null && String(mw).trim() !== '' ? String(mw) : momWord(lang)
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
      revMomPct != null && Number.isFinite(Number(revMomPct))
        ? ` (${formatSignedPctForLang(revMomPct, 1, lang)})`
        : ''
    lines.push(`${L.revenue} ${arrowForDelta(revD)} ${fmtSignedMoney(revD, lang)}${pct} ${momentum}`)
  } else if (revMomPct != null && Number.isFinite(Number(revMomPct))) {
    lines.push(
      `${L.revenue} ${arrowForDelta(revMomPct)} (${formatSignedPctForLang(revMomPct, 1, lang)}) ${momentum}`,
    )
  }

  if (expD != null && Number.isFinite(Number(expD))) {
    const pct =
      expMomPct != null && Number.isFinite(Number(expMomPct))
        ? ` (${formatSignedPctForLang(expMomPct, 1, lang)})`
        : ''
    lines.push(`${L.expenses} ${arrowForDelta(expD)} ${fmtSignedMoney(expD, lang)}${pct} ${momentum}`)
  } else if (expMomPct != null && Number.isFinite(Number(expMomPct))) {
    lines.push(
      `${L.expenses} ${arrowForDelta(expMomPct)} (${formatSignedPctForLang(expMomPct, 1, lang)}) ${momentum}`,
    )
  }

  if (ratioPp != null && Number.isFinite(Number(ratioPp))) {
    const a = Number(ratioPp) > 0 ? '↓' : Number(ratioPp) < 0 ? '↑' : '→'
    lines.push(`${L.margin} ${a} ${formatPpForLang(ratioPp, 1, lang)} ${momentum}`)
  } else if (nmMomPct != null && Number.isFinite(Number(nmMomPct))) {
    lines.push(
      `${L.margin} ${arrowForDelta(nmMomPct)} (${formatSignedPctForLang(nmMomPct, 1, lang)}) ${momentum}`,
    )
  }

  return lines.slice(0, MAX_COL)
}

function buildWhyLines(payload, L, lang, translate) {
  const lines = []
  const fb = payload.financial_brain
  const links = fb?.why?.links || {}
  const cat = links.category_driver_mom
  if (cat?.category != null && cat.delta != null && Number.isFinite(Number(cat.delta))) {
    const amt = fmtSignedMoney(cat.delta, lang)
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
    const amt = fmtSignedMoney(momBr.mom_delta_total_expense, lang)
    _dedupePush(lines, L.branchPressure(String(momBr.branch_name), amt))
  }

  const ineff = cp?.most_inefficient_branch
  if (
    lines.length < MAX_COL &&
    ineff?.branch_name &&
    ineff.expense_pct_of_revenue != null &&
    !lines.some((l) => l.includes(String(ineff.branch_name)))
  ) {
    const pct = formatPctForLang(Number(ineff.expense_pct_of_revenue), 1, lang)
    const name = String(ineff.branch_name)
    if (typeof translate === 'function') {
      const ofRev = translate('cmd_branch_of_rev')
      _dedupePush(lines, translate('narr_ineff_branch_line', { name, pct, of_rev: ofRev }))
    } else {
      const tag = lang === 'ar' ? 'من الإيرادات' : lang === 'tr' ? 'gelire göre' : 'of revenue'
      _dedupePush(lines, `${name} · ${pct} ${tag}`)
    }
  }

  if (lines.length < MAX_COL && Array.isArray(payload.root_causes)) {
    for (const rc of payload.root_causes) {
      const rcTitle = rc?.title || rc?.key
      if (rcTitle) {
        const s = String(rcTitle).trim()
        const short = s.length > 120 ? `${s.slice(0, 117)}…` : s
        const line =
          typeof translate === 'function'
            ? translate('narr_root_cause_item', { title: short })
            : L.rootCauseLine(short)
        _dedupePush(lines, line)
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
function pickWhyNumberLine(payload, L, lang) {
  const cf = payload.cashflow
  const cfOk = cf && typeof cf === 'object' && cf.error !== 'no data'
  if (cfOk && cf.operating_cashflow != null && Number.isFinite(Number(cf.operating_cashflow))) {
    let s = L.whyOcf(formatCompactForLang(cf.operating_cashflow, lang))
    if (cf.operating_cashflow_mom != null && Number.isFinite(Number(cf.operating_cashflow_mom))) {
      s += ' ' + L.whyOcfMom(formatSignedPctForLang(cf.operating_cashflow_mom, 1, lang))
    }
    return s
  }
  const stm = payload.statements
  const ocf2 = stm?.summary?.operating_cashflow ?? stm?.cashflow?.operating_cashflow
  if (ocf2 != null && Number.isFinite(Number(ocf2))) return L.whyOcf(formatCompactForLang(ocf2, lang))

  const wc =
    payload.kpi_block?.kpis?.working_capital?.value ??
    stm?.summary?.working_capital ??
    stm?.balance_sheet?.working_capital
  if (wc != null && Number.isFinite(Number(wc))) return L.whyWc(formatCompactForLang(wc, lang))

  const liq = payload.intelligence?.ratios?.liquidity
  const cr = ratioVal(liq?.current_ratio)
  if (cr != null) return L.whyCr(formatMultipleForLang(cr, 2, lang))

  const np =
    payload.kpi_block?.kpis?.net_profit?.point ??
    stm?.summary?.latest_net_profit ??
    stm?.income_statement?.net_profit
  if (np != null && Number.isFinite(Number(np))) return L.whyNp(formatCompactForLang(np, lang))

  return null
}

function lineHasDigit(s) {
  return /\d/.test(String(s || ''))
}

function buildHealthHeadline(payload, L, lang) {
  const nmMomPct = payload.kpi_block?.kpis?.net_margin?.mom_pct
  if (nmMomPct == null || !Number.isFinite(Number(nmMomPct))) return ''
  const n = Number(nmMomPct)
  const pp = formatPctForLang(Math.abs(n), 1, lang)
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
      if (one.length > 88) one = one.slice(0, 85)
      _dedupePush(lines, L.actionFrom(one))
      if (lines.length >= MAX_COL) break
    }
  }
  if (lines.length < MAX_COL && payload.top_focus) {
    let t = String(payload.top_focus).trim()
    if (t.length > 88) t = t.slice(0, 85)
    _dedupePush(lines, L.actionFrom(t))
  }
  if (lines.length < MAX_COL && Array.isArray(payload.decisions) && payload.decisions[0]?.title) {
    let t = String(payload.decisions[0].title).trim()
    if (t.length > 88) t = t.slice(0, 85)
    _dedupePush(lines, L.actionFrom(t))
  }
  return lines.slice(0, MAX_COL)
}

/**
 * @param {Record<string, unknown>} payload - Executive `data`
 * @param {{ lang?: string, t?: (key: string, params?: Record<string, string>) => string }} [options] — pass LangContext `tr` (supports params) for i18n-backed lines
 */
export function buildExecutiveNarrative(payload = {}, options = {}) {
  const lang = normalizeUiLang(options.lang)
  const translate = typeof options.t === 'function' ? options.t : null
  const mw = translate ? translate('mom_label') : momWord(lang)
  const L = translate ? lexFromTranslate(translate, mw, lang) : lex(lang, mw)

  if (!payload || typeof payload !== 'object') {
    return {
      whatChanged: { lines: [L.stableWhat], period: '' },
      why: { lines: [L.whyNoNumber], sources: ['fallback'] },
      whatToDo: { lines: [L.doDefault], sources: ['fallback'] },
      hasContent: false,
      healthHeadline: '',
      actionPrefix: L.actionPrefix,
      actionLine: null,
    }
  }

  const items = Array.isArray(payload.realized_causal_items) ? payload.realized_causal_items : []

  /** @param {'change_text'|'cause_text'|'action_text'} field */
  const takeField = (field, max) => {
    const lines = []
    for (const it of items) {
      const t = String(it[field] || '').trim()
      if (!t) continue
      if (!lines.includes(t)) lines.push(t)
      if (lines.length >= max) break
    }
    return lines
  }

  let whatLines = takeField('change_text', MAX_COL)
  if (!whatLines.length) whatLines = [L.stableWhat]

  let whyLines = takeField('cause_text', MAX_COL)
  if (!whyLines.length) whyLines = [L.whyNoNumber]

  let doLines = takeField('action_text', MAX_COL)
  if (!doLines.length) doLines = [L.doDefault]

  const healthHeadline = whatLines[0] || ''
  const actionLine = doLines[0] || null

  return {
    whatChanged: { lines: whatLines, period: '' },
    why: { lines: whyLines, sources: items.length ? ['causal'] : ['fallback'] },
    whatToDo: { lines: doLines, sources: items.length ? ['causal'] : ['fallback'] },
    hasContent: items.length > 0,
    healthHeadline,
    actionPrefix: L.actionPrefix,
    actionLine,
  }
}
