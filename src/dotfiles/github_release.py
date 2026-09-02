"""GitHub release asset resolution and checksum verification.

Imported by src/dotfiles/create_bundle.py, which verifies assets while building
an offline bundle, and by the providers, which verify them while installing.
Those were separate implementations — an awk program in the shell library, and
this — of rules subtle enough that a divergence would have gone unnoticed until
a bundle verified differently from a live install. The CLI below outlives the
shell that needed it, because it is how the rules are exercised by hand.

    python -m dotfiles.github_release verify <file> <asset> [repo] [tag]
    python -m dotfiles.github_release parse-url <url>       prints repo|tag, empty if not a release
    python -m dotfiles.github_release checksum-for <file> <asset>
    python -m dotfiles.github_release sha256 <file>

This module has no shell caller: every path in is an in-process import, so it runs
under whichever interpreter is running the CLI. A stdlib-only rule would be a rule
for an interpreter that could not run it anyway, since importing the package
reaches PyYAML.
"""

from __future__ import annotations

import argparse
import enum
import functools
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

import httpx2

from dotfiles import versions

# Named rather than borrowed. Some hosts answer httpx's default identification
# with a 403 where they serve a named agent fine, which is what the string is for
# — but claiming to be `curl/8.0` was solving that by lying. A TLS-inspecting
# proxy fingerprints the handshake and compares it to the agent, and a Python
# client presenting curl's name is a mismatch scored as evasion, which is a thing
# to be asked about rather than a thing to be.
USER_AGENT = 'dotfiles-installer (+https://github.com/datapointchris/dotfiles)'

REQUEST_TIMEOUT_SECONDS = 300

# Detached signatures, certificates and sigstore bundles sit beside the
# checksums file and match a naive "*checksum*" search — tflint publishes
# checksums.txt alongside checksums.txt.keyless.sig and checksums.txt.pem, and
# either would compare the asset against a signature.
CHECKSUM_AUX_PATTERN = re.compile(r'\.(sig|asc|pem|gpgsig|bundle|json|crt|cert)$|_hashes_order$|-bsd$', re.IGNORECASE)

CHECKSUM_SIDECAR_SUFFIXES = ('.sha256', '.sha256sum', '.sha256.txt', '.sha256sum.txt')

CLEARSIGNED_CHECKSUM_PATTERN = re.compile(r'^(sha\d*sums?|checksums?)[\w.-]*\.asc$', re.IGNORECASE)
"""A checksums file published only as PGP clearsigned text, which is readable.

Anchored on the stem so it matches `sha256sum.txt.asc` and never
`syncthing-source-v2.1.3.tar.gz.asc` — the first lists digests inside a signed
wrapper, the second is a detached signature over one tarball. Name alone cannot
prove which, so this is a last resort after the plain scan, and a file that turns
out to be detached yields no digest and falls through to the unverified path
rather than comparing an asset against a signature.

syncthing is why: it publishes `sha256sum.txt.asc` and no unsigned counterpart,
so skipping every `.asc` meant it could not verify and would have had to declare
an exception that was false.
"""

RELEASE_URL_PATTERN = re.compile(r'^https://github\.com/([^/]+/[^/]+)/releases/download/(.+)/([^/]+)$')


class Unreadable(Exception):
    """The release API could not be read, so what upstream published is unknown.

    Raised only where the alternative is a wrong sentence rather than a missing
    one. `tag_for_version` answering None makes the caller say a pin names a
    release that does not exist, which sends whoever reads it to `packages.yml`
    to correct a version that was right — and 60 anonymous API calls an hour is
    fewer than one full install spends.
    """


