/**
 * statement_hierarchy only — premium CFO workspace (Phase 4B).
 */
import React from 'react'
import { formatCompactForLang } from '../utils/numberFormat.js'
import {
  resolveStatementHierarchyRootTitle,
  resolveStatementHierarchyRowLabel,
  resolveStatementHierarchyBadgeLabel,
  resolveStatementHierarchyNote,
} from '../utils/statementHierarchyLabels.js'
import '../styles/statements-premium.css'

function fmt(v, lang) {
  if (v == null || v === '') return '—'
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  return formatCompactForLang(n, lang)
}

/** Visual lane for hierarchy rows — keys from backend statement_hierarchy only. */
function incomeRowLane(node) {
  const k = node.key || ''
  if (k === 'net_profit') return 'net'
  if (k === 'gross_profit' || k === 'operating_profit') return 'profit'
  if (k === 'revenue_total') return 'is_total'
  if (k === 'cogs_total' || k === 'opex_total') return 'subtotal'
  if (k === 'revenue' || k === 'tax' || k === 'unclassified_pnl') return 'section'
  return 'line'
}

function balanceRowLane(node) {
  const k = node.key || ''
  if (k === 'working_capital') return 'wc'
  if (k === 'assets' || k === 'liabilities' || k === 'equity') return 'pillar'
  if (
    k === 'current_assets' ||
    k === 'noncurrent_assets' ||
    k === 'current_liabilities' ||
    k === 'noncurrent_liabilities'
  ) {
    return 'split'
  }
  return 'line'
}

function cashRowLane(node) {
  const k = node.key || ''
  if (k === 'cf_operating') return 'ocf'
  if (k === 'cf_fcf') return 'fcf'
  return 'bridge'
}

function laneStyle(lane, { hasKids, statementKind, rowKind }) {
  const base = {
    borderBottom: '1px solid rgba(255,255,255,0.055)',
    transition: 'background 0.15s ease',
  }
  if (statementKind === 'income') {
    if (lane === 'net') {
      return {
        ...base,
        marginTop: 8,
        paddingTop: 12,
        paddingBottom: 12,
        borderTop: '1px solid rgba(255,255,255,0.14)',
        background: 'linear-gradient(90deg, rgba(63,185,80,0.18) 0%, transparent 58%)',
        borderInlineStart: '3px solid rgba(63,185,80,0.85)',
      }
    }
    if (lane === 'profit') {
      return {
        ...base,
        marginTop: 4,
        background: 'linear-gradient(90deg, rgba(88,166,255,0.12) 0%, transparent 52%)',
        borderInlineStart: '3px solid rgba(88,166,255,0.58)',
      }
    }
    if (lane === 'is_total') {
      return {
        ...base,
        marginTop: 6,
        paddingTop: 8,
        paddingBottom: 8,
        borderTop: '1px solid rgba(255,255,255,0.09)',
        background: 'linear-gradient(165deg, rgba(88,166,255,0.09) 0%, transparent 70%)',
        borderInlineStart: '3px solid rgba(88,166,255,0.35)',
      }
    }
    if (lane === 'subtotal' && hasKids) {
      return {
        ...base,
        background: 'linear-gradient(165deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.02) 100%)',
        borderInlineStart: '2px solid rgba(136,166,255,0.28)',
      }
    }
    if (lane === 'section' && hasKids) {
      return {
        ...base,
        background: 'rgba(255,255,255,0.035)',
        borderInlineStart: '2px solid rgba(136,166,255,0.2)',
      }
    }
  }
  if (statementKind === 'balance') {
    if (lane === 'wc') {
      return {
        ...base,
        marginTop: 8,
        paddingTop: 12,
        paddingBottom: 12,
        borderRadius: 8,
        border: '1px solid rgba(210,168,75,0.35)',
        background: 'linear-gradient(180deg, rgba(210,168,75,0.14) 0%, rgba(210,168,75,0.05) 100%)',
        borderBottom: '1px solid rgba(210,168,75,0.25)',
      }
    }
    if (lane === 'pillar' && hasKids) {
      return {
        ...base,
        background: 'rgba(255,255,255,0.042)',
        borderInlineStart: '2px solid rgba(136,166,255,0.22)',
      }
    }
    if (lane === 'split') {
      return {
        ...base,
        background: 'rgba(255,255,255,0.028)',
        borderInlineStart: '1px solid rgba(255,255,255,0.06)',
      }
    }
  }
  if (statementKind === 'cash') {
    if (lane === 'ocf' && hasKids) {
      return {
        ...base,
        background: 'rgba(255,255,255,0.05)',
        borderInlineStart: '2px solid rgba(136,166,255,0.24)',
      }
    }
    if (lane === 'fcf') {
      return {
        ...base,
        marginTop: 6,
        paddingTop: 10,
        paddingBottom: 10,
        borderTop: '1px solid rgba(255,255,255,0.12)',
        background: 'linear-gradient(90deg, rgba(63,185,80,0.1) 0%, transparent 55%)',
        borderInlineStart: '3px solid rgba(63,185,80,0.55)',
      }
    }
  }
  if (rowKind === 'source') {
    return {
      ...base,
      background: 'rgba(255,255,255,0.012)',
      borderInlineStart: '1px solid rgba(196,204,214,0.08)',
    }
  }
  return base
}

