---
name: panel
description: "Canlı iş paneli: tarayıcıda açık duran bir HTML sayfası. Sayfada bitenler, sıradakiler, {{USER_NAME}}'nin kontrol etmesi gerekenler ve cevap bekleyen sorular form olarak durur; 'Cevapları kopyala' butonu cevapları chat'e yapıştırılacak metne çevirir. Büyük, çok adımlı ya da çok kararlı işlerde kendiliğinden aç ve iş ilerledikçe kendiliğinden güncelle. Kısa işlerde açma. Elle tetik: '/panel', 'panel aç', 'panel kapat'."
---

# Panel

Uzun işte durum scroll'da kaybolmasın, {{USER_NAME}} cevaplarını tek seferde versin diye var.
Ne zaman açacağına, ne yazacağına sen karar ver.

- Şablonu (`template.html`, bu klasörde) `<proje kökü>/.panel/<slug>/index.html` olarak kopyala;
  projesiz işte `~/.claude/panels/<slug>/`. `.panel/` satırı `.gitignore`'da yoksa ekle.
- İçerik yanındaki `data.js` dosyasında. Şema ve alanlar `template.html` içindeki
  okuyucudan belli: `window.PANEL = { slug, title, project, updated: "YYYY-MM-DD HH:MM",
  status: "active"|"done", now, questions: [{id, text, context, type: "choice"|"confirm"|"text",
  options, recommended}], checks: [{id, text, how}], queue: [{text, owner}], done: [{text, evidence}] }`.
- Bir kez tarayıcıda aç (`Start-Process <yol>`); sayfa `data.js`'i kendisi yeniden okur.
- Güncellemeyi {{USER_NAME}} istemeden yap: durum değiştiğinde (adım bitti, soru çıktı, cevap
  işlendi, ajan başladı ya da bitti) `data.js`'i yeniden yaz. Panel eskirse işe yaramaz.
- {{USER_NAME}}'nin yapıştırdığı cevapları işle, paneli ona göre güncelle.
- İş bitince `status: "done"`; kalıcı olanı yine Threads / Last-Session / projenin dosyalarına yaz.
