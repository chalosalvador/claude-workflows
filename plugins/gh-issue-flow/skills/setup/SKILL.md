---
name: setup
description: >-
  Bootstrap a repo for this workflow, or check an already-configured one. Probes the
  repo for its integration branch, validation gate, spec flow and merge method; writes
  .claude/workflow.json; creates the labels triage and autopilot depend on; and verifies
  the project board has the fields they read. Reports every gap it cannot close itself.
  Use for "set up the workflow here", "onboard this repo", "why isn't triage working",
  or as the first thing you run after installing this plugin.
---

# Setup

Get a repo from nothing to the full workflow, or tell an already-configured repo what it
is missing.

Two modes, chosen from the user's wording:

- **Bootstrap** (default, or "set up", "onboard") — probe, write, create, report.
- **Check** ("check", "doctor", "why isn't X working", "what's missing") — probe and
  report only. **Changes nothing.** Run this first on a repo that already half-works.

**Never overwrite without asking.** If `.claude/workflow.json` already exists, show the
diff between it and what you would write, and let the user choose.

## Workflow

```
- [ ] 1. Preconditions — gh auth, repo, signing
- [ ] 2. Probe the repo (branch, gate, spec flow, merge method, protection)
- [ ] 3. Write .claude/workflow.json  (bootstrap only)
- [ ] 4. Labels — create the ones the skills read  (bootstrap only)
- [ ] 5. Board — verify the fields exist; create what gh can  (bootstrap only)
- [ ] 6. Confirm the two agents loaded, and say what they are for
- [ ] 7. Report: what is configured, what is missing, what only a human can do
```

## 1. Preconditions

```sh
gh auth status                       # must be logged in, with project scope for board steps
git rev-parse --show-toplevel        # must be a git repo
git config --get commit.gpgsign      # the workflow signs every commit
```

If `gh auth status` lacks the `project` scope, board steps will fail with a
permissions error rather than an empty result:

```sh
gh auth refresh -s project,read:project
```

If `commit.gpgsign` is unset, say so — every skill here signs commits and stops on a
signing failure. That is a user decision, not something to configure for them.

## 2. Probe

Never assume. Read each of these:

```sh
gh repo view --json nameWithOwner,defaultBranchRef,squashMergeAllowed,rebaseMergeAllowed,mergeCommitAllowed,isEmpty
git branch -r --list 'origin/*'
```

🚨 **Handle the empty repo first.** A GitHub repo created but never pushed to reports
`isEmpty: true` and `defaultBranchRef.name` as an **empty string** — measured, not null,
so a truthiness check on the object still passes and you compose `origin/` + `""` =
`origin/`, a branch name that silently matches nothing downstream.

```sh
gh repo view --json isEmpty --jq '.isEmpty'   # true -> stop probing the branch
```

On an empty repo: say so, write no `integrationBranch`, and tell the user to push first
and re-run. Everything else in this skill still applies — labels and the board can be set
up before the first commit.

⚠️ **Glob defensively — the agent's shell is zsh, where an unmatched glob is an ERROR,
not an empty list.** `ls .github/workflows/*.yml` exits 1 with `no matches found` and
aborts a chained command, where bash would have passed the pattern through. Measured on a
repo with no CI. Test the directory first, or use `find`:

```sh
[ -d .github/workflows ] && find .github/workflows -name '*.yml' -o -name '*.yaml'
```

