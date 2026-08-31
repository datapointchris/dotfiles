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

import json
import tarfile
from pathlib import Path

import pytest

from dotfiles import catalog
from dotfiles import machine as machines
from dotfiles import offline_bundle
from dotfiles import providers
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
    # The archive search reads `$XDG_CACHE_HOME/dotfiles/bundles`, and it is set on
    # every real desk. Inherited, a test asserting that nothing can be staged finds
    # whatever bundle that machine last built and unpacks it — half a gigabyte per
    # test, into the temp directory, before failing on an answer it was handed.
    monkeypatch.setenv('XDG_CACHE_HOME', str(root / '.cache'))
    return root


BUNDLE = 'dotfiles-offline-v20260814T190203Z-box-linux-x86_64'

MACHINE_NAME = 'box'
"""What these archives say they were built for, so staging is not a foreign one.

Passed explicitly rather than resolved, because `stage` takes the name it
compares against — a test that let it resolve the real machine would refuse or
allow depending on whose desk it ran at.
"""


@pytest.fixture
def staging(tmp_path, monkeypatch) -> Path:
    """The directory staged bundles land *in*, deliberately not named `installers`.

    `$DOTFILES_BUNDLE` is allowed to point anywhere, and extracting the archive's
    `installers` member in place would only ever land on a directory of that
    name — which is the bug this fixture exists to catch rather than describe.
    """
    destination = tmp_path / 'elsewhere' / 'staging'
    monkeypatch.setenv('DOTFILES_BUNDLE', str(destination))
    return destination


@pytest.fixture
def staged(staging) -> Path:
    """One bundle inside it, for a test that only needs there to be one."""
    return staging / BUNDLE


def test_the_newest_archive_in_a_directory_wins(tmp_path) -> None:
    """Dated names sort as dates do, which is the whole of the comparison."""
    archive(tmp_path, 'dotfiles-offline-v20260101-wsl-linux-x86_64.tar.gz')
    latest = archive(tmp_path, 'dotfiles-offline-v20260810-wsl-linux-x86_64.tar.gz')

    assert offline_bundle.newest(tmp_path) == latest


def test_the_newest_archive_across_every_directory_wins(tmp_path, home) -> None:
    """Ranked across all of them, not the first that holds any.

    A download writes into the cache, which is a third place a tarball
    legitimately sits — and no first-directory-wins order can rank it against a
    copy beside the checkout. The stamp is to the second, so the comparison it
    replaces that order with is unambiguous.
    """
    archive(tmp_path, 'dotfiles-offline-v20260101T010000Z-wsl-linux-x86_64.tar.gz')
    latest = archive(home, 'dotfiles-offline-v20260810T010000Z-wsl-linux-x86_64.tar.gz')

    assert offline_bundle.newest(tmp_path, home) == latest


def test_no_archive_anywhere_is_not_an_error(tmp_path, home) -> None:
    """The caller decides what to say: apply refuses, `bundle stage` explains."""
    assert offline_bundle.newest(tmp_path, home) is None


def test_a_peer_s_archive_does_not_outrank_this_machine_s(tmp_path) -> None:
    """`bundle download --machine X` writes a peer's archive into the same cache.
    Unfiltered it sorts newest, wins here, and is refused by `stage` a line later
    — ending the run with this machine's own bundle in the same directory and
    nothing able to reach it."""
    mine = archive(tmp_path, 'dotfiles-offline-v20260101T010000Z-box-linux-x86_64.tar.gz')
    archive(tmp_path, 'dotfiles-offline-v20260810T010000Z-other-box-linux-x86_64.tar.gz')

    assert offline_bundle.newest(tmp_path, machine=MACHINE_NAME) == mine
    assert offline_bundle.newest(tmp_path) != mine, 'unfiltered, the peer still wins'


def test_a_hand_carried_archive_still_stages(tmp_path) -> None:
    """A name this tool did not write answers `''` for its manifest, and passes.
    `stage`'s own `bundle.json` check is the backstop, and refusing here would
    make a tarball someone copied across unusable."""
    stranger = archive(tmp_path, 'dotfiles-offline-v20260810T010000Z-handmade.tar.gz')

    assert offline_bundle.newest(tmp_path, machine=MACHINE_NAME) == stranger


