---
name: review-pr
description: >-
  Review an open GitHub pull request with parallel gh-issue-flow:diff-reviewer
  lenses, without a planner, an issue or a board. Checks the PR out into its own
  worktree, diffs it against the PR's own base, spawns one read-only reviewer per
  lens, merges their findings and prints them with each lens's raw output; with
  `post`, posts them as one COMMENT review with inline comments. Never approves,
  requests changes, edits or pushes. Use for "review PR 123", "run the diff
  reviewer on this PR", or as the step a GitHub Action runs on every PR.
---

# Review a pull request

Runs the same reviewer `next-issue` and `autopilot` run before a PR exists, on a PR that
already does. The lenses, their rules and their output format belong to
[`agents/diff-reviewer.md`](../../agents/diff-reviewer.md); this skill only supplies what
a planner supplies in the issue flow: the diff location, the base, the lens list, and the
merge of the results.

**Arguments:** a PR number or URL (required), then optionally:

- `post` — post the result to the PR as a review (§ 6). Without it, nothing is written
  anywhere.
- `lenses=<a,b,…>` — run exactly these lenses instead of the default (§ 3).

```
- [ ] 1. Read the PR
- [ ] 2. Check it out into its own worktree
- [ ] 3. Pick the lenses
- [ ] 4. Spawn one reviewer per lens, in parallel
- [ ] 5. Merge and print
- [ ] 6. Post (only with `post`)
- [ ] 7. Remove the worktree
```

**This skill reads and comments; it changes nothing else.** No edit to the PR branch, no
push, no approval or change request, no resolved thread, no label.

## 1. Read the PR

Run from a clone of the PR's repo. With a URL, take the repo from it and check it against
the clone; with a number, the clone's repo is the PR's:

```sh
gh repo view "$(git remote get-url origin)" --json nameWithOwner --jq .nameWithOwner
gh pr view <PR> --repo <owner/repo> \
  --json number,url,title,body,state,baseRefName,headRefOid
```

Outside a clone, or in a clone of a different repo, stop and say which repo the PR needs.
A closed or merged PR is still reviewed, but never posted to.

## 2. Check it out into its own worktree

Review the PR in a worktree of its own, never in the checkout the session started in: the
user's checkout keeps its branch, and in CI the PR's head is fetched explicitly rather than
trusted from the job's checkout.

```sh
root=$(git rev-parse --show-toplevel)
wt="${RUNNER_TEMP:-${TMPDIR:-/tmp}}/review-pr-<N>"
git -C "$root" fetch origin \
  "+refs/heads/<baseRefName>:refs/remotes/origin/<baseRefName>" \
  "+refs/pull/<N>/head:refs/review-pr/<N>"
git -C "$root" worktree add --detach "$wt" refs/review-pr/<N>
git -C "$wt" rev-parse HEAD
git -C "$wt" merge-base origin/<baseRefName> HEAD
```

`refs/pull/<N>/head` exists on the base repo for a fork's PR too. Read two things back:

- **`rev-parse HEAD` equals `headRefOid`.** If not, a push landed between the two reads:
  re-read the PR and fetch again.
- **`merge-base` prints a commit.** Nothing printed means a shallow clone, and the
  three-dot diff the reviewers run has no base: `git -C "$root" fetch --unshallow origin`,
  then retry.

If `$wt` already exists, an earlier run did not clean up: remove it as § 7 does, then add
it again.

## 3. Pick the lenses

