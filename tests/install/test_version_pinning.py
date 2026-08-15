"""A declared pin is what installs, instead of whatever upstream calls latest.

The capability exists so a machine can hold a known-good release while upstream
is broken, and so an older distro can run an older build than the rest of the
fleet. Vocabulary and the reasoning: .planning/version-constraints.md.

Marked e2e where resolving a bare version to a tag means asking the repo which
tags it published. That is not incidental: the constraint is deliberately a bare
version rather than a tag, because the same release is spelled v0.56.0 by lazygit
and cli/v0.9.0 by the personal CLIs, and only the publisher knows which.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from dotfiles import catalog
from dotfiles.providers import ghrelease
from dotfiles.session import Session

PINNED_TOOL = 'lazygit'
PINNED_REPO = 'jesseduffield/lazygit'
PINNED_VERSION = '0.56.0'


def declared(tmp_path: Path, **fields: str) -> catalog.GithubRelease:
    """One release entry, through the real loader so the pin is validated as one."""
    packages = tmp_path / 'packages.yml'
    packages.write_text(yaml.safe_dump({'github_releases': [{'name': PINNED_TOOL, 'repo': PINNED_REPO, **fields}]}))
    entry = catalog.load(packages).find('github_releases', PINNED_TOOL)
    assert isinstance(entry, catalog.GithubRelease)
    return entry


@pytest.mark.e2e
def test_a_pinned_tool_resolves_to_the_pinned_release(tmp_path: Path):
    """The pin is written bare and comes back as the tag the repo publishes."""
    assert ghrelease.resolve_tag(declared(tmp_path, version=PINNED_VERSION)) == f'v{PINNED_VERSION}'


@pytest.mark.e2e
def test_an_unpinned_tool_still_resolves_to_latest(tmp_path: Path):
    """The pin must narrow one entry, not switch the whole catalog into pinned mode."""
    latest = ghrelease.resolve_tag(declared(tmp_path))

    assert latest
    assert latest != f'v{PINNED_VERSION}'


@pytest.mark.e2e
def test_a_pin_no_release_matches_resolves_to_nothing(tmp_path: Path):
    """Falling through to latest is exactly what the pin exists to prevent."""
    entry = declared(tmp_path, version='9999.0.0')

    assert ghrelease.resolve_tag(entry) is None
    assert 'publishes no release for' in ghrelease.unresolved(entry, offline=False)


def test_an_unreadable_catalog_stops_the_phase_rather_than_installing_latest(tmp_path: Path, monkeypatch):
    """No network, and the bug the bash version of this file caught: a failed
    lookup and a declared-nothing lookup both exited 1 there, so swallowing the
    difference installed latest over a pin nobody could see. A raise cannot be
    confused with an empty answer."""
    repo = tmp_path / 'repo'
    (repo / 'install' / 'manifests').mkdir(parents=True)
    (repo / 'install' / 'packages.yml').write_text('github_releases: [unclosed\n')
    (repo / 'install' / 'flags.yml').write_text('{}')
    (repo / 'install' / 'manifests' / 'box.yml').write_text('machine: box\nplatform: linux\n')

    # Asked of `Session.catalog`, which is the one reading of packages.yml a run
    # has — so this is the parse every phase depends on, not a second one that
    # could raise while the real one did not.
    live = Session(machine_name='box', repo=repo, home=tmp_path / 'home')

    with pytest.raises(Exception, match='unclosed|expected|while parsing'):
        _ = live.catalog
