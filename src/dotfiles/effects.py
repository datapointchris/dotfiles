"""The only module that touches the world outside this process.

Six doors are planned — `run`, `fetch`, `write`, `link`/`unlink`, `extract`,
`chmod` — and four exist, arriving as each resource moves. `write` and
`link`/`unlink` wait on the resources that need them.

The three added for the release engine are deliberately ignorant of what they are
unpacking. `unpack` sniffs a container rather than reading a declared archive
kind, so `providers.releases.Archive` stays a statement about what upstream
publishes and never becomes a second thing that has to be right for extraction to
work. That vocabulary belongs above this line, not on it.

Everything here is a chokepoint on purpose. A resource that reaches the world
some other way cannot be tested without the world.

Which is also why the debug event stream is emitted from here and nowhere else.
The questions asked after a failed install are what did it actually download and
which step was slow, and both are answered one level *below* the run record — the
record says an item took nine seconds, and only these lines say which of the four
commands behind it did. Instrumenting the walk instead would restate the record
in a second format.
"""

from __future__ import annotations

import gzip
import os
import shutil
import subprocess
import sys
import tarfile
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from dotfiles import github_release
from dotfiles import logging

log = logging.get_logger('effects')


class Output(StrEnum):
    """Where a child's output goes, which is a different question per caller."""

    STREAM = 'stream'
    """Merged and echoed to our stderr as it arrives, and kept. The default.

    Merged and streamed rather than buffered for the reason
    `install/run-installer.sh:34-38` records: buffering is what made a long
    install look hung, and capturing stderr alone silently dropped TPM's cause,
    which it prints on stdout. Echoed to *our* stderr because a shelled-out
    installer's chatter is a diagnostic of this process — which is what keeps
    `--json` parseable while it is talking.
    """

    DATA = 'data'
    """Streams inherited, nothing kept: the child's stdout is the caller's.

    For a child whose output is meant to be parsed or piped (`env show`), where
    routing it to stderr would break the pipeline it exists to feed.
    """

    QUIET = 'quiet'
    """Kept, echoed nowhere. For a probe whose output is evidence, not a message.

    `git config --get user.email` answers a question; printing its answer as
    though it were progress is noise in the middle of a check.
    """


ANSWER_LIMIT = 200
"""How much of a successful command's stdout the run log keeps.

Long enough for the answers whose whole content is the answer — a version
string, a resolved path, a one-line status — and far short of an install
transcript. The cut is by length rather than by naming which commands count,
because the caller that would have to declare it is every provider.
"""

NOT_FOUND = 127
"""A command that does not exist, as a shell reports it rather than as a crash."""

TIMED_OUT = 124
"""What `timeout(1)` exits with, so a bounded probe reports what the shell would."""


