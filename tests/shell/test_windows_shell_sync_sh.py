"""sync-windows-shell.sh — staging the Git Bash tree, and loading it.

The Windows shell tree is assembled on WSL and only ever executed by Git Bash on
Windows, so a fault in it surfaces days later, on the one machine with no working
shell left to debug from. Both halves therefore run for real here, on any
platform: the staging and `.bashrc` generation are the script's own functions,
and the loading is a real `bash --norc --noprofile` against the generated tree.

Git Bash is not a machine this repo deploys to and has no coordinates, so the
files that are overlay-keyed on the fleet arrive as siblings in one directory and
the load order is a literal list rather than something derived.
"""

from __future__ import annotations

import dataclasses as dc
from pathlib import Path

import pytest
from shells import REPO
from shells import Shell
from shells import shell_out

SCRIPT = str(REPO / 'install' / 'wsl' / 'sync-windows-shell.sh')

LOCAL_OVERLAY = 'machine-local-marker() { echo local-loaded; }\n'
"""Stands in for the deployed ~/.local/shell/local.sh a work box would have. It
exists nowhere in the repo by design — it holds employer hostnames and the like."""


@dc.dataclass(frozen=True, slots=True)
class Windows:
    home: Path

    @property
    def staged(self) -> Path:
        return self.home / '.local' / 'shell'

    @property
    def bashrc(self) -> Path:
        return self.home / '.bashrc'


def sync(home: Path, snippet: str, *args: str, **environment: str) -> Shell:
    """Run one of the script's functions. Sourcing runs neither `main` nor the WSL
    detection, which is what lets these run anywhere."""
    return shell_out(f'source "$1"; {snippet}', SCRIPT, *args, HOME=str(home), DOTFILES_DIR=str(REPO), **environment)


def shell_files() -> list[str]:
    return shell_out('source "$1"; printf "%s\\n" "${SHELL_FILES[@]}"', SCRIPT, DOTFILES_DIR=str(REPO)).stdout.split()


@pytest.fixture
def windows(tmp_path: Path) -> Windows:
    overlay = tmp_path / 'local-src.sh'
    overlay.write_text(LOCAL_OVERLAY)
    home = tmp_path / 'win-home'

    result = sync(
        home,
        'stage_shell_files "$2" >/dev/null; stage_local_file "$2" "$3" >/dev/null; write_bashrc "$4"',
        str(home / '.local' / 'shell'),
        str(overlay),
        str(home),
    )
    assert result.ok, result.stderr

    return Windows(home)


def load(windows: Windows, probe: str, **environment: str) -> Shell:
    """Load the generated .bashrc and then run `probe`.

    A file rather than `bash -c`, so the probe can name $HOME and the palette
    variables literally, the way Git Bash would.
    """
    script = windows.home / 'probe.sh'
    script.write_text(f'source "$HOME/.bashrc"\n{probe}')
    return shell_out('bash --norc --noprofile "$1"', str(script), HOME=str(windows.home), **environment)


@pytest.mark.parametrize('name', shell_files())
def test_every_file_in_the_load_order_is_staged_and_parses_as_bash(windows: Windows, name: str) -> None:
    assert (windows.staged / name).is_file()
    assert shell_out('bash -n "$1"', str(windows.staged / name)).ok


def test_the_generated_bashrc_parses_and_loads_without_error(windows: Windows) -> None:
    assert shell_out('bash -n "$1"', str(windows.bashrc)).ok

    result = load(windows, 'echo loaded')

    assert result.ok
    assert 'loaded' in result.stdout
    assert 'failed to load' not in result.stderr
    assert 'No such file' not in result.stderr


def test_the_loaded_shell_has_the_palette_the_helpers_and_the_aliases(windows: Windows) -> None:
    """FORCE_COLOR because the probe's stdout is a pipe, so the gate in colors.sh
    would blank the palette and the assertion would pass on an empty string."""
    result = load(windows, 'declare -F print_success >/dev/null || exit 1\n[[ -n "$COLOR_RED" ]] || exit 1\nalias open\n', FORCE_COLOR='1')

    assert result.ok
    assert 'start' in result.stdout


def test_the_windows_override_is_ordered_after_the_shared_files(windows: Windows) -> None:
    """So its overrides win rather than being overwritten by the shared copy."""
    order = shell_files()

    assert order.index('windows.sh') > order.index('aliases.sh')


def test_a_broken_file_costs_only_itself(windows: Windows) -> None:
    """The regression the whole layout exists for: a syntax error used to be fatal
    to everything after it, because the files were concatenated into one."""
    with (windows.staged / 'functions.sh').open('a') as broken:
        broken.write('if true; then\n')

    result = load(windows, 'declare -F print_success >/dev/null || exit 1\nalias open\n')

    assert result.ok
    assert 'functions.sh failed to load' in result.stderr
    assert 'start' in result.stdout


def test_a_missing_file_is_skipped_rather_than_fatal(windows: Windows) -> None:
    (windows.staged / 'wsl.sh').unlink()

    result = load(windows, 'echo survived')

    assert result.ok
    assert 'survived' in result.stdout
    assert 'No such file' not in result.stderr


