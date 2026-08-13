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

This module has no shell caller and never had one: every path in is an in-process
import, so it runs under whichever interpreter is running the CLI. It carried a
`#!/usr/bin/python3` shebang and a stdlib-only rule for the macOS system python
until 2026-08-08 — an interpreter that could not have run it, since importing the
package reaches PyYAML.
"""

from __future__ import annotations

import argparse
import enum
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
from pathlib import Path

import httpx2

from dotfiles import versions

# Some hosts answer a default client identification with a 403 where they serve
# curl fine.
USER_AGENT = 'curl/8.0 (dotfiles-installer)'

REQUEST_TIMEOUT_SECONDS = 300

# Detached signatures, certificates and sigstore bundles sit beside the
# checksums file and match a naive "*checksum*" search — tflint publishes
# checksums.txt alongside checksums.txt.keyless.sig and checksums.txt.pem, and
# either would compare the asset against a signature.
CHECKSUM_AUX_PATTERN = re.compile(r'\.(sig|asc|pem|gpgsig|bundle|json|crt|cert)$|_hashes_order$|-bsd$', re.IGNORECASE)

CHECKSUM_SIDECAR_SUFFIXES = ('.sha256', '.sha256sum', '.sha256.txt', '.sha256sum.txt')

RELEASE_URL_PATTERN = re.compile(r'^https://github\.com/([^/]+/[^/]+)/releases/download/(.+)/([^/]+)$')


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
    return None


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


def github_token() -> str | None:
    """Private repos need one for both the API and the download; public ones do not."""
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
answers a bearer token it does not recognise with a 400, measured 2026-08-10, and
that is the *polite* failure. The impolite one is that the token was sent at all.
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

    Both of httpx2's sharp edges are stated here rather than inherited, per
    `python.md`: redirects are *not* followed by default, and the default timeout
    is 5s — which a 200MB neovim tarball would meet as a failure.
    """
    headers = {'User-Agent': USER_AGENT}
    if accept:
        headers['Accept'] = accept
    token = github_token()
    if token and authorized_host(url):
        headers['Authorization'] = f'Bearer {token}'

    response = httpx2.get(url, headers=headers, follow_redirects=True, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.content


def release_assets(repo: str, tag: str) -> dict[str, int]:
    """{name: id} for a tag's assets, empty when the release cannot be read."""
    encoded = urllib.parse.quote(tag, safe='')
    try:
        payload = json.loads(request(f'https://api.github.com/repos/{repo}/releases/tags/{encoded}'))
    except (httpx2.HTTPError, json.JSONDecodeError):
        return {}
    return {asset['name']: asset['id'] for asset in payload.get('assets', [])}


def latest_version(repo: str, tag_prefix: str = '') -> str | None:
    """The newest release tag, or the newest one under `tag_prefix`.

    A prefix is not a nicety: four of the declared releases are CLIs living in a
    monorepo that also releases an API and a web app, so `releases/latest` there
    answers with whichever component shipped most recently. Asking it for `icb`
    would report the CLI outdated every time the API released, and current every
    time the API released after it.

    Two assumptions, both load-bearing: releases come back newest-first, so the
    first match is the latest, and a draft is not a release anyone can install.
    """
    if not tag_prefix:
        try:
            payload = json.loads(request(f'https://api.github.com/repos/{repo}/releases/latest'))
        except (httpx2.HTTPError, json.JSONDecodeError):
            return None
        return payload.get('tag_name')

    try:
        releases = json.loads(request(f'https://api.github.com/repos/{repo}/releases?per_page=100'))
    except (httpx2.HTTPError, json.JSONDecodeError):
        return None
    for release in releases:
        tag = release.get('tag_name') or ''
        if not release.get('draft') and tag.startswith(tag_prefix):
            return tag
    return None


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
        payload = json.loads(request(f'https://api.github.com/repos/{repo}/tags?per_page={TAG_PAGE}'))
    except (httpx2.HTTPError, json.JSONDecodeError):
        return None

    best, highest = None, ()
    for entry in payload:
        name = entry.get('name') or ''
        if not name.startswith(tag_prefix):
            continue
        parsed = versions.parse(name)
        if parsed is not None and parsed > highest:
            best, highest = name, parsed
    return best


def tag_for_version(repo: str, version: str, tag_prefix: str = '') -> str | None:
    """The published tag a declared pin means, or None when nothing published it.

    A pin in `packages.yml` is a bare version and never a tag, because the same
    release is spelled `v0.56.0` by lazygit, `0.8.30` by terraformer and
    `cli/v0.9.0` by the personal CLIs — so matching against what the repo
    published is what lets one spelling work everywhere.

    None is a refusal, not a fallback. Answering "latest" for a pin nothing
    matches would defeat the only thing a pin does.
    """
    try:
        releases = json.loads(request(f'https://api.github.com/repos/{repo}/releases?per_page=100'))
    except (httpx2.HTTPError, json.JSONDecodeError):
        return None

    wanted = version.removeprefix('v')
    for release in releases:
        tag = release.get('tag_name') or ''
        if release.get('draft') or not tag.startswith(tag_prefix):
            continue
        if tag.removeprefix(tag_prefix).removeprefix('v') == wanted:
            return tag
    return None


def download_asset(url: str, destination: Path, repo: str = '', tag: str = '', asset_name: str = '') -> bool:
    """The browser URL 404s on a private repo whatever token is presented; only
    the REST asset endpoint serves those, and only with an octet-stream Accept.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)

    if github_token() and repo and tag and asset_name:
        asset_id = release_assets(repo, tag).get(asset_name)
        if asset_id is not None:
            try:
                destination.write_bytes(
                    request(f'https://api.github.com/repos/{repo}/releases/assets/{asset_id}', accept='application/octet-stream')
                )
            except (httpx2.HTTPError, OSError):
                log_warning(f'Asset API download failed for {asset_name}, falling back to the public URL')
            else:
                return True

    try:
        destination.write_bytes(request(url))
    except (httpx2.HTTPError, OSError):
        return False
    return True


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

        checksum_asset = select_checksum_asset(sorted(release_assets(repo, tag)), asset_name)
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
            if not download_asset(browser_url, destination, repo, tag, checksum_asset):
                log_error(f'Failed to download {checksum_asset} from {repo}')
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
