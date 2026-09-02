# Reviewing a change before it becomes a PR

**Run the adversarial review before opening the PR, every time — not after.** Findings
then get fixed in the branch instead of chased in review.

Green CI plus a green review bot has never once been sufficient evidence that a
control holds.

---

## The shape

Spawn several **read-only, max-effort, single-lens** reviewers **in parallel**, one per
lens, then adjudicate the merged findings yourself. Typical lenses:

| Lens | Asks |
|---|---|
| `correctness` | Does this do what it says on every input? |
| `contract` | Does it change a wire/API/schema contract, and is the other side updated? |
| `scoping` | What else reaches the code this touches, that the diff does not touch? |
| `safety` | Tenant predicates, credentials, secrets — is the blast radius contained? |
| `tests` | Do the tests bite? Would they catch the bug they name? |
| `deploy` | What happens on rollout, rollback, and a partial apply? |

**`scoping` and `safety` are two questions, and they were one word until it cost
something.** The table here said "blast radius"; the agent said "tenant and credential
safety". A planner naming `scoping` off this table got an agent hunting for tenant
predicates, found none on a repo with no tenants, and reported *no findings* — a clean
run of the wrong question. Each name now means one thing in both files.

Each gets **fresh context and max effort**, which an inline same-session review does
not. Scale the lens list to the change — but do not under-scale: five-file plumbing
changes still ship regressions.

⚠️ **Spawn `gh-issue-flow:diff-reviewer`, never the bare name** — a shadowing file in
`~/.claude/agents/` wins silently and returns a plausible review of the wrong thing.

⚠️ Parallelism must live in the **parent**; a subagent cannot fan out. See
`parallel-agents.md` for what those agents share and can clobber.

---

## Re-review the fixes when they are NEW LOGIC

**Code written to satisfy a reviewer never got reviewed itself.**

If adjudicating the findings introduced a new branch, gate, condition or code path,
spawn **one** more reviewer, max effort, scoped to **just that delta** before
committing. Not a fresh fan-out, not for test/comment/doc-only fixes, and **not a
loop** — one conditional pass, then move on.

**Run it as the lens that RAISED the finding.** The delta exists to establish that
lens's property; asking a different question of it is how the pass goes through
motions. Measured: three max-effort lenses cleared a diff; a pre-apply gate was then
added *in response to the deploy lens*, and a bot found a Medium bug in it. **That late
code was the only part never adversarially reviewed** — and a `correctness` pass over a
gate that exists for rollout ordering would have been looking somewhere else. Use
`correctness` when the finding was your own rather than a lens's.

The delta pass keeps earning its keep. On another change `correctness` and `contract`
both returned **no findings** — and `scoping` still found a real wrong-denial hole,
plus three comment claims that overstated the code. Then the **delta re-review of that
fix** found the fix had dropped a normalization the old code did incidentally, and
verified a "byte-identical" claim by differential-testing ~105k generated paths
instead of taking the author's word.

> **A lens returning "no findings" is not evidence the diff is clean — it is evidence
> about that lens.**

---

## 🚨 Every lens shares one blind spot: code the diff does not touch

Lenses are scoped to the diff by construction, so **a guard that is correct for
everything in the diff and blind to an untouched caller reads as clean to every lens at
once.** Adding more lenses does not help.

Measured: five max-effort lenses found seven real defects and **all five missed** the
biggest one — a new `/32` guard lived in a test that only reads the committed tfvars,
so a `-var` / `-var-file` override reached the firewall's `source_ranges` completely
unvalidated. The variables file was not in the diff, so no lens looked at whether it
should have been. A PR-scoped bot caught it immediately.

> "Is this change correct?" and "is this property now enforced?" are different
> questions. A guard's *coverage* is a claim about the whole system, and you cannot
> verify it from the changed lines alone.

**This is what the `scoping` lens is for, and the question is now in the agent
itself** — `agents/diff-reviewer.md` carries it verbatim, so it fires whether or not
the caller remembers to paste it. It was a paste-it-in instruction here for long
enough to be worth saying plainly: **an instruction that depends on the caller
remembering is not a control.**

So: **any diff that adds a guard, validation or invariant gets `scoping`**, whatever
else the planner named — and **answer the question yourself before shipping** too. The
lens can miss it; you are the layer that knows what the change was for.

Then **decide the layer deliberately and write the split down in code**, because the
next reader will otherwise see the gap as an oversight.

---

## Recurring root causes worth checking for directly

### A denylist guard is fail-open

A guard written as a *denylist of shapes* — known member spellings, enumerated
statement types, "skip if it mentions X" — will be bypassed. On one PR a red-team
reviewer demonstrated **14 working bypasses** of one.

**Invert it:** require every item to match an explicit allowlist, and make anything
unreadable **fail** rather than pass. *"I could not resolve this expression" is
ignorance, not safety* — treating the two as the same was the single most repeated bug
in that PR.

