"""The language runtimes: whether each one this machine needs is there and current.

*Which* of them it needs belongs to the registry, not here: a toolchain is a
provider like every other mechanism, planned by `registry.ToolchainProvider` from
what the tool providers resolved.

What is left is the resource — ask the provider whether each one is there, compare
the versions against the floors the plan carries, and say what differs. Presence
is the provider's answer and never a second `which` here: two independent probes
let a packaged `go` satisfy a toolchain unpacked to a path nothing checked.

uv is ungated and always planned, because everything installed later resolves
through it — the symlink phase included, which shells out to `uv run`.
"""

from __future__ import annotations

import dataclasses as dc

from dotfiles import catalog
from dotfiles import evidence as ev
from dotfiles import registry
from dotfiles import versions
from dotfiles.privilege import Privilege
from dotfiles.resolve import DesiredItem
from dotfiles.resolve import Plan
from dotfiles.resources import Change
from dotfiles.resources import Outcome
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.session import Session

NAME = 'toolchains'


@dc.dataclass(frozen=True, slots=True)
class Observed:
    reported: dict[str, str]
    """Runtime name → the version string it printed, for those that answered."""

    absent: dict[str, str]
    """Runtime name → why it did not answer.

    The reason rather than a bare set, because "no `go` on PATH" and "a `go` that
    exits non-zero" are different findings and only the first is what a fresh
    machine looks like. A half-extracted tarball leaves the binary in place and
    `which` satisfied by it.
    """

    @property
    def summary(self) -> str:
        """Names the runtimes rather than counting them: which ones a machine
        needs is derived from its tool lists, so the list itself is the finding."""
        return ', '.join(sorted(self.reported)) or 'none needed'


class ToolchainsResource:
    name = NAME
    help = 'language runtimes and their version managers'

    def observe(self, session: Session, plan: Plan) -> Observed:
        reported: dict[str, str] = {}
        absent: dict[str, str] = {}

        for item in plan.for_resource(NAME):
            # Asked of the provider rather than of PATH. A runtime with a fixed
            # home is answered by that path, and `which` is a different question:
            # Arch's `go` package arrived transitively in a container, `which go`
            # found /usr/sbin/go, and this reported the toolchain present while
            # /usr/local/go did not exist — so every Go tool built against a
            # runtime this repo had not installed. `registry.evidence_for` already
            # knew; only this second measurement did not ask it.
            found = registry.evidence_for(item, session.inventories)
            probe = item.evidence_path or item.executable
            if found.verdict is not Verdict.MATCHED:
                absent[item.name] = found.detail
            elif (version := ev.reported_version(probe)) is None:
                # Probed where it was found, not by name. For a runtime with a
                # fixed home those are different binaries the moment a package
                # manager put one on PATH, and asking the wrong one is how this
                # came to report a version the machine does not run.
                absent[item.name] = f'{probe} would not report a version'
            else:
                reported[item.name] = version

        return Observed(reported=reported, absent=absent)

    def diff(self, plan: Plan, observed: Observed) -> tuple[Change, ...]:
        changes = []
        for item in plan.for_resource(NAME):
            if item.name in observed.absent:
                changes.append(
                    Change(
                        NAME,
                        item.stage,
                        item.address,
                        Verdict.MISSING,
                        detail=observed.absent[item.name],
                        desired=item,
                        privileged=registry.needs_root(item),
                    )
                )
                continue

            reported = observed.reported[item.name]
            floor = _floor(item)
            if not floor:
                continue

            meets = versions.at_least(reported, floor)
            if meets is None:
                changes.append(
                    Change(
                        NAME,
                        item.stage,
                        item.address,
                        Verdict.UNKNOWN,
                        detail=f'declares a floor of {floor} and reported {reported!r}, which has no version in it',
                        repair=Repair.NONE,
                        desired=item,
                        observed=reported,
                    )
                )
            elif not meets:
                changes.append(
                    Change(
                        NAME,
                        item.stage,
                        item.address,
                        Verdict.STALE,
                        detail=f'below the declared floor of {floor}',
                        desired=item,
                        observed=reported,
                        privileged=registry.needs_root(item),
                    )
                )
        return tuple(changes)

    def perform(self, session: Session, change: Change, privilege: Privilege) -> Outcome:
        """Whichever version manager planned it installs it, or says why it cannot."""
        return registry.install(session, change, privilege)


def _floor(item: DesiredItem) -> str:
    """The declared minimum for a runtime, or '' where none is declared.

    Read off the entry the plan carries rather than looked up, because
    `min_version` is a fact about what the tools need and belongs beside them —
    and resolution finishing in the plan is what stops this reaching back into the
    catalog for it.
    """
    entry = item.entry
    if not isinstance(entry, catalog.Runtime):
        return ''
    return entry.min_version or entry.version


RESOURCE = ToolchainsResource()
