"""Everything installed from a registry or a release: the tools.

What the machine *should* have is `resolve.py`, and whether it has it is
`evidence.py`. What is left here is the resource: which of the plan's items are
this one's, and what a difference means.

`perform` is provider by provider, and there is one path through it: every
provider installs through `providers/`, in the order `Stage` declares, so the noun
form and the composite verb cannot install one tool differently. The PATH each
provider needs is `providers/toolchain.put_on_path`, called as each runtime lands
rather than assembled by whatever drives the run.

Acting on `STALE` is what the `Change` buys. "Behind" is a verdict measured
against the release cache, so repairing it needs the item that carries the
verdict — which is why a layer that returns a bool can only ever install what is
absent.
"""

from __future__ import annotations

import dataclasses as dc
import datetime as dt
from pathlib import Path

from dotfiles import catalog
from dotfiles import evidence as ev
from dotfiles import registry
from dotfiles import releases
from dotfiles import versions
from dotfiles.privilege import Privilege
from dotfiles.providers import ghrelease
from dotfiles.providers import syspkg
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

`CustomInstaller` belongs with them because a vendor that ships its own installer
still publishes releases somewhere, and the entry names where: the repo is a
declarative fact even when the bytes come from an S3 bucket or a HashiCorp mirror.
The engine acts on verdicts, so a section with no verdict for "behind" is a section
that silently never upgrades.

