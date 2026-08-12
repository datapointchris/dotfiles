"""Nothing that lands on a Mac may use a bash 4 construct.

macOS ships bash 3.2 and always will, because the licence changed to GPLv3.
There `mapfile` is `command not found`, and under `set -e` the script dies on the
spot — while an interactive zsh, which has no `mapfile` builtin either, reports
it per call and carries on with the function half-run.

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

from dotfiles import machine as machines
from dotfiles.coordinates import OSFamily
from dotfiles.resources import symlinks
from dotfiles.symlinks import core


def scanned_directories() -> tuple[Path, ...]:
    """Every source directory that deploys to a machine running bash 3.2.

    Asked of `symlinks.layers` against the declared machines, because a list of
    trees is the same drift one level up from the list of files this guard
    replaced — and it had already happened: `shell/common/` reaches every machine
    and is sourced by every interactive zsh, while `shell/os/darwin/` and
    `shell/pkg/brew/` are overlays a Mac's coordinates rule *in*, and a
    hand-written list named none of the three.

    An overlay a Mac's coordinates rule out is absent because `layers` never
    yields it, not because anything here exempts it by name. `home` only shapes
    the destination, which nothing in this file reads.
    """
    directories: dict[Path, None] = {}
    for name in machines.names(REPO):
        coordinates = machines.load(name, REPO).coordinates
        if coordinates.os_family is not OSFamily.DARWIN:
            continue
        for source, _destination, _layer in symlinks.layers(REPO, coordinates, Path('/')):
            if source.is_dir():
                directories[source] = None
    return tuple(directories)


SCANNED_DIRS = scanned_directories()

BASH_FOUR = (
    (re.compile(r'\bmapfile\b'), 'mapfile'),
    (re.compile(r'\breadarray\b'), 'readarray'),
    (re.compile(r'\b(?:declare|typeset|local)\s+-[a-zA-Z]*A'), 'an associative array'),
    (re.compile(r'\$\{(?:[a-zA-Z_][a-zA-Z0-9_]*|[0-9]+|[@*])(?:\[[^]]*\])?(?:\^|,)'), 'a case-modifying expansion'),
)
"""What bash 4 added and 3.2 has no spelling for.

`${v^^}` and `${v,,}` are matched at the operator rather than whole, so `${v^}`
and `${v,pattern}` are caught by the same entry. The subscript is optional
because `${arr[0]^^}` is the same construct, and the name may be a digit or `@`
because `${1^^}` is the spelling a function reaching for this actually uses.

The operator has to sit against the name for the match: `${v/,/;}` replaces
commas and is bash 3.2's business as much as bash 4's.
"""

SAMPLES = (
    ('mapfile', 'mapfile -t lines < <(printf "a\\nb\\n")'),
    ('readarray', 'readarray -t lines <"$file"'),
    ('an associative array', 'declare -A seen'),
    ('a case-modifying expansion', 'echo "${name,,}"'),
    ('a case-modifying expansion', 'echo "${1^^}"'),
)
"""One line of real bash 4 per construct `BASH_FOUR` claims to catch.

More than one where a construct has spellings a single sample would not reach.
A sample naming a variable leaves `${1^^}` untested, and a positional parameter
is what a function reaching for case modification actually holds.

Written out rather than derived from `BASH_FOUR`, which is the whole reason it
holds: a sample generated from the thing under test vanishes with it, so
deleting a pattern would delete the case that would have caught the deletion.
The two are tied together in the other direction instead, by
`test_every_pattern_has_a_sample`.
"""

DECLARES_BASH = re.compile(r'^#!.*\bbash\b|^#\s*shellcheck\s+shell=bash')
"""What makes a file bash, given that half of these have no extension and two are
Python. The shellcheck directive counts because `prompt.bash` and `prompt-lib.sh`
are sourced rather than executed and so carry no shebang — and `prompt.zsh`,
which carries neither, is zsh and is not this rule's business."""


def is_bash(path: Path) -> bool:
    return any(DECLARES_BASH.match(line) for line in path.read_text().splitlines()[:5])


def bash_scripts(directory: Path) -> list[Path]:
    """Recursive, and filtered the way deployment filters.

    `configs/common/` is a whole home directory rather than a flat drawer of
    scripts, so its `.bashrc` and its `.config/` payload are only reachable by
    walking it — and `core.should_exclude` is what keeps a vendored tmux plugin,
    which never deploys, from being held to this repo's floor.
    """
    return sorted(
        path for path in directory.rglob('*') if path.is_file() and not core.should_exclude(path.relative_to(directory)) and is_bash(path)
    )


SCRIPTS = [path for directory in SCANNED_DIRS for path in bash_scripts(directory)]


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


@pytest.mark.parametrize('script', SCRIPTS, ids=identifier)
def test_no_script_a_mac_receives_uses_a_bash_4_construct(script: Path) -> None:
    found = [
        f'{identifier(script)}:{number} uses {construct}'
        for number, line in code_lines(script)
        for pattern, construct in BASH_FOUR
        if pattern.search(line)
    ]

    assert not found, 'macOS runs bash 3.2:\n' + '\n'.join(found)


@pytest.mark.parametrize(('construct', 'sample'), SAMPLES, ids=[sample for _, sample in SAMPLES])
def test_the_guard_recognizes_what_it_is_looking_for(construct: str, sample: str) -> None:
    """A grep that matches nothing reports the same green as a clean tree, and
    nothing about editing the patterns brings anyone back to check.

    Which pattern matched, not whether any did: `declare -A seen` is caught by
    the associative-array entry and by nothing else, so an `any()` over the whole
    tuple passes with that entry deleted.
    """
    matched = [name for pattern, name in BASH_FOUR if pattern.search(sample)]
    assert construct in matched, f'nothing in BASH_FOUR catches {sample!r}; matched {matched or "nothing"}'


def test_every_pattern_has_a_sample() -> None:
    """The direction the samples cannot cover themselves: a fifth pattern is free
    to arrive untested, because a sample list nobody edits stays green."""
    assert {construct for _, construct in BASH_FOUR} == {construct for construct, _ in SAMPLES}


def test_a_machine_running_bash_32_is_declared() -> None:
    """The scan derives its own scope, so a fleet holding no Mac collects nothing
    and reports the same green as a clean tree."""
    assert SCANNED_DIRS


@pytest.mark.parametrize('tree', [tree for tree, _below, _nested in symlinks.TREES])
def test_every_deployed_tree_reaches_the_scan(tree: str) -> None:
    """The other way to be vacuously green: a tree that stops contributing cases
    says nothing about it. Each of the three carries bash that a Mac runs."""
    assert [script for script in SCRIPTS if script.relative_to(REPO).parts[0] == tree]
