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

**A failed binstall reaches the bundle too, and the same question governs it.**
"Online" means a network rather than a reachable crates.io, so a firewalled
machine arrives here for every crate it declares, and a bundle carrying what is
already installed repairs none of them. `bundle.behind_refusal` is where that is
decided and why.

The bundle's layout is read from its manifest rather than guessed at.
`cargo-tools.sh` globbed for four increasingly loose patterns against two
candidate names, which is the shape a program takes when it cannot ask the
program that wrote the file — see `providers/bundle.py`.
"""

from __future__ import annotations

import shutil
import tempfile
import tomllib
from pathlib import Path

from dotfiles import catalog
from dotfiles import effects
from dotfiles import paths
from dotfiles.coordinates import OSFamily
from dotfiles.coordinates import Target
from dotfiles.providers import Kind
from dotfiles.providers import Result
from dotfiles.providers import bundle
from dotfiles.providers import place
from dotfiles.providers import releases
from dotfiles.providers import staged_bundles
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

    The relative half is `toolchain.CARGO_BIN`, which rustup's installer and
    `TOOL_PATH_DIRS` both already name — three spellings of one directory was two
    too many.
    """
    return Path.home() / toolchain.CARGO_BIN


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


def install(entry: catalog.CargoPackage, target: Target, *, offline: bool, floor: str) -> Result:
    """Converge one Rust CLI, from whichever source this run can reach.

    `floor` is what a staged bundle is ranked against before an online run installs
    from it, and it is required rather than defaulted. A default is the loop
    `bundle.behind_refusal` describes, restored by omission at a call site nothing
    would fail on — `registry.version_floor` is the one thing that knows the answer.
    """
    if offline:
        carried = _carried(entry)
        installed = _from_bundle(entry, *carried) if carried else None
        return installed or Result(
            False,
            f'{entry.name} is not in a bundle staged at {paths.staging_dir()}, and offline cannot reach crates.io',
            kind=Kind.NOT_IN_BUNDLE,
        )

    ready = binstall(target, offline=offline)
    if not ready.ok:
        return _from_bundle_unless_behind(entry, ready, floor)

    built = _from_binstall(entry)
    if built.ok:
        return built
    return _from_bundle_unless_behind(entry, built, floor)


def _carried(entry: catalog.CargoPackage) -> tuple[bundle.Staged, Path] | None:
    """The row and the archive it names, out of one bundle, or None where no bundle has both.

    Walked per root rather than asking `bundle.staged` for the row and
    `bundle_file` for the archive. Those are two newest-first searches keyed on
    different things — the crate name and the filename — and four declared crates
    name their asset with no version in it: `fnm`, `eza`, `oxker` and `abtop`. For
    those, a newer bundle recording a row whose archive failed to extract lends its
    version to an older bundle's file, and `behind_refusal` then ranks a version
    the bytes do not carry. Measured: floor `0.23.5`, newer row `v0.24.0`, older
    archive at `v0.23.5` — the guard passed, the old bytes were written, and the
    run reported `applied` at a version the machine did not have.

    A root carrying the row and not the archive is skipped rather than refused,
    which is the same reading `_from_bundle` already gave a manifest naming a file
    the bundle lacks: half a bundle is no bundle, not a broken one.
    """
    for root in staged_bundles():
        row = bundle.row_in(root, entry.name, BUNDLE_CATEGORY)
        if row is None:
            continue
        archive = root / BUNDLE_BINARIES / row.filename
        if archive.is_file():
            return row, archive
    return None


def _from_bundle_unless_behind(entry: catalog.CargoPackage, failure: Result, floor: str) -> Result:
    """The bundle, on a run that had a network and could not install through it.

    Worth reaching at all because "online" means a network rather than a reachable
    crates.io. On a firewalled machine it never is, and without this every Rust
    tool stays at the version the machine was built with while a current bundle
    sits unused on disk.

    Worth declining where the staged version is what is already installed, for the
    reason `bundle.behind_refusal` records. One `_carried` answers both halves, so
    the version ranked and the bytes written come out of one bundle by
    construction rather than by two searches agreeing.
    """
    carried = _carried(entry)
    if carried is None:
        return failure
    row, archive = carried
    return bundle.behind_refusal(row, floor, failure) or _from_bundle(entry, row, archive) or failure


