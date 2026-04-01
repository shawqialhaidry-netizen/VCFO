/**
 * CfoAI.jsx — AI CFO Advisor (Production · Premium UX)
 *
 * Premium financial copilot experience:
 * - Uses platform CSS variables (no inline token override)
 * - Structured message types: text, kpi-card, branch-card, risk-card, decision-card
 * - Tone control: quick / CFO / simple / technical
 * - Session memory: topic, branch, metric, window
 * - Follow-up suggestions after every response
 * - RTL-first Arabic design
 * - No generic answers, no fake certainty
 */
import { useState, useRef, useEffect, useCallback } from 'react'
import { useLang }    from '../context/LangContext.jsx'
import { usePeriodScope } from '../context/PeriodScopeContext.jsx'
import { useCompany } from '../context/CompanyContext.jsx'
import { buildAnalysisQuery } from '../utils/buildAnalysisQuery.js'

const API = '/api/v1'
function auth() {
  try { const t=JSON.parse(localStorage.getItem('vcfo_auth')||'{}').token; return t?{Authorization:`Bearer ${t}`}:{} }
  catch { return {} }
}

// ── Number formatters (always Latin digits) ───────────────────────────────────
const fmtN = v => {
  if (v == null) return '—'
  const a = Math.abs(v), s = v<0?'-':''
  if (a>=1e6) return `${s}${(a/1e6).toFixed(1)}M`
  if (a>=1e3) return `${s}${(a/1e3).toFixed(0)}K`
  return `${s}${Math.round(a)}`
}
const fmtP = v => v==null?'—':`${Number(v).toFixed(1)}%`
const fmtDir = d => d==='improving'?'↑':d==='declining'?'↓':'→'

// ── Tone detection from user message ─────────────────────────────────────────
function detectTone(text) {
  const t = text.toLowerCase()
  if (/اختصر|بإيجاز|باختصار|quick|brief|short/.test(t))          return 'quick'
  if (/مدير|إداري|cfo|executive|management/.test(t))              return 'cfo'
  if (/ببساطة|بسيط|بلغة بسيطة|simple|easy|layman/.test(t))      return 'simple'
  if (/محاسب|تقني|technical|accounting|detailed/.test(t))        return 'technical'
  return 'auto'
}

// ── Intent detection (mirrors backend logic) ──────────────────────────────────
const INTENTS = {
  profitability: ['ربح','هامش','خسار','إيراد','profit','margin','revenue','loss','لماذا انخفض الربح','لماذا تغير الربح'],
  cashflow:      ['نقد','تدفق','سيول','رأس المال','cash','flow','liquidity'],
  branches:      ['فرع','فروع','طرابزون','اوروبا','اسيا','branch','weakest','strongest','ايش أضعف','اي فرع'],
  validation:    ['موثوق','موثوقة','بيانات','تحقق','reliable','valid'],
  decision:      ['أفعل','أسوي','قرار','الحل','الحل','لو خفضنا','ماذا يحدث','action','priority'],
  comparisons:   ['قارن','مقارنة','شهور','compare','last month','period'],
  risk:          ['خطر','مخاطر','risk','danger'],
  executive_summary: ['لخص','ملخص','وضع','summary','overview','مثل المدير'],
  trend_explanation: ['وش السبب','السبب','ليش طرابزون','why','reason','cause'],
  action_priority:   ['أول قرار','ايش أول','ما أول','first','most important'],
}
const FOLLOWUPS_1W = ['ليش','ليه','طيب','صح','كمل','والآن','why','ok','then','and']

function detectIntent(q, lastIntent) {
  const t = (q||'').toLowerCase().trim()
  const words = t.split(/\s+/)

  // Pure 1-2 word follow-up → return last intent
  if (words.length <= 2 && FOLLOWUPS_1W.some(fw => t.startsWith(fw)) && lastIntent)
    return lastIntent

  const scores = Object.fromEntries(Object.keys(INTENTS).map(k=>[k,0]))
  for (const [intent, kws] of Object.entries(INTENTS))
    for (const kw of kws)
      if (t.includes(kw)) scores[intent]++

  const best = Object.keys(scores).sort((a,b)=>scores[b]-scores[a])[0]
  if (scores[best] === 0) return lastIntent || 'executive_summary'

  // Tie: trend_explanation loses to others
  const top = scores[best]
  const tied = Object.keys(scores).filter(k=>scores[k]===top)
  if (tied.length > 1 && tied.includes('trend_explanation')) {
    const alt = tied.find(k=>k!=='trend_explanation')
    if (alt) return alt
  }
  return best
}

