"""`prs --list` is the human rendering of `pr-list`, and the picker is the other.

Both were reported as reading worse than `gh pr list` for two reasons: no column
labels, and no branch anywhere — so a row named a PR by a number that collides
across the registry and a title that is the first thing to get truncated.

The seam is `pr-list` itself, shadowed on PATH. That is the whole point of the
split: the query lives in one place and this file only decides how a row reads,
so a rendering test has no business reaching a forge.

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

# `column` renders the stack marker's arrow as a literal `\xe2\x86\x90` escape
# unless the locale is UTF-8, so an env without one measures that escaping rather
# than the row. Named per platform because there is no portable spelling: glibc
# has C.UTF-8 built in and macOS does not ship it.
UTF8_LOCALE = 'en_US.UTF-8' if sys.platform == 'darwin' else 'C.UTF-8'


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


@pytest.fixture
def listing(tmp_path: Path, bin_dir: Path):
    """Run `prs --list` over a fixed set of rows, returning its stdout lines.

    PATH inherits rather than naming /usr/bin, because the pipeline needs the
    real jq and jq is a brew package on macOS. The locale is set because this
    listing is only ever read from a terminal that has one, and `column` measures
    a non-ASCII cell differently without it.
    """

    def _listing(*rows: dict[str, Any]) -> list[str]:
        stub_pr_list(bin_dir, rows)
        result = subprocess.run(
            [str(PRS), '--list'],
            capture_output=True,
            text=True,
            env={
                'HOME': str(tmp_path),
                'PATH': f'{bin_dir}:{os.environ["PATH"]}',
                'LC_ALL': UTF8_LOCALE,
            },
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
            env={
                'HOME': str(tmp_path),
                'PATH': f'{bin_dir}:{os.environ["PATH"]}',
                'LC_ALL': UTF8_LOCALE,
                'TMUX': '/tmp/tmux-fixture,1,0',
            },
        )
        assert result.returncode == 0, result.stderr
        return fed.read_text(encoding='utf-8').splitlines()

    return _picker


def cells(line: str) -> list[str]:
    """The row's columns, split on the run of spaces `column -t` pads with."""
    return re.split(r'\s{2,}', line.strip())


def test_the_columns_are_labelled(listing) -> None:
    """Five unlabelled columns read as a log line. `gh pr list` and `bbkt pr list`
    both label theirs, and the comparison against gh is the reported complaint."""
    lines = listing(pr('dotfiles', 1, 'a-branch'))
    assert cells(lines[0]) == ['REPO', 'PR', 'AGE', 'BRANCH', 'TITLE']


def test_a_row_names_the_branch_and_not_only_the_number(listing) -> None:
    """A number is a per-repo counter, so `#1` in a cross-repo listing identifies
    nothing and cannot be pasted into a gh command. The branch can be both."""
    lines = listing(pr('dotfiles', 1, 'split-plan-check-verbs'))
    assert cells(lines[1]) == ['dotfiles', '#1', '3d', 'split-plan-check-verbs', 'a change in dotfiles']


def test_a_pr_whose_provider_reports_no_branch_keeps_the_columns_aligned(listing) -> None:
    """An empty cell is where the table silently loses a column: BSD `column`
    collapses a repeated separator, so the title would slide left by one on macOS
    and the row would read as though the branch were the title."""
    lines = listing(pr('dotfiles', 1, 'a-branch'), pr('service', 42, '', slug='service'))
    assert len(cells(lines[2])) == 5
    assert cells(lines[2])[3] == '-'
    assert lines[1].index('a change in') == lines[2].index('a change in')


def test_a_draft_is_marked_the_way_fleet_marks_it(listing) -> None:
    """Two surfaces over one dataset; a draft that shows in one and not the other
    is the listing disagreeing with itself about what is open."""
    lines = listing(pr('doit', 7, 'wip', draft=True))
    assert cells(lines[1])[4] == 'a change in doit (draft)'


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
    assert re.fullmatch(r'language-toolchains \S+ #1', cells(lines[2])[3])
    assert 'split-plan-check-verbs' not in cells(lines[2])[3]
    assert cells(lines[1])[3] == 'split-plan-check-verbs'
    assert cells(lines[3]) == ['doit', '#3', '3d', 'a-branch', 'a change in doit']


def test_the_stack_marker_does_not_break_the_columns(listing) -> None:
    """The marker is the first cell that contains a space, and the first
    non-ASCII byte this listing has ever printed. It rides inside the branch cell
    only because `column -s` is a tab — delete that flag and the space becomes a
    column break, which this catches and nothing else does."""
    lines = listing(
        pr('dotfiles', 1, 'split-plan-check-verbs'),
        pr('dotfiles', 2, 'language-toolchains', base='split-plan-check-verbs'),
    )
    assert len(cells(lines[2])) == 5
    assert lines[1].index('a change in') == lines[2].index('a change in')
    assert lines[0].index('TITLE') == lines[2].index('a change in')


