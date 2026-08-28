# Git and GitHub: traps that silently change the answer

---

## Diff scope: three dots, always

To check "does this PR touch only `tests/`?", use **three dots**:
`git diff <base>...HEAD` (diff from the merge-base). **Two dots** diffs the two
commits directly, so anything that landed on the integration branch *after* you
branched shows up **inverted** — a file the base deleted appears as your branch
adding it back.

Measured: a two-dot stat listed 32 files and ~930 insertions, including a Terraform
root the base had just deleted, `+269`. The real change was one file, 496/50. A
tests-only PR looked like it was re-adding a retired directory.

GitHub renders PRs with merge-base semantics, so **the three-dot diff is what the
reviewer actually sees.**

> A review subagent told to run two-dot can report a clean file list and still be
> right *at that moment* — the discrepancy only appears once the base moves.
> **Re-check with three dots immediately before opening the PR.**

---

## 🚨 CI tests head MERGED WITH base, so "green locally, red in CI" is often neither flake nor environment

GitHub's `pull_request` event checks out the **merge** of head and base, not head.
The two runs are testing **different trees**.

Measured three times in one sitting: a guard pinning every file under an archive
directory was green locally (279 files pinned, 279 in the tree) and red in CI, which
saw 283 — because the base had archived another change after the push. The failure
message named directories that did not exist on the branch at all.

**When CI reds on something inventory- or count-shaped and the branch is green,
check whether the base moved before assuming flake:**

```bash
git fetch origin && git merge-base --is-ancestor origin/main HEAD
```

- To reproduce locally, **merge the base in first** — the local suite alone cannot
  see the defect.
- **Re-verify the base at the MERGE INSTANT**, not merely when checks go green.
  Between "all green" and clicking merge the base can move, and the squash then reds
  the integration branch itself.
- A matching file **count** is not proof the base is current — two independent
  additions can coincide numerically. Compare ancestry.
- `--match-head-commit` guards the PR **head**, not the base. It does nothing here.

⚠️ **Do not fabricate the SHA for `--match-head-commit`.** Abbreviating the head
yourself and padding it produces `GraphQL: Head branch was modified` and reads like a
real race. Read it: `gh pr view <N> --json headRefOid --jq .headRefOid`. It needs the
full 40 chars.

---

## 🚨 A conflicting PR SKIPS its workflow — the check goes MISSING, not red

When the base moves and the PR conflicts, GitHub cannot build a merge ref, so the
`pull_request` workflow **never fires**. `gh pr checks` then shows a healthy-looking
list — every other check green — with the required one simply **absent**. Nothing
announces it.

```bash
gh pr view <N> --json mergeable,mergeStateStatus
```

Confirm the required check is **present**, not merely that nothing is failing.

⚠️ `mergeable` is computed **asynchronously**: right after a push it reports the
stale value (measured `CONFLICTING/DIRTY` on a branch that was actually
`MERGEABLE`). Poll until it settles before believing it.

---

## 🚨 A NEGATED closing keyword still closes the issue

GitHub's linked-issue parser matches
`close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved` + `#N` and **does not
read negation in front of it.**

Measured: every commit deliberately said `Refs #784`, never `Fixes` — verified by
regex over the squash message, zero closing keywords. The issue closed anyway,
because a review bot appended a summary to the PR body containing:

> **Merging does not close #784** until Terraform is applied.

`close #784` matched. **The sentence written to say the issue must stay open is what
closed it.** Board automation then flipped the card to Done, and nothing in the repo
detects it.

- Never write a closing keyword next to `#N`, *even negated*. Phrase it as
  "#784 stays open until …" — no keyword within ~1 token of the number.
- ⚠️ **You do not control the whole PR body.** Bots append sections after you write
  it, so a body clean at creation can acquire one.
- When the merge must NOT close the issue, **read the issue state back after merging**
  and reopen if needed. Reopening does not restore the board card — set Status by hand.

---

## `paths:` filters are ORDER, not membership

GitHub resolves `paths:` / `paths-ignore:` **last-match-wins**, so the *order* of the
patterns is the semantics. A test asserting `"terraform/cells/prod/**" in paths` reads
as equivalent to testing the filter and is not.

Measured: moving two positive patterns to the end of the list — **all eight strings
unchanged** — kept a membership-style test green while three previously-excluded paths
began matching. Adding `- "**"` also stayed green.

**Assert OUTCOMES over corpora of real paths** (`_MUST_MATCH` / `_MUST_NOT_MATCH`),
never membership. Import a shared evaluator rather than rebuilding one.

⚠️ Two things an outcome test cannot do — pair it with shape rules:

- **Widening by ADDITION is invisible** to it; it only speaks about paths someone
  thought to list. Add a rule that no pattern reaches outside the intended tree.
- **A doubled `**/*.md` + `*.md` pair** must be asserted as membership: a model that
  collapses `**/` to zero segments treats the spellings as equivalent, so deleting one
  is structurally invisible to an outcome test.

Also: **re-derive any deploy note from the FINAL diff after review fixes.** A review
fix that added a *comment* to one file newly armed a drift workflow and invalidated a
note written earlier.

> 🚨 Related: a workflow that lists **its own file** in `paths:` fires a real run when
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

⚠️ `-F body=@file` reads the file; `-f` sends the literal string.

🚨 **Exhausted GraphQL does not always say "rate limit".** `gh issue create` reported
`API rate limit already exceeded` while `gh project item-add` failed with **`unknown
owner type`** — which reads like a bad `--owner` flag and sends you debugging the wrong
thing.

🚨 **And `gh api rate_limit` does not see the limit that stops `gh project`.** A
`gh project item-list` returned `API rate limit exceeded` at every `--limit` down to 30
while `rate_limit` reported **5000/5000 remaining on both core and graphql**. Projects
v2 pagination trips a *secondary* limit the endpoint does not report. **Believe the
error, not the meter.** Large `--limit` values make it worse, since each page is a
request.

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

- **Always `--squash`.** Read the state back afterwards (`gh pr view <n> --json
  state,mergedAt,mergeCommit`) — see `verification.md` §1, `gh pr merge` exits 0 on
  merges that did not happen *and* exits 1 on merges that did.
- **Branch off the remote ref explicitly**: `git checkout -b feat/x origin/main`.
  Fetching is not pulling.
- ⚠️ Piping a `gh` command into `tail`/`head` makes the pipeline's exit status that of
  `tail`, so an `||` fallback never fires and a failure looks like success.

---

## Permissions

🚨 **A team grant masks an individual role.** GitHub takes the **highest** grant, so
demoting a user does nothing while a team they belong to holds repo admin. And if your
*own* admin comes only from that team, lowering the team first is a self-lockout.
Check both paths before changing either.

🚨 **A repo transfer switches the OIDC subject.** A transfer after 2026-07-15 silently
moves GitHub's OIDC `sub` to the immutable `owner@id/repo@id` form, breaking every WIF
`principal://` binding. The failure surfaces only as impersonation 403s.
