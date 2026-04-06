/**
 * Statements.jsx — Phase 3: formal statement reading path
 * Statement (structured variance table) → Interpretation (deltas + bridge + story) → Margin & supporting.
 *
 * Data: /executive — structured_income_statement_*, structured_profit_bridge, structured_profit_story;
 * d.statement_hierarchy (root overlay, same bundle as Command Center) for drill trees;
 * d.statements for flat BS/CF summary rows and fallback IS comparison.
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useLang }        from '../context/LangContext.jsx'
import CmdServerText from '../components/CmdServerText.jsx'
import StructuredFinancialLayers, {
  formatStructuredProfitStoryForPrompt,
} from '../components/StructuredFinancialLayers.jsx'
import { StatementHierarchyTree } from '../components/StatementHierarchyTree.jsx'
import { useCompany }     from '../context/CompanyContext.jsx'
import { usePeriodScope } from '../context/PeriodScopeContext.jsx'
import { buildAnalysisQuery } from '../utils/buildAnalysisQuery.js'

import { safeIncludes } from '../utils/dataGuards.js'
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

// ── Formatters ────────────────────────────────────────────────────────────────
const fmtD  = (v,base) => { if(v==null||base==null||base===0)return null; return v-base }
const fmtDp = (v,base) => { if(v==null||base==null||base===0)return null; return ((v-base)/Math.abs(base))*100 }
const clrV  = v => v==null?'var(--text-secondary)':v>0?'var(--green)':v<0?'var(--red)':'var(--text-secondary)'
const clrVi = (v,inv) => inv?clrV(-v):clrV(v)  // inverted for costs
const urgC  = {high:'var(--red)',medium:'var(--amber)',low:'var(--blue)',info:'var(--green)'}
const domC  = {liquidity:'var(--blue)',profitability:'var(--green)',efficiency:'var(--violet)',leverage:'var(--amber)',growth:'var(--accent)'}
const stC   = {excellent:'var(--green)',good:'var(--accent)',warning:'var(--amber)',risk:'var(--red)',neutral:'var(--text-secondary)'}

function statementsSeverityLabel(tr, sev) {
  const s = String(sev || 'info').toLowerCase()
  return tr(`severity_${s}`)
}

function statementsDomainLabel(tr, dom) {
  if (!dom) return ''
  const map = {
    liquidity: 'domain_liquidity_simple',
    profitability: 'domain_profitability_simple',
    efficiency: 'domain_efficiency_simple',
    leverage: 'domain_leverage_simple',
    growth: 'domain_growth_simple',
  }
  const k = map[dom]
  return k ? tr(k) : dom
}

// ── Shared badge ──────────────────────────────────────────────────────────────
const Badge = ({label,color}) => (
  <span style={{fontSize:9,fontWeight:800,padding:'2px 7px',borderRadius:20,
    background:`${color}18`,color,border:`1px solid ${color}30`,
    textTransform:'uppercase',letterSpacing:'.05em',flexShrink:0}}>
    {label}
  </span>
)

const Card = ({children,style={}}) => (
  <div style={{
    background:'var(--bg-panel)',
    border:'1px solid var(--border)',
    borderRadius:13,padding:'16px 18px',
    transition:'box-shadow 0.2s ease, border-color 0.2s ease',
    ...style
  }}>{children}</div>
)

function SectionHead({label,color='var(--accent)',sub}) {
  return (
    <div style={{marginBottom:12}}>
      <div style={{display:'flex',alignItems:'center',gap:8}}>
        <div style={{width:20,height:2,background:color,borderRadius:2}}/>
        <span style={{fontSize:10,fontWeight:800,color,textTransform:'uppercase',letterSpacing:'.08em'}}>{label}</span>
      </div>
      {sub&&<p style={{fontSize:11,color:'var(--text-secondary)',margin:'4px 0 0 28px',lineHeight:1.5}}>{sub}</p>}
    </div>
  )
}

// ── Comparison row: label | current | prior | variance | variance% ─────────
function CmpRow({ label, cur, prior, bold, color, invertColor, pct, onClick, indent, lang }) {
  const delta  = fmtD(cur,prior)
  const deltap = fmtDp(cur,prior)
  const dc     = invertColor ? clrVi(delta,true) : clrV(delta)
  const fmtPcell = (v) => (v == null ? '—' : formatPctForLang(v, 1, lang))
  return (
    <div onClick={onClick}
      style={{display:'grid',gridTemplateColumns:'1fr 90px 90px 80px 70px',
        gap:4,padding:'8px 0',borderBottom:'1px solid var(--border)',
        cursor:onClick?'pointer':'default',alignItems:'center',
        paddingLeft:indent?16:0}}>
      <span style={{fontSize:bold?13:12,fontWeight:bold?700:400,
        color:bold?'#fff':'var(--text-secondary)',overflow:'hidden',textOverflow:'clip',whiteSpace:'nowrap'}}>
        {label}
      </span>
      {/* Current */}
      <span style={{fontFamily:'var(--font-mono)',fontSize:bold?13:12,fontWeight:bold?800:500,
        color:color||'var(--text-primary)',textAlign:'right',direction:'ltr'}}>
        {pct ? fmtPcell(cur) : formatCompactForLang(cur, lang)}
      </span>
      {/* Prior */}
      <span style={{fontFamily:'var(--font-mono)',fontSize:11,
        color:'var(--text-secondary)',textAlign:'right',direction:'ltr'}}>
        {prior != null ? (pct ? fmtPcell(prior) : formatCompactForLang(prior, lang)) : '—'}
      </span>
      {/* Variance absolute */}
      <span style={{fontFamily:'var(--font-mono)',fontSize:11,color:dc,textAlign:'right',direction:'ltr'}}>
        {delta != null ? `${delta > 0 ? '+' : ''}${formatCompactForLang(delta, lang)}` : '—'}
      </span>
      {/* Variance % */}
      <span style={{fontFamily:'var(--font-mono)',fontSize:10,
        color:dc,textAlign:'right',direction:'ltr'}}>
        {deltap != null
          ? deltap > 0
            ? `+${formatPctForLang(deltap, 1, lang)}`
            : formatPctForLang(deltap, 1, lang)
          : '—'}
      </span>
    </div>
  )
}

