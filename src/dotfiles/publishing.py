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
"""

from __future__ import annotations

import getpass
import json
from collections.abc import Mapping
from typing import Any

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


PROTOCOL_KEYS = ('machine',)
"""Fields the exchange itself is built on, excluded from the byte scan.

`machine` is the manifest name, and `remote.statuses_for` builds the shelf
directory out of it — so a scan that read it as a leak would refuse every
document ever composed. It is a filename in this repo rather than a fact about
the box: two Macs share one, and the hostname that *would* identify a machine is
deliberately not what goes here.

Measured 2026-08-15: on a box named `archlinux` running the
`archlinux-personal-workstation` manifest, the hostname is a substring of the
shelf key, and the gate refused its own protocol.
"""


class Unpublishable(Refusal):
    """A document that must not leave this machine, and the reason."""


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


def identifying() -> dict[str, str]:
    """The names that must not leave, read off the machine this is running on.

    `paths.machine_id()` is the bare hostname, which on the machine this exists
    for is an employer asset tag. `getpass.getuser()` is the work account. Two
    names and not a pattern: a general "does this look like an identifier" test
    would refuse half the package names in a document and teach whoever hit it to
    pass a flag.

    Separate from `redacted` so the decision is pure and the reads sit at the edge
    — standards/python.md § "Structure effects as impure -> pure -> impure". A
    gate that read the machine inside itself can only be tested against whatever
    machine the suite runs on, which is how an assertion comes to hold at a desk
    and fail on a runner whose hostname happens to contain its username.
    """
    return {'this machine name': paths.machine_id(), 'the account this runs as': getpass.getuser()}


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


def refuse_unpublishable(document: Any) -> None:
    """Raise where a document may not be published, naming every reason at once.

    Called before the bytes move rather than after, so a refusal never leaves half
    an artefact on a server — `standards/cli-design.md` § "Everything that can
    refuse runs before the first byte of data", applied to a remote instead of to
    stdout.
    """
    problems = redacted(document, identifying())
    if problems:
        raise Unpublishable(
            'this document carries more than packages and versions, so it stays here:\n' + '\n'.join(problems),
            code=ExitCode.ISSUE,
            advice='dotfiles status show --json is what would have been sent',
        )
