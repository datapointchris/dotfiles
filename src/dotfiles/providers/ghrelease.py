"""Installing one GitHub release: the seven steps all twenty-three of them share.

Resolve a tag, name the asset, fetch it, verify it, unpack it, place what came
out, confirm it answers on PATH. `install/common/lib/github-release-installer.sh`
is already exactly this, written twice — once for tarballs and once for zips —
with seven of the tools bypassing both because a bare binary, a gzipped one, a
tree or a second binary did not fit either. Every one of those bypasses skipped
checksum verification silently, which is how `hadolint` and `tenv` came to
install unverified from releases that publish perfectly good checksums.

So the engine is not a translation of that library. It is the same sequence with
the variation moved into `providers.releases.ReleaseArtifact`, where a bare binary is an
`Archive` value rather than a reason to write the sequence again:

    Archive.RAW           the download is the binary
    Archive.GZIP          gunzip it and the result is the binary
    TARBALL / ZIP         unpack, then take `path` out of it, plus any `extras`
    ReleaseArtifact.tree  unpack into ~/.local and symlink `path` out of the tree

Nothing here decides *whether* to install. Its caller does, from a `diff` it
already computed. An engine deciding again would be a second opinion, free to
disagree with the report the user was just shown.
"""

from __future__ import annotations

import enum
import shutil
import tempfile
from pathlib import Path

from dotfiles import catalog
from dotfiles import effects
from dotfiles import github_release
from dotfiles import paths
from dotfiles.coordinates import Target
from dotfiles.output import err_console
from dotfiles.output import warn
from dotfiles.providers import Result
from dotfiles.providers import bin_dir
from dotfiles.providers import bundle
from dotfiles.providers import bundle_file
from dotfiles.providers import local_dir
from dotfiles.providers.releases import ASSETS
from dotfiles.providers.releases import COMPANIONS
from dotfiles.providers.releases import Archive
from dotfiles.providers.releases import ReleaseArtifact

BUNDLE_CHECKSUMS = 'checksums.txt'
BUNDLE_BINARIES = 'binaries'

__all__ = ['Result', 'bin_dir', 'bundle_file', 'install', 'local_dir', 'missing_companions', 'resolve_tag', 'unresolved']


def install(entry: catalog.GithubRelease, target: Target, *, offline: bool = False, tag: str | None = None) -> Result:
    """Put one declared release on this machine.

    `tag` is for a caller that already resolved one to decide *whether* to
    install — passing it back is what keeps that decision from costing a second
    API call, and from being made about a different release than the one that
    then gets installed.

    Every failure returns rather than raises, and names the step it failed at.
    An install stage runs the whole list before reporting, because a broken
    release must not stop the twenty that follow it.
    """
    build = ASSETS.get(entry.name)
    if build is None:
        return Result(False, f'nothing in providers.releases names an asset for {entry.name}')

    tag = tag or resolve_tag(entry, offline=offline)
    if tag is None:
        return Result(False, unresolved(entry, offline=offline))

    asset = build(tag, target)
    url = f'https://github.com/{entry.repo}/releases/download/{tag}/{asset.name}'

    with tempfile.TemporaryDirectory(prefix=f'dotfiles-{entry.name}-') as scratch:
        staging = Path(scratch)
        download = staging / asset.name

        # soft_wrap so a long URL stays one selectable line: Rich's default wrap
        # inserts real newlines, and a download URL is the first thing anyone
        # copies out of a failed install.
        err_console.print(f'{entry.name} {tag}: {url}', soft_wrap=True)
        staged = _stage(download, url, entry.repo, tag, asset.name, offline=offline)
        if staged is None:
            return Result(False, f'could not download {asset.name}')

        refused = _verify(download, asset.name, entry, tag, from_bundle=staged is Staged.BUNDLE, offline=offline)
        if refused:
            return Result(False, refused)

        placed = _place(asset, entry.executable, download, staging)
        if not placed.ok:
            return placed

    missing = _companions(entry.name, tag, offline=offline)
    if missing:
        return Result(False, missing)

    if not shutil.which(entry.executable):
        return Result(False, f'{entry.executable} installed but is not on PATH — is {bin_dir()} in it?')
    return Result(True, f'{entry.name} {tag}')


# ─────────────────────────────────────────────────────────────────────────────
# Which release
# ─────────────────────────────────────────────────────────────────────────────


def resolve_tag(entry: catalog.GithubRelease, *, offline: bool = False) -> str | None:
    """The tag to install, or None when it cannot be decided.

    Three sources, in the order that keeps each honest. Offline reads the bundle,
    because the network that makes a bundle necessary is the same one that blocks
    the release API — and because the asset filename is built from the version, so
    a version fetched live names a file the bundle does not contain the moment
    upstream ships. A pin is matched against published tags rather than spelled as
    one, since the same release is `v0.56.0` for lazygit and `cli/v0.9.0` for the
    personal CLIs. Latest is the default.

    A declared pin that matches no release answers None rather than falling
    through to latest. Falling through is exactly what a pin exists to prevent.
    """
    if offline:
        version = bundle_version(entry.name)
        return f'{entry.release_tag_prefix}{version}' if version else None
    if entry.version:
        return github_release.tag_for_version(entry.repo, entry.version, entry.release_tag_prefix)
    return github_release.latest_version(entry.repo, entry.release_tag_prefix)


