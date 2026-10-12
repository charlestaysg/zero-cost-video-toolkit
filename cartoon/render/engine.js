// Cartoon engine: timeline, drawing helpers, characters, backgrounds, captions and word anchors.
// Everything is a pure function of time, so window.seek(t) always draws the same frame.
// Drawing space is 1280x720 SVG units, scaled to 1920x1080 by film.html.

// ---------- timeline ----------
const AUD = window.AUDN;                 // narration clip length per scene (from timings.py)
const NS = AUD.length;
const TITLE = window.TL.title, GAP = window.TL.gap, CREDITS = window.TL.credits;
const starts = []; { let t = TITLE; for (const d of AUD) { starts.push(t); t += d + GAP; } }
const TOTAL = starts[NS - 1] + AUD[NS - 1] + GAP + CREDITS;
window.TIMELINE = { starts, TOTAL };

// ---------- maths and easing ----------
const cl = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const pr = (t, a, b) => cl((t - a) / (b - a));                     // progress of t through [a, b]
const eo = x => 1 - Math.pow(1 - x, 3);                             // ease out
const eio = x => x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; // ease in-out
const eb = x => { const c1 = 1.70158, c3 = c1 + 1; return x <= 0 ? 0 : 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); }; // back-out
const pop = (t, a, d = .45) => eb(pr(t, a, a + d));                 // springy scale-in starting at a
const fi = (t, a, d = .35) => pr(t, a, a + d);                      // fade in starting at a
const win = (t, a, b, d = .35) => Math.min(fi(t, a, d), 1 - fi(t, b, d)); // visible between a and b
const lerp = (a, b, x) => a + (b - a) * x;
const rnd = i => { const x = Math.sin(i * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); }; // deterministic noise

// ---------- palette ----------
const C = { bg: '#FFF6E9', ink: '#2B2D42', green: '#4CAF7A', dgreen: '#2E7D57', lgreen: '#BFE7C5', coral: '#FF7A59', yellow: '#FFC845', sky: '#8EC5FF', lsky: '#DCEBFF', red: '#E5484D', grey: '#8D90A6', white: '#FFFFFF', wood: '#C98B55', steel: '#B8C0CC', copper: '#D9814A' };

