# Comments and docs

The default policy for every comment and doc line this plugin writes, or tells an agent to
write, into a repo: code comments, docs, `repo.md`, the deploy-target docs, `$comment` keys
in `workflow.json`, and anything a template generates.

**A repo's own written policy wins.** When the repo has one, commonly a section titled
"Comments and docs" in its `CONTRIBUTING.md`, `AGENTS.md` or `CLAUDE.md`, apply that
instead. This file is the default for a repo that has none.

## The rules

A comment states what the code cannot: why it is shaped this way, a constraint, or a trap.
Write it in the present tense, and only if it stays true without anyone editing it.

- **History goes in the commit message and the PR body**, never in code or in docs that
  describe current behaviour: what changed, what it used to be, what an earlier draft did,
  what a reviewer said. The PR body's History section is where it is written
  ([`git-and-github.md` § Writing a PR body](git-and-github.md#writing-a-pr-body)), and
  `git blame` links every line to that record.
- **Never name an issue or PR number in a comment or a doc**, apart from the two exceptions
  below. Issue and PR numbers belong in issue and PR text, commit messages and branch
  names. There is no TODO exception: describe work that is still missing in words, and let
  the tracker hold the issue. Examples, fenced code included, use `#N`.
- **No dates, "measured" or "currently".** A result lives in the report or the PR that
  produced it. A date that is itself part of a fact, such as a platform cutoff, is written
  in backticks.
- **No live state.** Whether something is enabled, deployed, required or set is read from
  the system when it matters. A doc gives the command that reads it, never the value.
- **One fact, one home.** Link to it instead of restating it. If several places need the
  same comment, extract the code and comment it once.
- **Three lines is normal, five is a smell, fifteen is a document.** Move a long
  explanation to the doc that owns the topic and leave a one-line pointer.
- **No 🚨, ⚠️ or capitals for emphasis.** If getting it wrong is dangerous, make a test or
  a type fail.
- **Commented-out code is deleted.** Git keeps it. Markup left out of a render on purpose
  says why, in the present tense.
- **Answer a reviewer in the thread, not in the code.** Make the code clearer, or reply.
- **Comments and docs are reviewed, not tested.** No test or CI step checks what a
  comment or a doc says; the `comments` lens in
  [`../agents/diff-reviewer.md`](../agents/diff-reviewer.md) does. A test reads a comment
  or a doc only where a program reads it, such as a suppression format a scanner requires
  or a header a skill looks up ([`guard-tests.md`](guard-tests.md) § 4).

## Exceptions

Two kinds of text name an issue because a tool requires it:

- An OpenSpec change folder, apart from its spec deltas, names its issue, because the
  change flow requires it ([`openspec.md`](openspec.md)).
- A security suppression carries the issue and expiry date that its scanner or guard
  requires.

## Where the plugin applies it

- `$comment` keys: [`../shared/config.md`](../shared/config.md) § Layer 2, `$comment*`.
- `repo.md` and the deploy-target docs: the skeletons they are generated from,
  [`../skills/setup/repo-template.md`](../skills/setup/repo-template.md) and
  [`../skills/setup/deploy-target-template.md`](../skills/setup/deploy-target-template.md).
- The PR body: [`git-and-github.md` § Writing a PR body](git-and-github.md#writing-a-pr-body).
- Review: the `comments` lens,
  [`../agents/diff-reviewer.md` § The lenses](../agents/diff-reviewer.md#the-lenses).
