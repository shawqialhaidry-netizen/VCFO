/**
 * Command Center sections — GET /executive payload only; presentation only.
 */
import { formatCompact, formatMultiple } from '../utils/numberFormat.js'
import { factOverlapsWhy } from '../utils/buildExecutiveNarrative.js'

const P = {
  surface: 'linear-gradient(165deg, rgba(17,24,39,0.98) 0%, rgba(15,23,42,0.99) 100%)',
  border: 'rgba(148,163,184,0.14)',
  glow: '0 0 0 1px rgba(0,212,170,0.08), 0 12px 40px rgba(0,0,0,0.42), 0 0 100px -24px rgba(124,92,252,0.12)',
  accent: '#00d4aa',
  green: '#34d399',
  red: '#f87171',
  amber: '#fbbf24',
  violet: '#7c5cfc',
  text1: '#f8fafc',
  text2: '#94a3b8',
  text3: '#64748b',
}

function looksLikeRawKey(v) {
  return typeof v === 'string' && /^(exec_|cmd_|nav_|dq_)[a-z0-9_]+$/i.test(v.trim())
}

function Tx(tr, key, en) {
  try {
    const v = tr(key)
    if (v == null || v === '' || v === key || looksLikeRawKey(v)) return en
    return v
  } catch {
    return en
  }
}

function sectionShell(title, subtitle, children) {
  return (
    <div
      style={{
        background: P.surface,
        border: `1px solid ${P.border}`,
        borderRadius: 16,
        boxShadow: P.glow,
        padding: '20px 22px',
      }}
    >
      <div style={{ marginBottom: 14 }}>
        <div
          style={{
            fontSize: 11,
            fontWeight: 800,
            color: P.accent,
            letterSpacing: '.08em',
            textTransform: 'uppercase',
          }}
        >
          {title}
        </div>
        {subtitle ? (
          <div style={{ fontSize: 10, color: P.text3, marginTop: 5, lineHeight: 1.45 }}>{subtitle}</div>
        ) : null}
      </div>
      {children}
    </div>
  )
}

function ratioVal(m) {
  if (m == null) return null
  if (typeof m === 'number' && Number.isFinite(m)) return m
  if (typeof m === 'object' && m.value != null && Number.isFinite(Number(m.value))) return Number(m.value)
  return null
}

function narrativeBlob(narrative) {
  if (!narrative) return ''
  const parts = [
    ...(narrative.whatChanged?.lines || []),
    ...(narrative.why?.lines || []),
    ...(narrative.whatToDo?.lines || []),
  ]
  return parts.join(' | ').toLowerCase()
}

function pickSyntheticSignalCard(main, intel, tr) {
  const cf = main?.cashflow
  const cfOk = cf && typeof cf === 'object' && cf.error !== 'no data'
  if (cfOk && cf.operating_cashflow != null && Number.isFinite(Number(cf.operating_cashflow))) {
    let v = formatCompact(cf.operating_cashflow)
    if (cf.operating_cashflow_mom != null && Number.isFinite(Number(cf.operating_cashflow_mom))) {
      const m = Number(cf.operating_cashflow_mom)
      v += ` (${m >= 0 ? '+' : ''}${m.toFixed(1)}% MoM)`
    }
    return {
      key: 'syn_ocf',
      label: Tx(tr, 'cmd_sig_ocf', 'Operating cash flow'),
      value: v,
    }
  }
  const stm = main?.statements
  const ocf2 = stm?.summary?.operating_cashflow ?? stm?.cashflow?.operating_cashflow
  if (ocf2 != null && Number.isFinite(Number(ocf2))) {
    return {
      key: 'syn_ocf2',
      label: Tx(tr, 'cmd_sig_ocf', 'Operating cash flow'),
      value: formatCompact(ocf2),
    }
  }
  const wc =
    main?.kpi_block?.kpis?.working_capital?.value ??
    stm?.summary?.working_capital ??
    stm?.balance_sheet?.working_capital
  if (wc != null && Number.isFinite(Number(wc))) {
    return {
      key: 'syn_wc',
      label: Tx(tr, 'cmd_sig_wc', 'Working capital'),
      value: formatCompact(wc),
    }
  }
  const cr = ratioVal(intel?.ratios?.liquidity?.current_ratio)
  if (cr != null) {
    return {
      key: 'syn_cr',
      label: Tx(tr, 'cmd_sig_liquidity', 'Liquidity (current ratio)'),
      value: formatMultiple(cr),
    }
  }
  return null
}

