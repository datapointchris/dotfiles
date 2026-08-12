"""Shared test fixtures.

Modules under `install/` are importable by name — `pythonpath` in pyproject.toml
names their directories. Apps are not: a command is `aws-profiles`, not
`aws_profiles.py`, and a filename with a hyphen and no extension is not a module
name. `load_app` loads one by path so its functions can still be called directly
rather than only exercised through a subprocess.
"""

import importlib.machinery
import importlib.util
import os
import shutil
import stat
import sys
from pathlib import Path
from types import ModuleType

import levels
import pytest

from dotfiles.privilege import Privilege

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
            if argv[:2] in INSTALLING:
                raise AssertionError(f'{" ".join(argv)} would install on this machine — stub the provider, or mark the test e2e')
            return original(command, *args, **kwargs)

        return guarded

    monkeypatch.setattr(subprocess, 'run', refuse_installs(subprocess.run))
    monkeypatch.setattr(subprocess, 'Popen', refuse_installs(subprocess.Popen))


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
    """
    from dotfiles import paths

    def artefacts() -> set[str]:
        return {path.name for path in paths.RUNS_DIR.iterdir()} if paths.RUNS_DIR.is_dir() else set()

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
    loader.exec_module(module)
    return module


@pytest.fixture(scope='session')
def aws_profiles():
    return load_app('_aws-profiles')


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
    """
    directory = tmp_path / 'bin'
    directory.mkdir()
    monkeypatch.setenv('PATH', f'{directory}{os.pathsep}/usr/bin{os.pathsep}/bin')
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
def granted(fake_bin: Path) -> Privilege:
    """A `Privilege` whose sudo runs the command instead of dropping it.

    A fake that logged and exited 0 would let every write test pass without a file
    ever being written, which is the one result they must not be able to produce.

    Nothing calls `authorize` any more: root is acquired at the first write, so the
    fake answers `sudo -v` and then execs whatever it was handed.
    """
    _executable(fake_bin, 'sudo', '#!/bin/sh\n[ "$1" = "-v" ] && exit 0\nexec "$@"\n')
    return Privilege()
