# Resolving configuration

Every skill in this plugin needs facts that differ per person and per repo. **Never
hardcode them, and never guess silently** — resolve them in this order and say which
layer answered when it matters.

---

## Layer 1 — plugin `userConfig` (per person, prompted on enable)

| Placeholder | Meaning |
|---|---|
| `${user_config.board_number}` | **Default** Projects v2 board number, e.g. `11` — a repo's `workflow.json` → `board` overrides it |
| `${user_config.board_owner}` | **Default** board owner, same override |
| `${user_config.status_in_progress}` | Status option name for work in flight — **defaults to `In Progress`** |
| `${user_config.ready_label}` | Label marking an issue safe for unattended work — **defaults to `agent-ready`** |

**None of the four is required**, and the two with defaults work unset — which is why the
install's "N options not yet set" count is not an error.

**`pluginConfigs` is stored per person, not per repo.** `--config` writes
to `~/.claude/settings.json` and lands there **even under `--scope project`** — a project
`.claude/settings.json` is never consulted for it. So Layer 1 holds **one** value per
machine and cannot by itself follow you between projects.

**So Layer 1 is only the DEFAULT board, never the answer** — a repo's `workflow.json` →
`board` wins. The board half of resolution (the order, the machine default, the way back
after a wipe, the fatal `${BOARD:-…}` idiom) is [`board.md`](board.md) § Resolution, read
only by the skills that touch a board. Every skill runs the step below.

---

## Resolving `workflow.json` and the deploy-target docs — every run

**Step 1 — ask the repo, from its root.** A bare relative path is wrong in any cwd below
the root.

**`git rev-parse --show-toplevel` is NOT enough — in a worktree it returns the
WORKTREE**, and `.claude/` is commonly gitignored, so `workflow.json` lives only in the
main checkout and the override silently vanishes. In a worktree:
`--show-toplevel` → the worktree (no file); `--git-common-dir` → the main checkout. That
is `autopilot`'s normal scheduled path, where an unattended run would then write to the
machine-default board with nobody to check with. Look in both, worktree first:

```sh
WT=$(git rev-parse --show-toplevel) || { echo "NOT INSIDE A CHECKOUT — cd into a repo and rerun; nothing is resolved yet"; exit 1; }
echo "repo=$(git -C "$WT" remote get-url origin 2>/dev/null | sed -E 's#^(git@|https://)github.com[:/]##; s#\.git$##' | grep . || printf '%s\n' -)  wt=$WT"  # which checkout answered
MAIN=$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)") # main checkout
WF=""
for D in "$WT" "$MAIN"; do
  [ -f "$D/.claude/workflow.json" ] && { WF="$D/.claude/workflow.json"; break; }
done
if [ -n "$WF" ]; then
  jq -r '"number=\(.board.number // "-")  owner=\(.board.owner // "-")"' "$WF"
  jq -r '"schema=\(.schemaVersion // 0)"' "$WF"        # step 2 compares this to Current schema
  jq -r '"targets=\(.deployTargets // [] | join(",") | if . == "" then "-" else . end)"' "$WF"  # step 3
  echo "src=$WF"
else
  echo "NO workflow.json in $WT or $MAIN"
fi
SD=""                                                   # the deploy-target docs live beside it — same two places
for D in "$WT" "$MAIN"; do
  [ -d "$D/.claude/workflow/deploy-targets" ] && { SD="$D/.claude/workflow/deploy-targets"; break; }
done
if [ -n "$SD" ]; then
  find "$SD" -maxdepth 1 -name '*.md' | sort | sed 's#.*/#targetdoc=#'
else
  echo "NO deploy-targets dir in $WT or $MAIN"
fi
RD=""                                                   # the per-repo doc, same two places
for D in "$WT" "$MAIN"; do
  [ -f "$D/.claude/workflow/repo.md" ] && { RD="$D/.claude/workflow/repo.md"; break; }
done
[ -n "$RD" ] && echo "repodoc=$RD" || echo "NO repo.md in $WT or $MAIN"
```

