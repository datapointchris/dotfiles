"""Self-update: where the checkout thinks it is, and what a pull invalidates.

Nothing here stubs git. Each test builds a real repository and a real clone of it
under `tmp_path`, and hands the path to `checkout.read` — the seam that function
already has, because this package's own repo root is bound at import and a test
that reached in to move it would be testing the patch rather than the code.

The command itself is exercised through `DOTFILES_DIR`, which is the documented
way to point the whole package at another tree, in a subprocess so that the
import-time binding happens against it. Every commit those tests pull touches a
file that is neither deployed nor a dependency, because the repair paths write to
the machine running the suite.
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

import pytest
from relay import install_spy
from relay import recorded

from dotfiles import checkout
from dotfiles import paths
from dotfiles.commands import manage
from dotfiles.vocabulary import ExitCode

NOW = dt.datetime(2026, 8, 8, 12, 0, tzinfo=dt.UTC)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ['git', '-C', str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, 'GIT_AUTHOR_NAME': 'T', 'GIT_AUTHOR_EMAIL': 't@t', 'GIT_COMMITTER_NAME': 'T', 'GIT_COMMITTER_EMAIL': 't@t'},
    ).stdout.strip()


def commit(repo: Path, name: str, text: str) -> None:
    (repo / name).write_text(text)
    git(repo, 'add', name)
    git(repo, 'commit', '-m', f'add {name}')


@pytest.fixture
def remote(tmp_path: Path) -> Path:
    """The upstream, with one commit on `main`."""
    origin = tmp_path / 'origin'
    origin.mkdir()
    git(origin, 'init', '--quiet', '--initial-branch=main')
    commit(origin, 'README.md', 'first\n')
    return origin


@pytest.fixture
def clone(tmp_path: Path, remote: Path) -> Path:
    """A checkout of it, tracking `origin/main` and nothing fetched since."""
    working = tmp_path / 'clone'
    subprocess.run(['git', 'clone', '--quiet', str(remote), str(working)], check=True)
    return working


# ─────────────────────────────────────────────────────────────────────────────
# Reading the position
# ─────────────────────────────────────────────────────────────────────────────


def test_a_fresh_clone_reports_that_nothing_has_fetched(clone: Path) -> None:
    """`git clone` writes no FETCH_HEAD, so there is no measurement to date.

    Reported rather than smoothed into "up to date", and asked to fetch: this is
    the case where a converged-looking answer means nobody has asked.
    """
    position = checkout.read(clone)
    assert position is not None
    assert position.fetched is None
    assert position.describe(NOW) == ('level with origin/main (nothing has fetched since the clone) — run: dotfiles update')


def test_a_clone_behind_its_upstream_counts_what_it_is_missing(clone: Path, remote: Path) -> None:
    commit(remote, 'second.md', 'second\n')
    commit(remote, 'third.md', 'third\n')
    git(clone, 'fetch', '--quiet')

    position = checkout.read(clone)
    assert position is not None
    assert (position.ahead, position.behind) == (0, 2)
    assert position.upstream == 'origin/main'
    assert 'dotfiles update' in position.describe(NOW)


def test_a_local_commit_reads_as_ahead_rather_than_as_drift(clone: Path) -> None:
    """An unpushed commit is the normal state of a machine being worked on."""
    commit(clone, 'local.md', 'local\n')

    position = checkout.read(clone)
    assert position is not None
    assert (position.ahead, position.behind) == (1, 0)
    assert 'unpushed' in position.describe(NOW)


def test_a_diverged_checkout_reports_both_sides(clone: Path, remote: Path) -> None:
    """Counted from the merge base, so neither side hides the other."""
    commit(remote, 'theirs.md', 'theirs\n')
    commit(clone, 'mine.md', 'mine\n')
    git(clone, 'fetch', '--quiet')

    position = checkout.read(clone)
    assert position is not None
    assert (position.ahead, position.behind) == (1, 1)
    described = position.describe(NOW)
    assert 'ahead' in described and 'behind' in described


def test_a_detached_head_has_no_position_and_says_nothing(clone: Path) -> None:
    """Mid-bisect is somewhere someone meant to be, not a fault to report."""
    git(clone, 'checkout', '--quiet', '--detach', 'HEAD')
    assert checkout.read(clone) is None


def test_the_age_dates_the_last_look_not_the_last_change(clone: Path) -> None:
    """A fetch that brings nothing still counts as having asked.

    This is why the remote-tracking refs are not the measurement: they move only
    when something new arrives, so a machine that fetches hourly and is up to
    date would read as never having checked.
    """
    git(clone, 'fetch', '--quiet')
    marker = clone / '.git' / 'FETCH_HEAD'
    os.utime(marker, (0, 0))

    stale = checkout.read(clone)
    git(clone, 'fetch', '--quiet')
    fresh = checkout.read(clone)

    assert stale is not None and fresh is not None
    assert stale.fetched is not None and fresh.fetched is not None
    assert fresh.fetched > stale.fetched


# ─────────────────────────────────────────────────────────────────────────────
# What the line says
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ('ahead', 'behind', 'minutes', 'expected'),
    [
        (0, 0, 0, 'level with origin/main (fetched moments ago)'),
        (0, 1, 5, '1 commit behind origin/main (fetched 5 minutes ago) — run: dotfiles update'),
        (0, 3, 90, '3 commits behind origin/main (fetched 1 hour ago) — run: dotfiles update'),
        (2, 0, 60, '2 commits ahead of origin/main, unpushed (fetched 1 hour ago)'),
        (
            2,
            0,
            60 * 24 * 3,
            '2 commits ahead of origin/main, unpushed (fetched 3 days ago) — run: dotfiles update',
        ),
        (1, 1, 60, '1 commit ahead of and 1 commit behind origin/main (fetched 1 hour ago) — run: dotfiles update'),
    ],
)
def test_the_line_names_the_counts_and_its_own_age(ahead: int, behind: int, minutes: int, expected: str) -> None:
    """Singular and plural both, because "1 commits behind" is what makes a
    generated line read as generated and stop being trusted.

    The two unpushed rows differ only in the age of the reading. Ahead-and-not-
    behind is a claim about where the upstream was when someone last looked, so
    at three days it asks for a fetch and at one hour it does not.
    """
    fetched = NOW - dt.timedelta(minutes=minutes)
    assert checkout.Position('origin/main', ahead, behind, fetched).describe(NOW) == expected


# ─────────────────────────────────────────────────────────────────────────────
# What a pull invalidates
# ─────────────────────────────────────────────────────────────────────────────


def test_the_dependency_files_are_paths_this_repo_actually_has() -> None:
    """The bound on editable staleness is a pair of filenames, so a rename would
    silently disable the venv repair rather than fail."""
    for name in manage.DEPENDENCY_FILES:
        assert (paths.REPO_ROOT / name).is_file(), f'{name} no longer exists — the venv would never be rebuilt'


def test_the_deployed_prefixes_are_directories_this_repo_actually_has() -> None:
    for prefix in manage.DEPLOYED_PREFIXES:
        assert (paths.REPO_ROOT / prefix).is_dir(), f'{prefix} no longer exists — a pull would never relink'


def run_update(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """The command in a subprocess, pointed at `repo` by the one variable that
    can move the repo root — it is read at import, so an in-process test cannot."""
    return subprocess.run(
        [sys.executable, '-m', 'dotfiles.main', 'update', *args],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, 'DOTFILES_DIR': str(repo)},
    )


def test_update_pulls_and_names_what_came_in(clone: Path, remote: Path) -> None:
    commit(remote, 'second.md', 'second\n')

    result = run_update(clone)

    assert result.returncode == ExitCode.CONVERGED, result.stderr
    assert '1 commit(s) pulled' in result.stdout
    assert 'add second.md' in result.stdout
    assert (clone / 'second.md').exists()


def test_update_on_a_current_checkout_says_so_and_pulls_nothing(clone: Path) -> None:
    result = run_update(clone)

    assert result.returncode == ExitCode.CONVERGED, result.stderr
    assert 'already up to date' in result.stderr
    assert 'pulled' not in result.stdout


def test_update_refuses_to_merge_a_diverged_checkout(clone: Path, remote: Path) -> None:
    """`--ff-only` is what stops a self-update inventing a merge commit, and the
    local work has to still be there afterwards — this never reaches for `reset`."""
    commit(remote, 'theirs.md', 'theirs\n')
    commit(clone, 'mine.md', 'mine\n')
    head = git(clone, 'rev-parse', 'HEAD')

    result = run_update(clone)

    assert result.returncode != ExitCode.CONVERGED
    assert 'pull refused' in result.stderr
    assert git(clone, 'rev-parse', 'HEAD') == head
    assert (clone / 'mine.md').exists()


def test_update_check_reports_the_position_without_pulling(clone: Path, remote: Path) -> None:
    """The explicit fetch: `check` reads the cache, this is how it gets refreshed."""
    commit(remote, 'second.md', 'second\n')

    result = run_update(clone, '--check')

    assert result.returncode == ExitCode.DRIFT
    assert '1 commit behind origin/main' in result.stdout
    assert not (clone / 'second.md').exists()


# ─────────────────────────────────────────────────────────────────────────────
# The two repairs, which is the half of `update` that changes the machine
#
# Both shell out, and both were unreached: every pull above touches a file that
# is neither deployed nor a dependency, precisely so the repairs stay asleep. A
# spy first on PATH is what lets them run — and `uv tool install --reinstall`
# deletes and recreates the virtualenv this suite is running from, so the
# assertion that the spy recorded the call is also the proof the real one did
# not. `tests/conftest.py`'s `INSTALLING` guard cannot reach here: it patches
# `subprocess` in this process, and the command under test is a child.
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def repairs(fake_bin: Path, tmp_path: Path) -> Path:
    """`dotfiles` and `uv` shadowed by recording spies, and the file they write to."""
    record = tmp_path / 'repairs.jsonl'
    install_spy(fake_bin, record, name='dotfiles')
    install_spy(fake_bin, record, name='uv')
    return record


def deployed_commit(repo: Path, name: str = 'configs/common/.config/x.conf') -> None:
    (repo / name).parent.mkdir(parents=True, exist_ok=True)
    (repo / name).write_text('changed\n')
    git(repo, 'add', name)
    git(repo, 'commit', '-m', f'change {name}')


def test_a_pull_touching_a_deployed_file_rebuilds_the_symlinks(clone: Path, remote: Path, repairs: Path) -> None:
    """A moved file under `configs/` leaves the machine linked to a path that no
    longer exists, and nothing else notices until the program that reads it fails."""
    deployed_commit(remote)

    result = run_update(clone)

    assert result.returncode == ExitCode.CONVERGED, result.stderr
    assert recorded(repairs) == [['symlinks', 'apply']]
    assert 'rebuilding symlinks' in result.stderr


def test_a_pull_touching_nothing_deployed_leaves_the_symlinks_alone(clone: Path, remote: Path, repairs: Path) -> None:
    """The negative half, because a repair that always runs is indistinguishable
    from one that runs when it should."""
    commit(remote, 'notes.md', 'prose\n')

    result = run_update(clone)

    assert result.returncode == ExitCode.CONVERGED, result.stderr
    assert recorded(repairs) == []


def test_a_pull_changing_the_dependency_set_reinstalls_the_tool_venv(clone: Path, remote: Path, repairs: Path) -> None:
    """Code changes never stale an editable install — uv points at the working
    tree. The dependency set is resolved once, so these two files are the whole
    of what a rebuild can be needed for."""
    commit(remote, 'pyproject.toml', '[project]\nname = "x"\n')

    result = run_update(clone)

    assert result.returncode == ExitCode.CONVERGED, result.stderr
    assert recorded(repairs) == [['tool', 'install', '--reinstall', '--editable', str(clone)]]
    assert 'rebuilding the tool venv' in result.stderr


def test_both_repairs_run_in_the_order_the_venv_rebuild_demands(clone: Path, remote: Path, repairs: Path) -> None:
    """The reinstall replaces the virtualenv this interpreter is running from, so
    anything after it never happens. Relinking has to be first."""
    (remote / 'configs' / 'common' / '.config').mkdir(parents=True)
    (remote / 'configs' / 'common' / '.config' / 'x.conf').write_text('changed\n')
    (remote / 'uv.lock').write_text('version = 1\n')
    git(remote, 'add', 'configs', 'uv.lock')
    git(remote, 'commit', '-m', 'change both')

    result = run_update(clone)

    assert result.returncode == ExitCode.CONVERGED, result.stderr
    assert [call[0] for call in recorded(repairs)] == ['symlinks', 'tool']


def test_a_failed_venv_rebuild_exits_issue_rather_than_reporting_success(clone: Path, remote: Path, fake_bin: Path, tmp_path: Path) -> None:
    """`os._exit` skips every handler, so the code it carries is the only answer a
    caller gets — and it is chosen from the reinstall rather than from the pull."""
    record = tmp_path / 'failed.jsonl'
    install_spy(fake_bin, record, name='uv', code=1)
    commit(remote, 'uv.lock', 'version = 1\n')

    result = run_update(clone)

    assert result.returncode == ExitCode.ISSUE
    assert recorded(record) == [['tool', 'install', '--reinstall', '--editable', str(clone)]]


# ─────────────────────────────────────────────────────────────────────────────
# The three refusals
# ─────────────────────────────────────────────────────────────────────────────


def test_update_outside_a_git_repository_refuses_before_pulling(tmp_path: Path, repairs: Path) -> None:
    """`DOTFILES_DIR` naming a directory that is not a checkout, which is what a
    half-finished rebuild leaves behind."""
    bare = tmp_path / 'not-a-repo'
    bare.mkdir()

    result = run_update(bare)

    assert result.returncode != ExitCode.CONVERGED
    assert 'is this a git repository' in result.stderr
    assert recorded(repairs) == [], 'nothing may be repaired on a tree that was never read'


def test_check_reports_an_unreachable_remote_rather_than_a_position(clone: Path) -> None:
    """The fetch is the network call, and a machine that cannot reach the remote
    knows nothing about where it stands — reporting `converged` would be a guess."""
    git(clone, 'remote', 'set-url', 'origin', str(clone / 'nowhere'))

    result = run_update(clone, '--check')

    assert result.returncode == ExitCode.ISSUE
    assert 'could not reach the remote' in result.stderr


def test_check_on_a_checkout_tracking_nothing_says_so_and_converges(clone: Path) -> None:
    """A branch with no upstream is a legitimate state, not a fault: there is
    nothing to be behind."""
    git(clone, 'checkout', '--quiet', '-b', 'local-only')

    result = run_update(clone, '--check')

    assert result.returncode == ExitCode.CONVERGED
    assert 'tracks no upstream branch' in result.stderr
