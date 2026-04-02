/**
 * Executive narrative — primary Command Center block; shared with Executive Dashboard.
 */
import { buildExecutiveNarrative } from '../utils/buildExecutiveNarrative.js'
const P = {
  surface: 'linear-gradient(165deg, rgba(17,24,39,1) 0%, rgba(15,23,42,1) 100%)',
  border: 'rgba(148,163,184,0.16)',
  glow: '0 0 0 1px rgba(124,92,252,0.18), 0 20px 56px rgba(0,0,0,0.5), 0 0 120px -28px rgba(124,92,252,0.22)',
  accent: '#00d4aa',
  violet: '#a78bfa',
  text1: '#f8fafc',
  text2: '#cbd5e1',
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

export default function ExecutiveNarrativeStrip({ narrative, tr, lang = 'en' }) {
  const n = narrative ?? buildExecutiveNarrative({}, { lang })
  const { whatChanged, why, whatToDo } = n

  const Sec = ({ label, children }) => (
    <div style={{ flex: 1, minWidth: 220 }}>
      <div
        style={{
          fontSize: 10,
          fontWeight: 800,
          color: P.accent,
          letterSpacing: '.1em',
          textTransform: 'uppercase',
          marginBottom: 12,
        }}
      >
        {label}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>{children}</div>
    </div>
  )

  const Line = ({ children }) => (
    <p style={{ margin: 0, fontSize: 14, color: P.text2, lineHeight: 1.6, fontWeight: 480 }}>{children}</p>
  )

  const whatLines = whatChanged?.lines?.filter(Boolean) || []
  const whyLines = why?.lines?.filter(Boolean) || []
  const doLines = whatToDo?.lines?.filter(Boolean) || []

  return (
    <div
      style={{
        background: P.surface,
        border: `1px solid ${P.border}`,
        borderRadius: 18,
        borderLeftWidth: 5,
        borderLeftColor: P.violet,
        padding: '26px 28px 28px',
        display: 'flex',
        flexWrap: 'wrap',
        gap: 28,
        alignItems: 'flex-start',
        boxShadow: P.glow,
      }}
    >
      <div style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
        <span style={{ fontSize: 22, lineHeight: 1 }}>🧠</span>
        <span style={{ fontSize: 15, fontWeight: 800, color: P.text1, letterSpacing: '.03em' }}>
          {Tx(tr, 'exec_narrative_title', 'Executive narrative')}
        </span>
      </div>
      <Sec label={Tx(tr, 'exec_narr_what', 'What changed')}>
        {whatLines.map((ln, i) => (
          <Line key={i}>{ln}</Line>
        ))}
      </Sec>
      <Sec label={Tx(tr, 'exec_narr_why', 'Why')}>
        {whyLines.map((ln, i) => (
          <Line key={i}>{ln}</Line>
        ))}
      </Sec>
      <Sec label={Tx(tr, 'exec_narr_do', 'What to do')}>
        {doLines.map((ln, i) => (
          <Line key={i}>{ln}</Line>
        ))}
      </Sec>
    </div>
  )
}
