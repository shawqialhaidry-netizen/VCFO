/**
 * Client i18n base layer: full locale maps from the same JSON the API serves
 * (`app/i18n/*.json`). Merged with live `/api/v1/language/translations/{lang}` so
 * strictT never sees an empty map on first paint and you do not duplicate strings here.
 */
import bundledEn from '../../../app/i18n/en.json'
import bundledAr from '../../../app/i18n/ar.json'
import bundledTr from '../../../app/i18n/tr.json'

export const BUNDLED_LOCALES = {
  en: bundledEn,
  ar: bundledAr,
  tr: bundledTr,
}

function pickBundled(lang) {
  if (lang === 'ar') return bundledAr
  if (lang === 'tr') return bundledTr
  return bundledEn
}

function looksLikeMojibake(v) {
  if (typeof v !== 'string') return false
  return /(?:Ã.|Å.|Ø.|Ù.|â.)/.test(v)
}

/**
 * Start from bundled JSON (complete keys), then overlay API map.
 * Skip API entries that echo the key, are empty, or look mojibake-like so
 * a broken API payload cannot clobber clean bundled locale text.
 */
export function mergeCritical(lang, fetched) {
  const fromDisk = { ...pickBundled(lang) }
  const raw = fetched && typeof fetched === 'object' && !Array.isArray(fetched) ? fetched : {}
  for (const [k, v] of Object.entries(raw)) {
    if (v == null || v === '') continue
    if (typeof v === 'string' && v.trim() === k) continue
    if (looksLikeMojibake(v)) continue
    fromDisk[k] = v
  }
  return fromDisk
}

/**
 * Synchronous read from bundled locale JSON only (same locale as `lang`).
 * Never falls back to English for ar/tr - avoids mixed-language UI.
 */
export function fallbackLabel(lang, key) {
  if (!key) return null
  const primary = pickBundled(lang)
  const v = primary[key]
  if (v == null || v === '') return null
  if (typeof v === 'string' && v.trim() === key) return null
  return v
}
