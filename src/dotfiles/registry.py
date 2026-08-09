"""Every mechanism that installs something, as one object each.

The provider concept was written five times in five keyings, and none of the five
knew about the others. `resolve.PROVIDERS` said which section a provider plans
from and when; `resolve.SYSTEM_PROVIDERS` said the same for the second pass;
`evidence.EVIDENCE` and `evidence.REGISTRY_PROVIDERS` said how to tell whether one
of its items is present; `resources/packages.py:PERFORMED` said how to install
one. Adding a mechanism meant editing four files and remembering the fifth, and
forgetting one was silent — a section named in no table resolves to nothing and
installs nothing, which is what `runtimes` did for months before `UNPROVIDED`
made the absence declarable.

One class per mechanism, and the tables become its fields and its methods.

**Planning is two-pass, and the signature says so.** `plan` is handed what the
providers before it planned, because the second pass genuinely depends on the
first: the docker group applies to a machine whose plan installs docker, which is
not knowable until the packages have resolved. That ordering used to be an
argument threaded into one private function in `resolve.py`; it is the protocol
now, and a third pass needs no new plumbing.

**Only `plan` is handed the Catalog.** `evidence` and `install` take a resolved
`DesiredItem` and cannot reach back for a fact the item does not carry, which
turns `resolve.py`'s "resolution finishes here" from a prose invariant into
something the signatures enforce.

**`install` is the only method handed a `Privilege`.** `plan`, `evidence` and the
observation behind them are not, so "the read-only verbs never escalate" is a
property of the signatures rather than a promise about the bodies.

The mechanisms are imported here rather than reached lazily: together they cost a
few ms on top of this module's own 85ms, measured, which is not worth a local
import inside every method and the explanation each would need.
"""

from __future__ import annotations

import dataclasses as dc
from collections.abc import Sequence

from dotfiles import catalog as catalogs
from dotfiles import coordinates
from dotfiles import evidence as ev
from dotfiles import machine as machines
from dotfiles import providers
from dotfiles import resolve
from dotfiles.privilege import Privilege
from dotfiles.providers import cargo
from dotfiles.providers import clone
from dotfiles.providers import custom
from dotfiles.providers import ghrelease
from dotfiles.providers import gotool
from dotfiles.providers import macdefaults
from dotfiles.providers import npm
from dotfiles.providers import steps
from dotfiles.providers import sysconfig
from dotfiles.providers import toolchain
from dotfiles.resolve import DesiredItem
from dotfiles.resolve import Reason
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Outcome
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Verdict
from dotfiles.session import Session


