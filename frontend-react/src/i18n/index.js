// Simple i18n — fetches translations from backend and caches them
import { mergeCritical } from './criticalFallbacks.js'

const _cache = {}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

/**
 * Load locale map from API. Only successful responses are cached — a failed or
 * empty fetch must NOT poison _cache (otherwise strict i18n sees missing keys until hard reload).
 */
export async function loadTranslations(lang) {
  if (_cache[lang]) return _cache[lang]
  let lastErr
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const res = await fetch(`/api/v1/language/translations/${lang}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      const raw = data?.translations
      if (raw == null || typeof raw !== 'object' || Array.isArray(raw)) {
        throw new Error('Invalid translations payload')
      }
      const merged = mergeCritical(lang, raw)
      _cache[lang] = merged
      return merged
    } catch (e) {
      lastErr = e
      await sleep(250 * (attempt + 1))
    }
  }
  console.error('[i18n] loadTranslations failed after retries', { lang, error: lastErr })
  return mergeCritical(lang, {})
}

/** Clear fetch cache (e.g. after fixing a failed first load without full page reload). */
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
