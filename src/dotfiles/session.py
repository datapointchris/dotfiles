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
from typing import TYPE_CHECKING

from dotfiles import catalog as catalogs
from dotfiles import envfile
from dotfiles import machine as machines
from dotfiles import paths
from dotfiles import resolve as resolver

if TYPE_CHECKING:
    from dotfiles import evidence


class NoMachine(Exception):
    """Nothing named a machine, and `~/.env` does not either."""


def declared_machine() -> str:
    """What `~/.env` says this machine is, or '' where there is no such file.

    Module-level rather than a method, because both front doors need it and only
    one of them had it. `Session.resolve` reads the *file* and not only the
    environment so that a run outside a login shell still knows what it is — a
    systemd user timer, a launchd agent, `docker exec` and cron all inherit no
    `~/.env`, which is why the file is read and not only the environment. The
    wsl e2e run is where that is load-bearing: its second `apply` — the
    idempotence assertion — is a bare `docker exec`, so a resolver reading the
    environment alone answers "MACHINE is not set" on a machine whose `~/.env`
    says exactly what it is.
    """
    try:
        return envfile.read(Path.home() / '.env').get('MACHINE', '')
    except OSError:
        return ''


def resolve_machine(machine: str | None = None) -> str:
    """The machine this run is about, from the argument, the environment or `~/.env`.

    One function raising one error, so every front door says the same thing about
    the same failure. Two messages kept in step by hand is an arrangement where
    the more-used door gets the less actionable half, and nothing reports the
    divergence — the message therefore has one home and `apply` resolves through
    it like everything else.
    """
    name = machine or os.environ.get('MACHINE') or declared_machine()
    if not name:
        raise NoMachine(
            f'no machine named, and neither MACHINE nor ~/.env says what this is. Known: {", ".join(machines.names()) or "none"}'
        )
    return name


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
    refresh: bool = False
    """Permission to spend the network on being current.

    `check` reads cached upstream release versions so it can run at a prompt and
    in a pre-commit hook without an API call per release. This is the explicit
    opt-in to measuring instead, and it is the only thing that makes a `check`
    reach GitHub.
    """

    force: bool = False
    """Authorisation to replace what this repo did not create.

    Not a switch between reading and writing — `check` never writes whatever this
    says. It is the deliberate answer to a refusal, for adopting a machine that
    already had dotfiles of its own.
    """

    reinstall: frozenset[str] = frozenset()
    """Entry names to install again whatever measuring them concludes.

    Named rather than a blanket `--force`, because "install everything again"
    is not a thing anyone wants: it is a fresh `go install` of every Go tool and a
    re-download of every release to repair one binary. The names are validated
    against the plan before the walk starts, so a typo is a usage error rather
    than a run that quietly reinstalls nothing.

    Distinct from `force` above, which authorises overwriting a *foreign* file and
    decides nothing about what is installed.
    """

    @classmethod
    def resolve(cls, machine: str | None = None, **kwargs: object) -> Session:
        """Name the machine from the argument, else the environment, else `~/.env`.

        `~/.env` is where `MACHINE` lives, and it is also the file the env
        resource manages — the bootstrap this design lives with. A fresh box has
        no such file and passes `--machine` instead.

        Reading the *file* and not only the environment is what makes this work
        outside a login shell. A systemd user timer, a launchd agent, `docker
        exec` and cron all inherit no `~/.env`, so a scheduled `check` failed
        with "MACHINE is unset" on a machine whose `~/.env` said exactly what it
        was. Found by installing the timer and reading its first failure.
        """
        return cls(machine_name=resolve_machine(machine), **kwargs)  # type: ignore[arg-type]

    @functools.cached_property
    def catalog(self) -> catalogs.Catalog:
        return catalogs.load(self.repo / 'install' / 'packages.yml')

    @functools.cached_property
    def machine(self) -> machines.Machine:
        return machines.load(self.machine_name, self.repo)

    @functools.cached_property
    def plan(self) -> resolver.Plan:
        return resolver.resolve(self.catalog, self.machine, owner=self.owner)

    @functools.cached_property
    def inventories(self) -> evidence.Inventories:
        """What the package managers report, shared by everything that asks.

        On the Session because more than one provider wants the same answer and
        each of them observes for itself: four providers over three managers used
        to mean four dicts built by whichever resource happened to own them.
        Asked lazily and cached per manager, so this costs nothing on a run that
        names no registry package.

        `evidence` is imported here rather than at module scope because it reaches
        the resource vocabulary, which reaches this file.
        """
        from dotfiles import evidence

        return evidence.Inventories(refresh=self.refresh)

    @property
    def env_file(self) -> Path:
        return self.home / '.env'
