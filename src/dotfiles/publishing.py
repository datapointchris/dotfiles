"""What may leave this machine, and the gate that will not let anything else.

The offline loop needs one thing to travel *from* the firewalled box: what it has
installed, so a machine with a network can build it a bundle carrying only what it
lacks. `~/dev/workstations.md` § "The seam between them" records the standing
arrangement that nothing written at work travels home, and this is the one narrow
exception to it. Narrow has to be a property of the code rather than of whoever
is looking.

**Two leaks decide the shape, and both are real on that machine.**
`resources/identity.py` examines `user.name` and `user.email`, and its own
docstring records that a nonfleet box defaults to the employer identity — so
`check --json` there contains an employer address. `resources/env.py` examines
every `~/.env` key, `WINDOWS_DOMAIN` among them.

So the document is composed over an **allowlist** and never filtered down to one.
A denylist admits whatever is added next; an allowlist excludes it until somebody
decides otherwise, which is the direction a privacy boundary has to fail in.

The gate below is the second half, and it exists because an allowlist protects
against a new *resource* and not against a new *field*. It reads the bytes about
to leave and refuses on the two names that identify this box.

**The match is an unanchored substring test, and it fires on strings this machine
did not write.** The document carries a row per installed tool, and a row's
`observed` is whatever that tool printed about itself — so a hostname can arrive
inside a third-party version banner having identified nothing. That is not
hypothetical and it is not rare: on a box named `archlinux`, `syncthing
--version` reports `syncthing@archlinux`, the build host the Arch package stamps
into its own banner.

**So the gate has three answers, not two.** A row carrying one of the names is
*withheld* — it does not travel, and neither does the name. Only a name with no
row to drop refuses the document. `screened` is that, and the reasoning for
per-row rather than per-document is there.

**Which names those are is the trust coordinate's answer, and it is one answer
for the whole exchange.** Off the fleet the hostname is an employer asset tag: it
is what `written_by` deliberately reduces to a digest, and it is what a row is
withheld for carrying. On the fleet the hostname is published on purpose, in the
filename and in `written_by`, so screening rows against it would drop a row to
hide a string travelling one key over — costing the builder a tool and protecting
nothing. `identifying` is where that single decision lives. The account name is
never published anywhere, so it is on the list on every machine.

Loosening the match itself was rejected and stays rejected. Word boundaries still
match `syncthing@archlinux`, a minimum length stops protecting `mbp`, and an
escape hatch is a hole in the one boundary that must not have one. Withholding is
not a loosening — nothing carrying a name leaves under either rule, and what
changes is only how much else goes with it.
"""

from __future__ import annotations

import dataclasses as dc
import datetime as dt
import getpass
import hashlib
import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dotfiles import coordinates as axes
from dotfiles import envfile
from dotfiles import paths
from dotfiles.refusal import Refusal
from dotfiles.vocabulary import ExitCode

PUBLISHABLE = ('packages', 'toolchains')
"""The resources whose rows a bundle builder can act on, and the only ones sent.

`providers.bundle.BUNDLED_KINDS` expressed as resources: a bundle stages release
binaries, Go tools, cargo packages, winget packages and vendor install scripts,
all of which are `packages`, plus the language runtimes, which are `toolchains`.
Everything else in a walk is either unbundlable or personal, and usually both.

**A resource added later is excluded until it is named here.** That is the
allowlist doing its job rather than an oversight: the alternative reads the new
resource's rows onto a server the day it lands, and nobody reviews a diff for a
leak that a denylist silently permits.
"""


PROTOCOL_KEYS = ('machine', 'written_by')
"""Fields the exchange itself is built on, excluded from the byte scan.

`machine` is the manifest name, and `remote.statuses_for` builds the shelf
directory out of it — so a scan that read it as a leak would refuse every
document ever composed. It is a filename in this repo rather than a fact about
the box: two Macs share one, and the hostname that *would* identify a machine is
deliberately not what goes here.

Measured 2026-08-15: on a box named `archlinux` running the
`archlinux-personal-workstation` manifest, the hostname is a substring of the
shelf key, and the gate refused its own protocol.

`written_by` is `discriminator` above, which is what tells two boxes sharing a
manifest apart and is *already* the trust decision this module cares about: a
`FLEET` box publishes its hostname because the hostname is not a secret there,
and anything else publishes a blake2b digest that identifies nothing. Excluding
it here is not a hole in the boundary — it is the same boundary, decided once
where the coordinate is known rather than twice.
"""