**`find`, not a glob, for the deploy-target docs.** `ls "$SD/"*.md` on an
existing-but-empty directory is a zsh `no matches found` error at exit 0 — no listing, no
sentinel, and the main checkout never tried. `find` prints nothing and the `else` still
distinguishes "no directory" from "empty directory".

**The `|| { … exit 1; }` and the explicit `else` are load-bearing, not decoration.**
Both failure shapes read as a clean run: without the first, a non-repo cwd adopts a
board from a stray file at exit 0; collapsed to `for … done || echo`, the boardless case
prints nothing at all.
[`../reference/shell-traps.md`](../reference/shell-traps.md) § A loop's fallback never fires.

In a normal checkout the two are identical and the loop reads it once.

**The `repo=` line says which checkout answered, and nothing else in the output does.**
Every other line of a run in the wrong repo looks exactly like a run in the right one: a
freshness check meant for one of two sibling checkouts, run without changing directory,
reports the other checkout's divergence as the intended one's. The line is the remote's
spelling, not the canonical owner — an org transfer does not
rewrite remotes, so a transferred repo still prints its old org here — which is why it
identifies WHICH checkout answered and is never the value to build API paths from; the
canonical `owner/repo` comes from `gh repo view --json nameWithOwner`, as the skills
already say. It never calls `gh` and never aborts the block: a checkout with no `origin`
prints `repo=-`, and a non-GitHub remote prints the URL as it is. The `| grep .` is
load-bearing: a pipeline's status is `sed`'s, so without it the fallback never fires —
a no-remote checkout prints `repo=` and nothing after it. And the fallback is
`printf`, not `echo '-'`: zsh's builtin `echo` reads a lone `-` as the end of
its options and prints nothing, so under zsh `echo '-'` prints the same empty `repo=`.

**A workspace directory holding several checkouts is a supported starting point**, and a
scheduled routine may start in one. The block cannot run *there* — a plain directory is
not a git repo, so its first line prints `NOT INSIDE A CHECKOUT` and stops — and that
line is a location error, never an answer about the board. `cd` into each repo you will
sweep (§ Repo scope) and run the block inside it, once per repo; each run's `number=` /
`schema=` / `targets=` lines are that repo's, and the `repo=` line is what proves it. A
`repo=` that names a different repo than the one you meant to resolve is the location
error to catch before reading anything else.

**Fetch before you trust the file.** The block reads the working tree, which is
whatever the checkout is parked on: a shared checkout behind its remote prints the old
`schema=` and `targets=`, and nothing in the output says so. So `git fetch origin` first,
then compare the working-tree file with the integration branch's copy — take
`integrationBranch` from the working-tree file to know which ref to read:

```sh
IB=$(jq -r '.integrationBranch // empty' "$WF")            # e.g. origin/dev
[ -n "$IB" ] && { git show "$IB:.claude/workflow.json" 2>/dev/null | jq -S . | diff -q - <(jq -S . "$WF") >/dev/null \
  || echo "workflow.json differs from $IB — the checkout is parked or behind; use the $IB copy and say so"; }
```

A checkout parked on a feature branch, or left behind by another session, is the common
cause; a stale reading is not a drift line's business and must not trigger `upgrade`.
The diff is run from the checkout the `repo=` line names, never from a sibling's.

**Step 2 — schema drift.** Step 1 also printed `schema=<n>`: the file's `schemaVersion`,
`0` when absent. Compare it to **Current schema** in § Layer 2. When the file is behind,
print exactly one line and carry on:

> `workflow.json is at schema <n>; the plugin expects <current>. Missing: <every key in
> the schema table whose Since is greater than n>. Run /gh-issue-flow:setup upgrade to
> add them.`

Carry on **with defaults** — every key is optional and an absent one falls through to
Layer 3, so a behind file is never a failure. But say it every run. `claude plugin update`
refreshes the plugin's code and tells no repo that its config is now behind; this line
is the only thing that does.

