"""`~/.env`: rendering it, reading it back, and writing it without losing anything.

The file tells a machine which machine it is and which features it wants running.
It used to be hand-authored, which made it the one piece of machine setup with no
source of truth: a flag added to the repo reached no existing machine, and nothing
could say which machines had drifted.

Everything above the OVERRIDES marker is generated from the manifest and
`flags.yml`; everything below it is preserved verbatim. That split is the whole
design, because a real `~/.env` also carries API tokens and machine-local values
that must never be committed and must never be lost to a regeneration.

This module renders, parses and writes. What the file *should* contain is
`machine.Machine`, and whether a machine matches it is `resources/env.py` — a
split that did not exist while this was a script with a `--check` flag.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path

from dotfiles.machine import Machine

MARKER = '# OVERRIDES - hand-edited; everything below is preserved on regenerate'

# Kept in step with flag_classify() in configs/common/.local/shell/flags.sh.
TRUTHY = {'1', 'true', 'yes', 'on'}
FALSEY = {'0', 'false', 'no', 'off'}

SELF_DEFAULT = re.compile(r'\$\{(\w+):-(.*)\}')


def assignment(name: str, value: str) -> str:
    """An export the ambient environment can still override for a single shell.

    Bare assignments clobbered it and broke `ZSHRC_DEBUG=1 zsh`, so the
    indirection is load-bearing and must not be simplified away.
    """
    return f'export {name}="${{{name}:-{value}}}"'


def render(machine: Machine) -> str:
    """Build the managed part of `~/.env`, ending with the OVERRIDES marker."""
    lines = [
        '# ================================================================',
        '# Machine Environment',
        '# ================================================================',
        f'# Generated from install/manifests/{machine.name}.yml and install/flags.yml.',
        '# Refresh with: dotfiles env apply',
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
        assignment('MACHINE', machine.name),
        assignment('PLATFORM', machine.platform_label),
        '',
        '# Features. Every declared flag is written explicitly, so a machine is never',
        '# silently running on a default it never saw.',
    ]

    for name, value in machine.flags.items():
        lines += ['', assignment(name, value)]

    # Named, never valued: this is the only place that tells you a machine needs
    # one before something quietly builds a wrong path out of the empty string.
    if values := machine.required_values:
        lines += [
            '',
            '# This machine also needs these set by hand BELOW the marker. Their values are',
            '# machine-local and deliberately not in the repo; `dotfiles check` fails until',
            '# each one is set.',
        ]
        lines += [f'#   {entry.name} - {entry.description}'.rstrip(' -') for entry in values]

    # Named for the same reason, and here rather than in a doc because a rebuild
    # reads this file: it is the only place that says where a restored overlay goes.
    if files := machine.required_files:
        lines += [
            '',
            '# This machine also expects these files, which safekeep restores rather than',
            '# `dotfiles apply` creating them. They are missing between an install and the',
            '# restore step of a rebuild, which is what `dotfiles check` reports.',
        ]
        lines += [f'#   {entry.path} - {entry.description}'.rstrip(' -') for entry in files]

    lines += ['', MARKER, '']
    return '\n'.join(lines)


def split_existing(path: Path) -> tuple[str, bool]:
    """Return the preserved override text, and whether the file predates generation.

    A file with no marker is treated as hand-written in full and preserved
    whole. Lossless by construction, which matters because the real file carries
    API tokens and passwords.
    """
    if not path.exists():
        return '', False

    text = path.read_text()
    if MARKER in text:
        return text.split(MARKER, 1)[1].lstrip('\n'), False
    return text, True


def parse_env_assignments(text: str) -> dict[str, str]:
    """Extract NAME=VALUE pairs, tolerating `export` and inline comments.

    A generated line reads `export NAME="${NAME:-value}"` so the ambient
    environment can still win, so a default naming its own variable is unwrapped
    back to the value it encodes. Only that shape is unwrapped; anything else is
    left alone.
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


def read(path: Path) -> dict[str, str]:
    """What the machine currently has set, or nothing when the file is absent."""
    return parse_env_assignments(path.read_text()) if path.exists() else {}


def write(path: Path, machine: Machine) -> bool:
    """Rewrite the generated section, preserving everything below the marker.

    Returns whether a markerless file was migrated, which is the one thing the
    caller has to say something about.
    """
    overrides, migrating = split_existing(path)
    content = render(machine)
    if overrides:
        content += overrides if overrides.endswith('\n') else overrides + '\n'

    if path.exists():
        # Built by name rather than with_suffix: pathlib treats a leading-dot
        # name as all stem, so `.env` has no suffix to append to.
        shutil.copy2(path, path.parent / (path.name + '.bak'))

    # Written to a temp file in the same directory and renamed, so an interrupted
    # write cannot leave a machine with a truncated ~/.env — which would take its
    # secrets with it.
    handle, staged = tempfile.mkstemp(dir=str(path.parent), prefix='.env.')
    try:
        with os.fdopen(handle, 'w') as target:
            target.write(content)
        os.chmod(staged, 0o600)
        os.replace(staged, path)
    except BaseException:
        Path(staged).unlink(missing_ok=True)
        raise

    return migrating
