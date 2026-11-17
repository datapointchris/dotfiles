"""`worktree land` against real git, sealed off from the machine running it.

Each scenario a landing meets has a test here, and under all of them sits one
claim: every sha the worklog hook recorded reaches main.

Nothing here reads this machine's git config, hooks or home. Each test gets a home
of its own and a global config whose hooks are this repo's own scripts. A `slate`
on PATH writes down each link it is asked for. git's repository variables are
cleared at import, so a run started by a commit hook in a linked worktree cannot
reach the repo being committed. Identities are passed with `git -c`, or through
git's identity variables for the tool, which takes no `-c`.

The module needs nothing but pytest, so the same file runs inside a bare container
and on a machine with none of this repo's environment:

    uv run --no-project --no-config --with pytest pytest --confcutdir tests/apps tests/apps/test_worktree_land.py

`--confcutdir` keeps tests/conftest.py, and the project it imports, out of the run.
`tests/e2e/test_worktree_land_on_each_git.py` runs it that way on each container's git.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WORKTREE = REPO / 'apps' / 'common' / 'worktree'
TRAILER_HOOK = REPO / 'apps' / 'trust' / 'fleet' / 'agent-commit-trailers'
LINK_HOOK = REPO / 'apps' / 'trust' / 'fleet' / 'link-commit-to-slate-worklog'
HOOK_LIBRARY = REPO / 'configs' / 'trust' / 'fleet' / '.local' / 'shell'

for variable in subprocess.run(['git', 'rev-parse', '--local-env-vars'], capture_output=True, text=True, check=True).stdout.split():
    os.environ.pop(variable, None)

# Read while HOME is still the machine's. Each test replaces HOME, and uv keeps its
# cache and its Pythons under it, so without these every `uv run` would download
# its interpreter and dependencies again.
UV_CACHE = os.environ.get('UV_CACHE_DIR') or str(Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache') / 'uv')
UV_PYTHONS = os.environ.get('UV_PYTHON_INSTALL_DIR') or str(
    Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share') / 'uv' / 'python'
)
UTF8_LOCALE = 'en_US.UTF-8' if sys.platform == 'darwin' else 'C.UTF-8'

SESSION = 'session-under-test'
WORKLOG = '1.1'
IDENTITY = ('-c', 'user.name=test', '-c', 'user.email=test@example.com')


def conventional_commits_release() -> str:
    """The conventional-pre-commit release this repo's own commit-msg hook runs."""
    config = (REPO / '.pre-commit-config.yaml').read_text()
    found = re.search(r'compilerla/conventional-pre-commit\n\s+rev: v?(\S+)', config)
    assert found, '.pre-commit-config.yaml names no conventional-pre-commit release'
    return found[1]


STAND_IN_SLATE = """#!/bin/sh
case "$1 $2" in
'worklogs current') echo "$WORKLOG" ;;
'worklogs link') echo "$*" >>"$LINKS" ;;
esac
"""

# What happens between `land`'s merge and its push. A positive count in $RACES is
# another landing reaching main first, made from the peer clone. Under
# $KILL_GROUP_BEFORE_PUSH the whole run dies: `kill 0` signals the hook's own
# process group, which `killed_land` starts afresh, so pytest is never in it.
PRE_PUSH = """#!/bin/sh
[ -z "${PEER_PUSHING:-}" ] || exit 0
[ -z "${KILL_GROUP_BEFORE_PUSH:-}" ] || kill -9 0
races=$(cat "$RACES" 2>/dev/null || echo 0)
[ "$races" -gt 0 ] || exit 0
echo $((races - 1)) >"$RACES"
unset $(git rev-parse --local-env-vars) CLAUDE_CODE_SESSION_ID
export PEER_PUSHING=1
git -C "$PEER" fetch -q origin
git -C "$PEER" switch -q --detach origin/main
echo "$races" >"$PEER/race-$races.txt"
git -C "$PEER" add "race-$races.txt"
git -C "$PEER" -c user.name=peer -c user.email=peer@example.com commit -qm "feat: another landing wins race $races"
git -C "$PEER" push -q origin HEAD:main
"""


