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

    def test_linux_is_not_assumed_to_be_x86(self):
        """It was, and a linux-arm64 bundle therefore carried x86_64 cargo binaries —
        an archive that builds cleanly and installs a machine that cannot run them."""
        assert create_bundle.cargo_target('linux', 'arm64') == 'aarch64-unknown-linux-gnu'
        assert create_bundle.rust_triple('linux', 'arm64') == 'aarch64-unknown-linux-gnu'

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
