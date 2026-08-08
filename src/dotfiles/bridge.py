"""Where each CLI leaf reaches the bash that has not moved yet.

Every function here is scaffolding with a scheduled demolition: as each resource
gains a real `plan`/`observe`/`diff`/`act`, its entry disappears, and when the
last one goes so does this module. Keeping them in one file rather than scattering
`subprocess` calls through the command modules is what makes that demolition
legible — the remaining callers are the remaining work.

The CLI surface is deliberately already its final shape. Only what sits behind it
changes, so the control inversion happens resource by resource without the
grammar moving under anyone.
"""

from __future__ import annotations

import contextlib
import sys

from dotfiles import paths
from dotfiles.effects import Completed
from dotfiles.effects import Output
from dotfiles.effects import run

OPS_DIR = paths.INSTALL_DIR / 'ops'


def _environment() -> dict[str, str]:
    """What every one of these scripts assumes about its environment.

    `DOTFILES_DIR` because the scripts fall back to `git rev-parse --show-toplevel`,
    which resolves to whatever repo the caller happens to be standing in — and
    aborts outright outside one. `TERM` because the formatting library calls
    `tput`, which fails noisily when it is unset, as it is under a systemd timer.

    `DOTFILES_PYTHON` because those scripts still ask Python to read packages.yml
    and need an interpreter that can import this package. This process is one, by
    construction — it is running from it. `install/common/lib/python.sh` reads the
    variable; both sides go when the last script stops shelling out to ask.
    """
    return {
        'DOTFILES_DIR': str(paths.REPO_ROOT),
        'TERM': 'xterm',
        'DOTFILES_PYTHON': sys.executable,
    }


def ops(script: str, *args: str, output: Output = Output.STREAM) -> Completed:
    """Run one of `install/ops/*.sh`, the scripts both front doors already shared."""
    return run(
        ['bash', str(OPS_DIR / f'{script}.sh'), *args],
        cwd=paths.REPO_ROOT,
        env=_environment(),
        output=output,
    )


def wsl_script(name: str, *args: str) -> Completed:
    return run(
        ['bash', str(paths.INSTALL_DIR / 'wsl' / name), *args],
        cwd=paths.REPO_ROOT,
        env=_environment(),
    )


def git(*args: str, output: Output = Output.QUIET) -> Completed:
    """Run git against this repo.

    Quiet by default because most calls here are probes — `rev-parse`, `diff
    --name-only` — whose output is evidence for the next decision rather than a
    message. `pull` passes STREAM, since it talks to the network and a silent
    pause reads as a hang.
    """
    return run(['git', '-C', str(paths.REPO_ROOT), *args], output=output)


def declaration(*args: str, output: Output = Output.DATA) -> int:
    """Query the declaration, in-process, returning its exit status.

    A call rather than a subprocess because it is already part of this package.
    `install/ops/doctor.sh` reaches it as `uv run packages`, which needs a uv
    project on disk — true in the repo, false for the installed tool this CLI is
    becoming.

    `declaration.main` signals through `sys.exit`, so the SystemExit it raises is
    the return value and not an error. Converting it here rather than letting it
    propagate is what stops a `packages verify` finding from killing the whole
    `check` walk before the resources after it have run.

    Running in-process means it prints to *our* stdout, so the same stream
    discipline `effects.run` applies to a subprocess has to be applied here by
    hand. `Output.STREAM` sends its output to stderr, which is what a caller
    wants when it is answering a check rather than being the command: without it
    `dotfiles check --json` emits two progress lines above the document and every
    parse of it fails.

    Imported inside the function, against the usual rule: `import
    dotfiles.declaration` costs 78ms (29ms of it yaml, measured 2026-08-08), and
    most invocations — `--help`, `report latest`, `repo path` — never read the
    declaration at all.
    """
    from dotfiles import declaration as declaration_module

    redirect: contextlib.AbstractContextManager = (
        contextlib.redirect_stdout(sys.stderr) if output is Output.STREAM else contextlib.nullcontext()
    )
    try:
        with redirect:
            declaration_module.main(list(args))
    except SystemExit as requested:
        return int(requested.code or 0)
    return 0
