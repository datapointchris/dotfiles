"""The color gate in colors.sh.

The contract is that escape sequences are emitted only where something will
render them, and that the decision is made once per process — which is what lets
`theme --help > notes` write text while the same function in an interactive shell
keeps its colors.
"""

from __future__ import annotations

import pytest
from shells import SHELLS
from shells import source


def palette(variable: str, **environment: str) -> str:
    """One palette variable's raw bytes, read from a shell that just sourced the file."""
    return source('colors.sh', f'printf "%s" "${variable}"', **environment).stdout


def test_a_pipe_gets_no_color() -> None:
    assert palette('COLOR_RED') == ''


def test_a_pipe_gets_no_reset_either() -> None:
    """Otherwise a caller that always emits the reset writes a bare escape into a file."""
    assert palette('COLOR_RESET') == ''


def test_force_color_overrides_the_non_terminal_detection() -> None:
    assert palette('COLOR_RED', FORCE_COLOR='1') == r'\033[0;31m'


def test_no_color_outranks_force_color() -> None:
    """NO_COLOR is the user's preference and FORCE_COLOR only answers "is this a
    terminal", so preference beats detection."""
    assert palette('COLOR_RED', FORCE_COLOR='1', NO_COLOR='1') == ''


def test_term_dumb_gets_no_color() -> None:
    assert palette('COLOR_RED', TERM='dumb') == ''


def test_the_short_aliases_follow_the_gate() -> None:
    assert palette('RED') == ''
    assert palette('RED', FORCE_COLOR='1') == r'\033[0;31m'


def test_color_enabled_reports_the_decision() -> None:
    assert palette('COLOR_ENABLED') == '0'
    assert palette('COLOR_ENABLED', FORCE_COLOR='1') == '1'


@pytest.mark.parametrize('shell', SHELLS)
def test_the_stored_value_is_a_literal_escape_not_a_resolved_esc_byte(shell: str) -> None:
    """`echo -e` is what renders these, so storing a real ESC would change what
    every caller emits. zsh sources this file too, and its printf has to agree."""
    result = source('colors.sh', 'printf "%s" "$COLOR_RED"', shell=shell, FORCE_COLOR='1')

    assert result.stdout == r'\033[0;31m'


def test_a_color_function_renders_when_color_is_on() -> None:
    result = source('colors.sh', 'color_red hello', FORCE_COLOR='1')

    assert result.stdout == '\x1b[0;31mhello\x1b[0m\n'


def test_a_color_function_degrades_to_plain_text_when_color_is_off() -> None:
    result = source('colors.sh', 'color_red hello')

    assert result.stdout == 'hello\n'