class Unpublishable(Refusal):
    """A document that must not leave this machine, and the reason."""


PREFIX = 'dotfiles-status-v'
SUFFIX = '.json'

WRITTEN_BY = 'written_by'
"""Which box composed a document, where the composer knew.

Keyed separately from `machine`, which is the manifest and is the field two Macs
write identically. A consumer that has to tell one from the other — the sparse
bundle builder is the only one — reads this, and `published_by` is how.

Absent rather than empty where nothing supplied it. `check --json` and `plan
--json` are read on the machine that produced them and have no second box to be
confused with, so a key there would be a fact with no question behind it.
"""


def discriminator(trust: axes.NetworkTrust) -> str:
    """What tells this box apart from the others sharing its manifest.

    Two machines legitimately share one, so a filename keyed on the manifest alone
    has one overwrite the other — standards/data.md § "In a synced directory, every
    machine writes its own file".

    **The trust coordinate decides which answer**, because the constraint does. On
    the fleet the hostname is not a secret and is what a reader wants. Anything
    that is not `FLEET` gets a blake2b digest, which is the direction a privacy
    boundary has to fail in.

    A hostname carrying a hyphen also falls back, since `wrote` recovers this by
    splitting on the last one and manifest names are full of them.

    **Here rather than in `status.py`, because this is the decision `identifying`
    makes** — which name may leave this box — and the two must not disagree.
    """
    named = paths.machine_id()
    if trust is axes.NetworkTrust.FLEET and '-' not in named:
        return named
    return hashlib.blake2b(named.encode(), digest_size=4).hexdigest()


def filename(machine: str, when: dt.datetime, trust: axes.NetworkTrust) -> str:
    stamped = when.astimezone(dt.UTC).strftime('%Y%m%dT%H%M%SZ')
    return f'{PREFIX}{stamped}-{machine}-{discriminator(trust)}{SUFFIX}'


def wrote(name: str) -> str:
    """Which box published a status, from the discriminator in its own filename.

    The only thing telling apart two documents whose `machine` field is identical,
    so a reader ignoring it picks whichever published last.

    Returns a hostname or a digest without distinguishing them: a caller wants an
    identity to group on, not the kind of one it is. Empty where the name is not
    ours, which groups strangers rather than inventing an owner for each.
    """
    stem = name.removesuffix(SUFFIX)
    return stem.rsplit('-', 1)[-1] if stem.startswith(PREFIX) and '-' in stem else ''


def age_column(name: str) -> str:
    """A published artefact's age, short enough to sit in the label column.

    The label is what the eye runs down, and every row of a remote listing carried
    the word `remote` — which the heading has already said. Age is the fact that
    varies, and putting it here leaves the filename unpadded: these names run to
    eighty characters, so a listing that pads them wraps every row mid-name on a
    120-column terminal and the identity a reader is about to paste is split.
    """
    stamped = re.search(r'-v(\d{8}T\d{6}Z)-', name)
    if stamped is None:
        return 'undated'
    made = dt.datetime.strptime(stamped.group(1), '%Y%m%dT%H%M%SZ').replace(tzinfo=dt.UTC)
    since = max(dt.datetime.now(dt.UTC) - made, dt.timedelta(0))
    if since.days:
        return f'{since.days}d ago'
    return f'{since.seconds // 3600}h ago' if since.seconds >= 3600 else f'{since.seconds // 60}m ago'


def published_by(document: object, name: str = '') -> str:
    """Which box a status document came from, preferring what it says over its name.

    A file can be renamed or moved, and `--against` takes whatever path it is
    given, so the identity has to survive inside the bytes — `data.md` § "A reader
    of a shared directory selects by the key that made the writes unique".

    The name answers for a document carrying no such field.
    """
    found = document.get(WRITTEN_BY) if isinstance(document, dict) else None
    return str(found) if found else wrote(name)


