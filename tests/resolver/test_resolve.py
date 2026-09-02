"""What each machine should have."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from dotfiles import catalog
from dotfiles import coordinates as axes
from dotfiles import machine as machines
from dotfiles import plan as planning
from dotfiles import registry
from dotfiles import resolve

REPO_ROOT = Path(__file__).resolve().parents[2]
MACHINES = machines.names(REPO_ROOT)


@pytest.fixture(scope='module')
def declaration() -> catalog.Catalog:
    return catalog.load(REPO_ROOT / 'install' / 'packages.yml')


def planned(declaration: catalog.Catalog, name: str, **kwargs: Any) -> planning.Plan:
    return resolve.resolve(declaration, machines.load(name, REPO_ROOT), **kwargs)


def synthetic(tmp_path: Path, declared: dict[str, Any], manifest: dict[str, Any], **narrowing: Any) -> planning.Plan:
    install = tmp_path / 'install'
    (install / 'manifests').mkdir(parents=True, exist_ok=True)
    (install / 'packages.yml').write_text(yaml.safe_dump(declared, sort_keys=False))
    (install / 'manifests' / 'box.yml').write_text(yaml.safe_dump(manifest, sort_keys=False))
    (install / 'flags.yml').write_text('{}')
    return resolve.resolve(catalog.load(install / 'packages.yml'), machines.load('box', tmp_path), **narrowing)


def test_wsl_plans_none_of_the_docker_packages_its_apt_repo_does_not_carry(declaration: catalog.Catalog) -> None:
    """The expectation is built from the declaration rather than from the field
    the resolver reads, so a resolver that had this wrong could not agree with it.

    The docker family lives in Docker's own apt repository, which nothing in the
    installer configures — so on WSL `apt install docker-ce` fails, and `check`
    reported five packages missing forever on a machine deliberately never going
    to have them. Docker Desktop on the Windows side is what serves that host.
    """
    machine = machines.load('wsl-work-workstation', REPO_ROOT)
    plan = resolve.resolve(declaration, machine)

    planned = {item.name for item in plan.for_section('system_packages')}
    excluded = {entry.name for entry in declaration.section('system_packages') if getattr(entry, 'excludes_host', '') == 'wsl'}

    assert excluded, 'nothing declares excludes_host, so this asserts nothing'
    assert not (planned & excluded)


# ─────────────────────────────────────────────────────────────────────────────
# Coverage: nothing falls outside the walk
# ─────────────────────────────────────────────────────────────────────────────


def test_every_section_is_either_provided_or_explained() -> None:
    """A section in neither installs nothing and says nothing about it, which is a
    declaration nobody can tell from a satisfied one.

    Both declarations at once. One registry holds `packages.yml` and `system.yml`
    together, so a new section in either file has to answer the same question. Two
    maps would answer it separately.
    """
    declared = set(catalog.SECTIONS) | set(catalog.SYSTEM_SECTIONS)
    unaccounted = declared - set(registry.BY_SECTION) - set(registry.UNPROVIDED)

    assert not unaccounted, f'sections with no provider and no stated reason: {sorted(unaccounted)}'


# ─────────────────────────────────────────────────────────────────────────────
# Coordinates decide what a machine *can* have
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ('section', 'platform', 'expected'),
    [
        ('macos_casks', 'macos', True),
        ('macos_casks', 'archlinux', False),
        ('mas_apps', 'macos', True),
        ('mas_apps', 'linux', False),
    ],
)
def test_a_platform_exclusive_section_resolves_only_where_it_can_install(
    declaration: catalog.Catalog, section: str, platform: str, expected: bool
) -> None:
    """A Mac is not declining flatpak and Arch is not declining casks — neither
    can have the other, which is different from not wanting it."""
    name = next(machine for machine in MACHINES if machines.load(machine, REPO_ROOT).platform_label == platform)

    assert bool(planned(declaration, name).for_section(section)) is expected


def test_a_tool_requiring_a_wsl_host_resolves_only_there(declaration: catalog.Catalog) -> None:
    """win32yank exists on the wsl manifest and nowhere else, and says in the file
    that it is declared so verification does not report a correct machine broken."""
    on_wsl = {item.name for item in planned(declaration, 'wsl-work-workstation').for_section('github_releases')}
    on_arch = {item.name for item in planned(declaration, 'archlinux-personal-workstation').for_section('github_releases')}

    assert 'win32yank' in on_wsl
    assert 'win32yank' not in on_arch


def test_the_windows_machine_plans_every_winget_row_and_nothing_else_does(declaration: catalog.Catalog) -> None:
    """Subscription, not availability — which is why the assertion is two-sided.

    `plan.available` has no rule for these, unlike the three sections beside it
    that a coordinate rules out. It could: a Mac cannot run winget any more than
    Arch can run a cask. What stops the rule being written today is that a Linux
    machine installing winget packages is not hypothetical — the WSL box does
    exactly that across `/mnt/c`, and forbidding it by `os_family` would decide
    against that before the verb doing it has been retired.

    So nothing but the manifest keeps these off the other four machines, and this
    is what says so the day one of them names a row.
    """
    declared = {entry.name for entry in declaration.section('winget_packages')}
    on_windows = {item.name for item in planned(declaration, 'windows-work-workstation').for_section('winget_packages')}

    assert declared, 'nothing declares a winget package, so this asserts nothing'
    assert on_windows == declared
    for name in MACHINES:
        if name != 'windows-work-workstation':
            assert not planned(declaration, name).for_section('winget_packages'), name


def test_every_winget_row_resolves_to_the_binary_it_puts_on_path(declaration: catalog.Catalog) -> None:
    """Three of the eight are named for the package and ship a differently-named
    binary — ripgrep/rg, fd-find/fd, git-delta/delta. The item carries what
    `evidence.by_command` asks PATH about, so a row whose `command` went missing
    would report itself installed on a machine that has no such executable.
    """
    plan = planned(declaration, 'windows-work-workstation')
    resolved = {item.name: item.executable for item in plan.for_section('winget_packages')}

    assert resolved['ripgrep'] == 'rg'
    assert resolved['fd-find'] == 'fd'
    assert resolved['git-delta'] == 'delta'
    assert all(resolved.values()), 'a row with no executable is measured by nothing'


DEPLOYED_TREES = ('apps', 'configs', 'shell')
"""The three trees that get symlinked into `$HOME`, and so the only places a
caller can invoke a binary from."""

WIN32YANK_CALL = re.compile(r'win32yank(\S*)[ \t]+-[io]\b')
"""`win32yank` followed by `-i` or `-o` on the same line — the two flags every
call site passes, and what invoking it looks like in shell, lua and tmux alike.