@dataclass(frozen=True)
class Completed:
    """What a subprocess did. `transcript` is empty when output was not captured."""

    command: tuple[str, ...]
    returncode: int
    transcript: str

    stdout: str = ''
    """The answer alone. Parse this; `transcript` is for reading, not for parsing.

    `transcript` is stdout and stderr concatenated, which is right for a diagnosis
    — `go install`'s TLS error and npm's warnings are the whole point of keeping
    it — and wrong for anything that reads fields out of lines. `brew outdated
    --formula --quiet` printed one package and brew's auto-update wrote a `✔︎`
    progress line to stderr, so the currency row reported `2 brew package(s)
    behind: ollama, ✔︎`. `syspkg._names` already carried a guard against apt's
    chatter, which is the same disease treated one manager at a time.

    Only `Output.QUIET` separates the two. `Output.STREAM` redirects stderr into
    the stdout pipe deliberately, so there is no separated answer to give and this
    stays empty rather than handing back the merged text under a name that says
    otherwise — empty parses to nothing, where merged text parses to something
    wrong.
    """

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run(
    command: list[str] | tuple[str, ...],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    unset: tuple[str, ...] = (),
    output: Output = Output.STREAM,
    show: Callable[[str], str | None] | None = None,
    timeout: float | None = None,
) -> Completed:
    """Run a command. See `Output` for where its output goes and why.

    `unset` removes variables, which `env` cannot: it merges over this process's
    environment, so the most it can do is blank one. TPM is the case that needs
    the difference — `$TMUX` names the live server's socket and outranks the
    `TMUX_TMPDIR` a caller sets, so a plugin install started from inside a session
    drives the user's real tmux however carefully the rest is arranged, and an
    empty `$TMUX` is set rather than absent.

    `show` filters what reaches the terminal without touching what is kept:
    returning None swallows a line, and the transcript is whole either way. Both
    plugin managers need it, and both had a filter in the shell they came from for
    one measured reason — lazy.nvim's headless output is fifty plugins' raw git
    spew, and sending that to a file instead left a fresh install with nothing on
    screen for minutes.

    `timeout` is for a caller that is *asking* rather than *installing*: a probe
    that has not answered is not answering, and one that never returns takes the
    whole run with it. `evidence.reported_version` is the case that proved it —
    the binary it probes is whatever a declaration names, and a GUI blocks on its
    event loop until a person closes a window, which on a scheduled check is
    never. Refused for STREAM, where minutes are a normal install rather than a
    hang, and where the reader loop would not observe a deadline anyway.

    **Every child's stdin is closed, on every branch, rather than inherited.**
    `yay -S --needed --noconfirm` still opens a menu when a name has several AUR
    providers — `--noconfirm` bypasses pacman's "Are you sure?" questions and
    nothing else, by pacman's own manual — and that menu reads its answer with
    `fgets(stdin, ...)`, unlike sudo's password prompt, which opens `/dev/tty`
    directly and so does not care what stdin is. Left inherited, the menu blocks
    on whatever this process's stdin happens to be: a real terminal when a person
    runs `dotfiles apply` by hand, which is a question nobody is watching for in
    the middle of a package transaction. Closed here, the read is EOF every time,
    which every caller observed to take the listed default — turning that from an
    accident of how stdin was wired into a guarantee this module makes.

    A missing binary is exit 127, not an exception. Every caller here already
    branches on the exit code, and several run something a machine may legitimately
    not have — `hyprctl` on an Arch box with no compositor is the one that proved
    it, taking down a whole install with a FileNotFoundError traceback from inside
    a symlink pass. Raising would mean each of those call sites needs its own
    `shutil.which` guard, and the one that forgets is a crash rather than a
    reported failure.
    """
    argv = tuple(command)
    environment = {**os.environ, **(env or {})}
    for name in unset:
        environment.pop(name, None)
    directory = str(cwd) if cwd else None

    if timeout is not None and output is Output.STREAM:
        raise ValueError('a streaming command has no deadline: its reader loop cannot observe one, and installs legitimately take minutes')
    if show is not None and output is not Output.STREAM:
        raise ValueError('only a streaming command echoes anything, so there is nothing for `show` to filter')

    began = time.perf_counter()

    def answered(completed: Completed) -> Completed:
        """Every command, on the way out, whichever of the five exits it took.

        The transcript only when the command failed. A successful `apt-get
        install` is thousands of lines nobody will ever read, and keeping all of
        them is how a debug stream turns into something people switch off — while
        a failed one is the entire reason the stream exists.

        The exception is a *short* successful answer, kept up to `ANSWER_LIMIT`.
        A version probe succeeds and its whole meaning is the one line it prints,
        so recording only the argv and the exit code makes an item that is
        permanently stale undiagnosable from the record: `toolbox --version`
        appears to have run fine, on every run, for weeks. That was measured — it
        is why the toolbox drift on one Mac could not be read from the shared run
        history and needed an ssh to answer.
        """
        fields = {
            'argv': list(argv),
            'returncode': completed.returncode,
            'seconds': round(time.perf_counter() - began, 3),
            'cwd': directory,
        }
        if not completed.ok:
            fields['transcript'] = completed.transcript
        elif (answer := completed.stdout.strip()) and len(answer) <= ANSWER_LIMIT:
            fields['answer'] = answer
        log.debug('ran', **fields)
        return completed

    def missing(problem: OSError) -> Completed:
        """A command the kernel would not start, reported as a shell reports one.

        Every `OSError` and not only the not-found and permission cases. `Exec
        format error` is a bare `OSError` — a PE32 binary reached on Linux, an
        architecture mismatch, a script with no interpreter — and an escaping one
        travels out of the provider, out of `observe`, and into a `Refusal` that
        takes a whole resource's measurement with it. A WSL container is where
        that is reachable: `win32yank` is a declared Windows executable with no
        Windows under it, and one unrunnable binary makes every package
        unmeasurable.
        """
        return answered(Completed(command=argv, returncode=NOT_FOUND, transcript=f'{argv[0]}: {problem.strerror}'))

    def expired(problem: subprocess.TimeoutExpired) -> Completed:
        """A timeout is a non-answer, in the shape every caller already handles.

        `subprocess.run` has already killed the child by the time this raises, so
        nothing is left running behind the report.
        """
        return answered(Completed(command=argv, returncode=TIMED_OUT, transcript=f'{argv[0]} did not answer within {problem.timeout:g}s'))

    if output is Output.DATA:
        try:
            completed = subprocess.run(argv, cwd=directory, env=environment, check=False, timeout=timeout, stdin=subprocess.DEVNULL)
        except OSError as problem:
            return missing(problem)
        except subprocess.TimeoutExpired as problem:
            return expired(problem)
        return answered(Completed(command=argv, returncode=completed.returncode, transcript=''))

    if output is Output.QUIET:
        try:
            captured = subprocess.run(
                argv, cwd=directory, env=environment, check=False, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL
            )
        except OSError as problem:
            return missing(problem)
        except subprocess.TimeoutExpired as problem:
            return expired(problem)
        return answered(
            Completed(
                command=argv,
                returncode=captured.returncode,
                transcript=captured.stdout + captured.stderr,
                stdout=captured.stdout,
            )
        )

    lines: list[str] = []
    try:
        with subprocess.Popen(
            argv,
            cwd=directory,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        ) as process:
            # `process.stdout` is not Optional in practice given stdout=PIPE, but the
            # stub says otherwise and the walrus keeps mypy from needing an assert.
            if stream := process.stdout:
                for line in stream:
                    lines.append(line)
                    if show is None:
                        sys.stderr.write(line)
                    elif (visible := show(line)) is not None:
                        sys.stderr.write(visible)
    except OSError as problem:
        return missing(problem)

    return answered(Completed(command=argv, returncode=process.returncode, transcript=''.join(lines)))


