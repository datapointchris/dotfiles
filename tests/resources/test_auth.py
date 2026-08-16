"""The tools a machine declares under `auth:`: probed locally, never repaired.

Every probe is exercised against a shadowed binary or a real file under
`tmp_path`, so nothing here reads whichever tools the machine running the suite
happens to have logged in. That is the same seam `tests/resources/test_steps.py`
uses and it matters more here: without it, "nomad is logged out" holds on this
box for the wrong reason and inverts the day somebody logs in.
"""

from __future__ import annotations

import contextlib
import os
import sqlite3
import stat
from pathlib import Path

import pytest

from dotfiles import machine as machines
from dotfiles import paths
from dotfiles.privilege import Privilege
from dotfiles.resolve import Preconditions
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.resources import auth
from dotfiles.session import Session

KEYCHAIN_CLIS = ('icb', 'learning', 'meso', 'nomad')


def executable(directory: Path, name: str, script: str = '#!/bin/sh\nexit 0\n') -> Path:
    """See `_executable` in tests/conftest.py for why this is copied rather than imported."""
    target = directory / name
    target.write_text(script)
    target.chmod(target.stat().st_mode | stat.S_IEXEC)
    return target


def build(tmp_path: Path, *tools: str) -> Session:
    """A synthetic install tree declaring these tools, and a home to probe under.

    `XDG_DATA_HOME` and `XDG_CONFIG_HOME` are left to the fixture below: they are
    real knobs every tool here honours, so pointing them at `tmp_path` is the same
    seam `GIT_CONFIG_GLOBAL` gives `test_identity.py` rather than a patch.
    """
    install = tmp_path / 'install'
    (install / 'manifests').mkdir(parents=True, exist_ok=True)
    (install / 'packages.yml').write_text('{}')
    (install / 'flags.yml').write_text('{}')
    declared = ''.join(f'  - {tool}\n' for tool in tools)
    (install / 'manifests' / 'box.yml').write_text(f'machine: box\nplatform: linux\nauth:\n{declared}')
    return Session(machine_name='box', repo=tmp_path, home=tmp_path)


@pytest.fixture
def xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point both XDG roots at the sandbox, so no probe can reach the real home."""
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / '.local' / 'share'))
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / '.config'))
    for name in (
        'GITHUB_TOKEN',
        'AWS_ACCESS_KEY_ID',
        'AWS_SHARED_CREDENTIALS_FILE',
        'BBKT_TOKEN',
        'JIRA_API_TOKEN',
        'JIRA_CONFIG_FILE',
        'ATUIN_CONFIG_DIR',
    ):
        monkeypatch.delenv(name, raising=False)
    return tmp_path


def changes(session: Session) -> tuple:
    return auth.RESOURCE.diff(session.plan, auth.RESOURCE.observe(session, session.plan))


# ─────────────────────────────────────────────────────────────────────────────
# The declaration against the code
# ─────────────────────────────────────────────────────────────────────────────


def declared_tools() -> set[str]:
    return {tool for name in machines.names(paths.REPO_ROOT) for tool in machines.load(name, paths.REPO_ROOT).auth}


def test_every_declared_tool_has_a_probe() -> None:
    """The direction that matters: a name nothing implements reads as converged.

    `observe` answers `UNKNOWN` for one, which `sift` counts as unmeasured and
    keeps out of the exit code — so a typo in an `auth:` list would leave the
    machine looking sound while the tool it meant to ask about went unasked.
    """
    named = declared_tools()

    assert named <= set(auth.PROBES), f'declared with no probe: {sorted(named - set(auth.PROBES))}'


def test_every_probe_is_declared_by_some_manifest() -> None:
    """The other direction, and the half `validate.py` structurally cannot ask: a
    synthetic tree can replace the manifests while these functions are always the
    real ones. A probe nothing declares is dead code that reads as maintained."""
    named = declared_tools()

    assert set(auth.PROBES) <= named, f'probes nothing declares: {sorted(set(auth.PROBES) - named)}'


LOCAL_PROBES = {f'{tool} auth status' for tool in KEYCHAIN_CLIS} | {'bbkt config path token'}
"""Every subprocess this resource is allowed to run, named as `<tool> <arguments>`.

