# Writing guard tests that survive adversarial review

A **guard test** asserts an invariant about the repo itself rather than about a
unit of behaviour: "no workflow hardcodes a WIF provider", "no module constructs
this type with a caller-supplied `env`", "this runbook still says the dangerous
thing is dangerous".

Guards are unusually easy to write and unusually easy to write *wrong*, because a
broken guard and a satisfied guard look identical: both are green. Everything
below was measured — each item is a guard that passed its whole suite and was then
defeated by a reviewer or a bot.

---

## 1. Pin the inventory; don't check a property

When a guard must guarantee "nothing unsafe was added", **pin the complete
reviewed set** (address → exact normalized expression) rather than asserting a
property of each item. Property checks lose to adversarial review reliably, and in
sequence.

One real case defeated **three successive** property guards on the same code, each
verified green:

1. name-based ("is it called `wif_binding`?") → defeated by a fresh resource name
2. type-based ("is it an IAM *member* resource?") → defeated by an authoritative
   IAM *binding*, which is worse: it removes the scoped members on apply
3. substring ("does the expression mention the pinned local?") → defeated three
   ways at once — a decoy local whose name *contains* the pinned one; one
   legitimate element laundering a hardcoded sibling inside a `members = [...]`
   list read as a whole; and addressing the same identity by `.email` instead of
   `.name`, invisible to the scan.

Each fix only closed the mutation the previous reviewer happened to imagine. An
inventory pin closes the entire family of "express the same thing differently" at
once, including mutations nobody has imagined yet.

**The cost — a legitimate change requires editing the pin — is the feature.** It
forces the review step every property check skips.

**How to apply:** enumerate, normalize (collapse whitespace), pin as a dict, and
add a comment recording *which* bypasses forced the pin. Keep cheap property
assertions alongside for readable failure messages, but never let them be the
guarantee.

### A predicate derived from the pin is still a property check

Narrowing it trades blind spots rather than shrinking them. One guard went through
three in two review rounds, each fix reviewed and each too narrow in a *different*
direction — for "is this workflow's provider hardcoded?":

1. `"vars." not in expr` → missed `${{ secrets.X }}` / `env.` / `inputs.`
2. `expr == <the sandbox literal>` → now meant "hardcodes *sandbox's* pool", so
   hardcoding a **different** project's pool passed — the original failure mode
3. `"${{" not in expr` → what "hardcoded" actually means; reds on both

**When you narrow a predicate in response to a review finding, re-run the mutation
the OLD predicate caught as well as the new one. Both must red.**

### Matching call syntax is a property check too — pin the import surface

A guard needed "nothing constructs `AuditEvent` with a caller-supplied `env`".
The first drafts matched construction *syntax* and review defeated them **eight**
ways, three of them working code paths:

- `from x import AuditEvent as AE` … `AE(env=…)` — only the local binding differs
- `REGISTRY = {"decision": AuditEvent}` … `REGISTRY[kind](env=…)` — callee is a `Subscript`
- `klass = AuditEvent` … `klass(env=…)` — a rebound local
- `class WireEvent(_Base)` where `_Base = AuditEvent`, with a `cls(**body)` classmethod
- `AuditEvent(**payload)` — a `**` splat carries the key past keyword inspection
- `dataclasses.replace(event, env=…)`, `object.__setattr__`, `event.__dict__["env"] = …`

**The fix was not eight patches.** The first four share one cause and closed at
once by pinning **the set of modules permitted to import the class** — the
invariant a registry, a rebinding and a subclass must all pass through, since none
can be written without naming the class first.

> When the property is "nothing may *do* X to type T", the syntaxes of X are
> unbounded, but the set of modules that can **reach T** is small, enumerable and
> semantically meaningful. **Pin the reach, not the verb.**

