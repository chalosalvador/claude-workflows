# Working in worktrees, and what parallel agents share

The premise: **parallel agent sessions share the filesystem.** Every trap here is a
consequence of two writers believing they are alone.

---

## Always branch into a dedicated worktree

Never work in a shared main checkout. Its HEAD moves without warning.

Measured twice in one session: a checkout was switched to the integration branch
mid-task by another session — the branch was intact on the remote, but
`git log origin/<base>..HEAD` read `0 commits ahead` until noticed. A second checkout
sat on a third session's feature branch, so a file that was expected did not exist.
Earlier the same session, `git add -A` in a shared checkout swept **another session's
untracked work** into a commit — twice.

```bash
git worktree add <scratch>/wt-<issue> -b feat/<issue>-<slug> origin/<base>
```

- **`cd` into it for every command.** A drifted cwd runs the MAIN checkout's suite —
  and some monorepo task runners resolve repo-wide from a subdirectory regardless.
- **Stage by explicit path.** Never `git add -A` or a directory glob, even inside a
  worktree.
- Gitignored assets the suite needs (model files, fixtures) do not come with a
  worktree — symlink them. ⚠️ A relative symlink like `ln -s ../../../models models`
  can resolve *inside* the tracked directory and produce a suite that crashes at ~83%
  with no summary.
- Some harnesses branch a new worktree off a **stale base**. Verify the base commit
  after creating one.

### 🚨 `git reset --soft <remote-ref>` + `git add -A` SILENTLY REVERTS merged work

The worktree was branched off the base at commit A. While the work proceeded, **two
PRs merged and the base moved to B** — fetches from the *main* checkout update the
shared ref, so this happens with no action in the worktree. Squashing with:

```sh
git reset --soft origin/main && git add -A && git commit
```

set the parent to **B** while the working tree still held **A's** content for every
file the branch never touched — so the commit's diff *reverted* both merged PRs: 444
lines of a new test deleted, a Terraform `depends_on` fix undone (which would have
force-replaced live IAM bindings on the next deploy), and two archived directories
removed.

**`git status` was clean and the suite was green, because the reverted state is
self-consistent.** A review lens caught it. Nothing in a normal gate looks at "files I
did not intend to touch".

> After ANY `git reset --soft <remote-ref>`, and after any `git add -A`, run
> `git diff --cached --name-only` and confirm **every** path is one you meant to
> change. The repair is surgical, not another reset.

---

## 🚨 Review subagents MUTATE the tree they review

A read-only-sounding reviewer with Bash access will verify a mutation check *for
real* — editing a helper into a naive mutant, injecting a statement into a script,
then restoring. Spawn several in parallel and **several agents are editing one shared
worktree concurrently, invisibly to each other.**

Observed: one lens caught another lens's transient mutants mid-review and flagged that
*"a `git add -A` taken while a mutant is resident would ship a broken shared helper"*.
Both restored correctly, but neither knew the other existed.

**The danger is not the mutation, it's the overlap window.** A reviewer restores from
*its own* backup — so if you edit the file while a mutant is resident, its restore
silently reverts your edit; and if you commit while one is resident, you ship the
mutant.

Worse, measured: a lens left a **live mutant behind** after failing to restore it, and
separately **clobbered two edits mid-write** by restoring a file while it was being
edited — an Edit call warned "modified on disk", and the diffstat showed 6 insertions
where there should have been ~100.

**Three habits, all cheap:**

1. **Commit before spawning the lenses.** A committed baseline makes any reviewer's
   damage recoverable and makes `git status` meaningful.
2. **Tell every lens explicitly** to `git archive` the commit into scratch and mutate
   *there*, and to verify `git status --short` is clean before finishing. The lenses
   given this instruction complied; the one that wasn't, didn't.
3. **Never edit a file while a lens is running.** Queue the fixes and apply them after
   every lens reports. If findings arrive while another lens is live, stop it first —
   the wait costs minutes, a clobbered edit costs the session.

**Re-verify before every later commit** — `git diff <base> --stat` plus a grep that
the fixed lines are actually fixed.

> Corollary: a reviewer reporting mutation-check numbers **actually ran them**, so
> those numbers are real evidence — but they were measured on a tree that may not be
> the tree you ship. Re-run the gate on the settled tree before opening the PR.

---

## The scratchpad is shared too

Five lenses ran in parallel, each told to keep scratch files outside the repo. One
wrote its harness to `<scratchpad>/mutate.py` — the exact path an existing 9-case
mutation matrix already occupied. The file was replaced by a different 2,151-byte
script.

**Re-running the clobbered path did not error. It printed nothing and exited 0** —
which reads as "the matrix passed" if you are scanning for a failure.

1. **Name harness files distinctively** — `wf810_matrix.py`, not `mutate.py`. Generic
   names (`test.py`, `check.sh`, `run.py`, `mutate.py`) are exactly what a subagent
   picks too.
2. **Assert the run produced output.** A matrix printing no `KILLED`/`SURVIVED` lines
   did not run. Treat empty stdout as failure, never as silence-means-success.
3. **Re-run the matrices on the settled tree** after every reviewer reports, and read
   the counts — do not trust an earlier run's numbers.
4. Telling a subagent "write scratch files outside the repo" does **not** deconflict
   them from each other or from you; they all land in the same session scratchpad.

---

## Effort tiering: plan max / write high / review max

Tier effort per phase rather than flat:

- **Implementation failures are context failures** — wrong file, stale assumption,
  unread convention — which more reasoning does not fix. The write phase is also the
  longest, so max costs most and buys least there.
- **Planning is where irreversible calls get made** (the seam; whether a wire change
  means two coordinated PRs).
- **Review is where marginal effort converts into caught bugs.** A same-session review
  is anchored on its own plan, so fresh context matters as much as the effort number.

Mechanism: subagent frontmatter supports **`effort`** (`low|medium|high|xhigh|max`),
and it **overrides the session effort level**. There is no way to declare per-phase
effort in a prompt alone.

⚠️ **A subagent cannot fan out** — it has no Agent tool and spawns do not nest. **The
parallelism has to live in the parent**: spawn the reviewer N times, one per lens, in
one message. Gate the lens list on what the planner named; five max-effort reviewers
on a styling change is pure waste.

⚠️ **Project agent discovery walks up from cwd only to the repository root.** An
umbrella directory above two repo roots is not a git repo, so agents defined there are
invisible to a session started inside either repo. `~/.claude/agents/` is
cwd-independent.
