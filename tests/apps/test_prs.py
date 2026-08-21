"""`prs list` is the human rendering of `pull-requests`, and the picker is the other.

Both were reported as reading worse than `gh pr list` for two reasons: no column
labels, and no branch anywhere — so a row named a PR by a number that collides
across the registry and a title that is the first thing to get truncated.

The seam is `pull-requests` itself, shadowed on PATH. That is the whole point of the
split: the query lives in one place and this file only decides how a row reads,
so a rendering test has no business reaching a forge.

Assertions read the text of a rendered line, never a column position. The layout
has been rebuilt several times — one line per PR, then two, fields left then
spread — and each rebuild renumbered every positional assertion whether or not
the thing it checked had moved. What a row *says* has been stable throughout.

Run with: pytest tests/apps/test_prs.py
"""

from __future__ import annotations

import json
import os
import pty
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
PRS = REPO / 'apps' / 'common' / 'prs'

# `prs` runs under `uv run --script`, and the fixtures below give it a throwaway
# HOME so nothing reads real config. uv's cache hangs off HOME, so without this
# every test resolves and downloads its dependencies again — and on a machine
# with no network, fails. Read at import, while HOME is still the real one.
UV_CACHE = os.environ.get('UV_CACHE_DIR') or str(Path.home() / '.cache' / 'uv')

# The stack marker's arrow and the em dash are non-ASCII, so an env without a
# UTF-8 locale measures escaping rather than the row. Named per platform because
# there is no portable spelling: glibc has C.UTF-8 built in and macOS does not.
UTF8_LOCALE = 'en_US.UTF-8' if sys.platform == 'darwin' else 'C.UTF-8'

ANSI = re.compile(r'\x1b\[[0-9;]*m')


def pr(repo: str, number: int, branch: str, **overrides: Any) -> dict[str, Any]:
    row = {
        'repo': repo,
        'slug': f'datapointchris/{repo}',
        'number': number,
        'title': f'a change in {repo}',
        'url': f'https://github.com/datapointchris/{repo}/pull/{number}',
        'branch': branch,
        'base': 'main',
        'draft': False,
        'created_at': '2026-08-01T10:00:00Z',
        'age_days': 3,
        'path': f'/home/chris/{repo}',
        'additions': 12,
        'deletions': 4,
        'changed_files': 2,
        'review': '',
        'reviews': 0,
        'checks': '',
        'provider': 'github',
        'body': f'what {repo} #{number} changes',
    }
    return row | overrides


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


def stub_pr_list(bin_dir: Path, rows: tuple[dict[str, Any], ...]) -> None:
    write_stub(bin_dir, 'pull-requests', f"cat <<'JSON'\n{json.dumps(list(rows))}\nJSON")


def script_env(tmp_path: Path, bin_dir: Path, **extra: str) -> dict[str, str]:
    return {
        'HOME': str(tmp_path),
        'PATH': f'{bin_dir}:{os.environ["PATH"]}',
        'LC_ALL': UTF8_LOCALE,
        'UV_CACHE_DIR': UV_CACHE,
        **extra,
    }


@pytest.fixture
def listing(tmp_path: Path, bin_dir: Path):
    """Run `prs list` over a fixed set of rows, returning its stdout lines."""

    def _listing(*rows: dict[str, Any]) -> list[str]:
        stub_pr_list(bin_dir, rows)
        result = subprocess.run(
            [str(PRS), 'list'],
            capture_output=True,
            text=True,
            env=script_env(tmp_path, bin_dir),
        )
        assert result.returncode == 0, result.stderr
        return result.stdout.splitlines()

    return _listing


@pytest.fixture
def picker(tmp_path: Path, bin_dir: Path):
    """Run bare `prs` over a fixed set of rows, returning what it feeds fzf.

    fzf is the only place a displayed row can be read: everything past it fetches
    a ref and opens a tmux window. The stub records its stdin and exits 130, the
    code for a dismissed picker, which `prs` turns into a clean exit. nvim and
    tmux are stubbed only to satisfy the tool check on a machine without them,
    and TMUX is set because this refuses to run outside a session.
    """
    fed = tmp_path / 'fed-to-fzf'

    def _picker(*rows: dict[str, Any]) -> str:
        stub_pr_list(bin_dir, rows)
        write_stub(bin_dir, 'fzf', f"cat >'{fed}'\nexit 130")
        write_stub(bin_dir, 'nvim', 'exit 0')
        write_stub(bin_dir, 'tmux', 'exit 0')
        result = subprocess.run(
            [str(PRS)],
            capture_output=True,
            text=True,
            env=script_env(tmp_path, bin_dir, TMUX='/tmp/tmux-fixture,1,0'),
        )
        assert result.returncode == 0, result.stderr
        # Raw, not split on newlines: records are NUL-separated and each is two
        # lines, so splitlines would cut every PR in half.
        return fed.read_text(encoding='utf-8')

    return _picker


