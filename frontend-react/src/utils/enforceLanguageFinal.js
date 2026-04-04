/**
 * Final guard for user-visible strings in Arabic UI: normalizes embedded K/M, %, and ratio "x"
 * that may leak from backends or concatenation. Does not machine-translate prose.
 */

import { formatCompactForLang, formatMultipleForLang } from './numberFormat.js'

const HAS_ARABIC = /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]/

function isArabicUi(lang) {
  return String(lang || '')
    .trim()
    .toLowerCase()
    .startsWith('ar')
}

/**
 * Normalize financial tokens inside free text for Arabic display.
 */
export function transformBackendProse(text, lang) {
  if (text == null) return ''
  let s = String(text)
  if (!isArabicUi(lang)) return s

  s = s.replace(/(-?)(\d+(?:\.\d+)?)\s*([KkMm])\b/g, (match, sign, numStr, unit) => {
    const n = Number(numStr)
    if (!Number.isFinite(n)) return match
    const mul = unit.toLowerCase() === 'm' ? 1e6 : 1e3
    const v = n * mul * (sign === '-' ? -1 : 1)
    return formatCompactForLang(v, lang)
  })

  s = s.replace(/(\d+(?:\.\d+)?)x\b/gi, (match, numStr) => {
    const n = Number(numStr)
    if (!Number.isFinite(n)) return match
    return formatMultipleForLang(n, 2, lang)
  })

  s = s.replace(/(\d+(?:\.\d+)?)%/g, '$1٪')

  return s
}

function isMostlyLatinSentence(s) {
  const t = String(s).trim()
  if (t.length < 10) return false
  if (HAS_ARABIC.test(t)) return false
  const letters = t.replace(/[^A-Za-z]/g, '')
  return letters.length >= 8 && letters.length >= t.length * 0.25
}

/**
 * Apply before rendering server-built or concatenated copy when `lang` is Arabic.
 */
export function enforceLanguageFinal(text, lang) {
  if (text == null) return text
  if (typeof text !== 'string') return text
  if (!isArabicUi(lang)) return text
  let s = transformBackendProse(text, lang)
  if (isMostlyLatinSentence(s)) {
    s = transformBackendProse(s, lang)
  }
  return s
}
