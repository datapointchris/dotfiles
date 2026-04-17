"""Synthetic-fixture tests for `apps/common/packages verify`.

Every test builds a temp tree with only the files needed to drive the specific
check under test, then invokes `packages verify --root <tmp_path>` via subprocess.
The real `install/packages.yml` and manifests are never read.

One test per check. Plus happy path, exit-code behavior, and --root-flag isolation.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGES_SCRIPT = REPO_ROOT / "apps" / "common" / "packages"


# ─────────────────────────────────────────────────────────────────────────────
# Fixture builders
# ─────────────────────────────────────────────────────────────────────────────


def build_tree(
    root: Path,
    *,
    packages: dict[str, Any] | None = None,
    manifests: dict[str, dict[str, Any]] | None = None,
    github_release_scripts: list[str] | None = None,
    custom_installer_scripts: list[str] | None = None,
) -> None:
    """Create a synthetic dotfiles tree under `root`.

    Only the pieces passed in are created — missing arguments mean "no such
    files/entries exist" in the synthetic world. Empty iterables still create
    the directory but no files.
    """
    install_dir = root / "install"
    install_dir.mkdir(parents=True, exist_ok=True)

    (install_dir / "packages.yml").write_text(yaml.safe_dump(packages or {}, sort_keys=False))

    if manifests is not None:
        manifests_dir = install_dir / "manifests"
        manifests_dir.mkdir(parents=True, exist_ok=True)
        for name, content in manifests.items():
            (manifests_dir / f"{name}.yml").write_text(yaml.safe_dump(content, sort_keys=False))

    if github_release_scripts is not None:
        gh_dir = install_dir / "common" / "github-releases"
        gh_dir.mkdir(parents=True, exist_ok=True)
        for stem in github_release_scripts:
            (gh_dir / f"{stem}.sh").write_text("#!/usr/bin/env bash\n")

    if custom_installer_scripts is not None:
        ci_dir = install_dir / "common" / "custom-installers"
        ci_dir.mkdir(parents=True, exist_ok=True)
        for stem in custom_installer_scripts:
            (ci_dir / f"{stem}.sh").write_text("#!/usr/bin/env bash\n")


def run_verify(root: Path) -> subprocess.CompletedProcess:
    """Invoke the real packages verify command against a synthetic tree.

    The real environment (PATH, HOME) is inherited so the `uv run --script`
    shebang on the packages script can find uv. Isolation from the real repo
    is provided by --root, not by scrubbing the environment.
    """
    env = {**os.environ, "TERM": "dumb"}
    return subprocess.run(
        [str(PACKAGES_SCRIPT), "verify", "--root", str(root)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def assert_clean(result: subprocess.CompletedProcess) -> None:
    """Assert 0 errors, 0 warnings, exit 0."""
    assert result.returncode == 0, f"expected exit 0, got {result.returncode}\nSTDERR:\n{result.stderr}"
    assert "0 errors, 0 warnings" in result.stdout


def assert_error(result: subprocess.CompletedProcess, fragment: str) -> None:
    """Assert exit 1 and the given fragment appears in the error output."""
    assert result.returncode == 1, f"expected exit 1, got {result.returncode}\nSTDERR:\n{result.stderr}"
    assert fragment in result.stderr, f"expected {fragment!r} in stderr, got:\n{result.stderr}"


def assert_warning(result: subprocess.CompletedProcess, fragment: str) -> None:
    """Assert exit 0 but the given warning fragment appears in the error output."""
    assert result.returncode == 0, f"expected exit 0, got {result.returncode}\nSTDERR:\n{result.stderr}"
    assert fragment in result.stderr, f"expected {fragment!r} in stderr, got:\n{result.stderr}"


# ─────────────────────────────────────────────────────────────────────────────
# Happy path
# ─────────────────────────────────────────────────────────────────────────────


def test_clean_tree_verifies_with_zero_issues(tmp_path: Path) -> None:
    """A minimal, internally-consistent tree passes verify with 0 errors, 0 warnings."""
    build_tree(
        tmp_path,
        packages={
            "go_tools": [{"name": "task", "package": "github.com/go-task/task/v3/cmd/task"}],
            "github_releases": [{"name": "fzf", "repo": "junegunn/fzf"}],
            "custom_installers": [
                {"name": "theme", "source_type": "github_clone", "description": "Theme installer"}
            ],
        },
        manifests={
            "test-machine": {
                "machine": "test-machine",
                "platform": "linux",
                "go_tools": ["task"],
                "github_releases": ["fzf"],
                "custom_installers": ["theme"],
            }
        },
        github_release_scripts=["fzf"],
        custom_installer_scripts=["theme"],
    )
    assert_clean(run_verify(tmp_path))


# ─────────────────────────────────────────────────────────────────────────────
# Tier 1 — section shape: required fields + duplicates
# ─────────────────────────────────────────────────────────────────────────────


def test_missing_required_field_flags_error(tmp_path: Path) -> None:
    """github_releases entry missing its required `repo` field."""
    build_tree(
        tmp_path,
        packages={"github_releases": [{"name": "fzf"}]},  # no `repo`
        manifests={},
        github_release_scripts=["fzf"],
    )
    assert_error(run_verify(tmp_path), "missing required field 'repo'")


def test_required_any_of_flags_error_when_none_present(tmp_path: Path) -> None:
    """system_packages requires at least one of apt/pacman/brew/aur."""
    build_tree(
        tmp_path,
        packages={"system_packages": [{"name": "git"}]},  # no package-manager key
        manifests={},
    )
    assert_error(run_verify(tmp_path), "must have at least one of")


def test_duplicate_name_within_section_flags_error(tmp_path: Path) -> None:
    """Two github_releases entries sharing the same name."""
    build_tree(
        tmp_path,
        packages={
            "github_releases": [
                {"name": "fzf", "repo": "junegunn/fzf"},
                {"name": "fzf", "repo": "other/fzf"},
            ]
        },
        manifests={},
        github_release_scripts=["fzf"],
    )
    assert_error(run_verify(tmp_path), "duplicate name: 'fzf'")


def test_dict_of_lists_flattens_for_shape_check(tmp_path: Path) -> None:
    """npm_globals is a dict of categories — shape check must traverse into each list."""
    build_tree(
        tmp_path,
        packages={
            "npm_globals": {
                "language_servers": [{"description": "missing name"}],  # no `name`
            }
        },
        manifests={},
    )
    assert_error(run_verify(tmp_path), "missing required field 'name'")


# ─────────────────────────────────────────────────────────────────────────────
# Tier 1 — manifest name resolution
# ─────────────────────────────────────────────────────────────────────────────


def test_manifest_names_unknown_go_tool_flags_error(tmp_path: Path) -> None:
    """A manifest lists a go tool with no corresponding packages.yml entry."""
    build_tree(
        tmp_path,
        packages={"go_tools": [{"name": "task", "package": "github.com/go-task/task/v3/cmd/task"}]},
        manifests={
            "test-machine": {"go_tools": ["task", "ghost-tool"]},  # ghost-tool unknown
        },
    )
    assert_error(run_verify(tmp_path), "names 'ghost-tool'")


def test_manifest_names_unknown_custom_installer_flags_error(tmp_path: Path) -> None:
    """Manifest's custom_installers list references a name with no packages.yml entry."""
    build_tree(
        tmp_path,
        packages={
            "custom_installers": [
                {"name": "theme", "source_type": "github_clone", "description": "Theme installer"}
            ]
        },
        manifests={"test-machine": {"custom_installers": ["theme", "unknown-installer"]}},
        custom_installer_scripts=["theme"],
    )
    assert_error(run_verify(tmp_path), "names 'unknown-installer'")