# An fzf that answers a scripted reply per call, and records what each call was
# given. Two calls happen when a PR is chosen with enter — the list, then the
# action menu — and they need different answers, so a stub that replies the same
# thing every time cannot tell the two paths apart.
#
# A call with no reply file exits 130, the code for a dismissed picker, which is
# how a scripted session stops without the caller having to script an ending.
FZF_STUB = """\
room={room}
call=$(cat "$room/count" 2>/dev/null || echo 0)
call=$((call + 1))
printf '%s' "$call" >"$room/count"
printf '%s\\n' "$@" >"$room/argv.$call"
cat >"$room/fed.$call"
if [ -s "$room/reply.$call" ]; then
  cat "$room/reply.$call"
  exit 0
fi
exit 130
"""


class Session:
    """One run of the picker, and everything the stubs recorded during it."""

    def __init__(self, stdout: str, stderr: str, room: Path) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.room = room

    @property
    def calls(self) -> int:
        """How many times fzf ran. One means the action menu never opened."""
        counted = self.room / 'count'
        return int(counted.read_text()) if counted.exists() else 0

    def fed(self, call: int) -> str:
        return (self.room / f'fed.{call}').read_text(encoding='utf-8')

    def argv(self, call: int) -> list[str]:
        return (self.room / f'argv.{call}').read_text(encoding='utf-8').splitlines()


@pytest.fixture
def session(tmp_path: Path, bin_dir: Path):
    """Run the picker with scripted fzf replies and a terminal for a stdin.

    stdin is a pty rather than a pipe because the merge confirm is only printed
    when `prs` believes a person is there, and `isatty` on a pipe says nobody is.
    The answer is written before the run, which a pty buffers until it is read.

    `gh` echoes its own arguments to stdout, which is where a merge is observed:
    everything past `run` hands the terminal to another tool, so what it was
    asked for is the only thing left to assert on.
    """
    room = tmp_path / 'fzf'
    room.mkdir()

    def _session(*rows: dict[str, Any], replies: tuple[str, ...] = (), answer: str = '\n') -> Session:
        stub_pr_list(bin_dir, rows)
        write_stub(bin_dir, 'fzf', FZF_STUB.format(room=room))
        write_stub(bin_dir, 'nvim', 'exit 0')
        write_stub(bin_dir, 'tmux', 'exit 0')
        write_stub(bin_dir, 'gh', 'printf \'gh %s\\n\' "$*"')
        for index, reply in enumerate(replies, start=1):
            (room / f'reply.{index}').write_text(reply)

        controller, terminal = pty.openpty()
        try:
            os.write(controller, answer.encode())
            result = subprocess.run(
                [str(PRS)],
                stdin=terminal,
                capture_output=True,
                text=True,
                timeout=60,
                env=script_env(tmp_path, bin_dir, TMUX='/tmp/tmux-fixture,1,0'),
            )
        finally:
            os.close(terminal)
            os.close(controller)
        assert result.returncode == 0, result.stderr
        return Session(result.stdout, result.stderr, room)

    return _session


def chose(index: int, key: str = '') -> str:
    """An fzf reply: the key pressed on its own line, then the row it was on."""
    return f'{key}\n{index}\tthe rendered row\n'


def plain(line: str) -> str:
    """The line with its colour stripped, which is what an assertion reads."""
    return ANSI.sub('', line)


def item(lines: list[str]) -> str:
    """A PR's two lines as one plain string, which is what an assertion reads."""
    return plain(' '.join(lines))


def items(rendered: list[str]) -> list[str]:
    """The picker's records, each flattened to one plain string."""
    return [item(record.split('\t', 1)[1].splitlines()) for record in rendered]


