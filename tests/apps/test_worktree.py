"""`worktree` gives a session its own index and lands it on main without a PR.

The tool exists because a working tree is shared state: two sessions in one
checkout share the index, the untracked files, and the tree pre-commit assembles
to run hooks against. So the invariants worth asserting are the ones about
*isolation* and about *not destroying work* — that a landed worktree leaves main
linear, that a stale one rebases itself rather than failing, and that no refusal
path ever discards commits the session has not landed anywhere else.

The git history is asserted directly rather than through the tool's own output,
per `standards/testing.md`: a tool reporting that it landed something is
not evidence that origin has it.

Run with: pytest tests/apps/test_worktree.py
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WORKTREE = REPO / 'apps' / 'common' / 'worktree'
SHELL_DIR = REPO / 'configs' / 'common' / '.local' / 'shell'


def git(cwd: Path, *args: str) -> str:
    """Run git and return its stdout, failing the test on a non-zero exit."""
    result = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


@pytest.fixture
def fleet(tmp_path: Path) -> dict[str, Path]:
    """A bare origin with one clone on main, which is the shape every repo has.

    A bare origin is what makes the push in `land` a real push: a test against a
    single clone would prove nothing about a fast-forward onto a branch someone
    else may have moved.
    """
    origin = tmp_path / 'origin.git'
    primary = tmp_path / 'primary'
    roots = tmp_path / 'roots'

    subprocess.run(['git', 'init', '-q', '--bare', str(origin)], check=True)
    subprocess.run(['git', 'clone', '-q', str(origin), str(primary)], check=True, capture_output=True)
    git(primary, 'config', 'user.email', 'test@test')
    git(primary, 'config', 'user.name', 'test')
    (primary / 'f.txt').write_text('base\n')
    git(primary, 'add', 'f.txt')
    git(primary, 'commit', '-qm', 'init')
    git(primary, 'push', '-q', 'origin', 'main')
    git(primary, 'remote', 'set-head', 'origin', '-a')

    return {'origin': origin, 'primary': primary, 'roots': roots}


@pytest.fixture
def run(fleet: dict[str, Path]):
    """Invoke the tool in a given directory, with the repo's own shell libraries."""

    def _run(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        env = {
            'HOME': str(fleet['primary'].parent),
            'PATH': '/usr/bin:/bin:/usr/local/bin',
            'SHELL_DIR': str(SHELL_DIR),
            'WORKTREE_ROOT': str(fleet['roots']),
        }
        return subprocess.run([str(WORKTREE), *args], cwd=cwd, capture_output=True, text=True, env=env)

    return _run


def commit_in(worktree: Path, name: str) -> None:
    (worktree / name).write_text(f'{name}\n')
    git(worktree, 'add', name)
    git(worktree, 'commit', '-qm', f'feat: {name}')


class TestIsolation:
    def test_a_worktree_has_its_own_index(self, fleet, run):
        """The whole reason the tool exists: staging here is invisible there."""
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'

        (fleet['primary'] / 'peer.txt').write_text('peer\n')
        git(fleet['primary'], 'add', 'peer.txt')
        (alpha / 'mine.txt').write_text('mine\n')
        git(alpha, 'add', 'mine.txt')

        assert git(alpha, 'diff', '--cached', '--name-only') == 'mine.txt'
        assert git(fleet['primary'], 'diff', '--cached', '--name-only') == 'peer.txt'

    def test_it_branches_from_origin_not_from_the_local_head(self, fleet, run):
        """A local checkout may be behind or carrying an unpushed commit; neither
        is a base another session should inherit."""
        (fleet['primary'] / 'local.txt').write_text('local\n')
        git(fleet['primary'], 'add', 'local.txt')
        git(fleet['primary'], 'commit', '-qm', 'local only')

        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'

        assert git(alpha, 'rev-parse', 'HEAD') == git(fleet['primary'], 'rev-parse', 'origin/main')


class TestLanding:
    def test_landing_leaves_main_linear(self, fleet, run):
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        commit_in(alpha, 'x')

        result = run(alpha, 'land')

        assert result.returncode == 0, result.stderr
        assert git(fleet['primary'], 'log', '--merges', '--oneline', 'origin/main') == '', (
            'a single commit must stay a single commit — the merge commit is what a PR would have cost'
        )
        assert 'feat: x' in git(fleet['primary'], 'log', '--oneline', 'origin/main')

    def test_a_stale_worktree_rebases_itself_and_still_lands(self, fleet, run):
        """Two sessions landing in sequence is the normal case, not the edge one."""
        run(fleet['primary'], 'new', 'alpha')
        run(fleet['primary'], 'new', 'beta')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        beta = fleet['roots'] / 'primary' / 'beta'
        commit_in(alpha, 'x')
        commit_in(beta, 'y')

        run(alpha, 'land')
        result = run(beta, 'land')

        assert result.returncode == 0, result.stderr
        landed = git(fleet['primary'], 'log', '--oneline', 'origin/main')
        assert 'feat: x' in landed and 'feat: y' in landed
        assert git(fleet['primary'], 'log', '--merges', '--oneline', 'origin/main') == ''

    def test_landing_cleans_up_after_itself(self, fleet, run):
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        commit_in(alpha, 'x')

        run(alpha, 'land')

        assert not alpha.exists()
        assert 'wip/alpha' not in git(fleet['primary'], 'branch', '--list')

    def test_the_primary_checkout_catches_up(self, fleet, run):
        """In dotfiles the checkout is deployed machine state, so a stale primary
        is not cosmetic."""
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        commit_in(alpha, 'x')

        run(alpha, 'land')

        assert (fleet['primary'] / 'x').exists()


class TestNothingIsDestroyed:
    def test_a_conflicted_rebase_keeps_the_work_and_stops(self, fleet, run):
        """A conflict is resolved inside the commit that caused it, so the tool
        must never abort a rebase on its own initiative."""
        run(fleet['primary'], 'new', 'alpha')
        run(fleet['primary'], 'new', 'beta')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        beta = fleet['roots'] / 'primary' / 'beta'
        (alpha / 'f.txt').write_text('alpha wins\n')
        git(alpha, 'commit', '-qam', 'feat: alpha edits f')
        (beta / 'f.txt').write_text('beta wins\n')
        git(beta, 'commit', '-qam', 'feat: beta edits f')

        run(alpha, 'land')
        result = run(beta, 'land')

        assert result.returncode != 0
        assert (beta / 'f.txt').exists(), 'the conflicted tree is the only copy of the resolution in progress'
        assert git(beta, 'rev-list', '--count', 'wip/beta') != '0'

    def test_a_dirty_worktree_is_refused(self, fleet, run):
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        commit_in(alpha, 'x')
        (alpha / 'unfinished.txt').write_text('half\n')

        result = run(alpha, 'land')

        assert result.returncode != 0
        assert 'feat: x' not in git(fleet['primary'], 'log', '--oneline', 'origin/main')

    def test_dropping_unlanded_commits_needs_force(self, fleet, run):
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        commit_in(alpha, 'x')

        refused = run(alpha, 'drop')
        assert refused.returncode != 0
        assert alpha.exists()

        forced = run(alpha, 'drop', '--force')
        assert forced.returncode == 0
        assert not alpha.exists()

    def test_a_busy_primary_checkout_is_left_alone(self, fleet, run):
        """Another session may be working there, and its tree is not ours to move."""
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        commit_in(alpha, 'x')
        (fleet['primary'] / 'f.txt').write_text('someone is editing this\n')

        result = run(alpha, 'land')

        assert result.returncode == 0, 'the landing still happens; only the catch-up is skipped'
        assert (fleet['primary'] / 'f.txt').read_text() == 'someone is editing this\n'


class TestUsage:
    def test_land_outside_a_worktree_is_refused(self, fleet, run):
        result = run(fleet['primary'], 'land')

        assert result.returncode != 0
        assert result.stdout.strip() != '', 'a refusal has to say what was wrong with it'

    def test_landing_nothing_is_refused(self, fleet, run):
        run(fleet['primary'], 'new', 'alpha')

        result = run(fleet['roots'] / 'primary' / 'alpha', 'land')

        assert result.returncode != 0

    def test_new_without_a_slug_is_refused(self, fleet, run):
        result = run(fleet['primary'], 'new')

        assert result.returncode != 0
