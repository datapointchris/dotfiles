"""What counts as evidence that a declared tool is installed.

Every seam here is a real knob the code already honours — `PATH`, `UV_TOOL_DIR`,
the package-manager binaries on `PATH` — so nothing in `src/dotfiles/` is
patched. `PATH` keeps `/usr/bin:/bin`, with the tools under test shadowed by name
in a fake bin dir: without the real ones, `git` and `bash` raise
FileNotFoundError and the fixture cannot run its own helpers.

These replace nine subprocess tests that drove `packages missing` against a
synthetic tree. The question is the same; the answer is now a function call.
"""

from __future__ import annotations

import dataclasses as dc
import datetime as dt
import stat
from pathlib import Path
from typing import Any

import pytest
import yaml

from dotfiles import evidence as ev
from dotfiles import releases
from dotfiles.privilege import Privilege
from dotfiles.providers import cargo
from dotfiles.providers import custom
from dotfiles.providers import ghrelease
from dotfiles.providers import gotool
from dotfiles.resources import Change
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.resources import packages
from dotfiles.session import Session


def executable(directory: Path, name: str, script: str = '#!/bin/sh\nexit 0\n') -> Path:
    """See `_executable` in tests/conftest.py for why this is copied rather than imported."""
    target = directory / name
    target.write_text(script)
    target.chmod(target.stat().st_mode | stat.S_IEXEC)
    return target


@pytest.fixture
def uv_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / 'uv-tools'
    directory.mkdir()
    monkeypatch.setenv('UV_TOOL_DIR', str(directory))
    return directory


def session(tmp_path: Path, packages_yml: dict[str, Any], manifest: dict[str, Any]) -> Session:
    repo = tmp_path / 'repo'
    (repo / 'install' / 'manifests').mkdir(parents=True, exist_ok=True)
    (repo / 'install' / 'packages.yml').write_text(yaml.safe_dump(packages_yml, sort_keys=False))
    (repo / 'install' / 'flags.yml').write_text('{}')
    (repo / 'install' / 'manifests' / 'box.yml').write_text(yaml.safe_dump(manifest, sort_keys=False))
    home = tmp_path / 'home'
    home.mkdir(exist_ok=True)
    return Session(machine_name='box', repo=repo, home=home)


def verdicts(live: Session) -> dict[str, Verdict]:
    observed = packages.RESOURCE.observe(live, live.plan)
    return {item.address: observed.evidence[item.address].verdict for item in live.plan.for_resource('packages')}


def changes(live: Session) -> tuple:
    return packages.RESOURCE.diff(live.plan, packages.RESOURCE.observe(live, live.plan))


GO_TOOL = {'go_tools': [{'name': 'task', 'package': 'github.com/go-task/task/v3/cmd/task'}]}
DECLARES_TASK = {'machine': 'box', 'platform': 'linux', 'go_tools': ['task']}


# ─────────────────────────────────────────────────────────────────────────────
# A binary on PATH
# ─────────────────────────────────────────────────────────────────────────────


def test_a_declared_tool_that_is_absent_is_missing(tmp_path: Path, fake_bin: Path) -> None:
    live = session(tmp_path, GO_TOOL, DECLARES_TASK)

    assert verdicts(live) == {'go/task': Verdict.MISSING}


def test_a_declared_tool_on_path_is_matched(tmp_path: Path, fake_bin: Path) -> None:
    executable(fake_bin, 'task')
    live = session(tmp_path, GO_TOOL, DECLARES_TASK)

    assert verdicts(live) == {'go/task': Verdict.MATCHED}


def test_an_entry_the_manifest_does_not_declare_is_not_looked_for(tmp_path: Path, fake_bin: Path) -> None:
    declared = {'go_tools': [{'name': 'task', 'package': 'x'}, {'name': 'gdu', 'package': 'y'}]}
    live = session(tmp_path, declared, DECLARES_TASK)

    assert set(verdicts(live)) == {'go/task'}


