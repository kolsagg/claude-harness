"""Kendi skill'lerimizi render ederek kurma ve eski harness dosyalarını temizleme."""
from pathlib import Path

from .model import StepResult

_SKIP_DIRS = {"__pycache__", "node_modules"}


def wanted_skills(manifest, flags):
    return [s for s in manifest.get("ownSkills", []) if s.get("requires") is None or s["requires"] in flags]


def _skill_files(src):
    return sorted(
        p for p in src.rglob("*") if p.is_file() and not (set(p.relative_to(src).parts) & _SKIP_DIRS)
    )


def install_skill(name, payload, claude, renderer, writer):
    """Yazılan dosyaların .claude'a göre yollarını döndürür."""
    src = Path(payload) / "skills" / name
    if not src.is_dir():
        raise FileNotFoundError(f"payload/skills/{name} yok")
    rels = []
    for file in _skill_files(src):
        rel = f"skills/{name}/{file.relative_to(src).as_posix()}"
        data = renderer.file_bytes(rel, file.read_bytes())
        writer.write(Path(claude) / rel, data, mode_from=file)
        rels.append(rel)
    return rels


def install_all(manifest, payload, claude, renderer, writer, flags):
    """(dosyalar, kurulan adlar, sonuçlar). Bir skill'in hatası diğerini durdurmaz."""
    files, installed, results = [], [], []
    for skill in wanted_skills(manifest, flags):
        name = skill["name"]
        try:
            files = files + install_skill(name, payload, claude, renderer, writer)
            installed = installed + [name]
        except (OSError, ValueError, KeyError) as exc:
            results = results + [StepResult(f"core:skill:{name}", False, str(exc))]
    return files, installed, results


def remove_stale(old_files, new_files, failed_names, claude, writer):
    """Eski durum dosyasında olup artık kurulmayan skill dosyalarını siler.

    Durum dosyasında olmayan (kullanıcıya ait) dosyaya dokunulmaz. Bu turda hata veren
    skill'in dosyaları korunur.
    """
    new_set = set(new_files)
    skills_root = (Path(claude) / "skills").resolve()
    removed = []
    for rel in old_files:
        parts = rel.split("/")
        if parts[0] != "skills" or len(parts) < 3 or rel in new_set or ".." in parts:
            continue
        if parts[1] in failed_names:
            continue
        target = Path(claude) / rel
        if skills_root not in target.resolve().parents or not target.is_file():
            continue
        writer.remove(target, stop_at=Path(claude) / "skills")
        removed = removed + [rel]
    return removed
