"""The winget declaration, and the half of the install that is filesystem.

Nothing here reaches Windows. What can be tested off a Windows box is the
declaration itself and the copy out of winget's package directory — which is the
step winget does not do, and therefore the step that decides whether a row
installed at all.
"""

from __future__ import annotations

import re
import stat
from pathlib import Path

import pytest

from dotfiles import catalog
from dotfiles import providers
from dotfiles.providers import Kind
from dotfiles.providers import winget


@pytest.fixture
def staged(tmp_path, monkeypatch) -> Path:
    """An offline bundle with the winget directory present and empty.

    Present rather than absent, because the two answer differently and only one of
    them is the interesting case: a machine with no bundle at all is already
    covered by every other provider's tests, while a bundle that was built and
    carries nothing for this row is the broken bundle `providers.Result.refused`
    says must read as a failure.
    """
    root = tmp_path / 'staged'
    directory = root / 'dotfiles-offline-v20260814T190203Z-box-linux-x86_64'
    (directory / winget.BUNDLE_BINARIES).mkdir(parents=True)
    (directory / providers.MANIFEST).write_text('')
    monkeypatch.setenv('DOTFILES_BUNDLE', str(root))
    return directory


@pytest.fixture(scope='module')
def tools() -> tuple[catalog.WingetPackage, ...]:
    """Every winget row, narrowed to the type that carries `winget`, `asset` and
    `filename` — none of which is reachable through `Entry`."""
    section = catalog.load().section(catalog.WingetPackage.section)
    return tuple(entry for entry in section if isinstance(entry, catalog.WingetPackage))


def named(tools: tuple[catalog.WingetPackage, ...], name: str) -> catalog.WingetPackage:
    return next(tool for tool in tools if tool.name == name)


class TestDeclaration:
    """A typo here is a broken bundle rather than an error, because a missing .exe
    is only noticed on the machine that cannot reach GitHub to fix it."""

    def test_every_tool_declares_both_ways_of_getting_it(self, tools) -> None:
        """The whole point of one row: a tool reachable by only one channel is a
        machine that installs it online and lacks it offline, or the reverse."""
        for tool in tools:
            assert '/' in tool.repo, tool.name
            assert '.' in tool.winget, tool.name
            assert tool.asset, tool.name

    def test_no_two_tools_claim_one_binary_or_one_package(self, tools) -> None:
        """Two rows writing one filename means the second silently wins, and the
        tool the first names is absent while the count says everything landed."""
        assert len({tool.filename for tool in tools}) == len(tools)
        assert len({tool.winget for tool in tools}) == len(tools)

    def test_the_asset_uses_only_the_two_placeholders_the_repo_spells(self, tools) -> None:
        """`{version}` and `{version_num}` are the whole vocabulary, and a stray
        `{tag}` or `{ver}` would reach a download URL literally and 404.

        Asserted on the string as well as through the expander, because a third
        placeholder would survive `stage` untouched and reach a download URL
        literally rather than raising anywhere.
        """
        for tool in tools:
            unknown = set(re.findall(r'\{([^}]*)\}', tool.asset)) - {'version', 'version_num'}
            assert not unknown, f'{tool.name}: {sorted(unknown)}'
            assert '{' not in winget.stage(tool, 'v1.2.3'), tool.name

    def test_the_asset_is_a_zip_or_an_exe_and_never_a_third_shape(self, tools) -> None:
        """`create_bundle.add_winget_binaries` unpacks the first and copies the
        second, so those two are the whole vocabulary. A row declaring a `.tar.gz`
        or a `.7z` is caught here rather than by the bundler, which is the earlier
        of the two and the one that does not need a network to fail.
        """
        for tool in tools:
            assert tool.asset.endswith(('.zip', '.exe')), f'{tool.name}: {tool.asset}'

    def test_the_filename_is_the_command_and_never_the_row_name(self, tools) -> None:
        """The three that differ are the reason `command` is declared at all:
        ripgrep ships rg.exe, and a bundle keyed on the row name carries nothing
        the machine looks for."""
        assert named(tools, 'ripgrep').filename == 'rg.exe'
        assert named(tools, 'fd-find').filename == 'fd.exe'
        assert named(tools, 'git-delta').filename == 'delta.exe'


