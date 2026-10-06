"""Tests for doktor.py. Run: python -m unittest test_doktor -v (from this folder)."""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import doktor

REGISTRY = """# Bagimliliklar

Prose line.

```
- example inside fence -> must be ignored
  kontrol: false
```

## Kayit

- green -> always
  kontrol: test -f BAGIMLILIKLAR.md
  bozuksa: never
- red -> missing file
  kontrol: grep -q x missing-file.txt
  bozuksa: restore it
- manual -> no command
  bozuksa: look by eye
- explicit manual -> elle
  kontrol: elle
"""


def run_main(root: Path) -> tuple[int, str]:
    buffer = io.StringIO()
    buffer.reconfigure = lambda **_: None  # main() reconfigures the real stdout
    with contextlib.redirect_stdout(buffer):
        code = doktor.main(["doktor.py", str(root)])
    return code, buffer.getvalue()


class ParseRegistryTest(unittest.TestCase):
    def test_skips_fenced_example_and_keeps_order(self) -> None:
        titles = [d.title for d in doktor.parse_registry(REGISTRY)]
        self.assertEqual(
            titles,
            ["green -> always", "red -> missing file", "manual -> no command", "explicit manual -> elle"],
        )

    def test_reads_check_and_repair(self) -> None:
        red = doktor.parse_registry(REGISTRY)[1]
        self.assertEqual(red.check, "grep -q x missing-file.txt")
        self.assertEqual(red.repair, "restore it")

    def test_crlf_input_parses_the_same(self) -> None:
        crlf = REGISTRY.replace("\n", "\r\n")
        self.assertEqual(doktor.parse_registry(crlf), doktor.parse_registry(REGISTRY))

    def test_manual_detection(self) -> None:
        deps = doktor.parse_registry(REGISTRY)
        self.assertEqual([doktor.is_manual(d) for d in deps], [False, False, True, True])

    def test_empty_registry_has_no_dependencies(self) -> None:
        self.assertEqual(doktor.parse_registry("# Bagimliliklar\n\n## Kayit\n"), ())


class ReviewRegressionTest(unittest.TestCase):
    """Findings from the 2026-09-20 Opus review; each one was a reproduced failure."""

    def test_wrapped_check_line_is_joined_not_truncated(self) -> None:
        text = "- wrapped -> x\n  kontrol: test -f var.txt\n    && test -f yok.txt\n  bozuksa: fix\n    it\n"
        dep = doktor.parse_registry(text)[0]
        self.assertEqual(dep.check, "test -f var.txt && test -f yok.txt")
        self.assertEqual(dep.repair, "fix it")

    def test_prose_bullets_are_not_dependencies(self) -> None:
        text = "- just a note\n- another note\n\n## Kayit\n\n- real -> thing\n  kontrol: true\n"
        self.assertEqual([d.title for d in doktor.parse_registry(text)], ["real -> thing"])

    def test_tilde_fence_is_skipped(self) -> None:
        text = "~~~\n- fenced -> example\n  kontrol: false\n~~~\n- real -> thing\n  kontrol: true\n"
        self.assertEqual([d.title for d in doktor.parse_registry(text)], ["real -> thing"])

    def test_manual_keyword_is_case_insensitive(self) -> None:
        dep = doktor.parse_registry("- a -> b\n  kontrol: Elle\n")[0]
        self.assertTrue(doktor.is_manual(dep))

    def test_bom_does_not_drop_first_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / doktor.REGISTRY_NAME).write_text("- first -> x\n  kontrol: true\n", encoding="utf-8-sig")
            code, out = run_main(root)
        self.assertEqual(code, 0)
        self.assertIn("YESIL   first -> x", out)

    def test_registry_without_any_dependency_is_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / doktor.REGISTRY_NAME).write_text("# Bagimliliklar\n\n  - indented -> x\n", encoding="utf-8")
            code, out = run_main(root)
        self.assertEqual(code, 2)
        self.assertIn("bagimlilik bulunamadi", out)

    def test_non_utf8_registry_is_exit_2_not_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / doktor.REGISTRY_NAME).write_bytes("- gerçek -> bağımlılık\n".encode("cp1254"))
            code, out = run_main(root)
        self.assertEqual(code, 2)
        self.assertIn("okunamadi", out)

    def test_timeout_bounds_wall_clock_even_with_grandchild(self) -> None:
        import time

        dep = doktor.Dependency("slow -> x", "(sleep 20 &) ; sleep 20", "")
        started = time.monotonic()
        outcome = doktor.run_check(dep, Path.cwd(), doktor.find_bash(), timeout_seconds=2)
        self.assertFalse(outcome.healthy)
        self.assertIn("timeout", outcome.detail)
        self.assertLess(time.monotonic() - started, 10)


def make_project(root: Path, skip: tuple[str, ...] = (), claude_text: str | None = None) -> None:
    for name in doktor.SKELETON_FILES:
        if name not in skip:
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text("x\n", encoding="utf-8")
    for name in doktor.SKELETON_DIRS:
        if name not in skip:
            (root / name).mkdir()
    pointers = " ".join(doktor.CLAUDE_POINTERS) if claude_text is None else claude_text
    (root / "CLAUDE.md").write_text(pointers, encoding="utf-8")
    (root / doktor.REGISTRY_NAME).write_text("# Bagimliliklar\n\n## Kayit\n", encoding="utf-8")


