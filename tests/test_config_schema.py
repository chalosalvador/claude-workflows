#!/usr/bin/env python3
"""Guard: the workflow.json schema table, its example, and setup's probe list agree.

WHY THIS EXISTS
---------------
`claude plugin update` refreshes the plugin's code and tells no repo that its
`.claude/workflow.json` is now behind. The migration path is `setup upgrade`,
which adds the keys the schema gained since the file was written. That only
works if three things never drift:

  1. every key the Layer-2 example in shared/config.md shows has a row in the
     schema table, with the schema version it arrived in ("Since");
  2. no row claims a version newer than **Current schema**;
  3. setup knows how to probe every key in the table — a key it has never
     heard of is a key `upgrade` can never add.

A PR that adds a key to the example but not to the table, or to the table but
not to setup, passes every other check and ships a config nobody can migrate
to. This guard is the cost that makes the three move together.

DESIGN — see plugins/gh-issue-flow/reference/guard-tests.md
----------------------------------------------------------
Inventory pins, not property checks: the row COUNT is asserted against an
independent constant so a silently emptied table cannot pass by having nothing
to disagree about. Matching is on normalized text, so reformatting a row or
reordering the table stays green.

Mutation-proven — see CONTRIBUTING.md § Conventions for the ledger.

Run:  python3 tests/test_config_schema.py
Set SCHEMA_GUARD_ROOT to point it at a copy (the mutation harness does).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(os.environ.get("SCHEMA_GUARD_ROOT") or Path(__file__).resolve().parent.parent)
CONFIG = ROOT / "plugins/gh-issue-flow/shared/config.md"
SETUP = ROOT / "plugins/gh-issue-flow/skills/setup/SKILL.md"

# Independent of the table, deliberately. Adding a key means bumping this too.
EXPECTED_KEYS = 20

ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*(\d+)\s*\|", re.M)
CURRENT = re.compile(r"\*\*Current schema:\s*(\d+)\.?\*\*")


def fail(msg: str) -> int:
    print(f"FAIL: {msg}", file=sys.stderr)
    return 1


def example_keys(config: str) -> set[str]:
    """Top-level keys of the first ```json block after the Layer 2 heading."""
    after = config.split("## Layer 2", 1)
    if len(after) < 2:
        sys.exit("HARNESS BUG: no '## Layer 2' heading in config.md")
    m = re.search(r"```json\n(.*?)\n```", after[1], re.S)
    if not m:
        sys.exit("HARNESS BUG: no json block under Layer 2")
    keys = set()
    for k in json.loads(m.group(1)):
        keys.add("$comment*" if k.startswith("$comment") else k)
    return keys


def main() -> int:
    config = CONFIG.read_text(encoding="utf-8")
    setup = SETUP.read_text(encoding="utf-8")
    problems: list[str] = []

    currents = CURRENT.findall(config)
    if len(currents) != 1:
        return fail(f"expected exactly one '**Current schema: N.**' in config.md, found {len(currents)}")
    current = int(currents[0])

    rows: dict[str, int] = {}
    for key, since in ROW.findall(config):
        if key in rows:
            problems.append(f"schema table lists `{key}` twice")
        rows[key] = int(since)
    if not rows:
        return fail("schema table has no rows — did a rewrite drop it?")
    if len(rows) != EXPECTED_KEYS:
        problems.append(
            f"schema table has {len(rows)} keys, expected {EXPECTED_KEYS}. "
            "Update EXPECTED_KEYS in the same commit, deliberately."
        )
    if "schemaVersion" not in rows:
        problems.append("schema table has no `schemaVersion` row")

    for key, since in rows.items():
        if since > current:
            problems.append(f"`{key}` claims Since {since} but Current schema is {current}")

    for key in sorted(example_keys(config) - rows.keys()):
        problems.append(f"Layer-2 example shows `{key}` but the schema table has no row for it")

    for key in sorted(rows):
        if key == "$comment*":
            needle = "`$comment"
        else:
            needle = f"`{key}`"
        if needle not in setup:
            problems.append(f"setup/SKILL.md never mentions `{key}` — `upgrade` cannot add a key setup cannot probe")

    if problems:
        print(f"FAIL: {len(problems)} schema-agreement violation(s)\n", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print(f"OK: schema {current}, {len(rows)} keys, example and setup agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