**Step 3 — deploy-target docs.** Step 1 printed `targets=<names or ->` from `workflow.json` and
one `targetdoc=<file>` line per file found. Reconcile them: every name must have a file
and every file a name. A mismatch is a finding to report in one line — a name with no
file means the doc never shipped (commonly `.claude/` gitignored, § Layer 2 →
Deploy-target docs); a file with no name means `setup upgrade` has not run since it was written. Then
read only the files that are named. `targets=-` at schema 4 or later is a deliberate "this repo
detected no deploy target" (`"deployTargets": []`); `targets=-` below schema 4 is covered by step 2.


---

## Layer 2 — `.claude/workflow.json` in the repo

The per-repo override. Read it from the repo root you are working in.

```json
{
  "schemaVersion": 5,
  "deployTargets": ["gcp-terraform"],
  "repos": ["acme/acme-api", "acme/acme-web"],
  "board": { "number": 11, "owner": "acme" },
  "integrationBranch": "origin/dev",
  "mergeMethod": "squash",
  "specFlow": "openspec",

  "preflight": ["test -d .venv"],
  "validate": [".venv/bin/ruff check .", ".venv/bin/python -m pytest tests/ -q"],
  "validateWhenChanged": {
    "terraform/**/*.tf": "terraform fmt -check -recursive terraform/"
  },
  "ciOnly": {
    "Schema Convergence": "needs the postgres service CI provisions"
  },

  "requiredChecks": ["lint-and-test", "build"],
  "protection": { "strict": false, "enforceAdmins": true, "conversationResolution": true },

  "deployOnMerge": "merging this branch auto-deploys staging and runs its migrations",
  "deployWorkflow": ".github/workflows/deploy-staging.yml",

  "workstreams": { "apps/admin": "Admin console", "packages/db": "Shared — database" },
  "areaLabels": { "area:backend": "what belongs here" },
  "dri": { "area:backend": "octocat" },
  "driOverrides": { "security": "octocat" },
  "trackForArea": { "area:backend": "Backend" },
  "agentReadyForbiddenPaths": ["terraform/**", "migrations/**"],
  "priorityCaps": { "legal": "P1" }
}
```

Every key is optional. Absent keys fall through to Layer 3.

### Schema

**Current schema: 5.** A file with no `schemaVersion` is schema **0** — the shape that
shipped through plugin 0.5.x. `setup` writes the current number on bootstrap and
`setup upgrade` moves an older file forward by adding what it lacks. **Since** is the
schema a key arrived in; that column is the migration list, and it is what the drift
line in § Resolving `workflow.json` step 2 reads. `tests/test_config_schema.py` holds this table, the
example above and `setup`'s probe list to the same key set.

