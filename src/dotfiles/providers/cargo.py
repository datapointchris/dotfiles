"""Installing a Rust CLI: `cargo binstall`, or the tarball an offline bundle staged.

`cargo binstall` is both the install and the upgrade, the same way `go install
@latest` is: it resolves the crate's current version and fetches the release
binary the project published for it, so there is no separate upgrade command and
nothing underneath deciding when a tool moves.

**Which source is preferred is decided by whether the run has a network.** The
bundle is a snapshot of whatever was current when it was built, so preferring it
on a machine that can reach crates.io would install a version this repo already
knows is behind — and, now that these entries carry currency, `apply` would
repair a `STALE` tool by reinstalling the same stale bytes and never converge.
Offline is the inverse: crates.io and the release hosts are both unreachable, so
the bundle is the only source there is.

The bundle's layout is read from its manifest rather than guessed at.
`cargo-tools.sh` globbed for four increasingly loose patterns against two
candidate names, which is the shape a program takes when it cannot ask the
program that wrote the file — see `providers/bundle.py`.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from dotfiles import catalog
from dotfiles import effects
from dotfiles import paths
from dotfiles.coordinates import OSFamily
from dotfiles.coordinates import Target
from dotfiles.effects import Output
from dotfiles.providers import Result
from dotfiles.providers import bundle
from dotfiles.providers import bundle_file
from dotfiles.providers import place
from dotfiles.providers import releases
from dotfiles.providers import toolchain

BUNDLE_BINARIES = 'binaries'
"""Beside the GitHub release assets, because that is what these are: the bundler
downloads a cargo tool's release binary rather than building the crate."""

BUNDLE_CATEGORY = 'cargo'

BINSTALL_REPO = 'cargo-bins/cargo-binstall'


def cargo_bin() -> Path:
    """Where `cargo binstall` puts a binary, and so where a bundled one goes too.

    A function rather than a constant so a test can move `HOME`, for the reason
    `providers.local_dir` records.
    """
    return Path.home() / '.cargo' / 'bin'


def triple(target: Target) -> str:
    """The Rust target triple, which is how a cargo tool's assets are named.

    `unknown-linux-gnu` rather than the `unknown-linux` prefix `cargo-tools.sh`
    matched on: that was a prefix because the glob had to cover both gnu and musl
    entries, and a declaration naming its own target — `ripgrep` and `zoxide` ship
    musl — says which one it is without anything having to guess.

    Windows is answered rather than left to the last expression, which is a
    fallthrough and not a Linux test. No `cargo_packages` entry ever resolves here
    for it — Windows CLIs are declared as `winget_packages` — but `create_bundle`
    also asks this for uv, and a Windows bundle was being handed
    `x86_64-unknown-linux-gnu` and staging a Linux ELF under a Windows label. That
    is the failure `coordinates.platform_label` names: a default that reads as an
    answer.
    """
    machine = 'aarch64' if target.is_arm else 'x86_64'
    if target.os_family is OSFamily.WINDOWS:
        return f'{machine}-pc-windows-msvc'
    return f'{machine}-apple-darwin' if target.is_darwin else f'{machine}-unknown-linux-gnu'


def asset_target(entry: catalog.CargoPackage, target: Target) -> str:
    """What `{target}` expands to in this entry's asset name.

    The triple, unless the declaration overrides it — fnm ships `fnm-linux.zip`
    and `fnm-macos.zip`, named after the OS word and not the platform it was
    built for.
    """
    if target.is_darwin and entry.darwin_target:
        return entry.darwin_target
    if not target.is_darwin and entry.linux_target:
        return entry.linux_target
    return triple(target)


def stage(entry: catalog.CargoPackage, version: str, target: Target) -> str:
    """The release asset an offline bundle stages for this package, by name.

    Here rather than in the bundler for the reason `gotool.stage` records: naming
    the file is the same question this module answers when installing from one,
    and two answers in two files off two shapes of the same data is how they came
    to disagree. `{arch}` is spelled `aarch64` because that is what a Rust
    project's release assets say.
    """
    return releases.expand_pattern(
        entry.binary_pattern,
        version,
        target,
        asset_target=asset_target(entry, target),
        arch='aarch64' if target.is_arm else 'x86_64',
    )


def install(entry: catalog.CargoPackage, target: Target, *, offline: bool) -> Result:
    """Converge one Rust CLI, from whichever source this run can reach."""
    if offline:
        return _from_bundle(entry) or Result(
            False, f'{entry.name} is not in the offline bundle at {bundle_file(BUNDLE_BINARIES)}, and offline cannot reach crates.io'
        )

    ready = binstall(target, offline=offline)
    if not ready.ok:
        return _from_bundle(entry) or ready

    built = _from_binstall(entry)
    if built.ok:
        return built

    # Worth trying even on an online run, because "online" means a network rather
    # than a reachable crates.io. On a firewalled machine it never is, and without
    # this every Rust tool stays at the version the machine was built with while a
    # current bundle sits unused on disk.
    return _from_bundle(entry) or built


