"""One object per mechanism, and the invariants that would otherwise be five tables.

Nothing here touches a machine. The registry is a description — which section a
provider plans from, how it tells whether one of its items is present, whether
repairing one escalates — and the whole point of one object is that those three
answers cannot be given by three files that disagree.
"""

from __future__ import annotations

import pytest

from dotfiles import catalog
from dotfiles import effects
from dotfiles import evidence as ev
from dotfiles import github_release
from dotfiles import machine as machines
from dotfiles import registry
from dotfiles import vocabulary
from dotfiles.effects import Completed
from dotfiles.privilege import Privilege
from dotfiles.providers import ghrelease
from dotfiles.providers import releases
from dotfiles.providers import toolchain
from dotfiles.resolve import DesiredItem
from dotfiles.resolve import Precondition
from dotfiles.resolve import Reason
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.session import Session


def item(provider: str, name: str, entry: catalog.Entry, *, executable: str = '', evidence_path: str = '') -> DesiredItem:
    known = registry.named(provider)
    assert known is not None
    return DesiredItem(
        section=known.section,
        provider=provider,
        resource=known.resource,
        stage=known.stage,
        name=name,
        executable=executable,
        evidence_path=evidence_path,
        precondition=Precondition.NONE,
        entry=entry,
        reason=Reason(known.section, 'test'),
    )


# ─────────────────────────────────────────────────────────────────────────────
# The registry is an index, and an index has to be unambiguous
# ─────────────────────────────────────────────────────────────────────────────


def test_no_two_providers_share_a_name_or_a_section() -> None:
    """`BY_NAME` and `BY_SECTION` are built by comprehension, so a duplicate is
    silently the last one written rather than an error — and the loser would plan
    nothing while still appearing in `--skip`'s help.

    A name has to be unique across the whole registry rather than within a
    resource, because `registry.named` is what an item's provider is looked up
    through and an item carries one name. That is why the runtimes are
    `go-toolchain` and `uv-toolchain`: `packages` already has a `go` and a `uv`.
    """
    sectioned = [provider.section for provider in registry.PROVIDERS if provider.section]

    assert len(registry.BY_NAME) == len(registry.PROVIDERS)
    assert len(registry.BY_SECTION) == len(sectioned)


def test_every_provider_belongs_to_a_resource_the_cli_exposes() -> None:
    """The resource is a CLI grouping, so a provider naming one that has no
    sub-app is unreachable: its items resolve and are never addressable."""
    assert {provider.resource for provider in registry.PROVIDERS} <= set(vocabulary.RESOURCES)


def test_every_provider_plans_from_a_section_that_exists_or_from_none() -> None:
    """A typo here resolves an empty section into an empty plan, which reads as a
    machine that declared nothing rather than as a broken registry.

    An empty section is the deliberate case, not a typo: a toolchain subscribes to
    nothing and is planned from what the tool providers resolved.
    """
    declared = set(catalog.SECTIONS) | set(catalog.SYSTEM_SECTIONS)
    assert {provider.section for provider in registry.PROVIDERS if provider.section} <= declared


def test_every_provider_names_a_stage_that_exists() -> None:
    """Stage is what orders execution, so a provider whose stage is not in the
    enum would sort into a position nothing declares."""
    assert all(provider.stage in Stage for provider in registry.PROVIDERS)


# ─────────────────────────────────────────────────────────────────────────────
# Evidence: the provider answers for its own kind
# ─────────────────────────────────────────────────────────────────────────────


def test_a_system_package_is_answered_by_its_manager_not_by_path() -> None:
    """The rule that made the old table necessary. `build-essential` installs no
    executable at all, so asking PATH reports it missing on a machine that has it.
    """
    entry = catalog.SystemPackage.from_mapping({'name': 'build-essential', 'apt': 'build-essential'})

    found = registry.evidence_for(item('system', 'build-essential', entry), {'apt': frozenset({'build-essential'})})

    assert found.verdict is Verdict.MATCHED


def test_a_release_is_answered_by_path() -> None:
    entry = catalog.GithubRelease.from_mapping({'name': 'lazygit', 'repo': 'jesseduffield/lazygit'})

    found = registry.evidence_for(item('ghrelease', 'lazygit', entry, executable='definitely-not-on-path'), {})

    assert found.verdict is Verdict.MISSING


