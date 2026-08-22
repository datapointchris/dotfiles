"""Shared test fixtures.

Modules under `install/` are importable by name — `pythonpath` in pyproject.toml
names their directories. Apps are not: a command is `aws-profiles`, not
`aws_profiles.py`, and a filename with a hyphen and no extension is not a module
name. `load_app` loads one by path so its functions can still be called directly
rather than only exercised through a subprocess.
"""

import os

# Before typer is imported, because typer.rich_utils reads both of these at
# module scope and never again. `FORCE_TERMINAL` is True whenever GITHUB_ACTIONS
# is set, so on a runner typer renders usage errors in colour and rich's
# highlighter splits the option name — `--source` arrives as
# `-\x1b[0m\x1b[1;36m-source`, and `assert 'No such option: --source' in stderr`
# cannot match. Locally it always matches, so the whole class of assertion passes
# on a desk and fails in CI. Eight tests did exactly that.
#
# `_TYPER_FORCE_DISABLE_TERMINAL` is typer's own escape hatch for this, read one
# line above the variable it overrides. Set here rather than in a fixture: by the
# time any fixture runs, the module-level constant is already computed.
os.environ.setdefault('_TYPER_FORCE_DISABLE_TERMINAL', '1')

import importlib.machinery  # noqa: E402
import importlib.util  # noqa: E402
import shutil  # noqa: E402
import stat  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402
from types import ModuleType  # noqa: E402

import levels  # noqa: E402
import pytest  # noqa: E402

from dotfiles.privilege import Privilege  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

# The suite reads the checkout it lives in, whatever the shell says.
#
# `paths.REPO_ROOT` lets `$DOTFILES_DIR` win unconditionally, which is right for
# the CLI: `.zshenv` pins it to ~/dotfiles so a shell standing in a worktree
# cannot deploy that worktree's config over the machine's. It is wrong here — a
# run inside a worktree would exercise the worktree's code against ~/dotfiles's
# packages.yml, manifests and configs, green against a declaration the branch
# never touched. Proven the day the worktree workflow landed: the step-B branch
# adds `reports_version` to packages.yml and a run from its worktree could not
# see it.
#
# It has to happen before anything imports `dotfiles.paths`, which resolves the
# root once at import — so the assert is the guard, not a formality. Nothing
# above pulls that module in today, and this fails loudly on the day something
# does rather than silently reading the wrong tree again.
assert 'dotfiles.paths' not in sys.modules, 'something above imported dotfiles.paths, so DOTFILES_DIR is already resolved'
os.environ['DOTFILES_DIR'] = str(REPO)

GIT_LOCATION = (
    'GIT_DIR',
    'GIT_WORK_TREE',
    'GIT_COMMON_DIR',
    'GIT_INDEX_FILE',
    'GIT_OBJECT_DIRECTORY',
    'GIT_ALTERNATE_OBJECT_DIRECTORIES',
    'GIT_PREFIX',
    'GIT_NAMESPACE',
)
"""The variables that decide *which repository* a `git` command acts on.

Dropped for the whole session, because a dozen fixtures build a throwaway repo in
`tmp_path` and every one of them would otherwise operate on the caller's.

git exports these when it runs a hook, so the caller is routinely `git commit`
itself — and this held only by accident until worktrees. In a normal checkout
`GIT_DIR` is the relative `.git`, which resolves harmlessly inside whatever
directory a fixture had chdir'd to; in a worktree it is absolute, so `git init`
made a repo in `tmp_path` and the `git commit` after it wrote to the real one and
exited non-zero. Eighteen errors and three failures, under `pre-commit` only, on
a suite that passes when run directly.
"""

for variable in GIT_LOCATION:
    os.environ.pop(variable, None)

APPS_DIR = REPO / 'apps'


# Both opt-in tiers are declared here rather than beside the tests they gate.
# pytest only calls `pytest_addoption` on an *initial* conftest — the rootdir's —
# so the copy that lived in `tests/e2e/conftest.py` registered only when pytest
# was pointed straight at that directory, and `pytest tests/ --docker` failed
# with `unrecognized arguments`.
TIERS = {
    '--e2e': ('e2e', 'also run tests that reach the real network', 'reaches the real network; pass --e2e to run'),
    '--docker': (
        'docker',
        'run the container installs (tens of minutes each)',
        'installs a whole machine in a container; pass --docker to run',
    ),
    '--replants': (
        'replants',
        'run the mutation tests that spawn a pytest per mutant',
        'spawns its own pytest per mutant; pass --replants to run',
    ),
}


