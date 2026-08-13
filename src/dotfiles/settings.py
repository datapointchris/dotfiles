"""This tool's own config file, and how a declared path is resolved through it.

`~/.env` is a shell file, so everything that answers from it is a shell. The
scheduled check is not one: a systemd user unit and a LaunchAgent both start
with an environment that has never sourced a profile, so `$REPOS_JSON` is unset
there and the registry entry in `install/flags.yml` resolved to the literal
string `$REPOS_JSON`. Four times a day the timer reported this machine's repo
registry missing and advised restoring it with safekeep, about a file that was
on disk the whole time. A machine's answer has to survive into a process with no
shell, and this config file is where it does.

Three rungs, highest first, per standards/data.md § "A shared file is named in
config; only the tool's own default is compiled in": a private variable only
this tool reads, the shared variable every reader of the same file consults, then
the config key. Each answers a different question — this invocation, this
machine's shells, this machine.

**There is no fourth rung, and that is deliberate.** A default naming a path
outside this tool's own XDG directories is what that standard forbids, and the
registry it would have to guess at moved twice in six hours on 2026-08-12. A
compiled-in path would have been wrong before the commit carrying it landed.

**The shared variable sits above the config key here and below it in indy**,
which is that standard's canonical source. The difference is deliberate and is
what this tool's situation asks for: indy's config key exists so one reader can
be pointed at a different registry from everyone else, whereas this file exists
only so a shell-less unit gets the same answer the shells already have. Putting
the config above the variable would let a stale config.toml silently override
the value every other reader on the machine is using.
"""

from __future__ import annotations

import dataclasses as dc
import os
import re
import tomllib
from pathlib import Path
from typing import Any

from dotfiles import paths


def config_file() -> Path:
    """Where a machine writes the answers this repo declares and never carries.

    A function rather than a constant bound at import, for the same reason
    `paths.cache_home` is one: `$XDG_CONFIG_HOME` is already the knob meaning
    "look somewhere else", and a constant cannot be redirected without patching
    this module.
    """
    return paths.xdg_home('XDG_CONFIG_HOME', '.config') / 'dotfiles' / 'config.toml'


@dc.dataclass(frozen=True, slots=True)
class Config:
    """What the config file holds, and why it could not be read when it could not.

    `problem` rather than a raised exception or an empty dict: a file a human
    hand-edited into invalid TOML must not read as a machine that named nothing,
    because the two get opposite advice. Returning it lets the check report the
    syntax error as its own finding instead of a traceback.
    """

    values: dict[str, Any]
    problem: str = ''


def read_config() -> Config:
    """Parse config.toml, tolerating its absence — a machine may answer in `~/.env` alone."""
    path = config_file()
    if not path.is_file():
        return Config({})
    try:
        return Config(tomllib.loads(path.read_text()))
    except (OSError, tomllib.TOMLDecodeError) as failure:
        return Config({}, str(failure))


@dc.dataclass(frozen=True, slots=True)
class Shared:
    """The three rungs that can name one file this tool reads but does not own."""

    private_env: str
    shared_env: str
    config_key: str


SHARED_PATHS: dict[str, Shared] = {
    'REPOS_JSON': Shared('DOTFILES_REPOS_JSON', 'REPOS_JSON', 'repos_file'),
}
"""Declared values this tool's own config can also answer, keyed by the name
`install/flags.yml` declares and every other reader of the same file consults.

`WINDOWS_USER` and `WINDOWS_DOMAIN` belong here in shape and deliberately are
not, and neither takes a `DOTFILES_` twin. A Windows account name and the domain
it authenticates against are facts about the machine rather than settings of this
tool, so a prefix would claim a name that is not ours to namespace — and the
shell code reading them would never find the prefixed spelling. What earns an
entry is a *shared file* whose location differs per machine.
"""


@dc.dataclass(frozen=True, slots=True)
class Resolution:
    """A value and the rung that supplied it."""

    value: str
    source: str
    """Named because the value alone does not explain itself. A check reporting a
    registry missing at a path nobody recognises is a different problem from one
    reporting it missing at the path the machine declared, and only the rung
    separates them — standards/data.md § "Report which layer supplied the value".
    """


def resolve(declared: str) -> Resolution | None:
    """The value for a declared name, or None when nothing names it.

    Empty counts as unset at every rung. `Path('')` is the current directory,
    which always exists, so a variable exported as nothing would otherwise
    resolve a declared file to something present while the machine had answered
    nothing at all.

    A name with no `SHARED_PATHS` entry has one rung, its own variable: the extra
    two exist to locate a file shared with other tools, and a machine fact like a
    Windows account name is neither shared nor this tool's to rename.
    """
    shared = SHARED_PATHS.get(declared)
    if shared is None:
        return Resolution(value, f'${declared}') if (value := os.environ.get(declared)) else None
    if value := os.environ.get(shared.private_env):
        return Resolution(value, f'${shared.private_env}')
    if value := os.environ.get(shared.shared_env):
        return Resolution(value, f'${shared.shared_env}')
    if value := read_config().values.get(shared.config_key):
        return Resolution(str(value), str(config_file()))
    return None


VARIABLE = re.compile(r'\$\{(\w+)\}|\$(\w+)')


def variables(text: str) -> tuple[str, ...]:
    """Every `$NAME` and `${NAME}` a declaration references, in order."""
    return tuple(match.group(1) or match.group(2) for match in VARIABLE.finditer(text))


def expand(text: str) -> str:
    """A declared path with `~` and every `$VAR` resolved through all three rungs.

    A variable nothing answers is left literal, which is what keeps the failure
    loud rather than plausible: no file is named `$REPOS_JSON`, so the check
    reports the declaration unanswered instead of resolving to a path that
    happens to exist.

    Not `os.path.expandvars`, which reads `os.environ` alone — that is precisely
    how the scheduled unit came to report a present registry as missing.
    """

    def substitute(match: re.Match[str]) -> str:
        found = resolve(match.group(1) or match.group(2))
        return found.value if found else match.group(0)

    return os.path.expanduser(VARIABLE.sub(substitute, text))


def unresolved(text: str) -> tuple[str, ...]:
    """The variables in a declaration that no rung answered."""
    return tuple(name for name in variables(text) if resolve(name) is None)


def path_source(text: str) -> str:
    """Which rungs answered a declared path, empty when it names no variable.

    Deduplicated in order rather than as a set, so a declaration referencing one
    variable twice reads as one source and the sentence stays stable.
    """
    found = [answer.source for name in variables(text) if (answer := resolve(name))]
    return ', '.join(dict.fromkeys(found))


def where_to_name(declared: str, env_file: Path) -> str:
    """Every place a machine can supply a declared value, for a change's advice.

    All three rather than the one this tool would prefer. The reader is looking
    at a check that found nothing, so the actionable fact is the whole set of
    places it looked — naming one of them turns a complete answer into a guess
    about which the machine was supposed to use.
    """
    shared = SHARED_PATHS.get(declared)
    if shared is None:
        return f'set {declared} below the OVERRIDES marker in {env_file}'
    return (
        f'set {shared.private_env} or {shared.shared_env} below the OVERRIDES marker in {env_file}, '
        f'or {shared.config_key} in {config_file()}'
    )
