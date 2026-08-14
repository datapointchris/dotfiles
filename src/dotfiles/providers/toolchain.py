"""Installing the language runtimes, one function per version manager.

Four unrelated mechanisms wearing one word, which is why this is four functions
rather than an engine with the variation pushed into a data class. uv and rustup
publish an install script and are two more callers of `providers/script.py`; Go
publishes a tarball that belongs under `/usr/local`, making it the one runtime
whose install needs root; Node is whatever fnm pins as its default alias, and fnm
itself arrives as a cargo package earlier in the same run.

*Which* of them a machine needs is not decided here. `registry.ToolchainProvider`
derives that from the tool sections that need one, so what is left here is only
how each is put on the box.

Every failure is returned rather than raised, like the custom installers: one
runtime that cannot install must not stop the other three, and the run reports
all of them together.

**A successful install puts its bin directory on this process's PATH.** The
converged providers run in one process, so a runtime installed at stage 30 is
invisible to the tools at stage 40 unless this happens — `shutil.which` reads
`os.environ`, and every command `effects.run` starts inherits it. `.zshenv` says
the same thing for the *next* shell, which is the one shell that cannot help the
run doing the installing.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from dotfiles import effects
from dotfiles import github_release
from dotfiles import paths
from dotfiles.coordinates import Target
from dotfiles.effects import Output
from dotfiles.privilege import Privilege
from dotfiles.privilege import PrivilegeUnavailable
from dotfiles.privilege import refusal
from dotfiles.providers import BIN_DIR
from dotfiles.providers import Kind
from dotfiles.providers import Result
from dotfiles.providers import bin_dir
from dotfiles.providers import npm
from dotfiles.providers import script

# ─────────────────────────────────────────────────────────────────────────────
# uv
# ─────────────────────────────────────────────────────────────────────────────

UV_INSTALL_URL = 'https://astral.sh/uv/install.sh'
"""Also spelled in `install.sh`, and that duplicate is the bootstrap's defining
property rather than an oversight: it runs before this package exists to be
asked. The offline bundler reads it from here, which retired the third copy."""

DEFAULT_PYTHON = '3.13'
"""The interpreter `uv run` resolves against when a project pins nothing."""


def install_uv(*, offline: bool) -> Result:
    """uv itself, then the interpreter everything else resolves against.

    The first half is nearly always a no-op: `install.sh` puts uv on the box
    before this package exists to be run, so the CLI is already running on it.
    The second half is the part with no other home — the bootstrap installs uv in
    order to install this package, and which Python is *default* afterwards is a
    convergence question about the machine rather than a bootstrap one.
    """
    if shutil.which('uv') is None:
        placed = script.run(
            'uv',
            UV_INSTALL_URL,
            offline=offline,
            env={'XDG_BIN_HOME': str(bin_dir()), 'UV_NO_MODIFY_PATH': '1'},
        )
        if not placed.ok:
            return placed
        put_on_path(bin_dir())
        if shutil.which('uv') is None:
            return Result(False, f'the uv install script ran but uv is not in {bin_dir()}', kind=Kind.VERIFY_FAILED)

    chosen = effects.run(
        ['uv', 'python', 'install', '--preview-features', 'python-install-default', '--default', DEFAULT_PYTHON],
    )
    if not chosen.ok:
        return Result(
            False,
            f'uv is installed but making python {DEFAULT_PYTHON} the default exited {chosen.returncode}',
            kind=Kind.COMMAND_FAILED,
        )
    return Result(True, f'uv, with python {DEFAULT_PYTHON} as the default', kind=Kind.APPLIED)


# ─────────────────────────────────────────────────────────────────────────────
# rust
# ─────────────────────────────────────────────────────────────────────────────

RUSTUP_URL = 'https://sh.rustup.rs'

CARGO_BIN = Path('.cargo/bin')


def install_rust(*, offline: bool) -> Result:
    """rustup, which is what puts `rustc` and `cargo` on the machine.

    `--no-modify-path` because PATH belongs to this repo: `.zshenv` already names
    `~/.cargo/bin`, and letting rustup append its own line to a shell rc would put
    a second writer on a file the symlink pass owns.

    Nothing stages rustup in the offline bundle, so an offline run is refused with
    that reason rather than left to fail inside curl. That costs an offline machine
    nothing it could have had: `providers/cargo.py` takes every declared package
    from the bundle rather than from a compiler, so the tools arrive without it.
    """
    placed = script.run('rustup', RUSTUP_URL, offline=offline, args=['-y', '--no-modify-path'])
    if not placed.ok:
        return placed

    put_on_path(Path.home() / CARGO_BIN)
    reported = effects.run(['rustc', '--version'], output=Output.QUIET)
    if not reported.ok:
        return Result(False, f'rustup ran but rustc is not in {Path.home() / CARGO_BIN}', kind=Kind.VERIFY_FAILED)
    return Result(True, reported.transcript.strip(), kind=Kind.APPLIED)


# ─────────────────────────────────────────────────────────────────────────────
# go
# ─────────────────────────────────────────────────────────────────────────────

GO_VERSION_URL = 'https://go.dev/VERSION?m=text'
GO_DOWNLOAD_URL = 'https://go.dev/dl'
GO_ROOT = Path('/usr/local/go')

GO_ENV_SECONDS = 10.0
"""`go env` reads and writes one small file — no proxy, no network — so this
bounds a stuck subprocess rather than a slow download."""

GO_BIN = Path('go/bin')
"""Where `go install` writes, relative to home — `GOPATH/bin` with GOPATH unset.

