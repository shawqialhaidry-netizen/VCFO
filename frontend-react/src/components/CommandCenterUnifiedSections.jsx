/**
 * Command Center sections — GET /executive payload only; presentation only.
 */
import '../styles/commandCenterStructure.css'
import { useState } from 'react'
import { useCountUp } from '../hooks/useCountUp.js'
import {
  formatCompactForLang,
  formatMultipleForLang,
  formatPctForLang,
  formatSignedPctForLang,
} from '../utils/numberFormat.js'
import { factOverlapsWhy } from '../utils/buildExecutiveNarrative.js'
import { strictT as st } from '../utils/strictI18n.js'
import { CLAMP_FADE_MASK_SHORT } from '../utils/serverTextUi.js'
import CmdServerText from './CmdServerText.jsx'
import CmdSparkline from './CmdSparkline.jsx'

const P = {
  surface: 'linear-gradient(165deg, rgba(17,24,39,0.98) 0%, rgba(15,23,42,0.99) 100%)',
  border: 'rgba(148,163,184,0.16)',
  cardShadow: '0 4px 28px rgba(0,0,0,0.32)',
  accent: '#00d4aa',
  green: '#34d399',
  red: '#f87171',
  amber: '#fbbf24',
  text1: '#ffffff',
  text2: '#d1dae6',
  text3: '#9ca8b8',
}