def _from_binstall(entry: catalog.CargoPackage) -> Result:
    """`cargo binstall`, keeping what it said.

    Invoked as a cargo subcommand rather than as the `cargo-binstall` binary
    directly, which it also supports: cargo is a hard dependency of this provider
    either way — the Rust toolchain converges at an earlier stage — and the
    subcommand spelling is what every crates.io instruction uses.

    **`--force` where a bundle already wrote this binary, and only there.**
    binstall's last strategy is `compile`, which is `cargo install` building the
    crate, and `cargo install` refuses to overwrite a binary it does not own:

        error: binary `oxker` already exists in destination
        Add --force to overwrite

    `_from_bundle` is what produces an unowned one. It goes through `place`,
    which copies the file into `~/.cargo/bin` and writes no row in
    `.crates.toml`, so cargo has no record of it. The machine that most needs the
    compile strategy is therefore the one where it cannot run — a firewalled box
    reaches crates.io and no release host, so every crate falls to `compile`, and
    every crate it restored from a bundle refuses. `--force` clears that, and
    clears it once: the successful build records the crate, `cargo_owns` answers
    True from then on, and the flag stops being passed.

    Narrow on purpose. Passing it unconditionally would defeat binstall's
    already-installed short-circuit and re-download every crate on every apply.

    **Streamed, because the compile strategy is reachable.** A crate with no
    prebuilt binary for this target builds from source, for as long as that crate
    takes — `docs/learnings/cargo-binstall-needs-release-binaries.md` is the
    account of why that is acceptable rather than a defect. Held quiet it cannot
    be told from a deadlock, and streamed the `Compiling` lines say it is moving.
    """
    forced = ['--force'] if placed_without_a_cargo_receipt(entry) else []
    completed = effects.run(['cargo', 'binstall', '-y', *forced, entry.name])
    if completed.ok:
        return Result(True, f'{entry.executable} installed by cargo binstall from {entry.name}', kind=Kind.APPLIED)
    return Result(
        False, f'cargo binstall {entry.name} exited {completed.returncode}: {completed.transcript.strip()}', kind=Kind.COMMAND_FAILED
    )


CRATES_RECEIPT = '.crates.toml'
"""Cargo's record of what it installed, beside the `bin` directory it installed into.

Read rather than `cargo install --list`, which spawns a process per package to
answer a question one file already holds.
"""


def cargo_owns(executable: str) -> bool:
    """Whether cargo installed the binary of this name, by its own receipt.

    The receipt is a `[v1]` table keyed by a crate spec, whose value is the list of
    binaries that crate placed — so the answer is a membership test across every
    value, not a lookup by crate name. A crate installs binaries under names of its
    own choosing, which is the same split `entry.command` exists for.

    False where the receipt is absent or will not parse. Both mean nothing here can
    show cargo owns the file, and claiming ownership it cannot demonstrate is the
    reading that leaves `cargo install` refusing with no way out.
    """
    try:
        recorded = tomllib.loads((cargo_bin().parent / CRATES_RECEIPT).read_text())
    except (OSError, tomllib.TOMLDecodeError):
        return False
    return any(executable in binaries for binaries in recorded.get('v1', {}).values())


def placed_without_a_cargo_receipt(entry: catalog.CargoPackage) -> bool:
    """Whether a binary sits at the destination with no row in `.crates.toml`.

    Both halves are needed. Nothing at the destination is the ordinary first
    install, and a binary cargo owns is the ordinary upgrade; only a file cargo
    cannot account for makes `cargo install` refuse.
    """
    return (cargo_bin() / entry.executable).exists() and not cargo_owns(entry.executable)


