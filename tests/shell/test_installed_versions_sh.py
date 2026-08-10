"""installed-versions.sh — what is actually installed, per package manager.

Every phase used to print a success line off an exit code, and `uv tool upgrade`,
`npm update -g` and tpm's `update_plugins` all exit 0 for a no-op — so a no-op, a
real upgrade and a failure were indistinguishable. These are the queries that
replaced that: each reads the installed state so a phase can diff it across the
update. The converged providers need none of them — a `Change` says what moved and
why — so this shrinks as each phase converts.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

import pytest
from shells import REPO
from shells import Shell
from shells import shell_out

LIBRARY = 'install/common/lib/installed-versions.sh'


def query(snippet: str, **environment: str) -> Shell:
    return shell_out(f'source "$1"; {snippet}', str(REPO / LIBRARY), **environment)


def stub(directory: Path, name: str, body: str) -> str:
    """An executable on PATH, so the query runs for real against something that
    answers — rather than the function under test being replaced by one that
    returns the answer."""
    directory.mkdir(exist_ok=True)
    command = directory / name
    command.write_text(f'#!/usr/bin/env bash\n{body}\n')
    command.chmod(command.stat().st_mode | stat.S_IEXEC)
    return f'{directory}{os.pathsep}/usr/bin{os.pathsep}/bin'


def uv_tool(root: Path, tool: str, version: str, commit: str = '') -> None:
    """The layout `uv tool install` leaves behind. uv normalizes `-` and `.` to
    `_` in the dist-info directory name."""
    normalized = tool.replace('-', '_').replace('.', '_')
    dist_info = root / tool / 'lib' / 'python3.13' / 'site-packages' / f'{normalized}-{version}.dist-info'
    dist_info.mkdir(parents=True)
    if commit:
        direct_url = {'url': f'https://example.com/{tool}', 'vcs_info': {'vcs': 'git', 'commit_id': commit}}
        (dist_info / 'direct_url.json').write_text(json.dumps(direct_url))


def uv_receipt(root: Path, tool: str, git_url: str) -> None:
    (root / tool).mkdir(parents=True, exist_ok=True)
    (root / tool / 'uv-receipt.toml').write_text(
        f'[tool]\nrequirements = [{{ name = "{tool}", git = "{git_url}" }}]\n'
        f'entrypoints = [\n    {{ name = "{tool}", install-path = "/tmp/{tool}", from = "{tool}" }},\n]\n'
    )


def checkout(directory: Path, content: str) -> str:
    """A git checkout with one commit, returning its short HEAD.

    The inherited git environment is scrubbed. pre-commit exports GIT_INDEX_FILE
    pointing at its staged index of *this* repo, and `-C` does not override it —
    so `git add` built a tree from that index inside a throwaway object store and
    died on blobs it has never seen. It passed standalone and failed only under
    the commit hook.
    """
    directory.mkdir(parents=True)
    (directory / 'file').write_text(content)
    clean = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}

    def git(*arguments: str) -> str:
        done = subprocess.run(['git', '-C', str(directory), *arguments], capture_output=True, text=True, env=clean, check=True)
        return done.stdout.strip()

    git('init', '--quiet')
    git('config', 'user.email', 'test@example.com')
    git('config', 'user.name', 'Test')
    git('add', 'file')
    git('commit', '--quiet', '-m', content)
    return git('rev-parse', '--short', 'HEAD')


def test_a_uv_tool_reports_its_version(tmp_path: Path) -> None:
    uv_tool(tmp_path, 'codespell', '2.4.3')

    assert query('uv_tool_installed_ref codespell', UV_TOOL_DIR=str(tmp_path)).stdout.strip() == '2.4.3'


def test_a_git_installed_uv_tool_carries_its_commit(tmp_path: Path) -> None:
    """Without the commit, two builds of the same version read as unchanged."""
    uv_tool(tmp_path, 'indy', '0.1.0', '852933d3fbaa0ac3aa1f1024c701ccf5e28e2b25')

    assert query('uv_tool_installed_ref indy', UV_TOOL_DIR=str(tmp_path)).stdout.strip() == '0.1.0 (852933d3fbaa)'


def test_a_rebuilt_git_tool_reads_as_changed(tmp_path: Path) -> None:
    uv_tool(tmp_path / 'before', 'indy', '0.1.0', '852933d3fbaa0ac3aa1f1024c701ccf5e28e2b25')
    uv_tool(tmp_path / 'after', 'indy', '0.1.0', 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb')

    before = query('uv_tool_installed_ref indy', UV_TOOL_DIR=str(tmp_path / 'before'))
    after = query('uv_tool_installed_ref indy', UV_TOOL_DIR=str(tmp_path / 'after'))

    assert before.stdout != after.stdout


def test_a_normalized_dist_info_name_is_still_found(tmp_path: Path) -> None:
    uv_tool(tmp_path, 'keymap-align', '0.1.0', '3e42d3960257000000000000000000000000000f')

    assert query('uv_tool_installed_ref keymap-align', UV_TOOL_DIR=str(tmp_path)).stdout.strip() == '0.1.0 (3e42d3960257)'


def test_an_absent_uv_tool_reports_nothing_rather_than_a_version(tmp_path: Path) -> None:
    result = query('uv_tool_installed_ref nonexistent', UV_TOOL_DIR=str(tmp_path))

    assert not result.ok
    assert result.stdout == ''


def test_an_uninstalled_uv_tool_is_not_treated_as_installed(tmp_path: Path) -> None:
    (tmp_path / 'present').mkdir()

    assert query('uv_tool_is_installed present', UV_TOOL_DIR=str(tmp_path)).ok
    assert not query('uv_tool_is_installed absent', UV_TOOL_DIR=str(tmp_path)).ok


@pytest.mark.parametrize(
    'url',
    [
        'https://github.com/datapointchris/syncer.git?rev=v6.0.0',
        'https://github.com/datapointchris/syncer.git?subdirectory=cli&rev=v6.0.0',
    ],
)
def test_the_pinned_rev_is_read_wherever_it_sits_in_the_url(tmp_path: Path, url: str) -> None:
    """The pin, not the installed version, decides whether `uv tool upgrade` can
    move a git-installed tool at all: a pinned tag re-resolves to the same commit
    and exits 0, which is how syncer was reported current eight releases behind."""
    uv_receipt(tmp_path, 'syncer', url)

    assert query('uv_tool_pinned_rev syncer', UV_TOOL_DIR=str(tmp_path)).stdout.strip() == 'v6.0.0'


def test_a_branch_install_is_unpinned_rather_than_an_error(tmp_path: Path) -> None:
    uv_receipt(tmp_path, 'relate', 'https://github.com/datapointchris/relate.git')

    result = query('uv_tool_pinned_rev relate', UV_TOOL_DIR=str(tmp_path))

    assert result.ok
    assert result.stdout.strip() == ''


def test_a_tool_with_no_receipt_fails(tmp_path: Path) -> None:
    result = query('uv_tool_pinned_rev nonexistent', UV_TOOL_DIR=str(tmp_path))

    assert not result.ok
    assert result.stdout == ''


def test_npm_globals_come_out_as_sorted_name_version_pairs(tmp_path: Path) -> None:
    """A package whose entry carries no version is reported as unknown rather than
    dropped, so it still shows up in the diff."""
    listing = json.dumps({'dependencies': {'prettier': {'version': '3.9.6'}, 'eslint': {'version': '10.8.0'}, 'broken': {}}})
    path = stub(tmp_path / 'bin', 'npm', f"echo '{listing}'")

    result = query('npm_global_versions', PATH=path)

    assert result.stdout.splitlines() == ['broken unknown', 'eslint 10.8.0', 'prettier 3.9.6']


def test_a_checkout_reports_its_short_head(tmp_path: Path) -> None:
    commit = checkout(tmp_path / 'plugin', 'one')

    assert query(f'git_checkout_commit "{tmp_path / "plugin"}"').stdout.strip() == commit


def test_a_directory_that_is_not_a_checkout_reports_nothing(tmp_path: Path) -> None:
    (tmp_path / 'plain').mkdir()

    result = query(f'git_checkout_commit "{tmp_path / "plain"}"')

    assert not result.ok
    assert result.stdout == ''


def test_a_snapshot_is_one_sorted_line_per_checkout(tmp_path: Path) -> None:
    plugins = tmp_path / 'plugins'
    yank = checkout(plugins / 'tmux-yank', 'yank')
    resurrect = checkout(plugins / 'tmux-resurrect', 'resurrect')
    (plugins / 'not-a-checkout').mkdir()

    result = query(f'git_checkouts_snapshot "{plugins}"')

    assert result.stdout.splitlines() == [f'tmux-resurrect {resurrect}', f'tmux-yank {yank}']


def test_a_snapshot_of_a_directory_that_is_not_there_fails(tmp_path: Path) -> None:
    assert not query(f'git_checkouts_snapshot "{tmp_path / "absent"}"').ok
