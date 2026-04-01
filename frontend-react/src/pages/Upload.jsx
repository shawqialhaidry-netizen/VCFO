import { useState, useRef, useEffect, useCallback } from 'react'
import { useLang }       from '../context/LangContext.jsx'
import { useCompany }    from '../context/CompanyContext.jsx'
import CompanySelector   from '../components/CompanySelector.jsx'
import { mapError }      from '../utils/errorMessages.js'

const API = '/api/v1'

function getAuthHeaders() {
  try {
    const raw   = localStorage.getItem('vcfo_auth')
    const token = raw ? JSON.parse(raw)?.token : null
    return token ? { Authorization: `Bearer ${token}` } : {}
  } catch { return {} }
}

// ── Type badge ─────────────────────────────────────────────────────────────────
const TYPE_COLORS = {
  revenue:     { bg:'rgba(34,197,94,.12)',   color:'#22c55e', border:'#22c55e' },
  cogs:        { bg:'rgba(251,146,60,.12)',   color:'#fb923c', border:'#fb923c' },
  expenses:    { bg:'rgba(239,68,68,.12)',    color:'#ef4444', border:'#ef4444' },
  assets:      { bg:'rgba(59,130,246,.12)',   color:'#3b82f6', border:'#3b82f6' },
  liabilities: { bg:'rgba(168,85,247,.12)',   color:'#a855f7', border:'#a855f7' },
  equity:      { bg:'rgba(20,184,166,.12)',   color:'#14b8a6', border:'#14b8a6' },
  tax:         { bg:'rgba(234,179,8,.12)',    color:'#eab308', border:'#eab308' },
  other:       { bg:'rgba(100,116,139,.12)', color:'#64748b', border:'#64748b' },
}
function TypeBadge({ type }) {
  const c = TYPE_COLORS[type] || TYPE_COLORS.other
  return (
    <span style={{ background:c.bg, color:c.color, border:`1px solid ${c.border}`,
      borderRadius:4, padding:'2px 8px', fontSize:10, fontWeight:700,
      textTransform:'uppercase', letterSpacing:'.05em', whiteSpace:'nowrap' }}>
      {type}
    </span>
  )
}
function ConfBar({ value }) {
  const pct   = Math.round((value || 0) * 100)
  const color = pct >= 70 ? 'var(--green)' : pct >= 40 ? 'var(--amber)' : 'var(--red)'
  return (
    <div style={{ display:'flex', alignItems:'center', gap:6 }}>
      <div style={{ width:44, height:5, background:'var(--border)', borderRadius:3, overflow:'hidden' }}>
        <div style={{ width:`${pct}%`, height:'100%', background:color, borderRadius:3 }}/>
      </div>
      <span style={{ fontSize:11, color, fontFamily:'monospace', fontWeight:600 }}>{pct}%</span>
    </div>
  )
}

// ── Upload mode selector ────────────────────────────────────────────────────────
function ModeSelector({ uploadMode, setUploadMode, tr }) {
  return (
    <div style={{ display:'flex', gap:0, background:'var(--bg-elevated)', borderRadius:10,
      padding:4, marginBottom:16, border:'1px solid var(--border)' }}>
      {[
        { key:'auto_detect', labelKey:'upload_mode_auto',    icon:'🔍' },
        { key:'monthly',     labelKey:'upload_mode_monthly', icon:'📅' },
        { key:'annual',      labelKey:'upload_mode_annual',  icon:'📆' },
      ].map(opt => (
        <button key={opt.key} onClick={() => setUploadMode(opt.key)}
          style={{ flex:1, padding:'10px 12px', borderRadius:8, border:'none', cursor:'pointer',
            fontSize:13, fontWeight:600, fontFamily:'var(--font-display)', transition:'all var(--t)',
            background: uploadMode === opt.key ? 'var(--accent)' : 'transparent',
            color:      uploadMode === opt.key ? '#000' : 'var(--text-secondary)' }}>
          {opt.icon} {tr(opt.labelKey) || opt.key}
        </button>
      ))}
    </div>
  )
}

