"""Every shell script finds the checkout the same way.

`CLAUDE.md` states the idiom; this is what holds it. Two failures it rules out.
A bare `$(git rev-parse --show-toplevel)` with no `${DOTFILES_DIR:-...}` around
it resolves to whatever repo the caller happens to be standing in — the
`dotfiles` CLI runs from any directory, and it exports `DOTFILES_DIR` precisely
so the scripts it calls do not have to guess. And relative navigation
(`$(cd "$(dirname ...)/../.." && pwd)`) re-encodes the script's depth in the
tree at every call site, so moving one file breaks a path that still parses.

Globbed over the tracked scripts rather than listed, so a new installer is
covered by existing.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
from shells import REPO

ASSIGNMENT = re.compile(r'^\s*DOTFILES_DIR=(.*)$', re.MULTILINE)

IDIOM = re.compile(r'^"\$\{DOTFILES_DIR:-\$\(git .*rev-parse --show-toplevel\)\}"$')

RELATIVE_NAVIGATION = re.compile(r'cd\s+"\$\(dirname[^)]*\)/\.\.')

FRONT_DOORS = {'install.sh', 'update.sh'}
"""The two that *export* DOTFILES_DIR rather than consuming it. Both sit at the
repo root and are the entry point, so there is no outer value to defer to — and
install.sh runs before the CLI exists at all."""


def shell_scripts() -> list[Path]:
    tracked = subprocess.run(
        ['git', 'ls-files', '*.sh', 'install.sh', 'update.sh'],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    return [REPO / line for line in tracked.stdout.split() if not line.startswith('tests/')]


def identifier(path: Path) -> str:
    return str(path.relative_to(REPO))


def assigning_scripts() -> list[Path]:
    return [path for path in shell_scripts() if ASSIGNMENT.search(path.read_text()) and path.name not in FRONT_DOORS]


@pytest.mark.parametrize('script', assigning_scripts(), ids=identifier)
def test_a_script_defers_to_an_exported_repo_root_before_asking_git(script: Path) -> None:
    for value in ASSIGNMENT.findall(script.read_text()):
        assert IDIOM.match(value.strip()), f'{identifier(script)} assigns DOTFILES_DIR={value.strip()}'


@pytest.mark.parametrize('script', shell_scripts(), ids=identifier)
def test_no_script_walks_up_the_tree_by_hand(script: Path) -> None:
    text = script.read_text()

    assert text.strip(), f'{identifier(script)} is empty, so it satisfies the sweep by carrying nothing'
    assert not RELATIVE_NAVIGATION.search(text), identifier(script)


def test_the_glob_finds_the_scripts_it_is_meant_to_cover() -> None:
    """A `git ls-files` pattern that stops matching collects zero cases and
    reports green, which is the failure mode this whole file exists to catch.

    The threshold is "still finding scripts", not a number. A count here is a
    second thing to maintain and it fails for the wrong reason — this asserted
    `> 10` and broke on the commit that deleted the platform package scripts,
    which is a conversion succeeding rather than a glob rotting. It falls to zero
    the moment the pattern stops matching, which is the case worth catching, and
    it is meant to reach zero legitimately once nothing here is bash.
    """
    assert assigning_scripts()
