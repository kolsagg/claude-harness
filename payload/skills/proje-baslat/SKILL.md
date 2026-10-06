---
name: proje-baslat
description: "Bootstrap a new code project (or retrofit an existing one) with the from-zero skeleton before any code is written: short CLAUDE.md, notes.md dump, GOALS.md, GitHub Issues for planned work (mattpocock-skills setup), BACKLOG.md, DONE.md, CONSTANTS.md, CONTEXT.md glossary and docs/adr/ decisions (mattpocock-skills domain-modeling format), BAGIMLILIKLAR.md + doktor check, reports/, references/, roles, git + GitHub. Load when the user says 'proje başlat', 'sıfırdan proje', 'yeni proje aç', 'iskelet kur', 'doktor çalıştır', or when a project folder lacks these files."
---

# Project bootstrap (from zero)

Principle: an empty but purposeful skeleton beats a full one. The agent must know WHERE each kind of information goes before the first line of code. Whole procedure takes under five minutes.

Never run this inside the second-brain vault (if you have one). Vault has its own system.

## When NOT to use

One-off short task, single-file script, throwaway experiment, a repo someone else owns. The skeleton pays off only when work spans several sessions.

## Steps

1. **Folder.** Use the current folder or create `~/dev/<name>`. Name is temporary; purpose matters.
2. **Create the files below** with the templates. Do not fill them with content the user did not give. `BAGIMLILIKLAR.md` and `references/` start empty; `docs/adr/` is created with the first decision. They fill on first real need.
3. **Dump session.** Ask the user to walk the product screen by screen (panels, data shown, integrations, auth, docs, profile...). Write raw items to `notes.md`, then shape them into a first architecture sketch in the same file: components, data sources, what is built vs bought, what is deferred to v2. Propose better paths where the user is unsure. Settle the data model here, before code. Mark items the user explicitly excluded from v1. Unanswered points go under `## Open questions` with codes Q1, Q2...
4. **Goals.** Ask for 1-3 goals and the done criterion of each. The user sets the criterion, never the agent. Write to `GOALS.md`.
5. **Language.** Seed `CONTEXT.md` with the domain words the user used in the dump, in the `mattpocock-skills:domain-modeling` format (term, one or two sentence definition, `_Avoid_:` synonyms). From here on that skill keeps it current.
6. **Constants.** Ask for values that never change (chain/RPC, ports, domains, tenant/account names, IDs). Write them to `CONSTANTS.md`. Leave placeholders for unknowns; never invent.
7. **Roles.** One line in CLAUDE.md pointing at the `fable-orchestration` skill. Main model orchestrates; sub-agents write code.
8. **Git.** `git init`, `.gitignore` for the stack, first commit `chore: project skeleton`. Then `gh repo create <owner>/<name> --private --source=. --push`. Owner: personal `{{GITHUB_OWNER}}`, unless an org rule below applies. If unclear, ask once. If `gh` is missing or not authenticated, tell the user the exact command and stop there. Decide here whether large binaries under `references/` are gitignored; never push copyrighted reference material to a public repo. Then run `python ~/.claude/skills/proje-baslat/doktor.py --trust .` (the project is yours, so the session hook may auto-run its registry; see Doctor).
9. **Agent skills setup.** Ask the user to type `/mattpocock-skills:setup-matt-pocock-skills` (user-invoked; you cannot start it). Answers: issue tracker GitHub, default triage labels, single-context. It writes `docs/agents/*.md` and an `## Agent skills` block in CLAUDE.md. If `gh` failed in step 8, choose local markdown instead.
10. **Report back** with the file list and the open questions from steps 3-6.

Retrofit mode (existing project): create only the missing files, do not touch code. Never overwrite an existing `CLAUDE.md`; add a short bridge section pointing at the new files. A project on the older template keeps its `DECISIONS.md` / `SOZLUK.md` as read-only archives (CLAUDE.md says so); terms move to `CONTEXT.md` when next used, new decisions go to `docs/adr/`. An old `TODO.md` stays as an archive; its open items become GitHub issues when next touched. Missing `docs/agents/issue-tracker.md` means step 9 never ran. If `CLAUDE.md` is over ~60 lines, propose which sections move to `docs/` and get confirmation before editing.

