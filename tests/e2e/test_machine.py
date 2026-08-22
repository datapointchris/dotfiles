"""What a machine looks like after `install.sh` and the `apply` it hands to.

Each test is one question about the finished machine, and they share a single
install through the session-scoped `machine` fixture. That split is the point:
the bash harnesses ran verification as sequential steps, so the first failure
decided the exit code and everything after it was noise. Here a broken update
path and a missing binary are two different red lines.

`install.sh` is a bootstrap that installs the CLI and stops, and `dotfiles apply`
is what converges the machine — so the first tests below are about that seam
specifically. A machine can fail to converge for a reason that has nothing to do
with whether the bootstrap worked, and telling those apart is what the whole step
is for.
"""

from __future__ import annotations

import json

import exchange
import pytest
from harness import Machine
from harness import declared_items
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
    """The CLI carries its own interpreter with its dependencies declared, which is
    what removed the system-python bootstrap. One that cannot import `dotfiles` is
    the exact failure the PyYAML-into-Apple's-python step existed to prevent."""
    assert machine.succeeds('"$(uv tool dir)/dotfiles/bin/python" -c "import dotfiles, yaml"')


def test_nothing_but_uv_reached_for_the_system_python(fresh_install: Machine) -> None:
    """The whole install ran with a `python3` first on PATH that exits 1 loudly,
    and only uv is allowed to have found it.

    This is what replaced `pip install --user PyYAML` into Apple's interpreter:
    the CLI runs on the interpreter uv installed it with, so nothing in a run has
    a reason to look for another and a bare `python3` anywhere in one is the old
    bootstrap growing back. uv is exempt because scanning PATH for an interpreter
    is what it is supposed to do — the offline path passes `--no-python-downloads`
    and needs to find a real one, which it does after rejecting this stub.
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


def test_the_machine_converged(converged_machine: Machine) -> None:
    """The whole install, judged as the machine judges it.

    Deliberately not softened to "converged or has known failures": a red line
    here is the accurate state, and the addresses it names are the work. They come
    off the run record, so the assertion message is the diagnosis.
    """
    if converged_machine.install_status == 0:
        return
    pytest.fail(
        f'{converged_machine.environment.name} did not converge: '
        f'{failed_outcomes(converged_machine) or converged_machine.install_log[-2000:]}'
    )


def test_neovim_starts_without_errors(converged_machine: Machine) -> None:
    """Presence is not health, and this is the difference.

    Every plugin directory can be on disk while the config that loads them raises
    on startup, and `test_verification.py` cannot see that: it asks whether the
    declaration landed, which is a question about files. Nothing declares "and it
    runs".
    """
    started = converged_machine.exec('timeout 30 nvim --headless +qa 2>&1')
    assert 'error' not in started.stdout.lower(), started.stdout[-2000:]


def test_yazi_starts_without_errors(converged_machine: Machine) -> None:
    """Its own check because it has its own failure: `package.toml` had two owners,
    so a fresh install deployed the file twice and yazi refused every start."""
    started = converged_machine.exec('timeout 20 yazi --clear-cache 2>&1')
    assert 'error' not in started.stdout.lower(), started.stdout[-2000:]


def test_docker_compose_is_the_v2_plugin(converged_machine: Machine) -> None:
    """`docker compose`, not `docker-compose`. The binary being present says
    nothing about the subcommand resolving, which is what every compose file here
    is written against.

    Skipped from the *declaration*, not from the environment's name. Skipping on
    `name == 'wsl'` misses `offline` and `restricted`, which also run the
    `wsl-work-workstation` manifest — where every docker entry carries
    `excludes_host: wsl`, because WSL uses Docker Desktop on the Windows host.
    That fails two environments for a package they correctly do not install.
    """
    if not any(item.name == 'docker-compose-plugin' for item in declared_items(converged_machine.environment)):
        pytest.skip('this machine does not declare the compose plugin')
    assert converged_machine.succeeds('docker compose version')


def test_the_apps_work(converged_machine: Machine) -> None:
    home = converged_machine.environment.home
    result = converged_machine.exec(f'bash {home}/dotfiles/tests/apps/all-apps.sh')
    assert result.returncode == 0, result.stdout[-4000:]


def test_apt_currency_is_measured_against_an_index_the_run_refreshed(machine: Machine) -> None:
    """The unprivileged refresh, against a real apt on a real Ubuntu.

    `syspkg._apt_outdated` redirects `Dir::State::lists` and `Dir::Cache` at a
    scratch directory so `apt-get update` needs no root, then lists against what it
    fetched. Nothing below this level can say whether apt accepts that: the unit
    tests assert the argv and a stub answers it.

    The machine's own lists are what the assertion is against. These images ship them
    stale, so a run reading them reports nothing upgradable — the measured-looking
    wrong answer the redirect exists to stop.

    Gated on the manager and the route rather than on the image name. A firewalled
    environment cannot reach the archive, so its refresh fails and the seeded index
    is the answer — correct behaviour, and not what this measures.
    """
    if machine.environment.firewalled or not machine.succeeds('command -v apt-get'):
        pytest.skip('needs apt and a route to the archive')
    home = machine.environment.home
    probe = "from dotfiles.providers import syspkg; print(len(syspkg.outdated('apt') or ()))"
    measured = machine.exec(f'cd {home}/dotfiles && uv run python -c "{probe}"')

    assert measured.returncode == 0, measured.stdout[-4000:]
    assert int(measured.stdout.strip().splitlines()[-1]) > 0, 'a stale index reports nothing behind, which is what this refresh is for'


def test_zdotdir_is_configured_system_wide(machine: Machine) -> None:
    """There is deliberately no `~/.zshenv`: `/etc/zshenv` (or `/etc/zsh/zshenv`
    on Debian) is what points zsh at `~/.config/zsh`, and a missing one means the
    install did not finish."""
    assert machine.succeeds('grep -rq ZDOTDIR /etc/zshenv /etc/zsh/zshenv 2>/dev/null')


def test_a_second_apply_over_a_converged_machine_changes_nothing(converged_machine: Machine) -> None:
    """Idempotence, against the machine the first apply just produced.

    `apply` is the only verb — it installs what is missing and upgrades what is
    behind — so running it twice is both the update path and the assertion that
    the first run converged.

    **The same flags as the install, or it is not a second apply of the same
    thing.** Without `--offline` this reaches the network the offline environment
    exists to do without, installs the toolchains that run deliberately refused,
    and passes — so a test named for changing nothing becomes the only thing on the
    machine that changes anything. It also leaves every later
    `--installed` check reading a container in a state no install produces, which
    makes an offline diagnosis wrong in a way nothing points at.
    """
    home = converged_machine.environment.home
    flags = converged_machine.environment.offline_flag
    result = converged_machine.exec(f'cd {home}/dotfiles && uv run dotfiles apply{flags}')
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

    `tests/resources/test_packages.py::test_offline_never_refreshes_however_it_was_asked`
    asserts the mechanism directly and cheaply; this is the same property observed
    on a real install, where a path that bypassed the short-circuit would show up
    as a resolution attempt.

    Read off the two sentences the bundle paths actually print. This asserted
    `'Using cached'` — a phrase nothing in this repo emits and uv stopped printing
    when the bootstrap moved from `pip install` to a wheelhouse — so it had been
    failing for a reason that said nothing about versions at all.

    `Checksum verified from offline bundle` is the tighter of the two and is why
    it is required rather than either-or: the digest is looked up by the asset
    *filename*, which is built from the bundled version, so a tag resolved online
    would name a file `checksums.txt` has no line for and fall through to the
    network instead of printing this.
    """
    if not machine.environment.offline:
        pytest.skip('only the offline environment installs from a bundle')
    assert 'Checksum verified from offline bundle' in machine.install_log
    assert 'installed from the bundle at' in machine.install_log


