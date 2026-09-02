---
name: autopilot
description: >-
  Work the agent-ready issues unattended. Picks up to 2 gated issues off the project
  board, then for each: plans it with issue-planner, implements it in an isolated git
  worktree, runs the repo's full validation gate, reviews the diff with parallel
  diff-reviewer lenses, opens a ready-for-review PR requesting review from the issue's
  assignee, and drives CI + review threads to green under a 45-minute cap — never
  merging, never touching infra. Use for "run the autopilot", "work the easy issues",
  "pick up the agent-ready queue", or as a scheduled unattended-work routine.
---

# Autopilot — unattended easy issues

Turn `agent-ready` issues into reviewable PRs while nobody is watching.

This runs with **no human in the loop**, so the operating principle is inverted from
[`next-issue`](../next-issue/SKILL.md): when anything is ambiguous, **stop and hand it
back** rather than making a judgment call. A skipped issue costs a day. A confidently
wrong PR costs a teammate's afternoon and their trust in the routine.

Resolve board, repos, branches and gate commands via
[`shared/config.md`](../../shared/config.md).

## 🚨 Two hard rules, no exceptions

1. **Never merge.** Merging the integration branch may auto-deploy and run migrations.
   This includes **queuing** a merge: never run `gh pr merge` in any form, and
   specifically not `--auto`. Where auto-merge is enabled and required approvals are 0,
   a queued PR lands green, unattended and unreviewed — which is the whole thing this
   routine hands back to a human to prevent.
2. **Never edit outside the worktree.** The user's own checkouts stay untouched.

## Workflow

```
- [ ] 1. Backpressure check — is the review queue already full? (if yes: stop)
- [ ] 2. Select up to 2 candidates from the agent-ready queue
- [ ] 3. Re-verify the gate yourself — do NOT trust the label alone
- [ ] 4. Claim it: `agent-wip` + board In Progress
- [ ] 5. Isolate + re-base onto the REMOTE integration branch (the base is stale by default)
- [ ] 6. Plan it: delegate to `issue-planner`; post the plan on the issue
- [ ] 7. Spec change from the plan's SPEC IMPACT, then implement the issue's scope
- [ ] 8. Run the repo's full VALIDATE gate until green
- [ ] 9. Review: parallel `diff-reviewer` subagents, one per lens the plan named
- [ ] 10. Archive → signed commit → push → PR ready-for-review → request review
- [ ] 11. Babysit to green — CI + review threads, under a 45-minute cap
- [ ] 12. Board + labels; clean up the worktree
- [ ] 13. Report: what shipped, what was skipped and why
```

Any step that cannot be completed honestly → **§ Handing it back**.

**Effort.** Planning and review run at `effort: max` from the `issue-planner` /
`diff-reviewer` frontmatter, so it is automatic regardless of how the run was launched.
**Implementation runs at the session's own effort** — a skill cannot pin the main
loop's effort, and a scheduled-task tool may not set it either. Set it in the routine's
own configuration if a given routine needs more than the default.

💰 **Spend rules — model tiering, the handoff, lens gating — live in
[`shared/execution.md`](../../shared/execution.md) § 3.1.** Autopilot-specific: only
`effort:easy` issues pass § 3's gate, so **the cheap tier is the common case here**. If
the work turns out bigger than `easy`, that is a handback — never a reason to quietly
upgrade the model and continue.

## 1. Backpressure

Unattended work piles up faster than humans review it.

```sh
for R in <owner/repo> <owner/repo>; do
  gh pr list --repo "$R" --state open --label agent-authored --json number,title,createdAt
done
```

**If 3 or more `agent-authored` PRs are already open, do nothing this run** — print the
open list and stop. The bottleneck is review, not authoring; a fourth PR makes the
queue worse. Also flag any `agent-authored` PR open more than 5 days as stalled.

## 2. Select candidates (max 2)

