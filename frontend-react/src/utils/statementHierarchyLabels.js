/**
 * statement_hierarchy row labels — structural rows always localized (no raw backend English);
 * account leaf rows keep real source names unless an explicit i18n mapping resolves.
 */
import { localizedMissingPlaceholder, looksLikeRawI18nKey } from './strictI18n.js'

/** Backend `node.key` → bundled i18n key (mirrors label_key where present; fallback when tr(label_key) misses). */
export const STRUCTURAL_KEY_TO_I18N = Object.freeze({
  income_statement: 'stmt_section_is',
  balance_sheet: 'stmt_section_bs',
  cashflow_statement: 'stmt_hier_cashflow_root',
  revenue: 'stmt_hier_revenue',
  revenue_total: 'stmt_hier_net_revenue',
  cogs_total: 'stmt_hier_total_cogs',
  gross_profit: 'stmt_hier_gross_profit',
  opex_total: 'stmt_hier_total_opex',
  unclassified_pnl: 'stmt_hier_unclassified_pnl',
  tax: 'stmt_hier_tax',
  operating_profit: 'stmt_hier_operating_profit',
  net_profit: 'stmt_hier_net_profit',
  assets: 'stmt_hier_assets',
  current_assets: 'stmt_hier_current_assets',
  noncurrent_assets: 'stmt_hier_noncurrent_assets',
  liabilities: 'stmt_hier_liabilities',
  current_liabilities: 'stmt_hier_current_liabilities',
  noncurrent_liabilities: 'stmt_hier_noncurrent_liabilities',
  equity: 'stmt_hier_equity',
  working_capital: 'stmt_hier_working_capital',
  cf_operating: 'stmt_hier_cf_operating',
  cf_investing: 'stmt_hier_cf_investing',
  cf_financing: 'stmt_hier_cf_financing',
  cf_np: 'stmt_hier_cf_np',
  cf_da: 'stmt_hier_cf_da',
  cf_d_ar: 'stmt_hier_cf_d_ar',
  cf_d_inv: 'stmt_hier_cf_d_inv',
  cf_d_ap: 'stmt_hier_cf_d_ap',
  cf_wc_adj: 'stmt_hier_cf_wc_adj',
  cf_fcf: 'stmt_hier_cf_fcf',
})

/**
 * Account line items from backend use `leaf: true` or keys like `rev_line_*`, `cogs_line_*`, etc.
 */
export function isAccountLeafRow(node) {
  if (!node || typeof node !== 'object') return false
  if (node.leaf === true) return true
  const k = String(node.key || '')
  return k.includes('_line_')
}

/**
 * Returns a translated string only when `tr` produced a real mapping (not missing placeholder / raw key).
 */
export function translateIfMapped(tr, lang, key) {
  if (!key || typeof key !== 'string') return null
  let v
  try {
    v = tr(key)
  } catch {
    return null
  }
  const miss = localizedMissingPlaceholder(lang)
  if (v == null || v === '' || v === key || v === miss || looksLikeRawI18nKey(v)) return null
  return v
}

function humanizeKey(key) {
  const k = String(key || '').trim()
  if (!k) return '—'
  return k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

function resolveStructuralLabel(node, tr, lang) {
  const tried = new Set()
  const keysToTry = []
  if (node.label_key) {
    const lk = String(node.label_key)
    keysToTry.push(lk)
    tried.add(lk)
  }
  const mapped = STRUCTURAL_KEY_TO_I18N[node.key]
  if (mapped && !tried.has(mapped)) keysToTry.push(mapped)

  for (const k of keysToTry) {
    const t = translateIfMapped(tr, lang, k)
    if (t) return t
  }
  return humanizeKey(node.key)
}

function resolveLeafLabel(node, tr, lang) {
  if (node.label_key) {
    const t = translateIfMapped(tr, lang, String(node.label_key))
    if (t) return t
  }
  const name = String(node.account_name ?? '').trim()
  const lbl = String(node.label ?? '').trim()
  return name || lbl || '—'
}

/**
 * @returns {{ text: string, rowKind: 'structural' | 'source' }}
 */
export function resolveStatementHierarchyRowLabel(node, tr, lang) {
  if (!node || typeof node !== 'object') {
    return { text: '—', rowKind: 'structural' }
  }
  if (isAccountLeafRow(node)) {
    return { text: resolveLeafLabel(node, tr, lang), rowKind: 'source' }
  }
  return { text: resolveStructuralLabel(node, tr, lang), rowKind: 'structural' }
}

export function resolveStatementHierarchyRootTitle(root, tr, lang) {
  if (!root || typeof root !== 'object') return '—'
  return resolveStructuralLabel(root, tr, lang)
}
