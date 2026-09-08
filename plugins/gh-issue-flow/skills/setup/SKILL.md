---
name: setup
description: >-
  Bootstrap a repo for this workflow, or check an already-configured one. Probes the
  repo for its integration branch, validation gate, spec flow and merge method; writes
  .claude/workflow.json; creates the labels triage and autopilot depend on; and verifies
  the project board has the fields they read. Reports every gap it cannot close itself.
  Use for "set up the workflow here", "onboard this repo", "why isn't triage working",
  or as the first thing you run after installing this plugin — and "upgrade the config"
  / "bring workflow.json up to date" after a plugin update adds keys an existing repo
  does not have yet.
---

# Setup

Get a repo from nothing to the full workflow, or tell an already-configured repo what it
is missing.

Two modes, chosen from the user's wording:

- **Bootstrap** (default, or "set up", "onboard") — probe, write, create, report.
- **Check** ("check", "doctor", "why isn't X working", "what's missing") — probe and
  report only. **Changes nothing.** Run this first on a repo that already half-works.
  When `repos` names siblings whose checkouts resolve (§ Repo scope), check also diffs
  the board-level keys — `board`, `areaLabels`, `dri`, `trackForArea`, `priorityCaps`
  — across the files and reports any disagreement as a Missing row: two files feeding
  one board with two DRI maps route the same area to two people.
- **Upgrade** ("upgrade", "migrate the config", "bring workflow.json up to date", or the
  drift line any skill prints) — an existing file, a newer plugin: add only the keys the
  schema gained since the file was written. § 3 Upgrade mode.

**Never overwrite without asking.** If `.claude/workflow.json` already exists, show the
diff between it and what you would write, and let the user choose.

## Workflow

```
- [ ] 1. Preconditions — gh auth, repo, signing
- [ ] 2. Probe the repo (branch, gate, spec flow, merge method, protection)
- [ ] 3. Write .claude/workflow.json  (bootstrap only) — or add its missing keys (upgrade only)
- [ ] 4. Labels — create the ones the skills read  (bootstrap only)
- [ ] 5. Board — verify the fields exist; create what gh can  (bootstrap only)
- [ ] 5b. Stacks — name the stack(s), generate .claude/workflow/stacks/<name>.md from
         what § 2 probed, list every UNVERIFIED section  (bootstrap + upgrade)
- [ ] 6. Confirm the two agents loaded, and say what they are for
- [ ] 7. Report: what is configured, what is missing, what only a human can do
```

## 1. Preconditions

```sh
gh auth status                       # must be logged in, with project scope for board steps
git rev-parse --show-toplevel        # must be a git repo
git config --get commit.gpgsign      # the workflow signs every commit
```

If `gh auth status` lacks the `project` scope, board steps will fail with a
permissions error rather than an empty result:

```sh
gh auth refresh -s project,read:project
```

If `commit.gpgsign` is unset, say so — every skill here signs commits and stops on a
signing failure. That is a user decision, not something to configure for them.

## 2. Probe

Never assume. Read each of these:

```sh
gh repo view --json nameWithOwner,defaultBranchRef,squashMergeAllowed,rebaseMergeAllowed,mergeCommitAllowed,isEmpty
git branch -r --list 'origin/*'
```

🚨 **Handle the empty repo first.** A GitHub repo created but never pushed to reports
`isEmpty: true` and `defaultBranchRef.name` as an **empty string** — measured, not null,
so a truthiness check on the object still passes and you compose `origin/` + `""` =
`origin/`, a branch name that silently matches nothing downstream.

```sh
gh repo view --json isEmpty --jq '.isEmpty'   # true -> stop probing the branch
```

On an empty repo: say so, write no `integrationBranch`, and tell the user to push first
and re-run. Everything else in this skill still applies — labels and the board can be set
up before the first commit.

⚠️ **Glob defensively — the agent's shell is zsh, where an unmatched glob is an ERROR,
not an empty list.** `ls .github/workflows/*.yml` exits 1 with `no matches found` and
aborts a chained command, where bash would have passed the pattern through. Measured on a
repo with no CI. Test the directory first, or use `find`:

