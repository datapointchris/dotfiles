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


def git(*args: str, output: Output = Output.QUIET) -> Completed:
    """Run git against this repo.

    Quiet by default because most calls here are probes — `rev-parse`, `diff
    --name-only` — whose output is evidence for the next decision rather than a
    message. `pull` passes STREAM, since it talks to the network and a silent
    pause reads as a hang.
    """
    return run(['git', '-C', str(paths.REPO_ROOT), *args], output=output)


def declaration(*args: str, output: Output = Output.DATA) -> None:
    """Query the declaration, in-process, letting its refusals travel.

    A call rather than a subprocess because it is already part of this package.
    A subprocess would have to reach it as `uv run packages`, which needs a uv
    project on disk — true in the repo, false for the installed tool this CLI is
    becoming.

    It raises a `Refusal`, which carries whether it is a typo or a broken
    declaration and travels to the boundary untouched. Handing argparse's status
    to `typer.Exit` instead lands on 1, which is this tool's `DRIFT`, so a
    misspelt package name would report the machine as having changes pending.

    Only browsing is left behind this — `list`, `show`, `search`. Validation was
    the caller that made the SystemExit conversion load-bearing, because a finding
    must not kill a walk part-way through; it is a function returning findings
    now, in `validate.py`, and reaches nothing through here.

    Running in-process means it prints to *our* stdout, so the same stream
    discipline `effects.run` applies to a subprocess has to be applied here by
    hand. `Output.STREAM` sends its output to stderr, which is what a caller
    wants when it is answering a check rather than being the command: without it
    `dotfiles check --json` emits two progress lines above the document and every
    parse of it fails.

    Imported inside the function, against the usual rule: `import
    dotfiles.declaration` costs around 78ms, 29ms of it yaml, and
    most invocations — `--help`, `report latest`, `repo path` — never read the
    declaration at all.
    """
    from dotfiles import declaration as declaration_module

    redirect: contextlib.AbstractContextManager = (
        contextlib.redirect_stdout(sys.stderr) if output is Output.STREAM else contextlib.nullcontext()
    )
    with redirect:
        declaration_module.main(list(args))
