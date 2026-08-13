"""This tool's own config file, and how a declared path is resolved through it.

`~/.env` is a shell file, so everything that answers from it is a shell. The
scheduled check is not one: a systemd user unit and a LaunchAgent both start
with an environment that has never sourced a profile, so a variable exported
there is unset and a declaration referencing one resolved to the literal string
`$NAME`. Four times a day the timer reported this machine's repo registry
missing and advised restoring it with safekeep, about a file that was on disk
the whole time. A machine's answer has to survive into a process with no shell,
and this config file is where it does.

Two rungs, highest first, per standards/data.md § "A shared file is named in
config; only the tool's own default is compiled in": this tool's own
`DOTFILES_`-prefixed variable, then the config key. One answers this invocation
and the other answers this machine.

**A shared unprefixed variable used to sit between them and is gone.** It was
how every reader of one file was told its location at once, and it could only
ever answer in a shell — which is the half of the fleet this file exists for.
The prefix rule is what replaced it: a tool reads no variable that is not its
own, so one fleet's vocabulary can never be compiled into a generic tool.

**There is no third rung, and that is deliberate.** A default naming a path
outside this tool's own XDG directories is what that standard forbids, and a
default *inside* them would be dotfiles claiming to own a registry that is the
fleet's data — which `CLAUDE.md` § "dotfiles does not manage fleet data" rules
out. The registry also moved twice in six hours on 2026-08-12, so a compiled-in
path would have been wrong before the commit carrying it landed.
"""

from __future__ import annotations

import dataclasses as dc
import os
import re
import tomllib
from collections.abc import Iterable
from collections.abc import Mapping
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
    """The two rungs that can name one file this tool reads but does not own.

    `env_var` carries this tool's name, always. That prefix is the invariant the
    whole resolution order rests on: a tool that reads an unprefixed variable is
    reading a name somebody else can set for a different file, and it has no way
    to tell the two apart.
    """

    env_var: str
    config_key: str


