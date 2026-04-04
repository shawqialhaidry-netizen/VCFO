/**
 * numberFormat.js — Global Number Formatting Standard
 *
 * ONE source of truth for all financial number display.
 * Used by: Dashboard, ExecutiveDashboard, Analysis, Statements, Branches
 *
 * PRECISION POLICY (mandatory — no exceptions):
 *   ≥ 1,000,000  →  2 decimal places + M    e.g. 2.05M
 *   ≥ 1,000      →  1 decimal place  + K    e.g. 547.3K
 *   < 1,000      →  whole number             e.g. 842
 *   null/undefined →  —
 *   Negatives:   sign preserved              e.g. -1.23M
 */

const FALLBACK = '—'

/** LTR isolate around digit clusters inside RTL Arabic sentences. */
const LRI = '\u2066'
const PDI = '\u2069'

function isArabicUi(lang) {
  return String(lang || '')
    .trim()
    .toLowerCase()
    .startsWith('ar')
}

/**
 * Compact format: 2.05M | 547.3K | 842
 * Primary display line for financial KPI cards.
 */
export function formatCompact(value) {
  if (value == null || value === '' || isNaN(Number(value))) return FALLBACK
  const v = Number(value)
  const a = Math.abs(v)
  const s = v < 0 ? '-' : ''
  if (a >= 1_000_000) return `${s}${(a / 1_000_000).toFixed(2)}M`
  if (a >= 1_000)     return `${s}${(a / 1_000).toFixed(1)}K`
  return `${s}${Math.round(a)}`
}

/**
 * Same magnitudes as {@link formatCompact}; Arabic UI uses مليون/ألف + isolated Western digits (no Latin K/M inside Arabic copy).
 */
export function formatCompactForLang(value, lang) {
  if (!isArabicUi(lang)) return formatCompact(value)
  if (value == null || value === '' || isNaN(Number(value))) return FALLBACK
  const v = Number(value)
  const a = Math.abs(v)
  const neg = v < 0 ? '-' : ''
  const wrap = (n) => `${LRI}${n}${PDI}`
  if (a >= 1_000_000) return `${neg}${wrap((a / 1_000_000).toFixed(2))} مليون`
  if (a >= 1_000) return `${neg}${wrap((a / 1_000).toFixed(1))} ألف`
  return `${neg}${wrap(String(Math.round(a)))}`
}

/**
 * Full format: 2,050,000 | 547,300 | 842
 * Secondary display line (subtitle) for exact value visibility.
 */
export function formatFull(value) {
  if (value == null || value === '' || isNaN(Number(value))) return FALLBACK
  const v = Number(value)
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(v)
}

/** Full amount with isolated digits when embedded in Arabic RTL paragraphs. */
export function formatFullForLang(value, lang) {
  if (!isArabicUi(lang)) return formatFull(value)
  if (value == null || value === '' || isNaN(Number(value))) return FALLBACK
  const v = Number(value)
  const s = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(v)
  return `${LRI}${s}${PDI}`
}

/**
 * Dual format: returns { compact, full } for two-line display.
 * compact → main line
 * full    → subtitle
 */
export function formatDual(value) {
  return {
    compact: formatCompact(value),
    full:    formatFull(value),
  }
}

export function formatDualForLang(value, lang) {
  return {
    compact: formatCompactForLang(value, lang),
    full: formatFullForLang(value, lang),
  }
}

/**
 * Percentage format: 26.7% | —
 * Used for margins and ratios shown as percentages.
 */
export function formatPct(value, decimals = 1) {
  if (value == null || isNaN(Number(value))) return FALLBACK
  return `${Number(value).toFixed(decimals)}%`
}

/** Percentage; Arabic UI uses ٪ (U+066A) instead of ASCII %. */
export function formatPctForLang(value, decimals = 1, lang) {
  if (value == null || isNaN(Number(value))) return FALLBACK
  const n = Number(value).toFixed(decimals)
  if (!isArabicUi(lang)) return `${n}%`
  return `${n}٪`
}

/**
 * Signed MoM / YoY style percent: +5.2% / −5.2% (en) or ٪ for Arabic.
 */
export function formatSignedPctForLang(value, decimals = 1, lang) {
  if (value == null || isNaN(Number(value))) return FALLBACK
  const n = Number(value)
  const body = formatPctForLang(Math.abs(n), decimals, lang)
  if (n > 0) return `+${body}`
  if (n < 0) return `-${body}`
  return body
}

/** Percentage points (margin mix deltas): +1.2pp with optional digit isolation for Arabic. */
export function formatPpForLang(value, decimals = 1, lang) {
  if (value == null || isNaN(Number(value))) return FALLBACK
  const n = Number(value)
  const sign = n >= 0 ? '+' : '-'
  const absStr = Math.abs(n).toFixed(decimals)
  if (!isArabicUi(lang)) return `${sign}${absStr}pp`
  return `${sign}${LRI}${absStr}${PDI}pp`
}

/**
 * Multiplier format: 3.66x | —
 * Used for ratios like current_ratio.
 */
export function formatMultiple(value, decimals = 2) {
  if (value == null || isNaN(Number(value))) return FALLBACK
  return `${Number(value).toFixed(decimals)}x`
}

/** Ratio multiplier; Arabic uses × instead of Latin `x` when adjacent to Arabic text. */
export function formatMultipleForLang(value, decimals = 2, lang) {
  const s = formatMultiple(value, decimals)
  if (!isArabicUi(lang)) return s
  return s.replace(/x$/i, '×')
}

/**
 * Days format: 12d | —
 * Used for DSO, CCC, DPO.
 */
export function formatDays(value) {
  if (value == null || isNaN(Number(value))) return FALLBACK
  return `${Math.round(Number(value))}d`
}

/**
 * MoM/change arrow helper.
 */
export function arrow(value) {
  if (value == null) return ''
  return value > 0.3 ? '↑' : value < -0.3 ? '↓' : '→'
}

/**
 * Sign prefix: +547.3K | -123.4K | 0
 */
export function formatCompactSigned(value) {
  if (value == null || isNaN(Number(value))) return FALLBACK
  const v = Number(value)
  const sign = v > 0 ? '+' : ''
  return `${sign}${formatCompact(v)}`
}

export function formatCompactSignedForLang(value, lang) {
  if (value == null || isNaN(Number(value))) return FALLBACK
  const v = Number(value)
  const sign = v > 0 ? '+' : ''
  return `${sign}${formatCompactForLang(v, lang)}`
}
