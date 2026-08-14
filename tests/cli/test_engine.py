"""The one walk: what it yields, and what it does when a resource cannot answer.

The isolation property is the reason the engine owns the `try` rather than the
generator owning it. A resource that raises must not end the stream, because the
readers downstream — the run record especially — would then record a partial walk
as a whole one, and "one checker crashed" would be indistinguishable from "there
was nothing after this".
"""

from __future__ import annotations

import inspect

import pytest

from dotfiles import engine
from dotfiles import vocabulary
from dotfiles.event import Refusal
from dotfiles.event import Started
from dotfiles.event import Summary
from dotfiles.privilege import Privilege
from dotfiles.resolve import Plan
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Examined
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
    def __init__(self, summary: str, inventory: tuple[Examined, ...] = ()) -> None:
        self.summary = summary
        self.inventory = inventory


def change(item: str) -> Change:
    return Change('packages', Stage.TOOLS, item, Verdict.MISSING, repair=Repair.AUTOMATIC, detail='not installed')


@pytest.fixture
def session() -> Session:
    return Session(machine_name=MACHINE)


def test_the_walk_covers_the_resources_the_vocabulary_names() -> None:
    """One list of addresses, so `--skip`, the help and the walk cannot disagree.

    It is the measuring and printing order, not the convergence order — that is
    `resolve.Stage`, asserted below.
    """
    assert list(engine.resources()) == list(vocabulary.RESOURCES)


def test_no_two_resources_share_a_stage() -> None:
    """The precondition for sorting a walk on the stage alone.

    Two resources at one stage would make the order between them a tie-break
    nobody declared, decided by whichever happened to be measured first. Stage
    numbers exist to state that order rather than let it fall out of the walk.
    """
    from dotfiles import registry

    owners: dict[Stage, set[str]] = {}
    for provider in registry.PROVIDERS:
        owners.setdefault(provider.stage, set()).add(provider.resource)

    # A resource with no provider decides its own stage inside its `diff`, where
    # nothing else can read it. Naming them here is therefore a second list, so
    # the assertion below covers it: one more such resource fails this test rather
    # than slipping past the guard — which is the same drift that put
    # `system/manager` at a stage no phase named.
    unprovided = {
        'env': Stage.ENVIRONMENT,
        'identity': Stage.IDENTITY,
        'symlinks': Stage.SYMLINKS,
        'auth': Stage.AUTH,
        'credentials': Stage.CREDENTIALS,
    }
    assert set(vocabulary.RESOURCES) == {provider.resource for provider in registry.PROVIDERS} | set(unprovided), (
        'a resource appeared that this test does not know the stage of; read it out of its `diff` and add it'
    )

    for resource, stage in unprovided.items():
        owners.setdefault(stage, set()).add(resource)

    shared = {stage: sorted(names) for stage, names in owners.items() if len(names) > 1}
    assert not shared, f'these stages are claimed by more than one resource: {shared}'


def findings(events: list) -> list:
    """The walk minus its announcements, which is what most of these assert on.

    A `Started` is the statement that a resource is about to be measured, so it
    carries no verdict and sits in front of every other event a resource produces.
    Filtering it here rather than in each test keeps the assertions about what was
    *found*, and leaves the two tests below to pin the announcement itself.
    """
    return [event for event in events if not isinstance(event.payload, Started)]


