"""Moving an artefact between the machine that has a network and the one that does not.

The transport is a program this repo never names. A machine declares which one in
`[remote.transport]` and dotfiles builds an argv from the templates beside it, so
the credential, the protocol and the retry behaviour all stay owned by the CLI
that owns them — standards/cli-design.md § "A composer shells out to the other
CLIs; it does not reimplement them".

**The whole contract is that `list` prints one name per line on stdout.** No JSON
dialect, no field mapping, no output-format key. Everything a caller needs to rank
a bundle and describe it is in the name and the sidecar beside it, so nothing here
parses the transport's own metadata. That is what keeps `[remote]` a document
rather than a program under standards/configuration.md § "Keep the config a
document, not a program": a fixed argv with one substituted placeholder carries no
conditional, no reference between keys and no evaluation order.

`root` has no compiled-in default and cannot have one — standards/data.md § "A
shared file is named in config; only the tool's own default is compiled in". A
machine that names nothing has no remote, which is an ordinary state for every box
that never exchanges a bundle.
"""

from __future__ import annotations

import dataclasses as dc
import shutil
import string
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any

from dotfiles import effects
from dotfiles import logging
from dotfiles import settings
from dotfiles.refusal import Refusal
from dotfiles.vocabulary import ExitCode

log = logging.get_logger('remote')

TABLE = 'remote'
DEFAULT_KEEP = 5


class Operation(StrEnum):
    """What a transport can be asked to do, and the key each is declared under."""

    LIST = 'list'
    UPLOAD = 'upload'
    DOWNLOAD = 'download'
    MKDIR = 'mkdir'
    DELETE = 'delete'


PLACEHOLDERS: dict[Operation, frozenset[str]] = {
    Operation.LIST: frozenset({'dir'}),
    Operation.UPLOAD: frozenset({'local', 'dir'}),
    Operation.DOWNLOAD: frozenset({'remote', 'local'}),
    Operation.MKDIR: frozenset({'dir'}),
    Operation.DELETE: frozenset({'remote'}),
}
"""Exactly which names each template must substitute, checked when the table is read.

Exact rather than "at least", because a template that names none of them is the
failure this catches: `upload = ["upload"]` parses, runs, and uploads nothing,
reporting whatever the transport says about being called with no arguments.
"""

REQUIRED = (Operation.LIST, Operation.UPLOAD, Operation.DOWNLOAD)
"""The three a remote is useless without. `mkdir` and `delete` are optional.

`mkdir` is optional because not every remote needs one to accept an upload. Where
it is absent and a directory does not exist, `push` refuses naming the directory
rather than uploading into a path the remote invented.

`delete` is optional because a machine can reasonably decline to give this tool
the ability to remove things from a server. Without it, retention is reported and
never performed, which is the safe half of the feature and the whole of it on a
machine that says nothing.
"""


class RemoteError(Refusal):
    """A remote that is unconfigured, misconfigured, or would not answer."""


@dc.dataclass(frozen=True, slots=True)
class Transport:
    """The program that moves bytes, and how to ask it to."""

    program: str
    commands: Mapping[Operation, tuple[str, ...]]

    def declares(self, operation: Operation) -> bool:
        return operation in self.commands

    def argv(self, operation: Operation, substitutions: Mapping[str, str]) -> tuple[str, ...]:
        """The full command line for one operation, placeholders filled.

        Substituted per argument rather than over a joined string, so a path
        holding a space stays one argument. Nothing here goes through a shell.

        A mapping rather than keyword arguments. One placeholder is spelled
        `remote` and every caller already holds a `Remote` under that name, so a
        keyword form type-checks while passing the wrong object.
        """
        template = self.commands[operation]
        return (self.program, *(part.format(**substitutions) for part in template))


@dc.dataclass(frozen=True, slots=True)
class Remote:
    """Where artefacts go, how they get there, and how many are kept."""

    root: str
    transport: Transport
    keep: int = DEFAULT_KEEP
    fetch_bundle_when_none_is_staged: bool = False
    publish_status_after_offline_apply: bool = False

    def directory(self, *parts: str) -> str:
        """A remote path under the configured root, always absolute from it.

        Joined here rather than with `Path`, because the remote's separator is the
        transport's business and a Windows `Path` would join with a backslash the
        remote has never heard of.
        """
        return '/'.join([self.root.rstrip('/'), *(part.strip('/') for part in parts)])


