"""Two resources that measure a person's access and repair none of it.

`auth` asks whether the tools a manifest names under `auth:` can show a
credential. `credentials` asks whether the git credential helpers this machine
resolved to will start. Both are read-only by construction — every finding is
`Repair.BY_HAND`, and neither noun has an `apply` verb at all — so the pair is
where the exit-code contract is at its sharpest. A logged-out CLI is *wrong* and
never *drift*, so `check` answers 3 on the same machine where `plan` answers 0.

Every subject is synthetic. A declared tool is a shell script in the sandbox's
bin, a credential helper is a file under `tmp_path` named by the sandbox's own
`$XDG_CONFIG_HOME/git/config`, and the one probe that asks for a real credential
is answered by a script this module wrote. Nothing consults which tools the
machine running the suite happens to have logged in, and nothing here can open a
browser.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from dotfiles import machine as machines
from dotfiles.vocabulary import ExitCode
from matrix.harness import ANSWERS as RUNS_AND_SAYS_NOTHING
from matrix.harness import REFUSED
from matrix.harness import Invocation
from matrix.harness import Sandbox

Arrange = Callable[[Sandbox, pytest.MonkeyPatch], None]

TOOL = 'nomad'
"""One of the four keychain CLIs, which share a probe and answer locally.

Named once because every auth row below is about the same tool in a different
state, and the state is what the row is measuring. A file-answered probe is
exercised too — `atuin` — because the two halves of `PROBES` fail differently.
"""

LOGGED_IN = '#!/bin/sh\nprintf "Logged in as synthetic\\n"\nexit 0\n'
LOGGED_OUT = REFUSED
"""What `<tool> auth status` does on either side of a login.

Exit status alone, because that is all the probe reads: `ErrNotLoggedIn` is exit
1 in the shared implementation the four CLIs use.
"""

PE_HEADER = b'MZ\x90\x00\x03\x00\x00\x00not a real executable'
"""Enough of a DOS header to look like a Windows binary and not enough to be one.

`execve` refuses a file with no ELF magic and no shebang with ENOEXEC — the same
errno a real PE32 helper gets on a WSL box whose binfmt handler has gone — so the
failure this resource was built for reproduces on Linux with no WSL involved.
"""


def declares(sandbox: Sandbox, *tools: str) -> None:
    """A manifest whose `auth:` roster is these tools and which declares nothing else."""
    sandbox.declare(manifest={'machine': sandbox.machine, 'platform': 'linux', 'auth': list(tools)})


def git_config(sandbox: Sandbox) -> Path:
    """The file `git config --global` resolves to under this sandbox.

    `$XDG_CONFIG_HOME` points into the sandbox and `~/.gitconfig` is absent, so
    this is the entry point git reads — which is what makes `gitconfig.read()` a
    real seam here rather than something to stub.
    """
    return sandbox.config / 'git' / 'config'


def configure(sandbox: Sandbox, *lines: str) -> Path:
    """Add a credential section to that file, keeping the identity `settle` wrote.

    Appended rather than replaced, and never before a `declare`: `declare` settles
    the machine again and rewrites this file, so a helper written first is gone by
    the time the command runs.
    """
    entry = git_config(sandbox)
    entry.write_text(entry.read_text() + '\n'.join(lines) + '\n')
    return entry


def helper_script(sandbox: Sandbox, name: str, script: str) -> Path:
    """A credential helper on disk, addressed by path rather than by PATH."""
    helper = sandbox.root / name
    helper.write_text(script)
    helper.chmod(0o755)
    return helper


# ─────────────────────────────────────────────────────────────────────────────
# auth: one roster, five states
# ─────────────────────────────────────────────────────────────────────────────


def a_tool_with_a_credential(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    sandbox.shadow(TOOL, LOGGED_IN)
    declares(sandbox, TOOL)


def a_tool_without_a_credential(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    sandbox.shadow(TOOL, LOGGED_OUT)
    declares(sandbox, TOOL)


def a_tool_that_is_not_installed(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    """The declared binary absent from PATH, which is a question that cannot be asked.

    `PATH` drops `/usr/bin` for this row alone. The sandbox keeps it so its own
    helpers can run, and with it a machine that happens to package one of these
    CLIs would answer the probe — which is the machine-dependence the sandbox
    exists to remove. Nothing in an `auth` walk shells out to anything but the
    declared tools and the `gh` the sandbox already shadows.
    """
    declares(sandbox, TOOL)
    monkeypatch.setenv('PATH', str(sandbox.bin))


def a_tool_no_probe_implements(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    declares(sandbox, 'invented')


def a_machine_declaring_nothing(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    declares(sandbox)


AUTH_STATES = [
    pytest.param(a_tool_with_a_credential, ExitCode.CONVERGED, id='has-a-credential'),
    pytest.param(a_tool_without_a_credential, ExitCode.ISSUE, id='has-none'),
    pytest.param(a_tool_that_is_not_installed, ExitCode.CONVERGED, id='not-installed'),
    pytest.param(a_tool_no_probe_implements, ExitCode.CONVERGED, id='unknown-tool'),
    pytest.param(a_machine_declaring_nothing, ExitCode.CONVERGED, id='declares-nothing'),
]
"""Each roster state, and what `check` makes of it.