function sectionShell(title, subtitle, children, visualTier = 2, headerAction = null, panelExtraClass = '') {
  const tier = Number(visualTier) || 2
  const panelCls = [
    'cmd-panel',
    panelExtraClass,
    tier === 3 ? 'cmd-panel--tier3' : '',
    tier === 3 ? 'cmd-panel--pad-3' : 'cmd-panel--pad-2',
  ]
    .filter(Boolean)
    .join(' ')
  const subTierCls = tier === 3 ? 'cmd-card-section-subtitle--t3' : ''
  const titleBlock = (
    <>
      <div className="cmd-card-title">{title}</div>
      {subtitle ? (
        <div className={`cmd-muted-foreign ${subTierCls}`.trim()} style={{ marginTop: 4 }}>
          {subtitle}
        </div>
      ) : null}
    </>
  )
  return (
    <div className={panelCls}>
      <div style={{ marginBottom: tier === 3 ? 10 : 14 }}>
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
              borderRadius: 10,
            }}
          >
            {titleBlock}
          </button>
        ) : (
          titleBlock
        )}
        {headerAction?.hint ? (
          <div style={{ fontSize: 11, color: P.text3, marginTop: 6, opacity: 0.95, lineHeight: 1.45 }}>
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
    let v = formatCompactForLang(cf.operating_cashflow, lang)
    if (cf.operating_cashflow_mom != null && Number.isFinite(Number(cf.operating_cashflow_mom))) {
      const m = Number(cf.operating_cashflow_mom)
      v += ` (${formatSignedPctForLang(m, 1, lang)} ${st(tr, lang, 'mom_label')})`
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
      value: formatCompactForLang(ocf2, lang),
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
      value: formatCompactForLang(wc, lang),
    }
  }
  const cr = ratioVal(intel?.ratios?.liquidity?.current_ratio)
  if (cr != null) {
    return {
      key: 'syn_cr',
      label: st(tr, lang, 'cmd_sig_liquidity'),
      value: formatMultipleForLang(cr, 2, lang),
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
      ? `${ineff.branch_name} · ${formatPctForLang(Number(ineff.expense_pct_of_revenue), 1, lang)} ${ofRev}`
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
    let value = `${top.name} · ${formatCompactForLang(top.amount, lang)}`
    const share = top.share_of_cost_pct
    const mam = top.amount_mom_pct
    if (share != null && Number.isFinite(Number(share))) {
      const sm =
        mam != null && Number.isFinite(Number(mam))
          ? ` (${formatSignedPctForLang(Number(mam), 1, lang)})`
          : ''
      value = `${top.name} = ${formatPctForLang(Number(share), 0, lang)} ${st(tr, lang, 'cmd_ei_pct_of_cost')}${sm}`
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
      value: `${formatPctForLang(Number(ratio), 1, lang)} ${ofRev}${dir}`,
    })
  }
  const g = expenseIntel.largest_increasing_category
  if (g?.name) {
    const pc = g.pct_change
    const val =
      pc != null && Number.isFinite(Number(pc))
        ? `${g.name} · ${formatSignedPctForLang(Number(pc), 1, lang)} ${st(tr, lang, 'mom_label')}`
        : g.absolute_change != null
          ? `${g.name} · ${formatCompactForLang(g.absolute_change, lang)}`
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
      ? `${cat.category}${cat.delta != null ? ` · ${formatCompactForLang(cat.delta, lang)}` : ''}`
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
      ? `${ineff.branch_name} · ${formatPctForLang(Number(ineff.expense_pct_of_revenue), 1, lang)} ${ofRevKs}`
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
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14 }}>
      {displayCards.map((c, idx) => (
        <div
          key={c.key}
          className={`cmd-signal-tile cmd-card-hover${idx === 0 ? ' cmd-signal-tile--featured' : ''}`.trim()}
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
            cursor: onOpenAnalysis ? 'pointer' : undefined,
            outline: 'none',
          }}
        >
          <div className="cmd-field-label" style={{ marginBottom: 6 }}>
            {c.label}
          </div>
          <div
            className="cmd-card-data-value"
            style={{
              ...CLAMP_FADE_MASK_SHORT,
            }}
          >
            <CmdServerText lang={lang} tr={tr} as="span" style={{ color: 'inherit' }}>
              {c.value}
            </CmdServerText>
          </div>
          <CmdSparkline mom={null} />
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
      text: `${hiExp.branch_name} · ${formatCompactForLang(hiExp.total_expense, lang)} (${formatPctForLang(hiExp.expense_pct_of_revenue, 1, lang)} ${ofRevBr})`,
    })
  }
  if (topIneff?.branch_name && (!dup || String(topIneff.branch_name).toLowerCase() !== dup)) {
    rows.push({
      k: 'ineffrank',
      label: st(tr, lang, 'cmd_branch_eff_rank'),
      text: `${topIneff.branch_name} · ${formatPctForLang(topIneff.expense_pct_of_revenue, 1, lang)} ${ofRevBr}`,
    })
  }
  if (mom?.branch_name && mom.mom_delta_total_expense != null) {
    rows.push({
      k: 'mom',
      label: st(tr, lang, 'cmd_branch_cost_pressure'),
      text: `${mom.branch_name} · ${momLab}${formatCompactForLang(mom.mom_delta_total_expense, lang)}`,
    })
  }
  if (loEff?.branch_name && (!dup || String(loEff.branch_name).toLowerCase() !== dup)) {
    rows.push({
      k: 'loeff',
      label: st(tr, lang, 'cmd_branch_best_ratio'),
      text: `${loEff.branch_name} · ${formatPctForLang(loEff.expense_pct_of_revenue, 1, lang)} ${ofRevBr}`,
    })
  }

  const visible = rows.filter((r) => !factOverlapsWhy(narrative, r.text))

  const emptyMsg = st(tr, lang, 'cmd_branch_no_pressure')

  const effList = Array.isArray(eff) ? eff.slice(0, 5) : []

  const rankingBlock =
    effList.length > 0 ? (
      <div style={{ marginBottom: 8 }}>
        <div className="cmd-field-label cmd-field-label--sm" style={{ marginBottom: 8 }}>
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
                borderRadius: 10,
                background: 'rgba(255,255,255,0.03)',
                border: `1px solid ${P.border}`,
                borderLeft: `3px solid ${bc === P.text3 ? P.border : bc}`,
                cursor: onBranchRankClick ? 'pointer' : undefined,
                outline: 'none',
              }}
            >
              <div className="cmd-data-num cmd-branch-rank-idx" style={{ width: 20 }}>
                {i + 1}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 800, color: P.text1, lineHeight: 1.25 }}>{name}</div>
                <div className="cmd-branch-metric-line cmd-data-num">
                  {pct != null && Number.isFinite(Number(pct))
                    ? `${formatPctForLang(Number(pct), 2, lang)} ${ofRevBr}`
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
        className="cmd-field-label cmd-field-label--sm"
        style={{ marginBottom: 8, marginTop: rankingBlock ? 8 : 0 }}
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
              <div className="cmd-field-label cmd-field-label--sm" style={{ marginBottom: 4 }}>
                {r.label}
              </div>
              <div
                className="cmd-card-data-value"
                style={{ marginTop: 4, lineHeight: 1.4, ...CLAMP_FADE_MASK_SHORT }}
              >
              <CmdServerText lang={lang} tr={tr} as="span" style={{ color: 'inherit' }}>
                {r.text}
              </CmdServerText>
            </div>
            </div>
          ))
        ) : !rankingBlock ? (
          <div style={{ fontSize: 13, color: P.text2, lineHeight: 1.5, padding: '6px 0' }}>{emptyMsg}</div>
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
    'cmd-branch-intel-heading',
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
    return `${st(tr, lang, 'cmd_dec_impact_monthly')}: ${formatCompactForLang(savings, lang)}`
  }
  return null
}

