/**
 * Canonical CFO decision causal shape (build_cfo_decisions + causal_realized).
 * Same id / same triple must render identically across surfaces.
 */

export function causalTriple(cr) {
  if (!cr || typeof cr !== 'object') {
    return { change: '', cause: '', action: '' }
  }
  return {
    change: String(cr.change_text || '').trim(),
    cause: String(cr.cause_text || '').trim(),
    action: String(cr.action_text || '').trim(),
  }
}

export function hasAnyCausal(cr) {
  const t = causalTriple(cr)
  return !!(t.change || t.cause || t.action)
}

/** Stable React key + cross-surface identity: prefer realized causal id, else domain/priority/key. */
export function decisionStableKey(dec) {
  if (!dec || typeof dec !== 'object') return ''
  const cid = dec.causal_realized?.id
  if (cid != null && String(cid).length) return `cr:${cid}`
  return ['dec', dec.domain, dec.priority, dec.key].filter((x) => x != null && x !== '').join(':') || 'dec'
}
