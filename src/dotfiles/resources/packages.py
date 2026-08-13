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
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
from pathlib import Path

from dotfiles import catalog
from dotfiles import diagnose
from dotfiles import evidence as ev
from dotfiles import logging
from dotfiles import registry
from dotfiles import releases
from dotfiles import versions
from dotfiles.coordinates import PackageManager
from dotfiles.privilege import Privilege
from dotfiles.providers import ghrelease
from dotfiles.providers import gotool
from dotfiles.providers import syspkg
from dotfiles.resolve import DesiredItem
from dotfiles.resolve import Plan
from dotfiles.resolve import Preconditions
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Examined
from dotfiles.resources import Outcome
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.resources import advice_for
from dotfiles.resources import repair_for
from dotfiles.session import Session

NAME = 'packages'

log = logging.get_logger(NAME)

CURRENCY = (catalog.GithubRelease, catalog.GoTool, catalog.CargoPackage, catalog.CustomInstaller, catalog.GitUvTool)
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

    undeclared: dict[str, str] = dc.field(default_factory=dict)
    """Binary name → the module it was built from, for an own tool nothing declares.

    Separate from `shadowed`, which is about a *declared* item having a second
    copy. This is the item that is not declared at all, and the two cannot be
    folded: one is keyed by address and the other has no address to be keyed by.
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
        """What the row says when nothing drifted, counted through the verdict
        `diff` reads for the same row.

        It read `all N declared packages are installed` — a count of the
        declaration with the word `installed` attached, so a machine missing four
        tools said every one of them was there. A second predicate here would be
        free to disagree with the rows it is summarising.

        Lives here rather than in the walk because it is a sentence about *this*
        observation: the walk reaching into `evidence` to count it is the walk
        knowing a field it has no other reason to know.
        """
        installed = sum(1 for found in self.evidence.values() if found.verdict is Verdict.MATCHED)
        return f'{installed} of {len(self.evidence)} declared packages installed'

    @property
    def inventory(self) -> tuple[Examined, ...]:
        """Every declared entry, addressed as `diff` addresses one.

        The reported version where a release binary printed one, and what the
        evidence found otherwise — which for a registry package is the manager
        that answered for it. `reconcile.sift` drops whatever produced a finding,
        so this is the installed set on a converged machine.
        """
        return tuple(Examined(address, self.reported.get(address) or found.detail) for address, found in sorted(self.evidence.items()))


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
            met=session.preconditions,
            reported=_reported_versions(present),
            shadowed=_shadowing(mine, evidence, plan, session.repo),
            undeclared=_undeclared_own_tools(plan, session.home),
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
                repair = repair_for(item, evidence.verdict, observed.met, evidence.blocked_by)
                changes.append(
                    Change(
                        NAME,
                        item.stage,
                        item.address,
                        evidence.verdict,
                        repair=repair,
                        detail=evidence.detail,
                        advice=advice_for(item, repair, evidence.blocked_by),
                        desired=item,
                    )
                )
            elif item.name in observed.reinstall:
                repair = repair_for(item, Verdict.STALE, observed.met)
                changes.append(
                    Change(
                        NAME,
                        item.stage,
                        item.address,
                        Verdict.STALE,
                        repair=repair,
                        detail='named by --reinstall, so it is installed again whatever it reports',
                        advice=advice_for(item, repair),
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
                        repair=Repair.BY_HAND,
                        detail=f'{item.executable} runs from {observed.evidence[item.address].detail}; nothing declares the other copy',
                        advice=_undeclared_advice(stray, plan.machine.coordinates.package_manager),
                        desired=item,
                        observed=', '.join(stray),
                    )
                )

        for binary, module in sorted(observed.undeclared.items()):
            changes.append(
                Change(
                    NAME,
                    Stage.TOOLS,
                    binary,
                    Verdict.UNDECLARED,
                    repair=Repair.BY_HAND,
                    detail=f'built from {module}, which nothing this machine declares asks for',
                    advice='declare it in install/packages.yml and this machine’s manifest, '
                    'or remove the binary if it was installed by hand and is not wanted',
                )
            )
        return tuple(changes)

    def perform(self, session: Session, change: Change, privilege: Privilege) -> Outcome:
        """Whichever provider planned it repairs it, or says why it cannot."""
        return registry.install(session, change, privilege)


def _undeclared_own_tools(plan: Plan, home: Path) -> dict[str, str]:
    """Go binaries built from an owner this machine declares tools from, and does
    not declare.

    The mirror of `_shadowing`, and the direction nothing else here looks. Every
    other measurement reads down from the declaration and asks whether the
    machine matches it; this one reads up from the machine and asks whether the
    declaration explains what is there. `fleet` sat installed on two workstations
    with no entry in `packages.yml` at all, and no verb could have said so —
    every one of them was looking the other way.

    Go only, deliberately. `go version -m` reads the module out of the binary
    itself, so "this is one of ours" is measured rather than guessed from a name.
    A uv tool does not record where it came from once installed, and matching on
    the name alone would report every coincidence.

    Scoped to owners the plan already names, because that is the whole of this
    repo's basis for calling a module ours. A machine declaring nothing of an
    owner's reports nothing of theirs, which is correct and not merely cautious.
    """
    owners = {owner for item in plan.items if item.entry and (owner := item.entry.owner)}
    if not owners:
        return {}
    declared = {item.executable for item in plan.items if item.executable}
    return {
        binary: module
        for binary, module in gotool.installed_modules(home / 'go' / 'bin').items()
        if binary not in declared and catalog.owner_of(module) in owners
    }


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
    # Only the names this resource can have a finding about. A second copy of
    # something nothing declares is not shadowing — there is no declared item for
    # it to shadow — so every other name on PATH is measured and then discarded.
    index = ev.executables_on_path(checkout, wanted=frozenset(item.executable for item in mine if item.executable))
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


PROBE_WORKERS = 8
"""How many version probes are in flight at once.

