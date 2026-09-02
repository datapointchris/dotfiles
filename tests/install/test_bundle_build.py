"""The whole offline build, driven through `dotfiles bundle create`.

`tests/install/test_create_bundle.py` holds the leaves — one asset name, one
wheel tag, one zip repacked. None of them enters `build`, so the function that
orchestrates the offline path had no executed statement at all, and neither did
`add_uv`, `add_wheels`, `verify_against_upstream`, `fetch_latest_version` or
anything inside `DownloadCache`. That is the shape the report-upload failure had:
a file named after the feature, four tests on a pure helper beside it, and the
orchestrator untouched.

**One seam, and it is the network.** `github_release.request` is the single
function this package builds an HTTP request in, so `Upstream` below stands in
for GitHub's release API, the asset host and PyPI and nothing else.
`catalog.load`, `resolve.resolve`, `machines.load`, `tarfile`, `Bundle` and every
`add_*` adder are the real ones, which is what makes a row in the manifest
evidence that the real adder wrote it.

**The declaration is synthetic and the dependency closure is not.** A test that
read `install/packages.yml` would be a description of today's package list,
failing on the next unrelated addition — so the three declaration paths are
pointed at a tree this file writes. `declared_closure` is the exception and has
to be: it is the *CLI's own* dependency closure, read from this repo's `uv.lock`
by uv itself, and there is no synthetic answer to that question.
"""

from __future__ import annotations

import dataclasses as dc
import gzip
import hashlib
import io
import json
import os
import re
import tarfile
import time
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest
import yaml
from typer.testing import CliRunner

from dotfiles import create_bundle
from dotfiles import github_release
from dotfiles import paths
from dotfiles import status as status_document
from dotfiles.coordinates import Arch
from dotfiles.coordinates import OSFamily
from dotfiles.coordinates import Target
from dotfiles.providers import bundle as bundle_format
from dotfiles.providers import cargo
from dotfiles.providers import releases
from dotfiles.providers import toolchain
from dotfiles.providers import winget
from dotfiles.vocabulary import ExitCode

MACHINE = 'box'
WINDOWS_MACHINE = 'winbox'

LINUX = Target(OSFamily.LINUX, Arch.X86_64)
LINUX_ARM = Target(OSFamily.LINUX, Arch.ARM64)
WINDOWS = Target(OSFamily.WINDOWS, Arch.X86_64)

LAZYGIT_REPO = 'jesseduffield/lazygit'
LAZYGIT_TAG = 'v0.45.0'
FZF_REPO = 'junegunn/fzf'
FZF_TAG = 'v0.55.0'
TASK_REPO = 'go-task/task'
TASK_TAG = 'v3.44.0'
CHEAT_REPO = 'cheat/cheat'
CHEAT_TAG = '4.4.4'
RIPGREP_REPO = 'BurntSushi/ripgrep'
RIPGREP_TAG = '14.1.1'
FNM_REPO = 'Schniz/fnm'
FNM_TAG = 'v1.38.1'
JQ_REPO = 'jqlang/jq'
JQ_TAG = 'jq-1.7.1'
THEME_REPO = 'datapointchris/theme'
THEME_TAG = 'v6.5.0'
UV_TAG = '0.9.9'

THEME_SCRIPT = 'https://raw.githubusercontent.com/datapointchris/theme/v1.0.0/install.sh'
VENDOR_SCRIPT = 'https://vendor.example.invalid/install.sh'

PACKAGES: dict[str, Any] = {
    'github_releases': [
        {'name': 'lazygit', 'repo': LAZYGIT_REPO, 'description': 'Terminal UI for git'},
        # The one declared tool that owes a file its release does not carry, so
        # the companion loop and the "not a GitHub release, no checksum" branch
        # are both reached by a real declaration rather than by a hand-built item.
        {'name': 'fzf', 'repo': FZF_REPO, 'description': 'Fuzzy finder'},
    ],
    # Placeholder-free `binary_pattern`s, deliberately. Expansion is
    # `TestPatternExpansion`'s subject next door, and a pattern here would make
    # the fake either guess the expansion or ask the same function the code
    # asked — which is a name agreeing with itself. A literal is a name upstream
    # publishes and the build has to arrive at.
    'go_tools': [
        # `command` differs from `name` deliberately: the sparse decision asks by
        # name and the manifest row files by executable, so a fixture where the
        # two are one word tests neither against the other.
        {
            'name': 'go-task',
            'command': 'task',
            'package': 'github.com/go-task/task/v3/cmd/task',
            'github_repo': TASK_REPO,
            'binary_pattern': 'task.tar.gz',
            'description': 'Task runner',
        },
        # The other shape a Go release ships: one gzipped binary and no tar
        # around it, which is a different branch from the tarball above.
        {
            'name': 'cheat',
            'package': 'github.com/cheat/cheat/cmd/cheat',
            'github_repo': CHEAT_REPO,
            'binary_pattern': 'cheat.gz',
            'description': 'Interactive cheatsheet CLI',
        },
    ],
    'cargo_packages': [
        {
            'name': 'ripgrep',
            'command': 'rg',
            'github_repo': RIPGREP_REPO,
            'binary_pattern': 'ripgrep.tar.gz',
            'description': 'Fast grep alternative',
        },
        # A crate publishing a zip, which the target has no zip handling for —
        # so the bundler repacks it as a tarball and records the new name.
        {
            'name': 'fnm',
            'command': 'fnm',
            'github_repo': FNM_REPO,
            'binary_pattern': 'fnm.zip',
            'description': 'Node version manager',
        },
    ],
    'winget_packages': [
        # The two shapes a Windows asset comes in, which is a fact about the
        # asset rather than about the tool: a bare `.exe` is copied and a `.zip`
        # is opened.
        {
            'name': 'jq',
            'command': 'jq',
            'winget': 'jqlang.jq',
            'repo': JQ_REPO,
            'asset': 'jq-windows-amd64.exe',
            'description': 'JSON processor',
        },
        {
            'name': 'ripgrep',
            'command': 'rg',
            'winget': 'BurntSushi.ripgrep',
            'repo': RIPGREP_REPO,
            'asset': 'rg.zip',
            'description': 'Fast grep alternative',
        },
    ],
    'custom_installers': [
        {
            'name': 'theme',
            'repo': THEME_REPO,
            'install_url': THEME_SCRIPT,
            'bundle_install_script': True,
            'description': 'Unified theming',
        },
        # A vendor script served from one unversioned URL, naming no repo — so
        # nothing can say what version running it installs, and the row records
        # none rather than a word.
        {
            'name': 'vendor-cli',
            'command': 'vendor',
            'install_url': VENDOR_SCRIPT,
            'bundle_install_script': True,
            'description': 'A tool that ships itself',
        },
        # Declares a repo and does not opt in. Asking this one for a version
        # would fail a build over a script nobody staged.
        {'name': 'awscli', 'command': 'aws', 'description': 'AWS CLI'},
    ],
}

MANIFESTS: dict[str, dict[str, Any]] = {
    MACHINE: {
        'machine': MACHINE,
        'platform': 'linux',
        'github_releases': ['lazygit', 'fzf'],
        'go_tools': ['go-task', 'cheat'],
        'cargo_packages': ['ripgrep', 'fnm'],
        'custom_installers': ['theme', 'vendor-cli', 'awscli'],
    },
    WINDOWS_MACHINE: {
        'machine': WINDOWS_MACHINE,
        'coordinates': {
            'package_manager': 'winget',
            'os_family': 'windows',
            'display_stack': 'none',
            'host': 'native',
            'network_trust': 'nonfleet',
            'capacity': 'workstation',
        },
        'winget_packages': ['jq', 'ripgrep'],
    },
}


def digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def tarball(member: str, body: bytes = b'#!/bin/sh\nexit 0\n') -> bytes:
    """A real `.tar.gz` holding one named file, which is what a Go release ships."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
        info = tarfile.TarInfo(member)
        info.size = len(body)
        archive.addfile(info, io.BytesIO(body))
    return buffer.getvalue()


def gzipped(body: bytes) -> bytes:
    """A lone gzipped executable, which is the second shape a Go release ships."""
    return gzip.compress(body)


def zipped(member: str, body: bytes = b'MZ\x90\x00') -> bytes:
    """A real `.zip` holding one named file, which is what astral and the winget publishers ship."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr(member, body)
    return buffer.getvalue()


class ReachedTheNetwork(BaseException):
    """Raised where a real socket was about to be opened, and not an `Exception`.

    `download` narrows on `(httpx2.HTTPError, OSError)` and retries three times,
    and `latest_version` answers None for anything it catches — so a guard raised
    as an ordinary exception would be absorbed into a plausible refusal and the
    test would pass without anyone learning the network was reached. Same
    reasoning as `WouldInstall` in `tests/conftest.py`.
    """


class Refused(httpx2.HTTPError):
    """What this fake answers a request the real service would not serve.

    An `httpx2.HTTPError`, because that is the exception every caller in
    `github_release` and `create_bundle` narrows on — a bespoke type would travel
    past `download`'s retry loop and `latest_version`'s fallback as a crash, so
    the tests would pass for the wrong reason.
    """


@dc.dataclass
class Upstream:
    """GitHub's release API, the asset host and PyPI, keeping their constraints.

    A fake and never a recording. Three rules are enforced rather than replayed,
    and each is a way a build can be wrong that a canned answer cannot express:

    - a checksum is computed from the bytes actually served, so
      `verify_against_upstream` really hashes a file and really compares it
    - an asset the release does not publish is a 404, so a bundler asking for a
      name upstream never had fails here rather than staging a plausible file
    - a repo with no release answers as GitHub does, which is the input
      `fetch_latest_version` exists to refuse

    `fetched` is the request log, which is how a test says *nothing was
    downloaded* about a specific asset rather than about the run as a whole.
    """

    releases: dict[str, str] = dc.field(default_factory=dict)
    assets: dict[tuple[str, str], dict[str, bytes]] = dc.field(default_factory=dict)
    plain: dict[str, bytes] = dc.field(default_factory=dict)
    fetched: list[str] = dc.field(default_factory=list)

    tampered: set[str] = dc.field(default_factory=set)
    """Asset names whose published checksum will not match the bytes served."""

    sdist_only: set[str] = dc.field(default_factory=set)
    """PyPI packages publishing no wheel, which is fatal for a bundle."""

    platform_wheels: set[str] = dc.field(default_factory=set)
    """Packages publishing a wheel per platform beside the pure-python one."""

    flaky: dict[str, int] = dc.field(default_factory=dict)
    """URL to the number of times it refuses before it starts answering."""

    def publish(
        self, repo: str, tag: str, assets: dict[str, bytes], *, checksums: bool = True, covering: dict[str, bytes] | None = None
    ) -> None:
        """One release, with a `checksums.txt` derived from what it actually holds.

        `checksums=False` is a release that publishes none, which several of the
        declared tools really do. `covering` is a checksums file that names other
        files — the state where something *is* published and this asset is not in
        it, which is one upstream fix away from being verifiable and so has to
        stay distinct from the first.
        """
        self.releases[repo] = tag
        held = dict(assets)
        if checksums:
            listed = covering if covering is not None else assets
            lines = [f'{"0" * 64 if name in self.tampered else digest(body)}  {name}' for name, body in listed.items()]
            held['checksums.txt'] = ('\n'.join(lines) + '\n').encode()
        self.assets[(repo, tag)] = held

    def serve(self, url: str, body: bytes) -> None:
        self.plain[url] = body

    def __call__(self, url: str, accept: str | None = None) -> bytes:
        self.fetched.append(url)
        remaining = self.flaky.get(url, 0)
        if remaining:
            self.flaky[url] = remaining - 1
            raise Refused(f'the connection to {url} was reset')

        if (latest := re.fullmatch(r'https://api\.github\.com/repos/(.+)/releases/latest', url)) is not None:
            repo = latest.group(1)
            if repo not in self.releases:
                raise Refused(f'404 Not Found: {repo} publishes no release')
            return json.dumps({'tag_name': self.releases[repo]}).encode()

        if (listing := re.fullmatch(r'https://api\.github\.com/repos/(.+)/releases\?per_page=\d+', url)) is not None:
            tag = self.releases.get(listing.group(1))
            return json.dumps([{'tag_name': tag, 'draft': False}] if tag else []).encode()

        if (tagged := re.fullmatch(r'https://api\.github\.com/repos/(.+)/releases/tags/(.+)', url)) is not None:
            held = self.assets.get((tagged.group(1), tagged.group(2)))
            if held is None:
                raise Refused(f'404 Not Found: no release {tagged.group(2)} in {tagged.group(1)}')
            return json.dumps({'assets': [{'name': name, 'id': index} for index, name in enumerate(sorted(held))]}).encode()

        if (asset := re.fullmatch(r'https://github\.com/(.+?)/releases/download/(.+)/([^/]+)', url)) is not None:
            held = self.assets.get((asset.group(1), asset.group(2))) or {}
            if asset.group(3) not in held:
                raise Refused(f'404 Not Found: {asset.group(1)} {asset.group(2)} publishes {sorted(held)}, not {asset.group(3)}')
            return held[asset.group(3)]

        if (project := re.fullmatch(r'https://pypi\.org/pypi/([^/]+)/([^/]+)/json', url)) is not None:
            return self._pypi(project.group(1), project.group(2))

        if url in self.plain:
            return self.plain[url]
        raise Refused(f'404 Not Found: nothing is published at {url}')

    def _pypi(self, name: str, version: str) -> bytes:
        """One release's files, registered for download as the answer is composed.

        Generated rather than declared, because the closure is the real one read
        out of `uv.lock` — a fixture naming the packages would be a copy of that
        lockfile, stale on the next dependency bump.
        """
        if name in self.sdist_only:
            return self._files(name, [f'{name}-{version}.tar.gz'])
        published = [f'{name}-{version}-py3-none-any.whl']
        if name in self.platform_wheels:
            published += [
                f'{name}-{version}-py3-none-manylinux_2_17_x86_64.whl',
                f'{name}-{version}-py3-none-macosx_11_0_arm64.whl',
            ]
        return self._files(name, published)

    def _files(self, name: str, filenames: list[str]) -> bytes:
        urls = []
        for filename in filenames:
            body = f'{name} {filename} payload'.encode()
            url = f'https://files.pythonhosted.org/packages/{filename}'
            self.plain[url] = body
            urls.append({'filename': filename, 'url': url, 'digests': {'sha256': '0' * 64 if filename in self.tampered else digest(body)}})
        return json.dumps({'urls': urls}).encode()


