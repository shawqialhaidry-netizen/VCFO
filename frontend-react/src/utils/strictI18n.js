/**
 * Strict i18n: missing/invalid keys → console.error + locale-neutral placeholder (U+2026).
 * LangContext `tr` uses the same rules (no raw keys, no EN→AR/TR leakage via fallbackLabel).
 */
export const STRICT_I18N_PLACEHOLDER = '\u2026'

export function looksLikeRawI18nKey(v) {
  if (typeof v !== 'string') return false
  const t = v.trim()
  return /^(exec_|cmd_|nav_|dq_|kpi_label_|kpi_explain_|tab_|ratio_|domain_signal_)[a-z0-9_]+$/i.test(t)
}

/**
 * @param {(key: string) => string} tr
 * @param {string} lang
 * @param {string} key
 */
export function strictT(tr, lang, key) {
  let v
  try {
    v = tr(key)
  } catch (e) {
    console.error('[i18n] tr() threw', { lang, key, error: e })
    return STRICT_I18N_PLACEHOLDER
  }
  if (v == null || v === '' || v === key || looksLikeRawI18nKey(v)) {
    console.error('[i18n] missing or invalid translation', { lang, key, resolved: v })
    return STRICT_I18N_PLACEHOLDER
  }
  return v
}

/**
 * Template with {name} placeholders — each segment strict; missing sub-key → placeholder for that segment only.
 */
export function strictTParams(tr, lang, key, params) {
  const base = strictT(tr, lang, key)
  if (base === STRICT_I18N_PLACEHOLDER) return base
  let s = base
  for (const [k, val] of Object.entries(params || {})) {
    s = s.replaceAll(`{${k}}`, val != null ? String(val) : STRICT_I18N_PLACEHOLDER)
  }
  return s
}
