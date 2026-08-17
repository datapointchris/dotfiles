"""The standing line never claims currency it did not measure.

Written after a scheduler container reported its dotfiles checkout up to date
against a fetch from the day before. `dotfiles update` then pulled a great deal.
Nothing had gone wrong in git: `read` compares HEAD to a remote-tracking ref, and
that ref moves on fetch alone, so a day-old fetch answers about a day-old remote.

The reading was correct and the sentence was not. "Up to date" was the whole
answer a reader took, and the age beside it in parentheses was read as trim.
"""

from __future__ import annotations

import datetime as dt

from dotfiles import checkout

NOW = dt.datetime(2026, 8, 17, 12, 0, tzinfo=dt.UTC)


def position(ahead: int = 0, behind: int = 0, fetched: dt.datetime | None = NOW) -> checkout.Position:
    return checkout.Position(upstream='origin/main', ahead=ahead, behind=behind, fetched=fetched)


def test_a_level_checkout_never_claims_to_be_up_to_date() -> None:
    line = position().describe(NOW)
    assert 'up to date' not in line
    assert 'level with origin/main' in line


def test_a_stale_measurement_asks_for_a_fetch() -> None:
    line = position(fetched=NOW - dt.timedelta(days=1, minutes=1)).describe(NOW)
    assert 'run: dotfiles update' in line
    assert 'fetched 1 day ago' in line


def test_a_fresh_measurement_does_not() -> None:
    line = position(fetched=NOW - dt.timedelta(minutes=5)).describe(NOW)
    assert 'run: dotfiles update' not in line


def test_a_checkout_that_never_fetched_asks_for_one() -> None:
    line = position(fetched=None).describe(NOW)
    assert 'nothing has fetched since the clone' in line
    assert 'run: dotfiles update' in line


def test_being_behind_still_asks_regardless_of_freshness() -> None:
    line = position(behind=3).describe(NOW)
    assert '3 commits behind origin/main' in line
    assert 'run: dotfiles update' in line


def test_unpushed_work_is_reported_without_asking_for_a_fetch() -> None:
    line = position(ahead=2).describe(NOW)
    assert '2 commits ahead of origin/main, unpushed' in line
    assert 'run: dotfiles update' not in line


def test_a_stale_reading_does_not_support_a_converged_mark(monkeypatch) -> None:
    """The row's verdict comes from this bool, and it drew CONVERGED off `behind`
    alone — so the one reading that could not be trusted was the one shown as
    fine."""
    monkeypatch.setattr(checkout, 'read', lambda repo: position(fetched=NOW - dt.timedelta(days=2)))
    line, drifted = checkout.standing(NOW)
    assert drifted, line


def test_a_fresh_level_reading_supports_a_converged_mark(monkeypatch) -> None:
    monkeypatch.setattr(checkout, 'read', lambda repo: position(fetched=NOW))
    _, drifted = checkout.standing(NOW)
    assert not drifted
