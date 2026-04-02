import { Routes, Route, Navigate } from 'react-router-dom'
import { useState } from 'react'
import { useAuth } from './context/AuthContext.jsx'
import { useCompany } from './context/CompanyContext.jsx'
import SessionExpiredBanner from './components/SessionExpiredBanner.jsx'
import Sidebar from './components/Sidebar.jsx'
import HeaderBar from './components/HeaderBar.jsx'
import CommandCenter from './pages/CommandCenter.jsx'
import Upload from './pages/Upload.jsx'
import CfoAI from './pages/CfoAI.jsx'
import Statements from './pages/Statements.jsx'
import Analysis from './pages/Analysis.jsx'
import Branches from './pages/Branches.jsx'
import BoardReport from './pages/BoardReport.jsx'
import Members  from './pages/Members.jsx'
import Settings from './pages/Settings.jsx'
import Login from './pages/Login.jsx'
import CfoPanel from './components/CfoPanel.jsx'

// ── Trial Expired Wall ────────────────────────────────────────────────────────
// Shown to analysts and viewers when the company trial has expired.
// Owners bypass this and can still access /members and /settings.
function TrialExpiredWall({ logout }) {
  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', background: '#0B0F14',
      padding: 24, gap: 20, textAlign: 'center' }}>
      <div style={{ fontSize: 48, opacity: .25 }}>⛔</div>
      <div style={{ fontSize: 22, fontWeight: 800, color: '#ffffff' }}>
        Your trial has ended
      </div>
      <div style={{ fontSize: 14, color: '#aab4c3', maxWidth: 380, lineHeight: 1.6 }}>
        Your company's trial period has expired. Please contact your account owner or
        reach out to us to continue using VCFO.
      </div>
      <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>
        Your data is safe and preserved.
      </div>
      <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
        <a href="mailto:support@vcfo.io" style={{
          padding: '10px 24px', borderRadius: 9, background: '#00d4aa',
          color: '#000', fontWeight: 700, fontSize: 13, textDecoration: 'none',
        }}>Contact Support</a>
        <button onClick={logout} style={{
          padding: '10px 24px', borderRadius: 9, border: '1px solid rgba(255,255,255,.15)',
          background: 'transparent', color: '#aab4c3', fontWeight: 600, fontSize: 13,
          cursor: 'pointer',
        }}>Log out</button>
      </div>
    </div>
  )
}

export default function App() {
  const { auth, sessionExpired, logout } = useAuth()
  const { isTrialExpired, isOwner }      = useCompany()
  const [sidebarOpen,  setSidebarOpen]  = useState(false)
  const [cfoPanelOpen, setCfoPanelOpen] = useState(false)

  // Not logged in → go directly to Login (no landing/onboarding)
  if (!auth) return <Login />

  // Expired trial:
  // - analyst / viewer → blocked by TrialExpiredWall
  // - owner → restricted shell: only /members and /settings accessible
  if (isTrialExpired && !isOwner) return <TrialExpiredWall logout={logout} />

  if (isTrialExpired && isOwner) return (
    <div style={s.shell}>
      <div style={s.body}>
        <HeaderBar onOpenSidebar={() => {}} onOpenCfo={() => {}} />
        <main style={s.main}>
          <Routes>
            <Route path="/members"  element={<Members />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*"         element={<Settings />} />
          </Routes>
        </main>
      </div>
      {sessionExpired && <SessionExpiredBanner onLogin={logout} />}
    </div>
  )

  return (
    <div style={s.shell}>
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {sidebarOpen && (
        <div onClick={() => setSidebarOpen(false)} style={s.backdrop} />
      )}

      <CfoPanel open={cfoPanelOpen} onClose={() => setCfoPanelOpen(false)} />

      <div style={s.body}>
        <HeaderBar
          onOpenSidebar={() => setSidebarOpen(true)}
          onOpenCfo={() => setCfoPanelOpen(true)}
        />
        <main style={s.main} className="grid-bg">
          <Routes>
            <Route path="/"           element={<CommandCenter />} />
            <Route path="/executive"  element={<Navigate to="/" replace />} />
            <Route path="/upload"     element={<Upload />} />
            <Route path="/cfo-ai"     element={<CfoAI />} />
            <Route path="/ai-advisor" element={<CfoAI />} />
            <Route path="/statements" element={<Statements />} />
            <Route path="/analysis"   element={<Analysis />} />
            <Route path="/branches"    element={<Branches />} />
            <Route path="/board-report" element={<BoardReport />} />
            <Route path="/members"    element={<Members />} />
            <Route path="/settings"   element={<Settings />} />
          </Routes>
        </main>
      </div>

      {sessionExpired && <SessionExpiredBanner onLogin={logout} />}
    </div>
  )
}

const s = {
  shell:    { position:'relative', height:'100vh', background:'var(--bg-void)', overflow:'hidden' },
  backdrop: { position:'fixed', inset:0, zIndex:199, background:'rgba(0,0,0,0.55)',
               backdropFilter:'blur(2px)', WebkitBackdropFilter:'blur(2px)' },
  body:     { display:'flex', flexDirection:'column', height:'100vh', overflow:'hidden' },
  main:     { flex:1, overflowY:'auto', minHeight:0 },
}
