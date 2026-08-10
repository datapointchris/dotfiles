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

    assert [event.resource for event in engine.assess(session, engine.Selection.of('symlinks', 'env'))] == ['symlinks', 'env']


def test_selection_keeps_convergence_order_not_the_caller_s(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """A caller passing a set, or passing them in the order they were typed, must
    not reorder the walk — the order is a dependency chain, not a preference."""
    monkeypatch.setattr(engine, 'resources', lambda: {name: Fake(name) for name in ('packages', 'symlinks', 'env')})

    assert [event.resource for event in engine.assess(session, engine.Selection.of('env', 'packages'))] == ['packages', 'env']


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


# ─────────────────────────────────────────────────────────────────────────────
# Selection: an address is a provider, not only a resource
# ─────────────────────────────────────────────────────────────────────────────


def test_a_bare_resource_narrows_nothing_and_hands_over_the_same_plan(session: Session) -> None:
    """`providers is None` rather than the full set, so a walk that excludes
    nothing does not rebuild the plan once per resource."""
    selection = engine.Selection.of('plugins')

    assert selection.providers is None
    assert selection.plan_for('plugins', session.plan) is session.plan


def test_selecting_one_provider_removes_its_neighbours_from_the_plan(session: Session) -> None:
    """Structural, not a filter each resource has to remember: what was left out
    is not in the plan the resource is handed, so it cannot observe or act on it."""
    narrowed = engine.Selection.of('plugins/tpm').plan_for('plugins', session.plan)

    assert {item.provider for item in narrowed.for_resource('plugins')} == {'tpm'}


def test_narrowing_one_resource_leaves_every_other_resources_items_alone(session: Session) -> None:
    """The subtlety that makes this per-resource. `toolchains` decides it needs the
    Go runtime because the plan contains `go_tools` items, so narrowing the plan
    globally by `--skip packages/go` would silently stop planning Go — a resource
    the caller never named."""
    narrowed = engine.Selection.excluding(['packages/go']).plan_for('plugins', session.plan)

    assert narrowed.for_section('go_tools') == session.plan.for_section('go_tools')


def test_skipping_one_provider_leaves_the_rest_of_its_resource_selected() -> None:
    selection = engine.Selection.excluding(['plugins/tpm'])

    assert 'plugins' in selection.resources
    assert selection.providers is not None
    assert 'tpm' not in selection.providers
    assert 'shell-plugin' in selection.providers


def test_skipping_a_whole_resource_drops_it_from_the_walk() -> None:
    assert 'plugins' not in engine.Selection.excluding(['plugins']).resources


def test_a_stage_selects_the_providers_that_run_at_it() -> None:
    """A phase *is* a stage, and the six system-configuration providers are not a
    list anyone should keep in step by hand."""
    selection = engine.Selection.at(Stage.SYSTEM_CONFIG)

    assert selection.resources == ('system',)
    assert selection.providers == {'group', 'systemd', 'file', 'login-shell', 'macos-default', 'step'}


def test_the_system_config_stage_leaves_the_package_half_out_of_the_plan(session: Session) -> None:
    """The debt A2 recorded here. That phase observed the whole `system` resource
    and filtered afterwards, spending a package-inventory query on rows it was
    about to discard."""
    narrowed = engine.Selection.at(Stage.SYSTEM_CONFIG).plan_for('system', session.plan)

    assert all(item.stage is Stage.SYSTEM_CONFIG for item in narrowed.for_resource('system'))


@pytest.mark.parametrize('address', ['nonsense', 'plugins/tmux', 'packages/group', 'plugins/'])
def test_an_address_naming_nothing_is_refused_rather_than_narrowing_to_nothing(address: str) -> None:
    """A run that accepted a misspelt `--skip` would install the sudo-gated phase
    the caller was trying to avoid and report success. `packages/group` is the
    interesting one: `group` is a real provider, of a different resource."""
    with pytest.raises(engine.UnknownAddress):
        engine.validate([address])


def test_a_resource_and_one_of_its_providers_together_keep_the_whole_resource() -> None:
    """`--source` and an address can name the same resource twice. The wider of
    the two has to win, or naming a thing twice would narrow it away."""
    selection = engine.Selection.of('plugins', 'plugins/tpm')

    assert selection.providers is not None
    assert {'tpm', 'shell-plugin', 'yazi-plugin'} <= selection.providers


# ─────────────────────────────────────────────────────────────────────────────
# Batching: a package manager repairs in one transaction, everything else does not
# ─────────────────────────────────────────────────────────────────────────────


class Transactional(Writer):
    """A resource that declares itself `Batched`, recording each call's whole set."""

    def __init__(self, name: str, *, changes: tuple[Change, ...] = (), explodes: bool = False) -> None:
        super().__init__(name, changes=changes)
        self.transactions: list[list[str]] = []
        self._explodes = explodes

    def perform_batch(self, session: Session, changes, privilege: object) -> list[Outcome]:
        if self._explodes:
            raise RuntimeError('the transaction was refused')
        self.transactions.append([change.item for change in changes])
        self.performed.extend(change.item for change in changes)
        return [Outcome(change, OutcomeStatus.DONE, f'did {change.item}') for change in changes]


def test_a_batched_resource_is_handed_its_whole_run_at_once(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """94 declared packages is one `pacman -S`, one dependency resolution and one
    authorization. The same 94 one at a time is 94 of each, which on a fresh
    machine is the difference between seconds and minutes."""
    writer = Transactional('system', changes=(change('a'), change('b'), change('c')))
    monkeypatch.setattr(engine, 'resources', lambda: {'system': writer})

    outcomes = [event.payload for event in engine.execute(session, list(engine.assess(session)), Privilege(offer=False))]

    assert writer.transactions == [['a', 'b', 'c']]
    assert [outcome.change.item for outcome in outcomes] == ['a', 'b', 'c']


def test_a_resource_that_does_not_declare_batching_still_goes_one_at_a_time(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """The default, and it must stay the default: a symlink, a clone and a
    `defaults write` cost the same alone as in company."""
    writer = Writer('packages', changes=(change('a'), change('b')))
    monkeypatch.setattr(engine, 'resources', lambda: {'packages': writer})

    list(engine.execute(session, list(engine.assess(session)), Privilege(offer=False)))

    assert writer.performed == ['a', 'b']
    assert not hasattr(writer, 'transactions')


def test_a_single_change_never_becomes_a_transaction(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """One package is one package. Routing it through the batch path would lose the
    per-item isolation for nothing."""
    writer = Transactional('system', changes=(change('a'),))
    monkeypatch.setattr(engine, 'resources', lambda: {'system': writer})

    list(engine.execute(session, list(engine.assess(session)), Privilege(offer=False)))

    assert writer.transactions == []
    assert writer.performed == ['a']


def test_a_failed_transaction_takes_its_whole_group(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Not a weaker guarantee than the item-by-item path — the true one. `pacman -S
    a b c` either happens or it does not, and reporting the first two as repaired
    because they came earlier in a list is a fiction the machine does not support."""
    writer = Transactional('system', changes=(change('a'), change('b')), explodes=True)
    monkeypatch.setattr(engine, 'resources', lambda: {'system': writer})

    payloads = [event.payload for event in engine.execute(session, list(engine.assess(session)), Privilege(offer=False))]

    assert all(isinstance(payload, Refusal) for payload in payloads)
    assert writer.performed == []


def test_the_transaction_is_timed_once_rather_than_per_item(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Repeating one measurement on each item would multiply the run record's
    totals by the size of the batch."""
    writer = Transactional('system', changes=(change('a'), change('b'), change('c')))
    monkeypatch.setattr(engine, 'resources', lambda: {'system': writer})

    timings = [event.timing for event in engine.execute(session, list(engine.assess(session)), Privilege(offer=False))]

    assert timings[0] is not None
    assert timings[1:] == [None, None]
