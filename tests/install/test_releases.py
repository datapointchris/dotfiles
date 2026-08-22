"""The cache that lets `check` ask about currency without asking GitHub.

Every seam is a real argument — the cache path and the clock are both parameters —
so nothing here patches `datetime` or `$XDG_CACHE_HOME`. The network is the one
exception, stubbed at `github_release.newest_version` and `newest_tag`, because the
module's whole purpose is to be the thing that does not call them.

Those two rather than `latest_version`: they carry the `ETag` a refresh offers and
the 304 it gets back, and revalidation is a fact about the cache rather than about
the lookup. `tests/install/test_github_release.py` holds the transport half.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from dotfiles import github_release
from dotfiles import releases

NOW = dt.datetime(2026, 8, 8, 12, 0, tzinfo=dt.UTC)


def cache(tmp_path: Path) -> Path:
    return tmp_path / 'releases.json'


# ─────────────────────────────────────────────────────────────────────────────
# Reading and writing
# ─────────────────────────────────────────────────────────────────────────────


def test_a_saved_cache_reads_back_as_what_was_written(tmp_path: Path) -> None:
    path = cache(tmp_path)
    releases.save({'owner/repo': releases.Cached('v1.2.3', NOW)}, path)

    assert releases.load(path) == {'owner/repo': releases.Cached('v1.2.3', NOW)}


def test_an_absent_cache_is_no_cache_rather_than_an_error(tmp_path: Path) -> None:
    assert releases.load(cache(tmp_path)) == {}


def test_a_corrupt_cache_is_no_cache_rather_than_an_error(tmp_path: Path) -> None:
    """Re-fetching costs one request. A traceback costs the whole check."""
    path = cache(tmp_path)
    path.write_text('{not json at all')

    assert releases.load(path) == {}


def test_a_cache_of_the_wrong_shape_is_no_cache(tmp_path: Path) -> None:
    path = cache(tmp_path)
    path.write_text('["a list, not a mapping"]')

    assert releases.load(path) == {}


def test_one_unreadable_record_does_not_discard_the_readable_ones(tmp_path: Path) -> None:
    path = cache(tmp_path)
    path.write_text(json.dumps({'good': {'version': 'v1', 'checked': NOW.isoformat()}, 'bad': {'version': 'v2'}}))

    assert set(releases.load(path)) == {'good'}


def test_an_unwritable_cache_does_not_fail_the_run(tmp_path: Path) -> None:
    """The answer is already produced by the time this is called; a full or
    read-only cache directory must not turn it into a failure."""
    blocked = tmp_path / 'a-file'
    blocked.write_text('not a directory')

    assert releases.save({'owner/repo': releases.Cached('v1', NOW)}, blocked / 'releases.json') is False


def test_an_unwritable_cache_is_reported_rather_than_swallowed(tmp_path: Path) -> None:
    """An unwritten cache reads back empty, so every declared release answers
    `UNKNOWN` advising a refresh — and the refresh it advises is this write. The
    machine reports nothing measurable forever with the reason unnamed, which is
    why the failure has to be an answer the caller can read."""
    blocked = tmp_path / 'a-file'
    blocked.write_text('not a directory')
    path = blocked / 'releases.json'

    assert releases.save({'owner/repo': releases.Cached('v1', NOW)}, path) is False
    assert releases.load(path) == {}


def test_a_written_cache_says_it_wrote(tmp_path: Path) -> None:
    assert releases.save({'owner/repo': releases.Cached('v1', NOW)}, cache(tmp_path)) is True


# ─────────────────────────────────────────────────────────────────────────────
# Freshness
# ─────────────────────────────────────────────────────────────────────────────


def test_an_entry_inside_the_ttl_is_fresh() -> None:
    assert releases.Cached('v1', NOW - releases.TTL + dt.timedelta(minutes=1)).fresh(NOW)


def test_an_entry_older_than_the_ttl_is_not() -> None:
    assert not releases.Cached('v1', NOW - releases.TTL - dt.timedelta(minutes=1)).fresh(NOW)


def test_an_expired_entry_answers_nothing_rather_than_its_stale_value(tmp_path: Path) -> None:
    """The rule the whole module exists for: unmeasured is never `ok`. Returning
    the old version would report a tool current on evidence a day out of date."""
    wanted = releases.Wanted('owner/repo')
    entries = {wanted.key: releases.Cached('v1', NOW - releases.TTL - dt.timedelta(hours=1))}

    assert releases.current(wanted, entries, NOW) is None


def test_a_repo_never_asked_about_answers_nothing() -> None:
    assert releases.current(releases.Wanted('owner/repo'), {}, NOW) is None


# ─────────────────────────────────────────────────────────────────────────────
# The cache key
# ─────────────────────────────────────────────────────────────────────────────


def test_two_clis_in_one_monorepo_do_not_share_a_cache_entry() -> None:
    """Four declared releases are CLIs in repos that also release other things.
    Keying on the repo alone would have them overwrite each other's answer."""
    assert releases.Wanted('datapointchris/ichrisbirch', 'cli/').key != releases.Wanted('datapointchris/ichrisbirch').key


