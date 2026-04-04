/**
 * Phase 3 Command Center charts — Recharts only; data from existing executive payload.
 */
import { useMemo } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { formatCompactForLang } from '../utils/numberFormat.js'
import { strictT as st } from '../utils/strictI18n.js'
import { extractBranchGroupedCompareRows, extractTripleTrendRows } from '../utils/executiveChartModels.js'

const G = {
  grid: 'rgba(30, 41, 59, 0.9)',
  text: '#94a3b8',
  rev: '#3b9eff',
  exp: '#f87171',
  np: '#34d399',
  profitBar: '#a78bfa',
}

function P3Tooltip({ active, payload, label, lang }) {
  if (!active || !payload?.length) return null
  return (
    <div
      style={{
        background: 'rgba(15, 23, 42, 0.96)',
        border: '1px solid rgba(148, 163, 184, 0.2)',
        borderRadius: 10,
        padding: '10px 12px',
        boxShadow: '0 12px 40px rgba(0,0,0,0.55)',
        minWidth: 140,
      }}
    >
      <div style={{ fontSize: 10, color: G.text, marginBottom: 8, fontWeight: 800, letterSpacing: '.06em' }}>
        {label}
      </div>
      {payload.map((p) => (
        <div
          key={p.dataKey}
          style={{
            fontSize: 12,
            fontWeight: 700,
            fontFamily: 'var(--font-mono, ui-monospace, monospace)',
            color: '#f1f5f9',
            marginTop: 4,
            direction: 'ltr',
          }}
        >
          <span style={{ color: p.color }}>{p.name}: </span>
          {p.value != null && Number.isFinite(Number(p.value)) ? formatCompactForLang(p.value, lang) : '—'}
        </div>
      ))}
    </div>
  )
}

