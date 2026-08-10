"""The Windows tool declaration, and the halves of the install that are filesystem.

Nothing here reaches Windows. What can be tested off a WSL machine is the
declaration itself and everything that is a file copy — which is most of what the
shell script did, and all of what `windows check` does.
"""

from __future__ import annotations

import tarfile

import pytest

from dotfiles import windows
from dotfiles import windows_bundle


class TestDeclaration:
    """A typo here is a broken bundle rather than an error, because a missing .exe
    is only noticed on the machine that cannot reach GitHub to fix it."""

    def test_every_tool_declares_both_ways_of_getting_it(self) -> None:
        """The whole point of one table: a tool reachable by only one channel is
        a machine that installs it online and lacks it offline, or the reverse."""
        for tool in windows.TOOLS:
            assert '/' in tool.repo, tool.name
            assert '.' in tool.winget, tool.name
            assert tool.exe.endswith('.exe'), tool.name

    def test_no_tool_is_declared_twice(self) -> None:
        names = [tool.name for tool in windows.TOOLS]
        assert len(names) == len(set(names))

    def test_no_two_tools_claim_one_binary_or_one_package(self) -> None:
        """Two rows writing one filename means the second silently wins, and the
        tool the first names is absent while the count says everything landed."""
        assert len({tool.exe for tool in windows.TOOLS}) == len(windows.TOOLS)
        assert len({tool.winget for tool in windows.TOOLS}) == len(windows.TOOLS)

    def test_placeholders_are_the_ones_expand_asset_knows(self) -> None:
        """A stray {tag} or {ver} — the vocabulary this file used to have — would
        survive expansion and 404 at download time."""
        for tool in windows.TOOLS:
            assert '{' not in windows_bundle.expand_asset(tool.asset, 'v1.2.3'), tool.name


class TestWhatIsInstalled:
    def test_a_directory_with_none_of_them_reports_every_tool_missing(self, tmp_path) -> None:
        assert windows.installed(tmp_path) == ()
        assert windows.missing(tmp_path) == tuple(tool.name for tool in windows.TOOLS)

    def test_a_tool_is_found_by_the_filename_it_declares(self, tmp_path) -> None:
        """Keyed on `exe` rather than `name` because they differ: ripgrep's binary
        is `rg.exe`, and looking for `ripgrep.exe` would report it missing on a
        machine that has it."""
        (tmp_path / 'rg.exe').write_text('BINARY')

        assert windows.installed(tmp_path) == ('rg',)
        assert 'rg' not in windows.missing(tmp_path)

    def test_a_directory_is_not_a_binary(self, tmp_path) -> None:
        """`is_file`, so a leftover directory named like the exe does not read as
        an install."""
        (tmp_path / 'rg.exe').mkdir()

        assert windows.installed(tmp_path) == ()


class TestInstallingFromABundle:
    def test_a_directory_bundle_is_copied_as_it_stands(self, tmp_path) -> None:
        bundle, into = tmp_path / 'bundle', tmp_path / 'bin'
        bundle.mkdir()
        (bundle / 'rg.exe').write_text('RIPGREP')
        (bundle / 'jq.exe').write_text('JQ')

        unresolved = windows.install_from_bundle(bundle, into)

        assert (into / 'rg.exe').read_text() == 'RIPGREP'
        assert set(unresolved) == {tool.name for tool in windows.TOOLS} - {'rg', 'jq'}

    def test_an_archive_is_extracted_first(self, tmp_path) -> None:
        """The two shapes `windows create` can hand over, so a bundle can be
        inspected before it is installed."""
        staging, into = tmp_path / 'staging', tmp_path / 'bin'
        staging.mkdir()
        (staging / 'fd.exe').write_text('FD')
        archive = tmp_path / 'tools.tar.gz'
        with tarfile.open(archive, 'w:gz') as tar:
            tar.add(staging / 'fd.exe', arcname='fd.exe')

        windows.install_from_bundle(archive, into)

        assert (into / 'fd.exe').read_text() == 'FD'

    def test_a_bundle_carrying_nothing_fails_rather_than_reporting_a_clean_install(self, tmp_path) -> None:
        """An empty directory copies zero files and would otherwise exit as though
        it had done the job, on the one machine that cannot go and get them."""
        empty, into = tmp_path / 'empty', tmp_path / 'bin'
        empty.mkdir()

        with pytest.raises(windows.WindowsError, match='no .exe files'):
            windows.install_from_bundle(empty, into)

    def test_a_bundle_that_is_not_there_says_so(self, tmp_path) -> None:
        with pytest.raises(windows.WindowsError, match='bundle not found'):
            windows.install_from_bundle(tmp_path / 'absent.tar.gz', tmp_path / 'bin')

    def test_a_bundle_newer_than_the_declaration_still_installs_in_full(self, tmp_path) -> None:
        """Every .exe is copied, not only the declared ones — a bundle built from a
        later declaration should not arrive half-installed. What is *reported* is
        still the declared set, since that is what this machine expects."""
        bundle, into = tmp_path / 'bundle', tmp_path / 'bin'
        bundle.mkdir()
        (bundle / 'rg.exe').write_text('RIPGREP')
        (bundle / 'newtool.exe').write_text('LATER')

        unresolved = windows.install_from_bundle(bundle, into)

        assert (into / 'newtool.exe').exists()
        assert 'newtool' not in unresolved


class TestReachingWindows:
    def test_off_wsl_it_says_so_rather_than_inventing_a_path(self, monkeypatch) -> None:
        """`/mnt/c/Users/<someone>` is a guess on a machine with no Windows side,
        and a guess here writes binaries into a directory nothing reads."""
        monkeypatch.setattr(windows, 'under_wsl', lambda: False)

        with pytest.raises(windows.WindowsError, match='not running under WSL'):
            windows.windows_home()

    def test_the_destination_is_the_one_directory_git_bash_puts_on_its_path(self, tmp_path) -> None:
        assert windows.destination(tmp_path) == tmp_path / '.local' / 'bin'
