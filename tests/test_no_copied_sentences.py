#!/usr/bin/env python3
"""Guard: no sentence is copied from one doc into another, or within one.

A copied sentence is a second home for one fact: a later edit updates one copy and
leaves the other contradicting it. This compares the docs with each other and holds
none of their wording, so rewording never reds it; only a copy does.

It reads sentences, list items, headings and table cells, with emphasis, code ticks
and whole links removed so one pointer in two docs is not a copy, and whole table
rows. Fenced code repeats commands on purpose and is not read. The re-proof cases
are in CONTRIBUTING.md § Conventions.

Run:  python3 tests/test_no_copied_sentences.py
Set COPY_GUARD_ROOT to point it at a copy (the mutation harness does).
"""
from __future__ import annotations

import collections
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("COPY_GUARD_ROOT") or Path(__file__).resolve().parent.parent)
SCAN_ROOTS = ("README.md", "CLAUDE.md", "CONTRIBUTING.md", "plugins/")
# Each is copied alone into a consumer repo, where a link to the other resolves nowhere,
# so a sentence they share only with each other is not a copy.
STANDALONE = frozenset({
    "plugins/gh-issue-flow/skills/setup/deploy-target-template.md",
    "plugins/gh-issue-flow/skills/setup/repo-template.md",
})
# One- and two-word repeats are headings and table labels, not facts.
MIN_WORDS = 3
# A row this wide is read whole as well, so a copied table reds even when its cells are short.
MIN_ROW_CELLS = 3

FENCE = re.compile(r"^(`{3,}|~{3,})(.*)$")
LINK = re.compile(r"!?\[(?:[^\[\]]|\[[^\]]*\])*\]\([^)]*\)")
REF_LINK = re.compile(r"!?\[[^\]]*\]\[[^\]]*\]")
LIST_ITEM = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
SEPARATOR_ROW = re.compile(r"^\|?[\s:|-]+\|?$")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
WORD = re.compile(r"[a-z0-9]")


def normalize(text: str) -> str:
    text = LINK.sub(" ", text)
    text = REF_LINK.sub(" ", text)
    text = text.replace("*", "").replace("`", "").replace("_", " ")
    return re.sub(r"\s+", " ", text).strip().lower()


def words(unit: str) -> int:
    return sum(1 for tok in unit.split(" ") if WORD.search(tok))


def units(text: str, rel: str) -> list[tuple[str, int, bool]]:
    """Every (unit, line, is_cell) in one markdown file."""
    out: list[tuple[str, int, bool]] = []
    para: list[str] = []
    para_line = 0
    fence: tuple[str, int] | None = None
    fence_line = 0

    def flush(cell: bool = False) -> None:
        nonlocal para
        if para:
            for s in SENTENCE_END.split(normalize(" ".join(para))):
                if words(s) >= MIN_WORDS:
                    out.append((s, para_line, cell))
            para = []

    def add(line_text: str, n: int) -> None:
        nonlocal para_line
        if not para:
            para_line = n
        para.append(line_text)

    lines = text.split("\n")
    start = 0
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                # Only `description` is prose; the other keys are settings two files may share.
                prose = False
                for j in range(1, i):
                    key = re.match(r"([\w-]+):\s*(?:[>|][-+]?\s*)?", lines[j])
                    if key:
                        flush()
                        prose = key.group(1) == "description"
                    if prose:
                        add(lines[j][key.end():] if key else lines[j], j + 1)
                flush()
                start = i + 1
                break

    for i in range(start, len(lines)):
        n = i + 1
        body = re.sub(r"^\s*(?:>\s?)*", "", lines[i])
        stripped = body.strip()
        m = FENCE.match(stripped)
        if fence:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= fence[1] and not m.group(2).strip():
                fence = None
            continue
        if m:
            flush()
            fence = (m.group(1)[0], len(m.group(1)))
            fence_line = n
            continue
        if not stripped or re.fullmatch(r"-{3,}|\*{3,}|_{3,}", stripped):
            flush()
            continue
        if stripped.startswith("|"):
            flush()
            if SEPARATOR_ROW.match(stripped):
                continue
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) >= MIN_ROW_CELLS:
                out.append((normalize(" | ".join(cells)), n, False))
            for c in cells:
                add(c, n)
                flush(cell=True)
            continue
        if stripped.startswith("#"):
            flush()
            add(stripped.lstrip("#"), n)
            flush()
            continue
        if LIST_ITEM.match(stripped):
            flush()
            add(LIST_ITEM.sub("", stripped), n)
            continue
        add(stripped, n)
    flush()
    # An open fence would hide the rest of the file from this guard.
    if fence:
        raise ValueError(f"{rel}:{fence_line}: a code fence opens here and never closes")
    return out


def docs() -> list[str]:
    # Untracked files too, so a new doc is read before it is staged.
    listed = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "*.md"],
        capture_output=True, text=True, check=True,
    ).stdout.split("\0")
    return sorted({p for p in listed if p.startswith(SCAN_ROOTS) and (ROOT / p).is_file()})


def main() -> int:
    files = docs()
    if not files:
        sys.exit(f"HARNESS BUG: no markdown found under {SCAN_ROOTS}")

    seen: dict[str, list[tuple[str, int, bool]]] = collections.defaultdict(list)
    problems: list[str] = []
    read = 0
    for rel in files:
        try:
            found = units((ROOT / rel).read_text(encoding="utf-8"), rel)
        except ValueError as e:
            problems.append(str(e))
            continue
        read += len(found)
        for unit, line, cell in found:
            seen[unit].append((rel, line, cell))
    if not read:
        sys.exit("HARNESS BUG: no sentences read — did the parser break?")

    for unit, sites in sorted(seen.items(), key=lambda kv: kv[1]):
        if len(sites) < 2 or all(rel in STANDALONE for rel, _, _ in sites):
            continue
        # A column holds the same value on many rows; the same cell in another file is a copy.
        if all(cell for _, _, cell in sites) and len({rel for rel, _, _ in sites}) == 1:
            continue
        where = ", ".join(f"{rel}:{line}" for rel, line, _ in sites)
        problems.append(f"{where}\n    {unit[:160]}")

    if problems:
        print(f"FAIL: {len(problems)} copied sentence(s)\n", file=sys.stderr)
        for p in problems:
            print(f"  - {p}\n", file=sys.stderr)
        print("Keep the sentence where the fact belongs and link to it from the other place.", file=sys.stderr)
        return 1

    print(f"OK: {read} sentences across {len(files)} docs, none copied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
