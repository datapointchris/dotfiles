"""What one resource turned out to be: the verdict, the question, and the row.

The measured counterpart to `plan`, which is what a machine should have. A
`ResourceResult` is a value and nothing else — it measures nothing, folds
nothing and prints nothing. `reconcile` composes one per resource, and every
other reader takes one already built.

**Here rather than beside the fold that builds it, because far more modules read
one than build one.** `output` annotates three signatures with it, `status` takes
a sequence into every run record it writes, `commands.status` carries them on
`Composed`, and `commands.resources` reports a sequence per verb. A type with
that many readers, defined inside the orchestrator, makes the orchestrator
reachable from everything that renders a row — which puts the three whole-machine
verbs beneath `registry` and `engine`, the two layers they are built on.

`Lens` and `ResourceVerdict` sit beside it rather than with the fold. `Lens` is a
field's default, so a result cannot be constructed without it, and a verdict word
read apart from the row it grades is half a vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dotfiles.resources import Change
    from dotfiles.resources import Examined


class ResourceVerdict(StrEnum):
    """What one resource had to say.

    `DRIFT` and `ISSUE` are different kinds, not degrees. Drift is expected and
    benign — the machine differs from its declaration, which is what `apply` is
    for. An Issue is something wrong: a checker crashed, a declaration is
    invalid. Collapsing them is what would make an exit code meaningless, and the
    scheduled unit sits `failed` on whichever one the code carries.

    There was a fourth, `PENDING`, for a resource whose checker had not been
    written yet. Every one of them answers for itself now, so a verdict
    meaning "no evidence either way" has nothing to report it.
    """

    CONVERGED = 'converged'
    DRIFT = 'drift'
    ISSUE = 'issue'


class Lens(StrEnum):
    """Which question is being asked of one walk.

    `plan` and `check` measure the same machine and differ only in what they keep,
    so they are two folds over one stream rather than two walks. The split uses
    fields that already existed and had never been read this way: `Repair` says
    who can fix a change, and its own docstring describes exactly this — *what
    lets `check` report it without `apply` reporting a failure for work it was
    never able to do*.
    """

    PLAN = 'plan'
    """What `apply` would change: `AUTOMATIC` repairs of a missing or stale item."""

    CHECK = 'check'
    """What is wrong: real findings `apply` cannot fix — a machine-local value
    nobody set, a file only safekeep restores, a private-repo tool with no
    credentials, a foreign target needing `--force`, a flag set that nothing
    declares. Plus anything that refused to be measured."""


@dataclass(frozen=True)
class ResourceResult:
    address: str
    verdict: ResourceVerdict
    detail: str

    lens: Lens = Lens.PLAN
    """Which question produced this row, so the renderer can word it.

    On the row it decides two words. "3 pending" under `check` means the drift
    `plan` owns, and `attention` under `plan` means the findings `check` owns —
    the same two counts, each read from the other side. Rendered without it, one
    of the two always reads as contradicting the verdict beside it.
    """

    findings: tuple[Change, ...] = ()
    """The items this lens kept, rendered as rows under the verdict.

    Carried rather than printed while folding, which is what put every resource's
    evidence above every resource's verdict: the rows for `auth` landed under the
    progress line for `credentials` and read as credentials failures, and the
    `credentials` row two lines below said converged.
    """

    others: tuple[Change, ...] = ()
    """The items the *other* lens keeps, plus what nothing could measure. Shown
    under `-v`, so one run can answer both questions when that is what is wanted."""

    examined: tuple[Examined, ...] = ()
    """What was looked at and found fine, minus anything that produced a finding."""

    invalid: tuple[tuple[str, str], ...] = ()
    """Section and message for each declaration problem, which only `machines` has.

    Carried for the reason `findings` is. Printed while the row was being built,
    these landed above every resource's heading and read as findings against
    whatever resource happened to follow them.
    """

    pending: int = 0
    """Items `apply` would change."""

    attention: int = 0
    """Items that differ and `apply` cannot repair — a machine-local value nobody
    set, a file only safekeep restores, a target this manager did not create."""

    unmeasured: int = 0
    """Items with no evidence either way. Neither verb's answer, and not in the
    exit code: a cold release cache makes every declared release unmeasurable at
    once, and calling that drift exits non-zero on a healthy machine."""

    privileged: int = 0
    """How many pending items will ask for a password.

    The half of the front-loaded design worth keeping. Root is acquired at the
    write now, because holding a sudo timestamp does not work on macOS — but a
    plan that is complete before anything runs can still say how many of its
    findings need one, so nobody is surprised mid-run. Counted rather than
    prompted for.
    """

    seconds: float = 0.0
    """What measuring this resource cost, off the engine's own clock.

    Already in every run record and never once on screen, which is how a check
    that took five minutes could be reported as a screen of converged rows with nothing
    saying where the five minutes went. Carried on the result rather than looked
    up from the record afterwards, because the reader who needs it is the one
    watching the run rather than the one reading it back.
    """

    def as_counts(self) -> dict[str, object]:
        """This resource's verdict and how much of it stands where. No items.

        `detail` is prose and will be reworded; the numbers are the answer. Read
        this rather than parsing the sentence, and never assert on rendered output.

        The half `status.state` writes per resource on every scheduled check.
        `lens` is held back, since the document names the verb once at the top.
        """
        return {
            'address': self.address,
            'verdict': str(self.verdict),
            'detail': self.detail,
            'pending': self.pending,
            'attention': self.attention,
            'unmeasured': self.unmeasured,
            'privileged': self.privileged,
            'seconds': round(self.seconds, 3),
        }

    def as_dict(self) -> dict[str, object]:
        """The counts, and the rows behind every one of them.

        **The counts alone were the same defect one level down.** They say how
        many, and every question anyone actually has is *which* — so a caller
        wanting the row it narrowed to had nothing to name it by and asserted on
        the total instead. That works until a second row moves, and then the
        failure reads `assert 3 == 2` and names neither. Every fact on screen is
        reachable through some machine door: `render_result` prints all four of
        these lists, so all four are reachable here.

        **All four unconditionally, because `--json` is not a rendering.** The
        screen shows `findings` always, and `others` and `examined` below a size
        threshold or under `-v`; `-v` is how loud a run is, and a document that
        varied with it would make the flag decide what a machine was told rather
        than what a person was shown.

        Reached only through `status.document`, which a caller asks for and keeps.
        The rows are what makes that document worth handing to another machine and
        what makes it 45 times the size of the counts, so the artifact written
        unasked by every scheduled check takes `as_counts` instead.
        """
        return {
            **self.as_counts(),
            'findings': [change.as_dict() for change in self.findings],
            'others': [change.as_dict() for change in self.others],
            'examined': [row.as_dict() for row in self.examined],
            'invalid': [{'section': section, 'message': message} for section, message in self.invalid],
        }
