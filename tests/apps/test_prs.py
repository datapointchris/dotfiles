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
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
PRS = REPO / 'apps' / 'common' / 'prs'


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
def listing(tmp_path: Path):
    """Run `prs --list` over a fixed set of rows, returning its stdout lines.

    PATH inherits rather than naming /usr/bin, because the pipeline needs the
    real jq and jq is a brew package on macOS. `bin_dir` first is what shadows
    `pr-list`.
    """
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()

    def _listing(*rows: dict[str, Any]) -> list[str]:
        stub = bin_dir / 'pr-list'
        stub.write_text(f"#!/bin/sh\ncat <<'JSON'\n{json.dumps(list(rows))}\nJSON\n")
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        result = subprocess.run(
            [str(PRS), '--list'],
            capture_output=True,
            text=True,
            env={'HOME': str(tmp_path), 'PATH': f'{bin_dir}:{os.environ["PATH"]}'},
        )
        assert result.returncode == 0, result.stderr
        return result.stdout.splitlines()

    return _listing


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


def test_an_empty_backlog_says_so_rather_than_printing_a_bare_header(listing) -> None:
    """An empty backlog is a real and good answer, and a lone header row reads as
    output that got cut off."""
    assert listing() == ['No open PRs.']
