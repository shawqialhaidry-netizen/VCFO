import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { useLang } from '../context/LangContext.jsx'
import { useCompany } from '../context/CompanyContext.jsx'
import CompanySelector from './CompanySelector.jsx'

// Page title keys map route → i18n key
const PAGE_TITLE_KEYS = {
  '/':           'nav_command_center',
  '/upload':     'nav_upload',
  '/statements': 'nav_statements',
  '/analysis':   'nav_drill_analysis',
  '/cfo-ai':     'nav_cfo_ai',
  '/ai-advisor': 'nav_cfo_ai',
  '/executive':  'nav_command_center',
  '/branches':   'nav_drill_branches',
  '/board-report': 'nav_board_report',
  '/members':    'nav_members',
  '/settings':   'nav_settings',
}

function titleKeyForPath(pathname) {
  if (!pathname) return 'nav_command_center'
  if (pathname === '/') return 'nav_command_center'
  if (pathname.startsWith('/analysis')) return 'nav_drill_analysis'
  if (pathname.startsWith('/branches')) return 'nav_drill_branches'
  return PAGE_TITLE_KEYS[pathname] || 'nav_command_center'
}

export default function HeaderBar({ onOpenSidebar, onOpenCfo }) {
  const loc = useLocation()
  const navigate = useNavigate()
  const { lang, tr } = useLang()
  const { auth, logout } = useAuth()
  const { companies, selectedId, setSelectedId, isTrial, isTrialExpired, trialDaysLeft } = useCompany()

  const titleKey = titleKeyForPath(loc.pathname)

  // Locale-aware date
  const localeCode = lang === 'ar' ? 'ar-SA' : lang === 'tr' ? 'tr-TR' : 'en-US'
  const now = new Date().toLocaleDateString(localeCode, {
    weekday: 'short', month: 'short', day: 'numeric', year: 'numeric',
  })

  return (
    <header style={s.bar}>
      {/* ── Hamburger menu button ── */}
      <button
        onClick={onOpenSidebar}
        title="Menu"
        style={{
          width:36, height:36, borderRadius:9, flexShrink:0,
          background:'var(--bg-elevated)', border:'1px solid var(--border)',
          color:'var(--text-secondary)', cursor:'pointer',
          display:'flex', flexDirection:'column', alignItems:'center',
          justifyContent:'center', gap:4,
          transition:'all var(--t)',
        }}
        onMouseEnter={e=>{e.currentTarget.style.borderColor='var(--accent)';e.currentTarget.style.color='var(--accent)'}}
        onMouseLeave={e=>{e.currentTarget.style.borderColor='var(--border)';e.currentTarget.style.color='var(--text-secondary)'}}>
        <span style={{display:'block',width:14,height:1.5,background:'currentColor',borderRadius:2}}/>
        <span style={{display:'block',width:14,height:1.5,background:'currentColor',borderRadius:2}}/>
        <span style={{display:'block',width:10,height:1.5,background:'currentColor',borderRadius:2}}/>
      </button>

      {/* VCFO brand — click to go to landing */}
      <button onClick={() => navigate('/')}
        style={{ display:'flex', alignItems:'center', gap:6, background:'none', border:'none',
          cursor:'pointer', padding:'4px 8px', borderRadius:7,
          transition:'opacity .15s', opacity:.7 }}
        onMouseEnter={e=>e.currentTarget.style.opacity='1'}
        onMouseLeave={e=>e.currentTarget.style.opacity='.7'}>
        <span style={{ fontSize:14, fontWeight:800, color:'var(--accent)', letterSpacing:'-.01em',
          fontFamily:'var(--font-display)' }}>VCFO</span>
      </button>

      {/* Page title + date */}
      <div style={s.titleBlock}>
        <h1 style={s.title}>{tr(titleKey)}</h1>
        <div style={s.date}>{now}</div>
      </div>

      {/* Search */}
      <div style={s.searchWrap}>
        <div style={s.searchIcon}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="2" strokeLinecap="round">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
        </div>
        <input
          style={s.search}
          placeholder={tr('search_placeholder')}
        />
        <kbd style={s.kbd}>⌘K</kbd>
      </div>

      {/* Right actions */}
      <div style={s.actions}>
        <CompanySelector style={s.companySel} />

        {/* ── Trial badge ── */}
        {isTrial && !isTrialExpired && trialDaysLeft !== null && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '5px 12px', borderRadius: 8, fontSize: 11, fontWeight: 700,
            background: trialDaysLeft <= 3 ? 'rgba(248,113,113,.12)' : trialDaysLeft <= 7 ? 'rgba(251,191,36,.10)' : 'rgba(0,212,170,.08)',
            border: `1px solid ${trialDaysLeft <= 3 ? 'rgba(248,113,113,.3)' : trialDaysLeft <= 7 ? 'rgba(251,191,36,.3)' : 'rgba(0,212,170,.2)'}`,
            color: trialDaysLeft <= 3 ? 'var(--red)' : trialDaysLeft <= 7 ? '#fbbf24' : 'var(--accent)',
            whiteSpace: 'nowrap', flexShrink: 0,
          }}>
            ⏱ {tr('trial_days_left_badge', { n: trialDaysLeft })}
          </div>
        )}
        {isTrialExpired && (
          <div style={{
            padding: '5px 12px', borderRadius: 8, fontSize: 11, fontWeight: 700,
            background: 'rgba(248,113,113,.12)', border: '1px solid rgba(248,113,113,.3)',
            color: 'var(--red)', whiteSpace: 'nowrap', flexShrink: 0,
          }}>
            ⛔ {tr('trial_expired_badge')}
          </div>
        )}

        <button style={s.iconBtn}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
            <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
          </svg>
          <span style={s.notifDot} />
        </button>

        {/* AI CFO button */}
        <button
          onClick={onOpenCfo}
          title="AI CFO"
          style={{
            display:'flex', alignItems:'center', gap:6,
            padding:'6px 12px', borderRadius:9,
            background:'linear-gradient(135deg,rgba(0,212,170,0.1),rgba(0,102,255,0.08))',
            borderWidth:'1px', borderStyle:'solid', borderColor:'rgba(0,212,170,0.3)',
            color:'var(--accent)', cursor:'pointer', fontSize:11, fontWeight:700,
            fontFamily:'var(--font-display)', letterSpacing:'0.02em',
            transition:'all 0.2s ease',
          }}
          onMouseEnter={e=>{e.currentTarget.style.background='linear-gradient(135deg,rgba(0,212,170,0.18),rgba(0,102,255,0.14))';e.currentTarget.style.boxShadow='0 0 14px rgba(0,212,170,0.2)'}}
          onMouseLeave={e=>{e.currentTarget.style.background='linear-gradient(135deg,rgba(0,212,170,0.1),rgba(0,102,255,0.08))';e.currentTarget.style.boxShadow='none'}}>
          <span style={{fontSize:14}}>🧠</span>
          <span>AI CFO</span>
        </button>

        <button onClick={logout} title="Logout" style={{
          padding:'6px 12px', borderRadius:8, border:'1px solid var(--border)',
          background:'transparent', color:'var(--text-muted)', fontSize:11,
          cursor:'pointer', fontFamily:'var(--font-display)', fontWeight:600,
        }}>⏻</button>
        <div style={s.avatar} title={auth?.user?.email||''}>
          <span style={s.avatarText}>{(auth?.user?.full_name||auth?.user?.email||'U')[0].toUpperCase()}</span>
        </div>
      </div>
    </header>
  )
}

