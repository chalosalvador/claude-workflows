# OpenSpec: install, use, and what its gate actually proves

**OpenSpec is optional.** These skills work without it. This doc exists because when a
repo *does* use it, the spec-change step sits at a specific point in the flow — before
any code is written — and its validate gate has blind spots that read like coverage.

Detect it: an `openspec/` directory at the repo root, or `workflow.json` →
`"specFlow": "openspec"`. No `openspec/` → skip every step below and say nothing.

---

## The skills do NOT ship OpenSpec skills — and shouldn't

If you have used OpenSpec, you have seen skills named `openspec-propose`,
`openspec-apply-change`, `openspec-archive-change` and so on in your `.claude/skills/`.

**Those are generated artifacts of the `openspec` CLI, not hand-written skills.** Their
frontmatter says so:

```yaml
license: MIT
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.8.0"
```

Vendoring them into this plugin would fork a dependency at a pinned version and be
silently clobbered the next time anyone runs `openspec update`. **Get them from the
CLI instead** — that is the supported path and it keeps them current.

---

## Install

The binary is a **machine-level** dependency. It is deliberately in neither
`requirements.txt` nor `package.json`, and nothing in a repo installs one:

```bash
npm i -g @fission-ai/openspec@1.8.0
```

Pin the version your repo's CI pins. Then, in the repo:

```bash
openspec init
```

That generates the skills and the `openspec/` scaffold for whichever assistants you
select.

⚠️ **Do not fall back to `npx --yes @fission-ai/openspec@… …` inside a skill.** Repos
typically allowlist only `openspec validate *` for npx, so a fallback for `archive` or
`new change` needs more allowlist entries per repo and adds a second code path that
gets exercised approximately never.

⚠️ **Preflight it, don't assume it.** The binary normally resolves under a
version-managed Node prefix, and under the reduced `PATH` of an unattended run it is
simply **not found**:

```sh
command -v openspec && openspec --version
```

Absent → stop, say so, give the install line. For an unattended run that is a handback.

---

## Two repos can be initialized with different command profiles

The generated skills differ by **naming profile** — the compact one emits
`/opsx:propose`, `/opsx:apply`, `/opsx:archive`; the expanded one emits
`/openspec-propose`, `/openspec-apply-change`, `/openspec-archive-change`.

The generated bodies are otherwise identical, so a `diff` between two repos' copies shows
only slash-command names and reads like drift. **It isn't** — nothing has diverged, the
repos were just initialized under different profiles.

To make them consistent:

```bash
openspec config profile
```

then `openspec update` in each repo. Don't hand-edit the generated files.

---

## Where it sits in the issue flow

```
plan  →  create the change directory  →  VALIDATE  →  write code  →  … →  archive (last commit of the PR)
```

**The change directory is created BEFORE any code.** That is the point: it is cheap to
fix a requirement now and expensive once the code exists.

```sh
openspec validate <N>-<slug> --type change --strict     # must exit 0 before implementing
```

**Archive as the last commit of the SAME pull request** — never a post-merge step. A
merge-gated archive never runs at all for a flow that does not merge.

```sh
openspec archive <N>-<slug> -y --json
openspec validate --all --strict          # re-validate the folded tree
```

**Read the JSON, not the exit code.** `specsUpdated` must match the call the plan
made: `true` when there was a delta to fold, `false` under `skip_specs: true`. Exit 0
alone does not distinguish "folded the delta" from "there was nothing to fold" — which
is precisely what a silently-empty delta produces. A missing change name exits 1 with
`"code": "archive_change_not_found"`, so it is safe to gate on.

---

## 🚨 What `openspec validate --all --strict` does NOT assert

Run it, but do not read a green from it as more than it is. Three measured caveats on
1.8.0, each of which has a way of being mistaken for coverage:

1. **It exits 0 on `No items found to validate.`** An empty `openspec/` root is green.
   A fresh worktree or a mis-scoped run puts you back to green-on-nothing. If the gate
   matters to a claim you are making, **confirm it validated something.**

2. **It never reads the archive.** `openspec/changes/archive/**` is outside its scope
   entirely, so a spec folded last month is not re-checked.

3. **`skip_specs: true` switches it off for that change.** The delta is the only thing
   checked on a change, so a change carrying `skip_specs` is not *partially* checked —
   it is **not checked**. Measured: a change directory holding *only* `.openspec.yaml`,
   with `proposal.md` deleted, passes `--all --strict`.

> On a `skip_specs` change the gate asserts nothing, and the justification written
> above the key is a claim a **human** has to check. **Say which case you are in
> rather than reporting a bare green.**

### ⚠️ A green `--strict` does not mean a spec will survive CI

Archiving a delta for a capability with **no spec yet** auto-generates:

```
TBD - created by archiving <change>. Update Purpose after archive.
```

Its length scales with the change name (78 and 91 chars both measured), so it **always
clears `--strict`'s 50-char floor and validates green** — and a repo's own
"every spec has a real purpose" test then **fails it** under a required check.

**Write the `## Purpose` into the delta.** It survives the fold verbatim. That is the
fix.

---

## Authoring rules worth keeping

- **Never invent a capability.** Get the target from an actual `openspec list --specs`
  run in that repo. If the work genuinely needs one that does not exist, say **new
  capability** explicitly and apply the Purpose rule above.
- ⚠️ **Read the spec list from the REMOTE integration branch**, not the working tree:
  `git ls-tree -r <integrationBranch> --name-only openspec/specs/`. A checkout parked
  on someone's feature branch shows an empty `openspec/specs/`, from which the obvious
  wrong conclusion is that the repo has no capability specs at all.
- **Every requirement cites the file and symbol it is grounded in**; every scenario
  traces to a passing test or to code actually read. **Never invent a scenario to
  satisfy the validator.**
- **`skip_specs: true`** is for a pure refactor, tooling, permission or doc change that
  moves no observable capability. It goes in the change's own `.openspec.yaml`, **with
  the reason written above it**, and it is not an archive flag. If you cannot write a
  reason that survives being read by a skeptic, that is a handback, not a `skip_specs`.
- **A `MODIFIED` delta replaces its requirement wholesale.** So on a rebase, **do not
  hand-resolve** a folded spec — a hand-merge can silently drop a requirement another
  PR just folded in, and `validate --all --strict` is green over the loss.

### Regenerating an archive on rebase

```sh
git reset --hard HEAD~1        # drop the archive commit; the change dir returns
git rebase <integrationBranch> # resolve only real code conflicts
openspec archive <name> -y --json   # assert specsUpdated: true
```

Then **verify the fold by counting and by name**: requirement/scenario counts
before→after, `diff | grep -c "^<"` equals only your intended edits, and grep the other
PR's scenario titles individually to prove they survived.
