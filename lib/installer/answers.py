"""Cevaplar: bayraklar > --answers dosyası > tty ise etkileşimli soru."""
import argparse
import json
import os
from pathlib import Path

TEXT_KEYS = ("USER_NAME", "LANGUAGE", "GITHUB_OWNER")
BOOL_KEYS = ("orca", "codex")
YES = {"y", "yes", "e", "evet", "true", "1"}
NO = {"n", "no", "h", "hayir", "hayır", "false", "0"}
BOOL_KEYS_ALL = ("orca", "codex", "permissions")


class AnswerError(ValueError):
    """Cevap dosyasında tanınmayan değer; kurulum exit 2 ile durur."""


def parse_bool(key, value):
    """JSON true/false ya da açık evet/hayır sözcüğü; başka her şey hata. None = cevap yok."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        word = value.strip().lower()
        if word in YES:
            return True
        if word in NO:
            return False
    raise AnswerError(
        f"'{key}' için geçersiz değer {value!r}: true/false ya da evet/hayır (yes/no) bekleniyor"
    )


class MissingAnswers(Exception):
    def __init__(self, keys):
        super().__init__(", ".join(keys))
        self.keys = list(keys)


def build_parser():
    p = argparse.ArgumentParser(prog="install.py", description="claude-harness kurulumu")
    p.add_argument("--name")
    p.add_argument("--language")
    p.add_argument("--github-owner", dest="github_owner")
    p.add_argument("--vault", metavar="PATH")
    p.add_argument("--no-vault", action="store_true")
    p.add_argument("--orca", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--codex", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--permissions", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--answers", metavar="FILE")
    p.add_argument("--home", metavar="DIR")
    p.add_argument("--skip-external", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--yes", action="store_true")
    return p


def _normalize_path(raw):
    path = Path(os.path.expanduser(str(raw)))
    return str(path if path.is_absolute() else Path.cwd() / path)


def _file_vault(data):
    """Dosyadaki vault/VAULT_PATH birleşimini (karar, yol) olarak yorumlar; karar None = belirsiz.

    vault: false/hayır sözcüğü -> vault yok; evet sözcüğü/true -> VAULT_PATH ile; başka metin -> yol.
    """
    flag = data.get("vault")
    path = data.get("VAULT_PATH")
    if path is not None and not isinstance(path, str):
        raise AnswerError(f"'VAULT_PATH' metin olmalı, bulunan: {path!r}")
    path = path or None
    if flag is None:
        return (True, path) if path else (None, None)
    if flag is False:
        return False, None
    if flag is True:
        return True, path
    if isinstance(flag, str):
        word = flag.strip().lower()
        if word in NO:
            return False, None
        if word in YES or not word:
            return True, path
        return True, flag.strip()
    raise AnswerError(f"'vault' için geçersiz değer {flag!r}: true/false ya da bir yol bekleniyor")


def _from_file(args):
    if not args.answers:
        return {}
    data = json.loads(Path(args.answers).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("--answers dosyası bir JSON nesnesi olmalı")
    return data


def merge_sources(args, previous=None):
    """Bayrak > dosya > önceki durum cevapları; belirsiz anahtarlar None kalır."""
    file_data = _from_file(args)
    prev = previous if isinstance(previous, dict) else {}
    data = {**prev, **{k: v for k, v in file_data.items() if k not in ("vault", "VAULT_PATH")}}
    out = {
        "USER_NAME": args.name or data.get("USER_NAME"),
        "LANGUAGE": args.language or data.get("LANGUAGE"),
        "GITHUB_OWNER": args.github_owner or data.get("GITHUB_OWNER"),
    }
    for key in BOOL_KEYS_ALL:
        flag = getattr(args, key)
        out[key] = flag if flag is not None else parse_bool(key, data.get(key))
    if args.no_vault:
        out["vault"], out["VAULT_PATH"] = False, None
    elif args.vault:
        out["vault"], out["VAULT_PATH"] = True, args.vault
    else:
        decided, path = _file_vault(file_data)
        if decided is None:
            decided, path = _file_vault(prev)
        out["vault"], out["VAULT_PATH"] = decided, path
    return out


def missing_keys(merged):
    missing = [k for k in TEXT_KEYS if not merged.get(k)]
    if merged["vault"] is None or (merged["vault"] and not merged["VAULT_PATH"]):
        missing.append("vault")
    missing.extend(k for k in BOOL_KEYS if merged.get(k) is None)
    return missing


def _ask_bool(question, deps):
    """Boş yanıt = hayır; tanınmayan yanıtta 3 denemeye kadar yeniden sorar, sonra hayır."""
    for _ in range(3):
        raw = deps.ask(f"{question} [e/H]: ").strip()
        if not raw:
            return False
        try:
            return parse_bool("yanıt", raw)
        except AnswerError:
            deps.say("Lütfen evet (e) ya da hayır (h) yaz.")
    return False


def _prompt(key, question, deps):
    try:
        if key == "vault":
            raw = deps.ask(f"{question}\n  (yol yaz; vault yoksa boş bırak): ").strip()
            return {"vault": bool(raw), "VAULT_PATH": raw or None}
        if key in BOOL_KEYS_ALL:
            return {key: _ask_bool(question, deps)}
        return {key: deps.ask(f"{question}: ").strip()}
    except EOFError:
        return {}


def collect(args, manifest, deps, previous=None):
    """Tam cevap sözlüğünü döndürür; eksik ve tty yoksa MissingAnswers fırlatır."""
    merged = merge_sources(args, previous)
    missing = missing_keys(merged)
    if deps.isatty():
        questions = manifest.get("questions", {})
        # permissions zorunlu değil ama tty'de sorulur (varsayılan hayır)
        ask_keys = missing + (["permissions"] if merged.get("permissions") is None else [])
        for key in ask_keys:
            merged = {**merged, **_prompt(key, questions.get(key, key), deps)}
        missing = missing_keys(merged)
    if missing:
        raise MissingAnswers(missing)
    vault = merged["VAULT_PATH"] if merged["vault"] else None
    return {
        "USER_NAME": merged["USER_NAME"],
        "LANGUAGE": merged["LANGUAGE"],
        "GITHUB_OWNER": merged["GITHUB_OWNER"],
        "VAULT_PATH": _normalize_path(vault).replace("\\", "/") if vault else None,
        "vault": bool(merged["vault"]),
        "orca": bool(merged["orca"]),
        "codex": bool(merged["codex"]),
        "permissions": bool(merged.get("permissions")),  # eksikse asla "evet" varsayma
    }


def missing_report(keys, manifest):
    questions = manifest.get("questions", {})
    return [{"key": k, "question": questions.get(k, k)} for k in keys]
