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
    SYSTEM = 20
    TOOLCHAIN = 30
    TOOLS = 40
    NODE = 50
    NODE_TOOLS = 60
    PYTHON_TOOLS = 70
    SHELL_PLUGINS = 80
    SYMLINKS = 90
    EDITOR_PLUGINS = 100


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

    def for_provider(self, provider: str) -> tuple[DesiredItem, ...]:
        return tuple(item for item in self.items if item.provider == provider)

    def for_stage(self, stage: Stage) -> tuple[DesiredItem, ...]:
        return tuple(item for item in self.items if item.stage is stage)

    def for_section(self, section: str) -> tuple[DesiredItem, ...]:
        return tuple(item for item in self.items if item.section == section)


PROVIDERS: dict[str, tuple[str, Stage]] = {
    'system_packages': ('system', Stage.SYSTEM),
    'macos_casks': ('cask', Stage.SYSTEM),
    'mas_apps': ('mas', Stage.SYSTEM),
    'flatpak_apps': ('flatpak', Stage.SYSTEM),
    'github_releases': ('ghrelease', Stage.TOOLS),
    'custom_installers': ('custom', Stage.TOOLS),
    'cargo_packages': ('cargo', Stage.TOOLS),
    'go_tools': ('go', Stage.TOOLS),
    'npm_globals': ('npm', Stage.NODE_TOOLS),
    'uv_tools': ('uv', Stage.PYTHON_TOOLS),
    'git_uv_tools': ('uv-git', Stage.PYTHON_TOOLS),
    'shell_plugins': ('shell-plugin', Stage.SHELL_PLUGINS),
    'tmux_plugins': ('tpm', Stage.EDITOR_PLUGINS),
}
"""Which provider installs a section, and when.

`system_packages` resolves to one provider whatever the manager is, because the
manager is a coordinate the provider reads — a provider per manager would be
three copies of one apply loop.
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

    for section, (provider, stage) in PROVIDERS.items():
        subscription = machine.subscription(section)
        for entry in declaration.section(section):
            if not subscription.wants(entry) or not available(entry, machine.coordinates):
                continue
            if owner is not None and entry.owner != owner:
                continue
            items.append(
                DesiredItem(
                    section=section,
                    provider=provider,
                    stage=stage,
                    name=entry.name,
                    executable=_executable(entry),
                    evidence_path=getattr(entry, 'installed_path', ''),
                    precondition=_precondition(entry),
                    entry=entry,
                    reason=Reason(section, _selector(section, subscription)),
                )
            )

    return Plan(machine=machine, items=tuple(sorted(items, key=lambda item: (item.stage, item.provider, item.name))))


def available(entry: catalog.Entry, coordinates: axes.Coordinates) -> bool:
    """Whether this machine's coordinates permit the entry at all.

    Not a subscription: a Mac is not *declining* flatpak, it cannot have it. The
    distinction is what stops `check` reporting a correctly-installed machine as
    broken — `win32yank` exists for exactly that reason and says so in the file.
    """
    if isinstance(entry, catalog.SystemPackage):
        return any(entry.package_for(installer) for installer in coordinates.installers)
    if isinstance(entry, catalog.MacosCask | catalog.MasApp):
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
