"""Installing a Python tool with uv, the pin that keeps its updater alive, and
the lock that holds its dependencies.

The PyPI half has one decision in it and the git half has all of them: what gets
handed to uv, what happens when the repo publishes nothing to pin to, and what
its lock at that revision holds the install to.

Resolving a tag through `github_release.latest_version` and cloning the
revision through `effects.run` both leave the machine. The last section drives real git and real uv against a
repo and an index this file builds, because the stubs above prove the argv and
only uv can say what that argv installs.
"""

from __future__ import annotations

import base64
import hashlib
import os
import subprocess
import zipfile
from pathlib import Path

import pytest

from dotfiles import catalog
from dotfiles import github_release
from dotfiles import uv_lock
from dotfiles.providers import Kind
from dotfiles.providers import uvtool

RUFF = catalog.UvTool.from_mapping({'name': 'ruff'})
SYNCER = catalog.GitUvTool.from_mapping({'name': 'syncer', 'repo': 'https://github.com/datapointchris/syncer.git'})
KEYMAP = catalog.GitUvTool.from_mapping(
    {'name': 'keymap-align', 'repo': 'https://github.com/datapointchris/keymap-align.git', 'tracks_branch': True}
)


@pytest.fixture
def uv(upstream):
    """`uv tool install`, answering however this test says it went."""
    return upstream


@pytest.fixture
def released(monkeypatch):
    """What the releases API answers, without asking it."""

    def publish(tag: str | None) -> list[str]:
        asked: list[str] = []

        def latest(repo: str, tag_prefix: str = '') -> str | None:
            asked.append(repo)
            return tag

        monkeypatch.setattr(github_release, 'latest_version', latest)
        return asked

    return publish


@pytest.fixture
def locked(monkeypatch):
    """What the lock at the cloned revision pins, without a clone to read it from.

    Without this the recorder's clone succeeds and writes nothing, so the
    revision reads as carrying no lock at all.
    """

    def pin(pins: uv_lock.Pins | Exception) -> None:
        def read(project: Path) -> uv_lock.Pins:
            if isinstance(pins, Exception):
                raise pins
            return pins

        monkeypatch.setattr(uv_lock, 'read', read)

    return pin


def installs(reached) -> list[tuple[str, ...]]:
    return [call for call in reached.calls if call[:3] == ('uv', 'tool', 'install')]


def clones(reached) -> list[tuple[str, ...]]:
    return [call for call in reached.calls if call[:2] == ('git', 'clone')]


# ─────────────────────────────────────────────────────────────────────────────
# From PyPI
# ─────────────────────────────────────────────────────────────────────────────


def test_a_pypi_tool_is_installed_by_name(uv) -> None:
    reached = uv()

    result = uvtool.install(RUFF, offline=False)

    assert result.ok
    assert reached.calls == [('uv', 'tool', 'install', 'ruff')]


def test_a_repair_that_would_not_move_the_requirement_forces_the_install(uv) -> None:
    """`uv tool install ruff` against an installed ruff prints "already installed"
    and exits 0, which this reads as success — so a repair recorded DONE having
    done nothing. That defeats the whole of what `--reinstall` exists for: the
    fault no comparison can see."""
    reached = uv()

    uvtool.install(RUFF, offline=False, again=True)

    assert reached.calls == [('uv', 'tool', 'install', '--reinstall', 'ruff')]


def test_an_ordinary_install_does_not_force_anything(uv) -> None:
    reached = uv()

    uvtool.install(RUFF, offline=False)

    assert '--reinstall' not in reached.calls[0]


def test_a_git_tool_repaired_again_is_forced_at_its_pin(uv, released) -> None:
    """The git half needs it for the case its pin cannot express: measured stale
    while the newest release is the tag it is already pinned to, which leaves the
    requirement unchanged and uv declining to move it forever."""
    released('v6.0.0')
    reached = uv()

    uvtool.install_git(SYNCER, offline=False, again=True)

    assert installs(reached) == [
        ('uv', 'tool', 'install', '--reinstall', 'syncer @ git+https://github.com/datapointchris/syncer.git@v6.0.0')
    ]


def test_a_failure_reports_what_uv_said(uv) -> None:
    uv(reachable=False, said='error: distribution not found for: nosuchtool')

    result = uvtool.install(RUFF, offline=False)

    assert not result.ok
    assert result.kind is Kind.COMMAND_FAILED
    assert 'distribution not found' in result.detail


