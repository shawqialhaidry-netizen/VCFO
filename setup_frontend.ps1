# VCFO Frontend Setup Script
# Run from C:\VCFO

Set-Location C:\VCFO

# Create directories
New-Item -ItemType Directory -Force -Path "frontend-react\src" | Out-Null
New-Item -ItemType Directory -Force -Path "frontend-react\src\components" | Out-Null
New-Item -ItemType Directory -Force -Path "frontend-react\src\pages" | Out-Null

# Write files
@'
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>VCFO — Virtual CFO Platform</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700;800&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;1,9..40,300&display=swap" rel="stylesheet" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>

'@ | Set-Content -Path "frontend-react\index.html" -Encoding UTF8

@'
{
  "name": "vcfo-frontend",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.2"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.1",
    "vite": "^5.4.8"
  }
}

'@ | Set-Content -Path "frontend-react\package.json" -Encoding UTF8

@'
import { Routes, Route } from ''react-router-dom''
import Sidebar from ''./components/Sidebar.jsx''
import Dashboard from ''./pages/Dashboard.jsx''
import Upload from ''./pages/Upload.jsx''
import CfoAI from ''./pages/CfoAI.jsx''

export default function App() {
  return (
    <div style={styles.shell}>
      <Sidebar />
      <main style={styles.main}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/cfo-ai" element={<CfoAI />} />
        </Routes>
      </main>
    </div>
  )
}

const styles = {
  shell: {
    display: ''flex'',
    minHeight: ''100vh'',
    background: ''var(--bg-base)'',
  },
  main: {
    marginLeft: ''var(--sidebar-w)'',
    flex: 1,
    minHeight: ''100vh'',
    overflowY: ''auto'',
  },
}

'@ | Set-Content -Path "frontend-react\src\App.jsx" -Encoding UTF8

@'
import { NavLink, useLocation } from ''react-router-dom''

const NAV = [
  {
    group: ''MAIN'',
    items: [
      { to: ''/'', label: ''Dashboard'', icon: <IconGrid /> },
      { to: ''/upload'', label: ''Upload'', icon: <IconUpload /> },
      { to: ''/cfo-ai'', label: ''CFO AI'', icon: <IconAI /> },
    ],
  },
]

export default function Sidebar() {
  return (
    <aside style={styles.aside}>
      {/* Logo */}
      <div style={styles.logo}>
        <div style={styles.logoMark}>
          <span style={styles.logoMarkInner} />
        </div>
        <div>
          <div style={styles.logoName}>VCFO</div>
          <div style={styles.logoSub}>Virtual CFO Platform</div>
        </div>
      </div>

      {/* Nav */}
      <nav style={styles.nav}>
        {NAV.map((section) => (
          <div key={section.group} style={styles.section}>
            <div style={styles.sectionLabel}>{section.group}</div>
            {section.items.map((item) => (
              <SidebarLink key={item.to} {...item} />
            ))}
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div style={styles.footer}>
        <div style={styles.statusDot} />
        <div>
          <div style={{ fontSize: 12, color: ''var(--text-secondary)'', fontWeight: 500 }}>System</div>
          <div style={{ fontSize: 11, color: ''var(--accent)'', fontFamily: ''monospace'' }}>● Online</div>
        </div>
      </div>
    </aside>
  )
}

function SidebarLink({ to, label, icon }) {
  return (
    <NavLink
      to={to}
      end={to === ''/''}
      style={({ isActive }) => ({
        ...styles.link,
        ...(isActive ? styles.linkActive : {}),
      })}
    >
      <span style={styles.linkIcon}>{icon}</span>
      <span>{label}</span>
      {/* active indicator bar */}
    </NavLink>
  )
}

// ── Icons (inline SVG) ────────────────────────────────────────────────────────

function IconGrid() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
      <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
    </svg>
  )
}

function IconUpload() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
      <polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
    </svg>
  )
}

function IconAI() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2a10 10 0 0 1 10 10c0 5.52-4.48 10-10 10S2 17.52 2 12"/>
      <path d="M12 8v4l3 3"/>
      <circle cx="12" cy="12" r="1" fill="currentColor"/>
    </svg>
  )
}