def stock(upstream: Upstream) -> Upstream:
    """Everything the declaration above resolves to, published as upstream has it.

    The two names this cannot fix in the declaration are asked of the module that
    decides them — `providers.releases.ASSETS` for a release binary and
    `cargo.triple` for uv's archive — rather than written out here, which is the
    same rule the bundler follows and the reason those two live in the providers.
    """
    upstream.publish(LAZYGIT_REPO, LAZYGIT_TAG, {asset_named('lazygit'): tarball('lazygit', b'LAZYGIT')})
    upstream.publish(FZF_REPO, FZF_TAG, {asset_named('fzf', FZF_TAG): tarball('fzf', b'FZF')})
    upstream.publish(TASK_REPO, TASK_TAG, {'task.tar.gz': tarball('task', b'TASK')})
    upstream.publish(CHEAT_REPO, CHEAT_TAG, {'cheat.gz': gzipped(b'CHEAT')})
    upstream.publish(RIPGREP_REPO, RIPGREP_TAG, {'ripgrep.tar.gz': tarball('rg', b'RIPGREP'), 'rg.zip': zipped('rg.exe', b'RG.EXE')})
    upstream.publish(FNM_REPO, FNM_TAG, {'fnm.zip': zipped('fnm', b'FNM')})
    upstream.publish(JQ_REPO, JQ_TAG, {'jq-windows-amd64.exe': b'JQ.EXE'})
    upstream.publish(THEME_REPO, THEME_TAG, {})
    uv_assets = {f'uv-{cargo.triple(target)}.tar.gz': tarball('uv', b'UV') for target in (LINUX, LINUX_ARM)}
    uv_assets[f'uv-{cargo.triple(WINDOWS)}.zip'] = zipped('uv.exe', b'UV.EXE')
    upstream.publish(create_bundle.UV_REPO, UV_TAG, uv_assets)
    for companion in releases.COMPANIONS['fzf']:
        upstream.serve(companion.url(FZF_TAG), b'#!/bin/sh\n# fzf-tmux\n')
    upstream.serve(THEME_SCRIPT, b'#!/bin/sh\n# theme\n')
    upstream.serve(VENDOR_SCRIPT, b'#!/bin/sh\n# vendor\n')
    upstream.serve(toolchain.UV_INSTALL_URL, b'#!/bin/sh\n# uv\n')
    return upstream


def downloads_from(repo: str, tag: str) -> str:
    """The prefix every asset of one release is served under."""
    return f'https://github.com/{repo}/releases/download/{tag}/'


def asset_named(tool: str, tag: str = LAZYGIT_TAG, target: Target = LINUX) -> str:
    """What a release binary's asset is called, asked of the table that names it.

    The two names the declaration cannot fix are these and uv's archive, so both
    are asked of the module the bundler asks — `providers.releases.ASSETS` here
    and `cargo.triple` there — rather than written out a second time. Everything
    else in this file's declaration carries a placeholder-free pattern, so its
    asset name is a literal upstream publishes and the build has to arrive at.
    """
    return releases.ASSETS[tool](tag, target).name


@pytest.fixture
def upstream(monkeypatch: pytest.MonkeyPatch) -> Upstream:
    """The one network seam, replaced, and every other route to a socket closed.

    The transport guard is not redundant with replacing `request`: it is what
    makes an unstubbed path a failure rather than a real download. `httpx2.get`
    and `HTTPTransport.handle_request` sit between every caller and the socket,
    including a client built somewhere this module has never looked.
    """
    fake = stock(Upstream())
    monkeypatch.setattr(github_release, 'request', fake)

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise ReachedTheNetwork('the build reached the network past github_release.request')

    monkeypatch.setattr(httpx2, 'get', refuse)
    monkeypatch.setattr(httpx2.HTTPTransport, 'handle_request', refuse)
    return fake


@pytest.fixture(autouse=True)
def declaration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A synthetic `install/` tree, and the three constants that resolve one.

    Autouse because every test in this file builds a bundle and a bundle needs a
    declaration to build from. Without it a run reads this checkout's real
    manifests and refuses on the synthetic machine name.

    Three, because they are three separate module constants and the build reads
    all of them: `catalog.load` opens `PACKAGES_FILE`, `machines.load` walks from
    `INSTALL_DIR`, and `machines.names` lists `MANIFESTS_DIR`. `REPO_ROOT` and
    `PYPROJECT_FILE` are deliberately left pointing at this checkout — see the
    module docstring on `declared_closure`.
    """
    install = tmp_path / 'repo' / 'install'
    (install / 'manifests').mkdir(parents=True)
    (install / 'packages.yml').write_text(yaml.safe_dump(PACKAGES, sort_keys=False))
    (install / 'flags.yml').write_text('')
    for name, declared in MANIFESTS.items():
        (install / 'manifests' / f'{name}.yml').write_text(yaml.safe_dump(declared, sort_keys=False))

    monkeypatch.setattr(paths, 'INSTALL_DIR', install)
    monkeypatch.setattr(paths, 'MANIFESTS_DIR', install / 'manifests')
    monkeypatch.setattr(paths, 'PACKAGES_FILE', install / 'packages.yml')
    return install


@pytest.fixture
def cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`$XDG_CACHE_HOME`, which is what `archive_dir` and `cache_root` re-read.

    The variable rather than a patch on either function, because both are
    functions precisely so this works — a constant bound at import left the
    download cache on the real machine, which is what their docstrings record.
    """
    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path / 'cache'))
    return tmp_path / 'cache' / 'dotfiles'


@dc.dataclass(frozen=True)
class Built:
    """One `bundle create` run: its status, the path it printed, and what it packed."""

    exit_code: int
    stdout: str
    stderr: str
    archive: Path | None

    @property
    def rows(self) -> tuple[tuple[str, str, str, str], ...]:
        """`manifest.txt` as the four fields it is written from, never as text."""
        if self.archive is None:
            return ()
        text = self._member(bundle_format.MANIFEST).decode()
        return tuple(tuple(line.split('|')) for line in text.splitlines() if line and not line.startswith('#'))  # type: ignore[misc]

    @property
    def described(self) -> dict[str, Any]:
        """`bundle.json`, which is the file that says what this bundle *is*."""
        assert self.archive is not None
        return json.loads(self._member(bundle_format.DOCUMENT))

    @property
    def checksums(self) -> dict[str, str]:
        assert self.archive is not None
        text = self._member('checksums.txt').decode()
        return {line.split()[1]: line.split()[0] for line in text.splitlines() if line.strip()}

    def staged(self, relative: str) -> bytes:
        return self._member(relative)

    def names(self) -> list[str]:
        assert self.archive is not None
        with tarfile.open(self.archive) as archive:
            return archive.getnames()

    def _member(self, relative: str) -> bytes:
        assert self.archive is not None
        with tarfile.open(self.archive) as archive:
            handle = archive.extractfile(f'{create_bundle.ARCHIVE_MEMBER}/{relative}')
            assert handle is not None, f'{relative} is not in {self.archive.name}'
            return handle.read()


def run(*argv: str) -> Built:
    """`dotfiles bundle create`, in process, and whatever it left behind.

    In process rather than in a subprocess for the reason `tests/matrix` gives:
    the fixtures above guard this interpreter, and a CLI run outside it could
    download for real with nothing able to say it did.
    """
    from dotfiles.main import app

    result = CliRunner().invoke(app, ['bundle', 'create', '--no-input', '--print-path', *argv], catch_exceptions=False)
    printed = result.stdout.strip().splitlines()
    archive = Path(printed[-1]) if printed and printed[-1].endswith('.tar.gz') else None
    return Built(exit_code=result.exit_code, stdout=result.stdout, stderr=result.stderr, archive=archive)


