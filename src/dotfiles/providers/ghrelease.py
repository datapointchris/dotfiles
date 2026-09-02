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

An eighth step reaches the one release that publishes a daemon rather than a
command: a supervision file, `ReleaseArtifact.unit` out of the archive on Linux and
`releases.AGENTS` written into `~/Library/LaunchAgents` on a Mac. `supervise` is
why that half is here and not in `install/system.yml` — a `systemd_units` row can
narrow on an OS family and on a *system* package, and neither says "the machines
declaring this release", so the row would reach every Linux box in the fleet.

Nothing here decides *whether* to install. Its caller does, from a `diff` it
already computed. An engine deciding again would be a second opinion, free to
disagree with the report the user was just shown.
"""

from __future__ import annotations

import enum
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from dotfiles import catalog
from dotfiles import effects
from dotfiles import github_release
from dotfiles import paths
from dotfiles.coordinates import Arch
from dotfiles.coordinates import OSFamily
from dotfiles.coordinates import Target
from dotfiles.output import err_console
from dotfiles.output import warn
from dotfiles.providers import Kind
from dotfiles.providers import Located
from dotfiles.providers import Result
from dotfiles.providers import bin_dir
from dotfiles.providers import bundle
from dotfiles.providers import bundle_file
from dotfiles.providers import launchd
from dotfiles.providers import local_dir
from dotfiles.providers import locate
from dotfiles.providers import systemd
from dotfiles.providers.releases import AGENTS
from dotfiles.providers.releases import ASSETS
from dotfiles.providers.releases import COMPANIONS
from dotfiles.providers.releases import Archive
from dotfiles.providers.releases import LaunchAgent
from dotfiles.providers.releases import ReleaseArtifact

BUNDLE_CHECKSUMS = 'checksums.txt'
BUNDLE_BINARIES = 'binaries'

__all__ = [
    'Result',
    'bin_dir',
    'bundle_file',
    'declared_unit',
    'install',
    'installed_at',
    'local_dir',
    'locate',
    'missing_companions',
    'resolve_tag',
    'supervise',
    'unit_dir',
    'unresolved',
    'unsupervised',
]


def install(
    entry: catalog.GithubRelease,
    target: Target,
    *,
    offline: bool = False,
    tag: str | None = None,
    before_place: Callable[[], Result] | None = None,
) -> Result:
    """Put one declared release on this machine.

    `tag` is for a caller that already resolved one to decide *whether* to
    install — passing it back is what keeps that decision from costing a second
    API call, and from being made about a different release than the one that
    then gets installed.

    `before_place` is what a caller that has to destroy something first hands in.
    It runs once the asset is downloaded and verified and before a byte is
    written to `~/.local/bin`, which is the only ordering that does not risk
    leaving the machine with neither copy: every step above it reaches the
    network or a checksum and can fail, and the caller's step is the one that
    cannot be undone. A failure from it stops the install and is reported as-is.

    Every failure returns rather than raises, and names the step it failed at.
    An install stage runs the whole list before reporting, because a broken
    release must not stop the twenty that follow it.
    """
    build = ASSETS.get(entry.name)
    if build is None:
        return Result(False, f'nothing in providers.releases names an asset for {entry.name}', kind=Kind.DECLARATION_INVALID)

    try:
        tag = tag or resolve_tag(entry, offline=offline)
    except github_release.Unreadable as unreachable:
        return Result(False, str(unreachable), kind=Kind.VERSION_UNRESOLVED)
    if tag is None:
        return Result(False, unresolved(entry, offline=offline), kind=Kind.VERSION_UNRESOLVED)

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
            return Result(False, f'could not download {asset.name}', kind=Kind.DOWNLOAD_FAILED)

        refused = _verify(download, asset.name, entry, tag, from_bundle=staged is Staged.BUNDLE, offline=offline)
        if refused:
            return Result(False, refused, kind=Kind.UNVERIFIED)

        if before_place is not None:
            cleared = before_place()
            if not cleared.ok:
                return cleared

        placed = _place(asset, entry.executable, download, staging)
        if not placed.ok:
            return placed

    missing = _companions(entry.name, tag, locate(f'{BUNDLE_BINARIES}/{asset.name}'), offline=offline)
    if missing:
        return Result(False, missing, kind=Kind.NOT_IN_BUNDLE if offline else Kind.DOWNLOAD_FAILED)

    if not shutil.which(entry.executable):
        return Result(False, f'{entry.executable} installed but is not on PATH — is {bin_dir()} in it?', kind=Kind.NOT_ON_PATH)

    supervised = supervise(entry, target)
    if not supervised.ok:
        return supervised
    return Result(True, f'{entry.name} {tag}', kind=Kind.APPLIED)


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
    """What version of a tool an offline bundle staged, from its manifest."""
    row = bundle.staged(name, *bundle.CATEGORIES)
    return row.version if row and row.version else None


def published_version(name: str) -> str | None:
    """What the staged stack says upstream published, newest bundle answering first.

    Both halves of one bundle before either half of the next, which is what keeps
    the answer ordered by bundle age rather than by which shape it arrived in.
    Separate from `bundle_version` because that one must name a tag whose asset is
    on disk — `resolve_tag` builds an asset name out of it — and a version a sparse
    bundle only measured has no file by definition.
    """
    return bundle.published(name, *bundle.CATEGORIES)


def unresolved(entry: catalog.GithubRelease, *, offline: bool) -> str:
    """Why no tag could be decided, in the caller's words rather than a bare None.

    Public because `create_bundle` resolves a tag itself — to decide what to
    stage for an offline machine — and must report the same reason this would.
    """
    if offline:
        return f'no bundle staged at {paths.staging_dir()} carries a version of {entry.name}'
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
    cached = locate(f'{BUNDLE_BINARIES}/{asset_name}')
    if cached is not None and cached.path.is_file():
        shutil.copy2(cached.path, download)
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

    **The checksums come from the bundle that staged the asset, not the newest one
    holding a `checksums.txt`.** Several bundles can be staged at once, and a
    digest is published for one build of one release — pairing a newer bundle's
    file with an older bundle's binary fails verification on a machine where
    nothing is wrong.
    """
    staged_asset = locate(f'{BUNDLE_BINARIES}/{asset_name}')
    checksums = staged_asset.beside(BUNDLE_CHECKSUMS) if staged_asset else bundle_file(BUNDLE_CHECKSUMS)
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
    if outcome is github_release.Verification.UNREADABLE:
        # No `excused_by`, so no declaration reaches it. `unpublished` is the
        # author saying upstream publishes nothing, which is a claim about the
        # release; this is not knowing what the release holds, and the bytes are
        # unverified either way.
        return _permitted(entry, f'the release {tag} of {entry.repo} could not be read, so its checksums are unknown')
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


