# Mutation harnesses: 20 ways yours reports a false result

Mutation-proving a test means: break the code, confirm the test reds. **A run that
reports "passed" is ambiguous** — it means either the guard is vacuous *or the
mutation never happened.* Everything below was measured on a real harness that
reported a wrong number.

The headline rule: **after mutating and before running the suite, print evidence
the mutation landed** — a `grep -c` of the changed token, a step count, a diff
line. Treat a non-kill as *unverified* until the mutation is proven present.

---

## The mutation never landed

1. **`git archive HEAD | tar -x` copies the COMMITTED tree.** Uncommitted fixes are
   absent, so the harness measures old code. Four mutations "survived" that
   actually kill. Use `rsync -a --exclude .venv --exclude .git ./ "$COPY"/`, or
   commit first.

2. **The interpreter lacks the library.** A mutation script rewriting a workflow
   via `yaml` under the *system* `python3` dies with `ModuleNotFoundError`, the
   file is untouched, and the suite reports a clean baseline. Use the project venv's
   interpreter for the mutation script too, not just for the tests.

3. **BSD `sed`'s `0,/re/` address silently no-ops.**
   `sed -i '' '0,/version = "~> 7.42"/s//…/' file` applies on GNU sed and does
   **nothing** on macOS — no error, exit 0. Caught only because the harness printed
   a `grep -c` that read `1` instead of `2`. **Use the venv Python with
   `assert old in text` / `assert new in text` around the replace instead of `sed`.**

4. **`perl -0pi -e 's{...}{...}'` without `/g` replaces the FIRST occurrence** —
   which in a well-commented file is the **comment**. Two mutations mutated prose,
   the code was untouched, both printed SURVIVED. Anchor on the full code line and
   grep for the mutated **code**, not the token.

5. **`perl` interpolates `${...}` and backticks in the replacement.** Mutating
   minified JS containing a template literal died with
   `Undefined subroutine &main::toLowerCase`. Use a `node -e` byte replacement with
   `assert before.includes(from)` and `assert after.includes(to)` whenever the
   target contains `$`, backticks or braces.

6. **A shell-quoted `\n` writes a literal backslash-n** into a `.py`, so the suite
   reports `1 error` at collection — which is not the guard firing either.

7. **A loose anchor produces a `SyntaxError`, and every guard then ERRORS.**
   `def publish_event(` matched inside `async def publish_event(`, splitting the
   `async` binding; all five guards errored at collection, which at a glance is
   indistinguishable from five guards that did not fire. **`ast.parse` the mutant
   before scoring it**, and prefer anchors that cannot be a substring of a longer
   declaration.

8. **A stale `.pyc` replays the unmutated module.** CPython invalidates a cached
   `.pyc` on **mtime-seconds + source size**, so a mutate → run → restore cycle
   completing inside one wall-clock second replays the stale module — and a
   same-byte-length mutation (an argument swap!) is exactly the case that hits it.
   Add `find <tree> -name __pycache__ -type d -exec rm -rf {} +` between rounds.

9. **The sweep reads the git INDEX, so a mutation that CREATES a file is
   invisible.** Three cases reported SURVIVED against a guard derived from
   `git ls-files`; the files were untracked. `git add -N` made all three kill
   immediately. ⚠️ **Whenever the code under test enumerates via git rather than the
   filesystem, a create-a-file mutation must be staged** — and that is also the
   state a real PR is in, so the staged run is the meaningful one.

10. **A mutation goes stale against restructured code.** Two trap-ordering
    mutations inserted a trap right after `GRANTED=1`; a later fix moved `GRANTED=1`
    *above* the call it guarded, so the mutation now placed the trap **before** the
    only dangerous call — it stopped expressing a defect and the guard passed
    *correctly*. ⚠️ **A survival is a claim about the mutation as much as the test:
    re-read what the mutated file now says before believing it.** Re-anchor on a
    semantic boundary, not a neighbouring line that can move.

11. **An anchor matching zero times never applied.** Refuse any anchor that matches
    ≠ 1 times.

---

