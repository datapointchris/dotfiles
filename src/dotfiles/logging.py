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
"""

import logging
import os
import sys
from pathlib import Path

import structlog

CONSOLE_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
CONSOLE_FORMAT = os.environ.get('LOG_FORMAT', 'console')
COLOR_CHOICE = os.environ.get('LOG_COLORS', 'auto')

EVENT_LOG_HANDLER_NAME = 'dotfiles_event_log'

SHARED_PROCESSORS = [
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
    if COLOR_CHOICE in {'true', 'false'}:
        return COLOR_CHOICE == 'true'
    return sys.stderr.isatty()


def console_processor():
    if CONSOLE_FORMAT == 'json':
        return structlog.processors.JSONRenderer()
    return structlog.dev.ConsoleRenderer(colors=use_colors(), pad_level=True)


def configure(event_log: Path | None = None) -> None:
    """Point logging at stderr, and at `event_log` when a run is recording.

    Safe to call more than once: the file handler is replaced rather than added,
    so a second run in the same process cannot append to the first one's stream.
    """
    logging.basicConfig(format='%(message)s', stream=sys.stderr, level=logging.DEBUG, force=True)

    console = logging.root.handlers[0]
    console.setLevel(getattr(logging, CONSOLE_LEVEL, logging.INFO))
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