Two failure modes while doing it: a guard scoped by an allow-list of package
directories drifted from the requirement it proved (six packages vs "the non-test
tree") — derive the sweep instead (`git ls-files` minus `tests/`). And a count
floor cannot detect a *deleted* entry.

---

## 2. The bug is usually WHERE it looked, not WHAT it accepts

Measured over five review rounds where every round found a real defect in the
*previous* round's guard fix — four in a row, all the same shape: the property was
checked correctly in one place, and a second path to the same place went
unexamined.

1. **Denylist instead of allowlist.** The guard forbade one column. A sibling
   column reintroduced the exact bug. Fixed by pinning an ALLOWLIST of the
   identifiers a `WHERE` clause may mention, so an unreviewed column fails by
   being *absent* rather than by being enumerated.
2. **Section-wide check satisfied by a sibling's copy.** A pin anchored on a whole
   section passed when an entire step was deleted, because a neighbouring step
   carried the same string. Fix: pin per step.
3. **Fence-style blindness.** A ``^``` `` anchor missed indented, blockquoted and
   `~~~` fences, and inline code spans. The document's dominant idiom was
   blockquote callouts, so the blind spot was one edit wide.
4. **Depth-1 block capture.** The indented-code-block branch appended only the line
   that *started* the block, so a multi-line command was inspected one line deep.

#1 is what people design for. #2–#4 are all "the guard never looked there", and
they are both more common and harder to see, because the guard passes on the
*correct* content while silently skipping the region that changed.

**Mutate along three axes, not one:**

- **What** — the forbidden thing reworded: a wrapper function, a sibling column, a
  comment carrying the right string, a trailing `or` that neuters a matched predicate.
- **Where** — the same thing *relocated*: a different fence style, an indented
  block, inside a blockquote, in inline code, on line 2+ of a multi-line block, in
  a sibling step, in a section outside the slice.
- **Spelling** — the same thing written another legal way.

### The spelling axis, measured

A guard on an OpenAPI document keyed on the `$ref`'d *component* name and read
only operation-level `parameters`. Six ways past it, every one legal and every one
a spelling the document already used:

- an **inline** (non-`$ref`) parameter — 62 of that document's parameters were
  inline against 15 `$ref`s, and the guarded operation already had seven
- a **path-item-level** `parameters` block — nine paths had one
- an **alias component** whose body is itself a `$ref` (`components.parameters` is
  `Map[string, Parameter | Reference]` in OpenAPI 3.1, so a one-hop resolver lands
  on `{"$ref": …}` and finds no `name`)
- a **path item declared as a `$ref`** — `"$ref"` is not an HTTP method, so a
  `for method in item` loop skips the whole path

It also **false-redded** on hoisting a parameter from the operation to its path
item — identical semantics.

The rule the fix followed: **key on what the requirement is written about.** The
requirement said "MUST NOT gain `page_token` on the wire", so the guard resolves
parameter *names* — merging path-item with operation, dereferencing `$ref` chains
— rather than matching the component name today's spelling happens to use.

> ⚠️ Widening a matcher can **drop a transitive pin**. `$ref: PageSizeQuery` can
> only mean one schema; an inline `page_size` can mean any, so an inline
> `maximum: 5000` passed against routers declaring `le=200`. When you widen, ask
> what the old narrow form was pinning for free.

### Prove the slice reaches the end of its region

Asserting that four step labels are *present* did not stop a line repeating the
next heading from shrinking the region past the whole final step. **Assert an end
anchor that sits after the last thing you guard.**

---

## 3. Comments satisfy token matchers — including your own explanatory comment

When a test asserts a token is present in source it extracted (a workflow `run:`
body, a script region, a config block), **comments are part of that text.**

Measured: a test asserted `"exit 1" in body` over a preflight step's `run:`. A
later commit added the comment *"The SA test used to sit after the provider
`exit 1`, which made it unreachable"* — and from that moment, mutating the only
real `exit 1` to `exit 0` left the assertion **passing on the comment alone**.

The nasty part: the disabling edit is *the explanatory comment a careful author
writes about the guard*. Nobody edits the test, so nothing looks suspicious.

**Match a statement, not a substring** —
`any(l.strip() == "exit 1" for l in body.splitlines())` — or strip comment lines
before matching. Prove it: add the token to a comment and confirm the test still
reds when the statement is removed.

The same trap runs in reverse for mutation harnesses: a `perl -0pi -e 's{...}{...}'`
without `/g` replaces the **first** occurrence, which in a well-commented file is
the comment. The code is untouched and the mutation prints SURVIVED.

### Negative vocabulary assertions permit every rewording

`assert "that project's service account" not in stdout` was defeated by a reworded
re-certification — "and the deployer SA is that project's" — measured at 0 killed.

**Replace with a positive, behavioural assertion:** assert the run *emits* the
thing the operator needs, which no rewording of the other message can fake. Where
no such assertion exists, record the surviving mutation as a known limit rather
than chasing it with a fragile matcher.

Corollary: a substring scan for a banned token **fires on a warning about that
token**. Never "fix" that by negating the phrase — an anchor is a substring of its
own negation.

---

## 4. Region, not line — and for a claim, not even region

**Scope a prose match to the REGION, never to the line.** Shell summaries are built
from many `echo` calls hard-wrapped at ~80 columns, so one sentence routinely spans
two or three lines. A matcher requiring two tokens on the *same* line silently
misses the wrapped form:

```
echo "# merging a change here triggers the gated"
echo "# terraform-apply, which rolls the corresponding service."
```

First line has one token, second has the other, neither has both → **the guard
could not detect its own revert.** It also failed the opposite way: re-wrapping a
*correct* claim across two echoes made it red.

Pick one token that carries the meaning and assert its presence/absence over a
whole region. Region-scoped on one token is robust to wrapping in both directions;
line-scoped on two is robust to neither.

### The opposite error: whole-file scope fails in both directions

A guard extracted every `§(\d+\.\d+)` from each file citing a design doc. One file
carried a standalone `§4.2` ~200 lines below the real citation. Measured:

- **false pass** — deleting the real `§4.1` next to the path left the guard green,
  satisfied by the far-away `§4.2`
- **false red** — adding a legitimate `§7.3` anywhere in the file made it demand a
  matching heading in an unrelated design doc

Anchor the region to the thing that gives the tokens their meaning — the lines
mentioning the cited path — then take a window of ±N *lines* around it. Assert
loudly when the region comes back empty.

### For a CLAIM, drop the window entirely — pin whole clauses by COUNT

⚠️ **The "±N lines around the citation" recipe is right for a CITATION and wrong
for a CLAIM.** A citation is a token whose neighbourhood gives it meaning. A claim
*is* the sentence — so the sentence is what to pin, and a window around it only
adds ways to be satisfied by something else.

An anchor+window+keywords design guarding three prose claims lost **five** ways:

1. **Keywords float free of the claim.** The guarded string was one ~1,300-char
   source line, so ±2 lines *was* the whole string: a trim deleting the substantive
   branch but keeping the lead sentence stayed green.
2. **Capitalisation is not a boundary.** A `THIS MODULE CREATES` needle was
   disarmable by SHOUTING an unrelated nearby sentence.
3. **Windows red on reformatting.** Rewriting as a heredoc moved the text out of
   the window with the prose byte-identical.
4. **Bounds were unpinned.** Setting a clause list to `()` leaves the inventory the
   same length and checks nothing — `len(_SITES) == 3` cannot see it.
5. **Pinning the correction is not pinning the claim.** With only a correction
   paragraph pinned, reinstating the bad claim eight lines above stayed green — the
   file then asserted and disowned the same thing.

**How to apply:** `(file, whole_clause, min_count)` tuples, matched
case-insensitively over the file normalized to one line (strip leading `#`/`//`
per line, collapse whitespace, drop `*` and backticks). No anchor, no window.
**Counts, not presence** — a clause appearing twice in one file means deleting it
from one site must red, which presence alone cannot see. Pin the total AND a
`min_count >= 1` floor.

