"""Tests for menu-dashboard — lane composition, degradation, and the JSON model.

menu-dashboard is a uv single-file script, so it is loaded by path with
importlib. Unlike its siblings it binds no paths at import time (every backend is
a subprocess), so no environment setup is needed before importing it.

Backends are never invoked here: lanes are built from committed fixture payloads
at a fixed date, and the subprocess layer is exercised with fabricated commands.
Nothing in this file touches the network.
"""

import importlib.machinery
import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "menu-dashboard"
SCRIPT = REPO_ROOT / "apps" / "common" / "menu-dashboard"

sys.path.insert(0, str(REPO_ROOT))

_loader = importlib.machinery.SourceFileLoader("menu_dashboard", str(SCRIPT))
_spec = importlib.util.spec_from_loader("menu_dashboard", _loader)
menu_dashboard = importlib.util.module_from_spec(_spec)
_loader.exec_module(menu_dashboard)

TODAY = date(2026, 7, 24)


def fixture(name: str):
    return json.loads((FIXTURE_DIR / name).read_text())


def ok(name: str) -> menu_dashboard.JsonResult:
    return menu_dashboard.JsonResult(payload=fixture(name), exit_code=0)


def all_results() -> dict:
    return {
        "icb": ok("icb-overview.json"),
        "learning": ok("learning-overview.json"),
        "review": ok("menu-review-list.json"),
        "labs": ok("menu-labs-list.json"),
    }


def lanes_by_name(results: dict) -> dict:
    lanes = menu_dashboard.build_lanes(results, TODAY, menu_dashboard.LANE_NAMES)
    return {lane.name: lane for lane in lanes}


def test_every_lane_builds_from_fixtures():
    lanes = lanes_by_name(all_results())

    assert list(lanes) == menu_dashboard.LANE_NAMES
    assert all(lane.available for lane in lanes.values())


def test_tasks_lane_reads_priority_name_and_category():
    lane = lanes_by_name(all_results())["tasks"]

    assert lane.meta == "12 open"
    assert lane.rows[0].label == "p1", "a bare numeral in a gutter of words reads as a row number"
    assert lane.rows[0].text == "Renew passport"
    assert lane.rows[0].note == "chore"


def test_habits_lane_shows_every_habit_as_a_grid():
    """Every current habit is due every day, so the useful view is the whole set
    with the finished ones ticked off — not a ranked excerpt."""
    lane = lanes_by_name(all_results())["habits"]

    assert lane.meta == "1 of 4 done today"
    assert lane.rows == [], "habits are a complete set, not ranked rows"
    assert [cell.text for cell in lane.grid] == ["Exercise", "Stretch", "Journal", "Read"]
    assert [cell.done for cell in lane.grid] == [True, False, False, False]


def test_habits_grid_keeps_a_completed_habit_in_place():
    """Ordering by category and name, never by completion, so ticking one off
    never shuffles the rest out from under you."""
    before = menu_dashboard.build_habits_lane(all_results(), TODAY)

    payload = fixture("icb-overview.json")
    stretch = payload["habits"]["due_today"].pop(0)
    payload["habits"]["completed_today"].append(stretch)
    results = {"icb": menu_dashboard.JsonResult(payload=payload, exit_code=0)}
    after = menu_dashboard.build_habits_lane(results, TODAY)

    assert [cell.text for cell in after.grid] == [cell.text for cell in before.grid]
    assert [cell.done for cell in after.grid] == [True, True, False, False]


def test_reading_lane_leads_with_one_of_each_kind():
    """With the small row cap, concatenation would hide what is next behind the
    books already in progress."""
    lane = lanes_by_name(all_results())["reading"]

    assert [row.label for row in lane.rows[:3]] == ["reading", "next", "article"]
    assert lane.meta == "2 reading · 40 queued", "the backlog is context, not rows you are behind on"


def test_reading_total_spans_the_whole_pile_not_the_rows_built():
    """A trailer measured against the handful of rows round-robin produced would
    contradict the queue size in the heading."""
    lane = lanes_by_name(all_results())["reading"]

    assert lane.total == 43, "2 in progress + 40 queued + 1 article"


def test_learning_lane_names_resources_rather_than_positions():
    """A track's current unit is a position, not a thing you can open."""
    lane = lanes_by_name(all_results())["learning"]

    assert lane.meta == "A Current Section · 6 of 42 done"
    assert [(row.label, row.text) for row in lane.rows] == [
        ("open", "A Resource In Progress"),
        ("open", "A Started Resource"),
        ("start", "The Next Resource"),
        ("start", "The One After Next"),
    ], "started resources first, then the section's order; completed ones are gone"


