"""Finding a bundle archive and unpacking it, on a real filesystem.

Nothing here is stubbed, because every question this module answers is a
filesystem question: which of two tarballs is the newer, whether the thing that
came out of one is a bundle, and whether staging a second one over the first
destroys what the first carried. A mocked archive would assert only that the code
calls the functions it calls.

The layout under test is the bundler's: one member named `installers`, holding
the manifest every provider reads. `test_create_bundle.py` owns the other half —
that what `bundle create` writes has that shape.
"""

from __future__ import annotations

import tarfile
from pathlib import Path

import pytest

from dotfiles import catalog
from dotfiles import machine as machines
from dotfiles import offline_bundle
from dotfiles import paths
from dotfiles import reconcile
from dotfiles import resolve
from dotfiles.providers import bundle
from dotfiles.vocabulary import ExitCode


def archive(at: Path, name: str, *, manifest: bool = True, files: dict[str, str] | None = None) -> Path:
    """A bundle tarball, laid out the way `bundle create` lays one out."""
    staging = at / f'{name}-contents' / 'installers'
    staging.mkdir(parents=True)
    if manifest:
        (staging / bundle.MANIFEST).write_text('binary|fd|10.2.0|fd\n')
    for relative, content in (files or {}).items():
        (staging / relative).parent.mkdir(parents=True, exist_ok=True)
        (staging / relative).write_text(content)

    tarball = at / name
    with tarfile.open(tarball, 'w:gz') as packed:
        packed.add(staging, arcname='installers')
    return tarball


@pytest.fixture
def home(tmp_path, monkeypatch) -> Path:
    root = tmp_path / 'home'
    root.mkdir()
    monkeypatch.setenv('HOME', str(root))
    return root


@pytest.fixture
def staged(tmp_path, monkeypatch) -> Path:
    """Where a bundle lands, deliberately not named `installers`.

    `$DOTFILES_BUNDLE` is allowed to point anywhere, and extracting the archive's
    `installers` member in place would only ever land on a directory of that
    name — which is the bug this fixture exists to catch rather than describe.
    """
    destination = tmp_path / 'elsewhere' / 'staging'
    monkeypatch.setattr(paths, 'BUNDLE_DIR', destination)
    return destination


def test_the_newest_archive_in_a_directory_wins(tmp_path) -> None:
    """Dated names sort as dates do, which is the whole of the comparison."""
    archive(tmp_path, 'dotfiles-offline-v20260101-wsl-linux-x86_64.tar.gz')
    latest = archive(tmp_path, 'dotfiles-offline-v20260810-wsl-linux-x86_64.tar.gz')

    assert offline_bundle.newest(tmp_path) == latest


def test_the_first_directory_holding_any_wins(tmp_path, home) -> None:
    """A tarball just copied next to the checkout beats a stale one in $HOME.

    Newest-across-both would pick the older file here, which is the answer a
    machine gets after its second rebuild in a year.
    """
    beside_the_checkout = archive(tmp_path, 'dotfiles-offline-v20260101-wsl-linux-x86_64.tar.gz')
    archive(home, 'dotfiles-offline-v20260810-wsl-linux-x86_64.tar.gz')

    assert offline_bundle.newest(tmp_path, home) == beside_the_checkout


def test_no_archive_anywhere_is_not_an_error(tmp_path, home) -> None:
    """The caller decides what to say: apply refuses, `bundle stage` explains."""
    assert offline_bundle.newest(tmp_path, home) is None


def test_staging_lands_on_the_bundle_dir_whatever_it_is_called(tmp_path, staged) -> None:
    tarball = archive(tmp_path, 'dotfiles-offline-v20260810-wsl-linux-x86_64.tar.gz', files={'bin/uv': 'uv'})

    assert offline_bundle.stage(tarball) == staged
    assert (staged / bundle.MANIFEST).is_file()
    assert (staged / 'bin' / 'uv').read_text() == 'uv'


