"""uv-git-tools.sh — the URL parsing and the requirement string.

The library exists so a git-installed Python tool is pinned to a release tag
rather than left tracking a branch. An unpinned install has the tool's own update
notice disabled, and once anything else pins it, `uv tool upgrade` re-resolves
that pin to the same commit forever and reports "already at latest" however far
behind it is — syncer sat eight releases back that way. These pin the two pure
functions that decide whether the receipt comes out pinned.
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest
from shells import source

LIBRARY = 'install/common/lib/uv-git-tools.sh'

ACCEPTED = [
    ('https://github.com/datapointchris/syncer.git', 'datapointchris/syncer'),
    ('https://github.com/datapointchris/relate', 'datapointchris/relate'),
    ('git@github.com:datapointchris/syncer.git', 'datapointchris/syncer'),
    ('git@github.com:datapointchris/syncer', 'datapointchris/syncer'),
    ('https://github.com/datapointchris/syncer/', 'datapointchris/syncer'),
    ('https://github.com/datapointchris/syncer.git/', 'datapointchris/syncer'),
]

REJECTED = [
    'https://gitlab.com/datapointchris/syncer.git',
    'ssh://git@github.com/datapointchris/syncer.git',
    'https://github.com/syncer',
    'https://github.com/org/team/repo',
    'https://github.com/',
    '',
]


def stub_curl(directory: Path, body: str) -> None:
    """A `curl` on PATH that answers with one body.

    The release lookup runs for real against it, rather than replacing the
    function under test with one that returns a tag.
    """
    curl = directory / 'curl'
    curl.write_text(f'#!/usr/bin/env bash\nprintf %s {body!r}\n')
    curl.chmod(curl.stat().st_mode | stat.S_IEXEC)


@pytest.mark.parametrize(('url', 'slug'), ACCEPTED)
def test_a_github_slug_is_recovered_from_every_clone_url_shape(url: str, slug: str) -> None:
    result = source(LIBRARY, f'github_slug_from_url "{url}"')

    assert result.ok
    assert result.stdout.strip() == slug


@pytest.mark.parametrize('url', REJECTED)
def test_anything_that_is_not_an_owner_and_a_name_is_refused(url: str) -> None:
    """Refused rather than echoed: the slug goes straight into a releases API URL,
    so a near-miss queries some other repo's releases instead of failing."""
    result = source(LIBRARY, f'github_slug_from_url "{url}"')

    assert not result.ok
    assert result.stdout == ''


def test_the_release_tag_is_the_pin(fake_bin: Path) -> None:
    stub_curl(fake_bin, '{"tag_name": "v6.0.0"}')

    result = source(LIBRARY, 'uv_git_tool_latest_ref "https://github.com/datapointchris/syncer.git"')

    assert result.ok
    assert result.stdout.strip() == 'v6.0.0'


def test_a_repo_that_has_published_no_release_has_no_pin(fake_bin: Path) -> None:
    stub_curl(fake_bin, '{}')

    result = source(LIBRARY, 'uv_git_tool_latest_ref "https://github.com/datapointchris/keymap-align.git"')

    assert not result.ok
    assert result.stdout.strip() == ''


def test_a_non_github_host_is_refused_before_the_lookup(fake_bin: Path) -> None:
    """The stub would answer with a tag, so success here would mean the host check
    was skipped and some other repo's release used."""
    stub_curl(fake_bin, '{"tag_name": "v9.9.9"}')

    result = source(LIBRARY, 'uv_git_tool_latest_ref "https://gitlab.com/datapointchris/syncer.git"')

    assert not result.ok
    assert result.stdout.strip() == ''


@pytest.mark.parametrize(
    ('tool', 'repo', 'ref'),
    [
        ('syncer', 'https://github.com/datapointchris/syncer.git', 'v6.0.0'),
        ('keymap-align', 'https://github.com/datapointchris/keymap-align.git', 'v1.0.0'),
    ],
)
def test_the_requirement_names_the_tool_ahead_of_the_pinned_url(tool: str, repo: str, ref: str) -> None:
    """uv records the requirement under the tool's own name, which is what makes
    the receipt readable by `uv_tool_pinned_rev`."""
    result = source(LIBRARY, f'uv_git_tool_requirement {tool} "{repo}" {ref}')

    assert result.stdout.strip() == f'{tool} @ git+{repo}@{ref}'
