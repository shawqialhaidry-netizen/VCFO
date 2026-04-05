/**
 * Presentation-only: split backend prose into short scannable lines for executive UI.
 * Does not alter payloads or business rules.
 */
export function toExecutiveBulletLines(text, max = 3) {
  const t = String(text || '').trim()
  if (!t) return []
  const lines = t.split(/\r?\n/).map((s) => s.trim()).filter(Boolean)
  if (lines.length > 1) return lines.slice(0, max)
  const bySentence = t.split(/(?<=[.!?؟])\s+/).map((s) => s.trim()).filter(Boolean)
  if (bySentence.length > 1) return bySentence.slice(0, max)
  if (t.length > 120) return [`${t.slice(0, 117)}…`]
  return [t]
}
