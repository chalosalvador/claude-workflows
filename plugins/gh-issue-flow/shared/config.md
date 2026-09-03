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

⚠️ **`pluginConfigs` is stored per person, not per repo.** MEASURED: `--config` writes
to `~/.claude/settings.json` and lands there **even under `--scope project`** — a project
`.claude/settings.json` is never consulted for it. So Layer 1 holds **one** value per
machine and cannot by itself follow you between projects.

🚨 **That is why Layer 1 is only the DEFAULT board, never the answer.** A workspace that
targets a different board sets it in that repo's `workflow.json` → `board`, which wins.
Resolution order, every run:

| Order | Source | Use when |
|---|---|---|
| 1 | `workflow.json` → `board` (§ Layer 2) | this repo names its own board — **always wins** |
| 2 | `${user_config.board_number}` / `${user_config.board_owner}` | no repo-level board; the machine default |
| 3 | neither is set | **no board** — label-only, see below |

**Resolve it once at the top of a run, then substitute the resulting NUMBERS into every
later command.** 🚨 **Do not try to carry it in a shell variable.** Each command runs in
a fresh shell, so `$BOARD` set in one block is empty in the next — and an empty board
number reads downstream exactly like "this repo has no board", which is how a boarded
repo gets silently triaged label-only. `triage` § 1 shows the shape: literal
`<board_number>` / `<board_owner>` placeholders you fill in.

🚨 **Never write `${BOARD:-${user_config.board_number}}` or any other parameter expansion
around a `${user_config.*}` placeholder.** MEASURED: an **unset** option is substituted
as the *literal placeholder text*, and `${BOARD:-${user_config.board_number}}` is then a
**fatal `bad substitution`** in both zsh and bash — the block dies on its first line, on
exactly the "leave them blank" path the README documents as supported. Read the value,
then decide in prose; do not make the shell do the fallback.

**Step 1 — ask the repo, from its root.** A bare relative path is wrong in any cwd below
the root.

🚨 **`git rev-parse --show-toplevel` is NOT enough — in a worktree it returns the
WORKTREE**, and `.claude/` is commonly gitignored, so `workflow.json` lives only in the
main checkout and the override silently vanishes. MEASURED in a worktree of this repo:
`--show-toplevel` → the worktree (no file); `--git-common-dir` → the main checkout. That
is `autopilot`'s normal scheduled path, where an unattended run would then write to the
machine-default board with nobody to check with. Look in both, worktree first:

```sh
WT=$(git rev-parse --show-toplevel) || { echo "NOT A GIT REPO — no repo board"; exit 1; }
MAIN=$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)") # main checkout
WF=""
for D in "$WT" "$MAIN"; do
  [ -f "$D/.claude/workflow.json" ] && { WF="$D/.claude/workflow.json"; break; }
done
if [ -n "$WF" ]; then
  jq -r '"number=\(.board.number // "-")  owner=\(.board.owner // "-")"' "$WF"
  echo "src=$WF"
else
  echo "NO workflow.json in $WT or $MAIN"
fi
```

⚠️ **The `|| { … exit 1; }` is not decoration either.** Without it, both `git rev-parse`
calls fail, `WT` is empty and `dirname ""` is `.`, so the loop quietly tests
`./.claude/workflow.json` and **adopts a board from whatever directory you happen to be
in, at exit 0.** Measured: a stray file in a non-repo cwd yielded
`number=999  owner=WRONG-ORG`.

⚠️ **The `else` is not decoration — do not collapse this into a `for … done || echo`.**
`continue` exits 0, so such a loop always "succeeds" and the fallback becomes dead code:
the boardless case then prints **nothing at all**, which reads as a clean run rather than
an unanswered question. Measured while writing this.

In a normal checkout the two are identical and the loop reads it once.

**Step 2 — read the machine default too.** ⚠️ **This file is never substituted** — the
`${user_config.*}` placeholders in the table above reach you as literal text, so you
cannot read Layer 1 by quoting one. Ask the settings file:

```sh
jq -r '.pluginConfigs["gh-issue-flow@claude-workflows"].options
       | "default_number=\(.board_number // "-")  default_owner=\(.board_owner // "-")"' \
   ~/.claude/settings.json 2>/dev/null || echo "default_number=-  default_owner=-"
```

**Step 3 — combine the two, whole-key, and say which layer answered.** Match on step 1's
output first; only the last row needs step 2:

