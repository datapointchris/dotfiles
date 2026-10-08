"""What a project's `uv.lock` pins, in the two forms `uv tool install` takes.

`uv tool install` never reads a lock. Handed `<name> @ git+<repo>@<tag>` or an
editable path, it resolves every dependency afresh, so a tool runs on whatever
was newest that day while its CI tested the lock.

`uv export` turns the lock into requirements, and they reach the install in two
files. A registry pin is a constraint, which holds a package to the locked
version without adding it. A URL pin has to be an override: uv refuses a
constraint whose URL differs from the one the package itself declares, and a
lock records `git+<repo>@<commit>` where the package declared `git+<repo>`.

The export names a URL-pinned package bare, and an override replaces the
requirement it matches whole. A tool declaring `gitdep[x] @ git+<repo>` would
install gitdep without what `x` brings. Only the lock's edges record the
extras, so `requested_extras` walks them and each override line carries what
the walk reached.

uv writes both lists into the tool's receipt, so `uv tool upgrade` keeps them.
uv does not check the hashes in a constraints file, so the export drops them
rather than imply a verification nothing performs.
"""

from __future__ import annotations

import dataclasses as dc
import re
import tomllib
from collections.abc import Collection
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dotfiles import effects
from dotfiles.effects import Output

LOCK_FILE = 'uv.lock'

EXPORT = ('uv', 'export', '--frozen', '--no-default-groups', '--no-emit-workspace', '--no-hashes', '--no-header', '--no-annotate')
"""The runtime closure as the lock records it, with the project's own packages left out.

`--no-emit-workspace` rather than `--no-emit-project`, because a workspace
member exports as a path, and the commit being installed already pins it.
`install.sh` carries the same flags, since it runs before this package exists.
"""


class Unexportable(Exception):
    """The lock is there and `uv export` would not read it. The message is what uv said."""


@dc.dataclass(frozen=True, slots=True)
class Pins:
    constraints: tuple[str, ...]
    overrides: tuple[str, ...]

    def arguments(self, directory: Path) -> list[str]:
        """Writes each non-empty list into `directory` and returns the flags naming them.

        An empty file is left out because uv warns about one on every install.
        """
        flags: list[str] = []
        for flag, lines in (('--constraints', self.constraints), ('--overrides', self.overrides)):
            if lines:
                written = directory / f'{flag.removeprefix("--")}.txt'
                written.write_text(''.join(f'{line}\n' for line in lines))
                flags += [flag, str(written)]
        return flags


def read(project: Path) -> Pins | None:
    """None where the project has no `uv.lock`. Raises `Unexportable` where it has one uv will not read."""
    lock = project / LOCK_FILE
    if not lock.is_file():
        return None
    exported = effects.run(EXPORT, cwd=project, output=Output.QUIET)
    if not exported.ok:
        raise Unexportable(exported.transcript.strip())
    return parse(exported.stdout, requested_extras(tomllib.loads(lock.read_text())))


def parse(exported: str, extras: Mapping[str, Collection[str]]) -> Pins:
    """A path requirement is neither a constraint nor an override. It is inside the commit being installed, so it is dropped.

    `extras` is keyed by normalized name, as `requested_extras` returns it.
    """
    constraints: list[str] = []
    overrides: list[str] = []
    for line in exported.splitlines():
        line = line.strip()
        requirement = line.split(';', 1)[0]
        if ' @ ' in requirement:
            name, pinned = line.split(' @ ', 1)
            wanted = extras.get(_normalized(name))
            overrides.append(f'{name}[{",".join(sorted(wanted))}] @ {pinned}' if wanted else line)
        elif '==' in requirement:
            constraints.append(line)
    return Pins(tuple(constraints), tuple(overrides))


def requested_extras(lock: Mapping[str, Any]) -> dict[str, frozenset[str]]:
    """The extras each package is installed with, walked from the project along its runtime edges.

    The walk starts at the project the lock sits in and follows `dependencies`,
    plus `optional-dependencies` for each extra an edge into the package asked
    for. Dev groups are left alone, as the export's `--no-default-groups`
    leaves them. Markers are not evaluated, so an extra one platform's edge asks
    for is asked for everywhere.
    """
    packages: dict[str, list[Mapping[str, Any]]] = {}
    for package in lock.get('package', ()):
        packages.setdefault(_normalized(package['name']), []).append(package)
    reached: dict[str, set[str]] = {
        name: set() for name, found in packages.items() if any(p.get('source') in ({'editable': '.'}, {'virtual': '.'}) for p in found)
    }
    pending = list(reached)
    while pending:
        name = pending.pop()
        for package in packages.get(name, ()):
            edges = [*package.get('dependencies', ())]
            for extra in reached[name]:
                edges += package.get('optional-dependencies', {}).get(extra, ())
            for edge in edges:
                target = _normalized(edge['name'])
                asked = set(edge.get('extra', ()))
                if target not in reached or not asked <= reached[target]:
                    reached.setdefault(target, set()).update(asked)
                    pending.append(target)
    return {name: frozenset(extras) for name, extras in reached.items() if extras}


def _normalized(name: str) -> str:
    return re.sub(r'[-_.]+', '-', name).lower()
