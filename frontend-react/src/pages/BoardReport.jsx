/**
 * BoardReport.jsx — Phase 46 Final Production
 *
 * Fixes: zero raw keys, zero hardcoded strings, window selector,
 * KPI with period avg comparison, clean chart, board-level header,
 * branch i18n, professional footer, print-ready A4.
 */
import { useState, useEffect, useCallback } from 'react'
import { usePeriodScope } from '../context/PeriodScopeContext.jsx'
import { useLang }        from '../context/LangContext.jsx'
import { useCompany }     from '../context/CompanyContext.jsx'
import {
  formatCompactForLang,
  formatFullForLang,
  formatPctForLang,
  formatMultipleForLang,
  formatDays,
} from '../utils/numberFormat.js'

const API = '/api/v1'
function auth() {
  try { const t = JSON.parse(localStorage.getItem('vcfo_auth')||'{}').token; return t?{Authorization:`Bearer ${t}`}:{} }
  catch { return {} }
}

// ── Tokens ────────────────────────────────────────────────────────────────────
const T = {
  bg:'#09100D', panel:'#0F1A14', card:'#141F18',
  border:'rgba(255,255,255,0.07)',
  accent:'#00d4aa', green:'#10d98a', red:'#ff4d6d',
  amber:'#fbbf24', blue:'#3b9eff', violet:'#a78bfa',
  text1:'#f0f4f1', text2:'#9db3a4', text3:'#5a7a65',
}
const HC = {strong:T.green, good:T.accent, stable:T.blue, weak:T.amber, critical:T.red}
const SC = {high:T.red, critical:T.red, medium:T.amber, warning:T.amber, low:T.text3, info:T.blue}

// ── Print CSS ─────────────────────────────────────────────────────────────────
const PCSS = `
@media print {
  nav,aside,.no-print,.export-toolbar{display:none!important}
  body,html{background:#fff!important;color:#1a1a1a!important;font-family:Georgia,serif!important;font-size:10.5pt!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .board-root{background:#fff!important;padding:0!important;max-width:100%!important}
  .cover-page{background:#0d1a12!important;min-height:100vh!important;page-break-after:always!important;break-after:page!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .report-section{background:#fff!important;border:1px solid #c8d4cc!important;border-left:3px solid #007a62!important;box-shadow:none!important;break-inside:avoid!important;page-break-inside:avoid!important}
  .kpi-card{background:#f7f8fa!important;border:1px solid #c8d4cc!important;box-shadow:none!important;break-inside:avoid!important}
  .branch-card{background:#f7f8fa!important;border:1px solid #c8d4cc!important;box-shadow:none!important;break-inside:avoid!important}
  .kpi-grid{grid-template-columns:repeat(2,1fr)!important;gap:8pt!important}
  .kpi-val{color:#1a1a1a!important;font-size:18pt!important}
  .two-col{grid-template-columns:1fr!important}
  .branch-grid{grid-template-columns:repeat(2,1fr)!important}
  .sdiv{break-before:auto!important;margin-top:16pt!important}
  .metric-row{border-bottom:1px solid #dde5e0!important}
  .sig-row{border-bottom:1px solid #dde5e0!important}
  .trend-box{border:1px solid #c8d4cc!important;box-shadow:none!important}
  .pfooter{display:flex!important;position:fixed!important;bottom:0!important;left:0!important;right:0!important;padding:5pt 20mm!important;border-top:1px solid #c8d4cc!important;font-size:8pt!important;color:#6b7a70!important;background:#fff!important}
  .sfooter{display:none!important}
  @page{margin:18mm 20mm 26mm;size:A4 portrait}
  @page:first{margin:0}
}
@media screen{.pfooter{display:none!important}}
`
function injectPCSS(){
  if(document.getElementById('vcfo-pcss'))return
  const s=document.createElement('style');s.id='vcfo-pcss';s.textContent=PCSS;document.head.appendChild(s)
}

// ── Window filter (display-only, no recalc) ───────────────────────────────────
function filterByWindow(allSeries=[], window){
  if(!allSeries.length) return allSeries
  const n = window==='1M'?1:window==='3M'?3:window==='6M'?6:window==='YTD'?allSeries.length:allSeries.length
  return allSeries.slice(-n)
}
function periodAvg(series=[]){
  const valid = series.filter(v=>v!=null)
  return valid.length ? valid.reduce((a,b)=>a+b,0)/valid.length : null
}

