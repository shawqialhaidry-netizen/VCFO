/**
 * Unified executive intelligence layer: forecast panel + smart tiles + compact profit path card.
 * Sits as one connected workspace (no separate lower bridge strip).
 */
import { strictT as st, strictTParams as stp } from '../utils/strictI18n.js'
import {
  formatCompactForLang,
  formatCompactSignedForLang,
  formatPctForLang,
  formatSignedPctForLang,
} from '../utils/numberFormat.js'
import CommandCenterIntelligenceGrid from './CommandCenterIntelligenceGrid.jsx'
import { ExecutiveProfitBridgeChart } from './ExecutiveChartBlocks.jsx'

const BRIDGE_STEPS = [
  { bridgeKey: 'revenue_change', labelKey: 'sfl_bridge_revenue', sense: 'revenue' },
  { bridgeKey: 'cogs_change', labelKey: 'sfl_bridge_cogs', sense: 'cost' },
  { bridgeKey: 'opex_change', labelKey: 'sfl_bridge_opex', sense: 'cost' },
  { bridgeKey: 'operating_profit_change', labelKey: 'sfl_bridge_operating', sense: 'profit' },
  { bridgeKey: 'net_profit_change', labelKey: 'sfl_bridge_net', sense: 'terminal' },
]

function deltaTone(d, sense) {
  if (d == null || !Number.isFinite(Number(d))) return '#94a3b8'
  const n = Number(d)
  if (sense === 'revenue') return n >= 0 ? '#34d399' : '#f87171'
  if (sense === 'cost') return n <= 0 ? '#34d399' : '#f87171'
  if (sense === 'profit' || sense === 'terminal') return n >= 0 ? '#2dd4bf' : '#f87171'
  return '#94a3b8'
}

/**
 * Left column: projections + next-period headline (toggles forecast module).
 */
function ForecastIntelCard({
  fcData,
  forecastReady,
  forecastPrimaryMetric,
  active,
  onToggle,
  tr,
  lang,
}) {
  const bRev = fcData?.scenarios?.base?.revenue?.[0]
  const bNp = fcData?.scenarios?.base?.net_profit?.[0]
  const risk = fcData?.summary?.risk_level
  const rk = risk != null ? String(risk).toLowerCase() : ''
  const riskWord =
    rk === 'high'
      ? st(tr, lang, 'urgency_high')
      : rk === 'medium'
        ? st(tr, lang, 'urgency_medium')
        : rk === 'low'
          ? st(tr, lang, 'urgency_low')
          : null
  const hasFc = fcData?.available && (bRev?.point != null || bNp?.point != null)

  return (
    <button
      type="button"
      className={`cmd-cine-forecast-card${active ? ' cmd-cine-forecast-card--active' : ''}`.trim()}
      onClick={() => onToggle('forecast')}
      aria-expanded={active}
      aria-label={st(tr, lang, 'cmd_intel_mosaic_forecast_aria')}
    >
      <div className="cmd-cine-forecast-card__head">
        <span className="cmd-cine-forecast-card__title">{st(tr, lang, 'cmd_intel_tile_forecast')}</span>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden className="cmd-cine-forecast-card__chev">
          <path d="M10 7l5 5-5 5" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      {hasFc ? (
        <>
          <div className="cmd-cine-forecast-card__grid">
            <div>
              <div className="cmd-cine-forecast-card__k">{st(tr, lang, 'revenue')}</div>
              <div className="cmd-cine-forecast-card__v cmd-data-num" dir="ltr">
                {bRev?.point != null ? formatCompactForLang(Number(bRev.point), lang) : '—'}
              </div>
              {bRev?.confidence != null && Number.isFinite(Number(bRev.confidence)) ? (
                <div className="cmd-cine-forecast-card__conf cmd-data-num" dir="ltr">
                  {formatPctForLang(Number(bRev.confidence), 0, lang)}
                </div>
              ) : null}
            </div>
            <div>
              <div className="cmd-cine-forecast-card__k">{st(tr, lang, 'net_profit')}</div>
              <div className="cmd-cine-forecast-card__v cmd-data-num" dir="ltr">
                {bNp?.point != null ? formatCompactForLang(Number(bNp.point), lang) : '—'}
              </div>
            </div>
          </div>
          {risk && riskWord ? (
            <div className={`cmd-cine-forecast-card__risk${risk === 'high' ? ' cmd-cine-forecast-card__risk--hi' : ''}`.trim()}>
              {st(tr, lang, 'forecast_risk')}: {riskWord}
            </div>
          ) : null}
        </>
      ) : (
        <p className="cmd-cine-forecast-card__empty">
          {forecastReady
            ? st(tr, lang, 'cmd_intel_mosaic_forecast_loading')
            : forecastPrimaryMetric
              ? stp(tr, lang, 'cmd_intel_tile_forecast_value_line', { v: forecastPrimaryMetric })
              : st(tr, lang, 'cmd_secondary_fc_empty')}
        </p>
      )}
      <div className="cmd-cine-forecast-card__foot">{st(tr, lang, 'cmd_intel_mosaic_forecast_tap')}</div>
    </button>
  )
}

/**
 * Single-row profit path summary; expands full bridge inline on click.
 */
