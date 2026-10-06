"""install.py orkestrasyonu."""
import argparse
import json
import os
import shlex
from pathlib import Path

from . import answers as ans
from . import claudemd, external, skills, state
from .fsops import Writer
from .model import Deps, StepResult
from .render import Renderer, build_flags, build_values, fwd
from .report import build_report, missing_json
from .settings import apply_settings, dump_settings, load_settings


def _guard(name, fn):
    """Adım hatasını sonuca çevirir; sonraki adım devam eder. Başarıda None döner."""
    try:
        fn()
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        return StepResult(f"core:{name}", False, f"{type(exc).__name__}: {exc}")
    return None


def _read_or_none(path):
    return path.read_bytes() if path.is_file() else None


def _step_claude_md(payload, claude, renderer, writer, files):
    tmpl = (payload / "global" / "CLAUDE.md.tmpl").read_text(encoding="utf-8")
    rendered = renderer.text("global/CLAUDE.md.tmpl", tmpl)
    target = claude / "CLAUDE.md"
    raw = _read_or_none(target)
    merged = claudemd.merge_claude_md(raw.decode("utf-8") if raw is not None else None, rendered)
    writer.write(target, merged.encode("utf-8"))
    files.append("CLAUDE.md")


def _step_blank_template(payload, claude, renderer, writer, files, old_files, name):
    src = payload / "global" / f"{name}.tmpl"
    target = claude / name
    existed = target.is_file()
    writer.write(target, renderer.text(f"global/{name}.tmpl", src.read_text(encoding="utf-8")).encode("utf-8"),
                 only_if_absent=True)
    if not existed or name in old_files:
        files.append(name)


def _step_settings(payload, claude, renderer, writer, files, with_permissions, prev_written, outcome):
    """Ayarları birleştirir; (settingsWritten, korunanlar) değerini outcome listesine ekler."""
    def load(name):
        return json.loads((payload / "settings" / name).read_text(encoding="utf-8"))

    incoming = renderer.json_obj("settings/base.json", load("base.json"))
    if with_permissions:
        perms = renderer.json_obj("settings/permissions.json", load("permissions.json"))
        incoming = {**incoming, **{k: v for k, v in perms.items() if k != "permissions"},
                    "permissions": {**incoming.get("permissions", {}), **perms.get("permissions", {})}}
    target = claude / "settings.json"
    merged, written, kept = apply_settings(load_settings(_read_or_none(target)), incoming, prev_written, with_permissions)
    writer.write(target, dump_settings(merged))
    files.append("settings.json")
    outcome.append((written, kept))


def _step_codex(payload, home, renderer, writer):
    src = payload / "codex" / "config.toml"
    data = renderer.file_bytes("codex/config.toml", src.read_bytes())
    writer.write(home / ".codex" / "config.toml", data, only_if_absent=True)


def _install_files(payload, home, claude, renderer, writer, flags, answers, manifest, old_files, prev_written, outcome):
    results, files = [], []
    # harness'in kurmadığı, kullanıcıya ait skill klasörleri (üzerine yazılırsa raporlanır)
    preexisting = [
        sk["name"] for sk in skills.wanted_skills(manifest, flags)
        if (claude / "skills" / sk["name"]).is_dir()
        and not any(f.startswith(f"skills/{sk['name']}/") for f in old_files)
    ]
    for name, fn in (
        ("claude-md", lambda: _step_claude_md(payload, claude, renderer, writer, files)),
        ("glossary", lambda: _step_blank_template(payload, claude, renderer, writer, files, old_files, "GLOSSARY.md")),
        ("bagimliliklar", lambda: _step_blank_template(payload, claude, renderer, writer, files, old_files, "BAGIMLILIKLAR.md")),
        ("settings", lambda: _step_settings(payload, claude, renderer, writer, files, answers["permissions"], prev_written, outcome)),
    ):
        results.append(_guard(name, fn))
    skill_files, installed, skill_results = skills.install_all(manifest, payload, claude, renderer, writer, flags)
    results.extend(skill_results)
    if answers["codex"]:
        results.append(_guard("codex-config", lambda: _step_codex(payload, home, renderer, writer)))
    failed = {r.name.split(":")[-1] for r in skill_results}
    skills.remove_stale(old_files, skill_files, failed, claude, writer)
    replaced = [
        f"replaced your skill {n} (backup at ~/.claude/backups/claude-harness-{writer.stamp}/skills/{n})"
        for n in preexisting if any(a == "updated" and p.startswith(f".claude/skills/{n}/") for a, p in writer.actions)
    ]
    return [r for r in results if r], files + skill_files, installed, replaced


def _notes(manifest, steps):
    names = {s.name for s in steps}
    out = []
    for item in manifest.get("plugins", []):
        if item.get("note") and f"plugin:{item['id']}" in names:
            out.append(f"{item['id']}: {item['note']}")
    for item in manifest.get("tools", []):
        if item.get("note") and f"pip:{item.get('package')}" in names:
            out.append(f"{item['package']}: {item['note']}")
    return out


