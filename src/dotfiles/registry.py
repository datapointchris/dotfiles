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
import shutil
from collections.abc import Callable
from collections.abc import Sequence
from pathlib import Path

from dotfiles import catalog as catalogs
from dotfiles import coordinates
from dotfiles import evidence as ev
from dotfiles import machine as machines
from dotfiles import providers
from dotfiles import resolve
from dotfiles.privilege import Privilege
from dotfiles.providers import Result
from dotfiles.providers import bootstrap
from dotfiles.providers import cargo
from dotfiles.providers import clone
from dotfiles.providers import custom
from dotfiles.providers import ghrelease
from dotfiles.providers import gotool
from dotfiles.providers import macdefaults
from dotfiles.providers import npm
from dotfiles.providers import pluginsync
from dotfiles.providers import steps
from dotfiles.providers import sysconfig
from dotfiles.providers import syspkg
from dotfiles.providers import toolchain
from dotfiles.providers import uvtool
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

    `plan` and `measure` have defaults because a provider can legitimately want
    neither. `install` has none: a provider that plans items and cannot repair
    them is a mechanism the walk would silently decline to run, so it has to be a
    loud failure rather than an inherited no-op.
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

        Raising rather than returning a refusal: a provider reaching this has
        planned items nothing can act on, so the run is misconfigured rather than
        blocked, and `engine._act` turns the exception into a `Refusal` naming it.
        """
        raise NotImplementedError(f'{self.name} plans items and cannot install them')

    def install_all(self, session: Session, changes: Sequence[Change], privilege: Privilege) -> list[Outcome]:
        """Repair several of this provider's items, one Outcome each in order.

        One at a time by default, which is what every provider but the package
        managers wants: a release download, a clone and a `defaults write` cost
        the same alone as in company.
        """
        return [install_one(self, session, change, privilege) for change in changes]


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

    The distinction that earns the base class: these two fetch an asset this
    package names, so they own the download, the checksum and the unpack. A
    manager-backed provider hands all three to `go install` or `npm i -g`.
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
    """A binary published as a GitHub release asset, and the files that ship beside it."""

    def evidence(self, item: DesiredItem, installed: ev.Inventory) -> ev.Evidence:
        """The binary, and then whatever the release does not publish.

        A companion is a separate file under `~/.local/bin`, so a present and
        current binary says nothing about whether it is still there — and a
        machine missing one is not converged, however current the binary is.

        Reported as `MISSING` because that is what it is and what makes it
        actionable — the detail carries which file, so a row naming the tool never
        reads as the tool itself being absent.
        """
        # Named explicitly, not `super()`: `@dc.dataclass(slots=True)` rebuilds the
        # class, so the `__class__` cell a zero-argument `super()` closes over
        # points at the class that was replaced and it raises at the first call.
        found = Provider.evidence(self, item, installed)
        if found.verdict is not Verdict.MATCHED:
            return found
        absent = ghrelease.missing_companions(item.name)
        if not absent:
            return found
        return ev.Evidence(Verdict.MISSING, f'{item.executable} is installed, but {", ".join(absent)} is not beside it')

    def fetch(self, session: Session, item: DesiredItem) -> providers.Result:
        entry = item.entry
        if not isinstance(entry, catalogs.GithubRelease):
            return providers.Result(False, f'{item.name} is not a github_releases entry')
        return ghrelease.install(entry, coordinates.target_for(session.machine.coordinates), offline=session.offline)


@dc.dataclass(frozen=True, slots=True)
class CustomProvider(VendoredProvider):
    """A vendor that ships its own installer, and whatever else that installer places."""

    def evidence(self, item: DesiredItem, installed: ev.Inventory) -> ev.Evidence:
        """The binary, and then the pieces beside it that are not binaries.

        `bats` is the case: it is on PATH and current while `~/.local/lib/bats-assert`
        is gone, which shows up as a failing `load` line in a suite rather than in
        any verdict. Same shape as `ReleaseProvider` above, and named explicitly
        rather than through `super()` for the same slotted-dataclass reason.
        """
        found = Provider.evidence(self, item, installed)
        if found.verdict is not Verdict.MATCHED or not isinstance(item.entry, catalogs.CustomInstaller):
            return found
        absent = custom.missing_parts(item.entry)
        if not absent:
            return found
        return ev.Evidence(Verdict.MISSING, f'{item.name} is installed, but {", ".join(absent)} is not')

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

    def install(self, session: Session, change: Change, item: DesiredItem, privilege: Privilege) -> Outcome:
        return self.install_all(session, [change], privilege)[0]

    def install_all(self, session: Session, changes: Sequence[Change], privilege: Privilege) -> list[Outcome]:
        """One transaction per manager, and one bootstrap and refresh before each.

        Grouped by manager rather than done in the order given, because the order
        given is the plan's and the transaction is the manager's. A machine has one
        of apt/pacman/brew, so this is usually one group — plus the AUR's, which is
        genuinely a second manager and a second transaction.
        """
        outcomes: dict[str, Outcome] = {}
        for manager, wanted in _by_manager(session, changes).items():
            ready = _bootstrap(manager, session, privilege)
            if not ready.ok:
                outcomes |= {change.item: Outcome(change, OutcomeStatus.REFUSED, ready.detail) for change, _ in wanted}
                continue
            outcomes |= _transact(manager, wanted, privilege)
        unreachable = 'no package manager on this machine installs it'
        return [outcomes.get(change.item, Outcome(change, OutcomeStatus.REFUSED, unreachable)) for change in changes]


@dc.dataclass(frozen=True, slots=True)
class UvToolProvider(CatalogProvider):
    """uv installs a tool per directory, and some are libraries with no script."""

    def measure(self, item: DesiredItem, installed: ev.Inventory) -> ev.Evidence:
        return ev.by_uv_tool(item)

    def install(self, session: Session, change: Change, item: DesiredItem, privilege: Privilege) -> Outcome:
        entry = item.entry
        if not isinstance(entry, catalogs.UvTool):
            return Outcome(change, OutcomeStatus.REFUSED, f'{item.name} is not a uv_tools entry')
        result = uvtool.install(entry, offline=session.offline)
        return Outcome(change, OutcomeStatus.DONE if result.ok else OutcomeStatus.FAILED, result.detail)


@dc.dataclass(frozen=True, slots=True)
class GitUvToolProvider(UvToolProvider):
    """The same mechanism, pointed at a git repo and pinned to its newest release.

    A subclass rather than a flag, because only the requirement differs and the
    evidence does not: uv puts a git-installed tool in the same per-tool directory
    as a PyPI one.
    """

    def install(self, session: Session, change: Change, item: DesiredItem, privilege: Privilege) -> Outcome:
        entry = item.entry
        if not isinstance(entry, catalogs.GitUvTool):
            return Outcome(change, OutcomeStatus.REFUSED, f'{item.name} is not a git_uv_tools entry')
        result = uvtool.install_git(entry, offline=session.offline)
        return Outcome(change, OutcomeStatus.DONE if result.ok else OutcomeStatus.FAILED, result.detail)


@dc.dataclass(frozen=True, slots=True)
class CaskProvider(RegistryProvider):
    """A GUI application Homebrew installs, which is one manager away from a formula.

    Its own provider rather than a `SystemPackage` with a fifth manager column,
    because a cask is not an alternative spelling of anything: `macos_casks` is a
    separate section a manifest subscribes to separately, and an entry there names
    an app rather than a package that happens to be graphical.
    """

    def install(self, session: Session, change: Change, item: DesiredItem, privilege: Privilege) -> Outcome:
        return self.install_all(session, [change], privilege)[0]

    def install_all(self, session: Session, changes: Sequence[Change], privilege: Privilege) -> list[Outcome]:
        return _through('cask', session, changes, privilege, lambda item: item.name)


@dc.dataclass(frozen=True, slots=True)
class AppStoreProvider(CatalogProvider):
    """An App Store app, judged by its bundle. Its CLI is a second question.

    The bundle rather than a `mas list` inventory, because the two answer
    different questions: an app installed from the store on another machine and
    restored by Migration Assistant is present and is not in `mas list`. Which is
    also why `mas` has no entry in `evidence.INSTALLER_QUERIES`.
    """

    def measure(self, item: DesiredItem, installed: ev.Inventory) -> ev.Evidence:
        return ev.by_app_bundle(item)

    def install(self, session: Session, change: Change, item: DesiredItem, privilege: Privilege) -> Outcome:
        return self.install_all(session, [change], privilege)[0]

    def install_all(self, session: Session, changes: Sequence[Change], privilege: Privilege) -> list[Outcome]:
        """`mas install`, which needs an App Store this process cannot sign into.

        mas 7 dropped `account` and offers no way to ask whether anyone is signed
        in, so there is nothing to gate on — the install is attempted and a
        sign-in failure is reported as the failure it is. `mas-apps.sh` said the
        same thing in a comment and then printed advice on every failure; the
        advice is here, once, on the outcome that earns it.
        """
        return _through('mas', session, changes, privilege, _app_id)


def _app_id(item: DesiredItem) -> str:
    """An App Store app is addressed by number, and only by number."""
    entry = item.entry
    return str(entry.id) if isinstance(entry, catalogs.MasApp) else ''


@dc.dataclass(frozen=True, slots=True)
class FlatpakProvider(RegistryProvider):
    """A Flathub app, addressed by its reverse-DNS id rather than its name."""

    def install(self, session: Session, change: Change, item: DesiredItem, privilege: Privilege) -> Outcome:
        return self.install_all(session, [change], privilege)[0]

    def install_all(self, session: Session, changes: Sequence[Change], privilege: Privilege) -> list[Outcome]:
        return _through('flatpak', session, changes, privilege, _flatpak_id)


def _flatpak_id(item: DesiredItem) -> str:
    entry = item.entry
    return entry.flatpak_id if isinstance(entry, catalogs.FlatpakApp) else ''


@dc.dataclass(frozen=True, slots=True)
class CloneProvider(CatalogProvider):
    """A plugin whose evidence is a checkout under `$HOME`.

    It deliberately does not override `measure`. Where the checkout belongs is a
    path relative to a home directory, and `evidence` is handed neither — so the
    plugins resource observes these itself rather than this class answering with
    a `which` that would be wrong for every one of them. `PluginSyncProvider`
    beside it takes the session-shaped route instead, because two managers answer
    that question two different ways; here one rule covers all three clones and
    the resource applying it is not yet worth a second protocol.
    """

    def install(self, session: Session, change: Change, item: DesiredItem, privilege: Privilege) -> Outcome:
        """Clone what is missing, pull what is behind.

        Two repairs behind one verb because the verdict already separates them,
        and the alternative was `update.sh` pulling every plugin on every run to
        find out whether any of them had moved.
        """
        landed = clone.destination(item, session.home)
        if change.verdict is Verdict.STALE:
            result = clone.pull(item, session.home)
        elif landed.is_dir():
            return Outcome(change, OutcomeStatus.SKIPPED, f'{landed} appeared since the check')
        else:
            result = clone.clone(item, session.home)
        return Outcome(change, OutcomeStatus.DONE if result.ok else OutcomeStatus.FAILED, result.detail)


@dc.dataclass(frozen=True, slots=True)
class PluginSyncProvider(Provider):
    """An external plugin manager, handed control of a list this repo cannot read.

    One synthetic row rather than one per plugin, because there is nothing to plan
    per plugin: TPM's list is `@plugin` lines in `tmux.conf` and lazy's is lua, so
    neither has a `packages.yml` section for the resolver to walk. What the row
    stands for is the *invocation* — the thing `tmux-plugins.sh` and
    `nvim-plugins.sh` each were, minus the phase that ran them.

    The row is measured rather than performed unconditionally, which the scripts
    could not manage: each ran its manager on every apply and reported whatever it
    printed. `providers/pluginsync.py` says what each can honestly be asked.
    """

    manager: str = ''
    """What the row is called, which is the manager rather than the program: `tpm`
    and `lazy` are what own the lists, and the addresses read `tmux-sync/tpm` and
    `nvim-sync/lazy`."""

    needs: str = ''
    """A catalog section whose items must be planned first. Empty means ungated by
    one.

    The tmux sync is the case: TPM installs the plugins, and TPM is the
    `tmux_plugins` clone. So the manifest gate on the clone gates the sync too,
    rather than the sync reading the same boolean a second time.
    """

    feature: str = ''
    """A manifest feature that gates it, for the sync with no section behind it.

    `nvim_plugins` is in `machine.FEATURES` precisely because lazy bootstraps
    itself and there is nothing in `packages.yml` to subscribe to.
    """

    ownable: bool = False
    """A plugin manager's list belongs to nobody here, so `--owner` skips these
    whole rather than dropping them for answering `owner is None`."""

    def plan(self, machine: machines.Machine, declaration: catalogs.Catalog, planned: tuple[DesiredItem, ...]) -> tuple[DesiredItem, ...]:
        if self.needs and not any(item.section == self.needs for item in planned):
            return ()
        if self.feature and not machine.wants(self.feature):
            return ()
        return (
            DesiredItem(
                section='',
                provider=self.name,
                resource=self.resource,
                stage=self.stage,
                name=self.manager,
                executable='',
                evidence_path='',
                precondition=resolve.Precondition.NONE,
                entry=None,
                reason=Reason('plugins', f'section:{self.needs}' if self.needs else f'feature:{self.feature}'),
            ),
        )

    def pending(self, session: Session) -> str:
        """What still needs this manager run, or '' where nothing does.

        Session-taking, unlike `evidence`, and this is the class that forced it:
        what a plugin manager installed is a path under a home directory, and
        `evidence` is handed neither a home nor a plan. `CloneProvider` names the
        same gap and leaves the answer to the plugins resource; these two cannot,
        because they answer it two different ways and a resource branching on the
        provider name would be the table this registry exists to delete.
        """
        return ''


@dc.dataclass(frozen=True, slots=True)
class TmuxSyncProvider(PluginSyncProvider):
    """TPM, told where to install and given a server that is not the user's."""

    def pending(self, session: Session) -> str:
        """What TPM has left to do, counting "cannot be asked yet" as work.

        A precondition TPM is missing is supplied by an earlier stage of this same
        run, so it makes the row a change rather than an unanswerable question —
        `pluginsync.blocked` carries the reasoning and `install` re-reads it live.
        """
        directory = tmux_plugins_dir(session)
        if directory is None:
            return ''
        if reason := pluginsync.blocked(session.home, directory):
            return reason
        declared = pluginsync.declared(session.home)
        missing = pluginsync.uninstalled(declared, directory)
        if not missing:
            return ''
        return f'{len(missing)} of the {len(declared)} plugins tmux.conf declares are not installed: {pluginsync.listed(missing)}'

    def install(self, session: Session, change: Change, item: DesiredItem, privilege: Privilege) -> Outcome:
        directory = tmux_plugins_dir(session)
        if directory is None:
            return Outcome(change, OutcomeStatus.REFUSED, 'nothing declares TPM, so there is nowhere to install its plugins')
        if reason := pluginsync.blocked(session.home, directory):
            return Outcome(change, OutcomeStatus.REFUSED, f'{reason}, and the stage that supplies it has not')
        result = pluginsync.sync_tmux(session.home, directory)
        return Outcome(change, OutcomeStatus.DONE if result.ok else OutcomeStatus.FAILED, result.detail)