// ── Tiny SVG line chart ───────────────────────────────────────────────────────
function TrendLine({revSeries=[], npSeries=[], tr}){
  const valid = revSeries.filter(v=>v!=null)
  if(valid.length < 2) return null
  const W=480,H=100,P=14
  const allVals=[...revSeries,...npSeries].filter(v=>v!=null)
  const maxV=Math.max(...allVals,1), minV=Math.min(0,...npSeries.filter(v=>v!=null))
  const tx=(i,tot)=>P+(i/(tot-1))*(W-P*2)
  const ty=v=>H-P-((v-minV)/(maxV-minV||1))*(H-P*2)
  function polyline(series,color){
    const pts=series.map((v,i)=>v!=null?`${tx(i,series.length).toFixed(1)},${ty(v).toFixed(1)}`:null).filter(Boolean)
    if(pts.length<2) return ''
    return `<polyline points="${pts.join(' ')}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" opacity="0.9"/>`
  }
  const svg=[polyline(revSeries,T.accent),polyline(npSeries,T.green)].join('')
  return(
    <div className="trend-box" style={{background:T.card,borderWidth:'1px',borderStyle:'solid',borderColor:T.border,borderRadius:12,padding:'14px 18px',marginBottom:8}}>
      <div style={{fontSize:10,fontWeight:700,color:T.text3,textTransform:'uppercase',letterSpacing:'.08em',marginBottom:10,display:'flex',alignItems:'center',gap:16}}>
        <span style={{color:T.text2}}>{tr('board_trend_title')}</span>
        <span style={{display:'flex',alignItems:'center',gap:5}}><span style={{width:16,height:2,background:T.accent,display:'inline-block',borderRadius:2}}/><span style={{fontSize:9}}>{tr('fc_revenue')}</span></span>
        <span style={{display:'flex',alignItems:'center',gap:5}}><span style={{width:16,height:2,background:T.green,display:'inline-block',borderRadius:2}}/><span style={{fontSize:9}}>{tr('fc_net_profit')}</span></span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} style={{width:'100%',maxHeight:H,display:'block'}} dangerouslySetInnerHTML={{__html:svg}}/>
    </div>
  )
}

// ── Cover ─────────────────────────────────────────────────────────────────────
function CoverPage({company,period,periodCount,health,genAt,tr}){
  const hc=HC[health?.label]||T.text3
  return(
    <div className="cover-page" style={{background:`radial-gradient(ellipse at 28% 38%,rgba(0,212,170,0.09) 0%,transparent 55%),${T.bg}`,minHeight:'auto',display:'flex',flexDirection:'column',justifyContent:'space-between',padding:'40px 56px 36px',borderRadius:16,margin:'0 0 0 0'}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
        <span style={{fontSize:11,fontWeight:800,letterSpacing:'.18em',textTransform:'uppercase',color:T.accent}}>VCFO</span>
        <span style={{fontSize:9,color:T.text3,letterSpacing:'.1em',textTransform:'uppercase'}}>{tr('board_header_label')} · {new Date().getFullYear()}</span>
      </div>
      <div style={{flex:1,display:'flex',flexDirection:'column',justifyContent:'center',paddingTop:28}}>
        <div style={{fontSize:10,color:T.text3,fontWeight:800,letterSpacing:'.2em',textTransform:'uppercase',marginBottom:16}}>— {tr('board_pack_type')} —</div>
        <div style={{fontSize:38,fontWeight:900,color:T.text1,letterSpacing:'-.03em',lineHeight:1.05,marginBottom:14,maxWidth:580}}>{company}</div>
        <div style={{width:48,height:3,background:T.accent,borderRadius:2,marginBottom:20}}/>
        <div style={{fontSize:16,color:T.text2,fontWeight:300,letterSpacing:'.02em'}}>
          {tr('period')}: &nbsp;<strong style={{color:T.text1,fontWeight:700}}>{period}</strong>
          &nbsp;·&nbsp;
          <strong style={{color:T.text1,fontWeight:700}}>{periodCount}</strong>{' '}{tr('total_periods_lbl')}
        </div>
        <div style={{display:'flex',alignItems:'center',gap:14,marginTop:24}}>
          <div style={{display:'flex',flexDirection:'column',alignItems:'center',gap:4,background:`${hc}10`,border:`1px solid ${hc}35`,borderRadius:12,padding:'12px 22px'}}>
            <div style={{fontSize:34,fontWeight:900,color:hc,lineHeight:1}}>{health?.score||0}</div>
            <div style={{fontSize:9,fontWeight:800,color:hc,textTransform:'uppercase',letterSpacing:'.1em'}}>{health?.label||'—'}</div>
            <div style={{fontSize:8,color:T.text3}}>{tr('health_score')}</div>
          </div>
          <div style={{fontSize:12,color:T.text2,lineHeight:1.65,maxWidth:320}}>{tr('cover_health_note')}</div>
        </div>
      </div>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-end',borderTop:`1px solid ${T.border}`,paddingTop:16,marginTop:24}}>
        <div style={{fontSize:10,color:T.text3,lineHeight:1.7}}>
          <div style={{fontWeight:700,color:T.text2,marginBottom:3}}>{tr('generated')}</div>
          <div>{genAt||'—'}</div>
        </div>
        <div style={{fontSize:9,color:T.text3,textTransform:'uppercase',letterSpacing:'.12em',textAlign:'right'}}>
          {tr('cover_confidential')}<br/>{tr('cover_board_only')}
        </div>
      </div>
    </div>
  )
}

// ── Window selector ───────────────────────────────────────────────────────────
function WindowPill({label, active, onClick}){
  return(
    <button onClick={onClick} style={{padding:'5px 14px',borderRadius:20,fontSize:11,fontWeight:700,cursor:'pointer',transition:'all .15s',
      background:active?T.accent:'transparent',color:active?'#000':T.text3,
      border:`1px solid ${active?T.accent:T.border}`,
    }}>{label}</button>
  )
}

// ── Section divider ───────────────────────────────────────────────────────────
function SDiv({n,title,accent=T.accent}){
  return(
    <div className="sdiv" style={{margin:'36px 0 18px',display:'flex',alignItems:'center',gap:12}}>
      <div style={{width:28,height:28,borderRadius:7,flexShrink:0,background:`${accent}15`,border:`1px solid ${accent}35`,display:'flex',alignItems:'center',justifyContent:'center',fontSize:10,fontWeight:900,color:accent,fontFamily:'monospace'}}>§{n}</div>
      <div style={{flex:1,height:1,background:`${accent}18`}}/>
      <div style={{fontSize:11,fontWeight:800,color:T.text2,textTransform:'uppercase',letterSpacing:'.1em',flexShrink:0}}>{title}</div>
      <div style={{flex:1,height:1,background:`${accent}18`}}/>
    </div>
  )
}

// ── Section card ──────────────────────────────────────────────────────────────
function Sec({children,accent=T.accent}){
  return(
    <div className="report-section" style={{background:T.panel,borderWidth:'1px 1px 1px 3px',borderStyle:'solid',borderColor:`${T.border} ${T.border} ${T.border} ${accent}`,borderRadius:14,padding:'20px 24px',marginBottom:8}}>
      {children}
    </div>
  )
}

// ── KPI card ──────────────────────────────────────────────────────────────────
function KpiCard({label,value,full,mom,momLabel,avg,avgLabel,chg,chgLabel,color=T.accent,lang}){
  const sign=mom!=null?(mom>0?'▲':'▼'):''
  const mc=mom!=null?(mom>0?T.green:T.red):T.text3
  return(
    <div className="kpi-card" style={{background:T.card,borderWidth:'2px 1px 1px 1px',borderStyle:'solid',borderColor:`${color} ${T.border} ${T.border} ${T.border}`,borderRadius:13,padding:'16px 18px'}}>
      <div style={{fontSize:9,color:T.text3,fontWeight:700,textTransform:'uppercase',letterSpacing:'.08em',marginBottom:8}}>{label}</div>
      <div className="kpi-val" style={{fontFamily:'var(--font-display,monospace)',fontSize:26,fontWeight:900,color:T.text1,letterSpacing:'-.025em',lineHeight:1,marginBottom:3}}>{value}</div>
      {full&&<div style={{fontSize:9,color:T.text3,fontFamily:'monospace',marginBottom:5,letterSpacing:'.02em'}}>{full}</div>}
      {mom!=null&&<div style={{fontSize:10,fontWeight:700,color:mc,fontFamily:'monospace',marginBottom:3}}>{sign} {formatPctForLang(Math.abs(mom), 1, lang)} {momLabel}</div>}
      {avg!=null&&<div style={{fontSize:9,color:T.text3,fontFamily:'monospace'}}>⌀ {avg} {avgLabel}</div>}
      {chg!=null&&(
        <div style={{fontSize:9,fontWeight:700,color:chg>=0?T.green:T.red,fontFamily:'monospace',marginTop:2}}>
          {chg>=0?'▲ +':'▼ '}{formatPctForLang(Math.abs(chg), 1, lang)} {chgLabel}
        </div>
      )}
    </div>
  )
}

// ── Metric row ────────────────────────────────────────────────────────────────
function MRow({label,value,badge,bc}){
  return(
    <div className="metric-row" style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'9px 0',borderBottom:`1px solid ${T.border}`}}>
      <span style={{fontSize:11,color:T.text2}}>{label}</span>
      <div style={{display:'flex',alignItems:'center',gap:8}}>
        <span style={{fontSize:12,fontWeight:700,color:T.text1,fontFamily:'monospace'}}>{value??'—'}</span>
        {badge&&<span style={{fontSize:8,fontWeight:700,color:bc||T.text3,padding:'1px 6px',borderRadius:10,background:`${bc||T.text3}15`,textTransform:'uppercase',letterSpacing:'.04em'}}>{badge}</span>}
      </div>
    </div>
  )
}

