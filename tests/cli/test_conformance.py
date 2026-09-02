"""The grammar is a contract, so it is asserted rather than reviewed.

Every command in the tree is walked and its name checked against the closed
vocabulary in `dotfiles.vocabulary`. That makes adding a verb an edit to a
documented list with a written reason, instead of something that happens by
accident on one subcommand and nowhere else — which is how `link`/`relink`,
`--dry-run`, `--force` and `--mine` each came to mean something slightly
different depending on where they were typed.

Nothing here invokes a command. Some tests inspect the built app and others render
a report into a buffer from fabricated results, so nothing reads or writes the
machine's own state.
"""

from __future__ import annotations

import ast
import datetime as dt
import functools
import importlib
import io
import pkgutil
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import click
import pytest
from rich.console import Console
from typer.main import get_command

import dotfiles
from dotfiles import create_bundle
from dotfiles import offline_bundle
from dotfiles import output
from dotfiles import reconcile
from dotfiles import registry
from dotfiles import remote
from dotfiles import resources
from dotfiles import vocabulary
from dotfiles.commands import staging
from dotfiles.main import app
from dotfiles.plan import Stage
from dotfiles.resources import Change
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.results import Lens
from dotfiles.results import ResourceResult
from dotfiles.results import ResourceVerdict


def walk(command: click.Command, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], click.Command]]:
    """Every command in the tree, with the path it is reached by."""
    found = [(path, command)] if path else []
    if isinstance(command, click.Group):
        for name, child in command.commands.items():
            found.extend(walk(child, (*path, name)))
    return found


TREE = walk(get_command(app))
LEAVES = [(path, cmd) for path, cmd in TREE if not isinstance(cmd, click.Group)]
GROUPS = [(path, cmd) for path, cmd in TREE if isinstance(cmd, click.Group)]


ACCEPTED = {
    path: {option for parameter in command.params for option in (*parameter.opts, *parameter.secondary_opts)} for path, command in LEAVES
}
"""Every leaf's option names, derived once.

Built here rather than inside each test because five of them ask the same
question of the whole tree, and a policy asserted against its own private copy of
the surface is a policy that can disagree with its neighbor about what the
surface is.

`secondary_opts` as well as `opts`, or a `--refresh/--cached` pair is half
invisible. click keeps the negative spelling of a boolean flag there, so a policy
about `--cached` asserted against `opts` alone could not fail whatever the tree
said — and this file already carries a rule about `--refresh`.
"""


def _branches_on_refresh(resource: str) -> bool:
    """Whether this resource's own module reads `session.refresh`.

    `packages` and `plugins` do. `system` does not and still depends on it, which
    is why this is one of two sources below rather than the answer.
    """
    module = Path(resources.__file__).parent / f'{resource}.py'
    return module.is_file() and 'session.refresh' in module.read_text()


CURRENCY_RESOURCES = frozenset(
    {provider.resource for provider in registry.PROVIDERS if isinstance(provider, registry.ManagerProvider)}
    | {resource for resource in {provider.resource for provider in registry.PROVIDERS} if _branches_on_refresh(resource)}
)
"""Every resource whose answer changes with whether the run measured upstream.

Two sources because there are two ways to depend on it, and a grep finds only one.
`packages` and `plugins` branch on `session.refresh` in their own modules;
`system` never names it — it carries a `ManagerProvider` row whose verdict comes
from `evidence.by_currency`, which reads an inventory built from the session's
answer one level down. Reading the resource modules alone reports `system` as
currency-free, which is exactly how it came to have no flag for a release.

Derived rather than listed, because a surface invariant comes from the command
tree: a table cannot tell "nobody added a networked resource"
from "somebody added one and nothing looked".
"""


RECONCILING = [(path, command) for path, command in LEAVES if path[-1] in {'plan', 'check', 'apply'}]
"""Every `plan`, `check` and `apply` in the tree, with no exceptions carved out.

The first cut of this rule kept `network check` and `bundle check` outside it, on
the stated grounds that neither emits through `effects`. That was measured
afterwards and is false: `network.py` references `effects` six times and
`offline_bundle.py` twice. Only `machines check` really does not, and `-q` still
means something there because the finding rows it suppresses are rendered the same
way.

So the rule is the verb, not the subject. A reader who learns `-v` on one
`check` has learned it everywhere, which is worth more than sparing a few leaves a
flag."""


STAGING = [(path, command) for path, command in LEAVES if path[0] in {'bundle', 'status', 'remote'}]
"""Every leaf of the offline loop, which renders evidence rows to a terminal.

Scoped to these three groups rather than to the whole tree, and the boundary is
measured rather than chosen: the read-only `show`/`list`/`path` leaves elsewhere
do not take the pair either, and giving it to all of them is a change larger than
the feature that surfaced the question. What this asserts is that the loop is
internally consistent, which is the asymmetry `--dry-run` and `--force` each grew
one subcommand at a time.
"""

VERBOSE = sorted({*RECONCILING, *STAGING}, key=lambda entry: entry[0])
"""Every leaf that owes `-v` and `-q`, from both selectors, deduplicated.

One list because there is one rule. `RECONCILING` selects by verb and `STAGING`
by group, and `bundle check` and `remote check` are in both — asserted twice by
two copies of one assertion, with nothing comparing the copies. A change to what
the pair means would have to find both, and the second is the one whose selector
is a literal.
"""