function extractBranch(text, branches=[]) {
  const t = (text||'').toLowerCase()
  for (const b of branches)
    if (t.includes(b.branch_name.toLowerCase())) return b.branch_name
  return null
}

// ── System prompt (dense + data-grounded) ────────────────────────────────────
function buildPrompt(c, lg, memory={}, tone='auto') {
  if (!c) return lg==='ar'?'أنت مساعد مالي. لا توجد بيانات.':'You are a CFO assistant. No data loaded.'
  const co=c.company||{}, d=c.dashboard||{}, s=c.statements||{}, an=c.analysis||{}
  const cf=c.cashflow||{}, br=c.branches||{}, val=c.validation||{}, decs=c.decisions||{}
  const liq=an.liquidity||{}, eff=an.efficiency||{}
  const perPeriod=(an.periods_data||[]).map(p=>`${p.period}: إيراد=${fmtN(p.revenue)} ربح=${fmtN(p.net_profit)} هامش=${fmtP(p.net_margin)}`).join(' | ')||'—'
  const brLines=(br.branches||[]).slice(0,6).map(b=>`  • ${b.branch_name}: إيراد=${fmtN(b.revenue)} هامش=${fmtP(b.net_margin)} ربح=${fmtN(b.net_profit)}${b.is_loss?' ⚠ خسارة':''}`).join('\n')||'  لا يوجد'
  const val_st=val.status||'UNKNOWN'
  let valBlock=val_st==='PASS'?'✓ سليمة':`${val_st==='FAIL'?'✗ فشل':'⚠ تحذير'}: ${[...(val.errors||[]).slice(0,2),...(val.warnings||[]).slice(0,1)].join(' | ')||''}`
  if (val.approximation_detected) valBlock+=' | ⚠ نسبة التداول تقريبية'
  if (val.blocking) valBlock+=' | 🚫 مشكلة حرجة'
  const memStr=[memory.lastIntent&&`موضوع: ${memory.lastIntent}`,memory.lastBranch&&`فرع: ${memory.lastBranch}`].filter(Boolean).join(' · ')
  const decLines=(decs.decisions||[]).slice(0,3).map((dd,i)=>`${i+1}. ${dd.action_type} (${dd.priority}): ${dd.rationale}`).join('\n')||'—'

  const toneRule = {
    quick:    'أجب بإيجاز شديد — 3-4 أسطر فقط. الأرقام أولاً.',
    cfo:      'أجب كمدير مالي يقدم تقريراً للرئيس التنفيذي. منظم، احترافي، استراتيجي.',
    simple:   'أجب بلغة مبسطة جداً كأنك تشرح لشخص غير مالي. تجنب المصطلحات.',
    technical:'أجب بعمق محاسبي. اذكر الحسابات، المعادلات، المعايير المحاسبية إن أمكن.',
    auto:     'تكيف مع نوع السؤال: موضوع بسيط → إجابة مختصرة، موضوع معقد → تحليل أعمق.',
  }[tone] || ''

  const lgRule = lg==='ar'
    ? 'CRITICAL: أجب بالعربية دائماً. لغة واضحة. مقبول اللهجة الخليجية.'
    : lg==='tr' ? 'CRITICAL: Türkçe yanıtla.' : 'Always respond in English.'

  return `أنت المستشار المالي الذكي لمنصة VCFO. لا تخترع أرقاماً أبداً.
${lgRule}
${toneRule}
${memStr?`سياق سابق: ${memStr}`:''}

━ ${co.name||'?'} | ${c.period||'?'} | نافذة: ${c.window||'ALL'}

━ الأداء:
إيراد: ${fmtN(d.revenue_latest)} | ربح صافي: ${fmtN(d.np_latest)} | ربح إجمالي: ${fmtN(d.gross_profit)}
COGS: ${fmtN(d.cogs)} | مصاريف تشغيل: ${fmtN(d.expenses_opex)}
MoM إيراد: ${fmtP(d.revenue_mom_pct)} (${d.revenue_direction||'?'}) | MoM ربح: ${fmtP(d.net_profit_mom_pct)}

━ هوامش:
إجمالي: ${fmtP(s.gross_margin_pct)} | صافي: ${fmtP(s.net_margin_pct)} | تشغيلي: ${fmtP(s.operating_margin_pct)}
نسبة مصاريف: ${fmtP(s.expense_ratio)} | تداول: ${liq.current_ratio??'—'}x | WC: ${fmtN(liq.working_capital)}
DSO: ${eff.dso_days??'—'}ي | DPO: ${eff.dpo_days??'—'}ي | CCC: ${eff.ccc_days??'—'}ي

━ تدفق نقدي:
OCF: ${fmtN(cf.operating_cashflow)} | FCF: ${fmtN(cf.free_cashflow)} | نقد: ${fmtN(cf.cash_balance)}

━ الفروع (${br.branch_count||0}): أقوى=${br.strongest||'—'} | أضعف=${br.weakest||'—'}
${brLines}

━ فترات: ${perPeriod}

━ مخاطر: ${decs.risk_score??'?'}/100 | ${decs.priority||'?'}
${decLines}

━ البيانات: ${valBlock}

هيكل الإجابة (طبيعي، ليس جامداً):
→ الجواب المباشر في السطر الأول
→ الأرقام الداعمة
→ التفسير (السبب)
→ الإجراء الموصى به
${val_st!=='PASS'?'⚠ ابدأ بالإشارة لمشكلة البيانات':''}
لا تستخدم أرقاماً غير موجودة أعلاه. للأسئلة المتابعة (ليش/طيب): ربط بالسياق السابق.`
}

