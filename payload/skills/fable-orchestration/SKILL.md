---
name: fable-orchestration
description: "Delegation policy for the agent stack: Fable 5.2 runs the main loop (plan, briefs, hard calls, synthesis, plus small jobs it can do in a handful of tool calls) and routes the rest by difficulty. Medium-high difficulty goes to Opus 5.5 with a fairly loose brief; simple-medium goes to Sonnet 5.5 with a tighter brief. GPT-side execution goes to gpt-6.1-sol with a step-by-step brief; second opinions go to gpt-6-astra. Very large data cleanup goes to Haiku 5.5 or gpt-6-luna. Includes the parallel-lane file-ownership rules (DO / DO NOT) and the brief template. Load whenever spawning sub-agents (Agent tool, Workflow agent() calls, codex fleets) or planning any delegation."
---

# Orchestration & delegation policy

Stack (operator decision, 11 Nov 2026; replaces the 9 Nov "orchestrator only"
rule): **main loop = Fable 5.2**, delegate tiers routed by difficulty. The
main loop sizes each job and picks the tier itself; the operator trusts that
call and does not want to be asked per task.

Core law: **the expensive model's tokens buy judgment, not throughput.** The
main loop writes the plan, the briefs, the hard calls and the final
synthesis. Everything else goes to the cheapest tier that can carry it.

Routing table and tier brief shapes adapted from avenoxai/avenoxskills
`fable-orchestration` (MIT, commit ef697fb, 10 Nov 2026). File ownership and
the brief template are ours.

## The routing table

| Work | Goes to | How to call it | Brief style |
|---|---|---|---|
| Architecture, specs, hard judgment, integration, final synthesis | **Main loop** (Fable) | itself | n/a |
| Medium-high difficulty: multi-file implementation, real debugging, research that needs judgment, review and verification | **Opus 5.5** | `model: 'opus'` | Fairly loose: goal, context, constraints, what done looks like |
| Simple-medium: scoped edits, pattern clones, lookups, templated work, straightforward reading and summarizing | **Sonnet 5.5** | `model: 'sonnet'` | A notch tighter: named files, steps, output shape, boundaries |
| GPT-side execution, when the operator asks to send work to GPT | **gpt-6.1-sol** | `codex exec -m gpt-6.1-sol` | Detailed and step by step, nothing left implicit |
| Second opinion, out-of-the-box thinking, an angle the main loop may be missing | **gpt-6-astra** | `codex exec -m gpt-6-astra` | The open question plus the evidence, as to a peer |
| Very large data cleanup: thousands of rows or files, normalizing, deduplicating, classifying, extracting | **Haiku 5.5** or **gpt-6-luna** | `model: 'haiku'` / `codex exec -m gpt-6-luna` | Exact rule set with input and output examples, small batches, spot checks |

## The hard rules

1. **Explicit `model:` on every spawn.** Agent tool, Workflow `agent()` and
   `meta.phases`, and plugin agents too (their frontmatter may carry its own
   model; the `model` parameter overrides it). This covers spawns another
   skill directs without naming a model (graphify, gptpro-handoff,
   `mattpocock-skills:code-review`): the main loop stamps them too. Omitting
   it inherits the main-loop model and silently fans out the most expensive
   tier (2x Opus / 4x Sonnet list price).
2. **The main-loop model is not a sub-agent tier.** Spawn it as a sub-agent
   only when the operator names it for that task, or when a rare
   judgment-heavy piece genuinely fails on Opus. `subagent_type: "fork"`
   always runs on the main loop's model and ignores `model`, so it counts as
   a Fable spawn under this rule.
3. **Route by difficulty, then pick the cheapest tier that can carry it.**
   When unsure between two tiers, take the cheaper one and verify the result;
   escalate one tier on failure rather than starting high.
4. **Claude tiers are the default.** The GPT side is used when the operator
   asks for it, with two standing exceptions: a second opinion on a hard call
   goes to astra, and bulk cleanup may go to luna.
5. **The main loop keeps its own context lean.** Wide reading, file dumps and
   raw data go to a delegate that returns the conclusion; the main loop reads
   what it must judge. Small things (a handful of tool calls, one known file)
   it does itself, since a delegation costs more than it saves there.