def run_install(repo, manifest, answers, home, args, deps):
    payload, claude = repo / "payload", home / ".claude"
    stamp = deps.now().strftime("%Y%m%d-%H%M%S")
    writer = Writer(home, stamp, dry_run=args.dry_run)
    values = build_values(answers, fwd(home), deps.windows)
    flags = build_flags(answers)
    renderer = Renderer(values, flags)
    old = state.read_state(claude)
    old_files = [f for f in old.get("files", []) if isinstance(f, str)]
    warnings = state.verify_manifest(payload)

    prev_written = old.get("settingsWritten") if isinstance(old.get("settingsWritten"), dict) else {}
    outcome = []
    core, files, installed, replaced = _install_files(
        payload, home, claude, renderer, writer, flags, answers, manifest, old_files, prev_written, outcome)
    settings_written, settings_kept = outcome[0] if outcome else (prev_written, list(old.get("settingsKept", [])))
    warnings = warnings + replaced
    old_answers = old.get("answers") if isinstance(old.get("answers"), dict) else {}
    if old_answers.get("codex") is True and not answers["codex"] and (home / ".codex" / "config.toml").is_file():
        warnings.append("Codex kapatıldı: ~/.codex/config.toml korundu, istemiyorsan elle sil")
    if renderer.stray:
        warnings.append("vault yok ama {{VAULT_PATH}} kullanan dosyalar (boş yazıldı): " + ", ".join(sorted(set(renderer.stray))))

    python_argv = ("py", "-3") if deps.windows else ("python3",)
    skill_dirs = {n: fwd(claude / "skills" / n) for n in installed}
    steps = external.plan_steps(manifest, flags, python_argv, skill_dirs)
    results = list(core)
    if not (args.skip_external or args.dry_run):
        results += external.run_steps(steps, deps)
    planned = [shlex.join(s.argv) for s in steps]

    if not args.dry_run:
        external_results = [r for r in results if not r.name.startswith("core:")]
        new_steps = [r.to_state() for r in results if r.name.startswith("core:")] + [r.to_state() for r in external_results]
        merged = state.merge_steps(old.get("steps", []), new_steps)
        new_state = state.build_state(manifest.get("version", "0.0.0"), deps.now().astimezone().isoformat(timespec="seconds"),
                                      repo, answers, files, merged, args.skip_external,
                                      settings_written, settings_kept)
        state.write_state(claude, new_state)
    return build_report(
        answers=answers, actions=writer.actions, results=results, warnings=warnings,
        skip_external=args.skip_external, dry_run=args.dry_run, planned=planned,
        kept=[f"kept your value for {k}" for k in settings_kept],
        notes=_notes(manifest, steps), python_cmd=" ".join(python_argv),
    ), results


def _confirm(deps):
    try:
        return deps.ask("Kurulum yukarıdaki cevaplarla başlasın mı? [e/H]: ").strip().lower() in ans.YES
    except EOFError:
        return False


def _is_real_home(home, real_home=None):
    real = Path(real_home).resolve() if real_home else Path.home().resolve()
    # iki taraf da çözülür: symlink/junction üzerinden gelen ev dizini yanlış eşleşmesin
    return os.path.normcase(str(Path(home).resolve())) == os.path.normcase(str(real))


def main(argv=None, repo_root=None, deps=None):
    deps = deps or Deps()
    repo = Path(repo_root) if repo_root else Path(__file__).resolve().parents[2]
    args = ans.build_parser().parse_args(argv)
    manifest = json.loads((repo / "harness.json").read_text(encoding="utf-8"))
    home = Path(args.home).expanduser().resolve() if args.home else Path.home()
    previous = state.read_state(home / ".claude").get("answers")
    try:
        answers = ans.collect(args, manifest, deps, previous)
    except ans.MissingAnswers as exc:
        deps.say(missing_json(ans.missing_report(exc.keys, manifest)))
        return 2
    except (OSError, ValueError) as exc:
        deps.say(f"cevaplar okunamadı: {exc}")
        return 2
    if deps.isatty() and not args.yes and not args.dry_run and not _confirm(deps):
        deps.say("Vazgeçildi.")
        return 1
    if not args.skip_external and not _is_real_home(home, deps.real_home):
        # claude plugin, npm -g, pip --user, npx skills -g gerçek profile yazar
        deps.say("Uyarı: --home gerçek ev dizini değil; harici adımlar kapatıldı (--skip-external gibi).")
        args = argparse.Namespace(**{**vars(args), "skip_external": True})
    report, results = run_install(repo, manifest, answers, home, args, deps)
    deps.say(report)
    return 1 if any(not r.ok and not r.skipped for r in results) else 0
