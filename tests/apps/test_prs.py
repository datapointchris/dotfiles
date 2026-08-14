"""`prs --list` is the human rendering of `pr-list`, and the picker is the other.

Both were reported as reading worse than `gh pr list` for two reasons: no column
labels, and no branch anywhere — so a row named a PR by a number that collides
across the registry and a title that is the first thing to get truncated.

The seam is `pr-list` itself, shadowed on PATH. That is the whole point of the
split: the query lives in one place and this file only decides how a row reads,
so a rendering test has no business reaching a forge.

Assertions key on a column name rather than an index. The layout has grown twice
now, and each time an index renumbered every assertion in the file whether or not
the thing it was checking had moved.

Run with: pytest tests/apps/test_prs.py
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

COLUMNS = ('status', 'repo', 'number', 'diff', 'age', 'branch', 'title')

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
        'checks': '',
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
    write_stub(bin_dir, 'pr-list', f"cat <<'JSON'\n{json.dumps(list(rows))}\nJSON")


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
    """Run `prs --list` over a fixed set of rows, returning its stdout lines."""

    def _listing(*rows: dict[str, Any]) -> list[str]:
        stub_pr_list(bin_dir, rows)
        result = subprocess.run(
            [str(PRS), '--list'],
            capture_output=True,
            text=True,
            env=script_env(tmp_path, bin_dir),
        )
        assert result.returncode == 0, result.stderr
        return result.stdout.splitlines()

    return _listing


@pytest.fixture
def picker(tmp_path: Path, bin_dir: Path):
    """Run bare `prs` over a fixed set of rows, returning the lines it feeds fzf.

    fzf is the only place a displayed row can be read: everything past it fetches
    a ref and opens a tmux window. The stub records its stdin and exits 130, the
    code for a dismissed picker, which `prs` turns into a clean exit. nvim and
    tmux are stubbed only to satisfy the tool check on a machine without them,
    and TMUX is set because this refuses to run outside a session.
    """
    fed = tmp_path / 'fed-to-fzf'

    def _picker(*rows: dict[str, Any]) -> list[str]:
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
        return fed.read_text(encoding='utf-8').splitlines()

    return _picker


def plain(line: str) -> str:
    """The line with its colour stripped, which is what an assertion reads."""
    return ANSI.sub('', line)


def cells(line: str) -> list[str]:
    """The row's columns, split on the run of two spaces that separates them."""
    return re.split(r'\s{2,}', plain(line).strip())


def row(line: str) -> dict[str, str]:
    """A rendered row keyed by column name."""
    return dict(zip(COLUMNS, cells(line), strict=True))


def fed_row(line: str) -> dict[str, str]:
    """One of the picker's lines: a hidden index, then the whole rendered row."""
    return row(line.split('\t')[1])


def test_the_columns_are_labelled(listing) -> None:
    """Unlabelled columns read as a log line. `gh pr list` and `bbkt pr list`
    both label theirs, and the comparison against gh is the reported complaint."""
    lines = listing(pr('dotfiles', 1, 'a-branch'))
    assert cells(lines[0]) == ['ST', 'REPO', 'PR', 'DIFF', 'AGE', 'BRANCH', 'TITLE']


def test_a_row_names_the_branch_and_not_only_the_number(listing) -> None:
    """A number is a per-repo counter, so `#1` in a cross-repo listing identifies
    nothing and cannot be pasted into a gh command. The branch can be both."""
    lines = listing(pr('dotfiles', 1, 'split-plan-check-verbs'))
    assert row(lines[1]) == {
        'status': '●◆',
        'repo': 'dotfiles',
        'number': '#1',
        'diff': '2f +12 -4',
        'age': '3d',
        'branch': 'split-plan-check-verbs',
        'title': 'a change in dotfiles',
    }


def test_a_pr_whose_provider_reports_no_branch_keeps_the_columns_aligned(listing) -> None:
    """An empty cell is where a table silently loses a column, after which the
    title slides left by one and the row reads as though the branch were the
    title."""
    lines = listing(pr('dotfiles', 1, 'a-branch'), pr('service', 42, '', slug='service'))
    assert len(cells(lines[2])) == len(COLUMNS)
    assert row(lines[2])['branch'] == '-'
    assert plain(lines[1]).index('a change in') == plain(lines[2]).index('a change in')


