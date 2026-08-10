"""Reading a version out of a tool's own output, and comparing two of them.

The one hand-rolled comparator in the package, and it is hand-rolled on purpose:
the alternative is a dependency that has to be installed before the thing that
checks whether anything is installed.

`parse` reduces its input to dotted numbers before anything is compared, so a
suffix that would order differently never reaches a comparison at all. Release
tags are the shapes that exercise it — a monorepo component carries its prefix on
both sides and a formula-style tag carries its name, which is why the numbers are
found inside the string rather than at the front of it.
"""

from __future__ import annotations

import re

NUMBERS = re.compile(r'v?(\d+(?:\.\d+)+)')


def parse(text: str) -> tuple[int, ...] | None:
    """The first dotted-numeric version in some output, as a comparable tuple.

    Tools disagree about how to say it — `go version go1.23.4 linux/amd64`,
    `rustc 1.83.0 (90b35a623 2024-11-26)`, `v22.11.0` — so the first thing that
    looks like a version is what is taken, which is what every one of those puts
    first.

    **At least two components**, which is the difference between reading a version
    and reading any number that happens to come first. lazygit leads with
    `commit=aee0e40ec1235476e9328678f0f3e2462576b9ae`, and a single-integer match
    took the `0` out of that hash and reported an up-to-date tool as eight minor
    versions behind. Nothing declared or reported anywhere here is a bare integer,
    and one that was would answer `None` — unmeasurable, not wrong.
    """
    match = NUMBERS.search(text)
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split('.'))


def at_least(current: str, floor: str) -> bool | None:
    """Whether `current` meets `floor`, or None when either cannot be read.

    None rather than False: an unparseable version is not a failing one, and
    reporting it as too old is the guess this exists to avoid.
    """
    have, want = parse(current), parse(floor)
    if have is None or want is None:
        return None
    return _padded(have, want) >= _padded(want, have)


def exceeds(current: str, ceiling: str) -> bool:
    """Whether `current` is strictly newer than `ceiling`.

    `False` rather than `None` where either cannot be read, unlike everything else
    here. The caller falls through to `at_least` with the same two strings, and
    that already answers `None` for an unparseable one — returning `None` here as
    well would report the same tool unmeasurable twice.
    """
    have, want = parse(current), parse(ceiling)
    if have is None or want is None:
        return False
    return _padded(have, want) > _padded(want, have)


def exactly(current: str, pinned: str) -> bool | None:
    """Whether `current` is `pinned`. A pin means that release and no other.

    Compared as numbers rather than as strings, so `1.10` and `1.10.0` are one
    version — which they are to every tool that installs them.
    """
    have, want = parse(current), parse(pinned)
    if have is None or want is None:
        return None
    return _padded(have, want) == _padded(want, have)


def _padded(value: tuple[int, ...], against: tuple[int, ...]) -> tuple[int, ...]:
    """Zero-fill to the longer length, so `1.23` and `1.23.0` compare equal.

    A declared floor is usually written to two components and the tool reports
    three, and without this every such machine reads as below its own floor.
    """
    return value + (0,) * (len(against) - len(value))
