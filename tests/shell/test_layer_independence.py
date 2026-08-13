"""Two layers a machine loads together must not define the same name.

`.zshrc` and `.bashrc` find the coordinate layers by globbing the deployed tree,
so they arrive in path order rather than in the order the axes are declared. That
is only safe while no two of them define the same symbol: with a collision, which
one wins would be decided by alphabetical accident, and moving a definition
between two files that both load would silently change a machine.

The invariant is what makes the ordering question moot rather than resolved. It
is asserted per machine, because whether two layers co-load is a property of a
manifest's coordinates and not of the repo.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dotfiles import machine as machines

REPO = Path(__file__).resolve().parent.parent.parent

DEFINITION = re.compile(
    r"""^\s*(?:
        alias\s+(?P<alias>[\w.-]+)=
      | export\s+(?P<export>\w+)=
      | function\s+(?P<function>[\w.-]+)
      | (?P<posix>[\w.-]+)\s*\(\)
    )""",
    re.VERBOSE,
)
"""Every shape these files declare a name in.

Deliberately blunt. A parser that missed a shape would make the test pass by
reading less, so this errs toward matching and a false positive is a name worth
looking at anyway.
"""


def defined(path: Path) -> set[str]:
    names = set()
    for line in path.read_text().splitlines():
        found = DEFINITION.match(line)
        if found:
            names.add(next(value for value in found.groupdict().values() if value))
    return names


def layers_for(name: str) -> list[Path]:
    """The layer directories this machine both selects and actually has.

    An axis earns a directory only where something differs along it, so every
    machine names six and has one or two. The absent ones are what the glob
    silently skips and are not a fault.
    """
    machine = machines.load(name)
    return [REPO / 'shell' / selected for selected in machine.coordinates.directories if (REPO / 'shell' / selected).is_dir()]


@pytest.mark.parametrize('name', machines.names())
def test_no_two_layers_one_machine_loads_define_the_same_name(name: str) -> None:
    """A collision here is an authoring mistake, and the shells cannot see it.

    They source whatever is in the tree. Nothing in a shell can report that two
    files disagreed, so this is the only place the question is asked.
    """
    seen: dict[str, Path] = {}
    collisions = []
    for layer in layers_for(name):
        for source in sorted(layer.glob('*.sh')):
            for symbol in defined(source):
                if symbol in seen and seen[symbol].parent != source.parent:
                    collisions.append(f'{symbol}: {seen[symbol].relative_to(REPO)} and {source.relative_to(REPO)}')
                seen.setdefault(symbol, source)

    assert not collisions, f'{name} loads two layers defining one name: ' + '; '.join(collisions)


def test_the_machines_under_test_actually_load_layers() -> None:
    """Guards the test above: every machine having no layers would pass it vacuously."""
    loaded = {name: layers_for(name) for name in machines.names()}

    assert any(layers for layers in loaded.values()), f'no machine selects an existing layer: {loaded}'