@dc.dataclass(frozen=True, slots=True)
class NvimSyncProvider(PluginSyncProvider):
    """lazy.nvim, run headless once so the first real `nvim` is not a clone storm."""

    def pending(self, session: Session) -> str:
        """Whether lazy has installed what it last recorded — not what the spec says.

        The spec is lua, and the only reader of it is nvim, whose startup installs
        what it finds missing. So a plugin *added* to the spec and not yet cloned
        is invisible here, deliberately: that case is lazy's, it repairs itself the
        next time the editor opens, and claiming to have checked it would be worse
        than the row saying what it actually looked at.

        What is left is the case the sync exists for, and it is the one this
        answers exactly — a machine where lazy has never run, whose first `nvim`
        would otherwise clone fifty repositories before drawing a window.
        """
        if pluginsync.recorded(session.home) is None:
            return 'lazy has not synced on this machine, so nothing is installed ahead of the first nvim'
        gone = pluginsync.unsynced(session.home)
        return f'{len(gone)} plugins lazy recorded installing are not on disk: {pluginsync.listed(gone)}' if gone else ''

    def install(self, session: Session, change: Change, item: DesiredItem, privilege: Privilege) -> Outcome:
        """Refused rather than failed where nvim is absent, because it is a package
        an earlier stage of this same run installs."""
        if not shutil.which('nvim'):
            return Outcome(change, OutcomeStatus.REFUSED, 'neovim is not installed, and the stage that installs it has not')
        result = pluginsync.sync_nvim()
        return Outcome(change, OutcomeStatus.DONE if result.ok else OutcomeStatus.FAILED, result.detail)


