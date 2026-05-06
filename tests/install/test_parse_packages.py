"""
Tests for parse_packages.py

Run with: pytest tests/install/test_parse_packages.py
Or from project root: python -m pytest tests/install/
"""

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "install"))
import parse_packages

PACKAGES_YML = Path(__file__).parent.parent.parent / "install" / "packages.yml"


@pytest.fixture
def real_packages_data():
    """Load actual packages.yml for tests that validate live configuration."""
    with open(PACKAGES_YML) as f:
        return yaml.safe_load(f)


@pytest.fixture
def sample_packages_data():
    """Sample packages.yml data for testing."""
    return {
        "runtimes": {
            "node": {"version": "22"},
            "python": {"version": "3.12"}
        },
        "system_packages": [
            {"apt": "curl", "brew": "curl", "pacman": "curl"},
            {"apt": "git", "brew": "git", "pacman": "git"},
            {"apt": "build-essential", "pacman": "base-devel"}
        ],
        "cargo_packages": [
            {"name": "ripgrep"},
            {"name": "fd-find"}
        ],
        "npm_globals": {
            "formatters": [
                {"name": "prettier"},
                {"name": "markdownlint-cli"}
            ],
            "language_servers": [
                {"name": "typescript-language-server"}
            ]
        },
        "uv_tools": {
            "formatters": [
                {"name": "black"},
                {"name": "isort"}
            ]
        },
        "go_tools": [
            {"package": "github.com/jesseduffield/lazydocker@latest"},
            {"package": "github.com/rhysd/actionlint/cmd/actionlint@latest"}
        ],
        "mas_apps": [
            {"id": 937984704, "name": "Amphetamine"},
            {"id": 1352778147, "name": "Bitwarden"}
        ],
        "github_releases": [
            {"name": "neovim", "repo": "neovim/neovim", "min_version": "0.9.0"},
            {"name": "lazygit", "repo": "jesseduffield/lazygit"}
        ],
        "shell_plugins": [
            {"name": "zsh-autosuggestions", "repo": "zsh-users/zsh-autosuggestions"},
            {"name": "fast-syntax-highlighting", "repo": "zdharma-continuum/fast-syntax-highlighting"}
        ],
        "macos_taps": [
            "homebrew/cask-fonts"
        ],
        "flatpak_apps": [
            {"flatpak_id": "com.slack.Slack"},
            {"flatpak_id": "us.zoom.Zoom"}
        ],
        "macos_casks": [
            {"name": "alfred"},
            {"name": "bettertouchtool"}
        ]
    }


def test_get_value_simple(sample_packages_data):
    """Test getting simple nested value."""
    value = parse_packages.get_value(sample_packages_data, "runtimes.node.version")
    assert value == "22"


def test_get_value_deep_nesting(sample_packages_data):
    """Test getting deeply nested value."""
    value = parse_packages.get_value(sample_packages_data, "runtimes.python.version")
    assert value == "3.12"


def test_get_system_packages_apt(sample_packages_data):
    """Test extracting apt packages."""
    packages = parse_packages.get_system_packages(sample_packages_data, "apt")
    assert packages == ["curl", "git", "build-essential"]


def test_get_system_packages_brew(sample_packages_data):
    """Test extracting brew packages."""
    packages = parse_packages.get_system_packages(sample_packages_data, "brew")
    assert packages == ["curl", "git"]


def test_get_system_packages_pacman(sample_packages_data):
    """Test extracting pacman packages."""
    packages = parse_packages.get_system_packages(sample_packages_data, "pacman")
    assert packages == ["curl", "git", "base-devel"]


def test_get_cargo_packages(sample_packages_data):
    """Test extracting cargo package names."""
    packages = parse_packages.get_cargo_packages(sample_packages_data)
    assert packages == ["ripgrep", "fd-find"]


def test_get_npm_packages(sample_packages_data):
    """Test extracting npm package names from all categories."""
    packages = parse_packages.get_npm_packages(sample_packages_data)
    assert packages == ["prettier", "markdownlint-cli", "typescript-language-server"]


