"""Build an offline installation bundle for dotfiles.

Downloads every GitHub release binary, cargo binary, Go binary and install
script a manifest asks for, verifies each against the checksum its release
published, and writes them into one tarball for a machine that cannot reach the
network.

Reached only through `dotfiles bundle create`, which calls `build` directly.

Output:
    dotfiles-offline-v{YYYYMMDD}-{manifest}-{os}-{arch}.tar.gz

It was written for the macOS system python3, still 3.9, back when bash invoked
it, and kept a stdlib-only rule long after `dotfiles_python` stopped ever being
that interpreter. The rule was dropped on 2026-08-08 — it named a constraint no
caller imposes, and this file had long since been importing the package anyway.

Streams: everything a person reads goes to stderr, and stdout carries the
tarball path under --print-path and nothing else, so the build can be piped
into whatever consumes the bundle.
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
import logging
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import tomllib
import zipfile
from dataclasses import dataclass
from pathlib import Path

import httpx2

from dotfiles import catalog
from dotfiles import github_release
from dotfiles import machine as machines
from dotfiles import paths
from dotfiles import resolve
from dotfiles.coordinates import Arch
from dotfiles.coordinates import OSFamily
from dotfiles.coordinates import Target
from dotfiles.providers import cargo
from dotfiles.providers import ghrelease
from dotfiles.providers import gotool
from dotfiles.providers import releases
from dotfiles.providers import toolchain
from dotfiles.resolve import DesiredItem

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

BUNDLE_README = """\
Dotfiles Offline Installers
============================

Copy this tarball to ~/ on the target machine, clone the repo, and run the
bootstrap in offline mode — it finds and unpacks the tarball itself:

  git clone https://github.com/datapointchris/dotfiles.git
  cd dotfiles && ./install.sh --machine <name> --offline
  dotfiles apply --machine <name> --offline

The bootstrap installs the CLI and stops, printing that second line back.
Everything comes out of ~/installers. bin/uv and wheels/ are what let the
bootstrap install the CLI with no network at all; the rest is what the apply
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

On a machine that is already built, `dotfiles bundle stage` unpacks a newer
tarball over this one -- refreshing what it carries, leaving alone what it
does not, and needing none of the bootstrap.

Offline, this manifest is what "latest" means -- a tool older than the version
recorded here reads as out of date, and apply moves it onto the bundled one:

  dotfiles packages apply --offline

Which also means the reverse: a tool this bundle does not carry cannot be
measured offline at all, and says so rather than reporting itself current.

Go tools take the bundled binary when proxy.golang.org is unreachable, so
that is how a firewalled machine moves off the version it was built with.
"""


class BundleError(Exception):
    """A failure that should end the build with a message rather than a traceback."""


def bundle_name(manifest: str, os_name: str, arch: str, today: dt.date) -> str:
    """Dated, so two builds of the same manifest are distinguishable."""
    return f'dotfiles-offline-v{today:%Y%m%d}-{manifest}-{os_name}-{arch}'


@dataclass(frozen=True)
class BundleAsset:
    """One downloadable file, and what it *is* rather than where it came from.

    The identity is the release coordinate; the URL is one way to reach it. Keying
    the cache on the URL is the same thing only for as long as an asset has exactly
    one — and the release API hands back a `browser_download_url` whose host varies,
    so anything resolving a download that way makes the key depend on which server
    answered and every warm entry misses.
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


def github_asset(repo: str, tag: str, name: str) -> BundleAsset:
    return BundleAsset(url=f'https://github.com/{repo}/releases/download/{tag}/{name}', key=('github', repo, tag, name))


def release_asset(url: str) -> BundleAsset:
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


def url_asset(url: str) -> BundleAsset:
    """For a download whose identity really is its URL — a PyPI file, an install script."""
    return BundleAsset(url=url, key=('url', url.split('://', 1)[-1]))


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
        except (httpx2.HTTPError, OSError) as error:
            last_error = error
            if attempt < DOWNLOAD_ATTEMPTS:
                log.warning('Retry %d/%d for %s (%s)', attempt, DOWNLOAD_ATTEMPTS, url, error)
        else:
            return

    raise BundleError(f'Failed to download: {url}\n  error: {last_error}')


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

    def digest_file(self, asset: BundleAsset) -> Path:
        cached = cache_path_for(asset.key)
        return cached.with_name(cached.name + '.sha256')

    def status_file(self, asset: BundleAsset) -> Path:
        """What asking upstream for a checksum returned. An answer about one
        immutable asset, so caching it is as safe as caching the asset.
        """
        cached = cache_path_for(asset.key)
        return cached.with_name(cached.name + '.checksum-status')

    def fetch(self, asset: BundleAsset, destination: Path, label: str) -> None:
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

    def remember_status(self, asset: BundleAsset, status: str) -> None:
        """Written only once the asset is cached, so a status cannot outlive the
        digest it refers to.
        """
        if not self.enabled or not self.digest_file(asset).is_file():
            return
        self.status_file(asset).write_text(status + '\n')

    def status(self, asset: BundleAsset) -> str | None:
        if not self.enabled or not self.status_file(asset).is_file():
            return None
        return self.status_file(asset).read_text().strip()

    def recorded_digest(self, asset: BundleAsset) -> str:
        return self.digest_file(asset).read_text().strip()

    def evict(self, asset: BundleAsset) -> None:
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


