/**
 * Capture Command Center viewport for visual sign-off.
 * Prerequisite: `npm run preview` (or dev) on BASE_URL.
 *
 * Optional: set SCREENSHOT_AUTH_JSON and SCREENSHOT_COMPANY_ID to skip login
 * and show authenticated shell (API may still 422 without real data).
 */
import { chromium } from 'playwright'
import { mkdir, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dir = dirname(fileURLToPath(import.meta.url))
const outDir = join(__dir, '..', 'screenshots')
const outPath = join(outDir, 'command-center-signoff.png')

const base = process.env.BASE_URL || 'http://127.0.0.1:4173'
const authJson = process.env.SCREENSHOT_AUTH_JSON || '{"token":"screenshot-placeholder"}'
const companyId = process.env.SCREENSHOT_COMPANY_ID || ''

const browser = await chromium.launch({ headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 60_000 })

  await page.evaluate(
    ({ authJson: aj, companyId: cid }) => {
      try {
        localStorage.setItem('vcfo_auth', aj)
        if (cid) localStorage.setItem('vcfo_company_id', cid)
      } catch (_) {}
    },
    { authJson, companyId },
  )

  await page.goto(`${base.replace(/\/$/, '')}/`, { waitUntil: 'networkidle', timeout: 90_000 }).catch(() =>
    page.goto(`${base.replace(/\/$/, '')}/`, { waitUntil: 'domcontentloaded', timeout: 30_000 }),
  )

  await page.waitForTimeout(2500)

  await mkdir(outDir, { recursive: true })
  await page.screenshot({ path: outPath, fullPage: true })

  console.log('Wrote', outPath)
} catch (e) {
  console.error('command-center-screenshot:', e.message || e)
  process.exit(1)
} finally {
  await browser.close()
}
