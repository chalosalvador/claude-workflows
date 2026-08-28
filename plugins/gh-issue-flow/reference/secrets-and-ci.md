# Secrets, environments and CI skew

The theme: **a value that is wrong by one byte, or read through a broken pipe, is
indistinguishable from a value that is right.**

---

## 🚨 Piping a generated secret stores the TRAILING NEWLINE

```bash
openssl rand -hex 32 | gcloud secrets versions add NAME --data-file=-
```

stores **65 bytes ending `0a`** instead of 64. Cloud Run injects a secret payload
**verbatim** into the env var, so the service holds `…\n` while every client holds the
value without it.

For an HMAC signing secret that is a byte mismatch ⇒ **401 on every request**, and
nothing in any log says why — the verifier cannot distinguish a wrong secret from a
forged signature.

```bash
openssl rand -hex 32 | tr -d '\n' | gcloud secrets versions add NAME --data-file=-

# verify BOTH, not just length:
gcloud secrets versions access latest --secret=NAME | wc -c              # want 64, not 65
gcloud secrets versions access latest --secret=NAME | tail -c 1 | xxd -p # want NOT 0a
```

**Fix a bad version by adding a corrected one and DISABLING — never destroying — the
old one:** `gcloud secrets versions disable 1 --secret=NAME`. `latest` then resolves to
the newest *enabled* version.

**Compare two secrets without printing either:** pipe each through `shasum -a 256` and
compare digests.

> Whenever one secret must match across two systems, **verify by byte-comparing the two
> sides**, not by re-reading one of them.

---

## `vercel env add` silently sets EMPTY, and stores unverifiably

Two silent failure modes, each of which creates a **production variable with an empty
string** and reports success-ish:

1. **`printf 'val' | vercel env add NAME production` does NOT set the value.** The var
   is created **EMPTY**. The CLI just prints its "Common next commands" help; there is
   no error. (Docs and older guides say it reads stdin — don't trust it.)
2. **It defaults to `Type: Sensitive`**, which is **write-only**: `vercel env pull` then
   returns `NAME=""` even when the value IS set. **A sensitive var is indistinguishable
   from an empty one on readback** — you cannot verify it.

⚠️ `--no-sensitive` no longer exists on current CLI versions; `--help` lists only
`--sensitive` (opt-in) — yet a plain `--value` add still lands as `type=sensitive`.
`--value` itself works; only the storage type is wrong.

**The reliable route is the REST API, which takes an explicit `type` and reports it
back:**

```bash
TOK=$(jq -r .token "$HOME/Library/Application Support/com.vercel.cli/auth.json")
PROJ=$(jq -r .projectId .vercel/project.json); TEAM=$(jq -r .orgId .vercel/project.json)

# read the true storage type (the CLI cannot show it):
curl -s -H "Authorization: Bearer $TOK" \
  "https://api.vercel.com/v9/projects/$PROJ/env?teamId=$TEAM" \
  | jq -r '.envs[] | "\(.type)\t\(.key)"' | sort

# create it verifiably:
jq -n --arg v "$SECRET" '{key:"NAME",value:$v,type:"encrypted",target:["production","preview"]}' > /tmp/b.json
curl -s -X POST -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  --data @/tmp/b.json "https://api.vercel.com/v10/projects/$PROJ/env?teamId=$TEAM"
```

**Match the sibling credential's type rather than the CLI default.**

⚠️ `vercel redeploy` needs `--scope <team>` (it defaults to whatever team the CLI last
switched to and errors "Deployment doesn't belong to current team"), and it does not
accept `--yes`.

---

## 🚨 A CLI needing reauth fails with EMPTY output and exit 0

```
ERROR: (gcloud.compute.regions.describe) There was a problem refreshing your
current auth tokens: Reauthentication failed. cannot prompt during
non-interactive execution.
```

That error goes to **stderr**, so piping into `grep`/`jq` yields **empty output and a 0
exit**. `gcloud compute regions describe … | grep -i gpu` printed nothing and looked
exactly like *"this project has no GPU quota"* — a false, load-bearing conclusion.

> `gcloud auth list` shows the account as ACTIVE. That is **not** proof the token can
> refresh.

Go around the CLI with the ADC token, which does work — and **always print the HTTP code
and assert 200 before reading the body**:

```sh
T=$(gcloud auth application-default print-access-token)
curl -s -H "Authorization: Bearer $T" \
  "https://compute.googleapis.com/compute/v1/projects/$P/regions/us-central1" \
  -o /tmp/reg.json -w "HTTP=%{http_code}\n"
jq -r '.quotas[] | select(.metric|test("GPU";"i")) | "\(.metric)\t\(.limit)"' /tmp/reg.json
```

An empty `jq` result over an error body is the same silent lie.

Two ADC-over-REST gotchas: some APIs additionally require an `x-goog-user-project: $P`
header, and they 403 if the API is **disabled** on the project. **Enabling an API is a
mutation — ask first, don't enable to finish a probe.**

⚠️ Related: `gcloud config get-value account` is **not** the identity that impersonates.
ADC is, and the two stores are independent.

---

## A floating dependency bound makes local and CI different programs

A pin like `fastapi>=0.136,<1` **floats**. CI installs fresh every run and resolves the
newest matching release; a long-lived local venv keeps whatever it first installed.
Measured: local `fastapi 0.136.1` / `starlette 1.0.0`, CI `fastapi 0.141.1` /
`starlette 1.6.0`.

**The concrete break.** FastAPI 0.141 keeps `_IncludedRouter` wrappers in `app.routes`,
and they have **no `.path`**. So:

```python
{r.path for r in app.routes}          # fine on 0.136, AttributeError on 0.141
```

took 11 tests from green locally to `AttributeError` in CI, on a required check.

**Version-stable fix:** read `app.openapi()["paths"]`. It is a public API, it drops the
built-in `/docs` + `/openapi.json` routes for free, and — for anything asserting "which
paths does this app serve" — it is the same surface an external post-deploy check reads,
so tests and runbook cannot disagree about what "mounted" means.

> Avoid `app.routes`, `route.dependant`, `app.user_middleware` and other internals in
> assertions unless the test IS about internals.

⚠️ **You probably cannot reproduce the CI version locally.** If worktree venvs are
symlinks to a shared one, `pip install fastapi==0.141` mutates the environment every
other session and worktree is using. Either accept that CI is the verifier and **say so
explicitly** rather than implying local proof, or build a genuinely separate venv.

⚠️ **It also invalidates local "identical behaviour" measurements.** One PR verified
"the refactor leaves the app unchanged — 54 routes, identical" against 0.136 while CI
runs 0.141. The conclusion happened to hold, but the measurement was not made against
the version that ships.

---

## CI cost structure, when it comes up

Two findings that generalize:

- **A large share of a CI bill is per-job rounding** — measured at 17% in one account.
  Caching a sub-minute step therefore saves **nothing**. Consolidating jobs does.
- **Filter jobs by path.** In one repo 44% of PR runs touched no Terraform at all and
  still paid for the Terraform job.

⚠️ **A billing outage presents as a code failure.** When Actions billing lapses, jobs
fail in ~3 seconds with **zero steps executed**. Read the run **annotation**, not the
logs — the logs are empty and read like a config error.
