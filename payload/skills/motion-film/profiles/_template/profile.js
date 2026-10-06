// Profile template: copy this folder to profiles/<id>/ and fill in the brand. See profile.md.
// Fonts: put woff2 files in assets/ and add @font-face rules below (served at /profile/assets/...).
(() => {
  const st = document.createElement('style');
  st.textContent = `html,body{margin:0;background:#0b0d12;overflow:hidden}canvas{display:block}`;
  document.head.appendChild(st);
})();
const PROFILE = {
  id: '_template',
  brand: 'Brand',
  cta: 'Get in touch',
  url: 'example.com',
  locale: 'en',
  bg: '#0b0d12',
  panelFill: 'rgba(20,24,34,0.92)',
  fontStack: "'Segoe UI', system-ui, sans-serif",
  fontProbes: [],
  fontCheck: '',
  // core helpers use ink (text), pale (secondary text), blue (panel borders), red/green/amber (states)
  colors: {
    ink: [240, 242, 246], pale: [190, 198, 212], blue: [110, 140, 220], ice: [140, 200, 255],
    cta: [70, 110, 255], green: [74, 222, 128], red: [239, 68, 68], amber: [251, 191, 36], gray: [110, 118, 134], viol: [165, 150, 255],
  },
};
