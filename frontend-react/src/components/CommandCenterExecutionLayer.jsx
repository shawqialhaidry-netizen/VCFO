/**
 * Command Center bottom — execution surface (actions, decision pipeline, alert resolution).
 * Primary action aligns with rail {@link selectPrimaryDecision}; pipeline excludes duplicate of primary.
 */
import { useMemo } from 'react'
import { strictT as st, strictTParams as stp } from '../utils/strictI18n.js'
import { formatCompactForLang, formatSignedPctForLang } from '../utils/numberFormat.js'
import { enforceLanguageFinal } from '../utils/enforceLanguageFinal.js'
import { splitPrimaryDecisionHeadlineAndMetrics } from '../utils/splitPrimaryDecisionHeadline.js'
import { isArabicUiLang, shouldSuppressLatinProseForArabic } from '../utils/arabicBackendCopy.js'
import CmdServerText from './CmdServerText.jsx'
import '../styles/commandCenterExecutionLayer.css'

const DOMAIN_KEYS = ['liquidity', 'profitability', 'efficiency', 'leverage', 'growth']

function pickExpenseCausalRow(items) {
  if (!Array.isArray(items) || !items.length) return null
  const hit = items.find((it) => String(it.id || '').toLowerCase().includes('expense'))
  return hit || items[0]
}

function domainLabel(tr, lang, raw) {
  const d = String(raw || '').trim().toLowerCase()
  if (!DOMAIN_KEYS.includes(d)) return raw ? String(raw) : st(tr, lang, 'cmd_exec_dash')
  return st(tr, lang, `domain_${d}_simple`)
}

function normPriority(p) {
  const x = String(p || 'medium').toLowerCase()
  if (x === 'high' || x === 'medium' || x === 'low') return x
  return 'medium'
}

function priorityClass(p) {
  const n = normPriority(p)
  if (n === 'high') return 'cmd-exec-pri--high'
  if (n === 'low') return 'cmd-exec-pri--low'
  return 'cmd-exec-pri--medium'
}

function safeImpactLabel(tr, lang, raw) {
  const s = String(raw || '').trim()
  if (!s) return st(tr, lang, 'cmd_exec_impact_qual_review')
  if (isArabicUiLang(lang) && shouldSuppressLatinProseForArabic(s)) return st(tr, lang, 'cmd_exec_impact_qual_ar')
  return s
}

function primaryKeys(primaryResolution) {
  const cfoKey =
    primaryResolution?.kind === 'cfo' && primaryResolution.decision
      ? primaryResolution.decision.key || primaryResolution.decision.domain
      : null
  const expId =
    primaryResolution?.kind === 'expense' &&
    primaryResolution.expense?.decision_id &&
    primaryResolution.expense.decision_id !== '_cmd_baseline'
      ? primaryResolution.expense.decision_id
      : null
  return { cfoKey: cfoKey ? String(cfoKey) : null, expId: expId ? String(expId) : null }
}

