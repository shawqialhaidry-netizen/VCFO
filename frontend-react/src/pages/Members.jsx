/**
 * Members.jsx — Company membership management (SaaS Core)
 * Uses CompanyContext for role flags: isOwner, canManage, userRole
 * Roles: owner (full) | analyst (view + invite) | viewer (view only)
 */
import { useState, useEffect, useCallback } from 'react'
import { useLang }    from '../context/LangContext.jsx'
import { useCompany } from '../context/CompanyContext.jsx'

const API = '/api/v1'

function getAuthHeaders() {
  try {
    const raw = localStorage.getItem('vcfo_auth')
    return raw ? { Authorization: `Bearer ${JSON.parse(raw).token}` } : {}
  } catch { return {} }
}

const ROLE_STYLE = {
  owner:   { bg: 'rgba(0,212,170,.13)',  border: 'rgba(0,212,170,.3)',  color: 'var(--accent)' },
  analyst: { bg: 'rgba(59,158,255,.13)', border: 'rgba(59,158,255,.3)', color: 'var(--blue)'   },
  viewer:  { bg: 'rgba(150,150,150,.12)',border: 'rgba(150,150,150,.3)',color: 'var(--text-muted)' },
}

function RoleBadge({ role, tr }) {
  const st = ROLE_STYLE[role] || ROLE_STYLE.viewer
  return (
    <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 4,
      textTransform: 'uppercase', letterSpacing: '.06em',
      background: st.bg, border: `1px solid ${st.border}`, color: st.color }}>
      {tr(`role_${role}`) || role}
    </span>
  )
}

