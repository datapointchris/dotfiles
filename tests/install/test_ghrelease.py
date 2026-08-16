"""The install engine: what it does with an asset once it has one.

Every test here runs with no network. The offline path is not a special case
built for the tests — it is the one a restricted-network machine takes, and it
reaches every step of the sequence except the two API calls, so exercising it is
exercising the engine.

The checksum policy is tested against `Verification` values directly rather than
against live releases. Which state a release is actually in is a different claim,
measured by `tests/install/test_release_urls.py` against upstream; what matters
here is that each state maps to the right decision, including the one that
refuses.
"""

from __future__ import annotations

import contextlib
import gzip
import io
import os
import stat
import tarfile
import zipfile
from pathlib import Path

import pytest

from dotfiles import catalog
from dotfiles import effects
from dotfiles import github_release
from dotfiles import paths
from dotfiles.coordinates import Arch
from dotfiles.coordinates import OSFamily
from dotfiles.coordinates import Target
from dotfiles.providers import Kind
from dotfiles.providers import ghrelease
from dotfiles.providers import releases
from dotfiles.providers.releases import Archive
from dotfiles.providers.releases import Companion
from dotfiles.providers.releases import ReleaseArtifact

LINUX = Target(OSFamily.LINUX, Arch.X86_64)

PAYLOAD = b'#!/bin/sh\necho installed\n'

UNREACHABLE = 'https://example.invalid/demo-tmux'
"""A companion URL no test may reach. Every one of these runs offline, so a test
that started downloading would be a test that stopped testing the bundle."""

COMPANION = (Companion('demo-tmux', UNREACHABLE),)


def entry(name: str = 'demo', **fields) -> catalog.GithubRelease:
    return catalog.GithubRelease(name=name, repo=f'someone/{name}', **fields)


def tarball(path: Path, members: dict[str, bytes]) -> None:
    with tarfile.open(path, 'w:gz') as bundle:
        for name, payload in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mode = 0o644
            bundle.addfile(info, io.BytesIO(payload))


def zipped(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, 'w') as bundle:
        for name, payload in members.items():
            bundle.writestr(name, payload)


@pytest.fixture
def home(tmp_path, monkeypatch) -> Path:
    """A home directory the engine installs into, and a PATH that can see it."""
    root = tmp_path / 'home'
    (root / '.local' / 'bin').mkdir(parents=True)
    monkeypatch.setenv('HOME', str(root))
    monkeypatch.setenv('PATH', str(root / '.local' / 'bin'))
    # `bin_dir` reads $HOME, but anything resolving an XDG directory prefers the
    # variable — so a developer whose $XDG_CONFIG_HOME is set has the engine write
    # into their real config directory from a test. Measured 2026-08-16: a unit
    # placement test put demo.service in the running user's ~/.config/systemd/user.
    monkeypatch.setenv('XDG_CONFIG_HOME', str(root / '.config'))
    return root


@pytest.fixture
def bundle(tmp_path, monkeypatch) -> Path:
    """A staged offline bundle, which is the seam that keeps these tests local."""
    staged = tmp_path / 'installers'
    (staged / 'binaries').mkdir(parents=True)
    monkeypatch.setattr(paths, 'BUNDLE_DIR', staged)
    return staged


def stage(bundle: Path, name: str, tool: str, version: str, payload: bytes) -> None:
    """Put one asset in the bundle, recorded and digested the way the bundler does."""
    asset = bundle / 'binaries' / name
    asset.write_bytes(payload)
    manifest = bundle / 'manifest.txt'
    manifest.write_text(manifest.read_text() if manifest.is_file() else '')
    with manifest.open('a') as handle:
        handle.write(f'binary|{tool}|{version}|{name}\n')
    with (bundle / 'checksums.txt').open('a') as handle:
        handle.write(f'{github_release.sha256_of(asset)}  {name}\n')


