---
name: next-issue
description: >-
  Pick the next issue off a GitHub Projects board — the theme-aligned Todo card
  assigned to the current user or unassigned — then either (A) emit a ready-to-paste
  "start it in a new session" prompt, or (B) start it in the current session (scoping-
  plan comment + board In Progress, pause for OK, then implement → validate → parallel
  diff review → PR → babysit CI and review threads to green). Use when asked "what's
  the next issue to work on", for a prompt to start an issue in a new session, or to
  "start" / "work on" the next issue now.
---

# Next issue — start prompt OR start now

Decide the **next issue**, then act in one of two modes:

- **Mode A — Prompt** (default): write a complete prompt the user pastes into a
  *fresh* session. Output is the prompt in one copyable code block. Do **not** start
  implementing.
- **Mode B — Start now**: actually begin the issue **in this session**.

**Pick the mode from the user's wording** (don't ask): "give me a prompt", "to start
in a new session", "draft a prompt" → **Mode A**. "start it", "work on it now",
"begin", "let's do it here" → **Mode B**. When genuinely ambiguous, default to **A**.

Resolve board, repos, branches and validate commands via
[`shared/config.md`](../../shared/config.md). With no board configured, select from
`gh issue list` by label and assignee instead.

## Workflow

```
Shared:
- [ ] 1. Pick the issue (theme-aligned Todo card, or the issue the user names)
- [ ] 2. Identify the repo + workstream
- [ ] 3. Research + plan: delegate to the `issue-planner` subagent (effort: max)
Mode A (Prompt):
- [ ] 4A. Fill template.md — every section, repo-specific VALIDATE commands
- [ ] 5A. Output the finished prompt in ONE code block
Mode B (Start now):
- [ ] 4B. Post scoping-plan comment + set board In Progress → PAUSE for the user's OK
- [ ] 5B. After OK: branch → spec change (if any) → implement → validate →
          parallel `gh-issue-flow:diff-reviewer` review → archive → commit → PR →
          babysit to green
```

## 1. Pick the issue

If the user named an issue, use it and skip selection.

Otherwise pick from the **Todo column**. **Eligible = Todo AND (assigned to the
current GitHub user OR unassigned).** Resolve the user dynamically —
`gh api user --jq .login` — never hardcode a login.

⚠️ **`$BOARD_JSON` is the one board fetch this run gets** — see
[`shared/config.md`](../../shared/config.md) § Board queries for it. This step and the
theme sense below are two `jq` passes over that same file, not two `item-list` calls.

```sh
ME=$(gh api user --jq .login)
jq -r --arg me "$ME" '.items[]
   | select(.status=="Todo")
   | select((.assignees|index($me)) or (.assignees|length==0))
   | "#\(.content.number)\t\(.content.repository|sub(".*/";""))\tP:\(.priority // "-")\t\(.assignees|if length==0 then "unassigned" else join(",") end)\t\(.content.title)"' "$BOARD_JSON"
```

⚠️ Strip owners with `sub(".*/";"")` — never match a literal owner prefix. Repos on one
board can sit under different owners.

### Sense the current theme

Before ranking, read what is *actively* happening so the pick continues the current
thread instead of cold-starting an unrelated one:

```sh
# Strongest signal — what is mid-flight right now (same fetch, second pass):
jq -r '.items[] | select(.status=="In Progress") | "#\(.content.number)\t\(.content.title)"' "$BOARD_JSON"

# Recently merged work (last ~2 weeks), per repo — owners differ, resolve each.
# The repo list is workflow.json -> repos; absent, it is just the repo you are in.
for NWO in <owner/repo> <owner/repo>; do
  gh pr list --repo "$NWO" --state merged --limit 20 --json number,title,mergedAt \
    --jq '.[] | "\(.number)\t\(.title)"'
done

# The commit log needs a real checkout. For the repo you are in, that is here:
git log --since="2 weeks ago" --oneline
```

⚠️ **Do not reach for `git -C <repo-name>`.** That guesses that every repo is a sibling
directory named after itself, which is false in the ordinary case where you are already
inside the only checkout — and it fails loudly there for no reason. Resolve a real path
first, or skip the log for that repo and say so; the `gh pr list` half needs no working
copy and carries most of the signal. See
[`shared/config.md`](../../shared/config.md) § Repo scope.