@dc.dataclass(frozen=True, slots=True)
class Provider:
    """One way of installing things, and everything that is true of all of them.

    The base is not abstract on purpose. A provider whose mechanism this package
    does not drive yet — the ones that still install through a phase — is a
    faithful description of what the machine has: it plans, its items are
    observable, and only the write is elsewhere. `install` says so in words a run
    can print, which is what the partial `PERFORMED` map used to leave to whichever
    resource happened to look the provider up and find nothing.
    """

    name: str
    """What `--skip`, `machines show` and the run record call it."""

    resource: str
    """The CLI noun that groups it.

    A grouping, not an owner: `packages` gathers seven mechanisms that have
    nothing in common but where a reader looks for them. Ordering, evidence and
    installation are the provider's; only the help text and the folded row are the
    resource's.
    """

    stage: Stage

    section: str = ''
    """The declaration section it plans from, or '' for one that subscribes to none.

    A toolchain is the second kind: nothing declares Go, and a machine has it
    because it declared `go_tools`. So the section is what a *subscription* names,
    and `BY_SECTION` indexes only the providers that have one.
    """

    ownable: bool = True
    """Whether an owner can be traced for this provider's items.

    A provider that cannot is skipped whole under `--owner` rather than filtered
    by it: a group membership belongs to nobody on GitHub, so every row would
    answer `owner is None` and be dropped for the wrong reason. `--mine` means
    "just my tools", usually right after releasing one, and it must not turn into
    a password prompt for a system reconfiguration nobody asked for.
    """

    def plan(self, machine: machines.Machine, declaration: catalogs.Catalog, planned: tuple[DesiredItem, ...]) -> tuple[DesiredItem, ...]:
        """What this machine should have from this provider, fully resolved.

        `planned` is what every earlier provider resolved, which is what makes the
        two passes one loop instead of a special case.
        """
        return ()

    def evidence(self, item: DesiredItem, installed: ev.Inventory) -> ev.Evidence:
        """Whether one of this provider's items is present.

        A declared `installed_path` beats any rule about the provider, because an
        entry saying where it lands is more specific than a rule about how its
        neighbours are usually found. That override is here rather than in each
        `measure` so it cannot be forgotten by one of them.
        """
        return ev.by_path(item) if item.evidence_path else self.measure(item, installed)

    def measure(self, item: DesiredItem, installed: ev.Inventory) -> ev.Evidence:
        """The provider's own rule. A binary on PATH, unless it says otherwise."""
        return ev.by_command(item)

    def needs_root(self, item: DesiredItem) -> bool:
        """Whether repairing this item escalates, known before anything runs.

        A method rather than the flat field the design called for, because for
        half the registry the answer is per entry and already declared: macOS
        preferences are user-level throughout and the Xcode licence is the one
        step whose *read* needs root. A field here plus that field on the entry
        would be two sources for one fact, which is the disease this module
        exists to cure.
        """
        return False

    def install(self, session: Session, change: Change, item: DesiredItem, privilege: Privilege) -> Outcome:
        """Repair one item, re-checking live that it is still the right thing to do.

        Refused rather than silently skipped by the providers that still install
        through a phase, because a provider that did nothing quietly would leave
        `apply` reporting a converged machine.
        """
        return Outcome(change, OutcomeStatus.REFUSED, f"run 'dotfiles {self.resource} apply', which still drives the phase registry")


@dc.dataclass(frozen=True, slots=True)
class CatalogProvider(Provider):
    """A `packages.yml` section a manifest subscribes to.

    Subscription and availability are different questions and both are asked: a
    machine can decline flatpak, and a Mac simply cannot have it. Collapsing them
    would make `check` report a correctly-installed machine as broken.
    """

    def plan(self, machine: machines.Machine, declaration: catalogs.Catalog, planned: tuple[DesiredItem, ...]) -> tuple[DesiredItem, ...]:
        subscription = machine.subscription(self.section)
        return tuple(
            DesiredItem(
                section=self.section,
                provider=self.name,
                resource=self.resource,
                stage=self.stage,
                name=entry.name,
                executable=executable_of(entry),
                evidence_path=getattr(entry, 'installed_path', ''),
                precondition=precondition_of(entry),
                entry=entry,
                reason=Reason(self.section, selector_of(self.section, subscription)),
            )
            for entry in declaration.section(self.section)
            if subscription.wants(entry) and resolve.available(entry, machine.coordinates)
        )


@dc.dataclass(frozen=True, slots=True)
class VendoredProvider(CatalogProvider):
    """A tool this package fetches and unpacks itself: a release, or a vendor's
    own installer driven through `providers/`.

    These are the two that have converted, and the two whose `install` the phase
    registry also calls — so the two front doors cannot install one tool
    differently.
    """

    def install(self, session: Session, change: Change, item: DesiredItem, privilege: Privilege) -> Outcome:
        if arrived := self._arrived(change, item):
            return arrived
        result = self.fetch(session, item)
        return Outcome(change, OutcomeStatus.DONE if result.ok else OutcomeStatus.FAILED, result.detail)

    def fetch(self, session: Session, item: DesiredItem) -> providers.Result:
        raise NotImplementedError

    def _arrived(self, change: Change, item: DesiredItem) -> Outcome | None:
        """The item installed itself between `observe` and here, so leave it alone.

        Not defensive padding. `observe` ran before the report was printed and
        before anything upstream in the stage order installed a toolchain, so a
        MISSING item may have arrived since — and installing over it would replace
        a binary nobody asked about with whatever upstream calls latest now. A
        STALE one is deliberately *not* re-checked this way: being behind is what
        this repairs.
        """
        if change.verdict is Verdict.MISSING and self.evidence(item, {}).verdict is Verdict.MATCHED:
            return Outcome(change, OutcomeStatus.SKIPPED, f'{item.executable} arrived before this ran')
        return None