def test_the_command_field_is_what_gets_looked_up(tmp_path: Path, fake_bin: Path) -> None:
    """ripgrep ships rg, `@taplo/cli` ships taplo. Without this an installed tool
    reads as missing forever, which is the failure mode that makes a checker get
    ignored."""
    executable(fake_bin, 'rg')
    declared = {'cargo_packages': [{'name': 'ripgrep', 'command': 'rg'}]}
    live = session(tmp_path, declared, {'machine': 'box', 'platform': 'linux', 'cargo_packages': ['ripgrep']})

    assert verdicts(live) == {'cargo/ripgrep': Verdict.MATCHED}


# ─────────────────────────────────────────────────────────────────────────────
# A declared path, for an entry that installs no binary
# ─────────────────────────────────────────────────────────────────────────────


def test_a_declared_install_path_is_the_evidence(tmp_path: Path, fake_bin: Path) -> None:
    """`bashselfupdate` is a sourced library: the checkout is the only evidence."""
    checkout = tmp_path / 'lib' / 'bashselfupdate'
    checkout.mkdir(parents=True)
    declared = {'custom_installers': [{'name': 'bashselfupdate', 'description': 'lib', 'installed_path': str(checkout)}]}
    live = session(tmp_path, declared, {'machine': 'box', 'platform': 'linux', 'custom_installers': ['bashselfupdate']})

    assert verdicts(live) == {'custom/bashselfupdate': Verdict.MATCHED}


def test_a_declared_install_path_that_is_absent_is_missing(tmp_path: Path, fake_bin: Path) -> None:
    declared = {'custom_installers': [{'name': 'bashselfupdate', 'description': 'lib', 'installed_path': str(tmp_path / 'nowhere')}]}
    live = session(tmp_path, declared, {'machine': 'box', 'platform': 'linux', 'custom_installers': ['bashselfupdate']})

    assert verdicts(live) == {'custom/bashselfupdate': Verdict.MISSING}


# ─────────────────────────────────────────────────────────────────────────────
# uv tools
# ─────────────────────────────────────────────────────────────────────────────


def test_a_uv_tool_directory_counts_as_installed(tmp_path: Path, fake_bin: Path, uv_tools: Path) -> None:
    (uv_tools / 'numpy').mkdir()
    declared = {'uv_tools': {'science': [{'name': 'numpy', 'library_only': True}]}}
    live = session(tmp_path, declared, {'machine': 'box', 'platform': 'linux', 'uv_tools': ['numpy']})

    assert verdicts(live) == {'uv/numpy': Verdict.MATCHED}


def test_a_library_only_tool_with_no_directory_is_missing_not_unknown(tmp_path: Path, fake_bin: Path, uv_tools: Path) -> None:
    """It installs no console script, so PATH can never answer — but the directory
    can, which is why this is a measured verdict rather than UNKNOWN."""
    declared = {'uv_tools': {'science': [{'name': 'numpy', 'library_only': True}]}}
    live = session(tmp_path, declared, {'machine': 'box', 'platform': 'linux', 'uv_tools': ['numpy']})

    assert verdicts(live) == {'uv/numpy': Verdict.MISSING}


def test_a_uv_tool_on_path_without_its_directory_still_counts(tmp_path: Path, fake_bin: Path, uv_tools: Path) -> None:
    """A tool installed some other way is still installed. The check reports the
    machine, not the mechanism."""
    executable(fake_bin, 'ruff')
    declared = {'uv_tools': {'lint': [{'name': 'ruff'}]}}
    live = session(tmp_path, declared, {'machine': 'box', 'platform': 'linux', 'uv_tools': ['ruff']})

    assert verdicts(live) == {'uv/ruff': Verdict.MATCHED}


# ─────────────────────────────────────────────────────────────────────────────
# Preconditions and what apply can act on
# ─────────────────────────────────────────────────────────────────────────────


