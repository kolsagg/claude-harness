"""settings.json -> payload/settings/base.json ve permissions.json."""
import json
import re

from .textops import apply_replace

OFFICIAL_MARKETPLACE = "claude-plugins-official"
_PY_PREFIX = re.compile(r"^py -3(?=\s|$)")


class UnknownHookError(Exception):
    def __init__(self, commands):
        self.commands = tuple(commands)
        super().__init__("sınıflandırılmamış hook komutları: " + "; ".join(self.commands))


def _map_strings(node, pairs):
    if isinstance(node, str):
        return apply_replace(node, pairs)
    if isinstance(node, list):
        return [_map_strings(v, pairs) for v in node]
    if isinstance(node, dict):
        return {k: _map_strings(v, pairs) for k, v in node.items()}
    return node


def _classify(command, rules):
    for rule in rules:
        if rule["match"] in command:
            return rule["action"]
    return None


def _short(command):
    return command if len(command) <= 80 else command[:77] + "..."


def filter_hooks(hooks, rules):
    """hookRules'a göre hook'ları süz; sınıfsız komut varsa UnknownHookError."""
    unknown = []
    result = {}
    for event, groups in (hooks or {}).items():
        kept_groups = []
        for group in groups:
            kept = []
            for hook in group.get("hooks", []):
                command = hook.get("command")
                if not isinstance(command, str):
                    unknown.append(f"{event}: komutsuz hook {hook.get('type')!r}")
                    continue
                action = _classify(command, rules)
                if action is None:
                    unknown.append(f"{event}: {_short(command)}")
                elif action == "keep":
                    kept.append(hook)
            if kept:
                kept_groups.append({**group, "hooks": kept})
        if kept_groups:
            result[event] = kept_groups
    if unknown:
        raise UnknownHookError(unknown)
    return result


def _python_placeholder(hooks):
    out = {}
    for event, groups in hooks.items():
        out[event] = [
            {
                **g,
                "hooks": [
                    {**h, "command": _PY_PREFIX.sub("{{PYTHON}}", h["command"])}
                    for h in g["hooks"]
                ],
            }
            for g in groups
        ]
    return out


def _marketplaces(harness):
    return {
        m["name"]: {"source": {"source": "github", "repo": m["repo"]}}
        for m in harness.get("marketplaces", [])
        if m["name"] != OFFICIAL_MARKETPLACE
    }


def build_base_settings(live, harness, pairs):
    export = harness["export"]
    base = {k: live[k] for k in export["settingsKeys"] if k in live}
    base["language"] = "{{LANGUAGE}}"
    base = _map_strings(base, pairs)
    hooks = filter_hooks(live.get("hooks"), export["hookRules"])
    hooks = _python_placeholder(_map_strings(hooks, pairs))
    if hooks:
        base["hooks"] = hooks
    base["enabledPlugins"] = {p["id"]: True for p in harness.get("plugins", [])}
    base["extraKnownMarketplaces"] = _marketplaces(harness)
    return base


def build_permissions(live, harness, pairs):
    keys = harness["export"]["permissionKeys"]
    return _map_strings({k: live[k] for k in keys if k in live}, pairs)


def dump_json(data):
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