@dc.dataclass(frozen=True, slots=True)
class ReleaseProvider(VendoredProvider):
    """A binary published as a GitHub release asset."""

    def fetch(self, session: Session, item: DesiredItem) -> providers.Result:
        entry = item.entry
        if not isinstance(entry, catalogs.GithubRelease):
            return providers.Result(False, f'{item.name} is not a github_releases entry')
        return ghrelease.install(entry, coordinates.target_for(session.machine.coordinates), offline=session.offline)


@dc.dataclass(frozen=True, slots=True)
class CustomProvider(VendoredProvider):
    """A vendor that ships its own installer."""

    def fetch(self, session: Session, item: DesiredItem) -> providers.Result:
        entry = item.entry
        if not isinstance(entry, catalogs.CustomInstaller):
            return providers.Result(False, f'{item.name} is not a custom_installers entry')
        return custom.install(entry, coordinates.target_for(session.machine.coordinates), offline=session.offline)


@dc.dataclass(frozen=True, slots=True)
class CargoProvider(CatalogProvider):
    """A Rust CLI installed by `cargo binstall`, or restored from a bundle.

    Not a `VendoredProvider` for the same reason `GoToolProvider` is not: nothing
    here fetches an asset this package names. binstall resolves the crate, picks
    the release its project published, and places the binary.
    """

    def install(self, session: Session, change: Change, item: DesiredItem, privilege: Privilege) -> Outcome:
        entry = item.entry
        if not isinstance(entry, catalogs.CargoPackage):
            return Outcome(change, OutcomeStatus.REFUSED, f'{item.name} is not a cargo_packages entry')
        result = cargo.install(entry, coordinates.target_for(session.machine.coordinates), offline=session.offline)
        return Outcome(change, OutcomeStatus.DONE if result.ok else OutcomeStatus.FAILED, result.detail)


@dc.dataclass(frozen=True, slots=True)
class GoToolProvider(CatalogProvider):
    """A Go module installed by the toolchain that built it.

    Not a `VendoredProvider`: nothing here fetches an asset this package names.
    `go install` resolves the module, builds it and places the binary, and the
    only alternative source is the prebuilt binary an offline bundle carries.
    """

    def install(self, session: Session, change: Change, item: DesiredItem, privilege: Privilege) -> Outcome:
        entry = item.entry
        if not isinstance(entry, catalogs.GoTool):
            return Outcome(change, OutcomeStatus.REFUSED, f'{item.name} is not a go_tools entry')
        result = gotool.install(entry, offline=session.offline)
        return Outcome(change, OutcomeStatus.DONE if result.ok else OutcomeStatus.FAILED, result.detail)


@dc.dataclass(frozen=True, slots=True)
class NpmProvider(CatalogProvider):
    """A global package from the npm registry.

    No currency, unlike the go and cargo providers beside it. `npm update -g`
    upgrades every global in one call and the registry owns what latest means, so
    asking per package whether it is behind is asking a question npm already
    answers for itself — which is what `resources/packages.CURRENCY` says.
    """

    def install(self, session: Session, change: Change, item: DesiredItem, privilege: Privilege) -> Outcome:
        entry = item.entry
        if not isinstance(entry, catalogs.NpmGlobal):
            return Outcome(change, OutcomeStatus.REFUSED, f'{item.name} is not an npm_globals entry')
        result = npm.install(entry, offline=session.offline)
        return Outcome(change, OutcomeStatus.DONE if result.ok else OutcomeStatus.FAILED, result.detail)


