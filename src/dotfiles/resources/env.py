"""`~/.env`: the machine's identity and its feature flags.

The first stage of every run, because everything below it reads the file: a
botched migration leaves a machine with a broken interactive shell independently,
as each box migrates — `.zshrc` sources `~/.env` before anything else and errors
when `PLATFORM` is unset.

Two kinds of drift live here and must not be collapsed. A flag whose value does
not match the declaration is ours to repair, and `apply` does. A machine-local
secret or a file safekeep restores is drift we can *report* and never write:
the repo knows a machine needs `WINDOWS_USER` and must never know its value.
Reporting one as a failure would make every freshly-installed work box look
broken between the install and the restore.
"""

from __future__ import annotations

import dataclasses as dc
from pathlib import Path

from dotfiles import envfile
from dotfiles.privilege import Privilege
from dotfiles.resolve import Plan
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Outcome
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.session import Session

NAME = 'env'

RESTORE = 'restore it with safekeep'
"""What gets a required file back, unless its entry declares otherwise."""


@dc.dataclass(frozen=True, slots=True)
class Observed:
    """What the machine has, read once."""

    path: Path
    exists: bool
    values: dict[str, str]
    present_files: frozenset[str]

    generated: dict[str, str]
    """What the section above the OVERRIDES marker sets, on its own.

    Carried beside `values` rather than replacing it, because the two answer
    different questions. `values` is what the machine reads, which is what says
    whether a flag arrived at all and what a required value was set to — both of
    which are answered below the marker. `generated` is the half a regeneration
    owns, and so the only half whose value can be held to the declaration.

    Required rather than defaulted, because an empty mapping is a valid reading of
    a markerless file: defaulted, an `Observed` built without it would report no
    value drift anywhere and call the machine converged.
    """

    @property
    def summary(self) -> str:
        return '~/.env matches the manifest and the declared flags'


class EnvResource:
    name = NAME
    help = '~/.env: the machine identity and its feature flags'

    def observe(self, session: Session, plan: Plan) -> Observed:
        path = session.env_file
        return Observed(
            path=path,
            exists=path.exists(),
            values=envfile.read(path),
            present_files=frozenset(entry.path for entry in plan.machine.required_files if entry.is_present),
            generated=envfile.read_generated(path),
        )

    def diff(self, plan: Plan, observed: Observed) -> tuple[Change, ...]:
        machine = plan.machine

        if not observed.exists:
            return (
                Change(
                    NAME,
                    Stage.ENVIRONMENT,
                    str(observed.path),
                    Verdict.MISSING,
                    detail='the file does not exist, so no shell knows what machine this is',
                ),
            )

        changes: list[Change] = []
        changes.extend(_identity(machine, observed))
        changes.extend(_flags(machine, observed))
        changes.extend(_requirements(machine, observed))
        changes.extend(_undeclared(machine, observed))
        return tuple(changes)

    def perform(self, session: Session, change: Change, privilege: Privilege) -> Outcome:
        """Rewrite the generated section.

        Every automatic change here is repaired by one write, so this re-reads
        first and skips when an earlier change in the same batch already fixed
        it. That is the same live re-verification every resource does, and it is
        what stops N drifted flags becoming N rewrites of one file.
        """
        machine = session.machine
        observed = self.observe(session, session.plan)
        if not any(later.actionable for later in self.diff(session.plan, observed)):
            return Outcome(change, OutcomeStatus.SKIPPED, 'already written by an earlier change in this run')

        migrated = envfile.write(observed.path, machine)
        message = f'wrote {observed.path}'
        if migrated:
            message += ' — no marker found, so the whole previous file was preserved below one; prune what it now duplicates'
        return Outcome(change, OutcomeStatus.DONE, message)


