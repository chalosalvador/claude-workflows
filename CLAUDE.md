# claude-workflows — working notes

A Claude Code plugin marketplace. `README.md` explains what it is and how to install it;
[`CONTRIBUTING.md`](CONTRIBUTING.md) holds the gate and every procedure below in full. This
file is the short list of things that are not obvious from the tree and have already
caused wasted work.

## Before you change anything

- **`main` is protected.** Every change needs a branch and a PR, the owner's included:
  [§ `main` is protected](CONTRIBUTING.md#main-is-protected--everything-goes-through-a-pr).
- **The gate** is [§ The gate](CONTRIBUTING.md#the-gate); CI runs it as the `guards` job.
  Stage the paths you changed before running it, because the guards that list files read
  the index.
- **Bump `version` in the same PR as any behaviour change**, in `plugin.json` and both
  fields of `.claude-plugin/marketplace.json`, and read the three back:
  [§ Bump `version`](CONTRIBUTING.md#bump-version-in-the-same-pr-as-any-behaviour-change).
- **Comments and docs** follow
  [`comments-and-docs.md`](plugins/gh-issue-flow/reference/comments-and-docs.md), and no
  test or CI step checks them: run the `comments` lens before a PR, as
  [§ Conventions](CONTRIBUTING.md#conventions) says.

## Testing what you changed

- **A directory-source install serves its checkout, not the cache.** Every session on the
  machine runs whatever that checkout has on disk, and `claude plugin update` changes
  nothing it loads. Test with `claude --plugin-dir ./plugins/gh-issue-flow`, or put the
  checkout on the branch under test for the whole run and put it back on `main` after;
  the session's init event names the path and version it loaded:
  [§ What the installed plugin serves](CONTRIBUTING.md#what-the-installed-plugin-serves).
- **Agents resolve at session start, and a same-named agent shadows the plugin's.** An
  agent edit cannot be tested in the session that made it; check `ls ~/.claude/agents/`
  and always spawn the namespaced `gh-issue-flow:<agent>`:
  [§ Testing a change to an agent](CONTRIBUTING.md#testing-a-change-to-an-agent).
- **Uninstall and `marketplace remove` wipe your plugin config; `claude plugin update`
  keeps it.** Write the values down before a reinstall:
  [§ The reinstall wipes your plugin config](CONTRIBUTING.md#the-reinstall-wipes-your-plugin-config-and-nothing-says-so).

## Testbed

End-to-end changes should be exercised against a throwaway repo, not a real one — see
[§ Build your own testbed](CONTRIBUTING.md#build-your-own-testbed) for how to build one in
about ten minutes.

The maintainer's is `chalosalvador/claude-workflows-testbed` + Projects board **1**
(owner `chalosalvador`) — **you will not have write access to it, so make your own.** It
is a small Python repo with real CI and six deliberately varied issues; its `main` is
deliberately unprotected; `scripts/reset.sh` in that repo returns it to pristine
(`--dry-run` first).

In that repo the `README.md` install line is **deliberately wrong** — it is the fixture
for one of its issues, not a bug. `scripts/reset.sh` restores the broken form on every
reset.
