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

import datetime as dt
import json
import tarfile
from collections.abc import Callable
from pathlib import Path

import pytest
import typer
from relay import declare
from relay import deny_listing
from relay import install_relay

from dotfiles import offline_bundle
from dotfiles import paths
from dotfiles import publishing as status_commands
from dotfiles import remote as transport
from dotfiles.commands import staging
from dotfiles.providers import bundle
from dotfiles.vocabulary import RESOURCES
from dotfiles.vocabulary import ExitCode
from matrix.harness import DECLARES_LAZYGIT
from matrix.harness import LAZYGIT
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

    def test_a_landed_upload_stays_converged_when_the_retention_nudge_cannot_list(
        self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]
    ) -> None:
        """Nothing a verb does after its effect has landed may change its exit
        code. The nudge ran after both pushes and after `success` printed, so a
        refused listing reported a completed upload as a failure and invited a
        caller to send it again."""
        built = archive(sandbox.root, NEWEST)
        deny_listing(server)

        ran = cli('bundle', 'upload', str(built), catch_exceptions=True)

        assert ran.exit_code == ExitCode.CONVERGED
        assert (shelf(server) / f'{NEWEST}.tar.gz').is_file()

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

    def test_a_downloaded_archive_keeps_its_record_beside_it(self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]) -> None:
        """`paths.archive_dir` already said this happens and nothing wrote one, so
        a machine that downloaded today had no digest to re-check next month and
        `prune` unlinked a path that never existed."""
        published(server, NEWEST)

        ran = cli('bundle', 'download', '--yes')

        assert ran.exit_code == ExitCode.CONVERGED
        sidecar = paths.archive_dir() / f'{NEWEST}.tar.gz{offline_bundle.SIDECAR_SUFFIX}'
        assert sidecar.is_file()
        assert json.loads(sidecar.read_text())['sha256']


class TestReportingTheRemoteSettings:
    """Every `[remote]` setting says which layer decided it.

    standards/configuration.md § "A resolved value reports which layer set it" —
    the failure is a plausible value rather than a wrong one. One of these governs
    deletion from a server and another decides whether a document leaves the
    machine unasked, and both defaulted silently beside register rows that all
    carry `from {source}`.
    """

    def test_a_declared_limit_names_the_table_it_came_from(self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]) -> None:
        declare(sandbox.config, extra='keep_bundles = 5\n')

        ran = cli('config', 'show')

        assert 'from remote.keep_bundles' in ran.stdout

    def test_the_same_number_undeclared_names_the_default(self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]) -> None:
        """Paired with the test above and the whole reason provenance is carried
        rather than compared: 5 is also `DEFAULT_KEEP`, so the value cannot say."""
        declare(sandbox.config)

        ran = cli('config', 'show')

        assert 'this tool’s default' in ran.stdout
        assert 'from remote.keep_bundles' not in ran.stdout

    def test_both_automatic_paths_are_on_the_human_screen(self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]) -> None:
        """They reached `--json` alone, and the second decides whether a status
        document leaves the machine without anyone asking."""
        declare(sandbox.config, extra='publish_status_after_offline_apply = true\n')

        ran = cli('config', 'show')

        assert 'fetch_bundle_when_none_is_staged off' in ran.stdout
        assert 'publish_status_after_offline_apply on' in ran.stdout
        assert 'from remote.publish_status_after_offline_apply' in ran.stdout

    def test_the_machine_door_carries_the_provenance_too(self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]) -> None:
        """A caller reading the JSON otherwise gets exactly the plausible value the
        rendered line was added to prevent."""
        declare(sandbox.config, extra='keep_bundles = 5\n')

        ran = cli('config', 'show', '--json')

        assert ran.document['remote']['from_table'] == ['keep_bundles', 'root', 'transport']


