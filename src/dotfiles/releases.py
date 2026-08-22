"""Cached upstream release versions, so a tool that is present can still read as behind.

`check` runs at a prompt and unattended on a timer, so it must not spend one GitHub
API call per declared release answering "is anything out of date". It reads this
cache, and the network is entered only by `--refresh`.

The consequence is deliberate: a release published in the last hour reads as
current until the cache is refreshed. What the cache must never do is let an
*unmeasured* tool read as current — a missing or expired entry answers `UNKNOWN`,
never `ok`. That is the same rule `Verdict.UNKNOWN` exists for, and the state the
bash it replaces got wrong: an empty version string there falls through into "will
reinstall", which is a guess wearing a measurement's clothes.

Cache rather than state by `data.md`'s test — deleting the file costs a recompute
and nothing else — which is why it lives under `$XDG_CACHE_HOME` while the run
records live under `$XDG_STATE_HOME`.
"""

from __future__ import annotations

import dataclasses as dc
import datetime as dt
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotfiles import github_release
from dotfiles import paths
from dotfiles.output import hint
from dotfiles.output import warn


def cache_file() -> Path:
    """Where the cache lives. A call rather than a constant, so `$XDG_CACHE_HOME`
    still means what it says after this module has been imported."""
    return paths.cache_home() / 'releases.json'


TTL = dt.timedelta(hours=12)
"""How long an answer is worth trusting.

Twice a day is far more often than these tools release and far less often than
`check` runs, which is the whole of the tradeoff. Longer would be defensible;
shorter turns the timer into a rate-limit problem.
"""

WORKERS = 16
"""Bounded, because the ceiling here is GitHub rather than the CPU — but not the
rate limit, which is a budget per hour and not per second.

What a worker count decides is *concurrency*, and GitHub's documented guidance on
that is to stay under 100 requests in flight. The request count is the same
whatever this says: one per present declared release, counted from the plan.

Measured 2026-08-22 over 73 of them, revalidating, median of three:

    8   3.34s      24  2.04s
    16  1.75s      32  0.92s

32 is faster still and is not what this is set to. Halving the sweep is worth a
doubling; quartering it is worth four times the requests in flight against one
host, on a fleet where the rate limit is already the thing being careful about.
"""


@dc.dataclass(frozen=True, slots=True)
class Cached:
    """One repo's newest release tag, when that was true, and how to re-ask cheaply."""

    version: str
    checked: dt.datetime

    etag: str = ''
    """What GitHub called this answer, sent back as `If-None-Match` on the next refresh.

    Optional because an entry written before there was one, or by a repo that
    offers no `ETag`, is still a perfectly good answer — it just costs a full
    response to confirm. Never load-bearing for the version: it decides how the
    question is asked, never what the answer means.
    """

    def fresh(self, now: dt.datetime, ttl: dt.timedelta = TTL) -> bool:
        return now - self.checked < ttl


@dc.dataclass(frozen=True, slots=True)
class Wanted:
    """A repo to ask about, the tag prefix that narrows the answer, and which
    endpoint holds it."""

    repo: str
    tag_prefix: str = ''

    from_tags: bool = False
    """Whether this repo's newest version is a tag rather than a release.

    One project declares it — `aws/aws-cli` tags every build and publishes no
    release — and `catalog.VERSION_SOURCES` is where that is stated. Deliberately
    not part of `key`: a repo answers one way or the other, so two `Wanted` for one
    repo disagreeing about which is a declaration bug rather than two cache
    entries.
    """

    @property
    def key(self) -> str:
        """What the cache is keyed on.

        The prefix is part of it: one monorepo releases four different CLIs, and
        keying on the repo alone would have them overwrite each other's answer.
        """
        return f'{self.repo}#{self.tag_prefix}' if self.tag_prefix else self.repo


