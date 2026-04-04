/**
 * Compact branch insights from comparative_intelligence (no ranking table).
 */
import { formatCompactForLang, formatPctForLang } from '../utils/numberFormat.js'
import { strictT as st } from '../utils/strictI18n.js'
import CmdServerText from './CmdServerText.jsx'

const P = {
  border: 'rgba(148,163,184,0.16)',
  text1: '#ffffff',
  text2: '#d1dae6',
  text3: '#9ca8b8',
  accent: '#00d4aa',
  amber: '#fbbf24',
  red: '#f87171',
}

export default function CommandCenterBranchStrip({
  comparativeIntel,
  tr,
  lang,
  onOpenBranches,
  onBranchRankClick,
}) {
  if (!comparativeIntel || typeof comparativeIntel !== 'object') return null

  const br = comparativeIntel.branch_rankings || {}
  const cp = comparativeIntel.cost_pressure || {}
  const eff = comparativeIntel.efficiency_ranking?.by_expense_pct_of_revenue_desc || []
  const hiExp = br.highest_total_expense
  const loEff = br.lowest_expense_pct_of_revenue
  const mom = cp.driving_expense_increase_mom
  const topIneff = eff[0]
  const ofRevBr = st(tr, lang, 'cmd_branch_of_rev')
  const momLab = st(tr, lang, 'cmd_row_mom_expense')
  const rankTitle = st(tr, lang, 'cmd_branch_rank_title')

  const effBars = (eff || [])
    .filter((r) => r?.branch_name != null && r.expense_pct_of_revenue != null && Number.isFinite(Number(r.expense_pct_of_revenue)))
    .slice(0, 4)
  const maxEffPct = effBars.length
    ? Math.max(...effBars.map((r) => Number(r.expense_pct_of_revenue)), 1e-9)
    : 0

  const chips = []
  if (hiExp?.branch_name) {
    chips.push({
      k: 'hi',
      border: P.amber,
      label: st(tr, lang, 'cmd_branch_hi_expense'),
      text: `${hiExp.branch_name} · ${formatCompactForLang(hiExp.total_expense, lang)}`,
    })
  }
  if (mom?.branch_name && mom.mom_delta_total_expense != null) {
    chips.push({
      k: 'mom',
      border: P.red,
      label: st(tr, lang, 'cmd_branch_cost_pressure'),
      text: `${mom.branch_name} · ${momLab} ${formatCompactForLang(mom.mom_delta_total_expense, lang)}`,
    })
  }
  if (loEff?.branch_name && topIneff?.branch_name && String(loEff.branch_name) !== String(topIneff.branch_name)) {
    chips.push({
      k: 'best',
      border: P.accent,
      label: st(tr, lang, 'cmd_branch_best_ratio'),
      text: `${loEff.branch_name} · ${formatPctForLang(loEff.expense_pct_of_revenue, 1, lang)} ${ofRevBr}`,
    })
  } else if (topIneff?.branch_name) {
    chips.push({
      k: 'ineff',
      border: P.amber,
      label: st(tr, lang, 'cmd_branch_eff_rank'),
      text: `${topIneff.branch_name} · ${formatPctForLang(topIneff.expense_pct_of_revenue, 1, lang)} ${ofRevBr}`,
    })
  }

  if (!chips.length) return null

  return (
    <div
      className="cmd-magic-branch-card"
      style={{
        padding: '14px 14px',
      }}
    >
      <div style={{ fontSize: 10, fontWeight: 800, color: P.text3, textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 10 }}>
        {st(tr, lang, 'cmd_branch_intel')}
      </div>
      {effBars.length >= 2 ? (
        <div className="cmd-magic-branch-bar-row" aria-label={rankTitle}>
          <div style={{ fontSize: 9, fontWeight: 800, color: P.text3, textTransform: 'uppercase', letterSpacing: '.08em' }}>{rankTitle}</div>
          {effBars.map((r, i) => {
            const pct = Number(r.expense_pct_of_revenue)
            const w = Math.round((pct / maxEffPct) * 100)
            return (
              <div key={`${r.branch_name}-${i}`}>
                <div className="cmd-magic-branch-bar-label">
                  <span className="cmd-magic-branch-bar-name" title={String(r.branch_name)}>
                    <CmdServerText lang={lang} tr={tr} as="span">
                      {String(r.branch_name)}
                    </CmdServerText>
                  </span>
                  <span style={{ fontVariantNumeric: 'tabular-nums', flexShrink: 0 }}>{formatPctForLang(pct, 1, lang)}</span>
                </div>
                <div className="cmd-magic-branch-bar">
                  <div className="cmd-magic-branch-bar__fill" style={{ width: `${w}%` }} />
                </div>
              </div>
            )
          })}
        </div>
      ) : null}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: effBars.length >= 2 ? 12 : 0 }}>
        {chips.slice(0, 3).map((c) => (
          <div
            key={c.k}
            style={{
              padding: '8px 10px',
              borderRadius: 10,
              borderLeft: `3px solid ${c.border}`,
              background: 'rgba(255,255,255,0.04)',
              border: `1px solid ${P.border}`,
            }}
          >
            <div style={{ fontSize: 9, fontWeight: 800, color: P.text3, textTransform: 'uppercase', marginBottom: 4 }}>{c.label}</div>
            <div style={{ fontSize: 12, fontWeight: 700, color: P.text1, lineHeight: 1.35 }}>
              <CmdServerText lang={lang} tr={tr} as="span">
                {c.text}
              </CmdServerText>
            </div>
          </div>
        ))}
      </div>
      {onOpenBranches ? (
        <button
          type="button"
          onClick={onOpenBranches}
          style={{
            marginTop: 10,
            padding: '6px 12px',
            borderRadius: 8,
            border: `1px solid ${P.border}`,
            background: 'rgba(255,255,255,0.05)',
            color: P.text2,
            fontSize: 11,
            fontWeight: 700,
            cursor: 'pointer',
          }}
        >
          {st(tr, lang, 'cmd_open_branches')}
        </button>
      ) : null}
    </div>
  )
}