def listed(lines: list[str]) -> list[str]:
    """`prs list` output as one string per PR.

    The header is the first non-blank line and every PR is the two after it, so
    the blanks are the record separator rather than something to index around.
    """
    blocks, current = [], []
    for line in lines[2:]:
        if plain(line).strip():
            current.append(line)
        elif current:
            blocks.append(item(current))
            current = []
    if current:
        blocks.append(item(current))
    return blocks


def test_the_columns_are_labelled(listing) -> None:
    """Unlabelled columns read as a log line. `gh pr list` and `bbkt pr list`
    both label theirs, and the comparison against gh is the reported complaint."""
    header = plain(next(line for line in listing(pr('dotfiles', 1, 'a-branch')) if line.strip()))

    assert [word for word in header.split() if word.isupper()] == ['STATUS', 'TITLE', 'DIFF', 'AGE', 'BRANCH']


def test_a_row_names_the_branch_and_not_only_the_number(listing) -> None:
    """A number is a per-repo counter, so `#1` in a cross-repo listing identifies
    nothing and cannot be pasted into a gh command. The branch can be both."""
    only = listed(listing(pr('dotfiles', 1, 'split-plan-check-verbs')))[0]

    assert 'split-plan-check-verbs' in only
    assert '#1' in only
    assert 'a change in dotfiles' in only


def test_a_row_names_where_the_repo_is_on_this_disk(listing) -> None:
    """A repo name is a label and two can collide across a registry; the path is
    what identifies a checkout, and it is what you go on to open."""
    only = listed(listing(pr('dotfiles', 1, 'a-branch', path='/home/chris/dotfiles')))[0]

    assert '/home/chris/dotfiles' in only or '~/dotfiles' in only


def test_a_repo_this_machine_has_not_cloned_says_so(listing) -> None:
    """That row is the one `prs` will refuse to open, so it has to say why before
    you pick it rather than after."""
    only = listed(listing(pr('service', 42, 'a-branch', path='')))[0]

    assert 'not cloned here' in only
    assert 'service' in only


def test_both_status_lines_say_their_state_in_words(listing) -> None:
    """This replaced a legend under the table, which made you carry a colour from
    the bottom of the window back up to a glyph."""
    only = listed(listing(pr('doit', 1, 'a-branch', checks='SUCCESS', review='CHANGES_REQUESTED')))[0]

    assert 'checks passing' in only
    assert 'review changes' in only


def test_a_state_nothing_has_reported_still_says_something(listing) -> None:
    only = listed(listing(pr('doit', 1, 'a-branch')))[0]

    assert 'checks not run' in only
    assert 'review no review' in only


def test_a_pr_the_forge_decided_nothing_about_says_how_many_reviews_were_posted(listing) -> None:
    """`no review` on a PR three reviewers read is the row saying the opposite of
    what happened."""
    only = listed(listing(pr('doit', 1, 'a-branch', reviews=3)))[0]

    assert 'review 3 posted' in only


def test_a_forge_decision_outranks_the_reviews_posted_beside_it(listing) -> None:
    """One line carries one state, and it is the blocking one."""
    only = listed(listing(pr('doit', 1, 'a-branch', review='CHANGES_REQUESTED', reviews=3)))[0]

    assert 'review changes' in only


def test_a_draft_is_marked_the_way_fleet_marks_it(listing) -> None:
    """Two surfaces over one dataset; a draft that shows in one and not the other
    is the listing disagreeing with itself about what is open."""
    assert '(draft)' in listed(listing(pr('doit', 7, 'wip', draft=True)))[0]


def test_the_diff_counts_files_then_lines(listing) -> None:
    """The three numbers ride in one cell so the row spends one column on size."""
    only = listed(listing(pr('doit', 1, 'a-branch', changed_files=7, additions=319, deletions=14)))[0]

    assert '7' in only
    assert '319' in only
    assert '14' in only


def test_a_provider_reporting_no_diff_shows_a_dash_and_never_a_zero(listing) -> None:
    """bbkt reports no stats at all. `+0 -0` would claim the PR changed nothing,
    which is a different and false statement from nobody having counted."""
    only = listed(listing(pr('etl', 1, 'a-branch', additions=None, deletions=None, changed_files=None)))[0]

    assert '\u2014' in only
    assert ' 0' not in only


