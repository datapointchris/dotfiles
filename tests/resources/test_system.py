"""What the OS package manager installed, read without escalating.

The queries behind these — `pacman -Qq`, `dpkg-query`, `brew list`,
`flatpak list` — all answer without sudo, which is the property that lets `check`
run anywhere including a container with no passwordless sudo. The inventories are
passed in directly here so the rule can be asserted without a machine that has
each manager.
"""

from __future__ import annotations

import dataclasses as dc
import shutil
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from dotfiles import catalog
from dotfiles import coordinates as axes
from dotfiles import evidence as ev
from dotfiles import providers
from dotfiles import registry
from dotfiles.privilege import Privilege
from dotfiles.providers import bootstrap
from dotfiles.providers import syspkg
from dotfiles.resolve import Precondition
from dotfiles.resolve import Preconditions
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.resources import system
from dotfiles.session import Session


def executable(directory: Path, name: str, script: str = '#!/bin/sh\nexit 0\n') -> Path:
    """See `_executable` in tests/conftest.py for why this is copied rather than imported."""
    target = directory / name
    target.write_text(script)
    target.chmod(target.stat().st_mode | stat.S_IEXEC)
    return target


def session(
    tmp_path: Path,
    packages: dict[str, Any],
    manifest: dict[str, Any],
    system_config: dict[str, Any] | None = None,
    **overrides: Any,
) -> Session:
    repo = tmp_path / 'repo'
    (repo / 'install' / 'manifests').mkdir(parents=True, exist_ok=True)
    (repo / 'install' / 'packages.yml').write_text(yaml.safe_dump(packages, sort_keys=False))
    (repo / 'install' / 'flags.yml').write_text('{}')
    (repo / 'install' / 'manifests' / 'box.yml').write_text(yaml.safe_dump(manifest, sort_keys=False))
    # Absent rather than empty when nothing is declared, because that is the state
    # every other test in this file runs in and the one a synthetic tree has.
    if system_config is not None:
        (repo / 'install' / 'system.yml').write_text(yaml.safe_dump(system_config, sort_keys=False))
    home = tmp_path / 'home'
    home.mkdir(exist_ok=True)
    return Session(machine_name='box', repo=repo, home=home, **overrides)


@pytest.fixture(autouse=True)
def unmeasured_currency(monkeypatch: pytest.MonkeyPatch):
    """No test in this file asks a package manager what is behind.

    Autouse because the `manager` rows are planned from whatever else the plan
    reached, so every fixture here grows one per manager without asking — and the
    unstubbed read is `checkupdates` against the Arch box running the suite, which
    makes a verdict here depend on what that machine is behind on. Currency is
    measured in its own tests, against a stub that says what it wants.
    """
    monkeypatch.setattr(syspkg, 'outdated', lambda manager: None)


@pytest.fixture(autouse=True)
def unmeasured_requests(request, monkeypatch: pytest.MonkeyPatch):
    """Most tests in this file do not ask a package manager what somebody chose.

    Autouse for `unmeasured_currency`'s reason, one manager over. The read is
    planned from whatever else the plan reached, so every fixture here would grow
    one without asking — and unstubbed it is `brew leaves` against the machine
    running the suite, which puts that machine's hand-installed formulae into the
    changes of tests about something else entirely.

    **It stands aside for `measures_requests`**, and that escape hatch is the point
    rather than a convenience. Autouse over the whole file meant the one test
    written to drive a real `brew` through `syspkg.requested` never reached it:
    deleting the parse under test left the suite green, because the stub answered
    first. A fixture that cannot be stepped out of silently owns every assertion
    beneath it.
    """
    if 'measures_requests' in request.keywords:
        return
    monkeypatch.setattr(syspkg, 'requested', lambda manager: None)


def payload(live: Session):
    """Everything the plan holds for this resource but the manager rows."""
    return [item for item in live.plan.for_resource('system') if item.provider != 'manager']


def only_item(live: Session):
    """The one payload item, ignoring the manager rows planned beside it.

    A `manager/<name>` row is one per package manager the rest of the plan
    reaches, so it appears wherever a package does. It is what upgrades that
    manager, and it is never what a test about a package name is looking at.
    """
    items = [item for item in live.plan.for_resource('system') if item.provider != 'manager']
    assert len(items) == 1, items
    return items[0]


WORKSTATION = {'machine': 'box', 'platform': 'linux', 'system_packages': 'workstation'}


def test_the_declared_package_name_is_what_is_looked_for(tmp_path: Path) -> None:
    """A package name is not a binary name and not the entry name: the entry is
    `7zip`, the package is `p7zip-full` on apt, and the binary is `7zz`."""
    live = session(tmp_path, {'system_packages': [{'name': '7zip', 'apt': 'p7zip-full', 'pacman': '7zip'}]}, WORKSTATION)
    item = only_item(live)

    assert registry.evidence_for(item, {'apt': frozenset({'p7zip-full'})}).verdict is Verdict.MATCHED
    assert registry.evidence_for(item, {'apt': frozenset({'7zip'})}).verdict is Verdict.MISSING


def test_a_package_installing_no_binary_is_still_answerable(tmp_path: Path, fake_bin: Path) -> None:
    """`build-essential` and `ca-certificates` put no executable on PATH, so the
    check that predated this skipped the whole section rather than report every one
    of them missing on a fully-installed machine."""
    live = session(tmp_path, {'system_packages': [{'name': 'build-essential', 'apt': 'build-essential'}]}, WORKSTATION)

    assert registry.evidence_for(only_item(live), {'apt': frozenset({'build-essential'})}).verdict is Verdict.MATCHED


def test_an_aur_package_is_answered_by_pacman(tmp_path: Path) -> None:
    """An AUR package is a pacman package once it is installed."""
    live = session(
        tmp_path,
        {'system_packages': [{'name': 'zen-browser', 'aur': 'zen-browser-bin'}]},
        {'machine': 'box', 'platform': 'archlinux', 'system_packages': 'workstation'},
    )

    assert registry.evidence_for(only_item(live), {'pacman': frozenset({'zen-browser-bin'})}).verdict is Verdict.MATCHED


def test_a_manager_that_cannot_be_asked_yields_unknown(tmp_path: Path) -> None:
    """Unverified is not permission. Reporting every apt package missing because
    dpkg-query is absent would be a measured-looking wrong answer."""
    live = session(tmp_path, {'system_packages': [{'name': 'curl', 'apt': 'curl'}]}, WORKSTATION)

    assert registry.evidence_for(only_item(live), {}).verdict is Verdict.UNKNOWN


def test_an_unmeasurable_package_is_nobody_s_to_repair(tmp_path: Path, fake_bin: Path) -> None:
    """The manager is present and refuses to answer, which is the state that must
    not read as missing. Shadowed rather than left to the host: without this the
    assertion holds on Arch only because dpkg-query is absent there, and inverts
    on any Debian machine — including every CI runner."""
    executable(fake_bin, 'dpkg-query', '#!/bin/sh\nexit 1\n')
    live = session(tmp_path, {'system_packages': [{'name': 'curl', 'apt': 'curl'}]}, WORKSTATION)

    observed = system.RESOURCE.observe(live, live.plan)
    change = system.RESOURCE.diff(live.plan, observed)[0]

    assert change.verdict is Verdict.UNKNOWN
    assert change.repair is Repair.NONE
    assert not change.actionable


