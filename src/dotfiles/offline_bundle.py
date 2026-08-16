"""Finding a bundle archive, and unpacking it where every provider looks.

install.sh does these same two things in POSIX sh and keeps its own copy on
purpose: the CLI that would run this is the thing the bundle exists to install,
so the bootstrap has nothing to call. What is deliberately not duplicated is
where a staged bundle lives — `paths.staging_dir()` answers that on both sides.

This exists because staging and converging stopped being one act. install.sh
ended in `exec dotfiles apply` until a bare run converged a work box nobody had
asked to converge, and the split that fixed it left `apply --offline` refusing on
a machine whose only fault was a bundle still in its tarball — with the
bootstrap, which reinstalls uv and the whole CLI, as the only thing that would
unpack it.
"""

from __future__ import annotations

import dataclasses as dc
import json
import re
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from dotfiles import catalog
from dotfiles import commands
from dotfiles import effects
from dotfiles import github_release
from dotfiles import paths
from dotfiles import providers
from dotfiles import publishing
from dotfiles import remote as transport
from dotfiles import resolve as resolver
from dotfiles.providers import bundle
from dotfiles.refusal import Refusal

ARCHIVE_SUFFIX = '.tar.gz'
"""What a bundle archive ends in, and the only thing that makes a listed name one.

Named because two readers of a remote shelf have to agree on it, and a shelf
holds more than bundles. A `.part` from an interrupted upload or a `.DS_Store`
from browsing the share sorts before `dotfiles-`, so a reader that took
everything-but-the-records would name one as the oldest bundle while the sweep it
points at declined to touch it.
"""

ARCHIVES = f'dotfiles-offline-*{ARCHIVE_SUFFIX}'
"""What `bundle create` names its output, which is how one is recognised."""


class StagingError(Refusal):
    """An archive that cannot be staged, carrying the reason a person needs."""


