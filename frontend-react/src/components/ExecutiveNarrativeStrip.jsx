/**
 * Executive narrative — primary Command Center block; shared with Executive Dashboard.
 */
import '../styles/commandCenterStructure.css'
import { buildExecutiveNarrative } from '../utils/buildExecutiveNarrative.js'
import { strictT as st } from '../utils/strictI18n.js'
import { CLAMP_FADE_MASK_SHORT } from '../utils/serverTextUi.js'
import CmdServerText from './CmdServerText.jsx'

const P = {
  surface: 'linear-gradient(165deg, rgba(17,24,39,1) 0%, rgba(15,23,42,1) 100%)',
  border: 'rgba(148,163,184,0.14)',
  cardShadow: '0 4px 24px rgba(0,0,0,0.22)',
  text1: '#ffffff',
  text2: '#d1dae6',
  text3: '#9ca8b8',
}

export default function ExecutiveNarrativeStrip({
  narrative,
  tr,
  lang = 'en',
  compact = false,
  onOpenFullAnalysis,
}) {
  const n = narrative ?? buildExecutiveNarrative({}, tr ? { lang, t: tr } : { lang })
  const { whatChanged, why, whatToDo } = n

  const pad = compact ? '14px 16px 16px' : '16px 18px 18px'
  const gap = 16
  const lineFs = compact ? 13 : 14
  const secMinW = compact ? 160 : 220
  const emojiFs = compact ? 16 : 18

  const Sec = ({ label, children, labelColor = P.text1, step }) => (
    <div style={{ flex: 1, minWidth: secMinW }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: compact ? 8 : 10 }}>
        {step != null ? (
          <span className="cmd-exec-sec-step" aria-hidden>
            {step}
          </span>
        ) : null}
        <div
          className={`cmd-exec-sec-label ${compact ? 'cmd-exec-sec-label--compact' : ''}`.trim()}
          style={{
            fontSize: compact ? 'var(--cmd-fs-section-tight)' : 'var(--cmd-fs-section)',
            color: labelColor,
            marginBottom: 0,
          }}
        >
          {label}
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>{children}</div>
    </div>
  )

  const Line = ({ children }) => (
    <p
      className="cmd-prose"
      style={{
        margin: 0,
        fontSize: lineFs,
        color: P.text2,
        fontWeight: 500,
        ...CLAMP_FADE_MASK_SHORT,
      }}
    >
      <CmdServerText lang={lang} tr={tr} as="span" style={{ color: 'inherit' }}>
        {children}
      </CmdServerText>
    </p>
  )

  const whatLines = whatChanged?.lines?.filter(Boolean) || []
  const whyLines = why?.lines?.filter(Boolean) || []
  const doLines = whatToDo?.lines?.filter(Boolean) || []

  return (
    <div
      className="cmd-typography-scope"
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
        border: `1px solid ${P.border}`,
        borderRadius: 14,
        padding: pad,
        display: 'flex',
        flexWrap: 'wrap',
        gap,
        alignItems: 'flex-start',
        textAlign: 'left',
        boxShadow: P.cardShadow,
        cursor: onOpenFullAnalysis ? 'pointer' : undefined,
        outline: 'none',
      }}
    >
      <div style={{ width: '100%' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: compact ? 8 : 12 }}>
          <span style={{ fontSize: emojiFs, lineHeight: 1 }}>🧠</span>
          <div>
            <div className={`cmd-card-title ${compact ? 'cmd-exec-strip-title--compact' : ''}`.trim()}>
              {st(tr, lang, 'exec_narrative_title')}
            </div>
            <div className="cmd-muted-foreign" style={{ marginTop: 4 }}>
              {st(tr, lang, 'cmd_exec_narrative_sub')}
            </div>
          </div>
        </div>
      </div>
      <Sec label={st(tr, lang, 'exec_narr_what')} step={1}>
        {whatLines.map((ln, i) => (
          <Line key={i}>{ln}</Line>
        ))}
      </Sec>
      <Sec label={st(tr, lang, 'exec_narr_why')} step={2}>
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
                background: 'rgba(255,255,255,0.06)',
                color: P.text2,
                fontSize: compact ? 10 : 11,
                fontWeight: 800,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
                border: `1px solid ${P.border}`,
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
