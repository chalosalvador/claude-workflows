#!/usr/bin/env python3
"""Guard: the lines a branch adds or changes follow the comment policy.

Only added and changed lines are read: a line the branch doesn't touch never fails, and
neither does one it only moves or re-indents. Markdown fails on an issue or PR number, or on
a date outside backticks; fenced code is skipped. A code comment fails on an issue or PR
number, a date, an alarm marker, narration of a superseded draft, or a block over
MAX_BLOCK_LINES lines. The rules: plugins/gh-issue-flow/reference/comments-and-docs.md.

Run:  git fetch origin && python3 tests/test_comment_policy.py
"""
from __future__ import annotations

import argparse
import ast
import io
import os
import re
import subprocess
import sys
import tokenize
import warnings
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN = "origin/main"
POLICY = "plugins/gh-issue-flow/reference/comments-and-docs.md"
MAX_BLOCK_LINES = 15

# A `#<digits>` followed by `-` is a heading anchor, as in `(#2-validation-gates)`.
ISSUE_REF = re.compile(
    r"(?<![\w&#/])(?:[\w.-]+(?:/[\w.-]+)?)?#\d{1,5}(?![\w-])"
    r"|\b(?:PR|pull request|issue)\s+#?\d{1,5}\b"
    r"|github\.com/[\w.-]+/[\w.-]+/(?:issues|pull)/\d+",
    re.IGNORECASE,
)
# A date inside a path, a name or an identifier (after `/` or `-`, joined by `_`, before
# `.ext`) is a name, not a claim; `pre-`, `post-` and `mid-` still read as prose.
DATE = re.compile(
    r"(?:(?<![/\w-])|(?<=\b[Pp]re-)|(?<=\b[Mm]id-)|(?<=\b[Pp]ost-))20\d\d-[01]\d-[0-3]\d"
    r"(?:(?![\w-]|\.\w)|(?=T\d)|(?=-20\d\d-[01]\d-[0-3]\d(?![\w-]|\.\w)))"
)
BACKTICKS = re.compile(r"``[^`]*``|`[^`]*`")
QUOTED = re.compile(
    r"``[^`]*``|`[^`]*`|(?<![\w\"])\"[^\"\n]*\"(?![\w\"])|(?<![\w'])'[^'\n]*'(?![\w'])"
)
TRIPLE_QUOTES = re.compile(r"\"\"\"|'''")
ALARM = re.compile("[\U0001f6a8⚠]")
EARLIER_DRAFT = re.compile(
    r"\ban earlier (?:draft|version|revision)\b"
    r"|\bthis (?:very )?(?:comment|paragraph|sentence|docstring|block)"
    r" (?:said|claimed|used to)\b",
    re.IGNORECASE,
)
HUNK = re.compile(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
HEREDOC = re.compile(r"(?<!<)<<(?!<)[-~]?\s*['\"]?([A-Za-z_]\w*)['\"]?")
FENCE = re.compile(r"`{3,}|~{3,}")
WORDY = re.compile(r"[^\W_]")
C_ESCAPES = {"a": "\a", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v"}
# Each flag pins a setting a developer's git config could otherwise change.
DIFF = (
    "-c",
    "core.quotepath=off",
    "-c",
    "core.attributesFile=/dev/null",
    "diff",
    "--unified=0",
    "--inter-hunk-context=0",
    "--no-renames",
    "--diff-filter=ADMRT",
    "--src-prefix=a/",
    "--dst-prefix=b/",
    "--no-color",
    "--no-ext-diff",
    "--no-textconv",
)


@dataclass(frozen=True)
class CommentLine:
    text: str
    own_line: bool


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    rule: str
    text: str


def names_an_issue(text: str) -> bool:
    return ISSUE_REF.search(text) is not None


def dated(kind: str, text: str) -> bool:
    """A date outside backticks in a doc, or outside any quotes in a comment."""
    if kind == "doc":
        return DATE.search(BACKTICKS.sub("", text)) is not None
    return DATE.search(QUOTED.sub("", TRIPLE_QUOTES.sub(" ", text))) is not None


def without(line: str, spans: list[tuple[int, int]]) -> str:
    """The line with the given column spans cut out."""
    parts, previous = [], 0
    for start, end in spans:
        parts.append(line[previous:start])
        previous = end
    parts.append(line[previous:])
    return "".join(parts)


def scan(
    source: str,
    markers: tuple[str, ...],
    *,
    blocks: bool = False,
    quotes: str = "\"'",
    heredocs: bool = False,
) -> dict[int, CommentLine]:
    """Comment text per line for languages whose comments a line scanner can find."""
    found: dict[int, CommentLine] = {}
    heredoc_end: str | None = None
    in_block = False
    for number, line in enumerate(source.split("\n"), start=1):
        if heredoc_end is not None:
            if line.strip() == heredoc_end:
                heredoc_end = None
            continue
        spans: list[tuple[int, int]] = []
        i = 0
        if in_block:
            end = line.find("*/")
            in_block = end == -1
            i = len(line) if in_block else end + 2
            spans.append((0, i))
        quote: str | None = None
        while i < len(line):
            ch = line[i]
            if quote:
                if ch == "\\":
                    i += 2
                    continue
                if ch == quote:
                    quote = None
            elif ch in quotes:
                quote = ch
            elif blocks and line.startswith("/*", i):
                end = line.find("*/", i + 2)
                in_block = end == -1
                spans.append((i, len(line) if in_block else end + 2))
                i = spans[-1][1]
                continue
            elif any(line.startswith(m, i) for m in markers) and (
                ch != "#" or i == 0 or line[i - 1] in " \t"
            ):
                spans.append((i, len(line)))
                break
            i += 1
        code = without(line, spans)
        if spans:
            text = " ".join(line[start:end].strip() for start, end in spans)
            found[number] = CommentLine(text, not code.strip())
        if heredocs:
            match = HEREDOC.search(code)
            if match:
                heredoc_end = match.group(1)
    return found


def python_lines(source: str) -> dict[int, CommentLine]:
    """Comments and docstrings, from the tokenizer and the parse tree."""
    rows = source.split("\n")
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source)
    except (SyntaxError, ValueError, tokenize.TokenError):
        return scan(source, ("#",))
    found: dict[int, CommentLine] = {}
    for token in tokens:
        if token.type != tokenize.COMMENT:
            continue
        row, col = token.start
        if row == 1 and token.string.startswith("#!"):
            continue
        found[row] = CommentLine(token.string, not rows[row - 1][:col].strip())
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        first = node.body[0] if node.body else None
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            for row in range(first.lineno, (first.end_lineno or first.lineno) + 1):
                found[row] = CommentLine(rows[row - 1].strip(), True)
    return found


def markdown_lines(source: str) -> dict[int, CommentLine]:
    """Every prose line of a markdown file; fenced code blocks are skipped."""
    found: dict[int, CommentLine] = {}
    fence: str | None = None
    for number, line in enumerate(source.split("\n"), start=1):
        text = line.strip()
        if fence is None:
            opener = FENCE.match(text)
            if opener:
                fence = opener.group(0)
            else:
                found[number] = CommentLine(text, True)
        elif set(text) == {fence[0]} and len(text) >= len(fence):
            fence = None
    return found


def language(path: str) -> str | None:
    """The comment syntax of a file the policy covers, else None."""
    name = path.rsplit("/", 1)[-1]
    if name == ".gitignore":
        return "hash"
    suffix = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return {
        "md": "markdown",
        "py": "python",
        "sh": "shell",
        "bash": "shell",
        "yml": "shell",
        "yaml": "shell",
        "toml": "hash",
        "css": "css",
    }.get(suffix)


def counted(path: str) -> bool:
    """Whether the check reads this file at all."""
    return language(path) is not None


def classify(path: str, source: str) -> tuple[str, dict[int, CommentLine]] | None:
    """("doc" | "code", comment lines) for a file the policy covers, else None."""
    syntax = language(path)
    if syntax == "markdown":
        return "doc", markdown_lines(source)
    if syntax == "python":
        return "code", python_lines(source)
    if syntax == "shell":
        return "code", scan(source, ("#",), heredocs=True)
    if syntax == "hash":
        return "code", scan(source, ("#",))
    if syntax == "css":
        return "code", scan(source, (), blocks=True)
    return None


def check_file(path: str, source: str, added: set[int]) -> list[Violation]:
    classified = classify(path, source)
    if classified is None:
        return []
    kind, lines = classified
    found: list[Violation] = []
    for number in sorted(added):
        line = lines.get(number)
        if line is None:
            continue
        broken = ["issue or PR number"] if names_an_issue(line.text) else []
        if dated(kind, line.text):
            broken.append("date")
        if kind == "code":
            if ALARM.search(line.text):
                broken.append("alarm marker")
            if EARLIER_DRAFT.search(line.text):
                broken.append("note about an earlier draft")
        found.extend(Violation(path, number, rule, line.text) for rule in broken)
    if kind == "code":
        found.extend(long_blocks(path, lines, added))
    return found


def long_blocks(path: str, lines: dict[int, CommentLine], added: set[int]) -> list[Violation]:
    """A run of more than MAX_BLOCK_LINES added comment-only lines."""
    found: list[Violation] = []
    run_start = run = 0
    previous: int | None = None
    for number in sorted(added):
        line = lines.get(number)
        if line is not None and line.own_line:
            if run and previous == number - 1:
                run += 1
            else:
                run_start, run = number, 1
            if run == MAX_BLOCK_LINES + 1:
                rule = f"comment block over {MAX_BLOCK_LINES} lines"
                found.append(Violation(path, run_start, rule, lines[run_start].text))
        else:
            run = 0
        previous = number
    return found


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    ).stdout


