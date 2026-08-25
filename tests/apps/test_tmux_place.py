"""Where `tmux-place` puts a pane, decided without a tmux server anywhere near it.

`place()` is a pure function over window dimensions, the panes already there, and
what is being placed. That is the whole reason the module is arranged this way:
the size rule, pair adjacency and the coordinator's promotion are the behaviour
worth pinning, and every one of them is reachable here for the cost of building a
dataclass.

The windows these tests build carry the arithmetic tmux itself performs -- even
columns with a divider between them, even rows with a border row per pane. The
numbers were checked against a live server before they were written down: two
columns of a 377-wide window are 188 wide at lefts 0 and 189, three are 125 wide,
and an 81-row window splits into 39 and 40. `layout()` reproduces exactly that, so
a fixture is what tmux would have produced rather than a convenient approximation.

The last two tests reach `execute()`, where the tmux calls live. `subprocess.run`
is replaced and the argv the module would have used is read back, so what is
asserted is how a pane is addressed rather than what tmux did with it.

Run with: pytest tests/apps/test_tmux_place.py
"""

from __future__ import annotations

from typing import Any

import pytest

WINDOW = 377
HEIGHT = 81
"""The measured window this whole layout was derived from. Every expected number
below is computed from these two rather than restated, so a test says which rule
produced it."""


def layout(module, window_id: str, columns, width: int = WINDOW, height: int = HEIGHT, session: str = 'system'):
    """A window laid out the way tmux lays one out.

    `columns` is a list of columns, each a list of `(pane_id, role)` or
    `(pane_id, role, pair)`. Columns divide the width evenly with one divider
    column between them and the rightmost absorbing the remainder; panes divide
    the column the same way, one row shorter than the window because each pane
    gives a row to its border.
    """
    count = len(columns)
    share = (width - (count - 1)) // count
    panes = []
    left = 0
    for index, column in enumerate(columns):
        column_width = share if index < count - 1 else width - left
        rows = len(column)
        row_share = (height - 1 - (rows - 1)) // rows
        top = 0
        for row, spec in enumerate(column):
            pane_id, role = spec[0], spec[1]
            pair = spec[2] if len(spec) > 2 else ''
            pane_height = row_share if row < rows - 1 else height - 1 - top
            panes.append(
                module.Pane(
                    pane_id=pane_id,
                    left=left,
                    top=top,
                    width=column_width,
                    height=pane_height,
                    role=module.Role(role),
                    pair=pair,
                )
            )
            top += pane_height + 1
        left += column_width + 1
    return module.Window(window_id=window_id, width=width, height=height, session=session, panes=tuple(panes))


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
    assert tmux_place.fits_down(2 * tmux_place.MIN_ROWS) == 1
    assert tmux_place.fits_down(2 * tmux_place.MIN_ROWS + 1) == 2


def test_an_even_share_matches_what_tmux_divides_a_window_into(tmux_place):
    assert tmux_place.even_share(WINDOW, 1) == WINDOW
    assert tmux_place.even_share(WINDOW, 2) == 188
    assert tmux_place.even_share(WINDOW, 3) == 125


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


def test_a_reviewer_sits_directly_below_its_worker(tmux_place, build):
    window = build('@1', [[('%1', 'coordinator')], [('%2', 'worker')]])
    request = tmux_place.Request(role=tmux_place.Role.REVIEWER, caller='%1', partner='%2')
    placement = tmux_place.place([window], request)

    assert placement.window == '@1'
    assert placement.target == '%2'
    assert placement.direction is tmux_place.Direction.BELOW
    assert placement.pair == '%2'
    assert placement.readable


def test_a_pair_splits_the_measured_window_into_the_two_readable_halves(tmux_place, build):
    window = build('@1', [[('%1', 'coordinator')], [('%2', 'worker')]])
    request = tmux_place.Request(role=tmux_place.Role.REVIEWER, caller='%1', partner='%2')
    placement = tmux_place.place([window], request)

    # 39 below and 40 above, which is what tmux produced on the window this was
    # measured on, and both are over the 35-row minimum.
    assert placement.size == 39
    assert placement.size >= tmux_place.MIN_ROWS
    assert HEIGHT - 1 - 1 - placement.size >= tmux_place.MIN_ROWS


