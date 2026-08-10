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
from dotfiles import github_release
from dotfiles import paths
from dotfiles.coordinates import Arch
from dotfiles.coordinates import OSFamily
from dotfiles.coordinates import Target
from dotfiles.providers import ghrelease
from dotfiles.providers import releases
from dotfiles.providers.releases import Archive
from dotfiles.providers.releases import Asset
from dotfiles.providers.releases import Companion

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
        monkeyed = Asset('demo-linux-x86_64', Archive.RAW)

        result = install_one(monkeyed, entry(), offline=True)

        assert result.ok, result.detail
        installed = home / '.local' / 'bin' / 'demo'
        assert installed.read_bytes() == PAYLOAD
        assert installed.stat().st_mode & stat.S_IXUSR

    def test_a_gzipped_binary_is_decompressed_in_place(self, home, bundle, tmp_path):
        compressed = gzip.compress(PAYLOAD)
        stage(bundle, 'demo-linux-x64.gz', 'demo', 'v1.2.3', compressed)

        result = install_one(Asset('demo-linux-x64.gz', Archive.GZIP), entry(), offline=True)

        assert result.ok, result.detail
        assert (home / '.local' / 'bin' / 'demo').read_bytes() == PAYLOAD

    def test_a_tarball_yields_the_declared_path_and_every_extra_present(self, home, bundle, tmp_path):
        archive = tmp_path / 'demo.tar.gz'
        tarball(archive, {'demo': PAYLOAD, 'proxy': b'proxy', 'nested/other': b'other'})
        stage(bundle, 'demo.tar.gz', 'demo', 'v1.2.3', archive.read_bytes())

        asset = Asset('demo.tar.gz', Archive.TARBALL, path='demo', extras=('proxy', 'nested/other', 'absent'))
        result = install_one(asset, entry(), offline=True)

        assert result.ok, result.detail
        placed = home / '.local' / 'bin'
        assert placed.joinpath('demo').read_bytes() == PAYLOAD
        assert placed.joinpath('proxy').read_bytes() == b'proxy'
        # Named by its basename, wherever it sat in the archive.
        assert placed.joinpath('other').read_bytes() == b'other'
        assert not placed.joinpath('absent').exists()

    def test_a_missing_extra_is_passed_over_rather_than_failing(self, home, bundle, tmp_path):
        """tenv's proxy set has grown release by release, so demanding all of them
        would break on the release before the one that added a name."""
        archive = tmp_path / 'demo.tar.gz'
        tarball(archive, {'demo': PAYLOAD})
        stage(bundle, 'demo.tar.gz', 'demo', 'v1.2.3', archive.read_bytes())

        result = install_one(Asset('demo.tar.gz', Archive.TARBALL, path='demo', extras=('tf', 'tofu')), entry(), offline=True)

        assert result.ok, result.detail

    def test_a_zip_unpacks_the_same_way_a_tarball_does(self, home, bundle, tmp_path):
        archive = tmp_path / 'demo.zip'
        zipped(archive, {'demo-1.0/demo': PAYLOAD})
        stage(bundle, 'demo.zip', 'demo', 'v1.2.3', archive.read_bytes())

        result = install_one(Asset('demo.zip', Archive.ZIP, path='demo-1.0/demo'), entry(), offline=True)

        assert result.ok, result.detail
        assert (home / '.local' / 'bin' / 'demo').read_bytes() == PAYLOAD

    def test_an_archive_without_the_declared_path_fails_rather_than_installing_nothing(self, home, bundle, tmp_path):
        archive = tmp_path / 'demo.tar.gz'
        tarball(archive, {'something-else': PAYLOAD})
        stage(bundle, 'demo.tar.gz', 'demo', 'v1.2.3', archive.read_bytes())

        result = install_one(Asset('demo.tar.gz', Archive.TARBALL, path='demo'), entry(), offline=True)

        assert not result.ok
        assert 'contains no demo' in result.detail


