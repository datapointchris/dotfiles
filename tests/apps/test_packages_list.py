"""The `python -m dotfiles.declaration` door, and nothing else.

Every assertion about what the read commands *answer* — the payload of a listing,
the per-section counts, the total — lives in `tests/cli/test_packages_browse.py`,
which drives the same code in process and asserts it strictly. What is left here
is the door: the module runs as a script, and a fresh process locates the
declaration from `DOTFILES_DIR` alone. In process that resolution cannot be
measured, because `paths` derives the packages file from the variable once at
import and the in-process tests re-run that derivation themselves.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

PACKAGES = [sys.executable, '-m', 'dotfiles.declaration']

# A real section name, because `iter_section_entries` branches on the structure
# the catalog declares for it and an invented name yields nothing.
DECLARED: dict[str, Any] = {
    'github_releases': [{'name': 'fzf', 'repo': 'junegunn/fzf', 'description': 'fuzzy finder'}],
}


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    install_dir = tmp_path / 'install'
    install_dir.mkdir(parents=True)
    (install_dir / 'packages.yml').write_text(yaml.safe_dump(DECLARED, sort_keys=False))
    return tmp_path


def run_packages(root: Path, *args: str) -> subprocess.CompletedProcess:
    """Point the catalog at a synthetic tree.

    Through `DOTFILES_DIR` rather than a `--root` flag, which only `verify` and
    `missing` accept. It is the same variable every script and the CLI itself
    uses to locate the repo, so the read commands are exercised through the
    resolution path they really use.
    """
    return subprocess.run(
        [*PACKAGES, *args],
        capture_output=True,
        text=True,
        env={**os.environ, 'TERM': 'dumb', 'DOTFILES_DIR': str(root)},
        check=False,
    )


def test_the_module_run_as_a_script_reads_the_declaration_dotfiles_dir_names(tree: Path) -> None:
    """What the read commands answer is asserted in
    `tests/cli/test_packages_browse.py`, in process and strictly. This is the
    subprocess door alone: `python -m dotfiles.declaration` reaches `cli()`.

    The one name is what makes the run say which file it read. A door that
    ignored `DOTFILES_DIR` would resolve this checkout's own packages.yml and
    exit zero over a listing of everything, so neither the exit code nor a
    non-empty payload can tell the two apart.
    """
    result = run_packages(tree, 'list', '--json')

    assert result.returncode == 0, result.stderr
    assert [entry['name'] for entry in json.loads(result.stdout)] == ['fzf'], result.stdout
