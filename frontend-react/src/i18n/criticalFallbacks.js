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

/**
 * Start from bundled JSON (complete keys), then overlay API map.
 * Skip API entries that echo the key or are empty — avoids clobbering good AR/EN/TR.
 */
export function mergeCritical(lang, fetched) {
  const fromDisk = { ...pickBundled(lang) }
  const raw = fetched && typeof fetched === 'object' && !Array.isArray(fetched) ? fetched : {}
  for (const [k, v] of Object.entries(raw)) {
    if (v == null || v === '') continue
    if (typeof v === 'string' && v.trim() === k) continue
    fromDisk[k] = v
  }
  return fromDisk
}

/** Resolve a label when the async map lookup runs before merge completed (edge case). */
export function fallbackLabel(lang, key) {
  if (!key) return null
  const primary = pickBundled(lang)
  return primary[key] ?? bundledEn[key] ?? null
}
