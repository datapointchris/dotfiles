#!/usr/bin/python3
"""
Parse packages.yml and output package lists for installation.

Usage:
    python parse_packages.py --type=system --manager=apt
    python parse_packages.py --type=cargo
    python parse_packages.py --type=npm
    python parse_packages.py --type=uv
    python parse_packages.py --type=local_uv
    python parse_packages.py --type=go
    python parse_packages.py --type=mas
    python parse_packages.py --type=github
    python parse_packages.py --type=flatpak
    python parse_packages.py --type=macos-casks
    python parse_packages.py --taps
    python parse_packages.py --get=runtimes.node.version

Manifest-filtered usage:
    python parse_packages.py --type=go --manifest=ubuntu-lxc-server
    python parse_packages.py --manifest-field=platform --manifest=arch-personal-workstation
    python parse_packages.py --manifest-field=go_tools --manifest=ubuntu-lxc-server

Note: This script requires PyYAML to be installed.
    - Install scripts use /usr/bin/python3 which has PyYAML installed
    - If running manually and getting "No module named 'yaml'", use:
        /usr/bin/python3 management/parse_packages.py [args]
      OR
        uv run --python python3 management/parse_packages.py [args]
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


def get_manifest_file(machine_name):
    """Find machine manifest YAML relative to script location."""
    script_dir = Path(__file__).parent
    manifest_file = script_dir / "machines" / f"{machine_name}.yml"
    if not manifest_file.exists():
        print(f"Error: manifest not found at {manifest_file}", file=sys.stderr)
        sys.exit(1)
    return manifest_file


def load_manifest(machine_name):
    """Load and parse a machine manifest."""
    manifest_file = get_manifest_file(machine_name)
    with open(manifest_file) as f:
        return yaml.safe_load(f)


def filter_go_packages_by_manifest(data, manifest):
    """Filter go packages to only those named in the manifest."""
    manifest_tools = manifest.get('go_tools', [])
    if manifest_tools is True:
        return get_go_packages(data)
    if not manifest_tools:
        return []
    all_tools = data.get('go_tools', [])
    return [pkg['package'] for pkg in all_tools if pkg['name'] in manifest_tools]


def filter_github_releases_by_manifest(data, manifest):
    """Filter github binary names to only those in the manifest."""
    manifest_releases = manifest.get('github_releases', [])
    if manifest_releases is True:
        return get_github_packages(data)
    if not manifest_releases:
        return []
    all_binaries = data.get('github_binaries', [])
    return [pkg['name'] for pkg in all_binaries if pkg['name'] in manifest_releases]


def filter_cargo_packages_by_manifest(data, manifest, output_format='names'):
    """Filter cargo packages to only those named in the manifest."""
    manifest_pkgs = manifest.get('cargo_packages', [])
    if manifest_pkgs is True:
        return get_cargo_packages(data, output_format)
    if not manifest_pkgs:
        return []
    all_pkgs = data.get('cargo_packages', [])
    filtered = [pkg for pkg in all_pkgs if pkg['name'] in manifest_pkgs]
    if output_format == 'name_command':
        return [f"{pkg['name']}|{pkg.get('command', pkg['name'])}" for pkg in filtered]
    elif output_format == 'github_repos':
        return [f"{pkg.get('command', pkg['name'])}|{pkg['github_repo']}"
                for pkg in filtered if 'github_repo' in pkg]
    elif output_format == 'binary_info':
        results = []
        for pkg in filtered:
            if 'github_repo' in pkg and 'binary_pattern' in pkg:
                cmd = pkg.get('command', pkg['name'])
                repo = pkg['github_repo']
                pattern = pkg['binary_pattern']
                linux_target = pkg.get('linux_target', '')
                results.append(f"{cmd}|{repo}|{pattern}|{linux_target}")
        return results
    else:
        return [pkg['name'] for pkg in filtered]


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


def get_cargo_packages(data, output_format='names'):
    """Extract cargo package information.

    Args:
        output_format: 'names' returns just names,
                      'name_command' returns 'name|command' pairs,
                      'github_repos' returns 'command|github_repo' for offline bundling,
                      'binary_info' returns 'command|repo|pattern|linux_target' for offline bundling
    """
    if 'cargo_packages' not in data:
        return []

    if output_format == 'name_command':
        return [f"{pkg['name']}|{pkg.get('command', pkg['name'])}" for pkg in data['cargo_packages']]
    elif output_format == 'github_repos':
        return [f"{pkg.get('command', pkg['name'])}|{pkg['github_repo']}"
                for pkg in data['cargo_packages'] if 'github_repo' in pkg]
    elif output_format == 'binary_info':
        results = []
        for pkg in data['cargo_packages']:
            if 'github_repo' in pkg and 'binary_pattern' in pkg:
                cmd = pkg.get('command', pkg['name'])
                repo = pkg['github_repo']
                pattern = pkg['binary_pattern']
                linux_target = pkg.get('linux_target', '')
                results.append(f"{cmd}|{repo}|{pattern}|{linux_target}")
        return results
    else:
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


def get_local_uv_packages(data):
    """Extract local uv tool name:path pairs."""
    if 'local_uv_tools' not in data:
        return []
    return [f"{pkg['name']}:{pkg['path']}" for pkg in data['local_uv_tools']]


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


def get_flatpak_apps(data):
    """Extract Flatpak app IDs."""
    if 'flatpak_apps' not in data:
        return []
    return [app['flatpak_id'] for app in data['flatpak_apps']]


def get_macos_casks(data):
    """Extract macOS cask names."""
    if 'macos_casks' not in data:
        return []
    return [cask['name'] for cask in data['macos_casks']]


def get_nerd_fonts(data, output_format='names'):
    """Extract Nerd Font information.

    Args:
        output_format: 'names' returns just names,
                      'packages' returns just package names (for download),
                      'full' returns 'name|package|check_pattern|extension' tuples
    """
    if 'nerd_fonts' not in data:
        return []

    fonts = data['nerd_fonts']
    if output_format == 'packages':
        return [font['package'] for font in fonts]
    elif output_format == 'full':
        return [f"{font['name']}|{font['package']}|{font['check_pattern']}|{font['extension']}" for font in fonts]
    else:  # names
        return [font['name'] for font in fonts]


def main():
    parser = argparse.ArgumentParser(description='Parse packages.yml')
    parser.add_argument('--type', choices=['system', 'cargo', 'npm', 'uv', 'local_uv', 'go', 'mas', 'github', 'shell-plugins', 'flatpak', 'macos-casks', 'nerd-fonts'],
                        help='Type of packages to extract')
    parser.add_argument('--manager', choices=['apt', 'pacman', 'brew', 'aur'],
                        help='Package manager for system packages')
    parser.add_argument('--get', help='Get a specific value using dot notation (e.g., runtimes.node.version)')
    parser.add_argument('--taps', action='store_true',
                        help='Get macOS Homebrew taps')
    parser.add_argument('--github-binary', help='Name of GitHub binary (e.g., neovim)')
    parser.add_argument('--field', help='Field to extract from GitHub binary (e.g., min_version, repo)')
    parser.add_argument('--format', choices=['names', 'name_repo', 'name_command', 'packages', 'full', 'github_repos', 'binary_info'], default='names',
                        help='Output format: names, name|repo pairs (shell-plugins), name|command pairs (cargo), github_repos/binary_info (cargo for offline), packages/full (nerd-fonts)')
    parser.add_argument('--manifest', help='Machine manifest name (e.g., ubuntu-lxc-server) to filter packages')
    parser.add_argument('--manifest-field', help='Extract a field from the manifest (e.g., platform, go_tools)')

    args = parser.parse_args()

    # Handle manifest-field extraction (no packages.yml needed)
    if args.manifest_field:
        if not args.manifest:
            print("Error: --manifest required with --manifest-field", file=sys.stderr)
            sys.exit(1)
        manifest = load_manifest(args.manifest)
        value = manifest.get(args.manifest_field)
        if value is None:
            print(f"Error: field '{args.manifest_field}' not found in manifest", file=sys.stderr)
            sys.exit(1)
        if isinstance(value, list):
            for item in value:
                print(item)
        elif isinstance(value, bool):
            print("true" if value else "false")
        else:
            print(value)
        return

    data = load_packages()
    manifest = load_manifest(args.manifest) if args.manifest else None

    if args.taps:
        taps = get_macos_taps(data)
        for tap in taps:
            print(tap)
        return

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

    if args.get:
        value = get_value(data, args.get)
        print(value)
        return

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
        fmt = args.format if hasattr(args, 'format') and args.format else 'names'
        if manifest:
            packages = filter_cargo_packages_by_manifest(data, manifest, fmt)
        else:
            packages = get_cargo_packages(data, fmt)
    elif args.type == 'npm':
        if manifest and not manifest.get('npm_globals', True):
            packages = []
        else:
            packages = get_npm_packages(data)
    elif args.type == 'uv':
        if manifest and not manifest.get('uv_tools', True):
            packages = []
        else:
            packages = get_uv_packages(data)
    elif args.type == 'local_uv':
        if manifest and not manifest.get('local_uv_tools', True):
            packages = []
        else:
            packages = get_local_uv_packages(data)
    elif args.type == 'go':
        if manifest:
            packages = filter_go_packages_by_manifest(data, manifest)
        else:
            packages = get_go_packages(data)
    elif args.type == 'mas':
        packages = get_mas_apps(data)
    elif args.type == 'github':
        if manifest:
            packages = filter_github_releases_by_manifest(data, manifest)
        else:
            packages = get_github_packages(data)
    elif args.type == 'shell-plugins':
        packages = get_shell_plugins(data, args.format)
    elif args.type == 'flatpak':
        packages = get_flatpak_apps(data)
    elif args.type == 'macos-casks':
        packages = get_macos_casks(data)
    elif args.type == 'nerd-fonts':
        packages = get_nerd_fonts(data, args.format)

    for pkg in packages:
        print(pkg)


if __name__ == '__main__':
    main()
