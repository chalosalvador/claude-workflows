# Verification: why green, empty and exit-0 are not evidence

One failure shape runs through everything here: **the tool silently did nothing,
and the silence looked like success.** A false verification is worse than none,
because it gets written into a commit message or a PR body as a positive claim, and
the next reader stops looking.

---

## 1. A CLI can exit 0 on an operation that did not happen

`gh` does this routinely. Measured twice in one session:

- `gh api .../pulls/<pr>/comments/<id>/replies` returned **HTTP 502** four times in
  a row. The pipeline exited 0, so `&& echo replied` printed "replied". Reading the
  thread back showed the reply never posted — and the thread had already been
  **resolved**, leaving it resolved-in-silence.
- `gh pr merge <pr> --squash --match-head-commit <SHORT_SHA>` printed
  `GraphQL: … Could not coerce value to GitObjectID` and **exited 0**.
  `merged: false`. (`--match-head-commit` needs the full 40-char oid.)

These are the actions whose whole point is a side effect on someone else's system.
An exit code reflecting "the CLI ran" rather than "the server accepted" makes the
natural `cmd && echo ok` idiom actively misleading.

**Never chain `&& echo <success>` off a mutation. Read the state back and assert
on it.**

```sh
gh pr view <n> --json state,mergedAt,mergeCommit
```

> 🚨 **The inverse also happens.** `gh pr merge` once **exited 1 on a merge that
> succeeded** — `state=MERGED` with a real merge commit, the non-zero exit coming
> from a later step. Retrying on the exit code would have chased a phantom failure.
> Same remedy in both directions: read the state back.

### The mirror image: a write that SUCCEEDED but does not read back yet

Not every mismatch is a failed write. **Projects v2 is eventually consistent.** Measured:
six `gh project item-add` calls each returned a real item id and exit 0; `item-list`
immediately afterwards reported **0 cards**, then 5 at ~20s and 6 at ~30s. Every write had
landed.

So a read-back that concludes from one immediate query manufactures a false failure — the
same error as trusting exit 0, pointed the other way. **Verify the object, not the
aggregate:** a write that returns an id lets you resolve that id directly, which is true
immediately even while the collection lags.

```sh
gh api graphql -f query='{node(id:"<returned id>"){... on ProjectV2Item{project{number}}}}'
```

Where only a count is available, **poll with backoff** before declaring anything wrong.
Label and issue writes do not need this; board writes do.

### The trap bites READS inside an unattended poll

An unresolved-thread query hit a 503, `--jq` produced nothing, and the *error text*
landed in the variable — so `[ -n "$t" ]` was true and the watch reported
`unresolved: {"message": "No server is currently available…"}`. There were **0**.
A phantom finding is worse than a missed poll: it sends you hunting for a review
comment that does not exist.

**Validate the shape of anything read from a CLI before believing it:**

```sh
t=$(gh api graphql -f query='…' --jq '…|length' 2>/dev/null)
case "$t" in ''|*[!0-9]*) : ;; 0) : ;; *) echo "unresolved: $t" ;; esac

echo "$s" | jq -e 'type=="array"' >/dev/null 2>&1 || continue
```

Outages are bursty and endpoint-specific — in that session `gh api user` and the
GraphQL thread query were both 503-ing while `gh project item-list`, `gh issue view`
and `gh pr checks` all worked.

---

## 2. An empty grep is only evidence if the pattern can match at all

When a grep **is** the acceptance criterion ("no reference to X survives"), prove
the pattern fires on a known-present string first, then trust the empty result.

- ⚠️ **`git grep -E "\bword\b"` matches ZERO lines.** git grep's POSIX ERE has no
  `\b`. It does not error — it returns empty, which reads exactly like "clean". Use
  **`git grep -w word`**. One sweep reported clean and written into a commit
  message; `-w` returned 177 hits.
- ⚠️ **`git grep` reads the INDEX, not the working tree.** After unstaged edits it
  reports pre-edit state — which reads exactly like "the edit didn't apply". Use
  plain `grep -rn` for a working-tree claim.
- ⚠️ **`git check-ignore` exits 0 on ANY pattern match, a negation included.** So
  `git check-ignore -v path && echo IGNORED` reports a path you just un-ignored with
  `!/path` as ignored. The `-v` output is the real signal: parse the pattern (third
  colon field) and test `startswith("!")`. Treat empty output as a **third state** —
  collapsing "no match" into "ignored" let a reviewer delete a blanket ignore line
  with the guard still green.
- ⚠️ **Substring false positives cut the other way.** `grep -n "rag"` matches
  `verify-cove`**`rag`**`e`. An "exit 0, still dirty" reading is as wrong as a false
  clean.
- ⚠️ **Exclude with an explicit `grep -v`, never by narrowing the pattern.** A leading
  `/` added to a pattern in order to exclude one longer filename also silenced every
  legal same-directory link to the short one.

