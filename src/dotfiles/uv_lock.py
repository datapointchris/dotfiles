"""What a project's `uv.lock` pins, in the two forms `uv tool install` takes.

`uv tool install` never reads a lock. Handed `<name> @ git+<repo>@<tag>` or an
editable path, it resolves every dependency afresh, so a tool runs on whatever
was newest that day while its CI tested the lock. claude-code-metrics installed
typer 0.27.3 against a locked 0.20.0, and every clean run exited 3.

`uv export` turns the lock into requirements, and they reach the install in two
files. A registry pin is a constraint, which holds a package to the locked
version without adding it. A URL pin has to be an override: uv refuses a
constraint whose URL differs from the one the package itself declares, and a
lock records `git+<repo>@<commit>` where the package declared `git+<repo>`.

uv writes both lists into the tool's receipt, so `uv tool upgrade` keeps them.
It does not check the hashes a constraints file carries, so the export drops
them rather than imply a verification nothing performs.
"""

from __future__ import annotations

import dataclasses as dc
from pathlib import Path

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
    if not (project / LOCK_FILE).is_file():
        return None
    exported = effects.run(EXPORT, cwd=project, output=Output.QUIET)
    if not exported.ok:
        raise Unexportable(exported.transcript.strip())
    return parse(exported.stdout)


def parse(exported: str) -> Pins:
    """A path requirement is neither, and is dropped: it is inside the commit being installed."""
    constraints: list[str] = []
    overrides: list[str] = []
    for line in exported.splitlines():
        line = line.strip()
        requirement = line.split(';', 1)[0]
        if ' @ ' in requirement:
            overrides.append(line)
        elif '==' in requirement:
            constraints.append(line)
    return Pins(tuple(constraints), tuple(overrides))