def test_a_base_matching_another_repos_branch_is_not_a_stack(listing) -> None:
    """A base only ever names a branch in its own repo, and `develop`, `wip` and
    `staging` recur across the registry. Keying the lookup on the branch alone
    passes every other test here and marks those rows as stacked on a stranger."""
    lines = listing(
        pr('doit', 1, 'shared-name'),
        pr('dotfiles', 2, 'other', base='shared-name'),
    )
    assert cells(lines[1])[3] == 'shared-name'
    assert cells(lines[2])[3] == 'other'


def test_a_fork_sharing_a_basename_is_not_a_stack(listing) -> None:
    """`repo` is a bare basename. pr-list searches all of GitHub and filters to the
    registry by name, so a PR authored in someone else's `typos` arrives under the
    same `repo` as your own — and keying on it pairs two unrelated repositories,
    asserting a review order that does not exist."""
    lines = listing(
        pr('typos', 4, 'align-config'),
        pr('typos', 1188, 'other-work', slug='crate-ci/typos', base='align-config'),
    )
    assert cells(lines[1])[3] == 'align-config'
    assert cells(lines[2])[3] == 'other-work'


def test_a_repo_whose_default_branch_is_master_is_not_marked_stacked(listing) -> None:
    """What makes a row stacked is that its base is some other open PR's head, not
    that its base is spelled something other than `main`. pr-list reports no
    default branch, so the literal comparison has nothing true to compare against
    and would mark every row of a repo that still defaults to master."""
    lines = listing(pr('dotfiles', 1, 'a-branch', base='master'), pr('doit', 2, 'b-branch', base='master'))
    assert cells(lines[1])[3] == 'a-branch'
    assert cells(lines[2])[3] == 'b-branch'


def test_a_pr_is_never_marked_as_stacked_on_itself(listing) -> None:
    """A row heading the branch it also targets would point at its own number. No
    forge can create one, but the marker is built from a lookup that would find
    it, and a provider reporting a degenerate base gets a sane row instead."""
    lines = listing(pr('dotfiles', 1, 'self', base='self'))
    assert cells(lines[1])[3] == 'self'


def fields(line: str) -> list[str]:
    """The picker's row, which is tab-separated rather than padded."""
    return line.split('\t')


def test_the_picker_marks_a_stacked_pr_the_way_the_listing_does(picker) -> None:
    """The picker is the default mode and the surface where a PR is chosen for
    review, so a child that reads here as ordinary work against the default
    branch gets reviewed against the wrong base. Two renderings of one dataset
    disagreeing about a stack is worse than neither showing it."""
    lines = picker(
        pr('dotfiles', 1, 'split-plan-check-verbs'),
        pr('dotfiles', 2, 'language-toolchains', base='split-plan-check-verbs'),
    )
    assert re.fullmatch(r'language-toolchains \S+ #1', fields(lines[1])[4])
    assert 'split-plan-check-verbs' not in fields(lines[1])[4]
    assert fields(lines[0])[4] == 'split-plan-check-verbs'


def test_the_picker_keeps_the_marker_inside_one_field(picker) -> None:
    """fzf splits the line on tabs and hides the first field, so a marker built
    with a tab instead of a space would push the title out of view and shift what
    `--with-nth` displays."""
    lines = picker(
        pr('dotfiles', 1, 'split-plan-check-verbs'),
        pr('dotfiles', 2, 'language-toolchains', base='split-plan-check-verbs'),
    )
    assert [len(fields(line)) for line in lines] == [6, 6]
    assert fields(lines[1])[0] == '1'
    assert fields(lines[1])[5] == 'a change in dotfiles'


def test_the_picker_leaves_an_unstacked_row_alone(picker) -> None:
    """Every row carrying an arrow is the same failure as no row carrying one:
    the marker only means something if it distinguishes."""
    lines = picker(pr('dotfiles', 1, 'a-branch'), pr('doit', 2, 'b-branch', base='master'))
    assert fields(lines[0]) == ['0', 'dotfiles', '#1', '3d', 'a-branch', 'a change in dotfiles']
    assert fields(lines[1]) == ['1', 'doit', '#2', '3d', 'b-branch', 'a change in doit']


def test_an_empty_backlog_says_so_rather_than_printing_a_bare_header(listing) -> None:
    """An empty backlog is a real and good answer, and a lone header row reads as
    output that got cut off."""
    assert listing() == ['No open PRs.']
