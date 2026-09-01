"""One synthetic machine, built from files, and the front door driven against it.

Every knob here is one the code already honours. The declaration is a real
`packages.yml` and a real manifest on disk; the installed tools are real
executables on a real `PATH`; the upstream versions are a real release cache under
a real `$XDG_CACHE_HOME`; the uv tools are real receipts under a real
`$UV_TOOL_DIR`. Nothing in `src/dotfiles/` is stubbed, so what a matrix test
measures is what the CLI does.

**Two seams are read once, at import, and so cannot be reached by setting the
variable alone.** `paths` derives eleven constants from `$DOTFILES_DIR` and the
XDG variables at module scope, and `Session.repo`'s default is one of them, frozen
into the generated `__init__` when the dataclass was created. `rebind` runs the
module's own derivation again and rewrites that captured default — it invents no
value, and the environment variable is still what decides. Without it every matrix
test would measure `~/dotfiles`'s own declaration, which is the machine-independence
the suite exists to keep.

**In process rather than in a subprocess**, and the guards are the whole reason. A
`python -m dotfiles.main` would need no rebinding at all — but
`no_installing_on_this_machine` guards `subprocess` inside this interpreter, and so
does the network guard in `conftest.py`. A CLI run outside it can install and can
reach GitHub, with nothing able to say it did.
"""

from __future__ import annotations

import dataclasses as dc
import datetime as dt
import inspect
import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from dotfiles import paths
from dotfiles import releases
from dotfiles.providers import bundle
from dotfiles.session import Session


class ReachedTheNetwork(BaseException):
    """Raised where a request was attempted, and deliberately not an `Exception`.

    `engine._measure` wraps every resource in `except Exception` and turns what it
    raised into a `Refusal`, so the walk survives one checker crashing. A guard
    raised as an `AssertionError` is caught by exactly that: the request is still
    refused, and the run reports `packages could not be examined` and exits 3 —
    a plausible answer, so the test passes its exit-code assertion and nobody
    learns the network was reached. `plan --refresh` is the verb that reaches it.

    Same reasoning as `WouldInstall` in `tests/conftest.py`, and the same reason
    `pytest.fail` raises one.
    """


MACHINE = 'box'
"""The manifest every synthetic repo carries, unless a test writes another.

Named once because it is three things at the same address — the file
`install/manifests/box.yml`, the `machine:` key inside it, and the `$MACHINE` the
sandbox exports so a leaf resolves without `--machine`.
"""

STAGED_BUNDLE = 'dotfiles-offline-v20260814T190203Z-box-linux-x86_64'
"""What a sandbox's one staged bundle is called.

Stamped and named the way `create_bundle.bundle_name` names one, so a test whose
subject is the stack orders a second bundle against it by writing an earlier or
later stamp rather than by inventing a naming scheme of its own.
"""

MINIMAL_MANIFEST: dict[str, Any] = {'machine': MACHINE, 'platform': 'linux'}
"""A machine that declares nothing, on the one platform every CI runner can be.

`linux` is apt on a native host with no display stack, per
`coordinates.PLATFORM_BUNDLES`. The package manager matters because `system`
queries it; the sandbox shadows the binary, so the answer is the same on Arch, on
macOS and in a container.
"""

LAZYGIT: dict[str, Any] = {'github_releases': [{'name': 'lazygit', 'repo': 'jesseduffield/lazygit'}]}
"""One release binary, which is the smallest declaration with an upstream version.

Here rather than in each module because a `--owner` row, a currency row and an
asset probe all need the *same* entry to be comparable across modules — the owner
is `jesseduffield`, and a module inventing its own repo silently stops testing the
same thing its neighbour does.
"""

DECLARES_LAZYGIT: dict[str, Any] = {**MINIMAL_MANIFEST, 'github_releases': ['lazygit']}
"""The manifest subscribing to it. Separate because declaring and subscribing are
the two halves a matrix row varies independently."""

SYNCER: dict[str, Any] = {'git_uv_tools': [{'name': 'syncer', 'repo': 'https://github.com/datapointchris/syncer.git'}]}
"""One tool with an upstream version that no bundle is ever built to carry.

The counterpart to `LAZYGIT` across the `providers.bundle.bundlable` line: both have
a repo to ask about, and only this one is unanswerable when the upstream in hand is
a staged tarball."""

