"""The test ladder, as data rather than as five invocations to remember.

Addressed by hand — a file path here, a flag combination there — reaching for the
cheapest rung that can answer a question means remembering which one that is. Get
it wrong and the cost is half an hour: a container dies, or an assertion added
after a run started needs the run again.

**A level is identified by the fixture its tests ask for, never by a file list.**
`over_base` starts a throwaway container from a base image, `machine` needs a
whole install, `container` needs neither. A list of module names beside them
would be a second keying of the same fact, and the one that goes stale — the same
failure `registry.py` exists to have ended for providers.

`matrix.py` runs them in order. Nothing here starts anything.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Level:
    number: int
    name: str
    """What `task test:<name>` and `--level <name>` call it."""

    fixture: str | None
    """The fixture whose presence puts a test at this level, or None for the
    level that is everything Docker never touches."""

    purpose: str | None
    """What this level's container is *for*, and the segment its name carries.

    Not the level name, because `installed` and `full` must share one container —
    asserting against an install means finding the one the full run left. So the
    name says `machine`, and `docker ps` reads as what a container holds rather
    than as which invocation happened to make it.
    """

    docker: bool
    installed: bool
    """Whether this level asserts against an install rather than performing one.

    The one place two levels select the same tests: `installed` and `full` are
    both the `machine` fixture, and the flag is the whole difference between
    twenty seconds and twenty-four minutes.
    """

    per_environment: bool
    """Whether the matrix fans this level out over the environments at all."""

    concurrency: int
    """How many environments may run it at once."""

    cost: str
    """What one environment costs, for the runner to print before it spends it."""

    answers: str
    """What this level can tell you, so a reader can pick without running one."""


LEVELS = (
    Level(
        number=0,
        name='no-container',
        purpose=None,
        fixture=None,
        docker=False,
        installed=False,
        per_environment=False,
        concurrency=1,
        cost='~30s total',
        answers='every question that does not need a machine, including the rig itself',
    ),
    Level(
        number=1,
        name='empty-container',
        purpose='empty',
        fixture='container',
        docker=True,
        installed=False,
        per_environment=True,
        concurrency=4,
        cost='~25s each',
        answers='the container, the exec environment, the firewall — with nothing installed',
    ),
    Level(
        number=2,
        name='section-over-base',
        purpose='section',
        fixture='over_base',
        docker=True,
        installed=False,
        per_environment=True,
        concurrency=2,
        cost='minutes each',
        answers='one section installing over a base image, without building a whole machine',
    ),
    Level(
        number=3,
        name='existing-install',
        purpose='machine',
        fixture='machine',
        docker=True,
        installed=True,
        per_environment=True,
        concurrency=4,
        cost='~20s each',
        answers='every assertion about a finished machine, against the install already there',
    ),
    Level(
        number=4,
        name='fresh-install',
        purpose='machine',
        fixture='machine',
        docker=True,
        installed=False,
        per_environment=True,
        # Deliberately one, and not because two would collide: `container_name`
        # made that impossible. An install is twenty to thirty minutes of one
        # box's CPU and disk, and four at once made the machine unusable for the
        # duration. Raise it with `--concurrency` on a box that has been measured
        # rather than by editing this number.
        concurrency=1,
        cost='20-30 min each',
        answers='whether a machine installs from nothing, which no cheaper level can',
    ),
)

BY_NAME = {level.name: level for level in LEVELS}
BY_NUMBER = {level.number: level for level in LEVELS}

LAST = LEVELS[-1].name
"""Where a matrix run stops unless told otherwise: the top.

`--through` defaults here because "run the matrix" should mean the matrix. The
expensive rung is opt-*out*, and the runner prints what each level costs before
it spends it, so the price is stated rather than hidden behind a default that
quietly did less than the word says.

`task test:matrix:quick` is the subset worth having — everything below the rung
whose cost is measured in hours once the environments are counted.
"""

QUICK_THROUGH = 'existing-install'
"""What `--through` means for the subset that answers most questions in a minute."""


def resolve(wanted: str) -> Level:
    """A level from its name or its number, with the alternatives on a refusal."""
    if wanted in BY_NAME:
        return BY_NAME[wanted]
    if wanted.isdigit() and int(wanted) in BY_NUMBER:
        return BY_NUMBER[int(wanted)]
    known = ', '.join(f'{level.number}/{level.name}' for level in LEVELS)
    raise KeyError(f'no such level {wanted!r}; known are {known}')


def level_of(fixturenames: tuple[str, ...] | list[str], *, docker: bool, installed: bool) -> Level:
    """Which level a collected test belongs to.

    Ordered most specific first, because the fixtures nest: `machine` is built on
    `container`, and `fresh_install` on `machine`. Asking about `container` first
    would put every install test at level 1 and quietly run the whole ladder as
    its cheapest rung.
    """
    if not docker:
        return BY_NAME['no-container']
    if 'over_base' in fixturenames:
        return BY_NAME['section-over-base']
    if 'machine' in fixturenames or 'fresh_install' in fixturenames:
        return BY_NAME['existing-install'] if installed else BY_NAME['fresh-install']
    # `builder` here rather than beside `machine`, and the order decides it: the
    # exchange fixture asks for both, and it needs an install while this needs
    # only a started container.
    if 'container' in fixturenames or 'fresh_container' in fixturenames or 'builder' in fixturenames:
        return BY_NAME['empty-container']
    return BY_NAME['no-container']
