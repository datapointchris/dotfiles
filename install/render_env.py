#!/usr/bin/env python3
"""Render ~/.env from a machine manifest and the declared flag list.

~/.env is what tells a machine which machine it is, which OS it runs, and which
features it wants running. It used to be hand-authored, which made it the one
piece of machine setup with no source of truth: a flag added to the repo
reached no existing machine, and nothing could tell you which machines had
drifted.

The file is generated from install/manifests/<machine>.yml (identity) and
install/flags.yml (features), with everything below the OVERRIDES marker
preserved verbatim. That split matters because a real ~/.env also carries
secrets and machine-local values that must never be checked in and must never
be lost to a regeneration.

Usage:
    render_env.py --machine NAME --sync     # write/refresh ~/.env
    render_env.py --machine NAME --check    # report drift, write nothing
    render_env.py --machine NAME            # print the generated section
"""

import argparse
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

MARKER = '# OVERRIDES - hand-edited; everything below is preserved on regenerate'

# Kept in step with flag_classify() in configs/common/.local/shell/flags.sh.
TRUTHY = {'1', 'true', 'yes', 'on'}
FALSEY = {'0', 'false', 'no', 'off'}

SELF_DEFAULT = re.compile(r'\$\{(\w+):-(.*)\}')

INSTALL_DIR = Path(__file__).resolve().parent


def load_yaml(path):
    if not path.exists():
        sys.exit(f'Error: {path} not found')
    with open(path) as f:
        return yaml.safe_load(f) or {}


def load_flags():
    """Return the declared flags as a list of dicts."""
    return load_yaml(INSTALL_DIR / 'flags.yml').get('flags', [])


def load_required():
    """Return the declared machine-local values as a list of dicts."""
    return load_yaml(INSTALL_DIR / 'flags.yml').get('required', [])


def load_required_files():
    """Return the declared machine-local files as a list of dicts."""
    return load_yaml(INSTALL_DIR / 'flags.yml').get('required_files', [])


def _applies_to(entry, manifest):
    """Whether a declaration narrows to this machine.

    An entry narrows by platform and/or machine; one that names neither applies
    everywhere.
    """
    machine = manifest.get('machine')
    platform = manifest.get('platform')
    return entry.get('platform', platform) == platform and entry.get('machine', machine) == machine


def applicable_required(manifest, required):
    """The required values that apply to this machine."""
    return [entry for entry in required if _applies_to(entry, manifest)]


def applicable_required_files(manifest, required_files):
    """The machine-local files that apply to this machine."""
    return [entry for entry in required_files if _applies_to(entry, manifest)]


def load_manifest(machine):
    return load_yaml(INSTALL_DIR / 'manifests' / f'{machine}.yml')


def as_env_value(value):
    """Render a YAML scalar the way the shell should read it."""
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return str(value)


def resolve_flag_values(manifest, flags):
    """Each flag's value for this machine: the manifest's override, else the default."""
    overrides = manifest.get('flags') or {}
    return [
        (flag['name'], as_env_value(overrides.get(flag['name'], flag.get('default', True))), flag.get('description', '')) for flag in flags
    ]


def assignment(name, value):
    """An export the ambient environment can still override for a single shell."""
    return f'export {name}="${{{name}:-{value}}}"'


def render_generated_section(manifest, flags, required=None, required_files=None):
    """Build the managed part of ~/.env, ending with the OVERRIDES marker."""
    required = load_required() if required is None else required
    required_files = load_required_files() if required_files is None else required_files
    machine = manifest.get('machine', '')
    lines = [
        '# ================================================================',
        '# Machine Environment',
        '# ================================================================',
        f'# Generated from install/manifests/{machine}.yml and install/flags.yml.',
        '# Refresh with: dotfiles env sync',
        '#',
        '# Everything above the OVERRIDES marker is regenerated and will be',
        '# overwritten. Put secrets and machine-local values below it.',
        '',
        '# Every value is written as ${NAME:-...} so the ambient environment still',
        '# wins for one shell: `ZSHRC_DEBUG=1 zsh` and `PLATFORM=wsl ./install.sh`',
        '# both have to keep working without editing this file.',
        '',
        '# Identity. MACHINE selects the manifest and is read by install.sh before',
        '# anything else, so this file is also the install bootstrap.',
        assignment('MACHINE', machine),
        assignment('PLATFORM', manifest.get('platform', '')),
        '',
        '# Features. Every declared flag is written explicitly, so a machine is never',
        '# silently running on a default it never saw.',
    ]

    for name, value, description in resolve_flag_values(manifest, flags):
        lines.append('')
        if description:
            lines.append(f'# {description}')
        lines.append(assignment(name, value))

    # Named, never valued: this is the only place that tells you a machine needs
    # one before something quietly builds a wrong path out of the empty string.
    needed = applicable_required(manifest, required)
    if needed:
        lines += [
            '',
            '# This machine also needs these set by hand BELOW the marker. Their values are',
            '# machine-local and deliberately not in the repo; `dotfiles doctor` fails until',
            '# each one is set.',
        ]
        lines += [f'#   {entry["name"]} - {entry.get("description", "")}'.rstrip(' -') for entry in needed]

    # Named for the same reason, and here rather than in a doc because a rebuild
    # reads this file: it is the only place that says where a restored overlay goes.
    needed_files = applicable_required_files(manifest, required_files)
    if needed_files:
        lines += [
            '',
            '# This machine also expects these files, which safekeep restores rather than',
            '# `dotfiles install` creating them. They are missing between an install and the',
            '# restore step of a rebuild, which is what `dotfiles doctor` reports.',
        ]
        lines += [f'#   {entry["path"]} - {entry.get("description", "")}'.rstrip(' -') for entry in needed_files]

    lines += ['', MARKER, '']
    return '\n'.join(lines)


