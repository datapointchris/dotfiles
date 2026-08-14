"""`~/.env` and the git identity, driven through the front door.

The two resources a machine is *identified* by, and the two whose findings a
person rather than `apply` usually has to settle. They are measured together
because they answer one question from opposite sides: `env` says which machine
this is and what it wants running, `identity` says who its commits come from.
Neither reads `packages.yml`, so a row here can attribute its exit code to the
one file it wrote.

Every state is built out of real files under the sandbox — a manifest, a
`flags.yml`, `~/.env` itself, and a git configuration git actually reads —
because both resources measure files and nothing else. Nothing in `src/dotfiles/`
is patched, and no test asserts against the developer's own machine.

**The pairing is what most of this pins.** `plan` and `check` are two folds over
one measurement: `plan` keeps what `apply` would repair and `check` keeps what
only a person can. A state appearing under both, or under neither, is the failure
these matrices exist to catch — it is what made a scheduled unit sit permanently
failed on a healthy box.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from dotfiles import envfile
from dotfiles.vocabulary import ExitCode
from matrix import harness
from matrix.harness import Invocation
from matrix.harness import Sandbox
from matrix.harness import resource
from matrix.harness import unwrapped

Run = Callable[..., Invocation]
Arrange = Callable[[Sandbox], None]

MACOS_MACHINE: dict[str, Any] = {'machine': 'other', 'platform': 'macos'}

ALPHA_ON: dict[str, Any] = {'flags': [{'name': 'ALPHA_FLAG', 'description': 'first flag', 'default': True}]}
ALPHA_OFF: dict[str, Any] = {'flags': [{'name': 'ALPHA_FLAG', 'description': 'first flag', 'default': False}]}

LOCAL_VALUE: dict[str, Any] = {'required': [{'name': 'MATRIX_LOCAL_VALUE', 'description': 'an employer hostname'}]}
"""A name no shell on any machine exports, so the register is answered by the
sandbox alone. `WINDOWS_USER` would be the real one and is deliberately not used:
`settings.resolve` reads `os.environ` for a value with no `SHARED_PATHS` entry, so
a developer who happened to export one would converge a row built to drift."""

SECRET = 'export OPENAI_API_KEY=sk-matrix-secret\n'
"""What the real file carries below the marker, and the thing a regeneration must
never lose."""

IDENTITY = '[user]\n\tname = Synthetic Box\n\temail = box@example.invalid\n'
"""The identity `Sandbox.settle` writes, restated where a test rewrites the file."""


# ─────────────────────────────────────────────────────────────────────────────
# Building one machine's state
# ─────────────────────────────────────────────────────────────────────────────


def redeclare(sandbox: Sandbox, manifest: dict[str, Any] | None = None, flags: dict[str, Any] | None = None) -> None:
    """Change the declaration and leave `~/.env` as it was, which is the drift.

    `sandbox.declare` settles afterwards, so it can express what a machine
    declares and never what one has fallen behind. This is the other half: the
    repo moved and the machine has not regenerated, which is how a flag's new
    default reaches nothing.
    """
    harness.write_declaration(sandbox.repo, manifest=manifest or harness.MINIMAL_MANIFEST, flags=flags, machine=sandbox.machine)


def below_the_marker(sandbox: Sandbox, *lines: str) -> None:
    """Append hand-edited assignments, where a real machine keeps its secrets."""
    with sandbox.env_file.open('a') as handle:
        handle.writelines(lines)


def git_config(sandbox: Sandbox, name: str, text: str) -> Path:
    """One file in the chain git assembles this machine's configuration from.

    Written under `$XDG_CONFIG_HOME`, which is where git looks for the global
    config and where `Sandbox.settle` puts the entry point. That is a real knob
    git honours, so the configuration under test is assembled by git itself.
    """
    path = sandbox.config / 'git' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


# ─────────────────────────────────────────────────────────────────────────────
# ~/.env: what each state looks like to each verb
# ─────────────────────────────────────────────────────────────────────────────


def converged(sandbox: Sandbox) -> None:
    """The sandbox as built. Named so the matrix has a row for the baseline."""


def no_env_file(sandbox: Sandbox) -> None:
    sandbox.env_file.unlink()


def flag_default_moved(sandbox: Sandbox) -> None:
    sandbox.declare(flags=ALPHA_OFF)
    redeclare(sandbox, flags=ALPHA_ON)


def flag_overridden_below_the_marker(sandbox: Sandbox) -> None:
    sandbox.declare(flags=ALPHA_ON)
    below_the_marker(sandbox, 'export ALPHA_FLAG=false\n')


def identity_overridden_below_the_marker(sandbox: Sandbox) -> None:
    below_the_marker(sandbox, 'export MACHINE="elsewhere"\n')


def required_value_unset(sandbox: Sandbox) -> None:
    sandbox.declare(flags=LOCAL_VALUE)


def required_value_answered(sandbox: Sandbox) -> None:
    sandbox.declare(flags=LOCAL_VALUE)
    below_the_marker(sandbox, 'export MATRIX_LOCAL_VALUE=some-employer-host\n')


def required_file_absent(sandbox: Sandbox) -> None:
    sandbox.declare(flags={'required_files': [{'name': 'local.sh', 'path': str(sandbox.home / 'local.sh'), 'description': 'shell code'}]})


def required_file_present(sandbox: Sandbox) -> None:
    required_file_absent(sandbox)
    (sandbox.home / 'local.sh').write_text('# machine-local\n')


def flag_nothing_declares(sandbox: Sandbox) -> None:
    below_the_marker(sandbox, 'export NVIM_AI_ENABLED=false\n')


def flag_nothing_declares_in_the_generated_section(sandbox: Sandbox) -> None:
    """The same name, in the other half of the file, and a different answer.

    Above the marker it is `apply`'s to remove, so it is drift and no person is
    needed. Below it, `apply` owns nothing and only a person can act, which is the
    row above this one. The pair is here rather than in two standalone tests
    because the question is which of `plan` and `check` claims it — one, never
    both.
    """
    generated_line(sandbox, 'export NVIM_AI_ENABLED=false')


def unreadable_config_toml(sandbox: Sandbox) -> None:
    config = sandbox.config / 'dotfiles' / 'config.toml'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('repos_registry = "unterminated\n')


ENV_STATES = [
    pytest.param(converged, ExitCode.CONVERGED, 0, ExitCode.CONVERGED, 0, id='converged'),
    pytest.param(no_env_file, ExitCode.DRIFT, 1, ExitCode.CONVERGED, 0, id='no-env-file'),
    pytest.param(flag_default_moved, ExitCode.DRIFT, 1, ExitCode.CONVERGED, 0, id='flag-default-moved'),
    pytest.param(flag_overridden_below_the_marker, ExitCode.CONVERGED, 0, ExitCode.CONVERGED, 0, id='flag-overridden-by-hand'),
    pytest.param(identity_overridden_below_the_marker, ExitCode.CONVERGED, 0, ExitCode.ISSUE, 1, id='identity-overridden-by-hand'),
    pytest.param(required_value_unset, ExitCode.CONVERGED, 0, ExitCode.ISSUE, 1, id='required-value-unset'),
    pytest.param(required_value_answered, ExitCode.CONVERGED, 0, ExitCode.CONVERGED, 0, id='required-value-answered'),
    pytest.param(required_file_absent, ExitCode.CONVERGED, 0, ExitCode.ISSUE, 1, id='required-file-absent'),
    pytest.param(required_file_present, ExitCode.CONVERGED, 0, ExitCode.CONVERGED, 0, id='required-file-present'),
    pytest.param(flag_nothing_declares, ExitCode.CONVERGED, 0, ExitCode.ISSUE, 1, id='flag-nothing-declares'),
    pytest.param(
        flag_nothing_declares_in_the_generated_section,
        ExitCode.DRIFT,
        1,
        ExitCode.CONVERGED,
        0,
        id='flag-nothing-declares-generated',
    ),
    pytest.param(unreadable_config_toml, ExitCode.CONVERGED, 0, ExitCode.ISSUE, 1, id='unreadable-config-toml'),
]
"""One machine state per row, with what each verb makes of it.

