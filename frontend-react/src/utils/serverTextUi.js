/**
 * Visual treatment for API/backend copy when UI is Arabic but payload is Latin-heavy.
 * Does not change strings — only styling hints for consistency.
 */

const LATIN_RUN = /[A-Za-z]{4,}/

export function shouldDimLatinInArabic(lang, text) {
  if (String(lang || '').toLowerCase() !== 'ar') return false
  if (typeof text !== 'string' || !text.trim()) return false
  return LATIN_RUN.test(text)
}

/** Inline styles merged onto server-driven text in Arabic UI when Latin is detected. */
export function dimLatinServerStyle(lang, text) {
  if (!shouldDimLatinInArabic(lang, text)) return null
  return {
    color: 'rgba(148, 163, 184, 0.95)',
    fontStyle: 'italic',
    opacity: 0.9,
  }
}

/** Fade tail instead of ellipsis character — use with maxHeight + overflow hidden. */
export const CLAMP_FADE_MASK = {
  overflow: 'hidden',
  maxHeight: '4.2em',
  lineHeight: 1.45,
  WebkitMaskImage: 'linear-gradient(to bottom, #000 72%, transparent 100%)',
  maskImage: 'linear-gradient(to bottom, #000 72%, transparent 100%)',
}

export const CLAMP_FADE_MASK_SHORT = {
  overflow: 'hidden',
  maxHeight: '3em',
  lineHeight: 1.5,
  WebkitMaskImage: 'linear-gradient(to bottom, #000 60%, transparent 100%)',
  maskImage: 'linear-gradient(to bottom, #000 60%, transparent 100%)',
}
