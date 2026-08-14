"""The two plugin managers: what can be asked of each, and how each is run.

A real `tmux` with TPM stubbed, because the stub stands in for the one thing that
would otherwise need a network, and the server isolation is the whole point — it
cannot be asserted against a fake tmux.

Two regressions are pinned here. TPM shells out to a bare
`tmux`, where `$TMUX` — set whenever the installer runs from inside a session —
outranks `TMUX_TMPDIR`, so the throwaway session and the `kill-server` that cleans
it up both landed on the user's live server. And TPM writes its progress *and its
failures* to stdout, which was lost for as long as only stderr was captured.

The lazy half is the lockfile, and what makes it a different kind of test: there
is no invocation to exercise without installing fifty plugins, which is exactly
why the provider reads lazy's record instead of asking lazy.
"""

from __future__ import annotations

import dataclasses as dc
import json
import shutil
import stat
from pathlib import Path

import pytest

from dotfiles.providers import Kind
from dotfiles.providers import pluginsync

needs_tmux = pytest.mark.interpreter('tmux')
"""The same marker `tests/shell` uses, so the same gate covers this.

A plain `skipif` would be silently skipped on a CI runner with no tmux, which is
the exact failure `--require-interpreters` exists to stop — and these are the only
tests that drive a real interpreter from outside `tests/shell`.
"""


@dc.dataclass(frozen=True, slots=True)
class Tmux:
    home: Path

    @property
    def config(self) -> Path:
        return self.home / '.config' / 'tmux' / 'tmux.conf'

    @property
    def plugins(self) -> Path:
        return self.home / '.config' / 'tmux' / 'plugins'

    def stub_tpm(self, body: str) -> None:
        installer = self.plugins / 'tpm' / 'bin' / 'install_plugins'
        installer.write_text(f'#!/usr/bin/env bash\n{body}')
        installer.chmod(installer.stat().st_mode | stat.S_IEXEC)

    def sync(self):
        return pluginsync.sync_tmux(self.home, self.plugins)


@pytest.fixture
def tmux(tmp_path: Path) -> Tmux:
    home = tmp_path / 'home'
    (home / '.config' / 'tmux' / 'plugins' / 'tpm' / 'bin').mkdir(parents=True)
    (home / '.config' / 'tmux' / 'tmux.conf').write_text("set -g @plugin 'tmux-plugins/tmux-yank'\n")
    return Tmux(home)


# ─────────────────────────────────────────────────────────────────────────────
# Reading the list TPM reads
# ─────────────────────────────────────────────────────────────────────────────


def test_every_spelling_of_a_plugin_line_is_read(tmux: Tmux) -> None:
    """`set` and `set-option`, single quotes, double quotes and none — TPM's awk
    takes field four of any of them, so anything it would install must appear."""
    tmux.config.write_text(
        "set -g @plugin 'tmux-plugins/tmux-yank'\n"
        'set-option -g @plugin "tmux-plugins/tmux-cpu"\n'
        '  set -g @plugin tmux-plugins/tmux-sidebar\n'
        '# set -g @plugin tmux-plugins/commented-out\n'
    )

    assert pluginsync.declared(tmux.home) == ('tmux-yank', 'tmux-cpu', 'tmux-sidebar')


def test_a_plugin_named_by_url_lands_under_the_name_tpm_gives_it(tmux: Tmux) -> None:
    """`plugin_name_helper` is basename minus `.git`, so the three spellings of one
    plugin are one directory and must not read as three."""
    tmux.config.write_text(
        "set -g @plugin 'git://github.com/tmux-plugins/tmux-yank.git'\n"
        "set -g @plugin 'tmux-plugins/tmux-yank.git'\n"
        "set -g @plugin 'tmux-plugins/tmux-yank'\n"
    )

    assert pluginsync.declared(tmux.home) == ('tmux-yank',)


def test_a_sourced_file_contributes_its_plugins(tmux: Tmux) -> None:
    """TPM reads one level of sourced files, so a config that splits its plugin
    list across two files must not report the second one's as uninstalled."""
    (tmux.home / '.config' / 'tmux' / 'extra.conf').write_text("set -g @plugin 'tmux-plugins/tmux-cpu'\n")
    tmux.config.write_text("set -g @plugin 'tmux-plugins/tmux-yank'\nsource-file ~/.config/tmux/extra.conf\n")

    assert pluginsync.declared(tmux.home) == ('tmux-yank', 'tmux-cpu')


