import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lib.template import KNOWN
from tests.test_install_support import FIXTURES, HomeCase, run_install

ROOT = Path(__file__).resolve().parents[1]
LEFT = re.compile(r"\{\{(" + "|".join(KNOWN) + r")\}\}")


class AnswersTest(HomeCase):
    def test_missing_answers_without_tty_exit_2_with_json(self):
        code, out = run_install(self.home, ["--home", str(self.home)], answers=["--name", "Ada"])
        self.assertEqual(code, 2)
        items = json.loads(out)
        keys = [i["key"] for i in items]
        self.assertEqual(keys, ["LANGUAGE", "GITHUB_OWNER", "vault", "orca", "codex"])
        self.assertIn("hangi dilde", items[0]["question"])
        self.assertFalse((self.claude / ".claude-harness.json").exists())

    def test_real_script_exit_2_in_subprocess(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "install.py"), "--home", str(self.home), "--name", "Ada"],
            capture_output=True, stdin=subprocess.DEVNULL,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(json.loads(proc.stdout.decode("utf-8"))[0]["key"], "LANGUAGE")

    def test_answers_file_and_flag_priority(self):
        f = self.home / "a.json"
        f.write_text(json.dumps({"USER_NAME": "FromFile", "LANGUAGE": "English", "GITHUB_OWNER": "o",
                                 "vault": False, "VAULT_PATH": None, "orca": False, "codex": False,
                                 "permissions": False}), encoding="utf-8")
        code, _ = run_install(self.home, ["--home", str(self.home), "--skip-external", "--language", "German",
                                          "--answers", str(f)], answers=["--yes"])
        self.assertEqual(code, 0)
        answers = self.state()["answers"]
        self.assertEqual((answers["USER_NAME"], answers["LANGUAGE"]), ("FromFile", "German"))
        self.assertIsNone(answers["VAULT_PATH"])

    def test_previous_state_answers_are_lowest_priority(self):
        self.install()
        code, _ = run_install(self.home, ["--home", str(self.home), "--skip-external", "--language", "German"],
                              answers=["--yes"])
        self.assertEqual(code, 0)
        answers = self.state()["answers"]
        self.assertEqual((answers["USER_NAME"], answers["LANGUAGE"], answers["GITHUB_OWNER"]),
                         ("Ada", "German", "ada"))

    def test_permissions_default_off(self):
        self.install()
        self.assertEqual(self.state()["answers"]["permissions"], False)
        settings = json.loads((self.claude / "settings.json").read_text(encoding="utf-8"))
        self.assertNotIn("permissions", settings)
        self.assertNotIn("skipDangerousModePermissionPrompt", settings)

    def test_permissions_flag_merges_permission_keys(self):
        self.install("--permissions")
        settings = json.loads((self.claude / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["permissions"]["defaultMode"], "auto")


class FlagsTest(HomeCase):
    def test_no_flags_installs_base_only(self):
        self.install()
        self.assertNotIn("skills/codex-fleet/SKILL.md", self.tree())
        self.assertFalse((self.home / ".codex" / "config.toml").exists())
        text = (self.claude / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertNotIn("Vault at", text)
        self.assertNotIn("Orca notes", text)
        self.assertEqual(json.loads((self.claude / "settings.json").read_text("utf-8"))["extra"], ["always"])

    def test_codex_installs_fleet_and_config(self):
        self.install("--codex")
        self.assertIn("skills/codex-fleet/SKILL.md", self.tree())
        toml = (self.home / ".codex" / "config.toml").read_text(encoding="utf-8")
        self.assertIn(self.home.as_posix(), toml)

    def test_existing_codex_config_is_never_overwritten(self):
        cfg = self.home / ".codex" / "config.toml"
        cfg.parent.mkdir(parents=True)
        cfg.write_text("mine = 1\n", encoding="utf-8")
        self.install("--codex")
        self.assertEqual(cfg.read_text(encoding="utf-8"), "mine = 1\n")

    def test_vault_and_orca_blocks_appear(self):
        vault = self.home / "My Vault"
        self.install("--vault", str(vault), "--orca")
        text = (self.claude / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn(f"Vault at {vault.as_posix()}.", text)
        self.assertIn("Orca notes", text)
        self.assertIn("orca-only", (self.claude / "settings.json").read_text(encoding="utf-8"))
        code, out = self.install("--vault", str(vault))
        self.assertIn("Beyin V3", out)

    def test_no_known_placeholder_left_in_text_files(self):
        self.install("--vault", str(self.home / "v"), "--orca", "--codex")
        scanned = 0
        for path in list(self.claude.rglob("*")) + [self.home / ".codex" / "config.toml"]:
            if path.is_file() and "backups" not in path.parts and path.suffix != ".png":
                self.assertIsNone(LEFT.search(path.read_text(encoding="utf-8")), str(path))
                scanned += 1
        self.assertGreater(scanned, 6)

    def test_binary_file_copied_untouched(self):
        self.install()
        src = FIXTURES / "payload/skills/alpha/assets/logo.png"
        self.assertEqual((self.claude / "skills/alpha/assets/logo.png").read_bytes(), src.read_bytes())

    def test_stray_vault_placeholder_is_reported_not_fatal(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = Path(tmp.name) / "repo"
        import shutil
        shutil.copytree(FIXTURES, repo)
        (repo / "payload/skills/beta/SKILL.md").write_text("path {{VAULT_PATH}}\n", encoding="utf-8")
        from lib.installer.cli import main
        from tests.test_install_support import Deps, datetime
        import io
        out = io.StringIO()
        deps = Deps(out=out, isatty=lambda: False, now=lambda: datetime(2026, 1, 1), windows=False)
        code = main(["--name", "A", "--language", "T", "--github-owner", "a", "--no-vault", "--no-orca",
                    "--no-codex", "--yes", "--skip-external", "--home", str(self.home)], repo_root=repo, deps=deps)
        self.assertEqual(code, 0)
        self.assertIn("VAULT_PATH", out.getvalue())


class ClaudeMdTest(HomeCase):
    def test_existing_without_markers_goes_below_block(self):
        self.claude.mkdir(parents=True)
        (self.claude / "CLAUDE.md").write_text("# my own rules\nkeep me\n", encoding="utf-8")
        self.install()
        text = (self.claude / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("<!-- claude-harness:start -->"))
        self.assertLess(text.index("claude-harness:end"), text.index("keep me"))
        self.assertTrue((self.claude / "backups/claude-harness-20261006-120000/CLAUDE.md").is_file())

    def test_markers_replace_only_block(self):
        self.install()
        path = self.claude / "CLAUDE.md"
        text = path.read_text(encoding="utf-8")
        path.write_text("TOP LINE\n" + text.replace("Global for Ada", "STALE") + "\nBOTTOM LINE\n", encoding="utf-8")
        self.install()
        new = path.read_text(encoding="utf-8")
        self.assertTrue(new.startswith("TOP LINE\n"))
        self.assertTrue(new.endswith("\nBOTTOM LINE\n"))
        self.assertIn("Global for Ada", new)
        self.assertNotIn("STALE", new)
        self.assertEqual(new.count("claude-harness:start"), 1)

    def test_glossary_written_only_if_absent(self):
        self.claude.mkdir(parents=True)
        (self.claude / "GLOSSARY.md").write_text("mine\n", encoding="utf-8")
        self.install()
        self.assertEqual((self.claude / "GLOSSARY.md").read_text(encoding="utf-8"), "mine\n")
        self.assertTrue((self.claude / "BAGIMLILIKLAR.md").is_file())
        self.assertNotIn("GLOSSARY.md", self.state()["files"])


class IdempotencyTest(HomeCase):
    def test_second_run_same_files_and_no_new_backup(self):
        self.install("--codex", "--permissions")
        first = {p: (self.claude / p).read_bytes() for p in self.tree() if p != ".claude-harness.json"}
        state1 = self.state()
        self.install("--codex", "--permissions")
        second = {p: (self.claude / p).read_bytes() for p in self.tree() if p != ".claude-harness.json"}
        self.assertEqual(first, second)
        self.assertEqual(state1["files"], self.state()["files"])
        self.assertFalse((self.claude / "backups").exists())

    def test_state_file_shape(self):
        self.install("--vault", str(self.home / "v"))
        st = self.state()
        self.assertEqual(set(st), {"version", "installedAt", "repo", "answers", "skipExternal", "files", "steps",
                                  "settingsWritten", "settingsKept"})
        self.assertTrue(st["skipExternal"])
        self.assertIn("skills/alpha/SKILL.md", st["files"])
        self.assertIn("settings.json", st["files"])

    def test_dry_run_writes_nothing(self):
        code, out = run_install(self.home, ["--home", str(self.home), "--dry-run", "--no-vault", "--no-orca", "--no-codex"])
        self.assertEqual(code, 0)
        self.assertIn("[dry-run]", out)
        self.assertIn("claude plugin install context7@claude-plugins-official", out)
        self.assertEqual(list(self.home.iterdir()), [])


class StaleTest(HomeCase):
    def test_stale_harness_file_removed_user_file_kept(self):
        self.install("--codex")
        fleet = self.claude / "skills/codex-fleet"
        (fleet / "mine.txt").write_text("user file\n", encoding="utf-8")
        self.install("--no-codex")
        self.assertFalse((fleet / "SKILL.md").exists())
        self.assertEqual((fleet / "mine.txt").read_text(encoding="utf-8"), "user file\n")
        self.assertTrue((self.claude / "backups/claude-harness-20261006-120000/skills/codex-fleet/SKILL.md").is_file())
        self.assertNotIn("skills/codex-fleet/SKILL.md", self.state()["files"])

    def test_emptied_skill_dir_is_pruned(self):
        self.install("--codex")
        self.install("--no-codex")
        self.assertFalse((self.claude / "skills/codex-fleet").exists())


if __name__ == "__main__":
    unittest.main()
