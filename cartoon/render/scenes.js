// Demo scenes for script.example.md ("How Does a Kettle Know When to Stop?").
// Replace these with your own. Rules of thumb:
//  - one function per script scene, taking lt = seconds since the scene started;
//  - cue every animation to a spoken phrase with at(sceneIndex, "phrase"), never to fixed seconds,
//    so a new voice or speed never breaks the timing;
//  - end each scene with caption(sceneIndex, lt).

// ---------- props ----------
// Kettle drawn with the centre of its base at (0,0); about 300 units tall.
// o.on: switch on (red light); o.steam: 0..1 steam from the spout; o.cut: cutaway view
// o.water: 0..1 boiling bubbles; o.tube: 0..1 steam moving down the tube; o.disc: 0..1 highlight on the disc
function kettle(t, o = {}) {
  let s = '';
  // steam puffs from the spout
  const st = o.steam || 0;
  if (st > .01) for (let k = 0; k < 7; k++) {
    const u = (t * .55 + k / 7) % 1;
    s += `<circle cx="${-182 - u * 30 + Math.sin(t * 2 + k) * 10}" cy="${-262 - u * 140}" r="${12 + u * 22}" fill="#fff" stroke="${C.grey}" stroke-width="2" opacity="${(1 - u) * st * .9}"/>`;
  }
  // handle
  s += `<path d="M78,-236 Q170,-230 160,-140 Q152,-70 96,-52" fill="none" stroke="${C.ink}" stroke-width="30" stroke-linecap="round"/><path d="M78,-236 Q170,-230 160,-140 Q152,-70 96,-52" fill="none" stroke="#3D4152" stroke-width="22" stroke-linecap="round"/>`;
  // spout
  s += `<path d="M-96,-176 L-176,-258 L-158,-270 L-84,-214Z" fill="${C.steel}" stroke="${C.ink}" stroke-width="4" stroke-linejoin="round"/>`;
  // body
  s += `<path d="M-112,-12 L-88,-252 Q0,-268 88,-252 L112,-12Z" fill="${o.cut ? '#EEF2F6' : C.steel}" stroke="${C.ink}" stroke-width="5" stroke-linejoin="round"/>`;
  if (!o.cut) s += `<path d="M-70,-230 L-86,-40" stroke="#fff" stroke-width="10" stroke-linecap="round" opacity=".6"/>`;
  if (o.cut) {
    // water with boiling bubbles
    s += `<path d="M-104,-90 Q0,${-100 + Math.sin(t * 6) * 4} 104,-90 L108,-16 L-108,-16Z" fill="${C.sky}" opacity=".85"/>`;
    const w = o.water || 0;
    for (let k = 0; k < 14; k++) { const u = (t * (.8 + rnd(k) * .6) + rnd(k + 9)) % 1; if (w > .01) s += `<circle cx="${-90 + rnd(k) * 170}" cy="${-20 - u * 70}" r="${3 + rnd(k + 3) * 5}" fill="#fff" opacity="${w * (1 - u * .6)}"/>`; }
    // steam tube: from the top of the kettle, down the back, to the disc in the base of the handle
    const tube = 'M70,-236 L88,-210 L100,-120 L104,-58';
    s += `<path d="${tube}" fill="none" stroke="${C.ink}" stroke-width="16" stroke-linecap="round"/><path d="${tube}" fill="none" stroke="${o.tube > .01 ? '#FFE6A8' : '#fff'}" stroke-width="9" stroke-linecap="round"/>`;
    const tb = o.tube || 0;
    if (tb > .01) for (let k = 0; k < 5; k++) {
      const u = (t * .7 + k / 5) % 1, pts = [[70, -236], [88, -210], [100, -120], [104, -58]];
      const seg = Math.min(2, Math.floor(u * 3)), f = u * 3 - seg, [x0, y0] = pts[seg], [x1, y1] = pts[seg + 1];
      s += `<circle cx="${lerp(x0, x1, f)}" cy="${lerp(y0, y1, f)}" r="5" fill="#fff" stroke="${C.ink}" stroke-width="1.5" opacity="${tb}"/>`;
    }
    // the two-metal disc
    const d = o.disc || 0;
    if (d > .01) s += `<circle cx="104" cy="-46" r="${26 + 6 * Math.sin(t * 6) * d}" fill="${C.yellow}" opacity="${.45 * d}"/>`;
    s += `<ellipse cx="104" cy="-46" rx="16" ry="6" fill="${C.copper}" stroke="${C.ink}" stroke-width="3"/>`;
  }
  // lid
  s += `<path d="M-80,-252 Q0,-292 80,-252Z" fill="#9AA3B1" stroke="${C.ink}" stroke-width="4"/><rect x="-16" y="-292" width="32" height="18" rx="7" fill="#3D4152" stroke="${C.ink}" stroke-width="3"/>`;
  // base and switch
  s += `<rect x="-132" y="-14" width="264" height="30" rx="12" fill="#3D4152" stroke="${C.ink}" stroke-width="4"/>`;
  const sw = o.on ? -22 : 10;
  s += `<g transform="translate(106,-46) rotate(${sw})"><rect x="0" y="-9" width="44" height="18" rx="8" fill="${C.ink}"/></g>`;
  s += `<circle cx="-100" cy="1" r="7" fill="${o.on ? C.red : '#6B6F80'}" stroke="${C.ink}" stroke-width="2"/>`;
  return s;
}
// Two strips of metal bonded together; bend: -1..1 (negative = curls up, positive = curls down)
function bimetal(bend, w = 420) {
  const h = 22, k = bend * 90;
  const arc = dy => `M${-w / 2},${dy} Q0,${dy + k * 2} ${w / 2},${dy}`;
  return `<path d="${arc(0)}" fill="none" stroke="${C.ink}" stroke-width="${h + 8}" stroke-linecap="round"/>` +
    `<path d="${arc(-h / 4)}" fill="none" stroke="${C.copper}" stroke-width="${h / 2}" stroke-linecap="butt"/>` +
    `<path d="${arc(h / 4)}" fill="none" stroke="${C.steel}" stroke-width="${h / 2}" stroke-linecap="butt"/>`;
}
function thermometer(level) {
  const top = -150, bot = 110, y = lerp(bot, top + 20, cl(level));
  return `<rect x="-18" y="${top}" width="36" height="${bot - top + 10}" rx="18" fill="#fff" stroke="${C.ink}" stroke-width="4"/><rect x="-8" y="${y}" width="16" height="${bot - y + 10}" rx="8" fill="${C.red}"/><circle cx="0" cy="${bot + 24}" r="28" fill="${C.red}" stroke="${C.ink}" stroke-width="4"/>`;
}
function plug(power) {
  return `<rect x="-60" y="-40" width="120" height="80" rx="14" fill="#fff" stroke="${C.ink}" stroke-width="4"/><rect x="-30" y="-14" width="12" height="28" rx="3" fill="${C.ink}"/><rect x="18" y="-14" width="12" height="28" rx="3" fill="${C.ink}"/>` +
    `<path d="M-14,-110 L10,-110 L-2,-80 L18,-80 L-16,-40 L-6,-70 L-24,-70Z" fill="${C.yellow}" stroke="${C.ink}" stroke-width="3" stroke-linejoin="round" opacity="${power}"/>`;
}
const burst = (label, s = 1) => `<g transform="scale(${s})"><path d="${Array.from({ length: 16 }, (_, k) => { const a = k / 16 * Math.PI * 2, r = k % 2 ? 50 : 82; return `${k ? 'L' : 'M'}${Math.cos(a) * r * 1.4},${Math.sin(a) * r}`; }).join(' ')}Z" fill="${C.yellow}" stroke="${C.ink}" stroke-width="4"/>${heading(label, 34)}</g>`;