Anchoring on those flags rather than on a bare `-` is what keeps prose out. A
comment introducing the tool with a dash, `# win32yank - the clipboard bridge`,
otherwise reads as a caller under a name the entry does not install, and so does
a `--`-delimited aside or a quoted mention whose closing quote `\\S*` swallows.
The nvim provider named `win32yank-wsl` carries no flag and is excluded the same
way.
"""


def test_every_caller_invokes_the_win32yank_filename_the_entry_installs(declaration: catalog.Catalog) -> None:
    """The name is declared in one file and typed in three others, and nothing
    else compares them.

    `providers/ghrelease` writes `bin_dir() / entry.executable` and then asks
    `which` for that same name, so the check is a mirror: a machine whose
    clipboard is dead reports converged. `packages.yml` is the only place the
    installed filename is stated, and every call site names the `.exe` suffix
    that Linux, having no PATHEXT, will not supply on its own.

    Asserted against whatever the callers say rather than against a literal, so
    the pairing has to be broken on purpose from either side.
    """
    declared = declaration.find('github_releases', 'win32yank').executable

    called: dict[str, list[str]] = {}
    for tree in DEPLOYED_TREES:
        for path in sorted((REPO_ROOT / tree).rglob('*')):
            if not path.is_file():
                continue
            for number, line in enumerate(path.read_text(errors='ignore').splitlines(), start=1):
                for match in WIN32YANK_CALL.finditer(line):
                    called.setdefault(f'win32yank{match.group(1)}', []).append(f'{path.relative_to(REPO_ROOT)}:{number}')

    assert called, 'nothing invokes win32yank, so this asserts nothing'

    wrong = {name: sites for name, sites in called.items() if name != declared}
    assert not wrong, 'packages.yml installs {}; these ask for something else: {}'.format(
        declared, '; '.join(f'{name} at {", ".join(sites)}' for name, sites in sorted(wrong.items()))
    )


def test_a_system_package_with_no_name_under_this_manager_is_not_planned(tmp_path: Path) -> None:
    plan = synthetic(
        tmp_path,
        {'system_packages': [{'name': 'hyprland', 'pacman': 'hyprland'}, {'name': 'git', 'apt': 'git', 'pacman': 'git'}]},
        {'machine': 'box', 'platform': 'linux', 'system_packages': 'workstation'},
    )

    assert [item.name for item in plan.for_section('system_packages')] == ['git']


def test_an_aur_only_entry_is_planned_on_pacman(tmp_path: Path) -> None:
    """pacman selects a family — dropping `aur` loses five entries from Arch."""
    plan = synthetic(
        tmp_path,
        {'system_packages': [{'name': 'zen-browser', 'aur': 'zen-browser-bin'}]},
        {'machine': 'box', 'platform': 'archlinux', 'system_packages': 'workstation'},
    )

    assert [item.name for item in plan.for_section('system_packages')] == ['zen-browser']


# ─────────────────────────────────────────────────────────────────────────────
# What an item carries
# ─────────────────────────────────────────────────────────────────────────────


def test_the_plan_is_ordered_by_stage(declaration: catalog.Catalog) -> None:
    """Ordering is a real dependency chain: symlinks land after the tools that
    provide `task` and before tpm reads the tmux config they deploy."""
    stages = [item.stage for item in planned(declaration, 'archlinux-personal-workstation').items]

    assert stages == sorted(stages)


def test_an_item_names_what_pulled_it_in(declaration: catalog.Catalog) -> None:
    plan = planned(declaration, 'linux-lxc-server')

    assert plan.for_section('go_tools')[0].reason.selector == 'manifest:go_tools'
    assert plan.for_section('system_packages')[0].reason.selector == 'tier:core'


def test_an_entry_that_installs_no_binary_has_no_executable_to_look_for(tmp_path: Path) -> None:
    """A Python package pulled in for another tool's benefit installs a directory
    and no console script, and would otherwise read as permanently missing."""
    plan = synthetic(
        tmp_path,
        {'uv_tools': {'science': [{'name': 'numpy', 'library_only': True}, {'name': 'ruff'}]}},
        {'machine': 'box', 'platform': 'linux', 'uv_tools': ['numpy', 'ruff']},
    )
    executables = {item.name: item.executable for item in plan.for_section('uv_tools')}

    assert executables == {'numpy': '', 'ruff': 'ruff'}


def test_a_declared_install_path_becomes_the_evidence(tmp_path: Path) -> None:
    """A sourced bash library has nothing for `which` to find, so the checkout is
    the only evidence it installed."""
    plan = synthetic(
        tmp_path,
        {
            'custom_installers': [
                {
                    'name': 'bashselfupdate',
                    'description': 'sourced library',
                    'installed_path': '~/.local/lib/bashselfupdate',
                }
            ]
        },
        {'machine': 'box', 'platform': 'linux', 'custom_installers': ['bashselfupdate']},
    )

    installed = plan.for_section('custom_installers')[0]

    assert installed.evidence_path == '~/.local/lib/bashselfupdate'
    assert installed.executable == ''


def test_a_private_repo_carries_a_precondition_rather_than_being_dropped(declaration: catalog.Catalog) -> None:
    """Credentials are state a machine can lose, unlike a coordinate — so the item
    stays planned and the run says why it was skipped."""
    plan = planned(declaration, 'archlinux-personal-workstation')
    private = [item for item in plan.items if item.precondition is planning.Precondition.GITHUB_AUTH]

    assert private, 'the declaration has private-repo tools; none carried a precondition'


# ─────────────────────────────────────────────────────────────────────────────
# The runtimes, which are planned from what the tools resolved
# ─────────────────────────────────────────────────────────────────────────────

RUNTIMES = {'go': {'install_method': 'github_release', 'min_version': '1.23'}, 'rust': {'install_method': 'rustup'}}
GO_TOOL = {'go_tools': [{'name': 'task', 'package': 'github.com/go-task/task/v3/cmd/task'}]}
WANTS_GO = {'machine': 'box', 'platform': 'linux', 'go_tools': ['task']}


def test_a_runtime_is_planned_because_the_tools_that_need_it_are(tmp_path: Path) -> None:
    """Never because a manifest said `go: true` — that boolean was removed, since
    it said nothing the tool list did not and could be set with no tools at all."""
    plan = synthetic(tmp_path, {'runtimes': RUNTIMES, **GO_TOOL}, WANTS_GO)

    assert 'go-toolchain/go' in {item.address for item in plan.items}


def test_a_runtime_nothing_needs_is_not_planned(tmp_path: Path) -> None:
    plan = synthetic(tmp_path, {'runtimes': RUNTIMES, **GO_TOOL}, {'machine': 'box', 'platform': 'linux'})

    assert 'go-toolchain/go' not in {item.address for item in plan.items}


def test_uv_is_planned_for_every_machine(tmp_path: Path) -> None:
    """Ungated, unlike the other three: everything installed later resolves through
    it, and before the CLI existed the symlink phase itself shelled out to
    `uv run` and died with exit 127 on linux-lxc-server."""
    plan = synthetic(tmp_path, {'runtimes': RUNTIMES}, {'machine': 'box', 'platform': 'linux'})

    assert [item.address for item in plan.items] == ['uv-toolchain/uv']


def test_a_runtime_carries_the_row_that_declares_its_floor(tmp_path: Path) -> None:
    """And carries None where there is no row. `uv` and `node` have none at all, so
    an item with no entry is the case `Entry | None` exists for rather than an
    error — a synthetic row would be one `machines show` prints and `packages.yml`
    does not contain."""
    plan = synthetic(tmp_path, {'runtimes': RUNTIMES, **GO_TOOL}, WANTS_GO)
    carried = {item.name: item.entry for item in plan.for_section('runtimes')}

    assert isinstance(carried['go'], catalog.Runtime)
    assert carried['go'].min_version == '1.23'
    assert carried['uv'] is None


def test_a_runtime_runs_at_its_own_stage_however_late_it_is_planned(tmp_path: Path) -> None:
    """It is planned after the tools because it is planned *from* them, and it
    installs before them because the plan is sorted by stage on the way out."""
    plan = synthetic(tmp_path, {'runtimes': RUNTIMES, **GO_TOOL}, WANTS_GO)

    assert [item.address for item in plan.items] == ['go-toolchain/go', 'uv-toolchain/uv', 'go/task']


def test_owner_narrowing_drops_the_runtimes_whole(tmp_path: Path) -> None:
    """A runtime belongs to nobody, so filtering by owner would drop every one of
    them for answering `owner is None` — the wrong reason. `--mine` means "just my
    tools" and must not turn into a toolchain install nobody asked for."""
    install = tmp_path / 'install'
    (install / 'manifests').mkdir(parents=True)
    (install / 'packages.yml').write_text(yaml.safe_dump({'runtimes': RUNTIMES, **GO_TOOL}, sort_keys=False))
    (install / 'manifests' / 'box.yml').write_text(yaml.safe_dump(WANTS_GO, sort_keys=False))
    (install / 'flags.yml').write_text('{}')

    plan = resolve.resolve(catalog.load(install / 'packages.yml'), machines.load('box', tmp_path), owner='go-task')

    assert [item.address for item in plan.items] == ['go/task']


