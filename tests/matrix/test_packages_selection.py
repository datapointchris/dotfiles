"""What `packages` accepts as a narrowing, and what it refuses.

Three selectors narrow a packages run, and each narrows a different thing.
`--source` names a `packages.yml` section and resolves to addresses. `--owner`
names a GitHub owner and narrows the *plan*, which the walk is then narrowed to.
`--reinstall` names entries to install again whatever measuring them concludes.
The matrix is what each does with a value that is valid, wrong, or valid
somewhere else.

Every row starts from a converged two-provider machine, so an exit code belongs
to the selector under test rather than to the declaration. `lazygit` is a release
binary on `PATH` and `ruff` is a uv tool with a receipt; the declaration also
carries a section `system` owns, a section nothing installs, and an entry this
machine does not subscribe to, because each is a refusal worth measuring and none
of them can be reached without being declared.

**A `--reinstall` outside the `--source` is accepted and then does nothing**, and
that is the fault this module pins twice: once as the behaviour a caller gets
today, and once as an `xfail(strict=True)` for the behaviour `reconcile.py`'s own
comment about "a reinstall that ran and did nothing" says the validation exists
to prevent.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from dotfiles.vocabulary import ExitCode
from matrix.harness import Invocation
from matrix.harness import Sandbox

DECLARATION = {
    'github_releases': [{'name': 'lazygit', 'repo': 'jesseduffield/lazygit', 'reports_version': False}],
    'go_tools': [{'name': 'task', 'package': 'github.com/go-task/task/v3/cmd/task'}],
    'uv_tools': {'lint': [{'name': 'ruff'}]},
    'system_packages': [{'name': 'ripgrep', 'apt': 'ripgrep', 'pacman': 'ripgrep'}],
    'zen_extensions': [{'name': 'Bitwarden', 'url': 'https://addons.mozilla.org/firefox/addon/bitwarden/'}],
}
"""Five sections, each here to be reachable by one `--source` row.

`go_tools` is declared and unsubscribed on purpose: it is the only way to write a
`--reinstall` name that the declaration knows and this machine does not.
"""

MANIFEST = {'machine': 'box', 'platform': 'linux', 'github_releases': ['lazygit'], 'uv_tools': ['ruff']}


@pytest.fixture(autouse=True)
def two_providers(sandbox: Sandbox) -> Sandbox:
    """A machine converged under both of the providers a `--source` row selects.

    Both installed, because a selector test that started from drift could not tell
    a narrowing that excluded an item from one that found nothing wrong with it.

    `reports_version: false` on the release is what keeps `apply` off the network.
    `apply` resolves with `refresh=not offline`, so an installed release with a
    currency question is asked upstream on every run — and the matrix is about
    narrowing rather than about currency, so the entry declares that it has no
    version to report and the question is never put.
    """
    sandbox.declare(packages=DECLARATION, manifest=MANIFEST)
    sandbox.installed('lazygit')
    sandbox.uv_installed('ruff')
    return sandbox


def test_the_machine_every_row_starts_from_is_converged(cli: Callable[..., Invocation]) -> None:
    """Asserted rather than assumed, so every exit code below is the selector's."""
    assert cli('packages', 'plan').exit_code == ExitCode.CONVERGED
    assert cli('packages', 'apply').exit_code == ExitCode.CONVERGED


# ─────────────────────────────────────────────────────────────────────────────
# --source
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('verb', ['plan', 'apply'], ids=['plan', 'apply'])
@pytest.mark.parametrize('source', ['github_releases', 'uv_tools'], ids=['a-release-section', 'a-uv-tool-section'])
def test_a_source_naming_a_section_this_resource_installs_runs(verb: str, source: str, cli: Callable[..., Invocation]) -> None:
    """Both providers `packages` gathers are reachable by name, under both verbs."""
    assert cli('packages', verb, '--source', source).exit_code == ExitCode.CONVERGED


