"""Whether a machine level that cannot start reports a skip or a failure.

Measured 2026-08-16, adding the `scheduler` environment. `debian:12` was not on
the box, nothing declared how to build it, so every case skipped — and the cell
exited 0, so `matrix.py` printed `pass  fresh-install/scheduler  3.2s` and
`1/1 cells passed`. A rung documented at 20-30 minutes reported green in three
seconds having asserted nothing.

The reading depends on who is running, exactly as it does for a missing
interpreter. A workstation running the fast suite should skip the levels it
cannot start; a run that *asked* for `fresh-install` has already said it wants a
machine, and a skip there is the runner reporting success for work it did not
do. `tests/conftest.py` § `resolve_interpreters` states the same rule for bash,
zsh and tmux — this is that rule applied to the images.

Every environment is exposed to it. `archlinux:latest` declares no builder
either and works only because it happens to be pulled on this box; on a fresh
machine the archlinux cell skips and reports the same false pass.
"""

from __future__ import annotations

import pytest
from harness import machine_verdict


def test_a_present_image_runs() -> None:
    verdict = machine_verdict(docker_running=True, image_present=True, buildable=False, required=False)

    assert verdict.action == 'run'


def test_an_absent_image_with_a_builder_is_built() -> None:
    verdict = machine_verdict(docker_running=True, image_present=False, buildable=True, required=False)

    assert verdict.action == 'build'


def test_an_absent_image_is_a_skip_for_a_runner_that_did_not_ask() -> None:
    """The fast suite on a workstation must not fail for want of a container."""
    verdict = machine_verdict(docker_running=True, image_present=False, buildable=False, required=False)

    assert verdict.action == 'skip'
    assert 'absent' in verdict.reason


def test_an_absent_image_is_a_refusal_for_a_runner_that_asked() -> None:
    """This is the regression. A cell that ran nothing must not exit 0."""
    verdict = machine_verdict(docker_running=True, image_present=False, buildable=False, required=True)

    assert verdict.action == 'refuse'
    assert 'absent' in verdict.reason


def test_a_stopped_docker_is_a_refusal_for_a_runner_that_asked() -> None:
    """Same reading, one cause earlier.

    A matrix run against a machine whose Docker is down skipped every cell and
    reported the whole level green, which is the identical failure with a
    different first line in the log.
    """
    verdict = machine_verdict(docker_running=False, image_present=False, buildable=True, required=True)

    assert verdict.action == 'refuse'
    assert 'docker' in verdict.reason.lower()


def test_a_stopped_docker_is_a_skip_for_a_runner_that_did_not_ask() -> None:
    verdict = machine_verdict(docker_running=False, image_present=True, buildable=False, required=False)

    assert verdict.action == 'skip'
    assert 'docker' in verdict.reason.lower()


@pytest.mark.parametrize('required', (True, False))
def test_docker_is_asked_about_before_the_image(required: bool) -> None:
    """A stopped Docker cannot answer whether an image exists.

    Ordering rather than an implementation detail: `image_exists` shells out to
    `docker image inspect`, which fails for both reasons and cannot say which.
    """
    verdict = machine_verdict(docker_running=False, image_present=False, buildable=False, required=required)

    assert 'docker' in verdict.reason.lower()