def test_learning_lane_does_not_repeat_a_resource_listed_twice():
    lane = lanes_by_name(all_results())["learning"]

    titles = [row.text for row in lane.rows]
    assert titles.count("A Resource In Progress") == 1, "the section lists it too"


def test_learning_tracks_become_context_not_rows():
    lane = lanes_by_name(all_results())["learning"]

    # A track with no current unit contributes nothing.
    assert lane.context.text == "First Track 2/61"
    assert "First Track" not in [row.text for row in lane.rows]


def test_maintenance_lane_counts_only_what_is_due():
    lane = lanes_by_name(all_results())["maintenance"]

    # 3 review items due (never-done, overdue, due-today) and 1 lab; the
    # not-yet-due and on-demand entries are excluded.
    assert lane.meta == "3 reviews · 1 lab due"


def test_maintenance_lane_says_what_an_entry_is_for():
    """The register slug identifies a row to the tooling; what it is for only
    exists in the description."""
    lane = lanes_by_name(all_results())["maintenance"]

    assert "never-done-item" not in {row.text for row in lane.rows}
    assert "Has never been marked done" in {row.text for row in lane.rows}
    assert "An Overdue Lab" in {row.text for row in lane.rows}, "labs carry a title instead"


def test_maintenance_lane_ranks_by_how_late_a_row_actually_is():
    """Sorting the note text would rank "16d overdue" below "9d overdue" and put
    never-run entries above everything genuinely due."""
    lane = lanes_by_name(all_results())["maintenance"]

    assert [row.urgency for row in lane.rows] == [
        menu_dashboard.Urgency.OVERDUE,
        menu_dashboard.Urgency.OVERDUE,
        menu_dashboard.Urgency.DUE,
        menu_dashboard.Urgency.NONE,
    ]
    overdue = [row.note for row in lane.rows if row.urgency is menu_dashboard.Urgency.OVERDUE]
    assert overdue == ["16d overdue", "9d overdue"], "most overdue first, numerically"
    assert lane.rows[-1].note == "never run", "never run is the least urgent state, not the most"


def test_upcoming_lane_uses_one_distance_format_and_names_the_day():
    lane = lanes_by_name(all_results())["upcoming"]

    assert lane.rows[0].label == "in 12d"
    assert lane.rows[0].note == "05 Aug 2026", "the gutter says how far, the note says which day"
    assert lane.meta == "2 countdowns · 1 event"
    assert lane.total == 3, "the total spans both countdowns and events"


def test_projects_lane_separates_next_from_blocked():
    lane = lanes_by_name(all_results())["projects"]

    assert lane.meta == "5 next · 1 blocked"
    assert [row.label for row in lane.rows] == ["next", "next", "blocked"]


def test_projects_lane_carries_the_item_note_so_a_bare_title_says_something():
    lane = lanes_by_name(all_results())["projects"]

    assert lane.rows[0].text == "An actionable item — what it actually means"
    assert lane.rows[1].text == "A second item", "no note means no dangling separator"


def test_more_counts_come_from_the_backend_total_not_the_row_count():
    lane = lanes_by_name(all_results())["tasks"]

    assert len(lane.rows) == 4, "the payload carries fewer rows than the true total"
    assert lane.total == 12
    more = lane.total - min(len(lane.rows), menu_dashboard.ROW_CAP)
    assert more == 9


def test_lane_is_unavailable_when_its_backend_is_missing():
    results = all_results()
    results["icb"] = menu_dashboard.JsonResult(failure=menu_dashboard.BackendFailure.NOT_INSTALLED)

    lanes = lanes_by_name(results)

    assert lanes["tasks"].available is False
    assert "not installed" in lanes["tasks"].reason
    assert lanes["maintenance"].available is True, "one dead backend must not cost the other lanes"


def test_maintenance_renders_what_it_has_when_one_backend_is_missing():
    results = all_results()
    results["labs"] = menu_dashboard.JsonResult(failure=menu_dashboard.BackendFailure.NOT_INSTALLED)

    lane = menu_dashboard.build_maintenance_lane(results, TODAY)

    assert lane.available is True
    assert [row.label for row in lane.rows] == ["review", "review", "review"]
    assert "menu-labs is not installed" in lane.reason