@dc.dataclass(frozen=True, slots=True)
class Configured:
    """What the config file said about a remote, and why it could not be read.

    Three states rather than two, for the same reason `settings.Config` carries a
    `problem`: a machine that declared nothing and a machine whose declaration is
    malformed get opposite advice, and collapsing them tells the second it has no
    remote when it has a broken one.
    """

    remote: Remote | None = None
    problem: str = ''

    @property
    def declared(self) -> bool:
        return self.remote is not None or bool(self.problem)


def _template(operation: Operation, value: Any) -> tuple[tuple[str, ...], str]:
    """One operation's argv, or the sentence saying why it is not usable."""
    if not isinstance(value, list) or not all(isinstance(part, str) for part in value):
        return (), f'{TABLE}.transport.{operation} must be a list of strings'
    named = {name for part in value for _, name, _, _ in _fields(part) if name}
    wanted = PLACEHOLDERS[operation]
    if named != wanted:
        listed = ', '.join(f'{{{name}}}' for name in sorted(wanted))
        return (), f'{TABLE}.transport.{operation} must substitute exactly {listed}, and substitutes {_named(named)}'
    return tuple(value), ''


def _fields(part: str) -> list[tuple[str, str | None, str | None, str | None]]:
    """Every replacement field in one argv fragment, as `str.format` sees them.

    Asked of the formatter rather than matched with a regex, so a template that
    dotfiles accepts is exactly one `argv` will not raise on — standards/python.md
    § "Ask whatever owns a fact; never work it out a second time".
    """
    return list(string.Formatter().parse(part))


def _named(names: set[str]) -> str:
    return ', '.join(f'{{{name}}}' for name in sorted(names)) if names else 'nothing'


def _transport(table: Any) -> tuple[Transport | None, tuple[str, ...]]:
    """The declared transport, or every reason it could not be built."""
    if not isinstance(table, dict):
        return None, (f'{TABLE}.transport must be a table',)
    program = table.get('program')
    problems = [] if isinstance(program, str) and program else [f'{TABLE}.transport.program must name a program']

    commands: dict[Operation, tuple[str, ...]] = {}
    for operation in Operation:
        if operation not in table:
            if operation in REQUIRED:
                problems.append(f'{TABLE}.transport.{operation} is not declared')
            continue
        argv, problem = _template(operation, table[operation])
        if problem:
            problems.append(problem)
        else:
            commands[operation] = argv

    if problems:
        return None, tuple(problems)
    return Transport(program=str(program), commands=commands), ()


def _flag(table: dict[str, Any], key: str) -> tuple[bool, str]:
    value = table.get(key, False)
    if not isinstance(value, bool):
        return False, f'{TABLE}.{key} must be true or false'
    return value, ''


def read(config: settings.Config | None = None) -> Configured:
    """What this machine declares under `[remote]`, with every fault at once.

    Every fault rather than the first, matching `catalog.load`: a hand-edited
    table with three mistakes otherwise takes three runs to fix, and each run
    reports one line that looks like the only problem.
    """
    found = config if config is not None else settings.read_config()
    if found.problem:
        return Configured(problem=found.problem)

    table = found.values.get(TABLE)
    if table is None:
        return Configured()
    if not isinstance(table, dict):
        return Configured(problem=f'{TABLE} must be a table')

    problems: list[str] = []
    root = table.get('root')
    if not isinstance(root, str) or not root:
        problems.append(f'{TABLE}.root must name a directory on the remote')

    keep = table.get('keep', DEFAULT_KEEP)
    if not isinstance(keep, int) or isinstance(keep, bool) or keep < 1:
        problems.append(f'{TABLE}.keep must be a whole number of artefacts to retain, at least 1')

    fetch, problem = _flag(table, 'fetch_bundle_when_none_is_staged')
    problems.extend([problem] if problem else [])
    publish, problem = _flag(table, 'publish_status_after_offline_apply')
    problems.extend([problem] if problem else [])

    transport, faults = _transport(table.get('transport'))
    problems.extend(faults)

    if problems or transport is None:
        return Configured(problem='\n'.join(problems))
    return Configured(
        Remote(
            root=str(root),
            transport=transport,
            keep=int(keep),
            fetch_bundle_when_none_is_staged=fetch,
            publish_status_after_offline_apply=publish,
        )
    )


UNCONFIGURED = 'nothing in config.toml declares a remote'
ADVICE = 'declare the remote and remote.transport tables; run: dotfiles config show'