| Step 1 printed | Board is | Say |
|---|---|---|
| `number=42  owner=acme` | **42 / acme** | "board 42, from this repo's `workflow.json`" |
| `number=42  owner=-` (or the reverse) | **stop** | a half-written key is a config error, not a fallback — mixing a repo's number with a machine-default owner reads a board nobody configured |
| `NO workflow.json in …` | step 2's default, **unverified** | "no `workflow.json` here — using the machine default `<n>`; if this repo should have one, **stop and check before any board write**" |
| `number=-  owner=-` | step 2's default | "board `<n>`, the machine default — this repo names none" |
| …and step 2 also printed `-` | **none** | label-only (below) |

⚠️ **The provenance you report must name where the NUMBER came from, not merely that a
file existed.**⚠️ **The provenance you report must name where the NUMBER came from, not merely that a
file existed.** `setup` deliberately **omits** `board` when the repo uses the default, so
"file present, no board key" is the *common* shape — reporting it as "from
`workflow.json`" certifies the previous project's board as this repo's deliberate choice,
which is worse than saying nothing.

**Say which layer answered** whenever a board write is about to happen. Pointing a repo's
triage at the previous project's board is silent and expensive to undo.

**If BOTH are empty, skip every board step** and work from issue labels alone. Say so
once; do not fail.

⚠️ **An empty Layer 1 is not proof the user chose the label-only path.**
`claude plugin uninstall` empties `pluginConfigs` and the reinstall does not restore it,
so a board that was configured yesterday can be silently gone today. When you report the
boardless fallback, offer the way back rather than asserting a preference:

```sh
claude plugin install gh-issue-flow@claude-workflows \
  --config board_number=<n> --config board_owner=<owner>
```

Then **`/reload-plugins`** — a subprocess write does not reach this session's memoized
option values, so without it the very next resolution still reads empty.


---

## Layer 2 — `.claude/workflow.json` in the repo

The per-repo override. Read it from the repo root you are working in.

```json
{
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
  "trackForArea": { "area:backend": "Backend" },
  "agentReadyForbiddenPaths": ["terraform/**", "migrations/**"]
}
```

Every key is optional. Absent keys fall through to Layer 3.

Six of them carry weight the others do not:

- **`board`** names the Projects v2 board **this repo** feeds, and it **overrides**
  Layer 1. It is what lets one machine work several workspaces that target different
  boards — set it in every repo whose board is not your machine default, and the skills
  stop needing you to re-run the install between projects. `owner` is the board's owner,
  which is **not** necessarily the repo's (§ Owners are per-repo). Absent → Layer 1.
- **`repos`** is the repo list every multi-repo skill means by "every configured repo" —
  `triage`'s working set, `next-issue`'s theme sense, `work-summary`'s scope, and
  `autopilot`'s backpressure check all expand it. **Full `owner/repo`, never bare names**,
  because two repos on one board can sit under different owners. Absent → § Repo scope.
- **`dri`** maps each area label to the GitHub login that owns it, and it is what makes
  triage's **0-unassigned** guarantee possible — without it the integrity pass has no
  routing table and can only report the gap. Keep it beside `areaLabels`; an area with no
  DRI is the same failure as no area label.
- **`validate`** runs every time. **`validateWhenChanged`** maps a glob to a command run
  only when the diff touches it — keep slow or narrow gates here, not in `validate`.
- **`ciOnly`** names a required check you must **not** attempt locally, *with the reason*.
  A gate that needs a service, a secret, or a multi-GB download belongs here — running it
  and reading its failure as your own is the mistake this key exists to prevent.
- **`$comment*`** keys are for the human reading the file. Record **where a value came
  from and when** — every list in here is a snapshot of something that moves, and a
  transcribed file list or `paths-ignore` copy is the first thing to rot.

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
| `integrationBranch` | `origin/` + `defaultBranchRef.name`. ⚠️ Not always `main` — some repos integrate on `dev` and release from `main`. If the default branch looks like a release branch (a `dev`/`develop` branch exists and is ahead), **ask** rather than assume. |
| `validate` | `pyproject.toml`/`requirements.txt` → `pytest`, `ruff`. `package.json` → read its `scripts` block and run lint/typecheck/test/build that exist. `Cargo.toml` → `cargo test`, `cargo clippy`. Prefer copying the **CI workflow's** commands over inventing them. |
| `specFlow` | An `openspec/` directory at the repo root → `"openspec"`. Otherwise none. See [`../reference/openspec.md`](../reference/openspec.md). |
| `mergeMethod` | `squashMergeAllowed` / `rebaseMergeAllowed` from `gh repo view`. |
| `deployOnMerge` | Grep `.github/workflows/` for a workflow with `branches: [<integration>]` that deploys. **Do not assume a merge is inert.** |
| Required checks | `gh api repos/<owner>/<repo>/branches/<b>/protection` |

