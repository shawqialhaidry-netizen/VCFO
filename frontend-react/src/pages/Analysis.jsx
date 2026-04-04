/**
 * Analysis.jsx — Phase 32.8
 * Complete financial analysis + decision-support screen.
 *
 * Answers: What is wrong? Why? What to do? What impact?
 *
 * Structure:
 *   Header strip  — health + 3 KPIs with inline explanation
 *   Top Issues    — alerts + weak ratios + negative trends (top 3)
 *   Opportunities — strong signals + positive impacts (top 3)
 *   Tabs          — Overview / Profitability / Liquidity / Efficiency / Decisions / Alerts
 *
 * Data: single /executive fetch — no duplicate calculations.
 */
import { useState, useEffect, useCallback, useMemo } from 'react'
import { strictT, strictTParams } from '../utils/strictI18n.js'
import { buildExecutiveNarrative } from '../utils/buildExecutiveNarrative.js'
import { selectPrimaryDecision } from '../utils/selectPrimaryDecision.js'
import { buildDrillIntelligence } from '../utils/buildDrillIntelligence.js'
import CmdServerText from '../components/CmdServerText.jsx'
import DrillIntelligenceBlock from '../components/DrillIntelligenceBlock.jsx'
import { useNavigate, useLocation } from 'react-router-dom'
import DrillBackBar from '../components/DrillBackBar.jsx'
import { useLang }    from '../context/LangContext.jsx'
import { useCompany } from '../context/CompanyContext.jsx'
import { usePeriodScope } from '../context/PeriodScopeContext.jsx'  // FIX-1.2
import { kpiContextLabel, kpiLabel } from '../utils/kpiContext.js'
import {
  formatCompactForLang,
  formatFullForLang,
  formatPctForLang,
  formatSignedPctForLang,
  formatMultipleForLang,
  formatDays,
} from '../utils/numberFormat.js'
import { buildAnalysisQuery } from '../utils/buildAnalysisQuery.js'
import { ANALYSIS_PATH_BY_TAB } from '../utils/analysisRoutes.js'

const API = '/api/v1'
function auth() {
  try { const t=JSON.parse(localStorage.getItem('vcfo_auth')||'{}').token; return t?{Authorization:`Bearer ${t}`}:{} }
  catch { return {} }
}

// ── Formatters ────────────────────────────────────────────────────────────────
const clr   = v => v==null?'var(--text-secondary)':v>0?'var(--green)':v<0?'var(--red)':'var(--text-secondary)'
const arr   = v => v==null?'':v>0?'▲':v<0?'▼':'─'
const stC   = {excellent:'var(--green)',good:'var(--accent)',warning:'var(--amber)',risk:'var(--red)',neutral:'var(--text-secondary)'}
const urgC  = {high:'var(--red)',medium:'var(--amber)',low:'var(--blue)'}
const domC  = {liquidity:'var(--blue)',profitability:'var(--green)',efficiency:'var(--violet)',leverage:'var(--amber)',growth:'var(--accent)',cross_domain:'#e879f9'}

// ── Phase 6.4: forecast text helper (shared logic) ───────────────────────────
function kpiForecast(type, fcData, tr, fmtFn, lang) {
  if (!fcData?.available) return null
  const series = fcData?.scenarios?.base?.[type] || []
  const next = series[0]
  if (!next?.point) return null
  const val = fmtFn ? fmtFn(next.point) : formatFullForLang(next.point, lang)
  const dir = next.mom_applied != null
    ? (next.mom_applied > 0 ? '↑' : next.mom_applied < 0 ? '↓' : '→')
    : ''
  const conf = next.confidence != null
    ? tr('stmt_kpi_forecast_conf', { confidence: formatPctForLang(next.confidence, 0, lang) })
    : ''
  const body = [dir, val].filter(Boolean).join(' ')
  return `${body}${conf}`
}

// ── Micro components ──────────────────────────────────────────────────────────
const Badge = ({label,color}) => (
  <span style={{fontSize:9,fontWeight:800,padding:'2px 8px',borderRadius:20,
    background:`${color}18`,color,border:`1px solid ${color}30`,
    textTransform:'uppercase',letterSpacing:'.05em',flexShrink:0,whiteSpace:'nowrap'}}>
    {label}
  </span>
)

