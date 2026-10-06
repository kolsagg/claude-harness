// motion-film core: theme-agnostic canvas engine.
//
// film.html loads, in this order (render.js serves /engine and /profile over a local http server):
//   /profile/profile.js   -> PROFILE (colors, fonts, cta, url, language)
//   /engine/core.js       -> this file: canvas, PORTRAIT, W/H, math, easing, UI primitives, captions
//   /profile/theme.js     -> THEME (backdrop, chrome, end card)
//   <inline film script>  -> const FILM = { duration, drawScene(t), init() ... }
//   /engine/start.js      -> waits for fonts + THEME.init + FILM.init, exposes window.ready / renderFrame
// Because core and theme load BEFORE the film script, PORTRAIT, W, H, L and every helper are
// usable at the film's top level (the old per-project base.js loaded last and bit us there).
//
// Everything is deterministic: a frame is a pure function of t. Never use Date/performance/Math.random
// inside drawScene; use rng(seed) / hash3.

const PORTRAIT = /[?&]portrait(&|$)/.test(location.search);
const W = PORTRAIT ? 1080 : 1920, H = PORTRAIT ? 1920 : 1080, CX = W / 2, CY = H / 2;
const cv = document.createElement('canvas');
cv.width = W; cv.height = H;
document.body.appendChild(cv);
const x = cv.getContext('2d');
const F = PROFILE.fontStack;
const C = PROFILE.colors;

// Layout slots. Themes may Object.assign(L, ...) to move captions / chrome; films read L.
// Portrait safe areas for Reels/TikTok/Shorts: keep UI out of the top 250 px and bottom 330 px.
const L = PORTRAIT
  ? { bigY: 1500, smallY: 1566, capMax: 900, navX: 70, navY: 200, safeTop: 250, safeBottom: 1590, margin: 60 }
  : { bigY: 985, smallY: 1036, capMax: 1760, navX: 96, navY: 84, safeTop: 40, safeBottom: 930, margin: 60 };

const rgba = (c, a) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;
const mix = (a, b, p) => [a[0] + (b[0] - a[0]) * p, a[1] + (b[1] - a[1]) * p, a[2] + (b[2] - a[2]) * p];