def _from_bundle(entry: catalog.CargoPackage, row: bundle.Staged, archive: Path) -> Result | None:
    """Install one staged release archive, or None where it will not yield a binary.

    Handed the row and the archive rather than resolving them, so the version a
    caller ranked and the bytes written here cannot come from two bundles —
    `_carried` records what that costs when they do.

    None rather than a failed Result where the archive holds nothing usable, so a
    caller can tell "the bundle does not have this" from "the bundle has it and it
    would not install" — only the first is a reason to fall through.
    """
    with tempfile.TemporaryDirectory(prefix=f'dotfiles-{entry.name}-') as scratch:
        unpacked = Path(scratch) / 'unpacked'
        if not effects.unpack(archive, unpacked):
            return Result(False, f'{row.filename} is neither a tar nor a zip this could open', kind=Kind.ARCHIVE_UNREADABLE)

        binary = _inside(unpacked, entry.executable)
        if binary is None:
            return Result(False, f'{row.filename} carries no {entry.executable}', kind=Kind.ARCHIVE_INCOMPLETE)
        try:
            place(binary, cargo_bin() / entry.executable)
        except OSError as refused:
            return Result(False, f'could not install {entry.executable} from {archive}: {refused}', kind=Kind.WRITE_FAILED)

    return Result(True, f'{entry.executable} {row.version} installed from the bundle at {archive}', kind=Kind.APPLIED)


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
    also the only path that works on a restricted box, where release asset
    downloads are blocked but crates.io is reachable.
    """
    if shutil.which('cargo-binstall'):
        return Result(True, '', kind=Kind.UNCHANGED)
    if offline:
        return Result(
            False,
            f'cargo-binstall installs from {BINSTALL_REPO}, which no bundle staged at {paths.staging_dir()} carries it',
            kind=Kind.NOT_IN_BUNDLE,
        )

    placed = _binstall_from_release(target)
    if placed.ok:
        toolchain.put_on_path(cargo_bin())
        return placed

    if shutil.which('cargo') is None:
        return Result(
            False, f'cargo-binstall is unavailable: {placed.detail}, and there is no cargo to build it', kind=Kind.PREREQUISITE_MISSING
        )

    built = effects.run(['cargo', 'install', 'cargo-binstall'])
    if not built.ok:
        # `PREREQUISITE_MISSING` rather than `COMMAND_FAILED`, matching the branch
        # above it: both are one question — is there a cargo-binstall to install
        # with — and the residual kind would say the *tool's own* install command
        # failed. `bundle.behind_refusal` reads exactly that distinction, so a
        # machine that cannot build the precondition was reporting every declared
        # crate as a stale bundle.
        return Result(
            False,
            f'cargo-binstall is unavailable: {placed.detail}, and building it exited {built.returncode}',
            kind=Kind.PREREQUISITE_MISSING,
        )
    toolchain.put_on_path(cargo_bin())
    return Result(True, 'cargo-binstall built from source', kind=Kind.APPLIED)


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
            return Result(False, f'could not download {url}: {arrived.reason}', kind=Kind.DOWNLOAD_FAILED)

        unpacked = staging / 'unpacked'
        if not effects.unpack(download, unpacked):
            return Result(False, f'{archive_name} is neither a tar nor a zip this could open', kind=Kind.ARCHIVE_UNREADABLE)

        binary = _inside(unpacked, 'cargo-binstall')
        if binary is None:
            return Result(False, f'{archive_name} carries no cargo-binstall', kind=Kind.ARCHIVE_INCOMPLETE)
        try:
            place(binary, cargo_bin() / 'cargo-binstall')
        except OSError as refused:
            return Result(False, f'could not install cargo-binstall from {archive_name}: {refused}', kind=Kind.WRITE_FAILED)

    return Result(True, f'cargo-binstall from {url}', kind=Kind.APPLIED)
