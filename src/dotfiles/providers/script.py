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

import shutil
import tempfile
from collections.abc import Mapping
from collections.abc import Sequence
from pathlib import Path

from dotfiles import effects
from dotfiles import paths
from dotfiles.effects import Output
from dotfiles.output import err_console
from dotfiles.providers import Result
from dotfiles.providers import bundle_file

BUNDLE_SCRIPTS = 'scripts'


def staged(name: str, url: str, into: Path, *, offline: bool) -> Path | None:
    """The vendor's install script on disk, from the bundle or the network.

    The bundle is preferred whenever it holds one, not only when offline: the
    script is served from an unversioned URL, so a machine restoring from a bundle
    must run the script that bundle was built against rather than whatever the
    vendor is serving today.
    """
    script = into / 'install.sh'
    cached = bundle_file(BUNDLE_SCRIPTS) / f'{name}-install.sh'
    if cached.is_file():
        shutil.copy2(cached, script)
        return script
    if offline:
        return None
    return script if effects.fetch(url, script) else None


def unstaged(name: str, url: str, *, offline: bool) -> str:
    if offline:
        return f'{name} installs from {url}, which the offline bundle at {paths.BUNDLE_DIR} does not stage'
    return f'could not download the {name} install script from {url}'


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
        if script is None:
            # Offline is a refusal and a failed download is not, which is the whole
            # difference between the two sentences `unstaged` writes: nothing stages
            # rustup, so an offline run reaching here is the design working, while a
            # network that would not serve the script is the world saying no.
            return Result(False, unstaged(name, url, offline=offline), refused=offline)
        completed = effects.run(['bash', str(script), *args], env=dict(env) if env else None, output=Output.STREAM)

    if completed.ok:
        return Result(True, '')
    return Result(False, f'the {name} install script exited {completed.returncode}')
