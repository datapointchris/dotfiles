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
        ('Haskell Dockerfile Linter 2.12.0', (2, 12, 0)),
        ('tree-sitter 0.26.11', (0, 26, 11)),
        # The one that earned the two-component rule: a single-integer match took
        # the 0 out of the commit hash and reported a current lazygit as stale.
        (
            'commit=aee0e40ec1235476e9328678f0f3e2462576b9ae, build date=2026-08-04T07:26:19Z, '
            'build source=binaryRelease, version=0.64.0, os=linux, arch=amd64, git version=2.55.0',
            (0, 64, 0),
        ),
    ],
)
def test_the_first_dotted_number_is_the_version(output: str, expected: tuple[int, ...]) -> None:
    """Every tool says it differently and all of them say it first."""
    assert versions.parse(output) == expected


@pytest.mark.parametrize('output', ['', 'not a version', 'command not found', 'version 7', 'abc123def'])
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
        # Numeric, not lexical: 10 sorts before 9 as text and after it as a number.
        ('1.10.0', '1.9.0', True),
        ('1.9.0', '1.10.0', False),
        # Release *tags*, not tool output. A monorepo component carries its prefix
        # on both sides of the comparison and a formula-style tag carries its name,
        # so the numbers have to be found inside the tag rather than at the front
        # of it — the shapes `version-helpers.sh` was asked about before it went.
        ('cli/v1.2.1', 'cli/v1.2.0', True),
        ('cli/v1.2.0', 'cli/v1.2.1', False),
        ('jq-1.8.3', 'jq-1.8.2', True),
        ('jq-1.8.2', 'jq-1.8.3', False),
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


@pytest.mark.parametrize(
    ('current', 'ceiling', 'expected'),
    [
        ('2.10.0', '1.2.3', True),
        ('ifiles 2.10.0', '1.2.3', True),
        ('1.2.3', '1.2.3', False),
        ('1.2.3', '1.2.4', False),
        ('1.10', '1.10.0', False),
    ],
)
def test_a_version_above_the_newest_release_is_recognised(current: str, ceiling: str, expected: bool) -> None:
    """A repo that re-versioned downwards strands a machine above every tag it
    publishes. `at_least` reads that as comfortably current, which is why the
    question has to be asked the other way round as well."""
    assert versions.exceeds(current, ceiling) is expected


@pytest.mark.parametrize(('current', 'ceiling'), [('', '1.0'), ('built from source', '1.0'), ('1.0', 'unreadable')])
def test_an_unreadable_version_exceeds_nothing(current: str, ceiling: str) -> None:
    """False rather than None, unlike its neighbours: the caller falls through to
    `at_least` on the same two strings, which answers None for these already."""
    assert versions.exceeds(current, ceiling) is False
