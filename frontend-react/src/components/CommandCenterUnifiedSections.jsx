/**
 * Command Center sections — GET /executive payload only; presentation only.
 */
import { useState } from 'react'
import { useCountUp } from '../hooks/useCountUp.js'
import { formatCompact, formatMultiple } from '../utils/numberFormat.js'
import { factOverlapsWhy } from '../utils/buildExecutiveNarrative.js'
import { strictT as st } from '../utils/strictI18n.js'
import { CLAMP_FADE_MASK_SHORT } from '../utils/serverTextUi.js'
import CmdServerText from './CmdServerText.jsx'

const P = {
  surface: 'linear-gradient(165deg, rgba(17,24,39,0.98) 0%, rgba(15,23,42,0.99) 100%)',
  border: 'rgba(148,163,184,0.14)',
  cardShadow: '0 4px 24px rgba(0,0,0,0.22)',
  accent: '#00d4aa',
  green: '#34d399',
  red: '#f87171',
  amber: '#fbbf24',
  text1: '#f8fafc',
  text2: '#94a3b8',
  text3: '#64748b',
}

function sectionShell(title, subtitle, children, visualTier = 2, headerAction = null) {
  const tier = Number(visualTier) || 2
  const boxShadow =
    tier === 2 ? P.cardShadow : tier === 3 ? '0 2px 16px rgba(0,0,0,0.2)' : P.cardShadow
  const titleFs = tier === 3 ? 9 : 10
  const titleOpacity = tier === 3 ? 0.88 : 1
  const subOpacity = tier === 3 ? 0.85 : 0.95
  const titleBlock = (
    <>
      <div
        style={{
          fontSize: titleFs,
          fontWeight: 800,
          color: P.text1,
          letterSpacing: '.08em',
          textTransform: 'uppercase',
          opacity: titleOpacity,
        }}
      >
        {title}
      </div>
      {subtitle ? (
        <div
          style={{ fontSize: tier === 3 ? 8 : 9, color: P.text3, marginTop: 3, lineHeight: 1.35, opacity: subOpacity }}
        >
          {subtitle}
        </div>
      ) : null}
    </>
  )
  return (
    <div
      style={{
        background: P.surface,
        border: `1px solid ${P.border}`,
        borderRadius: 14,
        boxShadow,
        padding: tier === 3 ? '12px 14px 14px' : '14px 16px 16px',
        height: '100%',
        opacity: tier === 3 ? 0.96 : 1,
      }}
    >
      <div style={{ marginBottom: tier === 3 ? 8 : 12 }}>
        {headerAction ? (
          <button
            type="button"
            onClick={headerAction.onClick}
            title={headerAction.title || undefined}
            style={{
              display: 'block',
              width: '100%',
              margin: 0,
              padding: 0,
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              textAlign: 'inherit',
              borderRadius: 8,
            }}
          >
            {titleBlock}
          </button>
        ) : (
          titleBlock
        )}
        {headerAction?.hint ? (
          <div style={{ fontSize: 8, color: P.text3, marginTop: 4, opacity: 0.9, lineHeight: 1.35 }}>
            {headerAction.hint}
          </div>
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

function pickSyntheticSignalCard(main, intel, tr, lang) {
  const cf = main?.cashflow
  const cfOk = cf && typeof cf === 'object' && cf.error !== 'no data'
  if (cfOk && cf.operating_cashflow != null && Number.isFinite(Number(cf.operating_cashflow))) {
    let v = formatCompact(cf.operating_cashflow)
    if (cf.operating_cashflow_mom != null && Number.isFinite(Number(cf.operating_cashflow_mom))) {
      const m = Number(cf.operating_cashflow_mom)
      v += ` (${m >= 0 ? '+' : ''}${m.toFixed(1)}% ${st(tr, lang, 'mom_label')})`
    }
    return {
      key: 'syn_ocf',
      label: st(tr, lang, 'cmd_sig_ocf'),
      value: v,
    }
  }
  const stm = main?.statements
  const ocf2 = stm?.summary?.operating_cashflow ?? stm?.cashflow?.operating_cashflow
  if (ocf2 != null && Number.isFinite(Number(ocf2))) {
    return {
      key: 'syn_ocf2',
      label: st(tr, lang, 'cmd_sig_ocf'),
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
      label: st(tr, lang, 'cmd_sig_wc'),
      value: formatCompact(wc),
    }
  }
  const cr = ratioVal(intel?.ratios?.liquidity?.current_ratio)
  if (cr != null) {
    return {
      key: 'syn_cr',
      label: st(tr, lang, 'cmd_sig_liquidity'),
      value: formatMultiple(cr),
    }
  }
  return null
}

/** Branch name if the inefficient-branch key signal card is shown (for deduping branch intel rows). */
export function keySignalsShowsInefficientBranch(comparativeIntel, narrative, tr, lang) {
  const ineff = comparativeIntel?.cost_pressure?.most_inefficient_branch
  if (!ineff?.branch_name) return null
  const ofRev = st(tr, lang, 'cmd_branch_of_rev')
  let ineffLine =
    ineff.expense_pct_of_revenue != null
      ? `${ineff.branch_name} · ${ineff.expense_pct_of_revenue}% ${ofRev}`
      : ineff.branch_name
  const blob = narrativeBlob(narrative)
  if (ineffLine && blob.includes(String(ineff.branch_name).toLowerCase())) return null
  return ineff.branch_name
}

function expenseIntelSignalCards(expenseIntel, comparativeIntel, tr, lang) {
  if (!expenseIntel || expenseIntel.available !== true) return []
  const out = []
  const top = expenseIntel.top_category
  if (top?.name != null && top.amount != null) {
    let value = `${top.name} · ${formatCompact(top.amount)}`
    const share = top.share_of_cost_pct
    const mam = top.amount_mom_pct
    if (share != null && Number.isFinite(Number(share))) {
      const sm =
        mam != null && Number.isFinite(Number(mam))
          ? ` (${Number(mam) >= 0 ? '+' : ''}${Number(mam).toFixed(1)}%)`
          : ''
      value = `${top.name} = ${Number(share).toFixed(0)}% ${st(tr, lang, 'cmd_ei_pct_of_cost')}${sm}`
    }
    out.push({
      key: 'ei_top',
      label: st(tr, lang, 'cmd_sig_top_cost_driver'),
      value,
    })
  }
  const momBr = comparativeIntel?.cost_pressure?.driving_expense_increase_mom
  if (momBr?.branch_name) {
    out.push({
      key: 'ei_branch_pressure',
      label: st(tr, lang, 'cmd_sig_branch_pressure'),
      value: `${String(momBr.branch_name)} = ${st(tr, lang, 'cmd_sig_highest_pressure')}`,
    })
  }
  const ratio = expenseIntel.expense_ratio
  const pp = expenseIntel.mom_change?.expense_pct_of_revenue_pp
  if (ratio != null && Number.isFinite(Number(ratio))) {
    let dir = ''
    if (pp != null && Number.isFinite(Number(pp))) {
      if (Number(pp) > 0.5) dir = ` · ${st(tr, lang, 'cmd_sig_ratio_trend_up')}`
      else if (Number(pp) < -0.5) dir = ` · ${st(tr, lang, 'cmd_sig_ratio_trend_down')}`
    }
    const ofRev = st(tr, lang, 'cmd_branch_of_rev')
    out.push({
      key: 'ei_ratio',
      label: st(tr, lang, 'cmd_sig_expense_ratio_signal'),
      value: `${Number(ratio).toFixed(1)}% ${ofRev}${dir}`,
    })
  }
  const g = expenseIntel.largest_increasing_category
  if (g?.name) {
    const pc = g.pct_change
    const val =
      pc != null && Number.isFinite(Number(pc))
        ? `${g.name} · ${Number(pc) >= 0 ? '+' : ''}${Number(pc).toFixed(1)}% ${st(tr, lang, 'mom_label')}`
        : g.absolute_change != null
          ? `${g.name} · ${formatCompact(g.absolute_change)}`
          : String(g.name)
    out.push({
      key: 'ei_grow',
      label: st(tr, lang, 'cmd_sig_expense_growth_cat'),
      value: val,
    })
  }
  return out
}

/** Always renders at least one signal (synthetic or stable ops message). */
export function KeySignalsSection({
  financialBrain,
  comparativeIntel,
  alerts,
  narrative,
  tr,
  lang,
  main,
  intel,
  expenseIntel,
  onOpenAnalysis,
  visualTier = 2,
}) {
  const eiCards = expenseIntelSignalCards(expenseIntel, comparativeIntel, tr, lang)

  const cat = financialBrain?.why?.links?.category_driver_mom
  let costDriver =
    cat?.category != null
      ? `${cat.category}${cat.delta != null ? ` · ${formatCompact(cat.delta)}` : ''}`
      : null
  const blob = narrativeBlob(narrative)
  if (costDriver && cat?.category && blob.includes(String(cat.category).toLowerCase())) {
    costDriver = null
  }

  const momDriver = comparativeIntel?.cost_pressure?.driving_expense_increase_mom
  const ineff = comparativeIntel?.cost_pressure?.most_inefficient_branch
  const ofRevKs = st(tr, lang, 'cmd_branch_of_rev')
  let ineffLine =
    ineff?.branch_name && ineff.expense_pct_of_revenue != null
      ? `${ineff.branch_name} · ${ineff.expense_pct_of_revenue}% ${ofRevKs}`
      : ineff?.branch_name || null
  if (ineffLine && ineff?.branch_name && blob.includes(String(ineff.branch_name).toLowerCase())) {
    ineffLine = null
  }
  if (
    ineffLine &&
    momDriver?.branch_name &&
    ineff?.branch_name &&
    String(ineff.branch_name).toLowerCase() === String(momDriver.branch_name).toLowerCase()
  ) {
    ineffLine = null
  }

  const hi = Array.isArray(alerts) ? alerts.find((a) => a.severity === 'high') : null
  const crit = hi || (Array.isArray(alerts) ? alerts[0] : null)
  let anomalyLine = crit?.title || crit?.message || null
  if (anomalyLine && blob.includes(String(anomalyLine).toLowerCase().slice(0, 48))) {
    anomalyLine = null
  }

  const cards = []
  cards.push(...eiCards)

  const skipFbCostDriver = eiCards.length > 0

  if (!skipFbCostDriver && costDriver) {
    cards.push({
      key: 'cd',
      label: st(tr, lang, 'cmd_sig_cost_driver'),
      value: costDriver,
    })
  }
  if (ineffLine) {
    cards.push({
      key: 'ineff',
      label: st(tr, lang, 'cmd_sig_ineff_branch'),
      value: ineffLine,
    })
  }
  if (anomalyLine) {
    cards.push({
      key: 'alert',
      label: st(tr, lang, 'cmd_sig_critical'),
      value: anomalyLine,
    })
  }

  while (cards.length > 8) cards.pop()

  if (!cards.length) {
    const syn = pickSyntheticSignalCard(main, intel, tr, lang)
    if (syn && !factOverlapsWhy(narrative, syn.value)) cards.push(syn)
  }
  if (!cards.length) {
    cards.push({
      key: 'syn_stable',
      label: st(tr, lang, 'cmd_sig_status'),
      value: st(tr, lang, 'cmd_sig_no_anomalies'),
    })
  }

  const displayCards = cards.slice(0, 3)

  function analysisTabForSignal(cardKey) {
    const k = String(cardKey || '')
    if (k === 'ei_ratio' || k === 'ei_top' || k === 'ei_grow' || k === 'cd') return 'profitability'
    if (k === 'ineff' || k === 'ei_branch_pressure') return 'efficiency'
    if (k === 'alert') return 'alerts'
    return 'overview'
  }

  return sectionShell(
    st(tr, lang, 'cmd_key_signals'),
    st(tr, lang, 'cmd_key_signals_subcritical'),
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
      {displayCards.map((c) => (
        <div
          key={c.key}
          className="cmd-card-hover"
          role={onOpenAnalysis ? 'button' : undefined}
          tabIndex={onOpenAnalysis ? 0 : undefined}
          onClick={onOpenAnalysis ? () => onOpenAnalysis(analysisTabForSignal(c.key)) : undefined}
          onKeyDown={
            onOpenAnalysis
              ? (e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    onOpenAnalysis(analysisTabForSignal(c.key))
                  }
                }
              : undefined
          }
          title={onOpenAnalysis ? st(tr, lang, 'cmd_drill_signal_hint') : undefined}
          style={{
            flex: '1 1 180px',
            minWidth: 152,
            background: 'rgba(255,255,255,0.03)',
            border: `1px solid ${P.border}`,
            borderRadius: 14,
            padding: '12px 14px',
            boxShadow: 'none',
            cursor: onOpenAnalysis ? 'pointer' : undefined,
            outline: 'none',
            transition: 'border-color .15s ease, background .15s ease',
          }}
        >
          <div
            style={{
              fontSize: 8,
              fontWeight: 800,
              color: P.text3,
              textTransform: 'uppercase',
              letterSpacing: '.08em',
              marginBottom: 6,
            }}
          >
            {c.label}
          </div>
          <div style={{ fontSize: 12, fontWeight: 650, color: P.text1, lineHeight: 1.35, ...CLAMP_FADE_MASK_SHORT }}>
            <CmdServerText lang={lang} tr={tr} as="span" style={{ color: 'inherit' }}>
              {c.value}
            </CmdServerText>
          </div>
        </div>
      ))}
    </div>,
    visualTier
  )
}

/**
 * Branch intel: ranking + pressure + efficiency — skips row duplicated by key-signal inefficient branch.
 */
export function BranchIntelligenceSection({
  comparativeIntel,
  tr,
  lang,
  onOpenBranches,
  onBranchRankClick,
  onOpenBranchChart,
  duplicateIneffBranchName,
  narrative,
  visualTier = 2,
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
  const momLab = st(tr, lang, 'cmd_row_mom_expense')
  const ofRevBr = st(tr, lang, 'cmd_branch_of_rev')

  const rows = []
  if (hiExp?.branch_name) {
    rows.push({
      k: 'hiexp',
      label: st(tr, lang, 'cmd_branch_hi_expense'),
      text: `${hiExp.branch_name} · ${formatCompact(hiExp.total_expense)} (${hiExp.expense_pct_of_revenue}% ${ofRevBr})`,
    })
  }
  if (topIneff?.branch_name && (!dup || String(topIneff.branch_name).toLowerCase() !== dup)) {
    rows.push({
      k: 'ineffrank',
      label: st(tr, lang, 'cmd_branch_eff_rank'),
      text: `${topIneff.branch_name} · ${topIneff.expense_pct_of_revenue}% ${ofRevBr}`,
    })
  }
  if (mom?.branch_name && mom.mom_delta_total_expense != null) {
    rows.push({
      k: 'mom',
      label: st(tr, lang, 'cmd_branch_cost_pressure'),
      text: `${mom.branch_name} · ${momLab}${formatCompact(mom.mom_delta_total_expense)}`,
    })
  }
  if (loEff?.branch_name && (!dup || String(loEff.branch_name).toLowerCase() !== dup)) {
    rows.push({
      k: 'loeff',
      label: st(tr, lang, 'cmd_branch_best_ratio'),
      text: `${loEff.branch_name} · ${loEff.expense_pct_of_revenue}% ${ofRevBr}`,
    })
  }

  const visible = rows.filter((r) => !factOverlapsWhy(narrative, r.text))

  const emptyMsg = st(tr, lang, 'cmd_branch_no_pressure')

  const effList = Array.isArray(eff) ? eff.slice(0, 5) : []

  const rankingBlock =
    effList.length > 0 ? (
      <div style={{ marginBottom: 8 }}>
        <div
          style={{
            fontSize: 8,
            fontWeight: 800,
            color: P.text3,
            textTransform: 'uppercase',
            letterSpacing: '.08em',
            marginBottom: 8,
          }}
        >
          {st(tr, lang, 'cmd_branch_rank_title')}
        </div>
        {effList.map((b, i) => {
          const name = b.branch_name || '—'
          const pct = b.expense_pct_of_revenue
          const isMom = mom?.branch_name && String(mom.branch_name) === String(name)
          const isIneff = topIneff?.branch_name && String(topIneff.branch_name) === String(name)
          let badge = st(tr, lang, 'cmd_branch_status_watch')
          let bc = P.text3
          if (isMom) {
            badge = st(tr, lang, 'cmd_branch_status_pressure')
            bc = P.red
          } else if (isIneff) {
            badge = st(tr, lang, 'cmd_branch_status_ineff')
            bc = P.amber
          }
          return (
            <div
              key={String(b.branch_id || name) + i}
              className="cmd-branch-row cmd-card-hover"
              role={onBranchRankClick ? 'button' : undefined}
              tabIndex={onBranchRankClick ? 0 : undefined}
              onClick={onBranchRankClick ? () => onBranchRankClick(b) : undefined}
              onKeyDown={
                onBranchRankClick
                  ? (e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        onBranchRankClick(b)
                      }
                    }
                  : undefined
              }
              title={onBranchRankClick ? st(tr, lang, 'cmd_drill_branch_row_hint') : undefined}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '8px 10px',
                marginBottom: 6,
                borderRadius: 8,
                background: 'rgba(255,255,255,0.02)',
                border: `1px solid ${P.border}`,
                borderLeft: `3px solid ${bc === P.text3 ? P.border : bc}`,
                cursor: onBranchRankClick ? 'pointer' : undefined,
                outline: 'none',
              }}
            >
              <div style={{ fontFamily: 'monospace', fontSize: 11, fontWeight: 800, color: P.text3, width: 20 }}>
                {i + 1}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: P.text1, lineHeight: 1.25 }}>{name}</div>
                <div style={{ fontSize: 10, color: P.text2, marginTop: 1 }}>
                  {pct != null && Number.isFinite(Number(pct))
                    ? `${Number(pct).toFixed(2)}% ${ofRevBr}`
                    : '—'}
                </div>
              </div>
              <span
                style={{
                  fontSize: 8,
                  fontWeight: 800,
                  padding: '3px 6px',
                  borderRadius: 6,
                  background: `${bc}18`,
                  color: bc === P.text3 ? P.text2 : bc,
                  border: `1px solid ${bc === P.text3 ? P.border : `${bc}44`}`,
                  whiteSpace: 'nowrap',
                  maxWidth: '38%',
                  overflow: 'hidden',
                  textOverflow: 'clip',
                }}
              >
                {badge}
              </span>
            </div>
          )
        })}
      </div>
    ) : null

  return sectionShell(
    st(tr, lang, 'cmd_branch_intel'),
    st(tr, lang, 'cmd_branch_intel_sub_perf'),
    <>
      {rankingBlock}
      <div
        style={{
          fontSize: 8,
          fontWeight: 800,
          color: P.text3,
          textTransform: 'uppercase',
          letterSpacing: '.08em',
          marginBottom: 8,
          marginTop: rankingBlock ? 8 : 0,
        }}
      >
        {st(tr, lang, 'cmd_branch_detail_signals')}
      </div>
      <div>
        {visible.length ? (
          visible.map((r, i) => (
            <div
              key={r.k}
              className="cmd-branch-row cmd-card-hover"
              style={{
                padding: '6px 0',
                borderBottom: i < visible.length - 1 ? `1px solid ${P.border}` : 'none',
              }}
            >
              <div
                style={{
                  fontSize: 8,
                  fontWeight: 800,
                  color: P.text3,
                  textTransform: 'uppercase',
                  letterSpacing: '.07em',
                }}
              >
                {r.label}
              </div>
              <div style={{ fontSize: 12, color: P.text1, marginTop: 3, lineHeight: 1.35, ...CLAMP_FADE_MASK_SHORT }}>
              <CmdServerText lang={lang} tr={tr} as="span" style={{ color: 'inherit' }}>
                {r.text}
              </CmdServerText>
            </div>
            </div>
          ))
        ) : !rankingBlock ? (
          <div style={{ fontSize: 12, color: P.text2, lineHeight: 1.45, padding: '4px 0' }}>{emptyMsg}</div>
        ) : null}
      </div>
      {onOpenBranches ? (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            onOpenBranches()
          }}
          style={{
            marginTop: 12,
            padding: '8px 14px',
            borderRadius: 10,
            border: `1px solid ${P.border}`,
            background: 'rgba(255,255,255,0.04)',
            color: P.text2,
            fontSize: 12,
            fontWeight: 700,
            cursor: 'pointer',
            width: 'auto',
            boxShadow: 'none',
          }}
        >
          {st(tr, lang, 'cmd_open_branches')}
        </button>
      ) : null}
    </>,
    visualTier,
    onOpenBranchChart && eff.length > 0
      ? {
          onClick: onOpenBranchChart,
          hint: st(tr, lang, 'cmd_chart_branch_header_hint'),
          title: st(tr, lang, 'cmd_chart_branch_header_title'),
        }
      : null,
  )
}

