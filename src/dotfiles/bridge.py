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

RESOURCE_PHASES: dict[str, tuple[str, ...]] = {
    'packages': (
        'system-packages',
        'go-tools',
        'github-releases',
        'custom-installers',
        'cargo',
        'npm-globals',
        'uv-tools',
    ),
    'toolchains': ('go-toolchain', 'rust-toolchain', 'uv', 'node-toolchain'),
    'plugins': ('shell-plugins', 'tmux-plugins', 'nvim-plugins'),
    'symlinks': ('symlinks',),
    'system': ('zsh-config',),
}
"""Which `install/phases.sh` phases each resource owns.

Hand-written here and machine-checked in `tests/cli/test_bridge_phases.py`, which
sources `phases.sh` and asserts every registered phase is claimed by exactly one
resource. Without that assertion this is a literal that drifts silently: a phase
added to the registry would simply stop being reachable through the resource that
should own it, and nothing would say so.

Step 4 deletes both sides of that check by making the registry itself Python.
"""


def phases_for(skip: frozenset[str] = frozenset()) -> list[str]:
    """Which install phases a run covers, in registry order.

    Pure, and separate from the command that runs them, so "what would apply do"
    is answerable without doing it. Registry order matters and is not incidental:
    symlinks must land after the tools providing `task` and before tpm reads the
    tmux config it deploys, so this preserves `RESOURCE_PHASES`' ordering rather
    than sorting or de-duplicating into a set.
    """
    return [phase for resource, resource_phases in RESOURCE_PHASES.items() if resource not in skip for phase in resource_phases]


def _environment() -> dict[str, str]:
    """What every one of these scripts assumes about its environment.

    `DOTFILES_DIR` because the scripts fall back to `git rev-parse --show-toplevel`,
    which resolves to whatever repo the caller happens to be standing in — and
    aborts outright outside one. `TERM` because the formatting library calls
    `tput`, which fails noisily when it is unset, as it is under a systemd timer.
    """
    return {'DOTFILES_DIR': str(paths.REPO_ROOT), 'TERM': 'xterm'}


def ops(script: str, *args: str, output: Output = Output.STREAM) -> Completed:
    """Run one of `install/ops/*.sh`, the scripts both front doors already shared."""
    return run(
        ['bash', str(OPS_DIR / f'{script}.sh'), *args],
        cwd=paths.REPO_ROOT,
        env=_environment(),
        output=output,
    )


def repo_script(name: str, *args: str) -> Completed:
    """Run a top-level script — `install.sh` or `update.sh`."""
    return run(['bash', str(paths.REPO_ROOT / name), *args], cwd=paths.REPO_ROOT, env=_environment())


def install_script(*args: str) -> Completed:
    return repo_script('install.sh', *args)


def update_script(*args: str) -> Completed:
    return repo_script('update.sh', *args)


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


def catalog(*args: str, output: Output = Output.DATA) -> int:
    """Query the packages catalog, in-process, returning its exit status.

    A call rather than a subprocess because the catalog is already part of this
    package. `install/ops/doctor.sh` reaches it as `uv run packages`, which needs
    a uv project on disk — true in the repo, false for the installed tool this
    CLI is becoming.

    `catalog.main` signals through `sys.exit`, so the SystemExit it raises is the
    return value and not an error. Converting it here rather than letting it
    propagate is what stops a `packages verify` finding from killing the whole
    `check` walk before the resources after it have run.

    Running in-process means the catalog prints to *our* stdout, so the same
    stream discipline `effects.run` applies to a subprocess has to be applied
    here by hand. `Output.STREAM` sends its output to stderr, which is what a
    caller wants when the catalog is answering a check rather than being the
    command: without it `dotfiles check --json` emits two progress lines above
    the document and every parse of it fails.

    Imported inside the function, against the usual rule: `import dotfiles.catalog`
    costs 78ms (29ms of it yaml, measured 2026-08-08), and most invocations —
    `--help`, `report latest`, `repo path` — never reach the catalog at all.
    """
    from dotfiles import catalog as catalog_module

    redirect: contextlib.AbstractContextManager = (
        contextlib.redirect_stdout(sys.stderr) if output is Output.STREAM else contextlib.nullcontext()
    )
    try:
        with redirect:
            catalog_module.main(list(args))
    except SystemExit as requested:
        return int(requested.code or 0)
    return 0
