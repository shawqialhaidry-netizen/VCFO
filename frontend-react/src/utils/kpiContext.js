/**
 * kpiContext.js — KPI Period Context Utility (Fully Localized)
 *
 * All user-visible text comes from tr() i18n keys.
 * Month/date formatting uses Intl.DateTimeFormat (browser-native, locale-aware).
 * Zero hardcoded display strings.
 *
 * Required i18n keys:
 *   context_this_month, context_last_3_months, context_last_6_months,
 *   context_last_12_months, context_all_time, context_ytd, context_fy,
 *   context_custom_range, kpi_with_context
 */

const LOCALE_MAP = { en: 'en-US', ar: 'ar', tr: 'tr-TR' }

function formatPeriod(period, lang) {
  if (!period || !period.includes('-')) return period || ''
  try {
    const [year, month] = period.split('-').map(Number)
    const date   = new Date(year, month - 1, 1)
    const locale = LOCALE_MAP[lang] || 'en-US'
    return new Intl.DateTimeFormat(locale, { month: 'short', year: 'numeric' }).format(date)
  } catch { return period }
}

function fillTpl(tpl, values) {
  if (!tpl) return ''
  return tpl.replace(/\{(\w+)\}/g, (_, k) => (values[k] !== undefined ? values[k] : k))
}

export function kpiContextLabel({ window = 'ALL', ps = {}, latestPeriod = '', lang = 'en', tr } = {}) {
  try {
    const t  = tr || ((k) => k)
    const bt = (ps.basis_type || 'all').toLowerCase()

    if (bt === 'period' || bt === 'month')
      return formatPeriod(ps.period || latestPeriod, lang)

    if (bt === 'ytd') {
      const year = ps.year || (latestPeriod ? latestPeriod.slice(0, 4) : '')
      return t('context_ytd', { year })
    }

    if (bt === 'year') {
      const year = ps.year || (latestPeriod ? latestPeriod.slice(0, 4) : '')
      return t('context_fy', { year })
    }

    if (bt === 'custom') {
      const from = ps.from_period ? formatPeriod(ps.from_period, lang) : ''
      const to   = ps.to_period   ? formatPeriod(ps.to_period,   lang) : ''
      if (from && to) return `${from} \u2013 ${to}`
      return t('context_custom_range')
    }

    const w = (window || 'ALL').toUpperCase()
    if (w === '3M')  return t('context_last_3_months')
    if (w === '6M')  return t('context_last_6_months')
    if (w === '12M') return t('context_last_12_months')

    if (w === 'YTD') {
      const year = latestPeriod ? latestPeriod.slice(0, 4) : ''
      return t('context_ytd', { year })
    }

    if (w === 'ALL') {
      if (latestPeriod) return formatPeriod(latestPeriod, lang)
      return t('context_all_time')
    }

    return ''
  } catch { return '' }
}

export function kpiLabel(label, ctx, tr) {
  if (!ctx) return label
  if (!tr) return `${label} (${ctx})`
  return tr('kpi_with_context', { label, context: ctx })
}
