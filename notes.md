# Notes

## Dump (raw, 2026-10-06, repo sahibi)
- ECC, caveman, ponytail çıktı; yerine Matt Pocock skill'leri ve i-have-adhd geldi; global CLAUDE.md ve skill'ler değişti.
- Vault hafıza sistemi (beyin) kendi reposundan gelir ve `beyin-guncelle` ile güncellenir. Harness için de aynı modelde bir repo isteniyor.
- Repo linkini başka bilgisayarda ya da cloud kurulumunda verip "bunu kur" diyeceğim; oradaki kurulum bu makinedeki gibi olsun: skill'ler, plugin'ler, marketplace plugin'leri, CLAUDE.md.
- Repo public. Kişisel bilgiler ve vault yolları, kuran kişinin kendi bilgileriyle yazılsın.
- Vault varsa kur, yoksa atla. Eski ps1 yedek kiti emekliye ayrılsın.
- Kurulum soru sorsun: Orca kullanıyor musun? Vault kurulu mu? Codex kullanıyor musun? Temel her zaman Claude Code; Codex evet ise Codex ayarları ve Codex skill'leri de gelsin.
- Sahibin marka dosyaları public repoya girmez; skill'ler motor olarak gelir.
- GLOSSARY.md her zaman boş şablon gider.
- Tehlikeli mod atlama + izin listesi: varsayılan kapalı, soruyla açılır.
- proje-baslat tam iskelet bu repoya da uygulanır.

## Architecture sketch

### Components
- `harness.json` — manifest: sürüm, marketplace'ler, plugin'ler, kendi skill'lerimiz, harici skill'ler (`npx skills add`), npm/pip araçları, her birinin `requires` koşulu (`vault` | `orca` | `codex` | yok).
- `payload/` — export'un ürettiği, yer tutuculu harness kopyası:
  - `payload/global/CLAUDE.md.tmpl`, `GLOSSARY.md.tmpl` (boş şablon), `BAGIMLILIKLAR.md.tmpl` (boş şablon)
  - `payload/skills/<ad>/...`
  - `payload/settings/base.json` (hook'lar dahil, kişisel olmayan anahtarlar), `payload/settings/permissions.json` (opt-in)
  - `payload/codex/config.toml` (yalnız Codex = evet)
- `overrides/` — repoda elle tutulan, export'tan sonra payload'un üstüne yazılan nötr dosyalar (markasız logo, markasız SKILL.md). `overrides.lock` kaynak dosyanın hash'ini tutar; kaynak değişirse export uyarır.
- `lib/template.py` — ortak şablon motoru (yer tutucu, koşullu blok, private blok). Ana döngü sahibi.
- `install.py` — hedef makinede çalışır.
- `export.py` — kaynak makinede çalışır; scrub sıfır değilse durur.
- `doctor.py` — kurulum sağlığı.
- `INSTALL.md` — Claude'un hedef makinede okuyup uyguladığı talimat (soruları sor, sonra install.py'yi bayraklarla çalıştır).

### Şablon kuralları
- Yer tutucular: `{{USER_NAME}}`, `{{HOME}}` (ileri eğik çizgili), `{{VAULT_PATH}}`, `{{GITHUB_OWNER}}`, `{{LANGUAGE}}` (ör. English), `{{PYTHON}}` (Windows `py -3`, diğerleri `python3`).
- Koşullu blok: `<!-- if:vault -->` ... `<!-- endif:vault -->` (vault, orca, codex). Koşul doğruysa içerik VE işaretler kalır (yeniden export edilebilsin); yanlışsa blok tamamen silinir.
- Private blok: `<!-- private:start -->` ... `<!-- private:end -->` canlı dosyada durur, export siler, repoya hiç girmez.
- JSON'da koşul: dizi elemanında `"_requires": "orca"` anahtarı; render sırasında koşul yanlışsa eleman düşer, doğruysa `_requires` silinir.
- Kişisel eşleme kaynak makinede `export.local.json` (gitignore): `{"replace": [["<ad>", "{{USER_NAME}}"], ...], "forbidden": ["<marka>", ...], "exclude": ["<yerel glob>"]}`. Scrub: forbidden kelimeler + e-posta + token kalıpları + mutlak kullanıcı yolları; bulgu varsa export exit 1.

### Install akışı
1. Cevaplar: bayraklar > `--answers file.json` > tty ise soru; tty değil ve eksik varsa exit 2 + eksik soru listesi (Claude kullanıcıya sorar).
2. Mevcut `~/.claude` dosyaları `~/.claude/backups/claude-harness-<zaman>/` altına yedeklenir (yalnız dokunulacaklar).
3. Global CLAUDE.md: yönetilen bölüm `<!-- claude-harness:start -->` / `<!-- claude-harness:end -->` arası; dışındaki kullanıcı satırları korunur. GLOSSARY / BAGIMLILIKLAR yalnız yoksa yazılır.
4. Skill'ler: koşulu tutan kendi skill'lerimiz `~/.claude/skills/<ad>` altına render edilerek kopyalanır.
5. settings.json: derin birleştirme; enabledPlugins / extraKnownMarketplaces birleşim; hook'lar komut metnine göre tekrar eklenmez; kullanıcı anahtarı silinmez.
6. Plugin'ler: `claude` PATH'te ise `claude plugin marketplace add` + `claude plugin install`; hata bir sonrakini durdurmaz, raporlanır.
7. Harici skill'ler `npx skills add`, npm global, pip araçları.
8. Codex = evet: `~/.codex/config.toml` yoksa yazılır, codex-fleet skill'i kurulur.
9. Vault = evet: beyin köprü hook'ları vault'un kendi kurulumuyla gelir (bu repo kurmaz); install sonunda gereken komut yazılır.
10. Orca = evet: Orca skill'leri `npx skills add stablyai/orca` ile; Orca hook'larını Orca uygulaması kendisi kurar.
11. Durum dosyası `~/.claude/.claude-harness.json` (sürüm, cevaplar, kurulan dosyalar) + doctor.

