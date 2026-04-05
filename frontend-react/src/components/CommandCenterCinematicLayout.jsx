/**
 * Command Center — reference-grade cinematic layout (desktop).
 * KPI strip → main chart column + right intelligence rail → bridge → dock → footer.
 */
export default function CommandCenterCinematicLayout({
  contextRail,
  kpiStrip,
  mainCharts,
  rightRail,
  bridge,
  tileStrip,
  collapsed,
  footerSecondary,
}) {
  return (
    <div
      className="cmd-os cmd-cine-root cmd-magic-root cmd-phase1-layout cmd-p3-root"
      style={{ display: 'flex', flexDirection: 'column', gap: 18, minWidth: 0 }}
    >
      <div className="cmd-cine-context">{contextRail}</div>

      {kpiStrip ? <div className="cmd-cine-kpi-zone">{kpiStrip}</div> : null}

      <div className="cmd-cine-body-grid">
        <div className="cmd-cine-body-main">{mainCharts}</div>
        <aside className="cmd-cine-body-rail">{rightRail}</aside>
      </div>

      {bridge}

      {tileStrip}

      <div className="cmd-phase1-collapsed" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {collapsed}
      </div>

      {footerSecondary ? (
        <div
          className="cmd-phase1-footer cmd-cine-footer"
          style={{
            paddingTop: 20,
            borderTop: '1px solid rgba(148,163,184,0.12)',
            display: 'flex',
            flexDirection: 'column',
            gap: 14,
            opacity: 0.92,
          }}
        >
          {footerSecondary}
        </div>
      ) : null}

      <style>{`
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
