---
name: triage
description: >-
  Daily triage of GitHub issues across one or more repos. An UNCAPPED integrity pass
  guarantees a clean board — every open issue on the project board, area-labeled,
  assigned to its DRI, with a Track and Status (0 off-project, 0 unassigned). Then a
  capped deep pass categorizes (Bug/Feature/Improvement/Question), sizes effort, sets
  priority, flags duplicates, and marks safe-and-easy ones agent-ready for the
  autopilot skill. Writes verdicts to GitHub, then prints a receipt. Use for "triage
  the issues", "clean up the board", "board health", a daily triage routine, or before
  planning the week.
---

# Issue triage

Keep the board **clean, healthy, and honest** every day, and hand the safe work off to
the [`autopilot`](../autopilot/SKILL.md) skill.

Resolve the board, repos and labels via
[`shared/config.md`](../../shared/config.md) **before anything else**. With no board
configured, run the label half and skip every Project step.

**The clean-board guarantee (§ 2):** after any run, **no open issue is off the board
and none is unassigned** — every one is area-labeled, routed to its DRI, and has a
Track and Status. This pass is *uncapped*, so the guarantee holds even on a day the
deep pass hits its cap.

**The rule that makes this useful:** every verdict is written to GitHub — labels and
board fields — *not* just printed. The chat table is a **receipt, not the output**. A
run that only prints a table has done nothing, because the next run and the autopilot
both start with zero memory of it.

## Modes

- **Default** — analyze, write to GitHub, print the receipt.
- **Dry run** ("dry run", "don't change anything", "preview") — analyze and print the
  **exact** mutations you *would* make, change nothing. Use this the first time, and
  any time the taxonomy changes.

## Workflow

```
- [ ] 1. Pull the working set (open issues, every repo, + the board)
- [ ] 2. INTEGRITY PASS — uncapped, ALL open issues. Guarantee every one is:
         on the board · has an area label · assigned to its DRI · has a Track ·
         has a Status. This is the clean-board guarantee. (§ 2)
- [ ] 3. DEEP PASS — capped at 25 untriaged issues: category → effort → priority
         → duplicates → agent-ready gate. (§ 3–4)
- [ ] 4. Write it: labels, board fields, assignee, dup comments, `triaged` LAST
- [ ] 5. Print the receipt: summary table + detail on P0/P1 + board-health line
```

**Why split:** keeping the board on-project and assigned is cheap and must be
*guaranteed* every run. Categorizing and sizing needs to read each issue and open
files — expensive, so it is capped. Decoupling them means the board comes out
0-unassigned / 0-off-project **even on a day the deep pass hits its cap**.

## 1. Working set

Repos that feed one board may sit under **different owners**, and **issue numbers
collide across them** — always carry the repo alongside the number, and write
cross-repo refs as `owner/repo#N`.

```sh
for R in <owner/repo> <owner/repo>; do
  gh issue list --repo "$R" --state open --limit 300 \
    --json number,title,body,labels,assignees,createdAt,url \
    --jq ".[] | {repo:\"$R\"} + ."
done > "$SCRATCH/open.json"

gh project item-list "$BOARD" --owner "$BOARD_OWNER" --limit 1000 --format json \
  > "$SCRATCH/board.json"
```

⚠️ `--limit 1000` is mandatory — the 30-item default silently hides most cards.

**Untriaged = open AND no `triaged` label.** That label is the idempotency key —
without it every run re-litigates every open issue and spams the same comments. A
human who wants a re-triage removes `triaged`.

Also re-examine any issue that is `triaged` **but** has been edited or commented on
since the label was applied *and* is still unassigned — those are usually a scope
change that invalidated the old verdict.

**The 25-issue cap applies to the DEEP pass only, never the integrity pass.** When the
untriaged set exceeds 25, deep-triage the **newest 25** — priority is not a reliable
sort key here, it is usually unset until this pass runs — and report `N still untriaged
— next run` on the board-health line. The backlog drains over a few days; the board
stays clean the whole time.

## 2. Integrity pass — the clean-board guarantee (UNCAPPED)

Runs over **every** open issue in every repo, `triaged` or not, capped by nothing.

Per issue, ensure each — **fill blanks only; never overwrite a human's choice**:

| Invariant | How to satisfy |
|---|---|
| **On the board** | `gh project item-add "$BOARD" --owner "$BOARD_OWNER" --url <url>` |
| **Has an area label** | If missing, **determine and apply it** (§ 2a). This is the root-cause fix — don't route around a missing label, add it. |
| **Assigned to a DRI** | From the area label via `workflow.json` → `dri`. Never leave an open issue unassigned. |
| **Has a Track** | Mirror the area label to the Track field. |
| **Has a Status** | If none, set **Todo**. Never move an existing Status. |