# ─────────────────────────────────────────────────────────────────────────────
# --package
# ─────────────────────────────────────────────────────────────────────────────


TPM = {'tmux_plugins': {'tpm': {'repo': 'https://github.com/tmux-plugins/tpm', 'install_dir': '~/.config/tmux/plugins/tpm'}}}
WANTS_TPM = {**WANTS_GO, 'tmux_plugins': True}


def narrowed_to(
    tmp_path: Path, packages: frozenset[str], declared: dict[str, Any] | None = None, manifest: dict[str, Any] | None = None
) -> list[str]:
    plan = synthetic(tmp_path, declared or {'runtimes': RUNTIMES, **GO_TOOL}, manifest or WANTS_GO, packages=packages)
    return [item.address for item in plan.items]


def test_a_package_narrowing_keeps_the_runtime_that_entry_needs(tmp_path: Path) -> None:
    """`cli-design.md` § "A narrowing flag reaches the whole run, or what it cannot
    reach is left out of the run": narrowing to `task` and dropping Go asks for
    something that cannot install, which is the failure `--source` already had and
    `registry.required_by` already answers.

    `uv` goes, and it is the pair that makes this a rule rather than a
    coincidence — it is a runtime too, and nothing named needs it.
    """
    assert narrowed_to(tmp_path, frozenset({'task'})) == ['go-toolchain/go', 'go/task']