def fetch(url: str, destination: Path, *, repo: str = '', tag: str = '', asset_name: str = '') -> bool:
    """Download one file. The release-asset arguments are how a private repo works.

    Delegated rather than reimplemented: `github_release` already carries the
    asset-id fallback, and that module is stdlib-only because the offline bundler
    runs it under a system python3 this package cannot import into. One
    implementation, reachable from both.
    """
    began = time.perf_counter()
    ok = github_release.download_asset(url, destination, repo, tag, asset_name)
    log.debug(
        'fetched',
        url=url,
        destination=str(destination),
        repo=repo,
        tag=tag,
        ok=ok,
        seconds=round(time.perf_counter() - began, 3),
        # The literal answer to "what did it actually download", which a machine
        # behind a captive portal needs most: a fetch that reports success having
        # written a 900-byte login page looks identical to one that worked.
        bytes=destination.stat().st_size if destination.exists() else 0,
    )
    return ok


def unpack(archive: Path, into: Path) -> bool:
    """Extract a tar or zip, whichever it turns out to be.

    Sniffed rather than told, because the container is a property of the bytes and
    a caller that has to say which one is a caller that can be wrong about it.
    `tarfile` reads gzip, xz and bzip2 transparently, so the compression never
    needs naming either.

    Members are extracted under `filter='data'`, which refuses absolute paths,
    `..` traversal and device nodes. The tar these unpack came off the internet;
    the shell `tar -xf` this replaces applied no such filter.

    **A zip's permissions are restored by hand**, because `zipfile` discards them:
    `extractall` writes every member 0644 whatever the archive recorded. Every
    zip-distributed tool is therefore extracted non-executable, and the symptom is
    not an obvious one — `awscli` installed, symlinked, and answered `Permission
    denied`, which `shutil.which` reports as *not on PATH* because it tests for the
    execute bit. `tar -xf` and `unzip` both preserve the mode, so this is a
    regression the shell never had.
    """
    began = time.perf_counter()

    def extracted(container: str, ok: bool) -> bool:
        log.debug(
            'unpacked',
            archive=str(archive),
            into=str(into),
            container=container,
            ok=ok,
            seconds=round(time.perf_counter() - began, 3),
        )
        return ok

    into.mkdir(parents=True, exist_ok=True)
    try:
        if zipfile.is_zipfile(archive):
            with zipfile.ZipFile(archive) as zipped:
                for member in zipped.infolist():
                    restore_mode(member, zipped.extract(member, into))
            return extracted('zip', True)
        if tarfile.is_tarfile(archive):
            # A name of its own, not the zip's reused. One name bound to two
            # container types reads as one thing and typechecks as neither.
            with tarfile.open(archive) as tarred:
                tarred.extractall(into, filter='data')
            return extracted('tar', True)
    except (OSError, tarfile.TarError, zipfile.BadZipFile):
        return extracted('unreadable', False)
    # Neither sniffer recognised it, which is a different failure from one that
    # threw halfway through and worth being able to tell apart in the stream.
    return extracted('unrecognised', False)


