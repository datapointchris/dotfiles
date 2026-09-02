"""Reading the debug stream a run emits, while it runs or long afterwards.

Separate from `report` because the two artefacts are separate. A record is
*composed* — `sinks.record` walks the events and builds a typed `RunRecord` with
a schema and a versioned reader — and what it composes is what survives being
uploaded off the machine. A stream is *emitted* — whatever any module logged, at
debug, in whatever shape that module chose — and it stays behind saying what the
command actually printed. `docs/architecture/observability.md` places both among
the artefacts a run leaves.

`show` rather than `read`, because one word does one job:
`read` earns its place only where something is left over for `show` to say, and
everything knowable *about* a run's stream is already on the record beside it.
Nothing installed spells this `read` either — `docker logs`, `kubectl logs`,
`gh run view --log`.

**`--follow` switches files when a new run opens one.** That is the whole reason
this is a command rather than an alias for `tail -F`. A run's stream is named for
the moment it started, so following one file ends at the next invocation — and a
stable symlink cannot stand in, because `tail -F` pins to the target's inode and
does not notice a repoint. Owning the switch here costs nothing and needs no
second copy of every byte.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import typer
from rich.text import Text

from dotfiles import paths
from dotfiles import runs
from dotfiles.effects import SLOW_SECONDS
from dotfiles.output import console
from dotfiles.output import emit_json
from dotfiles.output import error
from dotfiles.vocabulary import ExitCode

app = typer.Typer(no_args_is_help=True, help='The debug stream a run emitted, live or afterwards')

IdentifierArgument = typer.Argument(None, help='Run id or filename prefix (default: the newest run on this machine)')
FollowOption = typer.Option(False, '--follow', '-f', help='Stream new lines, switching to the next run when one starts')
LimitOption = typer.Option(None, '--limit', '-n', help='Show only the last N lines')
JsonOption = typer.Option(False, '--json', help='Emit the stream unchanged, one JSON object per line')

POLL_SECONDS = 0.25
"""How often a follower looks for new lines and for a newer run.

Fast enough that a pane feels live next to the terminal it is narrating, slow
enough to cost nothing while idle. Polling rather than inotify because the only
alternative is a dependency, and the directory holds a handful of files.
"""

RENDERED_ELSEWHERE = frozenset(
    {'timestamp', 'level', 'logger', 'event', 'run_id', 'machine', 'resource', 'item', 'seconds', 'returncode', 'ok'}
)
"""Fields the row gives their own column or trailer, so the detail does not repeat them.