DECLARES_SYNCER: dict[str, Any] = {**MINIMAL_MANIFEST, 'git_uv_tools': ['syncer']}

VENDOR_INSTALLER: dict[str, Any] = {
    'custom_installers': [{'name': 'terraform-ls', 'repo': 'hashicorp/terraform-ls', 'description': 'a vendor installer'}]
}
"""The kind that answers `providers.bundle.bundlable` per entry rather than per section.

A `custom_installers` entry is staged only where it declares
`bundle_install_script`, so a machine can hold five of them in one bundle and one
outside it. A sentence blaming the section is false on that machine, which is why
this fixture declares no script and `LAZYGIT` cannot stand in for it."""

DECLARES_VENDOR_INSTALLER: dict[str, Any] = {**MINIMAL_MANIFEST, 'custom_installers': ['terraform-ls']}


# ─────────────────────────────────────────────────────────────────────────────
# Files on disk: the declaration, an installed tool, an upstream release
# ─────────────────────────────────────────────────────────────────────────────


def executable(directory: Path, name: str, script: str = '#!/bin/sh\nexit 0\n') -> Path:
    """A binary that exists and answers. The evidence `PATH` carries."""
    target = directory / name
    target.write_text(script)
    target.chmod(target.stat().st_mode | stat.S_IEXEC)
    return target


def reporting(directory: Path, name: str, version: str) -> Path:
    """An installed tool at a chosen version, answering the probe the way a real one does."""
    return executable(directory, name, f'#!/bin/sh\nprintf "%s\\n" "{version}"\n')


def receipt(directory: Path, name: str, requirement: str) -> None:
    """A uv tool directory with the receipt `uv tool install` writes beside it."""
    (directory / name).mkdir(exist_ok=True)
    (directory / name / 'uv-receipt.toml').write_text(f'[tool]\nrequirements = [{requirement}]\n')


def cached(path: Path, entries: dict[str, str], age: dt.timedelta = dt.timedelta(0)) -> None:
    """An upstream release at a chosen version, written where a refresh would leave it.

    The cache is the only upstream a test may have, and reaching it is asked for
    rather than assumed: `check` reads it, and `plan` reads it under `--cached`. A
    bare `plan` measures upstream and is guarded by `no_network_from_the_matrix`,
    so a test wanting these versions says which. `age` past `releases.TTL` is how a
    test asks for an answer the code must refuse to trust.
    """
    checked = dt.datetime.now(dt.UTC) - age
    releases.save({key: releases.Cached(version, checked) for key, version in entries.items()}, path)


def bundle_manifest(
    directory: Path,
    rows: dict[str, str],
    category: str = 'binary',
    *,
    sparse: bool = False,
    current: dict[str, str] | None = None,
    built_from: str = '',
    created: str = '2026-08-14T19:02:03Z',
) -> Path:
    """The two metadata files a bundle carries, written the way `Bundle` writes them.

    One writer for every caller, because both formats are contracts with
    `offline_bundle` rather than conveniences: the manifest reader splits on `|`
    and takes four fields, so a second spelling drifts from the parser silently
    and the test that would catch it is the one using the other spelling.

    The keyword arguments are the shapes a bundle comes in, all of them reachable
    from one fixture — standards/testing.md § "A fixture with one shape tests one
    shape". A sparse bundle and a full one differ only in `bundle.json`, so a
    fixture that could write only the second would leave every sparse branch with
    no test able to reach it.
    """
    directory.mkdir(parents=True, exist_ok=True)
    lines = [f'{category}|{name}|{version}|{name}' for name, version in rows.items()]
    manifest = directory / bundle.MANIFEST
    manifest.write_text('# Format: category|name|version|filename\n' + '\n'.join(lines) + '\n')

    described = bundle.Description(
        created=created,
        machine='box',
        platform='linux/x86_64',
        completeness=bundle.Completeness.SPARSE if sparse else bundle.Completeness.FULL,
        built_from=built_from,
        current=current or {},
    )
    (directory / bundle.DOCUMENT).write_text(json.dumps(described.as_dict(), indent=2) + '\n')
    return manifest


