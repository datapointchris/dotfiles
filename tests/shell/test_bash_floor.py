"""Nothing every machine gets may use a bash 4 construct.

macOS ships bash 3.2 and always will, because the licence changed to GPLv3.
`apps/common/` and `configs/common/.local/shell/` are the two trees carrying no
coordinate, so both land on the Mac unchanged — where `mapfile` is
`command not found`, and under `set -e` the script dies on the spot.

**Homebrew's bash 5 is what makes it invisible.** The file runs on the
developer's own Mac, shellcheck says nothing, and only a runner using the system
bash ever disagrees. `notes` carried `mapfile` in two of its four commands for as
long as nobody ran `notes new` from a shell that was not Homebrew's.

A grep rather than a real interpreter, deliberately: `standards/shell.md` calls
this the proportionate guard, against re-execing every script under a bash 5 —
which would put a dependency on the very thing being avoided at the top of each
one.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from shells import REPO

SCANNED_DIRS = ('apps/common', 'configs/common/.local/shell')
"""The trees with no `<axis>/<value>` on them: every machine gets both, so a Mac
gets both. An overlay is free to use bash 4 where its coordinate rules a Mac out
— `apps/display/wayland/` reaches no macOS box — and is deliberately not scanned
here rather than exempted by name."""

BASH_FOUR = (
    (re.compile(r'\bmapfile\b'), 'mapfile'),
    (re.compile(r'\breadarray\b'), 'readarray'),
    (re.compile(r'\b(?:declare|typeset|local)\s+-[a-zA-Z]*A'), 'an associative array'),
    (re.compile(r'\$\{[a-zA-Z_][a-zA-Z0-9_]*(?:\[[^]]*\])?(?:\^|,)'), 'a case-modifying expansion'),
)
"""What bash 4 added and 3.2 has no spelling for.

`${v^^}` and `${v,,}` are matched at the operator rather than whole, so `${v^}`
and `${v,pattern}` are caught by the same entry. The subscript is optional
because `${arr[0]^^}` is the same construct.
"""

DECLARES_BASH = re.compile(r'^#!.*\bbash\b|^#\s*shellcheck\s+shell=bash')
"""What makes a file bash, given that half of these have no extension and two are
Python. The shellcheck directive counts because `prompt.bash` and `prompt-lib.sh`
are sourced rather than executed and so carry no shebang — and `prompt.zsh`,
which carries neither, is zsh and is not this rule's business."""


def is_bash(path: Path) -> bool:
    return any(DECLARES_BASH.match(line) for line in path.read_text().splitlines()[:5])


def bash_scripts(directory: str) -> list[Path]:
    return sorted(path for path in (REPO / directory).iterdir() if path.is_file() and is_bash(path))


def identifier(path: Path) -> str:
    return str(path.relative_to(REPO))


def code_lines(path: Path) -> Iterator[tuple[int, str]]:
    """Every line that is not wholly a comment.

    `flags.sh` names `${v,,}` in prose explaining why it uses a character class
    instead, and a guard that cannot tell prose from code makes that sentence
    unwritable — which is worse than the sentence, because the next person just
    deletes the explanation.
    """
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.lstrip().startswith('#'):
            yield number, line


@pytest.mark.parametrize('script', [path for directory in SCANNED_DIRS for path in bash_scripts(directory)], ids=identifier)
def test_no_script_every_machine_gets_uses_a_bash_4_construct(script: Path) -> None:
    found = [
        f'{identifier(script)}:{number} uses {construct}'
        for number, line in code_lines(script)
        for pattern, construct in BASH_FOUR
        if pattern.search(line)
    ]

    assert not found, 'macOS runs bash 3.2:\n' + '\n'.join(found)


@pytest.mark.parametrize(('construct', 'sample'), [('mapfile', 'mapfile -t x < <(f)'), ('${v,,}', 'echo "${name,,}"')])
def test_the_guard_recognizes_what_it_is_looking_for(construct: str, sample: str) -> None:
    """A grep that matches nothing reports the same green as a clean tree, and
    nothing about editing the patterns brings anyone back to check."""
    assert any(pattern.search(sample) for pattern, _ in BASH_FOUR), construct


@pytest.mark.parametrize('directory', SCANNED_DIRS)
def test_every_scanned_directory_contributes_at_least_one_script(directory: str) -> None:
    """The other way to be vacuously green: a directory that moved collects no
    cases and says nothing about it."""
    assert bash_scripts(directory)
