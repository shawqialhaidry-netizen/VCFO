/**
 * Split primary decision change line into:
 * - headline: meaning-first, ideally no embedded stats (heuristic)
 * - metrics: lines/clauses with %, colon+value, or signed numerics
 *
 * Backend often joins narrative + KPI fragments with Arabic comma (،) or newlines.
 */

const PERCENTISH = /%|٪|\u066A|بالمائة|percent\b/i

const LONG_CLAUSE = 88

/**
 * @param {string} segment — single clause / line
 * @returns {boolean}
 */
export function isPrimaryDecisionMetricSegment(segment) {
  const s = String(segment || '').trim()
  if (!s) return false
  if (PERCENTISH.test(s)) return true
  if (/:\s*[\+\-−±]?\s*[\d\u0660-\u0669]/.test(s)) return true
  if (/[\+\-−±]\s*[\d\u0660-\u0669]+(?:[.,٫][\d\u0660-\u0669]+)?/.test(s)) return true
  if (s.length < 96 && /[\d\u0660-\u0669]+(?:[.,٫][\d\u0660-\u0669]+)/.test(s)) return true
  /* Long narrative may include a year; keep as headline unless it is clearly a stat row */
  if (s.length >= LONG_CLAUSE && !PERCENTISH.test(s) && !/[\+\-−±]\s*[\d\u0660-\u0669]+/.test(s)) {
    return false
  }
  if (/\d|[\u0660-\u0669]/.test(s)) return true
  return false
}

/**
 * Break one line into clauses (Arabic ، / ؛ first, then conservative Latin comma before signed numbers).
 * @param {string} line
 * @returns {string[]}
 */
function splitLineIntoSegments(line) {
  const t = String(line || '').trim()
  if (!t) return []

  let parts = t.split(/\s*[؛]\s+/).map((p) => p.trim()).filter(Boolean)
  if (parts.length <= 1) {
    parts = t.split(/\s*،\s+/).map((p) => p.trim()).filter(Boolean)
  }
  if (parts.length <= 1) {
    parts = t.split(/,(?=\s*[\+\-−]?\s*\d)/).map((p) => p.trim()).filter(Boolean)
  }
  if (parts.length <= 1) {
    parts = t.split(/(?<=[.!?؟۔])\s+/).map((p) => p.trim()).filter(Boolean)
  }
  if (parts.length <= 1) {
    parts = t.split(/\n+/).map((p) => p.trim()).filter(Boolean)
  }
  return parts.length ? parts : [t]
}

/**
 * Remove common stat tokens from prose when every clause was classified as metric
 * but the payload is one blob (last resort for a short headline).
 * @param {string} s
 */
function stripKnownMetricPatterns(s) {
  let t = String(s || '')
  t = t.replace(/[\(\[]\s*[\+\-−±]?\s*[\d\u0660-\u0669]+(?:[.,٫][\d\u0660-\u0669]+)?\s*(?:%|٪|\u066A)?\s*[\)\]]/g, ' ')
  t = t.replace(/[\+\-−±]?\s*[\d\u0660-\u0669]+(?:[.,٫][\d\u0660-\u0669]+)?\s*(?:%|٪|\u066A)/g, ' ')
  t = t.replace(/:\s*[\+\-−±]?\s*[\d\u0660-\u0669]+(?:[.,٫][\d\u0660-\u0669]+)?(?:\s*(?:%|٪|\u066A))?/g, ': ')
  t = t.replace(/\s*[؛،]\s*$/g, '')
  return t.replace(/\s+/g, ' ').trim()
}

/**
 * @param {string} raw — change_text or action_text
 * @returns {{ headline: string, metrics: string[] }}
 */
export function splitPrimaryDecisionHeadlineAndMetrics(raw) {
  const text = String(raw || '').trim()
  if (!text) return { headline: '', metrics: [] }

  const lines = text.split(/\n+/).map((l) => l.trim()).filter(Boolean)
  const headlineBits = []
  const metrics = []

  for (const line of lines) {
    for (const seg of splitLineIntoSegments(line)) {
      if (!seg) continue
      if (isPrimaryDecisionMetricSegment(seg)) {
        metrics.push(seg.replace(/\s+/g, ' ').trim())
      } else {
        headlineBits.push(seg.replace(/\s+/g, ' ').trim())
      }
    }
  }

  let headline = headlineBits.join(' ').replace(/\s+/g, ' ').trim()

  if (!headline && metrics.length) {
    headline = stripKnownMetricPatterns(text)
  }

  if (!headline && text) {
    const fallback = stripKnownMetricPatterns(text)
    if (fallback && !isPrimaryDecisionMetricSegment(fallback)) headline = fallback
  }

  if (!headline) {
    headline = text.split(/\n/)[0] || text
  }

  const seen = new Set()
  const deduped = []
  for (const m of metrics) {
    if (!m || seen.has(m)) continue
    seen.add(m)
    deduped.push(m)
  }

  return { headline, metrics: deduped }
}