def staged_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    rows: dict[str, str],
    category: str = 'binary',
    *,
    name: str = STAGED_BUNDLE,
    **described: Any,
) -> Path:
    """One staged bundle inside a staging directory, for a test with no sandbox.

    `$DOTFILES_BUNDLE` is what `paths.staging_dir` reads on every call, so setting
    it here is obeyed by a fixture running long after import — which is the whole
    reason those paths are functions rather than constants.

    `name` is a parameter so a test can stage two and control which is newer:
    `providers.staged_bundles` ranks on the directory name, and a stack whose
    order a test cannot set is a stack with no test for the falling-through half.
    """
    staging = tmp_path / 'staged'
    unpacked = staging / name
    bundle_manifest(unpacked, rows, category, **described)
    monkeypatch.setenv('DOTFILES_BUNDLE', str(staging))
    return unpacked


def git_checkout(path: Path, files: dict[str, str] | None = None, branch: str = 'trunk', subject: str = 'first commit') -> Path:
    """A real repository at `path`, with one commit on a named branch.

    Real git rather than a fabricated `.git`, because what reads it is real git —
    `checkout.read`, and the clone providers, which a directory shaped like a
    repository does not satisfy.

    The branch is named rather than defaulted: git's own default is `master` on one
    machine and `main` on the next, so an unnamed branch is a fact about the
    developer's `init.defaultBranch` leaking into an assertion. The identity is on
    the command line rather than from config, so this works before a test has
    written one and does not change meaning when a test rewrites it.
    """
    path.mkdir(parents=True, exist_ok=True)
    for name, body in (files or {}).items():
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        (path / name).write_text(body)
    identity = ('-c', 'user.email=box@example.invalid', '-c', 'user.name=Synthetic Box')
    for argv in (['init', '-q', '-b', branch], ['add', '-A'], [*identity, 'commit', '-q', '--allow-empty', '-m', subject]):
        subprocess.run(['git', '-C', str(path), *argv], check=True, capture_output=True)
    return path


def write_declaration(
    repo: Path,
    packages: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    flags: dict[str, Any] | None = None,
    machine: str = MACHINE,
) -> Path:
    """The three files every resolution reads, and the pyproject the symlink pass wants.

    Whole files rather than a merge into what is already there: a declaration is
    the input under test, and a test that appended to one could not express "this
    machine declares nothing".
    """
    (repo / 'install' / 'manifests').mkdir(parents=True, exist_ok=True)
    (repo / 'install' / 'packages.yml').write_text(yaml.safe_dump(packages or {}, sort_keys=False))
    (repo / 'install' / 'flags.yml').write_text(yaml.safe_dump(flags or {}, sort_keys=False))
    (repo / 'install' / 'manifests' / f'{machine}.yml').write_text(yaml.safe_dump(manifest or MINIMAL_MANIFEST, sort_keys=False))
    # `symlinks.core.console_script_names` reads it to learn which names
    # `[project.scripts]` has already claimed in ~/.local/bin. Absent, it answers
    # the empty set — which is right, and writing one makes that a measured answer
    # rather than a missing file.
    pyproject = repo / 'pyproject.toml'
    if not pyproject.exists():
        pyproject.write_text('[project]\nname = "synthetic"\nversion = "0.0.0"\n')
    return repo


def session(tmp_path: Path, packages_yml: dict[str, Any], manifest: dict[str, Any]) -> Session:
    """A Session over a synthetic declaration, for a test that drives a resource directly.

    Deliberately not the sandbox: this builds no home, sets no variable and rebinds
    nothing, so a resource test keeps measuring exactly the two files it wrote. The
    sandbox is for tests that go through the CLI, which resolves its own Session
    and cannot be handed one.
    """
    repo = tmp_path / 'repo'
    write_declaration(repo, packages_yml, manifest)
    home = tmp_path / 'home'
    home.mkdir(exist_ok=True)
    return Session(machine_name=manifest.get('machine', MACHINE), repo=repo, home=home)


# ─────────────────────────────────────────────────────────────────────────────
# The sandbox: one machine's worth of directories, and the variables naming them
# ─────────────────────────────────────────────────────────────────────────────