| Fact | How |
|---|---|
| `integrationBranch` | `origin/` + the default branch — **after** the empty-repo check above. ⚠️ **Not always `main`** — if a `dev`/`develop` remote branch exists and is ahead of the default, the repo probably integrates there and releases from the default. **Ask; do not guess.** |
| `validate` | **Read the CI workflow first** — `.github/workflows/*.yml`, the job that runs on PRs into the integration branch. Copy its step commands in order. Fall back to the toolchain only if there is no CI: `pyproject.toml`/`requirements.txt` → `ruff`/`pytest`; `package.json` → the lint/typecheck/test/build scripts that actually exist; `Cargo.toml` → `cargo clippy`/`cargo test`; `go.mod` → `go vet`/`go test ./...`. |
| `preflight` | Anything the gate shells out to that no lockfile installs. |
| `specFlow` | An `openspec/` directory at the repo root → `"openspec"`. |
| `mergeMethod` | From the `*MergeAllowed` flags. |
| `deployOnMerge` | Grep `.github/workflows/` for a workflow triggering on push to the integration branch that deploys. **Do not record "nothing happens" unless you looked.** Note that some hosts (Vercel, Netlify, Fly) deploy from the repo with no workflow at all — check for their config files too. |
| `requiredChecks`, `protection` | `gh api repos/<owner>/<repo>/branches/<b>/protection` — this 404s if the branch is unprotected, which is itself the answer. |
| `workstreams` | For a monorepo: the actual directories under `apps/`, `packages/`, `crates/`, etc. **Read the tree; never trust a README.** |

**Verify each probed command actually runs before writing it into the config.** A gate
entry that errors on first use is worse than an absent one — the next session reads its
failure as a broken repo. Run them; report any that fail.

## 3. Write `.claude/workflow.json`

Schema and key meanings: [`shared/config.md`](../../shared/config.md).

Write **only** what you probed. Leave a key out rather than guessing it — an absent key
falls through to Layer-3 probing, a wrong key is believed.

Add `$comment` keys recording **where each value came from and when**. Every list in that
file is a snapshot of something that moves; the comment is what tells the next reader to
re-derive rather than trust.

⚠️ **Check whether `.claude/` is gitignored** before declaring the file shared:

```sh
git check-ignore -v .claude/workflow.json
```

Read the `-v` output, not the exit code — `git check-ignore` exits 0 on **any** pattern
match, a negation included. Many repos blanket-ignore `.claude/*` with per-file
negations. If the new file is ignored, it is **local-only** and teammates get nothing:
tell the user the exact negation line to add, and that `.gitignore` is a tracked file
whose change may need a PR.

## 4. Labels

These are the labels the skills read. Create the missing ones; **never modify an existing
label's colour or description** — a repo's palette is a human's choice.

```sh
gh label create improvement     -d "Refactor, perf, DX, cleanup of something that works" -c 0E8A16
gh label create effort:easy     -d "One repo, obvious files, a pattern to mirror"        -c C2E0C6
gh label create effort:medium   -d "Multiple modules or a new pattern"                   -c FBCA04
gh label create effort:hard     -d "Cross-repo, migration, infra, or an open question"   -c D93F0B
gh label create triaged         -d "Deep-triage idempotency key"                         -c EDEDED
gh label create blocked         -d "Cannot proceed — see 'Blocked by: #n'"               -c B60205
gh label create epic            -d "Tracking issue with sub-issues"                      -c 5319E7
gh label create agent-ready     -d "Gated safe for unattended work"                      -c 1D76DB
gh label create agent-wip       -d "An unattended run has claimed this"                  -c 0052CC
gh label create agent-blocked   -d "Unattended run handed it back — a human decides"     -c B60205
gh label create agent-authored  -d "PR opened unattended"                                -c 1D76DB
```

A new GitHub repo ships with `bug`, `documentation`, `duplicate`, `enhancement`,
`good first issue`, `help wanted`, `invalid`, `question` and `wontfix` (verified) — so
four of the category labels already exist. Check before creating.

`gh label create` **exits 1 on an existing name** (measured) with
`label with name "x" already exists`. Tolerate that failure rather than passing
`--force`, which would overwrite a description someone wrote.

⚠️ **Do not pipe the loop into `head`/`tail`.** The pipeline's status becomes the pager's,
so every failure reads as success — and a label loop is exactly where that bites. Capture
the status separately, then **read the labels back** and report what actually exists:

```sh
gh label list --limit 200 --json name --jq '.[].name'
```

