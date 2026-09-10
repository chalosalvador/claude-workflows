# Git and GitHub: traps that silently change the answer

---

## Diff scope: three dots, always

To check "does this PR touch only `tests/`?", use **three dots**:
`git diff <base>...HEAD` (diff from the merge-base). **Two dots** diffs the two
commits directly, so anything that landed on the integration branch *after* you
branched shows up **inverted** — a file the base deleted appears as your branch
adding it back.

The distortion is not small: a one-file, tests-only change can show as dozens of files
and hundreds of insertions, among them a directory the base just deleted, so the PR reads
as re-adding it.

GitHub renders PRs with merge-base semantics, so **the three-dot diff is what the
reviewer actually sees.**

> A review subagent told to run two-dot can report a clean file list and still be
> right *at that moment* — the discrepancy only appears once the base moves.
> **Re-check with three dots immediately before opening the PR.**

---

## CI tests head MERGED WITH base, so "green locally, red in CI" is often neither flake nor environment

GitHub's `pull_request` event checks out the **merge** of head and base, not head.
The two runs are testing **different trees**.

A guard that pins every file under an archive directory is green locally and red in CI
when the base archives another change after the push: CI counts the base's files too,
and the failure names directories that do not exist on the branch at all.

**When CI reds on something inventory- or count-shaped and the branch is green,
check whether the base moved before assuming flake:**

```bash
git fetch origin && git merge-base --is-ancestor <integrationBranch> HEAD   # the remote ref — never `main` by assumption
```

- To reproduce locally, **merge the base in first** — the local suite alone cannot
  see the defect.
- **Re-verify the base at the MERGE INSTANT**, not merely when checks go green.
  Between "all green" and clicking merge the base can move, and the squash then reds
  the integration branch itself.
- A matching file **count** is not proof the base is current — two independent
  additions can coincide numerically. Compare ancestry.
- `--match-head-commit` guards the PR **head**, not the base. It does nothing here.

**Do not fabricate the SHA for `--match-head-commit`.** Abbreviating the head
yourself and padding it produces `GraphQL: Head branch was modified` and reads like a
real race. Read it: `gh pr view <N> --json headRefOid --jq .headRefOid`. It needs the
full 40 chars.

---

## A conflicting PR SKIPS its workflow — the check goes MISSING, not red

When the base moves and the PR conflicts, GitHub cannot build a merge ref, so the
`pull_request` workflow **never fires**. `gh pr checks` then shows a healthy-looking
list — every other check green — with the required one simply **absent**. Nothing
announces it.

```bash
gh pr view <N> --json mergeable,mergeStateStatus
```

Confirm the required check is **present**, not merely that nothing is failing.

`mergeable` is computed **asynchronously**: right after a push it can report a stale
value, such as `CONFLICTING/DIRTY` on a branch that is actually `MERGEABLE`. Poll until
it settles before believing it.

---

## A NEGATED closing keyword still closes the issue

GitHub's linked-issue parser matches
`close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved` + `#N` and **does not
read negation in front of it.**

Commits that all say `Refs #N`, never `Fixes`, do not keep the issue open: with zero
closing keywords in the squash message it still closes when a review bot appends a
summary to the PR body containing:

> **Merging does not close #N** until Terraform is applied.

`close #N` matches, so **the sentence written to say the issue must stay open is what
closes it.** Board automation then flips the card to Done, and nothing in the repo
detects it.

- Never write a closing keyword next to `#N`, *even negated*. Phrase it as
  "#N stays open until …" — no keyword within ~1 token of the number.
- **You do not control the whole PR body.** Bots append sections after you write
  it, so a body clean at creation can acquire one.
- When the merge must NOT close the issue, **read the issue state back after merging**
  and reopen if needed. Reopening does not restore the board card — set Status by hand.

---

## Writing a PR body

This section owns the shape; skills link here. The sections, in order:

- `Fixes #<N>`, or `owner/repo#N` across repos. When the merge must not close the issue,
  no closing keyword at all (the section above).
- **What changed** — 2–4 lines, plain language. **If the plan contradicted the issue's
  own diagnosis, lead with that**: the reporter needs to learn what was actually wrong,
  and a reviewer skimming for "does this match the issue" otherwise reads the mismatch
  as scope creep.
- **How it was verified** — the exact gate commands and their result, the mutation-check
  result for every new test, and, when the gate cannot see the diff, the manual
  acceptance you ran ([`../shared/execution.md`](../shared/execution.md) § 2).
- **History** — how the change evolved, what review found and how each finding was
  resolved (a rejected one with its reason, and whether the delta got its one re-review
  pass), and the measured results. This is the only place history is written; the code
  and the docs state the current behaviour ([`comments-and-docs.md`](comments-and-docs.md)).
- **Noticed, not fixed** — anything out of scope you saw, one line each.
- **For `repo.md`** — when the run measured something about the platform that the
  repo's `repo.md` § Traps does not say: one proposed bullet, undated and in the present
  tense. Proposed only; the reviewer commits it or drops it.
- **Spec** — which change was archived, and whether specs were updated or the change
  carried `skip_specs` with what reason. On a `skip_specs` change, say plainly that the
  validate gate asserted nothing ([`openspec.md`](openspec.md)).
- **Deploy note** — whether merging deploys, derived from the final diff as
  [`../shared/execution.md`](../shared/execution.md) § 7 says.

A skill may add its own closing line after these.

---

## `paths:` filters are ORDER, not membership

GitHub resolves `paths:` / `paths-ignore:` **last-match-wins**, so the *order* of the
patterns is the semantics. A test asserting `"terraform/cells/prod/**" in paths` reads
as equivalent to testing the filter and is not.

