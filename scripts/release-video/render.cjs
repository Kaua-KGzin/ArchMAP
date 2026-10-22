const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');
const { spawn } = require('child_process');
const path = require('path');
(async () => {
  const mode = process.argv[2]; // "stills" or "video"
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await page.goto('file://' + path.resolve(__dirname, 'index.html') + '?render');
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(500);
  if (mode === 'stills') {
    const ts = process.argv.slice(3).map(Number);
    for (const t of ts) { await page.evaluate(t => seek(t), t); await page.screenshot({ path: 'out/still_' + `${t}.png` }); }
  } else {
    const fps = 30, dur = await page.evaluate(() => DUR);
    const ff = spawn('ffmpeg', ['-loglevel','error','-y','-f','image2pipe','-framerate',String(fps),'-c:v','mjpeg','-i','-',
      '-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','out/video_noaudio.mp4'], { stdio: ['pipe','inherit','inherit'] });
    const total = Math.round(dur * fps);
    for (let i = 0; i < total; i++) {
      await page.evaluate(t => seek(t), i / fps);
      const buf = await page.screenshot({ type: 'jpeg', quality: 93 });
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if (i % 300 === 0) console.log('frame', i, '/', total);
    }
    ff.stdin.end(); await new Promise(r => ff.on('close', r));
  }
  await browser.close();
})();
