"""Why something is wrong, asked of the machine rather than guessed at.

A refusal used to arrive as the exception that caused it — `[Errno 26] Text file
busy: '/home/chris/.local/bin/ntfy'`. That names the subject and discards
everything needed to act on it: which process held the file, what manages that
process, and what to type next. Three commands answered all of it, and every one
of them was run by hand after the fact, twice, on two different days.

Three rules, in the order they were wanted.

**A probe never blocks.** Every one is bounded by `PROBE_TIMEOUT_SECONDS` and
goes through `effects.run`, so it lands in the event stream with its own timing
like any other call out of this process. Diagnosis runs when something has
already gone wrong, which is the worst possible moment to introduce a new way to
hang.

**A probe that cannot answer says so.** Silence is what would make a diagnosis
worse than none, because a reader cannot tell "nothing holds this file" from
"lsof is not installed" unless the second is written down. `unavailable` carries
that, and it is reported *beside* whatever was learned rather than instead of it.

**More is better here.** There are many moving parts, a run is usually read after
the fact, and the two costs are not symmetric: a cause that turns out to be
irrelevant costs one line, and a cause that was never gathered costs a session.

Nothing here raises. A diagnosis that threw would replace the failure being
explained with its own, which is the one outcome worse than saying nothing.
"""

from __future__ import annotations

import dataclasses as dc
import re
import shutil
from pathlib import Path

from dotfiles import effects
from dotfiles.coordinates import PackageManager

PROBE_TIMEOUT_SECONDS = 5.0
"""Long enough for a package database, short enough that four of them in a row
cannot turn a failed item into a hung run."""


@dc.dataclass(frozen=True, slots=True)
class Diagnosis:
    """What the machine said about a failure, and what to type next.

    `cause` is a sentence about the world — what was true that made the write
    fail. `fix` is a command for this machine, generated from what was measured
    rather than written into a string somewhere. `unavailable` is every question
    that could not be asked, which is reported rather than dropped.
    """

    cause: str = ''
    fix: str = ''
    unavailable: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.cause or self.fix or self.unavailable)

    def lines(self) -> tuple[str, ...]:
        """The diagnosis as advice rows, most actionable first."""
        rows = []
        if self.cause:
            rows.append(self.cause)
        if self.fix:
            rows.append(f'run: {self.fix}')
        rows.extend(f'could not check — {why}' for why in self.unavailable)
        return tuple(rows)


def _ask(argv: tuple[str, ...], about: str, absent_when: tuple[int, ...] = ()) -> tuple[str, str]:
    """One bounded, read-only question. Returns what it said and why it could not.

    Exactly one of the two is ever non-empty, and an empty pair means the command
    ran and had nothing to report — which is an answer, not a failure. That
    distinction is the whole point: "no process holds this file" and "there is no
    lsof here" reach a reader identically unless they are kept apart.

    `absent_when` names the exit codes that mean a clean "none", because several
    of these tools answer that with a failure code. `pacman -Qo` exits 1 for a
    file no package owns, and reporting that as an unavailable probe told a
    reader the check had broken when it had in fact succeeded and said no.
    """
    if not shutil.which(argv[0]):
        return '', f'{about}: {argv[0]} is not installed here'
    try:
        # QUIET, never DATA: DATA inherits the child's streams, so a probe's
        # answer would print itself in the middle of a check and arrive here
        # empty. It is the mode for a child whose stdout is the caller's, and a
        # probe's stdout is evidence.
        answered = effects.run(list(argv), output=effects.Output.QUIET, timeout=PROBE_TIMEOUT_SECONDS)
    except Exception as broke:  # noqa: BLE001 — a diagnosis must never replace the failure it explains
        return '', f'{about}: {argv[0]} raised {type(broke).__name__}'
    if answered.returncode == effects.TIMED_OUT:
        return '', f'{about}: {argv[0]} did not answer within {PROBE_TIMEOUT_SECONDS:g}s'
    if answered.returncode == effects.NOT_FOUND:
        return '', f'{about}: {argv[0]} could not be executed'
    if answered.returncode in absent_when:
        return '', ''
    if answered.returncode != 0:
        return '', f'{about}: {argv[0]} exited {answered.returncode}'
    return answered.stdout.strip(), ''


def process_holding(path: Path) -> tuple[str, str]:
    """The pid and name of whatever is executing `path`, if anything is.

    `lsof -t` rather than `fuser`, because it prints bare pids on stdout and
    `fuser` writes its pids to stderr with the path interleaved — parseable, but
    only by agreeing with a format nobody promised.
    """
    # lsof exits 1 when nothing has the file open, which is the common case and an
    # answer rather than a broken probe — the same convention `pacman -Qo` uses.
    pids, why = _ask(('lsof', '-t', '-w', '--', str(path)), 'what is holding it', absent_when=(1,))
    if why or not pids:
        return '', why

    first = pids.splitlines()[0].strip()
    name, name_why = _ask(('ps', '-o', 'comm=', '-p', first), 'the name of that process')
    if name_why:
        return f'pid {first}', name_why
    return f'{name} (pid {first})', ''


def unit_running(pid: str) -> tuple[str, str]:
    """The systemd unit a pid belongs to, user manager first.

    Read from the cgroup rather than asked of systemd: `/proc/<pid>/cgroup` names
    the unit for both managers without needing to know which one owns it, and it
    cannot prompt, stall on a bus, or exist on a machine that has no systemd at
    all — macOS reaches this function through exactly the same path.
    """
    cgroup = Path(f'/proc/{pid}/cgroup')
    if not cgroup.is_file():
        return '', f'the unit behind pid {pid}: no {cgroup} on this system'
    try:
        text = cgroup.read_text()
    except OSError as unreadable:
        return '', f'the unit behind pid {pid}: {type(unreadable).__name__}'
    for part in reversed(text.replace('/', ' ').split()):
        if part.endswith(('.service', '.scope')):
            return part, ''
    return '', ''


