/**
 * Statements — Phase 4B: CFO workspace; data from `statement_hierarchy` only.
 */
import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useLang } from '../context/LangContext.jsx'
import {
  StatementHierarchyTree,
  StatementCashOperatingTree,
  cashHierarchyHasOperatingData,
} from '../components/StatementHierarchyTree.jsx'
import { useCompany } from '../context/CompanyContext.jsx'
import { usePeriodScope } from '../context/PeriodScopeContext.jsx'
import { buildAnalysisQuery } from '../utils/buildAnalysisQuery.js'
import { normalizeFinancialTrust } from '../utils/trustNormalization.js'
import '../styles/statements-premium.css'

const API = '/api/v1'
function auth() {
  try {
    const t = JSON.parse(localStorage.getItem('vcfo_auth') || '{}').token
    return t ? { Authorization: `Bearer ${t}` } : {}
  } catch {
    return {}
  }
}

function DataQualityBanner({ validation, tr }) {
  if (!validation) return null
  const { consistent, warnings = [], has_errors, has_info } = validation
  if (consistent === true && !has_info) return null
  const color = has_errors ? 'var(--red)' : 'var(--amber)'
  const bg = has_errors ? 'rgba(248,113,113,0.06)' : 'rgba(251,191,36,0.06)'
  const bdr = has_errors ? 'rgba(248,113,113,0.25)' : 'rgba(251,191,36,0.25)'
  return (
    <div
      style={{
        padding: '8px 16px',
        borderRadius: 10,
        marginBottom: 4,
        background: bg,
        borderWidth: '1px 1px 1px 3px',
        borderStyle: 'solid',
        borderColor: `${bdr} ${bdr} ${bdr} ${color}`,
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: 10,
        maxWidth: 1200,
        marginLeft: 'auto',
        marginRight: 'auto',
      }}
    >
      <span style={{ fontSize: 12 }}>{has_errors ? '⚠' : 'ℹ'}</span>
      <span style={{ fontSize: 10, fontWeight: 800, color, letterSpacing: '.04em' }}>
        {has_errors ? tr('dq_warning_title') : tr('dq_notice_title')}:
      </span>
      {(warnings || []).map((w, i) => (
        <span key={i} style={{ fontSize: 10, color: 'rgba(196,204,214,0.75)' }}>
          · {tr(`dq_${w.code}`)}
        </span>
      ))}
    </div>
  )
}

function statusColor(status) {
  if (status === 'good') return 'var(--accent)'
  if (status === 'warning') return 'var(--amber)'
  if (status === 'risk') return 'var(--red)'
  return 'rgba(196,204,214,0.55)'
}

function StatusBadge({ status, tr }) {
  const color = statusColor(status)
  return (
    <span
      style={{
        fontSize: 9,
        fontWeight: 800,
        padding: '3px 8px',
        borderRadius: 999,
        color,
        background: `${color}14`,
        border: `1px solid ${color}35`,
        textTransform: 'uppercase',
        letterSpacing: '.04em',
        whiteSpace: 'nowrap',
      }}
    >
      {tr(`trust_status_${status || 'unavailable'}`)}
    </span>
  )
}

