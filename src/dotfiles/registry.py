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

**Only `plan` is handed the Catalog.** `evidence` takes a resolved `DesiredItem`
and cannot reach back for a fact the item does not carry, which turns
`resolve.py`'s "resolution finishes here" from a prose invariant into something
the signatures enforce.
"""

from __future__ import annotations

import dataclasses as dc

from dotfiles import catalog as catalogs
from dotfiles import evidence as ev
from dotfiles import machine as machines
from dotfiles import resolve
from dotfiles.resolve import DesiredItem
from dotfiles.resolve import Reason
from dotfiles.resolve import Stage
from dotfiles.resources import Verdict


@dc.dataclass(frozen=True, slots=True)
class Provider:
    """One way of installing things, and everything that is true of all of them.

    The base is not abstract on purpose. A provider whose mechanism this package
    does not drive yet — the four that still install through a phase — is a
    faithful description of what the machine has: it plans, its items are
    observable, and only the write is elsewhere. Forcing it to declare an
    `install` it does not have would be a stub, and a stub is what `PERFORMED`
    was avoiding by being a partial map in the first place.
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
    """The declaration section it plans from."""

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


PROVIDERS: tuple[Provider, ...] = (
    SystemPackageProvider('system', 'system', Stage.SYSTEM, 'system_packages'),
    RegistryProvider('cask', 'system', Stage.SYSTEM, 'macos_casks'),
    AppStoreProvider('mas', 'system', Stage.SYSTEM, 'mas_apps'),
    RegistryProvider('flatpak', 'system', Stage.SYSTEM, 'flatpak_apps'),
    CatalogProvider('ghrelease', 'packages', Stage.TOOLS, 'github_releases'),
    CatalogProvider('custom', 'packages', Stage.TOOLS, 'custom_installers'),
    CatalogProvider('cargo', 'packages', Stage.TOOLS, 'cargo_packages'),
    CatalogProvider('go', 'packages', Stage.TOOLS, 'go_tools'),
    CatalogProvider('npm', 'packages', Stage.NODE_TOOLS, 'npm_globals'),
    UvToolProvider('uv', 'packages', Stage.PYTHON_TOOLS, 'uv_tools'),
    UvToolProvider('uv-git', 'packages', Stage.PYTHON_TOOLS, 'git_uv_tools'),
    CloneProvider('shell-plugin', 'plugins', Stage.SHELL_PLUGINS, 'shell_plugins'),
    CloneProvider('tpm', 'plugins', Stage.TMUX_PLUGINS, 'tmux_plugins'),
    CloneProvider('yazi-plugin', 'plugins', Stage.YAZI_PLUGINS, 'yazi_plugins'),
    SystemConfigProvider('group', 'system', Stage.SYSTEM_CONFIG, 'group_memberships'),
    SystemConfigProvider('systemd', 'system', Stage.SYSTEM_CONFIG, 'systemd_units'),
    SystemConfigProvider('file', 'system', Stage.SYSTEM_CONFIG, 'managed_files'),
    SystemConfigProvider('login-shell', 'system', Stage.SYSTEM_CONFIG, 'login_shell'),
    SystemConfigProvider('macos-default', 'system', Stage.SYSTEM_CONFIG, 'macos_defaults'),
    SystemConfigProvider('step', 'system', Stage.SYSTEM_CONFIG, 'steps'),
)
"""The registry, in planning order — which is the two passes.

Every `system.yml` provider sits after every `packages.yml` one because each is
handed what the earlier providers resolved and some of them read it. Execution
order is `Stage`, not this: the plan is sorted before it leaves the resolver, so
a provider added in the wrong place here changes nothing about when it runs.
"""

UNPROVIDED: dict[str, str] = {
    'runtimes': 'derived by the toolchain resource from the tool sections that need one, never subscribed to directly',
    'zen_extensions': 'declared and installed by nothing; the browser profile is not managed from here yet',
}
"""Sections deliberately absent from the registry, each with the reason.

A section in neither is a section silently installing nothing, which is the
failure `runtimes` sat in for months — declared, validated by nothing, resolved by
nothing. `tests/resolver/test_resolve.py` asserts the two cover every section
between them, so a new section has to answer this question to be committed.
"""

BY_NAME: dict[str, Provider] = {provider.name: provider for provider in PROVIDERS}
BY_SECTION: dict[str, Provider] = {provider.section: provider for provider in PROVIDERS}


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
