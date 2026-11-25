"""The version `go install <package>@latest` takes, asked of the Go module proxy.

Two readers ask it. `install_versions` names the version an install would take
before anything is installed. `releases` measures a Go tool that publishes no
release against it, because `go install @latest` is that tool's upgrade and the
proxy is where it resolves.

The proxy sends no `ETag`, so each refresh reads the version list in full
rather than revalidating it.
"""

from __future__ import annotations

import json
import re

import httpx2

from dotfiles import github_release
from dotfiles import routing
from dotfiles import versions

PROXY_URL = f'https://{routing.GO_PROXY}'

NOT_A_MODULE = frozenset({404, 410})
"""How the module proxy answers a path that is not a module: a package inside one, or nothing."""


class Unanswered(Exception):
    """The proxy named no version for this package, and the message says why."""


def newest_version(package: str) -> github_release.Newest:
    """The package's newest release as `releases.refresh` reads an answer, or no answer where the proxy gave none."""
    try:
        return github_release.Newest(version=newest_release(package))
    except Unanswered:
        return github_release.Newest()


def newest_release(package: str) -> str:
    """The version `go install <package>@latest` takes.

    Go finds the module by asking the proxy about the package path and each shorter
    prefix, and the longest one the proxy knows is the module. `latest` is then the
    highest release in that module's version list, or the proxy's `@latest` where
    the list holds no release.
    """
    path = package
    while True:
        try:
            listing = github_release.request(f'{PROXY_URL}/{escaped(path)}/@v/list').decode()
        except httpx2.HTTPStatusError as refused:
            if refused.response.status_code in NOT_A_MODULE and path.count('/') > 1:
                path = path.rsplit('/', 1)[0]
                continue
            raise Unanswered(f'{PROXY_URL} could not name a version of {package} ({refused})') from refused
        except httpx2.HTTPError as unreachable:
            raise Unanswered(f'could not reach {PROXY_URL} for {package} ({unreachable})') from unreachable
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
        version = json.loads(github_release.request(f'{PROXY_URL}/{escaped(path)}/@latest')).get('Version', '')
    except (httpx2.HTTPError, ValueError) as failed:
        raise Unanswered(f'{PROXY_URL} lists no release of {path} and its @latest did not answer ({failed})') from failed
    if not version:
        raise Unanswered(f'{PROXY_URL} lists no release of {path} and its @latest names none')
    return version


def escaped(path: str) -> str:
    """A module path as the proxy spells it, each capital letter written as `!` and its lowercase."""
    return re.sub(r'[A-Z]', lambda capital: '!' + capital.group().lower(), path)


def bare(version: str) -> str:
    return version.removeprefix('v')