def test_a_second_bundle_refreshes_rather_than_replaces(tmp_path, staged) -> None:
    """What `tar -x` over the top does, and what the bundle README promises.

    Replacing would delete the wheels a half-finished run still needs, on the one
    machine that cannot download them again.
    """
    first = archive(tmp_path, 'dotfiles-offline-v20260101-wsl-linux-x86_64.tar.gz', files={'bin/uv': 'old', 'wheels/one.whl': 'kept'})
    second = archive(tmp_path, 'dotfiles-offline-v20260810-wsl-linux-x86_64.tar.gz', files={'bin/uv': 'new'})

    offline_bundle.stage(first)
    offline_bundle.stage(second)

    assert (staged / 'bin' / 'uv').read_text() == 'new'
    assert (staged / 'wheels' / 'one.whl').read_text() == 'kept'


def test_a_tarball_without_a_manifest_is_refused(tmp_path, staged) -> None:
    """Named here, where the archive is in hand, rather than as every tool in the
    plan turning up missing several stages later."""
    tarball = archive(tmp_path, 'dotfiles-offline-v20260810-wsl-linux-x86_64.tar.gz', manifest=False)

    with pytest.raises(offline_bundle.StagingError, match=bundle.MANIFEST):
        offline_bundle.stage(tarball)

    assert not staged.exists()


def test_an_unreadable_archive_is_refused(tmp_path, staged) -> None:
    tarball = tmp_path / 'dotfiles-offline-v20260810-wsl-linux-x86_64.tar.gz'
    tarball.write_text('this is not a tarball')

    with pytest.raises(offline_bundle.StagingError, match='not a readable archive'):
        offline_bundle.stage(tarball)


def test_apply_stages_the_archive_it_finds(tmp_path, home, staged, monkeypatch) -> None:
    """The behaviour the bootstrap would otherwise supply by running the apply itself."""
    monkeypatch.chdir(tmp_path)
    archive(tmp_path, 'dotfiles-offline-v20260810-wsl-linux-x86_64.tar.gz', files={'bin/uv': 'uv'})

    assert reconcile._stage_bundle() is None
    assert (staged / 'bin' / 'uv').read_text() == 'uv'


def test_apply_leaves_a_staged_bundle_alone(tmp_path, home, staged, monkeypatch) -> None:
    """A machine part way through an offline install already has one, and
    re-reading the archive is work for an answer that is on disk."""
    monkeypatch.chdir(tmp_path)
    staged.mkdir(parents=True)
    (staged / bundle.MANIFEST).write_text('what the interrupted run staged\n')
    archive(tmp_path, 'dotfiles-offline-v20260810-wsl-linux-x86_64.tar.gz')

    assert reconcile._stage_bundle() is None
    assert (staged / bundle.MANIFEST).read_text() == 'what the interrupted run staged\n'