/** Branch name if the inefficient-branch key signal card is shown (for deduping branch intel rows). */
export function keySignalsShowsInefficientBranch(comparativeIntel, narrative) {
  const ineff = comparativeIntel?.cost_pressure?.most_inefficient_branch
  if (!ineff?.branch_name) return null
  let ineffLine =
    ineff.expense_pct_of_revenue != null
      ? `${ineff.branch_name} · ${ineff.expense_pct_of_revenue}% of revenue`
      : ineff.branch_name
  const blob = narrativeBlob(narrative)
  if (ineffLine && blob.includes(String(ineff.branch_name).toLowerCase())) return null
  return ineff.branch_name
}

/** Always renders at least one signal (synthetic or stable ops message). */
export function KeySignalsSection({ financialBrain, comparativeIntel, alerts, narrative, tr, main, intel }) {
  const cat = financialBrain?.why?.links?.category_driver_mom
  let costDriver =
    cat?.category != null
      ? `${cat.category}${cat.delta != null ? ` · ${formatCompact(cat.delta)}` : ''}`
      : null
  const blob = narrativeBlob(narrative)
  if (costDriver && cat?.category && blob.includes(String(cat.category).toLowerCase())) {
    costDriver = null
  }

  const ineff = comparativeIntel?.cost_pressure?.most_inefficient_branch
  let ineffLine =
    ineff?.branch_name && ineff.expense_pct_of_revenue != null
      ? `${ineff.branch_name} · ${ineff.expense_pct_of_revenue}% of revenue`
      : ineff?.branch_name || null
  if (ineffLine && ineff?.branch_name && blob.includes(String(ineff.branch_name).toLowerCase())) {
    ineffLine = null
  }

  const hi = Array.isArray(alerts) ? alerts.find((a) => a.severity === 'high') : null
  const crit = hi || (Array.isArray(alerts) ? alerts[0] : null)
  let anomalyLine = crit?.title || crit?.message || null
  if (anomalyLine && blob.includes(String(anomalyLine).toLowerCase().slice(0, 48))) {
    anomalyLine = null
  }

  const cards = []
  if (costDriver) {
    cards.push({
      key: 'cd',
      label: Tx(tr, 'cmd_sig_cost_driver', 'Top cost driver'),
      value: costDriver,
    })
  }
  if (ineffLine) {
    cards.push({
      key: 'ineff',
      label: Tx(tr, 'cmd_sig_ineff_branch', 'Most inefficient branch'),
      value: ineffLine,
    })
  }
  if (anomalyLine) {
    cards.push({
      key: 'alert',
      label: Tx(tr, 'cmd_sig_critical', 'Critical signal'),
      value: anomalyLine,
    })
  }

  if (!cards.length) {
    const syn = pickSyntheticSignalCard(main, intel, tr)
    if (syn && !factOverlapsWhy(narrative, syn.value)) cards.push(syn)
  }
  if (!cards.length) {
    cards.push({
      key: 'syn_stable',
      label: Tx(tr, 'cmd_sig_status', 'Status'),
      value: Tx(tr, 'cmd_sig_no_anomalies', 'No critical anomalies detected. Operations stable.'),
    })
  }

  return sectionShell(
    Tx(tr, 'cmd_key_signals', 'Key signals'),
    Tx(tr, 'cmd_key_signals_sub', 'Scannable deltas — details sit in the narrative above.'),
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
      {cards.map((c) => (
        <div
          key={c.key}
          style={{
            flex: '1 1 160px',
            minWidth: 158,
            background: 'rgba(255,255,255,0.03)',
            border: `1px solid ${P.border}`,
            borderRadius: 12,
            padding: '14px 16px',
            borderTop: `3px solid ${P.violet}`,
            boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)',
          }}
        >
          <div
            style={{
              fontSize: 9,
              fontWeight: 800,
              color: P.text3,
              textTransform: 'uppercase',
              letterSpacing: '.08em',
              marginBottom: 8,
            }}
          >
            {c.label}
          </div>
          <div style={{ fontSize: 13, fontWeight: 650, color: P.text1, lineHeight: 1.45 }}>{c.value}</div>
        </div>
      ))}
    </div>
  )
}

