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
import plistlib
import stat
import tarfile
import zipfile
from pathlib import Path

import pytest

from dotfiles import catalog
from dotfiles import effects
from dotfiles import github_release
from dotfiles import providers
from dotfiles.coordinates import Arch
from dotfiles.coordinates import OSFamily
from dotfiles.coordinates import Target
from dotfiles.providers import Kind
from dotfiles.providers import ghrelease
from dotfiles.providers import launchd
from dotfiles.providers import releases
from dotfiles.providers.releases import Archive
from dotfiles.providers.releases import Companion
from dotfiles.providers.releases import LaunchAgent
from dotfiles.providers.releases import ReleaseArtifact

LINUX = Target(OSFamily.LINUX, Arch.X86_64)
DARWIN = Target(OSFamily.DARWIN, Arch.ARM64)

AGENT = LaunchAgent('com.example.demo', ('serve', '--no-browser'))
"""A declared agent for a tool no release publishes, for the reason `registered`
gives about assets: every real name in the table is measured against a live
release, so borrowing one to test a placement inherits its spelling."""

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
    root = tmp_path / 'staged'
    staged = root / 'dotfiles-offline-v20260814T190203Z-box-linux-x86_64'
    (staged / 'binaries').mkdir(parents=True)
    (staged / providers.MANIFEST).write_text('')
    monkeypatch.setenv('DOTFILES_BUNDLE', str(root))
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
        result = install_one(asset, entry(), offline=True)

        # The absence alone is satisfied by an install that never ran: measured,
        # this file with nothing staged reports ok=False, places no binary, and
        # the assertion below still holds.
        assert result.ok, result.detail
        assert (home / '.local' / 'bin' / 'demo').exists()
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

        result = install_one(ReleaseArtifact('demo.tar.gz', Archive.TARBALL, path='demo'), entry(), offline=True)

        assert result.ok, result.detail
        assert (home / '.local' / 'bin' / 'demo').exists()
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

    def test_a_companion_comes_from_the_bundle_that_supplied_the_binary(self, home, bundle, tmp_path):
        """A companion filename carries no version, so an unpinned lookup returns
        whichever staged bundle is newest — pairing an older bundle's binary with a
        newer bundle's companion, which is what `_verify` was already changed to
        stop doing for a checksum."""
        newer = tmp_path / 'staged' / 'dotfiles-offline-v20260901T000000Z-box-linux-x86_64'
        (newer / 'binaries').mkdir(parents=True)
        (newer / providers.MANIFEST).write_text('')
        (newer / 'binaries' / 'demo-tmux').write_bytes(b'from the newer bundle')

        stage(bundle, 'demo', 'demo', 'v1.2.3', PAYLOAD)
        (bundle / 'binaries' / 'demo-tmux').write_bytes(b'companion')

        result = install_one(ReleaseArtifact('demo', Archive.RAW), entry(), offline=True, companions=COMPANION)

        assert result.ok, result.detail
        assert (home / '.local' / 'bin' / 'demo-tmux').read_bytes() == b'companion'

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

    def test_a_pin_whose_releases_could_not_be_read_says_so_instead(self, home, bundle, monkeypatch):
        """Same refusal, opposite cause, and the sentence is the whole difference.

        60 anonymous API calls an hour is fewer than one full install spends, so
        this is the reachable state — and reporting it as an unpublished version
        sends whoever reads it to `packages.yml` to correct a pin that was right.
        """

        def refuse(repo, version, prefix):
            raise github_release.Unreadable(f'could not read the releases of {repo}, so its published versions are unknown')

        monkeypatch.setattr(github_release, 'tag_for_version', refuse)

        result = ghrelease.install(entry('lazygit', version='0.56.0'), LINUX)

        assert not result.ok
        assert result.kind is Kind.VERSION_UNRESOLVED
        assert 'could not read the releases' in result.detail
        assert 'publishes no release for' not in result.detail, 'the wrong sentence is the defect, not the refusal'


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


