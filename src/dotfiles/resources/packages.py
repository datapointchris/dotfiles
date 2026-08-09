"""Everything installed from a registry or a release: the tools.

What the machine *should* have is `resolve.py`, and whether it has it is
`evidence.py`. What is left here is the resource: which of the plan's items are
this one's, and what a difference means.

`perform` is provider by provider, and two have moved: `ghrelease` and `custom`
install through `providers/`, which is also what the phase registry now calls, so
the two front doors cannot install one tool differently. The rest still run
through the phase registry in `apply.py`, which knows the PATH each one needs and
the order they have to happen in.

This is the only path that acts on `STALE`. The phase registry installs what is
absent, because that is all a phase knows; a tool that is present but behind is a
verdict `check` measured against the release cache, and repairing it needs the
Change that carries it.
"""

from __future__ import annotations

import dataclasses as dc
import datetime as dt
from collections.abc import Callable

from dotfiles import catalog
from dotfiles import coordinates
from dotfiles import evidence as ev
from dotfiles import releases
from dotfiles import versions
from dotfiles.privilege import Privilege
from dotfiles.providers import custom
from dotfiles.providers import ghrelease
from dotfiles.resolve import DesiredItem
from dotfiles.resolve import Plan
from dotfiles.resolve import Precondition
from dotfiles.resources import Change
from dotfiles.resources import Outcome
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.session import Session

NAME = 'packages'

CURRENCY_PROVIDER = 'ghrelease'
"""The one provider whose items are checked for currency.

A release is pulled from a tag this repo names, so "what should be installed" is
a question with an upstream answer. Everything else here defers to a registry
that upgrades on its own schedule — asking apt or npm whether a package is the
newest one is asking a question the machine's own manager already owns.
"""


@dc.dataclass(frozen=True, slots=True)
class Observed:
    evidence: dict[str, ev.Evidence]
    have_github_credentials: bool
    reported: dict[str, str] = dc.field(default_factory=dict)
    """Address → the version string an installed release binary printed."""

    latest: dict[str, releases.Cached] = dc.field(default_factory=dict)
    """Cache key → the newest upstream release, for entries still inside the TTL."""

    consulted_network: bool = False

    @property
    def summary(self) -> str:
        """What the row says when nothing drifted.

        Lives here rather than in the walk because it is a sentence about *this*
        observation: the walk reaching into `evidence` to count it is the walk
        knowing a field it has no other reason to know.
        """
        return f'all {len(self.evidence)} declared packages are installed'


class PackagesResource:
    name = NAME
    help = 'everything installed from a package manager or a release'

    def observe(self, session: Session, plan: Plan) -> Observed:
        mine = plan.for_resource(NAME)
        installed = ev.inventories(mine)
        evidence = {item.address: ev.evidence_for(item, installed) for item in mine}

        present = tuple(item for item in mine if evidence[item.address].verdict is Verdict.MATCHED and _has_currency(item))
        latest, consulted = _upstream(session, present)

        return Observed(
            evidence=evidence,
            have_github_credentials=ev.have_github_credentials(),
            reported={item.address: found for item in present if (found := ev.reported_version(item.executable))},
            latest=latest,
            consulted_network=consulted,
        )

    def diff(self, plan: Plan, observed: Observed) -> tuple[Change, ...]:
        changes = []
        for item in plan.for_resource(NAME):
            evidence = observed.evidence[item.address]
            if evidence.verdict is not Verdict.MATCHED:
                changes.append(
                    Change(
                        NAME,
                        item.stage,
                        item.address,
                        evidence.verdict,
                        detail=evidence.detail,
                        repair=repair_for(item, evidence, observed.have_github_credentials),
                        desired=item,
                    )
                )
            elif _has_currency(item):
                changes.extend(currency_of(item, observed))
        return tuple(changes)

    def perform(self, session: Session, change: Change, privilege: Privilege) -> Outcome:
        """Two providers have moved; the rest still run through the phase registry.

        Refused rather than silently skipped for the ones that have not, because a
        resource that did nothing quietly would leave `apply` reporting a converged
        machine.
        """
        item = change.desired
        installer = PERFORMED.get(item.provider) if item else None
        if item is None or installer is None:
            return Outcome(change, OutcomeStatus.REFUSED, "run 'dotfiles packages apply', which still drives the phase registry")
        return installer(session, change, item)


def _arrived(session: Session, change: Change, item: DesiredItem) -> Outcome | None:
    """The item installed itself between `observe` and here, so leave it alone.

    Not defensive padding. `observe` ran before the report was printed and before
    anything upstream in the stage order installed a toolchain, so a MISSING item
    may have arrived since — and installing over it would replace a binary nobody
    asked about with whatever upstream calls latest now. A STALE one is
    deliberately *not* re-checked this way: being behind is what this repairs.
    """
    if change.verdict is Verdict.MISSING and ev.evidence_for(item, {}).verdict is Verdict.MATCHED:
        return Outcome(change, OutcomeStatus.SKIPPED, f'{item.executable} arrived before this ran')
    return None


def _install_custom(session: Session, change: Change, item: DesiredItem) -> Outcome:
    """One vendor that ships itself, through the same function the phase calls."""
    entry = item.entry
    if not isinstance(entry, catalog.CustomInstaller):
        return Outcome(change, OutcomeStatus.REFUSED, f'{item.name} is not a custom_installers entry')

    if arrived := _arrived(session, change, item):
        return arrived

    result = custom.install(entry, coordinates.target_for(session.machine.coordinates), offline=session.offline)
    return Outcome(change, OutcomeStatus.DONE if result.ok else OutcomeStatus.FAILED, result.detail)