def test_a_private_repo_without_credentials_is_not_apply_s_to_fix(tmp_path: Path, fake_bin: Path, uv_tools: Path, monkeypatch) -> None:
    """Attempting it records a failure for something the machine was never able to
    have, and the run exits non-zero for a reason no change to this repo can fix."""
    monkeypatch.delenv('GITHUB_TOKEN', raising=False)
    declared = {'git_uv_tools': [{'name': 'safekeep', 'repo': 'https://github.com/datapointchris/safekeep', 'requires_github_auth': True}]}
    live = session(tmp_path, declared, {'machine': 'box', 'platform': 'linux', 'git_uv_tools': ['safekeep']})

    found = changes(live)

    assert found[0].verdict is Verdict.MISSING
    # `gh` may be logged in on the machine running the suite, in which case this
    # is repairable — the assertion is that the two states are told apart at all.
    expected = Repair.AUTOMATIC if ev.have_github_credentials() else Repair.BY_HAND
    assert found[0].repair is expected


def test_a_private_repo_with_a_token_is_repairable(tmp_path: Path, fake_bin: Path, uv_tools: Path, monkeypatch) -> None:
    monkeypatch.setenv('GITHUB_TOKEN', 'ghp_pretend')
    declared = {'git_uv_tools': [{'name': 'safekeep', 'repo': 'https://github.com/datapointchris/safekeep', 'requires_github_auth': True}]}
    live = session(tmp_path, declared, {'machine': 'box', 'platform': 'linux', 'git_uv_tools': ['safekeep']})

    assert changes(live)[0].repair is Repair.AUTOMATIC