@dc.dataclass(frozen=True)
class Sandbox:
    """Where this test's machine lives. Every path is under one tmp root."""

    root: Path
    home: Path
    repo: Path
    bin: Path
    cache: Path
    config: Path
    data: Path
    state: Path
    runs: Path
    uv_tools: Path

    bundle: Path
    """One staged bundle, inside the staging directory that holds every one.

    A bundle rather than the directory they sit in, because that is what a test
    writes files into. `providers.locate` reads across the whole staging
    directory, so a test staging a second bundle beside this one exercises the
    stack — `staging` is that parent.
    """

    machine: str = MACHINE

    @property
    def user_bin(self) -> Path:
        """`~/.local/bin` under this sandbox, which is where the providers install.

        Derived from `home` rather than declared beside `bin`, because it is not a
        directory this harness chose: `providers.bin_dir` decides it, and a second
        spelling here would be free to point somewhere the code never writes.

        Apart from `bin`, and the two are different questions. `bin` is a directory
        this harness puts in *front* of the machine so a shadow answers instead of
        whatever is really installed. This is where the machine's own tools live, so
        a release binary placed here is one the release provider is entitled to
        claim — which is the whole of what `evidence.by_release` measures.
        """
        return self.home / '.local' / 'bin'

    @property
    def staging(self) -> Path:
        """Where staged bundles live, which is what `$DOTFILES_BUNDLE` names."""
        return self.bundle.parent

    @property
    def release_cache(self) -> Path:
        """Where `releases.cache_file()` resolves to under this sandbox."""
        return self.cache / 'dotfiles' / 'releases.json'

    @property
    def env_file(self) -> Path:
        return self.home / '.env'

    @property
    def status_file(self) -> Path:
        return self.state / 'dotfiles' / f'status-{paths.MACHINE_ID}.json'

    @property
    def run_files(self) -> list[Path]:
        """Everything the runs directory holds, records and event logs alike.

        The one to assert against for *nothing was written*, which is a stronger
        claim than *no record was filed*: `sinks.open_log` creates the `.jsonl`
        before anything fills it, and an empty one left behind is the exact leak
        `no_run_artefacts_on_this_machine` counts in the real directory.
        """
        return sorted(self.runs.iterdir())

    @property
    def filed_records(self) -> list[Path]:
        """The run records filed here, oldest last. The `.json` only.

        A run writes two files under one stem — the record and the `.jsonl` event
        log beside it — so counting the directory answers two per run and reads as
        a double-file bug.
        """
        return [path for path in self.run_files if path.suffix == '.json']

    @property
    def latest_record(self) -> dict[str, Any]:
        """The record the verb just filed, read back off disk.

        Off disk rather than out of `--json`, because only `apply` emits a record
        on stdout and the claim it usually serves — that every verb records what it
        was asked to do — has to hold for the two that emit the interchange
        document instead.
        """
        return json.loads(self.filed_records[-1].read_text())

    def declare(
        self,
        packages: dict[str, Any] | None = None,
        manifest: dict[str, Any] | None = None,
        flags: dict[str, Any] | None = None,
        machine: str | None = None,
    ) -> Path:
        """Replace this machine's declaration, and settle again. Returns the repo root.

        Settling afterwards rather than leaving it to the caller, because `~/.env`
        is *rendered from* the manifest — a declaration written after the file was
        settled leaves it stale, and `env` would report drift no test asked for.
        """
        written = write_declaration(self.repo, packages, manifest, flags, machine or self.machine)
        self.settle()
        return written

    def settle(self) -> None:
        """Bring the three things no declaration covers into line, so drift is the
        test's own.

        Every one of them is a real finding on a machine that has just been built,
        and every one of them would otherwise be in *every* matrix row — a baseline
        of three findings makes `exit 0` unreachable and every other assertion read
        as though the flag under test caused them.

        - **uv** is ungated and planned on every machine, because everything
          installed later resolves through it. Absent, `toolchains` drifts.
        - **`~/.env`** is what `env` exists to write, so an unwritten one is drift
          by construction. Written through `envfile.write`, the function `env apply`
          calls, so this cannot render it differently from the tool.
        - **a git identity** is `BY_HAND` drift, which makes it an *Issue* under
          `check` rather than drift under `plan` — the one baseline finding that
          moves an exit code to 3.

        A test that wants one of them back removes it: `sandbox.env_file.unlink()`,
        `(sandbox.user_bin / 'uv').unlink()`.

        Silent when the declaration will not load. A matrix test writing a broken
        manifest on purpose is measuring the refusal, and a settle that raised
        would take the test out before the command ran.
        """
        from dotfiles import envfile
        from dotfiles import machine as machines

        self.installed('uv', 'uv 0.9.9')
        entry = self.config / 'git' / 'config'
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_text('[user]\n\tname = Synthetic Box\n\temail = box@example.invalid\n')

        try:
            declared = machines.load(self.machine, self.repo)
        except machines.MachineError:
            return
        envfile.write(self.env_file, declared)

    def shadow(self, name: str, script: str = '#!/bin/sh\nexit 0\n') -> Path:
        """Put a binary in front of whatever the real machine has at that name."""
        return executable(self.bin, name, script)

    def installed(self, name: str, version: str | None = None) -> Path:
        """A declared tool this machine has, reporting `version` when asked.

        In `~/.local/bin` rather than the shadow directory, because that is where
        every provider that installs a binary puts one and a release entry is
        measured at that path rather than on `PATH` — a copy anywhere else is what
        `evidence.by_release` exists to report as *not this repo's*. The other
        providers are answered by `PATH`, which reaches here as well, so one
        placement serves both.
        """
        return reporting(self.user_bin, name, version) if version is not None else executable(self.user_bin, name)

    def elsewhere(self, name: str, version: str | None = None) -> Path:
        """The same tool, installed by something that is not this repo.

        A machine whose Homebrew or pacman put a binary on `PATH` at a path no
        provider here chose. The shadow directory is exactly that: on `PATH`, ahead
        of everything, and not `~/.local/bin`.
        """
        return reporting(self.bin, name, version) if version is not None else executable(self.bin, name)

    def uv_installed(self, name: str, pin: str | None = None, repo: str | None = None) -> None:
        """A uv tool directory, pinned to `pin` when a git install recorded one."""
        source = repo or f'https://github.com/datapointchris/{name}.git'
        requirement = f'{{ name = "{name}", git = "{source}{f"?rev={pin}" if pin else ""}" }}'
        receipt(self.uv_tools, name, requirement)

    def upstream(self, entries: dict[str, str], age: dt.timedelta = dt.timedelta(0)) -> Path:
        """The newest release each repo has published, as a refresh would have left it."""
        cached(self.release_cache, entries, age)
        return self.release_cache

    def stage_bundle(self, rows: dict[str, str], category: str = 'binary', *, name: str = '', **described: Any) -> Path:
        """The bundle an offline run reads its upstream versions out of.

        `name` stages a second one beside the first, which is how a test reaches
        the stack: `providers.staged_bundles` ranks on the directory name, so the
        caller decides which of the two wins.
        """
        staged = self.staging / name if name else self.bundle
        bundle_manifest(staged, rows, category, **described)
        return staged