def _install_release(session: Session, change: Change, item: DesiredItem) -> Outcome:
    """Install or upgrade one release, through the same engine the phase calls."""
    entry = item.entry
    if not isinstance(entry, catalog.GithubRelease):
        return Outcome(change, OutcomeStatus.REFUSED, f'{item.name} is not a github_releases entry')

    if arrived := _arrived(session, change, item):
        return arrived

    result = ghrelease.install(entry, coordinates.target_for(session.machine.coordinates), offline=session.offline)
    return Outcome(change, OutcomeStatus.DONE if result.ok else OutcomeStatus.FAILED, result.detail)


PERFORMED: dict[str, Callable[[Session, Change, DesiredItem], Outcome]] = {
    CURRENCY_PROVIDER: _install_release,
    'custom': _install_custom,
}
"""Which providers this resource can repair itself, rather than deferring to a phase.

The list shrinks the phase registry as it grows: a provider here is one whose
install is a function this package owns, and `apply` reaching it through a phase
and `check --fix` reaching it through a Change end up in the same code.
"""


def repair_for(item: DesiredItem, evidence: ev.Evidence, credentials: bool) -> Repair:
    """Whether `apply` could do anything about this.

    A private repo without credentials cannot be installed here: attempting it
    records a failure for something the machine was never able to have, and the
    run exits non-zero for a reason no change to this repo can fix. Warned rather
    than silent, because a `gh` login is state a machine can lose.

    An unmeasurable item is nobody's to repair either — there is no verdict to act
    on, only one to report.
    """
    if evidence.verdict is Verdict.UNKNOWN:
        return Repair.NONE
    if item.precondition is Precondition.GITHUB_AUTH and not credentials:
        return Repair.BY_HAND
    return Repair.AUTOMATIC


def _has_currency(item: DesiredItem) -> bool:
    return item.provider == CURRENCY_PROVIDER


def _wanted(item: DesiredItem) -> releases.Wanted:
    prefix = item.entry.release_tag_prefix if isinstance(item.entry, catalog.GithubRelease) else ''
    repo = item.entry.repo if isinstance(item.entry, catalog.GithubRelease) else ''
    return releases.Wanted(repo=repo, tag_prefix=prefix)


def _upstream(session: Session, present: tuple[DesiredItem, ...]) -> tuple[dict[str, releases.Cached], bool]:
    """The cached upstream versions, refreshed only when this run is allowed to.

    Offline never asks, whatever `--refresh` says: the flag means "spend the
    network on being current", and there is no network to spend. It reports
    `UNKNOWN` from the cache it has, which is the honest answer rather than a
    failure.
    """
    entries = releases.load()
    if not session.refresh or session.offline or not present:
        return entries, False

    now = dt.datetime.now(dt.UTC)
    entries = releases.refresh(tuple({_wanted(item) for item in present}), entries, now)
    releases.save(entries)
    return entries, True


def currency_of(item: DesiredItem, observed: Observed) -> tuple[Change, ...]:
    """Whether an installed release is the version this repo says it should be.

    Two different questions wearing one verb. A `version:` pin is answerable with
    no network at all — the declaration names the release — so a pinned tool stays
    checkable on a machine that has never reached GitHub. Everything else means
    "latest", and latest is a fact only upstream holds.

    An answer that could not be measured is `UNKNOWN` with the reason, never a
    quiet `MATCHED`: a tool nobody could ask about is not a tool known to be
    current, and the whole point of the cache is that it is allowed to be out of
    date without being allowed to lie.
    """
    reported = observed.reported.get(item.address)
    if reported is None:
        return (
            Change(
                NAME,
                item.stage,
                item.address,
                Verdict.UNKNOWN,
                detail=f'{item.executable} is installed but would not report a version',
                repair=Repair.NONE,
                desired=item,
            ),
        )

    pinned = item.entry.version if isinstance(item.entry, catalog.GithubRelease) else ''
    if pinned:
        return _compared(item, reported, pinned, versions.exactly(reported, pinned), f'pinned to {pinned}')

    cached = releases.current(_wanted(item), observed.latest, dt.datetime.now(dt.UTC))
    if cached is None:
        reason = 'offline, so upstream could not be asked' if observed.consulted_network is False else 'upstream did not answer'
        return (
            Change(
                NAME,
                item.stage,
                item.address,
                Verdict.UNKNOWN,
                detail=f'no cached release for {_wanted(item).repo} within the TTL ({reason}); check --refresh to measure',
                repair=Repair.NONE,
                desired=item,
                observed=reported,
            ),
        )

    return _compared(item, reported, cached.version, versions.at_least(reported, cached.version), f'{cached.version} is the latest release')


def _compared(item: DesiredItem, reported: str, wanted: str, verdict: bool | None, because: str) -> tuple[Change, ...]:
    """One comparison's outcome, with `None` kept distinct from `False`.

    An unparseable version is not an old one. Reporting it as behind would send
    `apply` to reinstall a tool nothing established was wrong, which is the guess
    `Verdict.UNKNOWN` exists to refuse.
    """
    if verdict is None:
        return (
            Change(
                NAME,
                item.stage,
                item.address,
                Verdict.UNKNOWN,
                detail=f'{because}, and {reported!r} has no version in it',
                repair=Repair.NONE,
                desired=item,
                observed=reported,
            ),
        )
    if verdict:
        return ()
    return (
        Change(
            NAME,
            item.stage,
            item.address,
            Verdict.STALE,
            detail=because,
            desired=item,
            observed=reported,
        ),
    )


RESOURCE = PackagesResource()