def test_offline_still_tries_pypi_and_says_there_is_no_fallback(uv) -> None:
    """The bundle stages wheels for this CLI's own closure and nothing else, while
    the machine that installs offline declares six uv tools — so refusing would
    install none of them on the box the offline path exists for."""
    reached = uv(reachable=False, said='error: network unreachable')

    result = uvtool.install(RUFF, offline=True)

    assert reached.calls == [('uv', 'tool', 'install', 'ruff')]
    assert result.kind is Kind.COMMAND_FAILED
    assert 'stages no Python tools' in result.detail


# ─────────────────────────────────────────────────────────────────────────────
# From a git repo, pinned
# ─────────────────────────────────────────────────────────────────────────────


def test_a_git_tool_is_pinned_to_its_newest_release(uv, released) -> None:
    """Unpinned is the degraded state, not the flexible one: pyselfupdate reads
    uv's receipt, treats a requirement with no `rev=` as a dev checkout, and
    refuses to reinstall over it. syncer sat eight releases back that way while
    the update phase called it current."""
    released('v6.0.0')
    reached = uv()

    uvtool.install_git(SYNCER, offline=False)

    assert installs(reached) == [('uv', 'tool', 'install', 'syncer @ git+https://github.com/datapointchris/syncer.git@v6.0.0')]


def test_a_repo_with_no_release_installs_from_the_branch_with_a_warning(uv, released, capsys) -> None:
    """The install still works; it is the tool's own updater that will not, and
    install time is the only moment anyone would notice."""
    released(None)
    reached = uv()

    uvtool.install_git(SYNCER, offline=False)

    assert installs(reached) == [('uv', 'tool', 'install', 'https://github.com/datapointchris/syncer.git')]
    assert 'refuse to run' in capsys.readouterr().err


@pytest.fixture
def unreadable(monkeypatch):
    """`latest_version` refusing, as the two states a provider has to tell apart."""

    def refuse(*, reached: bool) -> None:
        def raising(repo: str, tag_prefix: str = '') -> str:
            raise github_release.Unreadable(f'could not read the releases of {repo}', reached=reached)

        monkeypatch.setattr(github_release, 'latest_version', raising)

    return refuse


def test_an_unreadable_release_api_refuses_rather_than_installing_unpinned(uv, unreadable) -> None:
    """The sibling above is the same fallback taken on purpose, and that is what
    makes this one wrong: nothing afterwards can tell an unpinned install that was
    decided from one that was guessed at while the API was unreachable.

    A rate-limited minute is enough, and the tool it leaves behind has a dead
    `update` until somebody notices it is eight releases back.
    """
    unreadable(reached=True)
    reached = uv()

    result = uvtool.install_git(SYNCER, offline=False)

    assert not result.ok
    assert result.kind is Kind.VERSION_UNRESOLVED
    assert reached.calls == [], 'nothing is handed to uv, pinned or otherwise'


def test_a_service_that_refused_and_a_transport_that_failed_get_different_kinds(uv, unreadable) -> None:
    """A rate limit is waited out and a refused connection is a CA, a proxy or a
    firewall, so `--json` has to separate them.

    Asserted on `kind` and not on `detail`, because the sentence is what the two
    already shared: prose was the only place the split existed, which made every
    reader of this outcome match on English to find out which one happened.
    """
    uv()

    unreadable(reached=True)
    refused = uvtool.install_git(SYNCER, offline=False)
    unreadable(reached=False)
    unreachable = uvtool.install_git(SYNCER, offline=False)

    assert refused.kind is Kind.VERSION_UNRESOLVED
    assert unreachable.kind is Kind.DOWNLOAD_FAILED


def test_an_offline_refusal_names_the_bundle_that_stages_no_python_tools(uv, unreadable, capsys) -> None:
    """Offline reaches this on all ten declared git tools that pin, because
    resolving a tag is the one thing here that leaves the machine.

    `_uv_tool_install` carries this clause for exactly that case and no longer
    runs for those ten, so the refusal that replaced it owes the same sentence —
    otherwise a reader is sent after a network they already know is absent.
    """
    unreadable(reached=False)
    reached = uv()

    result = uvtool.install_git(SYNCER, offline=True)

    assert not result.ok
    assert 'the offline bundle stages no Python tools to fall back on' in result.detail
    assert reached.calls == []