REFUSED = '#!/bin/sh\nexit 1\n'
"""A shadow that is present and answers no. What `gh` and `curl` get by default.

Absent would be the other option and is worse: `shutil.which` then falls through
to the real one behind `/usr/bin`, so a machine with `gh` logged in reports
credentials and a machine without does not — the exact inversion `fake_bin`'s
shadowing exists to prevent.
"""

PACKAGE_MANAGERS = ('apt', 'apt-get', 'apt-cache', 'dpkg', 'pacman', 'brew', 'flatpak', 'snap', 'mas')
"""Every OS package manager, shadowed as REFUSED so the host's distro cannot answer.

The same argument as `gh` and `curl` one docstring up, and it was left out. The
`system` resource carries one row per package manager, so whether that row is
measurable depended on which manager the box running the suite happens to have.
On Arch `apt` is absent and the row is UNMEASURED; on the Ubuntu runner `apt` is
real, the row is measurable, and it reports upgrades — so `pending` came back one
higher and ten cases asserting an exact count failed in CI and passed on every
desk.

REFUSED rather than ANSWERS, measured both ways: a present-but-failing manager
gives `pending=2 unmeasured=1`, identical to an absent one, so every existing
assertion holds unchanged. Shadowing them as answering would have moved the row
from UNMEASURED to MATCHED and rewritten assertions that are not wrong.

A test wanting a manager that answers shadows it itself, which is the same
override `dpkg-query` already uses.
"""