function DecisionImpactAmount({ savingsRaw, tr, lang }) {
  const ok = savingsRaw != null && Number.isFinite(Number(savingsRaw)) && Number(savingsRaw) > 0
  const v = useCountUp(ok ? Number(savingsRaw) : null, { durationMs: 560, enabled: ok })
  if (!ok) return '—'
  return (
    <>
      {st(tr, lang, 'cmd_dec_impact_monthly')}: {formatCompactForLang(v, lang)}
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
            className={`cmd-decision-tile cmd-card-hover${first ? ' cmd-decision-priority-ring' : ''}`.trim()}
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
              padding: first ? '16px 18px' : '14px 16px',
              borderRadius: 14,
              border: first ? '1px solid rgba(0,212,170,0.28)' : `1px solid ${P.border}`,
              borderLeft: first ? `4px solid ${pc}` : `3px solid ${pc}`,
              background: first ? 'rgba(0,212,170,0.055)' : 'rgba(255,255,255,0.025)',
              boxShadow: first
                ? 'inset 0 0 0 1px rgba(0,212,170,0.1), 0 4px 24px rgba(0,0,0,0.26)'
                : 'inset 0 1px 0 rgba(255,255,255,0.035)',
              cursor: onOpenDecision ? 'pointer' : undefined,
              outline: 'none',
            }}
          >
            <div
              className="cmd-decision-eyebrow"
              style={{
                fontSize: 12,
                color: pc,
              }}
            >
              {idx + 1}. {pr}
            </div>
            <div
              className="cmd-decision-card-title cmd-card-title"
              style={{
                fontSize: first ? 16 : 14,
                fontWeight: 800,
                marginTop: first ? 8 : 6,
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
                gap: '8px 16px',
                marginTop: first ? 10 : 8,
                paddingTop: first ? 10 : 8,
                borderTop: `1px solid ${P.border}`,
              }}
            >
              <div style={{ flex: '1 1 90px', minWidth: 0 }}>
                <span className="cmd-decision-meta-label">{st(tr, lang, 'cmd_dec_meta_impact')}</span>
                <div className="cmd-decision-impact-line cmd-data-num" style={{ ...CLAMP_FADE_MASK_SHORT }}>
                  {savingsOk ? (
                    <DecisionImpactAmount savingsRaw={savingsRaw} tr={tr} lang={lang} />
                  ) : (
                    impactOneLine || '—'
                  )}
                </div>
              </div>
              <div style={{ flex: '0 1 auto', minWidth: 0 }}>
                <span className="cmd-decision-meta-label">{st(tr, lang, 'cmd_dec_meta_owner')}</span>
                <div className="cmd-decision-impact-line" style={{ lineHeight: 1.2 }}>
                  {owner || '—'}
                </div>
              </div>
              <div style={{ flex: '0 1 auto', minWidth: 0 }}>
                <span className="cmd-decision-meta-label">{st(tr, lang, 'cmd_dec_meta_horizon')}</span>
                <div className="cmd-decision-impact-line" style={{ lineHeight: 1.2 }}>
                  {horizon || '—'}
                </div>
              </div>
            </div>
            {d.rationale ? (
              <div
                style={{
                  fontSize: first ? 12 : 11,
                  color: P.text2,
                  marginTop: first ? 10 : 8,
                  lineHeight: 1.45,
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
          padding: '11px 16px',
          borderRadius: 10,
          border: `1px solid ${P.border}`,
          background: 'rgba(255,255,255,0.03)',
          color: P.text2,
          fontSize: 11,
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
