"""Which mutants count, decided by where a constant sits rather than by what it says.

A string is RENDERING when only a person reads it and LOGIC when a machine does. That distinction is not in the characters — `'ok'`
is a `--json` field value and `'no runs recorded yet'` is a sentence — so it is read off the AST position: what call the constant is
an argument to, what keyword it is bound to, whether it is a docstring, which module it is in.

**A rendering mutant is planted and then excluded from the score.** Excluding it from the *run* would lose the one thing that
catches a suite gaming the score: a rendering mutant that dies means some test asserted on prose, which
`docs/development/testing.md` forbids. `score.PROSE_PINNED` is that fourth bucket.

**The default direction is deliberate.** A logic string wrongly marked rendering vanishes from the score with nothing to notice it.
A rendering string wrongly marked logic surfaces as a survivor, which a person reads and corrects. So every rule here is narrow,
everything unmatched is LOGIC, and `run.py --explain` prints the rule that decided each site so the classifier is audited rather
than trusted.
"""

from __future__ import annotations

import ast
import dataclasses
from collections.abc import Iterator
from pathlib import Path

LOGIC = 'logic'
RENDERING = 'rendering'

RULE_RENDER_MODULE = 'render-module'
RULE_DOCSTRING = 'docstring'
RULE_BARE_STRING = 'bare-string-statement'
RULE_RENDER_KEYWORD = 'render-keyword'
RULE_RENDER_CALL = 'render-call'
RULE_EXCEPTION_MESSAGE = 'exception-message'
RULE_RICH_STYLE = 'rich-style'
RULE_JSON_CONTRACT = 'json-contract'
RULE_EVENT_NAME = 'structlog-event-name'
RULE_CONTROL_FLOW = 'control-flow'
RULE_DEFAULT = 'default-logic'

RENDER_MODULES = frozenset({'output.py', 'banner.py', 'logging.py'})
"""Modules whose every constant is rendering.

Their subject *is* the sentence — a colour name, a column width, a tick mark, a log format. Nothing in them is read by a machine
except through a caller, and the caller's own constants are classified on their own merits.
"""

RENDER_PREFIXES = ('dotfiles.output.', 'dotfiles.banner.', 'rich.')
"""Dotted names whose arguments are prose.

Matched after the import table resolves the head, so `console.print` and `warn` both land here while a local named `output` in some
other module does not.
"""

RENDER_CONSTRUCTORS = frozenset({'rich.table.Table', 'rich.panel.Panel', 'rich.text.Text', 'rich.console.Console'})
"""Calls whose *return value* renders, so a local bound to one makes every method call on it a render call — `table.add_row(...)`."""

JSON_CONTRACT = frozenset({'dotfiles.output.emit_json'})
"""The one `output.*` call whose arguments are a machine contract rather than prose.

Every key in an `emit_json` payload is read by `jq` in a script somebody wrote, so mutating one is a real defect. Without this carve-out the
render-call rule would swallow the whole `--json` surface — which is the exact direction this module is written to avoid.
"""

EXCEPTION_MESSAGES = frozenset({'typer.BadParameter', 'ValueError', 'RuntimeError'})
"""Exceptions whose argument is a sentence.

Deliberately not `typer.Exit`, whose argument is an exit code and is the most machine-read value in the CLI.
"""

STRUCTLOG_FACTORIES = frozenset({'dotfiles.logging.get_logger', 'structlog.get_logger'})
"""What binds a name to a logger, so `log.info(...)` can be recognised without matching every `.info` in the repo."""

STYLE_WORDS = frozenset(
    {
        'on',
        'bold',
        'dim',
        'italic',
        'underline',
        'blink',
        'black',
        'red',
        'green',
        'yellow',
        'blue',
        'magenta',
        'cyan',
        'white',
        'bright_black',
        'bright_red',
        'bright_green',
        'bright_yellow',
        'bright_blue',
        'bright_magenta',
        'bright_cyan',
        'bright_white',
    }
)
"""A rich style phrase, for the colour that is assigned to a name before it reaches the call that renders it.

The one content rule here, and it is kept narrow on purpose: `default`, `reverse` and `strike` are rich styles too and are also
plausible values in a declaration, so they are left out and a mutation on one surfaces as a survivor instead of disappearing.
"""

RENDER_KEYWORDS = frozenset({'help', 'short_help', 'epilog', 'title', 'prompt', 'description'})
"""Keyword arguments whose value is shown to a person wherever they appear."""


@dataclasses.dataclass(frozen=True)
class Verdict:
    bucket: str
    rule: str


CONTROL_FLOW = Verdict(LOGIC, RULE_CONTROL_FLOW)
DEFAULT = Verdict(LOGIC, RULE_DEFAULT)


def renders_everything(path: Path) -> bool:
    return path.name in RENDER_MODULES and path.parent.name == 'dotfiles'


def package_of(path: Path) -> str:
    """The dotted package a module sits in, for resolving a relative import.

    Read off the path rather than off `__file__`, because the file being classified is a copy in a temporary directory as often as it is the
    checkout's own.
    """
    parts = list(path.resolve().parts)
    if 'src' not in parts:
        return ''
    return '.'.join(parts[parts.index('src') + 1 : -1])


def import_table(tree: ast.AST, path: Path) -> dict[str, str]:
    """Local name to dotted name, which is what makes `warn` and `output.warn` the same question."""
    package = package_of(path)
    table: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                table[alias.asname or alias.name.split('.')[0]] = alias.name if alias.asname else alias.name.split('.')[0]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ''
            if node.level:
                trimmed = package.split('.')[: len(package.split('.')) - (node.level - 1)] if package else []
                base = '.'.join([*trimmed, base]) if base else '.'.join(trimmed)
            for alias in node.names:
                table[alias.asname or alias.name] = f'{base}.{alias.name}' if base else alias.name
    return table