ANSWERS = '#!/bin/sh\nexit 0\n'
"""A shadow that is present and answers yes, and `shadow`'s own default.

Named because a row in a table reads as a state — `('systemctl', ANSWERS)` — where
the literal reads as a shell script the reader has to parse before seeing which
of the two it is.
"""


def unwrapped(text: str) -> str:
    """Console output with Rich's wrapping and its column padding collapsed.

    Every row is rendered into a fixed-width console, so a sentence long enough to
    wrap carries a newline inside itself and no substring assertion against it
    holds. The width is the runner's rather than the code's, which makes an
    un-normalised assertion one that passes in a wide terminal and fails in CI.

    It cannot rejoin a *word* Rich broke, and a long path does get broken
    mid-token. `a_console_wide_enough_to_read` in the conftest is what prevents
    that; this is for the padding and the soft wraps that survive it.
    """
    return ' '.join(text.split())


def build(root: Path, monkeypatch: pytest.MonkeyPatch) -> Sandbox:
    """One machine's directories, the variables naming them, and a declaration.

    Ordered: make the directories, name them, write the declaration, then rebind.
    The rebinding reads the variables, so it has to come last.
    """
    box = Sandbox(
        root=root,
        home=root / 'home',
        repo=root / 'repo',
        bin=root / 'bin',
        cache=root / 'cache',
        config=root / 'config',
        data=root / 'data',
        state=root / 'state',
        runs=root / 'state' / 'dotfiles' / 'runs',
        uv_tools=root / 'uv-tools',
        bundle=root / 'staged' / STAGED_BUNDLE,
    )
    # `bundle` is deliberately absent from this list. `_stage_bundle` treats an
    # existing directory as an already-staged bundle, so creating it would make
    # `--offline` skip the staging path a matrix row is there to measure.
    for directory in (box.home, box.repo, box.bin, box.user_bin, box.cache, box.config, box.data, box.state, box.runs, box.uv_tools):
        directory.mkdir(parents=True, exist_ok=True)

    # `offline_bundle.newest` searches the working directory before `$HOME`, and
    # under pytest that is the checkout — so a tarball left beside the repo would
    # be staged into a test that never asked for one.
    monkeypatch.chdir(box.root)
    _name_the_directories(box, monkeypatch)
    _silence_the_ambient_environment(monkeypatch)
    write_declaration(box.repo, machine=box.machine)
    rebind(box, monkeypatch)

    for refused in ('gh', 'curl', *PACKAGE_MANAGERS):
        box.shadow(refused, REFUSED)
    box.settle()
    return box


