/**
 * Statements page — real Playwright screenshots (mocked executive + statement_hierarchy).
 *
 *   npm run screenshot:statements
 *
 * Outputs: screenshots/statements/01-income.png, 02-balance.png, 03-cash.png
 */
import { chromium } from 'playwright'
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(__dirname, '..')
const repoRoot = path.resolve(root, '..')
const outDir = path.join(root, 'screenshots', 'statements')
const baseUrl = 'http://127.0.0.1:5202'
const companyId = 'demo-co-statements'

const executiveBase = JSON.parse(fs.readFileSync(path.join(root, 'fixtures', 'cc-executive-en-review.json'), 'utf8'))
const hierarchySample = JSON.parse(fs.readFileSync(path.join(root, 'fixtures', 'statement-hierarchy-sample.json'), 'utf8'))
const executiveFixture = {
  ...executiveBase,
  data: {
    ...executiveBase.data,
    statement_hierarchy: hierarchySample,
  },
}

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

async function snapStatements(page, name) {
  const panel = page.locator('main.grid-bg > div.stmt-premium').first()
  await panel.waitFor({ state: 'visible', timeout: 30_000 })
  await page.waitForTimeout(500)
  await panel.screenshot({ path: path.join(outDir, name) })
}

let previewProc = null
try {
  fs.mkdirSync(outDir, { recursive: true })

  const viteBin = path.join(root, 'node_modules', 'vite', 'bin', 'vite.js')
  previewProc = spawn(process.execPath, [viteBin, 'preview', '--host', '127.0.0.1', '--port', '5202', '--strictPort'], {
    cwd: root,
    stdio: 'ignore',
  })

  await waitForOk(`${baseUrl}/`)

  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({
    viewport: { width: 1400, height: 2200 },
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
      body: JSON.stringify([{ id: companyId, name: 'Demo Co (Statements)' }]),
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

  await page.goto(`${baseUrl}/statements`, { waitUntil: 'networkidle', timeout: 120_000 })
  await page.getByRole('button', { name: 'Income Statement' }).waitFor({ state: 'visible', timeout: 30_000 })
  await page.waitForTimeout(800)

  await snapStatements(page, '01-income.png')

  await page.getByRole('button', { name: 'Balance Sheet' }).click()
  await page.waitForTimeout(600)
  await snapStatements(page, '02-balance.png')

  await page.getByRole('button', { name: 'Cash Flow Statement' }).click()
  await page.waitForTimeout(600)
  await snapStatements(page, '03-cash.png')

  await browser.close()
  console.log('statements-screenshots: wrote 3 PNGs under', outDir)
} catch (e) {
  console.error('statements-screenshots:', e.message || e)
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
