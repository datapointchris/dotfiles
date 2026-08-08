"""
Parse packages.yml and output package lists for installation.

Reached as a module, never as a path, because it imports its siblings — and
under whichever interpreter the caller has: `$DOTFILES_PYTHON` for a shell
installer, `uv run` otherwise. Never the system python, which is the one
interpreter that will not have this package's dependencies.

Usage:
    python -m dotfiles.parse_packages --type=system --manager=apt
    python -m dotfiles.parse_packages --type=cargo
    python -m dotfiles.parse_packages --type=npm
    python -m dotfiles.parse_packages --type=uv
    python -m dotfiles.parse_packages --type=git_uv
    python -m dotfiles.parse_packages --type=go
    python -m dotfiles.parse_packages --type=mas
    python -m dotfiles.parse_packages --type=github
    python -m dotfiles.parse_packages --type=custom
    python -m dotfiles.parse_packages --type=custom --filter=bundle_install_script
    python -m dotfiles.parse_packages --type=flatpak
    python -m dotfiles.parse_packages --type=macos-casks
    python -m dotfiles.parse_packages --taps
    python -m dotfiles.parse_packages --get=runtimes.node.version
    python -m dotfiles.parse_packages --custom-installer=terraform-ls --field=repo

Owner-filtered usage (drives `update.sh --mine`):
    python -m dotfiles.parse_packages --type=github --owner=datapointchris
    python -m dotfiles.parse_packages --type=go --owner=datapointchris --format=name_package

Manifest-filtered usage:
    python -m dotfiles.parse_packages --type=go --manifest=wsl-work-workstation
    python -m dotfiles.parse_packages --manifest-field=platform --manifest=archlinux-personal-workstation
    python -m dotfiles.parse_packages --manifest-field=go_tools --manifest=wsl-work-workstation
"""

import argparse
import sys
from pathlib import Path

import yaml

from dotfiles import paths


def get_packages_file():
    """The catalog this repo declares, or exit saying where it looked."""
    packages_file = paths.PACKAGES_FILE
    if not packages_file.exists():
        print(f'Error: packages.yml not found at {packages_file}', file=sys.stderr)
        sys.exit(1)
    return packages_file


def load_packages():
    """Load and parse packages.yml."""
    packages_file = get_packages_file()
    with open(packages_file) as f:
        return yaml.safe_load(f)


def get_manifest_file(machine_name):
    """The named machine's manifest, or exit saying where it looked."""
    manifest_file = paths.MANIFESTS_DIR / f'{machine_name}.yml'
    if not manifest_file.exists():
        print(f'Error: manifest not found at {manifest_file}', file=sys.stderr)
        sys.exit(1)
    return manifest_file


def load_manifest(machine_name):
    """Load and parse a machine manifest."""
    manifest_file = get_manifest_file(machine_name)
    with open(manifest_file) as f:
        return yaml.safe_load(f)


# Sections whose entries each put one executable on PATH. system_packages is not
# among them: apt/brew package names map to binaries too loosely to verify this way.
# npm_globals and uv_tools nest their entries under group keys, hence the flag.
VERIFIABLE_SECTIONS = (
    ('go_tools', False),
    ('github_releases', False),
    ('custom_installers', False),
    ('cargo_packages', False),
    ('git_uv_tools', False),
    ('npm_globals', True),
    ('uv_tools', True),
)


def entry_command(entry):
    """The executable an entry installs.

    `command` is the declared override for a package whose binary is named
    differently (ripgrep ships rg, @taplo/cli ships taplo). neovim instead
    declares the full symlink it creates, so the name comes off the end of it.
    Everything else installs a binary matching its own name.
    """
    if entry.get('command'):
        return entry['command']
    if entry.get('binary_link'):
        return Path(entry['binary_link']).name
    return entry['name']