// ---------- SVG helpers ----------
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
const G = (x, y, s, inner, o = 1, rot = 0) => `<g transform="translate(${x},${y}) rotate(${rot}) scale(${s})" opacity="${o}">${inner}</g>`;
const T = (x, y, s, size, col = C.ink, w = 700, anchor = 'middle', extra = '') => `<text x="${x}" y="${y}" font-size="${size}" fill="${col}" font-weight="${w}" text-anchor="${anchor}" dominant-baseline="middle" ${extra}>${esc(s)}</text>`;
function wrap(s, n) { const out = []; let line = ''; for (const w of s.split(' ')) { if ((line + ' ' + w).trim().length > n) { out.push(line.trim()); line = w; } else line += ' ' + w; } if (line.trim()) out.push(line.trim()); return out; }
const TW = (x, y, lines, size, col = C.ink, w = 600, anchor = 'start', lh = 1.3) => lines.map((l, i) => T(x, y + i * size * lh, l, size, col, w, anchor)).join('');
const card = (x, y, w, h, fill = C.white, stroke = C.ink, r = 18, sw = 4) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"/>`;
const chipW = (label, size) => label.length * size * .56 + 28;
function chip(x, y, label, fill, size = 30) {
  const w = chipW(label, size), h = size * 1.5;
  return `<rect x="${x - w / 2}" y="${y - h / 2}" width="${w}" height="${h}" rx="14" fill="${fill}" stroke="${C.ink}" stroke-width="3"/><text x="${x}" y="${y + 2}" font-size="${size}" fill="${C.ink}" font-weight="700" text-anchor="middle" dominant-baseline="middle">${esc(label)}</text>`;
}
const heading = (s, size = 44, col = C.ink) => `<text x="0" y="0" font-size="${size}" font-weight="800" fill="${col}" text-anchor="middle" dominant-baseline="middle">${esc(s)}</text>`;
const check = (x, y, s = 1, col = C.green) => `<g transform="translate(${x},${y}) scale(${s})"><circle r="20" fill="${col}"/><path d="M-9,0 L-2,8 L10,-8" stroke="#fff" stroke-width="5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></g>`;
const sparkle = (x, y, s, o) => `<g transform="translate(${x},${y}) scale(${s})" opacity="${o}"><path d="M0,-20 L5,-5 L20,0 L5,5 L0,20 L-5,5 L-20,0 L-5,-5Z" fill="${C.yellow}" stroke="${C.ink}" stroke-width="2"/></g>`;
// small grey source line above the caption area: cite where a claim comes from
const source = (s, o = 1) => `<text x="1250" y="598" font-size="15" font-weight="600" fill="${C.grey}" text-anchor="end" opacity="${o}">${esc(s)}</text>`;
function bubble(x, y, w, lines, size, o = 1, tailX = null, tailDir = 1) {
  const h = lines.length * size * 1.3 + 30;
  let s = card(x, y, w, h, C.white, C.ink, 22, 4);
  if (tailX !== null) s += `<path d="M${tailX - 14},${y + h - 2} L${tailX + 14 * tailDir},${y + h + 30} L${tailX + 16},${y + h - 2}Z" fill="#fff" stroke="${C.ink}" stroke-width="4" stroke-linejoin="round"/><rect x="${tailX - 12}" y="${y + h - 6}" width="26" height="6" fill="#fff"/>`;
  s += TW(x + w / 2, y + 15 + size * .65, lines, size, C.ink, 700, 'middle', 1.3);
  return `<g opacity="${o}">${s}</g>`;
}

