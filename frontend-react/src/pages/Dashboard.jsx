/**
 * Dashboard.jsx — CFO Product · Final Polish
 *
 * Changes in this version:
 *  1. ALL numbers forced to en-US (no Arabic/Eastern digits)
 *  2. Zero hardcoded text — every string via tr()
 *  3. KPI hover intelligence — contextual CEO-friendly explanation
 *  4. Expense intelligence — spike detection, top rising cost
 *  5. Executive language — DOL, working capital, all business-friendly
 *  6. KPI drill-down modal — click any KPI for full history
 *  7. RTL-safe layout preserved
 */
import { useEffect, useState, useRef, useCallback } from 'react'
import { useLang } from '../context/LangContext.jsx'
import { strictT, strictTParams } from '../utils/strictI18n.js'
import CmdServerText from '../components/CmdServerText.jsx'
import { kpiContextLabel, kpiLabel } from '../utils/kpiContext.js'
import { useCompany } from '../context/CompanyContext.jsx'
import PeriodSelector from '../components/PeriodSelector.jsx'
import UniversalScopeSelector from '../components/UniversalScopeSelector.jsx'
import { usePeriodScope } from '../context/PeriodScopeContext.jsx'
import { buildAnalysisQuery } from '../utils/buildAnalysisQuery.js'

import { hasFlag, safeIncludes } from '../utils/dataGuards.js'
import {
  formatCompactForLang,
  formatFullForLang,
  formatPctForLang,
  formatPpForLang,
  formatMultipleForLang,
  formatSignedPctForLang,
  formatDays,
} from '../utils/numberFormat.js'

const API = '/api/v1'

function getAuthHeaders() {
  try {
    const raw = localStorage.getItem('vcfo_auth')
    const token = raw ? JSON.parse(raw)?.token : null
    return token ? { Authorization: `Bearer ${token}` } : {}
  } catch { return {} }
}

// ══════════════════════════════════════════════════════════════════════════════
//  Translation hooks — ALL hoisted (Rules of Hooks)
// ══════════════════════════════════════════════════════════════════════════════
function useTSignal() {
  const { translations, lang } = useLang()
  return useCallback((sig) => {
    if (!sig) return ''
    if (sig.key && translations[sig.key]) {
      const tpl = translations[sig.key], data = sig.data || {}
      return tpl.replace(/\{([^}]+)\}/g, (_, raw) => {
        const k = raw.split(':')[0].trim(), v = data[k]
        if (v == null) return k
        if (typeof v === 'number') {
          const fmt = raw.includes(':') ? raw.split(':')[1] : ''
          if (fmt.includes('f')) return v.toFixed(parseInt((fmt.match(/\.(\d+)/) || [0,'1'])[1]))
          return formatCompactForLang(v, lang)
        }
        return String(v)
      })
    }
    return sig.what || sig.message || ''
  }, [translations, lang])
}

function useTSignalSub() {
  const { translations, lang } = useLang()
  return useCallback((sig) => {
    if (!sig) return ''
    const key = sig.why_key
    if (key && translations[key]) {
      const tpl = translations[key], data = sig.data || {}
      return tpl.replace(/\{([^}]+)\}/g, (_, raw) => {
        const k = raw.split(':')[0].trim(), v = data[k]
        if (v == null) return k
        if (typeof v === 'number') {
          const fmt = raw.includes(':') ? raw.split(':')[1] : ''
          if (fmt.includes('f')) return v.toFixed(parseInt((fmt.match(/\.(\d+)/) || [0,'1'])[1]))
          return formatCompactForLang(v, lang)
        }
        return String(v)
      })
    }
    return sig.why || ''
  }, [translations, lang])
}

function useTForecast() {
  const { translations } = useLang()
  return useCallback((nar) => {
    if (!nar) return ''
    if (typeof nar === 'string') return nar
    const parts = nar.parts || []
    if (!parts.length) return nar.fallback || ''
    return parts.map(p => {
      const tpl = translations[p.key] || ''
      if (!tpl) return ''
      const resolved = Object.fromEntries(
        Object.entries(p.data || {}).map(([k,v]) =>
          k === 'level_key' && translations[v] ? ['level', translations[v]] : [k,v])
      )
      return tpl.replace(/\{([^}]+)\}/g, (_,k) => resolved[k] ?? k)
    }).filter(Boolean).join(' ')
  }, [translations])
}

// ══════════════════════════════════════════════════════════════════════════════
//  Formatters — ALL en-US (mandatory: no Arabic/Eastern digits ever)

// ══════════════════════════════════════════════════════════════════════════════
//  Dynamic text normalization — maps backend phrases to translation keys
// ══════════════════════════════════════════════════════════════════════════════
const BACKEND_PHRASE_MAP = {
  'strengthen receivables management': 'action_strengthen_receivables',
  'debt reduction strategy': 'action_debt_reduction',
  'revenue growth acceleration': 'action_revenue_growth',
  'excellent — stay on current path': 'msg_excellent_status',
  'excellent - stay on current path': 'msg_excellent_status',
  'immediate attention required': 'msg_warning_status',
  'critical financial risk': 'msg_risk_status',
}

function normalizeDecisionKey(text) {
  if (!text) return null
  const n = text.toLowerCase().trim()
  if (BACKEND_PHRASE_MAP[n]) return BACKEND_PHRASE_MAP[n]

  for (const [phrase, key] of Object.entries(BACKEND_PHRASE_MAP)) {
    if (n.includes(phrase)) return key
  }
  return null
}

function normalizeMessageKey(text) {
  return normalizeDecisionKey(text)
}

function trDynamic(tr, text, maxLen) {
  if (!text) return ''
  const key = normalizeDecisionKey(text)
  const resolved = key ? tr(key) : null
  const result = (resolved && resolved !== key) ? resolved : text
  return maxLen && result.length > maxLen ? result.slice(0, maxLen) : result
}
// ══════════════════════════════════════════════════════════════════════════════
const clr   = v => v==null?'#6b80a8':v>0?'#10d98a':v<0?'#ff4d6d':'#6b80a8'
const arr   = v => v==null?'':v>0.3?'↑':v<-0.3?'↓':'→'
const pSign = v => v==null?'':v>=0?'+':''

// ══════════════════════════════════════════════════════════════════════════════
//  Design tokens
// ══════════════════════════════════════════════════════════════════════════════
const BG = {
  page:'#0B0F14',     surface:'#111827',  panel:'#111827',  card:'#111827',
  border:'#1F2937',   border2:'rgba(255,255,255,0.07)',
  elevated:'#111827',
}
const C = {
  accent:'#00d4aa', green:'#34d399', red:'#f87171', amber:'#fbbf24',
  violet:'#a78bfa', blue:'#60a5fa',
  /* Phase 32 readability fix — 4 clear tiers */
  text1:'#ffffff',   /* titles, KPI numbers — pure white          */
  text2:'#aab4c3',   /* labels, descriptions — clearly readable   */
  text3:'#6b7280',   /* supporting only — never for key content   */
  text4:'#4b5563',   /* truly secondary — use very sparingly      */
}

// ── Phase 6.1: KPI insight derivation ───────────────────────────────────────
// Reads ONLY from already-fetched data. Zero calculations.
function kpiInsight(type, data, lang, tr) {
  const d = data?.data || {}
  const l = lang || 'en'
  const kpis    = d.kpi_block?.kpis    || {}
  const trends  = d.intelligence?.trends || {}
  const ratios  = d.intelligence?.ratios || {}
  const cashflow= d.cashflow || {}
  const stmtIns = d.statements?.insights || []
  const decs    = d.decisions || []
  const findIns = key => stmtIns.find(i => i.key === key)

  const dirLabel = (dir) => {
    if (dir === 'up')     return tr('trend_up')
    if (dir === 'down')   return tr('trend_down')
    if (dir === 'stable') return tr('trend_stable')
    return null
  }
  const statusLabel = (st) => {
    if (!st) return null
    return tr(`kpi_margin_badge_${st}`)
  }

  switch (type) {
    case 'revenue': {
      const dir = trends?.revenue?.direction
      return dirLabel(dir)
    }
    case 'expenses': {
      const mom = kpis?.expenses?.mom_pct
      if (mom == null) return null
      const arrow = mom > 0 ? '↑' : '↓'
      return `${arrow} ${formatPctForLang(Math.abs(mom), 1, l)} ${tr('vs_prior_month')}`
    }
    case 'net_profit': {
      const st = ratios?.profitability?.net_margin_pct?.status
      return statusLabel(st)
    }
    case 'cashflow': {
      const ins = findIns('cashflow_positive')
      if (ins) return ins.message.split('. ')[0]
      const rel = cashflow?.reliability
      if (rel === 'estimated') return `⚠ ${tr('data_estimated_limited')}`
      if (rel === 'real')      return `✓ ${tr('data_real_based')}`
      return null
    }
    case 'net_margin': {
      const ins = findIns('strong_gross_margin')
      if (ins) return ins.message.split('. ')[0]
      const st = ratios?.profitability?.gross_margin_pct?.status
      return statusLabel(st)
    }
    default: return null
  }
}
// ── Shared dark-theme input styles ──────────────────────────────────────────
const INPUT_DARK = {
  background:    '#111827',
  color:         '#ffffff',
  border:        '1px solid #1F2937',
  borderRadius:  8,
  padding:       '7px 10px',
  fontSize:      12,
  outline:       'none',
  fontFamily:    'var(--font-mono)',
  direction:     'ltr',
  width:         '100%',
  WebkitAppearance: 'none',
  MozAppearance: 'none',
  appearance:    'none',
}
const SELECT_DARK = {
  ...INPUT_DARK,
  cursor:        'pointer',
  fontFamily:    'var(--font-display)',
  width:         undefined,
  paddingRight:  28,
  backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%23374560'/%3E%3C/svg%3E")`,
  backgroundRepeat:   'no-repeat',
  backgroundPosition: 'right 10px center',
}

