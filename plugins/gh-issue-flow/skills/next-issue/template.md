# Start-prompt template

The generated prompt is **prose with labelled blocks**, in this exact order. Keep it
portable: repo-relative paths and the current GitHub user — never absolute machine
paths or hardcoded logins.

---

## Worked example

Mirror this structure, level of specificity, and tone. Only the content changes.

```
Implement GitHub issue #412 in the acme-api repo: "Carry the audit payload through
the canonical envelope into the analytics feed".
https://github.com/acme/acme-api/issues/412

Repo: acme-api/ (run from the repo root; it is its own git root). Use the .venv
there. git fetch, then branch off origin/dev — the integration branch, NOT main.

CONTEXT: Direct follow-up to #399 (merged, PR #401), which populated a structured
before/after `payload` on admin-action audit events on the Postgres path. Today the
canonical envelope drops `payload`, so once a tenant cuts over to the analytics
feed, GET /api/audit?kind=admin_action returns `payload: null` — a silent
regression. This issue carries `payload` end-to-end so both paths return IDENTICAL
payloads. Decision-event payloads are unaffected.

DECIDE FIRST: Confirm product wants payload parity in production. Given #399 exists
specifically to feed the before/after diff rendering, the answer is almost
certainly YES — but post a short comment on #412 stating the decision + plan, and
proceed with "carry it through" unless told otherwise.

SCOPE:
- Envelope: add a nullable generic-JSON `payload` to the canonical admin_action
  event in api/events.py (build_admin_action_event) + the publisher path.
- Analytics landing schema + view: add { name="payload", type="JSON",
  mode="NULLABLE" }, mirroring the existing `metadata` column exactly.
- Read path: surface it in the audit query, matching the Postgres shape.
- NOT changing: decision events, the Postgres write path (#399 already did it).

SPEC: change `412-audit-payload-analytics`, capability `audit-feed` (confirmed via
`openspec list --specs`). Delta, not skip_specs.
  ## MODIFIED Requirements
  ### Requirement: The audit feed SHALL return an identical payload on both stores
  Grounded in api/events.py:build_admin_action_event and api/audit.py:query_audit.
  #### Scenario: An admin action is read back from the analytics store
  WHEN an admin_action event with a non-null payload is published
  THEN GET /api/audit?kind=admin_action returns the same payload as Postgres
Gate: `openspec validate 412-audit-payload-analytics --type change --strict` exits
0 BEFORE any implementation.

VERIFY-FIRST: read api/events.py (build_admin_action_event — confirm payload is
dropped today, not merely unused), api/audit.py (the read path's column list), and
infra/analytics/schema.tf (the `metadata` column is the precedent to mirror). The
Postgres writer in api/store.py must stay UNCHANGED — #399 owns it.

TESTS: parity test asserting the two stores return byte-identical payloads for the
same event. Mirror tests/test_audit_parity.py. Mutation-check it: drop `payload`
from the envelope and confirm the test reds — state the result in the PR body.

VALIDATE (verbatim, from the repo's gate):
  command -v openspec && openspec --version
  .venv/bin/python -m pytest tests/ -q
  .venv/bin/ruff check api/ tests/
  terraform fmt -check          # only because .tf changed
  openspec validate --all --strict
  ⚠️ That last one exits 0 on an empty root, never reads the archive, and is
  switched off entirely by skip_specs — do not report a bare green from it.

PROCESS:
1. Post the scoping plan as a comment on #412 first; set the board card to In
   Progress. Then branch, then create the SPEC block's change directory and get its
   validate to exit 0 BEFORE writing code.
2. Review with parallel diff-reviewer subagents (effort: max, fresh context), one
   per lens: `correctness` (the payload can be absent, null, or huge); `contract`
   (the envelope is consumed by the analytics reader — a shape change is two
   coordinated PRs); `tests` (parity across two stores); `deploy` (additive
   nullable column; infra is NOT in the CD workflow). Skip `scoping` — this adds no
   new tenant-scoped query. Commit before spawning them. Fix every valid finding;
   explain any rejected in the PR body.
2b. If those fixes added NEW LOGIC — a branch, gate, condition, or code path — one
   more diff-reviewer on `correctness` over just that delta. Once, not a loop.
   Skip for test/comment/doc-only fixes.
2c. `openspec archive 412-audit-payload-analytics -y --json` as the LAST commit of
   this PR — never post-merge. Assert specsUpdated: true, then re-validate the
   folded tree.
3. Branch feat/412-audit-payload-analytics; commit referencing "Fixes #412". Every
   commit GPG-signed — if signing fails, stop. Never commit secrets.
4. Open a PR, then drive CI + review-bot threads to green: reply, verify the reply
   posted, THEN resolve. Watch review THREADS as well as checks — a bot posts as a
   thread, so a checks-only poll never sees it. Do not assume a babysit skill
   exists; do the loop inline. Re-check 0 unresolved threads at the merge instant.
   Do NOT merge without my go-ahead.
5. Board tracking: resolve the #412 card's item id by querying the project for
   issue 412 in acme-api, then set Status → In Progress on start, Done only at
   merge. Resolve field and option ids from `gh project field-list` in the same
   run — never hardcode them. Keep the existing assignee, or assign yourself if
   unassigned.

DEPLOY NOTE: includes an analytics schema change (additive, nullable, no tenant
provisioned yet). Merging to `dev` DOES auto-deploy staging and run its migrations,
so this ships to shared staging on merge. The infra change is NOT covered by that
workflow: ask before applying it.
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
  memory — the versions in the original of this file were wrong for weeks. Include the
  preflight, and carry the caveats on what a spec validate does **not** assert so the
  fresh session does not read a green as proof.
- **PROCESS** — the numbered steps as in the example: scoping comment → branch → spec
  change before code → **named** review lenses from the plan (never the generic five)
  → conditional delta re-review → archive as the last commit → commit → PR → babysit
  threads *and* checks → board tracking.
- **DEPLOY NOTE** — schema/infra/deploy caveats. State plainly whether merging the
  integration branch deploys. If you claim a diff does **not** deploy, derive that from
  the live `paths-ignore` against **every** changed path — it is all-or-nothing per
  push, `tests/**` and `.github/workflows/**` are commonly not ignored, and "not baked
  into the image" does not mean "does not trigger". Say the claim must be
  **re-checked against the final diff** after review fixes land — that is what has
  actually made it wrong. Rules:
  [`shared/execution.md`](../../shared/execution.md) § 7.