| Key | Since | Setup | Scope | Meaning |
|---|---|---|---|---|
| `schemaVersion` | 1 | always written | file | Which shape this file has; `0` when absent |
| `repos` | 0 | § 2 | file | Every repo the multi-repo skills sweep, full `owner/repo` |
| `board` | 0 | § 2 | board | This repo's Projects v2 board; overrides Layer 1 |
| `integrationBranch` | 0 | § 2 | repo | Remote ref to branch from and merge into |
| `mergeMethod` | 0 | § 2 | repo | `squash` / `rebase` / `merge`, from the repo's allowed set |
| `specFlow` | 0 | § 2 | repo | `openspec` when the directory exists, else absent |
| `preflight` | 0 | § 2 | repo | Machine-level deps the gate needs and no lockfile installs |
| `validate` | 0 | § 2 | repo | The gate, verbatim from CI, run every time |
| `validateWhenChanged` | 0 | § 2 | repo | Glob → command, run only when the diff touches it |
| `ciOnly` | 0 | § 2 | repo | Required checks not to attempt locally, each with the reason |
| `requiredChecks` | 0 | § 2 | repo | Check names protection requires |
| `protection` | 0 | § 2 | repo | `strict`, `enforceAdmins`, `conversationResolution` |
| `deployOnMerge` | 0 | § 2 | repo | What merging the integration branch does, in words |
| `deployWorkflow` | 0 | § 2 | repo | The workflow file `deployOnMerge` was read from |
| `workstreams` | 0 | § 2 | repo | Monorepo path → human name |
| `areaLabels` | 0 | § 4 | repo | **This repo's** `area:*` labels → one-line meaning; a sibling's live in its own file |
| `dri` | 0 | § 4 | repo | **This repo's** `area:*` labels → GitHub login that owns each here |
| `trackForArea` | 0 | § 5 | repo | **This repo's** `area:*` labels → board Track option |
| `agentReadyForbiddenPaths` | 0 | § 2 | repo | Paths an unattended run must never touch |
| `$comment*` | 0 | § 3 | file | Provenance for the human reader. `setup upgrade` reads them for hints, and triage reads `$comment_dri` only as the fallback the `driOverrides` bullet describes |
| `deployTargets` | 4 | § 5b | repo | The deploy-target doc names this repo carries, one per file in `.claude/workflow/deploy-targets/`; `[]` when the evidence names none. Schema 3 called this `stacks`; `upgrade` renames the key and the directory |
| `priorityCaps` | 3 | § 2 | board | Label → highest priority that label may carry, applied by `triage` § 3c. Absent means `{"legal": "P1"}`; `{}` turns caps off |
| `driOverrides` | 5 | § 4 | repo | Label → GitHub login that owns an issue carrying it in **this repo**, whatever its area; the issue keeps its area's Track |

**Scope is what `repos` cannot widen.** A `board` key describes the Projects v2 board
every repo in `repos` feeds — `board` and `priorityCaps`, nothing else — and applies to
every issue a run sweeps. A `repo` key describes **the repo this file lives in** and
nothing else: its branch, gate, forbidden paths, deploy-target docs, **and its area
map** — `areaLabels`, `dri` and `trackForArea` name the `area:*` labels this repo
carries, described from this repo's point of view, and no other repo's. A `file` key is
about the file itself. So a run that sweeps a sibling from `repos` reads the two
board-level facts from this file and everything else **from the sibling's own
`workflow.json`** — its checkout when one resolves, else the file read from GitHub
(§ Repo scope). A sibling's area map comes from the sibling's own `workflow.json`,
never this one. A file that also carries a sibling's areas keeps working — an entry for a
label this repo does not have is never read for an issue here, and `setup check` lists it
as cleanup. A `repo` key read from the wrong file fails silently: with both repos listed
and one file, `work-summary` would judge every sibling commit against this repo's
`integrationBranch` — a branch the sibling may also have, long stale — and report merged
work as unmerged.

### Deploy-target docs and `repo.md` — `.claude/workflow/`

**Everything stack-specific lives in the repo, not in this plugin**, in two kinds of file
under `.claude/workflow/`:

- **`deploy-targets/<name>.md` — one per place code gets deployed**, not per technology:
  Vercel, Cloud Run, Terraform-applied infra, Fly, Kubernetes. Each holds what a merge
  deploys, how a secret is set and read back there, and what applies migrations. A
  database, a framework or an auth provider is not a target; it appears inside the
  sections of the target that deploys it. `setup` § 5b generates these from
  `skills/setup/deploy-target-template.md`; `workflow.json` → `deployTargets` names them,
  and that key is what lets the drift line, `upgrade` and `$comment_deployTargets`
  provenance carry them like every other key.
- **`repo.md` — exactly one per repo**, from `skills/setup/repo-template.md`: which bot
  reviews pull requests and how its comments look, the invariants a reviewer checks every
  diff against, and the traps. These do not vary by target, which is why they
  are not in the target docs — a repo with two targets would otherwise carry two copies
  of its review-bot patterns.

