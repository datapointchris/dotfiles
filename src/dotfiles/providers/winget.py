"""Installing a Windows CLI: winget, or the .exe an offline bundle carries.

winget resolves the package, downloads it and unpacks it — so this owns none of
that, the way `gotool` owns none of what the module proxy does. What it owns is
the step winget does not do for us: the package lands in a version-stamped
directory under the user's profile, and `~/.local/bin` is the one directory both
Git Bash and this repo's `apps/` tree put on PATH, so the binary is copied there.

**A zero exit code from winget is not the evidence.** It exits non-zero for
"already at latest version", which is not a failure, and it exits zero having
resolved a package whose exe sits somewhere the copy below cannot find. So the
install's status is ignored in both directions and what decides the outcome is
whether the binary arrived, measured directly.

**Which source is preferred is decided by whether winget delivered**, not by a
mode — the same arrangement `gotool` reaches for the module proxy. The employer
network this box sits on blocks winget outright, so "online" here means a network
and never a reachable Store; a run that only tried winget would leave every one of
these eight permanently uninstalled on the one machine that declares them. The
bundle is therefore tried after winget on an online run and is the whole of an
offline one.

`catalog.WingetPackage` carries `repo` and `asset` for exactly this, and
`create_bundle.add_winget_binaries` is what reads them. A missing staged file is a
failure rather than a refusal, per `providers.Result.refused`: the bundler stages
this category now, so a bundle without it is a broken bundle and the run says so.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from dotfiles import catalog
from dotfiles import effects
from dotfiles.effects import Output
from dotfiles.providers import Result
from dotfiles.providers import bundle_file
from dotfiles.providers import place

PACKAGES = 'AppData/Local/Microsoft/WinGet/Packages'
"""Where winget unpacks a package, relative to the Windows user's profile.

Copied out of rather than added to PATH: the shell gets one PATH entry,
`~/.local/bin`, and eight package directories with version-stamped names is what
that entry exists to avoid.
"""

BUNDLE_BINARIES = 'winget-binaries'
"""Where `create_bundle` stages these executables, agreed here rather than by
convention — the same agreement `gotool.BUNDLE_BINARIES` records, and for the
reason that module measured: the bundler and the installer once named the file
in two places off two shapes of one declaration, so a change moved one of them,
silently, on the only machine that reads a bundle.