class TestCopyingAWingetBinary:
    """The function that decides whether a row installed.

    Pure filesystem given a home and a destination, so both of its branches are
    testable with no Windows anywhere — which is worth doing precisely because the
    path around it is the one nothing off a Windows box can exercise.
    """

    @staticmethod
    def _package(home: Path, tool: catalog.WingetPackage, *, nested: bool = False) -> Path:
        """Lay out a winget package the way winget does: a version-stamped
        directory whose name starts with the package id."""
        package = home / winget.PACKAGES / f'{tool.winget}_Microsoft.Winget.Source_8wekyb3d8bbwe'
        location = package / 'inner-1.2.3' if nested else package
        location.mkdir(parents=True)
        (location / tool.filename).write_text('BINARY')
        return package

    def test_a_binary_at_the_package_root_is_found(self, tmp_path, tools) -> None:
        home, into = tmp_path / 'home', tmp_path / 'bin'
        self._package(home, named(tools, 'jq'))

        assert winget.copy_installed(home, into, named(tools, 'jq')) is True
        assert (into / 'jq.exe').read_text() == 'BINARY'

    def test_a_binary_nested_under_the_package_is_found(self, tmp_path, tools) -> None:
        """Some packages put the exe a level down, which is why the search
        recurses rather than only looking at the package root."""
        home, into = tmp_path / 'home', tmp_path / 'bin'
        self._package(home, named(tools, 'ripgrep'), nested=True)

        assert winget.copy_installed(home, into, named(tools, 'ripgrep')) is True
        assert (into / 'rg.exe').read_text() == 'BINARY'

    def test_the_package_is_matched_by_prefix_because_its_name_carries_a_version(self, tmp_path, tools) -> None:
        """An exact-name lookup finds nothing, since winget stamps the directory
        with a version and a source suffix that no declaration knows."""
        home, into = tmp_path / 'home', tmp_path / 'bin'
        tool = named(tools, 'fd-find')
        package = self._package(home, tool)

        assert package.name != tool.winget
        assert package.name.startswith(tool.winget)
        assert winget.copy_installed(home, into, tool) is True

    def test_a_package_that_installed_nothing_reports_false(self, tmp_path, tools) -> None:
        """winget exits non-zero for "already at latest version", so its status is
        ignored and this is what actually decides the outcome — an empty package
        directory has to read as unresolved rather than as a copy."""
        home, into = tmp_path / 'home', tmp_path / 'bin'
        tool = named(tools, 'bat')
        (home / winget.PACKAGES / f'{tool.winget}_x').mkdir(parents=True)

        assert winget.copy_installed(home, into, tool) is False
        assert not (into / 'bat.exe').exists()

    def test_no_winget_directory_at_all_reports_false(self, tmp_path, tools) -> None:
        assert winget.copy_installed(tmp_path / 'home', tmp_path / 'bin', tools[0]) is False

    def test_one_tool_does_not_pick_up_another_tools_binary(self, tmp_path, tools) -> None:
        """The glob is per package id, so a machine with only `fd` installed must
        still report `fzf` unresolved rather than copying whatever it finds."""
        home, into = tmp_path / 'home', tmp_path / 'bin'
        self._package(home, named(tools, 'fd-find'))

        assert winget.copy_installed(home, into, named(tools, 'fzf')) is False


class TestNamingTheAsset:
    """What the bundler downloads, decided here so the two sides cannot disagree."""

    def test_a_tag_with_a_prefix_still_yields_the_bare_number(self) -> None:
        """jq tags `jq-1.7.1`, which `lstrip('v')` leaves whole. `{version_num}` is
        declared as the tag from its first digit on, and this is the row that shows
        the two rules are not the same rule."""
        assert winget.version_num('jq-1.7.1') == '1.7.1'
        assert winget.version_num('v0.9.8') == '0.9.8'
        assert winget.version_num('0.9.8') == '0.9.8'

    def test_a_tag_with_no_digit_at_all_is_passed_through(self) -> None:
        """A release nobody numbered is not a reason to raise here: the download
        that follows names the asset it could not build and says so."""
        assert winget.version_num('nightly') == 'nightly'

    def test_both_placeholders_expand_from_one_tag(self, tools) -> None:
        assert winget.stage(named(tools, 'ripgrep'), 'v14.1.1') == 'ripgrep-v14.1.1-x86_64-pc-windows-msvc.zip'
        assert winget.stage(named(tools, 'fzf'), 'v0.65.0') == 'fzf-0.65.0-windows_amd64.zip'

    def test_an_asset_naming_no_placeholder_is_unchanged(self, tools) -> None:
        assert winget.stage(named(tools, 'jq'), 'jq-1.7.1') == 'jq-windows-amd64.exe'