## The mutation landed but the score is wrong

12. **Scoring "exit code != 0" as a clean kill.** A renderer **panic** (exit 11) and
    an `Invalid function argument` error also exit non-zero while printing none of
    the authored message. Two assertions were reported "4/4 measured kills" when
    they actually *crashed the process* on the regression they guarded.
    **Classify the outcome — panic / other-error / assertion-failure — not the exit
    code.** Count runs SKIPPED separately: a kill that skips the rest of the file is
    a half guard.

13. **An INVALID mutation is not a quiet guard.** `condition = true` is rejected by
    Terraform in both variable validations and resource preconditions, so eight
    guard-deletion mutations produced a *config error* instead of a neutered guard —
    and the harness called all eight survivors. Grep for
    `Invalid validation expression` / `Invalid precondition expression` and score
    that as MUTATION INVALID, not survival.

14. **Comparing against the wrong stream.** `terraform test` prints the run summary
    on **stdout** and the failing assertion's message on **stderr**.
    `capture_output=True` then `.stdout` sees `1 failed` and none of the message.
    Merge: `stdout=subprocess.PIPE, stderr=subprocess.STDOUT`.

15. **Output is wrapped and coloured.** Terraform wraps `error_message` across
    box-drawing lines (`│`, ANSI SGR) *and* hard-wraps at ~80 columns, so a raw
    `expect in out` never matches an authored sentence. Normalize **both sides**:
    strip `\x1b\[[0-9;]*m`, strip `│╵╷├`, then `" ".join(s.split())`.

16. **Counting `failed` but not `error`.** A mutation that breaks YAML parsing makes
    tests **error** at collection/fixture time, so a counter keyed on "failed" reads
    `0` and prints SURVIVED for two mutations that each killed 10. The tell was
    visible in the same line — `0 failed (48/58)`, ten tests unaccounted for.
    **If killed + passed ≠ baseline, the reading is invalid, not a survival.**
    Parse the last summary line, and count `failed` **plus** `error`.

17. **`pytest -rf` reports FAILED only.** A test whose *fixture* raises is reported
    **ERROR**. A mutation breaking a fixture returns an empty failing-set from a
    `^FAILED` regex — indistinguishable from green, and fatal for any
    must-stay-green case whose expectation is literally `set()`. **Use `-rfE` and
    parse `^(?:FAILED|ERROR)`.**

18. **A guard keyed on the string `"ERROR"` cannot detect a collection failure.**
    Under `-q --no-header --tb=no`, pytest prints
    `!!! Interrupted: 1 error during collection !!!` — **no uppercase ERROR
    anywhere**, so `if "ERROR" in out:` is dead code. **Key on the return code**
    (2=interrupted, 3=internal, 4=usage, 5=no-tests-collected) *and* require a
    `\d+ (passed|failed)` line before trusting an empty failing-set.
    ⚠️ #17 and #18 compound: a guard file that fails to import gives exit 2 and no
    FAILED lines — reported as "baseline green", and every later case is meaningless.

19. **`\S+` truncates a parametrized id containing a space.**
    `test_x[   -staging]` and `test_x[   -prod]` both became `test_x[` and deduped to
    one. Reported "killed 1 test"; it killed 2. Whitespace-only parametrize values
    are common in *emptiness* guards — precisely the tests most likely to need
    per-case scoring.

20. **The test reporter differs by runtime version.** Node 24 defaults to the `spec`
    reporter (`ℹ tests 21` / `✖ name`), Node 22 to TAP (`# tests 21` /
    `not ok 1 - name`). A harness parsing only `^# tests` finds nothing on Node 24,
    reports `ran=False`, and announces a **failing baseline over a fully green
    suite**. Parse both:

    ```python
    total  = re.search(r"^(?:#|ℹ) tests (\d+)$", out, re.M)
    failed = re.search(r"^(?:#|ℹ) fail (\d+)$", out, re.M)
    names  = re.findall(r"^not ok \d+ - (.+)$", out, re.M) or \
             [m.group(1) for m in re.finditer(r"^✖ (.+?) \(", out, re.M)]
    ```