```sh
jq -r --arg ready "$READY_LABEL" '.items[] | select(.status=="Todo")
   | select((.labels // []) | index($ready))
   | select(((.labels // []) | index("agent-wip") | not)
            and ((.labels // []) | index("agent-blocked") | not)
            and ((.labels // []) | index("blocked") | not))
   | "#\(.content.number)\t\(.content.repository|sub(".*/";""))\tP:\(.priority // "-")\t\(.content.title)"' "$BOARD_JSON"
```

⚠️ `$BOARD_JSON` is this run's single board fetch — see
[`shared/config.md`](../../shared/config.md) § Board queries. Every later step that needs
the board reads that file; only a post-write read-back re-fetches.

**Repo scope.** When the caller names a repo — a scheduled routine pinned to one
checkout does — filter to that repo and ignore the other's cards entirely. A run pinned
to one repo that picks up another's issue **has no checkout to build in**. With no repo
named, you are running by hand and may take either.

Order by Priority (P1 → P3), then by age (oldest first — the queue should drain, not
churn). Take at most **2**. Empty queue → say so in one line and stop.

## 3. Re-verify the gate

**The `agent-ready` label is a hypothesis from a different day.** The issue may have
been edited, a dependency may have appeared, or triage may simply have been wrong.
Before touching code, read the issue + comments + the actual files and re-run the full
checklist in [`triage` § 4](../triage/SKILL.md).

Read it **once**, into a file — § 6 hands the same file to the planner:

```sh
ISSUE_MD="${SCRATCH:-${TMPDIR:-/tmp}}/issue-<N>.md"
{ gh api repos/<owner>/<repo>/issues/<N> \
    --jq '"# #\(.number) \(.title)\n\n\(.body // "")"'
  gh api repos/<owner>/<repo>/issues/<N>/comments \
    --jq '.[] | "\n---\n@\(.user.login):\n\n\(.body)"'
} > "$ISSUE_MD"
```

⚠️ REST on purpose — `gh issue view` is GraphQL, and an unattended run that plans two
issues is the last thing that should be spending the GraphQL budget on a read it can get
from the core one.

Bail immediately if the issue now: is `blocked`/`legal`/`compliance`/`security`/`epic`,
needs infrastructure or a migration, touches secrets/env/runtime config, changes an
analytics schema, needs two repos, or contains an unanswered product question.

**Also bail if you cannot name the files you are about to change** — that means you do
not understand it yet, and understanding it is the human's call.

Bailing here is a normal outcome, not a failure. → § Handing it back.

## 4. Claim it

```sh
gh issue edit <N> --repo <owner>/<repo> --add-label agent-wip
```

Set the board card Status → In Progress, keep the existing assignee. Post one short
comment: what you understand the scope to be, and that a PR is coming. **That comment
is the assignee's chance to shout before you spend the effort** — and their record of
what happened if they were asleep.

## 5. Isolate — and re-base onto the REMOTE tip

Never edit the user's own checkout. **Detect which situation you are in, don't assume:**

```sh
git rev-parse --is-inside-work-tree && git rev-parse --git-common-dir
# .git                       → main checkout; create a worktree
# a path with a separate git-dir → already in a worktree
```

**A. The routine gave you a worktree.** Do **not** nest another one. Just rename the
branch: `git branch -m feat/<N>-<slug>`.

**B. Run by hand from the main checkout.** Create one:

```sh
git fetch origin
git worktree add ../.autopilot/<repo>-<N> -b feat/<N>-<slug> "$INTEGRATION"
```

Prune stale ones first: `git worktree list` → `git worktree remove <path>` for any
whose branch is merged or older than 7 days.

### 🚨 In case A, the base is a LOCAL branch and is probably stale

The routine forks the worktree from a local `sourceBranch`, and **a local branch does
not move when you fetch.** Building on it produces a PR based on a checkout dozens of
commits behind — a mistake already made once here on a five-commit-stale base.

```sh
git fetch origin
git rev-parse HEAD               # must equal ↓
git rev-parse "$INTEGRATION"
git reset --hard "$INTEGRATION"  # only in a FRESH worktree, nothing to lose
```

Confirm `git status --porcelain` is empty **before** the reset — if it is not, something
already went wrong; hand it back rather than discarding work.