SHARED_PATHS: dict[str, Shared] = {
    'REPOS_REGISTRY': Shared('DOTFILES_REPOS_REGISTRY', 'repos_registry'),
}
"""Files this tool reads and does not own, keyed by what the file is.

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


def resolve(declared: str, config: Config) -> Resolution | None:
    """The value for a declared name, or None when nothing names it.

    Empty counts as unset at every rung, which is why each is a walrus on a
    truthiness test rather than a `in os.environ`. `Path('')` is the current
    directory and always exists, so a variable exported as nothing would resolve a
    declared file to something present while the machine had answered nothing at
    all — and every rung below the empty one would be skipped on the strength of
    it. Falling through instead means a set-but-empty variable reads exactly like
    an unset one at every layer that consumes this.

    `config` is a parameter rather than a read, so one reading of the file answers
    every name in a register. Re-reading per name let a repair land between two
    answers in one report, which is how a check came to reject the config file and
    resolve a path through it in the same breath.

    A name with no `SHARED_PATHS` entry has one rung, the variable spelled exactly
    as declared: the second exists to locate a file shared with other tools, and a
    machine fact like a Windows account name is neither shared nor this tool's to
    rename.
    """
    shared = SHARED_PATHS.get(declared)
    if shared is None:
        return Resolution(value, f'${declared}') if (value := os.environ.get(declared)) else None
    if value := os.environ.get(shared.env_var):
        return Resolution(value, f'${shared.env_var}')
    if value := config.values.get(shared.config_key):
        return Resolution(str(value), str(config_file()))
    return None


VARIABLE = re.compile(r'\$\{(\w+)\}|\$(\w+)')


def variables(text: str) -> tuple[str, ...]:
    """Every `$NAME` and `${NAME}` a declaration references, in order."""
    return tuple(match.group(1) or match.group(2) for match in VARIABLE.finditer(text))


@dc.dataclass(frozen=True, slots=True)
class Resolved:
    """Every name a register declares, answered from one reading of the rungs.

    A snapshot rather than a resolver, so the half of a run that decides what is
    wrong touches nothing: `resources/__init__.py` gives `observe` the reads and
    keeps `diff` pure, and a resolution that reaches for the config file is a read
    inside `diff` however it is spelled.
    """

    answers: Mapping[str, Resolution | None]

    def of(self, declared: str) -> Resolution | None:
        """What answered this name, or None when no rung did.

        A name the snapshot was never asked for raises rather than reading as
        unanswered. The two are opposite findings — a machine that declared
        nothing, against a caller that resolved the wrong set of names — and only
        the first should ever reach a report.
        """
        return self.answers[declared]

    def expand(self, text: str) -> str:
        """A declared path with `~` and every `$VAR` resolved through the rungs it has.

        A variable nothing answers is left literal, which is what keeps the failure
        loud rather than plausible: no file is named `$NAME`, so the check reports
        the declaration unanswered instead of resolving to a path that happens to
        exist.

        Not `os.path.expandvars`, which reads `os.environ` alone — that is precisely
        how the scheduled unit came to report a present registry as missing.
        """

        def substitute(match: re.Match[str]) -> str:
            found = self.of(match.group(1) or match.group(2))
            return found.value if found else match.group(0)

        return os.path.expanduser(VARIABLE.sub(substitute, text))

    def unresolved(self, text: str) -> tuple[str, ...]:
        """The variables in a declaration that no rung answered."""
        return tuple(name for name in variables(text) if self.of(name) is None)

    def source(self, text: str) -> str:
        """Which rungs answered a declared path, empty when it names no variable.

        Deduplicated in order rather than as a set, so a declaration referencing one
        variable twice reads as one source and the sentence stays stable.
        """
        found = [answer.source for name in variables(text) if (answer := self.of(name))]
        return ', '.join(dict.fromkeys(found))


def resolve_all(names: Iterable[str], config: Config) -> Resolved:
    """Answer every declared name against one reading of the config file."""
    return Resolved({name: resolve(name, config) for name in names})


def where_to_name(declared: str, env_file: Path) -> str:
    """Every place a machine can supply a declared value, for a change's advice.

    Every one of them rather than the one this tool would prefer. The reader is
    looking at a check that found nothing, so the actionable fact is the whole set
    of places it looked — naming one of them turns a complete answer into a guess
    about which the machine was supposed to use.
    """
    shared = SHARED_PATHS.get(declared)
    if shared is None:
        return f'set {declared} below the OVERRIDES marker in {env_file}'
    return f'set {shared.env_var} below the OVERRIDES marker in {env_file}, or {shared.config_key} in {config_file()}'


@dc.dataclass(frozen=True, slots=True)
class Setting:
    """One thing this tool's config can answer, as this machine currently answers it."""

    name: str
    value: str
    source: str
    exists: bool
    advice: str
    """Where to answer it, on a machine that has not — empty once one has.

    Carried on the record rather than assembled by whichever surface is printing,
    so the terminal and `--json` cannot come to say different things about the
    same machine. It is also the half a reader arrives for: a setting nothing
    names is a question about where to put the answer, not about the value.
    """

    @property
    def answered(self) -> bool:
        return bool(self.source)


def describe(config: Config, env_file: Path) -> tuple[Setting, ...]:
    """Every setting this tool's config can answer, with the rung that answered it.

    Built by calling `resolve`, never by re-walking the rungs beside it, so the
    attribution a reader is shown cannot drift from the value the tool will use —
    standards/configuration.md § "A resolved value reports which layer set it".

    The value is expanded, because the question this answers is what the tool will
    do rather than what someone typed: `repos_registry = "~/dev/repos.json"` is a
    perfectly ordinary thing to write in the config file, and printing it back
    unexpanded answers a question nobody asked.
    """
    described = []
    for name in SHARED_PATHS:
        found = resolve(name, config)
        value = os.path.expanduser(found.value) if found else ''
        described.append(
            Setting(
                name=name,
                value=value,
                source=found.source if found else '',
                exists=bool(value) and Path(value).exists(),
                advice='' if found else where_to_name(name, env_file),
            )
        )
    return tuple(described)