// ---------- characters ----------
// Each character is drawn around (0,0) = centre of the head; the body reaches y≈170.
// Options: talk (mouth moves), wave (arm waves), mood: happy|sad|worried|flat, sweat, zzz, shake.
function mei(t, o = {}) {
  const talk = o.talk ? Math.abs(Math.sin(t * 14)) : 0;
  const wave = o.wave ? Math.sin(t * 9) * 22 : 0;
  const blink = (t % 3.7) < .12 ? .15 : 1;
  return `
  <path d="M-62,170 Q-64,62 0,56 Q64,62 62,170 Z" fill="${C.coral}" stroke="${C.ink}" stroke-width="4"/>
  <path d="M-36,170 L-32,86 Q0,96 32,86 L36,170Z" fill="#fff" stroke="${C.ink}" stroke-width="3"/>
  <path d="M-8,124 q8,-14 16,0 q-8,10 -16,0z" fill="${C.green}"/>
  ${o.wave ? `<g transform="translate(52,80) rotate(${-140 + wave})"><rect x="-10" y="0" width="20" height="70" rx="10" fill="${C.coral}" stroke="${C.ink}" stroke-width="4"/><circle cx="0" cy="74" r="13" fill="#F5C9A0" stroke="${C.ink}" stroke-width="3"/></g>` : `<g transform="translate(52,80) rotate(-20)"><rect x="-10" y="0" width="20" height="66" rx="10" fill="${C.coral}" stroke="${C.ink}" stroke-width="4"/></g>`}
  <g transform="translate(-52,80) rotate(20)"><rect x="-10" y="0" width="20" height="66" rx="10" fill="${C.coral}" stroke="${C.ink}" stroke-width="4"/></g>
  <circle cx="0" cy="0" r="50" fill="#F5C9A0" stroke="${C.ink}" stroke-width="4"/>
  <circle cx="0" cy="-66" r="22" fill="#3B3B4F"/>
  <path d="M-52,4 Q-56,-58 0,-58 Q56,-58 52,4 Q46,-30 0,-30 Q-46,-30 -52,4Z" fill="#3B3B4F"/>
  <ellipse cx="-18" cy="4" rx="5.5" ry="${6 * blink}" fill="${C.ink}"/><ellipse cx="18" cy="4" rx="5.5" ry="${6 * blink}" fill="${C.ink}"/>
  <circle cx="-30" cy="20" r="8" fill="#FF9E9E" opacity=".6"/><circle cx="30" cy="20" r="8" fill="#FF9E9E" opacity=".6"/>
  ${talk > .05 ? `<ellipse cx="0" cy="26" rx="10" ry="${3 + talk * 7}" fill="${C.ink}"/>` : `<path d="M-14,22 Q0,36 14,22" fill="none" stroke="${C.ink}" stroke-width="4" stroke-linecap="round"/>`}`;
}
// Generic person. Extra options: shirt, skin, hair, long (hair), glasses, tie, lanyard, seed (blink offset).
function person(t, o = {}) {
  const shirt = o.shirt || '#7FB2E5', skin = o.skin || '#E8B98F', hair = o.hair || '#232331';
  const blink = (t % (3.3 + (o.seed || 0) * .4)) < .12 ? .15 : 1;
  const talk = o.talk ? Math.abs(Math.sin(t * 14)) : 0;
  const sh = o.shake ? Math.sin(t * 60) * 3 : 0;
  let s = `<g transform="translate(${sh},0)">`;
  s += `<path d="M-58,170 Q-60,64 0,58 Q60,64 58,170 Z" fill="${shirt}" stroke="${C.ink}" stroke-width="4"/>`;
  s += `<path d="M-16,60 L0,78 L16,60" fill="#fff" stroke="${C.ink}" stroke-width="3"/>`;
  if (o.tie) s += `<path d="M0,72 L-8,84 L0,138 L8,84Z" fill="${C.red}" stroke="${C.ink}" stroke-width="2.5"/>`;
  if (o.lanyard) s += `<path d="M-20,62 L-8,112 M20,62 L8,112" stroke="#2E6FD8" stroke-width="4"/><rect x="-17" y="108" width="34" height="42" rx="5" fill="#fff" stroke="${C.ink}" stroke-width="3"/><rect x="-11" y="116" width="22" height="11" fill="${C.sky}"/>`;
  const arm = (x, rot) => `<g transform="translate(${x},80) rotate(${rot})"><rect x="-10" y="0" width="20" height="66" rx="10" fill="${shirt}" stroke="${C.ink}" stroke-width="4"/><circle cx="0" cy="70" r="11" fill="${skin}" stroke="${C.ink}" stroke-width="3"/></g>`;
  if (o.wave) { const w = Math.sin(t * 9) * 18; s += arm(-50, 150 - w) + arm(50, -150 + w); }
  else if (o.point) s += arm(-50, 20) + arm(50, -100);   // right arm out to the side
  else s += arm(-50, 20) + arm(50, -20);
  s += `<circle cx="0" cy="0" r="50" fill="${skin}" stroke="${C.ink}" stroke-width="4"/>`;
  if (o.long) s += `<path d="M-54,40 Q-60,-58 0,-58 Q60,-58 54,40 Q48,-24 0,-30 Q-48,-24 -54,40Z" fill="${hair}"/>`;
  else s += `<path d="M-51,-4 Q-56,-60 0,-60 Q56,-60 51,-4 Q46,-30 18,-34 L10,-26 L2,-36 Q-30,-32 -51,-4Z" fill="${hair}"/>`;
  const sleepy = o.sleepy ? .25 : 1;
  s += `<ellipse cx="-19" cy="4" rx="5.5" ry="${6 * blink * sleepy}" fill="${C.ink}"/><ellipse cx="19" cy="4" rx="5.5" ry="${6 * blink * sleepy}" fill="${C.ink}"/>`;
  if (o.glasses) s += `<circle cx="-19" cy="3" r="15" fill="none" stroke="${C.ink}" stroke-width="3.5"/><circle cx="19" cy="3" r="15" fill="none" stroke="${C.ink}" stroke-width="3.5"/><path d="M-4,2 H4" stroke="${C.ink}" stroke-width="3.5"/>`;
  const mood = o.mood || 'happy';
  if (talk > .05) s += `<ellipse cx="0" cy="30" rx="9" ry="${3 + talk * 6}" fill="${C.ink}"/>`;
  else if (mood === 'sad') s += `<path d="M-13,34 Q0,22 13,34" fill="none" stroke="${C.ink}" stroke-width="4" stroke-linecap="round"/>`;
  else if (mood === 'worried') s += `<path d="M-14,31 q7,-6 14,0 t14,0" fill="none" stroke="${C.ink}" stroke-width="4" stroke-linecap="round"/>`;
  else if (mood === 'flat') s += `<path d="M-11,30 H11" stroke="${C.ink}" stroke-width="4" stroke-linecap="round"/>`;
  else s += `<path d="M-14,25 Q0,39 14,25" fill="none" stroke="${C.ink}" stroke-width="4" stroke-linecap="round"/>`;
  if (mood === 'sad' || mood === 'worried') s += `<path d="M-30,-16 L-10,-11 M30,-16 L10,-11" stroke="${C.ink}" stroke-width="3.5" stroke-linecap="round"/>`;
  if (o.sweat) { for (let k = 0; k < 2; k++) { const u = ((t * 1.2 + k * .5) % 1); s += `<path d="M${56 + k * 10},${-30 + u * 40} q-7,12 0,16 q7,-4 0,-16z" fill="${C.sky}" stroke="${C.ink}" stroke-width="2" opacity="${1 - u}"/>`; } }
  if (o.zzz) s += `<text x="58" y="${-50 - (t * 12 % 20)}" font-size="26" font-weight="800" fill="${C.grey}">z</text><text x="74" y="${-74 - (t * 12 % 20)}" font-size="20" font-weight="800" fill="${C.grey}">z</text>`;
  return s + '</g>';
}
// Ben = person with glasses, tie and lanyard
const ben = (t, o = {}) => person(t, { glasses: true, tie: true, lanyard: true, shirt: '#7FB2E5', ...o });

