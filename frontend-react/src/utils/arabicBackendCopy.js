/**
 * Arabic UI: suppress raw Latin backend prose in favor of i18n-driven copy (presentation only).
 */

const HAS_ARABIC = /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/

export function isArabicUiLang(lang) {
  return String(lang || '')
    .trim()
    .toLowerCase()
    .startsWith('ar')
}

/**
 * True when the string is Latin-only prose (no Arabic script) with enough letters to be a sentence/fragment.
 * Short codes (e.g. tickers) stay visible.
 */
export function shouldSuppressLatinProseForArabic(text) {
  const t = String(text || '').trim()
  if (t.length < 10) return false
  if (HAS_ARABIC.test(t)) return false
  const latinLetters = (t.match(/[A-Za-z]/g) || []).length
  return latinLetters >= 8
}