## File semantics (the part that must hold across sessions)

- `GOALS.md` — what the project is for. Each goal has a code and a done criterion set by the user.
- GitHub Issues — planned work, not started, written by `mattpocock-skills:to-tickets` / `to-spec` / `wayfinder` per `docs/agents/issue-tracker.md`. Every issue names its goal (`G<n>`) and an observable acceptance criterion.
- `BACKLOG.md` — work that was STARTED and left unfinished. Mandatory: before stopping mid-task, append what was done, what remains, where. Read at session start. Finished item moves to `DONE.md` so BACKLOG stays clean.
- `DONE.md` — completed items. Every line carries evidence (report path, test count, commit) and who reviewed it. A line without evidence is not done.
- `docs/adr/NNNN-slug.md` — decisions, one file each, in the `mattpocock-skills:domain-modeling` ADR format, only for hard-to-reverse, surprising, real-trade-off decisions. The agent writes `Status: proposed`; only the user sets `accepted`. A replaced decision stays, marked `superseded by ADR-NNNN`.
- `CONSTANTS.md` — never-changing values. When unsure about such a value, read here. Never guess.
- `CONTEXT.md` — shared language between the user and the agent, maintained by `mattpocock-skills:domain-modeling`: domain terms only, no implementation detail. Look the user's terms up here first. General technical jargon stays in `~/.claude/GLOSSARY.md`.
- `BAGIMLILIKLAR.md` — dependency registry: things that silently break when something else changes (backup job vs database name, patch vs plugin version, two copies that must match). Each entry has a check command. An entry without a command is only documentation.
- `notes.md` — raw product dump, architecture sketch, open questions. Append, do not rewrite history.
- `reports/` — research WE produced, `YYYY-MM-DD-<topic>.md` (global Research Reports rule).
- `references/` — material from OTHERS (screenshots, competitor examples, external docs and PDFs, API sample responses). Never edited. `references/README.md` indexes each item: file, source URL, date taken, why it is here.
- `CLAUDE.md` — short. Every line is in context every session. Pointers, not prose.

## Doctor

`doktor.py` lives next to this file, one copy for every project; never copy it into a project. It runs each `kontrol:` command of `<root>/BAGIMLILIKLAR.md` through Git Bash from the project root and prints green / red / manual. Exit 0 all green, 1 any red, 2 registry missing, unreadable or empty. An entry is recognized only as a line-start `- <what> -> <depends on>` (the ` -> ` is required; other bullets are prose); a long `kontrol:` may wrap onto indented continuation lines; never put background jobs (`&`) in a check. Tests: `python -B -m unittest test_doktor` in this folder (`-B` keeps `__pycache__` out of the skill, which is backed up into the vault).

```
python ~/.claude/skills/proje-baslat/doktor.py <project-root>
```

It also has one built-in check that needs no registry entry: in a proje-baslat project (root has `CONSTANTS.md` or `notes.md`) it compares the folder with the CURRENT skeleton (every file and folder below present, `CLAUDE.md` pointing at `GOALS.md`, `CONTEXT.md`, `docs/adr/`, `BAGIMLILIKLAR.md`, `references/`). Red `iskelet` means the project was bootstrapped with an older template; the repair is retrofit mode. When you change the templates in this file, update `SKELETON_FILES` / `SKELETON_DIRS` / `CLAUDE_POINTERS` in `doktor.py` in the same change, or the check goes stale.

