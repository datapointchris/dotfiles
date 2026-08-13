"""Tests for create_bundle.py

These replace three bats files that needed a shell, a fixture tree and, for some
of them, a container. Everything below runs in-process against a function that
returns a value.

Run with: pytest tests/install/test_create_bundle.py
"""

import datetime as dt
import tarfile
import zipfile

import pytest

from dotfiles import catalog
from dotfiles import create_bundle
from dotfiles import paths
from dotfiles.coordinates import Arch
from dotfiles.coordinates import OSFamily
from dotfiles.coordinates import Target
from dotfiles.providers import bundle as bundle_manifest
from dotfiles.providers import cargo
from dotfiles.providers import ghrelease
from dotfiles.providers import gotool
from dotfiles.providers import releases
from dotfiles.resolve import DesiredItem
from dotfiles.resolve import Precondition
from dotfiles.resolve import Reason
from dotfiles.resolve import Stage


def planned(entry, section):
    """One row as the resolver would hand it to the bundler.

    Built here rather than resolved from a manifest because the entry under test
    is invented: what this fixes is the *shape* the bundler consumes, and the
    resolver producing that shape from a real manifest is `tests/resolver/`'s
    question rather than this file's.
    """
    return DesiredItem(
        section=section,
        provider='cargo',
        resource='packages',
        stage=Stage.TOOLS,
        name=entry.name,
        executable=entry.executable,
        evidence_path='',
        precondition=Precondition.NONE,
        entry=entry,
        reason=Reason(section, f'manifest:{section}'),
    )


class TestPlatform:
    def test_the_bundle_name_carries_date_manifest_and_platform(self):
        name = create_bundle.bundle_name('wsl-work-workstation', 'linux', 'x86_64', dt.date(2026, 8, 7))
        assert name == 'dotfiles-offline-v20260807-wsl-work-workstation-linux-x86_64'


LINUX_X86 = Target(OSFamily.LINUX, Arch.X86_64)
LINUX_ARM = Target(OSFamily.LINUX, Arch.ARM64)
MACOS_ARM = Target(OSFamily.DARWIN, Arch.ARM64)
MACOS_X86 = Target(OSFamily.DARWIN, Arch.X86_64)


def crate(**fields) -> catalog.CargoPackage:
    return catalog.CargoPackage.from_mapping({'name': 'tool', **fields})


class TestCargoTarget:
    """Naming lives in the provider that installs from the name; these are the
    same cases the bundler would otherwise answer for itself."""

    def test_defaults_to_the_triple_for_the_platform(self):
        assert cargo.asset_target(crate(), LINUX_X86) == 'x86_64-unknown-linux-gnu'
        assert cargo.asset_target(crate(), MACOS_ARM) == 'aarch64-apple-darwin'
        assert cargo.asset_target(crate(), MACOS_X86) == 'x86_64-apple-darwin'

    def test_linux_is_not_assumed_to_be_x86(self):
        """It was, and a linux-arm64 bundle therefore carried x86_64 cargo binaries —
        an archive that builds cleanly and installs a machine that cannot run them."""
        assert cargo.asset_target(crate(), LINUX_ARM) == 'aarch64-unknown-linux-gnu'
        assert cargo.triple(LINUX_ARM) == 'aarch64-unknown-linux-gnu'

    def test_an_override_applies_only_to_its_own_platform(self):
        # fnm ships fnm-linux.zip and fnm-macos.zip, named after neither triple.
        fnm = crate(linux_target='linux', darwin_target='macos')
        assert cargo.asset_target(fnm, LINUX_X86) == 'linux'
        assert cargo.asset_target(fnm, MACOS_ARM) == 'macos'
        # A linux override must not leak into the darwin answer.
        assert cargo.asset_target(crate(linux_target='x86_64-unknown-linux-musl'), MACOS_ARM) == 'aarch64-apple-darwin'


