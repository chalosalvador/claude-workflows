# Reference docs

Hard-won operational knowledge, distilled from measured incidents. Skills in this
plugin link to these at the moment they become relevant — read the section, not the
file, unless you are about to do the whole thing.

| Doc | Read it when |
|---|---|
| [`verification.md`](verification.md) | Before writing any claim of the form "X is clean / done / absent" into a commit message, PR body, or report. |
| [`guard-tests.md`](guard-tests.md) | The change adds a guard, invariant, scan, or lint-style test that asserts something about the repo. |
| [`mutation-harness.md`](mutation-harness.md) | You are about to mutation-prove a test, or you are reading a harness's numbers. |
| [`git-and-github.md`](git-and-github.md) | Checking diff scope, diagnosing CI-vs-local, writing a PR body, or merging. |
| [`review-process.md`](review-process.md) | Before opening any PR. Also when adjudicating reviewer findings. |
| [`parallel-agents.md`](parallel-agents.md) | Before spawning parallel reviewers, or before any worktree squash/reset. |
| [`openspec.md`](openspec.md) | The repo has an `openspec/` directory — install, where the spec change sits in the flow, and what its validate does NOT assert. |
| [`shell-traps.md`](shell-traps.md) | Writing any shell loop, batch-edit script, or script that holds a credential. |
| [`secrets-and-ci.md`](secrets-and-ci.md) | Provisioning a secret or environment variable; diagnosing green-local/red-CI. |

## The one idea underneath all of them

**Silence, an empty result, and exit 0 are indistinguishable from success.** Almost
every incident recorded here is a tool that did nothing while looking like it worked:

- a grep whose pattern could not match
- a CLI that exited 0 on a request the server rejected
- a mutation that never applied
- a guard satisfied by a comment about the guard
- a harness whose file another agent had overwritten
- a secret one byte longer than the one every client holds

So the recurring instruction is the same in every doc: **prove the positive case
first.** Prove the grep matches something. Prove the mutation landed. Prove the
control is green. Then, and only then, is an empty result evidence.

For the evidence behind that claim — four bugs found in this plugin by running it against
live systems, none caught by review or CI — see
[Why the plugin is shaped like this](../README.md#why-the-plugin-is-shaped-like-this).