class TestLaunchAgent:
    """The macOS half of a supervised release, which upstream cannot publish for us.

    syncthing's archive does carry `etc/macos-launchd/syncthing.plist`, and it is an
    example rather than a unit: `/Users/USERNAME` four times, the binary out of
    `~/bin`, and a README telling the reader to edit it. So the plist is authored in
    `releases.AGENTS` where the systemd unit is taken from the archive, and these
    assert the half that has no upstream file to compare against.
    """

    def test_a_declared_agent_lands_where_launchd_reads_it(self, home, bundle):
        stage(bundle, 'demo', 'demo', 'v1.2.3', PAYLOAD)

        result = install_one(ReleaseArtifact('demo', Archive.RAW), entry(), offline=True, target=DARWIN, agent=AGENT)

        assert result.ok, result.detail
        placed = home / 'Library' / 'LaunchAgents' / 'com.example.demo.plist'
        assert plistlib.loads(placed.read_bytes())['Label'] == 'com.example.demo'

    def test_the_plist_runs_the_binary_this_install_placed(self, home, bundle):
        """The same correction `_exec_at` makes to a systemd unit, and the reason it
        cannot come from upstream: the published example names `~/bin/syncthing` and
        a release install puts the binary under `~/.local/bin`."""
        stage(bundle, 'demo', 'demo', 'v1.2.3', PAYLOAD)

        install_one(ReleaseArtifact('demo', Archive.RAW), entry(), offline=True, target=DARWIN, agent=AGENT)

        placed = plistlib.loads((home / 'Library' / 'LaunchAgents' / 'com.example.demo.plist').read_bytes())
        assert placed['ProgramArguments'] == [str(home / '.local' / 'bin' / 'demo'), 'serve', '--no-browser']

    def test_the_job_is_a_daemon_rather_than_a_one_shot(self, home, bundle):
        """What declaring an agent at all means. Without `KeepAlive` launchd runs it
        once and forgets it, which is a sync daemon that stops at the first restart
        and a machine nothing reports as wrong."""
        stage(bundle, 'demo', 'demo', 'v1.2.3', PAYLOAD)

        install_one(ReleaseArtifact('demo', Archive.RAW), entry(), offline=True, target=DARWIN, agent=AGENT)

        placed = plistlib.loads((home / 'Library' / 'LaunchAgents' / 'com.example.demo.plist').read_bytes())
        assert placed['KeepAlive'] is True
        assert placed['RunAtLoad'] is True
        assert placed['StandardErrorPath'].endswith('demo-errors.log'), 'launchd sends a job output nowhere by default'

    def test_a_linux_target_gets_no_agent(self, home, bundle):
        """The declaration is macOS's half, so the same entry on Linux is supervised
        by the unit out of the archive and by nothing here."""
        stage(bundle, 'demo', 'demo', 'v1.2.3', PAYLOAD)

        result = install_one(ReleaseArtifact('demo', Archive.RAW), entry(), offline=True, target=LINUX, agent=AGENT)

        assert result.ok, result.detail
        assert not (home / 'Library' / 'LaunchAgents').exists()

    def test_a_release_declaring_no_agent_writes_nothing_there(self, home, bundle):
        """Every entry but one declares none, so the directory must not appear on a
        Mac that asked for nothing."""
        stage(bundle, 'demo', 'demo', 'v1.2.3', PAYLOAD)

        result = install_one(ReleaseArtifact('demo', Archive.RAW), entry(), offline=True, target=DARWIN)

        assert result.ok, result.detail
        assert (home / '.local' / 'bin' / 'demo').exists()
        assert not (home / 'Library' / 'LaunchAgents').exists()

    def test_a_plist_that_cannot_be_written_fails_the_install(self, home, bundle):
        """The same bet the declared unit makes: silently skipping the supervision
        installs a daemon that never runs, which is worse than a failed install."""
        stage(bundle, 'demo', 'demo', 'v1.2.3', PAYLOAD)
        (home / 'Library').mkdir()
        (home / 'Library' / 'LaunchAgents').write_text('not a directory')

        result = install_one(ReleaseArtifact('demo', Archive.RAW), entry(), offline=True, target=DARWIN, agent=AGENT)

        assert not result.ok
        assert result.kind is Kind.WRITE_FAILED

    def test_the_agent_is_booted_out_before_it_is_bootstrapped(self, home, bundle):
        """`bootstrap` refuses a label already loaded, so without the bootout an
        agent whose arguments changed keeps the definition launchd holds and the
        command still reports success."""
        stage(bundle, 'demo', 'demo', 'v1.2.3', PAYLOAD)
        log = recording(home, 'launchctl')

        install_one(ReleaseArtifact('demo', Archive.RAW), entry(), offline=True, target=DARWIN, agent=AGENT)

        verbs = [line.split()[0] for line in log.read_text().splitlines()]
        assert verbs == ['bootout', 'bootstrap']

    def test_a_machine_launchctl_will_not_answer_on_still_installs(self, home, bundle):
        """A plist under `~/Library/LaunchAgents` is loaded at the next login whether
        or not anything asked, so the load is a convenience and failing the install
        over it would strand the binary for the sake of not logging out."""
        stage(bundle, 'demo', 'demo', 'v1.2.3', PAYLOAD)
        recording(home, 'launchctl', exit_code=1)

        result = install_one(ReleaseArtifact('demo', Archive.RAW), entry(), offline=True, target=DARWIN, agent=AGENT)

        assert result.ok, result.detail
        assert (home / 'Library' / 'LaunchAgents' / 'com.example.demo.plist').is_file()


