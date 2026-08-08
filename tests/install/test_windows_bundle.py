"""Tests for windows_bundle.py

The bundle is built on a machine with a network and installed on one without,
so a wrong asset name or a binary that never made it into the archive is only
discovered on the machine that cannot fix it.

Run with: pytest tests/install/test_windows_bundle.py
"""

import zipfile

import pytest

from dotfiles import windows_bundle


class TestAssetNames:
    def test_the_two_placeholders_differ_by_the_leading_v(self):
        assert windows_bundle.expand_asset('bat-{version}-msvc.zip', 'v0.26.1') == 'bat-v0.26.1-msvc.zip'
        assert windows_bundle.expand_asset('zoxide-{version_num}-msvc.zip', 'v0.26.1') == 'zoxide-0.26.1-msvc.zip'

    def test_a_tag_with_a_prefix_still_yields_the_number(self):
        # jq tags releases jq-1.8.2, not v1.8.2.
        assert windows_bundle.version_num('jq-1.8.2') == '1.8.2'
        assert windows_bundle.version_num('v0.10.0') == '0.10.0'
        assert windows_bundle.version_num('15.2.0') == '15.2.0'

    def test_a_pattern_with_no_placeholder_is_left_alone(self):
        # eza and jq publish a Windows asset whose name never changes.
        assert windows_bundle.expand_asset('jq-windows-amd64.exe', 'jq-1.8.2') == 'jq-windows-amd64.exe'


class TestToolSpecs:
    """The specs are data, and a typo in one is a broken bundle rather than an
    error, because a missing .exe is only noticed on the target machine.
    """

    def test_every_tool_declares_what_the_build_needs(self):
        for tool in windows_bundle.WINDOWS_TOOLS:
            assert set(tool) == {'name', 'repo', 'asset', 'exe'}
            assert '/' in tool['repo']
            assert tool['exe'].endswith('.exe')

    def test_no_tool_is_declared_twice(self):
        names = [tool['name'] for tool in windows_bundle.WINDOWS_TOOLS]
        assert len(names) == len(set(names))

    def test_placeholders_are_the_ones_expand_asset_knows(self):
        # A stray {tag} or {ver} — the vocabulary this file used to have — would
        # survive expansion and 404 at download time.
        for tool in windows_bundle.WINDOWS_TOOLS:
            expanded = windows_bundle.expand_asset(tool['asset'], 'v1.2.3')
            assert '{' not in expanded, tool['name']


class TestExtraction:
    def test_a_binary_at_the_archive_root_is_found(self, tmp_path):
        archive = tmp_path / 'tool.zip'
        with zipfile.ZipFile(archive, 'w') as zip_file:
            zip_file.writestr('rg.exe', 'BINARY')

        windows_bundle.extract_exe(archive, 'rg.exe', tmp_path / 'rg.exe')
        assert (tmp_path / 'rg.exe').read_text() == 'BINARY'

    def test_a_binary_under_a_versioned_directory_is_found(self, tmp_path):
        # ripgrep and fd nest theirs; fzf does not. Searching covers both.
        archive = tmp_path / 'tool.zip'
        with zipfile.ZipFile(archive, 'w') as zip_file:
            zip_file.writestr('ripgrep-15.2.0-x86_64-pc-windows-msvc/rg.exe', 'NESTED')
            zip_file.writestr('ripgrep-15.2.0-x86_64-pc-windows-msvc/README.md', 'docs')

        windows_bundle.extract_exe(archive, 'rg.exe', tmp_path / 'rg.exe')
        assert (tmp_path / 'rg.exe').read_text() == 'NESTED'

    def test_an_archive_without_the_binary_fails_rather_than_bundling_nothing(self, tmp_path):
        archive = tmp_path / 'tool.zip'
        with zipfile.ZipFile(archive, 'w') as zip_file:
            zip_file.writestr('README.md', 'docs')

        with pytest.raises(windows_bundle.BundleError, match='rg.exe not found'):
            windows_bundle.extract_exe(archive, 'rg.exe', tmp_path / 'rg.exe')
