/**
 * AuthContext.jsx — FIX-FE1
 *
 * Handles auth state + token expiry detection.
 * Structured for Vite Fast Refresh compatibility:
 *   - AuthProvider: exported named component (provides context)
 *   - useAuth: exported named hook (consumes context)
 *
 * Token expiry: when any API call returns 401, sessionExpired is set to true.
 * The app should render <SessionExpiredBanner /> to prompt re-login.
 */
import { createContext, useContext, useState, useCallback, useRef } from 'react'

const AuthContext = createContext(null)
const STORAGE_KEY = 'vcfo_auth'

function readStoredAuth() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function getStoredToken() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw)?.token || null : null
  } catch {
    return null
  }
}

// ─── Provider ────────────────────────────────────────────────────────────────

export function AuthProvider({ children }) {
  const [auth, setAuthState]           = useState(() => readStoredAuth())
  const [sessionExpired, setExpired]   = useState(false)
  const loggingOut                     = useRef(false)

  const setAuth = useCallback((data) => {
    if (data) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
    setAuthState(data)
  }, [])

  const logout = useCallback(() => {
    loggingOut.current = false
    setExpired(false)
    setAuth(null)
  }, [setAuth])

  // FIX-FE1: authFetch — wraps fetch(), auto-detects 401 and triggers logout
  const authFetch = useCallback(async (url, options = {}) => {
    const token = auth?.token || getStoredToken()
    const headers = new Headers(options.headers || {})
    if (token && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${token}`)
    }
    const res = await fetch(url, { ...options, headers })
    if (res.status === 401 && !loggingOut.current) {
      loggingOut.current = true
      setAuth(null)
      setExpired(true)
    }
    return res
  }, [auth, setAuth])

  return (
    <AuthContext.Provider
      value={{ auth, setAuth, logout, authFetch, sessionExpired, setExpired }}
    >
      {children}
    </AuthContext.Provider>
  )
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useAuth() {
  return useContext(AuthContext)
}