# ─────────────────────────────────────────────────────────────────────────────
# The sparse round trip
# ─────────────────────────────────────────────────────────────────────────────


def test_a_sparse_bundle_built_against_this_machine_reports_its_omissions_current(
    exchanging: tuple[Machine, Machine],
) -> None:
    """The whole feature, over the transport, between two containers.

    Everything below this in the suite exercises the sparse decision against a
    synthetic status and a hand-written `bundle.json`. What none of it can reach
    is the pair the feature actually is: a status a real machine produced, and a
    bundle a real `create_bundle` built by diffing against it. A wrong key on
    either side passes every one of those tests and produces a bundle that carries
    everything, reporting itself sparse.

    The assertion is the omission rather than the size. A smaller archive is the
    point and not the property — a build that omitted the wrong things would be
    smaller too. What has to hold is that every omission is *accounted for*: read
    either as carried by the full bundle underneath, or as measured and current.

    Not `measured` specifically, because this machine installed from a full bundle
    and the sparse one stages on top of it. The stack answering for those files is
    the feature working, so everything the sparse build omitted reads as covered
    here. `tests/matrix/test_sparse_bundles.py` owns the case where a sparse bundle
    stands alone and `measured` is the only possible answer.
    """
    machine, builder = exchanging

    # `status upload`, never `status show`. Only upload and the post-apply publish
    # pass the document through the redaction gate, so a trip built on `show`
    # cannot reach a gate that refuses every real document — which is what one did
    # for the whole life of the branch.
    exchange.ran(machine, 'dotfiles status upload')

    built = exchange.build_bundle_in(builder, machine.environment.manifest, against='latest')
    name = built.rsplit('/', 1)[-1]
    assert name.endswith('-sparse.tar.gz'), f'a sparse build has to say so in its own name: {name}'
    exchange.ran(builder, f'cd {builder.environment.home}/dotfiles && uv run dotfiles bundle upload')

    exchange.ran(machine, 'dotfiles bundle download --yes')
    exchange.ran(machine, f'dotfiles bundle stage $HOME/.cache/dotfiles/bundles/{name}')

    # The bundle's own account of what it left out, read off the copy that
    # crossed rather than the one that was built, so a document the installing
    # side could not parse fails here instead of passing on the builder.
    stem = name.removesuffix('.tar.gz')
    described = json.loads(machine.read(f'cat $HOME/.cache/dotfiles/staged/{stem}/bundle.json') or '{}')
    assert described.get('completeness') == 'sparse'
    assert described.get('current'), 'a converged machine has something for the build to leave out'

    checked = json.loads(machine.read('dotfiles bundle check --json') or '{}')
    left_out = {key.split('/', 1)[-1] for key in described['current']}
    accounted = set(checked['covered']) | set(checked['measured'])

    assert not left_out & set(checked['uncovered']), f'omitted and reported missing: {sorted(left_out & set(checked["uncovered"]))}'
    assert left_out <= accounted, f'omitted and unaccounted for: {sorted(left_out - accounted)}'