def runs_hooks_set_in_config() -> bool:
    """Whether this git runs a hook declared as `hook.<name>.event`, asked with one that exits 3."""
    probe = subprocess.run(
        ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'hook.probe.event=pre-commit', '-c', 'hook.probe.command=exit 3',
         'hook', 'run', '--ignore-missing', 'pre-commit'],
        env={**os.environ, 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1'},
        capture_output=True,
    )  # fmt: skip
    return probe.returncode == 3


def write_executable(path: Path, text: str) -> None:
    path.write_text(text)
    path.chmod(0o755)


def hooks_into(hooks: Path) -> None:
    """The repo's own hook scripts, under the names git runs them at.

    `core.hooksPath` rather than `hook.<name>.event`, which git only reads from 2.54,
    so the oldest git a box runs fires them as the newest does. The commit-msg hook is
    the conventional check the repo's pre-commit config runs, with the same `--strict`,
    and it notes each subject it was handed in $CHECKED.
    """
    hooks.mkdir()
    write_executable(hooks / 'prepare-commit-msg', f'#!/bin/sh\nexec {shlex.quote(str(TRAILER_HOOK))} "$@"\n')
    write_executable(hooks / 'post-commit', f'#!/bin/sh\nexec {shlex.quote(str(LINK_HOOK))} "$@"\n')
    release = conventional_commits_release()
    write_executable(
        hooks / 'commit-msg',
        '#!/bin/sh\n'
        'head -n 1 "$1" >>"$CHECKED"\n'
        f'exec uv tool run --quiet --from conventional-pre-commit=={release} conventional-pre-commit --strict --no-color "$1"\n',
    )
    write_executable(hooks / 'pre-push', PRE_PUSH)


@dataclass
class Rig:
    """A bare origin, the primary checkout cloned from it, and a peer clone.

    The peer stands in for every other session: what it pushes is main moving while
    a landing is under way.
    """

    root: Path
    env: dict[str, str]
    origin: Path
    checkout: Path
    peer: Path

    def git(self, cwd: Path, *args: str, **env: str) -> str:
        done = subprocess.run(['git', *IDENTITY, *args], cwd=cwd, env=self.env | env, capture_output=True, text=True)
        assert done.returncode == 0, f'git {shlex.join(args)} in {cwd}: {done.stderr}'
        return done.stdout.strip()

    def tool(self, cwd: Path, *args: str, env: dict[str, str] | None = None, new_session: bool = False) -> subprocess.CompletedProcess[str]:
        identity = {
            'GIT_AUTHOR_NAME': 'test',
            'GIT_AUTHOR_EMAIL': 'test@example.com',
            'GIT_COMMITTER_NAME': 'test',
            'GIT_COMMITTER_EMAIL': 'test@example.com',
        }
        return subprocess.run(
            [str(WORKTREE), *args],
            cwd=cwd,
            env=self.env | identity | (env or {}),
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            start_new_session=new_session,
        )

    def land(self, cwd: Path, **env: str) -> subprocess.CompletedProcess[str]:
        """Every run ends in a landing or a refusal, so a test of either can tell it from a crash."""
        landing = self.tool(cwd, 'land', env=env)
        assert 'Traceback' not in landing.stderr, landing.stderr
        return landing

    def killed_land(self, cwd: Path) -> subprocess.CompletedProcess[str]:
        """A `land` killed with everything it started, at the moment before its push."""
        return self.tool(cwd, 'land', env={'KILL_GROUP_BEFORE_PUSH': '1'}, new_session=True)

    def new(self, slug: str) -> Path:
        made = self.tool(self.checkout, 'new', slug)
        assert made.returncode == 0, made.stderr
        return Path(made.stdout.strip())

    def commit(self, cwd: Path, name: str, text: str | None = None, *, subject: str | None = None, **env: str) -> str:
        (cwd / name).parent.mkdir(parents=True, exist_ok=True)
        (cwd / name).write_text(text if text is not None else f'{name}\n')
        self.git(cwd, 'add', name)
        self.git(cwd, 'commit', '-q', '-m', subject or f'feat: {name}', **env)
        return self.git(cwd, 'rev-parse', 'HEAD')

    def main_moves(self, name: str, text: str | None = None, *, subject: str | None = None) -> str:
        """Another session lands a commit of its own, outside any worklog."""
        self.git(self.peer, 'fetch', '-q', 'origin')
        self.git(self.peer, 'switch', '-q', '--detach', 'origin/main')
        sha = self.commit(self.peer, name, text, subject=subject, CLAUDE_CODE_SESSION_ID='')
        self.git(self.peer, 'push', '-q', 'origin', 'HEAD:main')
        return sha

    def races(self, count: int) -> None:
        Path(self.env['RACES']).write_text(f'{count}\n')

    def main(self) -> str:
        return self.git(self.origin, 'rev-parse', 'main')

    def parents(self, sha: str) -> list[str]:
        return self.git(self.origin, 'rev-list', '--parents', '-n', '1', sha).split()[1:]

    def first_parent_line(self) -> list[str]:
        return self.git(self.origin, 'rev-list', '--first-parent', 'main').splitlines()

    def merges_on_main(self) -> list[str]:
        return self.git(self.origin, 'rev-list', '--merges', 'main').splitlines()

    def on_main(self, sha: str) -> bool:
        asked = subprocess.run(['git', 'merge-base', '--is-ancestor', sha, 'main'], cwd=self.origin, env=self.env, capture_output=True)
        return asked.returncode == 0

    def linked(self) -> list[str]:
        """Each sha the worklog hook linked, in the order it linked them."""
        links = Path(self.env['LINKS'])
        lines = links.read_text().splitlines() if links.exists() else []
        return [line.split('--commit ', 1)[1].split()[0] for line in lines]

    def checked_subjects(self) -> list[str]:
        checked = Path(self.env['CHECKED'])
        return checked.read_text().splitlines() if checked.exists() else []

    def branch_of(self, worktree: Path) -> str | None:
        """The branch HEAD names, or None where HEAD is detached."""
        asked = subprocess.run(
            ['git', 'symbolic-ref', '--quiet', '--short', 'HEAD'], cwd=worktree, env=self.env, capture_output=True, text=True
        )
        return asked.stdout.strip() if asked.returncode == 0 else None