class Verification(enum.IntEnum):
    """Values are the CLI's exit codes, so the shell library can `case` on `$?`."""

    VERIFIED = 0
    FAILED = 1
    UNPUBLISHED = 2
    """No checksums file among the release's assets. Nothing to check against."""

    UNLISTED = 3
    """A checksums file exists and this asset is not named in it.

    Distinct from both its neighbours, and the distinction is the point. It is
    not FAILED — nothing was compared, so nothing was proven wrong, and deleting
    the download on that basis is what made `yq` uninstallable through the shared
    library. It is not UNPUBLISHED either: something *is* published, so a tool in
    this state is one upstream fix away from being verifiable, and collapsing the
    two would hide that fix when it lands.
    """

    UNREADABLE = 4
    """The release could not be read, so what it publishes is unknown.

    A release that publishes nothing is a fact about upstream and a declaration
    can accept it. This is a fact about the attempt, and no declaration can
    accept it, because it says nothing about the bytes on disk. Collapsing it
    into UNPUBLISHED is how a rate-limited API turns `checksum: unpublished`
    into an unverified install: the asset downloads from the CDN, whose limits
    are separate, and only the verification degrades.
    """


# The [LEVEL] prefixes are what logsift and the log aggregators match on, so
# these lines carry the same ones logging.sh emits rather than bare text.
def log_success(message: str) -> None:
    print(f'[INFO] ✓ {message}', file=sys.stderr)


def log_warning(message: str) -> None:
    print(f'[WARNING] ▲ {message}', file=sys.stderr)


def log_error(message: str) -> None:
    print(f'[ERROR] ✗ {message}', file=sys.stderr)


def parse_release_url(url: str) -> tuple[str, str] | None:
    """(repo, tag), or None for a URL that is not a GitHub release asset.

    The tag may contain slashes (a nested module's `cli/v1.2.0`). None is how a
    caller tells a HashiCorp or other non-GitHub source apart.
    """
    match = RELEASE_URL_PATTERN.match(url)
    return (match.group(1), match.group(2)) if match else None


def select_checksum_asset(asset_names: list[str], asset_name: str) -> str | None:
    """A per-asset sidecar wins outright, naming exactly one file and so never
    ambiguous; the combined goreleaser/coreutils file is the fallback.
    """
    for suffix in CHECKSUM_SIDECAR_SUFFIXES:
        if f'{asset_name}{suffix}' in asset_names:
            return f'{asset_name}{suffix}'

    for name in asset_names:
        if CHECKSUM_AUX_PATTERN.search(name):
            continue
        if re.search(r'checksum|sha256sums?$', name, re.IGNORECASE):
            return name

    signed = sorted(name for name in asset_names if CLEARSIGNED_CHECKSUM_PATTERN.match(name))
    # sha256 ahead of sha1 where a project publishes both, which syncthing does.
    for name in signed:
        if '256' in name:
            return name
    return signed[0] if signed else None


def checksum_for_asset(checksums_text: str, asset_name: str, from_sidecar: bool = False) -> str | None:
    """The digest for an asset, out of a checksums file.

    Three fallbacks, each earned by a real release. A leading path is stripped
    only after an exact match fails, because `sha256sum ./*.tar.gz` in CI records
    ./tool.tar.gz for an asset published as tool.tar.gz. Case is ignored last,
    because GitHub resolves asset paths case-insensitively, so a misspelled
    asset downloads fine and then misses its checksum line — lazygit fetched
    Linux_x86_64 against a recorded linux_x86_64 until its URL was corrected.

    A digest on a line of its own names no asset, so in a combined file it could
    belong to any of them and is only trusted when nothing else is there.
    `from_sidecar` says the file is a per-asset `<asset>.sha256`, whose name
    already settled which asset it describes — ripgrep's Windows sidecars are
    CertUtil output, where the digest is line two of three.
    """
    bare = None
    by_base = None
    by_case = None
    line_count = 0

    for raw_line in checksums_text.splitlines():
        fields = raw_line.rstrip('\r').split()
        if not fields:
            continue
        line_count += 1

        if len(fields) == 1:
            if re.fullmatch(r'[0-9a-fA-F]{64}', fields[0]):
                bare = fields[0]
            continue

        digest = fields[0]
        name = fields[1].lstrip('*')
        if name == asset_name:
            return digest

        base = re.sub(r'^.*[/\\]', '', name)
        if by_base is None and base == asset_name:
            by_base = digest
        if by_case is None and base.lower() == asset_name.lower():
            by_case = digest

    if by_base:
        return by_base
    if by_case:
        return by_case
    return bare if bare and (from_sidecar or line_count == 1) else None