class TestPlacement:
    """One binary out of four different shapes of download, all landing the same."""

    def test_a_raw_binary_is_the_download_itself(self, home, bundle):
        stage(bundle, 'demo-linux-x86_64', 'demo', 'v1.2.3', PAYLOAD)
        monkeyed = ReleaseArtifact('demo-linux-x86_64', Archive.RAW)

        result = install_one(monkeyed, entry(), offline=True)

        assert result.ok, result.detail
        assert result.kind is Kind.APPLIED
        installed = home / '.local' / 'bin' / 'demo'
        assert installed.read_bytes() == PAYLOAD
        assert installed.stat().st_mode & stat.S_IXUSR

    def test_a_gzipped_binary_is_decompressed_in_place(self, home, bundle, tmp_path):
        compressed = gzip.compress(PAYLOAD)
        stage(bundle, 'demo-linux-x64.gz', 'demo', 'v1.2.3', compressed)

        result = install_one(ReleaseArtifact('demo-linux-x64.gz', Archive.GZIP), entry(), offline=True)

        assert result.ok, result.detail
        assert result.kind is Kind.APPLIED
        assert (home / '.local' / 'bin' / 'demo').read_bytes() == PAYLOAD

    def test_a_tarball_yields_the_declared_path_and_every_extra_present(self, home, bundle, tmp_path):
        archive = tmp_path / 'demo.tar.gz'
        tarball(archive, {'demo': PAYLOAD, 'proxy': b'proxy', 'nested/other': b'other'})
        stage(bundle, 'demo.tar.gz', 'demo', 'v1.2.3', archive.read_bytes())

        asset = ReleaseArtifact('demo.tar.gz', Archive.TARBALL, path='demo', extras=('proxy', 'nested/other', 'absent'))
        result = install_one(asset, entry(), offline=True)

        assert result.ok, result.detail
        assert result.kind is Kind.APPLIED
        placed = home / '.local' / 'bin'
        assert placed.joinpath('demo').read_bytes() == PAYLOAD
        assert placed.joinpath('proxy').read_bytes() == b'proxy'
        # Named by its basename, wherever it sat in the archive.
        assert placed.joinpath('other').read_bytes() == b'other'
        assert not placed.joinpath('absent').exists()

    def test_a_declared_unit_is_placed_where_systemd_reads_it(self, home, bundle, tmp_path):
        """A release that ships its own supervision should not need a copy of it.

        syncthing publishes `etc/linux-systemd/user/syncthing.service` inside the
        tarball — the same unit its distro packages install. Moving syncthing off
        pacman and brew to one release everywhere took the packaging with it, and
        this is what puts the unit back without hand-maintaining a duplicate that
        drifts from upstream.
        """
        archive = tmp_path / 'demo.tar.gz'
        tarball(archive, {'demo': PAYLOAD, 'etc/linux-systemd/user/demo.service': b'[Unit]\n'})
        stage(bundle, 'demo.tar.gz', 'demo', 'v1.2.3', archive.read_bytes())

        asset = ReleaseArtifact('demo.tar.gz', Archive.TARBALL, path='demo', unit='etc/linux-systemd/user/demo.service')
        result = install_one(asset, entry(), offline=True)

        assert result.ok, result.detail
        placed = home / '.config' / 'systemd' / 'user' / 'demo.service'
        assert placed.read_bytes() == b'[Unit]\n'

    def test_the_unit_is_pointed_at_the_binary_this_installed(self, home, bundle, tmp_path):
        """Upstream's unit names the path its distro package uses, not ours.

        syncthing ships `ExecStart=/usr/bin/syncthing serve --no-browser
        --no-restart`, and a release install puts the binary in ~/.local/bin — so
        the unit as published fails with status 203, exec-not-found. Measured on
        scheduler-lxc 2026-08-16.

        Only the path is rewritten. The arguments stay upstream's, so a release
        that changes them is followed rather than overridden.
        """
        archive = tmp_path / 'demo.tar.gz'
        unit = b'[Service]\nExecStart=/usr/bin/demo serve --no-browser\n'
        tarball(archive, {'demo': PAYLOAD, 'etc/linux-systemd/user/demo.service': unit})
        stage(bundle, 'demo.tar.gz', 'demo', 'v1.2.3', archive.read_bytes())

        asset = ReleaseArtifact('demo.tar.gz', Archive.TARBALL, path='demo', unit='etc/linux-systemd/user/demo.service')
        result = install_one(asset, entry(), offline=True)

        assert result.ok, result.detail
        placed = (home / '.config' / 'systemd' / 'user' / 'demo.service').read_text()
        assert f'ExecStart={home}/.local/bin/demo serve --no-browser' in placed
        assert '/usr/bin/demo' not in placed

    def test_an_exec_line_naming_something_else_is_left_alone(self, home, bundle, tmp_path):
        """Only the tool's own path is ours to correct. A unit calling another
        binary is upstream saying so, and rewriting it would break the call."""
        archive = tmp_path / 'demo.tar.gz'
        unit = b'[Service]\nExecStartPre=/usr/bin/install -d /tmp/demo\nExecStart=/usr/bin/demo\n'
        tarball(archive, {'demo': PAYLOAD, 'etc/linux-systemd/user/demo.service': unit})
        stage(bundle, 'demo.tar.gz', 'demo', 'v1.2.3', archive.read_bytes())

        asset = ReleaseArtifact('demo.tar.gz', Archive.TARBALL, path='demo', unit='etc/linux-systemd/user/demo.service')
        install_one(asset, entry(), offline=True)

        placed = (home / '.config' / 'systemd' / 'user' / 'demo.service').read_text()
        assert 'ExecStartPre=/usr/bin/install -d /tmp/demo' in placed

    def test_a_unit_does_not_land_among_the_binaries(self, home, bundle, tmp_path):
        """`extras` places into the bin directory, which is wrong for a unit: it
        would put a systemd file on PATH and leave systemd unable to find it."""
        archive = tmp_path / 'demo.tar.gz'
        tarball(archive, {'demo': PAYLOAD, 'etc/linux-systemd/user/demo.service': b'[Unit]\n'})
        stage(bundle, 'demo.tar.gz', 'demo', 'v1.2.3', archive.read_bytes())

        asset = ReleaseArtifact('demo.tar.gz', Archive.TARBALL, path='demo', unit='etc/linux-systemd/user/demo.service')
        install_one(asset, entry(), offline=True)

        assert not (home / '.local' / 'bin' / 'demo.service').exists()

    def test_a_unit_is_not_marked_executable(self, home, bundle, tmp_path):
        """A binary earns the bit and a config file does not. systemd runs a unit
        it never executes, so the mode is only ever misleading."""
        archive = tmp_path / 'demo.tar.gz'
        tarball(archive, {'demo': PAYLOAD, 'etc/linux-systemd/user/demo.service': b'[Unit]\n'})
        stage(bundle, 'demo.tar.gz', 'demo', 'v1.2.3', archive.read_bytes())

        asset = ReleaseArtifact('demo.tar.gz', Archive.TARBALL, path='demo', unit='etc/linux-systemd/user/demo.service')
        install_one(asset, entry(), offline=True)

        placed = home / '.config' / 'systemd' / 'user' / 'demo.service'
        assert not placed.stat().st_mode & 0o111

    def test_a_release_declaring_no_unit_writes_nothing_there(self, home, bundle, tmp_path):
        """Every other release in the catalog declares none, so the directory must
        not appear on a machine that asked for nothing."""
        archive = tmp_path / 'demo.tar.gz'
        tarball(archive, {'demo': PAYLOAD})
        stage(bundle, 'demo.tar.gz', 'demo', 'v1.2.3', archive.read_bytes())

        install_one(ReleaseArtifact('demo.tar.gz', Archive.TARBALL, path='demo'), entry(), offline=True)

        assert not (home / '.config' / 'systemd' / 'user' / 'demo.service').exists()

    def test_a_declared_unit_the_archive_lacks_fails_rather_than_passing_quietly(self, home, bundle, tmp_path):
        """Unlike an extra, which upstream adds and removes release by release, a
        unit is declared because this fleet decided to supervise the tool. Missing,
        the tool installs and never runs, which is the silent half-install the
        declaration exists to prevent."""
        archive = tmp_path / 'demo.tar.gz'
        tarball(archive, {'demo': PAYLOAD})
        stage(bundle, 'demo.tar.gz', 'demo', 'v1.2.3', archive.read_bytes())

        asset = ReleaseArtifact('demo.tar.gz', Archive.TARBALL, path='demo', unit='etc/linux-systemd/user/demo.service')
        result = install_one(asset, entry(), offline=True)

        assert not result.ok
        assert result.kind is Kind.ARCHIVE_INCOMPLETE

    def test_a_missing_extra_is_passed_over_rather_than_failing(self, home, bundle, tmp_path):
        """tenv's proxy set has grown release by release, so demanding all of them
        would break on the release before the one that added a name."""
        archive = tmp_path / 'demo.tar.gz'
        tarball(archive, {'demo': PAYLOAD})
        stage(bundle, 'demo.tar.gz', 'demo', 'v1.2.3', archive.read_bytes())

        result = install_one(ReleaseArtifact('demo.tar.gz', Archive.TARBALL, path='demo', extras=('tf', 'tofu')), entry(), offline=True)

        assert result.ok, result.detail
        assert result.kind is Kind.APPLIED

    def test_a_zip_unpacks_the_same_way_a_tarball_does(self, home, bundle, tmp_path):
        archive = tmp_path / 'demo.zip'
        zipped(archive, {'demo-1.0/demo': PAYLOAD})
        stage(bundle, 'demo.zip', 'demo', 'v1.2.3', archive.read_bytes())

        result = install_one(ReleaseArtifact('demo.zip', Archive.ZIP, path='demo-1.0/demo'), entry(), offline=True)

        assert result.ok, result.detail
        assert result.kind is Kind.APPLIED
        assert (home / '.local' / 'bin' / 'demo').read_bytes() == PAYLOAD

    def test_an_archive_without_the_declared_path_fails_rather_than_installing_nothing(self, home, bundle, tmp_path):
        archive = tmp_path / 'demo.tar.gz'
        tarball(archive, {'something-else': PAYLOAD})
        stage(bundle, 'demo.tar.gz', 'demo', 'v1.2.3', archive.read_bytes())

        result = install_one(ReleaseArtifact('demo.tar.gz', Archive.TARBALL, path='demo'), entry(), offline=True)

        assert not result.ok
        assert result.kind is Kind.ARCHIVE_INCOMPLETE
        assert 'contains no demo' in result.detail