class TestTreeInstall:
    """neovim: a runtime directory under ~/.local with a symlink out of it."""

    def test_the_binary_is_a_symlink_into_the_unpacked_tree(self, home, bundle, tmp_path):
        archive = tmp_path / 'nvim.tar.gz'
        tarball(archive, {'nvim-linux/bin/nvim': PAYLOAD, 'nvim-linux/share/runtime': b'runtime'})
        stage(bundle, 'nvim-linux.tar.gz', 'neovim', 'v0.11.0', archive.read_bytes())

        asset = Asset('nvim-linux.tar.gz', Archive.TARBALL, path='nvim-linux/bin/nvim', tree=True)
        result = install_one(asset, entry('neovim', command='nvim'), offline=True)

        assert result.ok, result.detail
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

        asset = Asset('nvim-linux.tar.gz', Archive.TARBALL, path='nvim-linux/bin/nvim', tree=True)
        result = install_one(asset, entry('neovim', command='nvim'), offline=True)

        assert result.ok, result.detail
        assert not (home / '.local' / 'nvim-linux' / 'share' / 'from-the-old-release').exists()


class TestCompanions:
    """fzf-tmux: fetched at the tag, not optional, and now measurable."""

    def test_a_companion_in_the_bundle_is_installed_beside_the_binary(self, home, bundle):
        stage(bundle, 'demo', 'demo', 'v1.2.3', PAYLOAD)
        (bundle / 'binaries' / 'demo-tmux').write_bytes(b'companion')

        result = install_one(Asset('demo', Archive.RAW), entry(), offline=True, companions=COMPANION)

        assert result.ok, result.detail
        placed = home / '.local' / 'bin' / 'demo-tmux'
        assert placed.read_bytes() == b'companion'
        assert placed.stat().st_mode & stat.S_IXUSR

    def test_a_companion_that_cannot_be_had_fails_the_install(self, home, bundle):
        """Silently skipping it installs a tool whose tmux binding does nothing,
        which surfaces days later at a keystroke rather than here."""
        stage(bundle, 'demo', 'demo', 'v1.2.3', PAYLOAD)

        result = install_one(Asset('demo', Archive.RAW), entry(), offline=True, companions=COMPANION)

        assert not result.ok
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

        result = install_one(Asset('demo', Archive.RAW), entry(), offline=True)

        assert not result.ok
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

        result = install_one(Asset('demo', Archive.RAW), entry(checksum=declared), offline=True)

        assert result.ok, result.detail
        assert (home / '.local' / 'bin' / 'demo').read_bytes() == PAYLOAD

    def test_a_bundled_asset_that_was_tampered_with_is_refused(self, home, bundle):
        stage(bundle, 'demo', 'demo', 'v1.2.3', PAYLOAD)
        (bundle / 'binaries' / 'demo').write_bytes(b'not what was digested')

        result = install_one(Asset('demo', Archive.RAW), entry(), offline=True)

        assert not result.ok
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
        assert 'publishes no release for' in result.detail


class TestPreconditions:
    def test_a_tool_with_no_asset_function_refuses_rather_than_crashing(self, home, bundle):
        result = ghrelease.install(entry('never-heard-of-it'), LINUX)

        assert not result.ok
        assert 'names an asset' in result.detail

    def test_a_binary_that_does_not_land_on_path_is_a_failure(self, home, bundle, monkeypatch):
        """The last step of every installer it replaces, and the one that catches a
        machine whose ~/.local/bin is not on PATH at all."""
        stage(bundle, 'demo', 'demo', 'v1.2.3', PAYLOAD)
        monkeypatch.setenv('PATH', str(home / 'somewhere-else'))

        result = install_one(Asset('demo', Archive.RAW), entry(), offline=True)

        assert not result.ok
        assert 'not on PATH' in result.detail


def install_one(
    asset: Asset,
    declared: catalog.GithubRelease,
    *,
    offline: bool,
    companions: tuple[Companion, ...] = (),
) -> ghrelease.Result:
    """Run the engine against one synthetic asset."""
    with registered(asset, declared, companions):
        return ghrelease.install(declared, LINUX, offline=offline)


@contextlib.contextmanager
def registered(asset: Asset, declared: catalog.GithubRelease, companions: tuple[Companion, ...] = ()):
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
