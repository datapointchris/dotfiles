"""The click group that turns a `Refusal` into an exit status.

It prints a refusal through `output.report`, which a reconcile also calls to close
a run, so that function lives in `output` and this module holds the group alone.
"""

from __future__ import annotations

from typing import Any

import typer
from typer.core import TyperGroup

from dotfiles.output import error
from dotfiles.output import report
from dotfiles.refusal import Refusal
from dotfiles.vocabulary import ExitCode


class Boundary(TyperGroup):
    """The one place a `Refusal` becomes an exit status.

    On the *root* group, because click nests invocation — so one handler sees every
    command's failure and a new sub-app cannot forget its own `cls=`.

    **Inside click rather than around `app()` in the console script.**
    `typer.testing.CliRunner` never calls the entry point, so a handler outside
    click is one the suite cannot reach, on the branch where being wrong is silent.

    **`ctx` is untyped because its type is whichever click the installed typer
    carries.** typer 0.24 subclasses the real `click.Context`; 0.27 vendors its own
    and ships no `click` at all.
    """

    def invoke(self, ctx: Any) -> Any:
        """Every exit this tool owns, including the ones the framework hardcodes to 1.

        **A tool that spends 1 on a verdict owes a branch for the framework's
        default.** click exits 1 on `Abort`, and 1 is `DRIFT` here — so Ctrl-D at a
        prompt reports the machine as differing from its declaration.

        **`Abort` and `KeyboardInterrupt` do not get the same sentence, because
        only one of them knows.** A prompt raises `Abort` before anything has
        happened, so `nothing was done` is a fact. `KeyboardInterrupt` arrives at
        any instant — after eighty downloads, after an upload has landed — and
        claiming nothing happened would assert something unmeasured.
        """
        try:
            return super().invoke(ctx)
        except Refusal as refused:
            raise typer.Exit(report(refused)) from refused
        except typer.Abort as aborted:
            error('nothing was done')
            raise typer.Exit(ExitCode.ISSUE) from aborted
        except KeyboardInterrupt as interrupted:
            error('interrupted')
            raise typer.Exit(ExitCode.ISSUE) from interrupted
        except Exception as failure:
            name_takers(failure, ctx.find_root())
            raise


def name_takers(failure: Exception, root: Any) -> None:
    """Append the commands that do take an option this one refused.

    click's `NoSuchOption` is recognized by its `option_name`, `possibilities` and
    `message` rather than by class, because naming the class means importing click.
    """
    option = getattr(failure, 'option_name', None)
    if not option or not hasattr(failure, 'possibilities') or not hasattr(failure, 'message'):
        return
    takers = [f'`{path}`' for path in commands_taking(root.command, option, root.info_name or 'dotfiles')]
    if takers:
        listed = takers[0] if len(takers) == 1 else f'{", ".join(takers[:-1])} and {takers[-1]}'
        failure.message = f'{failure.message}. {listed} {"takes" if len(takers) == 1 else "take"} it.'


def commands_taking(group: Any, option: str, path: str) -> list[str]:
    """Every visible leaf command under `group` that declares `option`, by its full path."""
    found = []
    for name, command in sorted(group.commands.items()):
        if command.hidden:
            continue
        if hasattr(command, 'commands'):
            found.extend(commands_taking(command, option, f'{path} {name}'))
        elif any(option in getattr(param, 'opts', ()) for param in command.params):
            found.append(f'{path} {name}')
    return found
