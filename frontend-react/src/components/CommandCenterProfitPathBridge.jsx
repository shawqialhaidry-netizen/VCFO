/**
 * Period profit path — structured_profit_bridge as an interactive horizontal flow strip.
 * Segments: hover tooltip, click → drill; selected state dims siblings.
 */
import { Fragment, useMemo } from 'react'
import { formatCompactSignedForLang, formatSignedPctForLang } from '../utils/numberFormat.js'
import { strictT as st, strictTParams } from '../utils/strictI18n.js'
import {
  buildProfitBridgeSegmentPayload,
  profitBridgeSumAbsDelta,
} from '../utils/profitBridgeSegment.js'

const STEPS = [
  { bridgeKey: 'revenue_change', labelKey: 'sfl_bridge_revenue', sense: 'revenue' },
  { bridgeKey: 'cogs_change', labelKey: 'sfl_bridge_cogs', sense: 'cost' },
  { bridgeKey: 'opex_change', labelKey: 'sfl_bridge_opex', sense: 'cost' },
  { bridgeKey: 'operating_profit_change', labelKey: 'sfl_bridge_operating', sense: 'profit' },
  { bridgeKey: 'net_profit_change', labelKey: 'sfl_bridge_net', sense: 'terminal' },
]

function deltaRgb(d, sense) {
  if (d == null || !Number.isFinite(Number(d))) return '100, 116, 139'
  const n = Number(d)
  if (sense === 'revenue') return n >= 0 ? '52, 211, 153' : '248, 113, 113'
  if (sense === 'cost') return n <= 0 ? '52, 211, 153' : '248, 113, 113'
  if (sense === 'profit' || sense === 'terminal') return n >= 0 ? '45, 212, 191' : '248, 113, 113'
  return '148, 163, 184'
}

function deltaColor(d, sense) {
  const rgb = deltaRgb(d, sense)
  return `rgb(${rgb})`
}

function FlowChevron() {
  return (
    <div className="cmd-p3-flow-os__arrow" aria-hidden>
      <svg width="10" height="16" viewBox="0 0 10 16" fill="none">
        <path
          d="M3 3 L7 8 L3 13"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  )
}

/**
 * @param {object} props
 * @param {Record<string, unknown>} props.bridge
 * @param {Record<string, unknown> | null} [props.variance]
 * @param {Record<string, unknown> | null} [props.varianceMeta]
 * @param {Record<string, unknown> | null} [props.bridgeInterpretation]
 * @param {(payload: Record<string, unknown>) => void} [props.onSegmentClick]
 * @param {string | null} [props.selectedKey] — bridgeKey when drill open
 * @param {(k: string, p?: Record<string, string>) => string} props.tr
 * @param {string} props.lang
 */