Beside `GO_ROOT` rather than in `gotool` because `TOOL_PATH_DIRS` has to name it
and cannot import a module that imports this one. `gotool.gobin()` reads it from
here, so the two cannot come apart.
"""


def go_command() -> str | None:
    """The `go` this repo installed, in preference to whatever PATH offers.

    `shutil.which` asks a different question, and both fleet machines answer it
    wrong. `.zshrc` added `/usr/local/go/bin` on Linux only, so a Mac found no
    `go` at all; an Arch shell that never sourced `.zshrc` found the pacman
    `/usr/bin/go` instead. Measured 2026-08-14: the Mac reported all 18 Go tools
    unmeasurable, and Arch read their build info with a go1.26.6 the repo did not
    install while its own go1.26.5 sat unused.

    `resources/toolchains.py` reached this rule from the other side — ask the
    provider where it put the runtime, never PATH what it can see. A measurement
    that consults PATH is measuring the shell that launched the run.

    Falls back to PATH so a machine whose Go came from elsewhere still measures,
    and answers None where there is no `go` at all.
    """
    installed = GO_ROOT / 'bin' / 'go'
    if installed.is_file():
        return str(installed)
    return shutil.which('go')


GONOSUMDB = 'github.com/datapointchris/*'
"""A cold sum.golang.org lookup for a just-published version holds the connection
for ~60s and then answers 500, and `go install` retries — so updating an
own-namespace tool minutes after tagging it stalls for minutes with no output.

**Not every repo in this namespace is public, and one of them is why this is
load-bearing rather than a latency tweak.** `fleet` is private, so the checksum
database cannot read it at all: it fetches a module to hash it, fails to
authenticate, and answers 404. `go install github.com/datapointchris/fleet@latest`
then refuses to verify and installs nothing.