def test_staging_lands_in_a_directory_named_after_the_archive(tmp_path, staging) -> None:
    """Named after the archive, so a machine can say which bundle a file came from.

    The archive's single member is `installers` whatever the tarball is called, so
    extracting in place would land on a directory of that name every time.
    """
    tarball = archive(tmp_path, 'dotfiles-offline-v20260810T010000Z-wsl-linux-x86_64.tar.gz', files={'bin/uv': 'uv'})

    landed = offline_bundle.stage(tarball, MACHINE_NAME, '')

    assert landed == staging / 'dotfiles-offline-v20260810T010000Z-wsl-linux-x86_64'
    assert (landed / bundle.MANIFEST).is_file()
    assert (landed / 'bin' / 'uv').read_text() == 'uv'


def test_a_second_bundle_stacks_rather_than_merging(tmp_path, staging) -> None:
    """The newer bundle answers for what it carries; the older still answers for
    the rest.

    Merging into one tree refreshes the files and *replaces* `manifest.txt`, which
    leaves everything the first bundle staged on disk and unlisted — and the
    manifest is the only door in, so those tools become unmeasurable on the one
    machine that cannot download them again.
    """
    first = archive(
        tmp_path,
        'dotfiles-offline-v20260101T010000Z-wsl-linux-x86_64.tar.gz',
        files={'bin/uv': 'old', 'wheels/one.whl': 'kept'},
    )
    second = archive(tmp_path, 'dotfiles-offline-v20260810T010000Z-wsl-linux-x86_64.tar.gz', files={'bin/uv': 'new'})

    offline_bundle.stage(first, MACHINE_NAME, '')
    offline_bundle.stage(second, MACHINE_NAME, '')

    assert providers.bundle_file('bin/uv').read_text() == 'new'
    assert providers.bundle_file('wheels/one.whl').read_text() == 'kept'
    assert len(providers.staged_bundles()) == 2


def test_the_older_bundle_still_answers_for_what_the_newer_left_out(tmp_path, staging) -> None:
    """A sparse bundle is exactly this: it carries what changed and nothing else."""
    full = archive(
        tmp_path,
        'dotfiles-offline-v20260101T010000Z-wsl-linux-x86_64.tar.gz',
        files={'binaries/fd': 'fd-old', 'binaries/bat': 'bat-1'},
    )
    sparse = archive(tmp_path, 'dotfiles-offline-v20260810T010000Z-wsl-linux-x86_64-sparse.tar.gz', files={'binaries/fd': 'fd-new'})

    offline_bundle.stage(full, MACHINE_NAME, '')
    offline_bundle.stage(sparse, MACHINE_NAME, '')

    located = providers.locate('binaries/fd')
    assert located is not None
    assert located.path.read_text() == 'fd-new'
    assert located.bundle.endswith('-sparse')
    assert providers.bundle_file('binaries/bat').read_text() == 'bat-1'


def test_re_staging_one_archive_leaves_the_others_alone(tmp_path, staging) -> None:
    """An interrupted stage can be repeated. Replacing the whole staging directory
    would take the wheels a half-finished run still needs."""
    first = archive(tmp_path, 'dotfiles-offline-v20260101T010000Z-wsl-linux-x86_64.tar.gz', files={'wheels/one.whl': 'kept'})
    second = archive(tmp_path, 'dotfiles-offline-v20260810T010000Z-wsl-linux-x86_64.tar.gz', files={'bin/uv': 'new'})

    offline_bundle.stage(first, MACHINE_NAME, '')
    offline_bundle.stage(second, MACHINE_NAME, '')
    offline_bundle.stage(second, MACHINE_NAME, '')

    assert providers.bundle_file('wheels/one.whl').read_text() == 'kept'
    assert len(providers.staged_bundles()) == 2


def test_a_tarball_without_a_manifest_is_refused(tmp_path, staging) -> None:
    """Named here, where the archive is in hand, rather than as every tool in the
    plan turning up missing several stages later."""
    tarball = archive(tmp_path, 'dotfiles-offline-v20260810T010000Z-wsl-linux-x86_64.tar.gz', manifest=False)

    with pytest.raises(offline_bundle.StagingError, match=providers.MANIFEST):
        offline_bundle.stage(tarball, MACHINE_NAME, '')

    assert providers.staged_bundles() == ()