> 🚨 **A text pin freezes WORDING, not CORRECTNESS — say so in the file.** One
> guarded runbook was wrong twice, in *opposite* directions, and both drafts would
> have passed a green pin. The pin's job is to force the re-check into the same
> commit, not to tell you the answer.

---

## 5. Hash the exemption, not its current vocabulary

When carving a file out of a lint or scan test, **pin the exemption to a content
hash**, never to the set of bad strings it currently contains. A pinned set of bad
strings permits every rewording; a hash forces the carve-out back through review
the moment the file changes at all.

Same for prose: when the guarded thing is a document, a vocabulary check loses to
rewording. Pin the content hash and let derived token-exact tests carry only what
is mechanisable.

---

## 6. Allowlist beats ban-list for shell and workflows

Guarding a workflow against a dangerous command with a ban-list regex lost **four**
measured ways. The design that held: an **allowlist** of `uses:` values and command
heads, plus a **forbid list of shell constructs** — `$(`, backticks, `#`, `eval` —
rather than attempting to parse shell.

> ⚠️ A `\s*` added to a continuation-join reintroduced the exact bug it was
> fixing. Re-run the old mutation after every regex tweak.

---

## 7. Structural traps that make a guard vacuous

- **Completeness checks must be independent.** `count == list.length` over the list
  you loop is circular and passes over a narrowed subset. Compare discovery against
  an *independent* inventory.
- **Import the inventory; don't rebuild it.** A guard that reconstructs a
  dependency's inventory from regexes loses to any shape it didn't anticipate.
  Import and call the dependency's own function. 🚨 A package `exports` map
  restricts **bare specifiers only** — a deep relative path still resolves.
