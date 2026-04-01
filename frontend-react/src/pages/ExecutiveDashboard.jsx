/**
 * ExecutiveDashboard.jsx — Phase 30
 * Decision-first executive screen.
 * Hover = simple explanation. Click = deep panel.
 * Arabic = plain language, zero jargon.
 */
import { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLang }        from '../context/LangContext.jsx'
import { useCompany }     from '../context/CompanyContext.jsx'
import { usePeriodScope } from '../context/PeriodScopeContext.jsx'
import { kpiContextLabel, kpiLabel } from '../utils/kpiContext.js'
import { formatCompact, formatFull, formatDual, formatPct, formatMultiple, formatDays } from '../utils/numberFormat.js'

const API = '/api/v1'
function auth() {
  try { const t=JSON.parse(localStorage.getItem('vcfo_auth')||'{}').token; return t?{Authorization:`Bearer ${t}`}:{} }
  catch { return {} }
}

// ── Design tokens ─────────────────────────────────────────────────────────────
const T = {
  bg:'#0B0F14',      surface:'#111827',   panel:'#111827',    card:'#111827',
  border:'#1F2937',  accent:'#00d4aa',    green:'#34d399',    red:'#f87171',
  amber:'#fbbf24',   violet:'#7c5cfc',    blue:'#3b9eff',
  text1:'#ffffff',   text2:'#9ca3af',     text3:'#6b7280',
}
const stC  = {excellent:'#34d399', good:'#00d4aa', warning:'#fbbf24', risk:'#f87171', neutral:'#aab4c3'}
const dClr = {liquidity:T.blue, profitability:T.green, efficiency:T.violet, leverage:T.amber, growth:T.accent}
const dIco = {liquidity:'💧', profitability:'📈', efficiency:'⚡', leverage:'🏋', growth:'🚀'}
const uClr = {high:T.red, medium:T.amber, low:T.blue}
// fmtM → formatCompact (from numberFormat.js)
const fmtP = v => v==null?'—':`${Number(v).toFixed(1)}%`

// ── Pill badge ────────────────────────────────────────────────────────────────
const Pill = ({label, color}) => (
  <span style={{fontSize:9,fontWeight:800,padding:'2px 9px',borderRadius:20,
    background:`${color}18`,color,border:`1px solid ${color}30`,
    textTransform:'uppercase',letterSpacing:'.05em',flexShrink:0,whiteSpace:'nowrap'}}>
    {label}
  </span>
)

// ── Card hover lift ───────────────────────────────────────────────────────────
const lift = color => ({
  onMouseEnter: e => { e.currentTarget.style.transform='translateY(-2px)'; e.currentTarget.style.boxShadow=`0 10px 32px rgba(0,0,0,.55),0 0 0 1px ${color}30` },
  onMouseLeave: e => { e.currentTarget.style.transform=''; e.currentTarget.style.boxShadow='' },
})

// ──────────────────────────────────────────────────────────────────────────────
//  TopFocusBanner
// ──────────────────────────────────────────────────────────────────────────────

// ── FIX-4.3: DataQualityBanner ────────────────────────────────────────────────
function DataQualityBanner({ validation, lang, tr }) {
  if (!validation) return null
  const { consistent, warnings = [], has_errors, has_info } = validation
  if (consistent === true && !has_info) return null
  const color = has_errors ? '#f87171' : '#fbbf24'
  const bg    = has_errors ? 'rgba(248,113,113,0.05)' : 'rgba(251,191,36,0.05)'
  const bdr   = has_errors ? 'rgba(248,113,113,0.20)' : 'rgba(251,191,36,0.20)'
  return (
    <div style={{display:'flex',flexWrap:'wrap',alignItems:'center',gap:8,
      padding:'6px 14px',borderRadius:7,marginBottom:8,
      background:bg,borderWidth:'1px 1px 1px 3px',borderStyle:'solid',borderColor:`${bdr} ${bdr} ${bdr} ${color}`}}>
      <span style={{fontSize:11}}>{has_errors?'⚠':'ℹ'}</span>
      <span style={{fontSize:9,fontWeight:800,color,letterSpacing:'.05em',textTransform:'uppercase'}}>
        {has_errors ? tr('dq_warning_title') : tr('dq_notice_title')}
      </span>
      {warnings.map((w,i)=>{
        return <span key={i} style={{fontSize:9,color:'rgba(255,255,255,0.5)'}}>· {tr(`dq_${w.code}`)}</span>
      })}
    </div>
  )
}