Session start is automatic: a global SessionStart hook (`doktor_hook.py`, registered in `~/.claude/settings.json`) finds the project by walking up from the session folder, runs the skeleton check live (`doktor.py --iskelet`, milliseconds, no bash), and reads the cached result of the last full run; a missing or 30-minute-old cache starts a hidden background run, so the next session sees fresh results. A red first run is repeated once (cold npx/vitest caches can hit the 30 s timeout). Nothing is injected when all is green. Cache: `%LOCALAPPDATA%/proje-baslat-doktor/`. Trust: the hook runs the full registry (shell commands) in the background ONLY for projects listed in `trusted.txt` there (same format as `ignore.txt`: one absolute path per line, covers everything below it). For an untrusted project it still runs the skeleton check and, if the registry has entries, injects one line saying the registry was not auto-run. Add with `doktor.py --trust <root>`, remove with `doktor.py --untrust <root>`; a manual `doktor.py <root>` always works without trust. Never trust a repo cloned from someone else without the user's explicit yes (its registry is arbitrary shell). Trust is by path: everything below a trusted folder is trusted too, and a later `git pull` that changes its BAGIMLILIKLAR.md runs the new checks without asking again; do not keep someone else's repo inside a trusted folder. Projects the hook must never flag (client repos, handed-over work) go in `ignore.txt` there, one absolute path per line (covers everything below it, e.g. a factory-runs folder); nothing is written inside those repos. Factory SDK runs load user hooks, so their worktree folder belongs in this list. Tests: `python -B -m unittest test_doktor test_doktor_hook`. Still run the full doctor by hand after any change to infrastructure, config or names, and before claiming such a change done. On red, do the `bozuksa:` action or tell the user; never edit the check to make it green. When you fix something that broke silently, add its entry to the registry in the same change.

Adding entries is the agent's job, not the user's. In the same change that CREATES a coupling, add the entry with a working `kontrol:` command, run the doctor once to prove the check is green, and tell the user in one line. A coupling is any of:
- the same value living in two places (price, URL, version, name, ID, copy of a file)
- a script, job, cron or backup that names a resource (database, bucket, path, branch, domain)
- code reading an env var or secret name that must exist elsewhere (`.env.example`, hosting panel, CI)
- a call to an external endpoint, webhook, form target, DNS record or third-party account
- a local patch to generated, vendored or plugin code that an update will overwrite
- a doc, README step or runbook that describes behaviour the code can change under it
If no command can check it, still add it with `kontrol: elle`. Do not ask the user whether to add; ask only when you cannot tell if two things are coupled. Couplings that live outside the repo (DNS panel, hosting settings, a partner's server) are invisible to you: ask about them once, when deployment or integration first comes up. First live registry: `~/.claude/BAGIMLILIKLAR.md`.

## Templates

`CLAUDE.md`
```markdown
# <Project>

One sentence: what this is, for whom.

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

## Definition of done
Tests with pass criteria set by the user, not by the agent. No tests written merely to pass. Show evidence (test output, diff) before claiming done, and write it on the DONE.md line.
```

`notes.md`
```markdown
# Notes

## Dump (raw, screen by screen)
-

## Architecture sketch (agent shapes the dump)
### Components
### Data: what, from where, stored how
### Build vs buy
### Deferred to v2

## Open questions
- Q1
```

`GOALS.md`
```markdown
# Goals
Done criterion is set by the user. A goal closes when its criterion is met and no open task points at it.

- G1 <one sentence> — bitti ölçütü: <observable criterion>
```

`BACKLOG.md`
```markdown
# Backlog
Started and unfinished. Append before stopping mid-task. Move finished items to DONE.md.

Format:
## <date> <task>
- Done:
- Remaining:
- Where: <files/branch>
```

`DONE.md`
```markdown
# Done
`- <date> #<issue> <task> — kanıt: <report path | test count | commit> — inceleyen: <{{USER_NAME}} | opus-review | ...>`
```

`CONSTANTS.md`
```markdown
# Constants
Never-changing values. Agent reads here instead of guessing.

| Name | Value | Note |
|------|-------|------|
```

`BAGIMLILIKLAR.md`
````markdown
# Bağımlılıklar
Things that break silently when something else changes. Checked by `python ~/.claude/skills/proje-baslat/doktor.py .`
An entry without `kontrol:` is only documentation. Commands run from the project root in Git Bash; exit 0 means healthy.

```
- <what> -> <depends on>
  kontrol: <bash command>
  bozuksa: <what to do when red>
```

## Kayıt
````

`references/README.md`
```markdown
# References
Material from others. Never edited.

| File | Source | Date taken | Why here |
|------|--------|------------|----------|
```

## Do not

- Do not write code during bootstrap.
- Do not bloat CLAUDE.md with rules that belong in a skill or docs.
- Do not create `AGENTS.md` unless a non-Claude agent (Codex etc.) will work in the repo. If you do, first rule in both files: one changes, the other changes.
- Do not open the project inside the vault.
- Do not copy `doktor.py` into projects, and do not pre-fill `BAGIMLILIKLAR.md` with imagined dependencies.
