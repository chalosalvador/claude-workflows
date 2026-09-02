# Fanning work out with the Workflow tool

Two places in this plugin do N independent things one after another. This file holds the
Workflow-tool layer for each, and the boundaries that stop either from becoming a second,
divergent implementation of the skill it accelerates.

| Layer | What fans out | Ceiling |
|---|---|---|
| **A · triage deep pass** | up to 25 issues, judged in batches | the § 3 cap |
| **B · autopilot** | up to 2 issues, planned/built/reviewed/PR'd | the § 2 cap of 2 |

🚨 **Both are optimization layers, never replacements.** The serial path in each skill is
the contract; these are faster ways to reach the same outcome. If the Workflow tool is
absent from the session, or the set is small, or anything here fails — run the skill as
written. Its absence is a normal state, not an error, and not worth a line in the report.

Everything below is written against the `workflow-authoring` reference, which is the
authority on this API. Read it before changing a script here rather than pattern-matching
from these examples.

## The two boundaries differ — do not copy one into the other

This is the mistake to make. Both layers fan out, and the rule about what an agent may
write is **not the same in each**:

| | A · triage | B · autopilot |
|---|---|---|
| Agents may write to a worktree | no — nothing to build | **yes**, their own, one each |
| Agents may open a PR | no | **yes**, one each |
| Agents may write labels, board fields, issue comments | **no** | **no** |
| Who owns the terminal state of an issue | the session | the session |

The constant across both is the last row. What differs is that triage's agents produce
*judgments* and autopilot's produce *artifacts* — a branch and a PR, isolated per issue by
construction. Neither produces a state transition on the issue itself.

---

# A · Triage — the deep pass

The deep pass ([`../skills/triage/SKILL.md`](../skills/triage/SKILL.md) § 3–4) reads up
to 25 issues, opens the files each one names, and judges five attributes per issue. In
one session that is serial — 25 issues read one after another, by the pass that has to
open files to do its job. The judgments are independent, so they can run in parallel.

### The seam

Triage already splits along the line this needs: § 3–4 is analysis, § 5 is writes.

**Every agent in the fan-out is read-only; the writes never leave the main session.**
That is not tidiness, it is three separate requirements that a distributed writer
cannot meet:

- **§ 5 orders its writes**, and `triaged` goes on last so a half-finished run is
  re-triaged cleanly next time rather than silently lost. N agents writing
  independently cannot honour a global ordering rule.
- **§ 5's label-splitting trap** auto-creates any label that does not exist. One
  careless agent writes junk labels across the repo. One writer means one place to get
  it right ([`shell-traps.md`](shell-traps.md)).
- **§ 5's read-back** is a single post-write board pull with backoff, against
  eventually-consistent Projects v2 writes. There is nothing to distribute; it has to
  happen once, after everything.

"Only fill blanks" (§ 3c) and "don't strip a category a human already set" (§ 3a) then
cost nothing: the agent returns **its verdict plus the state it observed**, and the
session applies the write rules. The agent never needs to know them.

### When it pays

Three conditions, all of them:

| Condition | Why |
|---|---|
| The Workflow tool is in this session's toolset | It is not everywhere. Its absence is a normal state, not an error. |
| The untriaged set is **10 or more** | Each agent re-reads repo context it does not share with the others. Below ~10 issues that fixed overhead is most of the run. |
| Nothing about the run is already degraded | A run that fell back to a partial board fetch should stay simple. |

⚠️ **The 10 is a chosen threshold, not a measured one.** Nobody has priced the
crossover here. If you measure it, replace the number and mark it MEASURED.

**Dry run works unchanged** — the fan-out is read-only by construction, so a dry run is
the same script with § 5 skipped. That is strictly better than the serial path, where
dry-run correctness depends on the session remembering not to write.

**Authorization.** The Workflow tool needs explicit opt-in, and a skill instructing the
session to call it *is* that opt-in. That is why the call is named in the triage skill
rather than left to judgment.

### Batch — do not go one agent per issue

**5 issues per agent, at most 5 agents.** That is the existing cap of 25 with no change
to it, and it stays inside the default workflow size guideline.

One agent per issue would spawn 25 agents that each clone context and read the same
files — the duplicated-research waste priced in
[`../shared/execution.md`](../shared/execution.md) § 3.1, reintroduced at a new step.
Batching amortizes the repo exploration across the batch, and dupe detection *within* a
batch comes free.

