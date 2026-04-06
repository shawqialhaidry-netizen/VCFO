/**
 * OnboardingHint.jsx — Phase 6.9
 * Persistent but dismissible tooltip strip shown once per session.
 * Guides first-time expert reviewers through the platform.
 * No backend, no state persistence beyond sessionStorage.
 */
import { useState, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { useLang } from '../context/LangContext.jsx'
import { normalizeUiLang } from '../utils/strictI18n.js'

const HINT_KEY_BY_PATH = {
  '/': 'hint_command_center',
  '/statements': 'hint_statements',
  '/analysis': 'hint_analysis',
  '/upload': 'hint_upload',
  '/cfo-ai': 'hint_cfo_ai',
  '/ai-advisor': 'hint_cfo_ai',
}

const SESSION_KEY = 'vcfo_hints_dismissed'

export default function OnboardingHint() {
  const { lang, tr } = useLang()
  const loc = useLocation()
  const uiLang = normalizeUiLang(lang)
  const rtl = uiLang === 'ar'

  const [dismissed, setDismissed] = useState(() => {
    try {
      return JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'false')
    } catch {
      return false
    }
  })
  const [visible, setVisible] = useState(false)

  const hintKey = HINT_KEY_BY_PATH[loc.pathname]

  useEffect(() => {
    if (hintKey && !dismissed) {
      setVisible(true)
    } else {
      setVisible(false)
    }
  }, [loc.pathname, dismissed, hintKey])

  function dismiss() {
    setDismissed(true)
    sessionStorage.setItem(SESSION_KEY, 'true')
    setVisible(false)
  }

  if (!visible || !hintKey) return null

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 20,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 300,
        maxWidth: 680,
        width: 'calc(100vw - 40px)',
        background: 'rgba(13,24,41,0.97)',
        borderWidth: '1px',
        borderStyle: 'solid',
        borderColor: 'rgba(0,212,170,0.3)',
        borderRadius: 12,
        padding: '11px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        boxShadow: '0 8px 32px rgba(0,0,0,0.6), 0 0 0 1px rgba(0,212,170,0.1)',
        animation: 'slideUp .3s ease',
        direction: rtl ? 'rtl' : 'ltr',
      }}
    >
      <style>{`@keyframes slideUp{from{opacity:0;transform:translateX(-50%) translateY(12px)}to{opacity:1;transform:translateX(-50%) translateY(0)}}`}</style>
      <span style={{ fontSize: 11, color: '#aab4c3', flex: 1, lineHeight: 1.5 }}>{tr(hintKey)}</span>
      <button
        type="button"
        onClick={dismiss}
        style={{
          fontSize: 10,
          color: '#6b7280',
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          whiteSpace: 'nowrap',
          flexShrink: 0,
          padding: '3px 8px',
          borderRadius: 6,
          fontFamily: 'inherit',
        }}
      >
        {tr('hint_dismiss')} ×
      </button>
    </div>
  )
}