### An exemption must match the WHOLE expression

Each fix must **remove** the boundary, not move it inward. A carve-out reading "skip if
this grant references the safe role" was defeated in three consecutive rounds by the
same decoy one level deeper:

1. the reference appearing in `depends_on` anywhere in the body
2. the same string in a **same-line comment** on the `role =` line
3. a **ternary** naming the safe branch while evaluating to the dangerous one

The shape that finally held: read the attribute, strip comments, and require the
carve-out to equal the **entire** expression.

> Ask directly of any new exemption: *what is the largest text this test could be
> satisfied by that is not the thing I mean?*

### When a fix is positional, fix the MIRROR IMAGE in the same commit

Distinct from the boundary problem: here each fix was *correct where applied* and left
the symmetric position wide open. Five lenses cleared a file; a bot then found two,
both this shape:

- A fix for a comment *between the label and the brace* hiding a block matched headers
  on a comment-blanked view — but blanking a comment to **spaces** meant a comment
  *before the keyword* then failed the `^module` anchor and hid the block just as
  completely.
- A fix for an error handler that raised while formatting its own message was applied
  **inline in `main()`**, leaving the identical call in a sibling function untouched.

> **This bug had a position — enumerate every other position it can occupy, and fix
> them together or factor the guard into one helper.** After any positional fix, grep
> for the construct you just fixed and confirm every hit is covered.

### Read the comments adjacent to the code a new branch gates

No number of review rounds substitutes for this. One added gate keyed off a flag, and
the comment block ~80 lines below said verbatim that a root "can enable encryption purely
from its committed tfvars … and `ENABLE_ENCRYPTION` stays false on such a run" — the fact
that invalidated the gate was already written down in the file being edited.

---

## Neither layer is sufficient — budget for several bot rounds

On one security-control PR the pre-PR review caught two things that would otherwise
have shipped (an OAuth scope that does not exist, so every read would have 403'd in
production; and the 14-bypass denylist above). Then the bot found **7 more real defects
across 5 rounds** *after* that review passed — including holes each earlier fix had
just opened.

On another, four max-effort lenses missed three High-severity holes the bot then found,
**two of the three in code written to satisfy an earlier lens.**

> Your own fan-out is the layer that most needs the second opinion, because it reviews
> the diff it just helped shape. **A security or guard PR is not done at the first
> green.**

---

## ⚠️ A passing bot check is not evidence of zero findings

**A green check plus zero unresolved threads is not evidence of zero findings.** A
review bot's summary comment can carry `🛑 Comments failed to post (N)` sections whose
findings never become review threads — invisible from the checks page, invisible to
`gh pr checks`, invisible to a thread count.

Measured: check **pass**, 3 review threads, and **15** recovered findings across two
collapsed `<details>` sections. The summary claimed 18 actionable comments; ~3 were
delivered. Two of the buried ones were user-facing security defects.

**Read the summary comment body. Never trust the check or the thread count.**

### It rate-limits and still reports PASS

One review never ran at all — *"Review limit reached … we couldn't start this review"* —
and the check went green anyway.

🚨 **The re-trigger can be a NO-OP.** After the window elapsed, an `@bot review` comment
returned only an acknowledgement carrying the catch: *"…is an incremental review system
and does not re-review already reviewed commits."* It had marked those commits seen
while skipping them for the limit, so the command had nothing to do.

- **A re-trigger alone does not undo a rate-limited skip — only a NEW COMMIT does.**
- The wait window is **variable** (13 min in one case, 34 in another) — read it from
  the comment.
- **Distinguish the two comment shapes by body, never by count:** an ack matches
  `Review triggered`; a real review matches `Actionable comments|Walkthrough`.
- If you merge knowing a bot never looked, **say so** rather than letting an all-pass
  check board imply two reviews happened.

---

## Reporting findings and decisions

**Frame a decision as the decision, not as a retreat** — when that framing is factually
accurate. If the prior approach was never actually deployed, write it as an initial
provisioning decision, not "instead of X".

**Report, don't accuse.** In any team-health or throughput summary, a low or zero lane
is usually **allocation**, not underperformance. Ask the lead before inferring, and
make targets conditional.

**Verify the harness before believing a result.** In one session mutation harnesses lied
four separate times — an unquoted `$VAR` that never word-split so *every* case reported
CAUGHT; a `perl` pattern that silently matched nothing so a real bypass looked like a
miss; a grep that missed a crash-instead-of-summary output; and a broken baseline that
made all 13 results meaningless. See `mutation-harness.md`.

**When a tool turns out to be uninvokable, grep every skill that calls it.** One skill's
review step was an uninvokable no-op for two days — every unattended PR shipped with no
adversarial review while the file claimed otherwise — because only the first of two
callers got fixed.

**Never hardcode a test count in a skill or doc.** A growing suite moves by dozens within
a day, and the stale number then contradicts a passing run. Green-vs-red is the gate.