§ Resolving `workflow.json` step 1 prints the target names, the target files it finds and
whether `repo.md` exists (worktree first, then the main checkout, because `.claude/` is
commonly gitignored in a worktree); step 3 reconciles names with files, and a name with no
file or a file with no name is a one-line finding, never a silent skip.

**Skills read the section headers**, which is why both skeletons say to keep them exactly:

| Section | File | Read by | For |
|---|---|---|---|
| Identity | target | `setup` read-back | the name and the evidence it came from |
| Deploy | target | `issue-planner` (into HANDOFF), [`execution.md`](execution.md) § 7, the `deploy` lens via HANDOFF | what a merge does, and the paths filter — as a **starting point**; § 7 still verifies against the live workflow |
| Secrets and env | target | `triage` § 4, `autopilot` § 7 | why a credential change is human-gated here, and how a value is verified |
| Infra and migrations | target | `triage` § 4, `autopilot` § 3, the `deploy` lens via HANDOFF | the apply commands and the ordering rules; the forbidden paths stay in `workflow.json` |
| Review bot | repo.md | [`execution.md`](execution.md) § 5 | which comment is an ack and which is a review |
| Reviewer invariants | repo.md | `issue-planner` (into HANDOFF), the `safety` and `contract` lenses via HANDOFF | the predicates and cross-store parities to check every diff against |
| Traps | repo.md | `issue-planner` (it reads the whole file); written only through the proposal line in `next-issue` § 6 and `autopilot` § 10 | traps on this repo and what to do instead, undated |

**The planner reads the files once and carries the lines that apply into its HANDOFF
`Ops docs:` field; the lenses read the HANDOFF, not the files.** That is
[`execution.md`](execution.md) § 3.1 lever 1 applied, and it is also what keeps a lens
spawned inside a worktree from missing a doc that sits in the main checkout.

Three rules for a reader:

- **A section marked `UNVERIFIED` is an unknown, not an all-clear.** Say "the deploy-target doc
  does not say" rather than proceeding as if the answer were "nothing".
- **The doc is a snapshot.** For anything that decides a deploy claim, start from the
  doc and verify against the live workflow ([`execution.md`](execution.md) § 7). A doc
  that disagrees with the workflow is a finding to report, and the workflow wins.
- **Agents do not edit deploy-target docs or `repo.md`.** A run that learns something says so in its PR
  handoff — "add to `repo.md` § Traps" — and a human commits it.

**No deploy-target docs at all** has two honest shapes, and § Resolving `workflow.json` tells them apart: a file
below schema 4 gets the drift line naming `deployTargets` as missing; a file at schema 4 or later with
`"deployTargets": []` chose none, and step 3 says so in one line. Every skill still works from
the generic rules; what it loses is the stack-specific half of each lens.

These carry weight the others do not:

- **`board`** names the Projects v2 board **this repo** feeds, and it **overrides**
  Layer 1. It is what lets one machine work several workspaces that target different
  boards — set it in every repo whose board is not your machine default, and the skills
  stop needing you to re-run the install between projects. `owner` is the board's owner,
  which is **not** necessarily the repo's (§ Owners are per-repo). Absent → Layer 1.
- **`repos`** is the repo list every multi-repo skill means by "every configured repo" —
  `triage`'s working set, `next-issue`'s theme sense, `work-summary`'s scope, and
  `autopilot`'s backpressure check all expand it. **Full `owner/repo`, never bare names**,
  because two repos on one board can sit under different owners. Absent → § Repo scope.
- **`dri`** maps each of **this repo's** area labels to the GitHub login that owns it here
  — a sibling's map is in the sibling's file, and one login owning one area in two repos
  appears in both — and it is what makes
  triage's **0-unassigned** guarantee possible — without it the integrity pass has no
  routing table and can only report the gap. Keep it beside `areaLabels`; an area with no
  DRI is the same failure as no area label.
