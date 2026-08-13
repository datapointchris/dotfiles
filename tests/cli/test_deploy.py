"""The one write deployment makes into `$HOME` that this repo does not own.

Every other path the deploy touches is a symlink the manager can recreate from
the checkout. `~/.config/git/config` is the exception — a real file, deliberately
not in the repo — which is why the rule that it must never be written *through* a
link is worth pinning rather than leaving to the next reader to rediscover.

Git picks that path for `git config --global` only while `~/.gitconfig` is absent,
so retiring the latter is part of the same contract and is pinned here beside it.
"""

from __future__ import annotations

import dataclasses as dc
from pathlib import Path

import pytest

from dotfiles import coordinates as axes
from dotfiles import deploy

IDENTITY = '[user]\n\temail = someone@example.com\n'

NONFLEET = axes.Coordinates(
    package_manager=axes.PackageManager.APT,
    os_family=axes.OSFamily.LINUX,
    display_stack=axes.DisplayStack.NONE,
    host=axes.Host.WSL,
    network_trust=axes.NetworkTrust.NONFLEET,
    capacity=axes.Capacity.WORKSTATION,
)
"""Off the fleet, where an identity in ~/.gitconfig is the only copy there is.
The rescue advice differs by trust, so the coordinate is what these exercise."""


@pytest.fixture
def entry_point(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Both constants resolve `Path.home()` at import, so redirect them."""
    path = tmp_path / '.config' / 'git' / 'config'
    monkeypatch.setattr(deploy, 'GIT_CONFIG_ENTRY', path)
    monkeypatch.setattr(deploy, 'HOME_GITCONFIG', tmp_path / '.gitconfig')
    return path


@pytest.fixture
def home_gitconfig(entry_point: Path) -> Path:
    return deploy.HOME_GITCONFIG


def test_absent_entry_point_is_created(entry_point: Path) -> None:
    """Including its parent, which on a fresh machine does not exist yet."""
    deploy._ensure_git_config_entry(NONFLEET)
    assert entry_point.read_text() == deploy.GIT_CONFIG_STUB


def test_an_existing_entry_point_is_left_alone(entry_point: Path) -> None:
    """The stub carries no [user], so overwriting one would drop an identity."""
    entry_point.parent.mkdir(parents=True)
    entry_point.write_text(IDENTITY)

    deploy._ensure_git_config_entry(NONFLEET)

    assert 'someone@example.com' in entry_point.read_text()


def test_a_linked_entry_point_is_replaced_rather_than_written_through(entry_point: Path, tmp_path: Path) -> None:
    """The regression this whole file exists for.

    The entry point is a real file rather than a symlink into the checkout. `git
    config --global` follows a link when writing, so with one there the first
    person to follow git's own "Please tell me who you are" hint commits an
    identity into the repo.
    """
    repo_file = tmp_path / 'configs' / 'common' / '.config' / 'git' / 'common.gitconfig'
    repo_file.parent.mkdir(parents=True)
    repo_file.write_text('# shared\n')
    entry_point.parent.mkdir(parents=True)
    entry_point.symlink_to(repo_file)

    deploy._ensure_git_config_entry(NONFLEET)

    assert not entry_point.is_symlink()
    assert entry_point.read_text() == deploy.GIT_CONFIG_STUB
    assert repo_file.read_text() == '# shared\n'


def test_home_gitconfig_carrying_no_identity_is_removed(entry_point: Path, home_gitconfig: Path) -> None:
    """The placeholder this used to write. While it exists git prefers it for both
    reads and writes, so it silently out-ranks the entire include chain."""
    home_gitconfig.write_text('# placeholder, no [user]\n')

    deploy._ensure_git_config_entry(NONFLEET)

    assert not home_gitconfig.exists()


def test_home_gitconfig_holding_an_identity_is_kept(entry_point: Path, home_gitconfig: Path) -> None:
    """On the nonfleet machine it is the only copy of an address the repo does not
    hold, so this reports and leaves it rather than destroying a value while
    tidying up after itself."""
    home_gitconfig.write_text(IDENTITY)

    deploy._ensure_git_config_entry(NONFLEET)

    assert 'someone@example.com' in home_gitconfig.read_text()


def test_a_dangling_home_gitconfig_link_is_removed(entry_point: Path, home_gitconfig: Path, tmp_path: Path) -> None:
    """`exists()` follows a link, so a dangling one reads as absent while still
    being the path git writes through."""
    home_gitconfig.symlink_to(tmp_path / 'configs' / 'archlinux' / '.gitconfig')

    deploy._ensure_git_config_entry(NONFLEET)

    assert not home_gitconfig.is_symlink()


def test_a_linked_home_gitconfig_holding_an_identity_is_kept(entry_point: Path, home_gitconfig: Path, tmp_path: Path) -> None:
    """Pointing it at a private synced file is a deliberate act, and the identity
    behind the link is as irreplaceable as one written directly into it."""
    elsewhere = tmp_path / 'private' / 'gitconfig'
    elsewhere.parent.mkdir()
    elsewhere.write_text(IDENTITY)
    home_gitconfig.symlink_to(elsewhere)

    deploy._ensure_git_config_entry(NONFLEET)

    assert home_gitconfig.is_symlink()
    assert 'someone@example.com' in elsewhere.read_text()


FLEET = dc.replace(NONFLEET, network_trust=axes.NetworkTrust.FLEET, host=axes.Host.NATIVE)


def test_a_fleet_machine_is_told_to_delete_rather_than_to_rescue(
    entry_point: Path, home_gitconfig: Path, capsys: pytest.CaptureFixture
) -> None:
    """The repo already ships that address in personal.gitconfig, so there is
    nothing to preserve. Naming a rescue file here sent one Mac looking for a
    destination its trust variant never includes."""
    home_gitconfig.write_text(IDENTITY)

    deploy._ensure_git_config_entry(FLEET)

    advice = capsys.readouterr()
    assert 'personal.gitconfig' in advice.out + advice.err
    assert 'local.gitconfig' not in advice.out + advice.err
    assert home_gitconfig.exists()


def test_off_the_fleet_it_is_told_where_to_move_it(entry_point: Path, home_gitconfig: Path, capsys: pytest.CaptureFixture) -> None:
    """There the identity is the only copy of an address the repo deliberately
    does not hold, so it needs somewhere to go before ~/.gitconfig is deleted."""
    home_gitconfig.write_text(IDENTITY)

    deploy._ensure_git_config_entry(NONFLEET)

    advice = capsys.readouterr()
    assert 'local.gitconfig' in advice.out + advice.err