// ── Signal row ────────────────────────────────────────────────────────────────
function SRow({rank,description,severity,color}){
  const clr=color||SC[severity]||T.text3
  return(
    <div className="sig-row" style={{display:'flex',alignItems:'flex-start',gap:10,padding:'10px 0',borderBottom:`1px solid ${T.border}`}}>
      {rank!=null&&<div style={{width:20,height:20,borderRadius:5,flexShrink:0,marginTop:1,background:`${clr}15`,border:`1px solid ${clr}35`,display:'flex',alignItems:'center',justifyContent:'center',fontSize:9,fontWeight:900,color:clr,fontFamily:'monospace'}}>{rank}</div>}
      <div style={{flex:1,fontSize:12,color:T.text2,lineHeight:1.55}}>{description}</div>
      {severity&&<span style={{fontSize:8,fontWeight:800,padding:'2px 6px',borderRadius:20,flexShrink:0,background:`${clr}15`,color:clr,textTransform:'uppercase',letterSpacing:'.05em'}}>{severity}</span>}
    </div>
  )
}

// ── Branch card ───────────────────────────────────────────────────────────────
function BCard({branch,roleKey,alsoKey,accent,tr,momLabel,lang}){
  if(!branch) return null
  return(
    <div className="branch-card" style={{background:T.card,borderWidth:'1px 1px 1px 3px',borderStyle:'solid',borderColor:`${T.border} ${T.border} ${T.border} ${accent}`,borderRadius:12,padding:'14px 16px'}}>
      <div style={{fontSize:9,color:accent,fontWeight:800,textTransform:'uppercase',letterSpacing:'.08em',marginBottom:6}}>
        {tr(roleKey)}
        {alsoKey&&<span style={{color:T.text3,marginLeft:6,fontWeight:600,textTransform:'none',fontSize:8}}>({tr(alsoKey)})</span>}
      </div>
      <div style={{fontSize:15,fontWeight:800,color:T.text1,marginBottom:10}}>{branch.branch_name||branch.name||'—'}</div>
      <div style={{display:'flex',gap:18,flexWrap:'wrap'}}>
        {branch.revenue!=null&&<div><div style={{fontSize:8,color:T.text3,textTransform:'uppercase',letterSpacing:'.06em',marginBottom:2}}>{tr('fc_revenue')}</div><div style={{fontSize:12,fontWeight:700,color:T.text1,fontFamily:'monospace'}}>{formatCompactForLang(branch.revenue, lang)}</div></div>}
        {branch.net_margin!=null&&<div><div style={{fontSize:8,color:T.text3,textTransform:'uppercase',letterSpacing:'.06em',marginBottom:2}}>{tr('prof_net_margin')}</div><div style={{fontSize:12,fontWeight:700,color:branch.net_margin>=0?T.green:T.red,fontFamily:'monospace'}}>{formatPctForLang(branch.net_margin, 1, lang)}</div></div>}
        {branch.mom_revenue_pct!=null&&<div><div style={{fontSize:8,color:T.text3,textTransform:'uppercase',letterSpacing:'.06em',marginBottom:2}}>{momLabel}</div><div style={{fontSize:12,fontWeight:700,color:branch.mom_revenue_pct>=0?T.green:T.red,fontFamily:'monospace'}}>{branch.mom_revenue_pct>0?'▲ ':'▼ '}{formatPctForLang(Math.abs(branch.mom_revenue_pct), 1, lang)}</div></div>}
      </div>
    </div>
  )
}

