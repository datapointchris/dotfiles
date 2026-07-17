"""Tests for menu-labs — Lab loading, frontmatter parsing, and schedule status.

menu-labs is a uv single-file script, so it is loaded by path with importlib.
MENU_LABS_DIR points at a committed fixture deck and MENU_LABS_STATE at a
nonexistent file (so every Lab reads as never-practiced) — both must be set
before the module is imported, since it binds those paths at import time.
"""

import importlib.machinery
import importlib.util
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "menu-labs"
SCRIPT = REPO_ROOT / "apps" / "common" / "menu-labs"

os.environ["MENU_LABS_DIR"] = str(FIXTURE_DIR)
os.environ["MENU_LABS_STATE"] = str(FIXTURE_DIR / "does-not-exist-state.json")
sys.path.insert(0, str(REPO_ROOT))

_loader = importlib.machinery.SourceFileLoader("menu_labs", str(SCRIPT))
_spec = importlib.util.spec_from_loader("menu_labs", _loader)
menu_labs = importlib.util.module_from_spec(_spec)
_loader.exec_module(menu_labs)


def test_load_labs_reads_frontmatter():
    labs = menu_labs.load_labs()
    assert set(labs) == {"scheduled-lab", "ondemand-lab"}
    # Title comes from the body's first H1, not a frontmatter field.
    assert labs["scheduled-lab"]["title"] == "A Scheduled Lab"
    assert labs["scheduled-lab"]["tags"] == ["fd", "demo"]
    assert labs["scheduled-lab"]["cadence"] == "2w"
    # No cadence in the frontmatter → empty string (practice-on-demand).
    assert labs["ondemand-lab"]["cadence"] == ""


def test_statuses_scheduled_sorts_before_ondemand():
    rows = menu_labs.statuses()
    assert rows[0]["id"] == "scheduled-lab"
    assert rows[-1]["id"] == "ondemand-lab"
    assert rows[-1]["scheduled"] is False


def test_is_due_row():
    rows = {r["id"]: r for r in menu_labs.statuses()}
    # Scheduled + never practiced → due; on-demand → never due.
    assert menu_labs.is_due_row(rows["scheduled-lab"]) is True
    assert menu_labs.is_due_row(rows["ondemand-lab"]) is False


def test_strip_frontmatter_removes_block():
    text = "---\ntitle: X\ntags: [a]\n---\n\n# Heading\nbody\n"
    assert menu_labs.strip_frontmatter(text).startswith("# Heading")
    assert "title: X" not in menu_labs.strip_frontmatter(text)


def test_strip_frontmatter_passthrough_without_block():
    text = "# Heading\nbody\n"
    assert menu_labs.strip_frontmatter(text) == text


def test_parse_frontmatter(tmp_path):
    f = tmp_path / "x.md"
    f.write_text("---\ntags: [a, b]\ncadence: 1w\n---\n# H\n")
    meta = menu_labs.parse_frontmatter(f)
    assert meta["tags"] == ["a", "b"]
    assert meta["cadence"] == "1w"


def test_parse_frontmatter_none_when_absent(tmp_path):
    f = tmp_path / "x.md"
    f.write_text("# H\nno frontmatter\n")
    assert menu_labs.parse_frontmatter(f) == {}


def test_first_heading_is_the_title():
    assert menu_labs.first_heading("# The Title\n\ntext\n## Sub\n") == "The Title"


def test_first_heading_empty_when_none():
    assert menu_labs.first_heading("no heading here\n") == ""


def test_slugify():
    assert menu_labs.slugify("Find Files Fast!") == "find-files-fast"
    assert menu_labs.slugify("  rg/search  ") == "rgsearch"
