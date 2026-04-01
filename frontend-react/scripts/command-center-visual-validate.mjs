import { chromium } from 'playwright'

const BASE = process.env.VCFO_BASE_URL || 'http://127.0.0.1:5173'
const OUT_DIR = process.env.VCFO_OUT_DIR || 'artifacts/command-center'
const AUTH_TOKEN = process.env.VCFO_AUTH_TOKEN || ''
const AUTH_LANG = process.env.VCFO_LANG || ''

function nowStamp() {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}${pad(d.getMonth()+1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`
}

async function ensureDir(page) {
  // Use browser-side to create nothing; rely on Node fs
}

async function run() {
  const fs = await import('node:fs/promises')
  const path = await import('node:path')
  const runDir = path.join(process.cwd(), OUT_DIR, nowStamp())
  await fs.mkdir(runDir, { recursive: true })

  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

  const consoleErrors = []
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text())
  })
  page.on('pageerror', (err) => {
    consoleErrors.push(String(err))
  })

  const shots = []
  const shot = async (name) => {
    const file = path.join(runDir, `${name}.png`)
    await page.screenshot({ path: file, fullPage: true })
    shots.push({ name, file })
  }

  // Optional auth bootstrap for environments where / requires login
  if (AUTH_TOKEN) {
    await page.addInitScript((token, lang) => {
      try {
        localStorage.setItem('vcfo_auth', JSON.stringify({ token }))
        if (lang) localStorage.setItem('vcfo_lang', lang)
      } catch (_) {}
    }, AUTH_TOKEN, AUTH_LANG)
  }

  await page.goto(`${BASE}/`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(500)
  await shot('01-command-center-full')

  // If redirected to login, stop early and report (requires token bootstrap)
  const looksLikeLogin = await page.locator('text=VCFO').count().then(async () => {
    // Heuristic: login form has email/password placeholders; command center does not.
    const hasPassword = await page.locator('input[type="password"]').count().catch(() => 0)
    const hasEmail = await page.locator('input[type="email"], input[placeholder*="@"]').count().catch(() => 0)
    return hasPassword > 0 && hasEmail > 0
  })
  if (looksLikeLogin) {
    await shot('99-login-blocking')
    await browser.close()
    const report = {
      baseUrl: BASE,
      runDir,
      screenshots: shots,
      consoleErrors,
      ok: false,
      blockedByLogin: true,
      note: 'Login screen detected. Provide VCFO_AUTH_TOKEN to capture Command Center screenshots and click-test interactions.',
    }
    await fs.writeFile(path.join(runDir, 'report.json'), JSON.stringify(report, null, 2), 'utf8')
    console.log(JSON.stringify(report, null, 2))
    return
  }

  // Interactions: click first big decision card if present (best-effort)
  // Decision cards are divs with cursor:pointer; safest heuristic: first within ActionStrip grid (3 columns)
  const clickableCards = page.locator('div[title]').filter({ hasText: '' })
  // Try click an element that resembles a decision tile: has a timeframe "⏱"
  const decisionTile = page.locator('div', { hasText: '⏱' }).first()
  if (await decisionTile.count()) {
    await decisionTile.click({ timeout: 3000 }).catch(() => {})
    await page.waitForTimeout(300)
    await shot('02-context-panel-open')
    // Close (X button)
    const closeBtn = page.locator('button', { hasText: '×' }).first()
    if (await closeBtn.count()) await closeBtn.click().catch(() => {})
    await page.waitForTimeout(300)
  }

  // Click a KPI card (hero KPI area: look for "MoM" token)
  const kpiCard = page.locator('span', { hasText: 'MoM' }).first()
  if (await kpiCard.count()) {
    await kpiCard.click().catch(() => {})
    await page.waitForTimeout(300)
    await shot('03-kpi-context-open')
    const closeBtn = page.locator('button', { hasText: '×' }).first()
    if (await closeBtn.count()) await closeBtn.click().catch(() => {})
    await page.waitForTimeout(300)
  }

  // Navigate to analysis using command nav button (best-effort: contains /analysis route label)
  // Try clicking a button that navigates; we can click first button with text matching common translations
  const analysisBtn = page.locator('button', { hasText: /analysis|تحليل|Analiz/i }).first()
  if (await analysisBtn.count()) {
    await analysisBtn.click().catch(() => {})
    await page.waitForLoadState('networkidle').catch(() => {})
    await page.waitForTimeout(500)
    await shot('04-analysis-page')
    await page.goto(`${BASE}/`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(500)
  }

  await shot('05-command-center-post-interactions')

  await browser.close()

  const report = {
    baseUrl: BASE,
    runDir,
    screenshots: shots,
    consoleErrors,
    ok: consoleErrors.length === 0,
  }
  await fs.writeFile(path.join(runDir, 'report.json'), JSON.stringify(report, null, 2), 'utf8')

  console.log(JSON.stringify(report, null, 2))
}

run().catch((e) => {
  console.error(e)
  process.exit(1)
})