⚠️ **The cap stays 25 deliberately.** Fan-out changes what the cap costs, not what it
protects — the board still has to absorb the writes, and a human still has to read the
receipt. Raising it is a separate decision with its own measurement.

Cross-repo duplicates (§ 3d) are the one judgment that is not issue-local: it compares
against **all** open issues in **every** repo. Pass the full open-issue index — number,
repo, title, labels for ~300 issues is small — into every batch prompt, and reconcile
the results in JS afterwards.

### The script

Written against the `workflow-authoring` reference, which is the authority on this API —
read it before changing the script, rather than pattern-matching from here.

⚠️ **No `model` or `effort` override here, deliberately.** The tier table in
[`../shared/execution.md`](../shared/execution.md) § 3.1 keys off the issue's effort
label — and this is the pass that *assigns* that label, so the rule has nothing to key
off. Inheriting the session's model is the honest default until someone measures a
cheaper tier against real verdicts. (A workflow script *can* set both per call, unlike
an Agent-tool spawn; that asymmetry is § 3.1's, and it is not a reason to use it blind.)

```javascript
export const meta = {
  name: 'triage-deep-pass',
  description: 'Categorize, size, gate and dupe-check untriaged issues in parallel batches',
  phases: [{ title: 'Deep pass', detail: 'One agent per batch of up to 5 issues' }],
}

const ISSUE_VERDICT = {
  type: 'object',
  required: ['verdicts'],
  properties: {
    verdicts: {
      type: 'array',
      items: {
        type: 'object',
        required: ['number', 'repo', 'category', 'effort', 'priority', 'gate'],
        properties: {
          number: { type: 'integer' },
          repo:   { type: 'string' },                       // owner/repo, always
          category: { enum: ['bug', 'enhancement', 'improvement', 'question'] },
          effort:   { enum: ['effort:easy', 'effort:medium', 'effort:hard'] },
          priority: { enum: ['P0', 'P1', 'P2', 'P3'] },
          // Observed state, so the caller can apply "only fill blanks" itself:
          observedCategory: { type: ['string', 'null'] },
          observedPriority: { type: ['string', 'null'] },
          // Gate EVIDENCE, not a bare boolean — see "What the session still does".
          gate: {
            type: 'object',
            required: ['passes', 'files', 'disqualifiers'],
            properties: {
              passes:        { type: 'boolean' },
              files:         { type: 'array', items: { type: 'string' } },
              testPattern:   { type: ['string', 'null'] },
              disqualifiers: { type: 'array', items: { type: 'string' } },
            },
          },
          dupeOf:        { type: ['string', 'null'] },      // "owner/repo#N"
          dupeReason:    { type: ['string', 'null'] },
          dupeConfident: { type: 'boolean' },
          notes: { type: 'string' },                        // disagreements go here
        },
      },
    },
  },
}

const results = await parallel(
  args.batches.map(b => () => agent(
    `Deep-pass triage. Judge ONLY the issues listed below.

     Read ${args.skillPath} sections 3a-3d and 4 and apply them verbatim. They are the
     taxonomy of record; do not work from memory of them, and do not restate them back.

     You are READ-ONLY. Write nothing to GitHub — no labels, no comments, no board
     fields. Return verdicts; the caller writes them.

     Where a category or priority is already set, report it in observed* and still give
     your own verdict. Disagreement is data, not something to suppress.

     For section 4, return the EVIDENCE — the files you can name, the test pattern you
     found, every disqualifier you checked — not just passes true/false.

     Issues to judge: ${JSON.stringify(b.issues)}
     All open issues, for section 3d duplicate comparison: ${JSON.stringify(args.index)}`,
    { label: `triage:${b.label}`, phase: 'Deep pass', schema: ISSUE_VERDICT }
  ))
)

const verdicts = results.flatMap(r => r?.verdicts ?? [])
const key = v => `${v.repo}#${v.number}`

// Unordered dupe pairs. Direction is NOT decided here: the session holds createdAt
// and picks the canonical issue. Self-references and A->B/B->A collapse away.
const seen = new Set()
const dupes = verdicts
  .filter(v => v.dupeOf && v.dupeConfident && v.dupeOf !== key(v))
  .map(v => ({ a: key(v), b: v.dupeOf, why: v.dupeReason }))
  .filter(p => { const k = [p.a, p.b].sort().join('~'); return !seen.has(k) && seen.add(k) })

// An agent that drops an issue must be visible. Silence is not success.
const got = new Set(verdicts.map(key))
const missing = args.batches
  .flatMap(b => b.issues)
  .map(i => `${i.repo}#${i.number}`)
  .filter(k => !got.has(k))

if (missing.length) log(`NOT TRIAGED, no verdict returned: ${missing.join(', ')}`)

return { verdicts, dupes, missing }
```

🚨 **`missing` is the load-bearing return value.** An agent that returns four verdicts
for five issues has silently dropped one, and a receipt counted off `verdicts.length`
would never show it. Any issue in `missing` is **not triaged** — leave it untriaged for
the next run and say so on the board-health line. Never let it reach § 5 with a guessed
verdict. It is `log()`ged as well as returned, because a bounded run that does not
announce what it dropped reads as a run that covered everything.

### Building the batches

The session already has both inputs from § 1: `$SCRATCH/open.json` and `$BOARD_JSON`.
Untriaged, newest first, in fives:

```sh
jq -s --arg skill "<abs path to triage/SKILL.md>" '{
  skillPath: $skill,
  index: [ .[] | {repo, number, title, labels: [.labels[].name]} ],
  batches: [ .
    | map(select((.labels | map(.name) | index("triaged")) | not))
    | sort_by(.createdAt) | reverse | .[0:25]
    | to_entries | group_by(.key / 5 | floor)
    | .[] | { label: (.[0].value.repo + "#" + (.[0].value.number|tostring)),
              issues: [ .[].value | {repo, number, title, body, url,
                                     labels: [.labels[].name]} ] } ]
}' "$SCRATCH/open.json" > "$SCRATCH/args.json"
```

⚠️ **`-s` slurps a STREAM into one array, so the issues are `.`, not `.[0]`.** § 1 writes
`open.json` as newline-delimited objects — one per issue, not a JSON array — and the
first draft of this block read `.[0]` as if slurping produced a list of pages. MEASURED
on a 30-issue fixture: it dies with `Cannot index string with string "repo"`. A loud
failure, unusually — but the same off-by-one silently returns one issue's worth of work
if the stream ever becomes a single array.

MEASURED on that fixture, corrected: 30 issues in, 10 carrying `triaged`, out come 4
batches of 5 — newest first, no `triaged` issue leaked in. On a 28-untriaged fixture it
caps at 5 batches of 5 and leaves the oldest 3 for the next run, which is § 1's
newest-25 rule with the tail reported on the board-health line.

Pass that object as the Workflow tool's `args` — **as a JSON value, not a
JSON-encoded string**, or `args.batches.map` fails in the script.

### What the session still does

Everything that is not the per-issue judgment:

1. **The integrity pass (§ 2), first and serially.** Uncapped, mechanical, no judgment
   — and it is the guarantee that has to hold on a day the deep pass fails entirely.
   It never goes in the workflow.
2. **Adjudicate the gate.** Take `gate.passes` as a recommendation and read the
   evidence. § 4 calls the label a promise, and "when in doubt, don't apply it" is a
   call this plugin makes with something in front of it — the files the agent could
   name, the pattern it found. An empty `files` list with `passes: true` is a rejection.
3. **Orient the dupe pairs** by `createdAt` and apply § 3d's own rules about what is a
   dupe and what is a legitimate per-repo tracking issue.
4. **Write § 5 in § 5's order**, read back, print the receipt.

The shape is the one [`review-process.md`](review-process.md) already uses for reviewer
findings: agents surface, the session adjudicates and acts.

---

# B · Autopilot — two issues at once

[`../skills/autopilot/SKILL.md`](../skills/autopilot/SKILL.md) § 2 takes up to two
candidates and works them one after the other, because it has no choice: the moment an
issue is handed to a subagent, that subagent cannot spawn its own review lenses — spawns
do not nest ([`parallel-agents.md`](parallel-agents.md)). A workflow script does the
nesting at the script level, so both issues can run their full plan → build → review →
PR chain concurrently, each in its own worktree.

That is the entire case for this layer. It is a wall-clock win on a run nobody is
watching, with a ceiling of two. Everything below exists to make it not cost more than
it buys.

### The boundary

**Agents produce the branch and the PR; every state transition on the issue and the board
stays with the session.**

Autopilot's agents necessarily write — they commit, push and open a PR. That is safe
because each writes only inside its own worktree and its own branch, which § 5 already
isolates. What does *not* move into the workflow is the issue's state: the `agent-wip`
claim, the board card, the labels, the `agent-blocked` handback, the plan comment.

The reason is not tidiness. **An agent that labels its own issue `agent-blocked` and then
dies leaves the session unable to tell "handed back" from "crashed".** Both look like an
issue with a label and no PR. The session has to write the § 13 report and the § Handing
it back record, and it can only write them honestly if it owns those transitions — the
same reason `missing` exists in layer A.

### What goes in, and what cannot

| Autopilot step | Where it runs | Why |
|---|---|---|
| § 1 backpressure, § 2 select, § 3 re-verify, § 4 claim | **session**, before | Cheap, shared, and all board/issue writes. § 3 also writes `$ISSUE_MD`, which the workflow needs as input. |
| § 5 worktrees | **session**, before, **serially** | See the concurrency rules below. Agents never create one. |
| § 6 plan · § 7 implement · § 8 gate · § 9 review · § 10 PR | **workflow**, per issue | The independent chain. |
| § 11 babysit to green | **session**, after | Two reasons, below. |
| § 12 bookkeeping, § 13 report, § Handing it back | **session**, after | The state transitions. |

🚨 **§ 11 cannot go in the workflow, and would be worse there anyway.**
`Date.now()` and `new Date()` throw inside a workflow script — they would break resume —
so **the 45-minute cap cannot be enforced there at all**. And an agent babysitting is an
agent polling for up to 45 minutes, where the session can arm one `Monitor` and sleep.

That constraint turns into this layer's second win: the session comes back holding *both*
PRs and babysits them **together under one cap**, instead of 45 minutes for the first and
another 45 for the second.

### The shape

`pipeline()`, not `parallel()` — issue #2's review starts the moment its build finishes,
whatever issue #1 is doing. There is one deliberate barrier inside the ship stage: the
adjudicator needs every lens's findings together, which is what a barrier is for.

Per issue: 1 planner + 1 builder + L lenses + 1 shipper, plus 2 more only when
adjudication added new logic. With the plan naming three lenses that is 6 agents per
issue and **12 for a full run** — inside the default workflow size guideline, with room
for one delta path. If both plans name more lenses than that allows, run one issue
through the workflow and leave the other for the next run; do not silently drop lenses to
fit a budget.

**The planner gets no `schema`.** Its output shape is an allowlist it enforces itself, and
forcing a structured return would fight it. Its text is passed downstream verbatim — the
handoff [`../shared/execution.md`](../shared/execution.md) § 3.1 asks for — and the
builder is the one component that reads it, so § 6's late gate is judged once.

One incidental gain: a workflow `agent()` call takes `effort` per call, so the
implementation step's effort is settable here — the serial path cannot pin it, which
§ Effort in the skill says outright. Set it deliberately or not at all; do not raise it
to paper over an issue that turned out bigger than `easy`, which is a handback.

**New logic gets a draft PR, not a ready one.** § 9 requires a delta re-review when
adjudication introduced a branch, gate or code path, run as the lens that raised the
finding. The shipper cannot spawn that lens, so it opens the PR **as a draft**, says which
lens raised it, and the script runs the lens and a short finalize pass that flips the PR
to ready. A ready-for-review PR therefore never contains logic no lens has seen.

### The script

```javascript
export const meta = {
  name: 'autopilot-issues',
  description: 'Plan, build, review and open a PR for up to 2 agent-ready issues, one worktree each',
  phases: [
    { title: 'Plan',   detail: 'issue-planner, read-only, one per issue' },
    { title: 'Build',  detail: 'spec change, code, and the full validation gate' },
    { title: 'Review', detail: 'diff-reviewer lenses named by the plan' },
    { title: 'Ship',   detail: 'adjudicate, archive, commit, push, open the PR' },
  ],
}

