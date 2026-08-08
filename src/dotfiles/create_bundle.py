#!/usr/bin/python3
"""Build an offline installation bundle for dotfiles.

Downloads every GitHub release binary, cargo binary, Go binary and install
script a manifest asks for, verifies each against the checksum its release
published, and writes them into one tarball for a machine that cannot reach the
network.

Usage:
    create_bundle.py                                    # wsl-work-workstation, linux-x86_64
    create_bundle.py --platform linux-arm64
    create_bundle.py --manifest archlinux-personal-workstation
    create_bundle.py --no-cache                         # re-download everything
    create_bundle.py --print-path                       # print the tarball path on stdout

Output:
    dotfiles-offline-v{YYYYMMDD}-{manifest}-{os}-{arch}.tar.gz

Runs under the interpreter the CLI runs under, which is the only way it is
reached: `dotfiles bundle create` imports `main` in-process. It was written for
the macOS system python3, still 3.9, back when bash invoked it — and it kept the
stdlib-only rule after `dotfiles_python` stopped ever being that interpreter.
The rule holds for third-party packages, which are still worth not depending on
here; it no longer holds for this package's own modules, which is why the
release assets are read from `providers/releases.py` rather than through a pipe
from twenty-three bash scripts.

Streams: everything a person reads goes to stderr, and stdout carries the
tarball path under --print-path and nothing else, so the build can be piped
into whatever consumes the bundle.
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from dotfiles import catalog
from dotfiles import github_release
from dotfiles import parse_packages
from dotfiles import paths
from dotfiles.coordinates import Arch
from dotfiles.coordinates import OSFamily
from dotfiles.coordinates import Target
from dotfiles.providers import ghrelease
from dotfiles.providers import releases

log = logging.getLogger('create-bundle')

# Assets already downloaded by an earlier build, kept between runs. Regenerable
# from the network, so it belongs in the XDG cache rather than data or state.
CACHE_ROOT = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache')) / 'dotfiles' / 'offline-bundle'

# Long enough that a tool untouched across a few months of rebuilds still hits,
# short enough that superseded versions do not accumulate forever.
CACHE_RETENTION_DAYS = 90

DOWNLOAD_TIMEOUT_SECONDS = 300
DOWNLOAD_ATTEMPTS = 3

# Keep the tail of a failing command's output: a TLS, proxy or "too many errors"
# failure states its cause on the last lines, under however much progress
# preceded it.
FAILURE_DETAIL_MAX_LINES = 25

PLATFORMS = {
    'linux-x86_64': ('linux', 'x86_64'),
    'linux-amd64': ('linux', 'x86_64'),
    'linux-arm64': ('linux', 'arm64'),
    'linux-aarch64': ('linux', 'arm64'),
    'darwin-x86_64': ('darwin', 'x86_64'),
    'macos-x86_64': ('darwin', 'x86_64'),
    'darwin-arm64': ('darwin', 'arm64'),
    'macos-arm64': ('darwin', 'arm64'),
}

BUNDLE_README = """\
Dotfiles Offline Installers
============================

Copy this tarball to ~/ on the target machine, clone the repo, and run the
bootstrap in offline mode — it finds and unpacks the tarball itself:

  git clone https://github.com/datapointchris/dotfiles.git
  cd dotfiles && ./install.sh --machine <name> --offline

Everything comes out of ~/installers. bin/uv and wheels/ are what let the
bootstrap install the CLI with no network at all; the rest is what the CLI
then installs onto the machine.

