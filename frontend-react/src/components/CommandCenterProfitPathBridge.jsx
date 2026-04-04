/**
 * Period profit path — structured_profit_bridge deltas as a directional strip.
 * No new formulas; reads existing bridge + label keys.
 */
import { formatCompactSignedForLang, formatSignedPctForLang } from '../utils/numberFormat.js'
import { strictT as st } from '../utils/strictI18n.js'

const STEPS = [
  { bridgeKey: 'revenue_change', labelKey: 'sfl_bridge_revenue', sense: 'revenue' },
  { bridgeKey: 'cogs_change', labelKey: 'sfl_bridge_cogs', sense: 'cost' },
  { bridgeKey: 'opex_change', labelKey: 'sfl_bridge_opex', sense: 'cost' },
  { bridgeKey: 'operating_profit_change', labelKey: 'sfl_bridge_operating', sense: 'profit' },
  { bridgeKey: 'net_profit_change', labelKey: 'sfl_bridge_net', sense: 'terminal' },
]

function deltaTone(d, sense) {
  if (d == null || !Number.isFinite(Number(d))) return '#64748b'
  const n = Number(d)
  if (sense === 'revenue') return n >= 0 ? 'rgba(52, 211, 153, 0.85)' : 'rgba(248, 113, 113, 0.85)'
  if (sense === 'cost') return n <= 0 ? 'rgba(52, 211, 153, 0.85)' : 'rgba(248, 113, 113, 0.85)'
  if (sense === 'profit' || sense === 'terminal') return n >= 0 ? 'rgba(52, 211, 153, 0.9)' : 'rgba(248, 113, 113, 0.9)'
  return '#94a3b8'
}

function barFill(d, sense) {
  if (d == null || !Number.isFinite(Number(d))) return 'rgba(51, 65, 85, 0.5)'
  const n = Number(d)
  if (sense === 'revenue') return n >= 0 ? 'rgba(59, 158, 255, 0.45)' : 'rgba(59, 158, 255, 0.22)'
  if (sense === 'cost') return n <= 0 ? 'rgba(52, 211, 153, 0.35)' : 'rgba(248, 113, 113, 0.35)'
  if (sense === 'profit') return n >= 0 ? 'rgba(167, 139, 250, 0.4)' : 'rgba(248, 113, 113, 0.28)'
  return n >= 0 ? 'rgba(0, 212, 170, 0.42)' : 'rgba(248, 113, 113, 0.32)'
}

export default function CommandCenterProfitPathBridge({ bridge, tr, lang }) {
  if (!bridge || typeof bridge !== 'object') return null

  const rows = STEPS.map((s) => {
    const blk = bridge[s.bridgeKey] || {}
    const d = blk.delta
    const dp = blk.delta_pct
    return { ...s, delta: d, delta_pct: dp }
  }).filter((r) => r.delta != null && Number.isFinite(Number(r.delta)))

  if (rows.length < 2) return null

  const maxAbs = Math.max(...rows.map((r) => Math.abs(Number(r.delta))), 1e-9)
  const sub =
    bridge.latest_period && bridge.previous_period
      ? `${String(bridge.previous_period).slice(0, 7)} → ${String(bridge.latest_period).slice(0, 7)}`
      : null

  const title = st(tr, lang, 'cmd_p3_profit_path_title')

  return (
    <div className="cmd-p3-bridge-card">
      <div className="cmd-p3-bridge-title">{title}</div>
      {sub ? (
        <div style={{ fontSize: 10, color: '#64748b', marginTop: -6, marginBottom: 14, letterSpacing: '.04em' }}>{sub}</div>
      ) : null}
      <div className="cmd-p3-bridge-track" role="img" aria-label={title}>
        {rows.map((r, i) => (
          <div key={r.bridgeKey} style={{ display: 'contents' }}>
            {i > 0 ? <div className="cmd-p3-bridge-chev" aria-hidden>→</div> : null}
            <div
              className={`cmd-p3-bridge-step${r.sense === 'terminal' ? ' cmd-p3-bridge-step--terminal' : ''}`.trim()}
            >
              <div className="cmd-p3-bridge-step__label">{st(tr, lang, r.labelKey)}</div>
              <div
                className="cmd-p3-bridge-step__bar"
                style={{
                  flexGrow: 0,
                  height: `${Math.max(14, (Math.abs(Number(r.delta)) / maxAbs) * 52)}px`,
                  background: barFill(r.delta, r.sense),
                  border: `1px solid ${deltaTone(r.delta, r.sense)}`,
                }}
              />
              <div className="cmd-p3-bridge-step__val" style={{ color: deltaTone(r.delta, r.sense) }}>
                {formatCompactSignedForLang(Number(r.delta), lang)}
              </div>
              {r.delta_pct != null && Number.isFinite(Number(r.delta_pct)) ? (
                <div className="cmd-p3-bridge-step__pct" style={{ color: deltaTone(r.delta, r.sense) }}>
                  {formatSignedPctForLang(Number(r.delta_pct), 1, lang)}
                </div>
              ) : (
                <div className="cmd-p3-bridge-step__pct" style={{ opacity: 0.4 }}>
                  —
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