// ── Replace confirmation modal ─────────────────────────────────────────────────
function ReplaceModal({ info, onConfirm, onCancel, lang }) {
  if (!info) return null
  const l = lang || 'en'
  return (
    <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,.75)', zIndex:1000,
      display:'flex', alignItems:'center', justifyContent:'center', padding:'20px' }}>
      <div style={{ background:'var(--bg-surface)', border:'1px solid var(--amber)',
        borderRadius:16, padding:28, maxWidth:460, width:'100%',
        maxHeight:'calc(100vh - 80px)', overflowY:'auto',
        boxShadow:'0 24px 80px rgba(0,0,0,.6)' }}>

        <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:16 }}>
          <span style={{ fontSize:22 }}>🔄</span>
          <div>
            <div style={{ fontSize:16, fontWeight:800, color:'var(--amber)' }}>
              {l === 'ar' ? 'فترة موجودة مسبقاً' : 'Period Already Exists'}
            </div>
            <div style={{ fontSize:11, color:'var(--text-secondary)', marginTop:2 }}>
              {l === 'ar'
                ? 'يمكنك استبدال البيانات الحالية بالرفع الجديد'
                : 'You can replace the current data with the new upload'}
            </div>
          </div>
        </div>

        <div style={{ background:'var(--bg-elevated)', borderRadius:10, padding:'12px 14px',
          marginBottom:16, fontSize:12, lineHeight:2.2,
          border:'1px solid rgba(251,191,36,.25)' }}>
          {[
            [l === 'ar' ? 'الفترة'       : 'Period',       info.period      || '—'],
            [l === 'ar' ? 'الملف الحالي' : 'Existing file', info.filename    || '—'],
            [l === 'ar' ? 'ستُستبدل بـ'  : 'Replace with',  info.newFilename || (l === 'ar' ? 'الملف الجديد' : 'new file')],
          ].map(([label, value]) => (
            <div key={label} style={{ display:'flex', justifyContent:'space-between', gap:12 }}>
              <span style={{ color:'var(--text-secondary)', flexShrink:0 }}>{label}:</span>
              <span style={{ color:'#fff', fontFamily:'monospace', textAlign:'end',
                overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', maxWidth:260 }}>
                {value}
              </span>
            </div>
          ))}
        </div>

        <div style={{ padding:'9px 12px', background:'rgba(251,191,36,0.07)',
          border:'1px solid rgba(251,191,36,0.25)', borderRadius:8,
          fontSize:11, color:'var(--amber)', marginBottom:18, lineHeight:1.5 }}>
          ⚠ {l === 'ar'
            ? 'سيتم حذف البيانات الحالية لهذه الفترة واستبدالها نهائياً'
            : 'Current data for this period will be permanently replaced. This cannot be undone.'}
        </div>

        <div style={{ display:'flex', gap:10 }}>
          <button onClick={onConfirm}
            style={{ flex:1, background:'var(--amber)', color:'#000', border:'none',
              borderRadius:8, padding:'10px 0', fontSize:13, fontWeight:700, cursor:'pointer' }}>
            {l === 'ar' ? 'استبدال' : 'Replace'}
          </button>
          <button onClick={onCancel}
            style={{ flex:1, background:'var(--bg-elevated)', color:'var(--text-secondary)',
              border:'1px solid var(--border)', borderRadius:8, padding:'10px 0',
              fontSize:13, cursor:'pointer' }}>
            {l === 'ar' ? 'إلغاء' : 'Cancel'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Delete confirmation modal ──────────────────────────────────────────────────
function DeleteModal({ info, onConfirm, onCancel, lang }) {
  // deleteScope is separate from any outer state — no name collision
  const [deleteScope, setDeleteScope] = useState('single')

  // Reset scope every time the modal opens with new info
  useEffect(() => { if (info) setDeleteScope('single') }, [info])

  if (!info) return null
  const l = lang || 'en'

  const tbLabels = {
    pre_closing:  l === 'ar' ? 'قبل الإقفال' : 'Pre-closing',
    post_closing: l === 'ar' ? 'بعد الإقفال' : 'Post-closing',
  }

  return (
    <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,.75)', zIndex:1000,
      display:'flex', alignItems:'center', justifyContent:'center', padding:'20px' }}>
      <div style={{ background:'var(--bg-surface)', border:'1px solid var(--red)',
        borderRadius:16, padding:28, maxWidth:480, width:'100%',
        maxHeight:'calc(100vh - 80px)', overflowY:'auto',
        boxShadow:'0 24px 80px rgba(0,0,0,.6)' }}>

        {/* Header */}
        <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:18 }}>
          <span style={{ fontSize:22 }}>🗑</span>
          <div>
            <div style={{ fontSize:16, fontWeight:800, color:'var(--red)' }}>
              {l === 'ar' ? 'تأكيد الحذف' : 'Confirm Delete'}
            </div>
            <div style={{ fontSize:11, color:'var(--text-secondary)', marginTop:2 }}>
              {l === 'ar' ? 'هذا الإجراء لا يمكن التراجع عنه' : 'This action cannot be undone'}
            </div>
          </div>
        </div>

        {/* Record details */}
        <div style={{ background:'var(--bg-elevated)', borderRadius:10, padding:'12px 14px',
          marginBottom:16, fontSize:12, lineHeight:2.2, border:'1px solid var(--border)' }}>
          {[
            [l === 'ar' ? 'الشركة'      : 'Company',  info.company_name || '—'],
            [l === 'ar' ? 'الفترة'      : 'Period',   info.period       || '—'],
            [l === 'ar' ? 'الملف'       : 'File',     info.original_filename || info.filename || '—'],
            [l === 'ar' ? 'نوع الميزان' : 'TB Type',  info.tb_type
              ? (tbLabels[info.tb_type] || info.tb_type)
              : (l === 'ar' ? 'غير محدد' : 'Unknown')],
            [l === 'ar' ? 'الصفوف'      : 'Records',  info.record_count
              ? info.record_count.toLocaleString()
              : '—'],
          ].map(([label, value]) => (
            <div key={label} style={{ display:'flex', justifyContent:'space-between', gap:12 }}>
              <span style={{ color:'var(--text-secondary)', flexShrink:0 }}>{label}:</span>
              <span style={{ color:'var(--text-primary)', fontFamily:'monospace',
                textAlign:'end', overflow:'hidden', textOverflow:'ellipsis',
                whiteSpace:'nowrap', maxWidth:260 }}>
                {value}
              </span>
            </div>
          ))}
        </div>

        {/* Scope selector */}
        <div style={{ marginBottom:18 }}>
          <div style={{ fontSize:11, fontWeight:700, color:'var(--text-secondary)',
            textTransform:'uppercase', letterSpacing:'.06em', marginBottom:8 }}>
            {l === 'ar' ? 'نطاق الحذف' : 'Delete scope'}
          </div>
          {[
            ['single',
              l === 'ar' ? 'هذا الرفع فقط'           : 'This upload only',
              l === 'ar' ? 'يحذف السجل والملف فقط'   : 'Deletes this record + its file'],
            ['period',
              l === 'ar' ? 'كل بيانات هذه الفترة'    : 'All data for this period',
              l === 'ar' ? 'يحذف جميع رفعات الفترة والبيانات المشتقة'
                         : 'Deletes all uploads for this period + derived branch data'],
          ].map(([val, label, hint]) => (
            <label key={val} style={{ display:'flex', alignItems:'flex-start', gap:10,
              padding:'10px 12px', borderRadius:9, cursor:'pointer', marginBottom:6,
              border:`1px solid ${deleteScope === val ? 'var(--red)' : 'var(--border)'}`,
              background: deleteScope === val ? 'rgba(248,113,113,0.06)' : 'var(--bg-elevated)' }}>
              <input type="radio" value={val} checked={deleteScope === val}
                onChange={() => setDeleteScope(val)}
                style={{ marginTop:2, accentColor:'var(--red)', flexShrink:0 }}/>
              <div>
                <div style={{ fontSize:12, fontWeight:600, color:'#ffffff' }}>{label}</div>
                <div style={{ fontSize:10, color:'var(--text-secondary)', marginTop:2 }}>{hint}</div>
              </div>
            </label>
          ))}
        </div>

        {/* Warning */}
        <div style={{ padding:'9px 12px', background:'rgba(248,113,113,0.07)',
          border:'1px solid rgba(248,113,113,0.25)', borderRadius:8,
          fontSize:11, color:'var(--red)', marginBottom:18, lineHeight:1.5 }}>
          ⚠ {deleteScope === 'period'
            ? (l === 'ar'
                ? 'سيتم حذف جميع رفعات الفترة والبيانات المشتقة منها نهائياً'
                : 'All uploads for this period and derived data will be permanently deleted')
            : (l === 'ar'
                ? 'سيتم حذف هذا الرفع والملف المرتبط به نهائياً'
                : 'This upload record and its associated file will be permanently deleted')}
        </div>

        {/* Actions */}
        <div style={{ display:'flex', gap:10 }}>
          <button onClick={() => onConfirm(deleteScope)}
            style={{ flex:1, background:'var(--red)', color:'#fff', border:'none',
              borderRadius:8, padding:'10px 0', fontSize:13, fontWeight:700, cursor:'pointer' }}>
            {l === 'ar' ? 'تأكيد الحذف' : 'Confirm Delete'}
          </button>
          <button onClick={onCancel}
            style={{ flex:1, background:'var(--bg-elevated)', color:'var(--text-secondary)',
              border:'1px solid var(--border)', borderRadius:8, padding:'10px 0',
              fontSize:13, cursor:'pointer' }}>
            {l === 'ar' ? 'إلغاء' : 'Cancel'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ══════════════════════════════════════════════════════════════════════════════
//  Main Upload page
// ══════════════════════════════════════════════════════════════════════════════
export default function Upload() {
  const { tr, lang }                              = useLang()
  // Destructure selectedCompany explicitly — fixes "selectedCompany is not defined"
  const { selectedId, selectedCompany, invalidateCache } = useCompany()

  // uploadMode is distinct from any modal-level variable
  const [uploadMode, setUploadMode] = useState('auto_detect')
  const [dragging,   setDragging]   = useState(false)
  const [file,       setFile]       = useState(null)
  const [period,     setPeriod]     = useState('')
  const [year,       setYear]       = useState('')
  const [tbType,     setTbType]     = useState('')
  const [branchId,   setBranchId]   = useState('')
  const [branches,   setBranches]   = useState([])
  const [processing, setProcessing] = useState(false)
  const [result,     setResult]     = useState(null)
  const [error,      setError]      = useState(null)
  const [uploads,    setUploads]    = useState([])
  const [replaceInfo, setReplaceInfo] = useState(null)  // replace modal state
  const [deleteInfo,  setDeleteInfo]  = useState(null)  // delete modal state
  const [pendingSubmit, setPendingSubmit] = useState(false)
  const [toast,      setToast]      = useState(null)
  const inputRef = useRef()

  const companyId      = selectedId
  const companyName    = selectedCompany?.name || ''  // safe — never undefined

  // ── Fetch upload history ────────────────────────────────────────────────────
  const fetchUploads = useCallback(() => {
    if (!companyId) return
    fetch(`${API}/uploads?company_id=${companyId}`, { headers: getAuthHeaders() })
      .then(r => r.json())
      .then(data => { if (Array.isArray(data)) setUploads(data) })
      .catch(() => {})
  }, [companyId])

  useEffect(() => { fetchUploads() }, [fetchUploads])

  // ── Fetch branches for selected company ───────────────────────────────────
  useEffect(() => {
    setBranchId('')
    setBranches([])
    if (!companyId) return
    fetch(`${API}/branches?company_id=${companyId}`, { headers: getAuthHeaders() })
      .then(r => r.ok ? r.json() : [])
      .then(data => { if (Array.isArray(data)) setBranches(data.filter(b => b.is_active)) })
      .catch(() => {})
  }, [companyId])

  // ── Toast ──────────────────────────────────────────────────────────────────
  function showToast(msg, ok = true) {
    setToast({ msg, ok })
    setTimeout(() => setToast(null), 3500)
  }

  // ── File management ─────────────────────────────────────────────────────────
  function clearFile() {
    setFile(null); setResult(null); setError(null)
    if (inputRef.current) inputRef.current.value = ''
  }
  // Auto-detect uploadMode from filename keywords.
  // RULE: only switches mode when user is on auto_detect.
  // Explicit user choice (monthly / annual) is NEVER overridden.
  function detectModeFromFile(f) {
    if (!f) return
    const name = f.name.toLowerCase()
    const annualHints = ['annual', 'yearly', 'year', '_yr_', 'fy', 'full_year',
                         'سنوي', 'سنة', '2020','2021','2022','2023','2024','2025','2026']
    const hasYearMonth = /\d{4}-\d{2}/.test(name)
    const hasYearOnly  = /\b\d{4}\b/.test(name) && !hasYearMonth
    const hasAnnualKw  = annualHints.some(kw => name.includes(kw))

    const looksAnnual  = (hasAnnualKw || hasYearOnly) && !hasYearMonth
    const looksMonthly = hasYearMonth

    // Only auto-switch mode when the user has not made an explicit choice
    setUploadMode(prev => {
      if (prev !== 'auto_detect') return prev   // ← explicit choice wins, never override
      if (looksAnnual)  return 'annual'
      if (looksMonthly) return 'monthly'
      return prev
    })

    // Always try to pre-fill period/year from filename regardless of mode
    if (looksAnnual) {
      const m = name.match(/\b(20\d{2})\b/)
      if (m) setYear(m[1])
    } else if (looksMonthly) {
      const m = name.match(/(\d{4}-\d{2})/)
      if (m) setPeriod(m[1])
    }
  }

  function onDrop(e) {
    e.preventDefault(); setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) { setFile(f); setResult(null); setError(null); detectModeFromFile(f) }
  }
  function onSelect(e) {
    const f = e.target.files[0]
    if (f) { setFile(f); setResult(null); setError(null); detectModeFromFile(f) }
  }
  function onModeChange(m) {
    setUploadMode(m); setResult(null); setError(null); setFile(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  // ── Duplicate / replace check ───────────────────────────────────────────────
  async function checkDuplicate() {
    // Skip for annual and auto_detect — endpoint handles deduplication internally
    if (uploadMode === 'annual' || uploadMode === 'auto_detect') return null
    const p = period.trim()
    if (!p || !/^\d{4}-\d{2}$/.test(p)) return null
    try {
      // branch_id is part of duplicate identity: same period for a different branch is NOT a duplicate
      const qs = branchId
        ? `company_id=${companyId}&period=${p}&branch_id=${branchId}`
        : `company_id=${companyId}&period=${p}`
      const res  = await fetch(
        `${API}/uploads/check-period?${qs}`,
        { headers: getAuthHeaders() }
      )
      const data = await res.json()
      return data.exists ? data : null
    } catch { return null }
  }

  // ── Submit handler ──────────────────────────────────────────────────────────
  async function handleSubmit() {
    if (!file || !companyId) return

    if (uploadMode === 'monthly') {
      // Allow YYYY-MM — required for monthly
      if (!period.trim()) {
        setError(tr('upload_period_hint')); return
      }
      if (!/^\d{4}-\d{2}$/.test(period.trim())) {
        setError(tr('upload_format_hint')); return
      }
    }

    if (uploadMode === 'annual') {
      // Allow YYYY — required for annual
      if (!year.trim()) {
        setError(tr('upload_year_hint')); return
      }
      if (!/^\d{4}$/.test(year.trim())) {
        setError(tr('upload_year_invalid')); return
      }
      const y = parseInt(year.trim(), 10)
      if (y < 2000 || y > 2100) {
        setError(tr('upload_year_range')); return
      }
    }
    const dup = await checkDuplicate()
    if (dup) {
      setReplaceInfo({ period: period.trim(), filename: dup.filename, newFilename: file.name })
      setPendingSubmit(true)
      return
    }
    doSubmit()
  }

  function onConfirmReplace() { setReplaceInfo(null); setPendingSubmit(false); doSubmit() }
  function onCancelReplace()  { setReplaceInfo(null); setPendingSubmit(false) }

  async function doSubmit() {
    setProcessing(true); setResult(null); setError(null)
    try {
      const fd = new FormData()
      fd.append('file',        file)
      fd.append('company_id',  companyId)
      fd.append('upload_mode', uploadMode)
      if (uploadMode === 'monthly') fd.append('period', period.trim())
      if (uploadMode === 'annual')  fd.append('year',   year.trim())
      if (tbType)                   fd.append('tb_type', tbType)
      if (branchId)                 fd.append('branch_id', branchId)

      const res  = await fetch(`${API}/uploads`, {
        method: 'POST', headers: getAuthHeaders(), body: fd,
      })
      const data = await res.json()

      if (!res.ok) {
        // 409 = mode conflict — file structure disagrees with chosen mode
        if (res.status === 409 && data.detail?.mode_conflict) {
          const suggested = data.detail.suggested_mode || 'annual'
          setError(
            (data.detail.error || tr('upload_failed_msg')) +
            ` → Switch to "${suggested}" mode and try again.`
          )
        } else {
          setError(mapError(
            typeof data.detail === 'string' ? data.detail : (data.detail?.error || tr('upload_failed_msg')),
            lang
          ))
        }
      } else {
        setResult(data)
        clearFile()
        fetchUploads()
        invalidateCache?.(companyId)
        showToast(tr('upload_success'), true)
      }
    } catch (e) {
      setError(mapError(e.message, lang))
    } finally {
      setProcessing(false)
    }
  }

  // ── Delete handler ──────────────────────────────────────────────────────────
  // Parameter named deleteScope to avoid collision with uploadMode state
  async function handleConfirmDelete(deleteScope) {
    if (!deleteInfo) return
    try {
      const url = `${API}/uploads/${deleteInfo.id}?mode=${deleteScope || 'single'}`
      const res = await fetch(url, { method: 'DELETE', headers: getAuthHeaders() })

      if (res.ok) {
        const json = await res.json().catch(() => ({}))
        const n    = json.audit?.deleted_uploads?.length || 1
        showToast(
          deleteScope === 'period'
            ? tr('upload_deleted_for_period', { n, period: deleteInfo.period })
            : tr('delete_success'),
          true
        )
        fetchUploads()
        invalidateCache?.(companyId)
      } else {
        const json = await res.json().catch(() => ({}))
        showToast(json.detail || tr('upload_delete_failed'), false)
      }
    } catch {
      showToast(tr('upload_delete_failed'), false)
    } finally {
      setDeleteInfo(null)
    }
  }

  function openDeleteModal(uploadRecord) {
    setDeleteInfo({
      ...uploadRecord,
      company_name: companyName,   // always defined — from selectedCompany?.name
    })
  }

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div style={s.page}>

      {/* Toast notification */}
      {toast && (
        <div style={{
          position:'fixed', top:20, right:20, zIndex:2000,
          background: toast.ok ? 'rgba(34,197,94,.15)' : 'rgba(239,68,68,.15)',
          border: `1px solid ${toast.ok ? 'var(--green)' : 'var(--red)'}`,
          borderRadius:10, padding:'12px 20px',
          color: toast.ok ? 'var(--green)' : 'var(--red)',
          fontSize:13, fontWeight:600, 
        }}>
          {toast.ok ? '✓' : '✗'} {toast.msg}
        </div>
      )}

      {/* Modals */}
      <ReplaceModal
        info={replaceInfo}
        onConfirm={onConfirmReplace}
        onCancel={onCancelReplace}
        lang={lang}
      />
      <DeleteModal
        info={deleteInfo}
        onConfirm={handleConfirmDelete}
        onCancel={() => setDeleteInfo(null)}
        lang={lang}
      />

      {/* Header */}
      <div style={s.header}>
        <div>
          <h1 style={s.title}>{tr('upload_title')}</h1>
          <p style={s.subtitle}>{tr('upload_subtitle')}</p>
        </div>
        <CompanySelector />
      </div>

      {!companyId && (
        <div style={s.notice}>⚠ {tr('upload_company_select')}</div>
      )}

      {companyId && (
        <div style={s.grid}>

          {/* ── LEFT COLUMN ── */}
          <div>
            <div style={s.card}>
              <div style={s.cardTitle}>{tr('upload_mode')}</div>

              <ModeSelector uploadMode={uploadMode} setUploadMode={onModeChange} tr={tr} />

              <div style={s.hintBox}>
                {uploadMode === 'monthly'
                  ? `ℹ ${tr('upload_mode_hint_monthly')}`
                  : uploadMode === 'annual'
                  ? `ℹ ${tr('upload_mode_hint_annual')}`
                  : `ℹ ${tr('upload_mode_hint_auto')}`}
              </div>

              {/* Period / Year field — hidden in auto_detect unless user wants to specify */}
              {uploadMode !== 'auto_detect' && (
                <div style={{ ...s.formRow, marginTop:14 }}>
                  <div style={s.fieldWrap}>
                    <label style={s.label}>
                      {uploadMode === 'monthly'
                        ? tr('upload_period')
                        : tr('upload_year')}
                      <span style={{ color:'var(--text-secondary)', fontWeight:400,
                        marginLeft:6, fontSize:10 }}>
                        {uploadMode === 'monthly' ? 'YYYY-MM' : 'YYYY'}
                      </span>
                    </label>

                    {uploadMode === 'monthly' ? (
                      <input
                        style={{
                          ...s.input,
                          borderColor: period && !/^\d{4}-\d{2}$/.test(period)
                            ? 'var(--red)' : 'var(--border)'
                        }}
                        value={period}
                        onChange={e => setPeriod(e.target.value)}
                        placeholder="e.g. 2026-01"
                        maxLength={7}
                      />
                    ) : (
                      <input
                        style={{
                          ...s.input,
                          borderColor: year && !/^\d{4}$/.test(year)
                            ? 'var(--red)' : 'var(--amber)'
                        }}
                        value={year}
                        onChange={e => setYear(e.target.value)}
                        placeholder="e.g. 2025"
                        maxLength={4}
                      />
                    )}

                    <span style={{
                      ...s.fieldHint,
                      color: (uploadMode === 'monthly' && period && !/^\d{4}-\d{2}$/.test(period))
                          || (uploadMode === 'annual'  && year   && !/^\d{4}$/.test(year))
                        ? 'var(--red)' : 'var(--text-muted)'
                    }}>
                      {uploadMode === 'monthly'
                        ? (period && !/^\d{4}-\d{2}$/.test(period)
                            ? '✗ ' + tr('upload_format_hint')
                            : tr('upload_period_hint'))
                        : (year && !/^\d{4}$/.test(year)
                            ? '✗ ' + tr('upload_year_invalid')
                            : tr('upload_year_hint'))}
                    </span>
                  </div>
                </div>
              )}

              {/* TB Type selector */}
              <div style={{ ...s.formRow, marginTop:10 }}>
                <div style={s.fieldWrap}>
                  <label style={s.label}>
                    {tr('upload_tb_type_label')}
                    <span style={{ color:'var(--amber)', marginLeft:4, fontSize:10 }}>
                      ★ {tr('upload_tb_type_hint')}
                    </span>
                  </label>
                  <select style={{ ...s.input, cursor:'pointer' }}
                    value={tbType} onChange={e => setTbType(e.target.value)}>
                    <option value="">{tr('upload_tb_type_unknown')}</option>
                    <option value="pre_closing">{tr('upload_tb_type_pre')}</option>
                    <option value="post_closing">{tr('upload_tb_type_post')}</option>
                  </select>
                  {tbType === 'pre_closing' && (
                    <span style={{ ...s.fieldHint, color:'var(--green)' }}>
                      ✓ {tr('upload_tb_type_tooltip_pre')}
                    </span>
                  )}
                  {tbType === 'post_closing' && (
                    <span style={{ ...s.fieldHint, color:'var(--accent)' }}>
                      ✓ {tr('upload_tb_type_tooltip_post')}
                    </span>
                  )}
                  {!tbType && (
                    <span style={{ ...s.fieldHint, color:'var(--amber)' }}>
                      ⚠ {tr('tb_type_unknown')}
                    </span>
                  )}
                </div>
              </div>

              {/* Upload scope: company vs branch (TB row stores branch_id when set) */}
              <div style={{ ...s.formRow, marginTop:10 }}>
                <div style={s.fieldWrap}>
                  <label style={s.label}>
                    {tr('upload_scope_label')}
                    <span style={{ color:'var(--text-muted)', marginLeft:4, fontSize:10 }}>
                      ({tr('upload_optional')})
                    </span>
                  </label>
                  {branches.length > 0 ? (
                    <>
                      <select
                        style={{ ...s.input, cursor:'pointer' }}
                        value={branchId}
                        onChange={e => setBranchId(e.target.value)}
                      >
                        <option value="">{tr('upload_branch_company_level')}</option>
                        {branches.map(b => (
                          <option key={b.id} value={b.id}>
                            {b.code ? `[${b.code}] ` : ''}{b.name}{b.city ? ` — ${b.city}` : ''}
                          </option>
                        ))}
                      </select>
                      {branchId ? (
                        <span style={{ ...s.fieldHint, color:'var(--accent)' }}>
                          ✓ {tr('upload_branch_linked')}
                        </span>
                      ) : (
                        <span style={{ ...s.fieldHint, color:'var(--text-muted)' }}>
                          {tr('upload_branch_company_hint')}
                        </span>
                      )}
                    </>
                  ) : (
                    <div style={{ ...s.hintBox, marginTop:0, fontSize:12 }}>
                      {tr('upload_no_branches_hint')}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Drop zone */}
            <div
              style={{
                ...s.dropzone,
                ...(dragging ? s.dropDragging : {}),
                ...(file    ? s.dropHasFile  : {}),
              }}
              onDragOver={e => { e.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              onClick={() => !file && inputRef.current?.click()}
            >
              <input ref={inputRef} type="file" accept=".xlsx,.xls,.csv"
                style={{ display:'none' }} onChange={onSelect} />
              {file ? (
                <div style={{ textAlign:'center' }}>
                  <div style={{ fontSize:36, marginBottom:8 }}>📄</div>
                  <div style={{ fontWeight:600, marginBottom:4 }}>{file.name}</div>
                  <div style={{ fontSize:12, color:'var(--text-muted)', marginBottom:12 }}>
                    {(file.size / 1024).toFixed(1)} KB
                  </div>
                  <button style={s.btnOutline}
                    onClick={e => { e.stopPropagation(); clearFile() }}>
                    {tr('upload_remove')}
                  </button>
                </div>
              ) : (
                <div style={{ textAlign:'center' }}>
                  <UpIcon />
                  <div style={{ fontWeight:600, marginTop:12, marginBottom:6 }}>
                    {tr('upload_drop_title')}
                  </div>
                  <div style={{ fontSize:12, color:'var(--text-muted)' }}>
                    {tr('upload_drop_sub')}
                  </div>
                </div>
              )}
            </div>

            {file && (
              <button
                style={{ ...s.btnPrimary, width:'100%', marginTop:12,
                  opacity: processing ? 0.7 : 1 }}
                onClick={handleSubmit}
                disabled={processing || !companyId}>
                {processing ? tr('upload_processing') : tr('upload_submit')}
              </button>
            )}

            {error  && <div style={s.errorBox}>⚠ {error}</div>}
            {result && <ResultPanel result={result} tr={tr} />}
          </div>

          {/* ── RIGHT COLUMN ── */}
          <div>
            <FormatGuide uploadMode={uploadMode} tr={tr} />
            <UploadHistory
              uploads={uploads}
              branches={branches}
              onDelete={openDeleteModal}
              tr={tr}
            />
          </div>

        </div>
      )}
    </div>
  )
}

// ── Result panel ───────────────────────────────────────────────────────────────
function ResultPanel({ result, tr }) {
  const summary    = result.summary         || {}
  const breakdown  = summary.type_breakdown  || {}
  const unknowns   = summary.unknown_accounts || []
  const classRatio = summary.classified_ratio ?? 0
  const periods    = result.generated_periods || []
  const isAnnual   = result.upload_mode === 'annual'

  return (
    <div style={{ marginTop:14 }}>
      <div style={s.statsRow}>
        <MiniStat label={tr('normalized_row_count')} value={result.normalized_row_count} accent="var(--accent)" />
        <MiniStat label="Format"                     value={result.detected_format}       accent="var(--purple)" />
        <MiniStat label={tr('classified_ratio')}
          value={`${Math.round(classRatio * 100)}%`}
          accent={classRatio >= .8 ? 'var(--green)' : 'var(--amber)'} />
        <MiniStat label={tr('tb_balance_diff')}  value={result.diff}
          accent={result.tb_balanced ?? result.balanced ? 'var(--green)' : 'var(--red)'} />
      </div>

      {isAnnual && periods.length > 0 && (
        <div style={{ ...s.card, marginTop:12 }}>
          <div style={s.cardTitle}>{tr('generated_periods')} ({periods.length})</div>
          <div style={{ display:'flex', flexWrap:'wrap', gap:6 }}>
            {periods.map(p => (
              <span key={p} style={{ fontFamily:'monospace', fontSize:11, fontWeight:600,
                background:'var(--accent-dim)', color:'var(--accent)',
                border:'1px solid var(--accent-glow)', borderRadius:5, padding:'3px 10px' }}>
                {p}
              </span>
            ))}
          </div>
        </div>
      )}

      {Object.keys(breakdown).length > 0 && (
        <div style={{ ...s.card, marginTop:12 }}>
          <div style={s.cardTitle}>{tr('type_breakdown')}</div>
          <div style={{ display:'flex', flexDirection:'column', gap:5 }}>
            {Object.entries(breakdown).map(([type, stats]) => (
              <div key={type} style={{ display:'flex', alignItems:'center', gap:10,
                padding:'6px 10px', background:'var(--bg-elevated)', borderRadius:7 }}>
                <TypeBadge type={type} />
                <div style={{ flex:1 }} />
                <span style={{ fontSize:11, color:'var(--text-muted)', fontFamily:'monospace' }}>
                  {stats.count} rows
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {unknowns.length > 0 && (
        <div style={{ ...s.card, marginTop:12, borderColor:'var(--amber)' }}>
          <div style={{ ...s.cardTitle, color:'var(--amber)' }}>
            ⚠ {tr('unknown_accounts')} ({unknowns.length})
          </div>
          <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
            {unknowns.map((u, i) => (
              <div key={i} style={{ fontSize:12, color:'var(--text-secondary)',
                fontFamily:'monospace', padding:'3px 8px',
                background:'var(--bg-elevated)', borderRadius:5 }}>
                <span style={{ color:'var(--amber)' }}>{u.account_code}</span> — {u.account_name}
              </div>
            ))}
          </div>
        </div>
      )}

      {result.preview?.length > 0 && (
        <div style={{ ...s.card, marginTop:12 }}>
          <div style={s.cardTitle}>Preview — first 10 rows</div>
          <div style={{ overflowX:'auto' }}>
            <table style={s.table}>
              <thead>
                <tr>
                  {['account_code','account_name','debit','credit','period',
                    tr('mapped_type'), tr('confidence')].map(h => (
                    <th key={h} style={s.th}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.preview.map((row, i) => {
                  const isLow = (row.confidence || 0) < .5
                  return (
                    <tr key={i} style={{ ...s.tr,
                      background: isLow ? 'rgba(239,68,68,.04)' : 'transparent' }}>
                      <td style={{ ...s.td, color:'var(--accent)', fontFamily:'monospace' }}>
                        {row.account_code}
                      </td>
                      <td style={s.td}>{row.account_name}</td>
                      <td style={{ ...s.td, fontFamily:'monospace', color:'var(--blue)', textAlign:'right' }}>
                        {new Intl.NumberFormat('en-US').format(row.debit || 0)}
                      </td>
                      <td style={{ ...s.td, fontFamily:'monospace', color:'var(--purple)', textAlign:'right' }}>
                        {new Intl.NumberFormat('en-US').format(row.credit || 0)}
                      </td>
                      <td style={{ ...s.td, fontSize:11, color:'var(--text-muted)', fontFamily:'monospace' }}>
                        {row.period || '—'}
                      </td>
                      <td style={s.td}><TypeBadge type={row.mapped_type || 'other'} /></td>
                      <td style={s.td}><ConfBar value={row.confidence || 0} /></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Upload history list ────────────────────────────────────────────────────────
function UploadHistory({ uploads, branches = [], onDelete, tr }) {
  const [expandedId, setExpandedId] = useState(null)

  return (
    <div style={s.card}>
      <div style={s.cardTitle}>{tr('upload_history')} ({uploads.length})</div>
      {uploads.length === 0 ? (
        <div style={s.empty}>{tr('no_uploads_yet')}</div>
      ) : (
        <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
          {uploads.map(u => (
            <div key={u.id} style={{
              background:'var(--bg-elevated)', borderRadius:10, overflow:'hidden',
              border:`1px solid ${u.status === 'error' ? 'var(--red)' : 'var(--border)'}`,
            }}>
              {/* Summary row */}
              <div style={{ display:'flex', alignItems:'center', gap:8,
                padding:'10px 12px', cursor:'pointer',
                transition:'background 0.15s ease',
              }}
                onMouseEnter={e=>e.currentTarget.style.background='rgba(255,255,255,0.025)'}
                onMouseLeave={e=>e.currentTarget.style.background='transparent'}
                onClick={() => setExpandedId(expandedId === u.id ? null : u.id)}>

                <div style={{ flex:1, minWidth:0 }}>
                  <div style={{ fontSize:12, fontWeight:600, color:'var(--text-primary)',
                    overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                    {u.original_filename}
                  </div>
                  <div style={{ fontSize:11, color:'var(--text-muted)', marginTop:2 }}>
                    {u.period || '—'} · {u.record_count ?? '?'} rows · {u.format_detected || '?'}
                    {u.branch_id && (() => {
                      const b = Array.isArray(branches) ? branches.find(x => x.id === u.branch_id) : null
                      return b
                        ? <span style={{ marginLeft:6, color:'var(--accent)',
                            background:'var(--accent-dim)', padding:'1px 6px',
                            borderRadius:4, fontWeight:600 }}>
                            {b.code || b.name}
                          </span>
                        : null
                    })()}
                  </div>
                </div>

                {/* TB Balance badge — debit==credit check only */}
                {u.status === 'ok' && (
                  <span
                    title={u.is_balanced === 'true'
                      ? 'TB balanced: total debits = total credits'
                      : 'TB unbalanced: total debits ≠ total credits'}
                    style={{ fontSize:10, fontWeight:700, padding:'2px 7px',
                      borderRadius:20, flexShrink:0,
                      background: u.is_balanced === 'true' ? 'rgba(34,197,94,.1)' : 'rgba(245,166,35,.1)',
                      color:      u.is_balanced === 'true' ? 'var(--green)'       : 'var(--amber)',
                      border:     `1px solid ${u.is_balanced === 'true' ? 'var(--green)' : 'var(--amber)'}`,
                    }}>
                    {u.is_balanced === 'true' ? tr('tb_balanced') : tr('tb_unbalanced')}
                  </span>
                )}

                {/* Status badge */}
                <span style={{ fontSize:10, fontWeight:700, padding:'2px 8px',
                  borderRadius:20, flexShrink:0,
                  background: u.status === 'ok' ? 'rgba(34,197,94,.1)' : 'rgba(239,68,68,.1)',
                  color:      u.status === 'ok' ? 'var(--green)'       : 'var(--red)',
                  border:     `1px solid ${u.status === 'ok' ? 'var(--green)' : 'var(--red)'}`,
                }}>
                  {u.status}
                </span>

                {/* Delete button */}
                <button
                  style={{ background:'transparent', border:'1px solid var(--border)',
                    color:'var(--text-muted)', borderRadius:6, padding:'3px 8px',
                    fontSize:11, cursor:'pointer', flexShrink:0 }}
                  onClick={e => { e.stopPropagation(); onDelete(u) }}
                  title={tr('delete_upload')}>
                  🗑
                </button>

                <span style={{ color:'var(--text-muted)', fontSize:12 }}>
                  {expandedId === u.id ? '▲' : '▼'}
                </span>
              </div>

              {/* Expanded detail */}
              {expandedId === u.id && (
                <div style={{ padding:'0 12px 12px', borderTop:'1px solid var(--border)' }}>
                  <div style={{ fontSize:11, color:'var(--text-muted)', marginTop:8, lineHeight:2 }}>
                    <span style={{ color:'var(--text-secondary)' }}>ID:</span>{' '}
                    <span style={{ fontFamily:'monospace' }}>{u.id}</span><br />
                    <span style={{ color:'var(--text-secondary)' }}>{tr('uploaded_at')}:</span>{' '}
                    {u.uploaded_at ? new Date(u.uploaded_at).toLocaleString('en-US') : '—'}<br />
                    <span style={{ color:'var(--text-secondary)' }}>{tr('format')}:</span>{' '}
                    {u.format_detected || '—'}<br />
                    {u.branch_id && (() => {
                      const b = Array.isArray(branches) ? branches.find(x => x.id === u.branch_id) : null
                      return b ? <><span style={{ color:'var(--text-secondary)' }}>{tr('branch_name')}:</span>{' '}
                        <span style={{ color:'var(--accent)', fontWeight:600 }}>
                          {b.code ? `[${b.code}] ` : ''}{b.name}
                        </span><br /></> : null
                    })()}
                    {u.tb_type && <>
                      <span style={{ color:'var(--text-secondary)' }}>TB Type:</span>{' '}
                      {tbLabels[u.tb_type] || u.tb_type}<br />
                    </>}
                    {u.total_debit != null && <>
                      <span style={{ color:'var(--text-secondary)' }}>{tr('upload_debit_label')}:</span>{' '}
                      {new Intl.NumberFormat('en-US').format(u.total_debit)}<br />
                    </>}
                    {u.total_credit != null && <>
                      <span style={{ color:'var(--text-secondary)' }}>{tr('upload_credit_label')}:</span>{' '}
                      {new Intl.NumberFormat('en-US').format(u.total_credit)}<br />
                    </>}
                  </div>
                  {u.error_message && (
                    <div style={{ marginTop:8, padding:'8px 10px',
                      background:'rgba(239,68,68,.08)', border:'1px solid var(--red)',
                      borderRadius:7, fontSize:11, color:'var(--red)', lineHeight:1.5 }}>
                      <strong>{tr('error_detail')}:</strong><br />{u.error_message}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Format guide ───────────────────────────────────────────────────────────────
function FormatGuide({ uploadMode, tr }) {
  const rows = uploadMode === 'annual'
    ? [
        { col:'account_code', type:'text',   example:'1010',  desc:'رقم الحساب' },
        { col:'account_name', type:'text',   example:'Cash',  desc:'اسم الحساب' },
        { col:'Jan',          type:'number', example:'50000', desc:'يناير' },
        { col:'Feb…Dec',      type:'number', example:'…',     desc:'باقي الأشهر' },
      ]
    : [
        { col:'account_code', type:'text',   example:'1010',  desc:'رقم الحساب' },
        { col:'account_name', type:'text',   example:'Cash',  desc:'اسم الحساب' },
        { col:'debit',        type:'number', example:'50000', desc:'مدين' },
        { col:'credit',       type:'number', example:'30000', desc:'دائن' },
        { col:'period',       type:'text',   example:'2026-01',desc:'اختياري' },
      ]
  return (
    <div style={{ ...s.card, marginBottom:14 }}>
      <div style={s.cardTitle}>{tr('upload_format_guide')}</div>
      {rows.map(r => (
        <div key={r.col} style={s.fmtRow}>
          <code style={{ fontFamily:'monospace', fontSize:12, color:'var(--accent)' }}>{r.col}</code>
          <span style={{ fontSize:10, color:'var(--purple)', background:'rgba(168,85,247,.1)',
            padding:'2px 6px', borderRadius:4 }}>{r.type}</span>
          <span style={{ fontSize:11, color:'var(--text-muted)', fontFamily:'monospace' }}>{r.example}</span>
          <span style={{ fontSize:11, color:'var(--text-secondary)' }}>{r.desc}</span>
        </div>
      ))}
    </div>
  )
}

// ── Small helpers ──────────────────────────────────────────────────────────────
function MiniStat({ label, value, accent }) {
  return (
    <div style={{ flex:1, background:'var(--bg-surface)', border:'1px solid var(--border)',
      borderTop:`2px solid ${accent}`, borderRadius:10, padding:'11px 13px' }}>
      <div style={{ fontSize:10, color:'var(--text-muted)', textTransform:'uppercase',
        letterSpacing:'.07em', fontWeight:600 }}>{label}</div>
      <div style={{ fontSize:18, fontFamily:'var(--font-display)', fontWeight:700,
        color:accent, marginTop:4 }}>{value}</div>
    </div>
  )
}

function UpIcon() {
  return (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none"
      stroke="var(--text-muted)" strokeWidth="1.5"
      strokeLinecap="round" strokeLinejoin="round"
      style={{ margin:'0 auto', display:'block' }}>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
      <polyline points="17 8 12 3 7 8"/>
      <line x1="12" y1="3" x2="12" y2="15"/>
    </svg>
  )
}

// ── Style constants ────────────────────────────────────────────────────────────
const s = {
  page:       { padding:'36px 40px', maxWidth:1200 },
  header:     { display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:20 },
  title:      { fontFamily:'var(--font-display)', fontSize:26, fontWeight:700, letterSpacing:'-.01em' },
  subtitle:   { color:'var(--text-secondary)', fontSize:13, marginTop:4 },
  notice:     { padding:'12px 16px', background:'var(--amber-dim)', border:'1px solid var(--amber)',
                borderRadius:10, fontSize:13, color:'var(--amber)', marginBottom:20 },
  grid:       { display:'grid', gridTemplateColumns:'1fr 340px', gap:20, alignItems:'start' },
  card:       { background:'var(--bg-surface)', border:'1px solid var(--border)',
                borderRadius:14, padding:'18px 20px', marginBottom:0, transition:'box-shadow 0.2s ease' },
  cardTitle:  { fontFamily:'var(--font-display)', fontSize:11, fontWeight:600,
                color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'.08em', marginBottom:12 },
  hintBox:    { fontSize:12, color:'var(--text-secondary)', background:'var(--bg-elevated)',
                borderRadius:8, padding:'9px 12px', lineHeight:1.5 },
  formRow:    { display:'grid', gridTemplateColumns:'1fr', gap:12 },
  fieldWrap:  { display:'flex', flexDirection:'column', gap:5 },
  fieldHint:  { fontSize:10, color:'var(--text-muted)', marginTop:2 },
  label:      { fontSize:12, color:'var(--text-secondary)', fontWeight:500 },
  input:      { background:'var(--bg-elevated)', border:'1px solid var(--border)',
                borderRadius:8, padding:'8px 12px', color:'var(--text-primary)', fontSize:13 },
  dropzone:   { border:'2px dashed var(--border-bright)', borderRadius:16, padding:'36px 20px',
                textAlign:'center', cursor:'pointer', background:'var(--bg-surface)',
                transition:'all var(--t)', color:'var(--text-secondary)', fontSize:13, marginTop:14 },
  dropDragging: { borderColor:'var(--accent)', background:'var(--accent-dim)',
                  boxShadow:'0 0 30px var(--accent-glow)' },
  dropHasFile:  { cursor:'default', borderColor:'var(--green)', background:'rgba(34,197,94,.04)' },
  btnPrimary: { background:'var(--accent)', color:'#000', border:'none', borderRadius:9,
               padding:'10px 20px', fontSize:13, fontWeight:700, cursor:'pointer',
               fontFamily:'var(--font-display)' },
  btnOutline: { background:'transparent', border:'1px solid var(--border-bright)',
               color:'var(--text-secondary)', borderRadius:6, padding:'5px 14px',
               fontSize:12, cursor:'pointer' },
  errorBox:   { marginTop:12, padding:'12px 16px', background:'rgba(239,68,68,.08)',
               border:'1px solid var(--red)', borderRadius:10, fontSize:13, color:'var(--red)' },
  statsRow:   { display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:8, marginBottom:12 },
  table:      { width:'100%', borderCollapse:'collapse', fontSize:12 },
  th:         { textAlign:'left', padding:'7px 10px', color:'var(--text-muted)',
               borderBottom:'1px solid var(--border)', fontSize:10,
               textTransform:'uppercase', letterSpacing:'.06em', whiteSpace:'nowrap' },
  tr:         { borderBottom:'1px solid var(--border)' },
  td:         { padding:'7px 10px', color:'var(--text-secondary)', fontSize:12 },
  fmtRow:     { display:'grid', gridTemplateColumns:'120px 50px 70px 1fr', gap:8,
               alignItems:'center', padding:'7px 10px',
               background:'var(--bg-elevated)', borderRadius:7, marginBottom:5 },
  empty:      { color:'var(--text-muted)', fontSize:13, textAlign:'center', padding:'14px 0' },
}