The four columns are the whole contract: a state is drift, or it is a finding,
and no state is both. Reading down the two exit-code columns says which is which
without opening a single assertion — `apply` repairs the generated half of the
file, and every hand-edited or machine-local thing below it belongs to a person.
"""


@pytest.mark.parametrize(('arrange', 'planned', 'pending', 'checked', 'attention'), ENV_STATES)
def test_plan_and_check_keep_opposite_halves_of_one_env_measurement(
    sandbox: Sandbox,
    cli: Run,
    arrange: Arrange,
    planned: ExitCode,
    pending: int,
    checked: ExitCode,
    attention: int,
) -> None:
    """Both verbs against one state, in one test, because the pair is the claim.

    Asserted apart, each row reads as an isolated verdict and the property that
    matters is invisible: nothing this resource finds is reported by both verbs,
    and nothing it finds is reported by neither.
    """
    arrange(sandbox)

    ran = cli('env', 'plan', '--json')
    assert (ran.exit_code, resource(ran, 'env')['pending']) == (planned, pending)

    ran = cli('env', 'check', '--json')
    assert (ran.exit_code, resource(ran, 'env')['attention']) == (checked, attention)


@pytest.mark.parametrize(
    ('arrange', 'checked'),
    [
        pytest.param(no_env_file, ExitCode.CONVERGED, id='no-env-file'),
        pytest.param(flag_default_moved, ExitCode.CONVERGED, id='flag-default-moved'),
        pytest.param(identity_overridden_below_the_marker, ExitCode.ISSUE, id='identity-overridden-by-hand'),
        pytest.param(required_value_unset, ExitCode.ISSUE, id='required-value-unset'),
        pytest.param(required_file_absent, ExitCode.ISSUE, id='required-file-absent'),
    ],
)
def test_an_apply_settles_what_plan_planned_and_reports_the_rest_unchanged(
    sandbox: Sandbox, cli: Run, arrange: Arrange, checked: ExitCode
) -> None:
    """The write half of the same matrix, and the reason the split is worth having.

    `plan` is empty afterwards on every row, including the three `apply` could do
    nothing about — because it never planned them. `check` is unchanged on exactly
    those three, which is what stops a machine-local value nobody set from making
    a freshly-installed box look like a failed install.
    """
    arrange(sandbox)

    assert cli('env', 'apply').exit_code == ExitCode.CONVERGED
    assert cli('env', 'plan').exit_code == ExitCode.CONVERGED
    assert cli('env', 'check').exit_code == checked


def test_a_regeneration_keeps_every_hand_written_line_below_the_marker(sandbox: Sandbox, cli: Run) -> None:
    """The property the whole marker design exists for. The real file carries API
    tokens beside the generated flags, so a regeneration that lost the half below
    the marker would take a machine's secrets with it — and the drift being
    repaired here is precisely the one that rewrites the half above."""
    below_the_marker(sandbox, SECRET)
    redeclare(sandbox, flags=ALPHA_ON)

    cli('env', 'apply')

    written = sandbox.env_file.read_text()
    assert SECRET in written
    assert 'export ALPHA_FLAG="${ALPHA_FLAG:-true}"' in written


def test_an_apply_with_nothing_to_repair_takes_no_backup_over_the_last_one(sandbox: Sandbox, cli: Run) -> None:
    """A finding only a person can settle must not provoke a write.

    The loop this rules out was measured: STALE, apply, DONE, STALE again, with a
    fresh `.env.bak` taken over the last one every round until the backup is of
    nothing. The absent backup is the evidence, because `envfile.write` copies the
    file before it touches it — so a backup existing means the file was rewritten.
    """
    identity_overridden_below_the_marker(sandbox)

    cli('env', 'apply')

    assert not (sandbox.home / '.env.bak').exists()


# ─────────────────────────────────────────────────────────────────────────────
# env show
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    'named',
    [
        pytest.param('box', id='this-machine'),
        pytest.param('other', id='another-machine'),
    ],
)
def test_show_renders_the_generated_section_for_the_machine_named(sandbox: Sandbox, cli: Run, named: str) -> None:
    """`--machine` selects a manifest, so `show` answers for a box this one is not.

    That is what makes it useful before an install: the file it prints is the file
    `apply` would write on the machine named, and this machine's own `~/.env` takes
    no part in it.
    """
    harness.write_declaration(sandbox.repo, manifest=MACOS_MACHINE, machine='other')

    ran = cli('env', 'show', '--machine', named)

    assert ran.exit_code == ExitCode.CONVERGED
    assert f'export MACHINE="${{MACHINE:-{named}}}"' in ran.stdout


def test_show_writes_nothing_at_all(sandbox: Sandbox, cli: Run) -> None:
    """The rehearsal of a write, on a machine that has never had one. A `show` that
    created the file would make the first `plan` after it report a converged
    machine nobody applied to."""
    sandbox.env_file.unlink()

    cli('env', 'show')

    assert not sandbox.env_file.exists()


def test_show_names_a_required_value_without_carrying_one(sandbox: Sandbox, cli: Run) -> None:
    """The repo declares that a machine needs a value and must never hold what it
    is, so the generated section names it in a comment and assigns nothing."""
    sandbox.declare(flags=LOCAL_VALUE)

    ran = cli('env', 'show')

    assert 'MATRIX_LOCAL_VALUE - an employer hostname' in ran.stdout
    assert 'export MATRIX_LOCAL_VALUE' not in ran.stdout


# ─────────────────────────────────────────────────────────────────────────────
# The git identity, and the arrangement it arrives through
# ─────────────────────────────────────────────────────────────────────────────


def one_file(sandbox: Sandbox) -> None:
    """What `settle` leaves: an entry point that carries the identity itself."""


def three_file_chain(sandbox: Sandbox) -> None:
    """The real arrangement in miniature — entry point, shared config, identity.

    Three files rather than one because the identity arriving through a chain of
    includes is the thing that makes this configuration hard to follow by hand,
    and the reason `identity show` draws a tree at all.
    """
    personal = git_config(sandbox, 'personal.gitconfig', IDENTITY)
    shared = git_config(sandbox, 'common.gitconfig', f'[core]\n\tpager = less\n[include]\n\tpath = {personal}\n')
    git_config(sandbox, 'config', f'[include]\n\tpath = {shared}\n')


def no_identity(sandbox: Sandbox) -> None:
    (sandbox.config / 'git' / 'config').unlink()


def only_a_name(sandbox: Sandbox) -> None:
    git_config(sandbox, 'config', '[user]\n\tname = Synthetic Box\n')


def home_gitconfig_masks_the_chain(sandbox: Sandbox) -> None:
    """git prefers `~/.gitconfig` over the XDG entry point, so one sitting there
    silently outranks every include below it."""
    (sandbox.home / '.gitconfig').write_text('[user]\n\tname = Someone Else\n\temail = else@example.invalid\n')


def symlinked_entry_point(sandbox: Sandbox) -> None:
    """git follows a symlink when it writes, so an entry point linked into a
    checkout takes any identity written through it into the repo."""
    entry = sandbox.home / '.config' / 'git' / 'config'
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.symlink_to(sandbox.config / 'git' / 'config')


def two_files_disagree(sandbox: Sandbox) -> None:
    """One key, two files, two values — an ambiguity a reader cannot see, because
    a listing prints both rows with nothing saying which git read last."""
    other = git_config(sandbox, 'other.gitconfig', '[core]\n\tpager = delta\n')
    git_config(sandbox, 'config', f'{IDENTITY}[core]\n\tpager = less\n[include]\n\tpath = {other}\n')


IDENTITY_STATES = [
    pytest.param(one_file, ExitCode.CONVERGED, 0, id='one-file'),
    pytest.param(three_file_chain, ExitCode.CONVERGED, 0, id='three-file-include-chain'),
    pytest.param(no_identity, ExitCode.ISSUE, 2, id='no-identity'),
    pytest.param(only_a_name, ExitCode.ISSUE, 1, id='only-a-name'),
    pytest.param(home_gitconfig_masks_the_chain, ExitCode.ISSUE, 1, id='home-gitconfig-masks-the-chain'),
    pytest.param(symlinked_entry_point, ExitCode.ISSUE, 1, id='symlinked-entry-point'),
    pytest.param(two_files_disagree, ExitCode.ISSUE, 1, id='two-files-disagree'),
]


@pytest.mark.parametrize(('arrange', 'checked', 'attention'), IDENTITY_STATES)
def test_check_reports_the_identity_and_the_arrangement_around_it(
    sandbox: Sandbox, cli: Run, arrange: Arrange, checked: ExitCode, attention: int
) -> None:
    """Two kinds of finding under one verb: what is wrong with the identity, and
    what is wrong with the chain that produces it. Both change what a commit
    carries, and neither is visible in `git config --get user.email`."""
    arrange(sandbox)

    ran = cli('identity', 'check', '--json')

    assert (ran.exit_code, resource(ran, 'identity')['attention']) == (checked, attention)


@pytest.mark.parametrize(('arrange', 'checked', 'attention'), IDENTITY_STATES)
def test_plan_is_converged_whatever_is_wrong_with_the_identity(
    sandbox: Sandbox, cli: Run, arrange: Arrange, checked: ExitCode, attention: int
) -> None:
    """An identity is personal and per-machine, so the repo has nothing to write
    here and `plan` has nothing to promise. The verb exists so that a resource
    answering `check` and not `plan` cannot happen — and it answers zero every
    time, including on the machine `check` exits 3 for.

    `attention` still travels on the row, which is what lets `plan -v` report the
    other verb's findings without adopting them.
    """
    arrange(sandbox)

    ran = cli('identity', 'plan', '--json')

    assert ran.exit_code == ExitCode.CONVERGED
    assert resource(ran, 'identity')['pending'] == 0
    assert resource(ran, 'identity')['attention'] == attention


def test_the_converged_row_names_the_identity_and_how_many_files_produced_it(sandbox: Sandbox, cli: Run) -> None:
    """The file count is the part worth stating unasked: an address alone reads as
    though one file set it, and the difficulty here is that several did."""
    three_file_chain(sandbox)

    ran = cli('identity', 'check', '--json')

    assert resource(ran, 'identity')['detail'] == 'Synthetic Box <box@example.invalid>, from 3 config file(s)'


def test_a_home_gitconfig_takes_the_whole_chain_out_of_the_reading(sandbox: Sandbox, cli: Run) -> None:
    """Not merely outranking it — git stops reading the XDG entry point at all, so
    every include below it contributes nothing. That is why one file sitting in
    `$HOME` is a finding rather than a preference."""
    three_file_chain(sandbox)
    home_gitconfig_masks_the_chain(sandbox)

    ran = cli('identity', 'show', '--json')

    assert ran.document['files'] == [str(sandbox.home / '.gitconfig')]
    assert ran.document['masked_by'] == str(sandbox.home / '.gitconfig')


def test_show_draws_the_include_chain_in_the_order_git_read_it(sandbox: Sandbox, cli: Run) -> None:
    """`git config --list --show-origin` is the flat projection of this and is what
    made the arrangement hard to follow: it prints each leaf beside its file with
    nothing saying the file was reached through two others."""
    three_file_chain(sandbox)

    ran = cli('identity', 'show', '--json')

    assert ran.exit_code == ExitCode.CONVERGED
    assert ran.document['files'] == [
        str(sandbox.config / 'git' / 'config'),
        str(sandbox.config / 'git' / 'common.gitconfig'),
        str(sandbox.config / 'git' / 'personal.gitconfig'),
    ]
    assert [(one['target'], one['taken']) for one in ran.document['includes']] == [
        (str(sandbox.config / 'git' / 'common.gitconfig'), True),
        (str(sandbox.config / 'git' / 'personal.gitconfig'), True),
    ]


def test_show_names_the_file_that_wins_a_key_two_files_set(sandbox: Sandbox, cli: Run) -> None:
    """The winner is the last file git read, which is a fact about include order
    that neither file states. Exits 3, because a reader cannot predict the value
    from either file alone."""
    two_files_disagree(sandbox)

    ran = cli('identity', 'show', '--json')

    assert ran.exit_code == ExitCode.ISSUE
    (conflict,) = ran.document['conflicts']
    assert conflict['key'] == 'core.pager'
    assert conflict['winner'] == {'origin': str(sandbox.config / 'git' / 'other.gitconfig'), 'value': 'delta'}
    assert [loser['value'] for loser in conflict['losers']] == ['less']


def test_a_repeated_include_is_never_itself_a_conflict(sandbox: Sandbox, cli: Run) -> None:
    """Every hop in the chain is spelled `include.path`, so a detector reading them
    as one key called the entire layering one enormous conflict with itself — on a
    machine with nothing wrong with it, which is how a detector earns being
    ignored."""
    three_file_chain(sandbox)

    assert cli('identity', 'show', '--json').document['conflicts'] == []
    assert cli('identity', 'check').exit_code == ExitCode.CONVERGED


def test_show_refuses_rather_than_reporting_a_machine_with_no_configuration(sandbox: Sandbox, cli: Run) -> None:
    """git answers nothing when there is no global config to list, and the refusal
    goes to stderr with no document behind it — so a `--json` caller reads an exit
    code rather than an empty layering it would have to tell apart from a real
    one."""
    no_identity(sandbox)

    ran = cli('identity', 'show', '--json')

    assert ran.exit_code == ExitCode.ISSUE
    assert ran.stdout == ''
    assert 'git would not report its configuration' in ran.stderr


# ─────────────────────────────────────────────────────────────────────────────
# The machine contract: which stream, and what shape
# ─────────────────────────────────────────────────────────────────────────────


DOCUMENT_KEYS = {'version', 'verb', 'machine', 'checked', 'verdict', 'resources'}
"""The interchange document's own fields, which a resource-scoped read emits too.

