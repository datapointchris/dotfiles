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
import time
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

    PROBE = 'probe'
    LIST = 'list'
    UPLOAD = 'upload'
    DOWNLOAD = 'download'
    MKDIR = 'mkdir'
    DELETE = 'delete'


PLACEHOLDERS: dict[Operation, frozenset[str]] = {
    Operation.PROBE: frozenset(),
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

REQUIRED = (Operation.PROBE, Operation.LIST, Operation.UPLOAD, Operation.DOWNLOAD)
"""The four a remote is useless without. `mkdir` and `delete` are optional.

**`probe` is required because nothing else can answer "is it up".** Every other
operation names a path, so its failure means either "the server is unreachable"
or "that path is not there" and the exit code cannot say which. A caller that
guessed wrong would build a full bundle because a network blip hid a status that
was sitting on the server the whole time.

What a machine declares here has to succeed **whenever the transport can reach
the server, whatever is or is not stored on it** — `ifiles auth status`, not a
listing of the root. A root that does not exist yet is the ordinary state of a
fresh remote, so a probe that fails on it reports every first run as an outage.

`mkdir` is optional because not every remote needs one to accept an upload. Where
it is absent and a directory does not exist, `push` refuses naming the directory
rather than uploading into a path the remote invented.

`delete` is optional because a machine can reasonably decline to give this tool
the ability to remove things from a server. Without it, retention is reported and
never performed, which is the safe half of the feature and the whole of it on a
machine that says nothing.
"""


KEYS = frozenset({'root', 'keep_bundles', 'transport', 'fetch_bundle_when_none_is_staged', 'publish_status_after_offline_apply'})
"""Every key the `[remote]` table may hold, so anything else can be named."""


PROBE_ATTEMPTS = 3
PROBE_BACKOFF_SECONDS = 1.0
"""How hard to try before calling it an outage, and how long that costs.

Three tries about three seconds apart at most. A single dropped packet on a
corporate VPN must not be the reason a machine concludes it is offline — and the
cost of being wrong in the other direction is the whole bundle downloaded because
nothing could see the status that would have made it sparse.

Deliberately small. Past a few seconds this stops being a retry and starts being
a machine that hangs on a network that is genuinely down, which is the state the
refusal exists to report.
"""


class RemoteError(Refusal):
    """A remote that is unconfigured, misconfigured, or would not answer."""


class Unreachable(RemoteError):
    """The transport is declared and installed, and the server did not answer.

    Its own type because callers act on it differently from every other refusal.
    An absent directory means "nothing has been published yet" and a caller may
    reasonably carry on; this means "go and look at the network", and carrying on
    would spend a full download on a question nobody could ask.
    """


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
    keep_bundles: int = DEFAULT_KEEP
    keep_bundles_declared: bool = False
    """Whether the table set the limit, or this tool's default answered.

    Carried rather than inferred from the number, because a machine that declares
    the same value as the default is indistinguishable by comparison — and
    standards/configuration.md § "A resolved value reports which layer set it"
    names that exactly: *"the failure this prevents is not a wrong value, it is a
    plausible one."* The value governs deletion from a server.
    """

    fetch_bundle_when_none_is_staged: bool = False
    publish_status_after_offline_apply: bool = False

    def directory(self, *parts: str) -> str:
        """A remote path under the configured root, always absolute from it.

        Joined here rather than with `Path`, because the remote's separator is the
        transport's business and a Windows `Path` would join with a backslash the
        remote has never heard of.
        """
        return '/'.join([self.root.rstrip('/'), *(part.strip('/') for part in parts)])


BUNDLES = 'bundles'
STATUSES = 'status'
"""The two kinds of artefact under `root`, and dotfiles decides both.

A *shelf* is one machine's directory inside one of these — `<root>/bundles/<manifest>`
— which is what every `--machine` flag here reads and what `bundles_for` and
`statuses_for` build. Naming these two the same word left the term with two
referents and `remote check`, the only command that describes the remote, using
neither.


A remote's layout is this tool's to choose because both ends of the exchange are
this tool — nothing else reads these directories, and a machine that had to
describe the structure in config would be describing a fact it does not own.
What the machine supplies is the root they hang under, which is a fact about a
server.

Keyed by *manifest* under each, never by hostname. `paths.machine_id()` is the
bare hostname, and on the one machine this exists for that is an employer's asset
tag — a name that has no business on a shelf beside personal artefacts. The
manifest name is what a bundle is built for anyway, so it is also the right key.
"""


def bundles_for(remote: Remote, machine: str) -> str:
    return remote.directory(BUNDLES, machine)


def statuses_for(remote: Remote, machine: str) -> str:
    return remote.directory(STATUSES, machine)


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

    named: set[str] = set()
    for part in value:
        try:
            fields = _fields(part)
        except ValueError as malformed:
            return (), f'{TABLE}.transport.{operation} is not a usable template: {malformed}'
        # An unnamed field is `{}`, which `str.format` fills from a positional
        # argument. Nothing here has one, so accepting it means `argv` raises
        # IndexError at the moment the transport runs — a traceback where every
        # other fault in this table is collected into a sentence.
        if any(name == '' for _, name, _, _ in fields):
            return (), f'{TABLE}.transport.{operation} carries an empty {{}}, and nothing here fills a positional field'
        named |= {name for _, name, _, _ in fields if name}

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

    Raises `ValueError` on an unbalanced brace, which the caller turns into one
    more problem string. Uncaught it escapes `dotfiles config show`, and that is
    the command `ADVICE` sends the reader to when the table is wrong.
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

    named = {'program'} | {str(operation) for operation in Operation}
    problems.extend(f'{TABLE}.transport.{key} is not an operation this runs' for key in sorted(set(table) - named))

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
    # An unknown key is reported rather than ignored, because the commonest way to
    # get one is TOML's own section semantics: a key written *after*
    # `[remote.transport]` belongs to that table, so a machine that meant to turn
    # an automatic path on has it silently off and no way to tell.
    problems.extend(f'{TABLE}.{key} is not a setting this reads' for key in sorted(set(table) - KEYS))

    root = table.get('root')
    if not isinstance(root, str) or not root:
        problems.append(f'{TABLE}.root must name a directory on the remote')

    keep_bundles = table.get('keep_bundles', DEFAULT_KEEP)
    if not isinstance(keep_bundles, int) or isinstance(keep_bundles, bool) or keep_bundles < 1:
        problems.append(f'{TABLE}.keep_bundles must be at least 1')

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
            keep_bundles=int(keep_bundles),
            keep_bundles_declared='keep_bundles' in table,
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


@dc.dataclass(frozen=True, slots=True)
class Answer:
    """Whether the remote answered a probe, and what it said if it did not."""

    ok: bool
    detail: str = ''
    attempts: int = 1


def answered(remote: Remote, *, attempts: int = PROBE_ATTEMPTS, backoff: float = PROBE_BACKOFF_SECONDS) -> Answer:
    """Ask the declared probe whether the server is there, retrying a few times.

    The retry is the whole reason this is a separate act. One dropped packet is
    indistinguishable from an outage in a single call, and the two lead to
    opposite decisions — carry on with what the remote holds, or stop and go and
    look at the network.

    `attempts` and `backoff` are parameters so a test exercises the loop without
    waiting on it. Patching `time.sleep` would leave the loop itself untested,
    which is the half worth pinning.

    The last failure's own words come back with it. Nothing here parses them —
    that is the transport's business — but a person reading "could not reach the
    remote" wants to know whether the answer was a refused connection or an
    expired token, and only the transport can say.
    """
    # A binary that is not on PATH is not a network problem, and retrying it
    # three times over three seconds answers the same way each time. `which` is
    # definitive where an exit code is not, so this is the one failure worth
    # short-circuiting rather than waiting out.
    if shutil.which(remote.transport.program) is None:
        return Answer(False, f'{remote.transport.program} is not on PATH')

    spoken = ''
    for attempt in range(1, attempts + 1):
        ran = _ran(remote, Operation.PROBE, effects.Output.QUIET, {})
        if ran.ok:
            return Answer(True, attempts=attempt)
        spoken = _why(ran, remote.transport.program)
        if attempt < attempts:
            time.sleep(backoff * attempt)
    return Answer(False, spoken, attempts)


def reachable() -> Remote:
    """The configured remote, proven to answer. The first call of every verb.

    One entry point for the two questions that have to be asked in order, because
    asking them separately is how a caller comes to report an outage on a machine
    that simply never declared a remote — and how another comes to report an empty
    shelf on a machine whose network is down.

    `remote check` deliberately does not call this. Reporting these states *is*
    its job, so it reads the pieces and renders them rather than refusing on the
    first one.
    """
    where = require()
    found = answered(where)
    if not found.ok:
        raise Unreachable(
            f'{where.transport.program} could not reach the remote after {found.attempts} attempt(s)'
            + (f'\n{found.detail}' if found.detail else ''),
            code=ExitCode.ISSUE,
            advice='check the network and the transport, then run: dotfiles remote check',
        )
    return where


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


def listed(remote: Remote, directory: str) -> tuple[str, ...] | None:
    """Every entry, `None` where the directory is genuinely not there, raising otherwise.

    **Three answers, because a listing has three outcomes and a bool carries two.**
    A directory that has never been created and a transport that could not be
    reached are opposite findings, and every caller here acts differently on them:
    the first means "nothing has been published yet, build a full bundle", and the
    second means "stop, because a perfectly good status may be sitting on a server
    nobody could reach". Collapsing them turns a network fault into half an hour of
    downloads with nothing on screen saying a call failed.

    Absence is established by walking up. A transport reports one exit status for
    every kind of failure, so nothing in its answer says which this was — but an
    ancestor that lists proves the remote is reachable, which leaves the missing
    child as the only explanation. Nothing listing all the way to the root is
    unreachable, and that raises.

    The walk costs extra round trips only on the failure path. A directory that
    lists answers in one call, which is every ordinary run.
    """
    ran = _ran(remote, Operation.LIST, effects.Output.QUIET, {'dir': directory})
    if ran.ok:
        return tuple(line.strip() for line in ran.stdout.splitlines() if line.strip())
    if _reachable_above(remote, directory):
        return None
    raise RemoteError(f'{remote.transport.program} could not list {directory}\n{ran.transcript.strip()}', code=ExitCode.ISSUE)


def _reachable_above(remote: Remote, directory: str) -> bool:
    """Whether any ancestor of a directory lists, which is what proves it is merely absent."""
    root = remote.root.rstrip('/')
    walking = directory.rstrip('/')
    while walking != root and '/' in walking.removeprefix(root):
        walking = walking.rsplit('/', 1)[0]
        if _ran(remote, Operation.LIST, effects.Output.QUIET, {'dir': walking}).ok:
            return True
    return False


def exists(remote: Remote, directory: str) -> bool:
    """Whether a remote directory is there, for a caller that will create it if not.

    `push` alone, and only because its recovery is `mkdir` — which raises on its
    own when the remote is unreachable, so the distinction `listed` draws is one
    that path does not have to draw for itself. Every caller that *reads* a shelf
    goes through `listed`, where guessing costs a wrong bundle.
    """
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
        Reach('configured', True, remote.root),
    ]
    if where is None:
        return tuple(measured)

    # The probe first, and the root listing only if it answered. They report
    # different things: the probe says whether the server is there at all, and the
    # listing says whether anything has been put on it. A root that does not exist
    # is the ordinary state of a fresh remote and not a fault, which is precisely
    # what a single combined row could never say.
    answer = answered(remote)
    tried = f' after {answer.attempts} attempts' if answer.attempts > 1 else ''
    measured.append(Reach('reachable', answer.ok, f'the server answered{tried}' if answer.ok else f'{answer.detail}{tried}'))
    if not answer.ok:
        return tuple(measured)

    listed = _ran(remote, Operation.LIST, effects.Output.QUIET, {'dir': remote.root})
    if listed.ok:
        entries = tuple(line for line in listed.stdout.splitlines() if line.strip())
        measured.append(Reach('root', True, f'{len(entries)} entry(s) under {remote.root}', required=False))
    else:
        measured.append(Reach('root', False, f'{remote.root} is not there yet; the first upload creates it', required=False))

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