### Build vs buy
- Plugin'ler, harici skill'ler, beyin köprüsü, Orca hook'ları: kendi araçları kurar; biz yalnız listeyi tutup komutu çalıştırırız.
- Şablon, birleştirme, scrub: stdlib Python, bağımlılık yok.

### Deferred to v2
- macOS/Linux'ta gerçek makinede deneme (v1'de sahte HOME ile test).
- Otomatik "yeni sürüm var" bildirimi (beyin-guncelle benzeri skill).

## Open questions
- Q1 Beyin köprüsünü hedef makinede kuran komut ne? (vault kökündeki `beyin.py` yardımı ile netleşecek)
- Q2 graphify kurulumu: `pip install graphifyy` sonrası skill'i kuran komut doğrulanacak.
- Q3 GLOSSARY her zaman boş gidiyor; sahibin kendi ikinci makinesinde de boş başlar. Ayrı yedek istenir mi?

## Sözleşme (lane'ler arası, değişmez)

### payload/ düzeni (export yazar, install okur)
- `payload/global/CLAUDE.md.tmpl` — canlı `~/.claude/CLAUDE.md`'den; private blok silinmiş, kişisel eşleme uygulanmış, koşullu bloklar korunmuş.
- `payload/global/GLOSSARY.md.tmpl`, `payload/global/BAGIMLILIKLAR.md.tmpl` — her zaman boş şablon (başlık + format satırı). Install yalnız hedefte dosya yoksa yazar.
- `payload/skills/<ad>/**` — `harness.json` `ownSkills` listesindekiler; `export.exclude` glob'ları hariç; ardından `overrides/skills/<ad>/**` üstüne yazılır.
- `payload/settings/base.json` — `export.settingsKeys` anahtarları + `hooks` (yalnız `hookRules` `keep` olanlar, yollar yer tutuculu) + `enabledPlugins` (harness.json plugins'ten, hepsi true) + `extraKnownMarketplaces` (claude-plugins-official hariç marketplace'ler). `language` değeri `{{LANGUAGE}}`.
- `payload/settings/permissions.json` — `export.permissionKeys` anahtarları (opt-in).
- `payload/codex/config.toml` — canlı `~/.codex/config.toml`; `auth`/`key`/`token` içeren satırlar atılır.
- `payload/MANIFEST.json` — payload içindeki her dosyanın göreli yolu ve sha256'sı (doctor ve install kullanır).

### Yer tutucular
`{{USER_NAME}} {{HOME}} {{VAULT_PATH}} {{GITHUB_OWNER}} {{LANGUAGE}} {{PYTHON}}` (lib/template.py KNOWN). `{{SKILL_DIR}}` yalnız harness.json `postInstall` komutlarında, install doldurur. `{{HOME}}` ve `{{VAULT_PATH}}` ileri eğik çizgili mutlak yol.
Koşul bayrakları: `vault`, `orca`, `codex`.

### Durum dosyası `~/.claude/.claude-harness.json` (install yazar, doctor okur)
```json
{"version": "0.1.0", "installedAt": "<ISO>", "repo": "<repo kökü mutlak yolu>",
 "answers": {"USER_NAME": "...", "LANGUAGE": "...", "GITHUB_OWNER": "...", "VAULT_PATH": "... | null",
             "vault": true, "orca": false, "codex": true, "permissions": false},
 "files": ["skills/panel/SKILL.md", "..."],
 "steps": [{"name": "plugin:context7@claude-plugins-official", "ok": true, "detail": "..."}]}
```
`files` = install'ın `~/.claude` altına yazdığı dosyaların `~/.claude`'a göre yolu (ileri eğik çizgi).
Ek anahtarlar: `skipExternal` (bool), `settingsWritten` (harness'in yazdığı settings değerleri; sonraki kurulumda kullanıcı değiştirmediyse güncellenir), `settingsKept` (kullanıcının değeri korunan anahtarlar, ör. `model`, `enabledPlugins.<id>`). Adım kaydında `skipped: true` olabilir.
Cevap dosyası (`--answers`) anahtarları `answers` ile aynıdır; boolean değerler JSON true/false ya da açık evet/hayır kelimesi, başka değer exit 2. `permissions` eksikse false.

### install.py bayrakları
`--name --language --github-owner --vault PATH | --no-vault --orca/--no-orca --codex/--no-codex --permissions/--no-permissions --answers FILE --home DIR --skip-external --dry-run --yes`
Eksik cevap + tty yok → exit 2, stdout'a eksik soruların JSON listesi (`harness.json` `questions` metinleriyle).
