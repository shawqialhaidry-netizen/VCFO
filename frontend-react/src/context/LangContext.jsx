/**
 * LangContext — fixed language persistence
 *
 * Storage:
 *   localStorage key: 'vcfo_lang'
 *   Read:  useState initializer (runs once before first render)
 *   Write: inside setLang wrapper (runs synchronously before effect)
 *
 * RTL:
 *   Applied to <html dir="..."> synchronously inside the setLang wrapper
 *   AND on mount (in case the stored language is 'ar')
 *   so the document direction is correct before any paint.
 */
import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { loadTranslations, LANGUAGES } from '../i18n/index.js'
import { readTranslation, applyTranslationParams, normalizeUiLang } from '../utils/strictI18n.js'

const STORAGE_KEY = 'vcfo_lang'
const DEFAULT_LANG = 'en'

/** Apply dir + lang attributes to <html> immediately (sync) */
function applyDocumentLang(code) {
  const entry = LANGUAGES.find(l => l.code === code)
  const dir   = entry?.dir || 'ltr'
  document.documentElement.setAttribute('dir',  dir)
  document.documentElement.setAttribute('lang', code)
}

/** Read stored language, validate, fall back to default */
function readStoredLang() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored && LANGUAGES.some(l => l.code === stored)) return normalizeUiLang(stored)
  } catch { /* localStorage blocked in some contexts */ }
  return DEFAULT_LANG
}

const LangContext = createContext(null)

export function LangProvider({ children }) {
  // ── 1. Initialise from localStorage before first render ──────────────────
  const [lang, _setLang]         = useState(readStoredLang)
  const [translations, setTrans] = useState({})
  const [ready, setReady]        = useState(false)

  // ── 2. Apply document direction on mount (for stored Arabic) ─────────────
  useEffect(() => { applyDocumentLang(lang) }, [])   // runs once on mount

  // ── 3. Load translations whenever lang changes ────────────────────────────
  useEffect(() => {
    let cancelled = false
    setReady(false)
    loadTranslations(lang).then(tr => {
      if (cancelled) return
      setTrans(tr)
      setReady(true)
    })
    return () => { cancelled = true }
  }, [lang])

  // ── 4. Public setter: persist + apply direction synchronously ─────────────
  const setLang = useCallback((code) => {
    const normalized = normalizeUiLang(code)
    if (!LANGUAGES.some(l => l.code === normalized)) return
    try { localStorage.setItem(STORAGE_KEY, normalized) } catch { }
    applyDocumentLang(normalized)   // sync — before React re-render
    _setLang(normalized)
  }, [])

  // ── 5. Translation helper — same resolution as strictT(readTranslation); no EN→ar/tr leakage ─
  const tr = useCallback(
    (key, params = null) => {
      const s = readTranslation(translations, lang, key)
      return applyTranslationParams(s, lang, params)
    },
    [translations, lang]
  )

  return (
    <LangContext.Provider value={{ lang, setLang, tr, ready, translations }}>
      {children}
    </LangContext.Provider>
  )
}

export function useLang() {
  return useContext(LangContext)
}
