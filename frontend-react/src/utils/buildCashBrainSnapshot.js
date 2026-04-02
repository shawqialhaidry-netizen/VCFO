/**
 * buildCashBrainSnapshot — liquidity & cash intelligence from executive payload only.
 * Pure function; no I/O. Numbers: compact K/M and Western % — use formatCompact / fixed decimals.
 */

import { formatCompact, formatMultiple } from './numberFormat.js'
import { factOverlapsWhy } from './buildExecutiveNarrative.js'

function dedupeBullets(narrative, bullets) {
  if (!Array.isArray(bullets) || !bullets.length) return []
  const out = []
  for (const b of bullets) {
    const t = String(b || '').trim()
    if (!t) continue
    if (narrative && factOverlapsWhy(narrative, t)) continue
    if (!out.includes(t)) out.push(t)
  }
  return out.slice(0, 2)
}

function firstFinite(...vals) {
  for (const v of vals) {
    if (v != null && Number.isFinite(Number(v))) return Number(v)
  }
  return null
}

function cashflowRoot(data) {
  const c = data?.cashflow
  if (!c || typeof c !== 'object') return null
  if (c.error === 'no data') return null
  return c
}

function statementsRoot(data) {
  const s = data?.statements
  if (!s || typeof s !== 'object' || s.available === false) return null
  return s
}

function liquidityRatios(data) {
  return data?.intelligence?.ratios?.liquidity || {}
}

function metricVal(m) {
  if (m == null) return null
  if (typeof m === 'number' && Number.isFinite(m)) return m
  if (typeof m === 'object' && m.value != null && Number.isFinite(Number(m.value))) return Number(m.value)
  return null
}

function metricStatus(m) {
  if (m && typeof m === 'object' && typeof m.status === 'string') return m.status
  return null
}

function insightSet(data) {
  const stm = statementsRoot(data)
  const raw = stm?.insights
  if (!Array.isArray(raw)) return new Set()
  return new Set(raw.map((i) => i.key).filter(Boolean))
}

function hasInsight(data, key) {
  return insightSet(data).has(key)
}

function pickOcf(data) {
  const cf = cashflowRoot(data)
  const stm = statementsRoot(data)
  return firstFinite(cf?.operating_cashflow, stm?.summary?.operating_cashflow, stm?.cashflow?.operating_cashflow)
}

function pickOcfMom(data) {
  const cf = cashflowRoot(data)
  const stm = statementsRoot(data)
  return firstFinite(
    cf?.operating_cashflow_mom,
    stm?.summary?.mom_ocf,
    stm?.cashflow?.operating_cashflow_mom
  )
}

function pickNp(data) {
  const cf = cashflowRoot(data)
  const stm = statementsRoot(data)
  return firstFinite(cf?.debug?.net_profit, stm?.summary?.latest_net_profit, stm?.income_statement?.net_profit)
}

function pickCashBalance(data) {
  const cf = cashflowRoot(data)
  const stm = statementsRoot(data)
  return firstFinite(cf?.cash_balance, stm?.cashflow?.cash_balance)
}

function pickRunway(data) {
  const cf = cashflowRoot(data)
  const stm = statementsRoot(data)
  return firstFinite(cf?.runway_months, stm?.cashflow?.runway_months)
}

function pickBurn(data) {
  const cf = cashflowRoot(data)
  const stm = statementsRoot(data)
  return firstFinite(cf?.burn_rate, stm?.cashflow?.burn_rate)
}

function pickWcNet(data) {
  const cf = cashflowRoot(data)
  const net = cf?.working_capital_change?.net
  return net != null && Number.isFinite(Number(net)) ? Number(net) : null
}

function pickKpiWc(data) {
  return firstFinite(data?.kpi_block?.kpis?.working_capital?.value)
}

function pickBsWc(data) {
  const stm = statementsRoot(data)
  return firstFinite(stm?.balance_sheet?.working_capital, stm?.summary?.working_capital)
}

function conversionQuality(data) {
  const cf = cashflowRoot(data)
  const q = cf?.quality
  if (!q || typeof q !== 'object') return null
  const cq = q.cash_conversion_quality
  return typeof cq === 'string' ? cq : null
}

