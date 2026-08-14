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
writes `go-binaries/<name>` and the bash read `$HOME/installers/go-binaries/$name`
from a different file; one of them moving was a silent miss on the one machine
that needs it.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from dotfiles import catalog
from dotfiles import effects
from dotfiles.coordinates import Target
from dotfiles.effects import Output
from dotfiles.providers import Kind
from dotfiles.providers import Result
from dotfiles.providers import bundle_file
from dotfiles.providers import place
from dotfiles.providers import releases
from dotfiles.providers import toolchain

BUNDLE_BINARIES = 'go-binaries'


def gobin() -> Path:
    """Where `go install` puts a binary, and so where one from a bundle goes too.

    A function rather than a constant so a test can move `HOME`, for the reason
    `providers.local_dir` records: read at import it would freeze the real home
    into every test in the process.
    """
    return Path.home() / 'go' / 'bin'


MODULE_INFO_SECONDS = 10.0
"""`go version -m` reads one binary's embedded build info off disk — no proxy,
no network — so this bounds a stuck subprocess, not a slow download."""


def module_version(binary: Path) -> str | None:
    """The module version `go install` actually resolved, read back from the
    binary rather than asked of it.

    Exact where `--version` is not: the toolchain has stamped this into every
    binary it links since 1.18, using the same module-and-version pair `go
    install <module>@latest` resolved, while a vendor's own banner is whatever
    `-ldflags -X` a *release* build stamped it with — a flag `go install` never
    passes, which is why `gdu --version` says `development` for every copy this
    machine has ever built.

    The `mod` line is the one to read, not `path`: `path` carries the module
    below its command directory and, for gdu and sesh, a `/v5` or `/v2` major
    version suffix that is part of the import path and not a version at all.
    `mod` names the same module once more and follows it with the version on its
    own, so nothing here has to strip a suffix to tell the two apart.

    None where `go` cannot answer this — missing from PATH, or a binary it does
    not recognise as one it built — same as a probe that would not say.
    """
    go = shutil.which('go')
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


def tagged(version: str | None) -> bool:
    """Whether `go` resolved this binary from a release rather than a commit.

    The half of `module_version` that decides whether its answer is a version at
    all. `cheat` installs at `v0.0.0-20260216134545-b8098dc1b9de`, which
    `versions.parse` reads as `(0, 0, 0)` — below every release anyone publishes,
    so a currency comparison makes it permanently behind and reinstalls it on
    every apply. That is the same failure `0.0.0` in a vendor banner produces, one
    record over, and preferring the module unconditionally moved it rather than
    fixed it.

    Measured 2026-08-13 across the three fleet machines: `cheat` pseudo-versioned
    with a correct `5.1.0` banner, `docker-language-server` tagged `v0.20.1` with a
    `0.0.0` banner, `gdu` tagged `v5.36.1` with a `development` banner. No single
    record is authoritative; each fails in its own way, and only the module's
    failure announces itself.
    """
    return bool(version) and PSEUDO_VERSION.search(version or '') is None


def installed_modules(directory: Path) -> dict[str, str]:
    """Every binary in `directory`, to the module it was built from.

    One `go version -m` over the whole directory rather than one per binary: the
    toolchain accepts a directory and answers for everything in it, which is the
    difference between one subprocess and one per tool every time a check runs.

    Reads the `mod` line for the reason `module_version` records — `path` carries
    a command subdirectory and a major-version suffix, while `mod` names the
    module once and cleanly.

    Takes the directory rather than calling `gobin()`, for the reason
    `evidence.executables_on_path` takes the checkout: a caller measuring a run's
    own home must not be answered about the home of the process doing the
    measuring. Reading `Path.home()` here made every test in the packages suite
    read the machine it ran on.

    Empty where `go` is absent or the directory has never been created, which is
    a machine with no Go tools rather than a failure.
    """
    go = shutil.which('go')
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
    return bundle_file(BUNDLE_BINARIES) / entry.executable


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


def install(entry: catalog.GoTool, *, offline: bool) -> Result:
    """Converge one Go tool, from whichever source this run can reach.

    Offline takes the bundle and does not try the proxy at all. That is not
    caution: behind the work firewall `go install` does not fail fast, it hangs on
    a TLS handshake per tool, and thirteen of those is the difference between an
    install that finishes and one that looks broken.
    """
    if offline:
        return _from_bundle(entry) or Result(
            False,
            f'{entry.name} is not in the offline bundle at {bundled(entry).parent}, and offline cannot reach the proxy',
            kind=Kind.NOT_IN_BUNDLE,
        )

    fetched = _from_proxy(entry)
    if fetched.ok:
        return fetched

    # The bundle is worth trying even on an online run, because "online" here
    # means a network — not a reachable proxy. On a firewalled machine it never
    # is, and without this every Go tool stays pinned at the version the machine
    # was first built with while a current bundle sits unused on disk.
    if restored := _from_bundle(entry):
        return restored
    return fetched


def _from_proxy(entry: catalog.GoTool) -> Result:
    """`go install`, keeping what it said.

    Its output is the entire diagnosis behind the work firewall — the TLS error it
    prints there names the cause — and a caller that discarded it left a failure
    report saying only that the command exited non-zero.
    """
    # `/usr/local/go/bin` reaches PATH as a side effect of *installing* Go, so a
    # machine whose toolchain is already current never places it and every tool
    # here fails with "go: command not found" — invisibly, because an interactive
    # shell has it from `.zshenv` and only the non-interactive callers (the timer,
    # cron, `docker exec`, ssh) do not. cargo does this unconditionally for the
    # same reason; this provider never got the same treatment.
    toolchain.put_on_path(toolchain.GO_ROOT / 'bin')
    completed = effects.run(['go', 'install', f'{entry.package}@latest'], output=Output.QUIET)
    if completed.ok:
        return Result(True, f'{entry.executable} installed from {entry.package}', kind=Kind.APPLIED)

    # `go: downloading` lines are progress, and they are most of the transcript
    # for a tool with a large dependency tree.
    said = '\n'.join(line for line in completed.transcript.splitlines() if not line.startswith('go: downloading'))
    return Result(False, f'go install {entry.package}@latest exited {completed.returncode}: {said.strip()}', kind=Kind.COMMAND_FAILED)


def _from_bundle(entry: catalog.GoTool) -> Result | None:
    """The prebuilt binary, or None where the bundle carries none.

    None rather than a failed Result, so a caller can tell "the bundle does not
    have this" from "the bundle has it and it would not install" — only the first
    is a reason to fall through to something else.
    """
    cached = bundled(entry)
    if not cached.is_file():
        return None

    destination = gobin() / entry.executable
    try:
        place(cached, destination)
    except OSError as refused:
        return Result(False, f'could not install {entry.executable} from {cached}: {refused}', kind=Kind.WRITE_FAILED)
    return Result(True, f'{entry.executable} installed from the bundle at {cached}', kind=Kind.APPLIED)
