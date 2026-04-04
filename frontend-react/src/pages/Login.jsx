import { useState } from 'react'
import { useAuth } from '../context/AuthContext.jsx'
import { useCompany } from '../context/CompanyContext.jsx'
import { useLang } from '../context/LangContext.jsx'

const API = '/api/v1'

export default function Login() {
  const { tr }               = useLang()
  const { setAuth }          = useAuth()
  const { reloadCompanies }  = useCompany()
  const [mode, setMode]      = useState('login')
  const [email, setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [name, setName]      = useState('')
  const [error, setError]    = useState(null)
  const [loading, setLoading]= useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null); setLoading(true)
    try {
      if (mode === 'register') {
        const rReg = await fetch(`${API}/auth/register`, {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ email, password, full_name: name }),
        })
        const dReg = await rReg.json()
        if (!rReg.ok) { setError(dReg.detail || tr('login_err_register_failed')); setLoading(false); return }
      }

      const rLogin = await fetch(`${API}/auth/login`, {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ email, password }),
      })
      const dLogin = await rLogin.json()
      if (!rLogin.ok) { setError(dLogin.detail || tr('login_err_invalid_credentials')); setLoading(false); return }

      // Store auth first, then reload companies with the new token
      setAuth({ token: dLogin.access_token, user: dLogin.user })
      reloadCompanies()
    } catch {
      setError(tr('login_err_connection'))
    }
    setLoading(false)
  }

  return (
    <div style={s.page}>
      <div style={s.card}>
        <div style={s.logo}>
          <span style={s.logoText}>VCFO</span>
          <span style={s.logoSub}>Virtual CFO Platform</span>
        </div>
        <div style={s.toggle}>
          {['login','register'].map(m=>(
            <button key={m} onClick={()=>{setMode(m);setError(null)}}
              style={{...s.toggleBtn,...(mode===m?s.toggleActive:{})}}>
              {m==='login'?'تسجيل الدخول':'حساب جديد'}
            </button>
          ))}
        </div>
        <form onSubmit={handleSubmit} style={s.form}>
          {mode==='register'&&(
            <div style={s.field}>
              <label style={s.label}>الاسم الكامل</label>
              <input style={s.input} type="text" value={name}
                onChange={e=>setName(e.target.value)} placeholder="Admin VCFO" autoComplete="name"/>
            </div>
          )}
          <div style={s.field}>
            <label style={s.label}>البريد الإلكتروني</label>
            <input style={s.input} type="email" value={email}
              onChange={e=>setEmail(e.target.value)} placeholder="admin@vcfo.com" required autoComplete="email"/>
          </div>
          <div style={s.field}>
            <label style={s.label}>كلمة المرور</label>
            <input style={s.input} type="password" value={password}
              onChange={e=>setPassword(e.target.value)} placeholder="••••••••" required autoComplete="current-password"/>
          </div>
          {error&&<div style={s.error}>⚠ {error}</div>}
          <button type="submit" disabled={loading} style={{...s.btn,...(loading?s.btnDisabled:{})}}>
            {loading?'...':mode==='login'?'دخول':'إنشاء حساب والدخول'}
          </button>
        </form>
      </div>
    </div>
  )
}

const s = {
  page:        {minHeight:'100vh',background:'var(--bg-void)',display:'flex',alignItems:'center',justifyContent:'center',padding:20},
  card:        {background:'var(--bg-surface)',border:'1px solid var(--border)',borderRadius:18,padding:'40px 36px',width:'100%',maxWidth:400,boxShadow:'0 24px 64px rgba(0,0,0,0.6)'},
  logo:        {display:'flex',flexDirection:'column',alignItems:'center',marginBottom:32,gap:4},
  logoText:    {fontFamily:'var(--font-display)',fontSize:32,fontWeight:800,color:'var(--accent)',letterSpacing:'-0.02em'},
  logoSub:     {fontSize:11,color:'var(--text-muted)',letterSpacing:'0.08em',textTransform:'uppercase'},
  toggle:      {display:'flex',background:'var(--bg-elevated)',borderRadius:10,padding:4,marginBottom:28,gap:4},
  toggleBtn:   {flex:1,padding:'8px 0',borderRadius:7,border:'none',background:'transparent',color:'var(--text-muted)',fontSize:12,fontWeight:600,cursor:'pointer',transition:'all 0.15s',fontFamily:'var(--font-display)'},
  toggleActive:{background:'var(--accent)',color:'#000'},
  form:        {display:'flex',flexDirection:'column',gap:16},
  field:       {display:'flex',flexDirection:'column',gap:6},
  label:       {fontSize:11,fontWeight:600,color:'var(--text-secondary)',letterSpacing:'0.04em'},
  input:       {background:'var(--bg-elevated)',border:'1px solid var(--border)',borderRadius:9,padding:'10px 14px',fontSize:13,color:'var(--text-primary)',outline:'none',fontFamily:'inherit',direction:'ltr'},
  error:       {background:'var(--red-dim)',border:'1px solid var(--red)',borderRadius:8,padding:'10px 14px',fontSize:12,color:'var(--red)'},
  btn:         {background:'var(--accent)',color:'#000',border:'none',borderRadius:10,padding:'12px 0',fontSize:14,fontWeight:700,cursor:'pointer',fontFamily:'var(--font-display)',marginTop:4},
  btnDisabled: {opacity:0.5,cursor:'not-allowed'},
}
