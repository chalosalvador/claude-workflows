# Resolving configuration

Every skill in this plugin needs facts that differ per person and per repo. **Never
hardcode them, and never guess silently** — resolve them in this order and say which
layer answered when it matters.

---

## Layer 1 — plugin `userConfig` (per person, prompted on enable)

| Placeholder | Meaning |
|---|---|
| `${user_config.board_number}` | GitHub Projects v2 board number, e.g. `11` |
| `${user_config.board_owner}` | Org or user that owns the board |
| `${user_config.status_in_progress}` | Status option name for work in flight |
| `${user_config.ready_label}` | Label marking an issue safe for unattended work |

⚠️ **Claude Code reads `pluginConfigs` only from user-level settings.** Project
`.claude/settings.json` entries are ignored for it. So `userConfig` can hold
per-person values and **cannot** hold anything that varies between repos.

**If `board_number` is empty, skip every board step** and work from issue labels
alone. Say so once; do not fail.

---

## Layer 2 — `.claude/workflow.json` in the repo

The per-repo override. Read it from the repo root you are working in.

```json
{
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
  "trackForArea": { "area:backend": "Backend" },
  "agentReadyForbiddenPaths": ["terraform/**", "migrations/**"]
}
```

Every key is optional. Absent keys fall through to Layer 3.

Three of them carry weight the others do not:

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

```sh
gh project item-list "${user_config.board_number}" \
  --owner "${user_config.board_owner}" --limit 1000 --format json
```

🚨 **`--limit 1000` is mandatory.** The default is 30 and silently drops the newest
cards on any board bigger than that — it can return only `Done` rows and look like a
legitimately empty queue.

Resolve field and option ids dynamically; **never hardcode them**:

```sh
gh project field-list "${user_config.board_number}" \
  --owner "${user_config.board_owner}" --format json
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
