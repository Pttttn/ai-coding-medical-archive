/* Headless UI acceptance checks against the running local application. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_CHANNEL ? { channel: process.env.BROWSER_CHANNEL } : {}) });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [], remote = [], results = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('request', request => {
    const url = new URL(request.url());
    if (url.protocol.startsWith('http') && !['localhost', '127.0.0.1'].includes(url.hostname)) remote.push(request.url());
  });
  fs.mkdirSync('.runtime/ui', { recursive: true });
  const base = process.env.UI_BASE || 'http://127.0.0.1:8080';
  for (const path of ['/', '/archive', '/timeline', '/ask', '/consultation', '/history', '/upload']) {
    await page.goto(base + path, { waitUntil: 'networkidle' });
    await page.locator('h1').waitFor();
    const text = await page.locator('body').innerText();
    assert(!text.includes('Failed to fetch'), text);
    results.push({ path, title: await page.locator('h1').innerText(), viewport: 'desktop', loaded: true });
    if (path === '/') await page.screenshot({ path: '.runtime/ui/dashboard-desktop.png', fullPage: true });
    if (path === '/archive') await page.screenshot({ path: '.runtime/ui/archive-desktop.png', fullPage: true });
  }
  await page.goto(base + '/archive', { waitUntil: 'networkidle' });
  const link = page.locator('a[href^="/archive/"]').first();
  await link.click();
  await page.locator('h1').waitFor();
  await page.waitForLoadState('networkidle');
  results.push({ path: new URL(page.url()).pathname, title: await page.locator('h1').innerText(), loaded: true });
  await page.screenshot({ path: '.runtime/ui/document-desktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  for (const path of ['/', '/archive', '/timeline', '/ask', '/consultation', '/history', '/upload']) {
    await page.goto(base + path, { waitUntil: 'networkidle' });
    await page.locator('h1').waitFor();
    const dimensions = await page.evaluate(() => ({ width: window.innerWidth, scroll: document.documentElement.scrollWidth }));
    assert(dimensions.scroll <= dimensions.width + 1, JSON.stringify({ path, ...dimensions }));
    results.push({ path, viewport: 'mobile', noHorizontalOverflow: true });
    if (path === '/') await page.screenshot({ path: '.runtime/ui/dashboard-mobile.png', fullPage: true });
    if (path === '/archive') await page.screenshot({ path: '.runtime/ui/archive-mobile.png', fullPage: true });
  }
  assert.equal(errors.length, 0, JSON.stringify(errors));
  assert.equal(remote.length, 0, JSON.stringify(remote));
  fs.mkdirSync('docs/evaluation', { recursive: true });
  fs.writeFileSync('docs/evaluation/browser-smoke.json', JSON.stringify({ timestamp: new Date().toISOString(), base, results, pageErrors: errors, externalRequests: remote }, null, 2));
  console.log(JSON.stringify({ screensChecked: results.length, pageErrors: errors.length, externalRequests: remote.length }));
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