def _identity(machine, observed: Observed) -> list[Change]:
    """What machine this is, and where it sits on each axis.

    The coordinates are identity rather than configuration: they select which
    overlays every shell sources, so one of them missing or stale is a machine
    loading someone else's files, not a preference that drifted. That is the
    whole of why an override below the marker is named here and stays silent in
    `_flags` — the marker exists to let a machine hold a preference of its own,
    and a coordinate is not a preference.

    Which half disagrees decides who can repair it. A generated value that no
    longer matches the manifest is one rewrite away and `apply` makes it. An
    override below the marker is the last assignment in the file, so the shell
    takes it whatever the section above says: `apply` owns only the section above,
    so offering it as repairable buys a `check` that finds it, an `apply` that
    reports DONE, a fresh `.env.bak` over the last one, and a machine that has not
    moved.
    """
    expected_values = {'MACHINE': machine.name, 'PLATFORM': machine.platform_label, **envfile.coordinate_exports(machine)}

    changes = []
    for key, expected in expected_values.items():
        actual = observed.values.get(key)
        written = observed.generated.get(key)
        if actual is None:
            changes.append(Change(NAME, Stage.ENVIRONMENT, key, Verdict.MISSING, detail=f'the manifest declares {expected}'))
        elif written is not None and written != expected:
            changes.append(
                Change(NAME, Stage.ENVIRONMENT, key, Verdict.STALE, detail=f'the manifest declares {expected}', observed=written)
            )
        elif actual != expected:
            changes.append(
                Change(
                    NAME,
                    Stage.ENVIRONMENT,
                    key,
                    Verdict.STALE,
                    detail=f'the manifest declares {expected}, and an assignment below the marker overrides it',
                    observed=actual,
                    repair=Repair.BY_HAND,
                    advice=f'drop that assignment from {observed.path}, or declare {actual} in the manifest',
                )
            )
    return changes


def _flags(machine, observed: Observed) -> list[Change]:
    """Whether every declared flag arrived, parses, and still says what it should.

    The third question is asked of the generated half alone. A flag whose default
    moves in the repo reaches an existing machine only through a regeneration, and
    `true` and `false` both parse perfectly — so a machine that never regenerated
    holds the old answer, and nothing but this comparison can tell it from the new
    one. A hand-edited override below the marker stays quiet for the reason
    `read_generated` records: it wins at runtime, so it is not drift, and no
    rewrite of the section above it could repair it anyway.
    """
    changes = []
    for name, expected in machine.flags.items():
        actual = observed.values.get(name)
        written = observed.generated.get(name)
        if actual is None:
            changes.append(Change(NAME, Stage.ENVIRONMENT, name, Verdict.MISSING, detail=f'would be {expected}'))
        elif actual.lower() not in envfile.TRUTHY | envfile.FALSEY:
            changes.append(Change(NAME, Stage.ENVIRONMENT, name, Verdict.STALE, detail='is neither truthy nor falsey', observed=actual))
        elif written is not None and written != expected:
            changes.append(
                Change(NAME, Stage.ENVIRONMENT, name, Verdict.STALE, detail=f'the manifest declares {expected}', observed=written)
            )
    return changes


def _requirements(machine, observed: Observed) -> list[Change]:
    """Values and files the repo declares and deliberately never contains.

    Unset, a required value expands to the empty string and quietly builds a
    wrong path at the point of use rather than failing anywhere you would look.
    A required file is restored by safekeep, so it is legitimately absent between
    an install and the restore — reported, never written.
    """
    changes = []
    for entry in machine.required_values:
        if not observed.values.get(entry.name):
            changes.append(
                Change(
                    NAME,
                    Stage.ENVIRONMENT,
                    entry.name,
                    Verdict.MISSING,
                    detail=f'not set — {entry.description or "a machine-local value"}',
                    repair=Repair.BY_HAND,
                    advice=f'set it below the marker in {observed.path}',
                )
            )
    for entry in machine.required_files:
        if entry.path not in observed.present_files:
            changes.append(
                Change(
                    NAME,
                    Stage.ENVIRONMENT,
                    entry.path,
                    Verdict.MISSING,
                    detail=f'absent — {entry.description or "a machine-local file"}',
                    repair=Repair.BY_HAND,
                    advice=entry.restore or RESTORE,
                )
            )
    return changes


def _undeclared(machine, observed: Observed) -> list[Change]:
    """Flags the shell no longer knows about.

    Not repaired, because a machine may legitimately carry a flag from a newer
    commit — but it is exactly how NVIM_AI_ENABLED survived being read by
    nothing, so it is worth naming.
    """
    return [
        Change(
            NAME,
            Stage.ENVIRONMENT,
            name,
            Verdict.UNDECLARED,
            detail='is set but flags.yml declares no such flag',
            repair=Repair.NONE,
            observed=value,
        )
        for name, value in observed.values.items()
        if name.endswith(('_ENABLED', '_DEBUG')) and name not in machine.flags
    ]


RESOURCE = EnvResource()
