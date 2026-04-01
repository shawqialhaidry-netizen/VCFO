/**
 * PeriodScopeContext.jsx — Phase 22 (Hotfix: loop-free)
 *
 * Root causes fixed:
 * 1. toQueryString/toBodyFields used `scope` object in deps → recreated on
 *    every render → load() deps changed → infinite fetch loop.
 *    Fix: use useRef to hold scope values; callbacks read ref, never depend on scope.
 * 2. setResolved wrote back to scope → triggered localStorage effect →
 *    triggered callback recreation → triggered load().
 *    Fix: resolved label/months live in a SEPARATE ref, never in scope state.
 * 3. localStorage write on every render.
 *    Fix: only write when primitive params actually change (deep-equal guard).
 */
import {
  createContext, useContext, useState, useCallback,
  useEffect, useRef,
} from 'react'

const PeriodScopeContext = createContext(null)
const LS_KEY = 'vcfo_period_scope'
const WIN_KEY = 'vcfo_window'

const DEFAULT_PARAMS = {
  basis_type:  'all',
  period:      '',
  year:        '',
  from_period: '',
  to_period:   '',
}

function readLS() {
  try {
    const raw = localStorage.getItem(LS_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    // Validate — only trusted primitive keys
    const ok = ['all','month','year','ytd','custom'].includes(parsed.basis_type)
    return ok ? { ...DEFAULT_PARAMS, ...parsed } : null
  } catch { return null }
}

function primitivesEqual(a, b) {
  return a.basis_type  === b.basis_type  &&
         a.period      === b.period      &&
         a.year        === b.year        &&
         a.from_period === b.from_period &&
         a.to_period   === b.to_period
}

/** Returns true if the current custom scope is incomplete (both fields required) */
function isIncompleteCustom(params) {
  return params.basis_type === 'custom' &&
         (!params.from_period || !params.to_period)
}

export function PeriodScopeProvider({ children }) {
  // scope holds ONLY the 5 primitive input params
  const [params, setParams] = useState(() => readLS() || DEFAULT_PARAMS)

  // Shared window - single source of truth for active analysis window
  const [window, setWindowState] = useState(() => {
    try { return localStorage.getItem(WIN_KEY) || 'ALL' } catch { return 'ALL' }
  })
  const setWindow = useCallback((w) => {
    setWindowState(w)
    try { localStorage.setItem(WIN_KEY, w) } catch {}
  }, [])

  // resolved label/months from server — stored in a ref, NOT in state
  // so writing them never triggers re-renders or effect chains
  const resolvedRef = useRef({ label: null, months: [] })

  // paramsRef: always current, lets callbacks read without deps
  const paramsRef = useRef(params)
  useEffect(() => { paramsRef.current = params }, [params])

  // Persist to localStorage — only when primitives actually change
  const prevPersistedRef = useRef(null)
  useEffect(() => {
    if (prevPersistedRef.current && primitivesEqual(prevPersistedRef.current, params)) return
    prevPersistedRef.current = params
    try {
      const { basis_type, period, year, from_period, to_period } = params
      localStorage.setItem(LS_KEY, JSON.stringify({ basis_type, period, year, from_period, to_period }))
    } catch { /* ignore */ }
  }, [params])

  /**
   * update(patch) — merge patch into params.
   * Guards against no-op updates to prevent downstream re-renders.
   */
  const update = useCallback((patch) => {
    setParams(prev => {
      const next = { ...prev, ...patch }
      return primitivesEqual(prev, next) ? prev : next
    })
  }, [])

  /**
   * toQueryString(extras) — reads paramsRef (stable ref, no deps).
   * Returns '' for incomplete custom scope so callers can guard.
   */
  const toQueryString = useCallback((extras = {}) => {
    const p = paramsRef.current
    // FIX: guard undefined window — URLSearchParams converts undefined to string "undefined"
    const safeExtras = Object.fromEntries(
      Object.entries(extras).filter(([, v]) => v !== undefined && v !== null)
    )
    const url = new URLSearchParams(safeExtras)
    if (p.basis_type && p.basis_type !== 'all') {
      if (isIncompleteCustom(p)) return null   // signal: do not fetch
      url.set('basis_type', p.basis_type)
      if (p.period)      url.set('period',      p.period)
      if (p.year)        url.set('year',        p.year)
      if (p.from_period) url.set('from_period', p.from_period)
      if (p.to_period)   url.set('to_period',   p.to_period)
    }
    return url.toString()
  }, [])   // ← stable: reads ref, no scope dep

  /**
   * toBodyFields() — reads paramsRef (stable ref, no deps).
   * Returns null for incomplete custom scope.
   */
  const toBodyFields = useCallback(() => {
    const p = paramsRef.current
    if (!p.basis_type || p.basis_type === 'all') return {}
    if (isIncompleteCustom(p)) return null  // signal: do not fetch
    return {
      scope_basis_type:  p.basis_type,
      scope_period:      p.period      || undefined,
      scope_year:        p.year        || undefined,
      scope_from_period: p.from_period || undefined,
      scope_to_period:   p.to_period   || undefined,
    }
  }, [])   // ← stable

  /**
   * setResolved — writes to ref only, never to state.
   * Zero re-renders, zero effect chain.
   */
  const setResolved = useCallback((serverScope) => {
    if (!serverScope) return
    resolvedRef.current = {
      label:  serverScope.label  || null,
      months: serverScope.months || [],
    }
  }, [])   // ← stable

  /** Read resolved label for display (call inside render, value is current) */
  const getActiveLabel = useCallback(() => resolvedRef.current.label, [])

  const reset = useCallback(() => {
    setParams(DEFAULT_PARAMS)
    resolvedRef.current = { label: null, months: [] }
    try { localStorage.removeItem(LS_KEY) } catch { /* ignore */ }
  }, [])

  return (
    <PeriodScopeContext.Provider value={{
      params,
      update,
      reset,
      toQueryString,
      toBodyFields,
      setResolved,
      getActiveLabel,
      isIncompleteCustom: () => isIncompleteCustom(paramsRef.current),
      window,
      setWindow,
    }}>
      {children}
    </PeriodScopeContext.Provider>
  )
}

export function usePeriodScope() {
  const ctx = useContext(PeriodScopeContext)
  if (!ctx) throw new Error('usePeriodScope must be used inside PeriodScopeProvider')
  return ctx
}