def test_a_draft_is_marked_the_way_fleet_marks_it(listing) -> None:
    """Two surfaces over one dataset; a draft that shows in one and not the other
    is the listing disagreeing with itself about what is open."""
    lines = listing(pr('doit', 7, 'wip', draft=True))
    assert row(lines[1])['title'] == 'a change in doit (draft)'


def test_a_stacked_pr_names_its_parent_by_number(listing) -> None:
    """A stack is invisible in a flat listing: the child reads as ordinary work
    against the default branch, and reviewing it that way shows the parent's
    commits as its own. The parent goes in the cell as a number because two long
    branch names side by side is the version nobody reads."""
    lines = listing(
        pr('dotfiles', 1, 'split-plan-check-verbs'),
        pr('dotfiles', 2, 'language-toolchains', base='split-plan-check-verbs'),
        pr('doit', 3, 'a-branch'),
    )
    assert re.fullmatch(r'language-toolchains \S+ #1', row(lines[2])['branch'])
    assert 'split-plan-check-verbs' not in row(lines[2])['branch']
    assert row(lines[1])['branch'] == 'split-plan-check-verbs'
    assert row(lines[3])['branch'] == 'a-branch'


def test_the_stack_marker_does_not_break_the_columns(listing) -> None:
    """The marker is the only cell containing a space. It stays inside the branch
    cell because that space is a single one — widen it to the two that separate
    columns and the marker becomes a column of its own, which this catches."""
    lines = listing(
        pr('dotfiles', 1, 'split-plan-check-verbs'),
        pr('dotfiles', 2, 'language-toolchains', base='split-plan-check-verbs'),
    )
    assert len(cells(lines[2])) == len(COLUMNS)
    assert plain(lines[1]).index('a change in') == plain(lines[2]).index('a change in')
    assert plain(lines[0]).index('TITLE') == plain(lines[2]).index('a change in')


def test_a_base_matching_another_repos_branch_is_not_a_stack(listing) -> None:
    """A base only ever names a branch in its own repo, and `develop`, `wip` and
    `staging` recur across the registry. Keying the lookup on the branch alone
    passes every other test here and marks those rows as stacked on a stranger."""
    lines = listing(
        pr('doit', 1, 'shared-name'),
        pr('dotfiles', 2, 'other', base='shared-name'),
    )
    assert row(lines[1])['branch'] == 'shared-name'
    assert row(lines[2])['branch'] == 'other'


def test_a_fork_sharing_a_basename_is_not_a_stack(listing) -> None:
    """`repo` is a bare basename. pr-list searches all of GitHub and filters to the
    registry by name, so a PR authored in someone else's `typos` arrives under the
    same `repo` as your own — and keying on it pairs two unrelated repositories,
    asserting a review order that does not exist."""
    lines = listing(
        pr('typos', 4, 'align-config'),
        pr('typos', 1188, 'other-work', slug='crate-ci/typos', base='align-config'),
    )
    assert row(lines[1])['branch'] == 'align-config'
    assert row(lines[2])['branch'] == 'other-work'


def test_a_repo_whose_default_branch_is_master_is_not_marked_stacked(listing) -> None:
    """What makes a row stacked is that its base is some other open PR's head, not
    that its base is spelled something other than `main`. pr-list reports no
    default branch, so the literal comparison has nothing true to compare against
    and would mark every row of a repo that still defaults to master."""
    lines = listing(pr('dotfiles', 1, 'a-branch', base='master'), pr('doit', 2, 'b-branch', base='master'))
    assert row(lines[1])['branch'] == 'a-branch'
    assert row(lines[2])['branch'] == 'b-branch'


def test_a_pr_is_never_marked_as_stacked_on_itself(listing) -> None:
    """A row heading the branch it also targets would point at its own number. No
    forge can create one, but the marker is built from a lookup that would find
    it, and a provider reporting a degenerate base gets a sane row instead."""
    lines = listing(pr('dotfiles', 1, 'self', base='self'))
    assert row(lines[1])['branch'] == 'self'


def test_the_diff_counts_files_then_lines(listing) -> None:
    """The three numbers ride in one cell so the row spends one column on size."""
    lines = listing(pr('doit', 1, 'a-branch', changed_files=7, additions=319, deletions=14))
    assert row(lines[1])['diff'] == '7f +319 -14'


