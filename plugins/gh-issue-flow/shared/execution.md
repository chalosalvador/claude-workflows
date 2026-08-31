# Shared execution reference

The mechanics every skill here needs: how to branch, validate, review, babysit a PR,
and move a board card.

**This file holds FACTS, not policy.** Skills deliberately have inverted operating
principles — `next-issue` pauses for the user and merges on their go-ahead;
`autopilot` runs unattended, never merges, and hands back when anything is ambiguous.
Selection criteria, pauses, backpressure, labels, handback and caps live in the
skills. Only what would be *identical either way* belongs here.

It exists because these had already drifted once: the same command appeared in two
skills with different — and in places wrong — content. **If you change a command
here, you change it for every skill.** If you want different content per skill, it is
policy: put it back in the skill.

Config resolution: [`config.md`](config.md). Read it first — everything below is
written against those placeholders.

---

## 1. Branching

**Always `git fetch` and branch off the REMOTE ref explicitly:**

```sh
git fetch origin
git checkout -b feat/<N>-<slug> "<integrationBranch>"
```

Fetching is not pulling. A local branch does not move when you fetch, and local
checkouts routinely sit dozens of commits behind — building on one has produced a PR
on a five-commit-stale base.

**Work in a dedicated worktree**, never a shared main checkout — see
[`../reference/parallel-agents.md`](../reference/parallel-agents.md) for why, and for
the `git reset --soft` trap that silently reverts merged work.

---

## 2. Validation gates

Run the repo's gate and get it **green** before opening anything.

Commands come from `workflow.json` → `validate`, or are probed per
[`config.md`](config.md) Layer 3. **Run them verbatim; do not retype from memory** —
the reason this lives in one file is that duplicated copies rotted (a prefetch script
that had been renamed, so the first command errored; a linter path list missing four
directories).

### 2.0 Preflight

Run `workflow.json` → `preflight` first, if present. A tool the gate shells out to
may be a **machine-level** dependency that neither the lockfile nor the package
manifest installs — and under the reduced `PATH` of an unattended run it is simply
not found.

**Absent → stop and say so with the install line.** For an unattended run that is a
handback.

### 2.1 The suite is GREEN on the integration branch — so any red is yours

Do not wave red through as pre-existing. Two classes that are genuinely **not** your
change:

- **Collection/import errors naming a dependency** → stale virtualenv. Reinstall from
  the lockfile and re-run.
- **A wave of failures in a FRESH worktree** → gitignored assets (model weights,
  fixtures) that a worktree does not inherit. Run the repo's prefetch, or symlink
  them from the main checkout.

⚠️ **Never gate on a test COUNT.** A growing suite can move by dozens between a morning
and an afternoon, so a hardcoded number goes stale within days and then misleads.
Green-vs-red is the gate. For a true baseline, run the suite on the merge-base *before*
you edit.

⚠️ **Green locally + red in CI on anything inventory- or count-shaped is usually the
BASE having moved**, not flake — CI tests head merged with base. See
[`../reference/git-and-github.md`](../reference/git-and-github.md).

⚠️ **Green locally + red in CI on a framework internal is usually DEPENDENCY SKEW.** A
floating upper bound (`>=x,<y`) means CI resolves a newer release every run while a
long-lived local environment keeps whatever it first installed. See
[`../reference/secrets-and-ci.md`](../reference/secrets-and-ci.md) — including why you
probably cannot reproduce the CI version locally, and what to say instead of implying
local proof.

### 2.2 Tests are part of the gate

Add or extend tests for what changed. **Mutation-check any new test**: break the code
it covers and confirm it fails. A test that passes against broken code is worse than
no test — it reads as proof. **State the mutation result in the PR body.**

If the change adds a guard, invariant, or scan-style test, read
[`../reference/guard-tests.md`](../reference/guard-tests.md) before writing it, and
[`../reference/mutation-harness.md`](../reference/mutation-harness.md) before
believing any harness number.

### 🚨 When the gate cannot see the diff, say so and define manual acceptance

A docs, config, or comment change often touches nothing the gate reads. The gate is then
**green identically before and after** — which proves the branch broke nothing and proves
*nothing at all* about whether the change is correct.

Reporting that bare green as verification is the failure. Instead: **say the gate is
blind to this diff, and state the manual acceptance you actually ran.** For a documented
command, that is running it from a clean environment. For a config value, reading it back
from the system that consumes it.

⚠️ **A fresh-clone acceptance measures the COMMITTED tree.** `git clone` — of a repo or of
a worktree — copies commits, not your working tree, so an acceptance run before you commit
silently tests the OLD content and reports the bug you just fixed. **Commit first, then
clone.** Measured; same family as
[`../reference/mutation-harness.md`](../reference/mutation-harness.md) way #1.

