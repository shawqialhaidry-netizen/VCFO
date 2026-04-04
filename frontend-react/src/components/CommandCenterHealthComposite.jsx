/**
 * Health score panel + domain signals (+ Phase 3 executive band layout).
 */
import { strictT } from '../utils/strictI18n.js'

const T = {
  card: 'var(--bg-panel)',
  border: 'var(--border)',
  text2: 'var(--text-secondary)',
  text3: 'var(--text-muted)',
  green: 'var(--green)',
  amber: 'var(--amber)',
  red: 'var(--red)',
}

const stC = { good: T.green, warning: T.amber, risk: T.red, neutral: T.text2 }

const dClr = {
  profitability: '#34d399',
  liquidity: '#3b9eff',
  efficiency: '#fbbf24',
}

function scoreFromCategory(cat) {
  if (!cat) return 50
  const s2 = { good: 100, neutral: 60, warning: 35, risk: 10 }
  const vs = Object.values(cat)
    .map((v) => s2[v?.status] || 50)
    .filter((v) => Number.isFinite(v))
  if (!vs.length) return 50
  return Math.round(vs.reduce((a, b) => a + b, 0) / vs.length)
}

function DomainPill({ label, score, color, tr, lang, onClick }) {
  const st = score >= 70 ? 'good' : score >= 45 ? 'warning' : 'risk'
  const sc = stC[st]
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        textAlign: 'left',
        padding: '10px 10px',
        borderRadius: 10,
        border: `1px solid ${T.border}`,
        borderTop: `3px solid ${color}`,
        background: 'rgba(255,255,255,0.04)',
        cursor: 'pointer',
        color: 'inherit',
      }}
    >
      <div style={{ fontSize: 9, fontWeight: 800, color: T.text3, textTransform: 'uppercase', letterSpacing: '.06em' }}>{label}</div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginTop: 6 }}>
        <span style={{ fontSize: 18, fontWeight: 900, fontFamily: 'var(--font-mono)', color: sc }}>{score}</span>
        <span style={{ fontSize: 9, color: T.text2 }}>/100</span>
      </div>
      <div style={{ fontSize: 10, color: T.text2, marginTop: 4 }}>{strictT(tr, lang, `status_${st}_simple`)}</div>
    </button>
  )
}

function DomainChip({ label, score, color, onClick, tr, lang }) {
  const st = score >= 70 ? 'good' : score >= 45 ? 'warning' : 'risk'
  const sc = stC[st]
  return (
    <button
      type="button"
      className="cmd-p3-domain-chip"
      onClick={onClick}
      style={{ borderTop: `2px solid ${color}` }}
    >
      <div className="cmd-p3-domain-chip__k">{label}</div>
      <div className="cmd-p3-domain-chip__sc" style={{ color: sc }}>
        {score}
        <span style={{ fontSize: 10, fontWeight: 700, color: T.text3, marginLeft: 2 }}>/100</span>
      </div>
      <div style={{ fontSize: 9, color: T.text2, fontWeight: 600 }}>{strictT(tr, lang, `status_${st}_simple`)}</div>
    </button>
  )
}