**The tool is half the whitelist, and it is the discriminating half.** The cheap
spelling inverts between binaries: `auth status` is the 4ms keychain read for the
personal data CLIs and the 333ms networked validation for `gh`. Whitelisting the
arguments alone therefore permits `gh auth status` — the one alternative this
module's own docstring rejects by name — because it is spelled like the four that
are allowed. Measured: a probe swapped to `gh auth status` passed this test.

A whitelist rather than a list of forbidden spellings, because the forbidden ones
are unbounded and each of them appears in this module already — in the docstring
that says why it was rejected. `gh` is absent because it runs nothing at all.
"""


def test_every_subprocess_a_probe_runs_is_a_local_one(xdg: Path, fake_bin: Path) -> None:
    """The mechanical guard against a later edit reaching for the networked
    spelling. Each rejected alternative is the honest answer to "is this login
    usable" and each is a round trip, from a resource that runs unattended on a
    timer, where nobody is watching to discount an offline machine's answer."""
    log = xdg / 'argv'
    for tool in auth.PROBES:
        # The name is echoed rather than left to `$0`, which is the absolute path
        # the fixture wrote and so differs per run.
        executable(fake_bin, tool, f'#!/bin/sh\necho "{tool} $@" >> {log}\nexit 0\n')
    session = build(xdg, *auth.PROBES)
    session.__dict__['preconditions'] = Preconditions(github_auth=True)

    auth.RESOURCE.observe(session, session.plan)

    # Equality rather than a subset: a subset is satisfied by a run that shelled
    # out to nothing at all, which is what an exception thrown before the first
    # probe looks like from here.
    asked = set(log.read_text().splitlines()) if log.exists() else set()
    assert asked == LOCAL_PROBES, f'unexpected subprocesses: {sorted(asked ^ LOCAL_PROBES)}'


# ─────────────────────────────────────────────────────────────────────────────
# What a probe's answer becomes
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('tool', KEYCHAIN_CLIS)
def test_a_logged_out_cli_is_reported_and_never_repaired(xdg: Path, fake_bin: Path, tool: str) -> None:
    """A login is a browser flow. `apply` attempting one would put a prompt in
    front of every headless box, so the finding carries the command instead."""
    executable(fake_bin, tool, '#!/bin/sh\nexit 1\n')

    (found,) = changes(build(xdg, tool))

    assert found.verdict is Verdict.MISSING
    assert found.repair is Repair.BY_HAND
    assert not found.actionable
    assert tool in found.advice


@pytest.mark.parametrize('tool', KEYCHAIN_CLIS)
def test_a_logged_in_cli_produces_no_finding(xdg: Path, fake_bin: Path, tool: str) -> None:
    executable(fake_bin, tool, '#!/bin/sh\necho "Logged in"\nexit 0\n')

    assert changes(build(xdg, tool)) == ()


def test_a_keychain_cli_is_asked_with_status_rather_than_token(xdg: Path, fake_bin: Path) -> None:
    """`auth status` reads the keychain and makes no HTTP call, at 4ms whichever
    state the machine is in. `auth token` refreshes, so it costs 215ms on exactly
    the machine where the answer is yes — the inverse of what `gh` wants, which is
    why this is pinned rather than left to the next reader's intuition."""
    log = xdg / 'asked'
    executable(fake_bin, 'icb', f'#!/bin/sh\necho "$@" >> {log}\nexit 0\n')

    changes(build(xdg, 'icb'))

    assert log.read_text().split() == ['auth', 'status']


@pytest.mark.parametrize('tool', ['nomad', 'bbkt'])
def test_a_probe_that_never_answered_is_not_evidence_about_a_credential(
    xdg: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch, tool: str
) -> None:
    """`effects.run` reports a deadline as an exit code rather than an exception, so
    a hung keychain daemon arrives looking exactly like a clean "logged out" — and
    the deadline is per tool, over as many as a manifest declares. Read as logged
    out it advises a login on a machine that may well have one."""
    executable(fake_bin, tool, '#!/bin/sh\nsleep 30\n')
    monkeypatch.setattr(auth.evidence, 'PROBE_SECONDS', 0.2)

    (found,) = changes(build(xdg, tool))

    assert found.verdict is Verdict.UNKNOWN
    assert found.repair is Repair.NONE
    assert not found.advice
    assert '0.2s' in found.detail


