/**
 * Wraps API/backend copy: in Arabic UI, Latin-heavy strings get dim “system” styling + tooltip.
 */
import { dimLatinServerStyle, shouldDimLatinInArabic } from '../utils/serverTextUi.js'
import { strictT } from '../utils/strictI18n.js'
import { enforceLanguageFinal } from '../utils/enforceLanguageFinal.js'

export default function CmdServerText({
  lang,
  tr,
  children,
  as: Tag = 'span',
  style = {},
  title,
  ...rest
}) {
  const raw = children
  const text = raw == null ? '' : String(raw)
  const display = enforceLanguageFinal(text, lang)
  const dim = dimLatinServerStyle(lang, display) || {}
  const tip = shouldDimLatinInArabic(lang, display) ? strictT(tr, lang, 'cmd_source_data_tooltip') : undefined
  return (
    <Tag style={{ ...style, ...dim }} title={title != null && title !== '' ? title : tip || undefined} {...rest}>
      {display}
    </Tag>
  )
}