- **`driOverrides`** maps a label to the login that owns an issue carrying it in this
  repo, whatever its area — commonly `security`, `compliance` or `legal` going to one
  person. Triage assigns from it before `dri` whenever it assigns: in triage § 2, and in
  triage § 5 when its own deep pass adds such a label to an issue it has just assigned.
  An issue a human already assigned keeps its owner. With more than one such label, the
  first in the key's order wins; either way the issue keeps its area's Track. Where one
  area ends and the next begins belongs in the `areaLabels` meanings, not here. A file
  below schema 5 may still state an override, or an area boundary, as prose in
  `$comment_dri`: triage applies it from there for that file only and says so in its
  receipt, and `setup upgrade` proposes the key.
- **`validate`** runs every time. **`validateWhenChanged`** maps a glob to a command run
  only when the diff touches it — keep slow or narrow gates here, not in `validate`.
- **`ciOnly`** names a required check you must **not** attempt locally, *with the reason*.
  A gate that needs a service, a secret, or a multi-GB download belongs here — running it
  and reading its failure as your own is the mistake this key exists to prevent.
- **`$comment*`** keys are for the human reading the file. A `$comment_<key>` names the
  source path, or the command that derives the value, so the next reader re-derives
  rather than trusts. It never carries a date; `git blame` dates the line. Every list in
  here is a snapshot of something that moves, and a transcribed file list or
  `paths-ignore` copy is the first thing to rot.

**Prefer a command that DERIVES a list over one that hardcodes it** — e.g. reading the
file set out of the CI workflow at run time rather than transcribing it. Verify the
derivation selects exactly what CI selects before trusting it; a superset false-reds on
files CI never reads.

---

## Layer 3 — probe the repo

With no `workflow.json`, derive what you can. **This is the default path** — the
plugin must work in a repo that has never heard of it.

```sh
gh repo view --json nameWithOwner,defaultBranchRef,squashMergeAllowed,rebaseMergeAllowed
```

| Need | Probe |
|---|---|
| `integrationBranch` | `origin/` + `defaultBranchRef.name`. Not always `main` — some repos integrate on `dev` and release from `main`. If the default branch looks like a release branch (a `dev`/`develop` branch exists and is ahead), **ask** rather than assume. |
| `validate` | `pyproject.toml`/`requirements.txt` → `pytest`, `ruff`. `package.json` → read its `scripts` block and run lint/typecheck/test/build that exist. `Cargo.toml` → `cargo test`, `cargo clippy`. Prefer copying the **CI workflow's** commands over inventing them. |
| `specFlow` | An `openspec/` directory at the repo root → `"openspec"`. Otherwise none. See [`../reference/openspec.md`](../reference/openspec.md). |
| `mergeMethod` | `squashMergeAllowed` / `rebaseMergeAllowed` from `gh repo view`. |
| `deployOnMerge` | Grep `.github/workflows/` for a workflow with `branches: [<integration>]` that deploys. **Do not assume a merge is inert.** |
| `deployTargets` | The file names under `.claude/workflow/deploy-targets/` (§ Resolving `workflow.json` step 1 lists them). Nothing there → none. |
| Required checks | `gh api repos/<owner>/<repo>/branches/<b>/protection` |

**Prefer copying from the CI workflow when it disagrees with anything else.** The
workflow is what actually gates the PR.

---

## Repo scope

`triage`, `next-issue`, `work-summary` and `autopilot` all operate over a **set** of
repos. Resolve that set in this order and **say which answered**:

1. `workflow.json` → `repos` — the explicit list, full `owner/repo`.
   From a **workspace directory** that is not itself a git repo, first `cd` into any
   checkout it holds and read *its* file; the block in § Resolving `workflow.json` cannot
   run in a non-repo directory and says so.
2. No `repos` key → **the repo you are in**, and only that one:
   `gh repo view --json nameWithOwner --jq .nameWithOwner`. This is the common case
   and it is correct — do not go looking for siblings to widen the scope.
3. The user named repos in the request → use exactly those, for this run only.

