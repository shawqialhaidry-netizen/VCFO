/**
 * statement_hierarchy row labels:
 * - structural rows always come from i18n
 * - known recurring account rows can use a controlled frontend dictionary
 * - unknown account rows keep the original source label
 */
import { localizedMissingPlaceholder, looksLikeRawI18nKey, strictT } from './strictI18n.js'

/** Backend `node.key` -> bundled i18n key (mirrors label_key where present). */
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
  cf_opening_cash: 'stmt_hier_cf_opening_cash',
  cf_net_change: 'stmt_hier_cf_net_change',
  cf_ending_cash: 'stmt_hier_cf_ending_cash',
  cf_np: 'stmt_hier_cf_np',
  cf_da: 'stmt_hier_cf_da',
  cf_d_ar: 'stmt_hier_cf_d_ar',
  cf_d_inv: 'stmt_hier_cf_d_inv',
  cf_d_ap: 'stmt_hier_cf_d_ap',
  cf_wc_adj: 'stmt_hier_cf_wc_adj',
  cf_fcf: 'stmt_hier_cf_fcf',
})

const KNOWN_LEAF_LABEL_ALIASES = Object.freeze({
  stmt_leaf_service_revenue: ['Service Revenue', 'Revenue - Services', 'Services Revenue'],
  stmt_leaf_sales_revenue: ['Sales Revenue', 'Revenue - Sales', 'Sales', 'Revenue', 'Product Revenue', 'Revenue - Products'],
  stmt_leaf_consulting_revenue: ['Consulting Revenue', 'Revenue - Consulting'],
  stmt_leaf_project_revenue: ['Project Revenue', 'Revenue - Projects', 'Projects Revenue'],
  stmt_leaf_other_income: ['Other Income', 'Miscellaneous Income', 'Non-Operating Income', 'Other Revenue'],
  stmt_leaf_sales_discounts: ['Sales Discounts', 'Discounts', 'Sales Returns and Allowances', 'Revenue Discounts'],
  stmt_leaf_cost_of_sales: ['Cost of Sales', 'Cost of Goods Sold', 'COGS', 'Cost of Revenue'],
  stmt_leaf_materials_inventory: ['Materials Inventory', 'Materials', 'Raw Materials', 'Consumables', 'Inventory'],
  stmt_leaf_direct_labor: ['Direct Labor', 'Direct Labour', 'Direct Wages'],
  stmt_leaf_shipping_expense: ['Shipping', 'Shipping Expense', 'Freight Out', 'Delivery Expense', 'Logistics Expense'],
  stmt_leaf_payroll_expense: ['Payroll Expense', 'Payroll Expenses', 'Payroll', 'Staff Costs'],
  stmt_leaf_salaries_wages: ['Salaries and Wages', 'Salaries & Wages', 'Wages Expense', 'Salaries', 'Wages', 'Employee Salaries'],
  stmt_leaf_rent_expense: ['Rent Expense', 'Office Rent', 'Rent', 'Lease Expense'],
  stmt_leaf_utilities_expense: ['Utilities Expense', 'Utilities Expenses', 'Utilities', 'Electricity and Water', 'Electricity Expense', 'Water Expense'],
  stmt_leaf_fuel_expense: ['Fuel Expense', 'Fuel Costs', 'Fuel', 'Vehicle Fuel'],
  stmt_leaf_maintenance_repairs: ['Maintenance & Repairs', 'Maintenance and Repairs', 'Repairs and Maintenance', 'Maintenance Expense', 'Repairs Expense', 'Maintenance'],
  stmt_leaf_admin_expenses: ['Administrative Expenses', 'Admin Expenses', 'General and Administrative Expenses', 'G&A Expenses'],
  stmt_leaf_operating_expenses: ['Operating Expenses', 'Other Operating Expenses'],
  stmt_leaf_selling_marketing_expenses: ['Selling and Marketing Expenses', 'Sales and Marketing Expenses', 'Marketing Expense'],
  stmt_leaf_office_supplies: ['Office Supplies', 'Office Supplies Expense'],
  stmt_leaf_cash_and_cash_equivalents: ['Cash & Cash Equivalents', 'Cash and Cash Equivalents', 'Cash'],
  stmt_leaf_cash_on_hand: ['Cash on Hand', 'Cash in Hand', 'Petty Cash'],
  stmt_leaf_cash_at_bank: ['Cash at Bank', 'Bank Account', 'Bank Balance', 'Cash in Bank'],
  stmt_leaf_accounts_receivable_trade: [
    'Accounts Receivable',
    'Accounts Receivable - Trade',
    'Accounts Receivable-Trade',
    'Accounts Receivable Trade',
    'Trade Accounts Receivable',
    'Trade Receivables',
    'Receivables',
    'A/R - Trade',
    'A/R Trade',
  ],
  stmt_leaf_accounts_receivable_intercompany: [
    'Accounts Receivable - Intercompany',
    'Accounts Receivable-Intercompany',
    'Accounts Receivable Intercompany',
    'Intercompany Receivables',
    'Intercompany Accounts Receivable',
    'A/R - Intercompany',
    'A/R Intercompany',
  ],
  stmt_leaf_inventory_goods_in_transit: [
    'Inventory - Goods in Transit',
    'Inventory-Goods in Transit',
    'Inventory Goods in Transit',
    'Goods in Transit',
  ],
  stmt_leaf_inventory_warehouse: [
    'Inventory - Warehouse',
    'Inventory-Warehouse',
    'Inventory Warehouse',
    'Warehouse Inventory',
    'Finished Goods Inventory',
  ],
  stmt_leaf_prepaid_rent: ['Prepaid Rent'],
  stmt_leaf_prepaid_insurance: ['Prepaid Insurance'],
  stmt_leaf_other_prepaid_expenses: ['Other Prepaid Expenses', 'Prepayments', 'Prepaid Expenses'],
  stmt_leaf_vehicles_and_fleet: ['Vehicles & Fleet', 'Vehicles and Fleet', 'Vehicles', 'Fleet Vehicles', 'Fleet'],
  stmt_leaf_office_equipment: ['Office Equipment', 'Furniture and Fixtures', 'Furniture & Fixtures', 'Computer Equipment', 'Computers'],
  stmt_leaf_machinery_and_warehouse_equip: [
    'Machinery & Warehouse Equip',
    'Machinery and Warehouse Equip',
    'Machinery',
    'Warehouse Equipment',
    'Plant and Equipment',
    'Property Plant and Equipment',
    'PPE',
    'Equipment',
  ],
  stmt_leaf_leasehold_improvements: ['Leasehold Improvements'],
  stmt_leaf_accumulated_depreciation_generic: ['Accumulated Depreciation'],
  stmt_leaf_accumulated_depreciation_vehicles: [
    'Accumulated Depreciation - Vehicles',
    'Accumulated Depreciation-Vehicles',
    'Accumulated Depreciation Vehicles',
  ],
  stmt_leaf_accumulated_depreciation_equipment: [
    'Accumulated Depreciation - Equipment',
    'Accumulated Depreciation-Equipment',
    'Accumulated Depreciation Equipment',
  ],
  stmt_leaf_accumulated_depreciation_machinery: [
    'Accumulated Depreciation - Machinery',
    'Accumulated Depreciation-Machinery',
    'Accumulated Depreciation Machinery',
  ],
  stmt_leaf_accounts_payable: ['Accounts Payable', 'Trade Payables', 'AP', 'A/P', 'Payables'],
  stmt_leaf_accrued_expenses: ['Accrued Expenses', 'Accrued Liabilities', 'Accrued Payroll', 'Accrued Rent', 'Accrued Utilities'],
  stmt_leaf_salaries_payable: ['Salaries Payable', 'Wages Payable', 'Payroll Payable'],
  stmt_leaf_tax_payable: ['Tax Payable', 'Income Tax Payable', 'Taxes Payable'],
  stmt_leaf_vat_payable: ['VAT Payable', 'Sales Tax Payable'],
  stmt_leaf_short_term_loan: ['Short-Term Loan', 'Short Term Loan', 'Current Loan', 'Current Portion of Loan', 'Short-Term Debt', 'Short Term Debt'],
  stmt_leaf_long_term_loan: ['Long-Term Loan', 'Long Term Loan', 'Long-Term Debt', 'Long Term Debt', 'Bank Loan'],
  stmt_leaf_notes_payable: ['Notes Payable'],
  stmt_leaf_retained_earnings: ['Retained Earnings'],
  stmt_leaf_share_capital: ['Share Capital', 'Capital Stock', 'Issued Capital'],
  stmt_leaf_common_stock: ['Common Stock', 'Ordinary Shares', 'Ordinary Share Capital'],
  stmt_leaf_additional_paid_in_capital: ['Additional Paid-In Capital', 'Additional Paid in Capital', 'Paid-In Capital', 'Paid in Capital', 'APIC'],
  stmt_leaf_owners_equity: ["Owner's Equity", 'Owners Equity', 'Owner Equity', 'Equity'],
  stmt_leaf_owner_drawings: ['Owner Drawings', 'Drawings', 'Partner Drawings'],
  stmt_leaf_capital_expenditure_estimated: ['capital_expenditure_estimated', 'Capital Expenditure Estimated'],
  stmt_leaf_asset_disposals_estimated: ['asset_disposals_estimated', 'Asset Disposals Estimated'],
  stmt_leaf_debt_increase: ['debt_increase', 'Debt Increase'],
  stmt_leaf_debt_repayment: ['debt_repayment', 'Debt Repayment'],
  stmt_leaf_equity_injection_estimated: ['equity_injection_estimated', 'Equity Injection Estimated'],
  stmt_leaf_equity_reduction_estimated: ['equity_reduction_estimated', 'Equity Reduction Estimated'],
  stmt_leaf_owner_distributions_estimated: ['owner_distributions_estimated', 'Owner Distributions Estimated', 'Dividends', 'Dividend Distribution'],
})

