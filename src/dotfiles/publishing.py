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

`offline_bundle.BUNDLED_KINDS` expressed as resources: a bundle stages release
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

    Two machines legitimately share one manifest — `macos-personal-workstation` is
    both Macs — so a filename keyed on the manifest alone has one silently
    overwrite the other, which is the collision standards/data.md § "In a synced
    directory, every machine writes its own file" exists to make unreachable.

    **Which answer depends on the trust coordinate, because the constraint does.**
    On a fleet machine the hostname is not a secret and it is what a reader wants:
    a shelf listing says `macmini` rather than eight hex characters nobody can
    resolve. Off the fleet the hostname is an employer asset tag, so a blake2b
    digest disambiguates and identifies nothing. Anything that is not `FLEET` gets
    the digest, which is the direction a privacy boundary has to fail in.

    A hostname carrying a hyphen also falls back, because `wrote` recovers this by
    splitting on the last one and the manifest name it follows is full of them.

    **Here rather than in `status.py`, because this is the same decision
    `identifying` makes** — which name may leave this box — and the two disagreeing
    is how a row came to be withheld to hide a string published one key over. It
    also puts the naming where nothing needs `reconcile`, which is what let
    `offline_bundle` reach it without a deferred import round a cycle.
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

    The discriminator is what makes two machines sharing one manifest write two
    files instead of overwriting each other, so it is also the only thing that
    tells their documents apart afterwards. A reader that ignores it picks
    whichever published last, and the `machine` field cannot object because both
    carry the same one.

    A hostname on a fleet machine and a digest off it, and this returns whichever
    is there — the two are told apart by being read rather than by being parsed,
    since a caller wants an identity to group on and not the kind of one it is.

    Empty where the name is not one of ours, which groups strangers together
    rather than inventing an owner for each.
    """
    stem = name.removesuffix(SUFFIX)
    return stem.rsplit('-', 1)[-1] if stem.startswith(PREFIX) and '-' in stem else ''


def published_by(document: object, name: str = '') -> str:
    """Which box a status document came from, preferring what it says over its name.

    The document is authoritative and the filename is the fallback. A file can be
    renamed, moved out of the cache, or handed over by any means a person chooses,
    and `--against` takes whatever path it is given — so the identity has to
    survive inside the bytes. `data.md` § "A reader of a shared directory selects
    by the key that made the writes unique" is the rule, and it asks for the key in
    the document as well as in the name.

    The name still answers for a document published before the field existed,
    which is every one already sitting on a shelf.
    """
    found = document.get(WRITTEN_BY) if isinstance(document, dict) else None
    return str(found) if found else wrote(name)


def rooted(value: Any, home: str) -> Any:
    """Every absolute path under this home, rewritten the way a person types it.

    A published row's evidence is usually the path a tool was found at, and that
    path carries the account name — which is the thing the gate refuses. So a
    document composed without this refuses itself, and the return leg of the loop
    never runs at all.

    Recursive over the whole document rather than over a named field, because an
    account name can appear in any string a resource chose to write, and the
    field it appears in next is the one nobody thought of.

    Measured 2026-08-15: a real `status show --json` on this machine carried 28
    occurrences of the account, every one of them an absolute path in a `detail`.
    """
    if isinstance(value, str):
        return value.replace(home, '~') if home else value
    if isinstance(value, dict):
        return {key: rooted(item, home) for key, item in value.items()}
    if isinstance(value, list):
        return [rooted(item, home) for item in value]
    return value


def identifying(trust: axes.NetworkTrust) -> dict[str, str]:
    """The names that must not leave, read off the machine this is running on.

    `paths.machine_id()` is the bare hostname, which on the machine this exists
    for is an employer asset tag. `getpass.getuser()` is the work account. Two
    names and not a pattern: a general "does this look like an identifier" test
    would refuse half the package names in a document and teach whoever hit it to
    pass a flag.

    **The hostname is on this list only where publishing it is not already the
    decision.** `discriminator` puts the bare hostname in `written_by` on a
    `FLEET` box, deliberately — it is not a secret there, and a shelf listing that
    reads `macmini` rather than eight hex characters is the point. Screening rows
    against it as well withholds a row to hide a string the same document carries
    one key over: the builder loses a tool it had a version for, and the name
    ships regardless. Off the fleet the hostname is an employer asset tag,
    `written_by` is a blake2b digest, and this is the whole reason the gate exists.

    So one coordinate decides both halves. The account name is on the list
    everywhere, because nothing ever publishes it on purpose.

    Separate from `redacted` so the decision is pure and the reads sit at the edge
    — standards/python.md § "Structure effects as impure -> pure -> impure". A
    gate that read the machine inside itself can only be tested against whatever
    machine the suite runs on, which is how an assertion comes to hold at a desk
    and fail on a runner whose hostname happens to contain its username.
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

    `WINDOWS_USER` is the employer's account name and `WINDOWS_DOMAIN` the domain
    it authenticates against — the two entries `machines requirements` lists as
    set by hand, which is what makes them identifiers rather than configuration.
    They are not derivable from the machine the way a hostname is, so they are
    read from where a person put them.

    The environment first, because a run started from an interactive shell has
    `~/.env` sourced already and that is every run a person watches. The file
    second, because a scheduled run has no such shell and is exactly when nobody
    is looking at what left the box.

    Empty on a machine that declares neither, which is every fleet box. `redacted`
    skips an empty value, so this adds nothing to a document that has no Windows
    side — the coordinate does not have to be consulted twice.
    """
    if value := os.environ.get(name, '').strip():
        return value
    return envfile.read(Path.home() / '.env').get(name, '').strip()


def redacted(document: Any, identities: Mapping[str, str]) -> tuple[str, ...]:
    """Every reason this document may not be published, empty where there are none.

    Measured against the serialized bytes rather than the object, because the
    question is what would land on the server. A field added to a row, a path that
    slipped into a detail string, a hostname inside an error message — none of
    those are reachable by walking the shape this module expects, and all of them
    are reachable by looking at the text.

    `identities` has no default. Both callers already hold one, and a default here
    would be the seam that hides the machine again — the same reason the split
    above exists.

    Matched without regard to case, because the two names arrive here normalized
    and a document carries whatever the OS rendered. `machine_id` lowercases, and
    Windows reports a hostname in upper — so the literal string that made
    `connectivity-results.txt` a leak, `PF5XMXFY`, is one a case-sensitive test
    reads straight past.
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

    **A row is the unit, because the fault is per row and refusing is not.** One
    tool's version banner collided with this machine's hostname — `syncthing
    v2.1.3 ... syncthing@archlinux`, the Arch package relaying its own build host
    — and the whole document was refused for it, which took the return leg off
    this machine entirely while a hundred innocent rows were sitting in it. A row
    that cannot travel does not travel; nothing else changes.

    Withholding is not a loosening. Nothing carrying the name leaves either way,
    and the row's absence is a state the format already has a meaning for: a tool
    in neither the manifest nor `current` is unmeasurable, so the builder carries
    it rather than assuming it is current. The failure direction is a slightly
    larger bundle.

    **What cannot be withheld is still refused.** A name outside these lists — in
    the header, in a resource's own fields — has no row to drop and comes back as
    a problem, which is the whole document refused exactly as before.

    A tool relaying a name it got from elsewhere is what makes this necessary:
    syncthing's version banner carries the host that built the Arch package, so
    `syncthing@archlinux` reaches the scan on a box named `archlinux` while
    identifying nothing about it.
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

    Called before the bytes move rather than after, so a refusal never leaves half
    an artefact on a server — `standards/cli-design.md` § "Everything that can
    refuse runs before the first byte of data", applied to a remote instead of to
    stdout.

    Answers the screened document rather than checking the caller's, because a
    caller that published the one it already held would send the rows this just
    took out. There is no arrangement of two calls that cannot get that wrong,
    which is why there is one.
    """
    found = screened(document, identifying(trust))
    if found.problems:
        raise Unpublishable(
            'this document carries more than packages and versions, so it stays here:\n' + '\n'.join(found.problems),
            code=ExitCode.ISSUE,
            advice='dotfiles status show --json is what would have been sent',
        )
    return found
