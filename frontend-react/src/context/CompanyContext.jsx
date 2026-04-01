/**
 * CompanyContext
 * - Fetches companies using the stored Bearer token
 * - Persists selected company to localStorage
 * - Provides analysis cache
 */
import { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react'

const API = '/api/v1'
const CompanyContext = createContext(null)

function getToken() {
  try {
    const raw = localStorage.getItem('vcfo_auth')
    return raw ? JSON.parse(raw)?.token : null
  } catch { return null }
}

function authHeaders() {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export function CompanyProvider({ children }) {
  const [companies, setCompanies]               = useState([])
  const [selectedId, setSelectedId]             = useState(
    () => localStorage.getItem('vcfo_company_id') || ''
  )
  const [loadingCompanies, setLoadingCompanies] = useState(true)
  const [memberships,    setMemberships]    = useState([])  // [{company_id, role, can_write, can_manage}]

  const analysisCache = useRef({})
  const CACHE_TTL_MS  = 5 * 60 * 1000

  const reloadMemberships = useCallback(() => {
    fetch(`${API}/auth/me/memberships`, { headers: authHeaders() })
      .then(r => r.ok ? r.json() : [])
      .then(list => setMemberships(Array.isArray(list) ? list : []))
      .catch(() => {})
  }, [])

  // Expose reload so Login can trigger a refresh after login
  const reloadCompanies = useCallback(() => {
    setLoadingCompanies(true)
    fetch(`${API}/companies`, { headers: authHeaders() })
      .then(r => r.json())
      .then(list => {
        if (!Array.isArray(list)) { setLoadingCompanies(false); return }
        setCompanies(list)
        setLoadingCompanies(false)

        if (list.length === 0) {
          // Clear stale company selection from previous sessions/users.
          localStorage.removeItem('vcfo_company_id')
          setSelectedId('')
          return
        }

        const exists = list.some(c => c.id === selectedId)
        if (!selectedId || !exists) setSelectedId(list[0].id)
      })
      .catch(() => setLoadingCompanies(false))
  }, [selectedId])

  // Load company list on mount
  useEffect(() => { reloadCompanies(); reloadMemberships() }, [reloadCompanies, reloadMemberships])

  useEffect(() => {
    if (selectedId) localStorage.setItem('vcfo_company_id', selectedId)
  }, [selectedId])

  const selectedCompany = companies.find(c => c.id === selectedId) || null

  function getCachedAnalysis(id) {
    const e = analysisCache.current[id]
    if (!e) return null
    if (Date.now() - e.timestamp > CACHE_TTL_MS) { delete analysisCache.current[id]; return null }
    return e.data
  }
  function setCachedAnalysis(id, data) {
    analysisCache.current[id] = { data, timestamp: Date.now() }
  }
  function invalidateCache(id) {
    if (id) delete analysisCache.current[id]; else analysisCache.current = {}
  }

  const fetchAnalysis = useCallback(async (companyId, opts = {}) => {
    const { force = false } = opts
    if (!force) {
      const cached = getCachedAnalysis(companyId)
      if (cached) return { ok: true, data: cached, fromCache: true }
    }
    try {
      let lang = 'en'
      try { lang = localStorage.getItem('vcfo_lang') || 'en' } catch { }
      const res  = await fetch(`${API}/analysis/${companyId}?lang=${encodeURIComponent(lang)}`, { headers: authHeaders() })
      const json = await res.json()
      if (!res.ok) return { ok: false, error: json.detail || 'Analysis failed' }
      setCachedAnalysis(companyId, json)
      return { ok: true, data: json, fromCache: false }
    } catch (e) {
      return { ok: false, error: e.message }
    }
  }, [])

  const createCompany = useCallback(async (payload) => {
    const body = {
      name:     String(payload?.name || '').trim(),
      name_ar:  payload?.name_ar ?? null,
      industry: payload?.industry ?? null,
      currency: payload?.currency || 'USD',
    }
    if (!body.name) return { ok: false, error: 'Company name is required.' }

    try {
      const r = await fetch(`${API}/companies`, {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const j = await r.json().catch(() => ({}))
      if (!r.ok) return { ok: false, error: j?.detail || `Error ${r.status}` }

      const newId = j?.id
      if (newId) {
        setSelectedId(newId)
        localStorage.setItem('vcfo_company_id', newId)
      }
      reloadCompanies()
      reloadMemberships()
      return { ok: true, company: j }
    } catch (e) {
      return { ok: false, error: e.message }
    }
  }, [reloadCompanies, reloadMemberships])

  // Derive current user's role for the selected company
  const currentMembership = memberships.find(m => m.company_id === selectedId) || null
  const userRole    = currentMembership?.role     || null   // 'owner'|'analyst'|'viewer'|null
  const canWrite    = currentMembership?.can_write    ?? true  // default true while loading
  const canManage   = currentMembership?.can_manage   ?? false
  const isOwner     = userRole === 'owner'
  const isAnalyst   = userRole === 'analyst'
  const isViewer    = userRole === 'viewer'

  // ── Trial / subscription state ─────────────────────────────────────────────
  // Subscription is COMPANY-LEVEL: all members of the same company share the same plan.
  // plan: 'trial' | 'active' | 'enterprise'  (never store 'expired' — derive from date)
  const plan           = selectedCompany?.plan          || 'trial'
  const trialEndsAt    = selectedCompany?.trial_ends_at || null
  const trialDaysLeft  = selectedCompany?.trial_days_left ?? null   // computed by backend
  const isTrial        = plan === 'trial'
  const isSubscribed   = plan === 'active' || plan === 'enterprise'
  const isTrialExpired = isTrial && trialEndsAt !== null && (trialDaysLeft !== null && trialDaysLeft <= 0)

  return (
    <CompanyContext.Provider value={{
      companies, selectedId, setSelectedId, selectedCompany,
      loadingCompanies, fetchAnalysis, invalidateCache, reloadCompanies, createCompany,
      memberships, userRole, canWrite, canManage,
      isOwner, isAnalyst, isViewer, reloadMemberships,
      plan, trialDaysLeft, trialEndsAt, isTrial, isSubscribed, isTrialExpired,
    }}>
      {children}
    </CompanyContext.Provider>
  )
}

export function useCompany() { return useContext(CompanyContext) }