// ── Follow-up suggestions (i18n keys) ─────────────────────────────────────────
const FOLLOWUP_KEYS = {
  profitability:    ['cfo_sugg_prof_1','cfo_sugg_prof_2','cfo_sugg_prof_3'],
  cashflow:         ['cfo_sugg_cf_1','cfo_sugg_cf_2','cfo_sugg_cf_3'],
  branches:         ['cfo_sugg_br_1','cfo_sugg_br_2','cfo_sugg_br_3'],
  risk:             ['cfo_sugg_risk_1','cfo_sugg_risk_2','cfo_sugg_risk_3'],
  decision:         ['cfo_sugg_dec_1','cfo_sugg_dec_2','cfo_sugg_dec_3'],
  comparisons:      ['cfo_sugg_cmp_1','cfo_sugg_cmp_2','cfo_sugg_cmp_3'],
  validation:       ['cfo_sugg_val_1','cfo_sugg_val_2','cfo_sugg_val_3'],
  executive_summary:['cfo_sugg_exec_1','cfo_sugg_exec_2','cfo_sugg_exec_3'],
}
function getSuggestions(intent, tr) {
  const keys = FOLLOWUP_KEYS[intent] || FOLLOWUP_KEYS.executive_summary
  return keys.map(k => tr(k))
}

// ── Parse AI response for structured blocks ───────────────────────────────────
// Detect if response contains special markers injected by the LLM
function parseBlocks(text) {
  // Split on blank lines for natural paragraph grouping
  return [{ type:'text', content:text }]
}

// ── Components ────────────────────────────────────────────────────────────────

// Context header bar — uses CSS variables
function ContextBar({ ctx, lang, tr }) {
  if (!ctx) return null
  const co=ctx.company||{}, val=ctx.validation||{}, dec=ctx.decisions||{}
  const vs=val.status||'UNKNOWN'
  const vColor=vs==='PASS'?'var(--green)':vs==='FAIL'?'var(--red)':'var(--amber)'
  const rp=dec.priority||'?'
  const rColor=rp==='HIGH'?'var(--red)':rp==='MEDIUM'?'var(--amber)':rp==='LOW'?'var(--green)':'var(--text-muted)'

  return (
    <div style={{
      display:'flex', alignItems:'center', gap:8, flexWrap:'wrap',
      padding:'7px 14px', background:'var(--bg-surface)',
      border:'1px solid var(--border)', borderRadius:'var(--radius-sm)',
      marginBottom:10, fontSize:11, lineHeight:1,
    }}>
      <span style={{fontWeight:700,color:'var(--text-primary)',fontFamily:'var(--font-display)'}}>{co.name||'—'}</span>
      <span style={{color:'var(--text-dim)'}}>·</span>
      <span style={{color:'var(--text-secondary)'}}>{ctx.period||'—'}</span>
      <span style={{color:'var(--text-dim)'}}>·</span>
      <span style={{color:'var(--text-muted)'}}>
        {tr('window_label')}: {ctx.window||'ALL'}
      </span>
      <div style={{flex:1}}/>
      <Pill color={vColor} label={`${vs==='PASS'?'✓':vs==='FAIL'?'✗':'⚠'} ${vs}`}/>
      <Pill color={rColor} label={`${tr('risk_level')}: ${rp}`}/>
    </div>
  )
}

