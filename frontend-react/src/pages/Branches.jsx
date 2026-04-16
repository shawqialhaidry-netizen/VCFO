/**
 * Branches.jsx — Branch Management Page
 * Full CRUD: list, create, edit, soft-delete
 * Company-isolated, auth-protected, i18n-ready (EN/AR/TR)
 *
 * Phase 1.1: branch drill modal uses GET /branches/{id}/analysis (branch-scoped pipeline),
 * not company GET /executive — intentional; listed as non-canonical company surface for Phase 2.
 */
import { useState, useEffect, useCallback, useMemo, useId } from 'react'
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  ComposedChart,
  Line,
} from 'recharts'
import { useCompany } from '../context/CompanyContext.jsx'
import DrillBackBar from '../components/DrillBackBar.jsx'
import { useLang }    from '../context/LangContext.jsx'
import {
  formatCompactForLang,
  formatFullForLang,
  formatPctForLang,
} from '../utils/numberFormat.js'

const API = '/api/v1'

/** FastAPI/Pydantic detail can be string, object, or validation array */
function formatApiError(d, status, tr) {
  const det = d?.detail
  if (det == null) return tr ? tr('err_http_status', { status }) : `Error ${status}`
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
  if (typeof det === 'object') try { return JSON.stringify(det) } catch { return tr ? tr('err_http_status', { status }) : `Error ${status}` }
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
    manager_name: branch?.manager_name || '',
    city:      branch?.city     || '',
    country:   branch?.country  || '',
    currency:  branch?.currency || 'USD',
    is_active: branch?.is_active ?? true,
  })
  const [saving, setSaving] = useState(false)
  const [err,    setErr]    = useState(null)

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  async function handleSubmit() {
    if (!form.name.trim()) { setErr(`${tr('branch_name')} ${tr('field_required')}`); return }
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
            manager_name: form.manager_name?.trim() || null,
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
            manager_name: (form.manager_name && String(form.manager_name).trim()) || null,
            city:       (form.city && String(form.city).trim()) || null,
            country:    (form.country && String(form.country).trim()) || null,
            currency:   form.currency || 'USD',
          }
      const r = await fetch(url, { method, headers: getAuthHeaders(), body: JSON.stringify(body) })
      if (!r.ok) {
        const d = await r.json().catch(() => ({}))
        const msg = formatApiError(d, r.status, tr)
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

          <label style={{ ...s.label, gridColumn: '1 / -1' }}>
            <span>{tr('branch_manager_name')}</span>
            <input
              style={s.input}
              value={form.manager_name}
              onChange={e => set('manager_name', e.target.value)}
              placeholder={tr('branch_manager_name_placeholder')}
              dir={isRtl ? 'rtl' : 'ltr'}
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
            {saving ? tr('loading') : tr('branch_save')}
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
  const { selectedId: companyId, selectedCompany, canWrite } = useCompany()
  const { tr, lang }                               = useLang()

  const [branches,    setBranches]    = useState([])
  const [branchFinancials, setBranchFinancials] = useState([])
  const [portfolioIntel, setPortfolioIntel] = useState(null)
  const [drillBranch, setDrillBranch] = useState(null)
  const [drillData, setDrillData] = useState(null)
  const [drillLoading, setDrillLoading] = useState(false)
  const [drillError, setDrillError] = useState(null)
  const [loading,     setLoading]     = useState(false)
  const [err,         setErr]         = useState(null)
  const [showForm,    setShowForm]    = useState(false)
  const [editBranch,  setEditBranch]  = useState(null)   // null = create mode
  const [deletePending, setDeletePending] = useState(null)
  const [toast,       setToast]       = useState(null)
  const [showInactive, setShowInactive] = useState(false)
  const [activeTab, setActiveTab] = useState('list')

  // ── Fetch branches ────────────────────────────────────────────────────────
  const load = useCallback(async () => {
    if (!companyId) return
    setLoading(true); setErr(null)
    try {
      const [branchesResp, financialsResp, portfolioResp] = await Promise.all([
        fetch(`${API}/branches?company_id=${companyId}`, { headers: getAuthHeaders() }),
        fetch(`${API}/companies/${companyId}/branch-financials`, { headers: getAuthHeaders() }),
        fetch(`${API}/companies/${companyId}/portfolio-intelligence?lang=${lang}`, { headers: getAuthHeaders() }),
      ])
      if (!branchesResp.ok) { setErr(tr('err_http_status', { status: branchesResp.status })); return }
      const data = await branchesResp.json()
      setBranches(data)
      if (financialsResp.ok) {
        const fin = await financialsResp.json()
        setBranchFinancials(Array.isArray(fin?.rows) ? fin.rows : [])
      } else {
        setBranchFinancials([])
      }
      if (portfolioResp.ok) {
        const portfolio = await portfolioResp.json()
        setPortfolioIntel(portfolio)
      } else {
        setPortfolioIntel(null)
      }
    } catch (e) { setErr(e.message) }
    finally { setLoading(false) }
  }, [companyId, lang])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!drillBranch?.id) return
    let cancelled = false

    async function loadDrill() {
      setDrillLoading(true)
      setDrillError(null)
      setDrillData(null)
      try {
        const r = await fetch(`${API}/branches/${drillBranch.id}/drill-down?lang=${lang}`, { headers: getAuthHeaders() })
        if (!r.ok) throw new Error(tr('err_http_status', { status: r.status }))
        const json = await r.json()
        if (!cancelled) setDrillData(json)
      } catch (e) {
        if (!cancelled) setDrillError(e.message)
      } finally {
        if (!cancelled) setDrillLoading(false)
      }
    }

    loadDrill()
    return () => { cancelled = true }
  }, [drillBranch, lang])

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
      if (!r.ok && r.status !== 204) { showToast(tr('err_http_status', { status: r.status }), false); return }
      setBranches(prev => prev.map(b => b.id === deletePending.id ? { ...b, is_active: false } : b))
      showToast(tr('branch_deleted_ok'), true)
    } catch (e) { showToast(e.message, false) }
    finally { setDeletePending(null) }
  }

  function showToast(msg, ok) {
    setToast({ msg, ok })
  }

  function openEdit(b) { setEditBranch(b); setShowForm(true) }
  function openCreate() { setEditBranch(null); setShowForm(true) }
  function closeForm() { setShowForm(false); setEditBranch(null) }

  const filtered = branches.filter(b => showInactive ? true : b.is_active)
  const financialMap = useMemo(
    () => Object.fromEntries((branchFinancials || []).map((row) => [String(row.branch_id), row])),
    [branchFinancials],
  )
  const overview = useMemo(() => {
    const withData = (branchFinancials || []).filter((row) => row?.has_data)
    const totalRevenue = withData.reduce((sum, row) => sum + (Number(row?.revenue) || 0), 0)
    const totalNetProfit = withData.reduce((sum, row) => sum + (Number(row?.net_profit) || 0), 0)
    const bestMargin = withData.reduce((best, row) => {
      if ((row?.net_margin ?? null) == null) return best
      if (!best || row.net_margin > best.net_margin) return row
      return best
    }, null)
    const weakest = withData.reduce((worst, row) => {
      const value = Number(row?.net_profit)
      if (Number.isNaN(value)) return worst
      if (!worst || value < Number(worst?.net_profit)) return row
      return worst
    }, null)
    return { withDataCount: withData.length, totalRevenue, totalNetProfit, bestMargin, weakest }
  }, [branchFinancials])

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div style={s.page}>
      <DrillBackBar detailLabel={tr('nav_drill_branches')} />
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
          {activeTab === 'list' && (
            <button
              onClick={() => setShowInactive(v => !v)}
              style={{ ...s.btnSecondary, fontSize: 12, opacity: showInactive ? 1 : 0.6 }}
            >
              {showInactive ? `👁 ${tr('show_all')}` : `👁 ${tr('active_only')}`}
            </button>
          )}
          {activeTab === 'list' && canWrite !== false && companyId && (
            <button onClick={openCreate} style={s.btnPrimary}>
              <span style={{ fontSize: 16, lineHeight: 1 }}>+</span> {tr('branch_add')}
            </button>
          )}
        </div>
      </div>

      <div style={s.tabSwitch}>
        {[
          { key: 'list', label: tr('branch_list_tab') },
          { key: 'intel', label: tr('intelligence_tab') },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={activeTab === tab.key ? s.tabBtnActive : s.tabBtn}
          >
            {tab.label}
          </button>
        ))}
      </div>


      {/* ── Stats row ── */}
      {activeTab === 'list' && branches.length > 0 && (
        <div style={s.statsRow}>
          <StatCard label={tr('branch_active')}   value={branches.filter(b => b.is_active).length}  color="var(--green)" />
          <StatCard label={tr('branch_inactive')} value={branches.filter(b => !b.is_active).length} color="var(--text-muted)" />
          <StatCard label={tr('branch_total')}     value={branches.length}                            color="var(--accent)" />
        </div>
      )}

      {activeTab === 'list' && overview.withDataCount > 0 && (
        <div style={s.overviewGrid}>
          <InsightCard
            title={tr('data_source_branch_financials')}
            value={String(overview.withDataCount)}
            sub={tr('branch_total')}
            tone="var(--accent)"
          />
          <InsightCard
            title={tr('kpi_revenue')}
            value={formatCompactForLang(overview.totalRevenue, lang)}
            sub={formatFullForLang(overview.totalRevenue, lang)}
            tone="var(--accent)"
          />
          <InsightCard
            title={tr('kpi_net_profit')}
            value={formatCompactForLang(overview.totalNetProfit, lang)}
            sub={formatFullForLang(overview.totalNetProfit, lang)}
            tone={overview.totalNetProfit >= 0 ? 'var(--green)' : 'var(--red)'}
          />
          <InsightCard
            title={tr('best_margin')}
            value={overview.bestMargin?.branch_name || '—'}
            sub={overview.bestMargin?.net_margin != null ? formatPctForLang(overview.bestMargin.net_margin, 1, lang) : '—'}
            tone="var(--green)"
          />
          <InsightCard
            title={tr('weakest')}
            value={overview.weakest?.branch_name || '—'}
            sub={overview.weakest?.net_profit != null ? formatCompactForLang(overview.weakest.net_profit, lang) : '—'}
            tone="var(--red)"
          />
        </div>
      )}

      {activeTab === 'intel' && portfolioIntel?.portfolio_summary && (
        <BranchPortfolioPanelEnhanced
          data={portfolioIntel}
          tr={tr}
          lang={lang}
          onOpenBranch={(branchId) => {
            const match = branches.find((b) => String(b.id) === String(branchId))
            if (match) setDrillBranch(match)
          }}
        />
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
      {activeTab === 'list' && !loading && !err && filtered.length === 0 && (
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

      {/* ── Branch table ── */}
      {activeTab === 'list' && !loading && !err && filtered.length > 0 && (
        <div style={s.tableWrap}>
          <table style={s.table}>
            <thead>
              <tr>
                {[
                  tr('branch_code'),
                  tr('branch_name'),
                  tr('branch_name_ar'),
                  tr('branch_manager_name'),
                  tr('branch_col_period'),
                  tr('branch_col_revenue'),
                  tr('branch_col_net_profit'),
                  tr('prof_net_margin'),
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
                  financial={financialMap[String(b.id)] || null}
                  onOpen={() => setDrillBranch(b)}
                  onEdit={() => openEdit(b)}
                  onDelete={() => setDeletePending(b)}
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

      {drillBranch && (
        <BranchDrillModal
          branch={drillBranch}
          data={drillData}
          loading={drillLoading}
          err={drillError}
          onClose={() => {
            setDrillBranch(null)
            setDrillData(null)
            setDrillError(null)
          }}
          tr={tr}
          lang={lang}
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
function BranchRow({ branch: b, financial, onOpen, onEdit, onDelete, canWrite, tr, lang }) {
  const [hover, setHover] = useState(false)
  const dim = !b.is_active

  return (
    <tr
      onClick={onOpen}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        background: hover ? 'var(--bg-hover)' : 'transparent',
        opacity: dim ? 0.5 : 1,
        transition: 'background .15s, opacity .15s',
        cursor: 'pointer',
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
      <td style={{ ...s.td, color: b.manager_name ? 'var(--text-primary)' : 'var(--text-muted)' }}>
        {b.manager_name || '—'}
      </td>
      <td style={{ ...s.td, color: 'var(--text-secondary)', fontSize: 11 }}>
        {financial?.latest_period || '—'}
      </td>
      <td style={{ ...s.td, fontFamily: 'monospace', color: 'var(--text-primary)' }}>
        {financial?.has_data ? formatCompactForLang(financial?.revenue, lang) : '—'}
      </td>
      <td style={{ ...s.td, fontFamily: 'monospace', color: (financial?.net_profit ?? 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>
        {financial?.has_data ? formatCompactForLang(financial?.net_profit, lang) : '—'}
      </td>
      <td style={{ ...s.td, fontFamily: 'monospace', color: 'var(--text-secondary)' }}>
        {financial?.has_data && financial?.net_margin != null ? formatPctForLang(financial.net_margin, 1, lang) : '—'}
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
        <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }} onClick={(e) => e.stopPropagation()}>
          <ActionBtn icon=">" label={tr('cmd_drill_health_hint')} onClick={onOpen} color="var(--accent)" />
          {canWrite !== false && (
            <ActionBtn icon="E" label={tr('branch_edit')} onClick={onEdit} color="var(--blue)" />
          )}
          {canWrite !== false && b.is_active && (
            <ActionBtn icon="D" label={tr('branch_delete')} onClick={onDelete} color="var(--red)" />
          )}
        </div>
      </td>
    </tr>
  )
}



function InsightCard({ title, value, sub, tone }) {
  return (
    <div style={s.insightCard}>
      <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.08em' }}>
        {title}
      </div>
      <div style={{ fontSize: 20, fontWeight: 800, color: tone, marginTop: 6 }}>
        {value}
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
        {sub}
      </div>
    </div>
  )
}

function BranchPortfolioPanel({ data, tr, lang, onOpenBranch }) {
  const summary = data?.portfolio_summary || {}
  const contributions = Array.isArray(data?.contributions) ? data.contributions : []
  const insights = Array.isArray(data?.insights) ? data.insights : []
  const decisions = Array.isArray(data?.portfolio_decisions) ? data.portfolio_decisions : []
  const topRows = contributions.slice(0, 12)

  return (
    <div style={s.portfolioWrap}>
      <div style={s.portfolioHeader}>
        <div>
          <div style={s.portfolioEyebrow}>{tr('data_source_branch_financials')}</div>
          <h2 style={s.portfolioTitle}>{tr('intelligence_tab')}</h2>
          <p style={s.portfolioSub}>
            {summary?.branch_count || 0} {tr('branch_total')} • {data?.latest_period || '-'}
          </p>
        </div>
        <div style={s.portfolioPill}>
          <strong>{formatPctForLang(summary?.portfolio_margin_pct, 1, lang)}</strong>
          <span>{tr('prof_net_margin')}</span>
        </div>
      </div>

      <div style={s.overviewGrid}>
        <InsightCard
          title={tr('kpi_revenue')}
          value={formatCompactForLang(summary?.total_revenue, lang)}
          sub={formatFullForLang(summary?.total_revenue, lang)}
          tone="var(--accent)"
        />
        <InsightCard
          title={tr('kpi_net_profit')}
          value={formatCompactForLang(summary?.total_profit, lang)}
          sub={formatFullForLang(summary?.total_profit, lang)}
          tone={(summary?.total_profit ?? 0) >= 0 ? 'var(--green)' : 'var(--red)'}
        />
        <InsightCard
          title={tr('strongest')}
          value={summary?.top_contributor?.branch_name || '-'}
          sub={summary?.top_contributor?.profit_share_pct != null ? `${summary.top_contributor.profit_share_pct}%` : '-'}
          tone="var(--green)"
        />
        <InsightCard
          title={tr('weakest')}
          value={summary?.biggest_drag?.branch_name || '-'}
          sub={summary?.biggest_drag?.net_profit != null ? formatCompactForLang(summary.biggest_drag.net_profit, lang) : '-'}
          tone="var(--red)"
        />
        <InsightCard
          title={tr('highest_cost')}
          value={summary?.highest_cost_pressure?.branch_name || '-'}
          sub={summary?.highest_cost_pressure?.expense_ratio != null ? formatPctForLang(summary.highest_cost_pressure.expense_ratio, 1, lang) : '-'}
          tone="var(--amber)"
        />
      </div>

      <div style={s.twoCol}>
        <div style={s.drillSection}>
          <SectionTitle title={tr('tab_root_causes')} />
          <SimpleList items={insights.slice(0, 5).map(normalizeDecisionItem)} />
        </div>
        <div style={s.drillSection}>
          <SectionTitle title={tr('tab_cfo_decisions')} />
          <SimpleList items={decisions.slice(0, 5).map(normalizeDecisionItem)} />
        </div>
      </div>

      <div style={s.portfolioTableWrap}>
        <div style={s.portfolioTableHeader}>
          <SectionTitle title={tr('rankings')} />
        </div>
        <table style={s.table}>
          <thead>
            <tr>
              {[
                '#',
                tr('branch_name'),
                tr('prof_net_margin'),
                tr('branch_col_expense_ratio'),
                tr('kpi_revenue'),
                tr('kpi_net_profit'),
                tr('strongest'),
                tr('branch_status'),
              ].map((h, i) => (
                <th key={i} style={s.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {topRows.map((row) => (
              <tr key={row.branch_id} style={{ cursor: 'pointer' }} onClick={() => onOpenBranch(row.branch_id)}>
                <td style={s.td}>{row.overall_portfolio_rank ?? '-'}</td>
                <td style={{ ...s.td, fontWeight: 700 }}>
                  {lang === 'ar' && row.name_ar ? row.name_ar : row.branch_name}
                </td>
                <td style={{ ...s.td, fontFamily: 'monospace', color: 'var(--green)' }}>
                  {row.net_margin_pct != null ? formatPctForLang(row.net_margin_pct, 1, lang) : '-'}
                </td>
                <td style={{ ...s.td, fontFamily: 'monospace', color: 'var(--amber)' }}>
                  {row.expense_ratio != null ? formatPctForLang(row.expense_ratio, 1, lang) : '-'}
                </td>
                <td style={{ ...s.td, fontFamily: 'monospace' }}>
                  {row.revenue_share_pct != null ? `${row.revenue_share_pct}%` : '-'}
                </td>
                <td style={{ ...s.td, fontFamily: 'monospace' }}>
                  {row.profit_share_pct != null ? `${row.profit_share_pct}%` : '-'}
                </td>
                <td style={s.td}>{row.role_label || row.role || '-'}</td>
                <td style={s.td}>
                  <button style={s.rowOpenBtn} onClick={(e) => { e.stopPropagation(); onOpenBranch(row.branch_id) }}>
                    {tr('cmd_drill_health_hint')}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {contributions.length > topRows.length && (
          <div style={s.portfolioFootnote}>
            {topRows.length}/{contributions.length} {tr('branch_total')}
          </div>
        )}
      </div>
    </div>
  )
}

function PortfolioChartTooltip({ active, payload, label, formatter }) {
  if (!active || !payload?.length) return null
  return (
    <div style={s.chartTooltip}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>{label}</div>
      {payload.map((entry) => (
        <div key={entry.dataKey} style={s.chartTooltipRow}>
          <span style={{ color: entry.color || 'var(--text-secondary)' }}>{entry.name}</span>
          <strong style={{ color: 'var(--text-primary)' }}>
            {formatter ? formatter(entry.value, entry.dataKey) : entry.value}
          </strong>
        </div>
      ))}
    </div>
  )
}

function BranchPortfolioPanelEnhanced({ data, tr, lang, onOpenBranch }) {
  const chartId = useId().replace(/:/g, '')
  const summary = data?.portfolio_summary || {}
  const contributions = Array.isArray(data?.contributions) ? data.contributions : []
  const insights = Array.isArray(data?.insights) ? data.insights : []
  const decisions = Array.isArray(data?.portfolio_decisions) ? data.portfolio_decisions : []
  const [search, setSearch] = useState('')
  const [scope, setScope] = useState('all')
  const [sortBy, setSortBy] = useState('rank')

  const totalRevenue = Number(summary?.total_revenue) || 0
  const totalProfit = Number(summary?.total_profit) || 0

  const filteredRows = useMemo(() => {
    const q = search.trim().toLowerCase()
    const rows = contributions.filter((row) => {
      const searchable = [
        row?.branch_name,
        row?.name_ar,
        row?.city,
        row?.role_label,
        row?.role,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()

      if (q && !searchable.includes(q)) return false

      const profitShare = Number(row?.profit_share_pct) || 0
      const netMargin = Number(row?.net_margin_pct)
      const expenseRatio = Number(row?.expense_ratio)

      if (scope === 'profit' && !(profitShare > 0 && netMargin >= 0)) return false
      if (scope === 'loss' && !(profitShare < 0 || netMargin < 0)) return false
      if (scope === 'high_cost' && !(expenseRatio >= 75)) return false
      return true
    })

    const sorted = [...rows]
    sorted.sort((a, b) => {
      if (sortBy === 'margin') return (Number(b?.net_margin_pct) || -999) - (Number(a?.net_margin_pct) || -999)
      if (sortBy === 'cost') return (Number(b?.expense_ratio) || -999) - (Number(a?.expense_ratio) || -999)
      if (sortBy === 'revenue') return (Number(b?.revenue_share_pct) || -999) - (Number(a?.revenue_share_pct) || -999)
      if (sortBy === 'profit') return (Number(b?.profit_share_pct) || -999) - (Number(a?.profit_share_pct) || -999)
      return (Number(a?.overall_portfolio_rank) || 999) - (Number(b?.overall_portfolio_rank) || 999)
    })
    return sorted
  }, [contributions, scope, search, sortBy])

  const filteredSummary = useMemo(() => {
    const branchCount = filteredRows.length
    const revenueFiltered = filteredRows.reduce(
      (sum, row) => sum + (totalRevenue * ((Number(row?.revenue_share_pct) || 0) / 100)),
      0,
    )
    const profitFiltered = filteredRows.reduce(
      (sum, row) => sum + (totalProfit * ((Number(row?.profit_share_pct) || 0) / 100)),
      0,
    )
    const withMargin = filteredRows.filter((row) => row?.net_margin_pct != null)
    const withExpense = filteredRows.filter((row) => row?.expense_ratio != null)
    const avgMargin = withMargin.length
      ? withMargin.reduce((sum, row) => sum + (Number(row?.net_margin_pct) || 0), 0) / withMargin.length
      : null
    const avgExpense = withExpense.length
      ? withExpense.reduce((sum, row) => sum + (Number(row?.expense_ratio) || 0), 0) / withExpense.length
      : null
    const strongest = filteredRows.reduce((best, row) => {
      if (!best) return row
      return (Number(row?.net_margin_pct) || -999) > (Number(best?.net_margin_pct) || -999) ? row : best
    }, null)
    const weakest = filteredRows.reduce((worst, row) => {
      if (!worst) return row
      return (Number(row?.net_margin_pct) || 999) < (Number(worst?.net_margin_pct) || 999) ? row : worst
    }, null)
    return { branchCount, revenueFiltered, profitFiltered, avgMargin, avgExpense, strongest, weakest }
  }, [filteredRows, totalProfit, totalRevenue])

  const topRows = filteredRows.slice(0, 12)
  const topCostRows = useMemo(
    () => [...filteredRows]
      .filter((row) => row?.expense_ratio != null)
      .sort((a, b) => (Number(b?.expense_ratio) || -999) - (Number(a?.expense_ratio) || -999))
      .slice(0, 5),
    [filteredRows],
  )
  const shareChartData = topRows.map((row) => ({
    id: row.branch_id,
    branch: lang === 'ar' && row.name_ar ? row.name_ar : row.branch_name,
    revenueShare: Number(row?.revenue_share_pct) || 0,
    profitShare: Number(row?.profit_share_pct) || 0,
  }))
  const ratioChartData = topRows.map((row) => ({
    id: row.branch_id,
    branch: lang === 'ar' && row.name_ar ? row.name_ar : row.branch_name,
    netMargin: Number(row?.net_margin_pct) || 0,
    expenseRatio: Number(row?.expense_ratio) || 0,
  }))
  const scopeOptions = [
    { key: 'all', label: tr('branch_intel_scope_all') },
    { key: 'profit', label: tr('branch_intel_scope_profit') },
    { key: 'loss', label: tr('branch_intel_scope_loss') },
    { key: 'high_cost', label: tr('branch_intel_scope_high_cost') },
  ]
  const sortOptions = [
    { key: 'rank', label: tr('branch_intel_sort_rank') },
    { key: 'margin', label: tr('branch_intel_sort_margin') },
    { key: 'cost', label: tr('branch_intel_sort_cost') },
    { key: 'revenue', label: tr('branch_intel_sort_revenue') },
    { key: 'profit', label: tr('branch_intel_sort_profit') },
  ]

  return (
    <div style={s.portfolioWrap}>
      <div style={s.portfolioHeader}>
        <div>
          <div style={s.portfolioEyebrow}>{tr('data_source_branch_financials')}</div>
          <h2 style={s.portfolioTitle}>{tr('intelligence_tab')}</h2>
          <p style={s.portfolioSub}>
            {filteredSummary.branchCount} / {summary?.branch_count || 0} {tr('branch_total')} | {data?.latest_period || '-'}
          </p>
        </div>
        <div style={s.portfolioPill}>
          <strong>{filteredSummary.avgMargin != null ? formatPctForLang(filteredSummary.avgMargin, 1, lang) : '-'}</strong>
          <span>{tr('prof_net_margin')}</span>
        </div>
      </div>

      <div style={s.portfolioFilters}>
        <label style={s.filterBlock}>
          <span>{tr('search_placeholder')}</span>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={tr('branch_intel_search_placeholder')}
            style={s.filterInput}
          />
        </label>
        <label style={s.filterBlock}>
          <span>{tr('branch_filter_label')}</span>
          <select value={scope} onChange={(e) => setScope(e.target.value)} style={s.filterInput}>
            {scopeOptions.map((option) => (
              <option key={option.key} value={option.key}>{option.label}</option>
            ))}
          </select>
        </label>
        <label style={s.filterBlock}>
          <span>{tr('branch_intel_sort_label')}</span>
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} style={s.filterInput}>
            {sortOptions.map((option) => (
              <option key={option.key} value={option.key}>{option.label}</option>
            ))}
          </select>
        </label>
      </div>

      <div style={s.overviewGrid}>
        <InsightCard
          title={tr('kpi_revenue')}
          value={formatCompactForLang(filteredSummary.revenueFiltered, lang)}
          sub={formatFullForLang(filteredSummary.revenueFiltered, lang)}
          tone="var(--accent)"
        />
        <InsightCard
          title={tr('kpi_net_profit')}
          value={formatCompactForLang(filteredSummary.profitFiltered, lang)}
          sub={formatFullForLang(filteredSummary.profitFiltered, lang)}
          tone={(filteredSummary.profitFiltered ?? 0) >= 0 ? 'var(--green)' : 'var(--red)'}
        />
        <InsightCard
          title={tr('branch_intel_filtered_count')}
          value={String(filteredSummary.branchCount)}
          sub={tr('branch_total')}
          tone="var(--blue)"
        />
        <InsightCard
          title={tr('branch_intel_avg_margin')}
          value={filteredSummary.avgMargin != null ? formatPctForLang(filteredSummary.avgMargin, 1, lang) : '-'}
          sub={tr('prof_net_margin')}
          tone="var(--green)"
        />
        <InsightCard
          title={tr('branch_intel_avg_cost')}
          value={filteredSummary.avgExpense != null ? formatPctForLang(filteredSummary.avgExpense, 1, lang) : '-'}
          sub={tr('expense_ratio_short')}
          tone="var(--amber)"
        />
        <InsightCard
          title={tr('best_margin')}
          value={filteredSummary.strongest ? (lang === 'ar' && filteredSummary.strongest.name_ar ? filteredSummary.strongest.name_ar : filteredSummary.strongest.branch_name) : '-'}
          sub={filteredSummary.strongest?.net_margin_pct != null ? formatPctForLang(filteredSummary.strongest.net_margin_pct, 1, lang) : '-'}
          tone="var(--green)"
        />
      </div>

      <div style={s.portfolioChartsGrid}>
        <div style={s.chartCard}>
          <SectionTitle title={tr('branch_intel_chart_share')} />
          <div style={s.chartWrap}>
            {shareChartData.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={shareChartData} layout="vertical" margin={{ top: 8, right: 12, left: 12, bottom: 8 }}>
                  <defs>
                    <linearGradient id={`${chartId}-rev`} x1="0" y1="0" x2="1" y2="0">
                      <stop offset="0%" stopColor="#00d4aa" stopOpacity="0.85" />
                      <stop offset="100%" stopColor="#3b9eff" stopOpacity="0.9" />
                    </linearGradient>
                    <linearGradient id={`${chartId}-np`} x1="0" y1="0" x2="1" y2="0">
                      <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.75" />
                      <stop offset="100%" stopColor="#ef4444" stopOpacity="0.85" />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="rgba(255,255,255,.06)" horizontal={false} />
                  <XAxis type="number" tick={{ fill: '#93a1b3', fontSize: 11 }} tickFormatter={(v) => `${v}%`} />
                  <YAxis type="category" dataKey="branch" width={110} tick={{ fill: '#d8dee9', fontSize: 11 }} />
                  <Tooltip content={(props) => <PortfolioChartTooltip {...props} formatter={(v) => `${Number(v).toFixed(1)}%`} />} />
                  <Bar dataKey="revenueShare" name={tr('kpi_revenue')} fill={`url(#${chartId}-rev)`} radius={[0, 6, 6, 0]} />
                  <Bar dataKey="profitShare" name={tr('kpi_net_profit')} fill={`url(#${chartId}-np)`} radius={[0, 6, 6, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div style={s.chartEmpty}>{tr('branch_intel_chart_empty')}</div>
            )}
          </div>
        </div>

        <div style={s.chartCard}>
          <SectionTitle title={tr('branch_intel_chart_margin')} />
          <div style={s.chartWrap}>
            {ratioChartData.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={ratioChartData} margin={{ top: 8, right: 12, left: 4, bottom: 8 }}>
                  <CartesianGrid stroke="rgba(255,255,255,.06)" />
                  <XAxis dataKey="branch" tick={{ fill: '#93a1b3', fontSize: 11 }} interval={0} angle={-14} textAnchor="end" height={56} />
                  <YAxis tick={{ fill: '#93a1b3', fontSize: 11 }} tickFormatter={(v) => `${v}%`} />
                  <Tooltip content={(props) => <PortfolioChartTooltip {...props} formatter={(v) => `${Number(v).toFixed(1)}%`} />} />
                  <Bar dataKey="expenseRatio" name={tr('expense_ratio_short')} fill="rgba(245, 158, 11, 0.6)" radius={[6, 6, 0, 0]}>
                    {ratioChartData.map((entry) => (
                      <Cell key={entry.id} fill={entry.expenseRatio >= 75 ? 'rgba(239, 68, 68, 0.72)' : 'rgba(245, 158, 11, 0.68)'} />
                    ))}
                  </Bar>
                  <Line type="monotone" dataKey="netMargin" name={tr('prof_net_margin')} stroke="#00d4aa" strokeWidth={2.5} dot={{ r: 3 }} activeDot={{ r: 5 }} />
                </ComposedChart>
              </ResponsiveContainer>
            ) : (
              <div style={s.chartEmpty}>{tr('branch_intel_chart_empty')}</div>
            )}
          </div>
        </div>
      </div>

      <div style={s.twoCol}>
        <div style={s.drillSection}>
          <SectionTitle title={tr('expense_analysis_title')} />
          <div style={s.metricMiniGrid}>
            <MetricMiniCard
              label={tr('branch_intel_avg_cost')}
              value={filteredSummary.avgExpense != null ? formatPctForLang(filteredSummary.avgExpense, 1, lang) : '-'}
              tone="var(--amber)"
            />
            <MetricMiniCard
              label={tr('highest_cost')}
              value={topCostRows[0] ? (lang === 'ar' && topCostRows[0].name_ar ? topCostRows[0].name_ar : topCostRows[0].branch_name) : '-'}
              tone="var(--red)"
              sub={topCostRows[0]?.expense_ratio != null ? formatPctForLang(topCostRows[0].expense_ratio, 1, lang) : '-'}
            />
          </div>
          <SimpleList
            items={topCostRows.map((row) => ({
              title: `${lang === 'ar' && row.name_ar ? row.name_ar : row.branch_name} · ${formatPctForLang(row.expense_ratio, 1, lang)}`,
              body: `${tr('kpi_net_profit')}: ${row.profit_share_pct != null ? `${Number(row.profit_share_pct).toFixed(1)}%` : '-'} | ${tr('kpi_revenue')}: ${row.revenue_share_pct != null ? `${Number(row.revenue_share_pct).toFixed(1)}%` : '-'}`,
              tone: Number(row.expense_ratio) >= 75 ? 'var(--red)' : 'var(--amber)',
            }))}
            emptyText="-"
          />
        </div>

        <div style={s.drillSection}>
          <SectionTitle title={tr('tab_root_causes')} />
          <SimpleList items={insights.slice(0, 5).map(normalizeDecisionItem)} />
        </div>
        <div style={s.drillSection}>
          <SectionTitle title={tr('tab_cfo_decisions')} />
          <SimpleList items={decisions.slice(0, 5).map(normalizeDecisionItem)} />
        </div>
      </div>

      <div style={s.portfolioTableWrap}>
        <div style={s.portfolioTableHeader}>
          <SectionTitle title={tr('rankings')} />
        </div>
        <table style={s.table}>
          <thead>
            <tr>
              {[
                '#',
                tr('branch_name'),
                tr('prof_net_margin'),
                tr('branch_col_expense_ratio'),
                tr('kpi_revenue'),
                tr('kpi_net_profit'),
                tr('strongest'),
                tr('branch_status'),
              ].map((h, i) => (
                <th key={i} style={s.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {topRows.map((row) => (
              <tr key={row.branch_id} style={{ cursor: 'pointer' }} onClick={() => onOpenBranch(row.branch_id)}>
                <td style={s.td}>{row.overall_portfolio_rank ?? '-'}</td>
                <td style={{ ...s.td, fontWeight: 700 }}>
                  {lang === 'ar' && row.name_ar ? row.name_ar : row.branch_name}
                </td>
                <td style={{ ...s.td, fontFamily: 'monospace', color: 'var(--green)' }}>
                  {row.net_margin_pct != null ? formatPctForLang(row.net_margin_pct, 1, lang) : '-'}
                </td>
                <td style={{ ...s.td, fontFamily: 'monospace', color: 'var(--amber)' }}>
                  {row.expense_ratio != null ? formatPctForLang(row.expense_ratio, 1, lang) : '-'}
                </td>
                <td style={{ ...s.td, fontFamily: 'monospace' }}>
                  {row.revenue_share_pct != null ? `${row.revenue_share_pct}%` : '-'}
                </td>
                <td style={{ ...s.td, fontFamily: 'monospace' }}>
                  {row.profit_share_pct != null ? `${row.profit_share_pct}%` : '-'}
                </td>
                <td style={s.td}>{row.role_label || row.role || '-'}</td>
                <td style={s.td}>
                  <button style={s.rowOpenBtn} onClick={(e) => { e.stopPropagation(); onOpenBranch(row.branch_id) }}>
                    {tr('cmd_drill_health_hint')}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filteredRows.length > topRows.length && (
          <div style={s.portfolioFootnote}>
            {topRows.length}/{filteredRows.length} {tr('branch_total')}
          </div>
        )}
      </div>
    </div>
  )
}

function BranchDrillModal({ branch, data, loading, err, onClose, tr, lang }) {
  const detail = data || {}
  const kpis = detail.kpis || {}
  const expenseIntel = detail.expense_intelligence || {}
  const expenseSummary = expenseIntel.summary || {}
  const expenseThresholds = expenseIntel.thresholds || {}
  const expenseInsights = Array.isArray(expenseIntel.insights) ? expenseIntel.insights : []
  const expenseMovers = Array.isArray(expenseIntel.top_movers) ? expenseIntel.top_movers : []
  const rootCauses = Array.isArray(detail.root_causes) ? detail.root_causes : []
  const decisions = Array.isArray(detail.cfo_decisions) ? detail.cfo_decisions : []
  const branchDecisions = Array.isArray(detail.decisions) ? detail.decisions : []
  const expenseDecisions = Array.isArray(detail.expense_decisions_v2) ? detail.expense_decisions_v2 : []
  const forecast = detail.forecast_scenarios || detail.forecast || {}

  return (
    <div style={s.overlay}>
      <div style={{ ...s.modal, maxWidth: 1080, maxHeight: '92vh', overflowY: 'auto', paddingBottom: 28 }}>
        <div style={{ ...s.modalHeader, position: 'sticky', top: 0, background: 'var(--bg-surface)', zIndex: 2 }}>
          <div style={s.modalIconWrap}>
            <IcoBranch size={16} />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 800, fontSize: 16, color: 'var(--text-primary)' }}>
              {lang === 'ar' && branch.name_ar ? branch.name_ar : branch.name}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
              {detail.latest_period ? `${tr('latest_period')}: ${detail.latest_period}` : (branch.city || branch.country || '')}
            </div>
          </div>
          {detail.health_score != null && (
            <div style={s.healthPill}>
              <strong>{detail.health_score}/100</strong>
              <span>{detail.health_label || tr('financial_health')}</span>
            </div>
          )}
          <button onClick={onClose} style={s.closeBtn}>x</button>
        </div>

        {loading && (
          <div style={s.center}>
            <div style={s.spinner} />
          </div>
        )}

        {err && !loading && (
          <div style={s.errorBox}>
            <span>! {err}</span>
          </div>
        )}

        {!loading && !err && detail && detail.has_data === false && (
          <div style={s.emptyState}>
            <div style={s.emptyIcon}><IcoBranch size={28} /></div>
            <p style={{ color: 'var(--text-secondary)', fontSize: 14, margin: '12px 0 0' }}>
              {tr('branch_no_data_title')}
            </p>
          </div>
        )}

        {!loading && !err && detail && detail.has_data !== false && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18, paddingTop: 18 }}>
            <div style={s.overviewGrid}>
              <InsightCard title={tr('kpi_revenue')} value={formatCompactForLang(kpis.revenue, lang)} sub={formatFullForLang(kpis.revenue, lang)} tone="var(--accent)" />
              <InsightCard title={tr('kpi_net_profit')} value={formatCompactForLang(kpis.net_profit, lang)} sub={formatFullForLang(kpis.net_profit, lang)} tone={(kpis.net_profit ?? 0) >= 0 ? 'var(--green)' : 'var(--red)'} />
              <InsightCard title={tr('kpi_net_margin')} value={kpis.net_margin_pct != null ? formatPctForLang(kpis.net_margin_pct, 1, lang) : '-'} sub={tr('net_margin')} tone="var(--green)" />
              <InsightCard title={tr('kpi_expense_ratio')} value={kpis.expense_ratio != null ? formatPctForLang(kpis.expense_ratio, 1, lang) : '-'} sub={tr('expense_ratio_short')} tone="var(--amber)" />
              <InsightCard title={tr('cashflow_operating')} value={kpis.operating_cashflow != null ? formatCompactForLang(kpis.operating_cashflow, lang) : '-'} sub={kpis.operating_cashflow != null ? formatFullForLang(kpis.operating_cashflow, lang) : '-'} tone="var(--blue)" />
            </div>

            <div style={s.drillSection}>
              <SectionTitle title={tr('financial_health')} />
              <div style={s.signalGrid}>
                <SignalPill label={tr('latest_period')} value={detail.latest_period || '-'} />
                <SignalPill label={tr('kpi_revenue')} value={readTrendLabel(detail?.trends?.revenue?.direction, tr)} />
                <SignalPill label={tr('chart_net_profit_trend')} value={readTrendLabel(detail?.trends?.net_profit?.direction, tr)} />
                <SignalPill label={tr('expense_ratio_short')} value={readTrendLabel(detail?.trends?.expenses?.direction, tr)} />
              </div>
            </div>

            <div style={s.twoCol}>
              <div style={s.drillSection}>
                <SectionTitle title={tr('expense_analysis_title')} />
                <div style={s.metricMiniGrid}>
                  <MetricMiniCard
                    label={tr('expense_ratio_short')}
                    value={expenseSummary.expense_ratio_pct != null ? formatPctForLang(expenseSummary.expense_ratio_pct, 1, lang) : '-'}
                    tone={readThresholdTone(expenseThresholds.expense_ratio_pct?.status)}
                    sub={localizeThresholdStatus(expenseThresholds.expense_ratio_pct?.status, tr)}
                  />
                  <MetricMiniCard
                    label={tr('expense_cogs_ratio')}
                    value={expenseSummary.cogs_ratio_pct != null ? formatPctForLang(expenseSummary.cogs_ratio_pct, 1, lang) : '-'}
                    tone={readThresholdTone(expenseThresholds.cogs_ratio_pct?.status)}
                    sub={localizeThresholdStatus(expenseThresholds.cogs_ratio_pct?.status, tr)}
                  />
                  <MetricMiniCard
                    label={tr('expense_opex_ratio')}
                    value={expenseSummary.opex_ratio_pct != null ? formatPctForLang(expenseSummary.opex_ratio_pct, 1, lang) : '-'}
                    tone={readThresholdTone(expenseThresholds.opex_ratio_pct?.status)}
                    sub={localizeThresholdStatus(expenseThresholds.opex_ratio_pct?.status, tr)}
                  />
                  <MetricMiniCard
                    label={tr('expense_primary_pressure')}
                    value={localizeExpenseGroup(expenseSummary.primary_pressure, tr)}
                    tone="var(--amber)"
                  />
                </div>
                <div style={s.twoColCompact}>
                  <div>
                    <SectionTitle title={tr('expense_top_movers')} />
                    <SimpleList
                      items={expenseMovers.map((item) => ({
                        title: `${localizeExpenseGroup(item?.group, tr)} · ${item?.variance_pct != null ? formatPctForLang(item.variance_pct, 1, lang) : '-'}`,
                        body: item?.amount_delta != null ? formatFullForLang(item.amount_delta, lang) : '',
                        tone: item?.direction === 'increasing' ? 'var(--red)' : item?.direction === 'decreasing' ? 'var(--green)' : 'var(--accent)',
                      }))}
                      emptyText="-"
                    />
                  </div>
                  <div>
                    <SectionTitle title={tr('expense_alerts_title')} />
                    <SimpleList
                      items={expenseInsights.slice(0, 5).map((item) => ({
                        title: item?.what_happened || item?.type || '-',
                        body: [item?.why_it_matters, item?.what_to_do].filter(Boolean).join(' '),
                        tone: item?.severity === 'critical' || item?.severity === 'high' ? 'var(--red)' : item?.severity === 'warning' ? 'var(--amber)' : 'var(--accent)',
                      }))}
                      emptyText="-"
                    />
                  </div>
                </div>
              </div>

              <div style={s.drillSection}>
                <SectionTitle title={tr('tab_root_causes')} />
                <SimpleList
                  items={rootCauses.map((item) => ({
                    title: item?.title || item?.domain || '-',
                    body: item?.explanation || localizeTrendDirection(item?.direction, tr) || '',
                    tone: item?.direction === 'declining' ? 'var(--red)' : 'var(--accent)',
                  }))}
                />
              </div>

              <div style={s.drillSection}>
                <SectionTitle title={tr('expense_actions_title')} />
                <SimpleList items={[...expenseDecisions, ...decisions, ...branchDecisions].map(normalizeDecisionItem)} />
              </div>
            </div>

            <div style={s.twoCol}>
              <div style={s.drillSection}>
                <SectionTitle title={tr('intelligence_tab')} />
                <SimpleList items={extractNarrativeLines(detail.deep_intelligence)} />
              </div>

              <div style={s.drillSection}>
                <SectionTitle title={tr('ai_forecast_title')} />
                <SimpleList items={extractForecastLines(forecast, tr)} emptyText="-" />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function SectionTitle({ title }) {
  return (
    <div style={{ fontSize: 11, fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 12 }}>
      {title}
    </div>
  )
}

function SignalPill({ label, value }) {
  return (
    <div style={s.signalPill}>
      <span style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.06em' }}>{label}</span>
      <strong style={{ fontSize: 13, color: 'var(--text-primary)' }}>{value}</strong>
    </div>
  )
}

function MetricMiniCard({ label, value, sub, tone = 'var(--text-primary)' }) {
  return (
    <div style={s.metricMiniCard}>
      <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.06em' }}>
        {label}
      </div>
      <div style={{ fontSize: 18, fontWeight: 800, color: tone, marginTop: 4 }}>
        {value}
      </div>
      {sub ? (
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
          {sub}
        </div>
      ) : null}
    </div>
  )
}

function SimpleList({ items, emptyText = '-' }) {
  if (!items?.length) return <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>{emptyText}</div>
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {items.map((item, index) => (
        <div key={index} style={s.listCard}>
          <div style={{ fontWeight: 700, fontSize: 13, color: item?.tone || 'var(--text-primary)' }}>
            {item?.title || '-'}
          </div>
          {item?.body ? (
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.55, marginTop: 4 }}>
              {item.body}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  )
}

function normalizeDecisionItem(item) {
  if (typeof item === 'string') return { title: item, body: '', tone: 'var(--accent)' }
  if (!item || typeof item !== 'object') return { title: '-', body: '', tone: 'var(--text-primary)' }
  return {
    title: item.title || item.action || item.decision || item.label || item.summary || item.priority || '-',
    body: item.detail || item.message || item.reason || item.explanation || item.recommendation || '',
    tone: item.priority === 'high' ? 'var(--red)' : item.priority === 'medium' ? 'var(--amber)' : 'var(--accent)',
  }
}

function extractNarrativeLines(value) {
  if (!value) return []
  if (Array.isArray(value)) return value.map(normalizeDecisionItem)
  if (typeof value === 'string') return [{ title: value, body: '', tone: 'var(--accent)' }]
  if (typeof value !== 'object') return []
  return Object.entries(value)
    .flatMap(([, nested]) => {
      if (Array.isArray(nested)) return nested.map(normalizeDecisionItem)
      if (typeof nested === 'string') return [{ title: nested, body: '', tone: 'var(--accent)' }]
      if (nested && typeof nested === 'object') {
        return Object.values(nested)
          .filter((entry) => typeof entry === 'string')
          .map((entry) => ({ title: entry, body: '', tone: 'var(--accent)' }))
      }
      return []
    })
    .slice(0, 8)
}

function extractForecastLines(forecast, tr) {
  if (!forecast) return []
  if (forecast.forecast_available) {
    return [
      {
        title: tr('latest_period'),
        body: Array.isArray(forecast.forecast_periods) ? forecast.forecast_periods.join(' * ') : '-',
        tone: 'var(--accent)',
      },
      {
        title: tr('financial_health'),
        body: forecast.forecast_quality || '-',
        tone: 'var(--blue)',
      },
    ]
  }
  if (forecast.available === false) {
    return [{ title: tr('ai_forecast_title'), body: forecast.reason || '-', tone: 'var(--text-muted)' }]
  }
  return Object.entries(forecast)
    .filter(([, val]) => typeof val === 'string' || typeof val === 'number')
    .slice(0, 4)
    .map(([key, val]) => ({ title: key, body: String(val), tone: 'var(--accent)' }))
}

function readTrendLabel(direction, tr) {
  if (direction === 'improving') return tr('trend_growing')
  if (direction === 'declining') return tr('trend_declining')
  return tr('trend_stable')
}

function readThresholdTone(status) {
  if (status === 'critical' || status === 'high') return 'var(--red)'
  if (status === 'warning' || status === 'elevated') return 'var(--amber)'
  if (status === 'ok') return 'var(--green)'
  return 'var(--text-primary)'
}

function localizeThresholdStatus(status, tr) {
  if (status === 'ok') return tr('status_good_simple')
  if (status === 'warning' || status === 'elevated') return tr('status_warning_simple')
  if (status === 'critical' || status === 'high') return tr('status_risk_simple')
  return tr('status_neutral_simple')
}

function localizeTrendDirection(direction, tr) {
  if (direction === 'improving' || direction === 'growing') return tr('trend_growing')
  if (direction === 'declining') return tr('trend_declining')
  if (direction === 'stable' || direction === 'neutral') return tr('trend_stable')
  return direction || ''
}

function localizeExpenseGroup(group, tr) {
  if (!group) return '-'
  const key = String(group).toLowerCase()
  const map = {
    cogs: 'exp_group_cogs',
    payroll: 'exp_group_payroll',
    fuel: 'exp_group_fuel',
    maintenance: 'exp_group_maintenance',
    opex: 'exp_group_opex',
    unclassified: 'exp_group_unclassified',
    other: 'exp_group_other',
  }
  return map[key] ? tr(map[key]) : String(group)
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
  tabSwitch: {
    display: 'inline-flex',
    gap: 8,
    marginBottom: 18,
    padding: 6,
    borderRadius: 12,
    background: 'var(--bg-elevated)',
    border: '1px solid var(--border)',
  },
  tabBtn: {
    padding: '9px 14px',
    borderRadius: 8,
    border: '1px solid transparent',
    background: 'transparent',
    color: 'var(--text-secondary)',
    fontSize: 12,
    fontWeight: 700,
    cursor: 'pointer',
  },
  tabBtnActive: {
    padding: '9px 14px',
    borderRadius: 8,
    border: '1px solid var(--border-accent)',
    background: 'var(--accent-dim)',
    color: 'var(--accent)',
    fontSize: 12,
    fontWeight: 800,
    cursor: 'pointer',
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
  overviewGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
    gap: 12,
    marginBottom: 20,
  },
  insightCard: {
    background: 'var(--bg-surface)',
    border: '1px solid var(--border)',
    borderRadius: 12,
    padding: '14px 16px',
  },
  drillSection: {
    background: 'var(--bg-surface)',
    border: '1px solid var(--border)',
    borderRadius: 12,
    padding: '16px 18px',
  },
  twoCol: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
    gap: 16,
  },
  signalGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
    gap: 10,
  },
  signalPill: {
    display: 'flex',
    flexDirection: 'column',
    gap: 5,
    padding: '10px 12px',
    borderRadius: 10,
    background: 'var(--bg-elevated)',
    border: '1px solid var(--border)',
  },
  metricMiniGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
    gap: 10,
    marginBottom: 14,
  },
  metricMiniCard: {
    padding: '10px 12px',
    borderRadius: 10,
    background: 'var(--bg-elevated)',
    border: '1px solid var(--border)',
  },
  twoColCompact: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
    gap: 14,
  },
  listCard: {
    padding: '10px 12px',
    borderRadius: 10,
    background: 'var(--bg-elevated)',
    border: '1px solid var(--border)',
  },
  healthPill: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-end',
    gap: 2,
    padding: '8px 12px',
    borderRadius: 10,
    background: 'var(--accent-dim)',
    border: '1px solid var(--border-accent)',
    color: 'var(--accent)',
    fontSize: 11,
  },
  portfolioWrap: {
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
    marginBottom: 22,
    padding: '18px 18px 16px',
    background: 'linear-gradient(180deg, rgba(0,212,170,.05), rgba(255,255,255,.01))',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-card)',
  },
  portfolioHeader: {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 16,
    flexWrap: 'wrap',
  },
  portfolioEyebrow: {
    fontSize: 10,
    fontWeight: 800,
    color: 'var(--accent)',
    textTransform: 'uppercase',
    letterSpacing: '.1em',
    marginBottom: 6,
  },
  portfolioTitle: {
    fontSize: 20,
    fontWeight: 800,
    color: 'var(--text-primary)',
    margin: 0,
  },
  portfolioSub: {
    fontSize: 12,
    color: 'var(--text-muted)',
    margin: '4px 0 0',
  },
  portfolioPill: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-end',
    gap: 4,
    padding: '10px 14px',
    borderRadius: 12,
    background: 'rgba(0,212,170,.08)',
    border: '1px solid var(--border-accent)',
    color: 'var(--accent)',
  },
  portfolioTableWrap: {
    overflowX: 'auto',
    background: 'var(--bg-surface)',
    border: '1px solid var(--border)',
    borderRadius: 12,
  },
  portfolioTableHeader: {
    padding: '14px 16px 0',
  },
  portfolioFootnote: {
    padding: '10px 16px 14px',
    fontSize: 11,
    color: 'var(--text-muted)',
  },
  portfolioFilters: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
    gap: 12,
    marginBottom: 6,
  },
  filterBlock: {
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
    fontSize: 11,
    fontWeight: 700,
    color: 'var(--text-muted)',
    textTransform: 'uppercase',
    letterSpacing: '.06em',
  },
  filterInput: {
    width: '100%',
    padding: '10px 12px',
    borderRadius: 10,
    border: '1px solid var(--border)',
    background: 'var(--bg-surface)',
    color: 'var(--text-primary)',
    fontSize: 13,
    outline: 'none',
  },
  portfolioChartsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
    gap: 16,
  },
  chartCard: {
    background: 'var(--bg-surface)',
    border: '1px solid var(--border)',
    borderRadius: 12,
    padding: '16px 18px',
  },
  chartWrap: {
    width: '100%',
    height: 300,
  },
  chartEmpty: {
    height: '100%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: 'var(--text-muted)',
    fontSize: 12,
  },
  chartTooltip: {
    background: 'rgba(8,12,18,.96)',
    border: '1px solid rgba(255,255,255,.08)',
    borderRadius: 10,
    padding: '10px 12px',
    minWidth: 140,
    boxShadow: '0 14px 28px rgba(0,0,0,.35)',
  },
  chartTooltipRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    fontSize: 12,
    marginTop: 4,
  },
  rowOpenBtn: {
    padding: '6px 10px',
    borderRadius: 8,
    border: '1px solid var(--border)',
    background: 'transparent',
    color: 'var(--text-secondary)',
    fontSize: 11,
    fontWeight: 700,
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
}
