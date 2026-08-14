"""`~/.env`: the machine's identity and its feature flags.

The first stage of every run, because everything below it reads the file: a
botched migration leaves a machine with a broken interactive shell independently,
as each box migrates — `.zshrc` sources `~/.env` before anything else and reads
its coordinates from nothing else.

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
from dotfiles import settings
from dotfiles.privilege import Privilege
from dotfiles.resolve import Plan
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Examined
from dotfiles.resources import Outcome
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.session import Session

NAME = 'env'

RESTORE = 'restore it with safekeep'
"""What gets a required file back, unless its entry declares otherwise."""

NOT_A_FLAG = 'is neither truthy nor falsey'
"""Said once, because the two halves of the file report it with the same words and
a different repair — see `_unparseable`."""


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

    resolved: settings.Resolved
    """Every name the register declares, answered once, from the same reading of
    config.toml that `config_problem` reports on.

    Carried rather than resolved in `diff`, for the reason `symlinks` carries
    `ownership` and `pointing_at`: `diff` is the pure half, and a rung that is a
    file on disk makes any resolution there a read. It also has to be the *same*
    reading — a repair landing between two of them produced one report that
    rejected config.toml and resolved the registry through it two rows apart.
    """

    named_files: tuple[settings.Setting, ...] = ()
    """Every shared path this tool can resolve, with whether its file is there.

    Measured in `observe` rather than derived in `diff`, because `exists` is a
    filesystem read and `diff` is the pure half.
    """

    config_problem: str = ''
    """Why this tool's own config.toml could not be read, empty when it could.

    Defaulted where `generated` is not, and for the opposite reason: empty is the
    honest reading of a machine with no config file at all, which is most of them.
    """

    @property
    def summary(self) -> str:
        return '~/.env matches the manifest and the declared flags'

    @property
    def inventory(self) -> tuple[Examined, ...]:
        """Every assignment the file makes, then the required files that are there.

        The generated half carries its value, because that value is the answer: a
        flag says whether a machine wants something running, and `MACHINE` names
        the manifest everything else derives from. The half below the marker is
        named without one: a required value is machine-local precisely because the
        repo must never hold it, and printing it on a screen somebody screenshots
        undoes that.

        Nothing here asks what drifted. `diff` decides that, and `reconcile.sift`
        drops any item it reported — so a stale flag appears once, as a finding,
        rather than once here and once there.
        """
        if not self.exists:
            return ()
        generated = tuple(Examined(key, self.generated[key]) for key in sorted(self.generated))
        below = tuple(Examined(key, 'set below the marker') for key in sorted(set(self.values) - set(self.generated)))
        files = tuple(Examined(path, 'present') for path in sorted(self.present_files))
        return generated + below + files


class EnvResource:
    name = NAME
    help = '~/.env: the machine identity and its feature flags'

    def observe(self, session: Session, plan: Plan) -> Observed:
        path = session.env_file
        config = settings.read_config()
        resolved = settings.resolve_all(
            {name for entry in plan.machine.requirements for name in entry.declared_names},
            config,
        )
        return Observed(
            path=path,
            exists=path.exists(),
            values=envfile.read(path),
            present_files=frozenset(entry.path for entry in plan.machine.required_files if entry.is_present(resolved)),
            generated=envfile.read_generated(path),
            resolved=resolved,
            named_files=settings.describe(config, path),
            config_problem=config.problem,
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
                    repair=Repair.AUTOMATIC,
                    detail='the file does not exist, so no shell knows what machine this is',
                ),
            )

        changes: list[Change] = []
        changes.extend(_identity(machine, observed))
        changes.extend(_flags(machine, observed))
        changes.extend(_config(observed))
        changes.extend(_named_files(machine, observed))
        changes.extend(_unexported(machine, observed))
        changes.extend(_requirements(machine, observed))
        changes.extend(_orphaned(machine, observed))
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
    """What machine this is.

    `MACHINE` is identity rather than configuration: it selects the manifest every
    coordinate, package list and flag is derived from, so a machine holding the
    wrong one is a machine converging on somebody else's declaration, not a
    preference that drifted. That is the whole of why an override below the marker
    is named here and stays silent in `_flags` — the marker exists to let a machine
    hold a preference of its own, and an identity is not a preference.

    Which half disagrees decides who can repair it. A generated value that no
    longer matches the manifest is one rewrite away and `apply` makes it. An
    override below the marker is the last assignment in the file, so the shell
    takes it whatever the section above says: `apply` owns only the section above,
    so offering it as repairable buys a `check` that finds it, an `apply` that
    reports DONE, a fresh `.env.bak` over the last one, and a machine that has not
    moved.
    """
    expected_values = {'MACHINE': machine.name, **envfile.coordinate_exports(machine)}

    changes = []
    for key, expected in expected_values.items():
        actual = observed.values.get(key)
        written = observed.generated.get(key)
        if actual is None:
            changes.append(
                Change(
                    NAME,
                    Stage.ENVIRONMENT,
                    key,
                    Verdict.MISSING,
                    repair=Repair.AUTOMATIC,
                    detail=f'the manifest declares {expected}',
                )
            )
        elif written is not None and written != expected:
            changes.append(
                Change(
                    NAME,
                    Stage.ENVIRONMENT,
                    key,
                    Verdict.STALE,
                    repair=Repair.AUTOMATIC,
                    detail=f'the manifest declares {expected}',
                    observed=written,
                )
            )
        elif actual != expected:
            changes.append(
                Change(
                    NAME,
                    Stage.ENVIRONMENT,
                    key,
                    Verdict.STALE,
                    repair=Repair.BY_HAND,
                    detail=f'the manifest declares {expected}, and an assignment below the marker overrides it',
                    observed=actual,
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

    The second question asks the same thing of the same file and has to answer who
    can repair it, which is `_identity`'s split three functions above. A value the
    shell cannot read is drift wherever it was written, but only the generated half
    is `apply`'s to rewrite: an unparseable assignment below the marker is still
    the last one in the file, so offering it as repairable buys a `check` that
    finds it, an `apply` that reports DONE, a fresh `.env.bak` over the last one,
    and a machine that has not moved.
    """
    changes = []
    for name, expected in machine.flags.items():
        actual = observed.values.get(name)
        written = observed.generated.get(name)
        if actual is None:
            changes.append(Change(NAME, Stage.ENVIRONMENT, name, Verdict.MISSING, repair=Repair.AUTOMATIC, detail=f'would be {expected}'))
        elif actual.lower() not in envfile.TRUTHY | envfile.FALSEY:
            changes.append(_unparseable(name, actual, generated=written == actual, path=observed.path))
        elif written is not None and written != expected:
            changes.append(
                Change(
                    NAME,
                    Stage.ENVIRONMENT,
                    name,
                    Verdict.STALE,
                    repair=Repair.AUTOMATIC,
                    detail=f'the manifest declares {expected}',
                    observed=written,
                )
            )
    return changes


