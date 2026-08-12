"""Logging configuration: a console for people, a JSON stream for machines.

Two sinks, deliberately at different levels. Everything is emitted at debug and
the full stream goes to the run's `.jsonl`, because the questions asked after a
failed install ("what did it actually download", "which step was slow") are only
answerable if the detail was recorded while nobody wanted it. The terminal shows
what is useful at the time, which today's output already gets right and is the
bar to hold rather than to change for its own sake.

`LOG_FORMAT=json` sends the console sink to JSON too, for a caller parsing
stderr. `LOG_LEVEL` moves the console threshold; the file sink stays at debug
whatever it says, since a record that respected it would be missing exactly the
detail it exists to keep.

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


EVENT_LOG_HANDLER_NAME = 'dotfiles_event_log'

SHARED_PROCESSORS: list[structlog.typing.Processor] = [
    structlog.contextvars.merge_contextvars,
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt='iso', utc=True),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
]


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


HTTP_LOGGERS = ('httpx2', 'httpx', 'httpcore')
"""Third-party loggers that narrate every request at INFO.

Named rather than solved by lowering the root level: root is DEBUG on purpose, so
the event log gets everything while the console filters. That means any library
logging at INFO reaches the console by default, and httpx writes one
`HTTP Request: GET https://api.github.com/... "200 OK"` per call — which on a
release refresh is a line per declared tool, between the rows a person is
actually reading.

`httpx` and `httpcore` are here alongside the fork this repo uses because the
cost of naming a logger that does not exist is nothing, and the cost of missing
one is the noise coming back on a dependency swap.
"""


def _quiet_the_http_client() -> None:
    for name in HTTP_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def configure(event_log: Path | None = None) -> None:
    """Point logging at stderr, and at `event_log` when a run is recording.

    Safe to call more than once: the file handler is replaced rather than added,
    so a second run in the same process cannot append to the first one's stream.
    """
    logging.basicConfig(format='%(message)s', stream=sys.stderr, level=logging.DEBUG, force=True)
    _quiet_the_http_client()

    console = logging.root.handlers[0]
    # Through the name mapping rather than `getattr(logging, ...)`, which answers
    # for any attribute the module happens to have: `LOG_LEVEL=basic_format` fetched
    # the format string and `setLevel` raised ValueError on it. WARN and FATAL are
    # in the mapping too, so the aliases still resolve.
    console.setLevel(logging.getLevelNamesMapping().get(console_level(), logging.INFO))
    console.setFormatter(structlog.stdlib.ProcessorFormatter(processor=console_processor()))

    for handler in list(logging.root.handlers):
        if handler.name == EVENT_LOG_HANDLER_NAME:
            logging.root.removeHandler(handler)
            handler.close()

    if event_log is not None:
        event_log.parent.mkdir(parents=True, exist_ok=True)
        to_file = logging.FileHandler(event_log)
        to_file.name = EVENT_LOG_HANDLER_NAME
        to_file.setLevel(logging.DEBUG)
        to_file.setFormatter(structlog.stdlib.ProcessorFormatter(processor=structlog.processors.JSONRenderer()))
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
