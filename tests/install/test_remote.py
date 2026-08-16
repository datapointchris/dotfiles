"""Reading a `[remote]` table, and driving a transport through it.

Two kinds of double, for two different questions. `relay` is a **fake**: a real
executable backed by a real directory that refuses what a real remote refuses —
listing a directory that is not there, downloading a name that does not exist,
uploading into a path nobody created. A fake that accepted everything would assert
this module's mental model rather than challenge it (standards/testing.md § "A
fake enforces the service's constraints; it never just replays responses"), and
the constraint it exists for is the one that costs an artefact: an upload the
transport reroutes lands where no `list` will ever find it.

`spy` is the other kind, and it answers the only question a fake cannot: whether
the argv this module *builds* is the one the transport was meant to receive. A
successful upload through the fake is satisfied by two different correct-looking
commands — standards/testing.md § "Assert invariants by spying on argv, not by
inspecting the result".

Config is read through `remote.read` over a real `config.toml`, never by
constructing a `Remote` by hand, per standards/testing.md § "Read the tool's own
files through the tool's own loader".
"""

from __future__ import annotations

from pathlib import Path

import pytest
from relay import install_relay
from relay import install_spy
from relay import recorded

from dotfiles import remote as transport
from dotfiles import settings
from dotfiles.vocabulary import ExitCode

TABLE = """
[remote]
root = "/artefacts"

[remote.transport]
program = "{program}"
probe = ["probe"]
list = ["list", "{{dir}}"]
upload = ["upload", "{{local}}", "{{dir}}"]
download = ["download", "{{remote}}", "{{local}}"]
"""
"""Deliberately narrower than `relay.TABLE`, which declares both optional
operations. What each omission costs is exactly what several tests here assert,
so the shared complete table cannot be the one they use."""


def declare(config_home: Path, body: str) -> None:
    """Write a real config.toml where `settings.config_file()` will look for it."""
    written = config_home / 'dotfiles'
    written.mkdir(parents=True, exist_ok=True)
    (written / 'config.toml').write_text(body)


@pytest.fixture
def config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / 'config'
    root.mkdir()
    monkeypatch.setenv('XDG_CONFIG_HOME', str(root))
    return root


@pytest.fixture
def server(tmp_path: Path) -> Path:
    """The directory the fake transport treats as the remote's source root."""
    root = tmp_path / 'server'
    root.mkdir()
    return root


@pytest.fixture
def relay(fake_bin: Path, server: Path) -> Path:
    return install_relay(fake_bin, server)


@pytest.fixture
def configured(config_home: Path, relay: Path) -> transport.Remote:
    declare(config_home, TABLE.format(program='relay'))
    found = transport.read()
    assert found.remote is not None, found.problem
    return found.remote


def spying(fake_bin: Path, tmp_path: Path, *, code: int = 0) -> Path:
    record = tmp_path / 'argv.jsonl'
    install_spy(fake_bin, record, code=code)
    return record


