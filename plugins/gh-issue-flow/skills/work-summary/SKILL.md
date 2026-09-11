---
name: work-summary
description: >-
  Summarize what got done in a date window from git history, in plain language. Covers
  every configured repo (and, for a monorepo, each workstream), collapses squash-merged
  PR duplicates into one item per feature, groups by repo and day, and flags repos or
  days with no commits. Supports one-liner, short-paragraph, or day-grouped-bullet
  output, a fixed three-section standup draft (Yesterday / Today / Blockers, keyword-led
  bullets, derived blockers) — or renders a Slidev slide deck for a stakeholder update,
  from a bundled generic template and stylesheet. Use when asked "what was done today /
  yesterday / this week", for a daily standup draft or commit summary, a Friday rollup,
  "give me a one-liner of today's work", or a weekly-update deck / slides / status deck.
---

# Work summary

Turn a window of git commits into a short, honest, **plain-language** summary of what
got done.

Resolve repos and integration refs via [`shared/config.md`](../../shared/config.md).

## Workflow

```
- [ ] 1. Resolve the date window from the user's wording (default: today)
- [ ] 2. Resolve the repo scope (default: every configured repo)
- [ ] 3. Pull commits for the window across each repo (git -C <repo> …)
- [ ] 4. Collapse squash-merge duplicates → one item per feature/PR
- [ ] 5. Translate to plain language; group by repo; pick the output shape asked for
- [ ] 6. If a STANDUP was asked for: render the three-section shape (§ Standup) —
         and derive the Blockers section, which is not in the commit log
- [ ] 7. If a DECK was asked for: fill deck-template.md, copy the stylesheet, tell
         them how to preview (§ Deck)
```

## 1. Date window

Use **today's date from the environment**, never a remembered one.

| Wording | Window |
|---|---|
| "today" | just today |
| "yesterday" | just yesterday |
| "yesterday and today" | both, in **separate** sections |
| a named date | that day |
| "this week" / "Friday update" | since the previous Friday |
| "standup" | **two days**: the last working day *and* today, separate sections (§ Standup) |

**On a Monday, "the last working day" is Friday, not the empty Sunday.**

The window is a half-open day range: `--since` = `00:00` of the first day, `--until` =
`00:00` of the day **after** the last day, so the whole last day is included.

## 2. Repo scope

**Default: cover every repo in `workflow.json` → `repos`** and group the output by repo.
With no `repos` key that is **just the repo you are in**, which is the common case and a
complete answer — say so rather than implying a wider sweep happened. For a monorepo,
split by the paths in `workflow.json` → `workstreams`. Narrow only when the user names
one.

**Resolve each repo to a real checkout path before reading its log.** A workspace root
holding several repos is usually **not itself a git repo**, so `git -C <path>` is right
there — but `<path>` must be proven, not guessed from the repo name
([`shared/config.md`](../../shared/config.md) § Repo scope):

```sh
git rev-parse --show-toplevel                       # the repo you are in
git -C "<candidate>" rev-parse --show-toplevel      # prove a sibling before using it
```

**A configured repo with no checkout here is a gap to report, not a quiet day.** It has
no commits *to you*; that is not the same as no commits. List it under "not covered" with
the reason — this is the same failure as the stale-workstream-path one below, and it
reads identically in the output.

**A sibling's integration ref and workstreams come from ITS `workflow.json`, never this
one.** Run the resolution block from the sibling's checkout and take `integrationBranch`
and `workstreams` from what it prints. Judging a sibling's commits against this file's
`integrationBranch` — a branch the sibling may also have, but stale — reports merged work
as unmerged, with no error.

**Read the workstream paths from config, not from memory.** An app that was split or
renamed leaves the old path in every doc and half the skills; a stale path silently
reports zero commits for a live workstream.

**Cross-cutting commits.** One commit often touches several paths — a tooling or
design-system sweep can hit all of them — so it will appear under more than one
workstream. **Attribute it to the workstream it is *about* and mention it once**; don't
repeat it under every app it touched. The mirror case: a commit touching **no**
workstream path — a runbook under `documentation/`, a root config — is invisible to the
per-path pull. A day whose only work is such a commit reports every stream empty.
Always run the unscoped pull too, and attribute by what the commit is about.

## 3. Pull the commits

**Fetch first.** A local checkout is routinely dozens of commits behind, and a stale
checkout silently under-reports the day — which reads exactly like a quiet day.

### Resolve the identities BEFORE filtering

