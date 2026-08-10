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
import os
import stat
from pathlib import Path
from typing import Any

import pytest
import yaml

from dotfiles import evidence as ev
from dotfiles import paths
from dotfiles import releases
from dotfiles.privilege import Privilege
from dotfiles.providers import cargo
from dotfiles.providers import custom
from dotfiles.providers import ghrelease
from dotfiles.providers import gotool
from dotfiles.providers import npm
from dotfiles.providers import uvtool
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


@pytest.mark.skipif(os.geteuid() == 0, reason='root is refused nothing, so the entry under test stays readable')
def test_an_unreadable_entry_does_not_take_out_the_whole_scan(tmp_path: Path) -> None:
    """macOS ships `/usr/sbin/weakpass_edit` pointing into SIP-protected
    `authserver/`, so following it is denied. One such entry made the whole
    `packages` resource report "could not be examined" on both Macs."""
    forbidden = tmp_path / 'forbidden'
    forbidden.mkdir()
    (forbidden / 'target').write_text('')
    searched = tmp_path / 'bin'
    searched.mkdir()
    executable(searched, 'reachable')
    (searched / 'denied').symlink_to(forbidden / 'target')
    forbidden.chmod(0o000)

    try:
        found = ev.executables_on_path(tmp_path / 'checkout', search=str(searched))
    finally:
        forbidden.chmod(0o700)

    assert 'reachable' in found


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


