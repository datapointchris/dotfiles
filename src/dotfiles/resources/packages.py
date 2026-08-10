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

from dotfiles import catalog
from dotfiles import evidence as ev
from dotfiles import registry
from dotfiles import releases
from dotfiles import versions
from dotfiles.privilege import Privilege
from dotfiles.resolve import DesiredItem
from dotfiles.resolve import Plan
from dotfiles.resolve import Preconditions
from dotfiles.resources import Change
from dotfiles.resources import Outcome
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.resources import repair_for
from dotfiles.session import Session

NAME = 'packages'

CURRENCY = (catalog.GithubRelease, catalog.GoTool, catalog.CargoPackage, catalog.CustomInstaller)
"""The entries whose currency is a question with an upstream answer.

All four install from a repo this declaration names, so "what should be
installed" is decided by a tag rather than by anyone else's schedule. `go install
@latest` and `cargo binstall` are not exceptions to that — they *are* the upgrade,
because nothing sits underneath a Go tool or a Rust CLI deciding when it moves.

Everything else here defers to a registry that upgrades on its own: asking apt or
npm whether a package is the newest one is asking a question the machine's own
manager already owns.

`CustomInstaller` is here because the alternative was the install phase running
every vendor's installer on every apply and letting each decide internally whether
it was already current — `terraform-ls`, `bats` and `mount-s3` each held their own
copy of this comparison. That is an unconditional re-run standing in for a
measurement, and it stops working the moment those rows converge through the
engine, which only ever acts on a verdict. The four with no repo to ask —
`awscli`, `claude-code` — fall out through `_has_currency` rather than being named
here, and are the entries `check` honestly cannot answer for.
"""


@dc.dataclass(frozen=True, slots=True)
class Observed:
    evidence: dict[str, ev.Evidence]
    met: Preconditions
    """Which declared preconditions this machine meets, measured once for the walk."""

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
        evidence = {item.address: registry.evidence_for(item, session.inventories) for item in mine}

        present = tuple(item for item in mine if evidence[item.address].verdict is Verdict.MATCHED and _has_currency(item))
        latest, consulted = _upstream(session, present)

        return Observed(
            evidence=evidence,
            met=ev.measured_preconditions(),
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
                        repair=repair_for(item, evidence.verdict, observed.met),
                        desired=item,
                    )
                )
            elif _has_currency(item):
                changes.extend(currency_of(item, observed))
        return tuple(changes)

    def perform(self, session: Session, change: Change, privilege: Privilege) -> Outcome:
        """Whichever provider planned it repairs it, or says why it cannot."""
        return registry.install(session, change, privilege)


def _has_currency(item: DesiredItem) -> bool:
    """Whether this item can be compared against an upstream at all.

    Every clause has to hold, and an entry failing one is not a finding — it is a
    question nobody can answer, and an UNKNOWN row on every plan is noise. A Go
    tool declared by module path alone names no repo to consult. A GUI names one
    and still cannot be asked: probing `webviewrs` opened a window and blocked the
    plan on its event loop, which is what `reports_version` exists to declare. And
    something that installs no binary has nothing to ask — `bashselfupdate` is a
    sourced library found by its `installed_path`, so it names a repo and still has
    no version to report.
    """
    return isinstance(item.entry, CURRENCY) and item.entry.reports_version and bool(item.executable) and bool(_wanted(item).repo)


def _wanted(item: DesiredItem) -> releases.Wanted:
    entry = item.entry
    if isinstance(entry, catalog.GithubRelease | catalog.CustomInstaller):
        return releases.Wanted(repo=entry.repo, tag_prefix=entry.release_tag_prefix)
    if isinstance(entry, catalog.GoTool | catalog.CargoPackage):
        return releases.Wanted(repo=entry.github_repo)
    return releases.Wanted(repo='')


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
