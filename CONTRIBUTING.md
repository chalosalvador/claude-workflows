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
red gate means the PR cannot merge.

`test_single_owner_facts.py`, `test_no_stray_files.py`, `test_links.py` and
`test_doc_headers.py` list files with `git ls-files`, i.e. the index, so a new file is
invisible to them until it is staged.
`git add` the paths you changed before trusting a local green, never `git add -A`: a
sweeping add is how a stray file reaches a commit.

`tests/test_comment_policy.py` reads the lines your branch adds or changes since it left
`origin/main`, and every untracked file that is not ignored, so `git fetch origin` before
running it and keep drafts such as a PR body outside the checkout. What it enforces is
[`comments-and-docs.md`](plugins/gh-issue-flow/reference/comments-and-docs.md); a line
nobody touches is never read, so older text that breaks the policy stays until it is
edited.

**A PR with no checks is not a passing PR.** `guards` is required, so zero checks blocks a
merge rather than allowing it, but the PR page looks clean either way. The workflow
triggers on every base, and on `edited` so that retargeting a PR re-runs it. Look for a
green `guards`, not for the absence of red.

## `main` is protected — everything goes through a PR

`guards` is a required check with `enforce_admins: true`, plus linear history, required
conversation resolution and no force-pushes. That applies to the maintainer too: a direct
push is rejected with `GH006: Protected branch update failed`. Branch, PR, merge.

## The installed plugin is a cached copy

`claude plugin install` copies the plugin into a version-keyed cache and serves it from
there, even when the marketplace is registered as a directory source:

```
~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/
```

`claude plugin marketplace list` shows which source each marketplace uses —
`Directory (<your checkout>)` or GitHub. Either way the copy is not a live view of the
checkout: its files are not symlinks, and a
`git checkout` here does not change what it serves. `<version>` is `plugin.json` →
`version`, and nothing invalidates the cache while that string is unchanged, so every
change merged since the install is invisible to every session until the version moves,
and nothing says so.

When the version did not change, both refresh commands report success and change nothing:

| Command | Says | Does |
|---|---|---|
| `claude plugin marketplace update <name>` | `✔ Successfully updated marketplace` | refreshes the marketplace manifest only, not the cached plugin |
| `claude plugin update <plugin>` | `✔ already at the latest version (…)` | nothing: it compares versions, and yours did not change |

Once `version` changes, `claude plugin marketplace update` then `claude plugin update` is
the right sequence. It creates the new cache directory and keeps your plugin config:

```
✔ Plugin "gh-issue-flow" updated from 0.3.0 to 0.3.1 for scope user.
cache dirs: 0.3.0  0.3.1        # new dir created
pluginConfigs: PRESERVED         # board number and owner survive
```

Keep uninstall and reinstall for a cache that is stale because the version did not
change, and read § *The reinstall wipes your plugin config* below first.

**Restart after any update.** The Skill tool resolves the plugin directory once per
session: after `claude plugin update`, a skill invoked in the same session still loads
from the directory it resolved before, and neither `plugin update` nor `/reload-plugins`
repoints it. A check made through the Skill tool without a restart reads the old text.

Unverified: whether a GitHub-source marketplace caches the same way. On a GitHub source,
local edits reach nothing until they land on `main` regardless.

## Testing a change to a skill

Use `--plugin-dir`, which serves the working tree directly:

```bash
claude --plugin-dir ./plugins/gh-issue-flow
```

Skills are read at invocation, so under `--plugin-dir` a local edit takes effect
immediately, and `/reload-plugins` picks up further edits without a restart.

## Testing a change to an agent

Two traps, and both return a plausible result from the wrong file.

**Agent types resolve at session start.** Editing an agent file, or installing the plugin,
changes nothing for the session already running: the spawn fails with
`Agent type '<name>' not found`, listing the agents as they were at launch.
`/reload-plugins` refreshes skills, not agents. So an agent edit cannot be tested in the
session that made it; restart first.

**A same-named agent elsewhere silently wins.** If `~/.claude/agents/` or the project's
`.claude/agents/` holds `issue-planner.md` or `diff-reviewer.md`, that file runs and the
plugin's copy never does. There is no warning, and the shadowing agent returns a plausible
result, so every symptom points at the file you edited, which is not the file executing.
A bare `issue-planner` resolves to whichever file wins; only the namespaced
`gh-issue-flow:issue-planner` reaches the plugin's.

Verify before testing:

```bash
claude plugin list                 # must show gh-issue-flow enabled
ls ~/.claude/agents/               # anything here with a matching name shadows the plugin
```

Then spawn `gh-issue-flow:issue-planner` with a `Plugin:` line naming the absolute path of
`plugins/gh-issue-flow`. Without it the agent reads the lens set from the newest installed
copy, not your working tree.

To test the installed path against your working tree rather than the published version,
add the checkout as a directory source, then reinstall on every change you want to see,
because the install is a copy:

```bash
claude plugin marketplace add ./
claude plugin uninstall gh-issue-flow
claude plugin install gh-issue-flow@claude-workflows
```

Restart to apply it. That recipe wipes your plugin config; read the next section first.

### The reinstall wipes your plugin config, and nothing says so

`claude plugin uninstall` empties your `userConfig`, and the reinstall does not put it
back. It lives in `~/.claude/settings.json` → `pluginConfigs`, keyed by plugin id:

| Step | `pluginConfigs` |
|---|---|
| `install … --config board_number=1` | `{"gh-issue-flow@claude-workflows": {"options": {"board_number": "1"}}}` |
| `claude plugin uninstall gh-issue-flow` | `{}` |
| `claude plugin install …` | `{}` — not restored |

`claude plugin marketplace remove <name>` wipes `pluginConfigs` too, for every plugin that
marketplace provided, and dropping the `./` source is how the recipe above is undone.
`claude plugin update` is the one command that keeps it, which is the reason to bump the
version rather than reinstall. Write the values down before you run the recipe. To
recover them, re-supply them; `--config` is repeatable and works on an installed plugin:

```bash
claude plugin install gh-issue-flow@claude-workflows \
  --config board_number=<n> --config board_owner=<owner>
```

Then `/reload-plugins` in any running session: option values are memoized per plugin id
in-process, and the subprocess that wrote them cannot invalidate that map.

What you lose is a machine-wide default. Any repo that names its own board in
`workflow.json` → `board` is unaffected, because that layer wins. Why `pluginConfigs`
cannot be per-repo: [`README.md`](README.md#configuration-in-three-layers) § Layer 1.

Two things this is not. It is not the *"N userConfig options not yet set"* line the install
prints — that appears whether or not you ever had config, and what it counts is in
[`README.md`](README.md#1-install). And it is not something to diagnose by sharing that
settings file — it also holds `permissions` and every other plugin's configuration. Read
the one key, not the file.

## Bump `version` in the same PR as any behaviour change

`plugin.json` → `version`, and both `version` fields in
`.claude-plugin/marketplace.json`. The bump is the only thing that gives
`claude plugin update` anything to do; without it a merged change reaches no running
session.

`tests/test_version_agreement.py` reds when the three disagree. `claude plugin validate`
alone does not: `plugin.json` disagreeing with `marketplace.json` → `plugins[0].version`
exits 1, but a stale or deleted top-level `version` passes `--strict` at exit 0, and
`claude plugin tag` validates only "plugin.json and any enclosing marketplace entry".
Nothing can tell you that you forgot to bump at all, so read the three back yourself.

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

**A claim here comes from running the thing.** When a doc states a number or a behaviour,
it was checked by running it. If you change a claim, re-check it or mark it unverified.
How it was checked, and the story of a claim that turned out wrong, go in the PR body's
History
([`git-and-github.md` § Writing a PR body](plugins/gh-issue-flow/reference/git-and-github.md#writing-a-pr-body));
the doc states the current fact. Comments and docs follow
[`comments-and-docs.md`](plugins/gh-issue-flow/reference/comments-and-docs.md).

**The single-owner guard will block you, and that is the point.**
`tests/test_single_owner_facts.py` pins each clause in `OWNED` to exactly one owning file.
Rewrite a section so a pinned clause stops existing, and it fails with *"0 means the owner
lost it — did a rewrite drop the fact?"* Update `OWNED` in the same commit; do not route
around it by deleting the entry.

The guards that hold docs to each other — `test_single_owner_facts.py`,
`test_config_schema.py` and `test_doc_headers.py` — are this repo's exception to "don't
write a test that pins prose" in
[`comments-and-docs.md`](plugins/gh-issue-flow/reference/comments-and-docs.md). In a
repo of markdown the only source a doc can be checked against is another doc, so they
pin clauses, headers and counts; no structural check can see a copied sentence without
comparing text.

**A guard is mutation-proven, and a change to it is re-proven.** A re-proof covers both
halves: the mutants that must red, and the edits that must stay green, which is what stops
a guard reddening on ordinary reformatting. The cases each guard's re-proof includes:

- `test_single_owner_facts.py`: a softened or inverted owner and an exact copy elsewhere
  red; a hard-wrap, moved emphasis, a move within the owner and a paraphrase elsewhere stay
  green. Match a pinned clause as the owner wraps it.
- `test_config_schema.py`: a dropped row, an example key with no row, a Since above
  Current, a key setup never mentions, a missing Current line, a duplicate row and an
  emptied table red; reversed rows, padded cells, a reworded Meaning and a legitimate
  schema bump stay green.
- `test_links.py`: a typo'd path, a link to an untracked file, a link escaping the repo, a
  link climbing out of the plugin directory to a marketplace-only path, and a parser that
  matches nothing red; an anchor link and a mix of `./`, directory, `https:` and `#` links
  stay green. It strips fences and code spans first, because a link quoted in a code span
  is an example, and it checks the plugin boundary as well as the repo's.
- `test_doc_headers.py`: a renamed skeleton header, a renamed table row, a "§ Infra" short
  reference, demoted headers, an added header the table lacks, and a header present in
  both skeletons red; a reordered table and a mix of other § references with full header
  names stay green. References are compared word by word, because a greedy match lets a
  short form through.
- `test_version_agreement.py`: any disagreement among the three numbers reds, including a
  stale top-level `version` that `claude plugin validate` passes; three equal numbers,
  before and after a legitimate bump of all three, stay green.

**Facts live in one place.** `shared/execution.md` owns mechanics; skills own policy and
link to it. If you find yourself pasting the same rule into two skills, it belongs in
`shared/` — that is exactly the drift the guard exists to catch.
