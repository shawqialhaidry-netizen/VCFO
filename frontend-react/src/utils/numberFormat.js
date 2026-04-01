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
 * Full format: 2,050,000 | 547,300 | 842
 * Secondary display line (subtitle) for exact value visibility.
 */
export function formatFull(value) {
  if (value == null || value === '' || isNaN(Number(value))) return FALLBACK
  const v = Number(value)
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(v)
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

/**
 * Percentage format: 26.7% | —
 * Used for margins and ratios shown as percentages.
 */
export function formatPct(value, decimals = 1) {
  if (value == null || isNaN(Number(value))) return FALLBACK
  return `${Number(value).toFixed(decimals)}%`
}

/**
 * Multiplier format: 3.66x | —
 * Used for ratios like current_ratio.
 */
export function formatMultiple(value, decimals = 2) {
  if (value == null || isNaN(Number(value))) return FALLBACK
  return `${Number(value).toFixed(decimals)}x`
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