// ---------- backgrounds ----------
function paperBg() {
  let s = `<rect width="1280" height="720" fill="${C.bg}"/>`;
  for (let i = 0; i < 1280; i += 40) s += `<line x1="${i}" y1="0" x2="${i}" y2="720" stroke="#F3E6D2" stroke-width="1.5"/>`;
  for (let j = 0; j < 720; j += 40) s += `<line x1="0" y1="${j}" x2="1280" y2="${j}" stroke="#F3E6D2" stroke-width="1.5"/>`;
  return s;
}
// Tiled kitchen: wall tiles, optional window, worktop at y=470, cupboard doors below
function kitchen(withWindow = true) {
  let s = `<rect width="1280" height="720" fill="#EAF4F4"/>`;
  for (let x = 0; x < 1280; x += 48) s += `<line x1="${x}" y1="0" x2="${x}" y2="470" stroke="#D3E6E6" stroke-width="2"/>`;
  for (let y = 0; y < 470; y += 48) s += `<line x1="0" y1="${y}" x2="1280" y2="${y}" stroke="#D3E6E6" stroke-width="2"/>`;
  if (withWindow) s += `<rect x="60" y="40" width="260" height="170" rx="10" fill="${C.lsky}" stroke="${C.ink}" stroke-width="4"/><path d="M190,40 V210 M60,125 H320" stroke="${C.ink}" stroke-width="4"/>`;
  s += `<rect x="0" y="470" width="1280" height="26" fill="${C.wood}" stroke="${C.ink}" stroke-width="4"/>`;
  s += `<rect x="0" y="496" width="1280" height="224" fill="#F7E7CF"/>`;
  for (let x = 20; x < 1280; x += 210) s += card(x, 516, 190, 190, '#FBEFDC', C.ink, 8, 3) + `<rect x="${x + 80}" y="530" width="30" height="8" rx="4" fill="${C.grey}"/>`;
  return s;
}
// Shop or café front with a sign; label is the sign text
function shopFront(label = 'CAFE') {
  let s = `<rect width="1280" height="720" fill="#FFE9CC"/>`;
  for (let i = 0; i < 14; i++) s += `<rect x="${i * 92}" y="0" width="46" height="520" fill="#FFF1DC"/>`;
  s += `<rect x="0" y="520" width="1280" height="200" fill="${C.wood}"/><rect x="0" y="520" width="1280" height="16" fill="#A86E3E"/>`;
  s += `<g transform="translate(40,26)">${card(0, 0, 300, 58, C.green, C.ink, 29, 4)}<text x="150" y="31" font-size="28" font-weight="800" fill="#fff" text-anchor="middle" dominant-baseline="middle">${esc(label)}</text></g>`;
  return s;
}

