"""The only module that touches the world outside this process.

The unpacking doors are deliberately ignorant of what they are unpacking.
`unpack` sniffs a container rather than reading a declared archive kind, so a
declaration's archive vocabulary stays a statement about what upstream publishes
and never becomes a second thing that has to be right for extraction to work.

Everything here is a chokepoint on purpose. A resource that reaches the world
some other way cannot be tested without the world.

Which is also why the debug event stream is emitted from here and nowhere else.
The questions asked after a failed install are what did it actually download and
which step was slow, and both are answered one level *below* the run record — the
record says an item took nine seconds, and only these lines say which command
behind it did. Instrumenting the walk instead would restate the record in a
second format.
"""

from __future__ import annotations

import gzip
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
import zipfile
from collections.abc import Callable
from collections.abc import Sequence
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

A credential is short, so the length cut is exactly what lets one through.
`redacted` and `yields_credential` are the gates that stop it.
"""

SECRET_SHAPES = (
    re.compile(r'\b(?:gh[pousr]|github_pat)_[A-Za-z0-9_]{16,}'),
    re.compile(r'\bxox[abposr]-[A-Za-z0-9-]{10,}'),
    re.compile(r'\b(?:sk|rk)-[A-Za-z0-9]{20,}'),
    re.compile(r'\bAKIA[0-9A-Z]{16}\b'),
    re.compile(r'\bey[JI][A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+'),
)
"""Token shapes scrubbed from anything a command said before it is recorded.

The run log is replicated between machines, so a credential written here does
not stay on the box that minted it. `gh auth token` is on the default `check`
path, so an unredacted transcript puts a live token in a file that reaches every
machine.

Shape matching rather than a list of commands that yield secrets: the argv that
prints one is not knowable from here, and `--refresh` alone reaches half a dozen
providers. A shape that stops being current leaks again, which is why
`yields_credential` also drops the answer of an argv naming a credential.

Three doors, not one. A secret reaches the record as the answer, as a failed
command's transcript, or in the argv itself — a token passed as an argument is
recorded whatever the command did with it. All three are scrubbed.
"""

CREDENTIAL_WORDS = ('token', 'secret', 'password', 'credential', 'apikey', 'api-key')
"""Argv words whose command's output is never recorded, whatever it looks like.

The shapes above cannot know a bespoke format. A command asked for a credential
by name is one whose answer has no diagnostic value worth the risk.
"""


def redacted(text: str) -> str:
    """Replace anything token-shaped, so a record can be read anywhere."""
    for shape in SECRET_SHAPES:
        text = shape.sub('[redacted]', text)
    return text


def yields_credential(argv: Sequence[str]) -> bool:
    """Whether this command was asked for a secret, so its answer is dropped."""
    return any(word in part.lower() for part in argv for word in CREDENTIAL_WORDS)


SLOW_SECONDS = 5.0
"""How long a single command may take before the run says so unasked.

Every command here is timed and written to the run's event stream at debug,
which answers the question perfectly and only for somebody who already suspected
a command was the answer. A run that stalls for five minutes and prints nothing
gives nobody that suspicion, so a command over this threshold is an `info` record
instead, which reaches the console at the default level.

Five seconds because it has to sit above the slowest *legitimate* probe and below
anything a person would call a stall. Measured across this fleet's records, the
slowest ordinary command is `aws --version` at ~0.5s — a Python interpreter start
— so five is an order of magnitude clear of normal and still names a stall long
before the five minutes that prompted it.

Deliberately not applied to `Output.STREAM`. A streaming command is an install,
minutes are its normal cost, and it is already narrating itself on screen.
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
    stdin_text: str | None = None,
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
    plugin managers need it — lazy.nvim's headless output is fifty plugins' raw git
    spew, and sending that to a file instead leaves a fresh install with nothing on
    screen for minutes.

    `timeout` is for a caller that is *asking* rather than *installing*: a probe
    that has not answered is not answering, and one that never returns takes the
    whole run with it. A version probe runs whatever binary a declaration names,
    and a GUI blocks on its event loop until a person closes a window, which on a
    scheduled check is never. Refused for STREAM, where minutes are a normal
    install rather than a hang, and where the reader loop would not observe a
    deadline anyway.

    `stdin_text` is the one way to send a child anything, and it is `QUIET` only.
    A git credential helper is the case: its request arrives on stdin as
    `protocol=https\\nhost=...\\n\\n` and there is no flag spelling of it. Supplying
    bytes is the opposite of the hazard below — the child reads a value this
    process chose and then EOF, rather than whatever terminal happened to be
    wired up — so the guarantee that closed stdin gives every other caller is
    unchanged. Refused for STREAM and DATA because neither captures the answer
    that would make writing worth it.

    **Every other child's stdin is closed, on every branch, rather than inherited.**
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
    not have — `hyprctl` on a box with no compositor. Raising would mean each of
    those call sites needs its own `shutil.which` guard, and the one that forgets
    is a crash rather than a reported failure.
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
    if stdin_text is not None and output is not Output.QUIET:
        raise ValueError('writing to a child is only worth it where its answer is captured, which is QUIET alone')

    began = time.perf_counter()

    def answered(completed: Completed) -> Completed:
        """Every command, on the way out, whichever of the five exits it took.

        The transcript only when the command failed. A successful `apt-get
        install` is thousands of lines nobody will ever read, and keeping all of
        them is how a debug stream turns into something people switch off — while
        a failed one is the entire reason the stream exists.

        The exception is a *short* successful answer, kept up to `ANSWER_LIMIT`.
        A version probe succeeds and its whole meaning is the one line it prints,
        so recording only the argv and the exit code makes a permanently stale item
        undiagnosable from the record: the probe appears to have run fine, on every
        run, and the drift can only be read by logging into the machine.
        """
        seconds = round(time.perf_counter() - began, 3)
        fields = {
            'argv': [redacted(part) for part in argv],
            'returncode': completed.returncode,
            'seconds': seconds,
            'cwd': directory,
        }
        if not completed.ok:
            fields['transcript'] = redacted(completed.transcript)
        elif not yields_credential(argv) and (answer := redacted(completed.stdout.strip())) and len(answer) <= ANSWER_LIMIT:
            fields['answer'] = answer
        log.debug('ran', **fields)

        # A second record rather than the first one promoted, so the debug stream
        # keeps one line per command whatever its duration and nothing reading it
        # has to know that slow commands are spelled differently.
        if seconds >= SLOW_SECONDS and output is not Output.STREAM:
            log.info('slow command', command=' '.join(argv), seconds=seconds)
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
                argv,
                cwd=directory,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
                **({'input': stdin_text} if stdin_text is not None else {'stdin': subprocess.DEVNULL}),
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


