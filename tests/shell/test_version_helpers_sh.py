"""version-helpers.sh — comparing two tags, and asking GitHub for the newest.

Version comparison is hand-rolled here and in `src/dotfiles/versions.py`, on
purpose: the alternative is a dependency that has to be installed before the
thing that checks whether anything is installed. Two hand-rolled comparators
means the ordering has to be asserted rather than assumed, which is why the table
below is a table.

The bash one has a single caller left — update.sh comparing a pinned tag against
the newest one from the same repo — so the shapes it is asked about are release
tags, not arbitrary tool output. `versions.py` is what reads a version out of
whatever a tool prints.
"""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest
from shells import REPO
from shells import Shell
from shells import shell_out

LIBRARY = 'install/common/lib/version-helpers.sh'

EQUAL, OLDER, NEWER = 0, 1, 2
"""`version_compare` answers with an exit code, so a caller can write
`if version_compare "$current" "$latest"` and read it as "already current"."""


def compare(current: str, latest: str) -> int:
    return shell_out(f'source "$1"; version_compare "{current}" "{latest}"', str(REPO / LIBRARY)).returncode


def helper(snippet: str, **environment: str) -> Shell:
    return shell_out(f'source "$1"; {snippet}', str(REPO / LIBRARY), **environment)


def stub_curl(directory: Path, body: str) -> str:
    """A `curl` answering with one body, so the lookup runs for real against it.

    The bats version reached api.github.com from inside a container for this,
    which made a parser test depend on neovim's release cadence and a network.
    """
    directory.mkdir(exist_ok=True)
    curl = directory / 'curl'
    curl.write_text(f'#!/usr/bin/env bash\nprintf %s {body!r}\n')
    curl.chmod(curl.stat().st_mode | stat.S_IEXEC)
    return f'{directory}:/usr/bin:/bin'


@pytest.mark.parametrize(
    ('current', 'latest', 'expected'),
    [
        ('1.2.3', '1.2.3', EQUAL),
        ('v1.2.3', 'v1.2.3', EQUAL),
        ('v1.2.3', '1.2.3', EQUAL),
        ('1.2', '1.2', EQUAL),
        ('1.2.3', '1.2.4', OLDER),
        ('1.2.3', '1.3.0', OLDER),
        ('1.2.3', '2.0.0', OLDER),
        ('v1.2.3', '1.2.4', OLDER),
        ('1.2.3', 'v1.2.4', OLDER),
        ('1.2', '1.3', OLDER),
        ('2.0.0', '1.9.9', NEWER),
        # Numeric, not lexical: 10 sorts before 9 as text and after it as a number.
        ('1.10.0', '1.9.0', NEWER),
        ('1.9.0', '1.10.0', OLDER),
        # A tag with a prefix compares as a whole, which is what update.sh hands
        # it — both sides come from one repo, so both carry the same prefix.
        ('cli/v1.2.0', 'cli/v1.2.1', OLDER),
        ('jq-1.8.2', 'jq-1.8.3', OLDER),
    ],
)
def test_the_ordering_matrix(current: str, latest: str, expected: int) -> None:
    assert compare(current, latest) == expected


@pytest.mark.parametrize(('current', 'latest'), [('', '1.2.3'), ('1.2.3', ''), ('', '')])
def test_an_unknown_version_reads_as_older_rather_than_current(current: str, latest: str) -> None:
    """Deliberately not "equal": a version nothing could read must not be reported
    as up to date, because that is the answer that silently stops an update."""
    assert compare(current, latest) == OLDER


def test_the_latest_tag_comes_from_the_release_metadata(tmp_path: Path) -> None:
    path = stub_curl(tmp_path / 'bin', json.dumps({'tag_name': 'v0.11.4'}))

    result = helper('fetch_github_latest_version neovim/neovim', PATH=path)

    assert result.ok
    assert result.stdout.strip() == 'v0.11.4'


def test_a_repo_with_no_release_metadata_fails(tmp_path: Path) -> None:
    path = stub_curl(tmp_path / 'bin', json.dumps({'message': 'Not Found'}))

    result = helper('fetch_github_latest_version invalid/nonexistent-repo-12345', PATH=path)

    assert not result.ok
    assert result.stdout.strip() == ''


@pytest.mark.parametrize('repo', ['', 'invalid-repo-format'])
def test_a_malformed_repo_is_rejected_before_any_request(tmp_path: Path, repo: str) -> None:
    """The stub would answer, so success here would mean the request went out with
    a path that cannot name a repository."""
    path = stub_curl(tmp_path / 'bin', json.dumps({'tag_name': 'v9.9.9'}))

    assert not helper(f'fetch_github_latest_version "{repo}"', PATH=path).ok


def test_a_fetched_tag_compares_against_an_older_one(tmp_path: Path) -> None:
    """The two functions in the arrangement update.sh uses them in."""
    path = stub_curl(tmp_path / 'bin', json.dumps({'tag_name': 'v0.11.4'}))

    result = helper(
        'latest=$(fetch_github_latest_version neovim/neovim); version_compare v0.9.0 "$latest"; echo "$?";'
        ' version_compare "$latest" "$latest"; echo "$?"',
        PATH=path,
    )

    assert result.stdout.split() == [str(OLDER), str(EQUAL)]


def test_a_prefixed_tag_is_picked_out_of_the_release_listing(tmp_path: Path) -> None:
    """`/releases/latest` returns whatever is newest overall, which in a repo whose
    app owns the bare v* tags is never the CLI's release."""
    listing = json.dumps(
        [
            {'draft': False, 'tag_name': 'v9.0.0'},
            {'draft': True, 'tag_name': 'cli/v2.0.0'},
            {'draft': False, 'tag_name': 'cli/v1.4.0'},
        ]
    )
    path = stub_curl(tmp_path / 'bin', listing)

    result = helper('fetch_github_latest_version_prefixed owner/name cli/', PATH=path)

    assert result.stdout.strip() == 'cli/v1.4.0', 'a draft is not a release anyone can download'


@pytest.mark.parametrize(('repo', 'prefix'), [('invalid-repo-format', 'cli/'), ('owner/name', '')])
def test_the_prefixed_fetch_refuses_the_same_malformed_input(tmp_path: Path, repo: str, prefix: str) -> None:
    path = stub_curl(tmp_path / 'bin', json.dumps([{'draft': False, 'tag_name': 'cli/v1.4.0'}]))

    assert not helper(f'fetch_github_latest_version_prefixed "{repo}" "{prefix}"', PATH=path).ok
