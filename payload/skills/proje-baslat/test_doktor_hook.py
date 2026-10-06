"""Tests for doktor_hook.py. Run: python -B -m unittest test_doktor_hook -v (from this folder)."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path

import doktor
import doktor_hook
from test_doktor import make_project

NL = chr(10)
tempfile.tempdir = os.path.realpath(tempfile.gettempdir())  # TMP may be an 8.3 short path; find_root resolves


class FindRootTest(unittest.TestCase):
    def test_finds_project_from_subfolder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            root = home / "dev" / "app"
            (root / "src" / "deep").mkdir(parents=True)
            (root / "CONSTANTS.md").write_text("x", encoding="utf-8")
            self.assertEqual(doktor_hook.find_root(root / "src" / "deep", home), root)

    def test_stops_at_home_and_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "notes.md").write_text("x", encoding="utf-8")
            (home / "dev").mkdir()
            self.assertIsNone(doktor_hook.find_root(home / "dev", home))

    def test_vault_is_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            vault = home / "vault"
            inner = vault / "proj"
            inner.mkdir(parents=True)
            (vault / ".beyin-runtime.json").write_text("{}", encoding="utf-8")
            (inner / "notes.md").write_text("x", encoding="utf-8")
            self.assertIsNone(doktor_hook.find_root(inner, home))

    def test_ignored_project_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            root = home / "dev" / "client"
            (root / "sub").mkdir(parents=True)
            (root / "notes.md").write_text("x", encoding="utf-8")
            ignore = home / "ignore.txt"
            ignore.write_text("# yorum" + NL + str(root).upper() + NL, encoding="utf-8")
            self.assertIsNone(doktor_hook.find_root(root / "sub", home, ignore_file=ignore))
            self.assertEqual(doktor_hook.find_root(root / "sub", home, ignore_file=home / "missing.txt"), root)

    def test_ignore_entry_covers_descendant_projects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            runs = home / "dev" / "factory" / "factory-runs"
            worktree = runs / "ticket-1"
            worktree.mkdir(parents=True)
            (worktree / "notes.md").write_text("x", encoding="utf-8")
            sibling = home / "dev" / "factory-runs-other"
            sibling.mkdir(parents=True)
            (sibling / "notes.md").write_text("x", encoding="utf-8")
            ignore = home / "ignore.txt"
            ignore.write_text(str(runs) + NL, encoding="utf-8")
            self.assertIsNone(doktor_hook.find_root(worktree, home, ignore_file=ignore))
            self.assertEqual(doktor_hook.find_root(sibling, home, ignore_file=ignore), sibling)


class CacheTest(unittest.TestCase):
    def test_refresh_writes_exit_and_red_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, state = Path(tmp) / "p", Path(tmp) / "s"
            root.mkdir()
            make_project(root)
            (root / doktor.REGISTRY_NAME).write_text(
                "- bad -> thing\n  kontrol: false\n  bozuksa: fix it\n", encoding="utf-8")
            doktor_hook.refresh(root, state)
            cache = doktor_hook.read_cache(doktor_hook.cache_path(state, root))
        self.assertEqual(cache["exit"], 1)
        self.assertEqual(cache["root"], str(root))
        self.assertTrue(any("bad -> thing" in line for line in cache["reds"]))
        self.assertFalse(any("iskelet" in line for line in cache["reds"]))

    def test_red_first_run_is_retried_once(self) -> None:
        calls: list[int] = []
        results = [(1, "  KIRMIZI slow -> thing" + NL + "          neden:   timeout after 30s" + NL), (0, "ozet: 1 yesil" + NL)]

        def runner(root: Path) -> tuple[int, str]:
            calls.append(1)
            return results[len(calls) - 1]

        with tempfile.TemporaryDirectory() as tmp:
            root, state = Path(tmp) / "p", Path(tmp) / "s"
            root.mkdir()
            doktor_hook.refresh(root, state, runner=runner)
            cache = doktor_hook.read_cache(doktor_hook.cache_path(state, root))
        self.assertEqual(len(calls), 2)
        self.assertEqual(cache["exit"], 0)
        self.assertEqual(cache["reds"], [])

    def test_green_first_run_is_not_retried(self) -> None:
        calls: list[int] = []

        def runner(root: Path) -> tuple[int, str]:
            calls.append(1)
            return 0, "ozet: 1 yesil" + NL

        with tempfile.TemporaryDirectory() as tmp:
            root, state = Path(tmp) / "p", Path(tmp) / "s"
            root.mkdir()
            doktor_hook.refresh(root, state, runner=runner)
        self.assertEqual(len(calls), 1)

    def test_corrupt_cache_reads_as_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "c.json"
            path.write_text("{not json", encoding="utf-8")
            self.assertIsNone(doktor_hook.read_cache(path))

    def test_needs_refresh(self) -> None:
        self.assertTrue(doktor_hook.needs_refresh(None, 1000.0))
        self.assertTrue(doktor_hook.needs_refresh({"at": 0.0}, doktor_hook.REFRESH_AFTER_SECONDS + 1))
        self.assertFalse(doktor_hook.needs_refresh({"at": 1000.0}, 1001.0))


class MessageTest(unittest.TestCase):
    def test_all_green_gives_empty_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_project(root)
            skeleton = doktor.skeleton_outcome(root)
            msg = doktor_hook.build_message(root, skeleton, {"at": 0, "exit": 0, "reds": []}, now=10.0)
        self.assertEqual(msg, "")

    def test_red_skeleton_mentions_retrofit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notes.md").write_text("x", encoding="utf-8")
            skeleton = doktor.skeleton_outcome(root)
            msg = doktor_hook.build_message(root, skeleton, None, now=10.0)
        self.assertIn("iskelet", msg)
        self.assertIn("retrofit", msg)

    def test_cached_red_is_reported_with_age(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_project(root)
            skeleton = doktor.skeleton_outcome(root)
            cache = {"at": 0.0, "exit": 1, "reds": ["KIRMIZI bad -> thing", "neden: exit 1"]}
            msg = doktor_hook.build_message(root, skeleton, cache, now=7200.0)
        self.assertIn("bad -> thing", msg)
        self.assertIn("120 dk", msg)


class MainTest(unittest.TestCase):
    def run_hook(self, payload: dict, home: Path, state: Path) -> str:
        out = io.StringIO()
        doktor_hook.hook(io.StringIO(json.dumps(payload)), out, home=home, state=state, spawn=lambda root: None)
        return out.getvalue()

    def test_non_project_prints_empty_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "x").mkdir()
            out = self.run_hook({"hook_event_name": "SessionStart", "cwd": str(home / "x")}, home, home / "s")
        self.assertEqual(json.loads(out), {})

    def test_red_project_injects_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            root = home / "p"
            root.mkdir()
            (root / "notes.md").write_text("x", encoding="utf-8")
            out = json.loads(self.run_hook({"hook_event_name": "SessionStart", "cwd": str(root)}, home, home / "s"))
        text = out["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn("iskelet", text)

    def test_spawns_refresh_when_cache_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            root = home / "p"
            root.mkdir()
            make_project(root)
            spawned: list[Path] = []
            (home / "s").mkdir()
            (home / "s" / doktor_hook.TRUSTED_NAME).write_text(str(root) + NL, encoding="utf-8")
            doktor_hook.hook(io.StringIO(json.dumps({"hook_event_name": "SessionStart", "cwd": str(root)})),
                             io.StringIO(), home=home, state=home / "s", spawn=spawned.append)
        self.assertEqual(spawned, [root])

    def test_garbage_payload_never_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            doktor_hook.hook(io.StringIO("not json"), out, home=Path(tmp), state=Path(tmp) / "s", spawn=lambda r: None)
        self.assertEqual(json.loads(out.getvalue()), {})


class TrustTest(unittest.TestCase):
    """Hook runs the full registry only for trusted roots; untrusted ones get a hint."""

    def project(self, home: Path, entries: bool = True) -> Path:
        root = home / "dev" / "p"
        root.mkdir(parents=True)
        make_project(root)
        if entries:
            (root / doktor.REGISTRY_NAME).write_text("- a -> b\n  kontrol: echo hi\n  bozuksa: fix\n", encoding="utf-8")
        return root

    def run_hook(self, root: Path, home: Path, state: Path) -> tuple[dict, list[Path]]:
        spawned: list[Path] = []
        out = io.StringIO()
        payload = json.dumps({"hook_event_name": "SessionStart", "cwd": str(root)})
        doktor_hook.hook(io.StringIO(payload), out, home=home, state=state, spawn=spawned.append)
        return json.loads(out.getvalue()), spawned

    def test_untrusted_root_does_not_spawn_and_shows_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            root = self.project(home)
            out, spawned = self.run_hook(root, home, home / "s")
        self.assertEqual(spawned, [])
        text = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("--trust", text)
        self.assertIn(str(root.resolve()), text)

    def test_untrusted_root_ignores_cached_reds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            root = self.project(home)
            state = home / "s"
            doktor_hook._atomic_write(doktor_hook.cache_path(state, root), {
                "root": str(root), "at": 9e12, "exit": 1, "reds": ["KIRMIZI EVIL-CACHE -> x"]})
            out, spawned = self.run_hook(root, home, state)
        self.assertEqual(spawned, [])
        self.assertNotIn("EVIL-CACHE", json.dumps(out))

    def test_untrusted_root_without_entries_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            root = self.project(home, entries=False)
            out, spawned = self.run_hook(root, home, home / "s")
        self.assertEqual(spawned, [])
        self.assertEqual(out, {})

    def test_trusted_root_spawns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            root = self.project(home)
            state = home / "s"
            state.mkdir()
            (state / doktor_hook.TRUSTED_NAME).write_text("# x" + NL + str(root).upper() + NL, encoding="utf-8")
            out, spawned = self.run_hook(root, home, state)
        self.assertEqual(spawned, [root])
        self.assertEqual(out, {})

    def test_trusted_parent_covers_child(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            root = self.project(home)
            state = home / "s"
            state.mkdir()
            (state / doktor_hook.TRUSTED_NAME).write_text(str(root.parent) + NL, encoding="utf-8")
            _, spawned = self.run_hook(root, home, state)
        self.assertEqual(spawned, [root])

    def test_refresh_mode_refuses_untrusted_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, state = Path(tmp) / "p", Path(tmp) / "s"
            root.mkdir()
            ran: list[int] = []
            doktor_hook.refresh_if_trusted(root, state, runner=lambda r: (ran.append(1), (0, ""))[1])
        self.assertEqual(ran, [])

    def test_refresh_mode_runs_trusted_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, state = Path(tmp) / "p", Path(tmp) / "s"
            root.mkdir()
            state.mkdir()
            (state / doktor_hook.TRUSTED_NAME).write_text(str(root) + NL, encoding="utf-8")
            ran: list[int] = []
            doktor_hook.refresh_if_trusted(root, state, runner=lambda r: (ran.append(1), (0, ""))[1])
        self.assertEqual(ran, [1])


if __name__ == "__main__":
    unittest.main()