Only one of the five is *wrong*. A tool that is not installed and a name no probe
implements are both unmeasured — the packages resource already reports the first,
and `machines check` reports the second against the declaration — so neither
reaches the exit code from here.
"""


@pytest.mark.parametrize(('arrange', 'checked'), AUTH_STATES)
def test_auth_check_reports_only_the_tool_that_needs_a_person(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation], arrange: Arrange, checked: ExitCode
) -> None:
    """3 for a login nobody can automate, 0 for everything else.

    The three converged rows are the load-bearing ones. A resource that reported
    every unmeasurable tool would exit 3 on a machine mid-install, which is how a
    scheduled check earns being switched off.
    """
    arrange(sandbox, monkeypatch)

    ran = cli('auth', 'check', '--json')

    assert ran.exit_code == checked
    assert ran.document['address'] == 'auth'


@pytest.mark.parametrize(('arrange', 'checked'), AUTH_STATES)
def test_auth_plan_is_converged_whatever_the_roster_turned_out_to_be(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation], arrange: Arrange, checked: ExitCode
) -> None:
    """`plan` rehearses `apply`, and `apply` has nothing to do here.

    Parameterized over the same five states rather than the interesting one,
    because the claim is that *no* roster state produces work — a row that exits 1
    would be `apply` promising a login it cannot perform.
    """
    arrange(sandbox, monkeypatch)

    ran = cli('auth', 'plan', '--json')

    assert ran.exit_code == ExitCode.CONVERGED
    assert ran.document['pending'] == 0


@pytest.mark.parametrize(
    ('arrange', 'attention', 'unmeasured'),
    [
        pytest.param(a_tool_with_a_credential, 0, 0, id='has-a-credential'),
        pytest.param(a_tool_without_a_credential, 1, 0, id='has-none'),
        pytest.param(a_tool_that_is_not_installed, 0, 1, id='not-installed'),
        pytest.param(a_tool_no_probe_implements, 0, 1, id='unknown-tool'),
        pytest.param(a_machine_declaring_nothing, 0, 0, id='declares-nothing'),
    ],
)
def test_the_counts_separate_a_finding_from_a_question_that_could_not_be_asked(
    sandbox: Sandbox,
    monkeypatch: pytest.MonkeyPatch,
    cli: Callable[..., Invocation],
    arrange: Arrange,
    attention: int,
    unmeasured: int,
) -> None:
    """The numbers behind the exit code, which is the part a caller branches on.

    `detail` is prose and will be reworded; a test asserting on the sentence is
    asserting on a rendering. The counts are the answer, and they say which bucket
    each state landed in rather than only that it stayed out of the exit code.
    """
    arrange(sandbox, monkeypatch)

    ran = cli('auth', 'check', '--json')

    assert (ran.document['attention'], ran.document['unmeasured']) == (attention, unmeasured)


def test_a_file_answered_probe_reaches_the_same_two_verdicts_as_a_cli_one(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """`atuin` is answered by a session file rather than by a subprocess.

    Both halves of `PROBES` are exercised because they fail differently: a CLI
    probe reads an exit status, and this one reads `$XDG_DATA_HOME`. A sandbox that
    moved only `PATH` would leave this one reading the real home.
    """
    sandbox.shadow('atuin')
    declares(sandbox, 'atuin')

    logged_out = cli('auth', 'check', '--json')

    session = sandbox.data / 'atuin' / 'session'
    session.parent.mkdir(parents=True)
    session.write_text('token\n')
    logged_in = cli('auth', 'check', '--json')

    assert (logged_out.exit_code, logged_in.exit_code) == (ExitCode.ISSUE, ExitCode.CONVERGED)


def test_the_github_row_is_answered_by_the_runs_own_measurement(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation]
) -> None:
    """`gh` is the one roster entry with no probe of its own.

    `evidence.have_github_credentials` has already answered it for the resources
    that gate an install on a credential, so a second probe here would spend the
    cost twice for a verdict the run holds — and two probes can disagree inside one
    report. The sandbox shadows `gh` with a binary that refuses and deletes the
    token, so the token is what moves this row, and the advice is the one sentence
    `packages` uses for the same fault.
    """
    declares(sandbox, 'gh')

    logged_out = cli('auth', 'check')

    monkeypatch.setenv('GITHUB_TOKEN', 'ghp_synthetic')
    logged_in = cli('auth', 'check')

    assert (logged_out.exit_code, logged_in.exit_code) == (ExitCode.ISSUE, ExitCode.CONVERGED)
    assert 'gh auth login' in logged_out.output


def test_the_finding_carries_the_login_command_rather_than_running_it(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation]
) -> None:
    """A login is a browser flow, a password or a device code.

    The whole of what `apply` can do about one is print the sentence that names
    it, so the sentence is the finding rather than a hint attached to a repair.
    """
    a_tool_without_a_credential(sandbox, monkeypatch)

    ran = cli('auth', 'check')

    assert f'{TOOL} auth login' in ran.output


# ─────────────────────────────────────────────────────────────────────────────
# auth never repairs
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('noun', ['auth', 'credentials'])
def test_neither_noun_offers_an_apply_verb_at_all(cli: Callable[..., Invocation], noun: str) -> None:
    """Not a `perform` that refuses — no command to reach one.

    A resource whose every change is `BY_HAND` would answer an `apply` by doing
    nothing and reporting success, which reads as a repair that happened. The verb
    is absent so the question is a usage error instead.
    """
    ran = cli(noun, 'apply', catch_exceptions=True)

    assert ran.exit_code == ExitCode.USAGE


def test_a_whole_machine_apply_leaves_a_logged_out_tool_logged_out(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation]
) -> None:
    """`apply` reports the finding and converges, because the finding is not its work.

    Exiting non-zero here would make every freshly-built box look like a failed
    install until somebody sat down and logged in — and `apply` runs unattended on
    exactly those boxes.
    """
    a_tool_without_a_credential(sandbox, monkeypatch)

    ran = cli('apply')

    assert ran.exit_code == ExitCode.CONVERGED
    assert TOOL in ran.output


def test_a_check_of_the_whole_machine_is_where_the_same_tool_becomes_an_issue(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation]
) -> None:
    """The pair that makes the two verbs legible: one machine, two answers.

    `apply` above converged on this exact state. Nothing changed in between, so
    the difference is entirely which question was asked.
    """
    a_tool_without_a_credential(sandbox, monkeypatch)

    assert cli('check').exit_code == ExitCode.ISSUE


def test_a_name_no_probe_implements_is_the_declarations_problem_and_not_auths(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation]
) -> None:
    """`auth check` is quiet about it and `machines check` names it.

    Both are right. The tool was never asked about, so `auth` has no evidence to
    report; the manifest names something nothing implements, which is a fault in
    the declaration and is where a typo actually gets caught.
    """
    a_tool_no_probe_implements(sandbox, monkeypatch)

    assert cli('auth', 'check').exit_code == ExitCode.CONVERGED
    assert cli('machines', 'check').exit_code == ExitCode.ISSUE


# ─────────────────────────────────────────────────────────────────────────────
# auth show: the whole roster, including what check keeps quiet about
# ─────────────────────────────────────────────────────────────────────────────


def test_auth_show_lists_the_roster_that_check_reports_one_row_of(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The answer to "did that work" straight after logging one in.

    `check` is silent about a tool that is fine, by design — so the verb that
    lists every declared tool with what asking found is a different verb rather
    than a flag on that one.
    """
    sandbox.shadow('icb', LOGGED_IN)
    sandbox.shadow('meso', LOGGED_OUT)
    declares(sandbox, 'icb', 'meso')

    ran = cli('auth', 'show', '--json')

    assert ran.document == {
        'icb': {'verdict': 'matched', 'detail': 'Logged in as synthetic'},
        'meso': {'verdict': 'missing', 'detail': 'the OS keychain holds no token'},
    }