def test_a_resource_announces_itself_before_it_is_measured(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """The property the payload exists for. A reader that hears from a resource
    only once it has an answer cannot say which resource a long silence belongs
    to, and the silence is exactly when somebody asks."""
    monkeypatch.setattr(engine, 'resources', lambda: {'packages': Fake('packages', changes=(change('a'),))})

    events = list(engine.assess(session))

    assert isinstance(events[0].payload, Started)
    assert events[0].resource == 'packages'
    assert events[0].timing is None


def test_a_resource_that_cannot_be_measured_still_announced_itself(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Announced before the `try`, so the resource whose measurement crashed is
    named by the stream rather than only by the refusal it turned into."""
    monkeypatch.setattr(engine, 'resources', lambda: {'packages': Fake('packages', raises=RuntimeError('pacman is not installed'))})

    events = list(engine.assess(session))

    assert [type(event.payload).__name__ for event in events] == ['Started', 'Refusal']


def test_a_resource_yields_its_changes_then_its_summary(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine, 'resources', lambda: {'packages': Fake('packages', changes=(change('a'), change('b')))})

    events = findings(list(engine.assess(session)))

    assert [type(event.payload).__name__ for event in events] == ['Change', 'Change', 'Summary']
    assert events[-1].payload == Summary('packages examined')
    assert all(event.resource == 'packages' for event in events)


def test_a_converged_resource_yields_only_its_summary(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine, 'resources', lambda: {'packages': Fake('packages')})

    assert [event.payload for event in findings(list(engine.assess(session)))] == [Summary('packages examined')]


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

    events = findings(list(engine.assess(session)))

    assert isinstance(events[0].payload, Refusal)
    assert 'pacman is not installed' in events[0].payload.reason
    assert events[0].payload.exit_code is vocabulary.ExitCode.ISSUE
    assert [event.resource for event in events] == ['packages', 'symlinks']
    assert events[1].payload == Summary('symlinks examined')


def test_selecting_addresses_walks_only_those(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine, 'resources', lambda: {name: Fake(name) for name in ('packages', 'symlinks', 'env')})

    walked = findings(list(engine.assess(session, engine.Selection.of('symlinks', 'env'))))
    assert [event.resource for event in walked] == ['symlinks', 'env']


def test_selection_keeps_convergence_order_not_the_caller_s(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """A caller passing a set, or passing them in the order they were typed, must
    not reorder the walk — the order is a dependency chain, not a preference."""
    monkeypatch.setattr(engine, 'resources', lambda: {name: Fake(name) for name in ('packages', 'symlinks', 'env')})

    walked = findings(list(engine.assess(session, engine.Selection.of('env', 'packages'))))
    assert [event.resource for event in walked] == ['packages', 'env']


def test_a_change_carries_the_stage_and_a_summary_does_not(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """A summary is about the resource, not about one item, so it has no place in
    the convergence order — and stamping it with a stage would sort it among the
    items it is summarising."""
    monkeypatch.setattr(engine, 'resources', lambda: {'packages': Fake('packages', changes=(change('a'),))})

    events = findings(list(engine.assess(session)))

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


def test_execute_acts_in_stage_order_rather_than_in_walk_order(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """The two orders differ, and the difference is a real dependency chain.

    `assess` groups by resource because that is how the rows are read. The node
    toolchain is therefore measured with the rest of `toolchains`, and has to be
    *installed* between the cargo packages that ship fnm and the npm globals
    resolved against what it pins — which is a position no ordering of resource
    names can give it.
    """
    packages = Writer(
        'packages',
        changes=(
            Change('packages', Stage.TOOLS, 'fnm', Verdict.MISSING, repair=Repair.AUTOMATIC),
            Change('packages', Stage.NODE_TOOLS, 'typescript-language-server', Verdict.MISSING, repair=Repair.AUTOMATIC),
        ),
    )
    toolchains = Writer('toolchains', changes=(Change('toolchains', Stage.NODE, 'node', Verdict.MISSING, repair=Repair.AUTOMATIC),))
    monkeypatch.setattr(engine, 'resources', lambda: {'packages': packages, 'toolchains': toolchains})

    planned = list(engine.assess(session))
    assert [event.item for event in planned if isinstance(event.payload, Change)] == ['fnm', 'typescript-language-server', 'node']

    acted = [event.item for event in engine.execute(session, planned, Privilege(offer=False))]
    assert acted == ['fnm', 'node', 'typescript-language-server']


def test_execute_skips_what_apply_cannot_repair(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """A required machine-local value is real drift and not apply's to fix. It must
    reach `check`, never `perform`."""
    by_hand = Change(
        'packages', Stage.TOOLS, 'WINDOWS_USER', Verdict.MISSING, repair=Repair.BY_HAND, advice='set it below the marker in ~/.env'
    )
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
    """The system-configuration providers are not a list anyone should keep in
    step by hand."""
    selection = engine.Selection.at(Stage.SYSTEM_CONFIG)

    assert selection.resources == ('system',)
    assert selection.providers == {'group', 'systemd', 'file', 'login-shell', 'macos-default', 'step'}


def test_the_system_config_stage_leaves_the_package_half_out_of_the_plan(session: Session) -> None:
    """The debt A2 recorded here. That phase registry observed the whole `system` resource
    and filtered afterwards, spending a package-inventory query on rows it was
    about to discard."""
    narrowed = engine.Selection.at(Stage.SYSTEM_CONFIG).plan_for('system', session.plan)

    assert all(item.stage is Stage.SYSTEM_CONFIG for item in narrowed.for_resource('system'))


def test_a_ceiling_keeps_everything_up_to_and_including_the_stage(session: Session) -> None:
    """`Stage` is an IntEnum because execution order is a property of the work, so
    "everything through this" is a projection of an order that already exists
    rather than a second opinion about sequence."""
    ceiling = engine.Selection.everything().capped_at(Stage.SYMLINKS)

    for resource in vocabulary.RESOURCES:
        assert all(item.stage <= Stage.SYMLINKS for item in ceiling.plan_for(resource, session.plan).items)


def test_a_ceiling_keeps_the_stages_below_it_rather_than_only_its_own(session: Session) -> None:
    """The difference from `Selection.at`, which is exactly-these-stages. A base a
    test installs over is everything *up to* a point, and saying that with `at`
    means enumerating every stage below — the list nothing should keep by hand."""
    ceiling = engine.Selection.everything().capped_at(Stage.SYMLINKS)

    stages = {item.stage for item in ceiling.plan_for('system', session.plan).for_resource('system')}

    assert Stage.SYSTEM in stages
    assert Stage.SYSTEM_CONFIG not in stages


def test_a_ceiling_and_a_provider_narrowing_both_apply(session: Session) -> None:
    """They answer different questions — which mechanisms against how far — so a
    caller giving both means the intersection."""
    both = engine.Selection.excluding(['packages/go']).capped_at(Stage.TOOLS)

    kept = both.plan_for('packages', session.plan).for_resource('packages')

    assert kept, 'the narrowing removed everything, so this asserts nothing'
    assert all(item.stage <= Stage.TOOLS and item.provider != 'go' for item in kept)


def test_no_ceiling_hands_back_the_very_same_plan(session: Session) -> None:
    """The property `providers is None` already had: a walk narrowing nothing must
    not pay to rebuild the plan, and identity is how that is asserted."""
    assert engine.Selection.everything().plan_for('packages', session.plan) is session.plan


def test_an_absent_ceiling_leaves_the_selection_alone() -> None:
    """`--through` is optional and the call site passes its result straight through,
    so `None` has to be the identity rather than a ceiling at the lowest stage."""
    selection = engine.Selection.everything()

    assert selection.capped_at(None) is selection


def test_the_ceiling_includes_the_stage_it_names() -> None:
    """Asserted directly because two callers read it — the plan filter and the
    epilogue gate — and an off-by-one between them means deploying files under a
    ceiling that planned none, or the reverse."""
    capped = engine.Selection.everything().capped_at(Stage.SYMLINKS)

    assert capped.reaches(Stage.SYMLINKS)
    assert not capped.reaches(Stage.TMUX_PLUGINS)
    assert engine.Selection.everything().reaches(Stage.SYSTEM_CONFIG)


def test_every_stage_is_spellable_by_the_name_that_gets_printed() -> None:
    """`machines show` groups by `stage.name.lower()` and the run records store it,
    so the names were an output vocabulary with nothing accepting one."""
    for stage in Stage:
        assert engine.stage_named(stage.name.lower()) is stage
        assert engine.stage_named(stage.name.upper()) is stage


def test_a_stage_naming_nothing_is_refused_with_the_ones_that_exist() -> None:
    with pytest.raises(engine.UnknownAddress) as refused:
        engine.stage_named('halfway')

    assert 'symlinks' in str(refused.value)


@pytest.mark.parametrize('address', ['nonsense', 'plugins/tmux', 'packages/group', 'plugins/'])
def test_an_address_naming_nothing_is_refused_rather_than_narrowing_to_nothing(address: str) -> None:
    """A run that accepted a misspelt `--skip` would install the sudo-gated stage
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


def test_every_resource_can_name_what_it_examined() -> None:
    """`_measure` reads `observed.inventory` off whatever a resource returns, so a
    resource that never grew one raises `AttributeError` mid-walk and takes down
    the whole of its own report — as a `Refusal`, which reads as a checker that
    crashed rather than as a missing property.

    Asserted on the class rather than by observing, because observing reaches the
    machine and the property is what the walk actually touches.
    """
    observations = {name: inspect.getmodule(type(resource)).Observed for name, resource in engine.resources().items()}  # type: ignore[union-attr]

    assert [name for name, observed in observations.items() if not hasattr(observed, 'inventory')] == []
