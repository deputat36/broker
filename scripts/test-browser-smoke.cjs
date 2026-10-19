'use strict';
// Uses a local build only. All form responses are mocked; no email is sent.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES
  ? path.join(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES, 'playwright') : 'playwright');
let base = process.argv[2] || 'http://127.0.0.1:8765';
let server;
assert.ok(['localhost', '127.0.0.1'].includes(new URL(base).hostname), 'Use a local build');
const output = process.argv[3] || '/tmp/broker-browser-smoke';
fs.mkdirSync(output, { recursive: true });
const pages = ['/', '/online-zayavka/', '/kalkulyator-ipoteki/', '/stoimost/', '/uslugi/otkazali-v-ipoteke/', '/kontakty/'];
const widths = [360, 390, 430, 768, 1440];
const checks = [];
let browser;
function contrast(a, b) {
  const lum = color => {
    const rgb = color.match(/[\d.]+/g).slice(0, 3).map(v => {
      const n = Number(v) / 255; return n <= .04045 ? n / 12.92 : ((n + .055) / 1.055) ** 2.4;
    });
    return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722;
  };
  const x = lum(a), y = lum(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05);
}
async function formContext(mode) {
  const context = await browser.newContext({ viewport: { width: 390, height: 900 } });
  const requests = [], errors = [];
  await context.route('**/*', async route => {
    const url = route.request().url();
    if (new URL(url).origin === new URL(base).origin) return route.continue();
    if (url.startsWith('https://api.web3forms.com/')) {
      requests.push(JSON.parse(route.request().postData()));
      if (mode === 'timeout') return;
      await new Promise(resolve => setTimeout(resolve, 120));
      return route.fulfill({ status: mode === 'success' ? 200 : 500,
        contentType: 'application/json', body: JSON.stringify({ success: mode === 'success' }) });
    }
    return route.abort();
  });
  const page = await context.newPage();
  page.on('pageerror', e => errors.push(String(e)));
  await page.goto(base + '/online-zayavka/?source=%2Fuslugi%2Fotkazali-v-ipoteke%2F&placement=browser_smoke&utm_source=smoke&utm_medium=test');
  await page.waitForFunction(() => document.querySelector('[data-online-application]').dataset.applicationReady === 'true');
  return { context, page, requests, errors };
}
async function fill(page) {
  await page.locator('[name="client_name"]').fill('Тест интерфейса');
  await page.locator('[name="phone"]').fill('89999999999');
  await page.locator('[name="city"]').fill('Тестовый город');
  await page.locator('[name="consent"]').check();
}
(async () => {
  if (process.env.BROKER_SITE_DIR) {
    const root = path.resolve(process.env.BROKER_SITE_DIR);
    server = require('node:http').createServer((req, res) => {
      let file = path.join(root, decodeURIComponent(new URL(req.url, 'http://localhost').pathname));
      if (file.endsWith(path.sep)) file = path.join(file, 'index.html');
      if (!file.startsWith(root + path.sep) || !fs.existsSync(file)) { res.writeHead(404); return res.end(); }
      const types = { '.html': 'text/html; charset=utf-8', '.js': 'application/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.webp': 'image/webp' };
      res.setHeader('Content-Type', types[path.extname(file)] || 'application/octet-stream');
      fs.createReadStream(file).pipe(res);
    });
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    base = 'http://127.0.0.1:' + server.address().port;
  }
  browser = await chromium.launch({ headless: true,
    ...(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {}),
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'] });
  for (const width of widths) {
    const context = await browser.newContext({ viewport: { width, height: 900 } });
    const page = await context.newPage(); const errors = [];
    page.on('pageerror', e => errors.push(String(e)));
    await context.route('**/*', route => new URL(route.request().url()).origin === new URL(base).origin ? route.continue() : route.abort());
    for (const pathname of pages) {
      await page.goto(base + pathname);
      await page.waitForLoadState('networkidle');
      const directory = page.locator('.footer-directory');
      if (pathname !== '/online-zayavka/') {
        assert.equal(await directory.getAttribute('open'), null);
        await directory.locator('summary').click();
        assert.notEqual(await directory.getAttribute('open'), null);
        await directory.locator('summary').click();
        await page.evaluate(() => window.scrollTo({top:0,behavior:'instant'}));
      }
      const layout = await page.evaluate(() => ({ width: innerWidth, content: document.documentElement.scrollWidth,
        h1: document.querySelectorAll('h1').length, brokenImages: [...document.images].filter(i => !i.complete || !i.naturalWidth).map(i => i.src) }));
      assert.equal(layout.h1, 1, pathname + ': H1');
      assert.ok(layout.content <= layout.width + 1, `${width} ${pathname}: horizontal overflow ${layout.content}`);
      assert.deepEqual(layout.brokenImages, [], pathname + ': images');
      if (pathname === '/online-zayavka/') {
        const y = await page.locator('[name="client_name"]').evaluate(e => e.getBoundingClientRect().top);
        assert.ok(y < 650, `${width}: first field too low (${y})`);
        const toggle = page.locator('.nav-toggle');
        if (await toggle.isVisible()) {
          await toggle.focus(); await page.keyboard.press('Enter');
          assert.equal(await toggle.getAttribute('aria-expanded'), 'true');
        }
        const nav = await page.locator('.nav-apply').evaluate(e => {
          const s = getComputedStyle(e); return { color: s.color, background: s.backgroundColor };
        });
        assert.ok(contrast(nav.color, nav.background) >= 4.5, 'Application navigation contrast');
        const phoneLines = await page.locator('.nav-phone').evaluate(e => { const r = document.createRange(); r.selectNodeContents(e); return r.getClientRects().length; });
        assert.equal(phoneLines, 1, `${width}: wrapped phone`);
        if (await toggle.isVisible()) { await page.keyboard.press('Escape'); assert.equal(await toggle.getAttribute('aria-expanded'), 'false'); }
      }
      if (pathname === '/') {
        assert.equal(await page.locator('.hero .hero-actions a').count(), 2);
        assert.match(await page.locator('[data-calc-result]').innerText(), /Введите ставку для расчёта/);
        assert.equal(await page.locator('[name="rate"]').getAttribute('aria-invalid'), 'false');
        await page.locator('[name="rate"]').fill('6');
        assert.match(await page.locator('[data-calc-result]').innerText(), /Примерный ежемесячный платёж/);
        assert.ok((await page.locator('[data-calc-application-link]').getAttribute('href')).includes('calc_rate=6'));
      }
      if (['/', '/online-zayavka/'].includes(pathname)) {
        await page.evaluate(() => window.scrollTo({top:0,behavior:'instant'}));
        await page.screenshot({ path: path.join(output, `${width}-${pathname === '/' ? 'home' : 'form'}.png`), fullPage: false });
      }
      checks.push({ width, pathname, overflow: false });
    }
    assert.deepEqual(errors, [], `${width}: JavaScript errors`); await context.close();
  }
  for (const mode of ['success', 'error', 'timeout']) {
    const { context, page, requests, errors } = await formContext(mode);
    assert.equal(await page.locator('[name="scenario"]').inputValue(), 'Банк отказал в ипотеке');
    await page.locator('[data-application-submit]').click();
    assert.equal(await page.locator('[data-application-result]').isVisible(), false);
    await fill(page);
    await page.locator('[name="consent"]').uncheck();
    await page.locator('[data-application-submit]').click();
    assert.equal(await page.locator('[data-application-result]').isVisible(), false);
    await page.locator('[name="consent"]').check();
    await page.locator('[data-application-submit]').click();
    assert.equal(requests.length, 0, 'Preparation must not send');
    await page.locator('[name="city"]').fill('Новый тестовый город');
    assert.equal(await page.locator('[data-application-result]').isVisible(), false, 'Edited data invalidates preview');
    await page.locator('[data-application-submit]').click();
    await page.waitForTimeout(3100);
    await page.locator('[data-application-direct-send]').click();
    assert.equal(await page.locator('form[data-online-application]').evaluate(e => e.inert), true, 'Fields locked during delivery');
    // A second synthetic click must not create another request, even before the response.
    await page.locator('[data-application-direct-send]').evaluate(e => e.dispatchEvent(new MouseEvent('click')));
    if (mode === 'success') {
      await page.waitForURL('**/spasibo/**');
      assert.match(await page.locator('h1').innerText(), /технически принято/);
      assert.equal(requests.length, 1, 'Single successful request');
      const stored = await page.evaluate(() => Object.entries(localStorage).map(([k, v]) => [k, v]));
      assert.ok(!JSON.stringify(stored).includes('89999999999'));
      assert.ok(!JSON.stringify(stored).includes('Тест интерфейса'));
      const last = JSON.parse(stored.find(([k]) => k === 'sterlikovaMortgageLastLead')[1]);
      assert.deepEqual(Object.keys(last).sort(), ['expires_at', 'request_id']);
      assert.equal(last.request_id, requests[0].request_id);
      assert.equal(requests[0].placement, 'browser_smoke');
      assert.equal(requests[0].fields_json, undefined);
    } else {
      await page.waitForFunction(() => document.querySelector('[data-application-delivery-note]').classList.contains('is-error'), null, { timeout: 12000 });
      assert.equal(requests.length, 1, 'Single failed request');
      assert.equal(await page.locator('form[data-online-application]').evaluate(e => e.inert), false);
      assert.equal(await page.locator('[data-application-direct-send]').isEnabled(), true);
      assert.ok((await page.locator('[data-application-output]').inputValue()).includes('Новый тестовый город'));
      assert.ok((await page.locator('[data-application-sms]').getAttribute('href')).startsWith('sms:'));
    }
    assert.deepEqual(errors, [], mode + ': JavaScript errors');
    checks.push({ form: mode, requests: requests.length }); await context.close();
  }
  const nojs = await browser.newContext({ javaScriptEnabled: false });
  const page = await nojs.newPage(); await page.goto(base + '/online-zayavka/');
  assert.ok(await page.locator('noscript').innerText()); await nojs.close();
  fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify(checks, null, 2));
  console.log(`Browser smoke passed: ${checks.length} scenarios, five viewport widths; all deliveries mocked.`);
})().catch(error => { console.error(error); process.exitCode = 1; }).finally(async () => { if (browser) await browser.close(); if (server) server.close(); });
