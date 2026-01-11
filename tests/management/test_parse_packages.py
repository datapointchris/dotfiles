"""
Tests for parse_packages.py

Run with: pytest tests/management/test_parse_packages.py
Or from project root: python -m pytest tests/management/
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "management"))
import parse_packages


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
        "github_binaries": [
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
    """Test extracting GitHub binary package names."""
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


def test_get_github_binary_field(sample_packages_data):
    """Test getting field from GitHub binary."""
    value = parse_packages.get_github_binary_field(sample_packages_data, "neovim", "min_version")
    assert value == "0.9.0"

    value = parse_packages.get_github_binary_field(sample_packages_data, "neovim", "repo")
    assert value == "neovim/neovim"


def test_get_github_binary_field_not_found(sample_packages_data):
    """Test getting field from non-existent binary."""
    value = parse_packages.get_github_binary_field(sample_packages_data, "nonexistent", "repo")
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
