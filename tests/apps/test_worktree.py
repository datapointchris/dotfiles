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
    tool of that name."""
    path = tmp_path / 'bin'
    path.mkdir()
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
    """

    def _run(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        env = {
            'HOME': str(tmp_path),
            'PATH': f'{bin_dir}:{os.environ["PATH"]}',
            'LC_ALL': UTF8_LOCALE,
            'UV_CACHE_DIR': UV_CACHE,
            'WORKTREE_ROOT': str(fleet['roots']),
        }
        return subprocess.run([str(WORKTREE), *args], cwd=cwd, capture_output=True, text=True, env=env)

    return _run


def commit_in(worktree: Path, name: str) -> None:
    (worktree / name).write_text(f'{name}\n')
    git(worktree, 'add', name)
    git(worktree, 'commit', '-qm', f'feat: {name}')


def plain(text: str) -> str:
    """The text with its colour stripped, which is what an assertion reads."""
    return ANSI.sub('', text)


def fake_worktree(app: Any, path: str, **overrides: Any) -> Any:
    """A Worktree with no repository behind it, for the renderers to lay out."""
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
    }
    return app.Worktree(**(fields | overrides))


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

        preview = next(line for line in argv.read_text().splitlines() if ' show {1}' in line)

        assert preview.endswith('show {1}')
        assert 'FORCE_COLOR=1' in preview, 'a preview is a pipe, so colour has to be asked for'

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