function buildPrimaryCard({
  primaryResolution,
  realizedCausalItems,
  impacts,
  expenseIntel,
  comparativeIntelligence,
  tr,
  lang,
}) {
  if (!primaryResolution) return null

  if (primaryResolution.kind === 'expense') {
    const e = primaryResolution.expense
    if (!e || e.decision_id === '_cmd_baseline') return null
    const ec = pickExpenseCausalRow(realizedCausalItems)
    const rawTitle = String(ec?.change_text || ec?.action_text || e?.title || '').trim()
    const { headline } = splitPrimaryDecisionHeadlineAndMetrics(rawTitle)
    const title = headline.trim() || rawTitle || st(tr, lang, 'cmd_exec_action_expense_fallback')
    let impact = null
    const sav = e.expected_financial_impact?.estimated_monthly_savings
    if (sav != null && Number.isFinite(Number(sav))) {
      impact = stp(tr, lang, 'cmd_exec_impact_savings_mo', { v: formatCompactForLang(Number(sav), lang) })
    }
    const branch = comparativeIntelligence?.cost_pressure?.driving_expense_increase_mom?.branch_name
    const whyRaw = String(ec?.cause_text || e.rationale || '').trim()
    const why =
      whyRaw && !(isArabicUiLang(lang) && shouldSuppressLatinProseForArabic(whyRaw))
        ? whyRaw
        : branch
          ? stp(tr, lang, 'cmd_exec_action_why_branch', { branch: String(branch).slice(0, 48) })
          : st(tr, lang, 'cmd_exec_action_why_expense_default')
    const instruction =
      String(ec?.action_text || '').trim().split('\n')[0]?.trim() || st(tr, lang, 'cmd_exec_instruction_panel')
    return {
      id: `pa-exp-${e.decision_id || 'x'}`,
      title,
      why,
      impact: impact || st(tr, lang, 'cmd_exec_impact_exec_review'),
      instruction,
      priority: normPriority(e.priority),
      activate: { type: 'expense_v2', payload: e },
      isPrimary: true,
    }
  }

  if (primaryResolution.kind === 'cfo' && primaryResolution.decision) {
    const d = primaryResolution.decision
    const key = d.key || d.domain
    const cr = d.causal_realized || {}
    const rawPrimary = String(cr.change_text || cr.action_text || d.title || '').trim()
    const { headline } = splitPrimaryDecisionHeadlineAndMetrics(rawPrimary)
    const title = headline.trim() || rawPrimary || st(tr, lang, 'cmd_exec_dash')
    const imp = impacts?.[key]?.impact
    let impact = null
    if (imp?.value != null && Number.isFinite(Number(imp.value))) {
      impact = stp(tr, lang, 'cmd_exec_impact_modeled', { v: formatCompactForLang(Number(imp.value), lang) })
    } else if (imp?.type === 'qualitative' && imp?.label) {
      impact = safeImpactLabel(tr, lang, imp.label)
    } else {
      impact = st(tr, lang, 'cmd_exec_impact_qual_review')
    }
    const whyRaw = String(cr.cause_text || d.rationale || '').trim()
    const why =
      whyRaw && !(isArabicUiLang(lang) && shouldSuppressLatinProseForArabic(whyRaw))
        ? whyRaw
        : st(tr, lang, 'cmd_exec_action_why_decision_default')
    const instruction =
      String(cr.action_text || '').trim().split('\n')[0]?.trim() || st(tr, lang, 'cmd_exec_instruction_panel')
    return {
      id: `pa-cfo-${key || 'd'}`,
      title,
      why,
      impact,
      instruction,
      priority: normPriority(d.priority),
      activate: { type: 'decision', payload: d },
      isPrimary: true,
    }
  }

  return null
}

