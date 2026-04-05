/**
 * Surfaces canonical structured P&L layers from executive / analysis payloads:
 * structured_income_statement, variance, margin variance, profit bridge, profit story.
 */
import { Fragment } from 'react'
import {
  formatCompactForLang,
  formatPctForLang,
  formatSignedPctForLang,
  formatPpForLang,
  formatCompactSignedForLang,
} from '../utils/numberFormat.js'
import CommandCenterMiniPnlFlow from './CommandCenterMiniPnlFlow.jsx'
import { storyParagraphContent } from '../utils/arabicFinancialStoryText.jsx'
import { normalizeUiLang } from '../utils/strictI18n.js'

const CARD_STYLE = {
  background: 'var(--bg-panel)',
  borderRadius: 13,
  padding: '16px 18px',
  borderTop: '2px solid var(--border)',
  marginBottom: 0,
}

const H2 = {
  fontSize: 11,
  fontWeight: 800,
  letterSpacing: '.08em',
  textTransform: 'uppercase',
  color: 'var(--text-secondary)',
  margin: '0 0 12px',
}

function localizeStoryParams(tr, params) {
  if (!params || typeof params !== 'object') return params || {}
  const p = { ...params }
  const d = String(p.primary_driver || '').toLowerCase()
  if (d === 'n/a') {
    p.primary_driver = tr('sfl_driver_n/a')
  } else if (d && ['revenue', 'cogs', 'opex', 'mixed'].includes(d)) {
    p.primary_driver = tr(`sfl_driver_${d}`)
  }
  return p
}

function storyLine(tr, key, params) {
  if (!key) return ''
  return tr(key, localizeStoryParams(tr, params))
}

function fmtMoney(v, lang) {
  if (v == null || (typeof v === 'number' && !Number.isFinite(v))) return '—'
  return formatCompactForLang(v, lang)
}

function fmtDeltaMoney(v, lang) {
  if (v == null || (typeof v === 'number' && !Number.isFinite(v))) return '—'
  return formatCompactSignedForLang(v, lang)
}

const IS_ROWS = [
  { field: 'revenue', labelKey: 'sfl_row_revenue', margin: false },
  { field: 'cogs', labelKey: 'sfl_row_cogs', margin: false },
  { field: 'gross_profit', labelKey: 'sfl_row_gross_profit', margin: false },
  { field: 'gross_margin_pct', labelKey: 'sfl_row_gross_margin_pct', margin: true },
  { field: 'opex', labelKey: 'sfl_row_opex', margin: false },
  { field: 'operating_profit', labelKey: 'sfl_row_operating_profit', margin: false },
  { field: 'operating_margin_pct', labelKey: 'sfl_row_operating_margin_pct', margin: true },
  { field: 'net_profit', labelKey: 'sfl_row_net_profit', margin: false },
  { field: 'net_margin_pct', labelKey: 'sfl_row_net_margin_pct', margin: true },
]

const VAR_LINE_KEYS = [
  'revenue',
  'cogs',
  'gross_profit',
  'opex',
  'operating_profit',
  'net_profit',
]

const VAR_LABEL_KEYS = {
  revenue: 'sfl_row_revenue',
  cogs: 'sfl_row_cogs',
  gross_profit: 'sfl_row_gross_profit',
  opex: 'sfl_row_opex',
  operating_profit: 'sfl_row_operating_profit',
  net_profit: 'sfl_row_net_profit',
}

const MARGIN_VAR_KEYS = ['gross_margin_pct', 'operating_margin_pct', 'net_margin_pct']

const MARGIN_LABEL_KEYS = {
  gross_margin_pct: 'sfl_row_gross_margin_pct',
  operating_margin_pct: 'sfl_row_operating_margin_pct',
  net_margin_pct: 'sfl_row_net_margin_pct',
}

const MONO = 'sfl-mono'
const MONO_SOFT = 'sfl-mono sfl-mono--soft'
const ROW_LBL = 'sfl-row-label'