def test_a_real_inventory_query_is_parsed(tmp_path: Path, fake_bin: Path) -> None:
    """End to end through the actual subprocess, because the parse and the command
    are one thing: a `-f` format that changed would break both silently."""
    executable(fake_bin, 'dpkg-query', '#!/bin/sh\nprintf "build-essential\\ncurl\\n"\n')
    live = session(tmp_path, {'system_packages': [{'name': 'curl', 'apt': 'curl'}]}, WORKSTATION)

    observed = system.RESOURCE.observe(live, live.plan)

    assert observed.asked == {'apt'}
    assert changes(live) == []


def test_every_installer_maps_to_a_query_that_exists() -> None:
    """A missing key and a deliberately empty one looked the same, and `flatpak`
    was exactly that — reporting UNKNOWN on a machine where the query works and
    both apps are installed.

    The coverage set is the whole `PackageManager` vocabulary, not the installers
    the bundles happen to select. A manifest may name its six coordinates without
    naming a bundle, so `PLATFORM_BUNDLES` is a set of shorthands rather than a
    roster of managers — and `winget` reached the repo through exactly that door,
    invisible to a set derived from the bundles.

    `flatpak` is asserted separately because no family carries it: it is selected
    by a manifest boolean rather than by the package-manager coordinate, so
    deriving from `INSTALLER_FAMILIES` alone would stop covering the installer
    that motivated this test.

    The last two assertions are what an empty value costs, from each side. `mas`
    carried one, so every App Store row fell past its inventory to a PATH probe no
    `.app` can satisfy and read MISSING on a machine where `mas list` showed it —
    which is why a named query has to resolve to a real command. And an installer
    with no inventory query at all is a real state rather than an oversight, so
    the set of them is written out: one joining it silently is the failure the
    whole table is shaped against.
    """
    installers = {installer for manager in axes.PackageManager for installer in axes.INSTALLER_FAMILIES[manager]}

    assert installers <= set(ev.INSTALLER_QUERIES)
    assert {'cask', 'flatpak', 'mas'} <= set(ev.INSTALLER_QUERIES)
    assert all(ev.QUERIES.get(query) for query in ev.INSTALLER_QUERIES.values() if query), ev.INSTALLER_QUERIES
    assert {installer for installer, query in ev.INSTALLER_QUERIES.items() if not query} == {'winget'}


def test_the_system_resource_takes_only_its_own_items(tmp_path: Path, fake_bin: Path) -> None:
    """Without resource ownership on the item, this resource and `packages` both
    claimed everything, and each reported the other's items by the wrong rule."""
    live = session(
        tmp_path,
        {
            'system_packages': [{'name': 'curl', 'apt': 'curl'}],
            'go_tools': [{'name': 'task', 'package': 'github.com/go-task/task/v3/cmd/task'}],
        },
        {**WORKSTATION, 'go_tools': ['task']},
    )

    assert {item.address for item in payload(live)} == {'system/curl'}
    assert {item.address for item in live.plan.for_resource('packages')} == {'go/task'}


# ─────────────────────────────────────────────────────────────────────────────
# The configuration half
# ─────────────────────────────────────────────────────────────────────────────


def zshenv(tmp_path: Path) -> dict[str, Any]:
    """One managed file, pointed somewhere writable so a repair can be measured."""
    return {'managed_files': [{'name': 'zdotdir', 'path': str(tmp_path / 'zshenv'), 'append_line': 'export ZDOTDIR="$HOME/.config/zsh"'}]}


def test_a_configuration_row_is_planned_beside_the_packages(tmp_path: Path) -> None:
    """One resource, two authorities. Both need root and neither is a tool, which
    is why the group membership and the apt package answer to the same noun."""
    live = session(tmp_path, {'system_packages': [{'name': 'curl', 'apt': 'curl'}]}, WORKSTATION, zshenv(tmp_path))

    assert {item.address for item in payload(live)} == {'system/curl', 'file/zdotdir'}


def test_a_configuration_change_declares_that_it_needs_root(tmp_path: Path) -> None:
    """Declared on the change rather than discovered when the write is attempted,
    so the whole list can be named at one prompt before any of it runs."""
    live = session(tmp_path, {}, WORKSTATION, zshenv(tmp_path))
    change = only_change(live)

    assert change.verdict is Verdict.MISSING
    assert change.privileged
    assert change.actionable


def test_an_apt_package_says_it_needs_root_whoever_installs_it(tmp_path: Path, fake_bin: Path) -> None:
    """Root is a fact about the mechanism, not about which code path reaches it.

    This asserted the opposite while privilege was acquired up front: a change the
    phase registry writes rather than `perform` must not, the reasoning went, put
    a password prompt in front of a run that would never ask. Acquiring root at
    the write removed that consequence — nothing prompts because of this field —
    and left the assertion saying something untrue about apt.
    """
    executable(fake_bin, 'dpkg-query', '#!/bin/sh\nexit 0\n')
    live = session(tmp_path, {'system_packages': [{'name': 'curl', 'apt': 'curl'}]}, WORKSTATION)

    assert only_change(live).privileged


def test_configuration_is_absent_from_an_owner_narrowed_plan(tmp_path: Path) -> None:
    """`--mine` means "just my tools", usually right after releasing one. A group
    membership belongs to nobody on GitHub, so filtering by owner would drop every
    row for the wrong reason — and running them anyway would turn a tool update
    into a password prompt for a reconfiguration nobody asked for."""
    live = session(tmp_path, {}, WORKSTATION, zshenv(tmp_path), owner='datapointchris')

    assert live.plan.for_resource('system') == ()


def test_applying_a_configuration_row_writes_it(tmp_path: Path, granted: Privilege) -> None:
    live = session(tmp_path, {}, WORKSTATION, zshenv(tmp_path))
    change = only_change(live)

    outcome = system.RESOURCE.perform(live, change, granted)

    assert outcome.status is OutcomeStatus.DONE
    assert (tmp_path / 'zshenv').read_text() == 'export ZDOTDIR="$HOME/.config/zsh"\n'


def test_a_row_that_became_true_since_the_report_is_skipped(tmp_path: Path, granted: Privilege) -> None:
    """`observe` ran before the report was printed and before the packages stage
    installed anything, so the state it decided from can be minutes old."""
    live = session(tmp_path, {}, WORKSTATION, zshenv(tmp_path))
    change = only_change(live)
    (tmp_path / 'zshenv').write_text('export ZDOTDIR="$HOME/.config/zsh"\n')

    assert system.RESOURCE.perform(live, change, granted).status is OutcomeStatus.SKIPPED