def rooted(value: Any, home: str) -> Any:
    """Every absolute path under this home, rewritten the way a person types it.

    A published row's evidence is usually the path a tool was found at, which
    carries the account name the gate refuses — so a document composed without this
    refuses itself and the return leg never runs.

    Recursive over the whole document rather than a named field, because an account
    name can appear in any string a resource chose to write.
    """
    if isinstance(value, str):
        return value.replace(home, '~') if home else value
    if isinstance(value, dict):
        return {key: rooted(item, home) for key, item in value.items()}
    if isinstance(value, list):
        return [rooted(item, home) for item in value]
    return value


def placeholder(what: str) -> str:
    """What a masked name is replaced by, built from the reason it is masked.

    Derived rather than tabulated, so there is no second structure to keep in step
    with `identifying`. A leading article goes because `<the-windows-account>`
    reads worse than `<windows-account>` and carries nothing extra.
    """
    return '<' + what.lower().removeprefix('the ').replace(' ', '-') + '>'


def masked(value: Any, identities: Mapping[str, str]) -> Any:
    """Every identifying name replaced in place, keeping the shape around it.

    **Masking rather than withholding, because a run record is read by a person
    diagnosing a failure.** Dropping the line takes the command, its exit code and
    its timing with it. `screened` drops rows instead, for a document whose
    consumer is a bundle builder that can afford to lose one.

    **Case-insensitive**, because `machine_id` lowercases and Windows reports a
    hostname in upper — so a case-sensitive pass reads the asset tag straight past
    and the gate then refuses the document.

    **Longest first**, so a name containing another does not leave the shorter
    one's placeholder embedded in a half-substituted string.

    Recursive over the whole document: an account name can appear in any string a
    resource chose to write.
    """
    named = sorted(((value, placeholder(what)) for what, value in identities.items() if value), key=lambda pair: len(pair[0]), reverse=True)
    return _masking(value, named)


def _masking(value: Any, named: list[tuple[str, str]]) -> Any:
    if isinstance(value, str):
        for name, token in named:
            value = re.sub(re.escape(name), token, value, flags=re.IGNORECASE)
        return value
    if isinstance(value, dict):
        return {key: _masking(item, named) for key, item in value.items()}
    if isinstance(value, list):
        return [_masking(item, named) for item in value]
    return value


def identifying(trust: axes.NetworkTrust) -> dict[str, str]:
    """The names that must not leave, read off the machine this is running on.

    Two names and not a pattern: a general "does this look like an identifier"
    test would refuse half the package names in a document.

    **The hostname is on this list only where publishing it is not already the
    decision.** `discriminator` puts it in `written_by` on a `FLEET` box
    deliberately, so screening rows against it there withholds a row to hide a
    string the same document carries one key over. One coordinate decides both
    halves. The account name is on the list everywhere.

    Separate from `redacted` so the decision is pure and the reads sit at the edge
    — standards/python.md § "Structure effects as impure -> pure -> impure". Read
    inside the gate, it can only be tested against the machine the suite runs on.
    """
    named = {'the account this runs as': getpass.getuser()}
    if trust is axes.NetworkTrust.FLEET:
        return named
    return {
        'this machine name': paths.machine_id(),
        **named,
        'the Windows account': declared_by_hand('WINDOWS_USER'),
        'the Windows domain': declared_by_hand('WINDOWS_DOMAIN'),
    }


def declared_by_hand(name: str) -> str:
    """A value from the OVERRIDES half of `~/.env`, or empty where it is unset.

    Not derivable from the machine the way a hostname is, so it is read from where
    a person put it.

    **The environment first, then the file.** A scheduled run has no shell to have
    sourced `~/.env`, and that is exactly when nobody is watching what leaves.

    Empty on a machine declaring neither, and `redacted` skips an empty value.
    """
    if value := os.environ.get(name, '').strip():
        return value
    return envfile.read(Path.home() / '.env').get(name, '').strip()


def redacted(document: Any, identities: Mapping[str, str]) -> tuple[str, ...]:
    """Every reason this document may not be published, empty where there are none.

    **Measured against the serialized bytes, never the object.** A field added to a
    row, a path in a detail string, a hostname inside an error message — none are
    reachable by walking the shape this module expects.

    `identities` has no default, which would be the seam that hides the machine.

    Matched without regard to case: `machine_id` lowercases and Windows reports a
    hostname in upper, so the two never meet as typed.
    """
    scanned = {key: value for key, value in document.items() if key not in PROTOCOL_KEYS} if isinstance(document, dict) else document
    lowered = json.dumps(scanned).lower()
    problems = []

    scope = document.get('scope') if isinstance(document, dict) else None
    if isinstance(scope, list):
        outside = sorted(str(name) for name in scope if name not in PUBLISHABLE)
        if outside:
            problems.append(f'it covers {", ".join(outside)}, which is outside the publishable set {", ".join(PUBLISHABLE)}')

    problems.extend(f'{what} appears in it' for what, value in identities.items() if value and value.lower() in lowered)
    return tuple(problems)


