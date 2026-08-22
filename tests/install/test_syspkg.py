"""Asking a package manager what it has installed and behind, and upgrading it.

The seam is the real binary, shadowed on PATH. What breaks here is never the
logic — it is a manager's output convention, and every one of them has a
different one: `pacman -Qu` reports an empty result as a failure, apt prefaces its
list with two lines that are not packages and spells a name `curl/noble-updates`,
and `mas` answers with numeric ids. A fake that returns tidy lines would assert
nothing about any of that.
"""

from __future__ import annotations

import stat
from pathlib import Path

from dotfiles.providers import syspkg


def executable(directory: Path, name: str, script: str) -> Path:
    """See `_executable` in tests/conftest.py for why this is copied rather than imported."""
    target = directory / name
    target.write_text(script)
    target.chmod(target.stat().st_mode | stat.S_IEXEC)
    return target


def manager(fake_bin: Path, name: str, body: str) -> None:
    """A manager that answers `--version` and then behaves as `body` says.

    The `--version` probe is how `outdated` decides a manager exists at all, so a
    fake without it is a manager that is not installed rather than one that
    answered.
    """
    executable(fake_bin, name, f'#!/bin/sh\n[ "$1" = "--version" ] && exit 0\n{body}\n')


def test_a_current_pacman_answers_nothing_rather_than_refusing(fake_bin: Path) -> None:
    """`pacman -Qu` exits 1 having printed nothing when everything is current —
    the grep convention for an empty result, not an error.

    Reading it as a refusal is what the first version of this did, and it reported
    a fully-current Arch box as unmeasurable rather than converged.
    """
    manager(fake_bin, 'pacman', 'exit 1')

    assert syspkg.outdated('pacman') == frozenset()


def test_a_pacman_that_actually_failed_is_still_a_non_answer(fake_bin: Path) -> None:
    """Only a *silent* non-zero exit is the empty result. One that said something
    is a broken database, and answering "nothing to upgrade" on the strength of an
    error message would report a machine current that nobody measured."""
    manager(fake_bin, 'pacman', 'echo "error: could not open database" >&2\nexit 1')

    assert syspkg.outdated('pacman') is None


def test_pacmans_names_are_taken_from_the_version_lines(fake_bin: Path) -> None:
    manager(fake_bin, 'pacman', 'printf "curl 8.5.0-1 -> 8.6.0-1\\nlinux 6.9-1 -> 6.10-1\\n"')

    assert syspkg.outdated('pacman') == frozenset({'curl', 'linux'})


def test_apts_preamble_is_not_mistaken_for_a_package(fake_bin: Path) -> None:
    """apt prefaces its list with `Listing...` and a warning that its CLI is not
    stable, both on the same stream as the answer — and spells the name
    `curl/noble-updates`."""
    listing = 'WARNING: apt does not have a stable CLI interface.\\nListing...\\ncurl/noble-updates 8.5.0 amd64 [upgradable from: 8.4.0]\\n'
    manager(fake_bin, 'apt', f'printf "{listing}"')

    assert syspkg.outdated('apt') == frozenset({'curl'})


def test_a_managers_progress_on_stderr_is_not_a_package_behind(fake_bin: Path) -> None:
    """`brew outdated --formula --quiet` prints the answer on stdout while brew's
    auto-update writes progress to stderr. Read from the merged transcript, the
    decoration becomes a package name: `2 brew package(s) behind: ollama, ✔︎` on a
    machine that is behind on one.

    apt's preamble above is the same disease. Guarding it line-shape by line-shape
    is the wrong answer; reading the stream that carries the answer is the right
    one.
    """
    manager(fake_bin, 'brew', 'printf "✔︎ Cask copilot-money\\n" >&2\nprintf "ollama\\n"')

    assert syspkg.outdated('brew') == frozenset({'ollama'})


def test_an_app_store_app_is_named_by_the_id_it_is_addressed_by(fake_bin: Path) -> None:
    """`mas outdated` prints `<id> <name> (<old> -> <new>)`, and the id is both
    field one and the only thing `mas install` accepts."""
    manager(fake_bin, 'mas', 'printf "497799835 Xcode (15.0 -> 15.1)\\n"')

    assert syspkg.outdated('mas') == frozenset({'497799835'})


def test_a_manager_that_is_not_installed_answers_nothing_at_all(fake_bin: Path) -> None:
    """None rather than an empty set: "nothing is behind" and "nobody asked" are
    the difference between a converged row and an unmeasurable one."""
    assert syspkg.outdated('brew') is None


def test_every_manager_that_installs_can_also_be_asked_and_upgraded() -> None:
    """Three tables over one set of keys, and a manager missing from one of them
    fails at a different time than the commit that added it: absent from OUTDATED
    it is permanently unmeasurable, absent from UPGRADE it raises KeyError inside
    a repair."""
    assert set(syspkg.OUTDATED) == set(syspkg.INSTALL)
    assert set(syspkg.UPGRADE) == set(syspkg.INSTALL)