def test_section_warning_degrades_only_its_own_lane():
    payload = fixture("icb-overview.json")
    payload["warnings"] = [{"section": "reading", "message": "books: API request failed (500)"}]
    results = all_results()
    results["icb"] = menu_dashboard.JsonResult(payload=payload, exit_code=0)

    lanes = lanes_by_name(results)

    assert lanes["reading"].reason == "books: API request failed (500)"
    assert lanes["tasks"].reason == ""


def test_newer_schema_version_is_reported_rather_than_half_read():
    payload = fixture("icb-overview.json")
    payload["schema_version"] = menu_dashboard.ICB_SCHEMA_VERSION + 1
    results = {"icb": menu_dashboard.JsonResult(payload=payload, exit_code=0)}

    lane = menu_dashboard.build_tasks_lane(results, TODAY)

    assert lane.available is False
    assert "newer than this dashboard" in lane.reason


def test_backend_reason_exit_two_means_version_skew():
    """Exit 2 is reserved for usage errors across these CLIs, so a rejected
    `overview` is an old binary rather than a runtime failure."""
    result = menu_dashboard.JsonResult(
        exit_code=2,
        stderr='error: unknown command "overview" for "icb"',
        failure=menu_dashboard.BackendFailure.FAILED,
    )

    assert menu_dashboard.backend_reason("icb", result) == "installed icb predates `overview` — reinstall it"


def test_backend_reason_uses_the_first_stderr_line():
    result = menu_dashboard.JsonResult(
        exit_code=1,
        stderr="error: not logged in — run `icb auth login`\nUsage:\n  icb overview [flags]",
        failure=menu_dashboard.BackendFailure.FAILED,
    )

    assert menu_dashboard.backend_reason("icb", result) == "error: not logged in — run `icb auth login`"


def test_backend_reason_reports_the_timeout_actually_used():
    result = menu_dashboard.JsonResult(failure=menu_dashboard.BackendFailure.TIMED_OUT, timeout=0.25)

    assert menu_dashboard.backend_reason("icb", result) == "icb timed out after 0.25s"


def test_backends_for_selects_only_what_the_lanes_need():
    assert menu_dashboard.backends_for(["tasks"]) == ["icb"]
    assert menu_dashboard.backends_for(["maintenance"]) == ["review", "labs"]
    assert sorted(menu_dashboard.backends_for(["tasks", "learning"])) == ["icb", "learning"]


def test_lanes_as_json_shape():
    lanes = menu_dashboard.build_lanes(all_results(), TODAY, menu_dashboard.LANE_NAMES)

    payload = json.loads(menu_dashboard.lanes_as_json(lanes, TODAY, menu_dashboard.ROW_CAP))

    assert [lane["name"] for lane in payload["lanes"]] == menu_dashboard.LANE_NAMES
    tasks = payload["lanes"][0]
    assert set(tasks) == {
        "name",
        "title",
        "meta",
        "status",
        "reason",
        "rows",
        "grid",
        "context",
        "total",
        "more",
        "hints",
    }
    assert tasks["status"] == "ok"
    assert set(tasks["rows"][0]) == {"label", "text", "note", "urgency"}


def test_lanes_as_json_carries_the_habits_grid():
    lanes = menu_dashboard.build_lanes(all_results(), TODAY, ["habits"])

    payload = json.loads(menu_dashboard.lanes_as_json(lanes, TODAY, menu_dashboard.ROW_CAP))
    habits = payload["lanes"][0]

    assert habits["rows"] == []
    assert habits["grid"][0] == {"text": "Exercise", "done": True}
    assert habits["more"] == 0, "a complete set has no remainder"


def test_lanes_as_json_keeps_unavailable_lanes():
    results = all_results()
    results["learning"] = menu_dashboard.JsonResult(failure=menu_dashboard.BackendFailure.NOT_INSTALLED)
    lanes = menu_dashboard.build_lanes(results, TODAY, menu_dashboard.LANE_NAMES)

    payload = json.loads(menu_dashboard.lanes_as_json(lanes, TODAY, menu_dashboard.ROW_CAP))
    learning = next(lane for lane in payload["lanes"] if lane["name"] == "learning")

    assert learning["status"] == "unavailable"
    assert "not installed" in learning["reason"]


def test_run_json_reports_a_missing_command():
    result = menu_dashboard.run_json(["definitely-not-a-real-binary-xyz"], timeout=5)

    assert result.failure is menu_dashboard.BackendFailure.NOT_INSTALLED


def test_run_json_reports_a_timeout():
    result = menu_dashboard.run_json(["/bin/sh", "-c", "sleep 2"], timeout=0.2)

    assert result.failure is menu_dashboard.BackendFailure.TIMED_OUT
    assert result.timeout == 0.2