---

## The environment fabricates failures

- **A reduced `PATH` in `env=` breaks tests that shell out.** Running the suite from
  `subprocess.run(..., env={"PATH": "/usr/bin:/bin"})` failed a test that invokes a
  script and skipped another. Invisible while the harness ran a module subset, then
  looked like a second kill on the first full-suite run.
- **Extend `os.environ`, never replace it.** Dropping `HOME` and the rest makes the
  runtime fail to start, and the harness again reports a failing baseline rather
  than its own breakage.
- **Re-run the UNMUTATED tree under the identical env before attributing any failure
  to the mutation.**

> 🚨 **A control that is not green is a broken harness, not a fact about the code.**
> Two successive harnesses reconstructed a pre-change tree whose control reported
> failures, and the instinct was to *explain* them. Both failures were
> self-inflicted — the harness had moved tracked files aside. **Fix the control
> until it is green before interpreting anything downstream of it.** A published
> measurement with an unexplained failure teaches the reader to distrust the rest.

---

## The fixture cannot express the failure

A fake-CLI stub logged the fixed label `"curl tokeninfo"` instead of `"curl $*"`, so
a test asserting *"the token never appears in a recorded argument list"* scanned a
recording that could never contain a token — while its own docstring claimed the log
was "exactly the view `ps` would give". Changing the stub to log `$*` immediately
redded it, and exposed a **second** un-flagged instance of the same bug.

Relatedly, a stateless stub whose `get-iam-policy` always reported "no binding" made
a successful add and a failed add indistinguishable — the exact thing the code under
test had to tell apart — so two tests passed for the wrong reason.

**Prove the harness can observe the failure (log real args; model state) before
trusting a green. A docstring asserting fidelity is not fidelity.**

---

## Crash safety and cleanup

- **A harness killed mid-run LEAVES A MUTATION APPLIED.** Run it backgrounded,
  repair the line explicitly, and assert the restore succeeded.
- **Never restore with `git checkout`.** A `restore()` running
  `git checkout -- <paths>` **silently reverted uncommitted corrections** made
  between two runs. Commit before every re-run, or scope `restore()` to the exact
  files the harness mutates.
- **Derive mutated text from the live file at run time, never embed a copy.** An
  embedded copy silently degrades to `HARNESS-BUG` on the first reword — honest, but
  a harness needing hand-repair after every edit stops being re-run.
- **Parallel agents share the working tree and the scratchpad.** A review lens once
  overwrote a mutation harness mid-session and the re-run printed nothing and exited
  0. Namespace scratch files per agent; commit before spawning.

---

## 🚨 The meta-lesson

One harness reported **16/16 killed**. An independent reviewer then found **16
SURVIVING mutations** against the same file — including one that let the entire
guarded feature be deleted with a green suite.

> **N/N killed is evidence about the mutation LIST, never about the file.**

Quote it as "16 of my 16", and treat an independent adversarial pass over the test
file as a separate, required step.

**Ask for the right thing.** Another 6/6-killed harness was undone by a reviewer
prompt phrased as *"find a mutation that makes this guard **wrong**, not one that
removes it"* — it found one that survived the entire suite (passing the raw env
instead of the normalized one, because every case spelled the env canonically).
**Deletion mutations are the ones you think of unaided.**

## ⚠️ Expectations that are RIGHT but INCOMPLETE are the common failure

Across three harness rounds — 6/16, then 3/22 mismatches — **every single one was an
omission, never a wrong prediction**: a test the author did not realize also reds.
Two recurring shapes: adding a count literal means every mutation that narrows the
matcher now reds *that* too; and widening a matcher drags previously unmatched real
lines into the sweep.

When you add an arm, **re-derive the expectations of every existing case.** And when
correcting an expectation, write the STRUCTURAL MECHANISM ("a `⊆` check survives its
left side shrinking"), never "that is what was observed". **A re-fitted expectation
dressed in a plausible mechanism is worse than a red harness** — worth asking a
reviewer to audit your mechanisms explicitly.
