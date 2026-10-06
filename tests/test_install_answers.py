import json
import tempfile
import unittest
from pathlib import Path

from lib.installer.answers import AnswerError, parse_bool
from tests.test_install_support import FakeRunner, HomeCase, run_install

GOOD = {"USER_NAME": "Ada", "LANGUAGE": "English", "GITHUB_OWNER": "ada",
        "vault": False, "orca": False, "codex": False, "permissions": False}


class ParseBoolTest(unittest.TestCase):
    def test_json_bools_and_yes_no_words(self):
        for word in ("yes", "Y", "true", "evet", "E", "1", " yes "):
            self.assertIs(parse_bool("k", word), True, word)
        for word in ("no", "n", "false", "hayir", "hayır", "H", "0"):
            self.assertIs(parse_bool("k", word), False, word)
        self.assertIs(parse_bool("k", True), True)
        self.assertIs(parse_bool("k", False), False)
        self.assertIsNone(parse_bool("k", None))

    def test_anything_else_is_an_error(self):
        for bad in ("", "maybe", "nope", 1, 0, [], {}, "  "):
            with self.assertRaises(AnswerError, msg=repr(bad)):
                parse_bool("k", bad)


class AnswersFileTest(HomeCase):
    def go(self, data, extra=()):
        f = self.home / "a.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        return run_install(self.home, ["--home", str(self.home), "--skip-external", "--answers", str(f), *extra],
                           answers=["--yes"])

    def test_string_no_words_turn_everything_off(self):
        code, _ = self.go({**GOOD, "vault": "false", "orca": "no", "codex": "no", "permissions": "false"})
        self.assertEqual(code, 0)
        a = self.state()["answers"]
        self.assertEqual((a["vault"], a["orca"], a["codex"], a["permissions"]), (False, False, False, False))
        self.assertNotIn("permissions", json.loads((self.claude / "settings.json").read_text("utf-8")))

    def test_string_yes_words_turn_on(self):
        code, _ = self.go({**GOOD, "orca": "evet", "codex": "y", "permissions": "yes"})
        self.assertEqual(code, 0)
        a = self.state()["answers"]
        self.assertEqual((a["orca"], a["codex"], a["permissions"]), (True, True, True))

    def test_unknown_word_exits_2_with_message(self):
        for key in ("orca", "codex", "permissions", "vault"):
            home_case = self.go({**GOOD, key: 5 if key == "vault" else "maybe"})
            self.assertEqual(home_case[0], 2, key)
            self.assertIn(key, home_case[1])
        self.assertFalse((self.claude / ".claude-harness.json").exists())

    def test_vault_path_string_means_vault_with_that_path(self):
        vault = self.home / "v"
        code, _ = self.go({**GOOD, "vault": str(vault)})
        self.assertEqual(code, 0)
        a = self.state()["answers"]
        self.assertTrue(a["vault"])
        self.assertEqual(a["VAULT_PATH"], vault.as_posix())

    def test_vault_path_key_is_accepted(self):
        vault = self.home / "w"
        code, _ = self.go({**{k: v for k, v in GOOD.items() if k != "vault"}, "VAULT_PATH": str(vault)})
        self.assertEqual(code, 0)
        self.assertEqual(self.state()["answers"]["VAULT_PATH"], vault.as_posix())

    def test_vault_yes_word_without_path_is_missing(self):
        code, out = self.go({**GOOD, "vault": "yes"})
        self.assertEqual(code, 2)
        self.assertIn('"vault"', out)

    def test_vault_no_word_means_no_vault(self):
        code, _ = self.go({**GOOD, "vault": "hayır", "VAULT_PATH": "/ignored"})
        self.assertEqual(code, 0)
        self.assertFalse(self.state()["answers"]["vault"])
        self.assertIsNone(self.state()["answers"]["VAULT_PATH"])


class PermissionsPromptTest(HomeCase):
    def test_missing_permissions_without_tty_defaults_false(self):
        code, _ = run_install(self.home, ["--home", str(self.home), "--skip-external", "--no-vault",
                                          "--no-orca", "--no-codex"])
        self.assertEqual(code, 0)
        self.assertFalse(self.state()["answers"]["permissions"])

    def _tty(self, replies):
        asked = []

        def ask(prompt=""):
            asked.append(prompt)
            return next(replies)

        code, _ = run_install(self.home, ["--home", str(self.home), "--skip-external", "--no-vault", "--no-orca",
                                          "--no-codex", "--yes"], tty=True, ask=ask)
        return code, asked

    def test_tty_asks_permissions_default_no(self):
        code, asked = self._tty(iter([""]))
        self.assertEqual(code, 0)
        self.assertEqual(len(asked), 1)
        self.assertIn("Tehlikeli mod", asked[0])
        self.assertFalse(self.state()["answers"]["permissions"])

    def test_tty_yes_enables_permissions(self):
        code, _ = self._tty(iter(["evet"]))
        self.assertEqual(code, 0)
        self.assertTrue(self.state()["answers"]["permissions"])

    def test_tty_does_not_ask_when_flag_given(self):
        asked = []
        code, _ = run_install(self.home, ["--home", str(self.home), "--skip-external", "--no-vault", "--no-orca",
                                          "--no-codex", "--no-permissions", "--yes"], tty=True,
                              ask=lambda p="": asked.append(p) or "")
        self.assertEqual((code, asked), (0, []))


class ForeignHomeTest(unittest.TestCase):
    def test_custom_home_forces_external_steps_off(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as real:
            home = Path(tmp).resolve()
            runner = FakeRunner()
            code, out = run_install(home, ["--home", str(home), "--no-vault", "--no-orca", "--no-codex"],
                                    runner=runner, real_home=Path(real))
            self.assertEqual(code, 0, out)
            self.assertEqual(runner.calls, [])
            self.assertIn("gerçek ev dizini değil", out)
            state = json.loads((home / ".claude/.claude-harness.json").read_text(encoding="utf-8"))
            self.assertTrue(state["skipExternal"])

    def test_real_home_still_runs_external_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            runner = FakeRunner()
            run_install(home, ["--home", str(home), "--no-vault", "--no-orca", "--no-codex"], runner=runner,
                        real_home=home)
            self.assertTrue(runner.calls)


if __name__ == "__main__":
    unittest.main()
