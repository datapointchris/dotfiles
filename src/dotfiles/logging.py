"""Logging configuration: a console for people, a JSON stream for machines.

Two sinks, deliberately at different levels. Everything is emitted at debug and
the full stream goes to the run's `.jsonl`, because the questions asked after a
failed install ("what did it actually download", "which step was slow") are only
answerable if the detail was recorded while nobody wanted it. The terminal shows
what is useful at the time, which today's output already gets right and is the
bar to hold rather than to change for its own sake.

`LOG_FORMAT=json` sends the console sink to JSON too, for a caller parsing
stderr. `LOG_LEVEL` moves the console threshold, and `-v`/`-vv`/`-q` on a
reconcile verb beat it. The file sink stays at debug whatever any of them says,
since a record that respected them would be missing exactly the detail it exists
to keep.

**All three are read when they are used, never at import.** As module constants
they were fixed by whatever the environment held when `dotfiles.logging` was
first imported, which is before `main` has parsed anything — so nothing could
override them afterwards and no test could set one without reloading the module.
That is why the three documented knobs had no test between them.
"""

import logging
import os
import sys
from pathlib import Path

import structlog

DEFAULT_LEVEL = 'INFO'
DEFAULT_FORMAT = 'console'
DEFAULT_COLORS = 'auto'


def console_level() -> str:
    return os.environ.get('LOG_LEVEL', DEFAULT_LEVEL).upper()


def console_format() -> str:
    return os.environ.get('LOG_FORMAT', DEFAULT_FORMAT)


def color_choice() -> str:
    return os.environ.get('LOG_COLORS', DEFAULT_COLORS)


QUIET_LEVEL = 'WARNING'
VERBOSE_LEVEL = 'DEBUG'

_CONSOLE_CHOICE: tuple[str, bool] | None = None
"""What the flags asked for, as (level, http_noise), or None to leave LOG_LEVEL
in charge. Module state rather than an argument threaded through `sinks.open_log`
and `reconcile.apply_machine`: `configure` runs twice in a recording verb — once
from the root callback before a verb is known, once when the run opens its event
log — and the second call must not undo what the first resolved. Threading it
would also put a presentation argument on two functions that have no other reason
to know a flag exists."""


def choose_console(verbose: int = 0, quiet: bool = False) -> None:
    """Record what `-v`/`-q` asked for, so every later `configure` honours it.

    `-q` is WARNING rather than silence, because a run that printed nothing at
    all would hide the one thing the scheduled check exists to surface.

    The second `-v` un-silences the HTTP client rather than moving the level
    again: DEBUG is already the bottom, and the only detail still withheld there
    is the per-request line `_quiet_the_http_client` pins to WARNING.

    Called with neither flag it clears the choice, so the default restores
    `LOG_LEVEL` instead of leaving a previous verb's answer in place.
    """
    global _CONSOLE_CHOICE
    if quiet:
        _CONSOLE_CHOICE = (QUIET_LEVEL, False)
    elif verbose:
        _CONSOLE_CHOICE = (VERBOSE_LEVEL, verbose >= 2)
    else:
        _CONSOLE_CHOICE = None


def resolved_console() -> tuple[str, bool]:
    """The console level and whether the HTTP client may speak. Flag beats env."""
    if _CONSOLE_CHOICE is not None:
        return _CONSOLE_CHOICE
    return console_level(), False


EVENT_LOG_HANDLER_NAME = 'dotfiles_event_log'

SHARED_PROCESSORS: list[structlog.typing.Processor] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_logger_name,
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt='iso', utc=True),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
]
"""Applied to this package's own events and, through `foreign_pre_chain`, to
records from libraries too.

`add_logger_name` is what makes a stream answerable about itself. Without it
every event was anonymous, so the only way to find out which library was filling
a 265KB apply log was to recognise the text — and nobody did, for as long as the
log existed. A stream that cannot say who wrote a line cannot be filtered by
anyone reading it either."""


def use_colors() -> bool:
    """LOG_COLORS forces the answer; otherwise ask the terminal.

    Forcing matters in a container, where TTY detection says no and the operator
    reading the output says otherwise.
    """
    choice = color_choice()
    if choice in {'true', 'false'}:
        return choice == 'true'
    return sys.stderr.isatty()


