/**
 * What / Why / Do drill explanation — labels from i18n; body lines use CmdServerText when server-sourced.
 */
import CmdServerText from './CmdServerText.jsx'

function BulletList({ items, lang, tr, textColor }) {
  if (!items?.length) return null
  return (
    <ul style={{ margin: 0, paddingLeft: 16, color: textColor, fontSize: 12, lineHeight: 1.55 }}>
      {items.map((item, i) => (
        <li key={i} style={{ marginBottom: 6 }}>
          {item.serverText ? (
            <CmdServerText lang={lang} tr={tr} as="span">
              {item.text}
            </CmdServerText>
          ) : (
            item.text
          )}
        </li>
      ))}
    </ul>
  )
}

/**
 * @param {object} p
 * @param {Array<{ text: string, serverText?: boolean }>} [p.what]
 * @param {Array<{ text: string, serverText?: boolean }>} [p.why]
 * @param {Array<{ text: string, serverText?: boolean }>} [p.do]
 * @param {(k: string, params?: object) => string} p.tr
 * @param {string} p.lang
 * @param {{ card?: string, border?: string, text1?: string, text2?: string, text3?: string, accent?: string }} [p.theme]
 */
export default function DrillIntelligenceBlock({ what = [], why = [], do: doLines = [], tr, lang, theme }) {
  const th = theme || {}
  const card = th.card ?? 'var(--bg-panel)'
  const border = th.border ?? 'var(--border)'
  const text1 = th.text1 ?? 'var(--text-primary)'
  const text2 = th.text2 ?? 'var(--text-secondary)'
  const text3 = th.text3 ?? 'var(--text-muted)'
  const accent = th.accent ?? 'var(--accent)'

  if (!what.length && !why.length && !doLines.length) return null

  return (
    <div
      style={{
        marginBottom: 18,
        padding: '14px 16px',
        borderRadius: 12,
        border: `1px solid ${border}`,
        background: card,
      }}
    >
      <div
        style={{
          fontSize: 10,
          fontWeight: 800,
          letterSpacing: '.08em',
          textTransform: 'uppercase',
          color: accent,
          marginBottom: 12,
        }}
      >
        {tr('drill_intel_title')}
      </div>
      {what.length ? (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 9, fontWeight: 800, color: text3, textTransform: 'uppercase', marginBottom: 6 }}>
            {tr('ai_cfo_section_what')}
          </div>
          <BulletList items={what} lang={lang} tr={tr} textColor={text1} />
        </div>
      ) : null}
      {why.length ? (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 9, fontWeight: 800, color: text3, textTransform: 'uppercase', marginBottom: 6 }}>
            {tr('ai_cfo_section_why')}
          </div>
          <BulletList items={why} lang={lang} tr={tr} textColor={text2} />
        </div>
      ) : null}
      {doLines.length ? (
        <div>
          <div style={{ fontSize: 9, fontWeight: 800, color: text3, textTransform: 'uppercase', marginBottom: 6 }}>
            {tr('ai_cfo_section_do')}
          </div>
          <BulletList items={doLines} lang={lang} tr={tr} textColor={text2} />
        </div>
      ) : null}
    </div>
  )
}