🚨 **Especially never move `Hold`** — it means a human parked the card by choice, and
flipping it to Todo un-decides that. Hold is orthogonal to a `blocked` label: Hold =
*won't* do now; `blocked` = *can't*, with a "Blocked by: #n" pointer.

Because most open issues already carry an area label, this pass is cheap in aggregate:
the only real judgment runs solely on the handful that lack one.

Two things this pass **reports but does not change** — a card's state is a
conversation, not a silent edit:

| Observation | Action |
|---|---|
| In Progress, no linked PR and no commit on a `feat/<N>-*` branch in 72h | **Report** as stale — don't move it |
| Closed issue still Todo/In Progress | Set Done — this one is safe |
| A DRI now carrying >2 In Progress (from your assignments) | List under load warnings — still assign, don't drop the invariant |

### 2a. Determining a missing area label

Decide from the **repo + title + existing labels** — usually enough without opening
files. Apply exactly one, from the repo's own label set (`gh label list`).

If the title genuinely isn't enough, read the body — still bounded, only the few
unlabeled issues reach here. Only if it is *still* unclassifiable does it fall to the
lead as holding owner, flagged in the receipt as "needs area". **That last resort
should be near-empty; the goal is a real label, not a default dumping ground.**

⚠️ **The area label drives the assignee, so get boundaries between repos right.** A
subject-matter word in a title does not override the repo: e.g. AI/classification work
inside a backend service is a *backend* issue, not an *agents* one, however it reads.
Write the repo-specific boundary rules into `workflow.json` → `dri` and follow them.

## 3. Deep pass — categorize, size, prioritize (CAPPED at 25)

Runs only on **untriaged** issues, newest 25 first. Read the issue **and its
comments** before judging, and open the files it names. If `gh issue view` returns
empty (a transferred issue), read `.content.body` out of the board JSON instead.

By the time an issue reaches here it already has area, assignee, Track, Status and a
board slot from § 2 — so this pass adds only the judgment-heavy attributes.

### 3a. Category → label

| Verdict | Label |
|---|---|
| Bug | `bug` |
| Feature request | `enhancement` |
| Improvement (refactor, perf, DX, cleanup of something that already works) | `improvement` |
| Question | `question` |

Exactly one category label per issue. **Don't strip a category a human already set** —
if you disagree, leave theirs and note the disagreement in the receipt.

### 3b. Effort → label

Estimate against **this codebase**, not in the abstract. Open the files the issue names
before deciding; **an effort label you guessed is worse than none.**

| Label | Means |
|---|---|
| `effort:easy` | One repo, files obvious from the issue text, an existing test/pattern to mirror, no schema or infra change. Roughly a focused sitting. |
| `effort:medium` | Multiple modules or a new pattern; needs a design call but the shape is clear. |
| `effort:hard` | Cross-repo, migration, infra, an unresolved product question, or an epic's worth of surface. |

### 3c. Priority → the board's Priority field

`Critical→P0` · `High→P1` · `Medium→P2` · `Low→P3`.

- 🚨 **P0 is code/technical-critical ONLY** — prod broken, data loss, active security
  exposure, a customer blocked. Legal / policy / contractual items **cap at P1** no
  matter how urgent they read, and take the `legal` label.
- **Only fill blanks.** If a Priority is set, leave it and put the disagreement in the
  receipt with one line of reasoning. Priority is a human negotiation; silently
  overwriting it destroys trust in the whole routine.

Resolve field and option ids from `gh project field-list` in the same run — never
hardcode them.

### 3d. Duplicates

Compare each new issue against **all** open issues in **every** repo — near-dupes
across a repo boundary are common. One tracking issue per repo for the same feature is
a legitimate pattern, not a dupe; the same *work* described twice is.

When confident: apply `duplicate`, comment `Looks like a duplicate of owner/repo#N —
<one line on why>. Closing is up to <assignee>.` **Never close an issue.** When unsure:
no label, list it under "possible duplicates" in the receipt.

## 4. Gate — what earns the agent-ready label

This is the load-bearing part of the whole routine. The label is a **promise** that an
unattended agent can finish this issue and open a PR a human will want to review.
**`effort:easy` is not sufficient** — easy and safe-unattended are different questions.

Apply it only when **every** positive condition holds:

