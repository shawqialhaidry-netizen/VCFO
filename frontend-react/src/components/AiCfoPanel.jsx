/**
 * AI CFO — context-aware Q&A from executive payload (no new API).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import '../styles/aiCfoPanel.css'
import { buildAiCfoReply } from '../utils/buildAiCfoReply.js'

function AssistantBody({ what, why, doLines, actions, onDrill, followUp, onFollowUp, tr }) {
  return (
    <div className="ai-cfo-msg__bubble">
      {what?.length ? (
        <div className="ai-cfo-block">
          <div className="ai-cfo-block__label">{tr('ai_cfo_section_what')}</div>
          <ul className="ai-cfo-block__list">
            {what.map((line, i) => (
              <li key={`w-${i}`}>{line}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {why?.length ? (
        <div className="ai-cfo-block">
          <div className="ai-cfo-block__label">{tr('ai_cfo_section_why')}</div>
          <ul className="ai-cfo-block__list">
            {why.map((line, i) => (
              <li key={`y-${i}`}>{line}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {doLines?.length ? (
        <div className="ai-cfo-block">
          <div className="ai-cfo-block__label">{tr('ai_cfo_section_do')}</div>
          <ul className="ai-cfo-block__list">
            {doLines.map((line, i) => (
              <li key={`d-${i}`}>{line}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {actions?.length ? (
        <div className="ai-cfo-actions" role="group" aria-label={tr('ai_cfo_actions_aria')}>
          {actions.map((a) => (
            <button
              key={`${a.path}-${a.focus ?? ''}`}
              type="button"
              className="ai-cfo-action-chip"
              onClick={() => onDrill?.(a.path, a.focus)}
            >
              {tr(a.labelKey)}
            </button>
          ))}
        </div>
      ) : null}
      {followUp ? (
        <div className="ai-cfo-follow">
          <button type="button" className="ai-cfo-follow__chip" onClick={() => onFollowUp?.()}>
            {followUp}
          </button>
        </div>
      ) : null}
    </div>
  )
}

/**
 * @param {object} p
 * @param {(k: string, params?: object) => string} p.tr
 * @param {boolean} p.hasExecutiveData
 * @param {object} [p.narrative]
 * @param {object} [p.kpis]
 * @param {object} [p.main]
 * @param {unknown[]} [p.decisions]
 * @param {object} [p.expenseIntel]
 * @param {object} [p.primaryResolution]
 * @param {number | null} [p.health]
 * @param {unknown[]} [p.alerts]
 * @param {string} [p.companyName]
 * @param {string} [p.scopeLabel]
 * @param {string} [p.scopeSummary]
 */
