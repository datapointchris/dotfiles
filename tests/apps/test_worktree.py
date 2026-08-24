"""`worktree` gives a session its own index and lands it on main without a PR.

The tool exists because a working tree is shared state: two sessions in one
checkout share the index, the untracked files, and the tree pre-commit assembles
to run hooks against. So the invariants worth asserting are the ones about
*isolation* and about *not destroying work* — that a landed worktree leaves main
linear, that a stale one rebases itself rather than failing, and that no refusal
path ever discards commits the session has not landed anywhere else.

The git history is asserted directly rather than through the tool's own output,
per `standards/testing.md`: a tool reporting that it landed something is not
evidence that origin has it.

The reads have a second axis. `list`, `show` and `choose` answer for every repo on
the machine, so the fixture builds two — a single-repo fixture cannot tell "every
repo" from "the repo I happen to be in", and that is the whole claim those three
commands make. `claude-sessions` and `fzf` are shadowed on PATH rather than
reimplemented: the session registry and the picker each have one owner, and this
file only decides what a row says and where the path goes.

Run with: pytest tests/apps/test_worktree.py
"""

from __future__ import annotations

import json
import os
import re
import shlex
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
WORKTREE = REPO / 'apps' / 'common' / 'worktree'

# `worktree` runs under `uv run --script`, and the fixtures below give it a
# throwaway HOME so nothing reads real config. uv's cache hangs off HOME, so
# without this every test resolves and downloads its dependencies again — and on
# a machine with no network, fails. Read at import, while HOME is still real.
UV_CACHE = os.environ.get('UV_CACHE_DIR') or str(Path.home() / '.cache' / 'uv')

# The em dash in `show` is non-ASCII, so an env without a UTF-8 locale measures
# escaping rather than the line. Named per platform because there is no portable
# spelling: glibc has C.UTF-8 built in and macOS does not.
UTF8_LOCALE = 'en_US.UTF-8' if sys.platform == 'darwin' else 'C.UTF-8'

ANSI = re.compile(r'\x1b\[[0-9;]*m')


def git(cwd: Path, *args: str) -> str:
    """Run git and return its stdout, failing the test on a non-zero exit."""
    result = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def make_repo(root: Path, name: str) -> Path:
    """A bare origin with one clone on main, which is the shape every repo has.

    A bare origin is what makes the push in `land` a real push: a test against a
    single clone would prove nothing about a fast-forward onto a branch someone
    else may have moved.

    `-b main` names the branch rather than inheriting `init.defaultBranch`, which
    is a fact about the machine and not about the fixture. Cloning an empty bare
    repo takes the local branch from the remote's HEAD, so without it the initial
    commit lands on `master` and `push origin main` fails with "src refspec main
    does not match any" — green on any box whose gitconfig sets it, red on every
    CI runner.
    """
    origin = root / f'{name}.git'
    clone = root / name

    subprocess.run(['git', 'init', '-q', '--bare', '-b', 'main', str(origin)], check=True)
    subprocess.run(['git', 'clone', '-q', str(origin), str(clone)], check=True, capture_output=True)
    git(clone, 'config', 'user.email', 'test@test')
    git(clone, 'config', 'user.name', 'test')
    (clone / 'f.txt').write_text('base\n')
    git(clone, 'add', 'f.txt')
    git(clone, 'commit', '-qm', 'init')
    git(clone, 'push', '-q', 'origin', 'main')
    git(clone, 'remote', 'set-head', 'origin', '-a')
    return clone


@pytest.fixture
def fleet(tmp_path: Path) -> dict[str, Path]:
    """Two repos on one machine, and the root every worktree of either lands in."""
    return {
        'primary': make_repo(tmp_path, 'primary'),
        'other': make_repo(tmp_path, 'other'),
        'roots': tmp_path / 'roots',
    }


@pytest.fixture
def bin_dir(tmp_path: Path) -> Path:
    """A directory that leads PATH, so anything written into it shadows the real
    tool of that name.

    It starts with a `claude-sessions` reporting an empty machine. Without one the
    real binary answers, and what it says is whichever sessions happen to be running
    — so a suite that gates on sessions would pass on this laptop and, where the tool
    is not installed at all, take a different branch on CI.
    """
    path = tmp_path / 'bin'
    path.mkdir()
    stub_sessions(path)
    return path


def write_stub(bin_dir: Path, name: str, body: str) -> None:
    stub = bin_dir / name
    stub.write_text(f'#!/bin/sh\n{body}\n')
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)


def stub_sessions(bin_dir: Path, *sessions: dict[str, Any]) -> None:
    write_stub(bin_dir, 'claude-sessions', f"cat <<'JSON'\n{json.dumps(list(sessions))}\nJSON")


def session(name: str, cwd: Path, status: str = 'idle', tmux: str | None = None) -> dict[str, Any]:
    return {'name': name, 'sessionId': 'abc', 'status': status, 'waiting': None, 'cwd': str(cwd), 'tmux': tmux, 'pid': 1}