function cashLex(lang) {
  const l = (lang || 'en').toLowerCase()
  if (l === 'ar') {
    return {
      sectionTitle: 'ذكاء السيولة',
      sectionSub: 'ضغط السيولة، المخاطر، والبقاء قصير الأجل — من نفس نطاق التحليل.',
      cardPressure: 'ضغط النقد',
      cardLiquidity: 'مخاطر السيولة',
      cardSurvival: 'البقاء',
      insufficient: 'بيانات غير كافية',
      pressure: {
        low: 'توليد النقد التشغيلي ضمن حدود مقبولة.',
        moderate: 'يستحق توليد النقد متابعة وإدارة.',
        high: 'تحويل الأرباح إلى نقد أو التدفق التشغيلي تحت ضغط.',
        unknown: '',
      },
      liquidity: {
        low: 'تغطية الالتزامات قصيرة الأجل ضمن نطاق مقبول.',
        moderate: 'مرونة سيولة محدودة — راقب النسبة الجارية ورأس المال العامل.',
        high: 'ضغط سيولة — التزامات قصيرة الأجل قد تفوق الموارد المتاحة.',
        unknown: '',
      },
      survival: {
        comfortable: 'احتياطي زمني مريح',
        watch: 'احتياطي زمني يحتاج متابعة',
        critical: 'احتياطي زمني ضيق',
        unknown: 'مدة البقاء غير مقدّرة',
        copyRunway: (m) => `نحو ${m} شهرًا عند معدل الحرق الحالي (تقرير).`,
        copyNoBurn: 'لا يظهر حرق مرتبط بالخسارة في الفترة؛ المؤشر لا يُحسب عادةً عند عدم وجود خسارة تشغيلية.',
        copyUnknownLoss: 'خسارة تشغيلية مع بيانات نقدية غير كافية لتقدير المدة.',
      },
      bullets: {
        ocf: (a) => `التدفق النقدي التشغيلي: ${a}`,
        ocfMom: (p) => `التدفق التشغيلي مقارنة بالشهر السابق: ${p}`,
        convert: (q) => `جودة التحويل النقدي: ${q}`,
        wcNet: (a) => `صافي حركة رأس المال العامل: ${a}`,
        insightBelow: 'التحصيل يتأخر عن الأرباح المعلنة (مؤشر البيانات).',
        currentRatio: (r) => `النسبة الجارية: ${r}`,
        quickRatio: (r) => `النسبة السريعة: ${r}`,
        wcNeg: (a) => `رأس المال العامل سالب (${a}).`,
      },
      convLabel: (q) =>
        q === 'strong' ? 'قوية' : q === 'moderate' ? 'متوسطة' : q === 'weak' ? 'ضعيفة' : q,
    }
  }
  if (l === 'tr') {
    return {
      sectionTitle: 'Nakit zekâsı',
      sectionSub: 'Aynı yönetici kapsamından likidite baskısı, risk ve kısa vadeli sürdürülebilirlik.',
      cardPressure: 'Nakit baskısı',
      cardLiquidity: 'Likidite riski',
      cardSurvival: 'Sürdürülebilirlik',
      insufficient: 'Veri yetersiz',
      pressure: {
        low: 'İşletme nakit üretimi yönetilebilir görünüyor.',
        moderate: 'Nakit üretimi yakından izlenmeli.',
        high: 'Kârın nakde dönüşümü veya işletme nakdi baskı altında.',
        unknown: '',
      },
      liquidity: {
        low: 'Kısa vadeli yükümlülük karşılama makul seviyede.',
        moderate: 'Likidite marjı sıkı — cari oran ve işletme sermayesini izleyin.',
        high: 'Likidite sıkışıklığı — kısa vadeli yükümlülükler kaynakları aşabilir.',
        unknown: '',
      },
      survival: {
        comfortable: 'Görece rahat süre',
        watch: 'İzlenecek süre',
        critical: 'Sıkı süre',
        unknown: 'Süre tahmin edilemiyor',
        copyRunway: (m) => `Mevcut harcama hızıyla kabaca ${m} ay (rapor).`,
        copyNoBurn: 'Dönem zararına bağlı nakit erimesi görünmüyor; gösterge genelde zarar yokken hesaplanmaz.',
        copyUnknownLoss: 'Zarar var; nakit tarafı süre tahmini için yetersiz.',
      },
      bullets: {
        ocf: (a) => `İşletme nakdi: ${a}`,
        ocfMom: (p) => `İşletme nakdi önceki aya göre: ${p}`,
        convert: (q) => `Nakit dönüşüm kalitesi: ${q}`,
        wcNet: (a) => `Net işletme sermayesi hareketi: ${a}`,
        insightBelow: 'Beyan edilen kâra göre nakit daha zayıf (veri göstergesi).',
        currentRatio: (r) => `Cari oran: ${r}`,
        quickRatio: (r) => `Asit-test oranı: ${r}`,
        wcNeg: (a) => `İşletme sermayesi negatif (${a}).`,
      },
      convLabel: (q) =>
        q === 'strong' ? 'Güçlü' : q === 'moderate' ? 'Orta' : q === 'weak' ? 'Zayıf' : q,
    }
  }
  return {
    sectionTitle: 'Cash Brain',
    sectionSub: 'Liquidity pressure, risk, and short-term runway — same executive scope.',
    cardPressure: 'Cash pressure',
    cardLiquidity: 'Liquidity risk',
    cardSurvival: 'Survival',
    insufficient: 'Insufficient data',
    pressure: {
      low: 'Operating cash generation looks manageable.',
      moderate: 'Cash generation warrants attention.',
      high: 'Cash conversion or operating cash flow is under pressure.',
      unknown: '',
    },
    liquidity: {
      low: 'Short-term coverage appears within range.',
      moderate: 'Liquidity headroom is tight — watch current ratio and working capital.',
      high: 'Liquidity strain — short-term obligations may exceed available resources.',
      unknown: '',
    },
    survival: {
      comfortable: 'Comfortable runway',
      watch: 'Runway to watch',
      critical: 'Tight runway',
      unknown: 'Runway not estimated',
      copyRunway: (m) => `~${m} months at current burn (reported).`,
      copyNoBurn: 'No loss-driven burn indicated; runway is usually not computed when earnings are not loss-making.',
      copyUnknownLoss: 'Loss-making period with insufficient cash inputs to estimate runway.',
    },
    bullets: {
      ocf: (a) => `Operating cash flow: ${a}`,
      ocfMom: (p) => `Operating cash flow vs prior month: ${p}`,
      convert: (q) => `Cash conversion quality: ${q}`,
      wcNet: (a) => `Net working-capital movement: ${a}`,
      insightBelow: 'Collections lag reported profit (data signal).',
      currentRatio: (r) => `Current ratio: ${r}`,
      quickRatio: (r) => `Quick ratio: ${r}`,
      wcNeg: (a) => `Working capital is negative (${a}).`,
    },
    convLabel: (q) => q,
  }
}

