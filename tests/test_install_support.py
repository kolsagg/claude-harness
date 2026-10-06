"""install testleri için ortak yardımcılar (sahte HOME, sahte runner)."""
import io
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from lib.installer.cli import main
from lib.installer.model import Deps

FIXTURES = Path(__file__).resolve().parent / "fixtures"
BASE = ["--name", "Ada", "--language", "Turkish", "--github-owner", "ada", "--yes"]
NO_ALL = ["--no-vault", "--no-orca", "--no-codex"]


class FakeRunner:
    def __init__(self, fail=()):
        self.calls = []
        self.fail = tuple(fail)

    def __call__(self, argv, cwd=None):
        self.calls.append(list(argv))
        joined = " ".join(argv)
        if any(f in joined for f in self.fail):
            return 1, "boom"
        return 0, "done"


def run_install(home, extra=None, runner=None, which=None, tty=False, now=None, answers=None,
                real_home=None, ask=None):
    out = io.StringIO()
    deps = Deps(
        real_home=real_home or home,
        runner=runner or FakeRunner(),
        which=which or (lambda name: f"/bin/{name}"),
        now=lambda: now or datetime(2026, 10, 6, 12, 0, 0),
        isatty=lambda: tty,
        ask=ask or (lambda prompt="": (_ for _ in ()).throw(EOFError())),
        out=out,
        windows=False,
    )
    args = list(BASE if answers is None else answers) + list(extra or [])
    code = main(args, repo_root=FIXTURES, deps=deps)
    return code, out.getvalue()


class HomeCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name).resolve()
        self.claude = self.home / ".claude"

    def install(self, *extra, **kw):
        flags = [] if any(f in extra for f in ("--vault", "--no-vault")) else ["--no-vault"]
        for name in ("orca", "codex"):
            if f"--{name}" not in extra and f"--no-{name}" not in extra:
                flags.append(f"--no-{name}")
        return run_install(self.home, ["--home", str(self.home), "--skip-external", *flags, *extra], **kw)

    def state(self):
        return json.loads((self.claude / ".claude-harness.json").read_text(encoding="utf-8"))

    def tree(self):
        return sorted(
            p.relative_to(self.claude).as_posix()
            for p in self.claude.rglob("*")
            if p.is_file() and "backups" not in p.parts
        )
