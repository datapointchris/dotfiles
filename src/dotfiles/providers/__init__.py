"""How each kind of thing gets installed, one module per provider.

What lives here is only what every provider needs and none of them owns: the
shape of an install's outcome, and the three directories they all write into.
Every provider imports `Result` from here rather than defining its own — a
second vocabulary for the same answer — and calls `bin_dir`/`local_dir` rather
than spelling `~/.local/bin` again, which is a second chance for one spelling
to stop matching what the symlink manager deploys.
"""

from __future__ import annotations

import dataclasses as dc
import enum
import shutil
from pathlib import Path

from dotfiles import paths


class Kind(enum.StrEnum):
    """What condition a `Result` reports, as a value rather than a sentence.

    `detail` is prose written for the person reading the report, and it stays
    prose — it interpolates the entry, the URL and the path, which is the half a
    member can never carry. What a member carries is the half prose is bad at:
    telling two sibling branches of one installer apart without matching English.
    A test asserting a substring to prove which branch ran is a test pinned to
    wording that exists to be rewritten, which `standards/testing.md` § "Never
    assert on rendered output" names by this exact shape.

    The set is deliberately coarse. A member earns its place by being a condition
    something could plausibly act on differently — a different fix hint, a
    different column, a different exit — never by being a different sentence.
    Where two conditions share a remedy they share a member, and the prose still
    tells them apart for the reader.

    `ok` and `refused` are not folded in here and still decide the verdict.
    `NOT_IN_BUNDLE` is the clearest case: with `refused=True` it is a source the
    bundle deliberately does not stage, and with `refused=False` it is a bundle
    that is broken.
    """

    APPLIED = 'applied'
    """The change was made: something was installed, written, enabled or linked."""

    PARTIALLY_APPLIED = 'partially-applied'
    """The change was made, and a step it depends on could not be.

    Still a success — the machine has what it declared — so `ok` stays True and
    `Outcome.from_result` reads it as DONE. What separates it from `APPLIED` is the
    fix hint: a whole repair needs nothing further, and this one is waiting on
    something a person does, usually a login or a reboot.

    `sysconfig._unit_applied` is the case it was added for: a user unit enabled
    while its manager would not answer, so the symlink is on disk and nothing has
    loaded it. Without a member, which of the two branches ran was legible only by
    matching the `detail` sentence — the fault this enum's own docstring names.
    """

    UNCHANGED = 'unchanged'
    """Nothing was written, and nothing needed to be.

    Covers a tool already present, a manager with no bootstrap or refresh step, an
    offline run with nothing to compare against, and a vendor installer that
    declined because another process already holds it. Separated from `APPLIED`
    because "converged" and "converged by this run" are different answers to
    anything counting changes.
    """

    DECLARATION_INVALID = 'declaration-invalid'
    """The repo asked for something that cannot be dispatched or does not exist.

    A `packages.yml` row with no function behind it, a planned item carrying the
    wrong entry type, a monorepo subdirectory upstream has renamed. The fix is in
    this repo, never on the machine — which is what separates it from every other
    member here.
    """

    PREREQUISITE_MISSING = 'prerequisite-missing'
    """Something an earlier stage owes this one is not on the machine yet.

    fnm, brew, base-devel, nvim, tmux, a group, the login shell's binary. Becomes
    true on a later run once the stage that supplies it succeeds, which is exactly
    what separates it from `UNSUPPORTED_HERE`.
    """

    UNSUPPORTED_HERE = 'unsupported-here'
    """This machine structurally cannot do it, and no run will change that.

    No D-Bus system bus for flatpak, no Windows fonts directory outside WSL, no
    macOS build published at all. Reported with `ok=True` where the declaration is
    waived rather than failed.
    """

    PRIVILEGE_UNAVAILABLE = 'privilege-unavailable'
    """Root was needed and sudo is absent or was declined; nothing was attempted."""

    NOT_IN_BUNDLE = 'not-in-bundle'
    """An offline run, and the bundle carries nothing for this row.

    `refused` says whether that is legitimate: the bundle deliberately stages no
    Go tarball, and a missing `jq.exe` is a bundle that failed to build.
    """

    VERSION_UNRESOLVED = 'version-unresolved'
    """No tag to install: the release API answered nothing, or a pin matches no
    release. The transport worked, so a network fix is the wrong one."""

    DOWNLOAD_FAILED = 'download-failed'
    """A transfer did not complete, whatever ran it.

    A fetch, a `git clone`, a `git pull` — the failing step moved bytes over the
    network, so a CA, a firewall or an offline bundle are the plausible fixes.
    That is the test, never whether a subprocess was involved.
    """

    UNVERIFIED = 'unverified'
    """The bytes arrived and could not be trusted: digest mismatch, unreadable
    checksum, unpinned signing key, unverified signature. Never a placement or
    archive problem — the asset was refused before either was reached."""

    ARCHIVE_UNREADABLE = 'archive-unreadable'
    """The asset would not open or extract at all — not a tar, not a zip, would
    not decompress. Usually a truncated transfer, or an error page carrying an
    archive's name."""

    ARCHIVE_INCOMPLETE = 'archive-incomplete'
    """The archive opened and does not contain what the declaration named.

    Read the declaration, not the transfer: upstream repacked, or the path in
    `releases.py` is wrong. `ARCHIVE_UNREADABLE` is the same asset failing one
    step earlier, and the two want opposite investigations.
    """

    WRITE_FAILED = 'write-failed'
    """A write to the filesystem was attempted and the machine said no.

    Placing a binary in `~/.local/bin`, installing a managed file under `/etc`,
    creating a GnuPG home, replacing the GOROOT tree. `diagnose.explain` reads
    `Text file busy`, `Permission denied` and `No space left` out of these details.
    """

    COMMAND_FAILED = 'command-failed'
    """A command ran to completion and exited non-zero.

    The residual, and deliberately broad: a package manager, a vendor install
    script, `systemctl`, `chsh`, TPM, lazy. They share one remedy — read the
    transcript the detail carries — so they share one member.
    """

    VERIFY_FAILED = 'verify-failed'
    """The command exited clean and the thing it promised is not there.

    Distinct from `COMMAND_FAILED` by which half to go and look at, the same split
    `OutcomeStatus.ABSENT` draws: `COMMAND_FAILED` means read the command,
    `VERIFY_FAILED` means the command lied about itself.
    """

    NOT_ON_PATH = 'not-on-path'
    """The binary is where it belongs and the shell will not find it.

    Split from `VERIFY_FAILED` because the file exists: the fix is this machine's
    PATH, not a re-run of the installer.
    """

    TARGET_UNUSABLE = 'target-unusable'
    """Something is already at the destination and was not put there by this tool.

    A hand-made directory where a clone belongs, a `config.json` that is not JSON.
    Refusing to clobber it is the behaviour; a person has to decide what happens
    next.
    """