Whole-set equality, because the wrapping is the claim: this door answered a bare
`ResourceResult` for one result and an array of them for several, so a consumer
branched on a shape decided by a `needed_by` edge it never saw.
"""

RESOURCE_RESULT_KEYS = {
    'address',
    'verdict',
    'detail',
    'findings',
    'others',
    'examined',
    'invalid',
    'pending',
    'attention',
    'unmeasured',
    'privileged',
    'seconds',
}
"""Every field `ResourceResult.as_dict` emits.

Asserted as a whole set rather than by picking two of them: the counts are the
answer a caller branches on, the four lists are which items those counts are
about, and one dropped in a refactor would leave every test reading `detail` —
which is prose and says so.
"""


@pytest.mark.parametrize(
    ('address', 'verb'),
    [
        pytest.param('env', 'plan', id='env-plan'),
        pytest.param('env', 'check', id='env-check'),
        pytest.param('identity', 'plan', id='identity-plan'),
        pytest.param('identity', 'check', id='identity-check'),
    ],
)
def test_a_json_run_puts_one_resource_result_on_stdout_and_nothing_beside_it(sandbox: Sandbox, cli: Run, address: str, verb: str) -> None:
    """The two consoles, measured on the pair of resources most likely to warn: one
    reads a file that may not exist and the other shells out to git. A stray
    diagnostic on stdout turns a `--json` parse into a syntax error rather than
    the warning it was."""
    required_value_unset(sandbox)
    no_identity(sandbox)

    ran = cli(address, verb, '--json')

    assert set(ran.document) == DOCUMENT_KEYS
    assert ran.document['verb'] == verb
    assert set(resource(ran, address)) == RESOURCE_RESULT_KEYS
    assert ran.stderr == ''


def test_the_identity_layering_document_carries_the_four_things_a_reader_came_for(sandbox: Sandbox, cli: Run) -> None:
    """Which files are involved, which pulled in which, where two disagree, and
    whether anything is masking the lot. `document` is built from the same three
    properties the tree is drawn from, so the two cannot reach different
    conclusions."""
    three_file_chain(sandbox)

    assert set(cli('identity', 'show', '--json').document) == {'files', 'includes', 'conflicts', 'masked_by'}


@pytest.mark.parametrize(
    ('address', 'verb'),
    [
        pytest.param('env', 'check', id='env-check'),
        pytest.param('identity', 'check', id='identity-check'),
    ],
)
def test_a_human_run_prints_the_verdict_on_stdout_and_its_evidence_on_stderr(sandbox: Sandbox, cli: Run, address: str, verb: str) -> None:
    """The row is the answer and the item rows under it are the working, so the two
    are on different streams — a pipeline reading the verdict gets one line, and a
    person watching gets both."""
    required_value_unset(sandbox)
    no_identity(sandbox)

    ran = cli(address, verb)

    assert ran.exit_code == ExitCode.ISSUE
    assert ran.stdout.startswith('✗ ')
    assert '→ ' in ran.stderr


def test_a_check_lists_what_it_looked_at_and_was_happy_with(sandbox: Sandbox, cli: Run) -> None:
    """The other half of a measurement. `diff` returns only what differs, so
    everything a healthy machine holds was invisible — and the name selecting the
    manifest every other resource resolves against is exactly what someone looking
    at this file wants to see the value of."""
    required_value_unset(sandbox)

    ran = cli('env', 'check')

    assert 'matched MACHINE box' in unwrapped(ran.stderr)


# ─────────────────────────────────────────────────────────────────────────────
# A flag below the marker that parses as neither true nor false
# ─────────────────────────────────────────────────────────────────────────────


def unparseable_flag_below_the_marker(sandbox: Sandbox) -> None:
    sandbox.declare(flags=ALPHA_ON)
    below_the_marker(sandbox, 'export ALPHA_FLAG=maybe\n')


def test_an_unparseable_flag_below_the_marker_is_reported_and_not_planned(sandbox: Sandbox, cli: Run) -> None:
    """The value the shell reads is the one below the marker, so the section `apply`
    owns is not where the wrong value is. `_flags` asks which half wrote it, the way
    `_identity` does, and a value `apply` cannot reach counts as attention rather
    than as work the run intends to do."""
    unparseable_flag_below_the_marker(sandbox)

    ran = cli('env', 'plan', '--json')

    assert ran.exit_code == ExitCode.CONVERGED
    row = resource(ran, 'env')
    assert (row['pending'], row['attention']) == (0, 1)


def test_applying_an_unparseable_flag_writes_nothing(sandbox: Sandbox, cli: Run) -> None:
    """No write means no backup, which is the fact that separates this from the loop
    it used to sit in: an `apply` that reported DONE, rolled `.env.bak` over the last
    one, and left the machine reading `maybe`."""
    unparseable_flag_below_the_marker(sandbox)
    (sandbox.home / '.env.bak').unlink(missing_ok=True)

    assert cli('env', 'apply').exit_code == ExitCode.CONVERGED
    assert not (sandbox.home / '.env.bak').exists()


def test_an_apply_settles_a_flag_that_parses_as_neither_true_nor_false(sandbox: Sandbox, cli: Run) -> None:
    """An `apply` leaves nothing behind that the next `plan` still offers to repair.

    Giving an unparseable value `Repair.AUTOMATIC` without asking which half of the
    file it came from loops for ever on `ALPHA_FLAG=maybe` written below the marker:
    `plan` offers the rewrite, `apply` performs it against the section above, and
    the assignment below stays the last one in the file.
    """
    unparseable_flag_below_the_marker(sandbox)

    cli('env', 'apply')

    assert cli('env', 'plan').exit_code == ExitCode.CONVERGED


# ─────────────────────────────────────────────────────────────────────────────
# A dangling ~/.gitconfig
# ─────────────────────────────────────────────────────────────────────────────


def dangling_home_gitconfig(sandbox: Sandbox) -> None:
    (sandbox.home / '.gitconfig').symlink_to(sandbox.root / 'nothing-here')


def test_check_reports_a_dangling_home_gitconfig_as_masking(sandbox: Sandbox, cli: Run) -> None:
    """`exists` follows a link, so a dangling one reads as absent — while git still
    picks it as the file to write to, which is the whole failure. The resource
    tests `is_symlink` as well, and finds it."""
    dangling_home_gitconfig(sandbox)

    ran = cli('identity', 'check', '--json')

    assert ran.exit_code == ExitCode.ISSUE
    assert '~/.gitconfig' in resource(ran, 'identity')['detail']


def test_show_names_the_dangling_home_gitconfig_that_check_reports(sandbox: Sandbox, cli: Run) -> None:
    """The two surfaces answer the same question with one predicate.

    `identity show` decided masking with `home_config().exists()` and the resource
    decided it with `exists() or is_symlink()`, so the same file on the same
    machine in the same minute was named by `check` and drawn out of `show`'s tree
    — and `show` is the command a person runs *because* `check` named the file.

    One fact derived at two sites that can disagree, which is the cause behind more
    of these faults than any other. Both now read `gitconfig.masking`, which
    carries the reason: a dangling link answers `exists` False and is still the
    file git writes an identity into.
    """
    dangling_home_gitconfig(sandbox)

    assert cli('identity', 'show', '--json').document['masked_by'] == str(sandbox.home / '.gitconfig')


# ─────────────────────────────────────────────────────────────────────────────
# A --machine naming no manifest
# ─────────────────────────────────────────────────────────────────────────────


UNKNOWN_MACHINE = ('--machine', 'nosuch')

READ_VERBS = [
    pytest.param(('env', 'plan'), id='env-plan'),
    pytest.param(('env', 'check'), id='env-check'),
    pytest.param(('env', 'show'), id='env-show'),
    pytest.param(('identity', 'plan'), id='identity-plan'),
    pytest.param(('identity', 'check'), id='identity-check'),
]


def test_the_write_verb_names_the_missing_manifest_and_the_ones_that_exist(sandbox: Sandbox, cli: Run) -> None:
    """The write verb names the manifest it looked for and the ones that exist, and
    answers the code every read verb answers.

    The write verb and the read verbs answer alike, because the typo is the same
    typo whichever verb is given it. A verb diagnosing it as an Issue would be
    reporting a fault in the machine, and the machine is fine.
    """
    ran = cli('env', 'apply', *UNKNOWN_MACHINE)

    assert ran.exit_code == ExitCode.USAGE
    assert 'nosuch: has no manifest at' in unwrapped(ran.stderr)
    assert 'Available: box' in unwrapped(ran.stderr)


@pytest.mark.parametrize('argv', READ_VERBS)
def test_a_read_verb_reports_a_machine_with_no_manifest_rather_than_crashing(sandbox: Sandbox, cli: Run, argv: tuple[str, ...]) -> None:
    """A `--machine` naming no manifest is reported with the name, under exit 2.

    `Session.machine` is lazy precisely so a run that never asks about a machine
    pays nothing, and that once put the first read of the manifest inside the walk
    rather than at `Session.resolve`. `assess` evaluates `session.plan` outside the
    `try` that `_measure` wraps each resource in, so the declaration failing to
    load was not the refusal the walk turns every exception into — it escaped as a
    traceback. `Session.resolve` now reads the manifest itself, which is what puts
    the failure back in front of the handler.

    The code is the one claim this file shares with `test_symlinks.py`,
    `test_auth_credentials.py` and `test_composite.py`, and the latter carries the
    reasoning.
    """
    ran = cli(*argv, *UNKNOWN_MACHINE, catch_exceptions=True)

    assert ran.exit_code == ExitCode.USAGE
    assert 'nosuch' in ran.stderr


# ─────────────────────────────────────────────────────────────────────────────
# The converged sentence on a machine with no identity
# ─────────────────────────────────────────────────────────────────────────────


def test_the_identity_row_names_both_missing_fields_where_the_machine_has_none(sandbox: Sandbox, cli: Run) -> None:
    """`plan` is right that there is nothing to change, and the sentence beside the
    tick says which fields the machine is missing rather than laying them out as an
    address. The file count stays, because how many files were read and set no
    identity is the difference between an unconfigured machine and a broken chain."""
    git_config(sandbox, 'config', '[core]\n\tpager = less\n')

    ran = cli('identity', 'plan', '--json')

    assert ran.exit_code == ExitCode.CONVERGED
    assert resource(ran, 'identity')['detail'] == 'no name and no email, from 1 config file(s)'


def test_the_converged_identity_row_says_a_machine_has_no_identity(sandbox: Sandbox, cli: Run) -> None:
    """An empty address is never rendered as one.

    `Observed.who` built `f'{name} <{email}>'` from two values that may both be
    empty, and `summary` is what the converged row prints — so a machine with none
    got `✓ identity  <>`, a tick beside an identity of nobody, on a machine where
    `user.useConfigOnly` means the next commit is refused. `check` reports it
    properly one verb away, which is what made the tick misread as the whole answer
    rather than as half of a pair.

    The verdict stays converged either way, because there is still nothing for
    `apply` to write.
    """
    git_config(sandbox, 'config', '[core]\n\tpager = less\n')

    assert '<>' not in resource(cli('identity', 'plan', '--json'), 'identity')['detail']


def test_the_identity_row_names_the_one_field_a_machine_is_missing(sandbox: Sandbox, cli: Run) -> None:
    """Half an identity is the same fault at half strength, and it is the state a
    machine reaches by setting `user.name` and stopping. `Synthetic Box <>` reads as
    an address that is empty rather than as one that was never set."""
    only_a_name(sandbox)

    ran = cli('identity', 'plan', '--json')

    assert resource(ran, 'identity')['detail'] == 'Synthetic Box and no email, from 1 config file(s)'


def generated_line(sandbox: Sandbox, line: str) -> None:
    """Insert an assignment into the managed section, above the OVERRIDES marker.

    Where a variable the declaration used to write sits after it stops writing it.
    `below_the_marker` is the other half of the file and a different question: that
    is where a machine keeps what is its own, and `apply` never touches it.
    """
    text = sandbox.env_file.read_text()
    sandbox.env_file.write_text(text.replace(envfile.MARKER, f'{line}\n\n{envfile.MARKER}', 1))


def test_a_generated_line_the_declaration_no_longer_writes_is_drift(sandbox: Sandbox, cli: Run) -> None:
    """Reported by name, and repairable, because `apply` rebuilds the section.

    The managed half is regenerated from `render` in full, so a line nothing
    declares is one rewrite from gone.

    The name here is deliberately not flag-shaped. `_undeclared` identifies a
    stray by whether it ends `_ENABLED` or `_DEBUG`, which is a convention rather
    than the declaration, so a variable named anything else is invisible to it.
    """
    sandbox.declare()
    generated_line(sandbox, 'export DOTFILES_LAYERS="pkg/apt os/linux"')

    ran = cli('env', 'plan', '--json')

    assert ran.exit_code == ExitCode.DRIFT
    assert resource(ran, 'env')['pending'] == 1


def test_an_apply_drops_the_line_and_keeps_what_is_below_the_marker(sandbox: Sandbox, cli: Run) -> None:
    """The repair is the regeneration, so the orphan goes and a secret stays.

    Both halves in one case because they are one act: `apply` rewrites everything
    above the marker and copies everything below it, so a check that the orphan
    went is only half an answer without a check that the file was not truncated.
    """
    sandbox.declare()
    generated_line(sandbox, 'export DOTFILES_LAYERS="pkg/apt os/linux"')
    below_the_marker(sandbox, 'export A_SECRET="keep me"\n')

    assert cli('env', 'apply').exit_code == ExitCode.CONVERGED

    settled = sandbox.env_file.read_text()
    assert 'DOTFILES_LAYERS' not in settled
    assert 'A_SECRET' in settled
    assert cli('env', 'plan').exit_code == ExitCode.CONVERGED
