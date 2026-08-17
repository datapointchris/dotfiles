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

import datetime as dt
import getpass
import json
from collections.abc import Callable
from pathlib import Path

import pytest
from relay import declare
from relay import install_relay

from dotfiles import coordinates as axes
from dotfiles import paths
from dotfiles import publishing
from dotfiles import publishing as status_commands
from dotfiles import vocabulary
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

    def test_the_shelf_key_is_not_read_as_a_leak(self) -> None:
        """`machine` is the manifest name and the shelf is a directory built from
        it, so a scan that read it as identity would refuse every document there
        has ever been. Measured on a box named `archlinux` running
        `archlinux-personal-workstation`, where the hostname is a substring of the
        key the exchange is organised by."""
        document = {'scope': list(publishing.PUBLISHABLE), 'machine': 'pf5xmxfy-work-workstation', 'rows': []}

        assert publishing.redacted(document, NAMED) == ()

    def test_a_document_whose_evidence_names_a_home_is_refused_unrooted(self) -> None:
        """The state the return leg was in for the whole life of the branch: a
        row's evidence is the path a tool was found at, and that path carries the
        account."""
        document = {'scope': list(publishing.PUBLISHABLE), 'rows': [{'detail': '/home/a-work-account/go/bin/gopls'}]}

        assert publishing.redacted(document, NAMED) == ('the account this runs as appears in it',)

    def test_rooting_the_same_document_clears_it(self) -> None:
        """Paired with the test above, because that one passing proves only that
        the gate fires. What has to hold is that composing correctly gets through
        it, or the feature is a refusal with extra steps."""
        document = {'scope': list(publishing.PUBLISHABLE), 'rows': [{'detail': '/home/a-work-account/go/bin/gopls'}]}

        rooted = publishing.rooted(document, '/home/a-work-account')

        assert rooted['rows'][0]['detail'] == '~/go/bin/gopls'
        assert publishing.redacted(rooted, NAMED) == ()

    def test_rooting_reaches_every_shape_a_document_holds(self) -> None:
        """Over the whole document rather than a named field. The field an account
        name turns up in next is the one nobody thought of, which is the same
        reasoning the byte scan itself rests on."""
        nested = {'rows': [{'evidence': ['/home/bob/bin/fd', 'unrelated']}, {'detail': '/home/bob/.cargo/bin/rg'}], 'count': 2}

        rooted = publishing.rooted(nested, '/home/bob')

        assert rooted['rows'][0]['evidence'] == ['~/bin/fd', 'unrelated']
        assert rooted['rows'][1]['detail'] == '~/.cargo/bin/rg'
        assert rooted['count'] == 2, 'a non-string value is carried through unchanged'

    def test_every_reason_is_reported_at_once(self) -> None:
        problems = publishing.redacted({'scope': ['identity'], 'rows': [{'detail': 'pf5xmxfy a-work-account'}]}, NAMED)

        assert len(problems) == 3

    def test_the_names_it_refuses_are_this_machine_s(self, monkeypatch) -> None:
        """The half the chosen names above cannot cover: that what reaches the gate
        in production is the hostname and the account rather than two constants."""
        monkeypatch.setenv('WINDOWS_USER', 'ab12345')
        monkeypatch.setenv('WINDOWS_DOMAIN', 'corp')

        assert publishing.identifying(axes.NetworkTrust.NONFLEET) == {
            'this machine name': paths.machine_id(),
            'the account this runs as': getpass.getuser(),
            'the Windows account': 'ab12345',
            'the Windows domain': 'corp',
        }

    def test_a_machine_with_no_windows_side_contributes_no_name(self, monkeypatch, tmp_path) -> None:
        """Empty rather than absent, because `redacted` already skips a falsy value.
        A key that appears only sometimes would make the shape depend on the box."""
        monkeypatch.delenv('WINDOWS_USER', raising=False)
        monkeypatch.delenv('WINDOWS_DOMAIN', raising=False)
        monkeypatch.setattr(publishing.Path, 'home', staticmethod(lambda: tmp_path))

        named = publishing.identifying(axes.NetworkTrust.NONFLEET)

        assert named['the Windows account'] == ''
        assert publishing.redacted({'rows': ['nothing here']}, named) == ()

    def test_a_fleet_box_does_not_screen_for_a_name_it_publishes_on_purpose(self) -> None:
        """`written_by` carries the bare hostname on `FLEET`, deliberately. Screening
        rows against it too withholds a row to hide a string travelling one key
        over — the builder loses a tool and the name ships regardless."""
        assert publishing.identifying(axes.NetworkTrust.FLEET) == {'the account this runs as': getpass.getuser()}