// ---------- math ----------
const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const seg = (t, a, b) => clamp((t - a) / (b - a));
const lerp = (a, b, p) => a + (b - a) * p;
const eOutExpo = p => p >= 1 ? 1 : 1 - Math.pow(2, -10 * p);
const eInExpo = p => p <= 0 ? 0 : Math.pow(2, 10 * p - 10);
const eInOut = p => p < .5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;
const eInOutQ = p => p < .5 ? 8 * p * p * p * p : 1 - Math.pow(-2 * p + 2, 4) / 2;
const eOutCubic = p => 1 - Math.pow(1 - p, 3);
const eOutBack = p => { const c1 = 1.8, c3 = c1 + 1; return 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2); };
function rng(s) { return () => { s |= 0; s = s + 0x6D2B79F5 | 0; let t = Math.imul(s ^ s >>> 15, 1 | s); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function hash3(i, j, k) { let h = (i * 374761393 + j * 668265263 + k * 2147483647) | 0; h = Math.imul(h ^ (h >>> 13), 1274126177); return ((h ^ (h >>> 16)) >>> 0) / 4294967296; }
function rotYP(px, py, pz, yaw, pitch) {
  const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
  const x1 = px * cy - pz * sy, z1 = px * sy + pz * cy;
  return [x1, py * cp - z1 * sp, py * sp + z1 * cp];
}
// Uppercase for UI labels: locale-aware for words, plain for brand/product names (Acme -> ACME, not ACİME).
const upper = (str, brand = false) => brand ? str.toUpperCase() : str.toLocaleUpperCase(PROFILE.locale || 'en');

// ---------- UI primitives ----------
function circle(cx, cy, r) { x.beginPath(); x.arc(cx, cy, r, 0, Math.PI * 2); }
function glow(cx, cy, r, col, a) {
  if (a <= 0) return;
  const g = x.createRadialGradient(cx, cy, 0, cx, cy, r);
  g.addColorStop(0, rgba(col, a)); g.addColorStop(0.4, rgba(col, a * 0.3)); g.addColorStop(1, rgba(col, 0));
  x.fillStyle = g; x.fillRect(cx - r, cy - r, r * 2, r * 2);
}
function text(str, px, py, size, weight, col, a, align = 'left', spacing = 0) {
  if (a <= 0.001) return;
  x.save(); x.globalAlpha = clamp(a); x.font = `${weight} ${size}px ${F}`; x.letterSpacing = `${spacing}px`;
  x.textAlign = align; x.textBaseline = 'alphabetic'; x.fillStyle = rgba(col, 1);
  x.fillText(str, px, py); x.restore();
}
// Centred caption that blurs in and drifts out; wraps to two lines when wider than L.capMax.
function caption(str, y, size, weight, col, t, tin, tout, colA = 1) {
  if (t < tin || t > tout + 0.4) return;
  const pi = eOutExpo(seg(t, tin, tin + 0.7)), po = eInOut(seg(t, tout, tout + 0.35));
  const a = pi * (1 - po);
  if (a <= 0) return;
  x.save(); x.globalAlpha = a * colA;
  x.font = `${weight} ${size}px ${F}`; x.letterSpacing = size > 40 ? '-1.5px' : '0px';
  x.textAlign = 'center'; x.textBaseline = 'alphabetic'; x.fillStyle = rgba(col, 1);
  if (pi < 1) x.filter = `blur(${(1 - pi) * 8}px)`;
  const yy = y + (1 - pi) * 24 - po * 12;
  if (x.measureText(str).width <= L.capMax) x.fillText(str, CX, yy);
  else {
    const sp = [...str.matchAll(/ /g)].map(m => m.index);
    const cut = sp.reduce((b, i) => Math.abs(i - str.length / 2) < Math.abs(b - str.length / 2) ? i : b, sp[0] ?? str.length);
    x.fillText(str.slice(0, cut), CX, yy - size * 1.15); x.fillText(str.slice(cut + 1), CX, yy);
  }
  x.restore();
}
const bigCaption = (str, t, tin, tout) => caption(str, L.bigY, 58, 300, C.ink, t, tin, tout);
const smallCaption = (str, t, tin, tout) => caption(str, L.smallY, 26, 400, C.pale, t, tin, tout, 0.85);
function drawLetters(ctx, str, cx, cy, size, weight, col, t, t0, stagger, dur, spacing = 0, rise = 40) {
  ctx.font = `${weight} ${size}px ${F}`; ctx.letterSpacing = '0px';
  const ws = [...str].map(ch => ctx.measureText(ch).width + spacing);
  let p0 = cx - (ws.reduce((a, b) => a + b, 0) - spacing) / 2;
  ctx.textBaseline = 'middle'; ctx.textAlign = 'left';
  [...str].forEach((ch, i) => {
    const p = eOutExpo(seg(t, t0 + i * stagger, t0 + i * stagger + dur));
    if (p > 0) {
      ctx.save(); ctx.globalAlpha *= p; ctx.fillStyle = rgba(col, 1);
      if (p < 1) ctx.filter = `blur(${(1 - p) * 12}px)`;
      ctx.fillText(ch, p0, cy + (1 - p) * rise); ctx.restore();
    }
    p0 += ws[i];
  });
}
// Glass panel: dark rounded card. Draw content after it.
function panel(px, py, w, h, r = 14, border = C.blue, borderA = 0.3, fill = PROFILE.panelFill || 'rgba(8,16,38,0.9)') {
  x.save();
  x.shadowColor = 'rgba(0,0,0,0.6)'; x.shadowBlur = 30; x.shadowOffsetY = 12;
  x.fillStyle = fill; x.beginPath(); x.roundRect(px, py, w, h, r); x.fill();
  x.shadowColor = 'transparent'; x.strokeStyle = rgba(border, borderA); x.lineWidth = 1.5; x.stroke();
  x.restore();
}
// Pill tag centred at (px, py). size >= 20 keeps it readable on phones.
function pill(label, px, py, col, sc = 1, alpha = 1, size = 20) {
  if (alpha <= 0.001 || sc <= 0.01) return;
  x.save(); x.globalAlpha = clamp(alpha); x.translate(px, py); x.scale(sc, sc);
  x.font = `700 ${size}px ${F}`; x.letterSpacing = '1.5px';
  const tw = x.measureText(label).width + size * 2.4, th = size * 1.8;
  x.fillStyle = PROFILE.panelFill || 'rgba(8,16,38,0.98)'; x.beginPath(); x.roundRect(-tw / 2, -th / 2, tw, th, th / 2); x.fill();
  x.strokeStyle = rgba(col, 0.9); x.lineWidth = 1.4; x.stroke();
  x.fillStyle = rgba(col, 1); x.textAlign = 'center'; x.textBaseline = 'middle';
  x.fillText(label, 0, 1);
  x.restore();
}
function drawLock(px, py, openP, alpha, shake = 0, col = C.red) {
  if (alpha <= 0.001) return;
  x.save(); x.globalAlpha = clamp(alpha); x.translate(px + shake, py);
  glow(0, 0, 60, col, 0.4 * (1 - openP));
  x.strokeStyle = rgba(col, 1); x.lineWidth = 5; x.lineCap = 'round';
  x.save(); x.translate(11, -2); x.rotate(-openP * 0.9); x.translate(-11, 2 - openP * 8);
  x.beginPath(); x.moveTo(-11, -2); x.lineTo(-11, -12); x.arc(0, -12, 11, Math.PI, 0); x.lineTo(11, -2); x.stroke();
  x.restore();
  x.fillStyle = rgba(col, 1); x.beginPath(); x.roundRect(-19, -4, 38, 30, 7); x.fill();
  x.fillStyle = PROFILE.bg; circle(0, 9, 4.5); x.fill();
  x.restore();
}
function drawAvatar(px, py, sc, flip, col, alpha) {
  if (alpha <= 0.001 || sc <= 0) return;
  x.save(); x.globalAlpha = clamp(alpha); x.translate(px, py); x.scale(sc * Math.max(0.02, flip), sc);
  glow(0, 0, 180, col, 0.28);
  x.fillStyle = '#081026'; circle(0, 0, 64); x.fill();
  x.strokeStyle = rgba(col, 1); x.lineWidth = 3.5; x.stroke();
  x.fillStyle = rgba(C.ink, 0.95); circle(0, -14, 17); x.fill();
  x.beginPath(); x.ellipse(0, 30, 31, 22, 0, Math.PI, 0); x.closePath(); x.fill();
  x.restore();
}
function beam(ax, ay, bx, by, p0, p1, col, a, w = 2.5, dash = null) {
  if (a <= 0 || p1 <= p0) return;
  x.save(); x.strokeStyle = rgba(col, a); x.lineWidth = w; x.lineCap = 'round';
  if (dash) x.setLineDash(dash);
  x.beginPath(); x.moveTo(lerp(ax, bx, p0), lerp(ay, by, p0)); x.lineTo(lerp(ax, bx, p1), lerp(ay, by, p1)); x.stroke();
  x.restore();
}
// Glowing packets travelling a->b; ext (0..1) limits how far along they have reached.
function flow(ax, ay, bx, by, t, ext, col, a = 1, n = 7, speed = 0.9) {
  x.save(); x.globalCompositeOperation = 'lighter';
  for (let j = 0; j < n; j++) {
    const u = (t * speed + j / n) % 1;
    if (u > ext) continue;
    const px = lerp(ax, bx, u), py = lerp(ay, by, u), f = Math.sin(u * Math.PI);
    glow(px, py, 10, col, 0.5 * a * f);
    x.fillStyle = rgba(C.ink, a * f); x.fillRect(px - 1.3, py - 1.3, 2.6, 2.6);
  }
  x.restore();
}
function drawCursor(px, py, sc, alpha) {
  if (alpha <= 0.001) return;
  x.save(); x.globalAlpha = clamp(alpha); x.translate(px, py); x.scale(sc, sc);
  x.shadowColor = 'rgba(0,0,0,0.5)'; x.shadowBlur = 12; x.shadowOffsetY = 4;
  x.fillStyle = '#ffffff'; x.strokeStyle = '#02040c'; x.lineWidth = 2.5; x.lineJoin = 'round';
  x.beginPath(); x.moveTo(0, 0); x.lineTo(0, 40); x.lineTo(10, 30); x.lineTo(18, 46); x.lineTo(25, 43); x.lineTo(17, 27); x.lineTo(30, 27); x.closePath();
  x.fill(); x.shadowColor = 'transparent'; x.stroke();
  x.restore();
}
// Particles sucked into a point (q runs 0->1).
function absorb(px, py, q, col, seed) {
  if (q <= 0 || q >= 1) return;
  x.save(); x.globalCompositeOperation = 'lighter';
  for (let j = 0; j < 28; j++) {
    const a = j / 28 * Math.PI * 2 + seed * 3.1 + hash3(seed, j, 1) * 0.8;
    const d = lerp(70 + 70 * hash3(seed, j, 2), 0, eInOut(clamp(q * (1.1 + hash3(seed, j, 3) * 0.6))));
    x.globalAlpha = (1 - q) * 0.9;
    x.fillStyle = rgba(j % 3 ? col : C.ink, 1);
    x.fillRect(px + Math.cos(a) * d - 1.3, py + Math.sin(a) * d - 1.3, 2.6, 2.6);
  }
  x.restore();
}
// Checkmark drawn progressively (p 0..1), starting at (px, py).
function check(px, py, p, col, w = 3.5, s = 1) {
  if (p <= 0) return;
  x.save(); x.strokeStyle = rgba(col, 1); x.lineWidth = w; x.lineCap = 'round'; x.lineJoin = 'round';
  x.beginPath(); x.moveTo(px, py); x.lineTo(px + 6 * s * clamp(p * 2), py + 6 * s * clamp(p * 2));
  if (p > 0.5) x.lineTo(px + (6 + 11 * clamp(p * 2 - 1)) * s, py + (6 - 14 * clamp(p * 2 - 1)) * s);
  x.stroke(); x.restore();
}
// Load an image (SVG, PNG) and decode it before the first frame; use inside an async init().
async function loadImage(src) { const img = new Image(); img.src = src; await img.decode(); return img; }