def unquote(name: str) -> str:
    """Undo the C-style quoting git gives a path holding a quote, a backslash or a control byte."""
    if len(name) < 2 or not name.startswith('"') or not name.endswith('"'):
        return name
    return re.sub(
        r"\\([0-7]{3}|.)",
        lambda m: chr(int(m[1], 8)) if len(m[1]) == 3 else C_ESCAPES.get(m[1], m[1]),
        name[1:-1],
    )


def added_lines(repo: Path, base: str, counts: Callable[[str], bool] = counted) -> dict[str, set[int]]:
    """Line numbers each counted file gains, working tree included, since the branch left `base`.

    A line whose words the same diff removes somewhere, in any file, is a move or a re-indent,
    not new. A file `counts` rejects neither gains lines nor lends them.
    """
    merge_base = git(repo, "merge-base", base, "HEAD").strip()
    added: dict[str, dict[int, str]] = {}
    removed: Counter[str] = Counter()
    path: str | None = None
    lends = False
    old = new = number = 0
    for line in git(repo, *DIFF, merge_base).split("\n"):
        if old or new:
            if old and line.startswith("-"):
                if lends:
                    removed[line[1:].strip()] += 1
                old -= 1
            elif new and line.startswith("+"):
                if path is not None:
                    added.setdefault(path, {})[number] = line[1:].strip()
                number += 1
                new -= 1
            elif line.startswith(" "):
                old, new, number = old - 1, new - 1, number + 1
            continue
        if line.startswith("--- "):
            origin = unquote(line[4:].removesuffix("\t"))
            lends = origin.startswith("a/") and counts(origin[2:])
            continue
        if line.startswith("+++ "):
            target = unquote(line[4:].removesuffix("\t"))
            path = target[2:] if target.startswith("b/") and counts(target[2:]) else None
            continue
        hunk = HUNK.match(line)
        if hunk:
            old = int(hunk.group(1) or 1)
            number = int(hunk.group(2))
            new = int(hunk.group(3) or 1)
    for name in git(repo, "ls-files", "-z", "--others", "--exclude-standard").split("\0"):
        file = repo / name
        if name and counts(name) and file.is_file() and not file.is_symlink():
            rows = file.read_bytes().decode("utf-8", "replace").split("\n")
            added[name] = {n: row.strip() for n, row in enumerate(rows, start=1)}
    changes: dict[str, set[int]] = {}
    for name, rows_added in sorted(added.items()):
        for n, text in sorted(rows_added.items()):
            if WORDY.search(text) and removed[text]:
                removed[text] -= 1
            else:
                changes.setdefault(name, set()).add(n)
    return changes


