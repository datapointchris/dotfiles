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
from fnmatch import fnmatch

import pytest
from shells import REPO

from dotfiles import coordinates

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


SHELL_CASE = re.compile(r'^\s*([A-Z*|\s]+)\)\s*UV=uv\.exe', re.MULTILINE)
"""The `case` arm that decides the uv filename, as its glob patterns."""

GIT_BASH_UNAMES = ('MINGW64_NT-10.0-26100', 'MSYS_NT-10.0-26100', 'CYGWIN_NT-10.0-26100')
"""What `uname -s` answers under each POSIX emulation layer on Windows."""


@pytest.mark.parametrize('reported', GIT_BASH_UNAMES)
def test_the_bootstrap_and_the_cli_agree_on_what_windows_looks_like(reported: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """One fact written at two sites, so a test holds them together.

    `install.sh` imports nothing — that is the whole reason it is POSIX sh and
    readable before running it — so it cannot ask `coordinates` which unames mean
    Windows and has to carry the list itself. Two sites deriving one fact is how
    four of this repo's pinned faults happened, and the only site that would find
    out here is a Windows box nobody else in the fleet can reach.

    Asserted through both implementations rather than by comparing the two lists
    as text: `case` takes globs and `_os_family` takes prefixes, so equal strings
    were never the property. Whether each answers *Windows* is.
    """
    patterns = SHELL_CASE.search(BOOTSTRAP.read_text())
    assert patterns, 'install.sh no longer decides the uv filename from `uname -s`'
    globs = [glob.strip() for glob in patterns.group(1).split('|')]

    monkeypatch.setattr(coordinates.platform, 'system', lambda: reported)

    assert any(fnmatch(reported, glob) for glob in globs), f'install.sh calls {reported} unix'
    assert coordinates.detect().os_family is coordinates.OSFamily.WINDOWS, f'the CLI calls {reported} linux'


def test_the_bootstrap_stages_the_uv_its_platform_carries() -> None:
    """A Windows bundle stages `bin/uv.exe`, so a hardcoded `bin/uv` fails there.

    It failed loudly rather than silently, which is the better of the two — the
    copy would otherwise have put a Linux ELF on PATH under a name Git Bash
    resolves. Pinned because the literal reads perfectly well and nothing else
    would notice its return.
    """
    text = BOOTSTRAP.read_text()

    assert 'bin/uv"' not in text, 'install.sh hardcodes bin/uv, which no Windows bundle carries'
    assert '$BUNDLE/bin/$UV' in text
