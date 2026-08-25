"""One module per section of the help, so where a command goes is never a question.

The verbosity pair lives here rather than beside each command group because it is
the one option every reconciling leaf takes, in all three verbs and under every
resource. `--machine` and `--json` are declared per module and that is
fine — they differ in help text and in which leaves want them — but a flag that
must read identically on twenty leaves is a flag that should have one definition.
"""

from __future__ import annotations

from typing import Any

import typer

from dotfiles import logging
from dotfiles import machine as machine_declaration
from dotfiles.output import console
from dotfiles.output import error
from dotfiles.session import NoMachine
from dotfiles.session import Session
from dotfiles.vocabulary import ExitCode

VerboseOption = typer.Option(
    0,
    '--verbose',
    '-v',
    count=True,
    metavar='',
    show_default=False,
    help='Every item examined, and every step; -vv adds the HTTP requests behind them',
)
QuietOption = typer.Option(False, '--quiet', '-q', help='The verdict alone, without the per-item evidence')

MEASURES_UPSTREAM = True
"""Every read verb measures. `--cached` is how a caller declines.

A verb was invoked because somebody wanted an answer, so it gives the current one.
`plan` and `apply` need it to be right about what a write would do, and `check`
needs it to answer "is anything here behind" at all — which is the question it was
asked. A figure up to `releases.TTL` old serves none of them.

The budget that would argue against it is not there. `check` is the verb that runs
unattended, and `schedule.INTERVAL_SECONDS` fires it once a day — one refresh a day
is not worth designing around. Conditional requests settle the rest: a revalidated
refresh bills a handful of requests rather than one per release, because GitHub does
not charge for a 304.
"""


EVERY_SOURCE = 'GitHub, the package managers and each plugin remote'
"""What a composite verb reaches. `main.plan`, `main.check` and `main.apply`."""

RELEASES_AND_MANAGERS = 'GitHub and the package managers'
"""What `packages` reaches: declared releases, and the managers holding packages back."""

THE_MANAGERS = 'the package managers'
"""What `system` reaches. It asks GitHub about nothing."""

EACH_PLUGIN_REMOTE = 'each plugin remote'
"""What `plugins` reaches. It asks no package manager."""


def refresh_flag(sources: str = EVERY_SOURCE) -> Any:
    """The currency axis, spelled one way on every verb that reads it.

    **Tri-state rather than a plain bool**, because `--offline` has to tell "not
    passed" from "passed false". Under a `True` default, `plan --offline` refuses
    itself as a contradiction for typing neither flag.

    **The default is in parentheses, never brackets.** Rich parses `[...]` in help
    text as a style tag and drops what it cannot resolve — `cli-design.md` § "Never
    use `[dim]` in text you write". `show_default` cannot do it either, since the
    declared value is the tri-state `None`.

    **`sources` is a parameter because one line on eight leaves is wrong on four.**
    `system` asks GitHub about nothing and `plugins` asks no package manager. The
    spelling and default stay identical; only the sentence narrows.
    """
    return typer.Option(
        None,
        '--refresh/--cached',
        show_default=False,
        help=f'Ask {sources} what is newest, or answer from cache (default: refresh)',
    )


def currency(refresh: bool | None, *, offline: bool) -> bool:
    """Whether this run spends the network on upstream versions.

    The contradiction fires on an explicit `--refresh` alone. `--cached --offline`
    asks for the same thing twice rather than for two opposite things, and neither
    flag typed is the default, which cannot be a usage error.
    """
    if offline and refresh:
        contradiction('--offline', '--refresh')
    return MEASURES_UPSTREAM if refresh is None else refresh


def contradiction(first: str, second: str) -> None:
    """Refuse two flags that cancel each other, rather than picking one.

    Shared so the next pair does not go unguarded: `--offline --refresh` otherwise
    resolves silently to offline.

    `BadParameter`, so it exits 2 — a caller has to tell "you typed it wrong" from
    "it ran and failed", and only the first is worth retrying.
    """
    raise typer.BadParameter(f'{first} and {second} contradict each other; pass one')


def verbosity(verbose: int, quiet: bool) -> None:
    """Point the console sink at what the flags asked for, before anything logs.

    Counted `-v` with a `-q` beside it, as uv, ruff, cargo, rsync and curl all
    ship. The two together are a usage error rather than a precedence rule: either
    resolution is defensible, which is the tell that the caller meant neither.

    The file sink is untouched by both, because the questions asked after a failed
    install are only answerable if the detail was recorded while nobody wanted it.

    **Reconfigured here rather than left to the next `configure`.** Only the three
    recording verbs call `sinks.open_log`, so on a verb that opens no log `-v`
    would record a choice nothing reads. Nothing has opened the file sink this
    early, so rebuilding the console here drops no handler.
    """
    if verbose and quiet:
        raise typer.BadParameter('--verbose and --quiet ask for opposite things; pass one')
    logging.choose_console(verbose, quiet)
    logging.configure()


def resolved(
    machine: str | None,
    owner: str | None = None,
    packages: frozenset[str] = frozenset(),
    *,
    offline: bool = False,
    refresh: bool = False,
) -> Session:
    """One machine's Session, for every leaf that takes `--machine`.

    Three failures, two answers, and none of them is decided here any more.
    `NoMachine` is nothing named at all and `NoSuchMachine` is a name nothing
    declares; both are retryable by naming a different one, which is what
    `ExitCode.USAGE` means, and both now say so themselves. A manifest that
    exists and will not parse is `ExitCode.ISSUE` — the machine really is wrong
    and no amount of retyping helps.

    All three are raised by `Session.resolve`, which reads the manifest rather than
    only naming it — a helper touching a lazy property to provoke an error reads as
    a dead line to the next person.
    """
    return Session.resolve(machine, owner=owner, packages=packages, offline=offline, refresh=refresh and not offline)
