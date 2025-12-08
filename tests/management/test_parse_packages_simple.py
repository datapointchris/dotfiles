#!/usr/bin/python3
"""
Simple tests for parse-packages.py (no pytest required)

Run with: /usr/bin/python3 tests/management/test_parse_packages_simple.py
or: python3 tests/management/test_parse_packages_simple.py (if yaml is available)
"""

import sys
from pathlib import Path

# Add management directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "management"))

# Import parse-packages.py (has hyphen so use importlib)
import importlib.util
spec = importlib.util.spec_from_file_location("parse_packages", Path(__file__).parent.parent.parent / "management" / "parse-packages.py")
parse_packages = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parse_packages)


def test_get_value():
    """Test getting nested values with dot notation."""
    data = {
        "runtimes": {
            "node": {"version": "22"},
            "python": {"version": "3.12"}
        }
    }

    assert parse_packages.get_value(data, "runtimes.node.version") == "22"
    assert parse_packages.get_value(data, "runtimes.python.version") == "3.12"
    print("✓ test_get_value passed")


def test_get_cargo_packages():
    """Test extracting cargo packages."""
    data = {
        "cargo_packages": [
            {"name": "ripgrep"},
            {"name": "fd-find"}
        ]
    }

    packages = parse_packages.get_cargo_packages(data)
    assert packages == ["ripgrep", "fd-find"]

    # Test with empty data
    empty_packages = parse_packages.get_cargo_packages({})
    assert empty_packages == []

    print("✓ test_get_cargo_packages passed")


def test_get_npm_packages():
    """Test extracting npm packages from categories."""
    data = {
        "npm_globals": {
            "formatters": [
                {"name": "prettier"},
                {"name": "markdownlint-cli"}
            ],
            "language_servers": [
                {"name": "typescript-language-server"}
            ]
        }
    }

    packages = parse_packages.get_npm_packages(data)
    assert packages == ["prettier", "markdownlint-cli", "typescript-language-server"]
    print("✓ test_get_npm_packages passed")


def test_get_system_packages():
    """Test extracting system packages by manager."""
    data = {
        "system_packages": [
            {"apt": "curl", "brew": "curl", "pacman": "curl"},
            {"apt": "git", "brew": "git", "pacman": "git"},
            {"apt": "build-essential", "pacman": "base-devel"}
        ]
    }

    apt_pkgs = parse_packages.get_system_packages(data, "apt")
    assert apt_pkgs == ["curl", "git", "build-essential"]

    brew_pkgs = parse_packages.get_system_packages(data, "brew")
    assert brew_pkgs == ["curl", "git"]

    pacman_pkgs = parse_packages.get_system_packages(data, "pacman")
    assert pacman_pkgs == ["curl", "git", "base-devel"]

    print("✓ test_get_system_packages passed")


def test_get_go_packages():
    """Test extracting go tool packages."""
    data = {
        "go_tools": [
            {"package": "github.com/jesseduffield/lazydocker@latest"},
            {"package": "github.com/rhysd/actionlint/cmd/actionlint@latest"}
        ]
    }

    packages = parse_packages.get_go_packages(data)
    assert len(packages) == 2
    assert packages[0] == "github.com/jesseduffield/lazydocker@latest"
    print("✓ test_get_go_packages passed")


def test_get_github_binary_field():
    """Test getting fields from GitHub binaries."""
    data = {
        "github_binaries": [
            {"name": "neovim", "repo": "neovim/neovim", "min_version": "0.9.0"},
            {"name": "lazygit", "repo": "jesseduffield/lazygit"}
        ]
    }

    min_version = parse_packages.get_github_binary_field(data, "neovim", "min_version")
    assert min_version == "0.9.0"

    repo = parse_packages.get_github_binary_field(data, "neovim", "repo")
    assert repo == "neovim/neovim"

    not_found = parse_packages.get_github_binary_field(data, "nonexistent", "repo")
    assert not_found is None

    print("✓ test_get_github_binary_field passed")


def test_get_shell_plugins():
    """Test extracting shell plugins in different formats."""
    data = {
        "shell_plugins": [
            {"name": "zsh-autosuggestions", "repo": "zsh-users/zsh-autosuggestions"},
            {"name": "fast-syntax-highlighting", "repo": "zdharma-continuum/fast-syntax-highlighting"}
        ]
    }

    # Test names format
    names = parse_packages.get_shell_plugins(data, output_format='names')
    assert names == ["zsh-autosuggestions", "fast-syntax-highlighting"]

    # Test name|repo format
    pairs = parse_packages.get_shell_plugins(data, output_format='name_repo')
    assert pairs[0] == "zsh-autosuggestions|zsh-users/zsh-autosuggestions"
    assert len(pairs) == 2

    print("✓ test_get_shell_plugins passed")


def main():
    """Run all tests."""
    print("Running parse-packages.py tests...\n")

    test_get_value()
    test_get_cargo_packages()
    test_get_npm_packages()
    test_get_system_packages()
    test_get_go_packages()
    test_get_github_binary_field()
    test_get_shell_plugins()

    print("\n✅ All tests passed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
