---
name: sunum-site
description: |
  Tek sayfalık, koyu temalı, kaydırmalı sunum sitesi kalıbı (framework yok, build yok).
  Sol ray navigasyon, numaralı bölümler, scroll-reveal, sayaçlar, L tuşu ile tema.
  Marka parametriktir: tek dosyadan (css/brand.css + assets/logo-*) değişir; varsayılan
  nötr "Brand" profiliyle gelir, kendi markanı nasıl ekleyeceğin aşağıda. Diyagramlar
  diagram-design plugin'inden inline SVG olarak gelir. Kullan: "sunum sitesi", "sunum
  hazırla", "patron sunumu", "pitch", "teklif sunumu", "presentation site". Kaynak
  fikir: Avenox sunum-sitesi deseni (lisanssız repo — metin kopyalanmadı, desen
  yeniden yazıldı).
argument-hint: "[konu] [marka] [bölüm sayısı]"
---

# Sunum Sitesi

`template/` klasörü kopyalanır, `brand.css` + logolar değişir, bölümler doldurulur. `python3 -m http.server 8080` ile sunulur; herhangi bir statik hosting'e olduğu gibi atılır.

## Marka

Kalıp nötr bir varsayılan profille ("Brand") gelir: `css/brand.css` token'ları (yazı tipleri, koyu ve açık tema renkleri, tek vurgu rengi) ve yer tutucu logolar (`assets/logo-dark.svg` beyaz artwork koyu zemin için, `assets/logo-light.svg` siyah artwork açık zemin için, `assets/icon.svg`).

Kendi markanı eklemek için:

1. `brand.css`'in `:root` (koyu) ve `body.light` bloklarındaki token'ları ve font import'unu markana göre değiştir.
2. `assets/logo-dark.*`, `assets/logo-light.*` ve `icon.*` dosyalarını markanın artwork'üyle değiştir (SVG ya da PNG; PNG ise `index.html`'deki `src` uzantısını güncelle) ve `index.html`'deki `alt` metnini düzelt.
3. diagram-design'a markan için bir profil kaydet (`references/profiles.md` → `save`); diyagramları üretmeden önce `/profile load <profil>` çalıştır.

Kalıbın başka hiçbir yeri değişmez. Birden çok marka kullanıyorsan her biri için `brand.css` token setini ve logo çiftini ayrı tut, sunum klasörüne kopyalarken ilgili olanı koy.

## Süreç

1. **İçerik envanteri.** Kaynak notu (PRD, teklif, karar notu) oku. 6–10 bölüm çıkar; her bölümün tek cümlelik derdi. Kapanış her zaman "karar ve ihtiyaçlar" — dinleyiciden ne istendiği.
2. **Kopyala.** `cp -r template/ <hedef>/`. Hedef: ilgili proje klasörü altında `Sunum/`.
3. **Marka.** Varsayılan nötr profil yeterliyse dokunma. Kendi markan için yukarıdaki "Marka" adımlarını uygula: `brand.css` token'ları, logolar, diagram-design profili.
4. **Bölümleri doldur.** `index.html` iskeleti: her bölüm `<section id class="rv">` + `.sec-head` (numara + kicker) + `h2` + gövde. `data-nav` ile ray etiketi kısaltılır. Bileşenler: `.grid.c2/c3/c4` + `.card` (`.card.accent` tek vurgu), `.list`, `.stat` + `data-count`, `table`, `.badge`.
5. **Diyagramlar.** diagram-design plugin'iyle üret (profil: marka). Üretmeden önce `/profile load <profil>` çalıştır; Sunum klasörüne `profile: <profil>` içeren bir `.diagram-design` marker dosyası bırakmak da yeterli. Çıktı HTML'indeki `<svg>` bloğunu `<figure class="fig">` içine inline yapıştır; standalone HTML'i `diagrams/` altında sakla. Diyagram koyu varyantı kullan (site koyu). Tip seçimi plugin'in §3 tablosuna göre; ≤9 node. Inline SVG'de hex renkler CSS token'a çevrilir (`var(--paper)`, `var(--paper-2)`, `var(--ink)`, `var(--muted)`, `var(--soft)`, `var(--rule-solid)`, `var(--accent)`, `var(--accent-tint)`) — böylece L ile tema değişince diyagram da döner. Standalone HTML'ler koyu ve açık olarak iki dosya (`diagrams/<ad>.html`, `diagrams/<ad>-light.html`). Her diyagram istisnasız tam ekran açılır: `.fig` tıklanınca / Enter ile `<dialog>` viewport'u doldurur, Esc kapatır (app.js otomatik bağlar, ek işaretleme gerekmez). Sunumda diyagram anlatılırken önce büyütülür; kutu içindeki küçük hali sadece önizlemedir. Diyagram kalabalıksa küçültme yapılmaz, bölünmez; tam ekranda okunması yeter.

