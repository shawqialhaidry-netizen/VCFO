/**
 * What / Why / Do drill explanation — strict i18n lines from structured builders + final Arabic guard.
 */
import { enforceLanguageFinal } from '../utils/enforceLanguageFinal.js'

function BulletList({ items, textColor, lang }) {
  if (!items?.length) return null
  return (
    <ul style={{ margin: 0, paddingLeft: 16, color: textColor, fontSize: 12, lineHeight: 1.55 }}>
      {items.map((item, i) => (
        <li key={i} style={{ marginBottom: 6 }}>
          <span>{enforceLanguageFinal(item.text, lang)}</span>
        </li>
      ))}
    </ul>
  )
}

/**
 * @param {object} p
 * @param {Array<{ text: string }>} [p.what]
 * @param {Array<{ text: string }>} [p.why]
 * @param {Array<{ text: string }>} [p.do]
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
          <BulletList items={what} textColor={text1} lang={lang} />
        </div>
      ) : null}
      {why.length ? (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 9, fontWeight: 800, color: text3, textTransform: 'uppercase', marginBottom: 6 }}>
            {tr('ai_cfo_section_why')}
          </div>
          <BulletList items={why} textColor={text2} lang={lang} />
        </div>
      ) : null}
      {doLines.length ? (
        <div>
          <div style={{ fontSize: 9, fontWeight: 800, color: text3, textTransform: 'uppercase', marginBottom: 6 }}>
            {tr('ai_cfo_section_do')}
          </div>
          <BulletList items={doLines} textColor={text2} lang={lang} />
        </div>
      ) : null}
    </div>
  )
}
