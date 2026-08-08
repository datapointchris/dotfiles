"""Everything asked of the declaration that is not "what should this machine have?".

Browsing and search, plus the two drift checks — `verify` compares the repo
against itself and runs on every commit, `missing` compares *this machine*
against what its manifest declares and is what `doctor` calls. They are separate
because a box part-way through a rollout is not a repo defect.

The schema left here for `catalog.py`, where a section's shape is the section's
dataclass. What stays is the half that is about more than one file: a manifest
naming a package that does not exist, an installer script with no entry, an entry
no manifest ever names.
"""

import argparse
import json
import os
import platform
import shutil
import sys
from collections import Counter
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

import dotfiles
from dotfiles import catalog
from dotfiles import paths

SECTION_STRUCTURES = {section: cls.structure for section, cls in catalog.SECTIONS.items()}
"""How each section is spelled, for the raw-dict walks below. `catalog.SECTIONS`
is the one description of that; nothing here restates it."""

PACKAGE_SECTIONS = tuple(catalog.SECTIONS)

ID_FIELDS = {'flatpak_apps': 'flatpak_id'}
"""The one section identified by something other than `name`. Everything absent
from this map is keyed by its name."""

# Sections whose manifest field is a list of names that must resolve to packages.yml entries.
NAME_SUBSCRIBED_SECTIONS = (
    'go_tools',
    'cargo_packages',
    'npm_globals',
    'uv_tools',
    'git_uv_tools',
    'github_releases',
    'custom_installers',
)

# Manifest keys that used to gate runtimes but were removed in Phase 1.6.
# Runtime installation is now derived from name-list presence (e.g. go_tools non-empty → Go).
DEPRECATED_MANIFEST_KEYS = ('go', 'rust', 'nvm', 'uv', 'tenv')

# Sections whose entries have a 1:1 script in a directory under install/common/.
# Maps section name → subdir name.
#
# `github_releases` left when its scripts did. The parity that replaced it is
# `check_release_assets` below: the guarantee was never "a file exists with this
# name", it was "something knows how to install this entry", and a function in
# providers/releases.py is that something now.
SCRIPT_BACKED_SECTIONS = {
    'custom_installers': 'custom-installers',
}


class Color(Enum):
    """ANSI color codes."""

    RESET = '\033[0m'
    RED = '\033[0;31m'
    CYAN = '\033[0;36m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[0;33m'
    MAGENTA = '\033[0;35m'
    BRIGHT_CYAN = '\033[0;96m'
    BRIGHT_MAGENTA = '\033[0;95m'
    BRIGHT_YELLOW = '\033[0;93m'
    BRIGHT_BLUE = '\033[0;94m'
    BRIGHT_BLACK = '\033[0;90m'
    ORANGE = '\033[38;5;208m'


class InstallStatus(Enum):
    """Package installation status."""

    INSTALLED = 'installed'
    APP_ONLY = 'app-only'
    NOT_INSTALLED = 'not-installed'
    NOT_AVAILABLE = 'not-available'


class Platform(Enum):
    """Supported platforms."""

    MACOS = 'macos'
    ARCH = 'archlinux'
    LINUX = 'linux'
    UNKNOWN = 'unknown'


def use_color() -> bool:
    """Check if terminal supports color output."""
    return sys.stdout.isatty() and os.environ.get('TERM', '') != 'dumb'


USE_COLOR = use_color()


def colorize(text: str, color: Color) -> str:
    """Apply color to text if terminal supports it."""
    if USE_COLOR:
        return f'{color.value}{text}{Color.RESET.value}'
    return text


def print_section(title: str, color: Color = Color.BRIGHT_CYAN) -> None:
    """Print a section header with underline."""
    print(f'\n{title}')
    line_char = '─' if USE_COLOR else '-'
    line = line_char * (len(title) + 15)
    print(colorize(line, color) if USE_COLOR else line)