def test_a_stacked_pr_names_its_parent_by_number(listing) -> None:
    """A stack is invisible in a flat listing: the child reads as ordinary work
    against the default branch, and reviewing it that way shows the parent's
    commits as its own. The parent goes in the cell as a number because two long
    branch names side by side is the version nobody reads."""
    blocks = listed(
        listing(
            pr('dotfiles', 1, 'split-plan-check-verbs'),
            pr('dotfiles', 2, 'language-toolchains', base='split-plan-check-verbs'),
            pr('doit', 3, 'a-branch'),
        )
    )

    assert re.search(r'language-toolchains \S+ #1', blocks[1])
    assert '#1' not in blocks[0].split('a change')[0]
    assert not re.search(r'a-branch \S+ #', blocks[2])


def test_a_base_matching_another_repos_branch_is_not_a_stack(listing) -> None:
    """A base only ever names a branch in its own repo, and `develop`, `wip` and
    `staging` recur across the registry. Keying the lookup on the branch alone
    passes every other test here and marks those rows as stacked on a stranger."""
    blocks = listed(listing(pr('doit', 1, 'shared-name'), pr('dotfiles', 2, 'other', base='shared-name')))

    assert not re.search(r'other \S+ #', blocks[1])


def test_a_fork_sharing_a_basename_is_not_a_stack(listing) -> None:
    """`repo` is a bare basename. pull-requests searches all of GitHub and filters
    to the registry by name, so a PR authored in someone else's `typos` arrives
    under the same `repo` as your own — and keying on it pairs two unrelated
    repositories, asserting a review order that does not exist."""
    blocks = listed(
        listing(
            pr('typos', 4, 'align-config'),
            pr('typos', 1188, 'other-work', slug='crate-ci/typos', base='align-config'),
        )
    )

    assert not re.search(r'other-work \S+ #', blocks[1])


def test_a_repo_whose_default_branch_is_master_is_not_marked_stacked(listing) -> None:
    """What makes a row stacked is that its base is some other open PR's head, not
    that its base is spelled something other than `main`. pull-requests reports no
    default branch, so the literal comparison has nothing true to compare against
    and would mark every row of a repo that still defaults to master."""
    blocks = listed(listing(pr('dotfiles', 1, 'a-branch', base='master'), pr('doit', 2, 'b-branch', base='master')))

    assert not any(re.search(r'-branch \S+ #\d', block) for block in blocks)


def test_a_pr_is_never_marked_as_stacked_on_itself(listing) -> None:
    """A row heading the branch it also targets would point at its own number. No
    forge can create one, but the marker is built from a lookup that would find
    it, and a provider reporting a degenerate base gets a sane row instead."""
    assert not re.search(r'self \S+ #\d', listed(listing(pr('dotfiles', 1, 'self', base='self')))[0])


def test_the_listing_is_plain_when_it_is_not_a_terminal(listing) -> None:
    """stdout is data. Colour written into a pipe is escape codes in whatever
    reads it next."""
    lines = listing(pr('doit', 1, 'a-branch', checks='SUCCESS'))

    assert all(line == plain(line) for line in lines)


def test_the_picker_feeds_one_record_per_pr(picker) -> None:
    """Records are NUL-separated so a two-line PR is one item. Newline-separated
    input would make every second line a selectable row with no PR behind it."""
    fed = picker(pr('dotfiles', 1, 'a-branch'), pr('doit', 2, 'b-branch'))

    assert [record.split('\t', 1)[0] for record in fed.split('\0')] == ['0', '1']
    assert all(len(record.split('\t', 1)[1].splitlines()) == 2 for record in fed.split('\0'))


def test_the_picker_marks_a_stacked_pr_the_way_the_listing_does(picker) -> None:
    """The picker is the default mode and the surface where a PR is chosen for
    review, so a child that reads here as ordinary work against the default
    branch gets reviewed against the wrong base. Two renderings of one dataset
    disagreeing about a stack is worse than neither showing it."""
    fed = picker(
        pr('dotfiles', 1, 'split-plan-check-verbs'),
        pr('dotfiles', 2, 'language-toolchains', base='split-plan-check-verbs'),
    )
    records = items(fed.split('\0'))

    assert re.search(r'language-toolchains \S+ #1', records[1])
    assert not re.search(r'split-plan-check-verbs \S+ #\d', records[0])


