/**
 * Command Center layout — Phase 3 executive band + intelligence deck + tile strip.
 */
export default function CommandCenterPhase1Layout({
  contextRail,
  executiveBand,
  intelligenceDeck,
  tileStrip,
  collapsed,
  footerSecondary,
}) {
  return (
    <div
      className="cmd-magic-root cmd-phase1-layout cmd-p3-root"
      style={{ display: 'flex', flexDirection: 'column', gap: 20, minWidth: 0 }}
    >
      {contextRail}

      {/* A) Executive band — story | primary decision | financial health */}
      <div className="cmd-p3-executive-band">{executiveBand}</div>

      {/* Charts + profit path bridge */}
      {intelligenceDeck}

      {/* Icon tiles → expand detail */}
      {tileStrip}

      {/* Lower collapsed (lighter) */}
      <div className="cmd-phase1-collapsed" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {collapsed}
      </div>

      {footerSecondary ? (
        <div
          className="cmd-phase1-footer"
          style={{
            paddingTop: 20,
            borderTop: '1px solid rgba(148,163,184,0.12)',
            display: 'flex',
            flexDirection: 'column',
            gap: 14,
            opacity: 0.88,
          }}
        >
          {footerSecondary}
        </div>
      ) : null}

      <style>{`
        @media (max-width: 1100px) {
          .cmd-p3-executive-band { grid-template-columns: 1fr !important; }
        }
        .cmd-phase1-details { border-radius: 12px; border: 1px solid var(--border); background: rgba(255,255,255,0.02); }
        .cmd-phase1-details > summary {
          cursor: pointer;
          list-style: none;
          padding: 12px 16px;
          font-size: 11px;
          font-weight: 800;
          letter-spacing: .08em;
          text-transform: uppercase;
          color: var(--text-secondary);
          user-select: none;
        }
        .cmd-phase1-details > summary::-webkit-details-marker { display: none; }
        .cmd-phase1-details[open] > summary { border-bottom: 1px solid var(--border); }
        .cmd-phase1-details-body { padding: 14px 16px 16px; }
      `}</style>
    </div>
  )
}