def pytest_addoption(parser):
    for flag, (_, help_text, _reason) in TIERS.items():
        parser.addoption(flag, action='store_true', default=False, help=help_text)
    parser.addoption(
        '--require-interpreters',
        action='store_true',
        default=False,
        help='refuse to run rather than skip when a test needs an interpreter this machine lacks',
    )
    parser.addoption(
        '--require-images',
        action='store_true',
        default=False,
        help='refuse to run rather than skip when an e2e level cannot start its container',
    )
    parser.addoption('--keep', action='store_true', default=False, help='leave e2e containers running afterwards')
    parser.addoption('--reuse', action='store_true', default=False, help='reuse a kept container and any built bundle')
    parser.addoption(
        '--installed',
        action='store_true',
        default=False,
        help='assert against the install already in the container instead of running one',
    )
    # Selection by environment cannot be `-k`, which matches test names too:
    # `-k offline` also matched `test_the_offline_run_never_resolved_a_version_online`
    # and so selected all four environments. The run started a second Arch
    # container, `docker rm -f` took the name from the Arch install running in
    # another process, and that install died at 137 looking like an OOM.
    # `tests/e2e/conftest.py` does the deselecting; the option has to be declared
    # here for the same reason the tiers above do.
    parser.addoption('--environment', default='', help='e2e environments to run, comma-separated (default: all)')
    # One knob for a rung of the ladder, because the rungs were addressed by a
    # file path and a flag combination and so had to be remembered. It selects
    # *and* sets the mode: `installed` and `full` are the same tests, and
    # `--installed` is the whole difference between them.
    parser.addoption(
        '--level', default='', help='one rung of the ladder, by name or number; `tests/e2e/levels.py` is what each costs and answers'
    )


INSTALLING = {
    ('go', 'install'),
    ('cargo', 'install'),
    ('cargo', 'binstall'),
    ('npm', 'install'),
    ('uv', 'tool'),
    ('uv', 'python'),
    ('fnm', 'install'),
    ('pacman', '-S'),
    ('pacman', '-Syu'),
    ('yay', '-S'),
    ('apt-get', 'install'),
    ('apt-get', 'update'),
    ('apt', 'install'),
    ('brew', 'install'),
    ('brew', 'tap'),
    ('mas', 'install'),
    ('flatpak', 'install'),
}
"""Commands that would install something on the machine running the suite.

A pair rather than a binary name, because `go version` and `uv --version` are
reads a unit test may legitimately want and only the second word separates them.

Removals are deliberately absent, and so are the two supervisors. Every test that
drives one puts a fake `brew`, `pacman`, `launchctl` or `systemctl` on PATH and
asserts the argv it was handed — which is the pattern `standards/testing.md` asks
for, and a denylisted pair blocks it whether the binary on PATH is real or not. The
one call that pattern does not reach is `no_stopping_this_machines_daemons`.
"""

REDIRECTED_STATE = 'Dir::State::lists='
"""The option that turns an `apt-get update` into a read of somebody else's directory.

`('apt-get', 'update')` is on the list above because the bare form rewrites
`/var/lib/apt/lists` and needs root for it. Pointed at a scratch directory it
writes only there, which is how `syspkg._apt_outdated` measures apt currency
without escalating — a read, and the guard has to be able to tell them apart.
"""

REDIRECTABLE = frozenset({('apt-get', 'update')})
"""The one denylisted pair a redirect makes harmless, named rather than inferred.

Every apt subcommand takes `Dir::State::lists`, and on `apt-get install` it moves
where the *index* is read from while the packages still land on the machine. So the
option cannot be read as "this is a read" on its own — the exemption is this pair
plus that option, and nothing else.
"""