@pytest.mark.parametrize(
    ('repo', 'slug'),
    [
        ('https://github.com/datapointchris/syncer.git', 'datapointchris/syncer'),
        ('https://github.com/datapointchris/syncer', 'datapointchris/syncer'),
        ('https://github.com/datapointchris/syncer/', 'datapointchris/syncer'),
        ('git@github.com:datapointchris/syncer.git', 'datapointchris/syncer'),
    ],
)
def test_every_clone_url_shape_resolves_to_the_same_repo(released, repo: str, slug: str) -> None:
    """A trailing slash passing straight through as part of the slug builds
    `/repos/owner/name//releases/latest`."""
    asked = released('v6.0.0')

    uvtool.latest_release(repo)

    assert asked == [slug]


@pytest.mark.parametrize(
    'repo',
    ['https://gitlab.com/someone/thing.git', 'https://github.com/datapointchris/some/deep/path', 'not-a-url'],
)
def test_a_repo_with_no_releases_api_answers_nothing_rather_than_guessing(released, repo: str) -> None:
    """A non-GitHub host and a malformed path mean the same thing — nothing to pin
    to — and the caller does the same thing with either."""
    asked = released('v6.0.0')

    assert uvtool.latest_release(repo) is None
    assert asked == []


# ─────────────────────────────────────────────────────────────────────────────
# Held to the lock at the revision it installs
# ─────────────────────────────────────────────────────────────────────────────

PINS = uv_lock.Pins(('typer==0.20.0',), ('toon-format @ git+https://github.com/toon-format/toon-python@8dfb593',))


def test_the_lock_is_read_at_the_tag_being_installed(uv, released, locked) -> None:
    """A lock read from the branch head would hold a tagged install to versions its tag never tested."""
    released('v6.0.0')
    locked(PINS)
    reached = uv()

    uvtool.install_git(SYNCER, offline=False)

    [clone] = clones(reached)
    assert clone[:-1] == ('git', 'clone', '--quiet', '--depth', '1', '--branch', 'v6.0.0', 'https://github.com/datapointchris/syncer.git')


def test_a_branch_tracking_tool_reads_the_lock_at_the_head(uv, released, locked) -> None:
    """`tracks_branch` is declared rather than discovered, so the releases API is never asked."""
    asked = released('v1.0.0')
    locked(PINS)
    reached = uv()

    uvtool.install_git(KEYMAP, offline=False)

    [clone] = clones(reached)
    assert '--branch' not in clone
    assert installs(reached)[0][-1] == 'https://github.com/datapointchris/keymap-align.git'
    assert asked == []


def test_a_locked_revision_hands_uv_its_constraints_and_overrides(uv, released, locked) -> None:
    released('v6.0.0')
    locked(PINS)
    reached = uv()

    result = uvtool.install_git(SYNCER, offline=False, again=True)

    [install] = installs(reached)
    assert install[:4] == ('uv', 'tool', 'install', '--reinstall')
    assert (install[4], install[6]) == ('--constraints', '--overrides')
    assert install[-1] == 'syncer @ git+https://github.com/datapointchris/syncer.git@v6.0.0'
    assert result.ok
    assert 'held to its uv.lock' in result.detail


def test_a_revision_with_no_lock_installs_unconstrained_and_names_the_revision(uv, released, capsys) -> None:
    released('v6.0.0')
    reached = uv()

    result = uvtool.install_git(SYNCER, offline=False)

    assert result.ok
    assert installs(reached) == [('uv', 'tool', 'install', 'syncer @ git+https://github.com/datapointchris/syncer.git@v6.0.0')]
    assert 'syncer: v6.0.0 has no uv.lock' in capsys.readouterr().err


def test_a_clone_that_fails_refuses_rather_than_installing_unlocked(uv) -> None:
    """Offline, on a branch-tracking tool, because that is the one install that
    reaches the clone with no network: a pinned one has already refused on its tag."""
    reached = uv(reachable=False, said='fatal: unable to access the repository')

    result = uvtool.install_git(KEYMAP, offline=True)

    assert not result.ok
    assert result.kind is Kind.DOWNLOAD_FAILED
    assert 'could not clone' in result.detail
    assert 'the offline bundle stages no Python tools to fall back on' in result.detail
    assert installs(reached) == []