export default function AiCfoPanel({
  tr,
  hasExecutiveData,
  narrative,
  kpis,
  main,
  decisions,
  expenseIntel,
  primaryResolution,
  health,
  alerts,
  companyName,
  scopeLabel,
  scopeSummary,
}) {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState([])
  const chatEndRef = useRef(null)
  const chatRef = useRef(null)

  const replyCtx = useMemo(
    () => ({
      tr,
      narrative,
      kpis: kpis || {},
      main: main || {},
      decisions: decisions || [],
      expenseIntel,
      primaryResolution,
      health: health ?? null,
      alerts: alerts || [],
      companyName: companyName || '',
      scopeLabel: scopeLabel || '',
      scopeSummary: scopeSummary || '',
    }),
    [
      tr,
      narrative,
      kpis,
      main,
      decisions,
      expenseIntel,
      primaryResolution,
      health,
      alerts,
      companyName,
      scopeLabel,
      scopeSummary,
    ],
  )

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, open])

  const runQuery = useCallback(
    (rawQuestion) => {
      const q = String(rawQuestion || '').trim()
      if (!q) return

      setMessages((prev) => [...prev, { id: `u-${Date.now()}`, role: 'user', text: q }])

      if (!hasExecutiveData) {
        setMessages((prev) => [
          ...prev,
          {
            id: `a-${Date.now()}`,
            role: 'assistant',
            what: [tr('ai_cfo_need_data')],
            why: [],
            do: [],
            followUp: null,
            followUpFill: null,
            actions: [],
          },
        ])
        return
      }

      const reply = buildAiCfoReply(q, replyCtx)

      setMessages((prev) => [
        ...prev,
        {
          id: `a-${Date.now()}`,
          role: 'assistant',
          what: reply.what,
          why: reply.why,
          do: reply.do,
          followUp: reply.followUp,
          followUpFill: reply.followUpFill,
          actions: reply.actions || [],
        },
      ])
    },
    [hasExecutiveData, tr, replyCtx],
  )

  const drillNavigate = useCallback(
    (path, focus) => {
      if (!path) return
      if (focus) navigate(path, { state: { focus } })
      else navigate(path)
      setOpen(false)
    },
    [navigate],
  )

  const send = useCallback(() => {
    const q = input.trim()
    if (!q) return
    setInput('')
    runQuery(q)
  }, [input, runQuery])

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  const starterChips = [
    { key: 'ai_cfo_chip_profit_why' },
    { key: 'ai_cfo_chip_what_now' },
    { key: 'ai_cfo_chip_cash' },
  ]

  return (
    <>
      {!open ? (
        <button type="button" className="ai-cfo-fab" onClick={() => setOpen(true)} aria-expanded={false}>
          {tr('ai_cfo_toggle_open')}
        </button>
      ) : (
        <div className="ai-cfo-panel" role="dialog" aria-label={tr('ai_cfo_title')}>
          <div className="ai-cfo-panel__header">
            <div className="ai-cfo-panel__title">
              <span className="ai-cfo-panel__title-text">{tr('ai_cfo_title')}</span>
              <span className="ai-cfo-panel__status">
                <span className="ai-cfo-panel__status-dot" aria-hidden />
                {tr('ai_cfo_online')}
              </span>
            </div>
            <button
              type="button"
              className="ai-cfo-panel__close"
              onClick={() => setOpen(false)}
              aria-label={tr('ai_cfo_toggle_close')}
            >
              ×
            </button>
          </div>
          <div className="ai-cfo-panel__chat" ref={chatRef} dir="ltr">
            {messages.length === 0 ? (
              <div className="ai-cfo-panel__empty">{tr('ai_cfo_empty')}</div>
            ) : null}
            {messages.map((m) =>
              m.role === 'user' ? (
                <div key={m.id} className="ai-cfo-msg ai-cfo-msg--user">
                  <div className="ai-cfo-msg__bubble">{m.text}</div>
                </div>
              ) : (
                <div key={m.id} className="ai-cfo-msg ai-cfo-msg--assistant">
                  <AssistantBody
                    what={m.what}
                    why={m.why}
                    doLines={m.do}
                    actions={m.actions}
                    onDrill={drillNavigate}
                    followUp={m.followUp}
                    onFollowUp={
                      m.followUpFill ? () => runQuery(m.followUpFill) : undefined
                    }
                    tr={tr}
                  />
                </div>
              ),
            )}
            <div ref={chatEndRef} />
          </div>
          <div className="ai-cfo-panel__suggestions" role="toolbar" aria-label={tr('ai_cfo_suggestions_aria')}>
            {starterChips.map((c) => (
              <button
                key={c.key}
                type="button"
                className="ai-cfo-suggest-chip"
                onClick={() => runQuery(tr(c.key))}
              >
                {tr(c.key)}
              </button>
            ))}
          </div>
          <div className="ai-cfo-panel__input-row">
            <input
              type="text"
              className="ai-cfo-panel__input"
              placeholder={tr('ai_cfo_placeholder')}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              aria-label={tr('ai_cfo_placeholder')}
            />
            <button
              type="button"
              className="ai-cfo-panel__send"
              onClick={send}
              disabled={!input.trim()}
              aria-label={tr('ai_cfo_send_aria')}
            >
              {tr('ai_cfo_send')}
            </button>
          </div>
        </div>
      )}
    </>
  )
}