def test_get_uv_packages(sample_packages_data):
    """Test extracting uv tool names."""
    packages = parse_packages.get_uv_packages(sample_packages_data)
    assert packages == ["black", "isort"]


def test_get_go_packages(sample_packages_data):
    """Test extracting go tool package paths."""
    packages = parse_packages.get_go_packages(sample_packages_data)
    assert packages == [
        "github.com/jesseduffield/lazydocker@latest",
        "github.com/rhysd/actionlint/cmd/actionlint@latest"
    ]


def test_get_mas_apps(sample_packages_data):
    """Test extracting Mac App Store app IDs."""
    packages = parse_packages.get_mas_apps(sample_packages_data)
    assert packages == ["937984704", "1352778147"]


def test_get_github_packages(sample_packages_data):
    """Test extracting GitHub release package names."""
    packages = parse_packages.get_github_packages(sample_packages_data)
    assert packages == ["neovim", "lazygit"]


def test_get_shell_plugins_names(sample_packages_data):
    """Test extracting shell plugin names."""
    packages = parse_packages.get_shell_plugins(sample_packages_data, output_format='names')
    assert packages == ["zsh-autosuggestions", "fast-syntax-highlighting"]


def test_get_shell_plugins_name_repo(sample_packages_data):
    """Test extracting shell plugin name|repo pairs."""
    packages = parse_packages.get_shell_plugins(sample_packages_data, output_format='name_repo')
    assert packages == [
        "zsh-autosuggestions|zsh-users/zsh-autosuggestions",
        "fast-syntax-highlighting|zdharma-continuum/fast-syntax-highlighting"
    ]


def test_get_github_release_field(sample_packages_data):
    """Test getting field from GitHub release."""
    value = parse_packages.get_github_release_field(sample_packages_data, "neovim", "min_version")
    assert value == "0.9.0"

    value = parse_packages.get_github_release_field(sample_packages_data, "neovim", "repo")
    assert value == "neovim/neovim"


def test_get_github_release_field_not_found(sample_packages_data):
    """Test getting field from non-existent release."""
    value = parse_packages.get_github_release_field(sample_packages_data, "nonexistent", "repo")
    assert value is None


def test_get_macos_taps(sample_packages_data):
    """Test extracting macOS Homebrew taps."""
    taps = parse_packages.get_macos_taps(sample_packages_data)
    assert taps == ["homebrew/cask-fonts"]


def test_get_flatpak_apps(sample_packages_data):
    """Test extracting Flatpak app IDs."""
    apps = parse_packages.get_flatpak_apps(sample_packages_data)
    assert apps == ["com.slack.Slack", "us.zoom.Zoom"]


def test_get_macos_casks(sample_packages_data):
    """Test extracting macOS cask names."""
    casks = parse_packages.get_macos_casks(sample_packages_data)
    assert casks == ["alfred", "bettertouchtool"]


def test_get_cargo_packages_empty():
    """Test with no cargo packages."""
    data = {}
    packages = parse_packages.get_cargo_packages(data)
    assert packages == []


def test_get_system_packages_empty():
    """Test with no system packages."""
    data = {}
    packages = parse_packages.get_system_packages(data, "apt")
    assert packages == []


# ================================================================
# Live packages.yml validation: cargo binary_pattern
# ================================================================
# broot has burned us twice with non-standard release format.
# These tests pin the known-good patterns so regressions are caught
# before the offline bundle is built, not after install on WSL.