function buildSecondaryCards({
  primaryResolution,
  decs,
  expenseDecisionsV2,
  alerts,
  impacts,
  expenseIntel,
  comparativeIntelligence,
  tr,
  lang,
  max,
}) {
  const { cfoKey, expId } = primaryKeys(primaryResolution)
  const out = []
  const seen = new Set()

  const push = (item) => {
    if (!item?.title) return
    const k = String(item.title).trim().slice(0, 140)
    if (seen.has(k)) return
    seen.add(k)
    out.push(item)
    return out.length >= max
  }

  for (const ed of expenseDecisionsV2 || []) {
    if (out.length >= max) break
    if (!ed?.title) continue
    if (expId && String(ed.decision_id) === expId) continue
    let impact = null
    const sav = ed.expected_financial_impact?.estimated_monthly_savings
    if (sav != null && Number.isFinite(Number(sav))) {
      impact = stp(tr, lang, 'cmd_exec_impact_savings_mo', { v: formatCompactForLang(Number(sav), lang) })
    }
    const whyRaw = String(ed.rationale || '').trim()
    const why =
      whyRaw && !(isArabicUiLang(lang) && shouldSuppressLatinProseForArabic(whyRaw))
        ? whyRaw
        : st(tr, lang, 'cmd_exec_action_why_expense_default')
    if (
      push({
        id: `pa-ed2-${ed.decision_id || ed.title}`,
        title: String(ed.title).trim(),
        why,
        impact: impact || st(tr, lang, 'cmd_exec_impact_exec_review'),
        instruction: st(tr, lang, 'cmd_exec_instruction_panel'),
        priority: normPriority(ed.priority),
        activate: { type: 'expense_v2', payload: ed },
        isPrimary: false,
      })
    ) {
      break
    }
  }

  for (const d of decs || []) {
    if (out.length >= max) break
    if (!d?.title) continue
    const k = d.key || d.domain
    if (cfoKey && String(k) === cfoKey) continue
    const imp = impacts?.[k]?.impact
    let impact = null
    if (imp?.value != null && Number.isFinite(Number(imp.value))) {
      impact = stp(tr, lang, 'cmd_exec_impact_modeled', { v: formatCompactForLang(Number(imp.value), lang) })
    } else if (imp?.type === 'qualitative' && imp?.label) {
      impact = safeImpactLabel(tr, lang, imp.label)
    } else {
      impact = st(tr, lang, 'cmd_exec_impact_qual_review')
    }
    const whyRaw = String(d.rationale || '').trim()
    const why =
      whyRaw && !(isArabicUiLang(lang) && shouldSuppressLatinProseForArabic(whyRaw))
        ? whyRaw
        : stp(tr, lang, 'cmd_exec_action_why_domain', { domain: domainLabel(tr, lang, k) })
    push({
      id: `pa-dec-${k || d.title}`,
      title: String(d.title).trim(),
      why,
      impact,
      instruction: st(tr, lang, 'cmd_exec_instruction_panel'),
      priority: normPriority(d.priority),
      activate: { type: 'decision', payload: d },
      isPrimary: false,
    })
  }

  const hi = (alerts || []).find((a) => a.severity === 'high')
  if (hi && out.length < max) {
    const title = stp(tr, lang, 'cmd_exec_action_resolve_alert_title', { title: String(hi.title || '').slice(0, 80) })
    const whyRaw = String(hi.body || hi.message || '').trim()
    const why =
      whyRaw && !(isArabicUiLang(lang) && shouldSuppressLatinProseForArabic(whyRaw))
        ? whyRaw
        : st(tr, lang, 'cmd_exec_alert_why_high')
    push({
      id: `pa-al-${hi.id || 'hi'}`,
      title,
      why,
      impact: st(tr, lang, 'cmd_exec_impact_risk_contain'),
      instruction: st(tr, lang, 'cmd_exec_instruction_panel'),
      priority: 'high',
      activate: { type: 'alert', payload: hi },
      isPrimary: false,
    })
  }

  return out
}

function collectActionList(args) {
  const primary = buildPrimaryCard(args)
  const maxSecondary = primary ? 2 : 3
  const secondaries = buildSecondaryCards({
    ...args,
    max: maxSecondary,
  })

  if (primary) {
    return [primary, ...secondaries].slice(0, 3)
  }
  if (secondaries.length) {
    return secondaries.slice(0, 3)
  }
  return [
    {
      id: 'pa-insufficient',
      title: st(args.tr, args.lang, 'cmd_exec_insufficient_title'),
      why: st(args.tr, args.lang, 'cmd_exec_insufficient_why'),
      impact: st(args.tr, args.lang, 'cmd_exec_insufficient_impact'),
      instruction: st(args.tr, args.lang, 'cmd_exec_insufficient_action'),
      priority: 'medium',
      activate: null,
      isPrimary: true,
    },
  ]
}