def test_the_tree_is_not_empty() -> None:
    """Guards every other test here: a walk that finds nothing passes vacuously.

    Every derived list, because a parametrization that collects nothing reports
    `1 skipped` rather than a failure — so renaming a group would remove a
    conformance policy and leave the suite green.
    """
    assert len(LEAVES) > 20
    assert len(GROUPS) == len(vocabulary.NOUNS)
    assert len(RECONCILING) > 15
    assert len(STAGING) > 10
    assert len(VERBOSE) >= len(RECONCILING)


@pytest.mark.parametrize(('path', 'command'), VERBOSE, ids=lambda value: '/'.join(value) if isinstance(value, tuple) else '')
def test_every_leaf_that_owes_the_verbosity_pair_takes_it(path: tuple[str, ...], command: click.Command) -> None:
    """A flag that works on `dotfiles apply` and not on `dotfiles packages apply`
    is the drift this file exists to catch — the same asymmetry `--dry-run` and
    `--force` had, one subcommand at a time. `bundle create` is the loudest verb
    in the offline loop and was one of two there with no way to quieten it."""
    flags = {name for param in command.params for name in param.opts}
    assert {'-v', '--verbose'} <= flags, f'`dotfiles {" ".join(path)}` cannot be turned up'
    assert {'-q', '--quiet'} <= flags, f'`dotfiles {" ".join(path)}` cannot be quietened'


@pytest.mark.parametrize(('path', 'command'), LEAVES, ids=lambda value: '/'.join(value) if isinstance(value, tuple) else '')
def test_every_leaf_is_a_documented_verb(path: tuple[str, ...], command: click.Command) -> None:
    verb = path[-1]
    assert verb in vocabulary.VERBS, (
        f'`dotfiles {" ".join(path)}` uses the verb {verb!r}, which is not in the closed vocabulary. '
        f'Add it to CORE_VERBS, or to EXCEPTION_VERBS with the reason it cannot be one of '
        f'{vocabulary.CORE_VERBS}.'
    )


@pytest.mark.parametrize(('path', 'group'), GROUPS, ids=lambda value: '/'.join(value) if isinstance(value, tuple) else '')
def test_every_group_is_a_documented_noun(path: tuple[str, ...], group: click.Group) -> None:
    assert path[-1] in vocabulary.NOUNS


def test_every_documented_exception_is_actually_used() -> None:
    """An exception nobody uses is a license left lying around.

    The list is what a reviewer reads to decide whether a new verb is justified,
    so a stale entry makes the bar look lower than it is.
    """
    used = {path[-1] for path, _ in LEAVES}
    unused = set(vocabulary.EXCEPTION_VERBS) - used
    assert not unused, f'documented but unused: {sorted(unused)}'


def test_every_resource_offers_check() -> None:
    """`check` is what makes a resource a resource: it can say whether it matches."""
    leaves = {(path[0], path[-1]) for path, _ in LEAVES if len(path) == 2}
    for resource in vocabulary.RESOURCES:
        assert (resource, 'check') in leaves, f'{resource} has no check'


CHECKED_ONLY = {'identity', 'auth', 'credentials'}
"""The resources with nothing for `apply` to write, and the reason is nearly the
same for all three: what they measure is personal and arrives by hand. An identity
is per-machine, so the repo holds no value for it; a login is a browser flow, a
password or a device code, so `apply` attempting one would put a prompt in front
of every headless box. `credentials` is the odd one — its findings are not
personal but they are not the repo's either, since a helper that will not start is
a fault in the machine underneath git. Naming them here is what stops `apply`
being added to any of them later on the grounds that the set looked incomplete."""


def test_apply_exists_wherever_drift_can_be_fixed() -> None:
    leaves = {(path[0], path[-1]) for path, _ in LEAVES if len(path) == 2}
    for resource in vocabulary.RESOURCES:
        has_apply = (resource, 'apply') in leaves
        assert has_apply is (resource not in CHECKED_ONLY), f'{resource}: unexpected apply={has_apply}'


def test_machine_and_offline_bind_to_leaves_not_groups() -> None:
    """Click parses group options before the subcommand name, so `dotfiles apply
    --machine X` — the exact line a bootstrap runs — would raise `No such option`
    if these were declared on the callback."""
    for path, group in GROUPS:
        names = {option for parameter in group.params for option in parameter.opts}
        assert '--machine' not in names, f'{"/".join(path) or "root"} declares --machine on the group'
        assert '--offline' not in names, f'{"/".join(path) or "root"} declares --offline on the group'


SELECTORS = ('--machine', '--source', '--owner', '--package', '--offline')
"""Options that narrow *what* a verb covers, rather than how it writes.

`--offline` belongs here despite reading as a write instruction: under the flag the
staged bundle *is* the upstream every currency verdict is measured against, so it
changes what the answer is rather than narrowing the write. A plan that ignores it
rehearses a different run, which is the defect this test exists for.

`--reinstall` is the genuine member of the other group, and the split is what made
that clean: it used to take a name, which put a narrowing inside a force flag and
left it a member of both groups at once. Bare, it adds work to whatever the
selectors above left, so there is no reading of a machine it could change.
"""


def test_plan_accepts_every_selector_its_apply_does() -> None:
    """`plan` answers "what would `apply` change", so a scope the write accepts and
    the read cannot express is not a narrower preview — it is no preview at all.

    An `apply` taking `--source` and `--owner` where its `plan` takes neither
    leaves the narrow write most worth rehearsing as the one with no rehearsal
    available. Asserted across the tree rather than for one pair, because the gap
    opened by adding a selector to one verb and forgetting
    the other, and nothing but this notices.
    """
    for path, options in ACCEPTED.items():
        if path[-1] != 'apply' or (preview := ACCEPTED.get((*path[:-1], 'plan'))) is None:
            continue
        missing = {selector for selector in SELECTORS if selector in options} - preview
        assert not missing, f'{"/".join(path)} accepts {sorted(missing)}, which its plan cannot express'


