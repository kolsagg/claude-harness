"""Yasaklı kelime kuralı, yerel exclude birleşimi ve ağaç (--tree) taraması."""
import json
import subprocess
import unittest

from lib.exporter.build import build_payload
from lib.exporter.config import LocalConfig, load_local_config
from lib.exporter.pipeline import run_export
from lib.exporter.scrub import scrub_files
from tests.export_support import HARNESS, PAIRS, ExportCase


def hits(text, *forbidden):
    cfg = LocalConfig(forbidden=tuple(forbidden))
    return [f for f in scrub_files({"x.md": text.encode("utf-8")}, cfg) if f.rule == "forbidden"]


class ForbiddenWordRuleTest(unittest.TestCase):
    def test_capitalized_entry_is_whole_word_and_case_sensitive(self):
        self.assertEqual(len(hits("the Zork product", "Zork")), 1)
        self.assertEqual(hits("zork hello; ZORK; zorks; Zorks", "Zork"), [])
        self.assertEqual(hits("makes quux, Quuxes, nonquux", "Quux"), [])

    def test_lowercase_entry_is_substring_and_case_insensitive(self):
        self.assertEqual(len(hits("xAdAx and ADA", "ada")), 2)

    def test_binary_follows_same_rule(self):
        cfg = LocalConfig(forbidden=("Zork", "ada"))
        self.assertEqual(scrub_files({"a.bin": b"\x00 zork \x00"}, cfg), [])
        found = scrub_files({"a.bin": b"\x00 Zork \x00"}, cfg)
        self.assertEqual([f.rule for f in found], ["forbidden-binary"])
        self.assertEqual(len(scrub_files({"b.bin": b"\x00 xADAx \x00"}, cfg)), 1)


class LocalExcludeTest(ExportCase):
    def test_config_reads_exclude_and_build_merges_it(self):
        path = self._tmp / "l.json"
        path.write_text(json.dumps({"replace": [], "forbidden": [], "exclude": ["skills/demo/private/**"]}),
                        encoding="utf-8")
        local = load_local_config(path)
        self.assertEqual(local.exclude, ("skills/demo/private/**",))
        private = self.home / ".claude" / "skills" / "demo" / "private"
        private.mkdir()
        (private / "x.md").write_text("p", encoding="utf-8")
        (self.home / ".claude" / "skills" / "demo" / "SKILL.md.bak-2026-09-28").write_text("b", encoding="utf-8")
        files, _ = build_payload(self.home, HARNESS, local, self.root / "overrides", {})
        self.assertFalse([p for p in files if "private" in p or ".bak" in p], sorted(files))
        # harness.json'un kendi exclude'ları da hâlâ geçerli
        self.assertIn("skills/demo/SKILL.md", files)


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


class TreeScrubTest(ExportCase):
    def setUp(self):
        super().setUp()
        git(self.root, "init", "-q")
        (self.root / ".gitignore").write_text("secret.txt\nexport.local.json\n", encoding="utf-8")
        (self.root / "notes.md").write_text("clean\n", encoding="utf-8")
        git(self.root, "add", ".gitignore", "notes.md", "harness.json")
        self.local = self.write_local(forbidden=("ada",))

    def tree(self, check_only=False):
        lines = []
        code = run_export(self.root, self.home, self.out, self.local, check_only, say=lines.append, tree=True)
        return code, lines

    def test_clean_tree_passes(self):
        self.assertEqual(self.tree()[0], 0)

    def test_planted_word_in_tracked_non_payload_file(self):
        (self.root / "notes.md").write_text("hello Ada\n", encoding="utf-8")
        code, lines = self.tree()
        self.assertEqual(code, 1)
        self.assertTrue(any(ln.startswith("notes.md:1: forbidden") for ln in lines), lines)

    def test_planted_word_in_untracked_non_ignored_file(self):
        (self.root / "draft.md").write_text("by ada\n", encoding="utf-8")
        code, lines = self.tree()
        self.assertEqual(code, 1)
        self.assertTrue(any(ln.startswith("draft.md:1:") for ln in lines), lines)

    def test_gitignored_file_is_ignored(self):
        (self.root / "secret.txt").write_text("ada\n", encoding="utf-8")
        (self.root / "export.local.json").write_text('{"forbidden": ["ada"]}', encoding="utf-8")
        self.assertEqual(self.tree()[0], 0)

    def test_local_config_never_scanned_even_if_untracked_unignored(self):
        (self.root / "export.local.json").write_text('{"forbidden": ["ada"]}', encoding="utf-8")
        self.assertEqual(self.tree()[0], 0)

    def test_binary_file_checked_for_forbidden_only(self):
        (self.root / "img.bin").write_bytes(b"\x00\x01 someone@example.org \x00")
        self.assertEqual(self.tree()[0], 0)
        (self.root / "img.bin").write_bytes(b"\x00\x01 ada \x00")
        self.assertEqual(self.tree()[0], 1)

    def test_normal_export_runs_tree_scrub_and_fails(self):
        (self.root / "draft.md").write_text("by ada\n", encoding="utf-8")
        lines = []
        code = run_export(self.root, self.home, self.out, self.local, False, say=lines.append)
        self.assertEqual(code, 1)
        self.assertTrue(any(ln.startswith("draft.md:1:") for ln in lines), lines)

    def test_check_only_skips_tree_unless_requested(self):
        self.assertEqual(run_export(self.root, self.home, self.out, self.local, False, say=lambda _: None), 0)
        (self.root / "draft.md").write_text("by ada\n", encoding="utf-8")
        self.assertEqual(run_export(self.root, self.home, self.out, self.local, True, say=lambda _: None), 0)
        self.assertEqual(self.tree(check_only=True)[0], 1)


if __name__ == "__main__":
    unittest.main()
