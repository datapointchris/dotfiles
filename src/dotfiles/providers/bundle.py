"""What an offline bundle staged, read back by the providers that install from it.

`create_bundle` writes one `category|name|version|filename` row per file it puts
in the bundle, and that manifest is the agreement between the two programs. The
alternative is a convention — the bundler expanding a `binary_pattern` and the
installer globbing for whatever it produced. Globbing means increasingly loose
patterns tried against several candidate names, so a miss is indistinguishable
from a hit on the wrong tool, and either way the machine the bundle exists for
silently installs nothing.

Read here rather than in each provider so the format is spelled once. A category
is a provider's word for its own files and stays with the provider; what is
shared is only how to find the row.

**Two files, carrying disjoint facts.** `manifest.txt` says which files are here.
`bundle.json` says what this bundle *is* — when, for which machine, and whether
what it omits was measured or missed. Neither restates the other, which is why
the created-at and platform headers are not in both.

That second question is the one a sparse bundle turns on. A bundle that carries
fewer files and a bundle that failed to carry more are indistinguishable from the
rows alone, and reading the first as the second is the failure
standards/cli-design.md § "A narrowing default reads as a deletion to anything
that reconciles by sweep" measures.
"""

from __future__ import annotations

import dataclasses as dc
import json
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any

from dotfiles.providers import MANIFEST
from dotfiles.providers import staged_bundles

DOCUMENT = 'bundle.json'

VERSION = 1
"""`bundle.json`'s own schema number, independent of every other version here.

Not `status.VERSION` and not `STATE_VERSION`: three artefacts with three
lifetimes, and a shared number could not say which of them changed — the split
`status.py` already documents between the document and the state file.
"""

FIELDS = 4
"""`category|name|version|filename`. A shorter row is a comment or the header."""

CATEGORIES = ('binary', 'extra', 'go-binary', 'cargo', 'script', 'winget')
"""Every category a named tool is staged under, across every provider.

Here rather than in any one provider because a tool is a `binary` on one machine
and a `cargo` on another, and both readers of this format ask the same question
of it. `winget` earns its place from `create_bundle.add_winget_binaries`, one of
the four writers of `current` — omitted, a sparse bundle for a Windows manifest
records `winget/rg` and every lookup searches past it.
"""


class Completeness(StrEnum):
    """Whether a name absent from the manifest was measured or missed.

    The whole reason `bundle.json` exists. Under `FULL` an absent entry is a gap
    the bundler failed to fill, which is what `bundle check` reports as
    `uncovered`. Under `SPARSE` it may instead be an entry the bundler measured as
    already current on the target, and `Description.current` says which.
    """

    FULL = 'full'
    SPARSE = 'sparse'


@dc.dataclass(frozen=True, slots=True)
class Description:
    """What a bundle is, as against what it carries.

    Every field defaults, and the defaults are what an unreadable or absent
    `bundle.json` reads as. `FULL` is the conservative one of the two
    completenesses — it makes an absent entry a reported gap rather than a silent
    pass — per standards/python.md § "Dispatch over a closed vocabulary names
    every member", whose fallthrough "returns the conservative answer".
    """

    created: str = ''
    machine: str = ''
    platform: str = ''
    completeness: Completeness = Completeness.FULL
    built_from: str = ''
    built_for: str = ''
    """Which box's status the omissions were measured against, where one was.

    `machine` is the manifest and two boxes share one, so it cannot answer whether
    a sparse bundle's omissions are true here. This can, and the target is the only
    end that knows its own answer — `offline_bundle.stage` is where the comparison
    happens. Empty on a full bundle and on one built before this field existed,
    both of which stage without the question being asked.
    """
    current: Mapping[str, str] = dc.field(default_factory=dict)
    """Entries the bundler measured on the target and deliberately did not carry,
    against the upstream version it resolved for each.

    Keyed `category/name`, matching the two manifest fields that identify a row —
    one tool is a `binary` on one machine and a `cargo` on another, so the name
    alone is not an identity.

    Empty on a full bundle and meaningless there. On a sparse one, a key present
    here is `MATCHED` at its value; a key in neither this nor the manifest was
    never measured, and reporting it as current would be a guess.
    """

    version: int = VERSION

    @property
    def sparse(self) -> bool:
        return self.completeness is Completeness.SPARSE

    def as_dict(self) -> dict[str, Any]:
        return {
            'version': self.version,
            'created': self.created,
            'machine': self.machine,
            'platform': self.platform,
            'completeness': str(self.completeness),
            'built_from': self.built_from,
            'built_for': self.built_for,
            'current': dict(self.current),
        }


def description_from(document: Any) -> Description:
    """A `Description` from parsed JSON, tolerating anything that is not one.

    A bundle that cannot describe itself is still a bundle and its rows still
    install, which is the same tolerance `rows` already extends to an unreadable
    manifest. What it must not do is describe itself *wrongly*: a `completeness`
    naming something this version has never heard of falls back to `FULL`, so an
    unknown value reports gaps rather than silently passing them.
    """
    if not isinstance(document, dict):
        return Description()
    named = str(document.get('completeness', ''))
    current = document.get('current')
    return Description(
        created=str(document.get('created', '')),
        machine=str(document.get('machine', '')),
        platform=str(document.get('platform', '')),
        completeness=Completeness.SPARSE if named == Completeness.SPARSE else Completeness.FULL,
        built_from=str(document.get('built_from', '')),
        built_for=str(document.get('built_for', '')),
        current={str(key): str(value) for key, value in current.items()} if isinstance(current, dict) else {},
        version=int(document['version']) if isinstance(document.get('version'), int) else VERSION,
    )