class TestReadingTheTable:
    def test_a_machine_with_no_table_has_no_remote_and_no_problem(self, config_home: Path) -> None:
        """The ordinary state of every box that never exchanges a bundle.

        Distinguished from a broken table because the two get opposite advice, and
        a machine told it has no remote when it has a malformed one goes looking
        for the wrong thing.
        """
        declare(config_home, 'repos_registry = "~/dev/repos.json"\n')

        found = transport.read()

        assert found.remote is None
        assert found.problem == ''
        assert found.declared is False

    def test_an_absent_config_file_is_the_same_answer(self, config_home: Path) -> None:
        found = transport.read()

        assert (found.remote, found.problem) == (None, '')

    def test_a_valid_table_resolves_with_the_compiled_in_defaults(self, config_home: Path) -> None:
        """`keep_bundles` and both automatic-path flags are this tool's own settings, so they
        have defaults. `root` is a path on somebody else's server and never can."""
        declare(config_home, TABLE.format(program='relay'))

        found = transport.read()

        assert found.remote is not None
        assert found.remote.root == '/artefacts'
        assert found.remote.transport.program == 'relay'
        assert found.remote.keep_bundles == transport.DEFAULT_KEEP
        assert found.remote.fetch_bundle_when_none_is_staged is False
        assert found.remote.publish_status_after_offline_apply is False

    def test_every_fault_in_a_hand_edited_table_is_reported_at_once(self, config_home: Path) -> None:
        """Three mistakes otherwise cost three runs, and each run's one line reads
        as the only thing wrong."""
        declare(
            config_home,
            """
            [remote]
            keep = 0

            [remote.transport]
            list = ["list", "{dir}"]
            upload = ["upload", "{local}", "{dir}"]
            download = ["download", "{remote}", "{local}"]
            """,
        )

        found = transport.read()

        assert found.remote is None
        assert 'remote.root' in found.problem
        assert 'remote.keep' in found.problem
        assert 'remote.transport.program' in found.problem

    def test_a_template_naming_no_placeholder_is_refused(self, config_home: Path) -> None:
        """`upload = ["upload"]` parses, runs, and uploads nothing — reporting
        whatever the transport says about being called with no arguments."""
        declare(
            config_home,
            """
            [remote]
            root = "/artefacts"

            [remote.transport]
            program = "relay"
            list = ["list", "{dir}"]
            upload = ["upload"]
            download = ["download", "{remote}", "{local}"]
            """,
        )

        found = transport.read()

        assert found.remote is None
        assert 'remote.transport.upload' in found.problem
        assert '{local}' in found.problem

    def test_an_empty_placeholder_is_refused_rather_than_raising_at_run_time(self, config_home: Path) -> None:
        """`{}` fills from a positional argument and nothing here has one, so an
        accepted template raises IndexError at the moment the transport runs —
        a traceback where every other fault in this table is a sentence."""
        declare(
            config_home,
            """
            [remote]
            root = "/artefacts"

            [remote.transport]
            program = "relay"
            probe = ["probe"]
            list = ["list", "{dir}", "{}"]
            upload = ["upload", "{local}", "{dir}"]
            download = ["download", "{remote}", "{local}"]
            """,
        )

        found = transport.read()

        assert found.remote is None
        assert 'remote.transport.list' in found.problem
        assert '{}' in found.problem

    def test_an_unbalanced_brace_is_reported_rather_than_escaping_config_show(self, config_home: Path) -> None:
        """`string.Formatter().parse` raises ValueError on one, and the command
        `ADVICE` sends the reader to is exactly `dotfiles config show`."""
        declare(
            config_home,
            """
            [remote]
            root = "/artefacts"

            [remote.transport]
            program = "relay"
            probe = ["probe"]
            list = ["list", "{dir"]
            upload = ["upload", "{local}", "{dir}"]
            download = ["download", "{remote}", "{local}"]
            """,
        )

        found = transport.read()

        assert found.remote is None
        assert 'remote.transport.list' in found.problem

    def test_a_template_naming_a_placeholder_the_operation_does_not_have_is_refused(self, config_home: Path) -> None:
        declare(
            config_home,
            """
            [remote]
            root = "/artefacts"

            [remote.transport]
            program = "relay"
            list = ["list", "{dir}", "{local}"]
            upload = ["upload", "{local}", "{dir}"]
            download = ["download", "{remote}", "{local}"]
            """,
        )

        found = transport.read()

        assert found.remote is None
        assert 'remote.transport.list' in found.problem

    def test_a_missing_required_operation_is_named(self, config_home: Path) -> None:
        declare(
            config_home,
            """
            [remote]
            root = "/artefacts"

            [remote.transport]
            program = "relay"
            list = ["list", "{dir}"]
            upload = ["upload", "{local}", "{dir}"]
            """,
        )

        found = transport.read()

        assert found.remote is None
        assert 'remote.transport.download is not declared' in found.problem

    def test_mkdir_and_delete_are_optional(self, config_home: Path) -> None:
        """A machine can decline to give this tool the ability to create or remove
        things on a server, and still exchange artefacts."""
        declare(config_home, TABLE.format(program='relay'))

        found = transport.read()

        assert found.remote is not None
        assert found.remote.transport.declares(transport.Operation.MKDIR) is False
        assert found.remote.transport.declares(transport.Operation.DELETE) is False

    def test_a_config_file_that_will_not_parse_is_a_problem_not_an_absent_remote(self, config_home: Path) -> None:
        declare(config_home, 'this is not toml [[[\n')

        found = transport.read()

        assert found.remote is None
        assert found.problem != ''
        assert found.declared is True