function ProfitBridgeCompactCard({ bridge, active, onToggle, tr, lang }) {
  if (!bridge || typeof bridge !== 'object') return null
  const rows = BRIDGE_STEPS.map((s) => {
    const blk = bridge[s.bridgeKey] || {}
    return { ...s, delta: blk.delta, delta_pct: blk.delta_pct }
  }).filter((r) => r.delta != null && Number.isFinite(Number(r.delta)))
  if (rows.length < 2) return null

  const sub =
    bridge.latest_period && bridge.previous_period
      ? st(tr, lang, 'sfl_period_compare', {
          from: String(bridge.previous_period).slice(0, 7),
          to: String(bridge.latest_period).slice(0, 7),
        })
      : null

  return (
    <button
      type="button"
      className={`cmd-cine-bridge-compact${active ? ' cmd-cine-bridge-compact--active' : ''}`.trim()}
      onClick={() => onToggle('profit_bridge')}
      aria-expanded={active}
      aria-label={st(tr, lang, 'cmd_intel_mosaic_bridge_aria')}
    >
      <div className="cmd-cine-bridge-compact__head">
        <span className="cmd-cine-bridge-compact__title">{st(tr, lang, 'cmd_p3_profit_path_title')}</span>
        {sub ? <span className="cmd-cine-bridge-compact__sub">{sub}</span> : null}
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden className="cmd-cine-bridge-compact__chev">
          <path d="M10 7l5 5-5 5" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      <div className="cmd-cine-bridge-compact__flow" role="presentation">
        {rows.map((r, i) => (
          <div key={r.bridgeKey} className="cmd-cine-bridge-compact__cell">
            {i > 0 ? <span className="cmd-cine-bridge-compact__arr" aria-hidden /> : null}
            <div className="cmd-cine-bridge-compact__cell-inner">
              <span className="cmd-cine-bridge-compact__lbl">{st(tr, lang, r.labelKey)}</span>
              <span className="cmd-cine-bridge-compact__d cmd-data-num" dir="ltr" style={{ color: deltaTone(r.delta, r.sense) }}>
                {formatCompactSignedForLang(Number(r.delta), lang)}
              </span>
              <span className="cmd-cine-bridge-compact__p cmd-data-num" dir="ltr" style={{ color: deltaTone(r.delta, r.sense) }}>
                {r.delta_pct != null && Number.isFinite(Number(r.delta_pct))
                  ? formatSignedPctForLang(Number(r.delta_pct), 1, lang)
                  : '—'}
              </span>
            </div>
          </div>
        ))}
      </div>
      <div className="cmd-cine-bridge-compact__foot">{st(tr, lang, 'cmd_intel_mosaic_bridge_tap')}</div>
      <div className="cmd-cine-bridge-compact__legend">{st(tr, lang, 'cmd_intel_bridge_flow_legend')}</div>
    </button>
  )
}

/**
 * @param {object} p — mosaic + all {@link CommandCenterIntelligenceGrid} props (forecast fields still passed for hints if needed)
 */
export default function CommandCenterIntelligenceMosaic({
  activeTile = null,
  onToggle,
  main,
  fcData,
  forecastReady,
  forecastPrimaryMetric,
  tr,
  lang,
  alertCount,
  liquidityHint,
  liquidityScore,
  efficiencyScore,
  efficiencyHint,
  riskScore,
  highAlertCount,
  tileDigestSubs = null,
}) {
  const hasStructuredBridge = main?.structured_profit_bridge && typeof main.structured_profit_bridge === 'object'

  return (
    <div className="cmd-cine-intel-mosaic" aria-label={st(tr, lang, 'cmd_intel_mosaic_zone_aria')}>
      <div className="cmd-cine-intel-mosaic__top">
        <ForecastIntelCard
          fcData={fcData}
          forecastReady={forecastReady}
          forecastPrimaryMetric={forecastPrimaryMetric}
          active={activeTile === 'forecast'}
          onToggle={onToggle}
          tr={tr}
          lang={lang}
        />
        <div className="cmd-cine-intel-mosaic__tiles">
          <CommandCenterIntelligenceGrid
            onToggle={onToggle}
            activeTile={activeTile}
            alertCount={alertCount}
            forecastReady={forecastReady}
            forecastPrimaryMetric={forecastPrimaryMetric}
            liquidityHint={liquidityHint}
            liquidityScore={liquidityScore}
            efficiencyScore={efficiencyScore}
            efficiencyHint={efficiencyHint}
            riskScore={riskScore}
            highAlertCount={highAlertCount}
            tr={tr}
            lang={lang}
            omitForecast
            tileDigestSubs={tileDigestSubs}
          />
        </div>
      </div>
      <div className="cmd-cine-intel-mosaic__bridge-row">
        {hasStructuredBridge ? (
          <ProfitBridgeCompactCard
            bridge={main.structured_profit_bridge}
            active={activeTile === 'profit_bridge'}
            onToggle={onToggle}
            tr={tr}
            lang={lang}
          />
        ) : main?.kpi_block ? (
          <button
            type="button"
            className={`cmd-cine-bridge-compact cmd-cine-bridge-compact--chart-fallback${activeTile === 'profit_bridge' ? ' cmd-cine-bridge-compact--active' : ''}`.trim()}
            onClick={() => onToggle('profit_bridge')}
            aria-expanded={activeTile === 'profit_bridge'}
            aria-label={st(tr, lang, 'cmd_intel_mosaic_bridge_aria')}
          >
            <div className="cmd-cine-bridge-compact__head">
              <span className="cmd-cine-bridge-compact__title">{st(tr, lang, 'cmd_p3_profit_path_title')}</span>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden className="cmd-cine-bridge-compact__chev">
                <path d="M10 7l5 5-5 5" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <div className="cmd-cine-bridge-compact__chart-fallback-inner">
              <ExecutiveProfitBridgeChart kpiBlock={main.kpi_block} tr={tr} lang={lang} />
            </div>
            <div className="cmd-cine-bridge-compact__foot">{st(tr, lang, 'cmd_intel_mosaic_bridge_tap')}</div>
            <div className="cmd-cine-bridge-compact__legend">{st(tr, lang, 'cmd_intel_bridge_flow_legend')}</div>
          </button>
        ) : null}
      </div>
    </div>
  )
}