Which entries cannot be asked is `_has_currency`'s answer rather than a list here —
an entry naming no repo, reporting no version, or installing no binary drops out
there, and `dotfiles machines show --json` is what enumerates them.
"""


@dc.dataclass(frozen=True, slots=True)
class Observed:
    evidence: dict[str, ev.Evidence]
    met: Preconditions
    """Which declared preconditions this machine meets, measured once for the walk."""

    reported: dict[str, str] = dc.field(default_factory=dict)
    """Address → the version string an installed release binary printed."""

    shadowed: dict[str, tuple[str, ...]] = dc.field(default_factory=dict)
    """Address → the copies of its binary that nothing this machine declares explains.

    Only populated for an item that has more than one copy on PATH, so the common
    case carries an empty dict and costs nothing to fold.
    """

    latest: dict[str, releases.Cached] = dc.field(default_factory=dict)
    """Cache key → the newest upstream release, for entries still inside the TTL."""

    consulted_network: bool = False

    from_bundle: bool = False
    """Whether `latest` came from a staged bundle rather than the release cache.

    Carried so an unanswerable row can say which upstream had nothing to say. The
    two are different findings on a machine that cannot reach GitHub: a cache with
    no entry means nobody has asked, while a bundle with no row for a tool means
    the bundle does not carry it and never will until a newer one is built.
    """

    reinstall: frozenset[str] = frozenset()
    """Entry names this run was told to install again whatever their state.

    A session fact carried into the observation because `diff` is handed the plan
    and the observation and nothing else — the same route `from_bundle` takes. It
    is the one input here that is not a measurement, which is why it produces a
    Change with its own detail rather than being folded into a verdict.
    """

    @property
    def measured_upstream(self) -> bool:
        """Whether `latest` was established this run rather than read from a cache.

        A refresh asked GitHub just now and a staged bundle holds the bytes a
        fresh install would use; both are current by construction. The plain cache
        read is the one that is *allowed* to be behind reality, and that is the
        whole of the difference — it decides whether an installed version newer
        than `latest` is drift or just an answer nobody has refreshed.
        """
        return self.consulted_network or self.from_bundle

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
            shadowed=_shadowing(mine, evidence, plan, session.repo),
            latest=latest,
            consulted_network=consulted,
            from_bundle=session.offline,
            reinstall=session.reinstall,
        )

    def diff(self, plan: Plan, observed: Observed) -> tuple[Change, ...]:
        """An installed item is left alone unless something says otherwise, and
        `--reinstall` is that something even when nothing was measurable.

        It is checked ahead of currency rather than after, because the tools worth
        naming are the ones currency cannot speak for: a half-written binary, a
        version string nobody can parse, an entry whose section is not asked about
        upstream at all. Running the comparison first would answer "current" and
        drop the item the caller explicitly asked for.
        """
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
            elif item.name in observed.reinstall:
                changes.append(
                    Change(
                        NAME,
                        item.stage,
                        item.address,
                        Verdict.STALE,
                        detail='named by --reinstall, so it is installed again whatever it reports',
                        repair=repair_for(item, Verdict.STALE, observed.met),
                        desired=item,
                        observed=observed.reported.get(item.address, ''),
                    )
                )
            elif _has_currency(item):
                changes.extend(currency_of(item, observed))

            if stray := observed.shadowed.get(item.address):
                changes.append(
                    Change(
                        NAME,
                        item.stage,
                        item.address,
                        Verdict.UNDECLARED,
                        detail=f'{item.executable} runs from {observed.evidence[item.address].detail}; nothing declares the other copy',
                        repair=Repair.BY_HAND,
                        desired=item,
                        observed=', '.join(stray),
                    )
                )
        return tuple(changes)

    def perform(self, session: Session, change: Change, privilege: Privilege) -> Outcome:
        """Whichever provider planned it repairs it, or says why it cannot."""
        return registry.install(session, change, privilege)


def _shadowing(
    mine: tuple[DesiredItem, ...],
    evidence: dict[str, ev.Evidence],
    plan: Plan,
    checkout: Path,
) -> dict[str, tuple[str, ...]]:
    """Which declared tools have a copy on PATH that nothing declared put there.

    Two copies of one binary means the one that runs is decided by PATH order
    rather than by the declaration, and the loser is invisible: `apply` installs,
    `evidence` finds *a* binary, and every verb reports the machine converged
    while the tool anyone actually runs came from somewhere else.

    **A second copy is not by itself a finding**, which is the whole difficulty
    and why the shell script this replaces reported nine things on a healthy
    machine. Three explanations are legitimate, and none of them is a list here:

    - the copy this item's own evidence names — whatever the provider installed;
    - a copy an OS package manager attributes to a package *this manifest
      declares*. fnm owns node and npm while pacman's `nodejs` ships `/usr/bin/node`
      underneath it, and that second copy is the bootstrap npm the declaration asks
      for;
    - a copy owned by a package the manager installed to satisfy something else.
      Nobody chose it, so nobody can be told to remove it: yay needs a compiler,
      so pacman's Go sits under the tarball's on every machine that builds an AUR
      package.

    What is left over is a stray somebody installed by hand and then declared
    through another mechanism — `shellcheck` from pacman beside the release
    binary. `Repair.BY_HAND` because removing one is a judgement about which: the
    declaration says what should be there and cannot say what else is safe to
    uninstall.
    """
    index = ev.executables_on_path(checkout)
    declared: set[str] = set()
    for item in plan.items:
        if isinstance(item.entry, catalog.SystemPackage):
            declared.update(filter(None, (item.entry.package_for(installer) for installer in syspkg.OWNER)))

    candidates = [item for item in mine if item.executable and len(index.get(item.executable, ())) > 1]
    explained = declared | (syspkg.unchosen() if candidates else frozenset())

    shadowed = {}
    for item in candidates:
        if evidence[item.address].verdict is not Verdict.MATCHED:
            continue
        stray = tuple(
            path for path in index[item.executable] if path != evidence[item.address].detail and syspkg.owner_of(path) not in explained
        )
        if stray:
            shadowed[item.address] = stray
    return shadowed


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
        from_tags = entry.version_source == catalog.VERSION_FROM_TAGS
        return releases.Wanted(repo=entry.repo, tag_prefix=entry.release_tag_prefix, from_tags=from_tags)
    if isinstance(entry, catalog.GoTool | catalog.CargoPackage):
        return releases.Wanted(repo=entry.github_repo)
    return releases.Wanted(repo='')


def _upstream(session: Session, present: tuple[DesiredItem, ...]) -> tuple[dict[str, releases.Cached], bool]:
    """What each present tool should be at, from whichever upstream this run has.

    Offline never asks GitHub, whatever `--refresh` says: the flag means "spend the
    network on being current", and there is no network to spend.

    **Offline, the bundle is the upstream.** It has to be: the release cache is
    empty on a machine that has never reached GitHub, so reading it there answers
    `UNKNOWN` for every installed tool and leaves nothing repairable — a newer
    bundle extracted onto a built machine would upgrade nothing at all. The bundle
    records a version per staged file, which is the same fact `resolve_tag` reads to
    name a tag with no network.
    """
    if session.offline:
        return _staged(present), False

    entries = releases.load()
    if not session.refresh or not present:
        return entries, False

    now = dt.datetime.now(dt.UTC)
    entries = releases.refresh(tuple({_wanted(item) for item in present}), entries, now)
    releases.save(entries)
    return entries, True


def _staged(present: tuple[DesiredItem, ...]) -> dict[str, releases.Cached]:
    """What a staged bundle holds for each present tool, keyed as the cache is.

    Stamped now rather than with the bundle's build date, because the TTL is about
    how stale an *answer* is and this answer cannot go stale: what the bundle
    carries is what the bundle carries until a newer one is extracted.

    Deliberately not written back through `releases.save`. These versions are what
    one tarball happens to hold, not what upstream published, and persisting them
    would have the next online run read a bundle's contents as the release cache.
    """
    now = dt.datetime.now(dt.UTC)
    found = {}
    for item in present:
        version = ghrelease.bundle_version(item.name)
        if version:
            found[_wanted(item).key] = releases.Cached(version=version, checked=now)
    return found


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

    **Ahead of the newest release is drift, but only against a figure measured
    this run.** A version nothing upstream publishes is not current — it is a
    machine holding bytes no declaration can reproduce, which is what a repo that
    re-versioned downwards leaves behind: `ifiles` went to 2.10 and back to 1.x,
    and `at_least` read the stranded 2.10 as comfortably current forever while it
    kept serving `get`/`put` against an API that had moved to `upload`/`download`.
    Gated on `measured_upstream` because the same comparison against a *cached*
    figure means the opposite — the tool self-updated and the cache has not caught
    up, which is the cache being behind rather than the tool being wrong.
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
        return (
            Change(
                NAME,
                item.stage,
                item.address,
                Verdict.UNKNOWN,
                detail=_unmeasurable(item, observed),
                repair=Repair.NONE,
                desired=item,
                observed=reported,
            ),
        )

    if observed.measured_upstream and versions.exceeds(reported, cached.version):
        return (
            Change(
                NAME,
                item.stage,
                item.address,
                Verdict.STALE,
                detail=f'ahead of {cached.version}, which is the newest release and what a fresh install produces',
                desired=item,
                observed=reported,
            ),
        )

    return _compared(item, reported, cached.version, versions.at_least(reported, cached.version), f'{cached.version} is the latest release')


def _unmeasurable(item: DesiredItem, observed: Observed) -> str:
    """Why nothing can say whether this one is current, in the terms of the upstream
    that was asked. A bundle carrying no row for a tool and a cache nobody has
    filled are different problems with different fixes."""
    if observed.from_bundle:
        return f'the staged bundle carries no version for {item.name}, so an offline run has nothing to compare against'
    reason = 'not refreshed this run' if not observed.consulted_network else 'upstream did not answer'
    return f'no cached release for {_wanted(item).repo} within the TTL ({reason}); check --refresh to measure'


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
