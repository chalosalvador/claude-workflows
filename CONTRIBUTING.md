# Contributing

Everything here is markdown and JSON. There is no build, no install, no dependency beyond
`python3` and the `claude` CLI.

## The gate

```bash
python3 tests/test_single_owner_facts.py
python3 tests/test_no_stray_files.py
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

Use `--plugin-dir`, which serves the working tree directly:

```bash
claude --plugin-dir ./plugins/gh-issue-flow
```

Skills are read at invocation, so under `--plugin-dir` a local edit takes effect
immediately, and `/reload-plugins` picks up further edits without a restart.

🚨 **An INSTALLED plugin is a different thing entirely — it is a cached copy, and your
edits do not reach it.** `claude plugin install` copies the plugin into
`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/` and serves from there.
Nothing invalidates that cache while `plugin.json` → `version` is unchanged, and
**`git checkout` does not change what it serves.** Both refresh commands report success
and do nothing: `claude plugin marketplace update` refreshes only the manifest, and
`claude plugin update` compares versions and yours did not change. See
[`CLAUDE.md`](CLAUDE.md) for the measured incident — a four-day-old plugin served
silently across 14 commits and 8 merged PRs.

**So: use `--plugin-dir` to test. To test an install, uninstall and reinstall**, then
restart.

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

To test the **installed** path against your working tree rather than the published
version, add the checkout as a directory source — then reinstall on every change you
want to see, because the install is a copy, not a live view:

```bash
claude plugin marketplace add ./
claude plugin uninstall gh-issue-flow
claude plugin install gh-issue-flow@claude-workflows
```

A restart is required to apply it, and agent discovery still happens at session start.

## 🚨 Bump `version` in the same PR as any behaviour change

`plugin.json` → `version`, **and** both `version` fields in
`.claude-plugin/marketplace.json` — `claude plugin tag` validates that they agree.

That bump is the only thing that gives `claude plugin update` anything to do. Skipping it
is how eight consecutive PRs reached `main` without reaching a single running session.

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
`tests/test_single_owner_facts.py` pins ten clauses to exactly one owning file. Rewrite a
section and the pinned clause stops existing, and it fails with *"0 means the owner lost
it — did a rewrite drop the fact?"* **Update `OWNED` in the same commit.** Do not route
around it by deleting the entry — it has already caught its own pin going stale three
times, which is the behaviour it was built for.

It is mutation-proven 11/11 (7 kill + 4 must-stay-green). If you change the guard itself,
re-prove it; the must-stay-green half is what stops it reddening on ordinary reformatting.

**Facts live in one place.** `shared/execution.md` owns mechanics; skills own policy and
link to it. If you find yourself pasting the same rule into two skills, it belongs in
`shared/` — that is exactly the drift the guard exists to catch.
