import { useState, useRef, useCallback } from 'react'

/**
 * Hover layer for executive “intelligence” copy (no new data; tip is passed in).
 */
export function IntelHoverTip({ children, tip, disabled = false, maxWidth = 300 }) {
  const [open, setOpen] = useState(false)
  const leaveTimer = useRef(null)

  const onEnter = useCallback(() => {
    if (disabled || !tip) return
    if (leaveTimer.current) clearTimeout(leaveTimer.current)
    setOpen(true)
  }, [disabled, tip])

  const onLeave = useCallback(() => {
    leaveTimer.current = setTimeout(() => setOpen(false), 120)
  }, [])

  return (
    <div
      style={{ position: 'relative', width: '100%', minWidth: 0 }}
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
      onFocus={onEnter}
      onBlur={onLeave}
    >
      {children}
      {open && tip ? (
        <div
          role="tooltip"
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            top: '100%',
            zIndex: 50,
            marginTop: 8,
            maxWidth,
            padding: '10px 12px',
            borderRadius: 10,
            background: 'linear-gradient(165deg, rgba(15,23,42,0.98) 0%, rgba(17,24,39,0.99) 100%)',
            border: '1px solid rgba(0,212,170,0.22)',
            boxShadow: '0 12px 40px rgba(0,0,0,0.55), 0 0 0 1px rgba(124,92,252,0.12)',
            fontSize: 11,
            lineHeight: 1.45,
            color: '#94a3b8',
            pointerEvents: 'none',
            animation: 'cmdTipIn 0.18s ease-out',
          }}
        >
          {tip}
        </div>
      ) : null}
    </div>
  )
}