def dotted(node: ast.AST, table: dict[str, str]) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return ''
    parts.append(node.id)
    parts.reverse()
    return '.'.join([table.get(parts[0], parts[0]), *parts[1:]])


def _bound_by(tree: ast.AST, table: dict[str, str], wanted: frozenset[str]) -> set[str]:
    """Local names assigned the result of one of `wanted`."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        if dotted(node.value.func, table) not in wanted:
            continue
        found.update(target.id for target in node.targets if isinstance(target, ast.Name))
    return found


def docstring_rules(tree: ast.AST) -> dict[int, str]:
    """Every bare string statement, and which of the two docstring rules names it.

    `ast.get_docstring` answers for a module, a class and a function. It does not answer for the attribute docstring — a bare string
    statement following an assignment — which this repo uses on nearly every module constant, and which is prose by exactly the same
    argument.
    """
    found: dict[int, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) and ast.get_docstring(node) is not None:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                found[id(first.value)] = RULE_DOCSTRING
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            found.setdefault(id(node.value), RULE_BARE_STRING)
    return found


def is_style(value: str) -> bool:
    words = value.split()
    return bool(words) and words != ['on'] and all(word in STYLE_WORDS for word in words)


def _call_contexts(node: ast.Call, table: dict[str, str], receivers: set[str], loggers: set[str]) -> tuple[Verdict | None, Verdict | None]:
    """What this call's arguments inherit, as `(first positional, everything else)`.

    They differ for one caller. A structlog event name is compared against a literal by `sinks` and by `report._slow_commands`, so
    it is read by a machine and is logic; everything else in the same call is the sentence beside it.
    """
    name = dotted(node.func, table)
    if name in JSON_CONTRACT:
        return Verdict(LOGIC, RULE_JSON_CONTRACT), Verdict(LOGIC, RULE_JSON_CONTRACT)
    if name in EXCEPTION_MESSAGES:
        message = Verdict(RENDERING, RULE_EXCEPTION_MESSAGE)
        return message, message
    if _is_logger_call(node.func, loggers):
        return Verdict(LOGIC, RULE_EVENT_NAME), Verdict(RENDERING, RULE_RENDER_CALL)
    if name.startswith(RENDER_PREFIXES) or _is_receiver_call(node.func, receivers):
        rendering = Verdict(RENDERING, RULE_RENDER_CALL)
        return rendering, rendering
    return None, None


def _is_receiver_call(func: ast.AST, receivers: set[str]) -> bool:
    return isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id in receivers


def _is_logger_call(func: ast.AST, loggers: set[str]) -> bool:
    return isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id in loggers


def _children(
    node: ast.AST, inherited: Verdict | None, table: dict[str, str], receivers: set[str], loggers: set[str]
) -> Iterator[tuple[ast.AST, Verdict | None]]:
    if isinstance(node, ast.keyword):
        yield from (
            (child, Verdict(RENDERING, RULE_RENDER_KEYWORD) if node.arg in RENDER_KEYWORDS else inherited)
            for child in ast.iter_child_nodes(node)
        )
        return
    if isinstance(node, ast.comprehension):
        # What a comprehension draws from is control data wherever it sits. `table.add_row(*(str(row[key]) for key in
        # ('runs', 'total', 'median', 'slowest')))` renders the strings it produces and subscripts a dict with the ones it
        # reads, and only the second half is a contract. Caught by the prose-pinned counter rather than by inspection: all
        # four died, which a rendering mutant is not supposed to do.
        yield node.iter, DEFAULT
        yield from ((test, DEFAULT) for test in node.ifs)
        yield node.target, inherited
        return
    if isinstance(node, ast.Call):
        first, rest = _call_contexts(node, table, receivers, loggers)
        yield node.func, inherited
        for position, argument in enumerate(node.args):
            yield argument, (first if position == 0 else rest) if first is not None or rest is not None else inherited
        for keyword in node.keywords:
            yield keyword, rest if rest is not None else inherited
        return
    yield from ((child, inherited) for child in ast.iter_child_nodes(node))


def _constant_verdict(node: ast.Constant, inherited: Verdict | None, docstrings: dict[int, str], whole_file: bool) -> Verdict:
    if whole_file:
        return Verdict(RENDERING, RULE_RENDER_MODULE)
    if id(node) in docstrings:
        return Verdict(RENDERING, docstrings[id(node)])
    if inherited is not None:
        return inherited
    if isinstance(node.value, str) and is_style(node.value):
        return Verdict(RENDERING, RULE_RICH_STYLE)
    return DEFAULT


def annotate(tree: ast.AST, path: Path) -> dict[int, Verdict]:
    """Every node a mutation operator applies to, keyed by `id`, with the rule that decided it.

    Keyed by identity because the caller holds this exact tree — `planter.mutable` walks the same object — rather than a re-parse of it.
    """
    table = import_table(tree, path)
    receivers = _bound_by(tree, table, RENDER_CONSTRUCTORS)
    loggers = _bound_by(tree, table, STRUCTLOG_FACTORIES)
    docstrings = docstring_rules(tree)
    whole_file = renders_everything(path)
    verdicts: dict[int, Verdict] = {}

    def descend(node: ast.AST, inherited: Verdict | None) -> None:
        if isinstance(node, ast.Constant):
            verdicts[id(node)] = _constant_verdict(node, inherited, docstrings, whole_file)
        elif isinstance(node, ast.Compare | ast.BoolOp | ast.UnaryOp):
            verdicts[id(node)] = CONTROL_FLOW
        for child, context in _children(node, inherited, table, receivers, loggers):
            descend(child, context)

    descend(tree, None)
    return verdicts
