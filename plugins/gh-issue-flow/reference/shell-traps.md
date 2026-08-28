# Shell traps that pass lint and a green suite

Every item here was measured, and every one produced a *plausible* wrong answer
rather than an error.

---

## The agent's shell is zsh, and zsh does not word-split

An unquoted parameter expansion holding a space-separated list expands to a **single
argument**:

```sh
T="tests/a.py tests/b.py"
pytest $T          # zsh: ONE arg "tests/a.py tests/b.py" -> "no tests ran"
```

This fails *silently plausible*. `pytest` reported "no tests ran in 0.00s" and a
grep-filtered mutation loop printed nothing for three mutations in a row — which
reads exactly like "no test failed", i.e. like the mutations survived. Three false
mutation results, nearly recorded.

**Use an array** (`T=(a.py b.py); pytest "${T[@]}"`), write the words literally, or
`${=T}` for explicit zsh splitting. In any loop whose output is *evidence*, print a
positive baseline first so "no output" can never be mistaken for "no failures".

### 🚨 The same trap pollutes a repo through `gh api .../labels`

`POST /repos/{o}/{r}/issues/{n}/labels` **auto-creates any label that does not
exist** — it does not 422. So:

```sh
for l in ${VAR}; do gh api … -f "labels[]=$l"; done   # VAR="improvement effort:hard"
```

doesn't split, sends ONE label `"improvement effort:hard"`, and GitHub silently
**creates that junk label repo-wide**. Exit 0, response looks fine. Measured: 4 junk
labels born across 5 issues during one triage run.

Pass each label as its own explicit `-f "labels[]=…"`. To repair:
`gh api -X DELETE "repos/{o}/{r}/labels/<name%20enc>"` removes it from every issue at
once. **After any label-add loop, read the labels back and assert none contain a
space.**

### ⚠️ zsh applies HISTORY MODIFIERS to `$VAR:x`

`$SA:getIamPolicy` does **not** expand to `<sa>:getIamPolicy`. zsh reads `:g` / `:e`
as parameter modifiers, so a Google API URL built that way produced

```
.../serviceAccounts/comtIamPolicy      # `:e` took the "extension" of the email
```

and the request 404'd against a URL that never contained the service account.

**Never leave a literal `:` directly after `$VAR`.** Build the whole URL in one
quoted variable: `URL="https://…/${SA}:getIamPolicy"`. The failure mode is a
*plausible* 404, not a syntax error — it reads as "the resource does not exist"
rather than "your shell rewrote the string".

---

## `IFS=$'\t' read -r a b c` cannot parse a row with an empty MIDDLE column

TAB is an **IFS whitespace** character, so a run of tabs collapses into ONE delimiter
and an empty middle field vanishes — every later column shifts left.

Measured against a real `gcloud --format='value(...)'` row: a firewall rule with no
target tags but a target service account parsed the SA into the `tags` variable,
silently inverting the check that read it.

A **trailing** empty column is harmless (the variable is just empty), which is why
this survives casual review.

```sh
_next_field() {           # sets FIELD and REST
  case "$1" in
    *$'\t'*) FIELD="${1%%$'\t'*}"; REST="${1#*$'\t'}" ;;
    *)       FIELD="$1";           REST="" ;;
  esac
}
```

Make the remainder **empty** when no delimiter is left, or a short row makes the last
two columns alias each other.

> When a guard reads columns positionally out of any tool's tabular output, **assert
> the projection and its column order too.** A stub that ignores `--format` makes a
> projection change render the guard *wrong rather than absent*, and every behavioural
> test stays green.

---

## `export VAR="$(cmd)"` DISCARDS cmd's exit status

`export` is a command; the substitution's status is thrown away, so `set -e` never
fires (SC2155). Measured: a failed secret fetch left a startup script exiting **0**,
and the service started with an empty credential and restart-looped on billed
hardware.

⚠️ **shellcheck cannot see it when the line is RENDERED into a generated script**
rather than executed in place.

```sh
VAR="$(cmd)"
export VAR
```

Two lines. This also keeps the value off any later `-e VAR=...` argv.

---

## `grep "\t"` is BSD-only

BSD grep interprets `\t`; **GNU grep matches a literal `t`**. A test stub using
`grep -v "^name\t"` was green on macOS and RED on `ubuntu-latest`. Use a literal tab
character.