@dc.dataclass(frozen=True, slots=True)
class RegistryProvider(CatalogProvider):
    """A provider whose items only its own package manager can answer for.

    A package name is not a binary name: `p7zip-full` installs `7zz`, and
    `build-essential` and `ca-certificates` install no executable at all. Asking
    PATH about them reports every one of them missing on a fully-installed
    machine, which is why the check that predated this skipped these sections
    rather than getting them wrong.
    """

    def measure(self, item: DesiredItem, installed: ev.Inventory) -> ev.Evidence:
        return ev.by_registry(item, installed)


@dc.dataclass(frozen=True, slots=True)
class SystemPackageProvider(RegistryProvider):
    """apt, pacman, the AUR and Homebrew formulae, which is one provider.

    The manager is a coordinate this provider reads rather than a provider of its
    own: three classes differing only in which binary they shell out to would be
    three copies of one apply loop, and the entry already declares a name per
    manager.
    """

    def needs_root(self, item: DesiredItem) -> bool:
        return True


@dc.dataclass(frozen=True, slots=True)
class UvToolProvider(CatalogProvider):
    """uv installs a tool per directory, and some are libraries with no script."""

    def measure(self, item: DesiredItem, installed: ev.Inventory) -> ev.Evidence:
        return ev.by_uv_tool(item)


@dc.dataclass(frozen=True, slots=True)
class AppStoreProvider(CatalogProvider):
    """An App Store app, judged by its bundle. Its CLI is a second question."""

    def measure(self, item: DesiredItem, installed: ev.Inventory) -> ev.Evidence:
        return ev.by_app_bundle(item)


@dc.dataclass(frozen=True, slots=True)
class CloneProvider(CatalogProvider):
    """A plugin whose evidence is a checkout under `$HOME`.

    It deliberately does not override `measure`. Where the checkout belongs is a
    path relative to a home directory, and `evidence` is handed neither — so the
    plugins resource observes these itself rather than this class answering with
    a `which` that would be wrong for every one of them. The honest fix is the
    session-taking `observe` the provider protocol grows when the engine walks
    providers; guessing here in the meantime would be worse than not answering.
    """

    def install(self, session: Session, change: Change, item: DesiredItem, privilege: Privilege) -> Outcome:
        if clone.destination(item, session.home).is_dir():
            return Outcome(change, OutcomeStatus.SKIPPED, f'{clone.destination(item, session.home)} appeared since the check')
        result = clone.clone(item, session.home)
        return Outcome(change, OutcomeStatus.DONE if result.ok else OutcomeStatus.FAILED, result.detail)