@dc.dataclass(frozen=True, slots=True)
class Result:
    """What one install did, in the form a caller can turn into an Outcome."""

    ok: bool
    detail: str

    kind: Kind = dc.field(kw_only=True)
    """Which condition this is, for a caller that must not read `detail` to find out.

    Keyword-only and with no default. A default is the two-tier API this field
    exists to end — half the sites carrying a real member and half carrying
    whatever the default is, with nothing afterwards able to tell them apart,
    which is exactly `detail`'s existing failure. Without one, a missed site
    raises `TypeError` where it is constructed rather than importing wrong.

    Keyword-only so it can sit before `refused` without reordering any existing
    call: every construction passes `ok` and `detail` positionally and `refused`
    by name.
    """

    refused: bool = False
    """Nothing was written, and nothing was wrong with the write: what this row
    needs is not on the machine to work with.

    Distinct from a failure because `apply` exits non-zero on failures, and a row
    waiting on a package an earlier stage could not deliver is not a fault of the
    run. `pluginsync.blocked` draws the same distinction for TPM.

    Two shapes qualify, and the second is the one this was widened for. A
    precondition an earlier stage of the same run was supposed to supply and did
    not — brew, a system package. And a source this machine structurally cannot
    reach: an offline run wanting go.dev or rustup.rs, which the bundle
    deliberately does not stage because the tools those runtimes would build
    arrive prebuilt instead. The second never becomes true by re-running, which is
    exactly why reporting it as a failure makes an offline machine permanently
    unconverged for working as designed.

    What is *not* refused: a bundle missing something the bundler does stage. That
    is a broken bundle and the run should say so.
    """


