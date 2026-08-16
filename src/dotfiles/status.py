"""What a `check` leaves behind for something that is not watching it.

Two files, and the split is the whole design. `status.json` is the state — every
resource's verdict, its counts, and when it was measured — for a caller that
wants to reason about the machine. `nudge` is one line of human text, present
only when there is something a person should act on.

Two rather than one because of who reads them. The nudge is read by a **shell
snippet at every prompt**, and JSON parsing in zsh means `jq`, which means a
subprocess per shell — the exact cost `.zshrc`'s completion caching exists to
avoid. A one-line file is `$(<file)`, which zsh reads with no fork at all.

**The state file is not the `--json` document, and the difference is who asked.**
`document` below is composed for one run because a caller asked for it, and that
caller keeps it — so it carries every item behind every count, which is what makes
it worth handing to a machine that can reach the network. This file is written by
every check, wanted by nobody in particular, and lands in `$XDG_STATE_HOME`, which
is a Syncthing folder for the fleet. Written as the document it was 127 KB against
2.8 KB for the same walk, several times a day, on every box.

**It fires on Issues, not on drift.** Drift is the normal state of a machine
between applies; nudging about it every prompt would train the nudge away inside
a week. An Issue is something wrong — a checker that could not run, a declaration
that will not parse — and those are rare enough to be worth interrupting for.

Written by every `check`, not only the scheduled one, so an interactive check
also refreshes what the next shell reports. That is what stops the nudge
outliving the problem it describes.
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
from dotfiles.reconcile import ResourceVerdict


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
    """Write both files, and say when the state directory would not take them.

    The state directory is on Syncthing for the fleet and absent on a fresh
    machine, and neither is a reason for `dotfiles check` to exit non-zero — it
    answered the question it was asked. Degrading is right here; degrading
    silently is not. An unwritable directory is indistinguishable from a
    successful write to everything downstream, and what it produces is a prompt
    nudge that never fires again — which reads as a converged machine.

    Not atomic across the two, and it does not claim to be: a directory that
    refuses the first write refuses both, which is the failure this actually
    meets, but a status file written and a nudge that then fails leaves the
    status on disk beside a nudge that is one run out of date. Bounded rather
    than repaired, because the shell stops reading a nudge older than
    `MAX_AGE_SECONDS` anyway.

    Returns whether it recorded. The warning goes to stderr so it cannot corrupt
    a `--json` run, which is also why the answer is a value rather than the
    warning being the only trace.
    """
    try:
        paths.STATE_HOME.mkdir(parents=True, exist_ok=True)
        paths.STATUS_FILE.write_text(json.dumps(state(results, machine, when), indent=2) + '\n')
        _write_nudge(results)
    except OSError as unwritable:
        warn(f'could not record this check under {paths.STATE_HOME}: {unwritable}')
        hint(f'no shell will nudge until {paths.STATE_HOME} takes a write — check its permissions and free space')
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
    results: Sequence[ResourceResult], machine: str, when: dt.datetime, verb: str = 'check', written_by: str = ''
) -> dict[str, object]:
    """The versioned interchange document, from every read door.

    Versioned because it crosses machines: the work box's output is what decides
    what the fleet builds into its next offline bundle, and an unversioned
    document breaks silently when the two ends disagree about its shape. What each
    generation holds, and why this one is 2, is `VERSION`'s own.

    `verb` names which question produced it. `plan` and `check` measure the same
    machine and keep different findings, so two documents of one shape would
    otherwise be indistinguishable — and the bundle builder wants the plan's rows
    rather than the check's.

    **`scope` names which resources it covers, and a reader has to honour it.**
    One shape now comes from three widths: every resource from `check`, one from a
    resource-scoped door, and the publishable subset from `status show`. Without
    it, a consumer diffing this against a declaration reads "the resources this
    document does not mention" as "resources this machine has nothing for" —
    which is the sweep-as-deletion failure `standards/cli-design.md` § "A
    narrowing default reads as a deletion to anything that reconciles by sweep"
    measures. Additive, so `VERSION` does not move: a reader that ignores it is
    exactly as correct as it was, which was correct for the one width that
    existed.

    **One shape for one resource and for nine.** The resource-scoped verbs emitted
    a bare row for a single result and an array for several, on the argument that a
    reader tells those apart on the first byte. It can, and having to is the defect:
    a consumer of `packages plan --json` branches on a count it did not choose,
    because `--source` reaching a runtime through `needed_by` silently makes the
    walk two resources wide, and a two-resource walk then dropped a row through the
    door that takes an object. `standards/cli-design.md` § "A fact on screen is
    reachable through some machine door" states the property — one run reads
    identically through either door — and § "Two front doors on one dataset spell
    everything identically" is why a second spelling has nothing to distinguish.
    """
    composed: dict[str, object] = {
        'version': VERSION,
        'verb': verb,
        'machine': machine,
        'checked': when.isoformat(),
        'scope': sorted({vocabulary.parse_address(result.address)[0] for result in results}),
        'verdict': _worst(results),
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


def _write_nudge(results: Sequence[ResourceResult]) -> None:
    """One line, or the file removed. Removed rather than emptied, because the
    shell tests for a non-empty file and a stale empty one is a file whose mtime
    keeps saying the check ran."""
    issues = [result for result in results if result.verdict is ResourceVerdict.ISSUE]
    if not issues:
        paths.NUDGE_FILE.unlink(missing_ok=True)
        return

    named = ', '.join(result.address for result in issues)
    paths.NUDGE_FILE.write_text(f'dotfiles: {len(issues)} resource(s) need attention ({named}) — run: dotfiles check\n')


SNIPPETS = {
    'zsh': """\