Name the **current theme(s)** in a phrase or two. Capture the subsystem, files/dirs,
labels and track involved.

### Rank and present

On an established board there are often dozens of eligible cards, and `item-list` does
**not** return reliable manual board order — don't blindly grab the first row. Rank by:

1. **Alignment with the current theme** — biggest weight. Boost a card if its body says
   "follow-up to" / "depends on" a just-merged issue, or it shares the subsystem, files,
   labels or track of In-Progress and recently-merged work.
2. **Priority** (P0→P3).
3. **Assignee** — assigned-to-the-current-user ahead of unassigned on ties.

Present the **top ~5** with a one-line "why it's aligned" note each, default to the top
one, and let the user choose. If they said "just give me the next one", take the
default and continue. If no eligible cards exist, fall back to the top Todo card and
**say** it is assigned to someone else.

**No eligible cards and no Todo column at all** — a new repo, or a board that has just
been emptied — is a legitimate answer, not a failure. Say `nothing in Todo` in one line,
and offer the one useful next step: file the issue the user actually wants worked, or run
`/gh-issue-flow:triage` if there are open issues that never reached the board. Do not
invent work, and do not fall through to a Done or In Progress card.

**Flag, don't silently proceed:** if the chosen issue's body says "sequenced after" /
"blocked by" / "depends on #N", verify #N is closed/merged and note the blocker's real
state in your summary.

🚨 **Cards with Status `Hold` are never eligible.** A human parked it by choice.
Un-parking is the user's call, not the picker's.

## 2. Repo + workstream

The issue's repo is on its GitHub URL. Narrow to the workstream from `workflow.json` →
`workstreams`, or from the repo's own directory layout.

⚠️ **Beware stale paths in issue bodies and docs.** An app that was split or renamed
leaves the old path valid-looking — sometimes still on disk as an untracked leftover.
Confirm against the current tree, not the issue text.

## 3. Research before writing

Read the issue **once**, into a file — its contents go into the planner's spawn prompt,
and the planner is told not to fetch them again:

```sh
ISSUE_MD="${SCRATCH:-${TMPDIR:-/tmp}}/issue-<N>.md"
{ gh api repos/<owner>/<repo>/issues/<N> \
    --jq '"# #\(.number) \(.title)\n\n\(.body // "")"'
  gh api repos/<owner>/<repo>/issues/<N>/comments \
    --jq '.[] | "\n---\n@\(.user.login):\n\n\(.body)"'
} > "$ISSUE_MD"
```

⚠️ **These are the REST spellings on purpose.** `gh issue view` is GraphQL; these bill
against the separate core budget, which is the budget a planning run is *not* exhausting.
For a transferred issue that returns empty, take the body from `$BOARD_JSON`
(`.content.body`) — you already have that file, so it costs nothing.

**Do not chase the linked PRs here.** The planner does that, bounded to the few the
decision turns on. Fetching them in both places is the same read billed twice.

Then delegate to the **`issue-planner`** subagent (read-only, `effort: max`), **pasting
`$ISSUE_MD` into the prompt verbatim**. A subagent starts blank: anything you hold and do
not pass, it pays to re-fetch. It returns the decision, what exists vs. what changes, the
scope, the test/validate plan, a HANDOFF block for the reviewers, and which review lenses
this diff needs.

🚨 **State the tier from the issue's effort label; name no sections.** Naming one
re-establishes the whole vocabulary and the planner emits all of them — measured. Pass
the facts (branch, gate, spec flow, worktree) and let it choose the shape.

**The VERIFY-FIRST section must name real files/symbols, not guesses.**

## 4A. Mode A — fill the template

Use the bundled template — read it by absolute path, since from an installed copy the
working tree is not on disk:

```sh
cat "${CLAUDE_PLUGIN_ROOT}/skills/next-issue/template.md"
```

Sections, in order: header line + URL → Repo →
CONTEXT → DECIDE FIRST → SCOPE → VERIFY-FIRST → TESTS → VALIDATE → PROCESS →
DEPLOY NOTE.