def test_check_takes_offline_wherever_apply_does() -> None:
    """`--offline` swaps the upstream for a staged bundle, so it changes what every
    verb *answers* rather than narrowing what one covers.

    Asserted for this flag alone, and not by widening the selector test above.
    `check` deliberately does not take `--source` or `--owner` — that was decided
    against on the symmetry argument, because narrowing what is examined is a
    different act from changing what the examination compares against. Nothing
    pinned this pair, so `dotfiles check --offline` existed while
    `dotfiles packages check --offline` did not, and the test written for exactly
    this class of gap could not see it.

    No verb is exempt. `windows` was, because its `check` asked which filenames
    exist in one directory and reached no network for the answer — and it left
    with the group.
    """
    for path, options in ACCEPTED.items():
        if path[-1] != 'apply' or '--offline' not in options:
            continue
        examined = ACCEPTED.get((*path[:-1], 'check'))
        if examined is None:
            continue
        assert '--offline' in examined, f'{"/".join(path)} takes --offline, which its check cannot express'


def test_no_leaf_offers_dry_run() -> None:
    """`check` is `apply` with the last step not run, so there is no code path a
    flag could switch off. A `--dry-run` would have to be a second implementation."""
    for path, command in LEAVES:
        names = {option for parameter in command.params for option in parameter.opts}
        assert '--dry-run' not in names, f'{"/".join(path)} offers --dry-run'


# ─────────────────────────────────────────────────────────────────────────────
# Which verb may take which flag
# ─────────────────────────────────────────────────────────────────────────────
#
# Each of these was pinned by one literal invocation in `tests/matrix/`, asserting
# that one command rejected one flag. The rule in every case is about the whole
# tree, and a three-row list is silent about a fourth resource in exactly the way
# a fourth that conforms is — so the list cannot tell "nobody added one" from
# "somebody added one and nothing looked".


def test_no_read_verb_offers_a_ceiling() -> None:
    """A ceiling bounds how far a machine *converges*, and neither read verb
    converges anything. Offering one would preview a subset of a walk that reads
    the whole machine either way.

    Asserted of `plan` and `check` rather than of `apply`, because the rule is
    what a read verb may not have. Only the top-level `apply` offers one today and
    a resource-scoped ceiling would be meaningless, but that is a separate claim
    and stating it here would make this test fail for the wrong reason.
    """
    for path, options in ACCEPTED.items():
        if path[-1] in {'plan', 'check'}:
            assert '--through' not in options, f'{"/".join(path)} is a read verb offering a ceiling'


def test_no_read_verb_offers_force() -> None:
    """`--force` authorizes a write that cannot be undone — a foreign file replaced,
    a package removed — so it belongs on the verb that writes and nowhere else.
    A flag appears only on the commands that read it.

    Over the whole tree rather than over the one resource that has it today, which
    is the difference this section exists for: a literal list of resources cannot
    tell "nobody added one" from "somebody added one and nothing looked".
    """
    for path, options in ACCEPTED.items():
        if path[-1] in {'plan', 'check'}:
            assert '--force' not in options, f'{"/".join(path)} is a read verb offering --force'


def test_no_apply_offers_refresh_because_every_apply_already_refreshes() -> None:
    """`apply` resolves with `refresh=not offline`, so being current is not
    something a caller opts into. An install writes a version onto the machine, and
    the cached answer it would otherwise trust is the one it was just told to
    distrust.

    That `apply` really does reach upstream is behavior and cannot be derived from
    the tree; `tests/matrix/test_composite.py` measures it.
    """
    for path, options in ACCEPTED.items():
        if path[-1] == 'apply':
            assert '--refresh' not in options, f'{"/".join(path)} offers --refresh, which it cannot decline to do'


def test_the_currency_flag_is_always_the_whole_pair() -> None:
    """One axis, two spellings, and a verb offering one of them is a verb a caller
    cannot reverse.

    Derived rather than listed, because a surface invariant comes from the command
    tree: a table naming which verbs take the pair cannot tell
    "nobody added a door" from "somebody added one and nothing looked". Six leaves
    gained the pair in one branch, each by hand.
    """
    for path, options in ACCEPTED.items():
        assert ('--refresh' in options) == ('--cached' in options), f'{"/".join(path)} offers half of the currency pair'


def test_every_resource_that_reads_currency_offers_the_flag_on_both_read_verbs() -> None:
    """A resource whose observation branches on `session.refresh` has two answers,
    so its own doors have to let a caller pick between them.

    `system` and `plugins` each spent a release answering `False` while the
    composite verbs measured — two front doors disagreeing about one dataset, both
    found by a person rather than by this. The set is read off the source for the
    reason the section gives: a literal list is the thing that cannot notice a
    seventh resource.

    `system` reads it one level down, through `evidence.Inventories`, so the grep
    is over the resource *and* what it dispatches to rather than over the module
    alone.
    """
    assert CURRENCY_RESOURCES, 'nothing was found to read currency, so this asserts nothing'
    for resource in sorted(CURRENCY_RESOURCES):
        for verb in ('plan', 'check'):
            options = ACCEPTED.get((resource, verb))
            assert options is not None, f'{resource} {verb} is not in the tree'
            assert '--refresh' in options, f'{resource} {verb} reads currency and cannot be told whether to measure'


