---
name: derin-analiz
description: "Kanıta dayalı derin analiz protokolü. Tetik: '/derin-analiz', 'derin analiz', 'derinlemesine bak', 'dürüst analiz', 'sistemi denetle'. Her bulgu kanıtlı, çıktı iyi/bozuk/düzeltme üçlüsü, yazmadan önce karşı görüş turu, sonuç projenin reports/ dizinine ve vault'a kalıcı yazılır."
---

# Derin analiz

Amaç: sohbette kaybolmayan, kanıtsız cümle içermeyen, karşı görüşten geçmiş analiz.
Dil Türkçe, düz nesir; kısa cevap kuralları bu skill aktifken anlatımı kısaltmaz.

## 1. Kapsam

Bir cümleyle yaz: neyi, hangi soruya cevap için, hangi kaynaklarla inceliyorsun.
Kapsam belirsizse tek soru sor, sonra devam et. Önce `<projeKökü>/reports/` ve vault'ta
aynı konuda önceki rapor var mı bak; varsa üstüne yaz, sıfırdan toplama.

## 2. Kanıt toplama

- Her bulgu bir dosya yolu, bir sayı (log sayımı, satır sayısı, test çıktısı) veya bir
  komut çıktısına dayanır. Kaynak gösterilemeyen cümle bulgu değildir, yazılmaz.
- "Sanırım", "muhtemelen", "genelde" yasak. Bilinmeyen şey "doğrulanmadı" diye yazılır.
- Geniş tarama (çok dosya, log sayımı) Opus ajanına verilir (`model: opus`;
  çıktı yargı olduğu için fable-orchestration (d) istisnası); sentez ve yargı ana döngüde kalır.
- Rakamları tabloya koy, nesirde sayı verme.

## 3. Yapı: üçlü

Üç bölüm, her maddeye sabit kod, sohbet boyunca kod değişmez:

- **İyi** — `İ1..` çalışan, korunacak şeyler. Kanıtla.
- **Bozuk** — `F1..` bulgular. Her biri: ne, kanıt, neden önemli. Acıtan şey yumuşatılmaz.
- **Düzeltme** — `Ö1..` öneriler. Önce budama, sonra ekleme. Yeni araç/repo önerisi
  yalnız "bu hafta hangi işte kullanırım?" sorusunun cevabıyla yazılır.

Çelişkileri ayrı listele (yazılan ile yapılan, iki ayarın birbirini bozması).

## 4. Karşı görüş turu (yazmadan önce)

Taslak bulguları `advisor` aracına ver; yoksa Opus ajanına "bu bulguları çürüt" de.
Çürütülen bulgu silinir veya "zayıf" etiketiyle kalır. Sonuçta hangi bulguların
düştüğü tek satırla raporda belirtilir. Kullanıcı sonradan bir bulguyu çürütürse
düzeltme aynı turda yazılır, savunulmaz.

## 5. Kalıcı çıktı

Sohbet cevabı özet; tam metin dosyaya gider, aynı içerik iki yere yazılmaz.

- Kod projesindeysen: `<projeKökü>/reports/YYYY-MM-DD-derin-analiz-<konu>.md`
  (kaynak, tarih, İ/F/Ö listesi, düşen bulgular, alınan kararlar).
- Vault tarafı:
  - Analiz bir projeyle ilgiliyse `🏰 300-Projects/<proje>/` altındaki ilgili nota
    tarihli "Derin analiz YYYY-MM-DD" bölümü ekle; nota bağlantı ver, metni kopyalama.
  - Projeyle ilgili değilse (sistem, araç, karar) `🧠 500-Knowledge/` altında konuyla
    ilgili mevcut nota tarihli bölüm; yoksa yeni not.
- Alınan karar varsa `🧘 800-Mind/Kararlar.md`'ye tek satır. Kod projesindeysen karar önce `docs/adr/` altına `Status: proposed` olarak yazılır; Kararlar.md satırı yalnız ona bağlantı verir.
- Tetik "bitti" gelmeden önce Last-Session'a kısa özet.

## Yasaklar

- Kanıtsız bulgu, yuvarlanmış "yaklaşık" sayı, uydurulmuş ad.
- Alışveriş listesi: analizden "şunu kur" çıkmaz, "şunu kaldır/ölç/kullan" çıkar.
- Aynı raporu iki yere kopyalamak.
- Bulguyu kullanıcı hoşlanmasın diye yumuşatmak.
