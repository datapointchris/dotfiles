"""Catalog × Machine → Plan. Pure.

"What should this machine have?" is answered today by 28 bash call sites, each
spawning an interpreter, re-parsing 258 entries, printing text, and handing that
text back to bash to re-parse. It is one function over two objects here, with no
subprocess, no network and no filesystem beyond what those two already hold.

That purity is what makes the whole machine × section matrix a parametrized test
with no fixtures. The 28 call sites could only ever be exercised by running an
installer, which is why nine bats files approximated them by running bash.

**Resolution finishes here.** No provider re-reads the catalog and nothing
downstream needs the Machine again: if a fact is not on the `DesiredItem`, it
does not affect the install. That is the property that makes
`dotfiles machines show` an audit rather than a summary — and it is a
precondition for the overlay layering, where "what does this machine get" stops
being answerable by reading one directory.
"""

from __future__ import annotations

import dataclasses as dc
import enum
from collections.abc import Iterator

from dotfiles import catalog
from dotfiles import coordinates as axes
from dotfiles import machine as machines


class Stage(enum.IntEnum):
    """Execution order *across* sections, replacing `install/phases.sh`'s registry.

    Ordering is a property of the work rather than of a CLI noun: symlinks must
    land after the tools that provide `task` and before tpm reads the tmux config
    it deploys, which is a constraint between two resources and therefore cannot
    live on either. The registry's other columns die with it — `group` becomes the
    stage's own name, `owner_aware` becomes `entry.owner`, and the install/update
    pair becomes one act, because reconcile has one verb.
    """

    ENVIRONMENT = 10
    IDENTITY = 15
    """Its own stage rather than part of ENVIRONMENT: the git identity lives in
    `~/.gitconfig`, has nothing to do with `~/.env`, and an address a caller
    branches on must not lie about which file it is talking about."""

    SYSTEM = 20
    TOOLCHAIN = 30
    TOOLS = 40
    NODE = 50
    NODE_TOOLS = 60
    PYTHON_TOOLS = 70
    SHELL_PLUGINS = 80
    SYMLINKS = 90
    EDITOR_PLUGINS = 100

    SYSTEM_CONFIG = 110
    """Last, where `install.sh` put the two halves of it that existed.

    Not beside SYSTEM, despite the name. Every row needs the package it
    configures to be installed first — the docker group, the unit that serves the
    socket, zsh before it can be the login shell — and nothing installed later
    needs any of them. `apply` ending on the one stage that asks for a password
    is a property worth keeping rather than an accident of where it landed.
    """


class Precondition(enum.StrEnum):
    """State a machine can be in that stops an item installing, checked live.

    Distinct from a coordinate, which is a fact about the machine and filters the
    plan outright. Credentials are the difference: a `gh` login is something a
    machine can lose, so the item stays in the plan and the run says why it was
    skipped — where a Mac simply never plans win32yank at all.
    """

    NONE = ''
    GITHUB_AUTH = 'github_auth'


@dc.dataclass(frozen=True, slots=True)
class Reason:
    """Why this item is in the plan.

    A precondition rather than a nicety: under overlays, "what does this machine
    get" stops being answerable by reading one directory, and every overlay system
    worth copying fails exactly there. If the resolver cannot name what pulled
    something in, the audit command is a listing.
    """

    section: str
    selector: str

    def __str__(self) -> str:
        return f'{self.section}: {self.selector}'


@dc.dataclass(frozen=True, slots=True)
class DesiredItem:
    """One thing this machine should have, fully resolved."""

    section: str
    provider: str
    resource: str
    stage: Stage
    name: str
    executable: str
    evidence_path: str
    precondition: Precondition
    entry: catalog.Entry
    reason: Reason

    @property
    def address(self) -> str:
        return f'{self.provider}/{self.name}'

    def as_dict(self) -> dict[str, str]:
        return {
            'section': self.section,
            'provider': self.provider,
            'resource': self.resource,
            'stage': self.stage.name.lower(),
            'name': self.name,
            'executable': self.executable,
            'evidence_path': self.evidence_path,
            'precondition': str(self.precondition),
            'selector': self.reason.selector,
        }