WITHHELD_FROM_CHECK = ('--source', '--owner', '--package')
"""The narrowings `check` deliberately does not take.

`check` asks whether anything is *wrong*, and none of these narrows that: a
logged-out CLI and an unset machine-local value belong to no owner, no section and
no entry. `--offline` is the one narrowing-shaped flag it does take, because that
changes what the examination compares against rather than what it examines, and
`test_check_takes_offline_wherever_apply_does` asserts the other direction for it.
"""


@pytest.mark.parametrize('flag', WITHHELD_FROM_CHECK)
def test_no_check_offers_a_narrowing(flag: str) -> None:
    """The other half of the selector decision, which nothing else pins.

    These are in `SELECTORS`, and the selector test above asserts plan ⊇ apply and
    says nothing about `check` — deliberately. Without this, a narrowing added to
    one `check` would pass every test in the file.
    """
    for path, options in ACCEPTED.items():
        if path[-1] == 'check':
            assert flag not in options, f'{"/".join(path)} is a check offering {flag}'


# ─────────────────────────────────────────────────────────────────────────────
# No leaf decides an exit status for itself
# ─────────────────────────────────────────────────────────────────────────────


SOURCE = sorted((Path(dotfiles.__file__).parent).rglob('*.py'))


def exit_arguments() -> list[tuple[str, int, ast.expr | None]]:
    """Every `typer.Exit(...)` in the package, with what it was handed."""
    found = []
    for path in SOURCE:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'Exit':
                found.append((path.name, node.lineno, node.args[0] if node.args else None))
    return found


def returns_an_exit_code(name: str) -> bool:
    """Whether a function in this package is annotated `-> ExitCode`.

    Asked of the source rather than kept as a list, so a helper that stops
    returning one is caught here instead of quietly widening what a leaf may hand
    to `typer.Exit`. mypy already holds each of them to its annotation, so the two
    together are the whole claim.
    """
    for path in SOURCE:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return node.returns is not None and ast.unparse(node.returns) == 'ExitCode'
    return False


def names_an_exit_code(argument: ast.expr | None) -> bool:
    if isinstance(argument, ast.Attribute):
        return ast.unparse(argument).startswith('ExitCode.')
    if isinstance(argument, ast.IfExp):
        return names_an_exit_code(argument.body) and names_an_exit_code(argument.orelse)
    if isinstance(argument, ast.Call):
        callee = argument.func
        return returns_an_exit_code(callee.attr if isinstance(callee, ast.Attribute) else getattr(callee, 'id', ''))
    return False


def test_no_leaf_hands_typer_exit_an_integer_from_somewhere_else() -> None:
    """The invariant the boundary created, which the boundary's own tests do not
    assert.

    A hand-written handler per leaf makes a wrong exit code visible beside its
    right siblings. One shared handler puts nothing in place of that redundancy —
    so a leaf written afterwards can hand `typer.Exit` argparse's status or git's
    return
    code, land on 1, and mean DRIFT while the suite stays green. That is exactly
    what `bundle create`, `manage update` and six `bridge.declaration` callers did.

    An integer is not forbidden because it is an integer. It is forbidden because
    nothing about it says which of the four codes it is, and `ExitCode` is an
    `IntEnum` — so the wrong answer type-checks, runs, and exits.
    """
    for where, line, argument in exit_arguments():
        assert names_an_exit_code(argument), f'{where}:{line} hands typer.Exit `{ast.unparse(argument) if argument else "nothing"}`'


def test_the_exit_scan_finds_the_calls_it_is_asserting_about() -> None:
    """Guards the test above: a walk that finds nothing passes vacuously."""
    assert len(exit_arguments()) > 30


# ─────────────────────────────────────────────────────────────────────────────
# The set of sites doing a thing is exactly the set that should
# ─────────────────────────────────────────────────────────────────────────────
#
# Each centralization below has two independent claims: that the one owner works,
# and that nothing goes round it. The rendering tests further down assert the
# first. These assert the second, and it cannot be reached by rendering — a site
# nothing exercises renders nothing.
#
# Keyed on the function or the constant, never on the file. A symbol that moves to
# another module keeps its readers, so these answers do not change; a second reader
# is a second owner wherever it lands.


def functions_naming(*names: str) -> set[str]:
    """Which functions in the package reference all of these names.

    Module scope is left out. The assignment that defines a name and the import
    that carries it into a module are not readers of it, and counting them would
    make the answer a list of files again.
    """
    wanted, found = set(names), set()
    for path in SOURCE:
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            reached = {inner.id for inner in ast.walk(node) if isinstance(inner, ast.Name)}
            reached |= {inner.attr for inner in ast.walk(node) if isinstance(inner, ast.Attribute)}
            if wanted <= reached:
                found.add(node.name)
    return found


def phrase_sites(phrase: str) -> tuple[set[str], list[str]]:
    """Which constants are assigned this phrase, and everywhere else it is written.

    The second list is the invariant: a rendered literal, or a docstring pasting
    one, is a copy nothing keeps in step. A comment explains the thing rather than
    the change that produced it, which refuses the docstring case for the
    same reason, and no linter or type checker reads either.
    """
    owners, copies = set(), []
    for path in SOURCE:
        tree = ast.parse(path.read_text())
        assigned = {
            id(node.value): node.targets[0].id
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.targets[0], ast.Name)
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and phrase in node.value:
                if id(node) in assigned:
                    owners.add(assigned[id(node)])
                else:
                    copies.append(f'{path.name}:{node.lineno}')
    return owners, copies