class TestTreeInstall:
    """neovim: a runtime directory under ~/.local with a symlink out of it."""

    def test_the_binary_is_a_symlink_into_the_unpacked_tree(self, home, bundle, tmp_path):
        archive = tmp_path / 'nvim.tar.gz'
        tarball(archive, {'nvim-linux/bin/nvim': PAYLOAD, 'nvim-linux/share/runtime': b'runtime'})
        stage(bundle, 'nvim-linux.tar.gz', 'neovim', 'v0.11.0', archive.read_bytes())

        asset = ReleaseArtifact('nvim-linux.tar.gz', Archive.TARBALL, path='nvim-linux/bin/nvim', tree=True)
        result = install_one(asset, entry('neovim', command='nvim'), offline=True)

        assert result.ok, result.detail
        assert result.kind is Kind.APPLIED
        link = home / '.local' / 'bin' / 'nvim'
        assert link.is_symlink()
        assert link.resolve() == home / '.local' / 'nvim-linux' / 'bin' / 'nvim'
        assert (home / '.local' / 'nvim-linux' / 'share' / 'runtime').read_bytes() == b'runtime'

    def test_the_previous_tree_is_removed_rather_than_merged(self, home, bundle, tmp_path):
        """An upgrade unpacked over its predecessor leaves both runtimes, and
        neovim's runtime is version-locked to its binary."""
        stale = home / '.local' / 'nvim-linux' / 'share'
        stale.mkdir(parents=True)
        (stale / 'from-the-old-release').write_bytes(b'stale')

        archive = tmp_path / 'nvim.tar.gz'
        tarball(archive, {'nvim-linux/bin/nvim': PAYLOAD})
        stage(bundle, 'nvim-linux.tar.gz', 'neovim', 'v0.11.0', archive.read_bytes())

        asset = ReleaseArtifact('nvim-linux.tar.gz', Archive.TARBALL, path='nvim-linux/bin/nvim', tree=True)
        result = install_one(asset, entry('neovim', command='nvim'), offline=True)

        assert result.ok, result.detail
        assert result.kind is Kind.APPLIED
        assert not (home / '.local' / 'nvim-linux' / 'share' / 'from-the-old-release').exists()