class TestPatternExpansion:
    def test_version_placeholders_differ_by_the_leading_v(self):
        assert releases.expand_pattern('tool-{version}.tar.gz', 'v1.2.3', LINUX_X86) == 'tool-v1.2.3.tar.gz'
        assert releases.expand_pattern('tool-{version_num}.tar.gz', 'v1.2.3', LINUX_X86) == 'tool-1.2.3.tar.gz'

    def test_architecture_spellings_cover_every_upstream_convention(self):
        # Go releases name the architecture amd64 where the kernel says x86_64.
        assert releases.expand_pattern('{os}_{go_arch}', 'v1', LINUX_X86) == 'linux_amd64'
        assert releases.expand_pattern('{os}_{go_arch}', 'v1', MACOS_ARM) == 'darwin_arm64'
        # Capitalised kernel names (gum, lazydocker).
        assert releases.expand_pattern('{Os}_{Arch}', 'v1', LINUX_X86) == 'Linux_x86_64'
        # The product name for Apple rather than the kernel name (jira-cli).
        assert releases.expand_pattern('{os_mac}', 'v1', MACOS_ARM) == 'macOS'
        assert releases.expand_pattern('{Os_mac}', 'v1', LINUX_X86) == 'Linux'

    def test_the_rust_target_triple_is_substituted_whole(self):
        entry = crate(binary_pattern='rg-{version}-{target}.tar.gz', linux_target='x86_64-unknown-linux-musl')

        assert cargo.stage(entry, 'v14.1.0', LINUX_X86) == 'rg-v14.1.0-x86_64-unknown-linux-musl.tar.gz'

    def test_the_two_sections_disagree_about_arm_and_each_gets_its_own_spelling(self):
        """A cargo tool's assets say aarch64 and a Go tool's say arm64, for the same
        CPU. Each provider carries its own spelling, rather than the bundler
        passing a different arch string per section from two call sites."""
        pattern = {'binary_pattern': '{platform}_{arch}.tar.gz'}

        assert cargo.stage(crate(**pattern), 'v1', MACOS_ARM) == 'apple_darwin_aarch64.tar.gz'
        assert gotool.stage(catalog.GoTool.from_mapping({'name': 'tool', 'package': 'x', **pattern}), 'v1', MACOS_ARM) == (
            'apple_darwin_arm64.tar.gz'
        )


class TestAssetIdentity:
    """The cache keys on what an asset *is*, not on the URL that reached it.

    Keying on the URL is the same thing only while an asset has one URL. The
    release API hands back a `browser_download_url` whose host varies, so the
    moment anything resolves a download that way the key starts depending on
    which server answered and every warm entry misses.
    """

    def test_a_release_asset_is_keyed_on_repo_tag_and_name(self):
        asset = create_bundle.release_asset('https://github.com/sharkdp/fd/releases/download/v10.2.0/fd.tar.gz')
        assert asset.key == ('github', 'sharkdp/fd', 'v10.2.0', 'fd.tar.gz')
        assert asset.release == ('sharkdp/fd', 'v10.2.0')
        assert asset.filename == 'fd.tar.gz'

    def test_the_same_release_reached_by_two_hosts_is_one_cache_entry(self):
        browser = create_bundle.release_asset('https://github.com/sharkdp/fd/releases/download/v10.2.0/fd.tar.gz')
        direct = create_bundle.github_asset('sharkdp/fd', 'v10.2.0', 'fd.tar.gz')
        assert create_bundle.cache_path_for(browser.key) == create_bundle.cache_path_for(direct.key)

    def test_a_new_release_is_a_new_entry(self):
        # The cache has no staleness check; the tag is what makes an entry miss.
        old = create_bundle.github_asset('o/r', 'v1.0.0', 'tool.tar.gz')
        new = create_bundle.github_asset('o/r', 'v1.1.0', 'tool.tar.gz')
        assert create_bundle.cache_path_for(old.key) != create_bundle.cache_path_for(new.key)

    def test_something_that_is_not_a_release_falls_back_to_its_url(self):
        asset = create_bundle.release_asset('https://astral.sh/uv/install.sh')
        assert asset.release is None
        assert asset.key[0] == 'url'

    def test_a_traversal_cannot_escape_the_cache_root(self):
        path = create_bundle.cache_path_for(create_bundle.url_asset('https://evil.example/../../../etc/passwd').key)
        assert '..' not in path.parts
        assert str(path).startswith(str(create_bundle.CACHE_ROOT))

    def test_characters_outside_the_portable_set_become_underscores(self):
        path = create_bundle.cache_path_for(create_bundle.url_asset('https://example.com/a b;rm -rf/x.tar.gz').key)
        assert ' ' not in str(path)
        assert ';' not in str(path)


