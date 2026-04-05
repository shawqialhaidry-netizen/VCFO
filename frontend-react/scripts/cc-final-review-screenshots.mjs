/**
 * Final review screenshots — Command Center main column (mocked API, English).
 *
 *   npm run screenshot:cc-final-review
 *
 * Outputs: screenshots/final-review/01-main-risk-expanded.png … 04-liquidity-expanded.png
 */
import { chromium } from 'playwright'
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const repoRoot = path.resolve(root, '..')
const outDir = path.join(root, 'screenshots', 'final-review')
const baseUrl = 'http://127.0.0.1:5201'
const companyId = 'demo-co-review'

const executiveFixture = JSON.parse(fs.readFileSync(path.join(root, 'fixtures', 'cc-executive-en-review.json'), 'utf8'))
const enTranslations = JSON.parse(fs.readFileSync(path.join(repoRoot, 'app', 'i18n', 'en.json'), 'utf8'))

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

async function snapMainColumn(page, name) {
  const box = page.locator('.cmd-cine-body-main')
  await box.waitFor({ state: 'visible', timeout: 30_000 })
  await page.waitForTimeout(500)
  await box.screenshot({ path: path.join(outDir, name) })
}

async function closeExpanded(page) {
  const closeBtn = page.locator('.cmd-cine-intel-expanded__close')
  if (await closeBtn.isVisible().catch(() => false)) {
    await closeBtn.click()
    await page.waitForTimeout(400)
  }
}

let previewProc = null
try {
  fs.mkdirSync(outDir, { recursive: true })

  const viteBin = path.join(root, 'node_modules', 'vite', 'bin', 'vite.js')
  previewProc = spawn(process.execPath, [viteBin, 'preview', '--host', '127.0.0.1', '--port', '5201', '--strictPort'], {
    cwd: root,
    stdio: 'ignore',
  })

  await waitForOk(`${baseUrl}/`)

  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({
    viewport: { width: 1680, height: 2600 },
    locale: 'en-US',
  })

  await context.addInitScript(({ companyId: cid }) => {
    localStorage.setItem('vcfo_lang', 'en')
    localStorage.setItem('vcfo_auth', JSON.stringify({ token: 'screenshot-demo', user: { name: 'Demo' } }))
    localStorage.setItem('vcfo_company_id', cid)
    try {
      localStorage.removeItem('vcfo_period_scope')
    } catch {
      /* ignore */
    }
  }, { companyId })

  const page = await context.newPage()

  await page.route('**/api/v1/language/translations/en', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ translations: enTranslations }),
    })
  })

  await page.route('**/api/v1/companies', async (route) => {
    if (route.request().method() !== 'GET') return route.continue()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([{ id: companyId, name: 'Demo Co (Review)' }]),
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
          summary: {
            risk_level: 'medium',
            trend_mom_revenue: 2.1,
            trend_mom_net_profit: 1.8,
            insight: 'Base case holds; stress liquidity if revenue momentum fades.',
            base_confidence: 0.71,
          },
          scenarios: {
            base: {
              revenue: [
                { point: 2550000, confidence: 0.72 },
                { point: 2620000, confidence: 0.7 },
              ],
              net_profit: [
                { point: 445000, confidence: 0.68 },
                { point: 468000, confidence: 0.65 },
              ],
            },
            optimistic: {
              revenue: [{ point: 2680000, confidence: 0.55 }],
              net_profit: [{ point: 492000, confidence: 0.52 }],
            },
            risk: {
              revenue: [{ point: 2380000, confidence: 0.58 }],
              net_profit: [{ point: 380000, confidence: 0.55 }],
            },
          },
        },
      }),
    })
  })

  await page.goto(`${baseUrl}/`, { waitUntil: 'networkidle', timeout: 120_000 })
  await page.waitForSelector('.cmd-cine-root', { timeout: 60_000 })
  await page.waitForSelector('.cmd-cine-intel-mosaic', { timeout: 30_000 })
  await page.waitForTimeout(1200)

  const pathAfterLoad = new URL(page.url()).pathname
  if (pathAfterLoad !== '/' && pathAfterLoad !== '') {
    throw new Error(`Expected / after load, got ${pathAfterLoad}`)
  }

  // 1 — Main column: triple trend + mosaic + compact bridge + expanded (Risk)
  await page.locator('.cmd-cine-intel-grid').getByRole('button', { name: /^Risk/i }).click()
  await page.waitForSelector('.cmd-cine-intel-expanded', { timeout: 15_000 })
  await snapMainColumn(page, '01-main-risk-expanded.png')

  await closeExpanded(page)

  // 2 — Forecast expanded
  await page.locator('.cmd-cine-forecast-card').click()
  await page.waitForSelector('.cmd-cine-intel-expanded', { timeout: 15_000 })
  await snapMainColumn(page, '02-forecast-expanded.png')

  await closeExpanded(page)

  // 3 — Profit bridge expanded
  await page.locator('button.cmd-cine-bridge-compact').first().click()
  await page.waitForSelector('.cmd-cine-intel-expanded', { timeout: 15_000 })
  await snapMainColumn(page, '03-profit-bridge-expanded.png')

  await closeExpanded(page)

  // 4 — Liquidity (domain tile)
  await page.locator('.cmd-cine-intel-grid').getByRole('button', { name: /^Liquidity/i }).click()
  await page.waitForSelector('.cmd-cine-intel-expanded', { timeout: 15_000 })
  await snapMainColumn(page, '04-liquidity-expanded.png')

  const urlEnd = new URL(page.url()).pathname
  if (urlEnd !== '/' && urlEnd !== '') {
    throw new Error(`URL changed unexpectedly: ${urlEnd}`)
  }

  await closeExpanded(page)
  await page.locator('.cmd-exec-layer').scrollIntoViewIfNeeded()
  await page.waitForTimeout(500)
  await page.locator('.cmd-exec-layer').screenshot({ path: path.join(outDir, '05-execution-layer-bottom.png') })

  await browser.close()
  console.log('cc-final-review-screenshots: wrote 5 PNGs under', outDir)
} catch (e) {
  console.error('cc-final-review-screenshots:', e.message || e)
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
