"""An offline run never carries a refresh, whichever door asked for one.

`Session.resolve` is the only statement of that rule, and every caller depends on
it rather than restating it. `reconcile.apply_machine` asks for `refresh=True`
outright and gets a cached run when the machine is offline.

What an unpinned version costs is a whole apply spending the network it was told
not to: GitHub per declared release, a fetch per plugin clone, and every manager
in `syspkg.NETWORKED`.
"""

from __future__ import annotations

import pytest

from dotfiles.session import Session

MACHINE = 'linux-lxc-server'


@pytest.mark.parametrize(
    ('offline', 'asked', 'carried'),
    [
        (False, False, False),
        (False, True, True),
        (True, False, False),
        (True, True, False),
    ],
)
def test_refresh_survives_only_when_the_run_has_a_network(offline: bool, asked: bool, carried: bool) -> None:
    session = Session.resolve(MACHINE, offline=offline, refresh=asked)

    assert session.refresh is carried
    assert session.offline is offline


def test_an_apply_asking_to_refresh_offline_is_narrowed_rather_than_refused() -> None:
    """`apply_machine` passes `refresh=True` unconditionally, so the narrowing is
    what stops `apply --offline` reaching the network. A refusal here would make
    the flag pair unusable rather than redundant."""
    session = Session.resolve(MACHINE, offline=True, refresh=True)

    assert session.refresh is False


def test_direct_construction_keeps_the_pair_a_caller_set() -> None:
    """The narrowing is a guarantee of the front door, not of the dataclass. A
    test building the contradictory pair on purpose still gets it, which is what
    makes the assertions above measure `resolve` rather than `__init__`."""
    session = Session(machine_name=MACHINE, offline=True, refresh=True)

    assert session.refresh is True
