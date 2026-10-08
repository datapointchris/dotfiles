"""A deployed file whose source ends in `.tmpl`, written with this machine's values in it.

Everything else this repo deploys is the same bytes on every machine that
selects it, so a link carries it. A file naming something only the machine
knows — a server on its own network — cannot be a link without the repo
carrying the value, and the repo is public. Where the program reading the file
takes the value from its environment or from an included file, the value goes
there and the file stays a link. A template is for a program that reads one file
in every process that starts it, including the ones that never sourced a shell
profile.

A placeholder's value is a `required:` entry in `install/flags.yml`, answered
below the OVERRIDES marker in `~/.env`. That entry is what makes `dotfiles check`
name an unset value. Rendering never writes a file with a placeholder left
unfilled: an unset value is a finding, and the target stays as it was.

`string.Template` syntax: `${NAME}` or `$NAME` is a placeholder and `$$` is a
literal dollar sign. The rendered file is written at mode 600, because its
values come from the file that holds this machine's secrets.
"""

from __future__ import annotations

import dataclasses as dc
import os
import re
import string
import tempfile
from collections.abc import Mapping
from pathlib import Path

SUFFIX = '.tmpl'

MODE = 0o600


def is_template(path: Path) -> bool:
    return path.suffix == SUFFIX


def deployed_as(relative: Path) -> Path:
    """Where a source file lands, relative to its tree's destination."""
    return relative.with_suffix('') if is_template(relative) else relative


@dc.dataclass(frozen=True, slots=True)
class Rendering:
    """A template's text with this machine's values in it, or the names that stopped it."""

    text: str
    unset: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return not self.unset


def placeholders(source: Path) -> tuple[str, ...]:
    return tuple(string.Template(source.read_text()).get_identifiers())


def malformed(source: Path) -> str:
    """Why the template cannot be filled whatever the values, empty when it can.

    A `$` followed by neither a name, a brace nor a second `$` is the case.
    `substitute` raises on it, so the declaration check reports it before any
    machine renders.
    """
    template = string.Template(source.read_text())
    if template.is_valid():
        return ''
    return 'a $ that is neither a placeholder nor escaped as $$'


def render(source: Path, values: Mapping[str, str]) -> Rendering:
    """The file this machine should hold, or every placeholder nothing answered.

    An empty value counts as unset. An empty address renders a config that parses
    and points nowhere, which is the silent failure the register exists to make
    loud.
    """
    template = string.Template(source.read_text())
    unset = tuple(name for name in template.get_identifiers() if not values.get(name))
    if unset:
        return Rendering('', unset)
    return Rendering(template.substitute({name: values[name] for name in template.get_identifiers()}))


def is_rendering_of(source: Path, text: str) -> bool:
    """Whether the text is this template filled in with any values at all.

    A rendered file is a regular file, so this is what tells this manager's output
    from somebody's file: the template's literal text, with each placeholder
    matching anything on one line. A rendering made with an earlier value matches,
    and a file anyone wrote or edited does not.
    """
    pieces: list[str] = []
    end = 0
    template_text = source.read_text()
    for found in string.Template.pattern.finditer(template_text):
        pieces.append(re.escape(template_text[end : found.start()]))
        if found.group('escaped') is not None:
            pieces.append(re.escape('$'))
        elif found.group('invalid') is not None:
            raise ValueError(malformed(source))
        else:
            pieces.append(r'[^\n]*')
        end = found.end()
    pieces.append(re.escape(template_text[end:]))
    return re.fullmatch(''.join(pieces), text) is not None


def write(target: Path, text: str) -> None:
    """Replace the target with this text in one rename, at `MODE`.

    The rename replaces a symlink at the target rather than writing through it.
    A link left from deploying the file by link points into the repo, and
    writing through it would overwrite the template.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, staged = tempfile.mkstemp(dir=str(target.parent), prefix=f'.{target.name}.')
    try:
        with os.fdopen(handle, 'w') as staging:
            staging.write(text)
        os.chmod(staged, MODE)
        os.replace(staged, target)
    except BaseException:
        Path(staged).unlink(missing_ok=True)
        raise