class TestCompanions:
    """fzf-tmux: fetched at the tag, not optional, and now measurable."""

    def test_a_companion_in_the_bundle_is_installed_beside_the_binary(self, home, bundle):
        stage(bundle, 'demo', 'demo', 'v1.2.3', PAYLOAD)
        (bundle / 'binaries' / 'demo-tmux').write_bytes(b'companion')

        result = install_one(ReleaseArtifact('demo', Archive.RAW), entry(), offline=True, companions=COMPANION)

        assert result.ok, result.detail
        assert result.kind is Kind.APPLIED
        placed = home / '.local' / 'bin' / 'demo-tmux'
        assert placed.read_bytes() == b'companion'
        assert placed.stat().st_mode & stat.S_IXUSR

    def test_a_companion_that_cannot_be_had_fails_the_install(self, home, bundle):
        """Silently skipping it installs a tool whose tmux binding does nothing,
        which surfaces days later at a keystroke rather than here."""
        stage(bundle, 'demo', 'demo', 'v1.2.3', PAYLOAD)

        result = install_one(ReleaseArtifact('demo', Archive.RAW), entry(), offline=True, companions=COMPANION)

        assert not result.ok
        assert result.kind is Kind.NOT_IN_BUNDLE
        assert 'demo-tmux' in result.detail

    def test_an_absent_companion_is_named_without_resolving_a_release(self, home, monkeypatch):
        """The whole point of splitting the name off the URL. Nothing here has a
        tag, a network or a release to consult, and the answer still comes back."""
        monkeypatch.setattr(ghrelease, 'COMPANIONS', {'demo': COMPANION})

        assert ghrelease.missing_companions('demo') == ('demo-tmux',)

    def test_a_companion_on_disk_is_not_reported_missing(self, home, monkeypatch):
        monkeypatch.setattr(ghrelease, 'COMPANIONS', {'demo': COMPANION})
        placed = home / '.local' / 'bin' / 'demo-tmux'
        placed.parent.mkdir(parents=True, exist_ok=True)
        placed.write_bytes(b'companion')

        assert ghrelease.missing_companions('demo') == ()

    def test_a_tool_declaring_no_companions_owes_nothing(self):
        assert ghrelease.missing_companions('demo') == ()


