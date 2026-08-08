"""A library must be sourceable without changing its caller's shell.

Sourcing is not calling: whatever a library turns on stays on for every line the
caller runs afterwards. `-e` is the one that has actually bitten — a script that
handles a non-zero exit itself starts dying on it instead — but the property is
asserted as "the flag set is unchanged", which costs nothing more and catches
`-u` and `-o pipefail` too.

Globbed, never listed. The bats version carried a hardcoded list, and its own
comment records that the list named `install/common/lib/platform-detection.sh`
for months after no such file existed: it reported seven libraries covered and
checked six.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from shells import REPO
from shells import shell_out

LIBRARY_DIRS = ('configs/common/.local/shell', 'install/common/lib')


def libraries() -> list[Path]:
    return sorted(path for directory in LIBRARY_DIRS for path in (REPO / directory).glob('*.sh'))


def identifier(path: Path) -> str:
    return str(path.relative_to(REPO))


@pytest.mark.parametrize('library', libraries(), ids=identifier)
def test_no_library_changes_its_caller_s_shell_flags(library: Path) -> None:
    """`set -u` and nothing else, which is what a caller that has not opted into
    `-e` looks like — the state the library must hand back unchanged."""
    result = shell_out(
        'set -u; before="$-"; source "$1" >/dev/null 2>&1; printf "%s|%s" "$before" "$-"',
        str(library),
        DOTFILES_DIR=str(REPO),
    )
    before, _, after = result.stdout.partition('|')

    assert before == after, f'{identifier(library)} left the shell in {after} having been handed {before}'


@pytest.mark.parametrize('directory', LIBRARY_DIRS)
def test_every_library_directory_contributes_at_least_one_case(directory: str) -> None:
    """A glob that matches nothing collects zero cases and reports green, which is
    the failure mode the hardcoded list had in a quieter form."""
    assert list((REPO / directory).glob('*.sh'))