function fmtMomPct(v) {
  if (v == null || !Number.isFinite(Number(v))) return ''
  const n = Number(v)
  return `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`
}

function liquidityInsightSeverity(data, key) {
  const stm = statementsRoot(data)
  const raw = stm?.insights
  if (!Array.isArray(raw)) return null
  const row = raw.find((i) => i.key === key)
  return row?.severity || null
}

function buildPressure(data, L, narrative) {
  const ocf = pickOcf(data)
  const ocfMom = pickOcfMom(data)
  const np = pickNp(data)
  const cq = conversionQuality(data)
  const wcNet = pickWcNet(data)
  const below = hasInsight(data, 'cashflow_below_profit')

  const evidence = {
    operating_cashflow: ocf,
    operating_cashflow_mom: ocfMom,
    net_profit: np,
    cash_conversion_quality: cq,
    working_capital_change_net: wcNet,
    insight_cashflow_below_profit: below,
  }

  const hasSignal =
    ocf != null ||
    ocfMom != null ||
    (cq && cq !== 'indeterminate') ||
    below ||
    (wcNet != null && wcNet !== 0)

  if (!hasSignal) {
    return {
      tier: 'unknown',
      headline: '',
      bullets: [],
      evidence,
      meaningful: false,
    }
  }

  let tier = 'low'
  if (ocf != null && ocf < 0) tier = 'high'
  else if (np != null && np > 0 && cq === 'weak') tier = 'high'
  else if (below) tier = tier === 'high' ? 'high' : 'moderate'
  else if (ocfMom != null && ocfMom <= -20) tier = tier === 'high' ? 'high' : 'moderate'
  else if (cq === 'weak') tier = 'moderate'
  else if (cq === 'moderate' || (ocfMom != null && ocfMom <= -10)) tier = 'moderate'
  else if (wcNet != null && ocf != null && ocf > 0 && wcNet < 0 && Math.abs(wcNet) > ocf * 0.2)
    tier = 'moderate'

  const rawBullets = []
  if (ocf != null) rawBullets.push(L.bullets.ocf(formatCompact(ocf)))
  if (ocfMom != null) rawBullets.push(L.bullets.ocfMom(fmtMomPct(ocfMom)))
  if (cq && cq !== 'indeterminate') rawBullets.push(L.bullets.convert(L.convLabel(cq)))
  if (below) rawBullets.push(L.bullets.insightBelow)
  if (wcNet != null && wcNet !== 0) rawBullets.push(L.bullets.wcNet(formatCompact(wcNet)))

  const bullets = dedupeBullets(narrative, rawBullets)

  return {
    tier,
    headline: L.pressure[tier] || L.pressure.moderate,
    bullets,
    evidence,
    meaningful: true,
  }
}

