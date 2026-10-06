"""Dependency doctor: run every check in <root>/BAGIMLILIKLAR.md, print green/red.

Usage: python doktor.py [--iskelet] [root]   (root defaults to the current directory)
       --iskelet: only the built-in skeleton check; no bash, milliseconds (session-start hooks)
       --trust <root> / --untrust <root>: add / remove the project in <state>/trusted.txt; the
       session-start hook runs a project's kontrol commands in the background only if trusted.
       A manual `doktor.py <root>` run needs no trust (explicit user/agent action).

Registry format, one block per dependency:

    - <what> -> <depends on>
      kontrol: <bash command, exit 0 means healthy>
      bozuksa: <what to do when red>

Rules the parser enforces:
- A block opens only on a column-0 "- " line whose title contains " -> "; other bullets are prose.
- An indented line that is not a keyword continues the previous `kontrol:` / `bozuksa:` value.
- Fenced examples (``` or ~~~) are skipped.
- A block without `kontrol:` (or `kontrol: elle`) is listed as unchecked, never skipped silently.

Built-in check, no registry entry needed: when the root is a proje-baslat project (it has
CONSTANTS.md or notes.md) the doctor compares it with the skill's CURRENT skeleton: every
skeleton file/folder present, and CLAUDE.md pointing at the newer ones. Red means the project
was bootstrapped with an older template; the repair is the skill's retrofit mode. When the
skill's templates change, update SKELETON_FILES / SKELETON_DIRS / CLAUDE_POINTERS here too.

Exit code: 0 all green, 1 any red, 2 registry unreadable / empty or bash missing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REGISTRY_NAME = "BAGIMLILIKLAR.md"
CHECK_TIMEOUT_SECONDS = 30
KILL_DRAIN_SECONDS = 5
TITLE_ARROW = " -> "
FENCES = ("```", "~~~")
KEYWORDS = {"kontrol:": "check", "bozuksa:": "repair"}
MANUAL_VALUES = ("", "elle")
PROJECT_MARKERS = ("CONSTANTS.md", "notes.md")
SKELETON_FILES = (
    "notes.md",
    "GOALS.md",
    "BACKLOG.md",
    "DONE.md",
    "CONSTANTS.md",
    "docs/agents/issue-tracker.md",
)
SKELETON_DIRS = ("reports", "references")
CLAUDE_POINTERS = ("GOALS.md", "CONTEXT.md", "docs/adr/", "docs/agents/issue-tracker.md", "BAGIMLILIKLAR.md", "references/")
SKELETON_ONLY_FLAG = "--iskelet"
SKELETON_TITLE = "iskelet -> proje-baslat guncel sablonu"
RETROFIT_HINT = (
    "Claude'a soyle: proje-baslat skill'ini retrofit modunda calistir "
    "(eksik dosyalari ekler, CLAUDE.md'ye kopru bolum yazar, mevcutlara dokunmaz)"
)
WSL_LAUNCHER_DIRS = ("system32", "syswow64", "windowsapps")
GIT_BASH_FALLBACKS = (
    r"C:\Program Files\Git\usr\bin\bash.exe",
    r"C:\Program Files\Git\bin\bash.exe",
)


@dataclass(frozen=True)
class Dependency:
    title: str
    check: str
    repair: str


@dataclass(frozen=True)
class Outcome:
    dependency: Dependency
    healthy: bool
    detail: str


def parse_registry(text: str) -> tuple[Dependency, ...]:
    blocks: list[dict[str, str]] = []
    in_fence = False
    open_key = ""  # field of the current block that a continuation line extends
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith(FENCES):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if raw.startswith("- "):
            is_dependency = TITLE_ARROW in line
            if is_dependency:
                blocks.append({"title": line[2:].strip(), "check": "", "repair": ""})
            open_key = "" if is_dependency else "prose"
            continue
        if not line or not raw[0].isspace() or not blocks or open_key == "prose":
            open_key = "prose" if open_key == "prose" and line else ""
            continue
        keyword = next((k for k in KEYWORDS if line.startswith(k)), None)
        if keyword:
            open_key = KEYWORDS[keyword]
            blocks[-1][open_key] = line[len(keyword):].strip()
        elif open_key:
            blocks[-1][open_key] = f"{blocks[-1][open_key]} {line}".strip()
    return tuple(Dependency(**block) for block in blocks)


def kill_tree(process: subprocess.Popen[str]) -> None:
    # On Windows proc.kill() leaves grandchildren holding the pipe; taskkill /T must run
    # while bash is still alive, otherwise the orphans are reparented and unreachable.
    # Known limit: a process detached through an already-exited subshell, e.g. `(cmd &)`,
    # is outside the tree and lives on until it ends by itself. The doctor's own wall
    # clock stays bounded either way; keep background jobs out of `kontrol:` commands.
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            capture_output=True,
            check=False,
        )
    process.kill()


def run_check(
    dependency: Dependency,
    root: Path,
    bash: str,
    timeout_seconds: int = CHECK_TIMEOUT_SECONDS,
) -> Outcome:
    # Outside a Git Bash session (PowerShell, hooks) grep/ls/diff are not on PATH.
    env = {**os.environ, "PATH": str(Path(bash).parent) + os.pathsep + os.environ.get("PATH", "")}
    process = subprocess.Popen(
        [bash, "-c", dependency.check],
        cwd=root,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        output, _ = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        kill_tree(process)
        try:
            process.communicate(timeout=KILL_DRAIN_SECONDS)
        except subprocess.TimeoutExpired:
            pass
        return Outcome(dependency, False, f"timeout after {timeout_seconds}s")
    lines = output.strip().splitlines()
    detail = lines[-1] if lines else f"exit {process.returncode}"
    return Outcome(dependency, process.returncode == 0, detail)


def find_bash() -> str | None:
    # System32\bash.exe is the WSL launcher, not Git Bash: different filesystem view.
    found = shutil.which("bash")
    if found and not any(part in found.lower() for part in WSL_LAUNCHER_DIRS):
        return found
    return next((path for path in GIT_BASH_FALLBACKS if Path(path).is_file()), None)


def is_manual(dependency: Dependency) -> bool:
    return dependency.check.strip().lower() in MANUAL_VALUES


def skeleton_outcome(root: Path) -> Outcome | None:
    """Compare a proje-baslat project with the current skeleton; None when root is not one."""
    if not any((root / marker).is_file() for marker in PROJECT_MARKERS):
        return None
    missing = [name for name in (*SKELETON_FILES, REGISTRY_NAME, "CLAUDE.md") if not (root / name).is_file()]
    missing += [f"{name}/" for name in SKELETON_DIRS if not (root / name).is_dir()]
    unpointed: list[str] = []
    claude = root / "CLAUDE.md"
    if claude.is_file():
        try:
            text = claude.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            text = ""
        unpointed = [pointer for pointer in CLAUDE_POINTERS if pointer not in text]
    problems = []
    if missing:
        problems.append("eksik: " + ", ".join(missing))
    if unpointed:
        problems.append("CLAUDE.md isaret etmiyor: " + ", ".join(unpointed))
    dependency = Dependency(SKELETON_TITLE, "", RETROFIT_HINT)
    return Outcome(dependency, not problems, "; ".join(problems))


def has_bullets(text: str) -> bool:
    in_fence = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith(FENCES):
            in_fence = not in_fence
        elif not in_fence and line.startswith("- "):
            return True
    return False


def load_registry(registry: Path) -> tuple[Dependency, ...] | str:
    """Return the dependencies, or a one-line reason why the registry cannot be used.

    A registry with no list items at all is legitimately empty (fresh project). List items
    that parse to nothing mean a broken format, which must not look healthy.
    """
    try:
        text = registry.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as error:
        return f"{registry} okunamadi (UTF-8 olmali): {error}"
    dependencies = parse_registry(text)
    if not dependencies and has_bullets(text):
        return f"{registry} icinde bagimlilik bulunamadi. Bicim: '- <ne> -> <neye bagli>' satir basinda."
    return dependencies


def report(registry: Path, outcomes: tuple[Outcome, ...], manual: tuple[Dependency, ...], empty: bool) -> int:
    red = tuple(o for o in outcomes if not o.healthy)
    print(f"doktor: {registry}")
    if empty:
        print("  kayit bos: henuz bagimlilik yazilmamis (yeni projede normal)")
    for outcome in outcomes:
        mark = "YESIL  " if outcome.healthy else "KIRMIZI"
        print(f"  {mark} {outcome.dependency.title}")
        if not outcome.healthy:
            print(f"          neden:   {outcome.detail}")
            print(f"          bozuksa: {outcome.dependency.repair or '(yazilmamis)'}")
    for dependency in manual:
        print(f"  ELLE    {dependency.title}  (kontrol komutu yok, yalnizca belge)")
    print(f"ozet: {len(outcomes) - len(red)} yesil, {len(red)} kirmizi, {len(manual)} kontrolsuz")
    return 1 if red else 0

# --- guven listesi: hook yalnizca burada listeli projelerin kontrol komutlarini kosar ---
TRUSTED_NAME = "trusted.txt"
TRUST_FLAG = "--trust"
UNTRUST_FLAG = "--untrust"


def default_state() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".cache")
    return Path(base) / "proje-baslat-doktor"


def listed_paths(list_file: Path) -> set[str]:
    """Absolute paths, one per line, '#' comments; normcase-normalised (case-insensitive)."""
    try:
        lines = list_file.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError):
        return set()
    return {os.path.normcase(str(Path(line.strip()))) for line in lines if line.strip() and not line.strip().startswith("#")}


def is_listed(folder: Path, listed: set[str]) -> bool:
    """An entry covers itself and every folder below it."""
    return any(os.path.normcase(str(candidate)) in listed for candidate in (folder, *folder.parents))


def is_trusted(root: Path, state: Path) -> bool:
    return is_listed(root, listed_paths(state / TRUSTED_NAME))


def trust(root: Path, state: Path) -> str:
    """Append the root to trusted.txt (idempotent); returns a one-line report."""
    target = state / TRUSTED_NAME
    if os.path.normcase(str(root)) in listed_paths(target):
        return f"doktor: {root} zaten guvenli ({target})."
    state.mkdir(parents=True, exist_ok=True)
    existing = target.read_text(encoding="utf-8-sig") if target.is_file() else ""
    separator = "" if not existing or existing.endswith("\n") else "\n"
    target.write_text(f"{existing}{separator}{root}\n", encoding="utf-8")
    return f"doktor: {root} guvenli listeye eklendi ({target})."


def untrust(root: Path, state: Path) -> str:
    """Remove the root's own line from trusted.txt; comments and other entries stay."""
    target = state / TRUSTED_NAME
    if not target.is_file():
        return f"doktor: {root} listede degildi ({target} yok)."
    lines = target.read_text(encoding="utf-8-sig").splitlines()
    key = os.path.normcase(str(root))
    kept = [line for line in lines if line.strip().startswith("#") or os.path.normcase(str(Path(line.strip()))) != key or not line.strip()]
    if len(kept) == len(lines):
        return f"doktor: {root} listede degildi ({target})."
    target.write_text("".join(f"{line}\n" for line in kept), encoding="utf-8")
    return f"doktor: {root} guvenli listeden cikarildi ({target})."