def _unparseable(name: str, actual: str, generated: bool, path: Path) -> Change:
    """A flag holding a value no shell reads as true or false, addressed to whoever
    owns the half it was written in."""
    if generated:
        return Change(NAME, Stage.ENVIRONMENT, name, Verdict.STALE, repair=Repair.AUTOMATIC, detail=NOT_A_FLAG, observed=actual)
    return Change(
        NAME,
        Stage.ENVIRONMENT,
        name,
        Verdict.STALE,
        repair=Repair.BY_HAND,
        detail=f'{NOT_A_FLAG}, and an assignment below the marker sets it',
        observed=actual,
        advice=f'drop that assignment from {path}, or give it a value `flag_enabled` reads',
    )


def _config(observed: Observed) -> list[Change]:
    """This tool's own config.toml, when it exists and cannot be parsed.

    Reported before the register below it, because it is the reason every entry
    the file was supposed to answer is about to report missing. Without this the
    machine gets N findings naming the values and none naming the broken file
    that lost them, and the advice on each is to write the answer somewhere it
    already is.
    """
    if not observed.config_problem:
        return []
    return [
        Change(
            NAME,
            Stage.ENVIRONMENT,
            str(settings.config_file()),
            Verdict.STALE,
            repair=Repair.BY_HAND,
            detail=f'cannot be read, so it answers nothing — {observed.config_problem}',
            advice='fix the TOML, or delete the file to fall back to ~/.env alone',
        )
    ]