function buildPipelineRows({ decs, expenseDecisionsV2, impacts, primaryResolution, tr, lang }) {
  const { cfoKey, expId } = primaryKeys(primaryResolution)
  const rows = []
  for (const d of decs || []) {
    if (!d?.title) continue
    const k = d.key || d.domain
    if (cfoKey && String(k) === cfoKey) continue
    const imp = impacts?.[k]?.impact
    let outcome = st(tr, lang, 'cmd_exec_outcome_review')
    if (imp?.value != null && Number.isFinite(Number(imp.value))) {
      outcome = stp(tr, lang, 'cmd_exec_outcome_value', { v: formatCompactForLang(Number(imp.value), lang) })
    } else if (imp?.summary && String(imp.summary).trim()) {
      const s = String(imp.summary).trim().slice(0, 120)
      outcome = isArabicUiLang(lang) && shouldSuppressLatinProseForArabic(s) ? st(tr, lang, 'cmd_exec_outcome_review') : s
    }
    rows.push({
      id: `pl-dec-${k}-${rows.length}`,
      title: String(d.title).trim(),
      driver: domainLabel(tr, lang, k),
      outcome,
      risk: normPriority(d.priority),
      activate: { type: 'decision', payload: d },
    })
  }
  for (const ed of expenseDecisionsV2 || []) {
    if (!ed?.title) continue
    if (expId && String(ed.decision_id) === expId) continue
    const cat = ed.category || ed.driver
    rows.push({
      id: `pl-ed-${ed.decision_id || rows.length}`,
      title: String(ed.title).trim(),
      driver: cat ? String(cat) : st(tr, lang, 'cmd_exec_driver_expense_program'),
      outcome:
        ed.expected_financial_impact?.estimated_monthly_savings != null &&
        Number.isFinite(Number(ed.expected_financial_impact.estimated_monthly_savings))
          ? stp(tr, lang, 'cmd_exec_outcome_savings', {
              v: formatCompactForLang(Number(ed.expected_financial_impact.estimated_monthly_savings), lang),
            })
          : st(tr, lang, 'cmd_exec_outcome_cost'),
      risk: normPriority(ed.priority),
      activate: { type: 'expense_v2', payload: ed },
    })
  }
  return rows.slice(0, 6)
}

function buildAlertResolutions({ alerts, tr, lang }) {
  return (alerts || []).slice(0, 5).map((a, i) => {
    const sev = String(a.severity || 'medium').toLowerCase()
    const bodyRaw = String(a.body || a.message || '').trim()
    const why =
      bodyRaw && !(isArabicUiLang(lang) && shouldSuppressLatinProseForArabic(bodyRaw))
        ? bodyRaw
        : sev === 'high'
          ? st(tr, lang, 'cmd_exec_alert_why_high')
          : st(tr, lang, 'cmd_exec_alert_why_watch')
    const cat = a.category ? domainLabel(tr, lang, a.category) : st(tr, lang, 'cmd_exec_alert_cat_general')
    const resolve = stp(tr, lang, 'cmd_exec_alert_resolve', { domain: cat })
    return {
      id: a.id || `ar-${i}`,
      what: a.title,
      why,
      resolve,
      severity: sev,
      activate: { type: 'alert', payload: a },
    }
  })
}

function nextStepLines(narrative, expenseIntel, fcData, tr, lang) {
  const lines = []
  if (narrative?.whatToDo?.lines?.length) {
    for (const L of narrative.whatToDo.lines) {
      const t = enforceLanguageFinal(String(L), lang).trim()
      if (!t) continue
      if (isArabicUiLang(lang) && shouldSuppressLatinProseForArabic(t)) continue
      lines.push(t)
    }
  }
  if (lines.length < 4 && expenseIntel?.narrative_excerpt) {
    const ex = String(expenseIntel.narrative_excerpt).trim()
    if (ex && (!isArabicUiLang(lang) || !shouldSuppressLatinProseForArabic(ex)) && !lines.includes(ex.slice(0, 160))) {
      lines.push(ex.slice(0, 160))
    }
  }
  if (lines.length < 4 && fcData?.summary?.insight && typeof fcData.summary.insight === 'string') {
    const ins = fcData.summary.insight.trim()
    if (ins && (!isArabicUiLang(lang) || !shouldSuppressLatinProseForArabic(ins))) {
      if (!lines.some((x) => x.includes(ins.slice(0, 20)))) lines.push(ins.slice(0, 160))
    }
  }
  if (!lines.length) {
    lines.push(st(tr, lang, 'cmd_exec_next_data_only'))
  }
  return lines.slice(0, 4)
}

