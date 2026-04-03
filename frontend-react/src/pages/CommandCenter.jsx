/**
 * CommandCenter.jsx — Command Center orchestrator (state, fetch, drill, chrome).
 * Main body: CSS grid via CommandCenterDashboardGrid — row1 narrative|health, row2 KPIs×4,
 * row3 signals|branch, row4 expense|decisions, row5 secondary.
 */
import { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLang }        from '../context/LangContext.jsx'
import { useCompany }     from '../context/CompanyContext.jsx'
import { usePeriodScope } from '../context/PeriodScopeContext.jsx'
import { kpiContextLabel } from '../utils/kpiContext.js'
import { formatCompact, formatFull } from '../utils/numberFormat.js'
import { buildAnalysisQuery } from '../utils/buildAnalysisQuery.js'
import { buildExecutiveNarrative } from '../utils/buildExecutiveNarrative.js'
import { analysisTabFromDrill } from '../utils/commandCenterDrill.js'
import { strictT, looksLikeRawI18nKey } from '../utils/strictI18n.js'
import PeriodSelector from '../components/PeriodSelector.jsx'
import UniversalScopeSelector from '../components/UniversalScopeSelector.jsx'
import ExecutiveNarrativeStrip from '../components/ExecutiveNarrativeStrip.jsx'
import {
  KeySignalsSection,
  BranchIntelligenceSection,
  DecisionsSection,
  keySignalsShowsInefficientBranch,
} from '../components/CommandCenterUnifiedSections.jsx'
import ExpenseInsightsSection from '../components/ExpenseInsightsSection.jsx'
import CommandCenterDashboardGrid from '../components/CommandCenterDashboardGrid.jsx'

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
const fmtP = v => (v == null || !Number.isFinite(Number(v)) ? '' : `${Number(v).toFixed(1)}%`)

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
        {has_errors ? strictT(tr, lang, 'dq_warning_title') : strictT(tr, lang, 'dq_notice_title')}
      </span>
      {warnings.map((w,i)=>(
        <span key={i} style={{fontSize:9,color:'rgba(255,255,255,0.5)'}}>· {strictT(tr, lang, `dq_${w.code}`)}</span>
      ))}
    </div>
  )
}

