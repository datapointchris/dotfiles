"""logging.sh — the parseable prefixes and the stream they go to.

Every level writes to stderr, including the ones carrying good news: stdout
belongs to whatever the script produces for a caller to consume, and a progress
line on it corrupts that. `standards/cli-design.md` § "stdout is data, stderr is
everything else" is the rule; this is what holds it.
"""

from __future__ import annotations

import pytest
from shells import source

LEVELS = (
    ('log_info', '[INFO]'),
    ('log_success', '[INFO]'),
    ('log_warning', '[WARNING]'),
    ('log_error', '[ERROR]'),
)
"""`log_success` shares `[INFO]` deliberately — the prefix is the severity an
aggregator filters on, and a success is not its own severity."""


@pytest.mark.parametrize(('level', 'prefix'), LEVELS)
def test_every_level_prints_its_own_prefix_to_stderr(level: str, prefix: str) -> None:
    """The prefixes are what logsift and the log aggregators match on.

    bats merged the two streams into one `$output`, so an assertion there passed
    whichever stream the code chose — which is exactly how the routing went
    unnoticed. Here the empty stdout is asserted alongside the message.
    """
    result = source('logging.sh', f'{level} "a message"')

    assert result.ok
    assert result.stdout == ''
    assert prefix in result.stderr
    assert 'a message' in result.stderr


def test_a_file_and_line_are_appended_only_when_both_are_given() -> None:
    assert 'test.sh:42' in source('logging.sh', 'log_error "broken" "test.sh" "42"').stderr

    without = source('logging.sh', 'log_error "broken"')
    assert 'broken' in without.stderr
    assert ' at ' not in without.stderr


def test_log_debug_is_silent_unless_debug_is_set() -> None:
    """`DEBUG=true` exactly — the check is an equality, so `DEBUG=1` stays quiet."""
    assert source('logging.sh', 'log_debug "noise"').stderr == ''

    verbose = source('logging.sh', 'DEBUG=true log_debug "noise"')
    assert '[DEBUG]' in verbose.stderr
    assert 'noise' in verbose.stderr


@pytest.mark.parametrize(('call', 'prefix'), [('log_fatal "gone"', '[FATAL]'), ('die "gone"', '[ERROR]')])
def test_log_fatal_and_die_both_exit_1(call: str, prefix: str) -> None:
    result = source('logging.sh', call)

    assert result.returncode == 1
    assert prefix in result.stderr
    assert 'gone' in result.stderr


def test_log_fatal_carries_a_file_and_line_the_way_log_error_does() -> None:
    assert 'script.sh:99' in source('logging.sh', 'log_fatal "gone" "script.sh" "99"').stderr