def build(*, machine: str = MACHINE, arch: str = 'x86_64', use_cache: bool = False, against: Path | None = None) -> Path:
    """`create_bundle.build`, called with what the command resolves and hands it.

    One rung under `run`, and used only where the *reason* for a refusal is the
    thing under test. The boundary turns every `BundleError` into one exit code
    and one wrapped sentence on stderr, so no front-door assertion can tell one
    refusal from another — while the exception itself carries the reason as a
    value. `test_a_refused_build_exits_issue_and_prints_no_path` is what holds the
    boundary to that translation, once, so nothing below has to restate it.
    """
    return create_bundle.build(machine, arch, use_cache=use_cache, against=against)


def status_reporting(path: Path, machine: str = MACHINE, **installed: str) -> Path:
    """A status document shaped the way `status show --json` shapes one.

    The `item` is the whole `provider/name` plan address, because that string is
    the key `already_current` looks the target up by — a bare name here would let
    every sparse case pass against a map nothing in production produces.
    """
    path.write_text(
        json.dumps(
            {
                'version': status_document.VERSION,
                'verb': 'plan',
                'machine': machine,
                'checked': '2026-08-14T12:00:00+00:00',
                'scope': ['packages', 'toolchains'],
                'resources': [
                    {
                        'address': 'packages',
                        'examined': [{'item': item, 'detail': version} for item, version in installed.items()],
                    }
                ],
            }
        )
    )
    return path


def age(directory: Path, days: int) -> None:
    """Push every file's mtime back, which is the clock `prune` reads."""
    when = time.time() - days * 86400
    for path in sorted(directory.rglob('*')):
        if path.is_file():
            os.utime(path, (when, when))


def redeclare(
    install: Path, *, packages: dict[str, Any] | None = None, manifest: dict[str, Any] | None = None, machine: str = MACHINE
) -> None:
    """Replace a declaration file wholesale, which is what a declaration is.

    Whole files rather than a merge, so a case can express "this section names
    something nothing can stage" without the original row surviving underneath.
    """
    if packages is not None:
        (install / 'packages.yml').write_text(yaml.safe_dump(packages, sort_keys=False))
    if manifest is not None:
        (install / 'manifests' / f'{machine}.yml').write_text(yaml.safe_dump(manifest, sort_keys=False))


def _unparseable_manifest(_upstream: Upstream, install: Path) -> None:
    redeclare(install, manifest={**MANIFESTS[MACHINE], 'platform': 'atlantis'})


def _release_with_no_asset_function(_upstream: Upstream, install: Path) -> None:
    packages = {**PACKAGES, 'github_releases': [*PACKAGES['github_releases'], {'name': 'nosuchtool', 'repo': 'owner/nosuchtool'}]}
    redeclare(install, packages=packages, manifest={**MANIFESTS[MACHINE], 'github_releases': ['lazygit', 'fzf', 'nosuchtool']})


def _a_pin_nothing_published(_upstream: Upstream, install: Path) -> None:
    pinned = [{**PACKAGES['github_releases'][0], 'version': '9.9.9'}, *PACKAGES['github_releases'][1:]]
    redeclare(install, packages={**PACKAGES, 'github_releases': pinned})


def _a_windows_asset_in_a_third_shape(upstream: Upstream, install: Path) -> None:
    winget_packages = [PACKAGES['winget_packages'][0], {**PACKAGES['winget_packages'][1], 'asset': 'rg.tar.gz'}]
    redeclare(install, packages={**PACKAGES, 'winget_packages': winget_packages})
    upstream.publish(RIPGREP_REPO, RIPGREP_TAG, {'rg.tar.gz': tarball('rg.exe', b'RG')})


def _a_zip_without_the_declared_executable(upstream: Upstream, _install: Path) -> None:
    upstream.publish(RIPGREP_REPO, RIPGREP_TAG, {'rg.zip': zipped('README.md', b'not the binary')})


def _a_uv_archive_without_uv_in_it(upstream: Upstream, _install: Path) -> None:
    upstream.publish(create_bundle.UV_REPO, UV_TAG, {f'uv-{cargo.triple(LINUX)}.tar.gz': tarball('uvx', b'THE OTHER BINARY')})


@dc.dataclass(frozen=True)
class Broken:
    """One way the input can be wrong, and the word the refusal has to carry."""

    id: str
    arrange: Callable[[Upstream, Path], None]
    says: str
    machine: str = MACHINE


BROKEN = (
    Broken('a manifest that will not parse', _unparseable_manifest, 'atlantis'),
    Broken('a release with no asset function', _release_with_no_asset_function, 'asset function'),
    Broken('a pin nothing published', _a_pin_nothing_published, 'release tag'),
    Broken('a windows asset in a third shape', _a_windows_asset_in_a_third_shape, 'neither a .zip nor a .exe', WINDOWS_MACHINE),
    Broken('a zip without the declared executable', _a_zip_without_the_declared_executable, 'rg.exe', WINDOWS_MACHINE),
    Broken('a uv archive without uv in it', _a_uv_archive_without_uv_in_it, 'no uv binary'),
)
"""Each row is a state, so a seventh is a row rather than a function.

Kept as data because the assertion is identical for all of them — the build
raises, the refusal names the thing that is wrong, and `archive_dir` stays empty.
What varies is only the arrangement and the word.
"""


# ─────────────────────────────────────────────────────────────────────────────
# A full build
#
# One archive, every declared section in it, and every asset verified.
#
# Nothing below stubs an adder. A row in `manifest.txt` is evidence that the
# real `add_*` staged a real file, and a digest in `checksums.txt` is evidence
# that `verify_against_upstream` hashed it and compared it to what the fake
# published.
# ─────────────────────────────────────────────────────────────────────────────


def test_every_declared_section_is_staged_into_one_archive(upstream: Upstream, cache: Path) -> None:
    built = run('--machine', MACHINE, '--arch', 'x86_64')

    assert built.exit_code == ExitCode.CONVERGED, built.stderr
    assert built.archive is not None and built.archive.is_file()
    staged = {(category, name): (version, filename) for category, name, version, filename in built.rows}
    assert staged['uv', 'uv'] == (UV_TAG, 'uv')
    assert staged['binary', 'lazygit'] == (LAZYGIT_TAG, asset_named('lazygit'))
    assert staged['go-binary', 'go-task'] == (TASK_TAG, 'task')
    assert staged['cargo', 'ripgrep'] == (RIPGREP_TAG, 'ripgrep.tar.gz')
    assert staged['script', 'theme'] == (THEME_TAG, 'theme-install.sh')
    assert staged['script', 'uv'] == (UV_TAG, 'uv-install.sh')
    assert [name for category, name, *_ in built.rows if category == 'wheel'], 'the wheelhouse is what the bootstrap installs from'


def test_a_crate_shipping_a_zip_is_recorded_under_the_tarball_it_was_repacked_as(upstream: Upstream, cache: Path) -> None:
    """So `install_from_cache` on the target needs no zip handling at all. The
    row has to name the file that is really there, or the offline install goes
    looking for the zip this consumed."""
    built = run('--machine', MACHINE, '--arch', 'x86_64')

    staged = {name: filename for category, name, _version, filename in built.rows if category == 'cargo'}
    assert staged['fnm'] == f'fnm_{FNM_TAG.lstrip("v")}_{cargo.triple(LINUX)}.tar.gz'
    assert f'{create_bundle.ARCHIVE_MEMBER}/binaries/{staged["fnm"]}' in built.names()
    assert f'{create_bundle.ARCHIVE_MEMBER}/binaries/fnm.zip' not in built.names()


