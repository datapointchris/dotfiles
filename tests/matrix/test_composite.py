"""The three root verbs, and what each of their selectors does to the walk.

`plan`, `check` and `apply` measure one machine and keep different halves of what
they find. Everything here is a claim about that split or about a selector that
narrows it — `--skip`, `--through`, `--refresh`, `--owner`, `--json` — asserted
through the front door against the synthetic machine the sandbox builds.

**Every selector is measured by what it removed, never by what it printed.** A
`--skip` that quietly narrowed to nothing and a `--skip` that was honoured both
produce a converged run, so a row count or an exit code alone cannot tell them
apart. The document's addresses say which resources were walked, the run record
says which flags were recorded, and the install guard says whether a narrowing
reached the write as well as the report.

The two verbs' answers are the last section below, and they are asserted on one
machine carrying both faults at once. Two machines, each with one fault, would let
a verb pass by ignoring the fault it was never shown.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest

from dotfiles.vocabulary import RESOURCES
from dotfiles.vocabulary import ExitCode
from matrix.harness import DECLARES_LAZYGIT
from matrix.harness import LAZYGIT
from matrix.harness import Invocation
from matrix.harness import ReachedTheNetwork
from matrix.harness import Sandbox
from matrix.harness import addresses
from matrix.harness import resource

READ_VERBS = ('plan', 'check')
ALL_VERBS = ('plan', 'check', 'apply')

RUFF = {'uv_tools': {'lint': [{'name': 'ruff'}]}}
DECLARES_RUFF = {'machine': 'box', 'platform': 'linux', 'uv_tools': ['ruff']}
"""One entry whose repair is a subprocess, so `no_installing_on_this_machine` fires
if a narrowing failed to reach the write.

