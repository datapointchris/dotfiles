"""What each machine should have."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from dotfiles import catalog
from dotfiles import coordinates as axes
from dotfiles import machine as machines
from dotfiles import registry
from dotfiles import resolve

REPO_ROOT = Path(__file__).resolve().parents[2]
MACHINES = machines.names(REPO_ROOT)


@pytest.fixture(scope='module')
def declaration() -> catalog.Catalog:
    return catalog.load(REPO_ROOT / 'install' / 'packages.yml')


def planned(declaration: catalog.Catalog, name: str, **kwargs: Any) -> resolve.Plan:
    return resolve.resolve(declaration, machines.load(name, REPO_ROOT), **kwargs)


def synthetic(tmp_path: Path, packages: dict[str, Any], manifest: dict[str, Any]) -> resolve.Plan:
    install = tmp_path / 'install'
    (install / 'manifests').mkdir(parents=True)
    (install / 'packages.yml').write_text(yaml.safe_dump(packages, sort_keys=False))
    (install / 'manifests' / 'box.yml').write_text(yaml.safe_dump(manifest, sort_keys=False))
    (install / 'flags.yml').write_text('{}')
    return resolve.resolve(catalog.load(install / 'packages.yml'), machines.load('box', tmp_path))


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
    """A section in neither installs nothing and says nothing about it — which is
    the state `runtimes` sat in for months.

    Both declarations at once. `packages.yml` and `system.yml` used to be asked
    this separately because two maps answered it; one registry holds both, so a
    new section in either file has to answer the same question.
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
    private = [item for item in plan.items if item.precondition is resolve.Precondition.GITHUB_AUTH]

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
    """A fixture set carrying only expressible shapes tests only the old design.

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


def system_plan(tmp_path: Path, system_config: dict[str, Any], manifest: dict[str, Any], **kwargs: Any) -> resolve.Plan:
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
    """`machines show` is an audit, not a listing: under overlays "what does this
    machine get" stops being answerable by reading one directory."""
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
    assert max(stages) is resolve.Stage.SYSTEM_CONFIG
    assert [item.stage for item in plan.for_resource('system')][-1] is resolve.Stage.SYSTEM_CONFIG
