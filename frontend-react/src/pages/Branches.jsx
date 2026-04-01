/**
 * Branches.jsx — Branch Management Page
 * Full CRUD: list, create, edit, soft-delete
 * Company-isolated, auth-protected, i18n-ready (EN/AR/TR)
 */
import { useState, useEffect, useCallback } from 'react'
import { useCompany } from '../context/CompanyContext.jsx'
import { useLang }    from '../context/LangContext.jsx'
import { usePeriodScope } from '../context/PeriodScopeContext.jsx'
import { formatCompact, formatFull, formatDual, formatPct, formatMultiple, formatDays } from '../utils/numberFormat.js'
import { buildAnalysisQuery } from '../utils/buildAnalysisQuery.js'

const API = '/api/v1'

/** FastAPI/Pydantic detail can be string, object, or validation array */
function formatApiError(d, status) {
  const det = d?.detail
  if (det == null) return `Error ${status}`
  if (typeof det === 'string') return det
  if (Array.isArray(det)) {
    const first = det[0]
    if (first && typeof first === 'object') {
      const loc = (first.loc || []).join('.')
      const msg = first.msg || first.type || JSON.stringify(first)
      return loc ? `${loc}: ${msg}` : msg
    }
    return String(det[0])
  }
  if (typeof det === 'object') try { return JSON.stringify(det) } catch { return `Error ${status}` }
  return String(det)
}

function getAuthHeaders() {
  try {
    const raw   = localStorage.getItem('vcfo_auth')
    const token = raw ? JSON.parse(raw)?.token : null
    return token
      ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
      : { 'Content-Type': 'application/json' }
  } catch {
    return { 'Content-Type': 'application/json' }
  }
}

const CURRENCIES = ['USD', 'SAR', 'AED', 'KWD', 'QAR', 'BHD', 'OMR', 'EGP', 'TRY', 'EUR', 'GBP']

// ── Toast notification ────────────────────────────────────────────────────────
function Toast({ msg, ok, onDone }) {
  useEffect(() => { const t = setTimeout(onDone, 3000); return () => clearTimeout(t) }, [onDone])
  return (
    <div style={{
      position: 'fixed', bottom: 28, right: 28, zIndex: 9999,
      background: ok ? 'rgba(16,217,138,.12)' : 'rgba(255,77,109,.12)',
      border: `1px solid ${ok ? 'var(--green)' : 'var(--red)'}`,
      color: ok ? 'var(--green)' : 'var(--red)',
      padding: '12px 20px', borderRadius: 10, fontSize: 13, fontWeight: 600,
      backdropFilter: 'blur(12px)', boxShadow: '0 8px 32px rgba(0,0,0,.4)',
      display: 'flex', alignItems: 'center', gap: 10, maxWidth: 340,
      animation: 'slideUp .25s ease',
    }}>
      <span style={{ fontSize: 16 }}>{ok ? '✓' : '✗'}</span>
      {msg}
    </div>
  )
}

// ── Confirm delete modal ───────────────────────────────────────────────────────
function DeleteModal({ branch, onConfirm, onCancel, tr }) {
  return (
    <div style={s.overlay}>
      <div style={{ ...s.modal, maxWidth: 420 }}>
        <div style={s.modalHeader}>
          <span style={{ color: 'var(--red)', fontSize: 20 }}>⚠</span>
          <span style={{ fontWeight: 700, fontSize: 15 }}>{tr('branch_delete')}</span>
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: 13, margin: '12px 0 6px', lineHeight: 1.6 }}>
          {tr('branch_confirm_delete')}
        </p>
        <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>
          {branch.name}{branch.code ? ` (${branch.code})` : ''}
        </p>
        <p style={{ color: 'var(--text-muted)', fontSize: 12, marginBottom: 20 }}>
          {tr('branch_delete_warning')}
        </p>
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <button onClick={onCancel} style={s.btnSecondary}>{tr('branch_cancel')}</button>
          <button onClick={onConfirm} style={{ ...s.btn, background: 'var(--red)', color: '#fff' }}>
            {tr('branch_delete')}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Branch form (create + edit) ───────────────────────────────────────────────
