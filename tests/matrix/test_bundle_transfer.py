"""Moving a bundle between two machines, driven through the CLI.

The whole loop against a fake remote: build an archive, upload it with the record
beside it, list what is there, fetch it back, verify the digest, and sweep what is
past the limit. Nothing under `src/` is patched — the transport is a real
executable on the sandbox's PATH, declared in a real `config.toml`, serving a real
directory.

`tests/install/test_remote.py` owns the layer below this: what a `[remote]` table
means and what one transport invocation does. This owns what the verbs do with it.
"""

from __future__ import annotations

import json
import tarfile
from collections.abc import Callable
from pathlib import Path

import pytest
from relay import declare
from relay import install_relay

from dotfiles import offline_bundle
from dotfiles.providers import bundle
from dotfiles.vocabulary import ExitCode
from matrix.harness import Invocation
from matrix.harness import Sandbox

MACHINE = 'box'
NEWEST = 'dotfiles-offline-v20260909T120000Z-box-linux-x86_64'
OLDER = 'dotfiles-offline-v20260101T010000Z-box-linux-x86_64'
SHELF = '/artefacts/bundles/box'


@pytest.fixture
def server(sandbox: Sandbox) -> Path:
    """The directory the fake transport treats as the remote, with a shelf on it."""
    root = sandbox.root / 'server'
    (root / 'artefacts' / 'bundles' / MACHINE).mkdir(parents=True)
    install_relay(sandbox.bin, root)
    declare(sandbox.config)
    return root


def shelf(server: Path) -> Path:
    return server / 'artefacts' / 'bundles' / MACHINE


def archive(at: Path, name: str, *, machine: str = MACHINE, sparse: bool = False, files: dict[str, str] | None = None) -> Path:
    """A tarball shaped the way `bundle create` shapes one."""
    staging = at / f'{name}-contents' / 'installers'
    staging.mkdir(parents=True)
    (staging / bundle.MANIFEST).write_text('binary|fd|10.2.0|fd\n')
    described = bundle.Description(
        created='2026-09-09T12:00:00Z',
        machine=machine,
        platform='linux/x86_64',
        completeness=bundle.Completeness.SPARSE if sparse else bundle.Completeness.FULL,
        built_from='a-status.json' if sparse else '',
        current={'binary/bat': 'v0.26.0'} if sparse else {},
    )
    (staging / bundle.DOCUMENT).write_text(json.dumps(described.as_dict()))
    for relative, content in (files or {}).items():
        (staging / relative).parent.mkdir(parents=True, exist_ok=True)
        (staging / relative).write_text(content)

    tarball = at / f'{name}.tar.gz'
    with tarfile.open(tarball, 'w:gz') as packed:
        packed.add(staging, arcname='installers')
    return tarball


def published(server: Path, name: str, **kwargs: object) -> Path:
    """An archive already on the remote, with the record `upload` would have written."""
    built = archive(server.parent / 'built', name, **kwargs)  # type: ignore[arg-type]
    landed = shelf(server) / built.name
    landed.write_bytes(built.read_bytes())
    record = offline_bundle.described_record(landed)
    (shelf(server) / f'{built.name}{offline_bundle.SIDECAR_SUFFIX}').write_text(json.dumps(record.as_dict()))
    return landed


class TestUploading:
    def test_the_archive_and_its_record_both_land_on_the_machines_shelf(
        self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]
    ) -> None:
        built = archive(sandbox.root, NEWEST)

        ran = cli('bundle', 'upload', str(built))

        assert ran.exit_code == ExitCode.CONVERGED
        assert (shelf(server) / f'{NEWEST}.tar.gz').is_file()
        assert (shelf(server) / f'{NEWEST}.tar.gz.json').is_file()

    def test_the_record_carries_the_digest_and_what_the_bundle_says_it_is(
        self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]
    ) -> None:
        """It is fetched before the archive, so it has to answer everything a
        person decides from without the archive being there."""
        built = archive(sandbox.root, NEWEST, sparse=True)

        cli('bundle', 'upload', str(built))
        record = json.loads((shelf(server) / f'{NEWEST}.tar.gz.json').read_text())

        assert record['sha256']
        assert record['size'] == built.stat().st_size
        assert record['bundle']['machine'] == MACHINE
        assert record['bundle']['completeness'] == 'sparse'

    def test_the_shelf_is_keyed_on_the_manifest_the_bundle_names(
        self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]
    ) -> None:
        """Never on the hostname. `paths.machine_id()` is an employer asset tag on
        the one machine this exists for, and it has no business on a shelf beside
        personal artefacts."""
        built = archive(sandbox.root, 'dotfiles-offline-v20260909T120000Z-elsewhere-linux-x86_64', machine='wsl-work-workstation')

        cli('bundle', 'upload', str(built))

        assert (server / 'artefacts' / 'bundles' / 'wsl-work-workstation').is_dir()

    def test_an_archive_that_names_no_machine_is_refused_before_anything_moves(
        self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]
    ) -> None:
        """Paired with the exit code and a positive fact: nothing landed, and the
        shelf that does exist is still empty."""
        staging = sandbox.root / 'nameless' / 'installers'
        staging.mkdir(parents=True)
        (staging / bundle.MANIFEST).write_text('binary|fd|10.2.0|fd\n')
        tarball = sandbox.root / f'{NEWEST}.tar.gz'
        with tarfile.open(tarball, 'w:gz') as packed:
            packed.add(staging, arcname='installers')

        ran = cli('bundle', 'upload', str(tarball), catch_exceptions=True)

        assert ran.exit_code == ExitCode.ISSUE
        assert 'does not say which machine' in ran.stderr
        assert list(shelf(server).iterdir()) == []

    def test_an_unconfigured_machine_refuses_and_names_the_command_that_configures_it(
        self, sandbox: Sandbox, cli: Callable[..., Invocation]
    ) -> None:
        built = archive(sandbox.root, NEWEST)

        ran = cli('bundle', 'upload', str(built), catch_exceptions=True)

        assert ran.exit_code == ExitCode.ISSUE
        assert 'dotfiles config show' in ran.stderr


