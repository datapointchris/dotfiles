"""Putting a language runtime on a machine: what each version manager decides.

No network and no subprocesses, the same seam `test_custom_installers.py` uses —
`effects.fetch` and `effects.run` recorded rather than performed. What a runtime
installer *is* is a decision about where to get it and what to do with it, so the
interesting assertion is what it decided rather than whether it worked.

Root is its own recorder. `privilege.run` binds `effects.run` at import, so
patching the effect does not reach it — and the two questions are different
anyway: whether the tarball was fetched, and whether the machine was asked for a
password.
"""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest

from dotfiles import effects
from dotfiles import github_release
from dotfiles import paths
from dotfiles import providers
from dotfiles.coordinates import Arch
from dotfiles.coordinates import OSFamily
from dotfiles.coordinates import Target
from dotfiles.effects import Completed
from dotfiles.privilege import Authorization
from dotfiles.privilege import PrivilegeUnavailable
from dotfiles.providers import Kind
from dotfiles.providers import toolchain

LINUX = Target(OSFamily.LINUX, Arch.X86_64)
DARWIN = Target(OSFamily.DARWIN, Arch.ARM64)

RELEASE = 'go1.26.5'


class Runs:
    """Every command an installer would have started, with the environment it set.

    The env matters here in a way it does not for the custom installers: `FNM_DIR`
    decides where the default alias lands, and `.zshenv` names that path.
    """

    def __init__(self, **answers: Completed) -> None:
        self.answers = answers
        self.calls: list[tuple[str, ...]] = []
        self.envs: list[dict[str, str]] = []

    # `**_bounds` so a caller adding a timeout is not a test failure. `effects.run`
    # takes more than these four, and a double that mirrors a subset turns every
    # new argument into a TypeError in a test that is not about that argument.
    def __call__(self, command, *, cwd=None, env=None, output=effects.Output.STREAM, **_bounds) -> Completed:
        argv = tuple(str(part) for part in command)
        self.calls.append(argv)
        self.envs.append(dict(env or {}))
        return next((answer for key, answer in self.answers.items() if any(key in part for part in argv)), Completed(argv, 0, 'ok'))

    def ran(self, *fragments: str) -> bool:
        return any(all(any(fragment in part for part in argv) for fragment in fragments) for argv in self.calls)


class Fetches:
    """Every URL an installer would have downloaded, with a body per URL."""

    def __init__(
        self,
        bodies: dict[str, bytes] | None = None,
        refuse: tuple[str, ...] = (),
        reason: str = 'ConnectError: certificate verify failed: unable to get local issuer certificate',
    ) -> None:
        self.bodies = bodies or {}
        self.refuse = refuse
        self.reason = reason
        self.urls: list[str] = []

    def __call__(self, url: str, destination: Path, **_kwargs) -> github_release.Fetched:
        """`Fetched`, not a bool, because that is what `effects.fetch` answers.

        A double returning a bare `False` would still read as a failure at every
        `if not fetch(...)`, so this is not about the branch — it is about `.reason`,
        which the providers now quote into their own messages. A refusal carries the
        text a TLS-intercepting proxy would produce, so a test can assert the cause
        survives the trip rather than only that the install failed.
        """
        self.urls.append(url)
        if any(part in url for part in self.refuse):
            return github_release.Fetched(False, self.reason)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.bodies.get(url, b'#!/bin/sh\necho installed\n'))
        return github_release.Fetched(True)


class Root:
    """A `Privilege` that records rather than escalating.

    `granted=False` is the machine with no sudo and the declined password at once:
    both raise `PrivilegeUnavailable` from `run`, and both are what the container
    harnesses are.
    """

    def __init__(self, *, granted: bool = True) -> None:
        self.granted = granted
        self.state = Authorization.GRANTED if granted else Authorization.UNAVAILABLE
        self.calls: list[tuple[str, ...]] = []

    def run(self, command, *, reason: str, output=effects.Output.QUIET) -> Completed:
        argv = tuple(str(part) for part in command)
        if not self.granted:
            raise PrivilegeUnavailable(reason)
        self.calls.append(argv)
        return Completed(argv, 0, '')

    def ran(self, fragment: str) -> bool:
        return any(fragment in part for argv in self.calls for part in argv)


@pytest.fixture
def home(tmp_path, monkeypatch) -> Path:
    root = tmp_path / 'home'
    (root / '.local' / 'bin').mkdir(parents=True)
    monkeypatch.setenv('HOME', str(root))
    monkeypatch.setenv('PATH', str(root / '.local' / 'bin'))
    monkeypatch.delenv('FNM_DIR', raising=False)
    return root