def require() -> Remote:
    """The configured remote, or the refusal that says which of the two is wrong.

    A machine that declared nothing and one whose table will not parse are
    different sentences. Both are `ISSUE` rather than `USAGE`: the command was
    typed correctly and the machine could not answer it, which is not the caller's
    mistake to fix at the command line.
    """
    found = read()
    if found.problem:
        raise RemoteError(f'the {TABLE} table cannot be read\n{found.problem}', code=ExitCode.ISSUE, advice=ADVICE)
    if found.remote is None:
        raise RemoteError(UNCONFIGURED, code=ExitCode.ISSUE, advice=ADVICE)
    return found.remote


def _ran(remote: Remote, operation: Operation, output: effects.Output, substitutions: Mapping[str, str]) -> effects.Completed:
    """One transport invocation, with the substitutions as a mapping.

    A mapping for the same reason `Transport.argv` takes one: `remote` is both a
    placeholder name and this parameter's name, so a keyword form binds the config
    object to the placeholder and raises on the argument it already had.
    """
    argv = remote.transport.argv(operation, substitutions)
    log.debug('remote.invoke', operation=str(operation), program=remote.transport.program)
    return effects.run(list(argv), output=output)


def names(remote: Remote, directory: str) -> tuple[str, ...]:
    """Every entry in a remote directory, in the order the transport listed them.

    Order is preserved rather than sorted, because a caller ranking bundles sorts
    on the timestamp inside the name and a caller checking for one entry does not
    care. Sorting here would assert an ordering the transport never promised.

    A failure raises rather than answering empty. An unreachable remote and an
    empty directory are opposite findings, and a caller that reconciles by sweep
    reads the second as "everything was deleted" — standards/cli-design.md § "A
    narrowing default reads as a deletion to anything that reconciles by sweep".
    """
    ran = _ran(remote, Operation.LIST, effects.Output.QUIET, {'dir': directory})
    if not ran.ok:
        raise RemoteError(f'{remote.transport.program} could not list {directory}\n{ran.transcript.strip()}', code=ExitCode.ISSUE)
    return tuple(line.strip() for line in ran.stdout.splitlines() if line.strip())


def exists(remote: Remote, directory: str) -> bool:
    """Whether a remote directory can be listed at all, without raising on absence."""
    return _ran(remote, Operation.LIST, effects.Output.QUIET, {'dir': directory}).ok


def push(remote: Remote, local: Path, directory: str) -> str:
    """Send one file to a remote directory, and answer the path it landed at.

    The directory is listed first, which is how a missing one is discovered. That
    is a read the caller usually wants anyway — retention needs it — and it turns
    "the remote invented a path" into a fault reported before any bytes move.

    Where the listing fails and `mkdir` is declared, the directory is created and
    the push continues. Where it is not declared the push refuses, rather than
    uploading and hoping: a transport that silently roots an upload elsewhere puts
    the artefact somewhere no `list` will ever find it, which reads as a lost
    upload rather than as a misconfiguration.
    """
    if not exists(remote, directory):
        if not remote.transport.declares(Operation.MKDIR):
            raise RemoteError(
                f'{directory} is not on the remote, and no {TABLE}.transport.mkdir is declared to create it',
                code=ExitCode.ISSUE,
                advice=f'create it once by hand, or declare mkdir in {settings.config_file()}',
            )
        made = _ran(remote, Operation.MKDIR, effects.Output.QUIET, {'dir': directory})
        if not made.ok:
            raise RemoteError(f'{remote.transport.program} could not create {directory}\n{made.transcript.strip()}', code=ExitCode.ISSUE)

    ran = _ran(remote, Operation.UPLOAD, effects.Output.STREAM, {'local': str(local), 'dir': directory})
    if not ran.ok:
        raise RemoteError(f'{remote.transport.program} could not upload {local.name} to {directory}', code=ExitCode.ISSUE)
    return f'{directory.rstrip("/")}/{local.name}'


def pull(remote: Remote, path: str, local: Path) -> Path:
    """Fetch one remote file to a local path, and answer where it landed.

    The destination directory is created first because the local cache legitimately
    does not exist yet on a machine that has never fetched anything, and a
    transport that refuses to write into a missing directory would report that as a
    missing *remote* file.

    A transport that exits 0 without writing is caught here rather than downstream.
    The verification that follows is a checksum, and a checksum of a file that does
    not exist is an unhandled `FileNotFoundError` several frames away from the
    command that caused it.
    """
    local.parent.mkdir(parents=True, exist_ok=True)
    ran = _ran(remote, Operation.DOWNLOAD, effects.Output.STREAM, {'remote': path, 'local': str(local)})
    if not ran.ok:
        raise RemoteError(f'{remote.transport.program} could not download {path}', code=ExitCode.ISSUE)
    if not local.is_file():
        raise RemoteError(f'{remote.transport.program} reported success and wrote no file at {local}', code=ExitCode.ISSUE)
    return local


