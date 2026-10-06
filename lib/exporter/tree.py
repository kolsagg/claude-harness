"""Ağaç taraması: git'in izlediği (ve izlenmeyen ama yok sayılmayan) tüm dosyalar."""
import subprocess
from pathlib import Path

from .build import ExportError

# Yalnız yerelde durur, asla izlenmez; kişisel haritanın kendisi
LOCAL_ONLY = ("export.local.json",)


def _git_list(root, *args):
    try:
        res = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", *args],
            capture_output=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ExportError(f"git ls-files çalışmadı ({root}): {exc}") from exc
    return [p for p in res.stdout.decode("utf-8").split("\0") if p]


def tree_paths(root):
    """İzlenen + izlenmeyen-yok-sayılmayan dosya yolları (git yolu, sıralı, tekil)."""
    tracked = _git_list(root, "--cached")
    untracked = _git_list(root, "--others", "--exclude-standard")
    return sorted({p for p in tracked + untracked if p not in LOCAL_ONLY})


def read_tree(root, skip_prefixes=()):
    """yol -> bayt; diskte olmayan (silinmiş) izlenen dosyalar atlanır."""
    root = Path(root)
    files = {}
    for rel in tree_paths(root):
        if any(rel.startswith(p) for p in skip_prefixes):
            continue
        path = root / rel
        if path.is_file():
            files[rel] = path.read_bytes()
    return files