class TestChecksumPolicy:
    """Which verification outcomes are allowed to install, and on whose say-so."""

    @staticmethod
    def refusal(outcome: github_release.Verification, declared: str, monkeypatch) -> str:
        monkeypatch.setattr(github_release, 'verify_release_checksum', lambda *args, **kwargs: outcome)
        return ghrelease._verify(Path('unused'), 'demo.tar.gz', entry(checksum=declared), 'v1', from_bundle=False, offline=False)

    def test_a_verified_asset_installs_whatever_it_declares(self, monkeypatch):
        for declared in sorted(catalog.CHECKSUM_STATES):
            assert self.refusal(github_release.Verification.VERIFIED, declared, monkeypatch) == ''

    def test_a_mismatch_is_refused_even_where_verification_is_declared_optional(self, monkeypatch):
        for declared in sorted(catalog.CHECKSUM_STATES):
            assert 'mismatch' in self.refusal(github_release.Verification.FAILED, declared, monkeypatch)

    def test_the_default_refuses_an_unverifiable_release(self, monkeypatch):
        refused = self.refusal(github_release.Verification.UNPUBLISHED, catalog.CHECKSUM_REQUIRED, monkeypatch)
        assert 'publishes no checksum file' in refused
        assert 'does not declare that' in refused

    def test_each_exception_excuses_only_its_own_state(self, monkeypatch):
        """Declaring one is a claim about what upstream publishes, so it must not
        cover the other — an entry whose upstream changed has to be caught."""
        assert self.refusal(github_release.Verification.UNPUBLISHED, catalog.CHECKSUM_UNPUBLISHED, monkeypatch) == ''
        assert self.refusal(github_release.Verification.UNLISTED, catalog.CHECKSUM_UNLISTED, monkeypatch) == ''
        assert self.refusal(github_release.Verification.UNLISTED, catalog.CHECKSUM_UNPUBLISHED, monkeypatch) != ''
        assert self.refusal(github_release.Verification.UNPUBLISHED, catalog.CHECKSUM_UNLISTED, monkeypatch) != ''

    def test_an_offline_asset_the_bundle_never_digested_is_refused(self, home, bundle):
        """`verify_release_checksum` would answer UNPUBLISHED here after spending
        a timeout on an unreachable API, which reads as a fact about upstream and
        is really a fact about the bundle."""
        (bundle / 'binaries' / 'demo').write_bytes(PAYLOAD)
        (bundle / 'manifest.txt').write_text('binary|demo|v1.2.3|demo\n')

        result = install_one(ReleaseArtifact('demo', Archive.RAW), entry(), offline=True)

        assert not result.ok
        assert result.kind is Kind.UNVERIFIED
        assert 'records no digest' in result.detail

    @pytest.mark.parametrize('declared', [catalog.CHECKSUM_UNPUBLISHED, catalog.CHECKSUM_UNLISTED])
    def test_an_offline_entry_that_declares_it_cannot_verify_still_installs(self, home, bundle, declared):
        """Found by round-tripping a real bundle: `yq` staged fine and then could
        not be installed from it. `create_bundle` records only digests it verified
        upstream, so an entry whose release publishes none is *correctly* absent
        from checksums.txt — and refusing it there makes the two exceptions mean
        'installable online only', which is the opposite of what a bundle is for."""
        (bundle / 'binaries' / 'demo').write_bytes(PAYLOAD)
        (bundle / 'manifest.txt').write_text('binary|demo|v1.2.3|demo\n')

        result = install_one(ReleaseArtifact('demo', Archive.RAW), entry(checksum=declared), offline=True)

        assert result.ok, result.detail
        assert result.kind is Kind.APPLIED
        assert (home / '.local' / 'bin' / 'demo').read_bytes() == PAYLOAD

    def test_a_bundled_asset_that_was_tampered_with_is_refused(self, home, bundle):
        stage(bundle, 'demo', 'demo', 'v1.2.3', PAYLOAD)
        (bundle / 'binaries' / 'demo').write_bytes(b'not what was digested')

        result = install_one(ReleaseArtifact('demo', Archive.RAW), entry(), offline=True)

        assert not result.ok
        assert result.kind is Kind.UNVERIFIED
        assert 'mismatch' in result.detail