function buildLiquidity(data, L, narrative) {
  const liq = liquidityRatios(data)
  const cr = metricVal(liq.current_ratio)
  const qr = metricVal(liq.quick_ratio)
  const crSt = metricStatus(liq.current_ratio)
  const qrSt = metricStatus(liq.quick_ratio)
  const wcLiq = metricVal(liq.working_capital)
  const wc = firstFinite(wcLiq, pickKpiWc(data), pickBsWc(data))

  const negInsight = hasInsight(data, 'negative_working_capital')
  const lowCr = hasInsight(data, 'low_current_ratio')
  const lowSev = liquidityInsightSeverity(data, 'low_current_ratio')

  const evidence = {
    current_ratio: cr,
    quick_ratio: qr,
    current_ratio_status: crSt,
    quick_ratio_status: qrSt,
    working_capital: wc,
    insight_negative_working_capital: negInsight,
    insight_low_current_ratio: lowCr,
  }

  const hasSignal =
    cr != null ||
    qr != null ||
    wc != null ||
    negInsight ||
    lowCr

  if (!hasSignal) {
    return {
      tier: 'unknown',
      headline: '',
      bullets: [],
      evidence,
      meaningful: false,
    }
  }

  let tier = 'low'
  if (negInsight || (cr != null && cr < 1) || crSt === 'risk' || (lowCr && lowSev === 'high'))
    tier = 'high'
  else if ((cr != null && cr < 1.2) || crSt === 'warning' || qrSt === 'risk' || lowCr)
    tier = 'moderate'
  else if (wc != null && wc < 0) tier = 'high'
  else if (qr != null && qr < 0.7) tier = 'moderate'

  const rawBullets = []
  if (cr != null) rawBullets.push(L.bullets.currentRatio(formatMultiple(cr)))
  if (qr != null) rawBullets.push(L.bullets.quickRatio(formatMultiple(qr)))
  if (wc != null && wc < 0) rawBullets.push(L.bullets.wcNeg(formatCompact(wc)))

  const bullets = dedupeBullets(narrative, rawBullets)

  return {
    tier,
    headline: L.liquidity[tier] || L.liquidity.moderate,
    bullets,
    evidence,
    meaningful: true,
  }
}

