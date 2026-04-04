/**
 * Icon-first tiles that expand one detail panel at a time (Command Center Phase 3).
 */
import { strictT as st } from '../utils/strictI18n.js'

const TILE_META = [
  { id: 'snapshot', icon: '◇', labelKey: 'cmd_cc_collapsed_snapshot' },
  { id: 'signals', icon: '⚡', labelKey: 'cmd_cc_collapsed_signals' },
  { id: 'domains', icon: '◎', labelKey: 'cmd_cc_collapsed_domains' },
  { id: 'more', icon: '▣', labelKey: 'cmd_cc_collapsed_more' },
  { id: 'narrative', icon: '✦', labelKey: 'cmd_cc_collapsed_narrative' },
]

export default function CommandCenterSecondaryTiles({ tr, lang, activeId, onSelect, onClose, children }) {
  const headLabel =
    activeId && TILE_META.find((t) => t.id === activeId)?.labelKey
      ? st(tr, lang, TILE_META.find((t) => t.id === activeId).labelKey)
      : ''

  return (
    <>
      <div className="cmd-p3-tiles" role="toolbar" aria-label={st(tr, lang, 'cmd_p3_tiles_aria')}>
        {TILE_META.map((t) => {
          const active = activeId === t.id
          return (
            <button
              key={t.id}
              type="button"
              className={`cmd-p3-tile${active ? ' cmd-p3-tile--active' : ''}`.trim()}
              onClick={() => onSelect(active ? null : t.id)}
              aria-pressed={active}
            >
              <span className="cmd-p3-tile__icon" aria-hidden>
                {t.icon}
              </span>
              {st(tr, lang, t.labelKey)}
            </button>
          )
        })}
      </div>
      {activeId ? (
        <div className="cmd-p3-tile-panel">
          <div className="cmd-p3-tile-panel__head">
            <span>{headLabel}</span>
            <button type="button" className="cmd-p3-tile-close" onClick={onClose} aria-label={st(tr, lang, 'cmd_p3_tile_close')}>
              ×
            </button>
          </div>
          <div className="cmd-p3-tile-panel__body">{children}</div>
        </div>
      ) : null}
    </>
  )
}
