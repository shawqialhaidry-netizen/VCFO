/**
 * Manual product-level load impression (Playwright).
 *
 * Uses real dev server + real backend via Vite proxy.
 *
 * Required env:
 *   BASE_URL=http://127.0.0.1:5173
 *   VCFO_TOKEN=<jwt>
 *   VCFO_COMPANY_ID=<company_id>
 *
 * Output: prints per-page timing + a short impression category.
 */
import { chromium } from 'playwright'
 
const base = process.env.BASE_URL || 'http://127.0.0.1:5173'
const token = process.env.VCFO_TOKEN || ''
const companyId = process.env.VCFO_COMPANY_ID || ''
 
if (!token || !companyId) {
  console.error('manual-load-impression: missing VCFO_TOKEN or VCFO_COMPANY_ID')
  process.exit(1)
}
 
async function measurePage(page, path) {
  const apiCalls = new Set()
  const t0 = Date.now()
 
  page.removeAllListeners('request')
  page.on('request', (req) => {
    const u = req.url()
    if (u.includes('/api/')) apiCalls.add(`${req.method()} ${u}`)
  })
 
  // crude "spinner" visibility: look for common loading glyphs/ellipsis container
  // (we don't want to couple to implementation; just detect long waits).
  const resp = await page.goto(`${base}${path}`, { waitUntil: 'domcontentloaded', timeout: 120_000 })
  const domMs = Date.now() - t0
 
  // wait for network to settle or main content markers to appear
  const t1 = Date.now()
  try {
    await page.waitForLoadState('networkidle', { timeout: 60_000 })
  } catch {
    /* ignore */
  }
  const netIdleMs = Date.now() - t1
 
  // "visible content" marker: any h1 or main panel visible
  const t2 = Date.now()
  try {
    await page.locator('h1, main').first().waitFor({ state: 'visible', timeout: 30_000 })
  } catch {
    /* ignore */
  }
  const firstVisibleMs = Date.now() - t2
 
  const totalMs = Date.now() - t0
  return {
    path,
    status: resp ? resp.status() : null,
    domMs,
    netIdleExtraMs: netIdleMs,
    firstVisibleExtraMs: firstVisibleMs,
    totalMs,
    apiCalls: Array.from(apiCalls).filter((u) => u.includes('/api/v1/')),
  }
}
 
function impressionFrom(m) {
  if (m.totalMs < 1500) return 'fast/acceptable'
  if (m.totalMs < 3000) return 'acceptable (noticeable but ok)'
  if (m.totalMs < 5000) return 'still heavy'
  return 'very heavy'
}
 
const browser = await chromium.launch({ headless: true })
try {
  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 },
    locale: 'en-US',
  })
 
  await context.addInitScript(({ t, cid }) => {
    localStorage.setItem('vcfo_lang', 'en')
    localStorage.setItem('vcfo_auth', JSON.stringify({ token: t, user: { name: 'Perf' } }))
    localStorage.setItem('vcfo_company_id', cid)
  }, { t: token, cid: companyId })
 
  const page = await context.newPage()
 
  const pages = [
    { name: 'Command Center', path: '/' },
    { name: 'ExecutiveDashboard', path: '/executive' },
    { name: 'Analysis', path: '/analysis' },
    { name: 'Statements', path: '/statements' },
  ]
 
  for (const p of pages) {
    const m = await measurePage(page, p.path)
    console.log('PAGE', p.name)
    console.log(
      JSON.stringify(
        {
          path: m.path,
          status: m.status,
          totalMs: m.totalMs,
          domMs: m.domMs,
          impression: impressionFrom(m),
          apiCalls: m.apiCalls.map((u) => u.replace(base, '')).slice(0, 20),
        },
        null,
        2,
      ),
    )
  }
} catch (e) {
  console.error('manual-load-impression:', e?.message || e)
  process.exitCode = 1
} finally {
  await browser.close()
}