The proxy is still deliberately left alone. GOPRIVATE would bypass that too, and
it does not need bypassing — `GOPROXY` ends in `,direct`, so resolution already
falls through to git, which authenticates through `gh auth git-credential`.
Measured 2026-08-14: with this set and nothing else changed, `fleet` builds."""


def install_go(target: Target, privilege: Privilege, *, offline: bool) -> Result:
    """Whatever go.dev currently serves, unpacked over `/usr/local/go`.

    Go is the one runtime with no version manager of its own, so this is the
    manager: resolve what upstream calls current, fetch the tarball, and replace
    the whole tree. `/usr/local/go` because that is where go.dev puts it on macOS
    and Linux alike, so there is no platform branch to write.

    Moving it is a change to `GO_ROOT` and to `.zshenv`, and to nothing else:
    `TOOL_PATH_DIRS`, `go_command` and the registry's `installed_at` all read it
    from there. `.zshenv` is the one copy that cannot, and `tests/cli/test_apply.py`
    is what holds it in step.
    """
    if offline:
        return Result(
            False,
            f'go installs from {GO_DOWNLOAD_URL}, which the offline bundle at {paths.BUNDLE_DIR} does not stage',
            kind=Kind.NOT_IN_BUNDLE,
            refused=True,
        )

    release = latest_release()
    if release is None:
        return Result(False, f'could not read the current Go release from {GO_VERSION_URL}', kind=Kind.VERSION_UNRESOLVED)

    archive_name = f'{release}.{go_platform(target)}.tar.gz'
    with tempfile.TemporaryDirectory(prefix='dotfiles-go-') as scratch:
        staging = Path(scratch)
        archive = _tarball(archive_name, staging)
        if archive is None:
            return Result(
                False,
                f'could not download {GO_DOWNLOAD_URL}/{archive_name}, and no copy of it is in {Path.home()}',
                kind=Kind.DOWNLOAD_FAILED,
            )

        unpacked = staging / 'unpacked'
        if not effects.unpack(archive, unpacked):
            return Result(False, f'{archive_name} would not extract', kind=Kind.ARCHIVE_UNREADABLE)
        if not (unpacked / 'go' / 'bin' / 'go').is_file():
            return Result(False, f'{archive_name} carries no go/bin/go', kind=Kind.ARCHIVE_INCOMPLETE)

        replaced = _replace_goroot(unpacked / 'go', privilege)
        if not replaced.ok:
            return replaced

    installed = effects.run([str(GO_ROOT / 'bin' / 'go'), 'version'], output=Output.QUIET)
    if not installed.ok:
        return Result(False, f'{GO_ROOT / "bin" / "go"} does not run after installing {release}', kind=Kind.VERIFY_FAILED)

    put_on_path(GO_ROOT / 'bin')
    set_go_env()
    return Result(True, installed.transcript.strip(), kind=Kind.APPLIED)


def latest_release(url: str = GO_VERSION_URL) -> str | None:
    """What go.dev calls current, as a release name: `go1.26.5`."""
    try:
        answered = github_release.request(url).decode()
    except OSError:
        return None
    first = answered.strip().splitlines()
    return first[0].strip() if first else None


def go_platform(target: Target) -> str:
    """`linux-amd64`, `darwin-arm64` — Go's own spelling of a platform.

    `amd64` rather than the `x86_64` this repo's `Arch` uses, because a release
    asset is named by whoever publishes it and Go publishes Go's names.
    """
    return f'{target.os_family}-{"arm64" if target.is_arm else "amd64"}'


def _tarball(name: str, into: Path) -> Path | None:
    """The tarball, from go.dev or from a copy left in `$HOME`.

    The home-directory fallback is the work firewall's escape hatch and predates
    this: fetch the tarball by hand on a machine that can reach go.dev, drop it in
    `$HOME`, re-run. It only helps once the *version* has been resolved, which is
    why an unreachable go.dev fails above rather than here.
    """
    archive = into / name
    if effects.fetch(f'{GO_DOWNLOAD_URL}/{name}', archive):
        return archive

    manual = Path.home() / name
    if manual.is_file():
        shutil.copy2(manual, archive)
        return archive
    return None


def _replace_goroot(unpacked: Path, privilege: Privilege) -> Result:
    """Swap the whole tree, which is the only supported way to move Go versions.

    Unpacked as this user first and copied in as root, rather than handing the
    tar to `sudo tar -C /usr/local`: `effects.unpack` extracts under
    `filter='data'`, which refuses absolute paths, `..` traversal and device
    nodes. The shell this replaces applied no such filter to an archive off the
    internet.
    """
    try:
        removed = privilege.run(['rm', '-rf', str(GO_ROOT)], reason=f'replace the Go toolchain in {GO_ROOT}')
        if not removed.ok:
            return Result(False, f'could not remove {GO_ROOT}: {removed.transcript.strip()}', kind=Kind.WRITE_FAILED)
        placed = privilege.run(['cp', '-a', str(unpacked), str(GO_ROOT)], reason=f'install the Go toolchain into {GO_ROOT}')
    except PrivilegeUnavailable:
        return Result(False, refusal(privilege.state), kind=Kind.PRIVILEGE_UNAVAILABLE)

    if not placed.ok:
        return Result(False, f'could not write {GO_ROOT}: {placed.transcript.strip()}', kind=Kind.WRITE_FAILED)
    return Result(True, '', kind=Kind.APPLIED)


def go_env_setting(go: str | Path, name: str) -> str | None:
    """What `go env` answers for one variable, asked of a named binary.

    Read back rather than assumed, which is the whole difference between a fact
    this run measured and one an earlier run is believed to have written. The
    empty string is a real answer — it means unset — so only a `go` that would
    not run is None.

    Takes the binary rather than resolving one, for the reason
    `gotool.installed_modules` takes its directory: a caller measuring a runtime
    it has already located must be answered about *that* runtime. Resolving here
    made the toolchains suite shell out to the real `/usr/local/go/bin/go` on
    whichever machine ran it, past the stub the test had just placed.
    """
    asked = effects.run([str(go), 'env', name], output=Output.QUIET, timeout=GO_ENV_SECONDS)
    return asked.stdout.strip() if asked.ok else None


def set_go_env() -> Result:
    """Put the declared module settings into the Go env file.

    Written to that file rather than to shell config because tool installs run
    non-interactively and never source one.

    **Public, and no longer reached only from `install_go`.** As a private step
    inside the installer it ran exactly when a machine's Go was replaced, which on
    a machine that already has Go is never: the toolchain is measured against a
    floor of 1.23, an installed 1.26.5 clears it forever, and `install_go` is not
    called again. Measured 2026-08-14 across the fleet — no machine had ever
    received this setting from this code. The one box carrying it had a file dated
    2026-08-08, written by the bash predecessor a day before this module existed.
    """
    go = go_command()
    if not go:
        return Result(False, f'there is no go at {GO_ROOT / "bin" / "go"} to configure', kind=Kind.PREREQUISITE_MISSING)
    written = effects.run([go, 'env', '-w', f'GONOSUMDB={GONOSUMDB}'], output=Output.QUIET, timeout=GO_ENV_SECONDS)
    if not written.ok:
        return Result(False, f'`go env -w GONOSUMDB` exited {written.returncode}: {written.transcript.strip()}', kind=Kind.COMMAND_FAILED)
    return Result(True, f'GONOSUMDB={GONOSUMDB}', kind=Kind.APPLIED)


# ─────────────────────────────────────────────────────────────────────────────
# node
# ─────────────────────────────────────────────────────────────────────────────

NODE_DEFAULT_VERSION = '24'
"""The version most of the portfolio pins and every CI workflow uses. Held here
rather than read from any one repo's `.nvmrc`: this is what a project with no pin
at all gets, and a repo wanting another version says so itself.

