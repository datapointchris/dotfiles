"""Installing a Go tool: the module proxy, or the binary an offline bundle carries.

`go install <package>@latest` is both the install and the upgrade. Nothing sits
underneath deciding when a Go tool moves — unlike npm or apt, where a registry
does — so "latest" is a question only the proxy answers, and the answer *is* the
install.

**Which source is preferred is decided by whether the run has a network**, not by
a mode. The bash had two, and the mode decided it: an install took the bundle, an
update took the proxy and fell back to the bundle. One verb cannot ask which mode
it is in — but it can ask whether it is offline, which is the fact both modes were
approximating. A machine behind the work firewall reaches neither differently for
having typed a different word.

The bundle's layout is agreed here rather than by convention. `create_bundle`
writes `go-binaries/<executable>` and this module opens it, so the two sides name
one path through one constant — where each spelling its own is a silent miss on
the one machine that needs it.
"""

from __future__ import annotations

import re
from pathlib import Path

from dotfiles import catalog
from dotfiles import effects
from dotfiles.coordinates import Target
from dotfiles.effects import Output
from dotfiles.providers import Kind
from dotfiles.providers import Result
from dotfiles.providers import bundle
from dotfiles.providers import bundle_file
from dotfiles.providers import place
from dotfiles.providers import releases
from dotfiles.providers import staged_bundles
from dotfiles.providers import toolchain

BUNDLE_BINARIES = 'go-binaries'

BUNDLE_CATEGORY = 'go-binary'
"""What `create_bundle.add_go_binaries` records these rows under.

The directory and the category are separate constants because they are separate
facts: `BUNDLE_BINARIES` is where the file sits and this is how the manifest
names it, and nothing makes one follow the other.
"""


def gobin() -> Path:
    """Where `go install` puts a binary, and so where one from a bundle goes too.

    A function rather than a constant so a test can move `HOME`, for the reason
    `providers.local_dir` records: read at import it would freeze the real home
    into every test in the process.

    The relative half is `toolchain.GO_BIN`, so this and `TOOL_PATH_DIRS` cannot
    disagree about where `go install` writes.
    """
    return Path.home() / toolchain.GO_BIN


MODULE_INFO_SECONDS = 10.0
"""`go version -m` reads one binary's embedded build info off disk — no proxy,
no network — so this bounds a stuck subprocess, not a slow download."""


def module_version(binary: Path) -> str | None:
    """The module version `go install` actually resolved, read back from the
    binary rather than asked of it.

    Exact where `--version` is not: a vendor's banner is whatever `-ldflags -X` a
    *release* build stamped, a flag `go install` never passes — which is why `gdu
    --version` says `development` for every copy built here.

    **Read the `mod` line, never `path`.** `path` carries the command subdirectory
    and a `/v5` or `/v2` major-version suffix that is part of the import path
    rather than a version.

    None where `go` cannot answer, same as a probe that would not say.
    """
    go = toolchain.go_command()
    if not go:
        return None
    result = effects.run([go, 'version', '-m', str(binary)], output=Output.QUIET, timeout=MODULE_INFO_SECONDS)
    if not result.ok:
        return None
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[0] == 'mod':
            return fields[2]
    return None


PSEUDO_VERSION = re.compile(r'-\d{14}-[0-9a-f]{12}$')
"""The suffix `go` appends where it resolved a commit rather than a tag.

A timestamp and a commit prefix, specified at golang.org/ref/mod#pseudo-versions.
Matched as a format the toolchain defines, which is not the same act as reading a
version string to guess what produced it — this is the toolchain saying, in its
own notation, that there was no tag to resolve.
"""

UNVERSIONED = '(devel)'
"""What `go` writes in the `mod` record of a binary built outside a module release.

The second notation the toolchain has for "no version here", and the one that does
not look like one — parentheses rather than a version-shaped string, so it reads as
a tag to anything testing for a pseudo-version suffix. `versions.parse` then returns
None for it, and a tool with a perfectly good banner measures as UNKNOWN.

Every goreleaser build writes it, which makes this the normal state of a Go tool
installed from a release asset rather than through the module proxy — the offline
bundle's whole path. Measured 2026-08-17 against upstream's own
`ascii-image-converter_Linux_amd64_64bit.tar.gz`: `mod (devel)` beside a banner
reading `v1.13.1`, and the box that installed it from a bundle had carried the tool
as unmeasurable ever since.
"""


