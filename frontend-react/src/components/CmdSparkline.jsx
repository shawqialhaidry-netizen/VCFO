/**
 * Decorative KPI / metric sparkline (inline SVG). Trend from MoM sign when provided.
 */
export default function CmdSparkline({ mom }) {
  const trend =
    mom == null || !Number.isFinite(Number(mom)) ? 'flat' : Number(mom) < 0 ? 'down' : Number(mom) > 0 ? 'up' : 'flat'
  const pts =
    trend === 'down'
      ? '0,8 20,14 40,10 60,18 80,12 100,20'
      : trend === 'flat'
        ? '0,15 20,16 40,15 60,16 80,15 100,15'
        : '0,20 20,15 40,18 60,10 80,14 100,8'
  return (
    <svg className="cmd-spark" viewBox="0 0 100 30" aria-hidden>
      <polyline fill="none" stroke="rgba(0,212,170,0.6)" strokeWidth="2" points={pts} />
    </svg>
  )
}
