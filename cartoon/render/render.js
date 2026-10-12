// Render film.html frame by frame with headless Chrome and pipe the frames into ffmpeg.
//
//   node render.js                       -> ../../out/video_silent.mp4
//   OUT=../../out/test.mp4 FPS=25 node render.js
//   START=1500 node render.js            -> resume from frame 1500 (writes only the remaining frames)
//
// Env: CHROME (path to Chrome; default is the macOS install), FILM (page, default film.html),
//      OUT, FPS (default 25), START (first frame), END (last frame, exclusive), CRF (default 20).
const path = require('path');
const fs = require('fs');
const puppeteer = require('puppeteer-core');
const { spawn } = require('child_process');

const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const FILM = path.resolve(__dirname, process.env.FILM || 'film.html');
const OUT = path.resolve(process.env.OUT || path.join(__dirname, '../../out/video_silent.mp4'));
const FPS = +(process.env.FPS || 25);

(async () => {
  if (!fs.existsSync(CHROME)) { console.error(`Chrome not found at ${CHROME}. Set CHROME=/path/to/chrome.`); process.exit(1); }
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  const b = await puppeteer.launch({ executablePath: CHROME, headless: true });
  const p = await b.newPage(); await p.setViewport({ width: 1920, height: 1080 });
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('file://' + FILM);
  if (errs.length) { console.error('page errors:', errs); await b.close(); process.exit(1); }
  const { TOTAL } = await p.evaluate(() => window.TIMELINE);
  const N = Math.min(Math.ceil(TOTAL * FPS), +(process.env.END || Infinity));
  const START = +(process.env.START || 0);
  console.log(`rendering frames ${START}-${N} (${(TOTAL).toFixed(2)} s at ${FPS} fps) -> ${OUT}`);
  const ff = spawn('ffmpeg', ['-y', '-v', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', process.env.CRF || '20', '-preset', 'medium', OUT], { stdio: ['pipe', 'inherit', 'inherit'] });
  const t0 = Date.now();
  for (let f = START; f < N; f++) {
    await p.evaluate(t => window.seek(t), f / FPS);
    const buf = await p.screenshot({ type: 'jpeg', quality: 92 });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (f % 250 === 0) console.log(`frame ${f}/${N}  ${((Date.now() - t0) / 1000).toFixed(0)} s`);
  }
  ff.stdin.end(); await new Promise(r => ff.on('close', r)); await b.close();
  if (errs.length) console.error('page errors during render:', errs);
  console.log('done', N - START, 'frames in', ((Date.now() - t0) / 1000).toFixed(0), 's');
})();
