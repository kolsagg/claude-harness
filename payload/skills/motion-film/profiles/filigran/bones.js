// bones.js: taşlı (rhinestone) iskelet çizimi. Kemikler dış hat boyunca dizilmiş gümüş taş
// noktalarıdır; uçlarda 4 köşeli yıldız parıltısı. Filmler parça listesi (HAND, FOREARM) ile grup
// kurar, her karede grubun pozunu (bilek dünya konumu, açı, ölçek) verir; toplanma, X anı parlaması
// ve dağılma burada. Her şey t'nin saf fonksiyonu (Math.random yok).
//
// Yerel eksen: bilek (0,0), parmaklar yukarı (-y), başparmak ve işaret parmağı -x tarafında.
// mirror: true -> x ekseninde aynalanır (sol eldeki yansıma).
const BONES = (() => {
  const TAU = Math.PI * 2;

  // Köpek kemiği dış hattı: uçlarda w0/w1, ortada wm yarı genişlik; uç kapakları basık yarım elips.
  function boneOutline(ax, ay, bx, by, w0, wm, w1) {
    const dx = bx - ax, dy = by - ay, len = Math.hypot(dx, dy), ux = dx / len, uy = dy / len, nx = -uy, ny = ux;
    const N = Math.max(8, Math.round(len / 3));
    const wAt = s => { const we = s < 0.5 ? w0 : w1; return wm + (we - wm) * Math.pow(Math.abs(2 * s - 1), 2.4); };
    const pts = [];
    for (let i = 0; i <= N; i++) { const s = i / N, w = wAt(s); pts.push([ax + dx * s + nx * w, ay + dy * s + ny * w]); }
    for (let i = 1; i < 12; i++) { const a = Math.PI / 2 - Math.PI * i / 12; pts.push([bx + (nx * Math.sin(a) + ux * Math.cos(a) * 0.55) * w1, by + (ny * Math.sin(a) + uy * Math.cos(a) * 0.55) * w1]); }
    for (let i = N; i >= 0; i--) { const s = i / N, w = wAt(s); pts.push([ax + dx * s - nx * w, ay + dy * s - ny * w]); }
    for (let i = 1; i < 12; i++) { const a = -Math.PI / 2 + Math.PI * i / 12; pts.push([ax + (nx * Math.sin(a) - ux * Math.cos(a) * 0.55) * w0, ay + (ny * Math.sin(a) - uy * Math.cos(a) * 0.55) * w0]); }
    return pts;
  }
  function blobOutline(cx, cy, rx, ry, rot) {
    const pts = [], c = Math.cos(rot), s = Math.sin(rot);
    for (let i = 0; i < 40; i++) { const a = i / 40 * TAU, px = Math.cos(a) * rx, py = Math.sin(a) * ry; pts.push([cx + px * c - py * s, cy + px * s + py * c]); }
    return pts;
  }
  // Kapalı çokgen çevresine d aralıkla eşit nokta dizer.
  function resample(poly, d, phase) {
    const segs = [];
    let total = 0;
    for (let i = 0; i < poly.length; i++) {
      const a = poly[i], b = poly[(i + 1) % poly.length], l = Math.hypot(b[0] - a[0], b[1] - a[1]);
      segs.push([a, b, l, total]); total += l;
    }
    const n = Math.max(3, Math.round(total / d)), step = total / n, out = [];
    let k = 0;
    for (let i = 0; i < n; i++) {
      const pos = (i + phase) * step;
      while (k < segs.length - 1 && segs[k][3] + segs[k][2] < pos) k++;
      const [a, b, l, st] = segs[k], p = l > 0 ? (pos - st) / l : 0;
      out.push([a[0] + (b[0] - a[0]) * p, a[1] + (b[1] - a[1]) * p]);
    }
    return out;
  }

  // ---------- geometri (yerel px) ----------
  // ['b', ax, ay, bx, by, w0, wm, w1, etiket] kemik, ['o', cx, cy, rx, ry, rot] karpal kemik
  const HAND = [
    // karpal kemikler (bilek)
    ['o', -24, -42, 12, 9, 0.5], ['o', -4, -45, 11, 9, 0.1], ['o', 16, -44, 11, 8.5, -0.3], ['o', 33, -38, 8, 9, -0.2],
    ['o', -17, -21, 13, 9, -0.25], ['o', 6, -23, 12, 10, 0.15], ['o', 28, -20, 10, 8, 0.4],
    // işaret parmağı: tarak kemiği + düz uzanan üç boğum
    ['b', -30, -58, -38, -148, 8.5, 5.5, 9.5], ['b', -40, -157, -43, -240, 10, 6.5, 8.5, 'f'],
    ['b', -43, -248, -45, -304, 8.5, 6, 7.5, 'f'], ['b', -45, -312, -46, -350, 7.5, 5, 4.5, 'f'],
    // kıvrık parmaklar (yumruk): eklem sırası kemerli, boğumlar avuç önünde aşağı inip başparmağa kıvrılır
    ['b', -17, -160, -13, -116, 11, 7.5, 10], ['b', -11, -109, -8, -83, 9, 6.5, 8], ['b', -8, -76, -16, -62, 7, 5, 4.5],
    ['b', 9, -158, 13, -114, 11, 7.5, 10], ['b', 15, -107, 16, -81, 9, 6.5, 8], ['b', 15, -74, 7, -63, 7, 5, 4.5],
    ['b', 32, -146, 38, -108, 9.5, 6.5, 8.5], ['b', 40, -101, 40, -80, 8, 5.5, 7], ['b', 38, -73, 31, -64, 6, 4.5, 4],
    // başparmak: yumruğun önüne, orta boğumların üstüne yatar
    ['b', -40, -48, -62, -86, 9, 6, 9], ['b', -61, -94, -39, -110, 8.5, 6, 8], ['b', -32, -113, -5, -108, 7.5, 5, 4.5],
  ];
  const HAND_CROSS = [-43, -200]; // işaret parmağının X'te kesiştiği nokta (ilk boğumun ortası)
  const HAND_TIP = [-46, -354];
  const FINGER_PIVOT = [-39, -152]; // işaret parmağı eklemi: pose.fa bu noktada parmağı ayrıca büker
  // v2 el: gerçekçi oranlar (işaret parmağı boğumları tarak kemiğinin ~0.6/0.35/0.27'si), kemerli eklem
  // sırası, küçülen serçe parmak, bileğin altında silinerek biten radius/ulna başları ('fade').
  const HAND2 = [
    ['o', -21, -41, 11, 8, 0.5], ['o', -3, -45, 10, 8.5, 0.15], ['o', 15, -43, 10, 8, -0.35], ['o', 30, -37, 7.5, 8.5, -0.3],
    ['o', -14, -21, 12, 8.5, -0.3], ['o', 7, -23, 11, 9.5, 0.2], ['o', 26, -19, 9, 7.5, 0.5],
    ['b', -17, -2, -21, 70, 17, 10, 10, 'fade'], ['b', 21, -1, 24, 70, 10, 7.5, 8, 'fade'],
    // işaret parmağı: hafif kavisli, gerçek boyda
    ['b', -29, -58, -36, -145, 8.5, 5.5, 9.5], ['b', -38, -153, -42, -207, 9.5, 6.2, 8, 'f'],
    ['b', -43, -214, -44, -246, 8, 5.5, 7, 'f'], ['b', -44, -252, -43, -275, 6.8, 4.5, 4, 'f'],
    // kıvrık parmaklar: orta en yüksek, serçe alçak ve küçük; uçlar başparmağa doğru kıvrılır
    ['b', -16, -160, -12, -117, 11, 7.5, 10], ['b', -10, -110, -8, -86, 9, 6.5, 8], ['b', -9, -79, -18, -67, 7, 5, 4.5],
    ['b', 9, -156, 12, -115, 10.5, 7, 9.5], ['b', 14, -108, 14, -85, 8.5, 6, 7.5], ['b', 13, -78, 4, -68, 6.5, 4.5, 4],
    ['b', 31, -140, 35, -109, 9, 6, 8], ['b', 37, -102, 36, -86, 7.5, 5, 6.5], ['b', 34, -79, 26, -72, 6, 4, 3.5],
    // başparmak: orta boğumların üstüne sarılır
    ['b', -37, -50, -58, -87, 9.5, 6, 9], ['b', -58, -95, -38, -113, 8.5, 6, 8], ['b', -31, -116, -9, -112, 7.5, 5, 4.5],
  ];
  const HAND2_CROSS = [-40, -182];
  const HAND2_TIP = [-43, -279];
  const FINGER2_PIVOT = [-37, -149];
  // önkol: radius + ulna, bilekten dirseğe (yerel +y aşağı)
  const FOREARM = [
    ['b', -22, 3, -31, 362, 19, 9, 12, 'w'], ['b', 22, 4, 31, 374, 11, 8, 19, 'w'],
  ];

  function build(parts, { spacing = 7, mirror = false, seed = 1 } = {}) {
    const R = rng(seed), dots = [];
    parts.forEach(p => {
      const polys = [p[0] === 'b' ? boneOutline(p[1], p[2], p[3], p[4], p[5], p[6], p[7]) : blobOutline(p[1], p[2], p[3], p[4], p[5])];
      // 'w': uzun kemik, içine ikinci (ilik) sıra taş dizilir
      if (p[8] === 'w') polys.push(boneOutline(p[1], p[2] + 6, p[3], p[4] - 6, p[5] * 0.42, p[6] * 0.35, p[7] * 0.42));
      polys.forEach((poly, k) => resample(poly, spacing * (k ? 1.25 : 1), R()).forEach(([lx, ly]) => {
        const d = { x: mirror ? -lx : lx, y: ly, f: p[8] === 'f', h1: R(), h2: R(), h3: R(), h4: R(), sz: (0.8 + 0.4 * R()) * (k ? 0.8 : 1), k: 1 };
        // 'fade': kemik aşağı doğru silinir (bilekten sonra kol devam ediyormuş gibi)
        if (p[8] === 'fade') d.k = clamp(1 - (ly - 8) / 58);
        if (d.k > 0.06) dots.push(d);
      }));
    });
    return dots;
  }
  const mpt = (p, mirror) => [mirror ? -p[0] : p[0], p[1]];

  // ---------- sprite'lar ----------
  let dotSpr = null, starSpr = null;
  const DOT_K = 0.42; // taş yarıçapı / sprite yarı boyu
  function initSprites() {
    dotSpr = document.createElement('canvas'); dotSpr.width = dotSpr.height = 64;
    let g = dotSpr.getContext('2d');
    const hg = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    hg.addColorStop(0, 'rgba(255,255,255,0.32)'); hg.addColorStop(0.45, 'rgba(225,232,245,0.10)'); hg.addColorStop(1, 'rgba(225,232,245,0)');
    g.fillStyle = hg; g.fillRect(0, 0, 64, 64);
    const r = 32 * DOT_K, sg = g.createRadialGradient(28, 28, 0, 32, 32, r);
    sg.addColorStop(0, '#ffffff'); sg.addColorStop(0.45, 'rgb(232,236,244)'); sg.addColorStop(0.85, 'rgb(170,178,194)'); sg.addColorStop(1, 'rgb(120,128,145)');
    g.fillStyle = sg; g.beginPath(); g.arc(32, 32, r, 0, TAU); g.fill();
    g.fillStyle = 'rgba(255,255,255,0.95)'; g.beginPath(); g.arc(28.5, 28.5, r * 0.28, 0, TAU); g.fill();

    starSpr = document.createElement('canvas'); starSpr.width = starSpr.height = 256;
    g = starSpr.getContext('2d');
    const cg = g.createRadialGradient(128, 128, 0, 128, 128, 46);
    cg.addColorStop(0, 'rgba(255,255,255,1)'); cg.addColorStop(0.18, 'rgba(255,255,255,0.65)'); cg.addColorStop(0.5, 'rgba(220,230,255,0.14)'); cg.addColorStop(1, 'rgba(220,230,255,0)');
    g.fillStyle = cg; g.fillRect(0, 0, 256, 256);
    const spike = (ang, len, hw) => {
      g.save(); g.translate(128, 128); g.rotate(ang);
      const lg = g.createLinearGradient(0, 0, len, 0);
      lg.addColorStop(0, 'rgba(255,255,255,1)'); lg.addColorStop(0.35, 'rgba(255,255,255,0.55)'); lg.addColorStop(1, 'rgba(255,255,255,0)');
      g.fillStyle = lg; g.beginPath(); g.moveTo(0, -hw); g.lineTo(len, 0); g.lineTo(0, hw); g.closePath(); g.fill(); g.restore();
    };
    for (let i = 0; i < 4; i++) spike(i * Math.PI / 2, 126, 3.2);
    for (let i = 0; i < 4; i++) spike(Math.PI / 4 + i * Math.PI / 2, 46, 1.8);
  }
  function drawDot(px, py, r, a) {
    if (a <= 0.003 || r <= 0.2) return;
    const s = r / DOT_K;
    x.globalAlpha = Math.min(1, a); x.drawImage(dotSpr, px - s, py - s, s * 2, s * 2);
  }
  // size: yıldızın kol uzunluğu (px)
  function drawStar(px, py, size, a, rot = 0) {
    if (a <= 0.003 || size <= 0.5) return;
    const prev = x.globalCompositeOperation;
    x.globalCompositeOperation = 'lighter'; x.globalAlpha = Math.min(1, a);
    if (rot) { x.save(); x.translate(px, py); x.rotate(rot); x.drawImage(starSpr, -size, -size, size * 2, size * 2); x.restore(); }
    else x.drawImage(starSpr, px - size, py - size, size * 2, size * 2);
    x.globalCompositeOperation = prev;
  }

  // pose: { x, y, a, s, fa?, pivot? }  (x,y = bileğin dünya konumu, a = açı (rad, saat yönü +), s = ölçek,
  // fa = işaret parmağının eklemde ek bükülmesi, pivot = aynalanmış FINGER_PIVOT)
  function place(lx, ly, pose) {
    const c = Math.cos(pose.a), sn = Math.sin(pose.a);
    return [pose.x + (lx * c - ly * sn) * pose.s, pose.y + (lx * sn + ly * c) * pose.s];
  }
  // Yerel bir nokta dünya konumu `at`a otursun diye bilek konumunu çözer.
  function wristFor(local, at, a, s) {
    const c = Math.cos(a), sn = Math.sin(a);
    return [at[0] - (local[0] * c - local[1] * sn) * s, at[1] - (local[0] * sn + local[1] * c) * s];
  }
  const frac = v => v - Math.floor(v);
  // Parmak boğumu: yerel noktayı pose.pivot etrafında pose.fa kadar döndürür.
  function bend(lx, ly, pose) {
    if (!pose.fa) return [lx, ly];
    const [ox, oy] = pose.pivot, c = Math.cos(pose.fa), s = Math.sin(pose.fa), dx = lx - ox, dy = ly - oy;
    return [ox + dx * c - dy * s, oy + dx * s + dy * c];
  }

  // T: { in0, in1, out0, out1, flash, flashAt:[x,y], sweep?:[altY, üstY] }  center: dağılma merkezi
  // opts: { r (taş yarıçapı px), stars: [[lx,ly,boyut,faz]] yerel parıltı noktaları }
  function drawGroup(dots, pose, t, T, center, opts) {
    const r = opts.r;
    // inStar/outStar: bu eşiğin üstündeki taşlar toplanma/dağılmada yıldız olur; sparkle: yıldız boyu çarpanı
    const inStar = opts.inStar ?? 0.9, outStar = opts.outStar ?? 0.84, sparkle = opts.sparkle ?? 1;
    // keskin hareket ayarları (varsayılanlar v1/v2 davranışı): giriş/çıkış eğrisi, gecikme payı, uçuş payı, girdap
    const inEase = opts.inEase || eOutCubic, outEase = opts.outEase || eOutCubic, swirl = opts.swirl ?? 1.4;
    const inStag = opts.inStagger ?? 0.6, outStag = opts.outStagger ?? 0.6, outFly = opts.outFlight ?? 0.4;
    const inSpan = T.in1 - T.in0, outSpan = T.out1 - T.out0;
    const sparks = [];
    for (let i = 0; i < dots.length; i++) {
      const d = dots[i];
      const [lx, ly] = d.f ? bend(d.x, d.y, pose) : [d.x, d.y];
      let [px, py] = place(lx, ly, pose);
      // toplanma: bir kısmı uzaktan uçar, kalanı yerinde parlayarak belirir
      const ts = T.in0 + d.h1 * inSpan * inStag, p = seg(t, ts, ts + inSpan * (1 - inStag));
      if (p <= 0) continue;
      const pe = inEase(p), far = d.h3 * d.h3, R0 = 25 + 330 * far, ang = d.h2 * TAU + (1 - pe) * swirl * (d.h4 - 0.5);
      px += Math.cos(ang) * R0 * (1 - pe); py += Math.sin(ang) * R0 * (1 - pe);
      let alpha = d.k * clamp(p * 2.4) * (p < 1 ? 0.55 + 0.45 * Math.sin(t * 31 + d.h1 * 60) : 1);
      let size = r * d.sz * (0.55 + 0.45 * pe);
      // tutuş: hafif titreşim + ara ara küçük parıltı
      let bright = 0.86 + 0.14 * Math.sin(t * (1.6 + 2.2 * d.h2) + d.h3 * 40);
      if (T.flash != null && t > T.flash) {
        const dist = Math.hypot(px - T.flashAt[0], py - T.flashAt[1]), front = (t - T.flash) * 1500;
        bright += 0.9 * Math.exp(-((dist - front) ** 2) / (2 * 45 * 45)) * (1 - seg(t, T.flash, T.flash + 0.7));
      }
      // dağılma: merkezden dışarı, hafif yukarı; titreşerek söner
      let q = 0;
      if (t > T.out0) {
        // T.sweep = [altY, üstY]: dağılma alttan üste dalga gibi ilerler, şekil bir süre seçilir kalır
        const sp = T.sweep ? clamp((T.sweep[0] - py) / (T.sweep[0] - T.sweep[1])) : d.h4;
        const to = T.out0 + (0.45 * d.h4 + 0.55 * sp) * outSpan * outStag;
        q = seg(t, to, to + outSpan * outFly);
        if (q > 0) {
          const qe = outEase(q);
          let vx = px - center[0], vy = py - center[1];
          const vl = Math.hypot(vx, vy) || 1, rot = (d.h2 - 0.5) * 1.7, c = Math.cos(rot), s = Math.sin(rot);
          vx /= vl; vy /= vl; [vx, vy] = [vx * c - vy * s, vx * s + vy * c];
          const dist = (60 + 300 * d.h3) * qe;
          px += vx * dist + Math.sin(t * 3 + d.h1 * 20) * 8 * q; py += vy * dist - 70 * q * (0.4 + d.h1);
          alpha *= Math.pow(1 - q, 1.25) * (1 - q * 0.55 * (0.5 + 0.5 * Math.sin(t * (16 + 22 * d.h4) + d.h1 * 50)));
          size *= 1 - 0.45 * q;
          if (d.h4 > outStar) { const e = Math.sin(Math.PI * seg(q, 0.12, 0.8)); if (e > 0) sparks.push([px, py, r * (5 + 6 * d.h1) * e * sparkle, 0.9 * e]); }
        }
      }
      drawDot(px, py, size, alpha * Math.min(1.25, bright));
      // tutuşta rastgele küçük parıltılar
      if (p >= 1 && q <= 0 && d.h4 > 0.62) {
        const g = frac(t * 0.42 + d.h1 * 7.31);
        if (g < 0.06) { const e = Math.sin(Math.PI * g / 0.06); sparks.push([px, py, r * 4.2 * e, 0.85 * e]); }
      }
      // toplanmada uçan taşların bir kısmı yıldız gibi çakar
      if (p > 0 && p < 1 && d.h4 > inStar) { const e = Math.sin(Math.PI * p); sparks.push([px, py, r * 4 * e * sparkle, 0.8 * e]); }
    }
    // sabit parıltılar (parmak ucu, eklemler): toplanma bitince yanar, dağılmada sönerken savrulur
    (opts.stars || []).forEach(([sx, sy, sz, ph, fing]) => {
      const [lx, ly] = fing ? bend(sx, sy, pose) : [sx, sy];
      const [px, py] = place(lx, ly, pose);
      const on = eOutCubic(seg(t, T.in1 - 0.25 + ph * 0.3, T.in1 + 0.25 + ph * 0.3));
      const off = 1 - seg(t, T.out0 + 0.1 + ph * 0.4, T.out0 + 0.55 + ph * 0.4);
      const tw = 0.72 + 0.28 * Math.sin(t * (2.3 + ph) + ph * 9);
      sparks.push([px, py, r * sz * (0.75 + 0.25 * tw), on * off * tw]);
    });
    x.globalAlpha = 1;
    sparks.forEach(s => drawStar(s[0], s[1], s[2], s[3]));
    x.globalAlpha = 1;
  }

  // Serbest parıltı tozu: [t0,t1] arasında elips içinde rastgele yanıp sönen yıldızlar (şekilden bağımsız).
  function glitter(t, { t0, t1, cx, cy, rx, ry, n, seed = 7, size = 30, drift = 0 }) {
    if (t < t0 - 0.1 || t > t1 + 0.8) return;
    const R = rng(seed);
    for (let i = 0; i < n; i++) {
      const a = R() * TAU, rr = Math.sqrt(R()), born = t0 + R() * (t1 - t0), life = 0.25 + 0.45 * R(), sz = size * (0.35 + 0.65 * R() * R());
      const q = (t - born) / life;
      if (q <= 0 || q >= 1) continue;
      const e = Math.sin(Math.PI * q);
      drawStar(cx + Math.cos(a) * rx * rr, cy + Math.sin(a) * ry * rr - drift * q, sz * e, 0.95 * e);
    }
  }

  return { HAND2, HAND2_CROSS, HAND2_TIP, FINGER2_PIVOT, glitter, HAND, HAND_CROSS, HAND_TIP, FINGER_PIVOT, FOREARM, bend, build, mpt, initSprites, drawDot, drawStar, place, wristFor, drawGroup };
})();
