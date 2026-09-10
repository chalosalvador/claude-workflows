# Contributing

Everything here is markdown and JSON. There is no build, no install, no dependency beyond
`python3` and the `claude` CLI.

## The gate

```bash
python3 tests/test_single_owner_facts.py
python3 tests/test_no_stray_files.py
python3 tests/test_version_agreement.py
python3 tests/test_config_schema.py
python3 tests/test_links.py
python3 tests/test_doc_headers.py
python3 tests/test_comment_policy.py
claude plugin validate ./plugins/gh-issue-flow --strict
claude plugin validate . --strict
```

CI runs all of them as the `guards` job. Run them before pushing — `main` is protected, so a
red gate means the PR simply cannot merge.

`tests/test_comment_policy.py` reads the lines your branch adds or changes since it left
`origin/main`, and every untracked file that is not ignored, so `git fetch origin` before
running it and keep drafts such as a PR body outside the checkout. What it enforces is
[`comments-and-docs.md`](plugins/gh-issue-flow/reference/comments-and-docs.md); a line
nobody touches is never read, so older text that breaks the policy stays until it is
edited.

⚠️ **A PR with NO checks is not a passing PR.** `guards` is required, so zero checks
blocks a merge rather than allowing it — but the PR page looks clean either way, which is
how a stacked PR once reached `MERGEABLE` having never run the gate. The workflow now
triggers on every base, and on `edited` so that retargeting a PR re-runs it. **Look for a
green `guards`, not for the absence of red.**

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
[`CLAUDE.md`](CLAUDE.md) for how the cache is keyed and what refreshes it.

**So: use `--plugin-dir` to test.** To collect a change that has already landed with a
version bump, `claude plugin marketplace update` then `claude plugin update` — MEASURED,
that delivers the new cache dir **and keeps your config**. Reach for uninstall+reinstall
only when the version did *not* change, and read § *the reinstall wipes your plugin
config* below first: that cycle costs you something nobody warns you about.

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

Then spawn `gh-issue-flow:issue-planner`, never a bare `issue-planner`, with a `Plugin:`
line naming the absolute path of `plugins/gh-issue-flow`. Without it the agent reads the
lens set from the newest installed copy, not your working tree.

To test the **installed** path against your working tree rather than the published
version, add the checkout as a directory source — then reinstall on every change you
want to see, because the install is a copy, not a live view:

```bash
claude plugin marketplace add ./
claude plugin uninstall gh-issue-flow
claude plugin install gh-issue-flow@claude-workflows
```

A restart is required to apply it, and agent discovery still happens at session start.

### 🚨 The reinstall wipes your plugin config, and nothing says so

**`claude plugin uninstall` empties your `userConfig`, and the reinstall does not put it
back.** It lives in `~/.claude/settings.json` → `pluginConfigs`, keyed by plugin id.
MEASURED on `0.3.0`:

| Step | `pluginConfigs` |
|---|---|
| `install … --config board_number=1` | `{"gh-issue-flow@claude-workflows": {"options": {"board_number": "1"}}}` |
| `claude plugin uninstall gh-issue-flow` | `{}` |
| `claude plugin install …` | `{}` — **not restored** |

So the recipe above silently costs a contributor their board number and owner. **Write
them down before you run it** — or avoid the cost entirely: `claude plugin update` on a
bumped version delivers the same new cache dir and **preserves `pluginConfigs`**
(measured, same run). Recovery when you have already lost them is to re-supply —
`--config` is repeatable and works on an already-installed plugin, so this needs no
second uninstall:

```bash
claude plugin install gh-issue-flow@claude-workflows \
  --config board_number=<n> --config board_owner=<owner>
```

Then **`/reload-plugins`** in any running session — option values are memoized per
plugin id in-process, and the subprocess that wrote them cannot invalidate that map.

⚠️ **Uninstall is not the only thing that clears it.** MEASURED: `claude plugin
marketplace remove <name>` wipes `pluginConfigs` for every plugin that marketplace
provided — which lands squarely on the directory-source recipe above, since dropping the
`./` source is how you undo it. `claude plugin update` is the one command that preserves
config.

