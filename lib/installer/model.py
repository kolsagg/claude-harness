"""Ortak veri tipleri ve enjekte edilebilir bağımlılıklar."""
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional


@dataclass(frozen=True)
class StepResult:
    name: str
    ok: bool
    detail: str = ""
    skipped: bool = False

    def to_state(self):
        entry = {"name": self.name, "ok": self.ok, "detail": self.detail}
        if self.skipped:
            entry["skipped"] = True
        return entry


@dataclass(frozen=True)
class Step:
    """Harici bir komut adımı. argv liste olarak tutulur, shell kullanılmaz."""

    name: str
    argv: tuple
    needs_cli: Optional[str] = None  # ör. "claude": PATH'te yoksa adım atlanır
    after: Optional[str] = None  # bu adım başarısızsa bu da atlanır
    note: str = ""


def default_runner(argv, cwd=None):
    """(returncode, çıktı) döndürür. Tek giriş noktası; testlerde yerine konur."""
    exe = shutil.which(argv[0]) or argv[0]
    try:
        proc = subprocess.run(
            [exe, *argv[1:]],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=900,
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return 127, f"komut bulunamadı: {argv[0]}"
    except subprocess.TimeoutExpired:
        return 124, "zaman aşımı (900 sn)"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def stdin_interactive():
    """Gerçek terminal mi? Windows'ta NUL cihazı isatty() True döner, konsol modu ile ayıklanır."""
    try:
        if not sys.stdin.isatty():
            return False
        if sys.platform.startswith("win"):
            import ctypes

            mode = ctypes.c_uint32()
            handle = ctypes.windll.kernel32.GetStdHandle(-10)
            return bool(ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)))
        return True
    except (AttributeError, OSError, ValueError):
        return False


@dataclass
class Deps:
    runner: Callable = default_runner
    which: Callable = shutil.which
    now: Callable = datetime.now
    isatty: Callable = stdin_interactive
    ask: Callable = input
    out: object = field(default_factory=lambda: sys.stdout)
    windows: bool = sys.platform.startswith("win")
    real_home: Optional[object] = None  # testlerde gerçek ev dizini yerine konur

    def say(self, text=""):
        print(text, file=self.out)