Enough to hide the latency of a process start, small enough that a machine is not
running dozens of unrelated binaries at the same moment. Every one of these is a
tool answering `--version`, so the cost is almost entirely waiting on `fork`,
`exec` and the child's own startup — which is why concurrency helps at all and why
more workers than this buys nothing.

Threads rather than processes: `subprocess.run` releases the GIL for the whole of
the wait, so the work being overlapped is exactly the part Python is not doing.
"""


def _reported_versions(present: tuple[DesiredItem, ...]) -> dict[str, str]:
    """What every installed tool says it is, asked concurrently.

    The dominant cost of measuring this resource, and the one that made a `check`
    unusable on the work box: 69 probes, each its own process start, strictly one
    after another. Serial, that is 1.4s on a fast Linux box and minutes on WSL,
    where a process start costs an order of magnitude more.

    Safe to overlap because a probe is a *read* that shares nothing: each runs one
    binary the declaration names, keeps its own answer, and reaches no state this
    resource holds. `effects.run` builds its own environment per call and
    `evidence.reported_version` has no globals, so two probes cannot observe each
    other. The result is a dict keyed by address, so the order they finish in
    cannot change what is measured.

    Failures stay per item, not per batch. A probe that raises would otherwise
    surface out of the pool and take the whole resource down as unmeasurable —
    which is the opposite of what the timeout inside it exists to guarantee.

    **A dropped probe is recorded.** Degrading here is right and degrading
    silently is not: serially, a raising probe propagated and the resource
    refused, so the failure had somewhere to be read. Caught and dropped, it is
    indistinguishable from a tool that answered and reported no version — which
    is a row saying nothing is wrong. The item and the error go to the run's
    event stream, where the rest of what a probe did already is.
    """
    if not present:
        return {}

    found: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=min(PROBE_WORKERS, len(present))) as pool:
        probes = {pool.submit(_installed_version, item): item for item in present}
        for probe in as_completed(probes):
            item = probes[probe]
            try:
                reported = probe.result()
            except Exception as failed:  # noqa: BLE001 — a probe runs whatever a declaration names
                log.debug('probe failed', address=item.address, executable=item.executable, error=str(failed))
                continue
            if reported:
                found[item.address] = reported
    return found


def _installed_version(item: DesiredItem) -> str | None:
    """What is actually installed, from whichever source can say it exactly.

    A git uv tool is asked through uv's receipt rather than by running it, and that
    *replaces* the probe rather than supplementing it, because the probe's answer
    for these is worse than no answer. `uv tool install` builds from a checkout
    without the `-ldflags`-equivalent stamping a release build does, so a tool that
    answers `--version` at all answers with whatever its source hardcodes — a
    plausible number, unrelated to the revision on disk, that `versions.parse` reads
    happily and compares wrongly. Item 191 records the several that cannot answer
    at all. The receipt is what uv resolved, so it is exact for both.
    """
    if isinstance(item.entry, catalog.GitUvTool):
        return ev.uv_tool_pin(item.name)
    return ev.reported_version(item.executable)


def _wanted(item: DesiredItem) -> releases.Wanted:
    entry = item.entry
    if isinstance(entry, catalog.GithubRelease | catalog.CustomInstaller):
        from_tags = entry.version_source == catalog.VERSION_FROM_TAGS
        return releases.Wanted(repo=entry.repo, tag_prefix=entry.release_tag_prefix, from_tags=from_tags)
    if isinstance(entry, catalog.GoTool | catalog.CargoPackage):
        return releases.Wanted(repo=entry.github_repo)
    if isinstance(entry, catalog.GitUvTool):
        # A `tracks_branch` repo publishes no release, so there is no tag it could
        # be behind and no upstream to consult. Naming no repo is how that reaches
        # `_has_currency`, which already reads an empty one as "not a question this
        # entry can be asked" — the same answer a Go tool declared by module path
        # alone gets, rather than a second exception written beside it.
        # Through `repo_slug_of` because this section carries a clone URL where
        # every other one carries a bare `owner/name` — uv is handed the URL
        # verbatim at install time — and the cache keys on what the API path wants.
        return releases.Wanted(repo='' if entry.tracks_branch else catalog.repo_slug_of(entry.repo))
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

    **Every verdict here answers through `repair_for`, the same as `diff`'s two
    branches.** A currency verdict is a verdict about an item the plan carries, so
    the preconditions that decide whether the item can be installed at all decide
    whether it can be upgraded — and they decide it in the direction the verdict is
    most likely to be true in, since a private release nobody could download is one
    nobody could upgrade either. Deciding it here instead left one entry on one
    machine with two answers: `BY_HAND` when `--reinstall` named it, `AUTOMATIC`
    when the version comparison did, and a failure recorded on every run for work
    the machine was never able to do.
    """
    reported = observed.reported.get(item.address)
    if reported is None:
        if isinstance(item.entry, catalog.GitUvTool):
            return _unpinned_git(item, observed)
        return (
            Change(
                NAME,
                item.stage,
                item.address,
                Verdict.UNKNOWN,
                repair=Repair.NONE,
                detail=f'{item.executable} is installed but would not report a version',
                desired=item,
            ),
        )

    pinned = item.entry.version if isinstance(item.entry, catalog.GithubRelease) else ''
    if pinned:
        return _compared(item, reported, pinned, versions.exactly(reported, pinned), f'pinned to {pinned}', observed.met)

    cached = releases.current(_wanted(item), observed.latest, dt.datetime.now(dt.UTC))
    if cached is None:
        return (
            Change(
                NAME,
                item.stage,
                item.address,
                Verdict.UNKNOWN,
                repair=Repair.NONE,
                detail=_unmeasurable(item, observed),
                advice=_unmeasurable_advice(observed),
                desired=item,
                observed=reported,
            ),
        )

    if observed.measured_upstream and versions.exceeds(reported, cached.version):
        repair = repair_for(item, Verdict.STALE, observed.met)
        return (
            Change(
                NAME,
                item.stage,
                item.address,
                Verdict.STALE,
                repair=repair,
                detail=f'ahead of {cached.version}, which is the newest release and what a fresh install produces',
                advice=advice_for(item, repair),
                desired=item,
                observed=reported,
            ),
        )

    return _compared(
        item,
        reported,
        cached.version,
        versions.at_least(reported, cached.version),
        f'{cached.version} is the latest release',
        observed.met,
    )


