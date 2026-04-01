/**
 * OnboardingHint.jsx — Phase 6.9
 * Persistent but dismissible tooltip strip shown once per session.
 * Guides first-time expert reviewers through the platform.
 * No backend, no state persistence beyond sessionStorage.
 */
import { useState, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { useLang } from '../context/LangContext.jsx'

const HINTS = {
  '/': {
    en: '📊 Dashboard — Start here. See KPIs, trends, and AI insights for every metric. Click any KPI card for a drill-down.',
    ar: '📊 لوحة التحكم — ابدأ هنا. اعرض المؤشرات والاتجاهات والرؤى الذكية. انقر على أي بطاقة للتفاصيل.',
  },
  '/statements': {
    en: '📋 Statements — Source of truth. Income Statement, Balance Sheet, and Cash Flow with prior-period comparison.',
    ar: '📋 القوائم المالية — المصدر الأساسي. قائمة الدخل والميزانية والتدفق النقدي مع مقارنة الفترات.',
  },
  '/analysis': {
    en: '🔬 Analysis — Drill into ratios, trends, and root causes by domain. Use tabs for Profitability, Liquidity, Efficiency.',
    ar: '🔬 التحليل — فصّل النسب والاتجاهات والأسباب الجذرية. استخدم التبويبات للربحية والسيولة والكفاءة.',
  },
  '/executive': {
    en: '🎯 Executive — CFO cockpit. Health score, top decisions, root causes, and domain performance grid.',
    ar: '🎯 التنفيذي — قمرة المدير المالي. الصحة المالية وأهم القرارات والأسباب الجذرية وشبكة الأداء.',
  },
  '/upload': {
    en: '📁 Upload — Load a trial balance CSV. Supports monthly (YYYY-MM) and annual (YYYY) periods. All analysis updates automatically.',
    ar: '📁 الرفع — ارفع ميزان مراجعة CSV. يدعم الفترات الشهرية والسنوية. يتحدث التحليل تلقائياً.',
  },
  '/cfo-ai': {
    en: '🧠 AI CFO — Chat with your financial data. Ask about profits, cash flow, risks, or what to do next.',
    ar: '🧠 المدير المالي الذكي — تحدث مع بياناتك. اسأل عن الأرباح والتدفق النقدي والمخاطر.',
  },
}

const SESSION_KEY = 'vcfo_hints_dismissed'

export default function OnboardingHint() {
  const { lang } = useLang()
  const loc = useLocation()
  const ar = lang === 'ar'

  const [dismissed, setDismissed] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'false') }
    catch { return false }
  })
  const [visible, setVisible] = useState(false)

  const hint = HINTS[loc.pathname]

  useEffect(() => {
    if (hint && !dismissed) {
      setVisible(true)
    } else {
      setVisible(false)
    }
  }, [loc.pathname, dismissed, hint])

  function dismiss() {
    setDismissed(true)
    sessionStorage.setItem(SESSION_KEY, 'true')
    setVisible(false)
  }

  if (!visible || !hint) return null

  return (
    <div style={{
      position: 'fixed', bottom: 20, left: '50%',
      transform: 'translateX(-50%)',
      zIndex: 300, maxWidth: 680, width: 'calc(100vw - 40px)',
      background: 'rgba(13,24,41,0.97)',
      borderWidth: '1px', borderStyle: 'solid', borderColor: 'rgba(0,212,170,0.3)',
      borderRadius: 12,
      padding: '11px 16px',
      display: 'flex', alignItems: 'center', gap: 12,
      boxShadow: '0 8px 32px rgba(0,0,0,0.6), 0 0 0 1px rgba(0,212,170,0.1)',
      
      animation: 'slideUp .3s ease',
      direction: ar ? 'rtl' : 'ltr',
    }}>
      <style>{`@keyframes slideUp{from{opacity:0;transform:translateX(-50%) translateY(12px)}to{opacity:1;transform:translateX(-50%) translateY(0)}}`}</style>
      <span style={{ fontSize: 11, color: '#aab4c3', flex: 1, lineHeight: 1.5 }}>
        {hint[ar ? 'ar' : 'en']}
      </span>
      <button
        onClick={dismiss}
        style={{ fontSize: 10, color: '#6b7280', background: 'transparent',
          border: 'none', cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
          padding: '3px 8px', borderRadius: 6,
          fontFamily: 'inherit' }}>
        {ar ? 'إغلاق ×' : 'Got it ×'}
      </button>
    </div>
  )
}