def bundle_version(name: str) -> str | None:
    """What version of a tool an offline bundle staged, from its manifest.

    Every category the bundler stages a named tool under, not just this
    provider's: a tool declared here on one machine is a cargo package or a Go
    tool on another, and the question being asked is what the bundle has.
    """
    row = bundle.staged(name, 'binary', 'extra', 'go-binary', 'cargo', 'script')
    return row.version if row and row.version else None


def unresolved(entry: catalog.GithubRelease, *, offline: bool) -> str:
    """Why no tag could be decided, in the caller's words rather than a bare None.

    Public because `create_bundle` resolves a tag itself — to decide what to
    stage for an offline machine — and must report the same reason this would.
    """
    if offline:
        return f'the offline bundle at {paths.BUNDLE_DIR} stages no version of {entry.name}'
    if entry.version:
        return f'pinned to {entry.version}, which {entry.repo} publishes no release for'
    return f'{entry.repo} did not answer with a release'


# ─────────────────────────────────────────────────────────────────────────────
# Fetch and verify
# ─────────────────────────────────────────────────────────────────────────────


class Staged(enum.StrEnum):
    """Where the asset came from, which decides what it is verified against."""

    BUNDLE = 'bundle'
    NETWORK = 'network'


def _stage(download: Path, url: str, repo: str, tag: str, asset_name: str, *, offline: bool) -> Staged | None:
    """Get the asset onto disk, or None if it could not be got.

    The bundle is preferred over the network whenever it holds the asset, not only
    when offline: a staged file was verified against its release when the bundle
    was built, and re-downloading it would spend a request to arrive at the same
    bytes.
    """
    cached = bundle_file(BUNDLE_BINARIES) / asset_name
    if cached.is_file():
        shutil.copy2(cached, download)
        return Staged.BUNDLE

    if offline:
        return None
    return Staged.NETWORK if effects.fetch(url, download, repo=repo, tag=tag, asset_name=asset_name) else None


def _verify(download: Path, asset_name: str, entry: catalog.GithubRelease, tag: str, *, from_bundle: bool, offline: bool) -> str:
    """'' when the asset may be installed, else why it may not.

    `required` is the default and the only state that installs on proof. The two
    exceptions are declared per entry in `packages.yml` and measured against live
    releases by `tests/install/test_release_urls.py`, so an entry claiming one it
    no longer needs fails there rather than quietly skipping verification here.
    """
    checksums = bundle_file(BUNDLE_CHECKSUMS)
    if offline:
        # No fallthrough to the network: it is unreachable by definition, and
        # `verify_release_checksum` would spend its timeout arriving at
        # UNPUBLISHED, which reads as "upstream publishes nothing" and is a lie
        # about why nothing could be checked.
        outcome = github_release.verify_from_bundle(download, asset_name, checksums) if checksums.is_file() else None
        if outcome is None:
            # Either exception excuses this, and the bundle cannot say which:
            # `create_bundle` records only digests it verified upstream, so an
            # entry whose release publishes none is simply absent from that file
            # — indistinguishable from one whose file does not name it. What is
            # *not* excused is `required`, where a missing digest means the
            # bundle failed at the one job it exists for.
            because = f'the offline bundle records no digest for {asset_name}'
            return _permitted(entry, because, catalog.CHECKSUM_UNPUBLISHED, catalog.CHECKSUM_UNLISTED)
        return '' if outcome is github_release.Verification.VERIFIED else f'checksum mismatch against the offline bundle for {asset_name}'

    outcome = github_release.verify_release_checksum(
        download,
        asset_name,
        entry.repo,
        tag,
        bundle_checksums=checksums if from_bundle and checksums.is_file() else None,
    )

    if outcome is github_release.Verification.VERIFIED:
        return ''
    if outcome is github_release.Verification.FAILED:
        return f'checksum mismatch for {asset_name}'
    if outcome is github_release.Verification.UNPUBLISHED:
        return _permitted(entry, f'{entry.repo} publishes no checksum file for {tag}', catalog.CHECKSUM_UNPUBLISHED)
    return _permitted(entry, f"{entry.repo}'s checksums file for {tag} does not name {asset_name}", catalog.CHECKSUM_UNLISTED)


