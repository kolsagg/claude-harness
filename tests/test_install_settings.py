import io
import json
import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from lib.installer.cli import main
from lib.installer.model import Deps
from lib.installer.settings import apply_settings
from tests.test_install_support import BASE, FIXTURES, HomeCase


class ApplySettingsUnitTest(unittest.TestCase):
    def test_inputs_not_mutated(self):
        old = {"hooks": {"Stop": [{"hooks": [{"command": "a"}]}]}, "x": 1, "env": {"A": "1"}}
        new = {"hooks": {"Stop": [{"hooks": [{"command": "b"}]}]}, "x": 2, "env": {"A": "2"}}
        before = json.dumps([old, new], sort_keys=True)
        merged, _, kept = apply_settings(old, new, {})
        self.assertEqual(json.dumps([old, new], sort_keys=True), before)
        self.assertEqual(merged["x"], 1)
        self.assertEqual(kept, ["env.A", "x"] if kept[0] == "env.A" else ["x", "env.A"])
        self.assertEqual(len(merged["hooks"]["Stop"]), 2)

    def test_duplicate_command_anywhere_in_event_is_skipped(self):
        old = {"hooks": {"Stop": [{"matcher": "m", "hooks": [{"type": "command", "command": "a"}]}]}}
        new = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "a"}]}]}}
        self.assertEqual(apply_settings(old, new, {})[0], old)

    def test_lists_union_and_dicts_recurse(self):
        old = {"permissions": {"allow": ["x"], "keep": 1}}
        new = {"permissions": {"allow": ["x", "y"]}}
        merged, _, _ = apply_settings(old, new, {})
        self.assertEqual(merged, {"permissions": {"allow": ["x", "y"], "keep": 1}})

    def test_untouched_value_written_earlier_is_updated(self):
        merged, written, kept = apply_settings({"model": "opus"}, {"model": "fable"}, {"model": "opus"})
        self.assertEqual((merged["model"], written, kept), ("fable", {"model": "fable"}, []))

    def test_changed_value_is_kept(self):
        merged, written, kept = apply_settings({"model": "sonnet"}, {"model": "fable"}, {"model": "opus"})
        self.assertEqual((merged["model"], written, kept), ("sonnet", {}, ["model"]))

    def test_sub_key_rule_keeps_user_false_plugin(self):
        old = {"enabledPlugins": {"a@x": False, "b@x": True}}
        new = {"enabledPlugins": {"a@x": True, "b@x": True, "c@x": True}}
        merged, written, kept = apply_settings(old, new, {"enabledPlugins": {"b@x": True}})
        self.assertEqual(merged["enabledPlugins"], {"a@x": False, "b@x": True, "c@x": True})
        self.assertEqual(kept, ["enabledPlugins.a@x"])
        self.assertEqual(written["enabledPlugins"], {"b@x": True, "c@x": True})

    def test_permissions_retired_only_when_unchanged(self):
        prev = {"skipDangerousModePermissionPrompt": True, "permissions": {"defaultMode": "auto"}}
        old = {"skipDangerousModePermissionPrompt": True, "permissions": {"defaultMode": "auto"}, "m": 1}
        merged, written, kept = apply_settings(old, {}, prev, with_permissions=False)
        self.assertEqual(merged, {"m": 1})
        self.assertEqual((written, kept), ({}, []))
        changed = {"skipDangerousModePermissionPrompt": False, "permissions": {"defaultMode": "plan"}}
        merged, written, kept = apply_settings(changed, {}, prev, with_permissions=False)
        self.assertEqual(merged, changed)
        self.assertEqual(sorted(kept), ["permissions.defaultMode", "skipDangerousModePermissionPrompt"])


    def test_preexisting_equal_user_value_is_not_claimed(self):
        # kullanıcı izinleri kendi açmışsa harness sahiplenmez, sonra kapatınca silmez
        user = {"skipDangerousModePermissionPrompt": True, "permissions": {"defaultMode": "auto"}}
        merged, written, _ = apply_settings(user, dict(user), {})
        self.assertEqual(merged, user)
        self.assertNotIn("skipDangerousModePermissionPrompt", written)
        self.assertNotIn("defaultMode", written.get("permissions", {}))
        merged, _, _ = apply_settings(merged, {}, written, with_permissions=False)
        self.assertEqual(merged, user)

    def test_value_owned_before_and_equal_stays_owned(self):
        _, written, _ = apply_settings({"model": "opus"}, {"model": "opus"}, {"model": "opus"})
        self.assertEqual(written, {"model": "opus"})


