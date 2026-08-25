"""Where `tmux-place` puts a pane, decided without a tmux server anywhere near it.

`place()` is a pure function over window dimensions, the panes already there, and
what is being placed. That is the whole reason the module is arranged this way:
the size rule, pair adjacency and the coordinator's promotion are the behaviour
worth pinning, and every one of them is reachable here for the cost of building a
dataclass.

The windows these tests build carry the arithmetic tmux itself performs. The
numbers were checked against a live server before they were written down: two
columns of a 377-wide window are 188 wide at lefts 0 and 189, three are 125 wide,
and an 81-row window splits into a 40-row worker above a 39-row reviewer.
`layout()` reproduces exactly that.

Three layers are covered, because the pure one alone was not enough. `place()` and
its helpers are exercised directly. `execute()` and the command functions run
against a recorded `subprocess.run`, so the argv is the subject. And the cases at
the end drive a real tmux server started for the test, because a stub proves the
decisions and cannot prove what tmux does with them -- every defect that reached
review lived in that gap.

Run with: pytest tests/apps/test_tmux_place.py
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

WINDOW = 377
HEIGHT = 81
"""The measured window this whole layout was derived from. Every expected number
below is computed from these two rather than restated, so a test says which rule
produced it."""

needs_tmux = pytest.mark.interpreter('tmux')
"""A real tmux, declared rather than skipped by hand.

