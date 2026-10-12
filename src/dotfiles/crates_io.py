"""The newest version of a crate, read from crates.io's sparse index.

A bare `cargo binstall <crate>` installs the newest version the registry holds,
so that is what a cargo package's currency is measured against. The crate's
GitHub repo is not the same answer. A project can tag a release before
publishing the crate, as broot tagged `v1.61.0` while crates.io held `1.60.2`.
Measured against the tag, such a crate reads as behind on a version no install
can reach, so every `apply` repairs it and no `check` afterwards agrees.

The index serves one static file per crate. It answers `ETag` and 304 the way a
GitHub release does, so a crate that has not published since the last refresh
costs one revalidation. A cold read is the whole file, which for broot is 1.1 MB.
"""

from __future__ import annotations

import json

from dotfiles import github_release
from dotfiles import versions

INDEX = 'https://index.crates.io'


def index_url(crate: str) -> str:
    """Where the index keeps one crate's file.

    Cargo's layout rule: the lowercased name's length picks the directories. One
    or two characters sit under `1/` or `2/`, three under `3/<first letter>/`, and
    anything longer under its first two and next two characters.
    """
    name = crate.lower()
    if len(name) <= 2:
        return f'{INDEX}/{len(name)}/{name}'
    if len(name) == 3:
        return f'{INDEX}/3/{name[0]}/{name}'
    return f'{INDEX}/{name[:2]}/{name[2:4]}/{name}'


def newest_version(crate: str, etag: str = '') -> github_release.Newest:
    """The crate's newest installable version, revalidated against `etag`.

    `github_release.revalidated` carries the request, because its `headers` is
    what keeps a GitHub credential off every other host.
    """
    answer = github_release.revalidated(index_url(crate), etag)
    if answer is None:
        return github_release.Newest()
    if answer.payload is None:
        return github_release.Newest(etag=answer.etag, unchanged=True)
    return github_release.Newest(version=newest_in(answer.payload), etag=answer.etag)


def newest_in(index: bytes) -> str | None:
    """The version a bare `cargo binstall` chooses: the highest one neither yanked nor a pre-release.

    Ranked rather than read off the last line. The file is in publish order, so a
    patch backported to an older minor after a newer one shipped is last and is
    not the newest.
    """
    ranked = []
    for line in index.splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict) or row.get('yanked'):
            continue
        version = row.get('vers')
        if not isinstance(version, str) or '-' in version.partition('+')[0]:
            continue
        if (parsed := versions.parse(version)) is not None:
            ranked.append((parsed, version))
    return max(ranked)[1] if ranked else None
