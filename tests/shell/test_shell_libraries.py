"""A library must be sourceable without changing its caller's shell.

Sourcing is not calling: whatever a library turns on stays on for every line the
caller runs afterwards. `-e` is the one that has actually bitten — a script that
handles a non-zero exit itself starts dying on it instead — but the property is
asserted as "the flag set is unchanged", which costs nothing more and catches
`-u` and `-o pipefail` too.

Globbed, never listed. The bats version carried a hardcoded list, and its own
comment records that the list named `install/common/lib/platform-detection.sh`
for months after no such file existed: it reported seven libraries covered and
checked six. The directories were then a hardcoded list of their own, which is
the same failure one level up — and it cost the whole `shell/` tree, seven
libraries the property was never asked of.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from shells import REPO
from shells import shell_out

LIBRARY_ROOTS = ('configs/common/.local/shell', 'install/common/lib', 'shell')
"""Where a sourced library can live. Named, because which trees hold libraries is
a decision — `install/wsl/` holds scripts that run as their own process and
*must* carry `set -euo pipefail`, so a repo-wide glob for `*.sh` would assert the
opposite property of them. Everything below a root is derived."""

NOT_A_LIBRARY = {'git-bash'}
"""`shell/git-bash/` is payload for a different computer — `sync-windows-shell.sh`
copies it onto the Windows host beside WSL — so nothing here ever sources it and
it has no caller of ours to protect. `tests/symlinks/test_overlays.py` exempts it
by name for the same reason."""


def library_directories() -> tuple[str, ...]:
    """Every directory under a root that actually holds a `*.sh`.

    `shell/` is one root carrying seven of these across four axes, and an eighth
    arrives the day a coordinate needs one — which is exactly the growth a list
    of directories does not track.
    """
    return tuple(
        sorted(
            {
                str(path.parent.relative_to(REPO))
                for root in LIBRARY_ROOTS
                for path in (REPO / root).rglob('*.sh')
                if NOT_A_LIBRARY.isdisjoint(path.relative_to(REPO).parts)
            }
        )
    )


LIBRARY_DIRS = library_directories()


def libraries() -> list[Path]:
    return sorted(path for directory in LIBRARY_DIRS for path in (REPO / directory).glob('*.sh'))


def identifier(path: Path) -> str:
    return str(path.relative_to(REPO))


@pytest.mark.parametrize('library', libraries(), ids=identifier)
def test_no_library_changes_its_caller_s_shell_flags(library: Path) -> None:
    """`set -u` and nothing else, which is what a caller that has not opted into
    `-e` looks like — the state the library must hand back unchanged."""
    result = shell_out(
        'set -u; before="$-"; source "$1" >/dev/null; printf "%s|%s" "$before" "$-"',
        str(library),
        DOTFILES_DIR=str(REPO),
    )
    before, separator, after = result.stdout.partition('|')

    # A library that kills the shell mid-source prints neither reading, and
    # `'' == ''` is a pass. `functions.sh` did exactly this: three unguarded
    # `$ZSH_VERSION` reads, fine under zsh and fatal under `set -u` in bash.
    assert separator, f'{identifier(library)} never came back: {result.stderr.strip() or f"exit {result.returncode}"}'
    assert before == after, f'{identifier(library)} left the shell in {after} having been handed {before}'


@pytest.mark.parametrize('root', LIBRARY_ROOTS)
def test_every_library_root_contributes_at_least_one_directory(root: str) -> None:
    """A glob that matches nothing collects zero cases and reports green, which is
    the failure mode the hardcoded list had in a quieter form.

    Asked of the roots rather than the directories: a directory is only in
    `LIBRARY_DIRS` because a glob found a file in it, so asking whether it holds
    one answers itself. A root is the last thing here anybody wrote down, so it is
    the last thing that can be silently wrong.
    """
    assert [directory for directory in LIBRARY_DIRS if directory == root or directory.startswith(f'{root}/')]
