/**
 * UniversalScopeSelector — Phase 22 period scope (extracted from Dashboard)
 */
import { strictT } from '../utils/strictI18n.js'
const BG = {
  panel: '#111827',
  border: '#1F2937',
}
const C = {
  accent: '#00d4aa',
  text2: '#aab4c3',
}
const INPUT_DARK = {
  background: '#111827',
  color: '#ffffff',
  border: '1px solid #1F2937',
  borderRadius: 8,
  padding: '7px 10px',
  fontSize: 12,
  outline: 'none',
  fontFamily: 'var(--font-mono)',
  direction: 'ltr',
  width: '100%',
  WebkitAppearance: 'none',
  MozAppearance: 'none',
  appearance: 'none',
}
const SELECT_DARK = {
  ...INPUT_DARK,
  cursor: 'pointer',
  fontFamily: 'var(--font-display)',
  width: undefined,
  paddingRight: 28,
  backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%23374560'/%3E%3C/svg%3E")`,
  backgroundRepeat: 'no-repeat',
  backgroundPosition: 'right 10px center',
}

export default function UniversalScopeSelector({ tr, lang = 'en', ps, psUpdate, onApply, allPeriods, activeLabel }) {
  const years = [...new Set((allPeriods || []).map(p => p.slice(0, 4)))].sort((a, b) => b - a)
  const months = allPeriods || []
  const bt = ps?.basis_type || 'all'

  const typeOpts = [
    { v: 'all', l: strictT(tr, lang, 'scope_all') },
    { v: 'ytd', l: strictT(tr, lang, 'scope_ytd') },
    { v: 'year', l: strictT(tr, lang, 'scope_year') },
    { v: 'month', l: strictT(tr, lang, 'scope_month') },
    { v: 'custom', l: strictT(tr, lang, 'scope_custom') },
  ]

  const IS = { ...SELECT_DARK, width: 'auto', fontSize: 11, padding: '5px 24px 5px 8px', backgroundSize: '8px 5px' }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap',
      background: BG.panel, border: `1px solid ${BG.border}`, borderRadius: 10, padding: '8px 12px' }}>

      <select value={bt} onChange={e => psUpdate({ basis_type: e.target.value, period: '', year: '', from_period: '', to_period: '' })} style={IS}>
        {typeOpts.map(o => <option key={o.v} value={o.v}>{o.l}</option>)}
      </select>

      {bt === 'month' && (
        <select value={ps?.period || ''} onChange={e => psUpdate({ period: e.target.value })} style={IS}>
          <option value="">—</option>
          {months.map(m => <option key={m} value={m}>{m}</option>)}
        </select>
      )}

      {(bt === 'year' || bt === 'ytd') && (
        <select value={ps?.year || ''} onChange={e => psUpdate({ year: e.target.value })} style={IS}>
          <option value="">
            {bt === 'ytd' ? strictT(tr, lang, 'scope_ytd_latest_option') : strictT(tr, lang, 'scope_year')}
          </option>
          {years.map(y => <option key={y} value={y}>{y}</option>)}
        </select>
      )}

      {bt === 'custom' && (<>
        <span style={{ fontSize: 10, color: C.text2 }}>{strictT(tr, lang, 'scope_from')}</span>
        <select value={ps?.from_period || ''} onChange={e => psUpdate({ from_period: e.target.value })} style={IS}>
          <option value="">—</option>
          {months.map(m => <option key={m} value={m}>{m}</option>)}
        </select>
        <span style={{ fontSize: 10, color: C.text2 }}>{strictT(tr, lang, 'scope_to')}</span>
        <select value={ps?.to_period || ''} onChange={e => psUpdate({ to_period: e.target.value })} style={IS}>
          <option value="">—</option>
          {months.map(m => <option key={m} value={m}>{m}</option>)}
        </select>
      </>)}

      <button type="button" onClick={onApply}
        style={{ padding: '5px 14px', borderRadius: 7, border: 'none',
          background: C.accent, color: '#000', fontSize: 11, fontWeight: 700,
          cursor: 'pointer', fontFamily: 'var(--font-display)' }}>
        {strictT(tr, lang, 'scope_apply')}
      </button>

      {activeLabel && (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: C.accent,
          background: `${C.accent}15`, padding: '3px 8px', borderRadius: 6, border: `1px solid ${C.accent}30` }}>
          {activeLabel}
        </span>
      )}
    </div>
  )
}