Its own directory rather than `binaries/`, because the two hold different things.
`binaries/` holds release assets under whatever the publisher called them, and
whoever installs one unpacks it. This holds the finished `.exe` under the name it
has to land on PATH as, which is the shape `go-binaries/` is in for the same
reason.
"""

FIRST_DIGIT = re.compile(r'[0-9].*')


def version_num(tag: str) -> str:
    """The tag from its first digit on: `v0.9.8` and `jq-1.7.1` both give the number.

    Deliberately not `releases.expand_pattern`, which is where every other section
    fills a `binary_pattern` in. Two reasons, and the second holds whatever the
    tags happen to be. It spells this one `lstrip('v')`, which agrees on every tag
    the eight rows resolve to today and is not what `catalog.WingetPackage`
    declares — jq tags `jq-1.7.1`. And its vocabulary answers `{Os}`, `{os_mac}`,
    `{Os_mac}` and `{platform}` from `target.is_darwin` alone, so a Windows entry
    reaching any of the four is told it is Linux. That is the failure
    `coordinates.platform_label` answers winget explicitly to avoid, and importing
    it here would be reintroducing it one module over.
    """
    found = FIRST_DIGIT.search(tag)
    return found.group(0) if found else tag


def stage(entry: catalog.WingetPackage, version: str) -> str:
    """The release asset an offline bundle stages for this package, by name.

    Here rather than in the bundler for the reason `gotool.stage` records: naming
    the file is the same question this module answers when installing from one.

    Only the name. Which release it comes from, downloading it, verifying it
    against the checksum its publisher wrote and pulling the `.exe` out of a zip
    are all the bundler's, because it is the only side with a network.
    """
    return entry.asset.replace('{version}', version).replace('{version_num}', version_num(version))


def bundled(entry: catalog.WingetPackage) -> Path:
    return bundle_file(BUNDLE_BINARIES) / entry.filename


def client() -> str:
    """The winget binary, or '' where this machine has none.

    Both spellings, because `shutil.which` consults `PATHEXT` only where `os.name`
    is `nt` — which an MSYS2 interpreter is not. Under Git Bash's own Python the
    bare name finds nothing, and a machine with winget installed would report
    having none. `coordinates._package_manager` looks it up the same way and says
    the same thing.
    """
    return shutil.which('winget') or shutil.which('winget.exe') or ''


def copy_installed(home: Path, into: Path, entry: catalog.WingetPackage) -> bool:
    """Find one winget-installed exe under `home` and copy it, or say it is not there.

    The package directory carries a version and a source suffix in its name, so it
    is matched by prefix; some packages then nest the exe a level down, which is
    the recursive search below and not a fallback for a mistake.

    `home` is a parameter rather than `Path.home()` read here, so the whole of what
    decides an install is reachable from a test with no Windows anywhere. It is the
    step winget does not do, which makes it the step that decides whether a row
    installed at all.
    """
    packages = home / PACKAGES
    if not packages.is_dir():
        return False

    for candidate in sorted(packages.glob(f'{entry.winget}*')):
        direct = candidate / entry.filename
        if direct.is_file():
            place(direct, into / entry.filename)
            return True
        for nested in sorted(candidate.rglob(entry.filename)):
            if nested.is_file():
                place(nested, into / entry.filename)
                return True
    return False


def install(entry: catalog.WingetPackage, into: Path, *, offline: bool) -> Result:
    """Install one package from whichever source this run can reach.

    `into` is a parameter rather than `providers.bin_dir()` read here, because the
    Windows profile a WSL box writes to is not the one this process has a home in
    — the same reason `copy_installed` takes a home. The provider passes
    `bin_dir()`, which is the one spelling of `~/.local/bin` this package keeps.

    Offline goes straight to the bundle and never calls winget, which needs the
    Store the network blocks. Online tries winget first and falls back, because
    reaching a network is not the same as reaching the Store: on this box it never
    is, and without the fallback every row here stays uninstalled while a current
    bundle sits staged on disk.
    """
    if offline:
        return _from_bundle(entry, into) or Result(False, _unstaged(entry))

    winget = client()
    if not winget:
        return _from_bundle(entry, into) or Result(False, f'winget is not on PATH, and {_unstaged(entry)}')

    home = Path.home()
    effects.run((winget, 'install', '--accept-package-agreements', '--accept-source-agreements', entry.winget), output=Output.STREAM)

    if copy_installed(home, into, entry):
        return Result(True, f'winget: {entry.winget}')
    return _from_bundle(entry, into) or Result(False, f'winget left no {entry.filename} under {home / PACKAGES}, and {_unstaged(entry)}')


def _unstaged(entry: catalog.WingetPackage) -> str:
    return f'the offline bundle at {bundled(entry).parent} carries no {entry.filename}'


def _from_bundle(entry: catalog.WingetPackage, into: Path) -> Result | None:
    """The staged executable, or None where the bundle carries none.

    None rather than a failed Result, so a caller can tell "the bundle does not
    have this" from "the bundle has it and it would not install" — the same split
    `gotool._from_bundle` makes, and only the first is a reason to fall through or
    to compose a message about what else was tried.
    """
    cached = bundled(entry)
    if not cached.is_file():
        return None

    try:
        place(cached, into / entry.filename)
    except OSError as refused:
        return Result(False, f'could not install {entry.filename} from {cached}: {refused}')
    return Result(True, f'{entry.filename} installed from the bundle at {cached}')