Not a `runtimes` row, because `version:` there means an exact pin and this is a
major line — `fnm install 24` takes the newest 24.x. Declaring it properly needs
the pin/floor vocabulary in `.planning/version-constraints.md` to grow a third
answer."""

FNM_HOME = Path('.local/share/fnm')

FNM_ALIAS_BIN = Path('aliases/default/bin')
"""fnm's default alias, relative to whichever fnm home a run resolved.

Relative rather than absolute because `install_node` honours an `FNM_DIR`
override and `TOOL_PATH_DIRS` cannot — one names the directory a run was told to
use, the other the directory `.zshenv` hardcodes.
"""


def install_node(home: Path, *, offline: bool) -> Result:
    """The fleet's default Node, linked as fnm's `default` alias.

    The alias is what `.zshenv` puts on PATH, so this is what a bare `node`
    resolves to in every non-interactive shell — pre-commit hooks, scripts,
    agents. A repo pinning something else in `.nvmrc` gets it from `--use-on-cd`
    in `.zshrc`, or from `fnm exec` when the caller is not an interactive shell.
    """
    if shutil.which('fnm') is None:
        return Result(
            False,
            "fnm is not on PATH — it ships as a cargo package, so check this machine's cargo_packages",
            kind=Kind.PREREQUISITE_MISSING,
        )
    if offline:
        return Result(
            False,
            f'fnm downloads Node {NODE_DEFAULT_VERSION} from nodejs.org, which the offline bundle does not stage',
            kind=Kind.NOT_IN_BUNDLE,
            refused=True,
        )

    directory = os.environ.get('FNM_DIR') or str(home / FNM_HOME)
    for command in (('fnm', 'install', NODE_DEFAULT_VERSION), ('fnm', 'default', NODE_DEFAULT_VERSION)):
        completed = effects.run(list(command), env={'FNM_DIR': directory})
        if not completed.ok:
            return Result(False, f'`{" ".join(command)}` exited {completed.returncode}', kind=Kind.COMMAND_FAILED)

    alias = Path(directory) / FNM_ALIAS_BIN
    put_on_path(alias)
    reported = effects.run([str(alias / 'node'), '--version'], output=Output.QUIET)
    if not reported.ok:
        return Result(False, f'fnm reported success but there is no node at {alias}', kind=Kind.VERIFY_FAILED)
    return Result(True, f"node {reported.transcript.strip()} is fnm's default alias", kind=Kind.APPLIED)


def _under_home(relative: Path) -> str:
    """One home-relative directory, spelled the way a shell reads it.

    `$HOME` rather than a resolved path because the readers are `.zshenv` and a
    container's PATH, and both run under a home this process does not have.
    """
    return f'$HOME/{relative}'


TOOL_PATH_DIRS = (
    _under_home(FNM_HOME / FNM_ALIAS_BIN),
    _under_home(npm.PREFIX / 'bin'),
    _under_home(BIN_DIR),
    _under_home(CARGO_BIN),
    _under_home(GO_BIN),
    str(GO_ROOT / 'bin'),
    '/usr/local/bin',
)
"""Where a stage finds what an earlier stage installed.

