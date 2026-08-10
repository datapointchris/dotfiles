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


def test_the_networked_reads_are_the_ones_with_no_local_index() -> None:
    """Flathub's available versions live on Flathub and the App Store has no
    offline catalogue. Everything else answers off a local index, which is what
    lets `check` measure them at a prompt and in a pre-commit hook."""
    assert sorted(syspkg.NETWORKED) == ['flatpak', 'mas']
    assert set(syspkg.OUTDATED) > syspkg.NETWORKED