class TestWheelSelection:
    """Which wheels a bundle carries, so `uv tool install` needs no index.

    Getting this wrong is silent on the build machine and fatal on the target:
    an over-broad match ships a wheel that cannot install, and a narrow one ships
    nothing for the interpreter the machine actually has.
    """

    def test_a_pure_python_wheel_installs_on_every_target(self):
        for os_name, arch in create_bundle.WHEEL_PLATFORMS:
            assert create_bundle.wheel_matches('typer-0.19.1-py3-none-any.whl', os_name, arch)

    def test_a_platform_wheel_matches_only_its_own_target(self):
        wheel = 'PyYAML-6.0.3-cp314-cp314-manylinux_2_17_x86_64.manylinux2014_x86_64.whl'
        assert create_bundle.wheel_matches(wheel, 'linux', 'x86_64')
        assert not create_bundle.wheel_matches(wheel, 'linux', 'arm64')
        assert not create_bundle.wheel_matches(wheel, 'darwin', 'x86_64')

    def test_every_installable_cpython_version_is_taken(self):
        """The machine's interpreter is whatever it is at or above the floor, and
        picking one from the wrong side of a firewall is deciding a fact only the
        target knows. Below the floor is different: uv would refuse the install, so
        those wheels are weight — they were 7MB of an 8.7MB wheelhouse."""
        floor = create_bundle.python_floor()
        for minor in range(floor, floor + 3):
            wheel = f'PyYAML-6.0.3-cp3{minor}-cp3{minor}-macosx_11_0_arm64.whl'
            assert create_bundle.wheel_matches(wheel, 'darwin', 'arm64')
        for minor in range(8, floor):
            wheel = f'PyYAML-6.0.3-cp3{minor}-cp3{minor}-macosx_11_0_arm64.whl'
            assert not create_bundle.wheel_matches(wheel, 'darwin', 'arm64')

    def test_the_floor_is_read_from_requires_python(self):
        """Written here, it would be true only until the floor moved — and the
        symptom of a stale one is a bundle quietly carrying unusable wheels."""
        import tomllib

        from dotfiles import paths

        declared = tomllib.loads(paths.PYPROJECT_FILE.read_text())['project']['requires-python']
        assert f'3.{create_bundle.python_floor()}' in declared

    def test_a_universal_macos_wheel_serves_both_architectures(self):
        wheel = 'PyYAML-6.0.3-cp313-cp313-macosx_10_9_universal2.whl'
        assert create_bundle.wheel_matches(wheel, 'darwin', 'arm64')
        assert create_bundle.wheel_matches(wheel, 'darwin', 'x86_64')

    def test_musl_and_pypy_are_refused(self):
        """This fleet is glibc, and uv will not pick a pypy interpreter here."""
        assert not create_bundle.wheel_matches('PyYAML-6.0.3-cp314-cp314-musllinux_1_2_x86_64.whl', 'linux', 'x86_64')
        assert not create_bundle.wheel_matches('PyYAML-6.0.3-pp310-pypy310_pp73-manylinux_2_17_x86_64.whl', 'linux', 'x86_64')

    def test_an_sdist_is_not_a_wheel(self):
        assert not create_bundle.wheel_matches('PyYAML-6.0.3.tar.gz', 'linux', 'x86_64')


class TestDeclaredClosure:
    def test_the_closure_is_read_from_uvs_own_lockfile(self):
        """Pinned versions, and never a hand-listed set — a list here would drift
        from uv.lock the first time a dependency moved."""
        closure = create_bundle.declared_closure()
        assert closure, 'an empty closure would make every assertion below vacuous'
        assert dict(closure).keys() >= {'typer', 'rich', 'pyyaml'}
        assert all(version and not version.startswith('=') for _, version in closure)

    def test_a_marker_does_not_stop_a_package_being_carried(self):
        """colorama is win32-only. Carrying it costs 14KB and uv applies the
        marker at install time; leaving it out cannot be undone on the target."""
        assert 'colorama' in dict(create_bundle.declared_closure())