def installed_at(executable: str) -> Path:
    """Where this provider puts a release binary, which is the whole of its provenance.

    One path for every shape below: a raw download, a decompressed one, a member of
    an archive, and the symlink a tree install leaves pointing into `~/.local`. So
    "did this install it" is one question with one answer, and the caller asking it
    is `evidence.by_release`.

    A function rather than a constant, for the reason `bin_dir` is one: read at
    import it would freeze the developer's home into every test in the process.
    """
    return bin_dir() / executable


def _place(asset: ReleaseArtifact, executable: str, download: Path, staging: Path) -> Result:
    """Get binaries out of what was downloaded and into `~/.local/bin`."""
    target = installed_at(executable)
    target.parent.mkdir(parents=True, exist_ok=True)

    if asset.archive is Archive.RAW:
        if not effects.install(download, target):
            return Result(False, _unplaceable(executable, target), kind=Kind.WRITE_FAILED)
        return Result(True, str(target), kind=Kind.APPLIED)

    if asset.archive is Archive.GZIP:
        # Decompressed beside the download rather than onto `target`, because
        # opening the destination for writing is the thing that fails when the
        # destination is running. `install` is what lands it.
        plain = staging / executable
        if not effects.gunzip(download, plain):
            return Result(False, f'{asset.name} did not decompress', kind=Kind.ARCHIVE_UNREADABLE)
        if not effects.install(plain, target):
            return Result(False, _unplaceable(executable, target), kind=Kind.WRITE_FAILED)
        return Result(True, str(target), kind=Kind.APPLIED)

    if asset.tree:
        return _place_tree(asset, download, target)

    unpacked = staging / 'unpacked'
    if not effects.unpack(download, unpacked):
        return Result(False, f'{asset.name} is neither a tar nor a zip this could open', kind=Kind.ARCHIVE_UNREADABLE)

    source = unpacked / asset.path
    if not source.is_file():
        return Result(False, f'{asset.name} contains no {asset.path}', kind=Kind.ARCHIVE_INCOMPLETE)
    if not effects.install(source, target):
        return Result(False, _unplaceable(executable, target), kind=Kind.WRITE_FAILED)

    for extra in asset.extras:
        beside = unpacked / extra
        if not beside.is_file():
            continue
        placed = bin_dir() / Path(extra).name
        if not effects.install(beside, placed):
            return Result(False, _unplaceable(Path(extra).name, placed), kind=Kind.WRITE_FAILED)

    if asset.unit:
        source = unpacked / asset.unit
        if not source.is_file():
            return Result(False, f'{asset.name} contains no {asset.unit}', kind=Kind.ARCHIVE_INCOMPLETE)
        source.write_text(_exec_at(source.read_text(), target))
        placed = unit_dir() / Path(asset.unit).name
        if not effects.install(source, placed, executable=False):
            return Result(False, _unplaceable(Path(asset.unit).name, placed), kind=Kind.WRITE_FAILED)

    return Result(True, str(target), kind=Kind.APPLIED)


