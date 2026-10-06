# Context

**Harness**: Bir makinedeki Claude Code kurulumunun bütünü: global CLAUDE.md, skill'ler, plugin'ler, marketplace'ler, ayarlar, hook'lar.
_Avoid_: setup, config, ortam

**Kaynak makine**: Harness'in canlı hâlinin durduğu ve `export.py` ile repoya aktarıldığı makine.
_Avoid_: ana bilgisayar

**Hedef makine**: Repo linki verilip harness'in kurulduğu başka bilgisayar ya da cloud ortamı.
_Avoid_: yeni makine, client

**Payload**: Repoda duran, kişisel bilgisi yer tutucuya çevrilmiş harness kopyası (`payload/`).
_Avoid_: backup, yedek

**Opsiyonel parça**: Kurulumda soruyla açılan bölüm: vault, Orca, Codex, izin listesi.
_Avoid_: modül, eklenti

**Scrub**: Export sırasında kişisel bilgi ve sırları yer tutucuya çeviren ve kalan sızıntıda export'u durduran tarama.
_Avoid_: temizlik, sanitize
