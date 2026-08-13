"""Is an installed release the version this machine should have, asked through the CLI.

Currency is the half of `packages` that a present tool can still fail. Presence is
a question `PATH` answers; currency is a comparison between what the binary printed
and what an upstream published, and every part of it — which upstream, whether the
answer is fresh, whether either side parses — changes the verdict. This walks that
comparison across the three verbs and the flags each of them takes.

**The upstream is a file, and there are only two of them.** `plan` and `check`
resolve a Session with `refresh=False`, so the release cache under
`$XDG_CACHE_HOME` is the whole of what they know; `--offline` replaces it with a
staged bundle's manifest. Neither reaches GitHub, which is what makes a row here
the same row on any machine.

**Every `apply` below is an offline one, and that is forced rather than chosen.**
`reconcile.apply_machine` resolves its Session with `refresh=not offline`, so an
online `packages apply` refreshes the cache for every present currency-capable
tool before it decides anything — measured, and it lands on
`github_release.latest_version` inside `observe`. There is no flag that turns it
off, so the online write verb is unreachable from a suite that may not use the
network.

**Which flag each verb takes is itself part of the matrix.** `--offline` is
`apply`'s alone, `--source` is `plan`'s and `apply`'s, and `check` takes neither —
so three of the twelve cells are usage errors rather than verdicts, and they are
asserted as such.

Rich wraps stderr at eighty columns, so every assertion here runs through
`said`, which collapses whitespace. A detail is one sentence whatever the terminal
did to it.
"""

from __future__ import annotations

import dataclasses as dc
import datetime as dt
import re
from collections.abc import Callable

import pytest

from dotfiles.vocabulary import ExitCode
from matrix.harness import Invocation
from matrix.harness import Sandbox

TOOL = 'lazygit'
REPO = 'jesseduffield/lazygit'

DECLARED = {'github_releases': [{'name': TOOL, 'repo': REPO}]}
"""One release, and the name matters: `validate._uninstallable` makes an entry with
no builder in `providers/releases.py` an ERROR, which `apply` refuses to run
against and `check` reports as an Issue. So the declaration is synthetic and the
name is a real one."""

GATED = {'github_releases': [{'name': TOOL, 'repo': REPO, 'requires_github_auth': True}]}
"""The same entry behind a credential this machine does not have.

The sandbox shadows `gh` with `exit 1` and deletes `$GITHUB_TOKEN`, so
`Precondition.GITHUB_AUTH` is unmet by construction rather than by whatever the
developer is logged into. That is what makes `--reinstall` observable at all: a
`BY_HAND` change is rendered and not acted on, where an `AUTOMATIC` one is acted
on and never printed."""

SUBSCRIBES = {'machine': 'box', 'platform': 'linux', 'github_releases': [TOOL]}

ROW = re.compile(r" \(is '[^']*'\)")
"""The measured value a row carries in parentheses, for a comparison about the rest."""

UNCACHED = f'no cached release for {REPO} within the TTL (not refreshed this run)'
"""What an unanswerable currency question says when the upstream is the cache.

One sentence for two relations, because they are one state: an entry nobody has
fetched and an entry fetched too long ago are both "no answer worth trusting", and
`releases.current` collapses them before `currency_of` sees either.
"""


def said(ran: Invocation) -> str:
    """What the run printed on stderr, as one line whatever the terminal width was.

    Rich wraps at eighty columns and a change row spends forty-three of them on the
    verdict and subject columns, so every detail in this module wraps. Collapsing
    whitespace is what makes a substring assertion mean the sentence rather than
    the sentence as laid out on this machine.
    """
    return ' '.join(ran.stderr.split())


def recorded(ran: Invocation) -> list[tuple[str, str, str]]:
    """The run record `apply --json` emits, as (address, verdict, action) triples.

    The verdict and what was done about it, which is the whole of what an `apply`
    can be asked. It carries no `detail`: `runs` records what was decided and what
    happened, and the sentence explaining a decision is the read verbs' to print.
    """
    return [(row['address'], row['verdict'], row['action']) for row in (ran.document or {}).get('outcomes', [])]


# ─────────────────────────────────────────────────────────────────────────────
# The relations, against a release cache
# ─────────────────────────────────────────────────────────────────────────────