class TestArchives:
    def test_a_flat_zip_becomes_a_tarball_and_the_zip_is_consumed(self, tmp_path):
        zip_path = tmp_path / 'fnm-linux.zip'
        with zipfile.ZipFile(zip_path, 'w') as archive:
            archive.writestr('fnm', 'FLAT-ZIP-BINARY')

        name = create_bundle.repackage_zip_as_tarball(zip_path, 'fnm', 'linux', '1.39.0')

        assert name == 'fnm_1.39.0_linux.tar.gz'
        assert not zip_path.exists()
        with tarfile.open(tmp_path / name) as tar:
            assert tar.getnames() == ['fnm']
            assert tar.extractfile('fnm').read() == b'FLAT-ZIP-BINARY'

    def test_a_fat_zip_yields_the_requested_platform_not_another(self, tmp_path):
        zip_path = tmp_path / 'broot.zip'
        with zipfile.ZipFile(zip_path, 'w') as archive:
            archive.writestr('x86_64-unknown-linux-gnu/broot', 'WANTED')
            archive.writestr('aarch64-apple-darwin/broot', 'WRONG')

        name = create_bundle.repackage_zip_as_tarball(zip_path, 'broot', 'x86_64-unknown-linux-gnu', '1.56.2')

        with tarfile.open(tmp_path / name) as tar:
            assert tar.extractfile('broot').read() == b'WANTED'

    def test_a_zip_without_the_binary_fails_rather_than_bundling_nothing(self, tmp_path):
        zip_path = tmp_path / 'fnm.zip'
        with zipfile.ZipFile(zip_path, 'w') as archive:
            archive.writestr('somethingelse', 'x')

        with pytest.raises(create_bundle.BundleError, match='Could not find fnm'):
            create_bundle.repackage_zip_as_tarball(zip_path, 'fnm', 'linux', '1.0.0')

    def test_a_go_binary_is_found_under_its_platform_suffixed_name(self, tmp_path):
        # gdu ships the binary as gdu_linux_amd64 inside the archive.
        payload = tmp_path / 'gdu_linux_amd64'
        payload.write_text('GDU')
        archive_path = tmp_path / 'gdu.tar.gz'
        with tarfile.open(archive_path, 'w:gz') as tar:
            tar.add(payload, arcname='gdu_linux_amd64')
        payload.unlink()

        destination = tmp_path / 'gdu'
        create_bundle.extract_go_binary(archive_path, 'gdu', destination)

        assert destination.read_text() == 'GDU'
        assert destination.stat().st_mode & 0o111

    def test_a_raw_binary_release_is_moved_rather_than_unpacked(self, tmp_path):
        # goose and gofumpt publish the bare executable.
        archive_path = tmp_path / 'gofumpt_linux_amd64'
        archive_path.write_text('GOFUMPT')

        destination = tmp_path / 'gofumpt'
        create_bundle.extract_go_binary(archive_path, 'gofumpt', destination)

        assert destination.read_text() == 'GOFUMPT'
        assert not archive_path.exists()


class TestFailureDetail:
    def test_the_tail_is_kept_because_that_is_where_the_cause_is(self):
        text = '\n'.join(str(n) for n in range(1, 101))
        detail = create_bundle.tail_lines(text, limit=5)
        assert detail.splitlines() == ['96', '97', '98', '99', '100']

    def test_blank_lines_do_not_consume_the_budget(self):
        detail = create_bundle.tail_lines('cause\n\n\n\n\n', limit=2)
        assert detail == 'cause'


def vendor(**fields) -> catalog.CustomInstaller:
    return catalog.CustomInstaller.from_mapping({'description': 'a tool that ships itself', 'bundle_install_script': True, **fields})


