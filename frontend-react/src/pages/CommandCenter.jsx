/**
 * CommandCenter.jsx — Flagship interface (Dashboard + Executive merged)
 *
 * Backbone: ExecutiveDashboard blocks (no API/model changes)
 * Additions:
 * - Explicit Forecast summary in "What Matters Now"
 * - Branch Performance aligned with same lang/window/scope query semantics
 * - Lightweight Command Navigation at bottom (drill-down launcher only)
 */
import { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLang }        from '../context/LangContext.jsx'
import { useCompany }     from '../context/CompanyContext.jsx'
import { usePeriodScope } from '../context/PeriodScopeContext.jsx'
import { kpiContextLabel, kpiLabel } from '../utils/kpiContext.js'
import { formatCompact, formatFull } from '../utils/numberFormat.js'
import { buildAnalysisQuery } from '../utils/buildAnalysisQuery.js'
import PeriodSelector from '../components/PeriodSelector.jsx'
import UniversalScopeSelector from '../components/UniversalScopeSelector.jsx'

const API = '/api/v1'
function auth() {
  try { const t=JSON.parse(localStorage.getItem('vcfo_auth')||'{}').token; return t?{Authorization:`Bearer ${t}`}:{} }
  catch { return {} }
}

// ── Design tokens (match ExecutiveDashboard) ───────────────────────────────────
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
const fmtP = v => v==null?'—':`${Number(v).toFixed(1)}%`

const Pill = ({label, color}) => (
  <span style={{fontSize:9,fontWeight:800,padding:'2px 9px',borderRadius:20,
    background:`${color}18`,color,border:`1px solid ${color}30`,
    textTransform:'uppercase',letterSpacing:'.05em',flexShrink:0,whiteSpace:'nowrap'}}>
    {label}
  </span>
)
const lift = color => ({
  onMouseEnter: e => { e.currentTarget.style.transform='translateY(-2px)'; e.currentTarget.style.boxShadow=`0 10px 32px rgba(0,0,0,.55),0 0 0 1px ${color}30` },
  onMouseLeave: e => { e.currentTarget.style.transform=''; e.currentTarget.style.boxShadow='' },
})

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
      {warnings.map((w,i)=>(
        <span key={i} style={{fontSize:9,color:'rgba(255,255,255,0.5)'}}>· {tr(`dq_${w.code}`)}</span>
      ))}
    </div>
  )
}

function TopBar({ tr, health, status, companyName, period, loading, onRefresh, periodCount, scopeLabel }) {
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
          <div style={{width:7,height:7,borderRadius:'50%',background:hc,boxShadow:`0 0 8px ${hc}`}}/>
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
//  ContextPanel — drill context drawer
//  Minimal fix: CommandCenter references this panel on click.
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
      <div onClick={onClose} style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.5)',zIndex:998}}/>
      <div style={{position:'fixed',top:0,right:0,bottom:0,width:460,
        background:T.panel,borderLeft:`1px solid ${T.border}`,
        zIndex:999,display:'flex',flexDirection:'column',
        boxShadow:'-24px 0 80px rgba(0,0,0,0.75)',
        animation:'slideIn .22s cubic-bezier(.4,0,.2,1)'}}>
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
        <div style={{flex:1,overflowY:'auto',padding:'22px 22px'}}>
          {type==='decision' && <Decision/>}
          {type==='kpi'      && <Kpi/>}
          {type==='domain'   && <Domain/>}
          {type==='alert'    && <Alert/>}
        </div>
        {!!onNavigate && (
          <div style={{padding:'12px 22px',borderTop:`1px solid ${T.border}`,background:T.surface}}>
            <button onClick={onNavigate} style={{width:'100%',padding:'10px 12px',borderRadius:10,
              border:`1px solid ${T.border}`,background:'transparent',color:T.text1,
              fontSize:12,fontWeight:800,cursor:'pointer'}}>
              {tr('open_analysis') || tr('nav_analysis') || tr('analysis')}
            </button>
          </div>
        )}
      </div>
    </>
  )
}