def test_a_release_missing_a_companion_is_not_converged(tmp_path, monkeypatch) -> None:
    """The gap that made companions unmeasurable. fzf's binary being current says
    nothing about `fzf-tmux` beside it, so a machine that lost the script reported
    a converged fzf and the tmux popup binding silently did nothing — repaired only
    because the install phase re-fetched companions blind on every current tool.
    """
    on_path(tmp_path, 'demo')
    monkeypatch.setenv('PATH', str(tmp_path))
    monkeypatch.setattr(ghrelease, 'bin_dir', lambda: tmp_path)
    monkeypatch.setattr(ghrelease, 'COMPANIONS', {'demo': (releases.Companion('demo-tmux', 'https://example.invalid/x'),)})

    entry = catalog.GithubRelease.from_mapping({'name': 'demo', 'repo': 'someone/demo'})
    found = registry.evidence_for(item('ghrelease', 'demo', entry, executable='demo'), {})

    assert found.verdict is Verdict.MISSING
    assert 'demo-tmux' in found.detail


def test_a_release_whose_companions_are_all_present_is_matched(tmp_path, monkeypatch) -> None:
    on_path(tmp_path, 'demo')
    on_path(tmp_path, 'demo-tmux')
    monkeypatch.setenv('PATH', str(tmp_path))
    monkeypatch.setattr(ghrelease, 'bin_dir', lambda: tmp_path)
    monkeypatch.setattr(ghrelease, 'COMPANIONS', {'demo': (releases.Companion('demo-tmux', 'https://example.invalid/x'),)})

    entry = catalog.GithubRelease.from_mapping({'name': 'demo', 'repo': 'someone/demo'})
    found = registry.evidence_for(item('ghrelease', 'demo', entry, executable='demo'), {})

    assert found.verdict is Verdict.MATCHED


def on_path(directory, name: str) -> None:
    placed = directory / name
    placed.write_text('#!/bin/sh\n')
    placed.chmod(0o755)


def test_a_declared_install_path_beats_the_providers_own_rule(tmp_path) -> None:
    """An entry saying where it lands is more specific than a rule about how its
    neighbours are usually found — and the override is on the base class so a new
    provider cannot forget it."""
    landed = tmp_path / 'bashselfupdate'
    landed.write_text('')
    declared = {'name': 'bashselfupdate', 'description': 'a sourced library', 'installed_path': str(landed)}
    entry = catalog.CustomInstaller.from_mapping(declared)

    found = registry.evidence_for(item('custom', 'bashselfupdate', entry, evidence_path=str(landed)), {})

    assert found.verdict is Verdict.MATCHED


def test_an_item_whose_provider_was_retired_is_unknown_rather_than_a_crash() -> None:
    """A run record crosses machines, so it can name a provider this checkout no
    longer has. Reading one must not raise."""
    entry = catalog.GoTool.from_mapping({'name': 'ghost', 'package': 'example.com/ghost'})
    orphan = DesiredItem(
        section='go_tools',
        provider='retired',
        resource='packages',
        stage=Stage.TOOLS,
        name='ghost',
        executable='ghost',
        evidence_path='',
        precondition=Precondition.NONE,
        entry=entry,
        reason=Reason('go_tools', 'test'),
    )

    assert registry.evidence_for(orphan, {}).verdict is Verdict.UNKNOWN


# ─────────────────────────────────────────────────────────────────────────────
# Root: one dispatch, two kinds of answer
# ─────────────────────────────────────────────────────────────────────────────


def test_installing_a_system_package_needs_root_whatever_the_entry_says() -> None:
    """Root is a property of apt and pacman, and no entry declares otherwise —
    which is why this provider answers with a constant rather than reading a field
    that would not be there."""
    entry = catalog.SystemPackage.from_mapping({'name': 'curl', 'apt': 'curl'})

    assert registry.needs_root(item('system', 'curl', entry))


def test_the_go_runtime_is_the_only_one_that_needs_root() -> None:
    """It unpacks over `/usr/local/go`; the other three install under `$HOME`.

    Go could too, but `.zshenv` and `toolchain.TOOL_PATH_DIRS`
    all name `/usr/local/go/bin`, so moving it is a change to every one of them
    and to every machine already built.
    """
    runtimes = {provider.name: provider for provider in registry.for_resource('toolchains')}
    needs_root = {name: provider.needs_root(None) for name, provider in runtimes.items()}  # type: ignore[arg-type]

    assert needs_root == {'go-toolchain': True, 'rust-toolchain': False, 'uv-toolchain': False, 'node-toolchain': False}