@dc.dataclass(frozen=True, slots=True)
class Against:
    """One version relation, and the row the read verbs print for it."""

    id: str
    reported: str | None
    """What the installed binary prints. None is a binary that exits 0 and says nothing."""

    upstream: str | None
    """What the release cache holds for the repo. None writes no cache at all."""

    verdict: str
    """The word in the row's first column, or '' where the item produces no finding."""

    detail: str
    age: dt.timedelta = dt.timedelta(0)
    """How long ago the cache says it was checked. Past `releases.TTL` it is refused."""


CACHED = (
    Against('at-the-latest', 'lazygit version 0.45.0', 'v0.45.0', '', ''),
    Against('behind', 'lazygit version 0.44.0', 'v0.45.0', 'stale', 'v0.45.0 is the latest release'),
    Against('ahead', 'lazygit version 0.46.0', 'v0.45.0', '', ''),
    Against('placeholder-that-parses', '0.0.0', 'v0.45.0', 'stale', 'v0.45.0 is the latest release'),
    Against('unparseable', 'development', 'v0.45.0', 'unknown', "v0.45.0 is the latest release, and 'development' has no version in it"),
    Against('reports-nothing', None, 'v0.45.0', 'unknown', 'lazygit is installed but would not report a version'),
    Against('no-cache-at-all', 'lazygit version 0.44.0', None, 'unknown', UNCACHED),
    Against('cache-past-its-ttl', 'lazygit version 0.44.0', 'v0.45.0', 'unknown', UNCACHED, age=dt.timedelta(hours=13)),
)
"""Every relation an installed release can stand in to a cached upstream.

`ahead` produces no finding, and that is the cache being honest about its own
limits rather than an oversight: a version newer than the newest release anyone
has *asked* about is a cache that has not caught up, and `currency_of` gates the
ahead-is-drift reading on `measured_upstream`. `STAGED` below is the same relation
against an upstream that was measured, where it is drift.
"""

READ = (
    pytest.param(('packages', 'plan'), id='plan'),
    pytest.param(('packages', 'plan', '--source', 'github_releases'), id='plan-source'),
    pytest.param(('packages', 'check'), id='check'),
)
"""The read verbs, and the one flag one of them takes that the other does not.

`--source github_releases` resolves through `registry.serving`, which answers
`packages/ghrelease` alone for this section — no toolchain is `needed_by` a
release — so the selection narrows to the same provider the bare verb walks and
the row must be identical.
"""


def machine(sandbox: Sandbox, relation: Against, packages: dict | None = None) -> None:
    """A machine standing in this relation to its upstream."""
    sandbox.declare(packages=packages or DECLARED, manifest=SUBSCRIBES)
    sandbox.installed(TOOL, relation.reported)
    if relation.upstream is not None:
        sandbox.upstream({REPO: relation.upstream}, age=relation.age)


@pytest.mark.parametrize('relation', CACHED, ids=[relation.id for relation in CACHED])
@pytest.mark.parametrize('argv', READ)
def test_the_row_a_relation_prints_is_the_same_under_every_read_verb(
    sandbox: Sandbox, cli: Callable[..., Invocation], relation: Against, argv: tuple[str, ...]
) -> None:
    """`plan` and `check` measure once and keep different halves, so the *rows* agree.

    What differs between them is which half is the answer and which is the
    evidence, and `--source` narrowing to the one provider that serves the section
    changes neither. A row that read differently under one of the three would mean
    the fold had an opinion about currency, which is `currency_of`'s alone.
    """
    machine(sandbox, relation)

    ran = cli(*argv)

    if relation.verdict:
        assert f'{relation.verdict} ghrelease/{TOOL} {relation.detail}' in said(ran)
    else:
        assert f'matched ghrelease/{TOOL}' in said(ran)


@pytest.mark.parametrize('relation', CACHED, ids=[relation.id for relation in CACHED])
@pytest.mark.parametrize('argv', READ)
def test_currency_moves_plans_exit_code_and_never_checks(
    sandbox: Sandbox, cli: Callable[..., Invocation], relation: Against, argv: tuple[str, ...]
) -> None:
    """A tool a version behind is drift, and drift is not something wrong.

    The rule rather than a table, because the rule is the claim: `plan` exits 1 for
    exactly the relations that produce a `stale` row, and `check` exits 0 for all of
    them. An unmeasurable one moves neither — a cold cache makes every declared
    release unknown at once, and exiting non-zero for that reports a fault on a
    machine with none.
    """
    machine(sandbox, relation)

    ran = cli(*argv)

    drifts = relation.verdict == 'stale' and argv[1] == 'plan'
    assert ran.exit_code == (ExitCode.DRIFT if drifts else ExitCode.CONVERGED)