Directory Structure:
  installers/
  |-- manifest.txt    # every included file, with its version
  |-- checksums.txt   # sha256 of each GitHub release asset, verified here
  |-- README.txt      # this file
  |-- bin/            # the uv binary
  |-- wheels/         # the CLI's own dependency closure
  |-- binaries/       # GitHub release binaries + cargo tools
  |-- go-binaries/    # pre-built Go tool binaries
  `-- scripts/        # install scripts (theme, font, claude-code)

checksums.txt is what lets the installer verify a cached binary without
reaching GitHub. Keep it beside binaries/ — moving or deleting it makes every
GitHub release install fail on a missing checksum.

On a machine that is already built, extracting a newer bundle refreshes
~/installers, but apply skips every tool already present. Move them with:

  dotfiles packages apply --reinstall

Go tools take the bundled binary when proxy.golang.org is unreachable, so
that is how a firewalled machine moves off the version it was built with.
"""


class BundleError(Exception):
    """A failure that should end the build with a message rather than a traceback."""


def parse_platform(target: str) -> tuple[str, str]:
    if target not in PLATFORMS:
        supported = ', '.join(sorted(PLATFORMS))
        raise BundleError(f'Unsupported platform: {target}\nSupported: {supported}')
    return PLATFORMS[target]


def bundle_name(manifest: str, os_name: str, arch: str, today: dt.date) -> str:
    """Dated, so two builds of the same manifest are distinguishable."""
    return f'dotfiles-offline-v{today:%Y%m%d}-{manifest}-{os_name}-{arch}'


def rust_triple(os_name: str, arch: str) -> str:
    """The Rust target triple for a platform, which is how cargo tools and uv both
    name their release assets."""
    machine = 'aarch64' if arch == 'arm64' else 'x86_64'
    return f'{machine}-apple-darwin' if os_name == 'darwin' else f'{machine}-unknown-linux-gnu'


def cargo_target(os_name: str, arch: str, linux_override: str = '', darwin_override: str = '') -> str:
    """The Rust target triple in a cargo tool's asset name.

    The overrides exist for tools whose assets are not named after the triple at
    all — fnm ships fnm-linux.zip and fnm-macos.zip.
    """
    if os_name == 'darwin' and darwin_override:
        return darwin_override
    if os_name != 'darwin' and linux_override:
        return linux_override
    return rust_triple(os_name, arch)


def expand_pattern(pattern: str, version: str, os_name: str, arch: str, target: str = '') -> str:
    """The placeholder set is the union of every naming scheme upstreams use:
    the kernel name, the Go spelling, capitalised variants (gum, lazydocker),
    and the product name for Apple (jira-cli ships macOS, not darwin).
    """
    version_num = version.lstrip('v')
    replacements = {
        '{version}': version,
        '{version_num}': version_num,
        '{target}': target,
        '{os}': os_name,
        '{arch}': arch,
        '{go_arch}': 'amd64' if arch == 'x86_64' else 'arm64',
        '{Os}': 'Linux' if os_name == 'linux' else 'Darwin',
        '{Arch}': arch,
        '{os_mac}': 'linux' if os_name == 'linux' else 'macOS',
        '{Os_mac}': 'Linux' if os_name == 'linux' else 'macOS',
        '{platform}': 'linux' if os_name == 'linux' else 'apple_darwin',
    }
    expanded = pattern
    for placeholder, value in replacements.items():
        expanded = expanded.replace(placeholder, value)
    return expanded


@dataclass(frozen=True)
class Asset:
    """One downloadable file, and what it *is* rather than where it came from.

    The cache used to key on the URL. That is the same thing only for as long as
    an asset has exactly one URL — and the release API hands back a
    `browser_download_url` whose host varies, so the moment anything resolves a
    download that way the key starts depending on which server answered and every
    warm entry misses. The identity is the release coordinate; the URL is one way
    to reach it.
    """

    url: str
    key: tuple[str, ...]

    @property
    def filename(self) -> str:
        return self.url.rsplit('/', 1)[-1]

    @property
    def release(self) -> tuple[str, str] | None:
        """The (repo, tag) this came from, for the assets that have one."""
        return (self.key[1], self.key[2]) if self.key[0] == 'github' else None


def github_asset(repo: str, tag: str, name: str) -> Asset:
    return Asset(url=f'https://github.com/{repo}/releases/download/{tag}/{name}', key=('github', repo, tag, name))


def release_asset(url: str) -> Asset:
    """Recover the release coordinate from a URL an installer script printed.

    The scripts emit a URL because that is what bash can pass through a pipe.
    Parsing it back is not a bandaid — it is the same parse `github_release`
    already does to verify a checksum, and it is what keeps a cache entry keyed
    on the release rather than on the host that happened to serve it.
    """
    parsed = github_release.parse_release_url(url)
    if parsed is None:
        return url_asset(url)
    repo, tag = parsed
    return github_asset(repo, tag, url.rsplit('/', 1)[-1])


def url_asset(url: str) -> Asset:
    """For a download whose identity really is its URL — a PyPI file, an install script."""
    return Asset(url=url, key=('url', url.split('://', 1)[-1]))


def cache_path_for(key: tuple[str, ...]) -> Path:
    """Where an asset's bytes live in the download cache.

    One directory level per key part so an entry can be read, inspected and
    pruned by repo without a lookup table. Anything outside the portable
    character set becomes an underscore and '..' collapses, so a hostile or
    merely odd name cannot write outside the cache root.
    """
    parts = [re.sub(r'[^A-Za-z0-9._-]', '_', part).replace('..', '__') for part in key]
    return CACHE_ROOT.joinpath(*parts)


def tail_lines(text: str, limit: int = FAILURE_DETAIL_MAX_LINES) -> str:
    """The tail is where a failing command states its cause."""
    lines = [line for line in text.splitlines() if line.strip()]
    return '\n'.join(lines[-limit:])


def fetch_latest_version(repo: str) -> str:
    """The tag of a repo's latest release, as a hard requirement.

    github_release.latest_version returns None for a release it cannot read,
    which is the right answer for an installer deciding whether to update. A
    bundle build has no such fallback: it cannot name the asset without the
    version, so the miss is fatal here.
    """
    tag = github_release.latest_version(repo)
    if not tag:
        raise BundleError(f'Could not fetch version for {repo}')
    return tag


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None

    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            destination.write_bytes(github_release.request(url))
        except (urllib.error.URLError, OSError) as error:
            last_error = error
            if attempt < DOWNLOAD_ATTEMPTS:
                log.warning('Retry %d/%d for %s (%s)', attempt, DOWNLOAD_ATTEMPTS, url, error)
        else:
            return

    raise BundleError(f'Failed to download: {url}\n  error: {last_error}')


def run_installer_script(script: Path, *args: str) -> list[tuple[str, str, str]]:
    """Ask an installer script for its download URLs.

    These scripts stay bash — they are a sequence of shell commands and gain
    nothing from being anything else. Each line is name|version|url.
    """
    result = subprocess.run(
        ['bash', str(script), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise BundleError(f'Could not get URL from {script.name}:\n{tail_lines(result.stderr)}')

    rows = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        fields = line.split('|')
        if len(fields) < 3:
            raise BundleError(f'{script.name} emitted an unreadable row: {line!r}')
        rows.append((fields[0], fields[1], fields[2]))
    return rows


#
# This is why install scripts are excluded. Every one of them is served from an
# unversioned URL (astral.sh/uv/install.sh, the raw.githubusercontent main
# branch), so a URL-keyed hit would pin whatever was current the first time and
# never update. They are also a few KB each, so there is nothing to win.


class DownloadCache:
    def __init__(self, enabled: bool):
        self.enabled = enabled
        self.hits = 0
        self.downloads = 0
        if enabled:
            CACHE_ROOT.mkdir(parents=True, exist_ok=True)

    def digest_file(self, asset: Asset) -> Path:
        cached = cache_path_for(asset.key)
        return cached.with_name(cached.name + '.sha256')

    def status_file(self, asset: Asset) -> Path:
        """What asking upstream for a checksum returned. An answer about one
        immutable asset, so caching it is as safe as caching the asset.
        """
        cached = cache_path_for(asset.key)
        return cached.with_name(cached.name + '.checksum-status')

    def fetch(self, asset: Asset, destination: Path, label: str) -> None:
        """Put an asset at `destination`, from the cache when it is there.

        Prints the per-asset progress line itself, because whether the bytes came
        from the network or the cache is known only here. A build that reads
        identically warm and cold makes a working cache look broken, which is
        exactly how it was first reported.
        """
        cached = cache_path_for(asset.key)
        digest_file = self.digest_file(asset)
        destination.parent.mkdir(parents=True, exist_ok=True)

        if self.enabled and cached.is_file() and digest_file.is_file():
            if github_release.sha256_of(cached) == digest_file.read_text().strip():
                log.info('%s [cached]', label)
                shutil.copyfile(cached, destination)
                # mtime is the clock the retention sweep reads, so a hit has to
                # count as use — otherwise a tool that never changes ages out
                # precisely because the cache kept working for it.
                now = None
                for path in (cached, digest_file, self.status_file(asset)):
                    if path.exists():
                        os.utime(path, now)
                self.hits += 1
                return
            log.warning('    cached copy of %s is corrupt, re-downloading', destination.name)
            self.evict(asset)

        log.info('%s', label)
        download(asset.url, destination)
        self.downloads += 1

        if not self.enabled:
            return

        # Publish through a temp name: an interrupted build must not leave a
        # truncated file that a later build reads as complete. A cache that
        # cannot be written is a slow build, not a failed one, so this never
        # aborts.
        cached.parent.mkdir(parents=True, exist_ok=True)
        try:
            partial = cached.with_name(f'{cached.name}.partial.{os.getpid()}')
            shutil.copyfile(destination, partial)
            partial.replace(cached)
            digest_file.write_text(github_release.sha256_of(cached) + '\n')
        except OSError:
            log.warning('    could not cache %s', destination.name)

    def remember_status(self, asset: Asset, status: str) -> None:
        """Written only once the asset is cached, so a status cannot outlive the
        digest it refers to.
        """
        if not self.enabled or not self.digest_file(asset).is_file():
            return
        self.status_file(asset).write_text(status + '\n')

    def status(self, asset: Asset) -> str | None:
        if not self.enabled or not self.status_file(asset).is_file():
            return None
        return self.status_file(asset).read_text().strip()

    def recorded_digest(self, asset: Asset) -> str:
        return self.digest_file(asset).read_text().strip()

    def evict(self, asset: Asset) -> None:
        cached = cache_path_for(asset.key)
        for path in (cached, self.digest_file(asset), self.status_file(asset)):
            path.unlink(missing_ok=True)

    def prune(self) -> None:
        """Drop entries not used for CACHE_RETENTION_DAYS.

        Ageing on last use rather than on age drops superseded versions while
        leaving a still-current one that simply never changes.
        """
        if not CACHE_ROOT.is_dir():
            return
        cutoff = dt.datetime.now().timestamp() - (CACHE_RETENTION_DAYS * 86400)
        for path in sorted(CACHE_ROOT.rglob('*'), reverse=True):
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
            elif path.is_dir() and not any(path.iterdir()):
                path.rmdir()


class Bundle:
    def __init__(self, staging: Path, os_name: str, arch: str):
        self.staging = staging
        self.os_name = os_name
        self.arch = arch
        self.binaries = staging / 'binaries'
        self.go_binaries = staging / 'go-binaries'
        self.scripts = staging / 'scripts'
        self.bin = staging / 'bin'
        self.wheels = staging / 'wheels'
        self.entries: list[str] = []
        self.checksums: list[str] = []

        for directory in (self.binaries, self.go_binaries, self.scripts, self.bin, self.wheels):
            directory.mkdir(parents=True, exist_ok=True)

    def record(self, category: str, name: str, version: str, filename: str) -> None:
        self.entries.append(f'{category}|{name}|{version}|{filename}')

    def record_checksum(self, digest: str, filename: str) -> None:
        self.checksums.append(f'{digest}  {filename}')

    def write_metadata(self) -> None:
        header = (
            '# Dotfiles Offline Bundle\n'
            f'# Created: {dt.datetime.now():%c}\n'
            f'# Platform: {self.os_name}/{self.arch}\n'
            '#\n'
            '# Format: category|name|version|filename\n'
        )
        (self.staging / 'manifest.txt').write_text(header + '\n'.join(self.entries) + '\n')
        (self.staging / 'checksums.txt').write_text('\n'.join(self.checksums) + ('\n' if self.checksums else ''))
        (self.staging / 'README.txt').write_text(BUNDLE_README)


def verify_against_upstream(bundle: Bundle, cache: DownloadCache, path: Path, asset: Asset) -> None:
    """Check a downloaded asset against the checksum its release published.

    Verification has to happen here. The install machine cannot resolve which
    asset holds the checksum without the release API, and on the network this
    bundle exists for, that API is unreachable — so an unverified bundle would
    force the installer to accept unverified bytes.

    Only digests actually checked against upstream are recorded. Writing one for
    an asset whose release publishes nothing usable would make the installer log
    'verified' for bytes nobody verified.
    """
    parsed = asset.release
    if parsed is None:
        log.warning('    not a GitHub release, no checksum recorded: %s', path.name)
        return
    repo, tag = parsed
    asset_name = asset.filename

    # What upstream publishes for a released tag does not change, so the answer
    # from an earlier build still holds — and it is the expensive half, one API
    # call to find the checksums asset plus one download to read it.
    status = cache.status(asset)
    if status == 'verified':
        bundle.record_checksum(cache.recorded_digest(asset), path.name)
        return
    if status == 'unpublished':
        return

    checksum_asset = github_release.select_checksum_asset(sorted(github_release.release_assets(repo, tag)), asset_name)
    if checksum_asset is None:
        log.warning('    %s publishes no checksums, none recorded', repo)
        cache.remember_status(asset, 'unpublished')
        return

    try:
        checksums_text = github_release.request(f'https://github.com/{repo}/releases/download/{tag}/{checksum_asset}').decode()
    except (urllib.error.URLError, UnicodeDecodeError) as error:
        raise BundleError(f'Failed to download {checksum_asset} from {repo}: {error}') from error

    expected = github_release.checksum_for_asset(
        checksums_text, asset_name, checksum_asset.endswith(github_release.CHECKSUM_SIDECAR_SUFFIXES)
    )
    if expected is None:
        # yq's checksums is an rhash table (name first, then one column per
        # algorithm), which the sha256sum parser cannot read. Its installer does
        # not verify either, so this is no worse than the online path.
        log.warning('    %s has no readable entry for %s, none recorded', checksum_asset, asset_name)
        cache.remember_status(asset, 'unpublished')
        return

    actual = github_release.sha256_of(path)
    if not github_release.digests_match(expected, actual):
        # Bytes that failed against upstream must not be served to the next build.
        cache.evict(asset)
        raise BundleError(f'Checksum mismatch while bundling {asset_name}\n  published:  {expected}\n  downloaded: {actual}')

    bundle.record_checksum(actual, path.name)
    cache.remember_status(asset, 'verified')


def extract_all(archive: tarfile.TarFile, destination: Path) -> None:
    """Unpack a tarball, refusing members that would write outside `destination`.

    The filter is a capability check rather than a version check: it landed in
    3.11.4 and becomes the default in 3.14, but this file also runs under the
    macOS system interpreter, which is still 3.9 and would reject the argument.
    """
    if hasattr(tarfile, 'data_filter'):
        archive.extractall(destination, filter='data')
    else:
        archive.extractall(destination)  # noqa: S202


def repackage_zip_as_tarball(zip_path: Path, tool: str, target: str, version_num: str) -> str:
    """Rewrite a release zip as a standard single-platform tarball.

    So install_from_cache on the target machine needs no zip handling at all.
    Two layouts occur: fat zips (broot) hold every platform in target-named
    subdirectories, and single-platform zips (fnm) hold the bare binary, so the
    subdirectory lookup falls back to searching the whole extraction.

    Returns the tarball's filename; the zip is consumed.
    """
    repackaged = f'{tool}_{version_num}_{target}.tar.gz'
    destination = zip_path.parent / repackaged

    with tempfile.TemporaryDirectory() as workspace:
        extracted = Path(workspace)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extracted)  # noqa: S202

        binary = next((path for path in (extracted / target).glob(tool) if path.is_file()), None)
        if binary is None:
            binary = next((path for path in extracted.rglob(tool) if path.is_file()), None)
        if binary is None:
            raise BundleError(f'Could not find {tool} in {zip_path.name}')

        binary.chmod(0o755)
        with tarfile.open(destination, 'w:gz') as tar:
            tar.add(binary, arcname=binary.name)

    zip_path.unlink()
    return repackaged


def extract_go_binary(archive_path: Path, binary_name: str, destination: Path) -> None:
    """Pull a Go tool's binary out of whatever shape its release ships.

    Some archives name the binary with a platform suffix (gdu_linux_amd64), so
    an exact match is tried before a prefix match.
    """
    if archive_path.name.endswith(('.tar.gz', '.tgz')):
        with tempfile.TemporaryDirectory() as workspace:
            extracted = Path(workspace)
            with tarfile.open(archive_path) as tar:
                extract_all(tar, extracted)

            found = next((path for path in extracted.rglob(binary_name) if path.is_file()), None)
            if found is None:
                found = next((path for path in extracted.rglob(f'{binary_name}_*') if path.is_file()), None)
            if found is None:
                raise BundleError(f'Could not find {binary_name} binary in {archive_path.name}')
            shutil.move(str(found), destination)
    elif archive_path.name.endswith('.gz'):
        with gzip.open(archive_path, 'rb') as source, destination.open('wb') as target:
            shutil.copyfileobj(source, target)
    else:
        shutil.move(str(archive_path), destination)

    destination.chmod(0o755)
    if archive_path.exists() and archive_path != destination:
        archive_path.unlink()


def add_github_releases(bundle: Bundle, cache: DownloadCache, packages: dict, manifest: dict) -> None:
    """Stage every declared release, named by the same functions that install it.

    The bundler used to ask each installer script what it would download, over a
    `name|version|url` pipe, because bash could not hand back anything richer.
    Asking `providers.releases` directly removes that pipe and the twenty-three
    subprocesses behind it — and removes the way a bundle could stage one asset
    while the installer went looking for another.

    The version recorded is the tag without its prefix, which is what
    `ghrelease.resolve_tag` reads back when installing offline. Recording the
    full `cli/v0.9.0` would have the install rebuild it as `cli/cli/v0.9.0`.
    """
    log.info('Downloading GitHub releases...')
    declaration = catalog.load()
    target = Target(OSFamily(bundle.os_name), Arch(bundle.arch))

    for tool in parse_packages.filter_github_releases_by_manifest(packages, manifest):
        entry = declaration.find('github_releases', tool)
        if not isinstance(entry, catalog.GithubRelease):
            raise BundleError(f"packages.yml github_releases entry '{tool}' is not a release entry")

        build = releases.ASSETS.get(tool)
        if build is None:
            raise BundleError(f"packages.yml github_releases entry '{tool}' has no asset function in providers/releases.py")

        tag = ghrelease.resolve_tag(entry)
        if tag is None:
            raise BundleError(f'Could not resolve a release tag for {tool} from {entry.repo}')
        version = tag.removeprefix(entry.release_tag_prefix)

        published = build(tag, target)
        asset = github_asset(entry.repo, tag, published.name)
        destination = bundle.binaries / asset.filename
        cache.fetch(asset, destination, f'  {tool} ({version})')
        verify_against_upstream(bundle, cache, destination, asset)
        bundle.record('binary', tool, version, asset.filename)

        for companion in published.companions:
            extra = url_asset(companion.url)
            extra_destination = bundle.binaries / companion.name
            cache.fetch(extra, extra_destination, f'    extra: {companion.name} ({version})')
            verify_against_upstream(bundle, cache, extra_destination, extra)
            bundle.record('extra', companion.name, version, companion.name)


def add_go_binaries(bundle: Bundle, cache: DownloadCache, packages: dict, manifest: dict) -> None:
    log.info('Downloading Go tool binaries...')

    for row in parse_packages.filter_go_packages_by_manifest(packages, manifest, output_format='binary_info'):
        binary_name, repo, pattern = row.split('|')
        version = fetch_latest_version(repo)
        asset = github_asset(repo, version, expand_pattern(pattern, version, bundle.os_name, bundle.arch))

        archive_path = bundle.go_binaries / asset.filename
        cache.fetch(asset, archive_path, f'  {binary_name} ({version})')
        extract_go_binary(archive_path, binary_name, bundle.go_binaries / binary_name)
        bundle.record('go-binary', binary_name, version, binary_name)


def add_cargo_binaries(bundle: Bundle, cache: DownloadCache, packages: dict, manifest: dict) -> None:
    log.info('Downloading Cargo tool binaries...')

    for row in parse_packages.filter_cargo_packages_by_manifest(packages, manifest, output_format='binary_info'):
        tool, repo, pattern, linux_override, darwin_override = row.split('|')
        version = fetch_latest_version(repo)
        target = cargo_target(bundle.os_name, bundle.arch, linux_override, darwin_override)

        arch_name = 'aarch64' if bundle.arch == 'arm64' else bundle.arch
        filename = expand_pattern(pattern, version, bundle.os_name, arch_name, target)
        asset = github_asset(repo, version, filename)

        destination = bundle.binaries / filename
        cache.fetch(asset, destination, f'  {tool} ({version})')

        if filename.endswith('.zip'):
            filename = repackage_zip_as_tarball(destination, tool, target, version.lstrip('v'))

        bundle.record('cargo', tool, version, filename)


UV_REPO = 'astral-sh/uv'

PYPI_RELEASE = 'https://pypi.org/pypi/{name}/{version}/json'

WHEEL_PLATFORMS = {
    ('linux', 'x86_64'): ('manylinux', 'x86_64'),
    ('linux', 'arm64'): ('manylinux', 'aarch64'),
    ('darwin', 'x86_64'): ('macosx', 'x86_64'),
    ('darwin', 'arm64'): ('macosx', 'arm64'),
}


def python_floor() -> int:
    """The lowest CPython minor this package can be installed on.

    Read from `requires-python` rather than written here, because a number in
    this file is true only until the floor moves — and the symptom of it being
    stale is a bundle quietly carrying wheels for interpreters uv would refuse.
    """
    declared = tomllib.loads(paths.PYPROJECT_FILE.read_text())['project']['requires-python']
    return int(declared.lstrip('>=~^ ').split('.')[1])


def wheel_matches(filename: str, os_name: str, arch: str) -> bool:
    """Whether a wheel can install on the target machine.

    A wheel name ends `-{python}-{abi}-{platform}.whl`. `any` is pure python and
    installs anywhere, which covers all but one of this CLI's dependencies.
    Everything else has to name this OS and architecture. CPython only, because
    uv will not pick a pypy interpreter here; glibc rather than musl, which is
    what every machine on this fleet runs.

    Interpreters below `requires-python` are refused too. pyyaml publishes a
    wheel per CPython version back to 3.8, and carrying all of them was 7MB of an
    8.7MB wheelhouse for interpreters uv could not install this package on.
    """
    if not filename.endswith('.whl'):
        return False
    tags = filename[: -len('.whl')].split('-')
    if len(tags) < 5:
        return False

    python_tag, platform_tag = tags[-3], tags[-1]
    if python_tag.startswith('pp'):
        return False
    if python_tag.startswith('cp') and int(python_tag[3:] or 0) < python_floor():
        return False
    if platform_tag == 'any':
        return True

    family, machine = WHEEL_PLATFORMS[(os_name, arch)]
    return any(
        tag.startswith(family) and (tag.endswith(machine) or (os_name == 'darwin' and tag.endswith('universal2')))
        for tag in platform_tag.split('.')
    )


def declared_closure() -> list[tuple[str, str]]:
    """The CLI's runtime dependencies, pinned, from uv's own lockfile.

    Environment markers are read but deliberately not evaluated. A wheel included
    for a platform that will not install it costs a few KB and uv applies the
    marker itself at install time; a wheel wrongly *excluded* fails the bootstrap
    on the one machine that cannot go and fetch it.
    """
    exported = subprocess.run(
        ['uv', 'export', '--no-default-groups', '--no-emit-project', '--no-hashes', '--no-header', '--no-annotate'],
        cwd=paths.REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if exported.returncode != 0:
        raise BundleError(f'could not read the dependency closure from uv:\n{tail_lines(exported.stderr)}')

    closure = []
    for line in exported.stdout.splitlines():
        requirement = line.split(';')[0].strip()
        if not requirement or requirement.startswith('#') or '==' not in requirement:
            continue
        name, version = requirement.split('==', 1)
        closure.append((name.strip(), version.strip()))
    if not closure:
        raise BundleError('uv export returned no dependencies, so the bundle would install nothing')
    return closure


def add_uv(bundle: Bundle, cache: DownloadCache) -> None:
    """The uv binary, which install.sh copies onto PATH before anything else.

    The bundle carries the binary rather than the installer script every other
    bootstrap uses: astral.sh is unreachable from the network this exists for,
    and a script that downloads uv is no more use there than no script at all.
    """
    log.info('Downloading uv...')
    version = fetch_latest_version(UV_REPO)
    triple = rust_triple(bundle.os_name, bundle.arch)
    asset = github_asset(UV_REPO, version, f'uv-{triple}.tar.gz')

    archive = bundle.bin / asset.filename
    cache.fetch(asset, archive, f'  uv ({version})')
    verify_against_upstream(bundle, cache, archive, asset)

    with tempfile.TemporaryDirectory() as workspace:
        extracted = Path(workspace)
        with tarfile.open(archive) as tar:
            extract_all(tar, extracted)
        binary = next((path for path in extracted.rglob('uv') if path.is_file()), None)
        if binary is None:
            raise BundleError(f'no uv binary inside {asset.filename}')
        shutil.move(str(binary), bundle.bin / 'uv')

    (bundle.bin / 'uv').chmod(0o755)
    archive.unlink()
    bundle.record('uv', 'uv', version, 'uv')


def add_wheels(bundle: Bundle, cache: DownloadCache) -> None:
    """The CLI's own dependency closure, so `uv tool install` needs no index.

    Every version of a platform-specific wheel is taken rather than one chosen
    against a guessed interpreter. The machine's python is whatever it is —
    picking here would be deciding, from the wrong side of a firewall, a fact
    only the target knows.
    """
    log.info("Downloading the CLI's dependency wheels...")

    for name, version in declared_closure():
        payload = json.loads(github_release.request(PYPI_RELEASE.format(name=name, version=version)).decode())
        wheels = [file for file in payload['urls'] if wheel_matches(file['filename'], bundle.os_name, bundle.arch)]
        if not wheels:
            raise BundleError(f'{name} {version} publishes no wheel for {bundle.os_name}/{bundle.arch}')

        for file in wheels:
            asset = url_asset(file['url'])
            destination = bundle.wheels / file['filename']
            cache.fetch(asset, destination, f'  {name} {version}')

            # PyPI publishes the digest alongside the file, so an unverified
            # wheel here would be a supply-chain hole the release assets beside
            # it do not have — and the machine installing from this bundle is
            # the one that cannot check for itself.
            published = file['digests']['sha256']
            actual = github_release.sha256_of(destination)
            if not github_release.digests_match(published, actual):
                cache.evict(asset)
                raise BundleError(f'checksum mismatch for {file["filename"]}\n  published:  {published}\n  downloaded: {actual}')

            bundle.record_checksum(actual, file['filename'])
            bundle.record('wheel', name, version, file['filename'])


def add_install_scripts(bundle: Bundle, packages: dict, manifest: dict) -> None:
    """Install scripts, from two sources.

    Language managers are a hardcoded list because they are bootstrap
    infrastructure, outside the custom_installers model in packages.yml. Custom
    installers opt in with bundle_install_script: true.

    These are never cached: every one is served from an unversioned URL, so a
    URL-keyed hit would pin whatever was current the first time.
    """
    log.info('Downloading install scripts...')

    scripts = [paths.INSTALL_DIR / 'common' / 'language-managers' / 'uv.sh']
    custom_dir = paths.INSTALL_DIR / 'common' / 'custom-installers'
    for tool in parse_packages.filter_custom_installers_by_manifest(packages, manifest, filter_field='bundle_install_script'):
        script = custom_dir / f'{tool}.sh'
        if not script.is_file():
            raise BundleError(f"packages.yml custom_installers entry '{tool}' has no script at {script}")
        scripts.append(script)

    for script in scripts:
        name, version, url = run_installer_script(script, '--print-url')[0]
        filename = f'{name}-install.sh'
        log.info('  %s...', name)
        download(url, bundle.scripts / filename)
        bundle.record('script', name, version, filename)


def build(manifest_name: str, target_platform: str, use_cache: bool, today: dt.date | None = None) -> Path:
    """Build the bundle and return the tarball's path.

    A return value, not a printed side effect: that is the whole reason this
    file is not a shell script.
    """
    os_name, arch = parse_platform(target_platform)

    manifest_file = paths.MANIFESTS_DIR / f'{manifest_name}.yml'
    if not manifest_file.is_file():
        available = '\n'.join(f'  {path.stem}' for path in sorted((paths.MANIFESTS_DIR).glob('*.yml')))
        raise BundleError(f'Manifest not found: {manifest_file}\nAvailable manifests:\n{available}')

    packages = parse_packages.load_packages()
    manifest = parse_packages.load_manifest(manifest_name)

    name = bundle_name(manifest_name, os_name, arch, today or dt.date.today())
    log.info('Creating offline bundle: %s', name)
    log.info('Target platform: %s/%s', os_name, arch)
    log.info('Manifest filter: %s', manifest_name)

    cache = DownloadCache(enabled=use_cache)
    tarball_path = paths.REPO_ROOT / f'{name}.tar.gz'

    with tempfile.TemporaryDirectory() as workspace:
        bundle = Bundle(Path(workspace) / 'installers', os_name, arch)

        add_uv(bundle, cache)
        add_wheels(bundle, cache)
        add_github_releases(bundle, cache, packages, manifest)
        add_go_binaries(bundle, cache, packages, manifest)
        add_cargo_binaries(bundle, cache, packages, manifest)
        add_install_scripts(bundle, packages, manifest)
        bundle.write_metadata()

        log.info('Creating tarball...')
        with tarfile.open(tarball_path, 'w:gz') as tar:
            tar.add(bundle.staging, arcname='installers')

    size_mb = tarball_path.stat().st_size / (1024 * 1024)
    log.info('Bundle created successfully!')
    log.info('  File: %s', tarball_path)
    log.info('  Size: %.1f MB', size_mb)
    log.info('  Downloads: %d', cache.downloads)
    if use_cache:
        log.info('  From cache: %d (%s)', cache.hits, CACHE_ROOT)
    log.info('To use this bundle:')
    log.info('  1. Copy the tarball to ~/ or ~/dotfiles/ on the target machine')
    log.info('  2. Run: ./install.sh --machine <name> --offline')

    # After the tarball, so a build is never delayed or failed by housekeeping.
    if use_cache:
        cache.prune()

    return tarball_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog='create_bundle.py',
        description='Create an offline installation bundle for dotfiles.',
    )
    parser.add_argument('--platform', default='linux-x86_64', help='target platform (default: linux-x86_64)')
    parser.add_argument('--manifest', default='wsl-work-workstation', help='machine manifest to bundle for')
    parser.add_argument('--no-cache', action='store_true', help='re-download every asset, ignoring the download cache')
    parser.add_argument('--print-path', action='store_true', help="print the finished tarball's path on stdout")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stderr)

    try:
        tarball_path = build(args.manifest, args.platform, use_cache=not args.no_cache)
    except BundleError as error:
        log.error('%s', error)
        return 1
    except KeyboardInterrupt:
        log.error('Interrupted')
        return 130

    # Last, so a consumer only ever receives a path whose bundle is complete.
    if args.print_path:
        print(tarball_path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
