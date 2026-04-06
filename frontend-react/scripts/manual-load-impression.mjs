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
const noDefer = process.env.VCFO_NO_DEFER === '1'
 
if (!token || !companyId) {
  console.error('manual-load-impression: missing VCFO_TOKEN or VCFO_COMPANY_ID')
  process.exit(1)
}
 
async function measurePage(page, path) {
  const apiCalls = new Set()
  const t0 = Date.now()
  let execMs = null
 
  page.removeAllListeners('request')
  page.removeAllListeners('response')
  page.on('request', (req) => {
    const u = req.url()
    if (u.includes('/api/')) apiCalls.add(`${req.method()} ${u}`)
  })
  page.on('response', async (res) => {
    const u = res.url()
    if (!u.includes('/api/v1/analysis/') || !u.includes('/executive')) return
    try {
      const t = res.request().timing()
      if (t && typeof t.responseEnd === 'number') execMs = Math.round(t.responseEnd)
    } catch {
      /* ignore */
    }
  })
 
  const resp = await page.goto(`${base}${path}`, { waitUntil: 'domcontentloaded', timeout: 120_000 })
  const domMs = Date.now() - t0

  // Measure "usable": company name visible (data-bound) or a main panel visible.
  const tU = Date.now()
  try {
    await page
      .locator(`text=${noDefer ? '' : ''}`)
      .first()
      .waitFor({ state: 'attached', timeout: 1 })
  } catch {
    /* noop */
  }
  try {
    await page
      .locator(`text=${'AJ INTERNATIONAL GRUP'}`)
      .first()
      .waitFor({ state: 'visible', timeout: 60_000 })
  } catch {
    // fallback: any h1/main visible
    try {
      await page.locator('h1, main').first().waitFor({ state: 'visible', timeout: 60_000 })
    } catch {
      /* ignore */
    }
  }
  const usableMs = Date.now() - tU

  // Paint metrics (if available)
  const paints = await page.evaluate(() => {
    try {
      const entries = performance.getEntriesByType('paint') || []
      const out = {}
      for (const e of entries) out[e.name] = Math.round(e.startTime)
      return out
    } catch {
      return {}
    }
  })

  const totalMs = Date.now() - t0
  return {
    path,
    status: resp ? resp.status() : null,
    domMs,
    usableExtraMs: usableMs,
    totalMs,
    paints,
    execMs,
    apiCalls: Array.from(apiCalls).filter((u) => u.includes('/api/v1/')),
  }
}
 
function impressionFrom(m) {
  if (m.usableExtraMs < 1200) return 'fast/acceptable'
  if (m.usableExtraMs < 2500) return 'acceptable (noticeable but ok)'
  if (m.usableExtraMs < 4500) return 'still heavy'
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
    // Optional: disable deferral for baseline comparison.
    if (localStorage.getItem('vcfo_perf_no_defer') == null) localStorage.removeItem('vcfo_perf_no_defer')
  }, { t: token, cid: companyId })
 
  const page = await context.newPage()
  if (noDefer) {
    await page.addInitScript(() => {
      try {
        localStorage.setItem('vcfo_perf_no_defer', '1')
      } catch {}
    })
  } else {
    await page.addInitScript(() => {
      try {
        localStorage.removeItem('vcfo_perf_no_defer')
      } catch {}
    })
  }
 
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
          usableMs: m.usableExtraMs,
          execMs: m.execMs,
          paints: m.paints,
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