function TopFocusBanner({ tr, decSum, alertSum, health }) {
  const topFocus = decSum?.top_focus
  const hiAlerts = alertSum?.high || 0
  const total    = alertSum?.total || 0
  if (!topFocus && !total) return null

  let icon, msg, color
  if (health >= 70 && hiAlerts === 0) {
    icon='✅'; color=T.green;  msg=tr('banner_all_good')
  } else if (hiAlerts >= 2 || health < 40) {
    icon='🚨'; color=T.red;   msg=tr(`dec_short_${decSum?.top_focus_domain||'liquidity'}`)||tr('banner_urgent')
  } else {
    icon='⚠️'; color=T.amber; msg=tr(`dec_short_${decSum?.top_focus_domain||'profitability'}`)||tr('banner_attention')
  }

  return (
    <div style={{background:`${color}0b`,borderWidth:'1px',borderStyle:'solid',borderColor:`${color}28`,
      borderLeftWidth:'4px',borderLeftColor:color,borderRadius:12,
      padding:'12px 20px',display:'flex',alignItems:'center',gap:12}}>
      <span style={{fontSize:20,flexShrink:0}}>{icon}</span>
      <div style={{flex:1,fontSize:14,fontWeight:700,color:T.text1,lineHeight:1.4}}>{msg}</div>
      {hiAlerts > 0 && <Pill label={`${hiAlerts} ${tr('banner_high_alerts')}`} color={T.red}/>}
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────────────────
//  ContextPanel — WHY → WHAT → IMPACT → TIME
// ──────────────────────────────────────────────────────────────────────────────
function ContextPanel({ type, payload, extra, tr, onClose, onNavigate, impacts={} }) {
  if (!type || !payload) return null
  const dc = dClr[payload.domain] || T.accent

  const Sec = ({ label, color=T.text3, children }) => (
    <div style={{marginBottom:22}}>
      <div style={{display:'flex',alignItems:'center',gap:7,marginBottom:10}}>
        <div style={{width:18,height:2,background:color,borderRadius:2}}/>
        <span style={{fontSize:10,fontWeight:800,color,textTransform:'uppercase',letterSpacing:'.07em'}}>{label}</span>
      </div>
      {children}
    </div>
  )

  const Steps = ({ text }) => {
    if (!text) return null
    const parts = text.split(/[0-9]+[).\s]+/).filter(s => s.trim().length > 5)
    if (parts.length <= 1) return <p style={{fontSize:12,color:T.text2,lineHeight:1.75,margin:0}}>{text}</p>
    return (
      <div style={{display:'flex',flexDirection:'column',gap:7}}>
        {parts.map((s,i) => (
          <div key={i} style={{display:'flex',gap:10,alignItems:'flex-start',
            background:`${dc}08`,borderRadius:8,padding:'9px 12px',border:`1px solid ${dc}15`}}>
            <div style={{width:20,height:20,borderRadius:'50%',background:`${dc}22`,
              display:'flex',alignItems:'center',justifyContent:'center',
              flexShrink:0,fontSize:11,fontWeight:800,color:dc}}>{i+1}</div>
            <span style={{fontSize:11,color:T.text2,lineHeight:1.6}}>{s.trim()}</span>
          </div>
        ))}
      </div>
    )
  }

  // DECISION
  const Decision = () => (
    <>
      <div style={{fontSize:17,fontWeight:800,color:T.text1,lineHeight:1.3,marginBottom:8}}>{payload.title}</div>
      <div style={{display:'flex',gap:6,flexWrap:'wrap',marginBottom:22}}>
        <Pill label={tr(`urgency_${payload.urgency}`)||payload.urgency} color={uClr[payload.urgency]||T.text3}/>
        {payload.impact_level && <Pill label={tr(`impact_${payload.impact_level}`)||payload.impact_level} color={uClr[payload.impact_level]||T.text3}/>}
        <Pill label={`${payload.confidence||'—'}%`} color={T.text3}/>
      </div>

      <Sec label={tr('exec_why')} color={T.red}>
        <p style={{fontSize:12,color:T.text2,lineHeight:1.75,margin:0,marginBottom:extra?.causes?.length?10:0}}>
          {payload.reason}
        </p>
        {extra?.causes?.slice(0,2).map((c,i) => (
          <div key={i} style={{marginTop:7,padding:'8px 11px',borderRadius:8,
            background:`${T.red}08`,border:`1px solid ${T.red}18`}}>
            <div style={{fontSize:10,fontWeight:700,color:T.text1,marginBottom:2}}>{c.title}</div>
            <div style={{fontSize:10,color:T.text2,lineHeight:1.5,
              display:'-webkit-box',WebkitLineClamp:2,WebkitBoxOrient:'vertical',overflow:'hidden'}}>
              {c.description}
            </div>
          </div>
        ))}
      </Sec>

      <Sec label={tr('exec_actions')} color={dc}>
        <Steps text={payload.action}/>
      </Sec>

      {payload.expected_effect && (
        <Sec label={tr('exec_effect')} color={T.green}>
          <div style={{background:`${T.green}08`,borderRadius:9,padding:'12px 14px',
            border:`1px solid ${T.green}1a`,fontSize:12,color:T.text2,lineHeight:1.75}}>
            {payload.expected_effect}
          </div>
        </Sec>
      )}

      {/* Expected Impact section */}
      {(()=>{
        const impKey = payload?.key||payload?.domain
        const imp = impacts[impKey]?.impact || impacts[payload?.domain]?.impact
        if (!imp||imp.type==='qualitative'||imp.value==null) return null
        const fmtV = v => v==null?'—':v>=1e6?`+${(v/1e6).toFixed(1)}M`:v>=1e3?`+${(v/1e3).toFixed(0)}K`:`+${v.toFixed(0)}`
        return (
          <div style={{background:`${T.green}08`,border:`1px solid ${T.green}25`,borderRadius:11,padding:'14px 16px',marginBottom:16}}>
            <div style={{display:'flex',alignItems:'center',gap:7,marginBottom:10}}>
              <div style={{width:18,height:2,background:T.green,borderRadius:2}}/>
              <span style={{fontSize:9,fontWeight:800,color:T.green,textTransform:'uppercase',letterSpacing:'.08em'}}>
                {tr('impact_expected_label')}
              </span>
            </div>
            <div style={{fontFamily:'monospace',fontSize:24,fontWeight:800,color:T.green,direction:'ltr',marginBottom:4}}>
              {fmtV(imp.value)}
            </div>
            {imp.range?.low!=null&&imp.range?.high!=null&&(
              <div style={{fontSize:10,color:T.text2,marginBottom:8,fontFamily:'monospace'}}>
                {fmtV(imp.range.low)} – {fmtV(imp.range.high)} {tr('impact_range_label')}
              </div>
            )}
            <p style={{fontSize:11,color:T.text2,lineHeight:1.6,margin:'0 0 10px'}}>{imp.description}</p>
            <div style={{display:'flex',alignItems:'center',gap:8,flexWrap:'wrap'}}>
              <span style={{fontSize:9,color:T.green,background:`${T.green}15`,padding:'2px 8px',borderRadius:20,fontWeight:700,border:`1px solid ${T.green}30`}}>
                {tr('fc_confidence')}: {imp.confidence}%
              </span>
              {imp.assumption&&<span style={{fontSize:10,color:T.text2,fontStyle:'italic'}}>{tr('impact_based_on')}: {imp.assumption}</span>}
            </div>
          </div>
        )
      })()}
      <div style={{display:'flex',alignItems:'center',gap:12,
        background:T.card,borderRadius:11,padding:'12px 16px',border:`1px solid ${T.border}`}}>
        <span style={{fontSize:22,opacity:.45}}>⏱</span>
        <div>
          <div style={{fontSize:9,color:T.text3,textTransform:'uppercase',letterSpacing:'.07em',marginBottom:3}}>
            {tr('exec_timeframe')}
          </div>
          <div style={{fontSize:16,fontWeight:800,color:uClr[payload.urgency]||T.accent,fontFamily:'monospace'}}>
            {payload.timeframe}
          </div>
        </div>
      </div>
    </>
  )

  // KPI
  const Kpi = () => (
    <>
      <div style={{fontSize:17,fontWeight:800,color:T.text1,marginBottom:6}}>
        {tr(`kpi_label_${payload.type}`)||payload.type}
      </div>
      <div style={{fontSize:12,color:T.text2,lineHeight:1.65,marginBottom:20}}>
        {tr(`kpi_explain_${payload.type}`)||extra?.explanation||''}
      </div>
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10,marginBottom:20}}>
        {[
          {lbl:tr('exec_trend'), val:payload.mom!=null?`${payload.mom>0?'+':''}${payload.mom?.toFixed(1)}% MoM`:'—', clr:payload.mom>0?T.green:payload.mom<0?T.red:T.text2},
          {lbl:'YoY',            val:payload.yoy!=null?`${payload.yoy>0?'+':''}${payload.yoy?.toFixed(1)}%`:'—',     clr:payload.yoy>0?T.green:payload.yoy<0?T.red:T.text2},
        ].map(({lbl,val,clr}) => (
          <div key={lbl} style={{background:T.card,borderRadius:8,padding:'12px 14px',border:`1px solid ${T.border}`}}>
            <div style={{fontSize:9,color:T.text3,textTransform:'uppercase',letterSpacing:'.06em',marginBottom:4}}>{lbl}</div>
            <div style={{fontFamily:'monospace',fontSize:17,fontWeight:800,color:clr}}>{val}</div>
          </div>
        ))}
      </div>
      {extra?.alerts?.length > 0 && (
        <Sec label={tr('alerts_title')} color={T.amber}>
          {extra.alerts.slice(0,3).map((a,i) => (
            <div key={i} style={{padding:'9px 11px',marginBottom:6,borderRadius:8,
              background:`${uClr[a.severity]||T.text3}0d`,border:`1px solid ${uClr[a.severity]||T.text3}25`}}>
              <div style={{fontSize:11,fontWeight:700,color:uClr[a.severity]||T.text2,marginBottom:2}}>{a.title}</div>
              <div style={{fontSize:10,color:T.text2,lineHeight:1.5}}>{a.message}</div>
            </div>
          ))}
        </Sec>
      )}
    </>
  )

  // DOMAIN
  const Domain = () => {
    const causes = extra?.causes?.filter(c=>c.domain===payload.domain||c.domain==='cross_domain')||[]
    const dDecs  = extra?.decisions?.filter(d=>d.domain===payload.domain)||[]
    return (
      <>
        <div style={{display:'flex',alignItems:'center',gap:12,marginBottom:20}}>
          <span style={{fontSize:26}}>{dIco[payload.domain]||'◉'}</span>
          <div style={{flex:1}}>
            <div style={{fontSize:17,fontWeight:800,color:T.text1}}>
              {tr(`domain_${payload.domain}_simple`)||tr(`domain_${payload.domain}`)||payload.domain}
            </div>
            <div style={{fontSize:11,color:T.text2,marginTop:2}}>{tr(`domain_${payload.domain}_exp`)||''}</div>
          </div>
          <div style={{textAlign:'right'}}>
            <div style={{fontFamily:'monospace',fontSize:22,fontWeight:800,color:dc}}>{payload.score!=null?Math.round(payload.score):'—'}</div>
            <div style={{fontSize:9,color:T.text3}}>/100</div>
          </div>
        </div>

        {causes.length>0 && (
          <Sec label={tr('exec_why')} color={T.red}>
            {causes.slice(0,3).map((c,i) => (
              <div key={i} style={{padding:'9px 11px',marginBottom:6,borderRadius:8,
                background:`${uClr[c.impact]||T.text3}0d`,borderWidth:'1px',borderStyle:'solid',
                borderColor:`${uClr[c.impact]||T.text3}25`,
                borderLeftWidth:'3px',borderLeftColor:uClr[c.impact]||T.text3}}>
                <div style={{fontSize:11,fontWeight:700,color:T.text1,marginBottom:3}}>{c.title}</div>
                <div style={{fontSize:10,color:T.text2,lineHeight:1.5,
                  display:'-webkit-box',WebkitLineClamp:2,WebkitBoxOrient:'vertical',overflow:'hidden'}}>
                  {c.description}
                </div>
              </div>
            ))}
          </Sec>
        )}

        {dDecs.length>0 && (
          <Sec label={tr('exec_actions')} color={dc}>
            {dDecs.slice(0,2).map((d,i) => (
              <div key={i} style={{padding:'9px 11px',marginBottom:6,borderRadius:8,
                background:`${dc}08`,border:`1px solid ${dc}20`}}>
                <div style={{fontSize:11,fontWeight:700,color:T.text1,marginBottom:2}}>{d.title}</div>
                <div style={{fontSize:10,color:T.text2,fontFamily:'monospace'}}>{d.timeframe}</div>
              </div>
            ))}
          </Sec>
        )}

        {Object.keys(payload.ratios||{}).length>0 && (
          <Sec label={tr('exec_breakdown')} color={T.text3}>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8}}>
              {Object.entries(payload.ratios).slice(0,6).map(([k,r]) => {
                const rc = {good:T.green,warning:T.amber,risk:T.red,neutral:T.text2}[r?.status]||T.text2
                return (
                  <div key={k} style={{background:T.card,borderRadius:7,padding:'8px 10px',
                    borderWidth:'1px 1px 1px 2px',borderStyle:'solid',borderColor:`${T.border} ${T.border} ${T.border} ${rc}`}}>
                    <div style={{fontSize:8,color:T.text3,textTransform:'uppercase',marginBottom:2}}>
                      {tr(`ratio_${k}`)||k.replace(/_/g,' ')}
                    </div>
                    <div style={{fontFamily:'monospace',fontSize:13,fontWeight:700,color:rc}}>
                      {r?.value!=null?r.value:'—'}
                      <span style={{fontSize:9,color:T.text3,marginLeft:3}}>{r?.unit||''}</span>
                    </div>
                  </div>
                )
              })}
            </div>
          </Sec>
        )}
      </>
    )
  }

  // ALERT
  const Alert = () => (
    <>
      <div style={{fontSize:17,fontWeight:800,color:T.text1,lineHeight:1.3,marginBottom:10}}>{payload.title}</div>
      <div style={{marginBottom:20}}><Pill label={tr(`urgency_${payload.severity}`)||payload.severity} color={uClr[payload.severity]||T.text3}/></div>
      <Sec label={tr('exec_why')} color={uClr[payload.severity]||T.amber}>
        <p style={{fontSize:12,color:T.text2,lineHeight:1.75,margin:0}}>{payload.message}</p>
      </Sec>
      <Sec label={tr('exec_actions')} color={T.accent}>
        <p style={{fontSize:12,color:T.text2,lineHeight:1.75,margin:0}}>{payload.action}</p>
      </Sec>
    </>
  )

  return (
    <>
      <div onClick={onClose} style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.5)',
        zIndex:998}}/>
      <div style={{position:'fixed',top:0,right:0,bottom:0,width:460,
        background:T.panel,borderLeft:`1px solid ${T.border}`,
        zIndex:999,display:'flex',flexDirection:'column',
        boxShadow:'-24px 0 80px rgba(0,0,0,0.75)',
        animation:'slideIn .22s cubic-bezier(.4,0,.2,1)'}}>

        {/* Header */}
        <div style={{padding:'18px 22px',borderBottom:`1px solid ${T.border}`,
          display:'flex',alignItems:'center',gap:10,flexShrink:0}}>
          <div style={{flex:1,fontSize:10,fontWeight:700,color:T.text2,
            textTransform:'uppercase',letterSpacing:'.07em'}}>
            {type==='decision'?tr('tab_decisions_v2')
             :type==='kpi'?tr('exec_kpi_title')
             :type==='domain'?tr('exec_domain_title')
             :type==='alert'?tr('alerts_title')
             :tr('exec_title')}
          </div>
          <button onClick={onClose} style={{width:30,height:30,borderRadius:8,
            border:`1px solid ${T.border}`,background:T.card,color:T.text2,
            cursor:'pointer',display:'flex',alignItems:'center',justifyContent:'center',
            fontSize:17,fontWeight:300}}>×</button>
        </div>

        {/* Body */}
        <div style={{flex:1,overflowY:'auto',padding:'22px 22px'}}>
          {type==='decision' && <Decision/>}
          {type==='kpi'      && <Kpi/>}
          {type==='domain'   && <Domain/>}
          {type==='alert'    && <Alert/>}
        </div>
      </div>
    </>
  )
}

