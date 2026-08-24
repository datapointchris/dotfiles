#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# ///
"""List tests whose assertions a broken run would also satisfy.

`standards/testing.md` § "A passing check is evidence only when failing would
have looked different" is the rule. This is the sweep that applies it to one
shape of it — the shape that can be found mechanically.

**The shape**: every assertion in the test is a *negative claim about an external
effect* — a file absent, a stream empty, a directory unwritten — and nothing in
the test pins how the run ended. A command that died before reaching the write
leaves exactly that state, so the test is green either way.

**Not every hit is a defect.** `assert settings() == {}` is safe even though it
is negative: a crash raises and fails the test, so the empty dict is only
reachable by the code deciding on it. What makes the shape dangerous is the
effect being *outside* the process, where "it did not happen" and "we never got
there" are the same observation. Read each hit and ask which one it is.

**The repair is one line**, and it is almost always already in the file: capture
the result and assert it succeeded, plus one positive fact the run should have
left behind.

Deliberately narrow. It finds the confounded-observation shape only where an AST
can see it, and says nothing about the other shape the rule names — a sweep over
a hand-written list that omits the failing cases. That one needs a person who
knows what the list left out.
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

EFFECT = ('exists()', 'is_file()', 'is_dir()', 'stdout', 'stderr', 'read_text()', 'iterdir()', 'listdir')
"""Assertions about something outside the process, where absence is ambiguous."""

NEGATIVE = ('not ', '== []', "== ''", '== {}', '== 0', 'is None', 'is False')

STATUS = ('returncode', 'exit_code', 'ExitCode', 'raises', 'SystemExit', '.ok', 'result.ok')
"""Anything pinning how the run ended, which is what makes the absence mean something."""


def undiscriminating(path: Path) -> list[tuple[int, str, list[str]]]:
    try:
        tree = ast.parse(path.read_text())
    except (SyntaxError, UnicodeDecodeError):
        return []
    lines = path.read_text().splitlines()

    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith('test_'):
            continue
        checks = [n for n in ast.walk(node) if isinstance(n, ast.Assert)]
        if not checks:
            continue
        rendered = [lines[check.lineno - 1].strip() for check in checks]
        if not any(any(effect in line for effect in EFFECT) for line in rendered):
            continue
        if not all(any(marker in line for marker in NEGATIVE) for line in rendered):
            continue
        body = '\n'.join(lines[node.lineno - 1 : (node.end_lineno or node.lineno)])
        if any(status in body for status in STATUS):
            continue
        found.append((node.lineno, node.name, rendered))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--tests', default='tests', help='directory of tests to sweep (default tests)')
    parsed = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    total = 0
    for path in sorted((root / parsed.tests).rglob('test_*.py')):
        for line, name, rendered in undiscriminating(path):
            total += 1
            print(f'{path.relative_to(root)}:{line}  {name}')
            for assertion in rendered:
                print(f'    {assertion}')
            print()

    print(f'{total} tests assert only that an external effect did not happen.')
    print('Each is a question, not a verdict — read it and ask what else leaves it green.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