ROW_KEYS = ('others', 'findings', 'examined', 'invalid')
"""Every per-item list `reconcile.ResourceResult.as_dict` emits.

All four rather than the three that carry an `observed`, because the set has to
be the emitter's rather than a guess about which lists can hold a relayed string.
Three of four fails closed — a name in the fourth refuses the document where the
same string one list over is withheld — and nothing would have said so. An
`invalid` row is a declaration fault keyed by `section`, and a builder acts on
none of them, so withholding one costs nothing a reader of this document wanted.

A row added to `as_dict` later is *not* covered until it is named here, which is
the allowlist direction and the same trade `PUBLISHABLE` makes one level up.
"""


@dc.dataclass(frozen=True, slots=True)
class Screened:
    """A document with the rows that could not travel taken out, and what remains wrong."""

    document: dict[str, Any]
    withheld: tuple[str, ...] = ()
    problems: tuple[str, ...] = ()


def screened(document: Any, identities: Mapping[str, str]) -> Screened:
    """Drop the rows carrying a name that must not leave, then judge what is left.

    **A row is the unit, because the fault is per row and refusing is not.** A tool
    relaying a name from elsewhere is what makes this necessary: syncthing's banner
    carries the host that built the Arch package, so `syncthing@archlinux` reaches
    the scan on a box named `archlinux` while identifying nothing about it.
    Refusing the whole document for that takes the return leg off the machine.

    Withholding is not a loosening: nothing carrying the name leaves either way,
    and an absent row is already meaningful — unmeasurable, so the builder carries
    the tool. The failure direction is a slightly larger bundle.

    **What cannot be withheld is still refused.** A name in the header or a
    resource's own fields has no row to drop and comes back as a problem.
    """
    if not isinstance(document, dict):
        return Screened(document, (), redacted(document, identities))

    withheld: list[str] = []
    resources = []
    for resource in document.get('resources') or ():
        if not isinstance(resource, dict):
            resources.append(resource)
            continue
        kept = dict(resource)
        for key in ROW_KEYS:
            rows = resource.get(key)
            if not isinstance(rows, list):
                continue
            # One pass, one question per row. Asking twice and inverting the second
            # is the same fact worked out from two places, and the two have to stay
            # exact opposites with nothing comparing them.
            allowed: list[Any] = []
            refused: list[Any] = []
            for row in rows:
                (refused if _names_the_machine(row, identities) else allowed).append(row)
            kept[key] = allowed
            withheld.extend(_named(row) for row in refused)
        resources.append(kept)

    remaining = {**document, 'resources': resources}
    return Screened(remaining, tuple(withheld), redacted(remaining, identities))


def _names_the_machine(row: Any, identities: Mapping[str, str]) -> bool:
    lowered = json.dumps(row).lower()
    return any(value and value.lower() in lowered for value in identities.values())


def _named(row: Any) -> str:
    """What to call a withheld row, which is the address a reader would look it up by.

    `item` on the three lists that carry one and `section` on `invalid`, which is
    keyed differently because it is a declaration fault rather than a tool.
    """
    if not isinstance(row, dict):
        return 'an unnamed row'
    return str(row.get('item') or row.get('section') or row.get('resource') or 'an unnamed row')


def publishable(document: Any, trust: axes.NetworkTrust) -> Screened:
    """The document as it may travel, or a refusal naming every reason at once.

    Called before the bytes move, per `standards/cli-design.md` § "Everything that
    can refuse runs before the first byte of data".

    **Answers the screened document rather than checking the caller's**, or a caller
    publishing the one it already held sends the rows this took out.
    """
    found = screened(document, identifying(trust))
    if found.problems:
        raise Unpublishable(
            'this document carries more than packages and versions, so it stays here:\n' + '\n'.join(found.problems),
            code=ExitCode.ISSUE,
            advice='dotfiles status show --json is what would have been sent',
        )
    return found
