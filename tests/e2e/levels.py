"""The test ladder, as data rather than as five invocations to remember.

Every rung already existed and was addressed by hand — a file path here, a flag
combination there — so reaching for the cheapest one that could answer a question
meant remembering which of them that was. Twice measured, it was not remembered:
a container died and thirty minutes went with it, then an assertion added after a
run started needed another thirty to answer.

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
        name='unit',
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
        name='container',
        purpose='probe',
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
        name='set',
        purpose='set',
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
        name='installed',
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
        name='full',
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

DEFAULT_THROUGH = 3
"""Where `task test:matrix` stops.

Level 4 is opt-in because it is the only one whose cost is measured in hours once
the environments are counted, and because levels 0 to 3 catch what it would catch
about the rig, the assertions and one section at a time.
"""


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
        return BY_NAME['unit']
    if 'over_base' in fixturenames:
        return BY_NAME['set']
    if 'machine' in fixturenames or 'fresh_install' in fixturenames:
        return BY_NAME['installed'] if installed else BY_NAME['full']
    if 'container' in fixturenames or 'fresh_container' in fixturenames:
        return BY_NAME['container']
    return BY_NAME['unit']