def _permitted(entry: catalog.GithubRelease, because: str, *excused_by: str) -> str:
    """Whether the entry's declaration excuses an unverified install of it.

    Anything the declaration does not name is refused, and `required` is never in
    `excused_by`. That is the whole value of defaulting to it: an install that
    cannot be verified stops, and making it proceed means writing down which
    reason applies, where a test can check the claim against what upstream
    actually publishes.
    """
    if entry.checksum in excused_by:
        warn(f'{because} (declared {entry.checksum}), so {entry.name} installs unverified')
        return ''
    return f'{because}, and {entry.name} does not declare that'


# ─────────────────────────────────────────────────────────────────────────────
# Placement
# ─────────────────────────────────────────────────────────────────────────────


def _place(asset: ReleaseArtifact, executable: str, download: Path, staging: Path) -> Result:
    """Get binaries out of what was downloaded and into `~/.local/bin`."""
    target = bin_dir() / executable
    target.parent.mkdir(parents=True, exist_ok=True)

    if asset.archive is Archive.RAW:
        if not effects.install(download, target):
            return Result(False, _unplaceable(executable, target))
        return Result(True, str(target))

    if asset.archive is Archive.GZIP:
        # Decompressed beside the download rather than onto `target`, because
        # opening the destination for writing is the thing that fails when the
        # destination is running. `install` is what lands it.
        plain = staging / executable
        if not effects.gunzip(download, plain):
            return Result(False, f'{asset.name} did not decompress')
        if not effects.install(plain, target):
            return Result(False, _unplaceable(executable, target))
        return Result(True, str(target))

    if asset.tree:
        return _place_tree(asset, download, target)

    unpacked = staging / 'unpacked'
    if not effects.unpack(download, unpacked):
        return Result(False, f'{asset.name} is neither a tar nor a zip this could open')

    source = unpacked / asset.path
    if not source.is_file():
        return Result(False, f'{asset.name} contains no {asset.path}')
    if not effects.install(source, target):
        return Result(False, _unplaceable(executable, target))

    for extra in asset.extras:
        beside = unpacked / extra
        if not beside.is_file():
            continue
        placed = bin_dir() / Path(extra).name
        if not effects.install(beside, placed):
            return Result(False, _unplaceable(Path(extra).name, placed))

    return Result(True, str(target))


def _unplaceable(executable: str, target: Path) -> str:
    """Why a replace failed, given that a running target is no longer a reason.

    Naming the directory rather than guessing: `install` replaces rather than
    writes through, so ETXTBSY is gone and what is left is a filesystem the user
    cannot write to, or one with no room.
    """
    return f'{executable} downloaded but could not be placed in {target.parent}'


def _place_tree(asset: ReleaseArtifact, download: Path, target: Path) -> Result:
    """Unpack under `~/.local` and link the binary out of the tree.

    The old tree is removed first rather than unpacked over: an upgrade that
    merges two releases leaves the runtime files of both, and neovim's runtime is
    version-locked to its binary.
    """
    root = local_dir() / Path(asset.path).parts[0]
    shutil.rmtree(root, ignore_errors=True)

    if not effects.unpack(download, local_dir()):
        return Result(False, f'{asset.name} did not unpack into {local_dir()}')

    binary = local_dir() / asset.path
    if not binary.is_file():
        return Result(False, f'{asset.name} unpacked without a {asset.path}')

    effects.make_executable(binary)
    target.unlink(missing_ok=True)
    target.symlink_to(binary)
    return Result(True, f'{target} -> {binary}')


def missing_companions(name: str) -> tuple[str, ...]:
    """Which of an entry's companion files are not on disk. A read, and a cheap one.

    `fzf-tmux` is a separate file under `~/.local/bin`, and nothing about the
    binary being current says it is still there — fzf installs cleanly without it
    and then the tmux popup binding does nothing, which surfaces days later at a
    keystroke rather than in any verdict.

    Asks `COMPANIONS` rather than an asset function, so no tag has to be resolved
    and no network is touched: a checker running offline still answers.
    """
    return tuple(companion.name for companion in COMPANIONS.get(name, ()) if not (bin_dir() / companion.name).exists())


def _companions(name: str, tag: str, *, offline: bool) -> str:
    """Fetch the files that ship with a tool without being in its release.

    '' when there is nothing to do or it was done. A companion is not optional,
    which is why a failure here fails the install rather than warning.

    Every companion, never only the absent ones: the caller is placing the binary,
    and a companion is fetched at that binary's tag so the two are a matched pair.
    Whether one is *missing* is `missing_companions`, and it belongs to the
    observation rather than to this.
    """
    for companion in COMPANIONS.get(name, ()):
        destination = bin_dir() / companion.name
        destination.parent.mkdir(parents=True, exist_ok=True)

        url = companion.url(tag)
        cached = bundle_file(BUNDLE_BINARIES) / companion.name
        if cached.is_file():
            shutil.copy2(cached, destination)
        elif offline:
            return f'{companion.name} is not in the offline bundle and cannot be downloaded'
        else:
            arrived = effects.fetch(url, destination)
            if not arrived:
                return f'could not download {companion.name} from {url}: {arrived.reason}'

        effects.make_executable(destination)
    return ''
