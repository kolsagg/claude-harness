"""SessionStart hook for the proje-baslat doctor. Never blocks, never raises.

The full doctor runs every `kontrol:` command and can take tens of seconds, too slow for
a session start. So the hook does two cheap things and one detached thing:

1. Built-in skeleton check (milliseconds, no bash), always fresh.
2. Reads the cached result of the last full doctor run for this project.
3. If that cache is missing or old, starts a detached full run that refreshes it.
   The current session sees the previous result; the next session sees the new one.

Context is injected only when something is red. Green projects cost nothing.
Projects are found by walking up from the session cwd to the first folder with
CONSTANTS.md or notes.md, never at or above the home folder, never inside a folder
tree that holds `.beyin-runtime.json` (the second-brain vault has its own system),
never for a project at or below a path listed in `<state>/ignore.txt` (one absolute path per line).

Trust: the full run executes the project's `kontrol:` shell commands, so the hook starts it
ONLY for a root at or below a path in `<state>/trusted.txt` (same format as ignore.txt; added
with `doktor.py --trust <root>`). An untrusted root still gets the skeleton check, plus one
hint line when it has a BAGIMLILIKLAR.md with entries; its cache is never read or shown.

Usage:
    hook:     python -B doktor_hook.py            (JSON payload on stdin)
    refresh:  python -B doktor_hook.py --refresh <root>
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, TextIO

sys.dont_write_bytecode = True  # the skill folder is backed up into the vault

import doktor  # noqa: E402  (after dont_write_bytecode on purpose)

REFRESH_AFTER_SECONDS = 30 * 60
RUNNING_STALE_SECONDS = 10 * 60
MAX_WALK_DEPTH = 8
MAX_PAYLOAD_CHARS = 1_000_000
VAULT_MARKER = ".beyin-runtime.json"
REFRESH_FLAG = "--refresh"
IGNORE_NAME = "ignore.txt"  # in the state folder: projects the hook must not flag
TRUSTED_NAME = doktor.TRUSTED_NAME  # in the state folder: projects whose kontrol commands may auto-run


default_state = doktor.default_state
ignored_roots = doktor.listed_paths  # same file format for ignore.txt and trusted.txt


def is_ignored(folder: Path, ignored: set[str]) -> bool:
    """An entry covers itself and every folder below it (e.g. all factory-run worktrees)."""
    return doktor.is_listed(folder, ignored)


def find_root(cwd: Path, home: Path, ignore_file: Path | None = None) -> Path | None:
    """First folder from cwd upward with a project marker, strictly below home.

    Projects listed in the ignore file (client repos, archived work) are never flagged;
    nothing is written inside those repos.
    """
    home = home.resolve()
    current = cwd.resolve()
    if any((folder / VAULT_MARKER).exists() for folder in (current, *current.parents)):
        return None
    for folder in [current, *current.parents][:MAX_WALK_DEPTH]:
        if folder == home or home not in folder.parents:
            return None
        if any((folder / marker).is_file() for marker in doktor.PROJECT_MARKERS):
            if ignore_file is not None and is_ignored(folder, ignored_roots(ignore_file)):
                return None
            return folder
    return None


def cache_path(state: Path, root: Path) -> Path:
    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:16]
    return state / f"{digest}.json"


def read_cache(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(value, dict) or not isinstance(value.get("at"), (int, float)):
        return None
    return value


def needs_refresh(cache: dict | None, now: float) -> bool:
    return cache is None or now - cache["at"] > REFRESH_AFTER_SECONDS


def _atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, path)


def red_lines(report_text: str) -> list[str]:
    """KIRMIZI rows and their reason lines, excluding the skeleton row (checked live)."""
    lines: list[str] = []
    keep = False
    for raw in report_text.splitlines():
        line = raw.strip()
        if line.startswith("KIRMIZI"):
            keep = doktor.SKELETON_TITLE not in line
            if keep:
                lines.append(line)
        elif keep and line.startswith("neden:"):
            lines.append(line)
        elif not line.startswith("bozuksa:"):
            keep = False
    return lines


def run_doctor(root: Path) -> tuple[int, str]:
    buffer = io.StringIO()
    buffer.reconfigure = lambda **_: None  # doktor.main reconfigures stdout
    with contextlib.redirect_stdout(buffer):
        code = doktor.main(["doktor.py", str(root)])
    return code, buffer.getvalue()


def refresh(root: Path, state: Path, runner: Callable[[Path], tuple[int, str]] = run_doctor) -> None:
    """Full doctor run; stores exit code and red rows. Runs detached from the hook.

    A red first run is repeated once: cold tool caches (npx, vitest) can push a healthy
    check past its timeout, and a false red teaches the reader to ignore the doctor.
    """
    code, text = runner(root)
    if code == 1:
        code, text = runner(root)
    reds = red_lines(text)
    if code == 2:
        reds = [line.strip() for line in text.splitlines() if line.strip()][:3]
    _atomic_write(cache_path(state, root), {"root": str(root), "at": time.time(), "exit": code, "reds": reds})


def refresh_if_trusted(root: Path, state: Path, runner: Callable[[Path], tuple[int, str]] = run_doctor) -> None:
    """Second gate for the detached `--refresh` entry point: never run commands of an untrusted root."""
    if doktor.is_trusted(root, state):
        refresh(root, state, runner=runner)


def spawn_refresh(root: Path, state: Path) -> None:
    marker = cache_path(state, root).with_suffix(".running")
    try:
        if time.time() - marker.stat().st_mtime < RUNNING_STALE_SECONDS:
            return
    except OSError:
        pass
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(str(time.time()), encoding="utf-8")
    command = [sys.executable, "-B", str(Path(__file__).resolve()), REFRESH_FLAG, str(root)]
    options = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
    if os.name != "nt":
        subprocess.Popen(command, start_new_session=True, **options)
        return
    # CREATE_NO_WINDOW gives the child a hidden console that bash/node inherit, so no
    # window flashes (DETACHED_PROCESS would make each console child open its own).
    # Breakaway keeps the refresh alive if the host kills the hook's job; not every
    # job allows it, so fall back to a plain child.
    base = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        subprocess.Popen(command, creationflags=base | subprocess.CREATE_BREAKAWAY_FROM_JOB, **options)
    except OSError:
        subprocess.Popen(command, creationflags=base, **options)


def build_message(root: Path, skeleton: doktor.Outcome | None, cache: dict | None, now: float) -> str:
    parts: list[str] = []
    if skeleton is not None and not skeleton.healthy:
        parts.append(f"- iskelet eski sablonda ({skeleton.detail}). Onarim: proje-baslat retrofit modu.")
    if cache and cache.get("exit") in (1, 2) and cache.get("reds"):
        age = int((now - cache["at"]) // 60)
        parts.append(f"- son tam doktor kosumu ({age} dk once):")
        parts.extend(f"  {line}" for line in cache["reds"])
    if not parts:
        return ""
    header = (f"proje-baslat doktoru {root.name} icin KIRMIZI verdi "
              "(BAGIMLILIKLAR.md kurali: bozuksa satirini uygula, kontrolu yesile boyamak icin degistirme).")
    footer = "Tam rapor: python ~/.claude/skills/proje-baslat/doktor.py ."
    return "\n".join([header, *parts, footer])


def untrusted_hint(root: Path) -> str:
    """One line when an untrusted project has registry entries that were NOT auto-run."""
    loaded = doktor.load_registry(root / doktor.REGISTRY_NAME) if (root / doktor.REGISTRY_NAME).is_file() else ()
    if isinstance(loaded, str) or not loaded:
        return ""
    return (f"proje-baslat: {root.name} icin BAGIMLILIKLAR.md otomatik kosulmadi, proje guvenli listede degil. "
            f"Kullanici bu repoya guvendigini onaylarsa: python ~/.claude/skills/proje-baslat/doktor.py --trust {root}")


def hook(
    stdin: TextIO,
    stdout: TextIO,
    home: Path | None = None,
    state: Path | None = None,
    spawn: Callable[[Path], None] | None = None,
) -> None:
    home = home or Path.home()
    state = state or default_state()
    try:
        payload = json.loads(stdin.read(MAX_PAYLOAD_CHARS) or "{}")
        cwd = payload.get("cwd") if isinstance(payload, dict) else None
        if payload.get("hook_event_name") != "SessionStart" or not isinstance(cwd, str) or not cwd:
            raise ValueError("not a session start")
        root = find_root(Path(cwd), home, ignore_file=state / IGNORE_NAME)
        if root is None:
            raise ValueError("not a proje-baslat project")
        now = time.time()
        skeleton = doktor.skeleton_outcome(root)
        if doktor.is_trusted(root, state):
            cache = read_cache(cache_path(state, root))
            if cache is not None and cache.get("root") != str(root):
                cache = None
            if needs_refresh(cache, now):
                try:
                    (spawn or (lambda r: spawn_refresh(r, state)))(root)
                except OSError:
                    pass
            message = build_message(root, skeleton, cache, now)
        else:
            # never spawn, never read a cache for a root nobody trusted
            skeleton_part = build_message(root, skeleton, None, now)
            message = "\n".join(part for part in (skeleton_part, untrusted_hint(root)) if part)
    except Exception:  # a doctor problem must never break or delay session start
        message = ""
    if message:
        stdout.write(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": message}}))
    else:
        stdout.write("{}")


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == REFRESH_FLAG:
        root = Path(argv[2]).resolve()
        state = default_state()
        try:
            refresh_if_trusted(root, state)
        finally:
            with contextlib.suppress(OSError):
                cache_path(state, root).with_suffix(".running").unlink()
        return 0
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    hook(sys.stdin, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
