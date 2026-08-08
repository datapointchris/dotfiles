"""The only module that touches the world outside this process.

Six doors are planned — `run`, `fetch`, `write`, `link`/`unlink`, `extract`,
`chmod` — and one exists so far, because only `run` has a caller: every leaf of
the CLI currently shells out to the bash it will eventually replace. The rest
arrive as each resource moves, and the point of the module is that a stub of it
covers every resource's I/O at once.

Everything here is a chokepoint on purpose. A resource that reaches the world
some other way cannot be tested without the world.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


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


NOT_FOUND = 127
"""A command that does not exist, as a shell reports it rather than as a crash."""


@dataclass(frozen=True)
class Completed:
    """What a subprocess did. `transcript` is empty when output was not captured."""

    command: tuple[str, ...]
    returncode: int
    transcript: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run(
    command: list[str] | tuple[str, ...],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    output: Output = Output.STREAM,
) -> Completed:
    """Run a command. See `Output` for where its output goes and why.

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
    directory = str(cwd) if cwd else None

    def missing(problem: OSError) -> Completed:
        return Completed(command=argv, returncode=NOT_FOUND, transcript=f'{argv[0]}: {problem.strerror}')

    if output is Output.DATA:
        try:
            completed = subprocess.run(argv, cwd=directory, env=environment, check=False)
        except (FileNotFoundError, PermissionError) as problem:
            return missing(problem)
        return Completed(command=argv, returncode=completed.returncode, transcript='')

    if output is Output.QUIET:
        try:
            captured = subprocess.run(argv, cwd=directory, env=environment, check=False, capture_output=True, text=True)
        except (FileNotFoundError, PermissionError) as problem:
            return missing(problem)
        return Completed(
            command=argv,
            returncode=captured.returncode,
            transcript=captured.stdout + captured.stderr,
        )

    lines: list[str] = []
    try:
        with subprocess.Popen(
            argv,
            cwd=directory,
            env=environment,
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
                    sys.stderr.write(line)
    except (FileNotFoundError, PermissionError) as problem:
        return missing(problem)

    return Completed(command=argv, returncode=process.returncode, transcript=''.join(lines))