class TestListing:
    def test_the_newest_is_first_and_records_are_not_rows(self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]) -> None:
        published(server, OLDER)
        published(server, NEWEST)

        ran = cli('bundle', 'list', '--json')

        assert ran.document['bundles'] == [f'{NEWEST}.tar.gz', f'{OLDER}.tar.gz']
        assert ran.document['machine'] == MACHINE

    def test_a_machine_with_no_shelf_lists_nothing_rather_than_failing(
        self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]
    ) -> None:
        """An absent shelf is an ordinary state — nobody has built for that machine
        yet — and the transport's own "not a directory" is not a finding about it."""
        ran = cli('bundle', 'list', '--machine', 'never-built-for', '--json')

        assert ran.exit_code == ExitCode.CONVERGED
        assert ran.document['bundles'] == []

    def test_the_human_listing_renders_and_names_each_bundles_age(
        self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]
    ) -> None:
        """The default path, which `--json` cannot stand in for.

        Every other case here reads the document, and the terminal render shipped
        a KeyError against `VERDICT_MARKS` that all of them passed straight over —
        the marks are keyed on a verdict word and `matched` is a change label.
        `standards/testing.md` § "Never assert on rendered output" exempts nothing
        from being *run*; what it forbids is asserting the wording, so this asserts
        the exit code and one fact the row must carry.
        """
        published(server, NEWEST)

        ran = cli('bundle', 'list')

        assert ran.exit_code == ExitCode.CONVERGED
        assert NEWEST in ran.stderr.replace('\n', '')
        assert 'ago' in ran.stderr

    def test_the_limit_narrows_the_rows_and_the_total_still_counts_them_all(
        self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]
    ) -> None:
        published(server, OLDER)
        published(server, NEWEST)

        ran = cli('bundle', 'list', '--limit', '1', '--json')

        assert ran.document['bundles'] == [f'{NEWEST}.tar.gz']
        assert ran.document['total'] == 2


class TestDownloading:
    def test_the_newest_arrives_in_the_cache_and_is_not_staged(
        self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]
    ) -> None:
        """Two acts, kept apart, so a download can be repeated without disturbing
        what is already staged."""
        published(server, NEWEST)

        ran = cli('bundle', 'download', '--yes')

        assert ran.exit_code == ExitCode.CONVERGED
        assert (sandbox.cache / 'dotfiles' / 'bundles' / f'{NEWEST}.tar.gz').is_file()
        assert not sandbox.staging.exists() or list(sandbox.staging.iterdir()) == []

    def test_a_named_bundle_is_fetched_instead_of_the_newest(self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]) -> None:
        published(server, OLDER)
        published(server, NEWEST)

        cli('bundle', 'download', '--bundle', f'{OLDER}.tar.gz', '--yes')

        assert (sandbox.cache / 'dotfiles' / 'bundles' / f'{OLDER}.tar.gz').is_file()

    def test_a_name_the_remote_does_not_hold_is_a_usage_error(self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]) -> None:
        published(server, NEWEST)

        ran = cli('bundle', 'download', '--bundle', 'not-on-the-shelf.tar.gz', '--yes', catch_exceptions=True)

        assert ran.exit_code == ExitCode.USAGE

    def test_an_empty_shelf_refuses_rather_than_succeeding_into_silence(
        self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]
    ) -> None:
        ran = cli('bundle', 'download', '--yes', catch_exceptions=True)

        assert ran.exit_code == ExitCode.ISSUE
        assert 'holds no bundle' in ran.stderr

    def test_an_archive_that_does_not_match_its_record_is_refused_and_deleted(
        self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]
    ) -> None:
        """Deleted rather than left behind, because `newest` ranks by name — a
        corrupt archive would be the one every later run picks up, and it would win
        against the good bundle it was meant to replace.
        """
        published(server, NEWEST)
        (shelf(server) / f'{NEWEST}.tar.gz').write_bytes(b'truncated on the way out')

        ran = cli('bundle', 'download', '--yes', catch_exceptions=True)

        assert ran.exit_code == ExitCode.ISSUE
        assert 'did not arrive whole' in ran.stderr
        assert not (sandbox.cache / 'dotfiles' / 'bundles' / f'{NEWEST}.tar.gz').exists()

    def test_a_bundle_with_no_record_still_downloads_and_says_it_is_unverified(
        self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]
    ) -> None:
        """One uploaded before records existed, or whose record upload failed, is
        still installable. What it costs is the digest, and that is said rather than
        passed over."""
        published(server, NEWEST)
        (shelf(server) / f'{NEWEST}.tar.gz.json').unlink()

        ran = cli('bundle', 'download', '--yes')

        assert ran.exit_code == ExitCode.CONVERGED
        assert 'nothing here can verify' in ran.stderr
        assert (sandbox.cache / 'dotfiles' / 'bundles' / f'{NEWEST}.tar.gz').is_file()

    def test_without_a_terminal_the_flag_that_would_have_answered_is_named(
        self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]
    ) -> None:
        """Never blocks: `standards/cli-design.md` § "Non-interactive by default"."""
        published(server, NEWEST)

        ran = cli('bundle', 'download', '--no-input', catch_exceptions=True)

        assert ran.exit_code == ExitCode.USAGE
        assert '--yes' in ran.stderr
        assert not (sandbox.cache / 'dotfiles' / 'bundles' / f'{NEWEST}.tar.gz').exists()

    def test_the_confirmation_names_the_bundle_and_when_it_was_built(
        self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]
    ) -> None:
        published(server, NEWEST, sparse=True)

        ran = cli('bundle', 'download', '--yes')
        said = ran.stderr.replace('\n', '')

        assert NEWEST in said
        assert 'built' in said
        assert 'sparse' in said