- **Emptiness must match the consumer.** A config guard's emptiness/equality test
  must match the test in the code that *consumes* the value, not the convention of
  the guards beside it. Copying the neighbours' `.strip()` shipped a hole where
  `"   "` booted clean and was then honoured.
- **Presence checks are defeated by presence.** "The route CALLS `x`" passes when
  the verdict is discarded. Anchor to the `!verdict` branch, not the call.
- **The happy path must be reachable.** A refusal test whose fixture cannot reach
  the un-refused path passes for the wrong reason. Stage the resource, then mutate
  die→warn to prove the assertions bite.

---

## 8. When a guard needs a third scope-widening round, stop widening

A guard for a config pin was written as a structural check **twice** and breached
**both** times — never by a wrong predicate, always by scope:

1. **Regex over the source.** Passed with the pin commented out; with the pin
   deleted but quoted in the module docstring; with the pin moved below the
   imports; and with it nested inside a hook. Four dead-pin states, all green.
2. **`ast` parse** (module-level `Expr`, `lineno` before the first import). Killed
   all four — then was breached by a tracked, empty `__init__.py` the test runner
   executes *before* the file the guard opened.

**A static answer to "does X happen early enough" is always scoped to somewhere,
and the import graph moves.** Each fix bought one round.

**What ended it: a child process asserting the real outcome.** Spawn with the
variable REMOVED, import the module the way the real loader does, assert the
resulting value. No list of paths, no list of packages, no fresh patch when imports
move — and crucially **as true in CI as locally**, because the child's env is
*constructed* rather than inherited.

> ⚠️ That last property is the whole trick. CI supplied the variable, which made
> every in-process value assertion pass under all six mutations. Constructing the
> child's environment is what removes the mask.

When a guard needs a third widening round, ask what observable state the
requirement is actually about, and build the situation that exhibits it.

---

## 9. 🚨 A killed mutation proves the guard FIRES, not that it is AIMED

Measured across five review lenses, a delta lens and a bot: **four findings, one
shape** — each time the guard's predicate was right, its mutation was "killed", and
it was pointed at something the real defect never touches.

1. An invariant read `<cell>/terraform.tfvars`. The documented arming path is
   `images.auto.tfvars`, which **overrides** it. The mutation had edited the file
   the guard already read.
2. Fixed by adding `*.auto.tfvars`… which omitted the **`.json`** forms Terraform
   also auto-loads. Same evasion, one file extension over.
3. Fixed by adding those… which globbed the two families as separate groups.
   Terraform sorts them as ONE lexical sequence, so `a.auto.tfvars.json` loads
   before `b.auto.tfvars` and the guard computed a different winner than Terraform.
4. A "never `:latest`" arm scanned the `docker push` **argument**. Every builder
   pushes an expression and builds the tag in a prior step, so it inspected text a
   tag structurally cannot appear in. The mutation that "killed" it had edited the
   push line — the one spelling no author would write.

**When writing the mutation, do not ask "does the guard reject this?" Ask "is this
the spelling a real author would produce?"** Prefer a mutation copied from an idiom
already committed elsewhere in the repo.

### Fixes that TIGHTEN a matcher need MUST-STAY-GREEN cases

Otherwise "reds more often" scores as success. One round ran 5 KILL + 3 KEEP; two
KEEPs were correct spellings already live in the repo that the tightened matcher
had started rejecting. Without them the fix ships a false RED that fires on the
next author who reformats a correct file.

**A guard that reds on a semantics-preserving edit is a guard someone deletes.**
Assert the no-false-fire direction explicitly: reformat, de-shout, re-wrap.

---

## Checklist

Before trusting a new guard:

- [ ] Is the guarantee an **inventory pin**, not a property check?
- [ ] Mutated along **what**, **where**, and **spelling**?
- [ ] Is every mutation **a spelling a real author would write**?
- [ ] Does the guard catch **its own revert**?
- [ ] Are there **MUST-STAY-GREEN** cases — reformat, re-wrap, hoist, de-shout?
- [ ] Does the region have a **proven end anchor**?
- [ ] Do **comments** satisfy any matcher? Does a comment absorb any mutation?
- [ ] Is any assertion **negative/vocabulary**-based? Make it positive and behavioural.
- [ ] Is any completeness check **derived from the list it iterates**?
- [ ] Did an **independent pass** look for a mutation that makes the guard *wrong*,
      not one that removes it?

See also: `mutation-harness.md` (how the harness itself lies to you),
`verification.md` (why green is not evidence).