def test_only_the_two_heading_builders_name_the_heading_widths() -> None:
    """A function naming either width is laying out a heading or a closing line of
    its own, whatever it draws it with.

    `machines show` and `network check` are the two that most wanted to. Both
    render a section and neither names a width, because `section_line` hands them
    the geometry already.
    """
    assert functions_naming('ADDRESS_COLUMN') == {'section_line', 'render_result'}
    assert functions_naming('VERDICT_WIDTH') == {'render_verdict'}


def test_one_function_asks_a_yes_or_no_question() -> None:
    """That `_confirmed` works and that nothing bypasses `_confirmed` are
    independent claims, and the tests for the first are satisfied by a fourth
    prompt written out longhand. Three copies is where this started: three
    different declines, one of them printing nothing at all."""
    assert functions_naming('confirm') == {'_confirmed'}


def test_one_function_composes_the_retention_rule() -> None:
    """`base_of` and `superseded` are each legitimate alone — the first names a pin
    and the second counts a limit. Composing them and dropping the base is the
    *rule*, and a fourth caller assembling it by hand is where three sites stopped
    agreeing before."""
    assert functions_naming('base_of', 'superseded') == {'retention'}


def test_the_attention_wording_is_written_once_and_read_everywhere_else() -> None:
    """A seventh site typing the literal is invisible to a suite that only ever
    compares against the constant.

    Every string constant is read, so a docstring pasting the phrase counts. That
    is the half no rendering reaches, and it is why this stands beside
    `test_every_line_wording_attention_reads_it_from_one_constant` rather than
    being replaced by it.
    """
    for phrase, owner in ((output.NEED_ATTENTION, 'NEED_ATTENTION'), (output.NEEDS_ATTENTION, 'NEEDS_ATTENTION')):
        owners, copies = phrase_sites(phrase)
        assert owners == {owner}, f'{phrase!r} is assigned to {sorted(owners)}'
        assert not copies, f'{phrase!r} is written out at {copies}'


# ─────────────────────────────────────────────────────────────────────────────
# Every report shares one geometry, one wording and one prompt
# ─────────────────────────────────────────────────────────────────────────────
#
# What each of these asserts is the rendered line: where a heading puts its
# columns, what a count is worded as, what a prompt does when nobody can answer
# it, and what a sweep keeps. Two reports disagreeing about a column is something
# a reader sees; which module holds the constant behind it is not.
#
# The pinning mechanism is a rebinding. A constant is swapped for a sentinel in
# every module of the package at once, the line is rendered, and a site that holds
# its own copy of the value is the one that did not move.


@functools.cache
def package_modules() -> tuple[ModuleType, ...]:
    """Every module in the package, imported.

    Walked rather than listed: a list of modules cannot tell "nobody put a second
    copy of a constant somewhere" from "somebody did and nothing looked".
    """
    found = pkgutil.walk_packages(dotfiles.__path__, prefix=f'{dotfiles.__name__}.')
    return (dotfiles, *(importlib.import_module(module.name) for module in found))


def rebind(monkeypatch: pytest.MonkeyPatch, name: str, value: object) -> list[str]:
    """Point every module holding this name at a different value, and say which.

    A module reaching a constant by `from dotfiles.output import X` holds its own
    reference, so patching the module that defines it moves nothing there. The
    sweep is what makes one rebinding reach every site rather than the first.
    """
    held = [module for module in package_modules() if name in vars(module)]
    for module in held:
        monkeypatch.setattr(module, name, value)
    return [module.__name__ for module in held]


def capture(monkeypatch: pytest.MonkeyPatch) -> io.StringIO:
    """Both consoles, writing into one buffer.

    Neither the width nor the color is pinned — a test asserts the value the
    output was built from rather than the rendering, which refuses both, and a
    pinned width only picks which terminal the suite pretends to be. Rich answers
    `is_terminal` false for a `StringIO` and emits no escape sequence into one, so
    the buffer is already the plain text these tests index into.

    Rebound across the package rather than on `output` alone, since modules
    throughout it hold their own reference to a console.
    """
    buffer = io.StringIO()
    stream = Console(file=buffer, highlight=False)
    rebind(monkeypatch, 'console', stream)
    rebind(monkeypatch, 'err_console', stream)
    return buffer


DETAIL = 'what-this-section-found'
"""A detail no renderer produces on its own, so its index in a rendered line is
the column that line started its detail in."""


def a_row(detail: str) -> ResourceResult:
    """One resource's row, which is the shape a read verb's heading is built from."""
    return ResourceResult(address='packages', verdict=ResourceVerdict.DRIFT, detail=detail)


def section_renderers() -> dict[str, Callable[[], None]]:
    """Every renderer that opens a section, by the report that reaches it.

    Four reports open one, and a section whose detail runs to a second line is here
    as a fifth: the continuation is laid out by its own format string and is what
    the first line has to agree with.
    """
    return {
        'a listing heading': lambda: output.console.print(output.section_line(output.VERDICT_MARKS['drift'], 'packages', DETAIL)),
        "an apply's measure pass": lambda: output.render_section('packages', DETAIL),
        'the summary block': lambda: output.render_summary_row('drift', 'packages', DETAIL, output.console),
        "a read verb's resource row": lambda: output.render_result(a_row(DETAIL), output.console),
        'a detail that runs on': lambda: output.render_result(a_row(f'first line\n{DETAIL}'), output.console),
    }


