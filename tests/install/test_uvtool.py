"""Installing a Python tool with uv, and the pin that keeps its updater alive.

The PyPI half has one decision in it and the git half has all of them, so most of
this is about `requirement`: what gets handed to uv, and what happens when the
repo it names publishes nothing to pin to.

The seam for the network is `github_release.latest_version`, because resolving a
tag is the only thing here that leaves the machine.
"""

from __future__ import annotations

import pytest

from dotfiles import catalog
from dotfiles import effects
from dotfiles import github_release
from dotfiles.effects import Completed
from dotfiles.providers import uvtool

RUFF = catalog.UvTool.from_mapping({'name': 'ruff'})
SYNCER = catalog.GitUvTool.from_mapping({'name': 'syncer', 'repo': 'https://github.com/datapointchris/syncer.git'})
KEYMAP = catalog.GitUvTool.from_mapping(
    {'name': 'keymap-align', 'repo': 'https://github.com/datapointchris/keymap-align.git', 'tracks_branch': True}
)


class Uv:
    """`uv tool install`, answering however this test says it went."""

    def __init__(self, *, ok: bool = True, said: str = '') -> None:
        self.ok = ok
        self.said = said
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, command, **_kwargs) -> Completed:
        argv = tuple(str(part) for part in command)
        self.calls.append(argv)
        return Completed(argv, 0, '') if self.ok else Completed(argv, 1, self.said)


@pytest.fixture
def uv(monkeypatch):
    def install(**kwargs) -> Uv:
        recorder = Uv(**kwargs)
        monkeypatch.setattr(effects, 'run', recorder)
        return recorder

    return install


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

    assert reached.calls == [('uv', 'tool', 'install', '--reinstall', 'syncer @ git+https://github.com/datapointchris/syncer.git@v6.0.0')]


def test_a_failure_reports_what_uv_said(uv) -> None:
    uv(ok=False, said='error: distribution not found for: nosuchtool')

    result = uvtool.install(RUFF, offline=False)

    assert not result.ok
    assert 'distribution not found' in result.detail


def test_offline_still_tries_pypi_and_says_there_is_no_fallback(uv) -> None:
    """The bundle stages wheels for this CLI's own closure and nothing else, while
    the machine that installs offline declares six uv tools — so refusing would
    install none of them on the box the offline path exists for."""
    reached = uv(ok=False, said='error: network unreachable')

    result = uvtool.install(RUFF, offline=True)

    assert reached.calls == [('uv', 'tool', 'install', 'ruff')]
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

    assert reached.calls == [('uv', 'tool', 'install', 'syncer @ git+https://github.com/datapointchris/syncer.git@v6.0.0')]


def test_the_tool_name_leads_the_requirement(uv, released) -> None:
    """uv records the requirement under whatever name leads it, and that is what
    makes the receipt readable by everything that reads it afterwards."""
    released('v6.0.0')

    assert uvtool.requirement(SYNCER).startswith('syncer @ git+')


def test_a_repo_declaring_tracks_branch_is_never_pinned(uv, released) -> None:
    """A repo publishing no releases has no tag to pin to, which is a declaration
    rather than something to discover per run."""
    asked = released('v1.0.0')

    assert uvtool.requirement(KEYMAP) == 'https://github.com/datapointchris/keymap-align.git'
    assert asked == []


def test_a_repo_with_no_release_installs_from_the_branch_with_a_warning(uv, released, capsys) -> None:
    """The install still works; it is the tool's own updater that will not, and
    install time is the only moment anyone would notice."""
    released(None)
    reached = uv()

    uvtool.install_git(SYNCER, offline=False)

    assert reached.calls == [('uv', 'tool', 'install', 'https://github.com/datapointchris/syncer.git')]
    assert 'refuse to run' in capsys.readouterr().err


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