def would_change_this_machine(argv: tuple[str, ...]) -> bool:
    """Whether a denylisted pair is really the form that writes to the machine."""
    if argv[:2] not in INSTALLING:
        return False
    redirected = any(part.startswith(REDIRECTED_STATE) for part in argv)
    return not (redirected and argv[:2] in REDIRECTABLE)


class WouldInstall(BaseException):
    """Raised where an install was attempted, and deliberately not an `Exception`.

    `engine._measure` and `engine._act` both wrap a resource in `except Exception`
    and turn what it raised into a `Refusal`, because one checker crashing must not
    end the walk. That isolation swallows a guard raised as an `AssertionError`:
    the install is still refused, but the run reports a refused resource and exits
    3, which reads as a resource that could not be examined rather than as a test
    that tried to change this machine.

    A `BaseException` passes straight through, which is the same reason
    `pytest.fail` raises one.
    """


@pytest.fixture(autouse=True)
def logging_is_configured():
    """Unconfigured structlog writes to stdout, which the suite must never see.

    `main.root` configures it for every real invocation, so production is covered
    — but a test calling into `effects` or a provider directly never reaches that
    callback, and structlog's default `PrintLogger` would put debug lines on
    stdout, where a `--json` assertion is reading. Configured with no event log,
    so the console sink alone is live and nothing writes a file.

    Per test rather than per session, because a test that exercises `open_log`
    installs a file handler onto a `tmp_path` that is gone by the next one, and a
    bound `run_id` outlives the test that bound it. Both are cheap to redo and
    neither is cheap to debug.
    """
    from dotfiles import logging as dotfiles_logging

    dotfiles_logging.choose_console()
    dotfiles_logging.configure()
    dotfiles_logging.clear_run()


@pytest.fixture(autouse=True)
def a_token_lookup_that_forgot_the_last_test():
    """Clear the memoised `github_token`, which is per-process and a suite is one.

    `github_release.github_token` caches so a refresh does not spawn `gh auth token`
    once per declared release. That is right for an invocation and wrong for a
    suite: a test setting `$GITHUB_TOKEN` would otherwise be answered with whatever
    the first test to ask happened to find, and the one it poisons is not the one
    that set it — which is a failure that moves when tests are reordered.

    Autouse rather than named by the tests that need it, because needing it is not
    visible from the test that breaks.
    """
    from dotfiles import github_release

    github_release.github_token.cache_clear()
    yield
    github_release.github_token.cache_clear()


class ReachedTheNetwork(BaseException):
    """Raised where a test made an HTTP request, and deliberately not an `Exception`.

    `engine._measure` wraps every resource in `except Exception` and turns what it
    raised into a `Refusal`, so a guard raised as one is caught by the code under
    test: the request is refused, the run reports the resource as unexaminable, and
    the test passes its exit-code assertion having learned nothing.

    Same reasoning as `WouldInstall`, and as `matrix.harness.ReachedTheNetwork`.
    """


@pytest.fixture(autouse=True)
def no_network_from_a_test(request, monkeypatch):
    """Refuse every HTTP request outside the tiers that declare they make them.

    `tests/matrix/` guarded itself and nothing else did, so `tests/install/`,
    `tests/cli/` and `tests/resources/` could reach GitHub. Measured 2026-08-22:
    one `pytest tests/` spent 17 requests against the rate limit, and
    `test_a_refresh_passes_the_prefix_through` asserted against `cli/v0.25.0` —
    what ichrisbirch had published that morning, not what the test wrote.

    That is the failure worth stopping. A test reading live upstream passes today
    and fails the week something ships, and the version it read is nowhere in the
    test.

    Guarded at `httpx2.get` and `HTTPTransport.handle_request`, which sit between
    every caller and the socket — including a `Client` built somewhere else. Our own
    `github_release.request` would prove only that nobody called that one, which is
    the gap `no_installing_on_this_machine` documents about `effects.run`.

    `tests/matrix/` patches these again with its own exception type, which its tests
    name in `pytest.raises`. A child conftest's autouse fixture runs after this one,
    so that one wins where both apply.
    """
    if request.node.get_closest_marker('e2e') or request.node.get_closest_marker('docker'):
        return

    import httpx2

    def refuse(*_args, **_kwargs):
        raise ReachedTheNetwork('a test made an HTTP request — stub the transport, or mark the test e2e')

    monkeypatch.setattr(httpx2, 'get', refuse)
    monkeypatch.setattr(httpx2.HTTPTransport, 'handle_request', refuse)


