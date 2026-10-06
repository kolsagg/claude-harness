import unittest

from lib.template import (
    UnresolvedPlaceholder,
    render_json,
    render_text,
    strip_private,
)


class RenderTextTest(unittest.TestCase):
    def test_fills_placeholders(self):
        out = render_text("Hi {{USER_NAME}} at {{HOME}}", {"USER_NAME": "Ada", "HOME": "/h/ada"}, set())
        self.assertEqual(out, "Hi Ada at /h/ada")

    def test_known_placeholder_without_value_raises(self):
        with self.assertRaises(UnresolvedPlaceholder):
            render_text("{{VAULT_PATH}}", {}, set())

    def test_unknown_braces_are_left_alone(self):
        self.assertEqual(render_text("{{TITLE}} {{x}}", {}, set()), "{{TITLE}} {{x}}")

    def test_true_condition_keeps_block_and_markers(self):
        src = "a\n<!-- if:vault -->\nv\n<!-- endif:vault -->\nb\n"
        self.assertEqual(render_text(src, {}, {"vault"}), src)

    def test_false_condition_drops_block_and_markers(self):
        src = "a\n<!-- if:vault -->\nv\n<!-- endif:vault -->\nb\n"
        self.assertEqual(render_text(src, {}, set()), "a\nb\n")

    def test_placeholder_inside_dropped_block_is_ignored(self):
        src = "<!-- if:codex -->\n{{MISSING}}\n<!-- endif:codex -->\nok\n"
        self.assertEqual(render_text(src, {}, set()), "ok\n")

    def test_unbalanced_block_raises(self):
        with self.assertRaises(ValueError):
            render_text("<!-- if:orca -->\nx\n", {}, set())


class StripPrivateTest(unittest.TestCase):
    def test_removes_private_blocks(self):
        src = "keep\n<!-- private:start -->\nsecret\n<!-- private:end -->\nalso\n"
        self.assertEqual(strip_private(src), "keep\nalso\n")

    def test_unbalanced_private_raises(self):
        with self.assertRaises(ValueError):
            strip_private("<!-- private:start -->\nx\n")


class RenderJsonTest(unittest.TestCase):
    def test_drops_items_with_false_requires(self):
        data = {"hooks": [{"cmd": "a"}, {"cmd": "b", "_requires": "orca"}]}
        self.assertEqual(render_json(data, {}, set()), {"hooks": [{"cmd": "a"}]})

    def test_keeps_items_with_true_requires_and_strips_key(self):
        data = {"hooks": [{"cmd": "{{PYTHON}} x", "_requires": "orca"}]}
        out = render_json(data, {"PYTHON": "py -3"}, {"orca"})
        self.assertEqual(out, {"hooks": [{"cmd": "py -3 x"}]})

    def test_does_not_mutate_input(self):
        data = {"a": [{"_requires": "vault"}]}
        render_json(data, {}, set())
        self.assertEqual(data, {"a": [{"_requires": "vault"}]})

    def test_drops_object_keys_with_requires_suffix(self):
        data = {"plugins": {"x@m": {"_requires": "codex", "value": True}, "y@m": True}}
        self.assertEqual(render_json(data, {}, set()), {"plugins": {"y@m": True}})


if __name__ == "__main__":
    unittest.main()