function priorityLabel(priority, tr, lang) {
  const p = (priority || '').toLowerCase()
  if (p === 'high') return st(tr, lang, 'cmd_dec_badge_high')
  if (p === 'medium') return st(tr, lang, 'cmd_dec_badge_med')
  return st(tr, lang, 'cmd_dec_badge_low')
}

function priorityColor(priority) {
  const p = (priority || '').toLowerCase()
  if (p === 'high') return P.red
  if (p === 'medium') return P.amber
  return P.accent
}

function decisionActionMeta(d, tr, lang) {
  const act = d.action
  if (act && typeof act === 'object') {
    const o = act.owner
    const h = act.time_horizon
    const owner =
      o != null ? st(tr, lang, `cmd_dec_owner_${String(o).toLowerCase()}`) : null
    const horizon =
      h != null ? st(tr, lang, `cmd_dec_horizon_${String(h).toLowerCase()}`) : null
    return { owner, horizon }
  }
  return { owner: null, horizon: null }
}

function decisionImpactSummary(d, tr, lang) {
  const savings = d.expected_financial_impact?.estimated_monthly_savings
  if (savings != null && Number.isFinite(Number(savings)) && Number(savings) > 0) {
    return `${st(tr, lang, 'cmd_dec_impact_monthly')}: ${formatCompact(savings)}`
  }
  return null
}