⚠️ Never squash with `git reset --soft "$INTEGRATION" && git add -A` — see
[`../../reference/parallel-agents.md`](../../reference/parallel-agents.md) for how that
silently reverts merged work with a clean `git status` and a green suite.

## 6. Plan it — delegate to `issue-planner`

Do this in the worktree, *after* the re-base, so the plan reflects the base you will
actually build on.

Spawn `issue-planner` (read-only, `effort: max`) with the issue number, repo, worktree
path, and **`$ISSUE_MD` from § 3 pasted verbatim — body and comments both**. A subagent
starts blank: every fact you hold and do not pass is one it pays to fetch again.

🚨 **State the tier, and name no sections.** MEASURED: a prompt that said "skip the SPEC
IMPACT section" and "your REVIEW LENSES section is load-bearing" made the planner emit
all eight sections including every one its tier suppresses — naming a section
re-establishes the whole vocabulary, and the caller's prompt beats the agent's own rules.

Pass the facts, not the shape:

```
Tier: S            # from the issue's effort label; the planner's own table defines the tiers
Issue body + comments: <contents of $ISSUE_MD, verbatim — do not re-fetch these>
Repo has no spec flow.
Integration branch: <branch>. Merging it <deploys X / is inert>.
Gate: <commands>
Worktree (read-only): <path>
```

Let the planner decide what to emit. If you need something specific back, ask for the
*fact* ("which reviewers does this diff need?"), never for the *section*.

Three things depend on it, so it is **not optional**:

- **REVIEW LENSES drives § 9.** Firing all five lenses on every diff is waste, and
  guessing which apply is exactly the judgment call an unattended run should not make.
- **SPEC IMPACT drives § 7's change directory.** It names the change, the target
  capability, and the delta-vs-`skip_specs` call. Choosing a capability yourself means
  inventing one, which the spec config forbids.
- **It is a second gate.** If the plan comes back naming infrastructure, a migration, a
  schema change, secrets, or an unanswered product question that § 3 missed, that is a
  late gate failure → § Handing it back. A plan that cannot name the files is the same
  signal as § 3's bail — and so is one that cannot name a capability or justify
  `skip_specs`.

Post the returned plan as a comment on the issue, folded into the § 4 claim comment if
you have not commented yet. **Unattended or not, the assignee should be able to read
what you understood before reading the diff.**

## 7. Implement — the issue's scope

### First, the spec change — before any code

Build the change directory from the plan's SPEC IMPACT and gate on its validate. Two
cases, and the difference matters more unattended than with a human watching — see
[`../../reference/openspec.md`](../../reference/openspec.md) for both, the Purpose
trap, and what a green does not assert.

🚨 **`skip_specs` disables validation for the change entirely.** The justification is a
claim the *reviewer* has to check by eye — exactly the kind of claim an unattended run
must not overstate. **If you cannot write a reason that survives being read by a
skeptic, that is a handback, not a `skip_specs`.**

### Then the code

Stay inside what the issue asks for. **An unattended run is the worst possible place for
opportunistic refactors:** the reviewer cannot tell your improvement from your mistake,
and every extra hunk is a reason to reject the whole PR. Follow the conventions already
in the file; match its idiom.

### The fold-in threshold — when to just fix it here

The fence above is not a reason to defer everything. **Fold it into this PR** when *all
four* hold:

1. It is in a file **this diff already touches**.
2. It needs **no new test** — the tests you are already writing cover it, or it is not
   behavior (a typo, stale comment, wrong docstring, dead import on a line you are
   editing anyway).
3. It adds **no new branch, gate, condition, or code path** — the same "new logic"
   trigger that forces a delta re-review in § 9.
4. It moves **no contract** — no wire format, response shape, field name, env var,
   migration, or board/label semantics.

Anything failing one → **"Noticed, not fixed"** in the PR body: a *one-line note to the
reviewer*, not a new issue.

**Do not open a follow-up issue for it.** Filing costs a triage pass, a board card with
Priority/Status/Track, an assignee, and a future branch — for a two-line fix in a file
you already had open, that is more process than the fix. Only file when the reviewer,
reading your note, would have to open one anyway: real scope, real sequencing, a
decision someone has to make.