def restore_mode(member: zipfile.ZipInfo, landed: str) -> None:
    """Put back the permission bits `extractall` dropped, on the file it wrote.

    **`landed` comes from the extractor, never from the member's name.** A zip
    records whatever name its author chose, and `ZipFile._extract_member` sanitises
    that — stripping drive letters, leading separators, `.` and `..` — before
    deciding where to write. Reconstructing the path instead means chmod-ing
    somewhere the extractor never touched: `into / '/etc/hosts'` is `/etc/hosts`,
    because `pathlib` resets on an absolute segment, and `into / '../x'` climbs out.
    A downloaded archive would then get an arbitrary chmod as the invoking user,
    while the file that *was* extracted kept the 0644 this exists to fix.
    `ZipFile.extract` returns the path it wrote, so there is one answer rather than
    two that can disagree.

    A zip records the creating system's mode in the high half of `external_attr`,
    and only when that system was unix — a zip written on Windows records nothing
    to restore, so a zero there is left alone rather than turned into 0000.

    Only the permission bits are taken. The file type bits in the same field would
    reintroduce exactly what `tarfile`'s `data` filter exists to refuse, and
    nothing here needs a zip to describe anything but a regular file or directory.
    """
    mode = (member.external_attr >> 16) & 0o7777
    if mode:
        Path(landed).chmod(mode)


def gunzip(source: Path, destination: Path) -> bool:
    """Decompress a bare gzipped file — a compressed binary, not an archive."""
    began = time.perf_counter()
    destination.parent.mkdir(parents=True, exist_ok=True)
    ok = True
    try:
        with gzip.open(source, 'rb') as compressed, destination.open('wb') as plain:
            shutil.copyfileobj(compressed, plain)
    except (OSError, gzip.BadGzipFile):
        ok = False
    log.debug('gunzipped', source=str(source), destination=str(destination), ok=ok, seconds=round(time.perf_counter() - began, 3))
    return ok


def make_executable(path: Path) -> None:
    """chmod +x, preserving whatever else the mode says."""
    path.chmod(path.stat().st_mode | 0o111)


NEW_SUFFIX = '.dotfiles-new'


def install(source: Path, target: Path) -> bool:
    """Put a downloaded file at `target`, even when `target` is running.

    Through a temporary name in the target's own directory and `os.replace`,
    never by writing into `target` itself. The kernel refuses to open a running
    executable for writing and returns ETXTBSY, and `shutil.copy2` and a
    `destination.open('wb')` both do exactly that.

    **`shutil.move` is not a way round it.** It renames only within one
    filesystem and falls back to copy-then-unlink across two, and here it is
    always across two: the download is staged in a `TemporaryDirectory` under
    `/tmp`, which is tmpfs, while `~/.local/bin` is on the root ext4. So the move
    that looks atomic degrades to a copy into the live path.

    Replacing unlinks the old inode instead of writing through it. A process
    still executing the old binary keeps its own inode and is undisturbed; the
    next start picks up the new one. That is why nothing has to be stopped before
    an apply, and why this needs no knowledge of what happens to be running.

    Measured on this fleet: `ntfy-client.service` has held `~/.local/bin/ntfy`
    for four days with `Restart=always`, so every apply refused with ETXTBSY and
    ntfy sat at 2.26.0 while 2.27.0 was published. Any long-running tool
    installed from a release had the same permanent failure.
    """
    began = time.perf_counter()
    target.parent.mkdir(parents=True, exist_ok=True)
    beside = target.with_name(f'.{target.name}{NEW_SUFFIX}')
    ok = True
    try:
        shutil.copy2(source, beside)
        beside.chmod(beside.stat().st_mode | 0o111)
        os.replace(beside, target)
    except OSError:
        ok = False
        beside.unlink(missing_ok=True)
    log.debug('installed', source=str(source), target=str(target), ok=ok, seconds=round(time.perf_counter() - began, 3))
    return ok
