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
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
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

    def _run(cwd: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        env = {
            'HOME': str(tmp_path),
            'PATH': f'{bin_dir}:{os.environ["PATH"]}',
            'LC_ALL': UTF8_LOCALE,
            'UV_CACHE_DIR': UV_CACHE,
            'WORKTREE_ROOT': str(fleet['roots']),
        } | (env or {})
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


def rewrite_onto_main(clone: Path, worktree: Path, name: str) -> None:
    """Put this branch's content on main under a sha the branch has never held.

    What a squash merge leaves behind, and what GitHub's "update with rebase" leaves
    behind: main carries the work, and the local ref still points at the commits the
    work was written as. Pushing `HEAD:main` from the worktree is the shape this
    cannot be — that puts the branch's own commits on main, which is the merge that
    already worked.

    The subject carries a PR number, as GitHub's squash subject does. Without something
    to differ on this commit is byte-identical to the branch's own — same tree, same
    parent, same message, same second — so git hands back the sha that already exists
    and the fixture quietly builds the clean merge instead.
    """
    (clone / name).write_text((worktree / name).read_text())
    git(clone, 'add', name)
    git(clone, 'commit', '-qm', f'feat: {name} (#1)')
    git(clone, 'push', '-q', 'origin', 'main')


def rewritten_worktree(clone: Path, roots: Path, run: Any, branch: str) -> Path:
    """A worktree whose work merged under different shas, with its remote branch gone.

    The bug this shape produced: `origin/main..HEAD` counts commits that will never be
    in main's history, so the count stays above zero for as long as the directory
    exists and every sweep keeps it for having unlanded work.
    """
    run(clone, 'new', branch)
    worktree = roots / clone.name / branch
    commit_in(worktree, f'{branch}.txt')
    publish(clone, worktree, branch)
    rewrite_onto_main(clone, worktree, f'{branch}.txt')
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
    fields: dict[str, Any] = {'published': True, 'fetched': True, 'remote': frozenset(), 'landed': True}
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
        (app.Kept.UNREADABLE_LANDING, {'ahead': 2}, {'landed': None}),
        (app.Kept.UNLANDED, {'ahead': 2}, {'landed': False}),
        (app.Kept.UNPUBLISHED, {}, {'published': False}),
        (app.Kept.REMOTE_UNREADABLE, {}, {'remote': None}),
        (app.Kept.REMOTE_LIVE, {}, {'remote': frozenset({'alpha'})}),
    ]


def rows(result: subprocess.CompletedProcess[str]) -> list[str]:
    """The listing's data rows, with the column header dropped."""
    return plain(result.stdout).splitlines()[1:]


TMUX = shutil.which('tmux')

RIG_COLUMNS = 200
"""How wide the rig's window is, so a layout claim can be a share of it rather than a
comparison between two panes. `split-window -h` halves a pane on its own, so "the caller
is wider than what it spawned" is true with the sizing removed."""

CLAUDE_STUB = r"""
__PREAMBLE__
printf '%s' "$TMUX_PANE" > "__STATE__/pane"
printf '%s' "$$" > "__STATE__/pid"
pwd > "__STATE__/cwd"
printf '%s' "$*" > "__STATE__/prompt"
__BODY__
"""
"""A `claude` that records where tmux put it before doing whatever the case needs.

Recording the pane is what lets the registry stub below be honest about *when* a session
exists: nothing is reported as running until the pane has really started something, which
is the ordering the poll in `await_registration` is written against. A stub that reported
the session immediately would pass whatever the poll did.

`$$` is its own pid, and it is the pid tmux reports for the pane because a pane command
is exec'd through `sh -c` rather than forked. Writing it here is what makes the registry's
`pid` field agree with `#{pane_pid}`, which is the machine this test rig has to reproduce.
"""

REGISTRY_STUB = r"""
state="__STATE__"
out=""
add() { if [ -n "$out" ]; then out="$out,$1"; else out="$1"; fi; }
preset=$(cat "$state/preset" 2>/dev/null || true)
[ -n "$preset" ] && add "$preset"
head='"sessionId":"x","status":"idle","waiting":null,'
if [ -f "$state/pane" ]; then
  pane=$(cat "$state/pane")
  if [ -f "$state/phantom" ]; then
    tail=$(printf '"cwd":"/nowhere","tmux":"gone:@11.%s","pid":999999}' "$pane")
    add "{\"name\":\"phantom\",$head$tail"
  fi
  if [ -f "$state/drop-pid" ]; then
    tail=$(printf '"cwd":"%s","tmux":"gone:@9.%s"}' "$(cat "$state/cwd")" "$pane")
  else
    tail=$(printf '"cwd":"%s","tmux":"gone:@9.%s","pid":%s}' "$(cat "$state/cwd")" "$pane" "$(cat "$state/pid")")
  fi
  add "{\"name\":\"spawned\",$head$tail"
fi
printf '[%s]' "$out"
"""
"""A `claude-sessions` that reports the spawned session once its pane is running.

`gone:@9` is neither the rig's tmux session nor a window it has, and both halves are wrong
on purpose. A pane moved with `tmux join-pane` keeps its id and takes a new window, and a
new tmux session too when it is moved between them — while the registry keeps the address
it recorded at startup. So a matcher comparing the whole address fails on every moved
pane, and every success here also asserts that only the pane id is compared.

`<state>/phantom` adds a second row claiming the same pane with a pid that is not the
pane's, which is what a `claude` started from inside another session's pane looks like in
the registry. It is emitted ahead of the real row, so a matcher that answered with the
first claimant would fail rather than pass by luck.

`<state>/drop-pid` emits the row without its `pid` at all, which is the sibling app's
output changing shape. The stub writes that field itself, so nothing else here would
notice the real producer dropping it.

Rows in `<state>/preset` are whatever was already on the machine, comma-separated and
without their brackets, so a case can put a session somewhere before spawning into it.
"""


@dataclass(frozen=True)
class Rig:
    """A tmux server of its own, and the pane a spawn is told to split."""

    socket: Path
    caller: str

    def tmux(self, *args: str) -> str:
        return subprocess.run([str(TMUX), '-S', str(self.socket), *args], capture_output=True, text=True).stdout.strip()

    def panes(self) -> list[str]:
        return self.tmux('list-panes', '-a', '-F', '#{pane_id}').splitlines()

    def geometry(self) -> dict[str, tuple[int, int, int]]:
        """left, top and width per pane, which is how a layout claim is asserted.

        The layout is what the panes are *for* — a caller squeezed into 80 columns is the
        failure this sizing exists to stop — so it is measured off tmux rather than off
        the arguments the tool passed it.
        """
        listed = self.tmux('list-panes', '-a', '-F', '#{pane_id} #{pane_left} #{pane_top} #{pane_width}')
        found = {}
        for line in listed.splitlines():
            pane, left, top, width = line.split()
            found[pane] = (int(left), int(top), int(width))
        return found

    def spawned(self) -> str:
        """The one pane that is not the caller's."""
        others = [pane for pane in self.panes() if pane != self.caller]
        assert len(others) == 1, f'expected exactly one spawned pane, got {others}'
        return others[0]

    def window_of(self, pane: str) -> str:
        return self.tmux('display-message', '-p', '-t', pane, '#{window_id}')

    def add_pane_before_the_caller(self) -> str:
        """Put an unrelated pane at index 0, so the caller no longer leads its window.

        That is the ordinary arrangement rather than a contrivance — a session is rarely
        the first pane of the window it is in — and a rig that only ever makes the caller
        pane 0 cannot see a layout handing the main pane to somebody else.
        """
        before = set(self.panes())
        self.tmux('split-window', '-d', '-b', '-h', '-t', self.caller, '-c', '/tmp', 'sleep 300')
        return (set(self.panes()) - before).pop()


