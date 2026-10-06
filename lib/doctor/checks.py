"""Tek tek denetimler. Her fonksiyon Check listesi döndürür; girdiyi değiştirmez."""
import json
import os
import shutil
import subprocess
from pathlib import Path

from lib.template import PLACEHOLDER

from .inputs import active_flags, applies, claude_dir, version_tuple
from .model import MANUAL, OK, RED, WARN, Check

MARK_START = "<!-- claude-harness:start -->"
MARK_END = "<!-- claude-harness:end -->"
OFFICIAL_MARKETPLACE = "claude-plugins-official"
MAX_SCAN_BYTES = 2_000_000


def default_run(argv, env_extra):
    """Komutu çalıştır; (çıkış kodu, stdout) döndür. Başarısızlıkta (None, hata)."""
    env = {**os.environ, **env_extra}
    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=60, env=env, encoding="utf-8"
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc)
    return proc.returncode, proc.stdout


def check_version(state, manifest):
    installed, repo = str(state.get("version", "")), str(manifest.get("version", ""))
    if not installed:
        return [Check(RED, "Sürüm", "durum dosyasında sürüm yok")]
    if version_tuple(repo) > version_tuple(installed):
        return [Check(WARN, "Sürüm", f"güncelleme var: kurulu {installed}, repo {repo}")]
    return [Check(OK, "Sürüm", f"kurulu {installed}, repo {repo}")]


def check_files(state, home):
    base = claude_dir(home)
    missing = [rel for rel in state.get("files", []) if not (base / rel).is_file()]
    if missing:
        return [Check(RED, "Kurulan dosyalar", "eksik: " + ", ".join(missing))]
    return [Check(OK, "Kurulan dosyalar", f"{len(state.get('files', []))} dosya yerinde")]


def _read_text(path):
    try:
        if path.stat().st_size > MAX_SCAN_BYTES:
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def check_placeholders(state, home):
    base = claude_dir(home)
    rels = list(dict.fromkeys([*state.get("files", []), "settings.json", "CLAUDE.md"]))
    found = []
    for rel in rels:
        path = base / rel
        if path.is_file():
            names = sorted({m.group(0) for m in PLACEHOLDER.finditer(_read_text(path))})
            if names:
                found.append(f"{rel} ({' '.join(names)})")
    if found:
        return [Check(RED, "Yer tutucu kalıntısı", "; ".join(found))]
    return [Check(OK, "Yer tutucu kalıntısı", "yok")]


def check_claude_md(home):
    path = claude_dir(home) / "CLAUDE.md"
    if not path.is_file():
        return [Check(RED, "Global CLAUDE.md", "dosya yok")]
    text = _read_text(path)
    start, end = text.find(MARK_START), text.find(MARK_END)
    if start == -1 or end == -1 or end < start:
        return [Check(RED, "Global CLAUDE.md", "claude-harness start/end bloğu yok")]
    return [Check(OK, "Global CLAUDE.md", "yönetilen blok var")]


def load_settings(home):
    path = claude_dir(home) / "settings.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "dosya yok"
    except (OSError, ValueError) as exc:
        return None, f"okunamadı: {exc}"
    return (data, None) if isinstance(data, dict) else (None, "kök nesne değil")


def expected_plugins(manifest, flags):
    return [p["id"] for p in manifest.get("plugins", []) if applies(p, flags)]


def check_settings(settings, err, manifest, flags, kept=()):
    if err:
        return [Check(RED, "settings.json", err)]
    out = [Check(OK, "settings.json", "geçerli JSON")]
    enabled = settings.get("enabledPlugins", {})
    off = [pid for pid in expected_plugins(manifest, flags) if enabled.get(pid) is not True]
    # kullanıcının bilerek kapattığı (kurulumcunun "korundu" diye kaydettiği) plugin kırmızı değil uyarıdır
    by_user = [pid for pid in off if enabled.get(pid) is False and f"enabledPlugins.{pid}" in kept]
    broken = [pid for pid in off if pid not in by_user]
    if broken:
        out.append(Check(RED, "enabledPlugins", "kapalı/eksik: " + ", ".join(broken)))
    if by_user:
        out.append(Check(WARN, "enabledPlugins", "senin kapattığın (korundu): " + ", ".join(by_user)))
    if not off:
        out.append(Check(OK, "enabledPlugins", "beklenen plugin'ler açık"))
    known = settings.get("extraKnownMarketplaces", {})
    wanted = [m["name"] for m in manifest.get("marketplaces", []) if m["name"] != OFFICIAL_MARKETPLACE]
    absent = [name for name in wanted if name not in known]
    if absent:
        out.append(Check(RED, "extraKnownMarketplaces", "eksik: " + ", ".join(absent)))
    else:
        out.append(Check(OK, "extraKnownMarketplaces", "resmi olmayan marketplace'ler tanımlı"))
    return out


def check_statusline(settings, which):
    """ccstatusline hook'u ya da statusLine'ı varsa komut PATH'te olmalı."""
    if not isinstance(settings, dict):
        return []
    scanned = json.dumps([settings.get("hooks", {}), settings.get("statusLine", {})])
    if "ccstatusline" not in scanned or which("ccstatusline"):
        return []
    return [Check(WARN, "ccstatusline", "ccstatusline kurulu değil: npm install -g ccstatusline")]


