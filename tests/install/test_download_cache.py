"""The download cache, which decides what bytes a bundle is built out of.

Every other test of `create_bundle` stubs `DownloadCache.fetch` and asserts what
the staging loops did with the file it produced. That is the right seam for those
questions and it leaves this whole class unexecuted — the cache lookup, the
digest check, the publish, the retention sweep and the retry loop behind them
had not run a single statement, under a module the coverage report called well
covered.

Everything here is real but the network: real files, real sha256, real mtimes,
real directory permissions. Only `github_release.request` is stubbed, because it
is the one thing in the path that reaches off the machine.

What makes this worth testing at all is that every failure below is silent. A
build whose cache serves the wrong bytes prints the same lines as one that
serves the right bytes, and the machine that finds out is the one with no network
to check against.

Run with: pytest tests/install/test_download_cache.py
"""

from __future__ import annotations

import dataclasses as dc
import datetime as dt
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

import httpx2
import pytest

from dotfiles import create_bundle
from dotfiles import github_release
from dotfiles.create_bundle import BundleAsset
from dotfiles.create_bundle import DownloadCache

ASSET = create_bundle.github_asset('sharkdp/fd', 'v10.2.0', 'fd-v10.2.0-x86_64-unknown-linux-gnu.tar.gz')

PAYLOAD = b'the bytes upstream serves now'
STALE = b'the bytes an earlier build wrote'
"""Two bodies that are never equal, so which copy reached the destination is a
fact the assertion can read rather than one it has to assume."""


class Wire:
    """`github_release.request`, answering the way an asset host does.

    A declared body per URL and nothing else: a URL nobody put in the mapping
    raises instead of returning something, so a test expecting the cache to
    answer cannot pass by quietly fetching. `flaky` is how many opening attempts
    refuse the connection before the body is served, which is the only way to
    drive the retry loop without a real network that flaps.
    """

    def __init__(self, bodies: dict[str, bytes], *, flaky: int = 0) -> None:
        self.bodies = dict(bodies)
        self.flaky = flaky
        self.calls: list[str] = []

    def __call__(self, url: str, accept: str | None = None) -> bytes:
        self.calls.append(url)
        if len(self.calls) <= self.flaky:
            raise httpx2.ConnectError(f'connection refused on attempt {len(self.calls)}')
        if url not in self.bodies:
            raise httpx2.HTTPError(f'404 for {url}')
        return self.bodies[url]


@pytest.fixture
def cache_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`$XDG_CACHE_HOME` is the knob `paths.cache_home` already re-reads per call.

    Pointing the variable rather than patching the module is what
    `create_bundle.cache_root` was made a function for: a constant bound at
    import moved the releases cache under a test and left this one writing into
    the real machine's `~/.cache`.
    """
    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path / 'cache'))
    return create_bundle.cache_root()


@pytest.fixture
def wire(monkeypatch: pytest.MonkeyPatch) -> Callable[..., Wire]:
    def install(bodies: dict[str, bytes] | None = None, *, flaky: int = 0) -> Wire:
        recorder = Wire(bodies if bodies is not None else {ASSET.url: PAYLOAD}, flaky=flaky)
        monkeypatch.setattr(github_release, 'request', recorder)
        return recorder

    return install


def entry_of(asset: BundleAsset) -> Path:
    return create_bundle.cache_path_for(asset.key)


def age(path: Path, days: float) -> None:
    """Move a file's last-use time back, which is the clock retention reads."""
    when = dt.datetime.now().timestamp() - (days * 86400)
    os.utime(path, (when, when))


def sha256_of_bytes(payload: bytes) -> str:
    """Asked of the function that writes every digest here, never recomputed."""
    with tempfile.TemporaryDirectory() as workspace:
        scratch = Path(workspace) / 'payload'
        scratch.write_bytes(payload)
        return github_release.sha256_of(scratch)


# ─────────────────────────────────────────────────────────────────────────────
# What can be sitting where a cache entry belongs
# ─────────────────────────────────────────────────────────────────────────────


def nothing_cached(cache: DownloadCache, asset: BundleAsset) -> None:
    pass


def an_entry_and_its_digest(cache: DownloadCache, asset: BundleAsset) -> None:
    """What a finished build leaves: the bytes, and the digest describing them."""
    cached = entry_of(asset)
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(STALE)
    cache.digest_file(asset).write_text(github_release.sha256_of(cached) + '\n')