// Column headers for comparison table
function CmpHeader({lang,priorLabel,tr}) {
  return (
    <div style={{display:'grid',gridTemplateColumns:'1fr 90px 90px 80px 70px',
      gap:4,padding:'5px 0 8px',borderBottom:'2px solid var(--border)'}}>
      {['',
        tr('cmp_current'),
        priorLabel || tr('cmp_prior'),
        tr('cmp_variance'),
        '%'
      ].map((h,i)=>(
        <span key={i} style={{fontSize:9,fontWeight:700,color:'var(--text-secondary)',
          textTransform:'uppercase',letterSpacing:'.06em',textAlign:i>0?'right':'left'}}>
          {h}
        </span>
      ))}
    </div>
  )
}

// ── Mini sparkline bar chart ──────────────────────────────────────────────────
function Spark({data=[],color='var(--accent)',h=36}) {
  if(!data||data.length<2) return null
  const vals = data.filter(v=>v!=null)
  if(!vals.length) return null
  const min = Math.min(...vals), max = Math.max(...vals)
  const range = max-min||1
  const w = 6, gap = 3
  const total = data.length*(w+gap)-gap
  return (
    <svg width={total} height={h} style={{display:'block'}}>
      {data.map((v,i)=>{
        if(v==null)return null
        const barH = Math.max(2,((v-min)/range)*(h-4))
        const x = i*(w+gap)
        return <rect key={i} x={x} y={h-barH} width={w} height={barH}
          rx={2} fill={color} opacity={i===data.length-1?1:0.5}/>
      })}
    </svg>
  )
}

// ── Insight card ──────────────────────────────────────────────────────────────
function InsightCard({ins,onClick,lang,tr}) {
  const uc = urgC[ins.severity]||'var(--text-secondary)'
  return (
    <div onClick={onClick}
      style={{background:'var(--bg-elevated)',border:`1px solid ${uc}20`,
        borderLeft:`3px solid ${uc}`,borderRadius:9,padding:'11px 13px',
        cursor:'pointer',transition:'background .12s',marginBottom:6}}
      onMouseEnter={e=>{e.currentTarget.style.background='var(--bg-panel)';e.currentTarget.style.transform='translateX(2px)'}}
      onMouseLeave={e=>{e.currentTarget.style.background='var(--bg-elevated)';e.currentTarget.style.transform='none'}}>
      <div style={{display:'flex',alignItems:'center',gap:7,marginBottom:5}}>
        <Badge label={statementsSeverityLabel(tr, ins.severity)} color={uc}/>
        {ins.domain ? <Badge label={statementsDomainLabel(tr, ins.domain)} color={domC[ins.domain]||'var(--accent)'}/> : null}
        <span style={{marginLeft:'auto',fontSize:9,color:'var(--accent)'}}>→</span>
      </div>
      <p style={{fontSize:11,color:'var(--text-secondary)',lineHeight:1.6,margin:0}}>
        <CmdServerText lang={lang} tr={tr}>{ins.message}</CmdServerText>
      </p>
    </div>
  )
}

// ── Ratio row ─────────────────────────────────────────────────────────────────
function RatioRow({ label, value, status, unit, lang }) {
  const sc = status === 'good' ? 'var(--green)' : status === 'warning' ? 'var(--amber)' : 'var(--red)'
  let disp = '—'
  if (value != null && Number.isFinite(Number(value))) {
    if (unit === '%') disp = formatPctForLang(value, 2, lang)
    else if (unit === 'x') disp = formatMultipleForLang(value, 2, lang)
    else if (unit === 'd' || unit === 'days') disp = formatDays(value)
    else disp = formatCompactForLang(value, lang)
  }
  return (
    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',
      padding:'8px 0',borderBottom:'1px solid var(--border)'}}>
      <span style={{fontSize:11,color:'var(--text-secondary)'}}>{label}</span>
      <span style={{fontFamily:'var(--font-mono)',fontSize:13,fontWeight:700,color:sc,direction:'ltr'}}>
        {disp}
      </span>
    </div>
  )
}

// ── Context side panel ────────────────────────────────────────────────────────
function ContextPanel({item,decs,tr,lang,onClose}) {
  if(!item) return null
  const uc = urgC[item.severity]||'var(--text-secondary)'
  const linked = (decs||[]).filter(d=>d.domain===item.domain).slice(0,2)
  return (
    <div style={{position:'fixed',inset:0,zIndex:900,display:'flex'}}
      onClick={onClose}>
      <div style={{flex:1}}/>
      <div style={{width:420,background:'var(--bg-surface)',
        borderLeft:'1px solid var(--border-bright)',
        padding:24,overflowY:'auto',animation:'slideIn .25s ease',
        boxShadow:'-20px 0 60px rgba(0,0,0,.6)',}}
        onClick={e=>e.stopPropagation()}>
        <div style={{display:'flex',justifyContent:'space-between',marginBottom:16}}>
          <div style={{display:'flex',gap:8}}>
            <Badge label={statementsSeverityLabel(tr, item.severity)} color={uc}/>
            {item.domain&&<Badge label={statementsDomainLabel(tr, item.domain)} color={domC[item.domain]||'var(--accent)'}/>}
          </div>
          <button onClick={onClose} style={{background:'transparent',border:'none',
            color:'var(--text-secondary)',fontSize:18,cursor:'pointer'}}>✕</button>
        </div>
        <p style={{fontSize:13,color:'var(--text-secondary)',lineHeight:1.7,marginBottom:16}}>
          <CmdServerText lang={lang} tr={tr}>{item.message}</CmdServerText>
        </p>
        {item.why&&<div style={{fontSize:12,color:'var(--text-secondary)',lineHeight:1.6,marginBottom:12}}>
          <strong style={{color:'#fff'}}>{tr('why_label')}</strong>
          <CmdServerText lang={lang} tr={tr}>{item.why}</CmdServerText>
        </div>}
        {item.recommendation&&<div style={{padding:'10px 12px',background:'rgba(99,102,241,.08)',
          border:'1px solid rgba(99,102,241,.2)',borderRadius:8,fontSize:12,
          color:'var(--accent)',lineHeight:1.6,marginBottom:16}}>
          💡 <CmdServerText lang={lang} tr={tr}>{item.recommendation}</CmdServerText>
        </div>}
        {linked.length>0&&<>
          <div style={{fontSize:10,fontWeight:700,color:'var(--text-secondary)',
            textTransform:'uppercase',letterSpacing:'.06em',marginBottom:8}}>
            {tr('linked_decisions')}
          </div>
          {linked.map((d,i)=>(
            <div key={i} style={{padding:'10px 12px',background:'var(--bg-elevated)',
              borderRadius:9,fontSize:12,color:'var(--text-secondary)',lineHeight:1.6,
              marginBottom:6,border:'1px solid var(--border)'}}>
              <CmdServerText lang={lang} tr={tr}>{d.title||d.action}</CmdServerText>
            </div>
          ))}
        </>}
        <button onClick={onClose}
          style={{width:'100%',marginTop:16,padding:'9px',borderRadius:8,border:'none',
            background:'var(--bg-elevated)',color:'var(--text-secondary)',fontSize:13,cursor:'pointer'}}>
          {tr('close')}
        </button>
      </div>
    </div>
  )
}