/**
 * Branch intel: ranking + pressure + efficiency — skips row duplicated by key-signal inefficient branch.
 */
export function BranchIntelligenceSection({
  comparativeIntel,
  tr,
  onOpenBranches,
  duplicateIneffBranchName,
  narrative,
}) {
  if (!comparativeIntel || typeof comparativeIntel !== 'object') return null

  const br = comparativeIntel.branch_rankings || {}
  const cp = comparativeIntel.cost_pressure || {}
  const eff = comparativeIntel.efficiency_ranking?.by_expense_pct_of_revenue_desc || []

  const hiExp = br.highest_total_expense
  const loEff = br.lowest_expense_pct_of_revenue
  const mom = cp.driving_expense_increase_mom
  const topIneff = eff[0]

  const dup = duplicateIneffBranchName ? String(duplicateIneffBranchName).toLowerCase() : null
  const momLab = Tx(tr, 'cmd_row_mom_expense', 'MoM expense +')

  const rows = []
  if (hiExp?.branch_name) {
    rows.push({
      k: 'hiexp',
      label: Tx(tr, 'cmd_branch_hi_expense', 'Highest expense (branch)'),
      text: `${hiExp.branch_name} · ${formatCompact(hiExp.total_expense)} (${hiExp.expense_pct_of_revenue}% of revenue)`,
    })
  }
  if (topIneff?.branch_name && (!dup || String(topIneff.branch_name).toLowerCase() !== dup)) {
    rows.push({
      k: 'ineffrank',
      label: Tx(tr, 'cmd_branch_eff_rank', 'Least efficient (expense % of revenue)'),
      text: `${topIneff.branch_name} · ${topIneff.expense_pct_of_revenue}% of revenue`,
    })
  }
  if (mom?.branch_name && mom.mom_delta_total_expense != null) {
    rows.push({
      k: 'mom',
      label: Tx(tr, 'cmd_branch_cost_pressure', 'Cost pressure (MoM)'),
      text: `${mom.branch_name} · ${momLab}${formatCompact(mom.mom_delta_total_expense)}`,
    })
  }
  if (loEff?.branch_name && (!dup || String(loEff.branch_name).toLowerCase() !== dup)) {
    rows.push({
      k: 'loeff',
      label: Tx(tr, 'cmd_branch_best_ratio', 'Best expense ratio'),
      text: `${loEff.branch_name} · ${loEff.expense_pct_of_revenue}% of revenue`,
    })
  }

  const visible = rows.filter((r) => !factOverlapsWhy(narrative, r.text))

  const emptyMsg = Tx(
    tr,
    'cmd_branch_no_pressure',
    'No branch-level pressure detected this period.'
  )

  return sectionShell(
    Tx(tr, 'cmd_branch_intel', 'Branch intelligence'),
    Tx(tr, 'cmd_branch_intel_sub', 'Rankings and pressure from the same executive scope.'),
    <>
      <div>
        {visible.length ? (
          visible.map((r, i) => (
            <div
              key={r.k}
              style={{
                padding: '10px 0',
                borderBottom: i < visible.length - 1 ? `1px solid ${P.border}` : 'none',
              }}
            >
              <div
                style={{
                  fontSize: 9,
                  fontWeight: 800,
                  color: P.text3,
                  textTransform: 'uppercase',
                  letterSpacing: '.07em',
                }}
              >
                {r.label}
              </div>
              <div style={{ fontSize: 13, color: P.text1, marginTop: 6, lineHeight: 1.45 }}>{r.text}</div>
            </div>
          ))
        ) : (
          <div style={{ fontSize: 13, color: P.text2, lineHeight: 1.55, padding: '6px 0' }}>{emptyMsg}</div>
        )}
      </div>
      {onOpenBranches ? (
        <button
          type="button"
          onClick={onOpenBranches}
          style={{
            marginTop: 14,
            padding: '10px 14px',
            borderRadius: 10,
            border: `1px solid ${P.border}`,
            background: 'rgba(0,212,170,0.06)',
            color: P.accent,
            fontSize: 12,
            fontWeight: 700,
            cursor: 'pointer',
            width: 'auto',
          }}
        >
          {Tx(tr, 'cmd_open_branches', 'Open branches →')}
        </button>
      ) : null}
    </>
  )
}