@dc.dataclass(frozen=True, slots=True)
class ToolchainProvider(Provider):
    """A language runtime, in the plan because the tools that need it are.

    Nothing subscribes to a toolchain. A machine gets Go because it declared
    `go_tools` and Rust because it declared `cargo_packages`, which is why the
    manifest booleans that used to gate them (`go:`, `rust:`, `nvm:`, `tenv:`) were
    removed — they said nothing the tool lists did not, and a machine could set one
    without declaring a single tool for it.

    That derivation is what the two-pass signature exists for, so this is the
    provider it was written for rather than a special case beside it: `planned`
    carries what the tool providers resolved, and reading it is the whole of what
    `resources/toolchains.py` kept as a table of its own — the fifth keying of the
    provider concept, and the one the A3 collapse did not reach.
    """

    runtime: str = ''
    """What the row is called: `rust`, where the provider is `rust-toolchain`.

    The provider name has to be unique across the whole registry — `packages`
    already has a `go` and a `uv` — while this is what a person reads, and
    `dotfiles toolchains plan` has printed these four words since it existed. It
    is also the `runtimes` key, so a floor declared for it starts being honoured
    without anything here changing.
    """

    executable: str = ''
    """The binary that answers for it, which is not always its name: Rust is
    measured through `rustc`."""

    needed_by: str = ''
    """The catalog section whose presence requires it. Empty means ungated."""

    ownable: bool = False
    """A runtime belongs to nobody, so `--owner` skips these whole.

    Filtering instead would drop every one of them for answering `owner is None`,
    which is the wrong reason — and it reproduces what the phase registry already
    did, where a toolchain phase declared no providers and so never survived the
    intersection.
    """

    def plan(self, machine: machines.Machine, declaration: catalogs.Catalog, planned: tuple[DesiredItem, ...]) -> tuple[DesiredItem, ...]:
        if self.needed_by and not any(item.section == self.needed_by for item in planned):
            return ()
        return (
            DesiredItem(
                section='runtimes',
                provider=self.name,
                resource=self.resource,
                stage=self.stage,
                name=self.runtime,
                executable=self.executable,
                evidence_path='',
                precondition=resolve.Precondition.NONE,
                entry=declared_runtime(declaration, self.runtime),
                reason=Reason('runtimes', f'section:{self.needed_by}' if self.needed_by else 'every machine'),
            ),
        )

    def install(self, session: Session, change: Change, item: DesiredItem, privilege: Privilege) -> Outcome:
        result = self.converge(session, privilege)
        return Outcome(change, OutcomeStatus.DONE if result.ok else OutcomeStatus.FAILED, result.detail)

    def converge(self, session: Session, privilege: Privilege) -> providers.Result:
        """Put this runtime on the machine, by whatever means it has.

        Abstract, unlike the base `Provider.install`, because there is no honest
        default: a runtime with no mechanism is not a faithful description of
        anything, it is a missing subclass.
        """
        raise NotImplementedError


@dc.dataclass(frozen=True, slots=True)
class UvToolchain(ToolchainProvider):
    """astral's install script, then the default interpreter it manages."""

    def converge(self, session: Session, privilege: Privilege) -> providers.Result:
        return toolchain.install_uv(offline=session.offline)


@dc.dataclass(frozen=True, slots=True)
class RustToolchain(ToolchainProvider):
    """rustup, which brings `rustc` and `cargo` together."""

    def converge(self, session: Session, privilege: Privilege) -> providers.Result:
        return toolchain.install_rust(offline=session.offline)


@dc.dataclass(frozen=True, slots=True)
class GoToolchain(ToolchainProvider):
    """A tarball unpacked over `/usr/local/go`, which is why this one needs root.

    The only runtime that does. The other three install under `$HOME`, and Go
    could too — but `.zshenv`, `install/tool-path.sh` and `apply.TOOL_PATH_DIRS`
    all name `/usr/local/go/bin`, so moving it is a change to every one of them
    and to every machine already built.
    """

    def converge(self, session: Session, privilege: Privilege) -> providers.Result:
        return toolchain.install_go(coordinates.target_for(session.machine.coordinates), privilege, offline=session.offline)

    def needs_root(self, item: DesiredItem) -> bool:
        return True


@dc.dataclass(frozen=True, slots=True)
class NodeToolchain(ToolchainProvider):
    """fnm's default alias, which is what a bare `node` resolves to."""

    def converge(self, session: Session, privilege: Privilege) -> providers.Result:
        return toolchain.install_node(session.home, offline=session.offline)


def declared_runtime(declaration: catalogs.Catalog, name: str) -> catalogs.Runtime | None:
    """The `runtimes` row carrying a toolchain's version floor, or None.

    Tolerant rather than `Catalog.find`, which raises. Two of the four toolchains
    have no row at all, and the two that do declare a floor optionally — rust names
    an install method and no version, so any rustc satisfies it. An absent row
    means "no floor", which is a legitimate state and not a broken plan.
    """
    for entry in declaration.section('runtimes'):
        if entry.name == name and isinstance(entry, catalogs.Runtime):
            return entry
    return None


