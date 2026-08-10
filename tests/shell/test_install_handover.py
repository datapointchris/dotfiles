"""The bootstrap installs the CLI and hands over; it never drives it.

`install.sh` ended in `exec dotfiles apply` for as long as it existed, so a bare
`./install.sh` on a machine whose `~/.env` already named it went straight into a
half-hour networked run nobody had asked to start — and behind the work firewall
that run hung mid-download with no plan ever having been shown.

Nothing else catches a return to that. The e2e machine tier runs the bootstrap
and an `apply` as one chain, and `apply` is idempotent, so a bootstrap that had
quietly converged the machine first would leave every assertion there green.
Reading the script is the only cheap place the property is visible at all, which
is why this asserts on its text.
"""

from __future__ import annotations

import re

from shells import REPO

BOOTSTRAP = REPO / 'install.sh'

INVOCATION = re.compile(r'^\s*(?:exec\s+)?dotfiles\b.*$', re.MULTILINE)
"""A line that *runs* the CLI, as against one that prints its name."""


def test_the_bootstrap_never_runs_the_cli_it_installs() -> None:
    running = [line.strip() for line in INVOCATION.findall(BOOTSTRAP.read_text())]
    assert not running, f'install.sh invokes the CLI it installs: {running}'


def test_the_bootstrap_says_what_to_run_next() -> None:
    """The other half of the same property: converging has to be one command
    away, and a tail deleted rather than replaced satisfies the test above on
    its own."""
    text = BOOTSTRAP.read_text()
    assert 'dotfiles plan' in text
    assert 'dotfiles apply' in text
