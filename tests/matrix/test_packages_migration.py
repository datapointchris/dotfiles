"""Moving a tool off the package manager that owns it, through the verbs.

The declaration says `github_releases` and Homebrew owns the binary. `check` has
to say so, `apply` has to refuse, and `apply --force` has to be the one thing that
moves the machine — because installing the release beside a package that ships its
own service leaves two daemons over one config directory and one port.

Every row here starts from that state and nothing removes anything, which the fake
brew's argv log is what proves. The forced run itself is not here: it resolves a
tag before it removes anything, and a matrix row that reached GitHub would be
measuring the network.

The behaviour under `perform` is `tests/resources/test_packages.py` — including the
ordering, which is where a failed fetch is shown to leave the package installed.
The blocker and its advice are `tests/resources/test_superseded_packages.py`. What
is here is what a person typing the verb sees.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.vocabulary import ExitCode
from matrix.harness import Invocation
from matrix.harness import Sandbox

RELEASE = {'name': 'syncthing', 'repo': 'syncthing/syncthing', 'supersedes': ['syncthing'], 'reports_version': False}
DECLARATION = {'github_releases': [RELEASE]}
MANIFEST = {'machine': 'box', 'platform': 'linux', 'github_releases': ['syncthing']}

BREW_HOLDING_SYNCTHING = (
    '#!/bin/sh\n'
    'printf "%s\\n" "$*" >> "$HOME/brew-argv"\n'
    '[ "$1" = list ] || exit 1\n'
    'case "$2" in --formula) printf \'syncthing\\n\' ;; esac\n'
)
"""A Homebrew holding syncthing as a formula, refusing everything else, and
recording every argv it was handed.

Answering both lists would report one installed package as two, under whichever
was asked first — `standards/testing.md` § "A fake enforces the service's
constraints". The log is how a row asserts that a removal did *not* happen, which
a refusing uninstall cannot say: an exit 1 looks the same whether the run reached
it or stopped before it. `reports_version: false` covers the route to GitHub that
the version check would otherwise take, for the reason `test_packages_selection`'s
fixture gives.
"""


@pytest.fixture(autouse=True)
def brew_owns_syncthing(sandbox: Sandbox) -> Sandbox:
    """The machine 559 describes: the declaration names a release, and the binary on
    it belongs to Homebrew."""
    sandbox.declare(packages=DECLARATION, manifest=MANIFEST)
    sandbox.shadow('brew', BREW_HOLDING_SYNCTHING)
    sandbox.elsewhere('syncthing')
    return sandbox


def finding(ran: Invocation) -> dict:
    """The one row this machine's packages resource reported, from either list.

    Both, because which of them a row lands in is the thing under test one row
    down: `sift` puts what `apply` will act on in `findings` and what needs a person
    in `others`, and a helper that read one of them would decide the answer before
    the assertion did.
    """
    resource = next(entry for entry in ran.document['resources'] if entry['address'] == 'packages')
    rows = [*resource['findings'], *resource['others']]
    assert len(rows) == 1, rows
    return rows[0]


def test_a_release_another_manager_owns_is_reported_as_missing(cli: Callable[..., Invocation]) -> None:
    """The measurement 559 is about. A `syncthing` on PATH at the right version was
    reading as the declaration satisfied, so `plan` had nothing to say about an
    entry no part of this repo had ever installed."""
    found = finding(cli('packages', 'check', '--json'))

    assert found['verdict'] == Verdict.MISSING


def test_apply_refuses_it_rather_than_installing_beside_the_package(cli: Callable[..., Invocation]) -> None:
    """`BY_HAND` is what keeps `apply` off it, and what puts the row in the list
    `plan` does not promise anything about. Two copies of one daemon is worse than
    either state alone, so the refusal is the safe default."""
    ran = cli('packages', 'plan', '--json')
    resource = next(entry for entry in ran.document['resources'] if entry['address'] == 'packages')

    assert finding(ran)['repair'] == Repair.BY_HAND
    assert resource['findings'] == [], 'plan promised an install that apply will not attempt'


def test_the_row_names_the_package_and_both_ways_out(cli: Callable[..., Invocation]) -> None:
    """A reader gets the removal to paste and the apply that does it for them.
    `standards/help.md` § "An error is the help screen for the failure in hand"."""
    advice = finding(cli('packages', 'check', '--json'))['advice']

    assert 'brew uninstall syncthing' in advice
    assert 'dotfiles packages apply --package syncthing --force' in advice


def test_a_blocked_release_is_something_check_reports(cli: Callable[..., Invocation]) -> None:
    """`check` is what runs unattended, and a machine that cannot install what it
    declares is exactly what it exists to say. `plan` promises nothing, because
    `apply` will not act on it."""
    assert cli('packages', 'check').exit_code == ExitCode.ISSUE
    assert cli('packages', 'plan').exit_code == ExitCode.CONVERGED


def test_apply_leaves_the_machine_alone_and_does_not_fail(cli: Callable[..., Invocation], sandbox: Sandbox) -> None:
    """Declining is not failing. `apply` reports the row and exits clean, because
    the work it is refusing is work this machine was never able to do unattended."""
    ran = cli('packages', 'apply')

    assert ran.exit_code == ExitCode.CONVERGED
    assert not (sandbox.user_bin / 'syncthing').exists()


def test_an_unforced_apply_asks_brew_nothing_but_its_inventory(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Declining is not a quiet removal. `apply` reads the formula list to decide the
    row and stops there, so the only argv brew is handed is the read."""
    cli('packages', 'apply')

    assert 'uninstall' not in (sandbox.home / 'brew-argv').read_text()