def test_an_unreadable_archive_is_refused(tmp_path, staged) -> None:
    tarball = tmp_path / 'dotfiles-offline-v20260810-wsl-linux-x86_64.tar.gz'
    tarball.write_text('this is not a tarball')

    with pytest.raises(offline_bundle.StagingError, match='not a readable archive'):
        offline_bundle.stage(tarball, MACHINE_NAME, '')


def test_apply_stages_the_archive_it_finds(tmp_path, home, staging, monkeypatch) -> None:
    """The behaviour the bootstrap would otherwise supply by running the apply itself."""
    monkeypatch.chdir(tmp_path)
    archive(tmp_path, 'dotfiles-offline-v20260810T010000Z-wsl-linux-x86_64.tar.gz', files={'bin/uv': 'uv'})

    assert reconcile._stage_bundle('', '') is None
    assert providers.bundle_file('bin/uv').read_text() == 'uv'


def test_apply_leaves_a_staged_bundle_alone(tmp_path, home, staged, monkeypatch) -> None:
    """A machine part way through an offline install already has one, and
    re-reading the archive is work for an answer that is on disk."""
    monkeypatch.chdir(tmp_path)
    staged.mkdir(parents=True)
    (staged / bundle.MANIFEST).write_text('what the interrupted run staged\n')
    archive(tmp_path, 'dotfiles-offline-v20260810-wsl-linux-x86_64.tar.gz')

    assert reconcile._stage_bundle('', '') is None
    assert (staged / bundle.MANIFEST).read_text() == 'what the interrupted run staged\n'