def verifiable_commands(data, manifest):
    """Rows of `section|kind|value|name` for everything this manifest should install.

    This is what keeps the verification honest: the checks are the manifest, so a
    tool that is removed stops being checked and a tool that is added starts being
    checked, with no list to update. Hand-maintained lists kept asserting `menu`
    and `theme-sync` for months after both were deleted.

    `kind` is `command` for a binary on PATH and `path` for an entry that declares
    `installed_path` — a sourced library like bashselfupdate puts nothing on PATH,
    and the checkout is the only evidence it installed.

    `name` is carried alongside because it is the package name where that differs
    from the binary (fd-find ships fd, git-delta ships delta), which is what the
    duplicate detector needs to recognise the same tool installed via apt or brew.
    """
    rows = []
    for section, is_grouped in VERIFIABLE_SECTIONS:
        declared = manifest.get(section)
        if not declared:
            continue

        available = data.get(section) or ([] if not is_grouped else {})
        if is_grouped:
            entries = [entry for group in available.values() for entry in group]
        else:
            entries = [entry for entry in available if isinstance(entry, dict)]

        wanted = None if declared is True else set(declared)
        for entry in entries:
            if wanted is not None and entry['name'] not in wanted:
                continue
            if entry.get('library_only'):
                continue
            if entry.get('installed_path'):
                kind = 'path'
                value = entry['installed_path']
            else:
                kind = 'command'
                if entry.get('requires_wsl_host'):
                    kind = 'command_wsl_host'
                elif entry.get('requires_github_auth'):
                    kind = 'command_github_auth'
                value = entry_command(entry)
            rows.append(f'{section}|{kind}|{value}|{entry["name"]}')
    return rows


def filter_go_packages_by_manifest(data, manifest, output_format='packages'):
    """Filter go packages to only those named in the manifest."""
    manifest_tools = manifest.get('go_tools', [])
    if manifest_tools is True:
        return get_go_packages(data, output_format)
    if not manifest_tools:
        return []
    all_tools = data.get('go_tools', [])
    filtered = [pkg for pkg in all_tools if pkg['name'] in manifest_tools]
    if output_format == 'name_package':
        return [f'{pkg["name"]}|{pkg["package"]}' for pkg in filtered]
    elif output_format == 'binary_info':
        return [
            f'{pkg["name"]}|{pkg["github_repo"]}|{pkg["binary_pattern"]}'
            for pkg in filtered
            if 'github_repo' in pkg and 'binary_pattern' in pkg
        ]
    return [pkg['package'] for pkg in filtered]


def filter_github_releases_by_manifest(data, manifest):
    """Filter github release names to only those in the manifest."""
    manifest_releases = manifest.get('github_releases', [])
    if manifest_releases is True:
        return get_github_packages(data)
    if not manifest_releases:
        return []
    all_binaries = data.get('github_releases', [])
    return [pkg['name'] for pkg in all_binaries if pkg['name'] in manifest_releases]


def names_requiring_github_auth(data, section):
    """Names in one section whose repo is private, so installing needs credentials.

    Read off the declaration rather than listed anywhere, because which repos are
    private is a fact about GitHub that changes without anything here changing.
    """
    return {entry['name'] for entry in data.get(section) or [] if isinstance(entry, dict) and entry.get('requires_github_auth')}


def filter_git_uv_packages_by_manifest(data, manifest):
    """Filter git uv packages to only those named in the manifest."""
    manifest_tools = manifest.get('git_uv_tools', [])
    if manifest_tools is True:
        return get_git_uv_packages(data)
    if not manifest_tools:
        return []
    all_tools = data.get('git_uv_tools', [])
    return [format_git_uv_package(pkg) for pkg in all_tools if pkg['name'] in manifest_tools]


def filter_npm_packages_by_manifest(data, manifest):
    """Filter npm globals to only those named in the manifest."""
    manifest_tools = manifest.get('npm_globals', [])
    if manifest_tools is True:
        return get_npm_packages(data)
    if not manifest_tools:
        return []
    all_tools = []
    for category in data.get('npm_globals', {}).values():
        if isinstance(category, list):
            all_tools.extend(category)
    return [pkg['name'] for pkg in all_tools if pkg['name'] in manifest_tools]


def filter_uv_packages_by_manifest(data, manifest):
    """Filter uv tools to only those named in the manifest."""
    manifest_tools = manifest.get('uv_tools', [])
    if manifest_tools is True:
        return get_uv_packages(data)
    if not manifest_tools:
        return []
    all_tools = []
    for category in data.get('uv_tools', {}).values():
        if isinstance(category, list):
            all_tools.extend(category)
    return [pkg['name'] for pkg in all_tools if pkg['name'] in manifest_tools]