def verify_against_upstream(bundle: Bundle, cache: DownloadCache, path: Path, asset: BundleAsset) -> None:
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
    except (httpx2.HTTPError, UnicodeDecodeError) as error:
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


def add_github_releases(bundle: Bundle, cache: DownloadCache, items: tuple[DesiredItem, ...]) -> None:
    """Stage every declared release, named by the same functions that install it.

    Asked of `providers.releases` directly, rather than of each installer script
    over a `name|version|url` pipe that bash could not hand back anything richer
    than. The pipe costs a subprocess per declared release, and it lets a bundle
    stage one asset while the installer goes looking for another.

    The version recorded is the tag without its prefix, which is what
    `ghrelease.resolve_tag` reads back when installing offline. Recording the
    full `cli/v0.9.0` would have the install rebuild it as `cli/cli/v0.9.0`.
    """
    log.info('Downloading GitHub releases...')
    target = Target(OSFamily(bundle.os_name), Arch(bundle.arch))

    for item in items:
        entry = item.entry
        assert isinstance(entry, catalog.GithubRelease)
        tool = entry.name

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

        for companion in releases.COMPANIONS.get(tool, ()):
            extra = url_asset(companion.url(tag))
            extra_destination = bundle.binaries / companion.name
            cache.fetch(extra, extra_destination, f'    extra: {companion.name} ({version})')
            verify_against_upstream(bundle, cache, extra_destination, extra)
            bundle.record('extra', companion.name, version, companion.name)


def bundleable(items: tuple[DesiredItem, ...]) -> list[catalog.GoTool | catalog.CargoPackage]:
    """The declared entries a bundle can stage, with the rest said out loud.

    An entry with no repo or no `binary_pattern` cannot be staged — there is no
    asset to name — and the machine that installs from this bundle then has no
    source for it at all. The row filter this replaces dropped those silently,
    which is the same information a log line carries and none of the evidence.

    The two sections are named rather than reached through `getattr` defaults,
    which is the same call `precondition_of` was corrected to: a default standing
    in for "this subclass has no such field" answers *unbundleable* for an entry
    whose field was merely renamed, and the symptom is a bundle silently one tool
    short on the machine that cannot fetch it.
    """
    staged = []
    for item in items:
        entry = item.entry
        if isinstance(entry, catalog.GoTool | catalog.CargoPackage) and entry.github_repo and entry.binary_pattern:
            staged.append(entry)
        else:
            log.warning('  %s declares no github_repo/binary_pattern, so nothing is staged for it', item.name)
    return staged


def add_go_binaries(bundle: Bundle, cache: DownloadCache, items: tuple[DesiredItem, ...]) -> None:
    """Stage every declared Go tool's prebuilt binary.

    The asset is named by `providers.gotool.stage`, which is the same module that
    installs from it. Naming it here as well is what went wrong before: the two
    sides expanded `binary_pattern` off different data, so a pattern change moved
    one and not the other, silently, on the one machine the bundle exists for.
    """
    log.info('Downloading Go tool binaries...')
    target = Target(OSFamily(bundle.os_name), Arch(bundle.arch))

    for entry in bundleable(items):
        assert isinstance(entry, catalog.GoTool)
        version = fetch_latest_version(entry.github_repo)
        asset = github_asset(entry.github_repo, version, gotool.stage(entry, version, target))

        archive_path = bundle.go_binaries / asset.filename
        cache.fetch(asset, archive_path, f'  {entry.executable} ({version})')
        extract_go_binary(archive_path, entry.executable, bundle.go_binaries / entry.executable)
        bundle.record('go-binary', entry.executable, version, entry.executable)