@dc.dataclass(frozen=True, slots=True)
class SystemConfigProvider(Provider):
    """A `system.yml` section, resolved against what the first pass planned.

    These cannot be `CatalogProvider`s: that class asks the manifest what it
    subscribes to, and no manifest subscribes to a group membership. What decides
    one of these rows instead is a coordinate, a feature, or the result of the
    first pass.
    """

    ownable: bool = False

    def plan(self, machine: machines.Machine, declaration: catalogs.Catalog, planned: tuple[DesiredItem, ...]) -> tuple[DesiredItem, ...]:
        installed = {item.name for item in planned if item.section == 'system_packages'}
        return tuple(
            DesiredItem(
                section=self.section,
                provider=self.name,
                resource=self.resource,
                stage=self.stage,
                name=entry.name,
                executable='',
                evidence_path='',
                precondition=resolve.Precondition.NONE,
                entry=entry,
                reason=Reason(self.section, decided_by(entry)),
            )
            for entry in declaration.section(self.section)
            if isinstance(entry, catalogs.SystemConfig)
            and resolve.available(entry, machine.coordinates)
            and resolve.configures(entry, machine, installed)
        )

    def needs_root(self, item: DesiredItem) -> bool:
        return isinstance(item.entry, catalogs.SystemConfig) and item.entry.needs_root

    def states(self, items: Sequence[DesiredItem]) -> dict[str, sysconfig.State]:
        """Every row's state, batching what this provider knows how to batch.

        A dict per provider rather than one function branching on the entry class,
        which is what `system.py` did — the batch hook below is the whole reason
        that dispatch existed, and it belongs to the one provider that needs it.
        """
        stores = self.stores([entry for item in items if isinstance(entry := item.entry, catalogs.SystemConfig)])
        return {item.address: self.state(_configuration(item.entry), stores) for item in items}

    def stores(self, entries: Sequence[catalogs.SystemConfig]) -> dict[macdefaults.Domain, dict[str, object] | None]:
        """A bulk read this provider can do once for all its rows. Usually none."""
        return {}

    def state(self, entry: catalogs.SystemConfig, stores: dict[macdefaults.Domain, dict[str, object] | None]) -> sysconfig.State:
        return sysconfig.observe(entry)

    def repair(self, entry: catalogs.SystemConfig, privilege: Privilege) -> sysconfig.Result:
        return sysconfig.apply(entry, privilege)

    def install(self, session: Session, change: Change, item: DesiredItem, privilege: Privilege) -> Outcome:
        entry = _configuration(item.entry)

        # Re-read rather than trusting the diff: `observe` ran before the report
        # was printed, and an earlier change in this same batch — the docker
        # package, zsh itself — may have made this one unnecessary or possible.
        if self.state(entry, self.stores([entry])).verdict is Verdict.MATCHED:
            return Outcome(change, OutcomeStatus.SKIPPED, 'already configured')

        result = self.repair(entry, privilege)
        return Outcome(change, OutcomeStatus.DONE if result.ok else OutcomeStatus.FAILED, result.detail)


@dc.dataclass(frozen=True, slots=True)
class MacDefaultProvider(SystemConfigProvider):
    """macOS preferences, which are the one section with a batched read.

    Seventy-four keys live in about fifteen domains, and `defaults export <domain>`
    answers a whole domain at once — so this is the provider `stores` exists for.
    """

    def stores(self, entries: Sequence[catalogs.SystemConfig]) -> dict[macdefaults.Domain, dict[str, object] | None]:
        return macdefaults.domains([entry for entry in entries if isinstance(entry, catalogs.MacosDefault)])

    def state(self, entry: catalogs.SystemConfig, stores: dict[macdefaults.Domain, dict[str, object] | None]) -> sysconfig.State:
        assert isinstance(entry, catalogs.MacosDefault)
        return macdefaults.observe_default(entry, stores)

    def repair(self, entry: catalogs.SystemConfig, privilege: Privilege) -> sysconfig.Result:
        assert isinstance(entry, catalogs.MacosDefault)
        return macdefaults.apply_default(entry)