def filter_custom_installers_by_manifest(data, manifest, filter_field=None):
    """Filter custom installer names to only those listed in the manifest.

    If filter_field is set, also require the installer to have that field truthy
    (e.g. bundle_install_script: true). Manifest field == True means 'all'.
    """
    manifest_installers = manifest.get('custom_installers', [])
    all_installers = data.get('custom_installers', [])
    if manifest_installers is True:
        candidates = all_installers
    elif not manifest_installers:
        return []
    else:
        candidates = [i for i in all_installers if i['name'] in manifest_installers]
    if filter_field:
        candidates = [i for i in candidates if i.get(filter_field)]
    return [i['name'] for i in candidates]


def cargo_binary_info_rows(packages):
    """Rows the offline bundler downloads from: command|repo|pattern|linux_target|darwin_target.

    The two target fields override the Rust target triple {target} expands to, for tools
    whose release assets are not named after it (fnm ships fnm-linux.zip, fnm-macos.zip).
    """
    rows = []
    for pkg in packages:
        if 'github_repo' in pkg and 'binary_pattern' in pkg:
            cmd = pkg.get('command', pkg['name'])
            rows.append(f'{cmd}|{pkg["github_repo"]}|{pkg["binary_pattern"]}|{pkg.get("linux_target", "")}|{pkg.get("darwin_target", "")}')
    return rows


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
        return [f'{pkg["name"]}|{pkg.get("command", pkg["name"])}' for pkg in filtered]
    elif output_format == 'github_repos':
        return [f'{pkg.get("command", pkg["name"])}|{pkg["github_repo"]}' for pkg in filtered if 'github_repo' in pkg]
    elif output_format == 'binary_info':
        return cargo_binary_info_rows(filtered)
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


def get_system_packages(data, manager, tier='workstation'):
    """Extract system packages for a package manager, filtered by tier.

    The tier lives on each entry in the single `system_packages` list (one
    source of truth — no parallel core/workstation lists to drift):

      - tier: core   Base tools every machine gets, including minimal LXC
                     servers and small boxes. Must be tagged explicitly.
      - untagged     Workstation-only extras (the default). Kept off servers
                     so a heavy new package can never silently bloat them.

    A 'core' request returns only core-tagged packages; a 'workstation'
    request returns everything, since core is a subset of workstation.
    """
    if 'system_packages' not in data:
        return []

    packages = []
    for pkg in data['system_packages']:
        if manager not in pkg:
            continue
        if tier == 'core' and pkg.get('tier') != 'core':
            continue
        packages.append(pkg[manager])
    return packages


def get_cargo_packages(data, output_format='names'):
    """Extract cargo package information.

    Args:
        output_format: 'names' returns just names,
                      'name_command' returns 'name|command' pairs,
                      'github_repos' returns 'command|github_repo' for offline bundling,
                      'binary_info' returns the offline bundling row (see cargo_binary_info_rows)
    """
    if 'cargo_packages' not in data:
        return []

    if output_format == 'name_command':
        return [f'{pkg["name"]}|{pkg.get("command", pkg["name"])}' for pkg in data['cargo_packages']]
    elif output_format == 'github_repos':
        return [f'{pkg.get("command", pkg["name"])}|{pkg["github_repo"]}' for pkg in data['cargo_packages'] if 'github_repo' in pkg]
    elif output_format == 'binary_info':
        return cargo_binary_info_rows(data['cargo_packages'])
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


def format_git_uv_package(pkg):
    """Format one git uv tool as 'name|repo|ref_mode|auth'.

    Pipe-delimited because a clone URL contains colons. The ref mode decides how
    the tool is installed: 'release' pins the newest release tag, 'branch'
    follows the default branch for a repo that publishes no releases. See
    install/common/lib/uv-git-tools.sh for why the pin matters. `auth` is 'auth'
    for a private repo, whose clone needs credentials a container has none of.
    """
    ref_mode = 'branch' if pkg.get('tracks_branch') else 'release'
    auth = 'auth' if pkg.get('requires_github_auth') else 'open'
    return f'{pkg["name"]}|{pkg["repo"]}|{ref_mode}|{auth}'


