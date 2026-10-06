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

## Definition of done
Tests with pass criteria set by the user, not by the agent. No tests written merely to pass. Show evidence (test output, diff) before claiming done, and write it on the DONE.md line.