```sh
[ -d .github/workflows ] && find .github/workflows -name '*.yml' -o -name '*.yaml'
```

| Fact | How |
|---|---|
| `board` | **Ask which board THIS repo feeds**, and write `{"number": N, "owner": "<owner>"}` whenever it is not the user's machine default. This is what lets one machine work several workspaces against different boards — see [`shared/board.md`](../../shared/board.md) § Resolution for the resolution order. Omit the key when the repo uses the default; do not write a copy of it. 🚨 **Both sub-keys or neither** — a `board` with `number` and no `owner` does not fall back, it stops every board step in a repo you just green-lit. If the owner is unknown, ask; if you cannot get it, write no `board` key. |
| `repos` | The repo you are in (`gh repo view --json nameWithOwner`). **Ask whether other repos feed the same board** — if so, list them all, full `owner/repo`. One repo is the common answer and a perfectly good one; write the key anyway so the skills never have to guess. Listing a sibling widens the issue sweep only: its branch, gate and forbidden paths still come from **its** own file ([`shared/config.md`](../../shared/config.md) § Repo scope), so every repo keeps a file, and the board-level keys must agree across them. |
| `integrationBranch` | `origin/` + the default branch — **after** the empty-repo check above. ⚠️ **Not always `main`** — if a `dev`/`develop` remote branch exists and is ahead of the default, the repo probably integrates there and releases from the default. **Ask; do not guess.** |
| `validate` | **Read the CI workflow first** — `.github/workflows/*.yml`, the job that runs on PRs into the integration branch. Copy its step commands in order. Fall back to the toolchain only if there is no CI: `pyproject.toml`/`requirements.txt` → `ruff`/`pytest`; `package.json` → the lint/typecheck/test/build scripts that actually exist; `Cargo.toml` → `cargo clippy`/`cargo test`; `go.mod` → `go vet`/`go test ./...`. |
| `preflight` | Anything the gate shells out to that no lockfile installs. |
| `specFlow` | An `openspec/` directory at the repo root → `"openspec"`. |
| `mergeMethod` | From the `*MergeAllowed` flags. |
| `deployOnMerge` | Grep `.github/workflows/` for a workflow triggering on push to the integration branch that deploys. **Do not record "nothing happens" unless you looked.** Note that some hosts (Vercel, Netlify, Fly) deploy from the repo with no workflow at all — check for their config files too. |
| `requiredChecks`, `protection` | `gh api repos/<owner>/<repo>/branches/<b>/protection` — this 404s if the branch is unprotected, which is itself the answer. |
| `workstreams` | For a monorepo: the actual directories under `apps/`, `packages/`, `crates/`, etc. **Read the tree; never trust a README.** |
| `validateWhenChanged` | A CI job gated by a `paths:` filter — its command keyed by that glob. Omit when CI has no such job. |
| `ciOnly` | A required check that needs a service, secret or multi-GB download you cannot reproduce locally — its name, with the reason. Read the job's `services:` and `secrets.` uses. |
| `deployWorkflow` | The workflow file `deployOnMerge` was read from, so the next reader can re-derive it. While it is open, copy its `paths` / `paths-ignore` block verbatim — § 5b writes it into the stack doc § Deploy. |
| `trackForArea` | Each `area:*` label → the board's Track option of the same name, from `field-list` (§ 5). Only when the board has a Track field. |
| `agentReadyForbiddenPaths` | The infra, migration and workflow directories the deploy and protection probes found — the paths an unattended run must never touch. Record the migration directory and its apply command from the same read; § 5b writes those under the stack doc § Infra and migrations. |
| `priorityCaps` | Never probed. Written as the default `{"legal": "P1"}` with a `$comment_priorityCaps` saying what it does and that `{}` turns it off — so the rule triage applies is visible in the file rather than implied by its absence. |
| `schemaVersion` | Always the **Current schema** from [`shared/config.md`](../../shared/config.md) § Layer 2 → Schema. Never probed, never omitted. |

**Verify each probed command actually runs before writing it into the config.** A gate
entry that errors on first use is worse than an absent one — the next session reads its
failure as a broken repo. Run them; report any that fail.