@dc.dataclass(frozen=True, slots=True)
class StepProvider(SystemConfigProvider):
    """The rows with no shared mechanism, each a pair of functions in `steps.py`."""

    def state(self, entry: catalogs.SystemConfig, stores: dict[macdefaults.Domain, dict[str, object] | None]) -> sysconfig.State:
        return steps.observe(entry.name)

    def repair(self, entry: catalogs.SystemConfig, privilege: Privilege) -> sysconfig.Result:
        return steps.apply(entry.name, privilege)


def _configuration(entry: catalogs.Entry | None) -> catalogs.SystemConfig:
    assert isinstance(entry, catalogs.SystemConfig)
    return entry


PROVIDERS: tuple[Provider, ...] = (
    SystemPackageProvider('system', 'system', Stage.SYSTEM, 'system_packages'),
    RegistryProvider('cask', 'system', Stage.SYSTEM, 'macos_casks'),
    AppStoreProvider('mas', 'system', Stage.SYSTEM, 'mas_apps'),
    RegistryProvider('flatpak', 'system', Stage.SYSTEM, 'flatpak_apps'),
    ReleaseProvider('ghrelease', 'packages', Stage.TOOLS, 'github_releases'),
    CustomProvider('custom', 'packages', Stage.TOOLS, 'custom_installers'),
    CargoProvider('cargo', 'packages', Stage.TOOLS, 'cargo_packages'),
    GoToolProvider('go', 'packages', Stage.TOOLS, 'go_tools'),
    NpmProvider('npm', 'packages', Stage.NODE_TOOLS, 'npm_globals'),
    UvToolProvider('uv', 'packages', Stage.PYTHON_TOOLS, 'uv_tools'),
    UvToolProvider('uv-git', 'packages', Stage.PYTHON_TOOLS, 'git_uv_tools'),
    CloneProvider('shell-plugin', 'plugins', Stage.SHELL_PLUGINS, 'shell_plugins'),
    CloneProvider('tpm', 'plugins', Stage.TMUX_PLUGINS, 'tmux_plugins'),
    CloneProvider('yazi-plugin', 'plugins', Stage.YAZI_PLUGINS, 'yazi_plugins'),
    UvToolchain('uv-toolchain', 'toolchains', Stage.TOOLCHAIN, runtime='uv', executable='uv'),
    GoToolchain('go-toolchain', 'toolchains', Stage.TOOLCHAIN, runtime='go', executable='go', needed_by='go_tools'),
    RustToolchain('rust-toolchain', 'toolchains', Stage.TOOLCHAIN, runtime='rust', executable='rustc', needed_by='cargo_packages'),
    NodeToolchain('node-toolchain', 'toolchains', Stage.NODE, runtime='node', executable='node', needed_by='npm_globals'),
    SystemConfigProvider('group', 'system', Stage.SYSTEM_CONFIG, 'group_memberships'),
    SystemConfigProvider('systemd', 'system', Stage.SYSTEM_CONFIG, 'systemd_units'),
    SystemConfigProvider('file', 'system', Stage.SYSTEM_CONFIG, 'managed_files'),
    SystemConfigProvider('login-shell', 'system', Stage.SYSTEM_CONFIG, 'login_shell'),
    MacDefaultProvider('macos-default', 'system', Stage.SYSTEM_CONFIG, 'macos_defaults'),
    StepProvider('step', 'system', Stage.SYSTEM_CONFIG, 'steps'),
)
"""The registry, in planning order — which is the two passes.

Every provider that reads what an earlier one resolved sits after it: the
toolchains after the tool sections that pull them in, and every `system.yml`
provider after every `packages.yml` one. Execution order is `Stage`, not this: the
plan is sorted before it leaves the resolver, so the Go runtime installs at
TOOLCHAIN despite being planned after the tools that need it, and a provider put
in the wrong place here changes nothing about when it runs.
"""

