"""Getting a package manager onto the machine before anything asks it for a package.

The seam is `effects.run` and `shutil.which`, because what each bootstrap decides
is an argv and an environment — whether Homebrew's installer works is Homebrew's
business. What is asserted here is the decision each one makes about *root*, which
is where all three differ and where getting it wrong is silent: `sudo brew` is an
error message, `sudo makepkg` refuses outright, and an escalated install script is
a build running as root that leaves root-owned files behind.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from dotfiles import effects
from dotfiles import github_release
from dotfiles.effects import Completed
from dotfiles.privilege import Privilege
from dotfiles.providers import Kind
from dotfiles.providers import Result
from dotfiles.providers import bootstrap
from dotfiles.providers import syspkg


class World:
    """Every command a bootstrap runs, recorded rather than run."""

    def __init__(self, *, fails: str = '') -> None:
        self.calls: list[tuple[str, ...]] = []
        self._fails = fails

    def __call__(self, command, **kwargs) -> Completed:
        argv = tuple(str(part) for part in command)
        self.calls.append(argv)
        broken = self._fails and self._fails in ' '.join(argv)
        return Completed(argv, 1, 'no') if broken else Completed(argv, 0, '')

    @property
    def argv0(self) -> list[str]:
        return [call[0] for call in self.calls]


@pytest.fixture
def world(monkeypatch):
    def arrange(*, absent: tuple[str, ...] = (), **kwargs) -> World:
        recorder = World(**kwargs)
        monkeypatch.setattr(effects, 'run', recorder)
        monkeypatch.setattr(shutil, 'which', lambda name: None if name in absent else f'/usr/bin/{name}')
        return recorder

    return arrange


# ─────────────────────────────────────────────────────────────────────────────
# Homebrew
# ─────────────────────────────────────────────────────────────────────────────


def test_homebrew_that_is_already_present_costs_nothing(world) -> None:
    """A precondition runs on every batch, so the common case has to be a which."""
    reached = world()

    result = bootstrap.homebrew()

    assert result.ok
    assert result.kind is Kind.UNCHANGED
    assert reached.calls == []


def test_the_homebrew_installer_is_never_escalated(world, monkeypatch) -> None:
    """It creates /opt/homebrew as root and then refuses to continue if it *is*
    root, calling sudo itself for the parts that need it. Handing it an already
    escalated shell is the one way to make it fail."""
    reached = world(absent=('brew',))
    monkeypatch.setattr(effects, 'fetch', lambda url, destination, **kwargs: True)
    monkeypatch.setattr(bootstrap, 'BREW_PREFIXES', (Path('/nowhere'),))

    bootstrap.homebrew()

    assert reached.argv0 == ['bash']
    assert 'sudo' not in [part for call in reached.calls for part in call]


def test_the_installer_runs_non_interactively(world, monkeypatch) -> None:
    """Without it the script blocks on "press RETURN", which on a scheduled or
    containerised install is forever."""
    seen: dict[str, object] = {}

    def record(command, **kwargs):
        seen.update(kwargs)
        return Completed(tuple(command), 0, '')

    world(absent=('brew',))
    monkeypatch.setattr(effects, 'run', record)
    monkeypatch.setattr(effects, 'fetch', lambda url, destination, **kwargs: True)
    monkeypatch.setattr(bootstrap, 'BREW_PREFIXES', (Path('/nowhere'),))

    bootstrap.homebrew()

    assert seen['env'] == {'NONINTERACTIVE': '1'}


def test_an_installer_that_leaves_no_brew_is_a_failure_not_a_success(world, monkeypatch) -> None:
    """Exit 0 is what the script reports; a `brew` on disk is what the next step
    needs, and only the second is worth believing."""
    world(absent=('brew',))
    monkeypatch.setattr(effects, 'fetch', lambda url, destination, **kwargs: True)
    monkeypatch.setattr(bootstrap, 'BREW_PREFIXES', (Path('/nowhere'),))

    result = bootstrap.homebrew()

    assert not result.ok
    assert result.kind is Kind.VERIFY_FAILED


def test_the_new_prefix_is_put_on_path_for_the_rest_of_the_run(world, monkeypatch, tmp_path) -> None:
    """The install that just ran is the one that will be asked for `brew install`
    one line later, in this same process. Nothing has re-read a shell profile
    between them, and `/opt/homebrew/bin` is on no default PATH."""
    prefix = tmp_path / 'opt' / 'homebrew' / 'bin'
    prefix.mkdir(parents=True)
    (prefix / 'brew').write_text('#!/bin/sh\n')
    world(absent=('brew',))
    monkeypatch.setattr(effects, 'fetch', lambda url, destination, **kwargs: True)
    monkeypatch.setattr(bootstrap, 'BREW_PREFIXES', (prefix,))
    monkeypatch.setenv('PATH', '/usr/bin')

    assert bootstrap.homebrew().ok
    assert os.environ['PATH'].split(os.pathsep)[0] == str(prefix)


REFUSED = 'ConnectError: certificate verify failed: unable to get local issuer certificate'


def test_a_download_that_fails_says_where_it_was_looking_and_why(world, monkeypatch) -> None:
    """The first thing that runs on a fresh Mac, so the failure with the least context
    around it — and the one most likely to be read as a dead network when it is a
    proxy certificate."""
    world(absent=('brew',))
    monkeypatch.setattr(effects, 'fetch', lambda url, destination, **kwargs: github_release.Fetched(False, REFUSED))

    result = bootstrap.homebrew()

    assert not result.ok
    assert result.kind is Kind.DOWNLOAD_FAILED
    assert bootstrap.BREW_INSTALLER in result.detail
    assert REFUSED in result.detail


# ─────────────────────────────────────────────────────────────────────────────
# Taps
# ─────────────────────────────────────────────────────────────────────────────


def test_every_declared_tap_is_registered(world) -> None:
    reached = world()

    assert bootstrap.taps(('FelixKratz/formulae', 'nikitabobko/tap')).ok
    assert reached.calls == [('brew', 'tap', 'FelixKratz/formulae'), ('brew', 'tap', 'nikitabobko/tap')]


def test_a_tap_that_fails_stops_the_batch_rather_than_warning(world) -> None:
    """A formula in an unregistered tap is unresolvable, and one unresolvable
    formula aborts a batched `brew install` before it touches anything. Installing
    anyway makes every package in the group fail naming the wrong formula."""
    world(fails='nikitabobko')

    result = bootstrap.taps(('nikitabobko/tap',))

    assert not result.ok
    assert result.kind is Kind.COMMAND_FAILED
    assert 'nikitabobko/tap' in result.detail


# ─────────────────────────────────────────────────────────────────────────────
# The AUR
# ─────────────────────────────────────────────────────────────────────────────


def test_yay_is_built_rather_than_installed(world, monkeypatch, tmp_path) -> None:
    """There is no other way to get an AUR helper: it is itself an AUR package."""
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'data'))
    reached = world(absent=('yay',))

    assert bootstrap.aur().ok
    assert reached.argv0 == ['git', 'makepkg']


def test_makepkg_is_never_escalated(world, monkeypatch, tmp_path) -> None:
    """It refuses to run as root and escalates for the install step itself.
    Running the whole build as root leaves root-owned files in the build cache."""
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'data'))
    reached = world(absent=('yay',))

    bootstrap.aur()

    assert 'sudo' not in [part for call in reached.calls for part in call]


def test_the_gnupg_home_exists_before_makepkg_verifies_anything(world, monkeypatch, tmp_path) -> None:
    """makepkg verifies upstream source signatures, and a missing GNUPGHOME fails
    the verification rather than skipping it. It is XDG here because that is where
    `.zshrc` puts it, and a second keyring under ~/.gnupg is invisible to the shell."""
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'data'))
    world(absent=('yay',))

    bootstrap.aur()

    keyring = tmp_path / 'data' / 'gnupg'
    assert keyring.is_dir()
    assert keyring.stat().st_mode & 0o777 == 0o700


def test_a_machine_that_cannot_build_says_so_rather_than_trying(world, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'data'))
    reached = world(absent=('yay', 'makepkg'))

    result = bootstrap.aur()

    assert not result.ok
    assert result.kind is Kind.PREREQUISITE_MISSING
    assert 'base-devel' in result.detail
    assert reached.calls == []


def test_an_existing_yay_is_left_alone(world, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'data'))
    reached = world()

    assert bootstrap.aur().ok
    assert reached.calls == []


# ─────────────────────────────────────────────────────────────────────────────
# Flathub
# ─────────────────────────────────────────────────────────────────────────────


def test_the_flathub_remote_is_added_before_any_app_names_it(world, monkeypatch) -> None:
    """`flatpak install <id>` with no remote fails naming the app, which reads as
    a missing app rather than a machine nobody pointed at Flathub."""
    reached = world()
    monkeypatch.setattr(bootstrap, 'SYSTEM_BUS', Path('/'))

    assert bootstrap.flathub('pacman', Privilege(offer=False)).ok
    assert reached.calls == [('flatpak', 'remote-add', '--if-not-exists', 'flathub', bootstrap.FLATHUB)]


def test_flatpak_itself_is_installed_through_the_machine_s_own_manager(world, monkeypatch) -> None:
    """It is the manager, so it is not one of its own packages — and a machine that
    subscribes to no flatpak apps should not carry the runtime for them."""
    world(absent=('flatpak',))
    monkeypatch.setattr(bootstrap, 'SYSTEM_BUS', Path('/'))
    asked: list[tuple[str, list[str]]] = []

    def record(manager, names, privilege) -> Result:
        asked.append((manager, list(names)))
        return Result(True, '', kind=Kind.APPLIED)

    monkeypatch.setattr(syspkg, 'install', record)

    assert bootstrap.flathub('pacman', Privilege(offer=False)).ok
    assert asked == [('pacman', ['flatpak'])]


def test_a_machine_with_no_message_bus_declines_rather_than_failing(world, monkeypatch) -> None:
    """flatpak talks to D-Bus, and a container has no bus. The bash asked whether
    it was under test — `DOTFILES_DOCKER_TEST` — which is a harness telling
    production code it is being tested. This asks about the bus, which is the
    actual reason and is equally right off a container."""
    reached = world()
    monkeypatch.setattr(bootstrap, 'SYSTEM_BUS', Path('/nonexistent/dbus/socket'))

    result = bootstrap.flathub('pacman', Privilege(offer=False))

    assert not result.ok
    assert result.kind is Kind.UNSUPPORTED_HERE
    assert reached.calls == []
