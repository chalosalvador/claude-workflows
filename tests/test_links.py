#!/usr/bin/env python3
"""Guard: every relative markdown link in the repo resolves to a tracked path.

WHY THIS EXISTS
---------------
The skills do not restate facts; they LINK to the file that owns each one, and
the agent follows the link at the moment the fact matters. A link that points at
a file that moved is therefore not a cosmetic defect — the skill silently runs
without the rule, and nothing in the run says so.

MEASURED: `reference/workflow-fanout.md` linked `../../../tests/`, a path that
exists in this marketplace checkout and nowhere in an installed plugin. Every
review passed it. That is the failure shape this repo's docs are about — a
missing thing that reads as nothing — applied to the docs themselves.

DESIGN — see plugins/gh-issue-flow/reference/guard-tests.md
----------------------------------------------------------
Positive case first: the guard refuses to pass on fewer than MIN_LINKS links, so
a parser that matched nothing cannot report a clean tree. Targets must be in
`git ls-files` (a directory counts if any tracked file is under it), so a link
to an untracked file reds — that file will not ship. And a file under
`plugins/<name>/` may only link inside `plugins/<name>/`: the installed copy is
that directory alone, so a link that climbs out of it resolves here and nowhere
a user runs it. MEASURED: without that rule the guard passed its own motivating
case (`../../../tests/` from inside the plugin), exit 0. Anchors (`#…`) are stripped
and not checked, and links inside fenced blocks or inline code spans are ignored as
quoted examples; both are known gaps, stated here rather than hidden.

Mutation-proven — ledger in CONTRIBUTING.md § Conventions.

Run:  git add -A && python3 tests/test_links.py
Set LINK_GUARD_ROOT to point it at a copy (the mutation harness does); the copy
must be a git repo with the files added.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(os.environ.get("LINK_GUARD_ROOT") or Path(__file__).resolve().parent.parent)

# Refuse to pass on a suspiciously small parse. Independent of the real count.
MIN_LINKS = 100   # measured 130 at ecbd9c5 on 2026-09-07; K4 (parser matching nothing) yields 0

LINK = re.compile(r"\]\(([^)\s]+)\)")
SKIP = ("http://", "https://", "mailto:", "#")
FENCE = re.compile(r"^(`{3,}|~{3,}).*?^\1[ \t]*$", re.M | re.S)
SPAN = re.compile(r"`[^`\n]*`")


def prose(text: str) -> str:
    """Drop fenced blocks and inline code spans: `](./x.md)` quoted in a code span is
    an example of a link, not a link. MEASURED: two such spans in the reference docs
    reddened the first version of this guard."""
    return SPAN.sub("`", FENCE.sub("", text))


def tracked() -> set[str]:
    # -z: NUL-separated, unquoted. Whitespace-splitting the default output turns
    # "a b.md" into two paths and leaves a non-ASCII name quoted and unmatched.
    out = [p for p in subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, text=True, check=True
    ).stdout.split("\0") if p]
    if not out:
        sys.exit("HARNESS BUG: git ls-files returned nothing")
    paths = set(out)
    for p in out:  # every parent directory of a tracked file is itself "tracked"
        parts = PurePosixPath(p).parts
        for i in range(1, len(parts)):
            paths.add("/".join(parts[:i]))
    return paths


def plugin_root(rel: str) -> str | None:
    """'plugins/<name>' for a file inside a plugin, else None."""
    parts = rel.split("/")
    return "/".join(parts[:2]) if len(parts) > 2 and parts[0] == "plugins" else None


def main() -> int:
    files = tracked()
    md = sorted(p for p in files if p.endswith(".md"))
    checked = 0
    broken: list[str] = []
    for rel in md:
        text = prose((ROOT / rel).read_text(encoding="utf-8"))
        for m in LINK.finditer(text):
            target = m.group(1)
            if target.startswith(SKIP) or target.startswith("/"):
                continue
            target = target.split("#", 1)[0]
            if not target:
                continue
            checked += 1
            resolved = os.path.normpath(os.path.join(os.path.dirname(rel), target))
            plugin = plugin_root(rel)
            if resolved.startswith(".."):
                broken.append(f"{rel}: {m.group(1)} escapes the repo")
            elif plugin and not (resolved + "/").startswith(plugin + "/"):
                broken.append(f"{rel}: {m.group(1)} → {resolved} is outside {plugin}/ and will not ship with the plugin")
            elif resolved not in files:
                broken.append(f"{rel}: {m.group(1)} → {resolved} is not a tracked path")

    if checked < MIN_LINKS:
        return_fail = f"only {checked} relative links parsed (< {MIN_LINKS}) — did the parser break?"
        print(f"FAIL: {return_fail}", file=sys.stderr)
        return 1
    if broken:
        print(f"FAIL: {len(broken)} broken relative link(s) across {len(md)} markdown files\n", file=sys.stderr)
        for b in broken:
            print(f"  - {b}", file=sys.stderr)
        print("\nA link to an untracked file reds on purpose: that file will not ship. git add it,\n"
              "or fix the link.", file=sys.stderr)
        return 1
    print(f"OK: {checked} relative links across {len(md)} markdown files all resolve to tracked paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