def split_existing(path):
    """Return the preserved override text from an existing ~/.env.

    A file with no marker predates generation, so all of it is treated as
    hand-written and preserved. That is lossless by construction, which matters
    because the real file carries API tokens and passwords.
    """
    if not path.exists():
        return '', False

    text = path.read_text()
    if MARKER in text:
        return text.split(MARKER, 1)[1].lstrip('\n'), False
    return text, True


def parse_env_assignments(text):
    """Extract NAME=VALUE pairs, tolerating `export` and inline comments.

    A generated line reads `export NAME="${NAME:-value}"` so the ambient
    environment can still win, so the self-referencing default is unwrapped back
    to the value it encodes. Only a default naming its own variable is unwrapped;
    anything else is left alone.
    """
    values = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        line = line.removeprefix('export ').strip()
        if '=' not in line:
            continue
        name, _, value = line.partition('=')
        name = name.strip()
        value = value.strip().strip('\'"')
        match = SELF_DEFAULT.fullmatch(value)
        if match and match.group(1) == name:
            value = match.group(2)
        values[name] = value
    return values


def check(path, manifest, flags, required=None, required_files=None):
    """Report drift between the declared flags and what the machine actually has."""
    required = load_required() if required is None else required
    required_files = load_required_files() if required_files is None else required_files
    problems = []

    if not path.exists():
        print(f'✗ {path} does not exist — run `dotfiles env sync`')
        return 1

    present = parse_env_assignments(path.read_text())

    for key, expected in (
        ('MACHINE', manifest.get('machine')),
        ('PLATFORM', manifest.get('platform')),
    ):
        actual = present.get(key)
        if actual is None:
            problems.append(f'{key} is missing (manifest declares {expected})')
        elif actual != str(expected):
            problems.append(f'{key} is {actual!r}, manifest declares {expected!r}')

    declared = {flag['name'] for flag in flags}
    for name, expected, _ in resolve_flag_values(manifest, flags):
        actual = present.get(name)
        if actual is None:
            problems.append(f'{name} is declared but missing (would be {expected})')
        elif actual.lower() not in TRUTHY | FALSEY:
            problems.append(f'{name} is {actual!r}, which is neither truthy nor falsey')

    # Machine-local values the repo knows are needed but must never hold. Unset,
    # they expand to the empty string and quietly build a wrong path at the point
    # of use rather than failing anywhere you would look.
    for entry in applicable_required(manifest, required):
        if not present.get(entry['name']):
            problems.append(f'{entry["name"]} must be set below the marker — {entry.get("description", "machine-local value")}')

    # Shell code the repo declares and never contains. Reported rather than
    # created: the remedy is a safekeep restore, so this is expected to be red on
    # a machine that has been installed but not yet restored.
    for entry in applicable_required_files(manifest, required_files):
        if not Path(entry['path']).expanduser().exists():
            problems.append(f'{entry["path"]} is missing — restore it with safekeep ({entry.get("description", "machine-local file")})')

    # Flags the shell no longer knows about. Not fatal — a machine may carry a
    # flag from a newer commit — but it is exactly how NVIM_AI_ENABLED survived
    # being read by nothing, so it is worth naming.
    for name in present:
        if name.endswith(('_ENABLED', '_DEBUG')) and name not in declared:
            problems.append(f'{name} is set but not declared in flags.yml')

    if problems:
        print(f'✗ {len(problems)} problem(s) in {path}:')
        for problem in problems:
            print(f'  - {problem}')
        return 1

    print(f'✓ {path} matches {manifest.get("machine")} ({len(flags)} flags declared)')
    return 0


def sync(path, manifest, flags, required=None):
    """Rewrite the generated section, preserving everything below the marker."""
    overrides, migrating = split_existing(path)
    content = render_generated_section(manifest, flags, required)
    if overrides:
        content += overrides if overrides.endswith('\n') else overrides + '\n'

    if path.exists():
        # Built by name rather than with_suffix: pathlib treats a leading-dot
        # name as all stem, so `.env` has no suffix to append to.
        backup = path.parent / (path.name + '.bak')
        shutil.copy2(path, backup)
        print(f'  Backed up: {backup}')

    # Written to a temp file in the same directory and renamed, so an
    # interrupted write cannot leave a machine with a truncated ~/.env — which
    # would take its secrets with it.
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix='.env.')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise

    print(f'  Wrote: {path}')
    if migrating:
        print('  No marker found — the whole previous file was preserved as overrides.')
        print('  Prune any lines it now duplicates above the marker.')
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--machine', required=True, help='Machine manifest name')
    parser.add_argument('--env-file', default=str(Path.home() / '.env'), help='Target file (default: ~/.env)')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--sync', action='store_true', help='Write the file')
    mode.add_argument('--check', action='store_true', help='Report drift without writing')
    args = parser.parse_args()

    manifest = load_manifest(args.machine)
    flags = load_flags()
    path = Path(args.env_file)

    if args.check:
        return check(path, manifest, flags)
    if args.sync:
        return sync(path, manifest, flags)

    print(render_generated_section(manifest, flags), end='')
    return 0


if __name__ == '__main__':
    sys.exit(main())
