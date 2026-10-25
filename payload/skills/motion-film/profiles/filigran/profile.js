// Filigran profili: edit sonuna konan kısa etiket klipleri (watermark/tag). Saf siyah zemin,
// tema yok, yazı yok. Siyah zemin editörde Screen/Ekran karışımıyla şeffaf gibi davranır.
(() => {
  const st = document.createElement('style');
  st.textContent = `html,body{margin:0;background:#000;overflow:hidden}canvas{display:block}`;
  document.head.appendChild(st);
})();
const PROFILE = {
  id: 'filigran',
  brand: '',
  cta: '',
  url: '',
  locale: 'tr-TR',
  bg: '#000000',
  panelFill: 'rgba(0,0,0,0)',
  fontStack: "'Segoe UI', system-ui, sans-serif",
  fontProbes: [],
  fontCheck: '',
  colors: {
    ink: [240, 242, 246], pale: [190, 198, 212], blue: [110, 140, 220], ice: [140, 200, 255],
    cta: [70, 110, 255], green: [74, 222, 128], red: [239, 68, 68], amber: [251, 191, 36], gray: [110, 118, 134], viol: [165, 150, 255],
  },
};
