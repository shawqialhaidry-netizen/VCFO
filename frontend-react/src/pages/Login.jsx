import { useMemo, useState } from 'react'
import { useAuth } from '../context/AuthContext.jsx'
import { useCompany } from '../context/CompanyContext.jsx'
import { useLang } from '../context/LangContext.jsx'
import './Login.css'

const API = '/api/v1'

const PARTICLE_COUNT = 28

function particleProps(i) {
  const left = ((i * 17 + 11) % 90) + 5
  const top = ((i * 23 + 7) % 85) + 7
  const delay = -(i * 0.65) % 10
  const duration = 11 + (i % 9)
  const size = 1.5 + (i % 5) * 0.65
  return {
    style: {
      left: `${left}%`,
      top: `${top}%`,
      width: `${size}px`,
      height: `${size}px`,
      animationDelay: `${delay}s`,
      animationDuration: `${duration}s`,
    },
  }
}

export default function Login() {
  const { tr } = useLang()
  const { setAuth } = useAuth()
  const { reloadCompanies } = useCompany()
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  const particles = useMemo(
    () => Array.from({ length: PARTICLE_COUNT }, (_, i) => ({ key: i, ...particleProps(i) })),
    [],
  )

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      if (mode === 'register') {
        const rReg = await fetch(`${API}/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password, full_name: name }),
        })
        const dReg = await rReg.json()
        if (!rReg.ok) {
          setError(dReg.detail || tr('login_err_register_failed'))
          setLoading(false)
          return
        }
      }

      const rLogin = await fetch(`${API}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      const dLogin = await rLogin.json()
      if (!rLogin.ok) {
        setError(dLogin.detail || tr('login_err_invalid_credentials'))
        setLoading(false)
        return
      }

      setAuth({ token: dLogin.access_token, user: dLogin.user })
      reloadCompanies()
    } catch {
      setError(tr('login_err_connection'))
    }
    setLoading(false)
  }

  return (
    <div className="login-page">
      <div className="login-page__gradient-mesh" aria-hidden />
      <div className="login-page__glow login-page__glow--a" aria-hidden />
      <div className="login-page__glow login-page__glow--b" aria-hidden />
      <div className="login-page__glow login-page__glow--c" aria-hidden />
      <div className="login-page__particles" aria-hidden>
        {particles.map(({ key, style }) => (
          <span key={key} className="login-page__particle" style={style} />
        ))}
      </div>

      <div className="login-card">
        <header className="login-brand">
          <span className="login-brand__kicker">AI Financial Intelligence</span>
          <h1 className="login-brand__name">VCFO</h1>
          <p className="login-brand__tagline">Virtual CFO Platform</p>
          <span className="login-brand__divider" aria-hidden />
        </header>

        <div className="login-toggle" role="tablist" aria-label="Account">
          {['login', 'register'].map((m) => (
            <button
              key={m}
              type="button"
              role="tab"
              aria-selected={mode === m}
              className={`login-toggle__btn${mode === m ? ' login-toggle__btn--active' : ''}`}
              onClick={() => {
                setMode(m)
                setError(null)
              }}
            >
              {m === 'login' ? 'تسجيل الدخول' : 'حساب جديد'}
            </button>
          ))}
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          {mode === 'register' && (
            <div className="login-field">
              <label className="login-label" htmlFor="login-name">
                الاسم الكامل
              </label>
              <input
                id="login-name"
                className="login-input"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Admin VCFO"
                autoComplete="name"
              />
            </div>
          )}
          <div className="login-field">
            <label className="login-label" htmlFor="login-email">
              البريد الإلكتروني
            </label>
            <input
              id="login-email"
              className="login-input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@vcfo.com"
              required
              autoComplete="email"
            />
          </div>
          <div className="login-field">
            <label className="login-label" htmlFor="login-password">
              كلمة المرور
            </label>
            <input
              id="login-password"
              className="login-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              autoComplete="current-password"
            />
          </div>
          {error && (
            <div className="login-error" role="alert">
              ⚠ {error}
            </div>
          )}
          <button type="submit" className="login-submit" disabled={loading}>
            {loading ? '...' : mode === 'login' ? 'دخول' : 'إنشاء حساب والدخول'}
          </button>
        </form>
      </div>
    </div>
  )
}
