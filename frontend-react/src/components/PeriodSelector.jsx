/**
 * PeriodSelector — Phase 7.6
 * [ 3M ] [ 6M ] [ 12M ] [ YTD ] [ ALL ]
 * Reads/sets window state from parent via props.
 */
import { useLang } from '../context/LangContext.jsx'

const WINDOWS = [
  { key: '3M',  labelKey: 'window_3m'  },
  { key: '6M',  labelKey: 'window_6m'  },
  { key: '12M', labelKey: 'window_12m' },
  { key: 'YTD', labelKey: 'window_ytd' },
  { key: 'ALL', labelKey: 'window_all' },
]

export default function PeriodSelector({ window, setWindow, disabled = false, style = {} }) {
  const { tr } = useLang()

  return (
    <div style={{ display: 'flex', gap: 4, alignItems: 'center', ...style }}>
      {WINDOWS.map(w => {
        const active = window === w.key
        return (
          <button
            key={w.key}
            disabled={disabled}
            onClick={() => setWindow(w.key)}
            style={{
              padding:        '5px 12px',
              borderRadius:   8,
              border:         active ? '1px solid var(--accent)' : '1px solid var(--border)',
              background:     active ? 'var(--accent-dim)' : 'transparent',
              color:          active ? 'var(--accent)' : 'var(--text-muted)',
              fontSize:       12,
              fontWeight:     active ? 700 : 500,
              fontFamily:     'var(--font-display)',
              cursor:         disabled ? 'not-allowed' : 'pointer',
              transition:     'all var(--t)',
              letterSpacing:  '0.03em',
              opacity:        disabled ? 0.5 : 1,
              boxShadow:      active ? '0 0 12px var(--accent-glow)' : 'none',
            }}
          >
            {tr(w.labelKey)}
          </button>
        )
      })}
    </div>
  )
}
