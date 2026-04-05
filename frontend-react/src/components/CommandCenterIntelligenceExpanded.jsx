/**
 * Inline expanded intelligence module for Command Center — no routing.
 * Uses executive payload + buildDrillIntelligence only (no extra fetches).
 */
import { useMemo } from 'react'
import { makeStrictTr } from '../utils/strictI18n.js'
import { strictT as st, strictTParams as stp } from '../utils/strictI18n.js'
import { buildDrillIntelligence } from '../utils/buildDrillIntelligence.js'
import DrillIntelligenceBlock from './DrillIntelligenceBlock.jsx'
import { ExecutiveKpiTrendChart } from './ExecutiveChartBlocks.jsx'
import CmdSparkline from './CmdSparkline.jsx'
import {
  riskScoreFromIntel,
  scoreFromCategory,
  domainStatusFromScore,
} from '../utils/commandCenterIntelScores.js'
import {
  formatCompactForLang,
  formatPctForLang,
  formatSignedPctForLang,
} from '../utils/numberFormat.js'
import CmdServerText from './CmdServerText.jsx'
import { extractKpiTrendPoints } from '../utils/executiveChartModels.js'

const DRILL_THEME = {
  card: 'rgba(15, 23, 42, 0.92)',
  border: 'rgba(71, 85, 105, 0.42)',
  text1: '#f8fafc',
  text2: '#cbd5e1',
  text3: '#94a3b8',
  accent: '#22d3ee',
}

const RATIO_STATUS_CLR = {
  good: '#34d399',
  warning: '#fbbf24',
  risk: '#f87171',
  neutral: '#94a3b8',
}

function drillExtraFromMain(main, kpis, primaryResolution, expenseIntel, decs, health) {
  return {
    drillIntelBundle: {
      kpis,
      primaryResolution,
      expenseIntel,
      decisions: Array.isArray(decs) ? decs : [],
      health,
      realizedCausalItems: main?.realized_causal_items ?? [],
      cashflow: main?.cashflow,
      comparative_intelligence: main?.comparative_intelligence,
    },
    execChartBundle: {
      kpi_block: main.kpi_block,
      cashflow: main.cashflow,
      comparative_intelligence: main.comparative_intelligence,
    },
  }
}

