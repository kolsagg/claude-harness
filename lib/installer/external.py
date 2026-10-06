"""Harici adımlar: plugin, marketplace, harici skill, npm/pip araçları, postInstall.

Hepsi tek bir runner fonksiyonundan geçer; shell kullanılmaz, argv listesidir.
"""
import shlex

from .model import Step, StepResult

AGENT = "claude-code"  # npx skills add -a değeri


def _allowed(item, flags):
    return item.get("requires") is None or item["requires"] in flags


def plan_steps(manifest, flags, python_argv, skill_dirs):
    """Çalıştırılacak adımların sıralı listesi. skill_dirs: {skill adı: kurulu dizin (/ ile)}."""
    steps = []
    for m in manifest.get("marketplaces", []):
        steps.append(Step(f"marketplace:{m['name']}", ("claude", "plugin", "marketplace", "add", m["repo"]), "claude"))
    for p in manifest.get("plugins", []):
        if _allowed(p, flags):
            steps.append(Step(f"plugin:{p['id']}", ("claude", "plugin", "install", p["id"]), "claude", note=p.get("note", "")))
    for s in manifest.get("externalSkills", []):
        if _allowed(s, flags):
            argv = ("npx", "--yes", "skills", "add", s["source"], "--skill", s["skill"], "-g", "-y", "-a", AGENT)
            steps.append(Step(f"skill:{s['source']}#{s['skill']}", argv))
    for t in manifest.get("tools", []):
        if not _allowed(t, flags):
            continue
        if t["kind"] == "npm":
            steps.append(Step(f"npm:{t['package']}", ("npm", "install", "-g", t["package"]), note=t.get("note", "")))
        elif t["kind"] == "pip":
            name = f"pip:{t['package']}"
            argv = (*python_argv, "-m", "pip", "install", "--user", t["package"])
            steps.append(Step(name, argv, note=t.get("note", "")))
            if t.get("then"):
                steps.append(Step(f"pip-then:{t['package']}", tuple(shlex.split(t["then"])), after=name))
    for skill in manifest.get("ownSkills", []):
        if skill.get("postInstall") and skill["name"] in skill_dirs:
            # önce bölünür, sonra doldurulur: boşluklu yol tek argüman kalır
            argv = tuple(a.replace("{{SKILL_DIR}}", skill_dirs[skill["name"]]) for a in shlex.split(skill["postInstall"]))
            steps.append(Step(f"post-install:{skill['name']}", argv, after=None))
    return steps


def _tail(text, limit=300):
    text = (text or "").strip()
    return text[-limit:] if text else "ok"


def run_steps(steps, deps):
    results = []
    done = {}
    for step in steps:
        cmd = shlex.join(step.argv)
        if step.after and not done.get(step.after, False):
            result = StepResult(step.name, False, f"skipped: önceki adım ({step.after}) başarısız", True)
        elif step.needs_cli and not deps.which(step.needs_cli):
            result = StepResult(
                step.name,
                False,
                f"skipped: `{step.needs_cli}` PATH'te yok. Claude Code'u kurup şunu çalıştır: {cmd}",
                True,
            )
        else:
            code, output = deps.runner(list(step.argv))
            result = StepResult(step.name, code == 0, _tail(output) if code == 0 else f"çıkış kodu {code}: {_tail(output)}")
        done[step.name] = result.ok
        results.append(result)
    return results
