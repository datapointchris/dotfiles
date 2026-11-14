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

The Go tool is the one whose answer differs from `plan`'s. `plan` measures it
against the GitHub release, and the proxy's list lags a new tag for a while after
it. A cache keyed on the GitHub release would name a version the build never got,
then hold the older one until some other key moved.

Nothing on this box is measured, so the answer is the same on any machine.
"""

from __future__ import annotations

import dataclasses as dc
import json
import re
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor

import httpx2

from dotfiles import catalog
from dotfiles import github_release
from dotfiles import python_index
from dotfiles import routing
from dotfiles import versions
from dotfiles.plan import DesiredItem
from dotfiles.providers import ghrelease
from dotfiles.providers import uvtool

GO_PROXY_URL = f'https://{routing.GO_PROXY}'

NOT_A_MODULE = frozenset({404, 410})
"""How the module proxy answers a path that is not a module: a package inside one, or nothing."""

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
    except (Unresolved, github_release.Unreadable, uvtool.LockUnreadable) as failed:
        return Resolved(item.name, item.section, why=str(failed))
    return Resolved(item.name, item.section, version=version)


def version_of(entry: catalog.Entry | None) -> str:
    if isinstance(entry, catalog.GithubRelease):
        tag = ghrelease.resolve_tag(entry)
        if tag is None:
            raise Unresolved(f'{entry.repo} publishes no release that matches its declaration')
        return bare(tag.removeprefix(entry.release_tag_prefix))
    if isinstance(entry, catalog.GoTool):
        return bare(entry.version) if entry.version else newest_module_release(entry.package)
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


def newest_module_release(package: str) -> str:
    """The version `go install <package>@latest` takes.

    Go finds the module by asking the proxy about the package path and each shorter
    prefix, and the longest one the proxy knows is the module. `latest` is then the
    highest release in that module's version list, or the proxy's `@latest` where
    the list holds no release.
    """
    path = package
    while True:
        try:
            listing = github_release.request(f'{GO_PROXY_URL}/{escaped(path)}/@v/list').decode()
        except httpx2.HTTPStatusError as refused:
            if refused.response.status_code in NOT_A_MODULE and path.count('/') > 1:
                path = path.rsplit('/', 1)[0]
                continue
            raise Unresolved(f'{GO_PROXY_URL} could not name a version of {package} ({refused})') from refused
        except httpx2.HTTPError as unreachable:
            raise Unresolved(f'could not reach {GO_PROXY_URL} for {package} ({unreachable})') from unreachable
        if (newest := highest_release(listing.split())) is not None:
            return bare(newest)
        return bare(proxy_latest(path))


def highest_release(listed: list[str]) -> str | None:
    """The highest version with no pre-release part, which is the one `latest` means."""
    ranked = [
        (parsed, version) for version in listed if '-' not in version.split('+')[0] and (parsed := versions.parse(version)) is not None
    ]
    return max(ranked)[1] if ranked else None


def proxy_latest(path: str) -> str:
    try:
        version = json.loads(github_release.request(f'{GO_PROXY_URL}/{escaped(path)}/@latest')).get('Version', '')
    except (httpx2.HTTPError, ValueError) as failed:
        raise Unresolved(f'{GO_PROXY_URL} lists no release of {path} and its @latest did not answer ({failed})') from failed
    if not version:
        raise Unresolved(f'{GO_PROXY_URL} lists no release of {path} and its @latest names none')
    return version


def escaped(path: str) -> str:
    """A module path as the proxy spells it, each capital letter written as `!` and its lowercase."""
    return re.sub(r'[A-Z]', lambda capital: '!' + capital.group().lower(), path)
