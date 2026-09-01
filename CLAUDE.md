# claude-workflows — working notes

A Claude Code plugin marketplace. `README.md` explains what it is and how to install it;
this file is only the things that are **not** obvious from the tree and have already
caused wasted work.

## Validation gate

```bash
python3 tests/test_single_owner_facts.py
claude plugin validate ./plugins/gh-issue-flow --strict
claude plugin validate . --strict
```

CI runs all three as the `guards` job. Everything is markdown and JSON — there is no
build, no install step, no dependency.

## 🚨 `main` is protected. You cannot push to it.

`guards` is a required check with `enforce_admins: true`, plus linear history, required
conversation resolution, and no force-pushes. **Every change needs a branch and a PR**,
including the owner's. A direct push is rejected with `GH006: Protected branch update
failed`.

## 🚨 The installed plugin is served from THIS working tree

The marketplace is registered as a **Directory** source pointing at this checkout, not at
GitHub:

```bash
claude plugin marketplace list     # Source: Directory (<your checkout>) — or GitHub
```

**If it says `Directory`, checking out a different branch changes what the installed
plugin serves.** That is deliberate — it is how unmerged agent changes get tested — but a
stray `git checkout` then silently changes behaviour in every other session on that
machine. After merging, return the checkout to `main`.

If it says `GitHub`, you are on the published version and local edits do nothing until
they land on `main`. Re-add as a directory source to test unmerged work:
`claude plugin marketplace add ./`

## 🚨 Two agent-loading traps, both of which cost real work here

**Shadowing.** If `~/.claude/agents/` (or a project's `.claude/agents/`) holds an agent
with the same name, **that file wins and the plugin's copy never runs.** A **bare**
`issue-planner` resolves to whichever wins; only `gh-issue-flow:issue-planner` reaches the
plugin's. There is no warning, and the shadowing agent returns a perfectly good-looking
result. Check with `ls ~/.claude/agents/` before trusting any agent change.

> Five consecutive agent runs were spent tuning the plugin's planner while the
> user-level file was the one executing. Four separate explanations were constructed for
> the resulting "non-compliance". All were void. **Always spawn the namespaced name.**

**Discovery timing.** Agent types resolve at **session start**. Editing an agent file —
or installing the plugin — changes nothing for the session already running; the spawn
fails with `Agent type '<name>' not found` listing the launch-time set. `/reload-plugins`
refreshes skills; do not assume it re-resolves agents.

**So an agent edit cannot be tested in the session that made it.** Restart first.

## The single-owner guard will block your commit. That is the point.

`tests/test_single_owner_facts.py` pins six clauses to exactly one owning file. If you
rewrite a section and the pinned clause stops existing, it fails with
`0 means the owner lost it — did a rewrite drop the fact?`

**Update `OWNED` in the same commit.** It has already caught its own pin going stale
three times, which is the cost-is-the-feature behaviour it was built for. Do not route
around it by deleting the entry.

It is mutation-proven 11/11 (7 kill + 4 must-stay-green). If you change it, re-prove it —
the must-stay-green half is what stops it reddening on reformatting.

⚠️ It enumerates via `git ls-files`, i.e. the **index**. A new unstaged file is invisible
to it, so `git add` before trusting a local green.

## Testbed

End-to-end changes should be exercised against a throwaway repo, not a real one — see
[`CONTRIBUTING.md`](CONTRIBUTING.md) for how to build one in about ten minutes.

The maintainer's is `chalosalvador/claude-workflows-testbed` + Projects board **1**
(owner `chalosalvador`) — **you will not have write access to it, so make your own.** It
is a small Python repo with real CI and six deliberately varied issues; its `main` is
deliberately unprotected; `scripts/reset.sh` in that repo returns it to pristine
(`--dry-run` first).

⚠️ In that repo the `README.md` install line is **deliberately wrong** — it is a fixture
for its issue #3, not a bug. `scripts/reset.sh` restores the broken form on every reset.

## Convention

Prose here is measured, not asserted. When a doc says a number or a behaviour, it came
from running the thing. If you change a claim, re-measure it or mark it unverified —
several commits here exist specifically to correct a claim that turned out to be wrong,
and that history is worth more than a clean-looking one.