def test_a_script_whose_repo_nothing_names_records_no_version_rather_than_a_word(upstream: Upstream, cache: Path) -> None:
    """`latest` stood here, and `ghrelease.bundle_version` hands whatever it
    finds to a tag comparison — so offline the row read as a release nobody
    published. Absent is the honest answer, and it reads back as None."""
    built = run('--machine', MACHINE, '--arch', 'x86_64')

    scripts = {name: version for category, name, version, _filename in built.rows if category == 'script'}
    assert scripts['vendor-cli'] == ''
    assert 'latest' not in scripts.values()


def test_an_installer_that_never_opted_in_is_neither_staged_nor_asked_for_a_version(upstream: Upstream, cache: Path) -> None:
    """`bundle_install_script` is the opt-in, and an entry without it must not
    be asked for a version either — a declared repo publishing no release
    would fail a build over a script nobody staged."""
    built = run('--machine', MACHINE, '--arch', 'x86_64')

    assert 'awscli' not in [name for category, name, *_ in built.rows if category == 'script']


def test_the_go_binary_is_extracted_from_its_release_archive_rather_than_staged_packed(upstream: Upstream, cache: Path) -> None:
    """The row records `task` and the release ships `task.tar.gz`, so a build
    that staged the tarball under the binary's name would satisfy every count
    and install nothing that runs — on the one machine with no way to find out
    why."""
    built = run('--machine', MACHINE, '--arch', 'x86_64')

    assert built.staged('go-binaries/task') == b'TASK'
    assert built.staged('go-binaries/cheat') == b'CHEAT', 'the other shape a Go release ships is a lone gzipped binary'
    packed = [name for name in built.names() if name.startswith(f'{create_bundle.ARCHIVE_MEMBER}/go-binaries/') and '.' in name]
    assert packed == [], 'the archive it came out of is consumed, or the offline install has two files to choose between'


def test_the_uv_binary_is_unpacked_because_the_bootstrap_copies_it_onto_path(upstream: Upstream, cache: Path) -> None:
    built = run('--machine', MACHINE, '--arch', 'x86_64')

    assert built.staged('bin/uv') == b'UV'


def test_a_wheel_for_another_platform_is_left_behind_and_the_portable_one_is_not(upstream: Upstream, cache: Path) -> None:
    """An over-broad match ships a wheel that cannot install and a narrow one
    ships nothing for the interpreter the machine has, and both are silent
    here and fatal on the target. Every version of a platform wheel is taken
    rather than one chosen against a guessed interpreter — the machine's
    python is a fact only the target knows."""
    name, version = create_bundle.declared_closure()[0]
    upstream.platform_wheels.add(name)

    built = run('--machine', MACHINE, '--arch', 'x86_64')

    carried = {filename for category, staged, _version, filename in built.rows if category == 'wheel' and staged == name}
    assert carried == {f'{name}-{version}-py3-none-any.whl', f'{name}-{version}-py3-none-manylinux_2_17_x86_64.whl'}


def test_every_release_asset_carries_the_digest_upstream_published_for_it(upstream: Upstream, cache: Path) -> None:
    """The install machine cannot resolve which asset holds the checksum
    without the release API, so verification happens on this side or it does
    not happen. Recomputed here from the bytes in the archive, which is the
    same comparison the offline installer makes.

    Every digest `checksums.txt` carries has to be right, which is what this
    asserts. It deliberately does not assert *which* assets get a row: the go
    and cargo staging loops write none, and whether that is intended is a
    question for the module rather than something to pin here either way.
    """
    built = run('--machine', MACHINE, '--arch', 'x86_64')

    recorded = built.checksums
    assert recorded, 'an empty checksums.txt makes every GitHub release install fail on a missing checksum'
    lazygit = asset_named('lazygit')
    assert recorded[lazygit] == digest(built.staged(f'binaries/{lazygit}'))
    for name, expected in recorded.items():
        for folder in ('binaries', 'wheels', 'bin'):
            if f'{create_bundle.ARCHIVE_MEMBER}/{folder}/{name}' in built.names():
                assert expected == digest(built.staged(f'{folder}/{name}'))


@pytest.mark.parametrize(
    ('publishing', 'recorded'),
    [
        ({}, True),
        ({'checksums': False}, False),
        ({'covering': {'source.tar.gz': b'ANOTHER ASSET'}}, False),
    ],
    ids=['a digest for this asset', 'no checksums file at all', 'a checksums file that omits it'],
)
def test_only_a_digest_actually_checked_against_upstream_is_recorded(
    upstream: Upstream, cache: Path, publishing: dict[str, Any], recorded: bool
) -> None:
    """Writing one for an asset whose release publishes nothing usable would
    make the installer log `verified` for bytes nobody verified.

    The two unpublished states stay apart upstream — one release publishes no
    checksums and another publishes a file this asset is not named in, which
    is one upstream fix away from being verifiable — and the bundle records
    nothing either way, because nothing was compared. The tool is staged in
    all three, which is what makes this a question about the digest rather
    than about whether the build survived."""
    lazygit = asset_named('lazygit')
    upstream.publish(LAZYGIT_REPO, LAZYGIT_TAG, {lazygit: tarball('lazygit', b'LAZYGIT')}, **publishing)

    built = run('--machine', MACHINE, '--arch', 'x86_64')

    assert built.exit_code == ExitCode.CONVERGED, built.stderr
    assert (lazygit in built.checksums) is recorded
    assert ('binary', 'lazygit') in {(category, name) for category, name, *_ in built.rows}