function ActionStrip({ decisions, tr, onSelect, causes, impacts={} }) {
  if (!decisions?.length) return null
  return (
    <div>
      <div style={{fontSize:10,fontWeight:700,color:T.text3,textTransform:'uppercase',
        letterSpacing:'.08em',marginBottom:10}}>{tr('exec_action_strip')}</div>
      {/* Visual hierarchy: #1 dominant, #2 medium, #3 smaller */}
      <div style={{display:'grid',gridTemplateColumns:'2fr 1.15fr 0.95fr',gap:10,alignItems:'stretch'}}>
        {decisions.slice(0,3).map((dec,i) => {
          const uc    = uClr[dec.urgency]||T.text3
          const isTop = i === 0
          const isMid = i === 1
          const shortTitle = tr(`dec_short_${dec.domain}`)||dec.title
          const hint       = dec.reason?.split('. ')[0]||''
          const linkedC    = causes?.filter(c=>c.domain===dec.domain||c.domain==='cross_domain')||[]
          return (
            <div key={dec.key||i}
              onClick={()=>onSelect('decision', dec, {causes:linkedC})}
              title={hint}
              style={{
                gridColumn: isTop ? '1 / span 1' : 'auto',
                background: isTop
                  ? `linear-gradient(135deg,${T.card},rgba(0,212,170,0.10))`
                  : isMid
                    ? `linear-gradient(135deg,${T.card},rgba(124,92,252,0.06))`
                    : T.card,
                borderWidth:'1px',borderStyle:'solid',
                borderColor:isTop?`${T.accent}40`:isMid?`${T.violet}26`:T.border,
                borderTopWidth:isTop?4:3,borderTopColor:uc,borderRadius:14,
                padding:isTop?'18px 18px':isMid?'16px 16px':'14px 14px',
                cursor:'pointer',
                minHeight:isTop?120:isMid?102:92,
                transition:'transform .15s ease,box-shadow .15s ease'}}
              {...lift(uc)}>
              <div style={{display:'flex',alignItems:'center',gap:7,marginBottom:9}}>
                <span style={{fontSize:isTop?18:14}}>{dIco[dec.domain]||'◉'}</span>
                <Pill label={tr(`urgency_${dec.urgency}`)||dec.urgency} color={uc}/>
                {isTop && <span style={{marginLeft:'auto',fontSize:9,color:T.accent,fontWeight:800}}>#1</span>}
                {isMid && <span style={{marginLeft:'auto',fontSize:9,color:T.violet,fontWeight:800}}>#2</span>}
              </div>
              <div style={{fontSize:isTop?16:isMid?14:13,fontWeight:900,color:T.text1,lineHeight:1.25,marginBottom:6}}>
                {shortTitle}
              </div>
              {(()=>{
                const impKey = dec.key||dec.domain
                const imp = impacts[impKey]?.impact || impacts[dec.domain]?.impact
                if (imp?.value!=null) return (
                  <div style={{display:'inline-flex',alignItems:'center',gap:4,
                    background:`${uc}15`,border:`1px solid ${uc}30`,borderRadius:20,
                    padding:isTop?'3px 10px':'2px 8px',marginBottom:8,width:'fit-content'}}>
                    <span style={{fontSize:isTop?13:11,fontWeight:900,color:uc,fontFamily:'monospace'}}>
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
              <div style={{fontSize:10,color:T.text2,lineHeight:1.4,marginBottom:9,
                display:'-webkit-box',WebkitLineClamp:isTop?2:1,WebkitBoxOrient:'vertical',overflow:'hidden'}}>
                {hint}
              </div>
              <div style={{fontSize:isTop?11:10,color:T.text2,fontFamily:'monospace'}}>⏱ {dec.timeframe}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ExecutiveKpiRow({ kpis, cashflow, main, tr, onSelect, alerts, ctxLabel }) {
  const cfEstimated = cashflow?.reliability === 'estimated'
  const wc       = kpis.working_capital?.value
             ?? cashflow?.working_capital
             ?? main?.statements?.balance_sheet?.working_capital
  const wcColor  = wc==null?T.text3:wc>=0?T.green:T.red
  const heroKey = 'net_profit'
  const cards = [
    { key:'revenue',         value:formatCompact(kpis.revenue?.value),        full:formatFull(kpis.revenue?.value),        mom:kpis.revenue?.mom_pct,    yoy:kpis.revenue?.yoy_pct,    color:T.accent,  icon:'📈' },
    { key:'net_profit',      value:formatCompact(kpis.net_profit?.value),      full:formatFull(kpis.net_profit?.value),      mom:kpis.net_profit?.mom_pct, yoy:kpis.net_profit?.yoy_pct, color:T.green,   icon:'💰' },
    { key:'cashflow',        value:formatCompact(cashflow?.operating_cashflow), full:formatFull(cashflow?.operating_cashflow), mom:cashflow?.operating_cashflow_mom, yoy:null, color:T.blue,   icon:'💧', estimated:cfEstimated },
    { key:'net_margin',      value:fmtP(kpis.net_margin?.value),               full:null,                                    mom:kpis.net_margin?.mom_pct, yoy:null,                     color:T.violet,  icon:'%'  },
    { key:'working_capital', value:formatCompact(wc),                           full:formatFull(wc),                          mom:null,                     yoy:null, sub:wc!=null&&wc<0?tr('wc_negative'):null, color:wcColor, icon:'⚖️' },
  ]
  const ordered = [
    ...cards.filter(c=>c.key===heroKey),
    ...cards.filter(c=>c.key!==heroKey),
  ]
  const hero = ordered[0]
  const secondary = ordered.slice(1)

  const renderCard = (c, { isHero }) => {
    const mc = c.mom==null?T.text3:c.mom>0?T.green:c.mom<0?T.red:T.text2
    const explain = tr(`kpi_explain_${c.key}`)
    return (
      <div key={c.key}
        onClick={()=>onSelect('kpi',{type:c.key,mom:c.mom,yoy:c.yoy},
          {alerts:alerts?.filter(a=>a.impact==='profitability')||[], explanation:explain})}
        title={explain}
        style={{
          background: isHero ? `linear-gradient(135deg,${T.card},${c.color}14)` : T.card,
          borderWidth:'1px',borderStyle:'solid',borderColor:isHero?`${c.color}35`:T.border,
          borderTopWidth:isHero?4:2,borderTopColor:c.color,borderRadius:14,
          padding:isHero?'18px 18px':'14px 16px',
          cursor:'pointer',
          transition:'transform 0.2s cubic-bezier(0.4,0,0.2,1), box-shadow 0.2s ease, border-color 0.2s ease',
        }}
        {...lift(c.color)}>
        <div style={{display:'flex',alignItems:'center',gap:7,marginBottom:isHero?10:8}}>
          <span style={{fontSize:isHero?18:12}}>{c.icon}</span>
          <span style={{fontSize:isHero?11:10,color:T.text2,fontWeight:800,textTransform:'uppercase',
            letterSpacing:'.06em'}}>
            {kpiLabel(tr(`kpi_label_${c.key}`)||c.key, ctxLabel(), tr)}
          </span>
          {isHero && (
            <span style={{marginLeft:'auto',fontSize:9,fontWeight:900,color:c.color,letterSpacing:'.10em',textTransform:'uppercase'}}>
              {tr('primary')}
            </span>
          )}
        </div>
        <div style={{fontFamily:'var(--font-display)',fontSize:isHero?30:22,fontWeight:900,color:'#ffffff',
          marginBottom:3,direction:'ltr',letterSpacing:'-0.025em',lineHeight:1}}>
          {c.value}
        </div>
        {c.full && (
          <div style={{fontFamily:'var(--font-mono)',fontSize:9,color:T.text3,marginBottom:4,letterSpacing:'.02em',direction:'ltr'}}>
            {c.full}
          </div>
        )}
        <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
          {c.mom!=null && (
            <span style={{fontFamily:'var(--font-mono)',fontSize:10,fontWeight:700,color:mc,
              padding:'1px 6px',borderRadius:8,background:`${mc}14`}}>
              {c.mom>0?'+':''}{c.mom?.toFixed(1)}% MoM
            </span>
          )}
          {c.yoy!=null && (
            <span style={{fontFamily:'monospace',fontSize:10,
              color:c.yoy>0?T.green:c.yoy<0?T.red:T.text2}}>
              {c.yoy>0?'+':''}{c.yoy?.toFixed(1)}% YoY
            </span>
          )}
        </div>
        {c.estimated && (
          <div style={{marginTop:6,fontSize:9,color:'#f59e0b',
            padding:'2px 7px',borderRadius:5,background:'rgba(245,158,11,0.1)',
            border:'1px solid rgba(245,158,11,0.25)',display:'inline-block'}}>
            ⚠ {tr('estimated')}
          </div>
        )}
        {c.sub && <div style={{marginTop:4,fontSize:10,color:T.text3}}>{c.sub}</div>}
      </div>
    )
  }

  return (
    <div>
      <div style={{fontSize:10,fontWeight:700,color:T.text3,textTransform:'uppercase',
        letterSpacing:'.08em',marginBottom:10}}>{tr('exec_kpi_title')}</div>
      {/* Hero KPI + secondary KPIs (avoid equal weight) */}
      <div style={{display:'grid',gridTemplateColumns:'1.25fr 1fr',gap:14,alignItems:'stretch'}}>
        <div style={{minWidth:0}}>
          {hero ? renderCard(hero, { isHero:true }) : null}
        </div>
        <div style={{minWidth:0,display:'grid',gridTemplateColumns:'repeat(2,1fr)',gap:12}}>
          {secondary.map(c => renderCard(c, { isHero:false }))}
        </div>
      </div>
    </div>
  )
}

function DomainGrid({ intelligence, tr, onSelect, rootCauses, decisions, alerts }) {
  const ratios  = intelligence?.ratios  || {}
  const trends  = intelligence?.trends  || {}
  const scoreFromCategory = (cat) => {
    if (!cat) return 50
    const s2  = {good:100,neutral:60,warning:35,risk:10}
    const vs  = Object.values(cat).map(v=>s2[v?.status]||50).filter(v=>Number.isFinite(v))
    if (!vs.length) return 50
    return Math.round(vs.reduce((a,b)=>a+b,0)/vs.length)
  }
  const score = d => scoreFromCategory(ratios[d])
  const riskScore = () => {
    // Risk = leverage posture + alert pressure (no new backend fields)
    const lev = score('leverage')
    const hi  = (alerts||[]).filter(a=>a.severity==='high').length
    const med = (alerts||[]).filter(a=>a.severity==='medium').length
    const penalty = Math.min(30, hi*12 + med*5)
    return Math.max(0, Math.min(100, Math.round(lev - penalty)))
  }
  const blocks = [
    { id:'profitability', label: tr('profitability') || tr('domain_profitability_simple'), color: dClr.profitability, icon:'📈', score: score('profitability'), ratiosKey:'profitability', navigateDomain:'profitability' },
    { id:'liquidity',     label: tr('liquidity')     || tr('domain_liquidity_simple'),     color: dClr.liquidity,     icon:'💧', score: score('liquidity'),     ratiosKey:'liquidity',     navigateDomain:'liquidity' },
    { id:'efficiency',    label: tr('efficiency')    || tr('domain_efficiency_simple'),    color: dClr.efficiency,    icon:'⚡', score: score('efficiency'),    ratiosKey:'efficiency',    navigateDomain:'efficiency' },
    { id:'risk',          label: tr('risk_level')    || tr('domain_leverage_simple'),      color: T.red,              icon:'🛡', score: riskScore(),            ratiosKey:'leverage',      navigateDomain:'leverage' },
  ]
  const ratioMap = key => ratios[key] || {}
  return (
    <div>
      <div style={{fontSize:10,fontWeight:700,color:T.text3,textTransform:'uppercase',
        letterSpacing:'.08em',marginBottom:10}}>{tr('exec_domain_title')}</div>
      <div style={{display:'grid',gridTemplateColumns:'repeat(12,1fr)',gap:10}}>
        {blocks.map((b, idx) => {
          const s   = b.score
          const dc  = b.color || T.accent
          const st  = s>=70?'good':s>=45?'warning':'risk'
          const sc  = stC[st]
          const sig = b.id==='risk'
            ? (s>=70?tr('risk_low'):s>=45?tr('risk_medium'):tr('risk_high'))
            : (s>=70 ? tr(`domain_signal_${b.navigateDomain}_good`)
                     : s>=45 ? tr(`domain_signal_${b.navigateDomain}_warn`)
                             : tr(`domain_signal_${b.navigateDomain}_risk`))
          return (
            <div key={b.id}
              onClick={()=>onSelect('domain',{domain:b.navigateDomain,score:s,status:st,ratios:ratioMap(b.ratiosKey)},{causes:rootCauses,decisions})}
              title={b.id==='risk' ? tr('alerts_title') : (tr(`domain_${b.navigateDomain}_exp`)||'')}
              style={{
                gridColumn: idx===0 ? 'span 4' : 'span 4',
                background: `linear-gradient(135deg,${T.card},${dc}0a)`,
                borderWidth:'1px',borderStyle:'solid',borderColor:`${dc}28`,
                borderTopWidth:4,borderTopColor:dc,borderRadius:15,
                padding:'16px 16px',cursor:'pointer',
                transition:'transform .15s ease,box-shadow .15s ease'}}
              {...lift(dc)}>
              <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:10,marginBottom:12}}>
                <div style={{display:'flex',alignItems:'center',gap:8,minWidth:0}}>
                  <span style={{fontSize:18}}>{b.icon}</span>
                  <div style={{minWidth:0}}>
                    <div style={{fontSize:11,fontWeight:900,color:dc,textTransform:'uppercase',letterSpacing:'.08em',whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>
                      {b.label}
                    </div>
                    <div style={{fontSize:10,color:T.text2,marginTop:2,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>
                      {sig || tr(`status_${st}_simple`) || st}
                    </div>
                  </div>
                </div>
                <div style={{textAlign:'right',flexShrink:0}}>
                  <div style={{fontFamily:'monospace',fontSize:22,fontWeight:900,color:dc,lineHeight:1,direction:'ltr'}}>{s}</div>
                  <div style={{fontSize:9,color:T.text3}}>/100</div>
                </div>
              </div>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8}}>
                {Object.entries(ratioMap(b.ratiosKey)).slice(0,4).map(([k,r]) => {
                  const rc = {good:T.green,warning:T.amber,risk:T.red,neutral:T.text2}[r?.status]||T.text2
                  return (
                    <div key={k} style={{background:`${dc}08`,borderRadius:10,padding:'10px 10px',
                      borderWidth:'1px 1px 1px 2px',borderStyle:'solid',borderColor:`${T.border} ${T.border} ${T.border} ${rc}`}}>
                      <div style={{fontSize:8,color:T.text3,textTransform:'uppercase',letterSpacing:'.08em',marginBottom:3}}>
                        {tr(`ratio_${k}`)||k.replace(/_/g,' ')}
                      </div>
                      <div style={{fontFamily:'monospace',fontSize:12,fontWeight:800,color:rc,direction:'ltr'}}>
                        {r?.value!=null?r.value:'—'}
                        <span style={{fontSize:9,color:T.text3,marginLeft:3}}>{r?.unit||''}</span>
                      </div>
                    </div>
                  )
                })}
                {b.id==='risk' && (
                  <div style={{gridColumn:'1 / -1',background:`${T.red}08`,border:`1px solid ${T.red}20`,borderRadius:10,padding:'10px 12px'}}>
                    <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:10}}>
                      <div style={{fontSize:9,fontWeight:900,color:T.red,textTransform:'uppercase',letterSpacing:'.08em'}}>
                        {tr('alerts_title')}
                      </div>
                      <div style={{fontFamily:'monospace',fontSize:12,fontWeight:900,color:T.red,direction:'ltr'}}>
                        {(alerts||[]).length ?? 0}
                      </div>
                    </div>
                    <div style={{marginTop:6,display:'flex',gap:6,flexWrap:'wrap'}}>
                      {['high','medium','low'].map(sev => {
                        const n = (alerts||[]).filter(a=>a.severity===sev).length
                        if (!n) return null
                        const c = uClr[sev]||T.text3
                        return <Pill key={sev} label={`${n} ${tr(`urgency_${sev}`)||sev}`} color={c}/>
                      })}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

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
              color:uClr[a.severity]||T.text3,transition:'all .15s ease'}}
            onMouseEnter={e=>e.currentTarget.style.background=`${uClr[a.severity]||T.text3}25`}
            onMouseLeave={e=>e.currentTarget.style.background=`${uClr[a.severity]||T.text3}12`}>
            {a.title}
          </button>
        ))}
      </div>
    </div>
  )
}

function ForecastNow({ fcData, tr }) {
  if (!fcData?.available) return null
  const bRev = fcData?.scenarios?.base?.revenue?.[0]
  const bNp  = fcData?.scenarios?.base?.net_profit?.[0]
  const risk = fcData?.summary?.risk_level
  if (!bRev?.point && !bNp?.point) return null
  const riskClr = risk==='high'?T.red:risk==='medium'?T.amber:risk?T.green:T.text3
  return (
    <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:12,padding:'12px 16px'}}>
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:10,marginBottom:8}}>
        <div style={{fontSize:10,fontWeight:800,color:T.text3,textTransform:'uppercase',letterSpacing:'.08em'}}>
          {tr('forecast_next_period')}
        </div>
        {risk && <Pill label={`${tr('forecast_risk')}: ${risk}`} color={riskClr}/>}
      </div>
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10}}>
        <div style={{background:T.card,border:`1px solid ${T.border}`,borderRadius:10,padding:'10px 12px'}}>
          <div style={{fontSize:9,color:T.text3,textTransform:'uppercase',letterSpacing:'.08em',marginBottom:4}}>{tr('revenue')}</div>
          <div style={{fontFamily:'monospace',fontSize:16,fontWeight:800,color:T.accent,direction:'ltr'}}>
            {bRev?.point!=null?formatCompact(bRev.point):'—'}
          </div>
          {bRev?.confidence!=null&&<div style={{fontSize:9,color:T.text3,marginTop:2}}>{tr('fc_confidence')}: {bRev.confidence}%</div>}
        </div>
        <div style={{background:T.card,border:`1px solid ${T.border}`,borderRadius:10,padding:'10px 12px'}}>
          <div style={{fontSize:9,color:T.text3,textTransform:'uppercase',letterSpacing:'.08em',marginBottom:4}}>{tr('net_profit')}</div>
          <div style={{fontFamily:'monospace',fontSize:16,fontWeight:800,color:T.green,direction:'ltr'}}>
            {bNp?.point!=null?formatCompact(bNp.point):'—'}
          </div>
          {bNp?.confidence!=null&&<div style={{fontSize:9,color:T.text3,marginTop:2}}>{tr('fc_confidence')}: {bNp.confidence}%</div>}
        </div>
      </div>
    </div>
  )
}

function BranchPerformance({ companyId, qs, tr }) {
  const [d,setD]=useState(null)
  useEffect(()=>{
    if (!companyId || !qs) return
    // Align with flagship semantics: same scope QS (lang + window + custom period scope)
    fetch(`${API}/companies/${companyId}/branch-comparison?${qs}`, { headers: auth() })
      .then(r=>r.ok?r.json():null)
      .then(j=>{ if(j) setD(j) })
      .catch(()=>{})
  },[companyId, qs])

  if (!d) return (
    <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:12,padding:'14px 16px'}}>
      <div style={{height:22,display:'flex',alignItems:'center',gap:10}}>
        <div style={{width:14,height:14,border:`2px solid ${T.border}`,borderTopColor:T.accent,borderRadius:'50%',animation:'spin .8s linear infinite'}}/>
        <span style={{fontSize:11,color:T.text2}}>{tr('loading')}</span>
      </div>
    </div>
  )
  if (!d.has_data) return (
    <div style={{background:T.surface,border:`1px dashed ${T.border}`,borderRadius:12,padding:'18px 16px',textAlign:'center'}}>
      <div style={{fontSize:11,fontWeight:700,color:T.accent,marginBottom:8,letterSpacing:'.04em'}}>
        {tr('data_source_branch_view_label')}
      </div>
      <div style={{fontSize:26,marginBottom:6,opacity:.3}}>🏢</div>
      <div style={{fontSize:12,fontWeight:700,color:T.text2,marginBottom:4}}>{tr('branches_config')}</div>
      <div style={{fontSize:11,color:T.text3}}>{tr('branches_hint')}</div>
    </div>
  )
  const ranking = (d.ranking||[]).slice()
  const topBranch = ranking[0] || null
  const weakBranch = ranking.length ? ranking[ranking.length-1] : null
  const top = ranking.slice(0,5)
  return (
    <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:12,padding:'14px 16px'}}>
      <div style={{marginBottom:10}}>
        <div style={{display:'flex',alignItems:'center',gap:8,flexWrap:'wrap',marginBottom:6}}>
          <span style={{fontSize:11,fontWeight:800,color:T.accent,letterSpacing:'.06em'}}>
            {tr('data_source_branch_view_label')}
          </span>
          <span
            title={tr('data_source_branch_vs_company_note')}
            aria-label={tr('data_source_branch_vs_company_note')}
            style={{cursor:'help',fontSize:12,color:T.text3}}>
            ℹ️
          </span>
        </div>
        <div style={{fontSize:10,color:T.text3,lineHeight:1.45,marginBottom:8}}>
          {tr('data_source_branch_vs_company_note')}
        </div>
        <div style={{display:'flex',alignItems:'baseline',justifyContent:'space-between',gap:10}}>
          <div style={{fontSize:10,fontWeight:800,color:T.text3,textTransform:'uppercase',letterSpacing:'.08em'}}>
            {tr('branch_performance')}
          </div>
          <div style={{fontSize:10,color:T.text3,fontFamily:'monospace'}}>{tr('window_label')}: {d.window||''}</div>
        </div>
      </div>
      {(topBranch || weakBranch) && (
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10,marginBottom:12}}>
          {topBranch && (
            <div style={{background:`linear-gradient(135deg,${T.card},rgba(52,211,153,0.10))`,
              border:`1px solid rgba(52,211,153,0.25)`,borderTop:`4px solid ${T.green}`,
              borderRadius:13,padding:'12px 12px'}}>
              <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:10,marginBottom:6}}>
                <div style={{fontSize:9,fontWeight:900,color:T.green,textTransform:'uppercase',letterSpacing:'.1em'}}>
                  {tr('best_branch') || tr('best_performing_branch') || tr('best')}
                </div>
                <span style={{fontSize:12,opacity:.9}}>🏆</span>
              </div>
              <div style={{fontSize:14,fontWeight:900,color:T.text1,marginBottom:4,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>
                {topBranch.branch_name}
              </div>
              <div style={{display:'flex',alignItems:'baseline',justifyContent:'space-between',gap:10}}>
                <div style={{fontFamily:'monospace',fontSize:16,fontWeight:900,color:T.accent,direction:'ltr'}}>
                  {formatCompact(topBranch.revenue)}
                </div>
                {topBranch.net_margin!=null && (
                  <div style={{fontFamily:'monospace',fontSize:12,fontWeight:900,color:(topBranch.net_margin>=0?T.green:T.red),direction:'ltr'}}>
                    {fmtP(topBranch.net_margin)}
                  </div>
                )}
              </div>
            </div>
          )}
          {weakBranch && (
            <div style={{background:`linear-gradient(135deg,${T.card},rgba(248,113,113,0.10))`,
              border:`1px solid rgba(248,113,113,0.25)`,borderTop:`4px solid ${T.red}`,
              borderRadius:13,padding:'12px 12px'}}>
              <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:10,marginBottom:6}}>
                <div style={{fontSize:9,fontWeight:900,color:T.red,textTransform:'uppercase',letterSpacing:'.1em'}}>
                  {tr('worst_branch') || tr('weakest_branch') || tr('weakest')}
                </div>
                <span style={{fontSize:12,opacity:.9}}>⚠</span>
              </div>
              <div style={{fontSize:14,fontWeight:900,color:T.text1,marginBottom:4,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>
                {weakBranch.branch_name}
              </div>
              <div style={{display:'flex',alignItems:'baseline',justifyContent:'space-between',gap:10}}>
                <div style={{fontFamily:'monospace',fontSize:16,fontWeight:900,color:T.accent,direction:'ltr'}}>
                  {formatCompact(weakBranch.revenue)}
                </div>
                {weakBranch.net_margin!=null && (
                  <div style={{fontFamily:'monospace',fontSize:12,fontWeight:900,color:(weakBranch.net_margin>=0?T.green:T.red),direction:'ltr'}}>
                    {fmtP(weakBranch.net_margin)}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
      <div>
        {top.map((b,i)=>(
          <div key={b.branch_id||i} style={{display:'flex',alignItems:'center',gap:10,padding:'8px 0',borderBottom:i<top.length-1?`1px solid ${T.border}`:'none'}}>
            <span style={{width:20,height:20,borderRadius:6,background:i===0?`${T.accent}20`:T.card,
              border:`1px solid ${i===0?T.accent:T.border}`,display:'flex',alignItems:'center',justifyContent:'center',
              fontSize:9,fontWeight:800,color:i===0?T.accent:T.text2,flexShrink:0}}>{i+1}</span>
            <div style={{flex:1,minWidth:0}}>
              <div style={{fontSize:12,fontWeight:700,color:T.text1,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{b.branch_name}</div>
              {b.city&&<div style={{fontSize:10,color:T.text3}}>{b.city}</div>}
            </div>
            <div style={{textAlign:'right',flexShrink:0}}>
              <div style={{fontSize:12,fontWeight:800,fontFamily:'monospace',color:T.accent,direction:'ltr'}}>{formatCompact(b.revenue)}</div>
              {b.net_margin!=null&&<div style={{fontSize:9,color:(b.net_margin>=0?T.green:T.red),fontFamily:'monospace',direction:'ltr'}}>{fmtP(b.net_margin)}</div>}
            </div>
            {b.mom_revenue_pct!=null&&(
              <span style={{fontSize:10,fontWeight:700,color:(b.mom_revenue_pct>0?T.green:b.mom_revenue_pct<0?T.red:T.text2),minWidth:44,textAlign:'right',direction:'ltr'}}>
                {b.mom_revenue_pct>0?'▲':b.mom_revenue_pct<0?'▼':'─'}{Math.abs(b.mom_revenue_pct).toFixed(1)}%
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function CommandNav({ tr, navigate }) {
  const links = [
    { to:'/analysis', label: tr('nav_analysis') },
    { to:'/statements', label: tr('nav_statements') },
    { to:'/branches', label: tr('nav_branches') },
    { to:'/board-report', label: tr('nav_board_report') },
    { to:'/upload', label: tr('nav_upload') },
  ]
  return (
    <div style={{marginTop:8,paddingTop:14,borderTop:`1px solid ${T.border}`}}>
      <div style={{fontSize:9,fontWeight:800,color:T.text3,textTransform:'uppercase',letterSpacing:'.12em',marginBottom:8}}>
        {tr('navigation')}
      </div>
      <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
        {links.map(l=>(
          <button key={l.to} onClick={()=>navigate(l.to)}
            style={{padding:'6px 10px',borderRadius:999,border:`1px solid ${T.border}`,
              background:'transparent',color:T.text2,fontSize:11,fontWeight:700,cursor:'pointer',
              opacity:.85,transition:'opacity .15s, border-color .15s'}}>
            {l.label}
          </button>
        ))}
      </div>
    </div>
  )
}

export default function CommandCenter() {
  const { tr, lang }   = useLang()
  const { selectedId, selectedCompany } = useCompany()
  const { toQueryString: scopeQS, params: ps, update: psUpdate, setResolved: psSetResolved,
    getActiveLabel: psActiveLabel, isIncompleteCustom: psIncomplete, window: win, setWindow: setWin } = usePeriodScope()
  const navigate = useNavigate()

  const ctxLabel = () => kpiContextLabel({ window: win, ps, latestPeriod: main?.intelligence?.latest_period || '', lang, tr })

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

  const [impacts, setImpacts] = useState({})
  const [pType, setPType] = useState(null)
  const [pLoad, setPLoad] = useState(null)
  const [pXtra, setPXtra] = useState(null)
  const open  = useCallback((t,p,x=null)=>{ setPType(t); setPLoad(p); setPXtra(x) },[])
  const close = useCallback(()=>{ setPType(null); setPLoad(null); setPXtra(null) },[])

  const load = useCallback(async () => {
    if (!selectedId) return
    if (psIncomplete()) return
    const qs = buildAnalysisQuery(scopeQS, { lang, window: win, consolidate })
    if (qs === null) return
    setLoading(true)
    setNoDataMsg(null)
    try {
      const r = await fetch(`${API}/analysis/${selectedId}/executive?${qs}`, { headers:auth() })
      if (!r.ok) {
        if (r.status === 422) {
          setMain(null)
          setNoDataMsg(tr('err_no_financial_data'))
        }
        return
      }
      const j = await r.json(); const d = j.data||{}
      psSetResolved(j.meta?.scope || null)
      setIntel(d.intelligence||null)
      setDecs(d.decisions||[])
      setCauses(d.root_causes||[])
      setAlerts(d.alerts||[])
      setDecSum(d.decisions_summary||{})
      setAlertSum(d.alerts_summary||{})
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
        all_periods:         j.meta?.all_periods || [],
      })
      try {
        const fqs = buildAnalysisQuery(scopeQS, { lang, window: win, consolidate: false })
        if (fqs !== null) {
          const fr = await fetch(`${API}/analysis/${selectedId}/forecast?${fqs}`, { headers:auth() })
          if (fr.ok) { const fj = await fr.json(); if (fj?.data) setFcData(fj.data) }
        }
      } catch (_) {}
    } finally {
      setLoading(false)
    }
  }, [selectedId, lang, consolidate, win, scopeQS, tr, psIncomplete, psSetResolved])

  useEffect(() => { load() }, [selectedId, win, consolidate])

  if (!selectedId) {
    return (
      <div style={{display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',height:'70vh',gap:12,background:T.bg}}>
        <span style={{fontSize:52,opacity:.15}}>🏢</span>
        <div style={{fontSize:15,fontWeight:600,color:T.text2}}>{tr('exec_no_company')}</div>
      </div>
    )
  }

  if (selectedId && noDataMsg && !main) {
    return (
      <div style={{padding:'18px 26px',minHeight:'calc(100vh - 62px)',background:T.bg}}>
        <div style={{padding:'12px 14px',borderRadius:12,
          background:'rgba(251,191,36,0.10)',border:'1px solid rgba(251,191,36,0.25)',
          color:T.text2,fontSize:13,fontWeight:600}}>
          {noDataMsg}
        </div>
      </div>
    )
  }

  const health = main?.health_score_v2 ?? intel?.health_score_v2 ?? null
  const status = intel?.status ?? (health!=null ? health>=80?'excellent':health>=60?'good':health>=40?'warning':'risk' : 'neutral')
  const kpis   = main?.kpi_block?.kpis || {}
  const period = main?.intelligence?.latest_period || main?.periods?.slice(-1)[0]

  const qs = buildAnalysisQuery(scopeQS, { lang, window: win })

  return (
    <div style={{padding:'18px 26px',display:'flex',flexDirection:'column',gap:14,minHeight:'calc(100vh - 62px)',background:T.bg}}>
      <style>{`
        @keyframes spin { to { transform:rotate(360deg) } }
        @keyframes slideIn { from { transform:translateX(100%);opacity:0 } to { transform:translateX(0);opacity:1 } }
        @keyframes fadeUp { from { opacity:0;transform:translateY(5px) } to { opacity:1;transform:none } }
      `}</style>

      {/* 1) Data quality + scope + period (before health / KPI strip) */}
      <DataQualityBanner validation={main?.pipeline_validation} lang={lang} tr={tr}/>
      <div style={{display:'flex',flexDirection:'column',gap:8}}>
        <UniversalScopeSelector tr={tr} ps={ps} psUpdate={psUpdate} onApply={load}
          activeLabel={psActiveLabel()} allPeriods={main?.all_periods||[]}/>
        <div style={{display:'flex',alignItems:'center',gap:12,flexWrap:'wrap'}}>
          <PeriodSelector window={win} setWindow={setWin} disabled={loading}/>
          <div style={{display:'flex',alignItems:'center',gap:0,background:T.card,
            border:`1px solid ${T.border}`,borderRadius:8,overflow:'hidden',flexShrink:0}}>
            {[{v:false,l:tr('company_uploads')},{v:true,l:tr('branch_consolidation')}].map(opt=>(
              <button key={String(opt.v)} type="button" onClick={()=>setConsolidate(opt.v)}
                style={{padding:'5px 12px',fontSize:11,fontWeight:600,border:'none',cursor:'pointer',
                  background: consolidate===opt.v ? T.accent : 'transparent',
                  color:      consolidate===opt.v ? '#000' : T.text2,
                  transition: 'all .15s', whiteSpace:'nowrap'}}>
                {opt.l}
              </button>
            ))}
          </div>
          {loading&&<div style={{width:14,height:14,border:`2px solid ${T.border}`,borderTopColor:T.accent,borderRadius:'50%',animation:'spin .8s linear infinite'}}/>}
        </div>
      </div>

      <div style={{padding:'8px 14px',borderRadius:10,border:`1px solid ${T.accent}35`,
        background:`${T.accent}0f`,fontSize:12,fontWeight:700,color:T.accent,letterSpacing:'.02em'}}>
        {tr('data_source_company_view_label')}
      </div>

      {/* 2) Executive Health + KPI Strip */}
      <TopBar tr={tr} health={health} status={status}
        companyName={selectedCompany?.name}
        period={period} loading={loading} onRefresh={load}
        periodCount={main?.periods?.length} scopeLabel={main?.scope_label}/>
      {main && <ExecutiveKpiRow kpis={kpis} cashflow={main.cashflow||{}} main={main} tr={tr}
        alerts={alerts} onSelect={open} ctxLabel={ctxLabel}/>}

      {/* 3) What Matters Now (explicit forecast included) */}
      <TopFocusBanner tr={tr} decSum={decSum} alertSum={alertSum} health={health}/>
      {decs?.length>0 && <ActionStrip decisions={decs} tr={tr} causes={causes} impacts={impacts} onSelect={open}/>}
      <ForecastNow fcData={fcData} tr={tr}/>

      {/* 4) Branch Performance (aligned lang/window/scope) */}
      <BranchPerformance companyId={selectedId} qs={qs} tr={tr}/>

      {/* 5) Intelligence Grid */}
      {intel && <DomainGrid intelligence={intel} tr={tr} rootCauses={causes} decisions={decs} alerts={alerts} onSelect={open}/>}
      <AlertsBar alerts={alerts} tr={tr} onSelect={open}/>

      {/* 6) Command Navigation (lightweight bottom launcher) */}
      <CommandNav tr={tr} navigate={navigate}/>

      {pType && (
        <ContextPanel
          type={pType}
          payload={pLoad}
          extra={pXtra}
          impacts={impacts}
          tr={tr}
          onClose={close}
          onNavigate={()=>navigate('/analysis',{state:{focus:pLoad?.domain||pLoad?.type||'overview'}})}
        />
      )}
    </div>
  )
}

