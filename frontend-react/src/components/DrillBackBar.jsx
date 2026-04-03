/**
 * DrillBackBar — return to Command Center from detail-only routes (analysis, branches, …).
 */
import { useNavigate } from 'react-router-dom'
import { useLang } from '../context/LangContext.jsx'
import { strictT } from '../utils/strictI18n.js'

export default function DrillBackBar({ detailLabel }) {
  const navigate = useNavigate()
  const { tr, lang } = useLang()
  const back = strictT(tr, lang, 'nav_back_command_center')
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        flexWrap: 'wrap',
        marginBottom: 14,
        paddingBottom: 12,
        borderBottom: '1px solid var(--border)',
      }}
    >
      <button
        type="button"
        onClick={() => navigate('/')}
        style={{
          padding: '8px 14px',
          borderRadius: 9,
          border: '1px solid var(--border-accent)',
          background: 'rgba(0,212,170,0.08)',
          color: 'var(--accent)',
          fontSize: 12,
          fontWeight: 700,
          cursor: 'pointer',
        }}
      >
        {back}
      </button>
      {detailLabel ? (
        <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600 }}>{detailLabel}</span>
      ) : null}
    </div>
  )
}