class Manager:
    """The package manager, recording what it was asked to do rather than doing it.

    The seam is `syspkg`, not `effects.run`: what these assert is which manager was
    chosen, what it was handed and in how many calls — the decisions this provider
    makes. Whether `pacman -S` is spelled right is `INSTALL`'s business, and a test
    that let it run would install packages on the machine running the suite.
    """

    def __init__(self, *, inventory: Path, fails: frozenset[str] = frozenset(), refuses: bool = False) -> None:
        self.calls: list[tuple[str, tuple[str, ...]]] = []
        self.refreshed: list[str] = []
        self._inventory = inventory
        """Where a successful install leaves its names, for the query to find.

        A recorder that only records is a manager whose installs never land, and
        `apply` re-observes now — so without this every outcome here is ABSENT and
        the tests assert against a machine no manager behaves like.
        """
        self._fails = fails
        self._refuses = refuses

    def install(self, manager: str, names, privilege) -> providers.Result:
        self.calls.append((manager, tuple(names)))
        broken = sorted(self._fails.intersection(names))
        if broken:
            return providers.Result(False, f'{manager} could not install {broken[0]}', kind=providers.Kind.COMMAND_FAILED)
        with self._inventory.open('a') as landed:
            landed.writelines(f'{name}\n' for name in names)
        return providers.Result(True, f'{manager}: {" ".join(names)}', kind=providers.Kind.APPLIED)

    def refresh(self, manager: str, privilege) -> providers.Result:
        self.refreshed.append(manager)
        if self._refuses:
            return providers.Result(False, 'no root', kind=providers.Kind.PRIVILEGE_UNAVAILABLE)
        return providers.Result(True, '', kind=providers.Kind.APPLIED)