export default function CommandCenterHealthComposite({
  healthPanel,
  intelligence,
  tr,
  lang,
  onSelectDomain,
  executiveBand = false,
}) {
  const ratios = intelligence?.ratios || {}
  const profitability = scoreFromCategory(ratios.profitability)
  const liquidity = scoreFromCategory(ratios.liquidity)
  const efficiency = scoreFromCategory(ratios.efficiency)

  const ratioMap = (key) => ratios[key] || {}

  const ac = intelligence?.anomaly_count
  const anomalies = intelligence?.anomalies
  const count = typeof ac === 'number' ? ac : Array.isArray(anomalies) ? anomalies.length : 0
  const preview =
    Array.isArray(anomalies) && anomalies[0]?.detail ? String(anomalies[0].detail).slice(0, 120) : null

  const anomalyBlock =
    count > 0 ? (
      <div className="cmd-p3-anomaly-slot" role="status">
        <div className="cmd-p3-anomaly-slot__k">{strictT(tr, lang, 'cmd_p3_anomaly_head')}</div>
        <div className="cmd-p3-anomaly-slot__v">
          {strictT(tr, lang, 'intel_anomalies')}: {count}
          {preview ? ` — ${preview}${preview.length >= 120 ? '…' : ''}` : null}
        </div>
      </div>
    ) : null

  if (executiveBand) {
    return (
      <div className="cmd-magic-health-wrap cmd-p3-health-band" style={{ display: 'flex', flexDirection: 'column', gap: 10, minWidth: 0 }}>
        {anomalyBlock}
        {healthPanel}
        {intelligence ? (
          <div className="cmd-p3-domain-row">
            <DomainChip
              tr={tr}
              lang={lang}
              label={strictT(tr, lang, 'domain_profitability_simple')}
              score={profitability}
              color={dClr.profitability}
              onClick={() =>
                onSelectDomain?.('domain', {
                  domain: 'profitability',
                  score: profitability,
                  status: profitability >= 70 ? 'good' : profitability >= 45 ? 'warning' : 'risk',
                  ratios: ratioMap('profitability'),
                })
              }
            />
            <DomainChip
              tr={tr}
              lang={lang}
              label={strictT(tr, lang, 'domain_liquidity_simple')}
              score={liquidity}
              color={dClr.liquidity}
              onClick={() =>
                onSelectDomain?.('domain', {
                  domain: 'liquidity',
                  score: liquidity,
                  status: liquidity >= 70 ? 'good' : liquidity >= 45 ? 'warning' : 'risk',
                  ratios: ratioMap('liquidity'),
                })
              }
            />
            <DomainChip
              tr={tr}
              lang={lang}
              label={strictT(tr, lang, 'domain_efficiency_simple')}
              score={efficiency}
              color={dClr.efficiency}
              onClick={() =>
                onSelectDomain?.('domain', {
                  domain: 'efficiency',
                  score: efficiency,
                  status: efficiency >= 70 ? 'good' : efficiency >= 45 ? 'warning' : 'risk',
                  ratios: ratioMap('efficiency'),
                })
              }
            />
          </div>
        ) : null}
      </div>
    )
  }

  return (
    <div className="cmd-magic-health-wrap" style={{ display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0 }}>
      {healthPanel}
      {anomalyBlock}
      {intelligence ? (
        <div className="cmd-magic-domain-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8 }}>
          <DomainPill
            label={strictT(tr, lang, 'domain_profitability_simple')}
            score={profitability}
            color={dClr.profitability}
            tr={tr}
            lang={lang}
            onClick={() =>
              onSelectDomain?.('domain', {
                domain: 'profitability',
                score: profitability,
                status: profitability >= 70 ? 'good' : profitability >= 45 ? 'warning' : 'risk',
                ratios: ratioMap('profitability'),
              })
            }
          />
          <DomainPill
            label={strictT(tr, lang, 'domain_liquidity_simple')}
            score={liquidity}
            color={dClr.liquidity}
            tr={tr}
            lang={lang}
            onClick={() =>
              onSelectDomain?.('domain', {
                domain: 'liquidity',
                score: liquidity,
                status: liquidity >= 70 ? 'good' : liquidity >= 45 ? 'warning' : 'risk',
                ratios: ratioMap('liquidity'),
              })
            }
          />
          <DomainPill
            label={strictT(tr, lang, 'domain_efficiency_simple')}
            score={efficiency}
            color={dClr.efficiency}
            tr={tr}
            lang={lang}
            onClick={() =>
              onSelectDomain?.('domain', {
                domain: 'efficiency',
                score: efficiency,
                status: efficiency >= 70 ? 'good' : efficiency >= 45 ? 'warning' : 'risk',
                ratios: ratioMap('efficiency'),
              })
            }
          />
        </div>
      ) : null}
    </div>
  )
}
