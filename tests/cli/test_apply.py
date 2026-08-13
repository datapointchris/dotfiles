"""`apply`: what one run covers, in what order, and what it does with the results.

The central property is that **every provider reaches a run**, and it is asserted
against `registry.PROVIDERS` rather than against a list kept here. A second list
of what a run covers is a list that can disagree with the first, and the
disagreement is silent: a provider missing from it installs nothing and the run
reports success. `system/manager` sat unreachable that way for as long as a
hand-written one existed.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
from collections import Counter
from pathlib import Path

import pytest

from dotfiles import catalog
from dotfiles import coordinates
from dotfiles import deploy
from dotfiles import engine
from dotfiles import machine as machines
from dotfiles import paths
from dotfiles import reconcile
from dotfiles import registry
from dotfiles import resolve
from dotfiles import sinks
from dotfiles.effects import Completed
from dotfiles.event import Event
from dotfiles.event import Refusal
from dotfiles.event import Summary
from dotfiles.providers import npm
from dotfiles.providers import toolchain
from dotfiles.resolve import Stage
from dotfiles.resources import Change
from dotfiles.resources import Outcome
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.runs import Timing
from dotfiles.vocabulary import ExitCode

MACHINE = 'linux-lxc-server'
LINUX = coordinates.PLATFORM_BUNDLES['linux']


def busiest_owner() -> str:
    """The owner the declaration names most, read rather than typed here.

    No `OWNER` constant exists anywhere in the repo, and writing one in would be a
    name that rots the day a repo moves — what these tests need is an owner with
    entries behind it, not a particular one.
    """
    declaration = catalog.load()
    owners = Counter(entry.owner for section in catalog.SECTIONS for entry in declaration.section(section) if entry.owner)
    assert owners, 'no entry declares an owner, so --owner narrowing cannot be asserted'
    return owners.most_common(1)[0][0]


OWNER = busiest_owner()


@pytest.fixture(autouse=True)
def no_event_log(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the run's `.jsonl` out of the real state directory.

    Autouse rather than part of `quiet`, because the tests that leaked were the
    three stubbing `sinks.keep` inline instead of taking the fixture — so the
    next one written would have leaked too.

    `open_log` opens the log under the real `$XDG_STATE_HOME`, and it swallows
    its own errors by design, so nothing here ever failed. Every suite run left
    four empty logs in the fleet's Syncthing folder: 1372 of them against 143
    real runs by the time anything counted. Stubbing `keep` is what kept them
    recordless as well as empty, which is what made them read as a crashed apply
    rather than as test residue.

    `tests/cli/test_sinks.py` is where `open_log` itself is asserted on.
    """
    monkeypatch.setattr(sinks, 'open_log', lambda identity: None)


@pytest.fixture
def quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    """Everything a run does to the world that is not the walk itself."""
    monkeypatch.setattr('dotfiles.checkout.report_stray_branch', lambda: None)
    monkeypatch.setattr(sinks, 'keep', lambda *args, **kwargs: None)
    monkeypatch.setattr(deploy, 'epilogue', lambda session: None)


# ─────────────────────────────────────────────────────────────────────────────
# What a run covers
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('name', machines.names())
def test_every_provider_with_work_reaches_the_walk(name: str) -> None:
    """The property the registry was there to supply, asserted against the registry.

    A phase-to-provider table is a second list of the same fact, and it drifted:
    the system-packages phase selected `SYSTEM` and `SYSTEM_APPS`, so
    `system/manager` — the OS package upgrade, at `SYSTEM_UPGRADE` — was in no
    phase at all and `dotfiles apply` never once ran it. A whole-plan walk cannot
    reproduce that, because there is nothing to leave a provider out of.
    """
    plan = resolve.resolve(catalog.load(), machines.load(name))
    covered = engine.Selection.everything()

    for provider in {item.provider for item in plan.items}:
        owner = registry.named(provider)
        assert owner is not None, f'{provider} plans items and is in no registry'
        assert owner.resource in covered.resources, f'{provider} plans items no run reaches'