class TestTagResolution:
    def test_offline_reads_the_version_the_bundle_staged(self, bundle):
        (bundle / 'manifest.txt').write_text('# header\nbinary|demo|v1.2.3|demo.tar.gz\n')

        assert ghrelease.resolve_tag(entry(), offline=True) == 'v1.2.3'

    def test_a_prefixed_tag_is_rebuilt_from_the_bundled_version(self, bundle):
        """The bundle records the version without the prefix, because that is what
        the tool calls itself; the asset lives under the full tag."""
        (bundle / 'manifest.txt').write_text('binary|icb|v0.9.0|icb_0.9.0_linux_amd64.tar.gz\n')

        assert ghrelease.resolve_tag(entry('icb', release_tag_prefix='cli/'), offline=True) == 'cli/v0.9.0'

    def test_offline_with_nothing_staged_answers_nothing(self, bundle):
        assert ghrelease.resolve_tag(entry(), offline=True) is None

    def test_a_pin_is_matched_against_published_tags(self, monkeypatch):
        monkeypatch.setattr(github_release, 'tag_for_version', lambda repo, version, prefix: f'v{version}')

        assert ghrelease.resolve_tag(entry(version='1.2.3')) == 'v1.2.3'

    def test_latest_is_the_default(self, monkeypatch):
        monkeypatch.setattr(github_release, 'latest_version', lambda repo, prefix: 'v9.9.9')

        assert ghrelease.resolve_tag(entry()) == 'v9.9.9'

    def test_a_pin_nothing_published_refuses_rather_than_falling_back(self, home, bundle, monkeypatch):
        monkeypatch.setattr(github_release, 'tag_for_version', lambda repo, version, prefix: None)
        monkeypatch.setattr(github_release, 'latest_version', lambda repo, prefix: 'v9.9.9')

        result = ghrelease.install(entry('lazygit', version='0.56.0'), LINUX)

        assert not result.ok
        assert result.kind is Kind.VERSION_UNRESOLVED
        assert 'publishes no release for' in result.detail