def test_an_absent_config_declares_nothing_rather_than_raising(tmux: Tmux) -> None:
    """The ordinary state of a machine whose symlink pass has not run."""
    tmux.config.unlink()

    assert pluginsync.declared(tmux.home) == ()


def test_a_half_cloned_plugin_counts_as_uninstalled(tmux: Tmux) -> None:
    """TPM's own test is `[ -d ] && cd && git remote`, so an interrupted clone
    leaves a directory that satisfies the first half and nothing else."""
    (tmux.plugins / 'tmux-yank').mkdir()
    (tmux.plugins / 'tmux-cpu' / '.git').mkdir(parents=True)

    assert pluginsync.uninstalled(('tmux-yank', 'tmux-cpu'), tmux.plugins) == ('tmux-yank',)


# ─────────────────────────────────────────────────────────────────────────────
# Running TPM
# ─────────────────────────────────────────────────────────────────────────────


@needs_tmux
def test_tpm_is_handed_the_plugin_path_directly_rather_than_through_tmux_conf(tmux: Tmux, capsys) -> None:
    """Relying on the tpm bootstrap line to have set it is what broke: a server
    running from before the config was linked leaves it unset, and TPM aborts
    naming the one thing that is usually fine."""
    tmux.stub_tpm('tmux show-environment -g TMUX_PLUGIN_MANAGER_PATH\nexit 0\n')

    assert tmux.sync().ok
    assert f'TMUX_PLUGIN_MANAGER_PATH={tmux.plugins}/' in capsys.readouterr().err


@needs_tmux
def test_tpm_talks_to_a_throwaway_server_not_the_callers(tmux: Tmux, capsys) -> None:
    tmux.stub_tpm('tmux list-sessions\nexit 0\n')

    assert tmux.sync().ok
    assert pluginsync.SESSION in capsys.readouterr().err


@needs_tmux
def test_the_isolation_holds_even_when_run_from_inside_a_session(tmux: Tmux, monkeypatch, capsys) -> None:
    """A bogus `$TMUX` is safe and proves the unset happened: were it honoured,
    tmux would fail to reach that socket entirely.

    `env` cannot express this — it merges over the environment, so the most it can
    do is blank the variable — which is why `effects.run` grew `unset`.
    """
    monkeypatch.setenv('TMUX', '/nonexistent/socket,1,0')
    monkeypatch.setenv('TMUX_PANE', '%99')
    tmux.stub_tpm('echo "TMUX=[${TMUX:-unset}]"\ntmux list-sessions\nexit 0\n')

    assert tmux.sync().ok
    reported = capsys.readouterr().err
    assert 'TMUX=[unset]' in reported
    assert pluginsync.SESSION in reported


@needs_tmux
def test_tpms_own_error_reaches_the_outcome(tmux: Tmux) -> None:
    tmux.stub_tpm(
        'echo "unknown variable: TMUX_PLUGIN_MANAGER_PATH" >&2\necho "FATAL: Tmux Plugin Manager not configured in tmux.conf" >&2\nexit 1\n'
    )

    result = tmux.sync()

    assert not result.ok
    assert result.kind is Kind.COMMAND_FAILED
    assert 'TPM plugin installation failed' in result.detail
    assert 'FATAL: Tmux Plugin Manager not configured in tmux.conf' in result.detail


@needs_tmux
def test_tpm_output_on_stdout_still_reaches_the_outcome(tmux: Tmux) -> None:
    """TPM writes its progress, and its failures, to stdout. This failed for as
    long as the wrapper captured only stderr, and it is what stops that split
    being reintroduced."""
    tmux.stub_tpm('echo "fatal: unable to access github.com: SSL certificate problem"\nexit 128\n')

    result = tmux.sync()

    assert result.kind is Kind.COMMAND_FAILED
    assert 'SSL certificate problem' in result.detail
    assert 'exit 128' in result.detail


@needs_tmux
def test_the_failure_carries_the_tmux_version_and_config_path(tmux: Tmux) -> None:
    """Read on another machine days later, "TPM failed" is undiagnosable without
    which tmux and which config it was reading."""
    tmux.stub_tpm('exit 1\n')

    result = tmux.sync()

    assert result.kind is Kind.COMMAND_FAILED
    assert 'tmux: tmux ' in result.detail
    assert f'{tmux.config} (present)' in result.detail


