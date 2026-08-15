"""Staging and running a vendor's own install script.

Twelve things converge this way — nine custom installers and two of the four
language runtimes — because the vendor publishes a shell script at an
unversioned URL and running it is the supported path. Two implementations of that
would be two answers to the question the offline bundle exists to settle: which
script a machine restoring from a bundle runs.

Unversioned is the whole difficulty. The URL names no release, so "the script"
is whatever the vendor is serving at the moment it is asked — which is why a
staged copy wins even on a machine with a working network.
"""

from __future__ import annotations

import dataclasses as dc
import shutil
import tempfile
from collections.abc import Mapping
from collections.abc import Sequence
from pathlib import Path

from dotfiles import effects
from dotfiles import paths
from dotfiles.effects import Output
from dotfiles.output import err_console
from dotfiles.providers import Kind
from dotfiles.providers import Result
from dotfiles.providers import bundle_file

BUNDLE_SCRIPTS = 'scripts'


@dc.dataclass(frozen=True, slots=True)
class Script:
    """A vendor install script on disk, or why it is not.

    Truthy when there is one to run, for the reason `github_release.Fetched` is: a
    caller branching on truthiness carries the reason as a field rather than having
    to unpack a `Path | None`.
    """

    path: Path | None
    reason: str = ''

    def __bool__(self) -> bool:
        return self.path is not None


def staged(name: str, url: str, into: Path, *, offline: bool) -> Script:
    """The vendor's install script on disk, from the bundle or the network.

    The bundle is preferred whenever it holds one, not only when offline: the
    script is served from an unversioned URL, so a machine restoring from a bundle
    must run the script that bundle was built against rather than whatever the
    vendor is serving today.

    **The reason is returned, because this was the one failure with no cause anywhere
    at all.** A script that fails to *run* streams its own error to the terminal and
    its transcript to the debug log; a script that fails to *download* produced
    `could not download the rustup install script from https://sh.rustup.rs` and
    nothing else, on screen, in the record and in the stream alike. That is the whole
    of what a TLS-intercepted machine was ever told about the certificate that stopped
    it.
    """
    script = into / 'install.sh'
    cached = bundle_file(f'{BUNDLE_SCRIPTS}/{name}-install.sh')
    if cached.is_file():
        shutil.copy2(cached, script)
        return Script(script)
    if offline:
        return Script(None)

    arrived = effects.fetch(url, script)
    return Script(script if arrived else None, arrived.reason)


def unstaged(name: str, url: str, *, offline: bool, reason: str = '') -> str:
    if offline:
        return f'{name} installs from {url}, which no bundle staged at {paths.STAGING_DIR} carries it'
    return f'could not download the {name} install script from {url}{f": {reason}" if reason else ""}'


def run(
    name: str,
    url: str,
    *,
    offline: bool,
    args: Sequence[str] = (),
    env: Mapping[str, str] | None = None,
) -> Result:
    """Fetch and run one vendor install script.

    An empty detail on success: the script's own output was streamed as it ran,
    and it knows what it did in a way nothing here can restate. Summarising it
    anyway is how the bash came to print `theme updated` over the top of
    `font already at latest` — a line that reads as a verdict and contradicts the
    one above it.
    """
    with tempfile.TemporaryDirectory(prefix=f'dotfiles-{name}-') as scratch:
        err_console.print(f'{name}: {url}', soft_wrap=True)
        script = staged(name, url, Path(scratch), offline=offline)
        if not script:
            # Offline is a refusal and a failed download is not, which is the whole
            # difference between the two sentences `unstaged` writes: nothing stages
            # rustup, so an offline run reaching here is the design working, while a
            # network that would not serve the script is the world saying no.
            return Result(
                False,
                unstaged(name, url, offline=offline, reason=script.reason),
                kind=Kind.NOT_IN_BUNDLE if offline else Kind.DOWNLOAD_FAILED,
                refused=offline,
            )
        completed = effects.run(['bash', str(script.path), *args], env=dict(env) if env else None, output=Output.STREAM)

    if completed.ok:
        return Result(True, '', kind=Kind.APPLIED)
    return Result(False, failure(name, completed), kind=Kind.COMMAND_FAILED)


def failure(name: str, completed: effects.Completed) -> str:
    """What a failed vendor script said, or its exit status where it said nothing.

    The transcript, because the exit status alone is unreadable and the cause is
    already in hand. A number-only sentence leaves a TLS-intercepted machine reading
    `the install script exited 60` — where 60 is curl's code for a certificate it
    would not verify, and the script printed the reason a screen earlier.

    Scrolling is the argument, not availability: the text does reach stderr while the
    script runs, and a multi-minute apply has carried it off the screen long before
    the failure line is read. It reaches neither `--json` nor `dotfiles report`, both
    of which show this message and only this message.

    The last lines rather than the first. A vendor installer prints its banner,
    progress and environment checks before it fails, so the head of a transcript is
    reliably the part that has nothing to do with the failure.
    """
    said = [line for line in completed.transcript.splitlines() if line.strip()]
    if not said:
        return f'the {name} install script exited {completed.returncode}'
    tail = '\n'.join(said[-TRANSCRIPT_LINES:])
    return f'the {name} install script exited {completed.returncode}\n{tail}'


TRANSCRIPT_LINES = 3
"""How much of a failed script's output rides on the failure message.

Three, because `Outcome.from_result` renders every line after the first as its own
indented advice row, so this is a budget in screen rows on a report that may carry
several failures. Enough for a curl error plus the line that provoked it, and short
of a stack of shell traces. The whole transcript is in the run's debug stream for
anyone who needs the rest."""
