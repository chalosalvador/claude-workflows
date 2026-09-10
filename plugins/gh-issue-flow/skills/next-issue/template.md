# Start-prompt template

The generated prompt is **prose with labelled blocks**, in this exact order. Keep it
portable: repo-relative paths and the current GitHub user — never absolute machine
paths or hardcoded logins.

---

## Worked example

Mirror this structure, level of specificity, and tone. Only the content changes. `#N` is
the issue being started; `#M` and `#P` stand for an earlier issue and its PR.

```
Implement GitHub issue #N in the acme-api repo: "Carry the order note through the
event envelope into the reporting store".
https://github.com/acme/acme-api/issues/N

Repo: acme-api/ (run from the repo root; it is its own git root). Use the .venv
there. git fetch, then branch off origin/dev — the integration branch, NOT main.

CONTEXT: Direct follow-up to #M (merged, PR #P), which added a free-text `note`
to cancelled-order events on the primary-database path. Today the event envelope
drops `note`, so once a customer is switched to the reporting feed,
GET /api/orders?kind=cancelled returns `note: null` — a silent regression. This
issue carries `note` end-to-end so both stores return IDENTICAL values. Refund
events are unaffected.

DECIDE FIRST: Confirm product wants note parity in production. Given #M exists
specifically to feed the cancellation-reason report, the answer is almost certainly
YES — but post a short comment on #N stating the decision + plan, and proceed with
"carry it through" unless told otherwise.

SCOPE:
- Envelope: add a nullable string `note` to the cancelled-order event in
  api/events.py (build_order_event) + the publisher path.
- Reporting store: migration adding a nullable `note` column, mirroring the existing
  `reason` column exactly — migrations/0042_order_note.sql.
- Read path: surface it in the orders query, matching the primary store's shape.
- NOT changing: refund events, the primary write path (#M already did it).

SPEC: change `N-order-note-reporting`, capability `order-feed` (confirmed via
`openspec list --specs`). Delta, not skip_specs.
  ## MODIFIED Requirements
  ### Requirement: The order feed SHALL return an identical note on both stores
  Grounded in api/events.py:build_order_event and api/orders.py:query_orders.
  #### Scenario: A cancelled order is read back from the reporting store
  WHEN a cancelled-order event with a non-null note is published
  THEN GET /api/orders?kind=cancelled returns the same note as the primary store
Gate: `openspec validate N-order-note-reporting --type change --strict` exits 0
BEFORE any implementation.

VERIFY-FIRST: read api/events.py (build_order_event — confirm note is dropped
today, not merely unused), api/orders.py (the read path's column list), and
migrations/0041_order_reason.sql (the `reason` column is the precedent to mirror).
The primary-store writer in api/store.py must stay UNCHANGED — #M owns it.

TESTS: parity test asserting the two stores return byte-identical notes for the
same event. Mirror tests/test_order_parity.py. Mutation-check it: drop `note` from
the envelope and confirm the test reds — state the result in the PR body.

VALIDATE (verbatim, from the repo's gate):
  command -v openspec && openspec --version
  .venv/bin/python -m pytest tests/ -q
  .venv/bin/ruff check api/ tests/
  .venv/bin/python -m migrations check   # only because migrations/ changed
  openspec validate --all --strict
  That last one exits 0 on an empty root, never reads the archive, and is
  switched off entirely by skip_specs — do not report a bare green from it.

PROCESS:
Plugin docs: `ls -d ~/.claude/plugins/cache/claude-workflows/gh-issue-flow/*/ | sort -V |
tail -1`. Pass that directory as `Plugin: <dir>` to every planner and reviewer you spawn.
1. Post the scoping plan as a comment on #N first; set the board card to In
   Progress. Then branch, then create the SPEC block's change directory and get its
   validate to exit 0 BEFORE writing code.
2. Review with parallel gh-issue-flow:diff-reviewer subagents (effort: max, fresh
   context — spawn the NAMESPACED name), one per lens: `correctness` (the note can
   be absent, null, or huge); `contract` (the envelope is consumed by the reporting
   reader — a shape change is two coordinated PRs); `tests` (parity across two
   stores); `deploy` (additive nullable column; the migration runs in the staging
   deploy, so it IS in the CD path); `comments` (the migration and the parity test
   add comments). Skip `scoping` — this adds no guard, and every caller of the
   writer is in the diff. Skip `safety` — no new account-scoped query and no
   credential moves. Commit before spawning them. Fix every valid finding; explain
   any rejected in the PR body's History.
2b. If those fixes added NEW LOGIC — a branch, gate, condition, or code path — one
   more gh-issue-flow:diff-reviewer over just that delta, run as the lens that raised
   the finding. Once, not a loop. Skip for test/comment/doc-only fixes.
2c. `openspec archive N-order-note-reporting -y --json` as the LAST commit of
   this PR — never post-merge. Assert specsUpdated: true, then re-validate the
   folded tree.
3. Branch feat/N-order-note-reporting; commit referencing "Fixes #N". Every
   commit GPG-signed — if signing fails, stop. Never commit secrets.
4. Open a PR whose body follows reference/git-and-github.md § Writing a PR body
   in that plugin directory; history goes in its History section, never in code or
   docs. Then drive CI + review-bot threads to green: reply, verify the reply
   posted, THEN resolve. Watch review THREADS as well as checks — a bot posts as a
   thread, so a checks-only poll never sees it. Do not assume a babysit skill
   exists; do the loop inline. Re-check 0 unresolved threads at the merge instant.
   Do NOT merge without my go-ahead.
5. Board tracking: resolve the #N card's item id by querying the project for
   issue N in acme-api, then set Status → In Progress on start, Done only at
   merge. Resolve field and option ids from `gh project field-list` in the same
   run — never hardcode them. Keep the existing assignee, or assign yourself if
   unassigned.

DEPLOY NOTE: includes a schema migration (additive, nullable; no customer is routed
to the reporting feed yet). Merging to `dev` DOES auto-deploy staging and run its
migrations, so this ships to shared staging on merge. The reporting store's view
definition is refreshed by a separate manual job that this workflow does not run:
ask before running it.
```

---

## Section skeleton

- **Header + URL** — `Implement GitHub issue #<N> in the <repo> repo: "<exact title>".`
  then the issue URL.
- **Repo** — repo dir (relative), runtime/toolchain, and `git fetch, then branch off
  <integrationBranch>`. Resolve the branch per
  [`shared/config.md`](../../shared/config.md); **never assume `main`.** No absolute
  machine paths.
- **CONTEXT** — why now: the regression or gap, the follow-up-to relationship (cite the
  prior issue/PR), what stays unaffected. Honest and specific.
- **DECIDE FIRST** — the one product/scope call to confirm; instruct to post the
  decision + plan as a comment and proceed with the likely default unless told
  otherwise. Omit only if the issue is purely mechanical.
- **SCOPE** — bullets of concrete changes, each naming the file/symbol and the
  precedent to follow. **Include what is explicitly NOT changing.**
- **SPEC** — only when the repo has a spec flow. Taken from the plan's SPEC IMPACT:
  change name `<N>-<slug>` (same slug as the branch), the target capability **from a
  real `openspec list --specs` run, never invented**, or `skip_specs: true` with the
  justification prose that goes above the key. For a delta, the requirement and
  scenario headers. For a **new** capability, the authored `## Purpose` (50+ chars) to
  write **into the delta**. See
  [`../../reference/openspec.md`](../../reference/openspec.md) for why that Purpose
  rule is load-bearing.
- **VERIFY-FIRST** — the reading list that proves "what changes vs. what already
  exists". Name real files and symbols. Call out anything that must stay UNCHANGED.
- **TESTS** — the assertion that proves the fix; hermetic; mirrors an existing test.
  **Include the mutation to run and require the result in the PR body.** If the change
  adds a guard or invariant test, point at
  [`../../reference/guard-tests.md`](../../reference/guard-tests.md).
- **VALIDATE** — the exact commands for this repo, **verbatim** from the resolved
  config ([`shared/execution.md`](../../shared/execution.md) § 2). Never retype from
  memory. Include the
  preflight, and carry the caveats on what a spec validate does **not** assert so the
  fresh session does not read a green as proof.
- **PROCESS** — the plugin-docs line, then the numbered steps as in the example: scoping comment → branch → spec
  change before code → **named** review lenses from the plan, never the generic list
  ([the set](../../agents/diff-reviewer.md#the-lenses)) → conditional delta re-review →
  archive as the last commit → commit → PR with the body
  [`git-and-github.md` § Writing a PR body](../../reference/git-and-github.md#writing-a-pr-body)
  gives → babysit threads *and* checks → board tracking.
- **DEPLOY NOTE** — schema/infra/deploy caveats. State plainly whether merging the
  integration branch deploys. If you claim a diff does **not** deploy, derive that from
  the live `paths-ignore` against **every** changed path — it is all-or-nothing per
  push, `tests/**` and `.github/workflows/**` are commonly not ignored, and "not baked
  into the image" does not mean "does not trigger". Say the claim must be
  **re-checked against the final diff** after review fixes land — that is what has
  actually made it wrong. Rules:
  [`shared/execution.md`](../../shared/execution.md) § 7.