# Generated by `dotfiles shell-init zsh`; cached by cache_eval in .zshrc.
() {
  # Suffixed because the fleet shares this directory: an unsuffixed nudge would
  # be whichever machine checked last, reporting its failure on every other one.
  #
  # The bare lowercased hostname, matching what Python writes. Not $MACHINE:
  # that names the manifest, and both Macs declare the same one, so their nudges
  # would share a path in a directory the fleet syncs. $HOST is a zsh parameter
  # and (L) is an expansion flag, so this still forks nothing — which is the
  # whole point of the snippet.
  local nudge=${XDG_STATE_HOME:-$HOME/.local/state}/dotfiles/nudge-${(L)HOST%%%%.*}
  [[ -s $nudge ]] || return 0

  # zsh/stat and zsh/datetime are builtin modules, so the whole check costs no
  # subprocess: the point of a startup nudge is that it is invisible when there
  # is nothing to say, and a fork per prompt is not invisible.
  zmodload -F zsh/stat b:zstat 2>/dev/null || return 0
  zmodload zsh/datetime 2>/dev/null || return 0

  local -a stamp
  zstat -A stamp +mtime -- $nudge 2>/dev/null || return 0
  # A stale nudge is worse than none: a timer that stopped running would leave a
  # week-old warning on screen with nothing to say it had stopped being true.
  (( EPOCHSECONDS - stamp[1] < %(max_age)d )) || return 0

  print -r -- $(<$nudge)
}
""",
    'bash': """\
# Generated by `dotfiles shell-init bash`.
__dotfiles_nudge() {
  # bash has no case-folding expansion before 4.0 and macOS ships 3.2, so this
  # takes the hostname as it comes. Every host in this fleet is already
  # lowercase; one that is not gets no nudge under bash, which is the fallback
  # shell and not the daily one.
  local nudge="${XDG_STATE_HOME:-$HOME/.local/state}/dotfiles/nudge-${HOSTNAME%%%%.*}"
  [ -s "$nudge" ] || return 0
  # bash has no builtin stat, so this is one subprocess per shell rather than
  # zsh's none. Accepted: bash here is a fallback shell, not the daily one.
  local age=$(( $(date +%%s) - $(stat -c %%Y "$nudge" 2>/dev/null || echo 0) ))
  [ "$age" -lt %(max_age)d ] || return 0
  cat "$nudge"
}
__dotfiles_nudge
""",
}

MAX_AGE_SECONDS = 60 * 60 * 24
"""How old the nudge may be before the shell ignores it.

A day, because the schedule runs several times a day: anything older means the
timer is not running, and a warning nobody is refreshing is a warning that has
stopped being evidence.
"""


def snippet(shell: str) -> str:
    return SNIPPETS[shell] % {'max_age': MAX_AGE_SECONDS}