def test_the_picker_carries_no_header_row(picker) -> None:
    """fzf draws its own, where it cannot be selected. A header fed as a row is a
    row you can press enter on, and there is no PR behind it."""
    fed = picker(pr('dotfiles', 1, 'a-branch'))

    assert len(fed.split('\0')) == 1
    assert 'a change in dotfiles' in items(fed.split('\0'))[0]


def test_an_empty_backlog_says_so_rather_than_printing_a_bare_header(listing) -> None:
    """An empty backlog is a real and good answer, and a lone header row reads as
    output that got cut off."""
    assert listing() == ['No open PRs across the registry.']


def test_a_letter_on_the_list_takes_its_action_without_opening_the_menu(session) -> None:
    """The menu is one screen and the merge confirm is another, and pressing `m`
    on a row is a decision already made about which of the five it is."""
    run = session(pr('dotfiles', 7, 'a-branch'), replies=(chose(0, 'm'),))

    assert run.calls == 1
    assert 'gh pr merge 7' in run.stdout


def test_a_merge_tells_gh_the_method_so_its_own_wizard_never_runs(session) -> None:
    """Without a method gh asks which one, whether to delete the branch, and then
    to submit. All three are settled — a merge commit, and the forge deletes the
    remote branch — so every prompt is a keypress that could only be answered one
    way."""
    run = session(pr('dotfiles', 7, 'a-branch'), replies=(chose(0, 'm'),))

    assert '--merge' in run.stdout
    assert '--repo datapointchris/dotfiles' in run.stdout


def test_enter_answers_the_merge_confirm(session) -> None:
    """The prompt is there to show which PR is about to land, not to make landing
    one cost a keystroke it never varies."""
    run = session(pr('dotfiles', 7, 'a-branch'), replies=(chose(0, 'm'),), answer='\n')

    assert '[Y/n]' in run.stdout
    assert 'gh pr merge 7' in run.stdout


def test_an_answer_that_is_not_yes_leaves_the_pr_alone(session) -> None:
    """Enter being yes only works if a stray key is still no. Treating anything
    unrecognised as agreement would make a mistimed keypress a merge."""
    run = session(pr('dotfiles', 7, 'a-branch'), replies=(chose(0, 'm'),), answer='x\n')

    assert 'left alone' in run.stdout
    assert 'gh pr merge' not in run.stdout


def test_enter_on_a_row_still_opens_the_action_menu(session) -> None:
    """The letters are an accelerator, not a replacement. Arriving with no idea
    which action you want is what the menu is for, and it is still the default."""
    run = session(pr('dotfiles', 7, 'a-branch'), replies=(chose(0),))

    assert run.calls == 2
    assert 'view diff' in plain(run.fed(2))


def test_the_action_menu_names_the_key_that_takes_each_action(session) -> None:
    """A shortcut nothing shows is a shortcut nobody presses. The menu is where
    the letters are learned, so each row carries its own."""
    run = session(pr('dotfiles', 7, 'a-branch'), replies=(chose(0),))
    rows = [plain(row.split('\t', 1)[1]) for row in run.fed(2).splitlines()]

    assert [row.split()[0] for row in rows] == ['d', 'o', 'b', 'c', 'm']
    labels = ['view diff', 'open in browser', 'copy branch', 'comment', 'merge']
    assert all(label in row for label, row in zip(labels, rows, strict=True))


def test_a_letter_in_the_action_menu_takes_that_action(session) -> None:
    """The same letter has to mean the same thing one screen deeper, or arriving
    by enter would punish having learned it."""
    run = session(pr('dotfiles', 7, 'a-branch'), replies=(chose(0), chose(4, 'm')))

    assert run.calls == 2
    assert 'gh pr merge 7' in run.stdout


def test_the_list_binds_a_letter_for_every_action(session) -> None:
    """The bindings come off the same list the menu is drawn from, so a new
    action cannot arrive with a row and no key."""
    run = session(pr('dotfiles', 7, 'a-branch'))

    assert '--expect=d,o,b,c,m' in run.argv(1)


def test_the_list_names_its_keys_in_a_footer(session) -> None:
    """Under the rows, not above them: the column labels are already at the top
    and a second line up there reads as a second header row."""
    run = session(pr('dotfiles', 7, 'a-branch'))
    footer = next(arg for arg in run.argv(1) if arg.startswith('--footer='))

    assert 'm merge' in plain(footer)
    assert 'd view diff' in plain(footer)
