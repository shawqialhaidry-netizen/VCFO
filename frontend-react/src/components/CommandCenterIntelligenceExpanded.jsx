/**
 * Inline expanded intelligence — full mini-workspace per tile (no routing, no new fetches).
 * Layout: summary strip → visual | narrative → action zone.
 */
import { useMemo, useId } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { makeStrictTr } from '../utils/strictI18n.js'
import { strictT as st, strictTParams as stp } from '../utils/strictI18n.js'
import { buildDrillIntelligence } from '../utils/buildDrillIntelligence.js'
import { ExecutiveKpiTrendChart, ExecutiveProfitBridgeChart } from './ExecutiveChartBlocks.jsx'
import CommandCenterProfitPathBridge from './CommandCenterProfitPathBridge.jsx'
import {
  riskScoreFromIntel,
  scoreFromCategory,
  domainStatusFromScore,
} from '../utils/commandCenterIntelScores.js'
import {
  formatCompactForLang,
  formatCompactSignedForLang,
  formatPctForLang,
  formatSignedPctForLang,
} from '../utils/numberFormat.js'
import CmdServerText from './CmdServerText.jsx'
import { extractKpiTrendPoints } from '../utils/executiveChartModels.js'
import { enforceLanguageFinal } from '../utils/enforceLanguageFinal.js'

const CHART = {
  grid: '#1f2937',
  tick: '#94a3b8',
  accent: '#22d3ee',
  green: '#34d399',
  amber: '#fbbf24',
  red: '#f87171',
  violet: '#a78bfa',
}

const RATIO_STATUS_CLR = {
  good: '#34d399',
  warning: '#fbbf24',
  risk: '#f87171',
  neutral: '#64748b',
}

const DOMAIN_KEYS = new Set(['liquidity', 'profitability', 'efficiency', 'leverage', 'growth', 'cross_domain'])

function drillExtraFromMain(main, kpis, primaryResolution, expenseIntel, decs, health, intel) {
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
    analysisRatios: intel?.ratios || {},
  }
}

function scoreBandState(score) {
  if (score == null || !Number.isFinite(Number(score))) return 'neutral'
  const s = Number(score)
  if (s >= 70) return 'good'
  if (s >= 45) return 'warn'
  return 'risk'
}

function parseRatioNumber(r) {
  if (!r || r.value == null) return null
  const n = Number(r.value)
  return Number.isFinite(n) ? n : null
}

