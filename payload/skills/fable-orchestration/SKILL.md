---
name: fable-orchestration
description: "Delegation policy for the Claude agent stack: Fable 5.2 runs the main loop as orchestrator only (judgment, specs, synthesis) and every piece of work goes to a sub-agent; Sonnet 5.5 sub-agents do most context gathering and code writing; Opus 5.5 sub-agents take important changes, architectural or risky work, and every review round. Includes the parallel-lane file-ownership rules (DO / DO NOT). Load whenever spawning sub-agents (Agent tool, Workflow agent() calls) or planning any delegation."
---

# Orchestration & delegation policy

Stack (operator decision, 9 Nov 2026): **main loop = Fable 5.2, orchestrator
only**. Delegate tiers: **Sonnet 5.5** (default) and **Opus 5.5** (important /
careful work and reviews). The main loop sizes each job and picks the tier
itself; the operator trusts that call and does not want to be asked per task.

Fable orchestrates and Sonnet / Opus execute, in every skill.

## The hard rules

1. **Explicit `model:` on every spawn.** Agent tool, Workflow `agent()` and
   `meta.phases`, and plugin agents too (their frontmatter may carry its own
   model; the `model` parameter overrides it). Only `'sonnet'` or `'opus'`.
   This covers spawns another skill directs without naming a model (graphify,
   gptpro-handoff, `mattpocock-skills:code-review`): the main loop stamps them
   too. Omitting it makes a Fable sub-agent at 2x Opus / 4x Sonnet list price.
   `subagent_type: "fork"` is off limits: a fork always runs on the main
   loop's model and ignores `model`.
2. **Two delegate tiers, no others.** No Haiku, no Fable.
3. **The main loop orchestrates.** Architecture, specs, contracts, briefs,
   conflict resolution, final synthesis, judgment calls. It verifies every
   delegated result from the evidence the agent returns (diff, test output)
   before claiming done.
4. **All execution is delegated, trivial work too.** A sweep, a lookup, a
   two-line edit, a merge, a test run: a Sonnet or Opus agent does it, with a
   brief as short as the job. The main loop touches only the conversation
   with the operator, the few reads it needs to write a brief or check a
   result, the written outputs of rule 3 (spec, final synthesis or report),
   and its own session notes (memory, companion files).

## Choosing the tier (main loop decides)

**Sonnet 5.5 is the default** for:
- Context gathering: file and code sweeps, grep/mapping, reading docs and
  reports, collecting facts for a spec.
- Code writing against a written spec: features, tests, refactors,
  migrations, mechanical multi-file edits, doc/config edits.

**Opus 5.5** when any of these holds:
- (a) The spec cannot be made complete: open-ended "investigate and fix",
  ambiguous root cause, a wrong diagnosis would be expensive.
- (b) The change is important or needs care: architectural decisions, a
  cross-module contract, auth / payments / customer data / secrets,
  data migrations on live data, anything hard to reverse.
- (c) Review and gate rounds, always, whatever the size of the diff. Never
  Sonnet reviewing Sonnet. Use `mattpocock-skills:code-review` or
  `/code-review` (plus `/security-review` for auth, payments, customer data
  or secrets), or a `general-purpose` agent with `model: 'opus'` and a
  review brief.
- (d) Synthesis-heavy research where the deliverable is a judgment, not a
  list of facts.

Split mixed jobs: Opus investigates, Sonnet fixes with the findings in its
brief, Opus reviews the diff. When in doubt between the two for a write lane,
pick Sonnet with a tighter spec plus an Opus review, not Opus alone.

Stamp the tier per lane in the plan so launching is mechanical.

## Parallel lanes: file ownership

Parallel agents must never write to the same file. The 28 Sep 2026 audit
found two agents sharing one scratchpad; one overwrote the other's script.

DO:
- Give every write lane an explicit **OWNS** list (exact paths). OWNS lists of
  parallel lanes are disjoint.
- Put every sibling lane's OWNS into each brief as **DO NOT TOUCH (owned by
  lane X)**.
- In a git repo, launch parallel write lanes with `isolation: "worktree"`;
  a Sonnet integration lane merges one lane at a time and runs the tests
  after each, and the main loop accepts or rejects from its output.
- **Commit often inside the lane** (operator decision, 29 Sep 2026) so work
  is never lost to a crash, a limit hit or a killed agent: one small commit
  per finished step (test green, file done), on the lane's own branch /
  worktree. Stage explicit OWNS paths only (`git add <path>`, never `-A` or
  `.`). Conventional commit message. The integration lane merges the branch
  after the main loop's acceptance check. A lone lane in the main tree may commit its
  OWNS files the same way.
- Outside git, give each lane its own subfolder: `<scratchpad>/<lane-name>/`
  for temp files, scripts and output.
- Declare shared files (barrels, route tables, config, lockfiles,
  `package.json`) owned by exactly one lane, or by the integration lane after
  all other lanes finish.
- Run read-only lanes (research, review) in parallel freely; they own nothing.
- Tell lanes to report a sibling's edit they notice and leave it intact.

DO NOT:
- Run two lanes that touch the same file at the same time. Serialize them,
  or give the overlapping part to one lane.
- Let a lane push, merge into main, rewrite history (amend/rebase/reset
  --hard), run the repo-wide gate, or install/upgrade dependencies unless
  the brief says so.
- Let two parallel lanes commit in the same checkout; parallel committing
  lanes need their own worktree.
- Let a lane "fix" something outside its OWNS list; it reports it instead.
- Reuse one scratchpad path, log file or port across lanes.
- Launch a write lane without an OWNS list.

## The brief (context contract)

Every agent starts with zero context. The brief carries everything. Write it in English (global Language rule); ask for the return in English too, and translate for {{USER_NAME}} yourself:

```
Goal: [one sentence in outcome language: what must be true for this to count as done]
Inputs: [raw material pasted as-is: file:line refs, error output, spec text; never a paraphrase]
OWNS: [exact paths this lane may write]
DO NOT TOUCH: [sibling-owned paths, with owner lane]
Limits:
- [do-not-use: libraries, commands]
- Commit: one small commit per finished step, OWNS paths only; no push/merge.
- [never: the unwanted outcomes, named explicitly]
Measure: [how we will know it is good; a test, a count, a command that must pass]
Freedom: [what the agent decides on its own]
Return: [diff summary, file paths, test output]
If you see a mistake in these instructions, say so before applying it.
```

The last line is mandatory in every write brief: a literal executor
implements the spec's mistakes too; that line lets it stop and flag them.
Read-only lanes drop OWNS / DO NOT TOUCH.

### Tone by tier

- **Sonnet:** full order + full boundary. Say exactly what, name exactly what
  not, leave nothing to taste. If the main loop cannot name the files and
  lines, research is not finished; send a research lane first.
- **Opus:** goal + boundaries + freedom. State the understanding or verdict
  needed back; do not script the search.

Name what you do not want in every brief: an unspecified dimension gets the
most generic option.

## Exceptions

- If the operator names a model for a scoped task, honor it for that task
  only, then return to this policy.
- The operator can override any of this per session; absent that, this
  policy stands.
