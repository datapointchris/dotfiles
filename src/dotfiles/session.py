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
from dotfiles.refusal import Refusal
from dotfiles.vocabulary import ExitCode

if TYPE_CHECKING:
    from dotfiles import evidence


class NoMachine(Refusal):
    """Nothing named a machine, and `~/.env` does not either.

    `USAGE`, for the same reason `NoSuchMachine` is: naming one is what fixes it,
    so a caller can act on it by retyping. It is the twin of that error, from the
    other side — one is a name nothing declares, this is no name at all.
    """

    code = ExitCode.USAGE


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
    on a timer without an API call per release. This is the explicit
    opt-in to measuring instead, and it is the only thing that makes a `check`
    reach GitHub.
    """

    force: bool = False
    """Authorisation to replace what this repo did not create.

    Not a switch between reading and writing — `check` never writes whatever this
    says. It is the deliberate answer to a refusal, for adopting a machine that
    already had dotfiles of its own.
    """

    packages: frozenset[str] = frozenset()
    """Entry names this run is narrowed to, or empty for every one this machine declares.

    `--package`, and it narrows the plan exactly as `owner` above does — plus the
    prerequisites the named entries need, which `resolve._named` keeps. Empty
    means unnarrowed, so the field spells "no narrowing" the same way `owner`'s
    None does rather than as a plan with nothing in it.

    The names are measured against the walk's `Selection` before anything runs, so
    a name outside the narrowing is a usage error rather than a run that reports a
    converged machine having looked at none of it.
    """

    reinstall: bool = False
    """Install again whatever measuring concludes, for everything this run covers.

    A boolean rather than a set of names, because scope is `--package`'s job:
    `cli-design.md` § "Scope is structural: the argument's presence selects it,
    never a flag" is what a name-taking `--reinstall` broke, welding one narrowing
    onto a force flag that every resource could otherwise honour. What survives as
    a flag is § "A flag never decides whether the command writes"'s test — what
    parameterises the work the same way whichever verb runs it — and a boolean
    passes it where `--reinstall lazygit` does not.

    Bare, it therefore means everything the run covers. That is expensive rather
    than dangerous — a fresh `go install` of every Go tool and a re-download of
    every release — which is exactly the case § "Scope is structural" sanctions a
    set-wide act for, and `--package` is how a caller spends less.

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

        **The manifest is read here, so a Session this returns has one.** Naming a
        machine and proving the name means something are the same act. Split, the
        `machine` property is lazy and `MachineError` surfaces from wherever it is
        first touched — inside `survey`, past every handler, as a traceback and
        exit 1. A name that resolves to no manifest is not a resolved machine.

        Deliberately not in `__init__`: constructing a Session directly is the
        bootstrap and test affordance, where the caller supplies the repo and
        knows what is on disk. This is the front door, and only the front door
        carries the guarantee.
        """
        session = cls(machine_name=resolve_machine(machine), **kwargs)  # type: ignore[arg-type]
        _ = session.machine
        return session

    @functools.cached_property
    def catalog(self) -> catalogs.Catalog:
        return catalogs.load(self.repo / 'install' / 'packages.yml')

    @functools.cached_property
    def machine(self) -> machines.Machine:
        return machines.load(self.machine_name, self.repo)

    @functools.cached_property
    def plan(self) -> resolver.Plan:
        return resolver.resolve(self.catalog, self.machine, owner=self.owner, packages=self.packages or None)

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

    @functools.cached_property
    def preconditions(self) -> resolver.Preconditions:
        """Which preconditions this machine meets, answered once for the whole run.

        On the Session for the reason `inventories` is: more than one resource
        wants the same answer and each observes for itself. The `gh` half is the
        expensive one — `gh auth token` is 30ms against the two stats `have_amd_gpu`
        costs — and it was already being paid once per resource that asked.

        `evidence` is imported here rather than at module scope because it reaches
        the resource vocabulary, which reaches this file.
        """
        from dotfiles import evidence

        return evidence.measured_preconditions()

    @property
    def env_file(self) -> Path:
        return self.home / '.env'
