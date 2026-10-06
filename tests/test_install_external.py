import unittest

from tests.test_install_support import FakeRunner, HomeCase, run_install


class ExternalStepsTest(HomeCase):
    def go(self, *extra, runner=None, which=None):
        runner = runner or FakeRunner()
        flags = ["--no-vault", "--no-orca", "--no-codex"]
        flags = [f for f in flags if f.replace("--no-", "--") not in extra]
        code, out = run_install(self.home, ["--home", str(self.home), *flags, *extra], runner=runner, which=which)
        return code, out, runner

    def test_expected_commands_without_codex_orca(self):
        code, out, runner = self.go()
        self.assertEqual(code, 0, out)
        calls = runner.calls
        self.assertEqual(calls[0], ["claude", "plugin", "marketplace", "add", "anthropics/claude-plugins-official"])
        self.assertIn(["claude", "plugin", "marketplace", "add", "mem0ai/mem0"], calls)
        self.assertIn(["claude", "plugin", "install", "context7@claude-plugins-official"], calls)
        self.assertIn(["claude", "plugin", "install", "mem0@mem0-plugins"], calls)
        self.assertIn(["npx", "--yes", "skills", "add", "vercel-labs/skills", "--skill", "find-skills",
                       "-g", "-y", "-a", "claude-code"], calls)
        self.assertIn(["npm", "install", "-g", "ccstatusline"], calls)
        self.assertIn(["python3", "-m", "pip", "install", "--user", "graphifyy"], calls)
        self.assertIn(["graphify", "install"], calls)
        skill_dir = (self.claude / "skills" / "beta").as_posix()
        self.assertIn(["npm", "install", "--prefix", f"{skill_dir}/engine"], calls)
        joined = [" ".join(c) for c in calls]
        self.assertFalse(any("orca" in j or "@openai/codex" in j for j in joined))
        self.assertIn("/mem0 onboard", out)

    def test_orca_and_codex_add_their_steps(self):
        _, _, runner = self.go("--orca", "--codex")
        joined = [" ".join(c) for c in runner.calls]
        self.assertTrue(any("stablyai/orca --skill orca-cli" in j for j in joined))
        self.assertIn(["npm", "install", "-g", "@openai/codex"], runner.calls)

    def test_failing_step_does_not_stop_next_and_is_recorded(self):
        code, out, runner = self.go(runner=FakeRunner(fail=["install context7"]))
        self.assertEqual(code, 1)
        self.assertIn(["claude", "plugin", "install", "mem0@mem0-plugins"], runner.calls)
        steps = {s["name"]: s for s in self.state()["steps"]}
        self.assertFalse(steps["plugin:context7@claude-plugins-official"]["ok"])
        self.assertTrue(steps["plugin:mem0@mem0-plugins"]["ok"])
        self.assertIn("BAŞARISIZ", out)

    def test_pip_then_skipped_when_pip_fails(self):
        _, _, runner = self.go(runner=FakeRunner(fail=["pip install"]))
        self.assertNotIn(["graphify", "install"], runner.calls)
        steps = {s["name"]: s for s in self.state()["steps"]}
        self.assertTrue(steps["pip-then:graphifyy"]["skipped"])

    def test_claude_missing_skips_plugin_steps_with_instruction(self):
        code, out, runner = self.go(which=lambda name: None if name == "claude" else f"/bin/{name}")
        self.assertEqual(code, 0)
        self.assertFalse(any(c[0] == "claude" for c in runner.calls))
        steps = {s["name"]: s for s in self.state()["steps"]}
        step = steps["plugin:context7@claude-plugins-official"]
        self.assertTrue(step["skipped"])
        self.assertIn("claude plugin install context7@claude-plugins-official", step["detail"])
        self.assertTrue(steps["npm:ccstatusline"]["ok"])

    def test_skip_external_runs_nothing_and_keeps_old_steps(self):
        self.go()
        before = self.state()["steps"]
        runner = FakeRunner()
        run_install(self.home, ["--home", str(self.home), "--skip-external", "--no-vault", "--no-orca", "--no-codex"],
                    runner=runner)
        self.assertEqual(runner.calls, [])
        self.assertEqual(self.state()["steps"], before)
        self.assertTrue(self.state()["skipExternal"])

    def test_skip_external_flag_recorded_false_when_run(self):
        self.go()
        self.assertFalse(self.state()["skipExternal"])


if __name__ == "__main__":
    unittest.main()
