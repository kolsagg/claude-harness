# claude-harness

Bir Claude Code kurulumunu (global CLAUDE.md, kendi skill'ler, plugin'ler, marketplace'ler, ayarlar, isteğe bağlı vault / Orca / Codex) başka bir makineye ya da cloud ortamına taşır. Kişisel bilgiler repoda durmaz; kuran kişinin kendi cevaplarıyla yazılır.

## Kurulum

Bu repo linkini Claude'a ver ve şunu söyle:

> Bunu kur: https://github.com/<owner>/claude-harness

Claude `INSTALL.md`'yi okur, birkaç soru sorar, `install.py`'yi çalıştırır ve `doctor.py` ile doğrular. Güncellemek için "harness'i güncelle" demen yeter.

## Neyi kurar

| Grup | İçerik |
|------|--------|
| Her zaman | Global `CLAUDE.md` (yönetilen blok), boş `GLOSSARY.md` ve `BAGIMLILIKLAR.md` şablonu, kendi skill'ler, plugin'ler ve marketplace'ler, temel `settings.json` anahtarları ve hook'lar, harici skill'ler ve npm/pip araçları |
| Vault = evet | Vault'a bağlı CLAUDE.md blokları ve ayarlar; beyin köprüsü hook'ları vault'un kendi kurulumuyla gelir (bu repo kurmaz) |
| Orca = evet | Orca skill'leri; Orca hook'larını Orca uygulaması kendisi kurar |
| Codex = evet | `~/.codex/config.toml`, `codex-fleet` skill'i, Codex CLI |

Tehlikeli mod atlama ve izin listesi varsayılan kapalıdır; yalnız soruya evet denirse açılır.

## Ne kurulur, kimden gelir

Bu repo kurulum sırasında üçüncü taraf kod çeker. Çoğu sürüme sabitlenmemiştir (varsayılan dal ya da en son sürüm); kurmadan önce bunu bil.

| Kaynak | Ne | Not |
|--------|----|-----|
| Claude plugin marketplace'leri: `anthropics/claude-plugins-official`, `mem0ai/mem0`, `cathrynlavery/diagram-design`, `ayghri/i-have-adhd` | Plugin'ler | Varsayılan dalın ucundan gelir, sabitlenmemiştir. Plugin'ler hook ve MCP sunucusu ekleyebilir |
| `npx --yes skills add` (`skills` npm paketinin son sürümü) | `vercel-labs/skills`, `cloudflare/security-audit-skill` skill'leri; yalnız Orca = evet iken `stablyai/orca` skill'leri | Paket ve skill kaynakları sabitlenmemiştir |
| `npm install -g` | `ccstatusline`, `agent-browser`; yalnız Codex = evet iken `@openai/codex` | En son sürüm, npm install betikleri çalışır |
| `pip install --user graphifyy`, ardından `graphify install` | graphify aracı ve skill'i | Sürüm sabit değil |
| `npm install` (motion-film motoru) | motion-film skill'inin bağımlılıkları | Kilit dosyası (lockfile) ile sabit |

Her harici adım `--skip-external` ile atlanabilir; `--home` gerçek ev dizini dışına verilirse harici adımlar kendiliğinden kapanır. `--dry-run` çalıştırılacak komutların tam listesini yazar.

`mem0` plugin ayarı `user_id: "USER"` yer tutucusuyla gelir; kendi kimliğini ayarlamak için Claude Code'da `/mem0 onboard` çalıştır.

Mevcut `settings.json` değerlerin korunur: harness yalnız olmayan ya da kendi yazdığı ve senin dokunmadığın anahtarları yazar; korunanlar kurulum raporunda "kept your value for <anahtar>" olarak listelenir.

## Repoda ASLA olmayanlar

- Kimlik bilgileri, API anahtarları, token'lar, oturum dosyaları
- Konuşma geçmişi, hafıza ve vault içeriği
- Marka dosyaları (logolar, marka profilleri); skill'ler yalnız nötr motor olarak gelir
- Kullanıcı adı, e-posta, mutlak kullanıcı yolları

## Bakımcı akışı (kaynak makine)

```
python export.py     # canlı kurulumu payload/'a yazar; scrub taraması sıfır bulgu vermeli
git add -A && git commit -m "chore: export"
git push
```

Scrub bulgu verirse `export.py` durur (exit 1); bulguyu giderip yeniden çalıştır. Scrub geçmeden commit atma.

## Sağlık denetimi

```
python doctor.py [--home DIR] [--json]
```

Çıkış: 0 sağlıklı, 1 kırmızı var, 2 kurulu değil.

## Lisans

TBD