/** Typography / emphasis tier — independent from backend `leaf` flag (structural rows may have no children). */
function computeTier(statementKind, lane, rowKind, hasKids) {
  if (rowKind === 'source') return 'ledger'
  if (statementKind === 'income') {
    if (lane === 'net') return 'total'
    if (lane === 'profit') return 'emphasis'
    if (lane === 'is_total' || lane === 'subtotal') return 'subtotal'
    if (lane === 'section') return 'section'
    return 'structural'
  }
  if (statementKind === 'balance') {
    if (lane === 'wc') return 'total'
    if (lane === 'pillar' && hasKids) return 'section'
    if (lane === 'split') return 'split'
    return 'structural'
  }
  if (statementKind === 'cash') {
    if (lane === 'fcf') return 'total'
    if (lane === 'ocf' && hasKids) return 'section'
    return 'structural'
  }
  return 'structural'
}

function labelStyle(lane, depth, labelLeaf, statementKind, tier) {
  const d = Number(depth) || 0
  let size = d >= 3 ? 11 : 12
  let weight = labelLeaf ? 400 : 600
  let color = labelLeaf ? 'rgba(196,204,214,0.82)' : 'rgba(232,236,244,0.95)'
  if (tier === 'ledger') {
    size = d >= 3 ? 10.5 : 11
    weight = 400
    color = 'rgba(176,184,194,0.72)'
  }
  if (tier === 'section' && !labelLeaf) {
    size = Math.max(size, 12.75)
    weight = 780
    color = '#f3f6fb'
  }
  if (tier === 'subtotal' && !labelLeaf) {
    size = Math.max(size, 12.25)
    weight = 740
    color = 'rgba(240,244,250,0.98)'
  }
  if (tier === 'split' && !labelLeaf) {
    weight = 660
    color = 'rgba(229,235,244,0.93)'
  }
  if (statementKind === 'income' && lane === 'net') {
    size = 13.5
    weight = 800
    color = '#fff'
  }
  if (statementKind === 'income' && lane === 'profit') {
    size = 12.5
    weight = 800
    color = '#fff'
  }
  if (statementKind === 'income' && lane === 'is_total') {
    size = 12
    weight = 720
    color = 'rgba(232,240,255,0.98)'
  }
  if (statementKind === 'balance' && lane === 'wc') {
    size = 12.5
    weight = 800
    color = '#f0e6d2'
  }
  if (statementKind === 'cash' && lane === 'ocf' && d <= 1) {
    weight = 800
    color = '#fff'
  }
  return {
    fontSize: size,
    fontWeight: weight,
    color,
    letterSpacing: tier === 'ledger' ? '0.01em' : 'normal',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  }
}

function valueStyle(lane, labelLeaf, statementKind, tier) {
  const mono = {
    fontFamily: 'var(--font-mono, ui-monospace, monospace)',
    direction: 'ltr',
    textAlign: 'right',
    fontVariantNumeric: 'tabular-nums',
  }
  let size = labelLeaf ? 11.5 : 12.5
  let weight = labelLeaf ? 500 : 650
  let color = 'rgba(232,236,244,0.92)'
  if (tier === 'ledger') {
    size = 10.75
    weight = 500
    color = 'rgba(186,194,204,0.8)'
  }
  if (tier === 'subtotal' && !labelLeaf) {
    size = 13.25
    weight = 760
    color = '#f2f5fa'
  }
  if (statementKind === 'income' && lane === 'net') {
    size = 14.5
    weight = 800
    color = '#fff'
  }
  if (statementKind === 'income' && lane === 'profit') {
    size = 13.25
    weight = 800
  }
  if (statementKind === 'income' && lane === 'is_total') {
    size = 12.75
    weight = 720
  }
  if (statementKind === 'balance' && lane === 'wc') {
    size = 13.25
    weight = 800
    color = '#f5ebd4'
  }
  if (statementKind === 'cash' && lane === 'ocf') {
    weight = 800
  }
  if (statementKind === 'cash' && lane === 'fcf' && !labelLeaf) {
    size = 13.25
    weight = 800
  }
  return { ...mono, fontSize: size, fontWeight: weight, color }
}

