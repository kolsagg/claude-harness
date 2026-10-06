"""Durum dosyası ~/.claude/.claude-harness.json ve payload MANIFEST doğrulaması."""
import hashlib
import json
from pathlib import Path

STATE_NAME = ".claude-harness.json"


def read_state(claude):
    path = Path(claude) / STATE_NAME
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def merge_steps(old_steps, new_steps):
    """Aynı adlı eski adım yenisiyle değişir; yeniden çalışmayanlar kalır; core: kayıtları sıfırlanır."""
    names = {s["name"] for s in new_steps}
    kept = [s for s in old_steps if isinstance(s, dict) and s.get("name") not in names
            and not str(s.get("name", "")).startswith("core:")]
    return kept + list(new_steps)


def build_state(version, installed_at, repo, answers, files, steps, skip_external, settings_written=None, settings_kept=()):
    return {
        "version": version,
        "installedAt": installed_at,
        "repo": str(repo).replace("\\", "/"),
        "answers": {
            "USER_NAME": answers["USER_NAME"],
            "LANGUAGE": answers["LANGUAGE"],
            "GITHUB_OWNER": answers["GITHUB_OWNER"],
            "VAULT_PATH": answers["VAULT_PATH"],
            "vault": answers["vault"],
            "orca": answers["orca"],
            "codex": answers["codex"],
            "permissions": answers["permissions"],
        },
        "skipExternal": bool(skip_external),
        "files": sorted(set(files)),
        "steps": list(steps),
        "settingsWritten": dict(settings_written or {}),
        "settingsKept": sorted(set(settings_kept)),
    }


def write_state(claude, state):
    path = Path(claude) / STATE_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def verify_manifest(payload):
    """payload/MANIFEST.json varsa sha256'ları denetler; sorunları uyarı listesi olarak döndürür."""
    path = Path(payload) / "MANIFEST.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        entries = data.get("files", data) if isinstance(data, dict) else data
        if isinstance(entries, list):
            entries = {e["path"]: e["sha256"] for e in entries}
        problems = []
        for rel, digest in entries.items():
            target = Path(payload) / rel
            if not target.is_file():
                problems.append(f"MANIFEST: {rel} payload'ta yok")
            elif hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                problems.append(f"MANIFEST: {rel} sha256 uyuşmuyor")
        return problems
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        return [f"MANIFEST.json okunamadı: {exc}"]