@pytest.mark.parametrize('verb', ['plan', 'apply'], ids=['plan', 'apply'])
@pytest.mark.parametrize(
    ('source', 'says'),
    [
        ('no_such_section', 'unknown source'),
        ('system_packages', 'belongs to system'),
        ('zen_extensions', 'nothing installs zen_extensions'),
    ],
    ids=['not-a-section', 'a-section-system-owns', 'a-section-nothing-installs'],
)
def test_a_source_this_resource_cannot_install_is_a_usage_error(verb: str, source: str, says: str, cli: Callable[..., Invocation]) -> None:
    """Three ways to be wrong, and each says which one it was.

    A name that is not a section at all is caught by the option's own callback
    against `packages.yml`; a section another resource installs and a section
    nothing installs are both caught in `_selected`, against the registry. All
    three are usage errors rather than findings, because none of them ran.
    """
    ran = cli('packages', verb, '--source', source)

    assert ran.exit_code == ExitCode.USAGE
    assert says in ran.stderr


def test_an_unknown_source_names_the_sections_that_would_have_worked(cli: Callable[..., Invocation]) -> None:
    """The valid set comes from the declaration rather than a list in the code, so
    it is the synthetic machine's sections that are offered here."""
    ran = cli('packages', 'plan', '--source', 'no_such_section')

    assert 'github_releases' in ran.stderr


def test_a_source_narrowing_measures_only_the_provider_it_names(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The narrowing is real and not cosmetic: a release gone missing is drift for
    the whole resource and converged for a run narrowed to the uv tools."""
    (sandbox.bin / 'lazygit').unlink()

    assert cli('packages', 'plan', '--source', 'github_releases').exit_code == ExitCode.DRIFT
    assert cli('packages', 'plan', '--source', 'uv_tools').exit_code == ExitCode.CONVERGED


@pytest.mark.parametrize(
    ('verb', 'flag', 'value'),
    [
        ('check', '--source', 'github_releases'),
        ('check', '--owner', 'jesseduffield'),
        ('check', '--reinstall', 'ruff'),
        ('plan', '--reinstall', 'ruff'),
    ],
    ids=['check-source', 'check-owner', 'check-reinstall', 'plan-reinstall'],
)
def test_a_selector_a_verb_does_not_take_is_refused_by_the_parser(verb: str, flag: str, value: str, cli: Callable[..., Invocation]) -> None:
    """`check` asks what is wrong with the whole resource and takes no narrowing at
    all; `--reinstall` is a write and so belongs to `apply` alone."""
    ran = cli('packages', verb, flag, value)

    assert ran.exit_code == ExitCode.USAGE
    assert 'No such option' in ran.stderr


# ─────────────────────────────────────────────────────────────────────────────
# --owner
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('verb', ['plan', 'apply'], ids=['plan', 'apply'])
def test_an_owner_with_entries_on_this_machine_runs_against_those_entries(verb: str, cli: Callable[..., Invocation]) -> None:
    """`jesseduffield` owns the release and nothing else, so the walk is the
    release provider alone."""
    ran = cli('packages', verb, '--owner', 'jesseduffield')

    assert ran.exit_code == ExitCode.CONVERGED


@pytest.mark.parametrize('verb', ['plan', 'apply'], ids=['plan', 'apply'])
def test_an_owner_with_no_entries_is_a_usage_error_rather_than_a_converged_run(verb: str, cli: Callable[..., Invocation]) -> None:
    """An owner-narrowed plan with nothing in it leaves no provider, and a walk
    over no resources would otherwise report a converged machine to someone who
    asked about tools this machine does not have."""
    ran = cli('packages', verb, '--owner', 'nobody')

    assert ran.exit_code == ExitCode.USAGE
    assert 'nothing selected for owner nobody' in ran.stderr


def test_an_owner_is_traced_from_the_entrys_repo_and_a_pypi_tool_has_none(cli: Callable[..., Invocation]) -> None:
    """`--owner` filters on a repo the declaration names, so an entry sourced from
    a registry matches nobody.

    `ruff` is a `uv_tools` row with no repo. `astral-sh` publishes it and still
    selects nothing, which is the case that reads as a bug from outside.
    """
    assert cli('packages', 'plan', '--owner', 'astral-sh').exit_code == ExitCode.USAGE


def test_an_owner_narrowing_measures_only_that_owners_entries(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The counterpart to the `--source` narrowing above, through the other
    mechanism: `--owner` narrows the plan, and the walk follows it.

    The uv tool is what goes missing, because it is the entry the owner does *not*
    cover — so the unnarrowed run drifts and the narrowed one does not.
    """
    sandbox.uv_tools.joinpath('ruff', 'uv-receipt.toml').unlink()
    sandbox.uv_tools.joinpath('ruff').rmdir()

    assert cli('packages', 'plan').exit_code == ExitCode.DRIFT
    assert cli('packages', 'plan', '--owner', 'jesseduffield').exit_code == ExitCode.CONVERGED


# ─────────────────────────────────────────────────────────────────────────────
# --reinstall
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ('names', 'says'),
    [
        (['no_such_tool'], 'named no_such_tool'),
        (['uv_tools'], 'named uv_tools'),
        (['task'], 'named task'),
        (['ruff', 'no_such_tool'], 'named no_such_tool'),
        (['no_such_tool', 'also_not_a_tool'], 'named also_not_a_tool, no_such_tool'),
    ],
    ids=['an-undeclared-name', 'a-section-name', 'a-name-this-machine-does-not-subscribe-to', 'one-good-one-bad', 'two-bad-sorted'],
)
def test_a_reinstall_name_the_resolved_plan_does_not_carry_is_a_usage_error(
    names: list[str], says: str, cli: Callable[..., Invocation]
) -> None:
    """Validated against the resolved plan rather than the declaration, which is
    what makes three different mistakes one message.

    A section name is not an entry name, and neither is an entry this machine
    declines to subscribe to — both would otherwise be accepted and then match
    nothing, which reads as a reinstall that ran and did nothing. A run naming one
    good name and one bad one is refused whole, before anything is installed.
    """
    argv = [flag for name in names for flag in ('--reinstall', name)]

    ran = cli('packages', 'apply', *argv)

    assert ran.exit_code == ExitCode.USAGE
    assert says in ran.stderr
    assert 'packages list' in ran.stderr


