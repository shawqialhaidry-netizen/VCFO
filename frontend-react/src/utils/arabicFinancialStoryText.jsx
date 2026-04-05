import { normalizeUiLang } from './strictI18n.js'

/**
 * Digit runs, bidi-isolated amounts (LRI…PDI), and common % / pp tokens in Arabic financial copy.
 */
const METRIC_RE =
  /(\u2066[\s\S]*?\u2069)|(\d+(?:[.,]\d+)?(?:\s*(?:%|٪|pp|PP))?)|([+\-−]\s*\d+(?:[.,]\d+)?(?:\s*(?:%|٪|pp|PP))?)/g

/**
 * Wraps metric-like spans for CSS emphasis (weight / mono / contrast).
 * @param {string} text
 * @returns {import('react').ReactNode}
 */
export function renderArabicFinancialInline(text) {
  if (typeof text !== 'string' || !text.length) return text
  const parts = []
  let last = 0
  let i = 0
  METRIC_RE.lastIndex = 0
  let m
  while ((m = METRIC_RE.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index))
    parts.push(
      <span key={`afm-${m.index}-${i++}`} className="ar-fin-story-metric">
        {m[0]}
      </span>
    )
    last = METRIC_RE.lastIndex
  }
  if (last < text.length) parts.push(text.slice(last))
  return parts.length ? parts : text
}

/** @param {string} text @param {string} lang */
export function storyParagraphContent(text, lang) {
  if (normalizeUiLang(lang) !== 'ar') return text
  return renderArabicFinancialInline(text)
}
