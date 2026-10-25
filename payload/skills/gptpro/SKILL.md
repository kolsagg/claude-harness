---
name: gptpro
description: Export a monorepo into review-ready zip bundles for a non-agentic frontier model (GPT Pro on the ChatGPT web UI, or any chat model with file upload) — node_modules-free, secret-free, split by subsystem so a model with no shell and a bounded context can navigate the codebase a part at a time. Use for packaging a repo for external LLM review, audit, or architecture feedback. Pairs with the `gptpro-handoff` workflow skill.
---

# GPTPro Export

Package a monorepo into clean, logically-split zip bundles for review by a
**powerful non-agentic model** — GPT Pro on the ChatGPT web UI, or any chat
model you upload files to.

That model has no shell, no live filesystem, and a bounded context. So we split
by subsystem and strip `node_modules`, build output, binary assets, and secrets
— giving it something it can actually navigate instead of a 400MB tarball it
will choke on.

## Windows: PowerShell only

This machine runs the PowerShell port, `scripts/export.ps1` (Windows PowerShell
5.1, no `zip`/`rsync`/bash needed). Never run a `.sh` script for this skill;
upstream's `export.sh` was removed on purpose. Every command below is
PowerShell. Smoke tests: `powershell -NoProfile -File scripts/export.Tests.ps1`.

`SKILL_DIR` below means this skill's folder: `$HOME\.claude\skills\gptpro`.

## Run it with no config

```powershell
& "$HOME\.claude\skills\gptpro\scripts\export.ps1" -ProjectRoot C:\path\to\repo
```

With no `bundles.conf`, the script autodetects: one bundle per workspace package
(`apps/*`, `packages/*`, `services/*`, `libs/*`), a schema-only `db` bundle from
whatever migrations directory exists, and a `docs` bundle. A single-package repo
gets one `src` bundle instead of the workspace walk.

That gets you a usable split on the first run. A hand-written config gets you a
*good* one — the model navigates by asking "which bundle would this live in", so
a split that matches your architecture is worth writing.

## Configure

Bundles are defined in `bundles.conf`, which overrides autodetect entirely.
The skill is global, so keep the config **per repo** in its gitignored
`gptpro/` folder and pass it with `-BundlesConf`; a `bundles.conf` inside the
skill folder would apply to every repo. Copy the example and edit:

```powershell
New-Item -ItemType Directory -Force C:\path\to\repo\gptpro | Out-Null
Copy-Item "$HOME\.claude\skills\gptpro\bundles.example.conf" C:\path\to\repo\gptpro\bundles.conf
```

Each line declares one bundle. The file is parsed, not executed: only
`define_bundle` lines, single/double quotes, `\` line continuation and `#`
comments are understood; no variables or other shell syntax.

```text
define_bundle <name> "<description>" <source>...
```

Sources are `dir:<path>[:<extra-exclude-glob>]` or `file:<path>[:<subdir>]`,
relative to the repo root, always with forward slashes:

```text
define_bundle core "domain logic — the most important bundle for architecture review" \
  dir:packages/core

define_bundle db "schema architecture only — no rows, no seed data" \
  dir:supabase/migrations \
  file:supabase/config.toml:supabase \
  file:docs/DB_PLAN.md

define_bundle docs "architecture and convention context" \
  dir:docs dir:adrs file:README.md file:AGENTS.md
```

## Run

```powershell
& "$HOME\.claude\skills\gptpro\scripts\export.ps1" `
  -ProjectRoot C:\path\to\repo `
  -BundlesConf C:\path\to\repo\gptpro\bundles.conf `
  -OutputDir $HOME\Desktop\review-bundles `
  -BundlePrefix myproject
```

Exit code `0` = bundles written, `1` = aborted (message on stderr). Each
parameter also reads the environment variable in brackets.

| Parameter (env) | Default | Meaning |
|---|---|---|
| `-ProjectRoot` (`PROJECT_ROOT`) | current directory | repo to export |
| `-OutputDir` (`OUTPUT_DIR`) | `<repo>\gptpro-bundles` | where zips land (upload folder) |
| `-BundlePrefix` (`BUNDLE_PREFIX`) | repo dir name | zip name prefix → `<prefix>-core.zip` |
| `-BundlesConf` (`BUNDLES_CONF`) | `SKILL_DIR\bundles.conf` | bundle definitions; autodetect if absent |
| `-AllowSecrets` (`ALLOW_SECRETS=1`) | off | continues past a hard secret-scan hit |

## What gets excluded

Every bundle drops: `.git`, `node_modules`, `.next`, `.turbo`, `dist`, `build`,
`out`, `coverage`, `.vercel`, `*.tsbuildinfo`, `.env`, `.env.*`, `*.log`,
`.DS_Store`, and binary assets (images, video, fonts).

**Tests are kept on purpose** — they encode contracts and are some of the most
useful review material in the repo.

## Secret scan

After staging and before zipping, every bundle is scanned. Two tiers, because a
one-tier scan on a real repo is *all* false positives and you end up passing
`-AllowSecrets` every run — which is the same as having no scan:

- **HARD** — provider-issued credential shapes: private key headers, `AKIA…`,
  `ghp_…`, `github_pat_…`, `xox…`, `AIza…`, long `sk-…`/`sk-ant-…`, JWTs.
  A hit **aborts the export**, file and line printed. Override with
  `-AllowSecrets` only after reading every hit.
- **SOFT** — generic `secret = "…"` / `password: "…"` assignments. Printed for
  your eyes, never fatal.

Hits under `test/`, `__tests__/`, `fixtures/`, `*.test.*`, or carrying an obvious
placeholder marker (`FAKE`, `EXAMPLE`, `xxxxxxxx`, `env(…)`) are demoted to SOFT
— a secret-handling test suite is *supposed* to contain credential-shaped
strings, and aborting on those trains you to ignore the guard.

## Notes

- **Split by subsystem, not by size.** The model navigates by asking "which
  bundle would this live in" — a split that matches your architecture is worth
  more than evenly-sized zips.
- **Database bundles should be architectural, not data.** Ship the schema map
  and forward-only migrations so the model can see *how the database is
  constructed*; never ship rows or seed data.
- Prior `<prefix>-*.zip` files in the output directory are deleted on each run,
  so re-running gives a clean set with no stale bundles; other zips there stay.
- `file:` must name a file. A folder aborts the export (it would bypass the
  exclusions); use `dir:` for folders. Symlinks and junctions are skipped.
- Nothing is skipped by the secret scan: UTF-16 files are decoded and binary
  files are read byte-wise, so a key inside them still aborts the export.
- Keep one bundle for docs/ADRs/conventions. Models reason much better about a
  codebase when they can read why it's shaped the way it is.

Pairs with **`gptpro-handoff`** — the workflow skill for authoring the prompt,
receiving the report, and verifying findings before implementing.