def bytes_with_no_digest(cache: DownloadCache, asset: BundleAsset) -> None:
    """A publish that got the rename in and died before writing the digest."""
    cached = entry_of(asset)
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(STALE)


def a_digest_with_no_bytes(cache: DownloadCache, asset: BundleAsset) -> None:
    """The sidecar alone, which describes nothing this cache can serve."""
    digest = cache.digest_file(asset)
    digest.parent.mkdir(parents=True, exist_ok=True)
    digest.write_text(sha256_of_bytes(STALE) + '\n')


def a_corrupt_entry(cache: DownloadCache, asset: BundleAsset) -> None:
    """Bytes that no longer hash to the digest recorded for them.

    Truncated by a full disk, half-written by a killed process, flipped by the
    filesystem — the cause does not matter and the cache cannot ask. It carries
    a verdict as well, because that verdict was reached about the *other* bytes.
    """
    cached = entry_of(asset)
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(STALE)
    cache.digest_file(asset).write_text(sha256_of_bytes(PAYLOAD) + '\n')
    cache.status_file(asset).write_text('verified\n')


def debris_from_an_interrupted_build(cache: DownloadCache, asset: BundleAsset) -> None:
    """The temp file a build that was killed mid-publish left behind.

    Under a name carrying the writer's pid, which is what keeps it out of the
    lookup: `cached.is_file()` is the whole cache test, so debris that had been
    written straight to the entry's own name would be served to this build as a
    complete asset.
    """
    cached = entry_of(asset)
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.with_name(f'{cached.name}.partial.999999').write_bytes(STALE[:8])


def is_republished(cache: DownloadCache, asset: BundleAsset) -> bool:
    """The cache holds what was just served, described by its own digest."""
    cached = entry_of(asset)
    return cached.is_file() and cached.read_bytes() == PAYLOAD and cache.recorded_digest(asset) == github_release.sha256_of(cached)


def is_the_earlier_entry(cache: DownloadCache, asset: BundleAsset) -> bool:
    cached = entry_of(asset)
    return cached.is_file() and cached.read_bytes() == STALE and cache.recorded_digest(asset) == github_release.sha256_of(cached)


Seed = Callable[[DownloadCache, BundleAsset], None]


@dc.dataclass(frozen=True)
class CacheState:
    """One state of the cache directory, and everything a fetch does about it.

    Every answer on one row, because a counter alone cannot tell a hit from a
    miss that happened to leave the same tally: `served` says which copy reached
    the build, `downloads` is also how many times the network was consulted, and
    `after` says what the next build will find.
    """

    seed: Seed
    enabled: bool
    hits: int
    downloads: int
    served: bytes
    after: Callable[[DownloadCache, BundleAsset], bool]


CACHE_STATES: dict[str, CacheState] = {
    'nothing-is-cached': CacheState(nothing_cached, True, 0, 1, PAYLOAD, is_republished),
    'the-entry-and-its-digest-agree': CacheState(an_entry_and_its_digest, True, 1, 0, STALE, is_the_earlier_entry),
    'bytes-with-no-digest': CacheState(bytes_with_no_digest, True, 0, 1, PAYLOAD, is_republished),
    'a-digest-with-no-bytes': CacheState(a_digest_with_no_bytes, True, 0, 1, PAYLOAD, is_republished),
    'a-corrupt-entry': CacheState(a_corrupt_entry, True, 0, 1, PAYLOAD, is_republished),
    'debris-from-an-interrupted-build': CacheState(debris_from_an_interrupted_build, True, 0, 1, PAYLOAD, is_republished),
    'a-disabled-cache-over-a-good-entry': CacheState(an_entry_and_its_digest, False, 0, 1, PAYLOAD, is_the_earlier_entry),
}
"""Every state, and which of them may answer for the build.

One row hits. The rest are the ways an entry can be present and not trustworthy,
and every one of them has to reach the network instead — a lookup that answered
from any of them installs bytes nobody checked onto the machine that cannot check
them either.

The last row is the same good entry with the cache switched off, which is what
separates "the entry was rejected" from "the entry was never consulted".
"""


