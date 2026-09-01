# Contributing

Everything here is markdown and JSON. There is no build, no install, no dependency beyond
`python3` and the `claude` CLI.

## The gate

```bash
python3 tests/test_single_owner_facts.py
claude plugin validate ./plugins/gh-issue-flow --strict
claude plugin validate . --strict
```

CI runs all three as the `guards` job. Run them before pushing — `main` is protected, so a
red gate means the PR simply cannot merge.

⚠️ The single-owner guard enumerates via `git ls-files`, i.e. the **index**. A new
unstaged file is invisible to it. `git add` before trusting a local green.

## `main` is protected — everything goes through a PR

`guards` is required with `enforce_admins: true`, plus linear history and required
conversation resolution. That applies to the maintainer too. Branch, PR, merge.

## Testing a change to a **skill**

Skills are read at invocation, so a local edit takes effect immediately:

```bash
claude --plugin-dir ./plugins/gh-issue-flow
```

`/reload-plugins` picks up further edits without a restart.

## 🚨 Testing a change to an **agent** — read this before you waste a day

Two traps, both of which have already cost real work here.

**1. Agent types resolve at SESSION START.** Editing an agent file changes nothing for the
session already running. The spawn fails with `Agent type '<name>' not found`, listing the
agents as they were at launch. `/reload-plugins` refreshes skills; do **not** assume it
re-resolves agents. **So an agent edit cannot be tested in the session that made it.
Restart.**

**2. A same-named agent elsewhere silently wins.** If `~/.claude/agents/` or the project's
`.claude/agents/` holds `issue-planner.md` or `diff-reviewer.md`, that file runs and the
plugin's copy never does. There is no warning, and the shadowing agent returns a
perfectly plausible result — so every symptom points at the file you edited, which is not
the file executing.

> Five consecutive agent runs were once spent tuning a plugin agent that nothing read.
> Four separate explanations were constructed for the resulting behaviour. All were void.

**Always verify before measuring, and always spawn the namespaced name:**

```bash
claude plugin list                 # must show gh-issue-flow enabled
ls ~/.claude/agents/               # anything here with a matching name shadows the plugin
```

Then spawn `gh-issue-flow:issue-planner`, never a bare `issue-planner`.

To serve your working tree rather than the published version:

```bash
claude plugin marketplace add ./
claude plugin install gh-issue-flow@claude-workflows
```

⚠️ That makes the installed plugin follow **whatever branch is checked out**, in every
session on your machine. Return the checkout to `main` when you are done.

## Build your own testbed

The maintainer's testbed is not writable by you. Making one takes about ten minutes and is
the only way to exercise `triage` / `autopilot` end to end.

You need a **throwaway repo** with:

- a small real codebase, a passing test, and a **CI workflow** — `setup` reads the gate
  commands out of it, so a repo without CI tests a different code path;
- **half a dozen deliberately varied issues** — the point is that `triage`'s `agent-ready`
  gate has to *reject* some. Include a genuine bug, an easy feature, a docs fix, an open
  product question, and something that needs a migration;
- optionally a **Projects v2 board**; without one the skills fall back to labels, which is
  also worth testing.

Then run `/gh-issue-flow:setup` against it — that creates the labels and board fields the
other skills read.

**Never point `triage` or `autopilot` at a repo you care about while developing.** They
write across every open issue and open PRs unattended. Both are reversible; neither is
quiet.

## Conventions

**Prose here is measured, not asserted.** When a doc states a number or a behaviour, it
came from running the thing. If you change a claim, re-measure it or mark it unverified.
Several commits exist specifically to correct a claim that turned out to be wrong, and
that history is worth more than a clean-looking one.

**The single-owner guard will block you, and that is the point.**
`tests/test_single_owner_facts.py` pins six clauses to exactly one owning file. Rewrite a
section and the pinned clause stops existing, and it fails with *"0 means the owner lost
it — did a rewrite drop the fact?"* **Update `OWNED` in the same commit.** Do not route
around it by deleting the entry — it has already caught its own pin going stale three
times, which is the behaviour it was built for.

It is mutation-proven 11/11 (7 kill + 4 must-stay-green). If you change the guard itself,
re-prove it; the must-stay-green half is what stops it reddening on ordinary reformatting.

**Facts live in one place.** `shared/execution.md` owns mechanics; skills own policy and
link to it. If you find yourself pasting the same rule into two skills, it belongs in
`shared/` — that is exactly the drift the guard exists to catch.