// ── Styles ───────────────────────────────────────────────────────────────────

const styles = {
  aside: {
    width: ''var(--sidebar-w)'',
    minHeight: ''100vh'',
    background: ''var(--bg-surface)'',
    borderRight: ''1px solid var(--border)'',
    display: ''flex'',
    flexDirection: ''column'',
    position: ''fixed'',
    top: 0,
    left: 0,
    bottom: 0,
    zIndex: 100,
  },
  logo: {
    display: ''flex'',
    alignItems: ''center'',
    gap: 12,
    padding: ''24px 20px 20px'',
    borderBottom: ''1px solid var(--border)'',
    marginBottom: 8,
  },
  logoMark: {
    width: 34,
    height: 34,
    borderRadius: 10,
    background: ''linear-gradient(135deg, var(--accent), #00a8ff)'',
    display: ''flex'',
    alignItems: ''center'',
    justifyContent: ''center'',
    boxShadow: ''0 0 20px var(--accent-glow)'',
    flexShrink: 0,
  },
  logoMarkInner: {
    display: ''block'',
    width: 14,
    height: 14,
    borderRadius: 3,
    background: ''rgba(0,0,0,0.4)'',
    transform: ''rotate(45deg)'',
  },
  logoName: {
    fontFamily: ''var(--font-display)'',
    fontSize: 18,
    fontWeight: 800,
    color: ''var(--text-primary)'',
    letterSpacing: ''0.04em'',
  },
  logoSub: {
    fontSize: 10,
    color: ''var(--text-muted)'',
    letterSpacing: ''0.06em'',
    textTransform: ''uppercase'',
    fontWeight: 500,
  },
  nav: {
    flex: 1,
    overflowY: ''auto'',
    padding: ''8px 12px'',
  },
  section: {
    marginBottom: 24,
  },
  sectionLabel: {
    fontSize: 10,
    fontWeight: 600,
    color: ''var(--text-muted)'',
    letterSpacing: ''0.1em'',
    textTransform: ''uppercase'',
    padding: ''4px 8px 8px'',
  },
  link: {
    display: ''flex'',
    alignItems: ''center'',
    gap: 10,
    padding: ''9px 12px'',
    borderRadius: 8,
    color: ''var(--text-secondary)'',
    textDecoration: ''none'',
    fontSize: 14,
    fontWeight: 500,
    transition: ''all var(--t)'',
    marginBottom: 2,
  },
  linkActive: {
    color: ''var(--text-primary)'',
    background: ''var(--bg-elevated)'',
    borderLeft: ''2px solid var(--accent)'',
    paddingLeft: 10,
  },
  linkIcon: {
    display: ''flex'',
    alignItems: ''center'',
    opacity: 0.8,
  },
  footer: {
    padding: ''16px 20px'',
    borderTop: ''1px solid var(--border)'',
    display: ''flex'',
    alignItems: ''center'',
    gap: 10,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: ''50%'',
    background: ''var(--green)'',
    boxShadow: ''0 0 8px var(--green)'',
    flexShrink: 0,
  },
}

'@ | Set-Content -Path "frontend-react\src\components\Sidebar.jsx" -Encoding UTF8

@'
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

:root {
  /* Core palette */
  --bg-base:       #080c12;
  --bg-surface:    #0e1420;
  --bg-elevated:   #141c2e;
  --bg-hover:      #1a2440;
  --border:        #1e2c44;
  --border-bright: #2a3d5e;

  /* Brand accent — electric teal */
  --accent:        #00d4aa;
  --accent-dim:    #00d4aa22;
  --accent-glow:   #00d4aa44;

  /* Secondary accent — amber */
  --amber:         #f5a623;
  --amber-dim:     #f5a62320;

  /* Status */
  --green:         #22c55e;
  --red:           #ef4444;
  --blue:          #3b82f6;
  --purple:        #a855f7;

  /* Text */
  --text-primary:  #e8edf5;
  --text-secondary:#8a9ab8;
  --text-muted:    #4a5a7a;

  /* Sidebar */
  --sidebar-w: 240px;

  /* Typography */
  --font-display: ''Syne'', sans-serif;
  --font-body:    ''DM Sans'', sans-serif;

  /* Transitions */
  --t: 180ms cubic-bezier(0.4, 0, 0.2, 1);
}

html, body, #root {
  height: 100%;
  background: var(--bg-base);
  color: var(--text-primary);
  font-family: var(--font-body);
  font-size: 14px;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}