def test_a_package_narrowing_can_name_the_runtime_itself(tmp_path: Path) -> None:
    """A runtime is a planned entry like any other, so naming one narrows to it.

    The tool it exists for is not dragged in with it: `needed_by` points from the
    section to the runtime, and reading it backwards would make a runtime name mean
    every tool that uses it.
    """
    assert narrowed_to(tmp_path, frozenset({'uv'})) == ['uv-toolchain/uv']


def test_an_empty_set_is_not_the_absence_of_the_flag(tmp_path: Path) -> None:
    """None is every entry and an empty set is none of them, which is why
    `Session.plan` passes `self.packages or None` rather than the field itself. A
    frozenset that meant both would make an unpassed flag resolve an empty plan and
    report a converged machine."""
    assert narrowed_to(tmp_path, frozenset()) == []
    assert narrowed_to(tmp_path, frozenset({'task', 'uv'})) == ['go-toolchain/go', 'uv-toolchain/uv', 'go/task']


def test_a_package_naming_a_row_that_belongs_to_no_section_keeps_no_runtime(tmp_path: Path) -> None:
    """`''` is two different facts, and matching them against each other equated them.

    A manager upgrade, a plugin sync and a toolchain gated by nothing all carry
    `''` — the first two as the section they were planned from, the last as the
    section that would gate it. So `required_by('')` answered "every ungated
    runtime", and narrowing to the tmux sync resolved a plan carrying uv, which
    `apply` then installed on a run that named a tmux plugin.

    Both rows named `tpm` stay: the clone and the sync are two items with one
    name, and a narrowing that kept one of them would be dropping work the other
    half of the pair depends on.
    """
    assert narrowed_to(tmp_path, frozenset({'tpm'}), {'runtimes': RUNTIMES, **GO_TOOL, **TPM}, WANTS_TPM) == ['tpm/tpm', 'tmux-sync/tpm']


