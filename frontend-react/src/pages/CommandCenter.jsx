/**
 * CommandCenter.jsx — Command Center orchestrator (state, fetch, drill, chrome).
 * Main body: CommandCenterCinematicLayout — context → KPI strip → main charts + right intelligence rail → bridge → dock → footer.
 */
import { useState, useCallback, useEffect, useMemo, useRef } from 'react'
import '../styles/commandCenterMotion.css'
import '../styles/commandCenterStructure.css'
import '../styles/commandCenterChromeImport.css'
import '../styles/commandCenterOS.css'
import '../styles/commandCenterCinematic.css'
import { useCountUp } from '../hooks/useCountUp.js'
import { useNavigate } from 'react-router-dom'
import { useLang }        from '../context/LangContext.jsx'
import { useAuth }        from '../context/AuthContext.jsx'
import { useCompany }     from '../context/CompanyContext.jsx'
import { usePeriodScope } from '../context/PeriodScopeContext.jsx'
import { kpiContextLabel } from '../utils/kpiContext.js'
import {
  formatCompactForLang,
  formatCompactSignedForLang,
  formatFullForLang,
  formatPctForLang,
  formatSignedPctForLang,
} from '../utils/numberFormat.js'
import { buildAnalysisQuery } from '../utils/buildAnalysisQuery.js'
import { buildExecutiveNarrative } from '../utils/buildExecutiveNarrative.js'
import { analysisPathFromPanelType, pathForDrillAnalysisTab } from '../utils/analysisRoutes.js'
import { strictT, strictTParams, localizedMissingPlaceholder } from '../utils/strictI18n.js'
import { selectPrimaryDecision } from '../utils/selectPrimaryDecision.js'
import { splitPrimaryDecisionHeadlineAndMetrics } from '../utils/splitPrimaryDecisionHeadline.js'
import { toExecutiveBulletLines } from '../utils/executiveTextDensity.js'
import { isArabicUiLang, shouldSuppressLatinProseForArabic } from '../utils/arabicBackendCopy.js'

function pickExpenseCausalRow(items) {
  if (!Array.isArray(items) || !items.length) return null
  const hit = items.find((it) => String(it.id || '').toLowerCase().includes('expense'))
  return hit || items[0]
}

function PrimaryDecisionMetricsList({ lines, tr, lang }) {
  if (!lines?.length) return null
  return (
    <ul
      className="cmd-primary-decision-metrics"
      aria-label={strictT(tr, lang, 'cmd_primary_decision_metrics_aria')}
    >
      {lines.map((line, i) => (
        <li key={`pd-met-${i}`}>
          <CmdServerText lang={lang} tr={tr} as="span">
            {line}
          </CmdServerText>
        </li>
      ))}
    </ul>
  )
}
import { CLAMP_FADE_MASK_SHORT } from '../utils/serverTextUi.js'
import CmdServerText from '../components/CmdServerText.jsx'
import StructuredFinancialLayers from '../components/StructuredFinancialLayers.jsx'
import CommandCenterCinematicLayout from '../components/CommandCenterCinematicLayout.jsx'
import CommandCenterExecutionLayer from '../components/CommandCenterExecutionLayer.jsx'
import CommandCenterContextRail from '../components/CommandCenterContextRail.jsx'
import CommandCenterHealthComposite from '../components/CommandCenterHealthComposite.jsx'
import CommandCenterIntelligenceGrid, {
  liquidityHintLine,
  efficiencyHintLine,
} from '../components/CommandCenterIntelligenceGrid.jsx'
import CommandCenterIntelligenceMosaic from '../components/CommandCenterIntelligenceMosaic.jsx'
import CommandCenterIntelligenceExpanded from '../components/CommandCenterIntelligenceExpanded.jsx'
import {
  CommandCenterBranchGroupedChart,
  CommandCenterTripleTrendChart,
} from '../components/CommandCenterPhase3Charts.jsx'
import AiCfoPanel from '../components/AiCfoPanel.jsx'
import DrillIntelligenceBlock from '../components/DrillIntelligenceBlock.jsx'
import { buildDrillIntelligence } from '../utils/buildDrillIntelligence.js'
import CmdSparkline from '../components/CmdSparkline.jsx'
import {
  ExecutiveBranchCompareChart,
  ExecutiveKpiTrendChart,
  ExecutiveProfitBridgeChart,
} from '../components/ExecutiveChartBlocks.jsx'

const API = '/api/v1'
function auth() {
  try { const t=JSON.parse(localStorage.getItem('vcfo_auth')||'{}').token; return t?{Authorization:`Bearer ${t}`}:{} }
  catch { return {} }
}

// ── Design tokens (match ExecutiveDashboard) ───────────────────────────────────
const T = {
  bg:'#0B0F14',      surface:'#111827',   panel:'#111827',    card:'#111827',
  border:'#1F2937',  accent:'#00d4aa',    green:'#34d399',    red:'#f87171',
  amber:'#fbbf24',   violet:'#7c5cfc',    blue:'#3b9eff',
  text1:'#ffffff',   text2:'#b4bcc8',     text3:'#9ca8b8',
}
const stC  = {excellent:'#34d399', good:'#00d4aa', warning:'#fbbf24', risk:'#f87171', neutral:'#aab4c3'}
const dClr = {liquidity:T.blue, profitability:T.green, efficiency:T.violet, leverage:T.amber, growth:T.accent}
const uClr = {high:T.red, medium:T.amber, low:T.blue}
function firstRecommendedLine(action) {
  if (!action || typeof action !== 'string') return ''
  const t = action.trim()
  if (!t) return ''
  const nl = t.indexOf('\n')
  return (nl >= 0 ? t.slice(0, nl) : t).trim()
}

const DOMAIN_SIMPLE_KEYS = ['liquidity', 'profitability', 'efficiency', 'leverage', 'growth']

function resolveDomainSimpleLabel(tr, lang, raw) {
  const d = String(raw || '').trim().toLowerCase()
  if (!DOMAIN_SIMPLE_KEYS.includes(d)) return null
  return strictT(tr, lang, `domain_${d}_simple`)
}

const NEU_BD = '1px solid rgba(148,163,184,0.16)'
/** Controlled accent — primary decision + key KPI only */
const CMD_ACCENT_BD = '1px solid rgba(0,212,170,0.24)'
const CMD_PRIMARY_SHADOW = '0 4px 28px rgba(0,0,0,0.3), 0 0 0 1px rgba(0,212,170,0.1)'
const CMD_PRIMARY_SHADOW_HOVER = '0 6px 32px rgba(0,0,0,0.36), 0 0 0 1px rgba(0,212,170,0.14)'
const CARD_BG = '#111827'
const Pill = ({ label, critical }) => (
  <span
    style={{
      fontSize: 12,
      fontWeight: 800,
      padding: '3px 11px',
      borderRadius: 20,
      background: 'rgba(255,255,255,0.05)',
      color: critical ? T.red : T.text2,
      border: NEU_BD,
      textTransform: 'uppercase',
      letterSpacing: '.05em',
      flexShrink: 0,
      whiteSpace: 'nowrap',
    }}
  >
    {label}
  </span>
)
const lift = () => ({
  onMouseEnter: (e) => {
    e.currentTarget.style.transform = 'translateY(-2px)'
    e.currentTarget.style.boxShadow = '0 8px 24px rgba(0,0,0,0.32)'
  },
  onMouseLeave: (e) => {
    e.currentTarget.style.transform = ''
    e.currentTarget.style.boxShadow = ''
  },
})

function HeroExpenseSavings({ sav, lang }) {
  const ok = sav != null && Number.isFinite(Number(sav)) && Number(sav) > 0
  const v = useCountUp(ok ? Number(sav) : null, { durationMs: 620, enabled: ok })
  if (!ok) return null
  return formatCompactForLang(v, lang)
}

function HeroCfoImpactValue({ raw, fmtQuantImpact }) {
  const ok = raw != null && Number.isFinite(Number(raw))
  const v = useCountUp(ok ? Number(raw) : null, { durationMs: 580, enabled: ok })
  if (!ok) return '—'
  return fmtQuantImpact(v)
}

function KpiMainNumber({ raw, mode, isHero, compact, na, signedTone, lang, cinematicSemantic = null }) {
  const ok = raw != null && raw !== '' && !Number.isNaN(Number(raw)) && Number.isFinite(Number(raw))
  const n = ok ? Number(raw) : null
  const v = useCountUp(n, { durationMs: 520, enabled: ok })
  let toneClass = 'cmd-kpi-val-neu'
  if (signedTone && ok) toneClass = n >= 0 ? 'cmd-kpi-val-pos' : 'cmd-kpi-val-neg'
  const text = !ok ? na : mode === 'percent' ? formatPctForLang(Number(v), 1, lang) : formatCompactForLang(v, lang)
  const semClass =
    cinematicSemantic != null ? ` cmd-cine-kpi-val cmd-cine-kpi-val--${cinematicSemantic}` : ''
  return (
    <div
      className={`cmd-kpi-val cmd-data-num ${toneClass}${semClass}`.trim()}
      style={{
        fontFamily: 'var(--cmd-kpi-num-font, var(--font-display))',
        fontSize: isHero
          ? 'var(--cmd-fs-kpi-hero)'
          : compact
            ? 'var(--cmd-fs-kpi-compact)'
            : 'var(--cmd-fs-kpi)',
        fontWeight: cinematicSemantic ? 700 : 900,
        marginBottom: 4,
        direction: 'ltr',
        letterSpacing: '-0.025em',
        lineHeight: 1.08,
      }}
    >
      {text}
    </div>
  )
}

