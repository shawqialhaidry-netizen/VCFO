/**
 * statement_hierarchy only — premium CFO workspace (Phase 4B).
 */
import React from 'react'
import { formatCompactForLang } from '../utils/numberFormat.js'
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

function laneStyle(lane, { hasKids, leaf, statementKind }) {
  const base = {
    borderBottom: '1px solid rgba(255,255,255,0.055)',
    transition: 'background 0.15s ease',
  }
  if (statementKind === 'income') {
    if (lane === 'net') {
      return {
        ...base,
        marginTop: 6,
        paddingTop: 10,
        paddingBottom: 10,
        borderTop: '1px solid rgba(255,255,255,0.12)',
        background: 'linear-gradient(90deg, rgba(63,185,80,0.16) 0%, transparent 55%)',
        borderLeft: '3px solid rgba(63,185,80,0.75)',
      }
    }
    if (lane === 'profit') {
      return {
        ...base,
        background: 'linear-gradient(90deg, rgba(88,166,255,0.1) 0%, transparent 50%)',
        borderLeft: '3px solid rgba(88,166,255,0.5)',
      }
    }
    if (lane === 'subtotal' && hasKids) {
      return { ...base, background: 'rgba(255,255,255,0.025)' }
    }
    if (lane === 'section' && hasKids) {
      return { ...base, background: 'rgba(255,255,255,0.02)' }
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
      return { ...base, background: 'rgba(255,255,255,0.035)' }
    }
    if (lane === 'split') {
      return { ...base, background: 'rgba(255,255,255,0.02)' }
    }
  }
  if (statementKind === 'cash') {
    if (lane === 'ocf' && hasKids) {
      return { ...base, background: 'rgba(255,255,255,0.04)' }
    }
    if (lane === 'fcf') {
      return {
        ...base,
        marginTop: 4,
        borderTop: '1px solid rgba(255,255,255,0.1)',
        background: 'rgba(255,255,255,0.03)',
      }
    }
  }
  if (leaf) {
    return { ...base, background: 'transparent' }
  }
  return base
}

function labelStyle(lane, depth, leaf, statementKind) {
  const d = Number(depth) || 0
  let size = d >= 3 ? 11 : 12
  let weight = leaf ? 400 : 600
  let color = leaf ? 'rgba(196,204,214,0.82)' : 'rgba(232,236,244,0.95)'
  if (statementKind === 'income' && lane === 'net') {
    size = 13
    weight = 800
    color = '#fff'
  }
  if (statementKind === 'income' && lane === 'profit') {
    size = 12
    weight = 800
    color = '#fff'
  }
  if (statementKind === 'balance' && lane === 'wc') {
    size = 12
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
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    paddingLeft: 4,
  }
}

function valueStyle(lane, leaf, statementKind) {
  const mono = {
    fontFamily: 'var(--font-mono, ui-monospace, monospace)',
    direction: 'ltr',
    textAlign: 'right',
    fontVariantNumeric: 'tabular-nums',
  }
  let size = leaf ? 11.5 : 12.5
  let weight = leaf ? 500 : 650
  let color = 'rgba(232,236,244,0.92)'
  if (statementKind === 'income' && lane === 'net') {
    size = 14
    weight = 800
    color = '#fff'
  }
  if (statementKind === 'income' && lane === 'profit') {
    size = 13
    weight = 800
  }
  if (statementKind === 'balance' && lane === 'wc') {
    size = 13
    weight = 800
    color = '#f5ebd4'
  }
  if (statementKind === 'cash' && lane === 'ocf') {
    weight = 800
  }
  return { ...mono, fontSize: size, fontWeight: weight, color }
}

function StmtHierRow({ node, tr, lang, defaultOpen = false, statementKind }) {
  const kids = Array.isArray(node.children) ? node.children : []
  const hasKids = kids.length > 0
  const lbl = node.label_key ? tr(String(node.label_key)) : String(node.label ?? '')
  const val = node.value
  const depth = Number(node.depth) || 0
  const pad = 14 + depth * 16
  const leaf = Boolean(node.leaf)

  let lane = 'line'
  if (statementKind === 'income') lane = incomeRowLane(node)
  else if (statementKind === 'balance') lane = balanceRowLane(node)
  else lane = cashRowLane(node)

  const wrapSx = laneStyle(lane, { hasKids, leaf, statementKind })

  if (!hasKids) {
    return (
      <div
        className="stmt-premium-grid"
        style={{
          ...wrapSx,
          padding: `6px 12px 6px ${pad}px`,
        }}
      >
        <span style={labelStyle(lane, depth, true, statementKind)}>{lbl}</span>
        <span style={valueStyle(lane, true, statementKind)}>{fmt(val, lang)}</span>
      </div>
    )
  }

  return (
    <details open={defaultOpen} className="stmt-premium" style={wrapSx}>
      <summary
        className="stmt-premium-grid"
        style={{
          cursor: 'pointer',
          padding: `8px 12px 8px ${pad}px`,
          listStyle: 'none',
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', minWidth: 0 }}>
          <span className="stmt-chevron" aria-hidden>
            ▶
          </span>
          <span style={labelStyle(lane, depth, false, statementKind)}>{lbl}</span>
        </span>
        <span style={valueStyle(lane, false, statementKind)}>
          {val != null && val !== '' ? fmt(val, lang) : ''}
        </span>
      </summary>
      <div style={{ paddingBottom: 2 }}>
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
  const title = root.label_key ? tr(String(root.label_key)) : String(root.label ?? '')
  const children = Array.isArray(root.children) ? root.children : []

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
          <div key={g.section} style={{ marginBottom: 4 }}>
            <div
              style={{
                padding: '10px 20px 6px',
                fontSize: 10,
                fontWeight: 800,
                letterSpacing: '0.14em',
                textTransform: 'uppercase',
                color: 'rgba(136,166,255,0.75)',
              }}
            >
              {tr(g.section)}
            </div>
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
      {children.map((ch) => (
        <StmtHierRow
          key={String(ch.key ?? ch.label)}
          node={ch}
          tr={tr}
          lang={lang}
          defaultOpen={ch.key === 'revenue'}
          statementKind="income"
        />
      ))}
    </WorkspaceChrome>
  )
}

/** Operating block from statement_hierarchy.cashflow — no inferred lines. */
export function StatementCashOperatingTree({ cashflowRoot, tr, lang }) {
  if (!cashflowRoot || !Array.isArray(cashflowRoot.children)) return null
  const operating =
    cashflowRoot.children.find((c) => c.key === 'cf_operating') || cashflowRoot.children[0]
  if (!operating) return null
  const rootTitle = cashflowRoot.label_key ? tr(String(cashflowRoot.label_key)) : String(cashflowRoot.label ?? '')
  return (
    <WorkspaceChrome title={rootTitle} tr={tr}>
      <div style={{ padding: '0 8px' }}>
        <StmtHierRow node={operating} tr={tr} lang={lang} defaultOpen statementKind="cash" />
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