def test_every_manager_a_reader_is_told_to_remove_with_can_also_be_removed_with() -> None:
    """`REMOVE` is a sentence to paste and `UNINSTALL` is argv to run, and a manager
    in one and not the other fails at a different time than the commit that added
    it: absent from `UNINSTALL` it raises KeyError inside a repair, absent from
    `REMOVE` it offers a blank command to whoever was refused."""
    assert set(syspkg.UNINSTALL) == set(syspkg.REMOVE)
    assert set(syspkg.UNINSTALL) >= syspkg.REMOVES_AS_ROOT


def test_the_sentence_a_reader_gets_asks_before_it_removes(fake_bin: Path) -> None:
    """The one difference between the two tables, and the reason they are written
    out rather than derived from each other. `--noconfirm` in front of a person is
    a removal they were never shown; its absence in a run nobody is watching is a
    prompt on a closed stdin."""
    assert '--noconfirm' not in syspkg.REMOVE['pacman']
    assert '--noconfirm' in syspkg.UNINSTALL['pacman']


def test_a_removal_runs_the_managers_own_uninstall(fake_bin: Path, unprivileged) -> None:
    """Spied on argv rather than the result, per `standards/testing.md`: what is
    being asserted is the command the engine built, and brew's own answer is about
    the machine the suite happens to run on."""
    log = fake_bin / 'argv'
    executable(fake_bin, 'brew', f'#!/bin/sh\nprintf "%s\\n" "$*" >> {log}\nexit 0\n')

    result = syspkg.uninstall('brew', ['syncthing'], unprivileged)

    assert result.ok, result.detail
    assert log.read_text().splitlines() == ['uninstall syncthing']


def test_the_apt_removal_cannot_take_more_than_the_name_it_was_given(fake_bin: Path) -> None:
    """`apt-get remove -y` resolves reverse dependencies and `-y` answers the
    confirmation that would have shown the list, so one authorised removal takes an
    unbounded set. `dpkg --remove` refuses exactly where `pacman -R` does, which is
    what makes `--force` mean the same thing on both distros."""
    assert syspkg.UNINSTALL['apt'][:2] == ('dpkg', '--remove')
    assert '-y' not in syspkg.UNINSTALL['apt']


def test_a_systemd_package_has_its_unit_stopped_before_it_is_removed(fake_bin: Path, monkeypatch) -> None:
    """Neither `pacman -R` nor `apt-get remove` stops a running daemon, so without
    this the displaced process outlives its own package and holds the ports and the
    state directory the replacement is about to be pointed at."""
    stopped: list[str] = []
    monkeypatch.setattr(syspkg.systemd, 'disable', lambda unit: stopped.append(unit))
    executable(fake_bin, 'systemctl', '#!/bin/sh\nexit 0\n')

    syspkg.stop_service('pacman', 'syncthing', 'syncthing.service')

    assert stopped == ['syncthing.service']


def test_a_homebrew_package_has_its_service_stopped_through_brew(fake_bin: Path) -> None:
    """The label Homebrew generates is its own, so `brew services` is what knows it."""
    log = fake_bin / 'argv'
    executable(fake_bin, 'brew', f'#!/bin/sh\nprintf "%s\\n" "$*" >> {log}\nexit 0\n')

    syspkg.stop_service('brew', 'syncthing', '')

    assert log.read_text().splitlines() == ['services stop syncthing']


def test_a_package_declaring_no_unit_stops_nothing_on_linux(fake_bin: Path, monkeypatch) -> None:
    """Most superseded packages are commands. A blank unit name must not become a
    `systemctl --user disable --now` against the empty string."""
    stopped: list[str] = []
    monkeypatch.setattr(syspkg.systemd, 'disable', lambda unit: stopped.append(unit))
    executable(fake_bin, 'systemctl', '#!/bin/sh\nexit 0\n')

    syspkg.stop_service('pacman', 'ripgrep', '')

    assert stopped == []


def test_a_manager_that_refuses_the_removal_says_so(fake_bin: Path, unprivileged) -> None:
    """A failed removal is what stops the install that was clearing the way for it,
    so it has to come back as a failure rather than as a quiet success."""
    executable(fake_bin, 'brew', '#!/bin/sh\nexit 1\n')

    assert not syspkg.uninstall('brew', ['syncthing'], unprivileged).ok


def test_the_networked_reads_are_the_ones_with_no_local_index() -> None:
    """Flathub's available versions live on Flathub, the App Store has no offline
    catalogue, and `yay -Qu` asks the AUR's RPC about every AUR package.

    `aur` is the one a reader would not predict, because it is spelled like its
    local neighbour and `pacman -Qu` really does answer off the sync database.
    Measured at 41% CPU against `yay -Qu --repo`'s 103%: a process under 100% is
    waiting on something.

    Membership decides only what a run declining the network skips. Every read verb
    measures, so all three are asked on a plain `plan` or `check`.
    """
    assert sorted(syspkg.NETWORKED) == ['aur', 'flatpak', 'mas']
    assert set(syspkg.OUTDATED) > syspkg.NETWORKED
