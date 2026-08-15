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


class Unpublishable(Refusal):
    """A document that must not leave this machine, and the reason."""


def redacted(document: Any) -> tuple[str, ...]:
    """Every reason this document may not be published, empty where there are none.

    Measured against the serialized bytes rather than the object, because the
    question is what would land on the server. A field added to a row, a path that
    slipped into a detail string, a hostname inside an error message — none of
    those are reachable by walking the shape this module expects, and all of them
    are reachable by looking at the text.

    Two names and not a pattern. `paths.machine_id()` is the bare hostname, which
    on the machine this exists for is an employer asset tag, and
    `getpass.getuser()` is the work account. A general "does this look like an
    identifier" test would refuse half the package names in the document and teach
    whoever hit it to pass a flag.
    """
    text = json.dumps(document)
    problems = []

    scope = document.get('scope') if isinstance(document, dict) else None
    if isinstance(scope, list):
        outside = sorted(str(name) for name in scope if name not in PUBLISHABLE)
        if outside:
            problems.append(f'it covers {", ".join(outside)}, which is outside the publishable set {", ".join(PUBLISHABLE)}')

    for what, value in (('this machine name', paths.machine_id()), ('the account this runs as', getpass.getuser())):
        if value and value in text:
            problems.append(f'{what} appears in it')

    return tuple(problems)


def refuse_unpublishable(document: Any) -> None:
    """Raise where a document may not be published, naming every reason at once.

    Called before the bytes move rather than after, so a refusal never leaves half
    an artefact on a server — `standards/cli-design.md` § "Everything that can
    refuse runs before the first byte of data", applied to a remote instead of to
    stdout.
    """
    problems = redacted(document)
    if problems:
        raise Unpublishable(
            'this document carries more than packages and versions, so it stays here:\n' + '\n'.join(problems),
            code=ExitCode.ISSUE,
            advice='dotfiles status show --json is what would have been sent',
        )