The upside: that pre-commit run is a valid **control**. Keep it and report both
directions — pre-fix reproduces, post-fix passes.

### 2.3 Spec flow

When `workflow.json` → `specFlow` is `openspec`, see
[`../reference/openspec.md`](../reference/openspec.md) for the commands, the install,
and — importantly — **what a green validate does and does not assert.** Do not report
a bare green from it.

---

## 3. Code review — parallel `diff-reviewer` subagents

**Full method: [`../reference/review-process.md`](../reference/review-process.md).**
Read it before the first review of a session.

Before committing, spawn `diff-reviewer` subagents (read-only, `effort: max`, fresh
context) **in parallel — one message, several tool calls** — one per lens:
`correctness`, `contract`, `scoping`, `tests`, `deploy`. Give each the diff location
and enough issue context to judge intent.

⚠️ **A built-in `/code-review` skill may be `disable-model-invocation`, meaning a
session cannot invoke it and the call errors.** Do not put it in a workflow step. (It
was in one here until it was noticed, which meant PRs shipped claiming a review that
never ran.) The user can still type it themselves; this is the step a *session* can
execute unaided.

**Fire only the lenses that apply.** `issue-planner` names them under **REVIEW
LENSES**; gate on that rather than always firing five. A max-effort lens on a diff it
cannot touch buys nothing.

### 3.1 Cost discipline

**This subsection is the single source for spend rules. Skills link here; they do not
restate it.**

Measured on a one-line docs fix: planner 42k tokens, two lenses 67k, **~110k total**. The
dominant waste was not review depth — three agents each cloned the repo, built their own
environment and read the same files. Roughly a third of the spend, buying nothing.

Four levers, in order of saving:

1. **Pass the planner's `HANDOFF` block to every lens**, verbatim, plus the gate result
   and the worktree path. This is the one that removes the duplication above.
2. **Gate the lens list** on the plan's REVIEW LENSES. Five lenses where two apply is
   more than double.
3. **Tier the `model` per spawn**, by the issue's size label:

   | Label | Planner | Lenses |
   |---|---|---|
   | `effort:easy` | `sonnet` | `sonnet` |
   | `effort:medium` | inherit | inherit; `sonnet` for a narrow lens |
   | `effort:hard` | inherit (strongest) | inherit |

   ⚠️ **`model` is a per-spawn argument; `effort` is frontmatter-only and cannot be
   overridden.** That asymmetry is why tiering goes through the model.

4. **Let the planner scale its own output** (its own frontmatter carries the budget).
   Every word is paid for twice — once written, once read by each lens.

🚨 **None of this is a reason to skip the review.** Scale it to the change; never cut it
across the board. What is being removed is *duplicated research*, not scrutiny — and a
handoff tells a reviewer where to look, never what to conclude.

Adjudicate the merged findings yourself: fix every valid one, and for any you reject
**say so with the reason in the PR body, never silently.**

### Re-review the delta when the fixes added NEW LOGIC

Code written to satisfy a reviewer was never itself reviewed. If adjudicating
introduced a new branch, gate, condition, or code path, spawn **one** more
`diff-reviewer` (`correctness`) over just that delta. Skip it when the fixes were only
tests, comments, messages, or docs. **Once — a conditional pass, not a loop.**

⚠️ **Commit before spawning lenses**, and do not edit files while one is running —
they mutate the shared worktree. See
[`../reference/parallel-agents.md`](../reference/parallel-agents.md).

---

## 4. Commit and PR

- Branch `feat/<N>-<slug>`; commit referencing `Fixes #<N>`.
- **Every commit GPG-signed.** Never pass `--no-gpg-sign`. If signing fails, **stop**
  and surface it — do not push unsigned.
- **Never commit secrets.** If the work appears to need a credential, that is a gate
  failure, not something to work around.
- When `specFlow` is set, **archive the spec change as the last commit of the SAME
  pull request**, before the push — not after the merge. A post-merge archive is
  unimplementable for any flow that does not merge.
- Cross-repo: write `owner/repo#N`, and close the tracking issue plus flip its board
  card by hand.

🚨 **Never write a closing keyword next to `#N` when the merge must NOT close the
issue — even negated.** GitHub's parser does not read negation, and review bots append
sections to your PR body after you write it. Read the issue state back after merging.
See [`../reference/git-and-github.md`](../reference/git-and-github.md).

---

## 5. Babysitting a PR to green

⚠️ **Do not assume a `/babysit-prs` skill exists.** Do the loop inline, or arm a
`Monitor` on the checks plus the unresolved-thread count and let it wake you.

Read the repo's actual protection rather than trusting any written claim — this is
the thing most likely to have moved:

```sh
gh api repos/<owner>/<repo>/branches/<b>/protection
```

