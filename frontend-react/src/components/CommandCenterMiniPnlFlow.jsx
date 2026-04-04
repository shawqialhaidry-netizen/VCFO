/**
 * Latest-period P&L flow from structured_income_statement (truth layer).
 * Optional dual trend (revenue + net profit) from kpi_block.series; directional flow + net emphasis.
 */
import { formatCompactForLang } from '../utils/numberFormat.js'

function normalizeTail(arr, maxLen = 10) {
  const v = (arr || []).filter((x) => x != null && Number.isFinite(Number(x))).slice(-maxLen)
  if (v.length < 2) return null
  const nums = v.map(Number)
  const mn = Math.min(...nums)
  const mx = Math.max(...nums)
  const rng = mx - mn || 1
  return nums.map((n) => (n - mn) / rng)
}

function MiniDualTrendChart({ seriesRev, seriesNp }) {
  const a = normalizeTail(seriesRev)
  const b = normalizeTail(seriesNp)
  if (!a && !b) return null
  const W = 100
  const H = 28
  const pad = 2
  const innerH = H - pad * 2

  const toPoints = (norm) => {
    const n = norm.length
    if (n < 2) return ''
    return norm
      .map((y, i) => {
        const x = (i / (n - 1)) * W
        const py = pad + (1 - y) * innerH
        return `${x.toFixed(1)},${py.toFixed(1)}`
      })
      .join(' ')
  }

  return (
    <svg className="cmd-magic-flow-svg" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden>
      <defs>
        <linearGradient id="cmdFlowTrendFade" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="rgba(148,163,184,0.12)" />
          <stop offset="100%" stopColor="rgba(148,163,184,0)" />
        </linearGradient>
      </defs>
      <rect x="0" y="0" width={W} height={H} fill="url(#cmdFlowTrendFade)" rx="4" />
      {a ? (
        <polyline
          points={toPoints(a)}
          fill="none"
          stroke="rgba(59,158,255,0.75)"
          strokeWidth="1.35"
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      ) : null}
      {b ? (
        <polyline
          points={toPoints(b)}
          fill="none"
          stroke="rgba(0,212,170,0.9)"
          strokeWidth="1.35"
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      ) : null}
    </svg>
  )
}

function FlowNode({ label, value, lang, terminal }) {
  const v =
    value != null && (typeof value === 'number' ? Number.isFinite(value) : true)
      ? formatCompactForLang(Number(value), lang)
      : '—'
  return (
    <div className={`cmd-magic-flow-node${terminal ? ' cmd-magic-flow-node--terminal' : ''}`.trim()}>
      <div className="cmd-magic-flow-node__label">{label}</div>
      <div className="cmd-magic-flow-node__ring">
        <div className="cmd-magic-flow-node__val">{v}</div>
      </div>
    </div>
  )
}

export default function CommandCenterMiniPnlFlow({
  data,
  tr,
  lang,
  titleKey = 'cmd_cc_profit_flow_title',
  seriesRev,
  seriesNp,
}) {
  const sis = data?.structured_income_statement
  if (!sis || typeof sis !== 'object') return null

  const steps = [
    { k: 'rev', label: tr('sfl_row_revenue'), field: 'revenue', terminal: false },
    { k: 'cogs', label: tr('sfl_row_cogs'), field: 'cogs', terminal: false },
    { k: 'opex', label: tr('sfl_row_opex'), field: 'opex', terminal: false },
    { k: 'op', label: tr('sfl_row_operating_profit'), field: 'operating_profit', terminal: false },
    { k: 'np', label: tr('sfl_row_net_profit'), field: 'net_profit', terminal: true },
  ]

  const showTrend = normalizeTail(seriesRev) || normalizeTail(seriesNp)

  return (
    <div className="cmd-magic-flow-card">
      <div className="cmd-magic-flow-title">{tr(titleKey)}</div>
      {showTrend ? <MiniDualTrendChart seriesRev={seriesRev} seriesNp={seriesNp} /> : null}
      <div className="cmd-magic-flow-track">
        <div className="cmd-magic-flow-connector" aria-hidden />
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'flex-end',
            justifyContent: 'space-between',
            gap: 4,
            position: 'relative',
          }}
        >
          {steps.map((s) => (
            <FlowNode key={s.k} label={s.label} value={sis[s.field]} lang={lang} terminal={s.terminal} />
          ))}
        </div>
      </div>
    </div>
  )
}
