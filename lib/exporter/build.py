"""Kaynak ev dizininden bellekte payload dosya haritası üretir (yazmaz)."""
import hashlib
import json
from pathlib import Path

from .settings import build_base_settings, build_permissions, dump_json
from .textops import is_excluded, normalize_newlines, transform_bytes

GLOSSARY_TMPL = "# Sözlük\n\nFormat: `- **terim** — kısa açıklama`\n"
DEPS_TMPL = (
    "# Bağımlılıklar\n\n"
    "Format:\n\n"
    "```\n"
    "- <ne> -> <neye bağlı>\n"
    "  kontrol: <bash komutu>\n"
    "  bozuksa: <kırmızıysa yapılacak>\n"
    "```\n"
)


# harness.json glob'ları yalnız ilk seviye node_modules'u yakalar; iç içe olanlar da hiç girmemeli
ALWAYS_EXCLUDE = ("**/node_modules/**", "**/__pycache__/**")


class ExportError(Exception):
    pass


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def source_path_for(payload_path, source_home):
    """Payload yolunun canlı kaynak karşılığı; eşleşmesi yoksa None."""
    home = Path(source_home)
    if payload_path.startswith("skills/"):
        return home / ".claude" / payload_path
    if payload_path == "global/CLAUDE.md.tmpl":
        return home / ".claude" / "CLAUDE.md"
    if payload_path == "codex/config.toml":
        return home / ".codex" / "config.toml"
    return None


def _read_live_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExportError(f"{path} okunamadı: {exc}") from exc


def _skill_files(source_home, harness, pairs, local_excludes=()):
    export = harness.get("export", {})
    # Yerel exclude'lar (marka yolları) public harness.json'a girmez; burada birleşir
    excludes = list(export.get("exclude", [])) + list(local_excludes) + list(ALWAYS_EXCLUDE)
    files = {}
    for skill in harness.get("ownSkills", []):
        root = Path(source_home) / ".claude" / "skills" / skill["name"]
        if not root.is_dir():
            raise ExportError(f"skill kaynağı yok: {root}")
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            rel_claude = "skills/" + path.relative_to(root.parent).as_posix()
            if is_excluded(rel_claude, excludes):
                continue
            files[rel_claude] = transform_bytes(path.read_bytes(), pairs)
    return files


def _codex_config(source_home, pairs):
    path = Path(source_home) / ".codex" / "config.toml"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    kept = [
        ln
        for ln in text.splitlines(keepends=True)
        if not any(w in ln.lower() for w in ("auth", "key", "token", "secret"))
    ]
    return transform_bytes("".join(kept).encode("utf-8"), pairs)


def _overrides(overrides_dir):
    root = Path(overrides_dir)
    if not root.is_dir():
        return {}
    return {
        p.relative_to(root).as_posix(): normalize_newlines(p.read_bytes())
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def check_overrides(override_paths, source_home, lock):
    """Kaynağı değişmiş ya da kilitsiz override'lar için uyarı listesi."""
    warnings = []
    for path in sorted(override_paths):
        src = source_path_for(path, source_home)
        if path not in lock:
            warnings.append(f"override {path}: overrides.lock girdisi yok")
            continue
        recorded = lock[path]
        if recorded is None or src is None:
            continue
        if not src.is_file():
            warnings.append(f"override {path}: kaynak dosya artık yok, override eskimiş olabilir")
        elif sha256_bytes(src.read_bytes()) != recorded:
            warnings.append(f"override {path}: kaynak değişti, override eskimiş olabilir")
    return warnings


def build_payload(source_home, harness, local, overrides_dir, lock):
    """(dosya_haritası, uyarılar) döndür. Yol -> bayt; girdiler değiştirilmez."""
    pairs = local.replace
    claude_md = Path(source_home) / ".claude" / "CLAUDE.md"
    if not claude_md.is_file():
        raise ExportError(f"CLAUDE.md yok: {claude_md}")
    live_settings = _read_live_json(Path(source_home) / ".claude" / "settings.json")

    files = {
        "global/CLAUDE.md.tmpl": transform_bytes(claude_md.read_bytes(), pairs),
        "global/GLOSSARY.md.tmpl": GLOSSARY_TMPL.encode("utf-8"),
        "global/BAGIMLILIKLAR.md.tmpl": DEPS_TMPL.encode("utf-8"),
        "settings/base.json": dump_json(
            build_base_settings(live_settings, harness, pairs)
        ).encode("utf-8"),
        "settings/permissions.json": dump_json(
            build_permissions(live_settings, harness, pairs)
        ).encode("utf-8"),
    }
    files.update(_skill_files(source_home, harness, pairs, local.exclude))
    codex = _codex_config(source_home, pairs)
    if codex is not None:
        files["codex/config.toml"] = codex

    overrides = _overrides(overrides_dir)
    warnings = check_overrides(overrides, source_home, lock)
    files.update(overrides)
    return files, warnings


def manifest_bytes(files):
    entries = [
        {"path": p, "sha256": sha256_bytes(b)}
        for p, b in sorted(files.items())
        if p != "MANIFEST.json"
    ]
    return (json.dumps(entries, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