### 🚨 After a RENAME, a clean grep for the old string proves nothing

Different failure: the pattern fired correctly and the answer was true — it was the
wrong question. `git grep -F "<the old directory>"` returned 0 and went into a commit
message as the acceptance criterion. A catch-all rewrite rule had sent **77
references across 17 files** to paths that never existed. Old string gone ✅, new
string wrong. Three review lenses each found it independently; no test could.

**The only honest check after a move is to RESOLVE every reference and DIFF the
unresolved set against the base** — never count, never grep for absence:

```python
# for every tracked file, every path-like string, at base AND at head
print(sorted(head_unresolved - base_unresolved))   # must be empty
```

That turned "0, clean" into "10 before, 10 after, and the one delta is a pre-existing
broken image reference following its directory rename". Also prove the replacement
**landed** (`git grep -c` the new string) and that its target **exists**.

### A path-prefixed pattern cannot see a same-directory link

A sweep matching `architecture/tenant-isolation` reported **41** inbound references.
The real number was **52** — sibling files inside `architecture/` cross-link as
`](./tenant-isolation.md)`, which contains no `architecture/` at all.

**Before believing an empty grep:** run it against a string you know is there
(`git grep -c`). Prefer `-w` over `\b`, `-F` for literals. And **enumerate what the
pattern cannot see before calling it a gate** — one scope tripwire grepped
`default =` / `variable` / `output` and therefore could not see a `description`
changed inside a `resource` block.

---

## 3. A failed probe is evidence about the PROBE

When a reviewer or bot claims a guard is too weakly scoped, the instinct is to write
one mutation and, if the guard reds, mark the finding theoretical.

Measured: a bot said an assertion searched the whole file. The first probe added a
decoy under a *different* variable name; the assertion anchors on the name, so it
killed that trivially and the finding looked wrong. The probe that actually tests the
claim keeps the name AND the expression identical, relocating only the thing the
reviewer named. That **survived** the pre-fix guard. The finding was right; the probe
was lazy.

> A weak probe and a sound guard produce the same green, so green cannot distinguish
> them.

**For any finding of the form "X could be satisfied by Y instead of Z", write the
probe so it differs from the real thing in exactly one respect — the one the reviewer
named.** If the probe changes anything else (a name, an indent, a keyword the matcher
anchors on), it is testing your own regex, not the claim.

Report **both directions**: pre-fix survived, post-fix killed. If pre-fix also kills,
say so plainly and skip the change rather than fixing on speculation.

**Corollary: severity labels are the reviewer's hypothesis too.** A bot tagged a
brace-counting bug "🔵 Trivial | 💤 Low value"; measuring it showed a `}` inside a
quoted string truncated the block so a real `count = 1` went unseen — the assertion
passed green against exactly the mutation it existed to catch.

---

## 4. Never declare a limit you have not tested

Do not write "this needs credentials I don't have" or "the tooling can't reach that"
without probing first. Measured: a verification was reported as honest-limited for
lack of credentials when the ambient application-default credentials were valid the
whole time.

Probe the tooling, then state the limit — or state the finding.

Related trap: a CLI that needs interactive reauth **fails with EMPTY output through a
pipe** and exit 0, so a piped read returns empty and reads as "no results" rather than
"not authenticated". Go over REST with an explicit token and **assert HTTP 200**.

---

## 5. Declared facts rot, and nothing tests prose

A repo can state measured infrastructure facts in prose — serial numbers, resource
counts, "X is applied" — and test none of them. One audit over four review rounds
found **21 false statements**, three of which were the stated safety premise for a
destructive action.

Treat any number or state claim in a doc as **untested until a guard pins it**. See
`guard-tests.md` §4 for pinning claims by clause and count.

### 🚨 Citations rot inside their own commit

A `file:line` citation written *during* a change is invalidated **by that same
change**. Line-addressed mutations then land on the wrong line and score a false
pass.

**Address by pattern, never by line number**, in anything that outlives the edit.

---

## 6. A file can vanish from the diff while every gate stays green

A literal NUL byte makes git treat a source file as **binary** — the whole file
disappears from the PR diff, and no check notices.

**Assert `git diff --numstat` shows real line counts** for every file you expect to
be reviewed. A `-` in either column means binary.

---

## Checklist

- [ ] Did I read back the **state**, not the exit code, after every mutation?
- [ ] Did I prove every acceptance grep **matches** something first?
- [ ] Is the claim about the **working tree** or the **index**? (`git grep` = index)
- [ ] After a rename: did I resolve references, not grep for absence?
- [ ] Does my probe differ from the real thing in **exactly one** respect?
- [ ] Did I **test** every limitation before declaring it?
- [ ] Does `git diff --numstat` show line counts for every file in the change?