// ---------- word anchors ----------
// at(i, "phrase") returns the time (seconds into scene i, 0-based) when the phrase starts.
// It matches the script's spoken words or caption words, so write phrases as they appear in the script.
const nrm = s => s.toLowerCase().replace(/[^a-z0-9]/g, '');
function at(i, phrase, from = 0) {
  const ws = window.WORDS[i], p = phrase.split(' ').map(nrm).filter(Boolean);
  for (let j = 0; j + p.length <= ws.length; j++) {
    if (ws[j][1] < from) continue;
    if (p.every((t, k) => ws[j + k][0] === t || ws[j + k][3] === t)) return ws[j][1];
  }
  throw new Error(`anchor not found: scene ${i + 1} "${phrase}"`);
}
// talking(i, "MEI", lt): true while that character speaks (dialogue scripts only)
function talking(i, who, lt) {
  const L = window.LINES && window.LINES[`S${i + 1}`];
  return !!L && L.some(l => l.who === who && lt >= l.start && lt <= l.end);
}

// ---------- captions ----------
function caption(i, lt) {
  const c = (window.CAPS[i] || []).find(c => lt >= c[0] && lt <= c[1] + .15);
  if (!c) return '';
  const lines = wrap(c[2], 78);
  const h = lines.length * 30 + 22, y0 = 708 - h;
  const o = Math.min(fi(lt, c[0], .15), 1 - fi(lt, c[1], .15));
  return `<g opacity="${o}"><rect x="140" y="${y0}" width="1000" height="${h}" rx="14" fill="${C.ink}" opacity=".85"/>` + lines.map((l, k) => `<text x="640" y="${y0 + 26 + k * 30}" font-size="23" fill="#fff" font-weight="600" text-anchor="middle" dominant-baseline="middle">${esc(l)}</text>`).join('') + '</g>';
}

// ---------- frame dispatcher ----------
// scenes.js must define titleCard(t), credits(t) and SCENES = [s1, s2, ...] (one per narration clip).
function frame(T0) {
  let body, fade = 1;
  if (T0 < TITLE) { body = titleCard(T0); fade = Math.min(fi(T0, 0, .4), 1 - fi(T0, TITLE - .35, .35)); }
  else {
    let i = 0; for (let k = 0; k < NS; k++) if (T0 >= starts[k]) i = k;
    const end = starts[i] + AUD[i] + GAP;
    if (i === NS - 1 && T0 >= end) { const lt = T0 - end; body = credits(lt); fade = Math.min(fi(lt, 0, .4), 1 - fi(lt, CREDITS - .6, .6)); }
    else { const lt = T0 - starts[i]; body = SCENES[i](lt); fade = Math.min(fi(lt, 0, .3), 1 - fi(lt, AUD[i] + GAP - .3, .3)); }
  }
  document.getElementById('stage').innerHTML = `<rect width="1280" height="720" fill="${C.bg}"/><g opacity="${fade}">${body}</g>`;
}
window.seek = frame;