@dc.dataclass(frozen=True, slots=True)
class Staging:
    """What is staged, where, and how it got there.

    One type read by three callers — the offline gate in `apply`, `bundle show` and
    `bundle check` — because all three answer the same first question and were
    answering it in three ways, one of which was silence. A run that installs from a
    bundle has to be able to say which bundle, and that sentence is composed here
    rather than at each of them.
    """

    directory: Path
    carried: tuple[bundle.Staged, ...]

    bundles: tuple[Path, ...] = ()
    """Every staged bundle, newest first — the stack `carried` is merged from."""

    descriptions: tuple[bundle.Description, ...] = ()
    """What each of those says it is, in the same order.

    Every one rather than the newest alone, because a sparse bundle's `current`
    map explains an absence that a *different* bundle might have explained by
    carrying the file. Reading only the newest reports an entry the older full
    bundle staged as one nothing considered.
    """

    extracted: Path | None = None
    """The archive this run unpacked, or None when the bundle was already staged.

    The distinction is the one a reader needs and the one that was missing: a run
    that found a directory somebody staged last week and a run that unpacked a
    tarball a minute ago are the same afterwards and are not the same fact. Silence
    reported them identically, which is how a stale bundle installs a stale machine
    with nothing on screen to suggest looking at its date.
    """

    @property
    def present(self) -> bool:
        return self.directory.is_dir()

    @property
    def readable(self) -> bool:
        """Whether anything here can install from this at all.

        A staged bundle with a manifest, not a row count. A manifest listing
        nothing is a strange bundle and still a bundle — every provider looks its
        own tool up and reports its own miss, which is a worse answer than this
        one but an honest one. No manifest anywhere is different in kind:
        `providers.locate` is the only door in, so there is nothing for any
        provider to miss and the run is inert before it starts.
        """
        return bool(self.bundles)

    @property
    def description(self) -> bundle.Description:
        """The newest staged bundle's own, for the one line that names a build."""
        return next(iter(self.descriptions), bundle.Description())

    @property
    def built(self) -> str:
        return self.description.created

    @property
    def platform(self) -> str:
        return self.description.platform

    @property
    def counts(self) -> dict[str, int]:
        return bundle.counted(self.carried)

    @property
    def names(self) -> frozenset[str]:
        """Every tool the bundle carries a file for, whatever category it is under."""
        return frozenset(row.name for row in self.carried)

    @property
    def sparse(self) -> bool:
        return any(described.sparse for described in self.descriptions)

    def measured(self, name: str) -> str | None:
        """The version a sparse bundle recorded for a tool it left out, if any.

        Across every staged description rather than the newest, because an entry a
        sparse bundle omitted may be one an older full bundle carried — and the two
        answers are both true. The caller asks this only about names nothing
        carries, so there is no case where they compete.

        Answered by `bundle.measured_in` rather than here, so this and the offline
        apply cannot disagree. They did: this matched the name half of the key and
        that one matches the whole `category/name`, which differ on exactly the
        tools declared under more than one category.
        """
        return bundle.measured_in(self.descriptions, name, *bundle.CATEGORIES)

    def headline(self) -> str:
        """The one line that says which bundle this run is installing from.

        Every clause earns its place by being a thing that turned out to be wrong on
        a real machine: the count, because a bundle of wheels alone reads as a full
        one; the date, because a bundle from a previous rebuild installs versions
        nobody expects; and the platform, because a linux bundle staged on a Mac
        fails one tool at a time rather than once, up front.
        """
        if not self.readable:
            return f'no bundle staged at {paths.under_home(self.directory)}'
        origin = f'unpacked {self.extracted.name}' if self.extracted else 'already staged'
        described = ', '.join(part for part in (f'built {self.built}' if self.built else '', self.platform) if part)
        beneath = f' over {len(self.bundles) - 1} older' if len(self.bundles) > 1 else ''
        return f'{len(self.carried)} file(s) from {self.newest.name}{beneath} — {origin}{f" ({described})" if described else ""}'

    @property
    def newest(self) -> Path:
        """The bundle whose rows win, which is the one a headline names.

        The staging directory is not an answer to "which bundle". Several are
        staged at once and the whole point of naming each after its archive is
        that a machine can say which one a file came from — a headline pointing
        at their parent says only that some bundle exists.
        """
        return next(iter(self.bundles), self.directory)

    @property
    def base(self) -> Path | None:
        """The newest staged bundle carrying the whole declaration.

        What the sparse bundles above it read through, and what retention pins.
        Read off the descriptions this already holds rather than off the names,
        because they are here — the sweeps use the name rule because a remote
        listing has nothing else.
        """
        paired = zip(self.bundles, self.descriptions, strict=True)
        return next((path for path, described in paired if not described.sparse), None)

    def breakdown(self) -> str:
        """The per-category counts, which is what says whether a bundle is usable.

        Empty where the manifest lists nothing, so a staged directory that carries no
        manifest reads as the problem it is rather than as a bundle with no files.
        """
        return ', '.join(f'{category} {count}' for category, count in self.counts.items())


BUNDLED_KINDS = (catalog.GithubRelease, catalog.GoTool, catalog.CargoPackage, catalog.CustomInstaller, catalog.WingetPackage)
"""The declaration kinds `create_bundle` stages, and the only ones a bundle can miss.

Read off its `record` calls: a `GithubRelease` becomes a `binary` row plus an `extra`
per companion, a `GoTool` a `go-binary`, a `CargoPackage` a `cargo`, a
`WingetPackage` a `winget`, and a `CustomInstaller` a `script` — and that last only
where the entry declares `bundle_install_script`.

A `WingetPackage` belongs here for a reason the others do not need stated: its
machine declares nothing else. Counting it `outside` would have `bundle check`
report a Windows box as fully covered by a bundle carrying nothing it can install,
which is the one machine where that sentence is both wrong and unfalsifiable from
the other end.

Everything else is deliberately absent and must not be reported as a gap. A system
package comes from apt or pacman on the machine, an npm global from a registry, a
shell plugin from a clone. Counting those made the first `bundle check` report `apt`,
`bash` and `ca-certificates` as things the bundle failed to carry, which is a list
nobody can act on and buries the rows that matter.
"""


