/**
 * Command Center Phase 1 — compact full-width context (company, window, scope, DQ).
 */
import PeriodSelector from './PeriodSelector.jsx'
import UniversalScopeSelector from './UniversalScopeSelector.jsx'
import { strictT } from '../utils/strictI18n.js'

const T = {
  card: 'var(--bg-elevated)',
  border: 'var(--border)',
  text2: 'var(--text-secondary)',
  text1: '#e8eef5',
  red: 'var(--red)',
  text3: 'var(--text-muted)',
}

function DataQualityInline({ validation, lang, tr }) {
  if (!validation) return null
  const { consistent, warnings = [], has_errors, has_info } = validation
  if (consistent === true && !has_info) return null
  const color = has_errors ? T.red : T.text3
  return (
    <span style={{ display: 'inline-flex', flexWrap: 'wrap', alignItems: 'center', gap: 6, fontSize: 11 }}>
      <span style={{ fontWeight: 800, color, letterSpacing: '.04em' }}>
        {has_errors ? strictT(tr, lang, 'dq_warning_title') : strictT(tr, lang, 'dq_notice_title')}
      </span>
      {warnings.slice(0, 2).map((w, i) => (
        <span key={i} style={{ color: T.text2 }}>
          · {strictT(tr, lang, `dq_${w.code}`)}
        </span>
      ))}
    </span>
  )
}

export default function CommandCenterContextRail({
  tr,
  lang,
  companyName,
  pageTitleKey = 'nav_command_center',
  window,
  setWindow,
  loading,
  consolidate,
  setConsolidate,
  ps,
  psUpdate,
  onScopeApply,
  scopeActiveLabel,
  allPeriods,
  validation,
}) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        padding: '10px 14px',
        borderRadius: 12,
        border: `1px solid ${T.border}`,
        background: 'rgba(255,255,255,0.03)',
        marginBottom: 2,
      }}
    >
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: '8px 14px',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 9, fontWeight: 800, letterSpacing: '.14em', color: T.text3, textTransform: 'uppercase' }}>
            {strictT(tr, lang, pageTitleKey)}
          </div>
          <div style={{ fontSize: 14, fontWeight: 800, color: T.text1, marginTop: 2 }}>{companyName || '—'}</div>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
          <PeriodSelector window={window} setWindow={setWindow} disabled={loading} />
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 0,
              background: T.card,
              border: `1px solid ${T.border}`,
              borderRadius: 8,
              overflow: 'hidden',
            }}
          >
            {[
              { v: false, l: strictT(tr, lang, 'company_uploads') },
              { v: true, l: strictT(tr, lang, 'branch_consolidation') },
            ].map((opt) => (
              <button
                key={String(opt.v)}
                type="button"
                onClick={() => setConsolidate(opt.v)}
                style={{
                  padding: '6px 12px',
                  fontSize: 10,
                  fontWeight: 700,
                  border: 'none',
                  cursor: 'pointer',
                  background: consolidate === opt.v ? 'var(--accent)' : 'transparent',
                  color: consolidate === opt.v ? '#000' : T.text2,
                  whiteSpace: 'nowrap',
                }}
              >
                {opt.l}
              </button>
            ))}
          </div>
          <UniversalScopeSelector
            tr={tr}
            lang={lang}
            ps={ps}
            psUpdate={psUpdate}
            onApply={onScopeApply}
            activeLabel={scopeActiveLabel}
            allPeriods={allPeriods || []}
          />
          {loading ? (
            <div
              style={{
                width: 14,
                height: 14,
                border: `2px solid ${T.border}`,
                borderTopColor: 'var(--accent)',
                borderRadius: '50%',
                animation: 'spin .8s linear infinite',
              }}
            />
          ) : null}
        </div>
      </div>
      {validation ? (
        <div style={{ borderTop: `1px solid ${T.border}`, paddingTop: 8 }}>
          <DataQualityInline validation={validation} lang={lang} tr={tr} />
        </div>
      ) : null}
    </div>
  )
}
