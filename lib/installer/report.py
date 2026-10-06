"""Kurulum sonu insan raporu."""
import json


def missing_json(items):
    return json.dumps(items, ensure_ascii=False, indent=2)


def _section(title, lines):
    return [f"{title}:"] + [f"  - {l}" for l in lines] if lines else []


def build_report(*, answers, actions, results, warnings, skip_external, dry_run, planned, notes, python_cmd, kept=()):
    created = [p for a, p in actions if a in ("created", "updated")]
    unchanged = [p for a, p in actions if a in ("unchanged", "kept")]
    removed = [p for a, p in actions if a == "removed"]
    failed = [r for r in results if not r.ok and not r.skipped]
    skipped = [r for r in results if r.skipped]
    okay = [r for r in results if r.ok]
    head = "[dry-run] Plan (hiçbir şey yazılmadı)" if dry_run else "claude-harness kurulumu bitti"
    lines = [head, ""]
    lines += _section("Yazılan/güncellenen dosyalar" if not dry_run else "Yazılacak dosyalar", created)
    lines += _section("Değişmedi/korundu", [f"{len(unchanged)} dosya"] if unchanged else [])
    lines += _section("Silinen eski harness dosyaları", removed)
    if dry_run:
        lines += _section("Çalıştırılacak harici komutlar", planned)
    elif skip_external:
        lines.append("Harici adımlar atlandı (--skip-external).")
    lines += _section("Başarılı adımlar", [r.name for r in okay])
    lines += _section("Atlanan adımlar", [f"{r.name}: {r.detail}" for r in skipped])
    lines += _section("BAŞARISIZ adımlar", [f"{r.name}: {r.detail}" for r in failed])
    lines += _section("Korunan kendi ayarların", list(kept))
    lines += _section("Uyarılar", warnings)
    steps = list(notes)
    if answers["vault"]:
        steps.append(
            "Vault: beyin köprü hook'larını bu repo kurmaz. Vault'un kendi resmi Beyin V3 kurulumu getirir; "
            f"vault kökünde `{python_cmd} beyin.py doctor` ile sağlığı, `{python_cmd} beyin.py update` ile güncellemeyi çalıştır."
        )
    if answers["orca"]:
        steps.append("Orca: Orca uygulaması kendi hook'larını kurar; uygulamayı bir kez aç.")
    steps.append("Claude Code'u yeniden başlat; giriş yapılmadıysa `claude` ile oturum aç.")
    lines += _section("Sonraki elle adımlar", steps)
    return "\n".join(lines)
