/**
 * SessionExpiredBanner.jsx — FIX-FE1
 *
 * Shown when a 401 is detected (token expired / invalidated).
 * Replaces silent API failures with a clear user prompt.
 *
 * Props:
 *   onLogin: () => void — called when user clicks "Log In"
 *                         (should clear auth and navigate to login)
 */
export default function SessionExpiredBanner({ onLogin }) {
  return (
    <div style={{
      position:       'fixed',
      top:            0, left: 0, right: 0,
      zIndex:         9999,
      background:     '#140500',
      borderBottom:   '2px solid #f87171',
      padding:        '12px 24px',
      display:        'flex',
      alignItems:     'center',
      justifyContent: 'space-between',
      gap:            16,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ fontSize: 16 }}>⚠</span>
        <span style={{ fontSize: 13, color: '#fca5a5', fontWeight: 600 }}>
          Your session has expired. Please log in again.
        </span>
      </div>
      <button
        onClick={onLogin}
        style={{
          background:   '#f87171',
          color:        '#fff',
          border:       'none',
          borderRadius: 8,
          padding:      '6px 18px',
          fontSize:     12,
          fontWeight:   700,
          cursor:       'pointer',
          flexShrink:   0,
        }}
      >
        Log In
      </button>
    </div>
  )
}