### Diyagram standardı (tema-bağımsız)

1. SVG kendi arka plan rect'ini çizmez (yoksa `fill="none"`); zemini `.fig` konteyneri (`--paper-2`) sağlar.
2. Her node: `fill="var(--paper)"` `stroke="var(--rule-solid)"` stroke-width 1. Focal node: `fill="var(--accent-tint)"` `stroke="var(--accent)"`. Opsiyonel/external node: aynı stil + `stroke-dasharray="4 3"`. Düşük alfa ink dolgu/stroke (`rgba(...,0.03)`, `rgba(...,0.30)` gibi) yasak — her node görünür kutu tutar.
3. Metin: node adı `fill="var(--ink)"` font-size ≥12; alt etiket `fill="var(--muted)"` ≥10; kenar etiketi `fill="var(--muted)"` ≥10 mono; lejant ≥10. Kenar etiketi maskeleri (arkasındaki rect) `fill="var(--paper-2)"` olur, `paper` değil.
4. Kenarlar: `stroke="var(--muted)"`, ok uçları `fill="var(--muted)"`; döngü kapatan accent kenar `stroke="var(--accent)"` kendi accent marker'ıyla. Dashed ayna kenar `stroke-dasharray="4 4"`.

Hex ve rgba yasak; sadece token. Kaynak: açık tema kontrolünde bazı kutular kayboldu, arka plan paneli uyuşmadı.
6. **Sıkılaştırma turu.** İlk taslak hep seyrek çıkar. Her bölümü tek ekranda gör (`?capture` ile animasyonsuz); amaçsız boşluk varsa metin büyür ya da kutu küçülür.

## Kurallar

- Vurgu rengi (`--accent`) bölüm başına 1 öğe: bir kart, bir sayı, bir satır. Her şeyi vurgulamak vurguyu siler.
- Sayılar kaynağa bağlı; kaynak notta olmayan rakam uydurulmaz. Zaman ekseni yoksa "sıra, süre değil" yazılır.
- Uzun paragraf yok; `p` 64ch, `.lead` 56ch. Kartlarda 2–3 cümle.
- Hero'da animasyon, gövdede sadece reveal + sayaç. Tümü `?capture` ve `prefers-reduced-motion` ile kapanır.
- Fiyat/gizli bilgi: dinleyiciye göre. Şirket sunumunda fiyat bilgisi koyma; belirsizse sor.

## Tasarım ilkeleri (varsayılan profil)

- Minimal; büyük boşluk. Kalabalık kart yerine az ve nefes alan içerik.
- Başlıklar hafif ağırlıkta, kicker/eyebrow'larda geniş harf aralığı (uppercase, 0.18em).
- Bölüm başına tek vurgu rengi öğesi — gradyan yok, gölge yok, sadece hairline çizgiler (`--rule`).
- Diyagramlar diagram-design'dan marka profiliyle, koyu varyant.

## Klavye ve URL

- `↓ ↑ PgDn PgUp` bölüm geçişi · `L` tema · `?light` açık başlar · `?capture` animasyon kapalı (ekran kaydı).
- Diyagrama tıkla / Enter: tam ekran · Esc: kapat

## Kontrol listesi

- [ ] Her bölüm tek ekranda derdini anlatıyor (1280×720'de test)
- [ ] Ray'daki etiketler ≤ 2 kelime
- [ ] Koyu ve açık temada tüm metin ve diyagram okunur
- [ ] Diyagram açık temada da okunur (L bas, kontrol et)
- [ ] Diyagram font'ları site font'larıyla aynı aile (`brand.css` font token'ları)
- [ ] Sunucu önbelleği: değişiklik görünmüyorsa `?v=2`
- [ ] Diyagram tam ekranda 1280x720'de okunur