**Carry the plan's REVIEW LENSES into the PROCESS section.** The planner decided which
lenses this diff can actually trip; the fresh session reading the prompt has no way to
re-derive that. Name the specific lenses and why, and say which you skipped — **never
emit the generic full lens list.**

Emit VALIDATE commands **verbatim** from the resolved config. Do not paraphrase from
memory: the commands in the original of this skill were wrong for weeks — a prefetch
script that had been renamed, a linter path list missing four directories — which is
why they now resolve from one place.

## 4B. Mode B — start now

Same research (steps 1–3), executed as actions, with a hard checkpoint:

```
- [ ] 1. Post the plan `issue-planner` returned as a SCOPING PLAN comment on the issue.
- [ ] 2. Set the board card Status → In Progress; keep/claim assignee.
- [ ] 3. *** PAUSE. *** Show the plan + the comment link and WAIT for the user's OK.
         Do not edit code before they approve.
- [ ] 4. After OK: `git fetch`, branch feat/<N>-<slug> off the REMOTE integration ref.
         Work in a worktree — see reference/parallel-agents.md.
- [ ] 4b. *** Before writing any code: *** if the repo has a spec flow, create the
         change directory from the plan's SPEC IMPACT and get its validate to exit 0.
         Cheap to fix a requirement now, expensive once the code exists.
         ⚠️ See reference/openspec.md for what that green does NOT assert.
- [ ] 5. Run the repo's full VALIDATE gate — shared/execution.md § 2, verbatim.
- [ ] 6. Review: spawn `gh-issue-flow:diff-reviewer` subagents IN PARALLEL (effort:
         max, fresh context), one per lens the plan named — plus `scoping` whenever the
         diff adds a guard. 🚨 NAMESPACED name; a bare one can be shadowed silently.
         Adjudicate: fix every valid finding, explain any rejected. Commit BEFORE
         spawning them. 💰 Handoff + model tiering: shared/execution.md § 3.1.
- [ ] 6b. If those fixes introduced NEW LOGIC — a new branch, gate, condition or code
         path — spawn ONE more `gh-issue-flow:diff-reviewer` over just that delta, as
         THE LENS THAT RAISED THE FINDING (correctness only if it was your own).
         Skip for test/comment/doc-only fixes — a changed message still gets a pass.
- [ ] 6c. Archive the spec change as the LAST commit of this PR; assert the archive
         JSON matches the delta-vs-skip call, then re-validate the folded tree.
- [ ] 7. Commit referencing "Fixes #<N>" (never commit secrets), open a PR.
- [ ] 8. Babysit to green — CI **and** review threads. Reply, verify, then resolve.
- [ ] 9. Set the card → Done only at merge. NEVER merge without go-ahead.
```

🚨 **Read every GitHub mutation back before reporting it.** `gh` exits 0 on writes the
server rejected, so "posted the scoping comment" and "set the card In Progress" are
claims until you have re-read them. See
[`../../reference/verification.md`](../../reference/verification.md).

Respect every DEPLOY NOTE caveat: **ask before touching shared staging or applying
infrastructure**; flag destructive migrations.

## 5. Facts shared with the autopilot skill

The detail lives in [`shared/execution.md`](../../shared/execution.md) so the two
cannot drift. **Read it — do not restate it from memory.**

- **Code review** → § 3. Parallel `gh-issue-flow:diff-reviewer` lenses gated on the
  plan's REVIEW LENSES, plus the delta re-review as its raising lens. Never a
  `disable-model-invocation` built-in.
- **Branch, commit, signing, cross-repo refs, spec archive** → § 4. The archive is the
  **last commit of the same PR**, never post-merge.
- **PR babysitting** → § 5. Watch threads as well as checks. **Never merge without the
  requester's go-ahead**, and re-check 0 unresolved threads at the merge instant.
- **Board tracking** → § 6. In Progress on start, **Done only at merge**.
- **Deploy consequences** → § 7. If merging the integration branch deploys, the
  prompt's DEPLOY NOTE must say so.

## Output

- **Mode A:** emit the finished prompt as **one** fenced code block. At most one
  sentence before it, naming the issue.
- **Mode B:** don't emit a prompt. Post the scoping-plan comment, set the board, then
  stop at the checkpoint with a short summary + the comment link and wait for the OK.