def digests_match(expected: str, actual: str) -> bool:
    return expected.lower() == actual.lower()


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


@functools.cache
def github_token() -> str | None:
    """Private repos need one for both the API and the download; public ones do not.

    **Memoised because `_headers` asks on every request.** A refresh makes one
    request per declared release, so this ran `gh auth token` once per repo — a
    subprocess at roughly 35ms, spawned dozens of times in a run, to answer a
    question whose answer cannot change while that run is going.

    Cached for the life of the process, which is the life of one invocation.
    Nothing rewrites `$GITHUB_TOKEN` after start and `gh` does not rotate a token
    out from under a command. A test that changes either between cases is the one
    caller that needs the old behaviour, and `tests/conftest.py` clears this
    between every test rather than each test remembering to.

    **The memo alone does not make it once per run, and the caller that matters is
    concurrent.** `functools.cache` releases its lock across the call it is filling,
    so every thread arriving before the first returns misses and spawns its own.
    Measured with 73 tasks through 16 workers and a 20ms call: 16 subprocesses.
    `releases.refresh` primes this before it opens its pool, which is what collapses
    it to one.
    """
    token = os.environ.get('GITHUB_TOKEN')
    if token:
        return token
    if shutil.which('gh'):
        result = subprocess.run(['gh', 'auth', 'token'], capture_output=True, text=True, check=False)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    return None


GITHUB_HOSTS = frozenset({'api.github.com', 'github.com'})
"""The only hosts a GitHub credential is ever sent to.

Deliberately excludes the asset CDNs — `objects.githubusercontent.com` and its
siblings — even though a release download lands there. They are S3-backed and
serve a pre-signed URL that needs no credential of ours; `s3.amazonaws.com`
answers a bearer token it does not recognise with a 400, and that is the *polite*
failure. The impolite one is that the token was sent at all.
"""


def authorized_host(url: str) -> bool:
    """Whether this URL is one of ours to authenticate to.

    Equality against a closed set, never a suffix test: `endswith('github.com')`
    is true of `github.com.example.invalid`, so a suffix would hand the token to
    anyone who can register a domain.
    """
    return urllib.parse.urlsplit(url).hostname in GITHUB_HOSTS