`--author` matches a regex against author name **and** email, so the email is the precise
key. **One `--author` is not enough, and the failure is silent.**

A squash merge rewrites the author to whichever identity is on the merging GitHub
account. Where that differs from the checkout's `git config user.email` — a personal
address on the GitHub account, a work address in the clone — filtering on
`git config user.email` alone returns the **un-merged branch commit and hides its merged
twin**. The work is then reported as still in flight on the very day it shipped, which is
the opposite of what happened.

Discover the window's identities first, then pass **every** one of yours as a repeated
`--author` flag; git ORs them:

```bash
# 1. Who committed in this window, under which identities?
git -C <repo> log --all --since="$START" --pretty=tformat:"%an <%ae>" \
  | sort | uniq -c | sort -rn

# 2. Filter on all of the ones that are yours
AUTHORS=(--author="you@work.example" --author="you@personal.example")
git -C <repo> log --all "${AUTHORS[@]}" \
  --since="$START" --until="$END_EXCL" --pretty=tformat:"%h|%ad|%s"
```

**Sanity check:** if a stream looks emptier than the window felt, or something you
know merged still reads as un-merged, re-run step 1 before writing it up. It is almost
always a second identity, not a quiet day.

Drop `--author` entirely when summarizing the **team's** work rather than your own, and
never for a standup ([`reference/standup.md`](../../reference/standup.md)).
Say which you did — "my commits" and "the team's commits" are different reports and the
difference is invisible in the output.

### The pull

```bash
git -C <repo> fetch --all

START="2026-06-11 00:00"; END_EXCL="2026-06-12 00:00"
AUTHORS=(--author="you@work.example" --author="you@personal.example")
INTEGRATION="<integrationBranch>"   # workflow.json -> integrationBranch, e.g. origin/main.
                                    # Set it HERE — a fresh shell has no value from an earlier block.

# Single-stream repo, read from the REMOTE integration ref:
git -C <repo> log "$INTEGRATION" "${AUTHORS[@]}" \
  --since="$START" --until="$END_EXCL" \
  --pretty=tformat:"%h|%ad|%s" --date=format:"%a %m-%d %H:%M"

# Monorepo, split by workstream:
for P in <workstream paths>; do
  echo "--- $P ---"
  git -C <repo> log "$INTEGRATION" "${AUTHORS[@]}" \
    --since="$START" --until="$END_EXCL" \
    --pretty=tformat:"%h|%ad|%s" --date=format:"%a %m-%d %H:%M" -- "$P"
done
```

**Read the REMOTE integration ref, not the local branch or `HEAD`.** A checkout parked
on someone's feature branch reports that branch's history as the team's day. This is the
single most common way a summary comes out wrong.

**One exception — a standup reads `--all`, not `$INTEGRATION`.** A standup answers
"what I worked on", not "what shipped", so work still sitting on an un-merged feature
branch has to appear or the day reads as half-empty. Substitute `--all` for
`"$INTEGRATION"` in both commands above, then establish merge status **per commit** rather
than trusting a branch name:

```bash
git -C <repo> merge-base --is-ancestor <sha> "<integrationBranch>"   # exit 0 = merged
```

Anything that is not an ancestor is un-merged and must be marked as such — see
§ Standup. Skipping this check is how a standup claims something shipped that is still
sitting on a branch.

**Use `--pretty=tformat:`, never `format:`, whenever the output is piped.** `format:`
omits the trailing newline on the final record, so `... | while read` never runs the loop
body for it and **silently drops the oldest commit in the window**, once per repo. It
fails plausibly — the list looks complete and is short by one real item. `tformat:`
terminates every line. Print a count alongside any list you build and reconcile it
against `git log … --oneline | wc -l` before writing anything up.

## 4. Collapse squash-merge duplicates

A squash merge re-lands the same work under a new hash and a PR-shaped subject, so the
feature commits and the merge commit both fall in the window. **One item per feature**,
not one per commit.

One feature typically leaves **three** kinds of commit in the window:

- the feature commit, carrying its PR number — `... (#N)`;
- its review-fix commits — `Address PR review …`, `fix(...): … (PR #N review)`;
- a **double-numbered** merge — `... (#N) (#M)` — where the squash of a branch that
  already had a number in its subject picks up the merge's number too.

Match on the PR number in the subject and on subject similarity, and prefer the **merge**
subject — it is the one written for a reader.

**Drop pure merge commits** (`Merge pull request …`) **and review-nit commits outright.**
Neither is its own deliverable, and a review-fix commit reported as a bullet is how a
day's list fills up with work nobody outside the PR needed to hear about.

