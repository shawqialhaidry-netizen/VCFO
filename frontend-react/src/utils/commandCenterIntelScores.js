/**
 * Presentation-only mapping from a 0–100 score to a status band.
 * Business scores come from GET /executive intelligence.surface_scores (server).
 */
export function domainStatusFromScore(s) {
  if (s == null || !Number.isFinite(Number(s))) return 'warning'
  const n = Number(s)
  if (n >= 70) return 'good'
  if (n >= 45) return 'warning'
  return 'risk'
}