@pytest.fixture(autouse=True)
def no_installing_on_this_machine(request, monkeypatch):
    """Refuse a command that would change the box the tests run on.

    Not caution. A provider converted while the fixture that stubs its installer
    named only its two predecessors, and the resulting `pytest tests/` reached
    proxy.golang.org and rewrote `~/go/bin/task` — green, and indistinguishable
    from a suite that had stubbed everything. The tier system already says which
    tests may reach the world; this is what makes the rest unable to.

    **Guarded at `subprocess`, not at `effects.run`.** Most of the package binds
    `run` at import (`from dotfiles.effects import run`), so a patch on the
    `effects` module never reaches those callers — which is exactly how the
    incident above got past a test that thought it had stubbed the runner. Every
    binding lands here.

    Denylisted argv only, so a test driving `git`, `bash` or `which` through the
    same door is untouched.
    """
    if request.node.get_closest_marker('e2e') or request.node.get_closest_marker('docker'):
        return

    import subprocess

    def refuse_installs(original):
        def guarded(command, *args, **kwargs):
            argv = tuple(str(part) for part in command) if isinstance(command, list | tuple) else ()
            if would_change_this_machine(argv):
                raise WouldInstall(f'{" ".join(argv)} would install on this machine — stub the provider, or mark the test e2e')
            return original(command, *args, **kwargs)

        return guarded

    monkeypatch.setattr(subprocess, 'run', refuse_installs(subprocess.run))
    monkeypatch.setattr(subprocess, 'Popen', refuse_installs(subprocess.Popen))


@pytest.fixture(autouse=True)
def no_stopping_this_machines_daemons(request, monkeypatch):
    """Refuse the one supervisor call PATH shadowing does not already contain.

    Every other `systemctl` and `launchctl` in this package is reached only through
    a code path whose tests narrow PATH — `providers/schedule.py`'s through
    `fake_bin`, `ghrelease.supervise`'s through the `home` fixture — so a fake
    answers and the argv is what gets asserted. `systemd.disable` is the exception:
    `syspkg.stop_service` reaches it from a *displacement*, which a test stubs at
    `syspkg.uninstall` one line further on, and the manager deciding the branch is
    the machine's rather than the test's. On this desk that call stops syncthing.

    A test that means to exercise it overrides `systemd.disable` with a spy of its
    own, which shadows this for the duration.
    """
    if request.node.get_closest_marker('e2e') or request.node.get_closest_marker('docker'):
        return

    from dotfiles.providers import systemd

    def refuse(unit):
        raise WouldInstall(f'systemctl --user disable --now {unit} would stop a daemon on this machine — spy on it, or mark the test e2e')

    monkeypatch.setattr(systemd, 'disable', refuse)


@pytest.fixture(scope='session', autouse=True)
def no_run_artefacts_on_this_machine(request):
    """Fail the session if it left a run artefact in the real state directory.

    The counterpart to `no_installing_on_this_machine`, covering the other thing
    a verb writes to the box it runs on. `sinks.open_log` swallows its own errors
    by design, so a test that reaches it leaves a file and reports nothing. 1372
    empty `.jsonl` accumulated beside 143 real runs before anything counted, in a
    directory Syncthing shares with the rest of the fleet — and each looked like
    an apply that had died on the spot, because the stubbed `keep` left no record
    next to it.

    Session-scoped: listing the directory once per test costs more than the leak
    does, and one filename at the end is enough to find whoever wrote it.

    Skipped under `--docker`, where an install writes its records inside the
    container and the host's directory is not the subject.

    Two things arriving in that directory during a session are not leaks, and both
    will otherwise refuse a commit for something the suite did not do.
    A peer machine's record is delivered there by Syncthing; `runs.begin` defaults
    a record's host to `paths.MACHINE_ID`, so anything the suite could write
    carries this box's id and a file naming another one was not written here.
    And a `dotfiles` verb run by a person or a second session on this box writes
    a real record while the suite happens to be running.

    What the suite leaks is empty, which is what separates it from both: the
    stubbed `keep` returns before anything is written, so the file is created and
    never filled. That is the shape of all 1372.
    """
    from dotfiles import paths

    def artefacts() -> set[str]:
        """New, empty, and this machine's — a record no run finished writing."""
        if not paths.RUNS_DIR.is_dir():
            return set()
        return {
            path.name
            for path in paths.RUNS_DIR.iterdir()
            if f'-{paths.MACHINE_ID}-' in path.name and path.is_file() and path.stat().st_size == 0
        }

    if request.config.getoption('docker'):
        yield
        return

    before = artefacts()
    yield
    leaked = sorted(artefacts() - before)
    assert not leaked, f'the suite wrote {len(leaked)} run artefact(s) into {paths.RUNS_DIR}, starting {leaked[:4]}'