# ─────────────────────────────────────────────────────────────────────────────
# The cache answers only for an entry it can stand behind
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('named', list(CACHE_STATES), ids=list(CACHE_STATES))
def test_a_fetch_serves_the_cache_or_the_network_and_says_which(cache_home, wire, tmp_path, named):
    state = CACHE_STATES[named]
    recorder = wire()
    cache = DownloadCache(enabled=state.enabled)
    state.seed(cache, ASSET)
    destination = tmp_path / 'staging' / 'binaries' / ASSET.filename

    cache.fetch(ASSET, destination, f'  fd ({named})')

    assert destination.read_bytes() == state.served
    assert (cache.hits, cache.downloads) == (state.hits, state.downloads)
    assert len(recorder.calls) == state.downloads, 'the counter and the wire have to agree about who answered'
    assert state.after(cache, ASSET), 'the entry the next build will find'


def test_a_corrupt_entry_takes_its_verdict_with_it(cache_home, wire, tmp_path):
    """The status file records what upstream published about *these* bytes.

    Left behind when the bytes are replaced, `verify_against_upstream` reads
    `verified` for a copy nothing verified and records its digest into
    checksums.txt — so the installer on the far side logs a check it did not
    perform.
    """
    wire()
    cache = DownloadCache(enabled=True)
    a_corrupt_entry(cache, ASSET)
    assert cache.status(ASSET) == 'verified', 'the seed has to be the state being cleared'

    cache.fetch(ASSET, tmp_path / 'out' / ASSET.filename, '  fd')

    assert cache.status(ASSET) is None
    assert cache.downloads == 1


def test_the_staged_copy_is_the_builds_to_consume(cache_home, wire, tmp_path):
    """`extract_go_binary` unlinks the archive it was handed, and
    `extract_windows_exe` and `repackage_zip_as_tarball` both do the same.

    A hit that hardlinked or moved instead of copying would therefore destroy
    the entry it just served, and the symptom is a cache that misses forever
    while reporting itself enabled.
    """
    wire()
    cache = DownloadCache(enabled=True)
    an_entry_and_its_digest(cache, ASSET)
    destination = tmp_path / 'out' / ASSET.filename

    cache.fetch(ASSET, destination, '  fd')
    destination.unlink()
    cache.fetch(ASSET, destination, '  fd')

    assert destination.read_bytes() == STALE
    assert (cache.hits, cache.downloads) == (2, 0)


# ─────────────────────────────────────────────────────────────────────────────
# Publishing into the cache
#
# How bytes get *into* the cache, which is where a later build's answer comes from.
# ─────────────────────────────────────────────────────────────────────────────


def test_an_entry_appears_whole_or_not_at_all(cache_home, wire, tmp_path, monkeypatch):
    """Published through a temp name and renamed, so a build killed mid-copy
    leaves nothing at the entry's own name.

    Copied straight to `cached`, the truncated remains are a file that
    `cached.is_file()` accepts. The digest sidecar would be absent and today
    that is what saves it — but the two are written a line apart, and the
    cache's whole safety then rests on losing a race it never meant to run.

    The copy is watched rather than faked: `copyfile` still runs, and what is
    recorded is where it was pointed and what was at the entry's name at that
    instant.
    """
    watched: list[tuple[str, bool]] = []
    real_copyfile = shutil.copyfile
    cached = entry_of(ASSET)

    def watch(source, target, **kwargs):
        watched.append((Path(target).name, cached.exists()))
        return real_copyfile(source, target, **kwargs)

    monkeypatch.setattr(shutil, 'copyfile', watch)
    wire()
    cache = DownloadCache(enabled=True)

    cache.fetch(ASSET, tmp_path / 'out' / ASSET.filename, '  fd')

    assert watched == [(f'{cached.name}.partial.{os.getpid()}', False)]
    assert cached.read_bytes() == PAYLOAD
    assert list(cached.parent.glob('*.partial*')) == [], 'the temp name is consumed by the rename'


@pytest.mark.skipif(os.geteuid() == 0, reason='root ignores the directory permission this test removes')
def test_a_cache_that_cannot_be_written_is_a_slow_build_rather_than_a_failed_one(cache_home, wire, tmp_path):
    """A build must not fail over housekeeping it does not need to finish.

    The asset is still downloaded and still staged; only the copy into the
    cache is lost, and the next build pays for it in time rather than in a
    traceback.
    """
    wire()
    cache = DownloadCache(enabled=True)
    entry_of(ASSET).parent.mkdir(parents=True, exist_ok=True)
    entry_of(ASSET).parent.chmod(0o555)
    destination = tmp_path / 'out' / ASSET.filename

    try:
        cache.fetch(ASSET, destination, '  fd')
    finally:
        entry_of(ASSET).parent.chmod(0o755)

    assert destination.read_bytes() == PAYLOAD
    assert cache.downloads == 1
    assert not entry_of(ASSET).exists()