def test_apply_refuses_with_no_archive_to_stage(tmp_path, home, staged, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    assert reconcile._stage_bundle('', '') is ExitCode.ISSUE


def test_apply_skips_a_peer_s_archive_and_stages_this_machine_s(tmp_path, home, staging, monkeypatch) -> None:
    """The gate takes the machine the caller resolved. Unfiltered, the peer's
    archive was picked and then refused, ending the run."""
    monkeypatch.chdir(tmp_path)
    archive(tmp_path, 'dotfiles-offline-v20260101T010000Z-box-linux-x86_64.tar.gz', files={'bin/uv': 'mine'})
    archive(tmp_path, 'dotfiles-offline-v20260810T010000Z-other-box-linux-x86_64.tar.gz', files={'bin/uv': 'theirs'})

    assert reconcile._stage_bundle(MACHINE_NAME, '') is None
    assert providers.bundle_file('bin/uv').read_text() == 'mine'


def test_apply_refuses_a_peer_s_bundle_already_in_the_stack(tmp_path, home, staging, monkeypatch) -> None:
    """`providers.locate` reads across the whole stack, so a peer's bundle
    underneath a good one still supplies files. `stage` refuses at the moment of
    unpacking and cannot see what was already there."""
    monkeypatch.chdir(tmp_path)
    theirs = staging / 'dotfiles-offline-v20260810T010000Z-other-box-linux-x86_64'
    theirs.mkdir(parents=True)
    (theirs / bundle.MANIFEST).write_text('binary|fd|10.2.0|fd\n')
    (theirs / bundle.DOCUMENT).write_text('{"machine": "other-box", "completeness": "full"}\n')

    assert reconcile._stage_bundle(MACHINE_NAME, '') is ExitCode.ISSUE


def test_apply_stages_a_newer_archive_over_one_already_staged(tmp_path, home, staging, monkeypatch) -> None:
    """The download is the whole point of downloading. A run that stopped at "some
    bundle is staged" installed from the one the new archive was fetched to replace,
    reported a converged machine, and on a real box downgraded a tool to the version
    a fortnight-old bundle carried."""
    monkeypatch.chdir(tmp_path)
    older = staging / 'dotfiles-offline-v20260101T010000Z-box-linux-x86_64'
    (older / 'bin').mkdir(parents=True)
    (older / bundle.MANIFEST).write_text('binary|fd|10.2.0|fd\n')
    (older / 'bin' / 'uv').write_text('a fortnight old')
    archive(tmp_path, 'dotfiles-offline-v20260810T010000Z-box-linux-x86_64.tar.gz', files={'bin/uv': 'just downloaded'})

    assert reconcile._stage_bundle(MACHINE_NAME, '') is None
    assert providers.bundle_file('bin/uv').read_text() == 'just downloaded'
    assert len(providers.staged_bundles()) == 2, 'the older one stays, because a sparse bundle reads through it'


def test_apply_does_not_re_unpack_the_archive_it_already_staged(tmp_path, home, staging, monkeypatch) -> None:
    """The other half. Re-reading a tarball every run costs minutes on the machine
    this exists for, and the newest archive already being staged is the steady state."""
    monkeypatch.chdir(tmp_path)
    archive(tmp_path, f'{BUNDLE}.tar.gz', files={'bin/uv': 'from the tarball'})
    unpacked = staging / BUNDLE
    (unpacked / 'bin').mkdir(parents=True)
    (unpacked / bundle.MANIFEST).write_text('binary|fd|10.2.0|fd\n')
    (unpacked / 'bin' / 'uv').write_text('left alone')

    assert reconcile._stage_bundle(MACHINE_NAME, '') is None
    assert providers.bundle_file('bin/uv').read_text() == 'left alone'


def test_apply_leaves_a_working_stack_alone_when_the_machine_is_unresolved(tmp_path, home, staging, monkeypatch) -> None:
    """An empty machine name is a box that could not say who it is, so `newest` has
    nothing to filter a peer's archive out by. Staging one on top of a stack that
    already works would install another machine's binaries."""
    monkeypatch.chdir(tmp_path)
    unpacked = staging / 'dotfiles-offline-v20260101T010000Z-box-linux-x86_64'
    (unpacked / 'bin').mkdir(parents=True)
    (unpacked / bundle.MANIFEST).write_text('binary|fd|10.2.0|fd\n')
    (unpacked / 'bin' / 'uv').write_text('mine')
    archive(tmp_path, 'dotfiles-offline-v20260810T010000Z-other-box-linux-x86_64.tar.gz', files={'bin/uv': 'theirs'})

    assert reconcile._stage_bundle('', '') is None
    assert providers.bundle_file('bin/uv').read_text() == 'mine'


def test_apply_refuses_the_archive_it_cannot_stage(tmp_path, home, staging, monkeypatch) -> None:
    """A broken bundle stops the run rather than starting one that will fail as
    every tool in the plan turning up missing."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'dotfiles-offline-v20260810T010000Z-wsl-linux-x86_64.tar.gz').write_text('not a tarball')

    assert reconcile._stage_bundle('', '') is ExitCode.ISSUE
    assert providers.staged_bundles() == ()


class TestSayingWhichBundle:
    """A run that installs from a bundle has to name the bundle.

    The already-staged branch returned early and printed nothing, so every offline
    apply after the first said not one word about where its answers came from — and
    under `--offline` the bundle *is* the upstream every currency verdict is decided
    against. A screenful of unmeasurable package items then has nothing on it naming
    the bundle they were measured against.
    """

    def test_an_already_staged_bundle_is_named_rather_than_passed_over(self, staged, capsys) -> None:
        staged.mkdir(parents=True)
        (staged / bundle.MANIFEST).write_text('binary|fd|10.2.0|fd\ncargo|ripgrep|15.2.0|rg.tar.gz\n')

        assert reconcile._stage_bundle('', '') is None

        # Newlines stripped before matching: Rich wraps a long path across lines, and
        # the assertion is about what the line says rather than where it breaks.
        said = capsys.readouterr().err.replace('\n', '')
        assert staged.name in said, 'the headline names which bundle, not the directory they sit in'
        assert 'already staged' in said
        assert '2 file(s)' in said

    def test_the_categories_are_named_because_a_bundle_of_wheels_is_not_a_bundle(self, staged, capsys) -> None:
        """`61 files` reads as a full bundle when 60 of them are the CLI's own wheels."""
        staged.mkdir(parents=True)
        (staged / bundle.MANIFEST).write_text('wheel|rich|14.0.0|rich.whl\nbinary|fd|10.2.0|fd\n')

        reconcile._stage_bundle('', '')

        assert 'binary 1, wheel 1' in capsys.readouterr().err

    def test_a_freshly_unpacked_bundle_says_which_archive_it_came_from(self, tmp_path, home, staged, monkeypatch, capsys) -> None:
        monkeypatch.chdir(tmp_path)
        archive(tmp_path, 'dotfiles-offline-v20260813-wsl-linux-x86_64.tar.gz')

        assert reconcile._stage_bundle('', '') is None

        # Whitespace-normalised: the row carries an absolute staging path, so where
        # the renderer folds the line moves with the terminal width and with the
        # length of the tmp directory pytest happened to hand out.
        said = ' '.join(capsys.readouterr().err.split())
        assert 'unpacked dotfiles-offline-v20260813-wsl-linux-x86_64.tar.gz' in said

    def test_a_newer_archive_nobody_staged_is_named_as_the_one_not_measured(self, tmp_path, home, staging, monkeypatch) -> None:
        """A read verb stages nothing, so a bundle downloaded a minute ago answers
        every version from the old one — a machine reported up to date against a
        bundle nobody meant to consult. `_stage_bundle` cannot reach this, because
        it stages the newer archive rather than warning about it."""
        monkeypatch.chdir(tmp_path)
        older = staging / 'dotfiles-offline-v20260101T010000Z-box-linux-x86_64'
        older.mkdir(parents=True)
        (older / bundle.MANIFEST).write_text('binary|fd|10.2.0|fd\n')
        newer = archive(tmp_path, 'dotfiles-offline-v20260810T010000Z-box-linux-x86_64.tar.gz')

        assert reconcile.unstaged_newer(offline_bundle.describe(), MACHINE_NAME) == newer

    def test_the_newest_archive_being_staged_leaves_nothing_to_report(self, tmp_path, home, staging, monkeypatch) -> None:
        """The steady state. Paired with a positive fact, because an assertion that
        nothing happened is satisfied by a run that never reached the comparison."""
        monkeypatch.chdir(tmp_path)
        unpacked = staging / BUNDLE
        unpacked.mkdir(parents=True)
        (unpacked / bundle.MANIFEST).write_text('binary|fd|10.2.0|fd\n')
        archive(tmp_path, f'{BUNDLE}.tar.gz')
        staged = offline_bundle.describe()

        assert staged.newest.name == BUNDLE, 'the comparison had a staged bundle to run against'
        assert reconcile.unstaged_newer(staged, MACHINE_NAME) is None

    def test_a_directory_with_no_manifest_is_named_as_the_reason(self, staged, home, capsys, monkeypatch, tmp_path) -> None:
        """Every provider reads the bundle through the manifest, so without one the
        run installs nothing from anywhere and reports each tool as its own mystery.

        "There is none" would be true and useless here: the reader has a staged
        directory in front of them and would go looking for a tarball they already
        unpacked.

        The working directory is moved because `newest` searches it, and `bundle
        create` writes its output to the checkout root — so a real build left in the
        tree makes this stage that bundle and report success. That is the whole
        failure: the test passed for as long as nobody had built one.
        """
        monkeypatch.chdir(tmp_path)
        staged.mkdir(parents=True)

        assert reconcile._stage_bundle('', '') is ExitCode.ISSUE
        said = capsys.readouterr().err.replace('\n', '')
        assert providers.MANIFEST in said
        assert staged.name in said

    def test_the_build_time_and_platform_are_read_off_the_document(self, staged) -> None:
        """`manifest.txt` carries rows and `bundle.json` carries the bundle, so a
        reader asking when it was built never parses a row and vice versa."""
        staged.mkdir(parents=True)
        (staged / bundle.MANIFEST).write_text('# Dotfiles Offline Bundle\nbinary|fd|10.2.0|fd\n')
        (staged / bundle.DOCUMENT).write_text(
            json.dumps({'version': 1, 'created': '2026-08-13T00:51:54Z', 'machine': 'wsl', 'platform': 'linux/x86_64'})
        )

        described = offline_bundle.describe()

        assert described.built == '2026-08-13T00:51:54Z'
        assert described.platform == 'linux/x86_64'
        assert described.description.machine == 'wsl'
        assert len(described.carried) == 1, 'the comment line must not be read as a row'

    def test_a_bundle_with_no_document_still_installs_from_its_rows(self, staged) -> None:
        """A bundle that cannot describe itself is still a bundle. Paired with the
        positive fact, because an empty description is also what a crash leaves."""
        staged.mkdir(parents=True)
        (staged / bundle.MANIFEST).write_text('binary|fd|10.2.0|fd\n')

        described = offline_bundle.describe()

        assert described.readable is True
        assert len(described.carried) == 1
        assert described.built == ''
        assert described.description.completeness is bundle.Completeness.FULL

    def test_an_unreadable_document_reads_as_full_rather_than_sparse(self, staged) -> None:
        """The conservative fallthrough. `FULL` makes an absent entry a reported
        gap; `SPARSE` would pass it silently, so a corrupt document must not be the
        thing that quietens a bundle."""
        staged.mkdir(parents=True)
        (staged / bundle.MANIFEST).write_text('binary|fd|10.2.0|fd\n')
        (staged / bundle.DOCUMENT).write_text('{not json')

        assert offline_bundle.describe().description.completeness is bundle.Completeness.FULL

    def test_a_completeness_this_version_has_never_heard_of_reads_as_full(self, staged) -> None:
        staged.mkdir(parents=True)
        (staged / bundle.MANIFEST).write_text('binary|fd|10.2.0|fd\n')
        (staged / bundle.DOCUMENT).write_text(json.dumps({'completeness': 'partial-ish'}))

        assert offline_bundle.describe().description.completeness is bundle.Completeness.FULL

    def test_a_sparse_document_carries_what_it_measured_and_left_out(self, staged) -> None:
        staged.mkdir(parents=True)
        (staged / bundle.MANIFEST).write_text('binary|fd|10.2.0|fd\n')
        (staged / bundle.DOCUMENT).write_text(
            json.dumps({'completeness': 'sparse', 'built_from': 'a-status.json', 'current': {'binary/bat': 'v0.26.0'}})
        )

        described = offline_bundle.describe().description

        assert described.sparse is True
        assert described.built_from == 'a-status.json'
        assert described.current == {'binary/bat': 'v0.26.0'}


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


class TestRefusingAForeignBundle:
    """A bundle built for another machine is refused before anything is moved.

    `bundle download --machine X` writes into the same cache `newest` ranks, so
    fetching another box's bundle to look at it is one command away from
    `apply --offline` staging it. That hazard did not exist while a bundle could
    only be carried in by hand, and `bundle.json` is the first thing that knows
    the target.
    """

    def built_for(self, at: Path, machine: str, name: str = BUNDLE) -> Path:
        staging = at / f'{name}-contents' / 'installers'
        staging.mkdir(parents=True)
        (staging / bundle.MANIFEST).write_text('binary|fd|10.2.0|fd\n')
        (staging / bundle.DOCUMENT).write_text(json.dumps(bundle.Description(machine=machine).as_dict()))
        tarball = at / f'{name}.tar.gz'
        with tarfile.open(tarball, 'w:gz') as packed:
            packed.add(staging, arcname='installers')
        return tarball

    def test_a_bundle_for_another_machine_is_refused_and_names_both(self, tmp_path, staging) -> None:
        tarball = self.built_for(tmp_path, 'windows-work-workstation')

        with pytest.raises(offline_bundle.StagingError) as refused:
            offline_bundle.stage(tarball, 'wsl-work-workstation', '')

        assert 'windows-work-workstation' in str(refused.value)
        assert 'wsl-work-workstation' in str(refused.value)

    def test_nothing_is_left_behind_for_the_next_run_to_pick_up(self, tmp_path, staging) -> None:
        """Refused before the move, so a rejected bundle does not become the one
        `providers.staged_bundles` reads first next time."""
        tarball = self.built_for(tmp_path, 'windows-work-workstation')

        with pytest.raises(offline_bundle.StagingError):
            offline_bundle.stage(tarball, 'wsl-work-workstation', '')

        assert providers.staged_bundles() == ()
        assert list(staging.iterdir()) == [] if staging.is_dir() else True

    def test_the_machine_it_was_built_for_stages_it(self, tmp_path, staging) -> None:
        """Paired with the refusal, which a `stage` that refused everything would
        satisfy."""
        tarball = self.built_for(tmp_path, 'wsl-work-workstation')

        landed = offline_bundle.stage(tarball, 'wsl-work-workstation', '')

        assert (landed / bundle.MANIFEST).is_file()

    def test_a_bundle_that_names_no_machine_stages(self, tmp_path, staging) -> None:
        """A bundle that does not say is not evidence of a mismatch. Refusing on
        silence would make every archive built before `bundle.json` unusable."""
        tarball = self.built_for(tmp_path, '')

        assert offline_bundle.stage(tarball, 'wsl-work-workstation', '').is_dir()

    def test_a_machine_that_cannot_name_itself_stages_anything(self, tmp_path, staging) -> None:
        """The state part way through a rebuild, and the one that most needs to
        unpack a bundle — so the check is what would stop the machine being built.
        """
        tarball = self.built_for(tmp_path, 'windows-work-workstation')

        assert offline_bundle.stage(tarball, '', '').is_dir()


class TestRefusingAPremiseFromTheOtherBox:
    """The manifest cannot answer this, which is the whole reason it exists.

    Two Macs both declare `macos-personal-workstation`, so a sparse bundle
    planned against one of them passes the machine check on the other — and its
    omissions are recorded as measured about a box that never reported.
    """

    def planned_against(self, at: Path, box: str, *, sparse: bool = True) -> Path:
        staging = at / 'contents' / 'installers'
        staging.mkdir(parents=True)
        (staging / bundle.MANIFEST).write_text('binary|fd|10.2.0|fd\n')
        described = bundle.Description(
            machine='macos-personal-workstation',
            completeness=bundle.Completeness.SPARSE if sparse else bundle.Completeness.FULL,
            built_from='a-status.json' if sparse else '',
            built_for=box,
        )
        (staging / bundle.DOCUMENT).write_text(json.dumps(described.as_dict()))
        tarball = at / f'{BUNDLE}.tar.gz'
        with tarfile.open(tarball, 'w:gz') as packed:
            packed.add(staging, arcname='installers')
        return tarball

    def test_a_bundle_planned_against_the_twin_is_refused_and_names_both(self, tmp_path, staging) -> None:
        tarball = self.planned_against(tmp_path, 'mbp')

        with pytest.raises(offline_bundle.StagingError) as refused:
            offline_bundle.stage(tarball, 'macos-personal-workstation', 'macmini')

        assert 'mbp' in str(refused.value)
        assert 'macmini' in str(refused.value)

    def test_a_bundle_planned_against_this_box_stages(self, tmp_path, staging) -> None:
        tarball = self.planned_against(tmp_path, 'macmini')

        assert offline_bundle.stage(tarball, 'macos-personal-workstation', 'macmini').is_dir()

    def test_a_full_bundle_carries_no_premise_and_is_never_refused(self, tmp_path, staging) -> None:
        """Only a sparse bundle claims anything about what the target already had,
        so only a sparse bundle can be wrong about which target."""
        tarball = self.planned_against(tmp_path, '', sparse=False)

        assert offline_bundle.stage(tarball, 'macos-personal-workstation', 'macmini').is_dir()

    def test_a_box_that_cannot_name_itself_stages_anything(self, tmp_path, staging) -> None:
        """Same terms as the machine check above: a half-built box has to be able
        to unpack a bundle, or the guard is what stops the rebuild."""
        tarball = self.planned_against(tmp_path, 'mbp')

        assert offline_bundle.stage(tarball, 'macos-personal-workstation', '').is_dir()

    def test_the_resolver_answers_empty_rather_than_raising_on_a_bare_machine(self, home, monkeypatch) -> None:
        """What feeds the case above. `commands.resolved` refuses a machine nothing
        names, and that refusal must not reach the caller as a failed stage.

        `$MACHINE` and `~/.env` both, because the resolver reads the second where
        the first is unset — and a test that blanked only the variable would pass
        by reading whatever machine the suite happened to run on.
        """
        monkeypatch.delenv('MACHINE', raising=False)
        assert not (home / '.env').exists()

        assert offline_bundle.target() == ''
