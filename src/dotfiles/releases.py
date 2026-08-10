"""Cached upstream release versions, so a tool that is present can still read as behind.

`check` runs at a prompt and in a pre-commit hook, so it must not spend one GitHub
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


def cache_file() -> Path:
    """Where the cache lives. A call rather than a constant, so `$XDG_CACHE_HOME`
    still means what it says after this module has been imported."""
    return paths.cache_home() / 'releases.json'


TTL = dt.timedelta(hours=12)
"""How long an answer is worth trusting.

Twice a day is far more often than these tools release and far less often than
`check` runs, which is the whole of the tradeoff. Longer would be defensible;
shorter turns a pre-commit hook into a rate-limit problem.
"""

WORKERS = 8
"""Bounded, because the ceiling here is GitHub's rate limit rather than the CPU.

Unauthenticated that limit is 60 requests an hour, which one unbounded refresh of
every declared release would spend a third of in a second.
"""


@dc.dataclass(frozen=True, slots=True)
class Cached:
    """One repo's newest release tag, and when that was true."""

    version: str
    checked: dt.datetime

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
            entries[key] = Cached(version=record['version'], checked=dt.datetime.fromisoformat(record['checked']))
        except (TypeError, KeyError, ValueError):
            continue
    return entries


def save(entries: dict[str, Cached], path: Path | None = None) -> None:
    """Write the cache, and say nothing if the cache cannot be written.

    A read-only or full `$XDG_CACHE_HOME` must not fail a `check` that has already
    produced its answer — the next run simply measures again.
    """
    payload = {key: {'version': entry.version, 'checked': entry.checked.isoformat()} for key, entry in entries.items()}
    target = path or cache_file()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')
    except OSError:
        return


def refresh(wanted: tuple[Wanted, ...], existing: dict[str, Cached], now: dt.datetime) -> dict[str, Cached]:
    """Ask GitHub about each repo, keeping the previous answer where it cannot.

    Kept rather than dropped: a request that failed says nothing about whether the
    last answer was right, and dropping it would turn one rate-limited refresh into
    a report that every tool is unmeasurable.
    """
    if not wanted:
        return dict(existing)

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        fetched = list(pool.map(lambda item: (item, _newest(item)), wanted))

    entries = dict(existing)
    for item, version in fetched:
        if version:
            entries[item.key] = Cached(version=version, checked=now)
    return entries


def _newest(wanted: Wanted) -> str | None:
    """Whichever endpoint this repo publishes its newest version on.

    Dispatched on the declaration rather than tried in turn: falling back to tags
    when the release lookup fails would read a rate-limited minute as "this project
    tags instead", and start answering a different question with no way to tell.
    """
    if wanted.from_tags:
        return github_release.latest_tag(wanted.repo, wanted.tag_prefix)
    return github_release.latest_version(wanted.repo, wanted.tag_prefix)


def current(wanted: Wanted, entries: dict[str, Cached], now: dt.datetime) -> Cached | None:
    """The cached answer for one repo, or None when there is none worth using."""
    entry = entries.get(wanted.key)
    return entry if entry is not None and entry.fresh(now) else None
