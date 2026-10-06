"""Doctor'un okuduğu girdiler: durum dosyası, manifest, settings."""
import json
from pathlib import Path

STATE_NAME = ".claude-harness.json"
FLAGS = ("vault", "orca", "codex")


def claude_dir(home):
    return Path(home) / ".claude"


def state_path(home):
    return claude_dir(home) / STATE_NAME


def read_json(path):
    """JSON oku; (veri, hata) döndür."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, "dosya yok"
    except (OSError, ValueError) as exc:
        return None, f"okunamadı: {exc}"


def active_flags(answers):
    """Cevaplarda true olan koşul bayrakları."""
    return frozenset(f for f in FLAGS if answers.get(f) is True)


def applies(item, flags):
    """Öğenin `requires` koşulu tutuyor mu (yoksa her zaman geçerli)."""
    need = item.get("requires")
    return need is None or need in flags


def version_tuple(text):
    parts = []
    for piece in str(text).split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)