**A repo in `repos` is not necessarily checked out, and its checkout is not
necessarily a sibling directory named after it.** `git -C <repo-name>` is a *guess*
about someone's disk layout, and it fails in the ordinary single-repo case where you
are already inside the only checkout. Before any `git -C`, resolve a real path — the
current toplevel for the repo you are in, an explicit path the user gave, or a sibling
that `git -C <path> rev-parse --show-toplevel` actually confirms:

```sh
git rev-parse --show-toplevel                       # the repo you are in
git -C "<candidate>" rev-parse --show-toplevel      # prove a sibling before using it
```

**A repo with no resolvable checkout is not an error** — every issue, PR and board
operation goes through `gh` and needs no working copy. Only commit-log reads and
repo-level facts do. Skip those for that repo and **say you skipped them**, rather than
silently reporting it as a quiet day.

**`repos` is the issue-sweep set, not a config merge.** Listing a sibling widens which
issues, PRs and merged work a run reads. It does **not** make this file's `repo`-scoped
keys (§ Layer 2 → Schema, Scope column) apply to the sibling. For every sibling you
sweep:

| You need the sibling's | Read it from |
|---|---|
| board, priority caps | **this** file; they describe the shared board |
| area labels, DRI, owner overrides, Track — its area map | **the sibling's own** `.claude/workflow.json`: its checkout when one resolves, else the same file read from GitHub (below). Label, assign and set Track on a sibling's issue only from **its** map |
| integration branch, gate, forbidden paths, deploy-target docs, workstreams | **the sibling's own** `.claude/workflow.json` (its checkout, worktree then main, per the block in § Resolving `workflow.json` run from that checkout) |
| branch, gate, forbidden paths, docs with no checkout | nothing — the sibling is **board-only** this run: sweep its issues for the integrity pass, never gate one `agent-ready`, never judge its merges, never pick it to implement, and say so once |

**Reading a sibling's file with no checkout** is a two-step read, because the file is
current on the sibling's integration branch and you do not know that branch until you
have read the file once:

```sh
ref=$(gh repo view <owner/repo> --json defaultBranchRef --jq .defaultBranchRef.name)
gh api "repos/<owner>/<repo>/contents/.claude/workflow.json?ref=$ref" --jq .content | base64 -d
# if the result's integrationBranch names another branch, read again at that ref
```

That read gives you the area map only — never run a gate or judge a merge from it. A
404 means the sibling has no tracked file (most often `.claude/` is gitignored there,
see `setup` § 3): then the sibling has no map this run either — add its issues to the
board and set Status, report every unlabeled or unassigned one as a gap, and label
nothing there. Never fall back to this file's map for a sibling's issue.

Two files that both list each other must agree on `board` and `priorityCaps`; their area
maps are per repo by design and are not compared. `setup check` diffs the two shared keys
when both files can be read and reports a disagreement as a Missing row; for the map it
checks **coverage** — every `area:*` label the repo has maps to a DRI in the repo's own
file — and lists an entry with no matching label as cleanup, not as a failure.

---

## Owners are per-repo, never one constant

**The board owner and a repo owner are not the same thing, and two repos feeding
one board may sit under different owners.** Never build `<owner>/<repo>` from a
single constant.

- Resolve each repo's owner from its own URL or `gh repo view --json nameWithOwner`.
- Strip owners with `sub(".*/";"")` when comparing repo names — never match a
  literal owner prefix. A transferred repo still HTTP-redirects, so a stale ref
  keeps working in `gh` while silently failing every owner-string match.
- **Issue numbers collide across repos.** In issue and PR text, a bare `#N` resolves
  same-repo, so write `owner/repo#N` when referring across. Comments and docs name no
  issue at all ([`../reference/comments-and-docs.md`](../reference/comments-and-docs.md)).

---

## Things to resolve, never assume

- **The current user**: `gh api user --jq .login`. Never hardcode a login.
- **A test count**: never gate on one. It grows most weeks. Green-vs-red is the gate.
- **A field option id**: read it from `field-list` in the same run.
- **Whether a merge deploys**: read the workflow.