@pytest.mark.parametrize(
    'names',
    [['ruff'], ['ruff', 'ruff']],
    ids=['once', 'repeated'],
)
def test_a_reinstall_name_the_plan_carries_reaches_the_install(names: list[str], cli: Callable[..., Invocation]) -> None:
    """The accepted case, measured at the only place it is observable.

    The machine is converged, so an install attempted at all is `--reinstall`'s
    doing — and `uv tool install --reinstall ruff` is the argv the guard stops,
    which names the entry and the flag that asked for it.
    """
    argv = [flag for name in names for flag in ('--reinstall', name)]

    with pytest.raises(BaseException, match=r'uv tool install --reinstall ruff would install'):
        cli('packages', 'apply', *argv)


def test_a_name_given_twice_is_one_name(cli: Callable[..., Invocation]) -> None:
    """`frozenset` is what the CLI hands down, so the refusal names it once.

    Asserted on the refusal rather than on the install, because a second install
    is the thing that cannot be observed: the first one raises.
    """
    ran = cli('packages', 'apply', '--reinstall', 'no_such_tool', '--reinstall', 'no_such_tool')

    assert ran.exit_code == ExitCode.USAGE
    assert ran.stderr.count('no_such_tool') == 1


def test_a_bare_reinstall_is_refused_by_the_parser_rather_than_meaning_everything(cli: Callable[..., Invocation]) -> None:
    """It takes a value, and a bare flag must not be read as "all of them" — that
    is a fresh install of every declared tool to repair one binary."""
    ran = cli('packages', 'apply', '--reinstall')

    assert ran.exit_code == ExitCode.USAGE
    assert 'requires an argument' in ran.stderr


# ─────────────────────────────────────────────────────────────────────────────
# The selectors together
# ─────────────────────────────────────────────────────────────────────────────


