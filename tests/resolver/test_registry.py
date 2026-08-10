"""One object per mechanism, and the invariants that used to be five tables.

Nothing here touches a machine. The registry is a description — which section a
provider plans from, how it tells whether one of its items is present, whether
repairing one escalates — and the whole point of collapsing the tables is that
those three answers can no longer be given by three files that disagree.
"""

from __future__ import annotations

import pytest

from dotfiles import catalog
from dotfiles import evidence as ev
from dotfiles import registry
from dotfiles import vocabulary
from dotfiles.resolve import DesiredItem
from dotfiles.resolve import Precondition
from dotfiles.resolve import Reason
from dotfiles.resolve import Stage
from dotfiles.resources import Verdict


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

    Go could too, but `.zshenv`, `install/tool-path.sh` and `apply.TOOL_PATH_DIRS`
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