class TestTheValuesSetByHand:
    """`WINDOWS_USER` and `WINDOWS_DOMAIN` are identifiers the machine cannot derive."""

    def test_the_environment_answers_first(self, monkeypatch) -> None:
        monkeypatch.setenv('WINDOWS_USER', 'ab12345')

        assert publishing.declared_by_hand('WINDOWS_USER') == 'ab12345'

    def test_the_env_file_answers_when_no_shell_sourced_it(self, monkeypatch, tmp_path) -> None:
        """A scheduled run has no interactive shell behind it, and is exactly when
        nobody is watching what left the box."""
        monkeypatch.delenv('WINDOWS_USER', raising=False)
        (tmp_path / '.env').write_text('# OVERRIDES\nWINDOWS_USER=ab12345\n')
        monkeypatch.setattr(publishing.Path, 'home', staticmethod(lambda: tmp_path))

        assert publishing.declared_by_hand('WINDOWS_USER') == 'ab12345'

    def test_an_unset_value_is_empty_rather_than_a_refusal(self, monkeypatch, tmp_path) -> None:
        monkeypatch.delenv('WINDOWS_USER', raising=False)
        monkeypatch.setattr(publishing.Path, 'home', staticmethod(lambda: tmp_path))

        assert publishing.declared_by_hand('WINDOWS_USER') == ''

    def test_the_employee_id_refuses_a_document_carrying_it(self, monkeypatch) -> None:
        """The case this exists for. `steps.windows_fonts` asks Windows for the
        account and records the answer, so the id reaches a run record in an
        `answer` and a `target` — matching no token shape and no credential word."""
        monkeypatch.setenv('WINDOWS_USER', 'ab12345')
        named = publishing.identifying(axes.NetworkTrust.NONFLEET)

        problems = publishing.redacted({'rows': [{'target': '/mnt/c/Users/ab12345/AppData'}]}, named)

        assert problems == ('the Windows account appears in it',)

    def test_the_refusal_carries_an_issue_and_names_what_would_have_been_sent(self) -> None:
        with pytest.raises(publishing.Unpublishable) as refused:
            publishing.publishable({'scope': ['identity'], 'resources': []}, axes.NetworkTrust.NONFLEET)

        assert refused.value.code is ExitCode.ISSUE
        assert 'dotfiles status show --json' in refused.value.advice


def relayed(banner: str) -> dict[str, object]:
    """A document shaped like a real one, with a version string a tool printed.

    The shape the authored fixtures above cannot produce, and the reason this
    escaped every one of them: `observed` carries whatever the binary said about
    itself, and `syncthing --version` says `syncthing@<build host>`.
    """
    return {
        'version': 2,
        'machine': 'a-manifest',
        'scope': list(publishing.PUBLISHABLE),
        'resources': [
            {
                'address': 'packages',
                'others': [
                    {'item': 'ghrelease/syncthing', 'observed': banner},
                    {'item': 'cargo/bat', 'observed': 'bat 0.26.0'},
                ],
            }
        ],
    }