function SupportMetrics({ rows, tr, lang }) {
  if (!rows?.length) return null
  return (
    <div className="cmd-cine-intel-expanded__metrics" role="region" aria-label={st(tr, lang, 'cmd_intel_expanded_metrics_aria')}>
      <div className="cmd-cine-intel-expanded__section-label">{st(tr, lang, 'cmd_intel_expanded_section_metrics')}</div>
      <div className="cmd-cine-intel-expanded__metric-grid">
        {rows.map((r, i) => (
          <div key={`${r.label}-${i}`} className="cmd-cine-intel-expanded__metric-cell">
            <div className="cmd-cine-intel-expanded__metric-label">{r.label}</div>
            <div className="cmd-cine-intel-expanded__metric-val cmd-data-num" dir="ltr">
              {r.current}
            </div>
            {r.delta ? (
              <div className="cmd-cine-intel-expanded__metric-delta cmd-data-num" dir="ltr">
                {r.delta}
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  )
}

function RatioStrip({ ratios, tr, lang }) {
  const entries = Object.entries(ratios || {}).slice(0, 6)
  if (!entries.length) return null
  return (
    <div className="cmd-cine-intel-expanded__ratios" role="region" aria-label={st(tr, lang, 'cmd_intel_expanded_ratios_aria')}>
      <div className="cmd-cine-intel-expanded__section-label">{st(tr, lang, 'cmd_intel_expanded_section_ratios')}</div>
      <div className="cmd-cine-intel-expanded__ratio-row">
        {entries.map(([k, r]) => {
          const rc = RATIO_STATUS_CLR[r?.status] || RATIO_STATUS_CLR.neutral
          return (
            <div key={k} className="cmd-cine-intel-expanded__ratio-chip" style={{ borderLeftColor: rc }}>
              <div className="cmd-cine-intel-expanded__ratio-name">{st(tr, lang, `ratio_${k}`)}</div>
              <div className="cmd-cine-intel-expanded__ratio-val cmd-data-num" dir="ltr" style={{ color: rc }}>
                {r?.value != null ? r.value : '—'}
                {r?.unit ? <span className="cmd-muted-foreign"> {r.unit}</span> : null}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ForecastVisual({ fcData, tr, lang }) {
  if (!fcData?.available) return null
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
  if (!bRev?.point && !bNp?.point) return null
  return (
    <div className="cmd-cine-intel-expanded__fc-visual">
      <div className="cmd-cine-intel-expanded__section-label">{st(tr, lang, 'forecast_next_period')}</div>
      <div className="cmd-cine-intel-expanded__fc-grid">
        <div className="cmd-cine-intel-expanded__fc-cell">
          <div className="cmd-cine-intel-expanded__metric-label">{st(tr, lang, 'revenue')}</div>
          <div className="cmd-cine-intel-expanded__metric-val cmd-data-num" dir="ltr">
            {bRev?.point != null ? formatCompactForLang(Number(bRev.point), lang) : '—'}
          </div>
          {bRev?.confidence != null && Number.isFinite(Number(bRev.confidence)) ? (
            <div className="cmd-cine-intel-expanded__metric-delta cmd-data-num" dir="ltr">
              {st(tr, lang, 'fc_confidence')}: {formatPctForLang(Number(bRev.confidence), 0, lang)}
            </div>
          ) : null}
        </div>
        <div className="cmd-cine-intel-expanded__fc-cell">
          <div className="cmd-cine-intel-expanded__metric-label">{st(tr, lang, 'net_profit')}</div>
          <div className="cmd-cine-intel-expanded__metric-val cmd-data-num" dir="ltr">
            {bNp?.point != null ? formatCompactForLang(Number(bNp.point), lang) : '—'}
          </div>
          {bNp?.confidence != null && Number.isFinite(Number(bNp.confidence)) ? (
            <div className="cmd-cine-intel-expanded__metric-delta cmd-data-num" dir="ltr">
              {st(tr, lang, 'fc_confidence')}: {formatPctForLang(Number(bNp.confidence), 0, lang)}
            </div>
          ) : null}
        </div>
      </div>
      {risk && riskWord ? (
        <div className={`cmd-cine-intel-expanded__risk-tag${risk === 'high' ? ' cmd-cine-intel-expanded__risk-tag--critical' : ''}`}>
          {st(tr, lang, 'forecast_risk')}: {riskWord}
        </div>
      ) : null}
    </div>
  )
}

function AlertsVisual({ alerts, tr, lang }) {
  const list = Array.isArray(alerts) ? alerts.slice(0, 6) : []
  if (!list.length) {
    return <p className="cmd-cine-intel-expanded__empty">{st(tr, lang, 'cmd_intel_expanded_alerts_empty')}</p>
  }
  const hi = list.filter((a) => a.severity === 'high').length
  const mom = hi >= 2 ? -1 : hi === 1 ? 0 : 1
  return (
    <div className="cmd-cine-intel-expanded__alerts-visual" role="region" aria-label={st(tr, lang, 'cmd_intel_expanded_alerts_list_aria')}>
      <div className="cmd-cine-intel-expanded__spark-wrap">
        <CmdSparkline mom={mom} />
      </div>
      <ul className="cmd-cine-intel-expanded__alert-list">
        {list.map((a, i) => (
          <li key={a.id || i} className="cmd-cine-intel-expanded__alert-item">
            <span
              className={`cmd-cine-intel-expanded__sev cmd-cine-intel-expanded__sev--${String(a.severity || 'low')}`}
              aria-hidden
            />
            <CmdServerText lang={lang} tr={tr} as="span">
              {a.title || st(tr, lang, 'alerts_title')}
            </CmdServerText>
          </li>
        ))}
      </ul>
    </div>
  )
}

function ScenariosSnapshot({ main, tr, lang }) {
  const fb = main?.financial_brain
  if (!fb?.available || !fb?.what_changed) return null
  return (
    <div className="cmd-cine-intel-expanded__fb-snap" role="region">
      <div className="cmd-cine-intel-expanded__section-label">{st(tr, lang, 'cmd_intel_expanded_section_snapshot')}</div>
      <p className="cmd-cine-intel-expanded__fb-text">
        <CmdServerText lang={lang} tr={tr} as="span">
          {fb.what_changed}
        </CmdServerText>
      </p>
    </div>
  )
}

function kpiMetricRows(kpis, keys, tr, lang) {
  const rows = []
  for (const key of keys) {
    const row = kpis?.[key]
    if (!row || row.value == null || !Number.isFinite(Number(row.value))) continue
    const label = st(tr, lang, `kpi_label_${key}`)
    const current =
      key === 'net_margin'
        ? formatPctForLang(Number(row.value), 1, lang)
        : formatCompactForLang(Number(row.value), lang)
    let delta = ''
    if (row.mom_pct != null && Number.isFinite(Number(row.mom_pct))) {
      delta = stp(tr, lang, 'cmd_intel_expanded_mom', {
        pct: formatSignedPctForLang(Number(row.mom_pct), 1, lang),
      })
    }
    rows.push({ label, current, delta })
  }
  return rows
}

/**
 * @param {object} p
 * @param {string} p.tileId
 * @param {() => void} p.onClose
 * @param {(k: string, o?: object) => string} p.tr
 * @param {string} p.lang
 * @param {object} p.main
 * @param {object | null} p.intel
 * @param {object[] | null} p.alerts
 * @param {object | null} p.fcData
 * @param {object} p.kpis
 * @param {object[] | null} p.decs
 * @param {object | null} p.primaryResolution
 * @param {object | null} p.expenseIntel
 * @param {number | null} p.health
 */
export default function CommandCenterIntelligenceExpanded({
  tileId,
  onClose,
  tr,
  lang,
  main,
  intel,
  alerts,
  fcData,
  kpis,
  decs,
  primaryResolution,
  expenseIntel,
  health,
}) {
  const t = useMemo(() => makeStrictTr(tr, lang), [tr, lang])

  const { drill, chartKpi, chartHasData, ratioMap, metricKeys, showForecastVisual, showAlertsVisual, showFb } =
    useMemo(() => {
      const extra = drillExtraFromMain(main, kpis, primaryResolution, expenseIntel, decs, health)
      const ratios = intel?.ratios || {}
      const chartData = (kpi) => !!extractKpiTrendPoints(main?.kpi_block, main?.cashflow, kpi)

      if (tileId === 'forecast') {
        const ck = 'revenue'
        return {
          drill: buildDrillIntelligence({
            panelType: 'analysis_tab',
            payload: { tab: 'overview' },
            extra,
            t,
            lang,
          }),
          chartKpi: ck,
          chartHasData: chartData(ck),
          ratioMap: null,
          metricKeys: ['revenue', 'net_profit', 'net_margin', 'expenses'],
          showForecastVisual: true,
          showAlertsVisual: false,
          showFb: false,
        }
      }
      if (tileId === 'alerts') {
        const ck = 'net_margin'
        return {
          drill: buildDrillIntelligence({
            panelType: 'analysis_tab',
            payload: { tab: 'alerts' },
            extra,
            t,
            lang,
          }),
          chartKpi: ck,
          chartHasData: chartData(ck),
          ratioMap: null,
          metricKeys: ['revenue', 'net_profit', 'net_margin'],
          showForecastVisual: false,
          showAlertsVisual: true,
          showFb: false,
        }
      }
      if (tileId === 'scenarios') {
        const ck = 'net_margin'
        return {
          drill: buildDrillIntelligence({ panelType: 'decision', payload: {}, extra, t, lang }),
          chartKpi: ck,
          chartHasData: chartData(ck),
          ratioMap: null,
          metricKeys: ['revenue', 'expenses', 'net_profit', 'net_margin'],
          showForecastVisual: false,
          showAlertsVisual: false,
          showFb: true,
        }
      }
      if (tileId === 'risk') {
        const s = riskScoreFromIntel(intel, alerts || [])
        const ck = 'net_margin'
        return {
          drill: buildDrillIntelligence({
            panelType: 'domain',
            payload: { domain: 'leverage', score: s, status: domainStatusFromScore(s), ratios: ratios.leverage || {} },
            extra,
            t,
            lang,
          }),
          chartKpi: ck,
          chartHasData: chartData(ck),
          ratioMap: ratios.leverage || {},
          metricKeys: ['revenue', 'net_margin', 'expenses'],
          showForecastVisual: false,
          showAlertsVisual: false,
          showFb: false,
        }
      }
      if (tileId === 'liquidity') {
        const s = scoreFromCategory(ratios, 'liquidity')
        const ck = 'cashflow'
        return {
          drill: buildDrillIntelligence({
            panelType: 'domain',
            payload: { domain: 'liquidity', score: s, status: domainStatusFromScore(s), ratios: ratios.liquidity || {} },
            extra,
            t,
            lang,
          }),
          chartKpi: ck,
          chartHasData: chartData(ck),
          ratioMap: ratios.liquidity || {},
          metricKeys: ['revenue', 'net_profit', 'net_margin'],
          showForecastVisual: false,
          showAlertsVisual: false,
          showFb: false,
        }
      }
      if (tileId === 'efficiency') {
        const s = scoreFromCategory(ratios, 'efficiency')
        const ck = 'expenses'
        return {
          drill: buildDrillIntelligence({
            panelType: 'domain',
            payload: { domain: 'efficiency', score: s, status: domainStatusFromScore(s), ratios: ratios.efficiency || {} },
            extra,
            t,
            lang,
          }),
          chartKpi: ck,
          chartHasData: chartData(ck),
          ratioMap: ratios.efficiency || {},
          metricKeys: ['expenses', 'net_margin', 'revenue'],
          showForecastVisual: false,
          showAlertsVisual: false,
          showFb: false,
        }
      }
      const ck = 'revenue'
      return {
        drill: { what: [], why: [], do: [] },
        chartKpi: ck,
        chartHasData: chartData(ck),
        ratioMap: null,
        metricKeys: ['revenue', 'net_profit'],
        showForecastVisual: false,
        showAlertsVisual: false,
        showFb: false,
      }
    }, [tileId, main, kpis, primaryResolution, expenseIntel, decs, health, intel, alerts, t, lang])

  const metricRows = useMemo(() => kpiMetricRows(kpis, metricKeys, tr, lang), [kpis, metricKeys, tr, lang])

  const titleKey = `cmd_intel_tile_${tileId}`

  const ocfRow = useMemo(() => {
    const ocf = main?.cashflow?.operating_cashflow
    if (ocf == null || !Number.isFinite(Number(ocf))) return null
    return {
      label: st(tr, lang, 'cmd_chart_trend_ocf'),
      current: formatCompactForLang(Number(ocf), lang),
      delta: '',
    }
  }, [main, tr, lang])

  const metricsWithOcf = tileId === 'liquidity' && ocfRow ? [ocfRow, ...metricRows] : metricRows

  return (
    <section
      className="cmd-cine-intel-expanded"
      aria-label={stp(tr, lang, 'cmd_intel_expanded_aria', { title: st(tr, lang, titleKey) })}
    >
      <header className="cmd-cine-intel-expanded__header">
        <h3 className="cmd-cine-intel-expanded__title">{st(tr, lang, titleKey)}</h3>
        <button type="button" className="cmd-cine-intel-expanded__close" onClick={onClose} aria-label={st(tr, lang, 'close')}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
            <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
          </svg>
        </button>
      </header>

      <div className="cmd-cine-intel-expanded__body">
        {showForecastVisual ? <ForecastVisual fcData={fcData} tr={tr} lang={lang} /> : null}
        {showAlertsVisual ? <AlertsVisual alerts={alerts} tr={tr} lang={lang} /> : null}
        {showFb ? <ScenariosSnapshot main={main} tr={tr} lang={lang} /> : null}

        <div className="cmd-cine-intel-expanded__chart" role="region" aria-label={st(tr, lang, 'cmd_intel_expanded_section_trend')}>
          <div className="cmd-cine-intel-expanded__chart-inner">
            {chartHasData ? (
              <ExecutiveKpiTrendChart
                kpiBlock={main.kpi_block}
                cashflow={main.cashflow}
                kpiType={chartKpi}
                tr={tr}
                lang={lang}
                cinematic
              />
            ) : (
              <p className="cmd-cine-intel-expanded__empty">{st(tr, lang, 'cmd_intel_expanded_chart_empty')}</p>
            )}
          </div>
        </div>

        <SupportMetrics rows={metricsWithOcf} tr={tr} lang={lang} />

        {ratioMap && Object.keys(ratioMap).length ? <RatioStrip ratios={ratioMap} tr={tr} lang={lang} /> : null}

        <DrillIntelligenceBlock
          what={drill.what}
          why={drill.why}
          tr={tr}
          lang={lang}
          theme={DRILL_THEME}
          {...{ do: drill.do }}
        />

        {!drill.what.length && !drill.why.length && !drill.do.length ? (
          <p className="cmd-cine-intel-expanded__empty">{st(tr, lang, 'cmd_intel_expanded_drill_empty')}</p>
        ) : null}
      </div>
    </section>
  )
}
