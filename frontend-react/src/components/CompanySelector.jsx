/**
 * CompanySelector — Phase 7.5
 * Shared company picker that reads/writes from CompanyContext.
 * Drop it into any page that needs company awareness.
 */
import { useCompany } from '../context/CompanyContext.jsx'
import { useLang } from '../context/LangContext.jsx'
import { useState } from 'react'

export default function CompanySelector({ style = {} }) {
  const { companies, selectedId, setSelectedId, loadingCompanies, createCompany } = useCompany()
  const { tr } = useLang()
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [err, setErr] = useState(null)

  if (loadingCompanies) {
    return <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: '8px 12px' }}>…</div>
  }

  if (companies.length === 0) {
    return (
      <div style={{ display:'flex', flexDirection:'column', gap:8, ...style }}>
        <div style={{ fontSize: 12, color: 'var(--amber)', padding: '8px 12px',
          background: 'var(--amber-dim)', border: '1px solid var(--amber)',
          borderRadius: 8 }}>
          {tr('no_companies')}
        </div>
        <div style={{ display:'flex', gap:8, alignItems:'center' }}>
          <input
            value={name}
            onChange={e => { setName(e.target.value); setErr(null) }}
            placeholder={tr('company_name')}
            style={{
              background:'var(--bg-elevated)',
              border:'1px solid var(--border)',
              borderRadius:8,
              padding:'8px 10px',
              color:'var(--text-primary)',
              fontSize:12,
              minWidth:140,
            }}
          />
          <button
            onClick={async () => {
              if (creating) return
              setCreating(true); setErr(null)
              const res = await createCompany({ name })
              if (!res.ok) setErr(res.error || tr('company_create_failed'))
              setCreating(false)
              if (res.ok) setName('')
            }}
            style={{
              background:'var(--accent)',
              border:'none',
              borderRadius:8,
              padding:'8px 10px',
              fontSize:12,
              fontWeight:700,
              cursor: creating ? 'not-allowed' : 'pointer',
              opacity: creating ? 0.7 : 1,
            }}
            disabled={creating}
          >
            {creating ? tr('creating') : tr('create_company')}
          </button>
        </div>
        {err && (
          <div style={{ fontSize: 11, color: 'var(--red)' }}>
            {err}
          </div>
        )}
      </div>
    )
  }

  return (
    <select
      value={selectedId}
      onChange={e => setSelectedId(e.target.value)}
      style={{
        background:   'var(--bg-elevated)',
        border:       '1px solid var(--border)',
        borderRadius: 8,
        padding:      '8px 12px',
        color:        'var(--text-primary)',
        fontSize:     13,
        fontFamily:   'var(--font-body)',
        cursor:       'pointer',
        minWidth:     180,
        ...style,
      }}
    >
      {companies.map(c => (
        <option key={c.id} value={c.id}>{c.name}</option>
      ))}
    </select>
  )
}
