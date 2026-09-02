# The board query

`gh project item-list` is the most expensive call this plugin makes. This file holds the
hand-written GraphQL replacement, why it is cheaper, and what it deliberately drops.

Read this when a run is hitting the GraphQL budget, or before changing what the board
fetch returns. Everything else about board reads — the one-fetch-per-run rule, the
read-back exception — lives in [`../shared/config.md`](../shared/config.md) § Board
queries.

## Why the CLI is expensive

GraphQL bills on the **node count a query could return**, not on what it does return.
`gh project item-list` asks for a generic 100-item page with every nested connection
opened wide, so it is billed for a maximal board whatever your board actually holds.
MEASURED on a **6-item** board: `--limit 1000` and `--limit 100` both cost **102 points**,
`--limit 30` costs **31**. The price tracks the requested page size and ignores the
content.

You cannot narrow that from the CLI — there is no flag for "only these fields". Owning
the query string is the only lever, and it is worth a lot:

| | 6-item board |
|---|---|
| `gh project item-list --limit 1000` | **102 points** |
| the query below | **3 points** |

MEASURED, same board, same run, priced with GraphQL's own free meter.

🚨 **Cost tracks the `items(first:)` page cap and nothing else.** Measured: `first: 100`
costs 3, `first: 20` costs 1, `first: 2` costs 1 — and widening every *nested* cap
(`labels`, `assignees`, `fieldValues`) from 10 to 100 left the cost at **3**. Nested
selections are effectively free, so **do not narrow them to save points**; narrowing only
buys silent truncation. Budget ~3 points per page of 100 cards.

## The query

Ask for the seven things the skills actually read — `status`, `priority`, `track`,
`labels`, `assignees`, and `content.{number,title,body,repository,url}` — with every
nested connection opened to 100, because that costs nothing and truncation is the
expensive failure.

```sh
board_gql() {                      # $1 = "user" | "organization"
  cat <<GQL
query(\$login:String!, \$num:Int!, \$cursor:String) {
  rateLimit { cost remaining }
  $1(login: \$login) { projectV2(number: \$num) {
    items(first: 100, after: \$cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        id
        fieldValues(first: 100) { nodes {
          ... on ProjectV2ItemFieldSingleSelectValue {
            name field { ... on ProjectV2FieldCommon { name } } }
        } }
        content {
          ... on Issue { number title body url repository { nameWithOwner }
            labels(first: 100) { nodes { name } }
            assignees(first: 100) { nodes { login } } }
          ... on PullRequest { number title body url repository { nameWithOwner }
            labels(first: 100) { nodes { name } }
            assignees(first: 100) { nodes { login } } }
        }
      }
    }
  } }
}
GQL
}
```

🚨 **`user` and `organization` are different roots and there is no shared interface that
exposes `projectV2`.** Resolve which one applies first — over REST, so it costs no
GraphQL at all:

```sh
gh api "users/<login>" --jq 'if .type=="Organization" then "organization" else "user" end'
```

Guessing wrong returns `NOT_FOUND` with `data: null`, which reshapes to an empty board —
the silent-empty-result failure this plugin's reference docs are mostly about.

## The fetch

```sh
board_fetch() {                    # $1 owner login, $2 project number, $3 output path
  local login="$1" num="$2" out="$3" root q cursor="" page raw cost=0
  root=$(gh api "users/$login" \
    --jq 'if .type=="Organization" then "organization" else "user" end') || return 1
  q=$(board_gql "$root")
  raw=$(mktemp)
  while :; do
    if [ -z "$cursor" ]; then
      page=$(gh api graphql -f query="$q" -f login="$login" -F num="$num") || { rm -f "$raw"; return 1; }
    else
      page=$(gh api graphql -f query="$q" -f login="$login" -F num="$num" -f cursor="$cursor") || { rm -f "$raw"; return 1; }
    fi
    printf '%s\n' "$page" >> "$raw"
    cost=$(( cost + $(printf '%s' "$page" | jq -r '.data.rateLimit.cost') ))
    [ "$(printf '%s' "$page" | jq -r "(.data.$root).projectV2.items.pageInfo.hasNextPage")" = true ] || break
    cursor=$(printf '%s' "$page" | jq -r "(.data.$root).projectV2.items.pageInfo.endCursor")
  done
  jq -s '{items: [ .[]
    | (.data.user // .data.organization).projectV2.items.nodes[]
    | select(.content != null)
    | { id,
        status:   ([.fieldValues.nodes[]? | select(.field.name? == "Status")   | .name] | first),
        priority: ([.fieldValues.nodes[]? | select(.field.name? == "Priority") | .name] | first),
        track:    ([.fieldValues.nodes[]? | select(.field.name? == "Track")    | .name] | first),
        labels:    [.content.labels.nodes[]?.name],
        assignees: [.content.assignees.nodes[]?.login],
        content: { number: .content.number, title: .content.title, body: .content.body,
                   repository: .content.repository.nameWithOwner, url: .content.url } } ]}' \
    "$raw" > "$out"
  rm -f "$raw"
  echo "board_fetch: $(jq '.items|length' "$out") items, ${cost} GraphQL points" >&2
}
```

⚠️ **`-f` for the login, `-F` for the number.** `-F` coerces a value that looks numeric,
so `-F login=...` would silently turn an all-digits login into an integer and fail the
`String!` type check.

The reshape emits `{"items":[…]}` with the same field names `gh project item-list`
produces, so **every existing `jq` pass over `$BOARD_JSON` works unchanged.** That is the
point: this is a drop-in for the fetch line, not a rewrite of the consumers.

## What it deliberately drops

- **Draft issues.** `select(.content != null)` removes cards with no underlying
  issue or PR. Every consumer here keys on `.content.number`, which a draft does not
  have, so they were already unusable — but if you add a consumer that wants drafts,
  this is where they went.
- **Anything past 100** labels, assignees or project fields on a single card. That is
  GitHub's own page maximum, not a budget compromise — the caps were widened from 10 to
  100 after measuring that it changed the cost by zero. A card that exceeds one needs a
  second page, which this function does not do for nested connections.
- **Non-single-select fields.** `Status`, `Priority` and `Track` are single-selects. A
  text, number, date or iteration field needs its own inline fragment
  (`ProjectV2ItemFieldTextValue` and friends) — it will not appear otherwise, and its
  absence looks exactly like an unset value.

## Verified against the CLI

On a real board, the reshaped output was **identical to `gh project item-list` on every
key the skills read** — `content.number`, `content.repository`, `content.title`, `status`,
`priority`, `labels`, `assignees` — including items with six real labels and a live
`In Progress` status.

Two harmless shape differences, neither reaching a consumer:

- `gh` **omits** `labels` / `assignees` / `priority` when empty; this emits `[]` / `null`.
  Every consumer already spells them `(.labels // [])` and `(.priority // "-")`, so both
  behave the same. Verified by running all three skill `jq` passes against both files.
- `gh` carries a top-level `title` and a `repository` URL, and a `linked pull requests`
  field. Nothing reads them — the skills use `.content.title` and `.content.repository`.

It also gains `track`, which `gh project item-list` does not return at all.

## Verify before trusting it

Prove the positive case, per [`README.md`](README.md): a board fetch that silently
returns zero items is indistinguishable from a genuinely empty board.

```sh
jq '.items | length' "$BOARD_JSON"      # non-zero, and matches the board in the browser
jq -r '.items[].status' "$BOARD_JSON" | sort | uniq -c
```

An all-`null` status column means the field is not named `Status` on your board — the
query matches field names literally.