function RemoveModal({ member, onConfirm, onCancel, tr }) {
  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,.6)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)',
        borderRadius: 12, padding: 24, maxWidth: 360, width: '100%',
        boxShadow: '0 16px 48px rgba(0,0,0,.5)' }}>
        <div style={{ fontWeight: 700, fontSize: 15, color: 'var(--text-primary)', marginBottom: 8 }}>
          {tr('members_remove_confirm')}
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 20 }}>
          {member.user_name || member.user_email}
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button onClick={onCancel} style={{ padding: '7px 16px', borderRadius: 8,
            border: '1px solid var(--border)', background: 'transparent',
            color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 12 }}>
            {tr('members_cancel')}
          </button>
          <button onClick={onConfirm} style={{ padding: '7px 16px', borderRadius: 8,
            border: '1px solid var(--red)', background: 'rgba(248,113,113,.1)',
            color: 'var(--red)', cursor: 'pointer', fontWeight: 700, fontSize: 12 }}>
            {tr('members_remove')}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function Members() {
  const { selectedId, selectedCompany, isOwner, canManage, userRole, reloadMemberships } = useCompany()
  const { tr } = useLang()

  const [members,       setMembers]       = useState([])
  const [loading,       setLoading]       = useState(false)
  const [err,           setErr]           = useState(null)
  const [email,         setEmail]         = useState('')
  const [role,          setRole]          = useState('analyst')
  const [inviting,      setInviting]      = useState(false)
  const [inviteErr,     setInviteErr]     = useState(null)
  const [inviteOk,      setInviteOk]      = useState(false)
  const [editUid,       setEditUid]       = useState(null)
  const [editRole,      setEditRole]      = useState('analyst')
  const [saving,        setSaving]        = useState(false)
  const [removePending, setRemovePending] = useState(null)

  const canInvite = isOwner

  const load = useCallback(async () => {
    if (!selectedId) return
    setLoading(true); setErr(null)
    try {
      const r = await fetch(`${API}/companies/${selectedId}/members`, { headers: getAuthHeaders() })
      if (!r.ok) { setErr(`Error ${r.status}`); return }
      setMembers(await r.json())
    } catch(e) { setErr(e.message) }
    finally { setLoading(false) }
  }, [selectedId])

  useEffect(() => { load() }, [selectedId, load])

  async function handleInvite(e) {
    e.preventDefault()
    if (!email.trim()) return
    setInviting(true); setInviteErr(null); setInviteOk(false)
    try {
      const r = await fetch(`${API}/companies/${selectedId}/members`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_email: email.trim(), role }),
      })
      const j = await r.json()
      if (!r.ok) { setInviteErr(j.detail || `Error ${r.status}`); return }
      setEmail(''); setInviteOk(true)
      setTimeout(() => setInviteOk(false), 3000)
      load(); reloadMemberships?.()
    } catch(e) { setInviteErr(e.message) }
    finally { setInviting(false) }
  }

  async function handleRoleChange(userId) {
    setSaving(true)
    try {
      const r = await fetch(`${API}/companies/${selectedId}/members/${userId}`, {
        method: 'PATCH',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_email: '', role: editRole }),
      })
      if (r.ok) { setEditUid(null); load(); reloadMemberships?.() }
    } catch(e) { console.error(e) }
    finally { setSaving(false) }
  }

  async function handleRemoveConfirm() {
    if (!removePending) return
    try {
      await fetch(`${API}/companies/${selectedId}/members/${removePending.user_id}`, {
        method: 'DELETE', headers: getAuthHeaders(),
      })
      setRemovePending(null); load(); reloadMemberships?.()
    } catch(e) { console.error(e) }
  }

  const s = {
    page:      { maxWidth: 680, margin: '0 auto', padding: '28px 16px' },
    card:      { background: 'var(--bg-surface)', border: '1px solid var(--border)',
                 borderRadius: 'var(--radius-card)', padding: '20px 24px', marginBottom: 14 },
    label:     { fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase',
                 letterSpacing: '.06em', marginBottom: 5, display: 'block' },
    input:     { width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border)',
                 background: 'var(--bg-elevated)', color: 'var(--text-primary)', fontSize: 13,
                 outline: 'none', boxSizing: 'border-box' },
    select:    { padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border)',
                 background: 'var(--bg-elevated)', color: 'var(--text-primary)', fontSize: 12,
                 cursor: 'pointer', outline: 'none' },
    btnAccent: { padding: '8px 18px', borderRadius: 8, border: 'none', cursor: 'pointer',
                 background: 'var(--accent)', color: '#000', fontWeight: 700, fontSize: 12 },
    btnDanger: { padding: '4px 10px', borderRadius: 6, border: '1px solid var(--red)',
                 background: 'transparent', color: 'var(--red)', fontWeight: 600, fontSize: 11,
                 cursor: 'pointer' },
    btnGhost:  { padding: '4px 10px', borderRadius: 6, border: '1px solid var(--border)',
                 background: 'transparent', color: 'var(--text-muted)', fontWeight: 600, fontSize: 11,
                 cursor: 'pointer' },
    row:       { display: 'flex', alignItems: 'center', gap: 12, padding: '11px 0',
                 borderBottom: '1px solid rgba(255,255,255,.04)' },
    avatar:    { width: 36, height: 36, borderRadius: 10, background: 'var(--bg-elevated)',
                 border: '1px solid var(--border)', display: 'flex', alignItems: 'center',
                 justifyContent: 'center', fontSize: 13, fontWeight: 800, color: 'var(--accent)',
                 flexShrink: 0 },
  }

  if (!selectedId) return (
    <div style={{ ...s.page, textAlign: 'center', paddingTop: 80 }}>
      <div style={{ fontSize: 36, opacity: .2 }}>👥</div>
      <div style={{ color: 'var(--text-muted)', marginTop: 12, fontSize: 13 }}>
        {tr('members_select_company')}
      </div>
    </div>
  )

  const memberCount = members.length
  const countLabel  = `${memberCount} ${memberCount === 1 ? tr('members_sub') : tr('members_sub_plural')}`

  return (
    <div style={s.page}>

      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
          <h1 style={{ fontSize: 20, fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
            {tr('members_title')}
          </h1>
          {userRole && <RoleBadge role={userRole} tr={tr} />}
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          {selectedCompany?.name} · {countLabel}
        </div>
      </div>

      {/* Viewer notice */}
      {userRole === 'viewer' && (
        <div style={{ padding: '10px 14px', marginBottom: 14, borderRadius: 8,
          background: 'rgba(150,150,150,.08)', border: '1px solid rgba(150,150,150,.2)',
          fontSize: 12, color: 'var(--text-muted)', display: 'flex', gap: 8 }}>
          👁 {tr('members_viewer_notice')}
        </div>
      )}

      {/* Error */}
      {err && (
        <div style={{ padding: '10px 14px', marginBottom: 14, borderRadius: 8,
          background: 'rgba(248,113,113,.08)', border: '1px solid var(--red)',
          fontSize: 12, color: 'var(--red)' }}>⚠ {err}
        </div>
      )}

      {/* Invite card */}
      {canInvite && (
        <div style={s.card}>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 14 }}>
            {tr('members_invite_title')}
          </div>
          <form onSubmit={handleInvite}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto auto', gap: 8, alignItems: 'end' }}>
              <div>
                <label style={s.label}>{tr('members_email_label')}</label>
                <input style={s.input} type="email" placeholder="user@example.com"
                  value={email} onChange={e => setEmail(e.target.value)} required />
              </div>
              <div>
                <label style={s.label}>{tr('members_role_label')}</label>
                <select style={s.select} value={role} onChange={e => setRole(e.target.value)}>
                  {isOwner && <option value="owner">{tr('role_owner')}</option>}
                  <option value="analyst">{tr('role_analyst')}</option>
                  <option value="viewer">{tr('role_viewer')}</option>
                </select>
              </div>
              <button type="submit" style={{ ...s.btnAccent, alignSelf: 'flex-end' }} disabled={inviting}>
                {inviting ? '...' : tr('members_invite_btn')}
              </button>
            </div>
            {inviteErr && <div style={{ color: 'var(--red)', fontSize: 12, marginTop: 8 }}>⚠ {inviteErr}</div>}
            {inviteOk  && <div style={{ color: 'var(--accent)', fontSize: 12, marginTop: 8 }}>✓ {tr('members_invite_ok')}</div>}
          </form>
        </div>
      )}

      {/* Members list */}
      <div style={s.card}>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 14 }}>
          {tr('members_list_title')}
        </div>

        {loading && !members.length && (
          <div style={{ textAlign: 'center', padding: 24, color: 'var(--text-muted)', fontSize: 12 }}>
            {tr('members_loading')}
          </div>
        )}
        {!loading && !members.length && (
          <div style={{ textAlign: 'center', padding: 24, color: 'var(--text-muted)', fontSize: 12 }}>
            {tr('members_empty')}
          </div>
        )}

        {members.map(m => {
          const initials  = (m.user_name || m.user_email || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
          const isEditing = editUid === m.user_id
          return (
            <div key={m.id} style={s.row}>
              <div style={s.avatar}>{initials}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {m.user_name || m.user_email}
                </div>
                {m.user_name && (
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>{m.user_email}</div>
                )}
              </div>

              {isEditing ? (
                <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
                  <select style={{ ...s.select, fontSize: 11 }} value={editRole} onChange={e => setEditRole(e.target.value)}>
                    <option value="owner">{tr('role_owner')}</option>
                    <option value="analyst">{tr('role_analyst')}</option>
                    <option value="viewer">{tr('role_viewer')}</option>
                  </select>
                  <button style={s.btnAccent} onClick={() => handleRoleChange(m.user_id)} disabled={saving}>
                    {saving ? tr('members_saving') : tr('members_save')}
                  </button>
                  <button style={s.btnGhost} onClick={() => setEditUid(null)}>{tr('members_cancel')}</button>
                </div>
              ) : (
                <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
                  <RoleBadge role={m.role} tr={tr} />
                  {canManage && (
                    <>
                      <button style={s.btnGhost} onClick={() => { setEditUid(m.user_id); setEditRole(m.role) }}>
                        {tr('members_change_role')}
                      </button>
                      <button style={s.btnDanger} onClick={() => setRemovePending(m)}>
                        {tr('members_remove')}
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Role guide */}
      <div style={{ ...s.card, background: 'var(--bg-elevated)' }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)',
          textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 12 }}>
          {tr('members_role_guide')}
        </div>
        {['owner', 'analyst', 'viewer'].map(r => (
          <div key={r} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, marginBottom: 8 }}>
            <RoleBadge role={r} tr={tr} />
            <span style={{ fontSize: 12, color: 'var(--text-secondary)', paddingTop: 1 }}>
              {tr(`role_${r}_perms`)}
            </span>
          </div>
        ))}
      </div>

      {/* Remove modal */}
      {removePending && (
        <RemoveModal member={removePending} tr={tr}
          onConfirm={handleRemoveConfirm} onCancel={() => setRemovePending(null)} />
      )}
    </div>
  )
}