6. **A delegate's report is a claim.** Check the diff, the output or a sample
   before reporting it as done.

## Choosing between Sonnet and Opus

**Sonnet 5.5** for:
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
- (c) Review and verification of work that matters. Opus is the usual
  reviewer; a small, low-risk diff may be checked by the main loop itself or
  by Sonnet. Use `mattpocock-skills:code-review` or `/code-review` (plus
  `/security-review` for auth, payments, customer data or secrets), or a
  `general-purpose` agent with `model: 'opus'` and a review brief.
- (d) Synthesis-heavy research where the deliverable is a judgment, not a
  list of facts.

Split mixed jobs: Opus investigates, Sonnet fixes with the findings in its
brief, Opus reviews the diff. Stamp the tier per lane in the plan so
launching is mechanical.

## Parallel lanes: file ownership

Parallel agents must never write to the same file. The 28 Sep 2026 audit
found two agents sharing one scratchpad; one overwrote the other's script.

DO:
- Give every write lane an explicit **OWNS** list (exact paths). OWNS lists of
  parallel lanes are disjoint.
- Put every sibling lane's OWNS into each brief as **DO NOT TOUCH (owned by
  lane X)**.
- In a git repo, launch parallel write lanes with `isolation: "worktree"`;
  an integration lane (Sonnet, or the main loop when it is a small merge)
  merges one lane at a time and runs the tests after each, and the main loop
  accepts or rejects from the output.
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
Read-only lanes drop OWNS / DO NOT TOUCH. Long briefs go in a file; the
prompt points at the file.

### Brief shape per tier

The template is the skeleton for every tier. How tightly to fill it depends
on who reads it.

- **Opus (fairly loose).** State the goal and why it matters, the context it
  cannot discover on its own, the constraints, and what done looks like. Leave
  the route to it. Over-specifying an Opus brief costs tokens and removes the
  judgment you are paying for.
- **Sonnet (a notch tighter).** Name the files or area, list the steps in
  order when order matters, give the output format, and say what not to touch.
  Say when to stop and report instead of improvising. One task per agent. If
  the main loop cannot name the files and lines, research is not finished;
  send a research lane first.
- **gpt-6.1-sol (detailed, complete).** Sol is a soldier: it does exactly
  what the brief says, step by step, with nothing skipped and nothing added.
  That makes the brief the whole quality ceiling. Write numbered steps,
  exact paths and commands, the acceptance check for each step, the edge cases
  and what to do in each, and the things that are out of scope. Anything left
  unsaid will not happen. Do not ask it to "use judgment" on an open design
  question; decide that first, then hand it the decision.
- **gpt-6-astra (peer question).** Give it the problem, the evidence, the
  options you see and where you are unsure, and ask for what you may be
  missing. Do not hand it your conclusion to confirm. Treat the answer as a
  peer review and disagree on evidence. Medium or high effort; `xhigh` or
  `max` only when the question justifies it.
- **Haiku 5.5 / gpt-6-luna (bulk).** One mechanical rule set, stated exactly,
  with two or three input and output examples. Split the data into batches
  small enough that a bad batch is cheap to redo, have each batch write to its
  own output file, and sample the results before merging. Never ask this tier
  to decide what the rules should be.

Name what you do not want in every brief: an unspecified dimension gets the
most generic option.

## Codex lanes

GPT lanes run through `codex exec` (recipe in the `codex-fleet` skill). Pass
the model explicitly on every lane: `-m gpt-6.1-sol` for execution,
`-m gpt-6-astra` for second opinions, `-m gpt-6-luna` for bulk cleanup. The
local `codex-fleet` skill still defaults to astra, so an execution lane
without `-m` lands on the wrong tier. `gpt-6.1-sol` smoke-verified 11 Nov
2026 on codex-cli 0.167.0. Effort: `medium` for routine lanes, `high` for
precision lanes, `xhigh` or `max` only for an explicitly heavy lane. Stamp
the model per lane in the spec so the launch is mechanical and no routing
decision happens at spawn time.

## Exceptions

- If the operator names a model for a scoped task, honor it for that task
  only, then return to this policy.
- The operator can override any of this per session; absent that, this
  policy stands.