@pytest.fixture
def run(tmp_path: Path, fleet: dict[str, Path], bin_dir: Path):
    """Invoke the tool in a given directory, on a machine made of the fixture.

    HOME is the fixture root so `~`-relative paths in the listing are the
    fixture's, and PATH leads with the stub directory so a shadowed
    `claude-sessions` or `fzf` is the one that answers.

    stdin is /dev/null so the suite is the same run whether or not a terminal
    launched it. capture_output leaves stdin inherited, and `sweep` asks a y/N on a
    terminal — under `pytest` from a shell that would block forever, and under CI it
    would not, so the two would be testing different code.
    """

    def _run(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        env = {
            'HOME': str(tmp_path),
            'PATH': f'{bin_dir}:{os.environ["PATH"]}',
            'LC_ALL': UTF8_LOCALE,
            'UV_CACHE_DIR': UV_CACHE,
            'WORKTREE_ROOT': str(fleet['roots']),
        }
        return subprocess.run(
            [str(WORKTREE), *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            env=env,
            stdin=subprocess.DEVNULL,
        )

    return _run


def commit_in(worktree: Path, name: str) -> None:
    (worktree / name).write_text(f'{name}\n')
    git(worktree, 'add', name)
    git(worktree, 'commit', '-qm', f'feat: {name}')


def origin_of(clone: Path) -> Path:
    """The bare repo `make_repo` cloned from, which is the only place a branch can be
    deleted without this clone noticing."""
    return clone.parent / f'{clone.name}.git'


def publish(clone: Path, worktree: Path, branch: str) -> None:
    """Push the branch under its own name, so its upstream is its own ref.

    That is what `git push -u origin HEAD` does to a worktree branch, and it is the
    only thing separating work that reached a remote from work that never left the
    machine — `new` points a fresh branch at origin/<base>, not at itself.
    """
    git(worktree, 'push', '-q', '-u', 'origin', branch)


def delete_on_origin(clone: Path, branch: str) -> None:
    """Delete a branch in the bare repo, where this clone cannot see it happen.

    `sweep` looks for a remote-tracking ref that is still here and no longer there,
    so the deletion has to leave one behind for the prune to find. `push --delete`
    drops that ref as a side effect, which is a fixture that passes without ever
    exercising the check.
    """
    git(origin_of(clone), 'update-ref', '-d', f'refs/heads/{branch}')


def merged_worktree(clone: Path, roots: Path, run: Any, branch: str) -> Path:
    """The one shape `sweep` collects: a worktree whose commits are on main and whose
    remote branch has been deleted. Returns its path."""
    run(clone, 'new', branch)
    worktree = roots / clone.name / branch
    commit_in(worktree, f'{branch}.txt')
    publish(clone, worktree, branch)
    git(worktree, 'push', '-q', 'origin', 'HEAD:main')
    delete_on_origin(clone, branch)
    return worktree


def plain(text: str) -> str:
    """The text with its colour stripped, which is what an assertion reads."""
    return ANSI.sub('', text)


def fake_worktree(app: Any, path: str, **overrides: Any) -> Any:
    """A Worktree with no repository behind it, for the renderers to lay out.

    Its defaults are also the shape `sweep` removes — clean, nobody in it, nothing
    the base branch lacks — so a `held_by` case states only the one field it is about.
    """
    fields: dict[str, Any] = {
        'repo': 'primary',
        'path': Path(path),
        'checkout': False,
        'branch': 'alpha',
        'base': 'main',
        'ahead': 0,
        'behind': 0,
        'state': app.State.CLEAN,
        'sessions': (),
        'detached': False,
    }
    return app.Worktree(**(fields | overrides))


def fake_evidence(app: Any, **overrides: Any) -> Any:
    """Evidence that clears every check, so a case states only its one difference.

    An empty `remote` means origin carries no branch of this name, which with
    `published` is the pair that says *pushed once, deleted since*.
    """
    fields: dict[str, Any] = {'published': True, 'fetched': True, 'remote': frozenset()}
    return app.Evidence(**(fields | overrides))


def held_by_cases(app: Any) -> list[tuple[Any, dict[str, Any], dict[str, Any]]]:
    """Every reason a worktree survives, as (member, worktree fields, evidence fields).

    One table rather than one test each, because the claim worth asserting is that it
    covers `Kept` exactly. A member with no row here is a reason nothing can produce.
    """
    occupant = app.Session(name='reviewer', status='idle', waiting=None, cwd=Path('/w/alpha'), tmux=None)
    return [
        (app.Kept.DIRTY, {'state': app.State.DIRTY}, {}),
        (app.Kept.SESSIONS_UNREADABLE, {'sessions': None}, {}),
        (app.Kept.SESSION, {'sessions': (occupant,)}, {}),
        (app.Kept.DETACHED, {'branch': 'HEAD', 'detached': True}, {}),
        (app.Kept.UNFETCHED_REMOTE, {}, {'fetched': False}),
        (app.Kept.UNFETCHED_BASE, {'ahead': None}, {}),
        (app.Kept.UNLANDED, {'ahead': 2}, {}),
        (app.Kept.UNPUBLISHED, {}, {'published': False}),
        (app.Kept.REMOTE_UNREADABLE, {}, {'remote': None}),
        (app.Kept.REMOTE_LIVE, {}, {'remote': frozenset({'alpha'})}),
    ]


def rows(result: subprocess.CompletedProcess[str]) -> list[str]:
    """The listing's data rows, with the column header dropped."""
    return plain(result.stdout).splitlines()[1:]


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

    def test_the_path_it_created_is_what_it_prints(self, fleet, run):
        """`cd "$(worktree new x)"` is the reason stdout carries the path."""
        result = run(fleet['primary'], 'new', 'alpha')

        assert result.stdout.strip() == str(fleet['roots'] / 'primary' / 'alpha')


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
        assert 'alpha' not in git(fleet['primary'], 'branch', '--list')

    def test_the_last_worktree_leaving_takes_the_repo_directory_with_it(self, fleet, run):
        """`git worktree remove` takes the leaf only, so the root would otherwise
        fill with empty shells of repos carrying nothing."""
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        commit_in(alpha, 'x')

        run(alpha, 'land')

        assert not (fleet['roots'] / 'primary').exists()

    def test_a_repo_directory_with_a_worktree_left_in_it_stays(self, fleet, run):
        run(fleet['primary'], 'new', 'alpha')
        run(fleet['primary'], 'new', 'beta')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        commit_in(alpha, 'x')

        run(alpha, 'land')

        assert (fleet['roots'] / 'primary' / 'beta').is_dir()

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
        assert git(beta, 'rev-list', '--count', 'beta') != '0'

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

    def test_a_removal_that_failed_is_said_rather_than_announced_as_cleaned_up(self, fleet, run):
        """A removal git refuses leaves the worktree standing after the landing has
        already announced success, and $WORKTREE_ROOT then holds a tree whose work is
        on main. The landing line alone cannot be the whole verdict.

        A lock is the deterministic way to make git refuse: the tree is clean, so
        every other refusal has already been ruled out by the time removal runs.
        """
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        commit_in(alpha, 'x')
        git(fleet['primary'], 'worktree', 'lock', str(alpha))

        result = run(alpha, 'land')

        assert 'feat: x' in git(fleet['primary'], 'log', '--oneline', 'origin/main'), 'the landing itself still happened'
        assert alpha.exists()
        assert 'still here' in plain(result.stderr)

    def test_a_kept_branch_is_not_reported_as_a_worktree_still_standing(self, fleet, run, worktree_app):
        """The two halves of a disposal fail separately, and after the branch deletion
        fails the directory is already gone.

        One failure value cannot carry that, and a caller holding one says the worktree
        is still here about a path that no longer exists — sending a reader to look at
        a directory rather than at the ref that survived.
        """
        checkout = fleet['primary']
        run(checkout, 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'

        outcome, detail = worktree_app.dispose(checkout, alpha, 'no-such-branch', force=False)

        assert outcome is worktree_app.Disposal.BRANCH_KEPT
        assert not alpha.exists(), 'the removal half succeeded, so the path is gone'
        assert detail

    def test_a_busy_primary_checkout_is_left_alone(self, fleet, run):
        """Another session may be working there, and its tree is not ours to move."""
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        commit_in(alpha, 'x')
        (fleet['primary'] / 'f.txt').write_text('someone is editing this\n')

        result = run(alpha, 'land')

        assert result.returncode == 0, 'the landing still happens; only the catch-up is skipped'
        assert (fleet['primary'] / 'f.txt').read_text() == 'someone is editing this\n'


class TestHeldBy:
    """The decision that deletes a directory, exercised with no repository behind it.

    `held_by` is a function of its arguments, which is what lets a case *state* the
    thing it is about instead of assembling a repo that happens to produce it. Three
    of the reasons cannot be built through the CLI at all — a base branch nobody has
    fetched is restored by the sweep's own fetch, and `for-each-ref` returns 0 on any
    valid repository — so without this class they are guards no test can reach.
    """

    def test_a_finished_worktree_clears_every_check(self, worktree_app):
        cleared = fake_worktree(worktree_app, '/w/alpha')

        assert worktree_app.held_by(cleared, fake_evidence(worktree_app)) is None

    def test_each_reason_is_what_its_own_state_produces(self, worktree_app):
        for member, worktree_fields, evidence_fields in held_by_cases(worktree_app):
            worktree = fake_worktree(worktree_app, '/w/alpha', **worktree_fields)
            evidence = fake_evidence(worktree_app, **evidence_fields)
            assert worktree_app.held_by(worktree, evidence) is member, member

    def test_every_reason_is_reachable(self, worktree_app):
        """A `Kept` member nothing returns is a guard that was written and never wired.

        The enum is where the guards are declared, so it is the side to compare
        against — a table that only covered what the code happens to do would agree
        with the code by construction and assert nothing.
        """
        covered = {member for member, _, _ in held_by_cases(worktree_app)}

        assert covered == set(worktree_app.Kept)

    def test_an_unanswerable_check_never_reads_as_cleared(self, worktree_app):
        """The three reads that can fail, each proved to hold the worktree rather than
        resolve to a falsy value the next check walks past.

        This is the direction that costs work: `held_by` ends in *remove*, so a failed
        read that returns an empty tuple or a missing ref authorises a deletion on the
        strength of a question nobody managed to ask.
        """
        unanswerable = [
            (fake_worktree(worktree_app, '/w/alpha', sessions=None), fake_evidence(worktree_app)),
            (fake_worktree(worktree_app, '/w/alpha'), fake_evidence(worktree_app, fetched=False)),
            (fake_worktree(worktree_app, '/w/alpha'), fake_evidence(worktree_app, remote=None)),
        ]

        for worktree, evidence in unanswerable:
            assert worktree_app.held_by(worktree, evidence) is not None


class TestSweep:
    """`sweep` removes worktrees nobody is standing in, so every test here is about
    what it declines to touch.

    `land` and `drop` both read Path.cwd(), which means the only worktrees they can
    dispose of are ones a session is already in. Work that goes through a PR is
    merged on the forge and its branch deleted there, so `land` never runs and the
    directory outlives the work by months. `sweep` is what reaches those, and the
    price of reaching them is that it acts on trees whose owner is not present to
    object.
    """

    def test_a_merged_branch_with_its_remote_deleted_is_removed(self, fleet, run):
        alpha = merged_worktree(fleet['primary'], fleet['roots'], run, 'alpha')

        result = run(fleet['primary'], 'sweep', '--yes')

        assert result.returncode == 0
        assert not alpha.exists()
        assert 'alpha' not in git(fleet['primary'], 'branch', '--format=%(refname:short)').splitlines()

    def test_a_branch_tracking_the_base_is_never_swept(self, fleet, run):
        """The long-lived worktree that clears every other check: clean, nothing on it
        that main lacks, and no remote branch of its own to be deleted.

        `new` points a branch at origin/<base> rather than at itself, so this is also
        the shape of every worktree between creation and its first push. Sweeping it
        would delete work that has been nowhere else.
        """
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        commit_in(alpha, 'unpushed.txt')

        result = run(fleet['primary'], 'sweep', '--yes')

        assert result.returncode == 0
        assert alpha.exists()
        assert git(alpha, 'log', '--oneline', '-1').endswith('feat: unpushed.txt')

    def test_a_checkout_behind_origin_still_gives_up_the_branch(self, fleet, run):
        """The proof of a merge is ancestry against origin/<base>, never `git branch -d`.

        -d asks whether the branch is merged into the *checkout's* HEAD, and the
        checkout is a different tree whose local main is only as current as its last
        pull. Here main merged on the remote and the checkout has not pulled it, which
        is the ordinary state of every repo the moment a PR lands — and -d refuses the
        whole sweep in it.
        """
        alpha = merged_worktree(fleet['primary'], fleet['roots'], run, 'alpha')
        behind = git(fleet['primary'], 'rev-list', '--count', 'main..origin/main')
        assert behind != '0', 'the fixture has to leave the checkout behind, or this proves nothing'

        result = run(fleet['primary'], 'sweep', '--yes')

        assert result.returncode == 0
        assert not alpha.exists()
        assert 'alpha' not in git(fleet['primary'], 'branch', '--format=%(refname:short)').splitlines()

    def test_a_detached_worktree_is_kept_for_being_detached(self, fleet, run):
        """It has no branch, so nothing can be asked about where its commits are.

        The reason is asserted, not just the survival. Every keep here has several
        reasons available and the first one wins, so a test that only checks the
        directory still exists passes whichever guard actually fired.
        """
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        git(alpha, 'checkout', '-q', '--detach', 'HEAD')

        result = run(fleet['primary'], 'sweep', '--yes')

        assert result.returncode == 0
        assert alpha.exists()
        assert 'a detached HEAD' in plain(result.stderr)

    def test_a_merged_worktree_whose_remote_branch_lives_is_kept(self, fleet, run):
        """The other half of what the command's own help promises — merged *and* deleted
        on the remote. Merged alone is a branch someone is still publishing to."""
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        commit_in(alpha, 'shipped.txt')
        publish(fleet['primary'], alpha, 'alpha')
        git(alpha, 'push', '-q', 'origin', 'HEAD:main')

        result = run(fleet['primary'], 'sweep', '--yes')

        assert result.returncode == 0
        assert alpha.exists()
        assert 'its remote branch still exists' in plain(result.stderr)

    def test_claude_sessions_failing_keeps_everything(self, fleet, run, bin_dir):
        """An unanswerable session check held the worktree rather than clearing it.

        `live_sessions` answering with an empty tuple would mean *nobody is in this
        worktree*, which is the one sentence a failed read cannot support. The exposed
        window is the minutes after a merge, when the author's session is still in the
        worktree the sweep is coming for.
        """
        alpha = merged_worktree(fleet['primary'], fleet['roots'], run, 'alpha')
        write_stub(bin_dir, 'claude-sessions', 'exit 1')

        result = run(fleet['primary'], 'sweep', '--yes')

        assert alpha.exists()
        assert 'could not say whether anyone is in it' in plain(result.stderr)

    def test_claude_sessions_missing_reads_as_unknown_not_as_empty(self, worktree_app, monkeypatch, tmp_path):
        """Absent from PATH is the same unanswerable question reached another way, and
        it is the one that used to pass in complete silence — no warning, no mention of
        sessions at all, and a removal.

        Asserted against `live_sessions` rather than through the CLI, because PATH is
        the subject: the run fixture prepends its stub directory to the real PATH, so a
        removed stub is answered by whatever the machine has installed.
        """
        empty = tmp_path / 'nothing'
        empty.mkdir()
        monkeypatch.setenv('PATH', str(empty))

        assert worktree_app.live_sessions() is None

    def test_an_unreachable_origin_keeps_everything(self, fleet, run):
        """Every remote fact below the fetch is read out of refs/remotes/origin, which
        outlives a deleted branch until a prune. A fetch that failed leaves those refs
        saying whatever they said before, and a verdict read off them is about a remote
        the command never reached."""
        alpha = merged_worktree(fleet['primary'], fleet['roots'], run, 'alpha')
        git(fleet['primary'], 'remote', 'set-url', 'origin', '/nonexistent/origin.git')

        result = run(fleet['primary'], 'sweep', '--yes')

        assert alpha.exists()
        assert 'origin could not be reached' in plain(result.stderr)

    def test_a_dirty_worktree_is_kept(self, fleet, run):
        alpha = merged_worktree(fleet['primary'], fleet['roots'], run, 'alpha')
        (alpha / 'half-finished.txt').write_text('half\n')

        result = run(fleet['primary'], 'sweep', '--yes')

        assert alpha.exists()
        assert (alpha / 'half-finished.txt').read_text() == 'half\n'
        assert 'uncommitted changes' in plain(result.stderr)

    def test_a_session_standing_in_it_keeps_it(self, fleet, run, bin_dir):
        """Merged is not the same as finished with. Somebody is in there."""
        alpha = merged_worktree(fleet['primary'], fleet['roots'], run, 'alpha')
        stub_sessions(bin_dir, session('reviewer', alpha))

        result = run(fleet['primary'], 'sweep', '--yes')

        assert alpha.exists()
        assert 'a session is standing in it' in plain(result.stderr)

    def test_a_branch_deleted_without_merging_is_kept(self, fleet, run):
        """A deleted remote branch is not evidence of a merge. The commits are here
        and nowhere else, which is the one thing that must never be swept."""
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        commit_in(alpha, 'only-copy.txt')
        publish(fleet['primary'], alpha, 'alpha')
        delete_on_origin(fleet['primary'], 'alpha')

        result = run(fleet['primary'], 'sweep', '--yes')

        assert alpha.exists()
        assert (alpha / 'only-copy.txt').exists()
        assert 'commits that are on no other branch' in plain(result.stderr)

    def test_ignored_build_output_does_not_block_removal(self, fleet, run):
        """`new` runs `task setup`, so a real worktree carries a .venv or a
        node_modules by the time it is finished with. git counts neither as untracked,
        which is what lets the removal run without --force."""
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        (alpha / '.gitignore').write_text('.venv/\n')
        git(alpha, 'add', '.gitignore')
        git(alpha, 'commit', '-qm', 'chore: ignore the venv')
        publish(fleet['primary'], alpha, 'alpha')
        git(alpha, 'push', '-q', 'origin', 'HEAD:main')
        delete_on_origin(fleet['primary'], 'alpha')
        (alpha / '.venv').mkdir()
        (alpha / '.venv' / 'pyvenv.cfg').write_text('home = /usr\n')

        result = run(fleet['primary'], 'sweep', '--yes')

        assert result.returncode == 0
        assert not alpha.exists()

    def test_it_refuses_to_remove_anything_without_a_terminal(self, fleet, run):
        """The y/N is the guard, so losing the terminal has to mean losing the sweep
        rather than defaulting to yes.

        Exit 2, because the remedy is an argument. A partial removal failure exits 1,
        and only the first of those is worth reinvoking with different arguments.
        """
        alpha = merged_worktree(fleet['primary'], fleet['roots'], run, 'alpha')

        result = run(fleet['primary'], 'sweep')

        assert result.returncode == 2
        assert alpha.exists()
        assert '--yes' in plain(result.stderr)

    def test_the_primary_checkout_is_never_touched(self, fleet, run):
        """It is in every scan and it is nobody's worktree to remove."""
        merged_worktree(fleet['primary'], fleet['roots'], run, 'alpha')

        run(fleet['primary'], 'sweep', '--yes')

        assert fleet['primary'].exists()
        assert (fleet['primary'] / 'f.txt').exists()

    def test_it_sweeps_every_repo_from_wherever_it_is_run(self, fleet, run):
        """The reason it is not a bulk `drop`: the worktrees it collects are in repos
        the session is not standing in, which is where they accumulate."""
        elsewhere = merged_worktree(fleet['other'], fleet['roots'], run, 'beta')

        result = run(fleet['primary'], 'sweep', '--yes')

        assert result.returncode == 0
        assert not elsewhere.exists()

    def test_one_repo_can_be_named(self, fleet, run):
        alpha = merged_worktree(fleet['primary'], fleet['roots'], run, 'alpha')
        beta = merged_worktree(fleet['other'], fleet['roots'], run, 'beta')

        run(fleet['primary'], 'sweep', 'primary', '--yes')

        assert not alpha.exists()
        assert beta.exists()

    def test_an_empty_sweep_names_what_it_checked(self, fleet, run):
        """An all-clear that names the whole machine, from a command that measured one
        worktree, is the shape that stops being believed."""
        run(fleet['primary'], 'new', 'alpha')

        result = run(fleet['primary'], 'sweep', '--yes')

        assert result.returncode == 0
        assert '1 worktree(s) checked' in plain(result.stderr)

    def test_every_survivor_is_named_with_its_reason(self, fleet, run):
        """A worktree left standing with no reason given reads as one the tool missed."""
        run(fleet['primary'], 'new', 'alpha')

        result = run(fleet['primary'], 'sweep', '--yes')

        assert 'alpha — kept, never pushed under its own name' in plain(result.stderr)


class TestUsage:
    def test_land_outside_a_worktree_is_refused(self, fleet, run):
        result = run(fleet['primary'], 'land')

        assert result.returncode != 0
        assert result.stderr.strip() != '', 'a refusal has to say what was wrong with it'

    def test_landing_nothing_is_refused(self, fleet, run):
        run(fleet['primary'], 'new', 'alpha')

        result = run(fleet['roots'] / 'primary' / 'alpha', 'land')

        assert result.returncode != 0

    def test_new_without_a_slug_is_refused(self, fleet, run):
        result = run(fleet['primary'], 'new')

        assert result.returncode == 2, 'a usage error is 2, whatever else the run failed at'

    def test_a_refusal_never_reaches_stdout(self, fleet, run):
        """`cd "$(worktree choose)"` would otherwise cd into an error message."""
        result = run(fleet['primary'], 'land')

        assert result.stdout == ''


class TestProvisioning:
    """A new worktree runs the repo's own `task setup`, when the repo declares one.

    The target is the declaration, so there is no registry to keep in step and
    every way of not having one is silent: no `task` on PATH, no Taskfile, or a
    Taskfile that declares something else.
    """

    def stub_task(self, bin_dir: Path, marker: Path, *, declares: bool = True, fails: bool = False) -> None:
        tasks = '{"tasks":[{"name":"setup"}]}' if declares else '{"tasks":[{"name":"test"}]}'
        write_stub(
            bin_dir,
            'task',
            f"""case "$1" in
  --list-all) echo '{tasks}' ;;
  setup) echo ran > '{marker}'; exit {1 if fails else 0} ;;
esac""",
        )

    def test_a_declared_setup_runs_in_the_new_worktree(self, tmp_path, fleet, bin_dir, run):
        marker = tmp_path / 'setup-ran'
        self.stub_task(bin_dir, marker)

        result = run(fleet['primary'], 'new', 'alpha')

        assert result.returncode == 0
        assert marker.exists(), 'a repo declaring setup must have it run'

    def test_a_repo_declaring_no_setup_is_left_alone(self, tmp_path, fleet, bin_dir, run):
        marker = tmp_path / 'setup-ran'
        self.stub_task(bin_dir, marker, declares=False)

        result = run(fleet['primary'], 'new', 'alpha')

        assert result.returncode == 0
        assert not marker.exists(), 'setup must not run where the repo never declared it'

    def test_no_task_on_path_is_not_a_failure(self, fleet, bin_dir, run):
        """The work box has repos and may not have `task`. Absence is ordinary."""
        write_stub(bin_dir, 'task', 'exit 127')

        result = run(fleet['primary'], 'new', 'alpha')

        assert result.returncode == 0
        assert (fleet['roots'] / 'primary' / 'alpha').is_dir()

    def test_a_failing_setup_warns_and_keeps_the_worktree(self, tmp_path, fleet, bin_dir, run):
        """Destroying it would lose the isolation that was the whole point."""
        marker = tmp_path / 'setup-ran'
        self.stub_task(bin_dir, marker, fails=True)

        result = run(fleet['primary'], 'new', 'alpha')

        assert result.returncode == 0
        assert (fleet['roots'] / 'primary' / 'alpha').is_dir()
        assert 'setup' in result.stderr, 'a failed provision has to say so'

    def test_the_path_still_reaches_stdout_alone(self, tmp_path, fleet, bin_dir, run):
        """`cd "$(worktree new x)"` breaks if provisioning narrates onto stdout."""
        self.stub_task(bin_dir, tmp_path / 'setup-ran')

        result = run(fleet['primary'], 'new', 'alpha')

        assert result.stdout.strip() == str(fleet['roots'] / 'primary' / 'alpha')


class TestEcho:
    """Every subprocess is announced before it runs.

    `land` fetches, rebases and pushes onto the default branch, and the branch it
    moved is not recoverable from the one line it prints afterwards. The echo is
    asserted as text a shell would take, not as a message: what makes it worth
    having is that a stopped run is replayed by pasting a line back.
    """

    def commands(self, result: subprocess.CompletedProcess[str]) -> list[str]:
        return [line.strip().removeprefix('$ ') for line in plain(result.stderr).splitlines() if line.strip().startswith('$ ')]

    def test_the_git_that_moves_a_branch_is_named(self, fleet, run):
        alpha = fleet['roots'] / 'primary' / 'alpha'
        run(fleet['primary'], 'new', 'alpha')
        commit_in(alpha, 'a.txt')

        result = run(alpha, 'land')

        assert f'git -C {alpha} rebase --quiet origin/main' in self.commands(result)
        assert f'git -C {alpha} push --quiet origin HEAD:main' in self.commands(result)

    def test_an_echoed_line_runs_as_it_stands(self, fleet, run):
        """Pasteable is the claim, so the assertion pastes one.

        A git line, and a worktree for it to be about. `discover` probes
        `claude-sessions` before it runs any git, and the fixture's PATH ends in
        the real one — so taking the first line asserts against whichever tools
        the developer has installed, and finds nothing at all on a runner that
        has neither them nor a worktree to list.
        """
        run(fleet['primary'], 'new', 'alpha')

        result = run(fleet['primary'], 'list')

        pasted = next(line for line in self.commands(result) if line.startswith('git '))
        replayed = subprocess.run(shlex.split(pasted), capture_output=True, text=True)

        assert replayed.returncode == 0

    def test_what_is_not_git_is_announced_too(self, fleet, run, bin_dir):
        """One choke point, or the next subprocess added here escapes it."""
        stub_sessions(bin_dir, session('one', fleet['primary']))

        result = run(fleet['primary'], 'list')

        assert 'claude-sessions --json' in self.commands(result)

    def test_quiet_hides_the_commands_and_keeps_the_verdict(self, fleet, run):
        alpha = fleet['roots'] / 'primary' / 'alpha'
        run(fleet['primary'], 'new', 'alpha')
        commit_in(alpha, 'a.txt')

        result = run(alpha, 'land', '-q')

        assert self.commands(result) == []
        assert 'Landed 1 commit' in plain(result.stderr)

    def test_no_command_reaches_stdout(self, fleet, run):
        """One line of it on stdout and a caller's parse fails as malformed JSON."""
        run(fleet['primary'], 'new', 'alpha')

        result = run(fleet['primary'], 'list', '--json')

        assert self.commands(result) != [], 'the echo is on, so stdout is the thing under test'
        assert len(json.loads(result.stdout)) == 2


class TestListing:
    def test_it_reads_every_repo_not_just_the_one_you_are_in(self, fleet, run):
        run(fleet['primary'], 'new', 'alpha')
        run(fleet['other'], 'new', 'beta')

        listed = rows(run(fleet['primary'], 'list'))

        assert any('alpha' in row for row in listed)
        assert any('beta' in row for row in listed)

    def test_a_repo_argument_narrows_it(self, fleet, run):
        run(fleet['primary'], 'new', 'alpha')
        run(fleet['other'], 'new', 'beta')

        listed = rows(run(fleet['primary'], 'list', 'other'))

        assert any('beta' in row for row in listed)
        assert not any('alpha' in row for row in listed)

    def test_the_checkout_comes_before_what_was_cut_from_it(self, fleet, run):
        run(fleet['primary'], 'new', 'alpha')

        listed = rows(run(fleet['primary'], 'list'))

        assert listed[0].split()[0] == '~/primary'
        assert 'alpha' in listed[1]

    def test_a_repo_with_no_worktree_is_not_in_the_listing(self, fleet, run):
        """$WORKTREE_ROOT is the whole index, so a repo joins the listing by having
        a worktree and leaves it by losing the last one."""
        run(fleet['primary'], 'new', 'alpha')

        listed = rows(run(fleet['primary'], 'list'))

        assert not any('other' in row for row in listed)

    def test_an_empty_set_is_not_a_failure(self, fleet, run):
        result = run(fleet['primary'], 'list')

        assert result.returncode == 0
        assert result.stdout == ''
        assert 'No worktrees' in plain(result.stderr)

    def test_all_is_refused_and_names_the_argument_instead(self, fleet, run):
        """Scope is structural here, so the flag a habit reaches for has to teach
        the argument rather than fall through to "unrecognized arguments"."""
        result = run(fleet['primary'], 'list', '--all')

        assert result.returncode == 2
        assert 'worktree list <repo>' in result.stderr

    def test_json_carries_what_the_row_shows(self, fleet, run):
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        commit_in(alpha, 'x')
        (alpha / 'unstaged.txt').write_text('half\n')

        listed = json.loads(run(fleet['primary'], 'list', '--json').stdout)
        worktree = next(row for row in listed if row['path'] == str(alpha))

        assert worktree['repo'] == 'primary'
        assert worktree['checkout'] is False
        assert worktree['branch'] == 'alpha'
        assert worktree['ahead'] == 1
        assert worktree['state'] == 'dirty'

    def test_json_of_an_empty_set_is_an_empty_array(self, fleet, run):
        """An empty here-string was one empty row in the shell version, and its
        empty path prefix-matched every session on the machine."""
        assert json.loads(run(fleet['primary'], 'list', '--json').stdout) == []


class TestSessions:
    def test_a_session_below_a_worktree_is_claimed_by_it(self, fleet, run, bin_dir):
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        stub_sessions(bin_dir, session('alpha-7f', alpha / 'src', status='busy'))

        listed = rows(run(fleet['primary'], 'list'))

        assert any('alpha-7f (busy)' in row for row in listed)

    def test_a_sibling_whose_name_starts_the_same_is_not_claimed(self, fleet, run, bin_dir):
        run(fleet['primary'], 'new', 'alpha')
        run(fleet['primary'], 'new', 'alpha-two')
        stub_sessions(bin_dir, session('two-3a', fleet['roots'] / 'primary' / 'alpha-two'))

        listed = rows(run(fleet['primary'], 'list'))
        alpha = next(row for row in listed if row.split()[0].endswith('/alpha'))

        assert 'two-3a' not in alpha

    def test_a_failing_registry_reader_still_lists_the_worktrees(self, fleet, run, bin_dir):
        """The worktrees are the subject and the sessions annotate them, so losing
        the annotation degrades the listing rather than ending it — out loud."""
        run(fleet['primary'], 'new', 'alpha')
        write_stub(bin_dir, 'claude-sessions', 'exit 1')

        result = run(fleet['primary'], 'list')

        assert result.returncode == 0
        assert any('alpha' in row for row in rows(result))
        assert 'claude-sessions failed' in plain(result.stderr)


class TestShow:
    def test_it_names_the_worktree_and_what_it_carries(self, fleet, run):
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        commit_in(alpha, 'x')

        shown = plain(run(fleet['primary'], 'show', str(alpha)).stdout)

        assert 'primary/alpha' in shown
        assert '1 ahead' in shown
        assert 'feat: x' in shown

    def test_it_lists_the_files_that_are_dirty(self, fleet, run):
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        (alpha / 'unfinished.txt').write_text('half\n')

        shown = plain(run(fleet['primary'], 'show', str(alpha)).stdout)

        assert 'unfinished.txt' in shown

    def test_it_defaults_to_the_worktree_you_are_standing_in(self, fleet, run):
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'

        shown = plain(run(alpha, 'show').stdout)

        assert 'primary/alpha' in shown

    def test_a_checkout_is_named_by_its_repo_alone(self, fleet, run):
        shown = plain(run(fleet['primary'], 'show').stdout)

        assert shown.splitlines()[0] == 'primary'

    def test_it_names_the_session_standing_in_it(self, fleet, run, bin_dir):
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        stub_sessions(bin_dir, session('alpha-7f', alpha, status='busy'))

        shown = plain(run(fleet['primary'], 'show', str(alpha)).stdout)

        assert 'alpha-7f — busy' in shown

    def test_a_directory_outside_a_repo_is_refused(self, tmp_path, fleet, run):
        loose = tmp_path / 'loose'
        loose.mkdir()

        result = run(fleet['primary'], 'show', str(loose))

        assert result.returncode == 1
        assert 'Not a git worktree' in plain(result.stderr)


class TestChoose:
    """The picker is fzf, shadowed. What can be asserted is what it is handed and
    what comes back out — everything past that belongs to fzf."""

    @pytest.fixture
    def populated(self, fleet, run) -> Path:
        """One worktree, so the picker has a checkout and a worktree to offer."""
        run(fleet['primary'], 'new', 'alpha')
        return fleet['roots'] / 'primary' / 'alpha'

    @pytest.fixture
    def picker(self, tmp_path: Path, bin_dir: Path, run):
        """Run `choose` against a stub fzf, returning what it was fed and its argv.

        The stub picks by reading back the second line of its own input, which is
        the first row under the header — so the test never has to spell a row it
        did not build.
        """
        fed = tmp_path / 'fed-to-fzf'
        argv = tmp_path / 'fzf-argv'

        def _picker(cwd: Path, *args: str, behaviour: str = f"sed -n '2p' '{fed}'"):
            write_stub(bin_dir, 'fzf', f"printf '%s\\n' \"$@\" > '{argv}'\ncat > '{fed}'\n{behaviour}")
            return run(cwd, 'choose', *args), fed, argv

        return _picker

    def test_every_row_carries_its_path_in_front_of_what_is_displayed(self, fleet, populated, picker):
        _, fed, _ = picker(fleet['primary'], behaviour='exit 130')

        assert any(line.startswith(f'{populated}\t') for line in fed.read_text().splitlines())

    def test_the_header_is_the_first_row_and_fzf_is_told_to_hold_it(self, fleet, populated, picker):
        _, fed, argv = picker(fleet['primary'], behaviour='exit 130')

        assert fed.read_text().splitlines()[0].startswith('\tLOCATION')
        assert '--header-lines' in argv.read_text().splitlines()

    def test_it_prints_the_path_of_the_row_that_was_picked(self, fleet, populated, picker):
        result, _, _ = picker(fleet['primary'])

        assert result.stdout.strip() == str(fleet['primary']), 'the checkout is the first row'

    def test_a_dismissed_picker_prints_nothing_and_exits_clean(self, fleet, populated, picker):
        result, _, _ = picker(fleet['primary'], behaviour='exit 130')

        assert result.returncode == 0
        assert result.stdout == ''

    def test_the_preview_runs_show_against_the_path_field(self, fleet, populated, picker):
        _, _, argv = picker(fleet['primary'], behaviour='exit 130')

        preview = next(line for line in argv.read_text().splitlines() if ' show ' in line)

        assert preview.endswith('{1}')
        assert 'FORCE_COLOR=1' in preview, 'a preview is a pipe, so colour has to be asked for'
        assert ' -q ' in preview, 'the pane previews a worktree, not the git reads behind it'

    def test_a_repo_argument_narrows_the_picker(self, fleet, populated, picker, run):
        run(fleet['other'], 'new', 'beta')

        _, fed, _ = picker(fleet['primary'], 'primary', behaviour='exit 130')

        assert 'beta' not in fed.read_text()

    def test_nothing_to_choose_is_a_refusal_not_an_empty_picker(self, fleet, picker):
        result, fed, _ = picker(fleet['primary'], behaviour='exit 130')

        assert result.returncode == 1
        assert result.stdout == ''
        assert 'No worktrees' in plain(result.stderr)
        assert not fed.exists(), 'fzf is never opened on an empty set'


class TestRendering:
    """The half with no I/O in it: which sessions a worktree claims, and how a set
    of rows becomes a table. Both are cheap to enumerate here and expensive to
    reach through a fixture."""

    def test_a_session_deeper_in_the_tree_belongs_to_the_worktree(self, worktree_app):
        found = worktree_app.sessions_at(
            [worktree_app.Session('a', 'idle', None, Path('/w/alpha/src/deep'), None)],
            Path('/w/alpha'),
        )

        assert [session.name for session in found] == ['a']

    def test_a_sibling_sharing_a_name_prefix_does_not(self, worktree_app):
        found = worktree_app.sessions_at(
            [worktree_app.Session('a', 'idle', None, Path('/w/alpha-two'), None)],
            Path('/w/alpha'),
        )

        assert found == ()

    def test_columns_line_up_under_their_headers(self, worktree_app):
        header, *body = worktree_app.render_table(
            [
                fake_worktree(worktree_app, '/w/a', branch='short'),
                fake_worktree(worktree_app, '/w/a-very-long-one', branch='considerably-longer'),
            ]
        )
        branch_at = header.index('BRANCH')

        assert body[0].index('short') == branch_at
        assert body[1].index('considerably-longer') == branch_at

    def test_the_last_column_is_never_padded(self, worktree_app):
        """Session names run long, and nothing follows them."""
        table = worktree_app.render_table([fake_worktree(worktree_app, '/w/a')])

        assert all(row == row.rstrip() for row in table)