def pytest_configure(config):
    """A level sets the modes it means, before anything is collected.

    `--level full` has to imply `--docker` or the tier deselection below skips
    every test it just asked for; `--level installed` has to imply `--installed`
    or it runs the twenty-four-minute version of itself. Both are what makes one
    knob a rung rather than a third thing to combine by hand.

    Written onto the option values rather than checked at each use site, so
    everything downstream keeps reading the flags it already read.
    """
    if not (wanted := str(config.getoption('--level')).strip()):
        return

    level = levels.resolve(wanted)
    if level.docker:
        config.option.docker = True
    if level.installed:
        config.option.installed = True


def pytest_collection_modifyitems(config, items):
    """Deselect an opt-in tier unless it is asked for.

    Here rather than in `addopts`, which forge owns: a deselection written there
    is erased by the next sync-pyproject run.

    `get_closest_marker` rather than `in item.keywords`: keywords carry every
    ancestor node's name as well as the markers, so the membership test also
    matched every test under a *directory* named `e2e` — silently skipping the
    whole container suite, which is marked `docker` and asked for with `--docker`.
    """
    for flag, (marker, _help, reason) in TIERS.items():
        if config.getoption(flag):
            continue
        skip = pytest.mark.skip(reason=reason)
        for item in items:
            if item.get_closest_marker(marker):
                item.add_marker(skip)

    resolve_interpreters(config, items)


def resolve_interpreters(config, items):
    """Skip what needs a missing interpreter, or refuse the whole run.

    `tests/shell` drives real bash and zsh, and `tests/install/test_pluginsync.py`
    a real tmux. A machine without one should
    skip those cases and still run the rest; CI must do the opposite, because a
    runner image that has no zsh reports green having run a third of that
    directory. Both readings are right for their runner, which is why the marker
    only states the requirement and this decides what it means.

    The enforced set is read back off the collected items rather than written
    down anywhere, so it is exactly what the tests ask for. A workflow step
    proving two named binaries exist is a different claim that only looks like
    this one — it stays green after the last test needing them is deleted, and
    stays green when a new test starts needing a third.
    """
    required = {marker.args[0] for item in items for marker in item.iter_markers('interpreter')}
    missing = sorted(name for name in required if shutil.which(name) is None)

    if config.getoption('--require-interpreters'):
        if missing:
            raise pytest.UsageError(f'--require-interpreters, but this machine has no {", ".join(missing)}')
        return

    for item in items:
        for marker in item.iter_markers('interpreter'):
            if shutil.which(marker.args[0]) is None:
                item.add_marker(pytest.mark.skip(reason=f'{marker.args[0]} is not installed'))


def load_app(name: str, platform: str = 'common') -> ModuleType:
    """Import an executable from apps/<platform>/ under a usable module name.

    The loader is used directly rather than through spec.loader, which is
    Optional and would need narrowing at every call.
    """
    path = APPS_DIR / platform / name
    module_name = name.lstrip('_').replace('-', '_')

    loader = importlib.machinery.SourceFileLoader(module_name, str(path))
    spec = importlib.util.spec_from_loader(module_name, loader)
    if spec is None:
        raise ImportError(f'could not load {path}')

    module = importlib.util.module_from_spec(spec)
    # Registered before it is executed, which is what importlib's own docs
    # prescribe. `dataclass` under `from __future__ import annotations` resolves
    # its string annotations through sys.modules[cls.__module__], so a module
    # missing from there dies at the decorator with an AttributeError about
    # NoneType that names neither the module nor the field.
    sys.modules[module_name] = module
    loader.exec_module(module)
    return module


