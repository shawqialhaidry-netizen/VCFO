/**
 * Shared domain / risk scores for Command Center intelligence surfaces (domain grid + intel tiles).
 * Mirrors DomainGrid logic — single source for consistent numbers.
 */

export function scoreFromCategory(ratios, cat) {
  if (!cat) return 50
  const s2 = { good: 100, neutral: 60, warning: 35, risk: 10 }
  const category = ratios?.[cat]
  if (!category || typeof category !== 'object') return 50
  const vs = Object.values(category)
    .map((v) => s2[v?.status] || 50)
    .filter((v) => Number.isFinite(v))
  if (!vs.length) return 50
  return Math.round(vs.reduce((a, b) => a + b, 0) / vs.length)
}

export function riskScoreFromIntel(intel, alerts) {
  const ratios = intel?.ratios || {}
  const lev = scoreFromCategory(ratios, 'leverage')
  const hi = (alerts || []).filter((a) => a.severity === 'high').length
  const med = (alerts || []).filter((a) => a.severity === 'medium').length
  const penalty = Math.min(30, hi * 12 + med * 5)
  return Math.max(0, Math.min(100, Math.round(lev - penalty)))
}

export function domainStatusFromScore(s) {
  return s >= 70 ? 'good' : s >= 45 ? 'warning' : 'risk'
}
