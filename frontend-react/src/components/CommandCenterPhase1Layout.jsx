/**
 * Command Center Phase 1 — single reading path layout (no business logic).
 */
export default function CommandCenterPhase1Layout({
  contextRail,
  heroLeft,
  heroRight,
  secondaryHealth,
  secondaryFlow,
  secondaryBranch,
  collapsed,
  footerSecondary,
}) {
  return (
    <div className="cmd-phase1-layout" style={{ display: 'flex', flexDirection: 'column', gap: 16, minWidth: 0 }}>
      {contextRail}

      {/* B) Hero — story | primary decision */}
      <div
        className="cmd-phase1-hero"
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)',
          gap: 16,
          alignItems: 'stretch',
        }}
      >
        <div style={{ minWidth: 0 }}>{heroLeft}</div>
        <div style={{ minWidth: 0 }}>{heroRight}</div>
      </div>

      {/* C) Secondary — health | flow | branch */}
      <div
        className="cmd-phase1-secondary"
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(220px, 1.1fr) minmax(200px, 1fr) minmax(200px, 0.9fr)',
          gap: 14,
          alignItems: 'stretch',
        }}
      >
        <div style={{ minWidth: 0 }}>{secondaryHealth}</div>
        <div style={{ minWidth: 0 }}>{secondaryFlow}</div>
        <div style={{ minWidth: 0 }}>{secondaryBranch}</div>
      </div>

      {/* D) Collapsed detail */}
      <div className="cmd-phase1-collapsed" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
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
            opacity: 0.94,
          }}
        >
          {footerSecondary}
        </div>
      ) : null}

      <style>{`
        @media (max-width: 1100px) {
          .cmd-phase1-hero { grid-template-columns: 1fr !important; }
          .cmd-phase1-secondary { grid-template-columns: 1fr !important; }
        }
        @media (min-width: 1101px) and (max-width: 1320px) {
          .cmd-phase1-secondary { grid-template-columns: 1fr 1fr !important; }
          .cmd-phase1-secondary > div:last-child { grid-column: 1 / -1; }
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