class TestWithholdingARowRatherThanRefusingTheDocument:
    """A relayed version banner is not this machine identifying itself.

    Refusing the whole document for one of them took the return leg off a working
    box while a hundred innocent rows sat in it. The row is the unit of the fault,
    so the row is the unit of the remedy.
    """

    def test_the_row_carrying_the_name_does_not_travel(self) -> None:
        screen = publishing.screened(relayed('syncthing v2.1.3 (linux-amd64) syncthing@pf5xmxfy 2026-08-05'), NAMED)

        rows = screen.document['resources'][0]['others']  # type: ignore[index]
        assert [row['item'] for row in rows] == ['cargo/bat']
        assert 'pf5xmxfy' not in json.dumps(screen.document).lower()

    def test_the_withheld_row_is_named_rather_than_dropped_in_silence(self) -> None:
        screen = publishing.screened(relayed('syncthing v2.1.3 syncthing@pf5xmxfy'), NAMED)

        assert screen.withheld == ('ghrelease/syncthing',)

    def test_what_is_left_publishes(self) -> None:
        """The whole point. The document travels, one row lighter."""
        screen = publishing.screened(relayed('syncthing v2.1.3 syncthing@pf5xmxfy'), NAMED)

        assert screen.problems == ()
        assert len(screen.document['resources'][0]['others']) == 1  # type: ignore[index,arg-type]

    def test_the_production_door_screens_against_this_machine(self) -> None:
        """`publishable` reads the real names rather than taking them, which is the
        split `identifying` exists for — so this is the one assertion that has to
        use the machine the suite is running on."""
        banner = f'syncthing v2.1.3 syncthing@{paths.machine_id()}'

        screen = publishing.publishable(relayed(banner), axes.NetworkTrust.NONFLEET)

        assert screen.withheld == ('ghrelease/syncthing',)
        assert screen.problems == ()

    def test_an_untouched_document_is_unchanged_and_withholds_nothing(self) -> None:
        clean = relayed('syncthing v2.1.3 (linux-amd64) syncthing@some-build-host')

        screen = publishing.screened(clean, NAMED)

        assert screen == publishing.Screened(clean, (), ())

    def test_a_name_with_no_row_to_drop_still_refuses_the_document(self) -> None:
        """Withholding is not a way out. A name outside the per-item lists has
        nothing to withhold, so the document is refused exactly as before."""
        document = {'version': 2, 'machine': 'a-manifest', 'scope': list(publishing.PUBLISHABLE), 'note': 'pf5xmxfy', 'resources': []}

        screen = publishing.screened(document, NAMED)

        assert screen.withheld == ()
        assert screen.problems == ('this machine name appears in it',)

    def test_a_scope_outside_the_publishable_set_is_not_withholdable_either(self) -> None:
        screen = publishing.screened({'scope': ['identity'], 'resources': []}, NAMED)

        assert screen.problems and 'identity' in screen.problems[0]


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

    def test_a_fleet_machine_names_itself_in_the_filename(self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]) -> None:
        """Two machines share `macos-personal-workstation`, so the manifest alone
        would have one overwrite the other. On the fleet the hostname is not a
        secret and it is what a reader of the shelf wants."""
        cli('status', 'upload')
        published = next(iter(shelf(server).iterdir())).name

        assert status_commands.wrote(published) == paths.machine_id()

    def test_off_the_fleet_the_discriminator_names_nothing(self) -> None:
        """The hostname is an employer asset tag on the machine this exists for, so
        anything that is not FLEET gets a digest — the direction a privacy boundary
        has to fail in."""
        named = paths.machine_id()

        assert status_commands.discriminator(axes.NetworkTrust.FLEET) == named
        assert status_commands.discriminator(axes.NetworkTrust.NONFLEET) != named
        assert len(status_commands.discriminator(axes.NetworkTrust.NONFLEET)) == 8

    def test_a_hyphenated_hostname_falls_back_to_the_digest(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`wrote` recovers the discriminator by splitting on the last hyphen, and
        the manifest name it follows is full of them."""
        monkeypatch.setattr(paths, 'machine_id', lambda: 'my-laptop')
        stamped = dt.datetime(2026, 9, 9, 12, tzinfo=dt.UTC)

        name = status_commands.filename(MACHINE, stamped, axes.NetworkTrust.FLEET)

        assert status_commands.discriminator(axes.NetworkTrust.FLEET) != 'my-laptop'
        assert status_commands.wrote(name) == status_commands.discriminator(axes.NetworkTrust.FLEET)

    def test_composing_a_document_writes_no_run_record(self, sandbox: Sandbox, server: Path, cli: Callable[..., Invocation]) -> None:
        """`runs.write` re-points `latest` at whatever it wrote. Composing after an
        offline apply took that pointer off the apply and put it on a two-resource
        plan — on the box whose run records are the only account of what happened
        there, and where `report path` exists so a failed apply's record can be
        uploaded."""
        before = sorted(path.name for path in paths.RUNS_DIR.iterdir()) if paths.RUNS_DIR.is_dir() else []

        cli('status', 'upload')

        after = sorted(path.name for path in paths.RUNS_DIR.iterdir()) if paths.RUNS_DIR.is_dir() else []
        assert after == before

    def test_showing_a_status_does_not_name_the_bundle(self, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
        """It walks offline to get versions rather than to install anything. On a
        machine with nothing staged the note pointed at `bundle stage` — advice
        away from the next real step, in the state that is the first turn of the
        loop."""
        ran = cli('status', 'show', catch_exceptions=True)

        assert ran.exit_code == ExitCode.CONVERGED
        assert 'status' in ran.stdout + ran.stderr
        assert 'manifest.txt' not in ran.stderr
        assert 'bundle stage' not in ran.stderr

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
        monkeypatch.setattr(status_commands, 'filename', lambda machine, when, trust: second)
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
        assert (paths.status_cache() / f'{status_commands.PREFIX}20260909T120000Z-{MACHINE}-abcd1234.json').is_file()

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
    fetched = json.loads(next(iter(paths.status_cache().iterdir())).read_text())

    assert fetched == sent
    assert fetched['scope'] and fetched['resources'], 'a round trip of nothing would satisfy the line above'


def test_a_document_the_gate_would_refuse_exits_issue(sandbox: Sandbox, cli: Callable[..., Invocation], monkeypatch) -> None:
    """`status show && status upload` walked into a refusal the first command had
    already measured. `remote check` derives its verdict from its faults the same
    way, and this is the one finding this verb produces."""
    monkeypatch.setattr(publishing, 'identifying', lambda _trust: {'this machine name': 'packages'})

    ran = cli('status', 'show', catch_exceptions=True)

    assert ran.exit_code == ExitCode.ISSUE
    assert 'unpublishable' in ran.stderr


def test_a_clean_document_still_exits_converged(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    ran = cli('status', 'show', catch_exceptions=True)

    assert ran.exit_code == ExitCode.CONVERGED