class TestBuildingTheCommand:
    def test_each_operation_substitutes_exactly_its_own_placeholders(self, configured: transport.Remote) -> None:
        built = configured.transport
        assert built.argv(transport.Operation.LIST, {'dir': '/artefacts/bundles'}) == ('relay', 'list', '/artefacts/bundles')
        assert built.argv(transport.Operation.UPLOAD, {'local': '/tmp/a.tar.gz', 'dir': '/x'}) == ('relay', 'upload', '/tmp/a.tar.gz', '/x')
        assert built.argv(transport.Operation.DOWNLOAD, {'remote': '/x/a', 'local': '/tmp/a'}) == ('relay', 'download', '/x/a', '/tmp/a')

    def test_a_path_holding_a_space_stays_one_argument(self, configured: transport.Remote) -> None:
        """Nothing here goes through a shell, so the only way a space splits a path
        is a template joined into one string before substitution."""
        built = configured.transport.argv(transport.Operation.UPLOAD, {'local': '/tmp/two words.tar.gz', 'dir': '/x'})

        assert built == ('relay', 'upload', '/tmp/two words.tar.gz', '/x')

    def test_a_directory_is_joined_under_the_root_with_the_remote_separator(self, configured: transport.Remote) -> None:
        """Never `Path`, which joins with a backslash on Windows — where this repo
        now has a machine, and where the remote has never heard of one."""
        assert configured.directory('bundles', 'wsl-work-workstation') == '/artefacts/bundles/wsl-work-workstation'
        assert configured.directory('/bundles/') == '/artefacts/bundles'

    def test_the_argv_reaching_the_transport_is_the_one_that_was_built(self, fake_bin: Path, tmp_path: Path, config_home: Path) -> None:
        """The fake cannot answer this: two different correct-looking commands both
        put a file in the right place."""
        record = spying(fake_bin, tmp_path)
        declare(config_home, TABLE.format(program='spy'))
        found = transport.read()
        assert found.remote is not None

        transport.names(found.remote, '/artefacts/bundles')

        assert recorded(record) == [['list', '/artefacts/bundles']]


class TestListing:
    def test_every_line_is_one_name_and_order_is_the_transports(self, configured: transport.Remote, server: Path) -> None:
        (server / 'artefacts').mkdir()
        for name in ('b.tar.gz', 'a.tar.gz'):
            (server / 'artefacts' / name).write_text('x')

        assert transport.names(configured, '/artefacts') == ('a.tar.gz', 'b.tar.gz')

    def test_an_unreachable_directory_raises_rather_than_answering_empty(self, configured: transport.Remote) -> None:
        """Opposite findings. A caller that reconciles by sweep reads an empty
        answer as "everything was deleted", which is the failure
        standards/cli-design.md § "A narrowing default reads as a deletion to
        anything that reconciles by sweep" measures on todoui."""
        with pytest.raises(transport.RemoteError) as refused:
            transport.names(configured, '/artefacts/never-created')

        assert refused.value.code is ExitCode.ISSUE
        assert 'never-created' in str(refused.value)

    def test_an_empty_directory_answers_empty(self, configured: transport.Remote, server: Path) -> None:
        """The other half of the pair above: absence and emptiness must not collapse."""
        (server / 'artefacts').mkdir()

        assert transport.names(configured, '/artefacts') == ()

    def test_exists_answers_without_raising(self, configured: transport.Remote, server: Path) -> None:
        (server / 'artefacts').mkdir()

        assert transport.exists(configured, '/artefacts') is True
        assert transport.exists(configured, '/artefacts/nowhere') is False