def _unexported(machine, observed: Observed) -> list[Change]:
    """A required value the config answers that the generated half does not carry.

    Fires on the file rather than on the resolution: a resolved name satisfies
    this resource while every consumer reading the environment still finds
    nothing.
    """
    return [
        Change(
            NAME,
            Stage.ENVIRONMENT,
            entry.name,
            Verdict.STALE,
            repair=Repair.AUTOMATIC,
            detail=f'{found.source} answers it and the generated section does not export it',
            observed=observed.generated.get(entry.name, ''),
        )
        for entry in machine.required_values
        if (found := observed.resolved.of(entry.name)) and observed.generated.get(entry.name) != found.exported
    ]


def _named_files(machine, observed: Observed) -> list[Change]:
    """A shared path this tool resolved, whose file is not there.

    Resolving a name is not finding what it names, and a default is only safe
    because this fires. `required_values` covers the names a machine answers
    itself; this covers the rest of `SHARED_PATHS`.
    """
    declared = {entry.name for entry in machine.required_values}
    return [
        Change(
            NAME,
            Stage.ENVIRONMENT,
            setting.name,
            Verdict.STALE,
            repair=Repair.BY_HAND,
            detail='names a file that is not there',
            advice='point it at the real file, or put the file where it already points',
            observed=setting.value,
            source=setting.source,
        )
        for setting in observed.named_files
        if setting.value and not setting.exists and setting.name not in declared
    ]


def _requirements(machine, observed: Observed) -> list[Change]:
    """Values and files the repo declares and deliberately never contains.

    Unset, a required value expands to the empty string and quietly builds a
    wrong path at the point of use rather than failing anywhere you would look.
    A required file is restored by safekeep, so it is legitimately absent between
    an install and the restore — reported, never written.

    A missing file gets one of two findings, and conflating them is what made the
    scheduled check's advice wrong. *Nothing names its location* is a machine that
    never answered, and the remedy is to answer; *absent at a named path* is a
    machine that answered and has no file there, and the remedy is a restore. Only
    the second is what safekeep can fix. The two share a verdict, so `source` is
    what separates them for anything but a reader — set on the second and empty on
    the first, since a rung is exactly what the first one lacks.
    """
    changes = []
    for entry in machine.required_values:
        answer = observed.values.get(entry.name) or (found.value if (found := observed.resolved.of(entry.name)) else '')
        if not answer:
            changes.append(
                Change(
                    NAME,
                    Stage.ENVIRONMENT,
                    entry.name,
                    Verdict.MISSING,
                    repair=Repair.BY_HAND,
                    detail=f'not set — {entry.description or "a machine-local value"}',
                    advice=settings.where_to_name(entry.name, observed.path),
                )
            )
            continue
        # The value arrived and the file it names did not. Two findings rather
        # than one, because the remedies are opposite: the first is answered in
        # ~/.env and this one is answered wherever the file comes from.
        # Through the same expander the required_files half uses, so a `~` and a
        # `$HOME` in one register cannot resolve to different answers.
        if entry.file_must_exist and not Path(observed.resolved.expand(answer)).exists():
            changes.append(
                Change(
                    NAME,
                    Stage.ENVIRONMENT,
                    entry.name,
                    Verdict.STALE,
                    repair=Repair.BY_HAND,
                    detail=f'names a file that is not there — {entry.description or "a machine-local value"}',
                    advice='point it at the real file, or put the file where it already points',
                    observed=answer,
                )
            )
    for entry in machine.required_files:
        if entry.path in observed.present_files:
            changes.extend(_unready(entry, machine, observed))
            continue
        description = entry.description or 'a machine-local file'
        if unnamed := observed.resolved.unresolved(entry.path):
            changes.append(
                Change(
                    NAME,
                    Stage.ENVIRONMENT,
                    entry.path,
                    Verdict.MISSING,
                    repair=Repair.BY_HAND,
                    detail=f'nothing names its location — {description}',
                    advice=settings.where_to_name(unnamed[0], observed.path),
                )
            )
            continue
        # Carried only where a variable chose the path. An entry naming a literal
        # one reads worse with its own `~` expanded back at it, and there is no
        # rung to attribute it to.
        source = observed.resolved.source(entry.path)
        changes.append(
            Change(
                NAME,
                Stage.ENVIRONMENT,
                entry.path,
                Verdict.MISSING,
                repair=Repair.BY_HAND,
                detail=f'absent — {description}',
                advice=entry.restore or RESTORE,
                observed=entry.resolved_path(observed.resolved) if source else '',
                source=source,
            )
        )
    return changes