class TestPruning:
    def test_local_archives_and_staged_bundles_are_swept_to_the_same_depth(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        cache = sandbox.cache / 'dotfiles' / 'bundles'
        cache.mkdir(parents=True)
        for name in (OLDER, NEWEST):
            (cache / f'{name}.tar.gz').write_text('an archive')
            (sandbox.staging / name).mkdir(parents=True)
            (sandbox.staging / name / bundle.MANIFEST).write_text('binary|fd|10.2.0|fd\n')

        ran = cli('bundle', 'prune', '--keep', '1')

        assert ran.exit_code == ExitCode.CONVERGED
        assert (cache / f'{NEWEST}.tar.gz').is_file()
        assert not (cache / f'{OLDER}.tar.gz').exists()
        assert (sandbox.staging / NEWEST).is_dir()
        assert not (sandbox.staging / OLDER).exists()

    def test_the_newest_survives_a_limit_of_zero(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        """A machine with nothing staged cannot converge offline at all, so a limit
        that emptied the staging directory would take away its only way to install
        anything."""
        (sandbox.staging / NEWEST).mkdir(parents=True)
        (sandbox.staging / NEWEST / bundle.MANIFEST).write_text('binary|fd|10.2.0|fd\n')

        cli('bundle', 'prune', '--keep', '0')

        assert (sandbox.staging / NEWEST).is_dir()

    def test_the_remote_is_left_alone_unless_it_is_asked_for(self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]) -> None:
        """Deleting from a server is the one thing here another machine observes,
        and the machine running this is not always the one a bundle was built for."""
        published(server, OLDER)
        published(server, NEWEST)

        cli('bundle', 'prune', '--keep', '1')

        assert (shelf(server) / f'{OLDER}.tar.gz').is_file()

    def test_the_remote_sweep_removes_the_record_with_the_archive(
        self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]
    ) -> None:
        """A record whose archive is gone is a row `list` shows and `download`
        fails on, which reads as a broken remote."""
        published(server, OLDER)
        published(server, NEWEST)

        ran = cli('bundle', 'prune', '--keep', '1', '--remote', '--yes')

        assert ran.exit_code == ExitCode.CONVERGED
        assert not (shelf(server) / f'{OLDER}.tar.gz').exists()
        assert not (shelf(server) / f'{OLDER}.tar.gz.json').exists()
        assert (shelf(server) / f'{NEWEST}.tar.gz').is_file()

    def test_a_remote_sweep_without_a_terminal_names_the_flag(self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]) -> None:
        published(server, OLDER)
        published(server, NEWEST)

        ran = cli('bundle', 'prune', '--keep', '1', '--remote', '--no-input', catch_exceptions=True)

        assert ran.exit_code == ExitCode.USAGE
        assert (shelf(server) / f'{OLDER}.tar.gz').is_file()


def test_an_uploaded_bundle_comes_back_byte_for_byte(sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]) -> None:
    """The round trip, which neither half asserts on its own.

    `standards/testing.md` § "A green unit suite is not evidence the feature
    works": a push and a pull that each pass against their own fixture can still
    disagree about the name, the shelf or the record between them.
    """
    built = archive(sandbox.root, NEWEST, files={'binaries/fd': 'the payload'})

    cli('bundle', 'upload', str(built))
    cli('bundle', 'download', '--yes')
    fetched = sandbox.cache / 'dotfiles' / 'bundles' / f'{NEWEST}.tar.gz'

    assert fetched.read_bytes() == built.read_bytes()
    assert offline_bundle.peek(fetched).machine == MACHINE