A plain `skipif` is silently skipped on a runner without tmux, which is the exact
failure `--require-interpreters` exists to stop."""


def layout(module, window_id: str, columns, width: int = WINDOW, height: int = HEIGHT, session: str = 'system', dedicated: bool = False):
    """A window laid out the way tmux lays one out.

    `columns` is a list of columns, each a list of `(pane_id, role)` or
    `(pane_id, role, pair)`.

    The two axes hand their remainder to opposite ends, and that is tmux's own
    behaviour rather than an inconsistency here. Columns are reflowed left to
    right by `resize-pane -x`, so the rightmost absorbs what is left over. A row
    is made by `split-window -v -l <n>`, which gives the new *bottom* pane that
    many rows and leaves the rest on the pane above -- so a worker is the taller
    half of its pair. A helper that got this backwards would build every fixture
    one row off the real thing, and the readability boundary is one row wide.
    """
    count = len(columns)
    share = (width - (count - 1)) // count
    panes = []
    left = 0
    for index, column in enumerate(columns):
        column_width = share if index < count - 1 else width - left
        rows = len(column)
        lower = (height - 1 - (rows - 1)) // rows
        heights = [height - 1 - (lower + 1) * (rows - 1)] + [lower] * (rows - 1)
        top = 0
        for row, spec in enumerate(column):
            pane_id, role = spec[0], spec[1]
            pair = spec[2] if len(spec) > 2 else ''
            panes.append(
                module.Pane(
                    pane_id=pane_id,
                    left=left,
                    top=top,
                    width=column_width,
                    height=heights[row],
                    role=module.Role(role),
                    pair=pair,
                )
            )
            top += heights[row] + 1
        left += column_width + 1
    return module.Window(window_id=window_id, width=width, height=height, session=session, dedicated=dedicated, panes=tuple(panes))


@pytest.fixture
def build(tmux_place):
    """`layout` with the module already bound, so a test names only its panes."""

    def make(window_id, columns, **kwargs):
        return layout(tmux_place, window_id, columns, **kwargs)

    return make


@pytest.fixture
def worker_request(tmux_place):
    def make(caller='%1', **kwargs):
        return tmux_place.Request(role=tmux_place.Role.WORKER, caller=caller, **kwargs)

    return make


@pytest.fixture
def reviewer_request(tmux_place):
    def make(partner, caller='%1', **kwargs):
        return tmux_place.Request(role=tmux_place.Role.REVIEWER, caller=caller, partner=partner, **kwargs)

    return make


def refusal(tmux_place, raised) -> str:
    """The refusal a raised `Usage` carries, as a value rather than its wording."""
    assert isinstance(raised.value, tmux_place.Usage)
    return raised.value.refusal


# --- the helper this file's fixtures are built on ---


def test_the_helper_reproduces_the_column_widths_a_real_tmux_produces(build):
    # Measured on a live 377x81 server before any of these fixtures were written.
    # A wrong helper would make every test below agree with a wrong module.
    one = build('@1', [[('%0', 'coordinator')]])
    assert [(pane.left, pane.width) for pane in one.panes] == [(0, 377)]

    two = build('@2', [[('%0', 'coordinator')], [('%1', 'worker')]])
    assert [(pane.left, pane.width) for pane in two.panes] == [(0, 188), (189, 188)]

    three = build('@3', [[('%0', 'coordinator')], [('%1', 'worker')], [('%2', 'worker')]])
    assert [(pane.left, pane.width) for pane in three.panes] == [(0, 125), (126, 125), (252, 125)]


def test_the_helper_puts_the_taller_half_of_a_pair_on_the_worker(build):
    # `split-window -v -l 39` gives the new bottom pane 39 rows and leaves 40 on
    # the pane above, so the worker is the taller half. The live capture reads
    # `%1 125x40 worker` above `%2 125x39 reviewer`.
    window = build('@1', [[('%1', 'worker'), ('%2', 'reviewer', '%1')]])
    worker, reviewer = window.panes
    assert (worker.height, reviewer.height) == (40, 39)
    assert worker.top == 0
    assert reviewer.top == 41


def test_the_helper_stays_correct_at_the_readability_boundary(tmux_place, build):
    # A window gives one row to the pane border before anything is split, so 72
    # rows is the smallest that stacks two readable panes and 71 is one short.
    # The fixture has to agree with the real thing on exactly that row, because
    # it is the row the verdict turns on.
    fits = build('@1', [[('%1', 'worker'), ('%2', 'reviewer', '%1')]], height=2 * tmux_place.MIN_ROWS + 2)
    assert [pane.height for pane in fits.panes] == [tmux_place.MIN_ROWS, tmux_place.MIN_ROWS]

    short = build('@2', [[('%1', 'worker'), ('%2', 'reviewer', '%1')]], height=2 * tmux_place.MIN_ROWS + 1)
    assert [pane.height for pane in short.panes] == [tmux_place.MIN_ROWS, tmux_place.MIN_ROWS - 1]


# --- the size rule, which every other number here is derived from ---


def test_the_measured_window_holds_three_columns_and_two_rows(tmux_place):
    assert tmux_place.fits_across(WINDOW) == 3
    assert tmux_place.fits_down(HEIGHT) == 2


def test_a_column_count_leaves_room_for_the_divider_between_columns(tmux_place):
    # Two 120-wide panes need 241 columns, not 240: the border between them is a
    # column of its own. A plain floor division answers two at 240 and is wrong.
    assert tmux_place.fits_across(2 * tmux_place.MIN_COLUMNS) == 1
    assert tmux_place.fits_across(2 * tmux_place.MIN_COLUMNS + 1) == 2


def test_a_narrower_client_holds_fewer_columns(tmux_place):
    assert tmux_place.fits_across(250) == 2
    assert tmux_place.fits_across(130) == 1
    assert tmux_place.fits_across(100) == 0


def test_a_shorter_client_cannot_stack_a_pair(tmux_place):
    # One row short of the column rule, and the asymmetry is tmux's: a pane gives
    # a row to its own border and no column to it. Two 35-row panes need 72 rows,
    # and at 71 the split really does produce a 34-row pane.
    assert tmux_place.fits_down(2 * tmux_place.MIN_ROWS + 1) == 1
    assert tmux_place.fits_down(2 * tmux_place.MIN_ROWS + 2) == 2
    assert tmux_place.fits_down(HEIGHT) == 2


def test_an_even_share_matches_what_tmux_divides_a_window_into(tmux_place):
    assert tmux_place.even_share(WINDOW, 1) == WINDOW
    assert tmux_place.even_share(WINDOW, 2) == 188
    assert tmux_place.even_share(WINDOW, 3) == 125


def test_one_predicate_decides_readable_on_both_axes(tmux_place):
    assert tmux_place.readable(tmux_place.MIN_COLUMNS, tmux_place.MIN_ROWS)
    assert not tmux_place.readable(tmux_place.MIN_COLUMNS - 1, tmux_place.MIN_ROWS)
    assert not tmux_place.readable(tmux_place.MIN_COLUMNS, tmux_place.MIN_ROWS - 1)


# --- the target layout, built one placement at a time ---


def test_the_first_worker_goes_beside_the_coordinator(tmux_place, build, worker_request):
    window = build('@1', [[('%1', 'coordinator')]])
    placement = tmux_place.place([window], worker_request())

    assert placement.window == '@1'
    assert placement.target == '%1'
    assert placement.direction is tmux_place.Direction.BESIDE
    assert placement.size == tmux_place.even_share(WINDOW, 2)
    assert placement.readable


def test_the_second_worker_makes_the_third_column(tmux_place, build, worker_request):
    window = build('@1', [[('%1', 'coordinator')], [('%2', 'worker'), ('%3', 'reviewer', '%2')]])
    placement = tmux_place.place([window], worker_request())

    assert placement.window == '@1'
    assert placement.size == tmux_place.even_share(WINDOW, 3) == 125
    assert placement.promote is None
    assert placement.readable


def test_a_new_column_splits_the_rightmost_pane_this_tool_placed(tmux_place, build, worker_request):
    window = build('@1', [[('%1', 'coordinator')], [('%2', 'worker'), ('%3', 'reviewer', '%2')]])
    placement = tmux_place.place([window], worker_request())

    # The worker, not its reviewer: a column is split at its top pane so the new
    # column arrives beside the whole pair rather than beside its lower half.
    assert placement.target == '%2'


def test_a_reviewer_sits_directly_below_its_worker(tmux_place, build, reviewer_request):
    window = build('@1', [[('%1', 'coordinator')], [('%2', 'worker')]])
    placement = tmux_place.place([window], reviewer_request('%2'))

    assert placement.window == '@1'
    assert placement.target == '%2'
    assert placement.direction is tmux_place.Direction.BELOW
    assert placement.pair == '%2'
    assert placement.readable


def test_a_pair_splits_the_measured_window_into_the_two_readable_halves(tmux_place, build, reviewer_request):
    window = build('@1', [[('%1', 'coordinator')], [('%2', 'worker')]])
    placement = tmux_place.place([window], reviewer_request('%2'))

    # 39 to the new reviewer, 40 left on the worker, which is what tmux produced
    # on the window this was measured on. Both are over the 35-row minimum.
    assert placement.size == 39
    assert tmux_place.readable(125, placement.size)
    assert tmux_place.readable(125, HEIGHT - 1 - 1 - placement.size)


def test_a_reviewer_never_moves_to_another_window_to_find_room(tmux_place, build, reviewer_request):
    # A pair is a unit, so a client too short to stack one has no answer that
    # separates them. The placement stands and reports that it is under the size.
    short = build('@1', [[('%1', 'coordinator')], [('%2', 'worker')]], height=40)
    placement = tmux_place.place([short], reviewer_request('%2'))

    assert placement.window == '@1'
    assert placement.target == '%2'
    assert not placement.readable


def test_the_readability_boundary_for_a_pair_is_where_fits_down_puts_it(tmux_place, build, reviewer_request):
    # The two have to agree, which is why `beneath` asks `readable` rather than
    # comparing against the minimums a second time.
    tall = build('@1', [[('%2', 'worker')]], height=2 * tmux_place.MIN_ROWS + 2)
    short = build('@1', [[('%2', 'worker')]], height=2 * tmux_place.MIN_ROWS + 1)

    assert tmux_place.place([tall], reviewer_request('%2', caller='%2')).readable
    assert not tmux_place.place([short], reviewer_request('%2', caller='%2')).readable


# --- overflow: the third pair promotes the coordinator ---


def full_window(build, window_id: str = '@1', session: str = 'system'):
    """The measured target layout: a coordinator and two pairs, all three columns used."""
    return build(
        window_id,
        [
            [('%1', 'coordinator')],
            [('%2', 'worker'), ('%3', 'reviewer', '%2')],
            [('%4', 'worker'), ('%5', 'reviewer', '%4')],
        ],
        session=session,
    )


def test_a_third_pair_moves_the_coordinator_out_rather_than_opening_a_window(tmux_place, build, worker_request):
    placement = tmux_place.place([full_window(build)], worker_request())

    assert placement.promote is not None
    assert placement.promote.pane == '%1'
    assert not placement.opens_window
    assert placement.window == '@1'


def test_the_third_pair_takes_the_column_the_coordinator_vacated(tmux_place, build, worker_request):
    placement = tmux_place.place([full_window(build)], worker_request())

    # Three pairs in that window afterwards, at the same 125 columns the
    # coordinator and two pairs had. The freed column is reused, not left empty.
    assert placement.size == tmux_place.even_share(WINDOW, 3)
    # Split off the rightmost pair, so the new column arrives on the right rather
    # than pushing both existing pairs sideways.
    assert placement.target == '%4'
    assert placement.readable


def test_the_promotion_moves_the_coordinator_and_never_the_pane_that_called(tmux_place, build, worker_request):
    # A worker that dispatches would otherwise break itself out of the pairs
    # window and take the dashboard with it.
    window = full_window(build)
    for caller in ('%1', '%2', '%4'):
        placement = tmux_place.place([window], worker_request(caller=caller))
        assert placement.promote.pane == '%1', f'{caller} promoted {placement.promote.pane}'


def test_the_promoted_coordinator_gets_one_minimum_slot_of_monitor_beside_it(tmux_place, build, worker_request):
    placement = tmux_place.place([full_window(build)], worker_request())

    assert placement.promote.monitor_width == tmux_place.MIN_COLUMNS
    assert placement.promote.monitor_command == tmux_place.MONITOR_COMMAND
    # The coordinator keeps everything the monitor and its divider do not take,
    # which is still well over a readable width on this client.
    assert tmux_place.readable(WINDOW - tmux_place.MIN_COLUMNS - 1, HEIGHT)


def test_a_promoted_window_is_never_placed_into_even_with_no_monitor_in_it(tmux_place, build):
    # The monitor is best effort, so it cannot be what marks the window. A machine
    # without the binary would otherwise get the next pair placed on top of the
    # coordinator that was just moved out.
    with_monitor = build('@2', [[('%1', 'coordinator')], [('%9', 'monitor')]], dedicated=True)
    without_monitor = build('@2', [[('%1', 'coordinator')]], dedicated=True)

    assert not tmux_place.eligible(with_monitor)
    assert not tmux_place.eligible(without_monitor)
    # And the same window without the mark would have been a target, which is what
    # makes the mark the thing doing the work here.
    assert tmux_place.eligible(build('@2', [[('%1', 'coordinator')]]))


def test_a_fourth_pair_opens_a_window_because_nothing_is_left_to_promote(tmux_place, build, worker_request):
    pairs = build(
        '@1',
        [
            [('%2', 'worker'), ('%3', 'reviewer', '%2')],
            [('%4', 'worker'), ('%5', 'reviewer', '%4')],
            [('%6', 'worker'), ('%7', 'reviewer', '%6')],
        ],
    )
    promoted = build('@2', [[('%1', 'coordinator')], [('%9', 'monitor')]], dedicated=True)
    placement = tmux_place.place([pairs, promoted], worker_request())

    assert placement.opens_window
    assert placement.promote is None
    assert placement.size is None, 'nothing is divided, so a number there would measure a window that does not exist'
    assert placement.near == '@2'


def test_a_fifth_pair_fills_the_overflow_window_rather_than_opening_another(tmux_place, build, worker_request):
    # The overflow window is a candidate like any other, not a place things were
    # sent once. Opening a window per pair would leave a row of windows holding
    # one agent each, and every one of those is a window to switch to.
    full = build(
        '@1',
        [
            [('%2', 'worker'), ('%3', 'reviewer', '%2')],
            [('%4', 'worker'), ('%5', 'reviewer', '%4')],
            [('%6', 'worker'), ('%7', 'reviewer', '%6')],
        ],
    )
    overflow = build('@3', [[('%10', 'worker'), ('%11', 'reviewer', '%10')]])
    promoted = build('@2', [[('%1', 'coordinator')], [('%9', 'monitor')]], dedicated=True)
    placement = tmux_place.place([full, overflow, promoted], worker_request())

    assert placement.window == '@3'
    assert not placement.opens_window
    assert placement.size == tmux_place.even_share(WINDOW, 2)


def test_the_coordinator_is_never_moved_back_when_a_pair_finishes(tmux_place, build, worker_request):
    # Room opens up in the pairs window and the coordinator stays where it is.
    # Moving out is triggered by need; moving back is triggered by nothing, and a
    # layout that reflowed on every completion would move everything under the
    # eye reading it.
    pairs = build('@1', [[('%2', 'worker'), ('%3', 'reviewer', '%2')]])
    promoted = build('@2', [[('%1', 'coordinator')], [('%9', 'monitor')]], dedicated=True)
    placement = tmux_place.place([pairs, promoted], worker_request())

    assert placement.window == '@1'
    assert placement.promote is None


# --- density is a ceiling, not a target ---


def test_a_pair_alone_in_a_window_keeps_the_whole_width(tmux_place, build):
    window = build('@1', [[('%2', 'worker'), ('%3', 'reviewer', '%2')]])
    assert window.columns[0][0].width == WINDOW
    assert tmux_place.even_share(WINDOW, 1) == WINDOW


def test_a_partly_full_window_is_filled_before_an_emptier_one(tmux_place, build, worker_request):
    fuller = build('@1', [[('%2', 'worker')], [('%4', 'worker')]])
    emptier = build('@3', [[('%6', 'worker')]])
    placement = tmux_place.place([emptier, fuller], worker_request(caller='%2'))

    assert placement.window == '@1'


def test_a_tie_between_two_roomy_windows_goes_to_the_callers_own(tmux_place, build, worker_request):
    mine = build('@3', [[('%1', 'coordinator')]])
    other = build('@1', [[('%6', 'worker')]])
    placement = tmux_place.place([other, mine], worker_request(caller='%1'))

    assert placement.window == '@3'


def test_windows_are_ordered_numerically_so_at_two_comes_before_at_eleven(tmux_place):
    assert tmux_place.window_order('@2') < tmux_place.window_order('@11')


# --- the caller's own session ---


def test_a_worker_never_lands_in_another_tmux_session(tmux_place, build, worker_request):
    # Fullness outranks the caller's own window, and without a session term that
    # sends the pane to a window in a session the caller cannot see.
    elsewhere = build('@1', [[('%8', 'coordinator')], [('%9', 'worker')]], session='alpha')
    home = build('@2', [[('%1', 'coordinator')]], session='beta')
    placement = tmux_place.place([elsewhere, home], worker_request(caller='%1'))

    assert placement.window == '@2'


def test_a_full_session_opens_a_window_rather_than_borrowing_another_sessions(tmux_place, build, worker_request):
    elsewhere = build('@1', [[('%8', 'worker')]], session='alpha')
    home = full_window(build, '@2', session='beta')
    placement = tmux_place.place([elsewhere, home], worker_request(caller='%2'))

    # Promotion first, and it stays inside beta either way.
    assert placement.window == '@2'
    assert placement.promote is not None


# --- a pane this tool did not place ---


def test_an_unmarked_pane_is_unknown_rather_than_one_of_ours(tmux_place, build):
    window = build('@1', [[('%1', 'coordinator')], [('%9', 'unknown')]])
    assert not tmux_place.ours(window.columns[1])
    assert tmux_place.ours(window.columns[0])


def test_a_window_holding_a_hand_made_pane_is_never_placed_into(tmux_place, build, worker_request):
    # Adding a column reflows every column in the window, so there is no way to
    # place beside somebody's pane without resizing it. Opening a window costs
    # nothing; losing a pane opened by hand is not recoverable.
    shared = build('@1', [[('%1', 'coordinator')], [('%9', 'unknown')]], width=500)
    assert tmux_place.free_columns(shared) > 0, 'the window has room, so eligibility is what refuses'
    assert not tmux_place.eligible(shared)

    placement = tmux_place.place([shared], worker_request())
    assert placement.opens_window


def test_a_hand_made_pane_takes_its_width_out_of_what_a_window_reports(tmux_place, build):
    # Nothing places by this count any more, but reporting three free columns in
    # a window with room for one would be wrong on screen as well as in a decision.
    shared = build('@1', [[('%1', 'coordinator')], [('%9', 'unknown')]])
    assert tmux_place.free_columns(shared) == 0

    alone = build('@2', [[('%1', 'coordinator')]])
    assert tmux_place.free_columns(alone) == 2


def test_a_window_too_small_for_one_readable_pane_reports_no_room(tmux_place, build):
    assert tmux_place.free_columns(build('@1', [[('%1', 'coordinator')]], height=20)) == 0


def test_a_window_holding_nothing_this_tool_placed_is_left_alone(tmux_place, build, worker_request):
    theirs = build('@1', [[('%8', 'unknown')], [('%9', 'unknown')]])
    mine = build('@2', [[('%1', 'coordinator')]])
    placement = tmux_place.place([theirs, mine], worker_request())

    assert not tmux_place.eligible(theirs)
    assert placement.window == '@2'


# --- the first dispatch, where nothing carries a mark ---


def test_the_first_caller_is_the_coordinator_and_plan_says_so_too(tmux_place, build, worker_request):
    # Nothing on a fresh server carries a mark, so without this no window is
    # eligible and every placement opens one of its own.
    bare = build('@1', [[('%0', 'unknown')]])
    placement = tmux_place.place([bare], worker_request(caller='%0'))

    assert not placement.opens_window
    assert placement.target == '%0'
    assert placement.size == tmux_place.even_share(WINDOW, 2)


def test_a_second_caller_does_not_become_a_second_coordinator(tmux_place, build, worker_request):
    # Once the server has a coordinator, an unmarked caller stays unmarked --
    # otherwise any shell someone dispatched from would crown itself.
    window = build('@1', [[('%1', 'coordinator')], [('%9', 'unknown')]], session='alpha')
    crowned = tmux_place.crown([window], '%9')
    roles = {pane.pane_id: pane.role for pane in crowned[0].panes}

    assert roles['%9'] is tmux_place.Role.UNKNOWN
    assert roles['%1'] is tmux_place.Role.COORDINATOR


def test_crown_leaves_a_marked_caller_exactly_as_it_found_it(tmux_place, build):
    window = build('@1', [[('%1', 'coordinator')], [('%2', 'worker')]])
    assert tmux_place.crown([window], '%2') == (window,)


# --- what refuses, and why ---


def test_a_reviewer_for_a_pane_that_is_not_there_refuses(tmux_place, build, reviewer_request):
    window = build('@1', [[('%1', 'coordinator')]])
    with pytest.raises(tmux_place.Usage) as raised:
        tmux_place.place([window], reviewer_request('%404'))
    assert refusal(tmux_place, raised) is tmux_place.Refusal.NO_SUCH_PANE


def test_a_reviewer_with_no_worker_named_refuses(tmux_place, build, reviewer_request):
    window = build('@1', [[('%1', 'coordinator')]])
    with pytest.raises(tmux_place.Usage) as raised:
        tmux_place.place([window], reviewer_request(''))
    assert refusal(tmux_place, raised) is tmux_place.Refusal.NO_PARTNER


def test_a_second_reviewer_for_one_worker_refuses(tmux_place, build, reviewer_request):
    window = build('@1', [[('%1', 'coordinator')], [('%2', 'worker'), ('%3', 'reviewer', '%2')]])
    with pytest.raises(tmux_place.Usage) as raised:
        tmux_place.place([window], reviewer_request('%2'))
    assert refusal(tmux_place, raised) is tmux_place.Refusal.REVIEWER_TAKEN


def test_a_reviewer_moved_to_another_window_still_holds_its_workers_place(tmux_place, build, reviewer_request):
    # The marks were kept precisely because they survive `break-pane`, so a guard
    # scoped to one window would be disarmed by the one operation they outlive.
    home = build('@1', [[('%1', 'coordinator')], [('%2', 'worker')]])
    moved = build('@2', [[('%3', 'reviewer', '%2')]])
    with pytest.raises(tmux_place.Usage) as raised:
        tmux_place.place([home, moved], reviewer_request('%2'))
    assert refusal(tmux_place, raised) is tmux_place.Refusal.REVIEWER_TAKEN


def test_a_reviewer_under_something_that_is_not_a_worker_refuses(tmux_place, build, reviewer_request):
    window = build('@1', [[('%1', 'coordinator')]])
    with pytest.raises(tmux_place.Usage) as raised:
        tmux_place.place([window], reviewer_request('%1'))
    assert refusal(tmux_place, raised) is tmux_place.Refusal.NOT_A_WORKER


def test_a_worker_given_a_partner_refuses_rather_than_ignoring_it(tmux_place, build, worker_request):
    window = build('@1', [[('%1', 'coordinator')]])
    with pytest.raises(tmux_place.Usage) as raised:
        tmux_place.place([window], worker_request(partner='%2'))
    assert refusal(tmux_place, raised) is tmux_place.Refusal.STRAY_PARTNER


def test_a_caller_that_is_not_on_this_server_refuses_on_both_paths(tmux_place, build, worker_request, reviewer_request):
    # Reachable from a nested tmux or another socket. The worker path used to
    # invent a window and report `0 columns` as an ordinary success.
    window = build('@1', [[('%9', 'unknown')]])
    for request in (worker_request(caller='%404'), reviewer_request('%9', caller='%404')):
        with pytest.raises(tmux_place.Usage) as raised:
            tmux_place.place([window], request)
        assert refusal(tmux_place, raised) is tmux_place.Refusal.UNKNOWN_CALLER


def test_a_role_that_is_not_placed_refuses(tmux_place, build):
    window = build('@1', [[('%1', 'coordinator')]])
    request = tmux_place.Request(role=tmux_place.Role.MONITOR, caller='%1')
    with pytest.raises(tmux_place.Usage) as raised:
        tmux_place.place([window], request)
    assert refusal(tmux_place, raised) is tmux_place.Refusal.UNPLACEABLE


def test_every_refusal_has_wording_and_every_wording_has_a_refusal(tmux_place):
    # The enum is what a caller branches on and the table is what a reader sees.
    # A member with no entry raises KeyError at the moment it is needed most.
    assert set(tmux_place.REFUSALS) == set(tmux_place.Refusal)


# --- what tmux says about a window, and what it renders ---


def test_a_never_displayed_windows_stale_size_is_corrected_from_its_panes(tmux_place):
    # Observed on a live server: tmux reported a window as 80x24 while it held a
    # 377x81 pane. Believing the window would place one column where three fit.
    pane = tmux_place.Pane('%2', left=0, top=0, width=377, height=81)
    assert tmux_place.reconcile(80, 24, [pane]) == (377, 81)


def test_a_window_that_agrees_with_its_panes_is_left_as_tmux_reports_it(tmux_place):
    panes = [
        tmux_place.Pane('%0', left=0, top=0, width=188, height=80),
        tmux_place.Pane('%1', left=189, top=0, width=188, height=80),
    ]
    assert tmux_place.reconcile(WINDOW, HEIGHT, panes) == (WINDOW, HEIGHT)


def test_an_empty_window_keeps_the_only_reading_there_is(tmux_place):
    assert tmux_place.reconcile(80, 24, []) == (80, 24)


# --- the format strings, where a session name with a space gets in ---


def test_a_session_name_with_a_space_in_it_parses_whole(tmux_place):
    # A tmux session name can hold a space. A field after it would be shifted by
    # its contents, so it is last and the split stops before it.
    assert tmux_place.parse_window('@1\t377\t81\t\ttwo words') == ('@1', 377, 81, False, 'two words')
    assert tmux_place.WINDOW_FIELDS.endswith('#{session_name}')


def test_a_tab_inside_a_session_name_cannot_shift_a_column(tmux_place):
    assert tmux_place.parse_window('@1\t377\t81\t\tde\tinitiative') == ('@1', 377, 81, False, 'de\tinitiative')


def test_a_dedicated_window_is_read_off_its_own_option(tmux_place):
    assert tmux_place.parse_window('@1\t377\t81\tcoordinator\tsystem')[3] is True
    assert tmux_place.parse_window('@1\t377\t81\t\tsystem')[3] is False


def test_only_one_free_text_field_is_ever_asked_for(tmux_place):
    # The window name would be a second one, and two of them cannot both be last.
    assert '#{window_name}' not in tmux_place.WINDOW_FIELDS
    assert tmux_place.WINDOW_FIELDS.count('#{session_name}') == 1


def test_a_pane_with_no_marks_parses_the_same_as_one_carrying_both(tmux_place):
    # An unset user option renders as an empty field rather than being dropped,
    # so the row always has eight fields and an unmarked pane is not a parse
    # failure -- it is a pane this tool did not place.
    assert tmux_place.PANE_FIELDS.count('\t') == 7

    window_id, bare = tmux_place.parse_pane('@1\t%2\t0\t0\t377\t80\t\t')
    assert window_id == '@1'
    assert bare == tmux_place.Pane('%2', left=0, top=0, width=377, height=80, role=tmux_place.Role.UNKNOWN, pair='')

    _, marked = tmux_place.parse_pane('@1\t%3\t126\t41\t125\t39\treviewer\t%2')
    assert marked.role is tmux_place.Role.REVIEWER
    assert marked.pair == '%2'


def test_a_role_tmux_hands_back_that_is_not_one_of_ours_reads_as_unknown(tmux_place):
    assert tmux_place.read_role('something-else') is tmux_place.Role.UNKNOWN
    assert tmux_place.read_role('worker') is tmux_place.Role.WORKER


# --- the tmux layer, where addressing goes wrong ---


BALANCE_READBACK = '%1\t0\n%99\t126\n%4\t252\n'
"""What `list-panes` answers the reflow with: one row per pane, id and left edge.