// ---------- scenes ----------
function titleCard(t) {
  let s = kitchen(false);
  s += G(640, 110, pop(t, .2, .6), card(-500, -62, 1000, 124, C.yellow, C.ink, 30, 5) + heading('How Does a Kettle Know When to Stop?', 46));
  s += G(640, 206, 1, heading('A one-minute explainer', 26, C.dgreen), fi(t, .8));
  s += G(640, 470, pop(t, 1.0) * .62, kettle(t, { steam: .6 }));
  s += G(330, 330, pop(t, 1.3) * .8, mei(t, { wave: true })) + G(950, 330, pop(t, 1.6) * .8, ben(t));
  return s;
}
function s1(lt) {
  const A = (p, f = 0) => at(0, p, f);
  const tFlick = A('flicks the switch'), tWalk = A('walks away'), tLater = A('a few minutes'), tClick = A('click'),
    tNo = A('no screen'), tChip = A('no chip'), tApp = A('no app'), tQ = A('so how does');
  let s = kitchen();
  const on = lt >= tFlick + .3 && lt < tClick;
  const steam = lt < tClick ? .2 + .8 * pr(lt, tLater, tClick) : 1 - pr(lt, tClick, tClick + 2.5);
  s += G(700, 470, .9, kettle(lt, { on, steam: lt > tFlick ? steam : 0 }));
  // Mei stands by the kettle, then walks off to the left
  const mx = lerp(470, 150, eio(pr(lt, tWalk, tWalk + 1.4)));
  s += G(mx, 320, .9, mei(lt, { wave: lt > tFlick && lt < tFlick + 1 }));
  if (lt > tLater - .2 && lt < tClick) s += G(1000, 150, fi(lt, tLater - .2), chip(0, 0, 'a few minutes later…', '#fff', 26));
  const c = pop(lt, tClick, .35);
  if (c > .01) s += G(840, 380, c * (1 - fi(lt, tNo - .3, .3)), burst('CLICK!', .9));
  const no = (tt, y, label) => { const p = pop(lt, tt); return p > .01 ? G(1040, y, p * (1 - fi(lt, tQ - .2, .3)), chip(0, 0, label, '#FFD6D6', 28)) : ''; };
  s += no(tNo, 200, '✗ no screen') + no(tChip, 270, '✗ no chip') + no(tApp, 340, '✗ no app');
  const q = pop(lt, tQ);
  if (q > .01) s += G(640, 110, q, card(-420, -48, 840, 96, C.yellow, C.ink, 48, 5) + heading('So how does it know when to stop?', 36));
  return s + caption(0, lt);
}
function s2(lt) {
  const A = (p, f = 0) => at(1, p, f);
  const tTemp = A('a hundred'), tSteam = A('lots of steam'), tTube = A('a small tube'), tDisc = A('thin disc'), tTwo = A('two different metals');
  let s = paperBg();
  const boil = pr(lt, tTemp, tTemp + 1.5);
  s += G(560, 560, 1.3, kettle(lt, { cut: true, on: true, water: boil, steam: pr(lt, tSteam - .5, tSteam + 1), tube: pr(lt, tTube, tTube + 1), disc: pr(lt, tDisc, tDisc + .6) }));
  s += G(230, 420, pop(lt, tTemp), card(-110, -46, 220, 92, '#FFD6D6', C.ink, 20, 4) + heading('100 °C', 44, C.red));
  const lt1 = pop(lt, tTube);
  if (lt1 > .01) s += G(880, 240, lt1, chip(0, 0, 'steam tube', '#FFE6A8', 26)) + `<path d="M820,252 L708,300" stroke="${C.ink}" stroke-width="3" opacity="${lt1}"/>`;
  const lt2 = pop(lt, tDisc);
  if (lt2 > .01) s += G(900, 470, lt2, chip(0, 0, lt >= tTwo ? 'disc of two metals' : 'thin disc', C.yellow, 26)) + `<path d="${lt >= tTwo ? 'M770,476' : 'M832,476'} L705,500" stroke="${C.ink}" stroke-width="3" opacity="${lt2}"/>`;
  s += G(1130, 330, .75, ben(lt, { point: lt > tTube && lt < tTube + 2.5 }), fi(lt, .3));
  return s + caption(1, lt);
}
function s3(lt) {
  const A = (p, f = 0) => at(2, p, f);
  const tWarm = A('warm up'), tBend = A('the disc bends'), tSnap = A('snaps'), tPush = A('pushes the switch'), tCut = A('cuts the power'),
    tBen = A('ben calls'), tMei = A('just calls');
  let s = paperBg();
  const warm = pr(lt, .3, tSnap);
  const dim = 1 - .55 * fi(lt, tBen - .3, .5);
  // slow bend as it warms, then a sudden snap the other way
  const bend = lt < tSnap ? -.15 - .45 * eio(pr(lt, tBend, tSnap)) : lerp(-.6, .7, eb(pr(lt, tSnap, tSnap + .25)));
  let d = G(200, 300, 1, thermometer(warm)) + G(640, 300, 1, bimetal(bend));
  d += G(640, 150, fi(lt, .2), chip(-130, 0, 'copper: grows more', '#FBD9C2', 22) + chip(150, 0, 'steel: grows less', '#E3E8EF', 22));
  if (lt > tSnap - .05) d += G(640, 420, pop(lt, tSnap, .3) * (1 - fi(lt, tSnap + 1.6, .3)), burst('SNAP!', .8));
  const sw = lt < tPush ? -22 : 10;
  d += G(1060, 260, 1, `<rect x="-80" y="-30" width="160" height="60" rx="14" fill="#3D4152" stroke="${C.ink}" stroke-width="4"/><g transform="translate(-40,0) rotate(${sw})"><rect x="0" y="-12" width="90" height="24" rx="10" fill="${C.ink}" stroke="#fff" stroke-width="2"/></g>`) + G(1060, 196, 1, heading('switch', 22), fi(lt, .4));
  d += G(1060, 470, .9, plug(lt < tCut ? .6 + .4 * Math.abs(Math.sin(lt * 5)) : 1 - pr(lt, tCut, tCut + .4)));
  if (lt > tCut) d += G(1060, 560, fi(lt, tCut), chip(0, 0, 'power off', '#fff', 22));
  s += `<g opacity="${dim}">${d}</g>`;
  const b = pop(lt, tBen);
  if (b > .01) s += G(380, 380, b * .85, ben(lt)) + G(380, 205, b, chip(0, 0, 'a tiny bodyguard', '#fff', 26));
  const m = pop(lt, tMei);
  if (m > .01) s += G(860, 380, m * .85, mei(lt, { wave: true })) + G(860, 205, m, chip(0, 0, '“the click”', C.yellow, 30));
  return s + caption(2, lt);
}
function credits(t) {
  const lines = [
    ['How Does a Kettle Know When to Stop?', 42, C.ink, 800],
    ['a demo made with the zero-cost video toolkit', 22, C.grey, 600],
    ['', 10],
    ['Narration: Kokoro-82M (Apache 2.0), voice af_heart · word timings: Whisper large-v3-turbo (MIT)', 17, C.ink, 600],
    ['Drawn as SVG in code, rendered offline with headless Chrome and FFmpeg', 17, C.ink, 600],
    ['', 10],
    ['AI-generated voice and visuals. A simplified explanation: kettle designs vary.', 19, C.coral, 700],
    ['Characters: Mei & Ben', 20, C.dgreen, 700],
  ];
  let s = paperBg(), y = 110;
  lines.forEach(([l, sz, col, w], i) => { if (l) s += `<text x="640" y="${y}" font-size="${sz}" fill="${col}" font-weight="${w}" text-anchor="middle" dominant-baseline="middle" opacity="${fi(t, .2 + i * .15)}">${esc(l)}</text>`; y += sz * 2.2; });
  s += G(560, 520, .5, mei(t, { wave: true })) + G(720, 520, .5, ben(t, { wave: true }));
  return s;
}

const SCENES = [s1, s2, s3];   // one entry per narration clip, in order
