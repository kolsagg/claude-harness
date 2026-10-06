import json
import unittest

from lib.exporter.build import ExportError, build_payload, manifest_bytes, sha256_bytes
from lib.exporter.settings import UnknownHookError
from lib.exporter.textops import is_excluded, transform_text
from tests.export_support import HARNESS, PAIRS, ExportCase, local_config


class TextPipelineTest(unittest.TestCase):
    def test_private_block_removed(self):
        src = "a\n<!-- private:start -->\nsecret\n<!-- private:end -->\nb\n"
        self.assertEqual(transform_text(src, ()), "a\nb\n")

    def test_replace_pairs_apply_in_order(self):
        # Uzun yol önce verilirse {{VAULT_PATH}} olur; ters sırada {{HOME}}/vault kalırdı
        self.assertEqual(transform_text("/home/ada/vault", PAIRS), "{{VAULT_PATH}}")
        swapped = (PAIRS[1], PAIRS[0])
        self.assertEqual(transform_text("/home/ada/vault", swapped), "{{HOME}}/vault")

    def test_input_not_mutated(self):
        pairs = list(PAIRS)
        transform_text("Ada", pairs)
        self.assertEqual(pairs, list(PAIRS))

    def test_exclude_globs(self):
        pats = ["skills/*/node_modules/**", "skills/**/*.bak*", "skills/**/__pycache__/**"]
        self.assertTrue(is_excluded("skills/a/node_modules/x/y.js", pats))
        self.assertTrue(is_excluded("skills/a/deep/dir/old.bak", pats))
        self.assertTrue(is_excluded("skills/a/SKILL.md.bak-2026-09-28", pats))
        self.assertTrue(is_excluded("skills/a/b/__pycache__/m.pyc", pats))
        self.assertFalse(is_excluded("skills/a/SKILL.md", pats))
        self.assertFalse(is_excluded("skills/a/node_modules_notes.md", pats))


