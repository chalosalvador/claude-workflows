#!/usr/bin/env python3
"""Guard: the stack-doc header contract is one set, and every reader names it exactly.

WHY THIS EXISTS
---------------
A deploy-target doc (`.claude/workflow/deploy-targets/<name>.md`, generated into user repos from
`skills/setup/deploy-target-template.md`) is read by header NAME. The skeleton says so:
"skills read them by name, so keep every ## exactly as written". Three things
therefore have to agree, and prose cannot hold them:

  1. the `##` headers in the two skeletons, with no header in both;
  2. the Section column of the "Read by" table in shared/config.md § Deploy-target docs;
  3. every "§ <Section>" reference to a stack-doc section under plugins/.

A reader citing "§ Infra" while the header is "## Infra and migrations", or two
copies of the header set that disagree on its size, pass review easily. A reader
matching by name finds nothing, and nothing distinguishes "section missing" from
"section says nothing".

DESIGN — see plugins/gh-issue-flow/reference/guard-tests.md
----------------------------------------------------------
Inventory pin: the header COUNT is asserted against an independent constant.
Reference check is a prefix rule: a "§ X" whose X is a strict word-prefix of a
header (e.g. "Infra" for "Infra and migrations") is a reference to that header
spelled short, and reds; a "§ X" that matches no header at all ("§ Layer 1",
"§ 5b", "§ Board queries") is some other section and is ignored.

Mutation-proven — ledger in CONTRIBUTING.md § Conventions.

Run:  python3 tests/test_doc_headers.py
Set STACK_GUARD_ROOT to point it at a copy (the mutation harness does).
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("STACK_GUARD_ROOT") or Path(__file__).resolve().parent.parent)
TEMPLATES = {"target": ROOT / "plugins/gh-issue-flow/skills/setup/deploy-target-template.md",
             "repo": ROOT / "plugins/gh-issue-flow/skills/setup/repo-template.md"}
CONFIG = ROOT / "plugins/gh-issue-flow/shared/config.md"
SCAN = "plugins/gh-issue-flow/"

EXPECTED_HEADERS = {"target": 4, "repo": 3}

HEADER = re.compile(r"^## (.+?)\s*$", re.M)
TABLE_ROW = re.compile(r"^\| ([A-Z][^|]*?) \|", re.M)
# A wrapped reference ("§ Review\n  bot") is still one phrase: allow one line break between words.
REF = re.compile(r"§ ([A-Z][A-Za-z]+(?:[ \n][ \t]*[a-z]+)*)")


def fail(msg: str) -> int:
    print(f"FAIL: {msg}", file=sys.stderr)
    return 1


def main() -> int:
    headers: list[str] = []
    for kind, path in TEMPLATES.items():
        hs = HEADER.findall(path.read_text(encoding="utf-8"))
        if not hs:
            return fail(f"no ## headers found in the {kind} skeleton — did a rewrite drop them?")
        if len(hs) != EXPECTED_HEADERS[kind]:
            return fail(f"{kind} skeleton has {len(hs)} headers, expected {EXPECTED_HEADERS[kind]}; update the constant deliberately")
        headers += hs
    if len(set(headers)) != len(headers):
        return fail("a header appears in both skeletons; a section has one home")
    hset = set(headers)
    problems: list[str] = []

    config = CONFIG.read_text(encoding="utf-8")
    block = config.split("| Section | File | Read by | For |", 1)
    if len(block) < 2:
        return fail("config.md has no '| Section | File | Read by | For |' table")
    table = block[1].split("\n\n", 1)[0]
    rows = set(TABLE_ROW.findall(table)) - {"Section"}
    if rows != hset:
        problems.append(f"config.md Read-by table {sorted(rows)} != skeleton headers {sorted(headers)}")

    tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z", SCAN],
                             capture_output=True, text=True, check=True).stdout.split("\0")
    md = [p for p in tracked if p.endswith(".md")]
    if not md:
        sys.exit("HARNESS BUG: no tracked markdown under " + SCAN)
    for rel in md:
        text = (ROOT / rel).read_text(encoding="utf-8")
        for m in REF.finditer(text):
            words = re.sub(r"\s+", " ", m.group(1)).split(" ")
            # Word by word against each header: a phrase that matches the first k words of a
            # header and then stops, or diverges, is that header spelled short. The regex is
            # greedy, so "§ Infra before deciding" arrives as three words; only "Infra" matches.
            for h in hset:
                hw = h.split(" ")
                k = 0
                while k < len(hw) and k < len(words) and words[k] == hw[k]:
                    k += 1
                if 0 < k < len(hw):
                    line = text.count("\n", 0, m.start()) + 1
                    problems.append(f"{rel}:{line}: '§ {' '.join(words[:k])}' names no header — the header is '## {h}'")

    if problems:
        print(f"FAIL: {len(problems)} doc-header violation(s)\n", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"OK: {len(headers)} skeleton headers across {len(TEMPLATES)} skeletons, table agrees, references under {SCAN} name them exactly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
