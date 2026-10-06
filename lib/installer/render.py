"""Değerler, bayraklar ve render sarmalayıcısı (vault yokken kaçak VAULT_PATH tespiti dahil)."""
import json

from lib.template import render_json, render_text

_PROBE = "@@VAULT_PATH_PROBE@@"


def fwd(path):
    return str(path).replace("\\", "/")


def build_values(answers, home, windows):
    vault = answers.get("VAULT_PATH")
    return {
        "USER_NAME": answers["USER_NAME"],
        "LANGUAGE": answers["LANGUAGE"],
        "GITHUB_OWNER": answers["GITHUB_OWNER"],
        "VAULT_PATH": fwd(vault) if vault else "",
        "HOME": fwd(home),
        "PYTHON": "py -3" if windows else "python3",
    }


def build_flags(answers):
    return frozenset(k for k in ("vault", "orca", "codex") if answers.get(k))


def decode_text(data):
    """UTF-8 olarak çözülürse metin, değilse None (ikili dosya)."""
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


class Renderer:
    def __init__(self, values, flags):
        self.values = dict(values)
        self.flags = frozenset(flags)
        self.stray = []  # vault yokken VAULT_PATH kullanan dosyalar

    def _check_stray(self, label, probe_output):
        if not self.values["VAULT_PATH"] and _PROBE in probe_output:
            self.stray.append(label)

    def text(self, label, text):
        probe_values = {**self.values, "VAULT_PATH": _PROBE}
        self._check_stray(label, render_text(text, probe_values, self.flags))
        return render_text(text, self.values, self.flags)

    def json_obj(self, label, data):
        probe_values = {**self.values, "VAULT_PATH": _PROBE}
        self._check_stray(label, json.dumps(render_json(data, probe_values, self.flags)))
        return render_json(data, self.values, self.flags)

    def file_bytes(self, label, data):
        """Metin dosyayı render eder, ikiliyi olduğu gibi döndürür."""
        text = decode_text(data)
        if text is None:
            return data
        return self.text(label, text).encode("utf-8")