function BranchForm({ branch, companyId, onSave, onCancel, tr, lang }) {
  const isEdit = !!branch?.id
  const [form, setForm] = useState({
    code:      branch?.code     || '',
    name:      branch?.name     || '',
    name_ar:   branch?.name_ar  || '',
    city:      branch?.city     || '',
    country:   branch?.country  || '',
    currency:  branch?.currency || 'USD',
    is_active: branch?.is_active ?? true,
  })
  const [saving, setSaving] = useState(false)
  const [err,    setErr]    = useState(null)

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  async function handleSubmit() {
    if (!form.name.trim()) { setErr(tr('branch_name') + ' ' + 'required'); return }
    const cid = companyId != null ? String(companyId).trim() : ''
    if (!isEdit && !cid) {
      setErr(tr('branch_select_company_first'))
      return
    }
    setSaving(true); setErr(null)
    try {
      const url    = isEdit ? `${API}/branches/${branch.id}` : `${API}/branches`
      const method = isEdit ? 'PUT' : 'POST'
      // Create: explicit JSON keys only — never rely on spread with undefined company_id
      // (JSON.stringify drops undefined, which causes 422 missing company_id).
      const body   = isEdit
        ? {
            code:      form.code || null,
            name:      form.name.trim(),
            name_ar:   form.name_ar?.trim() || null,
            city:      form.city?.trim() || null,
            country:   form.country?.trim() || null,
            currency:  form.currency || 'USD',
            is_active: form.is_active,
          }
        : {
            company_id: cid,
            code:       (form.code && String(form.code).trim()) || null,
            name:       form.name.trim(),
            name_ar:    (form.name_ar && String(form.name_ar).trim()) || null,
            city:       (form.city && String(form.city).trim()) || null,
            country:    (form.country && String(form.country).trim()) || null,
            currency:   form.currency || 'USD',
          }
      const r = await fetch(url, { method, headers: getAuthHeaders(), body: JSON.stringify(body) })
      if (!r.ok) {
        const d = await r.json().catch(() => ({}))
        const msg = formatApiError(d, r.status)
        setErr(msg)
        return
      }
      const saved = await r.json()
      onSave(saved, isEdit)
    } catch (e) { setErr(e.message) }
    finally { setSaving(false) }
  }

  const isRtl = lang === 'ar'

  return (
    <div style={s.overlay}>
      <div style={{ ...s.modal, maxWidth: 520 }}>
        {/* Header */}
        <div style={s.modalHeader}>
          <div style={s.modalIconWrap}>
            <IcoBranch size={16} />
          </div>
          <span style={{ fontWeight: 700, fontSize: 15 }}>
            {isEdit ? tr('branch_edit') : tr('branch_add')}
          </span>
          <button onClick={onCancel} style={s.closeBtn}>✕</button>
        </div>

        {/* Form grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px 16px', padding: '20px 0 8px' }}>
          {/* Code */}
          <label style={s.label}>
            <span>{tr('branch_code')}</span>
            <input
              style={s.input} value={form.code}
              onChange={e => set('code', e.target.value)}
              placeholder={tr('branch_code_placeholder')}
              dir="ltr"
            />
          </label>

          {/* Currency */}
          <label style={s.label}>
            <span>{tr('branch_currency')}</span>
            <select style={s.input} value={form.currency} onChange={e => set('currency', e.target.value)}>
              {CURRENCIES.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>

          {/* Name (full width) */}
          <label style={{ ...s.label, gridColumn: '1 / -1' }}>
            <span>{tr('branch_name')} <span style={{ color: 'var(--red)' }}>*</span></span>
            <input
              style={s.input} value={form.name}
              onChange={e => set('name', e.target.value)}
              placeholder={tr('branch_name_placeholder')}
              dir={isRtl ? 'rtl' : 'ltr'}
            />
          </label>

          {/* Arabic name (full width) */}
          <label style={{ ...s.label, gridColumn: '1 / -1' }}>
            <span>{tr('branch_name_ar')}</span>
            <input
              style={{ ...s.input, textAlign: 'right' }}
              value={form.name_ar}
              onChange={e => set('name_ar', e.target.value)}
              placeholder={tr('branch_name_ar_placeholder')}
              dir="rtl"
            />
          </label>

          {/* City */}
          <label style={s.label}>
            <span>{tr('branch_city')}</span>
            <input
              style={s.input} value={form.city}
              onChange={e => set('city', e.target.value)}
              placeholder={tr('branch_city_placeholder')}
            />
          </label>

          {/* Country */}
          <label style={s.label}>
            <span>{tr('branch_country')}</span>
            <input
              style={s.input} value={form.country}
              onChange={e => set('country', e.target.value)}
              placeholder={tr('branch_country_placeholder')}
            />
          </label>

          {/* Active toggle */}
          {isEdit && (
            <label style={{ ...s.label, gridColumn: '1 / -1', flexDirection: 'row', alignItems: 'center', gap: 12, cursor: 'pointer' }}>
              <div
                onClick={() => set('is_active', !form.is_active)}
                style={{
                  width: 44, height: 24, borderRadius: 12,
                  background: form.is_active ? 'var(--accent)' : 'var(--border)',
                  position: 'relative', transition: 'background .2s', cursor: 'pointer', flexShrink: 0,
                }}
              >
                <div style={{
                  position: 'absolute', top: 3, left: form.is_active ? 22 : 3,
                  width: 18, height: 18, borderRadius: '50%', background: '#fff',
                  transition: 'left .2s', boxShadow: '0 1px 4px rgba(0,0,0,.3)',
                }} />
              </div>
              <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                {form.is_active ? tr('branch_active') : tr('branch_inactive')}
              </span>
            </label>
          )}
        </div>

        {err && (
          <div style={{ color: 'var(--red)', fontSize: 12, marginBottom: 8, padding: '8px 10px', background: 'var(--red-dim)', borderRadius: 6 }}>
            {err}
          </div>
        )}

        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', paddingTop: 8, borderTop: '1px solid var(--border)' }}>
          <button onClick={onCancel} style={s.btnSecondary} disabled={saving}>{tr('branch_cancel')}</button>
          <button onClick={handleSubmit} style={s.btnPrimary} disabled={saving}>
            {saving ? '...' : tr('branch_save')}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Status badge ──────────────────────────────────────────────────────────────
function StatusBadge({ active, tr }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '3px 10px', borderRadius: 20, fontSize: 11, fontWeight: 600,
      background: active ? 'var(--green-dim)' : 'rgba(107,114,128,.12)',
      color: active ? 'var(--green)' : 'var(--text-muted)',
      border: `1px solid ${active ? 'rgba(16,217,138,.25)' : 'var(--border)'}`,
    }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'currentColor' }} />
      {active ? tr('branch_active') : tr('branch_inactive')}
    </span>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function Branches() {
  const { selectedId: companyId, selectedCompany, canWrite, canManage } = useCompany()
  const { tr, lang }                               = useLang()
  const { window: brWindow, toQueryString }       = usePeriodScope()

  const [branches,    setBranches]    = useState([])
  const [loading,     setLoading]     = useState(false)
  const [err,         setErr]         = useState(null)
  const [showForm,    setShowForm]    = useState(false)
  const [editBranch,  setEditBranch]  = useState(null)   // null = create mode
  const [deletePending, setDeletePending] = useState(null)
  const [toast,       setToast]       = useState(null)
  const [showInactive, setShowInactive] = useState(false)
  const [analysisBranch, setAnalysisBranch] = useState(null)  // branch being analysed
  const [activeTab, setActiveTab] = useState('list')              // 'list' | 'intelligence'
  const [intel, setIntel] = useState(null)
  const [intelLoading, setIntelLoading] = useState(false)

  // ── Fetch branches ────────────────────────────────────────────────────────
  const load = useCallback(async () => {
    if (!companyId) return
    setLoading(true); setErr(null)
    try {
      const r = await fetch(`${API}/branches?company_id=${companyId}`, { headers: getAuthHeaders() })
      if (!r.ok) { setErr(`Error ${r.status}`); return }
      const data = await r.json()
      setBranches(data)
    } catch (e) { setErr(e.message) }
    finally { setLoading(false) }
  }, [companyId])

  useEffect(() => { load() }, [load])

  // ── Handlers ──────────────────────────────────────────────────────────────
  function handleSaved(saved, isEdit) {
    setBranches(prev =>
      isEdit
        ? prev.map(b => b.id === saved.id ? saved : b)
        : [saved, ...prev]
    )
    setShowForm(false); setEditBranch(null)
    showToast(tr(isEdit ? 'branch_updated_ok' : 'branch_created_ok'), true)
  }

  async function handleDelete() {
    if (!deletePending) return
    try {
      const r = await fetch(`${API}/branches/${deletePending.id}`, { method: 'DELETE', headers: getAuthHeaders() })
      if (!r.ok && r.status !== 204) { showToast(`Error ${r.status}`, false); return }
      setBranches(prev => prev.map(b => b.id === deletePending.id ? { ...b, is_active: false } : b))
      showToast(tr('branch_deleted_ok'), true)
    } catch (e) { showToast(e.message, false) }
    finally { setDeletePending(null) }
  }

  function showToast(msg, ok) {
    setToast({ msg, ok })
  }

  // Clear intel when company, language, or window changes so it re-fetches fresh data
useEffect(() => {
  setIntel(null);
}, [companyId, lang, brWindow]);

const loadIntel = useCallback(async () => {
  if (!companyId) return;

  setIntelLoading(true);
  try {
    const qs = buildAnalysisQuery(toQueryString, { lang, window: brWindow, consolidate: false })
    if (qs === null) return
    const r = await fetch(
      `${API}/companies/${companyId}/branch-intelligence?${qs}`,
      { headers: getAuthHeaders() }
    );

    if (!r.ok) throw new Error(`HTTP ${r.status}`);

    const json = await r.json();
    setIntel(json);
  } catch (e) {
    console.error(e);
  } finally {
    setIntelLoading(false);
  }
}, [companyId, lang, brWindow, toQueryString]);

useEffect(() => {
  if (activeTab !== 'intelligence') return;
  loadIntel();
}, [activeTab, loadIntel]);

  function openEdit(b) { setEditBranch(b); setShowForm(true) }
  function openCreate() { setEditBranch(null); setShowForm(true) }
  function closeForm() { setShowForm(false); setEditBranch(null) }
  function openAnalysis(b) { setAnalysisBranch(b) }

  const filtered = branches.filter(b => showInactive ? true : b.is_active)

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div style={s.page}>
      {/* ── Page header ── */}
      <div style={s.pageHeader}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={s.pageIconWrap}><IcoBranch size={18} /></div>
          <div>
            <h1 style={s.pageTitle}>{tr('branches_page_title')}</h1>
            {selectedCompany && (
              <p style={s.pageSubtitle}>{selectedCompany.name}</p>
            )}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--accent)' }}>
                {tr('data_source_branch_view_label')}
              </span>
              <span
                title={tr('data_source_branch_vs_company_note')}
                aria-label={tr('data_source_branch_vs_company_note')}
                style={{ cursor: 'help', fontSize: 13, color: 'var(--text-muted)' }}>
                ℹ️
              </span>
            </div>
            <p style={{
              fontSize: 11, color: 'var(--text-muted)', marginTop: 6, marginBottom: 0,
              maxWidth: 640, lineHeight: 1.5,
            }}>
              {tr('data_source_branch_vs_company_note')}
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          {/* Show inactive toggle */}
          <button
            onClick={() => setShowInactive(v => !v)}
            style={{ ...s.btnSecondary, fontSize: 12, opacity: showInactive ? 1 : 0.6 }}
          >
            {showInactive ? `👁 ${tr('show_all')}` : `👁 ${tr('active_only')}`}
          </button>
          {canWrite !== false && companyId && (
            <button onClick={openCreate} style={s.btnPrimary}>
              <span style={{ fontSize: 16, lineHeight: 1 }}>+</span> {tr('branch_add')}
            </button>
          )}
        </div>
      </div>

      {/* ── Tab switcher ── */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 16, background: 'var(--bg-elevated)',
        border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden', alignSelf: 'flex-start' }}>
        {[{k:'list',l:tr('branch_list_tab')},{k:'intelligence',l:tr('intelligence_tab')}].map(t => (
          <button key={t.k} onClick={() => setActiveTab(t.k)}
            style={{ padding: '7px 18px', fontSize: 12, fontWeight: 600, border: 'none', cursor: 'pointer',
              background: activeTab === t.k ? 'var(--accent)' : 'transparent',
              color:      activeTab === t.k ? '#000' : 'var(--text-secondary)',
              transition: 'all .15s' }}>
            {t.l}
          </button>
        ))}
      </div>

      {/* ── Stats row ── */}
      {branches.length > 0 && (
        <div style={s.statsRow}>
          <StatCard label={tr('branch_active')}   value={branches.filter(b => b.is_active).length}  color="var(--green)" />
          <StatCard label={tr('branch_inactive')} value={branches.filter(b => !b.is_active).length} color="var(--text-muted)" />
          <StatCard label={tr('branch_total')}     value={branches.length}                            color="var(--accent)" />
        </div>
      )}

      {/* ── Loading ── */}
      {loading && (
        <div style={s.center}>
          <div style={s.spinner} />
        </div>
      )}

      {/* ── Error ── */}
      {err && !loading && (
        <div style={s.errorBox}>
          <span>⚠ {err}</span>
          <button onClick={load} style={{ ...s.btnSecondary, fontSize: 12 }}>{tr('retry')}</button>
        </div>
      )}

      {/* ── Empty state ── */}
      {!loading && !err && filtered.length === 0 && (
        <div style={s.emptyState}>
          <div style={s.emptyIcon}><IcoBranch size={32} /></div>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14, margin: '12px 0 20px' }}>
            {branches.length === 0 ? tr('branch_empty_state') : tr('branch_no_active_hint')}
          </p>
          {branches.length === 0 && canWrite !== false && companyId && (
            <button onClick={openCreate} style={s.btnPrimary}>
              {tr('branch_add')}
            </button>
          )}
        </div>
      )}

      {activeTab === 'list' && (<>
      {/* ── Branch table ── */}
      {!loading && !err && filtered.length > 0 && (
        <div style={s.tableWrap}>
          <table style={s.table}>
            <thead>
              <tr>
                {[
                  tr('branch_code'),
                  tr('branch_name'),
                  tr('branch_name_ar'),
                  tr('branch_city'),
                  tr('branch_country'),
                  tr('branch_currency'),
                  tr('branch_status'),
                  tr('branch_created'),
                  '',
                ].map((h, i) => (
                  <th key={i} style={s.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map(b => (
                <BranchRow
                  key={b.id}
                  branch={b}
                  onEdit={() => openEdit(b)}
                  onDelete={() => setDeletePending(b)}
                  onAnalyse={() => openAnalysis(b)}
                  canWrite={canWrite}
                  tr={tr}
                  lang={lang}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Modals ── */}
      {showForm && (
        <BranchForm
          branch={editBranch}
          companyId={companyId}
          onSave={handleSaved}
          onCancel={closeForm}
          tr={tr}
          lang={lang}
        />
      )}

      {deletePending && (
        <DeleteModal
          branch={deletePending}
          onConfirm={handleDelete}
          onCancel={() => setDeletePending(null)}
          tr={tr}
        />
      )}

      </>
      )}

      {/* ── Toast ── */}

      {/* ── Intelligence Panel ── */}
      {activeTab === 'intelligence' && (
        <IntelligencePanel intel={intel} loading={intelLoading} />
      )}

      {analysisBranch && (
        <BranchAnalysisPanel
          branch={analysisBranch}
          onClose={() => setAnalysisBranch(null)}
          window={brWindow}
        />
      )}

      {toast && <Toast msg={toast.msg} ok={toast.ok} onDone={() => setToast(null)} />}

      <style>{`
        @keyframes slideUp {
          from { transform: translateY(16px); opacity: 0; }
          to   { transform: translateY(0);    opacity: 1; }
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}

// ── Branch row ────────────────────────────────────────────────────────────────
function BranchRow({ branch: b, onEdit, onDelete, onAnalyse, canWrite, tr, lang }) {
  const [hover, setHover] = useState(false)
  const dim = !b.is_active
  const nameDisplay = lang === 'ar' && b.name_ar ? b.name_ar : b.name

  return (
    <tr
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        background: hover ? 'var(--bg-hover)' : 'transparent',
        opacity: dim ? 0.5 : 1,
        transition: 'background .15s, opacity .15s',
      }}
    >
      <td style={s.td}>
        {b.code
          ? <span style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--accent)', background: 'var(--accent-dim)', padding: '2px 7px', borderRadius: 4 }}>{b.code}</span>
          : <span style={{ color: 'var(--text-muted)' }}>—</span>
        }
      </td>
      <td style={{ ...s.td, fontWeight: 600 }}>{b.name}</td>
      <td style={{ ...s.td, textAlign: 'right', direction: 'rtl', color: b.name_ar ? 'var(--text-primary)' : 'var(--text-muted)' }}>
        {b.name_ar || '—'}
      </td>
      <td style={{ ...s.td, color: 'var(--text-secondary)' }}>{b.city || '—'}</td>
      <td style={{ ...s.td, color: 'var(--text-secondary)' }}>{b.country || '—'}</td>
      <td style={s.td}>
        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', letterSpacing: '.06em' }}>
          {b.currency}
        </span>
      </td>
      <td style={s.td}><StatusBadge active={b.is_active} tr={tr} /></td>
      <td style={{ ...s.td, color: 'var(--text-muted)', fontSize: 11 }}>
        {b.created_at ? new Date(b.created_at).toLocaleDateString() : '—'}
      </td>
      <td style={{ ...s.td, textAlign: 'right' }}>
        <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
          <ActionBtn icon="📊" label={tr('analyse')} onClick={onAnalyse} color="var(--accent)" />
          {canWrite !== false && (
            <ActionBtn icon="✎" label={tr('branch_edit')} onClick={onEdit} color="var(--blue)" />
          )}
          {canWrite !== false && b.is_active && (
            <ActionBtn icon="⊘" label={tr('branch_delete')} onClick={onDelete} color="var(--red)" />
          )}
        </div>
      </td>
    </tr>
  )
}


// ── Intelligence Panel ────────────────────────────────────────────────────────
function IntelligencePanel({ intel, loading }) {
  const { tr } = useLang()
  if (loading) return (
    <div style={{ textAlign: 'center', padding: 48 }}>
      <div style={{ width: 28, height: 28, margin: '0 auto', border: '2px solid var(--border)',
        borderTop: '2px solid var(--accent)', borderRadius: '50%', animation: 'spin .7s linear infinite' }} />
      <div style={{ marginTop: 12, fontSize: 12, color: 'var(--text-muted)' }}>{tr('loading_intel')}</div>
    </div>
  )
  if (!intel || !intel.has_data) return (
    <div style={{ textAlign: 'center', padding: '40px 16px' }}>
      <div style={{ fontSize: 32, opacity: .25, marginBottom: 12 }}>📊</div>
      <div style={{ fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6 }}>{tr('no_branch_data')}</div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Upload trial balances with branch assignment to see intelligence.</div>
    </div>
  )

  // formatCompact imported from numberFormat.js
  // formatPct imported from numberFormat.js
  const clr  = v => v==null ? 'var(--text-muted)' : v>=0 ? 'var(--green)' : 'var(--red)'

  const PRIORITY_COLOR = { high: 'var(--red)', medium: 'var(--amber)', low: 'var(--text-muted)' }
  const INSIGHT_ICON   = { lead: '🏆', improving: '📈', risk: '⚠️', inefficient: '⚡', opportunity: '💡' }
  const RANK_KEYS = [
    { k: 'revenue',       label: tr('col_revenue'),     fmt: v => formatCompact(v) },
    { k: 'profitability', label: tr('col_net_margin'),   fmt: v => formatPct(v) },
    { k: 'efficiency',    label: tr('col_exp_ratio'),    fmt: v => formatPct(v) },
    { k: 'growth',        label: tr('col_mom_growth'),   fmt: v => v==null?'—':`${v>0?'+':''}${v.toFixed(1)}%` },
  ]

  const cls = intel.classifications || {}

  const CLASSIFICATION_DEFS = [
    { key: 'strongest_branch',   icon: '🏆', label: tr('strongest'),      accent: 'var(--accent)' },
    { key: 'best_margin_branch', icon: '💎', label: tr('best_margin'),     accent: 'var(--green)'  },
    { key: 'fastest_growing',    icon: '📈', label: tr('fastest_growing'), accent: 'var(--blue)'   },
    { key: 'highest_cost_branch',icon: '⚡', label: tr('highest_cost'),    accent: 'var(--amber)'  },
    { key: 'weakest_branch',     icon: '🔴', label: tr('weakest'),         accent: 'var(--red)'    },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{
        fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.5, padding: '10px 12px',
        background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8,
      }}>
        <span style={{ fontWeight: 700, color: 'var(--accent)' }}>{tr('data_source_branch_view_label')}</span>
        <span
          title={tr('data_source_branch_vs_company_note')}
          aria-label={tr('data_source_branch_vs_company_note')}
          style={{ cursor: 'help', marginInlineStart: 8 }}>
          ℹ️
        </span>
        <div style={{ marginTop: 6, fontSize: 10 }}>{tr('data_source_branch_vs_company_note')}</div>
      </div>

      {/* ── Classifications row ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', gap: 10 }}>
        {CLASSIFICATION_DEFS.map(({ key, icon, label, accent }) => {
          const branch = cls[key]
          return (
            <div key={key} style={{ background: 'var(--bg-surface)', border: `1px solid var(--border)`,
              borderTop: `2px solid ${accent}`, borderRadius: 10, padding: '12px 14px' }}>
              <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase',
                letterSpacing: '.08em', marginBottom: 4 }}>{icon} {label}</div>
              <div style={{ fontWeight: 700, fontSize: 13, color: branch ? accent : 'var(--text-muted)' }}>
                {branch ? branch.branch_name : '—'}
              </div>
              {branch?.value != null && (
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                  {typeof branch.value === 'number' && branch.value > 1000 ? formatCompact(branch.value) : formatPct(branch.value)}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* ── Rankings table ── */}
      <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
        <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)',
          fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.08em' }}>
          {tr('rankings')}
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr>
                <th style={{ padding: '8px 16px', textAlign: 'left', fontSize: 10, fontWeight: 700,
                  color: 'var(--text-muted)', borderBottom: '1px solid var(--border)', textTransform: 'uppercase' }}>{tr('col_branch')}</th>
                {RANK_KEYS.map(r => (
                  <th key={r.k} style={{ padding: '8px 12px', textAlign: 'right', fontSize: 10, fontWeight: 700,
                    color: 'var(--text-muted)', borderBottom: '1px solid var(--border)', textTransform: 'uppercase' }}>
                    {r.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(intel.branches || []).filter(b => b.has_data).map((b, i) => (
                <tr key={b.branch_id} style={{ borderBottom: '1px solid rgba(255,255,255,.04)',
                  background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,.015)' }}>
                  <td style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {b.flags?.is_strongest && <span style={{ marginRight: 6 }}>🏆</span>}
                    {b.branch_name}
                    {b.city && <span style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: 6 }}>{b.city}</span>}
                  </td>
                  {RANK_KEYS.map(r => {
                    const vals = intel.rankings?.[r.k] || []
                    const entry = vals.find(x => x.branch_id === b.branch_id)
                    const rank  = vals.findIndex(x => x.branch_id === b.branch_id) + 1
                    return (
                      <td key={r.k} style={{ padding: '10px 12px', textAlign: 'right', fontFamily: 'monospace',
                        color: rank === 1 ? 'var(--accent)' : 'var(--text-secondary)' }}>
                        {entry ? r.fmt(entry.value) : '—'}
                        {rank === 1 && <span style={{ marginLeft: 4, fontSize: 9 }}>▲</span>}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Per-branch profile cards ── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {(intel.branches || []).filter(b => b.has_data).map(b => {
          const p = b.profile || {}
          return (
            <div key={b.branch_id} style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)',
              borderRadius: 10, overflow: 'hidden' }}>
              {/* Branch header */}
              <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)',
                display: 'flex', alignItems: 'center', gap: 10, background: 'var(--bg-elevated)' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: 14 }}>
                    {b.flags?.is_strongest && '🏆 '}{b.branch_name}
                    {b.flags?.is_improving && <span style={{ marginLeft: 8, fontSize: 10, color: 'var(--green)',
                      background: 'rgba(0,200,100,.1)', padding: '1px 6px', borderRadius: 4 }}>{tr('trend_growing_short')}</span>}
                    {b.flags?.is_declining && <span style={{ marginLeft: 8, fontSize: 10, color: 'var(--red)',
                      background: 'rgba(248,113,113,.1)', padding: '1px 6px', borderRadius: 4 }}>{tr('trend_declining_short')}</span>}
                    {b.flags?.is_high_cost && <span style={{ marginLeft: 8, fontSize: 10, color: 'var(--amber)',
                      background: 'rgba(251,191,36,.1)', padding: '1px 6px', borderRadius: 4 }}>⚡ {tr('high_cost_label')}</span>}
                  </div>
                  {b.city && <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{b.city} · {b.period_count} {tr('label_periods')}</div>}
                </div>
                {/* KPI quick stats */}
                <div style={{ display: 'flex', gap: 16, fontSize: 11 }}>
                  <span style={{ color: 'var(--accent)', fontFamily: 'monospace', fontWeight: 700 }}>
                    {formatCompact(b.kpis?.revenue)}
                  </span>
                  <span style={{ color: clr(b.kpis?.net_margin_pct), fontFamily: 'monospace' }}>
                    {formatPct(b.kpis?.net_margin_pct)} {tr('label_nm')}
                  </span>
                  {b.kpis?.expense_ratio != null && (
                    <span style={{ color: (b.kpis.expense_ratio > 60) ? 'var(--red)' : 'var(--text-muted)', fontFamily: 'monospace' }}>
                      {formatPct(b.kpis.expense_ratio)} {tr('label_exp')}
                    </span>
                  )}
                </div>
              </div>

              <div style={{ padding: '12px 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: 12 }}>
                {p.strengths?.length > 0 && (
                  <div>
                    <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--green)', textTransform: 'uppercase',
                      letterSpacing: '.06em', marginBottom: 6 }}>✓ {tr('strengths')}</div>
                    {p.strengths.map((s, i) => (
                      <div key={i} style={{ color: 'var(--text-secondary)', marginBottom: 3 }}>{s}</div>
                    ))}
                  </div>
                )}
                {(p.weaknesses?.length > 0 || p.warnings?.length > 0) && (
                  <div>
                    {p.weaknesses?.length > 0 && (
                      <>
                        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--amber)', textTransform: 'uppercase',
                          letterSpacing: '.06em', marginBottom: 6 }}>⚠ {tr('weaknesses')}</div>
                        {p.weaknesses.map((w, i) => (
                          <div key={i} style={{ color: 'var(--text-secondary)', marginBottom: 3 }}>{w}</div>
                        ))}
                      </>
                    )}
                    {p.warnings?.length > 0 && (
                      <>
                        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--red)', textTransform: 'uppercase',
                          letterSpacing: '.06em', marginBottom: 6, marginTop: p.weaknesses?.length ? 8 : 0 }}>🔴 {tr('warnings_label')}</div>
                        {p.warnings.map((w, i) => (
                          <div key={i} style={{ color: 'var(--red)', marginBottom: 3 }}>{w}</div>
                        ))}
                      </>
                    )}
                  </div>
                )}
              </div>

              {p.actions?.length > 0 && (
                <div style={{ padding: '10px 16px', borderTop: '1px solid var(--border)',
                  display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {p.actions.map((a, i) => (
                    <div key={i} style={{ fontSize: 11, padding: '4px 10px', borderRadius: 6,
                      border: `1px solid ${PRIORITY_COLOR[a.priority]}33`,
                      color: PRIORITY_COLOR[a.priority], background: `${PRIORITY_COLOR[a.priority]}10` }}>
                      {a.priority === 'high' ? '⬆' : a.priority === 'medium' ? '→' : '·'} {a.detail}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* ── Company insights ── */}
      {intel.company_insights?.length > 0 && (
        <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)',
            fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.08em' }}>
            {tr('cfo_insights')}
          </div>
          <div style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 8 }}>
            {intel.company_insights.map((ins, i) => (
              <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', fontSize: 12,
                padding: '8px 10px', borderRadius: 8, background: 'var(--bg-elevated)' }}>
                <span style={{ fontSize: 14, flexShrink: 0 }}>{INSIGHT_ICON[ins.type] || '•'}</span>
                <div>
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)', marginInlineEnd: 6 }}>{ins.branch}:</span>
                  <span style={{ color: 'var(--text-secondary)' }}>{ins.message}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Global CFO Actions ── */}
      {intel.cfo_actions?.filter(a => a.priority === 'high').length > 0 && (
        <div style={{ background: 'rgba(248,113,113,.05)', border: '1px solid rgba(248,113,113,.2)',
          borderRadius: 10, padding: '12px 16px' }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--red)', textTransform: 'uppercase',
            letterSpacing: '.08em', marginBottom: 10 }}>🚨 {tr('high_priority_actions')}</div>
          {intel.cfo_actions.filter(a => a.priority === 'high').map((a, i) => (
            <div key={i} style={{ display: 'flex', gap: 10, marginBottom: 6, fontSize: 12 }}>
              <span style={{ color: 'var(--red)', fontWeight: 700, minWidth: 80 }}>{a.branch}:</span>
              <span style={{ color: 'var(--text-secondary)' }}>{a.detail}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Branch Analysis Panel ─────────────────────────────────────────────────────
function BranchAnalysisPanel({ branch, onClose, window: brWindow }) {
  const { tr, lang } = useLang()
  const { toQueryString } = usePeriodScope()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)

  useEffect(() => {
    if (!branch || !branch.id) return;
  
    setLoading(true);
    setErr(null);
  
    const qs = buildAnalysisQuery(toQueryString, { lang, window: brWindow, consolidate: false })
    if (qs === null) {
      setErr('Invalid period scope')
      setLoading(false)
      return
    }
    fetch(`${API}/branches/${branch.id}/analysis?${qs}`, {
      headers: getAuthHeaders()
    })
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(d => {
        setData(d);
        setLoading(false);
      })
      .catch(e => {
        setErr(`Error ${e}`);
        setLoading(false);
      });
  
    }, [branch, brWindow, lang, toQueryString]);

  // formatCompact / formatPct imported from numberFormat.js
  const clr  = v => v == null ? 'var(--text-muted)' : v >= 0 ? 'var(--green)' : 'var(--red)'

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(0,0,0,.65)', backdropFilter: 'blur(6px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
    }}>
      <div style={{
        background: 'var(--bg-surface)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius-card)', width: '100%', maxWidth: 680,
        maxHeight: '90vh', overflowY: 'auto',
        boxShadow: '0 24px 64px rgba(0,0,0,.6)',
        animation: 'slideUp .2s ease',
      }}>
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: '18px 24px', borderBottom: '1px solid var(--border)',
          position: 'sticky', top: 0, background: 'var(--bg-surface)', zIndex: 1,
        }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: 'var(--accent-dim)', border: '1px solid var(--border-accent)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--accent)', fontSize: 16, flexShrink: 0,
          }}>📊</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: 15, color: 'var(--text-primary)' }}>
              {branch.name}
              {branch.code && <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--accent)',
                background: 'var(--accent-dim)', padding: '1px 6px', borderRadius: 4 }}>
                {branch.code}
              </span>}
            </div>
            {branch.city && <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
              {branch.city}{branch.country ? `, ${branch.country}` : ''}
            </div>}
          </div>
          <button onClick={onClose} style={{
            background: 'none', border: 'none', color: 'var(--text-muted)',
            cursor: 'pointer', fontSize: 18, padding: '2px 8px', borderRadius: 4,
          }}>✕</button>
        </div>

        <div style={{
          padding: '10px 24px', borderBottom: '1px solid var(--border)',
          background: 'var(--bg-elevated)', fontSize: 11, fontWeight: 700,
          color: 'var(--text-secondary)', letterSpacing: '.04em',
        }}>
          {tr('data_source_branch_financials')}
        </div>

        <div style={{ padding: '20px 24px' }}>
          {loading && (
            <div style={{ textAlign: 'center', padding: 40 }}>
              <div style={{ width: 28, height: 28, margin: '0 auto', border: '2px solid var(--border)',
                borderTop: '2px solid var(--accent)', borderRadius: '50%',
                animation: 'spin .7s linear infinite' }} />
              <div style={{ marginTop: 12, fontSize: 12, color: 'var(--text-muted)' }}>{tr('loading_analysis')}</div>
            </div>
          )}

          {err && <div style={{ color: 'var(--red)', fontSize: 13, padding: 16,
            background: 'var(--red-dim)', borderRadius: 8 }}>{err}</div>}

          {data && !data.has_data && (
            <div style={{ textAlign: 'center', padding: '32px 16px' }}>
              <div style={{ fontSize: 32, marginBottom: 12, opacity: .3 }}>📭</div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', fontWeight: 600 }}>
                {tr('branch_no_data_title')}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
                {tr('branch_no_data_hint')}
              </div>
            </div>
          )}

          {data && data.has_data && (() => {
            const l = data.latest || {}
            const trends = data.trends || {}
            const ins = data.insights || {}
            const periods = trends.periods || []
            const revSeries = trends.revenue_series || []
            const npSeries  = trends.net_profit_series || []
            const momRev    = trends.revenue_mom_pct || []

            return (
              <>
                {/* Period info */}
                <div style={{ display: 'flex', gap: 8, marginBottom: 18, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)',
                    background: 'var(--bg-elevated)', padding: '3px 10px', borderRadius: 20,
                    border: '1px solid var(--border)' }}>
                    {tr('periods_analysed', { n: data.period_count })}
                  </span>
                  <span style={{ fontSize: 11, color: 'var(--accent)',
                    background: 'var(--accent-dim)', padding: '3px 10px', borderRadius: 20,
                    border: '1px solid var(--border-accent)' }}>
                    {tr('latest_period', { p: data.last_period })}
                  </span>
                  <span style={{ fontSize: 11, padding: '3px 10px', borderRadius: 20,
                    border: '1px solid var(--border)',
                    color: ins.trend === 'growing' ? 'var(--green)' : ins.trend === 'declining' ? 'var(--red)' : 'var(--text-muted)',
                    background: ins.trend === 'growing' ? 'var(--green-dim)' : ins.trend === 'declining' ? 'var(--red-dim)' : 'var(--bg-elevated)',
                  }}>
                    {ins.trend === 'growing' ? tr('trend_growing') : ins.trend === 'declining' ? tr('trend_declining') : tr('trend_stable')}
                  </span>
                </div>

                {/* KPI cards */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 20 }}>
                  {[
                    { label: tr('kpi_revenue'),           value: formatCompact(l.revenue),            full: formatFull(l.revenue),   color: 'var(--accent)' },
                    { label: tr('kpi_net_profit'),        value: formatCompact(l.net_profit),         full: formatFull(l.net_profit),color: clr(l.net_profit) },
                    { label: tr('kpi_gross_margin'),      value: formatPct(l.gross_margin_pct),       full: null, color: clr(l.gross_margin_pct) },
                    { label: tr('kpi_net_margin'),        value: formatPct(l.net_margin_pct),         full: null, color: clr(l.net_margin_pct) },
                    { label: tr('kpi_expense_ratio'),     value: formatPct(l.expense_ratio),          full: null, color: l.expense_ratio > 70 ? 'var(--red)' : 'var(--text-primary)' },
                    { label: tr('kpi_operating_margin'),  value: formatPct(l.operating_margin_pct),  full: null, color: clr(l.operating_margin_pct) },
                  ].map((kpi, i) => (
                    <div key={i} style={{
                      background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                      borderRadius: 10, padding: '12px 14px',
                    }}>
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4,
                        textTransform: 'uppercase', letterSpacing: '.06em' }}>{kpi.label}</div>
                      <div style={{ fontSize: 18, fontWeight: 800, color: kpi.color, fontFamily: 'monospace' }}>
                        {kpi.value}
                      </div>
                      {kpi.full&&<div style={{fontSize:9,color:'var(--text-muted)',fontFamily:'monospace',marginTop:2,letterSpacing:'.02em'}}>{kpi.full}</div>}
                    </div>
                  ))}
                </div>

                {/* Trend table */}
                {periods.length > 0 && (
                  <div style={{ marginBottom: 20 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)',
                      textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 10 }}>
                      {tr('monthly_trend')}
                    </div>
                    <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                      borderRadius: 10, overflow: 'hidden' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                        <thead>
                          <tr>
                            {[tr('col_period'), tr('kpi_revenue'), tr('kpi_net_profit'), tr('col_mom_rev')].map((h,i) => (
                              <th key={i} style={{ padding: '8px 12px', textAlign: i === 0 ? 'left' : 'right',
                                fontSize: 10, fontWeight: 700, color: 'var(--text-muted)',
                                borderBottom: '1px solid var(--border)',
                                textTransform: 'uppercase', letterSpacing: '.06em' }}>{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {periods.map((p, i) => (
                            <tr key={p} style={{ borderBottom: i < periods.length-1 ? '1px solid rgba(255,255,255,.04)' : 'none',
                              background: i === periods.length-1 ? 'rgba(0,212,170,.05)' : 'transparent' }}>
                              <td style={{ padding: '8px 12px', color: 'var(--text-secondary)', fontWeight: 600 }}>{p}</td>
                              <td style={{ padding: '8px 12px', textAlign: 'right', color: 'var(--accent)', fontFamily: 'monospace' }}>
                                {formatCompact(revSeries[i])}
                              </td>
                              <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace',
                                color: (npSeries[i] ?? 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>
                                {formatCompact(npSeries[i])}
                              </td>
                              <td style={{ padding: '8px 12px', textAlign: 'right', fontFamily: 'monospace',
                                color: momRev[i] == null ? 'var(--text-muted)' : momRev[i] > 0 ? 'var(--green)' : 'var(--red)' }}>
                                {momRev[i] == null ? '—' : `${momRev[i] > 0 ? '+' : ''}${momRev[i].toFixed(1)}%`}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Insights */}
                {(ins.avg_revenue != null || ins.avg_net_profit != null) && (
                  <div style={{ background: 'rgba(0,212,170,.06)', border: '1px solid var(--border-accent)',
                    borderRadius: 10, padding: '12px 16px' }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent)',
                      textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 8 }}>{tr('insights_title')}</div>
                    <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', fontSize: 12, color: 'var(--text-secondary)' }}>
                      {ins.avg_revenue != null && (
                        <span>{tr('avg_revenue')} <strong style={{ color: 'var(--accent)' }}>{formatCompact(ins.avg_revenue)}</strong></span>
                      )}
                      {ins.avg_net_profit != null && (
                        <span>{tr('avg_net_profit')} <strong style={{ color: clr(ins.avg_net_profit) }}>{formatCompact(ins.avg_net_profit)}</strong></span>
                      )}
                      {ins.periods_growing > 0 && (
                        <span>{tr('growth_months')} <strong style={{ color: 'var(--green)' }}>{ins.periods_growing}</strong></span>
                      )}
                      {ins.periods_declining > 0 && (
                        <span>{tr('decline_months')} <strong style={{ color: 'var(--red)' }}>{ins.periods_declining}</strong></span>
                      )}
                    </div>
                  </div>
                )}
              </>
            )
          })()}
        </div>
      </div>
    </div>
  )
}

function ActionBtn({ icon, label, onClick, color }) {
  const [h, setH] = useState(false)
  return (
    <button
      title={label}
      onClick={onClick}
      onMouseEnter={() => setH(true)}
      onMouseLeave={() => setH(false)}
      style={{
        background: h ? `${color}1a` : 'transparent',
        border: `1px solid ${h ? color : 'var(--border)'}`,
        color: h ? color : 'var(--text-muted)',
        borderRadius: 6, padding: '4px 8px', fontSize: 13,
        cursor: 'pointer', transition: 'all .15s',
      }}
    >
      {icon}
    </button>
  )
}

function StatCard({ label, value, color }) {
  return (
    <div style={{
      background: 'var(--bg-surface)', border: '1px solid var(--border)',
      borderRadius: 10, padding: '12px 18px', display: 'flex',
      flexDirection: 'column', gap: 4, minWidth: 100,
    }}>
      <span style={{ fontSize: 22, fontWeight: 800, color }}>{value}</span>
      <span style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.06em' }}>{label}</span>
    </div>
  )
}

function IcoBranch({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <line x1="6" y1="3" x2="6" y2="15"/>
      <circle cx="18" cy="6" r="3"/>
      <circle cx="6" cy="18" r="3"/>
      <path d="M18 9a9 9 0 0 1-9 9"/>
    </svg>
  )
}

// ── Styles ────────────────────────────────────────────────────────────────────
const s = {
  page: {
    padding: '24px 28px', maxWidth: 1200, margin: '0 auto',
    minHeight: '100%',
  },
  pageHeader: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    marginBottom: 24, flexWrap: 'wrap', gap: 12,
  },
  pageIconWrap: {
    width: 42, height: 42, borderRadius: 12,
    background: 'linear-gradient(135deg,rgba(0,212,170,.15),rgba(59,158,255,.12))',
    border: '1px solid var(--border-accent)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: 'var(--accent)', flexShrink: 0,
  },
  pageTitle: {
    fontSize: 20, fontWeight: 800, color: 'var(--text-primary)',
    letterSpacing: '-0.02em', margin: 0,
  },
  pageSubtitle: {
    fontSize: 12, color: 'var(--text-muted)', margin: '2px 0 0',
  },
  statsRow: {
    display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap',
  },
  tableWrap: {
    background: 'var(--bg-surface)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-card)',
    overflow: 'hidden',
    overflowX: 'auto',
  },
  table: {
    width: '100%', borderCollapse: 'collapse', fontSize: 13,
  },
  th: {
    padding: '11px 14px', textAlign: 'left',
    fontSize: 10, fontWeight: 700, letterSpacing: '.08em',
    textTransform: 'uppercase', color: 'var(--text-muted)',
    borderBottom: '1px solid var(--border)',
    background: 'rgba(255,255,255,.02)',
    whiteSpace: 'nowrap',
  },
  td: {
    padding: '13px 14px', borderBottom: '1px solid rgba(255,255,255,.04)',
    color: 'var(--text-primary)', verticalAlign: 'middle',
    whiteSpace: 'nowrap',
  },
  overlay: {
    position: 'fixed', inset: 0, zIndex: 1000,
    background: 'rgba(0,0,0,.65)', backdropFilter: 'blur(6px)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    padding: 16,
  },
  modal: {
    background: 'var(--bg-surface)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-card)',
    padding: '20px 24px',
    width: '100%',
    boxShadow: '0 24px 64px rgba(0,0,0,.6)',
    animation: 'slideUp .2s ease',
  },
  modalHeader: {
    display: 'flex', alignItems: 'center', gap: 10,
    borderBottom: '1px solid var(--border)', paddingBottom: 14, marginBottom: 4,
  },
  modalIconWrap: {
    width: 30, height: 30, borderRadius: 8,
    background: 'var(--accent-dim)', border: '1px solid var(--border-accent)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: 'var(--accent)', flexShrink: 0,
  },
  closeBtn: {
    marginLeft: 'auto', background: 'none', border: 'none',
    color: 'var(--text-muted)', cursor: 'pointer', fontSize: 16,
    padding: '2px 6px', borderRadius: 4,
    transition: 'color .15s',
  },
  label: {
    display: 'flex', flexDirection: 'column', gap: 5,
    fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)',
    letterSpacing: '.04em',
  },
  input: {
    width: '100%', padding: '9px 12px',
    background: 'var(--bg-elevated)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    color: 'var(--text-primary)',
    fontSize: 13, outline: 'none',
    transition: 'border-color .15s',
    boxSizing: 'border-box',
  },
  btnPrimary: {
    display: 'flex', alignItems: 'center', gap: 7,
    padding: '9px 18px', borderRadius: 'var(--radius-sm)',
    background: 'var(--accent)', color: '#000',
    fontWeight: 700, fontSize: 13, cursor: 'pointer',
    border: 'none', transition: 'opacity .15s',
    whiteSpace: 'nowrap',
  },
  btnSecondary: {
    padding: '9px 16px', borderRadius: 'var(--radius-sm)',
    background: 'transparent',
    border: '1px solid var(--border)',
    color: 'var(--text-secondary)',
    fontWeight: 600, fontSize: 13, cursor: 'pointer',
    transition: 'border-color .15s, color .15s',
    whiteSpace: 'nowrap',
  },
  btn: {
    padding: '9px 18px', borderRadius: 'var(--radius-sm)',
    fontWeight: 700, fontSize: 13, cursor: 'pointer', border: 'none',
  },
  center: {
    display: 'flex', justifyContent: 'center', alignItems: 'center',
    padding: 60,
  },
  spinner: {
    width: 32, height: 32, border: '2px solid var(--border)',
    borderTop: '2px solid var(--accent)', borderRadius: '50%',
    animation: 'spin .7s linear infinite',
  },
  errorBox: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    gap: 12, padding: '14px 18px',
    background: 'var(--red-dim)', border: '1px solid var(--red)',
    borderRadius: 10, color: 'var(--red)', fontSize: 13,
    marginBottom: 20,
  },
  emptyState: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', padding: '80px 24px',
    background: 'var(--bg-surface)', border: '1px solid var(--border)',
    borderRadius: 'var(--radius-card)', textAlign: 'center',
  },
  emptyIcon: {
    width: 64, height: 64, borderRadius: 18,
    background: 'var(--accent-dim)', border: '1px solid var(--border-accent)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: 'var(--accent)',
  },
}