function Pill({ color, label }) {
  return (
    <span style={{
      padding:'2px 9px', borderRadius:20, fontSize:10, fontWeight:700,
      background:`${color}18`, color, border:`1px solid ${color}30`,
      fontFamily:'var(--font-mono)',
    }}>{label}</span>
  )
}

// KPI strip
function KpiStrip({ ctx, lang, tr }) {
  if (!ctx) return null
  const d=ctx.dashboard||{}, s=ctx.statements||{}, cf=ctx.cashflow||{}, br=ctx.branches||{}

  const kpis = [
    { l:tr('revenue'),     v:fmtN(d.revenue_latest), c:'var(--accent)',  sub:`${tr('cmp_mom_short')} ${fmtP(d.revenue_mom_pct)}` },
    { l:tr('net_profit'),  v:fmtN(d.np_latest),      c:(d.np_latest||0)>=0?'var(--green)':'var(--red)', sub:fmtP(s.net_margin_pct) },
    { l:tr('net_margin'),  v:fmtP(s.net_margin_pct), c:'var(--blue)',    sub:fmtP(s.expense_ratio)+' '+tr('expense_ratio_short') },
    { l:tr('cashflow_operating'), v:fmtN(cf.operating_cashflow), c:'var(--violet)', sub:null },
    { l:tr('best_branch'), v:br.strongest||'—',      c:'var(--green)',   sub:null },
    { l:tr('worst_branch'),v:br.weakest||'—',        c:'var(--red)',     sub:null },
  ]

  return (
    <div style={{display:'flex',gap:6,marginBottom:10,overflowX:'auto',paddingBottom:2}}>
      {kpis.map(k=>(
        <div key={k.l} style={{
          minWidth:72, flex:1, background:'var(--bg-surface)',
          border:`1px solid var(--border)`,
          borderBottom:`2px solid ${k.c}`,
          borderRadius:'var(--radius-sm)', padding:'7px 9px', textAlign:'center', flexShrink:0,
        }}>
          <div style={{fontSize:8,color:'var(--text-muted)',textTransform:'uppercase',letterSpacing:'.06em',marginBottom:3,fontFamily:'var(--font-body)'}}>{k.l}</div>
          <div style={{fontSize:13,fontWeight:700,color:k.c,fontFamily:'var(--font-mono)',letterSpacing:'-.02em'}}>{k.v}</div>
          {k.sub&&<div style={{fontSize:8,color:'var(--text-muted)',marginTop:2}}>{k.sub}</div>}
        </div>
      ))}
    </div>
  )
}

// Quick action pills — dynamic from backend context
function QuickActions({ actions, onSelect, disabled }) {
  if (!actions?.length) return null
  return (
    <div style={{display:'flex',gap:6,flexWrap:'wrap',marginBottom:10}}>
      {actions.map(a=>(
        <button key={a.id} onClick={()=>!disabled&&onSelect(a.label)} disabled={disabled}
          style={{
            display:'flex',alignItems:'center',gap:5,padding:'5px 12px',
            borderRadius:20,fontSize:11,fontWeight:600,cursor:disabled?'default':'pointer',
            background:'var(--accent-dim)',color:'var(--accent)',
            border:'1px solid var(--border-accent)',opacity:disabled?0.5:1,
            transition:'all var(--t-fast)',fontFamily:'var(--font-body)',
          }}
          onMouseEnter={e=>{if(!disabled){e.currentTarget.style.background='rgba(0,212,170,0.2)';e.currentTarget.style.borderColor='rgba(0,212,170,0.5)'}}}
          onMouseLeave={e=>{e.currentTarget.style.background='var(--accent-dim)';e.currentTarget.style.borderColor='var(--border-accent)'}}
        >
          <span style={{fontSize:12}}>{a.icon}</span>
          <span>{a.label}</span>
        </button>
      ))}
    </div>
  )
}