**Prefer copying from the CI workflow when it disagrees with anything else.** The
workflow is what actually gates the PR.

---

## Repo scope

`triage`, `next-issue`, `work-summary` and `autopilot` all operate over a **set** of
repos. Resolve that set in this order and **say which answered**:

1. `workflow.json` → `repos` — the explicit list, full `owner/repo`.
2. No `repos` key → **the repo you are in**, and only that one:
   `gh repo view --json nameWithOwner --jq .nameWithOwner`. This is the common case
   and it is correct — do not go looking for siblings to widen the scope.
3. The user named repos in the request → use exactly those, for this run only.

⚠️ **A repo in `repos` is not necessarily checked out, and its checkout is not
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
operation goes through `gh` and needs no working copy. Only commit-log reads do. Skip
those for that repo and **say you skipped them**, rather than silently reporting it as
a quiet day.

---

## Owners are per-repo, never one constant

🚨 **The board owner and a repo owner are not the same thing, and two repos feeding
one board may sit under different owners.** Never build `<owner>/<repo>` from a
single constant.

- Resolve each repo's owner from its own URL or `gh repo view --json nameWithOwner`.
- Strip owners with `sub(".*/";"")` when comparing repo names — never match a
  literal owner prefix. A transferred repo still HTTP-redirects, so a stale ref
  keeps working in `gh` while silently failing every owner-string match.
- **Issue numbers collide across repos.** A bare `#N` resolves same-repo; always
  write `owner/repo#N` when referring across.

---

## Board queries

**Fetch the board once per run, into a file. Every consumer reads that file.**

Use `board_fetch` from [`../reference/board-query.md`](../reference/board-query.md) — a
hand-written GraphQL query returning exactly what these skills read. ⚠️ **It is a shell
function in that file, not a binary** — paste both `board_gql` and `board_fetch` into the
shell (or `. ` a file you wrote them to) before calling it, or you get `command not
found`:

```sh
SCRATCH="${SCRATCH:-${TMPDIR:-/tmp}}"          # fresh shell: re-establish it
BOARD_JSON="$SCRATCH/board-<board_number>.json"  # <-- the NUMBER you resolved, written in
[ -s "$BOARD_JSON" ] || board_fetch "<board_owner>" "<board_number>" "$BOARD_JSON"
```

🚨 **Do not use `gh project item-list` for this.** MEASURED on the same 6-item board in
the same run: the CLI costs **102 GraphQL points**, `board_fetch` costs **3**. GraphQL
bills on what a query could return, and the CLI asks for a maximal board whatever yours
holds — `--limit 1000` and `--limit 100` both cost 102, `--limit 30` costs 31. There is no
flag to narrow it. For scale, `gh issue view --comments` cost 2 on that same run, and its
REST spelling cost 0.

`board_fetch` emits the same `{"items":[…]}` field names, so every `jq` pass below works
against either. It was verified identical to the CLI on every key these skills read.

🚨 **Still one board read per run.** Two steps that both need the board are two `jq`
passes over `$BOARD_JSON`, **never two fetches**. Cheap is not free — and the rule also
keeps the two steps agreeing with each other.

⚠️ **One exception: a read-back AFTER a write must re-fetch.** Verifying a mutation
landed against JSON pulled *before* the mutation proves nothing. Pull to a second path for
that — and read the eventual-consistency trap before trusting the result.

⚠️ **If you fall back to the CLI, `--limit 1000` is mandatory.** The default is 30 and
silently drops the newest cards on any board bigger than that — it can return only `Done`
rows and look like a legitimately empty queue. `board_fetch` paginates to the end on its
own and needs no equivalent.

Resolve field and option ids dynamically; **never hardcode them**:

```sh
gh project field-list "<board_number>" --owner "<board_owner>" --format json
```

⚠️ `gh api rate_limit` does **not** see the secondary limit that stops `gh project`.
A clean meter does not mean the call will work — believe the error. There is no REST
fallback for Projects v2.

⚠️ An issue's `projectItems` comes back **empty** for a repo in a different org from
the board. Reverse lookups must go through `gh project item-list`, not the issue.

---

## Things to resolve, never assume

- **The current user**: `gh api user --jq .login`. Never hardcode a login.
- **A test count**: never gate on one. It grows most weeks. Green-vs-red is the gate.
- **A field option id**: read it from `field-list` in the same run.
- **Whether a merge deploys**: read the workflow.