function priorityLabel(priority, tr) {
  const p = (priority || '').toLowerCase()
  if (p === 'high') return Tx(tr, 'dec_priority_high', 'High priority')
  if (p === 'medium') return Tx(tr, 'dec_priority_medium', 'Medium priority')
  return Tx(tr, 'dec_priority_quick', 'Quick win')
}

function priorityColor(priority) {
  const p = (priority || '').toLowerCase()
  if (p === 'high') return P.red
  if (p === 'medium') return P.amber
  return P.accent
}

/** expense_decisions_v2; max 3; always at least one row (baseline if empty). */
export function DecisionsSection({ expenseDecisionsV2, tr }) {
  let list = Array.isArray(expenseDecisionsV2) ? expenseDecisionsV2.filter((d) => d && d.title) : []
  if (!list.length) {
    list = [
      {
        decision_id: '_cmd_baseline',
        title: Tx(
          tr,
          'cmd_decision_baseline',
          'Maintain current operational discipline and monitor cash flow closely.'
        ),
        rationale: null,
        priority: 'medium',
      },
    ]
  }

  return sectionShell(
    Tx(tr, 'cmd_decisions', 'Prioritized decisions'),
    Tx(tr, 'cmd_decisions_sub', 'Expense intelligence (v2) — act on these first.'),
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {list.slice(0, 3).map((d, idx) => {
        const pr = priorityLabel(d.priority, tr)
        const pc = priorityColor(d.priority)
        const first = idx === 0
        return (
          <div
            key={d.decision_id || d.title}
            style={{
              padding: first ? '20px 22px' : '12px 16px',
              borderRadius: 14,
              border: first ? `1px solid rgba(0,212,170,0.38)` : `1px solid ${P.border}`,
              borderLeft: first ? `6px solid ${pc}` : `4px solid ${pc}`,
              background: first ? 'rgba(0,212,170,0.08)' : 'rgba(255,255,255,0.02)',
              boxShadow: first
                ? '0 0 28px rgba(0,212,170,0.14), inset 0 1px 0 rgba(255,255,255,0.06)'
                : 'inset 0 1px 0 rgba(255,255,255,0.04)',
            }}
          >
            <div
              style={{
                fontSize: first ? 11 : 10,
                fontWeight: 800,
                color: pc,
                textTransform: 'uppercase',
                letterSpacing: '.07em',
              }}
            >
              {pr}
            </div>
            <div
              style={{
                fontSize: first ? 17 : 15,
                fontWeight: 800,
                color: P.text1,
                lineHeight: 1.35,
                marginTop: first ? 10 : 8,
              }}
            >
              {d.title}
            </div>
            {d.rationale ? (
              <div
                style={{
                  fontSize: first ? 13 : 12,
                  color: P.text2,
                  marginTop: first ? 10 : 8,
                  lineHeight: 1.55,
                }}
              >
                {d.rationale}
              </div>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}