## 5. Write it

**Plain language, no jargon, no commit hashes in prose.** The reader is deciding what to
ask about, not auditing the log.

Output shapes, chosen by what the user asked for:

- **One-liner** — a single sentence covering everything.
- **Short paragraph** — 2–4 sentences, grouped by theme not by repo.
- **Day-grouped bullets** — a heading per day, bullets under it, repo in bold.
- **Standup** — a fixed three-section shape (Yesterday / Today / Blockers). It has its
  own rules and they are not optional: see § Standup below.
- **Deck** — a Slidev presentation. See § Deck below.

**Skip any repo or workstream with no commits** — but if *everything* is empty, say so
plainly in one line rather than producing an empty scaffold. A quiet day should read
quiet.

## Honesty rules

These are what make the summary worth reading:

- **A commit is not a shipped feature.** Say "opened a PR for X" or "landed X behind a
  flag" when that is what happened. Verify against the code, not the commit subject.
- **A merged PR is not a deployed one** unless you have checked that merging deploys —
  see [`shared/execution.md`](../../shared/execution.md) § 7.
- **Never infer a status from a label.** Labels lag.
- **Per-person lanes and changed approaches are reported as
  [`reference/review-process.md`](../../reference/review-process.md) § Reporting findings
  and decisions says.**
- If you could not verify something, **say the summary is from commit subjects alone.**

---

## Standup

Triggered by "standup", or by a scheduled daily-update task. Everything above still runs
first: **the standup is a rendering of the commit pull, not a different investigation.**
Read it with `--all` and check merge status per commit (§ 3).

**Before writing one, read [`reference/standup.md`](../../reference/standup.md) in
full.** It owns the shape — Yesterday / Today / Blockers, always all three — the
heading derivation, the keyword-led bullets, the selection test that keeps it to
~6 bullets, the status markers, and how Blockers is derived read-only rather than
invented. This skill only decides *when* a standup is the output.

---

## Deck — a Slidev presentation

Triggered by "deck", "slides", "presentation", "status deck", "weekly update for
<stakeholder>". Everything above still runs first: **the deck is a rendering of the
summary, not a different investigation.** If the commits do not support a claim, the
slide does not get to make it.

### Audience

A deck has a **stakeholder** reader, not an engineer one. That changes the writing more
than the format does:

- **Translate to outcomes.** Not "migrated the job runner to a queue" — "batch imports no
  longer time out on large files".
- **No commit subjects, no hashes, no issue numbers** on a slide.
- **Say what is not done.** A deck that only lists wins is the one nobody believes the
  second time.

### Build it

1. **Fill the bundled template** into `slides/<name>.md`. It ships with the plugin, so
   read it by absolute path — from an installed copy the working tree is not on disk:

   ```sh
   cat "${CLAUDE_PLUGIN_ROOT}/skills/work-summary/deck-template.md"
   ```

   Sections:
   cover → at a glance → one slide per workstream that moved → roadmap → close.
2. **Copy the stylesheet** to `slides/style.css`:

   ```sh
   mkdir -p slides && cp "${CLAUDE_PLUGIN_ROOT}/skills/work-summary/assets/style.css" slides/style.css
   ```

   Slidev auto-loads `style.css` — **singular**. `styles.css` silently does not load,
   and the deck renders unstyled with no error.

   Do **not** overwrite an existing `slides/style.css` — it is probably already branded.
   Say it is there and leave it.

3. **Workstreams come from `workflow.json` → `workstreams`**, not from invention. One
   card and one slide per workstream that actually moved this period; **omit the ones
   that did not**. A card showing no progress reads as a stalled team rather than an
   unworked area.

4. **Tell the user how to see it**, with the commands in
   [`deck-template.md`](deck-template.md) § Preview and export.

### Rebranding

The stylesheet's first block is five CSS variables — accent, surface, ink, and two status
colours — with a light-mode swap documented beside them. **Point the user at that block**
rather than editing colours yourself; it is their brand, and one edit re-themes every
slide. The cover's `.brand-badge` holds a placeholder SVG to replace with their mark.

### Progress bars need a real denominator

`{{X of Y}}` is the part that makes a deck credible or hollow. Use a number you can
defend — screens wired of screens planned, endpoints migrated of endpoints total. **If
you cannot name the denominator, delete the bar** rather than inventing a percentage.
An invented number is the fastest way to lose a stakeholder's trust in the whole deck.
