"""What `packages` accepts as a narrowing, and what it refuses.

Three selectors narrow a packages run, and each narrows a different thing.
`--source` names a `packages.yml` section and resolves to addresses. `--owner`
names a GitHub owner and narrows the *plan*, which the walk is then narrowed to.
`--package` names entries and narrows the same plan one row further down. The
matrix is what each does with a value that is valid, wrong, or valid somewhere
else.

`--reinstall` is in here too and is not a selector: it is a boolean over whatever
the three above left, which is why the rows for it are about composition rather
than about values.

Every row starts from a converged two-provider machine, so an exit code belongs
to the selector under test rather than to the declaration. `lazygit` is a release
binary on `PATH` and `ruff` is a uv tool with a receipt; the declaration also
carries a section `system` owns, a section nothing installs, and an entry this
machine does not subscribe to, because each is a refusal worth measuring and none
of them can be reached without being declared.

**A name outside the narrowing is a usage error, not a converged run.** That is
what the last section pins: `reconcile.confirm_reachable` measures a name against
the `Selection` the walk will use rather than against the whole machine's plan, so
`--source X` and the resource noun both bound what a name may be.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from dotfiles.vocabulary import ExitCode
from matrix.harness import Invocation
from matrix.harness import ReachedTheNetwork
from matrix.harness import Sandbox
from matrix.harness import addresses

DECLARATION = {
    'github_releases': [{'name': 'lazygit', 'repo': 'jesseduffield/lazygit', 'reports_version': False}],
    'go_tools': [{'name': 'task', 'package': 'github.com/go-task/task/v3/cmd/task'}],
    'uv_tools': {'lint': [{'name': 'ruff'}]},
    'system_packages': [{'name': 'ripgrep', 'apt': 'ripgrep', 'pacman': 'ripgrep'}],
    'zen_extensions': [{'name': 'Bitwarden', 'url': 'https://addons.mozilla.org/firefox/addon/bitwarden/'}],
}
"""Five sections, each here to be reachable by one `--source` row.

`go_tools` is declared and unsubscribed on purpose: it is the only way to write a
`--package` name that the declaration knows and this machine does not.
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
    ('verb', 'argv'),
    [
        ('check', ('--source', 'github_releases')),
        ('check', ('--owner', 'jesseduffield')),
        ('check', ('--package', 'ruff')),
        ('check', ('--reinstall',)),
        ('plan', ('--reinstall',)),
    ],
    ids=['check-source', 'check-owner', 'check-package', 'check-reinstall', 'plan-reinstall'],
)
def test_a_selector_a_verb_does_not_take_is_refused_by_the_parser(verb: str, argv: tuple[str, ...], cli: Callable[..., Invocation]) -> None:
    """`check` asks what is wrong with the whole resource and takes no narrowing at
    all; `--reinstall` adds work and so belongs to `apply` alone."""
    ran = cli('packages', verb, *argv)

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
# --package
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
def test_a_package_name_the_resolved_plan_does_not_carry_is_a_usage_error(
    names: list[str], says: str, cli: Callable[..., Invocation]
) -> None:
    """Validated against the resolved plan rather than the declaration, which is
    what makes three different mistakes one message.

    A section name is not an entry name, and neither is an entry this machine
    declines to subscribe to — both would otherwise be accepted and then match
    nothing, which reads as a narrowed run that measured a converged machine. A
    run naming one good name and one bad one is refused whole, before anything is
    installed.
    """
    argv = [flag for name in names for flag in ('--package', name)]

    ran = cli('packages', 'apply', *argv)

    assert ran.exit_code == ExitCode.USAGE
    assert says in ran.stderr
    assert 'packages list' in ran.stderr


