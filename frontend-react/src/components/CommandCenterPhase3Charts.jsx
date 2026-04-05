/**
 * Phase 3 Command Center charts — Recharts only; data from existing executive payload.
 */
import { useId, useMemo } from 'react'
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

/** Slightly dim mid-ranked branches; emphasize first + last row (presentation-only). */
function osBranchBarShape(props) {
  const { fill, x, y, width, height, payload } = props
  if (width == null || width <= 0 || height == null) return null
  const alpha = payload?._osEmph ? 1 : 0.78
  return <rect x={x} y={y} width={width} height={height} fill={fill} fillOpacity={alpha} rx={5} ry={5} />
}

function P3Tooltip({ active, payload, label, lang }) {
  if (!active || !payload?.length) return null
  return (
    <div className="cmd-os-chart-tooltip">
      <div className="cmd-os-chart-tooltip__label">{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} className="cmd-os-chart-tooltip__row">
          <span style={{ color: p.color }}>{p.name}: </span>
          {p.value != null && Number.isFinite(Number(p.value)) ? formatCompactForLang(p.value, lang) : '—'}
        </div>
      ))}
    </div>
  )
}

export function CommandCenterTripleTrendChart({ kpiBlock, tr, lang, cinematic = false }) {
  const trendUid = useId().replace(/:/g, '')
  const data = useMemo(() => extractTripleTrendRows(kpiBlock), [kpiBlock])
  if (!data?.length) return null

  const title = st(tr, lang, 'cmd_p3_trend_title')
  const lr = st(tr, lang, 'cmd_chart_trend_revenue').replace(/\s*\(.*\)\s*$/, '')
  const le = st(tr, lang, 'cmd_chart_trend_expenses').replace(/\s*\(.*\)\s*$/, '')
  const ln = st(tr, lang, 'cmd_chart_trend_net_profit').replace(/\s*\(.*\)\s*$/, '')
  const spanFrom = data[0]?.period
  const spanTo = data[data.length - 1]?.period
  const spanLabel =
    spanFrom && spanTo && spanFrom !== spanTo ? `${spanFrom} → ${spanTo}` : spanTo || spanFrom || ''
  const lastIdx = data.length - 1
  const lastDot =
    (fill) =>
    (props) => {
      const { cx, cy, index } = props
      if (index !== lastIdx || cx == null || cy == null) return null
      return (
        <circle
          cx={cx}
          cy={cy}
          r={5}
          fill={fill}
          stroke="rgba(255,255,255,0.3)"
          strokeWidth={1.5}
        />
      )
    }

  return (
    <div
      className={`cmd-p3-chart-shell cmd-p3-chart-shell--primary${cinematic ? ' cmd-cine-primary-chart' : ''}`.trim()}
    >
      <div className="cmd-p3-chart-title">{title}</div>
      {spanLabel ? (
        <p className="cmd-p3-chart-subtitle" dir="ltr">
          {spanLabel}
        </p>
      ) : null}
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
      <div className={cinematic ? 'cmd-p3-chart-inner' : undefined} style={{ width: '100%', height: cinematic ? undefined : 320 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 14, left: 2, bottom: 6 }}>
            <defs>
              <linearGradient id={`${trendUid}-st-rev`} x1="0" y1="0" x2="1" y2="0" gradientUnits="objectBoundingBox">
                <stop offset="0%" stopColor={G.rev} stopOpacity="0.4" />
                <stop offset="50%" stopColor={G.rev} stopOpacity="0.95" />
                <stop offset="100%" stopColor={G.rev} stopOpacity="1" />
              </linearGradient>
              <linearGradient id={`${trendUid}-st-exp`} x1="0" y1="0" x2="1" y2="0" gradientUnits="objectBoundingBox">
                <stop offset="0%" stopColor={G.exp} stopOpacity="0.38" />
                <stop offset="100%" stopColor={G.exp} stopOpacity="1" />
              </linearGradient>
              <linearGradient id={`${trendUid}-st-np`} x1="0" y1="0" x2="1" y2="0" gradientUnits="objectBoundingBox">
                <stop offset="0%" stopColor={G.np} stopOpacity="0.42" />
                <stop offset="55%" stopColor={G.np} stopOpacity="0.95" />
                <stop offset="100%" stopColor={G.np} stopOpacity="1" />
              </linearGradient>
              <filter id={`${trendUid}-glow-rev`} x="-45%" y="-45%" width="190%" height="190%">
                <feGaussianBlur stdDeviation="2.2" result="b" />
                <feMerge>
                  <feMergeNode in="b" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
              <filter id={`${trendUid}-glow-exp`} x="-45%" y="-45%" width="190%" height="190%">
                <feGaussianBlur stdDeviation="2" result="b" />
                <feMerge>
                  <feMergeNode in="b" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
              <filter id={`${trendUid}-glow-np`} x="-45%" y="-45%" width="190%" height="190%">
                <feGaussianBlur stdDeviation="2.6" result="b" />
                <feMerge>
                  <feMergeNode in="b" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>
            <CartesianGrid strokeDasharray="4 6" stroke={G.grid} vertical={false} strokeLinecap="round" />
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
              stroke={`url(#${trendUid}-st-rev)`}
              strokeWidth={2.55}
              strokeLinecap="round"
              strokeLinejoin="round"
              dot={lastDot(G.rev)}
              activeDot={{ r: 5.5, strokeWidth: 0, stroke: 'rgba(255,255,255,0.25)', fill: G.rev }}
              connectNulls
              style={{ filter: `url(#${trendUid}-glow-rev)` }}
              animationDuration={1100}
              animationEasing="ease-out"
            />
            <Line
              type="monotone"
              name={le}
              dataKey="expenses"
              stroke={`url(#${trendUid}-st-exp)`}
              strokeWidth={2.35}
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeDasharray="7 5"
              dot={lastDot(G.exp)}
              activeDot={{ r: 5.5, strokeWidth: 0, stroke: 'rgba(255,255,255,0.2)', fill: G.exp }}
              connectNulls
              style={{ filter: `url(#${trendUid}-glow-exp)` }}
              animationDuration={1050}
              animationEasing="ease-out"
            />
            <Line
              type="monotone"
              name={ln}
              dataKey="net_profit"
              stroke={`url(#${trendUid}-st-np)`}
              strokeWidth={2.75}
              strokeLinecap="round"
              strokeLinejoin="round"
              dot={lastDot(G.np)}
              activeDot={{ r: 6.5, strokeWidth: 0, stroke: 'rgba(255,255,255,0.28)', fill: G.np }}
              connectNulls
              style={{ filter: `url(#${trendUid}-glow-np)` }}
              animationDuration={1150}
              animationEasing="ease-out"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export function CommandCenterBranchGroupedChart({
  comparativeIntelligence,
  tr,
  lang,
  onOpenBranches,
  cinematic = false,
}) {
  const branchUid = useId().replace(/:/g, '')
  const data = useMemo(() => {
    const raw = extractBranchGroupedCompareRows(comparativeIntelligence, 8)
    if (!raw?.length) return raw
    const last = raw.length - 1
    return raw.map((row, i) => ({ ...row, _osEmph: i === 0 || i === last }))
  }, [comparativeIntelligence])
  if (!data?.length) {
    return (
      <div
        className={`cmd-p3-chart-shell cmd-p3-chart-shell--branch${cinematic ? ' cmd-cine-branch-chart-shell' : ''}`.trim()}
      >
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
    <div
      className={`cmd-p3-chart-shell cmd-p3-chart-shell--branch${cinematic ? ' cmd-cine-branch-chart-shell' : ''}`.trim()}
    >
      <div className="cmd-p3-chart-title">{st(tr, lang, 'cmd_p3_branch_chart_title')}</div>
      <div className={cinematic ? 'cmd-p3-chart-inner' : undefined} style={{ width: '100%', height: h }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart layout="vertical" data={data} margin={{ top: 4, right: 8, left: 4, bottom: 4 }}>
            <defs>
              <linearGradient id={`${branchUid}-rev`} x1="0" y1="0" x2="1" y2="0" gradientUnits="objectBoundingBox">
                <stop offset="0%" stopColor={G.rev} stopOpacity="0.5" />
                <stop offset="100%" stopColor={G.rev} stopOpacity="1" />
              </linearGradient>
              <linearGradient id={`${branchUid}-exp`} x1="0" y1="0" x2="1" y2="0" gradientUnits="objectBoundingBox">
                <stop offset="0%" stopColor={G.exp} stopOpacity="0.45" />
                <stop offset="100%" stopColor={G.exp} stopOpacity="1" />
              </linearGradient>
              <linearGradient id={`${branchUid}-profit`} x1="0" y1="0" x2="1" y2="0" gradientUnits="objectBoundingBox">
                <stop offset="0%" stopColor={G.profitBar} stopOpacity="0.48" />
                <stop offset="100%" stopColor={G.profitBar} stopOpacity="1" />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="4 6" stroke={G.grid} vertical={false} strokeLinecap="round" />
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
            <Bar
              dataKey="revenue"
              name={lr}
              fill={`url(#${branchUid}-rev)`}
              radius={[0, 6, 6, 0]}
              maxBarSize={14}
              shape={osBranchBarShape}
              animationDuration={750}
              animationEasing="ease-out"
              style={{ filter: 'drop-shadow(0 0 8px rgba(59,158,255,0.12))' }}
            />
            <Bar
              dataKey="expenses"
              name={le}
              fill={`url(#${branchUid}-exp)`}
              radius={[0, 6, 6, 0]}
              maxBarSize={14}
              shape={osBranchBarShape}
              animationDuration={750}
              animationEasing="ease-out"
              style={{ filter: 'drop-shadow(0 0 8px rgba(248,113,113,0.1))' }}
            />
            <Bar
              dataKey="profit"
              name={lp}
              fill={`url(#${branchUid}-profit)`}
              radius={[0, 6, 6, 0]}
              maxBarSize={14}
              shape={osBranchBarShape}
              animationDuration={750}
              animationEasing="ease-out"
              style={{ filter: 'drop-shadow(0 0 8px rgba(167,139,250,0.12))' }}
            />
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