@pytest.fixture
def rig(tmp_path: Path) -> Rig:
    home = tmp_path / 'home'
    bin_dir = tmp_path / 'bin'
    for directory in (home, bin_dir):
        directory.mkdir()
    write_executable(bin_dir / 'slate', STAND_IN_SLATE)
    # `new` runs a repo's `task setup` where it declares one. These repos declare
    # nothing, and a stub says so without asking whatever `task` the machine has.
    write_executable(bin_dir / 'task', '#!/bin/sh\nexit 1\n')
    hooks_into(tmp_path / 'hooks')

    config = tmp_path / 'gitconfig'
    config.write_text(f'[core]\n\thooksPath = {tmp_path / "hooks"}\n[init]\n\tdefaultBranch = main\n[advice]\n\tdetachedHead = false\n')

    env = {
        'PATH': f'{bin_dir}{os.pathsep}{os.environ["PATH"]}',
        'HOME': str(home),
        'XDG_CONFIG_HOME': str(home / '.config'),
        'XDG_STATE_HOME': str(home / '.local' / 'state'),
        'GIT_CONFIG_GLOBAL': str(config),
        'GIT_CONFIG_NOSYSTEM': '1',
        'GIT_EDITOR': 'true',
        'LC_ALL': UTF8_LOCALE,
        'UV_CACHE_DIR': UV_CACHE,
        'UV_PYTHON_INSTALL_DIR': UV_PYTHONS,
        'WORKTREE_ROOT': str(tmp_path / 'worktrees'),
        'CLAUDE_CODE_SESSION_ID': SESSION,
        'WORKLOG': WORKLOG,
        'LINKS': str(tmp_path / 'links'),
        'SHELL_DIR': str(HOOK_LIBRARY),
        'CHECKED': str(tmp_path / 'checked'),
        'RACES': str(tmp_path / 'races'),
        'PEER': str(tmp_path / 'peer'),
    }
    if 'TMPDIR' in os.environ:
        env['TMPDIR'] = os.environ['TMPDIR']

    # Both hooks skip an origin with no host, so a fixture repo asks slate nothing.
    # git reads a path with a slash before its first colon as a local path, so this
    # origin pushes like any directory and reads to the hooks as a host's.
    origin = tmp_path / 'origin:' / 'dotfiles.git'
    checkout = tmp_path / 'dotfiles'
    rig = Rig(root=tmp_path, env=env, origin=origin, checkout=checkout, peer=tmp_path / 'peer')
    origin.parent.mkdir()
    rig.git(tmp_path, 'init', '-q', '--bare', '-b', 'main', str(origin))
    rig.git(tmp_path, 'clone', '-q', str(origin), str(checkout))
    rig.commit(checkout, 'f.txt', 'base\n', subject='chore: init', CLAUDE_CODE_SESSION_ID='')
    rig.git(checkout, 'push', '-q', 'origin', 'main')
    rig.git(checkout, 'remote', 'set-head', 'origin', '-a')
    rig.git(tmp_path, 'clone', '-q', str(origin), str(rig.peer))
    return rig


