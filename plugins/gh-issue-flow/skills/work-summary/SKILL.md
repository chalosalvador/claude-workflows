---
name: work-summary
description: >-
  Summarize what got done in a date window from git history, in plain language. Covers
  every configured repo (and, for a monorepo, each workstream), collapses squash-merged
  PR duplicates into one item per feature, groups by repo and day, and flags repos or
  days with no commits. Supports one-liner, short-paragraph, day-grouped-bullet, or
  standup output — or renders a Slidev slide deck for a stakeholder update, from a
  bundled generic template and stylesheet. Use when asked "what was done today /
  yesterday / this week", for a daily standup or commit summary, a Friday rollup, "give
  me a one-liner of today's work", or a weekly-update deck / slides / status deck.
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
- [ ] 6. If a DECK was asked for: fill deck-template.md, copy the stylesheet, tell
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
| "standup" | **two days**: the last working day *and* today, separate sections |

⚠️ **On a Monday, "the last working day" is Friday, not the empty Sunday.**

The window is a half-open day range: `--since` = `00:00` of the first day, `--until` =
`00:00` of the day **after** the last day, so the whole last day is included.

## 2. Repo scope

A workspace root holding several repos is usually **not itself a git repo** — always run
with `git -C <repo>`.

**Default: cover every configured repo** and group the output by repo. For a monorepo,
split by the paths in `workflow.json` → `workstreams`. Narrow only when the user names
one.

⚠️ **Read the workstream paths from config, not from memory.** An app that was split or
renamed leaves the old path in every doc and half the skills; a stale path silently
reports zero commits for a live workstream.

**Cross-cutting commits.** One commit often touches several paths — a tooling or
design-system sweep can hit all of them — so it will appear under more than one
workstream. **Attribute it to the workstream it is *about* and mention it once**; don't
repeat it under every app it touched.

## 3. Pull the commits

🚨 **Fetch first.** A local checkout is routinely dozens of commits behind, and a stale
checkout silently under-reports the day — which reads exactly like a quiet day.

```sh
git -C <repo> fetch --all

START="2026-06-11 00:00"; END_EXCL="2026-06-12 00:00"

# Single-stream repo, read from the REMOTE integration ref:
git -C <repo> log "$INTEGRATION" \
  --author="$(git -C <repo> config user.email)" \
  --since="$START" --until="$END_EXCL" \
  --pretty=tformat:"%h|%ad|%s" --date=format:"%a %m-%d %H:%M"

# Monorepo, split by workstream:
ME="$(git -C <repo> config user.email)"
for P in <workstream paths>; do
  echo "--- $P ---"
  git -C <repo> log "$INTEGRATION" --author="$ME" \
    --since="$START" --until="$END_EXCL" \
    --pretty=tformat:"%h|%ad|%s" --date=format:"%a %m-%d %H:%M" -- "$P"
done
```

🚨 **Read the REMOTE integration ref, not the local branch or `HEAD`.** A checkout parked
on someone's feature branch reports that branch's history as the team's day. This is the
single most common way a summary comes out wrong.

⚠️ Drop `--author` when summarizing the **team's** work rather than your own. Say which
you did — "my commits" and "the team's commits" are different reports and the difference
is invisible in the output.

## 4. Collapse squash-merge duplicates

A squash merge re-lands the same work under a new hash and a PR-shaped subject, so the
feature commits and the merge commit both fall in the window. **One item per feature**,
not one per commit.

Match on the PR number in the subject (`(#123)`) and on subject similarity, and prefer
the **merge** subject — it is the one written for a reader.

## 5. Write it

**Plain language, no jargon, no commit hashes in prose.** The reader is deciding what to
ask about, not auditing the log.

Output shapes, chosen by what the user asked for:

- **One-liner** — a single sentence covering everything.
- **Short paragraph** — 2–4 sentences, grouped by theme not by repo.
- **Day-grouped bullets** — a heading per day, bullets under it, repo in bold.
- **Standup** — last working day + today, separate sections, each 2–5 bullets, ending
  with anything blocked.
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
- ⚠️ **Report, don't accuse.** A zero or low lane for a person is usually **allocation**,
  not underperformance. Ask the lead before inferring, and make any target conditional.
- ⚠️ **Frame decisions, not retreats.** If an approach changed and the prior one was
  never actually deployed, write it as the decision it is — not as "instead of X".
- If you could not verify something, **say the summary is from commit subjects alone.**

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

1. **Fill [`deck-template.md`](deck-template.md)** into `slides/<name>.md`. Sections:
   cover → at a glance → one slide per workstream that moved → roadmap → close.
2. **Copy the stylesheet** to `slides/style.css`:

   ```sh
   mkdir -p slides && cp "${CLAUDE_PLUGIN_ROOT}/skills/work-summary/assets/style.css" slides/style.css
   ```

   ⚠️ Slidev auto-loads `style.css` — **singular**. `styles.css` silently does not load,
   and the deck renders unstyled with no error.

   Do **not** overwrite an existing `slides/style.css` — it is probably already branded.
   Say it is there and leave it.

3. **Workstreams come from `workflow.json` → `workstreams`**, not from invention. One
   card and one slide per workstream that actually moved this period; **omit the ones
   that did not**. A card showing no progress reads as a stalled team rather than an
   unworked area.

4. **Tell the user how to see it:**

   ```sh
   npx @slidev/cli slides/<name>.md --open
   ```

   The package is `@slidev/cli`, not `slidev`. Export to PDF with
   `npx @slidev/cli export slides/<name>.md` (needs `npx playwright install chromium`
   once).

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