@needs_tmux
def test_success_says_so_and_shows_what_tpm_said_bar_its_own_line(tmux: Tmux, capsys) -> None:
    """tpm.sh logs its own bootstrap, so echoing TPM's line about it reports one
    event twice."""
    tmux.stub_tpm('echo \'Already installed "tpm"\'\necho \'Installing "tmux-yank"\'\nexit 0\n')

    result = tmux.sync()
    shown = capsys.readouterr().err

    assert result.ok
    assert 'Installing "tmux-yank"' in shown
    assert 'Already installed "tpm"' not in shown


@needs_tmux
def test_a_missing_tpm_is_reported_rather_than_crashed_on(tmux: Tmux) -> None:
    """Marked, because "no tmux" is answered before this and outranks it: without
    the binary there is nothing for TPM to install into either way."""
    shutil.rmtree(tmux.plugins / 'tpm')

    result = tmux.sync()

    assert not result.ok
    assert result.kind is Kind.PREREQUISITE_MISSING
    assert 'TPM is not at' in result.detail


@needs_tmux
def test_a_missing_tmux_conf_is_reported_rather_than_silently_installing_nothing(tmux: Tmux) -> None:
    """Without it TPM installs nothing and exits 0 — a success that deploys no
    plugins."""
    tmux.stub_tpm('exit 0\n')
    tmux.config.unlink()

    result = tmux.sync()

    assert not result.ok
    assert result.kind is Kind.PREREQUISITE_MISSING
    assert 'no plugin list to read' in result.detail


# ─────────────────────────────────────────────────────────────────────────────
# lazy.nvim, which is read rather than asked
# ─────────────────────────────────────────────────────────────────────────────


def lockfile(home: Path, plugins: dict[str, dict[str, str]]) -> None:
    path = home / pluginsync.LAZY_LOCK
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plugins))


def test_a_machine_where_lazy_never_ran_has_no_record(tmp_path: Path) -> None:
    """None rather than an empty tuple, and the distinction is the whole point: a
    fresh install is the case the sync exists for."""
    assert pluginsync.recorded(tmp_path) is None


def test_an_unreadable_lockfile_reads_as_no_record_rather_than_raising(tmp_path: Path) -> None:
    """lazy rewrites this file, so a run interrupted mid-write leaves half of one —
    and reporting that as a crash tells nobody anything a re-sync would not fix."""
    (tmp_path / pluginsync.LAZY_LOCK).parent.mkdir(parents=True)
    (tmp_path / pluginsync.LAZY_LOCK).write_text('{"gitsigns.nvim": {"branch"')

    assert pluginsync.recorded(tmp_path) is None


def test_the_record_is_every_plugin_lazy_wrote_down(tmp_path: Path) -> None:
    lockfile(tmp_path, {'gitsigns.nvim': {'commit': 'a'}, 'blink.cmp': {'commit': 'b'}})

    assert pluginsync.recorded(tmp_path) == ('blink.cmp', 'gitsigns.nvim')


def test_a_recorded_plugin_missing_from_disk_is_unsynced(tmp_path: Path) -> None:
    lockfile(tmp_path, {'gitsigns.nvim': {'commit': 'a'}, 'blink.cmp': {'commit': 'b'}})
    (tmp_path / pluginsync.LAZY_STATE / 'blink.cmp').mkdir(parents=True)

    assert pluginsync.unsynced(tmp_path) == ('gitsigns.nvim',)


def test_nothing_is_unsynced_where_there_is_no_record(tmp_path: Path) -> None:
    """Absent is answered by `recorded`, and answering it twice as "everything is
    missing" would make the row say a number it did not measure."""
    assert pluginsync.unsynced(tmp_path) == ()


def test_a_long_list_is_named_in_part_and_counted_in_full(tmp_path: Path) -> None:
    """A fresh machine is missing every plugin lazy knows about."""
    assert pluginsync.listed(('a', 'b', 'c', 'd', 'e', 'f')) == 'a, b, c, d and 2 more'
    assert pluginsync.listed(('a', 'b')) == 'a, b'