const OUTCOME = {          // every stage answers this, so a handback is data, not a throw
  outcome: { enum: ['ok', 'handback'] },
  stage:   { type: 'string' },
  reason:  { type: 'string' },                    // one line, goes on the issue verbatim
}

const BUILD = { type: 'object', required: ['outcome'], properties: { ...OUTCOME,
  lenses:       { type: 'array', items: { type: 'string' } },   // from the plan's REVIEW LENSES
  handoff:      { type: 'string' },
  filesTouched: { type: 'array', items: { type: 'string' } },
  gateResult:   { type: 'string' },
  specChange:   { type: ['string', 'null'] },
  deploys:      { type: 'boolean' },
}}

const FINDINGS = { type: 'object', required: ['findings'], properties: {
  findings: { type: 'array', items: { type: 'object',
    required: ['lens', 'claim'],
    properties: { lens: {type:'string'}, claim: {type:'string'}, file: {type:'string'},
                  line: {type:['integer','null']}, why: {type:'string'} } } },
}}

const SHIP = { type: 'object', required: ['outcome'], properties: { ...OUTCOME,
  prNumber:    { type: ['integer', 'null'] },
  prUrl:       { type: ['string', 'null'] },
  isDraft:     { type: 'boolean' },
  newLogic:    { type: 'boolean' },      // did adjudication add a branch/gate/code path?
  raisingLens: { type: ['string', 'null'] },
  rejected:    { type: 'array', items: { type: 'object',
                  properties: { claim: {type:'string'}, reason: {type:'string'} } } },
  reviewerRequested: { type: ['string', 'null'] },   // READ BACK, never the exit code
}}