class TestSupervisionEvidence:
    """What `check` reads, answered without resolving a release.

    `missing_companions`' property, for the same reason: a checker offline or out of
    API budget still gets an answer, so nothing here has a tag or a target.
    """

    def test_a_tool_declaring_no_agent_owes_nothing(self, home):
        assert ghrelease.unsupervised('demo', 'demo') == ''

    def test_a_machine_with_no_launchd_owes_nothing(self, home):
        """The platform test, and it is the honest one: the question is whether
        launchd can be asked, and a Linux box that declares the same release is
        supervised by its unit instead."""
        with supervised('demo', AGENT):
            assert ghrelease.unsupervised('demo', 'demo') == ''

    def test_an_absent_plist_is_reported(self, home):
        recording(home, 'launchctl')

        with supervised('demo', AGENT):
            assert 'does not exist' in ghrelease.unsupervised('demo', 'demo')

    def test_a_plist_that_differs_from_the_declaration_is_reported(self, home):
        """The state nobody can see. launchd goes on running the definition it
        loaded, so an agent whose arguments moved in this repo is running the old
        ones with nothing on the machine saying so."""
        recording(home, 'launchctl')
        placed = home / 'Library' / 'LaunchAgents' / 'com.example.demo.plist'
        placed.parent.mkdir(parents=True)
        placed.write_bytes(ghrelease.agent_plist(LaunchAgent(AGENT.label, ('serve',)), home / '.local' / 'bin' / 'demo'))

        with supervised('demo', AGENT):
            assert 'differs from what this repo declares' in ghrelease.unsupervised('demo', 'demo')

    def test_a_plist_launchd_has_not_loaded_is_reported(self, home):
        recording(home, 'launchctl', exit_code=1)
        _write_agent(home, AGENT)

        with supervised('demo', AGENT):
            assert 'has not loaded it' in ghrelease.unsupervised('demo', 'demo')

    def test_a_loaded_agent_owes_nothing(self, home):
        recording(home, 'launchctl')
        _write_agent(home, AGENT)

        with supervised('demo', AGENT):
            assert ghrelease.unsupervised('demo', 'demo') == ''


UNIT = 'etc/linux-systemd/user/demo.service'

UNIT_BODY = b'[Unit]\nDescription=demo\n\n[Service]\nExecStart=/usr/bin/demo serve\n\n[Install]\nWantedBy=default.target\n'


def with_unit(tmp_path: Path, bundle: Path) -> ReleaseArtifact:
    """A release that publishes its own unit, staged the way syncthing's is."""
    archive = tmp_path / 'demo.tar.gz'
    tarball(archive, {'demo': PAYLOAD, UNIT: UNIT_BODY})
    stage(bundle, 'demo.tar.gz', 'demo', 'v1.2.3', archive.read_bytes())
    return ReleaseArtifact('demo.tar.gz', Archive.TARBALL, path='demo', unit=UNIT)


class TestSystemdUnit:
    """The Linux half of a supervised release, which is a write rather than a file.

    A plist under `~/Library/LaunchAgents` is loaded at the next login whether or not
    anything asked. A systemd user unit is inert until something enables it, so
    placing the file and stopping is a daemon that never runs — and `check` reported
    that machine converged, on the one box in the fleet that actually runs syncthing.
    """

    def test_a_placed_unit_is_enabled(self, home, bundle, tmp_path, monkeypatch):
        log = recording(home, 'systemctl')

        result = install_one(with_unit(tmp_path, bundle), entry(), offline=True)

        assert result.ok, result.detail
        assert log.read_text().splitlines() == ['--user daemon-reload', '--user enable --now demo.service']

    def test_the_reload_comes_before_the_enable(self, home, bundle, tmp_path, monkeypatch):
        """Without it systemd enables the copy it read at boot, which for a unit this
        install has just written is the previous one or nothing at all."""
        log = recording(home, 'systemctl')

        install_one(with_unit(tmp_path, bundle), entry(), offline=True)

        assert log.read_text().index('daemon-reload') < log.read_text().index('enable')

    def test_an_enable_that_fails_fails_the_install(self, home, bundle, tmp_path, monkeypatch):
        """The opposite call to launchd's, and the same question decides both: what
        does the file buy on its own. Nothing here."""
        recording(home, 'systemctl', exit_code=1)

        result = install_one(with_unit(tmp_path, bundle), entry(), offline=True)

        assert not result.ok
        assert result.kind is Kind.COMMAND_FAILED

    def test_a_machine_with_no_systemd_installs_without_one(self, home, bundle, tmp_path):
        """A container or a WSL host without a user manager owes no unit, and the
        binary is still what was asked for."""
        result = install_one(with_unit(tmp_path, bundle), entry(), offline=True)

        assert result.ok, result.detail
        assert (home / '.local' / 'bin' / 'demo').is_file()


