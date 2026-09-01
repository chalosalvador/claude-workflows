#!/usr/bin/env python3
"""Guard: every tracked file matches an expected shape.

WHY THIS EXISTS
---------------
A file named `Layer-3` containing `ABSENT - probe` was tracked on `main` for
days. It was created by an unquoted `>` in a shell probe — the intent was to
print `Layer-3 > ABSENT - probe`, and the shell redirected instead — and a
`git add -A` then swept it into a commit. Nothing noticed.

That is the second accident of this family in this project; the first put a
`README.md.bak` on a sibling repo's `main` via `sed -i.bak` plus a mismatched
cleanup. Both were invisible because a stray file breaks nothing.

DESIGN — see plugins/gh-issue-flow/reference/guard-tests.md
----------------------------------------------------------
ALLOWLIST, not a ban-list. Every tracked path must match one of the patterns
below; anything else fails by being *absent* from the list rather than by being
enumerated as bad. A ban-list ("no files named like a probe") cannot anticipate
the next accident's spelling.

Adding a genuinely new kind of file means editing ALLOWED in the same commit.
That is the cost, and it is the feature: it forces one deliberate look at a path
nobody chose on purpose.

Run:  git add -A && python3 tests/test_no_stray_files.py
"""
from __future__ import annotations

import fnmatch
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Every tracked path must match one of these.
ALLOWED = (
    ".gitignore",
    "LICENSE",
    "*.md",                                   # docs, skills, references
    ".claude-plugin/marketplace.json",
    "plugins/*/.claude-plugin/plugin.json",
    ".github/workflows/*.yml",
    "tests/*.py",
    "plugins/*/skills/*/assets/*.css",
)

# Independent of len(ALLOWED), which would be circular.
EXPECTED_ALLOWED_PATTERNS = 8


def main() -> int:
    if len(ALLOWED) != EXPECTED_ALLOWED_PATTERNS:
        sys.exit(
            f"ALLOWLIST CHANGED: {len(ALLOWED)} patterns, expected "
            f"{EXPECTED_ALLOWED_PATTERNS}. Update the constant deliberately."
        )

    tracked = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files"],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    if not tracked:
        sys.exit("HARNESS BUG: git ls-files returned nothing")

    strays = [p for p in tracked if not any(fnmatch.fnmatch(p, a) for a in ALLOWED)]

    if strays:
        print(f"FAIL: {len(strays)} tracked file(s) match no allowed pattern\n", file=sys.stderr)
        for p in strays:
            print(f"  - {p}", file=sys.stderr)
        print(
            "\nEither it is an accident — a shell redirect, an editor backup, a `git add -A`\n"
            "sweep — in which case `git rm` it; or it is deliberate, in which case add a\n"
            "pattern to ALLOWED and bump EXPECTED_ALLOWED_PATTERNS in this same commit.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: {len(tracked)} tracked files, all matching {len(ALLOWED)} allowed patterns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