class TestStaging:
    def test_a_named_path_that_is_not_there_is_a_usage_error(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        """A typo is the caller's mistake, which is USAGE. It reached `stage` and
        came back ISSUE, so a mistyped path read to a caller as a machine fault."""
        ran = cli('bundle', 'stage', '/nope/not-here.tar.gz', catch_exceptions=True)

        assert ran.exit_code == ExitCode.USAGE
        assert 'not-here.tar.gz' in ran.stderr


class TestPruning:
    def test_local_archives_and_staged_bundles_are_swept_to_the_same_depth(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        cache = sandbox.cache / 'dotfiles' / 'bundles'
        cache.mkdir(parents=True)
        for name in (OLDER, NEWEST):
            (cache / f'{name}.tar.gz').write_text('an archive')
            (sandbox.staging / name).mkdir(parents=True)
            (sandbox.staging / name / bundle.MANIFEST).write_text('binary|fd|10.2.0|fd\n')

        ran = cli('bundle', 'prune', '--keep', '1', '--yes')

        assert ran.exit_code == ExitCode.CONVERGED
        assert (cache / f'{NEWEST}.tar.gz').is_file()
        assert not (cache / f'{OLDER}.tar.gz').exists()
        assert (sandbox.staging / NEWEST).is_dir()
        assert not (sandbox.staging / OLDER).exists()

    def test_a_limit_below_one_is_refused_rather_than_clamped(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        """A flag the run cannot honour says so. Clamped in silence, `--keep 0`
        swept to one bundle while the caller believed it had asked for none."""
        (sandbox.staging / NEWEST).mkdir(parents=True)
        (sandbox.staging / NEWEST / bundle.MANIFEST).write_text('binary|fd|10.2.0|fd\n')

        ran = cli('bundle', 'prune', '--keep', '0', '--yes')

        assert ran.exit_code == ExitCode.USAGE
        assert 'the floor is 1' in ran.stderr
        assert (sandbox.staging / NEWEST).is_dir()

    def test_the_summary_reports_the_limit_that_was_applied(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        """Through the machine door rather than out of the sentence. The number
        only existed inside rendered prose, so the test that checked it was
        parsing the report rather than reading the value."""
        (sandbox.staging / NEWEST).mkdir(parents=True)
        (sandbox.staging / NEWEST / bundle.MANIFEST).write_text('binary|fd|10.2.0|fd\n')

        ran = cli('bundle', 'prune', '--keep', '1', '--yes', '--json')

        assert ran.exit_code == ExitCode.CONVERGED
        assert ran.document['kept'] == 1
        assert ran.document['removed'] == []

    def test_the_newest_survives_a_limit_of_zero(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        """A machine with nothing staged cannot converge offline at all, so a limit
        that emptied the staging directory would take away its only way to install
        anything."""
        (sandbox.staging / NEWEST).mkdir(parents=True)
        (sandbox.staging / NEWEST / bundle.MANIFEST).write_text('binary|fd|10.2.0|fd\n')

        cli('bundle', 'prune', '--keep', '0', '--yes')

        assert (sandbox.staging / NEWEST).is_dir()

    def test_another_machine_s_bundles_do_not_age_out_this_one_s(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        """Retention counts per machine. `bundle download --machine X` writes a
        peer's archive into this cache, so counting them together lets a few
        downloads for a peer take the only bundle on a box that cannot re-fetch."""
        cache = sandbox.cache / 'dotfiles' / 'bundles'
        cache.mkdir(parents=True)
        peers = [f'dotfiles-offline-v2026090{n}T120000Z-other-linux-x86_64' for n in range(1, 5)]
        for name in [OLDER, *peers]:
            (cache / f'{name}.tar.gz').write_text('an archive')

        ran = cli('bundle', 'prune', '--keep', '1', '--yes')

        assert ran.exit_code == ExitCode.CONVERGED
        assert (cache / f'{OLDER}.tar.gz').is_file(), 'this machine had one bundle and it was swept for a peer'
        assert (cache / f'{peers[-1]}.tar.gz').is_file(), "the peer's newest is kept too"
        assert not (cache / f'{peers[0]}.tar.gz').exists()

    def test_a_local_sweep_without_a_terminal_refuses_rather_than_deleting(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        """What is here is what a firewalled box cannot download again, and a
        machine with no `[remote]` declared has no `bundle download` to recover
        with. The remote sweep already had this pair."""
        cache = sandbox.cache / 'dotfiles' / 'bundles'
        cache.mkdir(parents=True)
        for name in (OLDER, NEWEST):
            (cache / f'{name}.tar.gz').write_text('an archive')

        ran = cli('bundle', 'prune', '--keep', '1', '--no-input')

        assert ran.exit_code == ExitCode.USAGE
        assert (cache / f'{OLDER}.tar.gz').is_file()

    def test_the_remote_is_left_alone_unless_it_is_asked_for(self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]) -> None:
        """Deleting from a server is the one thing here another machine observes,
        and the machine running this is not always the one a bundle was built for."""
        published(server, OLDER)
        published(server, NEWEST)

        cli('bundle', 'prune', '--keep', '1', '--yes')

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


class TestTheAutomaticPaths:
    """Both are off unless the machine turned them on, and that is the assertion.

    The box this exists for sits on an employer network where the concern is
    monitoring rather than capability, so a converge that reaches a server unasked
    is a change in posture. The loop is worth automating and is not worth
    automating quietly.
    """

    def staged_nothing(self, sandbox: Sandbox) -> None:
        sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)

    def test_an_offline_apply_fetches_nothing_by_default(self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]) -> None:
        """Paired with the exit code and a positive fact: it refused for want of a
        bundle, and the cache it would have filled is empty."""
        self.staged_nothing(sandbox)
        published(server, NEWEST)

        ran = cli('apply', '--offline', catch_exceptions=True)

        assert ran.exit_code == ExitCode.ISSUE
        assert not (sandbox.cache / 'dotfiles' / 'bundles').exists()

    def test_it_fetches_where_the_machine_asked_for_that(self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]) -> None:
        self.staged_nothing(sandbox)
        published(server, NEWEST)
        declare(sandbox.config, extra='fetch_bundle_when_none_is_staged = true\n')

        cli('apply', '--offline', catch_exceptions=True)

        assert (sandbox.cache / 'dotfiles' / 'bundles' / f'{NEWEST}.tar.gz').is_file()
        assert (sandbox.staging / NEWEST / bundle.MANIFEST).is_file()

    def test_a_remote_that_will_not_answer_still_ends_on_the_missing_bundle(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        """ "The remote would not answer" is a worse thing to end an apply on than
        "there is no bundle" — the second is what the caller can act on, and it is
        true either way."""
        self.staged_nothing(sandbox)
        declare(sandbox.config, program='nothing-installed-here', extra='fetch_bundle_when_none_is_staged = true\n')

        ran = cli('apply', '--offline', catch_exceptions=True)

        assert ran.exit_code == ExitCode.ISSUE
        assert 'needs a staged bundle' in ran.stderr

    def test_an_offline_apply_publishes_nothing_by_default(self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]) -> None:
        """Paired with the exit code and a positive fact. An apply that died while
        staging satisfied the negative on its own, and this is the only thing
        pinning the publish half of "both automatic paths default off"."""
        sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)
        sandbox.stage_bundle({'lazygit': '0.45.0'})
        sandbox.installed('lazygit', '0.45.0')

        ran = cli('apply', '--offline', catch_exceptions=True)

        assert ran.exit_code == ExitCode.CONVERGED
        assert not (server / 'artefacts' / 'status').exists()

    def test_it_publishes_where_the_machine_asked_for_that(self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]) -> None:
        sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)
        sandbox.stage_bundle({'lazygit': '0.45.0'})
        sandbox.installed('lazygit', '0.45.0')
        declare(sandbox.config, extra='publish_status_after_offline_apply = true\n')

        ran = cli('apply', '--offline', catch_exceptions=True)

        assert ran.exit_code == ExitCode.CONVERGED
        assert len(list((server / 'artefacts' / 'status' / MACHINE).iterdir())) == 1

    def test_a_failed_apply_publishes_nothing(self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]) -> None:
        """A document from a failed apply describes a machine part way through
        being something else, which is worse than no document at all."""
        self.staged_nothing(sandbox)
        declare(sandbox.config, extra='publish_status_after_offline_apply = true\n')

        ran = cli('apply', '--offline', catch_exceptions=True)

        assert ran.exit_code == ExitCode.ISSUE
        assert not (server / 'artefacts' / 'status').exists()

    def test_an_online_apply_never_publishes(self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]) -> None:
        """The document exists to plan an offline bundle. A machine that reaches the
        network needs none, and publishing from one puts a second machine's rows on
        a shelf the builder reads for the first.

        Narrowed to `symlinks`, which reaches no network. An online `apply`
        resolves with `refresh=True` and everything else would ask GitHub for a
        version, which the matrix guard refuses. The run still takes the whole path
        down to the gate, which is where the publish would happen.
        """
        sandbox.declare(packages=LAZYGIT, manifest=DECLARES_LAZYGIT)
        declare(sandbox.config, extra='publish_status_after_offline_apply = true\n')
        skipped = [flag for resource in RESOURCES if resource != 'symlinks' for flag in ('--skip', resource)]

        ran = cli('apply', *skipped, catch_exceptions=True)

        assert ran.exit_code == ExitCode.CONVERGED
        assert not (server / 'artefacts' / 'status').exists()