# ─────────────────────────────────────────────────────────────────────────────
# --mine
# ─────────────────────────────────────────────────────────────────────────────


def test_owner_narrows_to_one_github_owner(declaration: catalog.Catalog) -> None:
    """The whole of `--mine`. The `owner_aware` column in phases.sh was a
    hand-maintained restatement of a fact already in the data."""
    plan = planned(declaration, 'archlinux-personal-workstation', owner='datapointchris')

    assert plan.items
    assert {item.entry.owner for item in plan.items} == {'datapointchris'}


def test_owner_leaves_registry_sourced_sections_empty(declaration: catalog.Catalog) -> None:
    """npm, PyPI and apt entries have no owner and correctly match nothing, so
    their provider resolves to zero items and is skipped for being empty."""
    plan = planned(declaration, 'archlinux-personal-workstation', owner='datapointchris')

    assert plan.for_section('npm_globals') == ()
    assert plan.for_section('system_packages') == ()


# ─────────────────────────────────────────────────────────────────────────────
# The axes fixture matrix
# ─────────────────────────────────────────────────────────────────────────────


def test_the_four_manifests_do_not_collapse_an_axis() -> None:
    """A fixture set that collapses an axis tests only the shapes it already covers.

    Asserted per axis rather than as a total, because a set that collapses to one
    value is the case a reader would not notice.
    """
    seen: dict[str, set[str]] = {axis: set() for axis in axes.AXES}
    for name in MACHINES:
        for axis, value in machines.load(name, REPO_ROOT).coordinates.as_dict().items():
            seen[axis].add(value)

    collapsed = [axis for axis, values in seen.items() if len(values) < 2]
    assert not collapsed, f'every real manifest agrees on {collapsed}, so nothing here tests those axes'


# ─────────────────────────────────────────────────────────────────────────────
# System configuration: narrowed per entry, not per section
# ─────────────────────────────────────────────────────────────────────────────


def system_plan(tmp_path: Path, system_config: dict[str, Any], manifest: dict[str, Any], **kwargs: Any) -> planning.Plan:
    install = tmp_path / 'install'
    (install / 'manifests').mkdir(parents=True)
    (install / 'packages.yml').write_text(yaml.safe_dump({'system_packages': [{'name': 'docker', 'pacman': 'docker'}]}))
    (install / 'system.yml').write_text(yaml.safe_dump(system_config, sort_keys=False))
    (install / 'manifests' / 'box.yml').write_text(yaml.safe_dump(manifest, sort_keys=False))
    (install / 'flags.yml').write_text('{}')
    return resolve.resolve(catalog.load(install / 'packages.yml'), machines.load('box', tmp_path), **kwargs)


def test_the_system_sections_resolve_after_the_packages_they_read() -> None:
    """The registry's order *is* the two passes, and this is what pins it.

    A system-config row can be decided by what the first pass planned — the docker
    group applies to a machine whose plan installs docker — so a provider reading
    `planned` must come after the one that fills it. Moving one up the tuple would
    silently drop the group membership on every machine.
    """
    order = [provider.section for provider in registry.PROVIDERS]
    first_system_section = min(order.index(section) for section in catalog.SYSTEM_SECTIONS)
    last_package_section = max(order.index(section) for section in catalog.SECTIONS if section in order)

    assert last_package_section < first_system_section


