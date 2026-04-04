/**
 * Latest-period P&L flow from structured_income_statement (truth layer).
 */
import { formatCompactForLang } from '../utils/numberFormat.js'

const ARROW = '→'

function Step({ label, value, lang }) {
  const v =
    value != null && (typeof value === 'number' ? Number.isFinite(value) : true)
      ? formatCompactForLang(Number(value), lang)
      : '—'
  return (
    <div style={{ flex: '1 1 0', minWidth: 56, textAlign: 'center' }}>
      <div
        style={{
          fontSize: 9,
          fontWeight: 800,
          color: 'var(--text-muted)',
          textTransform: 'uppercase',
          letterSpacing: '.06em',
          marginBottom: 4,
          lineHeight: 1.2,
        }}
      >
        {label}
      </div>
      <div className="cmd-data-num" style={{ fontSize: 13, fontWeight: 800, color: '#e8eef5', direction: 'ltr' }}>
        {v}
      </div>
    </div>
  )
}

export default function CommandCenterMiniPnlFlow({ data, tr, lang, titleKey = 'cmd_cc_profit_flow_title' }) {
  const sis = data?.structured_income_statement
  if (!sis || typeof sis !== 'object') return null

  const steps = [
    { k: 'rev', label: tr('sfl_row_revenue'), field: 'revenue' },
    { k: 'cogs', label: tr('sfl_row_cogs'), field: 'cogs' },
    { k: 'opex', label: tr('sfl_row_opex'), field: 'opex' },
    { k: 'op', label: tr('sfl_row_operating_profit'), field: 'operating_profit' },
    { k: 'np', label: tr('sfl_row_net_profit'), field: 'net_profit' },
  ]

  return (
    <div
      style={{
        background: 'var(--bg-panel)',
        border: '1px solid var(--border)',
        borderRadius: 14,
        padding: '14px 12px',
        borderTop: '2px solid rgba(0,212,170,0.28)',
      }}
    >
      <div style={{ fontSize: 10, fontWeight: 800, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 12 }}>
        {tr(titleKey)}
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', justifyContent: 'space-between', gap: 4 }}>
        {steps.map((s, i) => (
          <div key={s.k} style={{ display: 'flex', alignItems: 'flex-end', gap: 4, flex: '1 1 auto' }}>
            {i > 0 ? (
              <span className="cmd-muted-foreign" style={{ fontSize: 12, paddingBottom: 10, opacity: 0.45 }}>
                {ARROW}
              </span>
            ) : null}
            <Step label={s.label} value={sis[s.field]} lang={lang} />
          </div>
        ))}
      </div>
    </div>
  )
}
