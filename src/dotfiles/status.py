"""What a `check` leaves behind for something that is not watching it.

`status-<box>.json` is the state — every resource's verdict, its counts, and when
it was measured — for a caller that wants to reason about the machine without
running a check of its own.

**The state file is not the `--json` document, and the difference is who asked.**
`document` below is composed for one run because a caller asked for it, and that
caller keeps it — so it carries every item behind every count, which is what makes
it worth handing to a machine that can reach the network. This file is written by
every check, wanted by nobody in particular, and lands in `$XDG_STATE_HOME`, which
is a Syncthing folder for the fleet. Written as the document it was 127 KB against
2.8 KB for the same walk, several times a day, on every box.

Written by every `check`, not only the scheduled one, so an interactive check
refreshes what a later reader sees.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Sequence

from dotfiles import paths
from dotfiles import publishing
from dotfiles import reconcile
from dotfiles import remote as transport
from dotfiles import vocabulary
from dotfiles.output import hint
from dotfiles.output import warn
from dotfiles.reconcile import ResourceResult


def on_remote(where: transport.Remote, machine: str) -> tuple[str, ...]:
    """Every status on a machine's shelf, newest first.

    Here rather than in the command that lists them, because three callers resolve
    the same set and one of them is `bundle create --against latest`. A second
    listing written there would be a second place this naming convention is known.

    Mirrors `offline_bundle.on_remote`, which answers the same question about the
    other shelf. Both return nothing where the shelf has never been created, and
    both let a transport failure travel — `remote.listed` is where that split is
    decided and why it is not a boolean.
    """
    directory = transport.statuses_for(where, machine)
    listed = transport.listed(where, directory)
    if listed is None:
        return ()
    named = (name for name in listed if name.startswith(publishing.PREFIX) and name.endswith(publishing.SUFFIX))
    return tuple(sorted(named, reverse=True))


def record(results: Sequence[ResourceResult], machine: str, when: dt.datetime) -> bool:
    """Write the state file, and say when the state directory would not take it.

    The state directory is on Syncthing for the fleet and absent on a fresh
    machine, and neither is a reason for `dotfiles check` to exit non-zero — it
    answered the question it was asked. Degrading is right here; degrading
    silently is not. An unwritable directory is indistinguishable from a
    successful write to everything downstream, so a reader asking where this
    machine stands would get an answer from whenever the last write landed and
    nothing saying it was stale.

    Returns whether it recorded. The warning goes to stderr so it cannot corrupt
    a `--json` run, which is also why the answer is a value rather than the
    warning being the only trace.
    """
    try:
        paths.STATE_HOME.mkdir(parents=True, exist_ok=True)
        paths.STATUS_FILE.write_text(json.dumps(state(results, machine, when), indent=2) + '\n')
    except OSError as unwritable:
        warn(f'could not record this check under {paths.STATE_HOME}: {unwritable}')
        hint(f'{paths.STATUS_FILE.name} is now out of date — check the directory permissions and free space')
        return False
    return True


STATE_VERSION = 1
"""Which generation of the status *file* this is.

Its own number because it is its own artifact. The two were one while `record`
wrote what `document` composed, and that is precisely how the file came to carry
the rows: a bump made for the interchange document reached a file that had no
reader for them. A shared number cannot say that one of two shapes moved, which
is the whole job a version has.

Still 1, and honestly so — this file holds exactly what it held before the
document grew rows, so anything already reading one keeps working. `runs.SCHEMA`
is the same arrangement for the run record: one artifact, one number, moved when
that artifact changes and never because a neighbour did.
"""

VERSION = 2
"""Which generation of the interchange document this is.

**2 carries the rows; 1 carried only the counts per resource.** Additive per row,
and additive is not the test. The test is whether a consumer can *state* which
generation it needs, and a bundle builder that reads `findings` needs 2 — under 1
it would have to infer the answer from whether a key is present, decide what an
absent one means, and get "this machine found nothing" for a machine that named
twelve missing tools. Inferring a generation from the keys in front of you is the
unversioned failure this number exists to end, not a substitute for it.

The same bump covers the resource-scoped doors. That half is not additive at all:
a resource's `--json` answers an object keyed on `resources`, not on `pending`.
"""


def document(
    results: Sequence[ResourceResult],
    machine: str,
    when: dt.datetime,
    verb: str = 'check',
    written_by: str = '',
    measured_against: str = '',
) -> dict[str, object]:
    """The versioned interchange document, from every read door.

    Versioned because it crosses machines: an unversioned document breaks silently
    when the two ends disagree about its shape. `VERSION` says what each generation
    holds.

    `verb` names which question produced it — `plan` and `check` measure the same
    machine and keep different findings, and the bundle builder wants the plan's.

    **`measured_against` names the staged bundle every version here was compared
    to, and is empty where the walk asked upstream.** Always a key rather than one
    that appears offline, for the reason `scope` is: inferring a generation from
    which keys are present is what the version exists to end. A document read off
    the shelf otherwise cannot say whether its figures came from GitHub or from a
    fortnight-old tarball, and those are different claims about the same machine.
    Additive, so `VERSION` does not move.

    **`scope` names which resources it covers, and a reader has to honour it.** One
    shape comes from three widths, so without it a consumer diffing this against a
    declaration reads "not mentioned" as "this machine has nothing for it" —
    `standards/cli-design.md` § "A narrowing default reads as a deletion to
    anything that reconciles by sweep". Additive, so `VERSION` does not move.

    **One shape for one resource and for nine.** A bare row for a single result
    makes a consumer branch on a count it did not choose: `--source` reaching a
    runtime through `needed_by` silently makes the walk two resources wide.
    """
    composed: dict[str, object] = {
        'version': VERSION,
        'verb': verb,
        'machine': machine,
        'checked': when.isoformat(),
        'scope': sorted({vocabulary.parse_address(result.address)[0] for result in results}),
        'verdict': _worst(results),
        'measured_against': measured_against,
        'resources': [result.as_dict() for result in results],
    }
    if written_by:
        composed[publishing.WRITTEN_BY] = written_by
    return composed


def state(results: Sequence[ResourceResult], machine: str, when: dt.datetime) -> dict[str, object]:
    """What `status.json` holds: every resource's verdict, its counts, and the time.

    The same header as `document` and `as_counts` in place of `as_dict`, which is
    the whole difference. Both cross machines and both are versioned; what they
    are not is one artifact, and writing the document here made every scheduled
    check push 127 KB into a Syncthing folder to answer a question — is this
    machine converged — that 2.8 KB answers.

    A caller wanting the items asks for them: `dotfiles check --json > wherever`
    is the composed-on-request half, and it is the same walk through a door that
    knows somebody is holding the result. `standards/cli-design.md` § "A fact on
    screen is reachable through some machine door" is satisfied by that door and
    asks nothing of this file.

    `verb` is here and constant, because only `check` writes this file — kept so
    the file says what produced it rather than leaving a reader to infer it from
    the filename.
    """
    return {
        'version': STATE_VERSION,
        'verb': 'check',
        'machine': machine,
        'checked': when.isoformat(),
        'verdict': _worst(results),
        'resources': [result.as_counts() for result in results],
    }


def _worst(results: Sequence[ResourceResult]) -> str:
    return str(reconcile.worst(results))
