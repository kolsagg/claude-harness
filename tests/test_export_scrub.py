import json
import unittest

from lib.exporter.config import load_local_config
from lib.exporter.pipeline import run_export
from lib.exporter.scrub import apply_allow, parse_allow, scrub_files
from tests.export_support import ExportCase, local_config

# Token biçimleri çalışma anında birleştirilir: kaynakta gerçek token gibi görünmesin
SAMPLES = {
    "forbidden": "contact the ADA team",
    "replace-from": "path is /home/ada/vault here",
    "email": "write to someone@example.org please",
    "token-sk": "key sk-" + "a1B2c3D4e5F6g7H8i9",
    "token-gh": "tok ghp_" + "A1b2C3d4E5f6G7h8",
    "token-slack": "tok xoxb-" + "1234567890abc",
    "token-aws": "id AKIA" + "ABCDEFGHIJKLMNOP",
    "bearer": "Authorization: Bearer " + "abcdefghij0123456789xyz",
    "api-key": "api_key = abcdefgh12345",
    "abs-path": "open C:\\Users\\bob\\file.txt",
}


def scrub(text, rule_name="x.md"):
    return scrub_files({rule_name: text.encode("utf-8")}, local_config())


class ScrubRulesTest(unittest.TestCase):
    def test_every_rule_fires_on_planted_sample(self):
        for rule, sample in SAMPLES.items():
            with self.subTest(rule=rule):
                rules = {f.rule for f in scrub(sample)}
                self.assertIn(rule, rules)

    def test_abs_path_variants(self):
        for sample in ("C:/Users/bob/x", "/c/Users/bob/x", "/Users/bob/x", "/home/bob/x"):
            with self.subTest(sample=sample):
                self.assertIn("abs-path", {f.rule for f in scrub(sample)})

    def test_placeholder_paths_are_clean(self):
        for sample in ("{{HOME}}/.claude", "/home/{{USER_NAME}}/x", "C:/Users/{{USER_NAME}}/x"):
            with self.subTest(sample=sample):
                self.assertEqual([f for f in scrub(sample) if f.rule == "abs-path"], [])

    def test_clean_text_has_no_findings(self):
        self.assertEqual(scrub("# Title\n\nHello {{USER_NAME}} at {{HOME}}/x\n"), [])

    def test_binary_forbidden_word_detected(self):
        found = scrub_files({"a.bin": b"\x00\x01 ada \x00"}, local_config())
        self.assertEqual([f.rule for f in found], ["forbidden-binary"])

    def test_finding_render_has_path_line_rule(self):
        found = scrub("ok\nwrite someone@example.org")
        self.assertEqual(found[0].render().split(": ")[0], "x.md:2")

    def test_secret_excerpt_is_masked(self):
        found = [f for f in scrub(SAMPLES["token-sk"]) if f.rule == "token-sk"]
        self.assertNotIn("a1B2c3D4e5F6g7H8i9", found[0].excerpt)


class AllowListTest(unittest.TestCase):
    def test_allow_requires_reason(self):
        with self.assertRaises(ValueError):
            parse_allow("x.md:email:foo\n")

    def test_allowed_finding_removed_and_unused_reported(self):
        entries = parse_allow("x.md:email:someone@example.org  # belge örneği\ny.md:email:none  # eski\n")
        found = scrub(SAMPLES["email"])
        remaining, unused = apply_allow(found, entries)
        self.assertEqual(remaining, [])
        self.assertEqual(unused, [("y.md", "email", "none")])


class RunExportScrubTest(ExportCase):
    def run_export(self, check_only=False, local=None):
        lines = []
        code = run_export(
            self.root, self.home, self.out, local or self.write_local(), check_only, say=lines.append
        )
        return code, lines

    def test_clean_fixture_exports_and_writes_manifest(self):
        code, lines = self.run_export()
        self.assertEqual(code, 0, lines)
        self.assertTrue((self.out / "MANIFEST.json").is_file())
        self.assertTrue((self.out / "global" / "CLAUDE.md.tmpl").is_file())

    def test_check_only_passes_then_fails_on_planted_leak(self):
        self.assertEqual(self.run_export()[0], 0)
        self.assertEqual(self.run_export(check_only=True)[0], 0)
        (self.out / "skills" / "demo" / "SKILL.md").write_text("mail me@example.org\n", encoding="utf-8")
        code, lines = self.run_export(check_only=True)
        self.assertEqual(code, 1)
        self.assertTrue(any("email" in ln for ln in lines))

    def test_failed_scrub_leaves_old_payload_untouched(self):
        self.assertEqual(self.run_export()[0], 0)
        before = {p: p.read_bytes() for p in self.out.rglob("*") if p.is_file()}
        # Kaynağa sızıntı koy: replace map'in yakalamadığı bir e-posta
        skill = self.home / ".claude" / "skills" / "demo" / "SKILL.md"
        skill.write_text("leak: someone@example.org\n", encoding="utf-8")
        code, lines = self.run_export()
        self.assertEqual(code, 1)
        after = {p: p.read_bytes() for p in self.out.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual([p for p in self._tmp.iterdir() if p.name.startswith(".payload")], [])

    def test_failed_scrub_creates_no_payload_when_none_existed(self):
        skill = self.home / ".claude" / "skills" / "demo" / "SKILL.md"
        skill.write_text("leak: someone@example.org\n", encoding="utf-8")
        self.assertEqual(self.run_export()[0], 1)
        self.assertFalse(self.out.exists())

    def test_unknown_hook_exit_1_and_lists_command(self):
        def add(data):
            data["hooks"]["Stop"][0]["hooks"].append({"type": "command", "command": "mystery-tool run"})
            return data

        self.edit_settings(add)
        code, lines = self.run_export()
        self.assertEqual(code, 1)
        self.assertTrue(any("mystery-tool run" in ln for ln in lines))
        self.assertFalse(self.out.exists())

    def test_repo_docs_are_scanned(self):
        (self.root / "README.md").write_text("by someone@example.org\n", encoding="utf-8")
        code, lines = self.run_export()
        self.assertEqual(code, 1)
        self.assertTrue(any(ln.startswith("README.md:1:") for ln in lines))

    def test_allow_list_suppresses_finding(self):
        (self.root / "README.md").write_text("by someone@example.org\n", encoding="utf-8")
        (self.root / "scrub-allow.txt").write_text(
            "README.md,scrub-allow.txt:email:someone@example.org  # örnek adres\n", encoding="utf-8"
        )
        self.assertEqual(self.run_export()[0], 0)

    def test_tolerates_unescaped_backslashes_in_local_config(self):
        path = self._tmp / "bad.json"
        path.write_text('{"replace": [["C:\\Users\\ada", "{{HOME}}"]], "forbidden": []}', encoding="utf-8")
        cfg = load_local_config(path)
        self.assertEqual(cfg.replace, (("C:\\Users\\ada", "{{HOME}}"),))
        self.assertEqual(len(cfg.warnings), 1)


if __name__ == "__main__":
    unittest.main()
