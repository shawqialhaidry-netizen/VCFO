/**
 * Executive charts — Recharts, data from executive payload only.
 */
import { useMemo, useState } from 'react'
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
import { formatCompact } from '../utils/numberFormat.js'
import { strictT as st } from '../utils/strictI18n.js'
import {
  extractBranchCompareRows,
  extractKpiTrendPoints,
  extractProfitBridge,
} from '../utils/executiveChartModels.js'

const G = {
  grid: '#1f2937',
  text: '#94a3b8',
  accent: '#00d4aa',
  green: '#34d399',
  red: '#f87171',
  violet: '#7c5cfc',
}

function ExecTooltip({ active, payload, label, formatter }) {
  if (!active || !payload?.length) return null
  const row = payload[0]?.payload
  const v = payload[0]?.value
  const lab = row?.name ?? row?.period ?? label
  return (
    <div
      style={{
        background: '#111827',
        border: '1px solid #1f2937',
        borderRadius: 8,
        padding: '8px 11px',
        boxShadow: '0 8px 24px rgba(0,0,0,0.45)',
      }}
    >
      <div style={{ fontSize: 9, color: G.text, marginBottom: 3, fontWeight: 700 }}>{lab}</div>
      <div style={{ fontSize: 13, fontWeight: 800, fontFamily: 'var(--font-mono)', color: '#f8fafc', direction: 'ltr' }}>
        {formatter(v)}
      </div>
    </div>
  )
}

function trendLineVisuals(kpiType) {
  if (kpiType === 'expenses') return { stroke: G.red, cursor: G.red }
  if (kpiType === 'net_margin') return { stroke: G.violet, cursor: G.violet }
  return { stroke: G.accent, cursor: G.accent }
}