@pytest.fixture
def spawn_state(tmp_path: Path) -> Path:
    """Where the stub `claude` records the pane and directory tmux started it in."""
    state = tmp_path / 'spawned'
    state.mkdir()
    return state


@pytest.fixture
def rig(tmp_path: Path, tmux_socket: Path, bin_dir: Path, spawn_state: Path):
    """A throwaway tmux server, with a `tmux` on PATH that can only reach it.

    The binary is shadowed rather than the socket passed through, because the app calls
    plain `tmux` and that is the invocation worth testing. A rig that handed it a `-S`
    would be measuring a command the machine never runs.

    The server is started carrying the stub directory on PATH: a pane inherits the
    server's environment, and the pane is where the stub `claude` has to be found.

    The socket sits outside `tmp_path`, which stays the rig's `$HOME` and working
    directory. `tmux_socket` holds the length limit that forces the split.
    """
    socket = tmux_socket
    server = os.environ | {'PATH': f'{bin_dir}:{os.environ["PATH"]}', 'HOME': str(tmp_path)}
    subprocess.run(
        [str(TMUX), '-S', str(socket), 'new-session', '-d', '-s', 'rig', '-x', str(RIG_COLUMNS), '-y', '50', '-c', str(tmp_path)],
        check=True,
        capture_output=True,
        env=server,
    )
    write_stub(bin_dir, 'tmux', f'exec {TMUX} -S {socket} "$@"')
    stub_claude(bin_dir, spawn_state)
    stub_registry(bin_dir, spawn_state)

    caller = subprocess.run(
        [str(TMUX), '-S', str(socket), 'display-message', '-p', '-t', 'rig', '#{pane_id}'],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    yield Rig(socket=socket, caller=caller)
    subprocess.run([str(TMUX), '-S', str(socket), 'kill-server'], capture_output=True)


def stub_claude(bin_dir: Path, spawn_state: Path, body: str = 'exec sleep 300', preamble: str = ':') -> None:
    """A `claude` that runs `preamble`, records where tmux put it, then runs `body`.

    The preamble runs before the recording so a case can change the machine in the window
    between the split and the moment the session becomes findable.
    """
    script = CLAUDE_STUB.replace('__PREAMBLE__', preamble).replace('__STATE__', str(spawn_state)).replace('__BODY__', body)
    write_stub(bin_dir, 'claude', script)


def stub_registry(bin_dir: Path, spawn_state: Path) -> None:
    write_stub(bin_dir, 'claude-sessions', REGISTRY_STUB.replace('__STATE__', str(spawn_state)))


def preset_session(spawn_state: Path, name: str, cwd: Path, pane: str) -> None:
    """Put a session on the machine before the spawn, as one row of the registry."""
    row = f'{{"name":"{name}","sessionId":"p","status":"idle","waiting":null,"cwd":"{cwd}","tmux":"rig:@0.{pane}","pid":1}}'
    (spawn_state / 'preset').write_text(row)


def brief_at(path: Path, text: str = 'Do the thing. Report to claude-73.\n') -> Path:
    path.write_text(text)
    return path


@pytest.fixture
def spawn(run: Any, rig: Rig, tmp_path: Path):
    """Invoke `spawn` as a session inside the rig's caller pane would.

    $TMUX and $TMUX_PANE are what tmux exports into everything it starts, so this is the
    environment the command really runs in rather than arguments invented for the test.
    """

    def _spawn(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return run(cwd, 'spawn', *args, env={'TMUX': str(rig.socket), 'TMUX_PANE': rig.caller})

    return _spawn


def briefs_in(tmp_path: Path) -> list[Path]:
    """Every brief the tool kept, under the state directory $HOME resolves to."""
    kept = tmp_path / '.local' / 'state' / 'worktree' / 'briefs'
    return sorted(kept.iterdir()) if kept.is_dir() else []


def claim_the_pane(spawn_state: Path) -> None:
    """Put a second registry row on the pane the spawn is about to create."""
    (spawn_state / 'phantom').touch()


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

        landed = run(alpha, 'land')

        assert landed.returncode == 0, landed.stderr
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

    def test_dropping_when_the_base_branch_cannot_be_read_refuses_without_naming_a_verdict(self, fleet, run):
        """A landing git could not measure is not an unlanded one, and `drop` is the
        caller where the difference is visible.

        Reporting it as unlanded would send the reader to `worktree land`, which cannot
        run against a base branch that is not there. The refusal says what is unknown
        and leaves --force as the way past it.
        """
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        commit_in(alpha, 'x')
        git(fleet['primary'], 'update-ref', '-d', 'refs/remotes/origin/main')
        git(fleet['primary'], 'symbolic-ref', '-d', 'refs/remotes/origin/HEAD')

        result = run(alpha, 'drop')

        assert result.returncode != 0
        assert alpha.exists()
        assert 'Cannot tell whether the work here is already on origin/main' in plain(result.stderr)

    def test_dropping_a_rewritten_history_that_landed_needs_no_force(self, fleet, run):
        """A history rewritten on its way onto the base carries new shas, so the local
        ref still counts the originals. `drop` reads content rather than that count,
        so it needs no --force here."""
        alpha = rewritten_worktree(fleet['primary'], fleet['roots'], run, 'alpha')

        result = run(alpha, 'drop')

        assert result.returncode == 0
        assert not alpha.exists()

    def test_landing_work_that_is_already_on_the_base_branch_is_refused(self, fleet, run):
        """The rebase would replay patches whose content main already carries, and the
        push would put a second copy of merged work on it.

        Asserted against origin rather than the exit code alone: a refusal that still
        moved the base branch is the failure this is about.
        """
        alpha = rewritten_worktree(fleet['primary'], fleet['roots'], run, 'alpha')
        before = git(fleet['primary'], 'rev-parse', 'origin/main')

        result = run(alpha, 'land')

        assert result.returncode != 0
        assert 'already on origin/main' in plain(result.stderr)
        assert git(fleet['primary'], 'rev-parse', 'origin/main') == before

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


class TestLanded:
    """The read that replaced the commit count, against repositories rather than fakes.

    `held_by` is where the decision is asserted and it takes this as a boolean, so a
    class of fakes can never say whether git answers what the boolean claims. These
    cases build each shape in a real repository and ask.
    """

    def test_a_branch_merged_under_its_own_shas_has_landed(self, worktree_app, fleet, run):
        """The ordinary merge, and the case the commit count was already right about."""
        alpha = merged_worktree(fleet['primary'], fleet['roots'], run, 'alpha')

        assert git(alpha, 'rev-list', '--count', 'origin/main..HEAD') == '0'
        assert worktree_app.landed(alpha, 'main') is True

    def test_a_branch_merged_under_new_shas_has_landed(self, worktree_app, fleet, run):
        """The bug. Ancestry says no and the count says four, and both are honest —
        the shas here are not the shas that reached main. The content is."""
        alpha = rewritten_worktree(fleet['primary'], fleet['roots'], run, 'alpha')

        ancestry = subprocess.run(['git', 'merge-base', '--is-ancestor', 'HEAD', 'origin/main'], cwd=alpha, capture_output=True)

        assert git(alpha, 'rev-list', '--count', 'origin/main..HEAD') != '0'
        assert ancestry.returncode != 0, 'the fixture has to leave the tip off main, or this proves nothing'
        assert worktree_app.landed(alpha, 'main') is True

    def test_a_branch_whose_work_is_nowhere_else_has_not_landed(self, worktree_app, fleet, run):
        alpha = fleet['roots'] / 'primary' / 'alpha'
        run(fleet['primary'], 'new', 'alpha')
        commit_in(alpha, 'only-copy.txt')

        assert worktree_app.landed(alpha, 'main') is False

    def test_a_rename_whose_deletion_never_landed_has_not_landed(self, worktree_app, fleet, run):
        """Rename detection reports a rename as the new path alone, so the old path
        never enters the comparison and a base branch that took only the addition reads
        as having the whole change.

        Here main gained the new file and kept the original. The branch's deletion of
        the original is on no other branch, and removing the worktree would lose it.
        """
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        git(alpha, 'mv', 'f.txt', 'g.txt')
        git(alpha, 'commit', '-qm', 'refactor: rename f to g')
        (fleet['primary'] / 'g.txt').write_text('base\n')
        git(fleet['primary'], 'add', 'g.txt')
        git(fleet['primary'], 'commit', '-qm', 'feat: add g (#1)')
        git(fleet['primary'], 'push', '-q', 'origin', 'main')
        git(alpha, 'fetch', '-q', 'origin')

        assert worktree_app.landed(alpha, 'main') is False

    def test_a_deletion_the_base_branch_took_has_landed(self, worktree_app, fleet, run):
        """The other half of asking about a path the branch no longer has. Both sides
        are missing it, so there is nothing here that is not there."""
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        git(alpha, 'rm', '-q', 'f.txt')
        git(alpha, 'commit', '-qm', 'refactor: drop f')
        git(fleet['primary'], 'rm', '-q', 'f.txt')
        git(fleet['primary'], 'commit', '-qm', 'refactor: drop f (#1)')
        git(fleet['primary'], 'push', '-q', 'origin', 'main')
        git(alpha, 'fetch', '-q', 'origin')

        assert worktree_app.landed(alpha, 'main') is True

    def test_a_mode_the_base_branch_did_not_take_has_not_landed(self, worktree_app, fleet, run):
        """Every byte of every touched path matches and the branch has still not
        landed. What differs is the file mode, which is tracked and is work."""
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        git(alpha, 'update-index', '--chmod=+x', 'f.txt')
        git(alpha, 'commit', '-qm', 'chore: make f executable')

        blobs = (git(alpha, 'rev-parse', 'origin/main:f.txt'), git(alpha, 'rev-parse', 'HEAD:f.txt'))

        assert blobs[0] == blobs[1], 'one blob on both sides, so the mode is the only thing left to differ'
        assert worktree_app.landed(alpha, 'main') is False

    def test_each_path_git_cannot_print_plainly_is_still_compared(self, worktree_app, fleet, run):
        """git's default listing is not the names. It C-quotes any path holding a
        non-ASCII byte, a quote, a backslash or a control character, and the strip that
        reads an ordinary git answer takes a leading or trailing space off the rest.

        A name that arrives in any of those forms selects no file as a pathspec, so the
        comparison finds no difference and the branch reads as landed. Each of these is
        its own worktree, so a failure names the character that got through rather than
        reporting that one of five did.
        """
        awkward = {
            'leading-space': ' leading.txt',
            'non-ascii': 'café.txt',
            'double-quote': 'say "hi".txt',
            'backslash': 'back\\slash.txt',
            'pathspec-magic': 'star*.txt',
        }

        for slug, name in awkward.items():
            run(fleet['primary'], 'new', slug)
            worktree = fleet['roots'] / 'primary' / slug
            (worktree / name).write_text('only copy\n')
            git(worktree, 'add', name)
            git(worktree, 'commit', '-qm', f'feat: {slug}')

            assert worktree_app.landed(worktree, 'main') is False, name

    def test_a_rename_across_names_git_quotes_needs_both_guards_at_once(self, worktree_app, fleet, run):
        """The one shape where dropping either guard on its own loses the work.

        Rename detection alone would report the new path and the base branch has that
        path, so the branch reads as landed while its deletion of the old one is on no
        other branch. Reading the listing as text alone would hand back two quoted names
        that select nothing, which reads as landed for the same reason by another route.

        The two other tests each hold one guard and would stay green without the other:
        the rename case uses ASCII names, and the quoted-names case adds files rather
        than renaming them.
        """
        body = 'a body long enough for rename detection to latch onto\nand more of it\n'
        (fleet['primary'] / 'æ file.txt').write_text(body)
        git(fleet['primary'], 'add', 'æ file.txt')
        git(fleet['primary'], 'commit', '-qm', 'feat: add a non-ascii name')
        git(fleet['primary'], 'push', '-q', 'origin', 'main')

        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        git(alpha, 'mv', 'æ file.txt', 'ø other.txt')
        git(alpha, 'commit', '-qm', 'refactor: rename it')

        (fleet['primary'] / 'ø other.txt').write_text(body)
        git(fleet['primary'], 'add', 'ø other.txt')
        git(fleet['primary'], 'commit', '-qm', 'feat: take the addition and keep the original (#1)')
        git(fleet['primary'], 'push', '-q', 'origin', 'main')
        git(alpha, 'fetch', '-q', 'origin')

        assert worktree_app.landed(alpha, 'main') is False

    def test_a_branch_whose_commits_net_out_to_nothing_has_landed(self, worktree_app, fleet, run):
        """Decided rather than left to whichever way the code happens to fall.

        Two commits that cancel leave the base branch's content untouched, so a removal
        takes the commits and no work. Every other case here errs toward keeping,
        because every other case has work at stake.
        """
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        commit_in(alpha, 'transient.txt')
        git(alpha, 'rm', '-q', 'transient.txt')
        git(alpha, 'commit', '-qm', 'revert: drop transient.txt')

        assert git(alpha, 'rev-list', '--count', 'origin/main..HEAD') == '2'
        assert worktree_app.landed(alpha, 'main') is True

    def test_a_base_branch_that_was_never_fetched_is_unanswerable(self, worktree_app, fleet, run):
        """None rather than False. `sweep` holds the worktree either way, but `drop`
        tells a human to go and look instead of claiming the work is unlanded."""
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'

        assert worktree_app.landed(alpha, 'no-such-base') is None

    def test_a_base_branch_that_moved_on_over_the_same_file_reads_as_unlanded(self, worktree_app, fleet, run):
        """The conservative half of the content comparison, stated so it is a decision
        rather than a surprise.

        The changes did land and main has since edited the same file, so the paths no
        longer match and the worktree is kept. Keeping a finished worktree costs a
        directory; sweeping an unfinished one costs the work in it.
        """
        alpha = rewritten_worktree(fleet['primary'], fleet['roots'], run, 'alpha')
        (fleet['primary'] / 'alpha.txt').write_text('main moved on\n')
        git(fleet['primary'], 'commit', '-qam', 'feat: revise alpha.txt')
        git(fleet['primary'], 'push', '-q', 'origin', 'main')
        git(alpha, 'fetch', '-q', 'origin')

        assert worktree_app.landed(alpha, 'main') is False


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
        """The four reads that can fail, each proved to hold the worktree rather than
        resolve to a falsy value the next check walks past.

        This is the direction that costs work: `held_by` ends in *remove*, so a failed
        read that returns an empty tuple or a missing ref authorises a deletion on the
        strength of a question nobody managed to ask.
        """
        unanswerable = [
            (fake_worktree(worktree_app, '/w/alpha', sessions=None), fake_evidence(worktree_app)),
            (fake_worktree(worktree_app, '/w/alpha'), fake_evidence(worktree_app, fetched=False)),
            (fake_worktree(worktree_app, '/w/alpha'), fake_evidence(worktree_app, remote=None)),
            (fake_worktree(worktree_app, '/w/alpha'), fake_evidence(worktree_app, landed=None)),
        ]

        for worktree, evidence in unanswerable:
            assert worktree_app.held_by(worktree, evidence) is not None

    def test_commits_above_the_base_do_not_hold_a_worktree_whose_work_landed(self, worktree_app):
        """The count is not the question. A history rewritten on its way onto the base
        branch carries new shas, so the branch keeps commits the base will never hold.

        Asserted at four commits ahead because that is the count a real rewrite left,
        and a fix that only cleared zero would pass every other test in this class.
        """
        rewritten = fake_worktree(worktree_app, '/w/alpha', ahead=4)

        assert worktree_app.held_by(rewritten, fake_evidence(worktree_app)) is None

    def test_work_that_never_landed_is_held_however_it_reached_that_state(self, worktree_app):
        """The two shapes `ahead > 0` was protecting, now protected by what it stood in
        for. Neither may be swept.

        The first is the never-pushed branch — one commit, no remote of its own, and the
        worktree is the only copy. The second is the near-miss of the new rule: pushed
        once and deleted on the remote without ever merging, which reads exactly like a
        merged branch until the changes themselves are compared.
        """
        never_pushed = fake_evidence(worktree_app, published=False, landed=False)
        deleted_unmerged = fake_evidence(worktree_app, published=True, remote=frozenset(), landed=False)
        worktree = fake_worktree(worktree_app, '/w/alpha', ahead=1)

        assert worktree_app.held_by(worktree, never_pushed) is worktree_app.Kept.UNLANDED
        assert worktree_app.held_by(worktree, deleted_unmerged) is worktree_app.Kept.UNLANDED


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
        assert git(alpha, 'rev-list', '--count', 'origin/main..HEAD') == '0', 'this is the shape whose tip is on main'

        result = run(fleet['primary'], 'sweep', '--yes')

        assert result.returncode == 0
        assert not alpha.exists()
        assert 'alpha' not in git(fleet['primary'], 'branch', '--format=%(refname:short)').splitlines()

    def test_a_branch_whose_history_was_rewritten_on_the_way_in_is_removed(self, fleet, run):
        """A squash merge, and GitHub's "update with rebase", both put the work on main
        under shas the branch never held. `origin/main..HEAD` counts the originals for
        as long as the directory exists, so the sweep kept it for having unlanded work
        and would have gone on keeping it forever.

        The count is asserted first. Without it this passes for the same reason the
        test above does, and the bug it is here for is invisible.
        """
        alpha = rewritten_worktree(fleet['primary'], fleet['roots'], run, 'alpha')
        assert git(alpha, 'rev-list', '--count', 'origin/main..HEAD') != '0', 'the whole bug is that this is not zero'

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
        and nowhere else, which is the one thing that must never be swept.

        This is the near-miss of the rewritten-history case above, and the two are
        identical on everything except the work: pushed once, deleted on the remote,
        and commits the base branch will never hold. Only comparing the changes
        themselves separates them.
        """
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        commit_in(alpha, 'only-copy.txt')
        publish(fleet['primary'], alpha, 'alpha')
        delete_on_origin(fleet['primary'], 'alpha')

        result = run(fleet['primary'], 'sweep', '--yes')

        assert alpha.exists()
        assert (alpha / 'only-copy.txt').exists()
        assert 'does not match it at the paths it touched' in plain(result.stderr)

    def test_a_branch_deleted_without_merging_is_kept_whatever_its_files_are_called(self, fleet, run):
        """The same shape as the test above, with one file whose name git does not print
        plainly. Reading the listing as text turned that name into something that
        selects nothing, and the sweep removed the directory and force-deleted the
        branch with the only copy of the work in it.
        """
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        (alpha / 'café.txt').write_text('only copy\n')
        git(alpha, 'add', 'café.txt')
        git(alpha, 'commit', '-qm', 'feat: only copy')
        publish(fleet['primary'], alpha, 'alpha')
        delete_on_origin(fleet['primary'], 'alpha')

        result = run(fleet['primary'], 'sweep', '--yes')

        assert alpha.exists()
        assert (alpha / 'café.txt').exists()
        assert 'alpha' in git(fleet['primary'], 'branch', '--format=%(refname:short)').splitlines()
        assert 'does not match it at the paths it touched' in plain(result.stderr)

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

        assert result.returncode != 0
        assert plain(result.stderr).strip() != '', 'the refusal it is withholding from stdout went to stderr'
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
        listed = run(fleet['primary'], 'list', '--json')

        assert listed.returncode == 0, listed.stderr
        assert json.loads(listed.stdout) == []


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
        offered = fed.read_text()

        assert str(populated) in offered, "the named repo's own worktree is still offered"
        assert 'beta' not in offered

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


def stub_failing_claude(bin_dir: Path, status: int, message: str) -> None:
    """A `claude` that never registers, which is what a launch that cannot start looks like.

    It records nothing, so the registry stub keeps answering with an empty machine and the
    poll has only the pane to go on — the condition the pane check exists for.

    The sleep is what makes the case the *diagnosable* one. `remain-on-exit` is turned on
    a moment after the split, and a command that dies instantly beats it, leaving a pane
    that is simply gone. Both are reported as a launch that died; only the slower one has
    an exit status left to read, and that is the half worth pinning.
    """
    write_stub(bin_dir, 'claude', f'echo "{message}" >&2\nsleep 0.3\nexit {status}')


def stub_silent_claude(bin_dir: Path) -> None:
    """A `claude` that runs forever and never registers, which is what a timeout is."""
    write_stub(bin_dir, 'claude', 'exec sleep 300')


@pytest.mark.interpreter('tmux')
class TestSpawnScope:
    """A slug is the branch, so its presence is what decides whether a worktree is cut.

    `cli-design.md` § "Scope is structural: the argument's presence selects it, never a
    flag" is the rule, and the two forms are not variations on one another — a worker
    needs an index nobody else is in, and a reviewer needs to be able to read a repo from
    outside a worktree, because a session inside one is refused any `git -C` that leaves it.
    """

    def test_a_slug_cuts_a_worktree_and_stands_the_session_in_it(self, fleet, spawn, spawn_state, tmp_path):
        result = spawn(fleet['primary'], 'alpha', '--brief', str(brief_at(tmp_path / 'b.md')))
        alpha = fleet['roots'] / 'primary' / 'alpha'

        assert result.returncode == 0, plain(result.stderr)
        assert git(alpha, 'rev-parse', '--abbrev-ref', 'HEAD') == 'alpha'
        assert (spawn_state / 'cwd').read_text().strip() == str(alpha)

    def test_no_slug_stands_the_session_in_the_checkout_and_cuts_nothing(self, fleet, spawn, spawn_state, tmp_path):
        result = spawn(fleet['primary'], '--brief', str(brief_at(tmp_path / 'b.md')))

        assert result.returncode == 0, plain(result.stderr)
        assert (spawn_state / 'cwd').read_text().strip() == str(fleet['primary'])
        assert not (fleet['roots'] / 'primary').exists(), 'no slug means no branch, so there is nothing to isolate'

    def test_an_existing_worktree_is_attached_to_rather_than_refused(self, fleet, run, spawn, spawn_state, tmp_path):
        """Respawning an agent into work already in progress is the ordinary case."""
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        commit_in(alpha, 'work.txt')

        result = spawn(fleet['primary'], 'alpha', '--brief', str(brief_at(tmp_path / 'b.md')))

        assert result.returncode == 0, plain(result.stderr)
        assert (alpha / 'work.txt').exists(), 'the branch it attached to still carries its commits'
        assert (spawn_state / 'cwd').read_text().strip() == str(alpha)

    def test_the_branch_is_read_from_git_rather_than_assumed_to_be_the_slug(self, fleet, run, spawn, tmp_path):
        """A session standing in a worktree may have moved it, and the report has to be true."""
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        git(alpha, 'checkout', '-q', '-b', 'renamed')

        result = spawn(fleet['primary'], 'alpha', '--brief', str(brief_at(tmp_path / 'b.md')), '--json')

        assert json.loads(result.stdout)['branch'] == 'renamed'


@pytest.mark.interpreter('tmux')
class TestSpawnBrief:
    """The brief is copied, and the copy is what the session is pointed at.

    A caller writing one into its own scratch directory has no way to know when the
    session has read it, so a brief that stayed where the caller put it would be a race
    between cleanup and startup. The copy also outlives the spawn, which is what lets a
    later reader tell a wrong agent from a wrong brief.
    """

    def test_the_session_is_pointed_at_the_copy_and_not_at_the_caller_s_file(self, fleet, spawn, spawn_state, tmp_path):
        source = brief_at(tmp_path / 'mine.md')

        spawn(fleet['primary'], 'alpha', '--brief', str(source))
        prompt = (spawn_state / 'prompt').read_text()

        kept = briefs_in(tmp_path)
        assert len(kept) == 1
        assert prompt == f'Read {kept[0]} and carry out the work it describes. It names the session to report to.'
        assert str(source) not in prompt

    def test_the_copy_survives_the_caller_deleting_its_own(self, fleet, spawn, tmp_path):
        source = brief_at(tmp_path / 'mine.md', 'the whole brief\n')

        spawn(fleet['primary'], 'alpha', '--brief', str(source))
        source.unlink()

        assert briefs_in(tmp_path)[0].read_text() == 'the whole brief\n'

    def test_the_copy_lands_under_the_state_directory(self, fleet, spawn, tmp_path):
        """standards/data.md § "Every path a tool writes is an XDG base directory"."""
        spawn(fleet['primary'], 'alpha', '--brief', str(brief_at(tmp_path / 'b.md')))

        kept = briefs_in(tmp_path)
        assert kept[0].parent == tmp_path / '.local' / 'state' / 'worktree' / 'briefs'
        assert kept[0].name.startswith('primary-alpha-')

    def test_two_spawns_in_the_same_second_get_their_own_brief(self, fleet, spawn, tmp_path):
        """Both calls have to reach `keep_brief` through a spawn that happens, or the
        second brief lands only because the copy runs ahead of a refusal.

        Different slugs, because a second spawn into one worktree is refused — and with no
        slug at all the two would be indistinguishable, which is the collision itself.
        """
        first = spawn(fleet['primary'], 'alpha', '--brief', str(brief_at(tmp_path / 'one.md', 'first\n')))
        second = spawn(fleet['primary'], 'beta', '--brief', str(brief_at(tmp_path / 'two.md', 'second\n')))

        assert (first.returncode, second.returncode) == (0, 0), plain(first.stderr + second.stderr)
        assert sorted(path.read_text() for path in briefs_in(tmp_path)) == ['first\n', 'second\n']

    def test_a_brief_is_not_overwritten_by_one_minted_in_the_same_second(self, worktree_app, tmp_path, monkeypatch):
        """A timestamp at second resolution is not a distinguishing part. Two no-slug
        spawns into one repo have nothing else left, and that is the reviewer form — the
        one a coordinator dispatches several of at once."""
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'state'))
        one = brief_at(tmp_path / 'one.md', 'review PR 33\n')
        two = brief_at(tmp_path / 'two.md', 'review PR 41\n')

        first = worktree_app.keep_brief(one, 'dotfiles', None)
        second = worktree_app.keep_brief(two, 'dotfiles', None)

        assert first != second
        assert first.read_text() == 'review PR 33\n'
        assert second.read_text() == 'review PR 41\n'

    def test_a_missing_brief_refuses_before_anything_is_created(self, fleet, spawn, rig, tmp_path):
        result = spawn(fleet['primary'], 'alpha', '--brief', str(tmp_path / 'absent.md'))

        assert result.returncode == 1
        assert not (fleet['roots'] / 'primary').exists()
        assert rig.panes() == [rig.caller]

    def test_a_refused_split_takes_back_the_worktree_it_had_just_cut(self, fleet, spawn, bin_dir, rig, tmp_path):
        """tmux runs out of room in a full window, which is the everyday case for a
        coordinator dispatching a fourth agent. What a refusal must not leave is a branch
        and a provisioned checkout — `sweep` will not collect one, because nothing was
        ever pushed and it is held as UNPUBLISHED.
        """
        write_stub(
            bin_dir,
            'tmux',
            f'[ "$1" = split-window ] && {{ echo "no space for a new pane" >&2; exit 1; }}\nexec {TMUX} -S {rig.socket} "$@"',
        )

        result = spawn(fleet['primary'], 'alpha', '--brief', str(brief_at(tmp_path / 'b.md')))

        assert result.returncode == 1
        assert not (fleet['roots'] / 'primary' / 'alpha').exists(), 'the worktree outlived the refusal'
        assert 'alpha' not in git(fleet['primary'], 'branch', '--list', 'alpha')

    def test_a_worktree_it_only_attached_to_survives_a_refused_split(self, fleet, run, spawn, bin_dir, rig, tmp_path):
        """The other half of the same rule: work somebody else started is not this run's
        to take away, however badly this run went."""
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        commit_in(alpha, 'theirs.txt')
        write_stub(
            bin_dir,
            'tmux',
            f'[ "$1" = split-window ] && {{ echo "no space for a new pane" >&2; exit 1; }}\nexec {TMUX} -S {rig.socket} "$@"',
        )

        result = spawn(fleet['primary'], 'alpha', '--brief', str(brief_at(tmp_path / 'b.md')))

        assert result.returncode == 1
        assert (alpha / 'theirs.txt').exists()

    def test_an_empty_brief_refuses(self, fleet, spawn, rig, tmp_path):
        result = spawn(fleet['primary'], 'alpha', '--brief', str(brief_at(tmp_path / 'b.md', '   \n')))

        assert result.returncode == 1
        assert rig.panes() == [rig.caller]


@pytest.mark.interpreter('tmux')
class TestSpawnCollision:
    """A worktree holds one session; a checkout does not, and the two are treated apart.

    Refusing an occupied checkout would make a review impossible whenever anyone happens
    to be working in the repo, which is most of the time. What makes sharing one tolerable
    is that the no-slug form gets no branch, so it has nothing of its own to commit.
    """

    def test_an_occupied_worktree_refuses_and_opens_no_pane(self, fleet, run, spawn, spawn_state, rig, tmp_path):
        run(fleet['primary'], 'new', 'alpha')
        alpha = fleet['roots'] / 'primary' / 'alpha'
        preset_session(spawn_state, 'already-here', alpha, '%77')

        result = spawn(fleet['primary'], 'alpha', '--brief', str(brief_at(tmp_path / 'b.md')))

        assert result.returncode == 1
        assert rig.panes() == [rig.caller]

    def test_an_unreadable_registry_refuses_rather_than_reading_as_empty(self, fleet, run, spawn, bin_dir, rig, tmp_path):
        """The same split `held_by` makes: nobody is here and nobody could be asked are one
        empty list, and reading the second as the first is what authorises the collision."""
        run(fleet['primary'], 'new', 'alpha')
        write_stub(bin_dir, 'claude-sessions', 'exit 1')

        result = spawn(fleet['primary'], 'alpha', '--brief', str(brief_at(tmp_path / 'b.md')))

        assert result.returncode == 1
        assert rig.panes() == [rig.caller]

    def test_an_occupied_checkout_warns_and_still_spawns(self, fleet, spawn, spawn_state, tmp_path):
        preset_session(spawn_state, 'someone-else', fleet['primary'], '%77')

        result = spawn(fleet['primary'], '--brief', str(brief_at(tmp_path / 'b.md')))

        assert result.returncode == 0, plain(result.stderr)
        assert 'already holds someone-else' in plain(result.stderr)
        assert (spawn_state / 'cwd').read_text().strip() == str(fleet['primary'])


@pytest.mark.interpreter('tmux')
class TestSpawnRegistration:
    """The session's name is the product, so a spawn without one is not a success.

    A caller's next move is a message addressed to that name. A run reporting success with
    nothing to address is the failure that reads as working, which is why it exits non-zero.
    """

    def test_the_name_is_what_stdout_carries(self, fleet, spawn, tmp_path):
        result = spawn(fleet['primary'], 'alpha', '--brief', str(brief_at(tmp_path / 'b.md')))

        assert result.stdout.strip() == 'spawned'

    def test_json_carries_everything_needed_to_reach_it(self, fleet, spawn, rig, tmp_path):
        result = spawn(fleet['primary'], 'alpha', '--brief', str(brief_at(tmp_path / 'b.md')), '--json')
        reported = json.loads(result.stdout)

        assert reported['session'] == 'spawned'
        assert reported['registration'] == 'registered'
        assert reported['repo'] == 'primary'
        assert reported['branch'] == 'alpha'
        assert reported['worktree'] is True
        assert reported['path'] == str(fleet['roots'] / 'primary' / 'alpha')
        assert reported['pane'] == rig.spawned()
        assert Path(reported['brief']).read_text() == 'Do the thing. Report to claude-73.\n'

    def test_a_reviewer_reports_no_branch_and_no_worktree(self, fleet, spawn, tmp_path):
        result = spawn(fleet['primary'], '--brief', str(brief_at(tmp_path / 'b.md')), '--json')
        reported = json.loads(result.stdout)

        assert reported['branch'] is None
        assert reported['worktree'] is False
        assert reported['path'] == str(fleet['primary'])

    def test_a_session_already_in_the_checkout_is_not_mistaken_for_the_new_one(self, fleet, spawn, spawn_state, tmp_path):
        """The reason the match is on the pane rather than on the directory.

        A no-slug spawn stands in the primary checkout on purpose, and that is the one
        directory several sessions share by design — so a directory match returns whichever
        the registry lists first, and the caller messages an agent that never asked for it.
        """
        preset_session(spawn_state, 'someone-else', fleet['primary'], '%77')

        result = spawn(fleet['primary'], '--brief', str(brief_at(tmp_path / 'b.md')), '--json')

        assert json.loads(result.stdout)['session'] == 'spawned'

    def test_a_second_row_claiming_the_new_pane_is_not_answered_with(self, fleet, spawn, spawn_state, tmp_path):
        """The registry keys a session on its pane, and a `claude` started from inside one
        inherits that pane and registers against it — so the new pane can carry two rows
        before the real session is the only one left. The pane's own process is what tells
        them apart, and it is the process this command started."""
        claim_the_pane(spawn_state)

        result = spawn(fleet['primary'], 'alpha', '--brief', str(brief_at(tmp_path / 'b.md')), '--json')

        assert json.loads(result.stdout)['session'] == 'spawned'

    def test_a_pane_moved_to_another_window_before_it_registers_is_still_found(self, fleet, spawn, bin_dir, spawn_state, rig, tmp_path):
        """A pane can be anywhere by the time its session appears in the registry.

        `tmux break-pane` gives it a new window, and moving it between tmux sessions gives
        it a new session name, so two of the address's three parts are gone. The pane id
        and the pane's process are what survive, and they are the two this matches on.
        """
        # -s is the pane being moved; break-pane's -t is the window it lands in.
        stub_claude(bin_dir, spawn_state, preamble='tmux break-pane -d -s "$TMUX_PANE" || exit 9')

        result = spawn(fleet['primary'], 'alpha', '--brief', str(brief_at(tmp_path / 'b.md')), '--json')
        reported = json.loads(result.stdout)

        assert result.returncode == 0, plain(result.stderr)
        assert reported['session'] == 'spawned'
        assert rig.window_of(reported['pane']) != rig.window_of(rig.caller), 'the pane really did move'

    def test_a_pane_that_died_reports_its_exit_status_rather_than_timing_out(self, fleet, spawn, bin_dir, tmp_path):
        stub_failing_claude(bin_dir, 17, 'could not start')

        result = spawn(fleet['primary'], 'alpha', '--brief', str(brief_at(tmp_path / 'b.md')), '--timeout', '20', '--json')
        reported = json.loads(result.stdout)

        assert result.returncode == 1
        assert reported['session'] is None
        assert reported['registration'] == 'pane_died'
        assert reported['exit_status'] == 17
        assert 'could not start' in plain(result.stderr)

    def test_a_dead_pane_is_not_left_standing_in_the_window(self, fleet, spawn, bin_dir, rig, tmp_path):
        """`remain-on-exit` keeps the corpse so its status can be read; nothing else would
        remove it afterwards, and a window collecting dead panes is worse than a timeout."""
        stub_failing_claude(bin_dir, 17, 'could not start')

        spawn(fleet['primary'], 'alpha', '--brief', str(brief_at(tmp_path / 'b.md')), '--timeout', '20')

        assert rig.panes() == [rig.caller]

    def test_a_registry_row_with_no_pid_is_reported_as_that_rather_than_as_a_timeout(self, fleet, spawn, spawn_state, bin_dir, tmp_path):
        """`pid` is an undeclared field of a sibling app's JSON, and its disappearance
        would otherwise present as sixty seconds of waiting that blames `claude` for a
        pane which is perfectly healthy. Nothing in the report would point at the registry.
        """
        (spawn_state / 'drop-pid').touch()

        result = spawn(fleet['primary'], 'alpha', '--brief', str(brief_at(tmp_path / 'b.md')), '--timeout', '20', '--json')
        reported = json.loads(result.stdout)

        assert result.returncode == 1
        assert reported['registration'] == 'no_pid_in_registry'
        assert 'claude-sessions' in plain(result.stderr)

    def test_a_session_that_never_registers_exits_non_zero(self, fleet, spawn, bin_dir, tmp_path):
        stub_silent_claude(bin_dir)

        result = spawn(fleet['primary'], 'alpha', '--brief', str(brief_at(tmp_path / 'b.md')), '--timeout', '2', '--json')
        reported = json.loads(result.stdout)

        assert result.returncode == 1
        assert reported['session'] is None
        assert reported['registration'] == 'timed_out'

    def test_the_worktree_and_the_pane_survive_a_timeout(self, fleet, spawn, bin_dir, rig, tmp_path):
        """A session that has not registered yet may still be starting, and the work it was
        given is already in the tree. Neither is thrown away over a wait that ran out."""
        stub_silent_claude(bin_dir)

        spawn(fleet['primary'], 'alpha', '--brief', str(brief_at(tmp_path / 'b.md')), '--timeout', '2')

        assert (fleet['roots'] / 'primary' / 'alpha').is_dir()
        assert len(rig.panes()) == 2


@pytest.mark.interpreter('tmux')
class TestSpawnLayout:
    """The caller keeps the wide pane, because the caller is the one being read.

    tmux halves the pane it splits, and `main-vertical` on its own falls back to a
    `main-pane-width` of 80 columns — so without the sizing the pane carrying prose is the
    narrow one, which is the failure the width exists to stop.
    """

    def test_a_beside_split_gives_the_caller_the_share_it_asked_for(self, fleet, spawn, rig, tmp_path):
        """Asserted against the requested share of the window, not merely against the pane
        beside it. `split-window -h` halves a pane by itself, so `caller > spawned` holds
        with the sizing deleted and the check could never fail."""
        spawn(fleet['primary'], 'alpha', '--brief', str(brief_at(tmp_path / 'b.md')))
        geometry = rig.geometry()
        caller_left, _, caller_width = geometry[rig.caller]
        spawned_left, _, _ = geometry[rig.spawned()]

        assert spawned_left > caller_left, 'beside means to the right of it'
        assert abs(caller_width - RIG_COLUMNS * 66 // 100) <= 2, f'{caller_width} of {RIG_COLUMNS} is not the 66% default'

    def test_the_caller_takes_the_main_pane_even_when_it_does_not_lead_the_window(self, fleet, spawn, rig, tmp_path):
        """`main-vertical` assigns the main pane by index, so a caller that is not the
        window's first pane hands the wide pane to whichever one is. A session is rarely
        the first pane of its window, so this is the ordinary case rather than the edge."""
        rig.add_pane_before_the_caller()

        spawn(fleet['primary'], 'alpha', '--brief', str(brief_at(tmp_path / 'b.md')))
        caller_width = rig.geometry()[rig.caller][2]

        assert abs(caller_width - RIG_COLUMNS * 66 // 100) <= 2, f'the caller got {caller_width} of {RIG_COLUMNS}'

    def test_the_width_flag_reaches_tmux(self, fleet, spawn, rig, tmp_path):
        spawn(fleet['primary'], 'alpha', '--brief', str(brief_at(tmp_path / 'b.md')), '--width', '25%')
        caller_width = rig.geometry()[rig.caller][2]

        assert abs(caller_width - RIG_COLUMNS * 25 // 100) <= 2, f'the caller got {caller_width} of {RIG_COLUMNS}'

    def test_a_width_tmux_would_silently_ignore_is_a_usage_error(self, fleet, run, rig, tmp_path):
        """tmux answers `abc`, `-5`, `0` and `999%` with exit 0 and then falls back to 80
        columns — the value `--width` exists to replace. Nothing downstream can catch it,
        because no return code in the sequence carries the failure."""
        for bogus in ('abc', '-5', '0', '0%', '999%', '66%%', ''):
            result = run(fleet['primary'], 'spawn', 'alpha', '--brief', str(brief_at(tmp_path / 'b.md')), '--width', bogus)

            assert result.returncode == 2, f'--width {bogus!r} was accepted'
            assert '--width takes columns or a percentage' in plain(result.stderr)

    def test_a_below_split_is_under_the_caller_and_the_same_width(self, fleet, spawn, rig, tmp_path):
        """A reviewer is put under its author on purpose, and `main-vertical` would lift it
        into the right-hand stack."""
        spawn(fleet['primary'], 'alpha', '--brief', str(brief_at(tmp_path / 'b.md')), '--below')
        geometry = rig.geometry()
        caller_left, caller_top, caller_width = geometry[rig.caller]
        spawned_left, spawned_top, spawned_width = geometry[rig.spawned()]

        assert spawned_top > caller_top
        assert spawned_left == caller_left
        assert spawned_width == caller_width


class TestHelp:
    """Every subcommand renders its own help.

    argparse runs a help string through %-formatting, so a percent sign in a default
    raises instead of printing — and it breaks only the leaf carrying it. The root help
    still renders, so nothing about the failure is visible until someone asks that one
    command for help.

    The commands are read off the parser rather than listed here, so one added later is
    covered on the day it arrives rather than on the day someone remembers this file.
    """

    def commands(self, app) -> list[str]:
        # argparse exposes its subcommands only through the action holding them, and the
        # action list is private. A hand-written list is the alternative, and that is the
        # thing this test exists to not depend on.
        holders = [action for action in app.build_parser()._actions if isinstance(getattr(action, 'choices', None), dict)]
        assert len(holders) == 1, 'expected one subcommand group'
        return sorted(holders[0].choices)

    def test_every_subcommand_renders_its_help(self, worktree_app, fleet, run):
        for command in self.commands(worktree_app):
            result = run(fleet['primary'], command, '--help')

            assert result.returncode == 0, f'{command} --help exited {result.returncode}: {plain(result.stderr)}'
            assert result.stdout.startswith('usage:'), f'{command} --help printed no usage'


@pytest.mark.interpreter('tmux')
class TestSpawnRefusals:
    """What it will not do. None of it needs a tmux *server*, and all of it needs the
    binary: `require_caller_pane` checks tmux is installed before it looks at $TMUX, so
    without the mark these fail on a machine that has no tmux instead of skipping."""

    def test_it_refuses_outside_tmux_rather_than_starting_something_invisible(self, fleet, run, tmp_path):
        result = run(fleet['primary'], 'spawn', 'alpha', '--brief', str(brief_at(tmp_path / 'b.md')))

        assert result.returncode == 1

    def test_width_with_below_is_a_usage_error(self, fleet, run, tmp_path):
        """`cli-design.md` § "A flag the run cannot honour says so; it never parses into
        silence" — a below split leaves the layout alone, so there is no main pane to size."""
        result = run(fleet['primary'], 'spawn', 'alpha', '--brief', str(brief_at(tmp_path / 'b.md')), '--below', '--width', '50')

        assert result.returncode == 2
        assert 'no --width with --below' in plain(result.stderr)

    def test_a_brief_is_required(self, fleet, run):
        result = run(fleet['primary'], 'spawn', 'alpha')

        assert result.returncode == 2
        assert '--brief' in plain(result.stderr)


class TestSessionMatching:
    """Which registered session is the one that was just started.

    Pure, and separate from the rig, because the registry field these read is unreliable in
    ways a live tmux server cannot be made to reproduce on demand.
    """

    def registered(self, app, name: str, tmux: str | None, pid: int = 100):
        return app.Session(name=name, status='idle', waiting=None, cwd=Path('/anywhere'), tmux=tmux, pid=pid)

    def test_a_stale_window_does_not_prevent_the_match(self, worktree_app):
        """`tmux join-pane` moves a pane between windows and the registry keeps the window it
        was recorded in. The pane id survives the move, so only the pane id is compared."""
        moved = self.registered(worktree_app, 'moved', 'system:@13.%24')

        assert worktree_app.session_in_pane([moved], '%24', 100) == 'moved'

    def test_a_pane_moved_to_another_tmux_session_still_matches(self, worktree_app):
        """The same move between tmux sessions rather than between windows, which rots the
        first field as well. Two of the address's three parts go stale and the pane id does
        not, so it is the only part worth comparing."""
        relocated = self.registered(worktree_app, 'relocated', 'the-old-one:@13.%24')

        assert worktree_app.session_in_pane([relocated], '%24', 100) == 'relocated'

    def test_a_tmux_session_name_containing_a_dot_still_resolves(self, worktree_app):
        awkward = self.registered(worktree_app, 'awkward', 'de.initiative:@0.%7')

        assert worktree_app.session_in_pane([awkward], '%7', 100) == 'awkward'

    def test_a_session_outside_tmux_is_never_matched(self, worktree_app):
        headless = self.registered(worktree_app, 'headless', None)

        assert worktree_app.session_in_pane([headless], '%7', 100) is None

    def test_a_different_pane_is_not_a_match(self, worktree_app):
        elsewhere = self.registered(worktree_app, 'elsewhere', 'rig:@0.%7')

        assert worktree_app.session_in_pane([elsewhere], '%77', 100) is None

    def test_a_pane_id_that_is_a_prefix_of_another_is_not_a_match(self, worktree_app):
        """%7 and %77 are different panes, and a startswith would join them."""
        seven = self.registered(worktree_app, 'seven', 'rig:@0.%7')

        assert worktree_app.session_in_pane([seven], '%77', 100) is None
        assert worktree_app.session_in_pane([seven], '%7', 100) == 'seven'

    def test_a_second_row_on_the_same_pane_is_told_apart_by_its_process(self, worktree_app):
        """A `claude` started from inside a session's pane inherits that pane's $TMUX_PANE
        and registers against it, so one pane id can carry two rows."""
        child = self.registered(worktree_app, 'child', 'rig:@0.%7', pid=999)
        real = self.registered(worktree_app, 'real', 'rig:@0.%7', pid=100)

        assert worktree_app.session_in_pane([child, real], '%7', 100) == 'real'

    def test_nothing_is_answered_with_when_no_claimant_owns_the_process(self, worktree_app):
        """Waiting is the right answer, because the caller's next act is to send this name
        an instruction. A wrong name is worse than a second of delay."""
        child = self.registered(worktree_app, 'child', 'rig:@0.%7', pid=999)

        assert worktree_app.session_in_pane([child], '%7', 100) is None

    def test_the_pane_alone_decides_when_the_process_cannot_be_read(self, worktree_app):
        """A pane tmux will not report a pid for is almost certainly already dead, and the
        wait has a pane check of its own for that."""
        only = self.registered(worktree_app, 'only', 'rig:@0.%7', pid=999)

        assert worktree_app.session_in_pane([only], '%7', None) == 'only'


class TestPaneState:
    """`list-panes` answers for a whole window, so the row has to be found by id.

    A caller's own healthy pane sits in the same answer as the dead one being asked about,
    and reading the first row would report whichever tmux happened to list first.
    """

    def listing(self, monkeypatch, worktree_app, stdout: str, returncode: int = 0):
        def fake(argv, **kwargs):
            return subprocess.CompletedProcess(argv, returncode, stdout, '')

        monkeypatch.setattr(worktree_app, 'run', fake)

    def test_a_pane_still_running_is_running(self, worktree_app, monkeypatch):
        self.listing(monkeypatch, worktree_app, '%0 0 \n%1 0 \n')

        assert worktree_app.pane_state('%1') == (worktree_app.Pane.RUNNING, None)

    def test_a_dead_pane_carries_the_status_its_command_exited_with(self, worktree_app, monkeypatch):
        self.listing(monkeypatch, worktree_app, '%0 0 \n%1 1 127\n')

        assert worktree_app.pane_state('%1') == (worktree_app.Pane.DEAD, 127)

    def test_a_live_sibling_is_not_read_in_place_of_the_pane_asked_about(self, worktree_app, monkeypatch):
        self.listing(monkeypatch, worktree_app, '%0 0 \n%1 1 127\n')

        assert worktree_app.pane_state('%0') == (worktree_app.Pane.RUNNING, None)

    def test_a_pane_tmux_refuses_to_list_is_gone(self, worktree_app, monkeypatch):
        self.listing(monkeypatch, worktree_app, '', returncode=1)

        assert worktree_app.pane_state('%1') == (worktree_app.Pane.GONE, None)

    def test_an_unreadable_status_is_reported_as_dead_without_one(self, worktree_app, monkeypatch):
        """A dead pane whose status tmux will not give up is still a launch that failed."""
        self.listing(monkeypatch, worktree_app, '%1 1 \n')

        assert worktree_app.pane_state('%1') == (worktree_app.Pane.DEAD, None)


class TestRefusalFaults:
    """A refusal is asserted by what it is, never by the sentence it prints.

    `testing.md` § "Never assert on rendered output — assert the value it was built from".
    Matching the prose means rewording an error breaks the suite, and it means the suite
    passes when the right sentence is raised for the wrong reason. These call the refusing
    functions directly, which is the only way the member is reachable at all.
    """

    def refusal(self, app, call) -> Any:
        with pytest.raises(app.Refused) as raised:
            call()
        return raised.value.fault

    def test_a_missing_binary_is_a_tool_fault(self, worktree_app, monkeypatch):
        monkeypatch.setattr(worktree_app.shutil, 'which', lambda _name: None)

        assert self.refusal(worktree_app, lambda: worktree_app.require_tool('tmux', 'why')) is worktree_app.Fault.TOOL_MISSING

    def test_being_outside_tmux_is_its_own_fault(self, worktree_app, monkeypatch):
        monkeypatch.setattr(worktree_app.shutil, 'which', lambda name: f'/usr/bin/{name}')
        monkeypatch.delenv('TMUX', raising=False)
        monkeypatch.delenv('TMUX_PANE', raising=False)

        assert self.refusal(worktree_app, worktree_app.require_caller_pane) is worktree_app.Fault.NO_TMUX

    def test_an_occupied_worktree_and_an_unreadable_registry_are_different_faults(self, worktree_app, monkeypatch, tmp_path):
        occupant = worktree_app.Session(name='someone', status='idle', waiting=None, cwd=tmp_path, tmux=None, pid=1)

        monkeypatch.setattr(worktree_app, 'live_sessions', lambda: (occupant,))
        occupied = self.refusal(worktree_app, lambda: worktree_app.require_unoccupied(tmp_path))

        monkeypatch.setattr(worktree_app, 'live_sessions', lambda: None)
        unreadable = self.refusal(worktree_app, lambda: worktree_app.require_unoccupied(tmp_path))

        assert occupied is worktree_app.Fault.WORKTREE_OCCUPIED
        assert unreadable is worktree_app.Fault.SESSIONS_UNREADABLE
        assert occupied is not unreadable, 'nobody is here and nobody could be asked are the same empty list'


class TestUsableWidth:
    """What tmux honours, which is a smaller set than what it parses.

    Every rejected value here was measured against real tmux answering exit 0 and then
    falling back to 80 columns — so `0` and `999%` are as unusable as `abc`, and only the
    first of those three looks wrong.
    """

    def test_columns_and_percentages_are_taken(self, worktree_app):
        assert all(worktree_app.usable_width(value) for value in ('1', '80', '120', '1%', '66%', '100%'))

    def test_a_value_tmux_would_ignore_is_refused(self, worktree_app):
        for value in ('abc', '-5', '0', '0%', '101%', '999%', '66%%', '', '12.5', '80 '):
            assert not worktree_app.usable_width(value), value


class TestBriefsDirectory:
    def test_it_follows_xdg_state_home(self, worktree_app, monkeypatch, tmp_path):
        monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'state'))

        assert worktree_app.briefs_dir() == tmp_path / 'state' / 'worktree' / 'briefs'

    def test_it_falls_back_under_home_when_the_variable_is_unset(self, worktree_app, monkeypatch, tmp_path):
        monkeypatch.delenv('XDG_STATE_HOME', raising=False)
        monkeypatch.setenv('HOME', str(tmp_path))

        assert worktree_app.briefs_dir() == tmp_path / '.local' / 'state' / 'worktree' / 'briefs'