No planner runs, so nobody names the lenses from the issue. The default is the whole
[set](../../agents/diff-reviewer.md#the-lenses), with one exception:

- **Every changed file is documentation** (`git -C "$wt" diff --name-only
  origin/<baseRefName>...HEAD` lists only `.md`, `.mdx`, `.rst` or `.txt` files): run
  `comments` and `correctness`.
- **Otherwise:** all eight.

`lenses=` replaces the rule. Print the list you ran and why, so two runs on the same PR
can be compared.

## 4. Spawn one reviewer per lens, in parallel

**One message, one `gh-issue-flow:diff-reviewer` call per lens**, so they run at once
([`parallel-agents.md`](../../reference/parallel-agents.md)). Spawn the namespaced name,
never the bare one ([`shared/execution.md`](../../shared/execution.md) § 3). Leave
`model` unset: every lens inherits the session's model, so the model is chosen once, when
the session starts.

Each prompt is exactly this, and nothing else:

```
Plugin: <plugin dir>
Worktree: <wt>
Base: origin/<baseRefName>
Lens: <lens>
No HANDOFF: this is a review of an open PR; no planner ran.

PR #<N>: <title>
PR description, the author's account and not evidence:
<body, verbatim>
```

`Plugin:` is the plugin directory as [`shared/execution.md`](../../shared/execution.md)
§ 3 derives it. Add no summary of the diff and no hint of where to look. The reviewer is
built to start from the diff, and a hint makes the run a test of the hint.

## 5. Merge and print

Keep every lens's output exactly as it came back; § 6 and the report both carry it. Then
build one combined list from them:

- **Merge duplicates.** Findings at the same `file:line` stating the same defect become
  one, carrying every lens prefix that raised it.
- **Drop a finding only when you can show it is wrong.** Read the code it cites; if the
  failure scenario cannot happen, drop it and list it under **Dropped** with the reason.
  Never drop one silently, and never drop one because it is minor.
- **Add none of your own.** The combined list is the reviewers' result; a finding the
  session adds makes the result a measure of the session.
- **Rank** most severe first.

Print, in this order:

1. **Run:** the PR URL, `origin/<baseRefName>`, the reviewed head SHA, the lenses run and
   why, and the plugin `version` read from `<plugin dir>/.claude-plugin/plugin.json`.
2. **Findings:** the combined list, each with its `file:line`, defect and failure scenario.
   With none, say so plainly.
3. **Dropped:** each dropped finding with its reason, or "none".
4. **Per lens:** each lens's output under its own heading, verbatim.

## 6. Post (only with `post`)

Only on an open PR, and only as **one review with event `COMMENT`**. Never `APPROVE`, never
`REQUEST_CHANGES`: the review is input for a human, not a merge gate.

**Inline or in the body.** A finding goes inline when its line is one GitHub can comment
on: on the new side of a hunk in `gh pr diff <N> --repo <owner/repo>`, so a hunk headed
`@@ -a,b +c,d @@` covers lines `c` to `c+d-1` of its file. Every other finding, including
one at a file the PR does not change, goes in the body with its `file:line`. A single
uncommentable line rejects the whole review, so check each one before posting.

The review body carries, in order: the Run line from § 5, the findings that are not
inline, Dropped, and each lens's raw output inside its own `<details>` block. If the body
would pass 60,000 characters, leave the raw outputs out and say so in the body; the
printed report still has them.

Write the request to a JSON file and post it:

```json
{
  "commit_id": "<the reviewed head SHA>",
  "event": "COMMENT",
  "body": "<body>",
  "comments": [
    { "path": "<file>", "line": 42, "side": "RIGHT", "body": "<lens>: <defect>\n\n<failure scenario>" }
  ]
}
```

```sh
gh api --method POST repos/<owner/repo>/pulls/<N>/reviews --input <file> --jq .id
gh api repos/<owner/repo>/pulls/<N>/reviews/<id>/comments --jq length
```

`commit_id` is the SHA the lenses reviewed, even if the PR has moved on since: GitHub then
places each comment on that commit's diff. **Read back** that the second command prints
the number of inline comments sent, and report the review's URL. On a 422, report the
error, then post again with every finding in the body and no inline comments, and say so.

## 7. Remove the worktree

```sh
git -C "$root" worktree remove "$wt"
git -C "$root" update-ref -d refs/review-pr/<N>
```

Without `--force`. If `worktree remove` refuses because the tree is modified, something
wrote to a tree every lens is told never to edit: report that with `git -C "$wt" status
--short`, then remove it with `--force`.

## Running it on every PR

A GitHub Actions workflow that runs this skill on each PR:
[`github-action.md`](github-action.md).
