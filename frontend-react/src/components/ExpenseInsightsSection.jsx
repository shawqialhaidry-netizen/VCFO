/**
 * ExpenseInsightsSection — structured expense intelligence from GET /executive data.expense_intelligence
 */
import { formatCompact } from '../utils/numberFormat.js'
import { strictT as st } from '../utils/strictI18n.js'

const P = {
  surface: 'linear-gradient(165deg, rgba(17,24,39,0.98) 0%, rgba(15,23,42,0.99) 100%)',
  border: 'rgba(148,163,184,0.14)',
  glow: '0 0 0 1px rgba(0,212,170,0.08), 0 12px 40px rgba(0,0,0,0.42)',
  accent: '#00d4aa',
  text1: '#f8fafc',
  text2: '#94a3b8',
  text3: '#64748b',
}

function row(label, value) {
  return (
    <div style={{ padding: '6px 0', borderBottom: `1px solid ${P.border}` }}>
      <div
        style={{
          fontSize: 8,
          fontWeight: 800,
          color: P.text3,
          textTransform: 'uppercase',
          letterSpacing: '.07em',
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: 12, fontWeight: 650, color: P.text1, marginTop: 3, lineHeight: 1.35 }}>{value}</div>
    </div>
  )
}

export default function ExpenseInsightsSection({
  expenseIntel,
  tr,
  lang = 'en',
  period,
  embedded = false,
  onDrillExpense,
  visualTier = 2,
}) {
  const tier = Number(visualTier) || 2
  const avail = expenseIntel && expenseIntel.available === true
  const weakMsg = st(tr, lang, 'cmd_expense_weak_data')

  const top = expenseIntel?.top_category
  const mom = expenseIntel?.mom_change
  const ratio = expenseIntel?.expense_ratio
  const ratioPrior = expenseIntel?.expense_ratio_prior
  const grow = expenseIntel?.largest_increasing_category
  const totals = expenseIntel?.totals

  const momTe = mom?.total_expense_pct
  const momTeStr =
    momTe != null && Number.isFinite(Number(momTe))
      ? `${Number(momTe) >= 0 ? '+' : ''}${Number(momTe).toFixed(1)}%`
      : null

  const pp = mom?.expense_pct_of_revenue_pp
  const ratioTrend =
    pp != null && Number.isFinite(Number(pp))
      ? Number(pp) > 0.5
        ? st(tr, lang, 'cmd_expense_ratio_up')
        : Number(pp) < -0.5
          ? st(tr, lang, 'cmd_expense_ratio_down')
          : st(tr, lang, 'cmd_expense_ratio_flat')
      : null

  const topLine =
    top?.name != null && top.amount != null
      ? `${String(top.name)} · ${formatCompact(top.amount)}`
      : null

  const growLine =
    grow?.name != null
      ? `${String(grow.name)} · ${grow.pct_change != null ? `${grow.pct_change >= 0 ? '+' : ''}${Number(grow.pct_change).toFixed(1)}% MoM` : formatCompact(grow.absolute_change || 0)}`
      : null

  const ofRev = st(tr, lang, 'cmd_branch_of_rev')
  const ratioLine =
    ratio != null && Number.isFinite(Number(ratio))
      ? ratioTrend
        ? `${Number(ratio).toFixed(1)}% ${ofRev} (${ratioTrend})`
        : `${Number(ratio).toFixed(1)}% ${ofRev}`
      : null

  const totalLine =
    totals?.total_expense != null && totals?.revenue != null
      ? `${st(tr, lang, 'cmd_expense_total_label')} ${formatCompact(totals.total_expense)} · ${st(tr, lang, 'cmd_expense_rev_label')} ${formatCompact(totals.revenue)}`
      : null

  const titleFs = tier === 3 ? 9 : 10
  const subFs = tier === 3 ? 8 : 9
  const headerOpacity = tier === 3 ? 0.88 : 1

  return (
    <div
      role={onDrillExpense ? 'button' : undefined}
      tabIndex={onDrillExpense ? 0 : undefined}
      onClick={onDrillExpense || undefined}
      onKeyDown={
        onDrillExpense
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onDrillExpense()
              }
            }
          : undefined
      }
      title={onDrillExpense ? st(tr, lang, 'cmd_drill_expense_hint') : undefined}
      style={{
        background: embedded ? 'rgba(255,255,255,0.02)' : P.surface,
        border: embedded ? `1px dashed ${P.border}` : `1px solid ${P.border}`,
        borderRadius: embedded ? 14 : 16,
        boxShadow: embedded ? 'none' : P.glow,
        padding: embedded ? (tier === 3 ? '10px 12px' : '12px 14px') : tier === 3 ? '12px 14px' : '14px 16px',
        cursor: onDrillExpense ? 'pointer' : undefined,
        outline: 'none',
        opacity: tier === 3 ? 0.96 : 1,
      }}
    >
      <div style={{ marginBottom: tier === 3 ? 6 : 8 }}>
        <div
          style={{
            fontSize: titleFs,
            fontWeight: 800,
            color: P.accent,
            letterSpacing: '.08em',
            textTransform: 'uppercase',
            opacity: headerOpacity,
          }}
        >
          {st(tr, lang, 'cmd_expense_insights')}
        </div>
        <div style={{ fontSize: subFs, color: P.text3, marginTop: 3, lineHeight: 1.35, opacity: tier === 3 ? 0.85 : 1 }}>
          {st(tr, lang, 'cmd_expense_insights_sub')}
        </div>
      </div>

      {!avail ? (
        <div style={{ fontSize: 12, color: P.text2, lineHeight: 1.45, padding: '6px 0' }}>{weakMsg}</div>
      ) : (
        <div>
          {period ? (
            <div style={{ fontSize: tier === 3 ? 8 : 9, color: P.text3, marginBottom: 6, fontWeight: 600 }}>
              {st(tr, lang, 'cmd_expense_period')}: {period}
            </div>
          ) : null}
          {totalLine ? row(st(tr, lang, 'cmd_expense_totals_row'), totalLine) : null}
          {topLine
            ? row(st(tr, lang, 'cmd_expense_top_driver'), topLine)
            : row(st(tr, lang, 'cmd_expense_top_driver'), st(tr, lang, 'cmd_expense_no_category_split'))}
          {momTeStr != null
            ? row(
                st(tr, lang, 'cmd_expense_mom_te'),
                `${momTeStr}${ratioPrior != null && ratio != null ? ` · ${st(tr, lang, 'cmd_expense_ratio_label')} ${Number(ratio).toFixed(1)}%` : ''}`
              )
            : row(st(tr, lang, 'cmd_expense_mom_te'), st(tr, lang, 'cmd_expense_mom_na'))}
          {ratioLine ? row(st(tr, lang, 'cmd_expense_ratio_row'), ratioLine) : null}
          {growLine
            ? row(st(tr, lang, 'cmd_expense_fastest_growing'), growLine)
            : row(st(tr, lang, 'cmd_expense_fastest_growing'), st(tr, lang, 'cmd_expense_no_mover'))}
        </div>
      )}
    </div>
  )
}
