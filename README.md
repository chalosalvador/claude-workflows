# claude-workflows

A Claude Code plugin marketplace: an issue-to-merged-PR workflow — triage a board, pick
the next issue, plan it, build it in a worktree, review it adversarially, ship it — plus
the operational reference docs that keep each step honest.

Works in a **new repo or an existing one**, on any language. Nothing about it is specific
to a stack, an org, or a board layout.

## The workflow it gives you

```
triage ──▶ next-issue ──▶ plan ──▶ branch ──▶ [spec] ──▶ build ──▶ validate
                                                                      │
   merge ◀── babysit ◀── PR ◀── commit ◀── [archive] ◀── review ◀─────┘
```

- **`triage`** keeps the board honest: every open issue on-board, area-labeled, assigned,
  sized, prioritized — and the safe ones gated `agent-ready`.
- **`next-issue`** picks the card that continues what the team is already doing, and
  either hands you a paste-ready prompt or runs it here with a pause for your OK,
  ending with a plain-words summary of what to review and test.
- **`autopilot`** works the `agent-ready` queue unattended and opens reviewable PRs. It
  never merges.
- **`work-summary`** turns a date window into a plain-language rollup.

Underneath, every step is backed by a reference doc — why an empty grep is not proof, how
a guard test gets defeated, what a passing bot check does not tell you.

## Getting started

### 1. Install

```bash
/plugin marketplace add chalosalvador/claude-workflows
```

```bash
/plugin install gh-issue-flow@claude-workflows
```

*(Working from a fork? Substitute your own `owner/repo` in the first line — the second is
unchanged, since it names the marketplace, not the repo.)*

You will be prompted for your board number and owner. **Leave them blank if you have no
project board** — the skills fall back to labels and `gh issue list`.

**The two install paths differ here, and neither is broken.** From a terminal,
`claude plugin install` prints a line like *"4 userConfig options not yet set"*.
MEASURED: the terminal path prints that count. The in-session `/plugin install` does
**not** — it may show a configuration step instead, or simply report the plugin enabled.
⚠️ That second half is **read from the CLI, not yet confirmed by a run**; treat it as
unverified. Either way, seeing neither a form nor a count is expected, not a failure.

That count is **not an error**. It counts options declared but not stored — including
the two that already carry working defaults (`status_in_progress` → `In Progress`,
`ready_label` → `agent-ready`) — and **none of the four is required**. On the boardless
path it is expected and nothing is wrong.

