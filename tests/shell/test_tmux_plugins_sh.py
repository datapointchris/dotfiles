"""tmux-plugins.sh — installing TPM's plugins without touching the live server.

The real installer under the real wrapper against a stubbed HOME, so what these
assert is what a person reads in the failure report on the machine that failed.
TPM itself is stubbed and nothing else is: the stub stands in for the one thing
that would otherwise need a network.

Two regressions are pinned here. tmux-plugins.sh piped TPM into a reader loop
under `set -o pipefail`, so a failing TPM aborted the script at the pipeline and
the reporting branch below it never ran — the diagnosis was lost twice, since the
loop had also re-emitted the output onto a stream the wrapper was not capturing.
And TPM shells out to a bare `tmux`, where `$TMUX` — set whenever the installer
runs from inside a session — outranks TMUX_TMPDIR, so the throwaway install
session and the kill-server that cleans it up both landed on the user's live
server.
"""

from __future__ import annotations

import dataclasses as dc
import shutil
import stat
import sys
from pathlib import Path

import pytest
from shells import REPO
from shells import Shell
from shells import shell_out

pytestmark = pytest.mark.skipif(shutil.which('tmux') is None, reason='tmux is not installed')

INSTALLER = str(REPO / 'install' / 'common' / 'plugins' / 'tmux-plugins.sh')
WRAPPER = str(REPO / 'install' / 'run-installer.sh')


@dc.dataclass(frozen=True, slots=True)
class Tmux:
    home: Path

    @property
    def config(self) -> Path:
        return self.home / '.config' / 'tmux' / 'tmux.conf'

    @property
    def tpm(self) -> Path:
        return self.home / '.config' / 'tmux' / 'plugins' / 'tpm'

    @property
    def log(self) -> str:
        path = self.home / 'failures.log'
        return path.read_text() if path.exists() else ''


@pytest.fixture
def tmux(tmp_path: Path) -> Tmux:
    home = tmp_path / 'home'
    (home / '.config' / 'tmux' / 'plugins' / 'tpm' / 'bin').mkdir(parents=True)
    (home / '.config' / 'tmux' / 'tmux.conf').write_text("set -g @plugin 'tmux-plugins/tmux-yank'\n")
    return Tmux(home)


def stub_tpm(tmux: Tmux, body: str) -> None:
    install_plugins = tmux.tpm / 'bin' / 'install_plugins'
    install_plugins.write_text(f'#!/usr/bin/env bash\n{body}')
    install_plugins.chmod(install_plugins.stat().st_mode | stat.S_IEXEC)


def install(tmux: Tmux, **environment: str) -> Shell:
    return shell_out(
        'source "$1"; run_installer "$2" tmux-plugins',
        WRAPPER,
        INSTALLER,
        DOTFILES_DIR=str(REPO),
        DOTFILES_PYTHON=sys.executable,
        FAILURES_LOG=str(tmux.home / 'failures.log'),
        HOME=str(tmux.home),
        XDG_CONFIG_HOME=str(tmux.home / '.config'),
        **environment,
    )


def test_tpm_is_handed_the_plugin_path_directly_rather_than_through_tmux_conf(tmux: Tmux) -> None:
    stub_tpm(tmux, 'tmux show-environment -g TMUX_PLUGIN_MANAGER_PATH\nexit 0\n')

    result = install(tmux)

    assert result.ok
    assert f'TMUX_PLUGIN_MANAGER_PATH={tmux.tpm.parent}/' in result.stdout + result.stderr


def test_tpm_talks_to_a_throwaway_server_not_the_callers(tmux: Tmux) -> None:
    stub_tpm(tmux, 'tmux list-sessions\nexit 0\n')

    result = install(tmux)

    assert result.ok
    assert 'dotfiles-tpm-install' in result.stdout + result.stderr


def test_the_isolation_holds_even_when_run_from_inside_a_session(tmux: Tmux) -> None:
    """A bogus $TMUX is safe and proves the unset happened: were it honoured, tmux
    would fail to reach that socket entirely."""
    stub_tpm(tmux, 'echo "TMUX=[${TMUX:-unset}]"\ntmux list-sessions\nexit 0\n')

    result = install(tmux, TMUX='/nonexistent/socket,1,0', TMUX_PANE='%99')

    assert result.ok
    reported = result.stdout + result.stderr
    assert 'TMUX=[unset]' in reported
    assert 'dotfiles-tpm-install' in reported


def test_tpms_own_error_reaches_the_failure_report(tmux: Tmux) -> None:
    stub_tpm(
        tmux,
        'echo "unknown variable: TMUX_PLUGIN_MANAGER_PATH" >&2\n'
        'echo "FATAL: Tmux Plugin Manager not configured in tmux.conf" >&2\nexit 1\n',
    )

    install(tmux)

    assert 'tmux-plugins' in tmux.log
    assert 'TPM plugin installation failed' in tmux.log
    assert 'FATAL: Tmux Plugin Manager not configured in tmux.conf' in tmux.log


def test_the_report_carries_the_tmux_version_and_config_path(tmux: Tmux) -> None:
    """Read on another machine days later, "TPM failed" is undiagnosable without
    which tmux and which config it was reading."""
    stub_tpm(tmux, 'exit 1\n')

    install(tmux)

    assert 'tmux: tmux ' in tmux.log
    assert f'{tmux.config} (present)' in tmux.log


def test_a_failing_tpm_does_not_abort_before_reporting(tmux: Tmux) -> None:
    """The script's own warning is what proves it ran past the pipeline that used
    to kill it."""
    stub_tpm(tmux, 'echo "Aborting." >&2\nexit 1\n')

    result = install(tmux)

    assert not result.ok
    assert 'Tmux plugin installation failed' in result.stdout + result.stderr


def test_tpm_output_on_stdout_still_reaches_the_report(tmux: Tmux) -> None:
    """TPM writes its progress, and its failures, to stdout. This failed for as
    long as the wrapper captured only stderr, and it is what stops that split
    being reintroduced."""
    stub_tpm(tmux, 'echo "fatal: unable to access github.com: SSL certificate problem"\nexit 128\n')

    install(tmux)

    assert 'SSL certificate problem' in tmux.log
    assert 'exit 128' in tmux.log


def test_a_missing_tpm_is_reported_rather_than_crashed_on(tmux: Tmux) -> None:
    shutil.rmtree(tmux.tpm)

    install(tmux)

    assert 'TPM not found' in tmux.log


def test_a_missing_tmux_conf_is_reported_rather_than_silently_installing_nothing(tmux: Tmux) -> None:
    stub_tpm(tmux, 'exit 0\n')
    tmux.config.unlink()

    result = install(tmux)

    assert not result.ok
    assert 'no plugin list to read' in tmux.log


def test_success_writes_no_failure_entry(tmux: Tmux) -> None:
    stub_tpm(tmux, 'echo \'Already installed "tpm"\'\necho \'Installing "tmux-yank"\'\nexit 0\n')

    result = install(tmux)

    assert result.ok
    assert 'Installing tmux-yank...' in result.stdout + result.stderr
    assert tmux.log == ''
