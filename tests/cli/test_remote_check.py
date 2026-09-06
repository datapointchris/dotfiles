"""`dotfiles remote check` driven through the front door, against the fake transport.

The verb had never executed a statement. `tests/install/test_remote.py` covers
`remote.measure` thoroughly and stops there, and `measure` returning the right
`Reach` tuple is only half of what this command promises — the other half is the
number a caller branches on, which is computed here and nowhere else.

**Where this belongs.** `tests/matrix/__init__.py` names four things that send a
test out of `tests/matrix/`, and this file needs two of them. `PROBE_BACKOFF_SECONDS`
is a patched module constant, and it is the whole reason this file runs in one
second rather than ten. `test_the_probe_is_retried_before_the_remote_is_called_unreachable`
asserts a real subprocess argv, which is the independent witness the document's
own attempt count is checked against.

No altitude is given up. The real `dotfiles` app is invoked in process with
nothing in `src/dotfiles/` stubbed, exactly as `matrix.harness.invoke` does it.
What is given up is the synthetic *machine*: no manifest, no repo, no `$MACHINE`.
This verb reads two things — `config.toml` and `PATH` — so a whole sandbox would
be scenery. The day it starts reading a third, this file should move.

**What this verb alone decides**, and each is silent when it is wrong:

- **It exits 3 on a fault**, so a caller learns the answer without parsing output.
- **A machine that declared no remote is a fault here and nowhere else.** Every
  other verb treats an absent `[remote]` as an ordinary state — `config show`
  reports `declared: false` and exits 0, which
  `tests/matrix/test_machines_config_repo.py` already pins. This verb exists to be
  asked that question, so it answers 3.
- **An undeclared `mkdir` or `delete` is a fact, not a fault.** Backwards, every
  working remote that never needed one exits non-zero.
- **A root that will not list is a fault except where the directory holding it
  proves it absent.** `remote.listed` refuses on the unprovable state and names
  this verb as the way to tell it from a shelf nobody has published to, so 0 there
  is the end of a loop and not an answer. `remote.RootState` names the four
  outcomes and each is a row in `STATES`.
- **Every fact a row spells in English is a value beside it.** A caller reading
  the probe attempts, the entry count or the root's state out of a sentence breaks
  the day the sentence is reworded.

Nothing here monkeypatches `remote.read`, `remote.measure` or `remote.answered`.
The transport is a real program on a real `PATH` serving a real directory —
`tests/relay.py` — because those four functions are the seam that hid the defect
this whole effort is about.
"""

from __future__ import annotations

import dataclasses as dc
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from relay import declare
from relay import deny_listing
from relay import install_relay
from relay import install_spy
from relay import recorded
from typer.testing import CliRunner
from typer.testing import Result

from dotfiles import remote as transport
from dotfiles.main import app
from dotfiles.vocabulary import ExitCode

REQUIRED_ONLY = """
[remote]
root = "/artifacts"

[remote.transport]
program = "relay"
probe = ["probe"]
list = ["list", "{dir}"]
upload = ["upload", "{local}", "{dir}"]
download = ["download", "{remote}", "{local}"]
"""
"""The four operations a remote is useless without, and neither optional one.

`relay.TABLE` declares all six on purpose, so it cannot express the row this file
exists for: a machine that declined to give this tool the ability to create or
remove things on a server, and is working perfectly.
"""


@pytest.fixture
def config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`$XDG_CONFIG_HOME` is the knob `settings.config_file()` already reads."""
    root = tmp_path / 'config'
    root.mkdir()
    monkeypatch.setenv('XDG_CONFIG_HOME', str(root))
    return root


@pytest.fixture
def server(tmp_path: Path) -> Path:
    """The directory the fake transport serves. `install_relay` creates it.

    Deliberately not created here: the relay's probe answers on the directory
    existing, so a fixture that made it would decide the reachability of every row
    before the row got a say.
    """
    return tmp_path / 'server'


@pytest.fixture(autouse=True)
def a_probe_that_does_not_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zero the retry sleep. The clock, and nothing else.

    `answered` reads this constant at call time, so patching it is enough and a
    rename fails here rather than degrading into ten seconds of real sleeping.

    Three real probes still run against a real program; only the seconds between
    them go. `test_the_probe_is_retried_before_the_remote_is_called_unreachable`
    is what proves the loop was not cut along with the wait.
    """
    monkeypatch.setattr(transport, 'PROBE_BACKOFF_SECONDS', 0)