def section_columns(monkeypatch: pytest.MonkeyPatch, width: int | None = None) -> dict[str, int]:
    """Where each section renderer put its detail, at one name-column width."""
    if width is not None:
        rebind(monkeypatch, 'ADDRESS_COLUMN', width)
    buffer = capture(monkeypatch)
    found = {}
    for report, render in section_renderers().items():
        buffer.seek(0)
        buffer.truncate()
        render()
        carrying = [line for line in buffer.getvalue().splitlines() if DETAIL in line]
        assert len(carrying) == 1, f'{report} rendered {len(carrying)} lines carrying its detail'
        found[report] = carrying[0].index(DETAIL)
    return found


def test_every_report_opens_its_section_in_one_column(monkeypatch: pytest.MonkeyPatch) -> None:
    """The invariant the shared renderer created, asserted as the line a reader sees.

    Four reports open a section — a read verb's resource row, an `apply`'s measure
    pass, the line above each group of work, and the summary block — and while each
    laid out its own, a fifth one's disagreement stood beside four siblings getting
    it right. `output.section_line` is the one builder for all of them, which
    removes that redundancy and puts nothing in its place.

    What it bought is one column, so the column is what is asserted. Measured at
    two widths, because a row of hardcoded numbers agrees at one width too: a
    renderer holding its own does not move with the constant, and the second
    measurement is what sees it.
    """
    narrow = section_columns(monkeypatch, width=8)
    wide = section_columns(monkeypatch, width=30)

    assert len(set(narrow.values())) == 1, f'section headings disagree about their column: {narrow}'
    assert len(set(wide.values())) == 1, f'section headings disagree about their column: {wide}'
    assert wide['the summary block'] - narrow['the summary block'] == 22, f'a heading did not follow the width: {narrow} then {wide}'


def test_a_name_wider_than_the_column_is_pushed_right_and_never_cut() -> None:
    """`ADDRESS_COLUMN` is a floor rather than a ceiling, and the difference is what
    a report does with a heading nobody sized the column for. An `apply` opens two
    sections named `needs attention` and `not measurable`, both wider than the
    widest resource name, and a format that truncated would drop the word telling a
    reader which set is in front of them.

    Asserted with a name from outside `vocabulary.RESOURCES`, deliberately.
    `ADDRESS_COLUMN` is the maximum over that tuple, so a heading measured against
    it agrees by construction and can only fail if the derivation is replaced by a
    literal.

    Measured on the markup rather than on a rendered line: the tags around the name
    are the same length whatever it is, so what moves is the padding.
    """
    wide = 'a-heading-nobody-sized-the-column-for'
    assert len(wide) > output.ADDRESS_COLUMN, 'the name is not wide enough to test anything'

    line = output.section_line('~', wide, DETAIL)

    assert wide in line, f'the name was cut rather than pushing its detail right: {line!r}'
    assert line.index(DETAIL) > line.index(wide) + len(wide), f'the detail runs into the name: {line!r}'


def test_every_resource_heading_shares_one_column() -> None:
    """The width has to fit every name it pads, or the report a machine really
    prints misaligns wherever the longest one lands.

    **It cannot fail while `ADDRESS_COLUMN` is the maximum over
    `vocabulary.RESOURCES`**, since that is the tuple it is measured over. A
    resource added later widens the constant with it. What it catches is the
    derivation replaced by a literal, and it is the only thing that does: a heading
    is compared against a hand-written column nowhere else in the suite, so
    `ADDRESS_COLUMN = 4` otherwise passes every test there is.
    """
    columns = {resource: output.section_line('~', resource, DETAIL).index(DETAIL) for resource in vocabulary.RESOURCES}

    assert len(set(columns.values())) == 1, f'a resource name is wider than the column every heading shares: {columns}'


def verdict_columns(monkeypatch: pytest.MonkeyPatch, width: int | None = None) -> dict[str, int]:
    """Where each verdict word's closing sentence started, at one word width."""
    if width is not None:
        rebind(monkeypatch, 'VERDICT_WIDTH', width)
    buffer = capture(monkeypatch)
    found = {}
    for word in output.VERDICT_COLORS:
        buffer.seek(0)
        buffer.truncate()
        output.render_verdict(word, DETAIL, output.console)
        found[word] = buffer.getvalue().index(DETAIL)
    return found


def test_every_run_starts_its_closing_sentence_in_one_column(monkeypatch: pytest.MonkeyPatch) -> None:
    """The other half of the same geometry, for the line a run answers with.

    `output.render_verdict` is the one place the verdict word is spelled out, and
    what that buys is a sentence starting in one place whatever the run answered.
    A report reaching the width by importing it, or by copying the number, is a
    second owner of that column.

    Measured under a rebinding rather than at the shipped width, which is a
    separate claim and is asserted separately below.
    """
    narrow = verdict_columns(monkeypatch, width=12)
    wide = verdict_columns(monkeypatch, width=30)

    assert len(set(narrow.values())) == 1, f'closing lines disagree about their column: {narrow}'
    assert len(set(wide.values())) == 1, f'closing lines disagree about their column: {wide}'
    assert wide['drift'] - narrow['drift'] == 18, f'a closing line did not follow the width: {narrow} then {wide}'