export function ExecutiveKpiTrendChart({ kpiBlock, cashflow, kpiType, tr, lang }) {
  const data = useMemo(
    () => extractKpiTrendPoints(kpiBlock, cashflow, kpiType),
    [kpiBlock, cashflow, kpiType],
  )
  if (!data?.length) return null

  const title =
    kpiType === 'cashflow'
      ? st(tr, lang, 'cmd_chart_trend_ocf')
      : kpiType === 'revenue'
        ? st(tr, lang, 'cmd_chart_trend_revenue')
        : kpiType === 'expenses'
          ? st(tr, lang, 'cmd_chart_trend_expenses')
          : kpiType === 'net_margin'
            ? st(tr, lang, 'cmd_chart_trend_net_margin')
            : st(tr, lang, 'cmd_chart_trend_net_profit')

  const { stroke, cursor } = trendLineVisuals(kpiType)
  const pctAxis = kpiType === 'net_margin'
  const tooltipFmt = (v) => (pctAxis && v != null && Number.isFinite(Number(v)) ? `${Number(v).toFixed(1)}%` : formatCompact(v))
  const yAxisFmt = (v) => (pctAxis && v != null && Number.isFinite(Number(v)) ? `${Number(v).toFixed(0)}%` : formatCompact(v))

  return (
    <div className="cmd-chart-enter" style={{ marginTop: 18, marginBottom: 8 }}>
      <div
        style={{
          fontSize: 9,
          fontWeight: 800,
          color: G.text,
          textTransform: 'uppercase',
          letterSpacing: '.08em',
          marginBottom: 10,
        }}
      >
        {title}
      </div>
      <div style={{ width: '100%', height: 200 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={G.grid} vertical={false} />
            <XAxis dataKey="period" tick={{ fill: G.text, fontSize: 9 }} axisLine={{ stroke: G.grid }} tickLine={false} />
            <YAxis
              tick={{ fill: G.text, fontSize: 9 }}
              axisLine={{ stroke: G.grid }}
              tickLine={false}
              tickFormatter={yAxisFmt}
              width={52}
            />
            <Tooltip
              content={(props) => <ExecTooltip {...props} formatter={tooltipFmt} />}
              cursor={{ stroke: cursor, strokeWidth: 1, strokeDasharray: '4 4' }}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke={stroke}
              strokeWidth={2}
              dot={{ r: 3, fill: stroke, strokeWidth: 0 }}
              activeDot={{ r: 5, fill: stroke }}
              animationDuration={420}
              animationEasing="ease-out"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export function ExecutiveProfitBridgeChart({ kpiBlock, tr, lang }) {
  const model = useMemo(() => extractProfitBridge(kpiBlock), [kpiBlock])
  if (!model?.steps?.length) return null

  const labelFor = (id) => {
    if (id === 'rev') return st(tr, lang, 'cmd_chart_bridge_rev')
    if (id === 'cost') return st(tr, lang, 'cmd_chart_bridge_cost')
    if (id === 'other') return st(tr, lang, 'cmd_chart_bridge_other')
    return st(tr, lang, 'cmd_chart_bridge_net')
  }

  const data = model.steps.map((s) => ({
    name: labelFor(s.id),
    value: s.value,
    id: s.id,
  }))

  const fillFor = (row) => {
    if (row.id === 'net') return row.value >= 0 ? G.green : G.red
    if (row.value >= 0) return G.green
    return G.red
  }

  const sub =
    model.periodPrev && model.periodLast
      ? `${model.periodPrev} → ${model.periodLast}`
      : null

  return (
    <div className="cmd-chart-enter" style={{ marginTop: 18, marginBottom: 8 }}>
      <div
        style={{
          fontSize: 9,
          fontWeight: 800,
          color: G.text,
          textTransform: 'uppercase',
          letterSpacing: '.08em',
          marginBottom: 4,
        }}
      >
        {st(tr, lang, 'cmd_chart_bridge_title')}
      </div>
      {sub ? (
        <div style={{ fontSize: 10, color: G.text, marginBottom: 10, opacity: 0.9 }}>{sub}</div>
      ) : null}
      <div style={{ width: '100%', height: 220 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={G.grid} vertical={false} />
            <XAxis
              dataKey="name"
              tick={{ fill: G.text, fontSize: 8 }}
              axisLine={{ stroke: G.grid }}
              tickLine={false}
              interval={0}
              height={48}
            />
            <YAxis
              tick={{ fill: G.text, fontSize: 9 }}
              axisLine={{ stroke: G.grid }}
              tickLine={false}
              tickFormatter={(v) => formatCompact(v)}
              width={52}
            />
            <Tooltip
              content={(props) => <ExecTooltip {...props} formatter={(v) => formatCompact(v)} />}
              cursor={{ fill: 'rgba(255,255,255,0.04)' }}
            />
            <Bar dataKey="value" radius={[4, 4, 0, 0]} animationDuration={400} animationEasing="ease-out">
              {data.map((entry, i) => (
                <Cell key={i} fill={fillFor(entry)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div style={{ fontSize: 9, color: G.text, lineHeight: 1.45, marginTop: 6, opacity: 0.85 }}>
        {st(tr, lang, 'cmd_chart_bridge_footnote')}
      </div>
    </div>
  )
}

export function ExecutiveBranchCompareChart({ comparativeIntelligence, tr, lang }) {
  const [metric, setMetric] = useState('ratio')
  const data = useMemo(
    () => extractBranchCompareRows(comparativeIntelligence, metric === 'revenue' ? 'revenue' : 'ratio'),
    [comparativeIntelligence, metric],
  )

  if (!data.length) {
    return (
      <div style={{ fontSize: 12, color: G.text, marginTop: 12 }}>
        {st(tr, lang, 'cmd_chart_branch_empty')}
      </div>
    )
  }

  const fmt = (v) => (metric === 'revenue' ? formatCompact(v) : `${Number(v).toFixed(2)}%`)

  return (
    <div className="cmd-chart-enter" style={{ marginTop: 8 }}>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        {[
          { id: 'ratio', l: st(tr, lang, 'cmd_chart_branch_metric_ratio') },
          { id: 'revenue', l: st(tr, lang, 'cmd_chart_branch_metric_revenue') },
        ].map((b) => (
          <button
            key={b.id}
            type="button"
            onClick={() => setMetric(b.id)}
            style={{
              padding: '5px 10px',
              borderRadius: 8,
              border: `1px solid ${metric === b.id ? G.accent : G.grid}`,
              background: metric === b.id ? 'rgba(0,212,170,0.12)' : 'transparent',
              color: metric === b.id ? G.accent : G.text,
              fontSize: 10,
              fontWeight: 700,
              cursor: 'pointer',
              transition: 'border-color 0.15s ease, background 0.15s ease',
            }}
          >
            {b.l}
          </button>
        ))}
      </div>
      <div style={{ width: '100%', height: Math.min(360, 40 + data.length * 28) }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart layout="vertical" data={data} margin={{ top: 4, right: 16, left: 4, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={G.grid} horizontal={false} />
            <XAxis
              type="number"
              tick={{ fill: G.text, fontSize: 9 }}
              axisLine={{ stroke: G.grid }}
              tickLine={false}
              tickFormatter={(v) => (metric === 'revenue' ? formatCompact(v) : `${v}%`)}
            />
            <YAxis
              type="category"
              dataKey="name"
              width={100}
              tick={{ fill: G.text, fontSize: 9 }}
              axisLine={{ stroke: G.grid }}
              tickLine={false}
            />
            <Tooltip
              content={(props) => <ExecTooltip {...props} formatter={(v) => fmt(v)} />}
              cursor={{ fill: 'rgba(255,255,255,0.04)' }}
            />
            <Bar
              dataKey="value"
              fill={G.violet}
              radius={[0, 4, 4, 0]}
              animationDuration={400}
              animationEasing="ease-out"
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
