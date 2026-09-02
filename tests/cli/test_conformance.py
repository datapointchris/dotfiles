"""The grammar is a contract, so it is asserted rather than reviewed.

Every command in the tree is walked and its name checked against the closed
vocabulary in `dotfiles.vocabulary`. That makes adding a verb an edit to a
documented list with a written reason, instead of something that happens by
accident on one subcommand and nowhere else — which is how `link`/`relink`,
`--dry-run`, `--force` and `--mine` each came to mean something slightly
different depending on where they were typed.

These tests never invoke a command. They inspect the built app, so nothing here
touches the machine.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import click
import pytest
from typer.main import get_command

import dotfiles
from dotfiles import output
from dotfiles import registry
from dotfiles import resources
from dotfiles import vocabulary
from dotfiles.main import app


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
the surface is a policy that can disagree with its neighbour about what the
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

Derived rather than listed, per `testing.md` § "A surface invariant is derived
from the command tree": a table cannot tell "nobody added a networked resource"
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
    """An exception nobody uses is a licence left lying around.

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
    """`--force` authorises a write that cannot be undone — a foreign file replaced,
    a package removed — so it belongs on the verb that writes and nowhere else.
    `standards/cli-design.md` § "A flag appears only on the commands that read it".

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

    That `apply` really does reach upstream is behaviour and cannot be derived from
    the tree; `tests/matrix/test_composite.py` measures it.
    """
    for path, options in ACCEPTED.items():
        if path[-1] == 'apply':
            assert '--refresh' not in options, f'{"/".join(path)} offers --refresh, which it cannot decline to do'


def test_the_currency_flag_is_always_the_whole_pair() -> None:
    """One axis, two spellings, and a verb offering one of them is a verb a caller
    cannot reverse.

    Derived rather than listed, per `testing.md` § "A surface invariant is derived
    from the command tree": a table naming which verbs take the pair cannot tell
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


PACKAGE = Path(dotfiles.__file__).parent


def sibling_commands() -> set[Path]:
    """The tools this package ships that are not the `dotfiles` CLI.

    Each is a top-level module or subpackage named by a `[project.scripts]` entry,
    and each is its own CLI with its own grammar — argparse rather than typer, its
    own exit codes, its own prompt. The rules in this file are about the tree
    `dotfiles.main:app` builds, so a sibling satisfying them would be coincidence
    and a sibling breaking one is not a finding.

    Derived from the declaration rather than listed, so a tool added later is out
    of scope on the day it arrives. `dotfiles` and `packages` name no module at
    this level — they resolve into `main.py` and `declaration.py` — so nothing the
    CLI owns is excluded by asking this question.
    """
    scripts = tomllib.loads((PACKAGE.parent.parent / 'pyproject.toml').read_text())['project']['scripts']
    roots = (PACKAGE / name.replace('-', '_') for name in scripts)
    return {root for root in roots if root.is_dir()} | {root.with_suffix('.py') for root in roots if root.with_suffix('.py').is_file()}


SIBLINGS = sibling_commands()

SOURCE = sorted(path for path in PACKAGE.rglob('*.py') if path not in SIBLINGS and not any(parent in SIBLINGS for parent in path.parents))


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
# No report draws its own section heading
# ─────────────────────────────────────────────────────────────────────────────


HEADING_GEOMETRY = ('ADDRESS_COLUMN', 'VERDICT_WIDTH')
"""The two widths that lay out a report's own lines: a section heading's name
column, and the closing line's verdict word.