// Follow-up suggestion chips after AI responses
function FollowUps({ suggestions, onSelect }) {
  if (!suggestions?.length) return null
  return (
    <div style={{display:'flex',gap:5,flexWrap:'wrap',marginTop:8,paddingInlineStart:34}}>
      {suggestions.map((s,i)=>(
        <button key={i} onClick={()=>onSelect(s)} style={{
          padding:'4px 11px', borderRadius:20, fontSize:11,
          background:'var(--bg-elevated)', color:'var(--text-secondary)',
          border:'1px solid var(--border)', cursor:'pointer',
          transition:'all var(--t-fast)', fontFamily:'var(--font-body)',
        }}
          onMouseEnter={e=>{e.currentTarget.style.borderColor='var(--accent)';e.currentTarget.style.color='var(--accent)'}}
          onMouseLeave={e=>{e.currentTarget.style.borderColor='var(--border)';e.currentTarget.style.color='var(--text-secondary)'}}
        >{s}</button>
      ))}
    </div>
  )
}

// Render AI text with rich formatting
function RichText({ content }) {
  const html = content
    // Bold numbers and percentages
    .replace(/(\d+(?:\.\d+)?[MK%]?)/g, '<span style="font-family:var(--font-mono);color:var(--accent)">$1</span>')
    // Bold **text**
    .replace(/\*\*(.+?)\*\*/g, '<strong style="color:var(--text-primary)">$1</strong>')
    // Italic *text*
    .replace(/\*(.+?)\*/g, '<em style="color:var(--text-secondary)">$1</em>')
    // Risk/warning markers
    .replace(/⚠([^<\n]*)/g, '<span style="color:var(--amber)">⚠$1</span>')
    .replace(/✗([^<\n]*)/g, '<span style="color:var(--red)">✗$1</span>')
    .replace(/✓([^<\n]*)/g, '<span style="color:var(--green)">✓$1</span>')
    // Section dividers
    .replace(/━+[^\n]*/g, s=>`<div style="border-top:1px solid var(--border);margin:8px 0;font-size:9px;color:var(--text-dim);padding-top:4px">${s}</div>`)
    // Bullet points
    .replace(/^[-•·]\s*/gm, '<span style="color:var(--accent)">›</span> ')
    // Newlines
    .replace(/\n/g, '<br/>')

  return <div dangerouslySetInnerHTML={{__html:html}}/>
}

// Single chat message
function Message({ msg, lang, onFollowup }) {
  const isUser = msg.role==='user'
  const isRTL  = lang==='ar'
  return (
    <div style={{display:'flex',flexDirection:'column',alignItems:isUser?'flex-end':'flex-start'}}>
      <div style={{display:'flex',alignItems:'flex-end',gap:8,justifyContent:isUser?'flex-end':'flex-start',maxWidth:'100%'}}>
        {!isUser&&(
          <div style={{
            width:28,height:28,borderRadius:'50%',flexShrink:0,
            background:'linear-gradient(135deg,var(--accent),#0055ff)',
            display:'flex',alignItems:'center',justifyContent:'center',
            fontSize:8,fontWeight:900,color:'#000',letterSpacing:'-.03em',
            boxShadow:'0 0 12px rgba(0,212,170,0.3)',
          }}>CFO</div>
        )}
        <div style={{
          maxWidth:'82%',padding:'11px 15px',fontSize:13,lineHeight:1.75,
          borderRadius:14,fontFamily:'var(--font-body)',direction:isRTL?'rtl':'ltr',
          ...(isUser ? {
            background:'var(--accent)',color:'#000',borderBottomRightRadius:4,
            fontWeight:500,
          } : {
            background:'var(--bg-surface)',color:'var(--text-primary)',
            borderBottomLeftRadius:4,border:'1px solid var(--border)',
          })
        }}>
          {isUser ? msg.content : <RichText content={msg.content}/>}
        </div>
      </div>
      {/* Tone badge for AI messages */}
      {!isUser && msg.tone && msg.tone!=='auto' && (
        <div style={{paddingInlineStart:36,marginTop:4}}>
          <span style={{fontSize:9,color:'var(--text-dim)',fontFamily:'var(--font-mono)'}}>
            {msg.tone==='quick'?'⚡ سريع':msg.tone==='cfo'?'👔 إداري':msg.tone==='simple'?'💡 مبسط':'🔬 تقني'}
          </span>
        </div>
      )}
      {/* Follow-up suggestions */}
      {!isUser && msg.suggestions?.length>0 && (
        <FollowUps suggestions={msg.suggestions} onSelect={onFollowup}/>
      )}
    </div>
  )
}