// ── Premium sparkline for Analysis ───────────────────────────────────────────
function SparkChart({data=[],color='var(--accent)',h=28,w=72}) {
  if(!data||data.filter(Boolean).length<2) return null
  const vals=data.filter(v=>v!=null)
  const mn=Math.min(...vals),mx=Math.max(...vals),rng=mx-mn||1
  const uid=`ac${Math.abs(Math.round(vals[0]||0)).toString(36)}`
  const pts=vals.map((v,i)=>[(i/(vals.length-1))*w, h-((v-mn)/rng)*(h*.8)-h*.1])
  const path=pts.reduce((acc,[x,y],i)=>{
    if(i===0) return `M${x.toFixed(1)},${y.toFixed(1)}`
    const [px,py]=pts[i-1]
    const cx1=(px+(x-px)*.5).toFixed(1)
    return acc+` C${cx1},${py.toFixed(1)} ${cx1},${y.toFixed(1)} ${x.toFixed(1)},${y.toFixed(1)}`
  },'')
  const area=`${path} L${w},${h} L0,${h} Z`
  return(
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{display:'block',direction:'ltr',overflow:'visible'}}>
      <defs>
        <linearGradient id={uid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3"/>
          <stop offset="100%" stopColor={color} stopOpacity="0"/>
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${uid})`}/>
      <path d={path} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round"/>
      <circle cx={pts[pts.length-1][0]} cy={pts[pts.length-1][1]} r="2.5"
        fill={color} style={{filter:`drop-shadow(0 0 3px ${color})`}}/>
    </svg>
  )
}

const Card = ({children,style={}}) => (
  <div style={{
    background:'var(--bg-panel)',
    border:'1px solid var(--border)',
    borderRadius:13,
    padding:'16px 18px',
    transition:'box-shadow 0.2s ease, border-color 0.2s ease',
    ...style
  }}>{children}</div>
)

function SectionHead({label,count,color='var(--accent)',sub}) {
  return (
    <div style={{marginBottom:12}}>
      <div style={{display:'flex',alignItems:'center',gap:8}}>
        <div style={{width:20,height:2,background:color,borderRadius:2}}/>
        <span style={{fontSize:10,fontWeight:800,color,textTransform:'uppercase',letterSpacing:'.08em'}}>{label}</span>
        {count!=null&&count>0&&(
          <span style={{fontSize:10,color:'var(--text-secondary)',background:'var(--bg-elevated)',
            border:'1px solid var(--border)',borderRadius:20,padding:'0px 7px'}}>{count}</span>
        )}
      </div>
      {sub&&<p style={{fontSize:11,color:'var(--text-secondary)',margin:'4px 0 0 28px',lineHeight:1.5}}>{sub}</p>}
    </div>
  )
}

function Spark({data,color='var(--accent)',h=28,w=70}) {
  const v=(data||[]).filter(x=>x!=null)
  if(v.length<2) return null
  const mn=Math.min(...v),mx=Math.max(...v),rng=mx-mn||1
  const pts=v.map((x,i)=>`${(i/(v.length-1))*w},${h-((x-mn)/rng)*h*0.82+h*0.09}`)
  return <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{flexShrink:0}}>
    <polyline points={pts.join(' ')} fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
}

function MetricCard({label,value,fullValue,mom,spark,color,explain,insight,cause,forecast,lang,tr,momWord}) {
  const [hov,setHov] = useState(false)
  return(
    <div
      style={{background:hov?`linear-gradient(160deg,rgba(255,255,255,.025),var(--bg-panel))`:'var(--bg-panel)',
        borderWidth:'2px 1px 1px 1px',
        borderStyle:'solid',
        borderColor:`${color} ${hov?color+'55':'rgba(255,255,255,0.08)'} ${hov?color+'55':'rgba(255,255,255,0.08)'} ${hov?color+'55':'rgba(255,255,255,0.08)'}`,
        borderRadius:13,padding:'14px 16px',flex:1,minWidth:0,
        cursor:'default',
        transition:'all 0.2s cubic-bezier(0.4,0,0.2,1)',
        transform: hov?'translateY(-2px)':'none',
        boxShadow: hov?`0 10px 28px rgba(0,0,0,0.4),0 0 0 1px ${color}18`:'0 2px 8px rgba(0,0,0,0.2)',
      }}
      onMouseEnter={()=>setHov(true)}
      onMouseLeave={()=>setHov(false)}
      title={explain||''}>
      <div style={{fontSize:9,color:'var(--text-muted)',fontWeight:700,textTransform:'uppercase',
        letterSpacing:'.07em',marginBottom:8}}>{label}</div>
      <div style={{
        fontFamily:'var(--font-display)',fontSize:24,fontWeight:800,
        color:'#ffffff',letterSpacing:'-.025em',lineHeight:1,direction:'ltr',
        textShadow:hov?`0 0 20px ${color}45`:'none',transition:'text-shadow .2s',
      }}>{value}</div>
      {fullValue&&<div style={{fontFamily:'var(--font-mono)',fontSize:9,color:'var(--text-muted)',marginTop:2,marginBottom:2,letterSpacing:'.02em',direction:'ltr'}}>{fullValue}</div>}
      {mom!=null&&(
        <span style={{
          display:'inline-block',marginTop:7,
          fontFamily:'var(--font-mono)',fontSize:10,fontWeight:700,
          color:clr(mom),
          padding:'1px 6px',borderRadius:9,background:`${clr(mom)}14`,
        }}>
          {arr(mom)} {formatPctForLang(Math.abs(mom), 1, lang)} {momWord}
        </span>
      )}
      {spark&&<div style={{marginTop:8,opacity:hov?1:.65,transition:'opacity .2s'}}>
        <SparkChart data={spark} color={color}/>
      </div>}
      {/* Phase 6.1: insight under metric */}
      {insight&&<div style={{fontSize:10,color:'var(--text-muted)',marginTop:6,
        lineHeight:1.4,opacity:.8,overflow:'hidden',textOverflow:'clip',whiteSpace:'nowrap'}}
        title={insight}>
        💡{' '}
        {lang && tr ? <CmdServerText lang={lang} tr={tr}>{insight}</CmdServerText> : insight}
      </div>}
      {cause&&<div style={{fontSize:9,color:'var(--text-dim)',marginTop:2,
        lineHeight:1.3,opacity:.6,overflow:'hidden',textOverflow:'clip',whiteSpace:'nowrap'}}
        title={cause}>
        ↳{' '}
        {lang && tr ? <CmdServerText lang={lang} tr={tr}>{cause}</CmdServerText> : cause}
      </div>}
      {forecast&&<div style={{fontSize:9,color:'var(--accent)',marginTop:3,
        lineHeight:1.3,opacity:.7,overflow:'hidden',textOverflow:'clip',whiteSpace:'nowrap',
        fontFamily:'var(--font-mono)'}} title={forecast}>
        📈{' '}
        {lang && tr ? <CmdServerText lang={lang} tr={tr} style={{fontFamily:'var(--font-mono)'}}>{forecast}</CmdServerText> : forecast}
      </div>}
    </div>
  )
}

function RatioRow({label,value,status,explain}) {
  const sc = {good:'var(--green)',warning:'var(--amber)',risk:'var(--red)',neutral:'var(--text-secondary)'}[status]||'var(--text-secondary)'
  return (
    <div style={{padding:'8px 4px',borderBottom:'1px solid var(--border)',
      borderRadius:4,transition:'background .15s'}}
      onMouseEnter={e=>e.currentTarget.style.background='rgba(255,255,255,0.025)'}
      onMouseLeave={e=>e.currentTarget.style.background='transparent'}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:explain?4:0}}>
        <span style={{fontSize:12,color:'var(--text-secondary)'}}>{label}</span>
        <span style={{
          fontFamily:'var(--font-mono)',fontSize:12,fontWeight:700,color:sc,
          padding:'2px 7px',borderRadius:9,background:`${sc}14`,direction:'ltr',
        }}>{value}</span>
      </div>
      {explain&&<p style={{fontSize:10,color:'var(--text-muted)',margin:0,lineHeight:1.5,paddingLeft:4}}>{explain}</p>}
    </div>
  )
}

function IssueCard({issue,tr,lang,onOpen}) {
  const sc = urgC[issue.severity]||'var(--text-secondary)'
  return (
    <div onClick={()=>issue.decision&&onOpen(issue.decision)}
      style={{background:'var(--bg-elevated)',border:`1px solid ${sc}20`,
        borderLeft:`3px solid ${sc}`,borderRadius:9,padding:'12px 14px',marginBottom:8,
        cursor:issue.decision?'pointer':'default',transition:'background .15s'}}
      onMouseEnter={e=>{if(issue.decision)e.currentTarget.style.background='var(--bg-panel)'}}
      onMouseLeave={e=>{e.currentTarget.style.background='var(--bg-elevated)'}}>
      <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:5,flexWrap:'wrap'}}>
        <Badge label={tr(`urgency_${issue.severity}`)} color={sc}/>
        <span style={{fontSize:12,fontWeight:700,color:'#ffffff',flex:1}}>
          <CmdServerText lang={lang} tr={tr}>{issue.title}</CmdServerText>
        </span>
        {issue.decision&&<span style={{fontSize:9,color:'var(--accent)',opacity:.8}}>→ {tr('exec_actions')}</span>}
      </div>
      <p style={{fontSize:11,color:'var(--text-secondary)',margin:0,lineHeight:1.6}}>
        <CmdServerText lang={lang} tr={tr}>{issue.reason}</CmdServerText>
      </p>
    </div>
  )
}

function OpportunityCard({opp,tr,lang,onOpen}) {
  const dc = domC[opp.domain]||'var(--accent)'
  return (
    <div onClick={()=>opp.decision&&onOpen(opp.decision)}
      style={{background:'var(--bg-elevated)',border:'1px solid rgba(52,211,153,.18)',
        borderLeft:'3px solid var(--green)',borderRadius:9,padding:'12px 14px',marginBottom:8,
        cursor:opp.decision?'pointer':'default',transition:'background .15s'}}
      onMouseEnter={e=>{if(opp.decision)e.currentTarget.style.background='var(--bg-panel)'}}
      onMouseLeave={e=>{e.currentTarget.style.background='var(--bg-elevated)'}}>
      <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:5,flexWrap:'wrap'}}>
        <Badge label={tr(`domain_${opp.domain}_simple`)} color={dc}/>
        <span style={{fontSize:12,fontWeight:700,color:'#ffffff',flex:1}}>
          <CmdServerText lang={lang} tr={tr}>{opp.title}</CmdServerText>
        </span>
      </div>
      <p style={{fontSize:11,color:'var(--text-secondary)',margin:0,lineHeight:1.6}}>
        <CmdServerText lang={lang} tr={tr}>{opp.reason}</CmdServerText>
      </p>
      {opp.impact_value&&(
        <div style={{marginTop:6,fontSize:11,fontWeight:800,color:'var(--green)',fontFamily:'var(--font-mono)'}}>{opp.impact_value} {tr('impact_expected')}</div>
      )}
    </div>
  )
}

function DecCard({dec,tr,lang,impacts,onOpen}) {
  const uc = urgC[dec.urgency]||'var(--text-secondary)'
  const dc = domC[dec.domain]||'var(--accent)'
  const impKey = dec.key||dec.domain
  const imp = impacts[impKey]?.impact || impacts[dec.domain]?.impact
  return (
    <div onClick={()=>onOpen(dec)}
      style={{background:'var(--bg-elevated)',border:'1px solid var(--border)',
        borderLeft:`3px solid ${uc}`,borderRadius:9,padding:'12px 14px',marginBottom:8,
        cursor:'pointer',transition:'background .15s'}}
      onMouseEnter={e=>{e.currentTarget.style.background='var(--bg-panel)'}}
      onMouseLeave={e=>{e.currentTarget.style.background='var(--bg-elevated)'}}>
      <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:5,flexWrap:'wrap'}}>
        <Badge label={tr(`urgency_${dec.urgency}`)} color={uc}/>
        <span style={{fontSize:11,fontWeight:700,color:dc,textTransform:'uppercase',letterSpacing:'.05em'}}>
          {tr(`domain_${dec.domain}_simple`)}
        </span>
        <span style={{marginLeft:'auto',fontSize:9,color:'var(--text-secondary)',fontFamily:'monospace'}}>
          ⏱ <CmdServerText lang={lang} tr={tr}>{dec.timeframe}</CmdServerText>
        </span>
      </div>
      <div style={{fontSize:13,fontWeight:700,color:'#ffffff',marginBottom:4}}>
        <CmdServerText lang={lang} tr={tr}>{dec.title}</CmdServerText>
      </div>
      <div style={{fontSize:11,color:'var(--text-secondary)',lineHeight:1.5,marginBottom:imp?.value?6:0,
        display:'-webkit-box',WebkitLineClamp:2,WebkitBoxOrient:'vertical',overflow:'hidden'}}>
        <CmdServerText lang={lang} tr={tr}>{dec.reason}</CmdServerText>
      </div>
      {imp?.value&&(
        <div style={{display:'inline-flex',alignItems:'center',gap:4,
          background:`${uc}12`,border:`1px solid ${uc}25`,borderRadius:20,padding:'2px 9px'}}>
          <span style={{fontSize:11,fontWeight:800,color:uc,fontFamily:'monospace'}}>
            +{formatCompactForLang(imp.value, lang)}
          </span>
          <span style={{fontSize:9,color:uc,opacity:.8}}>{imp.type==='cash'?tr('impact_type_cash'):tr('impact_type_margin')}</span>
        </div>
      )}
    </div>
  )
}

function AlertCard({alert,tr,lang}) {
  const uc = urgC[alert.severity]||'var(--text-secondary)'
  return (
    <div style={{padding:'10px 14px',borderRadius:9,background:'var(--bg-elevated)',
      borderWidth:'1px 1px 1px 3px',borderStyle:'solid',borderColor:`${uc}25 ${uc}25 ${uc}25 ${uc}`,marginBottom:6}}>
      <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:4}}>
        <Badge label={tr(`severity_${alert.severity}`)} color={uc}/>
        <span style={{fontSize:12,fontWeight:700,color:'#ffffff',flex:1}}>
          <CmdServerText lang={lang} tr={tr}>{alert.title}</CmdServerText>
        </span>
      </div>
      <div style={{fontSize:11,color:'var(--text-secondary)',lineHeight:1.5}}>
        <CmdServerText lang={lang} tr={tr}>{alert.message}</CmdServerText>
      </div>
    </div>
  )
}

function CauseCard({cause,lang,tr}) {
  const ic = {high:'var(--red)',medium:'var(--amber)',low:'var(--blue)'}[cause.impact]||'var(--text-secondary)'
  return (
    <div style={{padding:'10px 14px',borderRadius:9,background:'var(--bg-elevated)',
      borderWidth:'1px 1px 1px 3px',borderStyle:'solid',borderColor:`${ic}20 ${ic}20 ${ic}20 ${ic}`,marginBottom:6}}>
      <div style={{fontSize:12,fontWeight:700,color:'#ffffff',marginBottom:3}}>
        <CmdServerText lang={lang} tr={tr}>{cause.title}</CmdServerText>
      </div>
      <div style={{fontSize:11,color:'var(--text-secondary)',lineHeight:1.5,
        display:'-webkit-box',WebkitLineClamp:2,WebkitBoxOrient:'vertical',overflow:'hidden'}}>
        <CmdServerText lang={lang} tr={tr}>{cause.description}</CmdServerText>
      </div>
      {cause.mechanism&&(
        <div style={{marginTop:6,fontSize:10,color:'var(--text-secondary)',lineHeight:1.5,
          borderTop:'1px solid var(--border)',paddingTop:5,fontStyle:'italic',
          overflow:'hidden',textOverflow:'clip',whiteSpace:'nowrap'}} title={cause.mechanism}>
          <CmdServerText lang={lang} tr={tr}>{cause.mechanism.length > 130 ? cause.mechanism.slice(0, 130) : cause.mechanism}</CmdServerText>
        </div>
      )}
    </div>
  )
}

function DecisionPanel({dec,impacts,tr,lang,onClose}) {
  if (!dec) return null
  const dc = domC[dec.domain]||'var(--accent)'
  const uc = urgC[dec.urgency]||'var(--text-secondary)'
  const impKey = dec.key||dec.domain
  const imp = impacts[impKey]?.impact || impacts[dec.domain]?.impact
  const steps = (dec.action||'').split(/[0-9]+[).]\s*/).filter(s=>s.trim().length>5)
  const Sec = ({label,color='var(--text-secondary)',children}) => (
    <div style={{marginBottom:20}}>
      <div style={{display:'flex',alignItems:'center',gap:7,marginBottom:10}}>
        <div style={{width:18,height:2,background:color,borderRadius:2}}/>
        <span style={{fontSize:9,fontWeight:800,color,textTransform:'uppercase',letterSpacing:'.08em'}}>{label}</span>
      </div>
      {children}
    </div>
  )
  return (
    <>
      <div onClick={onClose} style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.45)',zIndex:90}}/>
      <div style={{position:'fixed',top:0,right:0,bottom:0,width:460,zIndex:91,
        background:'var(--bg-panel)',borderLeft:'1px solid var(--border)',
        display:'flex',flexDirection:'column',boxShadow:'-20px 0 60px rgba(0,0,0,.65)',
        animation:'slideIn .2s ease-out'}}>
        <div style={{padding:'16px 20px',borderBottom:'1px solid var(--border)',
          display:'flex',alignItems:'center',gap:10,flexShrink:0}}>
          <div style={{flex:1,fontSize:9,fontWeight:700,color:'var(--text-secondary)',
            textTransform:'uppercase',letterSpacing:'.08em'}}>{tr('tab_decisions_v2')}</div>
          <button onClick={onClose} style={{width:28,height:28,borderRadius:7,
            border:'1px solid var(--border)',background:'var(--bg-elevated)',
            color:'var(--text-secondary)',cursor:'pointer',fontSize:15}}>×</button>
        </div>
        <div style={{flex:1,overflowY:'auto',padding:'20px'}}>
          <div style={{fontSize:17,fontWeight:800,color:'#ffffff',lineHeight:1.3,marginBottom:8}}>
            <CmdServerText lang={lang} tr={tr}>{dec.title}</CmdServerText>
          </div>
          <div style={{display:'flex',gap:6,flexWrap:'wrap',marginBottom:20}}>
            <Badge label={tr(`urgency_${dec.urgency}`)} color={uc}/>
            {dec.impact_level&&<Badge label={tr(`impact_${dec.impact_level}`)} color={uc}/>}
            <Badge label={dec.confidence != null && Number.isFinite(Number(dec.confidence))
              ? formatPctForLang(Number(dec.confidence), 0, lang)
              : '—'} color='var(--text-secondary)'/>
          </div>
          <Sec label={tr('exec_why')} color='var(--red)'>
            <p style={{fontSize:12,color:'var(--text-secondary)',lineHeight:1.75,margin:0}}>
              <CmdServerText lang={lang} tr={tr}>{dec.reason}</CmdServerText>
            </p>
          </Sec>
          <Sec label={tr('exec_actions')} color={dc}>
            <div style={{display:'flex',flexDirection:'column',gap:7}}>
              {steps.length>1?steps.map((s,i)=>(
                <div key={i} style={{display:'flex',gap:8,background:`${dc}08`,borderRadius:8,padding:'9px 12px',border:`1px solid ${dc}15`}}>
                  <div style={{width:20,height:20,borderRadius:'50%',background:`${dc}22`,display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0,fontSize:11,fontWeight:800,color:dc}}>{i+1}</div>
                  <span style={{fontSize:11,color:'var(--text-secondary)',lineHeight:1.6}}>
                    <CmdServerText lang={lang} tr={tr}>{s.trim()}</CmdServerText>
                  </span>
                </div>
              )):<p style={{fontSize:12,color:'var(--text-secondary)',lineHeight:1.75,margin:0}}>
                <CmdServerText lang={lang} tr={tr}>{dec.action}</CmdServerText>
              </p>}
            </div>
          </Sec>
          {imp?.value&&(
            <Sec label={tr('impact_expected_label')} color='var(--green)'>
              <div style={{background:'rgba(52,211,153,.06)',borderRadius:9,padding:'12px 14px',border:'1px solid rgba(52,211,153,.2)'}}>
                <div style={{fontFamily:'var(--font-mono)',fontSize:22,fontWeight:800,color:'var(--green)',direction:'ltr',marginBottom:4}}>
                  +{formatCompactForLang(imp.value, lang)}
                </div>
                {imp.range?.low!=null&&imp.range?.high!=null&&<div style={{fontSize:10,color:'var(--text-secondary)',marginBottom:6,fontFamily:'var(--font-mono)'}}>
                  {formatCompactForLang(imp.range.low, lang)} – {formatCompactForLang(imp.range.high, lang)} {tr('impact_range_label')}
                </div>}
                <p style={{fontSize:11,color:'var(--text-secondary)',lineHeight:1.65,margin:'0 0 8px'}}>
                  <CmdServerText lang={lang} tr={tr}>{imp.description}</CmdServerText>
                </p>
                <Badge label={imp.confidence != null && Number.isFinite(Number(imp.confidence))
                  ? `${tr('fc_confidence')}: ${formatPctForLang(Number(imp.confidence), 0, lang)}`
                  : `${tr('fc_confidence')}: —`} color='var(--green)'/>
              </div>
            </Sec>
          )}
          {dec.expected_effect&&(
            <Sec label={tr('exec_effect')} color='var(--green)'>
              <p style={{fontSize:12,color:'var(--text-secondary)',lineHeight:1.75,margin:0}}>
                <CmdServerText lang={lang} tr={tr}>{dec.expected_effect}</CmdServerText>
              </p>
            </Sec>
          )}
          <div style={{display:'flex',alignItems:'center',gap:10,background:'var(--bg-elevated)',borderRadius:10,padding:'12px 16px',border:'1px solid var(--border)'}}>
            <span style={{fontSize:22,opacity:.4}}>⏱</span>
            <div>
              <div style={{fontSize:9,color:'var(--text-secondary)',textTransform:'uppercase',letterSpacing:'.06em',marginBottom:2}}>{tr('exec_timeframe')}</div>
              <div style={{fontSize:15,fontWeight:800,color:uc,fontFamily:'monospace'}}>
                <CmdServerText lang={lang} tr={tr}>{dec.timeframe}</CmdServerText>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

// ── Derive top issues / opportunities ─────────────────────────────────────────
function deriveIssues(alerts, causes, decs, tr) {
  const issues = []
  const seen = new Set()
  alerts.filter(a=>a.severity==='high').slice(0,2).forEach(a => {
    if (seen.has(a.title)) return; seen.add(a.title)
    issues.push({ id:a.id||a.title, title:a.title, reason:a.message, severity:'high',
      decision: decs.find(d=>d.domain===a.impact||d.domain===a.domain)||null })
  })
  causes.filter(c=>c.impact==='high').slice(0,2).forEach(c => {
    if (seen.has(c.id)||issues.length>=3) return; seen.add(c.id)
    issues.push({ id:c.id, title:c.title,
      reason:(c.description||'').length>120?(c.description||'').slice(0,120):(c.description||''),
      severity:'high', decision: decs.find(d=>d.domain===c.domain)||null })
  })
  if (issues.length<3) {
    alerts.filter(a=>a.severity==='medium'&&!seen.has(a.title)).slice(0,3-issues.length).forEach(a => {
      seen.add(a.title)
      issues.push({ id:a.id||a.title, title:a.title, reason:a.message, severity:'medium', decision:null })
    })
  }
  return issues.slice(0,3)
}

function deriveOpportunities(decs, causes, impacts, trends, ratios, tr, lang) {
  const opps = []
  const ytdRev = trends?.revenue?.ytd_vs_prior
  const revDir = trends?.revenue?.direction
  if (revDir==='up'||ytdRev>5) {
    const gDec = decs.find(d=>d.domain==='growth')
    opps.push({ domain:'growth',
      title: tr('opp_revenue_momentum'),
      reason: ytdRev>0
        ? tr('opp_revenue_momentum_reason_yoy', { pct: formatPctForLang(ytdRev, 1, lang) })
        : tr('opp_revenue_momentum_reason_trend'),
      impact_value: null, decision: gDec||null })
  }
  const sorted = Object.values(impacts||{}).filter(x=>x?.impact?.value>0)
    .sort((a,b)=>(b.impact.value||0)-(a.impact.value||0))
  sorted.slice(0,2).forEach(item => {
    if (opps.length>=3) return
    const dec = decs.find(d=>d.key===item.decision_key||d.domain===item.domain)
    if (!dec) return
    const v = item.impact.value
    opps.push({ domain:item.domain||dec.domain,
      title: tr(`dec_short_${dec.domain}`),
      reason: item.impact.description,
      impact_value: `+${formatCompactForLang(v, lang)}`, decision: dec })
  })
  if (opps.length<3) {
    const allR = {...(ratios.profitability||{}),...(ratios.liquidity||{})}
    const good = Object.entries(allR).find(([,r])=>r?.status==='good')
    if (good) {
      const [k,r] = good
      opps.push({ domain:'profitability',
        title: tr('opp_strong_ratio'),
        reason: tr('opp_strong_ratio_reason', { metric: tr(k) }),
        impact_value: null, decision: null })
    }
  }
  return opps.slice(0,3)
}


// ── FIX-4.3: DataQualityBanner ────────────────────────────────────────────────
function DataQualityBanner({ validation, lang, tr }) {
  if (!validation) return null
  const { consistent, warnings = [], has_errors, has_info } = validation
  if (consistent === true && !has_info) return null
  const color  = has_errors ? '#f87171' : '#fbbf24'
  const bg     = has_errors ? 'rgba(248,113,113,0.06)' : 'rgba(251,191,36,0.06)'
  const border = has_errors ? 'rgba(248,113,113,0.25)' : 'rgba(251,191,36,0.25)'
  const icon   = has_errors ? '⚠' : 'ℹ'
  return (
    <div style={{display:'flex',flexDirection:'column',gap:4,
      padding:'8px 14px',borderRadius:9,marginBottom:12,
      background:bg,borderWidth:'1px 1px 1px 3px',borderStyle:'solid',borderColor:`${border} ${border} ${border} ${color}`}}>
      <div style={{display:'flex',alignItems:'center',gap:6}}>
        <span style={{fontSize:13}}>{icon}</span>
        <span style={{fontSize:10,fontWeight:800,color,textTransform:'uppercase',letterSpacing:'.06em'}}>
          {has_errors ? tr('dq_warning_title') : tr('dq_notice_title')}
        </span>
      </div>
      {warnings.map((w,i)=>{
        return(<div key={i} style={{fontSize:10,color:'var(--text-secondary)',paddingLeft:20,lineHeight:1.5}}>
          · {tr(`dq_${w.code}`)}
        </div>)
      })}
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────────────────
//  Main Component
// ──────────────────────────────────────────────────────────────────────────────
export default function Analysis({ routeDefaultTab = null } = {}) {
  const { tr: trCtx, lang } = useLang()
  const tr = useCallback((key, params) => {
    if (params != null && typeof params === 'object') return strictTParams(trCtx, lang, key, params)
    return strictT(trCtx, lang, key)
  }, [trCtx, lang])

  const fmtV = useCallback(
    (k, v) => {
      if (v == null || (typeof v === 'number' && !Number.isFinite(v))) return '—'
      if (k.includes('margin') || k.includes('_pct')) return formatPctForLang(v, 1, lang)
      if (k.includes('ratio') || k.includes('turnover')) return formatMultipleForLang(v, 2, lang)
      if (k.includes('days')) return formatDays(v)
      return formatCompactForLang(v, lang)
    },
    [lang],
  )
  const ctxLabel = () => kpiContextLabel({ window: 'ALL', ps: ps||{}, latestPeriod: data?.meta?.periods?.slice(-1)[0] || '', lang, tr })
  const { selectedId, selectedCompany } = useCompany()
  const { params: ps, toQueryString: scopeQS, setResolved, isIncompleteCustom, window: win } = usePeriodScope()
  const navigate  = useNavigate()
  const location  = useLocation()
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(false)
  const [err,     setErr]     = useState(null)
  const [fcData,  setFcData]  = useState(null)
  const [tab,     setTab]     = useState(() => location.state?.focus || routeDefaultTab || 'overview')
  const [selDec,  setSelDec]  = useState(null)
  const [consolidate, setConsolidate] = useState(false)

  useEffect(() => {
    if (location.state?.focus) {
      setTab(location.state.focus)
      return
    }
    if (routeDefaultTab) setTab(routeDefaultTab)
  }, [location.state, routeDefaultTab])

  const goTab = useCallback(
    (k) => {
      setTab(k)
      const path = ANALYSIS_PATH_BY_TAB[k]
      if (path && location.pathname !== path) {
        navigate(path, { replace: true, state: { focus: k } })
      }
    },
    [navigate, location.pathname],
  )

  const load = useCallback(async () => {
    if (!selectedId) return
    if (isIncompleteCustom()) return   // FIX-1.2: guard incomplete custom scope
    const qs = buildAnalysisQuery(scopeQS, { lang, window: win, consolidate })
    if (qs === null) return            // FIX-1.2: null = incomplete scope, do not fetch
    setLoading(true); setErr(null)
    try {
      const r = await fetch(`${API}/analysis/${selectedId}/executive?${qs}`, {headers:auth()})
      if (!r.ok) {
        if (r.status === 422) {
          setErr(tr('err_no_financial_data'))
        } else {
          setErr(tr('err_http_status', { status: r.status }))
        }
        return
      }
      const json = await r.json()
      setData(json)
      setResolved(json.meta?.scope || null)  // FIX-1.2: sync scope label back to context
    } catch(e) { setErr(e.message) }
    // Phase 6.4: forecast — silent fail
    try {
      const fqs = buildAnalysisQuery(scopeQS, { lang, window: win, consolidate: false })
      if (fqs !== null) {
        const fr = await fetch(`${API}/analysis/${selectedId}/forecast?${fqs}`, {headers:auth()})
        if (fr.ok) { const fj = await fr.json(); if (fj?.data) setFcData(fj.data) }
      }
    } catch (_) {}
    finally { setLoading(false) }
  }, [selectedId, lang, consolidate, win, scopeQS, setResolved, isIncompleteCustom])

  useEffect(() => { load() }, [selectedId, load])  // FIX-1.2: depend on load (scope-aware)

  const d        = data?.data || {}
  const intel    = d.intelligence || {}
  const ratios   = intel.ratios   || {}
  const trends   = intel.trends   || {}
  const kpis     = d.kpi_block?.kpis   || {}
  const series   = d.kpi_block?.series || {}
  const cashflow = d.cashflow     || {}
  const decs     = d.decisions    || []
  const alerts   = d.alerts       || []
  const causes   = d.root_causes  || []
  const rawImps  = d.decision_impacts || []
  const health      = d.health_score_v2
  const validation  = data?.meta?.pipeline_validation  // FIX-4.3
  const status   = intel.status   || 'neutral'
  const hc       = stC[status]    || 'var(--text-secondary)'
  const periods  = trends.periods || data?.meta?.periods || []
  const currency = data?.currency || ''
  const prof = ratios.profitability || {}
  const liq  = ratios.liquidity    || {}
  const eff  = ratios.efficiency   || {}
  const lev  = ratios.leverage     || {}

  const impacts = {}
  rawImps.forEach(item => { impacts[item.decision_key||item.domain] = item })
  const issues = data ? deriveIssues(alerts, causes, decs, tr) : []
  const opps   = data ? deriveOpportunities(decs, causes, impacts, trends, ratios, tr, lang) : []
  const highAlerts = alerts.filter(a=>a.severity==='high').length

  const drillBundle = useMemo(() => {
    if (!data || !d || !Object.keys(d).length) return null
    const narr = buildExecutiveNarrative(d, { lang, t: tr })
    const pr = selectPrimaryDecision({
      decisions: Array.isArray(decs) ? decs : [],
      impacts,
      kpis,
      cashflow,
      comparativeIntelligence: d.comparative_intelligence ?? null,
      expenseIntelligence: d.expense_intelligence ?? null,
      expenseDecisionsV2: d.expense_decisions_v2 ?? [],
    })
    return {
      narrative: narr,
      kpis,
      kpi_block: d.kpi_block,
      primaryResolution: pr,
      expenseIntel: d.expense_intelligence ?? null,
      decisions: decs,
      health,
      cashflow: d.cashflow,
      comparative_intelligence: d.comparative_intelligence ?? null,
    }
  }, [data, d, decs, impacts, kpis, cashflow, health, lang, tr])

  const drillExtra = useMemo(() => {
    if (!drillBundle) return null
    return {
      drillIntelBundle: {
        narrative: drillBundle.narrative,
        kpis: drillBundle.kpis,
        primaryResolution: drillBundle.primaryResolution,
        expenseIntel: drillBundle.expenseIntel,
        decisions: drillBundle.decisions,
        health: drillBundle.health,
        cashflow: drillBundle.cashflow,
        comparative_intelligence: drillBundle.comparative_intelligence,
      },
      execChartBundle: {
        kpi_block: drillBundle.kpi_block,
        cashflow: drillBundle.cashflow,
        comparative_intelligence: drillBundle.comparative_intelligence,
      },
      analysisRatios: {
        profitability: prof,
        liquidity: liq,
        efficiency: eff,
      },
    }
  }, [drillBundle, prof, liq, eff])

  const analysisDrillLines = useCallback(
    (tabKey) => {
      if (!drillExtra) return { what: [], why: [], do: [] }
      return buildDrillIntelligence({
        panelType: 'analysis_tab',
        payload: { tab: tabKey },
        extra: drillExtra,
        t: tr,
        lang,
      })
    },
    [drillExtra, tr, lang],
  )

  const kpiExplain = {
    revenue:    kpis.revenue?.mom_pct!=null
      ? (kpis.revenue.mom_pct>0
        ? tr('kpi_rev_up_vs_last_month',   { pct: formatPctForLang(kpis.revenue.mom_pct, 1, lang) })
        : tr('kpi_rev_down_vs_last_month', { pct: formatPctForLang(Math.abs(kpis.revenue.mom_pct), 1, lang) }))
      : null,
    net_profit: prof.net_margin_pct?.value!=null
      ? tr('kpi_net_margin_of_revenue_to_profit', { pct: formatPctForLang(prof.net_margin_pct.value, 1, lang) })
      : null,
    margin: prof.net_margin_pct?.status
      ? tr(`kpi_margin_status_${prof.net_margin_pct.status}`)
      : null,
  }

  const TABS = [
    { k:'overview',      label:tr('tab_overview') },
    { k:'profitability', label:tr('tab_profitability') },
    { k:'liquidity',     label:tr('liquidity') },
    { k:'efficiency',    label:tr('efficiency') },
    { k:'decisions',     label:tr('tab_decisions_v2'), badge:decs.length },
    { k:'alerts',        label:tr('alerts_title'), badge:highAlerts||null },
  ]

  if (!selectedId) return (
    <div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'60vh',
      flexDirection:'column',gap:12,background:'var(--bg-void)'}}>
      <span style={{fontSize:40,opacity:.2}}>📊</span>
      <span style={{fontSize:14,color:'var(--text-secondary)'}}>{tr('gen_select_company')}</span>
    </div>
  )

  return (
    <div className="" style={{padding:'18px 26px',display:'flex',flexDirection:'column',
      gap:14,minHeight:'calc(100vh - 62px)',background:'var(--bg-void)'}}>
      <style>{`@keyframes slideIn{from{transform:translateX(100%);opacity:0}to{transform:translateX(0);opacity:1}}@keyframes spin{to{transform:rotate(360deg)}}`}</style>

      <DrillBackBar detailLabel={tr('nav_drill_analysis')} />

      {/* Header */}
      <div style={{display:'flex',alignItems:'center',gap:10,flexWrap:'wrap'}}>
        <div style={{flex:1}}>
          <h1 style={{fontSize:20,fontWeight:800,color:'#ffffff',margin:0}}>{tr('nav_drill_analysis')}</h1>
          <p style={{fontSize:11,color:'var(--text-secondary)',margin:'3px 0 0'}}>
            {selectedCompany?.name} · {periods.at(-1)||'—'} {currency&&`· ${currency}`}
          </p>
        </div>
        <button type="button" onClick={()=>navigate('/statements',{state:{focus:'cashflow'}})}
            style={{padding:'7px 14px',borderRadius:8,border:'1px solid var(--border)',
              background:'var(--bg-elevated)',color:'#aab4c3',fontSize:11,fontWeight:500,cursor:'pointer'}}>
          {tr('nav_statements')} →
        </button>
        <button onClick={load} disabled={loading}
          style={{padding:'7px 12px',borderRadius:8,border:'1px solid var(--border)',
            background:'var(--bg-elevated)',color:'#aab4c3',fontSize:12,cursor:'pointer'}}>
          {loading ? (
            <span style={{ display: 'inline-block', width: 12, height: 12, border: '2px solid var(--border)', borderTopColor: 'var(--accent)', borderRadius: '50%', animation: 'spin .7s linear infinite', verticalAlign: 'middle' }} />
          ) : (
            '↻'
          )}
        </button>
          {/* ── Data Source Toggle ── */}
          <div style={{display:'flex',alignItems:'center',gap:0,background:'var(--bg-elevated)',
            border:'1px solid var(--border)',borderRadius:8,overflow:'hidden',flexShrink:0}}>
            {[{v:false,l:tr('company_uploads')},{v:true,l:tr('branch_consolidation')}].map(opt=>(
              <button key={String(opt.v)} onClick={()=>{setConsolidate(opt.v);setData(null)}}
                style={{padding:'5px 12px',fontSize:11,fontWeight:600,border:'none',cursor:'pointer',
                  background: consolidate===opt.v ? 'var(--accent)' : 'transparent',
                  color:      consolidate===opt.v ? '#000' : 'var(--text-secondary)',
                  transition: 'all .15s', whiteSpace:'nowrap'}}>
                {opt.l}
              </button>
            ))}
          </div>
      </div>
      {/* ── Data Source Banner ── */}
      {data && (
        <div style={{display:'flex',alignItems:'center',gap:8,padding:'6px 12px',
          borderRadius:8,fontSize:11,marginBottom:2,
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

      {err&&<div style={{padding:'10px 14px',background:'rgba(248,113,113,.1)',
        border:'1px solid var(--red)',borderRadius:9,fontSize:12,color:'var(--red)'}}>⚠ {err}</div>}
      {loading&&!data&&(
        <div style={{display:'flex',flexDirection:'column',gap:12,paddingTop:8}}>
          {/* Header skeleton */}
          <div style={{display:'grid',gridTemplateColumns:'auto 1fr 1fr 1fr',gap:10}}>
            <div style={{background:'var(--bg-panel)',borderRadius:13,padding:16,minWidth:110}}>
              <div className="skeleton" style={{width:80,height:80,borderRadius:'50%'}}/>
            </div>
            {[1,2,3].map(i=>(
              <div key={i} style={{background:'var(--bg-panel)',borderRadius:13,padding:'14px 16px'}}>
                <div className="skeleton skeleton-text" style={{width:'60%',marginBottom:10}}/>
                <div className="skeleton skeleton-num" style={{marginBottom:8}}/>
                <div className="skeleton" style={{height:28,width:'100%',borderRadius:4}}/>
              </div>
            ))}
          </div>
          {/* Issues + Opportunities skeleton */}
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14}}>
            {[1,2].map(i=>(
              <div key={i} style={{background:'var(--bg-panel)',borderRadius:13,padding:'16px'}}>
                <div className="skeleton skeleton-text" style={{width:'40%',marginBottom:14}}/>
                {[1,2,3].map(j=>(
                  <div key={j} style={{marginBottom:8}}>
                    <div className="skeleton skeleton-text" style={{width:'90%',marginBottom:5}}/>
                    <div className="skeleton skeleton-text" style={{width:'70%'}}/>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}

      {data&&<DataQualityBanner validation={validation} lang={lang} tr={tr}/>}
      {data&&(<>
        {/* Health + KPI strip */}
        <div style={{display:'grid',gridTemplateColumns:'auto 1fr 1fr 1fr',gap:10,alignItems:'stretch'}}>
          <Card style={{display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',minWidth:110,borderTop:`2px solid ${hc}`}}>
            <div style={{fontFamily:'var(--font-mono)',fontSize:36,fontWeight:800,color:hc,lineHeight:1}}>{health??'—'}</div>
            <div style={{fontSize:9,color:'var(--text-secondary)',marginTop:4}}>/100</div>
            <div style={{fontSize:10,fontWeight:700,color:hc,marginTop:6,textAlign:'center'}}>{tr(`status_${status}_simple`)}</div>
          </Card>
          <MetricCard label={kpiLabel(tr('fc_revenue'), ctxLabel(), tr)} value={formatCompactForLang(kpis.revenue?.value, lang)} fullValue={formatFullForLang(kpis.revenue?.value, lang)}
            lang={lang} tr={tr} momWord={tr('mom_label')}
            mom={kpis.revenue?.mom_pct} spark={series.revenue?.slice(-10)} color='var(--accent)' explain={kpiExplain.revenue}
            insight={(() => {
              const dir = trends?.revenue?.direction
              return dir === 'up' ? tr('trend_up')
                : dir === 'down' ? tr('trend_down')
                : dir === 'stable' ? tr('trend_stable')
                : null
            })()}
            cause={(()=>{const dec=(d?.decisions||[]).find(x=>x.domain==='growth');return dec?.reason?dec.reason.split('. ')[0].slice(0,60):null})()}
            forecast={kpiForecast('revenue', fcData, tr, (v) => formatCompactForLang(v, lang), lang)}/>
          <MetricCard label={kpiLabel(tr('fc_net_profit'), ctxLabel(), tr)} value={formatCompactForLang(kpis.net_profit?.value, lang)} fullValue={formatFullForLang(kpis.net_profit?.value, lang)}
            lang={lang} tr={tr} momWord={tr('mom_label')}
            mom={kpis.net_profit?.mom_pct} spark={series.net_profit?.slice(-10)} color='var(--green)' explain={kpiExplain.net_profit}
            insight={(() => {
              const st = ratios?.profitability?.net_margin_pct?.status
              return st ? tr(`kpi_margin_badge_${st}`) : null
            })()}
            cause={(() => {
              const gm = ratios?.profitability?.gross_margin_pct
              return gm?.value != null ? tr('dash_gross_margin_line', { value: formatPctForLang(gm.value, 1, lang) }) : null
            })()}
            forecast={kpiForecast('net_profit', fcData, tr, (v) => formatCompactForLang(v, lang), lang)}/>
          <MetricCard label={tr('net_margin')} value={formatPctForLang(kpis.net_margin?.value, 1, lang)}
            lang={lang} tr={tr} momWord={tr('mom_label')}
            mom={kpis.net_margin?.mom_pct} color='var(--violet)' explain={kpiExplain.margin}
            insight={(()=>{const ins=(d?.statements?.insights||[]).find(i=>i.key==='strong_gross_margin');return ins?ins.message.split('. ')[0]:null})()}
            cause={(()=>{const dec=(d?.decisions||[]).find(x=>x.domain==='profitability');return dec?.reason?dec.reason.split('. ')[0].slice(0,60):null})()}/>
        </div>

        {drillExtra ? (
          <DrillIntelligenceBlock
            {...analysisDrillLines('overview')}
            tr={tr}
            lang={lang}
          />
        ) : null}

        {/* TOP ISSUES + OPPORTUNITIES — always visible */}
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14}}>
          <Card style={{borderTop:'2px solid var(--red)'}}>
            <SectionHead label={tr('analysis_top_issues')} count={issues.length} color='var(--red)'
              sub={tr('analysis_top_issues_sub')}/>
            {issues.length===0
              ?<p style={{fontSize:12,color:'var(--text-secondary)',fontStyle:'italic'}}>{tr('analysis_no_critical_issues')}</p>
              :issues.map((iss,i)=><IssueCard key={i} issue={iss} tr={tr} lang={lang} onOpen={setSelDec}/>)}
          </Card>
          <Card style={{borderTop:'2px solid var(--green)'}}>
            <SectionHead label={tr('analysis_top_opps')} count={opps.length} color='var(--green)'
              sub={tr('analysis_top_opps_sub')}/>
            {opps.length===0
              ?<p style={{fontSize:12,color:'var(--text-secondary)',fontStyle:'italic'}}>{tr('analysis_more_data_required')}</p>
              :opps.map((opp,i)=><OpportunityCard key={i} opp={opp} tr={tr} lang={lang} onOpen={setSelDec}/>)}
          </Card>
        </div>

        {/* Tabs */}
        <div style={{display:'flex',gap:4,background:'var(--bg-elevated)',borderRadius:10,padding:3,width:'fit-content',flexWrap:'wrap'}}>
          {TABS.map(t=>(
            <button key={t.k} onClick={()=>goTab(t.k)}
              style={{padding:'6px 14px',borderRadius:8,border:'none',fontSize:11,fontWeight:700,
                cursor:'pointer',transition:'all .15s',position:'relative',
                background:tab===t.k?'var(--bg-panel)':'transparent',
                color:tab===t.k?'#ffffff':'var(--text-secondary)'}}>
              {t.label}
              {t.badge>0&&<span style={{position:'absolute',top:2,right:2,width:6,height:6,borderRadius:'50%',background:'var(--red)'}}/>}
            </button>
          ))}
        </div>

        {/* OVERVIEW */}
        {tab==='overview'&&(
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14}}>
            <Card>
              <SectionHead label={tr('exec_action_strip')} count={decs.length} color='var(--red)'
                sub={tr('exec_action_strip_sub')}/>
              {decs.length===0?<p style={{fontSize:12,color:'var(--text-secondary)'}}>—</p>
                :decs.slice(0,3).map((dec,i)=><DecCard key={i} dec={dec} tr={tr} lang={lang} impacts={impacts} onOpen={setSelDec}/>)}
            </Card>
            <Card>
              <SectionHead label={tr('exec_root_causes')} count={causes.filter(c=>c.impact==='high').length} color='var(--amber)'
                sub={tr('exec_root_causes_sub')}/>
              {causes.length===0?<p style={{fontSize:12,color:'var(--text-secondary)'}}>—</p>
                :causes.slice(0,4).map((c,i)=><CauseCard key={i} cause={c} lang={lang} tr={tr}/>)}
            </Card>
            <Card>
              <SectionHead label={tr('exec_breakdown')} color='var(--accent)'
                sub={tr('exec_breakdown_sub')}/>
              {Object.keys(liq).length>0&&<>
                <div style={{fontSize:10,fontWeight:700,color:'var(--text-secondary)',marginBottom:6,textTransform:'uppercase',letterSpacing:'.06em'}}>{tr('liquidity')}</div>
                {liq.current_ratio&&<RatioRow label={tr('current_ratio')} value={formatMultipleForLang(liq.current_ratio.value, 2, lang)} status={liq.current_ratio.status}
                  explain={liq.current_ratio.value>=1.5 ? tr('liq_sufficient') : tr('liq_needs_improvement')}/>}
                {liq.quick_ratio&&<RatioRow label={tr('quick_ratio')} value={formatMultipleForLang(liq.quick_ratio.value, 2, lang)} status={liq.quick_ratio.status}/>}
              </>}
              {Object.keys(prof).length>0&&<>
                <div style={{fontSize:10,fontWeight:700,color:'var(--text-secondary)',marginTop:10,marginBottom:6,textTransform:'uppercase',letterSpacing:'.06em'}}>{tr('profitability')}</div>
                {prof.net_margin_pct&&<RatioRow label={tr('net_margin')} value={formatPctForLang(prof.net_margin_pct.value, 1, lang)} status={prof.net_margin_pct.status}/>}
                {prof.gross_margin_pct&&<RatioRow label={tr('gross_margin')} value={formatPctForLang(prof.gross_margin_pct.value, 1, lang)} status={prof.gross_margin_pct.status}/>}
              </>}
            </Card>
            <Card>
              <SectionHead label={tr('cashflow_operating')} color='var(--blue)'
                sub={tr('cashflow_operating_sub')}/>
              <div style={{fontFamily:'var(--font-mono)',fontSize:26,fontWeight:800,
                color:cashflow.operating_cashflow>=0?'var(--green)':'var(--red)',direction:'ltr',marginBottom:6}}>
                {formatCompactForLang(cashflow.operating_cashflow, lang)}
              </div>
              {cashflow.operating_cashflow_mom!=null&&(
                <div style={{fontSize:11,color:clr(cashflow.operating_cashflow_mom),marginBottom:8}}>
                  {formatSignedPctForLang(Number(cashflow.operating_cashflow_mom), 1, lang)}{' '}
                  {tr('mom_short')}
                </div>
              )}
              <p style={{fontSize:11,color:'var(--text-secondary)',lineHeight:1.5,marginBottom:10}}>
                {cashflow.operating_cashflow>=0 ? tr('cashflow_positive') : tr('cashflow_negative')}
              </p>
              <button onClick={()=>navigate('/statements',{state:{focus:'cashflow'}})}
                style={{padding:'5px 12px',borderRadius:7,border:'1px solid var(--border)',background:'var(--bg-elevated)',color:'#aab4c3',fontSize:11,cursor:'pointer'}}>
                {tr('nav_statements')} →
              </button>
            </Card>
          </div>
        )}

        {/* PROFITABILITY */}
        {tab==='profitability'&&(
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14}}>
            {drillExtra ? (
              <div style={{ gridColumn: '1 / -1' }}>
                <DrillIntelligenceBlock {...analysisDrillLines('profitability')} tr={tr} lang={lang} />
              </div>
            ) : null}
            {Object.keys(prof).filter((k) => prof[k]?.value != null).length === 0 && drillExtra ? (
              <Card style={{ gridColumn: '1 / -1', borderTop: '2px solid var(--amber)' }}>
                <SectionHead label={tr('exec_kpi_title')} color="var(--amber)" sub={tr('drill_intel_tab_fallback_hint')} />
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, marginTop: 8 }}>
                  {[
                    { k: 'revenue', v: kpis.revenue?.value },
                    { k: 'net_profit', v: kpis.net_profit?.value },
                    { k: 'expenses', v: kpis.expenses?.value },
                  ].map(({ k, v }) => (
                    <div key={k} style={{ minWidth: 120 }}>
                      <div style={{ fontSize: 9, color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>
                        {tr(`kpi_label_${k}`)}
                      </div>
                      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 16, fontWeight: 800, direction: 'ltr' }}>
                        {v != null && Number.isFinite(Number(v)) ? formatCompactForLang(Number(v), lang) : '—'}
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            ) : null}
            <div style={{display:'flex',flexDirection:'column',gap:14}}>
              <Card>
                <SectionHead label={tr('profitability')} color='var(--green)'
                  sub={tr('profitability_how_rev_to_profit_sub')}/>
                {Object.entries(prof).filter(([,r])=>r?.value!=null).map(([k,r])=>(
                  <RatioRow key={k} label={tr(k)||k.replace(/_/g,' ')} value={fmtV(k,r.value)} status={r.status}/>
                ))}
              </Card>
              {alerts.filter(a=>a.impact==='profitability').length>0&&(
                <Card>
                  <SectionHead label={tr('alerts_title')} color='var(--amber)'/>
                  {alerts.filter(a=>a.impact==='profitability').map((a,i)=><AlertCard key={i} alert={a} tr={tr} lang={lang}/>)}
                </Card>
              )}
            </div>
            <div style={{display:'flex',flexDirection:'column',gap:14}}>
              {causes.filter(c=>c.domain==='profitability').length>0&&(
                <Card>
                  <SectionHead label={tr('exec_why')} color='var(--red)'
                    sub={tr('profitability_root_causes_sub')}/>
                  {causes.filter(c=>c.domain==='profitability').map((c,i)=><CauseCard key={i} cause={c} lang={lang} tr={tr}/>)}
                </Card>
              )}
              {decs.filter(d=>d.domain==='profitability').length>0&&(
                <Card>
                  <SectionHead label={tr('exec_actions')} color='var(--accent)'/>
                  {decs.filter(d=>d.domain==='profitability').map((dec,i)=>(
                    <DecCard key={i} dec={dec} tr={tr} lang={lang} impacts={impacts} onOpen={setSelDec}/>
                  ))}
                </Card>
              )}
            </div>
          </div>
        )}

        {/* LIQUIDITY */}
        {tab==='liquidity'&&(
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14}}>
            {drillExtra ? (
              <div style={{ gridColumn: '1 / -1' }}>
                <DrillIntelligenceBlock {...analysisDrillLines('liquidity')} tr={tr} lang={lang} />
              </div>
            ) : null}
            {Object.keys(liq).filter((k) => liq[k]?.value != null).length === 0 && drillExtra ? (
              <Card style={{ gridColumn: '1 / -1', borderTop: '2px solid var(--amber)' }}>
                <SectionHead label={tr('liquidity')} color="var(--blue)" sub={tr('drill_intel_tab_fallback_hint')} />
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 20, fontWeight: 800, direction: 'ltr', color: 'var(--accent)' }}>
                  {cashflow?.operating_cashflow != null ? formatCompactForLang(cashflow.operating_cashflow, lang) : '—'}
                </div>
                <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 8 }}>{tr('cashflow_operating_sub')}</p>
              </Card>
            ) : null}
            <div style={{display:'flex',flexDirection:'column',gap:14}}>
              <Card>
                <SectionHead label={tr('liquidity')} color='var(--blue)'
                  sub={tr('liquidity_sub')}/>
                {Object.entries(liq).filter(([,r])=>r?.value!=null).map(([k,r])=>(
                  <RatioRow key={k} label={tr(k)||k.replace(/_/g,' ')} value={fmtV(k,r.value)} status={r.status}/>
                ))}
              </Card>
              <Card>
                <SectionHead label={tr('cashflow_operating')} color='var(--blue)'/>
                <div style={{fontFamily:'var(--font-mono)',fontSize:22,fontWeight:800,
                  color:cashflow.operating_cashflow>=0?'var(--green)':'var(--red)',direction:'ltr'}}>
                  {formatCompactForLang(cashflow.operating_cashflow, lang)}
                </div>
              </Card>
            </div>
            <div style={{display:'flex',flexDirection:'column',gap:14}}>
              {causes.filter(c=>['liquidity','cross_domain'].includes(c.domain)).length>0&&(
                <Card>
                  <SectionHead label={tr('exec_why')} color='var(--red)'
                    sub={tr('liquidity_why_sub')}/>
                  {causes.filter(c=>['liquidity','cross_domain'].includes(c.domain)).map((c,i)=><CauseCard key={i} cause={c} lang={lang} tr={tr}/>)}
                </Card>
              )}
              {decs.filter(d=>d.domain==='liquidity').length>0&&(
                <Card>
                  <SectionHead label={tr('exec_actions')} color='var(--accent)'/>
                  {decs.filter(d=>d.domain==='liquidity').map((dec,i)=>(
                    <DecCard key={i} dec={dec} tr={tr} lang={lang} impacts={impacts} onOpen={setSelDec}/>
                  ))}
                </Card>
              )}
            </div>
          </div>
        )}

        {/* EFFICIENCY */}
        {tab==='efficiency'&&(
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14}}>
            {drillExtra ? (
              <div style={{ gridColumn: '1 / -1' }}>
                <DrillIntelligenceBlock {...analysisDrillLines('efficiency')} tr={tr} lang={lang} />
              </div>
            ) : null}
            {Object.keys(eff).filter((k) => eff[k]?.value != null).length === 0 &&
            Object.keys(lev).filter((k) => lev[k]?.value != null).length === 0 &&
            drillExtra ? (
              <Card style={{ gridColumn: '1 / -1', borderTop: '2px solid var(--amber)' }}>
                <SectionHead label={tr('efficiency')} color="var(--violet)" sub={tr('drill_intel_tab_fallback_hint')} />
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, marginTop: 8 }}>
                  <div>
                    <div style={{ fontSize: 9, color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>
                      {tr('kpi_label_expenses')}
                    </div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 16, fontWeight: 800, direction: 'ltr' }}>
                      {kpis.expenses?.value != null ? formatCompactForLang(kpis.expenses.value, lang) : '—'}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 9, color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>
                      {tr('net_margin')}
                    </div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 16, fontWeight: 800, direction: 'ltr' }}>
                      {kpis.net_margin?.value != null ? formatPctForLang(kpis.net_margin.value, 1, lang) : '—'}
                    </div>
                  </div>
                </div>
              </Card>
            ) : null}
            <div style={{display:'flex',flexDirection:'column',gap:14}}>
              <Card>
                <SectionHead label={tr('efficiency')} color='var(--violet)'
                  sub={tr('efficiency_sub')}/>
                {Object.entries(eff).filter(([,r])=>r?.value!=null).map(([k,r])=>(
                  <RatioRow key={k} label={tr(k)||k.replace(/_/g,' ')} value={fmtV(k,r.value)} status={r.status}/>
                ))}
              </Card>
              <Card>
                <SectionHead label={tr('leverage')} color='var(--amber)'
                  sub={tr('leverage_sub')}/>
                {Object.entries(lev).filter(([,r])=>r?.value!=null).map(([k,r])=>(
                  <RatioRow key={k} label={tr(k)||k.replace(/_/g,' ')} value={fmtV(k,r.value)} status={r.status}/>
                ))}
              </Card>
            </div>
            <div style={{display:'flex',flexDirection:'column',gap:14}}>
              {causes.filter(c=>['efficiency','leverage'].includes(c.domain)).length>0&&(
                <Card>
                  <SectionHead label={tr('exec_root_causes')} color='var(--amber)'
                    sub={tr('efficiency_leverage_root_causes_sub')}/>
                  {causes.filter(c=>['efficiency','leverage'].includes(c.domain)).map((c,i)=><CauseCard key={i} cause={c} lang={lang} tr={tr}/>)}
                </Card>
              )}
              {decs.filter(d=>['efficiency','leverage'].includes(d.domain)).length>0&&(
                <Card>
                  <SectionHead label={tr('exec_actions')} color='var(--accent)'/>
                  {decs.filter(d=>['efficiency','leverage'].includes(d.domain)).map((dec,i)=>(
                    <DecCard key={i} dec={dec} tr={tr} lang={lang} impacts={impacts} onOpen={setSelDec}/>
                  ))}
                </Card>
              )}
            </div>
          </div>
        )}

        {/* DECISIONS */}
        {tab==='decisions'&&(
          <div style={{maxWidth:760}}>
            {drillExtra ? <DrillIntelligenceBlock {...analysisDrillLines('decisions')} tr={tr} lang={lang} /> : null}
            <SectionHead label={tr('exec_action_strip')} count={decs.length} color='var(--red)'
              sub={tr('exec_action_strip_ranked_sub')}/>
            {decs.length===0
              ? (
                <Card style={{ borderTop: '2px solid var(--amber)', marginTop: 12 }}>
                  <p style={{ color: 'var(--text-secondary)', fontSize: 12, margin: 0 }}>{tr('drill_intel_tab_fallback_hint')}</p>
                  {drillBundle?.primaryResolution?.kind === 'expense' && drillBundle.primaryResolution.expense?.title ? (
                    <p style={{ fontSize: 13, fontWeight: 700, marginTop: 10 }}>
                      <CmdServerText lang={lang} tr={tr}>{drillBundle.primaryResolution.expense.title}</CmdServerText>
                    </p>
                  ) : null}
                </Card>
              )
              :decs.map((dec,i)=><DecCard key={i} dec={dec} tr={tr} lang={lang} impacts={impacts} onOpen={setSelDec}/>)}
          </div>
        )}

        {/* ALERTS */}
        {tab==='alerts'&&(
          <div style={{maxWidth:760}}>
            {drillExtra ? <DrillIntelligenceBlock {...analysisDrillLines('alerts')} tr={tr} lang={lang} /> : null}
            <SectionHead label={tr('alerts_title')} count={alerts.length} color='var(--amber)'
              sub={tr('alerts_by_severity_sub')}/>
            {alerts.length===0
              ? (
                <Card style={{ borderTop: '2px solid var(--amber)', marginTop: 12 }}>
                  <p style={{ color: 'var(--text-secondary)', fontSize: 12, margin: 0 }}>{tr('drill_intel_do_fallback')}</p>
                  {health != null ? (
                    <p style={{ fontFamily: 'var(--font-mono)', fontSize: 18, fontWeight: 800, marginTop: 10, direction: 'ltr' }}>
                      {tr('drill_intel_health_score', { v: String(Math.round(health)) })}
                    </p>
                  ) : null}
                </Card>
              )
              :alerts.map((a,i)=><AlertCard key={i} alert={a} tr={tr} lang={lang}/>)}
            {causes.length>0&&<>
              <div style={{height:14}}/>
              <SectionHead label={tr('exec_root_causes')} count={causes.length} color='var(--amber)'/>
              {causes.slice(0,5).map((c,i)=><CauseCard key={i} cause={c} lang={lang} tr={tr}/>)}
            </>}
          </div>
        )}
      </>)}

      <DecisionPanel dec={selDec} impacts={impacts} tr={tr} lang={lang} onClose={()=>setSelDec(null)}/>
    </div>
  )
}