export default function CommandCenterProfitPathBridge({
  bridge,
  variance = null,
  varianceMeta = null,
  bridgeInterpretation = null,
  onSegmentClick,
  selectedKey = null,
  tr,
  lang,
}) {
  if (!bridge || typeof bridge !== 'object') return null

  const rows = STEPS.map((s) => {
    const blk = bridge[s.bridgeKey] || {}
    const d = blk.delta
    const dp = blk.delta_pct
    return { ...s, delta: d, delta_pct: dp }
  }).filter((r) => r.delta != null && Number.isFinite(Number(r.delta)))

  const sumAbs = useMemo(() => profitBridgeSumAbsDelta(rows), [rows])
  const maxAbs = Math.max(...rows.map((r) => Math.abs(Number(r.delta))), 1e-9)

  if (rows.length < 2) return null

  const sub =
    bridge.latest_period && bridge.previous_period
      ? st(tr, lang, 'sfl_period_compare', {
          from: String(bridge.previous_period).slice(0, 7),
          to: String(bridge.latest_period).slice(0, 7),
        })
      : null

  const title = st(tr, lang, 'cmd_p3_profit_path_title')
  const stripDimmed = selectedKey != null && selectedKey !== ''

  return (
    <div className="cmd-p3-bridge-card cmd-p3-bridge-card--flow-os">
      <div className="cmd-p3-flow-os">
        <header className="cmd-p3-flow-os__head">
          <h3 className="cmd-p3-flow-os__title">{title}</h3>
          {sub ? <p className="cmd-p3-flow-os__sub">{sub}</p> : null}
        </header>

        <div
          className={`cmd-p3-flow-os__strip${stripDimmed ? ' cmd-p3-flow-os__strip--dim-siblings' : ''}`.trim()}
          role="group"
          aria-label={title}
        >
          {rows.map((r, i) => {
            const w = Math.max(8, Math.round((Math.abs(Number(r.delta)) / maxAbs) * 100))
            const tone = deltaColor(r.delta, r.sense)
            const terminal = r.sense === 'terminal'
            const absSeg = Math.abs(Number(r.delta))
            const weightPct = sumAbs > 0 ? Math.round((absSeg / sumAbs) * 1000) / 10 : 0
            const pctStr =
              r.delta_pct != null && Number.isFinite(Number(r.delta_pct))
                ? formatSignedPctForLang(Number(r.delta_pct), 1, lang)
                : '—'
            const tip = strictTParams(tr, lang, 'cmd_bridge_segment_tooltip', {
              delta: formatCompactSignedForLang(Number(r.delta), lang),
              pct: pctStr,
              weight: String(weightPct),
            })
            const isSelected = selectedKey === r.bridgeKey
            const payload = buildProfitBridgeSegmentPayload({
              bridgeKey: r.bridgeKey,
              labelKey: r.labelKey,
              sense: r.sense,
              delta: r.delta,
              delta_pct: r.delta_pct,
              variance,
              varianceMeta,
              bridgeInterpretation,
              sumAbsDelta: sumAbs,
            })
            return (
              <Fragment key={r.bridgeKey}>
                {i > 0 ? <FlowChevron /> : null}
                <button
                  type="button"
                  className={[
                    'cmd-p3-flow-os__seg',
                    'cmd-p3-flow-os__seg--interactive',
                    terminal ? 'cmd-p3-flow-os__seg--terminal' : '',
                    terminal ? '' : `cmd-p3-flow-os__seg--${r.sense}`,
                    isSelected ? 'cmd-p3-flow-os__seg--selected' : '',
                    stripDimmed && !isSelected ? 'cmd-p3-flow-os__seg--dimmed' : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                  title={tip}
                  aria-pressed={isSelected}
                  aria-label={`${st(tr, lang, r.labelKey)}. ${tip}`}
                  onClick={() => onSegmentClick?.(payload)}
                >
                  <span className="cmd-p3-flow-os__seg-k">{st(tr, lang, r.labelKey)}</span>
                  <span className="cmd-p3-flow-os__seg-v cmd-data-num" style={{ color: tone }}>
                    {formatCompactSignedForLang(Number(r.delta), lang)}
                  </span>
                  {r.delta_pct != null && Number.isFinite(Number(r.delta_pct)) ? (
                    <span className="cmd-p3-flow-os__seg-p cmd-data-num" style={{ color: tone }}>
                      {formatSignedPctForLang(Number(r.delta_pct), 1, lang)}
                    </span>
                  ) : (
                    <span className="cmd-p3-flow-os__seg-p cmd-data-num cmd-p3-flow-os__seg-p--na">—</span>
                  )}
                  <div className="cmd-p3-flow-os__impact" aria-hidden>
                    <span
                      className="cmd-p3-flow-os__impact-fill"
                      style={{
                        width: `${w}%`,
                        background: tone,
                        opacity: terminal ? 0.95 : 0.65,
                      }}
                    />
                  </div>
                </button>
              </Fragment>
            )
          })}
        </div>
      </div>
    </div>
  )
}