def get_git_uv_packages(data):
    """Extract git uv tool name|repo|ref_mode|auth rows."""
    if 'git_uv_tools' not in data:
        return []
    return [format_git_uv_package(pkg) for pkg in data['git_uv_tools']]


def get_go_packages(data, output_format='packages'):
    """Extract go tool package paths.

    Args:
        output_format: 'packages' returns just package paths,
                      'name_package' returns 'name|package' pairs,
                      'binary_info' returns 'name|github_repo|binary_pattern' for offline bundling
    """
    if 'go_tools' not in data:
        return []
    if output_format == 'name_package':
        return [f'{pkg["name"]}|{pkg["package"]}' for pkg in data['go_tools']]
    elif output_format == 'binary_info':
        return [
            f'{pkg["name"]}|{pkg["github_repo"]}|{pkg["binary_pattern"]}'
            for pkg in data['go_tools']
            if 'github_repo' in pkg and 'binary_pattern' in pkg
        ]
    return [pkg['package'] for pkg in data['go_tools']]


def get_mas_apps(data):
    """Extract Mac App Store app IDs."""
    if 'mas_apps' not in data:
        return []
    return [str(pkg['id']) for pkg in data['mas_apps']]


def get_github_packages(data):
    """Extract GitHub release package names."""
    if 'github_releases' not in data:
        return []
    return [pkg['name'] for pkg in data['github_releases']]


def get_shell_plugins(data, output_format='names'):
    """Extract shell plugins.

    Args:
        output_format: 'names' returns just names, 'name_repo' returns 'name|repo' pairs
    """
    if 'shell_plugins' not in data:
        return []

    if output_format == 'name_repo':
        return [f'{pkg["name"]}|{pkg["repo"]}' for pkg in data['shell_plugins']]
    else:  # names
        return [pkg['name'] for pkg in data['shell_plugins']]


def get_github_release_field(data, name, field):
    """Get a field from a specific GitHub release by name."""
    if 'github_releases' not in data:
        return None

    for binary in data['github_releases']:
        if binary.get('name') == name:
            return binary.get(field)
    return None


def get_custom_installers(data, filter_field=None):
    """Extract custom installer names.

    Args:
        filter_field: if set, only return installers where filter_field is truthy
                      (e.g., 'bundle_install_script' for offline bundle inclusion).
    """
    if 'custom_installers' not in data:
        return []
    installers = data['custom_installers']
    if filter_field:
        return [i['name'] for i in installers if i.get(filter_field)]
    return [i['name'] for i in installers]


def print_custom_installer_sources(name: str) -> None:
    """Every host one custom installer reaches, for the offline connectivity probe.

    The URLs are code — `providers/custom.py` — so this is a window onto them
    rather than a second answer. It replaced a `case` on `source_type` that could
    say "a github_clone needs github.com" and nothing more: it could not express
    that `theme` also fetches its script from raw.githubusercontent.com, that
    `bats` needs three repos, or that `awscli` names a different zip per
    architecture.

    Imported here rather than at module scope: this module is loaded by shell
    scripts on every install for questions that have nothing to do with providers,
    and importing one drags in the catalog and coordinates behind it.
    """
    from dotfiles import catalog
    from dotfiles import coordinates
    from dotfiles.providers import custom

    entry = catalog.load().find('custom_installers', name)
    if not isinstance(entry, catalog.CustomInstaller):
        print(f'Error: no custom_installers entry named {name!r}', file=sys.stderr)
        sys.exit(1)

    target = coordinates.Target(coordinates.detect().os_family, coordinates.detect_arch())
    for source in custom.sources(entry, target):
        print(f'{source.reach}|{source.url}')


def get_custom_installer_field(data, name, field):
    """Get a field from a specific custom installer by name."""
    if 'custom_installers' not in data:
        return None
    for installer in data['custom_installers']:
        if installer.get('name') == name:
            return installer.get(field)
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