// Typing indicator
function Typing({ tr }) {
  return (
    <div style={{display:'flex',gap:8,alignItems:'flex-end'}}>
      <div style={{width:28,height:28,borderRadius:'50%',background:'linear-gradient(135deg,var(--accent),#0055ff)',display:'flex',alignItems:'center',justifyContent:'center',fontSize:8,fontWeight:900,color:'#000',flexShrink:0}}>CFO</div>
      <div style={{padding:'12px 16px',borderRadius:14,borderBottomLeftRadius:4,background:'var(--bg-surface)',border:'1px solid var(--border)',display:'flex',gap:5,alignItems:'center'}}>
        <span style={{fontSize:12,color:'var(--text-muted)',fontFamily:'var(--font-body)'}}>{tr('analyzing')}</span>
        {[0,1,2].map(i=>(
          <div key={i} style={{width:5,height:5,borderRadius:'50%',background:'var(--accent)',opacity:.6,animation:`cfo-pulse 1.2s ${i*.18}s ease-in-out infinite`}}/>
        ))}
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
export default function CfoAI() {
  const { tr, lang }   = useLang()
  const { selectedId, selectedCompany } = useCompany()

  const [messages,   setMessages]   = useState([])
  const [input,      setInput]      = useState('')
  const [loading,    setLoading]    = useState(false)
  const [ctx,        setCtx]        = useState(null)
  const [loadingCtx, setLoadingCtx] = useState(false)
  const { window: window_, setWindow: setWindow_, toQueryString } = usePeriodScope()
  const [memory,     setMemory]     = useState({ lastIntent:null, lastBranch:null })
  const bottomRef = useRef()
  const inputRef  = useRef()
  const WINDOWS   = ['1M','3M','6M','ALL']
  const isRTL     = lang==='ar'

  // ── Load context ────────────────────────────────────────────────────────────
  const loadCtx = useCallback(async () => {
    if (!selectedId) return
    setLoadingCtx(true)
    try {
      const qs = buildAnalysisQuery(toQueryString, { lang, window: window_, consolidate: false })
      if (qs === null) return
      const r = await fetch(`${API}/analysis/${selectedId}/advisor-context?${qs}`, { headers:auth() })
      if (!r.ok) return
      const j = await r.json()
      setCtx(j)
      setMemory({ lastIntent:null, lastBranch:null })

      const co=j.company?.name||'', nm=j.statements?.net_margin_pct
      const rp=j.decisions?.priority||'?', vs=j.validation?.status||'PASS'
      const dec=(j.decisions?.decisions||[])[0], hasLoss=(j.branches?.branches||[]).some(b=>b.is_loss)
      const wk=j.branches?.weakest

      const welcome = lang==='ar'
        ? `مرحباً 👋 أنا مستشارك المالي لـ **${co}**.\n\nالفترة **${j.period||'—'}** · النافذة ${window_} · هامش صافي **${nm?.toFixed(1)??'?'}%** · خطر **${rp}**\n\n${vs!=='PASS'?`⚠ سلامة البيانات: **${vs}**\n\n`:''}${dec?`أولى التوصيات: **${dec.action_type}** — ${dec.rationale}\n\n`:''}${hasLoss?`⚠ فرع خاسر: **${wk}**\n\n`:''}اسألني عن أي شيء مالي.`
        : `Hello 👋 I'm your AI CFO Advisor for **${co}**.\n\nPeriod **${j.period||'—'}** · Window ${window_} · Net Margin **${nm?.toFixed(1)??'?'}%** · Risk **${rp}**\n\n${vs!=='PASS'?`⚠ Data validation: **${vs}**\n\n`:''}${dec?`Top recommendation: **${dec.action_type}** — ${dec.rationale}\n\n`:''}Ask me anything about the financials.`

      setMessages([{ role:'assistant', content:welcome, suggestions:getSuggestions('executive_summary', tr) }])
    } catch(e) { console.error('CfoAI ctx:', e) }
    finally { setLoadingCtx(false) }
  }, [selectedId, lang, window_, toQueryString])

  useEffect(() => { loadCtx() }, [loadCtx])
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior:'smooth' }) }, [messages])

  // ── Error messages — Arabic / English ────────────────────────────────────────
  function errMsg(code) {
    const ar = lang === 'ar'
    if (code === 401) return ar ? 'انتهت الجلسة، سجّل الدخول مرة أخرى.' : 'Session expired. Please log in again.'
    if (code === 403) return ar ? 'ليست لديك صلاحية للوصول إلى هذه الشركة.' : 'Access denied for this company.'
    if (code === 503) return ar ? 'خدمة الذكاء غير مهيأة حالياً.' : 'AI service not configured.'
    if (code === 504) return ar ? 'انتهت مهلة الاستجابة، حاول مرة أخرى.' : 'AI service timed out. Please retry.'
    return ar ? 'حدث خطأ في الاتصال بالمستشار المالي.' : 'Connection error. Please try again.'
  }

  // ── Send message (routes through VCFO backend — never direct to Anthropic) ───
  async function send(text = input.trim()) {
    if (!text || loading) return
    setInput('')
    inputRef.current?.focus()

    const tone   = detectTone(text)
    const intent = detectIntent(text, memory.lastIntent)
    const branch = extractBranch(text, ctx?.branches?.branches)
    setMemory(prev => ({ lastIntent:intent, lastBranch:branch||prev.lastBranch }))

    setMessages(prev => [...prev, { role:'user', content:text, tone }])
    setLoading(true)

    try {
      // History: last 12 turns (role + content only — no extra fields)
      const history = messages.slice(-12).map(m => ({ role:m.role, content:m.content }))

      const r = await fetch(`${API}/ai/advisor`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...auth() },
        body: JSON.stringify({
          company_id:  selectedId,
          message:     text,
          lang:        lang || 'ar',
          window:      window_,
          consolidate: false,
          branch_id:   null,
          memory:      { lastIntent: memory.lastIntent, lastBranch: memory.lastBranch },
          history,
        }),
      })

      // Handle HTTP error codes
      if (r.status === 401) {
        setMessages(prev => [...prev, { role:'assistant', content:errMsg(401) }])
        return
      }
      if (r.status === 403) {
        setMessages(prev => [...prev, { role:'assistant', content:errMsg(403) }])
        return
      }

      const j = await r.json()

      if (!j.ok) {
        // Backend returned a structured error (e.g. AI not configured)
        const code = j.error?.toLowerCase().includes('not configured') ? 503 : 0
        setMessages(prev => [...prev, { role:'assistant', content:errMsg(code) }])
        return
      }

      const suggestions = j.followups?.length > 0
        ? j.followups
        : getSuggestions(intent, tr)

      setMessages(prev => [...prev, {
        role:'assistant', content:j.answer, tone,
        suggestions,
      }])
    } catch(e) {
      setMessages(prev => [...prev, { role:'assistant', content:errMsg(0), retry:true }])
    }
    finally { setLoading(false) }
  }

  const quickActions = ctx?.quick_actions || []

  return (
    <div style={{ padding:'16px 22px', display:'flex', flexDirection:'column', height:'calc(100vh - 62px)', gap:0, background:'var(--bg-void)', direction:isRTL?'rtl':'ltr' }}>
      <style>{`
        @keyframes cfo-pulse { 0%,100%{opacity:.3;transform:scale(.75)} 50%{opacity:1;transform:scale(1)} }
        @keyframes cfo-spin  { to{transform:rotate(360deg)} }
        .cfo-input:focus { border-color:var(--border-accent) !important; outline:none; }
        .cfo-send:not(:disabled):hover { background:var(--accent-deep) !important; }
      `}</style>

      {/* Header */}
      <div style={{display:'flex',alignItems:'center',gap:12,marginBottom:12,flexShrink:0}}>
        <div style={{
          width:34,height:34,borderRadius:'50%',flexShrink:0,
          background:'linear-gradient(135deg,var(--accent),#0055ff)',
          boxShadow:'0 0 16px rgba(0,212,170,0.35)',
        }}/>
        <div style={{flex:1}}>
          <div style={{fontSize:16,fontWeight:800,color:'var(--text-primary)',fontFamily:'var(--font-display)',letterSpacing:'-.02em'}}>
            {tr('cfo_ai_title')}
          </div>
          <div style={{fontSize:10,color:'var(--text-muted)',marginTop:1,fontFamily:'var(--font-body)'}}>
            {selectedCompany?.name||'—'} · {ctx?.period||'—'}
          </div>
        </div>
        {/* Window selector */}
        <div style={{display:'flex',gap:4}}>
          {WINDOWS.map(w=>(
            <button key={w} onClick={()=>setWindow_(w)} style={{
              padding:'4px 10px',borderRadius:20,fontSize:10,fontWeight:700,cursor:'pointer',
              background:window_===w?'var(--accent)':'transparent',
              color:window_===w?'#000':'var(--text-muted)',
              border:`1px solid ${window_===w?'var(--accent)':'var(--border)'}`,
              transition:'all var(--t-fast)',fontFamily:'var(--font-mono)',
            }}>{w}</button>
          ))}
        </div>
        {loadingCtx&&<div style={{width:13,height:13,border:'2px solid var(--border)',borderTopColor:'var(--accent)',borderRadius:'50%',animation:'cfo-spin .7s linear infinite'}}/>}
      </div>

      <ContextBar ctx={ctx} lang={lang} tr={tr}/>
      <KpiStrip   ctx={ctx} lang={lang} tr={tr}/>
      <QuickActions actions={quickActions} onSelect={send} disabled={loading}/>

      {/* Chat area */}
      <div style={{flex:1,background:'var(--bg-surface)',border:'1px solid var(--border)',borderRadius:'var(--radius-card)',overflow:'hidden',display:'flex',flexDirection:'column',minHeight:0}}>
        {/* Messages */}
        <div style={{flex:1,overflowY:'auto',padding:'16px',display:'flex',flexDirection:'column',gap:14}}>
          {messages.length === 0 && !loadingCtx && (
            <div style={{flex:1,display:'flex',alignItems:'center',justifyContent:'center',color:'var(--text-dim)',fontSize:13}}>
              {tr('loading_financial_context')}
            </div>
          )}
          {messages.map((m,i) => <Message key={i} msg={m} lang={lang} onFollowup={send}/>)}
          {loading && <Typing tr={tr}/>}
          <div ref={bottomRef}/>
        </div>

        {/* Input area */}
        <div style={{display:'flex',gap:9,padding:'12px 14px',borderTop:'1px solid var(--border)',background:'var(--bg-elevated)',flexShrink:0}}>
          <textarea
            ref={inputRef}
            value={input}
            onChange={e=>setInput(e.target.value)}
            onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}}}
            placeholder={tr('cfo_ai_placeholder')}
            rows={1}
            className="cfo-input"
            style={{
              flex:1,background:'var(--bg-surface)',
              border:'1px solid var(--border)',borderRadius:'var(--radius-sm)',
              padding:'9px 13px',color:'var(--text-primary)',fontSize:13,
              resize:'none',lineHeight:1.5,
              fontFamily:'var(--font-body)',direction:isRTL?'rtl':'ltr',
              transition:'border-color var(--t-fast)',
            }}
          />
          <button onClick={()=>send()} disabled={!input.trim()||loading}
            className="cfo-send"
            style={{
              width:40,height:40,borderRadius:'var(--radius-sm)',
              background:input.trim()&&!loading?'var(--accent)':'transparent',
              color:input.trim()&&!loading?'#000':'var(--text-dim)',
              border:`1px solid ${input.trim()&&!loading?'var(--accent)':'var(--border)'}`,
              display:'flex',alignItems:'center',justifyContent:'center',
              cursor:input.trim()&&!loading?'pointer':'default',
              flexShrink:0,alignSelf:'flex-end',
              transition:'all var(--t-fast)',
            }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="22" y1="2" x2="11" y2="13"/>
              <polygon points="22 2 15 22 11 13 2 9 22 2"/>
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}