def _exec_at(unit: str, binary: Path) -> str:
    """Upstream's unit, pointed at where this actually installed the binary.

    A published unit names the path its distro package uses — syncthing ships
    `ExecStart=/usr/bin/syncthing` — and a release install puts the binary under
    ~/.local/bin, so the unit as written fails with 203, exec-not-found. Measured
    on scheduler-lxc 2026-08-16.

    Only the path moves. The arguments stay upstream's, so a release that changes
    them is followed rather than overridden, and an Exec line calling some other
    binary is left alone because that call is upstream saying what it needs.
    """
    lines = []
    for line in unit.splitlines(keepends=True):
        key, sep, rest = line.partition('=')
        first, space, arguments = rest.strip().partition(' ')
        if sep and key.strip().startswith('Exec') and Path(first).name == binary.name:
            lines.append(f'{key}={binary}{space}{arguments}\n')
            continue
        lines.append(line)
    return ''.join(lines)


def unit_dir() -> Path:
    """Where systemd reads a user unit, which is not where binaries go."""
    return paths.xdg_home('XDG_CONFIG_HOME', '.config') / 'systemd' / 'user'


def agent_plist(agent: LaunchAgent, binary: Path) -> bytes:
    """The job this repo declares for a release's daemon.

    `KeepAlive` and `RunAtLoad` are here rather than per agent because they are what
    declaring an agent at all means: the thing being supervised is a daemon, so it
    starts when the job loads and comes back when it exits. That is the pair
    `Restart=on-failure` and `WantedBy=default.target` answer on the other platform.

    The two log paths are not optional. launchd sends a job's output nowhere by
    default, so a daemon that will not start leaves no evidence anywhere — which is
    why `providers/schedule.py` names both files even to point them at /dev/null.
    Here they are real, because a sync daemon's log is the thing anyone debugging it
    wants.
    """
    logs = Path.home() / 'Library' / 'Logs'
    return launchd.serialize(
        {
            'Label': agent.label,
            'ProgramArguments': [str(binary), *agent.arguments],
            'KeepAlive': True,
            'RunAtLoad': True,
            'ProcessType': 'Background',
            'LowPriorityIO': True,
            'StandardOutPath': str(logs / f'{binary.name}.log'),
            'StandardErrorPath': str(logs / f'{binary.name}-errors.log'),
        }
    )