LOCAL_DIR = Path('.local')
"""`~/.local`, spelled relative to home.

The relative half is separate from `local_dir()` because two callers need
different halves of one fact. A provider wants the resolved directory and gets
it from the function. `toolchain.TOOL_PATH_DIRS` wants the `$HOME/...` string a
shell reads, and resolving home to build it would bake this machine's home into
a list `.zshenv` has to match on every machine.
"""

BIN_DIR = LOCAL_DIR / 'bin'


def local_dir() -> Path:
    """`~/.local`, the prefix everything user-installed unpacks under.

    A function rather than a constant so a test can move `HOME`. Read at import
    time it would freeze the real home into every test in the process.
    """
    return Path.home() / LOCAL_DIR


def bin_dir() -> Path:
    return Path.home() / BIN_DIR


MANIFEST = 'manifest.txt'
"""What makes a staged directory a bundle.

Here rather than in `providers.bundle`, which reads the file: this module decides
what counts as a bundle at all, and `staged_bundles` skips a directory without
one. `bundle.py` imports the name from here, so there is one definition.
"""


def staged_bundles() -> tuple[Path, ...]:
    """Every unpacked bundle, newest first.

    Newest first is the whole ordering contract: a sparse bundle staged over a
    full one has to win for the entries it carries and fall through for the rest.
    Sorted on the directory name, which carries the UTC stamp `bundle_name`
    writes for exactly this.

    A directory without a manifest is not a bundle and is skipped rather than
    refused — a half-finished unpack should not make every staged bundle beside it
    unreadable.
    """
    if not paths.staging_dir().is_dir():
        return ()
    found = (path for path in paths.staging_dir().iterdir() if (path / MANIFEST).is_file())
    return tuple(sorted(found, key=lambda path: path.name, reverse=True))


@dc.dataclass(frozen=True, slots=True)
class Located:
    """One staged file, and which bundle it came out of."""

    path: Path
    root: Path

    @property
    def bundle(self) -> str:
        return self.root.name

    def beside(self, name: str) -> Path:
        """A sibling file from the *same* bundle, never the newest one holding it.

        `checksums.txt` is why this exists. A checksum has to be the one published
        for the asset actually staged, and resolving the two independently across
        the stack pairs a newer bundle's checksum with an older bundle's binary —
        which fails verification on a machine where nothing is wrong.
        """
        return self.root / name


def locate(relative: str) -> Located | None:
    """The newest staged bundle carrying this file, or None where none does."""
    for root in staged_bundles():
        found = root / relative
        if found.exists():
            return Located(found, root)
    return None


def bundle_file(relative: str) -> Path:
    """Where a staged file is, or where it would be if anything carried it.

    A path either way, because every caller asks `.is_file()` and a `None` would
    make each of them answer that question a second way. The path for a file
    nothing carries is under the staging directory itself, which exists on no
    machine and so reads as absent — and reads as a sensible location in the
    message a provider builds from it.
    """
    found = locate(relative)
    return found.path if found else paths.staging_dir() / relative


def place(source: Path, destination: Path) -> None:
    """Put a binary where it belongs: written beside the target, then renamed over it.

    A plain copy over a binary that is currently running fails with `text file
    busy`, and the binary currently running is routinely `task`, which is what
    invoked the install. Shared rather than written per provider because the
    failure is a property of the destination, not of where the bytes came from.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    staged = destination.with_name(f'{destination.name}.new')
    shutil.copy2(source, staged)
    staged.chmod(0o755)
    staged.replace(destination)
