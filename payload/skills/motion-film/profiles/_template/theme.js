// Minimal theme: soft gradient backdrop, brand chrome top-left, end card for the last 2.3 s.
// Replace with the brand's own visual language.
let IMPACT = 0;
Object.assign(L, PORTRAIT
  ? { titleY: 900, titleSize: 110, tagY: 1010, ctaY: 1130, urlY: 1230 }
  : { titleY: 470, titleSize: 140, tagY: 580, ctaY: 690, urlY: 800 });
const THEME = {
  init() { IMPACT = FILM.duration - 2.3; },
  background(t) {
    const g = x.createRadialGradient(CX, CY * 0.8, 0, CX, CY, Math.max(W, H) * 0.8);
    g.addColorStop(0, rgba(mix(C.blue, [0, 0, 0], 0.75), 1)); g.addColorStop(1, PROFILE.bg);
    x.fillStyle = g; x.fillRect(0, 0, W, H);
  },
  foreground(t) {
    const navA = eOutCubic(seg(t, 0.3, 1.0)) * (1 - eInOut(seg(t, IMPACT - 0.6, IMPACT - 0.2)));
    text(upper(PROFILE.brand, true), L.navX, L.navY, 26, 600, C.ink, navA, 'left', 6);
    if (t > IMPACT) {
      const a = eOutCubic(seg(t, IMPACT, IMPACT + 0.6));
      x.fillStyle = PROFILE.bg; x.globalAlpha = a * 0.85; x.fillRect(0, 0, W, H); x.globalAlpha = 1;
      text(FILM.name ? PROFILE.brand + ' ' + FILM.name : PROFILE.brand, CX, L.titleY, L.titleSize, 300, C.ink, eOutExpo(seg(t, IMPACT + 0.15, IMPACT + 0.9)), 'center', -3);
      caption(FILM.tagline || '', L.tagY, 32, 400, C.pale, t, IMPACT + 0.6, 999, 0.92);
      const ca = eOutBack(seg(t, IMPACT + 1.0, IMPACT + 1.5));
      if (ca > 0) {
        x.save(); x.globalAlpha = clamp(ca); x.translate(CX, L.ctaY); x.scale(ca, ca);
        x.fillStyle = rgba(C.cta, 1); x.beginPath(); x.roundRect(-160, -30, 320, 60, 30); x.fill();
        x.font = `600 23px ${F}`; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillStyle = '#ffffff';
        x.fillText(PROFILE.cta + '  →', 0, 1); x.restore();
      }
      text(upper(PROFILE.url, true), CX, L.urlY, 18, 600, C.pale, eOutCubic(seg(t, IMPACT + 1.3, IMPACT + 1.8)) * 0.6, 'center', 5);
    }
    const fin = 1 - eOutCubic(seg(t, 0, 0.5));
    if (fin > 0) { x.fillStyle = PROFILE.bg; x.globalAlpha = fin; x.fillRect(0, 0, W, H); }
  },
};