## 3. Write `.claude/workflow.json`

Schema and key meanings: [`shared/config.md`](../../shared/config.md).

Write **only** what you probed. Leave a key out rather than guessing it — an absent key
falls through to Layer-3 probing, a wrong key is believed. ⚠️ **`board` is the exception
to "leave a key out": it is both sub-keys or no key at all**, never a half. See § 2.

Add `$comment` keys recording **where each value came from and when**. Every list in that
file is a snapshot of something that moves; the comment is what tells the next reader to
re-derive rather than trust.

**Always write `schemaVersion`** — the current schema from
[`shared/config.md`](../../shared/config.md) § Layer 2 → Schema. It is how every later
run knows whether this file has kept up with the plugin.

### Upgrade mode — an existing file, a newer plugin

`claude plugin update` refreshes the plugin's code and tells no repo that its
`workflow.json` is behind. This mode closes that gap, and the drift line every skill
prints ([`shared/config.md`](../../shared/config.md) § Resolving `workflow.json`, step 2) is what sends
you here.

```
- [ ] 1. Read the file. `.schemaVersion // 0` is where it stands; Current schema is
         where it should be. Equal → the keys are current: say so, skip to step 8.
- [ ] 2. From the schema table, take every key whose Since is greater than the file's
         version — PLUS any other key the file lacks that § 2 knows how to probe.
- [ ] 3. Probe each exactly as § 2 does. Show the proposed keys with their sources and
         ASK. A probe is a proposal, not a decision. `stacks` is the exception: § 5b
         both probes it and writes its files, so hand that key to § 5b.
- [ ] 4. Write ONLY the missing keys, each with a `$comment_<key>` naming the plugin
         version, the source and the date. Set `schemaVersion` to the current schema.
- [ ] 5. Re-run any formatter the repo applies to the file — a `$comment` usually says
         which — then show the diff. In `workflow.json` it must touch nothing but the
         added keys; the stack docs § 5b writes are separate files.
- [ ] 6. The file is usually tracked on a protected branch: branch, commit, open a PR.
         Never merge it.
- [ ] 7. Read it back: `jq .schemaVersion` equals the current schema and every proposed
         key is present.
- [ ] 8. Run § 4 and § 5b — always, even when step 1 found the keys current. § 4 creates
         any label the skills read that the repo lacks (idempotent: `gh label create`
         exits 1 on an existing name, tolerate it). MEASURED: a repo upgraded from a
         pre-0.5.2 setup was missing `legal`, `compliance` and `security`, which triage
         applies and reads, because upgrade ran only the key steps. § 5b adds a header
         the skeleton gained, or a doc for evidence that appeared since, and says
         "nothing to add" otherwise. Neither depends on a schema bump.
