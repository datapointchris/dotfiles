"""Everything a command needs about this run, built once and passed down.

The declaration is read once per process here rather than once per question. The
files it reads are loaded lazily, because most invocations — `--help`,
`report latest`, `repo path` — never ask about a machine at all, and parsing
`packages.yml` costs 78ms of a run that was going to print one line.

Interactivity is a field rather than a probe, per `python.md` § "Inject terminal
detection; never monkeypatch it": a test that wants a non-interactive run builds
a Session that says so.
"""

from __future__ import annotations

import dataclasses as dc
import functools
import os
from pathlib import Path

from dotfiles import catalog as catalogs
from dotfiles import machine as machines
from dotfiles import paths
from dotfiles import resolve as resolver


class NoMachine(Exception):
    """Nothing named a machine, and `~/.env` does not either."""


@dc.dataclass(frozen=True)
class Session:
    """One invocation's world.

    Not slotted, because the three lazy readers below are `functools.cached_property`
    and that needs a `__dict__` to cache into.
    """

    machine_name: str
    repo: Path = paths.REPO_ROOT
    home: Path = dc.field(default_factory=Path.home)
    interactive: bool = False
    as_json: bool = False
    offline: bool = False
    owner: str | None = None
    force: bool = False
    """Authorisation to replace what this repo did not create.

    Not a switch between reading and writing — `check` never writes whatever this
    says. It is the deliberate answer to a refusal, for adopting a machine that
    already had dotfiles of its own.
    """

    @classmethod
    def resolve(cls, machine: str | None = None, **kwargs: object) -> Session:
        """Name the machine from the argument, else from the environment.

        `~/.env` is where `MACHINE` lives, and it is also the file the env
        resource manages — the bootstrap this design lives with. A fresh box has
        no such file and passes `--machine` instead.
        """
        name = machine or os.environ.get('MACHINE') or ''
        if not name:
            raise NoMachine(f'no machine named, and MACHINE is unset. Known: {", ".join(machines.names()) or "none"}')
        return cls(machine_name=name, **kwargs)  # type: ignore[arg-type]

    @functools.cached_property
    def catalog(self) -> catalogs.Catalog:
        return catalogs.load(self.repo / 'install' / 'packages.yml')

    @functools.cached_property
    def machine(self) -> machines.Machine:
        return machines.load(self.machine_name, self.repo)

    @functools.cached_property
    def plan(self) -> resolver.Plan:
        return resolver.resolve(self.catalog, self.machine, owner=self.owner)

    @property
    def env_file(self) -> Path:
        return self.home / '.env'