def tmux_plugins_dir(session: Session) -> Path | None:
    """Where TPM's plugins belong, or None where nothing declares TPM.

    Derived from the clone rather than declared a second time. `tmux_plugins`
    names TPM's own `install_dir` because TPM has to be told the path and agree
    with it, and the directory its plugins share with it is that path's parent — so
    a constant here would be the same fact written twice, free to disagree with the
    one the clone provider actually used.

    From `session.plan` rather than the narrowed one a resource is handed: which
    rows exist is the selection's business, but where TPM installs is a fact about
    the machine, and `--skip plugins/tpm` must not change the answer.
    """
    planned = session.plan.for_provider('tpm')
    return clone.destination(planned[0], session.home).parent if planned else None


@dc.dataclass(frozen=True, slots=True)
class ManagerProvider(Provider):
    """Whether each package manager on this machine is behind, and the upgrade.

    One synthetic row per manager, subscribed to by nothing — the shape a
    toolchain has, and for the same reason: a machine has pacman because of what
    its manifest asked pacman for, not because it named pacman.

    This is what `update.sh`'s `update_system_packages` was, and it is here rather
    than in a second front door because the question is measurable. That script
    ran `pacman -Syu`, `brew upgrade`, `mas upgrade` and `flatpak update`
    unconditionally and reported whatever they printed; a row that reads the
    manager's outdated list first can say *what* is behind before it moves, and
    say nothing on a machine that is current.

    The whole manager rather than the declared packages, deliberately. Arch does
    not support partial upgrades at all, and everywhere else a declared package's
    dependencies are as much this repo's business as the package — `pacman -S
    <one>` leaves a machine in a combination nobody tests.
    """

    ownable: bool = False
    """A package manager belongs to nobody, so `--owner` skips these whole rather
    than dropping them for answering `owner is None`."""

    def plan(self, machine: machines.Machine, declaration: catalogs.Catalog, planned: tuple[DesiredItem, ...]) -> tuple[DesiredItem, ...]:
        """One row per manager this machine actually installs something through.

        Read off what the earlier providers resolved rather than off the
        coordinates, which is the two-pass signature doing its job: a Mac
        subscribing to no casks has nothing for `brew upgrade --cask` to move, and
        a machine with no flatpak apps should not be told its flatpak is behind.
        """
        return tuple(
            DesiredItem(
                section='',
                provider=self.name,
                resource=self.resource,
                stage=self.stage,
                name=manager,
                executable='',
                evidence_path='',
                precondition=resolve.Precondition.NONE,
                entry=None,
                reason=Reason('managers', f'installs {provider}'),
            )
            for manager, provider in _managers_in_use(machine, planned)
        )

    def evidence(self, item: DesiredItem, installed: ev.Inventory) -> ev.Evidence:
        """Behind, current, or unmeasured — never guessed.

        The networked managers report UNKNOWN rather than MATCHED when nothing
        asked them, because a `check` that says "current" having asked nobody is
        the measured-looking wrong answer this resource exists to stop.
        """
        return ev.by_currency(item, installed)

    def needs_root(self, item: DesiredItem) -> bool:
        return item.name in syspkg.ESCALATES

    def install(self, session: Session, change: Change, item: DesiredItem, privilege: Privilege) -> Outcome:
        ready = _bootstrap(item.name, session, privilege)
        if not ready.ok:
            return Outcome(change, OutcomeStatus.REFUSED, ready.detail)
        result = syspkg.upgrade(item.name, privilege)
        return Outcome(change, OutcomeStatus.DONE if result.ok else OutcomeStatus.FAILED, result.detail)