# ─────────────────────────────────────────────────────────────────────────────
# Currency: a release that is installed but no longer the one declared
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def release_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`$XDG_CACHE_HOME` is the real knob, so pointing it here patches nothing."""
    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path / 'cache'))
    return tmp_path / 'cache' / 'dotfiles' / 'releases.json'


def cached(path: Path, entries: dict[str, str], age: dt.timedelta = dt.timedelta(0)) -> None:
    checked = dt.datetime.now(dt.UTC) - age
    releases.save({key: releases.Cached(version, checked) for key, version in entries.items()}, path)


LAZYGIT = {'github_releases': [{'name': 'lazygit', 'repo': 'jesseduffield/lazygit'}]}
DECLARES_LAZYGIT = {'machine': 'box', 'platform': 'linux', 'github_releases': ['lazygit']}


def reporting(directory: Path, name: str, version: str) -> Path:
    return executable(directory, name, f'#!/bin/sh\nprintf "%s\\n" "{version}"\n')


def test_a_release_behind_the_latest_is_stale(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    reporting(fake_bin, 'lazygit', 'lazygit version 0.44.0')
    cached(release_cache, {'jesseduffield/lazygit': 'v0.45.0'})
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)

    found = changes(live)

    assert [(change.item, change.verdict) for change in found] == [('ghrelease/lazygit', Verdict.STALE)]


def test_a_release_at_the_latest_reports_nothing(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    reporting(fake_bin, 'lazygit', 'lazygit version 0.45.0')
    cached(release_cache, {'jesseduffield/lazygit': 'v0.45.0'})
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)

    assert changes(live) == ()


def test_a_release_ahead_of_the_cache_is_not_stale(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    """The cache is allowed to be behind reality. A tool newer than the last
    answer is not out of date; it is the cache that is."""
    reporting(fake_bin, 'lazygit', 'lazygit version 0.46.0')
    cached(release_cache, {'jesseduffield/lazygit': 'v0.45.0'})
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)

    assert changes(live) == ()


def test_an_expired_cache_reports_unknown_rather_than_current(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    """The rule the cache exists to keep: it may be out of date, it may not lie."""
    reporting(fake_bin, 'lazygit', 'lazygit version 0.44.0')
    cached(release_cache, {'jesseduffield/lazygit': 'v0.45.0'}, age=releases.TTL + dt.timedelta(hours=1))
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)

    found = changes(live)

    assert [(change.item, change.verdict, change.repair) for change in found] == [('ghrelease/lazygit', Verdict.UNKNOWN, Repair.NONE)]


def test_no_cache_at_all_reports_unknown(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    reporting(fake_bin, 'lazygit', 'lazygit version 0.44.0')
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)

    assert [change.verdict for change in changes(live)] == [Verdict.UNKNOWN]


def test_a_tool_taking_the_version_subcommand_is_still_measured(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    """terrascan rejects the flag and takes the subcommand. Probing only the flag
    reported an installed, current tool as unmeasurable."""
    executable(fake_bin, 'lazygit', '#!/bin/sh\n[ "$1" = version ] || exit 1\nprintf "version: v0.45.0\\n"\n')
    cached(release_cache, {'jesseduffield/lazygit': 'v0.45.0'})
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)

    assert changes(live) == ()


def test_a_binary_that_answers_neither_probe_is_unknown(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    executable(fake_bin, 'lazygit', '#!/bin/sh\nexit 1\n')
    cached(release_cache, {'jesseduffield/lazygit': 'v0.45.0'})
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)

    found = changes(live)

    assert [(change.verdict, change.repair) for change in found] == [(Verdict.UNKNOWN, Repair.NONE)]


def test_an_unparseable_version_is_unknown_rather_than_behind(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    """Reporting it behind would send `apply` to reinstall a tool nothing
    established was wrong."""
    reporting(fake_bin, 'lazygit', 'built from source')
    cached(release_cache, {'jesseduffield/lazygit': 'v0.45.0'})
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)

    assert [change.verdict for change in changes(live)] == [Verdict.UNKNOWN]


def test_a_pinned_release_is_checked_without_any_cache(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    """A pin names the release, so the declaration is the whole answer. This is
    what keeps a pinned tool checkable on a machine that never reaches GitHub."""
    reporting(fake_bin, 'lazygit', 'lazygit version 0.44.0')
    declared = {'github_releases': [{'name': 'lazygit', 'repo': 'jesseduffield/lazygit', 'version': '0.45.0'}]}
    live = session(tmp_path, declared, DECLARES_LAZYGIT)

    found = changes(live)

    assert [(change.item, change.verdict) for change in found] == [('ghrelease/lazygit', Verdict.STALE)]


def test_a_release_at_its_pin_reports_nothing(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    reporting(fake_bin, 'lazygit', 'lazygit version 0.45.0')
    declared = {'github_releases': [{'name': 'lazygit', 'repo': 'jesseduffield/lazygit', 'version': '0.45.0'}]}
    live = session(tmp_path, declared, DECLARES_LAZYGIT)

    assert changes(live) == ()


def test_a_missing_release_is_missing_rather_than_unmeasured(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    """Presence is asked first. A tool that is not there has no currency to have."""
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)

    assert [change.verdict for change in changes(live)] == [Verdict.MISSING]


def test_a_registry_installed_tool_is_never_asked_about_currency(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    """apt and npm upgrade on their own schedule, and an entry naming no repo has
    no upstream to ask. Either way it is a question nothing here owns."""
    executable(fake_bin, 'task')
    live = session(tmp_path, GO_TOOL, DECLARES_TASK)

    assert changes(live) == ()


CARGO_CURRENCY = {'cargo_packages': [{'name': 'fd-find', 'command': 'fd', 'github_repo': 'sharkdp/fd'}]}
DECLARES_FD = {'machine': 'box', 'platform': 'linux', 'cargo_packages': ['fd-find']}


def test_a_cargo_package_behind_its_release_is_stale(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    """`cargo binstall` is the upgrade, so being behind the repo the declaration
    names is drift rather than someone else's schedule. Without this, converting
    the phase would have silently removed the only thing that moved these."""
    reporting(fake_bin, 'fd', 'fd 10.2.0')
    cached(release_cache, {'sharkdp/fd': 'v10.4.2'})
    live = session(tmp_path, CARGO_CURRENCY, DECLARES_FD)

    assert [(change.item, change.verdict) for change in changes(live)] == [('cargo/fd-find', Verdict.STALE)]


def test_an_entry_that_reports_no_version_is_never_run(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    """The probe is not a read for every binary. `webviewrs` opens its first
    positional argument as a URL, so asking it for a version opened a window
    titled `version` and blocked the plan on the webview's event loop — three
    times, before a declaration could say so.

    Asserted by making the probe leave a trace rather than by counting calls: a
    test that only checked the verdict would pass while still running the thing.
    """
    ran = tmp_path / 'ran'
    executable(fake_bin, 'webviewrs', f'#!/bin/sh\ntouch "{ran}"\nprintf "1.0.0\\n"\n')
    cached(release_cache, {'datapointchris/webviewrs': 'v2.0.0'})
    declared = {'cargo_packages': [{'name': 'webviewrs', 'github_repo': 'datapointchris/webviewrs', 'reports_version': False}]}
    live = session(tmp_path, declared, {'machine': 'box', 'platform': 'linux', 'cargo_packages': ['webviewrs']})

    assert changes(live) == ()
    assert not ran.exists()


def test_a_check_that_may_not_refresh_never_reaches_the_network(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    """`check` runs at a prompt and in a pre-commit hook. The default must not
    spend one API call per declared release."""
    reporting(fake_bin, 'lazygit', 'lazygit version 0.44.0')
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)

    observed = packages.RESOURCE.observe(live, live.plan)

    assert observed.consulted_network is False


def test_offline_never_refreshes_however_it_was_asked(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    """`--refresh` means "spend the network on being current", and there is none."""
    reporting(fake_bin, 'lazygit', 'lazygit version 0.44.0')
    live = dc.replace(session(tmp_path, LAZYGIT, DECLARES_LAZYGIT), refresh=True, offline=True)

    observed = packages.RESOURCE.observe(live, live.plan)

    assert observed.consulted_network is False


# ─────────────────────────────────────────────────────────────────────────────
# Which changes this resource can actually perform
# ─────────────────────────────────────────────────────────────────────────────
#
# `perform` is converting provider by provider, so what it refuses matters as
# much as what it does: a resource that silently did nothing would leave `apply`
# reporting a converged machine it never touched.


@pytest.fixture
def installs(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record what would be installed, instead of reaching GitHub, a vendor or the
    Go proxy.

    Every converted provider is patched here, not only the ones a test names. One
    that is missed does not fail — it *installs*, on the machine running the
    suite: this fixture covered two providers when a third converted, and the
    resulting run rebuilt a Go tool out of proxy.golang.org and wrote it into
    `~/go/bin`.
    """
    attempted: list[str] = []

    def record(entry, target=None, *, offline=False):
        attempted.append(entry.name)
        return ghrelease.Result(True, f'{entry.name} installed')

    monkeypatch.setattr(ghrelease, 'install', record)
    monkeypatch.setattr(custom, 'install', record)
    monkeypatch.setattr(gotool, 'install', record)
    monkeypatch.setattr(cargo, 'install', record)
    return attempted