def check_cli_plugins(home, manifest, flags, which, run, skipped=False):
    exe = which("claude")
    name = "claude plugin list"
    if not exe:
        return [Check(MANUAL, name, "claude PATH'te yok; plugin kurulumunu elle doğrula")]
    code, out = run(
        [exe, "plugin", "list", "--json"], {"CLAUDE_CONFIG_DIR": str(claude_dir(home))}
    )
    try:
        listed = json.loads(out) if code == 0 else None
    except (TypeError, ValueError):
        listed = None
    if not isinstance(listed, list):
        return [Check(MANUAL, name, "çıktı okunamadı; plugin kurulumunu elle doğrula")]
    installed = {p.get("id"): p for p in listed if isinstance(p, dict)}
    missing = [pid for pid in expected_plugins(manifest, flags) if pid not in installed]
    if missing:
        # --skip-external ile kurulduysa plugin kurulumu elle yapılacak iştir
        level = WARN if skipped else RED
        return [Check(level, name, "kurulu değil: " + ", ".join(missing))]
    return [Check(OK, name, "beklenen plugin'ler kurulu")]


def check_own_skills(manifest, flags, home):
    skills = claude_dir(home) / "skills"
    wanted = [s["name"] for s in manifest.get("ownSkills", []) if applies(s, flags)]
    missing = [n for n in wanted if not (skills / n / "SKILL.md").is_file()]
    if missing:
        return [Check(RED, "Kendi skill'ler", "SKILL.md yok: " + ", ".join(missing))]
    return [Check(OK, "Kendi skill'ler", f"{len(wanted)} skill tamam")]


def check_external_skills(manifest, flags, home, skipped=False):
    roots = (claude_dir(home) / "skills", Path(home) / ".agents" / "skills")
    wanted = [s["skill"] for s in manifest.get("externalSkills", []) if applies(s, flags)]
    missing = [n for n in wanted if not any((r / n).exists() or (r / n).is_symlink() for r in roots)]
    if missing:
        # --skip-external ile kurulduysa eksik harici skill beklenen durumdur
        level = WARN if skipped else RED
        return [Check(level, "Harici skill'ler", "yok: " + ", ".join(missing))]
    return [Check(OK, "Harici skill'ler", f"{len(wanted)} skill var")]


def check_codex(flags, home, which):
    if "codex" not in flags:
        return []
    out = []
    if (Path(home) / ".codex" / "config.toml").is_file():
        out.append(Check(OK, "Codex config", "config.toml var"))
    else:
        out.append(Check(RED, "Codex config", "~/.codex/config.toml yok"))
    if which("codex"):
        out.append(Check(OK, "codex komutu", "PATH'te"))
    else:
        out.append(Check(WARN, "codex komutu", "PATH'te değil"))
    return out


def check_vault(answers, flags, settings):
    if "vault" not in flags:
        return []
    vault = answers.get("VAULT_PATH")
    if not vault or not Path(vault).exists():
        out = [Check(RED, "Vault yolu", f"yok: {vault}")]
    else:
        out = [Check(OK, "Vault yolu", "var")]
    hooks = json.dumps((settings or {}).get("hooks", {}).get("SessionStart", []))
    # beyin köprüsü PowerShell -EncodedCommand ile gelir; düz metinde "beyin" görünmeyebilir
    if "beyin" in hooks or "-EncodedCommand" in hooks:
        out.append(Check(OK, "Beyin köprüsü", "SessionStart hook'u var"))
    else:
        out.append(Check(WARN, "Beyin köprüsü", "SessionStart hook'unda beyin yok; vault'un kendi kurulumunu çalıştır"))
    return out


def check_steps(state):
    steps = state.get("steps", [])
    bad = [s for s in steps if not s.get("ok") and not s.get("skipped")]
    skipped = [s for s in steps if not s.get("ok") and s.get("skipped")]
    if not bad and not skipped:
        return [Check(OK, "Kurulum adımları", f"{len(steps)} adım başarılı")]
    # atlanan adım (ör. claude PATH'te yok) elle tamamlanacak iştir, hata değil
    return [
        *[Check(RED, f"Adım: {s.get('name', '?')}", str(s.get("detail", ""))) for s in bad],
        *[Check(WARN, f"Atlandı: {s.get('name', '?')}", str(s.get("detail", ""))) for s in skipped],
    ]


def run_all(state, manifest, home, which=shutil.which, run=default_run):
    answers = state.get("answers", {})
    flags = active_flags(answers)
    settings, err = load_settings(home)
    kept = [k for k in state.get("settingsKept", []) if isinstance(k, str)]
    return [
        *check_version(state, manifest),
        *check_files(state, home),
        *check_placeholders(state, home),
        *check_claude_md(home),
        *check_settings(settings, err, manifest, flags, kept),
        *check_statusline(settings, which),
        *check_cli_plugins(home, manifest, flags, which, run, bool(state.get("skipExternal"))),
        *check_own_skills(manifest, flags, home),
        *check_external_skills(manifest, flags, home, bool(state.get("skipExternal"))),
        *check_codex(flags, home, which),
        *check_vault(answers, flags, settings),
        *check_steps(state),
    ]