// ── Data Quality Banner ───────────────────────────────────────────────────────
function DataQualityBanner({validation,lang,tr}) {
  if(!validation) return null
  const {consistent,warnings=[],has_errors,has_info} = validation
  if(consistent===true&&!has_info) return null
  const color = has_errors?'var(--red)':'var(--amber)'
  const bg    = has_errors?'rgba(248,113,113,0.06)':'rgba(251,191,36,0.06)'
  const bdr   = has_errors?'rgba(248,113,113,0.25)':'rgba(251,191,36,0.25)'
  return (
    <div style={{padding:'8px 14px',borderRadius:9,marginBottom:10,
      background:bg,borderWidth:'1px 1px 1px 3px',borderStyle:'solid',borderColor:`${bdr} ${bdr} ${bdr} ${color}`,
      display:'flex',flexWrap:'wrap',alignItems:'center',gap:10}}>
      <span style={{fontSize:12}}>{has_errors?'⚠':'ℹ'}</span>
      <span style={{fontSize:10,fontWeight:800,color,letterSpacing:'.04em'}}>
        {has_errors ? tr('dq_warning_title') : tr('dq_notice_title')}:
      </span>
      {warnings.map((w,i)=>{return(
        <span key={i} style={{fontSize:10,color:'var(--text-secondary)'}}>
          · {tr(`dq_${w.code}`)}
        </span>
      )})}
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  Main Component
// ══════════════════════════════════════════════════════════════════════════════
export default function Statements() {
  const { tr, lang } = useLang()
  const { selectedId, selectedCompany } = useCompany()
  const { params: ps, toQueryString:scopeQS, setResolved, isIncompleteCustom, window: win } = usePeriodScope()
  const navigate = useNavigate()
  const location = useLocation()

  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(false)
  const [consolidate, setConsolidate] = useState(false)
  const [err,     setErr]     = useState(null)
  const [tab,     setTab]     = useState('income')
  const [panel,   setPanel]   = useState(null)
  const [cmpMode, setCmpMode] = useState('mom') // mom | yoy | prior_ytd

  useEffect(()=>{ if(location.state?.focus) setTab(location.state.focus) },[location.state])

  const load = useCallback(async () => {
    if(!selectedId) return
    if(isIncompleteCustom()) return
    const qs = buildAnalysisQuery(scopeQS, { lang, window: win, consolidate })
    if(qs===null) return
    setLoading(true); setErr(null)
    try {
      const r = await fetch(`${API}/analysis/${selectedId}/executive?${qs}`,{headers:auth()})
      if(!r.ok){setErr(`Error ${r.status}`);return}
      const json = await r.json()
      setData(json)
      setResolved(json.meta?.scope||null)
    } catch(e){setErr(e.message)}
    finally{setLoading(false)}
  },[selectedId,lang,consolidate,win,scopeQS,setResolved,isIncompleteCustom])

  useEffect(()=>{ load() },[selectedId,load])

  // ── Data extraction (single source of truth) ─────────────────────────────
  const d       = data?.data || {}
  const stmtHier = d.statement_hierarchy || null
  const stmts   = d.statements || {}
  const is_     = stmts.income_statement || {}
  const bs_     = stmts.balance_sheet    || {}
  const cf_     = stmts.cashflow         || {}
  const ser     = stmts.series           || {}
  const insights= stmts.insights         || []
  const decs    = d.decisions            || []
  const series  = d.kpi_block?.series    || {}
  const intel   = d.intelligence         || {}
  const ratios  = intel.ratios           || {}
  const trends  = intel.trends           || {}
  const health  = d.health_score_v2
  const validation = data?.meta?.pipeline_validation
  const period  = stmts.period || data?.meta?.periods?.slice(-1)[0] || '—'

  const cfReliability = cf_.reliability || 'estimated'
  const cfEstimated   = cfReliability === 'estimated'
  const bsWarning     = bs_.balance_warning

  // Prior period from kpi_block series
  const serLen    = (series.revenue||[]).length
  const priorIdx  = serLen >= 2 ? serLen-2 : null
  const prior     = {
    revenue:    priorIdx!=null ? series.revenue?.[priorIdx]    : null,
    net_profit: priorIdx!=null ? series.net_profit?.[priorIdx] : null,
    cashflow:   priorIdx!=null ? (d.kpi_block?.mom_series?.ocf?.[priorIdx]||null) : null,
  }

  // Comparison label for header
  const priorLabel = tr(`cmp_${cmpMode}`)

  // Health color
  const healthC = health!=null?(health>=80?'var(--green)':health>=60?'var(--amber)':'var(--red)'):'var(--text-secondary)'

  const bizStatus = String(intel.status || 'neutral').toLowerCase()
  const bizStateColor = stC[bizStatus] || stC.neutral

  const headerSummaryLine = useMemo(() => {
    if (!data) return ''
    const parts = formatStructuredProfitStoryForPrompt(d?.structured_profit_story, tr)
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean)
    return parts[0] || tr('stmt_header_summary_fallback')
  }, [data, d, tr])

  const hasStructuredVariance =
    d.structured_income_statement_variance &&
    typeof d.structured_income_statement_variance === 'object' &&
    Object.keys(d.structured_income_statement_variance).length > 0

  const cfFlagClr = cf_.reliability==='good'?'var(--green)':cf_.reliability==='warning'?'var(--amber)':'var(--red)'

  const TABS = [
    { k:'income',   label:tr('stmt_section_is') },
    { k:'balance',  label:tr('stmt_section_bs') },
    { k:'cashflow', label:tr('cashflow_operating') },
    { k:'insights', label:tr('analysis_top_issues'),
      badge:insights.filter(x=>x.severity==='high').length||null },
  ]

  const l = lang||'en'

  if(!selectedId) return (
    <div style={{display:'flex',alignItems:'center',justifyContent:'center',
      height:'60vh',flexDirection:'column',gap:12,background:'var(--bg-void)'}}>
      <span style={{fontSize:40,opacity:.2}}>📊</span>
      <span style={{fontSize:14,color:'var(--text-secondary)'}}>{tr('gen_select_company')}</span>
    </div>
  )

  return (
    <div className="" style={{padding:'16px 24px',display:'flex',flexDirection:'column',
      gap:12,minHeight:'calc(100vh - 62px)',background:'var(--bg-void)'}}>
      <style>{`
        @keyframes slideIn{from{transform:translateX(100%);opacity:0}to{transform:translateX(0);opacity:1}}
        @keyframes spin{to{transform:rotate(360deg)}}
        .stmt-supporting-details > summary,.stmt-priority-details > summary{list-style:none;cursor:pointer}
        .stmt-supporting-details > summary::-webkit-details-marker,.stmt-priority-details > summary::-webkit-details-marker{display:none}
      `}</style>

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div style={{display:'flex',alignItems:'center',gap:10,flexWrap:'wrap'}}>
        <div style={{flex:1}}>
          <h1 style={{fontSize:20,fontWeight:800,color:'#fff',margin:0}}>
            {tr('stmt_page_title')}
          </h1>
          <p style={{fontSize:11,color:'var(--text-secondary)',margin:'3px 0 0'}}>
            {tr('stmt_page_subtitle')}
          </p>
        </div>
        {/* Comparison mode selector */}
        <div style={{display:'flex',gap:3,background:'var(--bg-elevated)',
          borderRadius:8,padding:2}}>
          {[['mom',tr('cmp_mom_short')],['yoy',tr('cmp_yoy_short')]].map(([k,lbl])=>(
            <button key={k} onClick={()=>setCmpMode(k)}
              style={{padding:'4px 12px',borderRadius:7,border:'none',fontSize:10,
                fontWeight:700,cursor:'pointer',transition:'all .15s',
                background:cmpMode===k?'var(--bg-panel)':'transparent',
                color:cmpMode===k?'#fff':'var(--text-secondary)'}}>
              {lbl}
            </button>
          ))}
        </div>
        {[['← '+tr('nav_back_command_center'),'/'],['↗ '+tr('nav_drill_analysis'),'/analysis']].map(([lbl,path])=>(
          <button key={path} type="button" onClick={()=>navigate(path, path==='/analysis'?{state:{focus:'overview'}}:undefined)}
            style={{padding:'6px 12px',borderRadius:8,border:'1px solid var(--border)',
              background:'var(--bg-elevated)',color:'#aab4c3',fontSize:11,cursor:'pointer'}}>
            {lbl}
          </button>
        ))}
        <button onClick={load} disabled={loading}
          style={{padding:'6px 11px',borderRadius:8,border:'1px solid var(--border)',
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
        border:'1px solid var(--red)',borderRadius:9,fontSize:12,color:'var(--red)'}}>
        ⚠ {err}
      </div>}

      {loading&&!data&&(
        <div style={{display:'flex',flexDirection:'column',gap:12,paddingTop:8}}>
          <div style={{background:'var(--bg-panel)',borderRadius:13,padding:16,minHeight:88,borderTop:'2px solid var(--border)'}}>
            <div className="skeleton skeleton-text" style={{width:'35%',marginBottom:10}}/>
            <div className="skeleton" style={{height:14,width:'92%',borderRadius:4}}/>
          </div>
          <div style={{background:'var(--bg-panel)',borderRadius:13,padding:20,minHeight:200}}>
            <div className="skeleton skeleton-text" style={{width:'28%',marginBottom:16}}/>
            {[1,2,3,4,5,6].map(i=><div key={i} className="skeleton skeleton-text" style={{marginBottom:10}}/>)}
          </div>
        </div>
      )}

      {data&&stmts.available&&(
        <Card style={{
          borderTop:`2px solid ${healthC}`,padding:'14px 18px',marginBottom:0,
        }}>
          <div style={{display:'flex',flexWrap:'wrap',alignItems:'flex-start',gap:16}}>
            <div style={{flex:'1 1 220px',minWidth:0}}>
              <div style={{
                fontSize:10,fontWeight:800,color:'var(--text-secondary)',textTransform:'uppercase',letterSpacing:'.08em',
              }}>
                {TABS.find(t=>t.k===tab)?.label} · {period}
              </div>
              <div style={{fontSize:15,fontWeight:800,color:'#fff',marginTop:4}}>{selectedCompany?.name}</div>
              <p style={{fontSize:12,color:'var(--text-secondary)',margin:'8px 0 0',lineHeight:1.5}}>
                <CmdServerText lang={lang} tr={tr}>{headerSummaryLine}</CmdServerText>
              </p>
            </div>
            <div style={{display:'flex',alignItems:'center',gap:16,flexShrink:0,flexWrap:'wrap'}}>
              <div style={{textAlign:'center',minWidth:72}}>
                <div style={{fontSize:9,color:'var(--text-secondary)',textTransform:'uppercase',letterSpacing:'.06em',fontWeight:700}}>
                  {tr('health_score')}
                </div>
                <div style={{fontFamily:'var(--font-mono)',fontSize:24,fontWeight:800,color:healthC,direction:'ltr',lineHeight:1.2}}>
                  {health!=null?health:'—'}
                </div>
                <div style={{fontSize:9,color:healthC,fontWeight:600}}>
                  {health!=null?tr(`health_tier_${health>=80?'excellent':health>=60?'good':health>=40?'warning':'risk'}`):'—'}
                </div>
              </div>
              <div style={{paddingLeft:14,borderLeft:'1px solid var(--border)',minWidth:100}}>
                <div style={{fontSize:9,color:'var(--text-secondary)',textTransform:'uppercase',letterSpacing:'.06em',fontWeight:700}}>
                  {tr('stmt_business_state')}
                </div>
                <div style={{fontSize:12,fontWeight:700,color:bizStateColor,marginTop:4}}>
                  {tr(`status_${bizStatus}_simple`)}
                </div>
              </div>
            </div>
          </div>
        </Card>
      )}

      {data&&<DataQualityBanner validation={validation} lang={l} tr={tr}/>}

      {data&&stmts.available&&(<>

        {/* ── Tabs ─────────────────────────────────────────────────── */}
        <div style={{display:'flex',gap:4,background:'var(--bg-elevated)',
          borderRadius:10,padding:3,width:'fit-content'}}>
          {TABS.map(t=>(
            <button key={t.k} onClick={()=>setTab(t.k)}
              style={{padding:'6px 16px',borderRadius:8,border:'none',fontSize:11,fontWeight:700,
                cursor:'pointer',transition:'all .15s',position:'relative',
                background:tab===t.k?'var(--bg-panel)':'transparent',
                color:tab===t.k?'#fff':'var(--text-secondary)'}}>
              {t.label}
              {t.badge>0&&<span style={{position:'absolute',top:2,right:2,
                width:6,height:6,borderRadius:'50%',background:'var(--red)'}}/>}
            </button>
          ))}
        </div>

        {/* ════════════════════════════════════════════════════════════
            INCOME STATEMENT TAB — with comparison + linked analysis
        ════════════════════════════════════════════════════════════ */}
        {tab==='income'&&(
          <div style={{display:'flex',flexDirection:'column',gap:14}}>
            {hasStructuredVariance ? (
              <StructuredFinancialLayers data={d} tr={tr} lang={lang} variant="statements_formal_variance" />
            ) : (
              <Card>
                <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:12}}>
                  <SectionHead label={tr('stmt_section_is')} color='var(--accent)' sub={period}/>
                  <Spark data={series.revenue?.slice(-8)} color='var(--accent)'/>
                </div>
                <CmpHeader lang={l} priorLabel={priorLabel} tr={tr}/>
                <CmpRow lang={lang} label={tr('fc_revenue')}
                  cur={is_.revenue} prior={prior.revenue}
                  bold color='var(--accent)'
                  onClick={()=>setPanel(insights.find(x=>x.domain==='growth')||null)}/>
                <CmpRow lang={lang} label={tr('cogs')}
                  cur={is_.cogs} prior={null} invertColor/>
                <CmpRow lang={lang} label={tr('stmt_bridge_gross')}
                  cur={is_.gross_profit} prior={null}
                  bold color='var(--green)'/>
                <CmpRow lang={lang} label={tr('stmt_bridge_opex')}
                  cur={is_.operating_expenses} prior={null} invertColor/>
                <CmpRow lang={lang} label={tr('stmt_bridge_op')}
                  cur={is_.operating_profit} prior={null} bold/>
                {is_.tax!=null&&<CmpRow lang={lang} label={tr('stmt_bridge_tax')}
                  cur={is_.tax} prior={null} invertColor/>}
                <CmpRow lang={lang} label={tr('fc_net_profit')}
                  cur={is_.net_profit} prior={prior.net_profit}
                  bold color={is_.net_profit>=0?'var(--green)':'var(--red)'}
                  onClick={()=>setPanel(insights.find(x=>x.key==='low_net_margin')||null)}/>
              </Card>
            )}
            <StructuredFinancialLayers data={d} tr={tr} lang={lang} variant="statements_interpretation" />
            <StructuredFinancialLayers data={d} tr={tr} lang={lang} variant="statements_margin_section" />
            {stmtHier?.available && stmtHier.income_statement && (
              <Card>
                <StatementHierarchyTree root={stmtHier.income_statement} tr={tr} lang={lang} />
              </Card>
            )}
            <div style={{display:'flex',flexWrap:'wrap',alignItems:'center',gap:10}}>
              <span style={{fontSize:10,fontWeight:800,color:'var(--text-secondary)',textTransform:'uppercase',letterSpacing:'.06em'}}>
                {tr('stmt_related_views')}
              </span>
              <button type="button" onClick={()=>setTab('cashflow')}
                style={{padding:'6px 12px',borderRadius:8,border:'1px solid var(--border)',
                  background:'var(--bg-elevated)',color:'#aab4c3',fontSize:11,fontWeight:600,cursor:'pointer'}}>
                {tr('cashflow_operating')} →
              </button>
              <button type="button" onClick={()=>setTab('balance')}
                style={{padding:'6px 12px',borderRadius:8,border:'1px solid var(--border)',
                  background:'var(--bg-elevated)',color:'#aab4c3',fontSize:11,fontWeight:600,cursor:'pointer'}}>
                {tr('stmt_section_bs')} →
              </button>
              <button type="button" onClick={()=>navigate('/analysis',{state:{focus:'overview'}})}
                style={{padding:'6px 12px',borderRadius:8,border:'1px solid var(--border)',
                  background:'var(--bg-elevated)',color:'#aab4c3',fontSize:11,fontWeight:600,cursor:'pointer'}}>
                {tr('nav_drill_analysis')} →
              </button>
            </div>
            <details className="stmt-supporting-details" style={{
              borderRadius:12,border:'1px solid var(--border)',padding:'10px 14px',background:'rgba(255,255,255,0.02)',
            }}>
              <summary style={{fontSize:12,fontWeight:800,color:'var(--text-secondary)',cursor:'pointer',listStyle:'none'}}>
                {tr('stmt_supporting_detail')}
              </summary>
              <div style={{marginTop:12,display:'grid',gridTemplateColumns:'1fr 300px',gap:14}}>
                <Card>
                  <SectionHead label={tr('margins')} color='var(--green)'/>
                  {[
                    {l:tr('gross_margin'),v:is_.gross_margin_pct,
                     c:is_.gross_margin_pct>=30?'var(--green)':is_.gross_margin_pct>=15?'var(--amber)':'var(--red)'},
                    {l:tr('net_margin'),v:is_.net_margin_pct,
                     c:is_.net_margin_pct>=10?'var(--green)':is_.net_margin_pct>=5?'var(--amber)':'var(--red)'},
                    {l:tr('operating_margin'),
                     v:is_.operating_profit&&is_.revenue?(is_.operating_profit/is_.revenue*100):null,
                     c:'var(--accent)'},
                  ].map(({l:lbl,v,c})=>(
                    <div key={lbl} style={{display:'flex',justifyContent:'space-between',
                      padding:'7px 0',borderBottom:'1px solid var(--border)'}}>
                      <span style={{fontSize:11,color:'var(--text-secondary)'}}>{lbl}</span>
                      <span style={{fontFamily:'var(--font-mono)',fontSize:13,fontWeight:700,color:c}}>
                        {formatPctForLang(v, 1, lang)}
                      </span>
                    </div>
                  ))}
                </Card>
                <div style={{display:'flex',flexDirection:'column',gap:10}}>
                  {ratios.profitability&&<Card>
                    <SectionHead label={tr('profitability')} color='var(--violet)'/>
                    {[
                      [tr('net_margin'), ratios.profitability?.net_margin_pct?.value, ratios.profitability?.net_margin_pct?.status, '%'],
                      [tr('gross_margin'), ratios.profitability?.gross_margin_pct?.value, ratios.profitability?.gross_margin_pct?.status, '%'],
                    ].map(([label,v,st,unit])=>(
                      <RatioRow key={label} label={label} value={v} status={st} unit={unit} lang={lang}/>
                    ))}
                  </Card>}
                  {insights.filter(x=>x.domain==='profitability'||x.domain==='growth').slice(0,2).map((ins,i)=>(
                    <InsightCard key={i} ins={ins} onClick={()=>setPanel(ins)} lang={l} tr={tr}/>
                  ))}
                </div>
              </div>
            </details>
          </div>
        )}

        {/* ════════════════════════════════════════════════════════════
            BALANCE SHEET TAB — with ratios + linked analysis
        ════════════════════════════════════════════════════════════ */}
        {tab==='balance'&&(
          <div style={{display:'grid',gridTemplateColumns:'1fr 300px',gap:14}}>
            <Card>
              <SectionHead label={tr('stmt_section_bs')} color='var(--blue)' sub={period}/>
              <CmpHeader lang={l} priorLabel={tr('na_label')} tr={tr}/>

              {/* Assets section */}
              <div style={{fontSize:10,fontWeight:700,color:'var(--blue)',
                textTransform:'uppercase',letterSpacing:'.06em',margin:'8px 0 4px'}}>
                {tr('assets')}
              </div>
              <CmpRow lang={lang} label={tr('current_assets')}
                cur={bs_.current_assets} prior={null} color='var(--blue)'/>
              <CmpRow lang={lang} label={tr('noncurrent_assets')}
                cur={bs_.noncurrent_assets} prior={null} indent/>
              <CmpRow lang={lang} label={tr('total_assets')}
                cur={bs_.total_assets} prior={null} bold color='var(--blue)'/>

              {/* Liabilities section */}
              <div style={{fontSize:10,fontWeight:700,color:'var(--red)',
                textTransform:'uppercase',letterSpacing:'.06em',margin:'12px 0 4px'}}>
                {tr('liabilities')}
              </div>
              <CmpRow lang={lang} label={tr('current_liabilities')}
                cur={bs_.current_liabilities} prior={null} invertColor/>
              <CmpRow lang={lang} label={tr('noncurrent_liabilities')}
                cur={bs_.noncurrent_liabilities} prior={null} invertColor indent/>
              <CmpRow lang={lang} label={tr('total_liabilities')}
                cur={bs_.total_liabilities} prior={null} bold color='var(--red)' invertColor/>

              {/* Equity */}
              <CmpRow lang={lang} label={tr('equity')}
                cur={bs_.total_equity} prior={null} bold color='var(--green)'/>

              {/* Working Capital — highlighted */}
              <div style={{marginTop:10,paddingTop:10,borderTop:'2px solid var(--border)'}}>
                <CmpRow lang={lang} label={tr('working_capital')}
                  cur={bs_.working_capital} prior={null} bold
                  color={bs_.working_capital>=0?'var(--green)':'var(--red)'}
                  onClick={bs_.working_capital<0?()=>setPanel(insights.find(x=>x.key==='negative_working_capital')||null):null}/>
              </div>

              {/* Balance check — BS only (assets == liabilities + equity) */}
              <div style={{marginTop:10,padding:'10px 12px',borderRadius:8,
                background:bs_.is_balanced?'rgba(34,197,94,.05)':'rgba(251,191,36,.05)',
                border:`1px solid ${bs_.is_balanced?'rgba(34,197,94,.25)':'rgba(251,191,36,.25)'}`}}>

                <div style={{display:'flex',alignItems:'center',gap:8}}>
                  <span style={{fontSize:15}}>{bs_.is_balanced?'✅':'⚠️'}</span>
                  <span style={{fontSize:11,fontWeight:700,
                    color:bs_.is_balanced?'var(--green)':'var(--amber)'}}>
                    {bs_.is_balanced ? tr('bs_balanced_msg') : tr('bs_not_balanced_msg')}
                  </span>
                  {bs_.balance_diff!=null&&!bs_.is_balanced&&(
                    <span style={{fontFamily:'var(--font-mono)',fontSize:10,
                      color:'var(--amber)',marginLeft:'auto'}}>
                      Δ {formatCompactForLang(bs_.balance_diff, lang)}
                    </span>
                  )}
                </div>

                {/* Explain WHY unbalanced */}
                {!bs_.is_balanced&&(
                  <div style={{marginTop:8,fontSize:10,color:'var(--text-secondary)',
                    lineHeight:1.6,paddingLeft:24}}>
                    {safeIncludes(bs_.balance_warning,'tb_type_unknown')
                      ? tr('bs_unbalanced_cause_tb_type')
                      : tr('bs_unbalanced_cause_other')}
                  </div>
                )}

                {/* TB check is separate */}
                <div style={{marginTop:6,fontSize:9,color:'var(--text-secondary)',
                  paddingLeft:24,opacity:.8}}>
                  {tr('bs_check_note')}
                </div>
              </div>
              {stmtHier?.available && stmtHier.balance_sheet && (
                <StatementHierarchyTree root={stmtHier.balance_sheet} tr={tr} lang={lang} />
              )}
            </Card>

            {/* Right panel: liquidity + leverage ratios + insights */}
            <div style={{display:'flex',flexDirection:'column',gap:10}}>
              <Card>
                <SectionHead label={tr('liquidity')} color='var(--blue)'/>
                {[
                  [tr('current_ratio'),  ratios.liquidity?.current_ratio?.value, ratios.liquidity?.current_ratio?.status, 'x'],
                  [tr('quick_ratio'),    ratios.liquidity?.quick_ratio?.value,   ratios.liquidity?.quick_ratio?.status,   'x'],
                  [tr('working_capital'), bs_.working_capital, bs_.working_capital>=0?'good':'risk',''],
                ].map(([label,v,st,unit])=>(
                  <RatioRow key={label} label={label} value={v} status={st} unit={unit} lang={lang}/>
                ))}
              </Card>

              <Card>
                <SectionHead label={tr('leverage')} color='var(--amber)'/>
                {[
                  [tr('debt_ratio_pct'), bs_.ratios?.debt_ratio_pct, bs_.ratios?.debt_ratio_pct<60?'good':bs_.ratios?.debt_ratio_pct<80?'warning':'risk','%'],
                  [tr('total_assets'),   bs_.total_assets, 'good', ''],
                  [tr('total_equity'),   bs_.total_equity,  bs_.total_equity>=0?'good':'risk',''],
                ].map(([label,v,st,unit])=>(
                  <RatioRow key={label} label={label} value={v} status={st} unit={unit} lang={lang}/>
                ))}
              </Card>

              {insights.filter(x=>x.domain==='liquidity'||x.domain==='leverage').slice(0,2).map((ins,i)=>(
                <InsightCard key={i} ins={ins} onClick={()=>setPanel(ins)} lang={l} tr={tr}/>
              ))}
            </div>
          </div>
        )}

        {/* ════════════════════════════════════════════════════════════
            CASH FLOW TAB — with OCF quality + reliability + comparison
        ════════════════════════════════════════════════════════════ */}
        {tab==='cashflow'&&(
          <div style={{display:'grid',gridTemplateColumns:'1fr 300px',gap:14}}>
            <Card>
              <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:12}}>
                <SectionHead label={tr('cashflow_operating_indirect')} color={cfFlagClr} sub={period}/>
                {cfEstimated&&(
                  <Badge label={tr('label_estimated')} color='var(--amber)'/>
                )}
              </div>

              <CmpHeader lang={l} priorLabel={priorLabel} tr={tr}/>
              <CmpRow lang={lang} label={tr('fc_net_profit')}
                cur={is_.net_profit} prior={prior.net_profit}/>
              {cf_.da_estimate!=null&&cf_.da_estimate!==0&&(
                <CmpRow lang={lang} label={tr('cf_da_estimate')}
                  cur={cf_.da_estimate} prior={null} color='var(--accent)'/>
              )}
              {cf_.wc_change?.net!=null&&(
                <CmpRow lang={lang} label={tr('cf_wc_change')}
                  cur={cf_.wc_change.net} prior={null}
                  color={cf_.wc_change.net>=0?'var(--green)':'var(--red)'}/>
              )}
              <CmpRow lang={lang} label={tr('cashflow_operating')}
                cur={cf_.operating_cashflow} prior={prior.cashflow}
                bold color={cf_.operating_cashflow>=0?'var(--green)':'var(--red)'}/>

              {/* Reliability badge */}
              {cfEstimated&&(
                <div style={{marginTop:10,display:'flex',alignItems:'center',gap:8,
                  padding:'8px 12px',borderRadius:8,
                  background:'rgba(251,191,36,.07)',border:'1px solid rgba(251,191,36,.22)'}}>
                  <span style={{fontSize:13}}>⚠</span>
                  <span style={{fontSize:10,color:'var(--amber)',lineHeight:1.4}}>
                    {tr('cf_estimated_hint')}
                  </span>
                </div>
              )}

              {/* WC movement breakdown */}
              {(cf_.wc_change?.receivables!=null||cf_.wc_change?.payables!=null)&&(
                <div style={{marginTop:12}}>
                  <div style={{fontSize:10,fontWeight:700,color:'var(--text-secondary)',
                    textTransform:'uppercase',letterSpacing:'.06em',marginBottom:6}}>
                    {tr('wc_movement_detail')}
                  </div>
                  {[
                    [tr('receivables_delta'),  cf_.wc_change?.receivables],
                    [tr('inventory_delta'),    cf_.wc_change?.inventory],
                    [tr('payables_delta'),     cf_.wc_change?.payables],
                  ].filter(([,v])=>v!=null).map(([lbl,v])=>(
                    <div key={lbl} style={{display:'flex',justifyContent:'space-between',
                      padding:'5px 0',borderBottom:'1px solid var(--border)'}}>
                      <span style={{fontSize:11,color:'var(--text-secondary)'}}>{lbl}</span>
                      <span style={{fontFamily:'var(--font-mono)',fontSize:11,
                        color:clrV(v),direction:'ltr'}}>
                        {v > 0 ? '+' : ''}
                        {formatCompactForLang(v, lang)}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Trend */}
              {ser.periods?.length>1&&(
                <div style={{marginTop:14}}>
                  <div style={{fontSize:9,color:'var(--text-secondary)',textTransform:'uppercase',
                    letterSpacing:'.06em',marginBottom:6}}>
                    {tr('trend')}
                  </div>
                  <Spark data={cf_.trend?.length?cf_.trend:series.net_profit}
                    color='var(--blue)' h={44}/>
                </div>
              )}
              {stmtHier?.available && stmtHier.cashflow && (
                <StatementHierarchyTree root={stmtHier.cashflow} tr={tr} lang={lang} />
              )}
            </Card>

            <div style={{display:'flex',flexDirection:'column',gap:10}}>
              {/* OCF quality card */}
              <Card style={{borderTop:`2px solid ${cfFlagClr}`}}>
                <SectionHead label={tr('ocf_quality')} color={cfFlagClr}/>
                <div style={{fontFamily:'var(--font-mono)',fontSize:24,fontWeight:800,
                  color:cfFlagClr,direction:'ltr',marginBottom:6}}>
                  {formatCompactForLang(cf_.operating_cashflow, lang)}
                </div>
                {cf_.quality&&<>
                  {[
                    [
                      tr('conversion_ratio'),
                      cf_.quality.cash_conversion_ratio != null
                        ? formatMultipleForLang(cf_.quality.cash_conversion_ratio, 2, lang)
                        : null,
                    ],
                    [tr('quality'),
                     cf_.quality.cash_conversion_quality||null],
                    [tr('profit_cash_gap'),
                     cf_.quality.profit_vs_cash_gap != null
                       ? formatCompactForLang(cf_.quality.profit_vs_cash_gap, lang)
                       : null],
                  ].filter(([,v])=>v!=null).map(([lbl,v])=>(
                    <div key={lbl} style={{display:'flex',justifyContent:'space-between',
                      padding:'6px 0',borderBottom:'1px solid var(--border)'}}>
                      <span style={{fontSize:10,color:'var(--text-secondary)'}}>{lbl}</span>
                      <span style={{fontFamily:'var(--font-mono)',fontSize:11,color:'var(--text-primary)'}}>{v}</span>
                    </div>
                  ))}
                </>}
                <p style={{fontSize:11,color:'var(--text-secondary)',lineHeight:1.5,margin:'8px 0 0'}}>
                  {cf_.operating_cashflow>=0 ? tr('cf_positive_note') : tr('cf_negative_note')}
                </p>
              </Card>

              {/* Cashflow reliability note */}
              <Card>
                <SectionHead label={tr('reliability')} color={cfEstimated?'var(--amber)':'var(--green)'}/>
                <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:6}}>
                  <span style={{fontSize:16}}>{cfEstimated?'⚠️':'✅'}</span>
                  <span style={{fontSize:12,fontWeight:600,
                    color:cfEstimated?'var(--amber)':'var(--green)'}}>
                    {cfEstimated ? tr('estimated') : tr('real')}
                  </span>
                </div>
                <p style={{fontSize:10,color:'var(--text-secondary)',lineHeight:1.5,margin:0}}>
                  {cfEstimated ? tr('cf_reliability_estimated_note') : tr('cf_reliability_real_note')}
                </p>
              </Card>

              {insights.filter(x=>x.domain==='cashflow'||x.key==='cashflow_below_profit').slice(0,2).map((ins,i)=>(
                <InsightCard key={i} ins={ins} onClick={()=>setPanel(ins)} lang={l} tr={tr}/>
              ))}
            </div>
          </div>
        )}

        {/* ════════════════════════════════════════════════════════════
            INSIGHTS TAB — all linked insights
        ════════════════════════════════════════════════════════════ */}
        {tab==='insights'&&(
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10,maxWidth:900}}>
            {insights.length===0&&(
              <div style={{gridColumn:'1/-1',textAlign:'center',padding:'40px',
                color:'var(--text-secondary)',fontSize:13,fontStyle:'italic'}}>
                {tr('no_insights_available')}
              </div>
            )}
            {insights.map((ins,i)=>(
              <InsightCard key={i} ins={ins} onClick={()=>setPanel(ins)} lang={l} tr={tr}/>
            ))}
          </div>
        )}

        {insights.filter(x=>x.severity==='high').length>0&&(
          <details className="stmt-priority-details" style={{
            borderRadius:12,border:'1px solid rgba(248,113,113,.28)',padding:'10px 14px',
            background:'rgba(248,113,113,.05)',marginTop:2,
          }}>
            <summary style={{fontSize:12,fontWeight:800,color:'var(--red)',cursor:'pointer',listStyle:'none'}}>
              {tr('stmt_priority_signals')}
            </summary>
            <div style={{display:'flex',flexWrap:'wrap',gap:8,marginTop:10}}>
              {insights.filter(x=>x.severity==='high').slice(0,5).map((ins,i)=>(
                <button key={i} type="button" onClick={()=>setPanel(ins)}
                  style={{fontSize:10,color:'var(--red)',background:'rgba(248,113,113,.1)',
                    padding:'4px 10px',borderRadius:20,border:'1px solid rgba(248,113,113,.22)',
                    cursor:'pointer',maxWidth:260,overflow:'hidden',textAlign:'start'}}>
                  <CmdServerText lang={lang} tr={tr} title={ins.message}
                    style={{display:'inline-block',maxWidth:'100%',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap',verticalAlign:'bottom'}}>
                    {ins.message}
                  </CmdServerText>
                  {' →'}
                </button>
              ))}
            </div>
          </details>
        )}

      </>)}

      {/* No statements */}
      {data&&!stmts.available&&(
        <div style={{textAlign:'center',padding:'60px 0',color:'var(--text-secondary)'}}>
          <div style={{fontSize:36,marginBottom:12,opacity:.3}}>📊</div>
          <p style={{fontSize:14}}>
            {tr('stmt_no_data')}
          </p>
        </div>
      )}

      {/* Context panel */}
      {panel&&<ContextPanel item={panel} decs={decs} tr={tr} lang={l} onClose={()=>setPanel(null)}/>}
    </div>
  )
}
