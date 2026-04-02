/**
 * Command Center UI smoke (Playwright).
 * Prerequisite: dev server reachable (e.g. npm run dev), or set CI_FRONTEND_URL / BASE_URL.
 *
 * Checks: non-empty body, no obvious raw i18n keys (exec_/cmd_/nav_/dq_) in visible text.
 */
import { chromium } from 'playwright'

const base = process.env.CI_FRONTEND_URL || process.env.BASE_URL || 'http://127.0.0.1:5173'

const browser = await chromium.launch({ headless: true })
try {
  const page = await browser.newPage()
  const resp = await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 45_000 })
  if (!resp) {
    console.error('command-center-smoke: no response')
    process.exit(1)
  }
  if (resp.status() >= 500) {
    console.error('command-center-smoke: HTTP', resp.status())
    process.exit(1)
  }
  const txt = await page.innerText('body')
  if (!txt || txt.trim().length < 5) {
    console.error('command-center-smoke: empty or nearly empty body')
    process.exit(1)
  }
  const rawKey = /\b(?:exec|cmd|nav|dq)_[a-z][a-z0-9_]{4,}\b/i
  if (rawKey.test(txt)) {
    const m = txt.match(rawKey)
    console.error('command-center-smoke: raw i18n-like token in page text:', m?.[0])
    process.exit(1)
  }
  console.log('command-center-smoke: ok', base)
} catch (e) {
  console.error('command-center-smoke:', e.message || e)
  process.exit(1)
} finally {
  await browser.close()
}
