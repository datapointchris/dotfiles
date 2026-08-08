"""Reading a version out of a tool's own output, and comparing two of them."""

from __future__ import annotations

import pytest

from dotfiles import versions


@pytest.mark.parametrize(
    ('output', 'expected'),
    [
        ('go version go1.26.5 linux/amd64', (1, 26, 5)),
        ('rustc 1.97.1 (8bab26f4f 2026-07-14)', (1, 97, 1)),
        ('uv 0.12.2 (x86_64-unknown-linux-gnu)', (0, 12, 2)),
        ('v24.19.0', (24, 19, 0)),
        ('0.11', (0, 11)),
        ('1.10.5', (1, 10, 5)),
    ],
)
def test_the_first_dotted_number_is_the_version(output: str, expected: tuple[int, ...]) -> None:
    """Every tool says it differently and all of them say it first."""
    assert versions.parse(output) == expected


@pytest.mark.parametrize('output', ['', 'not a version', 'command not found'])
def test_output_with_no_version_in_it_parses_to_nothing(output: str) -> None:
    assert versions.parse(output) is None


@pytest.mark.parametrize(
    ('current', 'floor', 'expected'),
    [
        ('1.23.4', '1.23', True),
        ('1.23', '1.23.0', True),
        ('1.23.0', '1.23', True),
        ('go version go1.26.5', '1.23', True),
        ('1.22.9', '1.23', False),
        ('0.49', '0.50', False),
        ('2.0.0', '1.99.99', True),
    ],
)
def test_a_floor_is_met_or_not(current: str, floor: str, expected: bool) -> None:
    """`1.23` and `1.23.0` are one version. A floor is usually written to two
    components and the tool reports three, so without zero-filling every such
    machine reads as below its own floor."""
    assert versions.at_least(current, floor) is expected


@pytest.mark.parametrize(('current', 'floor'), [('', '1.0'), ('nothing', '1.0'), ('1.0', 'unreadable')])
def test_an_unreadable_version_is_neither_met_nor_failed(current: str, floor: str) -> None:
    """None rather than False: reporting it as too old is the guess this avoids."""
    assert versions.at_least(current, floor) is None


@pytest.mark.parametrize(
    ('current', 'pinned', 'expected'),
    [('1.10.5', '1.10.5', True), ('1.10', '1.10.0', True), ('1.10.6', '1.10.5', False)],
)
def test_a_pin_means_that_release_and_no_other(current: str, pinned: str, expected: bool) -> None:
    assert versions.exactly(current, pinned) is expected