def _unready(entry, machine, observed: Observed) -> list[Change]:
    """A required file that is there and cannot do its job.

    Presence is not readiness, and the gap reads as success: measuring presence
    alone reports converged on a machine where the file exists and the value its
    contents read was never set. That is the one state the whole register exists
    to make loud, and it was the one state it was silent in.

    `STALE` rather than `MISSING`, because the file is present and something about
    it is wrong — the two verdicts send a reader to different halves, and a
    restore is the wrong remedy here.

    Only preconditions this machine declares. A name absent from its own register
    does not apply rather than failing: `local.sh` is required on both halves of
    the work laptop, and only the WSL half declares `WINDOWS_USER`.
    """
    declared = {value.name for value in machine.required_values}
    unmet = [name for name in entry.requires_values if name in declared and not (observed.values.get(name) or observed.resolved.of(name))]
    if not unmet:
        return []
    return [
        Change(
            NAME,
            Stage.ENVIRONMENT,
            entry.path,
            Verdict.STALE,
            repair=Repair.BY_HAND,
            detail=f'present, and reads {", ".join(unmet)} which nothing sets',
            advice=settings.where_to_name(unmet[0], observed.path),
        )
    ]


def _orphaned(machine, observed: Observed) -> list[Change]:
    """Generated lines the declaration no longer writes.

    Repairable, unlike `_undeclared`, and that is the whole difference between
    them. `apply` rebuilds the managed section from `render`, so an orphan is one
    rewrite from gone.

    The two also read different halves and ask different questions. `_undeclared`
    asks the hand-set half whether a name *looks* like a flag, which is a
    convention and sees nothing spelled otherwise. This asks the generated half
    whether the declaration still produces the name at all, so a variable named
    unusually cannot slip past.
    """
    # A required value belongs to the declaration exactly while a rung answers it.
    answered = {entry.name for entry in machine.required_values if observed.resolved.of(entry.name)}
    declared = {'MACHINE', *envfile.coordinate_exports(machine), *machine.flags, *answered}
    return [
        Change(
            NAME,
            Stage.ENVIRONMENT,
            name,
            Verdict.STALE,
            repair=Repair.AUTOMATIC,
            detail='this machine no longer declares it, so a regeneration drops it',
            observed=value,
        )
        for name, value in sorted(observed.generated.items())
        if name not in declared
    ]


def _undeclared(machine, observed: Observed) -> list[Change]:
    """Hand-set flags the declaration does not know about.

    Below the marker only, which is the same split `Observed.inventory` makes and
    the reason each name carries one verdict. The two checkers read overlapping
    halves of one file otherwise, and a flag-shaped name in the generated section
    matches both: `apply` would remove it and `check` would send a person after
    it. `ENV_STATES` states the invariant that breaks — a state is drift, or it
    is a finding, and no state is both — and nothing downstream would catch it,
    because `sift` classifies every change independently and never asks whether a
    key appeared twice.

    Not repaired, because a machine may legitimately carry a flag from a newer
    commit, and because `apply` owns only the section above the marker anyway. It
    is exactly how NVIM_AI_ENABLED survived being read by nothing, so it is worth
    naming.
    """
    hand_set = set(observed.values) - set(observed.generated)
    return [
        Change(
            NAME,
            Stage.ENVIRONMENT,
            name,
            Verdict.UNDECLARED,
            repair=Repair.NONE,
            detail='is set but flags.yml declares no such flag',
            observed=observed.values[name],
        )
        for name in sorted(hand_set)
        if name.endswith(('_ENABLED', '_DEBUG')) and name not in machine.flags
    ]


RESOURCE = EnvResource()
