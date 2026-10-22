// usage: node render_part.cjs START_FRAME END_FRAME OUT.mp4
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');
const { spawn } = require('child_process'); const path = require('path');
(async () => {
  const [a, b, out] = [+process.argv[2], +process.argv[3], process.argv[4]]; const fps = 30;
  const browser = await chromium.launch(); const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await page.goto('file://' + path.resolve(__dirname, 'index.html') + '?render');
  await page.evaluate(() => document.fonts.ready); await page.waitForTimeout(500);
  const ff = spawn('ffmpeg', ['-loglevel','error','-y','-f','image2pipe','-framerate',String(fps),'-c:v','mjpeg','-i','-',
    '-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p',out], { stdio: ['pipe','inherit','inherit'] });
  for (let i = a; i < b; i++) {
    await page.evaluate(t => seek(t), i / fps);
    const buf = await page.screenshot({ type: 'jpeg', quality: 93 });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
  }
  ff.stdin.end(); await new Promise(r => ff.on('close', r)); await browser.close();
})();
