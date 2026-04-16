/**
 * Settings.jsx ï¿½ Plan, account information, and account mapping overrides
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useAuth } from '../context/AuthContext.jsx'
import { useLang } from '../context/LangContext.jsx'
import { useCompany } from '../context/CompanyContext.jsx'

const API = '/api/v1'
const MAPPED_TYPES = ['assets', 'liabilities', 'equity', 'revenue', 'cogs', 'expenses', 'tax', 'other']


export default function Settings() {
  const { authFetch } = useAuth()
  const { tr, lang } = useLang()
  const {
    selectedCompany,
    plan,
    trialDaysLeft,
    trialEndsAt,
    isTrial,
    isTrialExpired,
    selectedId,
    userRole,
  } = useCompany()

  const [overrides, setOverrides] = useState([])
  const [reviewData, setReviewData] = useState(null)
  const [loadingOverrides, setLoadingOverrides] = useState(false)
  const [loadingReview, setLoadingReview] = useState(false)
  const [overrideError, setOverrideError] = useState('')
  const [reviewError, setReviewError] = useState('')
  const [overrideNotice, setOverrideNotice] = useState('')
  const [saving, setSaving] = useState(false)
  const [editId, setEditId] = useState(null)
  const [reviewSearch, setReviewSearch] = useState('')
  const [reviewFilter, setReviewFilter] = useState('review')
  const [reviewSort, setReviewSort] = useState('confidence')
  const [reviewDrafts, setReviewDrafts] = useState({})
  const [resolvedReviewKeys, setResolvedReviewKeys] = useState([])
  const [savingReviewKey, setSavingReviewKey] = useState('')
  const [bulkSelectedKeys, setBulkSelectedKeys] = useState([])
  const [bulkMappedType, setBulkMappedType] = useState('')
  const [bulkSaving, setBulkSaving] = useState(false)
  const [bulkLastResult, setBulkLastResult] = useState(null)
  const [reviewUploads, setReviewUploads] = useState([])
  const [loadingReviewUploads, setLoadingReviewUploads] = useState(false)
  const [selectedReviewUploadId, setSelectedReviewUploadId] = useState('')
  const [createForm, setCreateForm] = useState({
    account_code: '',
    account_name_hint: '',
    mapped_type: 'other',
    reason: '',
  })
  const [editForm, setEditForm] = useState({
    account_name_hint: '',
    mapped_type: 'other',
    reason: '',
  })

  const PLAN_LABEL = {
    trial: tr('plan_trial'),
    active: tr('plan_active'),
    enterprise: tr('plan_enterprise'),
  }

  const planColor = isTrialExpired ? 'var(--red)' : isTrial ? '#fbbf24' : 'var(--accent)'
  const canManageOverrides = userRole === 'owner' || userRole === 'analyst'
  const counts = reviewData?.summary_counts || {}

  const reviewFilterOptions = [
    { value: 'review', label: tr('settings_review_filter_all_review') },
    { value: 'fallback', label: tr('settings_review_filter_fallback') },
    { value: 'low_confidence', label: tr('settings_review_filter_low_confidence') },
    { value: 'override', label: tr('settings_review_filter_override') },
    { value: 'rule', label: tr('settings_review_filter_rule') },
  ]

  const reviewSortOptions = [
    { value: 'confidence', label: tr('settings_review_sort_confidence') },
    { value: 'account_code', label: tr('settings_review_sort_account_code') },
    { value: 'account_name', label: tr('settings_review_sort_account_name') },
    { value: 'mapped_type', label: tr('settings_review_sort_mapped_type') },
  ]

  const sourceLabel = (source) => {
    if (source === 'override') return tr('settings_review_source_override')
    if (source === 'fallback') return tr('settings_review_source_fallback')
    return tr('settings_review_source_rule')
  }

  const displayMappedType = (value) => {
    const raw = String(value || '').trim()
    if (!raw) return '-'
    return tr(`type_${raw}`)
  }

  const reviewRowKey = useCallback((row) => (
    `${String(row?.account_code || '').trim()}|${String(row?.account_name || '').trim()}`
  ), [])

  const getReviewRows = useCallback((data, filter) => {
    if (!data) return []
    if (filter === 'fallback') return data.fallback_accounts || []
    if (filter === 'low_confidence') return data.low_confidence_accounts || []
    if (filter === 'override') return data.override_accounts || []
    if (filter === 'rule') return data.rule_accounts || []
    return data.accounts_needing_review || []
  }, [])

  const filteredReviewRows = useMemo(() => {
    const resolved = new Set(resolvedReviewKeys)
    const rows = getReviewRows(reviewData, reviewFilter).filter((row) => !resolved.has(reviewRowKey(row)))
    const q = reviewSearch.trim().toLowerCase()
    const searched = q
      ? rows.filter((row) => {
          const haystack = [
            row?.account_code,
            row?.account_name,
            row?.mapped_type,
            row?.classification_source,
            row?.match_reason,
          ].map((v) => String(v || '').toLowerCase()).join(' ')
          return haystack.includes(q)
        })
      : rows

    const sorted = [...searched]
    sorted.sort((a, b) => {
      if (reviewSort === 'confidence') {
        return Number(a?.confidence ?? 0) - Number(b?.confidence ?? 0)
      }
      const av = String(a?.[reviewSort] || '').toLowerCase()
      const bv = String(b?.[reviewSort] || '').toLowerCase()
      return av.localeCompare(bv, lang === 'ar' ? 'ar' : lang === 'tr' ? 'tr' : 'en')
    })
    return sorted
  }, [getReviewRows, lang, resolvedReviewKeys, reviewData, reviewFilter, reviewRowKey, reviewSearch, reviewSort])

  const actionableReviewRows = useMemo(() => (
    filteredReviewRows.filter((row) => {
      const source = String(row?.classification_source || '')
      return source !== 'override' && source !== 'rule'
    })
  ), [filteredReviewRows])

  const selectedBulkRows = useMemo(() => {
    const selected = new Set(bulkSelectedKeys)
    return actionableReviewRows.filter((row) => selected.has(reviewRowKey(row)))
  }, [actionableReviewRows, bulkSelectedKeys, reviewRowKey])

  useEffect(() => {
    const visibleKeys = new Set(actionableReviewRows.map((row) => reviewRowKey(row)))
    setBulkSelectedKeys((keys) => keys.filter((key) => visibleKeys.has(key)))
  }, [actionableReviewRows, reviewRowKey])

  const fmtDate = (d) => {
    if (!d) return '-'
    const locale = lang === 'ar' ? 'ar-SA' : lang === 'tr' ? 'tr-TR' : 'en-US'
    return new Date(d).toLocaleDateString(locale, { year: 'numeric', month: 'long', day: 'numeric' })
  }

  const fmtDateTime = (d) => {
    if (!d) return '-'
    const locale = lang === 'ar' ? 'ar-SA' : lang === 'tr' ? 'tr-TR' : 'en-US'
    return new Date(d).toLocaleString(locale)
  }

  const uploadScopeLabel = (upload) => (
    upload?.branch_id
      ? tr('settings_review_scope_branch', { branch_id: upload.branch_id })
      : tr('settings_review_scope_company')
  )

  const uploadOptionLabel = (upload) => [
    upload?.original_filename || '-',
    upload?.period || '-',
    upload?.uploaded_at ? fmtDateTime(upload.uploaded_at) : '-',
    uploadScopeLabel(upload),
  ].join(' | ')

  const loadOverrides = useCallback(async () => {
    if (!selectedId) return
    setLoadingOverrides(true)
    setOverrideError('')
    try {
      const r = await authFetch(`${API}/companies/${selectedId}/account-mapping-overrides`)
      const j = await r.json().catch(() => [])
      if (!r.ok) {
        setOverrideError(j?.detail || `Error ${r.status}`)
        return
      }
      setOverrides(Array.isArray(j) ? j : [])
    } catch (e) {
      setOverrideError(e.message || 'Request failed')
    } finally {
      setLoadingOverrides(false)
    }
  }, [authFetch, selectedId])

  const loadReview = useCallback(async () => {
    if (!selectedId) return
    setLoadingReview(true)
    setReviewError('')
    try {
      const suffix = selectedReviewUploadId ? `?upload_id=${encodeURIComponent(selectedReviewUploadId)}` : ''
      const r = await authFetch(`${API}/companies/${selectedId}/classification-review${suffix}`)
      const j = await r.json().catch(() => ({}))
      if (!r.ok) {
        setReviewError(j?.detail || `Error ${r.status}`)
        setReviewData(null)
        return
      }
      setReviewData(j || null)
      setReviewDrafts({})
      setResolvedReviewKeys([])
      setBulkSelectedKeys([])
      setBulkLastResult(null)
    } catch (e) {
      setReviewError(e.message || 'Request failed')
      setReviewData(null)
    } finally {
      setLoadingReview(false)
    }
  }, [authFetch, selectedId, selectedReviewUploadId])

  const loadReviewUploads = useCallback(async () => {
    if (!selectedId) return
    setLoadingReviewUploads(true)
    try {
      const r = await authFetch(`${API}/uploads?company_id=${encodeURIComponent(selectedId)}`)
      const j = await r.json().catch(() => [])
      if (!r.ok) {
        setReviewUploads([])
        return
      }
      setReviewUploads((Array.isArray(j) ? j : []).filter((u) => u?.status === 'ok'))
    } catch {
      setReviewUploads([])
    } finally {
      setLoadingReviewUploads(false)
    }
  }, [authFetch, selectedId])

  useEffect(() => {
    setSelectedReviewUploadId('')
    setReviewUploads([])
  }, [selectedId])

  useEffect(() => {
    loadOverrides()
    loadReviewUploads()
  }, [loadOverrides, loadReviewUploads])

  useEffect(() => {
    loadReview()
  }, [loadReview])

  const refreshReviewWorkflow = useCallback(() => {
    loadOverrides()
    loadReviewUploads()
    loadReview()
  }, [loadOverrides, loadReview, loadReviewUploads])

  function resetCreateForm() {
    setCreateForm({
      account_code: '',
      account_name_hint: '',
      mapped_type: 'other',
      reason: '',
    })
  }

  function startEdit(row) {
    setEditId(row.id)
    setEditForm({
      account_name_hint: row.account_name_hint || '',
      mapped_type: row.mapped_type || 'other',
      reason: row.reason || '',
    })
    setOverrideError('')
    setOverrideNotice('')
  }

  function cancelEdit() {
    setEditId(null)
    setEditForm({
      account_name_hint: '',
      mapped_type: 'other',
      reason: '',
    })
  }

  async function handleCreateOverride(e) {
    e.preventDefault()
    if (!selectedId || !canManageOverrides) return
    setSaving(true)
    setOverrideError('')
    setOverrideNotice('')
    try {
      const r = await authFetch(`${API}/companies/${selectedId}/account-mapping-overrides`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          account_code: createForm.account_code.trim(),
          account_name_hint: createForm.account_name_hint.trim() || null,
          mapped_type: createForm.mapped_type,
          reason: createForm.reason.trim() || null,
        }),
      })
      const j = await r.json().catch(() => ({}))
      if (!r.ok) {
        setOverrideError(j?.detail || `Error ${r.status}`)
        return
      }
      resetCreateForm()
      setOverrideNotice(tr('settings_mapping_create_ok'))
      refreshReviewWorkflow()
    } catch (e) {
      setOverrideError(e.message || 'Request failed')
    } finally {
      setSaving(false)
    }
  }

  async function handleSaveEdit(id) {
    if (!selectedId || !canManageOverrides) return
    setSaving(true)
    setOverrideError('')
    setOverrideNotice('')
    try {
      const r = await authFetch(`${API}/companies/${selectedId}/account-mapping-overrides/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          account_name_hint: editForm.account_name_hint.trim() || null,
          mapped_type: editForm.mapped_type,
          reason: editForm.reason.trim() || null,
        }),
      })
      const j = await r.json().catch(() => ({}))
      if (!r.ok) {
        setOverrideError(j?.detail || `Error ${r.status}`)
        return
      }
      cancelEdit()
      setOverrideNotice(tr('settings_mapping_update_ok'))
      refreshReviewWorkflow()
    } catch (e) {
      setOverrideError(e.message || 'Request failed')
    } finally {
      setSaving(false)
    }
  }

  async function handleDeleteOverride(id) {
    if (!selectedId || !canManageOverrides) return
    if (!window.confirm(tr('settings_mapping_delete_confirm'))) return
    setSaving(true)
    setOverrideError('')
    setOverrideNotice('')
    try {
      const r = await authFetch(`${API}/companies/${selectedId}/account-mapping-overrides/${id}`, {
        method: 'DELETE',
      })
      if (!r.ok) {
        const j = await r.json().catch(() => ({}))
        setOverrideError(j?.detail || `Error ${r.status}`)
        return
      }
      if (editId === id) cancelEdit()
      setOverrideNotice(tr('settings_mapping_delete_ok'))
      refreshReviewWorkflow()
    } catch (e) {
      setOverrideError(e.message || 'Request failed')
    } finally {
      setSaving(false)
    }
  }

  async function handleInlineSaveOverride(row) {
    if (!selectedId || !canManageOverrides) return
    const key = reviewRowKey(row)
    const mappedType = reviewDrafts[key] || row?.mapped_type || 'other'
    setSavingReviewKey(key)
    setOverrideError('')
    setOverrideNotice('')
    try {
      const r = await authFetch(`${API}/companies/${selectedId}/account-mapping-overrides`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          account_code: String(row?.account_code || '').trim(),
          account_name_hint: String(row?.account_name || '').trim() || null,
          mapped_type: mappedType,
          reason: row?.classification_source === 'fallback'
            ? tr('settings_review_reason_fallback')
            : tr('settings_review_reason_low_confidence'),
        }),
      })
      const j = await r.json().catch(() => ({}))
      if (!r.ok) {
        setOverrideError(j?.detail || `Error ${r.status}`)
        return
      }
      setOverrides((items) => [j, ...items.filter((item) => item.id !== j.id)])
      setResolvedReviewKeys((keys) => (keys.includes(key) ? keys : [...keys, key]))
      setOverrideNotice(tr('settings_review_inline_saved'))
    } catch (e) {
      setOverrideError(e.message || 'Request failed')
    } finally {
      setSavingReviewKey('')
    }
  }

  function toggleBulkSelection(row, checked) {
    const key = reviewRowKey(row)
    setBulkSelectedKeys((keys) => {
      if (checked) return keys.includes(key) ? keys : [...keys, key]
      return keys.filter((item) => item !== key)
    })
  }

  function selectAllFilteredReviewRows() {
    setBulkSelectedKeys(actionableReviewRows.map((row) => reviewRowKey(row)))
    setBulkLastResult(null)
  }

  function clearBulkSelection() {
    setBulkSelectedKeys([])
    setBulkLastResult(null)
  }

  async function handleBulkSaveOverrides() {
    if (!selectedId || !canManageOverrides || !bulkMappedType || !selectedBulkRows.length) return
    if (selectedBulkRows.length >= 25 && !window.confirm(tr('settings_review_bulk_confirm', { count: selectedBulkRows.length }))) return
    setBulkSaving(true)
    setOverrideError('')
    setOverrideNotice('')
    setBulkLastResult(null)
    let created = 0
    let skipped = 0
    let failed = 0
    const createdKeys = []
    const createdItems = []
    const problemKeys = []

    for (const row of selectedBulkRows) {
      const key = reviewRowKey(row)
      try {
        const r = await authFetch(`${API}/companies/${selectedId}/account-mapping-overrides`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            account_code: String(row?.account_code || '').trim(),
            account_name_hint: String(row?.account_name || '').trim() || null,
            mapped_type: bulkMappedType,
            reason: tr('settings_review_bulk_reason'),
          }),
        })
        const j = await r.json().catch(() => ({}))
        if (r.status === 409) {
          skipped += 1
          problemKeys.push(key)
          continue
        }
        if (!r.ok) {
          failed += 1
          problemKeys.push(key)
          continue
        }
        created += 1
        createdKeys.push(key)
        createdItems.push(j)
      } catch {
        failed += 1
        problemKeys.push(key)
      }
    }

    if (createdItems.length) {
      setOverrides((items) => [
        ...createdItems,
        ...items.filter((item) => !createdItems.some((createdItem) => createdItem.id === item.id)),
      ])
    }
    if (createdKeys.length) {
      setResolvedReviewKeys((keys) => Array.from(new Set([...keys, ...createdKeys])))
    }
    setBulkSelectedKeys((keys) => Array.from(new Set([
      ...keys.filter((key) => !createdKeys.includes(key)),
      ...problemKeys,
    ])))

    const summary = tr('settings_review_bulk_summary', { created, skipped, failed })
    setBulkLastResult({ created, skipped, failed, problemKeys })
    if (failed > 0) setOverrideError(summary)
    else setOverrideNotice(summary)
    setBulkSaving(false)
  }

  const s = {
    page: { maxWidth: 760, margin: '0 auto', padding: '28px 16px' },
    card: {
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-card)',
      padding: '20px 24px',
      marginBottom: 14,
    },
    row: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '10px 0',
      borderBottom: '1px solid rgba(255,255,255,.04)',
    },
    label: { fontSize: 12, color: 'var(--text-muted)' },
    value: { fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' },
    input: {
      width: '100%',
      padding: '8px 10px',
      borderRadius: 8,
      border: '1px solid var(--border)',
      background: 'var(--bg-elevated)',
      color: 'var(--text-primary)',
      fontSize: 13,
      boxSizing: 'border-box',
      outline: 'none',
    },
    select: {
      width: '100%',
      padding: '8px 10px',
      borderRadius: 8,
      border: '1px solid var(--border)',
      background: 'var(--bg-elevated)',
      color: 'var(--text-primary)',
      fontSize: 13,
      boxSizing: 'border-box',
      outline: 'none',
    },
    textarea: {
      width: '100%',
      minHeight: 72,
      padding: '8px 10px',
      borderRadius: 8,
      border: '1px solid var(--border)',
      background: 'var(--bg-elevated)',
      color: 'var(--text-primary)',
      fontSize: 13,
      boxSizing: 'border-box',
      outline: 'none',
      resize: 'vertical',
    },
    btnAccent: {
      padding: '8px 16px',
      borderRadius: 8,
      border: 'none',
      cursor: 'pointer',
      background: 'var(--accent)',
      color: '#000',
      fontWeight: 700,
      fontSize: 12,
    },
    btnGhost: {
      padding: '8px 12px',
      borderRadius: 8,
      border: '1px solid var(--border)',
      background: 'transparent',
      color: 'var(--text-secondary)',
      fontWeight: 600,
      fontSize: 12,
      cursor: 'pointer',
    },
    btnDanger: {
      padding: '8px 12px',
      borderRadius: 8,
      border: '1px solid var(--red)',
      background: 'transparent',
      color: 'var(--red)',
      fontWeight: 700,
      fontSize: 12,
      cursor: 'pointer',
    },
    helper: { fontSize: 11, color: 'var(--text-muted)', marginTop: 4 },
    statGrid: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
      gap: 10,
      marginBottom: 16,
    },
    statCard: {
      border: '1px solid var(--border)',
      borderRadius: 10,
      padding: '12px 14px',
      background: 'var(--bg-elevated)',
    },
    accountCard: {
      border: '1px solid rgba(255,255,255,.06)',
      borderRadius: 12,
      padding: '14px',
      background: 'rgba(255,255,255,.02)',
      marginBottom: 10,
    },
    pill: {
      fontSize: 11,
      fontWeight: 700,
      padding: '3px 8px',
      borderRadius: 999,
      border: '1px solid rgba(255,255,255,.1)',
      background: 'rgba(255,255,255,.04)',
      color: 'var(--text-secondary)',
    },
  }

  function renderAccountRow(row, opts = {}) {
    const showQuickAction = opts.showQuickAction && canManageOverrides
    const rowKey = reviewRowKey(row)
    const showBulkSelect = opts.showBulkSelect && canManageOverrides
    const isBulkSelected = bulkSelectedKeys.includes(rowKey)
    const isBulkProblem = bulkLastResult?.problemKeys?.includes(rowKey)
    const draftMappedType = reviewDrafts[rowKey] || row?.mapped_type || 'other'
    const isSavingInline = savingReviewKey === rowKey
    const source = String(row?.classification_source || '')
    const isFallback = source === 'fallback'
    const confidence = typeof row?.confidence === 'number'
      ? row.confidence.toFixed(2)
      : (row?.confidence ?? '-')
    const pillStyle = {
      ...s.pill,
      color: isFallback ? 'var(--red)' : source === 'override' ? 'var(--accent)' : 'var(--text-secondary)',
      borderColor: isFallback ? 'rgba(248,113,113,.28)' : source === 'override' ? 'rgba(0,212,170,.25)' : 'rgba(255,255,255,.1)',
      background: isFallback ? 'rgba(248,113,113,.08)' : source === 'override' ? 'rgba(0,212,170,.08)' : 'rgba(255,255,255,.04)',
    }
    const accountCardStyle = isBulkProblem
      ? {
          ...s.accountCard,
          borderColor: 'rgba(248,113,113,.35)',
          background: 'rgba(248,113,113,.06)',
        }
      : s.accountCard

    return (
      <div key={`${opts.section || 'review'}-${row.account_code}-${row.account_name}-${row.match_reason}`} style={accountCardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start', marginBottom: 10, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start', minWidth: 0 }}>
            {showBulkSelect && (
              <input
                type="checkbox"
                aria-label={tr('settings_review_select_row')}
                checked={isBulkSelected}
                onChange={(e) => toggleBulkSelection(row, e.target.checked)}
                disabled={bulkSaving}
                style={{ marginTop: 3 }}
              />
            )}
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 14, fontWeight: 800, color: 'var(--text-primary)' }}>
                {String(row.account_code || '-')}
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
                {String(row.account_name || '-')}
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            <span style={pillStyle}>{sourceLabel(source)}</span>
            {isBulkProblem && <span style={{ ...s.pill, color: 'var(--red)', borderColor: 'rgba(248,113,113,.35)', background: 'rgba(248,113,113,.08)' }}>{tr('settings_review_bulk_problem_row')}</span>}
            <span style={s.pill}>{displayMappedType(row.mapped_type)}</span>
            <span style={s.pill}>{tr('settings_review_confidence_value', { value: confidence })}</span>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10, marginBottom: showQuickAction ? 12 : 0 }}>
          <div>
            <div style={s.label}>{tr('mapped_type')}</div>
            <div style={s.value}>{displayMappedType(row.mapped_type)}</div>
          </div>
          <div>
            <div style={s.label}>{tr('settings_review_classification_source')}</div>
            <div style={s.value}>{sourceLabel(source)}</div>
          </div>
          <div>
            <div style={s.label}>{tr('match_reason')}</div>
            <div style={{ ...s.value, fontWeight: 600 }}>{String(row.match_reason || '-')}</div>
          </div>
        </div>

        {showQuickAction && (
          <div style={{ display: 'grid', gridTemplateColumns: 'minmax(170px, 1fr) auto', gap: 10, alignItems: 'end' }}>
            <div>
              <label style={s.label}>{tr('settings_mapping_type')}</label>
              <select
                style={s.select}
                value={draftMappedType}
                onChange={(e) => setReviewDrafts((drafts) => ({ ...drafts, [rowKey]: e.target.value }))}
                disabled={saving || bulkSaving || isSavingInline}
              >
                {MAPPED_TYPES.map((type) => (
                  <option key={type} value={type}>{tr(`type_${type}`)}</option>
                ))}
              </select>
            </div>
            <button
              type="button"
              style={s.btnAccent}
              onClick={() => handleInlineSaveOverride(row)}
              disabled={saving || bulkSaving || isSavingInline}
            >
              {isSavingInline ? '...' : tr('settings_review_save_override')}
            </button>
          </div>
        )}
      </div>
    )
  }

  function renderAccountSection(title, subtitle, rows, opts = {}) {
    return (
      <div style={{ marginBottom: 18 }}>
        <div style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>{title}</div>
          {subtitle && <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{subtitle}</div>}
        </div>
        {!rows?.length ? (
          <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: '4px 0 2px' }}>{tr('settings_review_empty_group')}</div>
        ) : (
          rows.map((row) => renderAccountRow(row, opts))
        )}
      </div>
    )
  }

  return (
    <div style={s.page}>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: 20, fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
          {tr('settings_title')}
        </h1>
      </div>

      <div style={s.card}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 14, flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
              {tr('settings_review_title')}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
              {tr('settings_review_subtitle')}
            </div>
          </div>
          <button type="button" style={s.btnGhost} onClick={refreshReviewWorkflow} disabled={loadingReview || loadingOverrides || saving || bulkSaving}>
            {loadingReview ? tr('settings_mapping_loading') : tr('refresh')}
          </button>
        </div>

        {reviewError && (
          <div
            style={{
              padding: '10px 12px',
              borderRadius: 8,
              marginBottom: 14,
              background: 'rgba(248,113,113,.08)',
              border: '1px solid var(--red)',
              fontSize: 12,
              color: 'var(--red)',
            }}
          >
            {reviewError}
          </div>
        )}

        {reviewData && (
          <>
            <div style={s.statGrid}>
              {[
                [tr('settings_review_need_review'), counts.review_count ?? 0],
                [tr('settings_review_fallback'), counts.fallback_count ?? 0],
                [tr('low_confidence'), counts.low_confidence_count ?? 0],
                [tr('settings_review_overrides'), counts.override_count ?? 0],
                [tr('settings_review_rule_classified'), counts.rule_count ?? 0],
                [tr('classified_ratio'), counts.classified_ratio != null ? `${Math.round((counts.classified_ratio || 0) * 100)}%` : '-'],
              ].map(([label, value]) => (
                <div key={label} style={s.statCard}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>{label}</div>
                  <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--text-primary)' }}>{value}</div>
                </div>
              ))}
            </div>

            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 16 }}>
              {tr('settings_review_upload_context', {
                upload_id: reviewData.upload?.upload_id || '-',
                period: reviewData.upload?.period || '-',
              })}
              {counts.low_confidence_threshold != null ? ` ${tr('settings_review_low_confidence_threshold', { value: counts.low_confidence_threshold })}` : ''}
            </div>

            <div style={{ marginBottom: 16 }}>
              <label style={s.label}>{tr('settings_review_upload_selector')}</label>
              <select
                style={s.select}
                value={selectedReviewUploadId}
                onChange={(e) => setSelectedReviewUploadId(e.target.value)}
                disabled={loadingReview || loadingReviewUploads || bulkSaving}
              >
                <option value="">{tr('settings_review_upload_latest')}</option>
                {reviewUploads.map((upload) => (
                  <option key={upload.id} value={upload.id}>
                    {uploadOptionLabel(upload)}
                  </option>
                ))}
              </select>
              <div style={s.helper}>
                {loadingReviewUploads
                  ? tr('settings_mapping_loading')
                  : tr('settings_review_upload_selector_hint')}
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.4fr) minmax(150px, .8fr) minmax(150px, .8fr)', gap: 10, marginBottom: 16 }}>
              <div>
                <label style={s.label}>{tr('settings_review_search')}</label>
                <input
                  style={s.input}
                  value={reviewSearch}
                  onChange={(e) => setReviewSearch(e.target.value)}
                  placeholder={tr('settings_review_search_placeholder')}
                  disabled={bulkSaving}
                />
              </div>
              <div>
                <label style={s.label}>{tr('settings_review_filter')}</label>
                <select
                  style={s.select}
                  value={reviewFilter}
                  onChange={(e) => setReviewFilter(e.target.value)}
                  disabled={bulkSaving}
                >
                  {reviewFilterOptions.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label style={s.label}>{tr('settings_review_sort')}</label>
                <select
                  style={s.select}
                  value={reviewSort}
                  onChange={(e) => setReviewSort(e.target.value)}
                  disabled={bulkSaving}
                >
                  {reviewSortOptions.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {canManageOverrides && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'minmax(120px, 1fr) auto auto minmax(160px, .9fr) auto', gap: 10, alignItems: 'end' }}>
                  <div>
                    <div style={s.label}>{tr('settings_review_bulk_selected')}</div>
                    <div style={s.value}>{tr('settings_review_bulk_selected_count', { count: selectedBulkRows.length })}</div>
                  </div>
                  <button
                    type="button"
                    style={s.btnGhost}
                    onClick={selectAllFilteredReviewRows}
                    disabled={bulkSaving || !actionableReviewRows.length}
                  >
                    {tr('settings_review_bulk_select_all')}
                  </button>
                  <button
                    type="button"
                    style={s.btnGhost}
                    onClick={clearBulkSelection}
                    disabled={bulkSaving || !bulkSelectedKeys.length}
                  >
                    {tr('settings_review_bulk_clear')}
                  </button>
                  <div>
                    <label style={s.label}>{tr('settings_mapping_type')}</label>
                    <select
                      style={s.select}
                      value={bulkMappedType}
                      onChange={(e) => setBulkMappedType(e.target.value)}
                      disabled={bulkSaving}
                    >
                      <option value="">{tr('settings_review_bulk_type_placeholder')}</option>
                      {MAPPED_TYPES.map((type) => (
                        <option key={type} value={type}>{tr(`type_${type}`)}</option>
                      ))}
                    </select>
                  </div>
                  <button
                    type="button"
                    style={s.btnAccent}
                    onClick={handleBulkSaveOverrides}
                    disabled={bulkSaving || !selectedBulkRows.length || !bulkMappedType}
                  >
                    {bulkSaving ? '...' : tr('settings_review_bulk_save')}
                  </button>
                </div>
                {bulkLastResult && (
                  <div style={{ marginTop: 10, padding: '8px 10px', borderRadius: 8, border: '1px solid rgba(255,255,255,.08)', background: 'rgba(255,255,255,.03)', fontSize: 12, color: 'var(--text-secondary)' }}>
                    <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>
                      {tr('settings_review_bulk_summary', {
                        created: bulkLastResult.created,
                        skipped: bulkLastResult.skipped,
                        failed: bulkLastResult.failed,
                      })}
                    </span>
                    {(bulkLastResult.skipped > 0 || bulkLastResult.failed > 0) && (
                      <span style={{ marginLeft: 8 }}>
                        {tr('settings_review_bulk_recovery_hint')}
                      </span>
                    )}
                  </div>
                )}
              </div>
            )}

            {renderAccountSection(
              tr('settings_review_queue_title'),
              tr('settings_review_queue_subtitle'),
              filteredReviewRows,
              {
                section: reviewFilter,
                showQuickAction: reviewFilter !== 'override' && reviewFilter !== 'rule',
                showBulkSelect: reviewFilter !== 'override' && reviewFilter !== 'rule',
              },
            )}
          </>
        )}

        {!loadingReview && !reviewError && !reviewData && (
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            {tr('settings_review_no_upload')}
          </div>
        )}
      </div>

      <div style={s.card}>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 14 }}>
          {tr('settings_company')}
        </div>
        {[
          { label: tr('company_name'), value: selectedCompany?.name || tr('na_label') },
          { label: tr('currency'), value: selectedCompany?.currency || tr('na_label') },
          { label: tr('industry'), value: selectedCompany?.industry || tr('na_label') },
        ].map(({ label, value }) => (
          <div key={label} style={s.row}>
            <span style={s.label}>{label}</span>
            <span style={s.value}>{value}</span>
          </div>
        ))}
      </div>

      <div style={s.card}>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 14 }}>
          {tr('settings_plan')}
        </div>

        <div style={s.row}>
          <span style={s.label}>Plan</span>
          <span
            style={{
              fontSize: 13,
              fontWeight: 700,
              color: planColor,
              background: `${planColor}15`,
              padding: '2px 10px',
              borderRadius: 5,
              border: `1px solid ${planColor}33`,
            }}
          >
            {PLAN_LABEL[plan] || plan}
            {isTrialExpired && ' (Expired)'}
          </span>
        </div>

        {isTrial && trialEndsAt && (
          <div style={s.row}>
            <span style={s.label}>{tr('settings_trial_ends')}</span>
            <span style={{ ...s.value, color: planColor }}>
              {fmtDate(trialEndsAt)}
              {trialDaysLeft !== null && !isTrialExpired && ` ${tr('settings_trial_short_days_left', { n: trialDaysLeft })}`}
            </span>
          </div>
        )}

        <div style={{ marginTop: 18, padding: '14px 0 2px' }}>
          {isTrialExpired ? (
            <div
              style={{
                padding: '12px 16px',
                borderRadius: 8,
                background: 'rgba(248,113,113,.06)',
                border: '1px solid rgba(248,113,113,.2)',
                fontSize: 12,
                color: 'var(--red)',
                marginBottom: 12,
              }}
            >
              {tr('settings_trial_expired_notice')}
            </div>
          ) : isTrial ? (
            <div
              style={{
                padding: '12px 16px',
                borderRadius: 8,
                background: 'rgba(251,191,36,.06)',
                border: '1px solid rgba(251,191,36,.2)',
                fontSize: 12,
                color: '#fbbf24',
                marginBottom: 12,
              }}
            >
              {trialDaysLeft !== null
                ? tr('settings_trial_days_remaining', { n: trialDaysLeft })
                : tr('settings_trial_active')}
            </div>
          ) : null}
          <a
            href="mailto:sales@vcfo.io"
            style={{
              display: 'inline-block',
              padding: '9px 22px',
              borderRadius: 8,
              background: 'var(--accent)',
              color: '#000',
              fontWeight: 700,
              fontSize: 12,
              textDecoration: 'none',
            }}
          >
            {tr('settings_contact_sales')}
          </a>
        </div>
      </div>

      <div style={s.card}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 14 }}>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
              {tr('settings_mapping_title')}
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
              {tr('settings_mapping_subtitle')}
            </div>
          </div>
          <button type="button" style={s.btnGhost} onClick={loadOverrides} disabled={loadingOverrides || saving}>
            {loadingOverrides ? tr('settings_mapping_loading') : tr('refresh')}
          </button>
        </div>

        {userRole === 'viewer' && (
          <div
            style={{
              padding: '10px 12px',
              borderRadius: 8,
              marginBottom: 14,
              background: 'rgba(150,150,150,.08)',
              border: '1px solid rgba(150,150,150,.2)',
              fontSize: 12,
              color: 'var(--text-muted)',
            }}
          >
            {tr('settings_mapping_view_only')}
          </div>
        )}

        {overrideError && (
          <div
            style={{
              padding: '10px 12px',
              borderRadius: 8,
              marginBottom: 14,
              background: 'rgba(248,113,113,.08)',
              border: '1px solid var(--red)',
              fontSize: 12,
              color: 'var(--red)',
            }}
          >
            {overrideError}
          </div>
        )}

        {overrideNotice && (
          <div
            style={{
              padding: '10px 12px',
              borderRadius: 8,
              marginBottom: 14,
              background: 'rgba(0,212,170,.08)',
              border: '1px solid rgba(0,212,170,.25)',
              fontSize: 12,
              color: 'var(--accent)',
            }}
          >
            {overrideNotice}
          </div>
        )}

        <form onSubmit={handleCreateOverride} style={{ marginBottom: 18 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 10, marginBottom: 10 }}>
            <div>
              <label style={s.label}>{tr('settings_mapping_account_code')}</label>
              <input
                style={s.input}
                value={createForm.account_code}
                onChange={(e) => setCreateForm((f) => ({ ...f, account_code: e.target.value }))}
                placeholder={tr('settings_mapping_account_code_placeholder')}
                disabled={!canManageOverrides || saving}
              />
            </div>
            <div>
              <label style={s.label}>{tr('settings_mapping_type')}</label>
              <select
                style={s.select}
                value={createForm.mapped_type}
                onChange={(e) => setCreateForm((f) => ({ ...f, mapped_type: e.target.value }))}
                disabled={!canManageOverrides || saving}
              >
                {MAPPED_TYPES.map((type) => (
                  <option key={type} value={type}>{tr(`type_${type}`)}</option>
                ))}
              </select>
            </div>
          </div>

          <div style={{ marginBottom: 10 }}>
            <label style={s.label}>{tr('settings_mapping_name_hint')}</label>
            <input
              style={s.input}
              value={createForm.account_name_hint}
              onChange={(e) => setCreateForm((f) => ({ ...f, account_name_hint: e.target.value }))}
              placeholder={tr('settings_mapping_name_hint_placeholder')}
              disabled={!canManageOverrides || saving}
            />
          </div>

          <div style={{ marginBottom: 10 }}>
            <label style={s.label}>{tr('settings_mapping_reason')}</label>
            <textarea
              style={s.textarea}
              value={createForm.reason}
              onChange={(e) => setCreateForm((f) => ({ ...f, reason: e.target.value }))}
              placeholder={tr('settings_mapping_reason_placeholder')}
              disabled={!canManageOverrides || saving}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'center' }}>
            <div style={s.helper}>{tr('settings_mapping_exact_match_note')}</div>
            <button type="submit" style={s.btnAccent} disabled={!canManageOverrides || saving}>
              {saving ? '...' : tr('settings_mapping_add')}
            </button>
          </div>
        </form>

        {!loadingOverrides && overrides.length === 0 && (
          <div style={{ textAlign: 'center', padding: '18px 0 6px', color: 'var(--text-muted)', fontSize: 12 }}>
            {tr('settings_mapping_empty')}
          </div>
        )}

        {overrides.map((row) => {
          const isEditing = editId === row.id
          return (
            <div key={row.id} style={{ borderTop: '1px solid rgba(255,255,255,.06)', paddingTop: 14, marginTop: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start', marginBottom: 8 }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>{row.account_code}</div>
                  {row.account_name_hint && (
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 3 }}>{row.account_name_hint}</div>
                  )}
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      padding: '3px 8px',
                      borderRadius: 999,
                      background: 'rgba(0,212,170,.1)',
                      border: '1px solid rgba(0,212,170,.2)',
                      color: 'var(--accent)',
                    }}
                  >
                    {tr(`type_${row.mapped_type}`)}
                  </span>
                  {canManageOverrides && !isEditing && (
                    <>
                      <button type="button" style={s.btnGhost} onClick={() => startEdit(row)}>{tr('branch_edit')}</button>
                      <button type="button" style={s.btnDanger} onClick={() => handleDeleteOverride(row.id)} disabled={saving}>
                        {tr('branch_delete')}
                      </button>
                    </>
                  )}
                </div>
              </div>

              {row.reason && !isEditing && (
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8 }}>{row.reason}</div>
              )}

              {isEditing && (
                <div style={{ display: 'grid', gap: 10, marginTop: 10 }}>
                  <div>
                    <label style={s.label}>{tr('settings_mapping_type')}</label>
                    <select
                      style={s.select}
                      value={editForm.mapped_type}
                      onChange={(e) => setEditForm((f) => ({ ...f, mapped_type: e.target.value }))}
                      disabled={saving}
                    >
                      {MAPPED_TYPES.map((type) => (
                        <option key={type} value={type}>{tr(`type_${type}`)}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label style={s.label}>{tr('settings_mapping_name_hint')}</label>
                    <input
                      style={s.input}
                      value={editForm.account_name_hint}
                      onChange={(e) => setEditForm((f) => ({ ...f, account_name_hint: e.target.value }))}
                      disabled={saving}
                    />
                  </div>
                  <div>
                    <label style={s.label}>{tr('settings_mapping_reason')}</label>
                    <textarea
                      style={s.textarea}
                      value={editForm.reason}
                      onChange={(e) => setEditForm((f) => ({ ...f, reason: e.target.value }))}
                      disabled={saving}
                    />
                  </div>
                  <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                    <button type="button" style={s.btnGhost} onClick={cancelEdit} disabled={saving}>
                      {tr('branch_cancel')}
                    </button>
                    <button type="button" style={s.btnAccent} onClick={() => handleSaveEdit(row.id)} disabled={saving}>
                      {saving ? '...' : tr('branch_save')}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

