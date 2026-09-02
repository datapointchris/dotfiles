"""The closed vocabulary and the address grammar, in one place so they can be asserted.

Both are surfaces a caller binds to. A verb appearing on one subcommand and not
another, or an address spelled one way in `--skip` and another in the run record,
is a break for every script and shell completion built on it — and neither shows
up as a test failure unless something asserts the whole set at once. That is what
this module exists for: `tests/cli/test_conformance.py` walks the built app and
checks every command name against `VERBS`, so adding a verb means editing this
file deliberately rather than discovering it later.
"""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    """What a caller branches on. See `cli-design.md` § Machine contract.

    Three exists to stop `check` reporting "a checker crashed" as "no drift".
    Without it a caller reads a converged machine whose checker could not run as
    converged, and has no way to tell the two apart.
    """

    CONVERGED = 0
    DRIFT = 1
    USAGE = 2
    ISSUE = 3


CORE_VERBS = ('plan', 'check', 'apply', 'list', 'show', 'search')
"""The vocabulary proper: what a resource does, spelled the same way everywhere.

`plan` and `check` ask different questions of one measurement — *what would apply
change* and *is anything wrong* — and one verb answering both is what made a
scheduled unit sit permanently failed on a machine whose only fault was a package
being a version behind. `apply` is `plan` and then execute, so the three are a
Terraform-shaped trio rather than three unrelated words.
"""

EXCEPTION_VERBS: dict[str, str] = {
    'unlink': 'symlinks: the inverse of apply, and it has no other spelling',
    'create': 'bundle: builds an artefact rather than reconciling a machine',
    'stage': 'bundle: unpacks a bundle without installing from it',
    'edit': 'machines, repo: opens $EDITOR, which is not a read or a write of state',
    'requirements': 'machines: the register supplied by hand, which show prints in passing and no other verb can name alone',
    'prune': 'bundle: removes a staged artefact, not drift. Run records are never pruned',
    'upload': 'bundle, status: sends an artefact to the remote. A direction, not a synonym for download',
    'download': 'bundle, status: fetches one from the remote. The pair ifiles already spells, and both ends spell it the same',
    'latest': 'report: the common read, worth one word rather than `show $(… list)`',
    'path': 'report, repo: prints a path for a pipeline, e.g. `ifiles upload "$(dotfiles report path)"`',
    'stats': 'report: an aggregate across runs, which `show` on one run cannot be',
    'update': 'self-update, as everywhere in the fleet — here the checkout is the installation',
}
"""Each exception carries the reason it is not one of the five, so the next reader
does not have to reconstruct it — and so a new one has to be argued for in writing."""

VERBS = frozenset(CORE_VERBS) | frozenset(EXCEPTION_VERBS)


NOUNS = frozenset(
    {
        'packages',
        'toolchains',
        'plugins',
        'symlinks',
        'env',
        'system',
        'identity',
        'auth',
        'credentials',
        'machines',
        'config',
        'report',
        'logs',
        'network',
        'bundle',
        'remote',
        'status',
        'repo',
    }
)
"""Every subcommand group. A group is a thing; only its leaves are verbs.

Asserted alongside `VERBS` so that a new group is as deliberate as a new verb —
the grammar is `dotfiles <noun> <verb>`, and both halves are closed.
"""

RESOURCES = ('packages', 'toolchains', 'plugins', 'symlinks', 'env', 'system', 'identity', 'auth', 'credentials')
"""Every addressable part of the machine, in the order rows are measured and printed.

**Not the convergence order, and it cannot be.** Ordering *work* is
`plan.Stage`, because the chain interleaves these names: toolchains → packages
→ toolchains → packages → plugins → symlinks → plugins → system. No sequence of
resource names expresses that, so a walk sorts on the stage and this tuple
decides only who is asked first and whose row prints above whose.

`auth` and `credentials` are last because both can only be asked once every other
has had its say: a login is a question about a tool that is already installed,
and a credential helper is a question about a git configuration that is already
deployed. `credentials` follows `auth` because it is the narrower of the two —
`auth` covers whatever the manifest declares, while this one covers only what the
include chain happened to resolve to.

A dependency stated here would therefore be a dependency nothing enforces, which
is worse than none: it reads as a guarantee.
"""

ADDRESS_SEPARATOR = '/'
"""`plugins/tpm`, not `plugins:tpm` or `plugins.tpm`.

An address is `(resource, provider)` rather than `resource`, because
`plugins/shell-plugin` and `plugins/tpm` sit on opposite sides of `symlinks` in
the ordering. The separator has to survive being a shell word, a JSON string and
a `--skip` argument, and `/` is the one that reads as a path to everyone already.

Validating one is `engine.validate`, not here: the provider half is the registry's
to know, and this module is what the registry's resource names are checked
*against*.
"""


def address(resource: str, source: str | None = None) -> str:
    """Build the one string that `plan` prints, `--skip` takes, and the run record stores."""
    return f'{resource}{ADDRESS_SEPARATOR}{source}' if source else resource


def parse_address(value: str) -> tuple[str, str | None]:
    """Split an address into its resource and optional provider."""
    resource, separator, source = value.partition(ADDRESS_SEPARATOR)
    return resource, source if separator else None