@pytest.fixture(scope='session')
def aws_profiles():
    return load_app('_aws-profiles')


@pytest.fixture(scope='session')
def worktree_app():
    return load_app('worktree')


@pytest.fixture(scope='session')
def tmux_rearrange():
    return load_app('tmux-rearrange')


@pytest.fixture
def unprivileged() -> Privilege:
    """A `Privilege` that will not offer a prompt, which is what refuses.

    Every resource but `system` takes one and ignores it — `perform` carries it
    so that `observe` cannot — so a test of one of those wants the object that
    proves nothing escalated rather than a mock that would let it. `offer=False`
    is also what a non-interactive caller passes in production: root is acquired
    at the write now, so a bare `Privilege()` in a test would prompt for real.
    """
    return Privilege(offer=False)


@pytest.fixture
def fake_bin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A bin directory first on PATH, with the real system dirs still behind it.

    `/usr/bin:/bin` stays, or `git`, `bash` and `install` raise FileNotFoundError
    and a fixture cannot run its own helpers. Shadowing by name rather than
    emptying PATH is what keeps these tests from reading the machine they run on:
    without it, "dpkg-query refuses to answer" holds on Arch for the wrong reason
    and inverts on every Debian CI runner.

    The GNU userland directory rides behind those on macOS, where `/usr/bin/install`
    is the BSD one and has no `-D`. `sysconfig.apply` writes with `install -D` to
    create a parent directory the same way the privileged path does on a real
    machine, so without this the whole managed-file suite fails against a flag the
    platform never had. Resolved through `install` itself rather than by naming
    Homebrew's path, because that path differs between Intel and Apple silicon.
    """
    directory = tmp_path / 'bin'
    directory.mkdir()
    system = [Path(found).parent for name in ('install',) if (found := shutil.which(name))]
    behind = [str(path) for path in system if path not in (Path('/usr/bin'), Path('/bin'))]
    monkeypatch.setenv('PATH', os.pathsep.join([str(directory), *behind, '/usr/bin', '/bin']))
    return directory


def _executable(directory: Path, name: str, script: str = '#!/bin/sh\nexit 0\n') -> Path:
    """Local to this file on purpose. `tests/conftest.py` and `tests/e2e/conftest.py`
    are both the module `conftest` to an importer, so a `from conftest import ...`
    resolves to whichever one the tool looked at first — which typechecks as the
    wrong file and would run as the wrong one from another working directory.
    Fixtures are injected and have no such problem; a plain helper is copied."""
    target = directory / name
    target.write_text(script)
    target.chmod(target.stat().st_mode | stat.S_IEXEC)
    return target


@pytest.fixture
def uv_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A scratch `$UV_TOOL_DIR`, which is the knob uv itself honours.

    Here rather than beside the packages tests, because `tests/matrix/` builds the
    same directory as part of a whole synthetic machine and a fixture defined in
    one test package is invisible to another.
    """
    directory = tmp_path / 'uv-tools'
    directory.mkdir()
    monkeypatch.setenv('UV_TOOL_DIR', str(directory))
    return directory


@pytest.fixture
def release_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`$XDG_CACHE_HOME` is the real knob, so pointing it here patches nothing.

    Here for the reason `uv_tools` is, and it is the only upstream a test without
    a network may read: `matrix.harness.cached` writes it and
    `releases.cache_file()` re-reads the variable on every call.
    """
    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path / 'cache'))
    return tmp_path / 'cache' / 'dotfiles' / 'releases.json'


@pytest.fixture
def granted(fake_bin: Path) -> Privilege:
    """A `Privilege` whose sudo runs the command instead of dropping it.

    A fake that logged and exited 0 would let every write test pass without a file
    ever being written, which is the one result they must not be able to produce.

    Nothing calls `authorize` any more: root is acquired at the first write, so the
    fake answers `sudo -v` and then execs whatever it was handed.
    """
    _executable(fake_bin, 'sudo', '#!/bin/sh\n[ "$1" = "-v" ] && exit 0\nexec "$@"\n')
    return Privilege()