def only_change(live: Session) -> Change:
    found = changes(live)
    assert len(found) == 1, f'expected one change, got {[change.verdict for change in found]}'
    return found[0]


def test_a_missing_release_is_installed(
    tmp_path: Path, fake_bin: Path, release_cache: Path, installs: list[str], unprivileged: Privilege
) -> None:
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)

    outcome = packages.RESOURCE.perform(live, only_change(live), unprivileged)

    assert outcome.status is OutcomeStatus.DONE
    assert installs == ['lazygit']


def test_a_stale_release_is_upgraded_rather_than_reported(
    tmp_path: Path, fake_bin: Path, release_cache: Path, installs: list[str], unprivileged: Privilege
) -> None:
    """The verdict the phase registry cannot act on, because a phase has no plan
    to read it from."""
    cached(release_cache, {'jesseduffield/lazygit': 'v0.45.0'})
    reporting(fake_bin, 'lazygit', 'lazygit version 0.44.0')
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)

    change = only_change(live)
    assert change.verdict is Verdict.STALE
    assert packages.RESOURCE.perform(live, change, unprivileged).status is OutcomeStatus.DONE
    assert installs == ['lazygit']


def test_a_release_that_arrived_since_the_report_is_skipped(
    tmp_path: Path, fake_bin: Path, installs: list[str], unprivileged: Privilege
) -> None:
    """`observe` ran before the report was printed and before any earlier stage
    installed anything. Reinstalling over what turned up would replace a binary
    nobody asked about with whatever upstream calls latest now."""
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)
    change = only_change(live)
    executable(fake_bin, 'lazygit')

    outcome = packages.RESOURCE.perform(live, change, unprivileged)

    assert outcome.status is OutcomeStatus.SKIPPED
    assert installs == []


