"""What counts as evidence that a declared tool is installed.

Every seam here is a real knob the code already honours — `PATH`, `UV_TOOL_DIR`,
the package-manager binaries on `PATH` — so nothing in `src/dotfiles/` is
patched. `PATH` keeps `/usr/bin:/bin`, with the tools under test shadowed by name
in a fake bin dir: without the real ones, `git` and `bash` raise
FileNotFoundError and the fixture cannot run its own helpers.

These replace nine subprocess tests that drove `packages missing` against a
synthetic tree. The question is the same; the answer is now a function call.

The builders that write that tree — `session`, `executable`, `reporting`,
`receipt`, `cached`, `staged_bundle` — live in `matrix.harness`, because
`tests/matrix/` drives the same declaration through the CLI and two copies of a
synthetic-repo builder is two ideas of what a declaration is.
"""

from __future__ import annotations

import dataclasses as dc
import datetime as dt
import os
from pathlib import Path

import pytest
from matrix.harness import PACKAGE_MANAGERS
from matrix.harness import REFUSED
from matrix.harness import cached
from matrix.harness import executable
from matrix.harness import receipt
from matrix.harness import reporting
from matrix.harness import session
from matrix.harness import staged_bundle

from dotfiles import catalog
from dotfiles import evidence as ev
from dotfiles import providers
from dotfiles import releases
from dotfiles.coordinates import Target
from dotfiles.privilege import Privilege
from dotfiles.providers import Kind
from dotfiles.providers import cargo
from dotfiles.providers import custom
from dotfiles.providers import ghrelease
from dotfiles.providers import gotool
from dotfiles.providers import npm
from dotfiles.providers import syspkg
from dotfiles.providers import uvtool
from dotfiles.resources import Change
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.resources import packages
from dotfiles.session import Session


