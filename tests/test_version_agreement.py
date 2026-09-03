#!/usr/bin/env python3
"""Guard: the three version numbers must agree.

WHY THIS EXISTS
---------------
A behaviour change that does not bump `version` reaches no running session: the
installed plugin is served from a version-keyed cache that nothing invalidates
while that string is unchanged. This repo has a measured incident — eight
consecutive PRs shipped to `main` and none of them reached a session.

So CLAUDE.md and CONTRIBUTING.md both tell you to bump THREE numbers. The
existing gate only enforces two of them:

  MEASURED, `claude plugin validate . --strict`:
    plugin.json disagrees with marketplace plugins[0].version -> exit 1
    marketplace TOP-LEVEL version stale, garbage, or DELETED  -> exit 0

That third field is what a marketplace listing advertises. A PR that bumps
plugin.json and plugins[0].version and forgets the top level is green on every
check in CI while the manifest names a version that does not exist.

Both docs answer this with "read all three back yourself". That is a human
promise where a four-line assertion will do — which is the whole argument of
`reference/verification.md`: prove it, do not intend to.

WHAT THIS DOES **NOT** DO
-------------------------
It cannot tell that you forgot to bump at all — nothing can, without knowing
whether a diff is behavioural. It only guarantees the three numbers never
disagree, so a bump is all-or-nothing rather than partial. The partial bump is
the failure that passes today.

Run:  python3 tests/test_version_agreement.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"


def main() -> int:
    market = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    entries = market.get("plugins") or []
    if not entries:
        sys.exit("HARNESS BUG: marketplace.json declares no plugins")

    seen: dict[str, list[str]] = {}

    def note(version: object, where: str) -> None:
        if not isinstance(version, str) or not version:
            sys.exit(f"{where}: version is missing or not a string ({version!r})")
        seen.setdefault(version, []).append(where)

    note(market.get("version"), ".claude-plugin/marketplace.json -> version")

    for entry in entries:
        name = entry.get("name")
        source = entry.get("source", "")
        note(entry.get("version"), f"marketplace.json -> plugins[{name}].version")

        # The entry's source is the plugin dir; its manifest must agree.
        manifest = ROOT / str(source).lstrip("./") / ".claude-plugin" / "plugin.json"
        if not manifest.is_file():
            sys.exit(f"HARNESS BUG: no plugin.json at {manifest.relative_to(ROOT)}")
        note(
            json.loads(manifest.read_text(encoding="utf-8")).get("version"),
            f"{manifest.relative_to(ROOT)} -> version",
        )

    if len(seen) != 1:
        print("FAIL: version numbers disagree\n", file=sys.stderr)
        for version, wheres in sorted(seen.items()):
            for where in wheres:
                print(f"  {version:<12} {where}", file=sys.stderr)
        print(
            "\n  Bump every one of them in the same commit. `claude plugin validate`\n"
            "  does NOT check the marketplace top-level field — that is why this exists.",
            file=sys.stderr,
        )
        return 1

    version = next(iter(seen))
    print(f"OK: version {version}, agreed across {sum(len(w) for w in seen.values())} fields")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