class TestTellingAbsenceFromFailure:
    """`listed` has three answers because a listing has three outcomes.

    A boolean probe in front of a raising call re-collapsed the distinction that
    call exists to preserve: a transport failure answered as an empty shelf, and
    `bundle create --against latest` then built a full bundle on a run where a
    perfectly good status was sitting on a server nobody could reach.
    """

    def test_a_directory_that_lists_answers_with_its_rows(self, configured: transport.Remote, server: Path) -> None:
        (server / 'artefacts').mkdir()
        (server / 'artefacts' / 'a.tar.gz').write_text('x')

        assert transport.listed(configured, '/artefacts') == ('a.tar.gz',)

    def test_a_directory_that_was_never_created_answers_none(self, configured: transport.Remote, server: Path) -> None:
        """Absence is established by an ancestor that lists, which is what proves
        the remote is reachable and leaves the missing child as the explanation."""
        (server / 'artefacts').mkdir()

        assert transport.listed(configured, '/artefacts/never-created') is None

    def test_an_unreachable_remote_raises_rather_than_reading_as_absent(self, configured: transport.Remote) -> None:
        """Nothing up to the root lists, so nothing establishes absence. The
        refusal travels rather than a caller being told the shelf is empty."""
        with pytest.raises(transport.RemoteError) as refused:
            transport.listed(configured, '/artefacts/bundles/box')

        assert refused.value.code is ExitCode.ISSUE
        assert 'box' in str(refused.value)


class TestPushing:
    def test_a_file_lands_in_the_named_directory(self, configured: transport.Remote, server: Path, tmp_path: Path) -> None:
        (server / 'artefacts').mkdir()
        local = tmp_path / 'bundle.tar.gz'
        local.write_text('payload')

        landed = transport.push(configured, local, '/artefacts')

        assert landed == '/artefacts/bundle.tar.gz'
        assert (server / 'artefacts' / 'bundle.tar.gz').read_text() == 'payload'

    def test_a_missing_directory_with_no_declared_mkdir_refuses_before_any_bytes_move(
        self, configured: transport.Remote, server: Path, tmp_path: Path
    ) -> None:
        """Paired with the positive fact, per standards/testing.md § "An assertion
        that nothing happened is satisfied by a crash": the refusal carries ISSUE
        and names the directory, and nothing was written under it."""
        local = tmp_path / 'bundle.tar.gz'
        local.write_text('payload')

        with pytest.raises(transport.RemoteError) as refused:
            transport.push(configured, local, '/artefacts/bundles')

        assert refused.value.code is ExitCode.ISSUE
        assert 'mkdir' in str(refused.value)
        assert not (server / 'artefacts').exists()

    def test_a_missing_directory_is_created_where_mkdir_is_declared(
        self, config_home: Path, relay: Path, server: Path, tmp_path: Path
    ) -> None:
        declare(config_home, TABLE.format(program='relay') + 'mkdir = ["mkdir", "{dir}"]\n')
        found = transport.read()
        assert found.remote is not None, found.problem
        local = tmp_path / 'bundle.tar.gz'
        local.write_text('payload')

        transport.push(found.remote, local, '/artefacts/bundles')

        assert (server / 'artefacts' / 'bundles' / 'bundle.tar.gz').read_text() == 'payload'


class TestPulling:
    def test_a_file_arrives_at_the_named_path(self, configured: transport.Remote, server: Path, tmp_path: Path) -> None:
        (server / 'artefacts').mkdir()
        (server / 'artefacts' / 'bundle.tar.gz').write_text('payload')
        destination = tmp_path / 'cache' / 'bundle.tar.gz'

        transport.pull(configured, '/artefacts/bundle.tar.gz', destination)

        assert destination.read_text() == 'payload'

    def test_an_absent_remote_file_refuses(self, configured: transport.Remote, server: Path, tmp_path: Path) -> None:
        (server / 'artefacts').mkdir()
        destination = tmp_path / 'cache' / 'bundle.tar.gz'

        with pytest.raises(transport.RemoteError) as refused:
            transport.pull(configured, '/artefacts/bundle.tar.gz', destination)

        assert refused.value.code is ExitCode.ISSUE
        assert not destination.exists()

    def test_a_transport_that_exits_zero_and_writes_nothing_is_caught_here(self, fake_bin: Path, tmp_path: Path, config_home: Path) -> None:
        """Otherwise the checksum that follows raises `FileNotFoundError` several
        frames from the command that caused it."""
        spying(fake_bin, tmp_path)
        declare(config_home, TABLE.format(program='spy'))
        found = transport.read()
        assert found.remote is not None

        with pytest.raises(transport.RemoteError) as refused:
            transport.pull(found.remote, '/artefacts/bundle.tar.gz', tmp_path / 'cache' / 'bundle.tar.gz')

        assert refused.value.code is ExitCode.ISSUE
        assert 'wrote no file' in str(refused.value)