🚨 **Pass each label as its own argument, never a split shell variable.** The labels API
auto-creates any name it is handed, and under a shell that does not word-split, a
variable holding two names becomes one junk label created repo-wide. After any label
loop, assert no label name contains a space.

**Area labels are the user's taxonomy, not ours.** Ask what areas this repo has, create
`area:<name>` for each, and record them in `workflow.json` → `areaLabels` with a
one-line meaning, plus `dri` mapping each to its owner. Triage routes assignees off
this map; without it, the integrity pass cannot guarantee "0 unassigned".

## 5. Board

The board is optional. **With no board, triage still does the label half and
`next-issue` still selects from `gh issue list` — say so and move on.**

```sh
gh project list --owner <owner>
gh project field-list <number> --owner <owner> --format json
```

| Field | Needed for | If missing |
|---|---|---|
| `Status` | every skill | Ships with a new board: Todo / In Progress / Done |
| `Priority` | triage §3c, autopilot ordering | `gh project field-create` (below) |
| `Track` | triage integrity pass | `gh project field-create`, options = the user's areas |

```sh
gh project field-create <number> --owner <owner> --name Priority \
  --data-type SINGLE_SELECT --single-select-options P0,P1,P2,P3

gh project field-create <number> --owner <owner> --name Track \
  --data-type SINGLE_SELECT --single-select-options "<their areas, comma-separated>"
```

To create a board from scratch: `gh project create --owner <owner> --title "<name>"`,
then `gh project link <number> --owner <owner> --repo <owner>/<repo>`.

### 🚨 The one thing you must NOT automate: adding a Status option

The workflow uses a **`Hold`** Status — "a human parked this by choice" — which a new
board does not have. `gh project` has no `field-edit`, and the GraphQL alternative
(`updateProjectV2Field` with `singleSelectOptions`) takes the **whole option list and
replaces it**. Running it would mint new option ids for Todo / In Progress / Done and
**unset the Status of every existing card**.

**Tell the user to add `Hold` in the board UI** (Settings → Status → add option). It is
one click and it is not worth the blast radius.

If `Hold` does not exist, the skills still work — `triage` simply has no parked state to
protect, and every card it sees is fair game for `next-issue`. Say that plainly rather
than implying the board is broken.

⚠️ **Never hardcode a field or option id** into `workflow.json` or anywhere else.
Resolve them from `field-list` in the same run that uses them.

## 6. Confirm the agents

The workflow's quality comes from two subagents, and a user who does not know they exist
will never notice when they silently are not running.

| Agent | Runs at | Used by | Returns |
|---|---|---|---|
| `issue-planner` | `effort: max`, read-only | `next-issue`, `autopilot` | The scoping plan — and **REVIEW LENSES**, which decides the next step |
| `diff-reviewer` | `effort: max`, read-only | `next-issue`, `autopilot` | Findings through one lens: `correctness`, `contract`, `scoping`, `tests`, `deploy` |

### 🚨 Detect shadowing — do not just warn about it

**A same-named agent in `~/.claude/agents/` or the project's `.claude/agents/` wins, and
the plugin's copy never runs.** There is no error, no warning, and the shadowing agent
still returns a good-looking result — so every symptom points at the plugin's file, which
is not the file executing.

MEASURED: five consecutive agent runs were spent tuning a plugin agent file that nothing
read, because an older same-named agent sat in `~/.claude/agents/`. Four separate
explanations were constructed for the resulting "non-compliance". All were void. **Prose
warning this was already in this skill and was ignored** — which is why it is now a check
you run, not a paragraph you read.

```sh
claude plugin list          # "No plugins installed" -> NOTHING in the plugin is loaded
ls ~/.claude/agents/ .claude/agents/ 2>/dev/null
```

For each of `issue-planner` and `diff-reviewer`, report explicitly:

