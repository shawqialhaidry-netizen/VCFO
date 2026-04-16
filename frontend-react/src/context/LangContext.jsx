/**
 * LangContext - fixed language persistence
 *
 * Storage:
 *   localStorage key: 'vcfo_lang'
 *   Read: useState initializer (runs once before first render)
 *   Write: inside setLang wrapper (runs synchronously before effect)
 *
 * RTL:
 *   Applied to <html dir="..."> synchronously inside the setLang wrapper
 *   and on mount (in case the stored language is 'ar')
 *   so the document direction is correct before any paint.
 */
import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { loadTranslations, LANGUAGES } from '../i18n/index.js'
import { readTranslation, applyTranslationParams, normalizeUiLang } from '../utils/strictI18n.js'

const STORAGE_KEY = 'vcfo_lang'
const DEFAULT_LANG = 'en'

function applyDocumentLang(code) {
  const entry = LANGUAGES.find(l => l.code === code)
  const dir = entry?.dir || 'ltr'
  document.documentElement.setAttribute('dir', dir)
  document.documentElement.setAttribute('lang', code)
}

function readStoredLang() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored && LANGUAGES.some(l => l.code === stored)) return normalizeUiLang(stored)
  } catch {
    // localStorage blocked in some contexts
  }
  return DEFAULT_LANG
}

const LangContext = createContext(null)

export function LangProvider({ children }) {
  const [lang, _setLang] = useState(readStoredLang)
  const [translations, setTrans] = useState({})
  const [ready, setReady] = useState(false)

  useEffect(() => {
    applyDocumentLang(lang)
  }, [])

  useEffect(() => {
    let cancelled = false
    setReady(false)
    loadTranslations(lang).then(tr => {
      if (cancelled) return
      setTrans(tr)
      setReady(true)
    })
    return () => {
      cancelled = true
    }
  }, [lang])

  const setLang = useCallback((code) => {
    const normalized = normalizeUiLang(code)
    if (!LANGUAGES.some(l => l.code === normalized)) return
    try {
      localStorage.setItem(STORAGE_KEY, normalized)
    } catch {}
    applyDocumentLang(normalized)
    _setLang(normalized)
  }, [])

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