function PrimaryDecisionHero({
  resolution,
  impacts,
  tr,
  lang,
  causes,
  allDecisions,
  onOpen,
  realizedCausalItems,
  onOpenFullAnalysis,
}) {
  if (!resolution) return null

  const arUi = isArabicUiLang(lang)
  const factBullets = (paragraph) => {
    if (!paragraph) return []
    if (arUi && shouldSuppressLatinProseForArabic(paragraph)) {
      return [strictT(tr, lang, 'cmd_ar_backend_insight_placeholder')]
    }
    return toExecutiveBulletLines(paragraph)
  }

  const analysisLink =
    onOpenFullAnalysis != null ? (
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          onOpenFullAnalysis()
        }}
        style={{
          marginTop: 12,
          padding: '8px 0 0',
          border: 'none',
          borderTop: '1px solid rgba(148,163,184,0.14)',
          background: 'transparent',
          color: T.accent,
          fontSize: 12,
          fontWeight: 800,
          cursor: 'pointer',
          width: '100%',
          textAlign: 'inherit',
        }}
      >
        {strictT(tr, lang, 'open_analysis')} →
      </button>
    ) : null

  const fmtQuantImpact = (v) => {
    if (v == null || !Number.isFinite(Number(v))) return '—'
    const n = Number(v)
    if (n < 0) return formatCompactForLang(n, lang)
    return `+${formatCompactForLang(n, lang)}`
  }

  if (resolution.kind === 'expense') {
    const ex = resolution.expense
    const ec = pickExpenseCausalRow(realizedCausalItems)
    const titleText =
      String(ec?.change_text || ec?.action_text || '').trim() ||
      String(ex?.title || '').trim()
    if (!titleText) return null
    const { headline: expenseHeadline, metrics: expenseMetrics } = splitPrimaryDecisionHeadlineAndMetrics(titleText)
    const expenseTitleDisplay = expenseHeadline.trim() || titleText || strictT(tr, lang, 'cmd_na_short')
    const isBaseline = ex.decision_id === '_cmd_baseline'
    const pri = String(ex.priority || 'medium').toLowerCase()
    const sav = ex.expected_financial_impact?.estimated_monthly_savings
    const hasSav = sav != null && Number.isFinite(Number(sav)) && Number(sav) > 0
    const recLine = String(ec?.action_text || '').trim().split('\n')[0]?.trim() || ''

    const hoverLift = !isBaseline
    const descText = String(ec?.cause_text || '').trim()
    const numTone = hasSav ? 'cmd-hero-impact-pos' : pri === 'high' ? 'cmd-hero-impact-neg' : 'cmd-hero-impact-neu'

    return (
      <div
        className={[
          'cmd-primary-hero',
          'cmd-hero',
          isBaseline ? 'cmd-hero--baseline' : 'cmd-hero--accent cmd-primary-intro cmd-level-1',
        ]
          .filter(Boolean)
          .join(' ')}
        style={{
          width: '100%',
          textAlign: 'start',
          color: T.text1,
          display: 'block',
          opacity: isBaseline ? 0.92 : 1,
          transition: 'transform 0.18s ease, box-shadow 0.18s ease, opacity 0.18s ease',
        }}
      >
        <button
          type="button"
          onClick={() =>
            ec
              ? onOpen('causal_item', ec, {})
              : onOpen('expense_v2', ex, {})
          }
          style={{
            width: '100%',
            textAlign: 'start',
            cursor: 'pointer',
            color: 'inherit',
            display: 'block',
            background: 'transparent',
            border: 'none',
            padding: 0,
            font: 'inherit',
            transition: 'transform 0.18s ease, box-shadow 0.18s ease',
          }}
          onMouseEnter={(e) => {
            if (!hoverLift) return
            const root = e.currentTarget.closest('.cmd-primary-hero')
            if (root) {
              root.style.transform = 'translateY(-2px)'
              root.style.boxShadow = CMD_PRIMARY_SHADOW_HOVER
            }
          }}
          onMouseLeave={(e) => {
            if (!hoverLift) return
            const root = e.currentTarget.closest('.cmd-primary-hero')
            if (root) {
              root.style.transform = ''
              root.style.boxShadow = ''
            }
          }}
        >
          <div className="cmd-primary-hero-inner">
          <div className="cmd-hero-eyebrow-wrap">
            <span className="cmd-hero-eyebrow">
              {strictT(tr, lang, isBaseline ? 'cmd_primary_baseline_eyebrow' : 'cmd_primary_decision_label')}
            </span>
          </div>
          <div className="cmd-hero-title cmd-primary-decision-headline">
            <CmdServerText lang={lang} tr={tr} as="span">
              {expenseTitleDisplay}
            </CmdServerText>
          </div>
          <PrimaryDecisionMetricsList lines={expenseMetrics} tr={tr} lang={lang} />
          {descText ? (
            <div className="cmd-magic-hero-cause cmd-primary-decision-why">
              <span className="cmd-magic-hero-k">{strictT(tr, lang, 'exec_why')}</span>
              <ul className="cmd-os-fact-list cmd-primary-decision-bullets">
                {factBullets(descText).map((line, i) => (
                  <li key={`ex-why-${i}`}>
                    <CmdServerText lang={lang} tr={tr} as="span">
                      {line}
                    </CmdServerText>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {recLine ? (
            <div className="cmd-magic-hero-action cmd-primary-decision-actions">
              <span className="cmd-magic-hero-k">{strictT(tr, lang, 'exec_actions')}</span>
              <ul className="cmd-os-fact-list cmd-primary-decision-bullets">
                {factBullets(recLine).map((line, i) => (
                  <li key={`ex-act-${i}`}>
                    <CmdServerText lang={lang} tr={tr} as="span">
                      {line}
                    </CmdServerText>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <div className="cmd-hero-actions">
            {!isBaseline ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
                <Pill label={strictT(tr, lang, `priority_${pri}`)} critical={pri === 'high'} />
              </div>
            ) : null}
            <div className="cmd-muted-foreign" style={{ marginTop: recLine || !isBaseline ? 4 : 0 }}>
              {strictT(
                tr,
                lang,
                isBaseline ? 'cmd_primary_baseline_footer' : 'cmd_open_full_analysis_decisions',
              )}
              {!isBaseline ? ' →' : null}
            </div>
          </div>
          {!isBaseline ? (
            <div className="cmd-magic-impact-support">
              <span className="cmd-magic-impact-label">{strictT(tr, lang, 'impact_expected_label')}</span>
              <div className={`cmd-hero-number cmd-data-num cmd-magic-impact-num ${numTone}`.trim()}>
                {hasSav ? <HeroExpenseSavings sav={sav} lang={lang} /> : '—'}
              </div>
            </div>
          ) : null}
        </div>
        </button>
        {analysisLink}
      </div>
    )
  }

  const decision = resolution.decision
  if (!decision) return null
  const cr = decision.causal_realized || {}
  const impKey = decision.key || decision.domain
  const imp = impacts[impKey]?.impact
  const hasQuant =
    imp && imp.type !== 'qualitative' && imp.value != null && Number.isFinite(Number(imp.value))
  const recLine = String(cr.action_text || '').trim().split('\n')[0]?.trim() || ''
  const descText = String(cr.cause_text || '').trim()
  const rawPrimaryLine = String(cr.change_text || cr.action_text || '').trim()
  const { headline: cfoHeadline, metrics: cfoMetrics } = splitPrimaryDecisionHeadlineAndMetrics(rawPrimaryLine)
  const cfoTitleDisplay = cfoHeadline.trim() || rawPrimaryLine || strictT(tr, lang, 'cmd_na_short')

  let numTone = 'cmd-hero-impact-neu'
  if (hasQuant) {
    const n = Number(imp.value)
    if (n > 0) numTone = 'cmd-hero-impact-pos'
    else if (n < 0) numTone = 'cmd-hero-impact-neg'
    else numTone = 'cmd-hero-impact-neu'
  }

  return (
    <div
      className="cmd-primary-hero cmd-hero cmd-hero--accent cmd-primary-intro cmd-level-1"
      style={{
        width: '100%',
        textAlign: 'start',
        color: T.text1,
        display: 'block',
        transition: 'transform 0.18s ease, box-shadow 0.18s ease',
      }}
    >
      <button
        type="button"
        onClick={() =>
          cr.change_text || cr.action_text
            ? onOpen('causal_item', cr, { causes, decisions: allDecisions })
            : onOpen('decision', decision, { causes, decisions: allDecisions })
        }
        style={{
          width: '100%',
          textAlign: 'start',
          cursor: 'pointer',
          color: 'inherit',
          display: 'block',
          background: 'transparent',
          border: 'none',
          padding: 0,
          font: 'inherit',
          transition: 'transform 0.18s ease, box-shadow 0.18s ease',
        }}
        onMouseEnter={(e) => {
          const root = e.currentTarget.closest('.cmd-primary-hero')
          if (root) {
            root.style.transform = 'translateY(-2px)'
            root.style.boxShadow = CMD_PRIMARY_SHADOW_HOVER
          }
        }}
        onMouseLeave={(e) => {
          const root = e.currentTarget.closest('.cmd-primary-hero')
          if (root) {
            root.style.transform = ''
            root.style.boxShadow = ''
          }
        }}
      >
        <div className="cmd-primary-hero-inner">
        <div className="cmd-hero-eyebrow-wrap">
          <span className="cmd-hero-eyebrow">{strictT(tr, lang, 'cmd_primary_decision_label')}</span>
        </div>
        {decision.domain || decision.action_type ? (
          <div className="cmd-muted-foreign cmd-primary-decision-domain">
            {(() => {
              const raw = String(decision.action_type || decision.domain || '').trim()
              const mapped = resolveDomainSimpleLabel(tr, lang, raw)
              if (mapped) return mapped
              return (
                <CmdServerText lang={lang} tr={tr} as="span">
                  {raw}
                </CmdServerText>
              )
            })()}
          </div>
        ) : null}
        <div className="cmd-hero-title cmd-primary-decision-headline">
          <CmdServerText lang={lang} tr={tr} as="span">
            {cfoTitleDisplay}
          </CmdServerText>
        </div>
        <PrimaryDecisionMetricsList lines={cfoMetrics} tr={tr} lang={lang} />
        {descText ? (
          <div className="cmd-magic-hero-cause cmd-primary-decision-why">
            <span className="cmd-magic-hero-k">{strictT(tr, lang, 'exec_why')}</span>
            <ul className="cmd-os-fact-list cmd-primary-decision-bullets">
              {factBullets(descText).map((line, i) => (
                <li key={`cfo-why-${i}`}>
                  <CmdServerText lang={lang} tr={tr} as="span">
                    {line}
                  </CmdServerText>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {recLine ? (
          <div className="cmd-magic-hero-action cmd-primary-decision-actions">
            <span className="cmd-magic-hero-k">{strictT(tr, lang, 'exec_actions')}</span>
            <ul className="cmd-os-fact-list cmd-primary-decision-bullets">
              {factBullets(recLine).map((line, i) => (
                <li key={`cfo-act-${i}`}>
                  <CmdServerText lang={lang} tr={tr} as="span">
                    {line}
                  </CmdServerText>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        <div className="cmd-hero-actions">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
            <Pill label={strictT(tr, lang, `urgency_${decision.urgency}`)} critical={decision.urgency === 'high'} />
            {decision.impact_level ? (
              <Pill
                label={strictT(tr, lang, `impact_${decision.impact_level}`)}
                critical={decision.impact_level === 'high'}
              />
            ) : null}
          </div>
          <div className="cmd-muted-foreign" style={{ marginTop: 4 }}>
            {strictT(tr, lang, 'cmd_primary_decision_open')} →
          </div>
        </div>
        {hasQuant ? (
          <div className="cmd-magic-impact-support">
            <span className="cmd-magic-impact-label">{strictT(tr, lang, 'impact_expected_label')}</span>
            <div className={`cmd-hero-number cmd-data-num cmd-magic-impact-num ${numTone}`.trim()}>
              <HeroCfoImpactValue raw={imp.value} fmtQuantImpact={fmtQuantImpact} />
            </div>
          </div>
        ) : null}
      </div>
      </button>
      {analysisLink}
    </div>
  )
}

/** Level 1 — health ring + identity + narrative hooks (no KPIs). */
function HealthScorePanel({
  tr,
  lang,
  health,
  status,
  companyName,
  period,
  loading,
  onRefresh,
  periodCount,
  scopeLabel,
  healthHeadline,
  actionPrefix,
  actionLine,
  onDrillAnalysis,
  pairedLayout = false,
  hideCompanyIdentity = false,
  bandCompact = false,
}) {
  const hc = stC[status] || T.text2
  const circ = 2 * Math.PI * 30
  const h = health != null && Number.isFinite(Number(health)) ? Number(health) : null
  const dash = h != null ? (Math.max(0, Math.min(100, h)) / 100) * circ : 0
  const healthLabel = strictT(tr, lang, 'cmd_health_score')
  const snapSub = strictT(tr, lang, 'cmd_health_kpi_sub')
  const statusUi = strictT(tr, lang, `status_${status}_simple`)
  const actionLbl = actionPrefix || strictT(tr, lang, 'cmd_narr_action_label')

  return (
    <div
      className={`cmd-level-1${pairedLayout ? ' cmd-health-panel--paired' : ''}`.trim()}
      style={{
        background: CARD_BG,
        border: NEU_BD,
        borderRadius: 14,
        boxShadow: 'none',
        padding: bandCompact ? '10px 12px 12px' : pairedLayout ? '14px 16px 14px' : '16px 18px 16px',
        minHeight: 0,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: bandCompact ? 10 : 16,
          marginBottom: bandCompact ? 10 : 16,
        }}
      >
        <div>
          <div className="cmd-card-title">{healthLabel}</div>
          <div className="cmd-muted-foreign" style={{ marginTop: 4 }}>
            {snapSub}
          </div>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          style={{
            flexShrink: 0,
            width: 36,
            height: 36,
            borderRadius: 10,
            border: `1px solid ${T.border}`,
            background: T.card,
            color: T.text2,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 15,
          }}
        >
          {loading ? (
            <div
              style={{
                width: 14,
                height: 14,
                border: `2px solid ${T.border}`,
                borderTopColor: T.text1,
                borderRadius: '50%',
                animation: 'spin .7s linear infinite',
              }}
            />
          ) : (
            '↻'
          )}
        </button>
      </div>

      <div
        role={onDrillAnalysis ? 'button' : undefined}
        tabIndex={onDrillAnalysis ? 0 : undefined}
        onClick={onDrillAnalysis || undefined}
        onKeyDown={
          onDrillAnalysis
            ? (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onDrillAnalysis()
                }
              }
            : undefined
        }
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: bandCompact ? 12 : 16,
          cursor: onDrillAnalysis ? 'pointer' : undefined,
          borderRadius: onDrillAnalysis ? 12 : undefined,
          padding: onDrillAnalysis ? 4 : undefined,
          margin: onDrillAnalysis ? -4 : undefined,
          outline: 'none',
        }}
        title={onDrillAnalysis ? strictT(tr, lang, 'cmd_drill_health_hint') : undefined}
      >
        <svg
          width={bandCompact ? 68 : 76}
          height={bandCompact ? 68 : 76}
          viewBox="0 0 88 88"
          style={{ flexShrink: 0 }}
        >
          <circle cx={44} cy={44} r={34} fill="none" stroke={T.border} strokeWidth={5} />
          <circle
            cx={44}
            cy={44}
            r={34}
            fill="none"
            stroke={status === 'risk' ? T.red : T.green}
            strokeWidth={5}
            strokeDasharray={`${dash} ${circ - dash}`}
            strokeDashoffset={circ * 0.25}
            strokeLinecap="round"
          />
          <text x={44} y={43} textAnchor="middle" fontSize={17} fontWeight={800} fill={T.green} fontFamily="monospace">
            {h != null ? Math.round(h) : ''}
          </text>
          <text x={44} y={57} textAnchor="middle" fontSize={10} fill={T.text3}>
            /100
          </text>
        </svg>
        <div style={{ minWidth: 0, flex: 1 }}>
          {!hideCompanyIdentity ? (
            <div
              className={`cmd-display-headline${pairedLayout ? ' cmd-muted-foreign' : ''}`.trim()}
              style={{ marginBottom: 8, fontWeight: pairedLayout ? 650 : undefined }}
            >
              <CmdServerText lang={lang} tr={tr} as="span">
                {companyName || ''}
              </CmdServerText>
            </div>
          ) : null}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span
              className={hideCompanyIdentity ? 'cmd-magic-health-tier' : undefined}
              style={{
                fontSize: hideCompanyIdentity ? 13 : 10,
                fontWeight: 800,
                padding: hideCompanyIdentity ? '6px 12px' : '4px 10px',
                borderRadius: 999,
                background: 'rgba(255,255,255,0.06)',
                color: status === 'risk' ? T.red : T.text1,
                border: NEU_BD,
                letterSpacing: hideCompanyIdentity ? '.02em' : '.04em',
              }}
            >
              {statusUi}
            </span>
            {period ? (
              <span className="cmd-health-meta-muted" style={{ fontFamily: 'monospace' }}>
                {period}
              </span>
            ) : null}
            {periodCount != null ? <span className="cmd-health-meta-muted">· {periodCount}p</span> : null}
            {scopeLabel ? (
              <span className="cmd-health-meta-muted">
                ·{' '}
                <CmdServerText lang={lang} tr={tr} as="span">
                  {scopeLabel}
                </CmdServerText>
              </span>
            ) : null}
          </div>
        </div>
      </div>

      {healthHeadline || actionLine ? (
        <div
          style={{
            marginTop: 12,
            paddingTop: 12,
            borderTop: '1px solid rgba(148,163,184,0.12)',
          }}
        >
          {healthHeadline ? (
            <div
              className="cmd-prose"
              style={{ fontSize: 'var(--cmd-fs-body)', fontWeight: 650, color: T.text1, ...CLAMP_FADE_MASK_SHORT }}
            >
              <CmdServerText lang={lang} tr={tr} as="span">
                {healthHeadline}
              </CmdServerText>
            </div>
          ) : null}
          {actionLine ? (
            <div style={{ marginTop: healthHeadline ? 8 : 0 }}>
              <div className="cmd-field-label cmd-field-label--sm" style={{ marginBottom: 4 }}>
                {actionLbl}
              </div>
              <div
                className="cmd-prose"
                style={{ fontSize: 'var(--cmd-fs-body)', fontWeight: 700, color: T.text1, marginTop: 6, ...CLAMP_FADE_MASK_SHORT }}
              >
                <CmdServerText lang={lang} tr={tr} as="span">
                  {actionLine}
                </CmdServerText>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

// ──────────────────────────────────────────────────────────────────────────────
//  ContextPanel — drill context drawer
//  Minimal fix: CommandCenter references this panel on click.
// ──────────────────────────────────────────────────────────────────────────────
function ContextPanel({ type, payload, extra, tr, lang, onClose, onNavigate, impacts={} }) {
  if (!type || !payload) return null
  const dc = dClr[payload.domain] || T.accent
  const tDrill = (k, p) => (p != null && typeof p === 'object' ? strictTParams(tr, lang, k, p) : strictT(tr, lang, k))
  const drillLines = buildDrillIntelligence({ panelType: type, payload, extra, t: tDrill, lang })
  const drillTheme = { card: T.card, border: T.border, text1: T.text1, text2: T.text2, text3: T.text3, accent: T.accent }

  const Sec = ({ label, color=T.text3, children }) => (
    <div style={{marginBottom:22}}>
      <div style={{display:'flex',alignItems:'center',gap:7,marginBottom:10}}>
        <div style={{width:18,height:2,background:color,borderRadius:2}}/>
        <span style={{fontSize:10,fontWeight:800,color,textTransform:'uppercase',letterSpacing:'.07em'}}>{label}</span>
      </div>
      {children}
    </div>
  )

  const Steps = ({ text }) => {
    if (!text) return null
    const parts = text.split(/[0-9]+[).\s]+/).filter(s => s.trim().length > 5)
    if (parts.length <= 1) {
      return (
        <p style={{ fontSize: 12, color: T.text2, lineHeight: 1.75, margin: 0, ...CLAMP_FADE_MASK_SHORT }}>
          <CmdServerText lang={lang} tr={tr} as="span">
            {text}
          </CmdServerText>
        </p>
      )
    }
    return (
      <div style={{display:'flex',flexDirection:'column',gap:7}}>
        {parts.map((s,i) => (
          <div key={i} style={{display:'flex',gap:10,alignItems:'flex-start',
            background:`${dc}08`,borderRadius:8,padding:'9px 12px',border:`1px solid ${dc}15`}}>
            <div style={{width:20,height:20,borderRadius:'50%',background:`${dc}22`,
              display:'flex',alignItems:'center',justifyContent:'center',
              flexShrink:0,fontSize:11,fontWeight:800,color:dc}}>{i+1}</div>
            <span style={{fontSize:11,color:T.text2,lineHeight:1.6, ...CLAMP_FADE_MASK_SHORT}}>
              <CmdServerText lang={lang} tr={tr} as="span">
                {s.trim()}
              </CmdServerText>
            </span>
          </div>
        ))}
      </div>
    )
  }

  const Decision = () => {
    const cr = payload.causal_realized || {}
    const rawHead = String(cr.change_text || cr.action_text || '').trim()
    const { headline: drillHeadline, metrics: drillMetrics } = splitPrimaryDecisionHeadlineAndMetrics(rawHead)
    const headline =
      drillHeadline.trim() || rawHead || strictT(tr, lang, 'cmd_na_short')
    const causeBody = String(cr.cause_text || '').trim()
    const actionBody = String(cr.action_text || '').trim()
    return (
      <>
        <div className="cmd-hero-title cmd-primary-decision-headline">
          <CmdServerText lang={lang} tr={tr} as="span">
            {headline}
          </CmdServerText>
        </div>
        <PrimaryDecisionMetricsList lines={drillMetrics} tr={tr} lang={lang} />
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 22 }}>
          <Pill label={strictT(tr, lang, `urgency_${payload.urgency}`)} critical={payload.urgency === 'high'} />
          {payload.impact_level ? (
            <Pill label={strictT(tr, lang, `impact_${payload.impact_level}`)} critical={payload.impact_level === 'high'} />
          ) : null}
          <Pill
            label={
              payload.confidence != null && Number.isFinite(Number(payload.confidence))
                ? formatPctForLang(Number(payload.confidence), 0, lang)
                : '—'
            }
          />
        </div>

        <DrillIntelligenceBlock
          what={drillLines.what}
          why={drillLines.why}
          do={drillLines.do}
          tr={tr}
          lang={lang}
          theme={drillTheme}
        />

        {causeBody ? (
          <Sec label={strictT(tr, lang, 'exec_why')} color={T.red}>
            <p style={{ fontSize: 12, color: T.text2, lineHeight: 1.75, margin: 0, ...CLAMP_FADE_MASK_SHORT }}>
              <CmdServerText lang={lang} tr={tr} as="span">
                {causeBody}
              </CmdServerText>
            </p>
          </Sec>
        ) : null}

        {actionBody ? (
          <Sec label={strictT(tr, lang, 'exec_actions')} color={dc}>
            <p style={{ fontSize: 12, color: T.text2, lineHeight: 1.75, margin: 0, ...CLAMP_FADE_MASK_SHORT }}>
              <CmdServerText lang={lang} tr={tr} as="span">
                {actionBody}
              </CmdServerText>
            </p>
          </Sec>
        ) : null}

        {(() => {
          const impKey = payload?.key || payload?.domain
          const imp = impacts[impKey]?.impact || impacts[payload?.domain]?.impact
          if (!imp || imp.type === 'qualitative' || imp.value == null) return null
          const fmtImpactQuant = (v) => {
            if (v == null || !Number.isFinite(Number(v))) return '—'
            const n = Number(v)
            if (n < 0) return formatCompactForLang(n, lang)
            return `+${formatCompactForLang(n, lang)}`
          }
          return (
            <div
              style={{
                background: `${T.green}08`,
                border: `1px solid ${T.green}25`,
                borderRadius: 11,
                padding: '14px 16px',
                marginBottom: 16,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 10 }}>
                <div style={{ width: 18, height: 2, background: T.green, borderRadius: 2 }} />
                <span
                  style={{
                    fontSize: 9,
                    fontWeight: 800,
                    color: T.green,
                    textTransform: 'uppercase',
                    letterSpacing: '.08em',
                  }}
                >
                  {strictT(tr, lang, 'impact_expected_label')}
                </span>
              </div>
              <div
                style={{
                  fontFamily: 'monospace',
                  fontSize: 24,
                  fontWeight: 800,
                  color: T.green,
                  direction: 'ltr',
                  marginBottom: 4,
                }}
              >
                {fmtImpactQuant(imp.value)}
              </div>
              {imp.range?.low != null && imp.range?.high != null && (
                <div style={{ fontSize: 10, color: T.text2, marginBottom: 8, fontFamily: 'monospace' }}>
                  {fmtImpactQuant(imp.range.low)} – {fmtImpactQuant(imp.range.high)}{' '}
                  {strictT(tr, lang, 'impact_range_label')}
                </div>
              )}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <span
                  style={{
                    fontSize: 9,
                    color: T.green,
                    background: `${T.green}15`,
                    padding: '2px 8px',
                    borderRadius: 20,
                    fontWeight: 700,
                    border: `1px solid ${T.green}30`,
                  }}
                >
                  {imp.confidence != null && Number.isFinite(Number(imp.confidence))
                    ? `${strictT(tr, lang, 'fc_confidence')}: ${formatPctForLang(Number(imp.confidence), 0, lang)}`
                    : `${strictT(tr, lang, 'fc_confidence')}: —`}
                </span>
              </div>
            </div>
          )
        })()}

        {extra?.execChartBundle?.kpi_block ? (
          <ExecutiveProfitBridgeChart kpiBlock={extra.execChartBundle.kpi_block} tr={tr} lang={lang} />
        ) : null}

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            background: T.card,
            borderRadius: 11,
            padding: '12px 16px',
            border: `1px solid ${T.border}`,
          }}
        >
          <span className="cmd-drill-clock-glyph" aria-hidden style={{ color: T.text3, display: 'flex', flexShrink: 0 }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
              <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.5" opacity="0.35" />
              <path
                d="M12 7v5l3 2"
                stroke="currentColor"
                strokeWidth="1.65"
                strokeLinecap="round"
                strokeLinejoin="round"
                opacity="0.85"
              />
            </svg>
          </span>
          <div>
            <div
              style={{
                fontSize: 9,
                color: T.text3,
                textTransform: 'uppercase',
                letterSpacing: '.07em',
                marginBottom: 3,
              }}
            >
              {strictT(tr, lang, 'exec_timeframe')}
            </div>
            <div
              style={{
                fontSize: 16,
                fontWeight: 800,
                color: uClr[payload.urgency] || T.accent,
                fontFamily: 'monospace',
              }}
            >
              <CmdServerText lang={lang} tr={tr} as="span">
                {payload.timeframe}
              </CmdServerText>
            </div>
          </div>
        </div>
      </>
    )
  }

  const CausalItem = () => (
    <DrillIntelligenceBlock
      what={drillLines.what}
      why={drillLines.why}
      do={drillLines.do}
      tr={tr}
      lang={lang}
      theme={drillTheme}
    />
  )

  const Kpi = () => {
    const kbDrill = extra?.execChartBundle?.kpi_block
    const ciDrill = extra?.execChartBundle?.comparative_intelligence
    const periodsDrill = kbDrill?.periods || []
    const li = periodsDrill.length - 1
    const revL = li >= 0 ? kbDrill?.series?.revenue?.[li] : null
    const expL = li >= 0 ? kbDrill?.series?.expenses?.[li] : null
    const npL = li >= 0 ? kbDrill?.series?.net_profit?.[li] : null
    const plab = li >= 0 && periodsDrill[li] != null ? String(periodsDrill[li]).slice(0, 7) : null
    const topBr = ciDrill?.efficiency_ranking?.by_expense_pct_of_revenue_desc?.[0]
    const branchInfluence =
      topBr?.branch_name != null && topBr.expense_pct_of_revenue != null
        ? strictTParams(tr, lang, 'drill_intel_branch_expense_line', {
            name: String(topBr.branch_name),
            pct: formatPctForLang(Number(topBr.expense_pct_of_revenue), 1, lang),
          })
        : null

    const nmRaw = payload.type === 'net_margin' ? payload.raw : null
    const nmOk =
      nmRaw != null &&
      nmRaw !== '' &&
      !Number.isNaN(Number(nmRaw)) &&
      Number.isFinite(Number(nmRaw))
    const headlinePct = nmOk ? formatPctForLang(Number(nmRaw), 1, lang) : null
    const headlineColor =
      nmOk && Number(nmRaw) < 0 ? T.red : nmOk && Number(nmRaw) > 0 ? T.green : T.text1

    const chartTypes = ['revenue', 'net_profit', 'cashflow', 'expenses', 'net_margin']
    const showTrend = chartTypes.includes(payload.type) && extra?.execChartBundle

    const factorBlock =
      payload.type === 'net_margin' && (revL != null || expL != null || npL != null) ? (
        <Sec label={strictT(tr, lang, 'cmd_kpi_margin_factors')} color={T.text3}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {revL != null && Number.isFinite(Number(revL)) ? (
              <div
                key="rev"
                style={{
                  background: T.card,
                  borderRadius: 8,
                  padding: '10px 12px',
                  border: `1px solid ${T.border}`,
                }}
              >
                <div
                  style={{
                    fontSize: 9,
                    color: T.text3,
                    textTransform: 'uppercase',
                    letterSpacing: '.06em',
                  }}
                >
                  {strictT(tr, lang, 'kpi_label_revenue')}
                </div>
                <div
                  style={{
                    fontFamily: 'monospace',
                    fontSize: 15,
                    fontWeight: 800,
                    color: T.text1,
                    direction: 'ltr',
                  }}
                >
                  {formatCompactForLang(Number(revL), lang)}
                </div>
              </div>
            ) : null}
            {expL != null && Number.isFinite(Number(expL)) ? (
              <div
                key="exp"
                style={{
                  background: T.card,
                  borderRadius: 8,
                  padding: '10px 12px',
                  border: `1px solid ${T.border}`,
                }}
              >
                <div
                  style={{
                    fontSize: 9,
                    color: T.text3,
                    textTransform: 'uppercase',
                    letterSpacing: '.06em',
                  }}
                >
                  {strictT(tr, lang, 'kpi_label_expenses')}
                </div>
                <div
                  style={{
                    fontFamily: 'monospace',
                    fontSize: 15,
                    fontWeight: 800,
                    color: T.red,
                    direction: 'ltr',
                  }}
                >
                  {formatCompactForLang(Number(expL), lang)}
                </div>
              </div>
            ) : null}
            {npL != null && Number.isFinite(Number(npL)) ? (
              <div
                key="np"
                style={{
                  background: T.card,
                  borderRadius: 8,
                  padding: '10px 12px',
                  border: `1px solid ${T.border}`,
                }}
              >
                <div
                  style={{
                    fontSize: 9,
                    color: T.text3,
                    textTransform: 'uppercase',
                    letterSpacing: '.06em',
                  }}
                >
                  {strictT(tr, lang, 'kpi_label_net_profit')}
                </div>
                <div
                  style={{
                    fontFamily: 'monospace',
                    fontSize: 15,
                    fontWeight: 800,
                    color: Number(npL) >= 0 ? T.green : T.red,
                    direction: 'ltr',
                  }}
                >
                  {formatCompactForLang(Number(npL), lang)}
                </div>
              </div>
            ) : null}
          </div>
        </Sec>
      ) : null

    const branchBlock =
      payload.type === 'net_margin' && branchInfluence ? (
        <Sec label={strictT(tr, lang, 'cmd_kpi_margin_branch')} color={T.violet}>
          <p style={{ margin: 0, fontSize: 12, color: T.text2, lineHeight: 1.55, ...CLAMP_FADE_MASK_SHORT }}>
            <CmdServerText lang={lang} tr={tr} as="span">
              {branchInfluence}
            </CmdServerText>
          </p>
        </Sec>
      ) : null

    return (
      <>
        <div style={{ fontSize: 17, fontWeight: 800, color: T.text1, marginBottom: 6 }}>
          {strictT(tr, lang, `kpi_label_${payload.type}`)}
        </div>
        {payload.type === 'net_margin' && headlinePct ? (
          <>
            <div
              style={{
                fontFamily: 'monospace',
                fontSize: 28,
                fontWeight: 800,
                color: headlineColor,
                marginBottom: 6,
                direction: 'ltr',
              }}
            >
              {headlinePct}
            </div>
            <div className="cmd-muted-foreign" style={{ fontSize: 11, marginBottom: 12 }}>
              {strictT(tr, lang, 'cmd_kpi_margin_period_note')}
              {plab ? ` · ${plab}` : ''}
            </div>
          </>
        ) : null}
        <div style={{ fontSize: 12, color: T.text2, lineHeight: 1.55, marginBottom: 14 }}>
          {strictT(tr, lang, `kpi_explain_${payload.type}`)}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 14 }}>
          {[
            {
              lbl: strictT(tr, lang, 'exec_trend'),
              val:
                payload.mom != null
                  ? `${payload.mom > 0 ? '+' : ''}${formatPctForLang(Math.abs(payload.mom), 1, lang)} ${strictT(tr, lang, 'mom_label')}`
                  : '—',
              clr: payload.mom > 0 ? T.green : payload.mom < 0 ? T.red : T.text2,
            },
            {
              lbl: strictT(tr, lang, 'yoy_label'),
              val:
                payload.yoy != null
                  ? `${payload.yoy > 0 ? '+' : ''}${formatPctForLang(Math.abs(payload.yoy), 1, lang)}`
                  : '—',
              clr: payload.yoy > 0 ? T.green : payload.yoy < 0 ? T.red : T.text2,
            },
          ].map(({ lbl, val, clr }) => (
            <div key={lbl} style={{ background: T.card, borderRadius: 8, padding: '12px 14px', border: `1px solid ${T.border}` }}>
              <div style={{ fontSize: 9, color: T.text3, textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 4 }}>
                {lbl}
              </div>
              <div style={{ fontFamily: 'monospace', fontSize: 17, fontWeight: 800, color: clr }}>{val}</div>
            </div>
          ))}
        </div>
        <DrillIntelligenceBlock
          what={drillLines.what}
          why={drillLines.why}
          do={drillLines.do}
          tr={tr}
          lang={lang}
          theme={drillTheme}
        />
        {extra?.alerts?.length > 0 && (
          <Sec label={strictT(tr, lang, 'alerts_title')} color={T.amber}>
            {extra.alerts.slice(0, 3).map((a, i) => (
              <div
                key={i}
                style={{
                  padding: '9px 11px',
                  marginBottom: 6,
                  borderRadius: 8,
                  background: `${uClr[a.severity] || T.text3}0d`,
                  border: `1px solid ${uClr[a.severity] || T.text3}25`,
                }}
              >
                <div style={{ fontSize: 11, fontWeight: 700, color: uClr[a.severity] || T.text2, marginBottom: 2 }}>
                  <CmdServerText lang={lang} tr={tr} as="span">
                    {a.title}
                  </CmdServerText>
                </div>
                <div style={{ fontSize: 10, color: T.text2, lineHeight: 1.5, ...CLAMP_FADE_MASK_SHORT }}>
                  <CmdServerText lang={lang} tr={tr} as="span">
                    {a.message}
                  </CmdServerText>
                </div>
              </div>
            ))}
          </Sec>
        )}
        {payload.type === 'net_margin' ? (
          <>
            {factorBlock}
            {branchBlock}
          </>
        ) : null}
        {showTrend ? (
          <ExecutiveKpiTrendChart
            kpiBlock={extra.execChartBundle.kpi_block}
            cashflow={extra.execChartBundle.cashflow}
            kpiType={payload.type}
            tr={tr}
            lang={lang}
          />
        ) : null}
        {payload.type === 'net_profit' && extra?.execChartBundle?.kpi_block ? (
          <ExecutiveProfitBridgeChart kpiBlock={extra.execChartBundle.kpi_block} tr={tr} lang={lang} />
        ) : null}
      </>
    )
  }

  const Domain = () => {
    const causes = extra?.causes?.filter(c=>c.domain===payload.domain||c.domain==='cross_domain')||[]
    const dDecs  = extra?.decisions?.filter(d=>d.domain===payload.domain)||[]
    return (
      <>
        <div style={{display:'flex',alignItems:'center',gap:12,marginBottom:20}}>
          <span className="cmd-domain-glyph-wrap" style={{ width: 40, height: 40 }} aria-hidden>
            <DomainGlyph
              domain={payload.domain === 'leverage' ? 'leverage' : payload.domain}
              color={dc}
            />
          </span>
          <div style={{flex:1}}>
            <div style={{fontSize:17,fontWeight:800,color:T.text1}}>
              {strictT(tr, lang, `domain_${payload.domain}_simple`)}
            </div>
            <div style={{fontSize:11,color:T.text2,marginTop:2, ...CLAMP_FADE_MASK_SHORT}}>
              {strictT(tr, lang, `domain_${payload.domain}_exp`)}
            </div>
          </div>
          <div style={{textAlign:'right'}}>
            <div style={{fontFamily:'monospace',fontSize:22,fontWeight:800,color:dc}}>{payload.score!=null?Math.round(payload.score):'—'}</div>
            <div style={{fontSize:9,color:T.text3}}>/100</div>
          </div>
        </div>

        <DrillIntelligenceBlock
          what={drillLines.what}
          why={drillLines.why}
          do={drillLines.do}
          tr={tr}
          lang={lang}
          theme={drillTheme}
        />

        {causes.length>0 && (
          <Sec label={strictT(tr, lang, 'exec_why')} color={T.red}>
            {causes.slice(0,3).map((c,i) => (
              <div key={i} style={{padding:'9px 11px',marginBottom:6,borderRadius:8,
                background:`${uClr[c.impact]||T.text3}0d`,borderWidth:'1px',borderStyle:'solid',
                borderColor:`${uClr[c.impact]||T.text3}25`,
                borderLeftWidth:'3px',borderLeftColor:uClr[c.impact]||T.text3}}>
                <div style={{fontSize:11,fontWeight:700,color:T.text1,marginBottom:3}}>
                  <CmdServerText lang={lang} tr={tr} as="span">
                    {c.title}
                  </CmdServerText>
                </div>
                <div style={{fontSize:10,color:T.text2,lineHeight:1.5, ...CLAMP_FADE_MASK_SHORT}}>
                  <CmdServerText lang={lang} tr={tr} as="span">
                    {c.description}
                  </CmdServerText>
                </div>
              </div>
            ))}
          </Sec>
        )}

        {dDecs.length>0 && (
          <Sec label={strictT(tr, lang, 'exec_actions')} color={dc}>
            {dDecs.slice(0,2).map((d,i) => (
              <div key={i} style={{padding:'9px 11px',marginBottom:6,borderRadius:8,
                background:`${dc}08`,border:`1px solid ${dc}20`}}>
                <div style={{fontSize:11,fontWeight:700,color:T.text1,marginBottom:2}}>
                  <CmdServerText lang={lang} tr={tr} as="span">
                    {String(d.causal_realized?.change_text || d.causal_realized?.action_text || '').trim() ||
                      strictT(tr, lang, 'cmd_na_short')}
                  </CmdServerText>
                </div>
                <div style={{fontSize:10,color:T.text2,fontFamily:'monospace'}}>
                  <CmdServerText lang={lang} tr={tr} as="span">
                    {d.timeframe}
                  </CmdServerText>
                </div>
              </div>
            ))}
          </Sec>
        )}

        {Object.keys(payload.ratios||{}).length>0 && (
          <Sec label={strictT(tr, lang, 'exec_breakdown')} color={T.text3}>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8}}>
              {Object.entries(payload.ratios).slice(0,6).map(([k,r]) => {
                const rc = {good:T.green,warning:T.amber,risk:T.red,neutral:T.text2}[r?.status]||T.text2
                return (
                  <div key={k} style={{background:T.card,borderRadius:7,padding:'8px 10px',
                    borderWidth:'1px 1px 1px 2px',borderStyle:'solid',borderColor:`${T.border} ${T.border} ${T.border} ${rc}`}}>
                    <div style={{fontSize:8,color:T.text3,textTransform:'uppercase',marginBottom:2}}>
                      {strictT(tr, lang, `ratio_${k}`)}
                    </div>
                    <div style={{fontFamily:'monospace',fontSize:13,fontWeight:700,color:rc}}>
                      {r?.value!=null?r.value:'—'}
                      <span style={{fontSize:9,color:T.text3,marginLeft:3}}>{r?.unit||''}</span>
                    </div>
                  </div>
                )
              })}
            </div>
          </Sec>
        )}
      </>
    )
  }

  const Alert = () => (
    <>
      <div style={{fontSize:17,fontWeight:800,color:T.text1,lineHeight:1.3,marginBottom:10, ...CLAMP_FADE_MASK_SHORT}}>
        <CmdServerText lang={lang} tr={tr} as="span">
          {payload.title}
        </CmdServerText>
      </div>
      <div style={{ marginBottom: 20 }}>
        <Pill label={strictT(tr, lang, `urgency_${payload.severity}`)} critical={payload.severity === 'high'} />
      </div>
      <DrillIntelligenceBlock
        what={drillLines.what}
        why={drillLines.why}
        do={drillLines.do}
        tr={tr}
        lang={lang}
        theme={drillTheme}
      />
      <Sec label={strictT(tr, lang, 'exec_why')} color={uClr[payload.severity]||T.amber}>
        <p style={{fontSize:12,color:T.text2,lineHeight:1.75,margin:0, ...CLAMP_FADE_MASK_SHORT}}>
          <CmdServerText lang={lang} tr={tr} as="span">
            {payload.message}
          </CmdServerText>
        </p>
      </Sec>
      <Sec label={strictT(tr, lang, 'exec_actions')} color={T.accent}>
        <p style={{fontSize:12,color:T.text2,lineHeight:1.75,margin:0, ...CLAMP_FADE_MASK_SHORT}}>
          <CmdServerText lang={lang} tr={tr} as="span">
            {payload.action}
          </CmdServerText>
        </p>
      </Sec>
    </>
  )

  const ProfitBridgeDrill = () => {
    const pl = payload || {}
    const vline = pl.varianceLine || {}
    const kpiType = pl.kpiTrendType || 'net_profit'
    const lineLabel = strictT(tr, lang, pl.labelKey || 'cmd_p3_profit_path_title')
    const weight = pl.impactWeightPct
    const sub =
      pl.latestPeriod && pl.previousPeriod
        ? `${String(pl.previousPeriod).slice(0, 7)} → ${String(pl.latestPeriod).slice(0, 7)}`
        : null
    return (
      <>
        <div style={{ fontSize: 17, fontWeight: 800, color: T.text1, lineHeight: 1.3, marginBottom: 6 }}>
          {lineLabel}
        </div>
        {sub ? (
          <div className="cmd-muted-foreign" style={{ fontSize: 11, marginBottom: 14 }}>
            {sub}
          </div>
        ) : null}
        <Sec label={strictT(tr, lang, 'cmd_bridge_drill_breakdown')} color={T.accent}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
            {[
              { lbl: strictT(tr, lang, 'cmd_bridge_drill_value_current'), val: vline.current },
              { lbl: strictT(tr, lang, 'cmd_bridge_drill_value_previous'), val: vline.previous },
            ].map(({ lbl, val }) => (
              <div
                key={lbl}
                style={{
                  background: T.card,
                  borderRadius: 8,
                  padding: '10px 12px',
                  border: `1px solid ${T.border}`,
                }}
              >
                <div
                  style={{
                    fontSize: 9,
                    color: T.text3,
                    textTransform: 'uppercase',
                    letterSpacing: '.06em',
                    marginBottom: 4,
                  }}
                >
                  {lbl}
                </div>
                <div
                  style={{
                    fontFamily: 'monospace',
                    fontSize: 15,
                    fontWeight: 800,
                    color: T.text1,
                    direction: 'ltr',
                  }}
                >
                  {val != null && Number.isFinite(Number(val)) ? formatCompactForLang(Number(val), lang) : '—'}
                </div>
              </div>
            ))}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div
              style={{
                background: T.card,
                borderRadius: 8,
                padding: '10px 12px',
                border: `1px solid ${T.border}`,
              }}
            >
              <div
                style={{
                  fontSize: 9,
                  color: T.text3,
                  textTransform: 'uppercase',
                  letterSpacing: '.06em',
                  marginBottom: 4,
                }}
              >
                {strictT(tr, lang, 'cmd_bridge_drill_delta')}
              </div>
              <div
                style={{
                  fontFamily: 'monospace',
                  fontSize: 15,
                  fontWeight: 800,
                  color: T.text1,
                  direction: 'ltr',
                }}
              >
                {vline.delta != null && Number.isFinite(Number(vline.delta))
                  ? formatCompactSignedForLang(Number(vline.delta), lang)
                  : '—'}
              </div>
            </div>
            <div
              style={{
                background: T.card,
                borderRadius: 8,
                padding: '10px 12px',
                border: `1px solid ${T.border}`,
              }}
            >
              <div
                style={{
                  fontSize: 9,
                  color: T.text3,
                  textTransform: 'uppercase',
                  letterSpacing: '.06em',
                  marginBottom: 4,
                }}
              >
                {strictT(tr, lang, 'cmd_bridge_drill_delta_pct')}
              </div>
              <div
                style={{
                  fontFamily: 'monospace',
                  fontSize: 15,
                  fontWeight: 800,
                  color: T.text1,
                  direction: 'ltr',
                }}
              >
                {vline.delta_pct != null && Number.isFinite(Number(vline.delta_pct))
                  ? formatSignedPctForLang(Number(vline.delta_pct), 1, lang)
                  : '—'}
              </div>
            </div>
          </div>
          {weight != null && Number.isFinite(Number(weight)) ? (
            <div style={{ marginTop: 12, fontSize: 11, color: T.text2, lineHeight: 1.5 }}>
              {strictTParams(tr, lang, 'cmd_bridge_drill_weight_line', { weight: String(weight) })}
            </div>
          ) : null}
        </Sec>
        <Sec label={strictT(tr, lang, 'cmd_bridge_drill_accounts_sec')} color={T.text3}>
          <p style={{ margin: 0, fontSize: 12, color: T.text2, lineHeight: 1.65 }}>
            {strictT(tr, lang, 'cmd_bridge_drill_accounts_hint')}
          </p>
        </Sec>
        <DrillIntelligenceBlock
          what={drillLines.what}
          why={drillLines.why}
          do={drillLines.do}
          tr={tr}
          lang={lang}
          theme={drillTheme}
        />
        {extra?.execChartBundle?.kpi_block ? (
          <>
            <div
              style={{
                fontSize: 10,
                fontWeight: 800,
                color: T.text3,
                textTransform: 'uppercase',
                letterSpacing: '.08em',
                marginTop: 18,
                marginBottom: 8,
              }}
            >
              {strictT(tr, lang, 'cmd_bridge_drill_trend')}
            </div>
            <ExecutiveKpiTrendChart
              kpiBlock={extra.execChartBundle.kpi_block}
              cashflow={extra.execChartBundle.cashflow}
              kpiType={kpiType}
              tr={tr}
              lang={lang}
            />
          </>
        ) : null}
      </>
    )
  }

  const ExpenseDecisionV2 = () => {
    const d = payload || {}
    const pri = String(d.priority || 'medium').toLowerCase()
    const efi = d.expected_financial_impact || {}
    const sav = efi.estimated_monthly_savings
    const rc =
      (d.causal_realized && String(d.causal_realized.change_text || d.causal_realized.action_text || '').trim()
        ? d.causal_realized
        : null) || pickExpenseCausalRow(extra?.drillIntelBundle?.realizedCausalItems)
    const headline =
      String(rc?.change_text || rc?.action_text || '').trim() || strictT(tr, lang, 'cmd_na_short')
    const causeBody = String(rc?.cause_text || '').trim()
    const actionBody = String(rc?.action_text || '').trim()
    return (
      <>
        <div style={{ fontSize: 17, fontWeight: 800, color: T.text1, marginBottom: 10, ...CLAMP_FADE_MASK_SHORT }}>
          <CmdServerText lang={lang} tr={tr} as="span">
            {headline}
          </CmdServerText>
        </div>
        <div style={{ marginBottom: 16 }}>
          <Pill label={strictT(tr, lang, `urgency_${pri}`)} critical={pri === 'high'} />
        </div>
        <DrillIntelligenceBlock
          what={drillLines.what}
          why={drillLines.why}
          do={drillLines.do}
          tr={tr}
          lang={lang}
          theme={drillTheme}
        />
        {causeBody ? (
          <Sec label={strictT(tr, lang, 'exec_why')} color={T.red}>
            <p style={{ margin: 0, fontSize: 12, color: T.text2, lineHeight: 1.75, ...CLAMP_FADE_MASK_SHORT }}>
              <CmdServerText lang={lang} tr={tr} as="span">
                {causeBody}
              </CmdServerText>
            </p>
          </Sec>
        ) : null}
        {actionBody ? (
          <Sec label={strictT(tr, lang, 'exec_actions')} color={T.accent}>
            <p style={{ margin: 0, fontSize: 12, color: T.text2, lineHeight: 1.75, ...CLAMP_FADE_MASK_SHORT }}>
              <CmdServerText lang={lang} tr={tr} as="span">
                {actionBody}
              </CmdServerText>
            </p>
          </Sec>
        ) : null}
        {sav != null && Number.isFinite(Number(sav)) && Number(sav) > 0 ? (
          <Sec label={strictT(tr, lang, 'cmd_dec_impact_monthly')} color={T.green}>
            <div style={{ fontFamily: 'monospace', fontSize: 18, fontWeight: 800, color: T.green, direction: 'ltr' }}>
              {formatCompactForLang(sav, lang)}
            </div>
          </Sec>
        ) : null}
        {extra?.execChartBundle?.kpi_block ? (
          <ExecutiveProfitBridgeChart kpiBlock={extra.execChartBundle.kpi_block} tr={tr} lang={lang} />
        ) : null}
      </>
    )
  }

  return (
    <>
      <div onClick={onClose} style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.5)',zIndex:998}}/>
      <div style={{position:'fixed',top:0,right:0,bottom:0,width:460,
        background:T.panel,borderLeft:`1px solid ${T.border}`,
        zIndex:999,display:'flex',flexDirection:'column',
        boxShadow:'-24px 0 80px rgba(0,0,0,0.75)',
        animation:'slideIn .22s cubic-bezier(.4,0,.2,1)'}}>
        <div style={{padding:'16px 24px',borderBottom:`1px solid ${T.border}`,
          display:'flex',alignItems:'center',gap:10,flexShrink:0}}>
          <div style={{flex:1,fontSize:10,fontWeight:700,color:T.text2,
            textTransform:'uppercase',letterSpacing:'.07em'}}>
            {type==='expense_v2'?strictT(tr, lang, 'cmd_expense_decision_detail')
             :type==='causal_item'?strictT(tr, lang, 'tab_decisions_v2')
             :type==='decision'?strictT(tr, lang, 'tab_decisions_v2')
             :type==='kpi'?strictT(tr, lang, 'exec_kpi_title')
             :type==='domain'?strictT(tr, lang, 'exec_domain_title')
             :type==='alert'?strictT(tr, lang, 'alerts_title')
             :type==='branch_compare'?strictT(tr, lang, 'cmd_chart_branch_panel_title')
             :type==='profit_bridge_segment'?strictT(tr, lang, 'cmd_bridge_segment_drill_title')
             :strictT(tr, lang, 'exec_title')}
          </div>
          <button onClick={onClose} style={{width:30,height:30,borderRadius:8,
            border:`1px solid ${T.border}`,background:T.card,color:T.text2,
            cursor:'pointer',display:'flex',alignItems:'center',justifyContent:'center',
            fontSize:17,fontWeight:300}}>×</button>
        </div>
        <div style={{flex:1,overflowY:'auto',padding:'24px 24px'}}>
          {type==='expense_v2' && <ExpenseDecisionV2/>}
          {type==='causal_item' && <CausalItem/>}
          {type==='decision' && <Decision/>}
          {type==='kpi'      && <Kpi/>}
          {type==='domain'   && <Domain/>}
          {type==='alert'    && <Alert/>}
          {type==='branch_compare' && (
            <>
              <ExecutiveBranchCompareChart
                comparativeIntelligence={extra?.execChartBundle?.comparative_intelligence}
                tr={tr}
                lang={lang}
              />
              <DrillIntelligenceBlock
                what={drillLines.what}
                why={drillLines.why}
                do={drillLines.do}
                tr={tr}
                lang={lang}
                theme={drillTheme}
              />
            </>
          )}
          {type === 'profit_bridge_segment' && <ProfitBridgeDrill />}
        </div>
        {!!onNavigate && (
          <div style={{padding:'12px 24px',borderTop:`1px solid ${T.border}`,background:T.surface}}>
            <button onClick={onNavigate} style={{width:'100%',padding:'10px 12px',borderRadius:10,
              border:`1px solid ${T.border}`,background:'transparent',color:T.text1,
              fontSize:12,fontWeight:800,cursor:'pointer'}}>
              {type==='expense_v2' || type==='causal_item'
                ? strictT(tr, lang, 'cmd_open_full_analysis_decisions')
                : type==='branch_compare'
                  ? strictT(tr, lang, 'cmd_open_branches')
                  : strictT(tr, lang, 'open_analysis')}
            </button>
          </div>
        )}
      </div>
    </>
  )
}

/** KPI strip icons — 1.5px stroke; optional semanticAccent aligns stroke with tile color. */
const KPI_GLYPH_SEM_STROKE = {
  rev: '#38bdf8',
  exp: '#f87171',
  profit: '#34d399',
  margin: '#e2e8f0',
  cash: '#22d3ee',
  neutral: '#cbd5e1',
}
const KPI_GLYPH_DEFAULT_STROKE = {
  revenue: 'rgba(56, 189, 248, 0.9)',
  expenses: 'rgba(248, 113, 113, 0.88)',
  net_profit: 'rgba(45, 212, 191, 0.9)',
  cashflow: 'rgba(125, 211, 252, 0.88)',
  net_margin: 'rgba(167, 139, 250, 0.9)',
  working_capital: 'rgba(56, 189, 248, 0.9)',
}

function KpiDockGlyph({ metricKey, semanticAccent = null }) {
  const sw = 1.5
  const s =
    semanticAccent && KPI_GLYPH_SEM_STROKE[semanticAccent]
      ? KPI_GLYPH_SEM_STROKE[semanticAccent]
      : KPI_GLYPH_DEFAULT_STROKE[metricKey] || 'rgba(148,163,184,0.75)'
  const box = { width: 18, height: 18, viewBox: '0 0 24 24', fill: 'none', 'aria-hidden': true }
  switch (metricKey) {
    case 'revenue':
      return (
        <svg {...box}>
          <path d="M4 17V8l4 3 4-4 4 3 4-5" stroke={s} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" />
          <path d="M4 19h16" stroke={s} strokeWidth={sw} strokeLinecap="round" opacity="0.45" />
        </svg>
      )
    case 'expenses':
      return (
        <svg {...box}>
          <path d="M6 6v12M10 9v9M14 5v13M18 11v7" stroke={s} strokeWidth={sw} strokeLinecap="round" />
          <path d="M5 18h14" stroke={s} strokeWidth={sw} strokeLinecap="round" opacity="0.4" />
        </svg>
      )
    case 'net_profit':
      return (
        <svg {...box}>
          <rect x="5" y="6" width="14" height="12" rx="1.5" stroke={s} strokeWidth={sw} />
          <path d="M8 14h8M8 10h5" stroke={s} strokeWidth={sw} strokeLinecap="round" />
        </svg>
      )
    case 'cashflow':
      return (
        <svg {...box}>
          <circle cx="8" cy="12" r="2.5" stroke={s} strokeWidth={sw} />
          <path d="M12 12h6M16 8v8" stroke={s} strokeWidth={sw} strokeLinecap="round" />
          <path d="M5 12H2M22 12h-3" stroke={s} strokeWidth={sw} strokeLinecap="round" opacity="0.5" />
        </svg>
      )
    case 'net_margin':
      return (
        <svg {...box}>
          <path d="M5 18V6h6v12H5z" stroke={s} strokeWidth={sw} strokeLinejoin="round" />
          <path d="M14 18V10h5v8h-5z" stroke={s} strokeWidth={sw} strokeLinejoin="round" opacity="0.75" />
        </svg>
      )
    case 'working_capital':
      return (
        <svg {...box}>
          <path d="M5 8h14M5 8v10M19 8v10" stroke={s} strokeWidth={sw} strokeLinecap="round" />
          <path d="M8 12h3.5v5H8zM12.5 11H16v6h-3.5z" stroke={s} strokeWidth={sw} strokeLinejoin="round" />
        </svg>
      )
    default:
      return (
        <svg {...box}>
          <circle cx="12" cy="12" r="3.5" stroke={s} strokeWidth={sw} />
        </svg>
      )
  }
}

/** Domain grid / drill — same stroke system as KPI (1.5px, 20×20). */
function DomainGlyph({ domain, color }) {
  const stroke = color || 'rgba(56, 189, 248, 0.9)'
  const sw = 1.5
  const box = { width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none', 'aria-hidden': true }
  switch (domain) {
    case 'profitability':
      return (
        <svg {...box}>
          <path d="M4 17V7l4 3 4-3 4 2 4-4" stroke={stroke} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" />
          <path d="M4 19h16" stroke={stroke} strokeWidth={sw} strokeLinecap="round" opacity="0.4" />
        </svg>
      )
    case 'liquidity':
      return (
        <svg {...box}>
          <path
            d="M12 5c-3.5 3-5 6.5 0 14 5-7.5 3.5-11 0-14z"
            stroke={stroke}
            strokeWidth={sw}
            strokeLinejoin="round"
          />
          <path d="M12 9v6" stroke={stroke} strokeWidth={sw} strokeLinecap="round" />
        </svg>
      )
    case 'efficiency':
      return (
        <svg {...box}>
          <circle cx="12" cy="12" r="7" stroke={stroke} strokeWidth={sw} />
          <path d="M12 12l4-2" stroke={stroke} strokeWidth={sw} strokeLinecap="round" />
          <path d="M12 5v2.5" stroke={stroke} strokeWidth={sw} strokeLinecap="round" />
        </svg>
      )
    case 'risk':
      return (
        <svg {...box}>
          <path
            d="M12 4l7 4v8l-7 4-7-4V8l7-4z"
            stroke={stroke}
            strokeWidth={sw}
            strokeLinejoin="round"
          />
          <path d="M12 9v5" stroke={stroke} strokeWidth={sw} strokeLinecap="round" />
        </svg>
      )
    case 'leverage':
      return (
        <svg {...box}>
          <path d="M5 17V8M19 17V8M5 8l7-3 7 3" stroke={stroke} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" />
          <path d="M9 17v-4M15 17v-4" stroke={stroke} strokeWidth={sw} strokeLinecap="round" />
        </svg>
      )
    case 'growth':
      return (
        <svg {...box}>
          <path d="M5 16V9M5 9l4-3 4 3 5-5" stroke={stroke} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round" />
          <path d="M4 18h16" stroke={stroke} strokeWidth={sw} strokeLinecap="round" opacity="0.35" />
        </svg>
      )
    default:
      return (
        <svg {...box}>
          <circle cx="12" cy="12" r="3.5" stroke={stroke} strokeWidth={sw} />
        </svg>
      )
  }
}

function ExecutiveKpiRow({
  kpis,
  cashflow,
  main,
  tr,
  lang,
  onSelect,
  alerts,
  ctxLabel,
  hideTitle = false,
  layout = 'dashboard',
  supportingOnly = false,
}) {
  const na = strictT(tr, lang, 'cmd_na_short')
  const dispFull = (v) => (v == null || v === '' || isNaN(Number(v)) ? null : formatFullForLang(v, lang))
  const cfEstimated = cashflow?.reliability === 'estimated'
  const wc       = kpis.working_capital?.value
  const wcColor  = wc==null?T.text3:wc>=0?T.green:T.red
  const heroKey = 'net_profit'
  const cards = [
    { key:'revenue',         raw:kpis.revenue?.value,        mode:'money', signedTone:false, full:dispFull(kpis.revenue?.value),        mom:kpis.revenue?.mom_pct,    yoy:kpis.revenue?.yoy_pct,    color:T.text3 },
    { key:'expenses',        raw:kpis.expenses?.value,       mode:'money', signedTone:false, full:dispFull(kpis.expenses?.value),       mom:kpis.expenses?.mom_pct,   yoy:kpis.expenses?.yoy_pct,   color:T.text3 },
    { key:'net_profit',      raw:kpis.net_profit?.value,     mode:'money', signedTone:true,  full:dispFull(kpis.net_profit?.value),      mom:kpis.net_profit?.mom_pct, yoy:kpis.net_profit?.yoy_pct, color:T.text3 },
    { key:'cashflow',        raw:cashflow?.operating_cashflow, mode:'money', signedTone:true, full:dispFull(cashflow?.operating_cashflow), mom:cashflow?.operating_cashflow_mom, yoy:null, color:T.text3, estimated:cfEstimated },
    { key:'net_margin',      raw:kpis.net_margin?.value,     mode:'percent', signedTone:true, full:null, mom:kpis.net_margin?.mom_pct, yoy:null, color:T.text3 },
    { key:'working_capital', raw:wc,                         mode:'money', signedTone:true,  full:dispFull(wc),                          mom:null,                     yoy:null, sub:wc!=null&&wc<0?strictT(tr, lang, 'wc_negative'):null, color:wcColor },
  ]
  const ordered = [
    ...cards.filter(c=>c.key===heroKey),
    ...cards.filter(c=>c.key!==heroKey),
  ]
  const hero = ordered[0]
  const secondary = ordered.slice(1)

  const renderCard = (c, { isHero, compact = false, cinematic = false }) => {
    const mc = c.mom==null?T.text3:c.mom>0?T.green:c.mom<0?T.red:T.text2
    const explain = strictT(tr, lang, `kpi_explain_${c.key}`)
    const base = strictT(tr, lang, `kpi_label_${c.key}`)
    const ctx = ctxLabel()
    const tplRaw = strictT(tr, lang, 'kpi_with_context')
    const miss = localizedMissingPlaceholder(lang)
    const labelWithCtx =
      ctx && tplRaw !== miss ? tplRaw.replace(/\{label\}/g, base).replace(/\{context\}/g, ctx) : base
    const cmdFocus = layout === 'command' && c.key === 'net_profit'
    const expenseTone = c.key === 'expenses'
    const cardClass = cinematic
      ? `cmd-cine-kpi-card cmd-kpi-card cmd-cine-kpi-card--sem-${c.key === 'revenue' ? 'rev' : c.key === 'expenses' ? 'exp' : c.key === 'net_profit' ? 'profit' : c.key === 'net_margin' ? 'margin' : c.key === 'cashflow' ? 'cash' : 'neutral'}`.trim()
      : `cmd-kpi-card cmd-card-hover${expenseTone ? ' cmd-kpi-card--expense-tone' : ''}`.trim()
    const cardStyle = cinematic
      ? { cursor: 'pointer', padding: 0 }
      : {
          background: CARD_BG,
          border: cmdFocus ? CMD_ACCENT_BD : NEU_BD,
          borderRadius: 14,
          padding: isHero ? '16px 18px' : compact ? '14px 16px' : '16px 18px',
          boxShadow: cmdFocus ? 'inset 0 0 0 1px rgba(0,212,170,0.1), 0 4px 26px rgba(0,0,0,0.28)' : undefined,
          cursor: 'pointer',
        }
    const cinematicSem =
      c.key === 'revenue'
        ? 'rev'
        : c.key === 'expenses'
          ? 'exp'
          : c.key === 'net_profit'
            ? 'profit'
            : c.key === 'net_margin'
              ? 'margin'
              : c.key === 'cashflow'
                ? 'cash'
                : 'neutral'

    if (cinematic) {
      return (
        <div
          key={c.key}
          className={cardClass}
          onClick={() =>
            onSelect(
              'kpi',
              { type: c.key, mom: c.mom, yoy: c.yoy, raw: c.raw, mode: c.mode || 'money' },
              { alerts: alerts?.filter((a) => a.impact === 'profitability') || [], explanation: explain },
            )
          }
          title={explain}
          style={cardStyle}
        >
          <div className="cmd-cine-kpi-stack">
            <div className="cmd-cine-kpi-label-row">
              <span className="cmd-cine-kpi-glyph" aria-hidden>
                <KpiDockGlyph metricKey={c.key} semanticAccent={cinematicSem} />
              </span>
              <span className="cmd-cine-kpi-label">{base}</span>
            </div>
            <div className="cmd-cine-kpi-metric-band">
              <KpiMainNumber
                raw={c.raw}
                mode={c.mode || 'money'}
                isHero={false}
                compact
                na={na}
                signedTone={c.key === 'net_margin' ? false : !!c.signedTone}
                lang={lang}
                cinematicSemantic={cinematicSem}
              />
              {c.full ? (
                <div className="cmd-kpi-full-amount cmd-cine-kpi-full-amount">{c.full}</div>
              ) : null}
            </div>
            <div className="cmd-cine-kpi-delta-row">
              <div className="cmd-cine-kpi-delta-pills">
                {c.mom != null && (
                  <span className="cmd-kpi-mom-pill cmd-data-num cmd-cine-kpi-pill" style={{ color: mc }}>
                    {c.mom > 0 ? '+' : ''}
                    {formatPctForLang(Math.abs(c.mom), 1, lang)} {strictT(tr, lang, 'mom_label')}
                  </span>
                )}
                {c.yoy != null && (
                  <span
                    className="cmd-kpi-mom-pill cmd-data-num cmd-cine-kpi-pill"
                    style={{ color: c.yoy > 0 ? T.green : c.yoy < 0 ? T.red : T.text2 }}
                  >
                    {c.yoy > 0 ? '+' : ''}
                    {formatPctForLang(Math.abs(c.yoy), 1, lang)} {strictT(tr, lang, 'yoy_label')}
                  </span>
                )}
              </div>
              {ctx && tplRaw !== miss ? (
                <span className="cmd-cine-kpi-period">{ctx}</span>
              ) : null}
            </div>
            {c.estimated ? <div className="cmd-cine-kpi-est">{strictT(tr, lang, 'estimated')}</div> : null}
            {c.sub ? <div className="cmd-cine-kpi-sub">{c.sub}</div> : null}
            <CmdSparkline mom={c.mom} />
          </div>
        </div>
      )
    }

    return (
      <div key={c.key}
        className={cardClass}
        onClick={()=>onSelect('kpi',{type:c.key,mom:c.mom,yoy:c.yoy,raw:c.raw,mode:c.mode||'money'},
          {alerts:alerts?.filter(a=>a.impact==='profitability')||[], explanation:explain})}
        title={explain}
        style={cardStyle}
      >
        <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:isHero?8:compact?6:6}}>
          <span
            style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: isHero ? 28 : compact ? 22 : 24,
                    height: isHero ? 28 : compact ? 22 : 24,
                    borderRadius: 8,
                    flexShrink: 0,
                    background: 'rgba(0,0,0,0.22)',
                    border: '1px solid rgba(148,163,184,0.14)',
                  }}
            aria-hidden
          >
            <KpiDockGlyph metricKey={c.key} />
          </span>
          <span
            className={`cmd-kpi-dimension-label ${isHero ? 'cmd-kpi-dimension-label--hero' : ''}`.trim()}
            style={{ fontSize: isHero ? 11 : compact ? 9 : 10 }}
          >
            {labelWithCtx}
          </span>
          {isHero && (
            <span style={{marginLeft:'auto',fontSize:9,fontWeight:900,color:T.text3,letterSpacing:'.10em',textTransform:'uppercase'}}>
              {strictT(tr, lang, 'primary')}
            </span>
          )}
        </div>
        <KpiMainNumber
          raw={c.raw}
          mode={c.mode || 'money'}
          isHero={isHero}
          compact={compact}
          na={na}
          signedTone={!!c.signedTone}
          lang={lang}
        />
        {c.full && (
          <div className="cmd-kpi-full-amount">
            {c.full}
          </div>
        )}
        <div style={{display:'flex',gap:6,flexWrap:'wrap'}}>
          {c.mom!=null && (
            <span className="cmd-kpi-mom-pill cmd-data-num" style={{fontFamily:'var(--font-mono)',fontSize:12,fontWeight:700,color:mc,
              padding:'2px 8px',borderRadius:10,background:'rgba(148,163,184,0.14)'}}>
              {c.mom>0?'+':''}{formatPctForLang(Math.abs(c.mom), 1, lang)} {strictT(tr, lang, 'mom_label')}
            </span>
          )}
          {c.yoy!=null && (
            <span className="cmd-kpi-mom-pill cmd-data-num" style={{fontFamily:'monospace',fontSize:12,
              color:c.yoy>0?T.green:c.yoy<0?T.red:T.text2}}>
              {c.yoy>0?'+':''}{formatPctForLang(Math.abs(c.yoy), 1, lang)} {strictT(tr, lang, 'yoy_label')}
            </span>
          )}
        </div>
        {c.estimated && (
            <div
              style={{
                marginTop: 8,
                fontSize: 10,
                color: T.text3,
                padding: '3px 9px',
                borderRadius: 8,
                background: 'rgba(255,255,255,0.055)',
                border: NEU_BD,
                display: 'inline-block',
              }}
            >
              {strictT(tr, lang, 'estimated')}
            </div>
          )}
        {c.sub && <div style={{marginTop:6,fontSize:12,color:T.text3}}>{c.sub}</div>}
        <CmdSparkline mom={c.mom} />
      </div>
    )
  }

  if (layout === 'cinematic') {
    const cineOrder = ['revenue', 'expenses', 'net_profit', 'cashflow', 'net_margin']
    const cineCards = cineOrder.map((k) => cards.find((card) => card.key === k)).filter(Boolean)
    return (
      <div className="cmd-cine-kpi-dock">
        <div className="cmd-cine-kpi-strip">
          {cineCards.map((card) => renderCard(card, { isHero: false, compact: true, cinematic: true }))}
        </div>
      </div>
    )
  }

  if (layout === 'command') {
    const cmdOrder = ['revenue', 'expenses', 'net_profit', 'net_margin']
    const cmdCards = cmdOrder.map((k) => cards.find((c) => c.key === k)).filter(Boolean)
    return (
      <div
        className="cmd-kpi-four"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
          gap: supportingOnly ? 8 : 16,
          opacity: supportingOnly ? 0.9 : 1,
        }}
      >
        {cmdCards.map((c) => renderCard(c, { isHero: false, compact: supportingOnly }))}
      </div>
    )
  }

  return (
    <div>
      {!hideTitle ? (
        <div style={{fontSize:11,fontWeight:700,color:T.text3,textTransform:'uppercase',
          letterSpacing:'.08em',marginBottom:14}}>{strictT(tr, lang, 'exec_kpi_title')}</div>
      ) : null}
      {/* Hero KPI + secondary KPIs (avoid equal weight) */}
      <div style={{display:'grid',gridTemplateColumns:'1.25fr 1fr',gap:16,alignItems:'stretch'}}>
        <div style={{minWidth:0}}>
          {hero ? renderCard(hero, { isHero:true }) : null}
        </div>
        <div style={{minWidth:0,display:'grid',gridTemplateColumns:'repeat(2,1fr)',gap:16}}>
          {secondary.map(c => renderCard(c, { isHero:false }))}
        </div>
      </div>
    </div>
  )
}

export default function CommandCenter() {
  const { authFetch } = useAuth()
  const { tr, lang }   = useLang()
  const { selectedId, selectedCompany } = useCompany()
  const { toQueryString: scopeQS, params: ps, update: psUpdate, setResolved: psSetResolved,
    getActiveLabel: psActiveLabel, isIncompleteCustom: psIncomplete, window: win, setWindow: setWin } = usePeriodScope()
  const navigate = useNavigate()

  const ctxLabel = () =>
    kpiContextLabel({
      window: win,
      ps,
      latestPeriod: main?.intelligence?.latest_period || '',
      lang,
      tr: (k) => strictT(tr, lang, k),
    })

  const [intel,    setIntel]    = useState(null)
  const [decs,     setDecs]     = useState(null)
  const [causes,   setCauses]   = useState(null)
  const [alerts,   setAlerts]   = useState(null)
  const [main,     setMain]     = useState(null)
  const [fcData,   setFcData]   = useState(null)
  const [loading,  setLoading]  = useState(false)
  const prevLoadingRef = useRef(false)
  const [dashEnterCls, setDashEnterCls] = useState('')
  const [consolidate, setConsolidate] = useState(false)
  const [noDataMsg, setNoDataMsg] = useState(null)
  const [narrative, setNarrative] = useState(null)

  const [impacts, setImpacts] = useState({})
  const [pType, setPType] = useState(null)
  const [pLoad, setPLoad] = useState(null)
  const [pXtra, setPXtra] = useState(null)
  const [bridgeSelKey, setBridgeSelKey] = useState(null)
  const [intelActiveTile, setIntelActiveTile] = useState(null)

  const drillAnalysis = useCallback(
    (tab) => {
      const { path, focus } = pathForDrillAnalysisTab(tab || 'overview')
      navigate(path, { state: { focus } })
    },
    [navigate],
  )

  const load = useCallback(async () => {
    if (!selectedId) return
    if (psIncomplete()) return
    const qs = buildAnalysisQuery(scopeQS, { lang, window: win, consolidate })
    if (qs === null) return
    setLoading(true)
    setNoDataMsg(null)
    try {
      const r = await authFetch(`${API}/analysis/${selectedId}/executive?${qs}`, { headers: auth() })
      if (!r.ok) {
        if (r.status === 422) {
          setMain(null)
          setNarrative(null)
          setNoDataMsg(strictT(tr, lang, 'err_no_financial_data'))
        }
        return
      }
      const j = await r.json(); const d = j.data||{}
      setNarrative(buildExecutiveNarrative(d, { lang, t: tr }))
      psSetResolved(j.meta?.scope || null)
      setIntel(d.intelligence||null)
      setDecs(d.decisions||[])
      setCauses(d.root_causes||[])
      setAlerts(d.alerts||[])
      const impMap = {}
      ;(d.decision_impacts||[]).forEach(item => { impMap[item.decision_key||item.domain] = item })
      setImpacts(impMap)
      setMain({
        health_score_v2:     d.health_score_v2,
        kpi_block:           d.kpi_block,
        cashflow:            d.cashflow,
        statements:          d.statements || null,
        stmtInsights:        d.statements?.insights || [],
        periods:             j.meta?.periods||[],
        intelligence:        { latest_period: j.meta?.periods?.slice(-1)[0] },
        pipeline_validation: j.meta?.pipeline_validation || null,
        scope_label:         j.meta?.scope?.label || null,
        all_periods:         j.meta?.all_periods || [],
        comparative_intelligence: d.comparative_intelligence ?? null,
        financial_brain:          d.financial_brain ?? null,
        expense_decisions_v2:     d.expense_decisions_v2 ?? [],
        expense_intelligence:     d.expense_intelligence ?? null,
        realized_causal_items:    d.realized_causal_items ?? [],
        structured_income_statement: d.structured_income_statement ?? null,
        structured_income_statement_variance: d.structured_income_statement_variance ?? null,
        structured_income_statement_margin_variance:
          d.structured_income_statement_margin_variance ?? null,
        structured_income_statement_variance_meta:
          d.structured_income_statement_variance_meta ?? null,
        structured_profit_bridge: d.structured_profit_bridge ?? null,
        structured_profit_bridge_interpretation: d.structured_profit_bridge_interpretation ?? null,
        structured_profit_story: d.structured_profit_story ?? null,
        intel_tile_hints: d.intel_tile_hints ?? null,
      })
      setFcData(d.forecast && typeof d.forecast === 'object' ? d.forecast : null)
    } finally {
      setLoading(false)
    }
  }, [selectedId, lang, consolidate, win, scopeQS, tr, psIncomplete, psSetResolved, authFetch])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (prevLoadingRef.current && !loading && main) {
      setDashEnterCls('cmd-dash-content-enter')
      const t = window.setTimeout(() => setDashEnterCls(''), 230)
      return () => window.clearTimeout(t)
    }
    prevLoadingRef.current = loading
  }, [loading, main])

  const health = main?.health_score_v2 ?? intel?.health_score_v2 ?? null
  const status = intel?.status ?? (health!=null ? health>=80?'excellent':health>=60?'good':health>=40?'warning':'risk' : 'neutral')
  const kpis   = main?.kpi_block?.kpis || {}
  const intelForecastReady = useMemo(
    () => fcData != null && typeof fcData === 'object' && Object.keys(fcData).length > 0,
    [fcData],
  )
  const intelLiquidityHint = useMemo(
    () => (main ? liquidityHintLine(main.intel_tile_hints, tr, lang) : null),
    [main, tr, lang],
  )
  const intelEfficiencyHint = useMemo(
    () => (main ? efficiencyHintLine(main.intel_tile_hints, tr, lang) : null),
    [main, tr, lang],
  )
  const intelRiskScore = useMemo(() => {
    const s = intel?.surface_scores?.risk_composite
    return s != null && Number.isFinite(Number(s)) ? Number(s) : null
  }, [intel])
  const intelHighAlertCount = useMemo(
    () => (alerts || []).filter((a) => a.severity === 'high').length,
    [alerts],
  )
  const intelAlertCount = useMemo(() => (alerts || []).length, [alerts])
  const intelLiquidityScore = useMemo(() => {
    const s = intel?.surface_scores?.liquidity
    return s != null && Number.isFinite(Number(s)) ? Number(s) : null
  }, [intel])
  const intelEfficiencyScore = useMemo(() => {
    const s = intel?.surface_scores?.efficiency
    return s != null && Number.isFinite(Number(s)) ? Number(s) : null
  }, [intel])
  const intelForecastPrimaryMetric = useMemo(() => {
    if (!fcData?.available) return null
    const bRev = fcData?.scenarios?.base?.revenue?.[0]
    return bRev?.point != null ? formatCompactForLang(Number(bRev.point), lang) : null
  }, [fcData, lang])

  const intelTileDigestSubs = useMemo(() => {
    if (!main) return null
    const subs = {}
    if (Array.isArray(alerts) && alerts.length > 0) {
      const hi = intelHighAlertCount
      const t0 = String(alerts[0]?.title || '').trim().slice(0, 56)
      const title = t0 || '—'
      subs.alerts =
        hi > 0
          ? strictTParams(tr, lang, 'cmd_intel_digest_alerts_high', {
              hi: String(hi),
              n: String(intelAlertCount),
              title,
            })
          : strictTParams(tr, lang, 'cmd_intel_digest_alerts_open', { n: String(intelAlertCount), title })
    }
    if (intelRiskScore != null && Number.isFinite(Number(intelRiskScore))) {
      const em = kpis?.expenses?.mom_pct
      subs.risk = strictTParams(tr, lang, 'cmd_intel_digest_risk', {
        score: String(Math.round(Number(intelRiskScore))),
        hi: String(intelHighAlertCount),
        exp: em != null && Number.isFinite(Number(em)) ? formatSignedPctForLang(Number(em), 1, lang) : '—',
      })
    }
    if (fcData?.available) {
      const rk = fcData.summary?.risk_level != null ? String(fcData.summary.risk_level) : '—'
      const mom = fcData.summary?.trend_mom_revenue
      subs.scenarios = strictTParams(tr, lang, 'cmd_intel_digest_scenarios', {
        risk: rk,
        mom: mom != null && Number.isFinite(Number(mom)) ? formatSignedPctForLang(Number(mom), 1, lang) : '—',
      })
    } else {
      subs.scenarios = strictT(tr, lang, 'cmd_intel_digest_scenarios_no_fc')
    }
    return subs
  }, [main, alerts, intelAlertCount, intelHighAlertCount, intelRiskScore, kpis, fcData, tr, lang])

  const period = main?.intelligence?.latest_period || main?.periods?.slice(-1)[0]
  const expenseIntel = main?.expense_intelligence

  const primaryResolution =
    main &&
    (selectPrimaryDecision({
      decisions: Array.isArray(decs) ? decs : [],
      impacts,
      kpis,
      cashflow: main?.cashflow || {},
      comparativeIntelligence: main?.comparative_intelligence ?? null,
      expenseIntelligence: expenseIntel ?? null,
      expenseDecisionsV2: main?.expense_decisions_v2 ?? [],
    }) || {
      kind: 'expense',
      expense: {
        decision_id: '_cmd_baseline',
        title: strictT(tr, lang, 'cmd_decision_baseline'),
        rationale: null,
        priority: 'medium',
      },
      score: 0,
    })

  const primaryHeroKey =
    primaryResolution?.kind === 'expense'
      ? `h-ex-${primaryResolution.expense?.decision_id || 'x'}`
      : primaryResolution
        ? `h-cfo-${primaryResolution.decision?.key || primaryResolution.decision?.domain || 'd'}`
        : 'h-none'

  const healthPanelProps = {
    tr,
    lang,
    health,
    status,
    companyName: selectedCompany?.name,
    period,
    loading,
    onRefresh: load,
    periodCount: main?.periods?.length,
    scopeLabel: main?.scope_label,
    healthHeadline: null,
    actionPrefix: null,
    actionLine: null,
    onDrillAnalysis: () => drillAnalysis('overview'),
    hideCompanyIdentity: true,
    bandCompact: true,
  }

  const open = useCallback(
    (panelType, p, x = null) => {
      setPType(panelType)
      setPLoad(p)
      if (panelType === 'profit_bridge_segment' && p?.bridgeKey) setBridgeSelKey(String(p.bridgeKey))
      else setBridgeSelKey(null)
      const chartTypes =
        panelType === 'kpi' ||
        panelType === 'decision' ||
        panelType === 'expense_v2' ||
        panelType === 'causal_item' ||
        panelType === 'branch_compare' ||
        panelType === 'profit_bridge_segment'
      setPXtra({
        ...(x || {}),
        execChartBundle:
          chartTypes && main
            ? {
                kpi_block: main.kpi_block,
                cashflow: main.cashflow,
                comparative_intelligence: main.comparative_intelligence,
              }
            : null,
        drillIntelBundle: {
          narrative: narrative || null,
          kpis,
          primaryResolution,
          expenseIntel,
          decisions: Array.isArray(decs) ? decs : [],
          health,
          realizedCausalItems: main?.realized_causal_items ?? [],
        },
      })
    },
    [main, narrative, kpis, primaryResolution, expenseIntel, decs, health],
  )

  const handleIntelTileToggle = useCallback((id) => {
    setIntelActiveTile((prev) => (prev === id ? null : id))
  }, [])

  const closeIntelExpanded = useCallback(() => setIntelActiveTile(null), [])

  const close = useCallback(() => {
    setPType(null)
    setPLoad(null)
    setPXtra(null)
    setBridgeSelKey(null)
  }, [])

  if (!selectedId) {
    return (
      <div className="cmd-page cmd-page--os cmd-page--cinematic" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', justifyContent: 'center', minHeight: '70vh' }}>
        <div className="cmd-page-constrain" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 16 }}>
          <span style={{ opacity: 0.22, display: 'flex' }} aria-hidden>
            <svg width="56" height="56" viewBox="0 0 24 24" fill="none">
              <path
                d="M5 20V10l4-2v4l3-1.5V20M10 20V9.5l4-2V20M15 11.5L19 10v10"
                stroke="currentColor"
                strokeWidth="1.35"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ color: T.text3 }}
              />
              <path d="M4 20h16" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" style={{ color: T.text3 }} />
            </svg>
          </span>
          <div style={{ fontSize: 15, fontWeight: 600, color: T.text2, textAlign: 'left' }}>{strictT(tr, lang, 'exec_no_company')}</div>
        </div>
      </div>
    )
  }

  if (selectedId && noDataMsg && !main) {
    return (
      <div className="cmd-page cmd-page--os cmd-page--cinematic">
        <div className="cmd-page-constrain">
          <div style={{ padding: '12px 16px', borderRadius: 14, width: '100%', textAlign: 'left',
            background: 'rgba(251,191,36,0.10)', border: '1px solid rgba(251,191,36,0.25)',
            color: T.text2, fontSize: 13, fontWeight: 600 }}>
            {noDataMsg}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="cmd-page cmd-page--os cmd-page--cinematic">
      <style>{`
        @keyframes spin { to { transform:rotate(360deg) } }
        @keyframes slideIn { from { transform:translateX(100%);opacity:0 } to { transform:translateX(0);opacity:1 } }
        @keyframes fadeUp { from { opacity:0;transform:translateY(5px) } to { opacity:1;transform:none } }
      `}</style>

      <div className="cmd-page-constrain">
        <div className="cmd-page-main">
          <div className={main ? `${dashEnterCls} cmd-stack-major`.trim() : 'cmd-stack-major'}>
            <CommandCenterCinematicLayout
              key={primaryHeroKey}
              contextRail={
                <CommandCenterContextRail
                  tr={tr}
                  lang={lang}
                  companyName={selectedCompany?.name}
                  window={win}
                  setWindow={setWin}
                  loading={loading}
                  consolidate={consolidate}
                  setConsolidate={setConsolidate}
                  ps={ps}
                  psUpdate={psUpdate}
                  onScopeApply={load}
                  scopeActiveLabel={psActiveLabel()}
                  allPeriods={main?.all_periods || []}
                  validation={main?.pipeline_validation}
                />
              }
              kpiStrip={
                main ? (
                  <ExecutiveKpiRow
                    kpis={kpis}
                    cashflow={main?.cashflow || {}}
                    main={main}
                    tr={tr}
                    lang={lang}
                    alerts={alerts}
                    onSelect={open}
                    ctxLabel={ctxLabel}
                    hideTitle
                    layout="cinematic"
                  />
                ) : null
              }
              mainCharts={
                main ? (
                  <>
                    <CommandCenterTripleTrendChart
                      kpiBlock={main.kpi_block}
                      tr={tr}
                      lang={lang}
                      cinematic
                    />
                    <div className="cmd-cine-intel-zone">
                      <CommandCenterIntelligenceMosaic
                        activeTile={intelActiveTile}
                        onToggle={handleIntelTileToggle}
                        main={main}
                        fcData={fcData}
                        forecastReady={intelForecastReady}
                        forecastPrimaryMetric={intelForecastPrimaryMetric}
                        alertCount={intelAlertCount}
                        liquidityHint={intelLiquidityHint}
                        liquidityScore={intelLiquidityScore}
                        efficiencyScore={intelEfficiencyScore}
                        efficiencyHint={intelEfficiencyHint}
                        riskScore={intelRiskScore}
                        highAlertCount={intelHighAlertCount}
                        tileDigestSubs={intelTileDigestSubs}
                        tr={tr}
                        lang={lang}
                      />
                      {intelActiveTile ? (
                        <CommandCenterIntelligenceExpanded
                          key={intelActiveTile}
                          tileId={intelActiveTile}
                          onClose={closeIntelExpanded}
                          tr={tr}
                          lang={lang}
                          main={main}
                          intel={intel}
                          alerts={alerts}
                          fcData={fcData}
                          kpis={kpis}
                          decs={decs}
                          primaryResolution={primaryResolution}
                          expenseIntel={expenseIntel}
                          health={health}
                          impacts={impacts}
                          narrative={narrative}
                          bridgeSelKey={bridgeSelKey}
                          onBridgeSegment={(pl) => open('profit_bridge_segment', pl)}
                        />
                      ) : null}
                    </div>
                    <div className="cmd-cine-split-charts">
                      <ExecutiveKpiTrendChart
                        kpiBlock={main.kpi_block}
                        cashflow={main.cashflow}
                        kpiType="net_margin"
                        tr={tr}
                        lang={lang}
                        cinematic
                      />
                      <CommandCenterBranchGroupedChart
                        comparativeIntelligence={main.comparative_intelligence}
                        tr={tr}
                        lang={lang}
                        cinematic
                        onOpenBranches={() => navigate('/branches')}
                      />
                    </div>
                  </>
                ) : null
              }
              rightRail={
                <div className="cmd-cine-rail-stack cmd-cine-rail-console">
                  <div className="cmd-cine-rail-card cmd-cine-rail-card--health" style={{ minWidth: 0 }}>
                    <div className="cmd-cine-rail-section-title">{strictT(tr, lang, 'cmd_rail_section_health')}</div>
                    {main ? (
                      <CommandCenterHealthComposite
                        executiveBand
                        healthPanel={<HealthScorePanel {...healthPanelProps} pairedLayout={false} />}
                        intelligence={intel}
                        tr={tr}
                        lang={lang}
                        onSelectDomain={(panelType, payload) => open(panelType, payload, { causes, decisions: decs })}
                      />
                    ) : null}
                  </div>
                  <div className="cmd-cine-rail-card cmd-cine-rail-card--story" style={{ minWidth: 0 }}>
                    <div className="cmd-cine-rail-section-title">{strictT(tr, lang, 'cmd_rail_section_story')}</div>
                    {main ? (
                      main.structured_profit_story?.what_changed_key ? (
                        <StructuredFinancialLayers data={main} tr={tr} lang={lang} variant="command" />
                      ) : (
                        <div className="cmd-magic-story-empty cmd-cine-rail-empty">
                          <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>
                            {strictT(tr, lang, 'cmd_cc_story_empty')}
                          </p>
                        </div>
                      )
                    ) : null}
                  </div>
                  <div className="cmd-cine-rail-card cmd-cine-rail-card--decision" style={{ minWidth: 0 }}>
                    <div className="cmd-cine-rail-section-title">{strictT(tr, lang, 'cmd_rail_section_decision')}</div>
                    {main && primaryResolution ? (
                      <PrimaryDecisionHero
                        resolution={primaryResolution}
                        impacts={impacts}
                        tr={tr}
                        lang={lang}
                        causes={causes}
                        allDecisions={decs}
                        onOpen={open}
                        realizedCausalItems={main?.realized_causal_items}
                        onOpenFullAnalysis={() => drillAnalysis('overview')}
                      />
                    ) : null}
                  </div>
                </div>
              }
              bridge={null}
              tileStrip={null}
              collapsed={null}
              footerSecondary={
                main ? (
                  <CommandCenterExecutionLayer
                    tr={tr}
                    lang={lang}
                    alerts={alerts}
                    decs={decs}
                    expenseDecisionsV2={main?.expense_decisions_v2}
                    narrative={narrative}
                    primaryResolution={primaryResolution}
                    impacts={impacts}
                    expenseIntel={expenseIntel}
                    kpis={kpis}
                    comparativeIntelligence={main?.comparative_intelligence}
                    fcData={fcData}
                    realizedCausalItems={main?.realized_causal_items}
                    onActivate={(type, payload) => open(type, payload, {})}
                  />
                ) : null
              }
            />
          </div>
        </div>
      </div>

      <AiCfoPanel
        tr={tr}
        lang={lang}
        hasExecutiveData={!!main}
        narrative={narrative}
        kpis={kpis}
        main={main}
        decisions={decs}
        expenseIntel={expenseIntel}
        primaryResolution={primaryResolution}
        health={health}
        alerts={alerts}
        companyName={selectedCompany?.name}
        scopeLabel={main?.scope_label}
        scopeSummary={psActiveLabel()}
      />

      {pType && (
        <ContextPanel
          type={pType}
          payload={pLoad}
          extra={pXtra}
          impacts={impacts}
          tr={tr}
          lang={lang}
          onClose={close}
          onNavigate={() => {
            if (pType === 'branch_compare') {
              navigate('/branches')
            } else {
              const { path, focus } = analysisPathFromPanelType(pType, pLoad)
              navigate(path, { state: { focus } })
            }
            close()
          }}
        />
      )}
    </div>
  )
}