@pytest.mark.parametrize('tool', ['nomad', 'bbkt'])
def test_a_binary_on_path_that_cannot_run_is_unmeasured_rather_than_logged_out(xdg: Path, fake_bin: Path, tool: str) -> None:
    """A shared library the loader cannot find exits 127, which `shutil.which` has
    already passed. Claiming the keychain is empty is a diagnosis of something that
    was never asked."""
    executable(fake_bin, tool, '#!/nonexistent/interpreter\n')

    (found,) = changes(build(xdg, tool))

    assert found.verdict is Verdict.UNKNOWN
    assert found.repair is Repair.NONE
    assert 'could not be executed' in found.detail


def test_a_tool_that_is_not_installed_is_unmeasured_rather_than_an_issue(xdg: Path, fake_bin: Path) -> None:
    """`Repair.NONE` puts it in `sift`'s unmeasured bucket, outside the exit code.
    The packages resource already reports the binary missing, and a second row
    saying it is also not logged in is a finding nobody can act on until the first
    one is fixed."""
    (found,) = changes(build(xdg, 'nomad'))

    assert found.verdict is Verdict.UNKNOWN
    assert found.repair is Repair.NONE
    assert not found.actionable


def test_a_declared_tool_with_no_probe_says_so_rather_than_passing(xdg: Path) -> None:
    """What a reader sees between a typo landing and `machines check` catching it.
    Dropping the name silently would make an unasked login indistinguishable from
    a satisfied one."""
    session = build(xdg, 'invented')

    (found,) = changes(session)

    assert found.verdict is Verdict.UNKNOWN
    assert found.repair is Repair.NONE