@pytest.mark.parametrize(
    ('platform', 'wanted'),
    [('archlinux', True), ('linux', False), ('macos', False)],
)
def test_display_stack_narrows_an_entry_to_the_machines_with_that_compositor(tmp_path: Path, platform: str, wanted: bool) -> None:
    """Hyprland replacing the display manager is a fact about the display stack,
    not about Arch — which is what stops a Ubuntu-with-Wayland box needing a
    second copy of the entry."""
    declared = {'systemd_units': [{'name': 'gdm', 'display_stack': 'wayland', 'enabled': False}]}
    plan = system_plan(tmp_path, declared, {'machine': 'box', 'platform': platform})

    assert bool(plan.for_resource('system')) is wanted


def test_an_entry_is_dropped_where_the_package_it_configures_is_not_installed(tmp_path: Path) -> None:
    """Creating a docker group on a server that never installs docker would leave
    a group configured for nothing and report drift forever on a correct box."""
    declared = {'group_memberships': [{'name': 'docker', 'requires_package': 'docker', 'create_group': True}]}

    with_docker = system_plan(tmp_path / 'a', declared, {'machine': 'box', 'platform': 'archlinux', 'system_packages': 'workstation'})
    without = system_plan(tmp_path / 'b', declared, {'machine': 'box', 'platform': 'archlinux', 'system_packages': False})

    # The `manager/*` rows come from the same plan and are not what this is about:
    # they are one per package manager the plan reaches, so the machine that
    # installs docker has them and the machine that installs nothing has none.
    planned = [item.address for item in with_docker.for_resource('system') if item.provider != 'manager']

    assert planned == ['system/docker', 'group/docker']
    assert without.for_resource('system') == ()


def test_a_feature_narrows_an_entry_to_the_manifests_that_asked_for_it(tmp_path: Path) -> None:
    declared = {'login_shell': [{'name': 'zsh', 'feature': 'configure_zsh'}]}

    asked = system_plan(tmp_path / 'a', declared, {'machine': 'box', 'platform': 'linux', 'configure_zsh': True})
    silent = system_plan(tmp_path / 'b', declared, {'machine': 'box', 'platform': 'linux'})

    assert [item.address for item in asked.for_resource('system')] == ['login-shell/zsh']
    assert silent.for_resource('system') == ()


def test_every_narrowing_on_an_entry_has_to_hold(tmp_path: Path) -> None:
    """They compose by conjunction, so an entry needing two conditions says both
    rather than needing a new combined axis invented for it."""
    declared = {'systemd_units': [{'name': 'docker.socket', 'requires_package': 'docker', 'display_stack': 'wayland'}]}
    plan = system_plan(tmp_path, declared, {'machine': 'box', 'platform': 'linux', 'system_packages': 'workstation'})

    assert plan.for_resource('system') == ()


def test_the_reason_names_what_put_the_row_in_the_plan(tmp_path: Path) -> None:
    """`machines show` is an audit, not a listing: under coordinate directories
    "what does this machine get" stops being answerable by reading one place."""
    declared = {'group_memberships': [{'name': 'docker', 'requires_package': 'docker'}]}
    plan = system_plan(tmp_path, declared, {'machine': 'box', 'platform': 'archlinux', 'system_packages': 'workstation'})

    assert [item.reason.selector for item in plan.for_resource('system') if item.provider == 'group'] == ['package:docker']


def test_an_unconditional_entry_says_so_rather_than_saying_nothing(tmp_path: Path) -> None:
    declared = {'managed_files': [{'name': 'zdotdir', 'path': '/etc/zshenv', 'append_line': 'x'}]}
    plan = system_plan(tmp_path, declared, {'machine': 'box', 'platform': 'linux'})

    assert [item.reason.selector for item in plan.for_resource('system')] == ['every machine']


def test_system_configuration_runs_after_everything_it_configures(tmp_path: Path) -> None:
    """The docker group needs docker, the login shell needs zsh, and nothing
    installed later needs any of them."""
    declared = {'login_shell': [{'name': 'zsh'}]}
    plan = system_plan(tmp_path, declared, {'machine': 'box', 'platform': 'linux', 'system_packages': 'workstation'})

    stages = [item.stage for item in plan.items]
    assert max(stages) is planning.Stage.SYSTEM_CONFIG
    assert [item.stage for item in plan.for_resource('system')][-1] is planning.Stage.SYSTEM_CONFIG
