/**
 * Run buildCashBrainSnapshot + buildExecutiveNarrative on JSON payload (stdin or file).
 * Usage: node scripts/run_cash_brain_snapshot.mjs <path.json>
 */
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'
import { buildCashBrainSnapshot } from '../frontend-react/src/utils/buildCashBrainSnapshot.js'
import { buildExecutiveNarrative, factOverlapsWhy } from '../frontend-react/src/utils/buildExecutiveNarrative.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

const infile = process.argv[2] || path.join(__dirname, '..', 'tmp_cash_brain_payload.json')
const raw = fs.readFileSync(infile, 'utf8')
const data = JSON.parse(raw)

function report(lang) {
  const narrative = buildExecutiveNarrative(data, { lang })
  const snap = buildCashBrainSnapshot(
    {
      cashflow: data.cashflow,
      statements: data.statements,
      intelligence: data.intelligence,
      kpi_block: data.kpi_block,
    },
    { lang, narrative }
  )

  const narrativeLines = [
    ...(narrative.whatChanged?.lines || []),
    ...(narrative.why?.lines || []),
    ...(narrative.whatToDo?.lines || []),
  ]

  const dupes = []
  for (const b of [...(snap.pressure.bullets || []), ...(snap.liquidity.bullets || [])]) {
    if (factOverlapsWhy(narrative, b)) dupes.push({ lang, card: 'pressure|liquidity', text: b })
  }
  if (snap.survival.copy && factOverlapsWhy(narrative, snap.survival.copy)) {
    dupes.push({ lang, card: 'survival', text: snap.survival.copy })
  }

  return { lang, narrative, snap, narrativeLines, dupes }
}

const en = report('en')
const ar = report('ar')

function summarize(snap) {
  return {
    pressure: {
      tier: snap.pressure.tier,
      meaningful: snap.pressure.meaningful,
      headline: snap.pressure.headline,
      bullets: snap.pressure.bullets,
      evidenceKeys: Object.keys(snap.pressure.evidence || {}).filter(
        (k) => snap.pressure.evidence[k] != null && snap.pressure.evidence[k] !== false
      ),
    },
    liquidity: {
      tier: snap.liquidity.tier,
      meaningful: snap.liquidity.meaningful,
      headline: snap.liquidity.headline,
      bullets: snap.liquidity.bullets,
      evidenceKeys: Object.keys(snap.liquidity.evidence || {}).filter(
        (k) => snap.liquidity.evidence[k] != null && snap.liquidity.evidence[k] !== false
      ),
    },
    survival: {
      tier: snap.survival.tier,
      meaningful: snap.survival.meaningful,
      headline: snap.survival.headline,
      copy: snap.survival.copy,
      months: snap.survival.months,
      burn: snap.survival.burn,
      cash: snap.survival.cash,
    },
  }
}

const out = {
  inputSummary: {
    hasCashflow: Boolean(data.cashflow && typeof data.cashflow === 'object'),
    hasStatements: Boolean(data.statements?.available !== false && data.statements),
    hasIntelligence: Boolean(data.intelligence?.ratios?.liquidity),
    insightsCount: Array.isArray(data.statements?.insights) ? data.statements.insights.length : 0,
  },
  en: summarize(en.snap),
  arSample: {
    sectionTitle: ar.snap.sectionTitle,
    pressureHeadline: ar.snap.pressure.headline,
    pressureBullets: ar.snap.pressure.bullets,
  },
  duplicateFactsVsNarrative: [...en.dupes, ...ar.dupes],
  weakCards: [],
}

const weak = []
if (!en.snap.pressure.meaningful) weak.push('pressure: insufficient / empty')
if (!en.snap.liquidity.meaningful) weak.push('liquidity: insufficient / empty')
if (!en.snap.survival.meaningful) weak.push('survival: insufficient / empty')

// noisy placeholder: unknown tier with empty headline on meaningful? should not happen
if (en.snap.pressure.meaningful && en.snap.pressure.tier === 'unknown') weak.push('pressure: meaningful but tier unknown (unexpected)')
if (en.snap.liquidity.meaningful && en.snap.liquidity.tier === 'unknown')
  weak.push('liquidity: meaningful but tier unknown (unexpected)')

out.weakCards = weak
out.verdict =
  weak.length && weak.every((w) => w.includes('survival') && weak.length === 1)
    ? 'PASS_WITH_NOTES'
    : weak.length === 0
      ? 'PASS'
      : 'REVIEW'

console.log(JSON.stringify(out, null, 2))