@pytest.fixture
def manager(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    def install(**kwargs) -> Manager:
        recorder = Manager(inventory=tmp_path / INVENTORY, **kwargs)
        monkeypatch.setattr(syspkg, 'install', recorder.install)
        monkeypatch.setattr(syspkg, 'refresh', recorder.refresh)
        return recorder

    return install


class Bootstraps:
    """Every manager's precondition, answering however a test says the machine is.

    Stubbed rather than exercised: what a bootstrap *does* is
    `tests/install/test_bootstrap.py`'s question, and letting these run would
    build yay and download the Homebrew installer on the box running the suite.
    What is asserted through this is that the right one runs, once, before the
    batch its manager serves.
    """

    def __init__(self, *, refuses: str = '') -> None:
        self.ran: list[str] = []
        self.tapped: list[str] = []
        self._refuses = refuses

    def _answer(self, name: str) -> providers.Result:
        self.ran.append(name)
        if name == self._refuses:
            return providers.Result(False, f'{name} is unavailable here', kind=providers.Kind.PREREQUISITE_MISSING)
        return providers.Result(True, '', kind=providers.Kind.UNCHANGED)

    def homebrew(self) -> providers.Result:
        return self._answer('homebrew')

    def aur(self) -> providers.Result:
        return self._answer('aur')

    def flathub(self, installer: str, privilege) -> providers.Result:
        self.ran.append(f'flathub:{installer}')
        if self._refuses == 'flathub':
            return providers.Result(False, 'no bus', kind=providers.Kind.UNSUPPORTED_HERE)
        return providers.Result(True, '', kind=providers.Kind.APPLIED)

    def taps(self, wanted) -> providers.Result:
        self.tapped.extend(wanted)
        return self._answer('taps')


@pytest.fixture
def bootstraps(monkeypatch: pytest.MonkeyPatch):
    def arrange(**kwargs) -> Bootstraps:
        recorder = Bootstraps(**kwargs)
        for name in ('homebrew', 'aur', 'flathub', 'taps'):
            monkeypatch.setattr(bootstrap, name, getattr(recorder, name))
        return recorder

    return arrange


DECLARED = {
    'system_packages': [
        {'name': 'curl', 'apt': 'curl'},
        {'name': '7zip', 'apt': 'p7zip-full'},
        {'name': 'ripgrep', 'apt': 'ripgrep'},
    ]
}
"""apt names only, deliberately. `fake_bin` keeps the real `/usr/bin` behind it —
see its docstring — so a `pacman:` key here is answered by whatever the box running
the suite has installed, and all three read as MATCHED on an Arch machine."""


def answers_empty(fake_bin: Path, *managers: str) -> None:
    """Shadow each manager's inventory query with one that reports nothing installed.

    Necessary rather than tidy. `fake_bin` keeps the real `/usr/bin` behind it, so
    an unshadowed `flatpak list` is answered by the box running the suite — and on
    this Arch machine that means the app under test reads MATCHED, no Change is
    produced, and the assertion is made against an empty batch that installed
    nothing. Which is a green test proving nothing at all.
    """
    for manager in managers:
        executable(fake_bin, manager, '#!/bin/sh\nprintf "" \n')


INVENTORY = 'installed'
"""The file a `Manager` writes its successful installs to, under `tmp_path`.

A path rather than an argument threaded through every call site: the recorder and
the query are created by two fixtures that do not see each other, and both see
`tmp_path`.
"""


def answers_with_what_landed(fake_bin: Path, *managers: str) -> None:
    """Shadow each manager's query with one that reports what `Manager` installed.

    The pair to `answers_empty`, for a test that installs and then asserts on the
    result. `apply` re-observes, so a query that keeps saying "nothing" after a
    successful install describes a manager whose installs do not land — which is
    the defect under test elsewhere, not the premise wanted here.
    """
    for manager in managers:
        executable(fake_bin, manager, f'#!/bin/sh\ncat "$(dirname "$0")/../{INVENTORY}" 2>/dev/null || true\n')


def missing(tmp_path: Path, fake_bin: Path) -> Session:
    """A machine whose manager answers, with none of the three installed."""
    answers_with_what_landed(fake_bin, 'dpkg-query')
    return session(tmp_path, DECLARED, WORKSTATION)


def test_the_whole_batch_is_one_transaction(tmp_path: Path, fake_bin: Path, manager) -> None:
    """One `apt-get install` over three packages rather than three over one: one
    dependency resolution, one authorization, one cache read."""
    recorder = manager()
    live = missing(tmp_path, fake_bin)

    outcomes = system.RESOURCE.perform_batch(live, changes(live), Privilege(offer=False))

    assert recorder.calls == [('apt', ('p7zip-full', 'curl', 'ripgrep'))]
    assert [outcome.status for outcome in outcomes] == [OutcomeStatus.DONE] * 3


def test_the_declared_name_is_used_rather_than_the_entry_name(tmp_path: Path, fake_bin: Path, manager) -> None:
    """The entry is `7zip` and the package is `p7zip-full` on apt. Installing the
    entry name is installing something that does not exist."""
    recorder = manager()
    live = missing(tmp_path, fake_bin)

    system.RESOURCE.perform_batch(live, changes(live), Privilege(offer=False))

    assert 'p7zip-full' in recorder.calls[0][1]
    assert '7zip' not in recorder.calls[0][1]


def test_the_manager_is_refreshed_once_before_the_batch(tmp_path: Path, fake_bin: Path, manager) -> None:
    """apt resolves against its cached lists, so a stale cache 404s on files that
    exist. Once per manager, not once per package."""
    recorder = manager()
    live = missing(tmp_path, fake_bin)

    system.RESOURCE.perform_batch(live, changes(live), Privilege(offer=False))

    assert recorder.refreshed == ['apt']


def test_a_refresh_that_cannot_run_fails_the_batch_rather_than_installing_anyway(tmp_path: Path, fake_bin: Path, manager) -> None:
    """Installing against a database that could not be refreshed is the
    partial-upgrade case on Arch, and both fail later naming the wrong cause."""
    recorder = manager(refuses=True)
    live = missing(tmp_path, fake_bin)

    outcomes = system.RESOURCE.perform_batch(live, changes(live), Privilege(offer=False))

    assert recorder.calls == []
    assert [outcome.status for outcome in outcomes] == [OutcomeStatus.FAILED] * 3
    assert 'could not be refreshed' in outcomes[0].message


def test_a_failed_batch_is_retried_one_package_at_a_time(tmp_path: Path, fake_bin: Path, manager) -> None:
    """`apt-get install a b c` exiting 1 says nothing about which of the three is
    broken, and the machine still wants the other two."""
    recorder = manager(fails=frozenset({'p7zip-full'}))
    live = missing(tmp_path, fake_bin)

    outcomes = system.RESOURCE.perform_batch(live, changes(live), Privilege(offer=False))

    assert recorder.calls[0] == ('apt', ('p7zip-full', 'curl', 'ripgrep'))
    assert recorder.calls[1:] == [('apt', ('p7zip-full',)), ('apt', ('curl',)), ('apt', ('ripgrep',))]
    assert [outcome.status for outcome in outcomes] == [OutcomeStatus.FAILED, OutcomeStatus.DONE, OutcomeStatus.DONE]


def test_a_package_this_machine_has_no_manager_for_is_refused_not_claimed(tmp_path: Path, fake_bin: Path, manager) -> None:
    """Reporting it installed would leave a run claiming a converged machine it
    never touched.

    Built by hand rather than planned, because `resolve.available` filters a
    brew-only entry off an apt machine before it can reach a provider — so this
    asserts what the guard does, at the only level it is reachable from.
    """
    recorder = manager()
    live = missing(tmp_path, fake_bin)
    item = live.plan.for_resource('system')[0]
    unusable = dc.replace(item, entry=catalog.SystemPackage.from_mapping({'name': 'mas', 'brew': 'mas'}))
    change = Change('system', unusable.stage, unusable.address, Verdict.MISSING, repair=Repair.AUTOMATIC, desired=unusable)

    outcomes = registry.BY_NAME['system'].install_all(live, [change], Privilege(offer=False))

    assert recorder.calls == []
    assert [outcome.status for outcome in outcomes] == [OutcomeStatus.REFUSED]


def test_a_manager_whose_bootstrap_refuses_installs_nothing_through_it(tmp_path: Path, fake_bin: Path, manager, bootstraps) -> None:
    """REFUSED rather than FAILED, because nothing was written and the run has not
    gone wrong — a Mac with no Homebrew yet is a machine mid-build, not a broken
    one, and `Outcome.ok` is what keeps the stage honest about the difference."""
    recorder = manager()
    ready = bootstraps(refuses='homebrew')
    answers_empty(fake_bin, 'brew')
    live = session(tmp_path, {'macos_casks': [{'name': 'ghostty'}]}, MAC)

    outcomes = registry.BY_NAME['cask'].install_all(live, changes(live), Privilege(offer=False))

    assert recorder.calls == []
    assert [outcome.status for outcome in outcomes] == [OutcomeStatus.REFUSED]
    assert 'homebrew is unavailable' in outcomes[0].message
    assert ready.ran == ['homebrew']


# ─────────────────────────────────────────────────────────────────────────────
# Casks, App Store apps and flatpak apps
# ─────────────────────────────────────────────────────────────────────────────

MAC = {'machine': 'box', 'platform': 'macos', 'system_packages': 'workstation'}
ARCH = {'machine': 'box', 'platform': 'archlinux', 'system_packages': 'workstation', 'flatpak': True}


def test_casks_install_in_one_brew_call(tmp_path: Path, fake_bin: Path, manager, bootstraps) -> None:
    """A cask is a formula from another tap of the same manager, so it batches for
    the same reason and through the same code."""
    recorder = manager()
    bootstraps()
    answers_with_what_landed(fake_bin, 'brew')
    live = session(tmp_path, {'macos_casks': [{'name': 'ghostty'}, {'name': 'orbstack'}]}, MAC)

    outcomes = registry.BY_NAME['cask'].install_all(live, changes(live), Privilege(offer=False))

    assert recorder.calls == [('cask', ('ghostty', 'orbstack'))]
    assert [outcome.status for outcome in outcomes] == [OutcomeStatus.DONE] * 2


def test_an_app_store_app_is_installed_by_its_numeric_id(tmp_path: Path, fake_bin: Path, manager, bootstraps) -> None:
    """`mas install Xcode` is not a command. The name is for the report and the
    bundle check; the id is the only thing the App Store answers to."""
    recorder = manager()
    bootstraps()
    live = session(tmp_path, {'mas_apps': [{'name': 'Xcode', 'id': 497799835}]}, MAC)

    registry.BY_NAME['mas'].install_all(live, changes(live), Privilege(offer=False))

    assert recorder.calls == [('mas', ('497799835',))]


def app_store_item(tmp_path: Path, name: str, identifier: int):
    live = session(tmp_path, {'mas_apps': [{'name': name, 'id': identifier}]}, MAC)
    return live.plan.for_resource('system')[0]


def test_the_app_store_provider_asks_mas_and_not_only_the_bundle(tmp_path: Path) -> None:
    """Through `registry.evidence_for`, not `by_app_store` directly.

    The rule and the provider that uses it are separate edits, and the wiring is
    the half that silently reverted once: with the rule written and the provider
    still pointing at `by_app_bundle`, every test below this one passed while the
    machine kept reporting the app missing.
    """
    item = app_store_item(tmp_path, 'Disk Space Analyzer', 446243721)

    found = registry.evidence_for(item, {'mas': frozenset({'446243721'})})

    assert found.verdict is Verdict.MATCHED


def test_an_app_store_app_whose_bundle_is_not_its_store_title_is_found_by_mas(tmp_path: Path) -> None:
    """446243721 is `Disk Space Analyzer` in the store and `Disk Inspector.app` on
    disk, so no name-derived path finds it. Before mas was asked, this fell through
    to `by_command` — and a GUI app is never on PATH, so the row read
    `Disk Space Analyzer is not on PATH` on a machine where `mas list` shows it,
    permanently, and `apply` re-ran `mas install` for it every run."""
    item = app_store_item(tmp_path, 'Disk Space Analyzer', 446243721)

    found = ev.by_app_store(item, {'mas': frozenset({'446243721'})})

    assert found.verdict is Verdict.MATCHED
    assert '446243721' in found.detail


def test_a_bundle_mas_never_installed_is_still_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An app restored by Migration Assistant works and is absent from `mas list`,
    which is why the bundle is asked first rather than replaced by the inventory."""
    home = tmp_path / 'home'
    (home / 'Applications' / 'Dato.app').mkdir(parents=True)
    monkeypatch.setenv('HOME', str(home))
    item = app_store_item(tmp_path, 'Dato', 1470584107)

    found = ev.by_app_store(item, {'mas': frozenset()})

    assert found.verdict is Verdict.MATCHED
    assert 'Dato.app' in found.detail


def test_an_app_store_app_nobody_can_confirm_is_missing_rather_than_off_PATH(tmp_path: Path) -> None:
    """The message names both reads. `is not on PATH` was the old one and described
    a question that cannot be asked of a `.app`."""
    item = app_store_item(tmp_path, 'Absent', 1)

    found = ev.by_app_store(item, {'mas': frozenset()})

    assert found.verdict is Verdict.MISSING
    assert 'not on PATH' not in found.detail


def test_an_app_store_app_is_unknown_when_mas_cannot_be_asked(tmp_path: Path) -> None:
    """A Mac without mas installed yet. UNKNOWN, never MISSING: unverified is not
    permission, and a fresh machine would otherwise reinstall every declared app."""
    item = app_store_item(tmp_path, 'Absent', 1)

    assert ev.by_app_store(item, {}).verdict is Verdict.UNKNOWN


def test_mas_list_is_read_as_ids_not_whole_lines(tmp_path: Path, fake_bin: Path) -> None:
    """`mas list` prints `<id>  <Name>  (<version>)`, unlike every other query here,
    which prints a bare name per line. Taking the line whole matches nothing."""
    executable(fake_bin, 'mas', '#!/bin/sh\nprintf "446243721  Disk Space Analyzer  (6.0.2)\\n"\n')

    assert ev.query('mas') == frozenset({'446243721'})


def test_a_flatpak_app_is_installed_by_its_reverse_dns_id(tmp_path: Path, fake_bin: Path, manager, bootstraps) -> None:
    recorder = manager()
    bootstraps()
    answers_empty(fake_bin, 'flatpak')
    live = session(tmp_path, {'flatpak_apps': [{'name': 'dbeaver', 'flatpak_id': 'io.dbeaver.DBeaverCommunity'}]}, ARCH)

    registry.BY_NAME['flatpak'].install_all(live, changes(live), Privilege(offer=False))

    assert recorder.calls == [('flatpak', ('io.dbeaver.DBeaverCommunity',))]


def test_the_flathub_bootstrap_is_told_which_manager_installs_flatpak(tmp_path: Path, fake_bin: Path, manager, bootstraps) -> None:
    """flatpak is the manager, so it is not one of its own packages — the machine's
    own package manager is what puts it there."""
    manager()
    ready = bootstraps()
    answers_empty(fake_bin, 'flatpak')
    live = session(tmp_path, {'flatpak_apps': [{'name': 'dbeaver', 'flatpak_id': 'io.dbeaver.DBeaverCommunity'}]}, ARCH)

    registry.BY_NAME['flatpak'].install_all(live, changes(live), Privilege(offer=False))

    assert ready.ran == ['flathub:pacman']


def test_the_taps_are_registered_before_the_formulae_that_live_in_them(tmp_path: Path, fake_bin: Path, manager, bootstraps) -> None:
    """A formula in an unregistered tap is unresolvable, and one unresolvable
    formula aborts the whole batched install before it touches anything."""
    manager()
    ready = bootstraps()
    answers_empty(fake_bin, 'brew')
    declared = {'macos_taps': ['FelixKratz/formulae'], 'system_packages': [{'name': 'borders', 'brew': 'borders'}]}
    live = session(tmp_path, declared, MAC)

    registry.BY_NAME['system'].install_all(live, changes(live), Privilege(offer=False))

    assert ready.ran == ['homebrew', 'taps']
    assert ready.tapped == ['FelixKratz/formulae']


def test_the_apps_are_planned_after_the_packages_that_provide_their_managers(tmp_path: Path, fake_bin: Path) -> None:
    """`mas` is itself a Homebrew formula and a cask needs the brew that installed
    it. The plan sorts on `(stage, provider, name)`, so on stage alone all three app
    providers would sort ahead of `system` — which is what SYSTEM_APPS exists for.
    """
    declared = {
        'system_packages': [{'name': 'mas', 'brew': 'mas'}],
        'macos_casks': [{'name': 'ghostty'}],
        'mas_apps': [{'name': 'Xcode', 'id': 497799835}],
    }
    live = session(tmp_path, declared, MAC)

    assert [item.provider for item in payload(live)] == ['system', 'cask', 'mas']


# ─────────────────────────────────────────────────────────────────────────────
# The managers themselves, which is what `update.sh` upgraded
# ─────────────────────────────────────────────────────────────────────────────


def behind(monkeypatch: pytest.MonkeyPatch, answers: dict[str, frozenset[str] | None]) -> None:
    monkeypatch.setattr(syspkg, 'outdated', lambda manager: answers.get(manager))


def manager_rows(live: Session) -> dict[str, Change]:
    observed = system.RESOURCE.observe(live, live.plan)
    found = system.RESOURCE.diff(live.plan, observed)
    return {change.item.removeprefix('manager/'): change for change in found if change.item.startswith('manager/')}


def test_a_manager_is_planned_for_every_one_the_machine_installs_through(tmp_path: Path, fake_bin: Path) -> None:
    """Read off what the plan reached rather than off the coordinates, which are a
    superset: brew brings `cask` and `mas` with it, and a Mac subscribing to no
    casks has nothing for `brew upgrade --cask` to move."""
    answers_empty(fake_bin, 'brew')
    live = session(tmp_path, {'system_packages': [{'name': 'curl', 'brew': 'curl'}], 'macos_casks': [{'name': 'ghostty'}]}, MAC)

    assert set(manager_rows(live)) <= {'brew', 'cask'}
    assert 'mas' not in {item.name for item in live.plan.for_resource('system') if item.provider == 'manager'}


def test_a_manager_with_nothing_behind_is_converged(tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    answers_empty(fake_bin, 'dpkg-query')
    behind(monkeypatch, {'apt': frozenset()})
    live = session(tmp_path, DECLARED, WORKSTATION, refresh=True)

    assert 'apt' not in manager_rows(live)


def test_a_manager_with_packages_behind_is_stale_and_names_them(tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """STALE rather than MISSING: the manager is there and doing its job, and what
    drifted is the machine's distance from what its repositories now hold. A count
    alone says a machine is behind and nothing about whether it matters.

    `refresh` because apt's currency read refreshes an index copy before consulting
    it, which puts it in `syspkg.NETWORKED` — a session that declined the network
    reaches the row below without asking the stub.
    """
    answers_empty(fake_bin, 'dpkg-query')
    behind(monkeypatch, {'apt': frozenset({'curl', 'linux-image-generic'})})
    live = session(tmp_path, DECLARED, WORKSTATION, refresh=True)

    change = manager_rows(live)['apt']

    assert change.verdict is Verdict.STALE
    assert change.actionable
    assert 'linux-image-generic' in change.detail


def only_missing(*absent: str) -> Callable[..., str | None]:
    """A `shutil.which` where exactly these names are not on the machine.

    Named binaries rather than a shadow directory, because the three causes below
    turn on *which* of two binaries is missing and `fake_bin` keeps `/usr/bin`
    behind it — so a real `apt` on the runner and none on this Arch box decide the
    answer instead of the test.
    """
    return lambda name, *rest, **named: None if name in absent else f'/usr/bin/{name}'


UNMEASURED_CAUSES = (
    ('nothing-missing', (), ev.Unmeasured.DECLINED),
    ('the-manager', ('apt-get',), ev.Unmeasured.MANAGER_ABSENT),
    ('its-reader', ('apt',), ev.Unmeasured.READER_ABSENT),
)
"""Which binary is absent, and the cause that makes the row unmeasurable.

apt is the pair that shows the distinction: `INSTALL` names `apt-get` and
`OUTDATED` names `apt`. pacman is the case it was written for — `checkupdates` is
a different package from pacman — and cannot be exercised from this table because
this file's declaration is an apt machine.
"""


@pytest.mark.parametrize(('label', 'absent', 'reason'), UNMEASURED_CAUSES, ids=[case[0] for case in UNMEASURED_CAUSES])
def test_an_unmeasurable_manager_says_which_of_the_three_causes_it_is(
    label: str,
    absent: tuple[str, ...],
    reason: ev.Unmeasured,
    tmp_path: Path,
    fake_bin: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Three causes, three repairs: install the manager, install its reader, drop
    the flag. A reader handed the wrong one goes and does the wrong thing.

    Asserted as the member rather than the sentence. Reading `OUTDATED[name][0]` as
    the manager's own binary told every Arch box `no pacman on this machine` — on a
    machine pacman installed everything on — and no test could fail on it, because
    the only thing separating the causes was their English.
    """
    answers_empty(fake_bin, 'dpkg-query')
    monkeypatch.setattr(shutil, 'which', only_missing(*absent))
    behind(monkeypatch, {'apt': None})
    live = session(tmp_path, DECLARED, WORKSTATION)

    change = manager_rows(live)['apt']

    assert change.verdict is Verdict.UNKNOWN
    assert change.repair is Repair.NONE
    assert ev.by_currency(_row(live, 'apt'), {}).unmeasured is reason


def test_a_manager_whose_reader_ships_separately_names_the_package_to_install(
    tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """pacman's currency is `checkupdates`, which is `pacman-contrib` — so a machine
    with pacman and no reader needs a package name, not a manager name.

    The window is real and this branch opens it: `pacman-contrib` is declared here
    for the first time, so every Arch box prints this row until an apply lands it.
    """
    monkeypatch.setattr(shutil, 'which', only_missing('checkupdates'))

    evidence = ev._unmeasured_currency('pacman')

    assert evidence.unmeasured is ev.Unmeasured.READER_ABSENT
    assert 'pacman-contrib' in evidence.detail


def test_only_the_networked_currency_reads_wait_to_be_asked_for(monkeypatch: pytest.MonkeyPatch) -> None:
    """The gate is on the read, not on the row: a locally-answerable manager is
    measured whatever the caller said, and the ones that need a round trip are the
    only thing `--cached` buys back.

    brew is the local one here. Both Arch managers and apt refresh an index copy to
    answer, which is the round trip that put them in `NETWORKED`.
    """
    asked: list[str] = []

    def record(manager: str) -> frozenset[str]:
        asked.append(manager)
        return frozenset()

    monkeypatch.setattr(syspkg, 'outdated', record)

    assert ev.query('outdated:mas') is None
    assert ev.query('outdated:mas', refresh=True) == frozenset()
    assert ev.query('outdated:brew') == frozenset()
    assert asked == ['mas', 'brew']


def test_upgrading_a_manager_moves_everything_it_installed(tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Whole-manager rather than per package. Arch does not support partial
    upgrades at all, and elsewhere a declared package's dependencies are as much
    this repo's business as the package — `pacman -S <one>` leaves a machine in a
    combination nobody tests."""
    answers_empty(fake_bin, 'dpkg-query')
    behind(monkeypatch, {'apt': frozenset({'curl'})})
    ran: list[str] = []

    def record(manager: str, privilege: Privilege) -> providers.Result:
        ran.append(manager)
        return providers.Result(True, f'{manager} upgraded', kind=providers.Kind.APPLIED)

    monkeypatch.setattr(syspkg, 'upgrade', record)
    live = session(tmp_path, DECLARED, WORKSTATION)

    outcome = registry.BY_NAME['manager'].install(live, manager_rows(live)['apt'], _row(live, 'apt'), Privilege(offer=False))

    assert ran == ['apt']
    assert outcome.status is OutcomeStatus.DONE


def test_the_upgrade_runs_after_both_install_stages(tmp_path: Path, fake_bin: Path) -> None:
    """A manager that had to be bootstrapped cannot be asked what is behind until
    the stage that installs it has run — Homebrew on a fresh Mac, flatpak on a
    machine declaring its first app."""
    answers_empty(fake_bin, 'brew')
    declared = {'system_packages': [{'name': 'curl', 'brew': 'curl'}], 'macos_casks': [{'name': 'ghostty'}]}
    live = session(tmp_path, declared, MAC)

    stages = [item.stage for item in live.plan.for_resource('system')]

    assert stages == sorted(stages)
    assert max(item.stage for item in live.plan.for_resource('system') if item.provider == 'manager') is Stage.SYSTEM_UPGRADE


def _row(live: Session, manager: str):
    found = [item for item in live.plan.for_resource('system') if item.provider == 'manager' and item.name == manager]
    assert len(found) == 1, found
    return found[0]


def changes(live: Session):
    """Every change but the manager rows', which `unmeasured_currency` leaves UNKNOWN.

    Filtered here rather than at each call site: a manager row is planned beside
    whatever else the plan reached, so an unfiltered list would put an unrelated
    UNKNOWN in front of every batch assertion in this file.
    """
    observed = system.RESOURCE.observe(live, live.plan)
    return [change for change in system.RESOURCE.diff(live.plan, observed) if not change.item.startswith('manager/')]


def only_change(live: Session) -> Change:
    found = changes(live)
    assert len(found) == 1, found
    return found[0]


# ─────────────────────────────────────────────────────────────────────────────
# Preconditions: declared on the entry, checked live, never filtered from the plan
# ─────────────────────────────────────────────────────────────────────────────

ROCM = {'system_packages': [{'name': 'ollama', 'pacman': 'ollama-rocm', 'requires_amd_gpu': True}]}
ARCH_BOX: dict[str, Any] = {'machine': 'box', 'platform': 'archlinux', 'system_packages': 'workstation'}
EMPTY_INVENTORY = '#!/bin/sh\nexit 0\n'
"""A pacman that answers with nothing installed, so these read the declaration
rather than the Arch box running the suite — which really does have ollama-rocm."""


def test_a_rocm_build_is_not_installed_into_a_machine_with_no_amd_device(
    tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """12 GiB of compute stack, inert without the device. `BY_HAND` rather than a
    failure: attempting it records a failure for something this machine was never
    able to have, and the run then exits non-zero for a reason no change to this
    repo can fix."""
    monkeypatch.setattr(ev, 'have_amd_gpu', lambda: False)
    executable(fake_bin, 'pacman', EMPTY_INVENTORY)
    live = session(tmp_path, ROCM, ARCH_BOX)

    change = only_change(live)

    assert change.verdict is Verdict.MISSING
    assert change.repair is Repair.BY_HAND
    assert not change.actionable, 'apply must not hand this to pacman'


def test_the_same_entry_installs_normally_where_the_device_is_there(
    tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ev, 'have_amd_gpu', lambda: True)
    executable(fake_bin, 'pacman', EMPTY_INVENTORY)
    live = session(tmp_path, ROCM, ARCH_BOX)

    assert only_change(live).actionable


def test_the_row_stays_in_the_plan_either_way(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The difference between a precondition and a coordinate, and the reason this
    is not a seventh axis: `available()` reads coordinates and coordinates are what
    a *manifest* says a machine is, so filtering here would make `machines show
    archlinux-personal-workstation` describe whichever machine ran it."""
    monkeypatch.setattr(ev, 'have_amd_gpu', lambda: False)
    live = session(tmp_path, ROCM, ARCH_BOX)

    assert [item.address for item in payload(live)] == ['system/ollama']


def test_the_precondition_is_read_off_the_declaration_rather_than_the_name(
    tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An entry that does not declare it is unaffected, however it is spelled — the
    gate is `requires_amd_gpu`, not a substring of the package name."""
    monkeypatch.setattr(ev, 'have_amd_gpu', lambda: False)
    executable(fake_bin, 'pacman', EMPTY_INVENTORY)
    live = session(tmp_path, {'system_packages': [{'name': 'ollama', 'pacman': 'ollama-rocm'}]}, ARCH_BOX)

    assert only_change(live).actionable


def test_the_declared_rocm_entry_is_the_one_in_packages_yml() -> None:
    """Pinned against the real declaration, because the field is worth nothing if
    the entry it exists for stops carrying it."""
    ollama = catalog.load().find('system_packages', 'ollama')

    assert isinstance(ollama, catalog.SystemPackage)
    assert ollama.pacman == 'ollama-rocm'
    assert ollama.requires_amd_gpu, 'ollama-rocm pulls 12 GiB of ROCm and must not install without the device'


def test_the_probe_is_the_kernel_driver_node_rather_than_a_test_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """The flatpak rule: ask the real precondition. `DOTFILES_DOCKER_TEST` would be
    a test harness telling production code it is being tested, and would say
    nothing about a machine with an Nvidia card."""
    monkeypatch.setenv('DOTFILES_DOCKER_TEST', 'true')

    assert ev.have_amd_gpu() is ev.AMD_KFD.exists()


def test_an_unnamed_precondition_refuses_rather_than_passing(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fall-through decides what a *future* enum member means, and it must not
    mean "satisfied". Adding a `Precondition` is one line in the enum; a dispatch
    that absorbs it silently stops gating the install the precondition exists to
    gate. Asserted with a member this dispatch has never seen.
    """
    invented = 'a_precondition_nobody_wrote_a_branch_for'
    met = Preconditions(github_auth=True, amd_gpu=True)

    assert met.holds(invented) is False, 'an unnamed precondition must fail closed'
    assert met.holds(Precondition.NONE) is True, 'NONE answers True by being named'


# ─────────────────────────────────────────────────────────────────────────────
# A package the machine has and the declaration does not name
# ─────────────────────────────────────────────────────────────────────────────

MAC = {'machine': 'box', 'platform': 'macos', 'system_packages': 'workstation'}
MAC_CORE = {'machine': 'box', 'platform': 'macos', 'system_packages': 'core'}
"""A Mac subscribing to the base tier, which is the manifest that declines an entry.

`workstation` takes everything, so a machine on it can never reach `DECLINED` — the
first macOS manifest to subscribe at `core` is where that state becomes reachable.
"""

DECLARES_BAT = {'system_packages': [{'name': 'bat', 'brew': 'bat', 'apt': 'bat'}]}

BREW_LEAVES = """#!/bin/sh
case "$1" in
  --version) echo 'Homebrew 6.0.0' ;;
  leaves) printf '%s\\n' {names} ;;
esac
"""
"""A brew answering the two questions `syspkg.requested` asks, and nothing else.

`--version` is what `_answers` probes with, so a script without it is a brew that
is not there — a different assertion from the one the test using this makes.
"""


def chose(monkeypatch: pytest.MonkeyPatch, *names: str) -> None:
    """What brew reports as asked for by name.

    Replaces the module function rather than the subprocess, so nothing below
    `syspkg.requested` runs — not the command, not the tap-name parse. A test about
    either of those asks for `measures_requests` and a real `brew` on PATH.
    """
    monkeypatch.setattr(syspkg, 'requested', lambda manager: frozenset(names) if manager == 'brew' else None)


CONTROL = 'stylua'
"""A stray every declaration below leaves unexplained.

Carried by the tests whose claim is that something is *not* reported, because
`undeclared(live) == []` is also what a read that never ran returns. Asserting the
control survives beside the subject is what tells the two apart.
"""


def undeclared(live: Session) -> list[Change]:
    observed = system.RESOURCE.observe(live, live.plan)
    return [change for change in system.RESOURCE.diff(live.plan, observed) if change.verdict is Verdict.UNDECLARED]


def strays(live: Session) -> dict[str, system.Standing]:
    """Each reported package and why, which is the value the sentences are built from."""
    return {change.item: system.RESOURCE.observe(live, live.plan).undeclared[change.item].standing for change in undeclared(live)}


def test_a_package_nothing_declares_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The direction nothing else in this resource looks. `stylua` is named by the
    nvim config, declared in no section, and reached the Mac by hand — so a rebuilt
    machine gets nvim with its Lua formatter absent and every verb called it
    converged."""
    chose(monkeypatch, 'bat', CONTROL)
    live = session(tmp_path, DECLARES_BAT, MAC)

    assert strays(live) == {CONTROL: system.Standing.UNKNOWN}


def test_the_row_is_by_hand_so_apply_cannot_act_on_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`syspkg.REMOVE`'s rule: an uninstall inferred from what a declaration does
    not name takes a package off a machine on the strength of a typo. The row names
    the package and hands over the judgement."""
    chose(monkeypatch, CONTROL)
    live = session(tmp_path, DECLARES_BAT, MAC)
    change = undeclared(live)[0]

    assert change.repair is Repair.BY_HAND
    assert not change.actionable


def test_a_package_declared_under_its_manager_name_is_explained(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The entry is `nodejs` and brew installs it as `node`, so matching the entry
    name alone would report every renamed package undeclared."""
    chose(monkeypatch, 'node', CONTROL)
    live = session(tmp_path, {'system_packages': [{'name': 'nodejs', 'brew': 'node', 'apt': 'nodejs'}]}, MAC)

    assert 'node' not in strays(live)


def test_an_entry_naming_no_package_for_this_manager_is_its_own_answer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`zsh` reaches apt and pacman and names no brew package, so a Mac holding
    brew's zsh is neither a hand-install nor a declined subscription. Under the bool
    this replaced it reported that the machine does not subscribe, when the machine
    subscribes and the entry simply cannot install this copy."""
    chose(monkeypatch, 'zsh', CONTROL)
    live = session(tmp_path, {'system_packages': [{'name': 'zsh', 'apt': 'zsh', 'pacman': 'zsh'}]}, MAC)

    assert strays(live) == {'zsh': system.Standing.OTHER_MANAGERS, CONTROL: system.Standing.UNKNOWN}


NTFY = {'github_releases': [{'name': 'ntfy', 'repo': 'binwiederhier/ntfy'}]}


def test_a_package_declared_through_another_mechanism_is_explained(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`ntfy` is a `github_releases` entry and brew has a copy of it too. That is a
    duplicate, which `packages._shadowing` reports — reporting it here as well
    would tell someone to uninstall the thing they declared."""
    chose(monkeypatch, 'ntfy', CONTROL)
    live = session(tmp_path, NTFY, {**MAC, 'github_releases': ['ntfy']})

    assert 'ntfy' not in strays(live)


def test_a_package_the_file_carries_and_this_machine_does_not_is_not_called_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The file carries `ntfy` and this manifest does not ask for it, so the machine
    holds something the declaration knows about. Not `UNKNOWN`, which would send the
    reader to a file that carries it.

    `OTHER_MANAGERS` rather than `DECLINED`, and the release entry is why: it
    declares no brew package at all, so subscribing to it would not make brew's copy
    the declared one. `brew uninstall` is the right pointer either way.
    """
    chose(monkeypatch, 'ntfy', CONTROL)
    live = session(tmp_path, NTFY, MAC)

    assert strays(live) == {'ntfy': system.Standing.OTHER_MANAGERS, CONTROL: system.Standing.UNKNOWN}


def test_a_renamed_entry_the_manifest_declines_is_not_called_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The catalog side is spelled the way the plan side is. Built from `entry.name`
    alone, brew's `sevenzip` was unknown to one half of the comparison and declared
    to the other, and the row told a reader `packages.yml` does not carry an entry
    sitting in it."""
    chose(monkeypatch, 'sevenzip', CONTROL)
    live = session(tmp_path, {'system_packages': [{'name': '7zip', 'brew': 'sevenzip', 'apt': 'p7zip-full'}]}, MAC_CORE)

    assert strays(live) == {'sevenzip': system.Standing.DECLINED, CONTROL: system.Standing.UNKNOWN}


def test_a_manager_that_cannot_be_asked_is_not_a_manager_that_chose_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """None and an empty set are different answers, and `syspkg.requested`'s
    docstring says so. Nothing downstream distinguished them, so the claim was
    unpinned: `_undeclared_packages` skipped a None and iterated an empty set to the
    same result. `asked` is where the difference has to show."""
    silent = session(tmp_path, DECLARES_BAT, MAC)
    monkeypatch.setattr(syspkg, 'requested', lambda manager: frozenset())
    answered = session(tmp_path, DECLARES_BAT, MAC)

    assert undeclared(silent) == []
    assert undeclared(answered) == []
    assert f'{ev.REQUESTED_PREFIX}brew' not in silent.inventories.asked | answered.inventories.asked


def test_a_narrowed_run_reports_nothing_undeclared(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`--package` narrows the declaration to one entry, so everything else the
    machine holds falls outside the declared set. Asking the question against a
    plan that is deliberately partial answers it wrong."""
    chose(monkeypatch, 'bat', CONTROL)
    # `dc.replace` rather than an override on `session`, whose own second argument
    # is named `packages` and is the declaration rather than the narrowing.
    live = dc.replace(session(tmp_path, DECLARES_BAT, MAC), packages=frozenset({'bat'}))

    assert undeclared(live) == []


def test_a_stage_ceiling_does_not_invent_strays(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The subtraction is measured against the whole declaration, never the plan
    this resource was handed. `--through` narrows by stage across every resource, so
    a ceiling that drops the release entries reported `ntfy` as a stray — the case
    the test two above pins and the body promises."""
    chose(monkeypatch, 'ntfy', CONTROL)
    live = session(tmp_path, NTFY, {**MAC, 'github_releases': ['ntfy']})
    capped = dc.replace(live.plan, items=tuple(item for item in live.plan.items if item.resource == 'system'))

    observed = system.RESOURCE.observe(live, capped)

    assert 'ntfy' not in observed.undeclared
    assert CONTROL in observed.undeclared


@pytest.mark.measures_requests
def test_a_tap_qualified_name_is_matched_against_the_declared_short_one(tmp_path: Path, fake_bin: Path) -> None:
    """End to end through the real subprocess, because the command and the parse
    are one thing. `brew leaves` prints `felixkratz/formulae/borders` while
    `brew list --formula` prints `borders`, so the long form measured against a
    declaration naming the short one is a finding on every run, forever.

    `measures_requests` is what lets this reach `syspkg.requested` at all. Without
    it the autouse stub answers first, and deleting the parse under test leaves the
    whole suite green.
    """
    executable(fake_bin, 'brew', BREW_LEAVES.format(names=f'felixkratz/formulae/borders {CONTROL}'))
    live = session(tmp_path, {'system_packages': [{'name': 'borders', 'brew': 'borders'}]}, MAC)

    assert strays(live) == {CONTROL: system.Standing.UNKNOWN}


def test_the_undeclared_rows_are_kept_out_of_the_declared_package_count(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`summary` counts how much of the declaration is installed, and these are the
    opposite reading. Folded in, a machine carrying eight of them reports a total
    that counts the packages it is reporting as undeclared."""
    chose(monkeypatch, 'bat', CONTROL)
    live = session(tmp_path, DECLARES_BAT, MAC)
    observed = system.RESOURCE.observe(live, live.plan)

    assert CONTROL in observed.undeclared
    assert CONTROL not in observed.packages
    assert len(observed.packages) == 1


def test_every_standing_has_a_finding_and_an_advice_sentence() -> None:
    """The two tables are dispatch over a closed vocabulary, so a member added
    without a sentence has to fail here rather than at whichever machine first
    reaches it."""
    assert set(system.FOUND) == set(system.Standing)
    assert set(system.ADVICE) == set(system.Standing)


def test_the_requested_read_covers_brew_and_nothing_else() -> None:
    """`REQUESTED`'s name claims a category and its docstring holds the boundary:
    only a manager whose "installed on request" is comparable to a declaration
    belongs. pacman and apt own the base system, and on the fleet's Arch box 40 of
    123 explicitly installed packages appear nowhere in `packages.yml` — `base`,
    `linux` and `linux-firmware` among them. An addition fails here rather than
    shipping those rows."""
    assert set(syspkg.REQUESTED) == {'brew'}