def main(argv: list[str], state: Path | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    args = argv[1:]
    for flag, action in ((TRUST_FLAG, trust), (UNTRUST_FLAG, untrust)):
        if flag in args:
            targets = [a for a in args if a != flag]
            if len(targets) != 1:
                print(f"doktor: kullanim: doktor.py {flag} <proje-koku>")
                return 2
            print(action(Path(targets[0]).expanduser().resolve(), state or default_state()))
            return 0
    skeleton_only = SKELETON_ONLY_FLAG in args
    args = [a for a in args if a != SKELETON_ONLY_FLAG]
    root = Path(args[0]).expanduser().resolve() if args else Path.cwd()
    registry = root / REGISTRY_NAME
    skeleton = skeleton_outcome(root)
    if skeleton_only:
        # Fast path for session-start hooks: no bash, no registry commands.
        if skeleton is None:
            print(f"doktor: {root} proje-baslat projesi degil (CONSTANTS.md / notes.md yok).")
            return 2
        return report(registry, (skeleton,), (), empty=False)
    if not registry.is_file() and skeleton is None:
        print(f"doktor: {registry} yok. Kayit olmadan kontrol edilecek bir sey yok.")
        return 2
    loaded = load_registry(registry) if registry.is_file() else ()
    if isinstance(loaded, str):
        print(f"doktor: {loaded}")
        return 2
    runnable = tuple(d for d in loaded if not is_manual(d))
    bash = find_bash() if runnable else ""
    if bash is None:
        print("doktor: bash bulunamadi (Windows'ta Git Bash gerekir).")
        return 2
    checked = tuple(run_check(d, root, bash) for d in runnable)
    outcomes = ((skeleton,) if skeleton else ()) + checked
    manual = tuple(d for d in loaded if is_manual(d))
    return report(registry, outcomes, manual, empty=registry.is_file() and not loaded)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