def test_every_runtime_can_actually_install_itself() -> None:
    """The base `Provider.install` is a faithful description of a mechanism this
    package does not drive yet, and returns REFUSED to say so. That is the wrong
    answer for a runtime — one with no mechanism is a missing subclass, not a
    description — so `converge` is abstract and this is what catches the omission.
    """
    for provider in registry.for_resource('toolchains'):
        assert type(provider).converge is not registry.ToolchainProvider.converge, provider.name


class TestUvToolRepair:
    """A uv repair has to reach uv as something uv will act on.

    `uv tool install <target>` exits 0 printing "already installed" when the
    requirement matches its receipt, and the provider reads that exit code as
    success. So a `STALE` uv tool — which is every entry `--reinstall` names, and
    the git tool whose pin did not move — recorded DONE while nothing happened.
    """

    RUFF = catalog.UvTool.from_mapping({'name': 'ruff'})
    SYNCER = catalog.GitUvTool.from_mapping({'name': 'syncer', 'repo': 'https://github.com/datapointchris/syncer.git'})

    def repair(self, monkeypatch, provider: str, name: str, entry: catalog.Entry, verdict: Verdict) -> tuple[str, ...]:
        """One change through its provider, returning the argv uv was handed."""
        calls: list[tuple[str, ...]] = []

        def uv(command, **_kwargs):
            calls.append(tuple(str(part) for part in command))
            return Completed(tuple(str(part) for part in command), 0, '')

        monkeypatch.setattr(effects, 'run', uv)
        monkeypatch.setattr(github_release, 'latest_version', lambda repo, tag_prefix='': 'v6.0.0')

        planned = item(provider, name, entry)
        change = Change('packages', planned.stage, planned.address, verdict, repair=Repair.AUTOMATIC, desired=planned)
        found = registry.named(provider)
        assert found is not None
        outcome = found.install(Session(machine_name='box'), change, planned, Privilege(offer=False))

        assert outcome.status is OutcomeStatus.DONE
        return calls[0]

    def test_a_stale_pypi_tool_is_installed_again_rather_than_no_opped(self, monkeypatch) -> None:
        argv = self.repair(monkeypatch, 'uv', 'ruff', self.RUFF, Verdict.STALE)

        assert '--reinstall' in argv

    def test_a_stale_git_tool_is_installed_again_at_its_pin(self, monkeypatch) -> None:
        argv = self.repair(monkeypatch, 'uv-git', 'syncer', self.SYNCER, Verdict.STALE)

        assert '--reinstall' in argv

    def test_a_missing_tool_has_nothing_to_install_over(self, monkeypatch) -> None:
        """MISSING is the only other verdict `apply` acts on, and there is no
        installed copy for the flag to replace."""
        assert '--reinstall' not in self.repair(monkeypatch, 'uv', 'ruff', self.RUFF, Verdict.MISSING)
        assert '--reinstall' not in self.repair(monkeypatch, 'uv-git', 'syncer', self.SYNCER, Verdict.MISSING)


class TestTheVersionFloorABundleHasToClear:
    """What an online fallback compares a staged bundle against before writing it.

    One function because both providers with a bundle fallback ask it, and two
    copies is what lets cargo and go answer `--reinstall` differently — which is
    the one case where the honest answer is not the installed version.
    """

    FD = catalog.CargoPackage.from_mapping({'name': 'fd-find', 'command': 'fd'})

    def floor(self, *, reinstall: bool, observed: str, verdict: Verdict = Verdict.STALE) -> str:
        planned = item('cargo', 'fd-find', self.FD)
        change = Change('packages', planned.stage, planned.address, verdict, repair=Repair.AUTOMATIC, desired=planned, observed=observed)
        return registry.version_floor(Session(machine_name='box', reinstall=reinstall), change)

    def test_a_stale_row_floors_the_bundle_at_the_version_currency_measured(self) -> None:
        assert self.floor(reinstall=False, observed='10.4.2') == '10.4.2'

    def test_a_missing_tool_sets_no_floor_because_any_version_is_a_gain(self) -> None:
        assert self.floor(reinstall=False, observed='', verdict=Verdict.MISSING) == ''

    def test_reinstall_sets_no_floor_at_all(self) -> None:
        """It asks for the tool again whatever it reports, so comparing against what
        it reports would decline the only thing it was invoked to do."""
        assert self.floor(reinstall=True, observed='10.4.2') == ''