@dc.dataclass(frozen=True, slots=True)
class Coverage:
    """What a staged bundle can and cannot install, against one machine's plan."""

    covered: tuple[str, ...]
    uncovered: tuple[str, ...]
    outside: int
    """Declared items a bundle is never built to carry, counted rather than listed.

    Reported because the alternative reads as a bundle covering a third of the
    machine. It covers nearly all of what it is *for*, and the rest arrives another
    way — so the count is the context that makes the two lists above legible."""

    measured: tuple[str, ...] = ()
    """Items a sparse bundle left out because this machine already had them.

    Its own list rather than folded into `covered`, because the two are different
    facts and the difference is what a person acts on. A covered item can be
    installed from the staging directory right now; a measured one cannot be
    installed at all, and does not need to be. Counting it covered would report a
    bundle as able to repair something it deliberately does not hold.

    Not `uncovered` either, which is the failure this whole field exists to
    prevent: under a full bundle an absent item is a gap, and reading a sparse
    bundle's deliberate omissions the same way reports a working machine as
    missing most of itself.
    """


def coverage(staged: Staging, plan: resolver.Plan) -> Coverage:
    """Which of this machine's bundlable items the bundle actually holds.

    Matched on the executable as well as the name. A row is keyed on the declared
    name, and a plan item is looked up by whichever of the two a reader has —
    `bundle check` resolves from the plan, where a Go tool whose binary is called
    something else is reached by its executable. Either side alone reports a tool
    the bundle carries as missing from it.
    """
    wanted, outside = {}, 0
    for item in plan.items:
        if not isinstance(item.entry, BUNDLED_KINDS):
            outside += 1
            continue
        if isinstance(item.entry, catalog.CustomInstaller) and not item.entry.bundle_install_script:
            outside += 1
            continue
        wanted[item.name] = {item.name, item.entry.executable} & staged.names

    covered = sorted(name for name, found in wanted.items() if found)
    absent = set(wanted) - set(covered)
    measured = sorted(name for name in absent if staged.measured(name))
    return Coverage(tuple(covered), tuple(sorted(absent - set(measured))), outside, tuple(measured))


def describe(extracted: Path | None = None) -> Staging:
    """Read back what is staged, without staging anything.

    `extracted` is passed by the one caller that just unpacked something, so the
    description can say so. Discovering it instead would mean comparing mtimes
    against the run's own start, which is a guess where the caller already knows.

    **One walk, handed to all three readers.** `Staging.base` zips the paths and
    the descriptions `strict=True`, so three separate walks could disagree — and
    the `ValueError` that produced escapes `reconcile._stage_bundle`, which catches
    `StagingError`, as a traceback out of `apply --offline`. A second `bundle
    stage` or a hand-unpacked directory during a run is what reaches it. One walk
    makes the disagreement unreachable and costs two fewer reads.
    """
    staged = providers.staged_bundles()
    return Staging(
        paths.staging_dir(),
        bundle.rows_in(staged),
        bundles=staged,
        descriptions=tuple(bundle.description_of(root) for root in staged),
        extracted=extracted,
    )


SIDECAR_SUFFIX = '.json'
"""What a bundle's record on the remote is called: the archive's name plus this.

Derived from the archive rather than kept in an index file. An index is one
object several machines write, which is the collision standards/data.md § "In a
synced directory, every machine writes its own file" exists to make unreachable —
and it goes stale against the directory listing that is the actual truth.
"""


@dc.dataclass(frozen=True, slots=True)
class Record:
    """What a remote holds about one archive, without holding the archive.

    Fetched before the bundle itself, because it is a few hundred bytes and
    answers everything a person needs to decide whether to spend the download:
    when it was built, for which machine, whether it is sparse, and how big it is.
    """

    name: str
    size: int
    sha256: str
    description: bundle.Description = dc.field(default_factory=bundle.Description)

    def as_dict(self) -> dict[str, Any]:
        return {'name': self.name, 'size': self.size, 'sha256': self.sha256, 'bundle': self.description.as_dict()}