def assert_landed(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, f'{result.stdout}\n{result.stderr}'


def assert_every_linked_commit_is_on_main(rig: Rig) -> None:
    linked = rig.linked()
    assert linked, 'the worklog hook linked nothing, so the claim was never exercised'
    assert [sha for sha in linked if not rig.on_main(sha)] == []


class TestLandingKeepsEveryRecordedSha:
    def test_main_unmoved_fast_forwards_and_lands_the_commits_as_made(self, rig):
        alpha = rig.new('alpha')
        made = [rig.commit(alpha, 'a.txt'), rig.commit(alpha, 'b.txt')]

        result = rig.land(alpha)

        assert_landed(result)
        assert rig.main() == made[-1]
        assert rig.merges_on_main() == []
        assert rig.linked() == made
        assert 'Landed 2 commit(s) on main' in result.stderr
        assert not alpha.exists()
        assert rig.git(rig.checkout, 'branch', '--list', 'alpha') == ''

    def test_main_moved_lands_one_merge_with_main_as_its_first_parent(self, rig):
        alpha = rig.new('alpha')
        made = rig.commit(alpha, 'a.txt')
        moved = rig.main_moves('elsewhere.txt')

        result = rig.land(alpha)

        assert_landed(result)
        merge = rig.main()
        assert rig.parents(merge) == [moved, made]
        assert rig.first_parent_line()[:2] == [merge, moved]
        message = rig.git(rig.origin, 'log', '-1', '--format=%B', merge)
        assert message.splitlines()[0] == 'chore: merge alpha into main'
        assert '* alpha:\n  feat: a.txt' in message, 'the body is the --log list of what the merge carries'
        assert f'merged as {merge}' in result.stderr
        assert_every_linked_commit_is_on_main(rig)

    def test_a_branch_that_merged_main_in_lands_with_main_as_its_first_parent(self, rig):
        """A session catches its branch up by merging main in, then lands it.

        The branch then holds main as a second parent, so a fast-forward onto it would put
        the branch's commits first on main's line and move the landing it merged off it."""
        alpha = rig.new('alpha')
        rig.commit(alpha, 'a.txt')
        moved = rig.main_moves('elsewhere.txt')
        rig.git(alpha, 'fetch', '-q', 'origin')
        # A body keeps the subject a paragraph of its own: 2.39 stamps a lone merge subject's trailers onto it.
        rig.git(alpha, 'merge', '-q', '--no-ff', '-m', 'chore: merge main into alpha', '-m', 'Catch alpha up.', 'origin/main')
        caught_up = rig.git(alpha, 'rev-parse', 'HEAD')

        result = rig.land(alpha)

        assert_landed(result)
        merge = rig.main()
        assert rig.parents(merge) == [moved, caught_up]
        assert rig.first_parent_line()[:2] == [merge, moved]
        assert_every_linked_commit_is_on_main(rig)

    def test_work_main_already_holds_is_refused_and_nothing_moves(self, rig):
        """A squash or a cherry-pick leaves main with the work under other shas."""
        alpha = rig.new('alpha')
        rig.commit(alpha, 'x.txt', 'same\n')
        before = rig.main_moves('x.txt', 'same\n', subject='feat: x.txt (#1)')

        result = rig.land(alpha)

        assert result.returncode == 1
        assert rig.main() == before
        assert rig.branch_of(alpha) == 'alpha'

    @pytest.mark.parametrize('committed_by', ['land', 'session'])
    def test_a_conflict_stops_inside_the_merge_and_lands_once_resolved(self, rig, committed_by):
        alpha = rig.new('alpha')
        made = rig.commit(alpha, 'f.txt', 'alpha wins\n')
        moved = rig.main_moves('f.txt', 'main wins\n')

        stopped = rig.land(alpha)

        assert stopped.returncode == 1
        assert 'f.txt' in stopped.stderr, 'the refusal names the conflicted path'
        assert rig.git(alpha, 'rev-parse', 'MERGE_HEAD') == made, "git's own merge state holds the resolution in progress"
        assert rig.git(alpha, 'rev-parse', 'refs/heads/alpha') == made
        assert rig.main() == moved

        (alpha / 'f.txt').write_text('both\n')
        rig.git(alpha, 'add', 'f.txt')
        if committed_by == 'session':
            rig.git(alpha, 'commit', '-q', '--no-edit')
        result = rig.land(alpha)

        assert_landed(result)
        resolved = rig.main()
        assert rig.parents(resolved) == [moved, made]
        assert rig.linked()[-1] == resolved, 'committing a resolution fires post-commit, which links it'
        assert rig.git(rig.origin, 'show', f'{resolved}:f.txt') == 'both'
        assert_every_linked_commit_is_on_main(rig)

    def test_a_lost_race_makes_the_merge_again_on_the_new_main(self, rig):
        alpha = rig.new('alpha')
        made = rig.commit(alpha, 'a.txt')
        moved = rig.main_moves('elsewhere.txt')
        rig.races(1)

        result = rig.land(alpha)

        assert_landed(result)
        merge, winner, *rest = rig.first_parent_line()
        assert rest[0] == moved
        assert rig.parents(merge) == [winner, made]
        assert rig.merges_on_main() == [merge], 'the merge that lost was never pushed'
        assert_every_linked_commit_is_on_main(rig)

    def test_a_lost_race_after_a_resolution_merges_the_new_main_onto_it(self, rig):
        alpha = rig.new('alpha')
        made = rig.commit(alpha, 'f.txt', 'alpha wins\n')
        moved = rig.main_moves('f.txt', 'main wins\n')
        assert rig.land(alpha).returncode == 1
        (alpha / 'f.txt').write_text('both\n')
        rig.git(alpha, 'add', 'f.txt')
        rig.races(1)

        result = rig.land(alpha)

        assert_landed(result)
        resolved = rig.linked()[-1]
        assert rig.parents(resolved) == [moved, made], 'the resolution is kept as committed'
        merge, winner, *_ = rig.first_parent_line()
        assert rig.parents(merge) == [winner, resolved]
        assert_every_linked_commit_is_on_main(rig)

    def test_main_moving_on_every_push_refuses_once_the_tries_run_out(self, rig):
        alpha = rig.new('alpha')
        made = rig.commit(alpha, 'a.txt')
        rig.races(2)

        result = rig.land(alpha)

        assert result.returncode == 1
        assert Path(rig.env['RACES']).read_text().strip() == '0', 'each push it tried lost a race'
        assert not rig.on_main(made)
        assert rig.branch_of(alpha) == 'alpha'

    def test_a_push_that_fails_for_another_reason_says_what_git_said_and_keeps_the_branch(self, rig):
        alpha = rig.new('alpha')
        made = rig.commit(alpha, 'a.txt')
        moved = rig.main_moves('elsewhere.txt')
        rig.git(rig.checkout, 'config', 'remote.origin.pushurl', str(rig.root / 'unreachable.git'))

        refused = rig.land(alpha)

        assert refused.returncode == 1
        assert 'unreachable.git' in refused.stderr, "git's own line says what failed"
        assert rig.main() == moved
        assert rig.branch_of(alpha) == 'alpha'
        assert rig.git(alpha, 'rev-parse', 'HEAD') == made

        rig.git(rig.checkout, 'config', '--unset', 'remote.origin.pushurl')
        assert_landed(rig.land(alpha))
        assert rig.parents(rig.main()) == [moved, made]

    def test_a_land_killed_before_its_push_lands_from_the_branch_next_time(self, rig):
        alpha = rig.new('alpha')
        made = rig.commit(alpha, 'a.txt')
        moved = rig.main_moves('elsewhere.txt')

        killed = rig.killed_land(alpha)

        assert killed.returncode != 0
        assert rig.main() == moved
        assert rig.branch_of(alpha) is None, 'the run died on the detached merge it made'

        result = rig.land(alpha)

        assert_landed(result)
        assert rig.parents(rig.main()) == [moved, made]
        assert_every_linked_commit_is_on_main(rig)

    def test_a_stacked_child_lands_after_its_parent_and_both_keep_their_shas(self, rig):
        parent = rig.new('parent')
        below = rig.commit(parent, 'p.txt')
        child = rig.root / 'worktrees' / 'dotfiles' / 'child'
        rig.git(rig.checkout, 'worktree', 'add', '-q', '-b', 'child', str(child), 'parent')
        above = rig.commit(child, 'c.txt')
        rig.main_moves('elsewhere.txt')

        assert_landed(rig.land(parent))
        assert_landed(rig.land(child))

        landed_child, landed_parent, *_ = rig.first_parent_line()
        assert rig.parents(landed_parent)[1] == below
        assert rig.parents(landed_child) == [landed_parent, above]
        assert rig.on_main(below) and rig.on_main(above)


class TestTheMergeRunsTheCommitHooks:
    def test_a_clean_merge_is_stamped_checked_and_never_linked(self, rig):
        """A clean `git merge` fires prepare-commit-msg and commit-msg, and no post-commit.

        Whether the stamp reads back as a trailer depends on the git that wrote it.
        2.39's interpret-trailers takes the `--log` list for a trailer block and
        appends to it, where 2.53 starts a paragraph of its own. Every
        machine declares the trailer hook in config, which no git that old runs, so
        the read-back is asserted only where such a git would run it.
        """
        alpha = rig.new('alpha')
        rig.commit(alpha, 'a.txt')
        rig.main_moves('elsewhere.txt')

        assert_landed(rig.land(alpha))

        merge = rig.main()
        assert f'Agent-Session: {SESSION}' in rig.git(rig.origin, 'log', '-1', '--format=%B', merge)
        if runs_hooks_set_in_config():
            trailers = rig.git(rig.origin, 'log', '-1', '--format=%(trailers:only)', merge)
            assert f'Agent-Session: {SESSION}' in trailers
            assert f'Worklog: {WORKLOG}' in trailers
        assert rig.checked_subjects()[-1] == 'chore: merge alpha into main'
        assert merge not in rig.linked()


class TestThePrimaryCheckoutCatchesUpByFastForward:
    def test_a_clean_checkout_on_main_fast_forwards(self, rig):
        alpha = rig.new('alpha')
        made = rig.commit(alpha, 'a.txt')

        result = rig.land(alpha)

        assert_landed(result)
        assert rig.git(rig.checkout, 'rev-parse', 'HEAD') == made

    @pytest.mark.parametrize('busy', ['dirty', 'elsewhere', 'diverged'])
    def test_a_checkout_it_cannot_fast_forward_is_left_as_it_was(self, rig, busy):
        alpha = rig.new('alpha')
        rig.commit(alpha, 'a.txt')
        if busy == 'dirty':
            (rig.checkout / 'f.txt').write_text('someone is editing this\n')
        elif busy == 'elsewhere':
            rig.git(rig.checkout, 'switch', '-q', '-c', 'elsewhere')
        else:
            rig.commit(rig.checkout, 'local.txt', CLAUDE_CODE_SESSION_ID='')
        before = rig.git(rig.checkout, 'rev-parse', 'HEAD')

        result = rig.land(alpha)

        assert_landed(result)
        assert rig.git(rig.checkout, 'rev-parse', 'HEAD') == before
        if busy == 'dirty':
            assert (rig.checkout / 'f.txt').read_text() == 'someone is editing this\n'