A uv tool rather than a release: its install runs `uv tool install` and stops at
the guard, where a release install resolves its tag against GitHub first and would
stop at the network guard instead — a different assertion wearing the same shape.
"""

WOULD_INSTALL = 'would install on this machine'
"""What the root conftest's guard says. Matched as a string rather than imported,
because it raises a `BaseException` that `tests/` exports no name for."""


def skipping(*dropped: str) -> list[str]:
    """`--skip` is repeatable, so a matrix row carries the addresses and not the argv.

    Not `*addresses`, which is the module-level reader of a document imported
    above — the same collision `resource` had in two other files and was renamed
    out of. A parameter that shadows a helper reads fine until the helper is
    wanted inside the function that hid it.
    """
    return [argument for address in dropped for argument in ('--skip', address)]


def broken_identity(sandbox: Sandbox) -> None:
    """Remove the git identity, which is drift no `apply` can repair.

    `user.name` and `user.email` are `BY_HAND` — nothing in the repo knows what
    this person is called — so they are exactly the shape `check` keeps and `plan`
    does not.
    """
    (sandbox.config / 'git' / 'config').unlink()


# ─────────────────────────────────────────────────────────────────────────────
# Every resource reaches the run
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ('verb', 'expected'),
    [('plan', list(RESOURCES)), ('check', ['machines', *RESOURCES])],
    ids=['plan-walks-the-resources', 'check-walks-them-behind-the-declaration'],
)
def test_a_read_verb_reports_every_resource_in_the_order_the_vocabulary_declares(
    verb: str, expected: list[str], cli: Callable[..., Invocation]
) -> None:
    """Equality rather than containment, because both halves are the contract.

    A resource missing from the document is a part of the machine nothing measured
    and nothing said so. An extra one, or a different order, is a break for the
    `--skip` argument and the shell completion built on the same vocabulary.

    `check` carries `machines` and `plan` does not, and that asymmetry is the
    declaration check: an invalid `packages.yml` is something *wrong*, so a plan
    that refused to print because a manifest names a retired tool would be
    answering a question nobody asked.
    """
    assert addresses(cli(verb, '--json')) == expected


@pytest.mark.parametrize('verb', ALL_VERBS, ids=list(ALL_VERBS))
def test_every_verb_files_a_run_record_naming_every_resource_it_examined(
    verb: str, sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """The record is what answers "what did that run actually cover" afterwards, and
    it is the only artefact `plan` and `check` share with `apply`."""
    cli(verb)

    filed = sandbox.latest_record

    assert filed['verb'] == verb
    assert sorted({outcome['address'].split('/')[0] for outcome in filed['outcomes']}) == sorted(RESOURCES)


# ─────────────────────────────────────────────────────────────────────────────
# --skip
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    'skipped',
    [
        pytest.param(('packages',), id='one-resource'),
        pytest.param(('packages', 'system', 'auth'), id='three-resources'),
        pytest.param(RESOURCES, id='every-resource'),
    ],
)
@pytest.mark.parametrize('verb', READ_VERBS, ids=list(READ_VERBS))
def test_a_skipped_resource_is_absent_from_the_document_rather_than_a_row_nothing_measured(
    verb: str, skipped: tuple[str, ...], cli: Callable[..., Invocation]
) -> None:
    """A skip removes the row. It does not leave a fourth verdict behind.

    The alternative — a row saying `skipped` — would put something in `--json` that
    no checker produced, and a reader folding the document could not tell it from a
    resource that answered. Absence is the honest shape: it was not examined, so it
    has nothing to report.
    """
    ran = cli(verb, *skipping(*skipped), '--json')

    walked = addresses(ran)
    assert set(skipped).isdisjoint(walked)
    assert walked == [address for address in (['machines', *RESOURCES] if verb == 'check' else RESOURCES) if address not in skipped]


@pytest.mark.parametrize('verb', READ_VERBS, ids=list(READ_VERBS))
def test_skipping_every_resource_leaves_a_read_verb_with_nothing_to_report(verb: str, cli: Callable[..., Invocation]) -> None:
    """A read of nothing is converged, and `apply` refuses the same selection.

    The asymmetry is deliberate rather than a defect, and the reason is what the
    caller wrote: naming all nine addresses is an unambiguous request to examine
    none of them, and an empty report is the true answer to it. `apply` refuses
    because there is a *write* to authorise and no work in it — measured in
    `test_an_apply_with_nothing_selected_refuses_rather_than_reporting_success`.

    An owner that matched nothing is not this case, and is a bug: see
    `test_a_plan_scoped_to_an_owner_that_matches_nothing_reports_a_converged_machine`.
    """
    ran = cli(verb, *skipping(*RESOURCES), '--json')

    assert ran.exit_code == ExitCode.CONVERGED
    assert addresses(ran) == ([] if verb == 'plan' else ['machines'])


def test_an_apply_with_nothing_selected_refuses_rather_than_reporting_success(cli: Callable[..., Invocation]) -> None:
    ran = cli('apply', *skipping(*RESOURCES))

    assert ran.exit_code == ExitCode.USAGE
    assert 'nothing selected' in ran.stderr


@pytest.mark.parametrize(
    'address',
    [
        pytest.param('nonsense', id='no-such-resource'),
        pytest.param('packages/nope', id='no-such-provider'),
        pytest.param('toolchains/ghrelease', id='provider-under-the-wrong-resource'),
        pytest.param('plugins/', id='separator-with-nothing-after-it'),
    ],
)
@pytest.mark.parametrize('verb', ALL_VERBS, ids=list(ALL_VERBS))
def test_a_skip_naming_nothing_is_a_usage_error_on_every_verb(verb: str, address: str, cli: Callable[..., Invocation]) -> None:
    """Refusing the misspelling is the important half.

    A run that accepted one would converge the sudo-gated stage the caller was
    trying to avoid and report success. `plugins/` is the case a plain split gets
    wrong: read as a bare resource it silently skips all of `plugins`, which is the
    over-skip the address grammar exists to end.

    All three verbs, because the validation happens before the Session resolves and
    each verb calls it for itself — a fourth caller forgetting to is a `--skip` that
    is accepted and then matches nothing.
    """
    ran = cli(verb, '--skip', address)

    assert ran.exit_code == ExitCode.USAGE
    assert address in ran.stderr
    assert address not in ran.stdout


@pytest.mark.parametrize(
    'address',
    [pytest.param('machines', id='the-declaration-check'), pytest.param('packages/ghrelease', id='one-provider-inside-a-resource')],
)
@pytest.mark.parametrize('verb', ALL_VERBS, ids=list(ALL_VERBS))
def test_the_addresses_the_grammar_admits_beyond_a_bare_resource_are_accepted(
    verb: str, address: str, cli: Callable[..., Invocation]
) -> None:
    """`machines` is not a resource and `packages/ghrelease` is not a whole one, and
    both are spellable. Asserted on every verb because a leaf that validated a
    narrower grammar would reject an address the run record printed."""
    assert cli(verb, '--skip', address).exit_code != ExitCode.USAGE


def test_skipping_one_provider_keeps_the_resource_in_the_walk_and_drops_its_item(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The row stays, and is honest about the narrower thing it measured.

    A provider-level skip removing the whole resource is what the grammar was
    invented to stop: `plugins/tpm` and `plugins/shell-plugin` sit on opposite
    sides of the symlink pass, so "leave TPM alone" cannot mean "leave plugins
    alone".
    """
    sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)

    unnarrowed = cli('plan', '--json')
    narrowed = cli('plan', '--skip', 'packages/ghrelease', '--json')

    assert unnarrowed.exit_code == ExitCode.DRIFT
    assert resource(unnarrowed, 'packages')['pending'] == 1
    assert narrowed.exit_code == ExitCode.CONVERGED
    assert 'packages' in addresses(narrowed)
    assert resource(narrowed, 'packages')['pending'] == 0