def test_broot_uses_version_pattern_not_target(real_packages_data):
    """broot releases a fat zip named by version (broot_1.56.2.zip), NOT by
    target triple (broot_x86_64-unknown-linux-gnu.zip). Using {target} causes
    a 404 on every bundle build. This test pins the correct placeholder."""
    cargo_packages = real_packages_data.get("cargo_packages", [])
    broot = next((p for p in cargo_packages if p.get("name") == "broot"), None)

    assert broot is not None, "broot must be present in cargo_packages"
    pattern = broot.get("binary_pattern", "")

    assert pattern, "broot must have a binary_pattern field"
    assert "{target}" not in pattern, (
        f"broot binary_pattern must NOT use {{target}} — broot ships a fat zip "
        f"with all platforms, named only by version. Got: {pattern!r}"
    )
    assert "{version_num}" in pattern or "{version}" in pattern, (
        f"broot binary_pattern must use a version placeholder. Got: {pattern!r}"
    )


def test_cargo_packages_with_binary_pattern_have_github_repo(real_packages_data):
    """Any cargo package with a binary_pattern must also have a github_repo,
    since the pattern is only used to construct a GitHub release download URL."""
    cargo_packages = real_packages_data.get("cargo_packages", [])
    for pkg in cargo_packages:
        if "binary_pattern" in pkg:
            assert "github_repo" in pkg, (
                f"Cargo package {pkg['name']!r} has binary_pattern but no github_repo. "
                f"binary_pattern is only used for GitHub release URLs."
            )


# ================================================================
# Unit tests: filter_custom_installers_by_manifest
# ================================================================
# The offline bundler runs --type=custom --filter=bundle_install_script
# --manifest=<machine> to pick up only the install scripts that the target
# machine actually uses AND that have a downloadable script worth caching.
# Both predicates must compose correctly or the bundle will either be missing
# scripts (broken offline install) or carrying scripts the machine never runs.
#
# Each parametrize row encodes one mutation defense: invert the membership
# check, drop the True branch, swallow filter_field, etc. Together they pin
# every branch of the filter without requiring manual mutation testing.


@pytest.fixture
def custom_installers_sample():
    """Realistic sample mirroring the structure of packages.yml custom_installers."""
    return {
        "custom_installers": [
            {"name": "claude-code", "bundle_install_script": True},
            {"name": "theme", "bundle_install_script": True},
            {"name": "font", "bundle_install_script": True},
            {"name": "awscli"},
            {"name": "terraform-ls"},
        ]
    }


