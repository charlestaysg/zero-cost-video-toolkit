// Snapshot frames for checking layout before a full render, and optionally tile them into a contact sheet.
//
//   node snap.js 3 12.5 30           -> snapshots at those times (seconds)
//   node snap.js --count 24          -> 24 evenly spaced frames
//   node snap.js --count 24 --contact  -> ...plus contact.jpg (6 columns) via ffmpeg
//
// Env: CHROME, FILM (default film.html), SNAPS (output folder, default ../../out/snaps).
// Any page error (e.g. "anchor not found") is printed at the end. Fix those first.
const path = require('path');
const fs = require('fs');
const puppeteer = require('puppeteer-core');
const { execFileSync } = require('child_process');

const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const FILM = path.resolve(__dirname, process.env.FILM || 'film.html');
const SNAPS = path.resolve(process.env.SNAPS || path.join(__dirname, '../../out/snaps'));

(async () => {
  const args = process.argv.slice(2);
  const contact = args.includes('--contact');
  const ci = args.indexOf('--count');
  const count = ci >= 0 ? +args[ci + 1] : 0;
  let times = args.filter((a, i) => !a.startsWith('--') && !(ci >= 0 && i === ci + 1)).map(Number).filter(x => !isNaN(x));
  fs.mkdirSync(SNAPS, { recursive: true });
  const b = await puppeteer.launch({ executablePath: CHROME, headless: true });
  const p = await b.newPage(); await p.setViewport({ width: 1920, height: 1080 });
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  await p.goto('file://' + FILM);
  const tl = await p.evaluate(() => window.TIMELINE);
  if (!tl) { console.error('page failed to load:', errs); await b.close(); process.exit(1); }
  console.log('timeline', JSON.stringify({ starts: tl.starts.map(x => +x.toFixed(2)), TOTAL: +tl.TOTAL.toFixed(2) }));
  if (count) times = Array.from({ length: count }, (_, k) => +((k + .5) * tl.TOTAL / count).toFixed(2));
  if (!times.length) { console.error('give times in seconds, or --count N'); await b.close(); process.exit(1); }
  const files = [];
  for (const [k, t] of times.entries()) {
    try { await p.evaluate(t => window.seek(t), t); } catch (e) { errs.push(`t=${t}: ${e.message.split('\n')[0]}`); }
    const f = path.join(SNAPS, `${String(k).padStart(3, '0')}_t${t}.jpg`);
    await p.screenshot({ path: f, type: 'jpeg', quality: 70 });
    files.push(f);
  }
  console.log(`${files.length} snapshots in ${SNAPS}`);
  if (contact) {
    const cols = 6, rows = Math.ceil(files.length / cols), out = path.join(SNAPS, 'contact.jpg');
    const list = path.join(SNAPS, 'list.txt');
    fs.writeFileSync(list, files.map(f => `file '${f}'`).join('\n'));
    execFileSync('ffmpeg', ['-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', list,
      '-vf', `scale=320:-1,tile=${cols}x${rows}:padding=4:color=white`, '-frames:v', '1', '-q:v', '4', out]);
    console.log('contact sheet', out);
  }
  console.log('errors:', errs.length ? errs : 'none');
  await b.close();
  if (errs.length) process.exitCode = 1;
})();