def package_owning(path: Path, manager: PackageManager) -> tuple[str, str]:
    """The package a file belongs to, asked of the manager this machine declares.

    Per manager rather than by trying each: the coordinate is already resolved, so
    guessing would only make a wrong answer possible on a machine that has two
    installed.
    """
    queries = {
        PackageManager.PACMAN: ('pacman', '-Qoq', str(path)),
        PackageManager.APT: ('dpkg', '-S', str(path)),
        PackageManager.BREW: ('brew', 'which-formula', str(path)),
    }
    # Every one of these reports 'no package owns this' as exit 1, which is an
    # answer rather than a broken probe.
    answered, why = _ask(queries[manager], f'which package owns {path}', absent_when=(1,))
    if why or not answered:
        return '', why
    first = answered.splitlines()[0].strip()
    # dpkg answers `package: /path`; the others answer the name alone.
    owner = first.split(':')[0].strip() if manager is PackageManager.APT else first
    return owner, ''


def removal_command(package: str, manager: PackageManager) -> str:
    """The command that removes a package, for this machine's manager.

    Generated rather than written down, because the advice is read on four
    platforms and a hardcoded `pacman` line is wrong on three of them.
    """
    return {
        PackageManager.PACMAN: f'sudo pacman -Rs {package}',
        PackageManager.APT: f'sudo apt-get remove {package}',
        PackageManager.BREW: f'brew uninstall {package}',
    }[manager]


QUOTED_PATH = re.compile(r"'([^']+)'|\"([^\"]+)\"")
"""The path an OSError puts in its string. `strerror: 'path'` is what
`shutil`, `open` and `os.replace` all produce, so one reader covers every
provider that writes a file."""


def _path_in(message: str) -> Path | None:
    """The first quoted absolute path in a message, which is the subject of it."""
    for found in QUOTED_PATH.finditer(message):
        candidate = found.group(1) or found.group(2)
        if candidate.startswith('/'):
            return Path(candidate)
    return None


def _busy(path: Path) -> Diagnosis:
    """ETXTBSY: the kernel refused to write a file that is being executed.

    Worth keeping even though `effects.install` made this impossible for a
    release binary, because it is the shape every other writer can still hit and
    the message alone is unreadable — `[Errno 26]` names a condition rather than
    a cause.
    """
    holder, why = process_holding(path)
    unavailable = (why,) if why else ()
    if not holder:
        return Diagnosis(cause=f'{path} was being executed, so it could not be written', unavailable=unavailable)

    pid = holder.rsplit('pid ', 1)[-1].rstrip(')')
    unit, unit_why = unit_running(pid)
    if unit_why:
        unavailable = (*unavailable, unit_why)
    if unit:
        return Diagnosis(
            cause=f'{path} is being executed by {holder}, under {unit}',
            fix=f'systemctl --user stop {unit}  # then apply again',
            unavailable=unavailable,
        )
    return Diagnosis(cause=f'{path} is being executed by {holder}', unavailable=unavailable)


def _permission(path: Path) -> Diagnosis:
    """EACCES: the path exists and this user may not write it."""
    owner, why = _ask(('stat', '-c', '%U:%G %a', str(path)), f'who owns {path}')
    if why:
        return Diagnosis(cause=f'{path} could not be written by this user', unavailable=(why,))
    return Diagnosis(cause=f'{path} is owned {owner} and this user may not write it')


def _no_space(path: Path) -> Diagnosis:
    """ENOSPC: the filesystem is full, and which one is the useful half."""
    where, why = _ask(('df', '-h', '--output=target,avail', str(path)), f'which filesystem holds {path}')
    if why:
        return Diagnosis(cause=f'the filesystem holding {path} is full', unavailable=(why,))
    tail = where.splitlines()[-1].split() if where.splitlines() else []
    if len(tail) == 2:
        return Diagnosis(cause=f'{tail[0]} is full ({tail[1]} available), so {path.name} could not be written')
    return Diagnosis(cause=f'the filesystem holding {path} is full')


WRITE_FAILURES = (
    ('Text file busy', _busy),
    ('Permission denied', _permission),
    ('No space left', _no_space),
)
"""What a message has to contain for a probe to be worth running.

Matched on the strerror text rather than on an errno number, because these
arrive as the `str()` of an exception a provider caught, and the number is not
always in it. Ordered, and the first match wins.
"""


def explain(item: str, message: str) -> str:
    """A provider's failure message, plus what the machine says about it.

    Returns the message unchanged when nothing here recognises it. That is the
    common case and it must stay cheap: no probe runs until a known failure is
    matched *and* a path was found to ask about, so an unrecognised failure costs
    one regex.

    `item` is the address, whose first segment names the provider — which is what
    makes this granular rather than one table for everything. Today every entry
    is a file-write failure and so applies to any provider that writes one; a
    provider needing its own reading adds a branch here rather than a new call
    site.
    """
    for marker, interpret in WRITE_FAILURES:
        if marker not in message:
            continue
        path = _path_in(message)
        if path is None:
            return message
        found = interpret(path)
        return '\n'.join((message, *found.lines())) if found else message
    return message
