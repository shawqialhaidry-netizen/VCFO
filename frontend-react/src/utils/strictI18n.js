/**
 * Strict i18n: missing/invalid keys → console.error + locale-safe placeholder (bundled `i18n_missing_label`).
 * LangContext `tr` uses the same rules (no raw keys, no EN→AR/TR leakage via fallbackLabel).
 */
import { fallbackLabel } from '../i18n/criticalFallbacks.js'

export const STRICT_I18N_PLACEHOLDER = '\u2026'

/** Single source of truth for UI language codes (Command Center, narrative, drills). */
export function normalizeUiLang(lang) {
  const l = String(lang ?? '')
    .trim()
    .toLowerCase()
  if (l === 'ar') return 'ar'
  if (l === 'tr') return 'tr'
  return 'en'
}

/**
 * Bound translator for narrative builders: supports `t(key)` and `t(key, params)`.
 * Keeps one resolution path with strictT / strictTParams (no English leakage in ar/tr).
 */
export function makeStrictTr(tr, lang) {
  return (key, params) => {
    if (params != null && typeof params === 'object') return strictTParams(tr, lang, key, params)
    return strictT(tr, lang, key)
  }
}

/** Visible fallback when a key is missing — Arabic/Turkish get non-English copy from locale JSON. */
export function localizedMissingPlaceholder(lang) {
  const code = String(lang || 'en').toLowerCase()
  const loc = code === 'ar' ? 'ar' : code === 'tr' ? 'tr' : 'en'
  const v = fallbackLabel(loc, 'i18n_missing_label')
  if (v) return v
  return loc === 'ar' ? '[؟]' : loc === 'tr' ? '[?]' : '[?]'
}

export function looksLikeRawI18nKey(v) {
  if (typeof v !== 'string') return false
  const t = v.trim()
  return /^(exec_|cmd_|nav_|dq_|kpi_label_|kpi_explain_|tab_|ratio_|domain_signal_|narr_|drill_intel_|drill_sig_|ai_cfo_|loc_)[a-z0-9_]+$/i.test(t)
}

function invalidTranslation(key, val) {
  return (
    val == null ||
    val === '' ||
    val === key ||
    (typeof val === 'string' && looksLikeRawI18nKey(val))
  )
}

/**
 * Resolve a key from the live map + bundled fallback — same rules as strictT (no raw keys, locale-safe miss).
 * Used by LangContext `tr` so every consumer gets strict i18n without per-call strictT().
 */
export function readTranslation(translations, lang, key) {
  if (!key) return localizedMissingPlaceholder(lang)
  let s = translations && typeof translations === 'object' ? translations[key] : undefined
  if (invalidTranslation(key, s)) s = fallbackLabel(lang, key)
  if (invalidTranslation(key, s)) {
    console.error('[i18n] unresolved or invalid translation', { lang, key })
    return localizedMissingPlaceholder(lang)
  }
  return s
}

/** After param substitution, remove any leftover `{token}` so raw placeholders never reach UI. */
export function stripUnresolvedI18nPlaceholders(s) {
  if (typeof s !== 'string') return s
  return s.replace(/\{[a-zA-Z_][a-zA-Z0-9_.]*\}/g, '—')
}

export function applyTranslationParams(s, lang, params) {
  if (!params || typeof params !== 'object') return stripUnresolvedI18nPlaceholders(s)
  const miss = localizedMissingPlaceholder(lang)
  let out = s
  for (const [k, v] of Object.entries(params)) {
    out = out.replaceAll(`{${k}}`, v != null ? String(v) : miss)
  }
  return stripUnresolvedI18nPlaceholders(out)
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
    return localizedMissingPlaceholder(lang)
  }
  if (v == null || v === '' || v === key || looksLikeRawI18nKey(v)) {
    console.error('[i18n] missing or invalid translation', { lang, key, resolved: v })
    return localizedMissingPlaceholder(lang)
  }
  return v
}

/**
 * Template with {name} placeholders — each segment strict; missing sub-key → placeholder for that segment only.
 */
export function strictTParams(tr, lang, key, params) {
  const missing = localizedMissingPlaceholder(lang)
  const base = strictT(tr, lang, key)
  if (base === missing) return base
  let s = base
  for (const [k, val] of Object.entries(params || {})) {
    s = s.replaceAll(`{${k}}`, val != null ? String(val) : missing)
  }
  return stripUnresolvedI18nPlaceholders(s)
}