@dc.dataclass(frozen=True)
class Bench:
    """Everything a row is allowed to arrange: a config file, a `PATH`, a server."""

    config: Path
    bin: Path
    server: Path
    record: Path
    monkeypatch: pytest.MonkeyPatch

    def write_table(self, body: str) -> Path:
        written = self.config / 'dotfiles'
        written.mkdir(parents=True, exist_ok=True)
        path = written / 'config.toml'
        path.write_text(body)
        return path


@pytest.fixture
def bench(config_home: Path, fake_bin: Path, server: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Bench:
    return Bench(config=config_home, bin=fake_bin, server=server, record=tmp_path / 'argv.jsonl', monkeypatch=monkeypatch)


# ─────────────────────────────────────────────────────────────────────────────
# The eight states a machine's remote can be in
# ─────────────────────────────────────────────────────────────────────────────


def nothing_declared(bench: Bench) -> None:
    """No config.toml at all, which is every box that never exchanges a bundle."""


def a_table_that_will_not_load(bench: Bench) -> None:
    """Two faults in one table, because reporting the first would cost two runs."""
    bench.write_table('[remote]\nroot = 5\n')


def a_program_that_is_not_on_path(bench: Bench) -> None:
    """The binary exists and `PATH` does not carry it, which is what `which` answers.

    Stronger than naming a program nobody installed: the file is on disk, so a
    `transport` row that read the filesystem rather than `PATH` would pass the
    other spelling of this state and fail here.
    """
    install_relay(bench.bin, bench.server)
    declare(bench.config)
    bench.monkeypatch.setenv('PATH', f'/usr/bin{os.pathsep}/bin')
    assert (bench.bin / 'relay').is_file(), 'the binary is on disk; only PATH stops it being named'


def installed_and_not_answering(bench: Bench) -> None:
    """Presence without readiness — `command -v` perfect, first upload fails."""
    install_spy(bench.bin, bench.record, code=1)
    declare(bench.config, program='spy')


def a_fresh_root(bench: Bench) -> None:
    """The remote answers and nothing has been put on it. Every first run."""
    install_relay(bench.bin, bench.server)
    declare(bench.config)


def a_root_with_entries(bench: Bench) -> None:
    install_relay(bench.bin, bench.server)
    (bench.server / 'artifacts' / 'bundles').mkdir(parents=True)
    declare(bench.config)


def no_mkdir_and_no_delete_declared(bench: Bench) -> None:
    """A working remote on a machine that declared neither optional operation."""
    install_relay(bench.bin, bench.server)
    (bench.server / 'artifacts').mkdir(parents=True)
    bench.write_table(REQUIRED_ONLY)


def a_root_that_will_not_list(bench: Bench) -> None:
    """The probe answers and every listing is refused, the root's parent included.

    Nothing here can say whether the root is there, so the state is `UNPROVEN`.
    `a_fresh_root` is the other half of the pair: the same failed root listing over
    a parent that lists perfectly well.
    """
    install_relay(bench.bin, bench.server)
    deny_listing(bench.server)
    declare(bench.config)


def a_root_that_exists_and_is_refused(bench: Bench) -> None:
    """The parent lists and holds the root, and the root itself is refused.

    The commoner half of the ambiguity, and the one a parent's exit code alone
    reports as absence. A credential that reads a shared server and not one
    directory on it writes this, and so does a directory whose mode excludes the
    caller.
    """
    install_relay(bench.bin, bench.server)
    (bench.server / 'artifacts').mkdir(parents=True)
    deny_listing(bench.server, only='/artifacts')
    declare(bench.config)


def a_relative_root(bench: Bench) -> None:
    """A root carrying no separator, so there is no parent this can name.

    `Remote.above` answers `None` rather than `''`, because the empty string is not
    a path and a transport handed one either refuses it or answers about somewhere
    else. With no parent to ask, a failed listing is `UNPROVEN` — the honest answer
    where the alternative is proof built on an invented argument.
    """
    install_relay(bench.bin, bench.server)
    declare(bench.config, root='artifacts')


@dc.dataclass(frozen=True)
class State:
    """One machine, and everything `remote check` answers about it.

    The measured rows and the exit code together, because the split is the claim:
    a row recording only the exit code would pass equally well if `check` had
    measured something else and arrived at the same number.
    """

    arrange: Callable[[Bench], None]
    measured: tuple[tuple[str, bool, bool], ...]
    """Every condition, as `(subject, ok, required)`, in the order it is reported."""

    exit_code: ExitCode
    identity: tuple[bool, str, str]
    """`(declared, root, program)` — what the document says the machine configured."""

    problem: tuple[str, ...] = ()
    """Substrings the `problem` field must carry, and `()` asserts it is empty.

    A column rather than a set of functions beside the table, so a new state is a
    row and cannot be added in a shape three screens down that still asserts the
    old one. Substrings because the field is a sentence a person reads; what a
    caller branches on is `exit_code` and `faults`.
    """

    root: transport.RootState | None = None
    """Which of the four the `root` row found, or `None` where no such row is reported.

    A column of its own because `ok` and `required` cannot hold four values, and
    the pair that matters — a root proved absent and a root nobody could prove
    anything about — differ in `required` alone. `required` says whether a row is a
    fault, so a policy change there would move the discriminator without moving the
    state and every row here would still pass.
    """


STATES: dict[str, State] = {
    'nothing-is-declared': State(nothing_declared, (('config', False, True),), ExitCode.ISSUE, (False, '', '')),
    'the-table-will-not-load': State(
        a_table_that_will_not_load,
        (('config', False, True), ('config', False, True)),
        ExitCode.ISSUE,
        (True, '', ''),
        problem=('remote.root', 'remote.transport'),
    ),
    'the-program-is-not-on-path': State(
        a_program_that_is_not_on_path,
        (('transport', False, True), ('configured', True, True)),
        ExitCode.ISSUE,
        (True, '/artifacts', 'relay'),
    ),
    'installed-and-not-answering': State(
        installed_and_not_answering,
        (('transport', True, True), ('configured', True, True), ('reachable', False, True)),
        ExitCode.ISSUE,
        (True, '/artifacts', 'spy'),
    ),
    'a-fresh-root': State(
        a_fresh_root,
        (
            ('transport', True, True),
            ('configured', True, True),
            ('reachable', True, True),
            ('root', False, False),
            ('mkdir', True, False),
            ('delete', True, False),
        ),
        ExitCode.CONVERGED,
        (True, '/artifacts', 'relay'),
        root=transport.RootState.ABSENT,
    ),
    'a-root-with-entries': State(
        a_root_with_entries,
        (
            ('transport', True, True),
            ('configured', True, True),
            ('reachable', True, True),
            ('root', True, False),
            ('mkdir', True, False),
            ('delete', True, False),
        ),
        ExitCode.CONVERGED,
        (True, '/artifacts', 'relay'),
        root=transport.RootState.LISTED,
    ),
    'no-mkdir-and-no-delete-declared': State(
        no_mkdir_and_no_delete_declared,
        (
            ('transport', True, True),
            ('configured', True, True),
            ('reachable', True, True),
            ('root', True, False),
            ('mkdir', False, False),
            ('delete', False, False),
        ),
        ExitCode.CONVERGED,
        (True, '/artifacts', 'relay'),
        root=transport.RootState.LISTED,
    ),
    'a-root-that-will-not-list': State(
        a_root_that_will_not_list,
        (
            ('transport', True, True),
            ('configured', True, True),
            ('reachable', True, True),
            ('root', False, True),
            ('mkdir', True, False),
            ('delete', True, False),
        ),
        ExitCode.ISSUE,
        (True, '/artifacts', 'relay'),
        root=transport.RootState.UNPROVEN,
    ),
    'a-root-that-exists-and-is-refused': State(
        a_root_that_exists_and_is_refused,
        (
            ('transport', True, True),
            ('configured', True, True),
            ('reachable', True, True),
            ('root', False, True),
            ('mkdir', True, False),
            ('delete', True, False),
        ),
        ExitCode.ISSUE,
        (True, '/artifacts', 'relay'),
        root=transport.RootState.REFUSED,
    ),
    'a-relative-root': State(
        a_relative_root,
        (
            ('transport', True, True),
            ('configured', True, True),
            ('reachable', True, True),
            ('root', False, True),
            ('mkdir', True, False),
            ('delete', True, False),
        ),
        ExitCode.ISSUE,
        (True, 'artifacts', 'relay'),
        root=transport.RootState.UNPROVEN,
    ),
}
"""Every state, and the number a caller branches on for each.

Two rows carry the whole reason `required` exists.
`no-mkdir-and-no-delete-declared` is a working remote answering `False` twice and
exiting 0; `installed-and-not-answering` is one `False` and exit 3. Collapse the
distinction and the first row moves to 3, which is every machine that never needed
a `mkdir`.

**Four rows reach `check` with a root that will not list, and they are the set to
read together.** Every one answers its probe and gets one exit status back from the
transport, so nothing in the failure itself separates them. `a-fresh-root` has a
parent that lists and does not hold the root, which is absence proved and exit 0.
`a-root-that-exists-and-is-refused` has a parent that lists and does hold it, which
is exit 3 — and it is the row a parent's exit code alone reports as absence.
`a-root-that-will-not-list` has a parent that will not list either.
`a-relative-root` has no parent to name at all. The last two are `UNPROVEN` and
differ only in why, which is why `RootState` is a column and `required` is not
enough to hold the set.
"""


def check(*argv: str) -> Result:
    """One real invocation of the real app.

    `catch_exceptions=False`, so an unhandled exception arrives as a traceback
    rather than as exit 1 — which this verb cannot produce by design, and which
    would otherwise read as a plausible answer. A fresh runner per call, because
    typer builds its Click command lazily and a shared one is state.
    """
    return CliRunner().invoke(app, ['remote', 'check', *argv], catch_exceptions=False)


def document(ran: Result) -> dict[str, Any]:
    """Whatever `--json` put on **stdout**, parsed.

    Stdout alone rather than both streams: the split is the machine contract, and
    one stray diagnostic there turns a caller's parse into a syntax error.
    """
    return json.loads(ran.stdout)


def rows(ran: Result) -> dict[str, dict[str, Any]]:
    """The measured rows of a `--json` run, by subject."""
    return {found['subject']: found for found in document(ran)['measured']}


def faults(row: State) -> int:
    return sum(1 for _subject, ok, required in row.measured if required and not ok)


@pytest.mark.parametrize('state', list(STATES), ids=list(STATES))
def test_the_document_names_every_condition_and_the_exit_code_follows_the_faults(state: str, bench: Bench) -> None:
    """The whole machine contract of this verb, one state at a time.

    `faults` is derived from the row's own `required`/`ok` columns rather than
    written down beside them, which makes it a cross-check instead of a
    restatement: the command computes the count from `Reach.faulty` and the rows
    from `Reach.ok` and `Reach.required`, so a `faulty` that stopped agreeing with
    the two fields it is built from fails here.
    """
    row = STATES[state]
    row.arrange(bench)

    ran = check('--json')
    answered = document(ran)

    assert ran.exit_code == row.exit_code
    assert [(found['subject'], found['ok'], found['required']) for found in answered['measured']] == list(row.measured)
    assert answered['faults'] == faults(row)
    assert (answered['declared'], answered['root'], answered['program']) == row.identity
    assert rows(ran).get('root', {}).get('facts', {}).get('state') == row.root
    for named in row.problem:
        assert named in answered['problem']
    if not row.problem:
        assert answered['problem'] == '', 'a state with nothing to say about the config says nothing'


@pytest.mark.parametrize('state', list(STATES), ids=list(STATES))
def test_the_rendered_answer_reaches_the_same_verdict_and_leaves_stdout_free_of_a_document(state: str, bench: Bench) -> None:
    """`--json` is a rendering switch, not a second measurement.

    The exit code is the load-bearing half: a caller that branches on it must get
    the same answer whichever way it asked. The other half is channel discipline —
    a bare run puts a table on stdout and must not put a document there, because
    the parse `--json` promises is decided by what a run *without* it emits too.
    """
    row = STATES[state]
    row.arrange(bench)

    ran = check()

    assert ran.exit_code == row.exit_code
    assert ran.stdout.strip(), 'a person asking got nothing back'
    assert not ran.stdout.lstrip().startswith(('{', '[')), 'only --json emits a document'


def test_the_probe_is_retried_before_the_remote_is_called_unreachable(bench: Bench) -> None:
    """One dropped packet is indistinguishable from an outage in a single call.

    The argv the transport was handed is the independent witness, and the count in
    the document has to agree with it. Asserting only the document would pass
    against a verb that wrote `3` without probing three times; asserting only the
    argv is what left the count reachable through English alone. Three entries is
    also what proves `a_probe_that_does_not_wait` zeroed the sleep and not the loop.
    """
    installed_and_not_answering(bench)

    ran = check('--json')

    assert ran.exit_code == ExitCode.ISSUE
    assert recorded(bench.record) == [['probe'], ['probe'], ['probe']]
    reachable = document(ran)['measured'][-1]
    assert reachable['subject'] == 'reachable'
    assert reachable['facts']['attempts'] == len(recorded(bench.record))


def test_every_number_a_row_states_in_prose_is_a_value_beside_it(bench: Bench) -> None:
    """No row spells a measurement in `detail` without carrying it in `facts`.

    Built by walking what `measure` reported rather than from a list of subjects,
    so a row added later is covered by existing. A literal here passed against a
    fourth row whose prose carried a count and whose `facts` was empty, which is
    the whole failure this guards.

    The interpolated value is asserted inside the sentence too. A `facts` written
    by hand beside prose built from something else agrees with no assertion that
    reads only one of the two.
    """
    a_root_with_entries(bench)

    measured = rows(check('--json'))

    assert {name for name, row in measured.items() if row['facts']} == {'transport', 'reachable', 'root'}
    assert Path(measured['transport']['facts']['path']).resolve() == (bench.bin / 'relay').resolve()
    assert measured['transport']['facts']['path'] in measured['transport']['detail']
    assert measured['reachable']['facts'] == {'attempts': 1}
    assert measured['root']['facts'] == {'state': 'listed', 'entries': 1}
    assert '1 entry(s)' in measured['root']['detail']
    for name, row in measured.items():
        spelled = [word for word in row['detail'].replace('(s)', ' ').split() if word.isdigit()]
        assert not spelled or row['facts'], f'{name} states {spelled} in prose and carries no value'


UNLISTABLE = (
    ('a-parent-that-lists-and-holds-it', a_root_that_exists_and_is_refused, transport.RootState.REFUSED, 'is on the remote'),
    ('a-parent-that-will-not-list', a_root_that_will_not_list, transport.RootState.UNPROVEN, 'neither would /'),
    ('no-parent-to-name', a_relative_root, transport.RootState.UNPROVEN, 'no parent to ask'),
)
"""The three ways a root that will not list becomes a fault, and what each says.

The fourth way it can go — a parent that lists and does not hold the root — is
`a-fresh-root`, and it is the only one of the four that stays converged.
"""


@pytest.mark.parametrize(('shape', 'arrange', 'state', 'said'), UNLISTABLE, ids=[row[0] for row in UNLISTABLE])
def test_a_root_that_will_not_list_reports_which_state_it_is_in_and_what_to_run(
    shape: str, arrange: Callable[[Bench], None], state: transport.RootState, said: str, bench: Bench
) -> None:
    """The verb `remote.listed` sends the reader to, answering rather than agreeing.

    `listed` refuses on the unprovable state and says to run this. Reporting it
    converged left a refusal pointing at a clean bill of health, so each of these
    is a fault carrying the state as a value and the remedy beside it.

    The advice names a command rather than an action, and it is built from the
    machine's declared template — so it stays right when the template changes and
    it is a line the reader can paste. The transport's own words ride along, since
    they are what separates a permission boundary from a transient fault.
    """
    arrange(bench)

    ran = check('--json')
    root = rows(ran)['root']

    assert ran.exit_code == ExitCode.ISSUE
    assert (root['ok'], root['required']) == (False, True)
    assert root['facts'] == {'state': state}
    assert said in root['detail']
    assert root['advice'].endswith(f'relay list {bench_root(bench)}')


def bench_root(bench: Bench) -> str:
    """The root the config under test declares, as the advice would spell it."""
    return 'artifacts' if 'root = "artifacts"' in (bench.config / 'dotfiles' / 'config.toml').read_text() else '/artifacts'


def test_a_refused_root_carries_the_transports_own_words(bench: Bench) -> None:
    """The reason is the half that tells a permission boundary from an outage.

    Every other refusal in `remote.py` carries `ran.transcript`, and the row that
    exists to draw exactly that distinction was the one dropping it — while its
    advice told the reader to go and run the command the tool had just run.
    """
    a_root_that_exists_and_is_refused(bench)

    root = rows(check('--json'))['root']

    assert '403 token expired' in root['detail']