// ══════════════════════════════════════════════════════════════════════════════
//  Tooltip (chart hover — always LTR)
// ══════════════════════════════════════════════════════════════════════════════
function Tip({ tip }) {
  if (!tip) return null
  const TW=160, TH=14+tip.items.length*20+(tip.period?20:0)
  const tx=tip.x+12+TW>tip.cw?tip.x-TW-12:tip.x+12
  const ty=Math.max(4,Math.min(tip.y-TH/2,tip.ch-TH-4))
  return (
    <div style={{position:'absolute',left:tx,top:ty,pointerEvents:'none',zIndex:200,
      background:'rgba(6,11,22,0.97)',border:`1px solid rgba(255,255,255,0.12)`,borderRadius:10,
      padding:'9px 13px',minWidth:TW,
      boxShadow:'0 12px 40px rgba(0,0,0,0.9), 0 0 0 1px rgba(255,255,255,0.04)',
      direction:'ltr'}}>
      {tip.items.map((it,i)=>(
        <div key={i} style={{display:'flex',justifyContent:'space-between',gap:12,marginBottom:i<tip.items.length-1?4:0}}>
          <div style={{display:'flex',alignItems:'center',gap:5}}>
            <div style={{width:6,height:6,borderRadius:'50%',background:it.color,flexShrink:0}}/>
            <span style={{fontSize:10,color:C.text2}}>{it.label}</span>
          </div>
          <span style={{fontSize:11,fontWeight:700,color:it.color,fontFamily:'monospace'}}>{it.value}</span>
        </div>
      ))}
      {tip.period&&<div style={{fontSize:10,color:C.text2,marginTop:6,paddingTop:5,borderTop:`1px solid ${BG.border2}`,fontFamily:'monospace'}}>{tip.period}</div>}
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  KPI Hover Tooltip — intelligent explanation
// ══════════════════════════════════════════════════════════════════════════════
function KpiHoverTip({ visible, mom, type, tr }) {
  if (!visible) return null
  const getKey = () => {
    if (mom == null) return null
    const dir = mom > 0.5 ? 'up' : mom < -0.5 ? 'down' : 'flat'
    return `kpi_hover_${type}_${dir}`
  }
  const key = getKey()
  if (!key) return null
  return (
    <div style={{
      position:'absolute', bottom:'calc(100% + 8px)', left:'50%',
      transform:'translateX(-50%)', zIndex:300, pointerEvents:'none',
      background:'rgba(4,10,24,0.97)', border:`1px solid ${C.accent}40`,
      borderRadius:10, padding:'10px 14px', width:210, direction:'ltr',
      boxShadow:`0 8px 32px rgba(0,0,0,.8), 0 0 0 1px ${C.accent}20`
    }}>
      <div style={{fontSize:12,color:C.text1,lineHeight:1.6,marginBottom:6}}>{tr(key)}</div>
      <div style={{fontSize:9,color:C.accent,opacity:.7}}>{tr('kpi_hover_click')}</div>
      <div style={{position:'absolute',bottom:-5,left:'50%',
        width:8,height:8,background:'rgba(4,10,24,0.97)',border:`1px solid ${C.accent}40`,
        borderTop:'none',borderLeft:'none',transform:'translateX(-50%) rotate(45deg)'}}/>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  Drill-Down Modal
// ══════════════════════════════════════════════════════════════════════════════
function DrillModal({ kpiType, data, tr, onClose, ctxLabel, lang }) {
  if (!kpiType) return null
  const d = data?.data || {}
  const series = d.kpi_block?.series || {}
  const periods = d.kpi_block?.periods || []
  const kpis = d.kpi_block?.kpis || {}
  const fc = (v) =>
    v == null || v === '' || !Number.isFinite(Number(v)) ? '—' : formatCompactForLang(Number(v), lang)
  const fp = (v) => (v == null || !Number.isFinite(Number(v)) ? '—' : formatPctForLang(Number(v), 1, lang))

  const configs = {
    revenue:   { key:kpiLabel(tr('kpi_total_revenue'),ctxLabel(), tr),  series:series.revenue,   color:C.accent,  fmt:fc },
    expenses:  { key:kpiLabel(tr('kpi_total_expenses'),ctxLabel(), tr), series:series.expenses,  color:C.red,     fmt:fc },
    net_profit:{ key:kpiLabel(tr('kpi_net_profit'),ctxLabel(), tr),     series:series.net_profit,color:C.green,   fmt:fc },
    net_margin:{ key:'kpi_net_margin',     series:series.net_margin, color:C.violet, fmt:fp },  // FIX-3.4: read from kpi_block, no frontend recalculation
    cashflow:  { key:'cashflow_operating', series:d.cashflow?.series?.operating_cashflow, color:C.amber, fmt:fc },
  }
  const cfg = configs[kpiType]
  if (!cfg) return null
  const ser = cfg.series || []

  return (
    <div onClick={onClose} style={{position:'fixed',inset:0,zIndex:500,
      background:'rgba(0,0,0,0.65)',
      display:'flex',alignItems:'center',justifyContent:'center',padding:20}}>
      <div onClick={e=>e.stopPropagation()} style={{
        background:BG.surface, border:`1px solid ${BG.border}`, borderRadius:16,
        width:'100%', maxWidth:640, maxHeight:'80vh', display:'flex', flexDirection:'column',
        boxShadow:'0 24px 64px rgba(0,0,0,.8)', borderTop:`2px solid ${cfg.color}`
      }}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',
          padding:'16px 20px', borderBottom:`1px solid ${BG.border2}`}}>
          <div style={{fontSize:14,fontWeight:700,color:C.text1}}>{tr(cfg.key)}</div>
          <button onClick={onClose} style={{background:BG.card,border:`1px solid ${BG.border}`,
            borderRadius:7,color:C.text2,fontSize:12,padding:'5px 12px',cursor:'pointer'}}>
            {tr('modal_close')}
          </button>
        </div>
        <div style={{padding:'16px 20px',overflowY:'auto',flex:1,minHeight:0}}>
          {/* Summary stat */}
          <div style={{display:'flex',gap:16,marginBottom:16}}>
            <div style={{background:BG.panel,borderRadius:10,padding:'12px 16px',flex:1,border:`1px solid ${BG.border}`}}>
              <div style={{fontSize:10,color:C.text2,marginBottom:4,textTransform:'uppercase',letterSpacing:'.07em',fontWeight:600}}>{tr('gen_current_period')}</div>
              <div style={{fontFamily:'var(--font-display)',fontSize:28,fontWeight:800,color:cfg.color,direction:'ltr'}}>{cfg.fmt(ser.at(-1))}</div>
            </div>
            <div style={{background:BG.panel,borderRadius:10,padding:'12px 16px',flex:1,border:`1px solid ${BG.border}`}}>
              <div style={{fontSize:10,color:C.text2,marginBottom:4,textTransform:'uppercase',letterSpacing:'.07em',fontWeight:600}}>{tr('gen_prior_period')}</div>
              <div style={{fontFamily:'var(--font-display)',fontSize:28,fontWeight:800,color:C.text1,direction:'ltr'}}>{cfg.fmt(ser.at(-2))}</div>
            </div>
          </div>
          {/* Period table */}
          <div style={{overflowX:'auto'}}>
            <table style={{width:'100%',borderCollapse:'collapse',fontSize:11,direction:'ltr'}}>
              <thead>
                <tr style={{background:BG.panel}}>
                  {[tr('modal_period_label'),tr('modal_value_label'),tr('modal_change_label')].map((h,i)=>(
                    <th key={i} style={{padding:'8px 10px',textAlign:i===0?'left':'right',
                      color:C.text2,fontSize:10,fontWeight:700,textTransform:'uppercase',
                      letterSpacing:'.06em',borderBottom:`1px solid ${BG.border}`}}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {periods.slice().reverse().map((p,i)=>{
                  const idx=periods.indexOf(p)
                  const v=ser[idx], prev=ser[idx-1]
                  const delta=v!=null&&prev!=null?v-prev:null
                  const pct=prev&&prev!==0?delta/Math.abs(prev)*100:null
                  const isLast=i===0
                  return (
                    <tr key={p} style={{borderBottom:`1px solid ${BG.border2}`,background:isLast?`${cfg.color}08`:'transparent'}}>
                      <td style={{padding:'7px 10px',color:isLast?cfg.color:C.text1,fontFamily:'monospace',fontWeight:isLast?700:400}}>{p}</td>
                      <td style={{padding:'7px 10px',textAlign:'right',color:C.text1,fontFamily:'monospace',fontWeight:600}}>{cfg.fmt(v)}</td>
                      <td style={{padding:'7px 10px',textAlign:'right',color:clr(pct)}}>
                        {pct != null
                          ? pct > 0
                            ? `+${formatPctForLang(pct, 1, lang)}`
                            : formatPctForLang(pct, 1, lang)
                          : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  Charts — always LTR, numbers always en-US
// ══════════════════════════════════════════════════════════════════════════════
function AreaChart({ d1, d2, labels, c1 = C.accent, c2 = C.red, h = 160, n1 = '', n2 = '', showBars = false, lang = 'en' }) {
  const [tip,setTip]=useState(null); const ref=useRef(null)
  if (!d1||d1.length<2) return <div style={{height:h,display:'flex',alignItems:'center',justifyContent:'center',color:C.text2,fontSize:11}}>—</div>
  const all=[...d1.filter(Boolean),...(d2||[]).filter(Boolean)]
  const mx=Math.max(...all)||1
  const W=600,H=h,PL=40,PR=12,PT=8,PB=22,wi=W-PL-PR,hi=H-PT-PB
  const toX=i=>PL+(i/(d1.length-1))*wi
  const toY=v=>PT+(1-Math.max(0,v)/mx)*hi
  // Smooth cubic bezier path generator
  function smoothPath(data) {
    const pts = data.map((v,i) => [toX(i), toY(v||0)])
    return pts.reduce((acc,[x,y],i) => {
      if(i===0) return `M${x.toFixed(1)},${y.toFixed(1)}`
      const [px,py] = pts[i-1]
      const cpx = (px + x) / 2
      return acc + ` C${cpx.toFixed(1)},${py.toFixed(1)} ${cpx.toFixed(1)},${y.toFixed(1)} ${x.toFixed(1)},${y.toFixed(1)}`
    }, '')
  }
  const p1 = smoothPath(d1)
  const a1 = `${p1} L${toX(d1.length-1).toFixed(1)},${(PT+hi).toFixed(1)} L${PL},${(PT+hi).toFixed(1)} Z`
  const p2 = d2 ? smoothPath(d2) : ''
  const a2 = d2 ? `${p2} L${toX(d2.length-1).toFixed(1)},${(PT+hi).toFixed(1)} L${PL},${(PT+hi).toFixed(1)} Z` : ''
  const ticks=[0,mx*.5,mx]
  const bw=(wi/d1.length)*.35
  function onMove(e){
    const r=ref.current?.getBoundingClientRect(); if(!r)return
    const sx=((e.clientX-r.left)/r.width)*W
    let bi=0,bd=1e9; d1.forEach((_,i)=>{const dd=Math.abs(toX(i)-sx);if(dd<bd){bd=dd;bi=i}})
    const items=[{label:n1,value:formatCompactForLang(d1[bi],lang),color:c1}]
    if(d2) items.push({label:n2,value:formatCompactForLang(d2[bi],lang),color:c2})
    setTip({x:toX(bi)/W*r.width,y:toY(d1[bi]||0)/H*r.height,cw:r.width,ch:r.height,period:labels?.[bi]||`#${bi+1}`,items,idx:bi})
  }
  return (
    <div ref={ref} style={{position:'relative',direction:'ltr'}} onMouseMove={onMove} onMouseLeave={()=>setTip(null)}>
      <svg viewBox={`0 0 ${W} ${H}`} style={{width:'100%',height:H,display:'block'}}>
        <defs>
          <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={c1} stopOpacity=".22"/><stop offset="100%" stopColor={c1} stopOpacity="0"/></linearGradient>
          <linearGradient id="g2" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={c2} stopOpacity=".14"/><stop offset="100%" stopColor={c2} stopOpacity="0"/></linearGradient>
        </defs>
        {ticks.map((t,i)=>(
          <g key={i}>
            <line x1={PL} y1={toY(t)} x2={W-PR} y2={toY(t)} stroke="rgba(255,255,255,0.04)" strokeWidth="1"/>
            <text x={PL-5} y={toY(t)+4} textAnchor="end" fontSize="10" fill={C.text2}>{formatCompactForLang(t, lang)}</text>
          </g>
        ))}
        {showBars&&d1.map((v,i)=>{
          const bh=(v||0)/mx*hi
          return <rect key={i} x={toX(i)-bw/2} y={PT+hi-bh} width={bw} height={bh} fill={c1} opacity=".18" rx="1"/>
        })}
        {a2&&<path d={a2} fill="url(#g2)"/>}
        <path d={a1} fill="url(#g1)"/>
        {p2&&<path d={p2} fill="none" stroke={c2} strokeWidth="1.5" strokeLinecap="round" strokeDasharray="4,3"/>}
        <path d={p1} fill="none" stroke={c1} strokeWidth="2" strokeLinecap="round"/>
        {tip?.idx!=null&&(()=>{
          const xi=toX(tip.idx),y1t=toY(d1[tip.idx]||0),y2t=d2?toY(d2[tip.idx]||0):null
          return <g>
            <line x1={xi} y1={PT} x2={xi} y2={PT+hi} stroke="rgba(255,255,255,0.07)" strokeWidth="1" strokeDasharray="3,3"/>
            <circle cx={xi} cy={y1t} r="4" fill={c1} stroke={BG.page} strokeWidth="2"/>
            {y2t!=null&&<circle cx={xi} cy={y2t} r="3.5" fill={c2} stroke={BG.page} strokeWidth="2"/>}
          </g>
        })()}
        {labels&&d1.map((_,i)=>{
          if(i%Math.ceil(d1.length/7)!==0&&i!==d1.length-1)return null
          return <text key={i} x={toX(i)} y={H-5} textAnchor="middle" fontSize="10" fill={C.text2}>{(labels[i]||'').replace(/^\d{4}-/,'')}</text>
        })}
      </svg>
      <Tip tip={tip}/>
    </div>
  )
}

function BarChart({ data, labels, color = C.accent, h = 110, name = '', lang = 'en' }) {
  const [tip,setTip]=useState(null); const [hov,setHov]=useState(null); const ref=useRef(null)
  if (!data||data.length<1) return null
  const W=600,H=h,PL=8,PR=8,PT=8,PB=22,wi=W-PL-PR,hi=H-PT-PB
  const mx=Math.max(...data.map(Math.abs),.1)
  const bw=(wi/data.length)*.55, bx=i=>PL+i*(wi/data.length)+(wi/data.length)*.225
  function onMove(e){
    const r=ref.current?.getBoundingClientRect(); if(!r)return
    const sx=((e.clientX-r.left)/r.width)*W
    const idx=Math.floor((sx-PL)/(wi/data.length))
    if(idx<0||idx>=data.length){setTip(null);setHov(null);return}
    const v=data[idx]; if(v==null){setTip(null);setHov(null);return}
    setHov(idx)
    setTip({x:(bx(idx)+bw/2)/W*r.width,y:(PT+hi-(Math.abs(v)/mx)*hi)/H*r.height,cw:r.width,ch:r.height,
      period:labels?.[idx]||`#${idx+1}`,items:[{label:name,value:formatSignedPctForLang(v, 1, lang),color:v>=0?C.green:C.red}]})
  }
  return (
    <div ref={ref} style={{position:'relative',direction:'ltr'}} onMouseMove={onMove} onMouseLeave={()=>{setTip(null);setHov(null)}}>
      <svg viewBox={`0 0 ${W} ${H}`} style={{width:'100%',height:H,display:'block'}}>
        <line x1={PL} y1={PT+hi} x2={W-PR} y2={PT+hi} stroke="rgba(255,255,255,0.06)" strokeWidth="1"/>
        {data.map((v,i)=>{
          const bh=(Math.abs(v||0)/mx)*hi,y=PT+hi-bh,isH=hov===i
          const bc=v>=0?C.green:C.red
          return <g key={i}>
            <rect x={bx(i)} y={y} width={bw} height={bh} fill={isH?bc:color} opacity={isH?1:.7} rx="2"/>
            {labels&&<text x={bx(i)+bw/2} y={H-6} textAnchor="middle" fontSize="9" fill={isH?C.text1:C.text2}>{(labels[i]||'').replace(/^\d{4}-/,'')}</text>}
          </g>
        })}
      </svg>
      <Tip tip={tip}/>
    </div>
  )
}

function SparkLine({data,color=C.accent,h=32,w=88}) {
  if (!data||data.filter(Boolean).length<2) return null
  const vals=data.filter(v=>v!=null)
  const mn=Math.min(...vals),mx=Math.max(...vals),rng=mx-mn||1
  const uid=`sg${Math.random().toString(36).slice(2,7)}`
  // Smooth cubic bezier path
  const pts=vals.map((v,i)=>[
    (i/(vals.length-1))*w,
    h-((v-mn)/rng)*(h*.78)-h*.09
  ])
  const path=pts.reduce((acc,[x,y],i)=>{
    if(i===0) return `M${x.toFixed(1)},${y.toFixed(1)}`
    const [px,py]=pts[i-1]
    const cpx1=(px+(x-px)*0.5).toFixed(1), cpy1=py.toFixed(1)
    const cpx2=(px+(x-px)*0.5).toFixed(1), cpy2=y.toFixed(1)
    return acc+` C${cpx1},${cpy1} ${cpx2},${cpy2} ${x.toFixed(1)},${y.toFixed(1)}`
  },'')
  const areaPath=`${path} L${w},${h} L0,${h} Z`
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{display:'block',direction:'ltr',overflow:'visible'}}>
      <defs>
        <linearGradient id={uid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25"/>
          <stop offset="100%" stopColor={color} stopOpacity="0.01"/>
        </linearGradient>
      </defs>
      <path d={areaPath} fill={`url(#${uid})`}/>
      <path d={path} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      {/* Last point dot */}
      <circle cx={pts[pts.length-1][0].toFixed(1)} cy={pts[pts.length-1][1].toFixed(1)}
        r="2.5" fill={color} style={{filter:`drop-shadow(0 0 4px ${color})`}}/>
    </svg>
  )
}

function DonutChart({segments,size=80}) {
  const total=segments.reduce((s,x)=>s+x.value,0)||1
  let cum=0; const R=32,cx=size/2,cy=size/2
  const slices=segments.map(seg=>{
    const pct=seg.value/total
    const s=-Math.PI/2+cum*2*Math.PI,e=s+pct*2*Math.PI
    const x1=cx+R*Math.cos(s),y1=cy+R*Math.sin(s),x2=cx+R*Math.cos(e),y2=cy+R*Math.sin(e)
    const lg=pct>0.5?1:0
    const d=pct<0.999?`M${x1.toFixed(2)},${y1.toFixed(2)} A${R},${R} 0 ${lg},1 ${x2.toFixed(2)},${y2.toFixed(2)}`:`M${cx-R},${cy} A${R},${R} 0 1,1 ${cx+R},${cy} A${R},${R} 0 1,1 ${cx-R},${cy}`
    cum+=pct; return {...seg,d}
  })
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{direction:'ltr'}}>
      <circle cx={cx} cy={cy} r={R} fill="none" stroke={BG.border} strokeWidth="10"/>
      {slices.map((sl,i)=><path key={i} d={sl.d} fill="none" stroke={sl.color} strokeWidth="10" strokeLinecap="butt"/>)}
    </svg>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  Layout shells
// ══════════════════════════════════════════════════════════════════════════════
function Panel({children,style={},title,titleRight,sub,accent,noPad=false}) {
  return (
    <div style={{background:BG.surface,border:`1px solid ${BG.border}`,borderRadius:14,overflow:'hidden',
      ...(accent?{borderTop:`2px solid ${accent}`}:{}), ...style}}>
      {(title||titleRight)&&(
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',
          padding:'14px 18px 10px',borderBottom:`1px solid ${BG.border2}`}}>
          <div>
            <div style={{fontSize:13,fontWeight:700,color:'#ffffff',fontFamily:'var(--font-display)',letterSpacing:'-.01em'}}>{title}</div>
            {sub&&<div style={{fontSize:10,color:C.text2,marginTop:2}}>{sub}</div>}
          </div>
          {titleRight&&<div style={{flexShrink:0,marginTop:2}}>{titleRight}</div>}
        </div>
      )}
      <div style={noPad?{}:{padding:'14px 18px'}}>{children}</div>
    </div>
  )
}

function MiniCard({label,value,color=C.accent,sub,icon}) {
  return (
    <div style={{background:BG.panel,borderWidth:'2px 1px 1px 1px',borderStyle:'solid',borderColor:`${color} ${BG.border} ${BG.border} ${BG.border}`,borderRadius:10,padding:'10px 12px'}}>
      <div style={{display:'flex',alignItems:'center',gap:5,marginBottom:6}}>
        {icon&&<span style={{fontSize:12}}>{icon}</span>}
        <span style={{fontSize:10,color:C.text2,fontWeight:700,textTransform:'uppercase',letterSpacing:'.06em'}}>{label}</span>
      </div>
      <div style={{fontFamily:'var(--font-display)',fontSize:18,fontWeight:800,color,direction:'ltr'}}>{value}</div>
      {sub&&<div style={{fontSize:10,color:C.text2,marginTop:3}}>{sub}</div>}
    </div>
  )
}

function Chip({label,color=C.amber}) {
  return <span style={{fontSize:9,fontWeight:700,padding:'2px 8px',borderRadius:20,
    color,background:`${color}18`,textTransform:'uppercase',letterSpacing:'.07em'}}>{label}</span>
}

function Legend({color,label}) {
  return <div style={{display:'flex',alignItems:'center',gap:5}}>
    <div style={{width:16,height:2,background:color,borderRadius:2}}/>
    <span style={{fontSize:10,color:C.text2}}>{label}</span>
  </div>
}

// ── Phase 6.2: KPI cause derivation ─────────────────────────────────────────
// Reads ONLY: d.decisions[].reason, d.cashflow.flags, d.root_causes[]
function kpiCause(type, data, tr, lang) {
  const d = data?.data || {}
  const decs   = d.decisions   || []
  const causes = d.root_causes || []
  const cf     = d.cashflow    || {}
  const ratios = d.intelligence?.ratios || {}
  const decReason = domain => { const x=decs.find(v=>v.domain===domain); return x?.reason?(x.reason.split('. ')[0]||x.reason):null }
  const rcTitle   = domain => { const c=causes.find(x=>x.domain===domain||x.domain==='cross_domain'); return c?.title||null }
  const clip = s => (s && s.length > 60 ? s.slice(0, 57) : s)
  switch(type) {
    case 'revenue': {
      const rc = rcTitle('growth'); if (rc) return rc
      return clip(decReason('growth'))
    }
    case 'expenses': {
      const rc = rcTitle('efficiency'); if (rc) return rc
      return clip(decReason('efficiency'))
    }
    case 'net_profit': {
      const rc = rcTitle('profitability'); if (rc) return rc
      const nm = ratios?.profitability?.net_margin_pct
      if (nm?.value == null) return null
      const sk = nm.status === 'good' ? 'stmt_kpi_net_margin_cause_good'
        : nm.status === 'warning' ? 'stmt_kpi_net_margin_cause_warning'
          : 'stmt_kpi_net_margin_cause_risk'
      return tr(sk, { value: formatPctForLang(nm.value, 1, lang) })
    }
    case 'cashflow': {
      const rc = rcTitle('cashflow'); if (rc) return rc
      const flags = cf?.flags
      if (hasFlag(flags, 'single_period')) return tr('dash_cf_single_period_indirect')
      return clip(cf?.reliability_reason)
    }
    case 'net_margin': {
      const rc = rcTitle('profitability'); if (rc) return rc
      const gm = ratios?.profitability?.gross_margin_pct
      return gm?.value != null ? tr('dash_gross_margin_line', { value: formatPctForLang(gm.value, 1, lang) }) : null
    }
    default: return null
  }
}

// ── Phase 6.4: forecast line helper ─────────────────────────────────────────
// Reads ONLY: fcData.scenarios.base.[metric][0].point / confidence
// Returns display string or null — zero frontend calculations
function kpiForecast(type, fcData, tr, fmtFn, lang) {
  if (!fcData?.available) return null
  const base = fcData?.scenarios?.base || {}
  const series = base[type] || []
  const next = series[0]
  if (!next?.point) return null
  const val  = fmtFn ? fmtFn(next.point) : formatFullForLang(next.point, lang)
  const dir  = next.mom_applied != null
    ? next.mom_applied > 0 ? '↑' : next.mom_applied < 0 ? '↓' : '→'
    : ''
  const conf = next.confidence != null ? tr('stmt_kpi_forecast_conf', { confidence: formatPctForLang(next.confidence, 0, lang) }) : ''
  return `${dir} ${val}${conf}`
}

// ══════════════════════════════════════════════════════════════════════════════
//  Health Gauge
// ══════════════════════════════════════════════════════════════════════════════
function HealthGauge({score,label}) {
  if (score==null) return null
  const color=score>=80?C.green:score>=60?C.amber:C.red
  const R=34,cx=42,cy=42,pct=Math.max(0,Math.min(100,score))/100
  const s=-Math.PI/2,e=s+pct*2*Math.PI
  const x1=cx+R*Math.cos(s),y1=cy+R*Math.sin(s),x2=cx+R*Math.cos(e),y2=cy+R*Math.sin(e)
  const arc=`M${x1.toFixed(2)},${y1.toFixed(2)} A${R},${R} 0 ${pct>.5?1:0},1 ${x2.toFixed(2)},${y2.toFixed(2)}`
  const status=score>=80?'excellent':score>=60?'good':score>=40?'warning':'risk'
  return (
    <div style={{display:'flex',flexDirection:'column',alignItems:'center',gap:6}}>
      <svg width="84" height="84" viewBox="0 0 84 84" style={{direction:'ltr',filter:`drop-shadow(0 0 8px ${color}40)`}}>
        {/* Track */}
        <circle cx={cx} cy={cy} r={R} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="6"/>
        {/* Glow layer */}
        <path d={arc} fill="none" stroke={color} strokeWidth="10" strokeLinecap="round" opacity="0.15"/>
        {/* Main arc */}
        <path d={arc} fill="none" stroke={color} strokeWidth="6" strokeLinecap="round"/>
        {/* Score */}
        <text x={cx} y={cy+4} textAnchor="middle" fontSize="20" fontWeight="800"
          fill={color} fontFamily="var(--font-display)">{score}</text>
        <text x={cx} y={cy+16} textAnchor="middle" fontSize="7"
          fill="rgba(255,255,255,0.35)" fontFamily="var(--font-display)">/100</text>
      </svg>
      {label&&(
        <span className={`badge-${status}`} style={{
          fontSize:9,fontWeight:800,padding:'2px 8px',borderRadius:20,
          textTransform:'uppercase',letterSpacing:'.06em',
        }}>{label}</span>
      )}
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  Phase 2 — Executive Health Block
//  Dominant hero block: score + status + one-line summary
//  Reads: health_score_v2, decisions[0], intelligence.status — no calculation
// ══════════════════════════════════════════════════════════════════════════════
function HealthBlock({ score, data, tr, lang }) {
  if (score == null) return null
  const d     = data?.data || {}
  const color = score >= 80 ? C.green : score >= 60 ? C.accent : score >= 40 ? C.amber : C.red
  const status = score >= 80 ? 'excellent' : score >= 60 ? 'good' : score >= 40 ? 'warning' : 'risk'
  const statusLabel = tr(`health_tier_${status}`)

  const headline = tr(`dash_health_narrative_${status}`)

  // Supporting detail — first sentence of top decision reason
  const topDec = (d.decisions || [])[0]
  const summary = topDec?.reason ? topDec.reason.split('. ')[0] : null

  // Ring geometry
  const R=52, cx=62, cy=62, pct=Math.max(0,Math.min(100,score))/100
  const s=-Math.PI*.75, sweep=Math.PI*1.5, e=s+pct*sweep
  const x1=cx+R*Math.cos(s), y1=cy+R*Math.sin(s)
  const x2=cx+R*Math.cos(e), y2=cy+R*Math.sin(e)
  const lg=pct*sweep>Math.PI?1:0
  const arc=`M${x1.toFixed(2)},${y1.toFixed(2)} A${R},${R} 0 ${lg},1 ${x2.toFixed(2)},${y2.toFixed(2)}`
  const trackE=s+sweep, tx=cx+R*Math.cos(trackE), ty=cy+R*Math.sin(trackE)
  const track=`M${x1.toFixed(2)},${y1.toFixed(2)} A${R},${R} 0 1,1 ${tx.toFixed(2)},${ty.toFixed(2)}`

  return (
    <div style={{
      background:BG.panel, borderWidth:'1px', borderStyle:'solid', borderColor:BG.border,
      borderRadius:14, padding:'20px 24px',
      display:'flex', alignItems:'center', gap:24,
      borderTop:`2px solid ${color}`,
    }}>
      {/* Ring */}
      <div style={{flexShrink:0}}>
        <svg width="124" height="124" viewBox="0 0 124 124" style={{direction:'ltr'}}>
          <path d={track} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="7" strokeLinecap="round"/>
          <path d={arc}   fill="none" stroke={color} strokeWidth="7" strokeLinecap="round"/>
          <text x={cx} y={cy+5}  textAnchor="middle" fontSize="28" fontWeight="900"
            fill={color} fontFamily="var(--font-display)" style={{direction:'ltr'}}>{score}</text>
          <text x={cx} y={cy+20} textAnchor="middle" fontSize="9"
            fill="rgba(255,255,255,0.3)" fontFamily="var(--font-display)">/100</text>
        </svg>
      </div>
      {/* Text */}
      <div style={{flex:1, minWidth:0}}>
        <div style={{display:'flex', alignItems:'center', gap:10, marginBottom:6}}>
          <span className={`badge-${status}`} style={{
            fontSize:10, fontWeight:800, padding:'3px 10px', borderRadius:20,
            textTransform:'uppercase', letterSpacing:'.07em',
          }}>{statusLabel}</span>
          <span style={{fontSize:11, color:C.text3, fontFamily:'var(--font-mono)'}}>
            {tr('financial_health')}
          </span>
        </div>
        <div style={{fontSize:20, fontWeight:800, color:C.text1,
          fontFamily:'var(--font-display)', letterSpacing:'-.02em', lineHeight:1.3, marginBottom:8}}>
          {headline}
        </div>
        {summary && (
          <div style={{fontSize:12, color:C.text2, lineHeight:1.6,
            borderLeft:`2px solid ${color}40`, paddingLeft:10,
            overflow:'hidden', textOverflow:'clip', whiteSpace:'nowrap'}} title={summary}>
            <CmdServerText lang={lang} tr={tr}>{summary}</CmdServerText>
          </div>
        )}
      </div>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  Phase 2.1 — AI Insight Block
//  Single prominent AI insight + action under KPI row.
//  Reads: statements.insights, decisions — no calculation
// ══════════════════════════════════════════════════════════════════════════════
function AIInsightBlock({ data, lang, tr }) {  const d  = data?.data || {}
  // Pick best insight: prefer statements insights, fallback to decision reason
  const stmtIns = d.statements?.insights || []
  const topIns  = stmtIns[0]
  const topDec  = (d.decisions || [])[0]

  const insightText = topIns?.message
  ? trDynamic(tr, topIns.message)
  : topDec?.reason
    ? trDynamic(tr, topDec.reason.split('. ')[0])
    : null

const actionText = topDec?.action
  ? trDynamic(
      tr,
      topDec.action.replace(/^1[.)]\.?\s*/,'').split('\n')[0].split(';')[0].trim(),
      80
    )
  : null

  if (!insightText && !actionText) return null

  const domain = topIns?.domain || topDec?.domain || 'growth'
  const domClr = { liquidity:'var(--blue)', profitability:'var(--green)',
                   efficiency:'var(--violet)', leverage:'var(--amber)', growth:'var(--accent)' }
  const dc = domClr[domain] || 'var(--accent)'

  return (
    <div style={{
      background:BG.panel, borderWidth:'1px', borderStyle:'solid', borderColor:BG.border,
      borderRadius:12, padding:'14px 18px',
      display:'flex', alignItems:'flex-start', gap:14,
      borderLeft:`3px solid ${dc}`,
    }}>
      <div style={{fontSize:20, flexShrink:0, marginTop:1}}>🧠</div>
      <div style={{flex:1, minWidth:0}}>
        <div style={{fontSize:9, fontWeight:700, color:C.text3,
          textTransform:'uppercase', letterSpacing:'.08em', marginBottom:5}}>
          {tr('dash_ai_insight_title')}
        </div>
        {insightText && (
          <div style={{fontSize:13, fontWeight:600, color:C.text1, lineHeight:1.6, marginBottom:6,
            overflow:'hidden', textOverflow:'clip', whiteSpace:'nowrap'}} title={insightText}>
            <CmdServerText lang={lang} tr={tr}>{insightText}</CmdServerText>
          </div>
        )}
        {actionText && (
          <div style={{
            display:'inline-flex', alignItems:'center', gap:6,
            fontSize:11, color:dc, fontWeight:600,
            background:`${dc}10`, borderWidth:'1px', borderStyle:'solid',
            borderColor:`${dc}25`, borderRadius:8, padding:'4px 10px',
            maxWidth:'100%', overflow:'hidden',
          }}>
            <span>⚡</span>
            <span style={{overflow:'hidden', textOverflow:'clip', whiteSpace:'nowrap'}} title={actionText}>
              {tr('dash_action_prefix')}{' '}
              <CmdServerText lang={lang} tr={tr}>{actionText}</CmdServerText>
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  Phase 2 — Action Strip
//  Top 3 prioritised decisions as compact action chips.
//  Reads: d.decisions — no calculation
// ══════════════════════════════════════════════════════════════════════════════
function ActionStrip({ data, tr, lang }) {
  const d    = data?.data || {}
  const decs = (d.decisions || []).slice(0, 3)
  if (!decs.length) return null

  const urgClr  = { high: C.red, medium: C.amber, low: C.blue }
  const urgLabel = (u) => tr(`urgency_${u || 'low'}`)
  const domIco = { liquidity:'💧', profitability:'📈', efficiency:'⚡', leverage:'🏋', growth:'🚀' }

  return (
    <div style={{display:'flex', flexDirection:'column', gap:8}}>
      <div style={{fontSize:9, fontWeight:700, color:C.text3,
        textTransform:'uppercase', letterSpacing:'.09em', marginBottom:0}}>
        {tr('dash_immediate_priorities')}
      </div>
      <div style={{display:'grid', gridTemplateColumns:'repeat(3, 1fr)', gap:10}}>
        {decs.map((dec, i) => {
          const uc    = urgClr[dec.urgency]  || C.text2
          const ulbl  = urgLabel(dec.urgency)
          const ico   = domIco[dec.domain]   || '🎯'
          // First action step (read from existing field, no calculation)
         // First action step (read from existing field, no calculation)
const actionLine = dec.action
  ? trDynamic(
      tr,
      dec.action.replace(/^1[.)]\.?\s*/,'').split('\n')[0].split(';')[0].trim(),
      72
    )
  : null

// Expected effect — first sentence (read from existing field)
const impact = dec.expected_effect
  ? trDynamic(tr, dec.expected_effect.split('. ')[0], 60)
  : null
          return (
            <div key={i} style={{
              background:BG.panel, borderWidth:'2px 1px 1px 1px', borderStyle:'solid',
              borderColor:`${uc} ${BG.border} ${BG.border} ${BG.border}`,
              borderRadius:12, padding:'14px 16px',
              display:'flex', flexDirection:'column', gap:7,
              transition:'box-shadow .18s',
            }}>
              {/* Priority badge + icon */}
              <div style={{display:'flex', alignItems:'center', justifyContent:'space-between'}}>
                <div style={{display:'flex', alignItems:'center', gap:6}}>
                  <span style={{fontSize:15}}>{ico}</span>
                  <span style={{
                    fontSize:9, fontWeight:900, padding:'2px 8px', borderRadius:20,
                    background:`${uc}16`, color:uc,
                    textTransform:'uppercase', letterSpacing:'.08em',
                  }}>{ulbl}</span>
                </div>
                <span style={{fontSize:9, color:C.text3, fontFamily:'var(--font-mono)'}}>
                  {String(i + 1).padStart(2,'0')}
                </span>
              </div>
              {/* Title */}
              <div style={{fontSize:13, fontWeight:700, color:C.text1, lineHeight:1.35,
                overflow:'hidden', textOverflow:'clip', whiteSpace:'nowrap'}} title={trDynamic(tr, dec.title)}>
                <CmdServerText lang={lang} tr={tr}>{trDynamic(tr, dec.title)}</CmdServerText>
              </div>
              {/* Action line */}
              {actionLine && (
                <div style={{
                  fontSize:10, color:C.text2, lineHeight:1.5,
                  paddingLeft:8, borderLeft:`2px solid ${uc}40`,
                  overflow:'hidden', textOverflow:'clip', whiteSpace:'nowrap',
                }} title={actionLine}>
                  <CmdServerText lang={lang} tr={tr}>{actionLine}</CmdServerText>
                </div>
              )}
              {/* Impact line */}
              {impact && (
                <div style={{fontSize:9, color:C.text3, lineHeight:1.4, marginTop:-2,
                  overflow:'hidden', textOverflow:'clip', whiteSpace:'nowrap'}} title={impact}>
                  ✦ <CmdServerText lang={lang} tr={tr}>{impact}</CmdServerText>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  KPI Card — with hover intelligence + drill-down
// ══════════════════════════════════════════════════════════════════════════════
function KpiCard({labelKey,value,fullValue,mom,yoy,color,icon,spark,tr,lang,kpiType,onClick,ytdValue,ytdTrend,sub,insight,cause,forecast,momWord,yoyWord}) {
  const [hov,setHov]=useState(false)
  return (
    <div
      onClick={onClick}
      onMouseEnter={()=>setHov(true)}
      onMouseLeave={()=>setHov(false)}
      style={{
        background: hov
          ? `linear-gradient(160deg, ${BG.card}, ${BG.panel})`
          : BG.panel,
        borderWidth: '2px 1px 1px 1px',
        borderStyle: 'solid',
        borderColor: `${color} ${hov ? color+'60' : BG.border} ${hov ? color+'60' : BG.border} ${hov ? color+'60' : BG.border}`,
        borderRadius: 14,
        padding: '14px 16px',
        flex: 1, minWidth: 0,
        position: 'relative',
        overflow: 'visible',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'all 0.2s cubic-bezier(0.4,0,0.2,1)',
        transform: hov ? 'translateY(-2px)' : 'none',
        boxShadow: hov
          ? `0 12px 32px rgba(0,0,0,0.5), 0 0 0 1px ${color}20, 0 -2px 16px ${color}12`
          : '0 2px 8px rgba(0,0,0,0.25)',
      }}>
      {/* ① Label row — icon + name + MoM chip */}
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:8}}>
        <div style={{display:'flex',alignItems:'center',gap:5}}>
          <span style={{fontSize:13,opacity:0.85}}>{icon}</span>
          <span style={{fontSize:9,color:C.text3,fontWeight:700,
            textTransform:'uppercase',letterSpacing:'.07em'}}>{tr(labelKey)}</span>
        </div>
        {mom!=null&&(
          <span style={{
            fontSize:10,fontWeight:800,color:clr(mom),
            fontFamily:'var(--font-mono)',padding:'1px 6px',
            borderRadius:10,background:`${clr(mom)}14`,lineHeight:1.4,
          }}>
            {arr(mom)} {formatPctForLang(Math.abs(mom), 1, lang)} {momWord}
          </span>
        )}
      </div>
      {/* ② Value — largest element */}
      <div style={{
        fontFamily:'var(--font-display)',
        fontSize:28,fontWeight:900,color:'#ffffff',
        letterSpacing:'-.03em',lineHeight:1,direction:'ltr',
        marginBottom:2,
      }}>
        {value}
      </div>
      {/* ② Full exact value — secondary line */}
      {fullValue&&<div style={{
        fontFamily:'var(--font-mono)',fontSize:9,color:C.text3,
        letterSpacing:'.02em',marginBottom:3,direction:'ltr',
      }}>{fullValue}</div>}
      {/* ③ YoY secondary */}
      {yoy!=null&&<div style={{fontSize:9,color:clr(yoy),fontFamily:'var(--font-mono)',
        marginBottom:3}}>{arr(yoy)} {formatPctForLang(Math.abs(yoy), 1, lang)} {yoyWord}</div>}
      {sub&&<div style={{fontSize:9,color:C.text3,marginBottom:3}}>{sub}</div>}
      {/* ④ Cause — 1 concise line */}
      {cause&&<div style={{fontSize:9,color:C.text3,marginTop:4,lineHeight:1.4,
        overflow:'hidden',textOverflow:'clip',whiteSpace:'nowrap',
        paddingLeft:6,borderLeft:`2px solid ${color}30`}} title={cause}>
        {lang ? <CmdServerText lang={lang} tr={tr}>{cause}</CmdServerText> : cause}
      </div>}
      {/* ⑤ Forecast — accent mono */}
      {forecast&&<div style={{fontSize:9,color:'var(--accent)',marginTop:2,lineHeight:1.3,
        fontFamily:'var(--font-mono)',opacity:.8,
        overflow:'hidden',textOverflow:'clip',whiteSpace:'nowrap'}}
        title={forecast}>
        📈 {lang ? <CmdServerText lang={lang} tr={tr} style={{fontFamily:'var(--font-mono)'}}>{forecast}</CmdServerText> : forecast}
      </div>}
      {ytdValue&&<div style={{display:'flex',alignItems:'center',gap:5,marginTop:5,paddingTop:5,borderTop:`1px solid ${BG.border}`}}>
        <span style={{fontSize:9,color:C.text3,textTransform:'uppercase',letterSpacing:'.05em'}}>{tr('al_ytd_label')}</span>
        <span style={{fontSize:11,fontWeight:700,color:C.text2,fontFamily:'var(--font-mono)',direction:'ltr'}}>{ytdValue}</span>
        {ytdTrend!=null&&<span style={{fontSize:9,fontWeight:700,color:ytdTrend>=0?C.green:C.red,fontFamily:'var(--font-mono)'}}>{ytdTrend>=0?'▲':'▼'}{formatPctForLang(Math.abs(ytdTrend), 1, lang)}</span>}
      </div>}
      {/* Sparkline */}
      {spark&&<div style={{marginTop:8,opacity:hov?1:0.7,transition:'opacity .2s'}}><SparkLine data={spark} color={color}/></div>}
      {/* Hover tooltip */}
      <KpiHoverTip visible={hov} mom={mom} type={kpiType} tr={tr}/>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  AI Insight Row
// ══════════════════════════════════════════════════════════════════════════════
function InsightRow({type,text,sub,impact}) {
  const cfg={
    warning:{icon:'⚠',color:C.amber,bg:`${C.amber}0d`},
    rec:    {icon:'💡',color:C.violet,bg:`${C.violet}0d`},
    positive:{icon:'✓',color:C.green,bg:`${C.green}0d`},
    info:   {icon:'ℹ',color:C.blue,bg:`${C.blue}0d`},
  }
  const impC={critical:C.red,high:C.amber,medium:C.violet,low:C.green}
  const c=cfg[type]||cfg.info
  return (
    <div style={{display:'flex',gap:10,padding:'11px 14px',borderBottom:`1px solid ${BG.border2}`,background:c.bg}}>
      <span style={{fontSize:14,flexShrink:0,marginTop:1}}>{c.icon}</span>
      <div style={{flex:1,minWidth:0}}>
        <div style={{display:'flex',justifyContent:'space-between',gap:6,alignItems:'flex-start',marginBottom:sub?4:0}}>
          <div style={{fontSize:12,color:C.text1,lineHeight:1.45,fontWeight:500,flex:1}}>{text}</div>
          {impact&&<Chip label={impact} color={impC[impact]||c.color}/>}
        </div>
        {sub&&<div style={{fontSize:11,color:C.text2,lineHeight:1.4}}>{sub}</div>}
      </div>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  Tab Nav
// ══════════════════════════════════════════════════════════════════════════════
function TabNav({tabs,active,onChange}) {
  return (
    <div style={{display:'flex',gap:1,borderBottom:`1px solid ${BG.border}`,marginBottom:20}}>
      {tabs.map(t=>(
        <button key={t.key} onClick={()=>onChange(t.key)} style={{
          padding:'10px 18px',fontSize:12,fontWeight:active===t.key?700:500,
          color:active===t.key?'#ffffff':C.text2,background:'transparent',border:'none',
          borderBottom:`2px solid ${active===t.key?C.accent:'transparent'}`,
          cursor:'pointer',transition:'all .15s',letterSpacing:'.02em',fontFamily:'var(--font-display)',
          marginBottom:-1,whiteSpace:'nowrap'}}>
          {t.label}
          {t.badge!=null&&<span style={{marginLeft:6,fontSize:9,fontWeight:700,padding:'1px 6px',borderRadius:20,
            background:active===t.key?`${C.accent}20`:BG.card,color:active===t.key?'#ffffff':C.text3}}>{t.badge}</span>}
        </button>
      ))}
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  Variance Bridge
// ══════════════════════════════════════════════════════════════════════════════
function VarianceBridge({ curr, prev, tr, lang }) {
  if (!curr||!prev) return <div style={{color:C.text2,fontSize:12,textAlign:'center',padding:'20px 0'}}>{tr('var_insufficient')}</div>
  const rows=[
    {label:tr('kpi_total_revenue'),    curr:curr.revenue,     prev:prev.revenue,     color:C.accent},
    {label:tr('exp_cogs_label'),curr:curr.cogs,        prev:prev.cogs,        color:C.amber, inverse:true},
    {label:tr('gross_profit'), curr:curr.gross_profit,prev:prev.gross_profit,color:C.blue,  bold:true},
    {label:tr('opex'),          curr:curr.opex,        prev:prev.opex,        color:C.amber, inverse:true},
    {label:tr('kpi_net_profit'),        curr:curr.net_profit,  prev:prev.net_profit,  color:C.green, bold:true},
  ]
  const maxAbs=Math.max(...rows.map(r=>Math.abs((r.curr||0)-(r.prev||0))),1)
  return (
    <div style={{display:'flex',flexDirection:'column',gap:6}}>
      {rows.map((r,i)=>{
        const delta=(r.curr||0)-(r.prev||0)
        const pct=r.prev?delta/Math.abs(r.prev)*100:null
        const isPos=r.inverse?delta<=0:delta>=0
        const barW=Math.abs(delta)/maxAbs*100
        return (
          <div key={i} style={{display:'grid',gridTemplateColumns:'130px 1fr 80px 68px',gap:8,alignItems:'center',direction:'ltr'}}>
            <span style={{fontSize:11,color:r.bold?C.text1:C.text2,fontWeight:r.bold?700:400}}>{r.label}</span>
            <div style={{position:'relative',height:r.bold?20:14,background:BG.card,borderRadius:3,overflow:'hidden'}}>
              <div style={{position:'absolute',top:0,height:'100%',width:`${barW}%`,
                left:delta<0?`${100-barW}%`:0,background:isPos?C.green:C.red,opacity:.7,borderRadius:3}}/>
            </div>
            <span style={{fontSize:11,fontFamily:'monospace',color:isPos?C.green:C.red,fontWeight:700,textAlign:'right'}}>
              {pSign(delta)}{formatCompactForLang(delta, lang)}
            </span>
            <span style={{fontSize:10,color:isPos?C.green:C.red,textAlign:'right'}}>
              {pct != null
                ? pct > 0
                  ? `+${formatPctForLang(pct, 1, lang)}`
                  : formatPctForLang(pct, 1, lang)
                : '—'}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  Expense Breakdown
// ══════════════════════════════════════════════════════════════════════════════
function ExpenseBreakdown({ items, total, lang = 'en' }) {
  if (!items||!items.length) return <div style={{color:C.text2,fontSize:12,padding:'20px 0',textAlign:'center'}}>—</div>
  const colors=[C.violet,C.amber,C.blue,C.red,C.accent,C.green,'#ff9f43','#a29bfe']
  const top=items.slice(0,8)
  return (
    <div style={{display:'grid',gridTemplateColumns:'90px 1fr',gap:16,alignItems:'center'}}>
      <DonutChart segments={top.map((it,i)=>({value:Math.abs(it.amount),color:colors[i%colors.length]}))} size={90}/>
      <div style={{display:'flex',flexDirection:'column',gap:5}}>
        {top.map((it,i)=>{
          const pct=total?Math.abs(it.amount)/Math.abs(total)*100:0
          return (
            <div key={i} style={{display:'flex',alignItems:'center',gap:6}}>
              <div style={{width:8,height:8,borderRadius:'50%',background:colors[i%colors.length],flexShrink:0}}/>
              <div style={{flex:1,minWidth:0}}>
                <div style={{fontSize:11,color:C.text2,overflow:'hidden',textOverflow:'clip',whiteSpace:'nowrap'}}>{it.account_name}</div>
              </div>
              <span style={{fontSize:11,fontWeight:700,color:C.text1,fontFamily:'monospace',direction:'ltr'}}>{formatCompactForLang(Math.abs(it.amount), lang)}</span>
              <span style={{fontSize:10,color:C.text2}}>{formatPctForLang(pct, 0, lang)}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  Branch Panel
// ══════════════════════════════════════════════════════════════════════════════
function BranchPanel({companyId,tr}) {
  const { lang } = useLang()
  const { toQueryString, window: win } = usePeriodScope()
  const [d,setD]=useState(null)
  useEffect(()=>{
    if (!companyId) return
    const qs = buildAnalysisQuery(toQueryString, { lang, window: win, consolidate: false })
    if (qs === null) return
    fetch(`${API}/companies/${companyId}/branch-comparison?${qs}`, { headers: getAuthHeaders() }).then(r=>r.json()).then(setD).catch(()=>{})
  },[companyId, lang, win, toQueryString])
  if (!d) return <div style={{height:50,display:'flex',alignItems:'center',justifyContent:'center'}}><div style={{width:16,height:16,border:`2px solid ${BG.border}`,borderTopColor:C.accent,borderRadius:'50%',animation:'spin .8s linear infinite'}}/></div>
  if (!d.has_data) return (
    <div style={{padding:'24px',textAlign:'center',border:`1px dashed ${BG.border}`,borderRadius:10}}>
      <div style={{fontSize:28,marginBottom:8,opacity:.3}}>🏢</div>
      <div style={{fontSize:12,fontWeight:600,color:C.text2,marginBottom:6}}>{tr('branches_config')}</div>
      <div style={{fontSize:10,color:C.text2}}>{tr('branches_hint')}</div>
    </div>
  )
  return d.ranking.slice(0,5).map((b,i)=>(
    <div key={b.branch_id} style={{display:'flex',alignItems:'center',gap:10,padding:'8px 0',borderBottom:`1px solid ${BG.border2}`}}>
      <span style={{width:20,height:20,borderRadius:6,background:i===0?`${C.accent}20`:BG.card,
        border:`1px solid ${i===0?C.accent:BG.border}`,display:'flex',alignItems:'center',
        justifyContent:'center',fontSize:9,fontWeight:800,color:i===0?C.accent:C.text2,flexShrink:0}}>{i+1}</span>
      <div style={{flex:1,minWidth:0}}>
        <div style={{fontSize:12,fontWeight:600,color:C.text1,overflow:'hidden',textOverflow:'clip',whiteSpace:'nowrap'}}>{b.branch_name}</div>
        {b.city&&<div style={{fontSize:10,color:C.text2}}>{b.city}</div>}
      </div>
      <div style={{textAlign:'right',flexShrink:0}}>
        <div style={{fontSize:12,fontWeight:700,fontFamily:'monospace',color:C.accent,direction:'ltr'}}>{formatCompactForLang(b.revenue, lang)}</div>
        {b.net_margin!=null&&<div style={{fontSize:9,color:clr(b.net_margin),fontFamily:'monospace',direction:'ltr'}}>{formatPctForLang(b.net_margin,1,lang)}</div>}
      </div>
      {b.mom_revenue_pct!=null&&<span style={{fontSize:10,fontWeight:700,color:clr(b.mom_revenue_pct),minWidth:40,textAlign:'right',direction:'ltr'}}>{arr(b.mom_revenue_pct)}{b.mom_revenue_pct>0?`+${formatPctForLang(b.mom_revenue_pct,1,lang)}`:formatPctForLang(b.mom_revenue_pct,1,lang)}</span>}
    </div>
  ))
}


// ── FIX-4.3: DataQualityBanner ────────────────────────────────────────────────
function DataQualityBanner({ validation, lang, tr }) {
  if (!validation) return null
  const { consistent, warnings = [], has_errors, has_info } = validation
  if (consistent === true && !has_info) return null
  const color = has_errors ? '#f87171' : '#fbbf24'
  const bg    = has_errors ? 'rgba(248,113,113,0.06)' : 'rgba(251,191,36,0.06)'
  const bdr   = has_errors ? 'rgba(248,113,113,0.22)' : 'rgba(251,191,36,0.22)'
  return (
    <div style={{display:'flex',flexWrap:'wrap',alignItems:'center',gap:10,
      padding:'7px 14px',borderRadius:8,marginBottom:10,
      background:bg,borderWidth:'1px 1px 1px 3px',borderStyle:'solid',borderColor:`${bdr} ${bdr} ${bdr} ${color}`}}>
      <span style={{fontSize:12}}>{has_errors?'⚠':'ℹ'}</span>
      <span style={{fontSize:10,fontWeight:700,color,letterSpacing:'.04em'}}>
        {has_errors ? tr('dq_warning_title') : tr('dq_notice_title')}:
      </span>
      {warnings.map((w,i)=>{
        return <span key={i} style={{fontSize:10,color:'rgba(255,255,255,0.55)'}}>· {tr(`dq_${w.code}`)}</span>
      })}
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  TAB 1: Overview
// ══════════════════════════════════════════════════════════════════════════════
function OverviewTab({data,tr,lang,onKpiClick}) {
  const d = data?.data || {}
  const meta = data?.meta || {}
  const s=d.kpi_block?.series||{}, p=d.kpi_block?.periods||[], k=d.kpi_block?.kpis||{}
  const liq=d.intelligence?.ratios?.liquidity||{}, cf=d.cashflow||{}
  return (
    <div style={{display:'flex',flexDirection:'column',gap:16}}>
      <div style={{display:'grid',gridTemplateColumns:'1.5fr 1fr',gap:14}}>
        <Panel title={tr('chart_rev_vs_exp')}
          sub={`${p.length} ${tr('chart_months_label')} · ${data?.company_name||''}`}
          titleRight={<div style={{display:'flex',gap:12}}><Legend color={C.accent} label={tr('legend_revenue')}/><Legend color={C.red} label={tr('legend_expenses')}/></div>}>
          <AreaChart lang={lang} d1={s.revenue} d2={s.expenses} labels={p} c1={C.accent} c2={C.red} h={180} n1={tr('legend_revenue')} n2={tr('legend_expenses')} showBars/>
        </Panel>
        <Panel title={tr('kpi_net_profit')}>
          <AreaChart lang={lang} d1={s.net_profit} labels={p} c1={C.green} h={180} n1={tr('kpi_net_profit')}/>
        </Panel>
      </div>
      {cf?.operating_cashflow!=null&&(
        <Panel title={tr('cashflow_operating')} titleRight={(() => {
          const q = cf.quality?.cash_conversion_quality
          if (q == null || q === '') return null
          const qc = q === 'strong' ? C.green : q === 'moderate' ? C.amber : C.red
          const known = q === 'strong' || q === 'moderate' || q === 'weak'
          const inner = known ? tr(`cashflow_quality_${q}`) : <CmdServerText lang={lang} tr={tr}>{q}</CmdServerText>
          return <Chip label={inner} color={qc}/>
        })()}>
          <div style={{display:'grid',gridTemplateColumns:'1fr 280px',gap:14}}>
            <AreaChart lang={lang} d1={cf.series?.operating_cashflow} d2={cf.series?.net_profit} labels={cf.series?.periods} c1={C.accent} c2={C.violet} h={140} n1={tr('cashflow_ocf_label')} n2={tr('kpi_net_profit')}/>
            <div style={{display:'flex',flexDirection:'column',gap:8}}>
              {[
                {lbl:tr('cashflow_operating'),val:formatCompactForLang(cf.operating_cashflow,lang),c:(cf.operating_cashflow||0)>=0?C.accent:C.red,sub:cf.operating_cashflow_mom!=null?`${arr(cf.operating_cashflow_mom)} ${cf.operating_cashflow_mom>0?`+${formatPctForLang(cf.operating_cashflow_mom,1,lang)}`:formatPctForLang(cf.operating_cashflow_mom,1,lang)} ${tr('mom_label')}`:null},
                {lbl:tr('cashflow_free'),val:cf.free_cashflow!=null?formatCompactForLang(cf.free_cashflow,lang):'—',c:(cf.free_cashflow||0)>=0?C.green:C.red,sub:hasFlag(cf.flags,'capex_missing')?tr('cashflow_capex_unknown'):null},
                {lbl:tr('cashflow_balance'),val:formatCompactForLang(cf.cash_balance,lang),c:C.blue,sub:tr('cashflow_available')},
                {lbl:tr('cashflow_quality_title'),val:cf.quality?.cash_conversion_ratio!=null?formatMultipleForLang(cf.quality.cash_conversion_ratio,2,lang):'—',c:C.violet},
              ].map((x,i)=><MiniCard key={i} label={x.lbl} value={x.val} color={x.c} sub={x.sub}/>)}
            </div>
          </div>
          {/* FIX-3.5: Cash flow reliability badge */}
          {cf.reliability==='estimated'&&(
            <div style={{display:'flex',alignItems:'center',gap:6,
              marginTop:10,padding:'6px 12px',borderRadius:8,
              background:'rgba(251,191,36,0.07)',
              border:'1px solid rgba(251,191,36,0.22)'}}>
              <span style={{fontSize:13}}>⚠</span>
              <span style={{fontSize:10,color:C.amber,lineHeight:1.4}}>
                {tr('dash_ocf_estimate_banner')}
              </span>
            </div>
          )}
        </Panel>
      )}
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14}}>
        <Panel title={tr('company_overview')}>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:6}}>
            {[
              {lbl:tr('overview_periods'),val:meta.period_count??'—',c:C.accent},
              {lbl:tr('overview_latest'),val:p.at(-1)??'—',c:C.text1},
              {lbl:tr('overview_op_margin'),val:formatPctForLang(k.operating_margin?.value,1,lang),c:C.green},
              {lbl:tr('overview_quick_ratio'),val:liq.quick_ratio!=null?formatMultipleForLang(liq.quick_ratio,2,lang):'—',c:C.blue},
              {lbl:tr('prof_ccc'),val:formatDays(data?.analysis?.latest?.efficiency?.ccc_days),c:C.violet},
              {lbl:tr('kpi_ebitda_margin'),val:formatPctForLang(d.advanced_metrics?.profitability?.ebitda_margin_pct,1,lang),c:C.amber},
            ].map((r,i)=>(
              <div key={i} style={{background:BG.panel,border:`1px solid ${BG.border}`,borderRadius:8,padding:'9px 11px'}}>
                <div style={{fontSize:10,color:C.text2,textTransform:'uppercase',letterSpacing:'.06em',marginBottom:4}}>{r.lbl}</div>
                <div style={{fontSize:15,fontWeight:700,fontFamily:'monospace',color:r.c,direction:'ltr'}}>{r.val}</div>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title={tr('top_branches')} noPad>
          <div style={{padding:'0 14px 12px'}}><BranchPanel companyId={data?.company_id} tr={tr}/></div>
        </Panel>
      </div>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  TAB 2: Expense Analysis — with intelligence layer
// ══════════════════════════════════════════════════════════════════════════════
function ExpenseTab({ data, tr, lang }) {
  const d = data?.data || {}
  const bundle = d.statements || {}
  const latIS = bundle?.income_statement || null
  const trends=d.intelligence?.trends||{}, tPerds=trends.periods||[]
  if (!latIS) return (
    <div style={{display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',padding:'60px',gap:8}}>
      <span style={{fontSize:36,opacity:.3}}>📊</span>
      <div style={{fontSize:13,color:C.text2}}>{tr('exp_upload_hint')||tr('upload_for_insights')}</div>
    </div>
  )
  const expItems=latIS.items?.expenses||[], cogsItems=latIS.items?.cogs||[]
  const totalExp=latIS.operating_expenses||0, totalCogs=latIS.cogs||0
  const totalRev=latIS.revenue||1
  const cs=d.advanced_metrics?.risk?.cost_structure||{}
  const prevMap = {}  // previous-period comparison not available in statement_bundle

  // Expense intelligence — find top rising expense
  const rising=expItems.map(it=>{
    const prev=prevMap[it.account_code]
    const delta=prev!=null?it.amount-prev:null
    const pct=prev&&prev!==0?delta/Math.abs(prev)*100:null
    return {...it, delta, pct}
  }).filter(it=>it.pct!=null&&it.pct>10).sort((a,b)=>b.pct-a.pct)
  const topRising=rising[0]
  const hasSpike=rising.some(it=>it.pct>30)

  return (
    <div style={{display:'flex',flexDirection:'column',gap:16}}>
      {/* Intelligence banner */}
      {(topRising||hasSpike)&&(
        <div style={{background:`${hasSpike?C.red:C.amber}10`,border:`1px solid ${hasSpike?C.red:C.amber}30`,
          borderRadius:12,padding:'12px 16px',display:'flex',gap:12,alignItems:'flex-start'}}>
          <span style={{fontSize:16,flexShrink:0}}>{hasSpike?'🚨':'📊'}</span>
          <div style={{flex:1}}>
            <div style={{fontSize:12,fontWeight:700,color:hasSpike?C.red:C.amber,marginBottom:3}}>
              {tr('exp_exec_summary')} {hasSpike&&`— ${tr('exp_spike_warning')}`}
            </div>
            {topRising&&(
              <div style={{fontSize:11,color:C.text2}}>
                <span style={{fontWeight:600,color:C.text1}}>{topRising.account_name}</span>
                {' '}{tr('exp_spike_pct')}{' '}
                <span style={{color:C.red,fontWeight:700,direction:'ltr',display:'inline-block'}}>
                  {formatSignedPctForLang(topRising.pct, 1, lang)}
                </span>
                {' '}({tr('exp_vs_rev_label')}: {formatPctForLang(Math.abs(topRising.amount)/totalRev*100,1,lang)})
              </div>
            )}
            {!topRising&&<div style={{fontSize:11,color:C.text2}}>{tr('exp_no_spike')}</div>}
          </div>
        </div>
      )}

      {/* Cost structure summary */}
      <div style={{display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:12}}>
        {[
          {lbl:`${tr('exp_cogs_label')} %`,val:formatPctForLang(cs.latest_cogs_pct,1,lang),sub:`avg ${formatPctForLang(cs.avg_cogs_pct,1,lang)}`,c:C.amber,icon:'📦'},
          {lbl:`${tr('exp_opex_label')} %`,val:formatPctForLang(cs.latest_opex_pct,1,lang),sub:`avg ${formatPctForLang(cs.avg_opex_pct,1,lang)}`,c:C.violet,icon:'⚙️'},
          {lbl:tr('exp_total_load'),val:formatPctForLang((cs.latest_cogs_pct||0)+(cs.latest_opex_pct||0),1,lang),sub:tr('exp_of_revenue'),c:((cs.latest_cogs_pct||0)+(cs.latest_opex_pct||0))>90?C.red:C.green,icon:'📊'},
          {lbl:tr('exp_structure'),val:cs.cost_structure_type||'—',sub:`${tr('exp_cogs_label')}:${tr('exp_opex_label')} = ${formatMultipleForLang(cs.cogs_to_opex_ratio,2,lang)}`,c:C.accent,icon:'⚖️'},
        ].map((x,i)=><MiniCard key={i} label={x.lbl} value={x.val} color={x.c} sub={x.sub} icon={x.icon}/>)}
      </div>

      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14}}>
      <Panel title={tr('exp_breakdown')} sub={`${tr('exp_period_label')}: ${latIS.period||'—'} · ${formatCompactForLang(totalExp, lang)}`}>
          <ExpenseBreakdown items={expItems} total={totalExp} lang={lang}/>
        </Panel>
        <Panel title={tr('exp_cogs_title')} sub={`${formatPctForLang(cs.latest_cogs_pct, 1, lang)} ${tr('exp_of_revenue')} · ${formatCompactForLang(totalCogs, lang)}`}>
          <ExpenseBreakdown items={cogsItems} total={totalCogs} lang={lang}/>
        </Panel>
      </div>

      <Panel title={tr('exp_top_drivers')} sub={`${latIS.period||'—'}`}>
        <div style={{display:'flex',flexDirection:'column',gap:0}}>
          {expItems.slice(0,8).map((it,i)=>{
            const prev=prevMap[it.account_code]
            const delta=prev!=null?it.amount-prev:null
            const pct=prev&&prev!==0?delta/Math.abs(prev)*100:null
            const isUp=delta!=null&&delta>0
            const barW=totalExp?Math.abs(it.amount)/totalExp*100:0
            const isSpike=pct!=null&&pct>30
            return (
              <div key={i} style={{display:'grid',gridTemplateColumns:'160px 1fr 80px 70px 80px',gap:8,alignItems:'center',
                padding:'7px 0',borderBottom:`1px solid ${BG.border2}`,
                background:isSpike?`${C.red}06`:'transparent',direction:'ltr'}}>
                <span style={{fontSize:11,color:isSpike?C.red:C.text2,overflow:'hidden',textOverflow:'clip',whiteSpace:'nowrap',fontWeight:isSpike?600:400}}>
                  {it.account_name}{isSpike?' 🚨':''}
                </span>
                <div style={{background:BG.card,borderRadius:3,height:12,overflow:'hidden',position:'relative'}}>
                  <div style={{position:'absolute',left:0,top:0,height:'100%',width:`${barW}%`,background:isSpike?C.red:C.violet,opacity:.6,borderRadius:3}}/>
                </div>
                <span style={{fontSize:11,fontWeight:700,fontFamily:'monospace',color:C.text1,textAlign:'right'}}>{formatCompactForLang(Math.abs(it.amount), lang)}</span>
                <span style={{fontSize:10,color:C.text2,textAlign:'right'}}>{totalRev?formatPctForLang(Math.abs(it.amount)/totalRev*100,1,lang):'—'}</span>
                {delta!=null
                  ?<span style={{fontSize:10,fontWeight:700,color:isUp?C.red:C.green,textAlign:'right'}}>{pSign(delta)}{formatCompactForLang(delta, lang)}</span>
                  :<span style={{fontSize:10,color:C.text2,textAlign:'right'}}>—</span>}
              </div>
            )
          })}
          <div style={{display:'grid',gridTemplateColumns:'160px 1fr 80px 70px 80px',gap:8,marginTop:6,direction:'ltr'}}>
            {[tr('exp_account'),'',tr('exp_amount'),tr('exp_pct_rev'),tr('exp_vs_prior')].map((h,i)=>(
              <span key={i} style={{fontSize:10,color:C.text2,textAlign:i>1?'right':'left'}}>{h}</span>
            ))}
          </div>
        </div>
      </Panel>

      <Panel title={tr('exp_trend')} sub={`${tPerds.length} ${tr('gen_periods')}`}
        titleRight={<div style={{display:'flex',gap:12}}><Legend color={C.amber} label={tr('exp_opex_label')}/><Legend color={C.red} label={tr('exp_cogs_label')}/></div>}>
        <AreaChart lang={lang} d1={trends.expenses_series} d2={trends.cogs_series} labels={tPerds} c1={C.amber} c2={C.red} h={160} n1={tr('exp_opex_label')} n2={tr('exp_cogs_label')}/>
      </Panel>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  TAB 3: Variance
// ══════════════════════════════════════════════════════════════════════════════
function VarianceTab({ data, tr, lang }) {
  const d = data?.data || {}
  // Executive /analysis/{id}/executive returns data.statements as statement_engine bundle:
  // { income_statement, balance_sheet, cashflow, series, summary, insights } — not { period: stmt }.
  const bundle = d.statements || {}
  const latIS = bundle?.income_statement || null
  const trends=d.intelligence?.trends||{}, tPerds=trends.periods||[]
  const momSer=d.kpi_block?.mom_series||{}, kPerds=d.kpi_block?.periods||[]
  const idxLast = tPerds.length - 1
  const idxPrev = tPerds.length - 2
  const latP = (idxLast >= 0 && tPerds[idxLast]) || bundle.period || latIS?.period || '—'
  const prevP = idxPrev >= 0 ? tPerds[idxPrev] : '—'
  const curr = latIS ? {
    revenue: latIS.revenue,
    cogs: latIS.cogs,
    gross_profit: latIS.gross_profit,
    opex: latIS.operating_expenses,
    net_profit: latIS.net_profit,
  } : null
  const prev = idxPrev >= 0 ? {
    revenue: trends.revenue_series?.[idxPrev],
    cogs: trends.cogs_series?.[idxPrev],
    gross_profit: (trends.revenue_series?.[idxPrev] != null && trends.cogs_series?.[idxPrev] != null)
      ? trends.revenue_series[idxPrev] - trends.cogs_series[idxPrev]
      : null,
    opex: trends.expenses_series?.[idxPrev],
    net_profit: trends.net_profit_series?.[idxPrev],
  } : null
  const yoy=d.intelligence?.trends?.revenue?.yoy_change!=null

  // Executive summary for variance
  const execMsg=curr&&prev
    ? (curr.net_profit>prev.net_profit ? tr('var_exec_profit_up') : tr('var_exec_profit_down'))
    : null

  return (
    <div style={{display:'flex',flexDirection:'column',gap:16}}>
      {execMsg&&(
        <div style={{background:BG.panel,border:`1px solid ${BG.border}`,borderRadius:10,padding:'12px 16px',
          borderLeft:`3px solid ${curr.net_profit>prev.net_profit?C.green:C.red}`}}>
          <span style={{fontSize:12,color:C.text1}}>{execMsg}</span>
        </div>
      )}
      <div style={{display:'flex',gap:10,alignItems:'center'}}>
        <span style={{fontSize:11,color:C.text2}}>{tr('var_comparing')}</span>
        <Chip label={latP||'—'} color={C.accent}/>
        <span style={{fontSize:11,color:C.text2}}>{tr('var_vs')}</span>
        <Chip label={prevP||'—'} color={C.text2}/>
        {yoy&&<Chip label={tr('var_yoy_available')} color={C.green}/>}
      </div>
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14}}>
        <Panel title={tr('var_bridge_title')} sub={`${latP||'—'} vs ${prevP||'—'}`}>
          <VarianceBridge curr={curr} prev={prev} tr={tr} lang={lang}/>
        </Panel>
        <Panel
          title={tr('var_yoy_label')}
          sub={
            yoy
              ? `${tr('var_yoy_revenue')}: ${formatSignedPctForLang(d.intelligence?.trends?.revenue?.yoy_change, 1, lang)}`
              : tr('var_yoy_upload_hint')
          }
        >
          {yoy?(
            <div style={{display:'flex',flexDirection:'column',gap:8}}>
              {[{lbl:tr('var_yoy_revenue'),val:d.intelligence?.trends?.revenue?.yoy_change,c:C.accent},{lbl:tr('var_yoy_np'),val:d.intelligence?.trends?.net_profit?.yoy_change,c:C.green}].map((r,i)=>(
                <div key={i} style={{background:BG.panel,borderRadius:9,padding:'12px 14px',border:`1px solid ${BG.border}`}}>
                  <div style={{fontSize:10,color:C.text2,marginBottom:4}}>{r.lbl}</div>
                  <div style={{fontFamily:'var(--font-display)',fontSize:22,fontWeight:800,color:clr(r.val),direction:'ltr'}}>
                    {r.val != null ? formatSignedPctForLang(r.val, 1, lang) : '—'}
                  </div>
                </div>
              ))}
            </div>
          ):(
            <div style={{color:C.text2,fontSize:12,textAlign:'center',padding:'24px 0'}}>
              <div style={{fontSize:28,marginBottom:8,opacity:.3}}>📅</div>
              {tr('var_requires_13m')||tr('var_yoy_upload_hint')}
            </div>
          )}
        </Panel>
      </div>
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14}}>
        <Panel title={tr('var_mom_revenue')} sub={tr('var_mom_growth')}>
          <BarChart lang={lang} data={momSer.revenue} labels={kPerds} color={C.accent} h={120} name={tr('var_mom_revenue')}/>
        </Panel>
        <Panel title={tr('var_mom_np')} sub={tr('var_mom_growth')}>
          <BarChart lang={lang} data={momSer.net_profit} labels={kPerds} color={C.green} h={120} name={tr('var_mom_np')}/>
        </Panel>
      </div>
      <Panel title={tr('var_rolling_summary')}>
        <div style={{overflowX:'auto'}}>
          <table style={{width:'100%',borderCollapse:'collapse',fontSize:11,direction:'ltr'}}>
            <thead>
              <tr style={{background:BG.panel}}>
                {[tr('modal_period_label'),tr('kpi_total_revenue'),tr('exp_cogs_label'),tr('gross_profit'),'GM%',tr('opex'),tr('kpi_net_profit'),'NM%'].map((h,i)=>(
                  <th key={i} style={{padding:'8px 10px',textAlign:i===0?'left':'right',color:C.text2,fontSize:10,fontWeight:600,textTransform:'uppercase',letterSpacing:'.06em',borderBottom:`1px solid ${BG.border}`}}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tPerds.slice(-8).map((p,i)=>{
                const idx=tPerds.indexOf(p)
                const rev=trends.revenue_series?.[idx],cogs=trends.cogs_series?.[idx]
                const exp=trends.expenses_series?.[idx],np=trends.net_profit_series?.[idx]
                const gm=trends.gross_margin_series?.[idx],gp=rev&&cogs?rev-cogs:null,nm=rev?np/rev*100:null
                const last=i===tPerds.slice(-8).length-1
                return (
                  <tr key={p} style={{borderBottom:`1px solid ${BG.border2}`,background:last?`${C.accent}08`:'transparent'}}>
                    <td style={{padding:'7px 10px',color:last?C.accent:C.text2,fontFamily:'monospace',fontWeight:last?700:400}}>{p}</td>
                    <td style={{padding:'7px 10px',textAlign:'right',color:C.text1,fontFamily:'monospace'}}>{formatCompactForLang(rev, lang)}</td>
                    <td style={{padding:'7px 10px',textAlign:'right',color:C.amber,fontFamily:'monospace'}}>{formatCompactForLang(cogs, lang)}</td>
                    <td style={{padding:'7px 10px',textAlign:'right',color:C.blue,fontFamily:'monospace',fontWeight:600}}>{formatCompactForLang(gp, lang)}</td>
                    <td style={{padding:'7px 10px',textAlign:'right',color:clr(gm)}}>{formatPctForLang(gm, 1, lang)}</td>
                    <td style={{padding:'7px 10px',textAlign:'right',color:C.red,fontFamily:'monospace'}}>{formatCompactForLang(exp, lang)}</td>
                    <td style={{padding:'7px 10px',textAlign:'right',color:clr(np),fontFamily:'monospace',fontWeight:600}}>{formatCompactForLang(np, lang)}</td>
                    <td style={{padding:'7px 10px',textAlign:'right',color:clr(nm)}}>{formatPctForLang(nm, 1, lang)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  TAB 4: Profitability — executive language
// ══════════════════════════════════════════════════════════════════════════════
function ProfitabilityTab({ data, tr, ctxLabel, lang }) {
  const d = data?.data || {}
  const trends=d.intelligence?.trends||{}, periods=trends.periods||[]
  const adv=d.advanced_metrics?.profitability||{}
  const latest=data?.analysis?.latest?.profitability||{}
  const eff=data?.analysis?.latest?.efficiency||{}
  const liq=d.intelligence?.ratios?.liquidity||{}
  const series=d.kpi_block?.series||{}, kPerds=d.kpi_block?.periods||[]
  const gmSeries=trends.gross_margin_series||[]
  const revSeries=trends.revenue_series||[], npSeries=trends.net_profit_series||[]
  const nmSeries=revSeries.map((r,i)=>r&&npSeries[i]!=null?npSeries[i]/r*100:null)
  const dol=adv.operating_leverage_dol

  // Executive language for DOL
  const dolExecMsg = dol!=null
    ? (dol>3 ? tr('exec_dol_high') : dol>1.5 ? tr('exec_dol_medium') : tr('exec_dol_low'))
    : null
  const dolDetail = dol!=null ? `${tr('exec_dol_explain')} ${formatPctForLang(dol,1,lang)}` : null

  // Executive language for efficiency
  const dsoMsg=eff.dso_days!=null?(eff.dso_days>45?tr('exec_dso_high'):tr('exec_dso_normal')):null
  const cccMsg=eff.ccc_days!=null?(eff.ccc_days>60?tr('exec_ccc_high'):tr('exec_ccc_normal')):null
  const liqMsg=liq.current_ratio!=null?(liq.current_ratio>=1.5?tr('exec_liquidity_strong'):tr('exec_liquidity_weak')):null

  return (
    <div style={{display:'flex',flexDirection:'column',gap:16}}>
      <div style={{display:'grid',gridTemplateColumns:'repeat(5,1fr)',gap:12}}>
        {[
          {lbl:kpiLabel(tr('prof_gross_margin'),ctxLabel(), tr),val:formatPctForLang(latest.gross_margin_pct,1,lang),avg:formatPctForLang(adv.avg_gross_margin_pct,1,lang),c:C.green,icon:'📈'},
          {lbl:kpiLabel(tr('prof_op_margin'),ctxLabel(), tr),val:formatPctForLang(latest.operating_margin_pct,1,lang),avg:'—',c:C.violet,icon:'⚙️'},
          {lbl:kpiLabel(tr('prof_net_margin'),ctxLabel(), tr),val:formatPctForLang(latest.net_margin_pct,1,lang),avg:formatPctForLang(adv.avg_net_margin_pct,1,lang),c:C.accent,icon:'💰'},
          {lbl:tr('prof_ebitda_margin'),val:formatPctForLang(adv.ebitda_margin_pct,1,lang),avg:'—',c:C.amber,icon:'🏦'},
          {lbl:tr('prof_incr_margin'),val:formatPctForLang(adv.incremental_margin_pct,1,lang),avg:'—',c:C.blue,icon:'📊'},
        ].map((x,i)=>(
          <div key={i} style={{background:BG.panel,borderWidth:'2px 1px 1px 1px',borderStyle:'solid',borderColor:`${x.c} ${BG.border} ${BG.border} ${BG.border}`,borderRadius:12,padding:'14px 16px'}}>
            <div style={{display:'flex',alignItems:'center',gap:5,marginBottom:6}}>
              <span style={{fontSize:12}}>{x.icon}</span>
              <span style={{fontSize:10,color:C.text2,fontWeight:600,textTransform:'uppercase',letterSpacing:'.06em'}}>{x.lbl}</span>
            </div>
            <div style={{fontFamily:'var(--font-display)',fontSize:26,fontWeight:800,color:x.c,lineHeight:1,direction:'ltr'}}>{x.val}</div>
            {x.avg!=='—'&&<div style={{fontSize:10,color:C.text2,marginTop:4}}>{tr('prof_avg')} {x.avg}</div>}
          </div>
        ))}
      </div>
      <Panel title={tr('prof_margin_trends')} sub={`${periods.length} ${tr('gen_periods')}`}
        titleRight={<div style={{display:'flex',gap:12}}><Legend color={C.green} label={tr('prof_gross_label')}/><Legend color={C.amber} label={tr('prof_net_label')}/></div>}>
        <AreaChart lang={lang} d1={gmSeries} d2={nmSeries} labels={periods} c1={C.green} c2={C.amber} h={180} n1={tr('chart_gross_margin')} n2={tr('chart_net_margin')}/>
      </Panel>
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14}}>
        <Panel title={tr('prof_leverage_title')} sub={tr('prof_leverage_sub')}>
          <div style={{marginBottom:12}}>
            <div style={{fontFamily:'var(--font-display)',fontSize:36,fontWeight:800,color:dol!=null&&dol>3?C.amber:C.green,lineHeight:1,direction:'ltr'}}>
              {dol!=null?formatMultipleForLang(dol,2,lang):'—'}
            </div>
            {dolExecMsg&&<div style={{fontSize:12,fontWeight:600,color:dol>3?C.amber:C.green,marginTop:8,lineHeight:1.4}}>{dolExecMsg}</div>}
            {dolDetail&&<div style={{fontSize:11,color:C.text2,marginTop:4,lineHeight:1.5}}>{dolDetail}</div>}
          </div>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8}}>
            {[
              {lbl:tr('prof_cm'),val:formatCompactForLang(adv.contribution_margin,lang),c:C.accent},
              {lbl:tr('prof_cm_pct'),val:formatPctForLang(adv.contribution_margin_pct,1,lang),c:C.accent},
              {lbl:tr('prof_ebitda'),val:formatCompactForLang(adv.ebitda,lang),c:C.amber},
              {lbl:tr('prof_da_estimate'),val:formatCompactForLang(adv.ebitda_da_estimate,lang),c:C.text2},
            ].map((r,i)=>(
              <div key={i} style={{background:BG.card,borderRadius:7,padding:'8px 10px',border:`1px solid ${BG.border}`}}>
                <div style={{fontSize:10,color:C.text2,marginBottom:3}}>{r.lbl}</div>
                <div style={{fontSize:13,fontWeight:700,fontFamily:'monospace',color:r.c,direction:'ltr'}}>{r.val}</div>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title={tr('prof_wc_title')} sub={liqMsg||''}>
          {liqMsg&&<div style={{fontSize:11,color:liq.current_ratio>=1.5?C.green:C.amber,marginBottom:10,fontWeight:500}}>{liqMsg}</div>}
          {dsoMsg&&<div style={{fontSize:11,color:eff.dso_days>45?C.amber:C.green,marginBottom:6}}>{dsoMsg}</div>}
          {cccMsg&&<div style={{fontSize:11,color:eff.ccc_days>60?C.amber:C.green,marginBottom:12}}>{cccMsg}</div>}
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8}}>
            {[
              {lbl:tr('prof_current_ratio'),val:liq.current_ratio!=null?formatMultipleForLang(liq.current_ratio,2,lang):'—',c:liq.current_ratio>=1?C.green:C.red},
              {lbl:tr('prof_quick_ratio'),val:liq.quick_ratio!=null?formatMultipleForLang(liq.quick_ratio,2,lang):'—',c:(liq.quick_ratio||0)>=0.8?C.green:C.red},
              {lbl:tr('prof_dso'),val:formatDays(eff.dso_days),c:eff.dso_days!=null&&eff.dso_days>45?C.amber:C.green},
              {lbl:tr('prof_dpo'),val:formatDays(eff.dpo_days),c:C.blue},
              {lbl:tr('prof_dio'),val:formatDays(eff.dio_days),c:C.violet},
              {lbl:tr('prof_ccc'),val:formatDays(eff.ccc_days),c:eff.ccc_days!=null&&eff.ccc_days<30?C.green:C.amber},
              {lbl:tr('prof_inv_turnover'),val:eff.inventory_turnover!=null?formatMultipleForLang(eff.inventory_turnover,2,lang):'—',c:C.accent},
              {lbl:tr('prof_wc'),val:formatCompactForLang(liq.working_capital,lang),c:(liq.working_capital||0)>=0?C.green:C.red},
            ].map((r,i)=>(
              <div key={i} style={{background:BG.card,borderRadius:7,padding:'8px 10px',border:`1px solid ${BG.border}`}}>
                <div style={{fontSize:10,color:C.text2,marginBottom:3}}>{r.lbl}</div>
                <div style={{fontSize:13,fontWeight:700,fontFamily:'monospace',color:r.c,direction:'ltr'}}>{r.val}</div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
      <Panel title={tr('prof_revenue_growth')} titleRight={<div style={{display:'flex',gap:12}}><Legend color={C.accent} label={tr('legend_revenue')}/><Legend color={C.green} label={tr('kpi_net_profit')}/></div>}>
        <AreaChart lang={lang} d1={series.revenue} d2={series.net_profit} labels={kPerds} c1={C.accent} c2={C.green} h={160} n1={tr('legend_revenue')} n2={tr('kpi_net_profit')}/>
      </Panel>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  TAB 5: AI Decisions
// ══════════════════════════════════════════════════════════════════════════════
function DecisionsTab({data,tSig,tSub,tr,selectedId,lang}) {
  const d = data?.data || {}
  // DecisionIntelPanel fetches its own decision data independently via /decisions endpoint.
  // The canonical /executive decisions array (d.decisions) powers the risk snapshot.
  // Legacy /analysis decision object shape (insights/warnings/recommendations/forecast) removed.
  return (
    <div style={{display:'flex',flexDirection:'column',gap:14}}>
      <DecisionIntelPanel tr={tr} selectedId={selectedId} data={data} lang={lang}/>
      <Panel title={tr('dec_risk_snapshot')}>
        {[
          {lbl:tr('dec_risk_rating'),val:d.advanced_metrics?.risk?.risk_rating||'—',c:{low:C.green,medium:C.amber,high:C.red,critical:C.red}[d.advanced_metrics?.risk?.risk_rating]||C.text2},
          {lbl:tr('dec_risk_factors'),val:d.advanced_metrics?.risk?.risk_factor_count??'—',c:C.text1},
          {lbl:tr('dec_earn_consistency'),val:d.advanced_metrics?.risk?.earnings_consistency?.consistency_score!=null?`${formatFullForLang(d.advanced_metrics?.risk.earnings_consistency.consistency_score, lang)}/100`:'—',c:C.accent},
          {lbl:tr('dec_rev_stability'),val:d.advanced_metrics?.risk?.revenue_stability?.stability_score!=null?`${formatFullForLang(d.advanced_metrics?.risk.revenue_stability.stability_score, lang)}/100`:'—',c:C.blue},
        ].map((r,i)=>(
          <div key={i} style={{display:'flex',justifyContent:'space-between',padding:'7px 0',borderBottom:`1px solid ${BG.border2}`}}>
            <span style={{fontSize:11,color:C.text2}}>{r.lbl}</span>
            <span style={{fontSize:12,fontWeight:700,fontFamily:'monospace',color:r.c,direction:'ltr'}}>{r.val}</span>
          </div>
        ))}
      </Panel>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  Phase 15.5 — What-If Panel
// ══════════════════════════════════════════════════════════════════════════════
function WhatIfPanel({data,tr,selectedId}) {
  const { lang } = useLang()
  const d = data?.data || {}
  const { toBodyFields: wiScopeBody, toQueryString: wiToQS, window: win } = usePeriodScope()
  const [basis,    setBasis]    = useState('ytd')
  const [year,     setYear]     = useState('')
  const [revPct,   setRevPct]   = useState(0)
  const [cogsPct,  setCogsPct]  = useState(0)
  const [opexPct,  setOpexPct]  = useState(0)
  const [result,   setResult]   = useState(null)
  const [loading,  setLoading]  = useState(false)
  const [err,      setErr]      = useState(null)

  const al    = d.annual_layer || {}
  const years = (al.full_years||[]).map(fy=>fy.year)

  async function run() {
    if (!selectedId) return
    setLoading(true); setErr(null); setResult(null)
    try {
      const body = { basis, revenue_pct:Number(revPct), cogs_pct:Number(cogsPct), opex_pct:Number(opexPct) }
      if (basis==='full_year'&&year) body.year = year
      const scopeBody = wiScopeBody()
      if (scopeBody === null) { setErr(tr('fc_custom_scope_hint')); return }
      const qs = buildAnalysisQuery(wiToQS, { lang, window: win, consolidate: false })
      if (qs === null) { setErr(tr('fc_custom_scope_hint')); return }
      const r = await fetch(`/api/v1/analysis/${selectedId}/what-if?${qs}`, {
        method:'POST',
        headers:{...getAuthHeaders(),'Content-Type':'application/json'},
        body: JSON.stringify({...body, ...scopeBody}),
      })
      const d = await r.json()
      if (!r.ok) { setErr(d.detail||'Simulation failed'); return }
      setResult(d)
    } catch(e) { setErr(e.message) }
    finally { setLoading(false) }
  }

  const fmtV = (v) => (v == null ? '—' : formatFullForLang(v, lang))
  const diffClr = (v) => (v == null ? C.text2 : v > 0 ? C.green : v < 0 ? C.red : C.text2)
  const diffFmt = (v) => (v == null ? null : formatSignedPctForLang(Number(v), 1, lang))

  const inputStyle = INPUT_DARK
  const labelStyle = {fontSize:10,color:C.text2,fontWeight:600,
    textTransform:'uppercase',letterSpacing:'.05em',marginBottom:4}

  return (
    <div style={{display:'flex',flexDirection:'column',gap:14}}>
      {/* Controls */}
      <div style={{background:BG.panel,border:`1px solid ${BG.border}`,borderRadius:12,padding:'16px 18px'}}>
        <div style={{fontSize:12,fontWeight:700,color:C.text1,marginBottom:14}}>
          {tr('wi_title')}
        </div>
        <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(140px,1fr))',gap:12}}>
          {/* Basis */}
          <div>
            <div style={labelStyle}>{tr('wi_basis')}</div>
            <select value={basis} onChange={e=>{setBasis(e.target.value);setResult(null)}}
              style={{...SELECT_DARK}}>
              <option value="ytd">{tr('wi_basis_ytd')}</option>
              <option value="latest_month">{tr('wi_basis_month')}</option>
              <option value="full_year">{tr('wi_basis_fy')}</option>
            </select>
          </div>
          {/* Year selector — only for full_year */}
          {basis==='full_year'&&years.length>0&&(
            <div>
              <div style={labelStyle}>{tr('wi_year')}</div>
              <select value={year} onChange={e=>setYear(e.target.value)} style={{...SELECT_DARK}}>
                <option value="">{tr('wi_latest')}</option>
                {years.map(y=><option key={y} value={y}>{y}</option>)}
              </select>
            </div>
          )}
          {/* Revenue % */}
          <div>
            <div style={labelStyle}>{tr('wi_revenue_pct')}</div>
            <input type="number" step="0.5" value={revPct}
              onChange={e=>setRevPct(e.target.value)} style={INPUT_DARK}/>
          </div>
          {/* COGS % */}
          <div>
            <div style={labelStyle}>{tr('wi_cogs_pct')}</div>
            <input type="number" step="0.5" value={cogsPct}
              onChange={e=>setCogsPct(e.target.value)} style={INPUT_DARK}/>
          </div>
          {/* OpEx % */}
          <div>
            <div style={labelStyle}>{tr('wi_opex_pct')}</div>
            <input type="number" step="0.5" value={opexPct}
              onChange={e=>setOpexPct(e.target.value)} style={INPUT_DARK}/>
          </div>
          {/* Run button */}
          <div style={{display:'flex',alignItems:'flex-end'}}>
            <button onClick={run} disabled={loading||!selectedId}
              style={{width:'100%',padding:'8px 0',borderRadius:8,border:'none',
                background:loading?BG.border:C.accent,color:loading?C.text2:'#000',
                fontSize:12,fontWeight:700,cursor:loading?'default':'pointer',
                fontFamily:'var(--font-display)',transition:'background .15s'}}>
              {loading ? '...' : tr('wi_run')}
            </button>
          </div>
        </div>
        {err&&<div style={{marginTop:10,fontSize:11,color:C.red}}>⚠ {err}</div>}
      </div>

      {/* Warnings */}
      {result?.warnings?.length>0&&(
        <div style={{background:`${C.amber}0e`,border:`1px solid ${C.amber}40`,
          borderRadius:8,padding:'10px 14px'}}>
          {result.warnings.map((w,i)=>(
            <div key={i} style={{fontSize:11,color:C.amber,marginBottom:i<result.warnings.length-1?4:0}}>
              ⚠ {w}
            </div>
          ))}
        </div>
      )}

      {/* Results */}
      {result&&(
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:12}}>
          {/* Baseline */}
          <div style={{background:BG.panel,border:`1px solid ${BG.border}`,borderRadius:12,padding:'14px 16px'}}>
            <div style={{fontSize:10,fontWeight:700,color:C.text2,textTransform:'uppercase',
              letterSpacing:'.06em',marginBottom:10}}>
              {tr('wi_baseline')} · {result.period_label}
            </div>
            {[
              {label:tr('wi_revenue'),   val:fmtV(result.baseline?.revenue),   color:C.accent},
              {label:tr('wi_net_profit'),val:fmtV(result.baseline?.net_profit),color:C.green},
              {label:tr('wi_net_margin'),val:formatPctForLang(result.baseline?.net_margin_pct, 1, lang),color:C.violet},
            ].map(({label,val,color})=>(
              <div key={label} style={{display:'flex',justifyContent:'space-between',
                alignItems:'center',marginBottom:6}}>
                <span style={{fontSize:11,color:C.text2}}>{label}</span>
                <span style={{fontFamily:'var(--font-mono)',fontSize:12,fontWeight:700,
                  color,direction:'ltr'}}>{val}</span>
              </div>
            ))}
          </div>
          {/* Scenario */}
          <div style={{background:BG.panel,border:`1px solid ${C.accent}40`,
            borderLeft:`3px solid ${C.accent}`,borderRadius:12,padding:'14px 16px'}}>
            <div style={{fontSize:10,fontWeight:700,color:C.accent,textTransform:'uppercase',
              letterSpacing:'.06em',marginBottom:10}}>
              {tr('wi_scenario')}
            </div>
            {[
              {label:tr('wi_revenue'),   val:fmtV(result.scenario?.revenue),   color:C.accent},
              {label:tr('wi_net_profit'),val:fmtV(result.scenario?.net_profit),color:C.green},
              {label:tr('wi_net_margin'),val:formatPctForLang(result.scenario?.net_margin_pct, 1, lang),color:C.violet},
            ].map(({label,val,color})=>(
              <div key={label} style={{display:'flex',justifyContent:'space-between',
                alignItems:'center',marginBottom:6}}>
                <span style={{fontSize:11,color:C.text2}}>{label}</span>
                <span style={{fontFamily:'var(--font-mono)',fontSize:12,fontWeight:700,
                  color,direction:'ltr'}}>{val}</span>
              </div>
            ))}
          </div>
          {/* Impact */}
          <div style={{background:BG.panel,border:`1px solid ${BG.border}`,borderRadius:12,padding:'14px 16px'}}>
            <div style={{fontSize:10,fontWeight:700,color:C.text2,textTransform:'uppercase',
              letterSpacing:'.06em',marginBottom:10}}>
              {tr('wi_impact')}
            </div>
            {[
              {label:tr('wi_revenue'),   val:diffFmt(result.impact?.revenue_pct_change),   num:result.impact?.revenue_pct_change},
              {label:tr('wi_net_profit'),val:diffFmt(result.impact?.net_profit_pct_change), num:result.impact?.net_profit_pct_change},
              {label:tr('wi_margin_pp'), val:result.impact?.net_margin_pp!=null
                ? formatPpForLang(result.impact.net_margin_pp, 2, lang)
                : null, num:result.impact?.net_margin_pp},
            ].map(({label,val,num})=>(
              <div key={label} style={{display:'flex',justifyContent:'space-between',
                alignItems:'center',marginBottom:6}}>
                <span style={{fontSize:11,color:C.text2}}>{label}</span>
                <span style={{fontFamily:'var(--font-mono)',fontSize:12,fontWeight:700,
                  color:val!=null?diffClr(Number(num)):C.text2,direction:'ltr'}}>{val||'—'}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  Phase 16 — Decision Intelligence Panel
// ══════════════════════════════════════════════════════════════════════════════
function DecisionIntelPanel({tr, selectedId, data, lang}) {
  const { toQueryString: decScopeQS, toBodyFields: decScopeBody, window: win } = usePeriodScope()
  const [basis,   setBasis]   = useState('ytd')
  const [result,  setResult]  = useState(null)
  const [loading, setLoading] = useState(false)
  const [err,     setErr]     = useState(null)

  const scLabels = {
    combined:         tr('dec_sc_combined'),
    increase_revenue: tr('dec_sc_increase_revenue'),
    reduce_cogs:      tr('dec_sc_reduce_cogs'),
    reduce_opex:      tr('dec_sc_reduce_opex'),
  }
  const scDesc = {
    combined:         tr('dec_sc_combined_desc'),
    increase_revenue: tr('dec_sc_increase_revenue_desc'),
    reduce_cogs:      tr('dec_sc_reduce_cogs_desc'),
    reduce_opex:      tr('dec_sc_reduce_opex_desc'),
  }

  async function run() {
    if (!selectedId) return
    setLoading(true); setErr(null)
    try {
      const decScope = decScopeBody()
      if (decScope === null) { setErr(tr('fc_custom_scope_hint')); return }
      const qs = buildAnalysisQuery(decScopeQS, { lang, window: win, consolidate: false })
      if (qs === null) { setErr(tr('fc_custom_scope_hint')); return }
      const r = await fetch(`/api/v1/analysis/${selectedId}/decisions?${qs}`, {
        method:'POST',
        headers:{...getAuthHeaders(),'Content-Type':'application/json'},
        body: JSON.stringify({basis, ...decScope}),
      })
      const d = await r.json()
      if (!r.ok) { setErr(d.detail||'Failed'); return }
      setResult(d)
    } catch(e) { setErr(e.message) }
    finally { setLoading(false) }
  }

  const pClr = v => v>0?C.green:v<0?C.red:C.text2

  const best    = result?.best_scenario
  const ranking = result?.ranking || []

  return (
    <div style={{display:'flex',flexDirection:'column',gap:12}}>
      {/* Controls */}
      <div style={{display:'flex',gap:10,alignItems:'flex-end',flexWrap:'wrap'}}>
        <div>
          <div style={{fontSize:10,color:C.text2,fontWeight:600,textTransform:'uppercase',
            letterSpacing:'.05em',marginBottom:4}}>{tr('dec_basis_label')}</div>
          <select value={basis} onChange={e=>{setBasis(e.target.value);setResult(null)}}
            style={{...SELECT_DARK,width:'auto'}}>
            <option value="ytd">{tr('wi_basis_ytd')}</option>
            <option value="latest_month">{tr('wi_basis_month')}</option>
            <option value="full_year">{tr('wi_basis_fy')}</option>
          </select>
        </div>
        <button onClick={run} disabled={loading||!selectedId}
          style={{padding:'8px 18px',borderRadius:8,border:'none',
            background:loading?BG.border:C.violet,color:loading?C.text2:'#fff',
            fontSize:12,fontWeight:700,cursor:loading?'default':'pointer',
            fontFamily:'var(--font-display)',whiteSpace:'nowrap'}}>
          {loading?tr('dec_loading'):tr('dec_run')}
        </button>
        {err&&<span style={{fontSize:11,color:C.red}}>⚠ {err}</span>}
      </div>

      {!result&&!loading&&(
        <div style={{color:C.text2,fontSize:12,padding:'20px 0',textAlign:'center'}}>
          {tr('dec_no_data')}
        </div>
      )}

      {result&&(<>
        {/* Warnings */}
        {result.warnings?.length>0&&(
          <div style={{background:`${C.amber}0e`,border:`1px solid ${C.amber}40`,
            borderRadius:8,padding:'8px 14px'}}>
            {result.warnings.map((w,i)=>(
              <div key={i} style={{fontSize:11,color:C.amber}}>⚠ {w}</div>
            ))}
          </div>
        )}

        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12,alignItems:'start'}}>
          {/* Best Action — Phase 19 Pro */}
          {best&&(
            <div style={{background:BG.panel,border:`2px solid ${C.violet}`,
              borderRadius:12,padding:'16px 18px',display:'flex',flexDirection:'column',gap:12}}>
              {/* Header: title + priority */}
              <div style={{display:'flex',alignItems:'center',justifyContent:'space-between'}}>
                <div style={{fontSize:10,fontWeight:700,color:C.violet,textTransform:'uppercase',
                  letterSpacing:'.06em'}}>{tr('dec_best_action')}</div>
                {best.priority&&(()=>{
                  const priClr={high:C.green,medium:C.amber,low:C.text2}[best.priority]||C.text2
                  const priLbl={high:tr('dec_pri_high'),medium:tr('dec_pri_medium'),low:tr('dec_pri_low')}[best.priority]||best.priority
                  return <span style={{fontSize:9,fontWeight:800,padding:'2px 10px',borderRadius:20,
                    background:`${priClr}20`,color:priClr,textTransform:'uppercase',letterSpacing:'.06em'}}>{priLbl}</span>
                })()}
              </div>
              {/* Name + desc */}
              <div>
                <div style={{fontSize:14,fontWeight:700,color:C.text1,marginBottom:3}}>{scLabels[best.id]||best.id}</div>
                <div style={{fontSize:11,color:C.text2,lineHeight:1.4}}>{scDesc[best.id]||''}</div>
              </div>
              {/* Score bar */}
              <div style={{display:'flex',alignItems:'center',gap:8}}>
                <div style={{flex:1,height:6,background:BG.border,borderRadius:3,overflow:'hidden'}}>
                  <div style={{height:'100%',width:`${best.score}%`,background:`linear-gradient(90deg,${C.violet},${C.accent})`,borderRadius:3}}/>
                </div>
                <span style={{fontSize:10,fontWeight:700,color:C.violet,fontFamily:'var(--font-mono)',minWidth:32,direction:'ltr'}}>{best.score}</span>
              </div>
              {/* Confidence */}
              {best.confidence!=null&&(
                <div>
                  <div style={{display:'flex',justifyContent:'space-between',marginBottom:4}}>
                    <span style={{fontSize:10,color:C.text2,textTransform:'uppercase',letterSpacing:'.05em'}}>{tr('dec_confidence')}</span>
                    <span style={{fontSize:9,fontFamily:'var(--font-mono)',color:C.text2,direction:'ltr'}}>{formatPctForLang(best.confidence, 0, lang)}</span>
                  </div>
                  <div style={{height:4,background:BG.border,borderRadius:2,overflow:'hidden'}}>
                    <div style={{height:'100%',width:`${best.confidence}%`,
                      background:best.confidence>=70?C.green:best.confidence>=40?C.amber:C.red,borderRadius:2}}/>
                  </div>
                </div>
              )}
              {/* Impact */}
              <div style={{display:'flex',gap:16}}>
                <div>
                  <div style={{fontSize:10,color:C.text2,textTransform:'uppercase',letterSpacing:'.05em'}}>{tr('dec_np_delta')}</div>
                  <div style={{fontFamily:'var(--font-mono)',fontSize:13,fontWeight:700,color:pClr(best.impact?.net_profit_delta||0),direction:'ltr'}}>
                    {(() => { const d = best.impact?.net_profit_delta; return d != null ? `${d > 0 ? '+' : ''}${formatCompactForLang(d, lang)}` : '—' })()}
                  </div>
                </div>
                <div>
                  <div style={{fontSize:10,color:C.text2,textTransform:'uppercase',letterSpacing:'.05em'}}>{tr('dec_margin_pp')}</div>
                  <div style={{fontFamily:'var(--font-mono)',fontSize:13,fontWeight:700,color:pClr(best.impact?.net_margin_pp||0),direction:'ltr'}}>
                    {best.impact?.net_margin_pp!=null?formatPpForLang(best.impact.net_margin_pp, 2, lang):'—'}
                  </div>
                </div>
              </div>
              {/* Justification */}
              {best.justification&&(
                <div style={{borderTop:`1px solid ${BG.border}`,paddingTop:10}}>
                  <div style={{fontSize:9,fontWeight:700,color:C.text2,textTransform:'uppercase',letterSpacing:'.06em',marginBottom:6}}>{tr('dec_justification')}</div>
                  <p style={{fontSize:11,color:C.text2,lineHeight:1.55,margin:0}}>{best.justification}</p>
                </div>
              )}
              {/* Sensitivity */}
              {best.sensitivity&&(
                <div style={{background:`${C.blue}0d`,border:`1px solid ${C.blue}30`,borderRadius:8,padding:'10px 12px'}}>
                  <div style={{fontSize:9,fontWeight:700,color:C.blue,textTransform:'uppercase',letterSpacing:'.06em',marginBottom:8}}>{tr('dec_sensitivity')}</div>
                  <div style={{display:'flex',flexDirection:'column',gap:5}}>
                    {[
                      {key:'revenue',label:tr('dec_lever_revenue'),pct:best.sensitivity.revenue_contribution||0},
                      {key:'cogs',   label:tr('dec_lever_cogs'),   pct:best.sensitivity.cogs_contribution||0},
                      {key:'opex',   label:tr('dec_lever_opex'),   pct:best.sensitivity.opex_contribution||0},
                    ].filter(x=>x.pct>0).map(({key,label,pct})=>(
                      <div key={key} style={{display:'flex',alignItems:'center',gap:8}}>
                        <span style={{fontSize:10,color:C.text2,minWidth:110,flexShrink:0}}>{label}</span>
                        <div style={{flex:1,height:4,background:BG.border,borderRadius:2,overflow:'hidden'}}>
                          <div style={{height:'100%',width:`${pct}%`,
                            background:key===best.sensitivity.primary_lever?C.blue:`${C.blue}40`,borderRadius:2}}/>
                        </div>
                        <span style={{fontSize:9,fontFamily:'var(--font-mono)',color:C.text2,minWidth:28,textAlign:'end',direction:'ltr'}}>{formatPctForLang(pct, 0, lang)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Ranking */}
          <div style={{background:BG.panel,border:`1px solid ${BG.border}`,
            borderRadius:12,overflow:'hidden'}}>
            <div style={{padding:'12px 16px',borderBottom:`1px solid ${BG.border}`,
              fontSize:10,fontWeight:700,color:C.text2,textTransform:'uppercase',
              letterSpacing:'.06em'}}>{tr('dec_ranking')}</div>
            {ranking.map((sc,i)=>(
              <div key={sc.id} style={{display:'flex',alignItems:'center',gap:10,
                padding:'10px 16px',borderBottom:i<ranking.length-1?`1px solid ${BG.border}`:'none',
                background:i===0?`${C.violet}09`:'transparent'}}>
                <span style={{fontFamily:'var(--font-mono)',fontSize:11,color:C.text2,
                  minWidth:16,direction:'ltr'}}>{sc.rank}</span>
                <div style={{flex:1,minWidth:0}}>
                  <div style={{fontSize:11,fontWeight:600,color:i===0?C.violet:C.text2,
                    whiteSpace:'nowrap',overflow:'hidden',textOverflow:'clip'}}>
                    {scLabels[sc.id]||sc.id}
                  </div>
                  <div style={{fontSize:10,color:C.text2,marginTop:1}}>
                    {scDesc[sc.id]||''}
                  </div>
                </div>
                <div style={{display:'flex',gap:8,flexShrink:0,alignItems:'center'}}>
                  {sc.priority&&(()=>{
                    const pc={high:C.green,medium:C.amber,low:C.text2}[sc.priority]||C.text2
                    return <span style={{fontSize:8,fontWeight:700,padding:'1px 7px',borderRadius:10,
                      background:`${pc}18`,color:pc,textTransform:'uppercase'}}>{
                      {high:tr('dec_pri_high'),medium:tr('dec_pri_medium'),low:tr('dec_pri_low')}[sc.priority]||sc.priority
                    }</span>
                  })()}
                  <span style={{fontFamily:'var(--font-mono)',fontSize:10,
                    color:pClr(sc.np_pct_change||0),direction:'ltr',minWidth:44,textAlign:'end'}}>
                    {sc.np_pct_change!=null?formatSignedPctForLang(sc.np_pct_change, 1, lang):'—'}
                  </span>
                  <span style={{fontFamily:'var(--font-mono)',fontSize:10,
                    color:pClr(sc.margin_pp||0),direction:'ltr',minWidth:44,textAlign:'end'}}>
                    {sc.margin_pp!=null?formatPpForLang(sc.margin_pp, 2, lang):'—'}
                  </span>
                  <span style={{fontFamily:'var(--font-mono)',fontSize:10,
                    color:C.text2,minWidth:28,textAlign:'end',direction:'ltr'}}>
                    {sc.score}
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* Scenario Packs */}
          {result?.scenario_pack_results&&(
            <div style={{background:BG.panel,border:`1px solid ${BG.border}`,borderRadius:12,overflow:'hidden'}}>
              <div style={{padding:'12px 16px',borderBottom:`1px solid ${BG.border}`,
                fontSize:10,fontWeight:700,color:C.text2,textTransform:'uppercase',
                letterSpacing:'.06em'}}>{tr('dec_packs')}</div>
              <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)'}}>
                {['conservative','base','aggressive'].map((packId,i)=>{
                  const pk = result.scenario_pack_results[packId]
                  if (!pk) return null
                  const packClr = {conservative:C.text2,base:C.accent,aggressive:C.amber}[packId]||C.text2
                  const packLbl = {
                    conservative:tr('dec_pack_conservative'),
                    base:tr('dec_pack_base'),
                    aggressive:tr('dec_pack_aggressive'),
                  }[packId]||packId
                  return (
                    <div key={packId} style={{padding:'12px 14px',
                      borderRight:i<2?`1px solid ${BG.border}`:'none',
                      borderTop:`3px solid ${packClr}`}}>
                      <div style={{fontSize:10,fontWeight:700,color:packClr,
                        textTransform:'uppercase',letterSpacing:'.05em',marginBottom:8}}>
                        {packLbl}
                      </div>
                      <div style={{display:'flex',flexDirection:'column',gap:5}}>
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                          <span style={{fontSize:10,color:C.text2}}>{tr('dec_pack_np_pct')}</span>
                          <span style={{fontFamily:'var(--font-mono)',fontSize:11,fontWeight:700,
                            color:pClr(pk.net_profit_pct_change||0),direction:'ltr'}}>
                            {pk.net_profit_pct_change!=null?formatSignedPctForLang(pk.net_profit_pct_change, 1, lang):'—'}
                          </span>
                        </div>
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                          <span style={{fontSize:10,color:C.text2}}>{tr('dec_pack_margin_pp')}</span>
                          <span style={{fontFamily:'var(--font-mono)',fontSize:11,fontWeight:700,
                            color:pClr(pk.net_margin_pp||0),direction:'ltr'}}>
                            {pk.net_margin_pp!=null?formatPpForLang(pk.net_margin_pp, 2, lang):'—'}
                          </span>
                        </div>
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                          <span style={{fontSize:10,color:C.text2}}>{tr('dec_pack_np_delta')}</span>
                          <span style={{fontFamily:'var(--font-mono)',fontSize:10,
                            color:pClr(pk.net_profit_delta||0),direction:'ltr'}}>
                            {pk.net_profit_delta!=null?`${pk.net_profit_delta>0?'+':''}${formatCompactForLang(pk.net_profit_delta, lang)}`:'—'}
                          </span>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      </>)}
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  Phase 17 — Executive Narrative Panel
// ══════════════════════════════════════════════════════════════════════════════
function NarrativePanel({tr, selectedId, lang}) {
  const { toQueryString: narScopeQS, window: win } = usePeriodScope()
  const [basis,     setBasis]     = useState('ytd')
  const [narLang,   setNarLang]   = useState(lang==='ar'?'ar':'en')
  const [result,    setResult]    = useState(null)
  const [loading,   setLoading]   = useState(false)
  const [err,       setErr]       = useState(null)
  const [exporting, setExporting] = useState(null)  // 'xlsx' | 'json' | null

  async function exportXlsx() {
    if (!selectedId) return
    setExporting('xlsx')
    try {
      const base = buildAnalysisQuery(narScopeQS, { lang: narLang, window: win, consolidate: false })
      if (base === null) { setErr(tr('err_scope_custom_incomplete')); return }
      const r = await fetch(
        `/api/v1/analysis/${selectedId}/export.xlsx?${base}&basis=${encodeURIComponent(basis)}`,
        { headers: getAuthHeaders() }
      )
      if (!r.ok) { setErr('Export failed'); return }
      const blob = await r.blob()
      const url  = URL.createObjectURL(blob)
      const a    = document.createElement('a')
      a.href = url
      a.download = r.headers.get('Content-Disposition')?.match(/filename="([^"]+)"/)?.[1] || 'VCFO_Report.xlsx'
      a.click()
      URL.revokeObjectURL(url)
    } catch(e) { setErr(e.message) }
    finally { setExporting(null) }
  }

  async function exportJson() {
    if (!selectedId) return
    setExporting('json')
    try {
      const base = buildAnalysisQuery(narScopeQS, { lang: narLang, window: win, consolidate: false })
      if (base === null) { setErr(tr('err_scope_custom_incomplete')); return }
      const r = await fetch(
        `/api/v1/analysis/${selectedId}/report-bundle?${base}&basis=${encodeURIComponent(basis)}`,
        { headers: getAuthHeaders() }
      )
      const d = await r.json()
      if (!r.ok) { setErr(d.detail||'Export failed'); return }
      const blob = new Blob([JSON.stringify(d, null, 2)], {type:'application/json'})
      const url  = URL.createObjectURL(blob)
      const a    = document.createElement('a')
      a.href = url
      a.download = `VCFO_Report_${basis}.json`
      a.click()
      URL.revokeObjectURL(url)
    } catch(e) { setErr(e.message) }
    finally { setExporting(null) }
  }

  const RTL = narLang === 'ar'

  const statusCfg = {
    excellent: { color: C.green,  bg: `${C.green}18`,  label: tr('nar_status_excellent') },
    good:      { color: C.accent, bg: `${C.accent}18`, label: tr('nar_status_good') },
    warning:   { color: C.amber,  bg: `${C.amber}18`,  label: tr('nar_status_warning') },
    critical:  { color: C.red,    bg: `${C.red}18`,    label: tr('nar_status_critical') },
    neutral:   { color: C.text2,  bg: `${C.text2}18`,  label: tr('nar_status_neutral') },
  }

  async function run() {
    if (!selectedId) return
    setLoading(true); setErr(null)
    try {
      const base = buildAnalysisQuery(narScopeQS, { lang: narLang, window: win, consolidate: false })
      if (base === null) { setErr(tr('err_scope_custom_incomplete')); setLoading(false); return }
      const r = await fetch(
        `/api/v1/analysis/${selectedId}/narrative?${base}&basis=${encodeURIComponent(basis)}`,
        { headers: getAuthHeaders() }
      )
      const d = await r.json()
      if (!r.ok) { setErr(d.detail||'Failed'); return }
      setResult(d)
    } catch(e) { setErr(e.message) }
    finally { setLoading(false) }
  }

  // Parse KPI metrics from executive_summary using regex patterns
  function parseKpis(summary) {
    if (!summary) return null
    const nums = summary.match(/[\d,.]+(M|K|%)?/g) || []
    return nums.slice(0, 4)
  }

  const SectionHead = ({label, color=C.text2}) => (
    <div style={{fontSize:10,fontWeight:800,color,textTransform:'uppercase',
      letterSpacing:'.08em',marginBottom:12,display:'flex',alignItems:'center',gap:8}}>
      <div style={{width:20,height:2,background:color,borderRadius:2}}/>
      {label}
    </div>
  )

  const selStyle = SELECT_DARK

  return (
    <div style={{display:'flex',flexDirection:'column',gap:16,maxWidth:900}}>

      {/* ── Controls bar ─────────────────────────────────────────────────── */}
      <div style={{display:'flex',gap:10,alignItems:'flex-end',flexWrap:'wrap',
        background:BG.panel,border:`1px solid ${BG.border}`,borderRadius:12,
        padding:'14px 18px'}}>
        <div>
          <div style={{fontSize:10,color:C.text2,fontWeight:700,textTransform:'uppercase',
            letterSpacing:'.05em',marginBottom:5}}>{tr('nar_basis')}</div>
          <select value={basis} onChange={e=>{setBasis(e.target.value);setResult(null)}} style={selStyle}>
            <option value="ytd">{tr('wi_basis_ytd')}</option>
            <option value="latest_month">{tr('wi_basis_month')}</option>
            <option value="full_year">{tr('wi_basis_fy')}</option>
          </select>
        </div>
        <div>
          <div style={{fontSize:10,color:C.text2,fontWeight:700,textTransform:'uppercase',
            letterSpacing:'.05em',marginBottom:5}}>{tr('nar_lang_label')}</div>
          <select value={narLang} onChange={e=>setNarLang(e.target.value)} style={selStyle}>
            <option value="en">{tr('nar_lang_en')}</option>
            <option value="ar">{tr('nar_lang_ar')}</option>
          </select>
        </div>
        <div style={{marginLeft:'auto',display:'flex',alignItems:'center',gap:10}}>
          {err&&<span style={{fontSize:11,color:C.red}}>⚠ {err}</span>}
          <button onClick={run} disabled={loading||!selectedId}
            style={{padding:'9px 22px',borderRadius:9,border:'none',
              background:loading?BG.border:C.blue,color:loading?C.text2:'#fff',
              fontSize:13,fontWeight:700,cursor:loading?'not-allowed':'pointer',
              fontFamily:'var(--font-display)',display:'flex',alignItems:'center',gap:8,
              transition:'background .15s'}}>
            {loading&&<div style={{width:12,height:12,border:'2px solid rgba(255,255,255,.3)',
              borderTopColor:'#fff',borderRadius:'50%',animation:'spin .7s linear infinite'}}/>}
            {result?tr('nar_run_update'):tr('nar_run')}
          </button>
          {/* Export buttons — only show after first result */}
          {result&&(<>
            <button onClick={exportXlsx} disabled={exporting==='xlsx'}
              style={{padding:'9px 16px',borderRadius:9,border:`1px solid ${C.green}50`,
                background:exporting==='xlsx'?BG.border:`${C.green}15`,
                color:exporting==='xlsx'?C.text3:C.green,
                fontSize:12,fontWeight:700,cursor:exporting==='xlsx'?'not-allowed':'pointer',
                fontFamily:'var(--font-display)',display:'flex',alignItems:'center',gap:6,
                transition:'background .15s',whiteSpace:'nowrap'}}>
              {exporting==='xlsx'
                ? <><div style={{width:10,height:10,border:'2px solid rgba(16,217,138,.3)',borderTopColor:C.green,borderRadius:'50%',animation:'spin .7s linear infinite'}}/>{tr('exp_loading')}</>
                : <>📊 {tr('exp_excel')}</>}
            </button>
            <button onClick={exportJson} disabled={exporting==='json'}
              style={{padding:'9px 16px',borderRadius:9,border:`1px solid ${C.violet}50`,
                background:exporting==='json'?BG.border:`${C.violet}15`,
                color:exporting==='json'?C.text3:C.violet,
                fontSize:12,fontWeight:700,cursor:exporting==='json'?'not-allowed':'pointer',
                fontFamily:'var(--font-display)',display:'flex',alignItems:'center',gap:6,
                transition:'background .15s',whiteSpace:'nowrap'}}>
              {exporting==='json'
                ? <><div style={{width:10,height:10,border:'2px solid rgba(124,92,252,.3)',borderTopColor:C.violet,borderRadius:'50%',animation:'spin .7s linear infinite'}}/>{tr('exp_loading')}</>
                : <>📋 {tr('exp_json')}</>}
            </button>
          </>)}
        </div>
      </div>

      {/* ── Empty state ───────────────────────────────────────────────────── */}
      {!result&&!loading&&(
        <div style={{display:'flex',flexDirection:'column',alignItems:'center',
          justifyContent:'center',padding:'60px 20px',gap:12}}>
          <span style={{fontSize:40,opacity:.15}}>📋</span>
          <span style={{fontSize:13,color:C.text2}}>{tr('nar_no_data')}</span>
        </div>
      )}

      {/* ── Results ───────────────────────────────────────────────────────── */}
      {result&&(
        <div style={{display:'flex',flexDirection:'column',gap:16}}>

          {/* Header row: status badge + period */}
          <div style={{display:'flex',alignItems:'center',gap:12}}>
            {result.status&&(()=>{
              const cfg = statusCfg[result.status] || statusCfg.neutral
              return (
                <div style={{display:'flex',alignItems:'center',gap:10,
                  background:cfg.bg,border:`1px solid ${cfg.color}40`,
                  borderRadius:12,padding:'10px 20px'}}>
                  <div style={{width:10,height:10,borderRadius:'50%',
                    background:cfg.color,boxShadow:`0 0 10px ${cfg.color}`}}/>
                  <span style={{fontSize:16,fontWeight:800,color:cfg.color,
                    fontFamily:'var(--font-display)',letterSpacing:'-.01em'}}>
                    {cfg.label}
                  </span>
                </div>
              )
            })()}
            <span style={{fontSize:12,color:C.text2,fontFamily:'var(--font-mono)'}}>
              {result.basis_period}
            </span>
          </div>

          {/* Executive Summary — structured KPI rows */}
          <div style={{background:BG.panel,border:`1px solid ${BG.border}`,borderRadius:14,
            padding:'20px 24px'}}>
            <SectionHead label={tr('nar_summary')} color={C.accent}/>
            {/* Narrative prose */}
            <p style={{fontSize:13,color:C.text1,lineHeight:1.75,
              direction:RTL?'rtl':'ltr',marginBottom:20,maxWidth:700}}>
              {result.executive_summary}
            </p>
          </div>

          {/* Takeaways + Risks — 2 column */}
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14}}>

            {/* Key Takeaways */}
            <div style={{background:BG.panel,border:`1px solid ${BG.border}`,
              borderRadius:14,padding:'18px 20px'}}>
              <SectionHead label={tr('nar_takeaways')} color={C.green}/>
              <div style={{display:'flex',flexDirection:'column',gap:10}}>
                {(result.key_takeaways||[]).map((t,i)=>(
                  <div key={i} style={{display:'flex',gap:10,alignItems:'flex-start',
                    padding:'8px 10px',background:`${C.green}07`,borderRadius:8,
                    border:`1px solid ${C.green}15`}}>
                    <span style={{color:C.green,fontSize:13,flexShrink:0,lineHeight:1.5,
                      fontWeight:700}}>✓</span>
                    <span style={{fontSize:12,color:C.text2,lineHeight:1.6,
                      direction:RTL?'rtl':'ltr'}}>{t}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Risks */}
            <div style={{background:BG.panel,border:`1px solid ${BG.border}`,
              borderRadius:14,padding:'18px 20px'}}>
              <SectionHead label={tr('nar_risks')} color={C.amber}/>
              {(result.risks||[]).length===0?(
                <div style={{fontSize:12,color:C.text2,fontStyle:'italic'}}>
                  {tr('no_risks_identified')}
                </div>
              ):(
                <div style={{display:'flex',flexDirection:'column',gap:10}}>
                  {(result.risks||[]).map((r,i)=>(
                    <div key={i} style={{display:'flex',gap:10,alignItems:'flex-start',
                      padding:'8px 10px',background:`${C.amber}0d`,borderRadius:8,
                      border:`1px solid ${C.amber}30`}}>
                      <span style={{fontSize:14,flexShrink:0,lineHeight:1.4}}>⚠</span>
                      <span style={{fontSize:12,color:C.text2,lineHeight:1.6,
                        direction:RTL?'rtl':'ltr'}}>{r}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Recommended Action — highlight card */}
          {result.recommended_action&&(
            <div style={{background:`linear-gradient(135deg,${C.violet}18,${BG.elevated})`,
              border:`1px solid ${C.violet}40`,borderRadius:14,padding:'20px 24px',
              position:'relative',overflow:'hidden'}}>
              <div style={{position:'absolute',top:0,left:0,right:0,height:3,
                background:`linear-gradient(90deg,${C.violet},${C.blue})`,borderRadius:'14px 14px 0 0'}}/>
              <SectionHead label={tr('nar_action')} color={C.violet}/>
              <p style={{fontSize:13,color:C.text1,lineHeight:1.7,direction:RTL?'rtl':'ltr',
                maxWidth:680,margin:0,fontWeight:500}}>
                {result.recommended_action}
              </p>
            </div>
          )}

        </div>
      )}
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  Phase 20 — Management Report / Board Pack Panel
// ══════════════════════════════════════════════════════════════════════════════
function ManagementReportPanel({tr, selectedId, lang}) {
  const { toQueryString: mgmtScopeQS, window: win } = usePeriodScope()
  const [basis,   setBasis]   = useState('ytd')
  const [repLang, setRepLang] = useState(lang==='ar'?'ar':'en')
  const [report,  setReport]  = useState(null)
  const [loading, setLoading] = useState(false)
  const [err,     setErr]     = useState(null)

  const RTL = repLang === 'ar'

  const statusCfg = {
    excellent:{color:C.green, bg:`${C.green}15`},
    good:     {color:C.accent,bg:`${C.accent}15`},
    warning:  {color:C.amber, bg:`${C.amber}15`},
    critical: {color:C.red,   bg:`${C.red}15`},
    neutral:  {color:C.text2, bg:`${C.text3}10`},
  }
  const priClr = {high:C.green,medium:C.amber,low:C.text3}
  const priLbl = p => ({high:tr('dec_pri_high'),medium:tr('dec_pri_medium'),low:tr('dec_pri_low')}[p]||p)
  const packLbl = p => ({conservative:tr('dec_pack_conservative'),base:tr('dec_pack_base'),aggressive:tr('dec_pack_aggressive')}[p]||p)
  const packClr = {conservative:C.text2,base:C.accent,aggressive:C.amber}

  async function run() {
    if (!selectedId) return
    setLoading(true); setErr(null)
    try {
      const base = buildAnalysisQuery(mgmtScopeQS, { lang: repLang, window: win, consolidate: false })
      if (base === null) { setErr(tr('err_scope_custom_incomplete')); setLoading(false); return }
      const r = await fetch(
        `/api/v1/analysis/${selectedId}/management-report?${base}&basis=${encodeURIComponent(basis)}`,
        { headers: getAuthHeaders() }
      )
      const d = await r.json()
      if (!r.ok) { setErr(d.detail||'Failed'); return }
      setReport(d)
    } catch(e) { setErr(e.message) }
    finally { setLoading(false) }
  }

  const SecHead = ({label, color=C.text3, icon}) => (
    <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:12}}>
      {icon&&<span style={{fontSize:14}}>{icon}</span>}
      <div style={{fontSize:10,fontWeight:800,color,textTransform:'uppercase',letterSpacing:'.08em'}}>
        {label}
      </div>
      <div style={{flex:1,height:1,background:`${color}30`}}/>
    </div>
  )

  const KpiCell = ({label,value,sub,color=C.text1}) => (
    <div style={{background:BG.elevated,borderRadius:10,padding:'12px 14px',border:`1px solid ${BG.border}`}}>
      <div style={{fontSize:10,color:C.text2,textTransform:'uppercase',letterSpacing:'.05em',marginBottom:4}}>{label}</div>
      <div style={{fontFamily:'var(--font-mono)',fontSize:16,fontWeight:800,color,direction:'ltr',lineHeight:1}}>{value}</div>
      {sub&&<div style={{fontSize:10,color:C.text2,marginTop:4,direction:'ltr'}}>{sub}</div>}
    </div>
  )

  const secs = report?.sections || {}
  const kpi  = secs.kpi_snapshot?.data || {}
  const ytd  = kpi.ytd || {}
  const dec  = secs.decision_summary?.data || {}
  const best = dec.best || {}
  const packs = dec.scenario_packs || {}
  const status = report?.status || 'neutral'
  const stClr = (statusCfg[status]||statusCfg.neutral).color
  const stBg  = (statusCfg[status]||statusCfg.neutral).bg

  return (
    <div style={{display:'flex',flexDirection:'column',gap:16,maxWidth:960}}>

      {/* Controls */}
      <div style={{display:'flex',gap:10,alignItems:'flex-end',flexWrap:'wrap',
        background:BG.panel,border:`1px solid ${BG.border}`,borderRadius:12,padding:'14px 18px'}}>
        <div>
          <div style={{fontSize:10,color:C.text2,fontWeight:700,textTransform:'uppercase',letterSpacing:'.05em',marginBottom:5}}>{tr('nar_basis')}</div>
          <select value={basis} onChange={e=>{setBasis(e.target.value);setReport(null)}} style={{...SELECT_DARK,width:'auto'}}>
            <option value="ytd">{tr('wi_basis_ytd')}</option>
            <option value="latest_month">{tr('wi_basis_month')}</option>
            <option value="full_year">{tr('wi_basis_fy')}</option>
          </select>
        </div>
        <div>
          <div style={{fontSize:10,color:C.text2,fontWeight:700,textTransform:'uppercase',letterSpacing:'.05em',marginBottom:5}}>{tr('nar_lang_label')}</div>
          <select value={repLang} onChange={e=>setRepLang(e.target.value)} style={{...SELECT_DARK,width:'auto'}}>
            <option value="en">{tr('nar_lang_en')}</option>
            <option value="ar">{tr('nar_lang_ar')}</option>
          </select>
        </div>
        <div style={{marginLeft:'auto',display:'flex',alignItems:'center',gap:10}}>
          {err&&<span style={{fontSize:11,color:C.red}}>⚠ {err}</span>}
          <button onClick={run} disabled={loading||!selectedId}
            style={{padding:'9px 22px',borderRadius:9,border:'none',
              background:loading?BG.border:C.accent,color:loading?C.text2:'#000',
              fontSize:13,fontWeight:700,cursor:loading?'not-allowed':'pointer',
              fontFamily:'var(--font-display)',display:'flex',alignItems:'center',gap:8}}>
            {loading&&<div style={{width:12,height:12,border:'2px solid rgba(0,0,0,.2)',borderTopColor:'#000',borderRadius:'50%',animation:'spin .7s linear infinite'}}/>}
            {report?tr('rep_refresh'):tr('rep_generate')}
          </button>
        </div>
      </div>

      {!report&&!loading&&(
        <div style={{display:'flex',flexDirection:'column',alignItems:'center',padding:'60px 0',gap:12}}>
          <span style={{fontSize:44,opacity:.15}}>📋</span>
          <span style={{fontSize:13,color:C.text2}}>{tr('rep_no_data')}</span>
        </div>
      )}

      {report&&(<>

        {/* ── Header strip: company + status + period ── */}
        <div style={{background:stBg,border:`1px solid ${stClr}30`,borderRadius:12,
          padding:'16px 20px',display:'flex',alignItems:'center',gap:16,flexWrap:'wrap'}}>
          <div>
            <div style={{fontSize:13,fontWeight:800,color:C.text1}}>{report.company?.name}</div>
            <div style={{fontSize:11,color:C.text2,marginTop:2}}>{report.period_label}</div>
          </div>
          <div style={{marginLeft:'auto',display:'flex',gap:10,alignItems:'center'}}>
            <div style={{width:10,height:10,borderRadius:'50%',background:stClr,boxShadow:`0 0 8px ${stClr}`}}/>
            <span style={{fontSize:13,fontWeight:800,color:stClr,textTransform:'uppercase',letterSpacing:'.05em'}}>
              {({excellent:tr('nar_status_excellent'),good:tr('nar_status_good'),
                 warning:tr('nar_status_warning'),critical:tr('nar_status_critical'),
                 neutral:tr('nar_status_neutral')})[status]||status}
            </span>
          </div>
        </div>

        {/* ── KPI Snapshot ── */}
        <div style={{background:BG.panel,border:`1px solid ${BG.border}`,borderRadius:12,padding:'18px 20px'}}>
          <SecHead label={tr('rep_kpi_snapshot')} color={C.accent} icon="📊"/>
          <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(130px,1fr))',gap:10}}>
            <KpiCell label={tr('al_kpi_revenue')}    value={ytd.revenue_fmt||'—'} color={C.accent}
              sub={ytd.revenue_vs_prior_pct!=null?`${formatSignedPctForLang(ytd.revenue_vs_prior_pct, 1, repLang)} ${tr('rep_vs_prior')}`:undefined}/>
            <KpiCell label={tr('al_kpi_net_profit')} value={ytd.net_profit_fmt||'—'} color={C.green}
              sub={ytd.net_profit_vs_prior_pct!=null?`${formatSignedPctForLang(ytd.net_profit_vs_prior_pct, 1, repLang)} ${tr('rep_vs_prior')}`:undefined}/>
            <KpiCell label={tr('wi_net_margin')}     value={ytd.net_margin_fmt||'—'} color={C.violet}
              sub={ytd.margin_vs_prior_pp!=null?`${formatPpForLang(ytd.margin_vs_prior_pp, 2, repLang)} ${tr('rep_vs_prior')}`:undefined}/>
            <KpiCell label={`${tr('al_ytd_label')} ${ytd.year||''}`}
              value={`${ytd.month_count||'?'} ${tr('rep_months')}`}
              color={ytd.has_gaps?C.amber:C.text2}
              sub={ytd.has_gaps?tr('al_ytd_gaps_badge'):undefined}/>
          </div>
        </div>

        {/* ── Executive Summary + Key Findings side by side ── */}
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14}}>
          <div style={{background:BG.panel,border:`1px solid ${BG.border}`,borderRadius:12,padding:'18px 20px'}}>
            <SecHead label={tr('nar_summary')} color={C.accent} icon="📝"/>
            <p style={{fontSize:12,color:C.text1,lineHeight:1.7,direction:RTL?'rtl':'ltr',margin:0,maxWidth:440}}>
              {secs.executive_summary?.content||'—'}
            </p>
          </div>
          <div style={{background:BG.panel,border:`1px solid ${BG.border}`,borderRadius:12,padding:'18px 20px'}}>
            <SecHead label={tr('rep_takeaways')} color={C.green} icon="✓"/>
            <div style={{display:'flex',flexDirection:'column',gap:8}}>
              {(secs.key_takeaways?.items||[]).slice(0,5).map((t,i)=>(
                <div key={i} style={{display:'flex',gap:8,alignItems:'flex-start',
                  padding:'7px 10px',background:`${C.green}07`,borderRadius:7,border:`1px solid ${C.green}15`}}>
                  <span style={{color:C.green,fontSize:11,flexShrink:0,fontWeight:700,lineHeight:1.5}}>✓</span>
                  <span style={{fontSize:11,color:C.text2,lineHeight:1.5,direction:RTL?'rtl':'ltr'}}>{t}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── Board Recommendation + Risks side by side ── */}
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14}}>
          {/* Recommendation */}
          <div style={{background:`linear-gradient(135deg,${C.violet}15,${BG.elevated})`,
            border:`1px solid ${C.violet}40`,borderRadius:12,padding:'18px 20px',
            position:'relative',overflow:'hidden'}}>
            <div style={{position:'absolute',top:0,left:0,right:0,height:3,
              background:`linear-gradient(90deg,${C.violet},${C.blue})`,borderRadius:'12px 12px 0 0'}}/>
            <SecHead label={tr('rep_best_action')} color={C.violet} icon="🎯"/>
            {best.label&&(
              <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:8}}>
                <span style={{fontSize:13,fontWeight:700,color:C.text1}}>{best.label}</span>
                {best.priority&&<span style={{fontSize:9,fontWeight:700,padding:'2px 9px',
                  borderRadius:12,background:`${priClr[best.priority]||C.text3}20`,
                  color:priClr[best.priority]||C.text3,textTransform:'uppercase'}}>
                  {priLbl(best.priority)}
                </span>}
              </div>
            )}
            {best.confidence!=null&&(
              <div style={{marginBottom:10}}>
                <div style={{display:'flex',justifyContent:'space-between',marginBottom:4}}>
                  <span style={{fontSize:10,color:C.text2,textTransform:'uppercase',letterSpacing:'.05em'}}>{tr('rep_confidence')}</span>
                  <span style={{fontSize:9,fontFamily:'var(--font-mono)',color:C.text2,direction:'ltr'}}>{formatPctForLang(best.confidence, 0, repLang)}</span>
                </div>
                <div style={{height:4,background:BG.border,borderRadius:2,overflow:'hidden'}}>
                  <div style={{height:'100%',width:`${best.confidence}%`,
                    background:best.confidence>=70?C.green:best.confidence>=40?C.amber:C.red,borderRadius:2}}/>
                </div>
              </div>
            )}
            <div style={{display:'flex',gap:14,marginBottom:10}}>
              {best.np_delta_fmt&&<div>
                <div style={{fontSize:10,color:C.text2,textTransform:'uppercase',letterSpacing:'.05em'}}>{tr('dec_np_delta')}</div>
                <div style={{fontFamily:'var(--font-mono)',fontSize:14,fontWeight:700,color:C.green,direction:'ltr'}}>
                  {best.np_delta>0?'+':''}{best.np_delta_fmt}
                </div>
              </div>}
              {best.margin_pp!=null&&<div>
                <div style={{fontSize:10,color:C.text2,textTransform:'uppercase',letterSpacing:'.05em'}}>{tr('dec_margin_pp')}</div>
                <div style={{fontFamily:'var(--font-mono)',fontSize:14,fontWeight:700,color:C.violet,direction:'ltr'}}>
                  {formatPpForLang(best.margin_pp, 2, repLang)}
                </div>
              </div>}
            </div>
            {secs.recommended_action?.content&&(
              <p style={{fontSize:11,color:C.text2,lineHeight:1.6,direction:RTL?'rtl':'ltr',margin:0}}>
                {secs.recommended_action.content}
              </p>
            )}
          </div>

          {/* Risks */}
          <div style={{background:BG.panel,border:`1px solid ${BG.border}`,borderRadius:12,padding:'18px 20px'}}>
            <SecHead label={tr('rep_risks')} color={C.amber} icon="⚠"/>
            {(secs.key_risks?.items||[]).length===0
              ? <span style={{fontSize:11,color:C.text2,fontStyle:'italic'}}>{tr('no_risks_identified')}</span>
              : <div style={{display:'flex',flexDirection:'column',gap:8}}>
                  {(secs.key_risks?.items||[]).map((r,i)=>(
                    <div key={i} style={{display:'flex',gap:8,alignItems:'flex-start',
                      padding:'7px 10px',background:`${C.amber}0d`,borderRadius:7,border:`1px solid ${C.amber}25`}}>
                      <span style={{fontSize:12,flexShrink:0,lineHeight:1.4}}>⚠</span>
                      <span style={{fontSize:11,color:C.text2,lineHeight:1.5,direction:RTL?'rtl':'ltr'}}>{r}</span>
                    </div>
                  ))}
                </div>
            }
          </div>
        </div>

        {/* ── Scenario Packs ── */}
        {Object.keys(packs).length>0&&(
          <div style={{background:BG.panel,border:`1px solid ${BG.border}`,borderRadius:12,overflow:'hidden'}}>
            <div style={{padding:'12px 18px',borderBottom:`1px solid ${BG.border}`,
              fontSize:10,fontWeight:800,color:C.text2,textTransform:'uppercase',letterSpacing:'.07em'}}>
              {tr('rep_packs')}
            </div>
            <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)'}}>
              {['conservative','base','aggressive'].map((pid,i)=>{
                const pk = packs[pid]; if(!pk) return null
                const pc = packClr[pid]||C.text2
                return (
                  <div key={pid} style={{padding:'14px 18px',borderRight:i<2?`1px solid ${BG.border}`:'none',
                    borderTop:`3px solid ${pc}`}}>
                    <div style={{fontSize:10,fontWeight:700,color:pc,textTransform:'uppercase',
                      letterSpacing:'.05em',marginBottom:10}}>{packLbl(pid)}</div>
                    <div style={{display:'flex',flexDirection:'column',gap:6}}>
                      {[
                        {label:tr('dec_pack_np_pct'),  val:pk.np_pct!=null?formatSignedPctForLang(pk.np_pct, 1, repLang):null, clr:pk.np_pct>=0?C.green:C.red},
                        {label:tr('dec_pack_margin_pp'),val:pk.margin_pp!=null?formatPpForLang(pk.margin_pp, 2, repLang):null, clr:pk.margin_pp>=0?C.green:C.red},
                        {label:tr('dec_pack_np_delta'), val:pk.np_delta_fmt||null, clr:C.text2},
                      ].map(({label,val,clr})=>(
                        <div key={label} style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                          <span style={{fontSize:10,color:C.text2}}>{label}</span>
                          <span style={{fontFamily:'var(--font-mono)',fontSize:11,fontWeight:700,color:clr,direction:'ltr'}}>{val||'—'}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Warnings */}
        {(report.warnings||[]).length>0&&(
          <div style={{background:`${C.amber}0e`,border:`1px solid ${C.amber}30`,borderRadius:8,padding:'10px 14px'}}>
            {(report.warnings||[]).map((w,i)=>(
              <div key={i} style={{fontSize:11,color:C.amber,marginBottom:i<report.warnings.length-1?4:0}}>⚠ {w}</div>
            ))}
          </div>
        )}

      </>)}
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  Phase 21 — Financial Intelligence Panel
// ══════════════════════════════════════════════════════════════════════════════
function FinIntelPanel({tr, selectedId, lang, data}) {
  // Same executive payload as other Dashboard tabs: data.data.intelligence from GET /analysis/{id}/executive
  const { toQueryString: intelScopeQS, window: win } = usePeriodScope()
  const [alerts,     setAlerts]     = useState(null)
  const [alertsLoad, setAlertsLoad] = useState(false)
  const loading    = false
  const err        = null

  const d         = data?.data || {}
  const d21       = d.intelligence || {}
  const meta      = data?.meta || {}

  const statusClr = {excellent:C.green, good:C.accent, warning:C.amber, risk:C.red, neutral:C.text3}
  const sevClr    = {critical:C.red,    high:C.amber,  medium:C.violet, data_quality:C.blue}
  const dirLabel  = (dir) => ({up:tr('intel_dir_up'), down:tr('intel_dir_down'),
                              stable:tr('intel_dir_stable')})[dir] || tr('intel_dir_na')
  const dirClr    = (dir) => ({up:C.green, down:C.red, stable:C.text2})[dir] || C.text3
  const ratioSt   = (s) => ({good:C.green, warning:C.amber, risk:C.red, neutral:C.text2})[s] || C.text2

  const hasIntel  = Boolean(d.intelligence && Object.keys(d21).length)

  // Alerts still fetched independently (not always expanded in main executive response).
  function run() { if (selectedId) fetchAlerts() }

  async function fetchAlerts() {
    if (!selectedId) return
    setAlertsLoad(true)
    try {
      const qs = buildAnalysisQuery(intelScopeQS, { lang, window: win, consolidate: false })
      if (qs === null) return
      const r = await fetch(`/api/v1/analysis/${selectedId}/alerts?${qs}`, { headers: getAuthHeaders() })
      if (!r.ok) return
      const aj = await r.json()
      setAlerts(aj?.data || null)
    } catch { /* non-critical */ }
    finally { setAlertsLoad(false) }
  }

  const ratios  = d21.ratios || {}
  const trends  = d21.trends || {}
  const anoms   = d21.anomalies || []
  const score   = d21.health_score_v2
  const status  = d21.status || 'neutral'
  const stClr   = statusClr[status] || C.text3

  const SectionHead = ({label, color=C.text2}) => (
    <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:10}}>
      <div style={{width:16,height:2,background:color,borderRadius:2}}/>
      <span style={{fontSize:10,fontWeight:800,color,textTransform:'uppercase',letterSpacing:'.07em'}}>{label}</span>
    </div>
  )

  const RatioCard = ({label, value, unit, status: s}) => {
    const u = String(unit || '')
    let main = '—'
    let suffix = ''
    if (value != null && value !== '' && Number.isFinite(Number(value))) {
      const n = Number(value)
      if (u === '%') main = formatPctForLang(n, 1, lang)
      else if (u === 'x') main = formatMultipleForLang(n, 2, lang)
      else if (u === 'days') main = formatDays(n)
      else {
        main = formatCompactForLang(n, lang)
        suffix = u ? ` ${u}` : ''
      }
    }
    return (
      <div style={{background:BG.elevated,borderRadius:9,padding:'10px 12px',
        borderWidth:'2px 1px 1px 1px',borderStyle:'solid',borderColor:`${ratioSt(s)} ${ratioSt(s)}30 ${ratioSt(s)}30 ${ratioSt(s)}30`}}>
        <div style={{fontSize:10,color:C.text2,textTransform:'uppercase',letterSpacing:'.05em',marginBottom:4}}>{label}</div>
        <div style={{fontFamily:'var(--font-mono)',fontSize:15,fontWeight:700,color:ratioSt(s),direction:'ltr',lineHeight:1}}>
          {main}<span style={{fontSize:10,color:C.text2,marginLeft:3}}>{suffix}</span>
        </div>
      </div>
    )
  }

  const TrendRow = ({label, dir, yoy, ytd, roll, ytdAsPp}) => (
    <div style={{display:'flex',alignItems:'center',gap:10,padding:'8px 12px',
      background:BG.elevated,borderRadius:8,border:`1px solid ${BG.border}`}}>
      <span style={{flex:1,fontSize:11,color:C.text2}}>{label}</span>
      <span style={{fontSize:11,fontWeight:700,color:dirClr(dir),minWidth:80}}>{dirLabel(dir)}</span>
      {yoy!=null&&<span style={{fontFamily:'var(--font-mono)',fontSize:10,color:yoy>=0?C.green:C.red,direction:'ltr',minWidth:55}}>
        {formatSignedPctForLang(yoy, 1, lang)} {tr('intel_yoy')}
      </span>}
      {ytd!=null&&<span style={{fontFamily:'var(--font-mono)',fontSize:10,color:ytd>=0?C.green:C.red,direction:'ltr',minWidth:65}}>
        {ytdAsPp ? formatPpForLang(ytd, 1, lang) : formatSignedPctForLang(ytd, 1, lang)} {tr('intel_ytd_vs_prior')}
      </span>}
    </div>
  )

  return (
    <div style={{display:'flex',flexDirection:'column',gap:14,maxWidth:960}}>
      {/* Controls */}
      <div style={{display:'flex',gap:10,alignItems:'center',background:BG.panel,
        border:`1px solid ${BG.border}`,borderRadius:12,padding:'12px 18px'}}>
        <button onClick={run} disabled={loading||!selectedId}
          style={{padding:'8px 20px',borderRadius:9,border:'none',
            background:loading?BG.border:C.accent,color:loading?C.text2:'#000',
            fontSize:12,fontWeight:700,cursor:loading?'not-allowed':'pointer',
            fontFamily:'var(--font-display)',display:'flex',alignItems:'center',gap:6}}>
          {loading&&<div style={{width:10,height:10,border:'2px solid rgba(0,0,0,.2)',borderTopColor:'#000',
            borderRadius:'50%',animation:'spin .7s linear infinite'}}/>}
          {tr('intel_run')}
        </button>
        {err&&<span style={{fontSize:11,color:C.red}}>⚠ {err}</span>}
        {hasIntel&&(
          <div style={{marginLeft:'auto',display:'flex',alignItems:'center',gap:10}}>
            <div style={{width:8,height:8,borderRadius:'50%',background:stClr,boxShadow:`0 0 6px ${stClr}`}}/>
            <span style={{fontFamily:'var(--font-mono)',fontSize:11,fontWeight:700,color:stClr}}>
              {score??'—'}/100
            </span>
            <span style={{fontSize:10,color:C.text2,fontFamily:'monospace'}}>{meta.window ?? '—'}</span>
          </div>
        )}
      </div>

      {!hasIntel&&!loading&&Boolean(data)&&(
        <div style={{display:'flex',flexDirection:'column',alignItems:'center',padding:'50px 0',gap:10}}>
          <span style={{fontSize:40,opacity:.12}}>🧠</span>
          <span style={{fontSize:13,color:C.text2}}>{tr('intel_no_data')}</span>
        </div>
      )}

      {hasIntel&&(<>
        {/* Ratios grid */}
        <div style={{background:BG.panel,border:`1px solid ${BG.border}`,borderRadius:12,padding:'16px 18px'}}>
          <SectionHead label={tr('intel_ratios')} color={C.accent}/>
          <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(130px,1fr))',gap:10}}>
            {[
              {label:tr('intel_gross_margin'),  ...(ratios.profitability?.gross_margin_pct||{})},
              {label:tr('intel_net_margin'),     ...(ratios.profitability?.net_margin_pct||{})},
              {label:tr('intel_op_margin'),      ...(ratios.profitability?.operating_margin_pct||{})},
              {label:tr('intel_current_ratio'),  ...(ratios.liquidity?.current_ratio||{})},
              {label:tr('intel_quick_ratio'),    ...(ratios.liquidity?.quick_ratio||{})},
              {label:tr('intel_debt_ratio'),     ...(ratios.leverage?.debt_ratio_pct||{})},
              {label:tr('intel_inv_turnover'),   ...(ratios.efficiency?.inventory_turnover||{})},
              {label:tr('intel_dso'),            ...(ratios.efficiency?.dso_days||{})},
              {label:tr('intel_ccc'),            ...(ratios.efficiency?.ccc_days||{})},
            ].map(({label,value,unit,status:s})=>(
              <RatioCard key={label} label={label}
                value={value} unit={unit||''} status={s||'neutral'}/>
            ))}
          </div>
        </div>

        {/* Trends */}
        <div style={{background:BG.panel,border:`1px solid ${BG.border}`,borderRadius:12,padding:'16px 18px'}}>
          <SectionHead label={tr('intel_trends')} color={C.violet}/>
          <div style={{display:'flex',flexDirection:'column',gap:6}}>
            <TrendRow label={tr('intel_revenue')}
              dir={trends.revenue?.direction}   yoy={trends.revenue?.yoy_change}
              ytd={trends.revenue?.ytd_vs_prior} roll={trends.revenue?.rolling_3m}/>
            <TrendRow label={tr('intel_net_profit')}
              dir={trends.net_profit?.direction} yoy={trends.net_profit?.yoy_change}
              ytd={trends.net_profit?.ytd_vs_prior}/>
            <TrendRow label={tr('intel_gross_margin_trend')}
              dir={trends.gross_margin?.direction} ytd={trends.gross_margin?.ytd_margin_pp} ytdAsPp/>
          </div>
        </div>

        {/* Anomalies */}
        <div style={{background:BG.panel,border:`1px solid ${BG.border}`,borderRadius:12,padding:'16px 18px'}}>
          <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:10}}>
            <SectionHead label={tr('intel_anomalies')} color={C.amber}/>
            {anoms.length>0&&<span style={{fontSize:9,fontWeight:700,padding:'2px 8px',borderRadius:10,
              background:`${C.amber}20`,color:C.amber}}>{anoms.length}</span>}
          </div>
          {anoms.length===0
            ? <div style={{fontSize:12,color:C.text2,fontStyle:'italic'}}>{tr('intel_no_anomalies')}</div>
            : <div style={{display:'flex',flexDirection:'column',gap:6}}>
                {anoms.map((a,i)=>(
                  <div key={i} style={{display:'flex',gap:10,alignItems:'flex-start',padding:'8px 10px',
                    background:`${sevClr[a.severity]||C.violet}0d`,borderRadius:7,
                    border:`1px solid ${sevClr[a.severity]||C.violet}30`}}>
                    <span style={{fontSize:12,flexShrink:0,lineHeight:1.4}}>
                      {a.severity==='critical'?'🚨':a.severity==='high'?'⚠':'ℹ'}
                    </span>
                    <div style={{flex:1}}>
                      <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:2}}>
                        <span style={{fontSize:10,fontWeight:700,color:sevClr[a.severity]||C.violet,
                          textTransform:'uppercase'}}>{a.metric}</span>
                        <span style={{fontFamily:'var(--font-mono)',fontSize:10,color:C.text2}}>{a.period}</span>
                        {a.change_pct!=null&&<span style={{fontFamily:'var(--font-mono)',fontSize:10,
                          color:a.change_pct>=0?C.green:C.red,direction:'ltr'}}>
                          {formatSignedPctForLang(a.change_pct, 1, lang)}
                        </span>}
                      </div>
                      <div style={{fontSize:11,color:C.text2,lineHeight:1.4}}>{a.detail}</div>
                    </div>
                  </div>
                ))}
              </div>
          }
        </div>
      </>)}

      {/* Phase 23 — Key Alerts Section */}
      {(alerts||alertsLoad)&&Boolean(data)&&(
        <div style={{background:BG.panel,border:`1px solid ${BG.border}`,borderRadius:12,padding:'16px 18px'}}>
          <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:12}}>
            <SectionHead label={tr('alerts_title')} color={C.red}/>
            {alerts?.summary&&(
              <div style={{display:'flex',gap:6}}>
                {[['high',C.red],['medium',C.amber],['low',C.blue]].map(([k,c])=>
                  alerts.summary[k]>0&&(
                    <span key={k} style={{fontSize:9,fontWeight:700,padding:'2px 8px',borderRadius:10,
                      background:`${c}20`,color:c,textTransform:'uppercase'}}>
                      {tr(`alerts_${k}`)} {alerts.summary[k]}
                    </span>
                  )
                )}
              </div>
            )}
          </div>
          {alertsLoad&&<div style={{fontSize:11,color:C.text2}}>...</div>}
          {!alertsLoad&&alerts&&(
            (alerts.alerts||[]).length===0
              ? <div style={{fontSize:12,color:C.text2,fontStyle:'italic'}}>{tr('alerts_none')}</div>
              : <div style={{display:'flex',flexDirection:'column',gap:8}}>
                  {(alerts.alerts||[]).map((a,i)=>{
                    const sevClr = {high:C.red,medium:C.amber,low:C.blue}[a.severity]||C.text3
                    const impactKey = `impact_${a.impact}`
                    return (
                      <div key={a.id||i} style={{padding:'12px 14px',borderRadius:9,
                        background:`${sevClr}0d`,border:`1px solid ${sevClr}30`,
                        borderLeft:`3px solid ${sevClr}`}}>
                        <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:6}}>
                          <span style={{fontSize:11,fontWeight:700,color:sevClr}}>{a.title}</span>
                          <span style={{marginLeft:'auto',fontSize:9,padding:'1px 7px',borderRadius:10,
                            background:`${sevClr}20`,color:sevClr,textTransform:'uppercase',fontWeight:700}}>
                            {tr(`alerts_${a.severity}`)||a.severity}
                          </span>
                          <span style={{fontSize:10,color:C.text2,fontFamily:'var(--font-mono)'}}>
                            {formatPctForLang(a.confidence, 0, lang)}
                          </span>
                        </div>
                        <div style={{fontSize:11,color:C.text2,lineHeight:1.5,marginBottom:6}}>{a.message}</div>
                        <div style={{display:'flex',alignItems:'flex-start',gap:6}}>
                          <span style={{fontSize:9,fontWeight:700,color:sevClr,flexShrink:0,marginTop:1}}>→</span>
                          <span style={{fontSize:11,color:C.text2,fontStyle:'italic',lineHeight:1.4}}>{a.action}</span>
                        </div>
                        {a.impact&&(
                          <div style={{marginTop:5}}>
                            <span style={{fontSize:10,color:C.text2,padding:'1px 6px',borderRadius:5,
                              background:BG.elevated}}>{tr(impactKey)||a.impact}</span>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
          )}
        </div>
      )}

    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  Phase 25 — Decisions Panel V2 (CFO Decision Engine)
// ══════════════════════════════════════════════════════════════════════════════
function DecisionsPanelV2({tr, selectedId, lang}) {
  const { toQueryString: decQS, window: win } = usePeriodScope()
  const [result,  setResult]  = useState(null)
  const [loading, setLoading] = useState(false)
  const [err,     setErr]     = useState(null)

  const urgClr = { high: C.red, medium: C.amber, low: C.blue }
  const impClr = { high: C.red, medium: C.amber, low: C.blue }
  const domClr = { liquidity:C.blue, profitability:C.green, efficiency:C.violet,
                   leverage:C.amber, growth:C.accent }
  const domIco = { liquidity:'💧', profitability:'📈', efficiency:'⚡',
                   leverage:'🏋', growth:'🚀' }

  async function run() {
    if (!selectedId) return
    const qs = buildAnalysisQuery(decQS, { lang, window: win, consolidate: false })
    if (qs === null) { setErr(tr('fc_custom_scope_hint')); return }
    setLoading(true); setErr(null)
    try {
      const r = await fetch(`/api/v1/analysis/${selectedId}/decisions?${qs}`,
                            { headers: getAuthHeaders() })
      if (!r.ok) { const t=await r.text(); setErr(t||r.statusText); return }
      const d = await r.json()
      setResult(d)
    } catch(e) { setErr(e.message) }
    finally { setLoading(false) }
  }

  const decisions = result?.data?.decisions || []
  const summary   = result?.data?.summary   || {}
  const top       = decisions[0]
  const secondary = decisions.slice(1)

  const Badge = ({label, color}) => (
    <span style={{fontSize:9,fontWeight:800,padding:'2px 8px',borderRadius:20,
      background:`${color}18`,color,border:`1px solid ${color}35`,
      textTransform:'uppercase',letterSpacing:'.05em',flexShrink:0}}>
      {label}
    </span>
  )

  const SmallDecisionCard = ({dec}) => {
    const dc = domClr[dec.domain]||C.accent
    const uc = urgClr[dec.urgency]||C.text3
    return (
      <div style={{flex:'1 1 46%',background:BG.elevated,borderRadius:11,overflow:'hidden',
        borderWidth:'3px 1px 1px 1px',borderStyle:'solid',borderColor:`${dc} ${BG.border} ${BG.border} ${BG.border}`}}>
        <div style={{padding:'12px 14px 0'}}>
          <div style={{display:'flex',alignItems:'center',gap:6,marginBottom:8,flexWrap:'wrap'}}>
            <span style={{fontSize:14}}>{domIco[dec.domain]||'◉'}</span>
            <span style={{fontSize:11,fontWeight:700,color:dc,textTransform:'uppercase',
              letterSpacing:'.06em'}}>{tr(`domain_${dec.domain}`)||dec.domain}</span>
            <span style={{marginLeft:'auto'}}><Badge label={tr(`urgency_${dec.urgency}`)||dec.urgency} color={uc}/></span>
          </div>
          <div style={{fontSize:13,fontWeight:700,color:C.text1,lineHeight:1.4,marginBottom:8}}>
            {dec.title}
          </div>
          <div style={{fontSize:11,color:C.text2,lineHeight:1.5,marginBottom:10}}>
            {dec.reason}
          </div>
        </div>
        <div style={{background:`${dc}08`,borderTop:`1px solid ${dc}20`,
          padding:'10px 14px',display:'flex',flexDirection:'column',gap:6}}>
          <div>
            <div style={{fontSize:9,fontWeight:800,color:dc,textTransform:'uppercase',
              letterSpacing:'.06em',marginBottom:3}}>{tr('dec_v2_action')}</div>
            <div style={{fontSize:11,color:C.text2,lineHeight:1.5}}>{dec.action}</div>
          </div>
          <div style={{display:'flex',gap:8,flexWrap:'wrap',marginTop:2}}>
            <span style={{fontSize:10,color:C.text2,background:BG.panel,
              padding:'2px 7px',borderRadius:5,border:`1px solid ${BG.border}`}}>
              ⏱ {dec.timeframe}
            </span>
            <span style={{fontSize:10,color:C.text2,fontFamily:'var(--font-mono)',
              background:BG.panel,padding:'2px 7px',borderRadius:5,
              border:`1px solid ${BG.border}`}}>
              {formatPctForLang(dec.confidence, 0, lang)}
            </span>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div style={{display:'flex',flexDirection:'column',gap:14,maxWidth:960}}>

      {/* Controls bar */}
      <div style={{display:'flex',alignItems:'center',gap:10,background:BG.panel,
        border:`1px solid ${BG.border}`,borderRadius:12,padding:'12px 18px',flexWrap:'wrap'}}>
        <button onClick={run} disabled={loading||!selectedId}
          style={{padding:'8px 24px',borderRadius:9,border:'none',fontWeight:700,fontSize:12,
            background:loading?BG.border:C.accent,color:loading?C.text2:'#000',
            cursor:loading?'not-allowed':'pointer',fontFamily:'var(--font-display)',
            display:'flex',alignItems:'center',gap:6}}>
          {loading&&<div style={{width:10,height:10,border:'2px solid rgba(0,0,0,.2)',
            borderTopColor:'#000',borderRadius:'50%',animation:'spin .7s linear infinite'}}/>}
          {tr('dec_v2_run')}
        </button>
        {err&&<span style={{fontSize:11,color:C.red,flex:1}}>⚠ {err}</span>}
        {summary.health_score!=null&&(
          <div style={{marginLeft:'auto',display:'flex',alignItems:'center',gap:10}}>
            {summary.top_focus&&(
              <div style={{display:'flex',alignItems:'center',gap:5}}>
                <span style={{fontSize:10,color:C.text2,textTransform:'uppercase'}}>
                  {tr('dec_v2_focus')}:
                </span>
                <span style={{fontSize:10,fontWeight:700,
                  color:domClr[summary.top_focus]||C.accent,textTransform:'capitalize'}}>
                  {tr(`domain_${summary.top_focus}`)||summary.top_focus}
                </span>
              </div>
            )}
            <div style={{display:'flex',alignItems:'center',gap:4}}>
              <span style={{fontSize:10,color:C.text2}}>{tr('dec_v2_health')}:</span>
              <span style={{fontFamily:'var(--font-mono)',fontSize:12,fontWeight:700,
                color:summary.health_score>=60?C.green:summary.health_score>=40?C.amber:C.red}}>
                {summary.health_score}/100
              </span>
            </div>
          </div>
        )}
      </div>

      {!result&&!loading&&(
        <div style={{display:'flex',flexDirection:'column',alignItems:'center',
          padding:'60px 0',gap:12}}>
          <span style={{fontSize:52,opacity:.1}}>🧭</span>
          <div style={{fontSize:14,fontWeight:600,color:C.text2}}>{tr('dec_v2_no_data')}</div>
        </div>
      )}

      {result&&top&&(<>

        {/* TOP PRIORITY CARD */}
        <div style={{background:BG.panel,border:`2px solid ${domClr[top.domain]||C.accent}`,
          borderRadius:14,overflow:'hidden'}}>

          {/* Header */}
          <div style={{background:`${domClr[top.domain]||C.accent}10`,
            borderBottom:`1px solid ${domClr[top.domain]||C.accent}30`,
            padding:'14px 20px',display:'flex',alignItems:'center',gap:10,flexWrap:'wrap'}}>
            <span style={{fontSize:22}}>{domIco[top.domain]||'◉'}</span>
            <div style={{flex:1}}>
              <div style={{fontSize:9,fontWeight:800,textTransform:'uppercase',letterSpacing:'.08em',
                color:domClr[top.domain]||C.accent,marginBottom:2}}>
                {tr('dec_v2_top_priority')} · {tr(`domain_${top.domain}`)||top.domain}
              </div>
              <div style={{fontSize:15,fontWeight:800,color:C.text1,lineHeight:1.3}}>
                {top.title}
              </div>
            </div>
            <div style={{display:'flex',gap:6,flexWrap:'wrap'}}>
              <Badge label={tr(`urgency_${top.urgency}`)||top.urgency}
                     color={urgClr[top.urgency]||C.text3}/>
              <Badge label={tr(`impact_${top.impact_level}`)||top.impact_level}
                     color={impClr[top.impact_level]||C.text3}/>
              <span style={{fontFamily:'var(--font-mono)',fontSize:10,color:C.text2,
                alignSelf:'center'}}>{formatPctForLang(top.confidence, 0, lang)}</span>
            </div>
          </div>

          {/* Body */}
          <div style={{padding:'18px 20px',display:'grid',
            gridTemplateColumns:'1fr 1fr',gap:16}}>

            <div>
              <div style={{fontSize:9,fontWeight:800,color:C.text2,textTransform:'uppercase',
                letterSpacing:'.07em',marginBottom:6}}>{tr('dec_v2_reason')}</div>
              <div style={{fontSize:12,color:C.text2,lineHeight:1.7}}>{top.reason}</div>
            </div>

            <div style={{background:`${domClr[top.domain]||C.accent}08`,borderRadius:9,
              padding:'12px 14px',border:`1px solid ${domClr[top.domain]||C.accent}20`}}>
              <div style={{fontSize:9,fontWeight:800,
                color:domClr[top.domain]||C.accent,textTransform:'uppercase',
                letterSpacing:'.07em',marginBottom:6}}>{tr('dec_v2_action')}</div>
              <div style={{fontSize:12,color:C.text2,lineHeight:1.7}}>{top.action}</div>
            </div>

            <div>
              <div style={{fontSize:9,fontWeight:800,color:C.green,textTransform:'uppercase',
                letterSpacing:'.07em',marginBottom:6}}>{tr('dec_v2_effect')}</div>
              <div style={{fontSize:12,color:C.text2,lineHeight:1.7}}>{top.expected_effect}</div>
            </div>

            <div style={{display:'flex',alignItems:'center',gap:8}}>
              <span style={{fontSize:22,opacity:.4}}>⏱</span>
              <div>
                <div style={{fontSize:9,fontWeight:800,color:C.text2,textTransform:'uppercase',
                  letterSpacing:'.07em',marginBottom:2}}>{tr('dec_v2_timeframe')}</div>
                <div style={{fontSize:14,fontWeight:700,
                  color:urgClr[top.urgency]||C.accent,fontFamily:'var(--font-mono)'}}>
                  {top.timeframe}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* SECONDARY CARDS */}
        {secondary.length>0&&(
          <div>
            <div style={{fontSize:10,fontWeight:700,color:C.text2,textTransform:'uppercase',
              letterSpacing:'.07em',marginBottom:10}}>{tr('dec_v2_secondary')}</div>
            <div style={{display:'flex',gap:12,flexWrap:'wrap'}}>
              {secondary.map((dec,i)=>(
                <SmallDecisionCard key={dec.key||i} dec={dec}/>
              ))}
            </div>
          </div>
        )}
      </>)}
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  Phase 26 — Root Causes Panel
// ══════════════════════════════════════════════════════════════════════════════
function RootCausesPanel({tr, selectedId, lang}) {
  const { toQueryString: rcQS, window: win } = usePeriodScope()
  const [result,  setResult]  = useState(null)
  const [loading, setLoading] = useState(false)
  const [err,     setErr]     = useState(null)
  const [expand,  setExpand]  = useState({})

  const impClr = { high: C.red, medium: C.amber, low: C.blue }
  const domClr = { liquidity:C.blue, profitability:C.green, efficiency:C.violet,
                   leverage:C.amber, growth:C.accent, cross_domain:'#e879f9' }
  const domIco = { liquidity:'💧', profitability:'📈', efficiency:'⚡',
                   leverage:'🏋', growth:'🚀', cross_domain:'🔗' }

  async function run() {
    if (!selectedId) return
    const qs = buildAnalysisQuery(rcQS, { lang, window: win, consolidate: false })
    if (qs === null) { setErr(tr('fc_custom_scope_hint')); return }
    setLoading(true); setErr(null)
    try {
      const r = await fetch(`/api/v1/analysis/${selectedId}/root-causes?${qs}`,
                            { headers: getAuthHeaders() })
      if (!r.ok) { const t=await r.text(); setErr(t||r.statusText); return }
      const d = await r.json()
      setResult(d)
    } catch(e) { setErr(e.message) }
    finally { setLoading(false) }
  }

  const causes  = result?.data?.causes || []
  const summary = result?.data?.summary || {}
  const high    = causes.filter(c=>c.impact==='high')
  const medium  = causes.filter(c=>c.impact!=='high')

  const toggle = (id) => setExpand(prev => ({...prev, [id]: !prev[id]}))

  const CauseCard = ({c}) => {
    const ic = impClr[c.impact]||C.text3
    const dc = domClr[c.domain]||C.accent
    const isOpen = expand[c.id]
    const linkedDoms = (c.linked_decisions||[]).map(d=>
      tr(`domain_${d}`)||d
    ).join(' · ')

    return (
      <div style={{borderRadius:10,overflow:'hidden',border:`1px solid ${BG.border}`,
        borderLeft:`4px solid ${ic}`,background:BG.panel}}>

        {/* Cause header — always visible */}
        <div onClick={()=>toggle(c.id)} style={{padding:'12px 16px',cursor:'pointer',
          display:'flex',gap:10,alignItems:'flex-start'}}>
          <span style={{fontSize:14,flexShrink:0,marginTop:1}}>{domIco[c.domain]||'◉'}</span>
          <div style={{flex:1}}>
            <div style={{display:'flex',alignItems:'center',gap:8,flexWrap:'wrap',marginBottom:4}}>
              <span style={{fontSize:11,fontWeight:700,color:C.text1,flex:1,lineHeight:1.3}}>
                {c.title}
              </span>
              <span style={{fontSize:9,fontWeight:700,padding:'2px 8px',borderRadius:20,
                background:`${ic}18`,color:ic,border:`1px solid ${ic}35`,flexShrink:0,
                textTransform:'uppercase',letterSpacing:'.05em'}}>
                {tr(`impact_${c.impact}`)||c.impact}
              </span>
              <span style={{fontSize:10,color:C.text2,fontFamily:'var(--font-mono)',flexShrink:0}}>
                {formatPctForLang(c.confidence, 0, lang)}
              </span>
              <span style={{color:C.text2,fontSize:10,flexShrink:0}}>{isOpen?'▲':'▼'}</span>
            </div>
            {/* Description — always visible, truncated */}
            <div style={{fontSize:11,color:C.text2,lineHeight:1.5,
              display:'-webkit-box',WebkitLineClamp:isOpen?undefined:2,
              WebkitBoxOrient:'vertical',overflow:isOpen?'visible':'hidden'}}>
              {c.description}
            </div>
          </div>
        </div>

        {/* Expanded detail */}
        {isOpen&&(
          <div style={{borderTop:`1px solid ${BG.border}`,
            padding:'12px 16px',display:'flex',flexDirection:'column',gap:10}}>

            {/* Mechanism — the WHY */}
            <div style={{background:`${dc}08`,borderRadius:8,padding:'10px 14px',
              border:`1px solid ${dc}20`}}>
              <div style={{fontSize:9,fontWeight:800,color:dc,textTransform:'uppercase',
                letterSpacing:'.07em',marginBottom:5}}>
                {tr('rc_mechanism')}
              </div>
              <div style={{fontSize:11,color:C.text2,lineHeight:1.7}}>{c.mechanism}</div>
            </div>

            {/* Linked decisions */}
            {linkedDoms&&(
              <div style={{display:'flex',alignItems:'center',gap:6,flexWrap:'wrap'}}>
                <span style={{fontSize:9,fontWeight:700,color:C.text2,textTransform:'uppercase',
                  letterSpacing:'.06em'}}>{tr('rc_linked')}:</span>
                {(c.linked_decisions||[]).map(d=>(
                  <span key={d} style={{fontSize:9,padding:'2px 8px',borderRadius:20,
                    background:`${domClr[d]||C.accent}18`,color:domClr[d]||C.accent,
                    border:`1px solid ${domClr[d]||C.accent}30`,fontWeight:700}}>
                    {tr(`domain_${d}`)||d}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    )
  }

  return (
    <div style={{display:'flex',flexDirection:'column',gap:14,maxWidth:960}}>

      {/* Controls */}
      <div style={{display:'flex',alignItems:'center',gap:10,background:BG.panel,
        border:`1px solid ${BG.border}`,borderRadius:12,padding:'12px 18px',flexWrap:'wrap'}}>
        <button onClick={run} disabled={loading||!selectedId}
          style={{padding:'8px 24px',borderRadius:9,border:'none',fontWeight:700,fontSize:12,
            background:loading?BG.border:C.accent,color:loading?C.text2:'#000',
            cursor:loading?'not-allowed':'pointer',fontFamily:'var(--font-display)',
            display:'flex',alignItems:'center',gap:6}}>
          {loading&&<div style={{width:10,height:10,border:'2px solid rgba(0,0,0,.2)',
            borderTopColor:'#000',borderRadius:'50%',animation:'spin .7s linear infinite'}}/>}
          {tr('rc_run')}
        </button>
        {err&&<span style={{fontSize:11,color:C.red}}>⚠ {err}</span>}
        {summary.total>0&&(
          <div style={{marginLeft:'auto',display:'flex',alignItems:'center',gap:10}}>
            {[['high',C.red],['medium',C.amber]].map(([k,c])=>
              summary[k]>0&&(
                <span key={k} style={{fontSize:10,fontWeight:700,padding:'2px 8px',
                  borderRadius:10,background:`${c}20`,color:c}}>
                  {summary[k]} {tr(`impact_${k}`)}
                </span>
              )
            )}
          </div>
        )}
      </div>

      {!result&&!loading&&(
        <div style={{display:'flex',flexDirection:'column',alignItems:'center',
          padding:'60px 0',gap:12}}>
          <span style={{fontSize:52,opacity:.1}}>🔍</span>
          <div style={{fontSize:14,fontWeight:600,color:C.text2}}>{tr('rc_no_data')}</div>
        </div>
      )}

      {result&&causes.length>0&&(<>
        {/* High impact causes */}
        {high.length>0&&(
          <div>
            <div style={{fontSize:10,fontWeight:700,color:C.red,textTransform:'uppercase',
              letterSpacing:'.07em',marginBottom:8,display:'flex',alignItems:'center',gap:6}}>
              <div style={{width:14,height:2,background:C.red,borderRadius:2}}/>
              {tr('rc_high_causes')} ({high.length})
            </div>
            <div style={{display:'flex',flexDirection:'column',gap:6}}>
              {high.map(c=><CauseCard key={c.id} c={c}/>)}
            </div>
          </div>
        )}

        {/* Medium/low causes */}
        {medium.length>0&&(
          <div>
            <div style={{fontSize:10,fontWeight:700,color:C.amber,textTransform:'uppercase',
              letterSpacing:'.07em',marginBottom:8,display:'flex',alignItems:'center',gap:6}}>
              <div style={{width:14,height:2,background:C.amber,borderRadius:2}}/>
              {tr('rc_medium_causes')} ({medium.length})
            </div>
            <div style={{display:'flex',flexDirection:'column',gap:6}}>
              {medium.map(c=><CauseCard key={c.id} c={c}/>)}
            </div>
          </div>
        )}
      </>)}
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  Phase 27 — Forecast Panel
// ══════════════════════════════════════════════════════════════════════════════
function ForecastPanel({tr, selectedId, lang}) {
  const { toQueryString: fcQS, window: win } = usePeriodScope()
  const [result,    setResult]    = useState(null)
  const [loading,   setLoading]   = useState(false)
  const [err,       setErr]       = useState(null)
  const [scenario,  setScenario]  = useState('base')
  const [metric,    setMetric]    = useState('revenue')

  const scClr  = { base: C.accent, optimistic: C.green, risk: C.red }
  const rlClr  = { low: C.green, medium: C.amber, high: C.red }
  const metricLabel = { revenue: tr('fc_revenue'), net_profit: tr('fc_net_profit'), expenses: tr('fc_expenses') }

  async function run() {
    if (!selectedId) return
    const qs = buildAnalysisQuery(fcQS, { lang, window: win, consolidate: false })
    if (qs === null) { setErr(tr('fc_custom_scope_hint')); return }
    setLoading(true); setErr(null)
    try {
      const r = await fetch(`/api/v1/analysis/${selectedId}/forecast?${qs}`,
                            { headers: getAuthHeaders() })
      if (!r.ok) { const t=await r.text(); setErr(t||r.statusText); return }
      const d = await r.json()
      setResult(d)
    } catch(e) { setErr(e.message) }
    finally { setLoading(false) }
  }

  const fc   = result?.data
  const sum  = fc?.summary || {}
  const sc   = (fc?.scenarios || {})[scenario] || {}
  const acts = (fc?.actuals || {})[metric]     || []
  const fpts = (sc[metric]  || []).map(p=>p.point)
  const fbnd = (sc[metric]  || [])
  const allP = [...(fc?.periods||[]), ...(fc?.future_periods||[])]

  // Max value for chart scaling
  const allVals = [...acts.filter(Boolean), ...fpts.filter(Boolean)]
  const chartMax = allVals.length ? Math.max(...allVals) * 1.12 : 1

  return (
    <div style={{display:'flex',flexDirection:'column',gap:14,maxWidth:960}}>

      {/* Controls */}
      <div style={{display:'flex',alignItems:'center',gap:10,background:BG.panel,
        border:`1px solid ${BG.border}`,borderRadius:12,padding:'12px 18px',flexWrap:'wrap'}}>
        <button onClick={run} disabled={loading||!selectedId}
          style={{padding:'8px 24px',borderRadius:9,border:'none',fontWeight:700,fontSize:12,
            background:loading?BG.border:C.accent,color:loading?C.text2:'#000',
            cursor:loading?'not-allowed':'pointer',fontFamily:'var(--font-display)',
            display:'flex',alignItems:'center',gap:6}}>
          {loading&&<div style={{width:10,height:10,border:'2px solid rgba(0,0,0,.2)',
            borderTopColor:'#000',borderRadius:'50%',animation:'spin .7s linear infinite'}}/>}
          {tr('fc_run')}
        </button>
        {err&&<span style={{fontSize:11,color:C.red}}>⚠ {err}</span>}
        {sum.risk_level&&(
          <div style={{marginLeft:'auto',display:'flex',alignItems:'center',gap:10}}>
            <span style={{fontSize:10,color:C.text2,textTransform:'uppercase'}}>{tr('fc_risk_level')}:</span>
            <span style={{fontWeight:700,fontSize:11,
              color:rlClr[sum.risk_level]||C.text3}}>
              {tr(`risk_level_${sum.risk_level}`)}
            </span>
            <span style={{fontSize:10,color:C.text2}}>
              {tr('fc_confidence')}: <b style={{color:C.text2}}>{formatPctForLang(sum.base_confidence, 0, lang)}</b>
            </span>
          </div>
        )}
      </div>

      {!result&&!loading&&(
        <div style={{display:'flex',flexDirection:'column',alignItems:'center',padding:'60px 0',gap:12}}>
          <span style={{fontSize:52,opacity:.1}}>📈</span>
          <div style={{fontSize:14,fontWeight:600,color:C.text2}}>{tr('fc_no_data')}</div>
        </div>
      )}

      {fc?.available===false&&(
        <div style={{padding:'14px 18px',background:`${C.amber}10`,border:`1px solid ${C.amber}`,
          borderRadius:9,fontSize:12,color:C.amber}}>⚠ {fc.reason}</div>
      )}

      {fc?.available&&(<>

        {/* Scenario + Metric selectors */}
        <div style={{display:'flex',gap:10,alignItems:'center',flexWrap:'wrap'}}>
          <div style={{display:'flex',gap:4,background:BG.elevated,borderRadius:8,padding:3}}>
            {['base','optimistic','risk'].map(s=>(
              <button key={s} onClick={()=>setScenario(s)}
                style={{padding:'5px 14px',borderRadius:6,border:'none',fontSize:11,fontWeight:700,
                  cursor:'pointer',transition:'all .15s',
                  background:scenario===s?scClr[s]:'transparent',
                  color:scenario===s?'#000':(scClr[s]||C.text3)}}>
                {tr(`fc_${s}`)}
              </button>
            ))}
          </div>
          <div style={{display:'flex',gap:4,background:BG.elevated,borderRadius:8,padding:3}}>
            {['revenue','net_profit','expenses'].map(m=>(
              <button key={m} onClick={()=>setMetric(m)}
                style={{padding:'5px 12px',borderRadius:6,border:'none',fontSize:10,fontWeight:700,
                  cursor:'pointer',transition:'all .15s',
                  background:metric===m?BG.panel:'transparent',
                  color:metric===m?C.text1:C.text3}}>
                {metricLabel[m]||m}
              </button>
            ))}
          </div>
        </div>

        {/* Chart */}
        <div style={{background:BG.panel,border:`1px solid ${BG.border}`,borderRadius:12,
          padding:'16px 18px'}}>
          <div style={{fontSize:11,fontWeight:700,color:C.text2,marginBottom:12,
            display:'flex',alignItems:'center',gap:8}}>
            <span style={{color:scClr[scenario]}}>{tr(`fc_${scenario}`)}</span>
            <span style={{color:C.text2}}>—</span>
            <span>{metricLabel[metric]}</span>
          </div>
          {/* SVG bar chart */}
          <svg viewBox={`0 0 ${allP.length*60+20} 180`} style={{width:'100%',height:180}}>
            {allP.map((p,i)=>{
              const isHist = i < acts.length
              const val    = isHist ? acts[i] : fpts[i-acts.length]
              const bnd    = !isHist ? fbnd[i-acts.length] : null
              const barH   = val!=null ? Math.max(4, (val/chartMax)*140) : 0
              const x      = i*60+10
              const barColor = isHist?C.text3:(scClr[scenario]||C.accent)
              return (
                <g key={p}>
                  {/* Band (forecast only) */}
                  {bnd&&bnd.high!=null&&bnd.low!=null&&(
                    <rect x={x+8} y={180-20-Math.max(4,(bnd.high/chartMax)*140)}
                      width={28} height={Math.max(2,(bnd.high-bnd.low)/chartMax*140)}
                      fill={`${scClr[scenario]}25`} rx={2}/>
                  )}
                  {/* Main bar */}
                  <rect x={x+8} y={180-20-barH} width={28} height={barH}
                    fill={barColor} rx={3} opacity={isHist?0.6:0.95}/>
                  {/* Value label */}
                  {val!=null&&<text x={x+22} y={180-20-barH-4} textAnchor="middle"
                    fontSize={8} fill={C.text2}>{formatCompactForLang(val, lang)}</text>}
                  {/* Period label */}
                  <text x={x+22} y={178} textAnchor="middle" fontSize={7.5}
                    fill={isHist?C.text3:scClr[scenario]}>{p.slice(2)}</text>
                  {/* Divider between actual and forecast */}
                  {i===acts.length-1&&(
                    <line x1={x+50} y1={0} x2={x+50} y2={160}
                      stroke={C.text3} strokeWidth={1} strokeDasharray="4 3" opacity={0.4}/>
                  )}
                </g>
              )
            })}
            {/* Legend */}
            <g>
              <rect x={10} y={4} width={10} height={6} fill={C.text2} rx={1} opacity={0.6}/>
              <text x={24} y={10} fontSize={8} fill={C.text2}>{tr('fc_historical')}</text>
              <rect x={80} y={4} width={10} height={6} fill={scClr[scenario]} rx={1}/>
              <text x={94} y={10} fontSize={8} fill={scClr[scenario]}>{tr('fc_projected')}</text>
            </g>
          </svg>
        </div>

        {/* Forecast table */}
        <div style={{background:BG.panel,border:`1px solid ${BG.border}`,borderRadius:12,
          overflow:'hidden'}}>
          <table style={{width:'100%',borderCollapse:'collapse',fontSize:11}}>
            <thead>
              <tr style={{background:BG.elevated}}>
                <th style={{padding:'8px 14px',textAlign:'start',fontWeight:700,
                  color:C.text2,fontSize:10,textTransform:'uppercase',letterSpacing:'.06em'}}>
                  {tr('fc_months_ahead')}
                </th>
                {['revenue','net_profit','expenses'].map(m=>(
                  <th key={m} style={{padding:'8px 14px',textAlign:'end',fontWeight:700,
                    color:C.text2,fontSize:10,textTransform:'uppercase',letterSpacing:'.06em'}}>
                    {metricLabel[m]}
                  </th>
                ))}
                <th style={{padding:'8px 14px',textAlign:'end',fontWeight:700,
                  color:C.text2,fontSize:10,textTransform:'uppercase',letterSpacing:'.06em'}}>
                  {tr('fc_confidence')}
                </th>
              </tr>
            </thead>
            <tbody>
              {(fc.future_periods||[]).map((p,i)=>(
                <tr key={p} style={{borderTop:`1px solid ${BG.border}`}}>
                  <td style={{padding:'9px 14px',color:scClr[scenario],fontWeight:700,
                    fontFamily:'var(--font-mono)',fontSize:12}}>{p}</td>
                  {['revenue','net_profit','expenses'].map(m=>{
                    const pt = ((sc[m]||[])[i]||{}).point
                    const lo = ((sc[m]||[])[i]||{}).low
                    const hi = ((sc[m]||[])[i]||{}).high
                    const isNeg = pt!=null && pt < 0
                    return (
                      <td key={m} style={{padding:'9px 14px',textAlign:'end',
                        fontFamily:'var(--font-mono)',color:isNeg?C.red:C.text1}}>
                        <div>{formatCompactForLang(pt, lang)}</div>
                        <div style={{fontSize:10,color:C.text2}}>
                          {formatCompactForLang(lo, lang)} – {formatCompactForLang(hi, lang)}
                        </div>
                      </td>
                    )
                  })}
                  <td style={{padding:'9px 14px',textAlign:'end',fontFamily:'var(--font-mono)',
                    fontSize:10,color:C.text2}}>
                    {(() => { const c = ((sc.revenue||[])[i]||{}).confidence; return c != null && c !== '' ? formatPctForLang(Number(c), 0, lang) : '—' })()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Insight box */}
        {sum.insight&&(
          <div style={{background:BG.panel,border:`1px solid ${BG.border}`,borderRadius:12,
            padding:'14px 18px',display:'flex',gap:12,alignItems:'flex-start'}}>
            <span style={{fontSize:20,flexShrink:0,opacity:.6}}>💡</span>
            <div>
              <div style={{fontSize:9,fontWeight:800,color:C.accent,textTransform:'uppercase',
                letterSpacing:'.07em',marginBottom:5}}>{tr('fc_insight')}</div>
              <div style={{fontSize:12,color:C.text2,lineHeight:1.7}}>
                <CmdServerText lang={lang} tr={tr}>{sum.insight}</CmdServerText>
              </div>
              <div style={{marginTop:8,display:'flex',gap:12,flexWrap:'wrap'}}>
                {sum.trend_mom_revenue!=null&&(
                  <span style={{fontSize:10,color:C.text2}}>
                    {tr('fc_revenue')} {tr('mom_label')}:{' '}
                    <b style={{color:sum.trend_mom_revenue>=0?C.green:C.red,
                      fontFamily:'var(--font-mono)'}}>
                      {formatSignedPctForLang(sum.trend_mom_revenue, 1, lang)}
                    </b>
                  </span>
                )}
                {sum.trend_mom_net_profit!=null&&(
                  <span style={{fontSize:10,color:C.text2}}>
                    {tr('fc_net_profit')} {tr('mom_label')}:{' '}
                    <b style={{color:sum.trend_mom_net_profit>=0?C.green:C.red,
                      fontFamily:'var(--font-mono)'}}>
                      {formatSignedPctForLang(sum.trend_mom_net_profit, 1, lang)}
                    </b>
                  </span>
                )}
              </div>
            </div>
          </div>
        )}
      </>)}
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  Phase 28 — Portfolio Panel
// ══════════════════════════════════════════════════════════════════════════════
function PortfolioPanel({tr, lang, companyId}) {
  const { toQueryString, window: win } = usePeriodScope()
  const [result,  setResult]  = useState(null)
  const [loading, setLoading] = useState(false)
  const [err,     setErr]     = useState(null)

  useEffect(() => {
    if (!companyId) return
    load()
  }, [companyId, lang, win, toQueryString])

  async function load() {
    setLoading(true); setErr(null)
    try {
      const qs = buildAnalysisQuery(toQueryString, { lang, window: win, consolidate: false })
      if (qs === null) { setErr(tr('err_scope_custom_incomplete')); setLoading(false); return }
      const r = await fetch(
        `/api/v1/companies/${companyId}/portfolio-intelligence?${qs}`,
        { headers: getAuthHeaders() }
      )
      if (!r.ok) { const t = await r.text(); setErr(t || r.statusText); return }
      const d = await r.json()
      setResult(d)
    } catch(e) { setErr(e.message) }
    finally { setLoading(false) }
  }

  const sum          = result?.portfolio_summary  || {}
  const contributions = result?.contributions      || []
  const insights     = result?.insights            || []
  const decisions    = result?.portfolio_decisions || []

  const ROLE_COLOR = {
    profit_driver:   C.green,
    growth_engine:   C.accent,
    stable:          C.text2,
    value_destroyer: C.red,
  }
  const SEV_COLOR = { critical: C.red, warning: C.amber, info: C.accent }
  const PRI_COLOR = { high: C.red, medium: C.amber, low: C.accent }
  const fmtV = (v) => (v == null ? '—' : formatCompactForLang(v, lang))

  if (!companyId) return (
    <div style={{padding:'40px',textAlign:'center',color:C.text2,fontSize:13}}>
      {tr('select_company')}
    </div>
  )

  if (loading) return (
    <div style={{padding:'60px',textAlign:'center',color:C.text2,fontSize:13}}>
      <div style={{width:20,height:20,border:'2px solid currentColor',borderTopColor:'transparent',
        borderRadius:'50%',animation:'spin .7s linear infinite',margin:'0 auto 10px'}}/>
      {tr('loading_portfolio_intelligence')}
    </div>
  )

  if (err) return (
    <div style={{padding:'18px',background:`${C.red}10`,border:`1px solid ${C.red}40`,
      borderRadius:9,fontSize:12,color:C.red}}>⚠ {err}</div>
  )

  if (!result) return (
    <div style={{display:'flex',flexDirection:'column',alignItems:'center',padding:'60px 0',gap:12}}>
      <span style={{fontSize:52,opacity:.1}}>📊</span>
      <div style={{fontSize:14,fontWeight:600,color:C.text2}}>{tr('port_no_data')}</div>
    </div>
  )

  return (
    <div style={{display:'flex',flexDirection:'column',gap:16,maxWidth:960}}>

      {/* ── Summary cards ── */}
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(150px,1fr))',gap:10}}>
        {[
          {label: tr('total_revenue'), val: fmtV(sum.total_revenue),  color: C.accent},
          {label: tr('total_profit'),  val: fmtV(sum.total_profit),   color: sum.total_profit < 0 ? C.red : C.green},
          {label: tr('portfolio_margin'), val: formatPctForLang(sum.portfolio_margin_pct, 1, lang), color: C.blue},
          {label: tr('branches'),      val: sum.branch_count ?? contributions.length, color: C.text2},
        ].map(({label,val,color}) => (
          <div key={label} style={{background:BG.panel,border:`1px solid ${BG.border}`,
            borderTop:`2px solid ${color}`,borderRadius:9,padding:'10px 14px'}}>
            <div style={{fontFamily:'var(--font-mono)',fontSize:20,fontWeight:800,color}}>{val}</div>
            <div style={{fontSize:10,color:C.text2,marginTop:3}}>{label}</div>
          </div>
        ))}
      </div>

      {/* ── Top/Bottom callouts ── */}
      {(sum.top_contributor || sum.biggest_drag) && (
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10}}>
          {sum.top_contributor && (
            <div style={{background:BG.panel,border:`1px solid ${C.green}30`,borderRadius:9,padding:'10px 14px'}}>
              <div style={{fontSize:9,fontWeight:800,color:C.green,textTransform:'uppercase',letterSpacing:'.07em',marginBottom:4}}>
                {tr('top_contributor')}
              </div>
              <div style={{fontSize:13,fontWeight:700,color:C.text}}>{sum.top_contributor.branch_name}</div>
              <div style={{fontSize:11,color:C.text2}}>{fmtV(sum.top_contributor.net_profit)} · {formatPctForLang(sum.top_contributor.profit_share_pct, 1, lang)}</div>
            </div>
          )}
          {sum.biggest_drag && (
            <div style={{background:BG.panel,border:`1px solid ${C.red}30`,borderRadius:9,padding:'10px 14px'}}>
              <div style={{fontSize:9,fontWeight:800,color:C.red,textTransform:'uppercase',letterSpacing:'.07em',marginBottom:4}}>
                {tr('biggest_drag')}
              </div>
              <div style={{fontSize:13,fontWeight:700,color:C.text}}>{sum.biggest_drag.branch_name}</div>
              <div style={{fontSize:11,color:C.text2}}>{fmtV(sum.biggest_drag.net_profit)} · {formatPctForLang(sum.biggest_drag.profit_share_pct, 1, lang)}</div>
            </div>
          )}
        </div>
      )}

      {/* ── Contribution table ── */}
      {contributions.length > 0 && (
        <div style={{background:BG.panel,border:`1px solid ${BG.border}`,borderRadius:12,overflow:'hidden'}}>
          <div style={{padding:'12px 16px',borderBottom:`1px solid ${BG.border}`,
            fontSize:11,fontWeight:700,color:C.text2,textTransform:'uppercase',letterSpacing:'.06em'}}>
            {tr('branch_contributions')}
          </div>
          <div style={{overflowX:'auto'}}>
            <table style={{width:'100%',borderCollapse:'collapse',fontSize:12}}>
              <thead>
                <tr style={{background:BG.elevated}}>
                  {['#', tr('branch'), tr('role'), tr('rev_pct'), tr('np_pct'),
                    tr('net_margin'), tr('expense_ratio_short'),
                    tr('p_rank'), tr('c_rank'), tr('g_rank')].map(h => (
                    <th key={h} style={{padding:'8px 12px',textAlign:'left',fontWeight:700,
                      color:C.text2,fontSize:10,whiteSpace:'nowrap'}}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {contributions.map((b,i) => {
                  const rc = ROLE_COLOR[b.role] || C.text2
                  return (
                    <tr key={b.branch_id} style={{borderTop:`1px solid ${BG.border}`,
                      background: i%2===0 ? 'transparent' : `${BG.elevated}60`}}>
                      <td style={{padding:'8px 12px',color:C.text2,fontSize:10}}>{b.overall_portfolio_rank}</td>
                      <td style={{padding:'8px 12px',fontWeight:600,color:C.text}}>{b.branch_name}</td>
                      <td style={{padding:'8px 12px'}}>
                        <span style={{fontSize:9,fontWeight:700,color:rc,
                          background:`${rc}15`,padding:'2px 7px',borderRadius:10}}>
                          {b.role_label || b.role}
                        </span>
                      </td>
                      <td style={{padding:'8px 12px',fontFamily:'var(--font-mono)',fontSize:11,color:C.text}}>{formatPctForLang(b.revenue_share_pct, 1, lang)}</td>
                      <td style={{padding:'8px 12px',fontFamily:'var(--font-mono)',fontSize:11,
                        color: b.profit_share_pct < 0 ? C.red : C.text}}>{formatPctForLang(b.profit_share_pct, 1, lang)}</td>
                      <td style={{padding:'8px 12px',fontFamily:'var(--font-mono)',fontSize:11,
                        color: (b.net_margin_pct||0) < 0 ? C.red : C.green}}>{formatPctForLang(b.net_margin_pct, 1, lang)}</td>
                      <td style={{padding:'8px 12px',fontFamily:'var(--font-mono)',fontSize:11,color:C.text}}>{formatPctForLang(b.expense_ratio, 1, lang)}</td>
                      <td style={{padding:'8px 12px',fontFamily:'var(--font-mono)',fontSize:11,color:C.text2,textAlign:'center'}}>{b.profitability_rank}</td>
                      <td style={{padding:'8px 12px',fontFamily:'var(--font-mono)',fontSize:11,color:C.text2,textAlign:'center'}}>{b.cost_efficiency_rank}</td>
                      <td style={{padding:'8px 12px',fontFamily:'var(--font-mono)',fontSize:11,color:C.text2,textAlign:'center'}}>{b.growth_quality_rank}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Portfolio insights ── */}
      {insights.length > 0 && (
        <div style={{display:'flex',flexDirection:'column',gap:8}}>
          <div style={{fontSize:11,fontWeight:700,color:C.text2,textTransform:'uppercase',
            letterSpacing:'.06em'}}>{tr('insights')}</div>
          {insights.map((ins,i) => {
            const sc = SEV_COLOR[ins.severity] || C.text2
            return (
              <div key={i} style={{background:BG.panel,border:`1px solid ${sc}25`,
                borderLeft:`3px solid ${sc}`,borderRadius:9,padding:'12px 16px'}}>
                <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:6}}>
                  <span style={{fontSize:9,fontWeight:800,color:sc,textTransform:'uppercase',
                    letterSpacing:'.07em'}}>{tr(`severity_${ins.severity}`)||ins.severity}</span>
                  {ins.target_branch && <span style={{fontSize:9,color:C.text2}}>→ {contributions.find(c=>c.branch_id===ins.target_branch)?.branch_name || ins.target_branch}</span>}
                </div>
                <div style={{fontSize:12,fontWeight:600,color:C.text,marginBottom:4}}>{ins.what_happened}</div>
                <div style={{fontSize:11,color:C.text2,marginBottom:4}}>{ins.why_it_matters}</div>
                <div style={{fontSize:11,color:C.accent,fontStyle:'italic'}}>{ins.what_to_do}</div>
              </div>
            )
          })}
        </div>
      )}

      {/* ── Portfolio decisions ── */}
      {decisions.length > 0 && (
        <div style={{display:'flex',flexDirection:'column',gap:8}}>
          <div style={{fontSize:11,fontWeight:700,color:C.text2,textTransform:'uppercase',
            letterSpacing:'.06em'}}>{tr('portfolio_decisions')}</div>
          {decisions.map((d,i) => {
            const pc = PRI_COLOR[d.priority] || C.text2
            return (
              <div key={i} style={{background:BG.panel,border:`1px solid ${BG.border}`,
                borderRadius:9,padding:'12px 16px',display:'flex',gap:12}}>
                <div style={{flexShrink:0,marginTop:2}}>
                  <span style={{fontSize:9,fontWeight:800,color:pc,textTransform:'uppercase',
                    background:`${pc}15`,padding:'2px 7px',borderRadius:10}}>{tr(`priority_${d.priority}`)||d.priority}</span>
                </div>
                <div style={{flex:1}}>
                  <div style={{fontSize:12,fontWeight:600,color:C.text,marginBottom:4}}>{d.title}</div>
                  <div style={{fontSize:11,color:C.text2,marginBottom:3}}>{d.reason}</div>
                  <div style={{fontSize:11,color:C.accent,fontStyle:'italic'}}>{d.expected_impact}</div>
                  {d.target_branch && <div style={{fontSize:10,color:C.text2,marginTop:4}}>
                    {tr('target')}: <strong>{d.target_branch}</strong>
                    {d.owner_scope && <> · {d.owner_scope}</>}
                  </div>}
                </div>
              </div>
            )
          })}
        </div>
      )}

    </div>
  )
}


// helper for outlier display
function _r2String(v) {
  if (v==null) return '—'
  return Math.abs(v) >= 100 ? Math.round(v).toString() : Number(v).toFixed(1)
}

// ══════════════════════════════════════════════════════════════════════════════
//  MAIN DASHBOARD
// ══════════════════════════════════════════════════════════════════════════════
export default function Dashboard() {
  const { tr: trCtx, lang } = useLang()
  const tr = useCallback((key, params) => {
    if (params != null && typeof params === 'object') return strictTParams(trCtx, lang, key, params)
    return strictT(trCtx, lang, key)
  }, [trCtx, lang])
  const { selectedId, selectedCompany, createCompany, reloadCompanies } = useCompany()

  const tSig = useTSignal()
  const tSub = useTSignalSub()
  const tFc  = useTForecast()

  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState(null)
  const [fcData,  setFcData]  = useState(null)   // Phase 6.4: forecast
  // window is now shared via PeriodScopeContext — no local state
  const [tab,     setTab]     = useState('overview')
  const [modal,   setModal]   = useState(null)   // kpi drill-down
  const [consolidate, setConsolidate] = useState(false)  // data source toggle
  // Phase 22 — universal time-scope (from shared context)
  const { params: ps, update: psUpdate, toQueryString: psScopeQS, setResolved: psSetResolved, getActiveLabel: psActiveLabel, isIncompleteCustom: psIncomplete, window: win, setWindow: setWin } = usePeriodScope()
  const ctxLabel = () => kpiContextLabel({ window: win, ps, latestPeriod: meta.all_periods?.at(-1) || '', lang, tr })

  const load = useCallback(() => {
    if (!selectedId) return
    // Guard: incomplete custom scope — do not send invalid request
    if (psIncomplete()) return
    const qs = buildAnalysisQuery(psScopeQS, { lang, window: win, consolidate })
    if (qs === null) return   // toQueryString signals incomplete scope
    setLoading(true); setError(null)
    fetch(`${API}/analysis/${selectedId}/executive?${qs}`, { headers: getAuthHeaders() })
      .then(r => {
        if (!r.ok) return r.text().then(t => { throw new Error(t || r.statusText) })
        return r.json()
      })
      .then(json => {
        if (json.detail) { setError(json.detail) }
        else { setData(json); psSetResolved(json.meta?.scope || null) }
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
    // Phase 6.4: fetch forecast alongside main load — read-only, no calc
    const fqs = buildAnalysisQuery(psScopeQS, { lang, window: win, consolidate: false })
    if (fqs !== null) {
      fetch(`${API}/analysis/${selectedId}/forecast?${fqs}`, { headers: getAuthHeaders() })
        .then(r => r.ok ? r.json() : null)
        .then(j => { if (j?.data) setFcData(j.data) })
        .catch(() => {})  // silent — forecast is optional
    }
  // psScopeQS and psSetResolved are stable (refs-based) — safe as deps
  }, [selectedId, lang, win, consolidate, psScopeQS, psSetResolved, psIncomplete])

  // Only re-run when selectedId or window changes — NOT on every scope object change.
  // Scope is applied via the stable psScopeQS ref; no extra deps needed.
  useEffect(() => { load() }, [selectedId, win, consolidate])

  const { loadingCompanies, companies } = useCompany()
  const [firstCoName, setFirstCoName] = useState('')
  const [firstCoErr, setFirstCoErr] = useState(null)
  const [firstCoLoading, setFirstCoLoading] = useState(false)

  if (!selectedId) return (
    <div style={{display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',height:'70vh',gap:12,background:BG.page}}>
      <span style={{fontSize:52,opacity:.2}}>🏢</span>
      {loadingCompanies
        ? <div style={{width:18,height:18,border:`2px solid ${BG.border}`,borderTopColor:C.accent,borderRadius:'50%',animation:'spin .8s linear infinite'}} />
        : companies.length === 0
          ? <>
              <div style={{fontSize:16,color:C.text2,fontWeight:600}}>{tr('gen_no_companies')}</div>
              <div style={{fontSize:13,color:C.text2}}>{tr('gen_create_hint')}</div>
              <div style={{display:'flex',gap:10,alignItems:'center',marginTop:8}}>
                <input
                  value={firstCoName}
                  onChange={e => { setFirstCoName(e.target.value); setFirstCoErr(null) }}
                  placeholder={tr('company_name')}
                  style={{background:'var(--bg-elevated)',border:'1px solid var(--border)',borderRadius:10,
                    padding:'10px 12px',fontSize:13,color:'var(--text-primary)',minWidth:220}}
                />
                <button
                  disabled={firstCoLoading}
                  onClick={async () => {
                    if (firstCoLoading) return
                    setFirstCoLoading(true); setFirstCoErr(null)
                    const res = await createCompany({ name: firstCoName })
                    if (!res.ok) setFirstCoErr(res.error || tr('company_create_failed'))
                    else { setFirstCoName(''); reloadCompanies() }
                    setFirstCoLoading(false)
                  }}
                  style={{background:'var(--accent)',color:'#000',border:'none',borderRadius:10,padding:'10px 14px',
                    fontSize:13,fontWeight:800,cursor:firstCoLoading?'not-allowed':'pointer',opacity:firstCoLoading?.7:1}}
                >
                  {firstCoLoading ? tr('creating') : tr('create_company')}
                </button>
              </div>
              {firstCoErr && (
                <div style={{marginTop:8,fontSize:12,color:'var(--red)'}}>{firstCoErr}</div>
              )}
            </>
          : <>
              <div style={{fontSize:16,color:C.text2,fontWeight:600}}>{tr('gen_select_company')}</div>
              <div style={{fontSize:13,color:C.text2}}>{tr('gen_create_hint')}</div>
            </>
      }
    </div>
  )

  // ── Canonical destructure — single source of truth ──────────────────────
  const d       = data?.data  || {}
  const meta    = data?.meta  || {}

  const kpis    = d.kpi_block?.kpis    || {}
  const series  = d.kpi_block?.series  || {}
  const periods = d.kpi_block?.periods || meta.periods || []
  const intel   = d.intelligence       || {}
  // annual_layer — full-year strips
  const al      = d.annual_layer       ?? {}
  const alYtd   = al?.ytd              ?? {}
  const alYtdPr = al?.ytd_prior        ?? null
  const alComp  = al?.comparisons      ?? {}
  const alFY    = al?.full_years       ?? []
  const ytdVsPr = alComp?.ytd_vs_prior_ytd ?? null
  const ytdChg  = ytdVsPr?.changes         ?? {}
  // health from intelligence — single source
  const health  = d.health_score_v2 ?? null
  const healthC = health!=null?(health>=80?C.green:health>=60?C.amber:C.red):C.text3
  const insCount= (d.decisions||[]).length

  // Phase 2.1: Executive-first tab order
  const tabs=[
    {key:'overview',      label:tr('tab_overview')},
    {key:'profitability', label:tr('tab_profitability')},
    {key:'forecast',      label:tr('tab_forecast')},
    {key:'root_causes',   label:tr('tab_root_causes')},
    {key:'decisions_v2',  label:tr('tab_decisions_v2')},
    {key:'expenses',      label:tr('tab_expenses')},
    {key:'variance',      label:tr('tab_variance')},
    {key:'decisions',     label:tr('tab_decisions'), badge:insCount||null},
    {key:'whatif',        label:tr('tab_whatif')},
    {key:'narrative',     label:tr('tab_narrative')},
    {key:'report',        label:tr('tab_report')},
    {key:'intelligence',  label:tr('tab_intelligence')},
    {key:'portfolio',     label:tr('tab_portfolio')},
  ]

  return (
    <div style={{padding:'18px 26px',display:'flex',flexDirection:'column',gap:14,minHeight:'calc(100vh - 62px)',background:BG.page}}>

      {/* Drill-down modal */}
      <DrillModal kpiType={modal} data={data} tr={tr} onClose={()=>setModal(null)} ctxLabel={ctxLabel} lang={lang}/>

      {/* Scope + Period controls */}
      <div style={{display:'flex',flexDirection:'column',gap:8}}>
        <UniversalScopeSelector tr={tr} lang={lang} ps={ps} psUpdate={psUpdate} onApply={load} activeLabel={psActiveLabel()} allPeriods={meta.all_periods||[]}/>
        <div style={{display:'flex',alignItems:'center',gap:12,flexWrap:'wrap'}}>
          <PeriodSelector window={win} setWindow={setWin} disabled={loading}/>

          {/* ── Data Source Toggle ── */}
          <div style={{display:'flex',alignItems:'center',gap:0,background:BG.card,
            border:`1px solid ${BG.border}`,borderRadius:8,overflow:'hidden',flexShrink:0}}>
            {[{v:false,l:tr('company_uploads')},{v:true,l:tr('branch_consolidation')}].map(opt=>(
              <button key={String(opt.v)} onClick={()=>{setConsolidate(opt.v);setData(null)}}
                style={{padding:'5px 12px',fontSize:11,fontWeight:600,border:'none',cursor:'pointer',
                  background: consolidate===opt.v ? C.accent : 'transparent',
                  color:      consolidate===opt.v ? '#000' : C.text2,
                  transition: 'all .15s', whiteSpace:'nowrap'}}>
                {opt.l}
              </button>
            ))}
          </div>

          {loading&&<div style={{width:14,height:14,border:`2px solid ${BG.border}`,borderTopColor:C.accent,borderRadius:'50%',animation:'spin .8s linear infinite'}}/>}
          {intel.latest_period&&(
            <div style={{marginLeft:'auto',display:'flex',gap:10,alignItems:'center'}}>
              <span style={{fontSize:10,color:C.text2,fontFamily:'monospace',direction:'ltr'}}>
                {tr('data_window')} {intel.periods_in_window} {tr('of_total')} {intel.full_year?'12':data?.total_periods||'?'} {tr('total_periods_lbl')}
              </span>
              {!intel.yoy_available&&<Chip label={tr('no_yoy_chip')} color={C.amber}/>}
            </div>
          )}
        </div>
      </div>

      {/* Data Source Banner */}
      {data && (
        <div style={{display:'flex',alignItems:'center',gap:8,padding:'6px 12px',
          borderRadius:8,fontSize:11,
          background: consolidate ? 'rgba(0,212,170,.07)' : 'rgba(59,158,255,.07)',
          border: `1px solid ${consolidate ? C.accent+'44' : C.blue+'44'}`,
        }}>
          <span style={{fontWeight:700,color: consolidate ? C.accent : C.blue}}>
            {consolidate ? '⊞' : '⊟'}
          </span>
          <span style={{color: consolidate ? C.accent : C.blue, fontWeight:600}}>
            {tr('data_source')}:
          </span>
          <span style={{color:C.text2}}>
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

      {error&&(
        <div style={{padding:'12px 16px',background:`${C.red}12`,border:`1px solid ${C.red}`,borderRadius:9,fontSize:12,color:C.red,display:'flex',alignItems:'center',gap:12,flexWrap:'wrap'}}>
          <span style={{flex:1}}>⚠ {error}</span>
          {(error.includes('upload') || error.includes('Upload') || error.includes('No successful')) && (
            <a href="/upload" style={{padding:'5px 14px',borderRadius:7,background:'var(--accent)',color:'#000',fontWeight:700,fontSize:11,textDecoration:'none',flexShrink:0}}>
              {tr('nav_upload')}
            </a>
          )}
        </div>
      )}

      {/* ── Phase 2: Executive Layout ──
           Order: Health → Actions → KPI row → Tabs
      ── */}
      {data&&<DataQualityBanner validation={meta.pipeline_validation} lang={lang} tr={tr}/>}

      {/* 1. HEALTH BLOCK — dominant hero */}
      {data&&<HealthBlock score={health} data={data} tr={tr} lang={lang}/>}

      {/* 2. ACTION STRIP — top 3 decisions */}
      {data&&<ActionStrip data={data} tr={tr} lang={lang}/>}

      {/* 3. KPI ROW — 5 key metrics */}
      {data&&(
        <div style={{display:'grid',gridTemplateColumns:'repeat(5,1fr)',gap:10}}>
          <KpiCard tr={tr} lang={lang} momWord={tr('mom_label')} yoyWord={tr('yoy_label')} labelKey="kpi_total_revenue"  kpiType="revenue"    value={formatCompactForLang(kpis.revenue?.value, lang)} fullValue={formatFullForLang(kpis.revenue?.value, lang)}    mom={kpis.revenue?.mom_pct}    yoy={kpis.revenue?.yoy_pct}    color={C.accent} icon="📈" spark={series.revenue?.slice(-8)}    onClick={()=>setModal('revenue')}   insight={kpiInsight('revenue',data,lang,tr)}    cause={kpiCause('revenue',data,tr,lang)}    forecast={kpiForecast('revenue', fcData, tr, (v) => formatCompactForLang(v, lang), lang)}/>
          <KpiCard tr={tr} lang={lang} momWord={tr('mom_label')} yoyWord={tr('yoy_label')} labelKey="kpi_total_expenses" kpiType="expenses"   value={formatCompactForLang(kpis.expenses?.value, lang)} fullValue={formatFullForLang(kpis.expenses?.value, lang)}   mom={kpis.expenses?.mom_pct}   yoy={kpis.expenses?.yoy_pct}   color={C.red}    icon="📉" spark={series.expenses?.slice(-8)}   onClick={()=>setModal('expenses')}  insight={kpiInsight('expenses',data,lang,tr)}   cause={kpiCause('expenses',data,tr,lang)}/>
          <KpiCard tr={tr} lang={lang} momWord={tr('mom_label')} yoyWord={tr('yoy_label')} labelKey="kpi_net_profit"     kpiType="net_profit" value={formatCompactForLang(kpis.net_profit?.value, lang)} fullValue={formatFullForLang(kpis.net_profit?.value, lang)} mom={kpis.net_profit?.mom_pct} yoy={kpis.net_profit?.yoy_pct} color={C.green}  icon="💰" spark={series.net_profit?.slice(-8)} onClick={()=>setModal('net_profit')} insight={kpiInsight('net_profit',data,lang,tr)} cause={kpiCause('net_profit',data,tr,lang)} forecast={kpiForecast('net_profit', fcData, tr, (v) => formatCompactForLang(v, lang), lang)}/>
          <KpiCard tr={tr} lang={lang} momWord={tr('mom_label')} yoyWord={tr('yoy_label')} labelKey="kpi_net_margin"     kpiType="net_margin" value={formatPctForLang(kpis.net_margin?.value, 1, lang)} mom={kpis.net_margin?.mom_pct}                                 color={C.violet} icon="%"  onClick={()=>setModal('net_margin')} insight={kpiInsight('net_margin',data,lang,tr)} cause={kpiCause('net_margin',data,tr,lang)}/>
          <KpiCard tr={tr} lang={lang} momWord={tr('mom_label')} yoyWord={tr('yoy_label')} labelKey="cashflow_operating" kpiType="cashflow"   value={formatCompactForLang(d.cashflow?.operating_cashflow, lang)} fullValue={formatFullForLang(d.cashflow?.operating_cashflow, lang)} mom={d.cashflow?.operating_cashflow_mom} color={C.amber} icon="💧" onClick={()=>setModal('cashflow')} insight={kpiInsight('cashflow',data,lang,tr)} cause={kpiCause('cashflow',data,tr,lang)} sub={d.cashflow?.reliability==='estimated'?tr('label_estimated_short'):null}/>
        </div>
      )}

      {/* 4. AI INSIGHT — single most important signal */}
      {data&&<AIInsightBlock data={data} lang={lang} tr={tr}/>}

      {/* Annual Layer — YTD summary + full years + gap warning */}
      {data&&al?.ytd&&(
        <div style={{display:'flex',flexDirection:'column',gap:8}}>
          {/* Gap warning */}
          {alYtd?.has_gaps&&(
            <div style={{display:'flex',alignItems:'center',gap:8,padding:'8px 14px',
              background:`${C.amber}0f`,border:`1px solid ${C.amber}`,borderRadius:8}}>
              <span style={{fontSize:12}}>⚠</span>
              <span style={{fontSize:11,color:C.amber,fontWeight:600}}>
                {(alYtd?.missing_count??0)>1
                  ? tr('al_ytd_missing_warn_p').replace('{year}',alYtd?.year||'').replace('{n}',alYtd?.missing_count??'')
                  : tr('al_ytd_missing_warn').replace('{year}',alYtd?.year||'').replace('{n}',alYtd?.missing_count??'')
                }
              </span>
            </div>
          )}
          {/* FY comparison warning */}
          {alComp?.full_year_current_vs_prior&&!alComp?.full_year_current_vs_prior?.comparable&&(
            <div style={{display:'flex',alignItems:'center',gap:8,padding:'8px 14px',
              background:`${C.blue}0f`,border:`1px solid ${C.blue}40`,borderRadius:8}}>
              <span style={{fontSize:11,color:C.blue}}>{tr('al_fy_partial_warn').replace('{year}',alComp?.full_year_current_vs_prior?.current_year||'').replace('{n}',alComp?.full_year_current_vs_prior?.month_count||'')}</span>
            </div>
          )}
          {/* YTD block */}
          <div style={{background:BG.panel,border:`1px solid ${BG.border}`,borderRadius:12,padding:'14px 18px'}}>
            <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:12}}>
              <span style={{fontSize:11,fontWeight:700,color:C.text2,textTransform:'uppercase',letterSpacing:'.06em'}}>
                {tr('al_ytd_label')} {alYtd?.year}
              </span>
              <span style={{fontSize:10,color:C.text2,fontFamily:'monospace'}}>
                {alYtd?.month_count??0} {(alYtd?.month_count??0)!==1?tr('al_ytd_months_plural'):tr('al_ytd_months')}
                {alYtd?.has_gaps?` · ${tr('al_ytd_gaps_badge')}`:''}
              </span>
              {ytdVsPr&&<span style={{marginLeft:'auto',fontSize:10,color:C.text2}}>
                {tr('al_vs_prior_period').replace('{year}',alYtdPr?.year||'')}
              </span>}
            </div>
            <div style={{display:'flex',gap:20,flexWrap:'wrap'}}>
              {[
                {key:'revenue',    label:tr('al_kpi_revenue'),   val:alYtd?.revenue??null,    chg:ytdChg?.revenue??null,    color:C.accent},
                {key:'net_profit', label:tr('al_kpi_net_profit'),val:alYtd?.net_profit??null,  chg:ytdChg?.net_profit??null,  color:(alYtd?.net_profit??0)>=0?C.green:C.red},
                {key:'margin',     label:tr('al_kpi_margin'),     val:alYtd?.net_margin_pct!=null?formatPctForLang(alYtd.net_margin_pct, 1, lang):null,
                                    chg:ytdChg?.net_margin_pct??null, color:C.violet},
              ].map(({key,label,val,chg,color})=>(
                <div key={key} style={{minWidth:120}}>
                  <div style={{fontSize:10,color:C.text2,textTransform:'uppercase',letterSpacing:'.05em',marginBottom:3}}>{label}</div>
                  <div style={{fontFamily:'var(--font-mono)',fontSize:15,fontWeight:700,color,direction:'ltr'}}>
                    {key==='margin'?val:(val!=null?formatCompactForLang(val, lang):'—')}
                  </div>
                  {chg!=null&&<div style={{fontSize:9,fontWeight:700,color:chg>=0?C.green:C.red,marginTop:2}}>
                    {chg>=0?'▲':'▼'} {formatPctForLang(Math.abs(chg), 1, lang)} {tr('al_vs_prior_year')}
                  </div>}
                </div>
              ))}
            </div>
          </div>
          {/* Full years strip */}
          {alFY.length>0&&(
            <div style={{display:'flex',gap:8,overflowX:'auto',paddingBottom:2}}>
              {alFY.map(fy=>(
                <div key={fy.year} style={{background:BG.panel,border:`1px solid ${BG.border}`,borderRadius:10,
                  padding:'10px 14px',minWidth:160,flexShrink:0}}>
                  <div style={{display:'flex',alignItems:'center',gap:6,marginBottom:8}}>
                    <span style={{fontFamily:'var(--font-mono)',fontSize:12,fontWeight:700,color:C.text1}}>{fy.year}</span>
                    {!fy.complete&&<span style={{fontSize:8,fontWeight:700,padding:'1px 6px',borderRadius:10,
                      background:`${C.amber}20`,color:C.amber}}>{tr('al_fy_partial_badge')}</span>}
                    {fy.has_gaps&&<span style={{fontSize:8,padding:'1px 5px',borderRadius:10,
                      background:`${C.red}15`,color:C.red}}>{tr('al_fy_gaps_badge')}</span>}
                  </div>
                  <div style={{display:'flex',flexDirection:'column',gap:3}}>
                    <div style={{display:'flex',justifyContent:'space-between'}}>
                      <span style={{fontSize:10,color:C.text2}}>{tr('al_kpi_revenue')}</span>
                      <span style={{fontFamily:'var(--font-mono)',fontSize:11,fontWeight:600,color:C.accent,direction:'ltr'}}>{formatCompactForLang(fy.revenue, lang)}</span>
                    </div>
                    <div style={{display:'flex',justifyContent:'space-between'}}>
                      <span style={{fontSize:10,color:C.text2}}>{tr('al_kpi_net_profit')}</span>
                      <span style={{fontFamily:'var(--font-mono)',fontSize:11,fontWeight:600,color:fy.net_profit>=0?C.green:C.red,direction:'ltr'}}>{formatCompactForLang(fy.net_profit, lang)}</span>
                    </div>
                    {fy.net_margin_pct!=null&&<div style={{display:'flex',justifyContent:'space-between'}}>
                      <span style={{fontSize:10,color:C.text2}}>{tr('al_kpi_margin')}</span>
                      <span style={{fontFamily:'var(--font-mono)',fontSize:11,fontWeight:600,color:C.violet}}>{formatPctForLang(fy.net_margin_pct, 1, lang)}</span>
                    </div>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tabs */}
      {data&&(
        <>
          <TabNav tabs={tabs} active={tab} onChange={setTab}/>
          {tab==='overview'      && <OverviewTab      data={data} tr={tr} lang={lang} onKpiClick={kpiType=>setModal(kpiType)}/>}
          {tab==='expenses'      && <ExpenseTab       data={data} tr={tr} lang={lang}/>}
          {tab==='variance'      && <VarianceTab      data={data} tr={tr} lang={lang}/>}
          {tab==='profitability' && <ProfitabilityTab data={data} tr={tr} ctxLabel={ctxLabel} lang={lang}/>}
          {tab==='decisions'     && <DecisionsTab     data={data} tSig={tSig} tSub={tSub} tr={tr} selectedId={selectedId} lang={lang}/>}
          {tab==='whatif'        && <WhatIfPanel      data={data} tr={tr} selectedId={selectedId}/>}
          {tab==='narrative'     && <NarrativePanel   tr={tr} selectedId={selectedId} lang={lang}/>}
          {tab==='report'        && <ManagementReportPanel tr={tr} selectedId={selectedId} lang={lang}/>}
          {tab==='intelligence'  && <FinIntelPanel         tr={tr} selectedId={selectedId} lang={lang} data={data}/>}
          {tab==='decisions_v2'  && <DecisionsPanelV2     tr={tr} selectedId={selectedId} lang={lang}/>}
          {tab==='root_causes'   && <RootCausesPanel      tr={tr} selectedId={selectedId} lang={lang}/>}
          {tab==='forecast'      && <ForecastPanel        tr={tr} selectedId={selectedId} lang={lang}/>}
          {tab==='portfolio'     && <PortfolioPanel       tr={tr} lang={lang} companyId={selectedId}/>}
        </>
      )}

      {!data&&!loading&&!error&&(
        <div style={{display:'flex',flexDirection:'column',alignItems:'center',padding:'80px 60px',gap:16}}>
          <span style={{fontSize:48,opacity:.18}}>📊</span>
          <div style={{fontSize:15,color:C.text1,fontWeight:700}}>{tr('gen_upload_prompt')}</div>
          <div style={{fontSize:12,color:C.text2,textAlign:'center',maxWidth:340}}>{tr('upload_tb_hint')}</div>
          <a href="/upload" style={{
            marginTop:4, padding:'10px 24px', borderRadius:9, textDecoration:'none',
            background:'var(--accent)', color:'#000', fontWeight:700, fontSize:13,
          }}>{tr('nav_upload')}</a>
        </div>
      )}
    </div>
  )
}