⚠️ **What you enter here is a machine-wide DEFAULT, not a per-repo setting** — why, and
the measurement behind it, in [§ Configuration](#configuration-in-three-layers) below.

**So a workspace that targets a different board overrides it in that repo**, in
`.claude/workflow.json`, which wins over this default:

```json
{ "board": { "number": 11, "owner": "acme" } }
```

`setup` asks for it and writes it. Several repos feeding one board is the other
supported shape — list them in `workflow.json` → `repos`. Either way you set the machine
default once and never re-run the install to switch projects.

To enable it for a whole team, commit this to the repo's `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "claude-workflows": {
      "source": { "source": "github", "repo": "chalosalvador/claude-workflows" }
    }
  },
  "enabledPlugins": { "gh-issue-flow@claude-workflows": true }
}
```

### 2. Run setup, in the repo

```
/gh-issue-flow:setup
```

It probes the repo — integration branch, the gate commands out of your CI workflow, spec
flow, merge method, branch protection — writes `.claude/workflow.json`, creates the
labels the skills read, and checks your board has the fields they need. Then it reports
**every gap it could not close itself**, and who can close it.

On a repo that already half-works, run `/gh-issue-flow:setup check` instead. It changes
nothing and tells you what is missing.

Setup also writes **stack docs** — `.claude/workflow/stacks/<name>.md`, one per deploy
target it detects — from what it probed, and marks everything it could not probe
`UNVERIFIED` for a human to fill in. The plugin's own reference docs are stack-neutral;
what merging deploys, how a secret is verified, which bot reviews PRs, which invariants
a reviewer checks — all of that lives in your repo, where it can be right.

After a plugin update, `/gh-issue-flow:setup upgrade` adds the keys the config schema
gained since your `workflow.json` was written and generates any stack doc that new
evidence calls for. It touches nothing that already exists. You do not have
to remember: every skill prints one line when the file is behind.

### 3. Try it

```
/gh-issue-flow:triage dry run
```

Analyzes everything, writes nothing, prints the exact mutations it would make. When that
looks right, drop `dry run`.

### 4. Consider a testbed before your real repo

`triage` writes labels and board fields across every open issue, and `autopilot` opens
PRs unattended. Both are reversible, but neither is quiet.

A throwaway repo — a small project with real CI, half a dozen realistic issues, and its
own board — exercises every path in about twenty minutes and costs you nothing if it goes
wrong. **Building this plugin's own testbed found four bugs that reading the code had
not**, including two where a `gh` call returned exit 0 and did nothing. If you are
adapting the skills, do this first.

## What a run costs

Worth knowing before you point `autopilot` at a queue, because the caps exist for this
reason.

A **one-line documentation fix**, end to end, spent roughly **110k tokens and ~12 minutes
of wall clock** — about 40k on the planner and 70k across two review lenses, both pinned
at `effort: max`. A substantial change costs more.

That is the justification for three rules you might otherwise be tempted to relax:

- **`autopilot` stops at 3 open `agent-authored` PRs.** The bottleneck is human review,
  not authoring.
- **`autopilot` takes at most 2 issues per run**, and caps babysitting at 45 minutes.
- **The planner names which lenses apply, and you fire only those.** Five max-effort
  reviewers on a docs change is most of that bill for nothing.

The corollary: the `agent-ready` gate is not conservative for its own sake. Each wrong
call spends real money to put a wrong PR on a teammate's queue.

### Bringing it down

The dominant waste turned out not to be review depth. Three agents each cloned the repo,
built their own environment and read the same files — **the identical research, three
times, for about a third of the spend.**

So the skills pass a **research handoff** forward (what was read, what the gate returned,
and pointedly what is *still unverified*), gate the lens list on the plan, tier the model
by the issue's size label, and let the planner scale its own output. Rules and the
measured numbers: [`shared/execution.md`](plugins/gh-issue-flow/shared/execution.md)
§ 3.1 — one place, so they cannot drift.

⚠️ **None of it cuts scrutiny.** It removes duplicated research and unearned lenses. If
you find yourself skipping the review to save budget, the honest move is to not run the
agent on that issue at all.

**Measured, two issues, same prompt and worktree, only the planner spec differing:**

| | tokens before → after | |
|---|---|---|
| a 2-file code change | 52,075 → 40,790 | **−22%** |
| a 1-file docs change | 55,169 → 53,861 | −2%, flat |

So this **reallocates effort rather than uniformly cutting it.** The simple issue got
cheaper; the subtle one spent the same and used it better — on the docs change the planner
replayed six candidate strings through a consuming script and found one that passes its
guard, fails its rewrite, and destroys a fixture while printing success.

Section discipline held **17/17** across both, and the triggers discriminated in both
directions: `VERIFY-FIRST`/`TESTS` fired on the code change and stayed silent on the docs
one; `RISKS` did the reverse. **Treat this as a compliance-and-quality result, not a cost
result** — the saving is real only on easy issues.

### Measured: unattended runs on the testbed, 2026-09-07

Two full `triage` → `autopilot` runs on
[`claude-workflows-testbed`](https://github.com/chalosalvador/claude-workflows-testbed)
(plugin 0.8.1, same commit both times, board reset to pristine between them). Triage
took ~3 min and 6 GraphQL points per run, and gated the same three of six issues
`agent-ready` both times — the two-runs `agent-ready` disagreement the fan-out doc calls
"the finding" did not occur. Autopilot took the two P2s (#2, a two-file code change;
#3, a README fix) and skipped #6 on the cap of 2 both times.

| | Run 1 — serial | Run 2 — Workflow layer (§ B) |
|---|---|---|
| Issues taken / skipped | #2, #3 / #6 (cap) | #2, #3 / #6 (cap) |
| Lenses fired | #2: correctness, tests · #3: correctness, scoping | same four, same split — the plans named the same lenses |
| Findings | 1 real per issue: a surviving `pop()` mutant (#2); a paragraph the fix made false (#3) | #2: 2 (a soft-delete mutant, a last-match mutant, both survived the builder's tests) · #3: 1 latent `reset.sh` trap, noted |
| PRs | #10, #11 — both ready-for-review | #12, #13 — both ready-for-review |
| Babysit end-state | green / 0 threads, both | green / 0 threads, both |
| Wall-clock, first push → last PR green | 14 min 22 s (serial: 28 min from selection to report) | ~7 min (22 min from selection to report; workflow itself 17 min 52 s) |
| Subagent tokens | 261,943 across 6 agents (2 planners, 4 lenses, all `sonnet`) | 485,392 across 10 agents (2 planners, 2 builders, 4 lenses, 2 shippers — all at the session model, see below) |
| Main-session tokens | unmeasured — not exposed | unmeasured |

The two token numbers are not like-for-like: run 1 ran its planners and lenses at
`sonnet` and did the implementing and shipping in the main session (unmeasured); run 2's
script passed no `model`, so all ten agents ran at fable, and two builders and two
shippers are inside the count. Per agent in run 1: planners 43k and 49k; lenses 36k–48k each. The one-line docs fix
(#3) cost 130k of subagent spend on its own — in line with the 110k measured above, and
the reason a docs issue still gets only the two lenses its plan names.

Two mechanism defects surfaced in run 1 and are fixed in 0.8.2: a `tests` lens rewrote
the shared worktree in place to re-run mutants while the `correctness` lens was reading
it (`agents/diff-reviewer.md` now forbids that), and a survived mutant was committed
because the block printed the result instead of gating on it
(`shared/execution.md` § 2.2). Run 2 also hit a third: the local `feat/<N>-*` branch
from run 1 outlived its worktree and blocked `git worktree add -b`
(`skills/autopilot/SKILL.md` § 5).

## Prerequisites

| Need | Why | Check |
|---|---|---|
| `gh` authenticated, with `project` scope | every skill reads issues; board steps need the extra scope | `gh auth status` |
| A git repo with a GitHub remote | branch, PR, and protection lookups | `gh repo view` |
| A green suite on your integration branch | the skills treat "any red is yours" as true | run your gate once |
| GPG signing (recommended) | the flow signs every commit and stops if signing fails | `git config --get commit.gpgsign` |
| A Projects v2 board (optional) | triage's routing guarantees and priority ordering | `gh project list --owner <you>` |

Missing the board or signing does not break anything — it narrows what the skills claim.
`setup` tells you which.

## Configuration, in three layers

**Layer 1 — `userConfig`** (prompted once, on install): the **default** board number and
owner, status names, the autopilot label. Per person, one set per machine — a repo's
`workflow.json` → `board` overrides the board half.

⚠️ Claude Code reads `pluginConfigs` **only** from user-level settings — MEASURED: it
lands there even under `--scope project`, and a project `.claude/settings.json` is never
consulted for it. So Layer 1 is **one set of values per machine**, and anything that
varies per repo belongs in Layer 2. That is why the board here is only a default.

**Layer 2 — `.claude/workflow.json`** in each repo, written by `setup`:

```json
{
  "repos": ["acme/acme-api"],
  "board": { "number": 11, "owner": "acme" },
  "integrationBranch": "origin/dev",
  "validate": ["uv run ruff check .", "uv run pytest tests"],
  "deployOnMerge": "merging this branch deploys staging and runs migrations",
  "areaLabels": { "area:backend": "what belongs here" },
  "dri": { "area:backend": "octocat" }
}
```

`repos` is the set the multi-repo skills sweep — one entry is the normal answer. `board`
overrides the Layer-1 default, so different workspaces can target different boards on one
machine. `dri` maps each area to its owner, and is what lets triage guarantee
**0 unassigned**.

**Layer 3 — probe.** With no config at all the skills still work, deriving the branch
from `gh repo view` and the gate from your CI workflow or toolchain. **The config file is
an override, not a prerequisite** — that is what makes the plugin usable on a repo it has
never seen.

Full schema and every key's meaning:
[`shared/config.md`](plugins/gh-issue-flow/shared/config.md).

## Contents

**Skills** (`/gh-issue-flow:<name>`)

| Skill | Does |
|---|---|
| `setup` | Probes the repo, writes `.claude/workflow.json`, creates the labels and board fields the rest depend on, reports every gap it cannot close. `check` mode changes nothing. |
| `triage` | Uncapped integrity pass (0 off-board, 0 unassigned) + capped deep pass: category, effort, priority, duplicates, and the `agent-ready` gate. |
| `next-issue` | Picks the theme-aligned Todo card, then either emits a paste-ready start prompt or runs the issue in-session with a pause for your OK — and, once the PR is open, ends with a plain-words summary of what to review and test. |
| `autopilot` | Works the `agent-ready` queue unattended in a worktree, opens reviewable PRs, never merges. |
| `work-summary` | Plain-language summary of a date window from git history — daily, standup, weekly, or a rendered Slidev deck. |

**Agents** — `issue-planner` (scoping plan, read-only, max effort) and `diff-reviewer`
(adversarial single-lens review; spawn several in parallel from the parent, using the
namespaced `gh-issue-flow:` name so a same-named local file cannot shadow them).

**Shared** — [`shared/config.md`](plugins/gh-issue-flow/shared/config.md) (the three-layer
config resolution) and [`shared/execution.md`](plugins/gh-issue-flow/shared/execution.md)
(branch, validate, review, babysit, board, deploy — facts, not policy).

**Stack docs** — per repo, in `.claude/workflow/stacks/`, generated by `setup` and owned
by the repo: deploy, secrets, infra, review bot, reviewer invariants, traps. Nothing
stack-specific ships in the plugin.

**Reference** — twelve docs of measured operational knowledge, stack-neutral; see
[its README](plugins/gh-issue-flow/reference/README.md).

## Develop

```bash
claude --plugin-dir ./plugins/gh-issue-flow
```

```bash
claude plugin validate ./plugins/gh-issue-flow --strict
```

`/reload-plugins` picks up edits without a restart.

## Recommended: pair this with OpenSpec

These skills work without it — they detect its absence and skip the spec steps. But they
are **much better with it**, and the flow below assumes it.

[OpenSpec](https://www.npmjs.com/package/@fission-ai/openspec) is a spec-driven change
flow: each issue gets a change directory holding its proposal and a **delta** —
`## ADDED | MODIFIED | REMOVED Requirements`, each in SHALL/MUST form with WHEN/THEN
scenarios. When the PR lands, the delta is *archived*: folded into a living
capability spec under `openspec/specs/`.

