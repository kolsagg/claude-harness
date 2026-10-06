// motion-film start: last script on the page. Wires FILM + THEME into window.ready / window.renderFrame.
// FILM contract (inline film script):
//   duration   seconds (required; no fixed length, the storyboard decides)
//   drawScene(t)   the film's own objects, drawn between THEME.background and THEME.foreground
//   init()     optional, may be async (preload images with loadImage, measure text)
// THEME contract (profile theme.js, optional): init(), background(t), foreground(t) and anything else
// the profile documents (e.g. intro/outro timeline, product particle shape, end card).

const DUR = FILM.duration;
if (!(DUR > 0)) throw new Error('FILM.duration (seconds) is required');
const THEME_ = typeof THEME === 'undefined' ? {} : THEME;

function renderFrame(t) {
  x.setTransform(1, 0, 0, 1, 0, 0); x.globalAlpha = 1; x.globalCompositeOperation = 'source-over'; x.filter = 'none';
  x.fillStyle = PROFILE.bg; x.fillRect(0, 0, W, H);
  if (THEME_.background) { x.save(); THEME_.background(t); x.restore(); }
  x.setTransform(1, 0, 0, 1, 0, 0); x.globalAlpha = 1; x.globalCompositeOperation = 'source-over'; x.filter = 'none';
  x.save(); FILM.drawScene(t); x.restore();
  x.setTransform(1, 0, 0, 1, 0, 0); x.globalAlpha = 1; x.globalCompositeOperation = 'source-over'; x.filter = 'none';
  if (THEME_.foreground) { x.save(); THEME_.foreground(t); x.restore(); }
}

window.ready = (async () => {
  try { await Promise.all((PROFILE.fontProbes || []).map(f => document.fonts.load(f, PROFILE.fontProbeText || 'Aa'))); } catch (e) {}
  await document.fonts.ready;
  if (THEME_.init) await THEME_.init();
  if (FILM.init) await FILM.init();
  window.FILM_META = { duration: DUR, portrait: PORTRAIT, width: W, height: H };
  return PROFILE.fontCheck ? document.fonts.check(PROFILE.fontCheck) : true;
})();
window.renderFrame = renderFrame;
if (!location.search.includes('render')) {
  window.ready.then(() => { const t0 = performance.now(); const loop = () => { renderFrame(((performance.now() - t0) / 1000) % DUR); requestAnimationFrame(loop); }; loop(); });
}