def test_a_whole_walk_reaches_env_and_identity() -> None:
    """Neither had a phase, so neither was ever part of `dotfiles apply`.

    `~/.env` was written by a call at the top of the run instead — unconditionally,
    from the manifest, by a second implementation of what the env resource
    measures. It is stage 10 of the walk now, so it is still written first, and
    only when it differs.
    """
    covered = engine.Selection.everything().resources

    assert 'env' in covered
    assert 'identity' in covered


def test_selecting_one_resource_narrows_to_it() -> None:
    """What `dotfiles packages apply` does."""
    assert engine.Selection.of('packages').resources == ('packages',)


def test_selecting_one_provider_keeps_its_resource_and_drops_its_neighbours() -> None:
    """`--source github_releases` is one address now rather than the intersection
    of a section against a hand-written phase-to-provider column."""
    selection = engine.Selection.of('packages/ghrelease')

    assert selection.resources == ('packages',)
    assert selection.providers == frozenset({'ghrelease'})


@pytest.mark.parametrize('name', machines.names())
def test_owner_narrowing_leaves_only_providers_with_something_to_install(name: str) -> None:
    """`--owner` narrows the plan rather than the selection, because ownership is
    a fact about the entries rather than about the walk."""
    plan = resolve.resolve(catalog.load(), machines.load(name), owner=OWNER)

    assert all(registry.named(provider) is not None for provider in plan.providers)
    assert plan.providers <= {provider.name for provider in registry.PROVIDERS}


@pytest.mark.parametrize('name', machines.names())
def test_owner_narrowing_reaches_the_walk_and_not_only_the_plan(name: str) -> None:
    """`symlinks`, `env`, `identity` and `auth` have no provider, so `ownable` never
    reaches them and an owner-narrowed *plan* leaves every one of them intact.

    Unnarrowed, `apply --owner X` deployed every symlink, wrote `~/.env` and
    `~/.gitconfig`, and ran the deployment epilogue — none of which has anything
    to do with X. The phase registry dropped the symlink phase because its
    `providers` tuple was empty and had no phase for the other two at all, so
    every part of this arrived with the walk.
    """
    plan = resolve.resolve(catalog.load(), machines.load(name), owner=OWNER)
    narrowed = engine.Selection.everything().narrowed_to(plan.providers)

    assert 'symlinks' not in narrowed.resources
    assert 'env' not in narrowed.resources
    assert 'identity' not in narrowed.resources
    assert 'auth' not in narrowed.resources
    assert set(narrowed.resources) <= {registry.named(provider).resource for provider in plan.providers}


def test_owner_narrowing_composes_with_skip() -> None:
    """Two narrowings intersect rather than one replacing the other: `--skip` says
    which addresses to leave alone and `--owner` says whose entries are wanted."""
    plan = resolve.resolve(catalog.load(), machines.load(MACHINE), owner=OWNER)
    narrowed = engine.Selection.excluding(('packages',)).narrowed_to(plan.providers)

    assert 'packages' not in narrowed.resources


def test_owner_narrowing_keeps_the_ceiling_it_was_handed() -> None:
    """`--owner` and `--through` arrive from different flags and must both survive.

    A narrowing that rebuilds the selection field by field drops whatever it was
    not written to know about, and the failure is silent in the safe-looking
    direction: `apply --owner X --through Y` would honour the owner and then
    converge the whole machine.
    """
    plan = resolve.resolve(catalog.load(), machines.load(MACHINE), owner=OWNER)
    narrowed = engine.Selection.everything().capped_at(Stage.TOOLS).narrowed_to(plan.providers)

    assert narrowed.through is Stage.TOOLS