class TestResolvingLatestForASparseBuild:
    """`--against latest` reaches the remote, and that half is testable on its own.

    The build it feeds cannot run here — it downloads every installer the manifest
    names, which the matrix guard refuses — so what is asserted is the resolution:
    the newest status for a machine lands in the cache and its path is what the
    builder is handed. `tests/install/test_create_bundle.py` owns the other half.
    """

    def published(self, server: Path, stamp: str, *, wrote: str = 'abcd1234') -> Path:
        shelf = server / 'artefacts' / 'status' / MACHINE
        shelf.mkdir(parents=True, exist_ok=True)
        written = shelf / f'{status_commands.PREFIX}{stamp}-{MACHINE}-{wrote}.json'
        written.write_text(json.dumps({'version': 2, 'machine': MACHINE, 'scope': ['packages'], 'resources': []}))
        return written

    def test_two_machines_sharing_a_manifest_make_latest_a_usage_error(
        self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]
    ) -> None:
        """`macos-personal-workstation` is both Macs, which is why a status
        filename carries a hostname digest at all. Nothing here can tell which one
        a bundle is for, so picking the most recent diffs one Mac's plan against
        the other's installed set and reports the result as measured — the outcome
        the `machine` guard exists to prevent and cannot see, because both
        documents name the same manifest."""
        self.published(server, '20260101T010000Z', wrote='abcd1234')
        self.published(server, '20260909T120000Z', wrote='99887766')

        with pytest.raises(typer.BadParameter) as refused:
            staging._status_for('latest', MACHINE)

        assert '2 machines share' in str(refused.value)
        assert 'status download' in str(refused.value)

    def test_the_refusal_names_every_candidate_by_the_box_that_wrote_it(
        self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]
    ) -> None:
        """It pasted `--status {listed[0]}`, which is the newest by timestamp
        alone — so the remedy walked straight into the ambiguity it had just
        declined to resolve, on a path with no guard behind it."""
        self.published(server, '20260101T010000Z', wrote='abcd1234')
        self.published(server, '20260909T120000Z', wrote='99887766')

        with pytest.raises(typer.BadParameter) as refused:
            staging._status_for('latest', MACHINE)

        said = str(refused.value)
        assert 'abcd1234' in said
        assert '99887766' in said
        assert '--status NAME' in said

    def test_a_refused_listing_stops_rather_than_building_a_full_bundle(
        self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]
    ) -> None:
        """The probe answers and the listing does not, which is the case a boolean
        `exists` read as an empty shelf. Falling back there spends half an hour of
        downloads on a run where a perfectly good status was on the server."""
        self.published(server, '20260909T120000Z')
        deny_listing(server)

        with pytest.raises(transport.RemoteError):
            staging._status_for('latest', MACHINE)

    def test_one_machine_publishing_twice_is_not_ambiguous(self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]) -> None:
        """Paired with the refusal above, because a check that fired on every
        second publish would make the ordinary case unusable."""
        self.published(server, '20260101T010000Z')
        newest = self.published(server, '20260909T120000Z')

        assert staging._status_for('latest', MACHINE) is not None
        assert newest.name.endswith('.json')

    def test_the_newest_status_lands_in_the_cache_and_is_what_the_build_is_handed(
        self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]
    ) -> None:
        self.published(server, '20260101T010000Z')
        newest = self.published(server, '20260909T120000Z')

        found = staging._status_for('latest', MACHINE)

        assert found is not None
        assert found.name == newest.name
        assert found.parent == paths.status_cache()
        assert json.loads(found.read_text())['machine'] == MACHINE

    def test_a_path_is_taken_as_written(self, sandbox: Sandbox, server: Path, tmp_path: Path) -> None:
        """Everything that is not the literal `latest` is a file, so a machine with
        a status already on disk never reaches the remote for it."""
        named = tmp_path / 'a-status.json'
        named.write_text('{}')

        assert staging._status_for(str(named), MACHINE) == named

    def test_a_path_that_is_not_a_file_is_a_usage_error_naming_the_fetch(self, sandbox: Sandbox, server: Path, tmp_path: Path) -> None:
        with pytest.raises(typer.BadParameter, match='status download'):
            staging._status_for(str(tmp_path / 'never-written.json'), MACHINE)

    def test_an_empty_shelf_builds_a_full_bundle_and_says_so(self, sandbox: Sandbox, server: Path, capsys: pytest.CaptureFixture) -> None:
        """`latest` means "whatever the remote has", and nothing is a legitimate
        answer — it is the state of every machine before its first status is
        published, which is exactly when somebody runs this for the first time.

        What makes the fallback safe is that it is announced and the artefact says
        it for itself: no `-sparse` in the name and `completeness: full` inside.
        The failure the feature exists to avoid is a bundle carrying everything
        while reporting itself sparse, and this path cannot produce one.
        """
        assert staging._status_for('latest', MACHINE) is None

        said = capsys.readouterr().err.replace('\n', '')
        assert 'full bundle' in said
        assert 'status upload' in said

    def test_a_transport_that_will_not_answer_still_refuses(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        """A different fact from an empty shelf. Falling back here would build a
        full bundle on a run where a perfectly good status was sitting on a server
        nobody could reach — half an hour of downloads for a broken remote."""
        declare(sandbox.config, program='nothing-installed-here')

        with pytest.raises(transport.RemoteError):
            staging._status_for('latest', MACHINE)

    def test_no_status_is_fetched_for_a_full_build(self, sandbox: Sandbox, server: Path) -> None:
        """Paired with the cases above: `--against` absent must reach nothing at
        all, which a remote that answered would otherwise hide."""
        self.published(server, '20260909T120000Z')

        assert staging._status_for(None, MACHINE) is None
        assert not paths.status_cache().exists()


class TestReportingHowOldABundleIs:
    """`_age_of` is the first line of the `bundle download` confirmation, so it is
    the one fact that prompt exists to convey."""

    def test_a_future_stamp_reads_as_no_time_at_all(self) -> None:
        """`timedelta` normalises a negative by borrowing, so five minutes ahead is
        `days=-1, seconds=86100` and used to read as 23 hours ago. The builder
        stamps the name and the offline box renders it, so skew between two clocks
        is ordinary — and it misreported in the direction that argues against
        downloading."""
        assert staging._elapsed(dt.timedelta(minutes=-5)) == '0 minute(s)'

    def test_an_ordinary_age_is_unchanged(self) -> None:
        assert staging._elapsed(dt.timedelta(days=3)) == '3 day(s)'
        assert staging._elapsed(dt.timedelta(hours=5)) == '5 hour(s)'


SPARSE_NEWEST = 'dotfiles-offline-v20260909T120000Z-box-linux-x86_64-sparse'


class TestPinningTheFullBase:
    """A sparse bundle falls through to the full one beneath it, and retention
    could not see that: a name sorts as its stamp does, so the base is always the
    oldest and always the first thing a sweep takes."""

    def staged(self, sandbox: Sandbox, *names: str) -> None:
        for name in names:
            (sandbox.staging / name).mkdir(parents=True)
            (sandbox.staging / name / bundle.MANIFEST).write_text('binary|fd|10.2.0|fd\n')

    def test_the_newest_full_bundle_survives_a_limit_that_would_take_it(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        """Every tool the sparse bundle deliberately omitted has no other source,
        on the box that cannot fetch one."""
        self.staged(sandbox, OLDER, SPARSE_NEWEST)

        ran = cli('bundle', 'prune', '--keep', '1', '--yes')

        assert ran.exit_code == ExitCode.CONVERGED
        assert (sandbox.staging / OLDER).is_dir()
        assert (sandbox.staging / SPARSE_NEWEST).is_dir()

    def test_the_pin_is_named_rather_than_silent(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        """`prune --keep 1` on a stack of two keeping two reads as a broken limit
        without a word about why."""
        self.staged(sandbox, OLDER, SPARSE_NEWEST)

        ran = cli('bundle', 'prune', '--keep', '1', '--yes')
        machine_readable = cli('bundle', 'prune', '--keep', '1', '--yes', '--json')

        assert 'pinned' in ran.stdout + ran.stderr
        assert machine_readable.document['pinned'] == [OLDER]

    def test_a_newer_full_bundle_unpins_the_older_one(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        """What bounds the stack. The pin moves rather than accumulating, so a
        machine holds one base and the limit's worth of everything else."""
        self.staged(sandbox, OLDER, NEWEST)

        cli('bundle', 'prune', '--keep', '1', '--yes')

        assert (sandbox.staging / NEWEST).is_dir()
        assert not (sandbox.staging / OLDER).exists()

    def test_a_stack_of_only_sparse_bundles_sweeps_as_before(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        """Nothing is pinned where there is no base. A stack with none is already
        broken and holding a member back cannot repair it."""
        older_sparse = f'{OLDER}-sparse'
        self.staged(sandbox, older_sparse, SPARSE_NEWEST)

        cli('bundle', 'prune', '--keep', '1', '--yes')

        assert (sandbox.staging / SPARSE_NEWEST).is_dir()
        assert not (sandbox.staging / older_sparse).exists()