const rules = w => `Worktree: ${w} — cd there for EVERY command; a drifted cwd runs the
  main checkout. Never touch another issue's worktree. Stage explicit paths, never
  git add -A. Never stash: the stack is shared with every other worktree. Do not merge
  or queue a merge in any form. All commits GPG-signed; if signing fails, stop and hand
  back rather than pushing unsigned.`

const dead = (stage, what) => ({ outcome: 'handback', stage, reason: `${what} returned nothing` })

// ---- stage 1: plan, then build -------------------------------------------------
const build = async (issue) => {
  const plan = await agent(
    `Plan issue #${issue.number} in ${issue.repo}.
     Tier: ${issue.tier}
     Issue body + comments: ${issue.issueMd}
     Repo spec flow: ${issue.specFlow}
     Integration branch: ${issue.base}. Merging it ${issue.deployNote}.
     Gate: ${issue.gate}
     Worktree (READ-ONLY, do not edit): ${issue.worktree}`,
    { agentType: 'gh-issue-flow:issue-planner', label: `plan:#${issue.number}`, phase: 'Plan' }
  )
  if (!plan) return { issue, ...dead('Plan', 'the planner') }

  const built = await agent(
    `Implement issue #${issue.number} per autopilot SKILL.md sections 6 to 8, in order:
     the spec change first, then the code, then the full validation gate until green.
     ${rules(issue.worktree)}

     THE PLAN — treat as established; do not re-fetch what it already answers:
     ${plan}

     FIRST, judge the plan as section 6's late gate. If it names infrastructure, a
     migration, a schema change, secrets, or an unanswered product question — or cannot
     name the files, the capability, or a defensible skip_specs reason — return
     outcome handback with that reason and build nothing.

     Then implement. Stay inside the issue's scope; section 7's fold-in threshold decides
     anything else you notice. Any red in the gate that is not section 2.1's two known
     classes is a handback, not a judgment call. Add or extend tests and mutation-check
     them. Do NOT commit, push, or open a PR — a later stage does that.

     Return the plan's REVIEW LENSES in lenses, and a handoff a fresh reviewer can use.`,
    { label: `build:#${issue.number}`, phase: 'Build', schema: BUILD }
  )
  return built ? { issue, plan, ...built } : { issue, plan, ...dead('Build', 'the builder') }
}