def tagged(version: str | None) -> bool:
    """Whether `go` resolved this binary from a release rather than a commit.

    A pseudo-version like `v0.0.0-20260216134545-b8098dc1b9de` parses as `(0, 0,
    0)`, below every published release — so a currency comparison makes it
    permanently behind and reinstalls it on every apply.

    **No single record is authoritative.** Across the declared tools every
    combination occurs: pseudo-versioned with a correct banner, correctly tagged
    with a `0.0.0` banner, correctly tagged with a `development` banner. Only the
    module's failure announces itself, which is what this reads.
    """
    return bool(version) and version != UNVERSIONED and PSEUDO_VERSION.search(version or '') is None


def installed_modules(directory: Path) -> dict[str, str]:
    """Every binary in `directory`, to the module it was built from.

    One `go version -m` over the whole directory rather than one per binary.

    **Takes the directory rather than calling `gobin()`**, or a caller measuring a
    run's own home is answered about the home of the measuring process — which made
    every test in the packages suite read the machine it ran on.

    **Asked of `toolchain.go_command`, never of PATH.** A Mac has no `go` on PATH
    and answers `unknown` for every declared tool; an Arch box reached over ssh
    finds the pacman `/usr/bin/go` and answers plausibly with the wrong toolchain.

    Empty where `go` is absent or the directory does not exist, which is a machine
    with no Go tools rather than a failure.
    """
    go = toolchain.go_command()
    if not go or not directory.is_dir():
        return {}
    result = effects.run([go, 'version', '-m', str(directory)], output=Output.QUIET, timeout=MODULE_INFO_SECONDS)
    if not result.ok:
        return {}

    modules: dict[str, str] = {}
    binary = ''
    for line in result.stdout.splitlines():
        if not line.startswith('\t'):
            binary = Path(line.split(':', 1)[0]).name
            continue
        fields = line.split()
        if binary and len(fields) >= 3 and fields[0] == 'mod':
            modules[binary] = fields[1]
            binary = ''
    return modules


def bundled(entry: catalog.GoTool) -> Path:
    return bundle_file(f'{BUNDLE_BINARIES}/{entry.executable}')


def stage(entry: catalog.GoTool, version: str, target: Target) -> str:
    """The release asset an offline bundle stages for this tool, by name.

    Here rather than in the bundler because it is the same question this module
    answers when installing — which file *is* this tool for this platform. The two
    once answered it in different files off different data, the bundler expanding
    `binary_pattern` and the installer globbing for whatever came out, so a pattern
    change moved one and not the other, silently, on the one machine that needs
    the bundle.

    Only the name: which release, downloading it, verifying it and where it lands
    in the bundle are the bundler's, and it is the only side with a network.
    """
    return releases.expand_pattern(entry.binary_pattern, version, target)


def install(entry: catalog.GoTool, *, offline: bool, floor: str) -> Result:
    """Converge one Go tool, from whichever source this run can reach.

    Offline takes the bundle and does not try the proxy at all. That is not
    caution: behind the work firewall `go install` does not fail fast, it hangs on
    a TLS handshake per tool, and thirteen of those is the difference between an
    install that finishes and one that looks broken.

    `floor` is what a staged bundle is ranked against before an online run installs
    from it, and it is required rather than defaulted. A default is the loop
    `bundle.behind_refusal` describes, restored by omission at a call site nothing
    would fail on — `registry.version_floor` is the one thing that knows the answer.
    """
    if offline:
        carried = _carried(entry)
        installed = _from_bundle(entry, carried[1]) if carried else None
        return installed or Result(
            False,
            f'{entry.name} is not in the offline bundle at {bundled(entry).parent}, and offline cannot reach the proxy',
            kind=Kind.NOT_IN_BUNDLE,
        )

    fetched = _from_proxy(entry)
    if fetched.ok:
        return fetched
    return _from_bundle_unless_behind(entry, fetched, floor)


