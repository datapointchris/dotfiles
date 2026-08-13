"""The declaration side of the CLI: `machines`, `config` and `repo`.

Three nouns that read rather than reconcile. `machines` answers what a machine
declares and whether the declaration holds together, `config` answers what this
tool's own config resolves to and which rung said so, and `repo` answers where
the checkout is. None of them measures the machine, which is what makes them the
part of the surface a synthetic declaration can pin completely.

Every case here builds its own declaration through the sandbox, so nothing is a
fact about the box running the suite. The one real machine these commands are
also asserted against is `~/dotfiles`'s own, in `tests/cli/test_requirements.py`
— that answers whether the register describes *this fleet*, which a fixture
cannot, and it is a different question from whether the command is correct.

`os.execvp` is intercepted for the whole module. `machines edit` and `repo edit`
replace the interpreter with `$EDITOR`, which under an in-process runner is the
pytest process — so the exec is recorded instead of performed. `$EDITOR` itself
stays the real knob, and what is asserted is the argv the command built.
"""

from __future__ import annotations

import dataclasses as dc
from collections.abc import Callable
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml

from dotfiles.vocabulary import ExitCode
from matrix.harness import Invocation
from matrix.harness import Sandbox
from matrix.harness import git_checkout

# ─────────────────────────────────────────────────────────────────────────────
# Declarations the cases are built from
# ─────────────────────────────────────────────────────────────────────────────

TASK = 'github.com/go-task/task/v3/cmd/task'
MINE = 'github.com/datapointchris/mine'

TWO_OWNERS = {'go_tools': [{'name': 'task', 'package': TASK}, {'name': 'mine', 'package': MINE}]}
"""Two Go tools whose owners differ, which is the whole of what `--owner` filters on.

The owner is derived from `package` rather than declared — `catalog.owner_of` —
so these two rows are also what makes the derivation observable from the CLI.
"""

DECLARES_BOTH = {'machine': 'box', 'platform': 'linux', 'go_tools': ['task', 'mine']}

MAC = {'machine': 'mac', 'platform': 'macos'}
"""A machine this box is not, and could not be. `machines show mac` must answer
about the manifest rather than about the host, which is the property that lets one
machine validate the whole fleet's declaration."""

REGISTER = {
    'flags': [
        {'name': 'ENABLE_THING', 'description': 'a thing', 'default': True},
        {'name': 'ENABLE_OTHER', 'description': 'another', 'default': False},
    ],
    'required': [
        {'name': 'WINDOWS_USER', 'description': 'the Windows account name', 'consumers': ['shell/host/wsl/mount.sh']},
        {'name': 'AQUA_ONLY', 'description': 'a value only a Mac needs', 'display_stack': 'aqua'},
    ],
    'required_files': [
        {'path': '~/.local/shell/local.sh', 'description': 'machine-local shell code'},
        {
            'path': '$XDG_CONFIG_HOME/safekeep/config.toml',
            'description': 'where the snapshots are',
            'restore': 'copy it from another machine',
            'tags': ['backup'],
        },
    ],
}
"""One register carrying every shape the three renderings have to survive: a value,
a value narrowed to a coordinate this machine is not, a file, and a file whose
restore is not safekeep's."""


def write_manifest(sandbox: Sandbox, name: str, manifest: Mapping[str, Any]) -> Path:
    """A second manifest beside the one `declare` writes.

    Written directly rather than through `declare`, which replaces `packages.yml`
    and `flags.yml` on every call and would undo whatever the case declared first.
    """
    target = sandbox.repo / 'install' / 'manifests' / f'{name}.yml'
    target.write_text(yaml.safe_dump(dict(manifest), sort_keys=False))
    return target


@pytest.fixture(autouse=True)
def never_replace_this_process(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, list[str]]]:
    """Record what `edit` would exec instead of exec'ing it.

    `os.execvp` does not return: it replaces the running program, and the running
    program here is pytest. Autouse rather than opt-in, because the process it
    would take is the one collecting the rest of the module — a case that reaches
    it by accident ends the session rather than failing.

    Patched at `os`, which is stdlib, so nothing in `src/dotfiles/` is stubbed.
    """
    calls: list[tuple[str, list[str]]] = []
    monkeypatch.setattr('os.execvp', lambda file, args: calls.append((file, list(args))))
    return calls


# ─────────────────────────────────────────────────────────────────────────────
# machines list
# ─────────────────────────────────────────────────────────────────────────────