// ── Export toolbar ────────────────────────────────────────────────────────────
function Toolbar({tr,companyName,period,isBranch}){
  const [busy,setBusy]=useState(false)
  function doPrint(){setBusy(true);setTimeout(()=>{window.print();setBusy(false)},80)}
  const btn=(label,icon,color,fn)=>(
    <button onClick={fn} style={{display:'flex',alignItems:'center',gap:6,padding:'8px 16px',borderRadius:9,fontSize:12,fontWeight:700,cursor:'pointer',background:`${color}14`,color,border:`1px solid ${color}35`,transition:'background .15s'}}
      onMouseEnter={e=>e.currentTarget.style.background=`${color}26`}
      onMouseLeave={e=>e.currentTarget.style.background=`${color}14`}
    >{icon} {label}</button>
  )
  return(
    <div className="export-toolbar no-print" style={{display:'flex',alignItems:'center',gap:10,marginBottom:24,padding:'10px 16px',background:T.panel,borderWidth:'1px',borderStyle:'solid',borderColor:T.border,borderRadius:12}}>
      <span style={{fontSize:11,color:T.text3,marginRight:'auto',fontWeight:600}}>
        📋 {companyName} · {period}
        {isBranch&&<span style={{marginLeft:10,fontSize:10,color:T.accent,fontWeight:800}}>· {tr('branch_mode_label')}</span>}
      </span>
      {btn(busy?tr('print_preparing'):tr('print_report'),'🖨️',T.accent,doPrint)}
      {btn(tr('export_pdf'),'⬇️',T.blue,doPrint)}
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function BoardReport(){
  const {tr,lang}=useLang()
  const {selectedId,selectedCompany}=useCompany()
  const [data,setData]=useState(null)
  const [branches,setBranches]=useState(null)
  const [loading,setLoading]=useState(false)
  const [err,setErr]=useState(null)
  const { window: win, setWindow: setWin } = usePeriodScope()
  const [branchId,setBranchId]=useState('')

  useEffect(()=>{injectPCSS()},[])

  const load=useCallback(async()=>{
    if(!selectedId) return
    setLoading(true);setErr(null)
    try{
      const [rr,br]=await Promise.all([
        fetch(`${API}/analysis/${selectedId}/board-report?lang=${lang||'en'}&window=${win}${branchId?'&branch_id='+branchId:''}`,{headers:auth()}),
        fetch(`${API}/companies/${selectedId}/branch-comparison?lang=${lang||'en'}&window=${win}`,{headers:auth()}),
      ])
      if(!rr.ok){setErr(tr('err_http_status',{status:rr.status}));return}
      setData(await rr.json())
      if(br.ok){const bj=await br.json();if(bj.has_data)setBranches(bj)}
    }catch(e){setErr(e.message)}
    finally{setLoading(false)}
  },[selectedId,lang,win,branchId])

  useEffect(()=>{load()},[load])

  if(!selectedId) return <div style={{padding:48,textAlign:'center',color:T.text3}}><div style={{fontSize:32,marginBottom:12}}>📋</div><div>{tr('no_company_selected')}</div></div>
  if(loading)     return <div style={{padding:48,textAlign:'center',color:T.text3}}><div style={{fontWeight:600}}>{tr('loading')}</div></div>
  if(err)         return <div style={{padding:32}}><div style={{background:`${T.red}12`,border:`1px solid ${T.red}`,borderRadius:10,padding:'14px 18px',color:T.red,fontSize:13}}>⚠ {err}</div></div>
  if(!data)       return null
  const isBranch = Boolean(branchId || data?.branch_id)

  const snap=data.snapshot||{}
  const health=data.health||{}
  const summary=data.summary||''
  const outlook=data.outlook||''
  const risks=data.risks||[]
  const opps=data.opportunities||[]
  const pris=data.priorities||[]
  const highlights=data.highlights||[]
  const majorRisks=data.major_risks||[]
  const costDrivers=data.cost_drivers||{}
  const recs=data.recommendations||[]
  const allRevSeries=data.analysis?.trends?.revenue?.series||[]
  const allNpSeries =data.analysis?.trends?.net_profit?.series||[]
  const revSeries=filterByWindow(allRevSeries,win)
  const npSeries =filterByWindow(allNpSeries,win)
  const companyName=data.company_name||selectedCompany?.name||'—'
  const period=data.period||'—'
  const periodCount=data.period_count||0
  const genAt=data.generated_at?new Date(data.generated_at).toLocaleString():null
  const momLabel=tr('mom_label')
  const prevComp=data?.prev_comparison||{}
  const avgLabel=tr('period_avg_label')
  const deep=data?.deep_intelligence||{}
  const expDeep=deep?.expense_intelligence||{}
  const expDrivers=expDeep?.top_drivers||[]
  const expAnoms=expDeep?.anomalies||[]

  // Period-windowed averages (display only — no recalc)
  const revAvg = periodAvg(revSeries)
  const npAvg  = periodAvg(npSeries)

  // Branch data
  const ranking=branches?.ranking||[]
  const topBranch=ranking[0]||null
  const marginLeader=branches?.margin_leaders?.[0]||null
  const costBranch=ranking.find(b=>b.net_margin!=null&&b.net_margin<10)||null
  const hasBranches=topBranch!=null
  const topId=topBranch?.branch_id
  const marginId=marginLeader?.branch_id
  const costId=costBranch?.branch_id

  // Liquidity/efficiency badges
  const crBadge=snap.current_ratio!=null
    ?snap.current_ratio>=2?{l:tr('ratio_strong'),c:T.green}
     :snap.current_ratio>=1?{l:tr('ratio_adequate'),c:T.accent}
     :{l:tr('ratio_low'),c:T.red}
    :null
  const exBadge=snap.expense_ratio!=null
    ?snap.expense_ratio>70?{l:tr('cost_high'),c:T.red}:{l:tr('cost_controlled'),c:T.green}
    :null

  const WINDOWS=['1M','3M','6M','YTD','ALL']
  const winLabel={
    '1M':tr('window_1m'),'3M':tr('window_3m'),
    '6M':tr('window_6m'),'YTD':tr('window_ytd'),'ALL':tr('window_all')
  }

  return(
    <div className="board-root" style={{background:T.bg,minHeight:'100vh'}}>
      <CoverPage company={companyName} period={period} periodCount={periodCount} health={health} genAt={genAt} tr={tr}/>

      <div style={{padding:'32px 40px',maxWidth:1100,margin:'0 auto'}}>
        <Toolbar tr={tr} companyName={companyName} period={period} isBranch={isBranch}/>

        {/* Window selector */}
        <div className="no-print" style={{display:'flex',alignItems:'center',gap:8,marginBottom:24}}>
          <span style={{fontSize:10,color:T.text3,fontWeight:700,textTransform:'uppercase',letterSpacing:'.08em',marginRight:6}}>{tr('window_label')}</span>
          {WINDOWS.map(w=><WindowPill key={w} label={winLabel[w]} active={win===w} onClick={()=>setWin(w)}/>)}
        </div>

        {/* Branch selector — injected after window pills */}
        {branches?.ranking?.length>0&&(
          <div className='no-print' style={{display:'flex',alignItems:'center',gap:8,marginBottom:16}}>
            <span style={{fontSize:10,color:T.text3,fontWeight:700,textTransform:'uppercase',letterSpacing:'.08em',marginRight:6}}>{tr('branch_filter_label')}</span>
            <WindowPill label={tr('all_branches')} active={!branchId} onClick={()=>setBranchId('')}/>
            {branches.ranking.map(b=>(
              <WindowPill key={b.branch_id} label={b.branch_name} active={branchId===b.branch_id} onClick={()=>setBranchId(b.branch_id)}/>
            ))}
          </div>
        )}

        {/* §1 Executive Summary */}
        {summary&&<>
          <SDiv n={1} title={tr('board_summary')} accent={T.accent}/>
          <Sec accent={T.accent}><p style={{fontSize:14,color:T.text2,lineHeight:1.8,margin:0}}>{summary}</p></Sec>
        </>}

        {/* §2 Financial Snapshot */}
        <SDiv n={2} title={tr('board_snapshot')} accent={T.violet}/>
        <div className="kpi-grid" style={{display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:12,marginBottom:16}}>
          <KpiCard
            label={tr('fc_revenue')} value={formatCompactForLang(snap.revenue, lang)} full={formatFullForLang(snap.revenue, lang)}
            mom={snap.revenue_mom_pct??null} momLabel={momLabel}
            avg={revAvg!=null?formatCompactForLang(revAvg, lang):null} avgLabel={avgLabel}
            chg={prevComp.rev_chg_pct??null} chgLabel={prevComp.label||''}
            color={T.accent}
            lang={lang}
          />
          <KpiCard
            label={tr('fc_net_profit')} value={formatCompactForLang(snap.net_profit, lang)} full={formatFullForLang(snap.net_profit, lang)}
            mom={snap.net_profit_mom_pct??null} momLabel={momLabel}
            avg={npAvg!=null?formatCompactForLang(npAvg, lang):null} avgLabel={avgLabel}
            chg={prevComp.np_chg_pct??null} chgLabel={prevComp.label||''}
            color={snap.net_profit>=0?T.green:T.red}
            lang={lang}
          />
          <KpiCard label={tr('prof_gross_margin')} value={formatPctForLang(snap.gross_margin_pct, 1, lang)} color={T.violet} lang={lang}/>
          <KpiCard label={tr('prof_net_margin')}   value={formatPctForLang(snap.net_margin_pct, 1, lang)}   color={T.blue} lang={lang}/>
        </div>

        {revSeries.length>=2&&<TrendLine revSeries={revSeries} npSeries={npSeries} tr={tr}/>}

        <div className="two-col" style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12,marginBottom:8}}>
          <Sec accent={T.blue}>
            <div style={{fontSize:10,fontWeight:800,color:T.blue,textTransform:'uppercase',letterSpacing:'.08em',marginBottom:12}}>{tr('liquidity_title')}</div>
            <MRow label={tr('kpi_working_capital')} value={formatCompactForLang(snap.working_capital, lang)}/>
            <MRow label={tr('ratio_current_ratio')} value={snap.current_ratio!=null?formatMultipleForLang(snap.current_ratio, 2, lang):null} badge={crBadge?.l} bc={crBadge?.c}/>
            <MRow label={tr('ratio_dso_days')}      value={snap.dso_days!=null?formatDays(snap.dso_days):null}/>
            <MRow label={tr('ratio_ccc_days')}      value={snap.ccc_days!=null?formatDays(snap.ccc_days):null}/>
          </Sec>
          <Sec accent={T.amber}>
            <div style={{fontSize:10,fontWeight:800,color:T.amber,textTransform:'uppercase',letterSpacing:'.08em',marginBottom:12}}>{tr('efficiency_title')}</div>
            <MRow label={tr('prof_op_margin')}          value={formatPctForLang(snap.operating_margin_pct, 1, lang)}/>
            <MRow label={tr('kpi_expense_ratio')}       value={formatPctForLang(snap.expense_ratio, 1, lang)} badge={exBadge?.l} bc={exBadge?.c}/>
            <MRow label={tr('ratio_inventory_turnover')} value={snap.inventory_turnover!=null?formatMultipleForLang(snap.inventory_turnover, 2, lang):null}/>
            <MRow label={tr('ratio_dpo_days')}           value={snap.dpo_days!=null?formatDays(snap.dpo_days):null}/>
          </Sec>
        </div>

        {/* §3 Risks & Opportunities */}
        <SDiv n={3} title={tr('board_risks_opps')} accent={T.red}/>
        <div className="two-col" style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
          <Sec accent={T.red}>
            <div style={{fontSize:10,fontWeight:800,color:T.red,textTransform:'uppercase',letterSpacing:'.08em',marginBottom:12}}>{tr('board_risks_label')}</div>
            {risks.length===0
              ?<p style={{fontSize:12,color:T.text3,fontStyle:'italic',margin:0}}>{tr('no_risks')}</p>
              :risks.map((r,i)=><SRow key={i} description={r.description||r.summary||'—'} severity={r.severity} color={SC[r.severity]}/>)
            }
          </Sec>
          <Sec accent={T.green}>
            <div style={{fontSize:10,fontWeight:800,color:T.green,textTransform:'uppercase',letterSpacing:'.08em',marginBottom:12}}>{tr('board_opps_label')}</div>
            {opps.length===0
              ?<p style={{fontSize:12,color:T.text3,fontStyle:'italic',margin:0}}>{tr('no_opportunities')}</p>
              :opps.map((o,i)=><SRow key={i} description={o.description||'—'} color={T.green}/>)
            }
          </Sec>
        </div>

        {/* §4 Highlights & Recommendations (board-grade) */}
        {(highlights.length>0 || recs.length>0 || costDrivers?.summary) && <>
          <SDiv n={4} title={tr('board_highlights')} accent={T.accent}/>
          <div className="two-col" style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
            <Sec accent={T.accent}>
              <div style={{fontSize:10,fontWeight:800,color:T.accent,textTransform:'uppercase',letterSpacing:'.08em',marginBottom:12}}>
                {tr('board_highlights')}
              </div>
              {highlights.length===0
                ? <p style={{fontSize:12,color:T.text3,fontStyle:'italic',margin:0}}>—</p>
                : highlights.map((h,i)=><SRow key={i} rank={i+1} description={h.message||'—'} color={T.accent}/>)
              }
              {costDrivers?.summary && (
                <div style={{marginTop:10}}>
                  <div style={{fontSize:9,fontWeight:800,color:T.amber,textTransform:'uppercase',letterSpacing:'.08em',marginBottom:6}}>
                    {tr('cost_structure')}
                  </div>
                  <p style={{fontSize:12,color:T.text2,lineHeight:1.6,margin:0}}>{costDrivers.summary}</p>
                </div>
              )}
            </Sec>
            <Sec accent={T.green}>
              <div style={{fontSize:10,fontWeight:800,color:T.green,textTransform:'uppercase',letterSpacing:'.08em',marginBottom:12}}>
                {tr('board_recommendations')}
              </div>
              {recs.length===0
                ? <p style={{fontSize:12,color:T.text3,fontStyle:'italic',margin:0}}>—</p>
                : recs.map((r,i)=><SRow key={i} rank={i+1} description={r.action||'—'} severity={r.priority} color={T.green}/>)
              }
            </Sec>
          </div>
        </>}

        {/* §4.5 Expense Drivers & Anomalies (deep intelligence) */}
        {(expDrivers.length>0 || expAnoms.length>0) && <>
          <SDiv n={4.5} title={tr('board_expense_drivers')} accent={T.violet}/>
          <div className="two-col" style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
            <Sec accent={T.violet}>
              <div style={{fontSize:10,fontWeight:800,color:T.violet,textTransform:'uppercase',letterSpacing:'.08em',marginBottom:12}}>
                {tr('board_top_expense_drivers')}
              </div>
              {expDrivers.length===0
                ? <p style={{fontSize:12,color:T.text3,fontStyle:'italic',margin:0}}>—</p>
                : expDrivers.map((d,i)=>(
                    <SRow key={i} rank={i+1}
                      description={`${tr(d.label_key)||d.category_key}: ${formatPctForLang(d.ratio_pct, 1, lang)} · ${formatCompactForLang(d.amount, lang)}${d.mom_change_pct!=null?` · ${tr('mom_label')} ${d.mom_change_pct>=0?'+':''}${formatPctForLang(Math.abs(d.mom_change_pct), 1, lang)}`:''}`}
                      color={T.violet}/>
                  ))
              }
            </Sec>
            <Sec accent={T.red}>
              <div style={{fontSize:10,fontWeight:800,color:T.red,textTransform:'uppercase',letterSpacing:'.08em',marginBottom:12}}>
                {tr('board_expense_anomalies')}
              </div>
              {expAnoms.length===0
                ? <p style={{fontSize:12,color:T.text3,fontStyle:'italic',margin:0}}>—</p>
                : expAnoms.slice(0,6).map((a,i)=>(
                    <SRow key={i} rank={i+1}
                      description={a.what_happened||a.message||`${a.type||'anomaly'}: ${a.category_key||''}`}
                      severity={a.severity||'warning'}
                      color={SC[a.severity]||T.red}/>
                  ))
              }
            </Sec>
          </div>
        </>}

        {/* §4.75 Financial brain (API brain_pack + structured causes/decisions) */}
        {(() => {
          const brain = data?.brain_pack || {}
          const press = brain.expense_pressure || {}
          const tstats = brain.trend_series_stats || {}
          const profBr = brain.profitability || {}
          const interp = profBr.interpretation || {}
          const sigs = brain.trend_signals || []
          const srcRC = data?.structured_root_causes || []
          const srcDec = data?.structured_decisions || []
          const hasBrain = press?.interpretation || (sigs && sigs.length) || (interp?.notes && interp.notes.length)
            || srcRC.length || srcDec.length
          if (!hasBrain) return null
          return <>
            <SDiv n={4.75} title={tr('board_financial_brain')} accent={T.blue}/>
            <div className="two-col" style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
              <Sec accent={T.blue}>
                <div style={{fontSize:10,fontWeight:800,color:T.blue,textTransform:'uppercase',letterSpacing:'.08em',marginBottom:12}}>
                  {tr('board_cost_pressure')}
                </div>
                {press.pressure_level && (
                  <p style={{fontSize:12,color:T.text2,margin:'0 0 8px'}}>
                    <strong>{tr('board_pressure_level')}:</strong> {press.pressure_level}
                    {press.headline_metrics?.total_cost_ratio_pct != null && (
                      <> · {tr('board_total_cost_ratio')}: {formatPctForLang(press.headline_metrics.total_cost_ratio_pct, 1, lang)}</>
                    )}
                  </p>
                )}
                {press.interpretation && (
                  <p style={{fontSize:12,color:T.text2,lineHeight:1.6,margin:0}}>{press.interpretation}</p>
                )}
                {(interp.notes || []).length > 0 && (
                  <ul style={{margin:'8px 0 0',paddingLeft:18,fontSize:11,color:T.text2,lineHeight:1.5}}>
                    {interp.notes.map((n, i) => <li key={i}>{n}</li>)}
                  </ul>
                )}
                {tstats.revenue_mom_cv_6 != null && (
                  <p style={{fontSize:10,color:T.text3,margin:'8px 0 0'}}>
                    MoM CV (6): revenue {tstats.revenue_mom_cv_6} · profit {tstats.net_profit_mom_cv_6 ?? '—'}
                  </p>
                )}
              </Sec>
              <Sec accent={T.violet}>
                <div style={{fontSize:10,fontWeight:800,color:T.violet,textTransform:'uppercase',letterSpacing:'.08em',marginBottom:12}}>
                  {tr('board_trend_signals')}
                </div>
                {sigs.length === 0
                  ? <p style={{fontSize:12,color:T.text3,fontStyle:'italic',margin:0}}>—</p>
                  : <ul style={{margin:0,paddingLeft:18,fontSize:11,color:T.text2,lineHeight:1.55}}>
                      {sigs.slice(0, 8).map((s, i) => (
                        <li key={i}><strong>{s.type || 'signal'}</strong>{s.metric ? ` (${s.metric})` : ''}{s.value != null ? `: ${s.value}` : ''}</li>
                      ))}
                    </ul>
                }
                {srcRC.length > 0 && (
                  <div style={{marginTop:12}}>
                    <div style={{fontSize:9,fontWeight:800,color:T.red,textTransform:'uppercase',letterSpacing:'.06em',marginBottom:6}}>
                      {tr('board_root_causes')}
                    </div>
                    <ul style={{margin:0,paddingLeft:18,fontSize:11,color:T.text2,lineHeight:1.5}}>
                      {srcRC.slice(0, 5).map((r, i) => (
                        <li key={i}>
                          <strong>{r.cause || r.type}</strong>
                          {r.metric ? ` · ${r.metric}` : ''}{r.direction ? ` · ${r.direction}` : ''}{r.impact_level ? ` · ${r.impact_level}` : ''}
                          {r.what_happened ? ` — ${r.what_happened}` : ''}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {srcDec.length > 0 && (
                  <div style={{marginTop:12}}>
                    <div style={{fontSize:9,fontWeight:800,color:T.green,textTransform:'uppercase',letterSpacing:'.06em',marginBottom:6}}>
                      {tr('board_cfo_decisions')}
                    </div>
                    <ul style={{margin:0,paddingLeft:18,fontSize:11,color:T.text2,lineHeight:1.5}}>
                      {srcDec.slice(0, 5).map((d, i) => (
                        <li key={i}>
                          <strong>{d.title || d.domain}</strong>{d.priority != null ? ` (#${d.priority})` : ''}
                          {d.reason ? ` — ${String(d.reason).slice(0, 120)}${String(d.reason).length > 120 ? '…' : ''}` : ''}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </Sec>
            </div>
          </>
        })()}

        {/* §5 Priorities */}
        <SDiv n={5} title={tr('priorities_label')} accent={T.amber}/>
        <Sec accent={T.amber}>
          {pris.length===0
            ?<p style={{fontSize:12,color:T.text3,fontStyle:'italic',margin:0}}>{tr('no_priorities')}</p>
            :pris.map((p,i)=><SRow key={i} rank={p.rank||i+1} description={p.summary||'—'} severity={p.severity} color={T.amber}/>)
          }
        </Sec>

        {/* §6 Board Risk Register (expanded) */}
        {majorRisks.length>0 && <>
          <SDiv n={6} title={tr('board_risk_register')} accent={T.red}/>
          <Sec accent={T.red}>
            {majorRisks.map((r,i)=><SRow key={i} rank={i+1} description={r.message||'—'} severity={r.severity} color={SC[r.severity]}/>)}
          </Sec>
        </>}

        {/* §7 Branch Summary */}
        {hasBranches&&<>
          <SDiv n={7} title={tr('board_branch_summary')} accent={T.blue}/>
          <div className="branch-grid" style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:12,marginBottom:6}}>
            <BCard branch={topBranch}    roleKey="branch_top_revenue"    alsoKey={topId===costId?'branch_also_cost':null} accent={T.accent} tr={tr} momLabel={momLabel} lang={lang}/>
            {marginLeader&&marginId!==topId
              ?<BCard branch={marginLeader} roleKey="branch_margin_leader" accent={T.green} tr={tr} momLabel={momLabel} lang={lang}/>
              :ranking[1]?<BCard branch={ranking[1]} roleKey="branch_needs_attention" accent={T.amber} tr={tr} momLabel={momLabel} lang={lang}/>:null
            }
            {costBranch&&costId!==topId
              ?<BCard branch={costBranch} roleKey="branch_cost_pressure" accent={T.red} tr={tr} momLabel={momLabel} lang={lang}/>
              :ranking.length>=3?<BCard branch={ranking[ranking.length-1]} roleKey="branch_needs_attention" accent={T.amber} tr={tr} momLabel={momLabel} lang={lang}/>:null
            }
          </div>
          <div style={{fontSize:10,color:T.text3,padding:'4px 2px'}}>
            {tr('branch_count_note')}{branches?.branch_count>0&&` ${branches.branch_count} ${tr('nav_branches')}.`}
          </div>
        </>}

        {/* §8 Outlook */}
        {outlook&&<>
          <SDiv n={hasBranches?8:7} title={tr('board_outlook')} accent={T.blue}/>
          <Sec accent={T.blue}><p style={{fontSize:13,color:T.text2,lineHeight:1.8,margin:0}}>{outlook}</p></Sec>
        </>}

        <div className="sfooter" style={{textAlign:'center',marginTop:40,paddingTop:16,borderTop:`1px solid ${T.border}`,fontSize:10,color:T.text3,opacity:.45}}>
          {tr('board_footer_full')}
        </div>
      </div>

      {/* Print running footer */}
      <div className="pfooter" style={{display:'none',justifyContent:'space-between',alignItems:'center',fontSize:8,color:'#6b7a70'}}>
        <span>{companyName} · {period}</span>
        <span>{tr('board_footer_full')}</span>
        <span>{genAt||''}</span>
      </div>
    </div>
  )
}
