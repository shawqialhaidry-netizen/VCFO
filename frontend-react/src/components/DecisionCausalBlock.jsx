/**
 * Renders decision.causal_realized as change → cause → action (canonical order).
 * Use everywhere a CFO decision body is shown; do not substitute generic narrative when cr exists.
 */
import CmdServerText from './CmdServerText.jsx'
import { causalTriple, hasAnyCausal } from '../utils/decisionCausal.js'

export default function DecisionCausalBlock({
  causal_realized: cr,
  impact,
  hideChange = false,
  lang,
  tr,
  changeProps = {},
  causeProps = {},
  actionProps = {},
  impactProps = {},
  wrapperStyle = {},
}) {
  if (!hasAnyCausal(cr)) return null
  const { change, cause, action } = causalTriple(cr)
  const impactStr = impact != null && String(impact).trim() ? String(impact).trim() : ''
  return (
    <div style={wrapperStyle}>
      {change && !hideChange ? (
        <p style={{ margin: '0 0 6px', ...changeProps }}>
          <CmdServerText lang={lang} tr={tr} style={{ color: 'inherit' }}>
            {change}
          </CmdServerText>
        </p>
      ) : null}
      {cause ? (
        <p style={{ margin: '0 0 6px', ...causeProps }}>
          <CmdServerText lang={lang} tr={tr} style={{ color: 'inherit' }}>
            {cause}
          </CmdServerText>
        </p>
      ) : null}
      {action ? (
        <p style={{ margin: impactStr ? '0 0 6px' : 0, ...actionProps }}>
          <CmdServerText lang={lang} tr={tr} style={{ color: 'inherit' }}>
            {action}
          </CmdServerText>
        </p>
      ) : null}
      {impactStr ? (
        <p style={{ margin: 0, ...impactProps }}>
          <CmdServerText lang={lang} tr={tr} style={{ color: 'inherit' }}>
            {impactStr}
          </CmdServerText>
        </p>
      ) : null}
    </div>
  )
}