Nothing in a run reads `.zshenv`, so a tool is invisible to the provider that
consumes it unless it is named here: the cargo provider needs `cargo` from rustup,
the node toolchain needs the fnm that arrives as a cargo package, and npm-globals
needs the Node that fnm links as its default alias. Order mirrors `.zshenv` so a
run resolves the same binary an interactive shell would.

**Every entry is read from whichever module installs into it**, so a provider
that moves its directory moves this list with it. Retyping them is what the
`.zshenv` history records: the npm prefix reached three of the four lists that
name these directories and not the fourth, and eleven installed language servers
reported missing. Only npm was bound to its owner after that, and the entry that
stayed a literal is the one that went wrong next — `/usr/local/go/bin` was in
this tuple and in neither shell file, on any platform, for as long as the file
has existed.

This is the *declaration* of those directories rather than something applied
here: `put_on_path` is what places them, called by each provider as it installs.
What reads the list is the e2e harness, which has to rebuild the PATH `docker
exec` does not supply, and the test that holds `.zshenv` to it.
"""


def put_on_path(directory: Path) -> None:
    """Make what was just installed visible to the rest of this run.

    Mutating `os.environ` rather than threading a PATH through every caller,
    because that is what both readers already consult: `shutil.which` reads it
    directly, and `effects.run` merges it into every child.
    """
    entry = str(directory)
    current = os.environ.get('PATH', '')
    if entry not in current.split(os.pathsep):
        os.environ['PATH'] = os.pathsep.join([entry, current]) if current else entry
