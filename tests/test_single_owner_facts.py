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
SCAN_ROOTS = ("README.md", "plugins/")

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

    # The planner's own output budget belongs with the planner. Was a word count
    # ("≤400 words"); replaced by a structural section allowlist after the word
    # budget was measured being exceeded 4.75x — advice loses, structure holds.
    "| Tier | Trigger | EMIT exactly | DO NOT EMIT |":
        ("plugins/gh-issue-flow/agents/issue-planner.md", 1),

    # The HANDOFF schema. The planner PRODUCES it; diff-reviewer only consumes,
    # so the field list must not be restated there.
    "Still unverified:":
        ("plugins/gh-issue-flow/agents/issue-planner.md", 1),

    # Autopilot's first hard rule. Restating it elsewhere invites a softened copy.
    "Never merge.":
        ("plugins/gh-issue-flow/skills/autopilot/SKILL.md", 1),
}

# Independent completeness check: NOT derived from len(OWNED), which would be
# circular and pass over a silently emptied pin.
EXPECTED_PINNED_CLAUSES = 6


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