/* Scrollbar */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-bright); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

/* Utility */
.truncate { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

button {
  font-family: var(--font-body);
  cursor: pointer;
  border: none;
  outline: none;
}

input, textarea, select {
  font-family: var(--font-body);
  outline: none;
}

'@ | Set-Content -Path "frontend-react\src\index.css" -Encoding UTF8

@'
import React from ''react''
import ReactDOM from ''react-dom/client''
import { BrowserRouter } from ''react-router-dom''
import App from ''./App.jsx''
import ''./index.css''

ReactDOM.createRoot(document.getElementById(''root'')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
)

'@ | Set-Content -Path "frontend-react\src\main.jsx" -Encoding UTF8

@'
import { useState, useRef, useEffect } from ''react''

const WELCOME = {
  role: ''assistant'',
  content: `Welcome to **CFO AI** — your intelligent financial advisor.\n\nIn upcoming phases I will be able to:\n- Analyze your trial balance and financial statements\n- Detect anomalies and flag risks\n- Generate MoM / YoY commentary\n- Forecast cash flow and profitability\n- Answer questions about your company''s financial health\n\n*Phase 1 is foundation only — upload & analysis engine coming next.*`,
}

export default function CfoAI() {
  const [messages, setMessages] = useState([WELCOME])
  const [input, setInput] = useState('''')
  const bottomRef = useRef()

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: ''smooth'' })
  }, [messages])

  function send() {
    const text = input.trim()
    if (!text) return
    setMessages(prev => [
      ...prev,
      { role: ''user'', content: text },
      {
        role: ''assistant'',
        content: `*[Phase 1 — AI engine not yet connected.]*\n\nYour message has been received: "${text}"\n\nFull AI analysis will be available in Phase 3 once the financial data pipeline is wired up.`,
      },
    ])
    setInput('''')
  }

  function onKey(e) {
    if (e.key === ''Enter'' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div style={s.page}>
      {/* Header */}
      <div style={s.header}>
        <div style={s.headerLeft}>
          <div style={s.aiOrb} />
          <div>
            <h1 style={s.title}>CFO AI</h1>
            <p style={s.subtitle}>Intelligent financial insights — Phase 3 activation</p>
          </div>
        </div>
        <div style={s.badge}>Phase 1 Preview</div>
      </div>

      {/* Chat area */}
      <div style={s.chatWrap}>
        <div style={s.messages}>
          {messages.map((m, i) => (
            <Message key={i} role={m.role} content={m.content} />
          ))}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div style={s.inputRow}>
          <textarea
            style={s.textarea}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={onKey}
            placeholder="Ask about your financials… (Enter to send)"
            rows={1}
          />
          <button style={s.sendBtn} onClick={send} disabled={!input.trim()}>
            <SendIcon />
          </button>
        </div>
      </div>
    </div>
  )
}

function Message({ role, content }) {
  const isUser = role === ''user''

  // minimal markdown: bold and italic
  function renderContent(text) {
    const lines = text.split(''\n'')
    return lines.map((line, i) => {
      const parts = line
        .replace(/\*\*(.+?)\*\*/g, ''<strong>$1</strong>'')
        .replace(/\*(.+?)\*/g, ''<em>$1</em>'')
        .replace(/^- /, ''• '')
      return (
        <span key={i}>
          <span dangerouslySetInnerHTML={{ __html: parts }} />
          {i < lines.length - 1 && <br />}
        </span>
      )
    })
  }

  return (
    <div style={{ ...s.msgWrap, justifyContent: isUser ? ''flex-end'' : ''flex-start'' }}>
      {!isUser && <div style={s.avatar}>AI</div>}
      <div style={{ ...s.bubble, ...(isUser ? s.bubbleUser : s.bubbleAI) }}>
        {renderContent(content)}
      </div>
    </div>
  )
}

function SendIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13"/>
      <polygon points="22 2 15 22 11 13 2 9 22 2"/>
    </svg>
  )
}