def _managers_in_use(machine: machines.Machine, planned: tuple[DesiredItem, ...]) -> tuple[tuple[str, str], ...]:
    """Which managers this machine's plan reaches, each with the provider that reached it.

    Keyed on the provider that planned an item rather than on the machine's
    installer family, which is a superset: `brew` brings `cask` and `mas` with it,
    and a Mac subscribing to no casks has nothing for `brew upgrade --cask` to
    move. `flatpak` is in no family at all — it is opt-in per machine rather than
    something a package manager carries — so it appears here only when flatpak
    apps were planned, which is exactly when its runtime exists.
    """
    reached = {item.provider for item in planned}
    found: dict[str, str] = {}
    if 'system' in reached:
        for manager in syspkg.PREFERENCE:
            if manager in machine.coordinates.installers:
                found[manager] = 'system'
    for provider in ('cask', 'mas', 'flatpak'):
        if provider in reached:
            found[provider] = provider
    return tuple(found.items())


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

    installed_at: str = ''
    """Where this runtime must live, for one that is installed to a fixed path.

    Empty for the three that go wherever their own installer puts them, and set
    for Go, which is unpacked over `/usr/local/go` — a path `.zshenv`,
    `toolchain.TOOL_PATH_DIRS` and the verification script all name independently.

    It exists because `which` answers a different question than the declaration
    asks. A container picked up Arch's `go` package transitively, `which go` found
    `/usr/sbin/go`, and the toolchain reported itself installed while
    `/usr/local/go` did not exist — so every Go tool built against a runtime this
    repo did not put there, and nothing said so until the verification script
    checked the *location*.
    """

    ownable: bool = False
    """A runtime belongs to nobody, so `--owner` skips these whole.

    Filtering instead would drop every one of them for answering `owner is None`,
    which is the wrong reason: the answer would be right and the question wrong,
    and a later entry gaining an owner would silently change what `--owner`
    covers.
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
                evidence_path=self.installed_at,
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
    could too — but `.zshenv` and `toolchain.TOOL_PATH_DIRS` both name
    `/usr/local/go/bin`, so moving it is a change to both and to every machine
    already built.
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

    def repair(self, entry: catalogs.SystemConfig, privilege: Privilege) -> Result:
        return sysconfig.apply(entry, privilege)

    def install(self, session: Session, change: Change, item: DesiredItem, privilege: Privilege) -> Outcome:
        entry = _configuration(item.entry)

        # Re-read rather than trusting the diff: `observe` ran before the report
        # was printed, and an earlier change in this same batch — the docker
        # package, zsh itself — may have made this one unnecessary or possible.
        if self.state(entry, self.stores([entry])).verdict is Verdict.MATCHED:
            return Outcome(change, OutcomeStatus.SKIPPED, 'already configured')

        result = self.repair(entry, privilege)
        if result.refused:
            return Outcome(change, OutcomeStatus.REFUSED, result.detail)
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

    def repair(self, entry: catalogs.SystemConfig, privilege: Privilege) -> Result:
        assert isinstance(entry, catalogs.MacosDefault)
        return macdefaults.apply_default(entry)


@dc.dataclass(frozen=True, slots=True)
class StepProvider(SystemConfigProvider):
    """The rows with no shared mechanism, each a pair of functions in `steps.py`."""

    def state(self, entry: catalogs.SystemConfig, stores: dict[macdefaults.Domain, dict[str, object] | None]) -> sysconfig.State:
        return steps.observe(entry.name)

    def repair(self, entry: catalogs.SystemConfig, privilege: Privilege) -> Result:
        return steps.apply(entry.name, privilege)


def _configuration(entry: catalogs.Entry | None) -> catalogs.SystemConfig:
    assert isinstance(entry, catalogs.SystemConfig)
    return entry


PROVIDERS: tuple[Provider, ...] = (
    SystemPackageProvider('system', 'system', Stage.SYSTEM, 'system_packages'),
    CaskProvider('cask', 'system', Stage.SYSTEM_APPS, 'macos_casks'),
    AppStoreProvider('mas', 'system', Stage.SYSTEM_APPS, 'mas_apps'),
    FlatpakProvider('flatpak', 'system', Stage.SYSTEM_APPS, 'flatpak_apps'),
    ManagerProvider('manager', 'system', Stage.SYSTEM_UPGRADE),
    ReleaseProvider('ghrelease', 'packages', Stage.TOOLS, 'github_releases'),
    CustomProvider('custom', 'packages', Stage.TOOLS, 'custom_installers'),
    CargoProvider('cargo', 'packages', Stage.TOOLS, 'cargo_packages'),
    GoToolProvider('go', 'packages', Stage.TOOLS, 'go_tools'),
    NpmProvider('npm', 'packages', Stage.NODE_TOOLS, 'npm_globals'),
    UvToolProvider('uv', 'packages', Stage.PYTHON_TOOLS, 'uv_tools'),
    GitUvToolProvider('uv-git', 'packages', Stage.PYTHON_TOOLS, 'git_uv_tools'),
    CloneProvider('shell-plugin', 'plugins', Stage.SHELL_PLUGINS, 'shell_plugins'),
    CloneProvider('tpm', 'plugins', Stage.TMUX_PLUGINS, 'tmux_plugins'),
    TmuxSyncProvider('tmux-sync', 'plugins', Stage.TMUX_PLUGIN_SYNC, manager='tpm', needs='tmux_plugins'),
    CloneProvider('yazi-plugin', 'plugins', Stage.YAZI_PLUGINS, 'yazi_plugins'),
    NvimSyncProvider('nvim-sync', 'plugins', Stage.NVIM_PLUGIN_SYNC, manager='lazy', feature='nvim_plugins'),
    UvToolchain('uv-toolchain', 'toolchains', Stage.TOOLCHAIN, runtime='uv', executable='uv'),
    GoToolchain(
        'go-toolchain',
        'toolchains',
        Stage.TOOLCHAIN,
        runtime='go',
        executable='go',
        needed_by='go_tools',
        installed_at='/usr/local/go/bin/go',
    ),
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


def serving(section: str) -> tuple[Provider, ...]:
    """Every provider a run narrowed to one section needs, not only the one that installs it.

    `needed_by` already declares that a toolchain is wanted *because* a section
    resolved, and `resolve` honours it — the plan for a machine with
    `cargo_packages` carries `rust-toolchain` too. A selection that dropped it
    honoured the declaration in the plan and ignored it in the run, so
    `packages apply --source cargo_packages` on a machine without rustup failed
    with `cargo binstall bat exited 127: cargo: No such file or directory` rather
    than installing what it needed.

    Derived from the registry rather than listed, so a section that grows a
    prerequisite gets it here the moment `needed_by` says so.
    """
    provider = BY_SECTION.get(section)
    if provider is None:
        return ()
    required = tuple(other for other in PROVIDERS if isinstance(other, ToolchainProvider) and other.needed_by == section)
    return (*required, provider)


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


def _by_manager(session: Session, changes: Sequence[Change]) -> dict[str, list[tuple[Change, str]]]:
    """Which manager installs each change, and under what name.

    A machine's `installers` is the family its package manager selects — pacman
    brings the AUR with it, brew brings casks and the App Store — so an entry
    declaring names under three managers is narrowed to the one or two this
    machine can actually use. `PREFERENCE` breaks the remaining tie, which is only
    ever pacman against the AUR.

    A change no manager on this machine can install is absent from the result and
    answered separately, rather than silently dropped.
    """
    usable = session.machine.coordinates.installers
    grouped: dict[str, list[tuple[Change, str]]] = {}
    for change in changes:
        names = ev.declared_names(change.desired) if change.desired else {}
        chosen = next((manager for manager in syspkg.PREFERENCE if manager in usable and manager in names), '')
        if chosen:
            grouped.setdefault(chosen, []).append((change, names[chosen][0]))
    return grouped


def _bootstrap(manager: str, session: Session, privilege: Privilege) -> Result:
    """Whatever this manager needs to exist before it can install anything.

    Routed here rather than dispatched inside `providers.bootstrap`, for the same
    reason every other route is: this module is where a provider is matched to the
    mechanism that serves it, and the mechanism modules stay ignorant of the
    session. Four of the seven managers need nothing, and saying so as a fallthrough
    keeps `apt` and `pacman` from paying for a table lookup they would never use.
    """
    if manager == 'brew':
        ready = bootstrap.homebrew()
        return ready if not ready.ok else bootstrap.taps(session.catalog.macos_taps)
    if manager == 'cask':
        return bootstrap.homebrew()
    if manager == 'aur':
        return bootstrap.aur()
    if manager == 'flatpak':
        return bootstrap.flathub(session.machine.coordinates.installers[0], privilege)
    return Result(True, '')


def _through(
    manager: str,
    session: Session,
    changes: Sequence[Change],
    privilege: Privilege,
    name_of: Callable[[DesiredItem], str],
) -> list[Outcome]:
    """One manager's whole group, bootstrapped once and installed in one call.

    The three single-manager providers share this rather than each repeating the
    bootstrap-then-transact shape, and `SystemPackageProvider` does not because its
    group is not single-manager: it chooses between the names an entry declares,
    which is the one thing this does not have to do.
    """
    wanted = [(change, name_of(change.desired)) for change in changes if change.desired and name_of(change.desired)]
    if not wanted:
        return [Outcome(change, OutcomeStatus.REFUSED, 'nothing declares this any more') for change in changes]

    ready = _bootstrap(manager, session, privilege)
    if not ready.ok:
        return [Outcome(change, OutcomeStatus.REFUSED, ready.detail) for change in changes]

    outcomes = _transact(manager, wanted, privilege)
    undeclared = 'nothing declares this any more'
    return [outcomes.get(change.item, Outcome(change, OutcomeStatus.REFUSED, undeclared)) for change in changes]


def _transact(manager: str, wanted: list[tuple[Change, str]], privilege: Privilege) -> dict[str, Outcome]:
    """One manager's whole batch, falling back to one call per package on failure.

    The fallback is what lets the report name the package that broke: `brew
    install a b c` exiting 1 says nothing about which of the three is at fault, and
    the machine still wants the other two. Paid only when something is already
    wrong.
    """
    refreshed = syspkg.refresh(manager, privilege)
    if not refreshed.ok:
        reason = f'{manager} could not be refreshed: {refreshed.detail}'
        return {change.item: Outcome(change, OutcomeStatus.FAILED, reason) for change, _ in wanted}

    together = syspkg.install(manager, [name for _, name in wanted], privilege)
    if together.ok:
        return {change.item: Outcome(change, OutcomeStatus.DONE, f'{manager}: {name}') for change, name in wanted}

    isolated: dict[str, Outcome] = {}
    for change, name in wanted:
        alone = syspkg.install(manager, [name], privilege)
        status = OutcomeStatus.DONE if alone.ok else OutcomeStatus.FAILED
        isolated[change.item] = Outcome(change, status, f'{manager}: {name}' if alone.ok else alone.detail)
    return isolated


def install_one(provider: Provider, session: Session, change: Change, privilege: Privilege) -> Outcome:
    """One change through its provider, or a refusal naming what is missing."""
    item = change.desired
    if item is None:
        return Outcome(change, OutcomeStatus.REFUSED, 'nothing declares this any more')
    return provider.install(session, change, item, privilege)


def install_all(session: Session, changes: Sequence[Change], privilege: Privilege) -> list[Outcome]:
    """A group of changes through the one provider that planned them.

    The engine groups by provider before it gets here, so the group is homogeneous
    and the first change names the provider for all of them. A group that somehow
    is not answers per change, which is the same result the loop would give.
    """
    first = changes[0].desired if changes else None
    provider = named(first.provider) if first else None
    if provider is None:
        return [install(session, change, privilege) for change in changes]
    return provider.install_all(session, changes, privilege)


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
    """The one state that stops this entry installing, or NONE.

    One rather than a set, because no entry declares two and a set would be
    machinery for a case that does not exist. The day one does, this returns the
    set and `Preconditions.holds` takes it — both are two-line changes, and
    guessing at the shape now would be one more thing to unpick.

    Plain attribute access, not `getattr(..., False)`. Both fields are on `Entry`,
    so a rename raises here instead of quietly answering NONE — and NONE is the
    absence of the gate, which for `requires_amd_gpu` is the 12 GiB it exists to
    stop.
    """
    if entry.requires_github_auth:
        return resolve.Precondition.GITHUB_AUTH
    if entry.requires_amd_gpu:
        return resolve.Precondition.AMD_GPU
    return resolve.Precondition.NONE


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
