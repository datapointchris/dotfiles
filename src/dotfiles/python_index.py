"""What a Python package index holds for one project, read from its PEP 503 page.

A `uv_tools` entry naming an index installs from it, so that index is what its
currency is measured against. The project page carries one anchor per file, and
each filename carries its version, so one request answers both questions asked
here: whether the index lists the project at all, and which version is newest.

The HTML form is read rather than PEP 691's JSON, because HTML is the form every
index must serve and pypiserver serves nothing else.
"""

from __future__ import annotations

import html.parser
import re

import httpx2

from dotfiles import github_release
from dotfiles import versions

FINAL_RELEASE = re.compile(r'^\d+(?:\.\d+)+$')
"""A version uv chooses by default. A pre-release, dev or post release does not match, so none is ranked."""

ARCHIVE_SUFFIXES = ('.tar.gz', '.zip')


def project_url(index_url: str, name: str) -> str:
    """The index's page for one project, under PEP 503's normalized name."""
    return f'{index_url.rstrip("/")}/{normalized(name)}/'


def normalized(name: str) -> str:
    return re.sub(r'[-_.]+', '-', name).lower()


def newest_version(page: str, etag: str = '') -> github_release.Newest:
    """The project's newest final release, revalidated against `etag`.

    A page the index answers 404 for reads as unanswered, the same as one that
    could not be reached, so a cached answer survives either.
    """
    answer = github_release.revalidated(page, etag)
    if answer is None:
        return github_release.Newest()
    if answer.payload is None:
        return github_release.Newest(etag=answer.etag, unchanged=True)
    return github_release.Newest(version=newest_in(answer.payload, project_of(page)), etag=answer.etag)


def lists(page: str) -> bool:
    """Whether the index holds a file of this project that is not yanked.

    False only on an answer: a 404, or a page with no such file. Raises
    `github_release.Unreadable` where the index could not say, because an install
    that went ahead on that silence is the one that lands PyPI's project instead.
    """
    try:
        answer = github_release.revalidate(page)
    except httpx2.HTTPStatusError as refused:
        if refused.response.status_code == github_release.NOT_FOUND:
            return False
        raise github_release.Unreadable.because(f'could not read {page}', refused) from refused
    except httpx2.HTTPError as unreachable:
        raise github_release.Unreadable.because(f'could not reach {page}', unreachable) from unreachable
    return bool(released(answer.payload or b'', project_of(page)))


def newest_in(page: bytes, project: str) -> str | None:
    """The highest final release among the page's files for `project`."""
    ranked = []
    for version in released(page, project):
        if FINAL_RELEASE.match(version) and (parsed := versions.parse(version)) is not None:
            ranked.append((parsed, version))
    return max(ranked)[1] if ranked else None


def released(page: bytes, project: str) -> list[str]:
    """The version of each file on the page that belongs to `project` and is not yanked."""
    reader = Anchors()
    reader.feed(page.decode('utf-8', errors='replace'))
    found = []
    for filename, yanked in reader.files:
        if yanked:
            continue
        dist, version = split_filename(filename)
        if version and normalized(dist) == project:
            found.append(version)
    return found


def split_filename(filename: str) -> tuple[str, str]:
    """A wheel or sdist filename as its distribution and version, or two empty strings.

    A wheel's distribution never holds a hyphen, so its version is the second
    field. An sdist's version is after the last hyphen, which an older sdist's
    unnormalized name needs.
    """
    if filename.endswith('.whl'):
        fields = filename.split('-')
        return (fields[0], fields[1]) if len(fields) >= 5 else ('', '')
    for suffix in ARCHIVE_SUFFIXES:
        if filename.endswith(suffix):
            dist, _, version = filename.removesuffix(suffix).rpartition('-')
            return dist, version
    return '', ''


def project_of(page: str) -> str:
    """The normalized project name a page URL ends in."""
    return normalized(page.rstrip('/').rpartition('/')[2])


class Anchors(html.parser.HTMLParser):
    """Each anchor's text, which PEP 503 makes the filename, and whether it carries `data-yanked`."""

    def __init__(self) -> None:
        super().__init__()
        self.files: list[tuple[str, bool]] = []
        self._open: bool | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == 'a':
            self._open = any(name == 'data-yanked' for name, _ in attrs)
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._open is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == 'a' and self._open is not None:
            self.files.append((''.join(self._text).strip(), self._open))
            self._open = None