def test_an_owner_with_nothing_here_plans_nothing(quiet: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """A stranger's name must refuse rather than converge: reporting success for a
    run that covered nothing is the failure the old empty-selection check caught.
    """
    monkeypatch.setenv('MACHINE', MACHINE)

    assert reconcile.apply_machine(engine.Selection.everything(), owner='nobody-at-all') is ExitCode.USAGE


# ─────────────────────────────────────────────────────────────────────────────
# What the run does with what it found
# ─────────────────────────────────────────────────────────────────────────────


class Walk:
    """A stand-in for the engine, yielding whatever a test needs it to have found."""

    def __init__(self, *events: Event, outcomes: tuple[Event, ...] = ()) -> None:
        self.assessed = events
        self.outcomes = outcomes
        self.acted = False

    def assess(self, session, selection=None):
        return iter(self.assessed)

    def execute(self, session, planned, privilege):
        self.acted = True
        return iter(self.outcomes)


def drift(item: str, repair: Repair = Repair.AUTOMATIC) -> Event:
    advice = 'do it by hand' if repair is Repair.BY_HAND else ''
    return Event('packages', Change('packages', Stage.TOOLS, item, Verdict.MISSING, repair=repair, advice=advice), stage=Stage.TOOLS)


def done(item: str, status: OutcomeStatus = OutcomeStatus.DONE) -> Event:
    change = Change('packages', Stage.TOOLS, item, Verdict.MISSING)
    return Event('packages', Outcome(change, status, f'{status} {item}'), stage=Stage.TOOLS)


def walked(monkeypatch: pytest.MonkeyPatch, walk: Walk) -> Walk:
    monkeypatch.setenv('MACHINE', MACHINE)
    monkeypatch.setattr(engine, 'assess', walk.assess)
    monkeypatch.setattr(engine, 'execute', walk.execute)
    return walk


def test_a_run_that_repaired_everything_converges(quiet: None, monkeypatch: pytest.MonkeyPatch) -> None:
    walked(monkeypatch, Walk(drift('ripgrep'), outcomes=(done('ripgrep'),)))

    assert reconcile.apply_machine(engine.Selection.everything()) is ExitCode.CONVERGED


def test_apply_json_is_the_record_the_run_wrote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """`apply --json` is an execution transcript, and `plan --json` is the versioned
    interchange document a network-blocked machine hands over to have a bundle built
    from it. Two different artifacts, which is why this is the stored record rather
    than `status.document` with a third verb.

    Asserted as equality with the file rather than against a shape typed here: the
    record is emitted by reading back what was just written, so a caller piping this
    and one reading `dotfiles report show --json` later cannot be given different
    answers about one run. Building the document twice is what would allow that.

    `quiet` is deliberately not used — it stubs `sinks.keep` out, and writing the
    record is the thing under test.
    """
    monkeypatch.setattr('dotfiles.checkout.report_stray_branch', lambda: None)
    monkeypatch.setattr(deploy, 'epilogue', lambda session: None)
    monkeypatch.setattr('dotfiles.paths.RUNS_DIR', tmp_path / 'runs')
    walked(monkeypatch, Walk(drift('ripgrep'), outcomes=(done('ripgrep'),)))

    reconcile.apply_machine(engine.Selection.everything(), as_json=True)

    emitted = json.loads(capsys.readouterr().out)
    stored = json.loads(next((tmp_path / 'runs').glob('*.json')).read_text())
    assert emitted == stored
    assert emitted['verb'] == 'apply'


def test_apply_says_nothing_on_stdout_unless_asked(quiet: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """Everything a run narrates goes to stderr, so stdout is a stream a caller can
    pipe. A progress line landing there would corrupt whatever reads it."""
    walked(monkeypatch, Walk(drift('ripgrep'), outcomes=(done('ripgrep'),)))

    reconcile.apply_machine(engine.Selection.everything())

    assert capsys.readouterr().out == ''


def test_a_group_is_announced_before_it_runs_rather_than_after(quiet: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """The longest part of a fresh install is one batched `apt-get install` over
    every declared package, and it returns its outcomes minutes later as one list.

    Announcing on the first outcome therefore leaves the screen blank through
    exactly the stretch a person is watching to see whether the run has hung —
    measured against a real container, where `dotfiles apply` printed nothing for
    four minutes while apt unpacked 33 packages. `Output.STREAM`'s own docstring
    records the same defect from the other side.
    """
    announced: list[str] = []

    def acting(session, planned, privilege):
        announced.append(f'acted:{planned[0].item}')
        return iter((done(planned[0].item),))

    monkeypatch.setenv('MACHINE', MACHINE)
    monkeypatch.setattr(engine, 'assess', lambda *args, **kwargs: iter((drift('ripgrep'),)))
    monkeypatch.setattr(engine, 'execute', acting)
    monkeypatch.setattr('dotfiles.reconcile.heading', lambda text: announced.append(f'heading:{text}'))

    reconcile.apply_machine(engine.Selection.everything())

    assert announced == ['heading:packages', 'acted:ripgrep']


def test_a_failed_write_is_an_issue(quiet: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """`install.sh` exited 0 whatever failed, because the phase layer returned
    booleans nothing looked at — so `install.sh && next-thing` chained straight
    past a broken machine."""
    walked(monkeypatch, Walk(drift('ripgrep'), outcomes=(done('ripgrep', OutcomeStatus.FAILED),)))

    assert reconcile.apply_machine(engine.Selection.everything()) is ExitCode.ISSUE


def test_a_refusal_is_not_a_failure(quiet: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """A precondition an earlier stage could not deliver wrote nothing and did
    nothing wrong. Counting it would make every container without passwordless
    sudo report a failed install."""
    walked(monkeypatch, Walk(drift('win32yank'), outcomes=(done('win32yank', OutcomeStatus.REFUSED),)))

    assert reconcile.apply_machine(engine.Selection.everything()) is ExitCode.CONVERGED


def test_a_resource_that_could_not_be_examined_is_an_issue(quiet: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """It was in the selection, so part of the machine went unconverged. The phase
    layer dropped these on the floor: `_converge` filtered the stream to `Change`
    before looking at it, so a checker that crashed was invisible to `apply`."""
    walked(monkeypatch, Walk(Event('packages', Refusal('pacman is not installed'))))

    assert reconcile.apply_machine(engine.Selection.everything()) is ExitCode.ISSUE


def test_what_apply_cannot_repair_is_reported_and_does_not_move_the_exit_code(quiet: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """`apply` answers whether the work it attempted succeeded; whether anything
    is *wrong* is `check`'s question.

    A machine-local value nobody has set and a file only safekeep restores are
    real findings and not this run's failures — exiting non-zero for them makes
    every freshly-installed work box look broken between the install and the
    restore, which is the permanently-failed shape the verb split exists to end.
    """
    walked(monkeypatch, Walk(drift('WINDOWS_USER', repair=Repair.BY_HAND)))

    assert reconcile.apply_machine(engine.Selection.everything()) is ExitCode.CONVERGED


def test_the_run_records_both_what_was_decided_and_what_was_done(monkeypatch: pytest.MonkeyPatch) -> None:
    """`apply` recorded nothing until now, and the reason was structural: its phase
    layer returned booleans, so there was no per-item value to keep."""
    kept: list[tuple] = []
    monkeypatch.setattr('dotfiles.checkout.report_stray_branch', lambda: None)
    monkeypatch.setattr(deploy, 'epilogue', lambda session: None)
    monkeypatch.setattr(sinks, 'keep', lambda events, identity, flags: kept.append((list(events), identity)))
    walked(monkeypatch, Walk(drift('ripgrep'), outcomes=(done('ripgrep'),)))

    reconcile.apply_machine(engine.Selection.everything())

    events, identity = kept[0]
    assert (identity.machine, identity.verb) == (MACHINE, 'apply')
    assert [type(event.payload).__name__ for event in events] == ['Change', 'Outcome']
    # Stamped before the walk, not when the record is assembled afterwards, or the
    # run's own duration measures the loop over an already-collected list.
    assert identity.started < dt.datetime.now(dt.UTC)


# ─────────────────────────────────────────────────────────────────────────────
# The deployment epilogue
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def deployments(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every machine the epilogue ran for, with the rest of a run silenced.

    Not `quiet`, which stubs the epilogue out — this is the one thing these tests
    are looking at.
    """
    ran: list[str] = []
    monkeypatch.setattr('dotfiles.checkout.report_stray_branch', lambda: None)
    monkeypatch.setattr(sinks, 'keep', lambda *args, **kwargs: None)
    monkeypatch.setattr(deploy, 'epilogue', lambda session: ran.append(session.machine_name))
    return ran


def test_the_epilogue_follows_a_walk_that_deployed(deployments: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """It has to run whether or not the pass changed anything: `~/.gitconfig` has
    to exist on a converged machine too, or `git config --global` writes into the
    repo through the link this deploys.
    """
    walked(monkeypatch, Walk())

    reconcile.apply_machine(engine.Selection.of('symlinks'))

    assert deployments == [MACHINE]


def test_a_walk_that_did_not_deploy_skips_it(deployments: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """`dotfiles packages apply` deployed nothing, so there is nothing to reload
    and no Windows host to copy a shell profile to."""
    walked(monkeypatch, Walk())

    reconcile.apply_machine(engine.Selection.of('packages'))

    assert deployments == []


def test_a_ceiling_below_the_symlink_stage_deploys_nothing_and_so_runs_no_epilogue(
    deployments: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`--through` has to reach the work and not only the plan.

    Every job here is justified by "the pass above just deployed these files": git
    needs somewhere to write that is not this repo, Hyprland has to reload the
    config that landed, and WSL copies the shell profile onto the Windows host.
    Under a ceiling that deploys nothing they act on files nobody wrote.
    """
    walked(monkeypatch, Walk())

    reconcile.apply_machine(engine.Selection.of('symlinks').capped_at(Stage.SYSTEM_UPGRADE))

    assert deployments == []


def test_a_ceiling_at_the_symlink_stage_still_runs_it(deployments: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """The inverse mistake: a ceiling that includes the pass must not silently drop
    the three jobs that finish it."""
    walked(monkeypatch, Walk())

    reconcile.apply_machine(engine.Selection.of('symlinks').capped_at(Stage.SYMLINKS))

    assert deployments == [MACHINE]


# ─────────────────────────────────────────────────────────────────────────────
# Nothing hands work to a shell
# ─────────────────────────────────────────────────────────────────────────────


SHELLS = frozenset({'bash', 'sh', 'zsh', 'dash'})

SHELL_SURVIVORS = frozenset({'sync-windows-shell.sh'})
"""The one script a run may still reach, and only on a WSL host.

Git Bash reads the `.bashrc` it writes, so its *output* has to be shell; the
generator does not, and step E converts it. Named here rather than tolerated, so
that conversion empties this set and anything else appearing in it is new.
"""


@pytest.mark.parametrize('name', machines.names())
def test_no_part_of_a_run_hands_work_to_a_shell(name: str, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """The property the whole conversion is for, asserted by running the verb.

    Asserting that the removed symbols are gone would pass for a new caller of
    `effects.run(['bash', ...])`, which is the shape the conversion exists to
    end — so this records what actually reached the world.

    The engine is stubbed rather than exercised: what it does with a plan is its
    own tests' subject, and what this asks is whether the *verb* reaches a shell
    around it. Every machine, because the two gated calls in `deploy.epilogue`
    fire on coordinates rather than on anything the walk decided.
    """
    invoked: list[tuple[str, ...]] = []

    def record(command, **kwargs):
        argv = tuple(str(part) for part in command)
        invoked.append(argv)
        return Completed(argv, 0, '')

    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('MACHINE', name)
    monkeypatch.setattr('dotfiles.checkout.report_stray_branch', lambda: None)
    monkeypatch.setattr(sinks, 'keep', lambda *args, **kwargs: None)

    # Asserted rather than guarded, and in both directions. A module that stops
    # binding `effects.run` turns a guarded patch into a silent no-op, so this test
    # would pass having recorded nothing at all; one that starts binding it goes
    # unpatched and shells out unseen. Either way the fix is to edit this set, which
    # is what the failure says.
    binding = {module.__name__ for module in (reconcile, deploy) if hasattr(module, 'run')}
    assert binding == {'dotfiles.deploy'}, f'update the patch list below: {sorted(binding)} bind effects.run'
    monkeypatch.setattr(deploy, 'run', record)
    walked(monkeypatch, Walk())

    reconcile.apply_machine(engine.Selection.everything())

    shelled = [argv for argv in invoked if Path(argv[0]).name in SHELLS]
    stowaways = [argv for argv in shelled if Path(argv[-1]).name not in SHELL_SURVIVORS]
    assert stowaways == [], f'{name}: a run handed work to a shell'


# ─────────────────────────────────────────────────────────────────────────────
# The machine the run is about
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('label', sorted(coordinates.PLATFORM_BUNDLES))
def test_every_platform_bundle_round_trips_to_its_label(label: str) -> None:
    """The overlay is keyed on coordinates now, and the four labels are only a
    convenience bundle over them — so each must still come out with the name the
    scripts and the shell overlays know it by."""
    assert coordinates.platform_label(coordinates.PLATFORM_BUNDLES[label]) == label


def test_a_machine_declaring_coordinates_still_has_a_label() -> None:
    """Arch-on-WSL is the case the coordinate split exists for, and it has no
    `platform:` key to read a label from. Derived, it lands on the pacman answer —
    which is what a fused PLATFORM string had no row for.
    """
    arch_on_wsl = dataclasses.replace(coordinates.PLATFORM_BUNDLES['archlinux'], host=coordinates.Host.WSL)

    assert coordinates.platform_label(arch_on_wsl) == 'archlinux'
    assert machines.load(MACHINE).platform_label == coordinates.platform_label(LINUX)


def test_the_machine_is_read_from_the_env_file_when_the_environment_is_bare(
    quiet: None,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`Session.resolve` reads `~/.env` as well as the environment, for a reason it
    states: a systemd user timer, a launchd agent, `docker exec` and cron inherit
    none. `apply` had a second resolver that never learned it, so `dotfiles apply`
    with no `--machine` failed with "MACHINE is not set" on a machine whose
    `~/.env` said exactly what it was — found by the e2e idempotence assertion,
    which is a bare `docker exec`. There is one resolver now.
    """
    monkeypatch.delenv('MACHINE', raising=False)
    monkeypatch.setenv('HOME', str(tmp_path))
    (tmp_path / '.env').write_text(f'MACHINE={MACHINE}\n')
    walk = walked(monkeypatch, Walk(drift('ripgrep'), outcomes=(done('ripgrep'),)))
    monkeypatch.delenv('MACHINE', raising=False)

    assert reconcile.apply_machine(engine.Selection.everything()) is ExitCode.CONVERGED
    assert walk.acted, 'it resolved the machine but never reached the walk'


def test_a_machine_named_nowhere_at_all_is_a_usage_error(quiet: None, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('MACHINE', raising=False)
    monkeypatch.setenv('HOME', str(tmp_path))

    assert reconcile.apply_machine(engine.Selection.everything()) is ExitCode.USAGE


def test_the_declaration_is_read_once_however_much_a_run_asks_of_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """One read of the catalog and one of the machine, whatever the walk covers.

    The seventeen phases each held a `Session` that was a plain property, so one
    `apply --owner` parsed the 258-entry packages.yml seven times and resolved
    seven manifests. There is one `Session` per run now and nothing left to get
    this wrong.
    """
    reads = {'catalog': 0, 'machine': 0}
    for module, name, key in ((catalog, 'load', 'catalog'), (machines, 'load', 'machine')):
        original = getattr(module, name)

        def counted(*args: object, _original=original, _key=key, **kwargs: object) -> object:
            reads[_key] += 1
            return _original(*args, **kwargs)

        monkeypatch.setattr(module, name, counted)

    session = reconcile.Session.resolve(MACHINE, owner=OWNER)
    for _ in range(len(registry.PROVIDERS)):
        _ = session.plan

    assert reads == {'catalog': 1, 'machine': 1}


# ─────────────────────────────────────────────────────────────────────────────
# Where a stage finds what an earlier stage installed
# ─────────────────────────────────────────────────────────────────────────────


def test_every_directory_an_installer_writes_binaries_to_is_on_the_run_path() -> None:
    """Installing into a directory no later stage can see is a silent failure, and
    it happened: the npm installer set its own NPM_CONFIG_PREFIX, `.zshrc` added
    that prefix's bin for interactive shells, and nothing else did. All eleven
    language servers installed correctly and every non-interactive check —
    including the install's own verification — reported them missing.

    The prefix is read from the provider that sets it rather than restated here,
    so moving it fails this instead of going unnoticed until a container reports
    sixteen missing tools.
    """
    assert f'$HOME/{npm.PREFIX}/bin' in toolchain.TOOL_PATH_DIRS, f'{npm.PREFIX}/bin is where npm globals land, and no stage can see it'


def test_the_non_interactive_shell_sees_what_the_run_installed() -> None:
    """`.zshenv` is the PATH a script, an SSH command, a timer and an LSP spawned
    outside a login shell all get. Anything only `.zshrc` adds exists for a human
    at a prompt and for nobody else.
    """
    zshenv = (paths.REPO_ROOT / 'configs' / 'common' / '.config' / 'zsh' / '.zshenv').read_text()
    exported = [line for line in zshenv.splitlines() if line.startswith('export PATH=')]
    assert exported, '.zshenv no longer sets PATH'

    # /usr/local/go/bin is deliberately absent: `go` is reached through the
    # symlink the release installer puts in ~/.local/bin, and .zshenv is meant to
    # stay minimal.
    for directory in toolchain.TOOL_PATH_DIRS:
        if directory.startswith('/usr'):
            continue
        assert directory in exported[0], f'{directory} is on the run PATH but not on a non-interactive shell PATH'


def test_apply_reports_what_each_resource_cost_before_it_acts(
    quiet: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """An apply prints its rule and then measures the whole machine before writing
    anything, so on the work box that stretch was minutes of blank screen with the
    rule already scrolled past. The summary row is the only thing that says which
    part of the machine the wait belonged to."""
    measured = Event('packages', Summary('all 96 declared packages are installed'), timing=Timing('', 291.4))
    walked(monkeypatch, Walk(measured, drift('ripgrep'), outcomes=(done('ripgrep'),)))

    reconcile.apply_machine(engine.Selection.everything())

    narrated = capsys.readouterr().err
    assert 'all 96 declared packages are installed' in narrated
    assert '4m51.4s' in narrated


def test_a_streamed_walk_is_still_handed_over_whole(quiet: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Consumed one event at a time so the announcements arrive during the wait,
    and collected all the same — everything below still reads the list whole."""
    walk = Walk(drift('ripgrep'), drift('fd'), outcomes=(done('ripgrep'), done('fd')))
    walked(monkeypatch, walk)

    assert reconcile.apply_machine(engine.Selection.everything()) is ExitCode.CONVERGED
    assert walk.acted