class TestRetention:
    def test_the_oldest_beyond_the_limit_are_named_and_nothing_is_removed(self) -> None:
        """Pure, and separate from `remove`, so a machine with no declared `delete`
        can still say what has accumulated."""
        listed = (
            'dotfiles-offline-v20260901T0730Z-wsl.tar.gz',
            'dotfiles-offline-v20260101T0100Z-wsl.tar.gz',
            'dotfiles-offline-v20260814T1902Z-wsl.tar.gz',
        )

        assert transport.superseded(listed, keep=2) == ('dotfiles-offline-v20260101T0100Z-wsl.tar.gz',)

    def test_a_remote_holding_fewer_than_the_limit_supersedes_nothing(self) -> None:
        assert transport.superseded(('a', 'b'), keep=5) == ()

    def test_removing_refuses_where_the_machine_declared_no_delete(self, configured: transport.Remote, server: Path) -> None:
        (server / 'artefacts').mkdir()
        (server / 'artefacts' / 'old.tar.gz').write_text('x')

        with pytest.raises(transport.RemoteError) as refused:
            transport.remove(configured, '/artefacts/old.tar.gz')

        assert refused.value.code is ExitCode.ISSUE
        assert (server / 'artefacts' / 'old.tar.gz').exists()

    def test_removing_works_where_it_is_declared(self, config_home: Path, relay: Path, server: Path) -> None:
        declare(config_home, TABLE.format(program='relay') + 'delete = ["delete", "{remote}"]\n')
        found = transport.read()
        assert found.remote is not None, found.problem
        (server / 'artefacts').mkdir()
        (server / 'artefacts' / 'old.tar.gz').write_text('x')

        transport.remove(found.remote, '/artefacts/old.tar.gz')

        assert not (server / 'artefacts' / 'old.tar.gz').exists()


class TestRequiring:
    def test_an_unconfigured_machine_refuses_with_the_command_that_configures_it(self, config_home: Path) -> None:
        with pytest.raises(transport.RemoteError) as refused:
            transport.require()

        assert refused.value.code is ExitCode.ISSUE
        assert 'dotfiles config show' in refused.value.advice

    def test_a_malformed_table_refuses_with_a_different_sentence(self, config_home: Path) -> None:
        declare(config_home, '[remote]\nroot = 5\n')

        with pytest.raises(transport.RemoteError) as refused:
            transport.require()

        assert 'cannot be read' in str(refused.value)


class TestMeasuring:
    def test_presence_of_the_program_is_not_reported_as_readiness(self, config_home: Path, fake_bin: Path, tmp_path: Path) -> None:
        """The state standards/configuration.md § "A declared requirement states
        what has to be true" describes: the binary is there and the remote answers
        nothing."""
        spying(fake_bin, tmp_path, code=1)
        declare(config_home, TABLE.format(program='spy'))

        measured = transport.measure(transport.read())
        by_subject = {reach.subject: reach for reach in measured}

        assert by_subject['transport'].ok is True
        assert by_subject['reachable'].ok is False
        assert [reach.subject for reach in measured if reach.faulty] == ['reachable']

    def test_a_transport_that_is_not_installed_stops_the_measurement(self, config_home: Path, fake_bin: Path) -> None:
        declare(config_home, TABLE.format(program='nothing-is-installed-here'))

        measured = transport.measure(transport.read())

        assert [reach.subject for reach in measured] == ['transport', 'configured']
        assert measured[0].ok is False

    def test_an_undeclared_optional_is_a_fact_rather_than_a_fault(self, config_home: Path, relay: Path, server: Path) -> None:
        """Otherwise `remote check` exits non-zero on every working remote that
        never needed a `mkdir`."""
        (server / 'artefacts').mkdir()
        declare(config_home, TABLE.format(program='relay'))

        measured = transport.measure(transport.read())
        by_subject = {reach.subject: reach for reach in measured}

        assert by_subject['mkdir'].ok is False
        assert by_subject['mkdir'].required is False
        assert by_subject['mkdir'].faulty is False
        assert [reach.subject for reach in measured if reach.faulty] == []

    def test_an_unconfigured_machine_measures_one_fault(self, config_home: Path) -> None:
        measured = transport.measure(transport.read())

        assert [(reach.subject, reach.faulty) for reach in measured] == [('config', True)]


