#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# ///
"""List tests whose assertions a broken run would also satisfy.

A passing check is evidence only when failing would have looked different. This is
the sweep that applies that to one shape of it — the shape that can be found
mechanically.

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
left behind. An assertion that nothing happened is satisfied by a crash, so the
form is the exit code it expects plus one positive
fact — and it has no exemption clause, so there is nothing here to mark a hit
exempt with. A hit is repaired or it is a finding.

Exits non-zero above `--max`, which defaults to zero, so it gates.

Deliberately narrow, and it fails silent rather than loud. `EFFECT` is an
allow-list, so a read it cannot name — `envfile.read_generated(path)` is the live
one — reads as *not external* rather than as *unknown*, and one of those in a
test exempts the whole test. Loosening the composition trades that at about ten
to one: `any(external(...))` reports eleven more tests, and ten are the
return-value case named safe above. So the blind spot is kept and written down.

It also says nothing about the other shape the rule names — a sweep over a
hand-written list that omits the failing cases. That one needs a person who knows
what the list left out.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

EFFECT = ('exists', 'is_file', 'is_dir', 'stdout', 'stderr', 'read_text', 'iterdir', 'listdir')
"""Names that reach outside the process, where absence is ambiguous."""

STATUS = ('returncode', 'exit_code', 'ExitCode', 'raises', 'SystemExit', '.ok', 'result.ok')
"""Anything pinning how the run ended, which is what makes the absence mean something."""


def absent(node: ast.expr) -> bool:
    """Is this the nothing on the right of a comparison?

    An empty container display or a falsy constant. `0` and `False` are one value
    to `in`, which costs nothing here — both are the same claim.
    """
    if isinstance(node, ast.List | ast.Tuple | ast.Set):
        return not node.elts
    if isinstance(node, ast.Dict):
        return not node.keys
    return isinstance(node, ast.Constant) and node.value in (None, False, 0, '')


def claims(test: ast.expr) -> list[ast.expr]:
    """The separate claims in one assertion.

    `assert not a.exists() and not b.exists()` is two assertions written as one,
    and is judged as two. Without this the whole test is skipped, because a
    `BoolOp` is neither a `UnaryOp` nor a `Compare` and reads as positive.
    """
    if isinstance(test, ast.BoolOp):
        return [claim for value in test.values for claim in claims(value)]
    return [test]


def negative(test: ast.expr) -> bool:
    """Does the assertion claim that something is not there?

    Read off the tree rather than the source line. `assert 'not present' in
    ran.stdout` is a *positive* claim whose text carries the word, and matching
    the line would call three of those a finding.
    """
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return True
    if not isinstance(test, ast.Compare):
        return False
    if any(isinstance(operator, ast.NotIn) for operator in test.ops):
        return True
    return any(isinstance(operator, ast.Is | ast.Eq) and absent(right) for operator, right in zip(test.ops, test.comparators, strict=True))


def external(test: ast.expr) -> bool:
    """Does the assertion read something outside the process?"""
    return any(
        (isinstance(node, ast.Attribute) and node.attr in EFFECT) or (isinstance(node, ast.Name) and node.id in EFFECT)
        for node in ast.walk(test)
    )


def code(node: ast.FunctionDef) -> str:
    """The function with its docstring dropped, which is what STATUS is read against.

    A docstring explaining that the config *raises* on startup would otherwise
    exempt the test from the sweep, and one did.
    """
    body = node.body[1:] if ast.get_docstring(node) else node.body
    return '\n'.join(ast.unparse(statement) for statement in body)


def undiscriminating(path: Path) -> list[tuple[int, str, list[str]]]:
    try:
        text = path.read_text()
        tree = ast.parse(text)
    except (SyntaxError, UnicodeDecodeError):
        return []

    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith('test_'):
            continue
        checks = [child for child in ast.walk(node) if isinstance(child, ast.Assert)]
        if not checks:
            continue
        parts = [claim for check in checks for claim in claims(check.test)]
        if not all(negative(part) and external(part) for part in parts):
            continue
        if any(marker in code(node) for marker in STATUS):
            continue
        rendered = [' '.join((ast.get_source_segment(text, check) or '').split()) for check in checks]
        found.append((node.lineno, node.name, rendered))
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--tests', default='tests', help='directory of tests to sweep (default tests)')
    parser.add_argument('--max', type=int, default=0, help='exit non-zero above this many findings (default 0)')
    parsed = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    where = Path(parsed.tests) if Path(parsed.tests).is_absolute() else root / parsed.tests

    total = 0
    for path in sorted(where.rglob('test_*.py')):
        named = path.relative_to(root) if path.is_relative_to(root) else path
        for line, name, rendered in undiscriminating(path):
            total += 1
            print(f'{named}:{line}  {name}')
            for assertion in rendered:
                print(f'    {assertion}')
            print()

    print(f'{total} tests assert only that an external effect did not happen.', flush=True)
    if total > parsed.max:
        print('Pair each with the exit code it expects and one positive fact the run should have left.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
