/**
 * Drill-down tree for statement_hierarchy (Phase 4) — same bundle as /executive root.
 */
import React from 'react'
import { formatCompactForLang } from '../utils/numberFormat.js'

function StmtHierRow({ node, tr, lang, defaultOpen = false }) {
  const kids = node.children || []
  const hasKids = kids.length > 0
  const lbl = node.label_key ? tr(node.label_key) : node.label
  const val = node.value
  const pad = 10 + (Number(node.depth) || 0) * 12
  const mono = {
    fontFamily: 'var(--font-mono)',
    fontSize: 12,
    direction: 'ltr',
    textAlign: 'right',
  }
  if (!hasKids) {
    return (
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 100px',
          gap: 8,
          padding: `4px 0 4px ${pad}px`,
          borderBottom: '1px solid var(--border)',
        }}
      >
        <span
          style={{
            fontSize: 11,
            color: node.leaf ? 'var(--text-secondary)' : 'var(--text-primary)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {lbl}
        </span>
        <span style={{ ...mono, color: 'var(--text-primary)' }}>
          {val != null ? formatCompactForLang(val, lang) : '—'}
        </span>
      </div>
    )
  }
  return (
    <details open={defaultOpen} style={{ borderBottom: '1px solid var(--border)' }}>
      <summary
        style={{
          cursor: 'pointer',
          listStyle: 'none',
          display: 'grid',
          gridTemplateColumns: '1fr 100px',
          gap: 8,
          padding: `6px 0 6px ${pad}px`,
          fontWeight: 700,
          fontSize: 12,
        }}
      >
        <span>{lbl}</span>
        <span style={mono}>{val != null ? formatCompactForLang(val, lang) : ''}</span>
      </summary>
      <div>
        {kids.map((ch) => (
          <StmtHierRow key={ch.key} node={ch} tr={tr} lang={lang} defaultOpen={false} />
        ))}
      </div>
    </details>
  )
}

export function StatementHierarchyTree({ root, tr, lang, titleKey = 'stmt_hier_panel_title' }) {
  if (!root) return null
  return (
    <div style={{ marginTop: 12 }}>
      {titleKey ? (
        <div
          style={{
            fontSize: 10,
            fontWeight: 800,
            color: 'var(--text-secondary)',
            textTransform: 'uppercase',
            letterSpacing: '.06em',
            marginBottom: 8,
          }}
        >
          {tr(titleKey)}
        </div>
      ) : null}
      <StmtHierRow node={root} tr={tr} lang={lang} defaultOpen />
    </div>
  )
}