```bash
npm i -g @fission-ai/openspec@1.8.0   # pin the version your CI pins
openspec init                          # in the repo
```

**What you get.** Over time the archive accumulates the history while the specs stay
small: the spec says what is true *now*, the archive says how it got that way. A mature
repo tends toward a handful of capability specs distilled from dozens of changes.

- **The design call happens before the code.** The change directory is validated before
  implementation starts, so a wrong requirement costs minutes instead of a rewrite. This
  is the single biggest win, and it is why `next-issue` step 4b and `autopilot` § 7 both
  gate on it.
- **The spec resists drifting into fiction.** Every requirement cites the file and symbol
  it is grounded in; every scenario traces to a passing test or to code someone read.
- **It is CI-checkable**, so it stays maintained rather than rotting into a stale wiki
  page. Make `openspec validate --all --strict` a required check.
- **The reviewer gets intent before diff.** That matters most for `autopilot`, whose PRs
  arrive unattended: the plan and the delta say what the agent understood, so a reviewer
  can reject the *understanding* without reading the code.

⚠️ Read [`reference/openspec.md`](plugins/gh-issue-flow/reference/openspec.md) before
trusting the gate. A green `validate --all --strict` asserts less than it looks: it exits
0 on an empty root, never reads the archive, and `skip_specs: true` switches it off for
that change entirely.