# Names no machine can have, because `fake_bin` keeps /usr/bin behind it: a real
# package would read as installed on whichever box happens to have it, which is the
# hazard that fixture's docstring names.
CARGO_PACKAGE = {'cargo_packages': [{'name': 'unbuilt-crate', 'command': 'unbuilt-crate'}]}
DECLARES_CARGO = {'machine': 'box', 'platform': 'linux', 'cargo_packages': ['unbuilt-crate']}

NPM_GLOBAL = {'npm_globals': {'linters': [{'name': 'unpublished-linter'}]}}
DECLARES_NPM = {'machine': 'box', 'platform': 'linux', 'npm_globals': ['unpublished-linter']}


def test_a_provider_that_has_not_converted_is_refused_not_ignored(
    tmp_path: Path, fake_bin: Path, installs: list[str], unprivileged: Privilege
) -> None:
    live = session(tmp_path, NPM_GLOBAL, DECLARES_NPM)

    outcome = packages.RESOURCE.perform(live, only_change(live), unprivileged)

    assert outcome.status is OutcomeStatus.REFUSED
    assert installs == []


def test_a_missing_cargo_package_is_installed_by_its_provider(
    tmp_path: Path, fake_bin: Path, installs: list[str], unprivileged: Privilege
) -> None:
    live = session(tmp_path, CARGO_PACKAGE, DECLARES_CARGO)

    outcome = packages.RESOURCE.perform(live, only_change(live), unprivileged)

    assert outcome.status is OutcomeStatus.DONE
    assert installs == ['unbuilt-crate']


def test_a_missing_go_tool_is_installed_by_its_provider(
    tmp_path: Path, fake_bin: Path, installs: list[str], unprivileged: Privilege
) -> None:
    """Through the same function the phase calls, so the two front doors cannot
    install one tool differently."""
    live = session(tmp_path, GO_TOOL, DECLARES_TASK)

    outcome = packages.RESOURCE.perform(live, only_change(live), unprivileged)

    assert outcome.status is OutcomeStatus.DONE
    assert installs == ['task']


DECLARES_THEME = {'machine': 'box', 'platform': 'linux', 'custom_installers': ['theme']}
THEME = {'custom_installers': [{'name': 'theme', 'description': 'theme manager', 'repo': 'datapointchris/theme'}]}


def test_a_missing_custom_installer_runs_its_own_function(
    tmp_path: Path, fake_bin: Path, installs: list[str], unprivileged: Privilege
) -> None:
    """Through the same function the phase calls, so the two front doors cannot
    install one tool differently."""
    live = session(tmp_path, THEME, DECLARES_THEME)

    outcome = packages.RESOURCE.perform(live, only_change(live), unprivileged)

    assert outcome.status is OutcomeStatus.DONE
    assert installs == ['theme']


def test_a_custom_installer_that_arrived_since_the_report_is_skipped(
    tmp_path: Path, fake_bin: Path, installs: list[str], unprivileged: Privilege
) -> None:
    live = session(tmp_path, THEME, DECLARES_THEME)
    change = only_change(live)
    executable(fake_bin, 'theme')

    assert packages.RESOURCE.perform(live, change, unprivileged).status is OutcomeStatus.SKIPPED
    assert installs == []
