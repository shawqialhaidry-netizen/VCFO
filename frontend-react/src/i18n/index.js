// Simple i18n — fetches translations from backend and caches them
const _cache = {}

export async function loadTranslations(lang) {
  if (_cache[lang]) return _cache[lang]
  try {
    const res = await fetch(`/api/v1/language/translations/${lang}`)
    const data = await res.json()
    _cache[lang] = data.translations
    return _cache[lang]
  } catch {
    return {}
  }
}

export function t(translations, key) {
  return translations?.[key] ?? key
}

export const LANGUAGES = [
  { code: 'en', label: 'EN', name: 'English', dir: 'ltr' },
  { code: 'ar', label: 'AR', name: 'العربية', dir: 'rtl' },
  { code: 'tr', label: 'TR', name: 'Türkçe', dir: 'ltr' },
]