def test_skipping_the_declaration_check_removes_the_finding_it_would_have_reported(
    sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """The sharpest form of "a skip removes the row": the exit code moves with it.

    A machine whose manifest names an entry `packages.yml` does not declare is an
    Issue under `check`, and `--skip machines` is what makes the same machine
    answer converged. Nothing else in the walk changes, which is what says the skip
    reached the declaration row rather than the resources.
    """
    sandbox.declare(packages={}, manifest=DECLARES_RUFF)

    reported = cli('check', '--json')
    skipped = cli('check', '--skip', 'machines', '--json')

    assert reported.exit_code == ExitCode.ISSUE
    assert resource(reported, 'machines')['verdict'] == 'issue'
    assert skipped.exit_code == ExitCode.CONVERGED
    assert addresses(skipped) == list(RESOURCES)


def test_a_skip_reaches_the_write_and_not_only_the_report(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """A narrowing that only hid rows would install what it claimed to leave alone.

    The guard is the assertion: an unskipped `apply` reaches `uv tool install` and
    is stopped, and both skips complete. Nothing here reads output, because a run
    that installed and a run that did not both print a converged rule.
    """
    sandbox.declare(packages=RUFF, manifest=DECLARES_RUFF)

    with pytest.raises(BaseException, match=WOULD_INSTALL):
        cli('apply')

    assert cli('apply', '--skip', 'packages').exit_code == ExitCode.CONVERGED
    assert cli('apply', '--skip', 'packages/uv').exit_code == ExitCode.CONVERGED


@pytest.mark.parametrize('verb', ALL_VERBS, ids=list(ALL_VERBS))
def test_the_run_record_carries_the_skipped_addresses_sorted(verb: str, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """What a run was asked to leave alone is part of what it did.

    Sorted, so two invocations naming the same addresses in different orders file
    the same flags and a reader comparing two records is comparing the runs rather
    than the argv.
    """
    cli(verb, *skipping('system', 'auth'))

    assert sandbox.latest_record['flags']['skip'] == ['auth', 'system']


# ─────────────────────────────────────────────────────────────────────────────
# --through
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ('ceiling', 'installs'),
    [
        pytest.param('identity', False, id='far-below-the-work'),
        pytest.param('node_tools', False, id='one-stage-below-the-work'),
        pytest.param('python_tools', True, id='the-stage-the-work-sits-at'),
        pytest.param('system_config', True, id='above-the-work'),
        pytest.param(None, True, id='no-ceiling'),
    ],
)
def test_a_ceiling_stops_the_work_above_it_and_admits_the_stage_it_names(
    ceiling: str | None, installs: bool, sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """`--through` is inclusive, and the boundary is where that is decided.

    The uv tool sits at `python_tools`. A ceiling one stage below it converges with
    nothing installed; the ceiling *naming* that stage lets the install through, so
    "up to and including" is measured rather than assumed. The install guard is the
    only witness either way — a capped run and an uncapped one print the same rows.
    """
    sandbox.declare(packages=RUFF, manifest=DECLARES_RUFF)
    argv = ['apply'] if ceiling is None else ['apply', '--through', ceiling]

    if installs:
        with pytest.raises(BaseException, match=WOULD_INSTALL):
            cli(*argv)
        return

    assert cli(*argv).exit_code == ExitCode.CONVERGED


def test_an_unknown_stage_is_a_usage_error_naming_the_stages_that_exist(cli: Callable[..., Invocation]) -> None:
    """The names are read off `resolve.Stage` rather than written down, so a stage
    added there is spellable — and refusable — the day it exists."""
    ran = cli('apply', '--through', 'nonsense')

    assert ran.exit_code == ExitCode.USAGE
    assert 'unknown stage nonsense' in ran.stderr
    assert 'symlinks' in ran.stderr


def test_the_run_record_carries_the_ceiling_only_when_one_was_named(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Absent rather than null, so a record of an uncapped run cannot be read as a
    run capped at nothing."""
    cli('apply', '--through', 'symlinks')
    capped = sandbox.latest_record

    cli('apply')
    uncapped = sandbox.latest_record

    assert capped['flags']['through'] == 'symlinks'
    assert 'through' not in uncapped['flags']


# ─────────────────────────────────────────────────────────────────────────────
# --refresh
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('verb', READ_VERBS, ids=list(READ_VERBS))
def test_refresh_spends_the_network_on_a_tool_that_is_installed(verb: str, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Both read verbs run at a prompt and on a timer, so both need the opt-in and
    both have to honour it. A flag accepted by one and ignored by the other is a
    `check` that silently answers from a cache the caller asked it not to trust."""
    sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)
    sandbox.installed('lazygit', 'lazygit version 0.44.0')

    with pytest.raises(ReachedTheNetwork):
        cli(verb, '--refresh')


@pytest.mark.parametrize('verb', READ_VERBS, ids=list(READ_VERBS))
def test_refresh_asks_nothing_about_a_tool_that_is_not_installed(verb: str, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Presence is measured first, so a missing tool has no currency to have. The
    same flag therefore costs nothing on a machine that has not been built yet,
    which is the machine most likely to be running with no route to GitHub."""
    sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)

    ran = cli(verb, '--refresh', '--json')

    assert resource(ran, 'packages')['pending'] == 1
    assert resource(ran, 'packages')['unmeasured'] == 0


def test_apply_reaches_upstream_without_being_asked_to(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """`apply` resolves with `refresh=not offline`, so being current is not
    something a caller opts into — an install writes a version onto the machine and
    the cached answer it would otherwise trust is the one it was just told to
    distrust.

    That no `apply` *offers* `--refresh` is a fact about the command tree, and
    `tests/cli/test_conformance.py` derives it across every leaf. What only a run
    can show is the other half: that the network is reached anyway.
    """
    sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)
    sandbox.installed('lazygit', 'lazygit version 0.44.0')

    with pytest.raises(ReachedTheNetwork):
        cli('apply')


# ─────────────────────────────────────────────────────────────────────────────
# --owner
# ─────────────────────────────────────────────────────────────────────────────


def test_an_owner_narrows_the_walk_to_the_resources_holding_that_owners_providers(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The narrowing reaches the walk, not only the plan.

    `symlinks`, `env`, `identity` and `auth` have no provider, so an owner-narrowed
    *plan* leaves every one of them intact — and a walk that trusted the plan alone
    would report every symlink and `~/.env` as part of what one person's tools
    cover. Their absence here is the assertion; `packages` surviving is only the
    control.
    """
    sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)

    ran = cli('plan', '--owner', 'jesseduffield', '--json')

    assert ran.exit_code == ExitCode.DRIFT
    assert addresses(ran) == ['packages']
    assert resource(ran, 'packages')['pending'] == 1


def test_an_apply_scoped_to_an_owner_that_matches_nothing_refuses(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """And refuses before it writes: the uv tool this machine declares would have
    been installed by an unscoped run, and the guard says nothing here."""
    sandbox.declare(packages=RUFF, manifest=DECLARES_RUFF)

    ran = cli('apply', '--owner', 'nobody')

    assert ran.exit_code == ExitCode.USAGE
    assert 'nothing selected for owner nobody' in ran.stderr


def test_a_plan_scoped_to_an_owner_that_matches_nothing_refuses_as_apply_does(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """`plan`'s own docstring says `--owner` "is `apply`'s and means the same,
    because a scope the write accepts and the read cannot express is not a narrower
    preview but no preview at all". The two do not agree on an owner that selects
    nothing: `apply_machine` refuses with `nothing selected for owner X` and exit 2,
    and `survey` walks an empty selection and folds it to converged.

    It is the failure `engine._valid` exists to prevent, one flag over. A misspelt
    `--skip` is a usage error because a run that accepted it would report success
    for work it never did; a misspelt `--owner` does exactly that, and says
    `nothing to change` about a machine it did not look at.

    The fix belongs beside the one `apply` already has: `survey` narrows the
    selection by owner, so the emptiness is known there too.
    """
    sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)

    assert cli('plan', '--owner', 'nobody').exit_code == ExitCode.USAGE


# ─────────────────────────────────────────────────────────────────────────────
# --json
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ('verb', 'keys'),
    [
        pytest.param('plan', {'version', 'verb', 'machine', 'checked', 'verdict', 'resources'}, id='plan-emits-the-interchange-document'),
        pytest.param('check', {'version', 'verb', 'machine', 'checked', 'verdict', 'resources'}, id='check-emits-the-same-document'),
        pytest.param(
            'apply',
            {'id', 'machine', 'verb', 'flags', 'started_at', 'schema', 'finished_at', 'duration_seconds', 'host', 'outcomes', 'issues'},
            id='apply-emits-the-run-record',
        ),
    ],
)
def test_each_verb_emits_the_document_its_reader_wants(verb: str, keys: set[str], cli: Callable[..., Invocation]) -> None:
    """Two shapes, deliberately.

    `plan` and `check` emit one versioned interchange document — the artefact a
    network-blocked machine hands to one that can reach the network, so a partial
    bundle can be built from it — and it carries `verb` because the two keep
    different findings and a reader cannot otherwise tell which question produced
    it. `apply` emits the run record it just wrote, which is an execution
    transcript and answers a different question.

    Equality on the key set, because a reader that has to test for a key before
    trusting it is reading a shape rather than a document.
    """
    ran = cli(verb, '--json')

    assert set(ran.document) == keys
    assert ran.document['verb'] == verb


@pytest.mark.parametrize('verb', READ_VERBS, ids=list(READ_VERBS))
def test_the_interchange_document_says_which_generation_it_is(verb: str, cli: Callable[..., Invocation]) -> None:
    """A literal, which is the point: this is the one place a number is the check
    rather than a copy of it.

    Read from `status.VERSION` the assertion re-reads whatever the writer wrote
    with, so it survives a bump that should not have happened, a revert, and a
    shape change with no bump. Editing the number here is the deliberate second act
    that makes a bump a decision instead of a side effect — and this document
    crosses machines, so a generation nobody declared is one the far end cannot
    test for.
    """
    assert cli(verb, '--json').document['version'] == 2


@pytest.mark.parametrize('verb', ALL_VERBS, ids=list(ALL_VERBS))
def test_a_json_run_puts_the_document_alone_on_stdout(verb: str, cli: Callable[..., Invocation]) -> None:
    """One stray diagnostic on stdout turns a `--json` parse into a syntax error
    rather than the warning it was, so the assertion is that stdout parses whole —
    not that it contains a document somewhere."""
    ran = cli(verb, '--json')

    assert json.loads(ran.stdout) == ran.document


@pytest.mark.parametrize(
    ('verb', 'answers_on_stdout'),
    [
        pytest.param('plan', True, id='plan-answers-on-stdout'),
        pytest.param('check', True, id='check-answers-on-stdout'),
        pytest.param('apply', False, id='apply-is-all-transcript'),
    ],
)
def test_a_human_run_splits_the_answer_from_the_transcript(verb: str, answers_on_stdout: bool, cli: Callable[..., Invocation]) -> None:
    """The read verbs put each resource's verdict on stdout and its evidence on
    stderr, so a redirected run separates into an answer and a transcript. `apply`
    has no answer of that kind — everything it prints is the transcript of work —
    so its stdout is empty and `--json` is what a pipeline reads instead.
    """
    ran = cli(verb)
    heading = '✓ packages'

    assert bool(ran.stdout.strip()) is answers_on_stdout
    assert (heading in ran.stdout) is answers_on_stdout
    assert (heading in ran.stderr) is not answers_on_stdout


# ─────────────────────────────────────────────────────────────────────────────
# What is wrong versus what differs
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ('verb', 'code', 'verdicts'),
    [
        pytest.param('plan', ExitCode.DRIFT, {'packages': 'drift', 'identity': 'converged'}, id='plan-keeps-what-differs'),
        pytest.param('check', ExitCode.ISSUE, {'packages': 'converged', 'identity': 'issue'}, id='check-keeps-what-is-wrong'),
    ],
)
def test_each_verb_keeps_its_own_half_of_one_machines_findings(
    verb: str, code: ExitCode, verdicts: dict[str, str], sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """One machine carrying both faults, so neither verb can pass by not being shown one.

    A declared release that is absent is drift — normal between applies, and what
    `apply` exists for. A git identity nobody has set is an Issue — `apply` cannot
    invent a name, so no run will ever clear it. Folding the two together is what
    left the scheduled unit permanently failed on a healthy box.

    The verdicts cross: `packages` is drift under `plan` and converged under
    `check`, and `identity` is the mirror of that. Both rows appear in both
    documents, which is what makes this two folds over one measurement rather than
    two walks that happened to disagree.
    """
    sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)
    broken_identity(sandbox)

    ran = cli(verb, '--json')

    assert ran.exit_code == code
    assert {address: resource(ran, address)['verdict'] for address in verdicts} == verdicts


def test_the_two_verbs_count_the_same_items_and_disagree_only_about_which_matter(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The counts are identical; the verdict read off them is not.

    This is the claim the split rests on. If `check` measured less than `plan` did,
    the pair would be two walks and the exit codes would be answers to two
    different questions about two different machines.
    """
    sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)
    broken_identity(sandbox)

    planned = cli('plan', '--json')
    checked = cli('check', '--json')

    counted = {address: (resource(planned, address)['pending'], resource(planned, address)['attention']) for address in RESOURCES}
    assert counted == {address: (resource(checked, address)['pending'], resource(checked, address)['attention']) for address in RESOURCES}
    assert counted['packages'] == (1, 0)
    assert counted['identity'] == (0, 2)


@pytest.mark.parametrize(
    ('verb', 'code'),
    [
        pytest.param('plan', ExitCode.CONVERGED, id='plan-does-not-answer-for-the-declaration'),
        pytest.param('check', ExitCode.ISSUE, id='check-reports-it'),
        pytest.param('apply', ExitCode.ISSUE, id='apply-refuses-to-act-on-it'),
    ],
)
def test_an_invalid_declaration_is_checks_business_and_applys_gate_and_not_plans(
    verb: str, code: ExitCode, sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """Three verbs, one broken declaration, three different right answers.

    A manifest naming an entry `packages.yml` does not declare is *wrong*, so
    `check` reports it. It is also unsafe to act on, so `apply` refuses before it
    measures anything — a run against a declaration that will not hold together
    installs whatever survived the parse and reports success. `plan` says nothing:
    it answers what `apply` would change, and refusing to print because a manifest
    names a retired tool would be answering a question nobody asked.
    """
    sandbox.declare(packages={}, manifest=DECLARES_RUFF)

    assert cli(verb, '--json', catch_exceptions=True).exit_code == code


def test_a_check_leaves_a_nudge_only_for_what_is_wrong(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The nudge fires on Issues, never on drift.

    Drift is the normal state of a machine between applies; nudging about it at
    every prompt would train the nudge away inside a week. The declared release
    that is absent is drift and leaves no file; the unset identity is an Issue and
    names itself in one line.
    """
    sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)

    assert cli('check').exit_code == ExitCode.CONVERGED
    assert not sandbox.nudge_file.exists()

    broken_identity(sandbox)

    assert cli('check').exit_code == ExitCode.ISSUE
    assert 'identity' in sandbox.nudge_file.read_text()


def test_skipping_the_resource_that_is_wrong_clears_the_nudge_it_left(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """A skip removes the finding, and the file the finding wrote goes with it.

    Removed rather than emptied, because the shell tests for a non-empty file and a
    stale empty one is a file whose mtime keeps saying the check ran.
    """
    broken_identity(sandbox)
    cli('check')

    ran = cli('check', '--skip', 'identity')

    assert ran.exit_code == ExitCode.CONVERGED
    assert not sandbox.nudge_file.exists()


# ─────────────────────────────────────────────────────────────────────────────
# --machine
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('verb', READ_VERBS, ids=list(READ_VERBS))
def test_a_read_verb_reports_a_machine_with_no_manifest_rather_than_crashing(verb: str, cli: Callable[..., Invocation]) -> None:
    """Exit 2, and the same answer `machines show <typo>` already gives.

    Two codes were available and the codebase has already picked between them, in
    the noun whose whole subject is machines: `_manifest_path` raises
    `BadParameter` for a name with no manifest, so `machines show ghost` exits 2
    naming the ones that exist — a *passing* row in
    `test_machines_config_repo.py::test_a_leaf_given_a_machine_that_does_not_exist_names_the_ones_that_do`.
    `commands/resources.py::_validate_source` states the principle for the sibling
    case: a caller has to be able to tell "you typed it wrong" from "it ran and
    failed", and only the first is worth retrying.

    Exit 3 is the alternative and it is wrong here. It means something is wrong
    with the *machine*, and nothing is — a name is misspelt. `check` is documented
    to answer 0 or 3, so a mistyped `--machine` answering 3 is a scheduled caller
    paging about a typo. Catching the exception around a load reaches 3 without
    anyone deciding a typo is a machine fault, which is what `NoSuchMachine` exists
    to separate.

    A manifest that exists and will not parse keeps exit 3. That is the whole
    distinction `NoSuchMachine` carries, and
    `test_a_read_verb_reports_an_unreadable_manifest_as_an_issue` below pins it.
    """
    ran = cli(verb, '--machine', 'nosuch', catch_exceptions=True)

    assert ran.exit_code == ExitCode.USAGE
    assert 'nosuch' in ran.stderr


def test_apply_reports_a_machine_with_no_manifest(cli: Callable[..., Invocation]) -> None:
    """The write verb answers the code every read verb answers.

    `apply` was the leaf that always diagnosed this, and it diagnosed it as an
    Issue. Uniformity is the point: a typo is retryable wherever it is typed, so
    the code cannot depend on which verb caught the name.
    """
    ran = cli('apply', '--machine', 'nosuch')

    assert ran.exit_code == ExitCode.USAGE
    assert 'nosuch: has no manifest' in ran.stderr


def test_a_read_verb_reports_an_unreadable_manifest_as_an_issue(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The other half of the split, and the reason the split exists.

    A name with no manifest is a typo and exits 2. A manifest that exists and will
    not parse is a fault in the machine, exits 3, and is not worth retyping — so
    `NoSuchMachine` is a subclass and only the sites that care separate the two.
    Collapsing them would send a caller hunting for a misspelling in a name that is
    spelt correctly.
    """
    sandbox.declare(manifest={'machine': sandbox.machine})

    ran = cli('check', catch_exceptions=True)

    assert ran.exit_code == ExitCode.ISSUE
    assert 'declares neither a platform nor coordinates' in ran.output


def test_the_run_record_is_filed_under_the_resolved_machine_rather_than_the_argument(
    sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """Named explicitly or resolved from `$MACHINE`, the record says the same thing.

    Under the scheduled timer neither is set and the resolution comes from `~/.env`,
    which is why the document takes the resolved name: it once said the machine was
    `""` while the check itself had correctly read the file.
    """
    ran = cli('check', '--machine', sandbox.machine, '--json')

    assert ran.document['machine'] == sandbox.machine
    assert sandbox.latest_record['machine'] == sandbox.machine


def test_the_status_file_a_check_writes_carries_its_verdicts_and_none_of_its_rows(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Every `check` refreshes what the next shell reports, not only the scheduled
    one — which is what stops a nudge outliving the problem it describes.

    The same run and not the same bytes. This file is written unasked into a
    directory the fleet syncs, several times a day, and the question it answers is
    whether the machine is converged; the document on stdout was asked for and is
    kept by whoever asked, so it carries the items behind every count. Written as
    the document, the file measured 127 KB against 2.8 KB for the same walk.
    """
    sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)

    ran = cli('check', '--json')
    written = json.loads(sandbox.status_file.read_text())

    assert [row['address'] for row in written['resources']] == addresses(ran)
    assert [row['verdict'] for row in written['resources']] == [row['verdict'] for row in ran.document['resources']]
    assert written['verdict'] == ran.document['verdict']
    assert not any(key in row for row in written['resources'] for key in ('findings', 'others', 'examined', 'invalid'))