def test_manifest_names_unknown_npm_global_flags_error(tmp_path: Path) -> None:
    """npm_globals is a name-subscribed section — manifest list entries must resolve."""
    build_tree(
        tmp_path,
        packages={"npm_globals": {"linters": [{"name": "prettier"}]}},
        manifests={"test-machine": {"npm_globals": ["prettier", "nonexistent-lsp"]}},
    )
    assert_error(run_verify(tmp_path), "names 'nonexistent-lsp'")


# ─────────────────────────────────────────────────────────────────────────────
# Tier 1 — script parity (bidirectional)
# ─────────────────────────────────────────────────────────────────────────────


def test_github_release_script_without_entry_flags_error(tmp_path: Path) -> None:
    """tree-sitter.sh exists on disk but has no packages.yml github_releases entry."""
    build_tree(
        tmp_path,
        packages={},
        manifests={},
        github_release_scripts=["tree-sitter"],  # script exists
    )
    assert_error(
        run_verify(tmp_path),
        "install/common/github-releases/tree-sitter.sh exists but no packages.yml github_releases entry",
    )


def test_github_release_entry_without_script_flags_error(tmp_path: Path) -> None:
    """packages.yml has a github_releases entry but no matching .sh script on disk."""
    build_tree(
        tmp_path,
        packages={"github_releases": [{"name": "fzf", "repo": "junegunn/fzf"}]},
        manifests={},
        github_release_scripts=[],  # empty directory
    )
    assert_error(
        run_verify(tmp_path),
        "packages.yml github_releases entry 'fzf' has no install/common/github-releases/fzf.sh script",
    )


def test_custom_installer_script_without_entry_flags_error(tmp_path: Path) -> None:
    """Custom installer script on disk with no packages.yml custom_installers entry."""
    build_tree(
        tmp_path,
        packages={},
        manifests={},
        custom_installer_scripts=["bats"],
    )
    assert_error(
        run_verify(tmp_path),
        "install/common/custom-installers/bats.sh exists but no packages.yml custom_installers entry",
    )


