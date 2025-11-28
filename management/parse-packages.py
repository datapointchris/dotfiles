#!/usr/bin/python3
"""
Parse packages.yml and output package lists for installation.

Usage:
    python parse-packages.py --type=system --manager=apt
    python parse-packages.py --type=cargo
    python parse-packages.py --type=npm
    python parse-packages.py --type=uv
    python parse-packages.py --type=go
    python parse-packages.py --type=mas
    python parse-packages.py --type=github
    python parse-packages.py --type=linux-gui
    python parse-packages.py --type=macos-casks
    python parse-packages.py --taps
    python parse-packages.py --get=runtimes.node.version

Note: This script requires PyYAML to be installed.
    - Install scripts use /usr/bin/python3 which has PyYAML installed
    - If running manually and getting "No module named 'yaml'", use:
        /usr/bin/python3 management/parse-packages.py [args]
      OR
        uv run --python python3 management/parse-packages.py [args]
"""

import argparse
import sys
from pathlib import Path

import yaml


def get_packages_file():
    """Find packages.yml relative to script location."""
    script_dir = Path(__file__).parent
    packages_file = script_dir / "packages.yml"
    if not packages_file.exists():
        print(f"Error: packages.yml not found at {packages_file}", file=sys.stderr)
        sys.exit(1)
    return packages_file


def load_packages():
    """Load and parse packages.yml."""
    packages_file = get_packages_file()
    with open(packages_file) as f:
        return yaml.safe_load(f)


def get_value(data, path):
    """Get a nested value from data using dot notation (e.g., 'runtimes.node.version')."""
    keys = path.split('.')
    value = data
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            print(f"Error: Key '{path}' not found in packages.yml", file=sys.stderr)
            sys.exit(1)
    return value


def get_system_packages(data, manager):
    """Extract system packages for a specific package manager."""
    if 'system_packages' not in data:
        return []

    packages = []
    for pkg in data['system_packages']:
        if manager in pkg:
            packages.append(pkg[manager])
    return packages


def get_cargo_packages(data):
    """Extract cargo package names."""
    if 'cargo_packages' not in data:
        return []
    return [pkg['name'] for pkg in data['cargo_packages']]


def get_npm_packages(data):
    """Extract npm package names from all categories."""
    if 'npm_globals' not in data:
        return []

    packages = []
    for category in data['npm_globals'].values():
        for pkg in category:
            packages.append(pkg['name'])
    return packages


def get_uv_packages(data):
    """Extract uv tool names from all categories."""
    if 'uv_tools' not in data:
        return []

    packages = []
    for category in data['uv_tools'].values():
        for pkg in category:
            packages.append(pkg['name'])
    return packages


def get_go_packages(data):
    """Extract go tool package paths."""
    if 'go_tools' not in data:
        return []
    return [pkg['package'] for pkg in data['go_tools']]


def get_mas_apps(data):
    """Extract Mac App Store app IDs."""
    if 'mas_apps' not in data:
        return []
    return [str(pkg['id']) for pkg in data['mas_apps']]


def get_github_packages(data):
    """Extract GitHub binary package names."""
    if 'github_binaries' not in data:
        return []
    return [pkg['name'] for pkg in data['github_binaries']]


def get_shell_plugins(data, output_format='names'):
    """Extract shell plugins.

    Args:
        output_format: 'names' returns just names, 'name_repo' returns 'name|repo' pairs
    """
    if 'shell_plugins' not in data:
        return []

    if output_format == 'name_repo':
        return [f"{pkg['name']}|{pkg['repo']}" for pkg in data['shell_plugins']]
    else:  # names
        return [pkg['name'] for pkg in data['shell_plugins']]


def get_github_binary_field(data, name, field):
    """Get a field from a specific GitHub binary by name."""
    if 'github_binaries' not in data:
        return None

    for binary in data['github_binaries']:
        if binary.get('name') == name:
            return binary.get(field)
    return None


def get_macos_taps(data):
    """Extract macOS Homebrew taps."""
    return data.get('macos_taps', [])


def get_linux_gui_apps(data):
    """Extract Linux GUI app Flatpak IDs."""
    if 'linux_gui_apps' not in data:
        return []
    return [app['flatpak_id'] for app in data['linux_gui_apps']]


def get_macos_casks(data):
    """Extract macOS cask names."""
    if 'macos_casks' not in data:
        return []
    return [cask['name'] for cask in data['macos_casks']]


def main():
    parser = argparse.ArgumentParser(description='Parse packages.yml')
    parser.add_argument('--type', choices=['system', 'cargo', 'npm', 'uv', 'go', 'mas', 'github', 'shell-plugins', 'linux-gui', 'macos-casks'],
                        help='Type of packages to extract')
    parser.add_argument('--manager', choices=['apt', 'pacman', 'brew'],
                        help='Package manager for system packages')
    parser.add_argument('--get', help='Get a specific value using dot notation (e.g., runtimes.node.version)')
    parser.add_argument('--taps', action='store_true',
                        help='Get macOS Homebrew taps')
    parser.add_argument('--github-binary', help='Name of GitHub binary (e.g., neovim)')
    parser.add_argument('--field', help='Field to extract from GitHub binary (e.g., min_version, repo)')
    parser.add_argument('--format', choices=['names', 'name_repo'], default='names',
                        help='Output format for shell-plugins (names or name|repo pairs)')

    args = parser.parse_args()

    data = load_packages()

    # Handle --taps for extracting macOS Homebrew taps
    if args.taps:
        taps = get_macos_taps(data)
        for tap in taps:
            print(tap)
        return

    # Handle --github-binary for extracting GitHub binary metadata
    if args.github_binary:
        if not args.field:
            print("Error: --field required with --github-binary", file=sys.stderr)
            sys.exit(1)
        value = get_github_binary_field(data, args.github_binary, args.field)
        if value is not None:
            print(value)
        else:
            print(f"Error: {args.github_binary}.{args.field} not found", file=sys.stderr)
            sys.exit(1)
        return

    # Handle --get for extracting specific values
    if args.get:
        value = get_value(data, args.get)
        print(value)
        return

    # Handle package type extraction
    if not args.type:
        parser.print_help()
        sys.exit(1)

    packages = []

    if args.type == 'system':
        if not args.manager:
            print("Error: --manager required for system packages", file=sys.stderr)
            sys.exit(1)
        packages = get_system_packages(data, args.manager)
    elif args.type == 'cargo':
        packages = get_cargo_packages(data)
    elif args.type == 'npm':
        packages = get_npm_packages(data)
    elif args.type == 'uv':
        packages = get_uv_packages(data)
    elif args.type == 'go':
        packages = get_go_packages(data)
    elif args.type == 'mas':
        packages = get_mas_apps(data)
    elif args.type == 'github':
        packages = get_github_packages(data)
    elif args.type == 'shell-plugins':
        packages = get_shell_plugins(data, args.format)
    elif args.type == 'linux-gui':
        packages = get_linux_gui_apps(data)
    elif args.type == 'macos-casks':
        packages = get_macos_casks(data)

    # Output one per line
    for pkg in packages:
        print(pkg)


if __name__ == '__main__':
    main()