def console_processor():
    if console_format() == 'json':
        return structlog.processors.JSONRenderer()
    return structlog.dev.ConsoleRenderer(colors=use_colors(), pad_level=True)


HTTP_LOGGERS = ('httpx2', 'httpcore2', 'httpx', 'httpcore')
"""Third-party loggers that narrate every request.

Named rather than solved by lowering the root level: root is DEBUG on purpose, so
the event log gets everything while the console filters. That means any library
logging at INFO reaches the console by default, and httpx2 writes one
`HTTP Request: GET https://api.github.com/... "200 OK"` per call — which on a
release refresh is a line per declared tool, between the rows a person is
actually reading.

**`httpcore2` is the one that was missing, and it was the expensive one.** The
fork vendors its transport under that name, not `httpcore`, so it was never
pinned. Its DEBUG records carry whole response-header tuples as the event text
and they went straight into the file sink. Unpinned it dominates the log — around
three quarters of the events in a real apply, in a file Syncthing copies to every
machine, burying the failure the run actually had.

The unprefixed pair stays, on the reasoning the miss disproved only half of:
naming a logger that does not exist really is free. What it does not buy is
cover for a name nobody thought of, which is what a `logger` field in the stream
now makes visible.
"""


def _http_client_level(noisy: bool) -> None:
    """WARNING, or NOTSET when a second `-v` asked for the request lines.

    Set both ways rather than only pinned, because `configure` runs more than
    once in a process: a level left from an earlier call would otherwise survive
    a later one that wanted the opposite.
    """
    for name in HTTP_LOGGERS:
        logging.getLogger(name).setLevel(logging.NOTSET if noisy else logging.WARNING)


def configure(event_log: Path | None = None) -> None:
    """Point logging at stderr, and at `event_log` when a run is recording.

    Safe to call more than once: the file handler is replaced rather than added,
    so a second run in the same process cannot append to the first one's stream.
    """
    logging.basicConfig(format='%(message)s', stream=sys.stderr, level=logging.DEBUG, force=True)
    level, http_noise = resolved_console()
    _http_client_level(http_noise)

    console = logging.root.handlers[0]
    # Through the name mapping rather than `getattr(logging, ...)`, which answers
    # for any attribute the module happens to have: `LOG_LEVEL=basic_format` fetched
    # the format string and `setLevel` raised ValueError on it. WARN and FATAL are
    # in the mapping too, so the aliases still resolve.
    console.setLevel(logging.getLevelNamesMapping().get(level, logging.INFO))
    # `foreign_pre_chain` is what gives a library's record the same level, timestamp
    # and logger name as one of ours. Without it they arrived with `level: null`
    # and no name, which is what made a flood of them unattributable.
    console.setFormatter(structlog.stdlib.ProcessorFormatter(processor=console_processor(), foreign_pre_chain=SHARED_PROCESSORS))

    for handler in list(logging.root.handlers):
        if handler.name == EVENT_LOG_HANDLER_NAME:
            logging.root.removeHandler(handler)
            handler.close()

    if event_log is not None:
        event_log.parent.mkdir(parents=True, exist_ok=True)
        to_file = logging.FileHandler(event_log)
        to_file.name = EVENT_LOG_HANDLER_NAME
        to_file.setLevel(logging.DEBUG)
        to_file.setFormatter(
            structlog.stdlib.ProcessorFormatter(processor=structlog.processors.JSONRenderer(), foreign_pre_chain=SHARED_PROCESSORS)
        )
        logging.root.addHandler(to_file)

    structlog.configure(
        processors=[*SHARED_PROCESSORS, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )


def bind_run(run_id: str, machine: str) -> None:
    """Stamp every later event with the run it belongs to.

    Through contextvars rather than a bound logger passed around, so a function
    deep in a provider logs the run id without taking it as an argument.
    """
    structlog.contextvars.bind_contextvars(run_id=run_id, machine=machine)


def clear_run() -> None:
    structlog.contextvars.clear_contextvars()


def get_logger(name: str):
    return structlog.get_logger(name)