def test_every_verdict_word_shares_one_column(monkeypatch: pytest.MonkeyPatch) -> None:
    """The shipped half of the same geometry: a width narrower than the longest
    verdict pads that one word to nothing and moves its sentence right.

    **It cannot fail while `VERDICT_WIDTH` is the maximum over
    `VERDICT_COLORS`**, and `render_verdict` raises `KeyError` on any word outside
    that dict, so no other word can reach the padding. What it catches is the
    derivation replaced by a literal, and it is the only thing that does:
    `VERDICT_WIDTH = 5` otherwise passes every test in the suite.
    """
    shipped = verdict_columns(monkeypatch)

    assert len(set(shipped.values())) == 1, f'the closing sentence moves with the verdict: {shipped}'


ATTENTION = 'ATTENTION-READ-FROM-THE-CONSTANT'
ATTENTIONS = 'ATTENTIONS-READ-FROM-THE-CONSTANT'
"""Sentinels carrying no lowercase `attention`, so a site that typed the wording
rather than reading it is the one still spelling it after the swap."""


def a_declined_change() -> Change:
    """One item that differs, can be measured, and `apply` will not touch, which is
    the thing an attention count counts."""
    return Change(
        resource='auth',
        stage=Stage.ENVIRONMENT,
        item='auth/meso',
        verdict=Verdict.MISSING,
        repair=Repair.BY_HAND,
        detail='logged out',
        advice='log in with `meso auth login`',
    )