Three distinct lefts, so two get resized and the rightmost absorbs the remainder."""


@pytest.fixture
def recorded(tmux_place, monkeypatch):
    """Run the module against a recorded `subprocess.run` and hand back every argv.

    Answers per verb rather than with one canned string. `-P -F '#{pane_id}'` wants
    a pane id back, the reflow wants a pane listing, and the read-back wants a
    size -- a fake returning the same thing to all three would have the module
    parse a pane id as a layout.
    """
    calls: list[list[str]] = []

    class Completed:
        def __init__(self, stdout: str) -> None:
            self.returncode = 0
            self.stdout = stdout
            self.stderr = ''

    def answer(argv: list[str]) -> str:
        if 'list-panes' in argv:
            return BALANCE_READBACK
        if 'display-message' in argv:
            return '125\t80\n'
        return '%99\n'

    def record(command: Any, *_args: Any, **_kwargs: Any) -> Completed:
        argv = list(command)
        calls.append(argv)
        return Completed(answer(argv))

    monkeypatch.setattr(tmux_place.subprocess, 'run', record)
    monkeypatch.setattr(tmux_place.shutil, 'which', lambda name: f'/usr/bin/{name}')

    def run(placement, command=('claude', 'go'), cwd='/tmp/work', window_name='agents'):
        tmux_place.execute(placement, command, cwd, window_name)
        return calls

    run.calls = calls
    return run


def test_every_target_is_a_pane_or_window_id_and_never_an_index(tmux_place, build, worker_request, recorded):
    # Indices renumber on every split, so an index read before one names a
    # different pane after it. Measured while the geometry for this was taken:
    # splitting index 2 and then targeting index 3 hit the first column's lower
    # half rather than the second column.
    calls = recorded(tmux_place.place([full_window(build)], worker_request()))

    targets = [call[call.index('-t') + 1] for call in calls if '-t' in call]
    assert targets, 'nothing was targeted at all, so this proves nothing'
    assert all(target.startswith(('%', '@')) for target in targets), targets


def test_the_new_pane_is_named_by_tmux_rather_than_matched_back_afterwards(tmux_place, build, worker_request, recorded):
    window = build('@1', [[('%1', 'coordinator')]])
    calls = recorded(tmux_place.place([window], worker_request()))

    split = next(call for call in calls if 'split-window' in call)
    assert '-P' in split
    assert split[split.index('-F') + 1] == '#{pane_id}'
    listings = [call for call in calls if 'list-panes' in call]
    assert all(call[call.index('-F') + 1] == tmux_place.COLUMN_FIELDS for call in listings)


def test_the_placed_pane_carries_its_role_on_itself(tmux_place, build, reviewer_request, recorded):
    window = build('@1', [[('%1', 'coordinator')], [('%2', 'worker')]])
    calls = recorded(tmux_place.place([window], reviewer_request('%2')))

    marks = [call for call in calls if 'set-option' in call and '-p' in call]
    assert [f'@{tmux_place.PANE_ROLE}', 'reviewer'] == marks[0][-2:]
    assert [f'@{tmux_place.PANE_PAIR}', '%2'] == marks[1][-2:]


def test_a_new_column_is_split_without_a_size_and_reflowed_afterwards(tmux_place, build, worker_request, recorded):
    # Asking tmux for a column wider than the pane being split is refused
    # outright, and a reflow would overwrite the requested size anyway.
    window = build('@1', [[('%1', 'coordinator')]])
    calls = recorded(tmux_place.place([window], worker_request()))

    split = next(call for call in calls if 'split-window' in call)
    assert '-l' not in split
    resizes = [call for call in calls if 'resize-pane' in call]
    assert resizes, 'a new column that is never reflowed keeps the half tmux gave it'
    assert all(call[call.index('-x') + 1] == '188' for call in resizes)


def test_a_stacked_split_carries_its_size_because_nothing_reflows_it(tmux_place, build, reviewer_request, recorded):
    window = build('@2', [[('%1', 'coordinator')], [('%2', 'worker')]])
    calls = recorded(tmux_place.place([window], reviewer_request('%2')))

    split = next(call for call in calls if 'split-window' in call)
    assert split[split.index('-l') + 1] == '39'
    assert not [call for call in calls if 'resize-pane' in call]


def test_a_new_column_spans_the_full_window_height(tmux_place, build, worker_request, recorded):
    # Without `-f`, `split-window -h` splits the pane rather than the window, and
    # the top pane of a stacked pair owns only the upper half of its column. A
    # second pair placed that way measured 125x20 beside a 251-wide reviewer.
    window = build('@1', [[('%1', 'coordinator')], [('%2', 'worker'), ('%3', 'reviewer', '%2')]])
    calls = recorded(tmux_place.place([window], worker_request()))

    assert '-f' in next(call for call in calls if 'split-window' in call)


def test_a_reviewer_is_never_spanned_across_the_window(tmux_place, build, reviewer_request, recorded):
    # `-f` on a stacked split spans the window's full width, which would lift the
    # reviewer out of its worker's column and break the pair.
    window = build('@1', [[('%1', 'coordinator')], [('%2', 'worker')]])
    calls = recorded(tmux_place.place([window], reviewer_request('%2')))

    assert '-f' not in next(call for call in calls if 'split-window' in call)


def test_a_promotion_marks_its_window_before_it_starts_the_monitor(tmux_place, build, worker_request, recorded):
    calls = recorded(tmux_place.place([full_window(build)], worker_request()))

    verbs = [call[1] for call in calls]
    assert verbs.index('break-pane') < verbs.index('split-window')
    broken = next(call for call in calls if 'break-pane' in call)
    assert broken[broken.index('-s') + 1] == '%1'
    assert '-d' in broken, 'the coordinator is mid-turn, so the focus stays where it was'

    dedication = next(call for call in calls if 'set-option' in call and '-w' in call)
    assert dedication[-2:] == [f'@{tmux_place.WINDOW_ROLE}', 'coordinator']
    assert calls.index(dedication) < verbs.index('split-window')


def test_a_monitor_command_with_an_argument_is_resolved_by_its_first_word(tmux_place, build, worker_request, monkeypatch, recorded):
    # `shutil.which` takes a binary name, so a value carrying an argument came
    # back missing while the shell tmux runs it through would have found it.
    seen: list[str] = []

    def which(name):
        seen.append(name)
        # tmux itself still has to resolve, or the run refuses before it can
        # reach the question this test is about.
        return f'/usr/bin/{name}' if name in ('btop', 'tmux') else None

    monkeypatch.setattr(tmux_place.shutil, 'which', which)
    placement = tmux_place.place([full_window(build)], worker_request(monitor_command='btop --utf-force'))
    calls = recorded(placement)

    assert 'btop' in seen
    monitor = [call for call in calls if 'split-window' in call and 'btop --utf-force' in call]
    assert monitor, 'the monitor never started, so a command with a flag cannot carry one'


def test_a_new_window_opens_beside_the_caller_so_it_lands_in_that_session(tmux_place, build, worker_request, recorded):
    pairs = build(
        '@1',
        [
            [('%2', 'worker'), ('%3', 'reviewer', '%2')],
            [('%4', 'worker'), ('%5', 'reviewer', '%4')],
            [('%6', 'worker'), ('%7', 'reviewer', '%6')],
        ],
    )
    promoted = build('@2', [[('%1', 'coordinator')], [('%9', 'monitor')]], dedicated=True)
    calls = recorded(tmux_place.place([pairs, promoted], worker_request()))

    opened = next(call for call in calls if 'new-window' in call)
    assert opened[opened.index('-t') + 1] == '@2'
    assert '-a' in opened


def test_the_command_reaches_the_pane_as_one_quoted_argument(tmux_place, build, worker_request, recorded):
    window = build('@1', [[('%1', 'coordinator')]])
    calls = recorded(tmux_place.place([window], worker_request()), command=('claude', 'read the brief'))

    split = next(call for call in calls if 'split-window' in call)
    assert split[-1] == "claude 'read the brief'"
    assert split[split.index('-c') + 1] == '/tmp/work'


def test_the_pane_is_read_back_and_compared_against_what_was_announced(tmux_place, build, worker_request, monkeypatch):
    # `place()` announces a size and nothing below it was held to that number.
    # The read-back is what makes a mismatch reportable rather than invisible.
    window = build('@1', [[('%1', 'coordinator')]])
    placement = tmux_place.place([window], worker_request())

    class Completed:
        def __init__(self, stdout):
            self.returncode = 0
            self.stdout = stdout
            self.stderr = ''

    def record(command, *_args, **_kwargs):
        argv = list(command)
        if 'list-panes' in argv:
            return Completed(BALANCE_READBACK)
        if 'display-message' in argv:
            return Completed('93\t80\n')
        return Completed('%99\n')

    monkeypatch.setattr(tmux_place.subprocess, 'run', record)
    monkeypatch.setattr(tmux_place.shutil, 'which', lambda name: f'/usr/bin/{name}')

    landed = tmux_place.execute(placement, ('claude',), '', 'agents')
    assert landed.width == 93
    assert not landed.as_planned, 'tmux gave 93 where the plan said 188'
    assert not landed.readable


def test_a_failed_reflow_is_reported_rather_than_discarded(tmux_place, monkeypatch, capsys):
    # A reflow that fails leaves the column at the half-width the split gave it,
    # which is the outcome the whole tool exists to prevent, and nothing on
    # screen would have distinguished it from a balanced window.
    class Completed:
        def __init__(self, stdout, returncode=0, stderr=''):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def record(command, *_args, **_kwargs):
        argv = list(command)
        if 'list-panes' in argv:
            return Completed(BALANCE_READBACK)
        return Completed('', returncode=1, stderr='no space for new pane')

    monkeypatch.setattr(tmux_place.subprocess, 'run', record)
    monkeypatch.setattr(tmux_place.shutil, 'which', lambda name: f'/usr/bin/{name}')

    tmux_place.balance_columns('@1', 125)
    assert 'no space for new pane' in capsys.readouterr().err


# --- exit codes, and what a caller is told to retry ---


def test_a_failed_tmux_call_is_not_reported_as_a_usage_error(tmux_place, monkeypatch):
    # Nothing about the arguments is wrong and there are no different ones to try.
    # A caller told to retry a usage error would retry forever.
    class Completed:
        returncode = 1
        stdout = ''
        stderr = 'error connecting to /tmp/tmux-1000/nosuch (No such file or directory)'

    monkeypatch.setattr(tmux_place.subprocess, 'run', lambda *a, **k: Completed())
    monkeypatch.setattr(tmux_place.shutil, 'which', lambda name: f'/usr/bin/{name}')

    with pytest.raises(tmux_place.TmuxFailed) as raised:
        tmux_place.tmux('list-windows', '-a', '-F', tmux_place.WINDOW_FIELDS)
    assert not isinstance(raised.value, tmux_place.Usage)
    assert tmux_place.FAILURE == 1
    assert tmux_place.USAGE_ERROR == 2


def test_a_tmux_failure_names_the_subcommand_and_not_the_whole_argv(tmux_place, monkeypatch):
    # Interpolating the argv put a tab-separated format string in front of a
    # reader who needed the one line tmux wrote.
    class Completed:
        returncode = 1
        stdout = ''
        stderr = 'error connecting to /tmp/tmux-1000/nosuch'

    monkeypatch.setattr(tmux_place.subprocess, 'run', lambda *a, **k: Completed())
    monkeypatch.setattr(tmux_place.shutil, 'which', lambda name: f'/usr/bin/{name}')

    with pytest.raises(tmux_place.TmuxFailed) as raised:
        tmux_place.tmux('list-windows', '-a', '-F', tmux_place.WINDOW_FIELDS)
    message = str(raised.value)
    assert message == 'tmux list-windows: error connecting to /tmp/tmux-1000/nosuch'
    assert '#{' not in message


def test_a_machine_without_tmux_refuses_on_every_path_including_list(tmux_place, monkeypatch):
    # `list` read the server directly and gave an eleven-frame traceback, because
    # the guard lived at an entry point only two of the three verbs reached.
    monkeypatch.setattr(tmux_place.shutil, 'which', lambda _name: None)

    with pytest.raises(tmux_place.Usage) as raised:
        tmux_place.read_workspace()
    assert refusal(tmux_place, raised) is tmux_place.Refusal.NO_TMUX

    with pytest.raises(tmux_place.Usage) as caller:
        tmux_place.caller_pane()
    assert refusal(tmux_place, caller) is tmux_place.Refusal.NO_TMUX


def test_running_outside_tmux_refuses_with_its_own_reason(tmux_place, monkeypatch):
    monkeypatch.setattr(tmux_place.shutil, 'which', lambda name: f'/usr/bin/{name}')
    monkeypatch.delenv('TMUX', raising=False)
    monkeypatch.delenv('TMUX_PANE', raising=False)

    with pytest.raises(tmux_place.Usage) as raised:
        tmux_place.caller_pane()
    assert refusal(tmux_place, raised) is tmux_place.Refusal.OUTSIDE_TMUX


# --- the command surface ---


def test_no_arguments_prints_help_rather_than_an_error(tmux_place, capsys):
    assert tmux_place.build_parser().parse_args([]).verb is None

    parser = tmux_place.build_parser()
    parser.print_help()
    printed = capsys.readouterr().out
    assert 'list' in printed and 'plan' in printed and 'open' in printed


def test_every_screen_carries_an_example(tmux_place, capsys):
    # A leaf's help has to be usable by someone who arrived by tab-completion and
    # never read the root.
    parser = tmux_place.build_parser()
    parser.print_help()
    assert 'tmux-place plan worker' in capsys.readouterr().out

    for verb in ('list', 'plan', 'open', 'release'):
        with pytest.raises(SystemExit):
            parser.parse_args([verb, '--help'])
        screen = capsys.readouterr().out
        assert 'tmux-place plan worker' in screen, f'{verb} --help carries no example'
        assert screen.strip().splitlines()[0].startswith('usage:')


def test_every_verb_says_what_it_does_and_not_only_what_it_is_called(tmux_place, capsys):
    parser = tmux_place.build_parser()
    for verb in ('list', 'plan', 'open', 'release'):
        with pytest.raises(SystemExit):
            parser.parse_args([verb, '--help'])
        assert len(capsys.readouterr().out) > 400, f'{verb} --help is a flag list with no prose'


def test_the_nouns_on_a_screen_are_defined_on_it(tmux_place, capsys):
    # `coordinator` is not a value of any flag and not a command, so a reader
    # cannot resolve it without prose that says what one is.
    parser = tmux_place.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(['open', '--help'])
    screen = capsys.readouterr().out
    assert 'A coordinator is' in screen
    assert 'A worker is' in screen
    assert 'A reviewer' in screen


def test_the_default_window_name_is_spelled_once(tmux_place):
    # The dataclass default, the flag's default and the sentence in its help all
    # come from one constant, so they cannot drift apart.
    assert tmux_place.Request(role=tmux_place.Role.WORKER, caller='%1').window_name == tmux_place.WINDOW_NAME
    parsed = tmux_place.build_parser().parse_args(['plan', 'worker'])
    assert parsed.window_name == tmux_place.WINDOW_NAME

    # One literal in the whole module: the constant's own definition. The flag
    # default and its help sentence interpolate it rather than repeating it.
    source = Path(tmux_place.__file__).read_text()
    assert source.count(f"'{tmux_place.WINDOW_NAME}'") == 1


def test_the_set_is_listed_and_never_shown(tmux_place):
    # `list` owns the set and `show` owns a single instance. This verb prints
    # every window on the server.
    parser = tmux_place.build_parser()
    assert parser.parse_args(['list']).verb == 'list'
    with pytest.raises(SystemExit):
        parser.parse_args(['show'])


# --- the marks, from writing to retiring ---


def test_a_refused_open_leaves_no_mark_behind(tmux_place, build, monkeypatch):
    # Nothing ever cleared a mark, so a pane marked before a refusal stayed a
    # coordinator for the server's life and its window kept reading as a target.
    calls: list[list[str]] = []

    class Completed:
        returncode = 0
        stdout = '%99\n'
        stderr = ''

    def record(command, *_args, **_kwargs):
        calls.append(list(command))
        return Completed()

    monkeypatch.setattr(tmux_place.subprocess, 'run', record)
    monkeypatch.setattr(tmux_place.shutil, 'which', lambda name: f'/usr/bin/{name}')

    window = build('@1', [[('%0', 'unknown')]])
    with pytest.raises(tmux_place.Usage):
        tmux_place.place([window], tmux_place.Request(role=tmux_place.Role.REVIEWER, caller='%0', partner='%404'))
    assert not [call for call in calls if 'set-option' in call]


def test_release_drops_the_marks_and_the_window_dedication(tmux_place, monkeypatch):
    calls: list[list[str]] = []

    class Completed:
        def __init__(self, stdout):
            self.returncode = 0
            self.stdout = stdout
            self.stderr = ''

    def record(command, *_args, **_kwargs):
        argv = list(command)
        calls.append(argv)
        if 'list-panes' in argv:
            return Completed('@1\t%1\t0\t0\t377\t80\tcoordinator\t\n@1\t%9\t0\t0\t377\t80\t\t\n')
        if 'list-windows' in argv:
            return Completed('@1\t377\t81\tcoordinator\tsystem\n')
        return Completed('')

    monkeypatch.setattr(tmux_place.subprocess, 'run', record)
    monkeypatch.setattr(tmux_place.shutil, 'which', lambda name: f'/usr/bin/{name}')

    assert tmux_place.release([]) == 2

    unsets = [call for call in calls if 'set-option' in call]
    assert any('-pu' in call and call[-1] == f'@{tmux_place.PANE_ROLE}' for call in unsets)
    assert any('-wu' in call and call[-1] == f'@{tmux_place.WINDOW_ROLE}' for call in unsets)
    # The unmarked pane is left alone, which is the same rule the placement obeys.
    assert not any('%9' in call for call in unsets)


def test_release_can_be_pointed_at_one_pane(tmux_place, monkeypatch):
    calls: list[list[str]] = []

    class Completed:
        def __init__(self, stdout):
            self.returncode = 0
            self.stdout = stdout
            self.stderr = ''

    def record(command, *_args, **_kwargs):
        argv = list(command)
        calls.append(argv)
        if 'list-panes' in argv:
            return Completed('@1\t%1\t0\t0\t188\t80\tcoordinator\t\n@1\t%2\t189\t0\t188\t80\tworker\t\n')
        return Completed('')

    monkeypatch.setattr(tmux_place.subprocess, 'run', record)
    monkeypatch.setattr(tmux_place.shutil, 'which', lambda name: f'/usr/bin/{name}')

    assert tmux_place.release(['%2']) == 1
    assert not any('%1' in call for call in calls if 'set-option' in call)
    assert not [call for call in calls if 'list-windows' in call], 'a named pane is not a reason to clear every window'


# --- against a real tmux server ---


@pytest.fixture
def server(tmux_place, tmp_path, monkeypatch):
    """A tmux server of this test's own, at the measured geometry.

    A stub proves the decisions and cannot prove what tmux does with them. Every
    defect that reached review lived in that gap, and each was one command away.

    `$TMUX` is what a bare `tmux` reads to find its socket, so pointing it here
    sends the module's own calls to this server without any of them knowing.

    Addressed by socket path rather than by `-L <name>`: `tmp_path` is already
    unique per test and per parallel worker, so nothing has to invent a name that
    two workers might both choose.
    """
    socket = str(tmp_path / 'tmux.sock')
    idle = 'bash -c "while :; do sleep 5; done"'

    def control(*args: str) -> str:
        done = subprocess.run(['tmux', '-S', socket, *args], capture_output=True, text=True)
        assert done.returncode == 0, f'tmux {" ".join(args)}: {done.stderr}'
        # Newlines only. An unset user option renders as an empty trailing field,
        # and a full strip eats the tab in front of it -- so a pane with no role
        # comes back with one column fewer than a pane that has one.
        return done.stdout.rstrip('\n')

    # A session name with a space in it, because a real one can have one and the
    # format strings have to survive it.
    control('new-session', '-d', '-s', 'two words', '-x', str(WINDOW), '-y', str(HEIGHT), idle)
    monkeypatch.setenv('TMUX', f'{control("display-message", "-p", "#{socket_path}")},0,$0')
    monkeypatch.setenv('TMUX_PANE', control('list-panes', '-F', '#{pane_id}'))

    class Server:
        run = staticmethod(control)
        idle_command = ('bash', '-c', 'while :; do sleep 5; done')

        @staticmethod
        def geometry() -> list[tuple[str, int, int, int, str]]:
            rows = control('list-panes', '-a', '-F', '#{pane_id}\t#{pane_width}\t#{pane_height}\t#{pane_left}\t#{@place_role}')
            out = []
            for line in rows.splitlines():
                pane_id, width, height, left, role = line.split('\t')
                out.append((pane_id, int(width), int(height), int(left), role))
            return out

    try:
        yield Server()
    finally:
        subprocess.run(['tmux', '-S', socket, 'kill-server'], capture_output=True, text=True)


@needs_tmux
def test_a_real_first_dispatch_places_beside_the_caller_and_plan_agrees(tmux_place, server):
    # `plan` and `open` decided differently on exactly this placement, because one
    # marked the caller first and the other did not.
    caller = tmux_place.caller_pane()
    before = tmux_place.place(tmux_place.read_workspace(), tmux_place.Request(role=tmux_place.Role.WORKER, caller=caller))
    assert not before.opens_window
    assert before.size == tmux_place.even_share(WINDOW, 2)

    landed = tmux_place.execute(before, server.idle_command, '', 'agents')
    assert landed.as_planned
    assert [(width, left) for _, width, _, left, _ in server.geometry()] == [(188, 0), (188, 189)]


@needs_tmux
def test_a_real_pair_comes_out_at_the_measured_geometry(tmux_place, server):
    caller = tmux_place.caller_pane()
    request = tmux_place.Request(role=tmux_place.Role.WORKER, caller=caller)
    worker = tmux_place.execute(tmux_place.place(tmux_place.read_workspace(), request), server.idle_command, '', 'agents')

    review = tmux_place.Request(role=tmux_place.Role.REVIEWER, caller=caller, partner=worker.pane)
    reviewer = tmux_place.execute(tmux_place.place(tmux_place.read_workspace(), review), server.idle_command, '', 'agents')

    sizes = {pane: (width, height, left) for pane, width, height, left, _ in server.geometry()}
    assert sizes[worker.pane][:2] == (188, 40)
    assert sizes[reviewer.pane][:2] == (188, 39)
    assert sizes[worker.pane][2] == sizes[reviewer.pane][2], 'a reviewer shares its worker column'
    assert reviewer.as_planned


@needs_tmux
def test_a_real_second_pair_reaches_the_three_column_target(tmux_place, server):
    caller = tmux_place.caller_pane()
    for _ in range(2):
        request = tmux_place.Request(role=tmux_place.Role.WORKER, caller=caller)
        worker = tmux_place.execute(tmux_place.place(tmux_place.read_workspace(), request), server.idle_command, '', 'agents')
        review = tmux_place.Request(role=tmux_place.Role.REVIEWER, caller=caller, partner=worker.pane)
        tmux_place.execute(tmux_place.place(tmux_place.read_workspace(), review), server.idle_command, '', 'agents')

    widths = sorted({width for _, width, _, _, _ in server.geometry()})
    lefts = sorted({left for _, _, _, left, _ in server.geometry()})
    assert widths == [tmux_place.even_share(WINDOW, 3)]
    assert lefts == [0, 126, 252]


@needs_tmux
def test_a_real_hand_made_pane_is_never_resized_by_a_placement(tmux_place, server):
    # `split-window -h -f` reflows every column, so placing beside a pane opened
    # by hand is the same act as resizing it. Measured before this refused: a
    # 200-wide hand-made pane came back at 100.
    caller = tmux_place.caller_pane()
    # Narrow, so the window genuinely has a column left over. A hand-made pane
    # taking half the window would be refused for having no room, and the test
    # would pass without the invariant doing any work.
    server.run('split-window', '-d', '-h', '-l', str(tmux_place.MIN_COLUMNS), '-t', caller)
    theirs = {pane: width for pane, width, _, _, role in server.geometry() if pane != caller and role == ''}
    assert theirs, 'the fixture did not produce an unmarked pane'

    request = tmux_place.Request(role=tmux_place.Role.WORKER, caller=caller)
    home = next(window for window in tmux_place.crown(tmux_place.read_workspace(), caller) if window.holds(caller))
    assert tmux_place.free_columns(home) > 0, 'no room left, so eligibility is not what refuses'

    placement = tmux_place.place(tmux_place.read_workspace(), request)
    assert placement.opens_window

    tmux_place.execute(placement, server.idle_command, '', 'agents')
    after = {pane: width for pane, width, _, _, _ in server.geometry()}
    for pane, width in theirs.items():
        assert after[pane] == width, f'{pane} was resized from {width} to {after[pane]}'


@needs_tmux
def test_a_real_promotion_dedicates_its_window_without_a_monitor(tmux_place, server, monkeypatch):
    # The degraded path: no monitor binary, and the window still has to stop
    # being a placement target.
    caller = tmux_place.caller_pane()
    for _ in range(2):
        request = tmux_place.Request(role=tmux_place.Role.WORKER, caller=caller)
        worker = tmux_place.execute(tmux_place.place(tmux_place.read_workspace(), request), server.idle_command, '', 'agents')
        review = tmux_place.Request(role=tmux_place.Role.REVIEWER, caller=caller, partner=worker.pane)
        tmux_place.execute(tmux_place.place(tmux_place.read_workspace(), review), server.idle_command, '', 'agents')

    third = tmux_place.Request(role=tmux_place.Role.WORKER, caller=caller, monitor_command='nosuchmonitor-xyz')
    placement = tmux_place.place(tmux_place.read_workspace(), third)
    assert placement.promote is not None
    tmux_place.execute(placement, server.idle_command, '', 'agents')

    homes = [window for window in tmux_place.read_workspace() if window.holds(caller)]
    assert len(homes) == 1
    assert homes[0].dedicated
    assert not tmux_place.eligible(homes[0])

    # And the next worker does not land on top of the coordinator that just left.
    following = tmux_place.place(tmux_place.read_workspace(), tmux_place.Request(role=tmux_place.Role.WORKER, caller=caller))
    assert following.window != homes[0].window_id


@needs_tmux
def test_a_real_reviewer_that_moved_windows_still_blocks_a_second_one(tmux_place, server):
    caller = tmux_place.caller_pane()
    request = tmux_place.Request(role=tmux_place.Role.WORKER, caller=caller)
    worker = tmux_place.execute(tmux_place.place(tmux_place.read_workspace(), request), server.idle_command, '', 'agents')
    review = tmux_place.Request(role=tmux_place.Role.REVIEWER, caller=caller, partner=worker.pane)
    reviewer = tmux_place.execute(tmux_place.place(tmux_place.read_workspace(), review), server.idle_command, '', 'agents')

    server.run('break-pane', '-d', '-s', reviewer.pane, '-n', 'hold')
    moved = [pane for pane in tmux_place.read_workspace() for pane in pane.panes if pane.pane_id == reviewer.pane]
    assert moved[0].pair == worker.pane, 'the mark did not survive break-pane'

    with pytest.raises(tmux_place.Usage) as raised:
        tmux_place.place(tmux_place.read_workspace(), review)
    assert refusal(tmux_place, raised) is tmux_place.Refusal.REVIEWER_TAKEN


@needs_tmux
def test_the_command_functions_run_end_to_end_against_a_real_server(tmux_place, server, capsys):
    # `cmd_plan`, `cmd_open`, `request_from`, `caller_pane` and `read_workspace`
    # are reachable from no test of `place()`, because the fault they carry is in
    # what gets handed to it and what happens to what it returns.
    parser = tmux_place.build_parser()

    assert tmux_place.cmd_plan(parser.parse_args(['plan', 'worker'])) == 0
    planned = capsys.readouterr().out
    assert 'beside' in planned

    opened = parser.parse_args(['open', 'worker', '--', *server.idle_command])
    assert tmux_place.cmd_open(opened) == 0
    pane = capsys.readouterr().out.strip()

    assert tmux_place.cmd_list(False) == 0
    listing = capsys.readouterr().out
    assert pane in listing
    assert 'coordinator' in listing and 'worker' in listing

    # The plan said beside, and the pane the command made is where it said.
    placed = [p for window in tmux_place.read_workspace() for p in window.panes if p.pane_id == pane]
    assert placed[0].role is tmux_place.Role.WORKER
    assert placed[0].width == tmux_place.even_share(WINDOW, 2)


@needs_tmux
def test_a_real_release_clears_every_mark_it_wrote(tmux_place, server):
    caller = tmux_place.caller_pane()
    request = tmux_place.Request(role=tmux_place.Role.WORKER, caller=caller)
    tmux_place.execute(tmux_place.place(tmux_place.read_workspace(), request), server.idle_command, '', 'agents')
    tmux_place.mark(caller, tmux_place.Role.COORDINATOR)

    assert tmux_place.release([]) >= 2
    roles = {pane.role for window in tmux_place.read_workspace() for pane in window.panes}
    assert roles == {tmux_place.Role.UNKNOWN}
    assert not any(window.dedicated for window in tmux_place.read_workspace())