def test_the_config_file_this_reads_is_the_one_the_tool_resolves(config_home: Path) -> None:
    """Guards every test above: a fixture pointing `$XDG_CONFIG_HOME` somewhere the
    loader does not look would let all of them pass against an absent file."""
    declare(config_home, TABLE.format(program='relay'))

    assert settings.config_file() == config_home / 'dotfiles' / 'config.toml'
    assert settings.config_file().is_file()


class TestProbing:
    """Whether the server is there, asked apart from anything that names a path.

    The distinction the whole chain rests on. Every other operation names a
    directory, so its failure means either "unreachable" or "not there" and one
    exit code cannot say which — which is how a machine comes to build a full
    bundle because a dropped packet hid the status that would have made it sparse.
    """

    def test_a_reachable_remote_answers_on_the_first_attempt(self, configured: transport.Remote, server: Path) -> None:
        answer = transport.answered(configured, backoff=0)

        assert answer.ok is True
        assert answer.attempts == 1

    def test_a_probe_answers_even_where_nothing_has_been_uploaded(self, configured: transport.Remote, server: Path) -> None:
        """The property a probe must have, and the reason it cannot be a listing of
        the root: a root that does not exist yet is the ordinary state of a fresh
        remote, and a probe that failed on it would report every first run as an
        outage."""
        assert not (server / 'artefacts').exists()

        assert transport.answered(configured, backoff=0).ok is True

    def test_a_server_that_will_not_answer_is_retried_before_it_is_believed(
        self, config_home: Path, fake_bin: Path, tmp_path: Path
    ) -> None:
        """One dropped packet is indistinguishable from an outage in a single call,
        and the two lead to opposite decisions."""
        record = tmp_path / 'argv.jsonl'
        install_spy(fake_bin, record, code=1)
        declare(config_home, TABLE.format(program='spy'))
        found = transport.read()
        assert found.remote is not None

        answer = transport.answered(found.remote, attempts=3, backoff=0)

        assert answer.ok is False
        assert answer.attempts == 3
        assert len(recorded(record)) == 3, 'every attempt has to actually reach the transport'

    def test_a_program_that_is_not_installed_is_not_retried(self, config_home: Path, fake_bin: Path) -> None:
        """`which` is definitive where an exit code is not, so waiting three
        seconds to answer the same way three times buys nothing."""
        declare(config_home, TABLE.format(program='nothing-is-installed-here'))
        found = transport.read()
        assert found.remote is not None

        answer = transport.answered(found.remote, attempts=3, backoff=0)

        assert (answer.ok, answer.attempts) == (False, 1)
        assert 'not on PATH' in answer.detail


class TestTheSharedEntryPoint:
    """`reachable` is the first call of every verb, and asks the two in order."""

    def test_an_unconfigured_machine_refuses_before_anything_is_probed(self, config_home: Path) -> None:
        """The order matters: a machine that never declared a remote must not be
        reported as one whose network is down."""
        with pytest.raises(transport.RemoteError) as refused:
            transport.reachable()

        assert not isinstance(refused.value, transport.Unreachable)
        assert 'dotfiles config show' in refused.value.advice

    def test_a_declared_remote_that_will_not_answer_refuses_as_unreachable(
        self, config_home: Path, fake_bin: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Its own type, because a caller acts on it differently: an absent
        directory means "nothing published yet" and this means "go and look"."""
        install_spy(fake_bin, tmp_path / 'argv.jsonl', code=1)
        declare(config_home, TABLE.format(program='spy'))
        monkeypatch.setattr(transport, 'PROBE_BACKOFF_SECONDS', 0)

        with pytest.raises(transport.Unreachable) as refused:
            transport.reachable()

        assert refused.value.code is ExitCode.ISSUE
        assert 'remote check' in refused.value.advice

    def test_a_reachable_remote_is_handed_back(self, configured: transport.Remote, server: Path) -> None:
        """Paired with both refusals, which a `reachable` that always raised would
        satisfy."""
        assert transport.reachable().root == '/artefacts'