def supervise(entry: catalog.GithubRelease, target: Target) -> Result:
    """Hand a declared daemon to whichever supervisor this machine has.

    Public because a machine whose binary is current and whose supervisor is not
    owes only this — `registry.ReleaseProvider` calls it directly rather than
    spending a download on a state no download changes.

    **The two platforms differ in what placing the file buys, and that difference is
    the init systems' rather than this design's.** A plist under
    `~/Library/LaunchAgents` is loaded at the next login whether or not anything
    asked, so the file *is* the declaration and bootstrapping it only saves the
    wait — which is why a `launchctl` that will not answer warns instead of failing.
    A systemd user unit is inert until something enables it, so writing one and
    stopping is a daemon that never runs, and the enable is part of the install.
    """
    if target.is_darwin:
        return _supervise_launchd(entry) if entry.name in AGENTS else Result(True, '', kind=Kind.UNCHANGED)
    if systemd.available() and declared_unit(entry.name):
        return _supervise_systemd(entry)
    return Result(True, '', kind=Kind.UNCHANGED)


def unsupervised(name: str, executable: str) -> str:
    """Why a declared daemon is not supervised on this machine, or '' where it is.

    The observation half of `supervise`, and answered without resolving a release
    for `missing_companions`' reason: a checker offline, or one that has spent its
    API budget, still gets an answer.

    Three states rather than two on each platform, because a *stale* supervision
    file is the one nobody can see. launchd goes on running the definition it
    loaded and systemd the unit it read at boot, so a daemon whose arguments moved
    in this repo is running the old ones with nothing on the machine saying so.

    Which supervisor is asked is decided by whether it is on the machine, where
    `supervise` above is handed the declared target. This is the right test for a
    reading and the wrong one for a write: the question here is whether launchd or
    systemd can be *asked*, and a machine where neither can be owes no supervision
    — while an install already knows what kind of machine it is installing for.
    `sysconfig._observe_unit` opens with the same guard for the same reason.
    """
    if launchd.available() and name in AGENTS:
        return _unsupervised_launchd(name, executable)
    if systemd.available() and declared_unit(name):
        return _unsupervised_systemd(name, executable)
    return ''


def declared_unit(name: str) -> str:
    """The unit filename a declared release publishes, or '' where it declares none.

    Read off `ASSETS` without resolving a release, which is why the tag and the
    target are placeholders: `ReleaseArtifact.unit` is a constant of the builder
    rather than a fact about a particular release, and asking upstream for one
    would cost `check` an API call per entry.
    """
    build = ASSETS.get(name)
    if build is None:
        return ''
    asset = build('0', Target(OSFamily.LINUX, Arch.X86_64))
    return Path(asset.unit).name if asset.unit else ''


def _supervise_launchd(entry: catalog.GithubRelease) -> Result:
    """Write the plist and load it, failing only on the write.

    The agent is on disk and the next login loads it, so failing on a refused
    `launchctl` would report a machine broken over the step whose whole value is
    not having to log out — and would leave the binary installed and the run
    non-zero. A plist that cannot be *written* is a failure, for the reason a
    declared unit the archive lacks is one: silently skipping it installs a daemon
    that never runs.
    """
    agent = AGENTS[entry.name]
    plist = launchd.agent_path(agent.label)
    try:
        plist.parent.mkdir(parents=True, exist_ok=True)
        plist.write_bytes(agent_plist(agent, installed_at(entry.executable)))
    except OSError as unwritable:
        return Result(False, f'could not write {plist}: {unwritable.strerror}', kind=Kind.WRITE_FAILED)

    if not (launchd.available() and launchd.reload(agent.label).ok):
        warn(f'{plist} is written and launchctl would not load {agent.label}, so {entry.executable} starts at the next login')
    return Result(True, str(plist), kind=Kind.APPLIED)


