# Running `review-pr` on every PR

A workflow for the repo whose PRs you want reviewed. It runs the skill through
[`anthropics/claude-code-action`](https://github.com/anthropics/claude-code-action), with
the plugin loaded from a checkout of this marketplace pinned to one commit, so every run in
a comparison reviews with the same reviewer.

**Unverified end to end.** The input names below are the ones the action's `action.yml`
declares; that it passes `--plugin-dir` through to the CLI, and that the allowed-tools list
is enough for every lens, have not been run.

```yaml
name: review-pr

on:
  pull_request:
    types: [opened, ready_for_review, labeled]

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    # Runs on open and on ready-for-review; the label re-runs it on demand.
    if: >-
      !github.event.pull_request.draft &&
      (github.event.action != 'labeled' || github.event.label.name == 'review-pr')
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/checkout@v4
        with:
          repository: chalosalvador/claude-workflows
          ref: <commit SHA to review with>
          path: .review-plugin

      - uses: anthropics/claude-code-action@v1
        env:
          GH_TOKEN: ${{ github.token }}
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          github_token: ${{ github.token }}
          prompt: "/gh-issue-flow:review-pr ${{ github.event.pull_request.number }} post"
          claude_args: >-
            --plugin-dir ${{ github.workspace }}/.review-plugin/plugins/gh-issue-flow
            --allowedTools "Agent,Read,Glob,Grep,Bash(git:*),Bash(gh:*)"
```

What each part is for:

- **`fetch-depth: 0`** gives the clone the history the three-dot diff needs to find a merge
  base. The skill unshallows a shallow clone itself, at the cost of a second fetch.
- **`ref:` a commit SHA**, not a branch: a comparison run over several days otherwise
  reviews later PRs with a different reviewer. The skill prints the plugin `version` it
  loaded on every run.
- **`--allowedTools`** is the floor: spawning the lenses, reading files, `git` and `gh`. A
  lens that runs the repo's tests or a mutant needs those commands too; add the repo's
  gate commands, or the lens reports that it could not run them.
- **`GH_TOKEN`** is what `gh` reads. The `pull-requests: write` permission is what lets the
  skill post its review; everything else it does is a read.

The action also takes `plugin_marketplaces` and `plugins` inputs, which install the plugin
from its marketplace instead of a checkout. That tracks the marketplace's branch rather
than a fixed commit, which suits everyday use better than a comparison.

**A PR from a fork gets no secrets** under `pull_request`, so the run fails at
authentication. Reviewing fork PRs needs `pull_request_target`, which runs with the base
repo's secrets next to the fork's code; read GitHub's guidance on that trigger before
switching to it.
