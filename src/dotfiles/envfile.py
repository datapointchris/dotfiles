"""`~/.env`: rendering it, reading it back, and writing it without losing anything.

The file tells a machine which machine it is and which features it wants running.
Hand-authoring it leaves the one piece of machine setup with no source of truth:
a flag added to the repo reaches no existing machine, and nothing can say which
machines have drifted.

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

from dotfiles import settings
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


def coordinate_exports(machine: Machine) -> dict[str, str]:
    """The coordinate variables `~/.env` carries, and what they should say.

    One function for both halves: `render` writes these and `resources/env.py`
    checks a machine against them, so the file `apply` produces and the file
    `check` demands cannot disagree about a name or a spelling.

    **Empty, and that is the design.** A shell needs no coordinate to know what
    to load: `symlinks apply` deploys only the directories this machine's
    coordinates select and prunes the rest, so `~/.local/shell/` *is* the
    resolved answer and a glob over it reads that answer directly. Shipping the
    list as well made `~/.env` a second copy of a fact the filesystem already
    held, free to disagree with it — and it did, naming six directories where one
    existed.

    Kept as a function rather than deleted because the seam is the point: a
    coordinate value a shell genuinely cannot derive from what is on disk lands
    here, and `render` and `check` pick it up together.
    """
    return {}


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
        '# wins for one shell: `ZSHRC_DEBUG=1 zsh` and `MACHINE=other ./install.sh`',
        '# both have to keep working without editing this file.',
        '',
        '# Identity. MACHINE selects the manifest and is read by install.sh before',
        '# anything else, so this file is also the install bootstrap.',
        assignment('MACHINE', machine.name),
    ]

    lines += [assignment(name, value) for name, value in coordinate_exports(machine).items()]

    lines += [
        '',
        '# Features. Every declared flag is written explicitly, so a machine is never',
        '# silently running on a default it never saw.',
    ]

    for name, value in machine.flags.items():
        lines += ['', assignment(name, value)]

    # A required value the trust-scoped config answers is exported here, so a
    # consumer that reads the environment finds it without anyone editing this
    # file. The rest are named and not valued, because nothing but the machine
    # knows them and an empty string would build a wrong path silently.
    if values := machine.required_values:
        resolved = settings.resolve_all([entry.name for entry in values], settings.read_config())
        answered = [(entry, found) for entry in values if (found := resolved.of(entry.name))]
        unanswered = [entry for entry in values if not resolved.of(entry.name)]

        if answered:
            lines += [
                '',
                "# Supplied by this tool's own config, and exported so anything reading the",
                '# environment finds the same file. `dotfiles config show` says which rung',
                '# answered; a value already set below the marker still wins.',
            ]
            for entry, found in answered:
                lines += ['']
                if entry.description:
                    lines += [f'# {entry.description}']
                lines += [assignment(entry.name, found.value)]

        if unanswered:
            lines += [
                '',
                '# This machine also needs these set by hand BELOW the marker. Their values are',
                '# machine-local and deliberately not in the repo; `dotfiles check` fails until',
                '# each one is set.',
            ]
            lines += [f'#   {entry.name} - {entry.description}'.rstrip(' -') for entry in unanswered]

    # Named for the same reason, and here rather than in a doc because a rebuild
    # reads this file: it is the only place that says where a restored file goes.
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


def read_generated(path: Path) -> dict[str, str]:
    """Only what the generated section sets, ignoring everything below the marker.

    The half a regeneration owns, and so the only half a value can be *compared*
    against. A hand-edited assignment below the marker is later in the file, and
    both the shell and `parse_env_assignments` take the last one — so it wins at
    runtime, and rewriting the section above it would not change what the machine
    reads. Comparing the whole file would report that intentional override as
    drift on every run and `apply` would answer with a write that converged
    nothing.

    Empty for a markerless file, which `split_existing` treats as hand-written in
    full: none of it was generated, so there is nothing here to hold to the
    declaration.
    """
    if not path.exists():
        return {}
    text = path.read_text()
    return parse_env_assignments(text.split(MARKER, 1)[0]) if MARKER in text else {}


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