def record_from(document: Any) -> Record:
    """A `Record` from parsed JSON, tolerating anything that is not one."""
    if not isinstance(document, dict):
        return Record('', 0, '')
    return Record(
        name=str(document.get('name', '')),
        size=int(document['size']) if isinstance(document.get('size'), int) else 0,
        sha256=str(document.get('sha256', '')),
        description=bundle.description_from(document.get('bundle')),
    )


def peek(archive: Path) -> bundle.Description:
    """What an archive says it is, read out of the tarball without unpacking it.

    Every member is checked for the name rather than one being joined onto the
    known member directory, per standards/python.md § "Ask the library where it
    wrote; never rebuild the path" — the archive's own top-level name is the
    bundler's business and this must not depend on it.
    """
    try:
        with tarfile.open(archive, 'r:gz') as packed:
            found = next((member for member in packed.getmembers() if Path(member.name).name == bundle.DOCUMENT), None)
            if found is None or (opened := packed.extractfile(found)) is None:
                return bundle.Description()
            return bundle.description_from(json.loads(opened.read()))
    except (OSError, tarfile.TarError, ValueError):
        return bundle.Description()


def described_record(archive: Path) -> Record:
    """The record to upload beside an archive, measured from the archive itself."""
    return Record(archive.name, archive.stat().st_size, github_release.sha256_of(archive), peek(archive))


def on_remote(where: transport.Remote, machine: str) -> tuple[str, ...]:
    """Every bundle archive on a machine's shelf, newest first, records excluded.

    Here rather than in the command, because two callers resolve the same set: the
    verb a person types, and the automatic fetch inside `apply --offline`. Two
    listings would be two places the naming convention is known.
    """
    directory = transport.bundles_for(where, machine)
    listed = transport.listed(where, directory)
    if listed is None:
        return ()
    return tuple(sorted((name for name in listed if name.endswith(ARCHIVE_SUFFIX)), reverse=True))


def record_on_remote(where: transport.Remote, directory: str, name: str) -> Record:
    """The record beside an archive, or an empty one where the remote has none.

    Empty rather than refused: a bundle uploaded before records existed, or one
    whose record upload failed, is still installable. What that costs is the
    digest, and `verified` says so rather than passing silently.
    """
    sidecar = f'{name}{SIDECAR_SUFFIX}'
    with tempfile.TemporaryDirectory() as workspace:
        local = Path(workspace) / sidecar
        try:
            transport.pull(where, f'{directory}/{sidecar}', local)
            return record_from(json.loads(local.read_text()))
        except (transport.RemoteError, OSError, ValueError):
            return Record(name, 0, '')


def verified(archive: Path, record: Record) -> bool:
    """Whether an archive matches the digest its record publishes.

    A corrupt one is deleted rather than left in the cache, because `newest` ranks
    by name — it would be the archive every later run picks up, and it would win
    against the good bundle it was meant to replace.

    Answers True where the record carries no digest at all. That is a bundle
    nothing can verify rather than one that failed verification, and the caller
    says so; refusing here would make an unverifiable bundle uninstallable on the
    one machine that cannot fetch another.
    """
    if not record.sha256:
        return True
    if github_release.digests_match(record.sha256, github_release.sha256_of(archive)):
        return True
    archive.unlink(missing_ok=True)
    return False


def fetch(where: transport.Remote, machine: str, name: str, record: Record) -> Path:
    """Pull one bundle into the archive cache and verify it, or refuse.

    The record is a parameter and has no default. Every caller already reads one —
    the typed verb to describe the bundle before asking, the automatic path to
    verify it — and a default would have this fetch it a second time, which is a
    second round trip on the one network where round trips are the cost.
    """
    directory = transport.bundles_for(where, machine)
    destination = transport.pull(where, f'{directory}/{name}', paths.archive_dir() / name)
    if not verified(destination, record):
        raise StagingError(
            f'{name} does not match the digest its record publishes, so it did not arrive whole',
            advice='run it again: dotfiles bundle download',
        )
    # Kept beside the archive, which is what `paths.archive_dir` describes and
    # what `_prune_local` removes. It is the record of what arrived — size, digest
    # and what the bundle says it is — for an archive that outlives the listing it
    # came from. Nothing re-checks the digest at stage time today; `verified` runs
    # here, against this record, at the moment the bytes land.
    (paths.archive_dir() / f'{name}{SIDECAR_SUFFIX}').write_text(json.dumps(record.as_dict(), indent=2) + '\n')
    return destination