class TestPreconditions:
    def test_a_tool_with_no_asset_function_refuses_rather_than_crashing(self, home, bundle):
        result = ghrelease.install(entry('never-heard-of-it'), LINUX)

        assert not result.ok
        assert result.kind is Kind.DECLARATION_INVALID

    def test_a_binary_that_does_not_land_on_path_is_a_failure(self, home, bundle, monkeypatch):
        """The last step of every installer it replaces, and the one that catches a
        machine whose ~/.local/bin is not on PATH at all."""
        stage(bundle, 'demo', 'demo', 'v1.2.3', PAYLOAD)
        monkeypatch.setenv('PATH', str(home / 'somewhere-else'))

        result = install_one(ReleaseArtifact('demo', Archive.RAW), entry(), offline=True)

        assert not result.ok
        assert result.kind is Kind.NOT_ON_PATH


def install_one(
    asset: ReleaseArtifact,
    declared: catalog.GithubRelease,
    *,
    offline: bool,
    companions: tuple[Companion, ...] = (),
) -> ghrelease.Result:
    """Run the engine against one synthetic asset."""
    with registered(asset, declared, companions):
        return ghrelease.install(declared, LINUX, offline=offline)


@contextlib.contextmanager
def registered(asset: ReleaseArtifact, declared: catalog.GithubRelease, companions: tuple[Companion, ...] = ()):
    """Put one synthetic asset and its companions in the tables for one test.

    The tables are keyed by `packages.yml` name and every real entry in them is
    covered against live releases, so a test wanting a controlled archive shape
    would otherwise have to pick a real tool and inherit its spelling. Registering
    one for the duration is the smaller lie.
    """
    assets, companion_table = dict(releases.ASSETS), dict(releases.COMPANIONS)
    releases.ASSETS[declared.name] = lambda tag, target: asset
    releases.COMPANIONS[declared.name] = companions
    try:
        yield
    finally:
        releases.ASSETS.clear()
        releases.ASSETS.update(assets)
        releases.COMPANIONS.clear()
        releases.COMPANIONS.update(companion_table)


def test_the_engine_reads_home_at_call_time(tmp_path, monkeypatch):
    """Bound at import, `~/.local/bin` would be the developer's on every machine
    and untestable everywhere — the same reason `paths.cache_home` is a call."""
    monkeypatch.setenv('HOME', str(tmp_path))
    assert ghrelease.bin_dir() == tmp_path / '.local' / 'bin'
    assert os.fspath(ghrelease.local_dir()) == os.fspath(tmp_path / '.local')