### Why the `openspec-*` skills aren't vendored here

The six `openspec-propose` / `-apply-change` / `-archive-change` / … skills you may have
seen in a repo's `.claude/skills/` are **generated artifacts** of the CLI, not
hand-written skills — their frontmatter says `author: openspec`, `generatedBy: 1.8.0`,
MIT. Shipping copies would fork a dependency at a pinned version and be silently
clobbered by the next `openspec update`. **`openspec init` is the supported way to get
them**, and it keeps them current.

## Slide decks

`work-summary` also renders a [Slidev](https://sli.dev) deck for a stakeholder update —
ask it for "slides", "a deck", or "the weekly update deck".

It ships a **neutral starting template**: cover → at-a-glance cards with progress bars →
one slide per workstream that moved → roadmap → close. Workstreams come from
`workflow.json`, so the structure is yours without editing the template.

```bash
npm i -D @slidev/cli @slidev/theme-default vue     # once
npx @slidev/cli slides/weekly-update.md --open
```

**Rebranding is five CSS variables** at the top of the bundled stylesheet — accent,
surface, ink, and two status colours — with a documented swap for a light deck. The cover
carries a placeholder mark to replace with your own.

Both themes were rendered and checked: the status pills mix toward the ink colour so they
stay WCAG AA at 4.7–4.9 on light and ~14 on dark, rather than washing out.

The deck is a *rendering of the summary*, not a separate investigation — if the commits
do not support a claim, the slide does not get to make it.