/** Ordered bridge keys (revenue → cogs → opex → operating → net). */
const BRIDGE_KEYS = [
  { bridgeKey: 'revenue_change', labelKey: 'sfl_bridge_revenue' },
  { bridgeKey: 'cogs_change', labelKey: 'sfl_bridge_cogs' },
  { bridgeKey: 'opex_change', labelKey: 'sfl_bridge_opex' },
  { bridgeKey: 'operating_profit_change', labelKey: 'sfl_bridge_operating' },
  { bridgeKey: 'net_profit_change', labelKey: 'sfl_bridge_net' },
]

function VarianceTable({ variance, tr, lang }) {
  if (!variance || typeof variance !== 'object') return null
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
        <thead>
          <tr style={{ color: 'var(--text-secondary)', textAlign: 'left' }}>
            <th style={{ padding: '6px 8px 8px 0', fontWeight: 700 }}>{tr('sfl_col_line')}</th>
            <th style={{ padding: '6px 8px', fontWeight: 700 }}>{tr('sfl_col_current')}</th>
            <th style={{ padding: '6px 8px', fontWeight: 700 }}>{tr('sfl_col_previous')}</th>
            <th style={{ padding: '6px 8px', fontWeight: 700 }}>{tr('sfl_col_delta')}</th>
            <th style={{ padding: '6px 0 8px 8px', fontWeight: 700 }}>{tr('sfl_col_delta_pct')}</th>
          </tr>
        </thead>
        <tbody>
          {VAR_LINE_KEYS.map((k) => {
            const row = variance[k] || {}
            return (
              <tr key={k} style={{ borderTop: '1px solid var(--border)' }}>
                <td style={{ padding: '7px 8px 7px 0', color: 'var(--text-secondary)' }}>
                  {tr(VAR_LABEL_KEYS[k])}
                </td>
                <td className={MONO} style={{ padding: '7px 8px', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                  {fmtMoney(row.current, lang)}
                </td>
                <td className={MONO} style={{ padding: '7px 8px', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                  {fmtMoney(row.previous, lang)}
                </td>
                <td className={MONO} style={{ padding: '7px 8px', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                  {fmtDeltaMoney(row.delta, lang)}
                </td>
                <td className={MONO} style={{ padding: '7px 0 7px 8px', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                  {row.delta_pct != null && Number.isFinite(Number(row.delta_pct))
                    ? formatSignedPctForLang(Number(row.delta_pct), 1, lang)
                    : '—'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function MarginVarianceTable({ marginVar, tr, lang, showTitle = true }) {
  if (!marginVar || typeof marginVar !== 'object') return null
  return (
    <div style={{ overflowX: 'auto', marginTop: showTitle ? 12 : 0 }}>
      {showTitle ? <div style={{ ...H2, marginBottom: 8 }}>{tr('sfl_title_margin_var')}</div> : null}
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
        <thead>
          <tr style={{ color: 'var(--text-secondary)', textAlign: 'left' }}>
            <th style={{ padding: '6px 8px 8px 0', fontWeight: 700 }}>{tr('sfl_col_line')}</th>
            <th style={{ padding: '6px 8px', fontWeight: 700 }}>{tr('sfl_col_current')}</th>
            <th style={{ padding: '6px 8px', fontWeight: 700 }}>{tr('sfl_col_previous')}</th>
            <th style={{ padding: '6px 0 8px 8px', fontWeight: 700 }}>{tr('sfl_col_delta_pp')}</th>
          </tr>
        </thead>
        <tbody>
          {MARGIN_VAR_KEYS.map((k) => {
            const row = marginVar[k] || {}
            return (
              <tr key={k} style={{ borderTop: '1px solid var(--border)' }}>
                <td style={{ padding: '7px 8px 7px 0', color: 'var(--text-secondary)' }}>
                  {tr(MARGIN_LABEL_KEYS[k])}
                </td>
                <td className={MONO} style={{ padding: '7px 8px', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                  {row.current != null ? formatPctForLang(row.current, 1, lang) : '—'}
                </td>
                <td className={MONO} style={{ padding: '7px 8px', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                  {row.previous != null ? formatPctForLang(row.previous, 1, lang) : '—'}
                </td>
                <td className={MONO} style={{ padding: '7px 0 7px 8px', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                  {row.delta_pp != null && Number.isFinite(Number(row.delta_pp))
                    ? formatPpForLang(Number(row.delta_pp), 1, lang)
                    : '—'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function VarianceSummaryList({ variance, tr, lang }) {
  if (!variance || typeof variance !== 'object') return null
  return (
    <ul className="sfl-var-list" style={{ listStyle: 'none', padding: 0, margin: 0, fontSize: 12, lineHeight: 1.55 }}>
      {VAR_LINE_KEYS.map((k) => {
        const row = variance[k] || {}
        const d = row.delta
        const dp = row.delta_pct
        return (
          <li
            key={k}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              gap: 12,
              padding: '8px 0',
              borderBottom: '1px solid var(--border)',
            }}
          >
            <span className={ROW_LBL} style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>
              {tr(VAR_LABEL_KEYS[k])}
            </span>
            <span className={MONO} style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, textAlign: 'right' }}>
              {fmtDeltaMoney(d, lang)}
              {dp != null && Number.isFinite(Number(dp)) ? (
                <span className={MONO_SOFT} style={{ color: 'var(--text-muted)', fontWeight: 600, marginLeft: 8 }}>
                  ({formatSignedPctForLang(Number(dp), 1, lang)})
                </span>
              ) : null}
            </span>
          </li>
        )
      })}
    </ul>
  )
}

function MarginSummaryStrip({ marginVar, tr, lang }) {
  if (!marginVar || typeof marginVar !== 'object') return null
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
      {MARGIN_VAR_KEYS.map((k) => {
        const row = marginVar[k] || {}
        return (
          <div
            key={k}
            style={{
              flex: '1 1 120px',
              background: 'rgba(255,255,255,0.03)',
              borderRadius: 10,
              padding: '10px 12px',
              border: '1px solid var(--border)',
            }}
          >
            <div
              className="sfl-margin-strip-label"
              style={{
                fontSize: 9,
                fontWeight: 800,
                color: 'var(--text-muted)',
                textTransform: 'uppercase',
                letterSpacing: '.06em',
              }}
            >
              {tr(MARGIN_LABEL_KEYS[k])}
            </div>
            <div
              className={MONO}
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 14,
                fontWeight: 800,
                direction: 'ltr',
                marginTop: 4,
              }}
            >
              {row.current != null ? formatPctForLang(row.current, 1, lang) : '—'}
            </div>
            {row.delta_pp != null && Number.isFinite(Number(row.delta_pp)) ? (
              <div
                className={MONO}
                style={{
                  fontSize: 10,
                  color: Number(row.delta_pp) >= 0 ? 'var(--green)' : 'var(--red)',
                  marginTop: 4,
                  fontFamily: 'var(--font-mono)',
                }}
              >
                {formatPpForLang(Number(row.delta_pp), 1, lang)}
              </div>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}

function BridgeBlock({ bridge, tr, lang }) {
  if (!bridge || typeof bridge !== 'object') return null
  return (
    <ul className="sfl-bridge-list" style={{ listStyle: 'none', padding: 0, margin: 0, fontSize: 12, lineHeight: 1.55 }}>
      {BRIDGE_KEYS.map(({ bridgeKey, labelKey }) => {
        const blk = bridge[bridgeKey] || {}
        const d = blk.delta
        const dp = blk.delta_pct
        return (
          <li
            key={bridgeKey}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              gap: 12,
              padding: '8px 0',
              borderBottom: '1px solid var(--border)',
            }}
          >
            <span className={ROW_LBL} style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>
              {tr(labelKey)}
            </span>
            <span className={MONO} style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, textAlign: 'right' }}>
              {fmtDeltaMoney(d, lang)}
              {dp != null && Number.isFinite(Number(dp)) ? (
                <span className={MONO_SOFT} style={{ color: 'var(--text-muted)', fontWeight: 600, marginLeft: 8 }}>
                  ({formatSignedPctForLang(Number(dp), 1, lang)})
                </span>
              ) : null}
            </span>
          </li>
        )
      })}
    </ul>
  )
}

function ProfitStoryBlock({ story, tr, lang, compact, visualBlocks }) {
  if (!story || !story.what_changed_key) return null
  const st = story.summary_type
  const what = storyLine(tr, story.what_changed_key, story.what_changed_params)
  const why = storyLine(tr, story.why_key, story.why_params)
  const act = storyLine(tr, story.action_key, story.action_params)
  const isAr = normalizeUiLang(lang) === 'ar'
  const labelStyle = {
    fontSize: compact ? 9 : 10,
    fontWeight: 800,
    color: 'var(--accent)',
    textTransform: 'uppercase',
    letterSpacing: '.06em',
    marginBottom: 4,
    marginTop: compact ? (isAr ? 12 : 8) : isAr ? 14 : 10,
  }
  const textStyle = {
    fontSize: compact ? 12 : 13,
    color: 'var(--text-secondary)',
    lineHeight: isAr ? 1.62 : 1.55,
    margin: 0,
    fontWeight: isAr ? 400 : 500,
  }
  const storyP = (line) => (
    <p
      className={isAr ? 'cmd-magic-story-block__t ar-fin-story-body' : 'cmd-magic-story-block__t'}
    >
      {storyParagraphContent(line, lang)}
    </p>
  )
  if (visualBlocks) {
    return (
      <div className="cmd-magic-story-body">
        {st ? <div className="cmd-magic-summary-badge">{tr(`sfl_summary_${st}`)}</div> : null}
        <div className="cmd-magic-story-block">
          <div className="cmd-magic-story-block__k">{tr('sfl_story_what')}</div>
          {storyP(what)}
        </div>
        <div className="cmd-magic-story-block">
          <div className="cmd-magic-story-block__k">{tr('sfl_story_why')}</div>
          {storyP(why)}
        </div>
        <div className="cmd-magic-story-block">
          <div className="cmd-magic-story-block__k">{tr('sfl_story_action')}</div>
          {storyP(act)}
        </div>
      </div>
    )
  }
  return (
    <div>
      {st ? (
        <div
          style={{
            display: 'inline-block',
            fontSize: 10,
            fontWeight: 800,
            letterSpacing: isAr ? '0.05em' : '.06em',
            textTransform: 'uppercase',
            padding: '4px 10px',
            borderRadius: 8,
            background: 'rgba(0,212,170,0.12)',
            color: 'var(--accent)',
            marginBottom: isAr ? 12 : 10,
          }}
        >
          {tr(`sfl_summary_${st}`)}
        </div>
      ) : null}
      <div style={labelStyle}>{tr('sfl_story_what')}</div>
      <p style={{ ...textStyle, marginTop: 0 }} className={isAr ? 'ar-fin-story-plain' : undefined}>
        {storyParagraphContent(what, lang)}
      </p>
      <div style={labelStyle}>{tr('sfl_story_why')}</div>
      <p style={textStyle} className={isAr ? 'ar-fin-story-plain' : undefined}>
        {storyParagraphContent(why, lang)}
      </p>
      <div style={labelStyle}>{tr('sfl_story_action')}</div>
      <p style={textStyle} className={isAr ? 'ar-fin-story-plain' : undefined}>
        {storyParagraphContent(act, lang)}
      </p>
    </div>
  )
}

/**
 * @param {object} props
 * @param {Record<string, unknown>} props.data — executive `data` or analysis dict with structured keys
 * @param {(k: string, p?: object) => string} props.tr
 * @param {string} props.lang
 * @param {'full' | 'command' | 'story_only' | 'board' | 'board_executive' | 'analysis_spine' | 'statements_formal_variance' | 'statements_interpretation' | 'statements_margin_section'} props.variant
 */
export default function StructuredFinancialLayers({ data, tr, lang, variant = 'full' }) {
  if (!data || typeof data !== 'object') return null

  const sis = data.structured_income_statement
  const svar = data.structured_income_statement_variance
  const smvar = data.structured_income_statement_margin_variance
  const bridge = data.structured_profit_bridge
  const story = data.structured_profit_story
  const meta = data.structured_income_statement_variance_meta

  if (variant === 'analysis_spine') {
    const hasSpine =
      (sis && Object.keys(sis).length) ||
      (svar && Object.keys(svar).length) ||
      (smvar && Object.keys(smvar).length) ||
      (bridge && Object.keys(bridge).length) ||
      Boolean(story?.what_changed_key)
    if (!hasSpine) return null

    const spineDivider = (
      <div
        role="separator"
        style={{ height: 1, background: 'rgba(148,163,184,0.14)', margin: '16px 0' }}
      />
    )

    const detailsStyle = {
      marginTop: 12,
      borderRadius: 10,
      border: '1px solid var(--border)',
      background: 'rgba(255,255,255,0.02)',
      padding: '8px 12px',
    }
    const summaryStyle = {
      cursor: 'pointer',
      fontSize: 11,
      fontWeight: 700,
      color: 'var(--text-secondary)',
      listStyle: 'none',
    }

    const segments = []
    if (sis && typeof sis === 'object') {
      segments.push({
        key: 'is',
        el: (
          <div>
          <div style={{ ...H2, marginTop: 0 }}>{tr('sfl_title_is')}</div>
          <CommandCenterMiniPnlFlow data={data} tr={tr} lang={lang} titleKey="analysis_spine_flow_caption" />
          <details style={detailsStyle}>
            <summary style={summaryStyle}>{tr('analysis_spine_detail_tables')}</summary>
            <div style={{ marginTop: 10 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                <tbody>
                  {IS_ROWS.map(({ field, labelKey, margin }) => {
                    const v = sis[field]
                    return (
                      <tr key={field} style={{ borderTop: '1px solid var(--border)' }}>
                        <td className={ROW_LBL} style={{ padding: '7px 8px 7px 0', color: 'var(--text-secondary)' }}>
                          {tr(labelKey)}
                        </td>
                        <td
                          className={MONO}
                          style={{
                            padding: '7px 0',
                            fontFamily: 'var(--font-mono)',
                            fontWeight: 700,
                            textAlign: 'right',
                          }}
                        >
                          {margin
                            ? v != null && Number.isFinite(Number(v))
                              ? formatPctForLang(Number(v), 1, lang)
                              : '—'
                            : fmtMoney(v, lang)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </details>
          </div>
        ),
      })
    }
    if (svar && typeof svar === 'object') {
      segments.push({
        key: 'var',
        el: (
          <div>
          <div style={{ ...H2, marginTop: 0 }}>{tr('sfl_title_var')}</div>
          {meta?.latest_period != null && meta?.previous_period != null && (
            <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '0 0 10px' }}>
              {tr('sfl_period_compare', { from: meta.previous_period, to: meta.latest_period })}
            </p>
          )}
          <VarianceSummaryList variance={svar} tr={tr} lang={lang} />
          <details style={detailsStyle}>
            <summary style={summaryStyle}>{tr('analysis_spine_detail_tables')}</summary>
            <div style={{ marginTop: 10 }}>
              <VarianceTable variance={svar} tr={tr} lang={lang} />
            </div>
          </details>
          </div>
        ),
      })
    }
    if (smvar && typeof smvar === 'object') {
      segments.push({
        key: 'mvar',
        el: (
          <div>
          <div style={{ ...H2, marginTop: 0 }}>{tr('sfl_title_margin_var')}</div>
          <MarginSummaryStrip marginVar={smvar} tr={tr} lang={lang} />
          <details style={detailsStyle}>
            <summary style={summaryStyle}>{tr('analysis_spine_detail_tables')}</summary>
            <div style={{ marginTop: 10 }}>
              <MarginVarianceTable marginVar={smvar} tr={tr} lang={lang} showTitle={false} />
            </div>
          </details>
          </div>
        ),
      })
    }
    if (bridge && typeof bridge === 'object') {
      segments.push({
        key: 'bridge',
        el: (
          <div>
          <div style={{ ...H2, marginTop: 0 }}>{tr('sfl_title_bridge')}</div>
          <BridgeBlock bridge={bridge} tr={tr} lang={lang} />
          </div>
        ),
      })
    }
    if (story?.what_changed_key) {
      segments.push({
        key: 'story',
        el: (
          <div>
          <div style={{ ...H2, marginTop: 0 }}>{tr('sfl_title_story')}</div>
          <ProfitStoryBlock story={story} tr={tr} lang={lang} compact={false} />
          </div>
        ),
      })
    }

    return (
      <div
        className="analysis-financial-spine"
        style={{
          ...CARD_STYLE,
          borderTop: '2px solid rgba(0,212,170,0.38)',
          display: 'flex',
          flexDirection: 'column',
          gap: 0,
        }}
      >
        <div style={{ ...H2, color: 'var(--accent)', marginBottom: 4 }}>{tr('analysis_spine_title')}</div>
        <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '0 0 12px', lineHeight: 1.45 }}>
          {tr('analysis_spine_subtitle')}
        </p>
        {segments.map(({ key, el }, i) => (
          <Fragment key={key}>
            {i > 0 ? spineDivider : null}
            {el}
          </Fragment>
        ))}
      </div>
    )
  }

  if (variant === 'command') {
    if (!story?.what_changed_key) return null
    return (
      <div
        className="cmd-financial-story-lead cmd-magic-story-shell cmd-os-story"
        style={{ ...CARD_STYLE, borderTop: '2px solid rgba(0,212,170,0.35)' }}
      >
        <div className="cmd-magic-story-h2">{tr('sfl_title_story')}</div>
        <ProfitStoryBlock story={story} tr={tr} lang={lang} compact visualBlocks />
      </div>
    )
  }

  /** Board Report — story + profit bridge only; presentation scan order (narrative → mechanics). */
  if (variant === 'board_executive') {
    const hasStory = Boolean(story?.what_changed_key)
    const hasBridge = bridge && typeof bridge === 'object' && Object.keys(bridge).length > 0
    if (!hasStory && !hasBridge) return null
    return (
      <div className="board-exec-sfl">
        {hasStory ? (
          <div className="board-exec-sfl__block">
            <div className="board-exec-sfl__heading">{tr('sfl_title_story')}</div>
            <ProfitStoryBlock story={story} tr={tr} lang={lang} compact visualBlocks />
          </div>
        ) : null}
        {hasBridge ? (
          <div className={`board-exec-sfl__block${hasStory ? ' board-exec-sfl__block--bridge' : ''}`.trim()}>
            <div className="board-exec-sfl__heading board-exec-sfl__heading--bridge">{tr('sfl_title_bridge')}</div>
            <BridgeBlock bridge={bridge} tr={tr} lang={lang} />
          </div>
        ) : null}
      </div>
    )
  }

  if (variant === 'story_only' || variant === 'board') {
    if (!story?.what_changed_key) return null
    return <ProfitStoryBlock story={story} tr={tr} lang={lang} compact={variant === 'board'} />
  }

  if (variant === 'statements_formal_variance') {
    if (!svar || typeof svar !== 'object' || !Object.keys(svar).length) return null
    return (
      <div style={{ ...CARD_STYLE, marginBottom: 0, borderTop: '2px solid rgba(59,130,246,0.45)' }}>
        <div style={{ ...H2, color: 'var(--blue)' }}>{tr('stmt_formal_is_title')}</div>
        {meta?.latest_period != null && meta?.previous_period != null && (
          <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '0 0 12px' }}>
            {tr('sfl_period_compare', { from: meta.previous_period, to: meta.latest_period })}
          </p>
        )}
        <VarianceTable variance={svar} tr={tr} lang={lang} />
      </div>
    )
  }

  if (variant === 'statements_interpretation') {
    const hasAny =
      (svar && Object.keys(svar).length) ||
      (bridge && typeof bridge === 'object' && Object.keys(bridge).length) ||
      Boolean(story?.what_changed_key)
    if (!hasAny) return null
    return (
      <div style={{ ...CARD_STYLE, marginBottom: 0, borderTop: '2px solid rgba(0,212,170,0.32)' }}>
        <div style={{ ...H2, color: 'var(--accent)' }}>{tr('stmt_section_interpretation')}</div>
        {svar && Object.keys(svar).length ? (
          <>
            <div
              style={{
                fontSize: 10,
                fontWeight: 800,
                color: 'var(--text-secondary)',
                textTransform: 'uppercase',
                letterSpacing: '.07em',
                marginBottom: 8,
              }}
            >
              {tr('stmt_interp_period_deltas')}
            </div>
            <VarianceSummaryList variance={svar} tr={tr} lang={lang} />
          </>
        ) : null}
        {bridge && typeof bridge === 'object' && Object.keys(bridge).length ? (
          <>
            <div style={{ ...H2, marginTop: 14 }}>{tr('stmt_bridge_flow')}</div>
            <BridgeBlock bridge={bridge} tr={tr} lang={lang} />
          </>
        ) : null}
        {story?.what_changed_key ? (
          <>
            <div style={{ ...H2, marginTop: 14 }}>{tr('sfl_title_story')}</div>
            <ProfitStoryBlock story={story} tr={tr} lang={lang} compact />
          </>
        ) : null}
      </div>
    )
  }

  if (variant === 'statements_margin_section') {
    if (!smvar || typeof smvar !== 'object' || !Object.keys(smvar).length) return null
    return (
      <div style={{ ...CARD_STYLE, marginBottom: 0, borderTop: '2px solid rgba(139,92,246,0.35)' }}>
        <div style={{ ...H2, color: 'var(--violet)' }}>{tr('sfl_title_margin_var')}</div>
        <MarginVarianceTable marginVar={smvar} tr={tr} lang={lang} showTitle={false} />
      </div>
    )
  }

  // full (Analysis overview)
  const hasAny =
    (sis && Object.keys(sis).length) ||
    (svar && Object.keys(svar).length) ||
    (bridge && Object.keys(bridge).length) ||
    story?.what_changed_key
  if (!hasAny) return null

  return (
    <div style={{ ...CARD_STYLE, borderTop: '2px solid rgba(0,212,170,0.35)' }}>
      <div style={{ ...H2, color: 'var(--accent)' }}>{tr('sfl_section_financial_layers')}</div>

      {sis && typeof sis === 'object' ? (
        <>
          <div style={{ ...H2, marginTop: 4 }}>{tr('sfl_title_is')}</div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
            <tbody>
              {IS_ROWS.map(({ field, labelKey, margin }) => {
                const v = sis[field]
                return (
                  <tr key={field} style={{ borderTop: '1px solid var(--border)' }}>
                    <td className={ROW_LBL} style={{ padding: '7px 8px 7px 0', color: 'var(--text-secondary)' }}>
                      {tr(labelKey)}
                    </td>
                    <td
                      className={MONO}
                      style={{
                        padding: '7px 0',
                        fontFamily: 'var(--font-mono)',
                        fontWeight: 700,
                        textAlign: 'right',
                      }}
                    >
                      {margin
                        ? v != null && Number.isFinite(Number(v))
                          ? formatPctForLang(Number(v), 1, lang)
                          : '—'
                        : fmtMoney(v, lang)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </>
      ) : null}

      {svar ? (
        <>
          <div style={{ ...H2, marginTop: 16 }}>{tr('sfl_title_var')}</div>
          {meta?.latest_period != null && meta?.previous_period != null && (
            <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '0 0 8px' }}>
              {tr('sfl_period_compare', { from: meta.previous_period, to: meta.latest_period })}
            </p>
          )}
          <VarianceTable variance={svar} tr={tr} lang={lang} />
        </>
      ) : null}

      {smvar ? <MarginVarianceTable marginVar={smvar} tr={tr} lang={lang} /> : null}

      {bridge ? (
        <>
          <div style={{ ...H2, marginTop: 16 }}>{tr('sfl_title_bridge')}</div>
          <BridgeBlock bridge={bridge} tr={tr} lang={lang} />
        </>
      ) : null}

      {story?.what_changed_key ? (
        <>
          <div style={{ ...H2, marginTop: 16 }}>{tr('sfl_title_story')}</div>
          <ProfitStoryBlock story={story} tr={tr} lang={lang} compact={false} />
        </>
      ) : null}
    </div>
  )
}

/** Plain-text block for AI CFO prompt (uses same i18n keys + params). */
export function formatStructuredProfitStoryForPrompt(story, tr) {
  if (!story?.what_changed_key) return ''
  const w = storyLine(tr, story.what_changed_key, story.what_changed_params)
  const y = storyLine(tr, story.why_key, story.why_params)
  const a = storyLine(tr, story.action_key, story.action_params)
  return [w, y, a].filter(Boolean).join('\n')
}
