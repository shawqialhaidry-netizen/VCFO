/**
 * Full-page Command Center screenshot — Arabic UI, desktop width.
 * Uses mocked API (no backend). Requires: npm run build, Playwright browser.
 *
 *   npm run screenshot:cc-ar
 *
 * Output: screenshots/command-center-ar-desktop-full.png
 */
import { chromium } from 'playwright'
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const repoRoot = path.resolve(root, '..')
const outDir = path.join(root, 'screenshots')
const outFile = path.join(outDir, 'command-center-ar-desktop-full.png')
const baseUrl = 'http://127.0.0.1:5199'
const companyId = 'demo-co'

const executiveFixture = JSON.parse(
  fs.readFileSync(path.join(root, 'fixtures', 'cc-executive-ar-demo.json'), 'utf8'),
)
const arTranslations = JSON.parse(fs.readFileSync(path.join(repoRoot, 'app', 'i18n', 'ar.json'), 'utf8'))

function waitForOk(url, timeoutMs = 90_000) {
  const start = Date.now()
  return new Promise((resolve, reject) => {
    const tick = async () => {
      if (Date.now() - start > timeoutMs) {
        reject(new Error(`Timeout waiting for ${url}`))
        return
      }
      try {
        const r = await fetch(url, { signal: AbortSignal.timeout(2500) })
        if (r.ok) {
          resolve()
          return
        }
      } catch {
        /* retry */
      }
      setTimeout(tick, 400)
    }
    tick()
  })
}

let previewProc = null
try {
  fs.mkdirSync(outDir, { recursive: true })

  const viteBin = path.join(root, 'node_modules', 'vite', 'bin', 'vite.js')
  previewProc = spawn(process.execPath, [viteBin, 'preview', '--host', '127.0.0.1', '--port', '5199', '--strictPort'], {
    cwd: root,
    stdio: 'ignore',
  })

  await waitForOk(`${baseUrl}/`)

  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({
    viewport: { width: 1680, height: 960 },
    locale: 'ar',
  })

  await context.addInitScript(({ companyId: cid }) => {
    localStorage.setItem('vcfo_lang', 'ar')
    localStorage.setItem('vcfo_auth', JSON.stringify({ token: 'screenshot-demo', user: { name: 'Demo' } }))
    localStorage.setItem('vcfo_company_id', cid)
    try {
      localStorage.removeItem('vcfo_period_scope')
    } catch {
      /* ignore */
    }
  }, { companyId })

  const page = await context.newPage()

  await page.route('**/api/v1/language/translations/ar', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ translations: arTranslations }),
    })
  })

  await page.route('**/api/v1/companies', async (route) => {
    if (route.request().method() !== 'GET') return route.continue()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([{ id: companyId, name: 'شركة العرض التجريبي' }]),
    })
  })

  await page.route('**/api/v1/auth/me/memberships', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
  })

  await page.route(/\/api\/v1\/analysis\/[^/]+\/executive(\?|$)/, async (route) => {
    if (route.request().method() !== 'GET') return route.continue()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(executiveFixture),
    })
  })

  await page.route(/\/api\/v1\/analysis\/[^/]+\/forecast(\?|$)/, async (route) => {
    if (route.request().method() !== 'GET') return route.continue()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          available: true,
          summary: { risk_level: 'low' },
          scenarios: {
            base: {
              revenue: [{ point: 2550000, confidence: 0.72 }, { point: 2620000, confidence: 0.7 }],
              net_profit: [{ point: 445000, confidence: 0.68 }, { point: 468000, confidence: 0.65 }],
            },
          },
        },
      }),
    })
  })

  await page.goto(`${baseUrl}/`, { waitUntil: 'networkidle', timeout: 120_000 })
  await page.waitForSelector('.cmd-cine-root', { timeout: 60_000 })
  await new Promise((r) => setTimeout(r, 2800))

  await page.screenshot({ path: outFile, fullPage: true })

  await browser.close()
  console.log('cc-screenshot-ar: wrote', outFile)
} catch (e) {
  console.error('cc-screenshot-ar:', e.message || e)
  process.exitCode = 1
} finally {
  if (previewProc && !previewProc.killed) {
    try {
      previewProc.kill('SIGTERM')
    } catch {
      /* ignore */
    }
  }
}
