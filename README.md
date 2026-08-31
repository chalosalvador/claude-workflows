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
  either hands you a paste-ready prompt or runs it here with a pause for your OK.
- **`autopilot`** works the `agent-ready` queue unattended and opens reviewable PRs. It
  never merges.
- **`work-summary`** turns a date window into a plain-language rollup.

Underneath, every step is backed by a reference doc — why an empty grep is not proof, how
a guard test gets defeated, what a passing bot check does not tell you.

## Getting started

### 1. Install

```bash
/plugin marketplace add <owner>/claude-workflows
```

```bash
/plugin install gh-issue-flow@claude-workflows
```

You will be prompted for your board number and owner. **Leave them blank if you have no
project board** — the skills fall back to labels and `gh issue list`.

To enable it for a whole team, commit this to the repo's `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "claude-workflows": {
      "source": { "source": "github", "repo": "<owner>/claude-workflows" }
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

The skills apply four levers, in order of saving:

1. **A research handoff.** The planner ends with a `HANDOFF` block — files read, gate
   result, existing environment, what is already verified and **what is not** — and every
   reviewer starts from it. Without this, each agent re-clones the repo, rebuilds a
   virtualenv and re-reads the same files. Measured on the run above: three agents did the
   identical research three times, roughly a third of the spend for nothing.
2. **Lens gating.** The planner names which lenses the diff can actually trip. Five where
   two apply is more than double the review cost.
3. **Model tiering per spawn.** `model` is an argument on each spawn; `effort` is
   frontmatter-only and cannot be overridden. `effort:easy` issues run planner and lenses
   on a cheaper tier.
4. **Plan scaling.** The planner caps its own output by issue size — ≤400 words for a
   one-file easy fix, uncapped for a migration. Every word is paid for twice: once
   written, once read by each lens.

⚠️ **None of these cuts scrutiny.** They remove duplicated research and unearned lenses.
If you find yourself skipping the review to save budget, the honest move is to not run
the agent on that issue at all.

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

**Layer 1 — `userConfig`** (prompted once, on install): board number, board owner, status
names, the autopilot label. Per person.

⚠️ Claude Code reads `pluginConfigs` **only** from user-level settings — a project
`.claude/settings.json` is ignored for it — so anything that varies *per repo* cannot
live here.

**Layer 2 — `.claude/workflow.json`** in each repo, written by `setup`:

```json
{
  "integrationBranch": "origin/dev",
  "validate": ["uv run ruff check .", "uv run pytest tests"],
  "deployOnMerge": "merging this branch deploys staging and runs migrations",
  "areaLabels": { "area:backend": "what belongs here" }
}
```

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
| `next-issue` | Picks the theme-aligned Todo card, then either emits a paste-ready start prompt or runs the issue in-session with a pause for your OK. |
| `autopilot` | Works the `agent-ready` queue unattended in a worktree, opens reviewable PRs, never merges. |
| `work-summary` | Plain-language summary of a date window from git history — daily, standup, weekly, or a rendered Slidev deck. |

**Agents** — `issue-planner` (scoping plan, read-only, max effort) and `diff-reviewer`
(adversarial single-lens review; spawn several in parallel from the parent).

**Shared** — [`shared/config.md`](plugins/gh-issue-flow/shared/config.md) (the three-layer
config resolution) and [`shared/execution.md`](plugins/gh-issue-flow/shared/execution.md)
(branch, validate, review, babysit, board, deploy — facts, not policy).

**Reference** — nine docs of measured operational knowledge; see
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