function NarrativeColumn({ what, why, do: doLines, tr, lang }) {
  const blocks = [
    { key: 'what', label: st(tr, lang, 'ai_cfo_section_what'), items: what },
    { key: 'why', label: st(tr, lang, 'ai_cfo_section_why'), items: why },
    { key: 'do', label: st(tr, lang, 'ai_cfo_section_do'), items: doLines },
  ].filter((b) => b.items?.length)
  if (!blocks.length) return null
  return (
    <div className="cmd-cine-intel-ws__narrative-inner">
      <div className="cmd-cine-intel-ws__narrative-eyebrow">{st(tr, lang, 'drill_intel_title')}</div>
      {blocks.map((b) => (
        <div key={b.key} className="cmd-cine-intel-ws__narr-block">
          <div className="cmd-cine-intel-ws__narr-label">{b.label}</div>
          <ul className="cmd-cine-intel-ws__narr-list">
            {b.items.map((item, i) => (
              <li key={i}>{enforceLanguageFinal(item.text, lang)}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}

/** Period narrative from {@link buildExecutiveNarrative} — complements drill bullets without replacing them. */
function ExecutiveCausalBlock({ narrative, tr, lang }) {
  if (!narrative || typeof narrative !== 'object') return null
  const wc = Array.isArray(narrative.whatChanged?.lines) ? narrative.whatChanged.lines : []
  const why = Array.isArray(narrative.why?.lines) ? narrative.why.lines : []
  const todo = Array.isArray(narrative.whatToDo?.lines) ? narrative.whatToDo.lines : []
  const blocks = [
    { key: 'wc', label: st(tr, lang, 'cmd_intel_exec_causal_what'), items: wc },
    { key: 'why', label: st(tr, lang, 'cmd_intel_exec_causal_why'), items: why },
    { key: 'do', label: st(tr, lang, 'cmd_intel_exec_causal_do'), items: todo },
  ].filter((b) => b.items.length)
  if (!blocks.length) return null
  return (
    <div className="cmd-cine-intel-ws__exec-causal" role="region" aria-label={st(tr, lang, 'cmd_intel_exec_causal_aria')}>
      <div className="cmd-cine-intel-ws__exec-causal-title">{st(tr, lang, 'cmd_intel_exec_causal_title')}</div>
      {blocks.map((b) => (
        <div key={b.key} className="cmd-cine-intel-ws__exec-causal-block">
          <div className="cmd-cine-intel-ws__exec-causal-label">{b.label}</div>
          <ul className="cmd-cine-intel-ws__exec-causal-list">
            {b.items.map((line, i) => (
              <li key={i}>{enforceLanguageFinal(String(line), lang)}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}

function SummaryStrip({ cards, tr, lang }) {
  if (!cards?.length) return null
  return (
    <div className="cmd-cine-intel-ws__summary" role="region" aria-label={st(tr, lang, 'cmd_intel_ws_summary_aria')}>
      {cards.map((c) => (
        <div
          key={c.id}
          className={`cmd-cine-intel-ws__sum-card cmd-cine-intel-ws__sum-card--${c.state || 'neutral'}`.trim()}
        >
          <div className="cmd-cine-intel-ws__sum-label">{c.label}</div>
          <div className="cmd-cine-intel-ws__sum-value cmd-data-num" dir="ltr">
            {c.value}
          </div>
          {c.hint ? <div className="cmd-cine-intel-ws__sum-hint">{c.hint}</div> : null}
        </div>
      ))}
    </div>
  )
}

function ActionZone({ primary, effect, secondary, tr, lang }) {
  if (!primary && !effect && !secondary) return null
  return (
    <footer className="cmd-cine-intel-ws__action" role="region" aria-label={st(tr, lang, 'cmd_intel_ws_action_aria')}>
      <div className="cmd-cine-intel-ws__action-grid">
        {primary ? (
          <div className="cmd-cine-intel-ws__action-primary">
            <div className="cmd-cine-intel-ws__action-k">{st(tr, lang, 'cmd_intel_ws_action_primary')}</div>
            <p className="cmd-cine-intel-ws__action-text">
              <CmdServerText lang={lang} tr={tr} as="span">
                {primary}
              </CmdServerText>
            </p>
          </div>
        ) : null}
        {effect ? (
          <div className="cmd-cine-intel-ws__action-effect">
            <div className="cmd-cine-intel-ws__action-k">{st(tr, lang, 'impact_expected_label')}</div>
            <p className="cmd-cine-intel-ws__action-text cmd-data-num" dir="ltr">
              {effect}
            </p>
          </div>
        ) : null}
      </div>
      {secondary ? (
        <p className="cmd-cine-intel-ws__action-secondary">
          <CmdServerText lang={lang} tr={tr} as="span">
            {secondary}
          </CmdServerText>
        </p>
      ) : null}
    </footer>
  )
}

function mapRatioToSumState(status) {
  const s = String(status || '').toLowerCase()
  if (s === 'good') return 'good'
  if (s === 'warning') return 'warn'
  if (s === 'risk') return 'risk'
  return 'neutral'
}

function RechartsTooltipBody({ active, payload, label, formatter }) {
  if (!active || !payload?.length) return null
  const row = payload[0]
  const v = row?.value
  const nm = row?.name ?? label
  return (
    <div className="cmd-cine-intel-ws__chart-tip">
      {nm ? <div className="cmd-cine-intel-ws__chart-tip-name">{nm}</div> : null}
      <div className="cmd-cine-intel-ws__chart-tip-val cmd-data-num" dir="ltr">
        {formatter ? formatter(v, row) : v}
      </div>
    </div>
  )
}

function ForecastScenarioBars({ fcData, tr, lang }) {
  const keys = ['base', 'optimistic', 'risk']
  const rows = keys
    .map((k) => {
      const rev = fcData?.scenarios?.[k]?.revenue?.[0]?.point
      const np = fcData?.scenarios?.[k]?.net_profit?.[0]?.point
      return {
        key: k,
        name: st(tr, lang, `cmd_intel_scen_${k}`),
        revenue: rev != null && Number.isFinite(Number(rev)) ? Number(rev) : null,
        profit: np != null && Number.isFinite(Number(np)) ? Number(np) : null,
      }
    })
    .filter((r) => r.revenue != null || r.profit != null)
  if (rows.length < 2) return null
  return (
    <div className="cmd-cine-intel-ws__chart-block">
      <div className="cmd-cine-intel-ws__chart-title">{st(tr, lang, 'cmd_intel_ws_fc_scenario_chart')}</div>
      <div className="cmd-cine-intel-ws__rechart" dir="ltr">
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 5" stroke={CHART.grid} vertical={false} />
            <XAxis dataKey="name" tick={{ fill: CHART.tick, fontSize: 9 }} axisLine={{ stroke: CHART.grid }} tickLine={false} />
            <YAxis
              tick={{ fill: CHART.tick, fontSize: 9 }}
              axisLine={{ stroke: CHART.grid }}
              tickLine={false}
              tickFormatter={(v) => formatCompactForLang(v, lang)}
            />
            <Tooltip
              content={(props) => (
                <RechartsTooltipBody
                  {...props}
                  formatter={(v) => (v != null ? formatCompactForLang(Number(v), lang) : '—')}
                />
              )}
            />
            <Bar dataKey="revenue" name={st(tr, lang, 'revenue')} fill={CHART.accent} radius={[4, 4, 0, 0]} maxBarSize={36} />
            <Bar dataKey="profit" name={st(tr, lang, 'net_profit')} fill={CHART.green} radius={[4, 4, 0, 0]} maxBarSize={36} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

function ForecastTrajectoryChart({ fcData, tr, lang }) {
  const series = fcData?.scenarios?.base?.revenue || []
  const data2 = series
    .map((pt, i) => ({
      step: stp(tr, lang, 'cmd_intel_ws_fc_step', { n: String(i + 1) }),
      rev: pt?.point != null && Number.isFinite(Number(pt.point)) ? Number(pt.point) : null,
    }))
    .filter((d) => d.rev != null)
  if (data2.length < 2) return null
  return (
    <div className="cmd-cine-intel-ws__chart-block">
      <div className="cmd-cine-intel-ws__chart-title">{st(tr, lang, 'cmd_intel_ws_fc_path')}</div>
      <div className="cmd-cine-intel-ws__rechart" dir="ltr">
        <ResponsiveContainer width="100%" height={160}>
          <LineChart data={data2} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 5" stroke={CHART.grid} vertical={false} />
            <XAxis dataKey="step" tick={{ fill: CHART.tick, fontSize: 9 }} axisLine={{ stroke: CHART.grid }} tickLine={false} />
            <YAxis
              tick={{ fill: CHART.tick, fontSize: 9 }}
              axisLine={{ stroke: CHART.grid }}
              tickLine={false}
              tickFormatter={(v) => formatCompactForLang(v, lang)}
            />
            <Tooltip
              content={(props) => (
                <RechartsTooltipBody
                  {...props}
                  formatter={(v) => (v != null ? formatCompactForLang(Number(v), lang) : '—')}
                />
              )}
            />
            <Line type="monotone" dataKey="rev" stroke={CHART.accent} strokeWidth={2} dot={{ r: 3, fill: CHART.accent }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

function SeverityBars({ high, medium, low, tr, lang }) {
  const total = high + medium + low
  if (total === 0) {
    return <p className="cmd-cine-intel-expanded__empty">{st(tr, lang, 'cmd_intel_expanded_alerts_empty')}</p>
  }
  const data = [
    { name: st(tr, lang, 'urgency_high'), n: high, fill: CHART.red },
    { name: st(tr, lang, 'urgency_medium'), n: medium, fill: CHART.amber },
    { name: st(tr, lang, 'urgency_low'), n: low, fill: CHART.accent },
  ].filter((d) => d.n > 0)
  if (!data.length) {
    return <p className="cmd-cine-intel-expanded__empty">{st(tr, lang, 'cmd_intel_expanded_alerts_empty')}</p>
  }
  return (
    <div className="cmd-cine-intel-ws__chart-block">
      <div className="cmd-cine-intel-ws__chart-title">{st(tr, lang, 'cmd_intel_ws_alert_severity')}</div>
      <div className="cmd-cine-intel-ws__rechart" dir="ltr">
        <ResponsiveContainer width="100%" height={120}>
          <BarChart layout="vertical" data={data} margin={{ top: 4, right: 16, left: 4, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 5" stroke={CHART.grid} horizontal={false} />
            <XAxis type="number" allowDecimals={false} tick={{ fill: CHART.tick, fontSize: 9 }} axisLine={{ stroke: CHART.grid }} />
            <YAxis
              type="category"
              dataKey="name"
              width={88}
              tick={{ fill: CHART.tick, fontSize: 9 }}
              axisLine={{ stroke: CHART.grid }}
              tickLine={false}
            />
            <Tooltip content={(props) => <RechartsTooltipBody {...props} formatter={(v) => String(v)} />} />
            <Bar dataKey="n" radius={[0, 4, 4, 0]} maxBarSize={14}>
              {data.map((e, i) => (
                <Cell key={i} fill={e.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

function ImpactCategoryChips({ alerts, tr, lang }) {
  const map = {}
  for (const a of alerts || []) {
    const k = String(a.impact || a.domain || 'cross_domain').toLowerCase() || 'cross_domain'
    map[k] = (map[k] || 0) + 1
  }
  const entries = Object.entries(map).sort((a, b) => b[1] - a[1]).slice(0, 6)
  if (!entries.length) return null
  return (
    <div className="cmd-cine-intel-ws__chip-row">
      <div className="cmd-cine-intel-ws__chart-title">{st(tr, lang, 'cmd_intel_ws_alert_categories')}</div>
      <div className="cmd-cine-intel-ws__chips">
        {entries.map(([k, n]) => (
          <span key={k} className="cmd-cine-intel-ws__chip">
            <span className="cmd-cine-intel-ws__chip-label">
              {DOMAIN_KEYS.has(k) ? st(tr, lang, `domain_${k}_simple`) : k.replace(/_/g, ' ')}
            </span>
            <span className="cmd-cine-intel-ws__chip-n cmd-data-num" dir="ltr">
              {n}
            </span>
          </span>
        ))}
      </div>
    </div>
  )
}

function AlertListDetailed({ alerts, tr, lang }) {
  const list = Array.isArray(alerts) ? alerts.slice(0, 8) : []
  if (!list.length) return null
  return (
    <div className="cmd-cine-intel-ws__alert-scroll">
      <div className="cmd-cine-intel-ws__chart-title">{st(tr, lang, 'cmd_intel_ws_alert_top')}</div>
      <ul className="cmd-cine-intel-ws__alert-items">
        {list.map((a, i) => (
          <li key={a.id || i} className="cmd-cine-intel-ws__alert-row">
            <span className={`cmd-cine-intel-ws__dot cmd-cine-intel-ws__dot--${String(a.severity || 'low')}`} aria-hidden />
            <div className="cmd-cine-intel-ws__alert-body">
              <CmdServerText lang={lang} tr={tr} as="span">
                {a.title || '—'}
              </CmdServerText>
              {a.impact ? (
                <span className="cmd-cine-intel-ws__alert-meta">
                  {DOMAIN_KEYS.has(String(a.impact).toLowerCase())
                    ? st(tr, lang, `domain_${String(a.impact).toLowerCase()}_simple`)
                    : String(a.impact)}
                </span>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

function RatioBars({ ratios, tr, lang, titleKey }) {
  const entries = Object.entries(ratios || {})
    .map(([k, r]) => {
      const v = parseRatioNumber(r)
      return { k, v, status: r?.status || 'neutral', label: st(tr, lang, `ratio_${k}`) }
    })
    .filter((x) => x.v != null)
  if (!entries.length) return null
  const maxV = Math.max(...entries.map((e) => Math.abs(e.v)), 1)
  const data = entries.map((e) => ({
    name: e.label,
    pct: Math.min(100, (Math.abs(e.v) / maxV) * 100),
    raw: e.v,
    fill: RATIO_STATUS_CLR[e.status] || RATIO_STATUS_CLR.neutral,
  }))
  return (
    <div className="cmd-cine-intel-ws__chart-block">
      <div className="cmd-cine-intel-ws__chart-title">{st(tr, lang, titleKey)}</div>
      <div className="cmd-cine-intel-ws__rechart" dir="ltr">
        <ResponsiveContainer width="100%" height={28 + data.length * 36}>
          <BarChart layout="vertical" data={data} margin={{ top: 4, right: 12, left: 4, bottom: 4 }}>
            <XAxis type="number" domain={[0, 100]} hide />
            <YAxis
              type="category"
              dataKey="name"
              width={100}
              tick={{ fill: CHART.tick, fontSize: 9 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              content={(props) => (
                <RechartsTooltipBody
                  {...props}
                  formatter={(v, entry) => {
                    const raw = entry?.payload?.raw
                    return raw != null ? String(raw) : `${Number(v).toFixed(0)}%`
                  }}
                />
              )}
            />
            <Bar dataKey="pct" radius={[0, 4, 4, 0]} maxBarSize={12}>
              {data.map((e, i) => (
                <Cell key={i} fill={e.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

function ScenarioCompareTable({ fcData, tr, lang }) {
  if (!fcData?.available) return null
  const keys = ['base', 'optimistic', 'risk']
  const rows = keys.map((k) => {
    const rev = fcData?.scenarios?.[k]?.revenue?.[0]?.point
    const np = fcData?.scenarios?.[k]?.net_profit?.[0]?.point
    return {
      key: k,
      label: st(tr, lang, `cmd_intel_scen_${k}`),
      rev: rev != null && Number.isFinite(Number(rev)) ? Number(rev) : null,
      np: np != null && Number.isFinite(Number(np)) ? Number(np) : null,
    }
  })
  const baseRev = rows.find((r) => r.key === 'base')?.rev
  const baseNp = rows.find((r) => r.key === 'base')?.np
  return (
    <div className="cmd-cine-intel-ws__scen-table-wrap">
      <div className="cmd-cine-intel-ws__chart-title">{st(tr, lang, 'cmd_intel_ws_scen_compare')}</div>
      <table className="cmd-cine-intel-ws__scen-table">
        <thead>
          <tr>
            <th>{st(tr, lang, 'cmd_intel_ws_scen_col')}</th>
            <th>{st(tr, lang, 'revenue')}</th>
            <th>{st(tr, lang, 'net_profit')}</th>
            <th>{st(tr, lang, 'cmd_intel_ws_scen_delta_rev')}</th>
            <th>{st(tr, lang, 'cmd_intel_ws_scen_delta_np')}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const dRev = baseRev != null && r.rev != null ? r.rev - baseRev : null
            const dNp = baseNp != null && r.np != null ? r.np - baseNp : null
            return (
              <tr key={r.key}>
                <td>{r.label}</td>
                <td className="cmd-data-num">{r.rev != null ? formatCompactForLang(r.rev, lang) : '—'}</td>
                <td className="cmd-data-num">{r.np != null ? formatCompactForLang(r.np, lang) : '—'}</td>
                <td className="cmd-data-num">
                  {dRev != null ? formatCompactSignedForLang(dRev, lang) : '—'}
                </td>
                <td className="cmd-data-num">
                  {dNp != null ? formatCompactSignedForLang(dNp, lang) : '—'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function RiskScoreHero({ score, tr, lang }) {
  const stt = scoreBandState(score)
  return (
    <div className={`cmd-cine-intel-ws__risk-hero cmd-cine-intel-ws__risk-hero--${stt}`.trim()}>
      <div className="cmd-cine-intel-ws__risk-hero-label">{st(tr, lang, 'cmd_intel_tile_risk')}</div>
      <div className="cmd-cine-intel-ws__risk-hero-val cmd-data-num" dir="ltr">
        {score != null ? Math.round(Number(score)) : '—'}
        <span className="cmd-cine-intel-ws__risk-hero-denom">/100</span>
      </div>
      <div className="cmd-cine-intel-ws__risk-hero-sub">
        {st(tr, lang, `cmd_intel_ws_posture_${stt}`)}
      </div>
    </div>
  )
}

function LiquidityMeters({ ratios, ocf, tr, lang }) {
  const cur = ratios?.current_ratio
  const qk = ratios?.quick_ratio
  const curV = parseRatioNumber(cur)
  const qkV = parseRatioNumber(qk)
  const items = []
  if (curV != null) {
    items.push({
      id: 'cr',
      label: st(tr, lang, 'ratio_current_ratio'),
      v: curV,
      state: cur?.status || 'neutral',
      max: Math.max(curV, 2.5, qkV || 0),
    })
  }
  if (qkV != null) {
    items.push({
      id: 'qr',
      label: st(tr, lang, 'ratio_quick_ratio'),
      v: qkV,
      state: qk?.status || 'neutral',
      max: Math.max(qkV, 2.5, curV || 0),
    })
  }
  return (
    <div className="cmd-cine-intel-ws__meter-stack">
      {items.map((it) => (
        <div key={it.id} className="cmd-cine-intel-ws__meter">
          <div className="cmd-cine-intel-ws__meter-head">
            <span>{it.label}</span>
            <span className="cmd-data-num" dir="ltr" style={{ color: RATIO_STATUS_CLR[it.state] || CHART.tick }}>
              {it.v.toFixed(2)}
            </span>
          </div>
          <div className="cmd-cine-intel-ws__meter-track">
            <div
              className="cmd-cine-intel-ws__meter-fill"
              style={{
                width: `${Math.min(100, (it.v / it.max) * 100)}%`,
                background: RATIO_STATUS_CLR[it.state] || CHART.accent,
              }}
            />
          </div>
        </div>
      ))}
      {ocf != null && Number.isFinite(Number(ocf)) ? (
        <div className="cmd-cine-intel-ws__ocf-pill">
          <span className="cmd-cine-intel-ws__ocf-k">{st(tr, lang, 'cmd_chart_trend_ocf')}</span>
          <span className="cmd-data-num" dir="ltr">
            {formatCompactForLang(Number(ocf), lang)}
          </span>
        </div>
      ) : null}
    </div>
  )
}

function EfficiencyPressure({ kpis, ci, tr, lang }) {
  const expMom = kpis?.expenses?.mom_pct
  const nm = kpis?.net_margin?.value
  const branch = ci?.cost_pressure?.driving_expense_increase_mom
  return (
    <div className="cmd-cine-intel-ws__eff-stack">
      <div className="cmd-cine-intel-ws__eff-row">
        <span className="cmd-cine-intel-ws__eff-k">{st(tr, lang, 'kpi_label_expenses')}</span>
        <span className="cmd-data-num" dir="ltr">
          {expMom != null && Number.isFinite(Number(expMom))
            ? formatSignedPctForLang(Number(expMom), 1, lang)
            : '—'}
        </span>
        <span className="cmd-cine-intel-ws__eff-hint">{st(tr, lang, 'cmd_intel_ws_eff_mom_hint')}</span>
      </div>
      <div className="cmd-cine-intel-ws__eff-row">
        <span className="cmd-cine-intel-ws__eff-k">{st(tr, lang, 'kpi_label_net_margin')}</span>
        <span className="cmd-data-num" dir="ltr">
          {nm != null && Number.isFinite(Number(nm)) ? formatPctForLang(Number(nm), 1, lang) : '—'}
        </span>
      </div>
      {branch?.branch_name ? (
        <div className="cmd-cine-intel-ws__eff-branch">
          <span className="cmd-cine-intel-ws__eff-k">{st(tr, lang, 'cmd_intel_ws_eff_pressure_branch')}</span>
          <CmdServerText lang={lang} tr={tr} as="span">
            {String(branch.branch_name)}
          </CmdServerText>
        </div>
      ) : null}
    </div>
  )
}

function buildActionContent({ tileId, drill, primaryResolution, decs, impacts, fcData, expenseIntel, tr, lang, narrative, bridgeInterp }) {
  let primary =
    drill.do?.[0]?.text ||
    (Array.isArray(decs) && decs[0]?.title ? String(decs[0].title) : null) ||
    null
  if (primaryResolution?.kind === 'expense' && primaryResolution.expense?.decision_id === '_cmd_baseline') {
    primary = st(tr, lang, 'cmd_intel_action_primary_baseline')
  } else if (primaryResolution?.kind === 'expense' && primaryResolution.expense?.title) {
    primary = String(primaryResolution.expense.title)
  } else if (primaryResolution?.decision?.title) {
    primary = String(primaryResolution.decision.title)
  }
  if (!primary && drill.what?.[0]?.text) {
    if (tileId === 'forecast' || tileId === 'liquidity' || tileId === 'efficiency') primary = drill.what[0].text
  }
  if (!primary && drill.do?.[0]?.text && (tileId === 'alerts' || tileId === 'risk')) {
    primary = drill.do[0].text
  }

  if (tileId === 'profit_bridge' && bridgeInterp && typeof bridgeInterp === 'object') {
    const drv = bridgeInterp.primary_driver
    if (drv) {
      const dl =
        drv === 'mixed'
          ? st(tr, lang, 'cmd_intel_bridge_driver_mixed')
          : drv === 'revenue'
            ? st(tr, lang, 'sfl_bridge_revenue')
            : drv === 'cogs'
              ? st(tr, lang, 'sfl_bridge_cogs')
              : drv === 'opex'
                ? st(tr, lang, 'sfl_bridge_opex')
                : String(drv)
      primary = stp(tr, lang, 'cmd_intel_bridge_action_primary', { driver: dl })
    }
  }
  if (tileId === 'profit_bridge' && !primary && narrative?.whatToDo?.lines?.[0]) {
    primary = String(narrative.whatToDo.lines[0])
  }

  let effect = null
  if (primaryResolution?.kind === 'expense' && primaryResolution.expense?.expected_financial_impact?.estimated_monthly_savings != null) {
    const sav = Number(primaryResolution.expense.expected_financial_impact.estimated_monthly_savings)
    if (Number.isFinite(sav)) {
      effect = stp(tr, lang, 'cmd_intel_action_effect_savings', { v: formatCompactForLang(sav, lang) })
    }
  } else if (primaryResolution?.decision) {
    const impKey = primaryResolution.decision.key || primaryResolution.decision.domain
    const imp = impacts?.[impKey]?.impact
    if (imp?.value != null && Number.isFinite(Number(imp.value))) {
      effect = stp(tr, lang, 'cmd_intel_action_effect_value', { v: formatCompactForLang(Number(imp.value), lang) })
    }
  }

  if (tileId === 'profit_bridge' && bridgeInterp && typeof bridgeInterp === 'object') {
    const nr = bridgeInterp.net_result
    if (nr === 'profit_up') effect = st(tr, lang, 'cmd_intel_bridge_net_up')
    else if (nr === 'profit_down') effect = st(tr, lang, 'cmd_intel_bridge_net_down')
    else if (nr === 'flat') effect = st(tr, lang, 'cmd_intel_bridge_net_flat')
  }

  let secondary = drill.do?.[1]?.text || null
  if (fcData?.summary?.insight && typeof fcData.summary.insight === 'string') {
    secondary = secondary || fcData.summary.insight
  } else if (expenseIntel?.narrative_excerpt && typeof expenseIntel.narrative_excerpt === 'string') {
    secondary = secondary || expenseIntel.narrative_excerpt
  }

  if (tileId === 'profit_bridge' && bridgeInterp && typeof bridgeInterp === 'object') {
    const pf = bridgeInterp.paradox_flags
    if (pf?.revenue_up_profit_down) secondary = st(tr, lang, 'cmd_intel_bridge_paradox_rev_up_np_down')
    else if (pf?.revenue_down_profit_up) secondary = st(tr, lang, 'cmd_intel_bridge_paradox_rev_down_np_up')
  }

  return { primary, effect, secondary }
}

function recommendedScenarioKey(fcData) {
  if (!fcData?.available) return null
  const risk = fcData?.summary?.risk_level
  const revMom = fcData?.summary?.trend_mom_revenue
  if (risk === 'high') return 'risk'
  if (revMom != null && Number(revMom) >= 1.5) return 'optimistic'
  return 'base'
}

function recommendedScenarioLine(fcData, tr, lang) {
  if (!fcData?.available) return st(tr, lang, 'cmd_intel_rec_scen_kpi_only')
  const risk = fcData?.summary?.risk_level
  const revMom = fcData?.summary?.trend_mom_revenue
  if (risk === 'high') return st(tr, lang, 'cmd_intel_rec_scen_conservative')
  if (revMom != null && Number(revMom) >= 1.5) return st(tr, lang, 'cmd_intel_rec_scen_growth')
  return st(tr, lang, 'cmd_intel_rec_scen_base')
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
 * @param {Record<string, object>} [p.impacts]
 * @param {object | null} [p.narrative] — {@link buildExecutiveNarrative} output
 * @param {string | null} [p.bridgeSelKey]
 * @param {(payload: Record<string, unknown>) => void} [p.onBridgeSegment]
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
  impacts = {},
  narrative = null,
  bridgeSelKey = null,
  onBridgeSegment,
}) {
  const t = useMemo(() => makeStrictTr(tr, lang), [tr, lang])
  const chartUid = useId().replace(/:/g, '')

  const model = useMemo(() => {
    const extra = drillExtraFromMain(main, kpis, primaryResolution, expenseIntel, decs, health, intel)
    const ratiosRoot = intel?.ratios || {}
    const chartData = (kpi) => !!extractKpiTrendPoints(main?.kpi_block, main?.cashflow, kpi)
    const list = Array.isArray(alerts) ? alerts : []

    if (tileId === 'forecast') {
      const drill = buildDrillIntelligence({
        panelType: 'analysis_tab',
        payload: { tab: 'overview' },
        extra,
        t,
        lang,
      })
      const ck = 'revenue'
      const bRev = fcData?.scenarios?.base?.revenue?.[0]?.point
      const bNp = fcData?.scenarios?.base?.net_profit?.[0]?.point
      const conf = fcData?.summary?.base_confidence
      const risk = fcData?.summary?.risk_level
      const cards = [
        {
          id: 'rev',
          label: st(tr, lang, 'cmd_intel_ws_sum_proj_rev'),
          value:
            bRev != null
              ? formatCompactForLang(Number(bRev), lang)
              : kpis?.revenue?.value != null && Number.isFinite(Number(kpis.revenue.value))
                ? formatCompactForLang(Number(kpis.revenue.value), lang)
                : '—',
          state: scoreBandState(health),
          hint: st(tr, lang, 'cmd_intel_ws_next_period'),
        },
        {
          id: 'np',
          label: st(tr, lang, 'cmd_intel_ws_sum_proj_np'),
          value: bNp != null ? formatCompactForLang(Number(bNp), lang) : '—',
          state: bNp != null && Number(bNp) < 0 ? 'risk' : 'good',
          hint: st(tr, lang, 'cmd_intel_ws_next_period'),
        },
        {
          id: 'scen',
          label: st(tr, lang, 'cmd_intel_ws_active_scenario'),
          value: st(tr, lang, 'cmd_intel_scen_base'),
          state: 'neutral',
          hint: st(tr, lang, 'cmd_intel_ws_compare_below'),
        },
        {
          id: 'conf',
          label: st(tr, lang, 'fc_confidence'),
          value: conf != null ? formatPctForLang(Number(conf), 0, lang) : '—',
          state: risk === 'high' ? 'warn' : 'good',
          hint: risk ? st(tr, lang, `cmd_intel_ws_risk_${String(risk)}`) : '',
        },
      ]
      return { drill, chartKpi: ck, chartHasData: chartData(ck), cards, kind: 'forecast' }
    }

    if (tileId === 'alerts') {
      const drill = buildDrillIntelligence({
        panelType: 'analysis_tab',
        payload: { tab: 'alerts' },
        extra,
        t,
        lang,
      })
      const hi = list.filter((a) => a.severity === 'high').length
      const med = list.filter((a) => a.severity === 'medium').length
      const low = list.filter((a) => a.severity === 'low').length
      const cards = [
        { id: 'hi', label: st(tr, lang, 'urgency_high'), value: String(hi), state: hi ? 'risk' : 'good', hint: st(tr, lang, 'cmd_intel_ws_alerts_open') },
        { id: 'med', label: st(tr, lang, 'urgency_medium'), value: String(med), state: med ? 'warn' : 'neutral', hint: '' },
        { id: 'low', label: st(tr, lang, 'urgency_low'), value: String(low), state: 'neutral', hint: '' },
        { id: 'tot', label: st(tr, lang, 'cmd_intel_ws_alerts_total'), value: String(list.length), state: list.length ? 'warn' : 'good', hint: st(tr, lang, 'cmd_intel_ws_health_ref', { v: health != null ? String(Math.round(health)) : '—' }) },
      ]
      return { drill, chartKpi: 'net_margin', chartHasData: chartData('net_margin'), cards, kind: 'alerts', hi, med, low, list }
    }

    if (tileId === 'scenarios') {
      const drill = buildDrillIntelligence({ panelType: 'decision', payload: {}, extra, t, lang })
      const recKey = recommendedScenarioKey(fcData)
      const cards = [
        {
          id: 'active',
          label: st(tr, lang, 'cmd_intel_ws_scen_active'),
          value: st(tr, lang, 'cmd_intel_scen_base'),
          state: 'neutral',
          hint: st(tr, lang, 'cmd_intel_ws_scen_active_hint'),
        },
        {
          id: 'rec',
          label: st(tr, lang, 'cmd_intel_ws_scen_recommended'),
          value: recKey ? st(tr, lang, `cmd_intel_scen_${recKey}`) : st(tr, lang, 'cmd_intel_ws_scen_rec_center'),
          state: recKey === 'risk' ? 'warn' : recKey === 'optimistic' ? 'good' : 'neutral',
          hint: recommendedScenarioLine(fcData, tr, lang),
        },
        {
          id: 'momr',
          label: st(tr, lang, 'cmd_intel_ws_trend_rev_mom'),
          value:
            fcData?.summary?.trend_mom_revenue != null
              ? formatSignedPctForLang(Number(fcData.summary.trend_mom_revenue), 1, lang)
              : '—',
          state: 'neutral',
          hint: '',
        },
        {
          id: 'momnp',
          label: st(tr, lang, 'cmd_intel_ws_trend_np_mom'),
          value:
            fcData?.summary?.trend_mom_net_profit != null
              ? formatSignedPctForLang(Number(fcData.summary.trend_mom_net_profit), 1, lang)
              : '—',
          state: 'neutral',
          hint: '',
        },
      ]
      return { drill, chartKpi: 'net_margin', chartHasData: chartData('net_margin'), cards, kind: 'scenarios' }
    }

    if (tileId === 'risk') {
      const s = riskScoreFromIntel(intel, list)
      const levS = scoreFromCategory(ratiosRoot, 'leverage')
      const drill = buildDrillIntelligence({
        panelType: 'domain',
        payload: { domain: 'leverage', score: s, status: domainStatusFromScore(s), ratios: ratiosRoot.leverage || {} },
        extra,
        t,
        lang,
      })
      const cards = [
        { id: 'risk', label: st(tr, lang, 'cmd_intel_ws_risk_composite'), value: `${Math.round(s)}/100`, state: scoreBandState(s), hint: st(tr, lang, 'cmd_intel_ws_leverage_ref') },
        { id: 'lev', label: st(tr, lang, 'domain_leverage_simple'), value: `${Math.round(levS)}/100`, state: scoreBandState(levS), hint: '' },
        { id: 'hi', label: st(tr, lang, 'urgency_high'), value: String(list.filter((a) => a.severity === 'high').length), state: list.filter((a) => a.severity === 'high').length ? 'risk' : 'good', hint: '' },
        { id: 'hl', label: st(tr, lang, 'exec_health_score'), value: health != null ? String(Math.round(health)) : '—', state: scoreBandState(health), hint: '/100' },
      ]
      return { drill, chartKpi: 'net_margin', chartHasData: chartData('net_margin'), cards, kind: 'risk', riskScore: s, levRatios: ratiosRoot.leverage || {} }
    }

    if (tileId === 'liquidity') {
      const s = scoreFromCategory(ratiosRoot, 'liquidity')
      const drill = buildDrillIntelligence({
        panelType: 'analysis_tab',
        payload: { tab: 'liquidity' },
        extra,
        t,
        lang,
      })
      const liqR = ratiosRoot.liquidity || {}
      const cur = parseRatioNumber(liqR.current_ratio)
      const qk = parseRatioNumber(liqR.quick_ratio)
      const ocf = main?.cashflow?.operating_cashflow
      const cards = [
        { id: 'score', label: st(tr, lang, 'cmd_intel_ws_liq_score'), value: `${Math.round(s)}/100`, state: scoreBandState(s), hint: st(tr, lang, 'domain_liquidity_simple') },
        {
          id: 'cur',
          label: st(tr, lang, 'ratio_current_ratio'),
          value: cur != null ? cur.toFixed(2) : '—',
          state: mapRatioToSumState(liqR.current_ratio?.status),
          hint: '',
        },
        {
          id: 'qk',
          label: st(tr, lang, 'ratio_quick_ratio'),
          value: qk != null ? qk.toFixed(2) : '—',
          state: mapRatioToSumState(liqR.quick_ratio?.status),
          hint: '',
        },
        { id: 'ocf', label: st(tr, lang, 'cmd_chart_trend_ocf'), value: ocf != null && Number.isFinite(Number(ocf)) ? formatCompactForLang(Number(ocf), lang) : '—', state: Number(ocf) >= 0 ? 'good' : 'warn', hint: st(tr, lang, 'cmd_intel_ws_ocf_hint') },
      ]
      return { drill, chartKpi: 'cashflow', chartHasData: chartData('cashflow'), cards, kind: 'liquidity', liqR, ocf }
    }

    if (tileId === 'efficiency') {
      const s = scoreFromCategory(ratiosRoot, 'efficiency')
      const drill = buildDrillIntelligence({
        panelType: 'analysis_tab',
        payload: { tab: 'efficiency' },
        extra,
        t,
        lang,
      })
      const expMom = kpis?.expenses?.mom_pct
      const cards = [
        { id: 'score', label: st(tr, lang, 'cmd_intel_ws_eff_score'), value: `${Math.round(s)}/100`, state: scoreBandState(s), hint: st(tr, lang, 'domain_efficiency_simple') },
        { id: 'exp', label: st(tr, lang, 'kpi_label_expenses'), value: kpis?.expenses?.value != null ? formatCompactForLang(Number(kpis.expenses.value), lang) : '—', state: expMom != null && Number(expMom) > 3 ? 'warn' : 'neutral', hint: expMom != null ? stp(tr, lang, 'cmd_intel_expanded_mom', { pct: formatSignedPctForLang(Number(expMom), 1, lang) }) : '' },
        { id: 'nm', label: st(tr, lang, 'kpi_label_net_margin'), value: kpis?.net_margin?.value != null ? formatPctForLang(Number(kpis.net_margin.value), 1, lang) : '—', state: 'neutral', hint: '' },
        {
          id: 'br',
          label: st(tr, lang, 'cmd_intel_ws_branch_load'),
          value: main?.comparative_intelligence?.cost_pressure?.driving_expense_increase_mom?.branch_name
            ? String(main.comparative_intelligence.cost_pressure.driving_expense_increase_mom.branch_name).slice(0, 28) +
              (String(main.comparative_intelligence.cost_pressure.driving_expense_increase_mom.branch_name).length > 28 ? '…' : '')
            : '—',
          state: main?.comparative_intelligence?.cost_pressure ? 'warn' : 'good',
          hint: st(tr, lang, 'cmd_intel_ws_branch_load_hint'),
        },
      ]
      return {
        drill,
        chartKpi: 'expenses',
        chartHasData: chartData('expenses'),
        cards,
        kind: 'efficiency',
        effRatios: ratiosRoot.efficiency || {},
      }
    }

    if (tileId === 'profit_bridge') {
      const drill = buildDrillIntelligence({
        panelType: 'analysis_tab',
        payload: { tab: 'profitability' },
        extra,
        t,
        lang,
      })
      const bridge = main?.structured_profit_bridge
      const brKeys = ['revenue_change', 'cogs_change', 'opex_change', 'operating_profit_change', 'net_profit_change']
      const rowCount = brKeys.filter((k) => {
        const d = bridge?.[k]?.delta
        return d != null && Number.isFinite(Number(d))
      }).length
      const structuredBridgeReady = rowCount >= 2
      const interp = main?.structured_profit_bridge_interpretation
      const revD = bridge?.revenue_change?.delta
      const netD = bridge?.net_profit_change?.delta
      const opD = bridge?.operating_profit_change?.delta
      const revMom = kpis?.revenue?.mom_pct
      const npMom = kpis?.net_profit?.mom_pct
      const drv = interp?.primary_driver
      const driverHint =
        drv === 'revenue'
          ? st(tr, lang, 'sfl_bridge_revenue')
          : drv === 'cogs'
            ? st(tr, lang, 'sfl_bridge_cogs')
            : drv === 'opex'
              ? st(tr, lang, 'sfl_bridge_opex')
              : drv === 'mixed'
                ? st(tr, lang, 'cmd_intel_bridge_driver_mixed')
                : st(tr, lang, 'cmd_intel_bridge_driver_unknown')
      const cards = [
        {
          id: 'rev',
          label: st(tr, lang, 'sfl_bridge_revenue'),
          value:
            revD != null && Number.isFinite(Number(revD))
              ? formatCompactSignedForLang(Number(revD), lang)
              : kpis?.revenue?.value != null && Number.isFinite(Number(kpis.revenue.value))
                ? formatCompactForLang(Number(kpis.revenue.value), lang)
                : '—',
          state: revD != null && Number(revD) < 0 ? 'warn' : 'good',
          hint:
            revMom != null && Number.isFinite(Number(revMom))
              ? stp(tr, lang, 'cmd_intel_expanded_mom', { pct: formatSignedPctForLang(Number(revMom), 1, lang) })
              : '',
        },
        {
          id: 'op',
          label: st(tr, lang, 'sfl_bridge_operating'),
          value:
            opD != null && Number.isFinite(Number(opD)) ? formatCompactSignedForLang(Number(opD), lang) : '—',
          state: opD != null && Number(opD) < 0 ? 'warn' : 'neutral',
          hint: '',
        },
        {
          id: 'net',
          label: st(tr, lang, 'sfl_bridge_net'),
          value:
            netD != null && Number.isFinite(Number(netD))
              ? formatCompactSignedForLang(Number(netD), lang)
              : kpis?.net_profit?.value != null && Number.isFinite(Number(kpis.net_profit.value))
                ? formatCompactForLang(Number(kpis.net_profit.value), lang)
                : '—',
          state: netD != null && Number(netD) < 0 ? 'risk' : 'good',
          hint:
            npMom != null && Number.isFinite(Number(npMom))
              ? stp(tr, lang, 'cmd_intel_expanded_mom', { pct: formatSignedPctForLang(Number(npMom), 1, lang) })
              : '',
        },
        {
          id: 'drv',
          label: st(tr, lang, 'cmd_intel_ws_bridge_driver_card'),
          value: driverHint,
          state: interp?.paradox_flags?.revenue_up_profit_down ? 'warn' : 'neutral',
          hint: st(tr, lang, 'cmd_intel_ws_bridge_driver_hint'),
        },
      ]
      return {
        drill,
        chartKpi: 'net_margin',
        chartHasData: chartData('net_margin'),
        cards,
        kind: 'profit_bridge',
        structuredBridgeReady,
      }
    }

    return {
      drill: { what: [], why: [], do: [] },
      chartKpi: 'revenue',
      chartHasData: chartData('revenue'),
      cards: [],
      kind: 'unknown',
    }
  }, [tileId, main, kpis, primaryResolution, expenseIntel, decs, health, intel, alerts, fcData, t, lang, tr])

  const action = useMemo(
    () =>
      buildActionContent({
        tileId,
        drill: model.drill,
        primaryResolution,
        decs,
        impacts,
        fcData,
        expenseIntel,
        tr,
        lang,
        narrative,
        bridgeInterp: main?.structured_profit_bridge_interpretation,
      }),
    [tileId, model.drill, primaryResolution, decs, impacts, fcData, expenseIntel, tr, lang, narrative, main?.structured_profit_bridge_interpretation],
  )

  const titleKey = tileId === 'profit_bridge' ? 'cmd_intel_tile_profit_bridge' : `cmd_intel_tile_${tileId}`

  const visual = (() => {
    switch (model.kind) {
      case 'forecast':
        return (
          <div className="cmd-cine-intel-ws__visual-col">
            {fcData?.available ? (
              <>
                <ForecastScenarioBars fcData={fcData} tr={tr} lang={lang} />
                <ForecastTrajectoryChart fcData={fcData} tr={tr} lang={lang} />
              </>
            ) : null}
            <div className="cmd-cine-intel-ws__chart-block">
              <div className="cmd-cine-intel-ws__chart-title">{st(tr, lang, 'cmd_intel_ws_actual_trend')}</div>
              <div className="cmd-cine-intel-ws__chart-embed">
                {model.chartHasData ? (
                  <ExecutiveKpiTrendChart
                    kpiBlock={main.kpi_block}
                    cashflow={main.cashflow}
                    kpiType={model.chartKpi}
                    tr={tr}
                    lang={lang}
                    cinematic
                  />
                ) : (
                  <p className="cmd-cine-intel-expanded__empty">{st(tr, lang, 'cmd_intel_expanded_chart_empty')}</p>
                )}
              </div>
            </div>
          </div>
        )
      case 'alerts':
        return (
          <div className="cmd-cine-intel-ws__visual-col">
            <SeverityBars high={model.hi} medium={model.med} low={model.low} tr={tr} lang={lang} />
            <ImpactCategoryChips alerts={model.list} tr={tr} lang={lang} />
            <AlertListDetailed alerts={model.list} tr={tr} lang={lang} />
            <div className="cmd-cine-intel-ws__chart-block">
              <div className="cmd-cine-intel-ws__chart-title">{st(tr, lang, 'cmd_intel_ws_margin_context')}</div>
              <div className="cmd-cine-intel-ws__chart-embed">
                {model.chartHasData ? (
                  <ExecutiveKpiTrendChart
                    kpiBlock={main.kpi_block}
                    cashflow={main.cashflow}
                    kpiType={model.chartKpi}
                    tr={tr}
                    lang={lang}
                    cinematic
                  />
                ) : (
                  <p className="cmd-cine-intel-expanded__empty">{st(tr, lang, 'cmd_intel_expanded_chart_empty')}</p>
                )}
              </div>
            </div>
          </div>
        )
      case 'scenarios':
        return (
          <div className="cmd-cine-intel-ws__visual-col">
            <ScenarioCompareTable fcData={fcData} tr={tr} lang={lang} />
            {fcData?.available ? <ForecastScenarioBars fcData={fcData} tr={tr} lang={lang} /> : null}
            {main?.financial_brain?.available && main.financial_brain?.what_changed ? (
              <div className="cmd-cine-intel-ws__fb-inline">
                <div className="cmd-cine-intel-ws__chart-title">{st(tr, lang, 'cmd_intel_expanded_section_snapshot')}</div>
                <p className="cmd-cine-intel-ws__fb-inline-text">
                  <CmdServerText lang={lang} tr={tr} as="span">
                    {main.financial_brain.what_changed}
                  </CmdServerText>
                </p>
              </div>
            ) : null}
            <div className="cmd-cine-intel-ws__chart-block">
              <div className="cmd-cine-intel-ws__chart-title">{st(tr, lang, 'cmd_intel_ws_net_margin_path')}</div>
              <div className="cmd-cine-intel-ws__chart-embed">
                {model.chartHasData ? (
                  <ExecutiveKpiTrendChart
                    kpiBlock={main.kpi_block}
                    cashflow={main.cashflow}
                    kpiType={model.chartKpi}
                    tr={tr}
                    lang={lang}
                    cinematic
                  />
                ) : (
                  <p className="cmd-cine-intel-expanded__empty">{st(tr, lang, 'cmd_intel_expanded_chart_empty')}</p>
                )}
              </div>
            </div>
          </div>
        )
      case 'risk':
        return (
          <div className="cmd-cine-intel-ws__visual-col">
            <RiskScoreHero score={model.riskScore} tr={tr} lang={lang} />
            <RatioBars ratios={model.levRatios} tr={tr} lang={lang} titleKey="cmd_intel_ws_leverage_drivers" />
            <div className="cmd-cine-intel-ws__chart-block">
              <div className="cmd-cine-intel-ws__chart-title">{st(tr, lang, 'cmd_intel_ws_volatility_context')}</div>
              <div className="cmd-cine-intel-ws__chart-embed">
                {model.chartHasData ? (
                  <ExecutiveKpiTrendChart
                    kpiBlock={main.kpi_block}
                    cashflow={main.cashflow}
                    kpiType={model.chartKpi}
                    tr={tr}
                    lang={lang}
                    cinematic
                  />
                ) : (
                  <p className="cmd-cine-intel-expanded__empty">{st(tr, lang, 'cmd_intel_expanded_chart_empty')}</p>
                )}
              </div>
            </div>
          </div>
        )
      case 'liquidity':
        return (
          <div className="cmd-cine-intel-ws__visual-col">
            <LiquidityMeters ratios={model.liqR} ocf={model.ocf} tr={tr} lang={lang} />
            <RatioBars ratios={model.liqR} tr={tr} lang={lang} titleKey="cmd_intel_ws_liquidity_ratios" />
            <div className="cmd-cine-intel-ws__chart-block">
              <div className="cmd-cine-intel-ws__chart-title">{st(tr, lang, 'cmd_intel_ws_ocf_trend')}</div>
              <div className="cmd-cine-intel-ws__chart-embed">
                {model.chartHasData ? (
                  <ExecutiveKpiTrendChart
                    kpiBlock={main.kpi_block}
                    cashflow={main.cashflow}
                    kpiType={model.chartKpi}
                    tr={tr}
                    lang={lang}
                    cinematic
                  />
                ) : (
                  <p className="cmd-cine-intel-expanded__empty">{st(tr, lang, 'cmd_intel_expanded_chart_empty')}</p>
                )}
              </div>
            </div>
          </div>
        )
      case 'efficiency':
        return (
          <div className="cmd-cine-intel-ws__visual-col">
            <EfficiencyPressure kpis={kpis} ci={main?.comparative_intelligence} tr={tr} lang={lang} />
            <RatioBars ratios={model.effRatios} tr={tr} lang={lang} titleKey="cmd_intel_ws_efficiency_drivers" />
            <div className="cmd-cine-intel-ws__chart-block">
              <div className="cmd-cine-intel-ws__chart-title">{st(tr, lang, 'cmd_intel_ws_expense_trend')}</div>
              <div className="cmd-cine-intel-ws__chart-embed">
                {model.chartHasData ? (
                  <ExecutiveKpiTrendChart
                    kpiBlock={main.kpi_block}
                    cashflow={main.cashflow}
                    kpiType={model.chartKpi}
                    tr={tr}
                    lang={lang}
                    cinematic
                  />
                ) : (
                  <p className="cmd-cine-intel-expanded__empty">{st(tr, lang, 'cmd_intel_expanded_chart_empty')}</p>
                )}
              </div>
            </div>
          </div>
        )
      case 'profit_bridge':
        return (
          <div className="cmd-cine-intel-ws__visual-col">
            <div className="cmd-cine-intel-ws__chart-block cmd-cine-intel-ws__chart-block--bridge">
              <div className="cmd-cine-intel-ws__chart-title">{st(tr, lang, 'cmd_intel_ws_bridge_interactive')}</div>
              <div className="cmd-cine-intel-ws__bridge-embed">
                {model.structuredBridgeReady && main?.structured_profit_bridge ? (
                  <CommandCenterProfitPathBridge
                    bridge={main.structured_profit_bridge}
                    variance={main.structured_income_statement_variance}
                    varianceMeta={main.structured_income_statement_variance_meta}
                    bridgeInterpretation={main.structured_profit_bridge_interpretation}
                    selectedKey={bridgeSelKey}
                    onSegmentClick={onBridgeSegment}
                    tr={tr}
                    lang={lang}
                  />
                ) : main?.kpi_block ? (
                  <ExecutiveProfitBridgeChart kpiBlock={main.kpi_block} tr={tr} lang={lang} />
                ) : (
                  <p className="cmd-cine-intel-expanded__empty">{st(tr, lang, 'cmd_intel_expanded_chart_empty')}</p>
                )}
              </div>
            </div>
            <div className="cmd-cine-intel-ws__chart-block">
              <div className="cmd-cine-intel-ws__chart-title">{st(tr, lang, 'cmd_intel_ws_net_margin_path')}</div>
              <div className="cmd-cine-intel-ws__chart-embed">
                {model.chartHasData ? (
                  <ExecutiveKpiTrendChart
                    kpiBlock={main.kpi_block}
                    cashflow={main.cashflow}
                    kpiType={model.chartKpi}
                    tr={tr}
                    lang={lang}
                    cinematic
                  />
                ) : (
                  <p className="cmd-cine-intel-expanded__empty">{st(tr, lang, 'cmd_intel_expanded_chart_empty')}</p>
                )}
              </div>
            </div>
          </div>
        )
      default:
        return (
          <div className="cmd-cine-intel-ws__visual-col">
            <p className="cmd-cine-intel-expanded__empty">{st(tr, lang, 'cmd_intel_expanded_drill_empty')}</p>
          </div>
        )
    }
  })()

  const hasExecCausal =
    Boolean(narrative?.whatChanged?.lines?.length) ||
    Boolean(narrative?.why?.lines?.length) ||
    Boolean(narrative?.whatToDo?.lines?.length)
  const narrativeFallback =
    !model.drill.what.length && !model.drill.why.length && !model.drill.do.length && !hasExecCausal ? (
      <p className="cmd-cine-intel-expanded__empty">{st(tr, lang, 'cmd_intel_expanded_drill_empty')}</p>
    ) : null

  return (
    <section
      className="cmd-cine-intel-expanded cmd-cine-intel-expanded--workspace"
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

      <div className="cmd-cine-intel-expanded__body cmd-cine-intel-ws">
        <SummaryStrip cards={model.cards} tr={tr} lang={lang} />

        <div className="cmd-cine-intel-ws__split">
          <div className="cmd-cine-intel-ws__visual" id={`${chartUid}-intel-vis`}>
            {visual}
          </div>
          <aside className="cmd-cine-intel-ws__narrative" aria-labelledby={`${chartUid}-narr`}>
            <div id={`${chartUid}-narr`} className="cmd-cine-intel-ws__narrative-head">
              {st(tr, lang, 'cmd_intel_ws_narrative_head')}
            </div>
            <NarrativeColumn what={model.drill.what} why={model.drill.why} do={model.drill.do} tr={tr} lang={lang} />
            <ExecutiveCausalBlock narrative={narrative} tr={tr} lang={lang} />
            {narrativeFallback}
          </aside>
        </div>

        <ActionZone primary={action.primary} effect={action.effect} secondary={action.secondary} tr={tr} lang={lang} />

        {tileId === 'alerts' && model.hi > 0 ? (
          <div className="cmd-cine-intel-ws__immediate">
            <span className="cmd-cine-intel-ws__immediate-k">{st(tr, lang, 'cmd_intel_ws_immediate')}</span>
            <p>{st(tr, lang, 'cmd_intel_ws_immediate_alerts')}</p>
          </div>
        ) : null}
      </div>
    </section>
  )
}
