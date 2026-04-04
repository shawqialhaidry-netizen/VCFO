/**
 * Unified query string for analysis-family GETs and aligned company APIs.
 *
 * Phase 22 scope (basis_type, period, year, from_period, to_period) is merged
 * inside `toQueryString` from PeriodScopeContext (it reads the live ref).
 *
 * @param {function} toQueryString - from usePeriodScope().toQueryString
 * @param {object} options
 * @param {string} [options.lang='en']
 * @param {string} [options.window='ALL']
 * @param {boolean} [options.consolidate=false] - adds consolidate=true (executive / consolidated TB)
 * @param {string} [options.branch_id] - optional branch filter (endpoints that support it)
 * @returns {string|null} Query string without leading '?', or null if custom scope is incomplete
 */
export function buildAnalysisQuery(toQueryString, options = {}) {
  if (typeof toQueryString !== 'function') {
    throw new Error('buildAnalysisQuery: toQueryString is required')
  }
  const { lang = 'en', window = 'ALL', consolidate = false, branch_id: branchId } = options
  const qs = toQueryString({
    lang: lang || 'en',
    window: window || 'ALL',
  })
  if (qs === null) return null
  let out = qs
  if (consolidate) {
    out += (out ? '&' : '') + 'consolidate=true'
  }
  const bid = branchId != null && String(branchId).trim() !== '' ? String(branchId).trim() : ''
  if (bid) {
    out += (out ? '&' : '') + 'branch_id=' + encodeURIComponent(bid)
  }
  return out
}