def fetch(url: str, destination: Path, *, repo: str = '', tag: str = '', asset_name: str = '') -> github_release.Fetched:
    """Download one file. The release-asset arguments are how a private repo works.

    Delegated rather than reimplemented: `github_release` already carries the
    asset-id fallback. One implementation, reachable from both this and the bundler.

    **Returns why it failed, and is still usable as a boolean.** Every caller here
    writes `if effects.fetch(...)` or `if not effects.fetch(...)`, and `Fetched` is
    truthy exactly when the download happened — so the reason is additive rather
    than a migration. A caller that wants it reads `.reason`; one that does not is
    unchanged.
    """
    began = time.perf_counter()
    answered = github_release.download_asset(url, destination, repo, tag, asset_name)
    log.debug(
        'fetched',
        url=url,
        destination=str(destination),
        repo=repo,
        tag=tag,
        ok=answered.ok,
        # Beside the byte count for the same reason it is: this is the stream read
        # after a failed install, and a TLS-intercepting proxy is the one cause that
        # is invisible in every other field. It went unrecorded anywhere at all
        # until now, which is how a curl certificate rejection reached a person as
        # `could not download <url>`.
        reason=answered.reason,
        seconds=round(time.perf_counter() - began, 3),
        # The literal answer to "what did it actually download", which a machine
        # behind a captive portal needs most: a fetch that reports success having
        # written a 900-byte login page looks identical to one that worked.
        bytes=destination.stat().st_size if destination.exists() else 0,
    )
    return answered


def unpack(archive: Path, into: Path) -> bool:
    """Extract a tar or zip, whichever it turns out to be.

    Sniffed rather than told, because the container is a property of the bytes and
    a caller that has to say which one is a caller that can be wrong about it.
    `tarfile` reads gzip, xz and bzip2 transparently, so the compression never
    needs naming either.

    Members are extracted under `filter='data'`, which refuses absolute paths,
    `..` traversal and device nodes. The tar these unpack came off the internet,
    and a plain `tar -xf` applies no such filter.

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
    # Neither sniffer recognized it, which is a different failure from one that
    # threw halfway through and worth being able to tell apart in the stream.
    return extracted('unrecognized', False)


def restore_mode(member: zipfile.ZipInfo, landed: str) -> None:
    """Put back the permission bits `extractall` dropped, on the file it wrote.

    **`landed` comes from the extractor, never from the member's name.** A zip
    records whatever name its author chose, and `ZipFile._extract_member` sanitizes
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


def install(source: Path, target: Path, *, executable: bool = True) -> bool:
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

    Writing through instead is a permanent failure for any long-running tool
    installed from a release: a service under `Restart=always` holds its binary
    open indefinitely, so every apply refuses with ETXTBSY and the tool stays at
    whatever version it was when the service started.
    """
    began = time.perf_counter()
    target.parent.mkdir(parents=True, exist_ok=True)
    beside = target.with_name(f'.{target.name}{NEW_SUFFIX}')
    ok = True
    try:
        shutil.copy2(source, beside)
        # A binary earns the bit; a systemd unit is read rather than run, so the
        # mode would only mislead whoever next lists the directory.
        if executable:
            beside.chmod(beside.stat().st_mode | 0o111)
        else:
            beside.chmod(beside.stat().st_mode & ~0o111)
        os.replace(beside, target)
    except OSError:
        ok = False
        beside.unlink(missing_ok=True)
    log.debug('installed', source=str(source), target=str(target), ok=ok, seconds=round(time.perf_counter() - began, 3))
    return ok