def load(path: Path | None = None) -> dict[str, Cached]:
    """Whatever the cache holds, or nothing.

    Every failure is the same answer — no cache — because that answer is already
    correct and already handled. A corrupt file is not worth a traceback when
    re-fetching costs one request.
    """
    try:
        payload = json.loads((path or cache_file()).read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}

    entries = {}
    for key, record in payload.items():
        try:
            entries[key] = Cached(
                version=record['version'],
                checked=dt.datetime.fromisoformat(record['checked']),
                etag=record.get('etag') or '',
            )
        except (TypeError, KeyError, ValueError):
            continue
    return entries


def save(entries: dict[str, Cached], path: Path | None = None) -> bool:
    """Write the cache, and say when it could not be written.

    A read-only or full `$XDG_CACHE_HOME` must not fail a `check` that has already
    produced its answer. Silence is what makes that permanent: an unwritten cache
    reads back empty, so every currency-capable tool answers `UNKNOWN` advising a
    refresh, and the refresh it advises is the write that keeps failing. The
    machine is stuck reporting nothing measurable with the reason unnamed.

    Returns whether it wrote, so a caller can tell the two apart without reading
    the warning.
    """
    # The etag is omitted where there is none rather than written empty, so a repo
    # that offers no `ETag` reads the same on disk as one nobody has asked yet.
    payload = {
        key: {'version': entry.version, 'checked': entry.checked.isoformat()} | ({'etag': entry.etag} if entry.etag else {})
        for key, entry in entries.items()
    }
    target = path or cache_file()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')
    except OSError as unwritable:
        warn(f'could not cache upstream versions at {target}: {unwritable}')
        hint(f'every declared release reads as unknown until {target.parent} takes a write — check its permissions and free space')
        return False
    return True


def refresh(wanted: tuple[Wanted, ...], existing: dict[str, Cached], now: dt.datetime) -> dict[str, Cached]:
    """Ask GitHub about each repo, keeping the previous answer where it cannot.

    Kept rather than dropped: a request that failed says nothing about whether the
    last answer was right, and dropping it would turn one rate-limited refresh into
    a report that every tool is unmeasurable.

    **Each repo is asked with the `ETag` its own entry carries**, so a project that
    has not released since the last refresh answers 304 — which GitHub does not bill
    against the rate limit. That is what an entry keeps an etag for, and it is a
    quota saving rather than a speed one: `github_release.revalidate` has the
    measurement and the warning not to expect the other.

    An unchanged answer restamps `checked` and changes nothing else. The version is
    the one already held, which is precisely what the 304 asserted, so re-reading it
    off the response would be reading a body that was never sent.
    """
    if not wanted:
        return dict(existing)

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        fetched = list(pool.map(lambda item: (item, _newest(item, existing.get(item.key))), wanted))

    entries = dict(existing)
    for item, answer in fetched:
        previous = entries.get(item.key)
        if answer.unchanged and previous is not None:
            entries[item.key] = dc.replace(previous, checked=now)
        elif answer.version:
            entries[item.key] = Cached(version=answer.version, checked=now, etag=answer.etag)
    return entries


def _newest(wanted: Wanted, previous: Cached | None = None) -> github_release.Newest:
    """Whichever endpoint this repo publishes its newest version on.

    Dispatched on the declaration rather than tried in turn: falling back to tags
    when the release lookup fails would read a rate-limited minute as "this project
    tags instead", and start answering a different question with no way to tell.

    `previous` supplies the etag and nothing else. A repo with no entry, or one
    whose entry predates etags being stored, is asked unconditionally and costs
    exactly what it always did.
    """
    etag = previous.etag if previous else ''
    if wanted.from_tags:
        return github_release.newest_tag(wanted.repo, wanted.tag_prefix, etag)
    return github_release.newest_version(wanted.repo, wanted.tag_prefix, etag)


def current(wanted: Wanted, entries: dict[str, Cached], now: dt.datetime) -> Cached | None:
    """The cached answer for one repo, or None when there is none worth using."""
    entry = entries.get(wanted.key)
    return entry if entry is not None and entry.fresh(now) else None