def _unpinned_git(item: DesiredItem, observed: Observed) -> tuple[Change, ...]:
    """A git tool whose receipt records no revision, so it came from a default branch.

    `catalog.GitUvTool` calls that "the degraded state rather than the flexible
    one", which makes it drift `apply` repairs by reinstalling against the newest
    release rather than a version nobody could read. Its own updater refuses to run
    in this state, so nothing else is coming to fix it either.

    Only once something has confirmed there *is* a release, though: a cold cache
    cannot tell "this repo publishes none" from "nobody asked yet", and calling the
    first drift would report a permanently unrepairable row on every plan.
    """
    cached = releases.current(_wanted(item), observed.latest, dt.datetime.now(dt.UTC))
    if cached is None:
        return (
            Change(
                NAME,
                item.stage,
                item.address,
                Verdict.UNKNOWN,
                repair=Repair.NONE,
                detail=_unmeasurable(item, observed),
                advice=_unmeasurable_advice(observed),
                desired=item,
            ),
        )
    repair = repair_for(item, Verdict.STALE, observed.met)
    return (
        Change(
            NAME,
            item.stage,
            item.address,
            Verdict.STALE,
            repair=repair,
            detail=f'installed from the default branch, not a release; {cached.version} is the newest',
            advice=advice_for(item, repair),
            desired=item,
        ),
    )