def request(url: str, accept: str | None = None) -> bytes:
    """Fetch one URL, sending a credential only where one belongs.

    Sending it on every request this module makes, whatever the host, hands a
    GitHub PAT to `s3.amazonaws.com`, `releases.hashicorp.com`,
    `awscli.amazonaws.com` and `pypi.org` — and S3 rejects the download outright
    because of it.

    **Redirects are the other half, and httpx2 already handles it**: it pops
    `Authorization` whenever the redirect target is not the same origin, which is
    the behaviour a GitHub asset download needs by design — that URL redirects to a
    CDN, and a client that carried the header through would leak the credential on
    the request path that runs most often.

    Both of httpx2's sharp edges are stated here rather than inherited: redirects
    are *not* followed by default, and the default timeout
    is 5s — which a 200MB neovim tarball would meet as a failure.
    """
    response = httpx2.get(url, headers=_headers(url, accept=accept), follow_redirects=True, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.content


def _headers(url: str, accept: str | None = None, etag: str = '') -> dict[str, str]:
    """What every request this module makes carries, built in one place.

    Shared so the credential rule `request` argues is decided once. A second
    header dict assembled beside it is a second place that rule can be got wrong,
    and getting it wrong means a PAT on a host that never needed one.
    """
    headers = {'User-Agent': USER_AGENT}
    if accept:
        headers['Accept'] = accept
    if etag:
        headers['If-None-Match'] = etag
    token = github_token()
    if token and authorized_host(url):
        headers['Authorization'] = f'Bearer {token}'
    return headers


NOT_MODIFIED = 304


@dataclass(frozen=True, slots=True)
class Conditional:
    """One revalidated read: the body, or the news that nothing changed.

    `payload` is None exactly when GitHub answered 304, which is the whole point
    of asking this way — the caller already holds the answer, and GitHub does not
    bill a 304 against the rate limit.
    """

    payload: bytes | None
    etag: str


def revalidate(url: str, etag: str = '') -> Conditional:
    """Fetch one URL, offering an `ETag` so an unchanged answer costs nothing.

    **A 304 is not an error and must be read before `raise_for_status`.** httpx
    raises for anything that is not a 2xx, so letting the status check run first
    turns the cheap answer into an exception and the caller reads "upstream did
    not answer" about a repo that answered perfectly.

    **This buys quota, not wall-clock.** Measured 2026-08-22 over the declared
    releases: a cold refresh spent 65 requests and the revalidated one that followed
    spent 2. A 304 is faster in isolation — 147ms against 222ms median — but across
    `WORKERS` threads that saving does not survive run-to-run variance, and the
    whole sweep timed the same either way. Anyone reaching for this to speed up a
    `plan` is reading it wrong.

    The quota is what it is for. A machine with no `gh` token has 60 GitHub requests
    an hour and more declared releases than that, so 65 does not fit and 2 does.

    An empty `etag` sends no `If-None-Match`, so a cold entry is an ordinary fetch
    and pays an ordinary request.
    """
    response = httpx2.get(url, headers=_headers(url, etag=etag), follow_redirects=True, timeout=REQUEST_TIMEOUT_SECONDS)
    if response.status_code == NOT_MODIFIED:
        return Conditional(payload=None, etag=etag)
    response.raise_for_status()
    return Conditional(payload=response.content, etag=response.headers.get('etag', ''))


def release_assets(repo: str, tag: str) -> dict[str, int] | None:
    """{name: id} for a tag's assets, or None when the release could not be read.

    Three answers rather than two, over the distinction `remote.listed` already
    draws: `{}` is a release that publishes nothing, and None is not knowing.
    """
    encoded = urllib.parse.quote(tag, safe='')
    try:
        payload = json.loads(request(f'https://api.github.com/repos/{repo}/releases/tags/{encoded}'))
    except (httpx2.HTTPError, json.JSONDecodeError):
        return None
    return {asset['name']: asset['id'] for asset in payload.get('assets', [])}


def latest_version(repo: str, tag_prefix: str = '') -> str | None:
    """The newest release tag, or the newest one under `tag_prefix`.

    A prefix is not a nicety: four of the declared releases are CLIs living in a
    monorepo that also releases an API and a web app, so `releases/latest` there
    answers with whichever component shipped most recently. Asking it for `icb`
    would report the CLI outdated every time the API released, and current every
    time the API released after it.

    A draft is not a release anyone can install, so drafts are skipped.

    The matches are ranked rather than taken in the order GitHub sends them.
    That order is neither `created_at` nor `published_at` descending — measured
    2026-08-14, meso answered with `cli/v0.9.1` ahead of `cli/v0.10.0`, which was
    newer by both timestamps, because GitHub ranks the tags as strings. Taking
    the first match therefore froze a tool at 0.9.x the moment it shipped 0.10.0,
    and reported the machine converged while doing it.
    """
    try:
        payload = json.loads(request(_version_url(repo, tag_prefix)))
    except (httpx2.HTTPError, json.JSONDecodeError):
        return None
    return _version_from(payload, tag_prefix)


def _version_url(repo: str, tag_prefix: str) -> str:
    """Which endpoint holds this repo's newest version.

    Shared by the unconditional and the revalidating lookup, because choosing the
    wrong one is silent: `releases/latest` on a monorepo answers about whichever
    component shipped last, which is a version for the wrong project rather than an
    error anything could catch.
    """
    if tag_prefix:
        return f'https://api.github.com/repos/{repo}/releases?per_page=100'
    return f'https://api.github.com/repos/{repo}/releases/latest'


def _version_from(payload: object, tag_prefix: str) -> str | None:
    """The newest tag in a decoded payload, ranked by `_version_key` where a prefix narrows it.

    **Pre-releases are excluded, which the unprefixed sibling gets for free.**
    `/releases/latest` never returns one; this reads `/releases`, which returns
    every one. Filtering `draft` and not `prerelease` let `cli/v0.26.1-rc1` outrank
    `cli/v0.26.0`, because `_version_key` reads the suffix as a fourth component —
    so a machine would be told it was behind, and an install would put a release
    candidate on it. Pre-releases are excluded by default everywhere, and the two
    endpoints agreeing is the point.
    """
    if not tag_prefix:
        return payload.get('tag_name') if isinstance(payload, dict) else None
    if not isinstance(payload, list):
        return None
    published = [release for release in payload if not release.get('draft') and not release.get('prerelease')]
    candidates = [tag for release in published if (tag := release.get('tag_name') or '').startswith(tag_prefix)]
    if not candidates:
        return None
    return max(candidates, key=lambda tag: _version_key(tag, tag_prefix))


@dataclass(frozen=True, slots=True)
class Newest:
    """What one lookup established about a repo's newest version.

    Three outcomes rather than two, and they need different handling. A `version`
    is an answer. `unchanged` says the caller's own stored version still stands and
    is the only case where `version` being None is not a failure. Neither, and
    nothing could be read — which keeps whatever the caller already had, because a
    request that failed says nothing about whether the last answer was right.

    `etag` is what to send next time, and it is empty wherever there is nothing
    worth revalidating against.
    """

    version: str | None = None
    etag: str = ''
    unchanged: bool = False


def newest_version(repo: str, tag_prefix: str = '', etag: str = '') -> Newest:
    """`latest_version`, plus the `ETag` that makes asking again cheap.

    The endpoint is chosen by the prefix for the reason `latest_version` states,
    and both of them revalidate: a monorepo's `releases?per_page=100` is the larger
    payload and therefore the one a 304 saves most.
    """
    answer = _revalidated(_version_url(repo, tag_prefix), etag)
    if answer is None:
        return Newest()
    if answer.payload is None:
        return Newest(etag=answer.etag, unchanged=True)
    try:
        payload = json.loads(answer.payload)
    except json.JSONDecodeError:
        return Newest()
    return Newest(version=_version_from(payload, tag_prefix), etag=answer.etag)


def _revalidated(url: str, etag: str) -> Conditional | None:
    """`revalidate`, answering None where it could not be reached at all.

    The two are told apart by every caller here: a transport failure keeps what the
    caller already holds, and a body that will not parse is the same. Folding them
    into one return is what lets a rate-limited minute read as "this repo publishes
    nothing".
    """
    try:
        return revalidate(url, etag)
    except httpx2.HTTPError:
        return None


def _version_key(tag: str, tag_prefix: str) -> tuple[int, ...]:
    """Rank a tag by its numbers, so 0.10.0 outranks 0.9.1 where a string sort does not."""
    return tuple(int(number) for number in re.findall(r'\d+', tag.removeprefix(tag_prefix)))


TAG_PAGE = 100
"""How many tags one page holds, which is the whole of what `latest_tag` reads.

The newest hundred, and a project that published a hundred tags since its latest
is not one this repo is behind on by a version. Paging further would spend
requests against a rate limit `check` shares with every declared release.
"""


def latest_tag(repo: str, tag_prefix: str = '') -> str | None:
    """The newest *tag*, for a project that tags without publishing releases.

    `aws/aws-cli` is the case and the only one: `releases/latest` answers 404
    while `tags` lists `2.36.19`. Without this its entry could name no repo, and
    an entry naming none is one nothing can say is behind — which for awscli means
    a machine that never moves off whatever it first installed.

    **The greatest by version, never the first.** GitHub documents no ordering for
    this endpoint — it answers newest-first in practice, and has for every
    observation — so comparing rather than trusting the position costs one pass
    over a list already in memory and cannot be wrong if that changes. A tag whose
    name holds no version is skipped rather than guessed at, which is the same rule
    `versions.parse` states.
    """
    try:
        payload = json.loads(request(_tag_url(repo)))
    except (httpx2.HTTPError, json.JSONDecodeError):
        return None
    return _tag_from(payload, tag_prefix)


def _tag_url(repo: str) -> str:
    return f'https://api.github.com/repos/{repo}/tags?per_page={TAG_PAGE}'


def _tag_from(payload: object, tag_prefix: str) -> str | None:
    """The greatest tag by version in a decoded page, never the first in it."""
    if not isinstance(payload, list):
        return None
    best: str | None = None
    highest: tuple[int, ...] = ()
    for entry in payload:
        name = entry.get('name') or ''
        if not name.startswith(tag_prefix):
            continue
        parsed = versions.parse(name)
        if parsed is not None and parsed > highest:
            best, highest = name, parsed
    return best


def newest_tag(repo: str, tag_prefix: str = '', etag: str = '') -> Newest:
    """`latest_tag`, plus the `ETag` that makes asking again cheap."""
    answer = _revalidated(_tag_url(repo), etag)
    if answer is None:
        return Newest()
    if answer.payload is None:
        return Newest(etag=answer.etag, unchanged=True)
    try:
        payload = json.loads(answer.payload)
    except json.JSONDecodeError:
        return Newest()
    return Newest(version=_tag_from(payload, tag_prefix), etag=answer.etag)


def tag_for_version(repo: str, version: str, tag_prefix: str = '') -> str | None:
    """The published tag a declared pin means, or None when nothing published it.

    A pin in `packages.yml` is a bare version and never a tag, because the same
    release is spelled `v0.56.0` by lazygit, `0.8.30` by terraformer and
    `cli/v0.9.0` by the personal CLIs — so matching against what the repo
    published is what lets one spelling work everywhere.

    None is a refusal, not a fallback. Answering "latest" for a pin nothing
    matches would defeat the only thing a pin does.

    A list that could not be read raises rather than answering None, over the
    same distinction `release_assets` draws: not knowing what upstream published
    is not the same finding as upstream having published nothing, and the caller
    renders the second as "publishes no release for that version".
    """
    try:
        releases = json.loads(request(f'https://api.github.com/repos/{repo}/releases?per_page=100'))
    except (httpx2.HTTPError, json.JSONDecodeError) as unreachable:
        raise Unreadable(f'could not read the releases of {repo}, so its published versions are unknown') from unreachable

    wanted = version.removeprefix('v')
    for release in releases:
        tag = release.get('tag_name') or ''
        if release.get('draft') or not tag.startswith(tag_prefix):
            continue
        if tag.removeprefix(tag_prefix).removeprefix('v') == wanted:
            return tag
    return None


@dataclass(frozen=True, slots=True)
class Fetched:
    """Whether one download happened, and why it did not.

    **Truthy on success, so every existing call site is unchanged.** Eleven
    providers test the result of `effects.fetch` with `if` or `if not`, and eight
    test doubles return a bare `True`/`False`. A plain `str` return would have
    inverted every one of them silently — `False` and `''` are both falsy, so a
    double answering `False` would have read as a *successful* fetch. Nothing
    downstream has to change to keep working, and the sites that want the reason
    read one field.

    `reason` is the exception's own text and never a sentence composed here. What a
    reader needs is the string the transport produced — `certificate verify failed:
    unable to get local issuer certificate` is the whole diagnosis of a corporate
    TLS proxy, and no wording invented at this level can stand in for it.
    """

    ok: bool
    reason: str = ''

    def __bool__(self) -> bool:
        return self.ok

    @classmethod
    def failed(cls, problem: Exception) -> Fetched:
        """The reason as a reader needs it: the type, then what it said.

        The type is kept because several of these say nothing on their own —
        `httpx2.ConnectError('')` and a bare `OSError` are both possible, and
        `ConnectError` alone already separates a refused connection from a 404.
        """
        said = str(problem).strip()
        named = type(problem).__name__
        return cls(False, f'{named}: {said}' if said else named)


def download_asset(url: str, destination: Path, repo: str = '', tag: str = '', asset_name: str = '') -> Fetched:
    """The browser URL 404s on a private repo whatever token is presented; only
    the REST asset endpoint serves those, and only with an octet-stream Accept.

    **This is the only place a download's reason exists, so it has to leave here.**
    Both handlers catch `(httpx2.HTTPError, OSError)`, which spans a 404, a captive
    portal's 403, a TLS certificate rejection, a proxy refusal, ENOSPC and EACCES —
    one `False` for all of them makes every "could not download X" in the tree
    generic, because nothing else is left to print. `create_bundle.download` keeps
    its exception for the same reason; this is that shape one level lower, where
    every provider reaches it.

    Two consequences worth naming. `diagnose.explain` already probes on `Permission
    denied` and `No space left`, and neither could ever fire for a download while
    `OSError` was collapsed into the same `False` as an HTTP error. And a private
    repo that fails twice for two different reasons now says both, rather than
    reporting the second as though the first had not happened.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    first = ''

    if github_token() and repo and tag and asset_name:
        # An unreadable release falls through to the public URL, which is the
        # right answer for a download: the asset may well be fetchable when the
        # API is not. Only verification treats not knowing as a refusal.
        published = release_assets(repo, tag) or {}
        asset_id = published.get(asset_name)
        if asset_id is not None:
            try:
                destination.write_bytes(
                    request(f'https://api.github.com/repos/{repo}/releases/assets/{asset_id}', accept='application/octet-stream')
                )
            except (httpx2.HTTPError, OSError) as refused:
                first = Fetched.failed(refused).reason
                log_warning(f'Asset API download failed for {asset_name} ({first}), falling back to the public URL')
            else:
                return Fetched(True)

    try:
        destination.write_bytes(request(url))
    except (httpx2.HTTPError, OSError) as refused:
        answered = Fetched.failed(refused)
        # Both, where the private path was tried and also failed. One reason would
        # be the public URL's, which on a private repo is a 404 that explains
        # nothing about the credentialed attempt that came first.
        return Fetched(False, f'{answered.reason} (asset API first said {first})') if first else answered
    return Fetched(True)


def verify_from_bundle(path: Path, asset_name: str, checksums_file: Path) -> Verification | None:
    """None when the bundle records nothing for this asset, which is the caller's
    signal to fall through to the network. Falling through when it *does* record
    one would defeat the bundle's purpose — it exists because GitHub is
    unreachable, and its digests were checked where they could be.
    """
    expected = checksum_for_asset(checksums_file.read_text(), asset_name)
    if expected is None:
        return None

    actual = sha256_of(path)
    if not digests_match(expected, actual):
        log_error(f'Checksum mismatch for {asset_name} (offline bundle)')
        log_error(f'  bundled:  {expected}')
        log_error(f'  on disk:  {actual}')
        path.unlink(missing_ok=True)
        return Verification.FAILED

    log_success(f'Checksum verified from offline bundle: {asset_name}')
    return Verification.VERIFIED


def verify_release_checksum(
    path: Path,
    asset_name: str,
    repo: str = '',
    tag: str = '',
    bundle_checksums: Path | None = None,
    checksum_url: str = '',
) -> Verification:
    """A mismatch deletes the file, so a retry cannot extract bytes that already
    failed. `checksum_url` names the checksums file directly, for a release not
    hosted on GitHub.
    """
    if bundle_checksums is not None and bundle_checksums.is_file():
        outcome = verify_from_bundle(path, asset_name, bundle_checksums)
        if outcome is not None:
            return outcome
        log_warning(f'Offline bundle records no checksum for {asset_name}')

    from_sidecar = False
    if checksum_url:
        try:
            checksums_text = request(checksum_url).decode()
        except (httpx2.HTTPError, UnicodeDecodeError):
            log_error(f'Failed to download checksums from {checksum_url}')
            return Verification.FAILED
    else:
        if not repo or not tag:
            return Verification.UNPUBLISHED

        published = release_assets(repo, tag)
        if published is None:
            log_error(f'Could not read the release {tag} of {repo}, so its checksums are unknown')
            return Verification.UNREADABLE

        checksum_asset = select_checksum_asset(sorted(published), asset_name)
        if checksum_asset is None:
            return Verification.UNPUBLISHED
        from_sidecar = checksum_asset.endswith(CHECKSUM_SIDECAR_SUFFIXES)

        browser_url = f'https://github.com/{repo}/releases/download/{tag}/{checksum_asset}'
        # A fixed `/tmp/<asset>.checksums` is both writable and guessable by
        # anyone on the box, and `write_bytes` follows a symlink planted there.
        # A stale file another user owns is the quieter half: the write raises,
        # `download_asset` answers False, and every install of that tool fails
        # for good blaming the network.
        with tempfile.TemporaryDirectory(prefix='dotfiles-checksums-') as scratch:
            destination = Path(scratch) / checksum_asset
            # The reason, because the caller renders `FAILED` as "checksum mismatch"
            # and nothing mismatched — the file never arrived. That message has
            # already cost one install that blamed the network, which is what the
            # comment above is about, and a generic failure is why it was believed.
            arrived = download_asset(browser_url, destination, repo, tag, checksum_asset)
            if not arrived:
                log_error(f'Failed to download {checksum_asset} from {repo}: {arrived.reason}')
                return Verification.FAILED
            checksums_text = destination.read_text()

    expected = checksum_for_asset(checksums_text, asset_name, from_sidecar)
    if expected is None:
        log_warning(f'Checksums file has no entry for {asset_name}')
        return Verification.UNLISTED

    actual = sha256_of(path)
    if not digests_match(expected, actual):
        log_error(f'Checksum mismatch for {asset_name}')
        log_error(f'  published:  {expected}')
        log_error(f'  downloaded: {actual}')
        path.unlink(missing_ok=True)
        return Verification.FAILED

    log_success(f'Checksum verified: {asset_name}')
    return Verification.VERIFIED


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='github_release.py', description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest='command', required=True)

    verify = commands.add_parser('verify', help='verify a file against its published checksum (exit 0 ok, 1 failed, 2 none published)')
    verify.add_argument('file', help='the downloaded file to check')
    verify.add_argument('asset', help='the release asset name it was downloaded as')
    verify.add_argument('repo', nargs='?', default='', help='owner/name, omit for a non-GitHub source')
    verify.add_argument('tag', nargs='?', default='', help='release tag the asset belongs to')
    verify.add_argument('--bundle-checksums', default='', help="an offline bundle's checksums.txt to check against first")
    verify.add_argument('--checksum-url', default='', help='name the checksums file directly, for a release not hosted on GitHub')

    parse_url = commands.add_parser('parse-url', help='split a release download URL into repo|tag')
    parse_url.add_argument('url', help='the release download URL')

    checksum_for = commands.add_parser('checksum-for', help="read an asset's digest out of a checksums file")
    checksum_for.add_argument('file', help='the checksums file to read')
    checksum_for.add_argument('asset', help='the asset name to look up')

    sha256 = commands.add_parser('sha256', help="print a file's SHA-256")
    sha256.add_argument('file', help='the file to hash')

    args = parser.parse_args(argv)

    if args.command == 'verify':
        return int(
            verify_release_checksum(
                Path(args.file),
                args.asset,
                args.repo,
                args.tag,
                Path(args.bundle_checksums) if args.bundle_checksums else None,
                args.checksum_url,
            )
        )

    if args.command == 'parse-url':
        parsed = parse_release_url(args.url)
        if parsed:
            print(f'{parsed[0]}|{parsed[1]}')
        return 0

    if args.command == 'checksum-for':
        digest = checksum_for_asset(Path(args.file).read_text(), args.asset)
        if digest:
            print(digest)
        return 0

    print(sha256_of(Path(args.file)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