@pytest.mark.skipif(os.geteuid() == 0, reason='root ignores the directory permission this test removes')
def test_the_write_guard_covers_the_copy_and_not_the_directory_the_copy_needs(cache_home, wire, tmp_path):
    """Measured rather than endorsed, and the sibling above is why.

    The two are the same machine — a cache root nobody can write into — and
    differ only in whether this asset's directory happens to exist from an
    earlier build. `cached.parent.mkdir` sits outside the try that catches
    OSError, so on the first asset of a fresh cache the build dies with an
    uncaught PermissionError instead of the warning the second one gets.

    The download itself already succeeded, which is what makes it worth
    pinning: the bytes are in hand and the build ends anyway.
    """
    wire()
    cache = DownloadCache(enabled=True)
    cache_home.chmod(0o555)
    destination = tmp_path / 'out' / ASSET.filename

    try:
        with pytest.raises(PermissionError):
            cache.fetch(ASSET, destination, '  fd')
    finally:
        cache_home.chmod(0o755)

    assert destination.read_bytes() == PAYLOAD
    assert cache.downloads == 1


def test_the_recorded_digest_is_the_value_a_checksums_file_carries(cache_home, wire, tmp_path):
    """`verify_against_upstream` writes this straight into `checksums.txt` as
    `{digest}  {filename}`, so a trailing newline read back off the sidecar
    would put a blank line through the middle of the file the installer
    parses.
    """
    wire()
    cache = DownloadCache(enabled=True)
    destination = tmp_path / 'out' / ASSET.filename

    cache.fetch(ASSET, destination, '  fd')

    assert cache.recorded_digest(ASSET) == github_release.sha256_of(destination)
    assert cache.recorded_digest(ASSET).strip() == cache.recorded_digest(ASSET)


def test_an_enabled_cache_makes_its_root_and_a_disabled_one_makes_nothing(cache_home):
    DownloadCache(enabled=False)
    assert not cache_home.exists()

    DownloadCache(enabled=True)
    assert cache_home.is_dir()


@dc.dataclass(frozen=True)
class Aged:
    days: float
    survives: bool


RETENTION = create_bundle.CACHE_RETENTION_DAYS