@dc.dataclass(frozen=True, slots=True)
class Plan:
    machine: machines.Machine
    items: tuple[DesiredItem, ...]
    runtimes: tuple[catalog.Runtime, ...] = ()
    """The declared runtimes, carried rather than looked up.

    They are `Spelling.DERIVED` — no manifest subscribes to one — but the
    toolchain resource needs their version constraints, and resolution finishing
    here means it must not reach back into the catalog for them.
    """

    @property
    def providers(self) -> frozenset[str]:
        """Which providers have anything to do, which is how a phase learns it is empty.

        The replacement for `install/phases.sh`'s `owner_aware` column, and
        strictly finer than it: the plan is already narrowed by this machine's
        subscriptions, so a machine declaring none of the owner's Go tools skips
        the go-tools phase outright rather than running its installer over an
        empty list.
        """
        return frozenset(item.provider for item in self.items)

    def for_provider(self, provider: str) -> tuple[DesiredItem, ...]:
        return tuple(item for item in self.items if item.provider == provider)

    def for_resource(self, resource: str) -> tuple[DesiredItem, ...]:
        return tuple(item for item in self.items if item.resource == resource)

    def for_stage(self, stage: Stage) -> tuple[DesiredItem, ...]:
        return tuple(item for item in self.items if item.stage is stage)

    def for_section(self, section: str) -> tuple[DesiredItem, ...]:
        return tuple(item for item in self.items if item.section == section)


@dc.dataclass(frozen=True, slots=True)
class Provider:
    """Who installs a section, when, and which resource owns the answer.

    The `resource` column is what `install/phases.sh`'s registry hand-maintained.
    It lives here because it is a property of the section rather than of the
    resource: a resource asking the plan for its own items cannot then disagree
    with the phase that installs them.
    """

    name: str
    stage: Stage
    resource: str


PROVIDERS: dict[str, Provider] = {
    'system_packages': Provider('system', Stage.SYSTEM, 'system'),
    'macos_casks': Provider('cask', Stage.SYSTEM, 'system'),
    'mas_apps': Provider('mas', Stage.SYSTEM, 'system'),
    'flatpak_apps': Provider('flatpak', Stage.SYSTEM, 'system'),
    'github_releases': Provider('ghrelease', Stage.TOOLS, 'packages'),
    'custom_installers': Provider('custom', Stage.TOOLS, 'packages'),
    'cargo_packages': Provider('cargo', Stage.TOOLS, 'packages'),
    'go_tools': Provider('go', Stage.TOOLS, 'packages'),
    'npm_globals': Provider('npm', Stage.NODE_TOOLS, 'packages'),
    'uv_tools': Provider('uv', Stage.PYTHON_TOOLS, 'packages'),
    'git_uv_tools': Provider('uv-git', Stage.PYTHON_TOOLS, 'packages'),
    'shell_plugins': Provider('shell-plugin', Stage.SHELL_PLUGINS, 'plugins'),
    'tmux_plugins': Provider('tpm', Stage.EDITOR_PLUGINS, 'plugins'),
}
"""Which provider installs a section, when, and for which resource.

`system_packages` resolves to one provider whatever the manager is, because the
manager is a coordinate the provider reads — a provider per manager would be
three copies of one apply loop.
"""

SYSTEM_PROVIDERS: dict[str, Provider] = {
    'group_memberships': Provider('group', Stage.SYSTEM_CONFIG, 'system'),
    'systemd_units': Provider('systemd', Stage.SYSTEM_CONFIG, 'system'),
    'managed_files': Provider('file', Stage.SYSTEM_CONFIG, 'system'),
    'login_shell': Provider('login-shell', Stage.SYSTEM_CONFIG, 'system'),
    'macos_defaults': Provider('macos-default', Stage.SYSTEM_CONFIG, 'system'),
    'steps': Provider('step', Stage.SYSTEM_CONFIG, 'system'),
}
"""`system.yml`'s sections, resolved in a second pass rather than beside the rest.

They cannot be in `PROVIDERS`: that loop asks the manifest what it subscribes to,
and no manifest subscribes to a group membership. What decides a system-config
row instead is a coordinate, a feature, or *the result of the first pass* — the
docker group applies where this machine's plan installs docker, which is not
knowable until the packages have resolved.
"""

UNPROVIDED: dict[str, str] = {
    'runtimes': 'derived by the toolchain resource from the tool sections that need one, never subscribed to directly',
    'zen_extensions': 'declared and installed by nothing; the browser profile is not managed from here yet',
}
"""Sections deliberately absent from the plan, each with the reason.

A section in neither map is a section silently installing nothing, which is the
failure `runtimes` sat in for months — declared, validated by nothing, resolved
by nothing.
"""


