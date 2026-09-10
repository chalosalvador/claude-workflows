# claude-workflows — working notes

A Claude Code plugin marketplace. `README.md` explains what it is and how to install it;
this file is only the things that are **not** obvious from the tree and have already
caused wasted work.

## Validation gate

The commands are in [`CONTRIBUTING.md`](CONTRIBUTING.md#the-gate) § The gate. CI runs
them as the `guards` job.

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

### An unbumped version serves a stale plugin, silently

While `version` is unchanged, the cache keeps the tree from the last install however far
`main` moves on. Every change merged since is invisible to every session — a skill runs
the text it had at install, including a query `main` has since replaced — and nothing
anywhere says so.

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

**The Skill tool's plugin directory is resolved once per session too.** After `claude
plugin update`, a skill invoked in the same session still loads from the cache directory
it resolved earlier, and neither `plugin update` nor `/reload-plugins` repoints it. So
the version you just updated to is **not** what this session runs until you restart, and
a measurement made through the Skill tool without a restart measures the old text.

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

`tests/test_single_owner_facts.py` pins sixteen clauses to exactly one owning file. If you
rewrite a section and the pinned clause stops existing, it fails with
`0 means the owner lost it — did a rewrite drop the fact?`

**Update `OWNED` in the same commit.** It has already caught its own pin going stale
three times, which is the cost-is-the-feature behaviour it was built for. Do not route
around it by deleting the entry.

It is mutation-proven 11/11 (7 kill + 4 must-stay-green); the two board pins added later were proven 7/7 (3 kill + 4 must-stay-green) on top, the two ops-doc pins 8/8 (4 kill + 4 must-stay-green), the area-map pin 8/8 (4 kill + 4 must-stay-green), and the out-of-sweep pin 8/8 (4 kill + 4 must-stay-green). If you change it, re-prove it —
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

In that repo the `README.md` install line is **deliberately wrong** — it is the fixture
for one of its issues, not a bug. `scripts/reset.sh` restores the broken form on every
reset.

## Convention

Comments and docs here follow
[`plugins/gh-issue-flow/reference/comments-and-docs.md`](plugins/gh-issue-flow/reference/comments-and-docs.md),
and `tests/test_comment_policy.py` checks the lines a branch adds. How a claim here is
measured, and where the measurement goes: [`CONTRIBUTING.md`](CONTRIBUTING.md#conventions)
§ Conventions.