| Finding | What it means |
|---|---|
| plugin not installed | **Stop.** Every skill here is inert. Install it, or run `claude --plugin-dir <path>`. |
| same-named file in `~/.claude/agents/` | That file runs. The plugin's copy is dead. |
| same-named file in `.claude/agents/` | Same, and it also shadows the user-level one. |
| neither | The plugin's agents are live. |

**If a shadow exists, say which file will actually execute, by absolute path.** Do not
delete or rename it — it may be deliberate and it may be older and better. The user
decides; you only make the invisible visible.

⚠️ **The namespaced name is the reliable one.** `gh-issue-flow:issue-planner` always
resolves to the plugin's copy; a bare `issue-planner` resolves to whichever wins. Prefer
the namespaced form when spawning.

🚨 **Agent discovery happens at SESSION START.** Editing an agent file — or adding a new
one — changes nothing for the session already running; the spawn fails with
`Agent type '<name>' not found` listing the agents as they were at launch. Measured.

So an agent edit cannot be tested in the session that made it. **Restart with the plugin
loaded, then measure:**

```sh
claude --plugin-dir <path-to>/plugins/gh-issue-flow
```

`/reload-plugins` refreshes skills; do not assume it re-resolves agent types.

Two things worth telling the user once, because they are not obvious:

- **They pin `effort: max` regardless of the session's own effort**, so planning and
  review run at full reasoning even from a cheap session. Implementation does not — a
  skill cannot pin the main loop's effort.
- 🚨 **A subagent cannot fan out.** `diff-reviewer` is spawned **N times from the parent
  in one message**, one per lens. A single reviewer asked to "check everything" is a
  different, weaker thing.

## 7. Report

Print three blocks, in this order:

**Configured** — what was probed and written, each with where it came from:

| Setting | Value | Source |
|---|---|---|
| integrationBranch | `origin/dev` | `gh repo view` default branch |
| validate | 3 commands | `.github/workflows/ci.yml` job `test` |

**Created** — labels and board fields, with anything skipped because it already existed.

**Missing — and who can fix it.** The honest half. Separate what a human must do from
what is merely absent:

| Gap | Effect | Fix |
|---|---|---|
| No `Hold` Status option | No parked state; every Todo card is pickable | Board UI, one click |
| `.claude/` is gitignored | Config is local-only; teammates get nothing | Add `!/.claude/workflow.json`, needs a PR |
| No area labels yet | Triage cannot route assignees | Tell me your areas and I will create them |
| Branch unprotected | Nothing blocks a red merge | Repo settings — a deliberate choice |
| `commit.gpgsign` unset | Skills stop on a signing failure | `git config commit.gpgsign true` |

Close with the **one next command** the user should run — usually
`/gh-issue-flow:triage dry run` — and a one-line map of what follows it:
`triage` gates issues → `next-issue` or `autopilot` works them → `work-summary` reports.

⚠️ **Read back anything you created before claiming it.** `gh` exits 0 on writes the
server rejected, so a report listing labels or fields you never actually made is the
exact failure this skill exists to prevent. Re-list and count.

🚨 **But board writes are eventually consistent — labels are not.** A label read-back is
immediate and trustworthy. A Projects v2 read-back is **not**: measured, an `item-list`
immediately after adding items reported 0 while every add had in fact succeeded, settling
~30s later. Poll with backoff before concluding a board write failed, and prefer
resolving a returned item id over counting. See
[`../../reference/verification.md`](../../reference/verification.md).

## What this cannot give you

Say these plainly rather than letting the user discover them:

- **Issue hygiene.** Triage's guarantees are about *routing*, not content. Issues with
  no acceptance criteria stay un-`agent-ready` forever, and that is correct.
- **A green gate.** If the repo's suite is red on the integration branch, "any red is
  yours" stops being true and every skill's validation step degrades. Fix the base first.
- **Review bots.** The babysit loop watches whatever checks and review threads exist. It
  does not install a bot for you, and with none configured the review half of the loop
  has nothing to watch.