/** Level 1 — health ring + identity + narrative hooks (no KPIs). */
function HealthScorePanel({
  tr,
  lang,
  health,
  status,
  companyName,
  period,
  loading,
  onRefresh,
  periodCount,
  scopeLabel,
  healthHeadline,
  actionPrefix,
  actionLine,
  onDrillAnalysis,
}) {
  const hc = stC[status] || T.text2
  const circ = 2 * Math.PI * 30
  const h = health != null && Number.isFinite(Number(health)) ? Number(health) : null
  const dash = h != null ? (Math.max(0, Math.min(100, h)) / 100) * circ : 0
  const healthLabel = strictT(tr, lang, 'cmd_health_score')
  const snapSub = strictT(tr, lang, 'cmd_health_kpi_sub')
  const stSimple = tr(`status_${status}_simple`)
  const stFull = tr(`status_${status}`)
  const statusUi =
    stSimple && stSimple !== `status_${status}_simple` && !looksLikeRawI18nKey(stSimple)
      ? stSimple
      : stFull && stFull !== `status_${status}` && !looksLikeRawI18nKey(stFull)
        ? stFull
        : strictT(tr, lang, `status_${status}_simple`)
  const actionLbl = actionPrefix || strictT(tr, lang, 'cmd_narr_action_label')

  return (
    <div
      className="cmd-level-1"
      style={{
        background: 'linear-gradient(165deg, rgba(17,24,39,0.99) 0%, rgba(15,23,42,1) 100%)',
        border: '1px solid rgba(0,212,170,0.22)',
        borderRadius: 14,
        boxShadow: '0 0 0 1px rgba(0,212,170,0.12), 0 18px 52px rgba(0,0,0,0.48), 0 0 100px -24px rgba(0,212,170,0.14)',
        padding: '14px 16px 14px',
        minHeight: 0,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10, marginBottom: 10 }}>
        <div>
          <div
            style={{
              fontSize: 11,
              fontWeight: 800,
              color: T.accent,
              letterSpacing: '.08em',
              textTransform: 'uppercase',
            }}
          >
            {healthLabel}
          </div>
          <div style={{ fontSize: 10, color: T.text3, marginTop: 4, lineHeight: 1.4 }}>{snapSub}</div>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          style={{
            flexShrink: 0,
            width: 36,
            height: 36,
            borderRadius: 10,
            border: `1px solid ${T.border}`,
            background: T.card,
            color: T.text2,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 15,
          }}
        >
          {loading ? (
            <div
              style={{
                width: 14,
                height: 14,
                border: `2px solid ${T.border}`,
                borderTopColor: T.accent,
                borderRadius: '50%',
                animation: 'spin .7s linear infinite',
              }}
            />
          ) : (
            '↻'
          )}
        </button>
      </div>

      <div
        role={onDrillAnalysis ? 'button' : undefined}
        tabIndex={onDrillAnalysis ? 0 : undefined}
        onClick={onDrillAnalysis || undefined}
        onKeyDown={
          onDrillAnalysis
            ? (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onDrillAnalysis()
                }
              }
            : undefined
        }
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 14,
          cursor: onDrillAnalysis ? 'pointer' : undefined,
          borderRadius: onDrillAnalysis ? 12 : undefined,
          padding: onDrillAnalysis ? 4 : undefined,
          margin: onDrillAnalysis ? -4 : undefined,
          outline: 'none',
        }}
        title={onDrillAnalysis ? strictT(tr, lang, 'cmd_drill_health_hint') : undefined}
      >
        <svg width={76} height={76} viewBox="0 0 88 88" style={{ flexShrink: 0 }}>
          <circle cx={44} cy={44} r={34} fill="none" stroke={T.border} strokeWidth={5} />
          <circle
            cx={44}
            cy={44}
            r={34}
            fill="none"
            stroke={hc}
            strokeWidth={5}
            strokeDasharray={`${dash} ${circ - dash}`}
            strokeDashoffset={circ * 0.25}
            strokeLinecap="round"
            style={{ filter: `drop-shadow(0 0 10px ${hc}90)` }}
          />
          <text x={44} y={43} textAnchor="middle" fontSize={17} fontWeight={800} fill={hc} fontFamily="monospace">
            {h != null ? Math.round(h) : ''}
          </text>
          <text x={44} y={57} textAnchor="middle" fontSize={8} fill={T.text3}>
            /100
          </text>
        </svg>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ fontSize: 18, fontWeight: 800, color: T.text1, lineHeight: 1.2, marginBottom: 6 }}>
            {companyName || ''}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span
              style={{
                fontSize: 10,
                fontWeight: 800,
                padding: '4px 10px',
                borderRadius: 999,
                background: `${hc}22`,
                color: hc,
                border: `1px solid ${hc}44`,
                letterSpacing: '.04em',
              }}
            >
              {statusUi}
            </span>
            {period ? <span style={{ fontSize: 11, color: T.text2, fontFamily: 'monospace' }}>{period}</span> : null}
            {periodCount != null ? (
              <span style={{ fontSize: 10, color: T.text3 }}>
                · {periodCount}p
              </span>
            ) : null}
            {scopeLabel ? <span style={{ fontSize: 10, color: T.text3 }}>· {scopeLabel}</span> : null}
          </div>
        </div>
      </div>

      {healthHeadline || actionLine ? (
        <div
          style={{
            marginTop: 10,
            paddingTop: 10,
            borderTop: '1px solid rgba(148,163,184,0.12)',
          }}
        >
          {healthHeadline ? (
            <div style={{ fontSize: 13, fontWeight: 650, color: T.text1, lineHeight: 1.45 }}>{healthHeadline}</div>
          ) : null}
          {actionLine ? (
            <div style={{ marginTop: healthHeadline ? 8 : 0 }}>
              <div
                style={{
                  fontSize: 9,
                  fontWeight: 800,
                  color: T.accent,
                  letterSpacing: '.1em',
                  textTransform: 'uppercase',
                }}
              >
                {actionLbl}
              </div>
              <div style={{ fontSize: 13, fontWeight: 700, color: T.text1, marginTop: 4, lineHeight: 1.45 }}>{actionLine}</div>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────────────────
//  ContextPanel — drill context drawer
//  Minimal fix: CommandCenter references this panel on click.
// ──────────────────────────────────────────────────────────────────────────────
function ContextPanel({ type, payload, extra, tr, lang, onClose, onNavigate, impacts={} }) {
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
        <Pill label={strictT(tr, lang, `urgency_${payload.urgency}`)} color={uClr[payload.urgency]||T.text3}/>
        {payload.impact_level && <Pill label={strictT(tr, lang, `impact_${payload.impact_level}`)} color={uClr[payload.impact_level]||T.text3}/>}
        <Pill label={`${payload.confidence||'—'}%`} color={T.text3}/>
      </div>

      <Sec label={strictT(tr, lang, 'exec_why')} color={T.red}>
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

      <Sec label={strictT(tr, lang, 'exec_actions')} color={dc}>
        <Steps text={payload.action}/>
      </Sec>

      {payload.expected_effect && (
        <Sec label={strictT(tr, lang, 'exec_effect')} color={T.green}>
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
                {strictT(tr, lang, 'impact_expected_label')}
              </span>
            </div>
            <div style={{fontFamily:'monospace',fontSize:24,fontWeight:800,color:T.green,direction:'ltr',marginBottom:4}}>
              {fmtV(imp.value)}
            </div>
            {imp.range?.low!=null&&imp.range?.high!=null&&(
              <div style={{fontSize:10,color:T.text2,marginBottom:8,fontFamily:'monospace'}}>
                {fmtV(imp.range.low)} – {fmtV(imp.range.high)} {strictT(tr, lang, 'impact_range_label')}
              </div>
            )}
            <p style={{fontSize:11,color:T.text2,lineHeight:1.6,margin:'0 0 10px'}}>{imp.description}</p>
            <div style={{display:'flex',alignItems:'center',gap:8,flexWrap:'wrap'}}>
              <span style={{fontSize:9,color:T.green,background:`${T.green}15`,padding:'2px 8px',borderRadius:20,fontWeight:700,border:`1px solid ${T.green}30`}}>
                {strictT(tr, lang, 'fc_confidence')}: {imp.confidence}%
              </span>
              {imp.assumption&&<span style={{fontSize:10,color:T.text2,fontStyle:'italic'}}>{strictT(tr, lang, 'impact_based_on')}: {imp.assumption}</span>}
            </div>
          </div>
        )
      })()}

      <div style={{display:'flex',alignItems:'center',gap:12,
        background:T.card,borderRadius:11,padding:'12px 16px',border:`1px solid ${T.border}`}}>
        <span style={{fontSize:22,opacity:.45}}>⏱</span>
        <div>
          <div style={{fontSize:9,color:T.text3,textTransform:'uppercase',letterSpacing:'.07em',marginBottom:3}}>
            {strictT(tr, lang, 'exec_timeframe')}
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
        {strictT(tr, lang, `kpi_label_${payload.type}`)}
      </div>
      <div style={{fontSize:12,color:T.text2,lineHeight:1.55,marginBottom:14}}>
        {strictT(tr, lang, `kpi_explain_${payload.type}`)}
      </div>
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10,marginBottom:14}}>
        {[
          {lbl:strictT(tr, lang, 'exec_trend'), val:payload.mom!=null?`${payload.mom>0?'+':''}${payload.mom?.toFixed(1)}% MoM`:'—', clr:payload.mom>0?T.green:payload.mom<0?T.red:T.text2},
          {lbl:strictT(tr, lang, 'yoy_label'), val:payload.yoy!=null?`${payload.yoy>0?'+':''}${payload.yoy?.toFixed(1)}%`:'—',     clr:payload.yoy>0?T.green:payload.yoy<0?T.red:T.text2},
        ].map(({lbl,val,clr}) => (
          <div key={lbl} style={{background:T.card,borderRadius:8,padding:'12px 14px',border:`1px solid ${T.border}`}}>
            <div style={{fontSize:9,color:T.text3,textTransform:'uppercase',letterSpacing:'.06em',marginBottom:4}}>{lbl}</div>
            <div style={{fontFamily:'monospace',fontSize:17,fontWeight:800,color:clr}}>{val}</div>
          </div>
        ))}
      </div>
      {extra?.alerts?.length > 0 && (
        <Sec label={strictT(tr, lang, 'alerts_title')} color={T.amber}>
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
              {(() => {
                const a = tr(`domain_${payload.domain}_simple`)
                if (a && a !== `domain_${payload.domain}_simple` && !looksLikeRawI18nKey(a)) return a
                return strictT(tr, lang, `domain_${payload.domain}`)
              })()}
            </div>
            <div style={{fontSize:11,color:T.text2,marginTop:2}}>
              {(() => {
                const e = tr(`domain_${payload.domain}_exp`)
                return e && e !== `domain_${payload.domain}_exp` && !looksLikeRawI18nKey(e) ? e : ''
              })()}
            </div>
          </div>
          <div style={{textAlign:'right'}}>
            <div style={{fontFamily:'monospace',fontSize:22,fontWeight:800,color:dc}}>{payload.score!=null?Math.round(payload.score):'—'}</div>
            <div style={{fontSize:9,color:T.text3}}>/100</div>
          </div>
        </div>

        {causes.length>0 && (
          <Sec label={strictT(tr, lang, 'exec_why')} color={T.red}>
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
          <Sec label={strictT(tr, lang, 'exec_actions')} color={dc}>
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
          <Sec label={strictT(tr, lang, 'exec_breakdown')} color={T.text3}>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8}}>
              {Object.entries(payload.ratios).slice(0,6).map(([k,r]) => {
                const rc = {good:T.green,warning:T.amber,risk:T.red,neutral:T.text2}[r?.status]||T.text2
                return (
                  <div key={k} style={{background:T.card,borderRadius:7,padding:'8px 10px',
                    borderWidth:'1px 1px 1px 2px',borderStyle:'solid',borderColor:`${T.border} ${T.border} ${T.border} ${rc}`}}>
                    <div style={{fontSize:8,color:T.text3,textTransform:'uppercase',marginBottom:2}}>
                      {strictT(tr, lang, `ratio_${k}`)}
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
      <div style={{marginBottom:20}}><Pill label={strictT(tr, lang, `urgency_${payload.severity}`)} color={uClr[payload.severity]||T.text3}/></div>
      <Sec label={strictT(tr, lang, 'exec_why')} color={uClr[payload.severity]||T.amber}>
        <p style={{fontSize:12,color:T.text2,lineHeight:1.75,margin:0}}>{payload.message}</p>
      </Sec>
      <Sec label={strictT(tr, lang, 'exec_actions')} color={T.accent}>
        <p style={{fontSize:12,color:T.text2,lineHeight:1.75,margin:0}}>{payload.action}</p>
      </Sec>
    </>
  )

  const ExpenseDecisionV2 = () => {
    const d = payload || {}
    const pri = String(d.priority || 'medium').toLowerCase()
    const pc = { high: T.red, medium: T.amber, low: T.accent }[pri] || T.text3
    const act = d.action
    const steps = act && typeof act === 'object' && Array.isArray(act.steps) ? act.steps : null
    const efi = d.expected_financial_impact || {}
    const sav = efi.estimated_monthly_savings
    return (
      <>
        <div style={{ fontSize: 17, fontWeight: 800, color: T.text1, marginBottom: 10 }}>{d.title}</div>
        <div style={{ marginBottom: 16 }}>
          <Pill label={strictT(tr, lang, `urgency_${pri}`)} color={pc} />
        </div>
        {d.rationale ? (
          <Sec label={strictT(tr, lang, 'exec_why')} color={T.red}>
            <p style={{ margin: 0, fontSize: 12, color: T.text2, lineHeight: 1.75 }}>{d.rationale}</p>
          </Sec>
        ) : null}
        {steps?.length ? (
          <Sec label={strictT(tr, lang, 'exec_actions')} color={T.accent}>
            <ol style={{ margin: 0, paddingLeft: 18, color: T.text2, fontSize: 12, lineHeight: 1.7 }}>
              {steps.map((s, i) => (
                <li key={i} style={{ marginBottom: 8 }}>{String(s)}</li>
              ))}
            </ol>
          </Sec>
        ) : typeof act === 'string' && act.trim() ? (
          <Sec label={strictT(tr, lang, 'exec_actions')} color={T.accent}>
            <p style={{ margin: 0, fontSize: 12, color: T.text2, lineHeight: 1.75 }}>{act}</p>
          </Sec>
        ) : null}
        {sav != null && Number.isFinite(Number(sav)) && Number(sav) > 0 ? (
          <Sec label={strictT(tr, lang, 'cmd_dec_impact_monthly')} color={T.green}>
            <div style={{ fontFamily: 'monospace', fontSize: 18, fontWeight: 800, color: T.green, direction: 'ltr' }}>
              {formatCompact(sav)}
            </div>
          </Sec>
        ) : null}
      </>
    )
  }

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
            {type==='expense_v2'?strictT(tr, lang, 'cmd_expense_decision_detail')
             :type==='decision'?strictT(tr, lang, 'tab_decisions_v2')
             :type==='kpi'?strictT(tr, lang, 'exec_kpi_title')
             :type==='domain'?strictT(tr, lang, 'exec_domain_title')
             :type==='alert'?strictT(tr, lang, 'alerts_title')
             :strictT(tr, lang, 'exec_title')}
          </div>
          <button onClick={onClose} style={{width:30,height:30,borderRadius:8,
            border:`1px solid ${T.border}`,background:T.card,color:T.text2,
            cursor:'pointer',display:'flex',alignItems:'center',justifyContent:'center',
            fontSize:17,fontWeight:300}}>×</button>
        </div>
        <div style={{flex:1,overflowY:'auto',padding:'22px 22px'}}>
          {type==='expense_v2' && <ExpenseDecisionV2/>}
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
              {type==='expense_v2'
                ? strictT(tr, lang, 'cmd_open_full_analysis_decisions')
                : strictT(tr, lang, 'open_analysis')}
            </button>
          </div>
        )}
      </div>
    </>
  )
}

function ExecutiveKpiRow({
  kpis,
  cashflow,
  main,
  tr,
  lang,
  onSelect,
  alerts,
  ctxLabel,
  hideTitle = false,
  layout = 'dashboard',
}) {
  const na = strictT(tr, lang, 'cmd_na_short')
  const dispN = (v) => (v == null || v === '' || isNaN(Number(v)) ? na : formatCompact(v))
  const dispFull = (v) => (v == null || v === '' || isNaN(Number(v)) ? null : formatFull(v))
  const cfEstimated = cashflow?.reliability === 'estimated'
  const wc       = kpis.working_capital?.value
             ?? cashflow?.working_capital
             ?? main?.statements?.balance_sheet?.working_capital
  const wcColor  = wc==null?T.text3:wc>=0?T.green:T.red
  const heroKey = 'net_profit'
  const cards = [
    { key:'revenue',         value:dispN(kpis.revenue?.value),        full:dispFull(kpis.revenue?.value),        mom:kpis.revenue?.mom_pct,    yoy:kpis.revenue?.yoy_pct,    color:T.accent,  icon:'📈' },
    { key:'expenses',        value:dispN(kpis.expenses?.value),       full:dispFull(kpis.expenses?.value),       mom:kpis.expenses?.mom_pct,   yoy:kpis.expenses?.yoy_pct,   color:T.amber,   icon:'📊' },
    { key:'net_profit',      value:dispN(kpis.net_profit?.value),      full:dispFull(kpis.net_profit?.value),      mom:kpis.net_profit?.mom_pct, yoy:kpis.net_profit?.yoy_pct, color:T.green,   icon:'💰' },
    { key:'cashflow',        value:dispN(cashflow?.operating_cashflow), full:dispFull(cashflow?.operating_cashflow), mom:cashflow?.operating_cashflow_mom, yoy:null, color:T.blue,   icon:'💧', estimated:cfEstimated },
    { key:'net_margin',      value:fmtP(kpis.net_margin?.value)||na, full:null, mom:kpis.net_margin?.mom_pct, yoy:null, color:T.violet,  icon:'%'  },
    { key:'working_capital', value:dispN(wc),                           full:dispFull(wc),                          mom:null,                     yoy:null, sub:wc!=null&&wc<0?strictT(tr, lang, 'wc_negative'):null, color:wcColor, icon:'⚖️' },
  ]
  const ordered = [
    ...cards.filter(c=>c.key===heroKey),
    ...cards.filter(c=>c.key!==heroKey),
  ]
  const hero = ordered[0]
  const secondary = ordered.slice(1)

  const renderCard = (c, { isHero }) => {
    const mc = c.mom==null?T.text3:c.mom>0?T.green:c.mom<0?T.red:T.text2
    const explain = strictT(tr, lang, `kpi_explain_${c.key}`)
    const base = strictT(tr, lang, `kpi_label_${c.key}`)
    const ctx = ctxLabel()
    const tplRaw = tr('kpi_with_context')
    const labelWithCtx =
      ctx && tplRaw && tplRaw !== 'kpi_with_context' && !looksLikeRawI18nKey(tplRaw)
        ? tplRaw.replace(/\{label\}/g, base).replace(/\{context\}/g, ctx)
        : base
    return (
      <div key={c.key}
        onClick={()=>onSelect('kpi',{type:c.key,mom:c.mom,yoy:c.yoy},
          {alerts:alerts?.filter(a=>a.impact==='profitability')||[], explanation:explain})}
        title={explain}
        style={{
          background: isHero ? `linear-gradient(135deg,${T.card},${c.color}14)` : T.card,
          borderWidth:'1px',borderStyle:'solid',borderColor:isHero?`${c.color}35`:T.border,
          borderTopWidth:isHero?3:2,borderTopColor:c.color,borderRadius:12,
          padding:isHero?'14px 14px':'10px 12px',
          cursor:'pointer',
          transition:'transform 0.2s cubic-bezier(0.4,0,0.2,1), box-shadow 0.2s ease, border-color 0.2s ease',
        }}
        {...lift(c.color)}>
        <div style={{display:'flex',alignItems:'center',gap:6,marginBottom:isHero?6:5}}>
          <span style={{fontSize:isHero?16:11}}>{c.icon}</span>
          <span style={{fontSize:isHero?10:9,color:T.text2,fontWeight:800,textTransform:'uppercase',
            letterSpacing:'.06em'}}>
            {labelWithCtx}
          </span>
          {isHero && (
            <span style={{marginLeft:'auto',fontSize:8,fontWeight:900,color:c.color,letterSpacing:'.10em',textTransform:'uppercase'}}>
              {strictT(tr, lang, 'primary')}
            </span>
          )}
        </div>
        <div style={{fontFamily:'var(--font-display)',fontSize:isHero?26:18,fontWeight:900,color:'#ffffff',
          marginBottom:2,direction:'ltr',letterSpacing:'-0.025em',lineHeight:1}}>
          {c.value}
        </div>
        {c.full && (
          <div style={{fontFamily:'var(--font-mono)',fontSize:8,color:T.text3,marginBottom:2,letterSpacing:'.02em',direction:'ltr'}}>
            {c.full}
          </div>
        )}
        <div style={{display:'flex',gap:6,flexWrap:'wrap'}}>
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

  if (layout === 'command') {
    const cmdOrder = ['revenue', 'expenses', 'net_profit', 'net_margin']
    const cmdCards = cmdOrder.map((k) => cards.find((c) => c.key === k)).filter(Boolean)
    return (
      <div
        className="cmd-kpi-four"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
          gap: 8,
        }}
      >
        {cmdCards.map((c) => renderCard(c, { isHero: false }))}
      </div>
    )
  }

  return (
    <div>
      {!hideTitle ? (
        <div style={{fontSize:10,fontWeight:700,color:T.text3,textTransform:'uppercase',
          letterSpacing:'.08em',marginBottom:10}}>{strictT(tr, lang, 'exec_kpi_title')}</div>
      ) : null}
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

function DomainGrid({ intelligence, tr, lang, onSelect, rootCauses, decisions, alerts, secondary = false }) {
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
  const pickLbl = (a, b) => {
    const x = tr(a)
    if (x && x !== a && !looksLikeRawI18nKey(x)) return x
    const y = tr(b)
    if (y && y !== b && !looksLikeRawI18nKey(y)) return y
    return strictT(tr, lang, a)
  }
  const blocks = [
    { id:'profitability', label: pickLbl('profitability', 'domain_profitability_simple'), color: dClr.profitability, icon:'📈', score: score('profitability'), ratiosKey:'profitability', navigateDomain:'profitability' },
    { id:'liquidity',     label: pickLbl('liquidity', 'domain_liquidity_simple'),     color: dClr.liquidity,     icon:'💧', score: score('liquidity'),     ratiosKey:'liquidity',     navigateDomain:'liquidity' },
    { id:'efficiency',    label: pickLbl('efficiency', 'domain_efficiency_simple'),    color: dClr.efficiency,    icon:'⚡', score: score('efficiency'),    ratiosKey:'efficiency',    navigateDomain:'efficiency' },
    { id:'risk',          label: pickLbl('risk_level', 'domain_leverage_simple'),      color: T.red,              icon:'🛡', score: riskScore(),            ratiosKey:'leverage',      navigateDomain:'leverage' },
  ]
  const ratioMap = key => ratios[key] || {}
  return (
    <div style={secondary ? { opacity: 0.88 } : undefined}>
      <div style={{fontSize:secondary?8:10,fontWeight:700,color:T.text3,textTransform:'uppercase',
        letterSpacing:'.1em',marginBottom:secondary?6:10}}>{strictT(tr, lang, 'exec_domain_title')}</div>
      <div style={{display:'grid',gridTemplateColumns:'repeat(12,1fr)',gap:secondary?8:10}}>
        {blocks.map((b, idx) => {
          const s   = b.score
          const dc  = b.color || T.accent
          const st  = s>=70?'good':s>=45?'warning':'risk'
          const sc  = stC[st]
          const sig = b.id==='risk'
            ? (s>=70?strictT(tr, lang, 'risk_level_low'):s>=45?strictT(tr, lang, 'risk_level_medium'):strictT(tr, lang, 'risk_level_high'))
            : (s>=70 ? strictT(tr, lang, `domain_signal_${b.navigateDomain}_good`)
                     : s>=45 ? strictT(tr, lang, `domain_signal_${b.navigateDomain}_warn`)
                             : strictT(tr, lang, `domain_signal_${b.navigateDomain}_risk`))
          return (
            <div key={b.id}
              onClick={()=>onSelect('domain',{domain:b.navigateDomain,score:s,status:st,ratios:ratioMap(b.ratiosKey)},{causes:rootCauses,decisions})}
              title={b.id==='risk' ? strictT(tr, lang, 'alerts_title') : (() => {
                const e = tr(`domain_${b.navigateDomain}_exp`)
                return e && e !== `domain_${b.navigateDomain}_exp` && !looksLikeRawI18nKey(e) ? e : ''
              })()}
              style={{
                gridColumn: idx===0 ? 'span 4' : 'span 4',
                background: `linear-gradient(135deg,${T.card},${dc}0a)`,
                borderWidth:'1px',borderStyle:'solid',borderColor:`${dc}28`,
                borderTopWidth:secondary?3:4,borderTopColor:dc,borderRadius:secondary?12:15,
                padding:secondary?'10px 10px':'16px 16px',cursor:'pointer',
                transition:'transform .15s ease,box-shadow .15s ease'}}
              {...lift(dc)}>
              <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:8,marginBottom:secondary?8:12}}>
                <div style={{display:'flex',alignItems:'center',gap:6,minWidth:0}}>
                  <span style={{fontSize:secondary?15:18}}>{b.icon}</span>
                  <div style={{minWidth:0}}>
                    <div style={{fontSize:secondary?10:11,fontWeight:900,color:dc,textTransform:'uppercase',letterSpacing:'.08em',whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>
                      {b.label}
                    </div>
                    <div style={{fontSize:secondary?9:10,color:T.text2,marginTop:1,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>
                      {sig || strictT(tr, lang, `status_${st}_simple`)}
                    </div>
                  </div>
                </div>
                <div style={{textAlign:'right',flexShrink:0}}>
                  <div style={{fontFamily:'monospace',fontSize:secondary?18:22,fontWeight:900,color:dc,lineHeight:1,direction:'ltr'}}>{s}</div>
                  <div style={{fontSize:8,color:T.text3}}>/100</div>
                </div>
              </div>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:secondary?6:8}}>
                {Object.entries(ratioMap(b.ratiosKey)).slice(0,4).map(([k,r]) => {
                  const rc = {good:T.green,warning:T.amber,risk:T.red,neutral:T.text2}[r?.status]||T.text2
                  return (
                    <div key={k} style={{background:`${dc}08`,borderRadius:secondary?8:10,padding:secondary?'6px 7px':'10px 10px',
                      borderWidth:'1px 1px 1px 2px',borderStyle:'solid',borderColor:`${T.border} ${T.border} ${T.border} ${rc}`}}>
                      <div style={{fontSize:7,color:T.text3,textTransform:'uppercase',letterSpacing:'.08em',marginBottom:2}}>
                        {strictT(tr, lang, `ratio_${k}`)}
                      </div>
                      <div style={{fontFamily:'monospace',fontSize:secondary?11:12,fontWeight:800,color:rc,direction:'ltr'}}>
                        {r?.value!=null?r.value:'—'}
                        <span style={{fontSize:9,color:T.text3,marginLeft:3}}>{r?.unit||''}</span>
                      </div>
                    </div>
                  )
                })}
                {b.id==='risk' && (
                  <div style={{gridColumn:'1 / -1',background:`${T.red}08`,border:`1px solid ${T.red}20`,borderRadius:secondary?8:10,padding:secondary?'6px 8px':'10px 12px'}}>
                    <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:8}}>
                      <div style={{fontSize:secondary?8:9,fontWeight:900,color:T.red,textTransform:'uppercase',letterSpacing:'.08em'}}>
                        {strictT(tr, lang, 'alerts_title')}
                      </div>
                      <div style={{fontFamily:'monospace',fontSize:secondary?11:12,fontWeight:900,color:T.red,direction:'ltr'}}>
                        {(alerts||[]).length ?? 0}
                      </div>
                    </div>
                    <div style={{marginTop:secondary?4:6,display:'flex',gap:5,flexWrap:'wrap'}}>
                      {['high','medium','low'].map(sev => {
                        const n = (alerts||[]).filter(a=>a.severity===sev).length
                        if (!n) return null
                        const c = uClr[sev]||T.text3
                        return <Pill key={sev} label={`${n} ${strictT(tr, lang, `urgency_${sev}`)}`} color={c}/>
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

function AlertsBar({ alerts, tr, lang, onSelect, secondary = false }) {
  if (!alerts?.length) return null
  return (
    <div style={{display:'flex',alignItems:'center',gap:8,
      background:T.surface,border:`1px solid ${T.border}`,
      borderRadius:11,padding:secondary?'8px 14px':'10px 16px',flexWrap:'wrap',opacity:secondary?0.9:1}}>
      <span style={{fontSize:11,fontWeight:700,color:T.amber,flexShrink:0}}>
        ⚠ {alerts.length} {strictT(tr, lang, 'alerts_title')}
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

function ForecastNow({ fcData, tr, lang, secondary = false }) {
  if (!fcData?.available) return null
  const bRev = fcData?.scenarios?.base?.revenue?.[0]
  const bNp  = fcData?.scenarios?.base?.net_profit?.[0]
  const risk = fcData?.summary?.risk_level
  if (!bRev?.point && !bNp?.point) return null
  const riskClr = risk==='high'?T.red:risk==='medium'?T.amber:risk?T.green:T.text3
  const riskWord =
    risk === 'high'
      ? strictT(tr, lang, 'urgency_high')
      : risk === 'medium'
        ? strictT(tr, lang, 'urgency_medium')
        : risk === 'low'
          ? strictT(tr, lang, 'urgency_low')
          : risk
  return (
    <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:10,padding:secondary?'8px 10px':'10px 12px',
      opacity:secondary?0.88:1}}>
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:8,marginBottom:secondary?6:8}}>
        <div style={{fontSize:9,fontWeight:800,color:T.text3,textTransform:'uppercase',letterSpacing:'.08em'}}>
          {strictT(tr, lang, 'forecast_next_period')}
        </div>
        {risk && <Pill label={`${strictT(tr, lang, 'forecast_risk')}: ${riskWord}`} color={riskClr}/>}
      </div>
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:secondary?8:10}}>
        <div style={{background:T.card,border:`1px solid ${T.border}`,borderRadius:8,padding:secondary?'6px 8px':'8px 10px'}}>
          <div style={{fontSize:8,color:T.text3,textTransform:'uppercase',letterSpacing:'.08em',marginBottom:2}}>{strictT(tr, lang, 'revenue')}</div>
          <div style={{fontFamily:'monospace',fontSize:secondary?14:15,fontWeight:800,color:T.accent,direction:'ltr'}}>
            {bRev?.point!=null?formatCompact(bRev.point):'—'}
          </div>
          {bRev?.confidence!=null&&<div style={{fontSize:8,color:T.text3,marginTop:2}}>{strictT(tr, lang, 'fc_confidence')}: {bRev.confidence}%</div>}
        </div>
        <div style={{background:T.card,border:`1px solid ${T.border}`,borderRadius:8,padding:secondary?'6px 8px':'8px 10px'}}>
          <div style={{fontSize:8,color:T.text3,textTransform:'uppercase',letterSpacing:'.08em',marginBottom:2}}>{strictT(tr, lang, 'net_profit')}</div>
          <div style={{fontFamily:'monospace',fontSize:secondary?14:15,fontWeight:800,color:T.green,direction:'ltr'}}>
            {bNp?.point!=null?formatCompact(bNp.point):'—'}
          </div>
          {bNp?.confidence!=null&&<div style={{fontSize:8,color:T.text3,marginTop:2}}>{strictT(tr, lang, 'fc_confidence')}: {bNp.confidence}%</div>}
        </div>
      </div>
    </div>
  )
}

function CommandNav({ tr, lang, navigate, secondary = false }) {
  /* Analysis / branches are drill-down only (from Command Center), not peer hubs. */
  const links = [
    { to:'/statements', label: strictT(tr, lang, 'nav_statements') },
    { to:'/board-report', label: strictT(tr, lang, 'nav_board_report') },
    { to:'/upload', label: strictT(tr, lang, 'nav_upload') },
  ]
  return (
    <div style={{marginTop:6,paddingTop:10,borderTop:`1px solid ${T.border}`,opacity:secondary?0.85:1}}>
      <div style={{fontSize:8,fontWeight:800,color:T.text3,textTransform:'uppercase',letterSpacing:'.12em',marginBottom:6}}>
        {strictT(tr, lang, 'navigation')}
      </div>
      <div style={{display:'flex',gap:6,flexWrap:'wrap'}}>
        {links.map(l=>(
          <button key={l.to} onClick={()=>navigate(l.to)}
            style={{padding:'4px 9px',borderRadius:999,border:`1px solid ${T.border}`,
              background:'transparent',color:T.text2,fontSize:10,fontWeight:700,cursor:'pointer',
              opacity:.85,transition:'opacity .15s, border-color .15s'}}>
            {l.label}
          </button>
        ))}
      </div>
    </div>
  )
}

function scrollToCmdSection(id) {
  const el = typeof document !== 'undefined' ? document.getElementById(id) : null
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function CommandCenterRail({ tr, lang }) {
  const sections = [
    { id: 'cmd-row-1', n: 1, tipKey: 'cmd_rail_tip_1' },
    { id: 'cmd-row-2', n: 2, tipKey: 'cmd_rail_tip_2' },
    { id: 'cmd-row-3', n: 3, tipKey: 'cmd_rail_tip_3' },
    { id: 'cmd-row-4', n: 4, tipKey: 'cmd_rail_tip_4' },
    { id: 'cmd-row-5', n: 5, tipKey: 'cmd_rail_tip_6' },
  ]
  return (
    <nav
      aria-label={strictT(tr, lang, 'cmd_rail_aria')}
      style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
    >
      {sections.map((s) => (
        <button
          key={s.id}
          type="button"
          title={strictT(tr, lang, s.tipKey)}
          onClick={() => scrollToCmdSection(s.id)}
          style={{
            width: 40,
            height: 40,
            borderRadius: '50%',
            border: '1px solid rgba(167,139,250,0.5)',
            background: 'linear-gradient(155deg, rgba(124,92,252,0.45), rgba(15,23,42,0.98))',
            color: '#f5f3ff',
            fontWeight: 900,
            fontSize: 14,
            cursor: 'pointer',
            boxShadow: '0 4px 24px rgba(124,92,252,0.2), inset 0 1px 0 rgba(255,255,255,0.12)',
            transition: 'transform .15s ease, box-shadow .15s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'scale(1.06)'
            e.currentTarget.style.boxShadow = '0 6px 28px rgba(124,92,252,0.35)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = ''
            e.currentTarget.style.boxShadow = '0 4px 24px rgba(124,92,252,0.2), inset 0 1px 0 rgba(255,255,255,0.12)'
          }}
        >
          {s.n}
        </button>
      ))}
    </nav>
  )
}

function SecondaryInsightsGrid({
  fcData,
  intel,
  alerts,
  tr,
  lang,
  navigate,
  drillAnalysis,
  onSelect,
  rootCauses,
  decisions,
}) {
  const nAlert = Array.isArray(alerts) ? alerts.length : 0
  const tileBase = {
    textAlign: 'left' ,
    padding: '10px 12px',
    borderRadius: 11,
    border: `1px solid ${T.border}`,
    background: 'linear-gradient(165deg, rgba(17,24,39,0.96) 0%, rgba(15,23,42,0.98) 100%)',
    boxShadow: '0 0 0 1px rgba(0,212,170,0.04), 0 6px 20px rgba(0,0,0,0.28)',
    cursor: 'pointer',
    transition: 'transform .15s ease, border-color .15s ease',
  }
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(168px, 1fr))',
        gap: 10,
      }}
    >
      <div style={{ ...tileBase, cursor: 'default', opacity: 0.92 }}>
        <div style={{ fontSize: 15, marginBottom: 4 }}>📉</div>
        <div style={{ fontSize: 11, fontWeight: 800, color: T.text1, marginBottom: 4 }}>
          {strictT(tr, lang, 'cmd_secondary_tile_forecast')}
        </div>
        {fcData?.available ? (
          <ForecastNow fcData={fcData} tr={tr} lang={lang} secondary />
        ) : (
          <div style={{ fontSize: 10, color: T.text3, lineHeight: 1.4 }}>
            {strictT(tr, lang, 'cmd_secondary_fc_empty')}
          </div>
        )}
      </div>
      <button
        type="button"
        onClick={() => drillAnalysis?.('overview')}
        style={tileBase}
        {...lift(dClr.profitability)}
      >
        <div style={{ fontSize: 15, marginBottom: 4 }}>📊</div>
        <div style={{ fontSize: 11, fontWeight: 800, color: T.text1 }}>
          {strictT(tr, lang, 'cmd_secondary_tile_domains')}
        </div>
        <div style={{ fontSize: 10, color: T.text3, marginTop: 3, lineHeight: 1.35 }}>
          {strictT(tr, lang, 'cmd_secondary_tile_domains_sub')}
        </div>
      </button>
      <button
        type="button"
        onClick={() => {
          if (alerts?.[0]) onSelect('alert', alerts[0], {})
          else drillAnalysis?.('alerts')
        }}
        style={tileBase}
        {...lift(T.amber)}
      >
        <div style={{ fontSize: 15, marginBottom: 4 }}>⚠️</div>
        <div style={{ fontSize: 11, fontWeight: 800, color: T.text1 }}>
          {strictT(tr, lang, 'cmd_secondary_tile_alerts')}
        </div>
        <div style={{ fontSize: 10, color: T.text3, marginTop: 3, lineHeight: 1.35 }}>
          {nAlert
            ? strictT(tr, lang, 'cmd_secondary_tile_alerts_count').replace('{n}', String(nAlert))
            : strictT(tr, lang, 'cmd_secondary_tile_alerts_none')}
        </div>
      </button>
      <button type="button" onClick={() => navigate('/statements')} style={tileBase} {...lift(T.accent)}>
        <div style={{ fontSize: 15, marginBottom: 4 }}>📑</div>
        <div style={{ fontSize: 11, fontWeight: 800, color: T.text1 }}>
          {strictT(tr, lang, 'cmd_secondary_tile_statements')}
        </div>
        <div style={{ fontSize: 10, color: T.text3, marginTop: 3, lineHeight: 1.35 }}>
          {strictT(tr, lang, 'cmd_secondary_tile_statements_sub')}
        </div>
      </button>
      {intel ? (
        <div style={{ gridColumn: '1 / -1' }}>
          <DomainGrid
            intelligence={intel}
            tr={tr}
            lang={lang}
            onSelect={onSelect}
            rootCauses={rootCauses}
            decisions={decisions}
            alerts={alerts}
            secondary
          />
        </div>
      ) : null}
      {nAlert ? <AlertsBar alerts={alerts} tr={tr} lang={lang} onSelect={onSelect} secondary /> : null}
      <div style={{ gridColumn: '1 / -1' }}>
        <CommandNav tr={tr} lang={lang} navigate={navigate} secondary />
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
  const [fcData,   setFcData]   = useState(null)
  const [loading,  setLoading]  = useState(false)
  const [consolidate, setConsolidate] = useState(false)
  const [noDataMsg, setNoDataMsg] = useState(null)
  const [narrative, setNarrative] = useState(null)

  const [impacts, setImpacts] = useState({})
  const [pType, setPType] = useState(null)
  const [pLoad, setPLoad] = useState(null)
  const [pXtra, setPXtra] = useState(null)
  const open  = useCallback((t,p,x=null)=>{ setPType(t); setPLoad(p); setPXtra(x) },[])
  const close = useCallback(()=>{ setPType(null); setPLoad(null); setPXtra(null) },[])

  const drillAnalysis = useCallback(
    (tab) => {
      navigate('/analysis', { state: { focus: tab || 'overview' } })
    },
    [navigate],
  )

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
          setNarrative(null)
          setNoDataMsg(tr('err_no_financial_data'))
        }
        return
      }
      const j = await r.json(); const d = j.data||{}
      setNarrative(buildExecutiveNarrative(d, { lang }))
      psSetResolved(j.meta?.scope || null)
      setIntel(d.intelligence||null)
      setDecs(d.decisions||[])
      setCauses(d.root_causes||[])
      setAlerts(d.alerts||[])
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
        comparative_intelligence: d.comparative_intelligence ?? null,
        financial_brain:          d.financial_brain ?? null,
        expense_decisions_v2:     d.expense_decisions_v2 ?? [],
        expense_intelligence:     d.expense_intelligence ?? null,
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

  useEffect(() => { load() }, [load])

  if (!selectedId) {
    return (
      <div style={{display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',height:'70vh',gap:12,background:T.bg}}>
        <span style={{fontSize:52,opacity:.15}}>🏢</span>
        <div style={{fontSize:15,fontWeight:600,color:T.text2}}>{strictT(tr, lang, 'exec_no_company')}</div>
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
  const dupIneffBranch = keySignalsShowsInefficientBranch(main?.comparative_intelligence, narrative, tr, lang)
  const expenseIntel = main?.expense_intelligence

  return (
    <div style={{ padding: '22px 24px', minHeight: 'calc(100vh - 62px)', background: T.bg }}>
      <style>{`
        @keyframes spin { to { transform:rotate(360deg) } }
        @keyframes slideIn { from { transform:translateX(100%);opacity:0 } to { transform:translateX(0);opacity:1 } }
        @keyframes fadeUp { from { opacity:0;transform:translateY(5px) } to { opacity:1;transform:none } }
        @media (max-width: 1100px) {
          .cmd-dashboard-grid .cmd-r1 { grid-template-columns: 1fr !important; }
          .cmd-dashboard-grid { grid-template-columns: 1fr !important; }
          .cmd-dashboard-grid .cmd-full { grid-column: 1 / -1 !important; }
        }
        @media (max-width: 960px) {
          .cmd-kpi-four { grid-template-columns: repeat(2, minmax(0, 1fr)) !important; }
        }
        @media (max-width: 480px) {
          .cmd-kpi-four { grid-template-columns: minmax(0, 1fr) !important; }
        }
      `}</style>

      <div style={{ display: 'flex', gap: 22, alignItems: 'flex-start' }}>
        <aside
          style={{
            position: 'sticky',
            top: 20,
            flexShrink: 0,
            paddingTop: 6,
            alignSelf: 'flex-start',
          }}
        >
          <CommandCenterRail tr={tr} lang={lang} />
        </aside>

        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div
            style={{
              position: 'sticky',
              top: 0,
              zIndex: 24,
              background: T.bg,
              paddingBottom: 12,
              marginBottom: 4,
              borderBottom: '1px solid rgba(148,163,184,0.12)',
            }}
          >
            <header>
              <div style={{ fontSize: 22, fontWeight: 800, color: T.text1, letterSpacing: '-0.02em' }}>
                {strictT(tr, lang, 'nav_command_center')}
              </div>
              <div style={{ fontSize: 12, color: T.text3, marginTop: 4, lineHeight: 1.45 }}>
                <span style={{ color: T.text2, fontWeight: 600 }}>{selectedCompany?.name || '—'}</span>
                <span style={{ marginLeft: 8 }}>· {strictT(tr, lang, 'cmd_page_sub')}</span>
              </div>
            </header>
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                gap: 10,
                marginTop: 12,
              }}
            >
              <PeriodSelector window={win} setWindow={setWin} disabled={loading} />
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0,
                  background: T.card,
                  border: `1px solid ${T.border}`,
                  borderRadius: 8,
                  overflow: 'hidden',
                  flexShrink: 0,
                }}
              >
                {[
                  { v: false, l: tr('company_uploads') },
                  { v: true, l: tr('branch_consolidation') },
                ].map((opt) => (
                  <button
                    key={String(opt.v)}
                    type="button"
                    onClick={() => setConsolidate(opt.v)}
                    style={{
                      padding: '5px 12px',
                      fontSize: 11,
                      fontWeight: 600,
                      border: 'none',
                      cursor: 'pointer',
                      background: consolidate === opt.v ? T.accent : 'transparent',
                      color: consolidate === opt.v ? '#000' : T.text2,
                      transition: 'all .15s',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {opt.l}
                  </button>
                ))}
              </div>
              <UniversalScopeSelector
                tr={tr}
                ps={ps}
                psUpdate={psUpdate}
                onApply={load}
                activeLabel={psActiveLabel()}
                allPeriods={main?.all_periods || []}
              />
              {loading ? (
                <div
                  style={{
                    width: 14,
                    height: 14,
                    border: `2px solid ${T.border}`,
                    borderTopColor: T.accent,
                    borderRadius: '50%',
                    animation: 'spin .8s linear infinite',
                  }}
                />
              ) : null}
            </div>
          </div>

          <DataQualityBanner validation={main?.pipeline_validation} lang={lang} tr={tr} />

          <CommandCenterDashboardGrid
            row1Narrative={
              <ExecutiveNarrativeStrip
                narrative={narrative}
                tr={tr}
                lang={lang}
                compact
                onOpenFullAnalysis={() => drillAnalysis('overview')}
              />
            }
            row1Health={
              <HealthScorePanel
                tr={tr}
                lang={lang}
                health={health}
                status={status}
                companyName={selectedCompany?.name}
                period={period}
                loading={loading}
                onRefresh={load}
                periodCount={main?.periods?.length}
                scopeLabel={main?.scope_label}
                healthHeadline={narrative?.healthHeadline}
                actionPrefix={narrative?.actionPrefix}
                actionLine={narrative?.actionLine}
                onDrillAnalysis={() => drillAnalysis('overview')}
              />
            }
            row2Kpis={
              main ? (
                <ExecutiveKpiRow
                  kpis={kpis}
                  cashflow={main?.cashflow || {}}
                  main={main}
                  tr={tr}
                  lang={lang}
                  alerts={alerts}
                  onSelect={open}
                  ctxLabel={ctxLabel}
                  hideTitle
                  layout="command"
                />
              ) : null
            }
            row3Signals={
              <KeySignalsSection
                financialBrain={main?.financial_brain}
                comparativeIntel={main?.comparative_intelligence}
                alerts={alerts}
                narrative={narrative}
                tr={tr}
                lang={lang}
                main={main}
                intel={intel}
                expenseIntel={expenseIntel}
                onOpenAnalysis={(tab) => drillAnalysis(tab)}
                visualTier={2}
              />
            }
            row3Branch={
              <BranchIntelligenceSection
                comparativeIntel={main?.comparative_intelligence}
                tr={tr}
                lang={lang}
                narrative={narrative}
                duplicateIneffBranchName={dupIneffBranch}
                onOpenBranches={() => navigate('/branches')}
                onBranchRankClick={(b) =>
                  navigate('/branches', {
                    state: {
                      focusBranchId: b?.branch_id,
                      focusBranchName: b?.branch_name,
                    },
                  })
                }
                visualTier={2}
              />
            }
            row4Expense={
              <ExpenseInsightsSection
                expenseIntel={expenseIntel}
                tr={tr}
                lang={lang}
                period={expenseIntel?.period || period}
                embedded
                onDrillExpense={() => drillAnalysis('profitability')}
                visualTier={2}
              />
            }
            row4Decisions={
              <DecisionsSection
                expenseDecisionsV2={main?.expense_decisions_v2}
                expenseIntel={expenseIntel}
                tr={tr}
                lang={lang}
                onOpenDecision={(d) => open('expense_v2', d, {})}
                visualTier={2}
              />
            }
            secondaryTitle={
              <div
                style={{
                  fontSize: 9,
                  fontWeight: 800,
                  color: T.text3,
                  textTransform: 'uppercase',
                  letterSpacing: '.1em',
                }}
              >
                {strictT(tr, lang, 'cmd_secondary_section')}
              </div>
            }
            secondarySubtitle={
              <div style={{ fontSize: 8, color: T.text3, lineHeight: 1.35, marginTop: -4 }}>
                {strictT(tr, lang, 'cmd_secondary_section_sub')}
              </div>
            }
            secondaryBlock={
              <SecondaryInsightsGrid
                fcData={fcData}
                intel={intel}
                alerts={alerts}
                tr={tr}
                lang={lang}
                navigate={navigate}
                drillAnalysis={drillAnalysis}
                onSelect={open}
                rootCauses={causes}
                decisions={decs}
              />
            }
          />
        </div>
      </div>

      {pType && (
        <ContextPanel
          type={pType}
          payload={pLoad}
          extra={pXtra}
          impacts={impacts}
          tr={tr}
          lang={lang}
          onClose={close}
          onNavigate={() => {
            if (pType === 'expense_v2') {
              navigate('/analysis', { state: { focus: 'decisions' } })
            } else {
              navigate('/analysis', {
                state: {
                  focus: analysisTabFromDrill({ type: pLoad?.type, domain: pLoad?.domain }),
                },
              })
            }
            close()
          }}
        />
      )}
    </div>
  )
}