def test_every_packages_provider_can_install_what_it_plans() -> None:
    """The whole `packages` resource has converted, so the base `Provider.install`
    — which refuses, to stop a run reporting converged for work it never did — is
    no longer a legitimate answer here.

    Asserted on the registry rather than through the resource, because there is no
    longer an unconverted provider to write that test against: the case is now
    unrepresentable, and this is what keeps it that way when a mechanism is added.
    The `system` half is a different story and `tests/resources/test_system.py`
    still holds the refusal there.
    """
    for provider in registry.for_resource('packages'):
        assert type(provider).install is not registry.Provider.install, provider.name


def test_a_macos_preference_does_not_need_root_and_the_entry_is_what_says_so() -> None:
    """The other half of why `needs_root` is a method: for `system.yml` the answer
    is per row and already declared. A flat field here would be a second source
    for a fact the entry carries, which is the disease the registry cures."""
    entry = catalog.MacosDefault.from_mapping({'domain': 'com.apple.dock', 'key': 'tilesize', 'type': 'int', 'value': '90'})

    assert not registry.needs_root(item('macos-default', 'com.apple.dock/tilesize', entry))


# ─────────────────────────────────────────────────────────────────────────────
# The inventory is asked once per manager, and only when something needs it
# ─────────────────────────────────────────────────────────────────────────────


def test_each_manager_is_asked_once_however_many_packages_name_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """195 subprocesses to answer one question is what this replaced."""
    asked: list[str] = []

    def record(name: str, **_asked_how: object) -> frozenset[str]:
        asked.append(name)
        return frozenset({'curl'})

    monkeypatch.setattr(ev, 'query', record)

    inventories = ev.Inventories()
    for _ in range(3):
        inventories.get('apt')

    assert asked == ['apt']


def test_a_manager_that_cannot_answer_is_not_asked_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """A machine without flatpak would otherwise pay a failed lookup once per
    declared flatpak app, which is the shape of the cost this cache exists for."""
    asked: list[str] = []

    def refuse(name: str, **_asked_how: object) -> None:
        asked.append(name)
        return None

    monkeypatch.setattr(ev, 'query', refuse)

    inventories = ev.Inventories()
    assert inventories.get('flatpak') is None
    assert inventories.get('flatpak') is None
    assert asked == ['flatpak']


def test_only_the_managers_that_answered_are_reported_as_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    """`asked` is what the system row prints, and naming a manager that returned
    nothing would turn a shrug into a claim to have measured something."""
    monkeypatch.setattr(ev, 'query', lambda name, **kwargs: frozenset({'curl'}) if name == 'apt' else None)

    inventories = ev.Inventories()
    inventories.get('apt')
    inventories.get('flatpak')

    assert inventories.asked == frozenset({'apt'})


def test_a_precondition_is_readable_on_an_entry_from_any_section() -> None:
    """The fields are on `Entry`, so `precondition_of` is a plain attribute access.

    Asserted through sections that did *not* declare them before the move — a
    cargo package and a shell plugin — because that is what the move buys: the
    read no longer has to default for "this subclass has no such field", and a
    default there answers `NONE`, which is the absence of the gate.
    """
    private = catalog.CargoPackage.from_mapping({'name': 'somecrate', 'requires_github_auth': True})
    accelerated = catalog.ShellPlugin.from_mapping({'name': 'someplugin', 'repo': 'x/y', 'requires_amd_gpu': True})

    assert registry.precondition_of(private) is Precondition.GITHUB_AUTH
    assert registry.precondition_of(accelerated) is Precondition.AMD_GPU


def test_a_renamed_precondition_field_raises_rather_than_reading_as_ungated() -> None:
    """The whole point of not reaching for `getattr(..., False)`: under it a rename
    answers `NONE` silently, which for `requires_amd_gpu` is the 12 GiB it exists
    to stop."""

    class Renamed:
        """An entry whose `requires_amd_gpu` was renamed out from under the reader."""

        requires_github_auth = False

    with pytest.raises(AttributeError):
        registry.precondition_of(Renamed())  # type: ignore[arg-type]


