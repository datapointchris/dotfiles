"""The mutation operators, and the one walk every other module counts sites in.

A site's identity is its ordinal in `mutable`, so the classifier, the planner and the planter have to traverse a module the same way
— which is why the traversal lives here once rather than being rewritten in each of them. `sites` and `plant` both enumerate the
same generator, so index *n* names the same node in both.

**A skipped site is still a site.** The first prototype dropped string constants of forty characters or more without saying so,
which silently excluded every long logic string from the score. Anything the harness will not plant is enumerated, counted and given
a reason.
"""

from __future__ import annotations

import ast
import dataclasses
from collections.abc import Iterator
from pathlib import Path

MARKER = '-mutant'
"""Appended to a string constant to mutate it.

Long enough that no equality, membership or suffix test can pass by accident, short enough to read in a report, and absent from this
repo's source so a survivor's effect is greppable.
"""

SWAP_COMPARISON: dict[type[ast.cmpop], type[ast.cmpop]] = {
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.Lt: ast.GtE,
    ast.GtE: ast.Lt,
    ast.Gt: ast.LtE,
    ast.LtE: ast.Gt,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
    ast.Is: ast.IsNot,
    ast.IsNot: ast.Is,
}

COMPARISON = 'comparison'
BOOLEAN_OPERATOR = 'boolean-operator'
NEGATION = 'negation'
BOOLEAN = 'bool'
INTEGER = 'int'
FLOATING = 'float'
STRING = 'string'

ANNOTATION = 'annotation'
"""Why an annotation site is never planted.

Both target files carry `from __future__ import annotations`, so an annotation is a string the interpreter never evaluates and a
mutation inside one cannot change what the program does. Counting those as survivors would credit the suite with a gap that does not
exist.
"""

UNPARSEABLE = 'unparseable'


@dataclasses.dataclass(frozen=True)
class Site:
    """One place a bug can be planted, named by where it is rather than by what is around it."""

    index: int
    lineno: int
    col: int
    kind: str
    description: str
    skipped: str = ''


@dataclasses.dataclass(frozen=True)
class Held:
    """A node together with where it hangs off its parent, which is what `not` removal needs to replace it."""

    node: ast.AST
    parent: ast.AST | None
    field: str
    slot: int


def walk(node: ast.AST, parent: ast.AST | None = None, field: str = '', slot: int = -1) -> Iterator[Held]:
    """Pre-order, in field order. Deterministic for one source text, which is the whole requirement."""
    yield Held(node, parent, field, slot)
    for name, value in ast.iter_fields(node):
        if isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, ast.AST):
                    yield from walk(item, node, name, index)
        elif isinstance(value, ast.AST):
            yield from walk(value, node, name, -1)


def annotation_nodes(tree: ast.AST) -> set[int]:
    """Every node underneath an `annotation` or `returns` field."""
    found: set[int] = set()
    for held in walk(tree):
        for name, value in ast.iter_fields(held.node):
            if name not in ('annotation', 'returns') or not isinstance(value, ast.AST):
                continue
            found.update(id(inner.node) for inner in walk(value))
    return found


def _mutation(node: ast.AST) -> tuple[str, str] | None:
    """The kind and the description, or None where no operator applies."""
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in SWAP_COMPARISON:
        operator = type(node.ops[0])
        return COMPARISON, f'{operator.__name__} -> {SWAP_COMPARISON[operator].__name__}'
    if isinstance(node, ast.BoolOp):
        spelled, flipped = ('and', 'or') if isinstance(node.op, ast.And) else ('or', 'and')
        return BOOLEAN_OPERATOR, f'{spelled} -> {flipped}'
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return NEGATION, 'drop not'
    if isinstance(node, ast.Constant):
        return _constant_mutation(node.value)
    return None


def _constant_mutation(value: object) -> tuple[str, str] | None:
    if isinstance(value, bool):
        return BOOLEAN, f'{value} -> {not value}'
    if isinstance(value, int):
        return INTEGER, f'{value} -> {value + 1}'
    if isinstance(value, float):
        return FLOATING, f'{value} -> {value + 1.0}'
    if isinstance(value, str):
        return STRING, f'{_short(value)} -> {_short(value + MARKER)}'
    return None


def _short(value: str) -> str:
    rendered = repr(value)
    return rendered if len(rendered) <= 48 else f'{rendered[:45]}…'


def mutated(value: object) -> str | bool | int | float:
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if isinstance(value, float):
        return value + 1.0
    if isinstance(value, str):
        return value + MARKER
    raise TypeError(f'no operator for {type(value).__name__}')


def mutable(tree: ast.AST) -> Iterator[tuple[Held, str, str, str]]:
    """Every site, in walk order, as `(held, kind, description, skip reason)`."""
    skippable = annotation_nodes(tree)
    for held in walk(tree):
        found = _mutation(held.node)
        if found is None:
            continue
        kind, description = found
        yield held, kind, description, ANNOTATION if id(held.node) in skippable else ''


def sites(tree: ast.AST) -> list[Site]:
    return [
        Site(
            index=index,
            lineno=getattr(held.node, 'lineno', 0),
            col=getattr(held.node, 'col_offset', 0),
            kind=kind,
            description=description,
            skipped=skipped,
        )
        for index, (held, kind, description, skipped) in enumerate(mutable(tree))
    ]


def _replace(held: Held, replacement: ast.AST) -> None:
    if held.parent is None:
        raise ValueError('a site with no parent cannot be replaced')
    if held.slot < 0:
        setattr(held.parent, held.field, replacement)
        return
    getattr(held.parent, held.field)[held.slot] = replacement


def _plant_into(held: Held) -> None:
    node = held.node
    if isinstance(node, ast.Compare):
        node.ops = [SWAP_COMPARISON[type(node.ops[0])]()]
        return
    if isinstance(node, ast.BoolOp):
        node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
        return
    if isinstance(node, ast.UnaryOp):
        _replace(held, node.operand)
        return
    if isinstance(node, ast.Constant):
        _replace(held, ast.Constant(value=mutated(node.value)))
        return
    raise TypeError(f'no operator for {type(node).__name__}')


def plant(source: str, index: int) -> str:
    """The source with site *index* mutated, as text.

    Re-parsed rather than mutated in place on a shared tree, so one planted bug cannot leak into the next mutant.
    """
    tree = ast.parse(source)
    for position, (held, _, _, _) in enumerate(mutable(tree)):
        if position != index:
            continue
        _plant_into(held)
        ast.fix_missing_locations(tree)
        return ast.unparse(tree)
    raise IndexError(f'no site {index}')


def round_trip(source: str) -> str:
    """The source as `plant` would emit it with nothing mutated.

    What the control run measures. `ast.unparse` drops comments and re-quotes every string, so a suite that passes against the
    original and fails against this is failing on the round trip rather than on any planted bug — and every mutant after it would
    read as killed.
    """
    return ast.unparse(ast.parse(source))


def read(path: Path) -> str:
    return path.read_text()