- [ ] `effort:easy`
- [ ] Exactly one repo, and you can name the files it touches
- [ ] Acceptance criteria concrete enough to write a test against
- [ ] An existing test file or pattern to mirror — **or** it is a pure docs/copy change
- [ ] No open product/design question in the body or comments

…and **none** of these disqualifiers is present:

| Disqualifier | Why |
|---|---|
| Labels `blocked`, `epic`, `legal`, `compliance`, `security` — or Status `Hold` | Needs a human owner (or a human un-parking) by definition |
| Body says "Blocked by: #n" / "depends on" / "sequenced after" (unresolved) | Ordering constraint an agent will miss |
| Priority P0 | A P0 deserves a person right now, not a queue |
| Touches infrastructure, migrations, or CI workflow files | Human-gated |
| Involves secrets, env vars, runtime config, or a credential swap | ⚠️ A credential/env change needs a **superset first** or no revision can boot — and the tooling silently stores empty or newline-suffixed values ([`secrets-and-ci.md`](../../reference/secrets-and-ci.md)) |
| Analytics schema or view change | Needs a materialized-view rebuild ordered against the image roll |
| Needs a coordinated change in two repos | Two PRs, one breaking moment |
| Requires touching shared staging or prod | Merging the integration branch may deploy |

**When in doubt, don't apply it.** The cost of a missed easy issue is one day; the cost
of a bad `agent-ready` is a wrong PR landing on a teammate's review queue with your
name on it.

## 5. Write it

Integrity writes first, for every issue: add-to-board → area label if missing →
assignee if unassigned → Track if blank → Status Todo if none. Then per deep-pass
issue: category → effort → Priority if blank → `agent-ready` if gated → duplicate
comment if any → **`triaged` last**.

🚨 **`triaged` goes on last, always.** If the run dies halfway, an issue without it gets
picked up cleanly next time; an issue marked `triaged` before its labels landed is
silently lost forever.

⚠️ **Pass each label as its own explicit `-f "labels[]=…"`, never a split shell
variable** — the label endpoint auto-creates any label that does not exist, so an
unsplit variable silently creates a junk label repo-wide. After any label-add loop,
read the labels back and assert none contain a space. See
[`../../reference/shell-traps.md`](../../reference/shell-traps.md).

Don't post a per-issue "I triaged this" comment. Labels are the record; comments are
for duplicates and for a genuine question to the DRI.

### 🚨 The receipt is a claim — verify the writes landed

`gh api` and `gh` mutations **exit 0 on operations the server rejected**, so a run that
looks clean can have written nothing. This run's whole value is that its verdicts reached
GitHub; a receipt reporting "0 unassigned" off attempted writes rather than confirmed
state is worse than no receipt, because the next run and the autopilot both trust it.

**Before printing § 6, re-read the state you claim** — one board pull and one issue list,
after the writes, and count from *those*:

```sh
gh project item-list "$BOARD" --owner "$BOARD_OWNER" --limit 1000 --format json
gh issue list --repo <owner>/<repo> --state open --limit 300 --json number,labels,assignees
```

If a number in the receipt does not match the re-read, **say which issue failed and why,
loudly** — that is the one line a human needs. Details and the other shapes of this trap:
[`../../reference/verification.md`](../../reference/verification.md).

## 6. Receipt

Open with the **integrity line** — proof the guarantee held this run:

`Board: N open · 0 off-project · 0 unassigned · N area-labels added · N newly assigned
· N Status set`

**The two zeros are the point.** If either is non-zero, something blocked the write —
say which issue and why, loudly.

**Summary table** — every issue that went through the deep pass this run:

| Issue | Repo | Title | Category | Effort | Priority | Assignee | Agent-ready | Notes |
|---|---|---|---|---|---|---|---|---|

Then **detail only for P0 and P1**: 2–4 lines each — what it is, why it is that
priority, what it blocks, and the concrete next action with a named owner. This is the
part a human reads at breakfast; make it worth the ink.

Close with a **board-health line**: `N deep-triaged · N still untriaged (next run) · N
agent-ready · N P0/P1 open · N without priority · N stale In-Progress · N possible
dupes`, plus any load warnings and anything you deliberately left alone.

**On a quiet day** — nothing off-board, nothing unassigned, no new untriaged — say so
in the integrity line plus one sentence, nothing else. A clean board should read clean.

⚠️ **Report, don't accuse.** A low or zero lane in any per-person view is usually
**allocation**, not underperformance. Ask the lead before inferring.