function DecisionImpactAmount({ savingsRaw, tr, lang }) {
  const ok = savingsRaw != null && Number.isFinite(Number(savingsRaw)) && Number(savingsRaw) > 0
  const v = useCountUp(ok ? Number(savingsRaw) : null, { durationMs: 560, enabled: ok })
  if (!ok) return '—'
  return (
    <>
      {st(tr, lang, 'cmd_dec_impact_monthly')}: {formatCompact(v)}
    </>
  )
}

/** expense_decisions_v2; max 3; always at least one row (baseline if empty). */
export function DecisionsSection({
  expenseDecisionsV2,
  expenseIntel,
  tr,
  lang,
  onOpenDecision,
  visualTier = 2,
  defaultCollapsed = false,
  omitDecisionIds = null,
}) {
  const [expanded, setExpanded] = useState(!defaultCollapsed)

  let list = Array.isArray(expenseDecisionsV2) ? expenseDecisionsV2.filter((d) => d && d.title) : []
  if (!list.length && expenseIntel?.available && Array.isArray(expenseIntel.decisions)) {
    list = expenseIntel.decisions
      .filter((d) => d && d.title)
      .map((d) => ({
        decision_id: d.decision_id,
        title: d.title,
        rationale: d.rationale || (typeof d.action === 'string' ? d.action : null),
        priority: d.priority || 'medium',
        expected_financial_impact: d.expected_financial_impact,
        action: typeof d.action === 'object' && d.action != null ? d.action : undefined,
      }))
  }
  if (omitDecisionIds && omitDecisionIds.size > 0) {
    list = list.filter((d) => d.decision_id && !omitDecisionIds.has(d.decision_id))
  }
  if (!list.length) {
    list = [
      {
        decision_id: '_cmd_baseline',
        title: st(tr, lang, 'cmd_decision_baseline'),
        rationale: null,
        priority: 'medium',
      },
    ]
  }

  const sub = st(tr, lang, 'cmd_decisions_prioritized_sub')
  const displayList = list.slice(0, 3)
  const n = displayList.length

  const listBody = (
    <div className="cmd-section-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {displayList.map((d, idx) => {
        const pr = priorityLabel(d.priority, tr, lang)
        const pc = priorityColor(d.priority)
        const first = idx === 0
        const { owner, horizon } = decisionActionMeta(d, tr, lang)
        const impactOneLine = decisionImpactSummary(d, tr, lang)
        const savingsRaw = d.expected_financial_impact?.estimated_monthly_savings
        const savingsOk =
          savingsRaw != null && Number.isFinite(Number(savingsRaw)) && Number(savingsRaw) > 0
        return (
          <div
            key={d.decision_id || d.title}
            className="cmd-decision-tile cmd-card-hover"
            role={onOpenDecision ? 'button' : undefined}
            tabIndex={onOpenDecision ? 0 : undefined}
            onClick={onOpenDecision ? () => onOpenDecision(d) : undefined}
            onKeyDown={
              onOpenDecision
                ? (e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      onOpenDecision(d)
                    }
                  }
                : undefined
            }
            title={onOpenDecision ? st(tr, lang, 'cmd_drill_decision_hint') : undefined}
            style={{
              padding: first ? '14px 16px' : '12px 14px',
              borderRadius: 14,
              border: first ? `1px solid rgba(0,212,170,0.35)` : `1px solid ${P.border}`,
              borderLeft: first ? `4px solid ${pc}` : `3px solid ${pc}`,
              background: first ? 'rgba(0,212,170,0.06)' : 'rgba(255,255,255,0.02)',
              boxShadow: first
                ? '0 0 16px rgba(0,212,170,0.1), inset 0 1px 0 rgba(255,255,255,0.04)'
                : 'inset 0 1px 0 rgba(255,255,255,0.03)',
              cursor: onOpenDecision ? 'pointer' : undefined,
              outline: 'none',
            }}
          >
            <div
              style={{
                fontSize: first ? 9 : 8,
                fontWeight: 800,
                color: pc,
                textTransform: 'uppercase',
                letterSpacing: '.07em',
              }}
            >
              {idx + 1}. {pr}
            </div>
            <div
              style={{
                fontSize: first ? 15 : 13,
                fontWeight: 800,
                color: P.text1,
                lineHeight: 1.3,
                marginTop: first ? 6 : 5,
                ...CLAMP_FADE_MASK_SHORT,
              }}
            >
              <CmdServerText lang={lang} tr={tr} as="span" style={{ color: 'inherit' }}>
                {d.title}
              </CmdServerText>
            </div>
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                alignItems: 'baseline',
                gap: '6px 14px',
                marginTop: first ? 8 : 6,
                paddingTop: first ? 8 : 6,
                borderTop: `1px solid ${P.border}`,
              }}
            >
              <div style={{ flex: '1 1 90px', minWidth: 0 }}>
                <span style={{ fontSize: 7, fontWeight: 800, color: P.text3, letterSpacing: '.05em' }}>
                  {st(tr, lang, 'cmd_dec_meta_impact')}
                </span>
                <div
                  style={{
                    fontSize: 10,
                    color: P.text2,
                    marginTop: 2,
                    lineHeight: 1.3,
                    ...CLAMP_FADE_MASK_SHORT,
                  }}
                >
                  {savingsOk ? (
                    <DecisionImpactAmount savingsRaw={savingsRaw} tr={tr} lang={lang} />
                  ) : (
                    impactOneLine || '—'
                  )}
                </div>
              </div>
              <div style={{ flex: '0 1 auto', minWidth: 0 }}>
                <span style={{ fontSize: 7, fontWeight: 800, color: P.text3, letterSpacing: '.05em' }}>
                  {st(tr, lang, 'cmd_dec_meta_owner')}
                </span>
                <div style={{ fontSize: 10, color: P.text2, marginTop: 2, lineHeight: 1.2 }}>{owner || '—'}</div>
              </div>
              <div style={{ flex: '0 1 auto', minWidth: 0 }}>
                <span style={{ fontSize: 7, fontWeight: 800, color: P.text3, letterSpacing: '.05em' }}>
                  {st(tr, lang, 'cmd_dec_meta_horizon')}
                </span>
                <div style={{ fontSize: 10, color: P.text2, marginTop: 2, lineHeight: 1.2 }}>{horizon || '—'}</div>
              </div>
            </div>
            {d.rationale ? (
              <div
                style={{
                  fontSize: first ? 11 : 10,
                  color: P.text2,
                  marginTop: first ? 8 : 6,
                  lineHeight: 1.4,
                  maxHeight: first ? '5.6em' : '4.2em',
                  overflow: 'hidden',
                  WebkitMaskImage: 'linear-gradient(to bottom, #000 75%, transparent 100%)',
                  maskImage: 'linear-gradient(to bottom, #000 75%, transparent 100%)',
                }}
              >
                <CmdServerText lang={lang} tr={tr} as="span" style={{ color: 'inherit' }}>
                  {d.rationale}
                </CmdServerText>
              </div>
            ) : null}
          </div>
        )
      })}
    </div>
  )

  const collapsedControls =
    defaultCollapsed && !expanded ? (
      <button
        type="button"
        onClick={() => setExpanded(true)}
        style={{
          width: '100%',
          padding: '10px 14px',
          borderRadius: 12,
          border: `1px solid ${P.border}`,
          background: 'rgba(255,255,255,0.03)',
          color: P.text2,
          fontSize: 10,
          fontWeight: 700,
          cursor: 'pointer',
          textAlign: 'center',
          transition: 'background 0.18s ease, border-color 0.18s ease, color 0.18s ease',
        }}
      >
        {st(tr, lang, 'cmd_decisions_expand')} ({n})
      </button>
    ) : defaultCollapsed && expanded ? (
      <button
        type="button"
        onClick={() => setExpanded(false)}
        style={{
          width: '100%',
          marginBottom: 8,
          padding: '8px 12px',
          borderRadius: 10,
          border: `1px solid ${P.border}`,
          background: 'transparent',
          color: P.accent,
          fontSize: 9,
          fontWeight: 800,
          cursor: 'pointer',
          textAlign: 'center',
          transition: 'background 0.18s ease, border-color 0.18s ease, color 0.18s ease',
        }}
      >
        {st(tr, lang, 'cmd_decisions_collapse')}
      </button>
    ) : null

  return sectionShell(
    st(tr, lang, 'cmd_decisions'),
    sub,
    <>
      {collapsedControls}
      {(!defaultCollapsed || expanded) && listBody}
    </>,
    visualTier,
  )
}