def _from_binstall(entry: catalog.CargoPackage) -> Result:
    """`cargo binstall`, keeping what it said.

    Invoked as a cargo subcommand rather than as the `cargo-binstall` binary
    directly, which it also supports: cargo is a hard dependency of this provider
    either way — the Rust toolchain converges at an earlier stage — and the
    subcommand spelling is what `update.sh` and every crates.io instruction use.
    """
    completed = effects.run(['cargo', 'binstall', '-y', entry.name], output=Output.QUIET)
    if completed.ok:
        return Result(True, f'{entry.executable} installed by cargo binstall from {entry.name}')
    return Result(False, f'cargo binstall {entry.name} exited {completed.returncode}: {completed.transcript.strip()}')


def _from_bundle(entry: catalog.CargoPackage) -> Result | None:
    """The staged release archive, or None where the bundle carries none.

    None rather than a failed Result, so a caller can tell "the bundle does not
    have this" from "the bundle has it and it would not install" — only the first
    is a reason to fall through to something else.
    """
    row = bundle.staged(entry.name, BUNDLE_CATEGORY)
    if row is None:
        return None
    archive = bundle_file(BUNDLE_BINARIES) / row.filename
    if not archive.is_file():
        return None

    with tempfile.TemporaryDirectory(prefix=f'dotfiles-{entry.name}-') as scratch:
        unpacked = Path(scratch) / 'unpacked'
        if not effects.unpack(archive, unpacked):
            return Result(False, f'{row.filename} is neither a tar nor a zip this could open')

        binary = _inside(unpacked, entry.executable)
        if binary is None:
            return Result(False, f'{row.filename} carries no {entry.executable}')
        try:
            place(binary, cargo_bin() / entry.executable)
        except OSError as refused:
            return Result(False, f'could not install {entry.executable} from {archive}: {refused}')

    return Result(True, f'{entry.executable} {row.version} installed from the bundle at {archive}')


def _inside(unpacked: Path, executable: str) -> Path | None:
    """The binary somewhere in what was extracted.

    Searched rather than addressed by path: a release archive puts the binary at
    the root, or one directory down under a name carrying the version and the
    target, and which of those is upstream's choice per project. Sorted so the
    shallowest match wins and the answer does not depend on directory order.
    """
    found = sorted((path for path in unpacked.rglob(executable) if path.is_file()), key=lambda path: len(path.parts))
    return found[0] if found else None


# ─────────────────────────────────────────────────────────────────────────────
# The precondition
# ─────────────────────────────────────────────────────────────────────────────


def binstall(target: Target, *, offline: bool) -> Result:
    """cargo-binstall itself, which is the mechanism everything above installs through.

    A precondition of this provider rather than part of the Rust runtime: rustup
    brings `cargo`, and this is a subcommand only the tools declared here need.
    Checked per package rather than once for the batch, which costs a PATH scan
    each — the provider protocol has no before-the-batch hook, and inventing one
    for this would be a change to the core vocabulary for a `shutil.which`.

    Not a `github_releases` entry, and so not verified against a checksum:
    cargo-binstall publishes minisign signatures and nothing this repo can read.
    The source build is the fallback rather than a relaxed verification — it is
    also the only path that works on the work box, where release asset downloads
    are blocked but crates.io is reachable.
    """
    if shutil.which('cargo-binstall'):
        return Result(True, '')
    if offline:
        return Result(False, f'cargo-binstall installs from {BINSTALL_REPO}, which the offline bundle at {paths.BUNDLE_DIR} does not stage')

    placed = _binstall_from_release(target)
    if placed.ok:
        toolchain.put_on_path(cargo_bin())
        return placed

    if shutil.which('cargo') is None:
        return Result(False, f'cargo-binstall is unavailable: {placed.detail}, and there is no cargo to build it')

    built = effects.run(['cargo', 'install', 'cargo-binstall'])
    if not built.ok:
        return Result(False, f'cargo-binstall is unavailable: {placed.detail}, and building it exited {built.returncode}')
    toolchain.put_on_path(cargo_bin())
    return Result(True, 'cargo-binstall built from source')


def _binstall_from_release(target: Target) -> Result:
    """The published binary, from the `latest` redirect rather than a resolved tag.

    Nothing here compares versions of cargo-binstall — it is present or it is not
    — so resolving a tag would spend an API call to name a file the redirect
    already serves.
    """
    archive_name = f'cargo-binstall-{triple(target)}.{"zip" if target.is_darwin else "tgz"}'
    url = f'https://github.com/{BINSTALL_REPO}/releases/latest/download/{archive_name}'

    with tempfile.TemporaryDirectory(prefix='dotfiles-cargo-binstall-') as scratch:
        staging = Path(scratch)
        download = staging / archive_name
        arrived = effects.fetch(url, download)
        if not arrived:
            return Result(False, f'could not download {url}: {arrived.reason}')

        unpacked = staging / 'unpacked'
        if not effects.unpack(download, unpacked):
            return Result(False, f'{archive_name} is neither a tar nor a zip this could open')

        binary = _inside(unpacked, 'cargo-binstall')
        if binary is None:
            return Result(False, f'{archive_name} carries no cargo-binstall')
        try:
            place(binary, cargo_bin() / 'cargo-binstall')
        except OSError as refused:
            return Result(False, f'could not install cargo-binstall from {archive_name}: {refused}')

    return Result(True, f'cargo-binstall from {url}')