// ──────────────────────────────────────────────────────────────────────────────
//  TopBar
// ──────────────────────────────────────────────────────────────────────────────
function TopBar({ tr, health, status, companyName, period, loading, onRefresh, periodCount, scopeLabel, consolidate, setConsolidate }) {
  const hc   = stC[status] || T.text2
  const circ = 2 * Math.PI * 34
  const dash = (Math.max(0,Math.min(100,health||0)) / 100) * circ
  return (
    <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:16,
      padding:'16px 24px',display:'flex',alignItems:'center',gap:20,flexWrap:'wrap'}}>
      <svg width={80} height={80} viewBox="0 0 88 88" style={{flexShrink:0}}>
        <circle cx={44} cy={44} r={34} fill="none" stroke={T.border} strokeWidth={5}/>
        <circle cx={44} cy={44} r={34} fill="none" stroke={hc} strokeWidth={5}
          strokeDasharray={`${dash} ${circ-dash}`} strokeDashoffset={circ*.25}
          strokeLinecap="round" style={{filter:`drop-shadow(0 0 7px ${hc}90)`}}/>
        <text x={44} y={43} textAnchor="middle" fontSize={17} fontWeight={800}
          fill={hc} fontFamily="monospace">{health??'—'}</text>
        <text x={44} y={57} textAnchor="middle" fontSize={8} fill={T.text3}>/100</text>
      </svg>
      <div style={{flex:1,minWidth:160}}>
        <div style={{fontSize:10,color:T.text2,marginBottom:3,textTransform:'uppercase',
          letterSpacing:'.06em',fontWeight:600}}>{tr('exec_health_label')}</div>
        <div style={{fontSize:19,fontWeight:800,color:T.text1,lineHeight:1.2,marginBottom:8}}>
          {companyName||'—'}
        </div>
        <div style={{display:'flex',alignItems:'center',gap:8,flexWrap:'wrap'}}>
          <div style={{width:7,height:7,borderRadius:'50%',background:hc,
            boxShadow:`0 0 8px ${hc}`}}/>
          <span style={{fontSize:12,fontWeight:700,color:hc}}>
            {tr(`status_${status}_simple`)||tr(`status_${status}`)||status}
          </span>
          {period && <span style={{fontSize:11,color:T.text2,fontFamily:'monospace'}}>{period}</span>}
          {periodCount!=null && <span style={{fontSize:10,color:T.text3}}>· {periodCount}p</span>}
          {scopeLabel && <span style={{fontSize:10,color:T.text3}}>· {scopeLabel}</span>}
        </div>
      </div>
      <button onClick={onRefresh} disabled={loading}
        style={{flexShrink:0,width:36,height:36,borderRadius:10,border:`1px solid ${T.border}`,
          background:T.card,color:T.text2,cursor:'pointer',
          display:'flex',alignItems:'center',justifyContent:'center',fontSize:16}}>
        {loading
          ? <div style={{width:14,height:14,border:`2px solid ${T.border}`,
              borderTopColor:T.accent,borderRadius:'50%',animation:'spin .7s linear infinite'}}/>
          : '↻'}
      </button>
          {/* ── Data Source Toggle ── */}
          <div style={{display:'flex',alignItems:'center',gap:0,background:'var(--bg-elevated)',
            border:'1px solid var(--border)',borderRadius:8,overflow:'hidden',flexShrink:0}}>
            {[{v:false,l:tr('company_uploads')},{v:true,l:tr('branch_consolidation')}].map(opt=>(
              <button key={String(opt.v)} onClick={()=>{ setConsolidate(opt.v) }}
                style={{padding:'5px 12px',fontSize:11,fontWeight:600,border:'none',cursor:'pointer',
                  background: consolidate===opt.v ? 'var(--accent)' : 'transparent',
                  color:      consolidate===opt.v ? '#000' : 'var(--text-secondary)',
                  transition: 'all .15s', whiteSpace:'nowrap'}}>
                {opt.l}
              </button>
            ))}
          </div>
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────────────────
//  ActionStrip — short titles, hover = reason, click = panel
// ──────────────────────────────────────────────────────────────────────────────
function ActionStrip({ decisions, tr, onSelect, causes, impacts={} }) {
  if (!decisions?.length) return null
  return (
    <div>
      <div style={{fontSize:10,fontWeight:700,color:T.text3,textTransform:'uppercase',
        letterSpacing:'.08em',marginBottom:10}}>{tr('exec_action_strip')}</div>
      <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:10}}>
        {decisions.slice(0,3).map((dec,i) => {
          const uc    = uClr[dec.urgency]||T.text3
          const isTop = i === 0
          // Short title: use dedicated i18n key (max 4 words)
          const shortTitle = tr(`dec_short_${dec.domain}`)||dec.title
          const hint       = dec.reason?.split('. ')[0]||''
          const linkedC    = causes?.filter(c=>c.domain===dec.domain||c.domain==='cross_domain')||[]

          return (
            <div key={dec.key||i}
              onClick={()=>onSelect('decision', dec, {causes:linkedC})}
              title={hint}
              style={{background:isTop?`linear-gradient(135deg,${T.card},rgba(0,212,170,0.07))`:T.card,
                borderWidth:'1px',borderStyle:'solid',
                borderColor:isTop?`${T.accent}30`:T.border,
                borderTopWidth:'3px',borderTopColor:uc,borderRadius:12,
                padding:'14px 16px',cursor:'pointer',
                transition:'transform .15s ease,box-shadow .15s ease'}}
              {...lift(uc)}>
              <div style={{display:'flex',alignItems:'center',gap:7,marginBottom:9}}>
                <span style={{fontSize:14}}>{dIco[dec.domain]||'◉'}</span>
                <Pill label={tr(`urgency_${dec.urgency}`)||dec.urgency} color={uc}/>
                {isTop && <span style={{marginLeft:'auto',fontSize:9,color:T.accent,fontWeight:800}}>#1</span>}
              </div>
              {/* Title: max 4 words */}
              <div style={{fontSize:13,fontWeight:800,color:T.text1,lineHeight:1.3,marginBottom:5}}>
                {shortTitle}
              </div>
              {/* Impact preview chip */}
              {(()=>{
                const impKey = dec.key||dec.domain
                const imp = impacts[impKey]?.impact || impacts[dec.domain]?.impact
                if (imp?.value!=null) return (
                  <div style={{display:'inline-flex',alignItems:'center',gap:4,
                    background:`${uc}15`,border:`1px solid ${uc}30`,borderRadius:20,
                    padding:'2px 8px',marginBottom:6,width:'fit-content'}}>
                    <span style={{fontSize:11,fontWeight:800,color:uc,fontFamily:'monospace'}}>
                      {imp.unit==='%'?`${imp.value>0?'+':''}${imp.value.toFixed(1)}%`
                       :(imp.value>=1e6?`+${(imp.value/1e6).toFixed(1)}M`
                        :imp.value>=1e3?`+${(imp.value/1e3).toFixed(0)}K`
                        :`+${imp.value.toFixed(0)}`)}
                    </span>
                    <span style={{fontSize:9,color:uc,opacity:.8}}>
                      {imp.type==='cash'?tr('impact_type_cash')
                       :imp.type==='margin'?tr('impact_type_margin')
                       :tr('risk_down_short')}
                    </span>
                  </div>
                )
                return null
              })()}
              {/* 1-line hint only */}
              <div style={{fontSize:10,color:T.text2,lineHeight:1.4,marginBottom:9,
                display:'-webkit-box',WebkitLineClamp:1,WebkitBoxOrient:'vertical',overflow:'hidden'}}>
                {hint}
              </div>
              <div style={{fontSize:10,color:T.text2,fontFamily:'monospace'}}>⏱ {dec.timeframe}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────────────────
//  ExecutiveKpiRow — simple labels, animated, hover = explanation
// ──────────────────────────────────────────────────────────────────────────────
function ExecutiveKpiRow({ kpis, cashflow, main, tr, onSelect, alerts, ctxLabel }) {
  // FIX-3.5: carry reliability flag on cashflow card
  const cfEstimated = cashflow?.reliability === 'estimated'
  // CERT-FIX: WC reads statement_bundle as authoritative fallback
  // kpi_block has no WC KPI, cashflow_engine doesn't expose it at top-level
  // statement_engine → balance_sheet → working_capital is single source of truth
  const wc       = kpis.working_capital?.value
               ?? cashflow?.working_capital
               ?? main?.statements?.balance_sheet?.working_capital
  const wcColor  = wc==null?T.text3:wc>=0?T.green:T.red
  const cards = [
    { key:'revenue',         value:formatCompact(kpis.revenue?.value),        full:formatFull(kpis.revenue?.value),        mom:kpis.revenue?.mom_pct,    yoy:kpis.revenue?.yoy_pct,    color:T.accent,  icon:'📈' },
    { key:'net_profit',      value:formatCompact(kpis.net_profit?.value),      full:formatFull(kpis.net_profit?.value),      mom:kpis.net_profit?.mom_pct, yoy:kpis.net_profit?.yoy_pct, color:T.green,   icon:'💰' },
    { key:'cashflow',        value:formatCompact(cashflow?.operating_cashflow), full:formatFull(cashflow?.operating_cashflow), mom:cashflow?.operating_cashflow_mom, yoy:null, color:T.blue,   icon:'💧', estimated:cfEstimated },
    { key:'net_margin',      value:fmtP(kpis.net_margin?.value),               full:null,                                    mom:kpis.net_margin?.mom_pct, yoy:null,                     color:T.violet,  icon:'%'  },
    { key:'working_capital', value:formatCompact(wc),                           full:formatFull(wc),                          mom:null,                     yoy:null, sub:wc!=null&&wc<0?tr('wc_negative'):null, color:wcColor, icon:'⚖️' },
  ]
  return (
    <div>
      <div style={{fontSize:10,fontWeight:700,color:T.text3,textTransform:'uppercase',
        letterSpacing:'.08em',marginBottom:10}}>{tr('exec_kpi_title')}</div>
      <div style={{display:'grid',gridTemplateColumns:'repeat(5,1fr)',gap:10}}>
        {cards.map(c => {
          const mc = c.mom==null?T.text3:c.mom>0?T.green:c.mom<0?T.red:T.text2
          const explain = tr(`kpi_explain_${c.key}`)
          return (
            <div key={c.key}
              onClick={()=>onSelect('kpi',{type:c.key,mom:c.mom,yoy:c.yoy},
                {alerts:alerts?.filter(a=>a.impact==='profitability')||[], explanation:explain})}
              title={explain}
              style={{
                background:T.card,
                borderWidth:'1px',borderStyle:'solid',borderColor:T.border,
                borderTopWidth:'2px',borderTopColor:c.color,
                borderRadius:13,
                padding:'14px 16px',cursor:'pointer',
                transition:'transform 0.2s cubic-bezier(0.4,0,0.2,1), box-shadow 0.2s ease, border-color 0.2s ease',
              }}
              {...lift(c.color)}>
              <div style={{display:'flex',alignItems:'center',gap:6,marginBottom:8}}>
                <span style={{fontSize:12}}>{c.icon}</span>
                <span style={{fontSize:10,color:T.text2,fontWeight:700,textTransform:'uppercase',
                  letterSpacing:'.05em'}}>{kpiLabel(tr(`kpi_label_${c.key}`)||c.key, ctxLabel(), tr)}</span>
              </div>
              <div style={{
                fontFamily:'var(--font-display)',fontSize:22,fontWeight:800,color:'#ffffff',
                marginBottom:3,direction:'ltr',
                letterSpacing:'-0.025em',lineHeight:1,
                animation:'fadeUp .35s ease',
                transition:'text-shadow 0.2s ease',
              }}>
                {c.value}
              </div>
              {c.full&&<div style={{fontFamily:'var(--font-mono)',fontSize:9,color:T.text3,marginBottom:4,letterSpacing:'.02em',direction:'ltr'}}>{c.full}</div>}
              <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
                {c.mom!=null && <span style={{
                  fontFamily:'var(--font-mono)',fontSize:10,fontWeight:700,color:mc,
                  padding:'1px 5px',borderRadius:8,background:`${mc}14`,
                }}>
                  {c.mom>0?'+':''}{c.mom?.toFixed(1)}% MoM
                </span>}
                {c.yoy!=null && <span style={{fontFamily:'monospace',fontSize:10,
                  color:c.yoy>0?T.green:c.yoy<0?T.red:T.text2}}>
                  {c.yoy>0?'+':''}{c.yoy?.toFixed(1)}% YoY
                </span>}
              </div>
              {/* FIX-3.5: estimated badge for cashflow card */}
              {c.estimated&&(
                <div style={{marginTop:6,fontSize:9,color:'#f59e0b',
                  padding:'2px 7px',borderRadius:5,
                  background:'rgba(245,158,11,0.1)',
                  border:'1px solid rgba(245,158,11,0.25)',
                  display:'inline-block'}}>
                  ⚠ Estimated
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────────────────
//  DomainGrid — score + signal (1 line) + action on click
// ──────────────────────────────────────────────────────────────────────────────
function DomainGrid({ intelligence, tr, onSelect, rootCauses, decisions }) {
  const ratios  = intelligence?.ratios  || {}
  const trends  = intelligence?.trends  || {}
  const domains = ['liquidity','profitability','efficiency','leverage','growth']

  const score = d => {
    if (d==='growth') {
      const dir = trends?.revenue?.direction
      return dir==='up'?72:dir==='down'?28:50
    }
    const cat = ratios[d]; if(!cat) return 50
    const s2  = {good:100,neutral:60,warning:35,risk:10}
    const vs  = Object.values(cat).map(v=>s2[v?.status]||50)
    return Math.round(vs.reduce((a,b)=>a+b,0)/vs.length)
  }

  const ratioMap = d => ratios[{
    liquidity:'liquidity', profitability:'profitability',
    efficiency:'efficiency', leverage:'leverage', growth:'profitability',
  }[d]] || {}

  return (
    <div>
      <div style={{fontSize:10,fontWeight:700,color:T.text3,textTransform:'uppercase',
        letterSpacing:'.08em',marginBottom:10}}>{tr('exec_domain_title')}</div>
      <div style={{display:'grid',gridTemplateColumns:'repeat(5,1fr)',gap:10}}>
        {domains.map(d => {
          const s   = score(d)
          const dc  = dClr[d]||T.accent
          const st  = s>=70?'good':s>=45?'warning':'risk'
          const sc  = stC[st]
          const sig = s>=70 ? tr(`domain_signal_${d}_good`)
                             : s>=45 ? tr(`domain_signal_${d}_warn`)
                                     : tr(`domain_signal_${d}_risk`)
          return (
            <div key={d}
              onClick={()=>onSelect('domain',{domain:d,score:s,status:st,ratios:ratioMap(d)},{causes:rootCauses,decisions})}
              title={tr(`domain_${d}_exp`)||''}
              style={{background:T.card,borderWidth:'1px',borderStyle:'solid',borderColor:`${sc}20`,
                borderTopWidth:'3px',borderTopColor:dc,borderRadius:13,
                padding:'14px 12px',cursor:'pointer',
                transition:'transform .15s ease,box-shadow .15s ease'}}
              {...lift(dc)}>
              <div style={{display:'flex',alignItems:'center',gap:6,marginBottom:10}}>
                <span style={{fontSize:15}}>{dIco[d]}</span>
                <span style={{fontSize:10,fontWeight:800,color:dc,
                  textTransform:'uppercase',letterSpacing:'.06em'}}>
                  {tr(`domain_${d}_simple`)||tr(`domain_${d}`)||d}
                </span>
              </div>

              {/* Mini arc gauge */}
              <svg width="100%" height={36} viewBox="0 0 100 36">
                <path d="M10,31 A40,40 0 0,1 90,31" fill="none" stroke={T.border} strokeWidth={5}/>
                <path d="M10,31 A40,40 0 0,1 90,31" fill="none" stroke={dc} strokeWidth={5}
                  strokeDasharray={`${s*1.26} 126`} strokeLinecap="round"
                  style={{filter:`drop-shadow(0 0 5px ${dc}70)`}}/>
                <text x={50} y={34} textAnchor="middle" fontSize={13}
                  fontWeight={800} fill={dc} fontFamily="monospace">{s}</text>
              </svg>

              {/* 1-line signal */}
              <div style={{marginTop:9,display:'flex',alignItems:'flex-start',gap:5}}>
                <div style={{width:5,height:5,borderRadius:'50%',background:sc,
                  flexShrink:0,marginTop:3}}/>
                <span style={{fontSize:9,color:sc,lineHeight:1.4}}>
                  {sig||tr(`status_${st}_simple`)||st}
                </span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────────────────
//  RootCausesStrip — top 3 causes with domain + impact badges
// ──────────────────────────────────────────────────────────────────────────────
function RootCausesStrip({ causes, tr, onSelect }) {
  if (!causes?.length) return null
  const top = causes.slice(0, 3)
  return (
    <div>
      <div style={{fontSize:10,fontWeight:700,color:T.text3,textTransform:'uppercase',
        letterSpacing:'.08em',marginBottom:10}}>{tr('exec_root_causes')}</div>
      <div style={{display:'grid',gridTemplateColumns:`repeat(${top.length},1fr)`,gap:10}}>
        {top.map((c,i) => {
          const ic = uClr[c.impact]||T.text3
          const dc = dClr[c.domain]||T.accent
          return (
            <div key={i}
              onClick={()=>onSelect('domain',{domain:c.domain,score:50},{causes:[c]})}
              style={{background:T.card,borderWidth:'1px',borderStyle:'solid',borderColor:T.border,
                borderLeftWidth:'3px',borderLeftColor:ic,borderRadius:11,
                padding:'13px 15px',cursor:'pointer',
                transition:'transform .15s ease,box-shadow .15s ease'}}
              onMouseEnter={e=>{e.currentTarget.style.transform='translateY(-2px)';e.currentTarget.style.boxShadow=`0 8px 28px rgba(0,0,0,.4),0 0 0 1px ${ic}25`}}
              onMouseLeave={e=>{e.currentTarget.style.transform='';e.currentTarget.style.boxShadow=''}}>
              <div style={{display:'flex',gap:6,marginBottom:8}}>
                {c.domain&&<Pill label={tr(`domain_${c.domain}_simple`)||c.domain} color={dc}/>}
                {c.impact&&<Pill label={tr(`urgency_${c.impact}`)||c.impact} color={ic}/>}
              </div>
              <div style={{fontSize:12,fontWeight:700,color:T.text1,lineHeight:1.35,marginBottom:5}}>
                {c.title}
              </div>
              <div style={{fontSize:10,color:T.text2,lineHeight:1.5,
                display:'-webkit-box',WebkitLineClamp:2,WebkitBoxOrient:'vertical',overflow:'hidden'}}>
                {c.description}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────────────────
//  KeyInsightsStrip — Phase 6.1: top insights from statements + decisions
//  Reads: d.statements.insights, d.decisions[].reason — NO calculation
// ──────────────────────────────────────────────────────────────────────────────
function KeyInsightsStrip({ stmtInsights, decisions, fcData, lang }) {
  const l = lang || 'en'
  // Build insight list: statement insights first, then decision reasons
  const items = []
  ;(stmtInsights || []).slice(0, 2).forEach(ins => {
    if (!ins?.message) return
    // cause: first matching decision reason for same domain
    const dec = (decisions||[]).find(d=>d.domain===ins.domain)
    const cause = dec?.reason ? dec.reason.split('. ')[0].slice(0,60) : null
    items.push({ text: ins.message.split('. ')[0], domain: ins.domain, cause })
  })
  ;(decisions || []).slice(0, 2).forEach(dec => {
    if (items.length >= 3) return
    const sentence = (dec.reason || '').split('. ')[0]
    if (sentence.length > 10) items.push({ text: sentence, domain: dec.domain, cause: null })
  })
  if (!items.length && !fcData?.available) return null
  const dc = {liquidity:'var(--blue)',profitability:'var(--green)',efficiency:'var(--violet)',
               growth:'var(--accent)',leverage:'var(--amber)'}
  return (
    <div>
      <div style={{fontSize:10,fontWeight:700,color:T.text3,textTransform:'uppercase',
        letterSpacing:'.08em',marginBottom:10}}>
        {l === 'ar' ? '💡 أبرز الرؤى' : '💡 Key Insights'}
      </div>
      <div style={{display:'flex',flexDirection:'column',gap:6}}>
        {items.map((item, i) => (
          <div key={i} style={{
            display:'flex',flexDirection:'column',gap:2,
            padding:'9px 14px',borderRadius:9,
            background:'rgba(255,255,255,0.02)',
            borderLeft:`2px solid ${dc[item.domain]||T.accent}`,
          }}>
            <span style={{fontSize:11,color:T.text2,lineHeight:1.5,opacity:.85}}>💡 {item.text}</span>
            {item.cause&&<span style={{fontSize:9,color:T.text3,opacity:.6,lineHeight:1.3}}>↳ {item.cause}</span>}
          </div>
        ))}
      </div>
      {/* Phase 6.4 */}
      {fcData?.available && (() => {
        const bRev = fcData?.scenarios?.base?.revenue?.[0]
        const bNp  = fcData?.scenarios?.base?.net_profit?.[0]
        const risk = fcData?.summary?.risk_level
        const fK   = v => v==null?'\u2014':Math.abs(v)>=1e6?`${v<0?'-':''}${(Math.abs(v)/1e6).toFixed(1)}M`:Math.abs(v)>=1e3?`${v<0?'-':''}${(Math.abs(v)/1e3).toFixed(0)}K`:`${v.toFixed(0)}`
        const ar   = lang === 'ar'
        const pts  = []
        if (bRev?.point) pts.push(`${ar?'إيرادات':'Rev'} ${fK(bRev.point)}`)
        if (bNp?.point)  pts.push(`${ar?'ربح':'NP'} ${fK(bNp.point)}`)
        if (!pts.length) return null
        const rClr = risk==='high'?T.red:risk==='medium'?T.amber:T.green
        return (
          <div style={{marginTop:8,padding:'7px 14px',borderRadius:8,
            background:'rgba(0,212,170,0.05)',borderLeft:'2px solid var(--accent)'}}>
            <span style={{fontSize:9,fontFamily:'var(--font-mono)',color:'var(--accent)',opacity:.8}}>
              {'\ud83d\udcc8'} {ar?'التوقعات':'Forecast'}: {pts.join(' · ')}
              {bRev?.confidence!=null&&` (${bRev.confidence}%)`}
              {risk&&<span style={{marginLeft:6,color:rClr}}> {risk}</span>}
            </span>
          </div>
        )
      })()}
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────────────────
//  AlertsBar — hover = explanation, click = panel
// ──────────────────────────────────────────────────────────────────────────────
function AlertsBar({ alerts, tr, onSelect }) {
  if (!alerts?.length) return null
  return (
    <div style={{display:'flex',alignItems:'center',gap:8,
      background:T.surface,border:`1px solid ${T.border}`,
      borderRadius:11,padding:'10px 16px',flexWrap:'wrap'}}>
      <span style={{fontSize:11,fontWeight:700,color:T.amber,flexShrink:0}}>
        ⚠ {alerts.length} {tr('alerts_title')}
      </span>
      <div style={{display:'flex',gap:6,flexWrap:'wrap',flex:1}}>
        {alerts.slice(0,4).map((a,i) => (
          <button key={i} onClick={()=>onSelect('alert',a,{})} title={a.message}
            style={{padding:'3px 10px',borderRadius:20,cursor:'pointer',fontSize:10,fontWeight:600,
              border:`1px solid ${uClr[a.severity]||T.text3}35`,
              background:`${uClr[a.severity]||T.text3}12`,
              color:uClr[a.severity]||T.text3,
              transition:'all .15s ease'}}
            onMouseEnter={e=>e.currentTarget.style.background=`${uClr[a.severity]||T.text3}25`}
            onMouseLeave={e=>e.currentTarget.style.background=`${uClr[a.severity]||T.text3}12`}>
            {a.title}
          </button>
        ))}
      </div>
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────────────────
//  Main
// ──────────────────────────────────────────────────────────────────────────────
export default function ExecutiveDashboard() {
  const { tr, lang }   = useLang()
  const { selectedId, selectedCompany } = useCompany()
  const { toQueryString: scopeQS, params: ps, window: win } = usePeriodScope()
  const ctxLabel = () => kpiContextLabel({ window: 'ALL', ps, latestPeriod: main?.intelligence?.latest_period || '', lang, tr })

  const [intel,    setIntel]    = useState(null)
  const [decs,     setDecs]     = useState(null)
  const [causes,   setCauses]   = useState(null)
  const [alerts,   setAlerts]   = useState(null)
  const [main,     setMain]     = useState(null)
  const [decSum,   setDecSum]   = useState(null)
  const [alertSum, setAlertSum] = useState(null)
  const [fcData,   setFcData]   = useState(null)
  const [loading,  setLoading]  = useState(false)
  const [consolidate, setConsolidate] = useState(false)
  const [noDataMsg, setNoDataMsg] = useState(null)

  const navigate = useNavigate()
  const [impacts, setImpacts] = useState({})
  const [pType, setPType] = useState(null)
  const [pLoad, setPLoad] = useState(null)
  const [pXtra, setPXtra] = useState(null)
  const open  = useCallback((t,p,x=null)=>{ setPType(t); setPLoad(p); setPXtra(x) },[])
  const close = useCallback(()=>{ setPType(null); setPLoad(null); setPXtra(null) },[])

  const load = useCallback(async () => {
    if (!selectedId) return
    const qs = scopeQS({ lang: lang||'en', window: win || 'ALL' }); if (qs===null) return
    const consolidateQS = consolidate ? '&consolidate=true' : ''
    setLoading(true)
    setNoDataMsg(null)
    try {
      const r = await fetch(`${API}/analysis/${selectedId}/executive?${qs}${consolidateQS}`, { headers:auth() })
      if (!r.ok) {
        if (r.status === 422) {
          setMain(null)
          setNoDataMsg(tr('err_no_financial_data'))
        }
        return
      }
      const j = await r.json(); const d = j.data||{}
      setIntel(d.intelligence||null)
      setDecs(d.decisions||[])
      setCauses(d.root_causes||[])
      setAlerts(d.alerts||[])
      setDecSum(d.decisions_summary||{})
      setAlertSum(d.alerts_summary||{})
      // Build impacts lookup: decision_key → impact object
      const impMap = {}
      ;(d.decision_impacts||[]).forEach(item => { impMap[item.decision_key||item.domain] = item })
      setImpacts(impMap)

      setMain({
        health_score_v2:     d.health_score_v2,
        kpi_block:           d.kpi_block,
        cashflow:            d.cashflow,
        statements:          d.statements || null,
        stmtInsights:        d.statements?.insights || [],
        periods:             j.meta?.periods||[],
        intelligence:        { latest_period: j.meta?.periods?.slice(-1)[0] },
        pipeline_validation: j.meta?.pipeline_validation || null,
        scope_label:         j.meta?.scope?.label || null,
      })
      // Phase 6.4: forecast fetch
      try {
        const fqs = scopeQS({ lang: lang||'en', window: win || 'ALL' })
        if (fqs !== null) {
          const fr = await fetch(`${API}/analysis/${selectedId}/forecast?${fqs}`, { headers:auth() })
          if (fr.ok) { const fj = await fr.json(); if (fj?.data) setFcData(fj.data) }
        }
      } catch (_) {}
    } catch(e) { console.error('exec:', e) }
    finally { setLoading(false) }
  }, [selectedId, lang, consolidate, win, scopeQS])

  useEffect(() => { load() }, [selectedId, load])  // scope-aware: load depends on scopeQS

  // Skeleton render while loading with no data
  if (selectedId && loading && !main) return (
    <div style={{padding:'18px 26px',display:'flex',flexDirection:'column',gap:14,
      minHeight:'calc(100vh - 62px)',background:T.bg}}>
      {/* TopBar skeleton */}
      <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:16,padding:'16px 24px',display:'flex',alignItems:'center',gap:20}}>
        <div className="skeleton" style={{width:80,height:80,borderRadius:'50%',flexShrink:0}}/>
        <div style={{flex:1}}>
          <div className="skeleton skeleton-text" style={{width:'40%',marginBottom:10}}/>
          <div className="skeleton skeleton-num" style={{width:'60%',marginBottom:8}}/>
          <div className="skeleton skeleton-text" style={{width:'30%'}}/>
        </div>
      </div>
      {/* KPI row skeleton */}
      <div style={{display:'grid',gridTemplateColumns:'repeat(5,1fr)',gap:10}}>
        {[1,2,3,4,5].map(i=>(
          <div key={i} style={{background:T.card,borderRadius:11,padding:'14px 16px',borderTop:`2px solid ${T.border}`}}>
            <div className="skeleton skeleton-text" style={{width:'60%',marginBottom:10}}/>
            <div className="skeleton skeleton-num" style={{marginBottom:8}}/>
            <div className="skeleton skeleton-text" style={{width:'45%'}}/>
          </div>
        ))}
      </div>
      {/* Action strip skeleton */}
      <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:10}}>
        {[1,2,3].map(i=>(
          <div key={i} style={{background:T.card,borderRadius:12,padding:'14px 16px',borderTop:`2px solid ${T.border}`}}>
            <div className="skeleton skeleton-text" style={{width:'40%',marginBottom:10}}/>
            <div className="skeleton skeleton-num" style={{marginBottom:8}}/>
            <div className="skeleton skeleton-text" style={{width:'80%',marginBottom:6}}/>
            <div className="skeleton skeleton-text" style={{width:'35%'}}/>
          </div>
        ))}
      </div>
    </div>
  )

  if (selectedId && noDataMsg && !main) return (
    <div style={{padding:'18px 26px',minHeight:'calc(100vh - 62px)',background:T.bg}}>
      <div style={{padding:'12px 14px',borderRadius:12,
        background:'rgba(251,191,36,0.10)',border:'1px solid rgba(251,191,36,0.25)',
        color:T.text2,fontSize:13,fontWeight:600}}>
        {noDataMsg}
      </div>
    </div>
  )

  if (!selectedId) return (
    <div style={{display:'flex',flexDirection:'column',alignItems:'center',
      justifyContent:'center',height:'70vh',gap:12,background:T.bg}}>
      <span style={{fontSize:52,opacity:.15}}>🏢</span>
      <div style={{fontSize:15,fontWeight:600,color:T.text2}}>{tr('exec_no_company')}</div>
    </div>
  )

  const health = main?.health_score_v2 ?? intel?.health_score_v2 ?? null
  const status = intel?.status ?? (health!=null ? health>=80?'excellent':health>=60?'good':health>=40?'warning':'risk' : 'neutral')
  const kpis   = main?.kpi_block?.kpis || {}
  const period = main?.intelligence?.latest_period || main?.periods?.slice(-1)[0]


  {/* ── Data Source Banner ── */}
  {main && (
    <div style={{display:'flex',alignItems:'center',gap:8,padding:'6px 12px',
      borderRadius:8,fontSize:11,marginBottom:6,
      background: consolidate ? 'rgba(0,212,170,.07)' : 'rgba(59,158,255,.07)',
      border: `1px solid ${consolidate ? 'rgba(0,212,170,.27)' : 'rgba(59,158,255,.27)'}`,
    }}>
      <span style={{fontWeight:700,color: consolidate ? 'var(--accent)' : 'var(--blue)'}}>
        {consolidate ? '⊞' : '⊟'}
      </span>
      <span style={{color: consolidate ? 'var(--accent)' : 'var(--blue)', fontWeight:600}}>
        {tr('data_source')}:
      </span>
      <span style={{color:'var(--text-secondary)'}}>
        {consolidate ? tr('branch_consolidation') : tr('company_uploads')}
      </span>
      {consolidate && (
        <span style={{marginLeft:8,padding:'2px 8px',borderRadius:4,fontSize:10,
          background:'rgba(251,191,36,.12)',color:'#fbbf24',border:'1px solid rgba(251,191,36,.25)',
          fontWeight:600}}>
          {tr('no_elimination')} · {tr('no_currency_conversion')} · {tr('simplified_consolidation')}
        </span>
      )}
    </div>
  )}
  return (
    <div className="" style={{padding:'18px 26px',display:'flex',flexDirection:'column',gap:14,
      minHeight:'calc(100vh - 62px)',background:T.bg}}>

      <style>{`
        @keyframes spin    { to   { transform:rotate(360deg) } }
        @keyframes slideIn { from { transform:translateX(100%);opacity:0 } to { transform:translateX(0);opacity:1 } }
        @keyframes fadeUp  { from { opacity:0;transform:translateY(5px) } to { opacity:1;transform:none } }
      `}</style>

      {/* FIX-4.3: Data quality banner */}
      <DataQualityBanner validation={main?.pipeline_validation} lang={lang} tr={tr}/>
      <TopBar tr={tr} health={health} status={status}
        companyName={selectedCompany?.name}
        period={period} loading={loading} onRefresh={load}
        periodCount={main?.periods?.length} scopeLabel={main?.scope_label}
        consolidate={consolidate} setConsolidate={setConsolidate}/>

      <TopFocusBanner tr={tr} decSum={decSum} alertSum={alertSum} health={health}/>

      {decs?.length>0 && <ActionStrip decisions={decs} tr={tr} causes={causes} impacts={impacts} onSelect={open}/>}

      {main && <ExecutiveKpiRow kpis={kpis} cashflow={main.cashflow||{}} main={main} tr={tr}
        alerts={alerts} onSelect={open} ctxLabel={ctxLabel}/>}

      {intel && <DomainGrid intelligence={intel} tr={tr}
        rootCauses={causes} decisions={decs} onSelect={open}/>}

      {/* Root Causes — shown only when causes exist */}
      {causes?.length>0 && <RootCausesStrip causes={causes} tr={tr} onSelect={open}/>}

      <KeyInsightsStrip stmtInsights={main?.stmtInsights} decisions={decs} fcData={fcData} lang={lang}/>

      <AlertsBar alerts={alerts} tr={tr} onSelect={open}/>

      {pType && <ContextPanel type={pType} payload={pLoad} extra={pXtra} impacts={impacts}
        tr={tr} onClose={close}
        onNavigate={()=>navigate('/analysis',{state:{focus:pLoad?.domain||pLoad?.type||'overview'}})}/>}
    </div>
  )
}
