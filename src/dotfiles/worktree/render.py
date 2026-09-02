"""The listing and the `show` blocks, as lines a terminal prints.

Widths come from the rows in hand rather than from constants, so a listing of one
repo is not padded to the width of every repo on the machine.
"""

from __future__ import annotations

from collections.abc import Sequence

from dotfiles.worktree import COLUMNS
from dotfiles.worktree import Worktree
from dotfiles.worktree.output import OUT
from dotfiles.worktree.panes import capture_pane
from dotfiles.worktree.repo import display_path


def session_cell(worktree: Worktree) -> str:
    """`?` where nobody could be asked, the same mark an unreadable ahead count gets."""
    if worktree.sessions is None:
        return '?'
    return ', '.join(f'{session.name} ({session.status})' for session in worktree.sessions)


def cells(worktree: Worktree) -> tuple[str, ...]:
    ahead = '?' if worktree.ahead is None else str(worktree.ahead)
    return (display_path(worktree.path), worktree.branch, ahead, str(worktree.state), session_cell(worktree))


def render_table(worktrees: Sequence[Worktree]) -> list[str]:
    """The listing, column-aligned, with its header first.

    Widths come from the rows in hand rather than from constants: a listing of
    every repo is as wide as its longest path and a single repo's is not, so a
    fixed width either truncates the one or pads the other. The last column is
    left unpadded — nothing follows it, and session names run long.
    """
    rows = [COLUMNS, *(cells(worktree) for worktree in worktrees)]
    widths = [max(len(row[column]) for row in rows) for column in range(len(COLUMNS) - 1)]
    return ['  '.join([*(cell.ljust(width) for cell, width in zip(row, widths, strict=False)), row[-1]]).rstrip() for row in rows]


def section(heading: str, body: str | None) -> None:
    if not body:
        return
    OUT.print('')
    OUT.print(f'[cyan]{heading}[/]', highlight=False)
    for line in body.splitlines():
        OUT.print(f'  {line}', markup=False, highlight=False)


def show_sessions(worktree: Worktree) -> None:
    """The session block, ending in each session's live pane.

    The pane rather than a summary, for the same reason tmux-sessions previews
    one: two sessions in one worktree are told apart by what is on their screens
    and by nothing else.
    """
    OUT.print('')
    OUT.print('[cyan]session[/]', highlight=False)
    if worktree.sessions is None:
        OUT.print('  unknown — claude-sessions could not be asked', markup=False, highlight=False)
        return
    if not worktree.sessions:
        OUT.print('  none', markup=False, highlight=False)
        return

    for session in worktree.sessions:
        detail = [session.status]
        if session.waiting:
            detail.append(f'waiting on {session.waiting}')
        if session.tmux:
            detail.append(session.tmux)
        OUT.print(f'  {session.name} — {", ".join(detail)}', markup=False, highlight=False)
        pane = capture_pane(session.tmux) if session.tmux else None
        for line in (pane or '').splitlines():
            OUT.print(f'  {line}', markup=False, highlight=False)