function normalizeLeafLabel(label) {
  return String(label || '')
    .normalize('NFKC')
    .replace(/[\u200B-\u200D\u2060\uFEFF]/g, '')
    .replace(/[\u2010\u2011\u2012\u2013\u2014\u2015\u2212]/g, '-')
    .replace(/\s*&\s*/g, ' and ')
    .replace(/\ba\s*\/\s*r\b/g, 'accounts receivable')
    .replace(/\s*-\s*/g, ' - ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
}

export const KNOWN_LEAF_LABEL_TO_I18N = Object.freeze(
  Object.entries(KNOWN_LEAF_LABEL_ALIASES).reduce((acc, [i18nKey, aliases]) => {
    for (const alias of aliases) {
      acc[normalizeLeafLabel(alias)] = i18nKey
    }
    return acc
  }, {})
)

/**
 * Account line items from backend use `leaf: true` or keys like `rev_line_*`, `cogs_line_*`, etc.
 */
export function isAccountLeafRow(node) {
  if (!node || typeof node !== 'object') return false
  if (node.leaf === true) return true
  if (typeof node.line_id === 'string' && node.line_id.trim()) return true
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

function getLeafSourceLabel(node) {
  const candidates = [node?.account_name, node?.label, node?.name, node?.title, node?.line_id]
  for (const value of candidates) {
    if (typeof value !== 'string') continue
    const text = value.trim()
    if (text) return text
  }
  return ''
}

export function resolveStatementHierarchyBadgeLabel(provenance, tr, lang) {
  const key = ({
    direct_source_leaf: 'stmt_badge_source',
    merged_source_leaf: 'stmt_badge_merged',
    derived_subtotal: 'stmt_badge_subtotal',
    derived_metric: 'stmt_badge_derived',
    synthetic_injected: 'stmt_badge_synthetic',
    structural_container: 'stmt_badge_structure',
  })[String(provenance || '')]
  return key ? strictT(tr, lang, key) : ''
}

export function resolveStatementHierarchyNote(node, tr, lang) {
  if (!node || typeof node !== 'object') return ''
  const reason = String(node.note || '').trim().toLowerCase()
  const availability = String(node.availability || '').trim().toLowerCase()
  const sectionFlags = node.section_flags && typeof node.section_flags === 'object' ? node.section_flags : null
  const reasonKey = ({
    not_modeled: 'stmt_note_not_modeled',
    not_modeled_yet: 'stmt_note_not_modeled_yet',
    opening_balance_unavailable: 'stmt_note_opening_balance_unavailable',
    no_classifiable_financing_accounts: 'stmt_note_no_classifiable_financing_accounts',
  })[reason]

  if (reasonKey) return strictT(tr, lang, reasonKey)
  if (sectionFlags && (sectionFlags.other_investing_unavailable || sectionFlags.other_financing_unavailable)) {
    return strictT(tr, lang, 'stmt_note_partial')
  }
  if (availability === 'partial') return strictT(tr, lang, 'stmt_note_partial')
  if (availability === 'unavailable') return strictT(tr, lang, 'stmt_note_unavailable')
  return ''
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

  for (const key of keysToTry) {
    return strictT(tr, lang, key)
  }
  return localizedMissingPlaceholder(lang)
}

function resolveLeafLabel(node, tr, lang) {
  const sourceLabel = getLeafSourceLabel(node)
  if (!sourceLabel) return '-'
  const dictKey = KNOWN_LEAF_LABEL_TO_I18N[normalizeLeafLabel(sourceLabel)]
  if (dictKey) {
    const mapped = translateIfMapped(tr, lang, dictKey)
    if (mapped) return mapped
  }
  return sourceLabel
}

/**
 * @returns {{ text: string, rowKind: 'structural' | 'source' }}
 */
export function resolveStatementHierarchyRowLabel(node, tr, lang) {
  if (!node || typeof node !== 'object') {
    return { text: '-', rowKind: 'structural' }
  }
  if (isAccountLeafRow(node)) {
    return { text: resolveLeafLabel(node, tr, lang), rowKind: 'source' }
  }
  return { text: resolveStructuralLabel(node, tr, lang), rowKind: 'structural' }
}

export function resolveStatementHierarchyRootTitle(root, tr, lang) {
  if (!root || typeof root !== 'object') return '-'
  return resolveStructuralLabel(root, tr, lang)
}