def test_the_machines_listed_are_the_manifests_on_disk(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Read from the directory rather than from a roster, so a manifest added by a
    commit needs no second edit to become listable."""
    write_manifest(sandbox, 'mac', MAC)

    assert cli('machines', 'list', '--json').document == ['box', 'mac']


def test_the_listing_is_sorted_rather_than_in_directory_order(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Directory order is the filesystem's, so an unsorted listing would differ
    between two machines holding the same commit."""
    for name in ('zeta', 'alpha'):
        write_manifest(sandbox, name, {'machine': name, 'platform': 'linux'})

    assert cli('machines', 'list', '--json').document == ['alpha', 'box', 'zeta']
    assert cli('machines', 'list').stdout.split() == ['alpha', 'box', 'zeta']


def test_a_repo_with_no_manifests_directory_lists_nothing_rather_than_failing(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """A missing directory is a repo that declares no machines, which is a listing
    of none rather than an error."""
    for manifest in (sandbox.repo / 'install' / 'manifests').glob('*.yml'):
        manifest.unlink()
    (sandbox.repo / 'install' / 'manifests').rmdir()

    ran = cli('machines', 'list', '--json')

    assert ran.exit_code == ExitCode.CONVERGED
    assert ran.document == []


# ─────────────────────────────────────────────────────────────────────────────
# machines show — the resolution
# ─────────────────────────────────────────────────────────────────────────────


def test_show_resolves_the_machine_named_in_the_environment(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """`$MACHINE` is what `~/.env` sets, so the common invocation names no machine."""
    ran = cli('machines', 'show', '--json')

    assert ran.exit_code == ExitCode.CONVERGED
    assert ran.document['machine'] == sandbox.machine


def test_show_answers_about_a_machine_this_box_is_not(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Resolution is machine-independent by construction: nothing in it probes the
    host. That is what lets one box validate the whole fleet's declaration, and it
    is asserted from a Linux sandbox describing a Mac."""
    write_manifest(sandbox, 'mac', MAC)

    ran = cli('machines', 'show', 'mac', '--json')

    assert ran.document['machine'] == 'mac'
    assert ran.document['coordinates']['os_family'] == 'darwin'
    assert ran.document['coordinates']['package_manager'] == 'brew'


def test_a_platform_bundle_and_direct_coordinates_reach_the_same_shape(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """A manifest naming `coordinates:` carries no platform label, and the label is
    the only field that differs. `custom coordinates` is what the human rendering
    says instead."""
    sandbox.declare(
        manifest={
            'machine': 'box',
            'coordinates': {
                'package_manager': 'pacman',
                'os_family': 'linux',
                'display_stack': 'wayland',
                'host': 'native',
                'network_trust': 'fleet',
                'capacity': 'workstation',
            },
        }
    )

    ran = cli('machines', 'show', '--json')
    printed = cli('machines', 'show')

    assert ran.document['platform'] == ''
    assert ran.document['coordinates']['display_stack'] == 'wayland'
    assert 'custom coordinates' in printed.stdout


def test_every_item_names_the_selector_that_pulled_it_in(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The property that makes this an audit rather than a listing: under coordinate
    directories, "what does this machine get" stops being answerable by reading one place."""
    sandbox.declare(packages=TWO_OWNERS, manifest=DECLARES_BOTH)

    selectors = {item['name']: item['selector'] for item in cli('machines', 'show', '--json').document['items']}

    assert selectors['task'] == 'manifest:go_tools'
    assert selectors['uv'] == 'every machine'


def test_a_precondition_is_annotated_on_the_row_rather_than_swallowed_as_markup(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """`[amd_gpu]` is a rich style tag unless it is escaped, and unescaped the
    annotation had never once been visible on an entry that declared one."""
    sandbox.declare(
        packages={'go_tools': [{'name': 'mine', 'package': MINE, 'requires_amd_gpu': True}]},
        manifest={'machine': 'box', 'platform': 'linux', 'go_tools': ['mine']},
    )

    ran = cli('machines', 'show', '--json')
    printed = cli('machines', 'show')

    assert [item['precondition'] for item in ran.document['items'] if item['name'] == 'mine'] == ['amd_gpu']
    assert '[amd_gpu]' in printed.stdout


@pytest.mark.parametrize(
    ('owner', 'expected'),
    [
        (None, ['go', 'mine', 'task', 'uv']),
        ('datapointchris', ['mine']),
        ('go-task', ['task']),
        ('nobody', []),
    ],
    ids=['no-owner-is-everything', 'one-owner', 'the-other-owner', 'an-owner-with-nothing'],
)
def test_owner_narrows_the_plan_to_what_one_github_owner_publishes(
    owner: str | None, expected: list[str], sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """`--owner` narrows rather than feeds. A provider whose entries all belong to
    someone else resolves to zero items and disappears — which is why the two
    toolchains are in the unfiltered answer and in neither filtered one.
    """
    sandbox.declare(packages=TWO_OWNERS, manifest=DECLARES_BOTH)
    argv = ('machines', 'show', '--json') if owner is None else ('machines', 'show', '--owner', owner, '--json')

    ran = cli(*argv)

    assert ran.exit_code == ExitCode.CONVERGED
    assert sorted(item['name'] for item in ran.document['items']) == expected


@pytest.mark.parametrize('extra', [(), ('--json',)], ids=['alone', 'with-json'])
def test_raw_prints_the_manifest_byte_for_byte_and_resolves_nothing(
    extra: tuple[str, ...], sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """`--raw` is a different question from the resolution, so it answers first —
    including over `--json`, which would otherwise emit a document about a
    manifest the reader asked to see as written."""
    written = (sandbox.repo / 'install' / 'manifests' / 'box.yml').read_text()

    ran = cli('machines', 'show', '--raw', *extra)

    assert ran.exit_code == ExitCode.CONVERGED
    assert ran.stdout == written
    assert ran.document is None


def test_raw_prints_a_manifest_that_could_never_resolve(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The state `--raw` is most worth having: the resolution refuses, and reading
    the file is the next thing anyone does."""
    (sandbox.repo / 'install' / 'manifests' / 'box.yml').write_text('- one\n- two\n')

    assert cli('machines', 'show', '--raw').stdout == '- one\n- two\n'
    assert cli('machines', 'show', catch_exceptions=True).exit_code == ExitCode.ISSUE


# ─────────────────────────────────────────────────────────────────────────────
# machines requirements — the register
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('rendering', [(), ('--json',), ('--safekeep',)], ids=['human', 'json', 'safekeep'])
def test_every_rendering_of_the_register_names_every_entry_in_it(
    rendering: tuple[str, ...], sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """Three formats of one answer, and the answer is what a rebuild needs. A
    rendering that dropped an entry would leave a machine broken in exactly the way
    the register exists to prevent — `--safekeep` names the values in a trailing
    comment rather than dropping them for having no path.
    """
    sandbox.declare(flags=REGISTER)

    ran = cli('machines', 'requirements', *rendering)

    assert ran.exit_code == ExitCode.CONVERGED
    assert 'WINDOWS_USER' in ran.stdout
    assert '~/.local/shell/local.sh' in ran.stdout
    assert '$XDG_CONFIG_HOME/safekeep/config.toml' in ran.stdout


def declared_in_register(ran: Invocation) -> list[str]:
    """Each entry by what identifies it — a value's name, a file's path."""
    return [entry['path'] or entry['name'] for entry in ran.document]


def test_a_register_entry_narrowed_to_another_coordinate_is_not_this_machine_s(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Every coordinate is a narrowing key, not just `platform:`. `AQUA_ONLY` is
    declared for the display stack this Linux box does not have."""
    sandbox.declare(flags=REGISTER)

    named = declared_in_register(cli('machines', 'requirements', '--json'))

    assert named == ['WINDOWS_USER', '~/.local/shell/local.sh', '$XDG_CONFIG_HOME/safekeep/config.toml']


def test_the_register_answers_for_a_machine_the_entry_does_narrow_to(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The other half of the same claim, and the one that proves the narrowing is
    read rather than the entry simply being dropped."""
    sandbox.declare(flags=REGISTER)
    write_manifest(sandbox, 'mac', MAC)

    named = declared_in_register(cli('machines', 'requirements', 'mac', '--json'))

    assert named[:2] == ['WINDOWS_USER', 'AQUA_ONLY']


def test_a_file_entry_carries_the_default_restore_and_a_value_entry_its_own(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """`restore` is only declared where safekeep is not the answer, so the default
    has to be supplied by the emitter rather than read off the entry."""
    sandbox.declare(flags=REGISTER)
    write_manifest(sandbox, 'mac', MAC)

    restores = {entry['path'] or entry['name']: entry['restore'] for entry in cli('machines', 'requirements', 'mac', '--json').document}

    assert restores['~/.local/shell/local.sh'] == 'restore it with safekeep'
    assert restores['$XDG_CONFIG_HOME/safekeep/config.toml'] == 'copy it from another machine'
    assert restores['WINDOWS_USER'] == 'set it below the OVERRIDES marker in ~/.env'


def test_the_safekeep_block_tags_every_file_dotfiles_and_keeps_the_path_unexpanded(
    sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """`safekeep restore --tag dotfiles` wanting exactly this register is the point
    of the tag. The path stays a literal because the block is generated for a named
    machine and pasted on it — expanding here bakes in the generating machine's
    answer.
    """
    sandbox.declare(flags=REGISTER)

    printed = cli('machines', 'requirements', '--safekeep').stdout

    assert 'path = "$XDG_CONFIG_HOME/safekeep/config.toml"' in printed
    assert 'tags = ["dotfiles", "backup"]' in printed
    assert 'tags = ["dotfiles"]' in printed


def test_a_machine_that_needs_nothing_by_hand_says_so(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """An empty section reads as a command that failed to find its file."""
    ran = cli('machines', 'requirements')

    assert 'nothing' in ran.stdout
    assert cli('machines', 'requirements', '--json').document == []


def test_json_and_safekeep_are_two_formats_of_one_answer_and_refuse_each_other(cli: Callable[..., Invocation]) -> None:
    ran = cli('machines', 'requirements', '--json', '--safekeep', catch_exceptions=True)

    assert ran.exit_code == ExitCode.USAGE
    assert 'pick one' in ran.stderr


# ─────────────────────────────────────────────────────────────────────────────
# machines check — the declaration validator
# ─────────────────────────────────────────────────────────────────────────────


@dc.dataclass(frozen=True)
class Declared:
    """One whole declaration, as the files a case writes."""

    packages: dict[str, Any] | None = None
    manifest: dict[str, Any] | None = None
    flags: dict[str, Any] | None = None
    files: Mapping[str, str] = dc.field(default_factory=dict)
    """Repo-relative extra files, for the two rules that are about `configs/`
    rather than about `install/`."""

    def write(self, sandbox: Sandbox) -> None:
        sandbox.declare(packages=self.packages, manifest=self.manifest or {'machine': 'box', 'platform': 'linux'}, flags=self.flags)
        for relative, text in self.files.items():
            target = sandbox.repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)


GITCONFIG = 'configs/trust/fleet/.config/git/fleet.gitconfig'
COMMON = 'configs/common/.config/git/common.gitconfig'
INCLUDES_FLEET = '[include]\n\tpath = ~/.config/git/fleet.gitconfig\n'

SOUND = [
    pytest.param(Declared(), id='a-machine-that-declares-nothing'),
    pytest.param(
        Declared(packages=TWO_OWNERS, manifest=DECLARES_BOTH),
        id='every-named-entry-exists',
    ),
    pytest.param(
        Declared(files={GITCONFIG: '[user]\n', COMMON: INCLUDES_FLEET}),
        id='a-variant-gitconfig-an-include-names',
    ),
    pytest.param(
        Declared(files={'configs/trust/fleet/.config/dotfiles/config.yml': 'repos_registry: ~/dev/repos.json\n'}),
        id='a-registry-named-under-configs-trust',
    ),
    pytest.param(
        Declared(
            files={
                'configs/trust/fleet/.config/dotfiles/config.yml': 'repos_registry: ~/dev/repos.json\n',
                'configs/trust/fleet/.config/other/config.toml': 'repos_registry = "~/dev/repos.json"\n',
            }
        ),
        id='two-copies-of-one-registry-path-that-agree',
    ),
]

WARNED = [
    pytest.param(
        Declared(packages=TWO_OWNERS),
        'go_tools',
        "'mine' is declared but no manifest names it",
        id='an-entry-no-manifest-subscribes-to',
    ),
    pytest.param(
        Declared(packages={'cargo_packages': [{'name': 'fnm', 'binary_pattern': 'fnm-linux.zip'}]}),
        'cargo_packages',
        'declares binary_pattern but no github_repo',
        id='a-binary-pattern-with-no-repo-to-expand-it-against',
    ),
    pytest.param(
        Declared(files={COMMON: '[include]\n\tpath = ~/.config/git/gone.gitconfig\n'}),
        'gitconfig',
        "includes 'gone.gitconfig', which no variant ships",
        id='an-include-naming-a-variant-that-was-removed',
    ),
]

BROKEN = [
    pytest.param(
        Declared(manifest={'machine': 'box'}),
        'manifest',
        'declares neither a platform nor coordinates',
        id='a-machine-that-says-nothing-about-what-it-is',
    ),
    pytest.param(
        Declared(manifest={'machine': 'box', 'platform': 'linux', 'coordinates': {'host': 'wsl'}}),
        'manifest',
        'a fact spelled twice is a fact that can disagree',
        id='a-platform-and-coordinates-together',
    ),
    pytest.param(
        Declared(manifest={'machine': 'box', 'platform': 'mainframe'}),
        'manifest',
        "declares platform 'mainframe'",
        id='a-platform-bundle-that-does-not-exist',
    ),
    pytest.param(
        Declared(
            manifest={
                'machine': 'box',
                'coordinates': {
                    'package_manager': 'apt',
                    'os_family': 'darwin',
                    'display_stack': 'aqua',
                    'host': 'native',
                    'network_trust': 'fleet',
                    'capacity': 'server',
                },
            }
        ),
        'manifest',
        'declares a machine that cannot exist',
        id='coordinates-no-machine-could-be-at',
    ),
    pytest.param(
        Declared(manifest={'machine': 'box', 'platform': 'linux', 'go': True}),
        'manifest',
        'declares go — install is derived from the corresponding name-list now',
        id='a-retired-runtime-gate',
    ),
    pytest.param(
        Declared(manifest={'machine': 'box', 'platform': 'linux', 'brew_casks': ['ghostty']}),
        'manifest',
        'declares brew_casks, which no reader consumes',
        id='a-manifest-key-nothing-reads',
    ),
    pytest.param(
        Declared(manifest={'machine': 'box', 'platform': 'linux', 'flags': {'ENABLE_GHOST': False}}, flags=REGISTER),
        'manifest',
        'overrides ENABLE_GHOST, which flags.yml does not declare',
        id='a-flag-override-with-no-flag-behind-it',
    ),
    pytest.param(
        Declared(packages=TWO_OWNERS, manifest={'machine': 'box', 'platform': 'linux', 'go_tools': ['task', 'ghost']}),
        'go_tools',
        "names 'ghost', which no go_tools entry declares",
        id='a-manifest-naming-a-tool-the-catalog-retired',
    ),
    pytest.param(
        Declared(manifest={'machine': 'box', 'platform': 'linux', 'auth': ['ghost']}),
        'auth',
        "names 'ghost', which has no probe in resources/auth.py",
        id='a-login-nothing-knows-how-to-ask-about',
    ),
    pytest.param(
        Declared(packages={'github_releases': [{'name': 'ghost', 'repo': 'nobody/ghost'}]}),
        'github_releases',
        "'ghost' has no installer function in providers/releases.py",
        id='a-release-nothing-knows-how-to-install',
    ),
    pytest.param(
        Declared(packages={'go_tools': [{'name': 'task'}]}),
        'go_tools',
        'task is missing required field(s) package',
        id='a-catalog-entry-missing-a-required-field',
    ),
    pytest.param(
        Declared(files={GITCONFIG: '[user]\n'}),
        'gitconfig',
        'common.gitconfig is missing, so no variant gitconfig is reachable',
        id='a-variant-with-nothing-to-include-it',
    ),
    pytest.param(
        Declared(files={GITCONFIG: '[user]\n', COMMON: '[core]\n'}),
        'gitconfig',
        'is deployed but no include names it',
        id='a-variant-no-include-names',
    ),
    pytest.param(
        Declared(files={'configs/trust/fleet/.config/git/trust.gitconfig': '[user]\n', COMMON: INCLUDES_FLEET}),
        'gitconfig',
        "the trust value here is 'fleet', so it must be fleet.gitconfig",
        id='a-variant-named-for-its-axis-instead-of-its-value',
    ),
    pytest.param(
        Declared(files={'configs/common/.config/dotfiles/config.yml': 'repos_registry: ~/dev/repos.json\n'}),
        'registry',
        'names repos_registry outside configs/trust/',
        id='a-registry-deployed-to-both-trust-domains',
    ),
    pytest.param(
        Declared(
            files={
                'configs/trust/fleet/.config/dotfiles/config.yml': 'repos_registry: ~/dev/repos.json\n',
                'configs/trust/fleet/.config/other/config.toml': 'repos_registry = "~/other/repos.json"\n',
            }
        ),
        'registry',
        'the fleet variant names more than one registry',
        id='two-copies-of-one-registry-path-that-disagree',
    ),
]


@pytest.mark.parametrize('case', SOUND)
def test_a_sound_declaration_reports_no_finding_at_all(case: Declared, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    case.write(sandbox)

    ran = cli('machines', 'check', '--json')

    assert ran.exit_code == ExitCode.CONVERGED
    assert ran.document == []


@pytest.mark.parametrize(('case', 'section', 'fragment'), BROKEN)
def test_a_broken_declaration_is_an_error_the_check_refuses_on(
    case: Declared, section: str, fragment: str, sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """Exit 3 rather than 1: an invalid declaration is the archetypal Issue, since
    there is nothing `apply` can do to repair it."""
    case.write(sandbox)

    ran = cli('machines', 'check', '--json', catch_exceptions=True)

    assert ran.exit_code == ExitCode.ISSUE
    found = [entry for entry in ran.document if entry['section'] == section and fragment in entry['message']]
    assert found, ran.document
    assert {entry['severity'] for entry in found} == {'error'}


@pytest.mark.parametrize(('case', 'section', 'fragment'), WARNED)
def test_a_declaration_worth_a_remark_still_converges(
    case: Declared, section: str, fragment: str, sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """Warnings alone exit 0. An entry nothing subscribes to is a fact about the
    rollout rather than a fault in the file, and a check that failed on it would be
    a check nobody could keep green."""
    case.write(sandbox)

    ran = cli('machines', 'check', '--json')

    assert ran.exit_code == ExitCode.CONVERGED
    found = [entry for entry in ran.document if entry['section'] == section and fragment in entry['message']]
    assert found, ran.document
    assert {entry['severity'] for entry in found} == {'warning'}


def test_a_catalog_that_will_not_load_short_circuits_every_later_finding(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Everything downstream is measured *against* the catalog, so findings derived
    from a file that could not be parsed would describe a declaration nobody has."""
    sandbox.declare(
        packages={'go_tools': [{'name': 'task'}]},
        manifest={'machine': 'box', 'platform': 'linux', 'auth': ['ghost']},
    )

    ran = cli('machines', 'check', '--json', catch_exceptions=True)

    assert ran.exit_code == ExitCode.ISSUE
    assert {entry['section'] for entry in ran.document} == {'go_tools'}


def test_the_check_is_whole_declaration_even_when_one_machine_is_named(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """`packages.yml` is shared, so a manifest cannot be validated without it — and
    a typo in another machine's manifest is invisible from the box where the commit
    happens. The argument is accepted and the hint says what it did not do."""
    write_manifest(sandbox, 'mac', {'machine': 'mac', 'platform': 'macos', 'auth': ['ghost']})

    ran = cli('machines', 'check', 'box', '--json', catch_exceptions=True)

    assert ran.exit_code == ExitCode.ISSUE
    assert [entry['message'] for entry in ran.document] == ["manifest 'mac' names 'ghost', which has no probe in resources/auth.py"]


def test_the_hint_that_the_named_machine_did_not_narrow_anything_is_a_diagnostic(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """On stderr, because a `--json` run has to leave stdout parseable."""
    ran = cli('machines', 'check', 'box', '--json')

    assert 'checking every manifest, not only box' in ran.stderr
    assert ran.document == []


def test_the_human_rendering_counts_what_it_found(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The closing line is the answer for a reader who is not branching on the exit
    code."""
    sandbox.declare(packages=TWO_OWNERS, manifest={'machine': 'box', 'platform': 'linux', 'go_tools': ['ghost']})

    ran = cli('machines', 'check', catch_exceptions=True)

    assert '1 errors, 2 warnings' in ran.stdout


# ─────────────────────────────────────────────────────────────────────────────
# machines edit
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ('argv', 'target'),
    [(('machines', 'edit'), 'install/manifests/box.yml'), (('repo', 'edit'), '')],
    ids=['a-manifest', 'the-repo'],
)
def test_edit_hands_the_path_to_the_editor_the_environment_names(
    argv: tuple[str, ...],
    target: str,
    sandbox: Sandbox,
    cli: Callable[..., Invocation],
    monkeypatch: pytest.MonkeyPatch,
    never_replace_this_process: list[tuple[str, list[str]]],
) -> None:
    monkeypatch.setenv('EDITOR', 'fake-editor')
    expected = str(sandbox.repo / target) if target else str(sandbox.repo)

    cli(*argv)

    assert never_replace_this_process == [('fake-editor', ['fake-editor', expected])]


def test_an_unset_editor_falls_back_to_nvim(
    sandbox: Sandbox,
    cli: Callable[..., Invocation],
    monkeypatch: pytest.MonkeyPatch,
    never_replace_this_process: list[tuple[str, list[str]]],
) -> None:
    monkeypatch.delenv('EDITOR', raising=False)

    cli('machines', 'edit')

    assert never_replace_this_process[0][0] == 'nvim'


# ─────────────────────────────────────────────────────────────────────────────
# Naming a machine: the argument, the environment, and neither
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('verb', ['show', 'requirements', 'edit'], ids=['show', 'requirements', 'edit'])
def test_a_leaf_with_no_machine_and_no_environment_says_which_machines_exist(
    verb: str, cli: Callable[..., Invocation], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exit 2 rather than 3: nothing is wrong with the machine, the invocation did
    not say which one it meant."""
    monkeypatch.delenv('MACHINE')

    ran = cli('machines', verb, catch_exceptions=True)

    assert ran.exit_code == ExitCode.USAGE
    assert 'no machine given and MACHINE is unset' in ran.stderr
    assert 'name one of: box' in ran.stderr


@pytest.mark.parametrize(
    'verb',
    [
        'show',
        'check',
        'edit',
        'requirements',
    ],
    ids=['show', 'check', 'edit', 'requirements'],
)
def test_a_leaf_given_a_machine_that_does_not_exist_names_the_ones_that_do(verb: str, cli: Callable[..., Invocation]) -> None:
    """A typo is a usage error naming the known machines, never a report that this
    machine's declaration cannot be read.

    All four call `_manifest_path` before loading. `requirements` was the one that
    did not, and it let the `MachineError` out as a traceback — which is the reason
    this is a matrix rather than one test about one leaf.
    """
    ran = cli('machines', verb, 'ghost', catch_exceptions=True)

    assert ran.exit_code == ExitCode.USAGE
    assert 'ghost' in ran.stderr
    assert 'box' in ran.stderr


@pytest.mark.parametrize('verb', ['requirements', 'show'], ids=['requirements', 'show'])
def test_an_unreadable_manifest_is_an_issue_whichever_door_asks(verb: str, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """A manifest that exists and will not load is a fault in the repo, so it is an
    Issue with its reasons printed rather than a usage error.

    Both halves of the question now answer together. Whether the *file* is there
    and whether it *reads* are different questions, and a guard answering only the
    first let an unreadable manifest through as exit 1 with both streams empty —
    `DRIFT`, on a machine with no drift, from a verb that measured nothing.
    """
    sandbox.declare(manifest={'machine': 'box'})

    ran = cli('machines', verb, catch_exceptions=True)

    assert ran.exit_code == ExitCode.ISSUE
    assert 'declares neither a platform nor coordinates' in ran.stderr


# ─────────────────────────────────────────────────────────────────────────────
# An unresolvable machine, and the stream its reasons land on
# ─────────────────────────────────────────────────────────────────────────────


def test_an_unresolvable_machine_is_an_issue_with_every_reason_printed(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """All of them, not the first. A manifest with three faults is fixed in one
    pass or in three."""
    sandbox.declare(manifest={'machine': 'box', 'platform': 'linux', 'go': True, 'rust': True})

    ran = cli('machines', 'show', catch_exceptions=True)

    assert ran.exit_code == ExitCode.ISSUE
    assert 'declares go' in ran.stderr
    assert 'declares rust' in ran.stderr


def test_the_reasons_a_machine_cannot_resolve_are_printed_on_one_stream(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """One diagnostic, one stream. It used to be split: a `cannot be resolved`
    header on stderr and the reasons under it on stdout, so neither half was the
    whole message and the machine channel carried prose.

    The header is gone with the hand-written handlers that printed it. Nothing is
    lost — every reason names its own subject, so the header repeated the machine
    name that is already on each line.
    """
    sandbox.declare(manifest={'machine': 'box'})

    ran = cli('machines', 'show', '--json', catch_exceptions=True)

    assert 'declares neither a platform nor coordinates' in ran.stderr
    assert 'declares neither a platform nor coordinates' not in ran.stdout


def test_a_json_run_that_cannot_answer_leaves_stdout_empty(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """stdout is the machine channel and carries the document or nothing.

    A caller that reads stdout and parses it gets a syntax error whose text is the
    real diagnostic — so the failure it reports is "invalid JSON" rather than
    "this manifest declares neither a platform nor coordinates". `machines check`
    is the same command family doing it correctly: its findings are the document,
    and its hint goes to stderr.
    """
    sandbox.declare(manifest={'machine': 'box'})

    ran = cli('machines', 'show', '--json', catch_exceptions=True)

    assert ran.exit_code == ExitCode.ISSUE
    assert ran.stdout == ''


# ─────────────────────────────────────────────────────────────────────────────
# config show
# ─────────────────────────────────────────────────────────────────────────────

REGISTRY_VARIABLE = 'DOTFILES_REPOS_REGISTRY'


def write_config(sandbox: Sandbox, body: str) -> Path:
    target = sandbox.config / 'dotfiles' / 'config.toml'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body)
    return target


def test_a_machine_that_names_nothing_is_told_every_place_it_could(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The reader is looking at a resolution that found nothing, so the actionable
    fact is the whole set of places it looked."""
    ran = cli('config', 'show', '--json')

    setting = ran.document['settings'][0]
    assert setting['source'] == ''
    assert str(sandbox.env_file) in setting['advice']
    assert str(sandbox.config / 'dotfiles' / 'config.toml') in setting['advice']


def test_the_variable_rung_is_reported_by_the_name_that_answered(
    sandbox: Sandbox, cli: Callable[..., Invocation], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The value alone does not explain itself. A registry named by an export made
    in October reads exactly like one named by the config file."""
    registry = sandbox.root / 'repos.json'
    registry.write_text('{}')
    monkeypatch.setenv(REGISTRY_VARIABLE, str(registry))

    setting = cli('config', 'show', '--json').document['settings'][0]

    assert setting['source'] == f'${REGISTRY_VARIABLE}'
    assert setting['value'] == str(registry)
    assert setting['exists'] is True


def test_the_file_rung_is_reported_by_the_path_of_the_file(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    registry = sandbox.root / 'repos.json'
    registry.write_text('{}')
    config = write_config(sandbox, f'repos_registry = "{registry}"\n')

    document = cli('config', 'show', '--json').document

    assert document['exists'] is True
    assert document['settings'][0]['source'] == str(config)


def test_the_variable_wins_over_the_file(sandbox: Sandbox, cli: Callable[..., Invocation], monkeypatch: pytest.MonkeyPatch) -> None:
    """One answers this invocation and the other answers this machine, so the
    invocation is the higher rung."""
    write_config(sandbox, 'repos_registry = "/from/the/file"\n')
    monkeypatch.setenv(REGISTRY_VARIABLE, '/from/the/variable')

    setting = cli('config', 'show', '--json').document['settings'][0]

    assert setting['value'] == '/from/the/variable'
    assert setting['source'] == f'${REGISTRY_VARIABLE}'


def test_a_declared_path_is_expanded_before_it_is_reported(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The question is what the tool will do, not what somebody typed. `~/dev` is
    an ordinary thing to write in the config file."""
    write_config(sandbox, 'repos_registry = "~/dev/repos.json"\n')

    setting = cli('config', 'show', '--json').document['settings'][0]

    assert setting['value'] == str(sandbox.home / 'dev' / 'repos.json')


def test_a_named_file_that_is_not_there_resolves_and_says_it_is_absent(
    sandbox: Sandbox, cli: Callable[..., Invocation], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Answered and present are different questions, and only the second is about
    the filesystem."""
    monkeypatch.setenv(REGISTRY_VARIABLE, str(sandbox.root / 'gone.json'))

    setting = cli('config', 'show', '--json').document['settings'][0]

    assert setting['source'] == f'${REGISTRY_VARIABLE}'
    assert setting['exists'] is False
    assert 'no file there' in cli('config', 'show').stdout


def test_an_empty_variable_reads_as_unset_rather_than_as_the_current_directory(
    sandbox: Sandbox, cli: Callable[..., Invocation], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`Path('')` is the current directory and always exists, so a variable exported
    as nothing would resolve a declared file to something present while the machine
    had answered nothing at all."""
    write_config(sandbox, 'repos_registry = "/from/the/file"\n')
    monkeypatch.setenv(REGISTRY_VARIABLE, '')

    setting = cli('config', 'show', '--json').document['settings'][0]

    assert setting['value'] == '/from/the/file'


def test_a_config_file_that_will_not_parse_is_reported_rather_than_read_as_empty(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """A file a human hand-edited into invalid TOML must not read as a machine that
    named nothing: the two get opposite advice."""
    write_config(sandbox, 'repos_registry = [[[\n')

    document = cli('config', 'show', '--json').document

    assert document['problem'] != ''
    assert document['settings'][0]['source'] == ''
    assert 'cannot be read' in cli('config', 'show').stdout


def test_an_absent_config_file_is_reported_as_absent_and_not_as_a_problem(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """A machine may answer in `~/.env` alone, so no file is an ordinary state."""
    document = cli('config', 'show', '--json').document

    assert document['exists'] is False
    assert document['problem'] == ''
    assert 'not present' in cli('config', 'show').stdout


# ─────────────────────────────────────────────────────────────────────────────
# repo
# ─────────────────────────────────────────────────────────────────────────────


def test_repo_path_prints_the_checkout_and_nothing_else(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """A bare line on stdout, because it is read by a pipeline —
    `ifiles upload "$(dotfiles repo path)"`."""
    ran = cli('repo', 'path')

    assert ran.exit_code == ExitCode.CONVERGED
    assert ran.stdout == f'{sandbox.repo}\n'
    assert ran.stderr == ''


def test_repo_show_reports_the_branch_and_the_last_commit(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    git_checkout(sandbox.repo, branch='trunk', subject='the only commit')

    ran = cli('repo', 'show')

    assert '## trunk' in ran.stdout
    assert 'the only commit' in ran.stdout


def test_repo_show_reports_a_dirty_tree_as_dirty(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """`status -sb` rather than a boolean, so what is uncommitted is named."""
    git_checkout(sandbox.repo)
    (sandbox.repo / 'untracked.txt').write_text('scratch\n')

    assert '?? untracked.txt' in cli('repo', 'show').stdout


def test_repo_show_refuses_rather_than_reporting_success_it_did_not_have(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Exit 0 is the answer "the repo is at this commit on this branch", and on a
    directory that is not a checkout there is no commit, no branch and no repo.

    It used to print git's transcript whether or not git succeeded and never read
    the return code, so the run answered 0 with `fatal: not a git repository` as
    its whole output. `manage.update` read the same call's status all along, so
    the two halves of one module disagreed about whether git refusing mattered.
    """
    ran = cli('repo', 'show', catch_exceptions=True)

    assert ran.exit_code == ExitCode.ISSUE
    assert 'could not read the working tree' in ran.stderr
    assert ran.stdout == ''


# ─────────────────────────────────────────────────────────────────────────────
# The machine contract: every --json shape
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ('argv', 'shape'),
    [
        (('machines', 'list', '--json'), list),
        (('machines', 'show', '--json'), dict),
        (('machines', 'requirements', '--json'), list),
        (('machines', 'check', '--json'), list),
        (('config', 'show', '--json'), dict),
    ],
    ids=['machines-list', 'machines-show', 'machines-requirements', 'machines-check', 'config-show'],
)
def test_a_json_leaf_puts_one_parseable_document_on_stdout_and_nothing_beside_it(
    argv: tuple[str, ...], shape: type, sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """One stray diagnostic on stdout turns the parse into a syntax error rather
    than the warning it was. The whole of stdout parses, so there was nothing
    beside the document."""
    sandbox.declare(packages=TWO_OWNERS, manifest=DECLARES_BOTH, flags=REGISTER)

    ran = cli(*argv)

    assert ran.exit_code == ExitCode.CONVERGED
    assert isinstance(ran.document, shape)


PLAN_KEYS = {'machine', 'platform', 'coordinates', 'features', 'flags', 'auth', 'items'}
ITEM_KEYS = {'section', 'provider', 'resource', 'stage', 'name', 'executable', 'evidence_path', 'precondition', 'selector'}
REGISTER_KEYS = {'name', 'kind', 'path', 'description', 'restore', 'tags', 'consumers', 'narrowing'}
FINDING_KEYS = {'section', 'severity', 'message'}
SETTINGS_KEYS = {'config_file', 'exists', 'problem', 'settings'}
SETTING_KEYS = {'name', 'value', 'source', 'exists', 'advice'}


def test_the_resolved_plan_document_carries_the_whole_machine_and_every_item(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Nothing about an install is decided outside this object, so what it holds is
    what a run will do."""
    sandbox.declare(packages=TWO_OWNERS, manifest={**DECLARES_BOTH, 'auth': ['gh'], 'nvim_plugins': True}, flags=REGISTER)

    document = cli('machines', 'show', '--json').document

    assert set(document) == PLAN_KEYS
    assert document['features'] == ['nvim_plugins']
    assert document['auth'] == ['gh']
    assert document['flags'] == {'ENABLE_THING': 'true', 'ENABLE_OTHER': 'false'}
    assert all(set(item) == ITEM_KEYS for item in document['items'])


def test_the_register_document_carries_every_field_a_rebuild_reads(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    sandbox.declare(flags=REGISTER)

    document = cli('machines', 'requirements', '--json').document

    assert [set(entry) for entry in document] == [REGISTER_KEYS] * len(document)
    assert [entry['kind'] for entry in document] == ['value', 'file', 'file']
    assert document[0]['consumers'] == ['shell/host/wsl/mount.sh']


def test_a_finding_document_carries_the_section_the_reader_has_to_open_next(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    sandbox.declare(manifest={'machine': 'box', 'platform': 'linux', 'go': True})

    document = cli('machines', 'check', '--json', catch_exceptions=True).document

    assert [set(finding) for finding in document] == [FINDING_KEYS]
    assert document[0]['severity'] == 'error'


def test_the_settings_document_carries_the_file_and_every_rung_s_answer(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    document = cli('config', 'show', '--json').document

    assert set(document) == SETTINGS_KEYS
    assert document['config_file'] == str(sandbox.config / 'dotfiles' / 'config.toml')
    assert [set(entry) for entry in document['settings']] == [SETTING_KEYS]