AGES: dict[str, Aged] = {
    'used-during-this-build': Aged(0, True),
    'used-a-month-ago': Aged(30, True),
    'used-just-inside-retention': Aged(RETENTION - 1, True),
    'used-just-past-retention': Aged(RETENTION + 1, False),
    'a-version-superseded-a-year-ago': Aged(365, False),
}
"""How old an entry's last use is, and whether the sweep keeps it.

Read off `CACHE_RETENTION_DAYS` rather than written as a number, so moving the
window moves the boundary cases with it instead of turning them into two
assertions about a value nothing uses any more.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Retention
#
# Ageing on last use, which is what lets a tool that never changes stay cached.
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('named', list(AGES), ids=list(AGES))
def test_the_sweep_drops_an_entry_by_when_it_was_last_used(cache_home, wire, tmp_path, named):
    aged = AGES[named]
    wire()
    cache = DownloadCache(enabled=True)
    cache.fetch(ASSET, tmp_path / 'out' / ASSET.filename, '  fd')
    cache.remember_status(ASSET, 'verified')
    sidecars = (entry_of(ASSET), cache.digest_file(ASSET), cache.status_file(ASSET))
    for path in sidecars:
        age(path, aged.days)

    cache.prune()

    assert [path.exists() for path in sidecars] == [aged.survives] * 3, 'an entry ages as one thing, sidecars included'
    assert cache_home.is_dir(), 'the sweep empties the cache, never removes it'
    assert entry_of(ASSET).parent.exists() is aged.survives, 'a directory with nothing left in it goes too'


def test_a_tool_that_never_changes_does_not_age_out_because_the_cache_kept_working(cache_home, wire, tmp_path):
    """mtime is the clock the sweep reads, so a hit has to count as use.

    Both entries below are already past retention when the build starts and
    one of them is what this build asks for. Without the touch it is swept
    anyway — the entry is dropped for having been useful, and the next build
    re-downloads a tool whose release has not moved in a year. Which is a
    cache that gets slower the better it works.
    """
    wanted = ASSET
    superseded = create_bundle.github_asset('sharkdp/fd', 'v9.0.0', 'fd-v9.0.0-x86_64-unknown-linux-gnu.tar.gz')
    wire()
    cache = DownloadCache(enabled=True)
    for asset in (wanted, superseded):
        an_entry_and_its_digest(cache, asset)
        cache.remember_status(asset, 'verified')
        for path in (entry_of(asset), cache.digest_file(asset), cache.status_file(asset)):
            age(path, RETENTION + 30)

    cache.fetch(wanted, tmp_path / 'out' / wanted.filename, '  fd')
    cache.prune()

    assert cache.hits == 1
    assert entry_of(wanted).read_bytes() == STALE
    assert cache.recorded_digest(wanted) == github_release.sha256_of(entry_of(wanted))
    assert cache.status(wanted) == 'verified', 'the verdict is refreshed with the bytes it describes'
    assert not entry_of(superseded).exists(), 'the version nothing asked for is what retention is for'
    assert not entry_of(superseded).parent.exists()
    assert entry_of(wanted).parent.parent.is_dir(), 'a directory something still lives under is left alone'


def test_a_cache_that_was_never_created_is_swept_without_complaint(cache_home):
    """`build` prunes unconditionally at the end, including a run with
    `--no-cache`, where the directory does not exist at all."""
    DownloadCache(enabled=False).prune()

    assert not cache_home.exists()


# ─────────────────────────────────────────────────────────────────────────────
# A verdict cannot outlive the digest it describes
#
# `status` answers for one immutable asset, and only while that asset is here.
#
# What upstream published for a released tag does not change, so caching the
# answer saves the expensive half of verification — an API call to find the
# checksums asset and a download to read it. It is also the one cached value
# that is *about* other bytes, so it is only as good as those bytes still being
# the ones on disk.
# ─────────────────────────────────────────────────────────────────────────────


def test_a_verdict_is_refused_until_there_are_bytes_for_it_to_describe(cache_home, wire, tmp_path):
    """Written first, it survives a fetch that then failed to cache anything —
    and `verify_against_upstream` reads `verified` and asks for the digest of
    an entry that was never written.
    """
    wire()
    cache = DownloadCache(enabled=True)

    cache.remember_status(ASSET, 'verified')

    assert cache.status(ASSET) is None
    assert not cache.status_file(ASSET).exists()

    cache.fetch(ASSET, tmp_path / 'out' / ASSET.filename, '  fd')
    cache.remember_status(ASSET, 'verified')

    assert cache.status(ASSET) == 'verified'


def test_a_disabled_cache_neither_records_a_verdict_nor_reads_one(cache_home, wire, tmp_path):
    """`--no-cache` is asked for by somebody who does not trust what is on
    disk, so a verdict read out of it would be the one thing that survived
    the flag."""
    wire()
    warm = DownloadCache(enabled=True)
    warm.fetch(ASSET, tmp_path / 'out' / ASSET.filename, '  fd')
    warm.remember_status(ASSET, 'verified')

    cold = DownloadCache(enabled=False)
    cold.remember_status(ASSET, 'unpublished')

    assert cold.status(ASSET) is None
    assert warm.status(ASSET) == 'verified', 'the file is there; the disabled cache declines to read it'


def test_eviction_takes_the_bytes_the_digest_and_the_verdict_together(cache_home, wire, tmp_path):
    """`verify_against_upstream` evicts on a checksum mismatch, which is the
    one case where the bytes are known to be wrong. Leaving either sidecar
    behind hands the next build a verdict about bytes it no longer has.
    """
    recorder = wire()
    cache = DownloadCache(enabled=True)
    destination = tmp_path / 'out' / ASSET.filename
    cache.fetch(ASSET, destination, '  fd')
    cache.remember_status(ASSET, 'verified')

    cache.evict(ASSET)

    assert [path.exists() for path in (entry_of(ASSET), cache.digest_file(ASSET), cache.status_file(ASSET))] == [False] * 3
    cache.fetch(ASSET, destination, '  fd')
    assert (cache.hits, cache.downloads) == (0, 2)
    assert len(recorder.calls) == 2


def test_evicting_something_that_was_never_cached_is_not_an_error(cache_home):
    """`add_wheels` evicts on a digest mismatch without knowing whether the
    cache was enabled, so the no-op has to be the ordinary case."""
    cache = DownloadCache(enabled=True)

    cache.evict(ASSET)

    assert cache_home.is_dir()


def test_an_entry_and_both_its_sidecars_share_one_directory(cache_home):
    """Which is what makes retention able to drop them as a unit, and what
    `cache_path_for`'s one-level-per-key-part layout is for."""
    cache = DownloadCache(enabled=False)
    paths = (entry_of(ASSET), cache.digest_file(ASSET), cache.status_file(ASSET))

    assert len({path.parent for path in paths}) == 1
    assert len(set(paths)) == 3


