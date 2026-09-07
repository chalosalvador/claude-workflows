# The standup shape

Owned here so the skill that renders it stays short. `work-summary` § Standup decides
*when* a standup is the output and links here; every rule about *what it looks like* is
below, and there is no second copy.

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
descriptive tail a heading must not: `"Checkout App — buyer-facing storefront (Next.js)"` is
the config value, `_Checkout_` is the heading. Three rules cover every case:

- **Cut at the first `—`, `(` or `,`**, then drop a redundant trailing noun
  (`Checkout App` → `Checkout`). Two or three words at most.
- **Entries sharing a prefix collapse into one heading.** `packages/db`,
  `packages/models` and `packages/shared` are all `Shared — …`; they are one
  `_Shared / repo-wide_` stream, not three.
- **A single-stream repo has no `workstreams` key at all.** Use the repo's own short
  name — `acme-gateway` → `_Gateway_`.

Keep the derived names **stable across runs**. The reader scans for the same heading every
day, and a stream that is `_Checkout_` on Monday and `_Checkout App_` on Tuesday reads as two
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
| an internal path or service — `/payments-proxy`, `apps/admin` | what it does for someone — "the admin console" |
| a protocol or vendor — OIDC, SSE, KMS, Terraform | the effect — "proves its identity", "the live activity stream" |
| a config value — `enabled_tenants = []` | the state in words — "no customer is switched on yet" |
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