def _unmeasurable(item: DesiredItem, observed: Observed) -> str:
    """Why nothing can say whether this one is current, in the terms of the upstream
    that was asked. A bundle carrying no row for a tool and a cache nobody has
    filled are different problems with different fixes."""
    if observed.from_bundle:
        return f'the staged bundle carries no version for {item.name}, so an offline run has nothing to compare against'
    reason = 'not refreshed this run' if not observed.consulted_network else 'upstream did not answer'
    return f'no cached release for {_wanted(item).repo} within the TTL ({reason})'


def _unmeasurable_advice(observed: Observed) -> str:
    """The fix for `_unmeasurable`, which is not always a command.

    `--refresh` is a flag of the two composite verbs (`dotfiles plan`, `dotfiles
    check`), never of the resource-scoped `dotfiles packages check` this row can
    just as easily be read from — naming the bare flag there would be advice that
    does not run. Offline has no such command at all: what is missing is a newer
    bundle, not a network call this run could make instead.
    """
    if observed.from_bundle:
        return 'extract a newer offline bundle; this one has nothing to compare against'
    return 'refresh the release cache with `dotfiles check --refresh` or `dotfiles plan --refresh`'


def _undeclared_advice(strays: Iterable[str], manager: PackageManager) -> str:
    """What to do about a copy nothing declares — asked of the machine, not guessed.

    The row names what owns the file rather than telling a person to go and find
    out, because `pacman -Qo` answers that in one bounded call the run can make
    itself. "Remove the undeclared copy yourself" is an instruction rather than a
    step.

    The alternative stays on the row, because it is still a judgement only a
    person can make: the two copies are often the same version, and which
    mechanism should own a tool is a real choice rather than a defect.

    Every path is asked about separately. Two strays for one tool are two
    different packages more often than not, and one removal command covering both
    would be wrong for at least one of them.
    """
    rows: list[str] = []
    for stray in strays:
        owner, unavailable = diagnose.package_owning(Path(stray), manager)
        if unavailable:
            rows.append(f'{stray} — could not check what owns it: {unavailable}')
        elif owner:
            rows.append(f'{stray} belongs to the {manager} package {owner}')
            rows.append(f'run: {diagnose.removal_command(owner, manager)}')
        else:
            rows.append(f'{stray} belongs to no {manager} package, so it was put there by hand')
    rows.append('or keep that copy instead, and drop this entry from packages.yml')
    return '\n'.join(rows)


def _compared(item: DesiredItem, reported: str, wanted: str, verdict: bool | None, because: str, met: Preconditions) -> tuple[Change, ...]:
    """One comparison's outcome, with `None` kept distinct from `False`.

    An unparseable version is not an old one. Reporting it as behind would send
    `apply` to reinstall a tool nothing established was wrong, which is the guess
    `Verdict.UNKNOWN` exists to refuse.

    `met` is carried down rather than the repair being decided by the caller,
    because the repair follows the verdict and the verdict is settled here.
    `repair_for` answers both branches: nobody's to repair for the one nothing
    could parse, and the item's own preconditions for the one `apply` would act on.
    """
    if verdict is None:
        return (
            Change(
                NAME,
                item.stage,
                item.address,
                Verdict.UNKNOWN,
                repair=repair_for(item, Verdict.UNKNOWN, met),
                detail=f'{because}, and {reported!r} has no version in it',
                desired=item,
                observed=reported,
            ),
        )
    if verdict:
        return ()
    repair = repair_for(item, Verdict.STALE, met)
    return (
        Change(
            NAME,
            item.stage,
            item.address,
            Verdict.STALE,
            repair=repair,
            detail=because,
            advice=advice_for(item, repair),
            desired=item,
            observed=reported,
        ),
    )


RESOURCE = PackagesResource()
