"""Denetim sonucu modeli ve çıkış kodu kuralı."""
from dataclasses import dataclass

OK = "green"
RED = "red"
WARN = "yellow"
MANUAL = "manual"

LABELS = {OK: "TAMAM ", RED: "HATA  ", WARN: "UYARI ", MANUAL: "MANUEL"}


@dataclass(frozen=True)
class Check:
    status: str
    name: str
    detail: str = ""

    def as_dict(self):
        return {"status": self.status, "name": self.name, "detail": self.detail}


def exit_code(checks):
    """Herhangi bir kırmızı varsa 1, yoksa 0."""
    return 1 if any(c.status == RED for c in checks) else 0


def format_line(check):
    tail = f" - {check.detail}" if check.detail else ""
    return f"[{LABELS[check.status]}] {check.name}{tail}"