class TestUnitEvidence:
    """The Linux half of `unsupervised`, and the three states it separates.

    The unit's body comes out of the archive rather than from this repo, so there is
    nothing to compare it against offline — except the one part `_place` authors,
    which is the `ExecStart` path. That is also the half that goes wrong: a unit
    still naming `/usr/bin` after the package it came from was removed is
    exec-not-found on every start.
    """

    def test_a_machine_with_no_systemd_owes_nothing(self, home, bundle, tmp_path):
        with registered(with_unit(tmp_path, bundle), entry()):
            assert ghrelease.unsupervised('demo', 'demo') == ''

    def test_an_absent_unit_is_reported(self, home, bundle, tmp_path):
        recording(home, 'systemctl')

        with registered(with_unit(tmp_path, bundle), entry()):
            assert 'does not exist' in ghrelease.unsupervised('demo', 'demo')

    def test_a_unit_starting_something_else_is_reported(self, home, bundle, tmp_path):
        """The state the migration produces: the release places a unit and the
        `ExecStart` still names the path the removed package used."""
        recording(home, 'systemctl')
        _write_unit(home, UNIT_BODY.decode())

        with registered(with_unit(tmp_path, bundle), entry()):
            assert 'does not start' in ghrelease.unsupervised('demo', 'demo')

    def test_a_unit_systemd_has_not_enabled_is_reported(self, home, bundle, tmp_path):
        recording(home, 'systemctl', exit_code=1)
        _write_unit(home, f'[Service]\nExecStart={home}/.local/bin/demo serve\n')

        with registered(with_unit(tmp_path, bundle), entry()):
            assert 'has not enabled it' in ghrelease.unsupervised('demo', 'demo')

    def test_an_enabled_unit_owes_nothing(self, home, bundle, tmp_path):
        recording(home, 'systemctl')
        _write_unit(home, f'[Service]\nExecStart={home}/.local/bin/demo serve\n')

        with registered(with_unit(tmp_path, bundle), entry()):
            assert ghrelease.unsupervised('demo', 'demo') == ''


def _write_unit(home: Path, body: str) -> Path:
    placed = ghrelease.unit_dir() / 'demo.service'
    placed.parent.mkdir(parents=True, exist_ok=True)
    placed.write_text(body)
    return placed


def _write_agent(home: Path, agent: LaunchAgent) -> Path:
    """The plist exactly as an install would have left it, so a comparison passes."""
    placed = launchd.agent_path(agent.label)
    placed.parent.mkdir(parents=True, exist_ok=True)
    placed.write_bytes(ghrelease.agent_plist(agent, home / '.local' / 'bin' / 'demo'))
    return placed


def recording(home: Path, name: str, *, exit_code: int = 0) -> Path:
    """A binary on this test's PATH that writes its arguments down and exits.

    Invariants are asserted by spying on argv: the question is
    which command the engine built, and the real `launchctl` would answer about the
    machine the suite happens to run on.
    """
    log = home / f'{name}.argv'
    placed = home / '.local' / 'bin' / name
    placed.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> {log}\nexit {exit_code}\n')
    placed.chmod(0o755)
    return log


@contextlib.contextmanager
def supervised(name: str, agent: LaunchAgent):
    """Declare one entry's LaunchAgent for the duration of a test.

    In place rather than by rebinding, because `ghrelease` imports the table by
    name — the same reason `registered` mutates `ASSETS` rather than replacing it.
    """
    table = dict(releases.AGENTS)
    releases.AGENTS[name] = agent
    try:
        yield
    finally:
        releases.AGENTS.clear()
        releases.AGENTS.update(table)


def install_one(
    asset: ReleaseArtifact,
    declared: catalog.GithubRelease,
    *,
    offline: bool,
    companions: tuple[Companion, ...] = (),
    target: Target = LINUX,
    agent: LaunchAgent | None = None,
) -> ghrelease.Result:
    """Run the engine against one synthetic asset."""
    with registered(asset, declared, companions), supervised(declared.name, agent) if agent else contextlib.nullcontext():
        return ghrelease.install(declared, target, offline=offline)


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
