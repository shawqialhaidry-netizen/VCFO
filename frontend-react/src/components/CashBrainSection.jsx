/**
 * Cash Brain — compact 3-card row (executive scope only).
 */
import { formatCompact } from '../utils/numberFormat.js'

const P = {
  surface: 'linear-gradient(165deg, rgba(17,24,39,0.98) 0%, rgba(15,23,42,0.99) 100%)',
  border: 'rgba(148,163,184,0.14)',
  glow: '0 0 0 1px rgba(0,212,170,0.08), 0 12px 40px rgba(0,0,0,0.42), 0 0 100px -24px rgba(0,212,170,0.08)',
  accent: '#00d4aa',
  green: '#34d399',
  red: '#f87171',
  amber: '#fbbf24',
  text1: '#f8fafc',
  text2: '#94a3b8',
  text3: '#64748b',
}

function barColor(kind, tier) {
  if (kind === 'survival') {
    if (tier === 'critical') return P.red
    if (tier === 'watch') return P.amber
    if (tier === 'comfortable') return P.green
    return P.accent
  }
  if (tier === 'high') return P.red
  if (tier === 'moderate') return P.amber
  if (tier === 'low') return P.green
  return P.accent
}

function CashMiniCard({ label, kind, tier, meaningful, insufficientLabel, children }) {
  const bar = barColor(kind, tier)
  return (
    <div
      style={{
        flex: '1 1 200px',
        minWidth: 188,
        background: 'rgba(255,255,255,0.03)',
        border: `1px solid ${P.border}`,
        borderRadius: 12,
        padding: '14px 16px',
        borderTop: `3px solid ${meaningful ? bar : P.text3}`,
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
        {label}
      </div>
      {!meaningful ? (
        <div style={{ fontSize: 12, fontWeight: 600, color: P.text3, lineHeight: 1.45 }}>{insufficientLabel}</div>
      ) : (
        children
      )}
    </div>
  )
}

export default function CashBrainSection({ snapshot }) {
  if (!snapshot) return null

  const { pressure, liquidity, survival, cardLabels, insufficientLabel, sectionTitle, sectionSub } = snapshot

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
          {sectionTitle}
        </div>
        <div style={{ fontSize: 10, color: P.text3, marginTop: 5, lineHeight: 1.45 }}>{sectionSub}</div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
        <CashMiniCard
          label={cardLabels.pressure}
          kind="pressure"
          tier={pressure.tier}
          meaningful={pressure.meaningful}
          insufficientLabel={insufficientLabel}
        >
          <>
            <div style={{ fontSize: 13, fontWeight: 650, color: P.text1, lineHeight: 1.45, marginBottom: 8 }}>
              {pressure.headline}
            </div>
            {(pressure.bullets || []).map((line, i) => (
              <div
                key={i}
                style={{
                  fontSize: 12,
                  color: P.text2,
                  lineHeight: 1.5,
                  marginTop: i ? 6 : 0,
                  textAlign: 'start',
                }}
              >
                {line}
              </div>
            ))}
          </>
        </CashMiniCard>

        <CashMiniCard
          label={cardLabels.liquidity}
          kind="liquidity"
          tier={liquidity.tier}
          meaningful={liquidity.meaningful}
          insufficientLabel={insufficientLabel}
        >
          <>
            <div style={{ fontSize: 13, fontWeight: 650, color: P.text1, lineHeight: 1.45, marginBottom: 8 }}>
              {liquidity.headline}
            </div>
            {(liquidity.bullets || []).map((line, i) => (
              <div
                key={i}
                style={{
                  fontSize: 12,
                  color: P.text2,
                  lineHeight: 1.5,
                  marginTop: i ? 6 : 0,
                  direction: 'ltr',
                  textAlign: 'start',
                }}
              >
                {line}
              </div>
            ))}
          </>
        </CashMiniCard>

        <CashMiniCard
          label={cardLabels.survival}
          kind="survival"
          tier={survival.tier}
          meaningful={survival.meaningful}
          insufficientLabel={insufficientLabel}
        >
          <>
            <div style={{ fontSize: 13, fontWeight: 650, color: P.text1, lineHeight: 1.45, marginBottom: 8 }}>
              {survival.headline}
            </div>
            {survival.copy ? (
              <div
                style={{
                  fontSize: 12,
                  color: P.text2,
                  lineHeight: 1.5,
                  marginBottom: 0,
                }}
              >
                {survival.copy}
              </div>
            ) : null}
            {(() => {
              const parts = []
              if (
                survival.months != null &&
                survival.months > 0 &&
                !String(survival.copy || '').trim()
              )
                parts.push(`${survival.months.toFixed(1)} mo`)
              if (survival.burn != null && survival.burn > 0) parts.push(`burn ${formatCompact(survival.burn)}`)
              if (survival.cash != null) parts.push(`cash ${formatCompact(survival.cash)}`)
              if (!parts.length) return null
              return (
                <div
                  style={{
                    fontSize: 11,
                    fontFamily: 'monospace',
                    color: P.text3,
                    direction: 'ltr',
                    marginTop: 8,
                  }}
                >
                  {parts.join(' · ')}
                </div>
              )
            })()}
          </>
        </CashMiniCard>
      </div>
    </div>
  )
}
