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
from dotfiles import plan as planning
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

    The file, not only the environment: the wsl e2e idempotence assertion is a
    bare `docker exec`, which inherits no `~/.env`.
    """
    try:
        return envfile.read(Path.home() / '.env').get('MACHINE', '')
    except OSError:
        return ''


def resolve_machine(machine: str | None = None) -> str:
    """The machine this run is about, from the argument, the environment or `~/.env`.

    One function raising one error, so every front door says the same thing about
    the same failure.
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
    """Whether this run spends the network on being current.

    Every verb a person invokes sets it, since each asks a question a stale figure
    gets wrong. `--cached` reaches the False default, for a box that is rate-limited
    or has no route out; `--offline` resolves here too via `commands.currency`.

    **It buys three reads, not one**: GitHub per declared release, a fetch per
    plugin clone, and every manager in `syspkg.NETWORKED`.
    `docs/learnings/finding-where-a-slow-run-went.md` attributes a slow run between
    them.
    """

    force: bool = False
    """Authorisation to destroy what this repo did not create, to converge over it.

    Not a switch between reading and writing — `check` never writes whatever this
    says. It is the deliberate answer to a refusal, and there are two:

    - a file under `$HOME` this repo did not put there, replaced by the symlink
      that belongs at its path, for adopting a machine that already had dotfiles
      of its own;
    - a **system package** a declared release supersedes, removed by its own
      manager so the release can take the name, because the two ship one daemon
      between them and a machine running both is worse than a machine running
      either.

    **The second is narrowed by declaration rather than by this flag**: only a
    `Blocker` carrying an `under_force` command is cleared, which is a superseded
    *release*. A superseded system package refuses whatever this says.
    """

    packages: frozenset[str] = frozenset()
    """Entry names this run is narrowed to, or empty for every one this machine declares.

    `--package`, narrowing the plan as `owner` does, plus the prerequisites
    `resolve._named` keeps. Empty means unnarrowed, never a plan with nothing in it.

    Measured against the walk's `Selection` before anything runs, so a name outside
    the narrowing is a usage error rather than a converged verdict about a machine
    nothing looked at.
    """

    reinstall: bool = False
    """Install again whatever measuring concludes, for everything this run covers.

    A boolean, never a set of names: scope is `--package`'s job, per `cli-design.md`
    § "Scope is structural: the argument's presence selects it, never a flag".

    Bare it means everything the run covers, which is expensive rather than
    dangerous. Distinct from `force`, which authorises destroying something
    *foreign* and decides nothing about what is installed in its place.
    """

    @classmethod
    def resolve(cls, machine: str | None = None, **kwargs: object) -> Session:
        """Name the machine from the argument, else the environment, else `~/.env`.

        **Reading the *file* and not only the environment is what makes this work
        outside a login shell.** A systemd timer, a launchd agent, `docker exec`
        and cron all inherit no `~/.env`.

        **The manifest is read here, so a Session this returns has one.** Left
        lazy, `MachineError` surfaces from wherever the property is first touched
        — inside `survey`, past every handler, as a traceback and exit 1.

        Not in `__init__`: constructing a Session directly is the bootstrap and
        test affordance, and only the front door carries the guarantee.
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
    def plan(self) -> planning.Plan:
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
    def preconditions(self) -> planning.Preconditions:
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
