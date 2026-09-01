"""The one boundary that turns a failure into an exit status.

Raised through a real command rather than by calling `Boundary.invoke` directly,
because what is being asserted is that click's nesting carries a leaf's exception
up to the root group. Calling the handler proves the handler works and says
nothing about whether anything reaches it.
"""

from __future__ import annotations

import typer
from typer.testing import CliRunner

from dotfiles.main import app
from dotfiles.refusal import Refusal
from dotfiles.vocabulary import ExitCode

runner = CliRunner()


class Retryable(Refusal):
    code = ExitCode.USAGE


def raising(error: BaseException):
    """A leaf that does nothing but fail, registered under a name nothing else uses.

    `BaseException` rather than `Exception`, because `KeyboardInterrupt` is one and
    it is exactly the case the boundary has to answer for.
    """

    def leaf() -> None:
        raise error

    return leaf


def invoke(error: BaseException):
    app.command('boundary-probe')(raising(error))
    try:
        return runner.invoke(app, ['boundary-probe'], catch_exceptions=False)
    finally:
        app.registered_commands = [entry for entry in app.registered_commands if entry.name != 'boundary-probe']


def test_a_refusal_raised_in_a_leaf_reaches_the_root_group() -> None:
    """The nesting is the point. A sub-app has no handler of its own and must not
    need one, or every new command group is a place to forget it."""
    ran = invoke(Refusal('the bundle could not be built'))

    assert ran.exit_code == ExitCode.ISSUE
    assert 'the bundle could not be built' in ran.output


def test_a_refusal_carries_its_own_kind_rather_than_the_site_deciding() -> None:
    """A subclass states its kind once, in its own declaration.

    This is what the whole boundary exists for. A leaf passing a *foreign* integer
    to `typer.Exit` — argparse's status, git's return code — lands on 1, which is
    DRIFT.
    """
    ran = invoke(Retryable('name a machine'))

    assert ran.exit_code == ExitCode.USAGE


def test_an_instance_can_override_the_class_it_was_declared_with() -> None:
    ran = invoke(Refusal('nothing named a machine', code=ExitCode.USAGE))

    assert ran.exit_code == ExitCode.USAGE


def test_every_reason_survives_and_the_later_ones_are_aligned_under_the_first() -> None:
    """A manifest with three faults is fixed in one pass or in three.

    Unindented, a second reason arrives with no marker and reads as an
    unattributed line rather than as part of the refusal above it.
    """
    ran = invoke(Refusal('box: declares go\nbox: declares rust'))

    assert 'declares go' in ran.output
    assert '  box: declares rust' in ran.output


def test_the_remedy_travels_with_the_refusal_rather_than_the_raise_site() -> None:
    """Whatever knows a bundle is missing also knows which command builds one.
    Printed apart, a message and its remedy are two things to keep in step."""
    ran = invoke(Refusal('no readable bundle', advice='stage one with: dotfiles bundle stage PATH'))

    assert 'no readable bundle' in ran.output
    assert 'dotfiles bundle stage PATH' in ran.output


def test_anything_that_is_not_a_refusal_is_left_alone() -> None:
    """A boundary catching every exception would turn a bug into a tidy sentence
    and hide the traceback that says where it is."""
    try:
        invoke(RuntimeError('a real bug'))
    except RuntimeError as escaped:
        assert str(escaped) == 'a real bug'
    else:
        raise AssertionError('the boundary swallowed a RuntimeError')


def test_a_typer_exit_still_carries_its_own_code() -> None:
    """`typer.Exit` is click's own control flow and predates all of this. The
    boundary must not intercept it, or every converged run exits ISSUE."""
    ran = invoke(typer.Exit(ExitCode.CONVERGED))

    assert ran.exit_code == ExitCode.CONVERGED


def test_an_aborted_prompt_does_not_report_the_machine_as_drifted() -> None:
    """click exits 1 on `Abort`, and 1 is DRIFT here. Ctrl-D at a prune prompt
    therefore said pending changes about a run that measured nothing and changed
    nothing, while answering `n` at the same prompt said ISSUE. The TTY guard
    beside each prompt covers the piped case and stops at the keyboard."""
    ran = invoke(typer.Abort())

    assert ran.exit_code == ExitCode.ISSUE
    assert ran.exit_code != ExitCode.DRIFT


def test_an_interrupt_is_the_same_answer_as_an_abort() -> None:
    """Ctrl-C is the other way a person leaves a prompt, and python exits 1 on it
    for reasons that have nothing to do with this tool's vocabulary."""
    ran = invoke(KeyboardInterrupt())

    assert ran.exit_code == ExitCode.ISSUE