def test_a_lock_uv_will_not_export_refuses_rather_than_installing_unlocked(uv, released, locked) -> None:
    released('v6.0.0')
    locked(uv_lock.Unexportable('error: unsupported lock version'))
    reached = uv()

    result = uvtool.install_git(SYNCER, offline=False)

    assert not result.ok
    assert result.kind is Kind.COMMAND_FAILED
    assert 'uv.lock at v6.0.0' in result.detail
    assert 'unsupported lock version' in result.detail
    assert installs(reached) == []


# ─────────────────────────────────────────────────────────────────────────────
# Against real git and real uv
#
# Offline, against a find-links directory this file writes, so nothing reaches
# an index and nothing lands in the machine's own tool directory.
# `would_change_this_machine` in tests/conftest.py lets this one `uv tool
# install` through, and only while the three `UV_TOOL_SCRATCH` directories are
# under tmp and `UV_OFFLINE` is 1.
# ─────────────────────────────────────────────────────────────────────────────


def git(repo: Path, *args: str) -> None:
    identity = {'GIT_AUTHOR_NAME': 'T', 'GIT_AUTHOR_EMAIL': 't@t', 'GIT_COMMITTER_NAME': 'T', 'GIT_COMMITTER_EMAIL': 't@t'}
    subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, env={**os.environ, **identity})


def wheel(index: Path, name: str, version: str) -> None:
    """A pure-Python wheel written by hand, so the index needs no build backend."""
    info = f'{name}-{version}.dist-info'
    files = {
        f'{name}/__init__.py': '',
        f'{info}/METADATA': f'Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n',
        f'{info}/WHEEL': 'Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n',
    }
    record = [f'{path},sha256={digest(body)},{len(body.encode())}' for path, body in files.items()]
    files[f'{info}/RECORD'] = '\n'.join([*record, f'{info}/RECORD,,', ''])
    with zipfile.ZipFile(index / f'{name}-{version}-py3-none-any.whl', 'w') as packed:
        for path, body in files.items():
            packed.writestr(path, body)


def digest(body: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(body.encode()).digest()).rstrip(b'=').decode()


def project(
    repo: Path,
    name: str,
    version: str,
    dependencies: tuple[str, ...] = (),
    script: bool = False,
    optional: dict[str, list[str]] | None = None,
) -> None:
    """A uv_build project in its own git repo, which uv builds with no backend to fetch."""
    (repo / 'src' / name).mkdir(parents=True)
    (repo / 'src' / name / '__init__.py').write_text('def main():\n    pass\n')
    scripts = f'\n[project.scripts]\n{name} = "{name}:main"\n' if script else ''
    extras = ''.join(f'{extra} = {wanted!r}\n' for extra, wanted in (optional or {}).items())
    table = f'[project.optional-dependencies]\n{extras}\n' if extras else ''
    (repo / 'pyproject.toml').write_text(
        f'[project]\nname = "{name}"\nversion = "{version}"\nrequires-python = ">=3.11"\n'
        f'dependencies = {list(dependencies)!r}\n{scripts}\n{table}'
        '[build-system]\nrequires = ["uv_build"]\nbuild-backend = "uv_build"\n'
    )
    git(repo, 'init', '--quiet', '--initial-branch=main')
    git(repo, 'add', '-A')
    git(repo, 'commit', '--quiet', '-m', version)


