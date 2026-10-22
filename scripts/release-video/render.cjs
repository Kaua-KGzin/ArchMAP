const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');
const path = require('path');
(async () => {
  const mode = process.argv[2]; // "stills" (full video: build.sh)
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await page.goto('file://' + path.resolve(__dirname, 'index.html') + '?render');
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(500);
  if (mode === 'stills') {
    const ts = process.argv.slice(3).map(Number);
    for (const t of ts) { await page.evaluate(t => seek(t), t); await page.screenshot({ path: 'out/still_' + `${t}.png` }); }
  }
  await browser.close();
})();
