#!/usr/bin/env python3
"""Guard: the stack-doc header contract is one set, and every reader names it exactly.

WHY THIS EXISTS
---------------
A deploy-target doc (`.claude/workflow/deploy-targets/<name>.md`, generated into user repos from
`skills/setup/deploy-target-template.md`) is read by header NAME. The skeleton says so:
"skills read them by name, so keep every ## exactly as written". Three things
therefore have to agree, and prose cannot hold them:

  1. the `##` headers in the two skeletons, with no header in both;
  2. the Section and File columns of the "Read by" table in shared/config.md
     § Deploy-target docs;
  3. every "§ <Section>" reference to a stack-doc section under plugins/.

A reader citing "§ Infra" while the header is "## Infra and migrations", or two
copies of the header set that disagree on its size, pass review easily. A reader
matching by name finds nothing, and nothing distinguishes "section missing" from
"section says nothing".

DESIGN — see plugins/gh-issue-flow/reference/guard-tests.md
----------------------------------------------------------
The table's (Section, File) pairs and the skeletons' (header, skeleton) pairs are
compared as sets, so a dropped, demoted or moved header reds on the row it leaves
behind. A "§ X" whose X is a strict word-prefix of a header ("Infra" for "Infra and
migrations") is that header spelled short, and reds. A reference that names its doc
(`repo.md`, "deploy-target doc" or a `deploy-targets/<name>.md` path) followed by one
or more "§ X" must name headers, so a section renamed or removed with its row reds on
those references. A "§ X" with no doc named is not tied to either skeleton: it reds
only when spelled short, and one that matches no header ("§ Layer 1", "§ 5b") is some
other section.

Mutation-proven; the cases a re-proof covers are in CONTRIBUTING.md § Conventions.

Run:  git add <the paths you changed> && python3 tests/test_doc_headers.py
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

HEADER = re.compile(r"^## (.+?)\s*$", re.M)
TABLE_ROW = re.compile(r"^\| ([A-Z][^|]*?) \| ([^|]*?) \|", re.M)
TABLE_FILE = {"target": "target", "repo.md": "repo"}
# A wrapped reference ("§ Review\n  bot") is still one phrase: allow one line break between words.
REF = re.compile(r"§ ([A-Z][A-Za-z]+(?:[ \n][ \t]*[a-z]+)*)")
# A reference that names its stack doc, then one or more sections: each has to land on a header.
SECTION = r"§ [A-Z][A-Za-z]+(?:[ \n][ \t]*[a-z]+)*"
DOC_REF = re.compile(r"(?i:(?<![\w-])`?repo\.md`?|deploy-target docs?|`?\.?[\w./-]*deploy-targets/<name>\.md`?)[ \n][ \t]*("
                     + SECTION + r"(?:,?[ \n][ \t]*(?:and[ \n][ \t]*)?" + SECTION + r")*)")


def fail(msg: str) -> int:
    print(f"FAIL: {msg}", file=sys.stderr)
    return 1


def main() -> int:
    headers: list[str] = []
    pairs: set[tuple[str, str]] = set()
    for kind, path in TEMPLATES.items():
        hs = HEADER.findall(path.read_text(encoding="utf-8"))
        if not hs:
            return fail(f"no ## headers found in the {kind} skeleton — did a rewrite drop them?")
        headers += hs
        pairs |= {(h, kind) for h in hs}
    if len(set(headers)) != len(headers):
        return fail("a header appears in both skeletons; a section has one home")
    hset = set(headers)
    problems: list[str] = []

    config = CONFIG.read_text(encoding="utf-8")
    block = config.split("| Section | File | Read by | For |", 1)
    if len(block) < 2:
        return fail("config.md has no '| Section | File | Read by | For |' table")
    table = block[1].split("\n\n", 1)[0]
    rows = {(sec, TABLE_FILE.get(f.strip("`"), f)) for sec, f in TABLE_ROW.findall(table) if sec != "Section"}
    if rows != pairs:
        problems.append(f"config.md Read-by table {sorted(rows)} != skeleton headers {sorted(pairs)}")

    tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z", SCAN],
                             capture_output=True, text=True, check=True).stdout.split("\0")
    md = [p for p in tracked if p.endswith(".md")]
    if not md:
        sys.exit("HARNESS BUG: no tracked markdown under " + SCAN)
    for rel in md:
        text = (ROOT / rel).read_text(encoding="utf-8")
        for m in DOC_REF.finditer(text):
            for s in re.finditer(SECTION, m.group(1)):
                words = re.sub(r"\s+", " ", s.group(0)[2:]).split(" ")
                if not any(words[:len(h.split(" "))] == h.split(" ") for h in hset):
                    line = text.count("\n", 0, m.start(1) + s.start()) + 1
                    problems.append(f"{rel}:{line}: '§ {words[0]}' after a stack-doc name matches no skeleton header")
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