def add_cargo_binaries(bundle: Bundle, cache: DownloadCache, items: tuple[DesiredItem, ...]) -> None:
    """Stage every declared Rust CLI's release binary, named by its own provider.

    Recorded under the *crate* name rather than the binary's, because that is what
    `providers.cargo` looks the row up by — a declaration agreeing with itself,
    rather than two halves agreeing by convention.
    """
    log.info('Downloading Cargo tool binaries...')
    target = Target(OSFamily(bundle.os_name), Arch(bundle.arch))

    for entry in bundleable(items):
        assert isinstance(entry, catalog.CargoPackage)
        version = fetch_latest_version(entry.github_repo)
        filename = cargo.stage(entry, version, target)
        asset = github_asset(entry.github_repo, version, filename)

        destination = bundle.binaries / filename
        cache.fetch(asset, destination, f'  {entry.name} ({version})')

        if filename.endswith('.zip'):
            filename = repackage_zip_as_tarball(destination, entry.executable, cargo.asset_target(entry, target), version.lstrip('v'))

        bundle.record('cargo', entry.name, version, filename)


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
    triple = cargo.triple(Target(OSFamily(bundle.os_name), Arch(bundle.arch)))
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


def add_install_scripts(bundle: Bundle, items: tuple[DesiredItem, ...]) -> None:
    """Install scripts, from two sources.

    uv is named here rather than declared, because it is bootstrap infrastructure
    and outside the custom_installers model in packages.yml. Custom installers opt
    in with bundle_install_script: true, and their URL is read from the
    declaration.

    Neither is asked of a bash script over a `name|version|url` pipe any more.
    That pipe was the last thing `install/common/language-managers/uv.sh` existed
    for once the install itself became `providers/toolchain.py`, and it was a
    second place for the bundler and the installer to disagree about which file to
    stage.

    These are never cached: every one is served from an unversioned URL, so a
    URL-keyed hit would pin whatever was current the first time.
    """
    log.info('Downloading install scripts...')

    for item in items:
        entry = item.entry
        assert isinstance(entry, catalog.CustomInstaller)
        if not entry.bundle_install_script:
            continue
        if not entry.install_url:
            raise BundleError(f"packages.yml custom_installers entry '{entry.name}' opts into bundling but declares no install_url")
        log.info('  %s...', entry.name)
        download(entry.install_url, bundle.scripts / f'{entry.name}-install.sh')
        bundle.record('script', entry.name, 'latest', f'{entry.name}-install.sh')

    log.info('  uv...')
    download(toolchain.UV_INSTALL_URL, bundle.scripts / 'uv-install.sh')
    bundle.record('script', 'uv', 'latest', 'uv-install.sh')


def build(manifest_name: str, arch: str, use_cache: bool, today: dt.date | None = None) -> Path:
    """Build the bundle and return the tarball's path.

    A return value, not a printed side effect: that is the whole reason this
    file is not a shell script.

    The OS is read off the manifest and only the CPU is passed in, which is the
    split `Target` already makes: a manifest declares what a machine is, and no
    manifest anywhere says what processor it runs on. Taking both from a caller
    let them contradict each other, and a linux manifest asked for with a darwin
    target built a tarball of the wrong binaries without saying so.
    """
    # The same resolution the install performs, for a machine that is not this one
    # and a target that need not be its own. Asking the resolver rather than
    # re-reading the manifest is what stops the bundle staging one set of tools
    # while `dotfiles apply` on the target goes looking for another — and it is
    # what makes a coordinate the manifest declares (`requires_wsl_host`) narrow
    # the bundle, which the name-list filters this replaces could not see.
    try:
        machine = machines.load(manifest_name)
        plan = resolve.resolve(catalog.load(), machine)
    except (catalog.CatalogError, machines.MachineError) as refused:
        raise BundleError(str(refused)) from refused

    if arch not in set(Arch):
        raise BundleError(f'Unsupported arch: {arch}\nSupported: {", ".join(Arch)}')

    os_name = str(machine.coordinates.os_family)
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
        add_github_releases(bundle, cache, plan.for_section('github_releases'))
        add_go_binaries(bundle, cache, plan.for_section('go_tools'))
        add_cargo_binaries(bundle, cache, plan.for_section('cargo_packages'))
        add_install_scripts(bundle, plan.for_section('custom_installers'))
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
    log.info('  2. Bootstrap: ./install.sh --machine <name> --offline')
    log.info('  3. Install:   dotfiles apply --machine <name> --offline')

    # After the tarball, so a build is never delayed or failed by housekeeping.
    if use_cache:
        cache.prune()

    return tarball_path