def test_a_public_tool_beside_a_blocked_private_one_is_still_offered(
    tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The half that is easy to lose. The install phase this replaced dropped the
    private names out of its list and warned, which worked; skipping the section
    wholesale would trade one wrong answer for a worse one, and a per-row `repair`
    cannot make that mistake at all.
    """
    monkeypatch.setattr(ev, 'have_github_credentials', lambda: False)
    declared = {
        'github_releases': [
            {'name': 'lazygit', 'repo': 'jesseduffield/lazygit'},
            {'name': 'learning', 'repo': 'datapointchris/learning', 'requires_github_auth': True},
        ]
    }
    live = session(tmp_path, declared, {'machine': 'box', 'platform': 'linux', 'github_releases': ['lazygit', 'learning']})

    assert {change.item: change.repair for change in changes(live)} == {
        'ghrelease/lazygit': Repair.AUTOMATIC,
        'ghrelease/learning': Repair.BY_HAND,
    }


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


def test_a_tool_ahead_of_a_measured_release_is_stale(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    """The `ifiles` case: a repo that went to 2.x and back to 1.x strands whatever
    installed the high version, and `at_least` calls it current forever. Measured
    against a figure established this run, above the newest release is drift —
    there is no install anything here can perform that produces it."""
    reporting(fake_bin, 'lazygit', 'lazygit version 2.10.0')
    cached(release_cache, {'jesseduffield/lazygit': 'v0.45.0'})
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)
    measured = dc.replace(packages.RESOURCE.observe(live, live.plan), consulted_network=True)
    item = live.plan.for_resource('packages')[0]

    found = packages.currency_of(item, measured)

    assert [(change.verdict, change.observed) for change in found] == [(Verdict.STALE, 'lazygit version 2.10.0')]
    assert 'ahead of v0.45.0' in found[0].detail


def test_a_tool_ahead_of_its_bundle_is_stale(tmp_path: Path, fake_bin: Path, release_cache: Path, monkeypatch) -> None:
    """A staged bundle holds the bytes a fresh install would use, so it is as
    authoritative as a refresh — which is what carries this to the firewalled
    machine, where the stranded version is and the network is not."""
    reporting(fake_bin, 'lazygit', 'lazygit version 2.10.0')
    staged_bundle(tmp_path, monkeypatch, {'lazygit': '0.45.0'})
    live = dc.replace(session(tmp_path, LAZYGIT, DECLARES_LAZYGIT), offline=True)

    assert [(change.item, change.verdict) for change in changes(live)] == [('ghrelease/lazygit', Verdict.STALE)]


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


MOUNT_S3 = {
    'custom_installers': [
        {
            'name': 'mount-s3',
            'description': 'mountpoint for S3',
            'repo': 'awslabs/mountpoint-s3',
            'release_tag_prefix': 'mountpoint-s3-',
        }
    ]
}
DECLARES_MOUNT_S3 = {'machine': 'box', 'platform': 'linux', 'custom_installers': ['mount-s3']}

AWSCLI = {
    'custom_installers': [
        {
            'name': 'awscli',
            'command': 'aws',
            'description': "AWS's CLI",
            'repo': 'aws/aws-cli',
            'version_source': 'tags',
        }
    ]
}
DECLARES_AWSCLI = {'machine': 'box', 'platform': 'linux', 'custom_installers': ['awscli']}

NO_REPO = {'custom_installers': [{'name': 'claude-code', 'command': 'claude', 'description': 'self-updating'}]}
DECLARES_NO_REPO = {'machine': 'box', 'platform': 'linux', 'custom_installers': ['claude-code']}


def test_a_custom_installer_behind_its_repo_is_stale(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    """A version behind is a verdict rather than something a vendor script decides
    privately, which is what lets the engine act on it — and the tag prefix comes
    off the declaration, so the repo name is written once."""
    reporting(fake_bin, 'mount-s3', 'mount-s3 1.22.0')
    cached(release_cache, {'awslabs/mountpoint-s3#mountpoint-s3-': 'mountpoint-s3-1.23.0'})
    live = session(tmp_path, MOUNT_S3, DECLARES_MOUNT_S3)

    assert [(change.item, change.verdict) for change in changes(live)] == [('custom/mount-s3', Verdict.STALE)]


def test_a_custom_installer_at_its_repos_latest_reports_nothing(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    reporting(fake_bin, 'mount-s3', 'mount-s3 1.23.0')
    cached(release_cache, {'awslabs/mountpoint-s3#mountpoint-s3-': 'mountpoint-s3-1.23.0'})
    live = session(tmp_path, MOUNT_S3, DECLARES_MOUNT_S3)

    assert changes(live) == ()


def test_a_custom_installer_naming_no_repo_is_not_asked(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    """claude-code updates itself in the background and names no repo, so there is
    nothing to compare against. Silence is the honest answer — an UNKNOWN row on
    every plan for a question nobody can answer is noise, not a finding."""
    reporting(fake_bin, 'claude', '2.1.226 (Claude Code)')
    live = session(tmp_path, NO_REPO, DECLARES_NO_REPO)

    assert changes(live) == ()


def test_an_entry_measured_against_tags_is_compared_like_any_other(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    """aws/aws-cli tags every build and publishes no release, so `version_source:
    tags` decides which endpoint fills the cache. Everything downstream of the
    cache is unchanged, which is the point — a tag is a version like any other."""
    reporting(fake_bin, 'aws', 'aws-cli/2.36.18 Python/3.14.6')
    cached(release_cache, {'aws/aws-cli': '2.36.19'})
    live = session(tmp_path, AWSCLI, DECLARES_AWSCLI)

    assert [(change.item, change.verdict) for change in changes(live)] == [('custom/awscli', Verdict.STALE)]


def test_the_declared_source_decides_which_endpoint_is_asked(tmp_path: Path, fake_bin: Path) -> None:
    """Declared rather than discovered. Falling back to tags when a release lookup
    fails would read a rate-limited minute as "this project tags instead"."""
    reporting(fake_bin, 'aws', 'aws-cli/2.36.18')
    live = session(tmp_path, AWSCLI, DECLARES_AWSCLI)

    item = next(item for item in live.plan.for_resource('packages') if item.name == 'awscli')

    assert packages._wanted(item) == releases.Wanted(repo='aws/aws-cli', from_tags=True)


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


def staged_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rows: dict[str, str], category: str = 'binary') -> Path:
    """A bundle manifest, written the way `create_bundle.Bundle.record` writes it."""
    installers = tmp_path / 'installers'
    installers.mkdir(parents=True, exist_ok=True)
    lines = [f'{category}|{name}|{version}|{name}' for name, version in rows.items()]
    (installers / 'manifest.txt').write_text('# Format: category|name|version|filename\n' + '\n'.join(lines) + '\n')
    monkeypatch.setattr(paths, 'BUNDLE_DIR', installers)
    return installers


def test_offline_a_tool_behind_its_bundle_is_stale(tmp_path: Path, fake_bin: Path, release_cache: Path, monkeypatch) -> None:
    """The machine a bundle exists for cannot reach GitHub, so the release cache is
    empty and answers UNKNOWN for everything installed. Offline the bundle is the
    upstream instead, which is what makes extracting a newer one onto a built
    machine upgrade anything at all."""
    reporting(fake_bin, 'lazygit', 'lazygit version 0.44.0')
    staged_bundle(tmp_path, monkeypatch, {'lazygit': '0.45.0'})
    live = dc.replace(session(tmp_path, LAZYGIT, DECLARES_LAZYGIT), offline=True)

    assert [(change.item, change.verdict) for change in changes(live)] == [('ghrelease/lazygit', Verdict.STALE)]


def test_offline_a_tool_at_its_bundles_version_reports_nothing(tmp_path: Path, fake_bin: Path, release_cache: Path, monkeypatch) -> None:
    reporting(fake_bin, 'lazygit', 'lazygit version 0.45.0')
    staged_bundle(tmp_path, monkeypatch, {'lazygit': '0.45.0'})
    live = dc.replace(session(tmp_path, LAZYGIT, DECLARES_LAZYGIT), offline=True)

    assert changes(live) == ()


def test_offline_a_tool_the_bundle_does_not_carry_says_so_rather_than_reporting_current(
    tmp_path: Path, fake_bin: Path, release_cache: Path, monkeypatch
) -> None:
    """The rule the cache exists to keep, applied to the other upstream: it may be
    out of date, it may not lie. A bundle with no row for a tool is a different
    finding from a cache nobody has filled, and the detail says which."""
    reporting(fake_bin, 'lazygit', 'lazygit version 0.44.0')
    staged_bundle(tmp_path, monkeypatch, {'something-else': '1.0.0'})
    live = dc.replace(session(tmp_path, LAZYGIT, DECLARES_LAZYGIT), offline=True)

    found = changes(live)

    assert [(change.verdict, change.repair) for change in found] == [(Verdict.UNKNOWN, Repair.NONE)]
    assert 'bundle' in found[0].detail


def test_offline_never_writes_what_the_bundle_holds_into_the_release_cache(
    tmp_path: Path, fake_bin: Path, release_cache: Path, monkeypatch
) -> None:
    """A bundle's versions are what one tarball happens to hold, not what upstream
    published. Persisting them would have the next online run read a bundle's
    contents as the release cache.

    `--refresh` is set deliberately: it is the flag that means "spend the network
    on being current", and offline is the state where there is no network to
    spend. An unwritten cache alone would not prove the request never went out,
    so `consulted_network` is asserted beside it.
    """
    reporting(fake_bin, 'lazygit', 'lazygit version 0.44.0')
    staged_bundle(tmp_path, monkeypatch, {'lazygit': '0.45.0'})
    live = dc.replace(session(tmp_path, LAZYGIT, DECLARES_LAZYGIT), refresh=True, offline=True)

    observed = packages.RESOURCE.observe(live, live.plan)

    assert not release_cache.exists()
    assert observed.consulted_network is False


@pytest.mark.parametrize('category', ['binary', 'extra', 'go-binary', 'cargo', 'script'])
def test_offline_the_bundle_answers_under_whichever_category_staged_the_tool(
    tmp_path: Path, fake_bin: Path, release_cache: Path, monkeypatch, category: str
) -> None:
    """A tool declared as a GitHub release here is a cargo package or a Go tool on
    another machine, and the bundler files it under whichever section staged it.

    A reader that understood only its own category would answer for `binary` and
    send the rest of the plan to a network the offline machine does not have —
    which is the whole failure the bundle exists to prevent.
    """
    reporting(fake_bin, 'lazygit', 'lazygit version 0.44.0')
    staged_bundle(tmp_path, monkeypatch, {'lazygit': '0.45.0'}, category=category)
    live = dc.replace(session(tmp_path, LAZYGIT, DECLARES_LAZYGIT), offline=True)

    assert [(change.item, change.verdict) for change in changes(live)] == [('ghrelease/lazygit', Verdict.STALE)]


def test_offline_with_no_bundle_at_all_is_a_miss_never_a_stale_answer(
    tmp_path: Path, fake_bin: Path, release_cache: Path, monkeypatch
) -> None:
    """A machine that never had a bundle extracted is the case a *missing manifest*
    reaches, which no other test here takes: every one of them stages one first.

    `BUNDLE_DIR` is pointed at a path that does not exist rather than left alone,
    because the real one may exist on the machine running this and the test would
    then read whatever it holds.
    """
    reporting(fake_bin, 'lazygit', 'lazygit version 0.44.0')
    monkeypatch.setattr(paths, 'BUNDLE_DIR', tmp_path / 'never-extracted')
    live = dc.replace(session(tmp_path, LAZYGIT, DECLARES_LAZYGIT), offline=True)

    found = changes(live)

    assert [(change.verdict, change.repair) for change in found] == [(Verdict.UNKNOWN, Repair.NONE)]
    assert 'bundle' in found[0].detail, 'offline the advice must not be `check --refresh`, which offline cannot do'


def test_an_online_run_ignores_a_staged_bundle(tmp_path: Path, fake_bin: Path, release_cache: Path, monkeypatch) -> None:
    """Staging a bundle must not pin an online machine to whatever it captured.

    The two upstreams answer different versions here on purpose: agreeing would
    let the bundle answer and still pass. What is asserted is *which* one was
    read, not that the verdict came out stale.
    """
    reporting(fake_bin, 'lazygit', 'lazygit version 0.44.0')
    staged_bundle(tmp_path, monkeypatch, {'lazygit': '0.45.0'})
    cached(release_cache, {'jesseduffield/lazygit': 'v0.46.0'})
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)

    found = changes(live)

    assert [(change.item, change.verdict) for change in found] == [('ghrelease/lazygit', Verdict.STALE)]
    assert 'v0.46.0' in found[0].detail, 'the release cache is the upstream online, never the bundle'


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
# --reinstall: installing again what measuring calls fine
# ─────────────────────────────────────────────────────────────────────────────


def test_a_named_reinstall_makes_an_installed_tool_actionable(tmp_path: Path, fake_bin: Path) -> None:
    executable(fake_bin, 'task')
    live = dc.replace(session(tmp_path, GO_TOOL, DECLARES_TASK), reinstall=frozenset({'task'}))

    found = changes(live)

    assert [(change.item, change.verdict) for change in found] == [('go/task', Verdict.STALE)]
    assert found[0].actionable


def test_an_installed_tool_nobody_named_is_still_left_alone(tmp_path: Path, fake_bin: Path) -> None:
    """The flag names entries because the alternative is a blanket force, which is
    a fresh `go install` of every Go tool to repair one binary."""
    executable(fake_bin, 'task')
    live = dc.replace(session(tmp_path, GO_TOOL, DECLARES_TASK), reinstall=frozenset({'something-else'}))

    assert changes(live) == ()


def test_a_reinstall_reaches_what_currency_cannot_measure(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    """The reason it is checked ahead of the comparison rather than after. A version
    string nothing can parse is UNKNOWN and `Repair.NONE`, so measuring alone can
    never repair it — and that is exactly the tool worth naming."""
    reporting(fake_bin, 'lazygit', 'built from source')
    cached(release_cache, {'jesseduffield/lazygit': 'v0.45.0'})
    live = dc.replace(session(tmp_path, LAZYGIT, DECLARES_LAZYGIT), reinstall=frozenset({'lazygit'}))

    found = changes(live)

    assert [(change.verdict, change.repair) for change in found] == [(Verdict.STALE, Repair.AUTOMATIC)]


def test_a_reinstall_of_something_absent_is_still_just_missing(tmp_path: Path, fake_bin: Path) -> None:
    """Naming a tool that is not there changes nothing: it was already going to be
    installed, and the detail should say why it is in the plan rather than
    reporting a reinstall of something that was never installed."""
    live = dc.replace(session(tmp_path, GO_TOOL, DECLARES_TASK), reinstall=frozenset({'task'}))

    found = changes(live)

    assert [change.verdict for change in found] == [Verdict.MISSING]


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
    monkeypatch.setattr(npm, 'install', record)
    monkeypatch.setattr(uvtool, 'install', record)
    monkeypatch.setattr(uvtool, 'install_git', record)
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

UV_TOOL = {'uv_tools': {'linters': [{'name': 'unreleased-linter'}]}}
DECLARES_UV = {'machine': 'box', 'platform': 'linux', 'uv_tools': ['unreleased-linter']}


def test_a_missing_uv_tool_is_installed_by_its_provider(
    tmp_path: Path, fake_bin: Path, uv_tools: Path, installs: list[str], unprivileged: Privilege
) -> None:
    live = session(tmp_path, UV_TOOL, DECLARES_UV)

    outcome = packages.RESOURCE.perform(live, only_change(live), unprivileged)

    assert outcome.status is OutcomeStatus.DONE
    assert installs == ['unreleased-linter']


def test_a_missing_npm_global_is_installed_by_its_provider(
    tmp_path: Path, fake_bin: Path, installs: list[str], unprivileged: Privilege
) -> None:
    live = session(tmp_path, NPM_GLOBAL, DECLARES_NPM)

    outcome = packages.RESOURCE.perform(live, only_change(live), unprivileged)

    assert outcome.status is OutcomeStatus.DONE
    assert installs == ['unpublished-linter']


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


# ─────────────────────────────────────────────────────────────────────────────
# A second copy on PATH
# ─────────────────────────────────────────────────────────────────────────────
#
# The question `detect-installed-duplicates.sh` asked, moved to where a real
# machine can be asked it. That script reported nine findings on a converged Arch
# box, two of them the declared bootstrap npm sitting under fnm — so what counts
# as an *explanation* is what these cover, not the counting.
#
# The tool is deliberately a name no machine carries. `fake_bin` keeps
# `/usr/bin:/bin` behind it so the fixture can run `git` and `bash`, which means a
# test naming a real tool measures the box it runs on: `rg` here found
# `/usr/bin/rg` and every assertion below inverted.

CARGO_TOOL = {'cargo_packages': [{'name': 'frobnicate', 'command': 'frob'}]}
DECLARES_FROB = {'machine': 'box', 'platform': 'linux', 'cargo_packages': ['frobnicate']}

OWNED_BY_FROBNICATE = '#!/bin/sh\n[ "$1" = "--version" ] && exit 0\n[ "$1" = "-Qoq" ] && echo frobnicate\nexit 0\n'
"""A package manager that says the same package owns whatever it is asked about."""


def second_bin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A directory behind `fake_bin`, for the copy that loses."""
    directory = tmp_path / 'other-bin'
    directory.mkdir(exist_ok=True)
    monkeypatch.setenv('PATH', f'{os.environ["PATH"]}{os.pathsep}{directory}')
    return directory


def shadow_changes(live: Session) -> list[Change]:
    return [change for change in changes(live) if change.verdict is Verdict.UNDECLARED]


def test_one_copy_of_a_declared_tool_reports_nothing(tmp_path: Path, fake_bin: Path) -> None:
    executable(fake_bin, 'frob')
    live = session(tmp_path, CARGO_TOOL, DECLARES_FROB)

    assert shadow_changes(live) == []


def test_a_second_copy_on_path_is_reported_against_the_item_that_declares_it(
    tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Which of the two runs is decided by PATH order rather than by the manifest,
    and the loser is invisible to every other check: `apply` installs, evidence
    finds *a* binary, and the machine reports converged while the tool anyone
    actually runs came from somewhere else."""
    executable(fake_bin, 'frob')
    stray = executable(second_bin(tmp_path, monkeypatch), 'frob')
    live = session(tmp_path, CARGO_TOOL, DECLARES_FROB)

    found = shadow_changes(live)

    assert [change.item for change in found] == ['cargo/frobnicate']
    assert found[0].observed == str(stray)
    assert str(fake_bin / 'frob') in found[0].detail


def test_a_second_copy_is_not_something_apply_can_repair(tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`check`'s subject and not `plan`'s. The declaration says what should be
    installed and cannot say which of two copies may be removed safely, so an
    `apply` that deleted one would be acting on a judgement nobody declared."""
    executable(fake_bin, 'frob')
    executable(second_bin(tmp_path, monkeypatch), 'frob')
    live = session(tmp_path, CARGO_TOOL, DECLARES_FROB)

    change = shadow_changes(live)[0]

    assert change.repair is Repair.BY_HAND
    assert change.drifted and not change.actionable


def test_the_same_binary_reachable_twice_is_one_installation(tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`~/.local/bin/fd` pointing at `/usr/bin/fd` is one tool with two names.
    Counting paths rather than real paths reports every symlinked companion this
    repo deploys on purpose."""
    real = executable(fake_bin, 'frob')
    (second_bin(tmp_path, monkeypatch) / 'frob').symlink_to(real)
    live = session(tmp_path, CARGO_TOOL, DECLARES_FROB)

    assert shadow_changes(live) == []


def test_a_copy_a_declared_package_owns_is_explained(tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The pair that made the shell script unreadable: fnm owns `node` and `npm`
    while pacman's `nodejs` ships `/usr/bin/node` underneath, and that second copy
    is the bootstrap the declaration asks for. Asking the package manager who put
    a file there is what separates it from a stray."""
    executable(fake_bin, 'frob')
    executable(second_bin(tmp_path, monkeypatch), 'frob')
    executable(fake_bin, 'pacman', OWNED_BY_FROBNICATE)
    declared = {**CARGO_TOOL, 'system_packages': [{'name': 'frobnicate', 'apt': 'frobnicate', 'pacman': 'frobnicate'}]}
    live = session(tmp_path, declared, {**DECLARES_FROB, 'system_packages': 'workstation'})

    assert shadow_changes(live) == []


def test_a_copy_an_undeclared_package_owns_is_still_a_stray(tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The inverse, and the direction that must not fail open: a package manager
    answering at all is not an explanation, or every `/usr/bin` copy on a Linux
    box would excuse itself."""
    executable(fake_bin, 'frob')
    executable(second_bin(tmp_path, monkeypatch), 'frob')
    executable(fake_bin, 'pacman', OWNED_BY_FROBNICATE)
    live = session(tmp_path, CARGO_TOOL, DECLARES_FROB)

    assert [change.item for change in shadow_changes(live)] == ['cargo/frobnicate']


def test_a_copy_inside_the_checkout_is_not_machine_state(tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`uv run dotfiles check` from the repo puts `.venv/bin` first on PATH, so
    every tool the dev environment also carries reads as duplicated. A second copy
    that exists for the duration of a development command is not the machine."""
    executable(fake_bin, 'frob')
    live = session(tmp_path, CARGO_TOOL, DECLARES_FROB)
    inside = live.repo / '.venv' / 'bin'
    inside.mkdir(parents=True)
    executable(inside, 'frob')
    monkeypatch.setenv('PATH', f'{inside}{os.pathsep}{os.environ["PATH"]}')

    assert shadow_changes(live) == []
