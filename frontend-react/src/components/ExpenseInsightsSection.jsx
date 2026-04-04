/**
 * ExpenseInsightsSection — structured expense intelligence from GET /executive data.expense_intelligence
 */
import '../styles/commandCenterStructure.css'
import { formatCompactForLang, formatPctForLang, formatSignedPctForLang } from '../utils/numberFormat.js'
import { strictT as st } from '../utils/strictI18n.js'
import { CLAMP_FADE_MASK_SHORT } from '../utils/serverTextUi.js'
import CmdServerText from './CmdServerText.jsx'
import CmdSparkline from './CmdSparkline.jsx'

const P = {
  surface: 'linear-gradient(165deg, rgba(17,24,39,0.98) 0%, rgba(15,23,42,0.99) 100%)',
  border: 'rgba(148,163,184,0.16)',
  cardShadow: '0 4px 28px rgba(0,0,0,0.32)',
  accent: '#00d4aa',
  text1: '#ffffff',
  text2: '#d1dae6',
  text3: '#9ca8b8',
}

function row(label, value, lang, tr) {
  return (
    <div style={{ padding: '6px 0', borderBottom: `1px solid ${P.border}` }}>
      <div className="cmd-field-label" style={{ marginBottom: 4 }}>
        {label}
      </div>
      <div
        className="cmd-card-data-value"
        style={{
          marginTop: 4,
          ...CLAMP_FADE_MASK_SHORT,
        }}
      >
        <CmdServerText lang={lang} tr={tr} as="span" style={{ color: 'inherit' }}>
          {value}
        </CmdServerText>
      </div>
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
      ? formatSignedPctForLang(Number(momTe), 1, lang)
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
      ? `${String(top.name)} · ${formatCompactForLang(top.amount, lang)}`
      : null

  const growLine =
    grow?.name != null
      ? `${String(grow.name)} · ${
          grow.pct_change != null
            ? `${formatSignedPctForLang(Number(grow.pct_change), 1, lang)} ${st(tr, lang, 'mom_label')}`
            : formatCompactForLang(grow.absolute_change || 0, lang)
        }`
      : null

  const ofRev = st(tr, lang, 'cmd_branch_of_rev')
  const ratioLine =
    ratio != null && Number.isFinite(Number(ratio))
      ? ratioTrend
        ? `${formatPctForLang(ratio, 1, lang)} ${ofRev} (${ratioTrend})`
        : `${formatPctForLang(ratio, 1, lang)} ${ofRev}`
      : null

  const totalLine =
    totals?.total_expense != null && totals?.revenue != null
      ? `${st(tr, lang, 'cmd_expense_total_label')} ${formatCompactForLang(totals.total_expense, lang)} · ${st(tr, lang, 'cmd_expense_rev_label')} ${formatCompactForLang(totals.revenue, lang)}`
      : null

  const shellCls = [
    'cmd-card-hover',
    embedded ? '' : 'cmd-panel',
    embedded ? '' : tier === 3 ? 'cmd-panel--tier3' : '',
    embedded ? '' : tier === 3 ? 'cmd-panel--pad-3' : 'cmd-panel--pad-2',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div
      className={shellCls}
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
        background: embedded ? 'rgba(255,255,255,0.032)' : undefined,
        border: embedded ? `1px solid ${P.border}` : undefined,
        borderRadius: 14,
        boxShadow: embedded ? 'none' : undefined,
        padding: embedded ? (tier === 3 ? '14px 16px' : '16px 18px') : undefined,
        cursor: onDrillExpense ? 'pointer' : undefined,
        outline: 'none',
        opacity: tier === 3 ? 0.98 : 1,
      }}
    >
      <div style={{ marginBottom: tier === 3 ? 10 : 14 }}>
        <div className="cmd-card-title">{st(tr, lang, 'cmd_expense_insights')}</div>
        <div className="cmd-muted-foreign" style={{ marginTop: 4 }}>
          {st(tr, lang, 'cmd_expense_insights_sub')}
        </div>
      </div>

      {avail && ratio != null && Number.isFinite(Number(ratio)) ? (
        <div style={{ marginBottom: 14, paddingBottom: 12, borderBottom: `1px solid ${P.border}` }}>
          <div className="cmd-field-label" style={{ marginBottom: 2 }}>
            {st(tr, lang, 'cmd_expense_ratio_row')}
          </div>
          <div
            className="cmd-ei-metric-hero"
            style={{
              color:
                pp != null && Number.isFinite(Number(pp))
                  ? Number(pp) > 0.5
                    ? P.red
                    : Number(pp) < -0.5
                      ? P.green
                      : P.text1
                  : P.text1,
            }}
          >
            {formatPctForLang(Number(ratio), 1, lang)}
            <span className="cmd-muted-foreign" style={{ fontSize: '0.5em', fontWeight: 700, marginLeft: 6 }}>
              {ofRev}
            </span>
          </div>
          {momTeStr != null ? (
            <div className="cmd-muted-foreign" style={{ marginTop: 8, fontSize: 11 }}>
              {st(tr, lang, 'cmd_expense_mom_te')}: {momTeStr}
            </div>
          ) : null}
          {ratioTrend ? (
            <div className="cmd-muted-foreign" style={{ marginTop: 4, fontSize: 11 }}>
              {ratioTrend}
            </div>
          ) : null}
        </div>
      ) : null}

      {!avail ? (
        <div style={{ fontSize: 14, color: P.text2, lineHeight: 1.55, padding: '10px 0' }}>{weakMsg}</div>
      ) : (
        <div>
          {period ? (
            <div style={{ fontSize: 12, color: P.text3, marginBottom: 10, fontWeight: 600 }}>
              {st(tr, lang, 'cmd_expense_period')}: {period}
            </div>
          ) : null}
          {totalLine ? row(st(tr, lang, 'cmd_expense_totals_row'), totalLine, lang, tr) : null}
          {topLine
            ? row(st(tr, lang, 'cmd_expense_top_driver'), topLine, lang, tr)
            : row(st(tr, lang, 'cmd_expense_top_driver'), st(tr, lang, 'cmd_expense_no_category_split'), lang, tr)}
          {momTeStr != null
            ? row(
                st(tr, lang, 'cmd_expense_mom_te'),
                `${momTeStr}${ratioPrior != null && ratio != null ? ` · ${st(tr, lang, 'cmd_expense_ratio_label')} ${formatPctForLang(Number(ratio), 1, lang)}` : ''}`,
                lang,
                tr
              )
            : row(st(tr, lang, 'cmd_expense_mom_te'), st(tr, lang, 'cmd_expense_mom_na'), lang, tr)}
          {ratioLine && !(avail && ratio != null && Number.isFinite(Number(ratio)))
            ? row(st(tr, lang, 'cmd_expense_ratio_row'), ratioLine, lang, tr)
            : null}
          {growLine
            ? row(st(tr, lang, 'cmd_expense_fastest_growing'), growLine, lang, tr)
            : row(st(tr, lang, 'cmd_expense_fastest_growing'), st(tr, lang, 'cmd_expense_no_mover'), lang, tr)}
          <CmdSparkline mom={momTe} />
        </div>
      )}
    </div>
  )
}
