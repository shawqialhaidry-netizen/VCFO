/**
 * Command Center — desktop-first body layout.
 * Top: optional paired Financial Health (left) + Primary Decision (right), or legacy in-grid primaryHero.
 * Main: ~68% left — KPI band, domain health, 2-col insights (signals | expense), narrative.
 * Side: ~32% — health (when not paired), branch intel, decisions, optional alerts strip.
 * Bottom (full width): secondary / deep links.
 * No business logic; parent passes section nodes.
 */
const row5 = {
  paddingTop: 24,
  borderTop: '1px solid rgba(148,163,184,0.12)',
  display: 'flex',
  flexDirection: 'column',
  gap: 14,
  opacity: 0.92,
}

const row0Hero = {
  minWidth: 0,
  width: '100%',
}

/**
 * @param {object} p
 * @param {import('react').ReactNode} [p.primaryHero]
 * @param {import('react').ReactNode} [p.rowTopHealth] — Financial Health (paired left)
 * @param {import('react').ReactNode} [p.rowTopHero] — Primary Decision (paired right)
 * @param {import('react').ReactNode} p.row1Narrative
 * @param {import('react').ReactNode} p.row1Health — sidebar health when top row is not paired
 * @param {import('react').ReactNode} [p.row2Kpis]
 * @param {import('react').ReactNode} [p.rowDomainHealth] — domain scores band (below KPIs)
 * @param {import('react').ReactNode} p.row3Signals
 * @param {import('react').ReactNode} p.row3Branch
 * @param {import('react').ReactNode} p.row4Expense
 * @param {import('react').ReactNode} p.row4Decisions
 * @param {import('react').ReactNode} [p.sidebarAlerts]
 * @param {import('react').ReactNode} p.secondaryBlock
 * @param {import('react').ReactNode} p.secondaryTitle
 * @param {import('react').ReactNode} p.secondarySubtitle
 * @param {boolean} [p.supportingDemoted]
 */
export default function CommandCenterDashboardGrid({
  primaryHero,
  rowTopHealth = null,
  rowTopHero = null,
  row1Narrative,
  row1Health,
  row2Kpis,
  rowDomainHealth = null,
  row3Signals,
  row3Branch,
  row4Expense,
  row4Decisions,
  sidebarAlerts = null,
  secondaryTitle,
  secondarySubtitle,
  secondaryBlock,
  supportingDemoted = false,
}) {
  const topPaired = rowTopHealth && rowTopHero
  const kpiBandCls = `cmd-kpi-strip cmd-scroll-anchor cmd-panel-kpi-band${supportingDemoted ? ' cmd-panel-kpi-band--demoted' : ''}`
  const leftColStyle = supportingDemoted ? { display: 'flex', flexDirection: 'column', gap: 24, minWidth: 0, opacity: 0.98 } : { display: 'flex', flexDirection: 'column', gap: 24, minWidth: 0 }
  const rightColStyle = supportingDemoted ? { display: 'flex', flexDirection: 'column', gap: 24, minWidth: 0, opacity: 0.97 } : { display: 'flex', flexDirection: 'column', gap: 24, minWidth: 0 }

  return (
    <div className="cmd-dashboard-desktop-root">
      {!topPaired && primaryHero ? (
        <div id="cmd-row-0" className="cmd-full cmd-primary-hero cmd-scroll-anchor" style={row0Hero}>
          {primaryHero}
        </div>
      ) : null}

      <div className="cmd-desktop-split cmd-scroll-anchor" id="cmd-desktop-main-split">
        <div className="cmd-desktop-primary-col" style={leftColStyle}>
          {topPaired ? (
            <div id="cmd-row-0" className="cmd-top-health-hero cmd-scroll-anchor cmd-primary-outer">
              <div className="cmd-top-health-col">{rowTopHealth}</div>
              <div className="cmd-top-hero-col">{rowTopHero}</div>
            </div>
          ) : null}

          <div id="cmd-row-2" className={`cmd-level-2 ${kpiBandCls}`} style={{ minWidth: 0 }}>
            {row2Kpis}
          </div>

          {rowDomainHealth ? (
            <div id="cmd-row-domain" className="cmd-domain-health-band cmd-scroll-anchor cmd-level-2" style={{ minWidth: 0 }}>
              {rowDomainHealth}
            </div>
          ) : null}

          <div id="cmd-row-3" className="cmd-desktop-insights-grid cmd-scroll-anchor">
            <div style={{ minWidth: 0 }}>{row3Signals}</div>
            <div id="cmd-row-4" style={{ minWidth: 0 }}>
              {row4Expense}
            </div>
          </div>

          <div id="cmd-row-1" className="cmd-scroll-anchor" style={{ minWidth: 0 }}>
            {row1Narrative}
          </div>
        </div>

        <aside className="cmd-desktop-side-col cmd-scroll-anchor" style={rightColStyle} role="complementary">
          {row1Health ? <div style={{ minWidth: 0 }}>{row1Health}</div> : null}
          <div style={{ minWidth: 0 }}>{row3Branch}</div>
          <div style={{ minWidth: 0 }}>{row4Decisions}</div>
          {sidebarAlerts ? <div style={{ minWidth: 0 }}>{sidebarAlerts}</div> : null}
        </aside>
      </div>

      <div id="cmd-row-5" className="cmd-full cmd-level-3 cmd-scroll-anchor" style={row5}>
        {secondaryTitle}
        {secondarySubtitle}
        {secondaryBlock}
      </div>
    </div>
  )
}