const s = {
  page: { padding: ''36px 40px'', maxWidth: 860, display: ''flex'', flexDirection: ''column'', height: ''100vh'' },
  header: { display: ''flex'', justifyContent: ''space-between'', alignItems: ''center'', marginBottom: 24, flexShrink: 0 },
  headerLeft: { display: ''flex'', alignItems: ''center'', gap: 14 },
  aiOrb: {
    width: 40, height: 40, borderRadius: ''50%'',
    background: ''radial-gradient(circle at 35% 35%, var(--accent), #0066ff)'',
    boxShadow: ''0 0 24px var(--accent-glow)'',
    flexShrink: 0,
    animation: ''pulse 3s ease-in-out infinite'',
  },
  title: { fontFamily: ''var(--font-display)'', fontSize: 26, fontWeight: 700, letterSpacing: ''-0.01em'' },
  subtitle: { color: ''var(--text-secondary)'', fontSize: 13, marginTop: 2 },
  badge: {
    background: ''var(--amber-dim)'', color: ''var(--amber)'',
    border: ''1px solid var(--amber)'', borderRadius: 20,
    padding: ''4px 14px'', fontSize: 11, fontWeight: 700,
    letterSpacing: ''0.06em'', textTransform: ''uppercase'',
  },
  chatWrap: {
    flex: 1, display: ''flex'', flexDirection: ''column'',
    background: ''var(--bg-surface)'', border: ''1px solid var(--border)'',
    borderRadius: 16, overflow: ''hidden'',
    minHeight: 0,
  },
  messages: {
    flex: 1, overflowY: ''auto'', padding: ''24px 24px 16px'',
    display: ''flex'', flexDirection: ''column'', gap: 16,
  },
  msgWrap: { display: ''flex'', alignItems: ''flex-end'', gap: 10 },
  avatar: {
    width: 28, height: 28, borderRadius: ''50%'',
    background: ''linear-gradient(135deg, var(--accent), #0066ff)'',
    display: ''flex'', alignItems: ''center'', justifyContent: ''center'',
    fontSize: 10, fontWeight: 700, color: ''#000'', flexShrink: 0,
  },
  bubble: {
    maxWidth: ''78%'', padding: ''12px 16px'', borderRadius: 14,
    fontSize: 13, lineHeight: 1.7,
  },
  bubbleAI: {
    background: ''var(--bg-elevated)'',
    color: ''var(--text-primary)'',
    borderBottomLeftRadius: 4,
    border: ''1px solid var(--border)'',
  },
  bubbleUser: {
    background: ''var(--accent)'',
    color: ''#000'',
    borderBottomRightRadius: 4,
    fontWeight: 500,
  },
  inputRow: {
    display: ''flex'', gap: 10, padding: ''16px 20px'',
    borderTop: ''1px solid var(--border)'',
    background: ''var(--bg-elevated)'',
    flexShrink: 0,
  },
  textarea: {
    flex: 1, background: ''var(--bg-surface)'',
    border: ''1px solid var(--border-bright)'',
    borderRadius: 10, padding: ''10px 14px'',
    color: ''var(--text-primary)'', fontSize: 13,
    resize: ''none'', lineHeight: 1.5,
    transition: ''border var(--t)'',
  },
  sendBtn: {
    width: 40, height: 40, borderRadius: 10, flexShrink: 0,
    background: ''var(--accent)'', color: ''#000'',
    display: ''flex'', alignItems: ''center'', justifyContent: ''center'',
    border: ''none'', cursor: ''pointer'', transition: ''opacity var(--t)'',
    alignSelf: ''flex-end'',
  },
}

'@ | Set-Content -Path "frontend-react\src\pages\CfoAI.jsx" -Encoding UTF8

@'
import { useEffect, useState } from ''react''

const API = ''/api/v1''

export default function Dashboard() {
  const [companies, setCompanies] = useState([])
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '''', name_ar: '''', industry: '''', currency: ''USD'' })
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    Promise.all([
      fetch(`${API}/health`).then(r => r.json()),
      fetch(`${API}/companies`).then(r => r.json()),
    ]).then(([h, c]) => {
      setHealth(h)
      setCompanies(c)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  async function handleCreate(e) {
    e.preventDefault()
    if (!form.name.trim()) return
    setCreating(true)
    try {
      const res = await fetch(`${API}/companies`, {
        method: ''POST'',
        headers: { ''Content-Type'': ''application/json'' },
        body: JSON.stringify(form),
      })
      const company = await res.json()
      setCompanies(prev => [company, ...prev])
      setForm({ name: '''', name_ar: '''', industry: '''', currency: ''USD'' })
      setShowForm(false)
    } finally {
      setCreating(false)
    }
  }

  return (
    <div style={s.page}>
      {/* Header */}
      <div style={s.header}>
        <div>
          <h1 style={s.title}>Dashboard</h1>
          <p style={s.subtitle}>Overview of your Virtual CFO platform</p>
        </div>
        <button style={s.btnPrimary} onClick={() => setShowForm(v => !v)}>
          {showForm ? ''✕ Cancel'' : ''+ New Company''}
        </button>
      </div>

      {/* System Status */}
      <div style={s.statsRow}>
        <StatCard
          label="System Status"
          value={health ? ''Online'' : ''—''}
          sub={health?.version ? `v${health.version}` : ''''}
          accent="var(--green)"
        />
        <StatCard
          label="Companies"
          value={loading ? ''…'' : companies.length}
          sub="active"
          accent="var(--accent)"
        />
        <StatCard
          label="Phase"
          value="1"
          sub="Foundation"
          accent="var(--amber)"
        />
        <StatCard
          label="Database"
          value="SQLite"
          sub="local"
          accent="var(--blue)"
        />
      </div>

      {/* Create Form */}
      {showForm && (
        <div style={s.card}>
          <div style={s.cardTitle}>Register Company</div>
          <form onSubmit={handleCreate} style={s.form}>
            <div style={s.formRow}>
              <Field
                label="Company Name (EN)"
                value={form.name}
                onChange={v => setForm(f => ({ ...f, name: v }))}
                required
              />
              <Field
                label="اسم الشركة (AR)"
                value={form.name_ar}
                onChange={v => setForm(f => ({ ...f, name_ar: v }))}
                dir="rtl"
              />
            </div>
            <div style={s.formRow}>
              <Field
                label="Industry"
                value={form.industry}
                onChange={v => setForm(f => ({ ...f, industry: v }))}
                placeholder="e.g. Waste Management"
              />
              <div style={s.fieldWrap}>
                <label style={s.label}>Currency</label>
                <select
                  style={s.select}
                  value={form.currency}
                  onChange={e => setForm(f => ({ ...f, currency: e.target.value }))}
                >
                  <option value="USD">USD</option>
                  <option value="AED">AED</option>
                  <option value="SAR">SAR</option>
                  <option value="EUR">EUR</option>
                  <option value="TRY">TRY</option>
                </select>
              </div>
            </div>
            <div style={{ display: ''flex'', gap: 10, marginTop: 4 }}>
              <button type="submit" style={s.btnPrimary} disabled={creating}>
                {creating ? ''Creating…'' : ''Create Company''}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Companies Table */}
      <div style={s.card}>
        <div style={s.cardTitle}>Companies</div>
        {loading ? (
          <div style={s.empty}>Loading…</div>
        ) : companies.length === 0 ? (
          <div style={s.empty}>No companies yet. Create one above.</div>
        ) : (
          <table style={s.table}>
            <thead>
              <tr>
                {[''Name'', ''Arabic Name'', ''Industry'', ''Currency'', ''Created''].map(h => (
                  <th key={h} style={s.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {companies.map(c => (
                <tr key={c.id} style={s.tr}>
                  <td style={s.td}><span style={s.companyName}>{c.name}</span></td>
                  <td style={{ ...s.td, direction: ''rtl'', textAlign: ''right'' }}>{c.name_ar || ''—''}</td>
                  <td style={s.td}>{c.industry || ''—''}</td>
                  <td style={s.td}><Tag>{c.currency}</Tag></td>
                  <td style={{ ...s.td, color: ''var(--text-muted)'', fontSize: 12 }}>
                    {new Date(c.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

function StatCard({ label, value, sub, accent }) {
  return (
    <div style={{ ...s.statCard, borderTop: `2px solid ${accent}` }}>
      <div style={{ fontSize: 11, color: ''var(--text-muted)'', textTransform: ''uppercase'', letterSpacing: ''0.08em'', fontWeight: 600 }}>{label}</div>
      <div style={{ fontSize: 28, fontFamily: ''var(--font-display)'', fontWeight: 700, color: accent, lineHeight: 1.2, marginTop: 6 }}>{value}</div>
      <div style={{ fontSize: 12, color: ''var(--text-secondary)'', marginTop: 2 }}>{sub}</div>
    </div>
  )
}

function Field({ label, value, onChange, required, placeholder, dir }) {
  return (
    <div style={s.fieldWrap}>
      <label style={s.label}>{label}{required && <span style={{ color: ''var(--accent)'' }}> *</span>}</label>
      <input
        style={{ ...s.input, direction: dir }}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder || ''''}
        required={required}
      />
    </div>
  )
}

function Tag({ children }) {
  return (
    <span style={{ background: ''var(--accent-dim)'', color: ''var(--accent)'', border: ''1px solid var(--accent-glow)'', borderRadius: 4, padding: ''2px 8px'', fontSize: 11, fontWeight: 600, fontFamily: ''monospace'' }}>
      {children}
    </span>
  )
}

const s = {
  page: { padding: ''36px 40px'', maxWidth: 1100 },
  header: { display: ''flex'', justifyContent: ''space-between'', alignItems: ''flex-start'', marginBottom: 32 },
  title: { fontFamily: ''var(--font-display)'', fontSize: 26, fontWeight: 700, color: ''var(--text-primary)'', letterSpacing: ''-0.01em'' },
  subtitle: { color: ''var(--text-secondary)'', fontSize: 13, marginTop: 4 },
  statsRow: { display: ''grid'', gridTemplateColumns: ''repeat(4, 1fr)'', gap: 16, marginBottom: 24 },
  statCard: { background: ''var(--bg-surface)'', border: ''1px solid var(--border)'', borderRadius: 12, padding: ''20px 22px'' },
  card: { background: ''var(--bg-surface)'', border: ''1px solid var(--border)'', borderRadius: 12, padding: ''24px'', marginBottom: 20 },
  cardTitle: { fontFamily: ''var(--font-display)'', fontSize: 14, fontWeight: 600, color: ''var(--text-secondary)'', textTransform: ''uppercase'', letterSpacing: ''0.06em'', marginBottom: 20 },
  form: { display: ''flex'', flexDirection: ''column'', gap: 16 },
  formRow: { display: ''grid'', gridTemplateColumns: ''1fr 1fr'', gap: 16 },
  fieldWrap: { display: ''flex'', flexDirection: ''column'', gap: 6 },
  label: { fontSize: 12, fontWeight: 500, color: ''var(--text-secondary)'', letterSpacing: ''0.03em'' },
  input: { background: ''var(--bg-elevated)'', border: ''1px solid var(--border)'', borderRadius: 8, padding: ''9px 12px'', color: ''var(--text-primary)'', fontSize: 14, transition: ''border var(--t)'' },
  select: { background: ''var(--bg-elevated)'', border: ''1px solid var(--border)'', borderRadius: 8, padding: ''9px 12px'', color: ''var(--text-primary)'', fontSize: 14 },
  btnPrimary: { background: ''var(--accent)'', color: ''#000'', border: ''none'', borderRadius: 8, padding: ''9px 20px'', fontSize: 13, fontWeight: 700, cursor: ''pointer'', fontFamily: ''var(--font-display)'', letterSpacing: ''0.02em'', transition: ''opacity var(--t)'' },
  table: { width: ''100%'', borderCollapse: ''collapse'' },
  th: { textAlign: ''left'', padding: ''8px 12px'', fontSize: 11, color: ''var(--text-muted)'', textTransform: ''uppercase'', letterSpacing: ''0.08em'', fontWeight: 600, borderBottom: ''1px solid var(--border)'' },
  tr: { borderBottom: ''1px solid var(--border)'', transition: ''background var(--t)'' },
  td: { padding: ''12px 12px'', fontSize: 13, color: ''var(--text-primary)'' },
  companyName: { fontWeight: 600 },
  empty: { color: ''var(--text-muted)'', fontSize: 13, padding: ''20px 0'', textAlign: ''center'' },
}

'@ | Set-Content -Path "frontend-react\src\pages\Dashboard.jsx" -Encoding UTF8

@'
import { useState, useRef } from ''react''

export default function Upload() {
  const [dragging, setDragging] = useState(false)
  const [file, setFile] = useState(null)
  const inputRef = useRef()

  function onDrop(e) {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) setFile(f)
  }

  function onSelect(e) {
    const f = e.target.files[0]
    if (f) setFile(f)
  }

  function clearFile() {
    setFile(null)
    if (inputRef.current) inputRef.current.value = ''''
  }

  return (
    <div style={s.page}>
      {/* Header */}
      <div style={s.header}>
        <div>
          <h1 style={s.title}>Upload Trial Balance</h1>
          <p style={s.subtitle}>Upload Excel or CSV files — processing engine coming in Phase 2</p>
        </div>
      </div>

      {/* Phase notice */}
      <div style={s.notice}>
        <span style={s.noticeIcon}>⚡</span>
        <span>
          <strong style={{ color: ''var(--amber)'' }}>Phase 1 — UI Ready.</strong>
          {'' ''}The file processing engine (account classification, financial statements) will be wired in Phase 2.
        </span>
      </div>

      {/* Upload Zone */}
      <div
        style={{
          ...s.dropzone,
          ...(dragging ? s.dropzoneDragging : {}),
          ...(file ? s.dropzoneHasFile : {}),
        }}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => !file && inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,.xls,.csv"
          style={{ display: ''none'' }}
          onChange={onSelect}
        />

        {file ? (
          <div style={s.fileInfo}>
            <div style={s.fileIcon}>📄</div>
            <div style={s.fileName}>{file.name}</div>
            <div style={s.fileSize}>{(file.size / 1024).toFixed(1)} KB</div>
            <button style={s.clearBtn} onClick={(e) => { e.stopPropagation(); clearFile() }}>
              Remove
            </button>
          </div>
        ) : (
          <div style={s.dropPlaceholder}>
            <div style={s.dropIcon}>
              <UploadIcon />
            </div>
            <div style={s.dropTitle}>Drop your Trial Balance here</div>
            <div style={s.dropSub}>Supports .xlsx, .xls, .csv — or click to browse</div>
          </div>
        )}
      </div>

      {/* Format Guide */}
      <div style={s.card}>
        <div style={s.cardTitle}>Expected File Format</div>
        <div style={s.formatGrid}>
          {[
            { col: ''account_code'', type: ''text'', example: ''1010'', desc: ''Account code / رقم الحساب'' },
            { col: ''account_name'', type: ''text'', example: ''Cash'', desc: ''Account name / اسم الحساب'' },
            { col: ''debit'', type: ''number'', example: ''50000'', desc: ''Debit total / مدين'' },
            { col: ''credit'', type: ''number'', example: ''30000'', desc: ''Credit total / دائن'' },
            { col: ''period'', type: ''text'', example: ''2026-01'', desc: ''Period (YYYY-MM) — optional'' },
          ].map(row => (
            <div key={row.col} style={s.formatRow}>
              <code style={s.colName}>{row.col}</code>
              <span style={s.colType}>{row.type}</span>
              <span style={s.colExample}>{row.example}</span>
              <span style={s.colDesc}>{row.desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function UploadIcon() {
  return (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
      <polyline points="17 8 12 3 7 8"/>
      <line x1="12" y1="3" x2="12" y2="15"/>
    </svg>
  )
}

const s = {
  page: { padding: ''36px 40px'', maxWidth: 900 },
  header: { marginBottom: 24 },
  title: { fontFamily: ''var(--font-display)'', fontSize: 26, fontWeight: 700, letterSpacing: ''-0.01em'' },
  subtitle: { color: ''var(--text-secondary)'', fontSize: 13, marginTop: 4 },
  notice: {
    display: ''flex'', alignItems: ''center'', gap: 10,
    background: ''var(--amber-dim)'', border: ''1px solid var(--amber)'',
    borderRadius: 10, padding: ''12px 16px'', marginBottom: 24,
    fontSize: 13, color: ''var(--text-secondary)'', lineHeight: 1.5,
  },
  noticeIcon: { fontSize: 16, flexShrink: 0 },
  dropzone: {
    border: ''2px dashed var(--border-bright)'',
    borderRadius: 16,
    padding: ''56px 40px'',
    textAlign: ''center'',
    cursor: ''pointer'',
    transition: ''all var(--t)'',
    background: ''var(--bg-surface)'',
    marginBottom: 24,
  },
  dropzoneDragging: {
    borderColor: ''var(--accent)'',
    background: ''var(--accent-dim)'',
    boxShadow: ''0 0 30px var(--accent-glow)'',
  },
  dropzoneHasFile: {
    cursor: ''default'',
    borderColor: ''var(--green)'',
    background: ''rgba(34,197,94,0.04)'',
  },
  dropPlaceholder: {},
  dropIcon: { color: ''var(--text-muted)'', marginBottom: 16, display: ''flex'', justifyContent: ''center'' },
  dropTitle: { fontSize: 16, fontWeight: 600, color: ''var(--text-primary)'', marginBottom: 8 },
  dropSub: { fontSize: 13, color: ''var(--text-muted)'' },
  fileInfo: { display: ''flex'', flexDirection: ''column'', alignItems: ''center'', gap: 8 },
  fileIcon: { fontSize: 40 },
  fileName: { fontSize: 16, fontWeight: 600, color: ''var(--text-primary)'' },
  fileSize: { fontSize: 12, color: ''var(--text-muted)'' },
  clearBtn: {
    marginTop: 8, background: ''transparent'', border: ''1px solid var(--border-bright)'',
    color: ''var(--text-secondary)'', borderRadius: 6, padding: ''5px 14px'',
    fontSize: 12, cursor: ''pointer'', transition: ''all var(--t)'',
  },
  card: { background: ''var(--bg-surface)'', border: ''1px solid var(--border)'', borderRadius: 12, padding: ''24px'' },
  cardTitle: { fontFamily: ''var(--font-display)'', fontSize: 13, fontWeight: 600, color: ''var(--text-muted)'', textTransform: ''uppercase'', letterSpacing: ''0.06em'', marginBottom: 16 },
  formatGrid: { display: ''flex'', flexDirection: ''column'', gap: 10 },
  formatRow: { display: ''grid'', gridTemplateColumns: ''140px 60px 80px 1fr'', alignItems: ''center'', gap: 16, padding: ''10px 14px'', background: ''var(--bg-elevated)'', borderRadius: 8 },
  colName: { fontFamily: ''monospace'', fontSize: 12, color: ''var(--accent)'', fontWeight: 600 },
  colType: { fontSize: 11, color: ''var(--purple)'', background: ''rgba(168,85,247,0.1)'', padding: ''2px 7px'', borderRadius: 4, textAlign: ''center'' },
  colExample: { fontSize: 12, color: ''var(--text-muted)'', fontFamily: ''monospace'' },
  colDesc: { fontSize: 12, color: ''var(--text-secondary)'' },
}

'@ | Set-Content -Path "frontend-react\src\pages\Upload.jsx" -Encoding UTF8

@'
import { defineConfig } from ''vite''
import react from ''@vitejs/plugin-react''

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      ''/api'': {
        target: ''http://localhost:8000'',
        changeOrigin: true,
      },
    },
  },
})

'@ | Set-Content -Path "frontend-react\vite.config.js" -Encoding UTF8

Write-Host '✓ All frontend files created' -ForegroundColor Green
Write-Host 'Now run: cd frontend-react && npm install && npm run dev' -ForegroundColor Cyan