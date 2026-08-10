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

from pathlib import Path

from dotfiles import catalog
from dotfiles import effects
from dotfiles.coordinates import Target
from dotfiles.effects import Output
from dotfiles.providers import Result
from dotfiles.providers import bundle_file
from dotfiles.providers import place
from dotfiles.providers import releases

BUNDLE_BINARIES = 'go-binaries'


def gobin() -> Path:
    """Where `go install` puts a binary, and so where one from a bundle goes too.

    A function rather than a constant so a test can move `HOME`, for the reason
    `providers.local_dir` records: read at import it would freeze the real home
    into every test in the process.
    """
    return Path.home() / 'go' / 'bin'


def bundled(entry: catalog.GoTool) -> Path:
    return bundle_file(BUNDLE_BINARIES) / entry.executable


def stage(entry: catalog.GoTool, version: str, target: Target) -> str:
    """The release asset an offline bundle stages for this tool, by name.

    Here rather than in the bundler because it is the same question this module
    answers when installing — which file *is* this tool for this platform — and
    the two used to answer it in different files off different data. The bundler
    read `binary_pattern` out of a pipe-joined `parse_packages` row while the
    installer globbed for whatever came out, so a pattern change moved one and
    not the other, silently, on the one machine that needs the bundle.

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
            False, f'{entry.name} is not in the offline bundle at {bundled(entry).parent}, and offline cannot reach the proxy'
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
    completed = effects.run(['go', 'install', f'{entry.package}@latest'], output=Output.QUIET)
    if completed.ok:
        return Result(True, f'{entry.executable} installed from {entry.package}')

    # `go: downloading` lines are progress, and they are most of the transcript
    # for a tool with a large dependency tree.
    said = '\n'.join(line for line in completed.transcript.splitlines() if not line.startswith('go: downloading'))
    return Result(False, f'go install {entry.package}@latest exited {completed.returncode}: {said.strip()}')


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
        return Result(False, f'could not install {entry.executable} from {cached}: {refused}')
    return Result(True, f'{entry.executable} installed from the bundle at {cached}')