Moving two positive patterns to the end of the list — **every string unchanged** — keeps
a membership-style test green while previously-excluded paths begin matching, and so does
adding `- "**"`.

**Assert OUTCOMES over corpora of real paths** (`_MUST_MATCH` / `_MUST_NOT_MATCH`),
never membership. Import a shared evaluator rather than rebuilding one.

Two things an outcome test cannot do — pair it with shape rules:

- **Widening by ADDITION is invisible** to it; it only speaks about paths someone
  thought to list. Add a rule that no pattern reaches outside the intended tree.
- **A doubled `**/*.md` + `*.md` pair** must be asserted as membership: a model that
  collapses `**/` to zero segments treats the spellings as equivalent, so deleting one
  is structurally invisible to an outcome test.

Also: **re-derive any deploy note from the FINAL diff after review fixes.** A review
fix that adds even a *comment* to one file can arm a workflow and invalidate a note
written earlier.

> Related: a workflow that lists **its own file** in `paths:` fires a real run when
> you edit the workflow — even when your diff is otherwise entirely excluded. "It only
> touches an excluded directory" is not the whole answer.

---

## GraphQL rate-limits separately from REST

`gh pr create`, `gh pr view --comments` and `gh project` use **GraphQL**, which has its
own 5000/hr budget independent of REST. GraphQL can read `0 remaining` while REST shows
~4995.

```bash
gh api rate_limit --jq '{core: .resources.core, graphql: .resources.graphql}'
```

Fallback that works when GraphQL is exhausted:

```bash
gh api repos/<owner>/<repo>/pulls -X POST \
  -f title="..." -f head=<branch> -f base=<base> -F body=@body.md --jq '.number, .html_url'
gh api repos/<owner>/<repo>/issues/<n>/assignees -X POST -f "assignees[]=<user>"
```

Reading PR state without GraphQL: `gh api .../pulls/<n>` (`mergeable_state: clean`),
`.../pulls/<n>/comments`, `.../issues/<n>/comments`, `.../pulls/<n>/reviews`,
`.../commits/<sha>/check-runs`.

`-F body=@file` reads the file; `-f` sends the literal string.

**Exhausted GraphQL does not always say "rate limit".** `gh issue create` reports
`API rate limit already exceeded` while `gh project item-add` fails with **`unknown
owner type`** — which reads like a bad `--owner` flag and sends you debugging the wrong
thing.

**`gh api rate_limit` reports a stale budget. Do not gate anything on it.** While every
GraphQL call fails with `API rate limit already exceeded` — including a bare
`{viewer{login}}`, the cheapest query there is — `rate_limit` can go on returning
`graphql 5000/5000` on nearly every read, and its `core` figure is just as stale.

**Use GraphQL's own meter instead — it is accurate, and it is free:**

```bash
gh api graphql -f query='{rateLimit{remaining}}' --jq .data.rateLimit.remaining
```

That query costs **0 points**, so it can bracket a command to price it exactly:
`before=$(probe); <command>; after=$(probe)`.

**Believe the error, not the meter.** When a `gh project` call fails beside a clean
`rate_limit` read, run a bare `viewer` query. If it fails the same way, the clean read is
the stale meter above and the GraphQL budget is spent. If it succeeds, the failure is the
secondary limit that `rate_limit` does not report
([`../shared/board.md`](../shared/board.md) § Board queries): back off and retry rather
than waiting for the hourly reset.

> There is no REST fallback for Projects v2. When GraphQL is exhausted, board writes
> simply wait.

---

## `git checkout <file>` restores from the INDEX and silently deletes uncommitted work

Not from HEAD. So a restore step in any script — a mutation harness, a cleanup trap —
wipes uncommitted edits made since the last `git add`, with no error and no output.

**Commit before running anything that restores files.** Scope `restore()` to the exact
paths it mutates.

---

## A file can vanish from the diff

A literal NUL byte makes git treat a file as **binary**: the whole file disappears from
the PR diff while every gate stays green. Assert `git diff --numstat` shows real line
counts — a `-` in either column means binary.

---

## Merging

- **Merge the way the repo says** — `workflow.json` → `mergeMethod`, probed from
  `gh repo view` when absent. A repo that disallows squash rejects `--squash`; one that
  requires linear history rejects a merge commit. Read the state back afterwards (`gh pr view <n> --json
  state,mergedAt,mergeCommit`) — see `verification.md` §1, `gh pr merge` exits 0 on
  merges that did not happen *and* exits 1 on merges that did.
- **Branch off the remote ref explicitly**: `git checkout -b feat/x <integrationBranch>`,
  resolved per `shared/config.md` — never `main` by assumption. Fetching is not pulling.
- Piping a `gh` command into `tail`/`head` makes the pipeline's exit status that of
  `tail`, so an `||` fallback never fires and a failure looks like success.

---

## Permissions

**A team grant masks an individual role.** GitHub takes the **highest** grant, so
demoting a user does nothing while a team they belong to holds repo admin. And if your
*own* admin comes only from that team, lowering the team first is a self-lockout.
Check both paths before changing either.

**A repo transfer changes the identity a cloud trusts.** A transfer after `2026-07-15`
silently moves GitHub's OIDC `sub` to the immutable `owner@id/repo@id` form.
That is GitHub's behaviour and applies to every repo; the failure surfaces only as
impersonation 403s, far from the cause, on a workflow that ran yesterday. Before any
transfer, re-bind every federation trust that matches on the subject. Which bindings this
stack has (a WIF `principal://` binding, an AWS trust policy condition) belongs in the
repo's repo.md § Traps.