**Never commit secrets.** If the implementation appears to need a credential, that is a
gate failure → § Handing it back. Credential and env changes are hand-work for a reason —
the provisioning tools store empty values, trailing newlines and write-only types without
erroring, and every failure surfaces far from the cause:
[`../../reference/secrets-and-ci.md`](../../reference/secrets-and-ci.md).

## 8. Validation gate

**Commands: [`shared/execution.md`](../../shared/execution.md) § 2, verbatim.** Do not
retype from memory — this section used to carry its own copy, and that copy named a
script that had been renamed (so the first command errored) and hardcoded a test count
~1400 tests stale (so the "any red is yours" rule was anchored to a number that no
longer existed).

- **Any red is yours.** § 2.1 lists the two classes that are genuinely not your change.
  Anything else red → § Handing it back, rather than a judgment call about whether it
  matters.
- **Never gate on a test COUNT.** Green-vs-red is the gate.
- Add or extend tests, and **mutation-check them**. A PR from an agent with no test is
  one a reviewer must verify entirely by hand; a PR with a test that passes against
  broken code is worse.

## 9. Code review

**Procedure: [`shared/execution.md`](../../shared/execution.md) § 3.** Parallel lenses
gated on the § 6 plan's REVIEW LENSES, then the delta re-review if the fixes added new
logic.

💰 Paste the plan's `HANDOFF` block into every lens prompt, plus the § 8 gate result and
the worktree path — [`shared/execution.md`](../../shared/execution.md) § 3.1.

⚠️ **Never a `disable-model-invocation` built-in review skill** — the call errors. This
step said to run one until it was noticed, which meant unattended PRs shipped with **no
adversarial review at all** while this file claimed they had been reviewed. That is the
failure mode this skill can least afford: nobody was watching.

Unattended specifics: fix every valid finding; for any you reject, **put the reason in
the PR body** — a silent drop is invisible to the only human who will look. If review
surfaces something that changes the *shape* of the fix, that is a scope escape →
§ Handing it back.

## 10. Archive, commit, push, PR

**Archive first — it is the last commit of this PR, not a post-merge step.** This
routine never merges, so a merge-gated archive would never run at all.

Read the archive JSON, not just the exit code: the updated-specs flag **must match the
plan's call**. Exit 0 alone does not distinguish "folded the delta" from "there was
nothing to fold", so a silently-empty delta reads as success. A mismatch is a handback:
it means the change directory does not say what the plan said it would.

```sh
git add <explicit paths> && git commit -m "<type>: <what> (Fixes #<N>)"   # GPG-signed
git push -u origin feat/<N>-<slug>
```

⚠️ **All commits GPG-signed.** Never `--no-gpg-sign`. If signing fails, **stop** — do
not push unsigned. Surface it in the report.
⚠️ **Stage explicit paths, never `git add -A`** — see
[`../../reference/parallel-agents.md`](../../reference/parallel-agents.md).

Open the PR **ready for review** against the integration branch, with
`--label agent-authored`, and request review from **the issue's assignee**; if
unassigned or assigned to the agent's own account, request the lead.

🚨 **`gh pr edit --add-reviewer` exits 0 when GitHub silently refuses the request.**
MEASURED: requesting review from the PR's own author returns exit 0 and adds nobody —
GitHub does not allow self-review. That is the normal case on a solo repo, or whenever
the run authenticates as the lead it is trying to notify. **Read it back:**

```sh
gh pr view <n> --json reviewRequests --jq '[.reviewRequests[].login]'
```

If it comes back empty, the notification never happened. **Fall back to an @-mention in a
PR comment**, which does notify, and say in the report that no reviewer could be
requested and why. Never report "review requested" off the exit code.

Tag them in the body too — a requested review alone is easy to miss.

PR body must contain, in order:

- `Fixes #<N>` (use `owner/repo#N` across repos)
- **What changed** — 2–4 lines, plain language. 🚨 **If the plan contradicted the
  issue's own diagnosis, lead with that.** The reporter needs to learn what was actually
  wrong, and a reviewer skimming for "does this match the issue" will otherwise read the
  mismatch as scope creep.
- **How it was verified** — the exact gate commands and their result, plus the
  mutation-check result for any new test
- **Noticed, not fixed** — anything out of scope you saw
- **Spec** — which change was archived, and whether specs were updated or the change
  carried `skip_specs` with what reason. On a `skip_specs` change **say plainly that the
  validate gate asserted nothing**, so the reviewer knows the justification is theirs to
  check.
- **Deploy note** — state whether merging deploys. 🚨 **Only claim a diff does NOT
  deploy if you checked every changed path in the FINAL diff against the live
  `paths-ignore`** ([`shared/execution.md`](../../shared/execution.md) § 7) — it is
  all-or-nothing per push, and `tests/**` is commonly not ignored, so the test you added
  in § 8 is itself enough to arm the deploy. **When unsure, say it deploys.** This is
  the one that has actually gone wrong.
- A closing line: *opened unattended by autopilot; not merged — <reviewer> decides.*

⚠️ **Never write a closing keyword next to an issue number you do not want closed, even
negated** — and note that review bots append sections to your body after you write it.

🚨 **Read every mutation back.** `gh` exits 0 on rejected writes, so an unattended run
can report a PR opened, a label swapped or a thread resolved that never happened — and
nobody is watching to notice. After the PR: `gh pr view <n> --json state,url,isDraft`.
See [`../../reference/verification.md`](../../reference/verification.md).

## 11. Babysit to green — 45-minute cap

**Loop and commands: [`shared/execution.md`](../../shared/execution.md) § 5.** Watch
checks **and** review threads — an old version of this step polled checks only, so a
bot's findings were never seen. Do not assume a babysit skill exists; do the loop
inline, or arm a `Monitor` and let it wake you.

**The 45-minute cap is a hard stop, from the first push.** It is what keeps an
unattended run bounded, and bounded is the whole point of the caps and the backpressure
rule. When it expires:

- **Green with threads outstanding** → leave the PR ready for review; an annotated PR is
  still reviewable. Comment naming the open threads.
- **A check still red** → convert to **draft**. Never leave a red PR sitting as
  ready-for-review.
- Either way, **report exactly where it stopped.** Never claim a green you did not watch
  land, and never claim threads are resolved that are not.

This step does not merge. Ever.

## 12. Bookkeeping

- Swap labels: remove `agent-wip`, keep `agent-ready` (the PR is the state now).
- Card stays **In Progress**. Only a human sets Done at merge.
- Remove the worktree after babysitting finishes; keep the branch.

## 13. Report

One compact block per issue attempted:

| Issue | Repo | Outcome | PR | Gate | CI / threads at cap | Reviewer |
|---|---|---|---|---|---|---|

The **CI / threads** column is the honest end-state of § 11 — `green / 0 open`,
`green / 2 open`, `red — drafted`, or `cap expired, 3 checks still running`. It is the
column a human scans to decide what still needs them. **There is no `n/a` value** — if
a repo has required checks, a row reporting `n/a` is a step that was skipped, not one
that did not apply.

Then a **Skipped** list — every candidate you passed on, with the one-line reason.
**This is the most valuable half of the report:** it is how the human learns that
triage's `agent-ready` calls are drifting, and it is the input to fixing the gate.

## Handing it back

Whenever you stop early — gate re-verification failed, validation stayed red, scope
escaped, signing failed, anything ambiguous:

1. `gh issue edit <N> --add-label agent-blocked --remove-label agent-ready,agent-wip`
2. Comment on the issue: what you tried, exactly where it stopped, and what a human
   needs to decide. Concrete and short.
3. Set the card back to **Todo**.
4. Delete the branch and remove the worktree — leave no half-finished state.
5. Include it in the report's Skipped list.

**`agent-blocked` is sticky on purpose:** the queue must not retry it tomorrow and
produce the same failure every night. A human removes it after deciding.