@pytest.mark.parametrize(
    "case_id, manifest, filter_field, expected",
    [
        # Intersection: list of names returns only names present in BOTH manifest and packages.yml.
        # Mutation it catches: inverting `in` to `not in` flips intersection to complement.
        ("list_intersection",
            {"custom_installers": ["claude-code", "awscli"]}, None,
            ["claude-code", "awscli"]),

        # True branch returns every entry in declaration order.
        # Mutation it catches: True branch returning [] or filtered list.
        ("true_returns_all",
            {"custom_installers": True}, None,
            ["claude-code", "theme", "font", "awscli", "terraform-ls"]),

        # Missing field defaults to [], not all.
        # Mutation it catches: `manifest.get('custom_installers', True)` (wrong default).
        ("missing_field_returns_empty",
            {}, None,
            []),

        # Empty list returns []. Note this is distinct from True — falsy list must NOT fall
        # through to the True branch.
        # Mutation it catches: `if not manifest_installers` placed BEFORE the `is True` check.
        ("empty_list_returns_empty",
            {"custom_installers": []}, None,
            []),

        # filter_field ANDs with manifest membership. terraform-ls and awscli are in the
        # manifest but lack bundle_install_script; only claude-code survives both predicates.
        # Mutation it catches: dropping the filter_field clause (would return all 3).
        ("filter_field_ands_with_manifest",
            {"custom_installers": ["claude-code", "awscli", "terraform-ls"]}, "bundle_install_script",
            ["claude-code"]),

        # filter_field still applies when manifest_installers is True.
        # Mutation it catches: filter_field clause skipped on the True branch only.
        ("filter_field_with_true_manifest",
            {"custom_installers": True}, "bundle_install_script",
            ["claude-code", "theme", "font"]),

        # filter_field with manifest containing only un-flagged names yields []. Catches the
        # case where manifest says "yes install awscli" but the bundle has no script for it.
        # Mutation it catches: filter_field treated as OR (would return both names).
        ("filter_field_excludes_all_unflagged",
            {"custom_installers": ["awscli", "terraform-ls"]}, "bundle_install_script",
            []),

        # Stale manifest names (no matching packages.yml entry) are silently dropped, not errors.
        # Mutation it catches: emitting manifest names verbatim instead of intersecting.
        ("unknown_manifest_names_dropped",
            {"custom_installers": ["claude-code", "ghost-installer", "another-ghost"]}, None,
            ["claude-code"]),

        # filter_field with missing manifest field still returns [] (not "all where flag").
        # Mutation it catches: filter_field path bypassing the manifest check entirely.
        ("filter_field_with_missing_manifest",
            {}, "bundle_install_script",
            []),
    ],
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_filter_custom_installers_by_manifest(custom_installers_sample, case_id, manifest, filter_field, expected):
    """Parametrized contract for filter_custom_installers_by_manifest. See the case
    comments above for the specific mutation each row defends against."""
    result = parse_packages.filter_custom_installers_by_manifest(
        custom_installers_sample, manifest, filter_field=filter_field
    )
    assert result == expected, f"case={case_id!r}: expected {expected}, got {result}"


# ================================================================
# Live-config invariants: cargo bundle composition by manifest
# ================================================================
# webviewrs is the regression: it depends on WebKitGTK + GStreamer at runtime
# (packages.yml:562-568) so it ships only on archlinux-personal-workstation.
# The offline bundler used to fetch all cargo_packages indiscriminately, which
# 404'd on webviewrs and broke WSL bundles.
#
# This parametrized test runs the same assertion across every machine manifest
# we ship. It's the strongest defense against two specific regression classes:
#
#   1. Filter goes back to "fetch everything" — webviewrs leaks into wsl/mac/ubuntu.
#   2. Someone hardcodes `if name == 'webviewrs': skip` — the arch row breaks.
#
# It also pins broot (which arch/mac/wsl have but ubuntu-lxc-server doesn't) so
# any future package with similar selective-shipping semantics is covered.


@pytest.mark.parametrize(
    "manifest_name, must_include, must_exclude",
    [
        # WSL work: the manifest that triggered the bug.
        ("wsl-work-workstation",
            ["bat", "fd", "eza", "zoxide", "delta", "oxker", "broot"],
            ["webviewrs"]),
        # macOS personal: same cargo set as WSL, also no webviewrs.
        ("macos-personal-workstation",
            ["bat", "fd", "eza", "zoxide", "delta", "oxker", "broot"],
            ["webviewrs"]),
        # Arch personal: the only machine that actually installs webviewrs.
        # Proves the filter is data-driven, not a hardcoded skip.
        ("archlinux-personal-workstation",
            ["bat", "fd", "eza", "zoxide", "delta", "oxker", "broot", "webviewrs"],
            []),
        # Ubuntu LXC server: smaller cargo set — no broot, no webviewrs.
        # Catches mutations that hardcode-include broot for all linux machines.
        ("ubuntu-lxc-server",
            ["bat", "fd", "eza", "zoxide", "delta", "oxker"],
            ["broot", "webviewrs"]),
    ],
)
def test_cargo_bundle_composition_by_manifest(real_packages_data, manifest_name, must_include, must_exclude):
    """Each machine's cargo bundle must contain its manifest's packages and nothing else.
    Names compared are commands (binary_info first column), since fd-find→fd, git-delta→delta."""
    manifest = parse_packages.load_manifest(manifest_name)
    result = parse_packages.filter_cargo_packages_by_manifest(
        real_packages_data, manifest, output_format="binary_info"
    )
    names = {line.split("|", 1)[0] for line in result}
    missing = [n for n in must_include if n not in names]
    leaked = [n for n in must_exclude if n in names]
    assert not missing, f"{manifest_name}: missing required cargo entries {missing}; got {sorted(names)}"
    assert not leaked, f"{manifest_name}: cargo bundle leaked {leaked}; got {sorted(names)}"