def test_auth_show_keeps_the_roster_in_the_order_the_manifest_wrote_it(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Declaration order, not sorted, so the rows read as the `auth:` list with the
    logged-out ones lifted out of it."""
    for tool in ('nomad', 'icb', 'meso'):
        sandbox.shadow(tool, LOGGED_IN)
    declares(sandbox, 'nomad', 'icb', 'meso')

    ran = cli('auth', 'show', '--json')

    assert list(ran.document) == ['nomad', 'icb', 'meso']


def test_auth_show_says_so_when_a_machine_declares_no_tools(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation]
) -> None:
    """A box whose whole job is to be SSHed into names nothing here, and that is an
    answer rather than an empty listing."""
    a_machine_declaring_nothing(sandbox, monkeypatch)

    ran = cli('auth', 'show')

    assert 'declares nothing' in ran.stdout
    assert ran.exit_code == ExitCode.CONVERGED


def test_auth_show_reports_a_logged_out_tool_without_earning_an_exit_code(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation]
) -> None:
    """`show` is a listing and `check` is the verdict.

    Exiting 3 from a listing would make `auth show` unusable in a shell that stops
    on a non-zero status, for a machine state its sibling verb already reports.
    """
    a_tool_without_a_credential(sandbox, monkeypatch)

    ran = cli('auth', 'show')

    assert ran.exit_code == ExitCode.CONVERGED
    assert 'missing' in ran.stdout


# ─────────────────────────────────────────────────────────────────────────────
# credentials: whatever the include chain resolved to, and whether it starts
# ─────────────────────────────────────────────────────────────────────────────


def no_helper_configured(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    """A machine on SSH remotes only, which has nothing wrong with it."""


def a_helper_that_starts(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    sandbox.shadow('git-credential-synthetic')
    configure(sandbox, '[credential]', '\thelper = synthetic')


def a_helper_that_is_not_on_path(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    """A bare name, which git expands to `git-credential-<name>` and looks up."""
    configure(sandbox, '[credential]', '\thelper = nosuchhelper')


def a_helper_whose_path_is_gone(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    configure(sandbox, '[credential "https://employer.example.com"]', '\thelper = /mnt/c/gone/git-credential-manager.exe')


def a_helper_the_kernel_refuses(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    """The WSL failure, reproduced without WSL: the file is there and will not start."""
    helper = sandbox.root / 'git-credential-manager.exe'
    helper.write_bytes(PE_HEADER)
    helper.chmod(0o755)
    configure(sandbox, '[credential]', f'\thelper = {helper}')


def a_helper_naming_no_command(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    """A bare `!`, which git would hand to a shell with nothing in front of the
    operation. Quoted in the file because git strips a trailing comment marker."""
    configure(sandbox, '[credential]', '\thelper = "!"')


CREDENTIAL_STATES = [
    pytest.param(no_helper_configured, ExitCode.CONVERGED, id='none-configured'),
    pytest.param(a_helper_that_starts, ExitCode.CONVERGED, id='runs'),
    pytest.param(a_helper_that_is_not_on_path, ExitCode.ISSUE, id='not-on-path'),
    pytest.param(a_helper_whose_path_is_gone, ExitCode.ISSUE, id='path-gone'),
    pytest.param(a_helper_the_kernel_refuses, ExitCode.ISSUE, id='kernel-refuses'),
    pytest.param(a_helper_naming_no_command, ExitCode.ISSUE, id='names-no-command'),
]


@pytest.mark.parametrize(('arrange', 'checked'), CREDENTIAL_STATES)
def test_credentials_check_reports_a_helper_that_will_not_run(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation], arrange: Arrange, checked: ExitCode
) -> None:
    """Three faults with three different fixes, and one exit code between them.

    Which fault it was is the row's business — the caller branching on the status
    only needs to know a person is required, which is the same answer a logged-out
    CLI earns one resource above.
    """
    arrange(sandbox, monkeypatch)

    ran = cli('credentials', 'check', '--json')

    assert ran.exit_code == checked
    assert ran.document['address'] == 'credentials'


@pytest.mark.parametrize(('arrange', 'checked'), CREDENTIAL_STATES)
def test_credentials_plan_has_nothing_to_change_about_any_of_them(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation], arrange: Arrange, checked: ExitCode
) -> None:
    """A missing helper is a tool to install and a refused one is a fault in the
    machine underneath git. Neither is a file this repo deploys, so `apply` has
    nothing to write and `plan` has nothing to rehearse."""
    arrange(sandbox, monkeypatch)

    ran = cli('credentials', 'plan', '--json')

    assert ran.exit_code == ExitCode.CONVERGED
    assert ran.document['pending'] == 0


@pytest.mark.parametrize(
    ('arrange', 'verdict', 'phrase'),
    [
        pytest.param(a_helper_that_starts, 'matched', 'runs', id='runs'),
        pytest.param(a_helper_that_is_not_on_path, 'missing', 'git-credential-nosuchhelper is not on PATH', id='not-on-path'),
        pytest.param(a_helper_whose_path_is_gone, 'missing', 'does not exist', id='path-gone'),
        pytest.param(a_helper_the_kernel_refuses, 'stale', 'Exec format error', id='kernel-refuses'),
        pytest.param(a_helper_naming_no_command, 'stale', 'names no command', id='names-no-command'),
    ],
)
def test_the_verdict_tells_a_broken_configuration_from_a_broken_machine(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation], arrange: Arrange, verdict: str, phrase: str
) -> None:
    """`stale` is the whole reason this resource exists.

    The configuration is correct and the machine underneath it is not, so a
    `missing` verdict would send a reader to `common.gitconfig` to fix a binfmt
    registration. The errno is quoted verbatim because that is what gets searched
    at the moment it matters.
    """
    arrange(sandbox, monkeypatch)

    (row,) = cli('credentials', 'show', '--json').document

    assert row['verdict'] == verdict
    assert phrase in row['detail']


def test_a_finding_names_the_config_file_that_set_the_helper(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation]
) -> None:
    """On a machine with five config files, which one set it is most of the fix.

    That is why the layering is read through `gitconfig.read()` instead of asked
    for again per URL — `git config --get-urlmatch` answers for one URL at a time
    and never says where the answer lived.
    """
    a_helper_that_is_not_on_path(sandbox, monkeypatch)

    ran = cli('credentials', 'check')

    assert str(git_config(sandbox)) in ran.output


def test_the_config_the_helpers_are_read_from_is_the_sandbox_one(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation]
) -> None:
    """The anchor for every row above, and the one that fails loudly rather than
    vacuously. A git that would not answer produces an empty layering, which reads
    exactly like a machine with no helper configured — so something has to assert
    that git answered at all, from this file."""
    a_helper_that_is_not_on_path(sandbox, monkeypatch)

    (row,) = cli('credentials', 'show', '--json').document

    assert row['origin'] == str(git_config(sandbox))


def test_a_scoped_helper_keeps_the_url_it_is_keyed_on(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation]
) -> None:
    """The key is `credential.<url>.helper` and the URL holds dots and slashes of
    its own, which a naive split destroys."""
    a_helper_whose_path_is_gone(sandbox, monkeypatch)

    (row,) = cli('credentials', 'show', '--json').document

    assert row['scope'] == 'https://employer.example.com'


def test_the_empty_reset_helper_is_not_reported_as_a_broken_one(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """git's own idiom for clearing an inherited helper before setting one, which
    `common.gitconfig` uses for every github.com entry. Read as a helper it would
    report a fault on every machine, on every run."""
    sandbox.shadow('git-credential-synthetic')
    configure(sandbox, '[credential "https://github.com"]', '\thelper =', '\thelper = synthetic')

    ran = cli('credentials', 'check', '--json')
    (row,) = cli('credentials', 'show', '--json').document

    assert ran.exit_code == ExitCode.CONVERGED
    assert row['value'] == 'synthetic'


def test_credentials_show_says_so_when_git_is_configured_with_none(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    ran = cli('credentials', 'show')

    assert 'no credential helper' in ran.stdout
    assert ran.exit_code == ExitCode.CONVERGED


@pytest.mark.parametrize(
    ('noun', 'empty'),
    [pytest.param('auth', {}, id='auth'), pytest.param('credentials', [], id='credentials')],
)
def test_show_hands_a_json_caller_an_empty_document_rather_than_the_prose(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation], noun: str, empty: object
) -> None:
    """The two nouns answer in different shapes and both answer.

    `auth` keys its roster by tool and `credentials` lists helpers in the order git
    read them, so the empty answer is `{}` for one and `[]` for the other. Either
    way it is a document: the prose both verbs print for a person is what a `--json`
    caller must never be handed instead.
    """
    a_machine_declaring_nothing(sandbox, monkeypatch)

    ran = cli(noun, 'show', '--json')

    assert ran.document == empty


# ─────────────────────────────────────────────────────────────────────────────
# --probe: the half that cannot run unattended
# ─────────────────────────────────────────────────────────────────────────────

ANSWERS = '#!/bin/sh\n[ "$1" = get ] && printf "username=u\\npassword=p\\n"\nexit 0\n'
SILENT = RUNS_AND_SAYS_NOTHING
"""A helper holding a credential, and one that is simply logged out.

Both exit 0, which is why `probe` reads the output rather than the status: a
helper with nothing to say is indistinguishable from a successful one on the exit
code alone.
"""


@pytest.mark.parametrize(
    ('script', 'answered', 'phrase'),
    [
        pytest.param(ANSWERS, True, 'returned a credential for example.com', id='has-a-credential'),
        pytest.param(SILENT, False, 'no credential for example.com', id='has-none'),
    ],
)
def test_probe_reads_what_came_back_rather_than_the_exit_status(
    sandbox: Sandbox, cli: Callable[..., Invocation], script: str, answered: bool, phrase: str
) -> None:
    helper = helper_script(sandbox, 'git-credential-probed', script)
    configure(sandbox, '[credential "https://example.com"]', f'\thelper = {helper}')

    (row,) = cli('credentials', 'show', '--probe', '--json').document

    assert row['probed'] is answered
    assert phrase in row['probe_detail']


def test_a_probe_of_a_helper_that_will_not_start_reports_that_rather_than_a_login(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation]
) -> None:
    """The verdict and the probe answer the same way about the same helper, which
    is the point: `--probe` adds a question and does not replace one."""
    a_helper_the_kernel_refuses(sandbox, monkeypatch)

    (row,) = cli('credentials', 'show', '--probe', '--json').document

    assert row['verdict'] == 'stale'
    assert row['probed'] is False


def test_nothing_but_probe_ever_asks_a_helper_for_a_credential(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The constraint that keeps `check` runnable on a timer.

    A real `get` is what makes a helper open a browser or a GUI prompt, and a
    scheduled check that can raise a login window on an idle desk is one nobody
    leaves enabled. Asserted with a witness the helper writes only when it is
    asked, because the exec test runs it with no arguments at all.
    """
    witness = sandbox.root / 'asked'
    helper = helper_script(sandbox, 'git-credential-witness', f'#!/bin/sh\n[ "$1" = get ] && echo asked > {witness}\nexit 0\n')
    configure(sandbox, '[credential]', f'\thelper = {helper}')

    for argv in (('credentials', 'check'), ('credentials', 'plan'), ('credentials', 'show'), ('check',), ('apply',)):
        cli(*argv)
        assert not witness.exists(), f'{" ".join(argv)} asked a helper for a credential'

    cli('credentials', 'show', '--probe')

    assert witness.is_file()


def test_a_probe_refuses_to_let_a_helper_prompt(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Both variables reach the helper, because they belong to different programs.

    git's suppresses the terminal prompt it falls back to when no helper answers;
    GCM's suppresses the browser and GUI dialog GCM opens on its own initiative,
    which git knows nothing about. Read out of the helper's own environment rather
    than out of the probe's answer, because the answer would be the same either
    way — and set for the child alone, which the second assertion is about.
    """
    witness = sandbox.root / 'environment'
    helper = helper_script(
        sandbox,
        'git-credential-env',
        f'#!/bin/sh\nprintf "%s/%s\\n" "$GIT_TERMINAL_PROMPT" "$GCM_INTERACTIVE" > {witness}\nprintf "password=p\\n"\n',
    )
    configure(sandbox, '[credential "https://example.com"]', f'\thelper = {helper}')

    (row,) = cli('credentials', 'show', '--probe', '--json').document

    assert row['probed'] is True
    assert witness.read_text().strip() == '0/never'
    assert os.environ.get('GIT_TERMINAL_PROMPT') is None, 'the probe leaked its environment into this process'


def test_a_probe_of_a_helper_naming_no_command_runs_the_operation_word_instead(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation]
) -> None:
    """The bug, pinned as it behaves today so the fix has something to break.

    `credentials_show` probes every listed helper, including one `_asked` has
    already ruled `stale` for naming no command. `Helper.invocation` assembles the
    shell form as `sh -c '<command> get'`, so an empty command leaves `sh -c ' get'`
    — and the shell looks `get` up on PATH and runs whatever it finds. Here it
    finds a script this test put there.
    """
    witness = sandbox.root / 'ran-get'
    sandbox.shadow('get', f'#!/bin/sh\necho ran > {witness}\nexit 0\n')
    a_helper_naming_no_command(sandbox, monkeypatch)

    (row,) = cli('credentials', 'show', '--probe', '--json').document

    assert row['verdict'] == 'stale'
    assert witness.is_file()


@pytest.mark.xfail(strict=True, reason='probe builds `sh -c " get"` for a helper whose command is empty')
def test_a_probe_should_never_execute_the_operation_word_as_a_command(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation]
) -> None:
    """What the run should do: report the empty value and start nothing.

    Two faults, and the second is the one that matters. The answer names a command
    called `get` rather than the helper, which contradicts the `stale` verdict
    printed on the same row — and reaching it at all means `--probe` executed a
    PATH binary the configuration never named. The resource had already decided
    there was no program to run, so nothing here needs a new judgement about what
    the value means.
    """
    witness = sandbox.root / 'ran-get'
    sandbox.shadow('get', f'#!/bin/sh\necho ran > {witness}\nexit 0\n')
    a_helper_naming_no_command(sandbox, monkeypatch)

    cli('credentials', 'show', '--probe', '--json')

    assert not witness.exists()


def test_show_without_the_flag_carries_no_probe_fields_at_all(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation]
) -> None:
    """Absent rather than null, so a caller can tell "was not asked" from "asked and
    got nothing" — which are the two states the exit code deliberately does not
    separate."""
    a_helper_that_starts(sandbox, monkeypatch)

    (row,) = cli('credentials', 'show', '--json').document

    assert 'probed' not in row
    assert 'probe_detail' not in row


# ─────────────────────────────────────────────────────────────────────────────
# Two helpers, one label
# ─────────────────────────────────────────────────────────────────────────────


def two_unscoped_helpers(sandbox: Sandbox) -> None:
    """What git does with a key it accumulates rather than resolves.

    Both helpers are configured, both are run, and the first that answers supplies
    the credential — so a second entry is an addition rather than an override.
    `gitconfig.ACCUMULATING` says so and `helpers()` lists both, which is correct.
    """
    silent = helper_script(sandbox, 'git-credential-first', SILENT)
    answering = helper_script(sandbox, 'git-credential-second', ANSWERS)
    configure(sandbox, '[credential]', f'\thelper = {silent}', f'\thelper = {answering}')


def test_two_helpers_sharing_a_label_are_both_listed(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    two_unscoped_helpers(sandbox)

    rows = cli('credentials', 'show', '--json').document

    assert [row['scope'] for row in rows] == ['every remote', 'every remote']
    assert [Path(row['program']).name for row in rows] == ['git-credential-first', 'git-credential-second']


def test_a_probe_answer_is_currently_keyed_on_the_label_and_so_collides(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The bug, pinned as it behaves today so the fix has something to break.

    `credentials_show` builds `{entry.helper.label: probe(entry.helper)}`, and a
    label is the scope or `every remote`. Two helpers on one scope collapse to one
    entry, so both rows print the *last* helper's answer — here the silent helper
    is reported as holding a credential it never returned.
    """
    two_unscoped_helpers(sandbox)

    first, second = cli('credentials', 'show', '--probe', '--json').document

    assert first['probed'] is True
    assert second['probed'] is True
    assert first['probe_detail'] == second['probe_detail']


@pytest.mark.xfail(strict=True, reason='probed is keyed on the helper label, which two helpers on one scope share')
def test_each_helper_should_report_its_own_probe_answer(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """What the row should say: the silent helper returned nothing.

    Keying on the label loses the association between a row and the answer that
    row is evidence for, and it does so silently — the run is correct about the
    verdicts printed beside it and wrong about the probe, which is the field a
    reader turned `--probe` on for. Two helpers on one scope is the ordinary
    accumulating case git documents, not a misconfiguration.

    The probe also runs once per entry and keeps one answer, so the wrong result
    is not even cheaper than the right one.
    """
    two_unscoped_helpers(sandbox)

    first, second = cli('credentials', 'show', '--probe', '--json').document

    assert first['probed'] is False
    assert second['probed'] is True


# ─────────────────────────────────────────────────────────────────────────────
# Usage against findings
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('noun', ['auth', 'credentials'])
@pytest.mark.parametrize('verb', ['plan', 'check', 'show'])
def test_the_machine_option_is_honoured_where_the_name_resolves(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation], noun: str, verb: str
) -> None:
    """Six leaves, one option, and the sandbox machine named explicitly.

    `$MACHINE` already resolves the same box, so this proves the option is wired
    rather than that the answer is right — which is what makes the row below a
    finding about the *unresolvable* name and not about the flag.
    """
    a_tool_with_a_credential(sandbox, monkeypatch)

    assert cli(noun, verb, '--machine', sandbox.machine).exit_code == ExitCode.CONVERGED


@pytest.mark.parametrize('noun', ['auth', 'credentials'])
@pytest.mark.parametrize('verb', ['plan', 'check', 'show'])
def test_a_machine_name_nothing_declares_escapes_as_a_traceback(cli: Callable[..., Invocation], noun: str, verb: str) -> None:
    """The bug, pinned as it behaves today so the fix has something to break.

    `_session` catches `NoMachine`, which is raised when *no* name could be found
    at all. A name that was given and has no manifest is a different exception —
    `MachineError`, raised by `Session.machine`, which is a cached property nothing
    touches until the walk is already running. By then the `try` in `_session` has
    returned and `engine.assess` evaluates `session.plan` outside `_measure`'s
    `except Exception`, so nothing on either side catches it.
    """
    with pytest.raises(machines.MachineError, match='no-such-machine'):
        cli(noun, verb, '--machine', 'no-such-machine')


@pytest.mark.xfail(strict=True, reason='MachineError escapes every read-only leaf; only `apply` catches it')
@pytest.mark.parametrize('noun', ['auth', 'credentials'])
@pytest.mark.parametrize('verb', ['plan', 'check', 'show'])
def test_a_machine_name_nothing_declares_should_be_diagnosed_rather_than_raised(
    cli: Callable[..., Invocation], noun: str, verb: str
) -> None:
    """What the caller should get: exit 2, and the name on stderr.

    Exit 1 is the specific harm today. It means `DRIFT`, and `check` cannot drift —
    its range is 0 and 3 — so a scheduled caller branching on the status reads a
    mistyped `--machine` as a machine that has work pending. The traceback goes to
    the console rather than to stderr's diagnostic channel, so the run also says
    nothing about which name was wrong.

    Exit 2 rather than the 3 `reconcile.apply_machine` answers, because
    `_manifest_path` already settles this for the `machines` noun and `machines
    show <typo>` exits 2 today. The reasoning is one shared claim across this file,
    `test_symlinks.py` and `test_composite.py`; it is written out in the latter's
    `test_a_read_verb_reports_a_machine_with_no_manifest_rather_than_crashing`.
    """
    ran = cli(noun, verb, '--machine', 'no-such-machine', catch_exceptions=True)

    assert ran.exit_code == ExitCode.USAGE
    assert 'no-such-machine' in ran.stderr


@pytest.mark.parametrize('noun', ['auth', 'credentials'])
def test_a_bare_noun_prints_its_help_rather_than_measuring_anything(cli: Callable[..., Invocation], noun: str) -> None:
    """A group is a thing and only its leaves are verbs, so naming one alone is a
    usage error rather than a default measurement."""
    ran = cli(noun, catch_exceptions=True)

    assert ran.exit_code == ExitCode.USAGE
    assert 'plan' in ran.output