const s = {
  bar:        { height:62, display:'flex', alignItems:'center', gap:16, padding:'0 28px', borderBottom:'1px solid var(--border)', background:'#0B0F14', position:'sticky', top:0, zIndex:50 },
  titleBlock: { minWidth:200 },
  title:      { fontFamily:'var(--font-display)', fontSize:16, fontWeight:700, color:'var(--text-primary)', letterSpacing:'-0.02em', lineHeight:1 },
  date:       { fontSize:11, color:'var(--text-muted)', marginTop:3, fontFamily:'var(--font-mono)' },
  searchWrap: { flex:1, maxWidth:360, position:'relative', display:'flex', alignItems:'center' },
  searchIcon: { position:'absolute', left:12, top:'50%', transform:'translateY(-50%)', display:'flex' },
  search:     { width:'100%', background:'var(--bg-elevated)', border:'1px solid var(--border)', borderRadius:10, padding:'8px 40px 8px 36px', color:'var(--text-secondary)', fontSize:13, transition:'border var(--t)' },
  kbd:        { position:'absolute', right:10, fontSize:10, color:'var(--text-muted)', background:'var(--bg-surface)', border:'1px solid var(--border)', borderRadius:5, padding:'2px 6px', fontFamily:'var(--font-mono)' },
  actions:    { display:'flex', alignItems:'center', gap:10, marginLeft:'auto' },
  companySel: { background:'var(--bg-elevated)', border:'1px solid var(--border)', borderRadius:10, padding:'7px 12px', color:'var(--text-primary)', fontSize:12, minWidth:160 },
  iconBtn:    { width:36, height:36, borderRadius:9, background:'var(--bg-elevated)', border:'1px solid var(--border)', color:'var(--text-secondary)', display:'flex', alignItems:'center', justifyContent:'center', cursor:'pointer', position:'relative', transition:'all var(--t)' },
  notifDot:   { position:'absolute', top:6, right:7, width:6, height:6, borderRadius:'50%', background:'var(--accent)', boxShadow:'0 0 8px var(--accent)' },
  avatar:     { width:36, height:36, borderRadius:10, background:'linear-gradient(135deg,var(--accent-dim),var(--violet-dim))', border:'1px solid var(--border-accent)', display:'flex', alignItems:'center', justifyContent:'center', cursor:'pointer' },
  avatarText: { fontSize:10, fontWeight:800, color:'var(--accent)', fontFamily:'var(--font-display)', letterSpacing:'0.04em' },
}