def _name_the_directories(box: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every variable the package resolves a path through, pointed at this sandbox.

    `PATH` keeps `/usr/bin:/bin` behind the sandbox bin, for the reason
    `tests/conftest.py`'s `fake_bin` gives: without them `git`, `bash` and `sh`
    raise FileNotFoundError and the harness cannot run its own helpers.

    `~/.local/bin` sits between them, in the order a real machine has: shadows
    ahead of everything so a fake package manager answers, then the tools this
    machine installed, then the system.
    """
    monkeypatch.setenv('HOME', str(box.home))
    monkeypatch.setenv('XDG_CACHE_HOME', str(box.cache))
    monkeypatch.setenv('XDG_CONFIG_HOME', str(box.config))
    monkeypatch.setenv('XDG_DATA_HOME', str(box.data))
    monkeypatch.setenv('XDG_STATE_HOME', str(box.state))
    monkeypatch.setenv('UV_TOOL_DIR', str(box.uv_tools))
    monkeypatch.setenv('DOTFILES_DIR', str(box.repo))
    monkeypatch.setenv('DOTFILES_BUNDLE', str(box.staging))
    monkeypatch.setenv('MACHINE', box.machine)
    monkeypatch.setenv('PATH', f'{box.bin}{os.pathsep}{box.user_bin}{os.pathsep}/usr/bin{os.pathsep}/bin')


def _silence_the_ambient_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drop what the developer's shell exports and a CI runner does not.

    `$GITHUB_TOKEN` alone flips a private-repo entry from `BY_HAND` to `AUTOMATIC`,
    so the same test passes at a desk and fails on the runner. `$LOG_LEVEL` moves the console threshold that `-v` and `-q` are being
    asserted against, and the `DOTFILES_*` settings twins answer `config show`
    before the config file can. `$ATUIN_CONFIG_DIR` reaches past `$XDG_CONFIG_HOME`
    to the desk's own atuin config, whose `auto_sync` decides whether a login is
    asked for at all.
    """
    for variable in ('GITHUB_TOKEN', 'LOG_LEVEL', 'FORCE_COLOR', 'CLICOLOR_FORCE', 'ATUIN_CONFIG_DIR'):
        monkeypatch.delenv(variable, raising=False)
    for variable in list(os.environ):
        if variable.startswith('DOTFILES_') and variable not in {'DOTFILES_DIR', 'DOTFILES_BUNDLE'}:
            monkeypatch.delenv(variable, raising=False)
    # git reads /etc/gitconfig before anything under $HOME, so a machine with a
    # system-wide `user.email` answers `identity check` differently from one
    # without. $HOME already redirects the other two rungs.
    monkeypatch.setenv('GIT_CONFIG_NOSYSTEM', '1')


# ─────────────────────────────────────────────────────────────────────────────
# Rebinding what was derived at import
# ─────────────────────────────────────────────────────────────────────────────


def rebind(box: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    """Re-run the derivations that already happened, now that the variables say this.

    Nothing here invents a value. `paths` is asked for its own answers a second
    time — `_repo_root()`, `xdg_home()` and `cache_home()` are the very calls the
    module body makes — so `$DOTFILES_DIR` and the XDG variables stay the thing
    that decides, and a change to how a path is derived reaches the sandbox with no
    edit here.

    The two that are not module constants are captured *function defaults*,
    evaluated when the function object was created and unreachable through the
    module afterwards. `Session.repo` is the load-bearing one: the CLI builds its
    own Session, so without this every leaf would read `~/dotfiles`'s declaration
    however the sandbox is configured.
    """
    from dotfiles import checkout
    from dotfiles.symlinks import core

    repo = paths._repo_root()  # noqa: SLF001 — the module's own derivation, re-run rather than reimplemented
    state = paths.xdg_home('XDG_STATE_HOME', '.local/state') / 'dotfiles'

    derived = {
        'REPO_ROOT': repo,
        'PYPROJECT_FILE': repo / 'pyproject.toml',
        'INSTALL_DIR': repo / 'install',
        'PACKAGES_FILE': repo / 'install' / 'packages.yml',
        'MANIFESTS_DIR': repo / 'install' / 'manifests',
        'FLAGS_FILE': repo / 'install' / 'flags.yml',
        'STATE_HOME': state,
        'RUNS_DIR': state / 'runs',
        'LATEST_RUN': state / f'latest-{paths.MACHINE_ID}',
        'STATUS_FILE': state / f'status-{paths.MACHINE_ID}.json',
    }
    for name, value in derived.items():
        monkeypatch.setattr(paths, name, value)

    monkeypatch.setattr(core, 'DOTFILES_DIR', repo)
    monkeypatch.setattr(core, 'TARGET_DIR', box.home.resolve())

    rebind_default(monkeypatch, Session.__init__, 'repo', repo)
    for reader in (checkout.read, checkout.stray_branch, checkout.fetch):
        rebind_default(monkeypatch, reader, 'repo', repo)


def rebind_default(monkeypatch: pytest.MonkeyPatch, function: Any, parameter: str, value: Any) -> None:
    """Replace one captured default in an already-created function.

    A default is evaluated once, when the `def` runs, and stored on the function
    object — so `paths.REPO_ROOT = x` after the fact changes nothing about a
    signature that read it at import. Setting the class attribute does not either:
    a dataclass bakes the value into the generated `__init__`'s defaults tuple, and
    `Session(machine_name='box').repo` still answers the old path.

    The position is computed from the signature rather than written down, so a
    parameter added before this one cannot silently move the value onto its
    neighbour.
    """
    spec = inspect.getfullargspec(function)
    defaults = list(spec.defaults or ())
    offset = len(spec.args) - len(defaults)
    index = spec.args.index(parameter) - offset
    if index < 0:
        raise ValueError(f'{function.__qualname__} takes {parameter} without a default')
    defaults[index] = value
    monkeypatch.setattr(function, '__defaults__', tuple(defaults))


# ─────────────────────────────────────────────────────────────────────────────
# The front door
# ─────────────────────────────────────────────────────────────────────────────


@dc.dataclass(frozen=True)
class Invocation:
    """One CLI run: what it answered, on which stream, and with what status."""

    argv: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    document: Any | None = None
    """Whatever `--json` put on stdout, parsed. None when the run emitted none.

    A field rather than a call at each assertion, because the contract being
    measured is that a `--json` run puts a parseable document on *stdout* — so
    parsing it is part of what the invocation records, not a convenience.
    """

    @property
    def output(self) -> str:
        """Both streams, for a test asserting a message appeared without caring where.

        Never use it to assert a message is on stdout. The split is the machine
        contract — one stray diagnostic there turns a `--json` parse into a syntax
        error — and this property cannot tell the two apart.
        """
        return self.stdout + self.stderr


def addresses(ran: Invocation) -> list[str]:
    """Which resources a read verb's document says it walked, in walk order."""
    return [found['address'] for found in _rows(ran)]


def resource(ran: Invocation, address: str) -> dict[str, Any]:
    """One resource's row out of a read verb's document, by name.

    Here rather than in one module because every read door emits the same
    document now — `dotfiles plan --json` and `dotfiles system plan --json` differ
    in what they walked and not in what they answer with. A per-module accessor
    would be the same lookup written nine times, and the module that wrote it
    slightly differently is the one whose assertion stops meaning what it says.

    Raises rather than answering `None` for an address the document does not hold.
    A test asking about a resource the run never walked is asserting against a
    machine it did not build, and `None['pending']` names the wrong thing.
    """
    rows = {found['address']: found for found in _rows(ran)}
    if address not in rows:
        raise AssertionError(f'{" ".join(ran.argv)} walked {sorted(rows)}, which does not include {address}')
    return rows[address]


def _rows(ran: Invocation) -> list[dict[str, Any]]:
    """The resource rows of a read verb's document, or a failure naming the run.

    `document` is None wherever stdout carried none, so indexing it directly
    raises `'NoneType' object is not subscriptable` — which names neither the
    command nor the missing `--json`. Same argument `resource` makes above about
    an address the document does not hold, one step earlier: the run that emitted
    no document at all is the commoner mistake of the two.
    """
    if ran.document is None:
        raise AssertionError(f'{" ".join(ran.argv)} put no document on stdout')
    return ran.document['resources']


def invoke(*argv: str, catch_exceptions: bool = False) -> Invocation:
    """Run one command against whatever the sandbox has built, and record all of it.

    `catch_exceptions=False` by default, so an unhandled exception reaches the test
    as a traceback rather than as a plausible exit code. `check` cannot exit 1 by
    design and does exit 1 on a traceback, which is exactly the confusion this
    prevents — a test wanting to observe that passes `catch_exceptions=True`.

    A fresh `CliRunner` per call: `typer.Typer` builds its Click command lazily and
    a shared runner is state a test can leave behind.
    """
    from dotfiles.main import app

    result = CliRunner().invoke(app, list(argv), catch_exceptions=catch_exceptions)
    return Invocation(
        argv=argv,
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        document=_parsed(result.stdout),
    )


def _parsed(stdout: str) -> Any | None:
    """The document on stdout, or None when stdout is not one.

    Tested rather than gated on `--json` being in the argv: `repo path` and
    `report path` print a bare line, and a leaf that emitted a document without
    being asked is a finding rather than something to hide.
    """
    text = stdout.strip()
    if not text or text[0] not in '[{':
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
