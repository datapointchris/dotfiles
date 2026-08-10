"""What a machine looks like after `install.sh` has run on it.

Each test is one question about the finished machine, and they share a single
install through the session-scoped `machine` fixture. That split is the point:
the bash harnesses ran verification as sequential steps, so the first failure
decided the exit code and everything after it was noise. Here a broken update
path and a missing binary are two different red lines.

`install.sh` is a bootstrap that installs the CLI and hands over, so the first
tests below are about that handover specifically — a machine can fail to
converge for a reason that has nothing to do with whether the bootstrap worked,
and telling those apart is what the whole step is for.
"""

from __future__ import annotations

import pytest
from harness import Machine
from harness import failed_outcomes
from harness import run_record
from harness import shadow_calls

pytestmark = pytest.mark.docker


# ─────────────────────────────────────────────────────────────────────────────
# The bootstrap
# ─────────────────────────────────────────────────────────────────────────────


def test_the_bootstrap_put_uv_on_the_machine(machine: Machine) -> None:
    """Online it comes from astral.sh; offline from the bundle's `bin/uv`. Either
    way nothing after this line can run without it."""
    assert machine.succeeds('command -v uv'), machine.install_log[-3000:]


def test_the_cli_is_installed_and_runs(machine: Machine) -> None:
    """`uv tool install --editable` and then the console script, which is the
    handover the whole bootstrap exists to reach."""
    assert machine.succeeds('command -v dotfiles')
    assert machine.read('dotfiles --version').startswith('dotfiles ')


def test_the_cli_runs_from_outside_the_repo(machine: Machine) -> None:
    """An installed tool, not a script found relative to the checkout — which is
    the difference between this and the bash CLI it replaced."""
    assert machine.read('cd / && dotfiles machines list') != ''


def test_the_interpreter_the_installers_get_can_import_the_package(machine: Machine) -> None:
    """`$DOTFILES_PYTHON` is what replaced the system-python bootstrap. An
    installer handed one that cannot import `dotfiles` is the exact failure that
    the PyYAML-into-Apple's-python step existed to prevent."""
    assert machine.succeeds('"$(uv tool dir)/dotfiles/bin/python" -c "import dotfiles, yaml"')


def test_nothing_but_uv_reached_for_the_system_python(fresh_install: Machine) -> None:
    """The whole install ran with a `python3` first on PATH that exits 1 loudly,
    and only uv is allowed to have found it.

    This is what replaced `pip install --user PyYAML` into Apple's interpreter:
    scripts reach Python through `$DOTFILES_PYTHON`, which is the CLI's own
    `sys.executable`, so a bare `python3` anywhere in a run is the old bootstrap
    growing back. uv is exempt because scanning PATH for an interpreter is what it
    is supposed to do — the offline path passes `--no-python-downloads` and needs
    to find a real one, which it does after rejecting this stub.
    """
    strangers = [f'{call.caller} → {call.argv}' for call in shadow_calls(fresh_install) if not call.by_uv]
    assert not strangers, strangers


def test_no_stage_crashed(machine: Machine) -> None:
    """A stage may fail; none may raise.

    A traceback in our own code means the walk stopped, so every stage after it
    silently did not run — which is how a symlink pass that had already deployed
    everything took tmux, Neovim and the shell config down with it.

    Scoped to frames naming this package. Matching any `Traceback` also caught
    setuptools building someone else's sdist: Pillow failing to find zlib is a
    real problem and a different one, and it made a third-party build failure
    read as the walk collapsing.
    """
    ours = [line for line in machine.install_log.splitlines() if '/dotfiles/src/dotfiles/' in line]
    assert not ours, ours[:10]


def test_the_run_reports_its_own_outcome(machine: Machine) -> None:
    """Exit 0 converged, 3 means something the run attempted failed. What must
    never happen is the third case this replaced: failures, and exit 0.

    Read off the run record rather than out of the console. A grep for the
    summary sentence pins an English fragment, and the record carries the same
    fact as a field — which is also the only copy that survives the scroll.
    """
    assert machine.install_status in {0, 3}
    if machine.install_status == 3:
        assert failed_outcomes(machine) or run_record(machine)['issues'], 'exit 3 with nothing recorded as wrong'


# ─────────────────────────────────────────────────────────────────────────────
# The machine it produced
# ─────────────────────────────────────────────────────────────────────────────


