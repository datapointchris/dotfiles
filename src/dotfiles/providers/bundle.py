"""What an offline bundle staged, read back by the providers that install from it.

`create_bundle` writes one `category|name|version|filename` row per file it puts
in the bundle, and that manifest is the agreement between the two programs. The
alternative is a convention — the bundler expanding a `binary_pattern` and the
installer globbing for whatever it produced — which is what `cargo-tools.sh` did:
four increasingly loose patterns tried against two candidate names, so a miss was
indistinguishable from a hit on the wrong tool, and either way the machine the
bundle exists for silently installed nothing.

Read here rather than in each provider so the format is spelled once. A category
is a provider's word for its own files and stays with the provider; what is
shared is only how to find the row.
"""

from __future__ import annotations

import dataclasses as dc
import re

from dotfiles.providers import bundle_file

MANIFEST = 'manifest.txt'

FIELDS = 4
"""`category|name|version|filename`. A shorter row is a comment or the header."""


@dc.dataclass(frozen=True, slots=True)
class Staged:
    """One file the bundle carries, as the bundler described it."""

    category: str
    name: str
    version: str
    filename: str


def rows() -> tuple[Staged, ...]:
    """Every staged file, or nothing at all where there is no bundle.

    An unreadable manifest is the same answer as an absent one — no bundle —
    because that answer is already correct and already handled by every caller.
    """
    return _parse(_text())[1]


def _text() -> str:
    """The manifest, or '' where there is none. One reader, so the header and the
    rows are read from the same bytes rather than from two opens that can disagree."""
    try:
        return bundle_file(MANIFEST).read_text()
    except OSError:
        return ''


HEADER_FIELD = re.compile(r'^#\s*(Created|Platform):\s*(.+)$')
"""The two header lines `create_bundle` writes that describe the bundle itself.

Read rather than ignored because they answer the question a person asks first of a
bundle they did not build: when, and for what. Every other `#` line is prose or the
format legend, so this matches the two by name instead of counting lines — a
bundler that adds a third comment must not shift what the second one means."""


def described() -> tuple[str, str]:
    """When this bundle was built and for which platform, from its own header.

    Empty strings where there is no bundle or the header does not say, which is the
    same answer every caller already handles: a bundle that cannot describe itself is
    still a bundle, and its rows are what installs from it.
    """
    return _parse(_text())[0]


def _parse(text: str) -> tuple[tuple[str, str], tuple[Staged, ...]]:
    """The header pair and every row, from one pass over one string.

    Pure and taking the text, so both public readers above are one call each and a
    test can hand it a manifest without a bundle on disk.
    """
    built, platform, staged = '', '', []
    for line in text.splitlines():
        if found := HEADER_FIELD.match(line):
            key, value = found.group(1), found.group(2).strip()
            built, platform = (value, platform) if key == 'Created' else (built, value)
            continue
        fields = line.split('|')
        if len(fields) >= FIELDS and not line.startswith('#'):
            staged.append(Staged(*fields[:FIELDS]))
    return (built, platform), tuple(staged)


def counted(carried: tuple[Staged, ...]) -> dict[str, int]:
    """How many files the bundle carries per category, in category order.

    A count per category rather than a total, because the total answers nothing a
    person asks: a bundle with 60 wheels and no binaries and one with 40 binaries are
    both "61 files", and only the first is useless for installing tools.
    """
    tally: dict[str, int] = {}
    for row in carried:
        tally[row.category] = tally.get(row.category, 0) + 1
    return {category: tally[category] for category in sorted(tally)}


def staged(name: str, *categories: str) -> Staged | None:
    """What the bundle holds for one tool, or None where it holds nothing.

    Categories are passed rather than searched blind: `binary` and `cargo` can
    both name `bat` — a GitHub release entry and a cargo package are different
    declarations of the same tool on different machines — and a provider asking
    for its own category is asking about the file it knows how to install.
    """
    wanted = frozenset(categories)
    return next((row for row in rows() if row.name == name and row.category in wanted), None)