---

## `until pgrep -f "<pat>"` hangs forever

The agent harness wraps the script into `zsh -c '<whole script>'`, so the waiting
shell's own command line contains the pattern and `pgrep -f` — which matches full
command lines — **matches itself**. The job spins until killed.

Match on something the script cannot contain: a pid captured earlier
(`while ps -p "$PID" >/dev/null`), a lock file, or `pgrep -f "[p]attern"` with a
bracket class. Better: background each step and let the harness notify on completion
instead of hand-rolling a waiter.

---

## Batch-edit scripts: two failure modes that look like success

### 1. Assert mid-loop + one `write_text` at the end = nothing persists

```python
for anchor, value in items:
    assert s.count(anchor) == 1, (value, s.count(anchor))
    s = s.replace(anchor, ...)
    print(f"applied {value}")     # <-- lies
p.write_text(s)                   # <-- never reached
```

If item 5 fails its assertion, items 1–4 printed "applied" and **were not written**.
Measured: four call sites reported applied, the file had none of them, and the next
run failed with `$7: unbound variable` from `set -u` — which looked like a *different*
bug in the code just written.

**`write_text` inside the loop** after each edit, so partial progress is real and the
printout matches the file. Verify with a `grep -c` of the expected result, never by
trusting the prints.

### 2. A blanket replace hits sites that were already correct

Twice in one session:

- Fixing one wrong citation replaced *every* mention of a path in a file. One of them
  legitimately pointed there. Caught only because `git diff` showed **two**
  replacements where one was expected.
- Repairing over-escaped backticks matched **22** occurrences when 3 were mine; the
  other 19 were pre-existing correct heredoc escaping, and shellcheck went red across
  untouched code.

**Count first (`s.count(old)`) and assert the expected number, not `>= 1`.** After any
multi-site replace, read `git diff` for that file before moving on. When the count
surprises you, narrow the anchor — do not accept the surprise.

---

## Scripts that hold a temporary credential

Six defects found by review in one hand-run grant script, all in the *lifetime* of a
temporary role grant, none visible in a static read. Generic to any "take a
credential, do a thing, give it back" script:

- **A piped read conflates "read failed" with "nothing found".**
  `gcloud … get-iam-policy … | grep -qx "$ME"` produces no match in both cases, so an
  unreadable policy takes the *no binding* branch → blind grant → cleanup revokes
  access that predated the run. ⚠️ Made **twice in one file**, the second time inside
  the branch added to fix the first. Capture output and `$?` **separately**; treat
  unknown as a stop, not a guess.
- **Arm the cleanup BEFORE the call that creates the grant.** `add-iam-policy-binding`
  is a multi-second round trip and the API can apply the binding before the CLI
  returns; a flag set *after* means Ctrl-C strands it. The flag means "this run MAY
  have created it".
- **Consequence: cleanup must confirm before alarming.** Arming early sends every
  failed add through cleanup, so an unconditional 🚨 fires when nothing is wrong — and
  an alarm that cries wolf is one the operator scrolls past. Three outcomes:
  removed / still there / cannot confirm.
- **`add-iam-policy-binding` is IDEMPOTENT**, so add-then-remove silently revokes a
  binding the operator already had. Only remove what this run created.
- **Tokens on argv are readable via `ps` by any user on the box.** Both
  `-d "access_token=$T"` and `-H "Authorization: Bearer $T"` count. Use
  `curl --data @-` and `curl --config -` (stdin). ⚠️ Review flagged one; the other was
  in the polling loop, 40× per run.
- **`trap cleanup EXIT INT TERM` RESUMES after a signal** — the handler runs,
  execution continues, then it fires again on EXIT. Use `trap cleanup EXIT` plus
  `trap 'exit 130' INT` / `trap 'exit 143' TERM`.

> ⚠️ `gcloud config get-value account` is **not** the identity that impersonates — ADC
> is, and the two stores are independent.

**Prose cannot hold this invariant.** The first version of the procedure was a comment
saying *"put the removal in a `trap`, not a final line"* directly above commands with
the removal as a final line. **Ship it as an executable script, not a runbook
paragraph**, and test it with the CLIs stubbed on PATH, asserting the calls it
actually made.
