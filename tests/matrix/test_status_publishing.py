"""What leaves this machine, and the gate that will not let anything else.

The document that travels is the one narrow exception to "nothing written at work
travels home", so what it may carry is asserted rather than reviewed. Two
independent guards, and both are tested here: the walk is composed over an
allowlist of resources, and the serialized bytes are read for the two names that
identify this box before any of them move.

Driven through the CLI against the real walk and a fake remote, so what is
asserted is what would land on a server.
"""

from __future__ import annotations

import getpass
import json
from collections.abc import Callable
from pathlib import Path

import pytest
from relay import declare
from relay import install_relay

from dotfiles import paths
from dotfiles import publishing
from dotfiles import vocabulary
from dotfiles.commands import status as status_commands
from dotfiles.vocabulary import ExitCode
from matrix.harness import Invocation
from matrix.harness import Sandbox

MACHINE = 'box'


@pytest.fixture
def server(sandbox: Sandbox) -> Path:
    root = sandbox.root / 'server'
    (root / 'artefacts').mkdir(parents=True)
    install_relay(sandbox.bin, root)
    declare(sandbox.config)
    return root


def shelf(server: Path) -> Path:
    return server / 'artefacts' / 'status' / MACHINE


class TestWhatTheDocumentCovers:
    def test_it_names_its_own_scope(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        """Without it, a consumer reads "not mentioned" as "this machine has none",
        which is the sweep-as-deletion failure the scope field exists to stop."""
        ran = cli('status', 'show', '--json')

        assert ran.exit_code == ExitCode.CONVERGED
        assert set(ran.document['scope']) <= set(publishing.PUBLISHABLE)

    def test_it_carries_no_resource_outside_the_allowlist(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        """`identity` is the one that matters and the one this is really about: its
        rows are `user.name` and `user.email`, and a nonfleet box defaults to the
        employer identity."""
        ran = cli('status', 'show', '--json')
        covered = {vocabulary.parse_address(str(row['address']))[0] for row in ran.document['resources']}

        assert covered <= set(publishing.PUBLISHABLE)
        assert 'identity' not in covered
        assert 'env' not in covered

    def test_a_resource_added_later_is_excluded_until_it_is_named(self) -> None:
        """The allowlist is the point. A denylist admits whatever lands next, and
        nobody reviews a diff for a leak it silently permits.

        Asserted against the vocabulary rather than a copy of it, so a resource
        added to `RESOURCES` fails here rather than being published the day it
        lands.
        """
        assert set(publishing.PUBLISHABLE) < set(vocabulary.RESOURCES)
        assert set(vocabulary.RESOURCES) - set(publishing.PUBLISHABLE)

    def test_the_full_check_document_still_covers_everything(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        """The narrowing belongs to this verb, not to the document. `check --json`
        is unchanged and still answers for the whole machine."""
        ran = cli('check', '--json', catch_exceptions=True)

        assert set(ran.document['scope']) > set(publishing.PUBLISHABLE)


NAMED = {'this machine name': 'pf5xmxfy', 'the account this runs as': 'a-work-account'}
"""The two names the gate refuses, chosen rather than read off this machine.

A test that reads `paths.machine_id()` and `getpass.getuser()` can only assert
against whatever machine it runs on, and the two overlap differently everywhere:
this counted two problems at a desk and three on a runner whose hostname contains
its username. `standards/testing.md` § "Never assert on rendered output" is the
same failure one layer up — assert the value, and choose the inputs.
"""


class TestTheGate:
    def test_a_document_naming_this_box_is_refused(self) -> None:
        """The second guard, and the one the allowlist cannot be: an allowlist
        protects against a new resource, never against a new field on a row."""
        problems = publishing.redacted({'scope': list(publishing.PUBLISHABLE), 'rows': [{'detail': 'pf5xmxfy'}]}, NAMED)

        assert problems == ('this machine name appears in it',)

    def test_a_document_naming_this_box_in_another_case_is_refused(self) -> None:
        """`machine_id` lowercases and Windows reports a hostname in upper, so the
        two never meet as typed. `PF5XMXFY` is the literal that made
        `connectivity-results.txt` a leak, and a case-sensitive test reads it
        straight past."""
        problems = publishing.redacted({'scope': list(publishing.PUBLISHABLE), 'rows': [{'detail': 'PF5XMXFY'}]}, NAMED)

        assert problems == ('this machine name appears in it',)

    def test_a_document_naming_the_account_is_refused(self) -> None:
        problems = publishing.redacted({'scope': list(publishing.PUBLISHABLE), 'rows': [{'detail': 'a-work-account'}]}, NAMED)

        assert problems == ('the account this runs as appears in it',)

    def test_a_document_covering_more_than_the_allowlist_is_refused(self) -> None:
        problems = publishing.redacted({'scope': ['packages', 'identity'], 'rows': []}, NAMED)

        assert any('identity' in problem for problem in problems)

    def test_a_clean_document_passes(self) -> None:
        """Paired with the refusals, because a gate that refused everything would
        satisfy all three above."""
        assert publishing.redacted({'scope': ['packages'], 'rows': [{'detail': 'fd 10.2.0'}]}, NAMED) == ()

    def test_every_reason_is_reported_at_once(self) -> None:
        problems = publishing.redacted({'scope': ['identity'], 'rows': [{'detail': 'pf5xmxfy a-work-account'}]}, NAMED)

        assert len(problems) == 3

    def test_the_names_it_refuses_are_this_machine_s(self) -> None:
        """The half the chosen names above cannot cover: that what reaches the gate
        in production is the hostname and the account rather than two constants."""
        assert publishing.identifying() == {
            'this machine name': paths.machine_id(),
            'the account this runs as': getpass.getuser(),
        }

    def test_the_refusal_carries_an_issue_and_names_what_would_have_been_sent(self) -> None:
        with pytest.raises(publishing.Unpublishable) as refused:
            publishing.refuse_unpublishable({'scope': ['identity'], 'rows': []})

        assert refused.value.code is ExitCode.ISSUE
        assert 'dotfiles status show --json' in refused.value.advice


class TestPublishing:
    def test_the_document_lands_on_the_machines_shelf(self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]) -> None:
        ran = cli('status', 'upload')

        assert ran.exit_code == ExitCode.CONVERGED
        published = list(shelf(server).iterdir())
        assert len(published) == 1
        assert published[0].name.startswith(status_commands.PREFIX)

    def test_what_lands_is_the_document_that_would_have_been_shown(
        self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]
    ) -> None:
        """One composer for both, so the thing a person inspects and the thing that
        travels cannot come to differ."""
        shown = cli('status', 'show', '--json').document
        cli('status', 'upload')
        sent = json.loads(next(iter(shelf(server).iterdir())).read_text())

        assert sent['scope'] == shown['scope']
        assert sent['version'] == shown['version']
        assert [row['address'] for row in sent['resources']] == [row['address'] for row in shown['resources']]

    def test_the_filename_carries_a_digest_rather_than_the_hostname(
        self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]
    ) -> None:
        """Two machines share `macos-personal-workstation`, so the manifest alone
        would have one overwrite the other — and the hostname that would ordinarily
        key it is an employer asset tag on the machine this exists for."""
        cli('status', 'upload')
        published = next(iter(shelf(server).iterdir())).name

        assert status_commands.discriminator() in published
        assert paths.machine_id() not in published

    def test_the_shelf_is_keyed_on_the_manifest(self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]) -> None:
        cli('status', 'upload')

        assert (server / 'artefacts' / 'status' / MACHINE).is_dir()
        assert not (server / 'artefacts' / 'status' / paths.machine_id()).exists()

    def test_two_uploads_accumulate_rather_than_overwriting(
        self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A machine's history is what makes "built against a status from six days
        ago" answerable, and the stamp is to the second so two in one day differ."""
        cli('status', 'upload')
        second = f'{status_commands.PREFIX}20260909T120000Z-{MACHINE}-ffff.json'
        monkeypatch.setattr(status_commands, 'filename', lambda machine, when: second)
        cli('status', 'upload')

        assert len(list(shelf(server).iterdir())) == 2

    def test_an_unconfigured_machine_refuses_and_points_at_the_config(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        ran = cli('status', 'upload', catch_exceptions=True)

        assert ran.exit_code == ExitCode.ISSUE
        assert 'dotfiles config show' in ran.stderr


class TestFetching:
    def test_the_newest_is_listed_first_and_fetched_by_default(
        self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]
    ) -> None:
        shelf(server).mkdir(parents=True)
        for stamp in ('20260101T010000Z', '20260909T120000Z'):
            (shelf(server) / f'{status_commands.PREFIX}{stamp}-{MACHINE}-abcd1234.json').write_text('{"version": 2}')

        listed = cli('status', 'list', '--json')
        fetched = cli('status', 'download')

        assert listed.document['statuses'][0].startswith(f'{status_commands.PREFIX}20260909T120000Z')
        assert fetched.exit_code == ExitCode.CONVERGED
        assert (paths.STATUS_CACHE / f'{status_commands.PREFIX}20260909T120000Z-{MACHINE}-abcd1234.json').is_file()

    def test_print_path_puts_the_path_alone_on_stdout(self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]) -> None:
        """So the networked side is a substitution rather than a copy-paste, the
        same handoff `bundle create --print-path` already offers."""
        shelf(server).mkdir(parents=True)
        (shelf(server) / f'{status_commands.PREFIX}20260909T120000Z-{MACHINE}-abcd1234.json').write_text('{"version": 2}')

        ran = cli('status', 'download', '--print-path')

        assert ran.stdout.strip().endswith('.json')
        assert Path(ran.stdout.strip()).is_file()

    def test_an_empty_shelf_refuses_rather_than_succeeding_into_silence(
        self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]
    ) -> None:
        ran = cli('status', 'download', catch_exceptions=True)

        assert ran.exit_code == ExitCode.ISSUE
        assert 'holds no status' in ran.stderr

    def test_a_name_the_remote_does_not_hold_is_a_usage_error(self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]) -> None:
        shelf(server).mkdir(parents=True)
        (shelf(server) / f'{status_commands.PREFIX}20260909T120000Z-{MACHINE}-abcd1234.json').write_text('{"version": 2}')

        ran = cli('status', 'download', '--status', 'nothing-like-that.json', catch_exceptions=True)

        assert ran.exit_code == ExitCode.USAGE


def test_a_published_status_comes_back_intact(sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]) -> None:
    """The round trip, which neither half asserts on its own.

    Everything but `checked`, which is the one field two runs of the same walk are
    *meant* to disagree about — it records when the measurement happened.
    """
    cli('status', 'upload')
    sent = json.loads(next(iter(shelf(server).iterdir())).read_text())
    cli('status', 'download')
    fetched = json.loads(next(iter(paths.STATUS_CACHE.iterdir())).read_text())

    assert fetched == sent
    assert fetched['scope'] and fetched['resources'], 'a round trip of nothing would satisfy the line above'
