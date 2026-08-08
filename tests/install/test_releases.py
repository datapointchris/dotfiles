"""The cache that lets `check` ask about currency without asking GitHub.

Every seam is a real argument — the cache path and the clock are both parameters —
so nothing here patches `datetime` or `$XDG_CACHE_HOME`. The network is the one
exception, stubbed at `github_release.latest_version`, because the module's whole
purpose is to be the thing that does not call it.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

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

    releases.save({'owner/repo': releases.Cached('v1', NOW)}, blocked / 'releases.json')


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
def answers(monkeypatch: pytest.MonkeyPatch) -> dict[tuple[str, str], str | None]:
    replies: dict[tuple[str, str], str | None] = {}
    monkeypatch.setattr(releases.github_release, 'latest_version', lambda repo, prefix='': replies.get((repo, prefix)))
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
