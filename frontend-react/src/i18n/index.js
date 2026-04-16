// Simple i18n - uses bundled locale JSON only
import { BUNDLED_LOCALES } from './criticalFallbacks.js'

const _cache = {}

/**
 * Load locale map from bundled JSON only.
 */
export async function loadTranslations(lang) {
  if (_cache[lang]) return _cache[lang]
  const bundled = BUNDLED_LOCALES[lang] || BUNDLED_LOCALES.en || {}
  _cache[lang] = bundled
  return bundled
}

/** Clear in-memory locale cache. */
export function clearTranslationCache(lang = null) {
  if (lang) delete _cache[lang]
  else Object.keys(_cache).forEach((k) => delete _cache[k])
}

export function t(translations, key) {
  return translations?.[key] ?? key
}

export const LANGUAGES = [
  { code: 'en', label: 'EN', name: 'English', dir: 'ltr' },
  { code: 'ar', label: 'AR', name: 'العربية', dir: 'rtl' },
  { code: 'tr', label: 'TR', name: 'Türkçe', dir: 'ltr' },
]
