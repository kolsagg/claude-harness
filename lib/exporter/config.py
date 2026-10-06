"""Yerel eşleme dosyası (export.local.json) ve harness.json yükleme."""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class LocalConfig:
    replace: tuple = ()  # ((from, to), ...) sırayla uygulanır
    forbidden: tuple = ()
    exclude: tuple = ()  # yerel ek exclude glob'ları; harness.json'unkilerle birleşir
    warnings: tuple = field(default_factory=tuple)


# JSON'da geçerli kaçışlar dışında kalan ters eğik çizgiler (Windows yolları)
_LONE_BACKSLASH = re.compile(r'\\(?!["\\/bfnrtu])')


def _pairs(raw):
    if isinstance(raw, dict):
        raw = list(raw.items())
    pairs = []
    for item in raw:
        if not (isinstance(item, (list, tuple)) and len(item) == 2):
            raise ConfigError(f"replace girdisi [from, to] olmalı: {item!r}")
        pairs.append((str(item[0]), str(item[1])))
    return tuple(pairs)


def load_local_config(path):
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"yerel eşleme dosyası yok: {path}")
    text = path.read_text(encoding="utf-8")
    warnings = ()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Elle yazılmış yol satırlarında kaçışsız ters eğik çizgi sık görülür
        try:
            data = json.loads(_LONE_BACKSLASH.sub(r"\\\\", text))
        except json.JSONDecodeError as exc:
            raise ConfigError(f"{path}: geçersiz JSON: {exc}") from exc
        warnings = (f"{path.name}: kaçışsız ters eğik çizgiler onarılarak okundu; dosyayı düzeltin",)
    return LocalConfig(
        replace=_pairs(data.get("replace", [])),
        forbidden=tuple(str(w) for w in data.get("forbidden", [])),
        exclude=tuple(str(g) for g in data.get("exclude", [])),
        warnings=warnings,
    )


def load_harness(root):
    path = Path(root) / "harness.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"harness.json okunamadı: {exc}") from exc