def _from_bundle_unless_behind(entry: catalog.GoTool, failure: Result, floor: str) -> Result:
    """The bundle, on a run that had a network and could not install through it.

    Worth reaching at all because "online" here means a network rather than a
    reachable proxy. On a firewalled machine it never is, and without this every
    Go tool stays pinned at the version the machine was first built with while a
    current bundle sits unused on disk.

    Worth declining where the staged version is what is already installed, for the
    reason `bundle.behind_refusal` records. One `_carried` answers both halves, so
    the version ranked and the bytes written come out of one bundle.
    """
    carried = _carried(entry)
    if carried is None:
        return failure
    row, binary = carried
    return bundle.behind_refusal(row, floor, failure) or _from_bundle(entry, binary) or failure


def _carried(entry: catalog.GoTool) -> tuple[bundle.Staged | None, Path] | None:
    """The staged binary and its own bundle's row, or None where no bundle has the file.

    The file decides which bundle answers, because `bundled` is what installs and
    a row describes bytes rather than producing them. A root holding the binary and
    no row is a real state — the manifest is how a version travels and the file
    opens without one — so the row half is optional and the pair is not.

    Read from one root rather than asking `bundle.staged`, which merges rows
    newest-first across every staged bundle. A newer bundle recording `v3.46.0`
    whose extraction left no binary would otherwise lend its version to an older
    bundle's `v3.44.0` file, and the floor would pass on a version the bytes do not
    carry.

    The row is keyed by the declared name, which is what `create_bundle` records it
    under, while the file is named by `executable` — different questions wherever a
    Go tool declares a `command`.
    """
    for root in staged_bundles():
        binary = root / BUNDLE_BINARIES / entry.executable
        if binary.is_file():
            return bundle.row_in(root, entry.name, BUNDLE_CATEGORY), binary
    return None


def _from_proxy(entry: catalog.GoTool) -> Result:
    """`go install`, keeping what it said.

    Its output is the entire diagnosis behind the work firewall — the TLS error it
    prints there names the cause — and a caller that discarded it left a failure
    report saying only that the command exited non-zero.
    """
    go = toolchain.go_command()
    if not go:
        return Result(False, f'there is no go at {toolchain.GO_ROOT / "bin" / "go"} to install with', kind=Kind.PREREQUISITE_MISSING)

    # Still placed on PATH, for the child rather than for this command: `go
    # install` shells out to git for a module the proxy will not serve, and git
    # is reached by name.
    toolchain.put_on_path(toolchain.GO_ROOT / 'bin')
    completed = effects.run([go, 'install', f'{entry.package}@latest'], output=Output.QUIET)
    if completed.ok:
        return Result(True, f'{entry.executable} installed from {entry.package}', kind=Kind.APPLIED)

    # `go: downloading` lines are progress, and they are most of the transcript
    # for a tool with a large dependency tree.
    said = '\n'.join(line for line in completed.transcript.splitlines() if not line.startswith('go: downloading'))
    return Result(False, f'go install {entry.package}@latest exited {completed.returncode}: {said.strip()}', kind=Kind.COMMAND_FAILED)


def _from_bundle(entry: catalog.GoTool, cached: Path) -> Result | None:
    """Install one staged binary, or None where it is not there to install.

    Handed the file rather than resolving it, so the version a caller ranked and
    the bytes written here cannot come from two bundles — `_carried` records what
    that costs when they do.

    None rather than a failed Result, so a caller can tell "the bundle does not
    have this" from "the bundle has it and it would not install" — only the first
    is a reason to fall through to something else.
    """
    if not cached.is_file():
        return None

    destination = gobin() / entry.executable
    try:
        place(cached, destination)
    except OSError as refused:
        return Result(False, f'could not install {entry.executable} from {cached}: {refused}', kind=Kind.WRITE_FAILED)
    return Result(True, f'{entry.executable} installed from the bundle at {cached}', kind=Kind.APPLIED)
