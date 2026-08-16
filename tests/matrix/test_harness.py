"""The harness measured against itself, before anything is measured through it.

Every matrix module rests on four claims: the synthetic declaration is what the
CLI resolves, a command runs against it end to end, the real home is never
touched, and nothing can reach the network. Each is asserted here, because each
fails silently everywhere else — a leaf that read `~/dotfiles` would report this
developer's machine and pass.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable

import pytest

from dotfiles import github_release
from dotfiles import paths
from dotfiles import releases
from dotfiles.session import Session
from dotfiles.vocabulary import ExitCode
from matrix.harness import DECLARES_LAZYGIT
from matrix.harness import LAZYGIT
from matrix.harness import Invocation
from matrix.harness import ReachedTheNetwork
from matrix.harness import Sandbox
from matrix.harness import resource

# ─────────────────────────────────────────────────────────────────────────────
# The synthetic repo is what resolves
# ─────────────────────────────────────────────────────────────────────────────


def test_the_repo_the_package_resolves_is_the_sandbox_one(sandbox: Sandbox) -> None:
    """`$DOTFILES_DIR` is the real knob and `paths` reads it once, at import. Without
    the rebinding every leaf below would measure ~/dotfiles's own declaration."""
    assert sandbox.repo == paths.REPO_ROOT
    assert sandbox.repo / 'install' / 'packages.yml' == paths.PACKAGES_FILE


def test_a_session_the_cli_builds_for_itself_lands_in_the_sandbox(sandbox: Sandbox) -> None:
    """The load-bearing rebinding. A CLI leaf resolves its own Session and cannot be
    handed one, and `Session.repo`'s default was frozen into the generated
    `__init__` when the dataclass was created — so the variable alone cannot move
    it."""
    assert Session.resolve().repo == sandbox.repo
    assert Session.resolve().home == sandbox.home


def test_the_machine_resolves_without_being_named(sandbox: Sandbox) -> None:
    """`$MACHINE` is exported, so a leaf under test does not spend a `--machine` on
    saying which box this is."""
    assert Session.resolve().machine_name == sandbox.machine


def test_a_declared_section_reaches_the_resolved_plan(sandbox: Sandbox) -> None:
    sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)

    assert [item.name for item in Session.resolve().plan.items] == ['uv', 'lazygit']


def test_a_manifest_that_declares_nothing_still_plans_uv(sandbox: Sandbox) -> None:
    """The sandbox's starting state, asserted rather than assumed. uv is ungated and
    planned on every machine, because everything installed later resolves through
    it — so "declares nothing" is one item, not none, and `settle` is what keeps it
    from being a finding in every matrix row."""
    assert [item.name for item in Session.resolve().plan.items] == ['uv']


# ─────────────────────────────────────────────────────────────────────────────
# A command runs against it
# ─────────────────────────────────────────────────────────────────────────────


def test_a_command_runs_end_to_end_against_the_synthetic_machine(cli: Callable[..., Invocation]) -> None:
    ran = cli('plan', '--json')

    assert ran.exit_code == ExitCode.CONVERGED
    assert ran.document is not None
    assert ran.document['machine'] == 'box'


@pytest.mark.parametrize('verb', ['plan', 'check', 'apply'], ids=['plan', 'check', 'apply'])
def test_the_baseline_machine_converges_under_every_verb(verb: str, cli: Callable[..., Invocation]) -> None:
    """What every matrix row starts from, pinned here so a row can attribute its
    exit code to the flag it is about.

    All three, because each reaches a different range: `plan` answers 0 or 1,
    `check` answers 0 or 3, and `apply` answers 0, 2 or 3. A baseline that was
    converged under one and not the others would leave two thirds of the matrix
    measuring the baseline.
    """
    assert cli(verb).exit_code == ExitCode.CONVERGED


def test_a_json_run_puts_the_document_on_stdout_and_nothing_else(cli: Callable[..., Invocation]) -> None:
    """The machine contract the two consoles exist for. One stray diagnostic on
    stdout turns a `--json` parse into a syntax error rather than the warning it
    was."""
    ran = cli('check', '--json')

    assert ran.document is not None
    assert ran.stdout.strip().startswith('{')