def test_a_repo_with_no_prefix_keys_on_its_name_alone() -> None:
    assert releases.Wanted('owner/repo').key == 'owner/repo'


# ─────────────────────────────────────────────────────────────────────────────
# Refreshing
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def answers(monkeypatch: pytest.MonkeyPatch) -> dict[tuple[str, str], str | tuple[str, str]]:
    """What each (repo, prefix) upstream says, keyed as `Wanted` keys it.

    A bare string is a repo offering no `ETag`. A `(version, etag)` pair is one that
    does, and it answers 304 whenever that same etag is offered back — which is the
    only way to write a test about revalidation without a socket.

    Both shapes are wanted rather than one: an entry written before etags were
    stored carries none, and a refresh has to keep working for it.
    """
    replies: dict[tuple[str, str], str | tuple[str, str]] = {}

    def newest(repo: str, prefix: str = '', etag: str = '') -> github_release.Newest:
        reply = replies.get((repo, prefix))
        if reply is None:
            return github_release.Newest()
        version, published = reply if isinstance(reply, tuple) else (reply, '')
        if etag and etag == published:
            return github_release.Newest(etag=etag, unchanged=True)
        return github_release.Newest(version=version, etag=published)

    monkeypatch.setattr(releases.github_release, 'newest_version', newest)
    monkeypatch.setattr(releases.github_release, 'newest_tag', newest)
    return replies


def test_a_refresh_records_what_upstream_said_and_when(answers: dict) -> None:
    answers[('owner/repo', '')] = 'v2.0.0'

    entries = releases.refresh((releases.Wanted('owner/repo'),), {}, NOW)

    assert entries['owner/repo'] == releases.Cached('v2.0.0', NOW)


def test_a_refresh_passes_the_prefix_through(answers: dict) -> None:
    answers[('datapointchris/ichrisbirch', 'cli/')] = 'cli/1.4.0'

    entries = releases.refresh((releases.Wanted('datapointchris/ichrisbirch', 'cli/'),), {}, NOW)

    assert entries['datapointchris/ichrisbirch#cli/'].version == 'cli/1.4.0'


def test_a_repo_that_did_not_answer_keeps_its_previous_entry(answers: dict) -> None:
    """A failed request says nothing about whether the last answer was right.
    Dropping it turns one rate-limited refresh into "nothing is measurable"."""
    yesterday = NOW - dt.timedelta(days=1)
    existing = {'owner/repo': releases.Cached('v1.0.0', yesterday)}

    entries = releases.refresh((releases.Wanted('owner/repo'),), existing, NOW)

    assert entries['owner/repo'] == releases.Cached('v1.0.0', yesterday)


def test_refreshing_nothing_asks_nothing(answers: dict) -> None:
    answers[('owner/repo', '')] = 'v2.0.0'

    assert releases.refresh((), {'owner/repo': releases.Cached('v1', NOW)}, NOW) == {'owner/repo': releases.Cached('v1', NOW)}