def test_a_reviewer_never_moves_to_another_window_to_find_room(tmux_place, build):
    # A pair is a unit, so a client too short to stack one has no answer that
    # separates them. The placement stands and says it is under the minimum.
    short = build('@1', [[('%1', 'coordinator')], [('%2', 'worker')]], height=40)
    request = tmux_place.Request(role=tmux_place.Role.REVIEWER, caller='%1', partner='%2')
    placement = tmux_place.place([short], request)

    assert placement.window == '@1'
    assert placement.target == '%2'
    assert not placement.readable
    assert str(tmux_place.MIN_ROWS) in placement.why


# --- overflow: the third pair promotes the coordinator ---


def full_window(build):
    """The measured target layout: a coordinator and two pairs, all three columns used."""
    return build(
        '@1',
        [
            [('%1', 'coordinator')],
            [('%2', 'worker'), ('%3', 'reviewer', '%2')],
            [('%4', 'worker'), ('%5', 'reviewer', '%4')],
        ],
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


def test_the_promoted_coordinator_gets_one_minimum_slot_of_monitor_beside_it(tmux_place, build, worker_request):
    placement = tmux_place.place([full_window(build)], worker_request())

    assert placement.promote.monitor_width == tmux_place.MIN_COLUMNS
    assert placement.promote.monitor_command == tmux_place.MONITOR_COMMAND
    # The coordinator keeps everything the monitor and its divider do not take,
    # which is still well over a readable width on this client.
    assert WINDOW - tmux_place.MIN_COLUMNS - 1 >= tmux_place.MIN_COLUMNS


def test_a_promoted_coordinators_window_is_never_placed_into_again(tmux_place, build):
    promoted = build('@2', [[('%1', 'coordinator')], [('%9', 'monitor')]])
    assert not tmux_place.eligible(promoted)


def test_a_fourth_pair_opens_a_window_because_nothing_is_left_to_promote(tmux_place, build, worker_request):
    pairs = build(
        '@1',
        [
            [('%2', 'worker'), ('%3', 'reviewer', '%2')],
            [('%4', 'worker'), ('%5', 'reviewer', '%4')],
            [('%6', 'worker'), ('%7', 'reviewer', '%6')],
        ],
    )
    promoted = build('@2', [[('%1', 'coordinator')], [('%9', 'monitor')]])
    placement = tmux_place.place([pairs, promoted], worker_request())

    assert placement.opens_window
    assert placement.promote is None
    assert placement.near == '@2', 'the new window opens beside the caller, so it lands in the caller’s session'


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
    promoted = build('@2', [[('%1', 'coordinator')], [('%9', 'monitor')]])
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
    promoted = build('@2', [[('%1', 'coordinator')], [('%9', 'monitor')]])
    placement = tmux_place.place([pairs, promoted], worker_request())

    assert placement.window == '@1'
    assert placement.promote is None


# --- density is a ceiling, not a target ---


def test_a_pair_alone_in_a_window_keeps_the_whole_width(tmux_place, build):
    window = build('@1', [[('%2', 'worker'), ('%3', 'reviewer', '%2')]])
    assert window.columns[0][0].width == WINDOW
    assert tmux_place.even_share(WINDOW, 1) == WINDOW


def test_a_partly_full_window_is_filled_before_a_emptier_one(tmux_place, build, worker_request):
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


# --- a pane this tool did not place ---


def test_an_unmarked_pane_is_unknown_rather_than_one_of_ours(tmux_place, build):
    window = build('@1', [[('%1', 'coordinator')], [('%9', 'unknown')]])
    assert not tmux_place.ours(window.columns[1])
    assert tmux_place.ours(window.columns[0])


def test_a_hand_made_pane_takes_its_width_out_of_what_the_window_can_hold(tmux_place, build):
    # Half of a 377-wide window taken by hand leaves 188 columns, which holds one
    # agent and no more. Dividing the whole window would answer three.
    shared = build('@1', [[('%1', 'coordinator')], [('%9', 'unknown')]])
    assert tmux_place.free_columns(shared) == 0

    # And the coordinator alone in the same window has two columns to give.
    alone = build('@2', [[('%1', 'coordinator')]])
    assert tmux_place.free_columns(alone) == 2


def test_a_hand_made_pane_is_never_the_pane_that_gets_split(tmux_place, build, worker_request):
    # Wide enough that a column is still free beside somebody else's pane, so the
    # question is which pane gets split rather than whether one does.
    window = build('@1', [[('%1', 'coordinator')], [('%9', 'unknown')]], width=500)
    assert tmux_place.free_columns(window) == 1

    placement = tmux_place.place([window], worker_request())
    assert placement.target == '%1'


def test_a_window_holding_nothing_this_tool_placed_is_left_alone(tmux_place, build, worker_request):
    theirs = build('@1', [[('%8', 'unknown')], [('%9', 'unknown')]])
    mine = build('@2', [[('%1', 'coordinator')]])
    placement = tmux_place.place([theirs, mine], worker_request())

    assert not tmux_place.eligible(theirs)
    assert placement.window == '@2'


def test_a_window_with_a_hand_made_pane_in_it_is_never_reflowed(tmux_place, build, worker_request):
    # Balancing resizes every column, and one of them would be somebody's own
    # work. The new column still arrives; nothing already there moves.
    mixed = build('@1', [[('%1', 'coordinator')], [('%9', 'unknown')]])
    clean = build('@2', [[('%1', 'coordinator')]])

    assert not tmux_place.place([mixed], worker_request()).balance
    assert tmux_place.place([clean], worker_request()).balance


# --- what refuses, and why ---


def test_a_reviewer_for_a_pane_that_is_not_there_refuses(tmux_place, build):
    window = build('@1', [[('%1', 'coordinator')]])
    request = tmux_place.Request(role=tmux_place.Role.REVIEWER, caller='%1', partner='%404')
    with pytest.raises(tmux_place.Usage, match='%404'):
        tmux_place.place([window], request)


def test_a_reviewer_with_no_worker_named_refuses(tmux_place, build):
    window = build('@1', [[('%1', 'coordinator')]])
    request = tmux_place.Request(role=tmux_place.Role.REVIEWER, caller='%1')
    with pytest.raises(tmux_place.Usage, match='--for'):
        tmux_place.place([window], request)


def test_a_second_reviewer_for_one_worker_refuses(tmux_place, build):
    window = build('@1', [[('%1', 'coordinator')], [('%2', 'worker'), ('%3', 'reviewer', '%2')]])
    request = tmux_place.Request(role=tmux_place.Role.REVIEWER, caller='%1', partner='%2')
    with pytest.raises(tmux_place.Usage, match='%3'):
        tmux_place.place([window], request)


def test_a_reviewer_under_something_that_is_not_a_worker_refuses(tmux_place, build):
    window = build('@1', [[('%1', 'coordinator')]])
    request = tmux_place.Request(role=tmux_place.Role.REVIEWER, caller='%1', partner='%1')
    with pytest.raises(tmux_place.Usage, match='coordinator'):
        tmux_place.place([window], request)


# --- what tmux says about a window, and what it renders ---


def test_a_never_displayed_windows_stale_size_is_corrected_from_its_panes(tmux_place):
    # Measured on a live server: tmux reported `@1` as an 80x24 window holding a
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
    # Chris has a session called `de initiative`. A field after it would be
    # shifted by its contents, so it is last and the split stops before it.
    assert tmux_place.parse_window('@1\t377\t81\tde initiative') == ('@1', 377, 81, 'de initiative')
    assert tmux_place.WINDOW_FIELDS.endswith('#{session_name}')


def test_a_tab_inside_a_session_name_cannot_shift_a_column(tmux_place):
    assert tmux_place.parse_window('@1\t377\t81\tde\tinitiative') == ('@1', 377, 81, 'de\tinitiative')


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

Three distinct lefts, so two of them get resized and the rightmost is left to
absorb the remainder."""


@pytest.fixture
def recorded(tmux_place, monkeypatch):
    """Run `execute` against a recorded subprocess and hand back every argv.

    Answers per verb rather than with one canned string. `-P -F '#{pane_id}'`
    wants a pane id back and the reflow wants a pane listing, and a fake that
    returns the same thing to both would have the module parse a pane id as a
    layout.
    """
    calls: list[list[str]] = []

    class Completed:
        def __init__(self, stdout: str) -> None:
            self.returncode = 0
            self.stdout = stdout
            self.stderr = ''

    def record(command: Any, *_args: Any, **_kwargs: Any) -> Completed:
        argv = list(command)
        calls.append(argv)
        return Completed(BALANCE_READBACK if 'list-panes' in argv else '%99\n')

    monkeypatch.setattr(tmux_place.subprocess, 'run', record)
    monkeypatch.setattr(tmux_place.shutil, 'which', lambda name: f'/usr/bin/{name}')

    def run(placement, command=('claude', 'go'), cwd='/tmp/work', window_name='agents'):
        tmux_place.execute(placement, command, cwd, window_name)
        return calls

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
    # The only pane listing is the reflow's, which runs after the split and reads
    # left edges. Nothing compares a pane list from before against one from after.
    listings = [call for call in calls if 'list-panes' in call]
    assert all(call[call.index('-F') + 1] == tmux_place.COLUMN_FIELDS for call in listings)


def test_the_placed_pane_carries_its_role_on_itself(tmux_place, build, recorded):
    window = build('@1', [[('%1', 'coordinator')], [('%2', 'worker')]])
    request = tmux_place.Request(role=tmux_place.Role.REVIEWER, caller='%1', partner='%2')
    calls = recorded(tmux_place.place([window], request))

    marks = [call for call in calls if 'set-option' in call and '-p' in call]
    assert [f'@{tmux_place.PANE_ROLE}', 'reviewer'] == marks[0][-2:]
    assert [f'@{tmux_place.PANE_PAIR}', '%2'] == marks[1][-2:]


def test_a_new_column_is_split_without_a_size_and_reflowed_afterwards(tmux_place, build, worker_request, recorded):
    # Asking tmux for a column wider than the pane being split is refused
    # outright, and after a reflow the requested size would be overwritten
    # anyway. The width arrives through `resize-pane` instead.
    window = build('@1', [[('%1', 'coordinator')]])
    calls = recorded(tmux_place.place([window], worker_request()))

    split = next(call for call in calls if 'split-window' in call)
    assert '-l' not in split
    resizes = [call for call in calls if 'resize-pane' in call]
    assert resizes, 'a new column that is never reflowed keeps the half tmux gave it'
    assert all(call[call.index('-x') + 1] == '188' for call in resizes)


def test_a_stacked_split_carries_its_size_because_nothing_reflows_it(tmux_place, build, recorded):
    window = build('@2', [[('%1', 'coordinator')], [('%2', 'worker')]])
    request = tmux_place.Request(role=tmux_place.Role.REVIEWER, caller='%1', partner='%2')
    calls = recorded(tmux_place.place([window], request))

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


def test_a_reviewer_is_never_spanned_across_the_window(tmux_place, build, recorded):
    # `-f` on a stacked split spans the window's full width, which would lift the
    # reviewer out of its worker's column and break the pair.
    window = build('@1', [[('%1', 'coordinator')], [('%2', 'worker')]])
    request = tmux_place.Request(role=tmux_place.Role.REVIEWER, caller='%1', partner='%2')
    calls = recorded(tmux_place.place([window], request))

    assert '-f' not in next(call for call in calls if 'split-window' in call)


def test_a_promotion_breaks_the_coordinator_out_before_anything_is_placed(tmux_place, build, worker_request, recorded):
    calls = recorded(tmux_place.place([full_window(build)], worker_request()))

    verbs = [call[1] for call in calls]
    assert verbs.index('break-pane') < verbs.index('split-window')
    broken = next(call for call in calls if 'break-pane' in call)
    assert broken[broken.index('-s') + 1] == '%1'
    assert '-d' in broken, 'the coordinator is mid-turn, so the focus stays where it was'


def test_a_new_window_opens_beside_the_caller_so_it_lands_in_that_session(tmux_place, build, worker_request, recorded):
    pairs = build(
        '@1',
        [
            [('%2', 'worker'), ('%3', 'reviewer', '%2')],
            [('%4', 'worker'), ('%5', 'reviewer', '%4')],
            [('%6', 'worker'), ('%7', 'reviewer', '%6')],
        ],
    )
    promoted = build('@2', [[('%1', 'coordinator')], [('%9', 'monitor')]])
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