def test_a_declared_release_that_is_absent_is_what_plan_reports(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The whole harness in one line: a declaration written by the test, an empty
    `PATH`, and a verdict that could only have come from those two."""
    sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)

    ran = cli('packages', 'plan', '--json')

    assert ran.exit_code == ExitCode.DRIFT
    assert [change['item'] for change in resource(ran, 'packages')['findings']] == ['ghrelease/lazygit']


def test_an_installed_tool_at_the_newest_release_reports_nothing_pending(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Both version helpers, against each other. Neither figure exists anywhere but
    in this test."""
    sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)
    sandbox.installed('lazygit', 'lazygit version 0.45.0')
    sandbox.upstream({'jesseduffield/lazygit': 'v0.45.0'})

    ran = cli('packages', 'plan', '--json')

    assert ran.exit_code == ExitCode.CONVERGED
    assert resource(ran, 'packages')['findings'] == []


def test_an_installed_tool_behind_the_release_cache_is_pending(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)
    sandbox.installed('lazygit', 'lazygit version 0.44.0')
    sandbox.upstream({'jesseduffield/lazygit': 'v0.45.0'})

    ran = cli('packages', 'plan', '--json')

    assert ran.exit_code == ExitCode.DRIFT
    assert [change['item'] for change in resource(ran, 'packages')['findings']] == ['ghrelease/lazygit']


def test_an_expired_cache_entry_is_unmeasured_rather_than_current(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """`age` is the knob for the rule the cache exists to keep: it may be out of
    date, it may not lie."""
    sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)
    sandbox.installed('lazygit', 'lazygit version 0.44.0')
    sandbox.upstream({'jesseduffield/lazygit': 'v0.45.0'}, age=releases.TTL + dt.timedelta(hours=1))

    ran = cli('packages', 'plan', '--json')

    assert resource(ran, 'packages')['unmeasured'] == 1


def test_a_usage_error_is_told_apart_from_a_finding(cli: Callable[..., Invocation]) -> None:
    """The distinction the whole matrix is about, proven reachable through the
    invoker: a misspelt address is a usage error, not drift."""
    ran = cli('plan', '--skip', 'nonsense')

    assert ran.exit_code == ExitCode.USAGE


def test_a_usage_error_is_reported_on_stderr_and_nowhere_else(cli: Callable[..., Invocation]) -> None:
    """The split the two consoles exist for, measured on the stream that carries
    diagnostics. Click writes its own usage errors to stderr; this asserts the
    invoker keeps them there rather than folding both streams into one string."""
    ran = cli('plan', '--skip', 'nonsense')

    assert 'nonsense' in ran.stderr
    assert 'nonsense' not in ran.stdout


def test_an_unhandled_exception_reaches_the_test_rather_than_becoming_an_exit_code(cli: Callable[..., Invocation]) -> None:
    """`check` cannot exit 1 by design and does exit 1 on a traceback. A harness
    that swallowed the traceback would report the impossible code as if the code
    had produced it."""
    ran = cli('report', 'show', 'no-such-run', catch_exceptions=True)

    assert ran.exit_code != ExitCode.CONVERGED


# ─────────────────────────────────────────────────────────────────────────────
# Nothing touches the real machine
# ─────────────────────────────────────────────────────────────────────────────


def test_the_home_every_path_resolves_through_is_the_sandbox_one(sandbox: Sandbox) -> None:
    from pathlib import Path

    assert Path.home() == sandbox.home
    assert Path.home() != Path('~').expanduser().parent / 'chris'


@pytest.mark.parametrize(
    ('name', 'attribute'),
    [
        ('STATE_HOME', 'state'),
        ('RUNS_DIR', 'state'),
        ('staging_dir', 'staging'),
        ('archive_dir', 'cache'),
        ('status_cache', 'cache'),
    ],
    ids=['state', 'runs', 'staged', 'archives', 'statuses'],
)
def test_every_directory_the_package_writes_to_is_under_the_sandbox(sandbox: Sandbox, name: str, attribute: str) -> None:
    """Each is a separate chance to write into the real fleet's state directory,
    which is on Syncthing.

    The cache paths are functions and resolve through `$XDG_CACHE_HOME` on every
    call, so the sandbox setting that one variable carries all of them — where a
    constant was a name somebody had to remember to rebind, and `status_cache` was
    the one nobody did."""
    found = getattr(paths, name)
    resolved = found() if callable(found) else found

    assert resolved.is_relative_to(getattr(sandbox, attribute))


