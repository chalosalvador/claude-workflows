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

⚠️ **Sanity check:** if a stream looks emptier than the window felt, or something you
know merged still reads as un-merged, re-run step 1 before writing it up. It is almost
always a second identity, not a quiet day.

⚠️ Drop `--author` entirely when summarizing the **team's** work rather than your own.
Say which you did — "my commits" and "the team's commits" are different reports and the
difference is invisible in the output.

### The pull

```bash
git -C <repo> fetch --all

START="2026-06-11 00:00"; END_EXCL="2026-06-12 00:00"
AUTHORS=(--author="you@work.example" --author="you@personal.example")

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

🚨 **Read the REMOTE integration ref, not the local branch or `HEAD`.** A checkout parked
on someone's feature branch reports that branch's history as the team's day. This is the
single most common way a summary comes out wrong.

🚨 **One exception — a standup reads `--all`, not `$INTEGRATION`.** A standup answers
"what I worked on", not "what shipped", so work still sitting on an un-merged feature
branch has to appear or the day reads as half-empty. Substitute `--all` for
`"$INTEGRATION"` in both commands above, then establish merge status **per commit** rather
than trusting a branch name:

```bash
git -C <repo> merge-base --is-ancestor <sha> "$INTEGRATION"   # exit 0 = merged
```

Anything that is not an ancestor is un-merged and must be marked as such — see
§ Standup. Skipping this check is how a standup claims something shipped that is still
sitting on a branch.

🚨 **Use `--pretty=tformat:`, never `format:`, whenever the output is piped.** `format:`
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

- the feature commit, carrying its PR number — `... (#6)`;
- its review-fix commits — `Address PR review …`, `fix(...): … (PR #34 review)`;
- a **double-numbered** merge — `... (#6) (#70)` — where the squash of a branch that
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
- ⚠️ **Report, don't accuse.** A zero or low lane for a person is usually **allocation**,
  not underperformance. Ask the lead before inferring, and make any target conditional.
- ⚠️ **Frame decisions, not retreats.** If an approach changed and the prior one was
  never actually deployed, write it as the decision it is — not as "instead of X".
- If you could not verify something, **say the summary is from commit subjects alone.**

---

## Standup — the three-section shape

Triggered by "standup", or by a scheduled daily-update task. Everything above still runs
first: **the standup is a rendering of the commit pull, not a different investigation.**
Read it with `--all` and check merge status per commit (§ 3).

🚨 **A standup is YOUR work, and only yours.** Keep the `--author` filter on, with every
one of your identities (§ 3). This is the one output shape where dropping it is always
wrong: you are reporting to the team, so a teammate's work in your update is at best noise
and at worst you appearing to claim it. Never add a "Team:" bullet, never name what someone
else landed — even when the commit pull surfaced it, and even when it is the most
interesting thing in the window. If the user explicitly wants everyone's work, that is a
different report and not this shape.

> *Standup — {Ddd DD Mon}*
>
> *Yesterday*
> _{Workstream}_
> - *{Keyword}* — {one small outcome}
>
> *Today*
> _{Workstream}_
> - *{Keyword}* — {one small outcome} (in progress)
>
> *Blockers*
> - None.

**Three sections, in this order, always all three present.** A day-part with no work gets
one honest line (`- Nothing committed.`) rather than being dropped — the three-beat shape
is what the reader scans for, and a missing section reads as an oversight. Blockers is
the one section that may legitimately say `- None.`

### Headings

**Two levels, and they must look different.** The markup above is Slack's, which has no
real heading levels — this is the entire hierarchy:

- Day sections are **bold**: `*Yesterday*`, `*Today*`, `*Blockers*`.
- Stream headings nested under them are **italic**: `_{Workstream}_`.

Bold for both flattens it and the reader loses the day boundary.

Stream headings are the **bare stream name** and nothing else. Never append a status — no
"— live", no "— on staging", no "(prod)". Streams repeat under Yesterday and Today as
needed; omit any stream with no work in *that* section.

⚠️ **Derive the heading from `workflow.json` → `workstreams`; do not paste the value in.**
Those values are descriptions written for a human reading the config, so they carry a
descriptive tail a heading must not: `"Scholar App — teacher workspace (Next.js)"` is the
config value, `_Scholar_` is the heading. Three rules cover every case:

- **Cut at the first `—`, `(` or `,`**, then drop a redundant trailing noun
  (`Scholar App` → `Scholar`). Two or three words at most.
- **Entries sharing a prefix collapse into one heading.** `packages/db`,
  `packages/models` and `packages/shared` are all `Shared — …`; they are one
  `_Shared / repo-wide_` stream, not three.
- **A single-stream repo has no `workstreams` key at all.** Use the repo's own short
  name — `brightfold-gateway` → `_Gateway_`.

Keep the derived names **stable across runs**. The reader scans for the same heading every
day, and a stream that is `_Scholar_` on Monday and `_Scholar App_` on Tuesday reads as two
different things. If a repo needs names that this derivation does not produce, pin them
where the repo's other local conventions live rather than re-deriving differently each
run.

### Which day is "Yesterday"

The **last working day**, not literally yesterday.

**Label it `*Yesterday*` whenever that is what it is** — which is most days. Only when the
last working day is *not* the previous calendar day do you name the day instead: on a
Monday the section is `*Friday*`, because that is when the work happened.

⚠️ Never label it with a date — `*Tuesday 1 Sep*` is wrong even when the date is right. The
reader wants the relationship to today, and the date is already in the header line.

A Monday standup with an empty Yesterday because Sunday was empty is a formatting bug, not
an honest report.

⚠️ **Never reach back more than one working day to fill it.** If the last working day was
genuinely quiet, say so.

⚠️ **Re-derive Yesterday from git every run — never paste the previous draft forward.**
Merge status is evaluated **as of now**, not as of yesterday: something tagged
`(in progress)` yesterday that merged this morning carries no marker today. Pasting
forward is how a shipped thing keeps being reported as open.

**One outcome appears once per draft.** Work spanning both days goes under the day it
*concluded* — normally Today — never in both. Two near-identical bullets a section apart
is the most common way this shape goes wrong.

**Yesterday is a recap, Today is the full list.** The team already heard yesterday's items
in yesterday's standup, so Yesterday is a short reminder: **2–3 bullets**. A thread still
running belongs in Today, where its current state is. What earns a Yesterday bullet is
work that *concluded* and that someone else still needs to know about, plus anything that
has since become a blocker.

### Bullets

**Every bullet leads with a bold keyword**, then an em dash, then the outcome:

> `- *Stuck queue* — fixed a flaw where one malformed message could freeze every new
> record for that customer.`

Rules for the keyword:

- **Name the subject, not the verdict.** `*Tooling drift*`, `*Missing deploy path*` — not
  `*Fixed*`, `*Improved*`, `*Done*`.
- **1–3 plain words.** No jargon in the keyword either: `*Passwordless database*`, not
  `*IAM auth*`.
- **Unique across the whole draft**, Yesterday and Today included. The same keyword twice
  means either they should have been one bullet, or one label is lazy.
- The keyword replaces nothing — the sentence after the dash still stands on its own.
- `(in progress)` goes at the **end of the sentence**, never in the keyword.

**One idea per bullet, one line each.** Split compound bullets. "Made merging safer:
queued merges, named reviewers, and an automatic contract check" is three bullets, not
one. Short beats complete-in-one-sentence.

**Lead with the consequence, not the mechanism.** Read the actual diff and commit body,
not just the subject line — the subject is usually the mechanism. Say what would have
broken and for whom.

**No PR numbers, file names, or jargon** in any Yesterday or Today bullet. (One carve-out,
in Blockers below.) "Jargon" is stricter here than elsewhere in this skill — the standup
reader is often non-technical, and these are the four kinds that leak in:

| Don't write | Write |
|---|---|
| an internal path or service — `/ai-proxy`, `apps/admin` | what it does for someone — "the teacher app" |
| a protocol or vendor — OIDC, SSE, CMEK, Terraform | the effect — "proves its identity", "the live activity stream" |
| a config value — `district_ids = []` | the state in words — "no customer is switched on yet" |
| a repo or branch name | the stream heading already says where |

The test: **would someone outside engineering know what changed for them?** If the sentence
only makes sense to someone who has read the diff, it is not finished.

### Selection — this is the part that goes wrong

**~4–6 bullets in Today, 2–3 in Yesterday, no more than ~3 per stream.**

🚨 **This is a selection problem, not an ordering one.** Taking the top N of a ranked
list of everything you did still leaves a list of everything you did, just shorter. Ask of
each candidate: **"who else needs to know this, and what would they do differently?"** If
the answer is nobody, it does not go in — however hard the work was, or however dramatic
the near-miss.

**Earns a bullet:**

- something a user or admin can now see or do that they could not before;
- something another person's work depends on — a contract change, a cutover, a shared
  environment moving;
- a risk that was live and is now closed, stated **once**, at thread level;
- something the team must act on or decide.

**Does not earn one**, however much of the day it took: internal housekeeping,
documentation moves, guard and test hardening, review-fix churn, tooling and process
changes nobody else feels.

**One thread, one bullet.** A multi-PR or multi-day piece of work — a service split, a
migration, an epic — gets a *single* bullet naming where the thread now stands. Never one
per PR, never one per near-miss found along the way. Several bullets in a row that all
begin "closed a gap where…" inside one workstream is that thread leaking into the list;
collapse them and say what shipped and what is left.

If cutting hurts, the cut item is usually a *detail of* a bullet you are already keeping —
fold it in as a clause, or drop it.

### Status markers

The heading cannot carry status, so the bullet does — minimally:

- **Merged to its integration branch → no marker at all.** And no "live", "in production"
  or "deployed" in the bullet text either: state the outcome and stop. Silence is honest;
  a production claim for work merged to a staging integration branch is not.
- **Still on an un-merged branch → `(in progress)`.** This is the only status marker
  allowed.
- Establish which per commit with `merge-base --is-ancestor` (§ 3), never from the branch
  name.

### Blockers

**`- None.` is the expected answer most days, and it is the right one.** The never-empty
rule governs *work*, not blockers. An invented blocker sends someone chasing a problem
that does not exist, and costs the section its credibility for the day there genuinely is
one. **Never pad it.**

A blocker is **something another person or system must clear** before the work can move.
Derive it cheaply and read-only from:

- your open PRs awaiting review, or red on a check you cannot fix yourself —
  `gh pr list --author @me --state open` per repo, then read the checks;
- open issues assigned to you carrying a `blocked` label and/or a `Blocked by: #N` marker
  in the body — name the **blocking** issue;
- anything the window's work surfaced that needs someone else's access, approval,
  credential, or decision, or a cross-repo dependency (a wire change on one side that the
  other cannot consume until it merges).

Two traps, both of which manufacture false blockers:

- ⚠️ **A board status meaning parked-by-choice (e.g. `Hold`) is not a blocker.** Parked is
  a decision; the `blocked` label is stuck. Reporting a parked card asks the team to
  unstick something nobody is stuck on.
- ⚠️ **Your own unfinished work is not a blocker.** "Still need to finish the tests" is a
  Today bullet tagged `(in progress)`.

**The one place a number belongs.** The no-numbers rule holds everywhere else, but a
blocker parked on another ticket is not actionable without it — write the plain-language
reason *and* the number (`waiting on #21`). The blocking issue only; still no PR numbers
or file names. Across repos, write `owner/repo#N`.

Name the blocker in the same consequence-first voice as the bullets, and say **who or what
would clear it** — that is the only reason the line exists.

⚠️ **Not a roll-call.** "Six PRs open for review, oldest first: …" is a list, not a blocker
section: it names no consequence, asks for nothing specific, and buries the one item that
actually needs a person. Blockers get the same selection test and the same one-per-thread
collapse as every other bullet — several issues stuck behind one unmade decision are **one**
blocker naming the decision, not one line each.

⚠️ If the read-only lookups fail or are unavailable, write `- None.` and say the lookup
failed **outside** the pasteable text. Never guess a blocker.

### A complete example

A full day's output. **This is the length** — the rules above describe it, this shows it.

> *Standup — Wed 02 Sep*
>
> *Yesterday*
> _Checkout_
> - *Card retries* — a failed payment now retries on its own instead of dropping the order.
>
> _Admin console_
> - *Refund history* — support can see every refund on an account without asking engineering.
>
> *Today*
> _Checkout_
> - *Guest orders* — people can buy without making an account. Not switched on for any store yet.
> - *Duplicate charges* — closed a gap where a slow network could bill the same card twice.
>
> _Admin console_
> - *Bulk export* — admins can pull a month of orders as a file (in progress).
>
> *Blockers*
> - *Tax rates review* — the new tax table has been ready and unreviewed since Monday; someone on the team needs to look at it before it can merge.

Six bullets total. Every one is a single line, leads with a bold keyword naming a subject,
and says what a person can now do. No numbers, no service names, no repo names.

**What the same day also contained, and why none of it is above:** a CI cache fix, a
dependency bump, three review-fix commits on the guest-orders PR, a docs move, and a
required-check rename. That is most of the commits and none of the bullets — the pull
surfaced them and the selection test dropped them.

Note also what the example does *not* do: no "Team:" line, though two teammates landed work
in the same window; no "live in production" on the merged items; and one bullet carries
`(in progress)` because that branch is not an ancestor of the integration ref.

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