def test_a_source_and_an_owner_that_do_not_overlap_select_nothing(cli: Callable[..., Invocation]) -> None:
    """Both are valid alone. `--source uv_tools` keeps the uv provider and
    `--owner jesseduffield` keeps the release provider, and the intersection is
    empty — which is the owner's message rather than the source's, because the
    source resolved fine and the owner is what emptied it."""
    ran = cli('packages', 'apply', '--source', 'uv_tools', '--owner', 'jesseduffield')

    assert ran.exit_code == ExitCode.USAGE
    assert 'nothing selected for owner jesseduffield' in ran.stderr


def test_a_source_and_an_owner_that_do_overlap_run(cli: Callable[..., Invocation]) -> None:
    ran = cli('packages', 'apply', '--source', 'github_releases', '--owner', 'jesseduffield')

    assert ran.exit_code == ExitCode.CONVERGED


def test_an_owner_narrowing_is_what_a_reinstall_name_is_validated_against(cli: Callable[..., Invocation]) -> None:
    """`--owner` narrows the plan before the names are checked, so a declared and
    subscribed entry belonging to someone else is a usage error under it."""
    ran = cli('packages', 'apply', '--owner', 'jesseduffield', '--reinstall', 'ruff')

    assert ran.exit_code == ExitCode.USAGE
    assert 'named ruff' in ran.stderr


def test_a_reinstall_inside_the_selected_source_reaches_the_install(cli: Callable[..., Invocation]) -> None:
    """The pair to the fault below: the same name, under the source that carries
    it, does reach the install."""
    with pytest.raises(BaseException, match=r'uv tool install --reinstall ruff would install'):
        cli('packages', 'apply', '--source', 'uv_tools', '--reinstall', 'ruff')


# ─────────────────────────────────────────────────────────────────────────────
# A reinstall outside the selection: current behaviour, then the correct one
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    'argv',
    [
        ('packages', 'apply', '--json', '--source', 'github_releases', '--reinstall', 'ruff'),
        ('packages', 'apply', '--json', '--reinstall', 'uv'),
    ],
    ids=['outside-the-source', 'outside-the-resource'],
)
def test_a_reinstall_outside_the_selection_is_accepted_and_then_does_nothing(argv: tuple[str, ...], cli: Callable[..., Invocation]) -> None:
    """Current behaviour, and it is the fault `reconcile.py` names.

    `--reinstall` is validated against `session.plan`, which is the whole
    machine's plan — not against the addresses `--source` resolved to, and not
    against the resource the command belongs to. `ruff` is in the plan and outside
    `github_releases`; `uv` is in the plan as the toolchain and outside `packages`
    entirely. Both pass validation, and the walk that follows never sees the item,
    so the run reports a converged machine to a caller who asked for a reinstall
    that never happened.
    """
    ran = cli(*argv)

    assert ran.exit_code == ExitCode.CONVERGED
    assert {row['action'] for row in ran.document['outcomes']} == {'observed'}


@pytest.mark.xfail(strict=True, reason='validated against the whole plan, not the selection, so it exits 0 having reinstalled nothing')
@pytest.mark.parametrize(
    ('argv', 'named'),
    [
        (('packages', 'apply', '--source', 'github_releases', '--reinstall', 'ruff'), 'ruff'),
        (('packages', 'apply', '--reinstall', 'uv'), 'uv'),
    ],
    ids=['outside-the-source', 'outside-the-resource'],
)
def test_a_reinstall_outside_the_selection_should_be_a_usage_error(
    argv: tuple[str, ...], named: str, cli: Callable[..., Invocation]
) -> None:
    """What the validation was written to prevent, applied to the narrowed run.

    `apply_machine` already refuses a name the machine does not declare, and says
    why: accepting one "would otherwise be accepted and then match nothing, which
    reads as a reinstall that ran and did nothing". A name the machine declares
    and the *selection* excludes has exactly that shape, and is not caught —
    because the set it is checked against is `plan.items`, which the selection has
    not touched yet.
    """
    ran = cli(*argv)

    assert ran.exit_code == ExitCode.USAGE
    assert named in ran.stderr
