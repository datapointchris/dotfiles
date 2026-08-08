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

from dotfiles import create_bundle


class TestPlatform:
    def test_every_supported_platform_splits_into_os_and_arch(self):
        assert create_bundle.parse_platform('linux-x86_64') == ('linux', 'x86_64')
        assert create_bundle.parse_platform('linux-arm64') == ('linux', 'arm64')
        assert create_bundle.parse_platform('darwin-arm64') == ('darwin', 'arm64')
        # The aliases exist because both spellings appear in the wild.
        assert create_bundle.parse_platform('linux-amd64') == create_bundle.parse_platform('linux-x86_64')
        assert create_bundle.parse_platform('macos-arm64') == create_bundle.parse_platform('darwin-arm64')

    def test_an_unknown_platform_names_the_supported_ones(self):
        with pytest.raises(create_bundle.BundleError) as error:
            create_bundle.parse_platform('solaris-sparc')
        assert 'linux-x86_64' in str(error.value)

    def test_the_bundle_name_carries_date_manifest_and_platform(self):
        name = create_bundle.bundle_name('wsl-work-workstation', 'linux', 'x86_64', dt.date(2026, 8, 7))
        assert name == 'dotfiles-offline-v20260807-wsl-work-workstation-linux-x86_64'


class TestCargoTarget:
    def test_defaults_to_the_triple_for_the_platform(self):
        assert create_bundle.cargo_target('linux', 'x86_64') == 'x86_64-unknown-linux-gnu'
        assert create_bundle.cargo_target('darwin', 'arm64') == 'aarch64-apple-darwin'
        assert create_bundle.cargo_target('darwin', 'x86_64') == 'x86_64-apple-darwin'

    def test_an_override_applies_only_to_its_own_platform(self):
        # fnm ships fnm-linux.zip and fnm-macos.zip, named after neither triple.
        assert create_bundle.cargo_target('linux', 'x86_64', 'linux', 'macos') == 'linux'
        assert create_bundle.cargo_target('darwin', 'arm64', 'linux', 'macos') == 'macos'
        # A linux override must not leak into the darwin answer.
        assert create_bundle.cargo_target('darwin', 'arm64', 'x86_64-unknown-linux-musl', '') == 'aarch64-apple-darwin'


class TestPatternExpansion:
    def test_version_placeholders_differ_by_the_leading_v(self):
        assert create_bundle.expand_pattern('tool-{version}.tar.gz', 'v1.2.3', 'linux', 'x86_64') == 'tool-v1.2.3.tar.gz'
        assert create_bundle.expand_pattern('tool-{version_num}.tar.gz', 'v1.2.3', 'linux', 'x86_64') == 'tool-1.2.3.tar.gz'

    def test_architecture_spellings_cover_every_upstream_convention(self):
        # Go releases name the architecture amd64 where the kernel says x86_64.
        assert create_bundle.expand_pattern('{os}_{go_arch}', 'v1', 'linux', 'x86_64') == 'linux_amd64'
        assert create_bundle.expand_pattern('{os}_{go_arch}', 'v1', 'darwin', 'arm64') == 'darwin_arm64'
        # Capitalised kernel names (gum, lazydocker).
        assert create_bundle.expand_pattern('{Os}_{Arch}', 'v1', 'linux', 'x86_64') == 'Linux_x86_64'
        # The product name for Apple rather than the kernel name (jira-cli).
        assert create_bundle.expand_pattern('{os_mac}', 'v1', 'darwin', 'arm64') == 'macOS'
        assert create_bundle.expand_pattern('{Os_mac}', 'v1', 'linux', 'x86_64') == 'Linux'

    def test_the_rust_target_triple_is_substituted_whole(self):
        expanded = create_bundle.expand_pattern('rg-{version}-{target}.tar.gz', 'v14.1.0', 'linux', 'x86_64', 'x86_64-unknown-linux-musl')
        assert expanded == 'rg-v14.1.0-x86_64-unknown-linux-musl.tar.gz'


class TestCachePath:
    def test_the_url_path_is_mirrored_so_entries_are_inspectable(self):
        path = create_bundle.cache_path_for_url('https://github.com/sharkdp/fd/releases/download/v10.2.0/fd.tar.gz')
        assert path.parts[-4:] == ('sharkdp', 'fd', 'releases', 'download') or 'sharkdp' in str(path)
        assert str(path).startswith(str(create_bundle.CACHE_ROOT))
        assert path.name == 'fd.tar.gz'

    def test_a_traversal_cannot_escape_the_cache_root(self):
        path = create_bundle.cache_path_for_url('https://evil.example/../../../etc/passwd')
        assert '..' not in path.parts
        assert str(path).startswith(str(create_bundle.CACHE_ROOT))

    def test_characters_outside_the_portable_set_become_underscores(self):
        path = create_bundle.cache_path_for_url('https://example.com/a b;rm -rf/x.tar.gz')
        assert ' ' not in str(path)
        assert ';' not in str(path)

    def test_the_version_in_the_url_is_what_makes_an_entry_miss(self):
        # The cache has no staleness check; a new release changes the key.
        old = create_bundle.cache_path_for_url('https://github.com/o/r/releases/download/v1.0.0/tool.tar.gz')
        new = create_bundle.cache_path_for_url('https://github.com/o/r/releases/download/v1.1.0/tool.tar.gz')
        assert old != new


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
