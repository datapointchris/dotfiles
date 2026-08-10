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
    IDENTITY = 15
    """Its own stage rather than part of ENVIRONMENT: the git identity lives in
    `~/.gitconfig`, has nothing to do with `~/.env`, and an address a caller
    branches on must not lie about which file it is talking about."""

    SYSTEM = 20
    SYSTEM_APPS = 25
    """Casks, App Store apps and flatpak apps, all of which need SYSTEM first.

    Not a nicety: `mas` is itself a Homebrew formula, a cask needs the brew the
    formula stage bootstrapped, and a flatpak app needs the flatpak binary. The
    plan sorts on `(stage, provider, name)`, so without a stage of their own all
    three would sort *before* `system` on the provider name alone and every one of
    them would run against a manager that was not there yet.
    """

    SYSTEM_UPGRADE = 27
    """Bringing each package manager's installed set up to date, after both.

    After rather than before, for two reasons. A manager that had to be
    bootstrapped — Homebrew on a fresh Mac, flatpak on a machine that just
    declared its first app — cannot be asked what is behind until the stage that
    installs it has run. And the partial-upgrade constraint an install has is
    already covered by `syspkg.REFRESH`, which syncs before each transaction; this
    stage is about the packages nothing planned to touch.
    """

    TOOLCHAIN = 30
    TOOLS = 40
    NODE = 50
    NODE_TOOLS = 60
    PYTHON_TOOLS = 70
    SHELL_PLUGINS = 80
    SYMLINKS = 90
    TMUX_PLUGINS = 100
    TMUX_PLUGIN_SYNC = 102
    YAZI_PLUGINS = 105
    NVIM_PLUGIN_SYNC = 107
    """All four after SYMLINKS, because each program reads the config that pass
    just deployed.

    The two syncs are stages of their own rather than riding the clone beside
    them, and the ordering is a real dependency both times: TPM installs the
    plugins `tmux.conf` names and TPM itself is the clone at TMUX_PLUGINS, so the
    sync cannot precede it. The plan sorts on `(stage, provider, name)`, which
    would have put `tmux-sync` before `tpm` on the provider name alone — a
    dependency held by alphabetical accident is one a rename breaks silently.
    """

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

    AMD_GPU = 'amd_gpu'
    """A ROCm build, which is 12 GiB of runtime for a device that may not be there.

    A precondition rather than a coordinate, and the distinction was argued rather
    than assumed. A seventh axis fails the bar `.planning/machine-axes.md` sets —
    each of the six is forced by dozens of consumers and this would be forced by
    one package name, which is what got "offline / restricted egress" rejected as
    n=1 and told to be a capability requirement instead. `coordinates.Arch` is the
    same verdict reached independently: a hardware fact deliberately kept out of
    the tuple because one consumer needed it.

    It also *cannot* be a coordinate, whatever the evidence said. Resolution is
    machine-independent by construction — `machines check` validates all four
    manifests offline from any machine, and `machines show <other>` describes that
    machine rather than this one — so a hardware probe inside `available()` would
    make the Mac's view of the Arch plan differ from the Arch box's.
    """


@dc.dataclass(frozen=True, slots=True)
class Preconditions:
    """Which of them this machine currently meets, measured once per observation.

    A record rather than a probe per item: both are questions about the machine
    and neither varies between two entries asking it, so one answer is carried to
    every row that names it. `evidence.measured_preconditions` is what fills it,
    and the default is the pessimistic reading — a caller that measured nothing
    has not thereby satisfied anything.
    """

    github_auth: bool = False
    amd_gpu: bool = False

    def holds(self, precondition: Precondition) -> bool:
        """Every member named, and an unnamed one refuses.

        `NONE` answers True by being written down rather than by falling off the
        end. The difference is what a *new* member gets: adding one is a one-line
        change in the enum above, and a dispatch that absorbed it silently would
        answer "satisfied" — a declared precondition quietly no longer gating the
        install it was declared to gate, which is failing open in the direction
        that does the thing.
        """
        if precondition is Precondition.NONE:
            return True
        if precondition is Precondition.GITHUB_AUTH:
            return self.github_auth
        if precondition is Precondition.AMD_GPU:
            return self.amd_gpu
        return False


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
    entry: catalog.Entry | None
    """The declaration row behind it, where one exists.

    None for an item nothing declares individually: a runtime is in the plan
    because the tools that need it are, and `uv` and `node` have no `runtimes` row
    at all. A `TypeVar` bounded on `Entry` would be uninhabitable for those, and a
    synthetic entry would be a row `machines show` prints that `packages.yml` does
    not contain.
    """

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

    @property
    def providers(self) -> frozenset[str]:
        """Which providers have anything to do, which is how a stage learns it is empty.

        The replacement for `install/phases.sh`'s `owner_aware` column, and
        strictly finer than it: the plan is already narrowed by this machine's
        subscriptions, so a machine declaring none of the owner's Go tools skips
        the go-tools stage outright rather than running its installer over an
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


def resolve(declaration: catalog.Catalog, machine: machines.Machine, *, owner: str | None = None) -> Plan:
    """Everything `machine` should have, in the order it has to be installed.

    One loop over the registry, and the registry's order *is* the two passes: a
    provider is handed what every earlier provider resolved, so the system-config
    rows that read the package plan get it as an argument rather than through a
    hand-placed second call.

    `owner` is the whole of `--mine`, and it narrows the plan rather than feeding
    it. The `owner_aware` column in `install/phases.sh` was a hand-maintained
    restatement of a fact already in the data; a provider whose entries all belong
    to someone else resolves to zero items and is skipped because it is empty, not
    because a column said so.

    The registry is imported here rather than at module scope because its
    providers build the item types defined in this file — asking for it at import
    time closes the loop.
    """
    from dotfiles import registry

    items: list[DesiredItem] = []
    for provider in registry.PROVIDERS:
        if owner is not None and not provider.ownable:
            continue
        planned = provider.plan(machine, declaration, tuple(items))
        if owner is not None:
            planned = tuple(item for item in planned if item.entry is not None and item.entry.owner == owner)
        items.extend(planned)

    return Plan(machine=machine, items=tuple(sorted(items, key=lambda item: (item.stage, item.provider, item.name))))


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


def available(entry: catalog.Entry, coordinates: axes.Coordinates) -> bool:
    """Whether this machine's coordinates permit the entry at all.

    Not a subscription: a Mac is not *declining* flatpak, it cannot have it. The
    distinction is what stops `check` reporting a correctly-installed machine as
    broken — `win32yank` exists for exactly that reason and says so in the file.
    """
    if isinstance(entry, catalog.SystemPackage):
        if entry.excludes_host and str(coordinates.host) == entry.excludes_host:
            return False
        return any(entry.package_for(installer) for installer in coordinates.installers)
    if isinstance(entry, catalog.MacosCask | catalog.MasApp | catalog.MacosDefault):
        return coordinates.os_family is axes.OSFamily.DARWIN
    if isinstance(entry, catalog.FlatpakApp):
        return coordinates.os_family is axes.OSFamily.LINUX
    if isinstance(entry, catalog.GithubRelease) and entry.requires_wsl_host:
        return coordinates.host is axes.Host.WSL
    return True