def extract_owner(entry):
    """Resolve the GitHub owner of a packages.yml entry, or None if it has none.

    Sections disagree on which field carries the owner and in what shape: `repo`
    is either `owner/name` (github_releases, custom_installers) or a clone URL
    (git_uv_tools), and `package` is a Go import path. Entries sourced from a
    registry rather than GitHub — npm, PyPI, apt/brew/pacman — have no owner and
    correctly match nothing.
    """
    for field in ('repo', 'github_repo', 'package'):
        value = entry.get(field)
        if not isinstance(value, str):
            continue
        path = value.split('://', 1)[-1].removesuffix('.git').strip('/')
        segments = [segment for segment in path.split('/') if segment]
        # A leading host (github.com) is only present in the URL and Go-import forms
        if segments and '.' in segments[0]:
            segments = segments[1:]
        if segments:
            return segments[0]
    return None


def filter_packages_by_owner(data, owner):
    """Prune every section to entries owned by `owner`.

    Applied to the loaded data before dispatch so all existing getters, output
    formats, and manifest filters compose with it unchanged.
    """

    def matching(entries):
        return [entry for entry in entries if isinstance(entry, dict) and extract_owner(entry) == owner]

    filtered = {}
    for key, value in data.items():
        if isinstance(value, list):
            filtered[key] = matching(value)
        elif isinstance(value, dict):
            # uv_tools and npm_globals nest their lists one level deeper, under categories
            filtered[key] = {category: matching(entries) for category, entries in value.items() if isinstance(entries, list)}
        else:
            filtered[key] = value
    return filtered


class QueryError(Exception):
    """A query that cannot be answered as asked. main() renders it as exit 1."""


def select_packages(data, manifest, args):
    """Everything --type resolves to: declaration in, lines out, no I/O.

    Separate from main() because both callers that matter need it without the
    printing — the parity harness, which answers hundreds of queries against one
    load of packages.yml, and every future caller that wants a value rather than
    a subprocess and a text stream to re-parse.
    """
    if args.owner:
        data = filter_packages_by_owner(data, args.owner)

    if args.type == 'system':
        if not args.manager:
            raise QueryError('--manager required for system packages')
        return get_system_packages(data, args.manager, args.tier)
    if args.type == 'cargo':
        output_format = args.format or 'names'
        if manifest:
            return filter_cargo_packages_by_manifest(data, manifest, output_format)
        return get_cargo_packages(data, output_format)
    if args.type == 'npm':
        return filter_npm_packages_by_manifest(data, manifest) if manifest else get_npm_packages(data)
    if args.type == 'uv':
        return filter_uv_packages_by_manifest(data, manifest) if manifest else get_uv_packages(data)
    if args.type == 'git_uv':
        return filter_git_uv_packages_by_manifest(data, manifest) if manifest else get_git_uv_packages(data)
    if args.type == 'go':
        output_format = args.format if args.format in ('packages', 'name_package', 'binary_info') else 'packages'
        if manifest:
            return filter_go_packages_by_manifest(data, manifest, output_format)
        return get_go_packages(data, output_format)
    if args.type == 'mas':
        return get_mas_apps(data)
    if args.type == 'github':
        return filter_github_releases_by_manifest(data, manifest) if manifest else get_github_packages(data)
    if args.type == 'custom':
        if manifest:
            return filter_custom_installers_by_manifest(data, manifest, filter_field=args.filter)
        return get_custom_installers(data, filter_field=args.filter)
    if args.type == 'shell-plugins':
        return get_shell_plugins(data, args.format)
    if args.type == 'flatpak':
        return get_flatpak_apps(data)
    if args.type == 'macos-casks':
        return get_macos_casks(data)
    return []


# Named rather than inlined into build_parser so a caller enumerating the query
# space reads the same list argparse validates against.
PACKAGE_TYPES = ['system', 'cargo', 'npm', 'uv', 'git_uv', 'go', 'mas', 'github', 'custom', 'shell-plugins', 'flatpak', 'macos-casks']
SYSTEM_TIERS = ['core', 'workstation']
PACKAGE_MANAGERS = ['apt', 'pacman', 'brew', 'aur']
OUTPUT_FORMATS = ['names', 'name_repo', 'name_command', 'name_package', 'packages', 'full', 'github_repos', 'binary_info']