@dc.dataclass(frozen=True, slots=True)
class Staged:
    """One file the bundle carries, as the bundler described it."""

    category: str
    name: str
    version: str
    filename: str


def rows_in(roots: tuple[Path, ...]) -> tuple[Staged, ...]:
    """Every staged file across the bundles handed in, newest bundle winning.

    Merged rather than concatenated, on `(category, name)`. That pair is the
    identity a provider looks a row up by — one tool is a `binary` on one machine
    and a `cargo` on another — and two rows for it would let a caller reading the
    first find the older version while `locate` hands back the newer file.

    Nothing at all where no bundle is staged, and an unreadable manifest is the
    same answer as an absent one. Both are already correct and already handled by
    every caller.

    Takes the walk rather than doing it, so a caller assembling several views of
    one staging directory reads it once and cannot get two answers.
    """
    merged: dict[tuple[str, str], Staged] = {}
    for root in reversed(roots):
        for row in parse(_text(root)):
            merged[row.category, row.name] = row
    return tuple(merged.values())


def rows() -> tuple[Staged, ...]:
    """The same, for a caller holding no walk of its own."""
    return rows_in(staged_bundles())


def _text(root: Path) -> str:
    """One bundle's manifest, or '' where it cannot be read."""
    try:
        return (root / MANIFEST).read_text()
    except OSError:
        return ''


def descriptions() -> tuple[Description, ...]:
    """What each staged bundle says it is, newest first.

    Every one of them rather than the newest alone, because a sparse bundle's
    `current` map explains an absence that a *different* bundle would have
    explained by carrying the file. Reading only the newest would report an entry
    the older full bundle staged as unconsidered.
    """
    return tuple(description_of(root) for root in staged_bundles())


def description_of(root: Path) -> Description:
    """What one staged bundle says it is, or the empty description where it says nothing.

    A bundle that cannot describe itself is still a bundle and its rows are what
    installs from it, which is the answer every caller already handles.
    """
    try:
        return description_from(json.loads((root / DOCUMENT).read_text()))
    except (OSError, ValueError):
        return Description()


def parse(text: str) -> tuple[Staged, ...]:
    """Every row in a manifest, from one pass over one string.

    Pure and taking the text, so a test can hand it a manifest without a bundle on
    disk and a caller merging several staged trees can read each one's own.
    """
    staged = []
    for line in text.splitlines():
        fields = line.split('|')
        if len(fields) >= FIELDS and not line.startswith('#'):
            staged.append(Staged(*fields[:FIELDS]))
    return tuple(staged)


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


def measured_in(described: tuple[Description, ...], name: str, *categories: str) -> str | None:
    """The same question as `measured`, asked of descriptions already in hand.

    Split out so a `Staging` — which carries its descriptions as a snapshot rather
    than re-reading disk — answers by the identical rule instead of its own. The
    two rules had drifted: this one matches the whole `category/name` key, and the
    copy in `offline_bundle` matched the name half alone, so they disagreed on
    exactly the tools declared under more than one category.
    """
    wanted = {f'{category}/{name}' for category in categories}
    for description in described:
        found = next((version for key, version in description.current.items() if key in wanted), None)
        if found:
            return found
    return None


def published(name: str, *categories: str) -> str | None:
    """What upstream published for a tool, from the newest bundle that answers.

    Asked per bundle rather than per kind of answer. A bundle says what upstream
    published two ways — a manifest row for what it carried, and `current` for
    what it measured and left out — and both are that one bundle's answer about
    that one moment.

    Asking every bundle's rows before any bundle's `current` orders the two by
    kind instead of by age, and the stack this feature builds is exactly where
    that goes wrong: a sparse bundle carries no row for a tool it measured, so an
    older full bundle's row survives the merge in `rows()` and wins. The machine
    is then told it is ahead of the newest release, and an offline apply repairs
    it by reinstalling the older binary the full bundle still holds.
    """
    wanted = {f'{category}/{name}' for category in categories}
    for root in staged_bundles():
        row = next((one for one in parse(_text(root)) if one.name == name and one.category in categories), None)
        if row and row.version:
            return row.version
        found = next((version for key, version in description_of(root).current.items() if key in wanted), None)
        if found:
            return found
    return None


def staged(name: str, *categories: str) -> Staged | None:
    """What the bundle holds for one tool, or None where it holds nothing.

    Categories are passed rather than searched blind: `binary` and `cargo` can
    both name `bat` — a GitHub release entry and a cargo package are different
    declarations of the same tool on different machines — and a provider asking
    for its own category is asking about the file it knows how to install.
    """
    wanted = frozenset(categories)
    return next((row for row in rows() if row.name == name and row.category in wanted), None)