@pytest.fixture
def bundle(tmp_path, monkeypatch) -> Path:
    root = tmp_path / 'staged'
    staged = root / 'dotfiles-offline-v20260814T190203Z-box-linux-x86_64'
    (staged / 'scripts').mkdir(parents=True)
    (staged / providers.MANIFEST).write_text('')
    monkeypatch.setenv('DOTFILES_BUNDLE', str(root))
    return staged


@pytest.fixture
def effected(monkeypatch):
    """Install the two recorders, defaulting to "everything worked, silently"."""

    def install(runs: Runs | None = None, fetches: Fetches | None = None) -> tuple[Runs, Fetches]:
        runs, fetches = runs or Runs(), fetches or Fetches()
        monkeypatch.setattr(effects, 'run', runs)
        monkeypatch.setattr(effects, 'fetch', fetches)
        return runs, fetches

    return install


def go_tarball(*, contains_go: bool = True) -> bytes:
    """A tarball shaped like go.dev's: everything under a top-level `go/`."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
        member = tarfile.TarInfo('go/bin/go' if contains_go else 'go/README')
        payload = b'#!/bin/sh\necho go version\n'
        member.size = len(payload)
        member.mode = 0o755
        archive.addfile(member, io.BytesIO(payload))
    return buffer.getvalue()


def answers(monkeypatch, release: str | None) -> None:
    monkeypatch.setattr(toolchain, 'latest_release', lambda url=toolchain.GO_VERSION_URL: release)


# ─────────────────────────────────────────────────────────────────────────────
# Naming: Go publishes Go's names, not this repo's
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(('target', 'expected'), [(LINUX, 'linux-amd64'), (DARWIN, 'darwin-arm64')])
def test_the_tarball_is_named_the_way_go_dev_names_it(target: Target, expected: str) -> None:
    """`amd64`, where `Arch` spells the same CPU `x86_64`. A release asset is named
    by whoever publishes it, and the Mac is the platform serving two architectures
    — so a fused guess is invisible from whichever Mac happens to run it."""
    assert toolchain.go_platform(target) == expected


def test_the_current_release_is_the_first_line_go_dev_serves(monkeypatch) -> None:
    monkeypatch.setattr(github_release, 'request', lambda url, accept=None: b'go1.26.5\ntime 2026-07-30T00:00:00Z\n')

    assert toolchain.latest_release() == 'go1.26.5'


def test_an_unreachable_go_dev_answers_none_rather_than_raising(monkeypatch) -> None:
    """One runtime that cannot be resolved must not end the walk for the other
    three, which is why every failure here is a value."""

    def refuse(url, accept=None):
        raise OSError('no route to host')

    monkeypatch.setattr(github_release, 'request', refuse)

    assert toolchain.latest_release() is None


# ─────────────────────────────────────────────────────────────────────────────
# go
# ─────────────────────────────────────────────────────────────────────────────


def test_go_offline_says_what_the_bundle_lacks_and_asks_for_nothing(home, bundle, effected) -> None:
    """Nothing stages the Go tarball, so an offline run is refused with the reason
    rather than left to fail inside a download.

    `refused`, not merely `not ok`: the Go tools this runtime would build come out
    of the bundle prebuilt, so an offline machine without it is converged. Counting
    this as a failure made the offline environment permanently red.
    """
    runs, fetches = effected()

    result = toolchain.install_go(LINUX, Root(), offline=True)

    assert not result.ok
    assert result.refused
    assert result.kind is Kind.NOT_IN_BUNDLE
    assert str(paths.staging_dir()) in result.detail
    assert fetches.urls == []


def test_go_that_cannot_be_resolved_is_not_downloaded(home, bundle, effected, monkeypatch) -> None:
    """The home-directory fallback below needs a version to name a file, so an
    unreachable go.dev fails here rather than there."""
    runs, fetches = effected()
    answers(monkeypatch, None)

    result = toolchain.install_go(LINUX, Root(), offline=False)

    assert not result.ok
    assert result.kind is Kind.VERSION_UNRESOLVED
    assert fetches.urls == []


def test_go_is_unpacked_as_this_user_and_moved_in_as_root(home, bundle, effected, monkeypatch) -> None:
    """`effects.unpack` extracts under `filter='data'`, which refuses absolute
    paths, `..` traversal and device nodes. Handing the tar to `sudo tar` instead
    would apply no filter to an archive off the internet."""
    url = f'{toolchain.GO_DOWNLOAD_URL}/{RELEASE}.linux-amd64.tar.gz'
    runs, fetches = effected(fetches=Fetches({url: go_tarball()}))
    answers(monkeypatch, RELEASE)
    root = Root()

    result = toolchain.install_go(LINUX, root, offline=False)

    assert result.ok, result.detail
    assert result.kind is Kind.APPLIED
    assert fetches.urls == [url]
    assert root.ran('rm') and root.ran(str(toolchain.GO_ROOT))
    assert runs.ran(str(toolchain.GO_ROOT / 'bin' / 'go'), 'version')


def test_go_sets_gonosumdb_for_the_namespace_that_stalls_without_it(home, bundle, effected, monkeypatch) -> None:
    """A cold sum.golang.org lookup for a just-published version holds for ~60s
    and then answers 500, so an own-namespace tool tagged minutes ago stalls."""
    url = f'{toolchain.GO_DOWNLOAD_URL}/{RELEASE}.linux-amd64.tar.gz'
    runs, _ = effected(fetches=Fetches({url: go_tarball()}))
    answers(monkeypatch, RELEASE)

    # Nothing to resolve, so only a caller that passes the binary it just unpacked
    # writes anything. Both halves are the guard: asserting the arguments alone
    # passed on a developer Mac carrying Go at GO_ROOT and failed on
    # ubuntu-latest carrying none, and asserting the path alone would pass again
    # on that same Mac because the resolver would answer with it.
    monkeypatch.setattr(toolchain, 'go_command', lambda: None)

    toolchain.install_go(LINUX, Root(), offline=False)

    assert runs.ran(str(toolchain.GO_ROOT / 'bin' / 'go'), 'env', '-w', f'GONOSUMDB={toolchain.GONOSUMDB}')


def test_go_without_root_reports_the_refusal_and_writes_nothing(home, bundle, effected, monkeypatch) -> None:
    """Declined or unavailable privilege is not fatal, which is what lets the
    Docker and LXC harnesses converge without a passwordless-sudo carve-out."""
    url = f'{toolchain.GO_DOWNLOAD_URL}/{RELEASE}.linux-amd64.tar.gz'
    runs, _ = effected(fetches=Fetches({url: go_tarball()}))
    answers(monkeypatch, RELEASE)
    root = Root(granted=False)

    result = toolchain.install_go(LINUX, root, offline=False)

    assert not result.ok
    assert result.kind is Kind.PRIVILEGE_UNAVAILABLE
    assert root.calls == []


def test_a_tarball_carrying_no_go_binary_is_refused_before_root_is_asked(home, bundle, effected, monkeypatch) -> None:
    """The whole tree is replaced, so a bad archive would take the working Go with
    it. Checked while it is still in a temporary directory nobody has escalated for."""
    url = f'{toolchain.GO_DOWNLOAD_URL}/{RELEASE}.linux-amd64.tar.gz'
    effected(fetches=Fetches({url: go_tarball(contains_go=False)}))
    answers(monkeypatch, RELEASE)
    root = Root()

    result = toolchain.install_go(LINUX, root, offline=False)

    assert not result.ok
    assert result.kind is Kind.ARCHIVE_INCOMPLETE
    assert root.calls == []


def test_a_tarball_left_in_home_is_used_when_go_dev_will_not_serve_it(home, bundle, effected, monkeypatch) -> None:
    """The work firewall's escape hatch: fetch it by hand somewhere that can reach
    go.dev, drop it in `$HOME`, re-run."""
    name = f'{RELEASE}.linux-amd64.tar.gz'
    (home / name).write_bytes(go_tarball())
    effected(fetches=Fetches(refuse=('go.dev',)))
    answers(monkeypatch, RELEASE)
    root = Root()

    result = toolchain.install_go(LINUX, root, offline=False)

    assert result.ok, result.detail
    assert root.ran(str(toolchain.GO_ROOT))


# ─────────────────────────────────────────────────────────────────────────────
# rust and uv, which are two more vendor scripts
# ─────────────────────────────────────────────────────────────────────────────


def test_rustup_is_told_not_to_touch_the_shell_config(home, bundle, effected) -> None:
    """PATH belongs to this repo: `.zshenv` already names `~/.cargo/bin`, and
    letting rustup append its own line puts a second writer on a file the symlink
    pass owns."""
    runs, _ = effected()

    toolchain.install_rust(offline=False)

    assert runs.ran('-y', '--no-modify-path')


def test_rust_offline_says_the_bundle_stages_no_rustup(home, bundle, effected) -> None:
    effected()

    result = toolchain.install_rust(offline=True)

    assert not result.ok
    assert result.refused
    assert result.kind is Kind.NOT_IN_BUNDLE


def test_uv_already_present_is_not_reinstalled_but_still_sets_the_default(home, bundle, effected) -> None:
    """`install.sh` puts uv on the box before this package exists to be run, so
    the first half is nearly always a no-op. Which Python is *default* afterwards
    is a machine question the bootstrap does not answer."""
    (home / '.local' / 'bin' / 'uv').write_bytes(b'#!/bin/sh\n')
    (home / '.local' / 'bin' / 'uv').chmod(0o755)
    runs, fetches = effected()

    result = toolchain.install_uv(offline=False)

    assert result.ok
    assert result.kind is Kind.APPLIED
    assert fetches.urls == []
    assert runs.ran('python', 'install', '--default', toolchain.DEFAULT_PYTHON)


def test_uv_installs_offline_from_the_script_the_bundle_stages(home, bundle, effected) -> None:
    """The one runtime an offline machine can install, which is why the bundler
    stages this script and not the other three."""
    (bundle / 'scripts' / 'uv-install.sh').write_bytes(b'#!/bin/sh\necho installed\n')
    runs, fetches = effected()

    toolchain.install_uv(offline=True)

    assert fetches.urls == []
    assert runs.ran('bash', 'install.sh')


# ─────────────────────────────────────────────────────────────────────────────
# node
# ─────────────────────────────────────────────────────────────────────────────


def test_node_without_fnm_names_where_fnm_comes_from(home, bundle, effected) -> None:
    """fnm ships as a cargo package, which is why the Node stage sits after the
    tools rather than beside Go."""
    effected()

    result = toolchain.install_node(home, offline=False)

    assert not result.ok
    assert result.kind is Kind.PREREQUISITE_MISSING
    assert 'cargo_packages' in result.detail


def test_node_offline_is_refused_because_nodejs_org_is_not_bundled(home, bundle, effected) -> None:
    """fnm downloads Node from nodejs.org, which nothing stages. Refused rather
    than failed, for the same reason as Go: an offline machine that never had a
    Node to download is not a broken install."""
    fnm = home / '.local' / 'bin' / 'fnm'
    fnm.write_bytes(b'#!/bin/sh\n')
    fnm.chmod(0o755)
    runs, fetches = effected()

    result = toolchain.install_node(home, offline=True)

    assert not result.ok
    assert result.refused
    assert result.kind is Kind.NOT_IN_BUNDLE
    assert runs.calls == [] and fetches.urls == []


def test_node_is_installed_and_aliased_where_zshenv_looks_for_it(home, bundle, effected, monkeypatch) -> None:
    """The `default` alias is what `.zshenv` puts on PATH, so this is what a bare
    `node` resolves to in every non-interactive shell."""
    fnm = home / '.local' / 'bin' / 'fnm'
    fnm.write_bytes(b'#!/bin/sh\n')
    fnm.chmod(0o755)
    runs, _ = effected()

    toolchain.install_node(home, offline=False)

    assert runs.ran('fnm', 'install', toolchain.NODE_DEFAULT_VERSION)
    assert runs.ran('fnm', 'default', toolchain.NODE_DEFAULT_VERSION)
    assert all(env['FNM_DIR'] == str(home / toolchain.FNM_HOME) for env in runs.envs if env)


# ─────────────────────────────────────────────────────────────────────────────
# What a run learns from an install
# ─────────────────────────────────────────────────────────────────────────────


def test_an_installed_runtime_is_on_path_for_the_rest_of_the_run(monkeypatch, tmp_path) -> None:
    """The converged providers share one process, so a runtime installed at stage
    30 is invisible to the tools at stage 40 without this. `.zshenv` says the same
    thing for the next shell, which cannot help the run doing the installing."""
    monkeypatch.setenv('PATH', '/usr/bin')

    toolchain.put_on_path(tmp_path / 'bin')

    assert os_path_entries()[0] == str(tmp_path / 'bin')


def test_a_directory_already_on_path_is_not_added_twice(monkeypatch) -> None:
    monkeypatch.setenv('PATH', '/usr/bin:/bin')

    toolchain.put_on_path(Path('/usr/bin'))

    assert os_path_entries() == ['/usr/bin', '/bin']


def os_path_entries() -> list[str]:
    import os

    return os.environ['PATH'].split(os.pathsep)
