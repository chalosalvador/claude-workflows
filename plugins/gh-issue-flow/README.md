# gh-issue-flow

An issue-to-merged-PR workflow for Claude Code: triage a board, pick the next issue, plan
it, build it in a worktree, review it adversarially, ship it — with the operational
reference docs that keep each step honest.

Works in a new repo or an existing one, on any language.

## Start here

```
/gh-issue-flow:setup
```

Probes the repo, writes `.claude/workflow.json`, creates the labels the skills read,
checks your board, and reports every gap it cannot close itself. Then:

```
/gh-issue-flow:triage dry run
```

⚠️ **Before pointing this at a repo you care about**, consider running it once against a
throwaway repo with real CI and a few realistic issues. `triage` writes across every open
issue; `autopilot` opens PRs unattended. Both are reversible, neither is quiet — and a
testbed run found four real bugs in this plugin that reading the code had not.

## What's inside

### Skills

| Skill | Invoke | Does |
|---|---|---|
| [`setup`](skills/setup/SKILL.md) | `/gh-issue-flow:setup` | Bootstrap or check a repo. `check` mode changes nothing. |
| [`triage`](skills/triage/SKILL.md) | `/gh-issue-flow:triage` | Uncapped integrity pass (0 off-board, 0 unassigned) + capped deep pass: category, effort, priority, duplicates, `agent-ready` gate. |
| [`next-issue`](skills/next-issue/SKILL.md) | `/gh-issue-flow:next-issue` | Picks the theme-aligned card; emits a paste-ready prompt **or** runs it here with a pause for your OK. |
| [`autopilot`](skills/autopilot/SKILL.md) | `/gh-issue-flow:autopilot` | Works the `agent-ready` queue unattended in a worktree. Opens reviewable PRs; **never merges**. |
| [`work-summary`](skills/work-summary/SKILL.md) | `/gh-issue-flow:work-summary` | A date window as plain language — daily, standup, weekly, or a rendered Slidev deck. |

### Agents

Both are **read-only** and pinned to `effort: max`, so they run at full reasoning
regardless of the session's own setting. They appear as `gh-issue-flow:<name>`.

| Agent | Used by | Returns |
|---|---|---|
| [`issue-planner`](agents/issue-planner.md) | `next-issue` step 3, `autopilot` § 6 | DECIDE-FIRST, VERIFY-FIRST, SCOPE (+FOLD IN), SPEC IMPACT, TESTS, RISKS, and **REVIEW LENSES** |
| [`diff-reviewer`](agents/diff-reviewer.md) | `next-issue` step 6, `autopilot` § 9 | Findings through **one** assigned lens: `correctness`, `contract`, `scoping`, `tests`, `deploy` |

🚨 **A subagent cannot fan out** — it has no Agent tool and spawns do not nest. Spawn
`diff-reviewer` **N times from the parent, in one message**, one per lens. Gate the lens
list on what the planner named; five max-effort reviewers on a styling change is waste.

⚠️ `issue-planner` describes the spec change; it never creates it. Its callers run it at
different points in the branch lifecycle, one of them before the branch exists.

### Shared

- [`shared/config.md`](shared/config.md) — the three-layer config resolution
  (`userConfig` → `workflow.json` → probe). **Read this first.**
- [`shared/execution.md`](shared/execution.md) — branch, validate, review, babysit,
  board, deploy. Facts, not policy: skills own the policy, this owns the mechanics, so
  the two cannot drift.

### Reference

Nine docs of measured operational knowledge — see [their index](reference/README.md).
Skills link into them at the moment each becomes relevant.

The one idea underneath all of them: **silence, an empty result, and exit 0 are
indistinguishable from success.** Prove the positive case first.

## How the skills fit together

```
setup ──▶ triage ──▶ next-issue ──▶ issue-planner ──▶ build ──▶ diff-reviewer ×N ──▶ PR
   │          │                                                                        │
   │          └──▶ agent-ready ──▶ autopilot ──────────────────────────────────────────┘
   │
   └──▶ work-summary  (independent — reads git, not the board)
```

`triage` produces the `agent-ready` label that `autopilot` consumes. That label is the
contract between them: triage's gate decides what an unattended run is allowed to touch,
and autopilot re-verifies it rather than trusting it.

## Config

Everything repo-specific resolves through `.claude/workflow.json`, written by `setup`.
Nothing is hardcoded — not the branch, the gate, the board ids, or the labels.

**The config is an override, not a prerequisite.** With no config the skills probe the
repo and still work.

## Developing

```bash
claude --plugin-dir ./plugins/gh-issue-flow
```

```bash
claude plugin validate ./plugins/gh-issue-flow --strict
```

`/reload-plugins` picks up edits without a restart.