def installed(tools: Path, tool: str, package: str) -> str:
    probe = 'import importlib.metadata, sys; print(importlib.metadata.version(sys.argv[1]))'
    return subprocess.run(
        [str(tools / tool / 'bin' / 'python'), '-c', probe, package], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def offline_index(tmp_path: Path, monkeypatch):
    """uv pointed at a directory of wheels and nothing else, writing only under tmp."""
    index = tmp_path / 'index'
    index.mkdir()
    for name, value in {
        'UV_TOOL_DIR': tmp_path / 'tools',
        'UV_TOOL_BIN_DIR': tmp_path / 'bin',
        'UV_CACHE_DIR': tmp_path / 'cache',
        'UV_FIND_LINKS': index,
        'UV_NO_INDEX': '1',
        'UV_OFFLINE': '1',
        'UV_PYTHON_DOWNLOADS': 'never',
    }.items():
        monkeypatch.setenv(name, str(value))
    return index


def test_an_installed_git_tool_runs_on_its_locks_versions_not_the_newest(tmp_path: Path, offline_index: Path, monkeypatch) -> None:
    """The tool's tag locks 1.0.0 of a registry package and of a git one, and 2.0.0
    of each exists by the time it is installed.

    Both kinds, because a registry pin reaches uv as a constraint and a git pin
    as an override. Exported whole as constraints, the lock fails on the git pin
    with `Requirements contain conflicting URLs`.

    The second install is the control. The same tag handed to uv with no lock
    takes 2.0.0 of both, so 1.0.0 above is the lock's doing rather than the only
    version on offer.
    """
    wheel(offline_index, 'pindemo', '1.0.0')
    gitdep = tmp_path / 'gitdep'
    project(gitdep, 'gitdep', '1.0.0')

    tool = tmp_path / 'locktool'
    project(tool, 'locktool', '1.0.0', dependencies=('pindemo>=1', f'gitdep @ git+file://{gitdep}'), script=True)
    subprocess.run(['uv', 'lock', '--quiet'], cwd=tool, check=True, capture_output=True)
    git(tool, 'add', 'uv.lock')
    git(tool, 'commit', '--quiet', '-m', 'lock')
    git(tool, 'tag', 'v1.0.0')

    wheel(offline_index, 'pindemo', '2.0.0')
    (gitdep / 'pyproject.toml').write_text((gitdep / 'pyproject.toml').read_text().replace('1.0.0', '2.0.0'))
    git(gitdep, 'commit', '--quiet', '-am', '2.0.0')

    monkeypatch.setattr(uvtool, 'latest_release', lambda repo: 'v1.0.0')
    entry = catalog.GitUvTool.from_mapping({'name': 'locktool', 'repo': f'file://{tool}'})
    tools = tmp_path / 'tools'

    result = uvtool.install_git(entry, offline=False)

    assert result.ok, result.detail
    assert (installed(tools, 'locktool', 'pindemo'), installed(tools, 'locktool', 'gitdep')) == ('1.0.0', '1.0.0')

    subprocess.run(
        ['uv', 'tool', 'install', '--quiet', '--reinstall', uvtool.requirement(entry, 'v1.0.0')], check=True, capture_output=True
    )
    assert (installed(tools, 'locktool', 'pindemo'), installed(tools, 'locktool', 'gitdep')) == ('2.0.0', '2.0.0')


def distributions(tools: Path, tool: str) -> dict[str, str]:
    probe = 'import importlib.metadata as m; print("\\n".join(f"{d.name}={d.version}" for d in m.distributions()))'
    listed = subprocess.run([str(tools / tool / 'bin' / 'python'), '-c', probe], check=True, capture_output=True, text=True)
    return dict(line.split('=', 1) for line in listed.stdout.split())


def test_a_git_dependency_keeps_the_extras_the_tool_asked_for(tmp_path: Path, offline_index: Path, monkeypatch) -> None:
    """The tool declares `gitdep[x]`, and `x` brings extrademo. Without the extra
    on the override line, gitdep installs and extrademo never does."""
    wheel(offline_index, 'pindemo', '1.0.0')
    wheel(offline_index, 'extrademo', '1.0.0')
    gitdep = tmp_path / 'gitdep'
    project(gitdep, 'gitdep', '1.0.0', optional={'x': ['extrademo']})

    tool = tmp_path / 'locktool'
    project(tool, 'locktool', '1.0.0', dependencies=('pindemo>=1', f'gitdep[x] @ git+file://{gitdep}'), script=True)
    subprocess.run(['uv', 'lock', '--quiet'], cwd=tool, check=True, capture_output=True)
    git(tool, 'add', 'uv.lock')
    git(tool, 'commit', '--quiet', '-m', 'lock')
    git(tool, 'tag', 'v1.0.0')
    wheel(offline_index, 'extrademo', '2.0.0')

    monkeypatch.setattr(uvtool, 'latest_release', lambda repo: 'v1.0.0')
    entry = catalog.GitUvTool.from_mapping({'name': 'locktool', 'repo': f'file://{tool}'})

    result = uvtool.install_git(entry, offline=False)

    assert result.ok, result.detail
    assert distributions(tmp_path / 'tools', 'locktool') == {
        'locktool': '1.0.0',
        'pindemo': '1.0.0',
        'gitdep': '1.0.0',
        'extrademo': '1.0.0',
    }