def remove(remote: Remote, path: str) -> None:
    """Delete one remote artefact, where the machine declared how to.

    Never reached from an upload. Retention runs from `bundle prune` alone, so
    nothing this tool does on a schedule can remove bytes from a server — see
    `superseded` for the split.
    """
    if not remote.transport.declares(Operation.DELETE):
        raise RemoteError(
            f'no {TABLE}.transport.delete is declared, so nothing here can remove {path}',
            code=ExitCode.ISSUE,
            advice=f'declare delete in {settings.config_file()}, or remove it by hand',
        )
    ran = _ran(remote, Operation.DELETE, effects.Output.QUIET, {'remote': path})
    if not ran.ok:
        raise RemoteError(f'{remote.transport.program} could not delete {path}\n{ran.transcript.strip()}', code=ExitCode.ISSUE)


def superseded(listed: tuple[str, ...], keep: int) -> tuple[str, ...]:
    """The names retention would remove, oldest first, given what is on the remote.

    Pure, and separate from `remove`, so the decision can be reported without the
    ability to act on it. That split is what lets a machine with no declared
    `delete` still say what has accumulated.

    Sorted lexicographically, which orders these names by time because every
    artefact this tool writes carries a compact UTC timestamp — the reason
    `create_bundle.bundle_name` stamps one to the second rather than to the day.
    """
    ordered = sorted(listed)
    return tuple(ordered[: max(0, len(ordered) - keep)])


@dc.dataclass(frozen=True, slots=True)
class Reach:
    """One thing measured about the remote, and whether it holds."""

    subject: str
    ok: bool
    detail: str

    required: bool = True
    """Whether a false `ok` here is a fault or a fact.

    An undeclared `mkdir` is a real answer about a working remote, not a finding.
    Reporting the two the same way would have `remote check` exit non-zero on every
    machine that never declared an operation it does not need, which is the
    "converged machine reports a problem" failure the exit codes exist to avoid.
    """

    @property
    def faulty(self) -> bool:
        return self.required and not self.ok


def measure(found: Configured) -> tuple[Reach, ...]:
    """Every condition `remote check` reports, in the order they have to hold.

    Presence of the program is measured *and* an actual listing is attempted,
    because presence is not readiness — standards/configuration.md § "A declared
    requirement states what has to be true, not only that the thing exists". A
    machine with the binary installed and no credential for it is exactly the state
    that otherwise reports converged and fails at the first upload.
    """
    if found.problem:
        return tuple(Reach('config', False, line) for line in found.problem.splitlines())
    if found.remote is None:
        return (Reach('config', False, UNCONFIGURED),)

    remote = found.remote
    program = remote.transport.program
    where = shutil.which(program)
    measured = [
        Reach('transport', bool(where), where or f'{program} is not on PATH'),
        Reach('root', True, remote.root),
    ]
    if where is None:
        return tuple(measured)

    listed = _ran(remote, Operation.LIST, effects.Output.QUIET, {'dir': remote.root})
    if listed.ok:
        entries = tuple(line for line in listed.stdout.splitlines() if line.strip())
        measured.append(Reach('reachable', True, f'{len(entries)} entry(s) under {remote.root}'))
    else:
        measured.append(Reach('reachable', False, _why(listed, program)))

    measured.append(_declares(remote, Operation.MKDIR, 'a new directory is created by hand'))
    measured.append(_declares(remote, Operation.DELETE, 'retention is reported and never performed'))
    return tuple(measured)


def _why(ran: effects.Completed, program: str) -> str:
    """The last line of a failure, which is where every CLI puts its reason."""
    spoken = ran.transcript.strip().splitlines()
    return spoken[-1] if spoken else f'{program} exited {ran.returncode}'


def _declares(remote: Remote, operation: Operation, consequence: str) -> Reach:
    """One optional operation, reported as a fact rather than as a verdict."""
    declared = remote.transport.declares(operation)
    return Reach(str(operation), declared, 'declared' if declared else f'not declared, so {consequence}', required=False)
