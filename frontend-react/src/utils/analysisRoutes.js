/**
 * Canonical Analysis screen URLs ↔ tab state (`focus` in location.state).
 * Command Center drills use these paths; Analysis tab bar keeps URL in sync.
 */
import { analysisTabFromDrill } from './commandCenterDrill.js'

/** Internal Analysis tab key → browser path */
export const ANALYSIS_PATH_BY_TAB = {
  overview: '/analysis',
  profitability: '/profitability',
  liquidity: '/cash',
  efficiency: '/expenses',
  decisions: '/decisions',
  alerts: '/alerts',
}

const PATH_BY_KPI_TYPE = {
  revenue: '/revenue',
  expenses: '/expenses',
  net_profit: '/profitability',
  net_margin: '/profitability',
  cashflow: '/cash',
  working_capital: '/cash',
}

/**
 * Resolve navigation target from Command Center drawer / KPI payload.
 */
export function analysisDrillTarget({ type, domain } = {}) {
  const d = String(domain || '')
  if (d === 'liquidity') return { path: '/cash', focus: 'liquidity' }
  if (d === 'profitability') return { path: '/profitability', focus: 'profitability' }
  if (d === 'efficiency') return { path: '/expenses', focus: 'efficiency' }
  if (d === 'leverage' || d === 'growth') return { path: '/expenses', focus: 'efficiency' }

  const t = String(type || '')
  const pathFromKpi = PATH_BY_KPI_TYPE[t]
  if (pathFromKpi) {
    return { path: pathFromKpi, focus: analysisTabFromDrill({ type, domain }) }
  }

  const tab = analysisTabFromDrill({ type, domain })
  const path = ANALYSIS_PATH_BY_TAB[tab] || '/analysis'
  return { path, focus: tab }
}

/**
 * Context panel type + payload → full analysis route (drawer “Open analysis” footer).
 */
export function analysisPathFromPanelType(pType, pLoad) {
  if (pType === 'alert') return { path: '/alerts', focus: 'alerts' }
  if (pType === 'expense_v2') return { path: '/decisions', focus: 'decisions' }
  if (pType === 'kpi') return analysisDrillTarget({ type: pLoad?.type, domain: pLoad?.domain })
  if (pType === 'decision') return analysisDrillTarget({ type: 'decision', domain: pLoad?.domain })
  if (pType === 'domain') return analysisDrillTarget({ domain: pLoad?.domain })
  return { path: '/analysis', focus: 'overview' }
}

/**
 * Map `drillAnalysis(tab)` argument (including `forecast`) → path + focus.
 */
export function pathForDrillAnalysisTab(tab) {
  const k = String(tab || 'overview')
  if (k === 'forecast') return { path: '/forecast', focus: 'overview' }
  const path = ANALYSIS_PATH_BY_TAB[k] || '/analysis'
  return { path, focus: k }
}
