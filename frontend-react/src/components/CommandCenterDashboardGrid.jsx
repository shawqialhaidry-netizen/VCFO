/**
 * Command Center main dashboard — CSS grid only (rows 1–5).
 * Parent passes section nodes; no business logic here.
 */
const gridShell = {
  display: 'grid',
  gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
  gap: 12,
  alignItems: 'stretch',
}

const row1 = {
  gridColumn: '1 / -1',
  display: 'grid',
  gridTemplateColumns: 'minmax(0, 1.12fr) minmax(0, 0.88fr)',
  gap: 12,
  alignItems: 'stretch',
  scrollMarginTop: 16,
}

const row2Wrap = {
  gridColumn: '1 / -1',
  minWidth: 0,
  scrollMarginTop: 16,
  padding: '10px 12px',
  borderRadius: 12,
  border: '1px solid rgba(148,163,184,0.14)',
  background: 'linear-gradient(165deg, rgba(17,24,39,0.95) 0%, rgba(15,23,42,0.98) 100%)',
  boxShadow: '0 0 0 1px rgba(0,212,170,0.05), 0 8px 28px rgba(0,0,0,0.35)',
}

const col = { minWidth: 0, scrollMarginTop: 16 }

const row5 = {
  gridColumn: '1 / -1',
  scrollMarginTop: 16,
  paddingTop: 10,
  borderTop: '1px solid rgba(148,163,184,0.1)',
  display: 'flex',
  flexDirection: 'column',
  gap: 8,
  opacity: 0.9,
}

/**
 * @param {object} p
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
 */
export default function CommandCenterDashboardGrid({
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
}) {
  return (
    <div className="cmd-dashboard-grid" style={gridShell}>
      <div id="cmd-row-1" className="cmd-r1" style={row1}>
        <div style={{ minWidth: 0 }}>{row1Narrative}</div>
        <div style={{ minWidth: 0 }}>{row1Health}</div>
      </div>

      <div id="cmd-row-2" className="cmd-full cmd-level-2" style={row2Wrap}>
        {row2Kpis}
      </div>

      <div id="cmd-row-3" className="cmd-level-2" style={col}>
        {row3Signals}
      </div>
      <div className="cmd-level-2" style={col}>
        {row3Branch}
      </div>

      <div id="cmd-row-4" className="cmd-level-2" style={col}>
        {row4Expense}
      </div>
      <div className="cmd-level-2" style={col}>
        {row4Decisions}
      </div>

      <div id="cmd-row-5" className="cmd-full cmd-level-3" style={row5}>
        {secondaryTitle}
        {secondarySubtitle}
        {secondaryBlock}
      </div>
    </div>
  )
}