```

🚨 **Never touch an existing key** — not its value, not its formatting, not its comment.
A human wrote it, possibly to override exactly what the probe would have found. If a
probe disagrees with an existing value, **report** the disagreement in § 7; do not
resolve it.

**Check mode reports the same delta and writes nothing**: the drift line, then the keys
upgrade would add and what each probe found.

⚠️ **Check whether `.claude/` is gitignored** before declaring the file shared:

```sh
git check-ignore -v .claude/workflow.json .claude/workflow/stacks/probe.md   # the second path need not exist
```

Both paths, because the fix for one is not the fix for the other: the common
`.claude/*` + `!/.claude/workflow.json` pattern shares the config and still hides every
stack doc § 5b writes — the read-back passes, the file never reaches the PR, and every
teammate reads "no stack docs" as a normal state.

Read the `-v` output, not the exit code — `git check-ignore` exits 0 on **any** pattern
match, a negation included. Many repos blanket-ignore `.claude/*` with per-file
negations. If the new file is ignored, it is **local-only** and teammates get nothing:
tell the user the exact negation line to add, and that `.gitignore` is a tracked file
whose change may need a PR.

## 4. Labels

These are the labels the skills read. Create the missing ones; **never modify an existing
label's colour or description** — a repo's palette is a human's choice.

```sh
gh label create improvement     -d "Refactor, perf, DX, cleanup of something that works" -c 0E8A16
gh label create effort:easy     -d "One repo, obvious files, a pattern to mirror"        -c C2E0C6
gh label create effort:medium   -d "Multiple modules or a new pattern"                   -c FBCA04
gh label create effort:hard     -d "Cross-repo, migration, infra, or an open question"   -c D93F0B
gh label create triaged         -d "Deep-triage idempotency key"                         -c EDEDED
gh label create blocked         -d "Cannot proceed — see 'Blocked by: #n'"               -c B60205
gh label create epic            -d "Tracking issue with sub-issues"                      -c 5319E7
gh label create agent-ready     -d "Gated safe for unattended work"                      -c 1D76DB
gh label create agent-wip       -d "An unattended run has claimed this"                  -c 0052CC
gh label create agent-blocked   -d "Unattended run handed it back — a human decides"     -c B60205
gh label create agent-authored  -d "PR opened unattended"                                -c 1D76DB
gh label create legal           -d "Legal / policy / contractual — priority caps at P1"   -c 5319E7
gh label create compliance      -d "Needs a human owner — never agent-ready"              -c B60205
gh label create security        -d "Needs a human owner — never agent-ready"              -c B60205
```

A new GitHub repo ships with `bug`, `documentation`, `duplicate`, `enhancement`,
`good first issue`, `help wanted`, `invalid`, `question` and `wontfix` (verified) — so
four of the category labels already exist. Check before creating.

`gh label create` **exits 1 on an existing name** (measured) with
`label with name "x" already exists`. Tolerate that failure rather than passing
`--force`, which would overwrite a description someone wrote.

⚠️ **Do not pipe the loop into `head`/`tail`.** The pipeline's status becomes the pager's,
so every failure reads as success — and a label loop is exactly where that bites. Capture
the status separately, then **read the labels back** and report what actually exists:

```sh
gh label list --limit 200 --json name --jq '.[].name'
```

🚨 **Pass each label as its own argument, never a split shell variable.** The labels API
auto-creates any name it is handed, and under a shell that does not word-split, a
variable holding two names becomes one junk label created repo-wide. After any label
loop, assert that no label **this run created** contains a space. Not every label:
MEASURED, GitHub's own defaults `good first issue` and `help wanted` contain spaces, so a
blanket check false-alarms on every fresh repo and trains you to ignore it.

**Area labels are the user's taxonomy, not ours.** Ask what areas this repo has, create
`area:<name>` for each, and record them in `workflow.json` → `areaLabels` with a
one-line meaning, plus **`dri` mapping each area to the GitHub login that owns it**.
Triage routes assignees off that map; without it, the integrity pass cannot guarantee
"0 unassigned" and can only report the gap.

**On a solo repo, `dri` is every area mapped to the one person** — write it out rather
than leaving the key off. "There is only me" is a fact worth recording; an absent key
reads as "not configured yet" to every later run. Both keys are in
[`shared/config.md`](../../shared/config.md).

## 5. Board

The board is optional. **With no board, triage still does the label half and
`next-issue` still selects from `gh issue list` — say so and move on.**

```sh
gh project list --owner <owner>
gh project field-list <number> --owner <owner> --format json
```

| Field | Needed for | If missing |
|---|---|---|
| `Status` | every skill | Ships with a new board: Todo / In Progress / Done |
| `Priority` | triage §3c, autopilot ordering | `gh project field-create` (below) |
| `Track` | triage integrity pass | `gh project field-create`, options = the user's areas |

```sh
gh project field-create <number> --owner <owner> --name Priority \
  --data-type SINGLE_SELECT --single-select-options P0,P1,P2,P3

gh project field-create <number> --owner <owner> --name Track \
  --data-type SINGLE_SELECT --single-select-options "<their areas, comma-separated>"
```

To create a board from scratch: `gh project create --owner <owner> --title "<name>"`,
then `gh project link <number> --owner <owner> --repo <owner>/<repo>`.

### 🚨 The one thing you must NOT automate: adding a Status option

The workflow uses a **`Hold`** Status — "a human parked this by choice" — which a new
board does not have. `gh project` has no `field-edit`, and the GraphQL alternative
(`updateProjectV2Field` with `singleSelectOptions`) takes the **whole option list and
replaces it**. Running it would mint new option ids for Todo / In Progress / Done and
**unset the Status of every existing card**.

**Tell the user to add `Hold` in the board UI** (Settings → Status → add option). It is
one click and it is not worth the blast radius.

If `Hold` does not exist, the skills still work — `triage` simply has no parked state to
protect, and every card it sees is fair game for `next-issue`. Say that plainly rather
than implying the board is broken.

⚠️ **Never hardcode a field or option id** into `workflow.json` or anywhere else.
Resolve them from `field-list` in the same run that uses them.

## 5b. Stacks — the repo's own operational knowledge

Stack-specific knowledge lives in the repo, not the plugin: `.claude/workflow/stacks/<name>.md`,
one file per stack, named in `workflow.json` → `stacks`. What each section is for and
which skill reads it: [`shared/config.md`](../../shared/config.md) § Stack docs.

Runs in **bootstrap and upgrade**. Check reports what it would generate and writes
nothing.

```
- [ ] 1. Name the stack(s) from EVIDENCE — the table below. Never from a README.
- [ ] 2. Copy the skeleton:  cat "${CLAUDE_PLUGIN_ROOT}/skills/setup/stack-template.md"
         Its header needs the plugin version:  jq -r .version "${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json"
- [ ] 3. Fill each section from what § 2 already probed, plus the two probes this step
         owns (below). Every filled line carries its source path and today's date.
         Anything no probe answered stays `UNVERIFIED — fill in`. Nothing is invented.
- [ ] 4. Show the file and ASK. A stack name is a proposal; the user may rename it,
         split it in two, or drop it.
- [ ] 5. Write it, and write the names into `workflow.json` → `stacks` with a
         `$comment_stacks` — `[]` when the evidence named nothing. Read both back: every
         `##` header from the skeleton is present, exactly, and every name has a file.
- [ ] 6. List every UNVERIFIED section in § 7 Missing, with who can fill it.
```

**Naming.** A lowercase slug for the deploy target plus the infra tool, from what the
repo contains — several may apply, and each gets its own file:

| Evidence | Name |
|---|---|
| `vercel.json` or `.vercel/project.json` | `vercel` |
| `fly.toml` | `fly` |
| `netlify.toml` | `netlify` |
| `gcloud run deploy` or `google-github-actions/*` in a workflow | `gcp-cloud-run` |
| `aws ecs` / `aws-actions/*` in a workflow, or `serverless.yml` | `aws` |
| `kubectl` / `helm` in a workflow, or a `k8s/` dir | `kubernetes` |
| `*.tf` or `terraform/` | `terraform`, prefixed by the provider the `.tf` names: `gcp-terraform`, `aws-terraform` |
| a `Dockerfile` alone | not a stack — it says nothing about where it runs |

Read the workflow lines, not just the file names: a `Dockerfile` plus a workflow that
runs `gcloud run deploy` is `gcp-cloud-run`. When the evidence names nothing, **write no
stack doc and say so** — the generic reference docs still apply, and an invented stack
is worse than none.

**Filling from § 2, and the two probes this step owns.** `deployOnMerge` and
`deployWorkflow` go under Deploy, with the `paths` / `paths-ignore` block § 2 copied
from that workflow; the migration directory and apply command § 2 recorded beside
`agentReadyForbiddenPaths` go under Infra. **The forbidden paths themselves are not
copied** — `workflow.json` owns that list and the stack doc points at it, so there is
one list to rot. Two things § 2 does not probe, so this step does:

```sh
grep -rn 'secrets\.\|env add\|secrets versions add\|--data-file=-' .github/workflows scripts 2>/dev/null   # Secrets and env
grep -rln 'terraform apply\|alembic\|migrate\|prisma\|drizzle-kit' .github/workflows scripts Makefile 2>/dev/null   # Infra apply commands
```

What those find goes in as PROBED lines with the path; the read-back that proves a
value landed stays `UNVERIFIED`, because no probe can know it.

**Review bot.** Detect, do not assume — and read **both** places a bot writes, because
they differ per bot. MEASURED on a public repo: the comment endpoints returned only two
CI bots while `pulls/<n>/reviews` returned the review bot on every recent PR; a scan of
comments alone would have written "no review bot" for a repo that has one.

```sh
# Who actually reviews. Seven REST calls; the check names are already in workflow.json -> requiredChecks (§ 2), do not re-fetch protection.
{ gh api "repos/<owner>/<repo>/issues/comments?sort=created&direction=desc&per_page=100" --jq '.[].user.login'
  gh pr list --repo <owner>/<repo> --state merged --limit 5 --json number --jq '.[].number' \
    | while read n; do gh api "repos/<owner>/<repo>/pulls/$n/reviews" --jq '.[].user.login'; done
} | grep '\[bot\]$' | sort | uniq -c | grep . \
  || echo "NO bot in the last 100 comments or the last 5 merged PRs' reviews -> Bot: none"
# MEASURED on a repo with no bot: without the final `grep . || echo`, this printed nothing at
# all — the same silent-empty result the rest of this plugin exists to prevent.
# A config file only ANNOTATES. If it names a bot the scan did not see, the file is stale: report it, do not write it as the bot.
ls .coderabbit.yaml .coderabbit.yml 2>/dev/null
```

Write the login and where it came from. Then, **in this same run, derive the two
patterns from the bot's own comments**: open the newest review it posted and the newest
acknowledgement (the short one with no findings), quote a phrase from each that the
other does not contain, and write both lines as PROBED with the two comment URLs as the
source. Show the user the two comments beside the two patterns — a pattern is a
proposal. Only when the bot has fewer than two comments to read do the lines stay
`UNVERIFIED`, and that is a Missing row: the babysit loop cannot tell an ack from a
review without them.

**Upgrade on a repo that already has stack docs**: add any `##` header the skeleton has
and the file lacks, with its body `UNVERIFIED`; generate a doc for evidence that has
appeared since (a new `fly.toml`, say) and add its name to `stacks`; say "nothing to
add" when neither applies. **Never touch a filled section**, and never rename a file — a
human chose that name.

## 6. Confirm the agents

Two subagents carry the workflow's quality, and a user who does not know they exist never
notices when they silently are not running.

| Agent | Runs at | Used by | Returns |
|---|---|---|---|
| `issue-planner` | `effort: max`, read-only | `next-issue`, `autopilot` | The scoping plan — and **REVIEW LENSES**, which decides the next step |
| `diff-reviewer` | `effort: max`, read-only | `next-issue`, `autopilot` | Findings through one lens: `correctness`, `contract`, `scoping`, `safety`, `tests`, `deploy` |

**Check, do not warn.** A same-named agent in `~/.claude/agents/` or the project's
`.claude/agents/` wins over the plugin's copy, with no error and a plausible result.
MEASURED: five runs were spent tuning a plugin file nothing read; the story is in
`CONTRIBUTING.md` § Testing a change to an agent, and the reason it is a check here is that
a prose warning in this skill was ignored.

```sh
claude plugin list          # "No plugins installed" -> every skill here is inert
ls ~/.claude/agents/ .claude/agents/ 2>/dev/null
```

For each of `issue-planner` and `diff-reviewer`, report explicitly:

| Finding | What it means |
|---|---|
| plugin not installed | **Stop.** Every skill here is inert. Install it, or run `claude --plugin-dir <path>`. |
| same-named file in `~/.claude/agents/` | That file runs. The plugin's copy is dead. |
| same-named file in `.claude/agents/` | Same, and it also shadows the user-level one. |
| neither | The plugin's agents are live. |

If a shadow exists, name the file that will execute, by absolute path, and change
nothing — it may be deliberate; the user decides. Every skill here spawns the namespaced
`gh-issue-flow:<agent>`, which always resolves to the plugin's copy; a bare name resolves
to whichever wins.

🚨 **Agent types resolve at session start.** Measured: an edit or an install changes
nothing for the running session, and the spawn fails with `Agent type '<name>' not
found`. Restart to test an agent change; `/reload-plugins` refreshes skills only.

Tell the user once: the agents pin `effort: max` regardless of the session's setting
(implementation does not — a skill cannot pin the main loop), and a subagent cannot fan
out, so `gh-issue-flow:diff-reviewer` is spawned N times from the parent in one message,
one per lens.

## 7. Report

Print three blocks, in this order:

**Configured** — what was probed and written, each with where it came from:

| Setting | Value | Source |
|---|---|---|
| integrationBranch | `origin/dev` | `gh repo view` default branch |
| validate | 3 commands | `.github/workflows/ci.yml` job `test` |
| schemaVersion | 2 | current schema, `shared/config.md` § Layer 2 |
| stacks | `gcp-cloud-run`, `gcp-terraform` | `.github/workflows/deploy.yml`, `terraform/` (provider `google`) |

**Created** — labels and board fields, with anything skipped because it already existed.

**Missing — and who can fix it.** The honest half. Separate what a human must do from
what is merely absent.

🚨 **An unset board is a narrowing, not a Missing row.** Resolve both layers first
([`shared/board.md`](../../shared/board.md) § Resolution): `workflow.json` → `board` wins,
the machine default is second, and only when both are empty is the repo label-only. Say
which layer answered, every run — pointing a repo's triage at the previous project's
board is silent and expensive to undo. When neither is set, say *"no board is configured
— if that is deliberate, nothing is wrong; if you expected one, here is how to restore
it"* and give the way back from `board.md` § Resolution: the `--config` command **and** the
`/reload-plugins` after it, without which the next skill still resolves empty. You cannot
tell a deliberate blank from one `claude plugin uninstall` wiped, so never assert it was
a choice. The install's "N options not yet set" count is the same shape: not a gap you
can close.

| Gap | Effect | Fix |
|---|---|---|
| No `Hold` Status option | No parked state; every Todo card is pickable | Board UI, one click |
| `workflow.json` behind the schema | Keys the plugin gained are unknown here; skills run on defaults | `/gh-issue-flow:setup upgrade` |
| `stacks/<name>.md` § Review bot patterns UNVERIFIED | The babysit loop cannot tell an ack from a review | The bot had fewer than two comments to read; re-run § 5b after its next review, or a human writes the two patterns |
| `stacks/<name>.md` § Reviewer invariants UNVERIFIED | The `safety` lens has nothing stack-specific to check | The person who owns the data model writes one line per invariant |
| `.claude/` is gitignored | Config and stack docs are local-only; teammates get nothing | Add `!/.claude/workflow.json` and `!/.claude/workflow/`, needs a PR |
| No area labels yet | Triage cannot route assignees | Tell me your areas and I will create them |
| Branch unprotected | Nothing blocks a red merge | Repo settings — a deliberate choice |
| `commit.gpgsign` unset | Skills stop on a signing failure | `git config commit.gpgsign true` |

Close with the **one next command** the user should run — usually
`/gh-issue-flow:triage dry run` — and a one-line map of what follows it:
`triage` gates issues → `next-issue` or `autopilot` works them → `work-summary` reports.

⚠️ **Read back anything you created before claiming it.** `gh` exits 0 on writes the
server rejected, so a report listing labels or fields you never actually made is the
exact failure this skill exists to prevent. Re-list and count.

🚨 **But board writes are eventually consistent — labels are not.** A label read-back is
immediate and trustworthy. A Projects v2 read-back is **not**: measured, an `item-list`
immediately after adding items reported 0 while every add had in fact succeeded, settling
~30s later. Poll with backoff before concluding a board write failed, and prefer
resolving a returned item id over counting. See
[`../../reference/verification.md`](../../reference/verification.md).

## What this cannot give you

Say these plainly rather than letting the user discover them:

- **Issue hygiene.** Triage's guarantees are about *routing*, not content. Issues with
  no acceptance criteria stay un-`agent-ready` forever, and that is correct.
- **A green gate.** If the repo's suite is red on the integration branch, "any red is
  yours" stops being true and every skill's validation step degrades. Fix the base first.
- **Review bots.** The babysit loop watches whatever checks and review threads exist. It
  does not install a bot for you, and with none configured the review half of the loop
  has nothing to watch.
