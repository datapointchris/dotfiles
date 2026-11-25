"""The version an install of each declared package would take now, from the source that install reads.

`plan` asks upstream only about a tool already present, because whether it is
behind is its question. A box that has none of them yet, such as an image build
about to install them, needs each install's version before anything installs, to
key a cache on. So every answer here comes from what the installer itself calls,
and the two cannot disagree:

- a GitHub release through `ghrelease.resolve_tag`, its prefix, pin and ceiling included;
- a uv tool on an index through `python_index`, the newest final release `uvtool.install` picks;
- a uv tool from git through `uvtool.release_tag`;
- a Go tool as `go install @latest` resolves it, the highest release the module proxy lists.

A Go tool that names a GitHub release is the one whose answer differs from
`plan`'s. `plan` measures it against that release, and the proxy's list lags a
new tag for a while after it. A cache keyed on the GitHub release would name a
version the build never got, then hold the older one until some other key moved.

Nothing on this box is measured, so the answer is the same on any machine.
"""

from __future__ import annotations

import dataclasses as dc
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor

from dotfiles import catalog
from dotfiles import github_release
from dotfiles import go_proxy
from dotfiles import python_index
from dotfiles.plan import DesiredItem
from dotfiles.providers import ghrelease
from dotfiles.providers import uvtool

WORKERS = 8


class Unresolved(Exception):
    """No version can be named for this entry, and the message says why."""


@dc.dataclass(frozen=True, slots=True)
class Resolved:
    """One declared package and the version an install would take, or why none can be named."""

    name: str
    section: str
    version: str = ''
    why: str = ''

    def as_dict(self) -> dict[str, str]:
        return dc.asdict(self)


def resolve(items: Iterable[DesiredItem]) -> list[Resolved]:
    """Each item's version, asked concurrently and returned by name."""
    wanted = [item for item in items if item.entry is not None]
    # Primed before the pool opens, for the reason `github_release.github_token` records.
    github_release.github_token()
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        found = list(pool.map(resolved, wanted))
    return sorted(found, key=lambda one: one.name)


def resolved(item: DesiredItem) -> Resolved:
    try:
        version = version_of(item.entry)
    except (Unresolved, go_proxy.Unanswered, github_release.Unreadable, uvtool.LockUnreadable) as failed:
        return Resolved(item.name, item.section, why=str(failed))
    return Resolved(item.name, item.section, version=version)


def version_of(entry: catalog.Entry | None) -> str:
    if isinstance(entry, catalog.GithubRelease):
        tag = ghrelease.resolve_tag(entry)
        if tag is None:
            raise Unresolved(f'{entry.repo} publishes no release that matches its declaration')
        return bare(tag.removeprefix(entry.release_tag_prefix))
    if isinstance(entry, catalog.GoTool):
        return bare(entry.version) if entry.version else go_proxy.newest_release(entry.package)
    if isinstance(entry, catalog.UvTool) and entry.index_url:
        if entry.version:
            return entry.version
        newest = python_index.newest_of(python_index.listed(python_index.project_url(entry.index_url, entry.name)))
        if newest is None:
            raise Unresolved(f'the {entry.index} index lists no final release of {entry.name}')
        return newest
    if isinstance(entry, catalog.GitUvTool):
        tag = uvtool.release_tag(entry)
        if tag is None:
            raise Unresolved(f'{entry.repo} has no release, so the install takes its default branch, which names no version')
        return bare(tag)
    section = entry.section if entry is not None else 'this section'
    raise Unresolved(f'nothing here names the version an install from {section} takes')


def bare(version: str) -> str:
    return version.removeprefix('v')