def test_run_json_reports_unreadable_output():
    result = menu_dashboard.run_json(["/bin/sh", "-c", "echo not json"], timeout=5)

    assert result.failure is menu_dashboard.BackendFailure.UNREADABLE


def test_run_json_reports_a_nonzero_exit():
    result = menu_dashboard.run_json(["/bin/sh", "-c", "echo boom >&2; exit 3"], timeout=5)

    assert result.failure is menu_dashboard.BackendFailure.FAILED
    assert result.exit_code == 3
    assert result.stderr == "boom"


def test_run_json_parses_a_payload():
    result = menu_dashboard.run_json(["/bin/sh", "-c", 'echo \'{"a": 1}\''], timeout=5)

    assert result.failure is None
    assert result.payload == {"a": 1}


def test_round_robin_interleaves_groups():
    rows = menu_dashboard.round_robin(
        [menu_dashboard.Row("a", "a1"), menu_dashboard.Row("a", "a2")],
        [menu_dashboard.Row("b", "b1")],
    )

    assert [row.text for row in rows] == ["a1", "b1", "a2"]


def test_round_robin_handles_empty_groups():
    assert menu_dashboard.round_robin([], []) == []


def test_relative_day_changes_unit_never_format():
    """Every row in the lane answers the same question, so a far-off date reads
    as a distance too rather than switching to a calendar stamp."""
    assert menu_dashboard.relative_day("2026-07-24", TODAY) == "today"
    assert menu_dashboard.relative_day("2026-08-05", TODAY) == "in 12d"
    assert menu_dashboard.relative_day("2026-10-22", TODAY) == "in 90d"
    assert menu_dashboard.relative_day("2026-10-23", TODAY) == "in 3mo"
    assert menu_dashboard.relative_day("2028-03-01", TODAY) == "in 20mo"
    assert menu_dashboard.relative_day("2026-07-20", TODAY) == "4d ago"
    assert menu_dashboard.relative_day("not-a-date", TODAY) == "not-a-date"


def test_calendar_day():
    assert menu_dashboard.calendar_day("2026-08-05") == "05 Aug 2026"
    assert menu_dashboard.calendar_day("not-a-date") == "not-a-date"


def test_day_urgency():
    assert menu_dashboard.day_urgency("2026-07-20", TODAY) is menu_dashboard.Urgency.OVERDUE
    assert menu_dashboard.day_urgency("2026-07-24", TODAY) is menu_dashboard.Urgency.DUE
    assert menu_dashboard.day_urgency("2026-08-05", TODAY) is menu_dashboard.Urgency.NONE
    assert menu_dashboard.day_urgency("not-a-date", TODAY) is menu_dashboard.Urgency.NONE


def test_plural():
    assert menu_dashboard.plural(0, "lab") == "0 labs"
    assert menu_dashboard.plural(1, "lab") == "1 lab"
    assert menu_dashboard.plural(2, "lab") == "2 labs"


def test_event_date_falls_back_on_an_unparseable_timestamp():
    assert menu_dashboard.event_date("2026-08-14T16:00:00") == "2026-08-14"
    assert menu_dashboard.event_date("garbage-value") == "garbage-va"


def test_is_due_row():
    assert menu_dashboard.is_due_row({"overdue": None}) is True
    assert menu_dashboard.is_due_row({"overdue": 0}) is True
    assert menu_dashboard.is_due_row({"overdue": -1}) is False


def test_maintenance_row_pairs_a_note_with_the_rank_it_sorts_on():
    assert menu_dashboard.maintenance_row("review", "x", {"overdue": None})[0] == (2, 0)
    assert menu_dashboard.maintenance_row("review", "x", {"overdue": 0})[0] == (1, 0)
    assert menu_dashboard.maintenance_row("review", "x", {"overdue": 5})[0] == (0, -5)
    assert menu_dashboard.maintenance_row("review", "x", {"overdue": 5})[1].note == "5d overdue"


def test_describe_joins_a_title_to_its_note():
    assert menu_dashboard.describe("A Title", "some detail") == "A Title — some detail"
    assert menu_dashboard.describe("A Title", "") == "A Title"
    assert menu_dashboard.describe("A Title", None) == "A Title"
    assert menu_dashboard.describe("A Title", "two\nlines") == "A Title — two lines"


def test_clip():
    assert menu_dashboard.clip("short", 10) == "short"
    assert menu_dashboard.clip("a much longer string", 10) == "a much lo…"
