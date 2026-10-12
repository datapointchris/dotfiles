"""Reading a crate's newest installable version off crates.io's sparse index.

The transport is stubbed at `github_release.revalidate`, the same seam
`test_github_release.py` uses, so these exercise everything above the socket.
"""

from __future__ import annotations

import json

import httpx2
import pytest

from dotfiles import crates_io
from dotfiles import github_release


def index(*rows: tuple[str, bool]) -> bytes:
    """An index file in publish order: one JSON line per `(version, yanked)`."""
    return b'\n'.join(json.dumps({'name': 'broot', 'vers': version, 'yanked': yanked}).encode() for version, yanked in rows)


@pytest.mark.parametrize(
    ('crate', 'path'),
    [('a', '1/a'), ('fd', '2/fd'), ('bat', '3/b/bat'), ('broot', 'br/oo/broot'), ('Fd-Find', 'fd/-f/fd-find')],
    ids=['one-letter', 'two-letters', 'three-letters', 'longer', 'mixed-case'],
)
def test_a_crate_is_asked_at_the_path_cargo_would_ask(crate: str, path: str) -> None:
    """A wrong path is a 404, which reads as an index that could not be reached on every run."""
    assert crates_io.index_url(crate) == f'https://index.crates.io/{path}'


def test_the_highest_version_wins_over_the_last_published() -> None:
    """A backported patch to an older minor is published last and is not the newest."""
    assert crates_io.newest_in(index(('1.60.0', False), ('1.60.2', False), ('1.59.3', False))) == '1.60.2'


def test_a_yanked_version_is_not_one_an_install_reaches() -> None:
    assert crates_io.newest_in(index(('1.60.2', False), ('1.61.0', True))) == '1.60.2'


@pytest.mark.parametrize(('newer', 'newest'), [('1.61.0-beta.1', '1.60.2'), ('1.61.0+build-7', '1.61.0+build-7')])
def test_a_pre_release_is_skipped_and_build_metadata_is_not_one(newer: str, newest: str) -> None:
    """A bare `cargo binstall` matches `*`, which no pre-release satisfies.

    A `+` suffix is build metadata, so a hyphen inside it is not a pre-release.
    """
    assert crates_io.newest_in(index(('1.60.2', False), (newer, False))) == newest


def test_an_index_with_nothing_installable_answers_none() -> None:
    assert crates_io.newest_in(index(('1.61.0', True), ('2.0.0-rc.1', False)) + b'\n{not json') is None


def revalidating(monkeypatch: pytest.MonkeyPatch, answer: github_release.Conditional | None) -> list[tuple[str, str]]:
    """Answer one `Conditional`, or fail the transport where it is None. Records what was asked."""
    asked: list[tuple[str, str]] = []

    def fake(url: str, etag: str = '') -> github_release.Conditional:
        asked.append((url, etag))
        if answer is None:
            raise httpx2.ConnectError('no route to host')
        return answer

    monkeypatch.setattr(github_release, 'revalidate', fake)
    return asked


def test_the_index_is_revalidated_with_the_offered_etag(monkeypatch: pytest.MonkeyPatch) -> None:
    asked = revalidating(monkeypatch, github_release.Conditional(index(('1.60.2', False)), '"b"'))

    assert crates_io.newest_version('broot', '"a"') == github_release.Newest(version='1.60.2', etag='"b"')
    assert asked == [('https://index.crates.io/br/oo/broot', '"a"')]


def test_an_unchanged_index_says_so_and_names_no_version(monkeypatch: pytest.MonkeyPatch) -> None:
    revalidating(monkeypatch, github_release.Conditional(None, '"a"'))

    assert crates_io.newest_version('broot', '"a"') == github_release.Newest(etag='"a"', unchanged=True)


def test_an_unreachable_index_is_not_an_unchanged_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only an unchanged answer may restamp the cached entry, so a failure must not look like one."""
    revalidating(monkeypatch, None)

    assert crates_io.newest_version('broot') == github_release.Newest()