def attention_wordings(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Every line in the package that words what `apply` declined to act on.

    Reached through the function that builds each one rather than through a
    command, so nothing here walks a machine. Two modules render them: the tally
    on a row, a folded `check` row's own sentence, both read verbs' closing lines,
    an `apply`'s closing line, and the section heading over what it walked past.
    """
    buffer = capture(monkeypatch)
    declined = a_declined_change()
    checked = reconcile.from_changes('auth', [declined], 'all logged in', lens=Lens.CHECK)
    planned = reconcile.from_changes('auth', [declined], 'all logged in', lens=Lens.PLAN)
    counted = ResourceResult(address='auth', verdict=ResourceVerdict.DRIFT, detail='', lens=Lens.PLAN, attention=1)

    reconcile._report_untouched([declined], [])

    return {
        'the tally on a row': output.tallies(counted),
        "a check row's own sentence": checked.detail,
        "plan's closing line": reconcile.verdict_line([planned], Lens.PLAN),
        "check's closing line": reconcile.verdict_line([checked], Lens.CHECK),
        "apply's closing line": reconcile.applied_line(1, [], [declined], []),
        'the heading over what apply walked past': buffer.getvalue(),
    }


def test_every_line_wording_attention_reads_it_from_one_constant(monkeypatch: pytest.MonkeyPatch) -> None:
    """The invariant centralizing the wording created, asserted as what is printed.

    Six render sites across two modules became one owner, and the copies were
    themselves the guard: while six existed, rewording meant finding all six. A
    seventh site typing the literal is invisible to a suite that only ever compares
    against the constant.

    Swapped rather than searched for, so what is asserted is that each line *reads*
    the constant. A site that typed the wording renders the shipped phrase after
    the swap while every sibling renders the sentinel.
    """
    shipped = attention_wordings(monkeypatch)
    for where, text in shipped.items():
        assert output.NEED_ATTENTION in text or output.NEEDS_ATTENTION in text, f'{where} words no attention count, so it asserts nothing'

    swept = rebind(monkeypatch, 'NEED_ATTENTION', ATTENTION)
    swept += rebind(monkeypatch, 'NEEDS_ATTENTION', ATTENTIONS)

    rendered = attention_wordings(monkeypatch)
    typed = {where: text for where, text in rendered.items() if 'attention' in text}
    assert not typed, f'wording typed rather than read, with {sorted(set(swept))} swapped: {typed}'
    for where, text in rendered.items():
        assert ATTENTION in text or ATTENTIONS in text, f'{where} lost its attention count under the swap: {text!r}'


def test_the_two_attention_spellings_agree() -> None:
    """They differ by one character and are interchangeable at every call site, so
    a site picking the wrong one renders `1 item(s) needs attention` with nothing
    to say so."""
    assert output.NEED_ATTENTION.replace('need', 'needs', 1) == output.NEEDS_ATTENTION


# ─────────────────────────────────────────────────────────────────────────────
# One way to ask a yes-or-no question, and one way to decline it
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(('interactive', 'no_input'), [(True, True), (False, False)], ids=['--no-input', 'no terminal'])
def test_a_question_nobody_can_answer_names_the_flag_and_the_effect(interactive: bool, no_input: bool) -> None:
    """A refactor that centralizes scattered handling pins the invariant it
    created, or it is one refactor and no guarantee.

    Three prompts written out longhand drift into three different declines, and the
    one that drifts furthest prints nothing at all — a non-zero status with no
    reason on screen for somebody who answered `n`. What `_confirmed` guarantees is
    the decline, so the decline is what is asserted.

    `BadParameter` and not `Abort`, which is the reason click's own `prompt=` is
    not used here: `Abort` exits 1, and 1 is DRIFT, so a pipeline that forgot a
    flag would report a machine that differs from its declaration.
    """
    with pytest.raises(click.BadParameter) as refused:
        staging._confirmed('Remove 3 bundle(s)?', 'removed 3 locally', yes=False, no_input=no_input, interactive=interactive)

    assert refused.value.exit_code == vocabulary.ExitCode.USAGE
    assert '--yes' in str(refused.value)
    assert 'removed 3 locally' in str(refused.value)


def test_a_question_that_can_be_asked_defaults_to_no_and_asks_on_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """The other two answers the one helper gives.

    Default no, because two of the three prompts it serves are destructive. On
    stderr, because stdout carries the document a `--json` caller parses and a
    question in the middle of one is a syntax error rather than a question.

    `--yes` short-circuits ahead of both, so a run that passed it never reaches a
    terminal that is not there.
    """
    monkeypatch.setattr(sys, 'stdin', io.StringIO('\n'))
    assert staging._confirmed('Remove 3 bundle(s)?', 'removed 3 locally', yes=False, no_input=False, interactive=True) is False

    asked = capsys.readouterr()
    assert '[y/N]' in asked.err, f'the prompt does not default to no: {asked.err!r}'
    # The question, rather than the whole stream: click puts a lone space on stdout
    # ahead of the read, as its own workaround for readline eating a backspace.
    assert 'Remove 3 bundle(s)?' not in asked.out

    assert staging._confirmed('Remove 3 bundle(s)?', 'removed 3 locally', yes=True, no_input=False, interactive=False) is True


def test_every_leaf_that_takes_yes_also_takes_no_input() -> None:
    """The surface half of one helper, which nothing else pins.

    `_confirmed` takes both, so a leaf reaching it declares both. A prompt written
    longhand declares whatever its author thought of, and the flag it leaves out is
    `--no-input` — the one nobody types by hand and a scheduled run needs.

    Not the other direction: `bundle create` asks which machine a bundle is for,
    which is a choice rather than a yes or no, so `--yes` would answer nothing.
    """
    answerable = [path for path, options in ACCEPTED.items() if '--yes' in options]

    assert answerable, 'no leaf offers --yes, so this asserts nothing'
    for path in answerable:
        assert '--no-input' in ACCEPTED[path], f'{"/".join(path)} can be answered yes and cannot be told not to ask'


# ─────────────────────────────────────────────────────────────────────────────
# One rule decides what a sweep of staged bundles removes
# ─────────────────────────────────────────────────────────────────────────────


KEEP = 2
"""A limit smaller than the stack `a_stack` builds, so retention has something to
remove."""


def a_stack(machine: str) -> tuple[str, ...]:
    """One machine's bundles: a full one, then three sparse ones built after it.

    Named through `create_bundle.bundle_name` rather than typed, so the stamp and
    the `-sparse` suffix are the ones the tool really writes — which is what
    `base_of` reads to find the base and what retention sorts by.
    """
    day = functools.partial(dt.datetime, 2026, 1, tzinfo=dt.UTC)
    built = create_bundle.bundle_name(machine, 'linux', 'x86_64', day(1))
    since = tuple(create_bundle.bundle_name(machine, 'linux', 'x86_64', day(number), sparse=True) for number in (2, 3, 4))
    return (built, *since)


def test_no_sweep_removes_the_bundle_the_sparse_ones_fall_back_to(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The invariant composing the rule created, asserted as what a sweep removes.

    `base_of` names a pin and `remote.superseded` counts a limit. Each is legitimate
    alone, and composing them is the rule: the count sorts by stamp and a full
    bundle is always the oldest, so it takes the base first. "The newest is never
    removed" is true and takes the only bundle a sparse stack can fall through to.

    That the count really does take the base is asserted first. Without it the rest
    passes on a stack retention would never have touched, which is the shape of a
    test that cannot fail.

    Asserted at every door that answers what a sweep would remove — the rule, the
    cross-machine sweep the local cache asks, and the helper `bundle prune` names
    files with — because a fourth caller assembling it by hand is where three sites
    stopped agreeing before.

    **Two machines' stacks, and the local sweep is asked for both.** One machine's
    is the shape where `swept` and `_superseded_locally` cannot differ from
    `retention`, since both reduce to it — so the two extra doors would be asserted
    and neither exercised. The limit counts per machine, and a peer's downloads
    aging out the only bundle on a box that cannot re-fetch one is the loss the
    grouping exists to prevent.
    """
    mine, peer = 'archlinux', 'wsl-workstation'
    names = a_stack(mine) + a_stack(peer)
    bases = (a_stack(mine)[0], a_stack(peer)[0])

    for base in bases:
        assert base in remote.superseded(names, KEEP), 'the count no longer takes a base, so nothing below is asserting anything'

    rule = offline_bundle.retention(a_stack(mine), KEEP)
    assert rule.superseded and bases[0] not in rule.superseded
    assert rule.pinned == (bases[0],)

    across = offline_bundle.swept(offline_bundle.by_machine(names), KEEP)
    assert across.superseded and not set(bases) & set(across.superseded)
    assert set(across.pinned) == set(bases)
    assert len(across.superseded) == 2, f'the limit is not counted per machine: {across.superseded}'

    for name in names:
        (tmp_path / f'{name}.tar.gz').touch()
    monkeypatch.setattr(staging.paths, 'archive_dir', lambda: tmp_path)
    monkeypatch.setattr(staging.providers, 'staged_bundles', lambda: ())

    narrowed = staging._superseded_locally(KEEP, mine)
    assert narrowed.superseded and bases[0] not in narrowed.superseded
    assert narrowed.pinned == (bases[0],)
    assert not [name for name in narrowed.superseded if peer in name], f"a peer's bundles were swept by --machine {mine}"

    whole = staging._superseded_locally(KEEP, None)
    assert whole.superseded and not set(bases) & set(whole.superseded)
    assert set(whole.pinned) == set(bases)
    assert len(whole.superseded) == 2, f'the cache sweep is not counted per machine: {whole.superseded}'