export default function CommandCenterExecutionLayer({
  tr,
  lang,
  alerts = [],
  decs = [],
  expenseDecisionsV2 = [],
  narrative = null,
  primaryResolution = null,
  impacts = {},
  expenseIntel = null,
  kpis = {},
  comparativeIntelligence = null,
  fcData = null,
  realizedCausalItems = [],
  onActivate,
}) {
  const actions = useMemo(
    () =>
      collectActionList({
        primaryResolution,
        realizedCausalItems,
        decs,
        expenseDecisionsV2,
        alerts,
        impacts,
        expenseIntel,
        comparativeIntelligence,
        narrative,
        kpis,
        tr,
        lang,
      }),
    [
      primaryResolution,
      realizedCausalItems,
      decs,
      expenseDecisionsV2,
      alerts,
      impacts,
      expenseIntel,
      comparativeIntelligence,
      narrative,
      kpis,
      tr,
      lang,
    ],
  )

  const pipeline = useMemo(
    () => buildPipelineRows({ decs, expenseDecisionsV2, impacts, primaryResolution, tr, lang }),
    [decs, expenseDecisionsV2, impacts, primaryResolution, tr, lang],
  )

  const alertBlocks = useMemo(() => buildAlertResolutions({ alerts, tr, lang }), [alerts, tr, lang])

  const steps = useMemo(() => nextStepLines(narrative, expenseIntel, fcData, tr, lang), [narrative, expenseIntel, fcData, tr, lang])

  const handleActivate = (spec) => {
    if (!spec || !onActivate) return
    onActivate(spec.type, spec.payload)
  }

  return (
    <section className="cmd-exec-layer" aria-label={st(tr, lang, 'cmd_exec_layer_aria')}>
      <header className="cmd-exec-layer__head">
        <h2 className="cmd-exec-layer__title">{st(tr, lang, 'cmd_exec_layer_title')}</h2>
        <p className="cmd-exec-layer__sub">{st(tr, lang, 'cmd_exec_layer_sub')}</p>
      </header>

      <div className="cmd-exec-layer__actions" role="region" aria-label={st(tr, lang, 'cmd_exec_zone_actions_aria')}>
        <div className="cmd-exec-zone-label">{st(tr, lang, 'cmd_exec_zone_actions')}</div>
        <div className="cmd-exec-actions-grid">
          {actions.map((a) => {
            const interactive = Boolean(a.activate)
            const Inner = (
              <>
                <div className="cmd-exec-action__top">
                  <span className={`cmd-exec-pri ${priorityClass(a.priority)}`}>
                    {st(tr, lang, `urgency_${normPriority(a.priority)}`)}
                  </span>
                </div>
                <div className={`cmd-exec-action__title${a.isPrimary ? ' cmd-exec-action__title--primary' : ''}`.trim()}>
                  <CmdServerText lang={lang} tr={tr} as="span">
                    {a.title}
                  </CmdServerText>
                </div>
                <dl className="cmd-exec-action__dl">
                  <div className="cmd-exec-action__row">
                    <dt>{st(tr, lang, 'cmd_exec_lbl_driver')}</dt>
                    <dd>{a.why}</dd>
                  </div>
                  <div className="cmd-exec-action__row">
                    <dt>{st(tr, lang, 'cmd_exec_lbl_impact')}</dt>
                    <dd>{a.impact}</dd>
                  </div>
                  <div className="cmd-exec-action__row">
                    <dt>{st(tr, lang, 'cmd_exec_lbl_action')}</dt>
                    <dd>{a.instruction}</dd>
                  </div>
                </dl>
              </>
            )
            const cls = [
              'cmd-exec-action',
              interactive ? 'cmd-exec-action--interactive' : '',
              a.isPrimary ? 'cmd-exec-action--primary' : 'cmd-exec-action--secondary',
            ]
              .filter(Boolean)
              .join(' ')
            if (interactive) {
              return (
                <button key={a.id} type="button" className={cls} onClick={() => handleActivate(a.activate)}>
                  {Inner}
                </button>
              )
            }
            return (
              <div key={a.id} className={cls}>
                {Inner}
              </div>
            )
          })}
        </div>
      </div>

      <div className="cmd-exec-layer__split">
        <div className="cmd-exec-col cmd-exec-col--pipeline" role="region" aria-label={st(tr, lang, 'cmd_exec_zone_pipeline_aria')}>
          <div className="cmd-exec-zone-label">{st(tr, lang, 'cmd_exec_zone_pipeline')}</div>
          {pipeline.length ? (
            <ul className="cmd-exec-pipeline">
              {pipeline.map((r) => (
                <li key={r.id} className="cmd-exec-pipeline__row">
                  <button type="button" className="cmd-exec-pipeline__btn" onClick={() => handleActivate(r.activate)}>
                    <div className="cmd-exec-pipeline__title">
                      <CmdServerText lang={lang} tr={tr} as="span">
                        {r.title}
                      </CmdServerText>
                    </div>
                    <div className="cmd-exec-pipeline__meta">
                      <span className="cmd-exec-pipeline__k">{st(tr, lang, 'cmd_exec_col_driver')}</span>
                      <span className="cmd-exec-pipeline__v">{r.driver}</span>
                    </div>
                    <div className="cmd-exec-pipeline__meta">
                      <span className="cmd-exec-pipeline__k">{st(tr, lang, 'cmd_exec_col_outcome')}</span>
                      <span className="cmd-exec-pipeline__v">{r.outcome}</span>
                    </div>
                    <div className="cmd-exec-pipeline__risk">
                      <span className={`cmd-exec-risk-dot cmd-exec-risk-dot--${r.risk}`} aria-hidden />
                      <span>{st(tr, lang, 'cmd_exec_col_risk')}</span>
                      <span className="cmd-exec-pipeline__risk-w">{st(tr, lang, `cmd_exec_conf_${r.risk}`)}</span>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="cmd-exec-empty">{st(tr, lang, 'cmd_exec_pipeline_empty')}</p>
          )}
        </div>

        <div className="cmd-exec-col cmd-exec-col--alerts" role="region" aria-label={st(tr, lang, 'cmd_exec_zone_alerts_aria')}>
          <div className="cmd-exec-zone-label">{st(tr, lang, 'cmd_exec_zone_alerts')}</div>
          {alertBlocks.length ? (
            <ul className="cmd-exec-alerts">
              {alertBlocks.map((b) => (
                <li key={b.id} className="cmd-exec-alert-card">
                  <button type="button" className="cmd-exec-alert-card__btn" onClick={() => handleActivate(b.activate)}>
                    <div className="cmd-exec-alert-card__what">
                      <span className={`cmd-exec-sev cmd-exec-sev--${b.severity}`} aria-hidden />
                      <CmdServerText lang={lang} tr={tr} as="span">
                        {b.what}
                      </CmdServerText>
                    </div>
                    <dl className="cmd-exec-alert-card__dl">
                      <div className="cmd-exec-alert-card__row">
                        <dt>{st(tr, lang, 'cmd_exec_alert_why_label')}</dt>
                        <dd>
                          <CmdServerText lang={lang} tr={tr} as="span">
                            {b.why}
                          </CmdServerText>
                        </dd>
                      </div>
                      <div className="cmd-exec-alert-card__row">
                        <dt>{st(tr, lang, 'cmd_exec_alert_resolve_label')}</dt>
                        <dd>{b.resolve}</dd>
                      </div>
                    </dl>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="cmd-exec-empty">{st(tr, lang, 'cmd_exec_alerts_empty')}</p>
          )}
        </div>
      </div>

      <div className="cmd-exec-next" role="region" aria-label={st(tr, lang, 'cmd_exec_zone_next_aria')}>
        <div className="cmd-exec-zone-label">{st(tr, lang, 'cmd_exec_zone_next')}</div>
        <ul className="cmd-exec-next__list">
          {steps.map((s, i) => (
            <li key={i} className="cmd-exec-next__item">
              <span className="cmd-exec-next__idx" aria-hidden>
                {i + 1}
              </span>
              <span className="cmd-exec-next__text">{s}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