def test_custom_installer_entry_without_script_flags_error(tmp_path: Path) -> None:
    """packages.yml custom_installers entry with no matching script file."""
    build_tree(
        tmp_path,
        packages={
            "custom_installers": [
                {"name": "theme", "source_type": "github_clone", "description": "Theme installer"}
            ]
        },
        manifests={},
        custom_installer_scripts=[],
    )
    assert_error(
        run_verify(tmp_path),
        "custom_installers entry 'theme' has no install/common/custom-installers/theme.sh script",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Tier 1 — deprecated manifest keys (Phase 1.6 runtime-gate booleans)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("deprecated_key", ["go", "rust", "nvm", "uv", "tenv"])
def test_deprecated_manifest_key_flags_error(tmp_path: Path, deprecated_key: str) -> None:
    """Every removed runtime-gate boolean must be caught, actionable message required."""
    build_tree(
        tmp_path,
        packages={},
        manifests={"test-machine": {deprecated_key: True}},
    )
    result = run_verify(tmp_path)
    assert_error(result, f"uses removed key '{deprecated_key}:'")
    assert "derived from the corresponding name-list" in result.stderr


# ─────────────────────────────────────────────────────────────────────────────
# Tier 2 — unreferenced packages.yml entries (warning, not error)
# ─────────────────────────────────────────────────────────────────────────────


def test_unreferenced_entry_is_warning_not_error(tmp_path: Path) -> None:
    """A go_tools entry that no manifest names should warn but not fail the commit."""
    build_tree(
        tmp_path,
        packages={
            "go_tools": [
                {"name": "task", "package": "github.com/go-task/task/v3/cmd/task"},
                {"name": "orphan", "package": "github.com/example/orphan"},
            ]
        },
        manifests={"test-machine": {"go_tools": ["task"]}},
    )
    result = run_verify(tmp_path)
    assert_warning(result, "'orphan' defined in packages.yml but not referenced by any manifest")
    assert "0 errors" in result.stdout
    assert "1 warnings" in result.stdout


def test_custom_installer_unreferenced_is_warning(tmp_path: Path) -> None:
    """Unreferenced custom_installers entry produces a warning like other name-subscribed sections."""
    build_tree(
        tmp_path,
        packages={
            "custom_installers": [
                {"name": "theme", "source_type": "github_clone", "description": "used"},
                {"name": "orphan", "source_type": "github_clone", "description": "unused"},
            ]
        },
        manifests={"test-machine": {"custom_installers": ["theme"]}},
        custom_installer_scripts=["theme", "orphan"],
    )
    result = run_verify(tmp_path)
    assert_warning(result, "'orphan' defined in packages.yml but not referenced by any manifest")


# ─────────────────────────────────────────────────────────────────────────────
# Exit-code contract
# ─────────────────────────────────────────────────────────────────────────────


def test_any_error_exits_1_even_with_warnings(tmp_path: Path) -> None:
    """When both errors and warnings are present, exit is 1 (errors dominate)."""
    build_tree(
        tmp_path,
        packages={
            "go_tools": [
                {"name": "task", "package": "github.com/go-task/task/v3/cmd/task"},
                {"name": "orphan", "package": "github.com/example/orphan"},
            ],
        },
        manifests={
            "test-machine": {
                "go": True,  # deprecated key → error
                "go_tools": ["task"],
            }
        },
    )
    result = run_verify(tmp_path)
    assert result.returncode == 1


def test_warnings_only_exits_0(tmp_path: Path) -> None:
    """Warnings alone never block the commit."""
    build_tree(
        tmp_path,
        packages={"go_tools": [{"name": "orphan", "package": "github.com/example/orphan"}]},
        manifests={"test-machine": {"go_tools": []}},
    )
    assert run_verify(tmp_path).returncode == 0


# ─────────────────────────────────────────────────────────────────────────────
# --root flag isolation
# ─────────────────────────────────────────────────────────────────────────────


def test_root_flag_reads_only_synthetic_tree(tmp_path: Path) -> None:
    """--root must drive the entire resolution — real repo packages.yml must not leak in."""
    # Synthetic tree is intentionally broken in a way the real repo isn't:
    # a github_releases entry with no matching script.
    build_tree(
        tmp_path,
        packages={"github_releases": [{"name": "ghost", "repo": "example/ghost"}]},
        manifests={},
        github_release_scripts=[],
    )
    # If --root leaked and fell back to the real repo, we'd get "0 errors" (the real
    # repo is clean). Asserting the ghost error proves the synthetic tree drove verify.
    assert_error(run_verify(tmp_path), "'ghost' has no install/common/github-releases/ghost.sh script")