What matters from it: the **required checks**, whether `strict` is set (must be up to
date with base — if false, concurrent PRs do not serialize), `enforce_admins` (if
true, a red check cannot be bypassed by anyone), and whether **conversation resolution
is required** — which makes an unresolved review thread block the merge button
outright, so resolving threads is not just hygiene.

**Watch two things, not one.** A review bot may report as a required *check* while its
findings arrive as review **threads** — a checks-only poll sees the status and none of
the substance, and threads must be resolved separately from the check going green.

```sh
gh pr checks <PR> --repo <owner>/<repo> --json name,bucket

gh api graphql -f query='{repository(owner:"<owner>",name:"<repo>"){
  pullRequest(number:<PR>){reviewThreads(first:50){nodes{id isResolved
  comments(first:1){nodes{databaseId author{login} body}}}}}}}'
```

Each round, until green and quiet:

- **Red check** → fix if the cause is yours, re-push, wait again.
- **Review-bot thread** → treat as a real finding. Fix it, reply on the thread with
  what changed and why, then **resolve** it. If it is wrong, say so on the thread with
  the reason — never resolve in silence. A fix that adds new logic gets the § 3 delta
  re-review before you push.
- Re-check **all checks green and 0 unresolved threads** after the final push, and
  again **at the merge instant**.

```sh
gh api repos/<owner>/<repo>/pulls/<PR>/comments/<COMMENT_ID>/replies -f body='…'
gh api graphql -f query='mutation($t:ID!){resolveReviewThread(input:{threadId:$t}){thread{isResolved}}}' -f t='<THREAD_ID>'
```

🚨 **Reply, verify, THEN resolve — never resolve first.** `gh api` exits 0 on a 502,
so a reply that never posted plus an eager resolve leaves a thread
resolved-in-silence. Read the state back. And a **missing** required check is not a
passing one: a conflicting PR skips its workflow entirely. See
[`../reference/verification.md`](../reference/verification.md) and
[`../reference/git-and-github.md`](../reference/git-and-github.md).

⚠️ **A passing bot check is not evidence of zero findings** — findings can fail to
post as threads and sit in a collapsed section of its summary comment. Read the
summary body. See
[`../reference/review-process.md`](../reference/review-process.md).

Green CI and a green bot are **never** sufficient evidence a control holds — they are
the floor, not the gate. Expect several rounds on anything security- or
correctness-shaped, including holes each earlier fix just opened.

---

## 6. Board tracking

Ids and queries: [`config.md`](config.md). Resolve field and option ids dynamically
every run; `--limit 1000` is mandatory.

Every issue carries an assignee, a Priority, a Status and a Track (or that board's
equivalents). **Done is set only at merge** — and for an unattended run, only by a
human.

⚠️ **Never move a Status that means "a human parked this by choice"** (commonly
`Hold`). It is orthogonal to a `blocked` label: Hold = *won't* do now; `blocked` =
*can't*, with a "Blocked by: #n" pointer. Flipping Hold to Todo un-decides a human's
call.

---

## 7. Deploy consequences

**Read the workflow, not a written summary.** Determine, per repo:

```sh
grep -rl "branches:" .github/workflows/ | xargs grep -l "<integration-branch>"
```

Then read that workflow's `paths` / `paths-ignore`. Two rules decide the answer, and
missing them is what has actually gone wrong:

- **`paths-ignore` is all-or-nothing per push.** One changed file outside the list
  arms the whole workflow; the other twenty being ignored count for nothing.
- **`tests/**` and `.github/workflows/**` are commonly NOT ignored**, so a test-only
  or workflow-only change **does** deploy. The test you added in § 2.2 can itself be
  enough to arm it.

⚠️ **"Not baked into the image" is not the same as "does not trigger the workflow."**
A Dockerfile copying an explicit file list means some paths can never reach the image
— and that is irrelevant to whether the workflow *fires*, which only `paths-ignore`
decides. Conflating the two produced a wrong deploy note: it was written while the
diff was four ignored files, a review fix then added a test file, and the claim was
never re-checked. It rolled.

🚨 **Re-derive the deploy claim from the FINAL diff, after review fixes** — not from
the diff you planned. `git diff <base>...HEAD --name-only`, then check every path
against the live list. **When unsure, say it deploys**: an over-cautious note costs a
reviewer nothing, and a wrong "this is safe" is the one they act on.

`paths:` filters resolve **last-match-wins**, so pattern *order* is the semantics —
see [`../reference/git-and-github.md`](../reference/git-and-github.md).

**Infrastructure apply is usually NOT in the CD path.** Applying it is a deliberate
manual step: **ask first**. Flag destructive or non-additive migrations before they
land; additive nullable columns are generally safe.
