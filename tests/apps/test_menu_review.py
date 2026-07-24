"""Tests for menu-review — register loading, derived schedule status, and --json.

menu-review is a uv single-file script, so it is loaded by path with importlib.
MENU_REVIEW_REGISTER points at a committed fixture register and
MENU_REVIEW_STATE at a nonexistent file — both must be set before the module is
imported, since it binds those paths at import time. Tests that need recorded
done-dates write a state file under tmp_path and repoint STATE, because overdue
days are derived from today and a committed state file would rot.
"""

import importlib.machinery
import importlib.util
import json
import os
import sys
from datetime import date
from datetime import timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "menu-review"
SCRIPT = REPO_ROOT / "apps" / "common" / "menu-review"

os.environ["MENU_REVIEW_REGISTER"] = str(FIXTURE_DIR / "register.yml")
os.environ["MENU_REVIEW_STATE"] = str(FIXTURE_DIR / "does-not-exist-state.json")
sys.path.insert(0, str(REPO_ROOT))

_loader = importlib.machinery.SourceFileLoader("menu_review", str(SCRIPT))
_spec = importlib.util.spec_from_loader("menu_review", _loader)
menu_review = importlib.util.module_from_spec(_spec)
_loader.exec_module(menu_review)


def write_state(tmp_path, monkeypatch, done_dates: dict) -> None:
    """Point the module at a state file recording the given last-done dates."""
    state_file = tmp_path / "review-state.json"
    state_file.write_text(json.dumps(done_dates))
    monkeypatch.setattr(menu_review, "STATE", state_file)


def test_load_items_reads_the_register():
    items = menu_review.load_items()
    assert set(items) == {"never-done", "overdue-item", "fresh-item"}
    assert items["overdue-item"]["cadence"] == "1w"
    assert items["fresh-item"]["show"] == "echo fresh"


def test_load_items_none_without_a_register(monkeypatch):
    """None distinguishes "no register at all" from "a register with no items"."""
    monkeypatch.setattr(menu_review, "REGISTER", FIXTURE_DIR / "nope.yml")
    assert menu_review.load_items() is None


def test_statuses_never_done_reads_as_most_urgent():
    rows = {row["id"]: row for row in menu_review.statuses()}
    assert rows["never-done"]["overdue"] is None
    assert menu_review.statuses()[0]["overdue"] is None


def test_statuses_orders_most_overdue_first(tmp_path, monkeypatch):
    today = date.today()
    write_state(
        tmp_path,
        monkeypatch,
        {
            "overdue-item": (today - timedelta(days=30)).isoformat(),
            "fresh-item": today.isoformat(),
        },
    )

    rows = menu_review.statuses()

    assert [row["id"] for row in rows] == ["never-done", "overdue-item", "fresh-item"]
    assert rows[1]["overdue"] == 23  # 30 days since done, 7-day cadence
    assert rows[2]["overdue"] == -28  # done today, 28-day cadence
    assert menu_review.is_due(rows[1]["overdue"]) is True
    assert menu_review.is_due(rows[2]["overdue"]) is False


def test_list_json_emits_every_item_with_its_status(capsys):
    assert menu_review.cmd_list(as_json=True) == 0

    rows = json.loads(capsys.readouterr().out)

    assert len(rows) == 3, "--json emits the whole register, not just what is due"
    assert set(rows[0]) == {"id", "cadence", "desc", "command", "show", "last", "overdue"}


def test_list_json_is_parseable_without_a_register(monkeypatch, capsys):
    """--json must always emit JSON; the prose hint would break a consumer."""
    monkeypatch.setattr(menu_review, "REGISTER", FIXTURE_DIR / "nope.yml")

    assert menu_review.cmd_list(as_json=True) == 0
    assert json.loads(capsys.readouterr().out) == []


def test_parse_duration_minutes():
    assert menu_review.parse_duration_minutes("4h") == 240
    assert menu_review.parse_duration_minutes("90m") == 90
    assert menu_review.parse_duration_minutes("4") == 240, "a bare number means hours"
    assert menu_review.parse_duration_minutes(" 30m ") == 30
    assert menu_review.parse_duration_minutes("soon") is None
    assert menu_review.parse_duration_minutes("") is None