@pytest.fixture(autouse=True)
def a_home_this_test_owns(tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`$HOME` named as the directory `harness.session` builds a home in, and every
    directory a provider installs into put on `PATH`.

    Two halves of one machine that have to agree. `session` hands the `Session` a
    home under `tmp_path`, while every provider resolves its own directory off
    `Path.home()` — the *process's* home, not the Session's. Unnamed, a release
    measured by provenance reads the developer's real `~/.local/bin`: the test then
    passes on a runner and fails at a desk that happens to have the tool, which is
    the fixture reading the machine it runs on that `fake_bin` exists to stop.

    The provider directories are on `PATH` for the reason `toolchain.TOOL_PATH_DIRS`
    puts them there on a real machine: a tool is invisible to anything walking
    `PATH` unless the directory holding it is named. `_shadowing` is that walk, and
    without them a declared tool measured at its provider's directory has no copy on
    `PATH` for a second one to shadow.

    Autouse because the hole is one a test cannot see it has, and behind `fake_bin`
    on `PATH` because that is the order a real machine has — a shadowed package
    manager answers ahead of anything installed.
    """
    home = tmp_path / 'home'
    monkeypatch.setenv('HOME', str(home))
    installed = [providers.bin_dir(), cargo.cargo_bin(), gotool.gobin(), npm.prefix() / 'bin']
    for directory in installed:
        directory.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv('PATH', os.pathsep.join([str(fake_bin), *map(str, installed), os.environ['PATH']]))
    # Anything resolving an XDG directory prefers the variable over `$HOME`, so a
    # developer whose `$XDG_CONFIG_HOME` is set has `ghrelease.unit_dir` reading
    # their real `~/.config/systemd/user` — where this desk will have a syncthing
    # unit the moment the migration this file tests is run on it.
    monkeypatch.setenv('XDG_CONFIG_HOME', str(home / '.config'))
    return home


def placed(directory: Path, name: str, version: str | None = None) -> Path:
    """A tool this machine has, in the directory its own provider installs into.

    `evidence.in_provider_dir` measures an entry there rather than on `PATH`, so a
    binary anywhere else is one this repo did not install — the whole distinction
    the provenance check exists to draw. Placing through the provider's own
    function rather than a literal keeps the fixture and the code reading one
    answer.
    """
    return reporting(directory, name, version) if version is not None else executable(directory, name)


def released(name: str, version: str | None = None) -> Path:
    """A release, where `ghrelease` puts one."""
    return placed(providers.bin_dir(), name, version)


def cargo_installed(name: str, version: str | None = None) -> Path:
    """A Rust CLI, where `cargo binstall` puts one."""
    return placed(cargo.cargo_bin(), name, version)


def go_installed(name: str, version: str | None = None) -> Path:
    """A Go tool, where `go install` puts one."""
    return placed(gotool.gobin(), name, version)


def released_script(name: str, script: str) -> Path:
    """The same placement, for a test that needs the binary to answer its own way."""
    return executable(providers.bin_dir(), name, script)


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


def test_a_declared_tool_in_its_provider_directory_is_matched(tmp_path: Path, fake_bin: Path) -> None:
    go_installed('task')
    live = session(tmp_path, GO_TOOL, DECLARES_TASK)

    assert verdicts(live) == {'go/task': Verdict.MATCHED}


def test_a_declared_tool_only_somewhere_else_on_path_is_not_matched(tmp_path: Path, fake_bin: Path) -> None:
    """The provenance question, for a Go tool. Measured on mbp 2026-08-24: `rg` and
    `oxker` are `cargo_packages` entries whose only copy is a brew formula somebody
    chose, and both reported MATCHED off `/usr/local/bin` while cargo had never
    installed either."""
    executable(fake_bin, 'task')
    live = session(tmp_path, GO_TOOL, DECLARES_TASK)

    assert verdicts(live) == {'go/task': Verdict.MISSING}


def test_the_copy_that_does_answer_is_named_for_a_provider_directory(tmp_path: Path, fake_bin: Path) -> None:
    """A row reading "not installed" on a machine whose `task --version` answers is
    the reading that sends somebody looking for a broken installer."""
    elsewhere = executable(fake_bin, 'task')
    live = session(tmp_path, GO_TOOL, DECLARES_TASK)
    observed = packages.RESOURCE.observe(live, live.plan)

    detail = observed.evidence['go/task'].detail
    assert str(gotool.gobin() / 'task') in detail, 'the directory that should hold it'
    assert str(elsewhere) in detail, 'and the copy that answers instead'


def test_an_entry_the_manifest_does_not_declare_is_not_looked_for(tmp_path: Path, fake_bin: Path) -> None:
    declared = {'go_tools': [{'name': 'task', 'package': 'x'}, {'name': 'gdu', 'package': 'y'}]}
    live = session(tmp_path, declared, DECLARES_TASK)

    assert set(verdicts(live)) == {'go/task'}


def test_the_command_field_is_what_gets_looked_up(tmp_path: Path, fake_bin: Path) -> None:
    """ripgrep ships rg, `@taplo/cli` ships taplo. Without this an installed tool
    reads as missing forever, which is the failure mode that makes a checker get
    ignored."""
    cargo_installed('rg')
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
    searched = tmp_path / 'searched'
    searched.mkdir()
    executable(searched, 'reachable')
    (searched / 'denied').symlink_to(forbidden / 'target')
    forbidden.chmod(0o000)

    try:
        found = ev.executables_on_path(tmp_path / 'checkout', search=str(searched))
    finally:
        forbidden.chmod(0o700)

    assert 'reachable' in found


def test_narrowing_the_scan_answers_the_same_for_the_names_asked_about(tmp_path: Path) -> None:
    """The whole basis for narrowing it: fewer syscalls, identical answer.

    Every entry costs three round trips to resolve and the caller asks about the
    hundred binaries a machine declares, not the three thousand names a PATH
    holds. On WSL with Windows interop left on those round trips cross drvfs and
    the untouched names are in the tens of thousands.
    """
    searched = tmp_path / 'searched'
    searched.mkdir()
    for name in ('wanted', 'ignored'):
        executable(searched, name)

    whole = ev.executables_on_path(tmp_path / 'checkout', search=str(searched))
    narrowed = ev.executables_on_path(tmp_path / 'checkout', search=str(searched), wanted=frozenset({'wanted'}))

    assert set(whole) == {'wanted', 'ignored'}
    assert narrowed == {'wanted': whole['wanted']}


def test_two_copies_of_one_declared_binary_are_both_found_when_narrowed(tmp_path: Path) -> None:
    """Narrowing must not cost the second copy, which is the only thing the index
    is built to see — one copy is never a finding."""
    first, second = tmp_path / 'a', tmp_path / 'b'
    for directory in (first, second):
        directory.mkdir()
        executable(directory, 'rg')

    found = ev.executables_on_path(tmp_path / 'checkout', search=f'{first}{os.pathsep}{second}', wanted=frozenset({'rg'}))

    assert found['rg'] == (str(first / 'rg'), str(second / 'rg'))


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


def test_a_git_installed_tool_reports_the_revision_uv_recorded(uv_tools: Path) -> None:
    receipt(uv_tools, 'doit', '{ name = "doit", git = "https://github.com/datapointchris/doit.git?rev=v1.0.0" }')

    assert ev.uv_tool_pin('doit') == 'v1.0.0'


def test_a_tool_installed_from_its_default_branch_has_no_pin(uv_tools: Path) -> None:
    """A repo publishing no release records no `?rev=`, so there is no version to
    compare against. That is a measured answer rather than a failure to look."""
    receipt(uv_tools, 'typos', '{ name = "typos", git = "https://github.com/datapointchris/typos.git" }')

    assert ev.uv_tool_pin('typos') is None


def test_a_tool_with_no_receipt_has_no_pin(uv_tools: Path) -> None:
    (uv_tools / 'ripgrep').mkdir()

    assert ev.uv_tool_pin('ripgrep') is None


def test_a_receipt_pinning_something_other_than_the_tool_does_not_answer(uv_tools: Path) -> None:
    """uv records the requirement under the tool's own name, and a receipt can
    carry a dependency's pin as readily as the tool's own."""
    receipt(uv_tools, 'indy', '{ name = "a-dependency", git = "https://github.com/other/dep.git?rev=v9.9.9" }')

    assert ev.uv_tool_pin('indy') is None


GIT_UV = {'git_uv_tools': [{'name': 'doit', 'repo': 'https://github.com/datapointchris/doit.git'}]}
DECLARES_GIT_UV = {'machine': 'box', 'platform': 'linux', 'git_uv_tools': ['doit']}
PINNED = '{{ name = "doit", git = "https://github.com/datapointchris/doit.git?rev={tag}" }}'
UNPINNED = '{ name = "doit", git = "https://github.com/datapointchris/doit.git" }'


def test_a_git_uv_tool_behind_its_newest_release_is_stale(tmp_path: Path, fake_bin: Path, uv_tools: Path, release_cache: Path) -> None:
    """The whole point: this section reported converged for as long as the tool
    directory existed, so one eight releases behind read as current."""
    receipt(uv_tools, 'doit', PINNED.format(tag='v1.0.0'))
    cached(release_cache, {'datapointchris/doit': 'v1.1.0'})
    live = session(tmp_path, GIT_UV, DECLARES_GIT_UV)

    assert [(change.item, change.verdict) for change in changes(live)] == [('uv-git/doit', Verdict.STALE)]


def test_a_git_uv_tool_at_its_newest_release_reports_nothing(tmp_path: Path, fake_bin: Path, uv_tools: Path, release_cache: Path) -> None:
    receipt(uv_tools, 'doit', PINNED.format(tag='v1.1.0'))
    cached(release_cache, {'datapointchris/doit': 'v1.1.0'})
    live = session(tmp_path, GIT_UV, DECLARES_GIT_UV)

    assert changes(live) == ()


def test_an_unpinned_git_uv_tool_is_stale_against_a_published_release(
    tmp_path: Path, fake_bin: Path, uv_tools: Path, release_cache: Path
) -> None:
    """`catalog.GitUvTool` calls an unpinned install "the degraded state rather than
    the flexible one", so it is drift `apply` repairs rather than a version nobody
    could read."""
    receipt(uv_tools, 'doit', UNPINNED)
    cached(release_cache, {'datapointchris/doit': 'v1.1.0'})
    live = session(tmp_path, GIT_UV, DECLARES_GIT_UV)

    found = changes(live)

    assert [(change.item, change.verdict) for change in found] == [('uv-git/doit', Verdict.STALE)]
    assert 'default branch' in found[0].detail


def test_a_git_uv_tool_with_a_cold_cache_is_unmeasured_not_current(
    tmp_path: Path, fake_bin: Path, uv_tools: Path, release_cache: Path
) -> None:
    """Nothing asked upstream, so nothing can say. Reading that as converged is the
    exact failure `Verdict.UNKNOWN` exists for."""
    receipt(uv_tools, 'doit', PINNED.format(tag='v1.0.0'))
    live = session(tmp_path, GIT_UV, DECLARES_GIT_UV)

    assert [(change.item, change.verdict) for change in changes(live)] == [('uv-git/doit', Verdict.UNKNOWN)]


def test_a_branch_tracking_tool_is_never_asked_about_currency(tmp_path: Path, fake_bin: Path, uv_tools: Path, release_cache: Path) -> None:
    """It publishes no release, so there is no tag it could be behind. An UNKNOWN
    row on every plan for something unanswerable by construction is noise, not a
    finding."""
    declared = {'git_uv_tools': [{'name': 'doit', 'repo': 'https://github.com/datapointchris/doit.git', 'tracks_branch': True}]}
    receipt(uv_tools, 'doit', UNPINNED)
    live = session(tmp_path, declared, DECLARES_GIT_UV)

    assert changes(live) == ()


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


LAZYGIT = {'github_releases': [{'name': 'lazygit', 'repo': 'jesseduffield/lazygit'}]}
DECLARES_LAZYGIT = {'machine': 'box', 'platform': 'linux', 'github_releases': ['lazygit']}


# ─────────────────────────────────────────────────────────────────────────────
# Provenance: which copy of a release counts as installed
# ─────────────────────────────────────────────────────────────────────────────
#
# Measured on macmini 2026-08-16. Homebrew's syncthing sat on PATH at the version
# the release publishes, so `packages plan` reported an entry satisfied that
# nothing here had ever installed — and `brew uninstall` would have taken the tool
# off the machine with every verb still calling it converged.


def test_a_release_at_the_path_this_provider_chose_is_installed(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    released('lazygit', 'lazygit version 0.45.0')
    cached(release_cache, {'jesseduffield/lazygit': 'v0.45.0'})
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)

    assert verdicts(live) == {'ghrelease/lazygit': Verdict.MATCHED}


def test_a_release_another_manager_put_on_path_is_not_this_declaration_satisfied(
    tmp_path: Path, fake_bin: Path, release_cache: Path
) -> None:
    """The version is right and the provenance is not, which is the whole finding:
    what answers `--version` is a binary this repo did not place and cannot keep."""
    reporting(fake_bin, 'lazygit', 'lazygit version 0.45.0')
    cached(release_cache, {'jesseduffield/lazygit': 'v0.45.0'})
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)

    assert verdicts(live) == {'ghrelease/lazygit': Verdict.MISSING}


def test_the_copy_that_does_answer_is_named(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    """A row reading "not installed" on a machine whose `lazygit --version` answers
    is the reading that sends somebody looking for a broken installer."""
    elsewhere = reporting(fake_bin, 'lazygit', 'lazygit version 0.45.0')
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)
    observed = packages.RESOURCE.observe(live, live.plan)

    assert str(elsewhere) in observed.evidence['ghrelease/lazygit'].detail


def test_a_release_installed_nowhere_is_still_plainly_missing(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    """The common case, and the one the naming above must not clutter."""
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)
    observed = packages.RESOURCE.observe(live, live.plan)
    found = observed.evidence['ghrelease/lazygit']

    assert found.verdict is Verdict.MISSING
    assert str(providers.bin_dir() / 'lazygit') in found.detail


def test_a_release_behind_the_latest_is_stale(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    released('lazygit', 'lazygit version 0.44.0')
    cached(release_cache, {'jesseduffield/lazygit': 'v0.45.0'})
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)

    found = changes(live)

    assert [(change.item, change.verdict) for change in found] == [('ghrelease/lazygit', Verdict.STALE)]


def test_a_release_at_the_latest_reports_nothing(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    released('lazygit', 'lazygit version 0.45.0')
    cached(release_cache, {'jesseduffield/lazygit': 'v0.45.0'})
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)

    assert changes(live) == ()


def test_a_release_ahead_of_the_cache_is_not_stale(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    """The cache is allowed to be behind reality. A tool newer than the last
    answer is not out of date; it is the cache that is."""
    released('lazygit', 'lazygit version 0.46.0')
    cached(release_cache, {'jesseduffield/lazygit': 'v0.45.0'})
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)

    assert changes(live) == ()


def test_a_tool_ahead_of_a_measured_release_is_stale(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    """The `ifiles` case: a repo that went to 2.x and back to 1.x strands whatever
    installed the high version, and `at_least` calls it current forever. Measured
    against a figure established this run, above the newest release is drift —
    there is no install anything here can perform that produces it."""
    released('lazygit', 'lazygit version 2.10.0')
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
    released('lazygit', 'lazygit version 2.10.0')
    staged_bundle(tmp_path, monkeypatch, {'lazygit': '0.45.0'})
    live = dc.replace(session(tmp_path, LAZYGIT, DECLARES_LAZYGIT), offline=True)

    assert [(change.item, change.verdict) for change in changes(live)] == [('ghrelease/lazygit', Verdict.STALE)]


def test_an_expired_cache_reports_unknown_rather_than_current(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    """The rule the cache exists to keep: it may be out of date, it may not lie."""
    released('lazygit', 'lazygit version 0.44.0')
    cached(release_cache, {'jesseduffield/lazygit': 'v0.45.0'}, age=releases.TTL + dt.timedelta(hours=1))
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)

    found = changes(live)

    assert [(change.item, change.verdict, change.repair) for change in found] == [('ghrelease/lazygit', Verdict.UNKNOWN, Repair.NONE)]


def test_no_cache_at_all_reports_unknown(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    released('lazygit', 'lazygit version 0.44.0')
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)

    assert [change.verdict for change in changes(live)] == [Verdict.UNKNOWN]


def test_a_tool_taking_the_version_subcommand_is_still_measured(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    """terrascan rejects the flag and takes the subcommand. Probing only the flag
    reported an installed, current tool as unmeasurable."""
    released_script('lazygit', '#!/bin/sh\n[ "$1" = version ] || exit 1\nprintf "version: v0.45.0\\n"\n')
    cached(release_cache, {'jesseduffield/lazygit': 'v0.45.0'})
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)

    assert changes(live) == ()


def test_a_binary_that_answers_neither_probe_is_unknown(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    released_script('lazygit', '#!/bin/sh\nexit 1\n')
    cached(release_cache, {'jesseduffield/lazygit': 'v0.45.0'})
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)

    found = changes(live)

    assert [(change.verdict, change.repair) for change in found] == [(Verdict.UNKNOWN, Repair.NONE)]


def test_an_unparseable_version_is_unknown_rather_than_behind(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    """Reporting it behind would send `apply` to reinstall a tool nothing
    established was wrong."""
    released('lazygit', 'built from source')
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
    released('lazygit', 'lazygit version 0.44.0')
    declared = {'github_releases': [{'name': 'lazygit', 'repo': 'jesseduffield/lazygit', 'version': '0.45.0'}]}
    live = session(tmp_path, declared, DECLARES_LAZYGIT)

    found = changes(live)

    assert [(change.item, change.verdict) for change in found] == [('ghrelease/lazygit', Verdict.STALE)]


def test_a_release_at_its_pin_reports_nothing(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    released('lazygit', 'lazygit version 0.45.0')
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
    go_installed('task')
    live = session(tmp_path, GO_TOOL, DECLARES_TASK)

    assert changes(live) == ()


CARGO_CURRENCY = {'cargo_packages': [{'name': 'fd-find', 'command': 'fd', 'github_repo': 'sharkdp/fd'}]}
DECLARES_FD = {'machine': 'box', 'platform': 'linux', 'cargo_packages': ['fd-find']}


def test_a_cargo_package_behind_its_release_is_stale(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    """`cargo binstall` is the upgrade, so being behind the repo the declaration
    names is drift rather than someone else's schedule. Without this, converting
    the phase would have silently removed the only thing that moved these."""
    cargo_installed('fd', 'fd 10.2.0')
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
    executable(cargo.cargo_bin(), 'webviewrs', f'#!/bin/sh\ntouch "{ran}"\nprintf "1.0.0\\n"\n')
    cached(release_cache, {'datapointchris/webviewrs': 'v2.0.0'})
    declared = {'cargo_packages': [{'name': 'webviewrs', 'github_repo': 'datapointchris/webviewrs', 'reports_version': False}]}
    live = session(tmp_path, declared, {'machine': 'box', 'platform': 'linux', 'cargo_packages': ['webviewrs']})

    assert changes(live) == ()
    assert not ran.exists()


def test_offline_a_tool_behind_its_bundle_is_stale(tmp_path: Path, fake_bin: Path, release_cache: Path, monkeypatch) -> None:
    """The machine a bundle exists for cannot reach GitHub, so the release cache is
    empty and answers UNKNOWN for everything installed. Offline the bundle is the
    upstream instead, which is what makes extracting a newer one onto a built
    machine upgrade anything at all."""
    released('lazygit', 'lazygit version 0.44.0')
    staged_bundle(tmp_path, monkeypatch, {'lazygit': '0.45.0'})
    live = dc.replace(session(tmp_path, LAZYGIT, DECLARES_LAZYGIT), offline=True)

    assert [(change.item, change.verdict) for change in changes(live)] == [('ghrelease/lazygit', Verdict.STALE)]


def test_offline_a_tool_at_its_bundles_version_reports_nothing(tmp_path: Path, fake_bin: Path, release_cache: Path, monkeypatch) -> None:
    released('lazygit', 'lazygit version 0.45.0')
    staged_bundle(tmp_path, monkeypatch, {'lazygit': '0.45.0'})
    live = dc.replace(session(tmp_path, LAZYGIT, DECLARES_LAZYGIT), offline=True)

    assert changes(live) == ()


def test_offline_a_tool_the_bundle_does_not_carry_says_so_rather_than_reporting_current(
    tmp_path: Path, fake_bin: Path, release_cache: Path, monkeypatch
) -> None:
    """The rule the cache exists to keep, applied to the other upstream: it may be
    out of date, it may not lie. A bundle with no row for a tool is a different
    finding from a cache nobody has filled, and the detail says which."""
    released('lazygit', 'lazygit version 0.44.0')
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
    released('lazygit', 'lazygit version 0.44.0')
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
    released('lazygit', 'lazygit version 0.44.0')
    staged_bundle(tmp_path, monkeypatch, {'lazygit': '0.45.0'}, category=category)
    live = dc.replace(session(tmp_path, LAZYGIT, DECLARES_LAZYGIT), offline=True)

    assert [(change.item, change.verdict) for change in changes(live)] == [('ghrelease/lazygit', Verdict.STALE)]


def test_offline_with_no_bundle_at_all_is_a_miss_never_a_stale_answer(
    tmp_path: Path, fake_bin: Path, release_cache: Path, monkeypatch
) -> None:
    """A machine that never had a bundle extracted is the case a *missing manifest*
    reaches, which no other test here takes: every one of them stages one first.

    `STAGING_DIR` is pointed at a path that does not exist rather than left alone,
    because the real one may exist on the machine running this and the test would
    then read whatever it holds.
    """
    released('lazygit', 'lazygit version 0.44.0')
    monkeypatch.setenv('DOTFILES_BUNDLE', str(tmp_path / 'never-extracted'))
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
    released('lazygit', 'lazygit version 0.44.0')
    staged_bundle(tmp_path, monkeypatch, {'lazygit': '0.45.0'})
    cached(release_cache, {'jesseduffield/lazygit': 'v0.46.0'})
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)

    found = changes(live)

    assert [(change.item, change.verdict) for change in found] == [('ghrelease/lazygit', Verdict.STALE)]
    assert 'v0.46.0' in found[0].detail, 'the release cache is the upstream online, never the bundle'


def test_a_check_that_may_not_refresh_never_reaches_the_network(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    """`check` runs at a prompt and unattended on a timer. The default must not
    spend one API call per declared release."""
    released('lazygit', 'lazygit version 0.44.0')
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)

    observed = packages.RESOURCE.observe(live, live.plan)

    assert observed.consulted_network is False


def test_offline_never_refreshes_however_it_was_asked(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    """`--refresh` means "spend the network on being current", and there is none."""
    released('lazygit', 'lazygit version 0.44.0')
    live = dc.replace(session(tmp_path, LAZYGIT, DECLARES_LAZYGIT), refresh=True, offline=True)

    observed = packages.RESOURCE.observe(live, live.plan)

    assert observed.consulted_network is False


# ─────────────────────────────────────────────────────────────────────────────
# --reinstall: installing again what measuring calls fine
# ─────────────────────────────────────────────────────────────────────────────


def test_a_reinstall_makes_an_installed_tool_actionable(tmp_path: Path, fake_bin: Path) -> None:
    go_installed('task')
    live = dc.replace(session(tmp_path, GO_TOOL, DECLARES_TASK), reinstall=True)

    found = changes(live)

    assert [(change.item, change.verdict) for change in found] == [('go/task', Verdict.STALE)]
    assert found[0].actionable


def test_an_installed_tool_is_left_alone_without_the_flag(tmp_path: Path, fake_bin: Path) -> None:
    """The default, and the thing the flag exists to override: a tool that measures
    fine is not touched."""
    go_installed('task')

    assert changes(session(tmp_path, GO_TOOL, DECLARES_TASK)) == ()


def test_a_reinstall_reaches_what_currency_cannot_measure(tmp_path: Path, fake_bin: Path, release_cache: Path) -> None:
    """The reason it is checked ahead of the comparison rather than after. A version
    string nothing can parse is UNKNOWN and `Repair.NONE`, so measuring alone can
    never repair it — and that is exactly the tool worth reinstalling."""
    released('lazygit', 'built from source')
    cached(release_cache, {'jesseduffield/lazygit': 'v0.45.0'})
    live = dc.replace(session(tmp_path, LAZYGIT, DECLARES_LAZYGIT), reinstall=True)

    found = changes(live)

    assert [(change.verdict, change.repair) for change in found] == [(Verdict.STALE, Repair.AUTOMATIC)]


def test_a_reinstall_of_something_absent_is_still_just_missing(tmp_path: Path, fake_bin: Path) -> None:
    """The flag changes nothing for a tool that is not there: it was already going
    to be installed, and the detail should say why it is in the plan rather than
    reporting a reinstall of something that was never installed."""
    live = dc.replace(session(tmp_path, GO_TOOL, DECLARES_TASK), reinstall=True)

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

    def record(entry, target=None, *, offline=False, again=False, before_place=None, installed=''):
        """The engine's shape rather than only its name.

        `before_place` is what the release provider hands in to displace a package
        once the asset is downloaded and verified, so a spy that ignored it would
        report an install nothing was cleared for — and would pass every ordering
        assertion below while the real engine did something else.

        `installed` is the version floor the two providers with a bundle fallback
        take. Accepted and ignored: what it governs is which *source* answers, and
        nothing here has a source to choose between.
        """
        if before_place is not None:
            cleared = before_place()
            if not cleared.ok:
                return cleared
        attempted.append(entry.name)
        return ghrelease.Result(True, f'{entry.name} installed', kind=Kind.APPLIED)

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


# ─────────────────────────────────────────────────────────────────────────────
# Migrating a release off the package manager that owns its name
# ─────────────────────────────────────────────────────────────────────────────
#
# The end-to-end half of `tests/resources/test_superseded_packages.py`, which
# measures the blocker and the advice. This drives the real `perform`, because a
# green measurement says nothing about whether the removal actually happens or
# whether it happens first.

SYNCTHING = {'github_releases': [{'name': 'syncthing', 'repo': 'syncthing/syncthing', 'supersedes': ['syncthing']}]}
DECLARES_SYNCTHING = {'machine': 'box', 'platform': 'linux', 'github_releases': ['syncthing']}

BREW_HOLDING_SYNCTHING = '#!/bin/sh\n[ "$1" = list ] || exit 0\ncase "$2" in --formula) printf \'syncthing\\n\' ;; esac\n'
"""A Homebrew holding syncthing as a formula, and as nothing else.

The `--formula`/`--cask` split is the real client's, and encoding it is what stops
the fake agreeing with every question put to it: answered for both, one installed
package reads as two and the blocker is reported under whichever list was asked
first. `standards/testing.md` § "A fake enforces the service's constraints".
"""


@pytest.fixture
def only_brew_answers(fake_bin: Path) -> None:
    """Every other package manager refusing, so the host's distro cannot answer.

    The hazard `fake_bin`'s own docstring names, reached here for real: this desk's
    pacman holds a syncthing, so an unshadowed run reported the blocker under
    `pacman` and would report none at all on a runner. The sandbox shadows the same
    list for the same reason.
    """
    for refused in PACKAGE_MANAGERS:
        executable(fake_bin, refused, REFUSED)


@pytest.fixture
def removals(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, list[str]]]:
    """Record what would be removed, instead of taking a package off this machine.

    Patched at `syspkg` rather than at the provider, so what is asserted is the
    manager and the names the engine resolved — `standards/testing.md` § "Assert
    invariants by spying on argv, not by inspecting the result".
    """
    attempted: list[tuple[str, list[str]]] = []

    def record(manager: str, names, privilege) -> ghrelease.Result:
        attempted.append((manager, list(names)))
        return ghrelease.Result(True, f'{manager}: removed', kind=Kind.APPLIED)

    monkeypatch.setattr(syspkg, 'uninstall', record)
    return attempted


def test_a_release_a_manager_still_owns_is_refused_rather_than_installed_beside_it(
    tmp_path: Path, fake_bin: Path, only_brew_answers: None, installs: list[str], removals: list, unprivileged: Privilege
) -> None:
    """Both copies ship a service, so installing over it leaves two daemons on one
    config directory — worse than either state alone."""
    executable(fake_bin, 'brew', BREW_HOLDING_SYNCTHING)
    live = session(tmp_path, SYNCTHING, DECLARES_SYNCTHING)

    change = only_change(live)

    assert change.repair is Repair.BY_HAND
    assert not change.actionable
    assert installs == []


def test_force_removes_the_package_and_installs_the_release(
    tmp_path: Path, fake_bin: Path, only_brew_answers: None, installs: list[str], removals: list, unprivileged: Privilege
) -> None:
    executable(fake_bin, 'brew', BREW_HOLDING_SYNCTHING)
    live = dc.replace(session(tmp_path, SYNCTHING, DECLARES_SYNCTHING), force=True)

    change = only_change(live)
    outcome = packages.RESOURCE.perform(live, change, unprivileged)

    assert change.actionable
    assert outcome.status is OutcomeStatus.DONE
    assert removals == [('brew', ['syncthing'])]
    assert installs == ['syncthing']


def test_a_removal_that_fails_stops_the_install(
    tmp_path: Path, fake_bin: Path, only_brew_answers: None, installs: list[str], monkeypatch: pytest.MonkeyPatch, unprivileged: Privilege
) -> None:
    """The ordering, asserted by what happens when the first half does not.

    Placing the release binary while the package's service is still loaded is the
    two-daemon state the refusal exists to prevent, so a removal that failed must
    not be followed by the install it was clearing the way for.
    """
    executable(fake_bin, 'brew', BREW_HOLDING_SYNCTHING)
    monkeypatch.setattr(syspkg, 'uninstall', lambda *_: ghrelease.Result(False, 'brew said no', kind=Kind.COMMAND_FAILED))
    live = dc.replace(session(tmp_path, SYNCTHING, DECLARES_SYNCTHING), force=True)

    outcome = packages.RESOURCE.perform(live, only_change(live), unprivileged)

    assert outcome.status is OutcomeStatus.FAILED
    assert installs == []


def test_a_release_that_cannot_be_fetched_leaves_the_package_installed(
    tmp_path: Path, fake_bin: Path, only_brew_answers: None, removals: list, monkeypatch: pytest.MonkeyPatch, unprivileged: Privilege
) -> None:
    """The other half of the ordering, and the one that costs the machine its tool.

    Every step before the write can fail — an unresolvable tag, a refused download,
    a checksum that does not match — and the box being displaced is the box that has
    syncthing. Removing first and failing there stops the fleet's file sync with
    nothing installed in its place, so the removal has to sit after the bytes are on
    disk and verified.
    """
    executable(fake_bin, 'brew', BREW_HOLDING_SYNCTHING)

    def unreachable(entry, target=None, *, offline=False, before_place=None):
        return ghrelease.Result(False, 'someone/syncthing did not answer with a release', kind=Kind.VERSION_UNRESOLVED)

    monkeypatch.setattr(ghrelease, 'install', unreachable)
    live = dc.replace(session(tmp_path, SYNCTHING, DECLARES_SYNCTHING), force=True)

    outcome = packages.RESOURCE.perform(live, only_change(live), unprivileged)

    assert outcome.status is OutcomeStatus.FAILED
    assert removals == []


def test_a_release_nothing_else_owns_is_installed_without_removing_anything(
    tmp_path: Path, fake_bin: Path, only_brew_answers: None, installs: list[str], removals: list, unprivileged: Privilege
) -> None:
    """`--force` authorises a removal; it does not ask for one. A machine that has
    already migrated must not have a package taken off it on every apply."""
    live = dc.replace(session(tmp_path, SYNCTHING, DECLARES_SYNCTHING), force=True)

    packages.RESOURCE.perform(live, only_change(live), unprivileged)

    assert removals == []
    assert installs == ['syncthing']


def test_a_binary_that_is_only_unsupervised_is_supervised_rather_than_reinstalled(
    tmp_path: Path, fake_bin: Path, only_brew_answers: None, installs: list[str], monkeypatch: pytest.MonkeyPatch, unprivileged: Privilege
) -> None:
    """`evidence` reports an unsupervised daemon as MISSING, and the repair for that
    is not a download.

    Left to fall through, the row spends a tag resolution, a download and a checksum
    on a state no download changes — every apply, for as long as the supervisor will
    not load, while `check` goes on reporting the same drift.
    """
    (tmp_path / 'home' / '.local' / 'bin').mkdir(parents=True, exist_ok=True)
    (tmp_path / 'home' / '.local' / 'bin' / 'syncthing').write_text('#!/bin/sh\n')
    supervised: list[str] = []

    def record(entry: catalog.GithubRelease, target: Target) -> providers.Result:
        supervised.append(entry.name)
        return APPLIED_NOTHING

    monkeypatch.setattr(ghrelease, 'unsupervised', lambda name, executable: 'the agent is not loaded')
    monkeypatch.setattr(ghrelease, 'supervise', record)
    live = session(tmp_path, SYNCTHING, DECLARES_SYNCTHING)

    outcome = packages.RESOURCE.perform(live, only_change(live), unprivileged)

    assert outcome.status is OutcomeStatus.DONE
    assert supervised == ['syncthing']
    assert installs == [], 'a supervisor that would not load cost a full release download'


APPLIED_NOTHING = ghrelease.Result(True, 'supervised', kind=Kind.APPLIED)


def test_a_stale_release_is_upgraded_rather_than_reported(
    tmp_path: Path, fake_bin: Path, release_cache: Path, installs: list[str], unprivileged: Privilege
) -> None:
    """The verdict the phase registry cannot act on, because a phase has no plan
    to read it from."""
    cached(release_cache, {'jesseduffield/lazygit': 'v0.45.0'})
    released('lazygit', 'lazygit version 0.44.0')
    live = session(tmp_path, LAZYGIT, DECLARES_LAZYGIT)

    change = only_change(live)
    assert change.verdict is Verdict.STALE
    assert packages.RESOURCE.perform(live, change, unprivileged).status is OutcomeStatus.DONE
    assert installs == ['lazygit']


# Names no machine can have, because `fake_bin` keeps /usr/bin behind it: a real
# package would read as installed on whichever box happens to have it, which is the
# hazard that fixture's docstring names.
CARGO_PACKAGE = {'cargo_packages': [{'name': 'unbuilt-crate', 'command': 'unbuilt-crate'}]}
DECLARES_CARGO = {'machine': 'box', 'platform': 'linux', 'cargo_packages': ['unbuilt-crate']}

NPM_GLOBAL = {'npm_globals': {'linters': [{'name': 'unpublished-linter'}]}}
DECLARES_NPM = {'machine': 'box', 'platform': 'linux', 'npm_globals': ['unpublished-linter']}

UV_TOOL = {'uv_tools': {'linters': [{'name': 'unreleased-linter'}]}}
DECLARES_UV = {'machine': 'box', 'platform': 'linux', 'uv_tools': ['unreleased-linter']}

DECLARES_THEME = {'machine': 'box', 'platform': 'linux', 'custom_installers': ['theme']}
THEME = {'custom_installers': [{'name': 'theme', 'description': 'theme manager', 'repo': 'datapointchris/theme'}]}

OWNED: tuple[tuple[str, dict, dict, str], ...] = (
    ('release', LAZYGIT, DECLARES_LAZYGIT, 'lazygit'),
    ('uv_tool', UV_TOOL, DECLARES_UV, 'unreleased-linter'),
    ('npm_global', NPM_GLOBAL, DECLARES_NPM, 'unpublished-linter'),
    ('cargo_package', CARGO_PACKAGE, DECLARES_CARGO, 'unbuilt-crate'),
    ('go_tool', GO_TOOL, DECLARES_TASK, 'task'),
    ('custom_installer', THEME, DECLARES_THEME, 'theme'),
)
"""One declaration per section, and the name whichever provider owns it installs."""


@pytest.mark.parametrize(('declaration', 'manifest', 'installed'), [row[1:] for row in OWNED], ids=[section for section, *_ in OWNED])
def test_a_missing_tool_is_installed_by_the_provider_that_owns_it(
    declaration: dict,
    manifest: dict,
    installed: str,
    tmp_path: Path,
    fake_bin: Path,
    release_cache: Path,
    uv_tools: Path,
    installs: list[str],
    unprivileged: Privilege,
) -> None:
    """Through the same function the phase calls, so the two front doors cannot
    install one tool differently.

    Every section in one table, because the claim is about the dispatch rather
    than about any provider: the resource picks the owner off the declaration and
    the provider it picked is the only one that runs.
    """
    live = session(tmp_path, declaration, manifest)

    outcome = packages.RESOURCE.perform(live, only_change(live), unprivileged)

    assert outcome.status is OutcomeStatus.DONE
    assert installs == [installed]


@pytest.mark.parametrize(
    ('declaration', 'manifest', 'arrived'),
    [
        pytest.param(LAZYGIT, DECLARES_LAZYGIT, 'lazygit', id='release'),
        pytest.param(THEME, DECLARES_THEME, 'theme', id='custom_installer'),
    ],
)
def test_a_tool_that_arrived_since_the_report_is_skipped(
    declaration: dict, manifest: dict, arrived: str, tmp_path: Path, fake_bin: Path, installs: list[str], unprivileged: Privilege
) -> None:
    """`observe` ran before the report was printed and before any earlier stage
    installed anything. Reinstalling over what turned up would replace a binary
    nobody asked about with whatever upstream calls latest now."""
    live = session(tmp_path, declaration, manifest)
    change = only_change(live)
    released(arrived)

    outcome = packages.RESOURCE.perform(live, change, unprivileged)

    assert outcome.status is OutcomeStatus.SKIPPED
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
    cargo_installed('frob')
    live = session(tmp_path, CARGO_TOOL, DECLARES_FROB)

    assert shadow_changes(live) == []


def test_a_second_copy_on_path_is_reported_against_the_item_that_declares_it(
    tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Which of the two runs is decided by PATH order rather than by the manifest,
    and the loser is invisible to every other check: `apply` installs, evidence
    finds *a* binary, and the machine reports converged while the tool anyone
    actually runs came from somewhere else."""
    cargo_installed('frob')
    stray = executable(second_bin(tmp_path, monkeypatch), 'frob')
    live = session(tmp_path, CARGO_TOOL, DECLARES_FROB)

    found = shadow_changes(live)

    assert [change.item for change in found] == ['cargo/frobnicate']
    assert found[0].observed == str(stray)
    assert found[0].detail.endswith('.cargo/bin/frob'), 'the copy that wins is named, abbreviated under ~'


def test_a_second_copy_is_not_something_apply_can_repair(tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`check`'s subject and not `plan`'s. The declaration says what should be
    installed and cannot say which of two copies may be removed safely, so an
    `apply` that deleted one would be acting on a judgement nobody declared."""
    cargo_installed('frob')
    executable(second_bin(tmp_path, monkeypatch), 'frob')
    live = session(tmp_path, CARGO_TOOL, DECLARES_FROB)

    change = shadow_changes(live)[0]

    assert change.repair is Repair.BY_HAND
    assert change.drifted and not change.actionable


def test_the_same_binary_reachable_twice_is_one_installation(tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`~/.local/bin/fd` pointing at `/usr/bin/fd` is one tool with two names.
    Counting paths rather than real paths reports every symlinked companion this
    repo deploys on purpose."""
    real = cargo_installed('frob')
    (second_bin(tmp_path, monkeypatch) / 'frob').symlink_to(real)
    live = session(tmp_path, CARGO_TOOL, DECLARES_FROB)

    assert shadow_changes(live) == []


def test_a_copy_a_declared_package_owns_is_explained(tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The pair that made the shell script unreadable: fnm owns `node` and `npm`
    while pacman's `nodejs` ships `/usr/bin/node` underneath, and that second copy
    is the bootstrap the declaration asks for. Asking the package manager who put
    a file there is what separates it from a stray."""
    cargo_installed('frob')
    executable(second_bin(tmp_path, monkeypatch), 'frob')
    executable(fake_bin, 'pacman', OWNED_BY_FROBNICATE)
    declared = {**CARGO_TOOL, 'system_packages': [{'name': 'frobnicate', 'apt': 'frobnicate', 'pacman': 'frobnicate'}]}
    live = session(tmp_path, declared, {**DECLARES_FROB, 'system_packages': 'workstation'})

    assert shadow_changes(live) == []


def test_asking_whether_a_manager_answers_follows_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The probe behind `owner_of` is cached, and PATH is not fixed for the life of
    a process — `toolchain.put_on_path` extends it as each runtime lands, and every
    test here hands the resource a PATH of its own.

    Cached under the bare name, the first answer answered for every later one. On
    a runner with no real pacman that meant one test's "there is no pacman" stood
    while the next test's fake pacman sat on PATH being ignored, so a copy the
    declaration explains was reported as a stray.
    """
    absent, present = tmp_path / 'absent', tmp_path / 'present'
    absent.mkdir()
    present.mkdir()
    executable(present, 'pacman')

    monkeypatch.setenv('PATH', str(absent))
    assert not syspkg._answers('pacman')

    monkeypatch.setenv('PATH', f'{present}{os.pathsep}{absent}')
    assert syspkg._answers('pacman')


def test_a_copy_an_undeclared_package_owns_is_still_a_stray(tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The inverse, and the direction that must not fail open: a package manager
    answering at all is not an explanation, or every `/usr/bin` copy on a Linux
    box would excuse itself."""
    cargo_installed('frob')
    executable(second_bin(tmp_path, monkeypatch), 'frob')
    executable(fake_bin, 'pacman', OWNED_BY_FROBNICATE)
    live = session(tmp_path, CARGO_TOOL, DECLARES_FROB)

    assert [change.item for change in shadow_changes(live)] == ['cargo/frobnicate']


def test_a_copy_inside_the_checkout_is_not_machine_state(tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`uv run dotfiles check` from the repo puts `.venv/bin` first on PATH, so
    every tool the dev environment also carries reads as duplicated. A second copy
    that exists for the duration of a development command is not the machine."""
    cargo_installed('frob')
    live = session(tmp_path, CARGO_TOOL, DECLARES_FROB)
    inside = live.repo / '.venv' / 'bin'
    inside.mkdir(parents=True)
    executable(inside, 'frob')
    monkeypatch.setenv('PATH', f'{inside}{os.pathsep}{os.environ["PATH"]}')

    assert shadow_changes(live) == []


# ─────────────────────────────────────────────────────────────────────────────
# An own tool the machine has and does not declare
# ─────────────────────────────────────────────────────────────────────────────

GO_VERSION_M = "#!/bin/sh\ncat <<'END'\n{body}\nEND\n"
"""A `go` that answers `version -m` and nothing else, which is all the probe asks."""


def fake_go(monkeypatch: pytest.MonkeyPatch, directory: Path, *built: tuple[str, str]) -> None:
    """Placed on disk *and* named as the toolchain, because putting it on PATH is
    no longer enough to be asked.

    `installed_modules` resolves through `toolchain.go_command`, which prefers the
    Go this repo unpacked over anything PATH offers — that is the whole point of
    it, and it means a stub reachable only by PATH is silently stepped over on any
    machine that has a real /usr/local/go.
    """
    lines = []
    for binary, module in built:
        lines.append(f'/go/bin/{binary}: go1.26.5')
        lines.append(f'\tpath\t{module}')
        lines.append(f'\tmod\t{module}\tv1.0.0\th1:abc=')
    stubbed = executable(directory, 'go', GO_VERSION_M.format(body='\n'.join(lines)))
    monkeypatch.setattr(gotool.toolchain, 'go_command', lambda: str(stubbed))


def go_bin(tmp_path: Path) -> Path:
    """The run's own home, which is `session`'s and not the process's."""
    directory = tmp_path / 'home' / 'go' / 'bin'
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def undeclared_own(live: Session) -> list[Change]:
    """The findings with no declared item behind them, which is what makes them
    this check's rather than the shadowing one's."""
    return [change for change in changes(live) if change.verdict is Verdict.UNDECLARED and change.desired is None]


def test_an_installed_tool_from_a_declared_owner_that_nothing_declares_is_reported(
    tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The direction nothing else looks. Every other measurement reads down from
    the declaration; this reads up from the machine. `fleet` sat installed on two
    workstations with no entry in packages.yml, and no verb could say so."""
    go_bin(tmp_path)
    fake_go(monkeypatch, fake_bin, ('frobnicate', 'github.com/go-task/frobnicate'))
    live = session(tmp_path, GO_TOOL, DECLARES_TASK)

    found = undeclared_own(live)

    assert [change.item for change in found] == ['frobnicate']
    assert 'github.com/go-task/frobnicate' in found[0].detail


def test_a_tool_built_by_somebody_else_is_not_ours_to_report(tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A machine is full of Go binaries nobody here published. Owner is the whole
    of the claim, and it comes out of the binary rather than off its name."""
    go_bin(tmp_path)
    fake_go(monkeypatch, fake_bin, ('ripgrep-go', 'github.com/someone-else/ripgrep-go'))
    live = session(tmp_path, GO_TOOL, DECLARES_TASK)

    assert undeclared_own(live) == []


def test_a_declared_tool_is_not_also_reported_undeclared(tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    go_bin(tmp_path)
    fake_go(monkeypatch, fake_bin, ('task', 'github.com/go-task/task'))
    executable(fake_bin, 'task')
    live = session(tmp_path, GO_TOOL, DECLARES_TASK)

    assert undeclared_own(live) == []


def test_a_machine_declaring_no_owned_tools_reports_none_of_theirs(tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Owners come from the plan because that is this repo's whole basis for
    calling a module ours. With none declared there is no claim to make, and
    inventing one would report every Go binary on the box."""
    go_bin(tmp_path)
    fake_go(monkeypatch, fake_bin, ('frobnicate', 'github.com/go-task/frobnicate'))
    system_only = {'system_packages': [{'name': 'frobnicate', 'apt': 'frobnicate', 'pacman': 'frobnicate'}]}
    live = session(tmp_path, system_only, {'machine': 'box', 'platform': 'linux', 'system_packages': 'workstation'})

    assert undeclared_own(live) == []


def test_an_undeclared_own_tool_is_not_something_apply_can_repair(tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Declaring it and deleting it are both defensible and the declaration says
    neither, so this is `check`'s to report and nobody's to write."""
    go_bin(tmp_path)
    fake_go(monkeypatch, fake_bin, ('frobnicate', 'github.com/go-task/frobnicate'))
    live = session(tmp_path, GO_TOOL, DECLARES_TASK)

    change = undeclared_own(live)[0]

    assert change.repair is Repair.BY_HAND
    assert change.advice


def test_a_run_narrowed_to_one_package_reports_none_of_the_others(tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`--package` narrows the declaration, and this reads the machine against it.
    Answering from a one-entry plan calls every other tool of that owner
    undeclared and advises removing the only copy on the box."""
    go_bin(tmp_path)
    fake_go(monkeypatch, fake_bin, ('task', 'github.com/go-task/task'), ('gum', 'github.com/go-task/gum'))
    executable(fake_bin, 'task')
    executable(fake_bin, 'gum')
    declares_both = {
        'go_tools': [
            {'name': 'task', 'package': 'github.com/go-task/task/v3/cmd/task'},
            {'name': 'gum', 'package': 'github.com/go-task/gum'},
        ]
    }
    live = session(tmp_path, declares_both, {'machine': 'box', 'platform': 'linux', 'go_tools': ['task', 'gum']})

    assert undeclared_own(dc.replace(live, packages=frozenset({'task'}))) == []


def test_a_run_narrowed_to_an_owner_still_answers(tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`--owner` narrows to that owner's whole set, so the declaration still
    explains everything of theirs the machine holds."""
    go_bin(tmp_path)
    fake_go(monkeypatch, fake_bin, ('frobnicate', 'github.com/go-task/frobnicate'))
    live = session(tmp_path, GO_TOOL, DECLARES_TASK)

    found = undeclared_own(dc.replace(live, owner='go-task'))

    assert [change.item for change in found] == ['frobnicate']


def test_a_go_that_cannot_answer_reports_nothing_rather_than_failing(tmp_path: Path, fake_bin: Path) -> None:
    """A box with no Go toolchain, or one too old to carry build info, has nothing
    to say here. A probe that raised would take the whole of `check` down with it."""
    go_bin(tmp_path)
    executable(fake_bin, 'go', '#!/bin/sh\nexit 1\n')
    live = session(tmp_path, GO_TOOL, DECLARES_TASK)

    assert undeclared_own(live) == []


def test_a_probe_that_raises_is_recorded_rather_than_dropped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Serially a raising probe propagated and the resource refused, so the
    failure had somewhere to be read. Caught and dropped by the pool it is
    indistinguishable from a tool that answered and reported no version — which is
    a row saying nothing is wrong.

    Dropped is still the right outcome: one unaskable binary must not take the
    whole resource down. What this pins is that it leaves a trace."""

    def raises(item: object) -> str:
        raise RuntimeError('the binary is a directory')

    live = session(tmp_path, CARGO_TOOL, DECLARES_FROB)
    (item,) = live.plan.for_resource('packages')
    monkeypatch.setattr(packages, '_installed_version', raises)

    with caplog.at_level('DEBUG'):
        assert packages._reported_versions((item,)) == {}

    assert any('probe failed' in record.getMessage() for record in caplog.records)