def test_the_go_toolchain_is_answered_by_where_it_is_unpacked(tmp_path, monkeypatch) -> None:
    """`which` answers a different question than the declaration asks.

    A container picked up Arch's `go` package transitively, so `which go` found
    `/usr/sbin/go` and the toolchain reported itself installed while
    `/usr/local/go` did not exist — every Go tool then built against a runtime this
    repo had not put there, and nothing measuring the version noticed.

    Still live on the fleet rather than a container artefact: an Arch box reached
    over ssh resolves `/usr/bin/go` at go1.26.6 while `GO_ROOT` holds go1.26.5.
    """
    shadowing = tmp_path / 'bin'
    shadowing.mkdir()
    on_path(shadowing, 'go')
    monkeypatch.setenv('PATH', str(shadowing))

    unpacked_to = tmp_path / 'local' / 'go' / 'bin' / 'go'
    provider = registry.GoToolchain(
        'go-toolchain', 'toolchains', Stage.TOOLCHAIN, runtime='go', executable='go', installed_at=str(unpacked_to)
    )
    planned = provider.plan(machines.load('archlinux-personal-workstation'), catalog.load(), ())

    assert provider.evidence(planned[0], {}).verdict is Verdict.MISSING, 'a go on PATH is not the go this repo installs'

    unpacked_to.parent.mkdir(parents=True)
    unpacked_to.write_text('#!/bin/sh\n')

    assert provider.evidence(planned[0], {}).verdict is Verdict.MATCHED


def test_the_registered_go_toolchain_names_the_path_everything_else_names() -> None:
    """One constant behind every naming of the Go root.

    `toolchain.GO_ROOT` is the source: `TOOL_PATH_DIRS` derives from it,
    `go_command` resolves through it, and this registration reads it rather than
    respelling it. `.zshenv` is the one copy that cannot import Python, and
    `tests/cli/test_apply.py` is what holds it to the list.
    """
    provider = registry.named('go-toolchain')

    assert isinstance(provider, registry.GoToolchain)
    assert provider.installed_at == str(toolchain.GO_ROOT / 'bin' / 'go')
    assert str(toolchain.GO_ROOT / 'bin') in toolchain.TOOL_PATH_DIRS


def test_a_runtime_with_no_fixed_home_is_answered_by_path(tmp_path, monkeypatch) -> None:
    """The other three go wherever their own installer puts them, so `which` is the
    right question for them and this must not have changed it."""
    on_path(tmp_path, 'rustc')
    monkeypatch.setenv('PATH', str(tmp_path))
    provider = registry.named('rust-toolchain')
    assert provider is not None

    resolved = (item('cargo', 'ripgrep', catalog.CargoPackage.from_mapping({'name': 'ripgrep', 'command': 'rg'})),)
    planned = provider.plan(machines.load('archlinux-personal-workstation'), catalog.load(), resolved)

    assert planned[0].evidence_path == ''
    assert registry.evidence_for(planned[0], {}).verdict is Verdict.MATCHED


def test_a_section_carries_the_toolchain_it_needs() -> None:
    """`needed_by` says a runtime is wanted *because* a section resolved, and
    `resolve` honours it — so a selection that dropped it honoured the declaration
    in the plan and ignored it in the run.

    `packages apply --source cargo_packages` on a machine without rustup failed
    with `cargo binstall bat exited 127: cargo: No such file or directory`, which
    is a selection asking for something that cannot install.
    """
    assert [provider.name for provider in registry.serving('cargo_packages')] == ['rust-toolchain', 'cargo']
    assert [provider.name for provider in registry.serving('go_tools')] == ['go-toolchain', 'go']
    assert [provider.name for provider in registry.serving('npm_globals')] == ['node-toolchain', 'npm']


def test_a_section_needing_no_toolchain_carries_only_its_own_provider() -> None:
    assert [provider.name for provider in registry.serving('github_releases')] == ['ghrelease']


def test_the_toolchain_comes_first_because_that_is_the_order_it_installs_in() -> None:
    """Ordering is `Stage`'s, not this function's — but a caller reading the tuple
    should not have to know that to see the dependency."""
    names = [provider.name for provider in registry.serving('cargo_packages')]
    stages = [registry.named(name).stage for name in names]  # type: ignore[union-attr]

    assert stages == sorted(stages)


def test_a_section_nothing_installs_serves_nothing() -> None:
    """`runtimes` is in `UNPROVIDED`, and the caller turns an empty answer into the
    usage error naming why."""
    assert registry.serving('runtimes') == ()