def _supervise_systemd(entry: catalog.GithubRelease) -> Result:
    """Reload the manager and enable the unit `_place` wrote.

    A failure here fails the install, which is the opposite call to launchd's above
    and is decided by the same question: what does the file buy on its own. Nothing,
    here — an unenabled user unit is a daemon that does not start at the next login
    or any login after it.
    """
    unit = declared_unit(entry.name)
    placed = unit_dir() / unit
    if not placed.is_file():
        return Result(False, f'{placed} was not placed, so nothing keeps {entry.executable} running', kind=Kind.ARCHIVE_INCOMPLETE)
    enabled = systemd.enable(unit)
    if not enabled.ok:
        return Result(False, f'could not enable {unit}: {enabled.transcript.strip()}', kind=Kind.COMMAND_FAILED)
    return Result(True, str(placed), kind=Kind.APPLIED)


def _unsupervised_launchd(name: str, executable: str) -> str:
    agent = AGENTS[name]
    plist = launchd.agent_path(agent.label)
    if not plist.is_file():
        return f'{plist} does not exist, so nothing keeps {executable} running'
    if plist.read_bytes() != agent_plist(agent, installed_at(executable)):
        return f'{plist} differs from what this repo declares'
    if not launchd.loaded(agent.label):
        return f'{agent.label} is installed and launchd has not loaded it'
    return ''


def _unsupervised_systemd(name: str, executable: str) -> str:
    """The three states, with the middle one narrowed to what is knowable offline.

    The unit's body comes out of the release archive rather than from this repo, so
    there is nothing here to compare it against without a download. What `_place`
    *does* author is the `ExecStart` path, and that is the half that goes wrong —
    a unit still naming `/usr/bin` after the package it came from was removed is
    exec-not-found on every start.
    """
    placed = unit_dir() / declared_unit(name)
    if not placed.is_file():
        return f'{placed} does not exist, so nothing keeps {executable} running'
    if _exec_at(placed.read_text(), installed_at(executable)) != placed.read_text():
        return f'{placed} does not start {installed_at(executable)}'
    if not systemd.enabled(placed.name):
        return f'{placed.name} is installed and systemd has not enabled it'
    return ''


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
        return Result(False, f'{asset.name} did not unpack into {local_dir()}', kind=Kind.ARCHIVE_UNREADABLE)

    binary = local_dir() / asset.path
    if not binary.is_file():
        return Result(False, f'{asset.name} unpacked without a {asset.path}', kind=Kind.ARCHIVE_INCOMPLETE)

    effects.make_executable(binary)
    target.unlink(missing_ok=True)
    target.symlink_to(binary)
    return Result(True, f'{target} -> {binary}', kind=Kind.APPLIED)


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


def _companions(name: str, tag: str, staged_asset: Located | None, *, offline: bool) -> str:
    """Fetch the files that ship with a tool without being in its release.

    '' when there is nothing to do or it was done. A companion is not optional,
    which is why a failure here fails the install rather than warning.

    Every companion, never only the absent ones: the caller is placing the binary,
    and a companion is fetched at that binary's tag so the two are a matched pair.
    Whether one is *missing* is `missing_companions`, and it belongs to the
    observation rather than to this.

    `staged_asset` is the bundle the binary came out of, and the companion is
    taken from beside it — the same pinning `_verify` does for a checksum, for the
    same reason. A companion filename carries no version, so an unpinned lookup
    returns whichever staged bundle is newest: a binary from an older full bundle
    would take `fzf-tmux` from a newer sparse one, which is the mismatched pair
    the paragraph above says must not happen. None where the binary came off the
    network, and the companion follows it there.
    """
    for companion in COMPANIONS.get(name, ()):
        destination = bin_dir() / companion.name
        destination.parent.mkdir(parents=True, exist_ok=True)

        url = companion.url(tag)
        cached = staged_asset.beside(f'{BUNDLE_BINARIES}/{companion.name}') if staged_asset else None
        if cached is not None and cached.is_file():
            shutil.copy2(cached, destination)
        elif offline:
            return f'{companion.name} is not in the offline bundle and cannot be downloaded'
        else:
            arrived = effects.fetch(url, destination)
            if not arrived:
                return f'could not download {companion.name} from {url}: {arrived.reason}'

        effects.make_executable(destination)
    return ''