class TestInstallScriptVersions:
    """A script row records the version its script installs, or records nothing.

    It recorded the literal `latest`, which reads back through
    `ghrelease.bundle_version` into a tag comparison — so offline, where the
    bundle *is* the upstream, every one of these rows asserted that `latest` was
    the newest release and then failed to parse it. Unmeasurable dressed as
    measured, which is the one answer `currency_of` exists to refuse.
    """

    def stage(self, tmp_path, monkeypatch, entries, latest=None, uv_version='0.9.7'):
        """Stage the script rows for some entries, and hand back the manifest."""
        staging = tmp_path / 'installers'
        bundle = create_bundle.Bundle(staging, 'linux', 'x86_64')

        monkeypatch.setattr(create_bundle, 'download', lambda url, destination: destination.write_text('#!/bin/sh\n'))
        monkeypatch.setattr(create_bundle, 'fetch_latest_version', lambda repo: (latest or {})[repo])

        items = tuple(planned(entry, 'custom_installers') for entry in entries)
        create_bundle.add_install_scripts(bundle, items, uv_version)
        bundle.write_metadata()

        monkeypatch.setattr(paths, 'BUNDLE_DIR', staging)
        return bundle

    def test_the_version_is_what_the_repo_released_not_the_tag_pinning_the_script(self, tmp_path, monkeypatch):
        """`install_url` pins the *script*, and every one of these scripts then clones
        its repo and moves to the newest tag — so the tool the bundle delivers is
        whatever upstream released, and that is what the row has to say."""
        font = vendor(
            name='font', repo='datapointchris/font', install_url='https://raw.githubusercontent.com/datapointchris/font/v4.0.0/install.sh'
        )
        self.stage(tmp_path, monkeypatch, [font], latest={'datapointchris/font': 'v4.1.0'})

        staged = bundle_manifest.staged('font', 'script')

        assert staged is not None
        assert staged.version == 'v4.1.0'
        assert staged.filename == 'font-install.sh'

    def test_the_provider_reads_the_version_back(self, tmp_path, monkeypatch):
        """The round trip that matters: what the bundler wrote is what an offline run
        compares an installed tool against."""
        theme = vendor(name='theme', repo='datapointchris/theme', install_url='https://example.invalid/theme/install.sh')
        self.stage(tmp_path, monkeypatch, [theme], latest={'datapointchris/theme': 'v6.5.0'})

        assert ghrelease.bundle_version('theme') == 'v6.5.0'

    def test_a_release_tag_prefix_is_stripped_as_it_is_for_a_release_binary(self, tmp_path, monkeypatch):
        """`add_github_releases` records the tag without its prefix, and a script row
        is read back by the same function, so it cannot spell the version differently."""
        cli = vendor(name='cli', repo='owner/monorepo', release_tag_prefix='cli/', install_url='https://example.invalid/cli/install.sh')
        self.stage(tmp_path, monkeypatch, [cli], latest={'owner/monorepo': 'cli/v0.9.0'})

        assert ghrelease.bundle_version('cli') == 'v0.9.0'

    def test_an_entry_naming_no_repo_records_no_version_at_all(self, tmp_path, monkeypatch):
        """claude.ai serves one unversioned script and the entry names no repo, so
        nothing recorded the fact and the field is absent.

        Absent is the honest answer: `bundle_version` reads it as None, and an
        offline row then says the bundle carries no version for this tool instead
        of asserting a release nobody published.
        """
        claude = vendor(name='claude-code', command='claude', install_url='https://claude.ai/install.sh')
        self.stage(tmp_path, monkeypatch, [claude])

        staged = bundle_manifest.staged('claude-code', 'script')

        assert staged is not None
        assert staged.version == ''
        assert ghrelease.bundle_version('claude-code') is None

    def test_the_uv_row_carries_the_uv_the_bundle_staged(self, tmp_path, monkeypatch):
        """astral.sh serves one unversioned script that installs the newest uv, and
        `add_uv` already resolved which one that is. Asking again would let the two
        rows describing one uv disagree."""
        self.stage(tmp_path, monkeypatch, [], uv_version='0.9.7')

        staged = bundle_manifest.staged('uv', 'script')

        assert staged is not None
        assert staged.version == '0.9.7'

    def test_no_row_says_latest(self, tmp_path, monkeypatch):
        """The regression itself. `latest` parses as neither a version nor an absence,
        which is how it survived: `versions.parse` answers None and the row reports a
        tool unmeasurable while claiming to have measured it."""
        entries = [
            vendor(name='font', repo='datapointchris/font', install_url='https://example.invalid/font/install.sh'),
            vendor(name='claude-code', command='claude', install_url='https://claude.ai/install.sh'),
        ]
        bundle = self.stage(tmp_path, monkeypatch, entries, latest={'datapointchris/font': 'v4.1.0'})

        assert [row for row in bundle.entries if 'latest' in row.split('|')] == []

    def test_an_entry_that_does_not_opt_in_stages_nothing(self, tmp_path, monkeypatch):
        """`bundle_install_script` is the opt-in, and an entry without it must not be
        asked for a version either — awscli declares a repo it publishes no release
        for, and resolving one would fail a build over a script nobody staged."""
        awscli = catalog.CustomInstaller.from_mapping({'name': 'awscli', 'repo': 'aws/aws-cli', 'description': 'aws'})
        bundle = self.stage(tmp_path, monkeypatch, [awscli])

        assert [row for row in bundle.entries if row.startswith('script|awscli|')] == []


