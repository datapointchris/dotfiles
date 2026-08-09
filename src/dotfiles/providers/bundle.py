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
    try:
        lines = (bundle_file(MANIFEST)).read_text().splitlines()
    except OSError:
        return ()

    staged = []
    for line in lines:
        fields = line.split('|')
        if len(fields) >= FIELDS and not line.startswith('#'):
            staged.append(Staged(*fields[:FIELDS]))
    return tuple(staged)


def staged(name: str, *categories: str) -> Staged | None:
    """What the bundle holds for one tool, or None where it holds nothing.

    Categories are passed rather than searched blind: `binary` and `cargo` can
    both name `bat` — a GitHub release entry and a cargo package are different
    declarations of the same tool on different machines — and a provider asking
    for its own category is asking about the file it knows how to install.
    """
    wanted = frozenset(categories)
    return next((row for row in rows() if row.name == name and row.category in wanted), None)