@pytest.mark.parametrize('relation', CACHED, ids=[relation.id for relation in CACHED])
@pytest.mark.parametrize('verb', ['plan', 'check'])
def test_a_json_run_counts_the_relation_and_prints_no_rows(
    sandbox: Sandbox, cli: Callable[..., Invocation], relation: Against, verb: str
) -> None:
    """The counts are the answer a caller parses, and they are the same under both verbs.

    `sift` is lens-independent — `pending`, `attention` and `unmeasured` are
    properties of the changes rather than of the question — so the split between
    "apply would fix this" and "nothing could measure it" is one fact read from two
    sides. Stderr is empty because `--json` renders no evidence at all: the document
    on stdout is the whole output, which is what keeps it parseable.
    """
    machine(sandbox, relation)

    ran = cli('packages', verb, '--json')

    assert ran.document['pending'] == (1 if relation.verdict == 'stale' else 0)
    assert ran.document['unmeasured'] == (1 if relation.verdict == 'unknown' else 0)
    assert ran.document['attention'] == 0
    assert ran.stderr == ''


def test_a_placeholder_that_parses_is_reported_as_merely_behind(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """A tool answering `0.0.0` produces the row a genuinely old one produces.

    `versions.parse` reads `0.0.0` as `(0, 0, 0)`, which is below every release
    anyone publishes, so `at_least` answers False and the row is `stale` — the same
    verdict, the same detail and the same repair as a tool one version behind. The
    only thing separating them on screen is the measured value in parentheses.

    Current behaviour, pinned so a change to it is visible. `icb` 486 is where it is
    filed, with the three ways it could fork.
    """
    behind, placeholder = CACHED[1], CACHED[3]
    machine(sandbox, behind)
    was_behind = said(cli('packages', 'plan'))

    sandbox.installed(TOOL, placeholder.reported)
    was_placeholder = said(cli('packages', 'plan'))

    assert ROW.sub('', was_behind) == ROW.sub('', was_placeholder)
    assert "(is '0.0.0')" in was_placeholder


@pytest.mark.xfail(strict=True, reason='icb 486: a placeholder banner that parses is read as a real version')
def test_a_placeholder_that_parses_is_not_reported_as_merely_behind(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """A version nothing was ever released at is not evidence that a tool is old.

    `0.0.0` is what a build prints when nothing stamped a version into it, and
    reading it as a number is how `docker-language-server` was reinstalled on three
    consecutive applies without ever converging. `development` — the same
    placeholder from a build that happens not to look numeric — is already answered
    `unknown`, so the fault is the shape of the string rather than the state of the
    tool.

    Asserted as *distinguishable* rather than as one particular verdict, because
    `icb` 486 has not settled which fix it gets: preferring the toolchain's answer
    over the banner, widening the unparseable test, or declaring
    `reports_version: false` per entry. Every one of the three stops these two
    machines producing the same row.
    """
    behind, placeholder = CACHED[1], CACHED[3]
    machine(sandbox, behind)
    was_behind = said(cli('packages', 'plan'))

    sandbox.installed(TOOL, placeholder.reported)
    was_placeholder = said(cli('packages', 'plan'))

    assert ROW.sub('', was_behind) != ROW.sub('', was_placeholder)


def test_nothing_could_be_measured_says_which_refresh_would_fix_it(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """An unmeasurable row carries the command that makes it measurable.

    `--refresh` belongs to the composite verbs and not to `packages check`, which
    is where this row is just as likely to be read — so the advice names the
    command that exists rather than the flag this verb would reject.
    """
    machine(sandbox, CACHED[6])

    ran = cli('packages', 'check')

    assert 'refresh the release cache with `dotfiles check --refresh` or `dotfiles plan --refresh`' in said(ran)


# ─────────────────────────────────────────────────────────────────────────────
# The same relations, against a staged bundle
# ─────────────────────────────────────────────────────────────────────────────


@dc.dataclass(frozen=True, slots=True)
class Staged:
    """One version relation to a bundle, and what an offline `apply` did about it."""

    id: str
    reported: str | None
    bundled: str | None
    """The version the bundle's manifest carries for this tool. None stages another
    tool instead, so the bundle exists and has nothing to say about this one."""

    verdict: str
    acted: bool
    """Whether `apply` tried to install it, which is `Change.actionable`."""


STAGED = (
    Staged('at-the-bundles-version', 'lazygit version 0.45.0', '0.45.0', '', False),
    Staged('behind-the-bundle', 'lazygit version 0.44.0', '0.45.0', 'stale', True),
    Staged('ahead-of-the-bundle', 'lazygit version 0.46.0', '0.45.0', 'stale', True),
    Staged('unparseable', 'development', '0.45.0', 'unknown', False),
    Staged('bundle-carries-no-row', 'lazygit version 0.44.0', None, 'unknown', False),
)
"""The offline relations, and the one that differs from its cached twin.

`ahead-of-the-bundle` is drift where `ahead` against the cache is nothing at all.
A bundle holds the bytes a fresh install would use, so `measured_upstream` is true
and a version above it is a machine holding something no declaration can reproduce
— the state `ifiles` left behind by re-versioning downwards. The cached form of the
same comparison means the opposite and is therefore silent.
"""


def offline_machine(sandbox: Sandbox, relation: Staged, packages: dict | None = None) -> None:
    """A machine with a bundle staged, standing in this relation to it."""
    sandbox.declare(packages=packages or DECLARED, manifest=SUBSCRIBES)
    sandbox.installed(TOOL, relation.reported)
    sandbox.stage_bundle({TOOL: relation.bundled} if relation.bundled else {'other-tool': '1.0.0'})


@pytest.mark.parametrize('relation', STAGED, ids=[relation.id for relation in STAGED])
def test_offline_the_bundle_is_the_upstream_and_the_record_says_what_was_done(
    sandbox: Sandbox, cli: Callable[..., Invocation], relation: Staged
) -> None:
    """`--offline` reads the staged manifest instead of the release cache.

    No cache is written by these machines at all, so a verdict here can only have
    come from the bundle. `apply` is the only verb that takes the flag, which is
    why this asserts against the run record rather than a rendered row: an
    `AUTOMATIC` change is acted on and never printed, so the record is where the
    decision survives.

    The install then fails locally, and deliberately so: the manifest names a
    version but no asset was staged beside it, and `_stage` returns None rather
    than reaching for the network when offline. That failure is the proof the run
    stayed local.
    """
    offline_machine(sandbox, relation)

    ran = cli('packages', 'apply', '--offline', '--json')

    # `unmeasured` is this branch's word for a row nothing could ask upstream
    # about. It used to be filed as `planned`, which read as work the run intended
    # and then silently did not do.
    decided = 'planned' if relation.acted else 'unmeasured'
    filed = [row for row in recorded(ran) if row[0].endswith(TOOL) and row[2] in {'planned', 'unmeasured'}]
    assert filed == ([(f'packages/ghrelease/{TOOL}', relation.verdict, decided)] if relation.verdict else [])
    assert [row for row in recorded(ran) if row[2] == 'failed'] == (
        [(f'packages/ghrelease/{TOOL}', relation.verdict, 'failed')] if relation.acted else []
    )
    assert ran.exit_code == (ExitCode.ISSUE if relation.acted else ExitCode.CONVERGED)


def test_offline_an_unmeasurable_row_is_filed_and_named(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """A bundle carrying no row for the tool leaves it unknown, and the run says so.

    Renamed rather than inverted. The old name was `..._filed_and_not_printed` and
    carried its assertion, so flipping the body under it would have left a test
    saying the opposite of what it checks — worse than no test.

    Silence was the old behaviour and the fault this branch exists to fix. An
    `UNKNOWN` change is neither acted on nor repairable, so `apply` printed nothing
    and the record was the only place it survived — a caller watching the screen
    saw a converged run over a machine holding a tool nothing could measure.
    """
    offline_machine(sandbox, STAGED[4])

    ran = cli('packages', 'apply', '--offline', '--json')

    assert (f'packages/ghrelease/{TOOL}', 'unknown', 'unmeasured') in recorded(ran)
    assert TOOL in said(ran)


def test_offline_needs_a_bundle_before_it_measures_anything(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """With nothing staged there is no upstream, so the run stops before the walk.

    `_stage_bundle` runs ahead of `engine.assess`, which is why this is an exit
    rather than a machine full of unmeasurable rows: an offline run with no bundle
    could install nothing whatever it found.
    """
    sandbox.declare(packages=DECLARED, manifest=SUBSCRIBES)
    sandbox.installed(TOOL, 'lazygit version 0.44.0')

    ran = cli('packages', 'apply', '--offline')

    assert ran.exit_code == ExitCode.ISSUE
    assert 'offline needs a staged bundle at' in said(ran)
    # The path is the whole of what this row is for, and Rich folds a long one
    # mid-word rather than at a space — so it is looked for with the wrapping
    # removed entirely rather than collapsed to single spaces.
    assert str(sandbox.bundle) in ''.join(ran.stderr.split())


# ─────────────────────────────────────────────────────────────────────────────
# --reinstall, which is not a measurement
# ─────────────────────────────────────────────────────────────────────────────


REINSTALL_DETAIL = 'named by --reinstall, so it is installed again whatever it reports'


@pytest.mark.parametrize('relation', STAGED, ids=[relation.id for relation in STAGED])
def test_a_reinstall_forces_stale_from_every_relation(sandbox: Sandbox, cli: Callable[..., Invocation], relation: Staged) -> None:
    """`--reinstall` is checked ahead of currency, so no relation can answer over it.

    Including the two currency cannot speak for. A tool whose banner nothing can
    parse and a bundle with no row for it both produce `unknown` on their own, and
    `unknown` is the one verdict `apply` will not act on — which would leave the
    caller's explicit instruction answered with "nothing could be measured". Naming
    it is the answer to exactly that state.

    The entry is credential-gated so the row is printed instead of performed:
    `repair_for` makes a reinstall `BY_HAND` where the precondition is unmet, and a
    `BY_HAND` change is what `apply` renders and leaves alone.
    """
    offline_machine(sandbox, relation, packages=GATED)

    ran = cli('packages', 'apply', '--offline', '--reinstall', TOOL)

    assert f'stale ghrelease/{TOOL} {REINSTALL_DETAIL}' in said(ran)
    assert ran.exit_code == ExitCode.CONVERGED


@pytest.mark.parametrize('relation', STAGED, ids=[relation.id for relation in STAGED])
def test_a_reinstall_carries_what_the_tool_reported_even_where_it_means_nothing(
    sandbox: Sandbox, cli: Callable[..., Invocation], relation: Staged
) -> None:
    """The row still names the measured value, which is the point of naming it.

    A reinstall is the answer to an installed state that measuring cannot see, so
    what the tool *said* is the reader's only clue about why the instruction was
    given. A binary that says nothing carries no parenthesis at all rather than an
    empty one.
    """
    offline_machine(sandbox, relation, packages=GATED)

    ran = cli('packages', 'apply', '--offline', '--reinstall', TOOL)

    assert (f"(is '{relation.reported}')" in said(ran)) is (relation.reported is not None)


def test_a_reinstall_apply_can_act_on_is_planned_and_attempted(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Ungated, the same instruction is work rather than a row.

    The pair with the test above: `--reinstall` produces one verdict and two
    outcomes depending on nothing but whether this machine could do it. Here the
    change is `AUTOMATIC`, so it is acted on and the record carries both halves —
    what was decided and what happened.
    """
    offline_machine(sandbox, STAGED[0])

    ran = cli('packages', 'apply', '--offline', '--reinstall', TOOL, '--json')

    assert (f'packages/ghrelease/{TOOL}', 'stale', 'planned') in recorded(ran)
    assert (f'packages/ghrelease/{TOOL}', 'stale', 'failed') in recorded(ran)


def test_a_reinstall_naming_nothing_this_machine_declares_is_a_usage_error(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Validated against the resolved plan, so a name the machine does not subscribe
    to is refused rather than matching nothing and reading as a reinstall that ran."""
    offline_machine(sandbox, STAGED[0])

    ran = cli('packages', 'apply', '--offline', '--reinstall', 'ripgrep')

    assert ran.exit_code == ExitCode.USAGE
    assert 'nothing this machine declares is named ripgrep' in said(ran)


# ─────────────────────────────────────────────────────────────────────────────
# Which verb takes which flag
# ─────────────────────────────────────────────────────────────────────────────


def test_check_refuses_a_section_it_cannot_narrow_to(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """`check` answers what is *wrong* with the whole resource, so a section-scoped
    one would report a converged machine by not having looked.

    The `--offline` half of this case is gone rather than reversed. It asserted
    that `plan` and `check` refuse the flag, which this branch deliberately
    changes, and `tests/cli/test_conformance.py::test_check_takes_offline_wherever_apply_does`
    is now where that policy lives — derived by walking the tree instead of listed
    here. Two copies do not disagree while both are true, so nothing surfaces the
    duplication until the policy moves, and then whichever copy the author knew
    about is the one revised. That is exactly what happened: `SELECTORS` gained
    `--offline` with the new argument while this docstring still stated the old one
    as fact. See `standards/testing.md` § "A surface invariant is derived from the
    command tree, never listed in a behavioural test".

    `--source` stays because nothing walks the tree for it. This literal is the
    only thing asserting that rule, and the rule reaches a policy with a derived
    home rather than every literal.
    """
    machine(sandbox, CACHED[1])

    ran = cli('packages', 'check', '--source', 'github_releases', catch_exceptions=True)

    assert ran.exit_code == ExitCode.USAGE
    assert 'No such option: --source' in said(ran)


def test_the_sections_source_will_take_are_this_machines_declaration(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """`available_sources` reads `packages.yml`, so what is valid is what is declared.

    A sandbox declaring one section rejects every other name — including
    `go_tools`, which is a real section of the real file. The completion and the
    validation are one list, and it is read rather than written down.

    Click renders a `BadParameter` inside a bordered panel, so the message arrives
    with box-drawing characters between its words. The two halves are asserted
    apart for that reason: what was rejected, and what the file does declare.
    """
    machine(sandbox, CACHED[1])

    ran = cli('packages', 'plan', '--source', 'go_tools', catch_exceptions=True)

    assert ran.exit_code == ExitCode.USAGE
    assert "unknown source 'go_tools'" in said(ran)
    assert 'github_releases' in said(ran)


# ─────────────────────────────────────────────────────────────────────────────
# A precondition gates the install and the reinstall, and not the upgrade
# ─────────────────────────────────────────────────────────────────────────────


def test_a_credential_gated_tool_is_upgraded_without_the_credential_being_checked(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """A stale private release is `AUTOMATIC`, where the reinstall of it is `BY_HAND`.

    `diff` runs `repair_for` on the two branches that reach it — evidence that did
    not match, and a named reinstall — and `currency_of` builds its `Change` with
    the default repair instead, so no currency verdict has ever consulted a
    precondition. One entry, one machine, one missing credential, two answers.

    Current behaviour, pinned so a change to it is visible.
    """
    offline_machine(sandbox, STAGED[1], packages=GATED)

    upgrade = cli('packages', 'apply', '--offline', '--json')
    reinstall = cli('packages', 'apply', '--offline', '--reinstall', TOOL, '--json')

    assert (f'packages/ghrelease/{TOOL}', 'stale', 'failed') in recorded(upgrade)
    assert [row for row in recorded(reinstall) if row[2] == 'failed'] == []


@pytest.mark.xfail(strict=True, reason='currency_of never calls repair_for, so a precondition does not gate an upgrade')
def test_a_credential_gated_tool_is_not_upgraded_without_the_credential(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """An upgrade this machine cannot perform should be reported, not attempted.

    `repair_for` exists to stop exactly this: *attempting it records a failure for
    something this machine was never able to have, and the run then exits non-zero
    for a reason no change to this repo can fix*. A private release behind its
    upstream on a machine with no `gh` login is that case, and it is the case the
    verdict is most likely to be true in — a tool nobody could download is a tool
    nobody could upgrade either.
    """
    offline_machine(sandbox, STAGED[1], packages=GATED)

    ran = cli('packages', 'apply', '--offline', '--json')

    assert [row for row in recorded(ran) if row[2] == 'failed'] == []
