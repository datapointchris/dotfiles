"""The language runtimes, and which of them this machine needs.

A toolchain is never subscribed to directly. A machine gets Go because it
declared `go_tools`, and Rust because it declared `cargo_packages` — which is why
the manifest booleans that used to gate them (`go:`, `rust:`, `nvm:`, `tenv:`) were
removed: they said nothing the tool lists did not, and a machine could set one
without declaring a single tool for it.

uv is the exception and is ungated. A manifest with empty uv lists still needs
it, because everything installed later resolves through it — before the CLI
existed, the symlink phase itself shelled out to `uv run` and died with exit 127
on `linux-lxc-server`.
"""

from __future__ import annotations

import dataclasses as dc
import shutil

from dotfiles import versions
from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.privilege import Privilege
from dotfiles.resolve import Plan
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Outcome
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.session import Session

NAME = 'toolchains'


@dc.dataclass(frozen=True, slots=True)
class Toolchain:
    """One runtime, what pulls it in, and how to ask its version."""

    name: str
    probe: tuple[str, ...]
    stage: Stage
    needed_by: str = ''
    """The catalog section whose presence requires it. Empty means ungated."""

    runtime: str = ''
    """The `runtimes` entry carrying its version constraint, where one exists."""


TOOLCHAINS = (
    Toolchain('uv', ('uv', '--version'), Stage.TOOLCHAIN),
    Toolchain('go', ('go', 'version'), Stage.TOOLCHAIN, needed_by='go_tools', runtime='go'),
    Toolchain('rust', ('rustc', '--version'), Stage.TOOLCHAIN, needed_by='cargo_packages', runtime='rust'),
    # After TOOLS, because fnm ships as a cargo package and node is whatever fnm
    # pins as its default alias.
    Toolchain('node', ('node', '--version'), Stage.NODE, needed_by='npm_globals'),
)


@dc.dataclass(frozen=True, slots=True)
class Observed:
    installed: dict[str, str]
    """Toolchain name → the version string it reported, for those that answered."""

    absent: frozenset[str]

    @property
    def summary(self) -> str:
        """Names the runtimes rather than counting them: which ones a machine
        needs is derived from its tool lists, so the list itself is the finding."""
        return ', '.join(sorted(self.installed)) or 'none needed'


class ToolchainsResource:
    name = NAME
    help = 'language runtimes and their version managers'

    def observe(self, session: Session, plan: Plan) -> Observed:
        installed: dict[str, str] = {}
        absent: set[str] = set()

        for toolchain in _needed(plan):
            if not shutil.which(toolchain.probe[0]):
                absent.add(toolchain.name)
                continue
            result = run(list(toolchain.probe), output=Output.QUIET)
            if result.ok and result.transcript.strip():
                installed[toolchain.name] = result.transcript.strip().splitlines()[0]
            else:
                absent.add(toolchain.name)

        return Observed(installed=installed, absent=frozenset(absent))

    def diff(self, plan: Plan, observed: Observed) -> tuple[Change, ...]:
        changes = []
        for toolchain in _needed(plan):
            if toolchain.name in observed.absent:
                changes.append(
                    Change(NAME, toolchain.stage, toolchain.name, Verdict.MISSING, detail=f'{toolchain.probe[0]} is not on PATH')
                )
                continue
            reported = observed.installed[toolchain.name]
            floor = _floor(plan, toolchain)
            if not floor:
                continue
            meets = versions.at_least(reported, floor)
            if meets is None:
                changes.append(
                    Change(
                        NAME,
                        toolchain.stage,
                        toolchain.name,
                        Verdict.UNKNOWN,
                        detail=f'declares a floor of {floor} and reported {reported!r}, which has no version in it',
                        repair=Repair.NONE,
                        observed=reported,
                    )
                )
            elif not meets:
                changes.append(
                    Change(
                        NAME,
                        toolchain.stage,
                        toolchain.name,
                        Verdict.STALE,
                        detail=f'below the declared floor of {floor}',
                        observed=reported,
                    )
                )
        return tuple(changes)

    def perform(self, session: Session, change: Change, privilege: Privilege) -> Outcome:
        """Not yet this resource's to do.

        Each toolchain installs through its own version manager — rustup, fnm, the
        go tarball, uv's own installer — and those are genuine sequences of shell
        commands that step 5 converts alongside the release installers.
        """
        return Outcome(change, OutcomeStatus.REFUSED, "run 'dotfiles toolchains apply', which still drives the phase registry")


def _needed(plan: Plan) -> tuple[Toolchain, ...]:
    """Which toolchains this machine's declaration implies."""
    return tuple(toolchain for toolchain in TOOLCHAINS if not toolchain.needed_by or plan.for_section(toolchain.needed_by))


def _floor(plan: Plan, toolchain: Toolchain) -> str:
    """The declared minimum for a toolchain, or '' where none is declared.

    Read off the catalog rather than carried here, because `min_version` is a fact
    about what the tools need and belongs beside them.
    """
    if not toolchain.runtime:
        return ''
    for entry in plan.runtimes:
        if entry.name == toolchain.runtime:
            return entry.min_version or entry.version
    return ''


RESOURCE = ToolchainsResource()