def build_parser():
    parser = argparse.ArgumentParser(description='Parse packages.yml')
    parser.add_argument(
        '--type',
        choices=PACKAGE_TYPES,
        help='Type of packages to extract',
    )
    parser.add_argument(
        '--tier',
        choices=SYSTEM_TIERS,
        default='workstation',
        help='System-package tier: core (minimal base for servers) or workstation (everything). Default workstation.',
    )
    parser.add_argument('--manager', choices=PACKAGE_MANAGERS, help='Package manager for system packages')
    parser.add_argument('--get', help='Get a specific value using dot notation (e.g., runtimes.node.version)')
    parser.add_argument('--taps', action='store_true', help='Get macOS Homebrew taps')
    parser.add_argument('--github-release', help='Name of GitHub release (e.g., neovim)')
    parser.add_argument('--custom-installer', help='Name of custom installer (e.g., terraform-ls)')
    parser.add_argument('--sources', help='Every host one custom installer reaches, as reach|url lines')
    parser.add_argument('--field', help='Field to extract from --github-release or --custom-installer (e.g., repo, url)')
    parser.add_argument(
        '--optional',
        action='store_true',
        help='With --field: an absent field prints nothing and exits 0, so a caller can tell it apart from a failed lookup',
    )
    parser.add_argument(
        '--filter', help='With --type=custom: only include installers where this field is truthy (e.g., bundle_install_script)'
    )
    parser.add_argument(
        '--format',
        choices=OUTPUT_FORMATS,
        default='names',
        help=(
            'Output format: names, name|repo pairs (shell-plugins), name|command pairs (cargo), '
            'name|package pairs (go), github_repos/binary_info (cargo/go for offline)'
        ),
    )
    parser.add_argument('--owner', help='Only include packages owned by this GitHub owner (e.g., datapointchris)')
    parser.add_argument('--manifest', help='Machine manifest name (e.g., wsl-work-workstation) to filter packages')
    parser.add_argument('--manifest-field', help='Extract a field from the manifest (e.g., platform, go_tools)')
    parser.add_argument(
        '--verify-commands',
        action='store_true',
        help='With --manifest: emit section|command for every executable the manifest should install',
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # Handle manifest-field extraction (no packages.yml needed)
    if args.manifest_field:
        if not args.manifest:
            print('Error: --manifest required with --manifest-field', file=sys.stderr)
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
            print('true' if value else 'false')
        else:
            print(value)
        return

    data = load_packages()
    manifest = load_manifest(args.manifest) if args.manifest else None

    if args.verify_commands:
        if not manifest:
            print('Error: --manifest required with --verify-commands', file=sys.stderr)
            sys.exit(1)
        for row in verifiable_commands(data, manifest):
            print(row)
        return

    if args.taps:
        taps = get_macos_taps(data)
        for tap in taps:
            print(tap)
        return

    if args.github_release:
        if not args.field:
            print('Error: --field required with --github-release', file=sys.stderr)
            sys.exit(1)
        value = get_github_release_field(data, args.github_release, args.field)
        if value is not None:
            print(value)
        elif not args.optional:
            print(f'Error: {args.github_release}.{args.field} not found', file=sys.stderr)
            sys.exit(1)
        return

    if args.sources:
        print_custom_installer_sources(args.sources)
        return

    if args.custom_installer:
        if not args.field:
            print('Error: --field required with --custom-installer', file=sys.stderr)
            sys.exit(1)
        value = get_custom_installer_field(data, args.custom_installer, args.field)
        if value is not None:
            print(value)
        elif not args.optional:
            print(f'Error: {args.custom_installer}.{args.field} not found', file=sys.stderr)
            sys.exit(1)
        return

    if args.get:
        value = get_value(data, args.get)
        print(value)
        return

    if not args.type:
        parser.print_help()
        sys.exit(1)

    try:
        packages = select_packages(data, manifest, args)
    except QueryError as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(1)

    for pkg in packages:
        print(pkg)


if __name__ == '__main__':
    main()