# ─────────────────────────────────────────────────────────────────────────────
# Downloading
#
# The one loop between the declaration and the bytes.
# ─────────────────────────────────────────────────────────────────────────────


def test_a_transfer_that_flaps_is_retried_rather_than_failing_the_build(cache_home, wire, tmp_path):
    """A bundle asks for every declared tool in one run, so a single refused
    connection anywhere in that list would otherwise end the build for the
    machine that has no other way to get any of them."""
    recorder = wire(flaky=create_bundle.DOWNLOAD_ATTEMPTS - 1)
    destination = tmp_path / 'staging' / 'binaries' / ASSET.filename

    create_bundle.download(ASSET.url, destination)

    assert destination.read_bytes() == PAYLOAD
    assert len(recorder.calls) == create_bundle.DOWNLOAD_ATTEMPTS


def test_a_transfer_that_never_answers_is_refused_and_writes_nothing(cache_home, wire, tmp_path):
    """Paired with the retry above, which a loop that swallowed the last
    failure would also satisfy. The absent file is the half that matters:
    a truncated one is staged, recorded in the manifest, and unpacked on the
    machine that cannot fetch a replacement.
    """
    recorder = wire(flaky=create_bundle.DOWNLOAD_ATTEMPTS)
    destination = tmp_path / 'staging' / 'binaries' / ASSET.filename

    with pytest.raises(create_bundle.BundleError, match=ASSET.url):
        create_bundle.download(ASSET.url, destination)

    assert len(recorder.calls) == create_bundle.DOWNLOAD_ATTEMPTS
    assert not destination.exists()


def test_a_failure_to_write_is_retried_on_the_same_terms_as_a_failure_to_reach(cache_home, wire, tmp_path):
    """`except (httpx2.HTTPError, OSError)`, because half of what can go wrong
    here is local. The destination below is a directory, which is the one
    local failure a test can produce without pretending the filesystem is
    something it is not.
    """
    recorder = wire()
    destination = tmp_path / 'staging' / ASSET.filename
    destination.mkdir(parents=True)

    with pytest.raises(create_bundle.BundleError, match=ASSET.url):
        create_bundle.download(ASSET.url, destination)

    assert len(recorder.calls) == create_bundle.DOWNLOAD_ATTEMPTS
    assert destination.is_dir(), 'nothing replaced what was in the way'


def test_the_staging_directory_is_made_by_whoever_writes_into_it(cache_home, wire, tmp_path):
    wire()
    destination = tmp_path / 'made' / 'by' / 'the' / 'download' / ASSET.filename

    create_bundle.download(ASSET.url, destination)

    assert destination.read_bytes() == PAYLOAD


LATEST = 'https://api.github.com/repos/sharkdp/fd/releases/latest'


@dc.dataclass(frozen=True)
class Answer:
    body: bytes | None
    tag: str | None
    """The version, or None where the build has to refuse."""


ANSWERS: dict[str, Answer] = {
    'a-published-release': Answer(b'{"tag_name": "v10.2.0"}', 'v10.2.0'),
    'nothing-answers': Answer(None, None),
    'a-payload-with-no-tag': Answer(b'{"draft": true}', None),
    'a-tag-that-is-empty': Answer(b'{"tag_name": ""}', None),
    'a-body-that-is-not-json': Answer(b'<html>rate limited</html>', None),
}
"""What the release API can say, and whether a bundle can be built from it.

`latest_version` answers None for all four failures, which is the right answer
for an installer deciding whether to update — it leaves the machine on what it
has. A bundle has no such fallback: it cannot name the asset without the
version, so the same None has to become a refusal here or the build stages
`None` into a URL.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Resolving a version
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('named', list(ANSWERS), ids=list(ANSWERS))
def test_a_version_the_build_cannot_read_ends_the_build(cache_home, wire, named):
    answer = ANSWERS[named]
    wire({LATEST: answer.body} if answer.body is not None else {})

    if answer.tag is None:
        with pytest.raises(create_bundle.BundleError, match='sharkdp/fd'):
            create_bundle.fetch_latest_version('sharkdp/fd')
    else:
        assert create_bundle.fetch_latest_version('sharkdp/fd') == answer.tag