def resolve(declaration: catalog.Catalog, machine: machines.Machine, *, owner: str | None = None) -> Plan:
    """Everything `machine` should have, in the order it has to be installed.

    `owner` is the whole of `--mine`. The `owner_aware` column in
    `install/phases.sh` was a hand-maintained restatement of a fact already in the
    data; a provider whose entries all belong to someone else resolves to zero
    items and is skipped because it is empty, not because a column said so.
    """
    items: list[DesiredItem] = []

    for section, provider in PROVIDERS.items():
        subscription = machine.subscription(section)
        for entry in declaration.section(section):
            if not subscription.wants(entry) or not available(entry, machine.coordinates):
                continue
            if owner is not None and entry.owner != owner:
                continue
            items.append(
                DesiredItem(
                    section=section,
                    provider=provider.name,
                    resource=provider.resource,
                    stage=provider.stage,
                    name=entry.name,
                    executable=_executable(entry),
                    evidence_path=getattr(entry, 'installed_path', ''),
                    precondition=_precondition(entry),
                    entry=entry,
                    reason=Reason(section, _selector(section, subscription)),
                )
            )

    if owner is None:
        items.extend(_system_configuration(declaration, machine, {item.name for item in items if item.section == 'system_packages'}))

    return Plan(
        machine=machine,
        items=tuple(sorted(items, key=lambda item: (item.stage, item.provider, item.name))),
        runtimes=tuple(entry for entry in declaration.section('runtimes') if isinstance(entry, catalog.Runtime)),
    )


def _system_configuration(
    declaration: catalog.Catalog,
    machine: machines.Machine,
    installed: set[str],
) -> Iterator[DesiredItem]:
    """The `system.yml` rows this machine wants, given what it already resolved.

    Absent entirely from an owner-narrowed plan, rather than filtered by it: a
    group membership belongs to nobody on GitHub, so every row would answer
    `owner is None` and be dropped for the wrong reason. `--mine` means "just my
    tools" — usually right after releasing one — and it must not turn into a
    password prompt for a system reconfiguration nobody asked for.
    """
    for section, provider in SYSTEM_PROVIDERS.items():
        for entry in declaration.section(section):
            assert isinstance(entry, catalog.SystemConfig)
            if not available(entry, machine.coordinates) or not configures(entry, machine, installed):
                continue
            yield DesiredItem(
                section=section,
                provider=provider.name,
                resource=provider.resource,
                stage=provider.stage,
                name=entry.name,
                executable='',
                evidence_path='',
                precondition=Precondition.NONE,
                entry=entry,
                reason=Reason(section, _decided_by(entry)),
            )


def configures(entry: catalog.SystemConfig, machine: machines.Machine, installed: set[str]) -> bool:
    """Whether one system-config row applies to this machine.

    Each key narrows independently and all of them must hold, so an entry needing
    two conditions says both rather than needing a new combined axis.
    """
    if any(value != str(getattr(machine.coordinates, axis)) for axis, value in entry.narrowing.items()):
        return False
    if entry.requires_package and entry.requires_package not in installed:
        return False
    return not (entry.feature and not machine.wants(entry.feature))


def _decided_by(entry: catalog.SystemConfig) -> str:
    """What put this row in the plan, for `machines show` to print."""
    narrowings = {'package': entry.requires_package, **entry.narrowing, 'feature': entry.feature}
    named = ', '.join(f'{key}:{value}' for key, value in narrowings.items() if value)
    return named or 'every machine'


def available(entry: catalog.Entry, coordinates: axes.Coordinates) -> bool:
    """Whether this machine's coordinates permit the entry at all.

    Not a subscription: a Mac is not *declining* flatpak, it cannot have it. The
    distinction is what stops `check` reporting a correctly-installed machine as
    broken — `win32yank` exists for exactly that reason and says so in the file.
    """
    if isinstance(entry, catalog.SystemPackage):
        return any(entry.package_for(installer) for installer in coordinates.installers)
    if isinstance(entry, catalog.MacosCask | catalog.MasApp | catalog.MacosDefault):
        return coordinates.os_family is axes.OSFamily.DARWIN
    if isinstance(entry, catalog.FlatpakApp):
        return coordinates.os_family is axes.OSFamily.LINUX
    if isinstance(entry, catalog.GithubRelease) and entry.requires_wsl_host:
        return coordinates.host is axes.Host.WSL
    return True


def _executable(entry: catalog.Entry) -> str:
    """The binary to look for, or '' where the entry installs none.

    A sourced bash library and a Python package pulled in for another tool's
    benefit both put nothing on PATH, and would read as permanently missing.
    """
    if isinstance(entry, catalog.UvTool) and entry.library_only:
        return ''
    if isinstance(entry, catalog.CustomInstaller) and entry.installed_path and not entry.command:
        return ''
    return entry.executable


def _precondition(entry: catalog.Entry) -> Precondition:
    needs_auth = getattr(entry, 'requires_github_auth', False)
    return Precondition.GITHUB_AUTH if needs_auth else Precondition.NONE


def _selector(section: str, subscription: machines.Subscription) -> str:
    if subscription.tier:
        return f'tier:{subscription.tier}'
    if subscription.declared:
        return f'manifest:{section}'
    return f'catalog:{section}'
