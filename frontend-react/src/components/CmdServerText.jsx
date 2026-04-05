/**
 * Wraps API/backend copy. Arabic UI: Latin-only prose is replaced with i18n (no English sentences on screen).
 * Mixed Arabic + Latin: Latin tokens get dir="ltr" spans when shown.
 */
import { dimLatinServerStyle, shouldDimLatinInArabic } from '../utils/serverTextUi.js'
import { strictT } from '../utils/strictI18n.js'
import { enforceLanguageFinal } from '../utils/enforceLanguageFinal.js'
import { isArabicUiLang, shouldSuppressLatinProseForArabic } from '../utils/arabicBackendCopy.js'

const LATIN_TOKEN = /([A-Za-z]+(?:[-'][A-Za-z]+)*)/g

/** Isolate ASCII word runs inside Arabic paragraphs for correct bidi + wrapping. */
function embedLatinRunsForArabic(text) {
  if (typeof text !== 'string' || !text) return text
  const parts = []
  let last = 0
  let k = 0
  LATIN_TOKEN.lastIndex = 0
  let m
  while ((m = LATIN_TOKEN.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index))
    const w = m[0]
    if (w.length >= 2) {
      parts.push(
        <span key={`ltr-${m.index}-${k++}`} dir="ltr" className="cmd-server-ltr-token">
          {w}
        </span>
      )
    } else parts.push(w)
    last = LATIN_TOKEN.lastIndex
  }
  if (last < text.length) parts.push(text.slice(last))
  return parts.length > 1 ? parts : text
}

export default function CmdServerText({
  lang,
  tr,
  children,
  as: Tag = 'span',
  style = {},
  title,
  /** Arabic UI: wrap Latin letter runs when text is shown (mixed copy). */
  bidiLatin = true,
  /** Arabic UI: replace Latin-only prose with localized placeholder. */
  hideLatinProseInArabic = true,
  /** Force-show raw text in Arabic UI (rare). */
  allowLatinInArabic = false,
  ...rest
}) {
  const raw = children
  const text = raw == null ? '' : String(raw)
  const display = enforceLanguageFinal(text, lang)
  const tip = shouldDimLatinInArabic(lang, display) ? strictT(tr, lang, 'cmd_source_data_tooltip') : undefined

  const suppressed =
    hideLatinProseInArabic &&
    !allowLatinInArabic &&
    isArabicUiLang(lang) &&
    shouldSuppressLatinProseForArabic(display)

  const visible = suppressed ? strictT(tr, lang, 'cmd_ar_backend_insight_placeholder') : display
  const dim = suppressed ? {} : dimLatinServerStyle(lang, display) || {}

  const titleFinal =
    title != null && title !== '' ? title : suppressed ? undefined : tip || undefined

  const inner =
    !suppressed && bidiLatin && isArabicUiLang(lang) && typeof visible === 'string'
      ? embedLatinRunsForArabic(visible)
      : visible

  return (
    <Tag style={{ ...style, ...dim }} title={titleFinal} {...rest}>
      {inner}
    </Tag>
  )
}