def target() -> str:
    """Which machine this box is, for the checks that need a name to compare with.

    Empty rather than raising where nothing answers. A machine with no `$MACHINE`
    and no manifest is a real state part way through a rebuild, and it is exactly
    the state that most needs to be able to unpack a bundle — so a resolver that
    refused here would make the check the reason the machine cannot be built.
    """
    try:
        return commands.resolved(None).machine_name
    except Refusal:
        return ''


def this_box() -> str:
    """Which box this is among those sharing its manifest, for the same checks.

    The discriminator, resolved the way a status filename resolves it — so a
    sparse bundle built against this box's report and one built against its
    twin's are told apart by the same string that kept their two reports from
    overwriting each other.

    Empty on the same terms as `target`, and for the same reason: a half-built
    machine has to be able to unpack a bundle.
    """
    try:
        return publishing.discriminator(commands.resolved(None).machine.coordinates.network_trust)
    except Refusal:
        return ''


def stem(archive: Path) -> str:
    """The directory one archive unpacks into: its name without the suffixes.

    `Path.stem` alone leaves `.tar` on a `.tar.gz`, and the directory is what a
    reader matches against a filename to say which bundle a file came from.
    """
    name = archive.name
    for suffix in ('.tar.gz', '.tgz', '.tar'):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return archive.stem


NAMED = re.compile(r'^dotfiles-offline-v\d{8}T\d{6}Z-(?P<manifest>.+)-(?P<os>[a-z]+)-(?P<arch>[a-z0-9_]+?)(?:-sparse)?$')
"""`create_bundle.bundle_name` read back, for the one field a sweep needs.

The manifest is greedy and the two after it are not, because a manifest carries
hyphens — `wsl-work-workstation` — and the OS and arch do not.
"""


def manifest_of(name: str) -> str:
    """Which machine a bundle was built for, from its own name.

    From the name because the callers have a listing rather than an archive: a
    remote sweep holds strings, and opening every local one to read `bundle.json`
    costs a stat and an unpack per row to answer what the name already says.

    Empty where the name is not one of ours, which groups every stranger together
    and is the conservative answer — a sweep then counts them among themselves
    rather than against a real machine's bundles.
    """
    found = NAMED.match(name.removesuffix('.tar.gz'))
    return found.group('manifest') if found else ''


SPARSE_SUFFIX = '-sparse'
"""What `create_bundle.bundle_name` appends where a build left something out."""


def carries_everything(name: str, described: bundle.Description | None = None) -> bool:
    """Whether a bundle holds the whole declaration rather than a difference.

    From the name unless a caller already has the document. A remote listing is
    names and nothing else — the sidecar carries `completeness` and reading one
    per row is a transfer per bundle, which `bundle list` already declined to
    spend for this same fact — so a rule that needs the document cannot serve both
    sweeps. The two cannot disagree on a bundle this tool built: `build` computes
    the name's suffix and sets `built_from` under one condition, and `describe`
    reads completeness off `built_from` alone.

    An unnamed shape reads as full, which is the direction that costs one retained
    file rather than a deleted one.
    """
    if described is not None:
        return not described.sparse
    return not name.removesuffix('.tar.gz').endswith(SPARSE_SUFFIX)


def base_of(names: tuple[str, ...]) -> str | None:
    """The newest full bundle in one machine's set, which retention must not remove.

    `providers.locate` reads the stack newest-first, so a sparse bundle wins for
    what it carries and falls through to the older full bundle for the rest. That
    fallthrough is what makes a sparse bundle possible, and retention could not
    see it: a name sorts as its stamp does and a full bundle is always the oldest,
    so it was always the first thing a sweep took. `prune` promised the newest is
    never removed, which is true and insufficient when the newest is sparse.

    Pinned only while it is the newest full one, so a newer full build releases the
    older and the stack stays bounded at the limit plus one.

    None for a machine holding only sparse bundles. Nothing is pinned there and
    retention behaves as it did, which is right — a stack with no base is already
    broken and holding one of its members back cannot repair it.
    """
    return max((name for name in names if carries_everything(name)), default=None)