// ---- stage 2: review, adjudicate, ship ----------------------------------------
const ship = async (built, issue) => {
  if (built.outcome !== 'ok') return built

  const lensPrompt = lens => `Review the working diff in ${issue.worktree} through the
    ${lens} lens ONLY, for issue #${issue.number}. Read-only: report, never fix.
    Handoff from the implementer: ${built.handoff}
    Files touched: ${built.filesTouched.join(', ')}
    Gate result: ${built.gateResult}`

  // Barrier is correct here: the adjudicator weighs every lens's findings together.
  const findings = (await parallel(built.lenses.map(lens => () => agent(lensPrompt(lens), {
      agentType: 'gh-issue-flow:diff-reviewer', label: `review:${lens}#${issue.number}`,
      phase: 'Review', schema: FINDINGS,
    })))).filter(Boolean).flatMap(r => r.findings)

  const shipPrompt = (extra = '') => `Finish issue #${issue.number} per autopilot
    SKILL.md sections 9 and 10. ${rules(issue.worktree)}

    Findings to adjudicate: ${JSON.stringify(findings)}${extra}

    Fix every valid finding. For any you reject, put the claim and your reason in
    rejected — they go in the PR body, never dropped silently.

    Set newLogic true if your fixes added a branch, gate, condition or code path, and
    name the lens that raised it in raisingLens. When newLogic is true, open the PR as a
    DRAFT; a delta review runs before it is marked ready.

    Then archive the spec change, commit with the plan's message, push, and open the PR
    with the section 10 body in the order that section gives. Request review from
    ${issue.reviewer}. READ THE REQUEST BACK — gh exits 0 when GitHub refuses it — and
    return who was actually requested, or null plus an at-mention comment instead.
    State plainly whether merging deploys; when unsure, say it deploys.`

  const shipped = await agent(shipPrompt(), { label: `ship:#${issue.number}`, phase: 'Ship', schema: SHIP })
  if (!shipped) return { ...built, ...dead('Ship', 'the shipper') }
  if (shipped.outcome !== 'ok' || !shipped.newLogic) return { ...built, ...shipped }

  // Delta re-review, as the lens that RAISED the finding — not always correctness.
  const delta = await agent(
    `Review ONLY the delta the adjudicator added to ${issue.worktree} for issue
     #${issue.number}, through the ${shipped.raisingLens} lens. That delta exists to
     establish that lens's property, so that is the question to ask of it.
     git diff on the commits after the implementation commit is the scope.`,
    { agentType: 'gh-issue-flow:diff-reviewer', label: `delta:${shipped.raisingLens}#${issue.number}`,
      phase: 'Review', schema: FINDINGS })

  const finalized = await agent(
    `PR #${shipped.prNumber} for issue #${issue.number} is a DRAFT pending this delta
     review. ${rules(issue.worktree)}
     Delta findings: ${JSON.stringify(delta ? delta.findings : [])}
     Fix every valid one, amend the PR body's rejected list, push, and mark the PR ready
     for review. Read the PR state back and return it. If a finding changes the shape of
     the fix, leave it a draft and return outcome handback with that reason.`,
    { label: `finalize:#${issue.number}`, phase: 'Ship', schema: SHIP })

  // deltaReviewed survives the merge: the finalizer's own newLogic/raisingLens would
  // otherwise overwrite the fact that a delta review happened at all, and § 13 reports it.
  const delta_ran = { deltaReviewed: shipped.raisingLens }
  return finalized ? { ...built, ...shipped, ...finalized, ...delta_ran }
                   : { ...built, ...shipped, ...dead('Finalize', 'the finalizer'), ...delta_ran }
}

