import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import doctor

FIXTURE_REPO = Path(__file__).parent / "fixtures" / "doctor"
PLUGINS = ["alpha@claude-plugins-official", "beta@extra-market"]


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_home(root, answers=None, version="0.2.0", steps=None, plugins=PLUGINS):
    """Yeşil bir sahte kurulum kur; ana dizin yolunu döndür."""
    answers = {"USER_NAME": "Test", "vault": False, "orca": False, "codex": False, **(answers or {})}
    claude = root / ".claude"
    files = ["CLAUDE.md", "skills/own-one/SKILL.md"]
    write(claude / "CLAUDE.md", "x\n<!-- claude-harness:start -->\nbody\n<!-- claude-harness:end -->\n")
    write(claude / "skills/own-one/SKILL.md", "# own\n")
    write(root / ".agents/skills/ext-one/SKILL.md", "# ext\n")
    if answers.get("codex"):
        write(claude / "skills/codex-skill/SKILL.md", "# c\n")
        files.append("skills/codex-skill/SKILL.md")
        write(root / ".codex/config.toml", "model = 'x'\n")
    settings = {
        "enabledPlugins": {p: True for p in plugins},
        "extraKnownMarketplaces": {"extra-market": {"source": {"repo": "example/extra-market"}}},
    }
    write(claude / "settings.json", json.dumps(settings))
    state = {"version": version, "answers": answers, "files": files, "steps": steps or []}
    write(claude / ".claude-harness.json", json.dumps(state))
    return root


def fake_which(found=("claude", "codex")):
    return lambda name: f"/bin/{name}" if name in found else None


def fake_run(ids=PLUGINS):
    listing = json.dumps([{"id": i, "enabled": True} for i in ids])
    return lambda argv, env: (0, listing)


def run_doctor(home, which=None, run=None, extra=()):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = doctor.main(
            ["--home", str(home), "--repo", str(FIXTURE_REPO), *extra],
            which=which or fake_which(),
            run=run or fake_run(),
        )
    return code, out.getvalue()


class DoctorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_green_install_exits_zero(self):
        code, out = run_doctor(build_home(self.tmp))
        self.assertEqual(code, 0, out)
        self.assertNotIn("HATA", out)

    def test_missing_file_is_red(self):
        home = build_home(self.tmp)
        (home / ".claude/skills/own-one/SKILL.md").unlink()
        code, out = run_doctor(home)
        self.assertEqual(code, 1)
        self.assertIn("skills/own-one/SKILL.md", out)

    def test_leftover_placeholder_is_red(self):
        home = build_home(self.tmp)
        write(home / ".claude/skills/own-one/SKILL.md", "merhaba {{USER_NAME}}\n")
        code, out = run_doctor(home)
        self.assertEqual(code, 1)
        self.assertIn("{{USER_NAME}}", out)

    def test_missing_plugin_in_settings_is_red(self):
        home = build_home(self.tmp, plugins=PLUGINS[:1])
        code, out = run_doctor(home)
        self.assertEqual(code, 1)
        self.assertIn("beta@extra-market", out)

    def test_conditional_plugin_expected_only_when_flag_set(self):
        home = build_home(self.tmp, answers={"orca": True})
        code, out = run_doctor(home)
        self.assertEqual(code, 1)
        self.assertIn("orca-only@extra-market", out)

    def test_cli_plugin_missing_is_red(self):
        code, out = run_doctor(build_home(self.tmp), run=fake_run(PLUGINS[:1]))
        self.assertEqual(code, 1)
        self.assertIn("kurulu değil", out)

    def test_no_claude_cli_is_manual_not_red(self):
        code, out = run_doctor(build_home(self.tmp), which=fake_which(()))
        self.assertEqual(code, 0, out)
        self.assertIn("MANUEL", out)

    def test_codex_expected_but_config_missing_is_red(self):
        home = build_home(self.tmp, answers={"codex": True})
        (home / ".codex/config.toml").unlink()
        code, out = run_doctor(home)
        self.assertEqual(code, 1)
        self.assertIn("config.toml yok", out)

    def test_codex_not_on_path_is_yellow(self):
        home = build_home(self.tmp, answers={"codex": True})
        code, out = run_doctor(home, which=fake_which(("claude",)))
        self.assertEqual(code, 0, out)
        self.assertIn("UYARI", out)

    def test_no_state_exits_two(self):
        code, out = run_doctor(self.tmp)
        self.assertEqual(code, 2)
        self.assertIn("kurulu değil", out)

    def test_newer_repo_version_warns(self):
        code, out = run_doctor(build_home(self.tmp, version="0.1.0"))
        self.assertEqual(code, 0, out)
        self.assertIn("güncelleme var", out)

    def test_failed_step_is_red_with_detail(self):
        steps = [{"name": "plugin:beta@extra-market", "ok": False, "detail": "ağ yok"}]
        code, out = run_doctor(build_home(self.tmp, steps=steps))
        self.assertEqual(code, 1)
        self.assertIn("ağ yok", out)

    def test_missing_claude_md_block_is_red(self):
        home = build_home(self.tmp)
        write(home / ".claude/CLAUDE.md", "bloksuz\n")
        code, _ = run_doctor(home)
        self.assertEqual(code, 1)

    def test_vault_missing_is_red_and_bridge_warns(self):
        home = build_home(self.tmp, answers={"vault": True, "VAULT_PATH": str(self.tmp / "yok")})
        code, out = run_doctor(home)
        self.assertEqual(code, 1)
        self.assertIn("beyin", out)

    def test_vault_present_without_bridge_only_warns(self):
        vault = self.tmp / "vault"
        vault.mkdir()
        home = build_home(self.tmp, answers={"vault": True, "VAULT_PATH": str(vault)})
        code, out = run_doctor(home)
        self.assertEqual(code, 0, out)
        self.assertIn("UYARI", out)

    def test_skipped_external_skill_only_warns(self):
        home = build_home(self.tmp)
        shutil.rmtree(home / ".agents")
        state_path = home / ".claude/.claude-harness.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        write(state_path, json.dumps({**state, "skipExternal": True}))
        code, out = run_doctor(home)
        self.assertEqual(code, 0, out)
        self.assertIn("ext-one", out)

    def test_missing_external_skill_is_red_without_skip(self):
        home = build_home(self.tmp)
        shutil.rmtree(home / ".agents")
        code, _ = run_doctor(home)
        self.assertEqual(code, 1)

    def test_encoded_bridge_hook_counts_as_bridge(self):
        vault = self.tmp / "vault"
        vault.mkdir()
        home = build_home(self.tmp, answers={"vault": True, "VAULT_PATH": str(vault)})
        settings_path = home / ".claude/settings.json"
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        hook = {"hooks": [{"type": "command", "command": "powershell.exe -EncodedCommand AAAA"}]}
        write(settings_path, json.dumps({**settings, "hooks": {"SessionStart": [hook]}}))
        code, out = run_doctor(home)
        self.assertEqual(code, 0, out)
        self.assertNotIn("UYARI", out)

    def test_skipped_step_only_warns(self):
        steps = [{"name": "plugin:x", "ok": False, "skipped": True, "detail": "skipped: claude yok"}]
        code, out = run_doctor(build_home(self.tmp, steps=steps))
        self.assertEqual(code, 0, out)
        self.assertIn("plugin:x", out)

    def test_uninstalled_plugins_warn_when_external_skipped(self):
        home = build_home(self.tmp)
        state_path = home / ".claude/.claude-harness.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        write(state_path, json.dumps({**state, "skipExternal": True}))
        code, out = run_doctor(home, run=fake_run(ids=[]))
        self.assertEqual(code, 0, out)
        self.assertIn("kurulu değil", out)

    def test_invalid_settings_is_red(self):
        home = build_home(self.tmp)
        write(home / ".claude/settings.json", "{bozuk")
        code, _ = run_doctor(home)
        self.assertEqual(code, 1)

    def test_user_disabled_plugin_recorded_as_kept_only_warns(self):
        home = build_home(self.tmp)
        sp = home / ".claude/settings.json"
        settings = json.loads(sp.read_text(encoding="utf-8"))
        write(sp, json.dumps({**settings, "enabledPlugins": {**settings["enabledPlugins"], PLUGINS[1]: False}}))
        stp = home / ".claude/.claude-harness.json"
        state = json.loads(stp.read_text(encoding="utf-8"))
        write(stp, json.dumps({**state, "settingsKept": [f"enabledPlugins.{PLUGINS[1]}"]}))
        code, out = run_doctor(home)
        self.assertEqual(code, 0, out)
        self.assertIn("senin kapattığın", out)

    def test_disabled_plugin_not_recorded_as_kept_is_red(self):
        home = build_home(self.tmp)
        sp = home / ".claude/settings.json"
        settings = json.loads(sp.read_text(encoding="utf-8"))
        write(sp, json.dumps({**settings, "enabledPlugins": {**settings["enabledPlugins"], PLUGINS[1]: False}}))
        code, _ = run_doctor(home)
        self.assertEqual(code, 1)

    def test_ccstatusline_hook_without_binary_warns(self):
        home = build_home(self.tmp)
        sp = home / ".claude/settings.json"
        settings = json.loads(sp.read_text(encoding="utf-8"))
        hook = {"hooks": [{"type": "command", "command": "ccstatusline --hook"}]}
        write(sp, json.dumps({**settings, "hooks": {"Stop": [hook]}}))
        code, out = run_doctor(home)
        self.assertEqual(code, 0, out)
        self.assertIn("npm install -g ccstatusline", out)
        code, out = run_doctor(home, which=fake_which(("claude", "codex", "ccstatusline")))
        self.assertNotIn("ccstatusline kurulu değil", out)

    def test_ccstatusline_statusline_without_binary_warns(self):
        home = build_home(self.tmp)
        sp = home / ".claude/settings.json"
        settings = json.loads(sp.read_text(encoding="utf-8"))
        write(sp, json.dumps({**settings, "statusLine": {"type": "command", "command": "ccstatusline"}}))
        _, out = run_doctor(home)
        self.assertIn("ccstatusline kurulu değil", out)

    def test_json_output(self):
        code, out = run_doctor(build_home(self.tmp), extra=("--json",))
        data = json.loads(out)
        self.assertEqual(data["exit"], code)
        self.assertTrue(all("status" in c for c in data["checks"]))


if __name__ == "__main__":
    unittest.main()