def by_machine(names: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    """The same names, grouped by the machine each was built for.

    Retention counts per machine and not across the cache. `bundle download
    --machine X` writes another box's archive into the same directory this
    machine's live in, so five downloads for a peer can age out the only bundle
    on a box that cannot re-fetch it — while `prune` promises the newest is never
    removed. `stage` already refuses a foreign bundle on the same reasoning; this
    is the eviction half of it.
    """
    grouped: dict[str, list[str]] = {}
    for name in names:
        grouped.setdefault(manifest_of(name), []).append(name)
    return {machine: tuple(sorted(held)) for machine, held in grouped.items()}


@dc.dataclass(frozen=True, slots=True)
class Sweep:
    """What retention would remove, and what the limit wanted and cannot have."""

    superseded: tuple[str, ...] = ()
    pinned: tuple[str, ...] = ()
    """A base the count would otherwise have taken.

    Only those. A base still inside the kept N is retained by the count and needs
    no line saying so, which keeps an ordinary sweep's output unchanged.
    """


def retention(names: tuple[str, ...], keep: int) -> Sweep:
    """What a sweep of one machine's bundles would remove, and what it pins.

    **One function, because the rule has three parts and three callers need all
    three.** The local sweep, the remote sweep and the post-upload nudge each want
    `base_of`, `superseded` and drop-the-base, in that order. Composed at each
    site they agree only while somebody keeps them agreeing, and the drift is
    invisible — a nudge counting against a different limit from the sweep it
    points at reads as a correct number. `standards/python.md` § "Ask whatever owns
    a fact; never work it out a second time" is the rule.

    **The floor is not enforced here, and that is deliberate.** `remote.read`
    refuses a declared `keep_bundles` below one and `bundle prune` refuses a
    `--keep` below one, so a value arriving here has already been through a parser
    that said so. A third clamp would be the silent behaviour those two refusals
    exist to replace: a caller passing zero would get one and no sentence saying
    the flag was not honoured. Where the number is wrong, it is wrong loudly at
    the door it came in through.

    Pure and taking names, so the two sweeps that read a remote and the one that
    reads a cache all answer by the identical rule without any of them holding a
    transport.
    """
    past = transport.superseded(names, keep)
    base = base_of(names)
    return Sweep(tuple(name for name in past if name != base), tuple(name for name in past if name == base))


def swept(grouped: dict[str, tuple[str, ...]], keep: int) -> Sweep:
    """Retention across several machines' bundles, counted per machine and merged.

    The local cache holds more than one machine's archives — `bundle download
    --machine X` writes a peer's beside this one's — and the limit counts per
    machine. A remote shelf holds one machine's, so it asks `retention` directly.
    """
    superseded: list[str] = []
    pinned: list[str] = []
    for owned in grouped.values():
        sweep = retention(owned, keep)
        superseded.extend(sweep.superseded)
        pinned.extend(sweep.pinned)
    return Sweep(tuple(superseded), tuple(pinned))


def newest(*searched: Path, machine: str = '') -> Path | None:
    """The bundle archive to stage, or None where there is none to find.

    Ranked across every directory rather than taking the first that holds any.
    The stamp in a name is now to the second, so two archives in different
    directories order unambiguously — and the cache a download writes into is a
    third place a tarball legitimately sits, which no first-directory-wins order
    can rank against a copy beside the checkout.

    `machine` skips archives built for another one. Without it the ranking and
    the refusal disagree: `bundle download --machine X` writes a peer's archive
    into the same cache, so a peer bundle that sorts newest wins here and is then
    refused by `stage`, ending the run while this machine's own installable
    bundle sits in the same directory with nothing able to reach it.

    A stranger — a name this tool did not write, which `manifest_of` answers `''`
    for — still passes, because a hand-carried tarball is a legitimate thing to
    stage and `stage`'s own `bundle.json` check is the backstop. `''` means no
    filter at all, which is the half-configured box `stage` already tolerates.
    """
    directories = searched or (paths.archive_dir(), Path.cwd(), Path.home())
    found = [archive for directory in directories if directory.is_dir() for archive in directory.glob(ARCHIVES)]
    if machine:
        found = [archive for archive in found if manifest_of(archive.name) in ('', machine)]
    return max(found, key=lambda archive: archive.name, default=None)


def stage(archive: Path, machine: str, box: str) -> Path:
    """Unpack a bundle into its own directory, and say which one.

    One directory per bundle rather than one tree they all merge into. Merging
    refreshes the *files* and replaces `manifest.txt`, so a bundle staged over
    another leaves everything the first carried on disk and unlisted — and under
    `--offline` the manifest is the only door in, which makes those files
    unreachable and the tools they install unmeasurable. Keeping them apart also
    means a machine can say which bundle any staged file came from.

    Unpacked into a sibling directory and moved, rather than extracted straight
    into the staging directory. The archive's single member is named `installers`,
    so extracting in place would land on a directory of that name whatever the
    archive is called.

    Re-staging the same archive replaces its own directory and touches no other,
    so an interrupted run can be repeated without losing what a different bundle
    staged.

    **A bundle built for another machine is refused**, and `machine` is what it is
    measured against. `bundle download --machine X` writes into the same cache
    `newest` ranks, so fetching another box's bundle to look at it is now one
    command away from `apply --offline` staging it — a hazard that did not exist
    while a bundle could only be carried in by hand. `Staging.headline` already
    records why failing up front beats failing one tool at a time; what was
    missing until `bundle.json` was anything that knew the target.

    **`box` is the second identity and is threaded the same way**, because the
    manifest cannot answer which of two machines sharing it a sparse bundle was
    planned against. Injected rather than resolved here: an ambient read answers
    `$MACHINE` or the default, so `apply --machine X --offline` where X's manifest
    carries a different `network_trust` would compare a digest against a hostname
    and refuse a valid bundle. The caller already resolved a session to get
    `machine`; both come from it.

    Either empty means the caller could not resolve one, which is a real state on
    a half-configured box. The check that needs it does not run there and the
    archive stages, because unpacking is this verb's job and refusing would make a
    machine with no `$MACHINE` unable to install at all.
    """
    staged = paths.staging_dir() / stem(archive)
    paths.staging_dir().mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=paths.staging_dir()) as workspace:
        if not effects.unpack(archive, Path(workspace)):
            raise StagingError(f'{archive} is not a readable archive')

        # The manifest, not the member's name: the name is what the bundler
        # happened to call its staging directory, whereas the manifest is the
        # agreement the providers actually read. Staging the wrong tarball
        # otherwise fails much later, as every tool in the plan missing at once.
        unpacked = [entry for entry in Path(workspace).iterdir() if entry.is_dir()]
        if len(unpacked) != 1 or not (unpacked[0] / providers.MANIFEST).is_file():
            raise StagingError(f'{archive} carries no {providers.MANIFEST}, so it is not a dotfiles bundle')

        # Read from what came out rather than from the archive, so what is checked
        # is what would be installed from. Refused before the move, so a rejected
        # bundle leaves nothing behind for `newest` to pick up next run.
        described = bundle.description_of(unpacked[0])
        built_for = described.machine
        if machine and built_for and built_for != machine:
            raise StagingError(
                f'{archive.name} was built for {built_for} and this machine is {machine}',
                advice=f'fetch this one instead: dotfiles bundle download --machine {machine}',
            )
        # The manifest cannot answer this one. Two boxes share it, so a sparse
        # bundle planned against the twin's report omits every tool the twin has
        # current and records the omissions as measured — about a machine that
        # never reported. Only a sparse bundle carries the claim, so only a sparse
        # bundle is refused.
        if box and described.built_for and described.built_for != box:
            raise StagingError(
                f'{archive.name} was planned against what {described.built_for} had installed, and this box is {box}',
                advice=f'build one against this box: dotfiles status upload, then bundle create --machine {machine} --against latest',
            )

        if staged.exists():
            shutil.rmtree(staged)
        shutil.move(unpacked[0], staged)

    return staged