def test_the_archive_lands_in_the_bundle_cache_and_not_beside_the_checkout(
    upstream: Upstream, cache: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`newest` searches `archive_dir`, the cwd and `$HOME`, and `prune`
    sweeps `archive_dir` alone — so an archive written to the checkout root
    was found by a bare `bundle upload` only from inside the checkout, and was
    never swept while `prune` printed a count."""
    monkeypatch.chdir(tmp_path)

    built = run('--machine', MACHINE, '--arch', 'x86_64')

    assert built.archive is not None
    assert built.archive.parent == paths.archive_dir()
    assert list(paths.archive_dir().glob('*.tar.gz')) == [built.archive]
    assert not list(tmp_path.glob('*.tar.gz')), 'the working directory is not where a bundle lives'
    assert not list(paths.REPO_ROOT.glob('dotfiles-offline-*.tar.gz')), 'nor is the checkout'


def test_the_archive_holds_one_top_level_directory(upstream: Upstream, cache: Path) -> None:
    """Both stagers find the member by its `manifest.txt`, so what matters is
    that there is exactly one thing to find."""
    built = run('--machine', MACHINE, '--arch', 'x86_64')

    assert {name.split('/')[0] for name in built.names()} == {create_bundle.ARCHIVE_MEMBER}


def test_a_windows_machine_gets_the_zip_archive_and_the_exe_suffix(upstream: Upstream, cache: Path) -> None:
    """astral publishes `uv-{triple}.zip` on Windows and no tarball, and a PE
    without its suffix is a file Windows declines to execute — so both are
    facts about the asset rather than decoration. `install.sh` derives the same
    name from `uname -s` and copies `bin/uv.exe` onto PATH."""
    built = run('--machine', WINDOWS_MACHINE, '--arch', 'x86_64')

    assert built.exit_code == ExitCode.CONVERGED, built.stderr
    staged = {(category, name): (version, filename) for category, name, version, filename in built.rows}
    assert staged['uv', 'uv'] == (UV_TAG, 'uv.exe')
    assert staged['winget', 'jq'] == (JQ_TAG, 'jq.exe')
    assert built.staged('bin/uv.exe') == b'UV.EXE'
    assert built.staged(f'{winget.BUNDLE_BINARIES}/jq.exe') == b'JQ.EXE'


def test_the_name_carries_the_manifest_and_the_platform_the_build_was_asked_for(upstream: Upstream, cache: Path) -> None:
    """The OS is read off the manifest and only the CPU is passed in. Taking
    both from the caller let a linux manifest asked for with a darwin target
    build a tarball of the wrong binaries without saying so."""
    built = run('--machine', MACHINE, '--arch', 'arm64')

    assert built.archive is not None
    assert re.fullmatch(rf'dotfiles-offline-v\d{{8}}T\d{{6}}Z-{MACHINE}-linux-arm64\.tar\.gz', built.archive.name)
    assert built.described['platform'] == 'linux/arm64'
    assert built.described['machine'] == MACHINE


# ─────────────────────────────────────────────────────────────────────────────
# What the build refuses
#
# Each refusal is paired with the archive not existing.
#
# An assertion that nothing was built is satisfied by a crash, so every case
# below names the reason it expects *and* checks that `archive_dir` is empty —
# a half-written bundle is worse than none, because the machine reading it
# cannot fetch what is missing and nothing in the archive says which tool was
# lost.
# ─────────────────────────────────────────────────────────────────────────────


def test_an_arch_the_tool_does_not_support_is_a_usage_error_before_anything_is_fetched(upstream: Upstream, cache: Path) -> None:
    """Refused by the `Arch` annotation at the boundary rather than inside the
    build, which is why the check inside `build` needs its own case below."""
    from dotfiles.main import app

    result = CliRunner().invoke(app, ['bundle', 'create', '--no-input', '--machine', MACHINE, '--arch', 'sparc64'])

    assert result.exit_code == ExitCode.USAGE
    assert upstream.fetched == []
    assert not paths.archive_dir().exists()


def test_the_builder_refuses_an_unsupported_arch_of_its_own_accord(upstream: Upstream, cache: Path) -> None:
    """`build` is called directly by the command and is importable by anything
    else, so the guard is the builder's rather than the annotation's alone."""
    with pytest.raises(create_bundle.BundleError, match='sparc64'):
        build(arch='sparc64')

    assert upstream.fetched == []


def test_a_refused_build_exits_issue_and_prints_no_path(upstream: Upstream, cache: Path) -> None:
    """The one test of the translation, so the cases below can assert the
    reason rather than restating the exit code. `--print-path` is what a
    pipeline reads, and a refused build must leave it empty rather than
    naming an archive that was never written."""
    upstream.releases.pop(TASK_REPO)

    ran = run('--machine', MACHINE, '--arch', 'x86_64')

    assert ran.exit_code == ExitCode.ISSUE
    assert ran.stdout.strip() == ''
    assert not list(paths.archive_dir().glob('*.tar.gz'))


def test_a_machine_with_no_manifest_is_named_rather_than_built_for(upstream: Upstream, cache: Path) -> None:
    from dotfiles.main import app

    result = CliRunner().invoke(app, ['bundle', 'create', '--no-input', '--machine', 'nowhere', '--arch', 'x86_64'])

    assert result.exit_code == ExitCode.USAGE
    assert upstream.fetched == []


def test_a_repo_that_publishes_no_release_ends_the_build_naming_it(upstream: Upstream, cache: Path) -> None:
    """`latest_version` answers None for a release it cannot read, which is
    right for an installer deciding whether to update. A build cannot name the
    asset without the version, so the miss is fatal here."""
    upstream.releases.pop(TASK_REPO)

    with pytest.raises(create_bundle.BundleError, match=TASK_REPO):
        build()

    assert not list(paths.archive_dir().glob('*.tar.gz'))


def test_bytes_that_fail_against_the_published_checksum_end_the_build_and_leave_no_cache_entry(upstream: Upstream, cache: Path) -> None:
    """Bytes that failed against upstream must not be served to the next
    build, which is the whole reason the mismatch evicts rather than only
    raising."""
    lazygit = asset_named('lazygit')
    upstream.tampered.add(lazygit)
    stock(upstream)

    with pytest.raises(create_bundle.BundleError, match='Checksum mismatch'):
        build(use_cache=True)

    assert not list(paths.archive_dir().glob('*.tar.gz'))
    assert not list(create_bundle.cache_root().rglob(lazygit))


def test_a_wheel_whose_digest_does_not_match_pypi_ends_the_build(upstream: Upstream, cache: Path) -> None:
    """PyPI publishes the digest alongside the file, so an unverified wheel
    would be a hole the release assets beside it do not have — and the machine
    installing from this bundle is the one that cannot check for itself."""
    name, version = create_bundle.declared_closure()[0]
    upstream.tampered.add(f'{name}-{version}-py3-none-any.whl')

    with pytest.raises(create_bundle.BundleError, match='checksum mismatch'):
        build()

    assert not list(paths.archive_dir().glob('*.tar.gz'))


def test_a_dependency_with_no_wheel_for_the_target_ends_the_build(upstream: Upstream, cache: Path) -> None:
    """An sdist cannot install with no index, so carrying one and calling the
    bundle complete strands the bootstrap on the machine it exists for."""
    name, _ = create_bundle.declared_closure()[0]
    upstream.sdist_only.add(name)

    with pytest.raises(create_bundle.BundleError, match=re.escape(name)):
        build()

    assert not list(paths.archive_dir().glob('*.tar.gz'))


def test_a_download_that_never_answers_ends_the_build_after_the_declared_attempts(upstream: Upstream, cache: Path) -> None:
    url = f'https://github.com/{TASK_REPO}/releases/download/{TASK_TAG}/task.tar.gz'
    upstream.flaky[url] = create_bundle.DOWNLOAD_ATTEMPTS + 1

    with pytest.raises(create_bundle.BundleError, match='Failed to download'):
        build()

    assert upstream.fetched.count(url) == create_bundle.DOWNLOAD_ATTEMPTS
    assert not list(paths.archive_dir().glob('*.tar.gz'))


def test_a_checksums_file_the_release_lists_and_will_not_serve_ends_the_build(upstream: Upstream, cache: Path) -> None:
    """Different from a release publishing none, and it has to be: the API
    said the file is there, so failing to read it is a fault rather than a
    state — and staging the asset anyway would record it unverified while
    upstream had a digest for it all along."""
    upstream.flaky[downloads_from(LAZYGIT_REPO, LAZYGIT_TAG) + 'checksums.txt'] = 1

    with pytest.raises(create_bundle.BundleError, match='checksums.txt'):
        build()

    assert not list(paths.archive_dir().glob('*.tar.gz'))


@pytest.mark.parametrize('broken', BROKEN, ids=lambda one: one.id)
def test_a_declaration_or_a_release_the_bundler_cannot_stage_is_named(
    upstream: Upstream, cache: Path, declaration: Path, broken: Broken
) -> None:
    """Every way `BROKEN` names, each ending the build with a sentence rather
    than a traceback, and none of them leaving an archive.

    A declaration fault and a release fault are one test because the answer is
    one answer: the build stops, the refusal names the thing that is wrong,
    and nothing half-written survives for a machine to install from.
    """
    broken.arrange(upstream, declaration)

    with pytest.raises(create_bundle.BundleError, match=broken.says):
        build(machine=broken.machine)

    assert not list(paths.archive_dir().glob('*.tar.gz'))


def test_a_transient_failure_is_retried_rather_than_ending_the_build(upstream: Upstream, cache: Path) -> None:
    """Paired with the case above, which a bundler that never retried would
    also satisfy."""
    url = f'https://github.com/{TASK_REPO}/releases/download/{TASK_TAG}/task.tar.gz'
    upstream.flaky[url] = create_bundle.DOWNLOAD_ATTEMPTS - 1

    built = run('--machine', MACHINE, '--arch', 'x86_64')

    assert built.exit_code == ExitCode.CONVERGED, built.stderr
    assert upstream.fetched.count(url) == create_bundle.DOWNLOAD_ATTEMPTS
    assert built.staged('go-binaries/task') == b'TASK'


# ─────────────────────────────────────────────────────────────────────────────
# A sparse build
#
# `--against` parameterizes the build; it never adds an effect to it.
#
# What changes is which installers are staged, and the omission has to stay
# legible on the other end — without `current`, a bundle carrying less is
# indistinguishable from one that failed to carry more.
# ─────────────────────────────────────────────────────────────────────────────


def test_a_status_from_another_machine_is_refused_rather_than_diffed(upstream: Upstream, cache: Path, tmp_path: Path) -> None:
    """A bundle is built for one manifest and its contents are that
    manifest's plan, so diffing it against another machine's report omits
    whatever the two happen to share and reports the result as measured.
    Nothing downstream can detect that: the archive is well-formed, its
    `bundle.json` reads sparse, and the omissions are simply wrong."""
    peer = status_reporting(tmp_path / 'peer.json', machine='someone-elses-box', **{'ghrelease/lazygit': '0.45.0'})

    with pytest.raises(create_bundle.BundleError, match='someone-elses-box'):
        build(against=peer)

    assert not list(paths.archive_dir().glob('*.tar.gz'))
    assert upstream.fetched == [], 'refused before a single asset is downloaded'


@pytest.mark.parametrize(
    ('machine', 'address', 'reported', 'measured', 'downloads'),
    [
        (MACHINE, 'ghrelease/lazygit', '0.45.0', ('binary/lazygit', LAZYGIT_TAG), downloads_from(LAZYGIT_REPO, LAZYGIT_TAG)),
        (MACHINE, 'go/go-task', '3.44.0', ('go-binary/go-task', TASK_TAG), downloads_from(TASK_REPO, TASK_TAG)),
        (MACHINE, 'cargo/ripgrep', '14.1.1', ('cargo/ripgrep', RIPGREP_TAG), downloads_from(RIPGREP_REPO, RIPGREP_TAG)),
        (WINDOWS_MACHINE, 'winget/jq', '1.7.1', ('winget/jq', JQ_TAG), downloads_from(JQ_REPO, JQ_TAG)),
    ],
    ids=['ghrelease', 'go', 'cargo', 'winget'],
)
def test_a_tool_the_target_already_has_is_neither_downloaded_nor_recorded_as_carried(
    upstream: Upstream,
    cache: Path,
    tmp_path: Path,
    machine: str,
    address: str,
    reported: str,
    measured: tuple[str, str],
    downloads: str,
) -> None:
    """Every staging loop has to consult the decision, and nothing else says
    when one does not: the bundle would carry the tool anyway, the build would
    still report itself sparse, and every test of `already_current` on its own
    would still pass.

    The two keys differ on purpose. `installed` is keyed on the plan address
    the target reported and `current` on the category a bundle row uses — `go`
    against `go-binary`, `ghrelease` against `binary` — so collapsing either
    to a bare name lets two providers naming one tool answer for each other.
    """
    report = status_reporting(tmp_path / 'box.json', machine=machine, **{address: reported})

    built = run('--machine', machine, '--arch', 'x86_64', '--against', str(report))

    assert built.exit_code == ExitCode.CONVERGED, built.stderr
    assert built.described['current'] == dict([measured])
    assert built.described['built_from'] == 'box.json'
    category, name = measured[0].split('/')
    assert name not in [row[1] for row in built.rows if row[0] == category]
    # The download refused outright rather than merely unasserted: a loop
    # that skipped the record and fetched anyway would satisfy a row count.
    assert [url for url in upstream.fetched if url.startswith(downloads)] == []


def test_a_tool_that_owes_a_companion_is_carried_even_where_the_target_has_it(upstream: Upstream, cache: Path, tmp_path: Path) -> None:
    """`already_current` records the binary alone and the skip takes the
    companion loop with it, so a sparse bundle would drop both and say nothing
    about either. `missing_companions` runs on the target after the status was
    taken, and on the machine that cannot fetch anything there is no recovery
    — the binary is not in the bundle either."""
    report = status_reporting(tmp_path / 'box.json', **{'ghrelease/fzf': '0.55.0'})

    built = run('--machine', MACHINE, '--arch', 'x86_64', '--against', str(report))

    assert [name for category, name, *_ in built.rows if category in ('binary', 'extra')] == ['fzf', 'fzf-tmux', 'lazygit']
    assert built.described['current'] == {}, 'a carried tool is never also recorded as measured'


def test_the_archive_says_sparse_in_its_own_name_before_anything_is_unpacked(upstream: Upstream, cache: Path, tmp_path: Path) -> None:
    report = status_reporting(tmp_path / 'box.json', **{'ghrelease/lazygit': '0.45.0'})

    built = run('--machine', MACHINE, '--arch', 'x86_64', '--against', str(report))

    assert built.archive is not None
    assert built.archive.name.endswith('-linux-x86_64-sparse.tar.gz')


def test_a_sparse_build_that_left_nothing_out_still_says_it_was_planned_against_a_report(
    upstream: Upstream, cache: Path, tmp_path: Path
) -> None:
    """Completeness follows `built_from` and never `bool(current)`, because
    `bundle_name` fixes the `-sparse` suffix before a tool has been measured.
    Keyed on the other one, a build planned against a report that omitted
    nothing would be named `-sparse` while its document read `full` — the
    disagreement between an archive and its own description that `bundle
    check` exists to make impossible."""
    report = status_reporting(tmp_path / 'box.json', **{'ghrelease/lazygit': '0.1.0'})

    built = run('--machine', MACHINE, '--arch', 'x86_64', '--against', str(report))

    assert built.described['current'] == {}
    assert built.described['completeness'] == str(bundle_format.Completeness.SPARSE)
    assert 'lazygit' in [name for category, name, *_ in built.rows if category == 'binary']


def test_a_full_build_records_no_measurement_it_did_not_make(upstream: Upstream, cache: Path) -> None:
    built = run('--machine', MACHINE, '--arch', 'x86_64')

    assert built.described['completeness'] == str(bundle_format.Completeness.FULL)
    assert built.described['current'] == {}
    assert built.described['built_from'] == ''


def test_a_path_that_is_not_a_file_is_a_usage_error(upstream: Upstream, cache: Path, tmp_path: Path) -> None:
    from dotfiles.main import app

    argv = ['bundle', 'create', '--no-input', '--machine', MACHINE, '--arch', 'x86_64', '--against', str(tmp_path / 'absent.json')]
    result = CliRunner().invoke(app, argv)

    assert result.exit_code == ExitCode.USAGE
    assert upstream.fetched == []


# ─────────────────────────────────────────────────────────────────────────────
# The download cache
#
# Kept between builds, and swept only after the archive is written.
#
# Everything here is observed through what the second build fetched, because
# that is the value the cache exists to change — a build that reads identically
# warm and cold makes a working cache look broken, which is how it was first
# reported.
# ─────────────────────────────────────────────────────────────────────────────


def test_a_second_build_serves_the_release_assets_from_disk(upstream: Upstream, cache: Path) -> None:
    run('--machine', MACHINE, '--arch', 'x86_64')
    upstream.fetched.clear()

    built = run('--machine', MACHINE, '--arch', 'x86_64')

    assert built.exit_code == ExitCode.CONVERGED, built.stderr
    assert f'https://github.com/{TASK_REPO}/releases/download/{TASK_TAG}/task.tar.gz' not in upstream.fetched
    assert built.staged('go-binaries/task') == b'TASK', 'a cache hit has to produce the same file a download does'


def test_a_checksum_already_confirmed_is_not_confirmed_again(upstream: Upstream, cache: Path) -> None:
    """What upstream publishes for a released tag does not change, and it is
    the expensive half — one API call to find the checksums asset plus one
    download to read it."""
    run('--machine', MACHINE, '--arch', 'x86_64')
    upstream.fetched.clear()

    built = run('--machine', MACHINE, '--arch', 'x86_64')

    assert f'https://api.github.com/repos/{LAZYGIT_REPO}/releases/tags/{LAZYGIT_TAG}' not in upstream.fetched
    lazygit = asset_named('lazygit')
    assert built.checksums[lazygit] == digest(built.staged(f'binaries/{lazygit}'))


def test_a_release_that_publishes_no_checksums_is_not_asked_about_twice(upstream: Upstream, cache: Path) -> None:
    """The answer is about one immutable asset, so caching it is as safe as
    caching the asset — and it is the expensive half, one API call plus one
    download, spent to learn there is nothing to compare against."""
    upstream.publish(LAZYGIT_REPO, LAZYGIT_TAG, {asset_named('lazygit'): tarball('lazygit', b'LAZYGIT')}, checksums=False)
    run('--machine', MACHINE, '--arch', 'x86_64')
    upstream.fetched.clear()

    built = run('--machine', MACHINE, '--arch', 'x86_64')

    assert f'https://api.github.com/repos/{LAZYGIT_REPO}/releases/tags/{LAZYGIT_TAG}' not in upstream.fetched
    assert asset_named('lazygit') not in built.checksums, 'a cached answer must not become a digest nobody checked'


def test_no_cache_asks_upstream_for_every_asset_again(upstream: Upstream, cache: Path) -> None:
    """The one thing no other flag reaches is a cached file that is wrong —
    truncated, or a release republished under a tag it already used."""
    run('--machine', MACHINE, '--arch', 'x86_64')
    upstream.fetched.clear()

    built = run('--machine', MACHINE, '--arch', 'x86_64', '--no-cache')

    assert built.exit_code == ExitCode.CONVERGED, built.stderr
    assert f'https://github.com/{TASK_REPO}/releases/download/{TASK_TAG}/task.tar.gz' in upstream.fetched


def test_a_corrupt_cached_copy_is_re_downloaded_rather_than_staged(upstream: Upstream, cache: Path) -> None:
    """The digest beside an entry is what makes a truncated file a miss
    instead of a bundle full of unusable bytes."""
    run('--machine', MACHINE, '--arch', 'x86_64')
    cached = create_bundle.cache_path_for(create_bundle.github_asset(TASK_REPO, TASK_TAG, 'task.tar.gz').key)
    cached.write_bytes(b'TRUNCATED')
    upstream.fetched.clear()

    built = run('--machine', MACHINE, '--arch', 'x86_64')

    assert f'https://github.com/{TASK_REPO}/releases/download/{TASK_TAG}/task.tar.gz' in upstream.fetched
    assert built.staged('go-binaries/task') == b'TASK'


def test_the_retention_sweep_runs_after_the_archive_rather_than_before_it(upstream: Upstream, cache: Path) -> None:
    """Ordering, observed rather than asserted about: a sweep that ran first
    would delete the aged entry the build is about to want, and the asset
    would be downloaded again. It runs last, so the entry is a *hit*, the hit
    touches it, and it survives its own sweep — while an aged entry nothing
    asked for is gone by the time the build returns.

    A build must never be delayed or failed by housekeeping, which is the
    whole reason the order is this way round.
    """
    run('--machine', MACHINE, '--arch', 'x86_64')
    orphan = create_bundle.cache_path_for(('github', 'go-task/task', 'v3.0.0', 'task.tar.gz'))
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_bytes(b'SUPERSEDED')
    age(create_bundle.cache_root(), create_bundle.CACHE_RETENTION_DAYS + 1)
    upstream.fetched.clear()

    built = run('--machine', MACHINE, '--arch', 'x86_64')

    wanted = create_bundle.cache_path_for(create_bundle.github_asset(TASK_REPO, TASK_TAG, 'task.tar.gz').key)
    assert built.exit_code == ExitCode.CONVERGED, built.stderr
    assert f'https://github.com/{TASK_REPO}/releases/download/{TASK_TAG}/task.tar.gz' not in upstream.fetched
    assert wanted.is_file(), 'a hit counts as use, or a tool that never changes ages out because the cache kept working'
    assert not orphan.exists(), 'a superseded version nothing asked for is what the sweep is for'


# ─────────────────────────────────────────────────────────────────────────────
# An entry the bundler cannot stage
#
# Said out loud, and the rest of the build continues.
#
# Dropping one silently carries the same information as a log line and none of
# the evidence — and the machine that installs from the bundle then has no
# source for that tool at all.
# ─────────────────────────────────────────────────────────────────────────────


def test_a_cargo_entry_with_no_release_repo_is_left_out_without_ending_the_build(
    upstream: Upstream, cache: Path, declaration: Path
) -> None:
    """An entry with no repo and no `binary_pattern` has no asset to name, so
    there is nothing to stage — and the two sections are read by name rather
    than through a `getattr` default, which would answer *unbundleable* for an
    entry whose field was merely renamed."""
    redeclare(
        declaration,
        packages={**PACKAGES, 'cargo_packages': [*PACKAGES['cargo_packages'], {'name': 'zoxide', 'description': 'Smarter cd'}]},
        manifest={**MANIFESTS[MACHINE], 'cargo_packages': ['ripgrep', 'zoxide']},
    )

    built = run('--machine', MACHINE, '--arch', 'x86_64')

    assert built.exit_code == ExitCode.CONVERGED, built.stderr
    assert [name for category, name, *_ in built.rows if category == 'cargo'] == ['ripgrep']


def test_an_installer_that_opts_into_bundling_without_a_url_ends_the_build(upstream: Upstream, cache: Path, declaration: Path) -> None:
    """The opt-in is a claim that a script can be staged, and an entry making
    it with nothing to fetch would leave a `script` row naming a file the
    archive does not hold."""
    opting_in = [{'name': 'theme', 'repo': THEME_REPO, 'bundle_install_script': True, 'description': 'Theming'}]
    redeclare(declaration, packages={**PACKAGES, 'custom_installers': opting_in})

    with pytest.raises(create_bundle.BundleError, match='install_url'):
        build()

    assert not list(paths.archive_dir().glob('*.tar.gz'))


# ─────────────────────────────────────────────────────────────────────────────
# What the bundle tells the target to do
#
# The four files at the root, each answering one question.
#
# Asserted as values rather than as prose: the README is the one file whose
# content is a sentence, and what is checked about it is that it is there at
# all, because `install.sh` and `bundle stage` both read the directory it
# describes.
# ─────────────────────────────────────────────────────────────────────────────


def test_the_four_root_files_are_all_written(upstream: Upstream, cache: Path) -> None:
    built = run('--machine', MACHINE, '--arch', 'x86_64')

    root = {name.split('/')[-1] for name in built.names() if name.count('/') == 1}
    assert {bundle_format.MANIFEST, bundle_format.DOCUMENT, 'checksums.txt', 'README.txt'} <= root