def test_the_machine_local_overlay_is_staged_and_loads(windows: Windows) -> None:
    assert shell_out('bash -n "$1"', str(windows.staged / 'local.sh')).ok

    result = load(windows, 'declare -F machine-local-marker >/dev/null || exit 1\nmachine-local-marker\n')

    assert result.ok
    assert 'local-loaded' in result.stdout


def test_the_overlay_loads_after_the_platform_files_it_builds_on(windows: Windows) -> None:
    """The work box's aws-login reads $winchris, exported by wsl.sh, so the overlay
    has to be sourced last rather than anywhere in the file list."""
    lines = windows.bashrc.read_text().splitlines()
    overlay = next(number for number, line in enumerate(lines) if 'SHELL_DIR/local.sh' in line)
    files = next(number for number, line in enumerate(lines) if 'unset shell_file SHELL_FILES' in line)

    assert overlay > files


def test_a_machine_with_no_overlay_is_skipped_rather_than_fatal(windows: Windows) -> None:
    """Every machine but the work box, and the work box itself between an install
    and its safekeep restore."""
    (windows.staged / 'local.sh').unlink()

    result = load(windows, 'echo survived')

    assert result.ok
    assert 'survived' in result.stdout
    assert 'No such file' not in result.stderr


def test_staging_is_a_no_op_when_the_source_overlay_does_not_exist(windows: Windows) -> None:
    (windows.staged / 'local.sh').unlink()

    result = sync(windows.home, 'stage_local_file "$2" "$3"', str(windows.staged), str(windows.home / 'absent.sh'))

    assert result.ok
    assert not (windows.staged / 'local.sh').exists()


def test_staging_never_deletes_an_overlay_that_exists_nowhere_else(windows: Windows) -> None:
    """The Windows copy may be the only one left — the repo cannot regenerate it."""
    (windows.staged / 'local.sh').write_text('echo out-of-repo\n')

    sync(windows.home, 'stage_local_file "$2" "$3" >/dev/null', str(windows.staged), str(windows.home / 'absent.sh'))

    assert 'out-of-repo' in (windows.staged / 'local.sh').read_text()


def test_staging_clears_a_combined_sh_left_by_the_old_generator(windows: Windows) -> None:
    (windows.staged / 'combined.sh').touch()

    sync(windows.home, 'stage_shell_files "$2" >/dev/null', str(windows.staged))

    assert not (windows.staged / 'combined.sh').exists()


def test_every_declared_file_has_a_source_in_the_repo(windows: Windows) -> None:
    """Staging warns and carries on for a file it cannot find, so a path that moved
    would otherwise leave Git Bash quietly short one file."""
    result = sync(windows.home, 'stage_shell_files "$2"', str(windows.staged))

    assert 'WARNING' not in result.stdout


def test_the_env_file_is_staged_so_the_windows_side_has_the_machine_values(tmp_path: Path) -> None:
    """$winchris was a literal export until the employee ID left the repo; it now
    resolves from WINDOWS_USER, which lives in ~/.env and nothing else carries."""
    source = tmp_path / 'wsl.env'
    source.write_text('export WINDOWS_USER=600002371\n')
    home = tmp_path / 'win-home'

    result = sync(home, 'stage_env_file "$2" "$3"', str(home), str(source))

    assert result.ok, result.stderr
    assert 'WINDOWS_USER=600002371' in (home / '.env').read_text()


def test_staging_the_env_is_a_no_op_when_there_is_none(tmp_path: Path) -> None:
    home = tmp_path / 'win-home'
    home.mkdir()

    result = sync(home, 'stage_env_file "$2" "$3"', str(home), str(tmp_path / 'absent.env'))

    assert result.ok
    assert not (home / '.env').exists()


def test_a_freshly_synced_tree_reports_no_drift(tmp_path: Path) -> None:
    """The check has to be silent on a converged machine or every apply resyncs."""
    home = tmp_path / 'win-home'

    rendered = sync(home, 'render_windows_home "$2" >/dev/null', str(home))
    assert rendered.ok, rendered.stderr

    drift = sync(home, 'windows_home_drift "$2"', str(home))

    assert drift.ok, drift.stderr
    assert drift.stdout.strip() == ''


def test_drift_names_the_file_that_is_missing_or_behind(tmp_path: Path) -> None:
    home = tmp_path / 'win-home'
    assert sync(home, 'render_windows_home "$2" >/dev/null', str(home)).ok

    (home / '.local' / 'shell' / 'aliases.sh').unlink()
    (home / '.inputrc').write_text('# edited on the Windows side\n')

    drift = sync(home, 'windows_home_drift "$2"', str(home))

    assert 'missing: .local/shell/aliases.sh' in drift.stdout
    assert 'stale: .inputrc' in drift.stdout


def test_a_windows_only_overlay_is_not_drift(tmp_path: Path) -> None:
    """Staging never deletes local.sh or ~/.env, so a Windows copy the WSL side no
    longer has must not read as being behind — it is the only copy left."""
    home = tmp_path / 'win-home'
    assert sync(home, 'render_windows_home "$2" >/dev/null', str(home)).ok
    (home / '.local' / 'shell' / 'local.sh').write_text('echo out-of-repo\n')

    drift = sync(home, 'windows_home_drift "$2"', str(home))

    assert drift.stdout.strip() == ''
