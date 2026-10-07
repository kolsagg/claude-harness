# claude-harness

Bir makinedeki Claude Code kurulumunu (global CLAUDE.md, skill'ler, plugin'ler, marketplace'ler, ayarlar; isteğe bağlı Codex / Orca / vault parçaları) public bir repodan başka bir makineye ya da cloud ortamına tek komutla kuran kit.

## Where things live
- Shared language with the user: CONTEXT.md (mattpocock-skills:domain-modeling). Look up the user's terms there first.
- Goals and done criteria: GOALS.md
- Product dump, architecture sketch, open questions: notes.md
- Never-changing values: CONSTANTS.md (read before assuming any address, port, name, ID)
- Planned work: GitHub Issues (docs/agents/issue-tracker.md) · Unfinished work: BACKLOG.md (mandatory on interruption) · Finished, with evidence: DONE.md
- Decisions: docs/adr/ (agent writes `proposed`, only the user sets `accepted`)
- Silent-break dependencies: BAGIMLILIKLAR.md, checked by `python ~/.claude/skills/proje-baslat/doktor.py .` Whenever a change couples two things (same value in two places, a job naming a resource, an env var, an external endpoint, a patch an update will overwrite), add the entry with its check command in that same change, unasked.
- Our research: reports/ · Others' material: references/
- Roles: main model orchestrates, sub-agents execute (skill: fable-orchestration)

## Repo-specific rules
- Public repo. Nothing personal or secret is committed: `export.py` scrub must pass before every push.
- `payload/global/CLAUDE.md.tmpl` is the SHIPPED global file; this file is the repo's own instructions. Do not confuse them.
- Installing on another machine: read INSTALL.md.
- Never run `install.py` for real on the source machine: it replaces the live skills with the scrubbed payload (private blocks and brand content gone). Here only `export.py` runs; use `--dry-run` or a sandbox `--home` to test.

## Release flow (every harness update)
1. Bump `version` in `harness.json` (semver: new skill/plugin/feature = minor, fix = patch).
2. `py -3 export.py`: scrub must report 0 findings.
3. Commit with the version in the message, e.g. `feat: <ne değişti> (v0.2.0)`, then `git push`.
4. Annotated tag on that commit and push it: `git tag -a v0.2.0 -m "v0.2.0 — <özet>"` then `git push origin v0.2.0`.
5. Verify: `git ls-remote --tags origin` lists the new tag. Tags so far: v0.1.0 (acb8f13).

## Definition of done
Tests with pass criteria set by the user, not by the agent. No tests written merely to pass. Show evidence (test output, diff) before claiming done, and write it on the DONE.md line.
