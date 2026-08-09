"""The one walk: what it yields, and what it does when a resource cannot answer.

The isolation property is the reason the engine owns the `try` rather than the
generator owning it. A resource that raises must not end the stream, because the
readers downstream — the run record especially — would then record a partial walk
as a whole one, and "one checker crashed" would be indistinguishable from "there
was nothing after this".
"""

from __future__ import annotations

import pytest

from dotfiles import engine
from dotfiles import vocabulary
from dotfiles.event import Refusal
from dotfiles.event import Summary
from dotfiles.privilege import Privilege
from dotfiles.resolve import Plan
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Outcome
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.session import Session

MACHINE = 'linux-lxc-server'


class Fake:
    """A resource with whatever behaviour a test needs, and nothing else."""

    def __init__(self, name: str, *, changes: tuple[Change, ...] = (), raises: Exception | None = None) -> None:
        self.name = name
        self.help = name
        self._changes = changes
        self._raises = raises

    def observe(self, session: Session, plan: Plan) -> object:
        if self._raises is not None:
            raise self._raises
        return _Observed(f'{self.name} examined')

    def diff(self, plan: Plan, observed: object) -> tuple[Change, ...]:
        return self._changes

    def perform(self, session: Session, change: Change, privilege: object) -> Outcome:  # pragma: no cover
        raise AssertionError('assess must not write')


class _Observed:
    def __init__(self, summary: str) -> None:
        self.summary = summary


def change(item: str) -> Change:
    return Change('packages', Stage.TOOLS, item, Verdict.MISSING, detail='not installed')


@pytest.fixture
def session() -> Session:
    return Session(machine_name=MACHINE)


def test_the_registry_is_ordered_as_the_machine_converges() -> None:
    """Not alphabetically: symlinks must land after the tools providing `task` and
    before tpm reads the tmux config it deploys."""
    assert list(engine.resources()) == list(vocabulary.RESOURCES)


def test_a_resource_yields_its_changes_then_its_summary(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine, 'resources', lambda: {'packages': Fake('packages', changes=(change('a'), change('b')))})

    events = list(engine.assess(session))

    assert [type(event.payload).__name__ for event in events] == ['Change', 'Change', 'Summary']
    assert events[-1].payload == Summary('packages examined')
    assert all(event.resource == 'packages' for event in events)


def test_a_converged_resource_yields_only_its_summary(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine, 'resources', lambda: {'packages': Fake('packages')})

    assert [event.payload for event in engine.assess(session)] == [Summary('packages examined')]


def test_a_resource_that_raises_becomes_a_refusal_and_the_walk_continues(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """The property the whole `try` exists for. Without it the stream ends at the
    first failure and every resource after it silently vanishes from the report."""
    monkeypatch.setattr(
        engine,
        'resources',
        lambda: {
            'packages': Fake('packages', raises=RuntimeError('pacman is not installed')),
            'symlinks': Fake('symlinks'),
        },
    )

    events = list(engine.assess(session))

    assert isinstance(events[0].payload, Refusal)
    assert 'pacman is not installed' in events[0].payload.reason
    assert events[0].payload.exit_code is vocabulary.ExitCode.ISSUE
    assert [event.resource for event in events] == ['packages', 'symlinks']
    assert events[1].payload == Summary('symlinks examined')


def test_selecting_addresses_walks_only_those(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine, 'resources', lambda: {name: Fake(name) for name in ('packages', 'symlinks', 'env')})

    assert [event.resource for event in engine.assess(session, ['symlinks', 'env'])] == ['symlinks', 'env']


def test_selection_keeps_convergence_order_not_the_caller_s(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """A caller passing a set, or passing them in the order they were typed, must
    not reorder the walk — the order is a dependency chain, not a preference."""
    monkeypatch.setattr(engine, 'resources', lambda: {name: Fake(name) for name in ('packages', 'symlinks', 'env')})

    assert [event.resource for event in engine.assess(session, ['env', 'packages'])] == ['packages', 'env']


def test_a_change_carries_the_stage_and_a_summary_does_not(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """A summary is about the resource, not about one item, so it has no place in
    the convergence order — and stamping it with a stage would sort it among the
    items it is summarising."""
    monkeypatch.setattr(engine, 'resources', lambda: {'packages': Fake('packages', changes=(change('a'),))})

    events = list(engine.assess(session))

    assert events[0].stage is Stage.TOOLS
    assert events[1].stage is None


# ─────────────────────────────────────────────────────────────────────────────
# Acting on what was decided
# ─────────────────────────────────────────────────────────────────────────────


class Writer(Fake):
    """A resource whose perform records what it was handed, or raises."""

    def __init__(self, name: str, *, changes: tuple[Change, ...] = (), explodes_on: str = '') -> None:
        super().__init__(name, changes=changes)
        self.performed: list[str] = []
        self._explodes_on = explodes_on

    def perform(self, session: Session, change: Change, privilege: object) -> Outcome:
        if change.item == self._explodes_on:
            raise RuntimeError('the disk went away')
        self.performed.append(change.item)
        return Outcome(change, OutcomeStatus.DONE, f'did {change.item}')


def test_execute_acts_on_the_changes_that_were_planned(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """The whole of "apply is plan then execute": what is acted on is what was
    decided and printed, not a second measurement that may disagree."""
    writer = Writer('packages', changes=(change('a'), change('b')))
    monkeypatch.setattr(engine, 'resources', lambda: {'packages': writer})

    planned = list(engine.assess(session))
    outcomes = [event.payload for event in engine.execute(session, planned, Privilege(offer=False))]

    assert writer.performed == ['a', 'b']
    assert all(isinstance(outcome, Outcome) and outcome.ok for outcome in outcomes)


def test_execute_skips_what_apply_cannot_repair(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """A required machine-local value is real drift and not apply's to fix. It must
    reach `check`, never `perform`."""
    by_hand = Change('packages', Stage.TOOLS, 'WINDOWS_USER', Verdict.MISSING, repair=Repair.BY_HAND)
    writer = Writer('packages', changes=(change('a'), by_hand))
    monkeypatch.setattr(engine, 'resources', lambda: {'packages': writer})

    list(engine.execute(session, list(engine.assess(session)), Privilege(offer=False)))

    assert writer.performed == ['a']


def test_one_item_failing_does_not_abandon_the_rest(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolation belongs to the engine here too. Without it a run stops silently
    part-way and the record says nothing about the half that never ran."""
    writer = Writer('packages', changes=(change('a'), change('boom'), change('c')), explodes_on='boom')
    monkeypatch.setattr(engine, 'resources', lambda: {'packages': writer})

    payloads = [event.payload for event in engine.execute(session, list(engine.assess(session)), Privilege(offer=False))]

    assert writer.performed == ['a', 'c']
    assert isinstance(payloads[1], Refusal)
