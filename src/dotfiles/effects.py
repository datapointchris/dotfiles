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
    """Run a command. See `Output` for where its output goes and why."""
    argv = tuple(command)
    environment = {**os.environ, **(env or {})}
    directory = str(cwd) if cwd else None

    if output is Output.DATA:
        completed = subprocess.run(argv, cwd=directory, env=environment, check=False)
        return Completed(command=argv, returncode=completed.returncode, transcript='')

    if output is Output.QUIET:
        captured = subprocess.run(argv, cwd=directory, env=environment, check=False, capture_output=True, text=True)
        return Completed(
            command=argv,
            returncode=captured.returncode,
            transcript=captured.stdout + captured.stderr,
        )

    lines: list[str] = []
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

    return Completed(command=argv, returncode=process.returncode, transcript=''.join(lines))