const results = await pipeline(args.issues, build, ship)

// A null item means the whole chain died. Never let that read as a quiet success.
const done = args.issues.map((issue, i) => results[i] ??
  { issue, outcome: 'handback', stage: 'pipeline', reason: 'the chain died with no result' })

for (const r of done) {
  if (r.outcome !== 'ok') log(`HANDBACK #${r.issue.number} at ${r.stage}: ${r.reason}`)
  else log(`#${r.issue.number} -> PR #${r.prNumber}${r.isDraft ? ' (DRAFT)' : ''}`)
}

return { results: done }
```

### Concurrency rules the script cannot enforce

Two agents editing one repository at once is the situation every trap in
[`parallel-agents.md`](parallel-agents.md) was measured in. The script cannot police the
filesystem, so these are the caller's job:

- 🚨 **The session creates both worktrees itself, serially, before the fan-out.**
  Concurrent `git worktree add` calls mutate the same `.git/worktrees` bookkeeping. Each
  agent is handed a ready path and a branch, and creates nothing.
- 🚨 **Do not use `agent()`'s `isolation: 'worktree'` for this.** That worktree is
  ephemeral, is auto-removed when unchanged, and is not the `feat/<N>-<slug>` branch
  based on the *remote* integration tip that § 5 requires and the PR needs to outlive the
  run. Autopilot's worktree discipline is not the same object as the API's.
- **No stash, ever.** The stash stack is shared across every worktree on the machine, so
  a pop can take another agent's — or another human's — work. Use a WIP commit.
- **Explicit paths on every `git add`.** `git add -A` in a shared checkout has already
  swept another session's untracked work into a commit here, twice.
- **The gate runs from inside the worktree.** A drifted cwd runs the main checkout's
  suite and reports it as yours.

### What this layer costs

Stated plainly, because the serial path does not pay these:

- **The § 6 plan comment lands late.** The session posts it after the workflow returns,
  so the assignee's window to object is § 4's claim comment alone. That comment already
  has to carry the scope understanding; here it is the only thing that does.
- **One extra context payment per issue.** Today the session implements *and* adjudicates,
  carrying everything it gathered across both. Here the shipper starts fresh on the
  builder's handoff. The handoff narrows the gap; it does not close it. This is the cost
  [`../shared/execution.md`](../shared/execution.md) § 3.1 exists to police, accepted
  knowingly rather than overlooked.
- **Handbacks become a schema.** Every bail is a returned outcome the script branches on,
  instead of a session deciding in prose. That is more rigid than § Handing it back reads,
  and a bail the schema has no field for will be forced into `reason` as text.
- **The ceiling is two.** Nothing here scales past § 2's cap, and § 1's backpressure rule
  is what makes that cap correct.



## What is measured here, and what is not

**Measured** — the two code blocks were run before this file was committed:

| Claim | How |
|---|---|
| The batch build produces newest-first batches of 5, capped at 25, with no `triaged` issue in them | `jq` against a 30-issue and a 28-issue fixture. It also caught the `.[0]` slurp bug above, which is why that ⚠️ is there. |
| The script's pure-JS half behaves: verdicts merge across batches, `missing` catches a dropped issue **and** an agent that returns nothing, the drop is announced via `log()`, a clean run logs nothing, reciprocal dupes collapse to one pair, self-references and unconfident dupes are dropped | 9 assertions against a throwaway harness that stubs `agent()`, `parallel()` and `log()` and runs the real script body |
| **B** — the autopilot script's control flow: a handback short-circuits before a single lens is spawned, a dead planner spends nothing after itself, new logic opens a draft and the delta lens runs **as the lens that raised it**, the finalizer flips it to ready, a dead finalizer leaves the PR a draft and reports a handback rather than a success, and `deltaReviewed` survives the finalizer overwriting `raisingLens` | 20 assertions against the same kind of harness, stubbing `agent()`, `parallel()`, `pipeline()` and `log()` |

⚠️ **A harness can read a stale script and pass.** Regenerating B's harness in place
failed silently once, so a green run was reporting on the previous version of the script.
Both harnesses now re-extract the code block from this file and assert on a string only
the current version contains. That is the same failure this repo keeps recording: an
empty or stale read is indistinguishable from a good one.

⚠️ The harnesses were throwaway and are not tracked — the guard suite is Python and this is
JS, and these optional layers do not earn a new file class in
[`../../../tests/`](../../../tests). Rebuild them if you change either script; each is
about twenty lines of stubs.

**Not measured** — everything that needs a live board and a real model:

- No agent has produced a verdict or a PR through either path. The prompts are written
  against the skills' sections, not tested against them.
- **B has never run two worktrees concurrently.** The concurrency rules in it are carried
  over from measured incidents in [`parallel-agents.md`](parallel-agents.md), not
  re-measured under a workflow.
- **No wall-clock or token number is claimed anywhere in this file**, deliberately. The
  fan-out is asserted to be *parallel*, not to be *cheaper* — each agent re-reading repo
  context could plausibly cost more in total tokens than the serial pass, and nobody has
  priced it.
- The 10-issue threshold in A, as flagged above.
- B's agent arithmetic (6 per issue, 12 a run) is counted, not observed. A plan naming
  more lenses changes it.

The way to settle the rest is the A/B the layered design makes free — same board, same day,
both paths, then compare:

- **Verdict agreement per attribute.** Category and effort disagreeing occasionally is
  expected. **`agent-ready` disagreeing is the finding**, in either direction: the
  fan-out marking one the serial pass would not is a bad promise heading for the
  autopilot queue, and the reverse means the fan-out is paying for judgment it then
  discards.
- **`missing` is empty**, across several runs.
- **Whether it is actually faster**, including the batch build and the adjudication —
  the serial pass being replaced is bounded by 25 issues, and this run is bounded by
  its slowest batch.

Until that comparison exists, the honest description is "plausible and unmeasured".