class TestBundleRoundTrip:
    """What the bundler writes is what the provider reads back.

    Agreeing by convention is not enough: a bundler expanding a `binary_pattern`
    out of a pipe-joined row and recording the *command*, against a
    `cargo-tools.sh` globbing four loose patterns over two candidate names. A
    disagreement is silent — the tool installs from the network instead, which on
    the firewalled machine the bundle exists for means it does not install at all.

    So this asserts the whole loop rather than either half: stage a package the
    way `add_cargo_binaries` does, then ask the provider for it.
    """

    def stage(self, tmp_path, monkeypatch, entry, version='v10.4.2'):
        target = Target(OSFamily.LINUX, Arch.X86_64)
        staging = tmp_path / 'installers'
        bundle = create_bundle.Bundle(staging, 'linux', 'x86_64')

        payload = tmp_path / 'build' / entry.executable
        payload.parent.mkdir(parents=True, exist_ok=True)
        payload.write_bytes(b'#!/bin/sh\necho hi\n')

        def fetch(_cache, _asset, destination, _label):
            with tarfile.open(destination, 'w:gz') as tar:
                tar.add(payload, arcname=payload.name)

        monkeypatch.setattr(create_bundle, 'fetch_latest_version', lambda repo: version)
        monkeypatch.setattr(create_bundle.DownloadCache, 'fetch', fetch)

        items = (planned(entry, 'cargo_packages'),)
        create_bundle.add_cargo_binaries(bundle, create_bundle.DownloadCache(enabled=False), items)
        bundle.write_metadata()

        monkeypatch.setattr(paths, 'BUNDLE_DIR', staging)
        return target

    def test_a_staged_cargo_package_is_found_by_the_provider_that_installs_it(self, tmp_path, monkeypatch):
        entry = catalog.CargoPackage.from_mapping(
            {'name': 'fd-find', 'command': 'fd', 'github_repo': 'sharkdp/fd', 'binary_pattern': 'fd-{version}-{target}.tar.gz'}
        )
        monkeypatch.setenv('HOME', str(tmp_path / 'home'))
        self.stage(tmp_path, monkeypatch, entry)

        result = cargo.install(entry, Target(OSFamily.LINUX, Arch.X86_64), offline=True)

        assert result.ok, result.detail
        assert (tmp_path / 'home' / '.cargo' / 'bin' / 'fd').is_file()

    def test_the_row_is_keyed_on_the_crate_name_the_provider_looks_up(self, tmp_path, monkeypatch):
        """`fd-find` installs `fd`, and the bundler recorded the binary's name while
        the provider asks by the crate's. Keyed on the declaration's own identity,
        both sides ask the same question."""
        entry = catalog.CargoPackage.from_mapping(
            {'name': 'fd-find', 'command': 'fd', 'github_repo': 'sharkdp/fd', 'binary_pattern': 'fd-{version}-{target}.tar.gz'}
        )
        self.stage(tmp_path, monkeypatch, entry)

        staged = bundle_manifest.staged('fd-find', 'cargo')

        assert staged is not None
        assert staged.filename == 'fd-v10.4.2-x86_64-unknown-linux-gnu.tar.gz'