Distinct from `VERDICT_COLUMN` and `SUBJECT_COLUMN`, which are an evidence *row*'s
and are imported wherever a command renders rows — `commands/resources.py` sets its
own rows in them deliberately. These two belong to `output.section_line` and
`output.render_verdict`, which are the only two functions that lay out those lines.
"""


def heading_layouts() -> list[tuple[str, int]]:
    """Every f-string in the package that puts a padded name behind a bold tag.

    The shape a section heading is: rich's `[bold]`, then the name of the thing,
    padded so the detail after it starts in one column. Matched on the pair rather
    than on either half, because a bold field alone is a title and a padded field
    alone is a row, and neither is what this asserts about.
    """
    found = []
    for path in SOURCE:
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.JoinedStr):
                continue
            for left, right in zip(node.values, node.values[1:], strict=False):
                bold = isinstance(left, ast.Constant) and str(left.value).endswith('[bold]')
                padded = isinstance(right, ast.FormattedValue) and right.format_spec is not None and '<' in ast.unparse(right.format_spec)
                if bold and padded:
                    found.append((path.name, node.lineno))
    return found


def files_naming(constants: tuple[str, ...]) -> set[str]:
    """Which files in the package reference any of these names."""
    return {
        path.name
        for path in SOURCE
        for node in ast.walk(ast.parse(path.read_text()))
        if isinstance(node, ast.Name | ast.Attribute) and ast.unparse(node).split('.')[-1] in constants
    }


def test_one_function_lays_out_every_section_heading() -> None:
    """The invariant the shared renderer created, which its own tests do not assert.

    Four reports open a section — a read verb's resource row, an `apply`'s measure
    pass, the line above each group of work, and `machines show`'s groups — and
    while each laid out its own, a fifth one's disagreement stood beside four
    siblings getting it right. `output.section_line` is the one builder for all of
    them, which removes that redundancy and puts nothing in its place: a report
    written next can lay out a heading of its own, land in a column no other report
    uses, and leave the suite green.

    The bound is the shape rather than the intent: a heading built without `[bold]`,
    or with a width computed some other way, is not caught here. What is caught is
    the one a person writes by copying a line that already looks right, which is how
    all four of the originals came to exist.
    """
    assert {where for where, _ in heading_layouts()} == {'output.py'}


def test_the_heading_scan_finds_the_line_it_is_asserting_about() -> None:
    """Guards the test above: a walk that matches nothing passes vacuously."""
    assert heading_layouts()


def files_spelling(phrase: str) -> set[str]:
    """Which files in the package write this phrase as a string literal."""
    return {
        path.name
        for path in SOURCE
        for node in ast.walk(ast.parse(path.read_text()))
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and phrase in node.value
    }


def test_the_attention_wording_is_spelled_in_exactly_one_file() -> None:
    """The invariant centralising it created, which nothing else asserts.

    Six render sites across `output.py` and `reconcile.py` became one owner, and
    the copies were themselves the guard: while six existed, rewording meant
    finding all six. A seventh site typing the literal is invisible to a suite
    that only ever compares against the constant.

    Docstrings count, and that is the point. `documentation.md` § "A comment
    explains the thing, not the change that produced it" refuses a docstring that
    pastes a rendered string, for the same reason — nothing keeps the copy in step,
    and no linter or type checker reads it.
    """
    assert files_spelling('need attention') == {'output.py'}


def test_the_two_attention_spellings_agree() -> None:
    """They differ by one character and are interchangeable at every call site, so
    a site picking the wrong one renders `1 item(s) needs attention` with nothing
    to say so."""
    assert output.NEED_ATTENTION.replace('need', 'needs', 1) == output.NEEDS_ATTENTION


def test_the_heading_widths_are_named_only_where_the_heading_is_built() -> None:
    """The other half of the same invariant, for a report that reaches the columns by
    importing them rather than by copying a number.

    A module naming either constant is laying out a heading or a closing line of its
    own, whatever it draws it with. `machines show` and `network check` are the two
    that most wanted to — both render a section and neither imports a width, because
    `section_line` and `render_verdict` hand them the geometry already.
    """
    assert files_naming(HEADING_GEOMETRY) == {'output.py'}


def calls_named(name: str) -> list[tuple[str, int]]:
    """Every call to `name` in the package, qualified or bare, with where it is.

    Both forms, because a function is reached one way from outside its module and
    the other from inside it — and the inside caller is the one a
    "somewhere else does this too" invariant would otherwise miss entirely.
    """
    found = []
    for path in SOURCE:
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.Call):
                continue
            called = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, 'id', '')
            if called == name:
                found.append((path.name, node.lineno))
    return found


def test_one_place_asks_a_yes_or_no_question() -> None:
    """A centralization pins the invariant it created, or it is one refactor and no
    guarantee — standards/testing.md § "A refactor that centralizes scattered
    handling pins the invariant it created".

    That `_confirmed` works and that nothing bypasses `_confirmed` are independent
    claims, and the tests for the first are satisfied by a fourth prompt written
    out longhand. Three copies is where this started: three different declines,
    one of them printing nothing at all.
    """
    assert [where for where, _ in calls_named('confirm')] == ['staging.py']


def test_one_place_composes_the_retention_rule() -> None:
    """The same claim for the other centralization in this feature.

    `base_of` and `superseded` are each legitimate alone — the first names a pin
    and the second counts a limit. Composing them and dropping the base is the
    *rule*, and a fourth caller assembling it by hand is where three sites stopped
    agreeing before.
    """
    composing = {where for where, _ in calls_named('base_of')} & {where for where, _ in calls_named('superseded')}

    assert composing == {'offline_bundle.py'}