function StatementsIntegrityPanel({ trust, tab, tr }) {
  if (!trust) return null
  const checks = Array.isArray(trust.checks) ? trust.checks : []
  const warnings = Array.isArray(trust.warnings) ? trust.warnings : []
  const cashWarningKeys = new Set(['cashflow_partial', 'working_capital_unavailable', 'reconciliation_mismatch'])
  const cashWarnings = warnings.filter((item) => cashWarningKeys.has(item.key))
  const overall = trust.overall_status || 'unavailable'
  const overallColor = statusColor(overall)

  return (
    <div
      style={{
        padding: '16px 18px',
        borderRadius: 12,
        border: `1px solid ${overallColor}30`,
        borderLeft: `3px solid ${overallColor}`,
        background: 'linear-gradient(135deg, rgba(22,27,34,0.9) 0%, rgba(13,17,23,0.96) 100%)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginBottom: 12 }}>
        <div>
          <div style={{ fontSize: 11, fontWeight: 800, color: '#fff', letterSpacing: '.08em', textTransform: 'uppercase' }}>
            {tr('trust_integrity_panel_title')}
          </div>
          <div style={{ fontSize: 11, color: 'rgba(196,204,214,0.65)', marginTop: 4 }}>
            {tr('trust_integrity_panel_subtitle')}
          </div>
        </div>
        <StatusBadge status={overall} tr={tr} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 10 }}>
        {checks.map((item) => (
          <div
            key={item.key}
            style={{
              padding: '10px 11px',
              borderRadius: 10,
              border: '1px solid rgba(255,255,255,0.08)',
              background: 'rgba(255,255,255,0.025)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 7 }}>
              <span style={{ fontSize: 11, fontWeight: 750, color: '#fff' }}>
                {tr(item.label_key || `trust_check_${item.key}`)}
              </span>
              <StatusBadge status={item.status} tr={tr} />
            </div>
            <div style={{ fontSize: 11, lineHeight: 1.45, color: 'rgba(196,204,214,0.68)' }}>
              {tr(`trust_check_${item.key}_desc`)}
            </div>
          </div>
        ))}
      </div>

      {warnings.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
          {warnings.map((item) => (
            <span
              key={item.key}
              style={{
                fontSize: 10,
                fontWeight: 700,
                color: statusColor(item.status),
                padding: '4px 8px',
                borderRadius: 999,
                background: `${statusColor(item.status)}12`,
                border: `1px solid ${statusColor(item.status)}30`,
              }}
            >
              {tr(item.label_key || `trust_warning_${item.key}`)}
            </span>
          ))}
        </div>
      )}

      {tab === 'cash' && cashWarnings.length > 0 && (
        <div
          style={{
            marginTop: 12,
            padding: '10px 12px',
            borderRadius: 10,
            border: '1px solid rgba(251,191,36,0.28)',
            background: 'rgba(251,191,36,0.07)',
            color: 'rgba(255,255,255,0.82)',
            fontSize: 11,
            lineHeight: 1.45,
          }}
        >
          <strong style={{ color: 'var(--amber)' }}>{tr('trust_cashflow_warning_title')}:</strong>{' '}
          {cashWarnings.map((item) => tr(item.label_key || `trust_warning_${item.key}`)).join(' · ')}
        </div>
      )}
    </div>
  )
}

export default function Statements() {
  const { tr, lang } = useLang()
  const { selectedId, selectedCompany } = useCompany()
  const { toQueryString: scopeQS, setResolved, isIncompleteCustom, window: win } = usePeriodScope()
  const navigate = useNavigate()
  const location = useLocation()

  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [consolidate, setConsolidate] = useState(false)
  const [err, setErr] = useState(null)
  const [tab, setTab] = useState('income')

  useEffect(() => {
    if (location.state?.focus === 'cashflow') setTab('cash')
    else if (location.state?.focus === 'balance') setTab('balance')
    else if (location.state?.focus === 'income') setTab('income')
  }, [location.state])

  const load = useCallback(async () => {
    if (!selectedId) return
    if (isIncompleteCustom()) return
    const qs = buildAnalysisQuery(scopeQS, { lang, window: win, consolidate })
    if (qs === null) return
    setLoading(true)
    setErr(null)
    try {
      const r = await fetch(`${API}/analysis/${selectedId}/executive?${qs}`, { headers: auth() })
      if (!r.ok) {
        setErr(`Error ${r.status}`)
        return
      }
      const json = await r.json()
      setData(json)
      setResolved(json.meta?.scope || null)
    } catch (e) {
      setErr(e?.message || 'fetch failed')
    } finally {
      setLoading(false)
    }
  }, [selectedId, lang, consolidate, win, scopeQS, setResolved, isIncompleteCustom])

  useEffect(() => {
    load()
  }, [selectedId, load])

  const d = data?.data || {}
  const meta = data?.meta || {}
  const stmtH = d.statement_hierarchy
  const period =
    stmtH?.period ||
    (Array.isArray(meta.periods) && meta.periods.length ? meta.periods[meta.periods.length - 1] : null) ||
    '—'
  const validation = meta.pipeline_validation
  const health = d.health_score_v2
  const trust = data ? normalizeFinancialTrust({ statements: d.statements, cashflow: d.cashflow }) : null
  const cfOk = tab === 'cash' ? cashHierarchyHasOperatingData(stmtH?.cashflow) : true
  const hasBalanceData = Boolean(stmtH?.balance_sheet?.has_data)

  const healthHue =
    health != null && Number.isFinite(Number(health))
      ? Number(health) >= 75
        ? 'rgba(63,185,80,0.35)'
        : Number(health) >= 50
          ? 'rgba(210,168,75,0.4)'
          : 'rgba(248,113,113,0.35)'
      : 'rgba(255,255,255,0.12)'

  const TABS = [
    { k: 'income', label: tr('stmt_section_is') },
    ...(hasBalanceData ? [{ k: 'balance', label: tr('stmt_section_bs') }] : []),
    { k: 'cash', label: tr('stmt_section_cf') },
  ]

  useEffect(() => {
    if (tab === 'balance' && !hasBalanceData) setTab('income')
  }, [tab, hasBalanceData])

  if (!selectedId) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '60vh',
          flexDirection: 'column',
          gap: 12,
          background: 'var(--bg-void)',
        }}
      >
        <span style={{ fontSize: 14, color: 'var(--text-secondary)' }}>{tr('gen_select_company')}</span>
      </div>
    )
  }

  return (
    <div
      className="stmt-premium statements-page-root"
      style={{
        padding: '20px 24px 32px',
        minHeight: 'calc(100vh - 62px)',
        background: 'radial-gradient(1200px 600px at 50% -10%, rgba(88,166,255,0.06), transparent 55%), var(--bg-void)',
      }}
    >
      <style>{`
        @keyframes spin{to{transform:rotate(360deg)}}
      `}</style>

      <div
        style={{
          maxWidth: 1200,
          margin: '0 auto 18px',
          display: 'flex',
          alignItems: 'flex-end',
          gap: 16,
          flexWrap: 'wrap',
        }}
      >
        <div style={{ flex: '1 1 220px', minWidth: 0 }}>
          <h1
            style={{
              fontSize: 24,
              fontWeight: 800,
              color: '#fff',
              margin: 0,
              letterSpacing: '-0.03em',
              lineHeight: 1.15,
            }}
          >
            {tr('stmt_page_title')}
          </h1>
          <p style={{ fontSize: 12, color: 'rgba(196,204,214,0.65)', margin: '8px 0 0', lineHeight: 1.45 }}>
            {tr('stmt_page_subtitle')}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <div
            style={{
              display: 'flex',
              gap: 2,
              background: 'rgba(255,255,255,0.04)',
              borderRadius: 10,
              padding: 3,
              border: '1px solid rgba(255,255,255,0.07)',
            }}
          >
            {[
              [false, tr('company_uploads')],
              [true, tr('branch_consolidation')],
            ].map(([v, lbl]) => (
              <button
                key={String(v)}
                type="button"
                onClick={() => {
                  setConsolidate(v)
                  setData(null)
                }}
                style={{
                  padding: '7px 14px',
                  fontSize: 11,
                  fontWeight: 600,
                  border: 'none',
                  cursor: 'pointer',
                  borderRadius: 8,
                  background: consolidate === v ? 'rgba(255,255,255,0.1)' : 'transparent',
                  color: consolidate === v ? '#fff' : 'rgba(196,204,214,0.65)',
                }}
              >
                {lbl}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => navigate('/')}
            style={{
              padding: '8px 14px',
              borderRadius: 10,
              border: '1px solid rgba(255,255,255,0.1)',
              background: 'rgba(255,255,255,0.03)',
              color: 'rgba(196,204,214,0.85)',
              fontSize: 11,
              cursor: 'pointer',
            }}
          >
            ← {tr('nav_back_command_center')}
          </button>
          <button
            type="button"
            onClick={load}
            disabled={loading}
            style={{
              padding: '8px 12px',
              borderRadius: 10,
              border: '1px solid rgba(255,255,255,0.1)',
              background: 'rgba(255,255,255,0.03)',
              color: 'rgba(196,204,214,0.85)',
              fontSize: 12,
              cursor: 'pointer',
            }}
          >
            {loading ? (
              <span
                style={{
                  display: 'inline-block',
                  width: 12,
                  height: 12,
                  border: '2px solid rgba(255,255,255,0.15)',
                  borderTopColor: 'var(--accent)',
                  borderRadius: '50%',
                  animation: 'spin .7s linear infinite',
                  verticalAlign: 'middle',
                }}
              />
            ) : (
              '↻'
            )}
          </button>
        </div>
      </div>

      {data && (
        <div
          style={{
            maxWidth: 1200,
            margin: '0 auto 12px',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '8px 14px',
            borderRadius: 10,
            fontSize: 11,
            background: consolidate ? 'rgba(0,212,170,.06)' : 'rgba(255,255,255,.03)',
            border: `1px solid ${consolidate ? 'rgba(0,212,170,.22)' : 'rgba(255,255,255,0.08)'}`,
          }}
        >
          <span style={{ fontWeight: 700, color: consolidate ? 'var(--accent)' : 'rgba(196,204,214,0.65)' }}>
            {tr('data_source')}:
          </span>
          <span style={{ color: 'rgba(196,204,214,0.75)' }}>
            {consolidate ? tr('branch_consolidation') : tr('company_uploads')}
          </span>
        </div>
      )}

      {err && (
        <div
          style={{
            maxWidth: 1200,
            margin: '0 auto 12px',
            padding: '12px 16px',
            background: 'rgba(248,113,113,.08)',
            border: '1px solid rgba(248,113,113,0.35)',
            borderRadius: 10,
            fontSize: 12,
            color: '#fca5a5',
          }}
        >
          {err}
        </div>
      )}

      {loading && !data && (
        <div style={{ maxWidth: 1200, margin: '0 auto', padding: 32, color: 'rgba(196,204,214,0.5)', fontSize: 13 }}>
          {tr('stmt_loading')}
        </div>
      )}

      {data && (
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          <DataQualityBanner validation={validation} tr={tr} />
        </div>
      )}

      {data && stmtH?.available && (
        <div style={{ maxWidth: 1200, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* TOP SUMMARY BAND */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr auto',
              gap: 20,
              alignItems: 'center',
              padding: '18px 22px',
              borderRadius: 12,
              border: '1px solid rgba(255,255,255,0.09)',
              background: 'linear-gradient(135deg, rgba(22,27,34,0.95) 0%, rgba(13,17,23,0.98) 100%)',
              boxShadow: '0 16px 40px rgba(0,0,0,0.28)',
              borderTop: `3px solid ${healthHue}`,
            }}
          >
            <div style={{ minWidth: 0 }}>
              <div
                style={{
                  fontSize: 10,
                  fontWeight: 800,
                  letterSpacing: '0.14em',
                  textTransform: 'uppercase',
                  color: 'rgba(136,166,255,0.75)',
                }}
              >
                {period}
              </div>
              <div
                style={{
                  fontSize: 19,
                  fontWeight: 800,
                  color: '#fff',
                  marginTop: 6,
                  letterSpacing: '-0.02em',
                  lineHeight: 1.2,
                }}
              >
                {selectedCompany?.name || '—'}
              </div>
            </div>
            {health != null && Number.isFinite(Number(health)) && (
              <div style={{ textAlign: 'right', paddingLeft: 16, borderLeft: '1px solid rgba(255,255,255,0.08)' }}>
                <div
                  style={{
                    fontSize: 9,
                    fontWeight: 800,
                    letterSpacing: '0.12em',
                    textTransform: 'uppercase',
                    color: 'rgba(196,204,214,0.45)',
                  }}
                >
                  {tr('health_score')}
                </div>
                <div
                  style={{
                    fontFamily: 'var(--font-mono, monospace)',
                    fontSize: 28,
                    fontWeight: 800,
                    color: '#fff',
                    marginTop: 4,
                    lineHeight: 1,
                  }}
                >
                  {health}
                </div>
              </div>
            )}
          </div>

          <StatementsIntegrityPanel trust={trust} tab={tab} tr={tr} />

          {/* TABS */}
          <div
            style={{
              display: 'inline-flex',
              gap: 0,
              padding: 4,
              borderRadius: 11,
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.08)',
              width: 'fit-content',
            }}
          >
            {TABS.map((t) => (
              <button
                key={t.k}
                type="button"
                onClick={() => setTab(t.k)}
                style={{
                  padding: '10px 22px',
                  borderRadius: 9,
                  border: 'none',
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: '0.04em',
                  cursor: 'pointer',
                  background: tab === t.k ? 'rgba(255,255,255,0.11)' : 'transparent',
                  color: tab === t.k ? '#fff' : 'rgba(196,204,214,0.55)',
                  boxShadow: tab === t.k ? 'inset 0 -2px 0 rgba(136,166,255,0.85)' : 'none',
                }}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* MAIN STATEMENT AREA */}
          <div className="statements-workspace" style={{ width: '100%' }}>
            {tab === 'income' && stmtH.income_statement && (
              <StatementHierarchyTree root={stmtH.income_statement} tr={tr} lang={lang} mode="income" />
            )}

            {tab === 'balance' && hasBalanceData && stmtH.balance_sheet && (
              <StatementHierarchyTree root={stmtH.balance_sheet} tr={tr} lang={lang} mode="balance" />
            )}

            {tab === 'cash' && (
              <div>
                {!cfOk ? (
                  <div
                    style={{
                      padding: '36px 24px',
                      textAlign: 'center',
                      color: 'rgba(196,204,214,0.65)',
                      fontSize: 13,
                      border: '1px solid rgba(255,255,255,0.08)',
                      borderRadius: 12,
                      background: 'linear-gradient(165deg, rgba(22,27,34,0.9) 0%, rgba(13,17,23,0.95) 100%)',
                    }}
                  >
                    {tr('stmt_cf_not_available')}
                  </div>
                ) : (
                  stmtH.cashflow && <StatementCashOperatingTree cashflowRoot={stmtH.cashflow} tr={tr} lang={lang} />
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {data && !stmtH?.available && (
        <div
          style={{
            maxWidth: 1200,
            margin: '48px auto',
            textAlign: 'center',
            color: 'rgba(196,204,214,0.65)',
            fontSize: 14,
          }}
        >
          {tr('stmt_no_data')}
        </div>
      )}
    </div>
  )
}