def test_apply_refuses_with_no_archive_to_stage(tmp_path, home, staged, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    assert reconcile._stage_bundle() is ExitCode.ISSUE


def test_apply_refuses_the_archive_it_cannot_stage(tmp_path, home, staged, monkeypatch) -> None:
    """A broken bundle stops the run rather than starting one that will fail as
    every tool in the plan turning up missing."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'dotfiles-offline-v20260810-wsl-linux-x86_64.tar.gz').write_text('not a tarball')

    assert reconcile._stage_bundle() is ExitCode.ISSUE
    assert not staged.exists()


class TestSayingWhichBundle:
    """A run that installs from a bundle has to name the bundle.

    The already-staged branch returned early and printed nothing, so every offline
    apply after the first said not one word about where its answers came from — and
    under `--offline` the bundle *is* the upstream every currency verdict is decided
    against. Measured 2026-08-13 on the work box: twelve package items came back
    unmeasurable and the only thing on screen was one failed install.
    """

    def test_an_already_staged_bundle_is_named_rather_than_passed_over(self, staged, capsys) -> None:
        staged.mkdir(parents=True)
        (staged / bundle.MANIFEST).write_text('binary|fd|10.2.0|fd\ncargo|ripgrep|15.2.0|rg.tar.gz\n')

        assert reconcile._stage_bundle() is None

        # Newlines stripped before matching: Rich wraps a long path across lines, and
        # the assertion is about what the line says rather than where it breaks.
        said = capsys.readouterr().err.replace('\n', '')
        assert str(staged) in said
        assert 'already staged' in said
        assert '2 file(s)' in said

    def test_the_categories_are_named_because_a_bundle_of_wheels_is_not_a_bundle(self, staged, capsys) -> None:
        """`61 files` reads as a full bundle when 60 of them are the CLI's own wheels."""
        staged.mkdir(parents=True)
        (staged / bundle.MANIFEST).write_text('wheel|rich|14.0.0|rich.whl\nbinary|fd|10.2.0|fd\n')

        reconcile._stage_bundle()

        assert 'binary 1, wheel 1' in capsys.readouterr().err

    def test_a_freshly_unpacked_bundle_says_which_archive_it_came_from(self, tmp_path, home, staged, monkeypatch, capsys) -> None:
        monkeypatch.chdir(tmp_path)
        archive(tmp_path, 'dotfiles-offline-v20260813-wsl-linux-x86_64.tar.gz')

        assert reconcile._stage_bundle() is None

        assert 'unpacked dotfiles-offline-v20260813-wsl-linux-x86_64.tar.gz' in capsys.readouterr().err

    def test_a_directory_with_no_manifest_ends_the_run_rather_than_starting_it(self, staged, capsys) -> None:
        """Every provider reads the bundle through the manifest, so without one the
        run installs nothing from anywhere and reports each tool as its own mystery."""
        staged.mkdir(parents=True)

        assert reconcile._stage_bundle() is ExitCode.ISSUE
        assert bundle.MANIFEST in capsys.readouterr().err

    def test_the_build_date_and_platform_are_read_off_the_header(self, staged) -> None:
        staged.mkdir(parents=True)
        (staged / bundle.MANIFEST).write_text(
            '# Dotfiles Offline Bundle\n# Created: Thu Aug 13 00:51:54 2026\n# Platform: linux/x86_64\nbinary|fd|10.2.0|fd\n'
        )

        described = offline_bundle.describe()

        assert described.built == 'Thu Aug 13 00:51:54 2026'
        assert described.platform == 'linux/x86_64'
        assert len(described.carried) == 1, 'the header lines must not be read as rows'


class TestCoverage:
    """Which declared items a bundle can install, and which it was never built to."""

    def _plan(self, name: str = 'wsl-work-workstation'):
        return resolve.resolve(catalog.load(), machines.load(name))

    def test_a_system_package_is_not_a_gap_in_a_bundle(self, staged) -> None:
        """The first version of this reported `apt`, `bash` and `ca-certificates` as
        things the bundle had failed to carry — a list nobody can act on, burying the
        rows that matter. A bundle stages four declaration kinds and apt is not one."""
        staged.mkdir(parents=True)
        (staged / bundle.MANIFEST).write_text('binary|fd|10.2.0|fd\n')

        found = offline_bundle.coverage(offline_bundle.describe(), self._plan())

        assert 'apt' not in found.uncovered
        assert 'bash' not in found.uncovered
        assert found.outside > 0, 'the items a bundle never carries are counted, not dropped'

    def test_a_go_tool_is_matched_on_its_executable_not_its_name(self, staged) -> None:
        """The bundler records a Go tool under `entry.executable` and every other kind
        under its name, so comparing names alone reported tools the bundle carries."""
        staged.mkdir(parents=True)
        (staged / bundle.MANIFEST).write_text('go-binary|task|v3.52.0|task\n')

        found = offline_bundle.coverage(offline_bundle.describe(), self._plan())

        assert 'task' in found.covered
