#!/usr/bin/env python3
"""Guard: facts that must live in exactly ONE file.

WHY THIS EXISTS
---------------
Spend rules, tier tables and measured numbers are the content most likely to be
tuned later. When the same fact sits in several files, a tune updates one and
leaves the others silently contradicting it. This guard reds instead.

It exists because that regression actually shipped: a commit put the model-tier
table in 3 files and one measurement in 9 places across 5 files, days after
`shared/execution.md` was written specifically to stop that.

DESIGN — see plugins/gh-issue-flow/reference/guard-tests.md
----------------------------------------------------------
* INVENTORY PIN, not a property check. `OWNED` names every guarded clause and its
  one owner. A new duplicate fails by being absent from the pin, not by matching
  some "looks duplicated" heuristic that the next author routes around.
* REGION-NORMALIZED, never line-scoped. Every file is collapsed to one line
  before matching. Markdown hard-wraps at ~90 cols, so a line-scoped matcher
  cannot see a clause split across two lines — measured three separate times
  while building this repo, twice producing a confident FALSE "not present".
* COUNTS, not presence. A clause appearing twice inside its own owner is drift
  too, and presence alone cannot see it.
* SCOPED to tracked markdown under the paths below. A bare rglob descends into
  .git and into any git worktree someone adds later.

KNOWN LIMIT — read before trusting a local green
------------------------------------------------
Enumeration is `git ls-files`, i.e. the INDEX. A brand-new, unstaged file is
invisible to this guard, so a duplicate introduced in one passes locally.
Measured. `git add` it first; that is also the state CI runs in, which is why CI
is the authoritative run.

Run:  git add -A && python3 tests/test_single_owner_facts.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Only these trees are scanned. Anything outside is not this guard's business.
#
# CLAUDE.md and CONTRIBUTING.md were added after this branch shipped a direct
# self-contradiction between them in ONE commit — CLAUDE.md said `claude plugin tag`
# validates two version fields while CONTRIBUTING.md said the gate checks two of three
# and the top-level is unchecked — and both guards passed. They are the repo's two
# highest-traffic prose files and nothing mechanical protected either. MEASURED:
# widening costs nothing, 25 scanned files -> 27, no existing pin becomes a stray.
SCAN_ROOTS = ("README.md", "CLAUDE.md", "CONTRIBUTING.md", "plugins/")

# ─── THE PIN ────────────────────────────────────────────────────────────────
# clause -> (owning file, exact count expected in that owner)
#
# Add an entry when a fact becomes single-owner. Editing this dict is the point:
# it forces the "is this really meant to live in two places?" question into the
# same commit as the duplication.
OWNED: dict[str, tuple[str, int]] = {
    # The model tier table. Was in 3 files; execution.md owns it.
    "| `effort:easy` | `sonnet` | `sonnet` |":
        ("plugins/gh-issue-flow/shared/execution.md", 1),

    # Why tiering goes through the model at all. Was in 3 files.
    "`effort` is frontmatter-only and cannot be overridden":
        ("plugins/gh-issue-flow/shared/execution.md", 1),

    # The measured waste. Was restated 9x across 5 files.
    "roughly a third of the spend":
        ("plugins/gh-issue-flow/shared/execution.md", 1),

    # The planner's output shape belongs with the planner. Third phrasing:
    #   1. "≤400 words"                 — advisory. Measured, blown 4.75x.
    #   2. tier table, EMIT / DO NOT EMIT — a BAN-LIST. 0/3 compliance.
    #   3. this — an ALLOWLIST: five sections fully specified, everything else
    #      trigger-gated and one line. Nothing describes a section you should
    #      not write. (guard-tests.md: "allowlist beats ban-list".)
    "## Your output is FIVE sections. That is the whole plan.":
        ("plugins/gh-issue-flow/agents/issue-planner.md", 1),

    # The HANDOFF schema. The planner PRODUCES it; diff-reviewer only consumes,
    # so the field list must not be restated there.
    "Still unverified:":
        ("plugins/gh-issue-flow/agents/issue-planner.md", 1),

    # Autopilot's first hard rule. Restating it elsewhere invites a softened copy.
    "Never merge.":
        ("plugins/gh-issue-flow/skills/autopilot/SKILL.md", 1),

    # Triage's fan-out boundary. This is the clause a caller would most naturally
    # restate in the triage skill, and a softened copy there would licence a
    # distributed writer — which § 5's write ordering, its label-splitting trap
    # and its eventually-consistent read-back each independently cannot survive.
    "Every agent in the fan-out is read-only; the writes never leave the main session.":
        ("plugins/gh-issue-flow/reference/workflow-fanout.md", 1),

    # Autopilot's fan-out boundary, which is DELIBERATELY NOT the same rule as the
    # one above — its agents do write, to their own worktree and their own PR. The
    # two live in one file so the difference is visible; pinning both is what stops
    # a later edit from "unifying" them into one softer sentence that would either
    # ban the PR write or licence a board write.
    "Agents produce the branch and the PR; every state transition on the issue and "
    "the board stays with the session.":
        ("plugins/gh-issue-flow/reference/workflow-fanout.md", 1),

    # The standup shape. It arrived here from a downstream copy that had already
    # drifted from the task prompt driving it — a stale workstream path in one, the
    # right one in the other. One owner is the whole point: a second copy is how the
    # two disagree again.
    "**Three sections, in this order, always all three present.**":
        ("plugins/gh-issue-flow/skills/work-summary/SKILL.md", 1),

    # The unattended babysit rule. execution.md § 5 owns it; autopilot § 11 links to
    # it and states only the consequence. A restated copy there is how it would get
    # softened into "prefer the foreground", which is not the rule — the rule is that
    # a backgrounded wait has nobody to report to when a scheduled session ends.
    "In an unattended run, the babysit loop runs in the foreground or through Monitor "
    "— never as a backgrounded command whose result arrives as a notification.":
        ("plugins/gh-issue-flow/shared/execution.md", 1),

    # The fatal-substitution ban. This shipped as a real bug: an UNSET userConfig option
    # substitutes as its own literal placeholder text, so `${BOARD:-${user_config.x}}` is
    # a `bad substitution` that kills the block on its first line — on exactly the
    # "leave them blank" path the README documents as supported. § Layer 1 has been
    # rewritten four times on this branch; these five lines are the only record of why
    # the idiom is forbidden, and they read like ordinary shell to anyone who rewrites
    # them. Softening or relocating this is how the bug returns.
    "Never write `${BOARD:-${user_config.board_number}}` or any other parameter "
    "expansion around a `${user_config.*}` placeholder.":
        ("plugins/gh-issue-flow/shared/config.md", 1),

    # Board precedence in the one skill that WRITES to a board. Its absence was the
    # shipped defect: triage named `userConfig` as its board source, so the
    # workflow.json override never reached it and repo B's cards would have been added
    # to repo A's board. Deliberately short and arrow-free — the full sentence reds when
    # `→` is rewritten as `->`, which is a legitimate reformat.
    "`board` FIRST, and only then from `userConfig`":
        ("plugins/gh-issue-flow/skills/triage/SKILL.md", 1),
}

# Independent completeness check: NOT derived from len(OWNED), which would be
# circular and pass over a silently emptied pin.
EXPECTED_PINNED_CLAUSES = 12


def normalize(text: str) -> str:
    """Collapse a markdown file to one lowercase line.

    Strips leading heading/comment/quote markers per line, drops emphasis and
    code ticks, then collapses all whitespace. This is what makes the guard
    immune to hard-wrapping and to reformatting that preserves the prose.
    """
    text = re.sub(r"^[ \t]*(?:#{1,6}|//|>)\s*", "", text, flags=re.M)
    text = text.replace("*", "").replace("`", "")
    return re.sub(r"\s+", " ", text).strip().lower()


def tracked_markdown() -> list[Path]:
    out = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "*.md"],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    files = [ROOT / p for p in out if p.startswith(SCAN_ROOTS)]
    if not files:
        sys.exit("HARNESS BUG: no tracked markdown found under %s" % (SCAN_ROOTS,))
    return files


def main() -> int:
    if len(OWNED) != EXPECTED_PINNED_CLAUSES:
        sys.exit(
            f"PIN CHANGED: {len(OWNED)} clauses, expected {EXPECTED_PINNED_CLAUSES}.\n"
            "Update EXPECTED_PINNED_CLAUSES in the same commit, deliberately."
        )

    files = tracked_markdown()
    bodies = {f: normalize(f.read_text(encoding="utf-8")) for f in files}
    failures: list[str] = []

    for clause, (owner_rel, want) in OWNED.items():
        needle = normalize(clause)
        owner = ROOT / owner_rel

        if owner not in bodies:
            failures.append(f"{clause!r}\n    owner {owner_rel} is not a tracked scanned file")
            continue

        got = bodies[owner].count(needle)
        if got != want:
            failures.append(
                f"{clause!r}\n    expected {want}x in {owner_rel}, found {got}x"
                + ("\n    (0 means the owner lost it — did a rewrite drop the fact?)" if not got else "")
            )

        strays = [
            f"{f.relative_to(ROOT)}×{b.count(needle)}"
            for f, b in bodies.items()
            if f != owner and needle in b
        ]
        if strays:
            failures.append(
                f"{clause!r}\n    DUPLICATED outside its owner ({owner_rel}): "
                + ", ".join(strays)
                + "\n    Link to the owner instead, or move ownership deliberately."
            )

    if failures:
        print(f"FAIL: {len(failures)} single-owner violation(s)\n", file=sys.stderr)
        for f in failures:
            print(f"  - {f}\n", file=sys.stderr)
        return 1

    print(f"OK: {len(OWNED)} clauses, each in exactly one of {len(files)} scanned files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
