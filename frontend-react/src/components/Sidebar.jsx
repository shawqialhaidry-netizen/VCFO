import { NavLink, useLocation } from 'react-router-dom'
import { useLang } from '../context/LangContext.jsx'
import { useCompany } from '../context/CompanyContext.jsx'
import { LANGUAGES } from '../i18n/index.js'

const NAV = [
  { to: '/',           key: 'nav_command_center', icon: <IcoDash />,   accent: 'var(--accent)'  },
  { to: '/upload',     key: 'nav_upload',       icon: <IcoUpload />, accent: 'var(--blue)'    },
  { to: '/statements', key: 'nav_statements',   icon: <IcoStmt />,   accent: 'var(--violet)'  },
  { to: '/board-report',key: 'nav_board_report',  icon: <IcoBoard />,  accent: 'var(--amber)'   },
  { to: '/ai-advisor',  key: 'nav_cfo_ai',        icon: <IcoAI />,     accent: 'var(--accent)'  },
  { to: '/members',     key: 'nav_members',       icon: <IcoMembers/>, accent: 'var(--violet)'  },
  { to: '/settings',   key: 'nav_settings',     icon: <IcoSettings/>,accent: 'var(--text-muted)'},
]

export default function Sidebar({ open, onClose }) {
  const { tr, lang, setLang } = useLang()
  const { selectedCompany }   = useCompany()
  const loc = useLocation()

  return (
    <aside
      className="app-sidebar"
      style={{...s.aside, transform: open ? 'translateX(0)' : 'translateX(-100%)'}}
    >
      <div style={s.topLine} />
      {/* Close button */}
      <button
        onClick={onClose}
        style={{
          position:'absolute', top:12, right:12,
          width:28, height:28, borderRadius:7,
          background:'rgba(255,255,255,0.06)',
          border:'1px solid var(--border)',
          color:'var(--text-muted)', cursor:'pointer',
          display:'flex', alignItems:'center', justifyContent:'center',
          fontSize:14, lineHeight:1, zIndex:1,
          transition:'background .15s',
        }}
        onMouseEnter={e=>e.currentTarget.style.background='rgba(255,255,255,0.12)'}
        onMouseLeave={e=>e.currentTarget.style.background='rgba(255,255,255,0.06)'}>
        ✕
      </button>

      {/* Logo */}
      <div style={s.logo}>
        <div style={s.logoOrb}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path d="M12 2L2 7l10 5 10-5-10-5z" stroke="var(--accent)" strokeWidth="1.5" strokeLinejoin="round"/>
            <path d="M2 17l10 5 10-5" stroke="var(--accent)" strokeWidth="1.5" strokeLinejoin="round" opacity="0.6"/>
            <path d="M2 12l10 5 10-5" stroke="var(--accent)" strokeWidth="1.5" strokeLinejoin="round" opacity="0.8"/>
          </svg>
        </div>
        <div>
          <div style={s.logoName}>VCFO</div>
          {/* tr('exec_intelligence') */}
          <div style={s.logoSub}>{tr('exec_intelligence')}</div>
        </div>
      </div>

      {/* Company chip */}
      {selectedCompany && (
        <div style={s.companyChip}>
          <div style={s.companyDot} />
          <span style={s.companyName}>{selectedCompany.name}</span>
        </div>
      )}

      {/* Nav */}
      <nav style={s.nav}>
        <div style={s.sectionLabel}>{tr('navigation')}</div>
        {NAV.map(item => {
          const isActive = item.to === '/'
            ? loc.pathname === '/'
            : loc.pathname.startsWith(item.to)
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              onClick={onClose}
              style={() => ({ ...s.link, ...(isActive ? s.linkActive : {}) })}
            >
              <span style={{ ...s.linkIcon, color: isActive ? item.accent : 'var(--text-muted)' }}>
                {item.icon}
              </span>
              <span style={{ color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                {tr(item.key)}
              </span>
              {isActive && (
                <div style={{ ...s.activeBar, background: item.accent, boxShadow: `0 0 10px ${item.accent}` }} />
              )}
            </NavLink>
          )
        })}
      </nav>

      <div style={{ flex: 1 }} />

      {/* Language switcher */}
      <div style={s.langSection}>
        <div style={s.sectionLabel}>{tr('language')}</div>
        <div style={s.langRow}>
          {LANGUAGES.map(l => (
            <button
              key={l.code}
              onClick={() => setLang(l.code)}
              style={{ ...s.langBtn, ...(lang === l.code ? s.langBtnActive : {}) }}
            >
              {l.label}
            </button>
          ))}
        </div>
      </div>

      {/* Status footer */}
      <div style={s.footer}>
        <div style={s.statusPulse} className="pulse" />
        <div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', fontWeight: 600 }}>
            {tr('system_online')}
          </div>
          <div style={{ fontSize: 10, color: 'var(--accent)', fontFamily: 'var(--font-mono)', marginTop: 1 }}>
            {tr('system_version')}
          </div>
        </div>
      </div>
    </aside>
  )
}

/* ── Icons ── */
function IcoDash()   { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/></svg> }
function IcoUpload() { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg> }
function IcoStmt()   { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="8" y1="8" x2="16" y2="8"/><line x1="8" y1="12" x2="16" y2="12"/><line x1="8" y1="16" x2="12" y2="16"/></svg> }
function IcoBoard()  { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg> }
function IcoMembers(){ return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg> }
function IcoSettings(){ return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg> }
function IcoAI()     { return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/></svg> }

const s = {
  aside:        { width:'var(--sidebar-w)', background:'#0B0F14', borderRight:'1px solid var(--border)', display:'flex', flexDirection:'column', position:'fixed', top:0, left:0, bottom:0, zIndex:200, overflowX:'hidden', overflowY:'auto', transition:'transform 0.28s cubic-bezier(0.4,0,0.2,1)', willChange:'transform' },
  topLine:      { height:2, background:'linear-gradient(90deg,transparent,var(--accent),transparent)', opacity:0.6 },
  logo:         { display:'flex', alignItems:'center', gap:12, padding:'20px 20px 16px', borderBottom:'1px solid var(--border)' },
  logoOrb:      { width:38, height:38, borderRadius:12, background:'linear-gradient(135deg,rgba(0,212,170,.15),rgba(124,92,252,.15))', border:'1px solid var(--border-accent)', display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 },
  logoName:     { fontFamily:'var(--font-display)', fontSize:20, fontWeight:800, color:'var(--text-primary)', letterSpacing:'-0.02em', lineHeight:1 },
  logoSub:      { fontSize:9, color:'var(--text-muted)', letterSpacing:'0.1em', textTransform:'uppercase', fontWeight:600, marginTop:2 },
  companyChip:  { margin:'12px 16px 4px', display:'flex', alignItems:'center', gap:7, padding:'7px 12px', background:'rgba(0,212,170,.06)', border:'1px solid var(--border-accent)', borderRadius:8 },
  companyDot:   { width:6, height:6, borderRadius:'50%', background:'var(--accent)', boxShadow:'0 0 8px var(--accent)', flexShrink:0 },
  companyName:  { fontSize:12, fontWeight:600, color:'var(--accent)', flex:1, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' },
  nav:          { padding:'16px 12px 8px', display:'flex', flexDirection:'column', gap:2 },
  sectionLabel: { fontSize:9, fontWeight:700, color:'var(--text-muted)', letterSpacing:'0.12em', textTransform:'uppercase', padding:'4px 10px 8px' },
  link:         { display:'flex', alignItems:'center', gap:10, padding:'9px 12px', borderRadius:10, color:'var(--text-secondary)', fontSize:13, fontWeight:500, transition:'all var(--t)', position:'relative', textDecoration:'none' },
  linkActive:   { background:'linear-gradient(90deg, rgba(0,212,170,0.08), rgba(0,212,170,0.03))', boxShadow:'inset 0 0 0 1px rgba(0,212,170,0.1)' },
  linkIcon:     { display:'flex', alignItems:'center', flexShrink:0, transition:'color var(--t)' },
  activeBar:    { position:'absolute', right:0, top:'50%', transform:'translateY(-50%)', width:3, height:20, borderRadius:'3px 0 0 3px' },
  langSection:  { padding:'0 12px 12px' },
  langRow:      { display:'flex', gap:5, marginTop:6 },
  langBtn:      { flex:1, padding:'6px 0', borderRadius:7, fontSize:11, fontWeight:700, background:'transparent', color:'var(--text-muted)', borderWidth:'1px', borderStyle:'solid', borderColor:'var(--border)', cursor:'pointer', transition:'all 0.2s ease', fontFamily:'var(--font-display)', letterSpacing:'0.04em' },
  langBtnActive:{ background:'var(--accent-dim)', color:'var(--accent)', borderWidth:'1px', borderStyle:'solid', borderColor:'var(--border-accent)', boxShadow:'0 0 10px rgba(0,212,170,0.1)' },
  footer:       { padding:'14px 18px 20px', borderTop:'1px solid var(--border)', display:'flex', alignItems:'center', gap:10 },
  statusPulse:  { width:8, height:8, borderRadius:'50%', background:'var(--green)', boxShadow:'0 0 12px var(--green)', flexShrink:0, animation:'pulse-glow 2s ease-in-out infinite' },
}