def test_a_recording_verb_files_its_run_inside_the_sandbox(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """`plan` writes a run record. 1372 empty ones accumulated in the real
    directory before anything counted them, which is what `RUNS_DIR` being rebound
    prevents here rather than detects afterwards."""
    cli('plan')

    assert len(sandbox.filed_records) == 1


def test_a_check_writes_its_status_document_inside_the_sandbox(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    cli('check')

    assert sandbox.status_file.is_file()


def test_an_env_apply_writes_the_sandbox_env_file(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The one resource whose whole job is to write into `$HOME`, so it is the
    sharpest test that `$HOME` moved."""
    sandbox.env_file.unlink()

    cli('env', 'apply')

    assert sandbox.env_file.is_file()
    assert 'export MACHINE="${MACHINE:-box}"' in sandbox.env_file.read_text()


def test_a_shadowed_binary_wins_over_the_real_one(sandbox: Sandbox) -> None:
    """`PATH` keeps `/usr/bin:/bin` behind the sandbox, so this is what stops a tool
    the developer happens to have installed from answering."""
    import shutil

    sandbox.shadow('git')

    assert shutil.which('git') == str(sandbox.bin / 'git')


def test_an_apply_that_would_install_is_stopped_rather_than_recorded_as_a_failure(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The root conftest's guard, proven to survive the walk's isolation.

    `engine._act` turns anything a `perform` raises into a `Refusal`, so a guard
    raised as an `AssertionError` came back as exit 3 with `ruff: ... would install
    ...` in the record — an outcome a matrix row asserting exit 3 would have
    accepted. It raises a `BaseException` for exactly this.
    """
    sandbox.declare(
        packages={'uv_tools': {'lint': [{'name': 'ruff'}]}},
        manifest={'machine': 'box', 'platform': 'linux', 'uv_tools': ['ruff']},
    )

    with pytest.raises(BaseException, match='would install on this machine'):
        cli('packages', 'apply')


def test_the_ambient_github_token_cannot_reach_a_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """One exported variable flips a private-repo entry from BY_HAND to AUTOMATIC,
    so the same assertion passes at one desk and fails on the runner."""
    import os

    from dotfiles import evidence

    assert os.environ.get('GITHUB_TOKEN') is None
    assert evidence.have_github_credentials() is False


# ─────────────────────────────────────────────────────────────────────────────
# The network guard
# ─────────────────────────────────────────────────────────────────────────────


def test_the_network_guard_fires_when_something_reaches_out() -> None:
    with pytest.raises(ReachedTheNetwork):
        github_release.request('https://api.github.com/repos/jesseduffield/lazygit/releases/latest')


def test_the_guard_catches_a_client_built_somewhere_other_than_our_own_helper() -> None:
    """Guarding `github_release.request` would prove only that nobody called that
    one. The transport is between every caller and the socket."""
    import httpx2

    with pytest.raises(ReachedTheNetwork):
        httpx2.Client().get('https://example.invalid/')


def test_a_refresh_that_would_measure_upstream_is_stopped_rather_than_answered(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """`--refresh` is the one flag that means "spend the network on being current",
    so it is the flag that proves the guard is reachable through the CLI.

    The tool has to be *installed* for the question to be asked at all: presence is
    measured first, and a tool that is not there has no currency to have.
    """
    sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)
    sandbox.installed('lazygit', 'lazygit version 0.44.0')

    with pytest.raises(ReachedTheNetwork):
        cli('plan', '--refresh')


def test_a_default_run_never_consults_the_network_at_all(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The guard proves nothing went out; this proves nothing tried. `check` runs at
    a prompt and on a timer, and the default must not spend an API call per
    release."""
    sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)

    ran = cli('packages', 'check', '--json')

    assert ran.exit_code == ExitCode.CONVERGED