class SettingsInstallTest(HomeCase):
    def seed(self):
        self.claude.mkdir(parents=True)
        user = {
            "myKey": {"a": 1},
            "model": "sonnet",
            "enabledPlugins": {"mine@x": True},
            "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "my-hook.sh"}]}],
                      "Stop": [{"hooks": [{"type": "command", "command": "stop.sh"}]}]},
        }
        (self.claude / "settings.json").write_text(json.dumps(user, indent=4), encoding="utf-8")

    def load(self):
        return json.loads((self.claude / "settings.json").read_text(encoding="utf-8"))

    def test_user_key_and_hook_survive_and_user_scalar_is_kept(self):
        self.seed()
        _, out = self.install()
        s = self.load()
        self.assertEqual(s["myKey"], {"a": 1})
        self.assertEqual(s["model"], "sonnet")
        self.assertIn("kept your value for model", out)
        self.assertEqual(self.state()["settingsKept"], ["model"])
        self.assertEqual(s["language"], "Turkish")
        self.assertEqual(s["enabledPlugins"], {"mine@x": True, "context7@claude-plugins-official": True})
        commands = [h["command"] for g in s["hooks"]["SessionStart"] for h in g["hooks"]]
        self.assertEqual(commands[0], "my-hook.sh")
        self.assertEqual(len(commands), 2)
        self.assertEqual(s["hooks"]["Stop"][0]["hooks"][0]["command"], "stop.sh")

    def test_backup_made_before_overwrite(self):
        self.seed()
        original = (self.claude / "settings.json").read_bytes()
        self.install()
        backup = self.claude / "backups/claude-harness-20261006-120000/settings.json"
        self.assertEqual(backup.read_bytes(), original)

    def test_second_run_adds_no_duplicate_hooks(self):
        self.seed()
        self.install()
        once = self.load()
        self.install()
        self.assertEqual(self.load(), once)

    def test_invalid_existing_settings_is_left_untouched_and_reported(self):
        self.claude.mkdir(parents=True)
        (self.claude / "settings.json").write_text("{not json", encoding="utf-8")
        code, out = self.install()
        self.assertEqual(code, 1)
        self.assertEqual((self.claude / "settings.json").read_text(encoding="utf-8"), "{not json")
        self.assertIn("core:settings", out)
        self.assertTrue((self.claude / "skills/alpha/SKILL.md").is_file())


class KeepUserValuesTest(HomeCase):
    def load(self):
        return json.loads((self.claude / "settings.json").read_text(encoding="utf-8"))

    def test_model_and_theme_survive_first_install_and_rerun(self):
        self.claude.mkdir(parents=True)
        (self.claude / "settings.json").write_text('{"model":"sonnet","theme":"light"}', encoding="utf-8")
        _, out = self.install()
        self.assertIn("kept your value for model", out)
        self.assertEqual(self.load()["model"], "sonnet")
        self.assertEqual(self.load()["theme"], "light")
        once = (self.claude / "settings.json").read_bytes()
        code, _ = self.install()
        self.assertEqual(code, 0)
        self.assertEqual(self.load()["model"], "sonnet")
        self.assertEqual((self.claude / "settings.json").read_bytes(), once)

    def test_value_written_by_harness_is_updated_when_payload_changes(self):
        self.install()
        self.assertEqual(self.load()["model"], "opus")
        self.assertEqual(self.state()["settingsWritten"]["model"], "opus")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = Path(tmp.name) / "repo"
        shutil.copytree(FIXTURES, repo)
        base = repo / "payload/settings/base.json"
        base.write_text(base.read_text(encoding="utf-8").replace('"opus"', '"fable"'), encoding="utf-8")
        deps = Deps(isatty=lambda: False, now=lambda: datetime(2026, 1, 1), windows=False,
                    real_home=self.home, out=io.StringIO())
        main([*BASE, "--no-vault", "--no-orca", "--no-codex", "--skip-external", "--home", str(self.home)],
             repo_root=repo, deps=deps)
        self.assertEqual(self.load()["model"], "fable")

    def test_user_disabled_plugin_stays_false(self):
        self.claude.mkdir(parents=True)
        user = {"enabledPlugins": {"context7@claude-plugins-official": False}}
        (self.claude / "settings.json").write_text(json.dumps(user), encoding="utf-8")
        _, out = self.install()
        self.install()
        self.assertFalse(self.load()["enabledPlugins"]["context7@claude-plugins-official"])
        self.assertIn("kept your value for enabledPlugins.context7@claude-plugins-official", out)
        self.assertEqual(self.state()["settingsKept"], ["enabledPlugins.context7@claude-plugins-official"])

    def test_permissions_yes_then_no_removes_untouched_values(self):
        self.install("--permissions")
        self.assertEqual(self.load()["permissions"]["defaultMode"], "auto")
        self.install("--no-permissions")
        s = self.load()
        self.assertNotIn("permissions", s)
        self.assertNotIn("skipDangerousModePermissionPrompt", s)

    def test_permissions_yes_then_no_keeps_changed_values_and_reports(self):
        self.install("--permissions")
        s = self.load()
        (self.claude / "settings.json").write_text(
            json.dumps({**s, "permissions": {"defaultMode": "plan"}}), encoding="utf-8")
        _, out = self.install("--no-permissions")
        self.assertEqual(self.load()["permissions"]["defaultMode"], "plan")
        self.assertNotIn("skipDangerousModePermissionPrompt", self.load())
        self.assertIn("kept your value for permissions.defaultMode", out)

    def test_codex_yes_then_no_keeps_config_and_says_so(self):
        self.install("--codex")
        _, out = self.install("--no-codex")
        self.assertTrue((self.home / ".codex" / "config.toml").is_file())
        self.assertIn("config.toml korundu", out)

    def test_replaced_user_skill_is_reported_with_backup(self):
        mine = self.claude / "skills" / "alpha"
        mine.mkdir(parents=True)
        (mine / "SKILL.md").write_text("my own alpha\n", encoding="utf-8")
        _, out = self.install()
        self.assertIn("replaced your skill alpha (backup at", out)
        backup = self.claude / "backups/claude-harness-20261006-120000/skills/alpha/SKILL.md"
        self.assertEqual(backup.read_text(encoding="utf-8"), "my own alpha\n")
        _, out2 = self.install()
        self.assertNotIn("replaced your skill", out2)


if __name__ == "__main__":
    unittest.main()