class TestZipPermissions:
    """`zipfile.extractall` writes every member 0644 whatever the archive recorded.

    `tar -xf` and `unzip` both preserve the mode, so this is a regression the shell
    never had, and its symptom is not an obvious one: awscli installed, symlinked
    into `~/.local/bin`, and answered `Permission denied` — which `shutil.which`
    reports as *not on PATH*, because it tests for the execute bit.
    """

    @staticmethod
    def zip_with_modes(path: Path, members: dict[str, int]) -> None:
        """A zip carrying whatever names it was given, including hostile ones.

        `zipfile.writestr` records the name verbatim, which is what makes an
        archive able to lie about where its members belong — and why the shapes
        below are the ones worth enumerating.
        """
        with zipfile.ZipFile(path, 'w') as archive:
            for name, mode in members.items():
                info = zipfile.ZipInfo(name)
                info.external_attr = mode << 16
                archive.writestr(info, '#!/bin/sh\nexit 0\n')

    def test_an_executable_member_comes_out_executable(self, tmp_path):
        archive = tmp_path / 'tool.zip'
        self.zip_with_modes(archive, {'aws/install': 0o755})

        assert effects.unpack(archive, tmp_path / 'out')
        assert (tmp_path / 'out' / 'aws' / 'install').stat().st_mode & stat.S_IXUSR

    def test_a_plain_member_stays_plain(self, tmp_path):
        archive = tmp_path / 'tool.zip'
        self.zip_with_modes(archive, {'README.md': 0o644})

        assert effects.unpack(archive, tmp_path / 'out')
        assert not (tmp_path / 'out' / 'README.md').stat().st_mode & stat.S_IXUSR

    def test_a_zip_recording_no_mode_is_left_alone(self, tmp_path):
        """A zip written on Windows records nothing to restore, and a zero there is
        an absent answer rather than a demand for 0000."""
        archive = tmp_path / 'tool.zip'
        with zipfile.ZipFile(archive, 'w') as bundle:
            bundle.writestr(zipfile.ZipInfo('plain.txt'), 'hello')

        assert effects.unpack(archive, tmp_path / 'out')
        assert (tmp_path / 'out' / 'plain.txt').read_text() == 'hello'

    def test_the_file_type_bits_are_never_restored(self, tmp_path):
        """Only the permission bits are taken. The type bits in the same field are
        what `tarfile`'s `data` filter exists to refuse."""
        archive = tmp_path / 'tool.zip'
        self.zip_with_modes(archive, {'thing': 0o100755})

        assert effects.unpack(archive, tmp_path / 'out')
        landed = (tmp_path / 'out' / 'thing').stat().st_mode
        assert stat.S_ISREG(landed)
        assert landed & 0o777 == 0o755

    @pytest.mark.parametrize(
        ('recorded', 'lands_at'),
        [
            ('../escaped', 'escaped'),
            ('/absolute', 'absolute'),
            ('./relative', 'relative'),
            # `..` components are dropped and the rest of the path is kept, so this
            # lands beside its sibling rather than at the root of the extraction.
            ('a/../../climbed', 'a/climbed'),
        ],
    )
    def test_a_member_lying_about_where_it_belongs_is_chmodded_where_it_landed(self, tmp_path, recorded, lands_at):
        """The shapes `ZipFile._extract_member` sanitises, which are exactly the
        ones a reconstructed path gets wrong.

        `into / '/absolute'` is `/absolute` — pathlib resets on an absolute segment
        — and `into / '../escaped'` climbs out, so restoring the mode by rebuilding
        the name chmods a file the extractor never wrote while leaving the one it
        did at 0644. A downloaded archive is not trusted to name its own targets.
        """
        archive = tmp_path / 'hostile.zip'
        into = tmp_path / 'out'
        self.zip_with_modes(archive, {recorded: 0o777})
        outside = tmp_path / 'escaped'
        outside.write_text('untouched')
        before = outside.stat().st_mode

        assert effects.unpack(archive, into)

        landed = into / lands_at
        assert landed.is_file(), f'{recorded!r} should have been written inside {into}'
        assert landed.stat().st_mode & 0o777 == 0o777
        assert outside.stat().st_mode == before, 'a file outside the extraction directory was touched'

    def test_nothing_outside_the_extraction_directory_is_ever_written(self, tmp_path):
        """The property behind the parametrization: whatever an archive claims, the
        blast radius is the directory it was unpacked into."""
        archive = tmp_path / 'hostile.zip'
        into = tmp_path / 'out'
        self.zip_with_modes(archive, {'../a': 0o777, '/b': 0o755, 'c': 0o644})

        assert effects.unpack(archive, into)

        written = {path for path in tmp_path.rglob('*') if path.is_file() and path != archive}
        assert all(into in path.parents for path in written), sorted(str(path) for path in written)