def test_the_token_is_resolved_before_the_pool_opens(answers: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    """`functools.cache` releases its lock across the call it is filling, so every
    worker arriving before the first returns spawns its own `gh auth token`.

    Priming on this thread is the only place that can be one call, and it has to
    happen here rather than in the memo — which is why the assertion is about
    `refresh` and not about `github_token`. `tests/install/test_github_release.py`
    holds the measurement of what the memo does without it.
    """
    asked: list[str] = []

    def note() -> str:
        asked.append('gh')
        return ''

    monkeypatch.setattr(releases.github_release, 'github_token', note)
    answers[('owner/repo', '')] = 'v2.0.0'

    releases.refresh((releases.Wanted('owner/repo'),), {}, NOW)

    assert asked == ['gh']


def test_nothing_to_refresh_resolves_no_token(answers: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    """The priming sits below the empty guard, so a run with nothing declared
    spawns nothing — which is what `--package` narrowing to an absent tool does."""
    asked: list[str] = []

    def note() -> str:
        asked.append('gh')
        return ''

    monkeypatch.setattr(releases.github_release, 'github_token', note)

    releases.refresh((), {}, NOW)

    assert asked == []


# ─────────────────────────────────────────────────────────────────────────────
# Revalidating with an ETag
# ─────────────────────────────────────────────────────────────────────────────


def test_a_new_answer_stores_the_etag_it_came_with(answers: dict) -> None:
    """Nothing revalidates on the first refresh. Storing the etag is what makes the
    second one cheap, so an entry that dropped it would never get there."""
    answers[('owner/repo', '')] = ('v2.0.0', 'W/"first"')

    entries = releases.refresh((releases.Wanted('owner/repo'),), {}, NOW)

    assert entries['owner/repo'] == releases.Cached('v2.0.0', NOW, etag='W/"first"')


def test_an_unchanged_answer_keeps_the_version_and_restamps_it(answers: dict) -> None:
    """A 304 sends no body, so the version can only come from what is already held —
    and that is exactly what the 304 asserted is still correct.

    `checked` moves because the answer was confirmed just now. Leaving it would have
    the entry expire against a TTL while being revalidated on every run, which is
    the cache paying for a request and getting no credit for it.
    """
    yesterday = NOW - dt.timedelta(days=1)
    answers[('owner/repo', '')] = ('v2.0.0', 'W/"same"')
    existing = {'owner/repo': releases.Cached('v1.0.0', yesterday, etag='W/"same"')}

    entries = releases.refresh((releases.Wanted('owner/repo'),), existing, NOW)

    assert entries['owner/repo'] == releases.Cached('v1.0.0', NOW, etag='W/"same"')


def test_a_changed_repo_answers_with_the_new_version_despite_the_offer(answers: dict) -> None:
    """The other half of the pair above, and the one the whole branch exists for. An
    etag that no longer matches is a release published since the last refresh."""
    answers[('owner/repo', '')] = ('v3.0.0', 'W/"second"')
    existing = {'owner/repo': releases.Cached('v1.0.0', NOW, etag='W/"first"')}

    entries = releases.refresh((releases.Wanted('owner/repo'),), existing, NOW)

    assert entries['owner/repo'] == releases.Cached('v3.0.0', NOW, etag='W/"second"')


def test_each_repo_is_asked_with_its_own_etag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Offered per entry, never one etag for the run. Sending another repo's tag
    would have GitHub compare against a body from a different project, which cannot
    match and quietly costs the full response every time."""
    asked: dict[str, str] = {}

    def newest(repo: str, prefix: str = '', etag: str = '') -> github_release.Newest:
        asked[repo] = etag
        return github_release.Newest(version='v9', etag='W/"x"')

    monkeypatch.setattr(releases.github_release, 'newest_version', newest)
    existing = {'owner/has': releases.Cached('v1', NOW, etag='W/"held"'), 'owner/none': releases.Cached('v1', NOW)}

    releases.refresh((releases.Wanted('owner/has'), releases.Wanted('owner/none')), existing, NOW)

    assert asked == {'owner/has': 'W/"held"', 'owner/none': ''}


def test_an_unmatched_repo_is_asked_unconditionally(monkeypatch: pytest.MonkeyPatch) -> None:
    """A repo with no entry has nothing to revalidate against, so it costs what it
    always did rather than being skipped."""
    asked: dict[str, str] = {}

    def newest(repo: str, prefix: str = '', etag: str = '') -> github_release.Newest:
        asked[repo] = etag
        return github_release.Newest(version='v1', etag='W/"new"')

    monkeypatch.setattr(releases.github_release, 'newest_version', newest)

    entries = releases.refresh((releases.Wanted('owner/fresh'),), {}, NOW)

    assert asked == {'owner/fresh': ''}
    assert entries['owner/fresh'].version == 'v1'


def test_an_etag_survives_a_save_and_load(tmp_path: Path) -> None:
    path = cache(tmp_path)
    releases.save({'owner/repo': releases.Cached('v1.2.3', NOW, etag='W/"kept"')}, path)

    assert releases.load(path) == {'owner/repo': releases.Cached('v1.2.3', NOW, etag='W/"kept"')}


def test_a_cache_written_before_etags_reads_back_without_one(tmp_path: Path) -> None:
    """Every entry on every machine predates this field, and a cache that would not
    load is a cache that answers UNKNOWN for every declared release at once."""
    path = cache(tmp_path)
    path.write_text(json.dumps({'owner/repo': {'version': 'v1.2.3', 'checked': NOW.isoformat()}}))

    assert releases.load(path) == {'owner/repo': releases.Cached('v1.2.3', NOW, etag='')}


def test_an_entry_with_no_etag_is_written_without_the_key(tmp_path: Path) -> None:
    """A repo offering no `ETag` reads the same on disk as one nobody has asked."""
    path = cache(tmp_path)
    releases.save({'owner/repo': releases.Cached('v1.2.3', NOW)}, path)

    assert 'etag' not in json.loads(path.read_text())['owner/repo']