export function CommandCenterTripleTrendChart({ kpiBlock, tr, lang }) {
  const data = useMemo(() => extractTripleTrendRows(kpiBlock), [kpiBlock])
  if (!data?.length) return null

  const title = st(tr, lang, 'cmd_p3_trend_title')
  const lr = st(tr, lang, 'cmd_chart_trend_revenue').replace(/\s*\(.*\)\s*$/, '')
  const le = st(tr, lang, 'cmd_chart_trend_expenses').replace(/\s*\(.*\)\s*$/, '')
  const ln = st(tr, lang, 'cmd_chart_trend_net_profit').replace(/\s*\(.*\)\s*$/, '')

  return (
    <div className="cmd-p3-chart-shell cmd-p3-chart-shell--primary">
      <div className="cmd-p3-chart-title">{title}</div>
      <div className="cmd-p3-chart-legend" aria-hidden>
        <span className="cmd-p3-chart-legend__i">
          <span className="cmd-p3-chart-legend__dot" style={{ color: G.rev, background: G.rev }} />
          {lr}
        </span>
        <span className="cmd-p3-chart-legend__i">
          <span className="cmd-p3-chart-legend__dot" style={{ color: G.exp, background: G.exp }} />
          {le}
        </span>
        <span className="cmd-p3-chart-legend__i">
          <span className="cmd-p3-chart-legend__dot" style={{ color: G.np, background: G.np }} />
          {ln}
        </span>
      </div>
      <div style={{ width: '100%', height: 268 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
            <defs>
              <filter id="cmdP3GlowRev" x="-40%" y="-40%" width="180%" height="180%">
                <feGaussianBlur stdDeviation="2" result="b" />
                <feMerge>
                  <feMergeNode in="b" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
              <filter id="cmdP3GlowExp" x="-40%" y="-40%" width="180%" height="180%">
                <feGaussianBlur stdDeviation="2" result="b" />
                <feMerge>
                  <feMergeNode in="b" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
              <filter id="cmdP3GlowNp" x="-40%" y="-40%" width="180%" height="180%">
                <feGaussianBlur stdDeviation="2.5" result="b" />
                <feMerge>
                  <feMergeNode in="b" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>
            <CartesianGrid strokeDasharray="4 6" stroke={G.grid} vertical={false} />
            <XAxis
              dataKey="period"
              tick={{ fill: G.text, fontSize: 9 }}
              axisLine={{ stroke: 'rgba(51,65,85,0.6)' }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: G.text, fontSize: 9 }}
              axisLine={false}
              tickLine={false}
              width={56}
              tickFormatter={(v) => formatCompactForLang(v, lang)}
            />
            <Tooltip
              content={(props) => <P3Tooltip {...props} lang={lang} />}
              cursor={{ stroke: 'rgba(148,163,184,0.25)', strokeWidth: 1 }}
            />
            <Line
              type="monotone"
              name={lr}
              dataKey="revenue"
              stroke={G.rev}
              strokeWidth={2.4}
              dot={false}
              activeDot={{ r: 5, strokeWidth: 0 }}
              connectNulls
              style={{ filter: 'url(#cmdP3GlowRev)' }}
              animationDuration={520}
            />
            <Line
              type="monotone"
              name={le}
              dataKey="expenses"
              stroke={G.exp}
              strokeWidth={2.2}
              strokeDasharray="6 4"
              dot={false}
              activeDot={{ r: 5, strokeWidth: 0 }}
              connectNulls
              style={{ filter: 'url(#cmdP3GlowExp)' }}
              animationDuration={520}
            />
            <Line
              type="monotone"
              name={ln}
              dataKey="net_profit"
              stroke={G.np}
              strokeWidth={2.6}
              dot={false}
              activeDot={{ r: 6, strokeWidth: 0 }}
              connectNulls
              style={{ filter: 'url(#cmdP3GlowNp)' }}
              animationDuration={520}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export function CommandCenterBranchGroupedChart({ comparativeIntelligence, tr, lang, onOpenBranches }) {
  const data = useMemo(() => extractBranchGroupedCompareRows(comparativeIntelligence, 8), [comparativeIntelligence])
  if (!data?.length) {
    return (
      <div className="cmd-p3-chart-shell cmd-p3-chart-shell--branch">
        <div className="cmd-p3-chart-title">{st(tr, lang, 'cmd_p3_branch_chart_title')}</div>
        <div style={{ fontSize: 12, color: G.text, padding: '24px 8px' }}>{st(tr, lang, 'cmd_chart_branch_empty')}</div>
      </div>
    )
  }

  const h = Math.min(400, 56 + data.length * 36)
  const lr = st(tr, lang, 'sfl_row_revenue')
  const le = st(tr, lang, 'cmd_p3_branch_bar_expense')
  const lp = st(tr, lang, 'cmd_p3_branch_bar_profit')

  return (
    <div className="cmd-p3-chart-shell cmd-p3-chart-shell--branch">
      <div className="cmd-p3-chart-title">{st(tr, lang, 'cmd_p3_branch_chart_title')}</div>
      <div style={{ width: '100%', height: h }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart layout="vertical" data={data} margin={{ top: 4, right: 8, left: 4, bottom: 4 }}>
            <CartesianGrid strokeDasharray="4 6" stroke={G.grid} vertical={false} />
            <XAxis
              type="number"
              tick={{ fill: G.text, fontSize: 9 }}
              axisLine={{ stroke: 'rgba(51,65,85,0.6)' }}
              tickLine={false}
              tickFormatter={(v) => formatCompactForLang(v, lang)}
            />
            <YAxis
              type="category"
              dataKey="name"
              width={92}
              tick={{ fill: G.text, fontSize: 9 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null
                return <P3Tooltip active={active} payload={payload} label={label} lang={lang} />
              }}
              cursor={{ fill: 'rgba(255,255,255,0.03)' }}
            />
            <Legend
              wrapperStyle={{ fontSize: 10, paddingTop: 8 }}
              formatter={(value) => <span style={{ color: '#cbd5e1', fontWeight: 700 }}>{value}</span>}
            />
            <Bar dataKey="revenue" name={lr} fill={G.rev} radius={[0, 4, 4, 0]} maxBarSize={14} animationDuration={480} />
            <Bar dataKey="expenses" name={le} fill={G.exp} radius={[0, 4, 4, 0]} maxBarSize={14} animationDuration={480} />
            <Bar dataKey="profit" name={lp} fill={G.profitBar} radius={[0, 4, 4, 0]} maxBarSize={14} animationDuration={480} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      {onOpenBranches ? (
        <button
          type="button"
          onClick={onOpenBranches}
          style={{
            marginTop: 12,
            padding: '8px 12px',
            borderRadius: 10,
            border: '1px solid rgba(148,163,184,0.2)',
            background: 'rgba(255,255,255,0.04)',
            color: '#cbd5e1',
            fontSize: 11,
            fontWeight: 700,
            cursor: 'pointer',
            width: '100%',
          }}
        >
          {st(tr, lang, 'cmd_open_branches')} →
        </button>
      ) : null}
    </div>
  )
}