The timing three are here for that reason and not because they are structural:
`measured` carries `seconds` as an ordinary field and rendered it twice, once in
the `key=value` fallback and once in the trailer that formats it."""


def _resolve(identifier: str | None) -> Path:
    """One run's stream, by id or filename prefix, or the newest on this box.

    Both spellings, because the two identifiers a reader has in front of them
    come from different places: `report` prints the run id, and the directory
    listing shows the stem. Matching the stem first costs no file reads at all,
    which is why the id pass is second.
    """
    if identifier is None:
        if found := runs.latest_event_log():
            return found
        error('no runs have been recorded on this machine yet')
        raise typer.Exit(ExitCode.ISSUE)

    available = runs.list_event_logs()
    matches = [path for path in available if path.stem.startswith(identifier)]
    if not matches:
        matches = [path for path in available if _run_id(path).startswith(identifier)]
    if not matches:
        raise typer.BadParameter(f'no run stream matching {identifier!r}')
    if len(matches) > 1:
        raise typer.BadParameter(f'{identifier!r} matches {len(matches)} runs; give more of the id')
    return matches[0]


def _run_id(path: Path) -> str:
    """The run a stream belongs to, off its first line, or '' where it has none.

    Every line carries `run_id` — `sinks.open_log` binds it before anything can
    log — so the first one answers without reading the file. An empty stream is a
    run that opened its log and then refused, which is a real state and not an
    error to raise here.
    """
    try:
        with path.open() as stream:
            first = stream.readline()
    except OSError:
        return ''
    try:
        return str(json.loads(first).get('run_id', ''))
    except ValueError:
        return ''


def _clock(entry: dict) -> str:
    """The wall time alone. A pane is read beside a running command, so the date
    is the one field every row would spend width on and no reader would use."""
    stamp = str(entry.get('timestamp', ''))
    _, _, clock = stamp.partition('T')
    return clock.rstrip('Z')[:12] or stamp


def _detail(entry: dict) -> str:
    """What this event is about, in the words the emitter used.

    `argv` is spelled as the command line it was, because it is 93% of a real
    run's lines and a bracketed list of quoted words is not what anyone is
    scanning for. Everything else falls through to `key=value`, which is what
    makes an event name nobody has written yet render as something rather than
    as nothing.
    """
    if argv := entry.get('argv'):
        return ' '.join(str(word) for word in argv)
    return ' '.join(f'{key}={value}' for key, value in entry.items() if key not in RENDERED_ELSEWHERE and value not in (None, ''))


def _failed(entry: dict) -> bool:
    return bool(entry.get('returncode')) or entry.get('ok') is False


def _row(entry: dict) -> Text:
    """One event as a line, built as styled spans rather than markup.

    `Text.append` and never a marked-up string: this renders arbitrary command
    lines and file paths, and Rich reads `[...]` in them as a style tag. That is
    the defect `report._render` carries a comment about, reached here on every
    row that names a version or an array.
    """
    line = Text()
    line.append(f'{_clock(entry):<12} ', style='blue')
    line.append(f'{str(entry.get("resource") or entry.get("logger", "")):<11} ', style='cyan')

    event = str(entry.get('event', ''))
    line.append(f'{event:<10} ', style='red' if _failed(entry) else 'bold')

    if item := entry.get('item'):
        line.append(f'{item} ', style='magenta')
    line.append(_detail(entry))

    if (seconds := entry.get('seconds')) is not None:
        elapsed = float(seconds)
        line.append(f'  {elapsed:.3f}s', style='yellow' if elapsed >= SLOW_SECONDS else 'green')
    if code := entry.get('returncode'):
        line.append(f'  exit {code}', style='red')
    return line


def _emit(line: str, as_json: bool) -> None:
    """One raw line, rendered or passed straight through.

    A line that will not parse is printed as it stands rather than skipped. The
    stream is written by a live process and the last line of a run in progress is
    routinely half-written, which is a thing worth seeing rather than a thing to
    hide.
    """
    stripped = line.rstrip('\n')
    if not stripped:
        return
    if as_json:
        # `print`, and never `output.emit_text`, which writes with `end=''` because
        # its job is a file's bytes. Here the newline *is* the format — JSON Lines
        # is what `jq` and `lnav` consume — and without one the whole stream
        # arrives as a single unparseable line.
        print(stripped)
        return
    try:
        entry = json.loads(stripped)
    except ValueError:
        console.print(Text(stripped))
        return
    console.print(_row(entry))


@app.command('show')
def show(
    identifier: str = IdentifierArgument,
    follow: bool = FollowOption,
    limit: int = LimitOption,
    as_json: bool = JsonOption,
) -> None:
    """Print one run's debug stream.

    With no argument this is the newest run on *this* machine, which is not the
    newest file in the directory: `runs/` is shared over Syncthing, so another
    box's check arriving mid-run would otherwise be the answer.

    `--follow` keeps the pane live across runs. Start it once beside the terminal
    you are working in, and it moves to each new run's stream as that run opens
    it — including the first one, when it is started on a machine that has never
    recorded anything.

    `--json` emits the stream unchanged for `lnav`, `jq` or anything else that
    reads JSON lines.
    """
    if follow:
        _follow(None if identifier is None else _resolve(identifier), as_json)
        return

    path = _resolve(identifier)
    lines = path.read_text(errors='replace').splitlines()
    for line in lines[-limit:] if limit else lines:
        _emit(line, as_json)


def _follow(start: Path | None, as_json: bool) -> None:
    """Stream lines until interrupted, moving on when a newer run opens a log.

    A missing `start` means wait for one, so the pane can be opened on a machine
    that has not run anything yet and still be correct when it does.

    Ctrl-C is the way out and is not a failure: this exits 0, because a follower
    was asked to run until stopped and stopping it is the caller doing that.
    """
    try:
        _stream(start, as_json)
    except KeyboardInterrupt:
        console.print()


def _stream(start: Path | None, as_json: bool) -> None:
    current = start
    handle = None
    try:
        while True:
            if current is None:
                current = runs.latest_event_log()
                if current is None:
                    time.sleep(POLL_SECONDS)
                    continue
            if handle is None:
                handle = current.open(errors='replace')
                _announce(current, as_json)

            if line := handle.readline():
                _emit(line, as_json)
                continue

            time.sleep(POLL_SECONDS)
            if (newer := _newer_than(current)) is not None:
                handle.close()
                handle = None
                current = newer
    finally:
        if handle is not None:
            handle.close()


def _newer_than(current: Path) -> Path | None:
    """The next run's stream, once one exists.

    Compared by name rather than by mtime: `Identity.stem` leads with a
    basic-format UTC timestamp precisely so the directory sorts chronologically
    as text, and an mtime comparison would instead follow whichever file
    Syncthing wrote last.
    """
    newest = runs.latest_event_log()
    return newest if newest is not None and newest.name > current.name else None


def _announce(path: Path, as_json: bool) -> None:
    """Name the run a follower has just moved to.

    Skipped under `--json`, where the contract is one parseable object per line
    and a separator is exactly the thing that breaks a downstream reader.
    """
    if as_json:
        return
    console.rule(Text(path.stem), style='blue')


@app.command('list')
def list_logs(limit: int = LimitOption, as_json: bool = JsonOption) -> None:
    """The runs on this machine that have a stream, newest first.

    Only this machine's, for the reason `show` gives. The whole fleet's records
    are `dotfiles report list`, which is a different question about a different
    artefact.
    """
    found = runs.list_event_logs(machine=paths.MACHINE_ID, limit=limit)
    if not found:
        error('no runs have been recorded on this machine yet')
        raise typer.Exit(ExitCode.ISSUE)

    if as_json:
        emit_json([{'stem': path.stem, 'run_id': _run_id(path), 'bytes': path.stat().st_size, 'path': str(path)} for path in found])
        return

    for path in found:
        row = Text()
        row.append(f'{_run_id(path) or "-":<14}', style='bold')
        row.append(f'{path.stem}  ', style='cyan')
        row.append(f'{path.stat().st_size / 1024:.0f}K')
        console.print(row)


@app.command('path')
def path(identifier: str = IdentifierArgument) -> None:
    """Print where one run's stream is, and nothing else.

    The same job `report path` does for the record, and for the same reason: a
    bare path on stdout is what gets substituted into another command, as in
    `lnav "$(dotfiles logs path)"`.
    """
    print(_resolve(identifier))