def test_a_package_narrowing_measures_only_the_entry_it_names(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The narrowing is real and not cosmetic, which is the same thing the
    `--source` and `--owner` rows above assert one level up: a release gone missing
    is drift for the whole resource and converged for a run narrowed to the uv
    tool beside it."""
    (sandbox.bin / 'lazygit').unlink()

    assert cli('packages', 'plan').exit_code == ExitCode.DRIFT
    assert cli('packages', 'plan', '--package', 'lazygit').exit_code == ExitCode.DRIFT
    assert cli('packages', 'plan', '--package', 'ruff').exit_code == ExitCode.CONVERGED


def test_a_package_reaches_the_runtime_its_section_declares(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The same widening `--source` makes, one row further down, through the same
    `needed_by` relation.

    `cli-design.md` § "A narrowing flag reaches the whole run, or what it cannot
    reach is left out of the run". The resolver already kept the runtime in the
    *plan*, and the resource-scoped door widened its `Selection` for `--source`
    alone — so `--package task` rehearsed a run that would have installed a Go
    tool with no Go, which is the `cargo: No such file or directory` failure the
    `--source` widening was written for.

    Asserted as an equality between the two flags rather than against a literal
    pair, because the claim is that one machine reads one way whichever narrowing
    named it.
    """
    sandbox.declare(packages=DECLARATION, manifest={**MANIFEST, 'go_tools': ['task']})

    named = addresses(cli('packages', 'plan', '--package', 'task', '--json'))

    assert named == addresses(cli('packages', 'plan', '--source', 'go_tools', '--json'))
    assert named == ['packages', 'toolchains']


def test_a_name_given_twice_is_one_name(cli: Callable[..., Invocation]) -> None:
    """`frozenset` is what the CLI hands down, so the refusal names it once.

    Asserted on the refusal rather than on the walk, because a name accepted twice
    and a name accepted once produce the same run.
    """
    ran = cli('packages', 'apply', '--package', 'no_such_tool', '--package', 'no_such_tool')

    assert ran.exit_code == ExitCode.USAGE
    assert ran.stderr.count('no_such_tool') == 1


# ─────────────────────────────────────────────────────────────────────────────
# --reinstall, which is force rather than scope
# ─────────────────────────────────────────────────────────────────────────────


def test_a_bare_reinstall_names_no_entry_and_still_reaches_one(cli: Callable[..., Invocation]) -> None:
    """It takes no value, and bare it means everything the run covers.

    The machine is converged, so an install attempted at all is `--reinstall`'s
    doing — and `uv tool install --reinstall ruff` is the argv the guard stops,
    which names an entry no flag in this command named.
    """
    with pytest.raises(BaseException, match=r'uv tool install --reinstall ruff would install'):
        cli('packages', 'apply', '--reinstall', '--source', 'uv_tools')


def test_a_reinstall_narrowed_by_package_stops_at_that_entry(cli: Callable[..., Invocation]) -> None:
    """The composed form, and the contrast that shows the two flags are different
    questions: scope is `--package`'s and force is `--reinstall`'s.

    Unnarrowed the run reinstalls the release too, which is `TOOLS` and so runs
    first — and reinstalling a release asks upstream what it would fetch, which
    the sandbox refuses. Narrowed to the uv tool the release is not in the plan at
    all, so that request is never made and the run reaches ruff instead. The
    exception each raises is therefore the whole assertion: one run went wide and
    the other did not.
    """
    with pytest.raises(ReachedTheNetwork):
        cli('packages', 'apply', '--reinstall')

    with pytest.raises(BaseException, match=r'uv tool install --reinstall ruff would install'):
        cli('packages', 'apply', '--reinstall', '--package', 'ruff')


def test_a_package_narrowing_without_the_flag_installs_nothing(cli: Callable[..., Invocation]) -> None:
    """The other half of the same split. `--package` alone narrows and does not
    force, so a converged entry stays converged — where the name-taking
    `--reinstall` could not express this at all."""
    assert cli('packages', 'apply', '--package', 'ruff').exit_code == ExitCode.CONVERGED


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


def test_an_owner_narrowing_is_what_a_package_name_is_validated_against(cli: Callable[..., Invocation]) -> None:
    """`--owner` narrows the plan before the names are checked, so a declared and
    subscribed entry belonging to someone else is a usage error under it."""
    ran = cli('packages', 'apply', '--owner', 'jesseduffield', '--package', 'ruff')

    assert ran.exit_code == ExitCode.USAGE
    assert 'named ruff' in ran.stderr


def test_a_package_inside_the_selected_source_reaches_the_install(cli: Callable[..., Invocation]) -> None:
    """The pair to the refusals below: the same name, under the source that
    carries it, does reach the install."""
    with pytest.raises(BaseException, match=r'uv tool install --reinstall ruff would install'):
        cli('packages', 'apply', '--reinstall', '--source', 'uv_tools', '--package', 'ruff')


# ─────────────────────────────────────────────────────────────────────────────
# A package outside the selection
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ('argv', 'named', 'carries'),
    [
        (('packages', 'apply', '--source', 'github_releases', '--package', 'ruff'), 'ruff', 'packages/uv'),
        (('packages', 'apply', '--package', 'uv'), 'uv', 'toolchains/uv-toolchain'),
    ],
    ids=['outside-the-source', 'outside-the-resource'],
)
def test_a_package_outside_the_selection_is_a_usage_error(
    argv: tuple[str, ...], named: str, carries: str, cli: Callable[..., Invocation]
) -> None:
    """What the validation was written to prevent, applied to the narrowed run.

    `apply_machine` refuses a name the machine does not declare, and says why:
    accepting one "would otherwise be accepted and then match nothing, which reads
    as a reinstall that ran and did nothing". A name the machine declares and the
    *selection* excludes has exactly that shape. `ruff` is in the plan and outside
    `--source github_releases`; `uv` is in the plan as the toolchain and outside
    the `packages` resource entirely. Both used to pass, walk past the item and
    report a converged machine.

    The advice names the address that does carry it, which is the one thing the
    caller cannot work out from the refusal.
    """
    ran = cli(*argv)

    assert ran.exit_code == ExitCode.USAGE
    assert named in ran.stderr
    assert carries in ran.stderr