class TestInstalling:
    def test_an_offline_run_installs_the_staged_executable(self, tmp_path, tools, staged) -> None:
        """The route this machine actually has. The employer network blocks the
        Store outright, so the bundle is not a fallback here — it is the mechanism."""
        tool = named(tools, 'ripgrep')
        (staged / winget.BUNDLE_BINARIES / tool.filename).write_text('RIPGREP')

        result = winget.install(tool, tmp_path / 'bin', offline=True)

        assert result.ok, result.detail
        assert (tmp_path / 'bin' / 'rg.exe').read_text() == 'RIPGREP'

    def test_an_offline_run_with_nothing_staged_fails_rather_than_refusing(self, tmp_path, tools, staged) -> None:
        """A refusal says the machine is working as designed. The bundler stages
        this category now, so a bundle without it is a broken bundle — which is the
        line `providers.Result.refused` draws."""
        result = winget.install(tools[0], tmp_path / 'bin', offline=True)

        assert not result.ok
        assert result.kind is Kind.NOT_IN_BUNDLE
        assert result.refused is False
        assert 'carries no jq.exe' in result.detail

    def test_no_winget_on_path_falls_back_to_the_bundle(self, tmp_path, tools, staged, monkeypatch) -> None:
        """Reaching a network is not reaching the Store, and on this box it never
        is. Without the fallback every row stays uninstalled while a current bundle
        sits staged on disk."""
        monkeypatch.setattr(winget, 'client', lambda: '')
        tool = named(tools, 'bat')
        (staged / winget.BUNDLE_BINARIES / tool.filename).write_text('BAT')

        result = winget.install(tool, tmp_path / 'bin', offline=False)

        assert result.ok, result.detail
        assert (tmp_path / 'bin' / 'bat.exe').read_text() == 'BAT'

    def test_no_winget_and_no_bundle_names_both(self, tmp_path, tools, staged, monkeypatch) -> None:
        """One message, because either alone would send a reader to fix the half
        that was never going to work on this machine."""
        monkeypatch.setattr(winget, 'client', lambda: '')

        result = winget.install(tools[0], tmp_path / 'bin', offline=False)

        assert not result.ok
        assert result.kind is Kind.NOT_IN_BUNDLE
        assert 'winget is not on PATH' in result.detail
        assert 'carries no jq.exe' in result.detail

    def test_a_client_that_installs_nothing_is_reported_unresolved(self, tmp_path, tools, staged, monkeypatch) -> None:
        """The install's own exit code is ignored in both directions, so a client
        exiting 0 having placed no binary must not read as converged."""
        client = tmp_path / 'winget'
        client.write_text('#!/bin/sh\nexit 0\n')
        client.chmod(client.stat().st_mode | stat.S_IXUSR)
        monkeypatch.setenv('HOME', str(tmp_path / 'home'))
        monkeypatch.setattr(winget, 'client', lambda: str(client))

        result = winget.install(named(tools, 'eza'), tmp_path / 'bin', offline=False)

        assert not result.ok
        assert result.kind is Kind.VERIFY_FAILED

    def test_a_client_that_installs_nothing_still_takes_the_bundle(self, tmp_path, tools, staged, monkeypatch) -> None:
        """The Store resolving a package it then cannot place is the same outcome
        for this machine as not reaching the Store at all."""
        client = tmp_path / 'winget'
        client.write_text('#!/bin/sh\nexit 0\n')
        client.chmod(client.stat().st_mode | stat.S_IXUSR)
        monkeypatch.setenv('HOME', str(tmp_path / 'home'))
        monkeypatch.setattr(winget, 'client', lambda: str(client))
        (staged / winget.BUNDLE_BINARIES / 'eza.exe').write_text('EZA')

        result = winget.install(named(tools, 'eza'), tmp_path / 'bin', offline=False)

        assert result.ok, result.detail
        assert (tmp_path / 'bin' / 'eza.exe').read_text() == 'EZA'

    def test_a_client_that_unpacks_a_package_puts_the_binary_on_path(self, tmp_path, tools, staged, monkeypatch) -> None:
        home = tmp_path / 'home'
        tool = named(tools, 'ripgrep')
        package = home / winget.PACKAGES / f'{tool.winget}_v14'
        client = tmp_path / 'winget'
        client.write_text(f'#!/bin/sh\nmkdir -p "{package}"\nprintf RIPGREP > "{package}/{tool.filename}"\nexit 1\n')
        client.chmod(client.stat().st_mode | stat.S_IXUSR)
        monkeypatch.setenv('HOME', str(home))
        monkeypatch.setattr(winget, 'client', lambda: str(client))

        result = winget.install(tool, tmp_path / 'bin', offline=False)

        assert result.ok, result.detail
        assert (tmp_path / 'bin' / 'rg.exe').read_text() == 'RIPGREP'