function provenanceBadgeStyle(provenance) {
  const background =
    provenance === 'synthetic_injected'
      ? 'rgba(210,168,75,0.22)'
      : provenance === 'merged_source_leaf'
        ? 'rgba(88,166,255,0.18)'
        : 'rgba(255,255,255,0.08)'
  return {
    display: 'inline-flex',
    alignItems: 'center',
    marginInlineStart: 8,
    padding: '1px 6px',
    borderRadius: 999,
    border: '1px solid rgba(255,255,255,0.1)',
    background,
    color: 'rgba(196,204,214,0.72)',
    fontSize: 9,
    fontWeight: 700,
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
    flexShrink: 0,
  }
}

function StmtHierRow({ node, tr, lang, defaultOpen = false, statementKind }) {
  const kids = Array.isArray(node?.children) ? node.children.filter((x) => x && typeof x === 'object') : []
  const hasKids = kids.length > 0
  const { text: lbl, rowKind } = resolveStatementHierarchyRowLabel(node, tr, lang)
  const rowClass = rowKind === 'structural' ? 'stmt-row--structural' : 'stmt-row--source'
  const val = node?.value
  const depth = Number(node?.depth) || 0
  const pad = 16 + depth * 18
  const labelLeaf = rowKind === 'source'
  const provenance = typeof node?.provenance === 'string' ? node.provenance : ''
  const provenanceText = resolveStatementHierarchyBadgeLabel(provenance, tr, lang)
  const noteText = resolveStatementHierarchyNote(node, tr, lang)

  let lane = 'line'
  if (statementKind === 'income') lane = incomeRowLane(node || {})
  else if (statementKind === 'balance') lane = balanceRowLane(node || {})
  else lane = cashRowLane(node || {})

  const tier = computeTier(statementKind, lane, rowKind, hasKids)
  const tierClass = `stmt-tier-${tier}`

  const wrapSx = laneStyle(lane, { hasKids, statementKind, rowKind })

  if (!hasKids) {
    return (
      <div
        className={`stmt-premium-grid ${rowClass} ${tierClass}`}
        style={{
          ...wrapSx,
          padding: `7px 14px 7px ${pad}px`,
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', minWidth: 0 }}>
          <span style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
            <span className="stmt-row-label-cell" style={labelStyle(lane, depth, labelLeaf, statementKind, tier)}>
              {lbl}
            </span>
            {noteText ? <span className="stmt-row-note">{noteText}</span> : null}
          </span>
          {provenanceText ? <span style={provenanceBadgeStyle(provenance)}>{provenanceText}</span> : null}
        </span>
        <span style={valueStyle(lane, labelLeaf, statementKind, tier)}>{fmt(val, lang)}</span>
      </div>
    )
  }

  return (
    <details open={defaultOpen} className="stmt-premium" style={wrapSx}>
      <summary
        className={`stmt-premium-grid ${rowClass} ${tierClass}`}
        style={{
          cursor: 'pointer',
          padding: `9px 14px 9px ${pad}px`,
          listStyle: 'none',
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', minWidth: 0 }}>
          <span className="stmt-chevron" aria-hidden>
            ▶
          </span>
          <span style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
            <span className="stmt-row-label-cell" style={labelStyle(lane, depth, false, statementKind, tier)}>
              {lbl}
            </span>
            {noteText ? <span className="stmt-row-note">{noteText}</span> : null}
          </span>
          {provenanceText ? <span style={provenanceBadgeStyle(provenance)}>{provenanceText}</span> : null}
        </span>
        <span style={valueStyle(lane, false, statementKind, tier)}>
          {val != null && val !== '' ? fmt(val, lang) : ''}
        </span>
      </summary>
      <div className="stmt-hier-children">
        {kids.map((ch, idx) => (
          <StmtHierRow
            key={String(ch.key ?? ch.label ?? idx)}
            node={ch}
            tr={tr}
            lang={lang}
            defaultOpen={false}
            statementKind={statementKind}
          />
        ))}
      </div>
    </details>
  )
}

function WorkspaceChrome({ title, tr, children }) {
  return (
    <div
      className="stmt-premium"
      style={{
        borderRadius: 12,
        border: '1px solid rgba(255,255,255,0.08)',
        background: 'linear-gradient(165deg, rgba(22,27,34,0.98) 0%, rgba(13,17,23,0.99) 100%)',
        boxShadow: '0 24px 48px rgba(0,0,0,0.35)',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          padding: '14px 20px 12px',
          borderBottom: '1px solid rgba(255,255,255,0.07)',
          display: 'flex',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          gap: 12,
        }}
      >
        <span
          style={{
            fontSize: 11,
            fontWeight: 800,
            letterSpacing: '0.11em',
            textTransform: 'uppercase',
            color: 'rgba(196,204,214,0.55)',
          }}
        >
          {title}
        </span>
      </div>
      <div
        className="stmt-premium-grid"
        style={{
          padding: '8px 20px',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          background: 'rgba(0,0,0,0.2)',
        }}
      >
        <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.12em', color: 'rgba(196,204,214,0.45)' }}>
          {tr('stmt_workspace_line')}
        </span>
        <span
          style={{
            fontSize: 9,
            fontWeight: 700,
            letterSpacing: '0.12em',
            color: 'rgba(196,204,214,0.45)',
            textAlign: 'right',
          }}
        >
          {tr('stmt_workspace_amount')}
        </span>
      </div>
      <div style={{ padding: '4px 0 8px' }}>{children}</div>
    </div>
  )
}

export function StatementHierarchyTree({ root, tr, lang, mode }) {
  if (!root) return null
  const title = resolveStatementHierarchyRootTitle(root, tr, lang)
  const children = Array.isArray(root.children) ? root.children.filter((x) => x && typeof x === 'object') : []

  if (mode === 'balance') {
    const byKey = {}
    for (const c of children) {
      if (c && typeof c.key === 'string') byKey[c.key] = c
    }
    const groups = [
      { section: 'stmt_bs_section_assets', keys: ['assets', 'current_assets', 'noncurrent_assets'] },
      { section: 'stmt_bs_section_liabilities', keys: ['liabilities', 'current_liabilities', 'noncurrent_liabilities'] },
      { section: 'stmt_bs_section_equity', keys: ['equity'] },
      { section: 'stmt_bs_section_wc', keys: ['working_capital'] },
    ]
    return (
      <WorkspaceChrome title={title} tr={tr}>
        {groups.map((g) => (
          <div key={g.section} className="stmt-bs-group" style={{ marginBottom: 6 }}>
            <div className="stmt-bs-section-heading">{tr(g.section)}</div>
            <div style={{ padding: '0 8px' }}>
              {g.keys.map((k) => {
                const node = byKey[k]
                if (!node) return null
                return (
                  <StmtHierRow
                    key={k}
                    node={node}
                    tr={tr}
                    lang={lang}
                    defaultOpen={k === 'assets' || k === 'liabilities' || k === 'equity'}
                    statementKind="balance"
                  />
                )
              })}
            </div>
          </div>
        ))}
      </WorkspaceChrome>
    )
  }

  /* income */
  return (
    <WorkspaceChrome title={title} tr={tr}>
      {children.map((ch, idx) => (
        <StmtHierRow
          key={String(ch.key ?? ch.label ?? idx)}
          node={ch}
          tr={tr}
          lang={lang}
          defaultOpen={ch?.key === 'revenue'}
          statementKind="income"
        />
      ))}
    </WorkspaceChrome>
  )
}

/** Cash flow block from statement_hierarchy.cashflow — no inferred lines. */
export function StatementCashOperatingTree({ cashflowRoot, tr, lang }) {
  const kids = Array.isArray(cashflowRoot?.children) ? cashflowRoot.children.filter((x) => x && typeof x === 'object') : []
  if (!cashflowRoot || kids.length === 0) return null
  const rootTitle = resolveStatementHierarchyRootTitle(cashflowRoot, tr, lang)
  return (
    <WorkspaceChrome title={rootTitle} tr={tr}>
      <div style={{ padding: '0 8px' }}>
        {kids.map((node, idx) => (
          <StmtHierRow
            key={String(node.key ?? node.label ?? idx)}
            node={node}
            tr={tr}
            lang={lang}
            defaultOpen={node?.key === 'cf_operating' || node?.key === 'cf_investing' || node?.key === 'cf_financing'}
            statementKind="cash"
          />
        ))}
      </div>
    </WorkspaceChrome>
  )
}

/** True only from hierarchy nodes — no cashflow engine payload. */
export function cashHierarchyHasOperatingData(cfRoot) {
  if (!cfRoot || !Array.isArray(cfRoot.children)) return false
  const op = cfRoot.children.find((c) => c.key === 'cf_operating')
  if (!op) return false
  if (op.value != null && op.value !== '' && Number.isFinite(Number(op.value))) return true
  return (op.children || []).some((ch) => ch.value != null && ch.value !== '')
}