def compared_bases(explicit: str | None, env: Mapping[str, str]) -> list[str]:
    """--base, or main plus the pull request's base when that is another branch.

    A stacked pull request's lines count only if they are new to main and to its base: its
    base alone blames the branch for lines main has and a trailing base lacks.
    """
    if explicit:
        return [explicit]
    target = env.get("GITHUB_BASE_REF")
    if not target or f"origin/{target}" == MAIN:
        return [MAIN]
    return [MAIN, f"origin/{target}"]


def main(argv: list[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    environment = os.environ if env is None else env
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--base", help=f"ref to compare with; {MAIN}, plus a stacked PR's base in CI")
    parser.add_argument("--repo", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    changes: dict[str, set[int]] | None = None
    for base in compared_bases(args.base, environment):
        try:
            found = added_lines(args.repo, base)
        except subprocess.CalledProcessError as exc:
            print(f"FAIL: cannot diff against {base}: {exc.stderr.strip()}", file=sys.stderr)
            return 2
        changes = (
            found
            if changes is None
            else {path: lines & found[path] for path, lines in changes.items() if path in found}
        )
    violations: list[Violation] = []
    for path, added in sorted((changes or {}).items()):
        file = args.repo / path
        if not added or file.is_symlink() or not file.is_file():
            continue
        try:
            source = file.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue
        violations.extend(check_file(path, source, added))
    checked = sum(len(lines) for lines in (changes or {}).values())
    if not violations:
        print(f"OK: {checked} added lines checked, none break the comment policy")
        return 0
    print(f"FAIL: {len(violations)} added line(s) break the comment policy\n", file=sys.stderr)
    for v in violations:
        print(f"  {v.path}:{v.line}: {v.rule}: {v.text[:120]}", file=sys.stderr)
    print(
        f"\nThe rules are in {POLICY}. History goes in the PR body, and a fact is linked to "
        "its home rather than restated.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
