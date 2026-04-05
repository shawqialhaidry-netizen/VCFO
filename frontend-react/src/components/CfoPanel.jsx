/**
 * CfoPanel.jsx — Phase 6.5: AI CFO Interface
 *
 * A right-side slide-in panel that maps questions to existing backend data.
 * NO external AI. NO calculations. NO API changes.
 * Reads: d.decisions, d.root_causes, d.intelligence, d.forecast — all from GET /executive `data` (single source).
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { useLang }    from '../context/LangContext.jsx'
import { useCompany } from '../context/CompanyContext.jsx'
import { usePeriodScope } from '../context/PeriodScopeContext.jsx'
import { buildAnalysisQuery } from '../utils/buildAnalysisQuery.js'
import {
  formatCompactForLang,
  formatPctForLang,
  formatMultipleForLang,
  formatDays,
} from '../utils/numberFormat.js'

const API = '/api/v1'
function auth() {
  try { const t=JSON.parse(localStorage.getItem('vcfo_auth')||'{}').token; return t?{Authorization:`Bearer ${t}`}:{} }
  catch { return {} }
}

// ── Question → Domain mapping ─────────────────────────────────────────────────
// Maps keywords to backend domain keys. No calculation, pure lookup.
// isVague: short queries with no domain keywords — use conversation memory
function isVague(text, lang) {
  const t = text.trim().toLowerCase()
  // Short with no topic keyword
  if (t.split(/\s+/).length <= 4) {
    const ar = lang === 'ar'
    const hasTopicAR = /ربح|هامش|نقد|تدفق|تكلف|مصار|خطر|ديون|نمو|إيراد|سيول|رأس/.test(t)
    const hasTopicEN = /profit|margin|cash|cost|risk|debt|grow|revenue|liquid|capital|efficien/.test(t)
    if (ar && !hasTopicAR) return true
    if (!ar && !hasTopicEN) return true
  }
  return false
}

function detectDomain(text, lang, lastDomain) {
  const txt = text.toLowerCase()
  const ar = lang === 'ar'

  // Explicit vague patterns — always use memory if available
  const vagueAR = /^(ماذا|والآن|وبعدين|إذن|حسناً|وماذا|استمر|أكمل|ثم)[؟?.\s]*$/.test(txt.trim())
  const vagueEN = /^(and now|what next|ok|so|continue|go on|then|what else|more)[?.\s]*$/i.test(txt.trim())
  if ((vagueAR || vagueEN || isVague(text, lang)) && lastDomain && lastDomain !== 'all') {
    return lastDomain
  }

  // AR keywords
  if (ar) {
    if (/ربح|هامش|خسار/.test(txt))              return 'profitability'
    if (/نقد|تدفق|سيول/.test(txt))              return 'cashflow'
    if (/تكلف|مصار|نفق/.test(txt))             return 'efficiency'
    if (/خطر|ديون|رفع/.test(txt))              return 'leverage'
    if (/نمو|إيراد|مبيع/.test(txt))            return 'growth'
    if (/عمل|رأس.*مال|سيول/.test(txt))         return 'liquidity'
    if (/ماذا|التالي|أولوي|أهم/.test(txt))     return 'all'
  }
  // EN keywords
  if (/profit|margin|loss|earn/.test(txt))        return 'profitability'
  if (/cash|flow|liquid|burn/.test(txt))          return 'cashflow'
  if (/cost|expense|efficien|opex/.test(txt))     return 'efficiency'
  if (/risk|debt|leverage|borrow/.test(txt))      return 'leverage'
  if (/grow|revenue|sales|expand/.test(txt))      return 'growth'
  if (/capital|current|working/.test(txt))        return 'liquidity'
  if (/what|next|priority|should|do/.test(txt))  return 'all'
  return 'all'
}

// ── Response builder — reads from fetched data, no calculation ────────────────
function buildResponse(question, domain, d, fcData, lang, tr) {
  const decs      = d?.decisions    || []
  const causes    = d?.root_causes  || []
  const intel     = d?.intelligence || {}
  const ratios    = intel.ratios    || {}
  const trends    = intel.trends    || {}
  const alerts    = d?.alerts       || []
  const health    = d?.health_score_v2
  const stmtIns   = d?.statements?.insights || []

  // Helper: get decision for a domain
  const getDec  = dom => decs.find(x => x.domain === dom)
  // Helper: first sentence
  const first   = s => s ? s.split('. ')[0] : null
  // Helper: first action step (up to first \n or numbered step)
  const firstStep = s => {
    if (!s) return null
    const match = s.match(/^1\)?\s*(.+?)(?:\n|$)/m) || s.match(/^(.+?)(?:\n|$)/)
    return match ? match[1].trim().slice(0, 90) : s.slice(0, 90)
  }
  const crHead = (dec) => {
    const t = String(dec?.causal_realized?.change_text || dec?.causal_realized?.action_text || '').trim()
    return t ? first(t) : null
  }
  const crCause = (dec) => {
    const t = String(dec?.causal_realized?.cause_text || '').trim()
    return t ? first(t) : null
  }
  const crAction = (dec) => {
    const t = String(dec?.causal_realized?.action_text || '').trim()
    return t ? first(t) : null
  }

  // Build sections
  const sections = []

  if (domain === 'all') {
    // Overview: health + top 3 priorities
    const tier = health!=null ? (health>=80?'excellent':health>=60?'good':health>=40?'warning':'risk') : null
    sections.push({
      icon: '📊',
      label: tr('cfo_panel_current_status'),
      text: health != null
        ? `${tr('health_score')} ${health}/100 — ${tr(`health_tier_${tier}`)}`
        : tr('insufficient_data')
    })
    const topDecs = decs.slice(0, 3)
    if (topDecs.length) {
      sections.push({
        icon: '🎯',
        label: tr('cfo_panel_action_priorities'),
        items: topDecs.map((dec, i) => ({
          num: i + 1,
          title: crHead(dec) || '—',
          urgency: dec.urgency,
          step: crAction(dec) || crCause(dec)
        }))
      })
    }

  } else if (domain === 'profitability') {
    const dec = getDec('profitability')
    const nm  = ratios?.profitability?.net_margin_pct
    const gm  = ratios?.profitability?.gross_margin_pct
    sections.push({
      icon: '💰',
      label: tr('profitability'),
      text: nm?.value != null
        ? `${tr('net_margin')} ${formatPctForLang(nm.value, 1, lang)} — ${tr(`kpi_margin_status_${nm.status}`)}`
        : tr('margin_data_unavailable')
    })
    const cC = crCause(dec)
    const cA = crAction(dec)
    if (cC) sections.push({ icon: '🔍', label: tr('cause'), text: cC })
    if (cA) sections.push({ icon: '⚡', label: tr('action'), text: cA })

  } else if (domain === 'cashflow' || domain === 'liquidity') {
    const decLiq  = getDec('liquidity')
    const decEff  = getDec('efficiency')
    const cr      = ratios?.liquidity?.current_ratio
    const wc      = ratios?.liquidity?.working_capital
    const cfIns   = stmtIns.find(i => i.key === 'cashflow_positive')
    sections.push({
      icon: '💧',
      label: tr('liquidity'),
      text: cr?.value != null
        ? `${tr('current_ratio')} ${formatMultipleForLang(cr.value, 2, lang)} — ${tr(`ratio_status_${cr.status}`)}`
        : (cfIns ? first(cfIns.message) : tr('liquidity_data_unavailable'))
    })
    const liqC = crCause(decLiq)
    const liqA = crAction(decLiq)
    const effC = crCause(decEff)
    if (liqC) sections.push({ icon: '🔍', label: tr('cause'), text: liqC })
    if (effC && domain === 'cashflow') sections.push({ icon: '📋', label: tr('cashflow_operating'), text: effC })
    if (liqA) sections.push({ icon: '⚡', label: tr('action'), text: liqA })

  } else if (domain === 'efficiency') {
    const dec = getDec('efficiency')
    const eff = ratios?.efficiency || {}
    const dsoV = Object.entries(eff).find(([k]) => k.includes('dso'))?.[1]
    sections.push({
      icon: '⚙️',
      label: tr('efficiency'),
      text: dsoV?.value != null
        ? tr('dso_days_line', { days: formatDays(dsoV.value) })
        : tr('efficiency_data_unavailable')
    })
    const eC = crCause(dec)
    const eA = crAction(dec)
    if (eC) sections.push({ icon: '🔍', label: tr('cause'), text: eC })
    if (eA) sections.push({ icon: '⚡', label: tr('action'), text: eA })

  } else if (domain === 'leverage') {
    const dr    = ratios?.leverage?.debt_ratio_pct
    const topAl = alerts.find(a => a.severity === 'high') || alerts[0]
    sections.push({
      icon: '⚠️',
      label: tr('risks'),
      text: dr?.value != null
        ? `${tr('debt_ratio_pct')} ${formatPctForLang(dr.value, 1, lang)} — ${tr(`debt_status_${dr.status||'neutral'}`)}`
        : tr('risk_data_unavailable')
    })
    if (topAl) sections.push({ icon: '🚨', label: tr('alert'), text: topAl.message || topAl.title })
    const dec = getDec('leverage') || getDec('liquidity')
    const lvA = crAction(dec)
    if (lvA) sections.push({ icon: '⚡', label: tr('action'), text: lvA })

  } else if (domain === 'growth') {
    const dec   = getDec('growth')
    const revT  = trends?.revenue?.direction
    sections.push({
      icon: '📈',
      label: tr('growth'),
      text: revT
        ? `${tr('revenue_trend')}: ${revT==='up'?tr('trend_up'):revT==='down'?tr('trend_down'):tr('trend_stable')}`
        : tr('revenue_trend_unavailable')
    })
    const gC = crCause(dec)
    const gA = crAction(dec)
    if (gC) sections.push({ icon: '🔍', label: tr('cause'), text: gC })
    if (gA) sections.push({ icon: '⚡', label: tr('action'), text: gA })
  }

  // Forecast section — always appended if available
  if (fcData?.available && domain !== 'leverage') {
    const bRev = fcData?.scenarios?.base?.revenue?.[0]
    const bNp  = fcData?.scenarios?.base?.net_profit?.[0]
    const riskLevel = fcData?.summary?.risk_level
    const fcParts = []
    if (bRev?.point) fcParts.push(`${tr('revenue')} ${formatCompactForLang(bRev.point, lang)}`)
    if (bNp?.point)  fcParts.push(`${tr('net_profit')} ${formatCompactForLang(bNp.point, lang)}`)
    if (fcParts.length) {
      const conf = bRev?.confidence != null
        ? ` (${formatPctForLang(bRev.confidence, 0, lang)})`
        : ''
      const risk = riskLevel ? ` · ${tr('forecast_risk')}: ${riskLevel}` : ''
      sections.push({
        icon: '🔮',
        label: tr('forecast_next_period'),
        text: fcParts.join(' · ') + conf + risk,
        accent: true
      })
    }
  }

  return sections
}

// ── Quick action chips ────────────────────────────────────────────────────────
function getQuickActions(tr) {
  const items = [
    { label: tr('cfo_sugg_risk_3'), q: tr('cfo_sugg_risk_3') },
    { label: tr('cfo_sugg_prof_1'), q: tr('cfo_sugg_prof_1') },
    { label: tr('cfo_sugg_cf_1'),   q: tr('cfo_sugg_cf_1') },
    { label: tr('cfo_sugg_risk_1'), q: tr('cfo_sugg_risk_1') },
  ]
  return items
}

// ── Main panel component ──────────────────────────────────────────────────────
export default function CfoPanel({ open, onClose }) {
  const { tr, lang }   = useLang()
  const { selectedId, selectedCompany } = useCompany()
  const { toQueryString, window: win } = usePeriodScope()

  const [input,    setInput]   = useState('')
  const [msgs,     setMsgs]    = useState([])
  const [loading,  setLoading] = useState(false)
  const [d,        setD]       = useState(null)   // /executive data
  const [fcData,   setFcData]  = useState(null)   // copy of d.forecast (same as GET /forecast object)
  const [consolidate] = useState(false)
  const inputRef    = useRef()
  const bottomRef   = useRef()
  const lastDomainRef = useRef(null)  // Phase 6.6: memory — last resolved domain
  const isRTL = lang === 'ar'

  // Load context once when panel opens
  const loadCtx = useCallback(async () => {
    if (!selectedId || d) return
    setLoading(true)
    try {
      const qs = buildAnalysisQuery(toQueryString, { lang, window: win, consolidate: false })
      if (qs === null) {
        setLoading(false)
        return
      }
      const exR = await fetch(`${API}/analysis/${selectedId}/executive?${qs}`, { headers: auth() })
      const exJ = exR.ok ? await exR.json() : null
      if (exJ?.data) {
        setD(exJ.data)
        setFcData(exJ.data.forecast && typeof exJ.data.forecast === 'object' ? exJ.data.forecast : null)
      }

      // Welcome message
      const health = exJ?.data?.health_score_v2
      const topDec = (exJ?.data?.decisions || [])[0]
      const welcome = tr('cfo_panel_welcome', { health: health ?? '—', top: topDec?.title || '' })
      setMsgs([{ role: 'assistant', content: welcome, sections: null }])
    } catch (e) {
      console.error('CfoPanel ctx:', e)
    } finally {
      setLoading(false)
    }
  }, [selectedId, lang, win, toQueryString, d, consolidate])

  useEffect(() => {
    if (open) {
      loadCtx()
      setTimeout(() => inputRef.current?.focus(), 300)
    } else {
      // Phase 6.6: reset memory on close
      lastDomainRef.current = null
    }
  }, [open, loadCtx])
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs])

  // Phase 6.6: reset conversation when company changes
  useEffect(() => {
    setMsgs([])
    setD(null)
    setFcData(null)
    lastDomainRef.current = null
  }, [selectedId])

  function ask(question) {
    if (!question.trim() || loading) return
    setInput('')
    // Phase 6.6: pass lastDomain for vague query resolution
    const domain = detectDomain(question, lang, lastDomainRef.current)
    // Persist non-all domains for conversation memory
    if (domain !== 'all') lastDomainRef.current = domain
    const sections = d ? buildResponse(question, domain, d, fcData, lang, tr) : null
    // Context label shown when domain came from memory
    const fromMemory = isVague(question, lang) && lastDomainRef.current && lastDomainRef.current !== 'all'
    setMsgs(prev => [
      ...prev,
      { role: 'user', content: question },
      { role: 'assistant', content: null, sections, domain, fromMemory },
    ])
  }

  const T = {
    bg:       '#0B0F14',
    surface:  '#111827',
    panel:    '#111827',
    card:     '#111827',
    border:   '#1F2937',
    bright:   'rgba(255,255,255,0.10)',
    accent:   '#00d4aa',
    text1:    '#ffffff',
    text2:    '#aab4c3',
    text3:    '#6b7280',
  }
  const urgClr = { high: '#f87171', medium: '#fbbf24', low: '#60a5fa' }

  if (!open) return null

  return (
    <>
      {/* Backdrop */}
      <div onClick={onClose}
        style={{ position:'fixed', inset:0, zIndex:1000,
          background:'rgba(0,0,0,0.55)' }}/>

      {/* Panel */}
      <div style={{
        position:'fixed', top:0, right:0, bottom:0, width:440,
        background:T.bg, borderLeft:`1px solid ${T.bright}`,
        zIndex:1001, display:'flex', flexDirection:'column',
        boxShadow:'-24px 0 80px rgba(0,0,0,0.7)',
        animation:'slideInRight .25s cubic-bezier(0.4,0,0.2,1)',
      }}>
        <style>{`
          @keyframes slideInRight{from{transform:translateX(100%);opacity:0}to{transform:none;opacity:1}}
          @keyframes spin{to{transform:rotate(360deg)}}
          .cfopanel-msg::-webkit-scrollbar{width:3px}
          .cfopanel-msg::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.1);border-radius:3px}
        `}</style>

        {/* Header */}
        <div style={{ padding:'16px 18px', borderBottom:`1px solid ${T.border}`,
          display:'flex', alignItems:'center', gap:12, flexShrink:0,
          background:`linear-gradient(135deg,${T.surface},${T.panel})` }}>
          <div style={{ width:36, height:36, borderRadius:10,
            background:'linear-gradient(135deg,#00d4aa,#0066ff)',
            boxShadow:'0 0 16px rgba(0,212,170,0.4)',
            display:'flex', alignItems:'center', justifyContent:'center',
            fontSize:16, flexShrink:0 }}>🧠</div>
          <div style={{ flex:1 }}>
            <div style={{ fontSize:14, fontWeight:800, color:T.text1, lineHeight:1 }}>
              {tr('cfo_ai_title')}
            </div>
            {selectedCompany?.name && (
              <div style={{ fontSize:11, color:T.text3, marginTop:2 }}>
                {selectedCompany.name}
              </div>
            )}
          </div>
          {loading && (
            <div style={{ width:14, height:14, border:`2px solid ${T.border}`,
              borderTopColor:T.accent, borderRadius:'50%',
              animation:'spin .7s linear infinite' }}/>
          )}
          <button onClick={onClose} style={{ width:30, height:30, borderRadius:8,
            border:`1px solid ${T.border}`, background:T.card,
            color:T.text2, cursor:'pointer', fontSize:16, lineHeight:1,
            display:'flex', alignItems:'center', justifyContent:'center' }}>✕</button>
        </div>

        {/* Quick actions */}
        <div style={{ padding:'10px 14px', borderBottom:`1px solid ${T.border}`,
          display:'flex', gap:6, flexWrap:'wrap', flexShrink:0,
          background:T.surface }}>
          {getQuickActions(tr).map((qa, i) => (
            <button key={i} onClick={() => ask(qa.q)}
              style={{ fontSize:10, fontWeight:600, padding:'4px 10px', borderRadius:20,
                background:T.card, border:`1px solid ${T.border}`,
                color:T.text2, cursor:'pointer',
                transition:'all .15s ease' }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = T.accent; e.currentTarget.style.color = T.accent }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = T.border; e.currentTarget.style.color = T.text2 }}>
              {qa.label}
            </button>
          ))}
        </div>

        {/* Messages */}
        <div className="cfopanel-msg" style={{ flex:1, overflowY:'auto',
          padding:'14px', display:'flex', flexDirection:'column', gap:10,
          direction: isRTL ? 'rtl' : 'ltr' }}>

          {msgs.map((msg, i) => (
            <div key={i} style={{ display:'flex',
              justifyContent: msg.role==='user' ? 'flex-end' : 'flex-start',
              alignItems:'flex-start', gap:8 }}>

              {msg.role === 'assistant' && (
                <div style={{ width:26, height:26, borderRadius:8, flexShrink:0,
                  background:'linear-gradient(135deg,#00d4aa22,#0066ff22)',
                  border:`1px solid ${T.accent}40`,
                  display:'flex', alignItems:'center', justifyContent:'center',
                  fontSize:12 }}>🧠</div>
              )}

              <div style={{ maxWidth:'84%' }}>
                {/* User bubble */}
                {msg.role === 'user' && (
                  <div style={{ padding:'9px 13px', borderRadius:'12px 12px 4px 12px',
                    background:T.accent, color:'#000',
                    fontSize:13, fontWeight:500, lineHeight:1.5 }}>
                    {msg.content}
                  </div>
                )}

                {/* Assistant: structured sections */}
                {msg.role === 'assistant' && msg.sections && (
                  <div style={{ display:'flex', flexDirection:'column', gap:7 }}>
                    {/* Phase 6.6: memory indicator */}
                    {msg.fromMemory && (
                      <div style={{ fontSize:9, color:T.text3, padding:'2px 8px',
                        borderRadius:20, background:T.card, border:`1px solid ${T.border}`,
                        display:'inline-flex', alignItems:'center', gap:4,
                        width:'fit-content', marginBottom:2 }}>
                        <span style={{ opacity:.6 }}>🧠</span>
                        <span>{tr('continuing_context')}</span>
                      </div>
                    )}
                    {msg.sections.map((sec, si) => (
                      <div key={si} style={{
                        padding:'10px 13px', borderRadius:10,
                        background: sec.accent ? `rgba(0,212,170,0.06)` : T.panel,
                        border: `1px solid ${sec.accent ? `rgba(0,212,170,0.2)` : T.border}`,
                        borderLeft: `3px solid ${sec.accent ? T.accent : T.bright}`,
                      }}>
                        <div style={{ fontSize:9, fontWeight:700, color:sec.accent?T.accent:T.text3,
                          textTransform:'uppercase', letterSpacing:'.07em', marginBottom:5 }}>
                          {sec.icon} {sec.label}
                        </div>
                        {sec.text && (
                          <div style={{ fontSize:12, color:T.text2, lineHeight:1.6 }}>
                            {sec.text}
                          </div>
                        )}
                        {sec.items && sec.items.map((item, ii) => (
                          <div key={ii} style={{ display:'flex', gap:8, marginTop:ii>0?6:0,
                            alignItems:'flex-start' }}>
                            <div style={{ width:18, height:18, borderRadius:'50%', flexShrink:0,
                              background:`${urgClr[item.urgency]||T.accent}18`,
                              border:`1px solid ${urgClr[item.urgency]||T.accent}40`,
                              display:'flex', alignItems:'center', justifyContent:'center',
                              fontSize:9, fontWeight:800, color:urgClr[item.urgency]||T.accent }}>
                              {item.num}
                            </div>
                            <div>
                              <div style={{ fontSize:11, fontWeight:700, color:T.text1,
                                marginBottom:2 }}>{item.title}</div>
                              {item.step && (
                                <div style={{ fontSize:10, color:T.text2, lineHeight:1.5 }}>
                                  {item.step}
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                )}

                {/* Assistant: plain text welcome */}
                {msg.role === 'assistant' && !msg.sections && msg.content && (
                  <div style={{ padding:'10px 13px', borderRadius:'12px 12px 12px 4px',
                    background:T.panel, border:`1px solid ${T.border}`,
                    fontSize:13, color:T.text2, lineHeight:1.7 }}
                    dangerouslySetInnerHTML={{ __html: msg.content
                      .replace(/\*\*(.+?)\*\*/g, `<strong style="color:${T.text1}">$1</strong>`)
                      .replace(/\n/g, '<br/>') }}/>
                )}
              </div>
            </div>
          ))}

          {/* Loading dots */}
          {loading && (
            <div style={{ display:'flex', gap:8, alignItems:'center', padding:'4px 0' }}>
              <div style={{ width:26, height:26, borderRadius:8, flexShrink:0,
                background:`rgba(0,212,170,0.1)`, border:`1px solid ${T.accent}40`,
                display:'flex', alignItems:'center', justifyContent:'center', fontSize:12 }}>🧠</div>
              <div style={{ display:'flex', gap:4 }}>
                {[0,1,2].map(i => (
                  <div key={i} style={{ width:6, height:6, borderRadius:'50%',
                    background:T.accent, opacity:.6,
                    animation:`spin .9s ${i*.2}s ease-in-out infinite` }}/>
                ))}
              </div>
            </div>
          )}
          <div ref={bottomRef}/>
        </div>

        {/* No company warning */}
        {!selectedId && (
          <div style={{ margin:'0 14px 10px', padding:'10px 14px', borderRadius:9,
            background:'rgba(245,166,35,0.08)', border:'1px solid rgba(245,166,35,0.22)',
            fontSize:11, color:'#f5a623' }}>
            {tr('cfo_select_company')}
          </div>
        )}

        {/* Input */}
        <div style={{ padding:'12px 14px', borderTop:`1px solid ${T.border}`,
          background:T.surface, flexShrink:0,
          display:'flex', gap:8, alignItems:'flex-end' }}>
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); ask(input) } }}
            placeholder={tr('cfo_ai_placeholder')}
            rows={1}
            style={{ flex:1, background:T.panel, border:`1px solid ${T.bright}`,
              borderRadius:10, padding:'9px 13px', color:T.text1, fontSize:13,
              resize:'none', lineHeight:1.5, outline:'none', fontFamily:'inherit',
              direction: isRTL ? 'rtl' : 'ltr',
              transition:'border-color .15s' }}
            onFocus={e => e.target.style.borderColor = T.accent}
            onBlur={e  => e.target.style.borderColor = T.bright}/>
          <button
            onClick={() => ask(input)}
            disabled={!input.trim() || loading}
            style={{ width:38, height:38, borderRadius:10,
              background: input.trim() && !loading ? T.accent : T.card,
              border:`1px solid ${input.trim() && !loading ? T.accent : T.border}`,
              color: input.trim() && !loading ? '#000' : T.text3,
              cursor: input.trim() && !loading ? 'pointer' : 'not-allowed',
              display:'flex', alignItems:'center', justifyContent:'center',
              transition:'all .15s', flexShrink:0 }}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <line x1="22" y1="2" x2="11" y2="13"/>
              <polygon points="22 2 15 22 11 13 2 9 22 2"/>
            </svg>
          </button>
        </div>
      </div>
    </>
  )
}