class BuildPayloadTest(ExportCase):
    def build(self, lock=None, overrides=None):
        return build_payload(
            self.home, HARNESS, local_config(), overrides or self.root / "overrides", lock or {}
        )

    def test_global_and_skill_text_is_transformed(self):
        files, _ = self.build()
        claude = files["global/CLAUDE.md.tmpl"].decode("utf-8")
        self.assertIn("{{USER_NAME}}", claude)
        self.assertIn("{{VAULT_PATH}}", claude)
        self.assertNotIn("Secret diary", claude)
        self.assertIn("{{USER_NAME}}", files["skills/demo/SKILL.md"].decode("utf-8"))

    def test_binary_copied_untouched_and_excludes_skipped(self):
        skill = self.home / ".claude" / "skills" / "demo"
        (skill / "cache").mkdir()
        (skill / "cache" / "x.txt").write_text("c", encoding="utf-8")
        (skill / "old.bak").write_text("b", encoding="utf-8")
        (skill / "SKILL.md.bak-2026-09-28").write_text("b", encoding="utf-8")
        (skill / "node_modules" / "p").mkdir(parents=True)
        (skill / "node_modules" / "p" / "i.js").write_text("n", encoding="utf-8")
        files, _ = self.build()
        self.assertEqual(files["skills/demo/logo.png"], (skill / "logo.png").read_bytes())
        self.assertEqual(sorted(p for p in files if p.startswith("skills/")),
                         ["skills/demo/SKILL.md", "skills/demo/logo.png"])

    def test_templates_are_empty_not_live(self):
        files, _ = self.build()
        for name in ("global/GLOSSARY.md.tmpl", "global/BAGIMLILIKLAR.md.tmpl"):
            self.assertLess(len(files[name].decode("utf-8").splitlines()), 15)
        self.assertNotIn("Ada", files["global/GLOSSARY.md.tmpl"].decode("utf-8"))

    def test_settings_keys_language_and_plugins(self):
        files, _ = self.build()
        base = json.loads(files["settings/base.json"])
        self.assertEqual(base["language"], "{{LANGUAGE}}")
        self.assertEqual(base["model"], "opus")
        self.assertNotIn("voice", base)
        self.assertNotIn("permissions", base)
        self.assertEqual(base["enabledPlugins"], {"alpha@claude-plugins-official": True, "beta@beta-market": True})
        self.assertEqual(
            base["extraKnownMarketplaces"],
            {"beta-market": {"source": {"source": "github", "repo": "someone/beta"}}},
        )
        perms = json.loads(files["settings/permissions.json"])
        self.assertEqual(set(perms), {"permissions", "skipDangerousModePermissionPrompt"})

    def test_hook_rules_keep_skip_and_placeholders(self):
        files, _ = self.build()
        hooks = json.loads(files["settings/base.json"])["hooks"]
        self.assertEqual(set(hooks), {"PreToolUse", "SessionStart"})  # Stop boşaldı, düştü
        self.assertEqual(len(hooks["PreToolUse"]), 1)
        self.assertEqual(hooks["PreToolUse"][0]["hooks"][0]["command"], "ccstatusline --hook")
        cmd = hooks["SessionStart"][0]["hooks"][0]["command"]
        self.assertEqual(cmd, '{{PYTHON}} -B "{{HOME}}/.claude/skills/proje-baslat/doktor_hook.py"')
        self.assertEqual(len(hooks["SessionStart"][0]["hooks"]), 1)

    def test_unknown_hook_fails_export(self):
        def add(data):
            data["hooks"]["Stop"][0]["hooks"].append({"type": "command", "command": "mystery-tool run"})
            return data

        self.edit_settings(add)
        with self.assertRaises(UnknownHookError) as ctx:
            self.build()
        self.assertIn("mystery-tool run", str(ctx.exception))

    def test_codex_secret_lines_dropped(self):
        files, _ = self.build()
        toml = files["codex/config.toml"].decode("utf-8")
        for bad in ("auth_mode", "api_key", "Access_Token", "client_SECRET"):
            self.assertNotIn(bad, toml)
        self.assertIn('model = "gpt-x"', toml)
        self.assertIn("[tui]", toml)

    def test_override_applied_over_result(self):
        ov = self.root / "overrides" / "skills" / "demo"
        ov.mkdir(parents=True)
        (ov / "SKILL.md").write_text("neutral\n", encoding="utf-8")
        src = self.home / ".claude" / "skills" / "demo" / "SKILL.md"
        lock = {"skills/demo/SKILL.md": sha256_bytes(src.read_bytes())}
        files, warnings = self.build(lock=lock)
        self.assertEqual(files["skills/demo/SKILL.md"], b"neutral\n")
        self.assertEqual(warnings, [])

    def test_stale_override_warns_but_does_not_fail(self):
        ov = self.root / "overrides" / "skills" / "demo"
        ov.mkdir(parents=True)
        (ov / "SKILL.md").write_text("neutral\n", encoding="utf-8")
        lock = {"skills/demo/SKILL.md": sha256_bytes(b"old source")}
        files, warnings = self.build(lock=lock)
        self.assertEqual(files["skills/demo/SKILL.md"], b"neutral\n")
        self.assertEqual(len(warnings), 1)
        self.assertIn("kaynak değişti", warnings[0])

    def test_missing_skill_source_is_error(self):
        data = json.loads(json.dumps(HARNESS))
        data["ownSkills"] = [{"name": "ghost"}]
        with self.assertRaises(ExportError):
            build_payload(self.home, data, local_config(), self.root / "overrides", {})

    def test_manifest_sorted_with_hashes(self):
        files, _ = self.build()
        entries = json.loads(manifest_bytes(files))
        paths = [e["path"] for e in entries]
        self.assertEqual(paths, sorted(paths))
        by_path = {e["path"]: e["sha256"] for e in entries}
        self.assertEqual(by_path["skills/demo/SKILL.md"], sha256_bytes(files["skills/demo/SKILL.md"]))
        self.assertNotIn("MANIFEST.json", by_path)

    def test_source_home_is_not_modified(self):
        before = {p: p.read_bytes() for p in self.home.rglob("*") if p.is_file()}
        self.build()
        after = {p: p.read_bytes() for p in self.home.rglob("*") if p.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
