/**
 * Executive narrative — primary Command Center block; shared with Executive Dashboard.
 */
import { buildExecutiveNarrative } from '../utils/buildExecutiveNarrative.js'
import { strictT as st } from '../utils/strictI18n.js'

const P = {
  surface: 'linear-gradient(165deg, rgba(17,24,39,1) 0%, rgba(15,23,42,1) 100%)',
  border: 'rgba(148,163,184,0.16)',
  glow: '0 0 0 1px rgba(124,92,252,0.2), 0 24px 64px rgba(0,0,0,0.5), 0 0 120px -28px rgba(124,92,252,0.28)',
  accent: '#00d4aa',
  violet: '#a78bfa',
  green: '#34d399',
  red: '#f87171',
  text1: '#f8fafc',
  text2: '#cbd5e1',
  text3: '#64748b',
}

function toneForWhatLine(text) {
  const s = String(text || '')
  if (s.includes('↓')) return P.red
  if (s.includes('↑')) return P.green
  return P.text2
}

export default function ExecutiveNarrativeStrip({
  narrative,
  tr,
  lang = 'en',
  compact = false,
  onOpenFullAnalysis,
}) {
  const n = narrative ?? buildExecutiveNarrative({}, { lang })
  const { whatChanged, why, whatToDo } = n

  const pad = compact ? '10px 12px 12px' : '14px 16px 16px'
  const gap = compact ? 12 : 16
  const titleFs = compact ? 13 : 14
  const lineFs = compact ? 12 : 13
  const secMinW = compact ? 160 : 200
  const emojiFs = compact ? 16 : 18

  const Sec = ({ label, children, labelColor = P.accent }) => (
    <div style={{ flex: 1, minWidth: secMinW }}>
      <div
        style={{
          fontSize: compact ? 8 : 9,
          fontWeight: 800,
          color: labelColor,
          letterSpacing: '.09em',
          textTransform: 'uppercase',
          marginBottom: compact ? 4 : 6,
        }}
      >
        {label}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: compact ? 4 : 6 }}>{children}</div>
    </div>
  )

  const Line = ({ children, color = P.text2 }) => (
    <p style={{ margin: 0, fontSize: lineFs, color, lineHeight: 1.45, fontWeight: 480 }}>{children}</p>
  )

  const whatLines = whatChanged?.lines?.filter(Boolean) || []
  const whyLines = why?.lines?.filter(Boolean) || []
  const doLines = whatToDo?.lines?.filter(Boolean) || []

  return (
    <div
      role={onOpenFullAnalysis ? 'button' : undefined}
      tabIndex={onOpenFullAnalysis ? 0 : undefined}
      onClick={onOpenFullAnalysis || undefined}
      onKeyDown={
        onOpenFullAnalysis
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onOpenFullAnalysis()
              }
            }
          : undefined
      }
      title={onOpenFullAnalysis ? st(tr, lang, 'cmd_drill_narrative_hint') : undefined}
      style={{
        background: P.surface,
        border: `1px solid rgba(167,139,250,0.28)`,
        borderRadius: 14,
        borderLeftWidth: 4,
        borderLeftColor: P.violet,
        padding: pad,
        display: 'flex',
        flexWrap: 'wrap',
        gap,
        alignItems: 'flex-start',
        boxShadow: P.glow,
        cursor: onOpenFullAnalysis ? 'pointer' : undefined,
        outline: 'none',
      }}
    >
      <div style={{ width: '100%' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: compact ? 2 : 4 }}>
          <span style={{ fontSize: emojiFs, lineHeight: 1 }}>🧠</span>
          <div>
            <div style={{ fontSize: titleFs, fontWeight: 800, color: P.text1, letterSpacing: '.03em' }}>
              {st(tr, lang, 'exec_narrative_title')}
            </div>
            <div
              style={{
                fontSize: compact ? 8 : 9,
                color: P.text3,
                marginTop: 2,
                letterSpacing: '.06em',
                textTransform: 'uppercase',
              }}
            >
              {st(tr, lang, 'cmd_exec_narrative_sub')}
            </div>
          </div>
        </div>
      </div>
      <Sec label={st(tr, lang, 'exec_narr_what')} labelColor={P.violet}>
        {whatLines.map((ln, i) => (
          <Line key={i} color={toneForWhatLine(ln)}>
            {ln}
          </Line>
        ))}
      </Sec>
      <Sec label={st(tr, lang, 'exec_narr_why')} labelColor={P.violet}>
        {whyLines.map((ln, i) => (
          <Line key={i}>{ln}</Line>
        ))}
      </Sec>
      <Sec label={st(tr, lang, 'exec_narr_do')}>
        {doLines.map((ln, i) => (
          <div
            key={i}
            style={{
              display: 'flex',
              gap: 8,
              alignItems: 'flex-start',
            }}
          >
            <span
              style={{
                width: compact ? 20 : 22,
                height: compact ? 20 : 22,
                borderRadius: 6,
                background: 'rgba(124,92,252,0.22)',
                color: P.violet,
                fontSize: compact ? 10 : 11,
                fontWeight: 800,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
                border: '1px solid rgba(124,92,252,0.35)',
              }}
            >
              {i + 1}
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <Line>{ln}</Line>
            </div>
          </div>
        ))}
      </Sec>
    </div>
  )
}