UNPROVIDED: dict[str, str] = {
    'runtimes': 'read by the toolchain providers for their floors; a machine gets a runtime from its tool lists, never by subscribing',
    'zen_extensions': 'declared and installed by nothing; the browser profile is not managed from here yet',
}
"""Sections deliberately absent from the registry, each with the reason.

A section in neither is a section silently installing nothing, which is the
failure `runtimes` sat in for months — declared, validated by nothing, resolved by
nothing. `tests/resolver/test_resolve.py` asserts the two cover every section
between them, so a new section has to answer this question to be committed.
"""

BY_NAME: dict[str, Provider] = {provider.name: provider for provider in PROVIDERS}
BY_SECTION: dict[str, Provider] = {provider.section: provider for provider in PROVIDERS if provider.section}
"""Only the providers a manifest can subscribe to.

A toolchain plans from no section, and indexing four of them under '' would make
`--source runtimes` resolve to whichever was written last.
"""


def named(name: str) -> Provider | None:
    return BY_NAME.get(name)


def for_section(section: str) -> Provider | None:
    return BY_SECTION.get(section)


def for_resource(resource: str) -> tuple[Provider, ...]:
    return tuple(provider for provider in PROVIDERS if provider.resource == resource)


def evidence_for(item: DesiredItem, installed: ev.Inventory) -> ev.Evidence:
    """One item's evidence, through the provider that planned it.

    An item whose provider has been retired out from under it is `UNKNOWN` rather
    than an exception: a run record from another machine can name a provider this
    checkout no longer has, and reading it must not raise.
    """
    provider = named(item.provider)
    if provider is None:
        return ev.Evidence(Verdict.UNKNOWN, f'nothing in this checkout provides {item.provider}')
    return provider.evidence(item, installed)


def needs_root(item: DesiredItem) -> bool:
    provider = named(item.provider)
    return provider is not None and provider.needs_root(item)


def install(session: Session, change: Change, privilege: Privilege) -> Outcome:
    """Repair one change through whichever provider planned it.

    The three resources that group providers share this rather than each keeping a
    table of which of their providers it can repair. `packages.PERFORMED` was one
    such table and `system.py`'s entry-class dispatch was another, and between them
    they decided the same question two different ways.
    """
    item = change.desired
    if item is None:
        return Outcome(change, OutcomeStatus.REFUSED, 'nothing declares this any more')
    provider = named(item.provider)
    if provider is None:
        return Outcome(change, OutcomeStatus.REFUSED, f'nothing in this checkout provides {item.provider}')
    return provider.install(session, change, item, privilege)


def executable_of(entry: catalogs.Entry) -> str:
    """The binary to look for, or '' where the entry installs none.

    A sourced bash library and a Python package pulled in for another tool's
    benefit both put nothing on PATH, and would read as permanently missing.
    """
    if isinstance(entry, catalogs.UvTool) and entry.library_only:
        return ''
    if isinstance(entry, catalogs.CustomInstaller) and entry.installed_path and not entry.command:
        return ''
    return entry.executable


def precondition_of(entry: catalogs.Entry) -> resolve.Precondition:
    needs_auth = getattr(entry, 'requires_github_auth', False)
    return resolve.Precondition.GITHUB_AUTH if needs_auth else resolve.Precondition.NONE


def selector_of(section: str, subscription: machines.Subscription) -> str:
    if subscription.tier:
        return f'tier:{subscription.tier}'
    if subscription.declared:
        return f'manifest:{section}'
    return f'catalog:{section}'


def decided_by(entry: catalogs.SystemConfig) -> str:
    """What put this row in the plan, for `machines show` to print."""
    narrowings = {'package': entry.requires_package, **entry.narrowing, 'feature': entry.feature}
    named_by = ', '.join(f'{key}:{value}' for key, value in narrowings.items() if value)
    return named_by or 'every machine'