def test_a_provider_reporting_no_diff_shows_a_dash_and_never_a_zero(listing) -> None:
    """bbkt reports no stats at all. `+0 -0` would claim the PR changed nothing,
    which is a different and false statement from nobody having counted."""
    lines = listing(pr('etl', 1, 'a-branch', additions=None, deletions=None, changed_files=None))
    assert row(lines[1])['diff'] == '—'


def test_the_status_column_is_two_glyphs_whatever_the_state(listing) -> None:
    """State is carried by colour, never by swapping the character. Two different
    glyphs are not guaranteed the same cell width, and a row differing only in
    review state would then sit a column off from the one above it."""
    lines = listing(
        pr('doit', 1, 'a-branch', checks='SUCCESS', review='APPROVED'),
        pr('doit', 2, 'b-branch', checks='FAILURE', review='CHANGES_REQUESTED'),
        pr('doit', 3, 'c-branch'),
    )
    assert {row(line)['status'] for line in lines[1:]} == {'●◆'}


def test_the_listing_is_plain_when_it_is_not_a_terminal(listing) -> None:
    """stdout is data. Colour written into a pipe is escape codes in whatever
    reads it next."""
    lines = listing(pr('doit', 1, 'a-branch', checks='SUCCESS'))
    assert all(line == plain(line) for line in lines)


def test_the_picker_hides_an_index_and_shows_one_rendered_row(picker) -> None:
    """The index leads so the choice survives a title containing a tab or a
    leading number. Everything else is one field because the columns are padded
    before fzf sees them — split across fields, fzf joins them on the delimiter
    and the alignment is gone."""
    lines = picker(pr('dotfiles', 1, 'a-branch'), pr('doit', 2, 'b-branch'))
    assert [line.split('\t')[0] for line in lines] == ['0', '1']
    assert all(len(line.split('\t')) == 2 for line in lines)
    assert fed_row(lines[1])['title'] == 'a change in doit'


def test_the_picker_is_coloured_where_the_listing_piped_is_not(picker) -> None:
    """fzf is given `--ansi` and is always a terminal, so the picker is the one
    surface that always paints."""
    lines = picker(pr('dotfiles', 1, 'a-branch', checks='SUCCESS'))
    assert ANSI.search(lines[0])


def test_the_picker_marks_a_stacked_pr_the_way_the_listing_does(picker) -> None:
    """The picker is the default mode and the surface where a PR is chosen for
    review, so a child that reads here as ordinary work against the default
    branch gets reviewed against the wrong base. Two renderings of one dataset
    disagreeing about a stack is worse than neither showing it."""
    lines = picker(
        pr('dotfiles', 1, 'split-plan-check-verbs'),
        pr('dotfiles', 2, 'language-toolchains', base='split-plan-check-verbs'),
    )
    assert re.fullmatch(r'language-toolchains \S+ #1', fed_row(lines[1])['branch'])
    assert 'split-plan-check-verbs' not in fed_row(lines[1])['branch']
    assert fed_row(lines[0])['branch'] == 'split-plan-check-verbs'


def test_the_picker_leaves_an_unstacked_row_alone(picker) -> None:
    """Every row carrying an arrow is the same failure as no row carrying one:
    the marker only means something if it distinguishes."""
    lines = picker(pr('dotfiles', 1, 'a-branch'), pr('doit', 2, 'b-branch', base='master'))
    assert fed_row(lines[0])['branch'] == 'a-branch'
    assert fed_row(lines[1])['branch'] == 'b-branch'


def test_the_picker_carries_no_header_row(picker) -> None:
    """fzf draws its own, where it cannot be selected. A header fed as a row is a
    row you can press enter on, and there is no PR behind it."""
    lines = picker(pr('dotfiles', 1, 'a-branch'))
    assert len(lines) == 1
    assert fed_row(lines[0])['repo'] == 'dotfiles'


def test_an_empty_backlog_says_so_rather_than_printing_a_bare_header(listing) -> None:
    """An empty backlog is a real and good answer, and a lone header row reads as
    output that got cut off."""
    assert listing() == ['No open PRs across the registry.']
