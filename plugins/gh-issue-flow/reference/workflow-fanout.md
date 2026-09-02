# Fanning the deep pass out with the Workflow tool

The deep pass ([`../skills/triage/SKILL.md`](../skills/triage/SKILL.md) § 3–4) reads up
to 25 issues, opens the files each one names, and judges five attributes per issue. In
one session that is serial — 25 issues read one after another, by the pass that has to
open files to do its job.

The judgments are independent of each other, so they can run in parallel. This file
holds the script that does it, and the boundaries that keep it from becoming a second,
divergent implementation of triage.

🚨 **This is an optimization layer, never a replacement.** The serial path in § 3–4 is
the contract; this is a faster way to reach the same verdicts. If the Workflow tool is
absent from the session, or the untriaged set is small, or anything here fails — run
§ 3–4 serially and say nothing about it in the receipt. A triage run that produces
verdicts is working correctly whichever path produced them.

## The seam

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

## When it pays

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

## Batch — do not go one agent per issue

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

## The script

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

## Building the batches

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

## What the session still does

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

## What is measured here, and what is not

**Measured** — the two code blocks were run before this file was committed:

| Claim | How |
|---|---|
| The batch build produces newest-first batches of 5, capped at 25, with no `triaged` issue in them | `jq` against a 30-issue and a 28-issue fixture. It also caught the `.[0]` slurp bug above, which is why that ⚠️ is there. |
| The script's pure-JS half behaves: verdicts merge across batches, `missing` catches a dropped issue **and** an agent that returns nothing, the drop is announced via `log()`, a clean run logs nothing, reciprocal dupes collapse to one pair, self-references and unconfident dupes are dropped | 9 assertions against a throwaway harness that stubs `agent()`, `parallel()` and `log()` and runs the real script body |

⚠️ The harness was throwaway and is not tracked — the guard suite is Python and this is
JS, and one optional layer does not earn a new file class in
[`../../../tests/`](../../../tests). Rebuild it if you change the reconciliation; it is
twenty lines of stubs.

**Not measured** — everything that needs a live board and a real model:

- No agent has produced a verdict through this path. The prompt is written against the
  triage skill's sections, not tested against them.
- **No wall-clock or token number is claimed anywhere in this file**, deliberately. The
  fan-out is asserted to be *parallel*, not to be *cheaper* — each agent re-reading repo
  context could plausibly cost more in total tokens than the serial pass, and nobody has
  priced it.
- The 10-issue threshold, as flagged above.

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
