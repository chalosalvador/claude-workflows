# claude-workflows — working notes

A Claude Code plugin marketplace. `README.md` explains what it is and how to install it;
this file is only the things that are **not** obvious from the tree and have already
caused wasted work.

## Validation gate

```bash
python3 tests/test_single_owner_facts.py
python3 tests/test_no_stray_files.py
python3 tests/test_version_agreement.py
claude plugin validate ./plugins/gh-issue-flow --strict
claude plugin validate . --strict
```

CI runs all four as the `guards` job. Everything is markdown and JSON — there is no
build, no install step, no dependency.

## 🚨 `main` is protected. You cannot push to it.

`guards` is a required check with `enforce_admins: true`, plus linear history, required
conversation resolution, and no force-pushes. **Every change needs a branch and a PR**,
including the owner's. A direct push is rejected with `GH006: Protected branch update
failed`.

## 🚨 The installed plugin is served from a CACHED COPY, not this working tree

Registering the marketplace as a **Directory** source does *not* make the installed
plugin a live view of the checkout:

```bash
claude plugin marketplace list     # Source: Directory (<your checkout>) — or GitHub
```

Install **copies** the plugin into a version-keyed cache and serves from there:

```
~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/
```

MEASURED: those files have different inodes from the checkout's, are not symlinks, and
carry the mtime of the install. **The version in that path is `plugin.json` → `version`,
and nothing invalidates the cache while that string is unchanged.**

### This has already served a four-day-old plugin, silently

MEASURED 2026-09-02: the cache held the tree as of `f12f53a` (2026-08-28) while the
checkout sat on `main` **14 commits and 8 merged PRs later** — because `version` had read
`0.1.0` since the initial commit and was never bumped. Every merged change was invisible
to every session. The triage skill that ran still carried the 102-point board query that
had been replaced days earlier, and nothing anywhere said so.

**Both refresh commands report success and change nothing:**

| Command | Says | Does |
|---|---|---|
| `claude plugin marketplace update <name>` | `✔ Successfully updated marketplace` | refreshes the marketplace manifest only — not the cached plugin |
| `claude plugin update <plugin>` | `✔ already at the latest version (0.1.0)` | nothing: it compares versions, and yours did not change |

**Both rows above describe the UNBUMPED case** — that is the whole reason they do
nothing. Once `version` actually changes, `claude plugin update` is the right command and
the safe one. MEASURED, in an isolated config dir, 0.3.0 → 0.3.1:

```
✔ Plugin "gh-issue-flow" updated from 0.3.0 to 0.3.1 for scope user.
cache dirs: 0.3.0  0.3.1        # new dir created
pluginConfigs: PRESERVED         # board number and owner survive
```

So: **bump the version, then `claude plugin marketplace update` + `claude plugin update`.**
Reserve the full reinstall — `claude plugin uninstall <plugin>` then
`claude plugin install <plugin>@<marketplace>` — for the case where the version did
*not* change and the cache is therefore stale. MEASURED: afterwards the cache matched
`main` byte for byte. **A restart is required either way**, and see the agent-discovery
trap below.

🚨 **That uninstall empties your `userConfig`, and the reinstall does not restore it** —
board number and owner included. MEASURED: `claude plugin marketplace remove` wipes it
too, which matters because testing unmerged work starts with `marketplace add ./`.
`claude plugin update` is the one that does **not**, and that asymmetry is the reason to
bump the version rather than reach for the reinstall. Write the values down first. The
measurements, the recovery, and why `--scope project` does not give you a per-repo value:
[`CONTRIBUTING.md`](CONTRIBUTING.md) § *The reinstall wipes your plugin config*.

### So bump `version` in the same PR as any behaviour change

`plugin.json` → `version`, **and** the two `version` fields in
`.claude-plugin/marketplace.json`. That bump is the only thing that gives
`claude plugin update` anything to do. Skipping it is how eight consecutive PRs shipped
to `main` without reaching a single running session.

🚨 **Do not trust the gate to catch a missed bump — MEASURED, it constrains two of the
three numbers and leaves the third free.** An earlier version of this file said
validation covers "the two `version` fields"; that was wrong. **Read all three back
yourself** — which spelling exits 0 and which exits 1, measured:
[`CONTRIBUTING.md`](CONTRIBUTING.md) § *Bump `version`*.

⚠️ **A `git checkout` here does NOT change what the installed plugin serves.** An earlier
version of this file claimed it did; that was wrong, and testing an unmerged branch this
way tests the last copy rather than your work. The live hazard is the reverse of the one
that used to be documented: **your edits do nothing until you reinstall.**

Not measured: whether a `GitHub`-source marketplace caches the same way. On a GitHub
source local edits do nothing until they land on `main` regardless; re-add as a directory
source to test unmerged work — `claude plugin marketplace add ./` — and reinstall after
each change you want to see.

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

`tests/test_single_owner_facts.py` pins twelve clauses to exactly one owning file. If you
rewrite a section and the pinned clause stops existing, it fails with
`0 means the owner lost it — did a rewrite drop the fact?`

**Update `OWNED` in the same commit.** It has already caught its own pin going stale
three times, which is the cost-is-the-feature behaviour it was built for. Do not route
around it by deleting the entry.

It is mutation-proven 11/11 (7 kill + 4 must-stay-green); the two board pins added later were proven 7/7 (3 kill + 4 must-stay-green) on top. If you change it, re-prove it —
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