class SkeletonTest(unittest.TestCase):
    def test_complete_project_with_empty_registry_is_green(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_project(root)
            code, out = run_main(root)
        self.assertEqual(code, 0)
        self.assertIn("YESIL   iskelet", out)
        self.assertIn("kayit bos", out)

    def test_missing_skeleton_files_are_red_with_retrofit_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_project(root, skip=("GOALS.md", "references"))
            code, out = run_main(root)
        self.assertEqual(code, 1)
        self.assertIn("KIRMIZI iskelet", out)
        self.assertIn("GOALS.md", out)
        self.assertIn("references/", out)
        self.assertIn("retrofit", out)

    def test_claude_md_without_pointers_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_project(root, claude_text="# Site\nnotes.md CONSTANTS.md TODO.md\n")
            code, out = run_main(root)
        self.assertEqual(code, 1)
        self.assertIn("CLAUDE.md isaret etmiyor", out)
        self.assertIn("BAGIMLILIKLAR.md", out)

    def test_old_project_without_registry_reports_skeleton_not_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CONSTANTS.md").write_text("x\n", encoding="utf-8")
            (root / "CLAUDE.md").write_text("old\n", encoding="utf-8")
            code, out = run_main(root)
        self.assertEqual(code, 1)
        self.assertIn("KIRMIZI iskelet", out)
        self.assertIn(doktor.REGISTRY_NAME, out)

    def test_non_project_root_skips_skeleton_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CLAUDE.md").write_text("harness\n", encoding="utf-8")
            (root / doktor.REGISTRY_NAME).write_text("- ok -> x\n  kontrol: true\n", encoding="utf-8")
            code, out = run_main(root)
        self.assertEqual(code, 0)
        self.assertNotIn("iskelet", out)

    def test_bullets_that_parse_to_nothing_are_still_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_project(root)
            (root / doktor.REGISTRY_NAME).write_text("## Kayit\n\n  - indented -> x\n    kontrol: true\n", encoding="utf-8")
            code, out = run_main(root)
        self.assertEqual(code, 2)
        self.assertIn("bagimlilik bulunamadi", out)


class MainTest(unittest.TestCase):
    def test_red_row_gives_exit_1_with_repair_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / doktor.REGISTRY_NAME).write_text(REGISTRY, encoding="utf-8")
            code, out = run_main(root)
        self.assertEqual(code, 1)
        self.assertIn("YESIL   green -> always", out)
        self.assertIn("KIRMIZI red -> missing file", out)
        self.assertIn("bozuksa: restore it", out)
        self.assertIn("ozet: 1 yesil, 1 kirmizi, 2 kontrolsuz", out)

    def test_all_green_gives_exit_0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / doktor.REGISTRY_NAME).write_text("- ok -> x\n  kontrol: true\n", encoding="utf-8")
            code, _ = run_main(root)
        self.assertEqual(code, 0)

    def test_missing_registry_gives_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, out = run_main(Path(tmp))
        self.assertEqual(code, 2)
        self.assertIn("yok", out)


class SkeletonOnlyFlagTest(unittest.TestCase):
    def run_flag(self, root: Path) -> tuple[int, str]:
        buffer = io.StringIO()
        buffer.reconfigure = lambda **_: None
        with contextlib.redirect_stdout(buffer):
            code = doktor.main(["doktor.py", "--iskelet", str(root)])
        return code, buffer.getvalue()

    def test_flag_skips_registry_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_project(root)
            (root / doktor.REGISTRY_NAME).write_text(REGISTRY, encoding="utf-8")
            code, out = self.run_flag(root)
        self.assertEqual(code, 0)
        self.assertIn("YESIL   iskelet", out)
        self.assertNotIn("red -> missing file", out)

    def test_flag_reports_red_skeleton(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notes.md").write_text("# n", encoding="utf-8")
            code, out = self.run_flag(root)
        self.assertEqual(code, 1)
        self.assertIn("KIRMIZI iskelet", out)

    def test_flag_on_non_project_is_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self.run_flag(Path(tmp))
        self.assertEqual(code, 2)
        self.assertIn("proje-baslat projesi degil", out)


class TrustCommandTest(unittest.TestCase):
    def run_main(self, args: list[str], state: Path) -> tuple[int, str]:
        buffer = io.StringIO()
        buffer.reconfigure = lambda **_: None
        with contextlib.redirect_stdout(buffer):
            code = doktor.main(["doktor.py", *args], state=state)
        return code, buffer.getvalue()

    def test_trust_appends_resolved_root_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, state = Path(tmp) / "p", Path(tmp) / "new" / "s"
            root.mkdir()
            code, out = self.run_main(["--trust", str(root)], state)
            self.assertEqual(code, 0)
            self.assertIn(str(root.resolve()), out)
            self.run_main(["--trust", str(root)], state)
            lines = (state / doktor.TRUSTED_NAME).read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines.count(str(root.resolve())), 1)

    def test_untrust_removes_only_that_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a, b, state = Path(tmp) / "a", Path(tmp) / "b", Path(tmp) / "s"
            a.mkdir()
            b.mkdir()
            self.run_main(["--trust", str(a)], state)
            self.run_main(["--trust", str(b)], state)
            code, _ = self.run_main(["--untrust", str(a)], state)
            text = (state / doktor.TRUSTED_NAME).read_text(encoding="utf-8")
        self.assertEqual(code, 0)
        self.assertNotIn(str(a.resolve()), text)
        self.assertIn(str(b.resolve()), text)

    def test_manual_run_needs_no_trust(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "p"
            root.mkdir()
            make_project(root)
            (root / doktor.REGISTRY_NAME).write_text("- a -> b\n  kontrol: true\n  bozuksa: x\n", encoding="utf-8")
            code, out = self.run_main([str(root)], Path(tmp) / "s")
        self.assertEqual(code, 0)
        self.assertNotIn("trust", out.lower())


if __name__ == "__main__":
    unittest.main()