def test_an_unreadable_credential_path_costs_one_row_rather_than_the_resource(
    xdg: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Letting the OSError out of `observe` turns it into `auth could not be
    examined`, which says nothing about the tools that answered fine."""
    executable(fake_bin, 'aws')
    executable(fake_bin, 'atuin')
    session = build(xdg, 'aws', 'atuin')
    # Resolved before the filesystem starts refusing: the declaration is read
    # through the same call, and a catalog that cannot be loaded would fail this
    # for a reason that has nothing to do with a credential.
    plan = session.plan

    def refuse(_self: Path) -> bool:
        raise PermissionError('Permission denied')

    monkeypatch.setattr(Path, 'is_file', refuse)

    found = {change.item: change for change in auth.RESOURCE.diff(plan, auth.RESOURCE.observe(session, plan))}

    assert found['aws'].verdict is Verdict.UNKNOWN
    assert found['atuin'].verdict is Verdict.UNKNOWN


def test_nothing_here_is_ever_written(xdg: Path, fake_bin: Path, unprivileged: Privilege) -> None:
    """The `identity.py` invariant, and the one `apply` depends on: no change is
    actionable, so `_in_stage_order` never hands one to `perform` at all."""
    executable(fake_bin, 'nomad', '#!/bin/sh\nexit 1\n')
    session = build(xdg, 'nomad')

    (found,) = changes(session)

    assert not found.actionable
    assert auth.RESOURCE.perform(session, found, unprivileged).status is OutcomeStatus.REFUSED


def test_a_machine_declaring_no_auth_tools_has_nothing_to_report(xdg: Path) -> None:
    session = build(xdg)
    observed = auth.RESOURCE.observe(session, session.plan)

    assert changes(session) == ()
    assert observed.found == {}
    assert observed.present == 0


def test_the_row_counts_the_credentials_found_rather_than_claiming_all_are(xdg: Path, fake_bin: Path) -> None:
    """This resource reaches its converged sentence under `plan` whatever it found,
    because nothing here is ever actionable — so a summary asserting every tool is
    authenticated would contradict the rows printed right above it."""
    executable(fake_bin, 'icb', '#!/bin/sh\nexit 0\n')
    executable(fake_bin, 'meso', '#!/bin/sh\nexit 1\n')
    session = build(xdg, 'icb', 'meso')

    observed = auth.RESOURCE.observe(session, session.plan)

    assert observed.present == 1
    assert len(observed.found) == 2


# ─────────────────────────────────────────────────────────────────────────────
# gh, which is answered by the run's shared measurement
# ─────────────────────────────────────────────────────────────────────────────


def test_the_gh_probe_runs_no_subprocess_of_its_own(xdg: Path, fake_bin: Path) -> None:
    """`gh auth token` is 30ms and the run has already paid for it once — the
    resources that gate an install on a credential read the same answer. A probe
    here would spend it again for a verdict already held, and two probes can
    disagree inside one report."""
    log = xdg / 'gh-calls'
    executable(fake_bin, 'gh', f'#!/bin/sh\necho "$@" >> {log}\nexit 0\n')
    session = build(xdg, 'gh')
    session.__dict__['preconditions'] = Preconditions(github_auth=True)

    assert changes(session) == ()
    assert not log.exists()


def test_a_gh_with_no_credential_is_reported_with_the_shared_advice(xdg: Path, fake_bin: Path) -> None:
    """One problem, one sentence. `packages` reports the same missing credential as
    the reason a private-repo tool cannot install, and a reader seeing both rows in
    one `check` must not be reading two different fixes."""
    executable(fake_bin, 'gh')
    session = build(xdg, 'gh')
    session.__dict__['preconditions'] = Preconditions(github_auth=False)

    (found,) = changes(session)

    assert found.verdict is Verdict.MISSING
    assert found.advice == auth.GITHUB_AUTH_ADVICE


def test_a_github_token_answers_for_a_machine_with_no_gh_binary(xdg: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A CI runner and a container both have the token and not the CLI. Reporting
    that as "gh is not installed" is right about the binary and wrong about the
    credential, which is the thing being asked about."""
    monkeypatch.setenv('GITHUB_TOKEN', 'ghp_stub')
    session = build(xdg, 'gh')
    session.__dict__['preconditions'] = Preconditions(github_auth=True)

    assert changes(session) == ()


# ─────────────────────────────────────────────────────────────────────────────
# The file-answered probes
# ─────────────────────────────────────────────────────────────────────────────


def atuin_data() -> Path:
    """`~/.local/share/atuin`, under the sandboxed root, made ready to write into."""
    directory = Path(os.environ['XDG_DATA_HOME']) / 'atuin'
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def atuin_meta(**rows: str) -> Path:
    """A `meta.db` shaped the way atuin 18 writes one.

    Built rather than copied from this machine, so the test says what the schema
    has to look like instead of inheriting whatever the desk happens to hold.
    """
    meta = atuin_data() / 'meta.db'
    with contextlib.closing(sqlite3.connect(meta)) as store:
        store.execute('create table meta (key text primary key, value text)')
        store.executemany('insert into meta values (?, ?)', rows.items())
        store.commit()
    return meta


def test_an_atuin_session_row_is_the_whole_answer(xdg: Path, fake_bin: Path) -> None:
    """Where atuin 18 keeps the token: a `session` row in `meta.db`, with
    `files_migrated` beside it marking the move off the old file."""
    executable(fake_bin, 'atuin')
    atuin_meta(host_id='019f9508d27e', session='6A0yy0Abamd', files_migrated='true')

    assert changes(build(xdg, 'atuin')) == ()


def test_the_session_file_older_atuin_wrote_still_answers(xdg: Path, fake_bin: Path) -> None:
    """A machine that has not run an atuin new enough to migrate keeps the file,
    and it is still a login. Read first because it costs a stat where the other
    costs opening a database."""
    executable(fake_bin, 'atuin')
    (atuin_data() / 'session').write_text('token\n')

    assert changes(build(xdg, 'atuin')) == ()


@pytest.mark.parametrize('rows', [{}, {'host_id': '019f9508d27e'}, {'session': ''}])
def test_a_meta_db_holding_no_session_names_the_login_command(xdg: Path, fake_bin: Path, rows: dict[str, str]) -> None:
    """`meta.db` exists from the first run, logged in or not, so its presence is
    not the answer. An empty value is `logout`, which clears the row rather than
    dropping it."""
    executable(fake_bin, 'atuin')
    atuin_meta(**rows)

    (found,) = changes(build(xdg, 'atuin'))

    assert found.verdict is Verdict.MISSING
    assert 'atuin login' in found.advice


def test_a_missing_atuin_session_names_the_login_command(xdg: Path, fake_bin: Path) -> None:
    executable(fake_bin, 'atuin')

    (found,) = changes(build(xdg, 'atuin'))

    assert found.verdict is Verdict.MISSING
    assert 'atuin login' in found.advice


def test_a_meta_db_that_will_not_open_is_a_no_rather_than_a_raise(xdg: Path, fake_bin: Path) -> None:
    """`observe` guards `OSError` alone, so a sqlite complaint reaching it would
    cost every other tool on the roster its measurement."""
    executable(fake_bin, 'atuin')
    (atuin_data() / 'meta.db').write_text('not a database at all\n')

    (found,) = changes(build(xdg, 'atuin'))

    assert found.verdict is Verdict.MISSING


def atuin_config(written: str) -> Path:
    """The client config at the path `atuin info` prints, under the sandboxed root."""
    config = Path(os.environ['XDG_CONFIG_HOME']) / 'atuin' / 'config.toml'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(written)
    return config


def test_atuin_with_sync_turned_off_has_no_login_to_be_missing(xdg: Path, fake_bin: Path) -> None:
    """The one name on the roster whose login is optional. Every other tool here
    is useless logged out; atuin logged out is a local history store that still
    records, searches and answers `doit` about this machine."""
    executable(fake_bin, 'atuin')
    atuin_config('auto_sync = false\n')

    (found,) = changes(build(xdg, 'atuin'))

    assert found.verdict is Verdict.UNKNOWN
    assert found.repair is Repair.NONE
    assert not found.declined


@pytest.mark.parametrize('written', ['auto_sync = true\n', 'sync_frequency = "5m"\n', 'auto_sync = [unparseable\n'])
def test_anything_short_of_sync_off_still_asks_atuin_for_a_session(xdg: Path, fake_bin: Path, written: str) -> None:
    """atuin's own default is on, so a setting left out and a file that will not
    parse both leave the question armed. A typo in the TOML silencing the check
    is the failure worth pinning: it answers by accident and reads as deliberate."""
    executable(fake_bin, 'atuin')
    atuin_config(written)

    (found,) = changes(build(xdg, 'atuin'))

    assert found.verdict is Verdict.MISSING


@pytest.mark.parametrize('written', [b'', b'   \n'])
def test_an_empty_aws_credentials_file_is_not_a_credential(xdg: Path, fake_bin: Path, written: bytes) -> None:
    """`aws configure` leaves the file behind when the profile it wrote is removed,
    so existence alone reads as logged in on a machine that is not."""
    executable(fake_bin, 'aws')
    credentials = xdg / '.aws' / 'credentials'
    credentials.parent.mkdir(parents=True)
    credentials.write_bytes(written)

    (found,) = changes(build(xdg, 'aws'))

    assert found.verdict is Verdict.MISSING


def test_a_credential_file_that_does_not_decode_costs_no_row_at_all(xdg: Path, fake_bin: Path) -> None:
    """One stray byte took the whole resource's measurement, not one row.

    `read_text` raises `UnicodeDecodeError`, which is a `ValueError` and so walks
    straight through the `OSError` guard in `_asked`, out of `observe` and into
    `auth could not be examined` — nine measured tools lost to a file nothing here
    interprets. `apply` then exits 3 on a machine whose only fault is that file.
    Reading bytes answers the question actually being asked, and the file counts
    as a credential because it holds more than whitespace.
    """
    executable(fake_bin, 'aws')
    credentials = xdg / '.aws' / 'credentials'
    credentials.parent.mkdir(parents=True)
    credentials.write_bytes(b'\xff\xfe\x00\x80not utf-8')

    assert changes(build(xdg, 'aws')) == ()


def test_a_populated_aws_credentials_file_is_a_credential(xdg: Path, fake_bin: Path) -> None:
    executable(fake_bin, 'aws')
    credentials = xdg / '.aws' / 'credentials'
    credentials.parent.mkdir(parents=True)
    credentials.write_text('[default]\naws_access_key_id = AKIA\n')

    assert changes(build(xdg, 'aws')) == ()


def test_an_sso_cache_counts_as_being_logged_in(xdg: Path, fake_bin: Path) -> None:
    """Static keys, an SSO cache and the environment are three ways to be logged
    in rather than one fact spelled three ways."""
    executable(fake_bin, 'aws')
    cache = xdg / '.aws' / 'sso' / 'cache'
    cache.mkdir(parents=True)
    (cache / 'abc123.json').write_text('{}')

    assert changes(build(xdg, 'aws')) == ()


def test_an_empty_sso_cache_directory_is_not_a_session(xdg: Path, fake_bin: Path) -> None:
    executable(fake_bin, 'aws')
    (xdg / '.aws' / 'sso' / 'cache').mkdir(parents=True)

    (found,) = changes(build(xdg, 'aws'))

    assert found.verdict is Verdict.MISSING


def test_bbkt_is_asked_where_its_token_lives_rather_than_told(xdg: Path, fake_bin: Path) -> None:
    """`config path token` honours a `token_file` override this repo has no
    business guessing at, and `config check` is refused because its own help says
    it connects to the instance."""
    token = xdg / 'somewhere-else' / 'token'
    token.parent.mkdir()
    token.write_text('secret\n')
    executable(fake_bin, 'bbkt', f'#!/bin/sh\necho {token}\n')

    assert changes(build(xdg, 'bbkt')) == ()


def test_a_bbkt_token_path_that_holds_nothing_is_reported(xdg: Path, fake_bin: Path) -> None:
    """`bbkt config init` writes the token file before anything puts a token in
    it, so the path existing is not the same as the login working."""
    token = xdg / 'token'
    token.write_text('')
    executable(fake_bin, 'bbkt', f'#!/bin/sh\necho {token}\n')

    (found,) = changes(build(xdg, 'bbkt'))

    assert found.verdict is Verdict.MISSING
    assert 'bbkt config init' in found.advice


def test_a_jira_config_file_is_read_from_the_variable_that_names_it(xdg: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The default path is upstream convention rather than measured — jira is the
    work box's alone — so the override is what makes the probe correct there
    whatever that default turns out to be."""
    executable(fake_bin, 'jira')
    config = xdg / 'jira.yml'
    config.write_text('server: https://jira.example.com\n')
    monkeypatch.setenv('JIRA_CONFIG_FILE', str(config))

    assert changes(build(xdg, 'jira')) == ()


def test_a_jira_with_no_config_and_no_token_names_init(xdg: Path, fake_bin: Path) -> None:
    executable(fake_bin, 'jira')

    (found,) = changes(build(xdg, 'jira'))

    assert found.verdict is Verdict.MISSING
    assert 'jira init' in found.advice


def test_a_stored_oauth_session_is_a_claude_login(xdg: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    executable(fake_bin, 'claude')
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    (xdg / '.claude').mkdir(parents=True, exist_ok=True)
    (xdg / '.claude' / '.credentials.json').write_text('{"claudeAiOauth": {"scopes": []}}')

    assert changes(build(xdg, 'claude')) == ()


def test_an_mcp_only_credential_file_is_not_a_claude_login(xdg: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The same file carries MCP logins, and a machine can hold those with no
    Claude login at all — so existence answers a different question."""
    executable(fake_bin, 'claude')
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    (xdg / '.claude').mkdir(parents=True, exist_ok=True)
    (xdg / '.claude' / '.credentials.json').write_text('{"mcpOAuth": {"a-server": {}}}')

    (found,) = changes(build(xdg, 'claude'))

    assert found.verdict is Verdict.MISSING
    assert 'browser login' in found.advice


def test_a_half_written_credential_file_costs_no_other_tool_its_measurement(
    xdg: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A token refresh rewrites this file. Parsing it would raise `JSONDecodeError`
    inside the `OSError` guard and take the whole resource down to `auth could not
    be examined`, so a read landing mid-write must not interpret what it finds."""
    executable(fake_bin, 'claude')
    executable(fake_bin, 'atuin')
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    (xdg / '.claude').mkdir(parents=True, exist_ok=True)
    (xdg / '.claude' / '.credentials.json').write_bytes(b'{"claudeAiOauth": {"acce')

    found = {change.item: change for change in changes(build(xdg, 'claude', 'atuin'))}

    assert 'claude' not in found
    assert found['atuin'].verdict is Verdict.MISSING


def test_an_api_key_counts_as_a_claude_login(xdg: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    executable(fake_bin, 'claude')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'not-a-real-key')

    assert changes(build(xdg, 'claude')) == ()


def test_a_machine_with_no_credential_file_is_missing_rather_than_unknown(
    xdg: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable(fake_bin, 'claude')
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)

    (found,) = changes(build(xdg, 'claude'))

    assert found.verdict is Verdict.MISSING
    assert found.repair is Repair.BY_HAND
