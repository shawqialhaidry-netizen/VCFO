/**
 * Compact executive intelligence zone — geometric tiles; expand inline (no routing).
 */
import { strictT as st, strictTParams as stp } from '../utils/strictI18n.js'
import { formatCompactForLang, formatPctForLang, formatSignedPctForLang } from '../utils/numberFormat.js'

function TileChevron({ open }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden
      className={`cmd-cine-intel-tile__chev${open ? ' cmd-cine-intel-tile__chev--open' : ''}`.trim()}
    >
      <path d="M10 7l5 5-5 5" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function domainSignalLine(tr, lang, domain, score) {
  if (score == null || !Number.isFinite(Number(score))) return null
  const s = Number(score)
  const tier = s >= 70 ? 'good' : s >= 45 ? 'warn' : 'risk'
  return st(tr, lang, `domain_signal_${domain}_${tier}`)
}

/**
 * @param {object} p
 * @param {(id: string) => void} p.onToggle — click tile: expand or collapse if same id
 * @param {string | null} [p.activeTile]
 * @param {number} [p.alertCount]
 * @param {boolean} [p.forecastReady]
 * @param {string | null} [p.forecastPrimaryMetric] — headline number for forecast tile
 * @param {string | null} [p.liquidityHint]
 * @param {number | null} [p.liquidityScore]
 * @param {number | null} [p.efficiencyScore]
 * @param {string | null} [p.efficiencyHint]
 * @param {number | null} [p.riskScore]
 * @param {number} [p.highAlertCount]
 * @param {boolean} [p.omitForecast] — forecast lives in mosaic column; hide tile
 * @param {{ alerts?: string, risk?: string, scenarios?: string } | null} [p.tileDigestSubs] — data-sharp one-liners (optional)
 * @param {(k: string, o?: object) => string} p.tr
 * @param {string} p.lang
 */
export default function CommandCenterIntelligenceGrid({
  onToggle,
  activeTile = null,
  alertCount = 0,
  forecastReady = false,
  forecastPrimaryMetric = null,
  liquidityHint = null,
  liquidityScore = null,
  efficiencyScore = null,
  efficiencyHint = null,
  riskScore = null,
  highAlertCount = 0,
  tr,
  lang,
  omitForecast = false,
  tileDigestSubs = null,
}) {
  const forecastTile = {
    id: 'forecast',
    titleKey: 'cmd_intel_tile_forecast',
    sub: forecastPrimaryMetric
      ? stp(tr, lang, 'cmd_intel_tile_forecast_value_line', { v: forecastPrimaryMetric })
      : st(tr, lang, forecastReady ? 'cmd_intel_tile_forecast_sub_ready' : 'cmd_intel_tile_forecast_sub'),
    kpi: forecastPrimaryMetric,
    kpiSuffix100: false,
  }
  const tiles = [
    ...(!omitForecast ? [forecastTile] : []),
    {
      id: 'alerts',
      titleKey: 'cmd_intel_tile_alerts',
      sub:
        tileDigestSubs?.alerts ||
        stp(tr, lang, 'cmd_intel_tile_alerts_sub', { n: String(alertCount) }),
      kpi: alertCount > 0 ? String(alertCount) : null,
      kpiSuffix100: false,
    },
    {
      id: 'scenarios',
      titleKey: 'cmd_intel_tile_scenarios',
      sub: tileDigestSubs?.scenarios || st(tr, lang, 'cmd_intel_tile_scenarios_sub'),
      kpi: null,
      kpiSuffix100: false,
    },
    {
      id: 'risk',
      titleKey: 'cmd_intel_tile_risk',
      sub:
        tileDigestSubs?.risk ||
        (riskScore != null && Number.isFinite(Number(riskScore))
          ? stp(tr, lang, 'cmd_intel_tile_risk_sub', {
              score: String(Math.round(Number(riskScore))),
              hi: String(highAlertCount),
            })
          : st(tr, lang, 'cmd_intel_tile_risk_sub_na')),
      kpi: riskScore != null && Number.isFinite(Number(riskScore)) ? String(Math.round(Number(riskScore))) : null,
      kpiSuffix100: true,
    },
    {
      id: 'liquidity',
      titleKey: 'cmd_intel_tile_liquidity',
      sub:
        domainSignalLine(tr, lang, 'liquidity', liquidityScore) ||
        liquidityHint ||
        st(tr, lang, 'cmd_intel_tile_liquidity_sub'),
      kpi: liquidityScore != null && Number.isFinite(Number(liquidityScore)) ? String(Math.round(Number(liquidityScore))) : null,
      kpiSuffix100: true,
    },
    {
      id: 'efficiency',
      titleKey: 'cmd_intel_tile_efficiency',
      sub:
        domainSignalLine(tr, lang, 'efficiency', efficiencyScore) ||
        efficiencyHint ||
        st(tr, lang, 'cmd_intel_tile_efficiency_sub'),
      kpi: efficiencyScore != null && Number.isFinite(Number(efficiencyScore)) ? String(Math.round(Number(efficiencyScore))) : null,
      kpiSuffix100: true,
    },
  ]

  return (
    <section className="cmd-cine-intel-grid" aria-label={st(tr, lang, 'cmd_intel_zone_aria')}>
      {tiles.map((t) => {
        const isOpen = activeTile === t.id
        return (
          <button
            key={t.id}
            type="button"
            className={`cmd-cine-intel-tile${isOpen ? ' cmd-cine-intel-tile--active' : ''}`.trim()}
            aria-expanded={isOpen}
            onClick={() => onToggle(t.id)}
          >
            <div className="cmd-cine-intel-tile__top">
              <span className="cmd-cine-intel-tile__title">{st(tr, lang, t.titleKey)}</span>
              <TileChevron open={isOpen} />
            </div>
            {t.kpi ? (
              <div className="cmd-cine-intel-tile__kpi cmd-data-num" dir="ltr">
                <span>{t.kpi}</span>
                {t.kpiSuffix100 ? <span className="cmd-cine-intel-tile__kpi-suffix">/100</span> : null}
              </div>
            ) : null}
            <p className="cmd-cine-intel-tile__sub">{t.sub}</p>
          </button>
        )
      })}
    </section>
  )
}

/** Server-authored tile hints (GET /executive intel_tile_hints) — no client metric selection. */
export function liquidityHintLine(hints, tr, lang) {
  if (!hints) return null
  if (
    hints.liquidity_primary === 'ocf' &&
    hints.liquidity_ocf != null &&
    Number.isFinite(Number(hints.liquidity_ocf))
  ) {
    return stp(tr, lang, 'cmd_intel_tile_liquidity_ocf', {
      v: formatCompactForLang(Number(hints.liquidity_ocf), lang),
    })
  }
  if (
    hints.liquidity_primary === 'wc' &&
    hints.liquidity_wc != null &&
    Number.isFinite(Number(hints.liquidity_wc))
  ) {
    return stp(tr, lang, 'cmd_intel_tile_liquidity_wc', {
      v: formatCompactForLang(Number(hints.liquidity_wc), lang),
    })
  }
  return null
}

export function efficiencyHintLine(hints, tr, lang) {
  if (hints?.efficiency_primary === 'exp_mom' && hints.efficiency_expense_mom != null) {
    return stp(tr, lang, 'cmd_intel_tile_efficiency_exp_mom', {
      pct: formatSignedPctForLang(Number(hints.efficiency_expense_mom), 1, lang),
    })
  }
  if (hints?.efficiency_primary === 'net_margin' && hints.efficiency_net_margin_pct != null) {
    return stp(tr, lang, 'cmd_intel_tile_efficiency_nm', {
      pct: formatPctForLang(Number(hints.efficiency_net_margin_pct), 1, lang),
    })
  }
  return null
}