def print_header(title: str) -> None:
    """Print a main header with box drawing."""
    line = '━' * 50
    if USE_COLOR:
        print(colorize(line, Color.BRIGHT_CYAN))
        print(colorize(f' {title}', Color.BRIGHT_CYAN))
        print(colorize(line, Color.BRIGHT_CYAN))
    else:
        print(line)
        print(f' {title}')
        print(line)


def get_packages_file(root: Path | None = None) -> Path:
    """Find packages.yml. If root is given, look under <root>/install/; else walk to git root."""
    if root is not None:
        packages_file = root / 'install' / 'packages.yml'
        if packages_file.exists():
            return packages_file
        print(f'Error: packages.yml not found at {packages_file}', file=sys.stderr)
        sys.exit(1)

    if paths.PACKAGES_FILE.exists():
        return paths.PACKAGES_FILE

    print('Error: packages.yml not found', file=sys.stderr)
    sys.exit(1)


def load_packages(root: Path | None = None) -> dict[str, Any]:
    """Load and parse packages.yml, optionally rooted at an override path."""
    with get_packages_file(root).open() as f:
        return yaml.safe_load(f)


def get_all_packages(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Get all packages with their section attached as _section."""
    all_packages = []
    for section in PACKAGE_SECTIONS:
        for pkg in iter_section_entries(data, section):
            if isinstance(pkg, dict) and 'name' in pkg:
                pkg_copy = dict(pkg)
                pkg_copy['_section'] = section
                all_packages.append(pkg_copy)
    return all_packages


def get_current_platform() -> Platform:
    """Detect the current operating system platform."""
    system = platform.system()
    if system == 'Darwin':
        return Platform.MACOS
    if system == 'Linux':
        if Path('/etc/arch-release').exists():
            return Platform.ARCH
        return Platform.LINUX
    return Platform.UNKNOWN


def is_available_on_platform(pkg: dict[str, Any]) -> bool:
    """Check if package is available on the current platform."""
    section = pkg.get('_section', '')
    current = get_current_platform()

    # Platform-exclusive sections
    macos_only = ('macos_casks', 'mas_apps')
    linux_only = ('flatpak_apps',)

    if section in macos_only and current != Platform.MACOS:
        return False
    if section in linux_only and current == Platform.MACOS:
        return False

    # System packages must have an entry for the current package manager
    if section == 'system_packages':
        if current == Platform.MACOS:
            return 'brew' in pkg
        if current == Platform.ARCH:
            return 'pacman' in pkg or 'aur' in pkg
        return 'apt' in pkg  # Linux/Ubuntu default

    return True


def check_installed(pkg: dict[str, Any]) -> tuple[InstallStatus, str | None]:
    """Check if a package is installed and return its status and path."""
    if not is_available_on_platform(pkg):
        return InstallStatus.NOT_AVAILABLE, None

    name = pkg.get('name', '')
    cmd_name = pkg.get('command', name)
    section = pkg.get('_section', '')

    # Check binary_link field (used by github_releases)
    binary_link = pkg.get('binary_link', '')
    if binary_link:
        link_path = Path(binary_link).expanduser()
        if link_path.exists():
            return InstallStatus.INSTALLED, str(link_path)

    # An explicit path, for the entries that install no binary at all — a sourced
    # bash library has nothing for `which` to find, and would read as missing
    # forever.
    installed_path = pkg.get('installed_path', '')
    if installed_path:
        target = Path(installed_path).expanduser()
        if target.exists():
            return InstallStatus.INSTALLED, str(target)
        return InstallStatus.NOT_INSTALLED, None

    # Check if command is in PATH
    which_path = shutil.which(cmd_name)
    if which_path:
        return InstallStatus.INSTALLED, which_path

    # uv installs a tool per directory, and some of them are libraries pulled in
    # for another tool's benefit (numpy for the Jupyter stack) with no console
    # script of their own.
    if section in ('uv_tools', 'git_uv_tools'):
        uv_dir = Path(os.environ.get('UV_TOOL_DIR', Path.home() / '.local/share/uv/tools')) / name
        if uv_dir.is_dir():
            return InstallStatus.INSTALLED, str(uv_dir)

    # Check macOS application bundles
    if section in ('macos_casks', 'mas_apps'):
        app_path = find_macos_app(name)
        if app_path:
            return InstallStatus.APP_ONLY, str(app_path)

    return InstallStatus.NOT_INSTALLED, None


def find_macos_app(name: str) -> Path | None:
    """Find a macOS .app bundle by name (case-insensitive)."""
    target = f'{name}.app'.lower()
    for base in (Path('/Applications'), Path.home() / 'Applications'):
        if not base.exists():
            continue
        for entry in base.iterdir():
            if entry.name.lower() == target:
                return entry
    return None


def format_status(status: InstallStatus, path: str | None) -> str | None:
    """Format installation status for display."""
    if status == InstallStatus.INSTALLED:
        return colorize(f'✓ {path}', Color.GREEN)
    if status == InstallStatus.APP_ONLY:
        return colorize(f'⚠ app exists but CLI not in PATH: {path}', Color.YELLOW)
    if status == InstallStatus.NOT_AVAILABLE:
        return None
    return colorize('✗ not installed', Color.BRIGHT_BLACK)


def calculate_column_widths(items: list[dict[str, Any]], fields: list[str], max_widths: dict[str, int] | None = None) -> dict[str, int]:
    """Calculate optimal column widths for a list of items."""
    max_widths = max_widths or {}
    widths = {}
    for field in fields:
        width = max(len(str(item.get(field, ''))) for item in items) + 2
        if field in max_widths:
            width = min(width, max_widths[field])
        widths[field] = width
    return widths


# ─────────────────────────────────────────────────────────────────────────────
# Commands
# ─────────────────────────────────────────────────────────────────────────────


def cmd_sections(args: argparse.Namespace, data: dict[str, Any]) -> None:
    """List all package sections with counts."""
    print_section('Package Sections')
    print()
    for section in PACKAGE_SECTIONS:
        packages = list(iter_section_entries(data, section))
        if packages:
            print(f'  {section:<20} {len(packages):3d} packages')


def cmd_stats(args: argparse.Namespace, data: dict[str, Any]) -> None:
    """Show package statistics by section."""
    print_section('Package Statistics')
    print()

    print(f'{"Section":<24} {"Count":>5}')
    print('─' * 32)

    total = 0
    for section in PACKAGE_SECTIONS:
        count = sum(1 for _ in iter_section_entries(data, section))
        if count:
            print(f'{section:<24} {count:5d}')
            total += count

    print('─' * 32)
    print(f'{"Total":<24} {total:5d}')


def cmd_tags(args: argparse.Namespace, data: dict[str, Any]) -> None:
    """List all tags with package counts."""
    print_section('Available Tags')
    print()

    tag_counts: Counter[str] = Counter()
    for pkg in get_all_packages(data):
        tag_counts.update(pkg.get('tags', []))

    if not tag_counts:
        print('  No tags defined yet.')
        print()
        print('  Add tags to packages.yml entries:')
        print('    - name: ghostty')
        print('      description: GPU-accelerated terminal')
        print('      tags: [gui, terminal]')
        return

    for tag, count in tag_counts.most_common():
        print(f'  {tag:<16} {count:3d} packages')


def cmd_show(args: argparse.Namespace, data: dict[str, Any]) -> None:
    """Show details for a specific package."""
    name_lower = args.name.lower()
    matches = [p for p in get_all_packages(data) if p.get('name', '').lower() == name_lower]

    if not matches:
        print(f'Error: Package not found: {args.name}', file=sys.stderr)
        print('\nSimilar packages:', file=sys.stderr)
        similar = [p for p in get_all_packages(data) if name_lower in p.get('name', '').lower()]
        for pkg in similar[:5]:
            print(f'  {pkg["name"]:<28} {pkg.get("description", "")}', file=sys.stderr)
        sys.exit(1)

    # Sort with available-on-this-platform first
    matches.sort(key=lambda p: 0 if is_available_on_platform(p) else 1)

    for pkg in matches:
        print()
        print(colorize(f'Package: {pkg["name"]}', Color.CYAN))
        print('━' * 40)
        print()

        print(f'Description: {pkg.get("description", "N/A")}')
        print(f'Section:     {pkg["_section"]}')
        print(f'Tags:        {", ".join(pkg.get("tags", [])) or "none"}')

        # Platform package names
        platform_fields = ('apt', 'brew', 'pacman', 'aur')
        platforms = [(f, pkg[f]) for f in platform_fields if f in pkg]
        if platforms:
            print('\nPlatform Packages:')
            for field, value in platforms:
                print(f'  {field}:    {value}')

        # Additional metadata fields
        for field, label in (('package', 'Package'), ('repo', 'Repository'), ('github_repo', 'GitHub')):
            if field in pkg:
                print(f'{label}:     {pkg[field]}')

        # Installation status
        if is_available_on_platform(pkg):
            status, path = check_installed(pkg)
            status_str = format_status(status, path)
            if status_str:
                print(f'\nStatus:      {status_str}')

        print()


def cmd_search(args: argparse.Namespace, data: dict[str, Any]) -> None:
    """Search packages by name."""
    query_lower = args.query.lower()
    results = [p for p in get_all_packages(data) if query_lower in p.get('name', '').lower()]

    if not results:
        print(f'No packages found matching: {args.query}')
        return

    widths = calculate_column_widths(results, ['name', '_section'])

    for pkg in results:
        name = pkg.get('name', '')
        desc = pkg.get('description', '')
        section = pkg.get('_section', '')
        tags = pkg.get('tags', [])

        status, path = check_installed(pkg)
        status_str = format_status(status, path)
        tags_str = f'[{", ".join(tags)}]' if tags else ''

        print(f'{name:<{widths["name"]}} {section:<{widths["_section"]}} {tags_str}')
        print(f'  {desc}')
        if status_str:
            print(f'  {status_str}')
        print()


def cmd_list(args: argparse.Namespace, data: dict[str, Any]) -> None:
    """List packages with optional filters."""
    # Validate section filter
    if args.section and args.section not in PACKAGE_SECTIONS:
        print(f'Error: Unknown section: {args.section}', file=sys.stderr)
        print('\nAvailable sections:', file=sys.stderr)
        for s in PACKAGE_SECTIONS:
            print(f'  {s}', file=sys.stderr)
        sys.exit(1)

    # Determine which sections to query
    if args.section:
        sections = [args.section]
    elif args.platform == 'macos':
        sections = [s for s in PACKAGE_SECTIONS if s != 'flatpak_apps']
    elif args.platform == 'linux':
        sections = [s for s in PACKAGE_SECTIONS if s not in ('macos_casks', 'mas_apps')]
    else:
        sections = list(PACKAGE_SECTIONS)

    # Collect matching packages
    results = []
    for section in sections:
        for pkg in iter_section_entries(data, section):
            if not isinstance(pkg, dict) or 'name' not in pkg:
                continue
            if args.tag and args.tag not in pkg.get('tags', []):
                continue
            results.append(
                {
                    'name': pkg['name'],
                    'description': pkg.get('description', ''),
                    'section': section,
                    'tags': pkg.get('tags', []),
                }
            )

    if args.json:
        print(json.dumps(results, indent=2))
        return

    if not results:
        print('No packages found')
        return

    widths = calculate_column_widths(results, ['name', 'section'], max_widths={'name': 30})

    if args.verbose:
        print(f'{"Name":<{widths["name"]}} {"Section":<{widths["section"]}} {"Description":<35} Tags')
        print('─' * (widths['name'] + widths['section'] + 50))
        for pkg in results:
            tags_str = ', '.join(pkg['tags'])
            desc = pkg['description'][:35]
            print(f'{pkg["name"]:<{widths["name"]}} {pkg["section"]:<{widths["section"]}} {desc:<35} {tags_str}')
    else:
        for pkg in results:
            print(f'{pkg["name"]:<{widths["name"]}} {pkg["description"]}')


# ─────────────────────────────────────────────────────────────────────────────
# Verify — drift detection between packages.yml, manifests, and installer scripts
# ─────────────────────────────────────────────────────────────────────────────


def resolve_repo_root(override: str | None = None) -> Path:
    """Return the repo root — the --root override, or the ancestor of packages.yml."""
    if override:
        root = Path(override).resolve()
        if not root.exists():
            print(f'Error: --root path does not exist: {root}', file=sys.stderr)
            sys.exit(1)
        return root
    return get_packages_file().parent.parent


def load_manifests(root: Path) -> dict[str, dict[str, Any]]:
    """Load all manifests from <root>/install/manifests/*.yml, keyed by stem."""
    manifests_dir = root / 'install' / 'manifests'
    if not manifests_dir.exists():
        return {}
    manifests: dict[str, dict[str, Any]] = {}
    for manifest_file in sorted(manifests_dir.glob('*.yml')):
        with manifest_file.open() as f:
            manifests[manifest_file.stem] = yaml.safe_load(f) or {}
    return manifests


def list_installer_scripts(root: Path, subdir: str) -> set[str]:
    """Return the stem (filename without .sh) of every *.sh in install/common/<subdir>/."""
    script_dir = root / 'install' / 'common' / subdir
    if not script_dir.exists():
        return set()
    return {p.stem for p in script_dir.glob('*.sh')}


def iter_section_entries(data: dict[str, Any], section: str):
    """Yield each entry from a section. For dict-of-lists (npm_globals/uv_tools),
    flatten subcategories. For dict-of-dicts (tmux_plugins), synthesize a 'name'
    field from the outer key so downstream checks work uniformly."""
    structure = SECTION_STRUCTURES.get(section)
    section_data = data.get(section)
    if section_data is None:
        return

    if structure is catalog.Structure.LIST:
        if isinstance(section_data, list):
            yield from section_data
    elif structure is catalog.Structure.GROUPED:
        if isinstance(section_data, dict):
            for category in section_data.values():
                if isinstance(category, list):
                    yield from category
    elif structure is catalog.Structure.KEYED and isinstance(section_data, dict):
        for key, entry in section_data.items():
            if isinstance(entry, dict):
                yield {'name': key, **entry}


def get_section_ids(data: dict[str, Any], section: str) -> set[str]:
    """Return the set of id_field values for a section (e.g., names for most sections)."""
    id_field = ID_FIELDS.get(section, 'name')
    return {entry[id_field] for entry in iter_section_entries(data, section) if isinstance(entry, dict) and id_field in entry}


def check_entry_shapes(root: Path, issues: list[tuple[str, str, str]]) -> None:
    """Every per-entry rule, by building the typed catalog and reporting what it refuses.

    Required fields, unknown keys, duplicate names, declared types and the
    version-constraint rules all live on the dataclasses now, so this is a
    parse rather than a second description of the same file. That is the point:
    the shape a reader consumes and the shape `verify` enforces cannot disagree
    when they are the same object.
    """
    try:
        catalog.load(root / 'install' / 'packages.yml')
    except catalog.CatalogError as refused:
        issues.extend((issue.section, 'error', issue.message) for issue in refused.issues)


def check_manifest_name_resolution(
    data: dict[str, Any],
    manifests: dict[str, dict[str, Any]],
    issues: list[tuple[str, str, str]],
) -> None:
    """Tier 1 check 3: every name referenced from a manifest must resolve to a packages.yml entry.
    Script existence is covered transitively by the parity check below, so no direct filesystem
    check is needed here — a missing script will surface via parity as an additional error."""
    section_ids = {section: get_section_ids(data, section) for section in NAME_SUBSCRIBED_SECTIONS}

    for manifest_name, manifest in manifests.items():
        for section in NAME_SUBSCRIBED_SECTIONS:
            value = manifest.get(section)
            if not isinstance(value, list):
                continue
            for name in value:
                if name not in section_ids[section]:
                    issues.append(
                        (section, 'error', f"manifest '{manifest_name}' names '{name}' but no packages.yml {section} entry exists")
                    )


def check_script_parity(
    data: dict[str, Any],
    scripts_by_section: dict[str, set[str]],
    issues: list[tuple[str, str, str]],
) -> None:
    """Tier 1 check 4: bidirectional script ↔ packages.yml parity for every script-backed section."""
    for section, subdir in SCRIPT_BACKED_SECTIONS.items():
        section_ids = get_section_ids(data, section)
        scripts = scripts_by_section.get(section, set())

        for script_name in sorted(scripts - section_ids):
            issues.append((section, 'error', f'install/common/{subdir}/{script_name}.sh exists but no packages.yml {section} entry'))

        for entry_name in sorted(section_ids - scripts):
            issues.append(
                (section, 'error', f"packages.yml {section} entry '{entry_name}' has no install/common/{subdir}/{entry_name}.sh script")
            )


def check_release_assets(data: dict[str, Any], issues: list[tuple[str, str, str]]) -> None:
    """Every `github_releases` entry names an asset something knows how to build.

    What `check_script_parity` did for this section before its scripts were
    deleted, against the functions that replaced them. The guarantee was never
    "a file exists with this name" — it was "something can install this entry".

    One direction only, unlike the script check. The other half — a function
    naming a tool nothing declares — cannot be asked here, because `--root`
    points this at a synthetic tree while the functions are code and are always
    the real ones. It is asserted instead by
    `tests/install/test_release_urls.py::TestCorpus`, which compares both sets
    against the real declaration.
    """
    from dotfiles.providers import releases

    for name in sorted(get_section_ids(data, 'github_releases') - set(releases.ASSETS)):
        uninstallable = f"packages.yml entry '{name}' has no asset function in providers/releases.py"
        issues.append(('github_releases', 'error', uninstallable))


def check_deprecated_manifest_keys(
    manifests: dict[str, dict[str, Any]],
    issues: list[tuple[str, str, str]],
) -> None:
    """Tier 1 check: manifests must not set removed runtime-gate booleans.
    Phase 1.6 replaced them with name-list derivation (e.g. go_tools non-empty → Go)."""
    for manifest_name, manifest in manifests.items():
        for key in DEPRECATED_MANIFEST_KEYS:
            if key in manifest:
                issues.append(
                    (
                        'manifest',
                        'error',
                        f"manifest '{manifest_name}' uses removed key '{key}:' — install is now derived from the corresponding name-list",
                    )
                )


def check_unreferenced_entries(
    data: dict[str, Any],
    manifests: dict[str, dict[str, Any]],
    issues: list[tuple[str, str, str]],
) -> None:
    """Tier 2 check 5: packages.yml entries in name-subscribed sections that no manifest uses."""
    for section in NAME_SUBSCRIBED_SECTIONS:
        # If any manifest uses `true` for this section, every entry is implicitly referenced
        if any(manifest.get(section) is True for manifest in manifests.values()):
            continue
        referenced: set[str] = set()
        for manifest in manifests.values():
            value = manifest.get(section)
            if isinstance(value, list):
                referenced.update(value)
        pkg_ids = get_section_ids(data, section)
        for name in sorted(pkg_ids - referenced):
            issues.append((section, 'warning', f"'{name}' defined in packages.yml but not referenced by any manifest"))


def cmd_verify(args: argparse.Namespace, data: dict[str, Any]) -> None:
    """Verify packages.yml against manifests and installer script directories."""
    root = resolve_repo_root(args.root)
    # Reload from the resolved root to guarantee data matches root when --root overrides default
    data = load_packages(root=root)
    manifests = load_manifests(root)
    scripts_by_section = {section: list_installer_scripts(root, subdir) for section, subdir in SCRIPT_BACKED_SECTIONS.items()}

    issues: list[tuple[str, str, str]] = []  # (section, severity, message)

    check_entry_shapes(root, issues)
    check_manifest_name_resolution(data, manifests, issues)
    check_script_parity(data, scripts_by_section, issues)
    check_release_assets(data, issues)
    check_deprecated_manifest_keys(manifests, issues)
    check_unreferenced_entries(data, manifests, issues)

    errors = [i for i in issues if i[1] == 'error']
    warnings = [i for i in issues if i[1] == 'warning']

    by_section: dict[str, list[tuple[str, str]]] = {}
    for section, severity, message in issues:
        by_section.setdefault(section, []).append((severity, message))

    for section in sorted(by_section):
        print(f'\n{colorize(section, Color.BRIGHT_CYAN)}', file=sys.stderr)
        for severity, message in by_section[section]:
            if severity == 'error':
                marker = colorize('error', Color.RED)
            else:
                marker = colorize('warn ', Color.YELLOW)
            print(f'  [{marker}] {message}', file=sys.stderr)

    if issues:
        print(file=sys.stderr)

    summary = f'{len(errors)} errors, {len(warnings)} warnings'
    if not errors and not warnings:
        summary = colorize(f'✓ {summary}', Color.GREEN)
    elif errors:
        summary = colorize(f'✗ {summary}', Color.RED)
    else:
        summary = colorize(f'⚠ {summary}', Color.YELLOW)
    print(summary)

    sys.exit(1 if errors else 0)


def main(argv: list[str] | None = None) -> None:
    """Main entry point with argument parsing.

    `argv` defaults to `sys.argv[1:]` for the console script, and is passed
    explicitly by the `dotfiles` CLI, which calls this in-process. The
    alternative was shelling out to `uv run packages`, which needs a uv project
    on disk — and the installed tool has none.
    """
    parser = argparse.ArgumentParser(
        prog='packages',
        description='Query packages.yml for browsing and discovery',
    )
    parser.add_argument('--version', '-V', action='store_true', help='Show version')

    subparsers = parser.add_subparsers(dest='command')

    # sections command
    sections_parser = subparsers.add_parser('sections', help='List all sections')
    sections_parser.set_defaults(func=cmd_sections)

    # stats command
    stats_parser = subparsers.add_parser('stats', help='Show package counts')
    stats_parser.set_defaults(func=cmd_stats)

    # tags command
    tags_parser = subparsers.add_parser('tags', help='List all tags')
    tags_parser.set_defaults(func=cmd_tags)

    # show command
    show_parser = subparsers.add_parser('show', help='Show package details')
    show_parser.add_argument('name', help='Package name')
    show_parser.set_defaults(func=cmd_show)

    # search command
    search_parser = subparsers.add_parser('search', aliases=['find'], help='Search packages')
    search_parser.add_argument('query', help='Search query')
    search_parser.set_defaults(func=cmd_search)

    # list command
    list_parser = subparsers.add_parser('list', aliases=['ls'], help='List packages')
    list_parser.add_argument('--section', help='Filter by section')
    list_parser.add_argument('--tag', help='Filter by tag')
    list_parser.add_argument('--platform', choices=['macos', 'linux', 'all'], help='Filter by platform')
    list_parser.add_argument('--verbose', '-v', action='store_true', help='Show details')
    list_parser.add_argument('--json', action='store_true', help='Output as JSON')
    list_parser.set_defaults(func=cmd_list)

    # verify command
    verify_parser = subparsers.add_parser('verify', help='Check packages.yml against manifests and installer scripts')
    verify_parser.add_argument('--root', help='Override repo root (for testing with synthetic trees)')
    verify_parser.set_defaults(func=cmd_verify)

    args = parser.parse_args(argv)

    if args.version:
        # One distribution now, so one version — read from its metadata rather
        # than a literal this file used to maintain separately.
        print(f'packages {dotfiles.__version__}')
        return

    if not args.command:
        parser.print_help()
        return

    root_override = getattr(args, 'root', None)
    root_path = Path(root_override).resolve() if root_override else None
    data = load_packages(root=root_path)
    args.func(args, data)


if __name__ == '__main__':
    main()