def test_the_machine_converged(machine: Machine) -> None:
    """The whole install, judged as the machine judges it.

    Deliberately not softened to "converged or has known failures": a red line
    here is the accurate state, and the addresses it names are the work. They come
    off the run record, so the assertion message is the diagnosis.
    """
    if machine.install_status == 0:
        return
    pytest.fail(f'{machine.environment.name} did not converge: {failed_outcomes(machine) or machine.install_log[-2000:]}')


def test_every_declared_tool_is_installed(machine: Machine) -> None:
    """The manifest is the checklist, so a tool added or removed changes what is
    verified with no list here to update."""
    home = machine.environment.home
    result = machine.exec(f'bash {home}/dotfiles/tests/install/verification/verify-installed-packages.sh')
    assert result.returncode == 0, result.stdout[-4000:]


def test_nothing_is_installed_twice(machine: Machine) -> None:
    """Two copies on PATH means the one that wins is decided by PATH order rather
    than by the manifest — apt's `batcat` shadowing the cargo `bat`, and so on."""
    home = machine.environment.home
    result = machine.exec(f'cd {home}/dotfiles && bash tests/install/verification/detect-installed-duplicates.sh')
    assert result.returncode == 0, result.stdout[-4000:]


def test_the_apps_work(machine: Machine) -> None:
    home = machine.environment.home
    result = machine.exec(f'bash {home}/dotfiles/tests/apps/all-apps.sh')
    assert result.returncode == 0, result.stdout[-4000:]


def test_zdotdir_is_configured_system_wide(machine: Machine) -> None:
    """There is deliberately no `~/.zshenv`: `/etc/zshenv` (or `/etc/zsh/zshenv`
    on Debian) is what points zsh at `~/.config/zsh`, and a missing one means the
    install did not finish."""
    assert machine.succeeds('grep -rq ZDOTDIR /etc/zshenv /etc/zsh/zshenv 2>/dev/null')


def test_a_second_apply_over_a_converged_machine_changes_nothing(machine: Machine) -> None:
    """Idempotence, against the machine the first apply just produced.

    This ran `update.sh` until reconcile collapsed to one verb. `apply` is that
    verb — it installs what is missing and upgrades what is behind — so running it
    twice is both the update path and the assertion that the first run converged.
    """
    home = machine.environment.home
    result = machine.exec(f'cd {home}/dotfiles && uv run dotfiles apply')
    assert result.returncode == 0, result.stdout[-4000:]


# ─────────────────────────────────────────────────────────────────────────────
# The offline machine specifically
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('tool', ['nvim', 'lazygit', 'fzf', 'bat', 'fd', 'eza', 'zoxide', 'delta', 'glow', 'duf'])
def test_the_bundle_installed_the_tools_the_network_could_not(machine: Machine, tool: str) -> None:
    """Every one of these comes from a release asset, which is the thing the work
    firewall blocks — so each is a tool that exists on the machine only because
    the bundle carried it."""
    if not machine.environment.offline:
        pytest.skip('only the offline environment installs from a bundle')
    assert machine.succeeds(f'command -v {tool}')


def test_the_offline_run_used_an_interpreter_the_machine_already_had(machine: Machine) -> None:
    """`--no-python-downloads` is otherwise untested, and one deletion from gone.

    It is the only thing between an offline install and fetching an interpreter
    over the network the bundle exists to avoid — but this image ships a python
    that satisfies `requires-python`, and uv picks it without being told to, so
    the install passes identically with the flag removed. Arch is the environment
    that would exercise it, and Arch runs online.

    Asserting the outcome instead: the interpreter is not one uv fetched. The
    firewall would stop the fetch anyway — interpreters come from
    `objects.githubusercontent.com`, which is blackholed — which is belt and
    braces, not a reason to leave the flag unasserted.
    """
    if not machine.environment.offline:
        pytest.skip('only the offline environment forbids interpreter downloads')

    managed = machine.read('uv python dir')
    interpreter = machine.read('readlink -f "$(uv tool dir)/dotfiles/bin/python"')

    assert managed and interpreter
    assert not interpreter.startswith(managed), f'the offline install fetched an interpreter: {interpreter}'


def test_the_offline_run_never_resolved_a_version_online(machine: Machine) -> None:
    """The version has to come from the bundle manifest, or the filename built
    from it names a file the cache does not hold.

    `tests/install/test_offline_versions.py` asserts the mechanism directly and
    cheaply; this is the same property observed on a real install, where a path
    that bypassed the short-circuit would show up as a resolution attempt.
    """
    if not machine.environment.offline:
        pytest.skip('only the offline environment installs from a bundle')
    assert 'Using cached' in machine.install_log
