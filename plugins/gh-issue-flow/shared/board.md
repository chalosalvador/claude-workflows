# The board: resolution and queries

Read this only when the run touches a Projects v2 board — `triage`, `next-issue`,
`autopilot`, and `setup` when it reports which board is in effect. `work-summary` never
needs it. The file-lookup step every skill runs, and the `number=` / `owner=` lines this
file interprets, are [`config.md`](config.md) § Resolving `workflow.json`.

---

## Resolution

**Layer 1 — the plugin's `userConfig`, one value per machine (config.md § Layer 1) — is
only the DEFAULT board, never the answer.** A workspace that
targets a different board sets it in that repo's `workflow.json` → `board`, which wins.
Resolution order, every run:

| Order | Source | Use when |
|---|---|---|
| 1 | `workflow.json` → `board` (§ Layer 2) | this repo names its own board — **always wins** |
| 2 | `${user_config.board_number}` / `${user_config.board_owner}` | no repo-level board; the machine default |
| 3 | neither is set | **no board** — label-only, see below |

**Resolve it once at the top of a run, then substitute the resulting NUMBERS into every
later command.** **Do not try to carry it in a shell variable.** Each command runs in
a fresh shell, so `$BOARD` set in one block is empty in the next — and an empty board
number reads downstream exactly like "this repo has no board", which is how a boarded
repo gets silently triaged label-only. `triage` § 1 shows the shape: literal
`<board_number>` / `<board_owner>` placeholders you fill in.

**Never write `${BOARD:-${user_config.board_number}}` or any other parameter expansion
around a `${user_config.*}` placeholder.** An **unset** option is substituted
as the *literal placeholder text*, and `${BOARD:-${user_config.board_number}}` is then a
**fatal `bad substitution`** in both zsh and bash — the block dies on its first line, on
exactly the "leave them blank" path the README documents as supported. Read the value,
then decide in prose; do not make the shell do the fallback.

**Read the machine default too.** **Nothing substitutes `${user_config.*}` into a
file** — those placeholders reach you as literal text, so you cannot read Layer 1 by
quoting one. Ask the settings file:

```sh
jq -r '.pluginConfigs["gh-issue-flow@claude-workflows"].options
       | "default_number=\(.board_number // "-")  default_owner=\(.board_owner // "-")"' \
   ~/.claude/settings.json 2>/dev/null || echo "default_number=-  default_owner=-"
```

**Combine the two, whole-key, and say which layer answered.** Match on the `number=` /
`owner=` line config.md's step 1 printed; only the last row needs the machine default:

| Step 1 printed | Board is | Say |
|---|---|---|
| `number=42  owner=acme` | **42 / acme** | "board 42, from this repo's `workflow.json`" |
| `number=42  owner=-` (or the reverse) | **stop** | a half-written key is a config error, not a fallback — mixing a repo's number with a machine-default owner reads a board nobody configured |
| `NO workflow.json in …` | the machine default, **unverified** | "no `workflow.json` here — using the machine default `<n>`; if this repo should have one, **stop and check before any board write**" |
| `number=-  owner=-` | the machine default | "board `<n>`, the machine default — this repo names none" |
| …and the machine default is `-` too | **none** | label-only (below) |

**The provenance you report must name where the NUMBER came from, not merely that a
file existed.** `setup` deliberately **omits** `board` when the repo uses the default, so
"file present, no board key" is the *common* shape — reporting it as "from
`workflow.json`" certifies the previous project's board as this repo's deliberate choice,
which is worse than saying nothing.

**Say which layer answered** whenever a board write is about to happen. Pointing a repo's
triage at the previous project's board is silent and expensive to undo.

**If BOTH are empty, skip every board step** and work from issue labels alone. Say so
once; do not fail.

**An empty Layer 1 is not proof the user chose the label-only path.**
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

## Board queries

**Fetch the board once per run, into a file. Every consumer reads that file.**

Use `board_fetch` from [`../reference/board-query.md`](../reference/board-query.md) — a
hand-written GraphQL query returning exactly what these skills read. **It is a shell
function in that file, not a binary** — paste both `board_gql` and `board_fetch` into the
shell (or `. ` a file you wrote them to) before calling it, or you get `command not
found`:

```sh
SCRATCH="${SCRATCH:-${TMPDIR:-/tmp}}"          # fresh shell: re-establish it
BOARD_JSON="$SCRATCH/board-<board_number>.json"  # <-- the NUMBER you resolved, written in
[ -s "$BOARD_JSON" ] || board_fetch "<board_owner>" "<board_number>" "$BOARD_JSON"
```

**Do not use `gh project item-list` for this.** It costs many times the GraphQL points
`board_fetch` does on the same board, and no CLI flag narrows it — the numbers, why, and
the proof that the two outputs agree on every key the skills read are in
[`../reference/board-query.md`](../reference/board-query.md).

**Still one board read per run.** Two steps that both need the board are two `jq`
passes over `$BOARD_JSON`, **never two fetches**. Cheap is not free — and the rule also
keeps the two steps agreeing with each other.

**One exception: a read-back AFTER a write must re-fetch.** Verifying a mutation
landed against JSON pulled *before* the mutation proves nothing. Pull to a second path for
that — and read the eventual-consistency trap before trusting the result.

**If you fall back to the CLI, `--limit 1000` is mandatory.** The default is 30 and
silently drops the newest cards on any board bigger than that — it can return only `Done`
rows and look like a legitimately empty queue. `board_fetch` paginates to the end on its
own and needs no equivalent.

Resolve field and option ids dynamically; **never hardcode them**:

```sh
gh project field-list "<board_number>" --owner "<board_owner>" --format json
```

`gh api rate_limit` does **not** see the secondary limit that stops `gh project`.
A clean meter does not mean the call will work — believe the error. There is no REST
fallback for Projects v2.

An issue's `projectItems` comes back **empty** for a repo in a different org from
the board. Reverse lookups must go through `gh project item-list`, not the issue.

---