function buildSurvival(data, L, narrative) {
  const runway = pickRunway(data)
  const burn = pickBurn(data)
  const cash = pickCashBalance(data)
  const np = pickNp(data)

  const evidence = {
    runway_months: runway,
    burn_rate: burn,
    cash_balance: cash,
    net_profit: np,
  }

  /** @type {'comfortable'|'watch'|'critical'|'unknown'} */
  let tier = 'unknown'
  let headline = L.survival.unknown
  let copy = ''

  if (runway != null && runway > 0 && Number.isFinite(runway)) {
    const rm = Math.round(runway * 10) / 10
    if (runway < 3) {
      tier = 'critical'
      headline = L.survival.critical
    } else if (runway < 6) {
      tier = 'watch'
      headline = L.survival.watch
    } else {
      tier = 'comfortable'
      headline = L.survival.comfortable
    }
    copy = L.survival.copyRunway(rm)
  } else {
    const burnZero = burn != null && burn === 0
    const profitable = np != null && np >= 0
    if (burnZero || profitable) {
      tier = 'comfortable'
      headline = L.survival.comfortable
      copy = L.survival.copyNoBurn
    } else if (np != null && np < 0) {
      tier = 'unknown'
      headline = L.survival.unknown
      copy = L.survival.copyUnknownLoss
    } else {
      return {
        tier: 'unknown',
        headline: '',
        copy: '',
        months: null,
        burn: burn != null && Number.isFinite(burn) ? burn : null,
        cash: cash != null && Number.isFinite(cash) ? cash : null,
        evidence,
        meaningful: false,
      }
    }
  }

  let outCopy = dedupeAgainstNarrativeSentence(narrative, copy)

  const meaningful =
    (runway != null && runway > 0) ||
    tier === 'comfortable' ||
    (tier === 'unknown' && np != null && np < 0 && Boolean(outCopy))

  if (!meaningful) {
    return {
      tier: 'unknown',
      headline: '',
      copy: '',
      months: runway,
      burn: burn != null && Number.isFinite(burn) ? burn : null,
      cash: cash != null && Number.isFinite(cash) ? cash : null,
      evidence,
      meaningful: false,
    }
  }

  return {
    tier,
    headline,
    copy: outCopy,
    months: runway != null && runway > 0 ? runway : null,
    burn: burn != null && Number.isFinite(burn) ? burn : null,
    cash: cash != null && Number.isFinite(cash) ? cash : null,
    evidence,
    meaningful: true,
  }
}

function dedupeAgainstNarrativeSentence(narrative, sentence) {
  const s = String(sentence || '').trim()
  if (!s || !narrative) return s
  if (factOverlapsWhy(narrative, s)) return ''
  return s
}

/**
 * @param {Record<string, unknown>} data - Executive payload slice (cashflow, statements, intelligence, kpi_block, …)
 * @param {{ lang?: string, narrative?: object }} [options]
 */
export function buildCashBrainSnapshot(data = {}, options = {}) {
  const lang = options.lang || 'en'
  const narrative = options.narrative || null
  const L = cashLex(lang)

  const pressure = buildPressure(data, L, narrative)
  const liquidity = buildLiquidity(data, L, narrative)
  const survival = buildSurvival(data, L, narrative)

  return {
    sectionTitle: L.sectionTitle,
    sectionSub: L.sectionSub,
    cardLabels: {
      pressure: L.cardPressure,
      liquidity: L.cardLiquidity,
      survival: L.cardSurvival,
    },
    insufficientLabel: L.insufficient,
    pressure: {
      tier: pressure.tier,
      headline: pressure.headline,
      bullets: pressure.bullets,
      evidence: pressure.evidence,
      meaningful: pressure.meaningful,
    },
    liquidity: {
      tier: liquidity.tier,
      headline: liquidity.headline,
      bullets: liquidity.bullets,
      evidence: liquidity.evidence,
      meaningful: liquidity.meaningful,
    },
    survival: {
      tier: survival.tier,
      headline: survival.headline,
      copy: survival.copy,
      months: survival.months ?? null,
      burn: survival.burn ?? null,
      cash: survival.cash ?? null,
      evidence: survival.evidence,
      meaningful: survival.meaningful,
    },
  }
}
