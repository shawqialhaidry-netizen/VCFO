/**
 * Command Center main dashboard — CSS grid only (optional row 0 hero, then rows 1–5).
 * Parent passes section nodes; no business logic here.
 */
const gridShell = {
  display: 'grid',
  gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
  gap: 16,
  alignItems: 'stretch',
}

const row1 = {
  gridColumn: '1 / -1',
  display: 'grid',
  gridTemplateColumns: 'minmax(0, 1.12fr) minmax(0, 0.88fr)',
  gap: 16,
  alignItems: 'stretch',
}

const row0Hero = {
  gridColumn: '1 / -1',
  minWidth: 0,
}

const row2WrapBase = {
  gridColumn: '1 / -1',
  minWidth: 0,
  padding: '14px 16px',
  borderRadius: 14,
  border: '1px solid rgba(148,163,184,0.14)',
  background: 'linear-gradient(165deg, rgba(17,24,39,0.95) 0%, rgba(15,23,42,0.98) 100%)',
  boxShadow: '0 4px 24px rgba(0,0,0,0.28)',
}

const row2WrapDemoted = {
  ...row2WrapBase,
  padding: '12px 14px',
  opacity: 0.94,
  boxShadow: '0 2px 16px rgba(0,0,0,0.22)',
}

const col = { minWidth: 0 }

const row5 = {
  gridColumn: '1 / -1',
  paddingTop: 24,
  borderTop: '1px solid rgba(148,163,184,0.1)',
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
  opacity: 0.9,
}

/**
 * @param {object} p
 * @param {import('react').ReactNode} [p.primaryHero]
 * @param {import('react').ReactNode} p.row1Narrative
 * @param {import('react').ReactNode} p.row1Health
 * @param {import('react').ReactNode} [p.row2Kpis]
 * @param {import('react').ReactNode} p.row3Signals
 * @param {import('react').ReactNode} p.row3Branch
 * @param {import('react').ReactNode} p.row4Expense
 * @param {import('react').ReactNode} p.row4Decisions
 * @param {import('react').ReactNode} p.secondaryBlock
 * @param {import('react').ReactNode} p.secondaryTitle
 * @param {import('react').ReactNode} p.secondarySubtitle
 * @param {boolean} [p.supportingDemoted] — softer KPI band when primary hero is shown
 */
export default function CommandCenterDashboardGrid({
  primaryHero,
  row1Narrative,
  row1Health,
  row2Kpis,
  row3Signals,
  row3Branch,
  row4Expense,
  row4Decisions,
  secondaryTitle,
  secondarySubtitle,
  secondaryBlock,
  supportingDemoted = false,
}) {
  const row2Wrap = supportingDemoted ? row2WrapDemoted : row2WrapBase
  const row1Style = supportingDemoted ? { ...row1, opacity: 0.97 } : row1
  const colStyle = supportingDemoted ? { ...col, opacity: 0.96 } : col

  return (
    <div className="cmd-dashboard-grid" style={gridShell}>
      {primaryHero ? (
        <div id="cmd-row-0" className="cmd-full cmd-primary-hero cmd-scroll-anchor" style={row0Hero}>
          {primaryHero}
        </div>
      ) : null}
      <div id="cmd-row-1" className="cmd-r1 cmd-scroll-anchor" style={row1Style}>
        <div style={{ minWidth: 0 }}>{row1Narrative}</div>
        <div style={{ minWidth: 0 }}>{row1Health}</div>
      </div>

      <div id="cmd-row-2" className="cmd-full cmd-level-2 cmd-scroll-anchor cmd-kpi-strip" style={row2Wrap}>
        {row2Kpis}
      </div>

      <div id="cmd-row-3" className="cmd-level-2 cmd-scroll-anchor" style={colStyle}>
        {row3Signals}
      </div>
      <div className="cmd-level-2 cmd-scroll-anchor" style={colStyle}>
        {row3Branch}
      </div>

      <div id="cmd-row-4" className="cmd-level-2 cmd-scroll-anchor" style={colStyle}>
        {row4Expense}
      </div>
      <div className="cmd-level-2 cmd-scroll-anchor" style={colStyle}>
        {row4Decisions}
      </div>

      <div id="cmd-row-5" className="cmd-full cmd-level-3 cmd-scroll-anchor" style={row5}>
        {secondaryTitle}
        {secondarySubtitle}
        {secondaryBlock}
      </div>
    </div>
  )
}