⚠️ **What you lose is a machine-wide *default*.** Any repo that names its own board in
`workflow.json` → `board` is unaffected, because that layer wins. Why `pluginConfigs`
cannot be per-repo, with the measurement:
[`README.md`](README.md#configuration-in-three-layers) § Layer 1.

Two things this is not. It is not the same as the *"N userConfig options not yet set"*
line the install prints — that appears whether or not you ever had config, and what it
counts is in [`README.md`](README.md#1-install). And it is not
something to diagnose by sharing that settings file — it also holds `permissions` and
every other plugin's configuration. Read the one key, not the file.

## 🚨 Bump `version` in the same PR as any behaviour change

`plugin.json` → `version`, **and** both `version` fields in
`.claude-plugin/marketplace.json`.

⚠️ **The gate constrains two of those three, and nothing checks the third.** MEASURED:
`plugin.json` disagreeing with `marketplace.json` → `plugins[0].version` exits **1**
(`plugin.json wins`), so bumping either alone reds. A stale — or even deleted —
**top-level** `version` passes `--strict` at exit 0, and nothing detects that you forgot
to bump at all. `claude plugin tag` is no help: its own `--help` says it validates
"plugin.json and any enclosing marketplace **entry**" — the entry, not the top level.
`tests/test_version_agreement.py` now reds on any disagreement between the three —
mutation-proven 3 kill / 2 must-stay-green, including the stale-top-level case
`claude plugin validate` passes at exit 0. It still cannot tell you *forgot* to bump;
nothing can. Read them back yourself when it matters.

That bump is the only thing that gives `claude plugin update` anything to do. Skipping it
is how eight consecutive PRs reached `main` without reaching a single running session.

### And bump the config schema when a PR adds a `workflow.json` key

A plugin update reaches the code, not the repos already configured. So a new key needs
three things in the same PR: a row in the schema table in `shared/config.md` § Layer 2
with its **Since** set to a bumped **Current schema**, a probe for it in `setup` § 2, and
`EXPECTED_KEYS` in `tests/test_config_schema.py` moved up by one. That guard reds on any
of the three missing. `setup upgrade` is then what carries the key into an existing repo.

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
The measurement, and the story of a claim that turned out wrong, go in the PR body's
History
([`git-and-github.md` § Writing a PR body](plugins/gh-issue-flow/reference/git-and-github.md#writing-a-pr-body));
the doc states the current fact. Comments and docs follow
[`comments-and-docs.md`](plugins/gh-issue-flow/reference/comments-and-docs.md).

**The single-owner guard will block you, and that is the point.**
`tests/test_single_owner_facts.py` pins sixteen clauses to exactly one owning file. Rewrite a
section and the pinned clause stops existing, and it fails with *"0 means the owner lost
it — did a rewrite drop the fact?"* **Update `OWNED` in the same commit.** Do not route
around it by deleting the entry — it has already caught its own pin going stale three
times, which is the behaviour it was built for.

It is mutation-proven 11/11 (7 kill + 4 must-stay-green); the two board pins added later were proven 7/7 (3 kill + 4 must-stay-green) on top, the two ops-doc pins 8/8 (4 kill + 4 must-stay-green), the area-map pin 8/8 (4 kill + 4 must-stay-green — two mutants first read wrong because the harness matched the clause unwrapped while the owner hard-wraps it; match the wrapped text), and the out-of-sweep pin 8/8 (4 kill + 4 must-stay-green, matched wrapped; one harness case first crashed on its own bug before scoring anything, which is not a survival either): a softened or inverted owner and an exact copy elsewhere red; a hard-wrap, moved emphasis, a move within the owner and a paraphrase elsewhere stay green. If you change the guard itself,
re-prove it; the must-stay-green half is what stops it reddening on ordinary reformatting.

`tests/test_config_schema.py` is mutation-proven **11/11 (7 kill + 4 must-stay-green)**:
a dropped row, an example key with no row, a Since above Current, a key setup never
mentions, a missing Current line, a duplicate row and an emptied table all red; reversed
rows, padded cells, a reworded Meaning and a legitimate schema bump stay green.

`tests/test_links.py` is mutation-proven **7/7 (5 kill + 2 must-stay-green)**: a typo'd
path, a link to an untracked file, a link escaping the repo, a link climbing out of the
plugin directory to a marketplace-only path, and a parser that matches nothing all red;
an anchor link and a mix of `./`, directory, `https:` and `#` links stay green. Its
positive-case floor (`MIN_LINKS`) is a measured number. Two lessons from its own review:
the first run reddened on two links quoted inside code spans, so it strips fences and
spans first; and its first version passed the very `../../../tests/` link it was written
for, because it checked the marketplace boundary and not the plugin's — the fifth kill
case is that link.

`tests/test_doc_headers.py` is mutation-proven **8/8 (6 kill + 2 must-stay-green)**: a
renamed skeleton header, a renamed table row, a "§ Infra" short reference, demoted
headers, an added header the table lacks, and a header present in both skeletons all
red; a reordered table and a mix of other § references with full header names stay
green. Its first version matched a
reference greedily ("§ Infra before deciding") and let the short form through; the
word-by-word comparison is the fix.

**Facts live in one place.** `shared/execution.md` owns mechanics; skills own policy and
link to it. If you find yourself pasting the same rule into two skills, it belongs in
`shared/` — that is exactly the drift the guard exists to catch.
