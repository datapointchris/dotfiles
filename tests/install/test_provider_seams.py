"""Four seams an apply runs through and no other test reaches.

Each one is the far end of a path the suite drives only from above, and each
fails quietly rather than loudly. A package transaction that stops streaming
looks like a hung run. A group of items whose provider answers nothing looks
like a converged machine. A headless nvim missing its `qa` never returns at all.
A `df` whose output shape moved stops naming the mount and reports the same
sentence it would have reported anyway.

The seams are faked and the logic is not. `Privilege` is a double because sudo
is not this suite's to spend; `effects.run` is a recorder for the two managers
whose argv the install guard in `tests/install/conftest.py` refuses outright.
Everything that decides — which manager escalates, which output mode each door
needs, which change reaches a provider, which line lazy shows — is the real
code.
"""

from __future__ import annotations

import dataclasses as dc
import inspect
import shutil
import stat
from pathlib import Path
from typing import Any

import pytest

from dotfiles import diagnose
from dotfiles import effects
from dotfiles import registry
from dotfiles.effects import Completed
from dotfiles.effects import Output
from dotfiles.plan import DesiredItem
from dotfiles.plan import Precondition
from dotfiles.plan import Reason
from dotfiles.plan import Stage
from dotfiles.privilege import Authorization
from dotfiles.privilege import Privilege
from dotfiles.privilege import PrivilegeUnavailable
from dotfiles.privilege import refusal
from dotfiles.providers import Kind
from dotfiles.providers import pluginsync
from dotfiles.providers import syspkg
from dotfiles.resources import Change
from dotfiles.resources import Outcome
from dotfiles.resources import OutcomeStatus
from dotfiles.resources import Repair
from dotfiles.resources import Verdict
from dotfiles.session import Session


def executable(directory: Path, name: str, script: str) -> Path:
    """See `_executable` in tests/conftest.py for why this is copied rather than imported."""
    target = directory / name
    target.write_text(script)
    target.chmod(target.stat().st_mode | stat.S_IEXEC)
    return target


# ─────────────────────────────────────────────────────────────────────────────
# syspkg: the transaction every apt and pacman install goes through
# ─────────────────────────────────────────────────────────────────────────────


class Escalation:
    """A `Privilege` that records what it was handed instead of asking for root.

    Not a `Privilege` subclass. What is being measured is exactly what `install`
    passes across that boundary, and inheriting the real `run` would answer it
    with this machine's sudo — which no unit test may spend.

    `kwargs['reason']` is read rather than defaulted, so an `install` that stopped
    naming what the password is for fails here instead of prompting a person with
    a bare sudo in the middle of a long run.
    """

    def __init__(self, *, state: Authorization = Authorization.GRANTED, returncode: int = 0) -> None:
        self.state = state
        self.returncode = returncode
        self.calls: list[tuple[tuple[str, ...], dict[str, Any]]] = []

    def run(self, command: list[str] | tuple[str, ...], **kwargs: Any) -> Completed:
        if self.state not in (Authorization.ALREADY_ROOT, Authorization.GRANTED):
            raise PrivilegeUnavailable(kwargs['reason'])
        argv = tuple(str(part) for part in command)
        self.calls.append((argv, kwargs))
        return Completed(argv, self.returncode, '')


MANAGERS = [
    ('pacman', 'pacman', True),
    ('aur', 'yay', False),
    ('apt', 'apt-get', True),
    ('brew', 'brew', False),
    ('cask', 'brew', False),
    ('mas', 'mas', False),
    ('flatpak', 'flatpak', False),
]
"""Every manager that installs, the binary it installs with, and whether it escalates.

Written out rather than read off `ESCALATES`, because which manager escalates is
the logic under test: `sudo brew` is an error message and `sudo yay` is a build
running as root, and a table derived from the one being checked agrees with any
answer. The binary column carries the two aliases — `aur` installs with yay and
`cask` with brew — which is the other thing a name-shaped table would hide.
"""


@pytest.mark.parametrize(('manager', 'binary', 'escalates'), MANAGERS, ids=[row[0] for row in MANAGERS])
def test_a_transaction_reaches_exactly_one_door_and_is_streamed_through_it(manager: str, binary: str, escalates: bool, upstream) -> None:
    """The escalating door has to ask for streaming and the plain one must not.

    `Privilege.run` defaults to QUIET and `effects.run` defaults to STREAM, so the
    same instruction is spelled two opposite ways. Drop the explicit `output` and
    apt and pacman — the two managers that install the most — go silent through a
    transaction over every declared package while brew and flatpak keep narrating.

    Which door is taken is the other half, and it is not a preference: `sudo brew`
    is an error message and `sudo yay` is a build running as root.
    """
    escalation = Escalation()
    recorder = upstream()

    result = syspkg.install(manager, ['ripgrep', 'fd'], escalation)

    assert result.kind is Kind.APPLIED
    assert (escalation.calls == []) is not escalates
    assert (recorder.calls == []) is escalates

    if escalates:
        argv, passed = escalation.calls[0]
        assert passed['output'] is Output.STREAM
    else:
        argv, passed = recorder.calls[0], recorder.kwargs[0]
        assert 'output' not in passed, 'effects.run already defaults to STREAM'

    assert argv[0] == binary
    assert argv[-2:] == ('ripgrep', 'fd')


def test_the_two_doors_a_transaction_can_take_default_to_opposite_output_modes() -> None:
    """What makes the explicit `Output.STREAM` above load-bearing rather than noise.

    Nothing else states it, and the two defaults are the whole reason one branch
    passes the argument and the other does not. A change to either signature
    silently inverts what a whole-machine install looks like on screen.
    """
    assert inspect.signature(Privilege.run).parameters['output'].default is Output.QUIET
    assert inspect.signature(effects.run).parameters['output'].default is Output.STREAM


@pytest.mark.parametrize('state', [Authorization.UNAVAILABLE, Authorization.DECLINED, Authorization.NOT_NEEDED])
def test_a_machine_that_cannot_escalate_reports_a_refusal_rather_than_ending_the_walk(state: Authorization, upstream) -> None:
    """`PrivilegeUnavailable` becomes a `Result` here, and that is the whole point:
    a box with no sudo installs everything unprivileged and reports the rest, where
    an exception escaping would take the walk with it.

    The detail is compared against `refusal` rather than a sentence, so the three
    states stay distinguishable to a reader without pinning any of the wording.
    """
    recorder = upstream()

    result = syspkg.install('pacman', ['ripgrep'], Escalation(state=state))

    assert not result.ok
    assert result.kind is Kind.PRIVILEGE_UNAVAILABLE
    assert result.detail == refusal(state)
    assert recorder.calls == [], 'a refused transaction must not fall through to an unprivileged run'


def test_a_privileged_manager_that_exits_non_zero_carries_its_status(upstream) -> None:
    """The status is the only thing separating "apt could not resolve that" from
    "apt was never run", and the detail is where a report reads it."""
    recorder = upstream()

    result = syspkg.install('apt', ['ripgrep'], Escalation(returncode=100))

    assert not result.ok
    assert result.kind is Kind.COMMAND_FAILED
    assert '100' in result.detail
    assert recorder.calls == []


def test_an_unprivileged_manager_that_exits_non_zero_fails_the_item_not_the_run(upstream) -> None:
    """brew failing is a failed item, which `_transact` then retries one package at
    a time — so it has to come back as a Result rather than as a raise."""
    upstream(reachable=False, said='Error: No available formula with the name "ripgrepp"')

    result = syspkg.install('brew', ['ripgrepp'], Escalation())

    assert not result.ok
    assert result.kind is Kind.COMMAND_FAILED


AVAILABILITY = [
    ('answers its version probe', '#!/bin/sh\nexit 0\n', True),
    ('is on PATH and will not run', '#!/bin/sh\nexit 1\n', False),
    ('is not installed at all', '', False),
]


@pytest.mark.parametrize(('condition', 'script', 'expected'), AVAILABILITY, ids=[row[0] for row in AVAILABILITY])
def test_a_manager_is_available_only_when_its_binary_answers(condition: str, script: str, expected: bool, fake_bin: Path) -> None:
    """Asked of the binary rather than of `which`, because a `brew` that is present
    and broken is the same answer to a caller as one that is absent.

    Both managers are asserted on every row: `cask` is brew, so a machine with brew
    has casks available and a machine without has neither. Answered off
    `INSTALL[manager][0]`, which is what makes that true without a second table.
    """
    if script:
        executable(fake_bin, 'brew', script)

    assert syspkg.available('brew') is expected, f'brew {condition}'
    assert syspkg.available('cask') is expected, f'brew {condition}, and a cask is a brew formula'


# ─────────────────────────────────────────────────────────────────────────────
# registry: the default install path, which every non-batching provider takes
# ─────────────────────────────────────────────────────────────────────────────


@dc.dataclass(frozen=True)
class Recording(registry.Provider):
    """A provider that installs nothing and remembers which items reached it.

    A subclass rather than a mock, so it inherits the `install_all` under test
    instead of standing in for it.
    """

    seen: list[str] = dc.field(default_factory=list)

    def install(self, session: Session, change: Change, item: DesiredItem, privilege: Privilege) -> Outcome:
        self.seen.append(item.name)
        return Outcome(change, OutcomeStatus.DONE, '')


def planned(name: str, provider: str = 'stub') -> DesiredItem:
    return DesiredItem(
        section='system_packages',
        provider=provider,
        resource='packages',
        stage=Stage.SYSTEM,
        name=name,
        executable='',
        evidence_path='',
        precondition=Precondition.NONE,
        entry=None,
        reason=Reason('system_packages', 'test'),
    )


def wanted(desired: DesiredItem | None, address: str = '') -> Change:
    """A change addressed the way the plan addresses one, which `Change` enforces.

    `address` is only ever passed for a retracted change, which carries no item to
    read one off.
    """
    return Change(
        'packages',
        Stage.SYSTEM,
        address or (desired.address if desired else ''),
        Verdict.MISSING,
        repair=Repair.AUTOMATIC,
        desired=desired,
    )


def test_a_group_is_installed_one_at_a_time_in_the_order_it_arrived(unprivileged: Privilege) -> None:
    """The default for every provider but the package managers: a release download,
    a clone and a `defaults write` cost the same alone as in company.

    Order is the contract a caller reads the result by — `engine` pairs outcomes
    with changes positionally — so a batch that answered out of order would name
    the wrong item in every row.
    """
    provider = Recording(name='stub', resource='packages', stage=Stage.SYSTEM)
    changes = [wanted(planned(name)) for name in ('ripgrep', 'fd', 'bat')]

    outcomes = provider.install_all(Session(machine_name='box'), changes, unprivileged)

    assert provider.seen == ['ripgrep', 'fd', 'bat']
    assert [outcome.change for outcome in outcomes] == changes
    assert [outcome.status for outcome in outcomes] == [OutcomeStatus.DONE] * 3


def test_an_item_nothing_declares_any_more_is_refused_without_reaching_the_provider(unprivileged: Privilege) -> None:
    """The retraction path. A change survives from the observe pass carrying no
    desired item when the declaration dropped it underneath the run, and installing
    it would put a package back on a machine that just stopped asking for one.

    The two neighbours are asserted alongside, because a refusal that also skipped
    them would satisfy any assertion about the retracted one on its own.
    """
    provider = Recording(name='stub', resource='packages', stage=Stage.SYSTEM)
    changes = [
        wanted(planned('ripgrep')),
        wanted(None, address='stub/retracted'),
        wanted(planned('bat')),
    ]

    outcomes = provider.install_all(Session(machine_name='box'), changes, unprivileged)

    assert provider.seen == ['ripgrep', 'bat']
    assert [outcome.status for outcome in outcomes] == [OutcomeStatus.DONE, OutcomeStatus.REFUSED, OutcomeStatus.DONE]
    assert [outcome.change for outcome in outcomes] == changes


def test_a_provider_that_plans_items_and_cannot_repair_them_raises(unprivileged: Privilege) -> None:
    """The base `install` is deliberately not an inherited no-op: a mechanism the
    walk would silently decline to run has to be a loud failure, which `engine._act`
    turns into a Refusal naming the provider."""
    described = registry.Provider(name='described', resource='packages', stage=Stage.SYSTEM)
    change = wanted(planned('ripgrep', provider='described'))

    with pytest.raises(NotImplementedError):
        registry.install_one(described, Session(machine_name='box'), change, unprivileged)


def test_a_group_the_registry_cannot_route_is_answered_per_change(unprivileged: Privilege) -> None:
    """`install_all` reads the provider off the first change and falls back to
    resolving each one alone when that fails — a group carrying a retracted item
    first, or a provider this checkout no longer has, must still return one outcome
    per change rather than an IndexError or a short list."""
    changes = [
        wanted(None, address='no-such-provider/retracted'),
        wanted(planned('ripgrep', provider='no-such-provider')),
    ]

    outcomes = registry.install_all(Session(machine_name='box'), changes, unprivileged)

    assert [outcome.status for outcome in outcomes] == [OutcomeStatus.REFUSED, OutcomeStatus.REFUSED]
    assert [outcome.change for outcome in outcomes] == changes


def test_an_empty_group_asks_no_provider_anything(unprivileged: Privilege) -> None:
    """`changes[0]` is read to name the provider, so an empty group is one index
    away from ending the walk with an IndexError."""
    assert registry.install_all(Session(machine_name='box'), [], unprivileged) == []


# ─────────────────────────────────────────────────────────────────────────────
# pluginsync: the headless nvim, whose argv is the whole of whether it returns
# ─────────────────────────────────────────────────────────────────────────────


def test_the_headless_sync_tells_lazy_not_to_wait_and_nvim_to_quit(fake_bin: Path) -> None:
    """Both halves of the argv are load-bearing and neither fails visibly: without
    the bang lazy waits for a keypress, and without `-c qa` nvim never exits. Either
    way a `dotfiles apply` stops on this row and reports nothing.

    Asserted as argv against a real nvim on PATH, so the flags are measured where
    they are actually handed over.
    """
    log = fake_bin / 'argv'
    executable(fake_bin, 'nvim', f'#!/bin/sh\nprintf \'%s\\n\' "$@" > {log}\nexit 0\n')

    result = pluginsync.sync_nvim()

    assert result.ok
    assert result.kind is Kind.APPLIED
    assert log.read_text().splitlines() == ['--headless', '-c', 'Lazy! sync', '-c', 'qa']


def test_a_machine_without_neovim_is_told_the_verb_that_installs_it(fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """PREREQUISITE_MISSING rather than a failure, because an earlier stage of the
    same run owes this one the binary — so the row becomes true on the next apply
    without anybody fixing anything.

    PATH is narrowed to the empty fake directory rather than shadowing nvim with a
    stub: the branch under test is `shutil.which` answering nothing, and a real nvim
    reached from behind the fake would run `Lazy! sync` against the developer's own
    config.
    """
    monkeypatch.setenv('PATH', str(fake_bin))
    assert shutil.which('nvim') is None, 'PATH still reaches a real nvim, which this test must never run'

    result = pluginsync.sync_nvim()

    assert not result.ok
    assert result.kind is Kind.PREREQUISITE_MISSING
    assert 'dotfiles packages apply' in result.detail


def test_lazys_own_transcript_is_what_a_failed_sync_carries(fake_bin: Path) -> None:
    """A lua error names the plugin and the line; `lazy exited 1` names neither, and
    is the whole of what a reader would otherwise get days later."""
    executable(fake_bin, 'nvim', '#!/bin/sh\necho "E5108: Error executing lua .../blink.cmp/init.lua:12" >&2\nexit 1\n')

    result = pluginsync.sync_nvim()

    assert result.kind is Kind.COMMAND_FAILED
    assert 'E5108' in result.detail
    assert 'blink.cmp' in result.detail


def test_a_sync_that_failed_silently_still_names_its_exit_status(fake_bin: Path) -> None:
    """nvim exits non-zero having printed nothing when it dies before lazy loads.
    An empty detail would report a failed row with no evidence at all."""
    executable(fake_bin, 'nvim', '#!/bin/sh\nexit 3\n')

    result = pluginsync.sync_nvim()

    assert result.kind is Kind.COMMAND_FAILED
    assert '3' in result.detail


LAZY_LINES = [
    ('a task line', 'gitsigns.nvim | Running task install\n', '  gitsigns.nvim\n'),
    ('a coloured task line', '\033[35mgitsigns.nvim\033[0m \033[2m| Running task install\033[0m\n', '  gitsigns.nvim\n'),
    ('git spew', 'Cloning into /home/chris/.local/share/nvim/lazy/blink.cmp...\n', None),
    ('coloured git spew', '\033[31mfatal: unable to access\033[0m\n', None),
]
"""One line each of what lazy writes headless, and what the filter shows for it.

The second row is the one worth having. lazy colours its own prefix, so the raw
line separates prefix from message with `\\033[0m \\033[2m|` — the escape codes go
first because the filter cannot see the ` | ` until they are gone. Reverse the two
and this line matches nothing, is swallowed, and a fresh machine clones fifty
repos with an empty screen.
"""


@pytest.mark.parametrize(('shape', 'line', 'shown'), LAZY_LINES, ids=[row[0] for row in LAZY_LINES])
def test_only_the_line_lazy_starts_a_task_with_reaches_the_screen(shape: str, line: str, shown: str | None) -> None:
    assert pluginsync._lazy_line(line) == shown, shape


# ─────────────────────────────────────────────────────────────────────────────
# diagnose: a full filesystem, and which one is the useful half
# ─────────────────────────────────────────────────────────────────────────────


DF_ANSWERS = [
    ('the two columns it was asked for', 'printf "Mounted on Avail\\n/mnt/data 12K\\n"', True, False),
    (
        'its own default table instead',
        'printf "Filesystem Size Avail Use%% Mounted on\\n/dev/sda2 100G 12K 100%% /mnt/data\\n"',
        False,
        False,
    ),
    ('nothing at all', 'exit 0', False, False),
    ('a non-zero exit', 'echo "df: unrecognized option" >&2\nexit 1', False, True),
]
"""How `df` can answer, and what the diagnosis is left holding.

Rows two and three are the degradation worth pinning: the probe ran, exited
clean, and the mount and the free space are simply gone from the advice. Nothing
fails, nothing is reported unavailable, and the sentence is the same one a
machine with no `df` would get — which is the shape `unavailable` exists to keep
apart.
"""


@pytest.mark.parametrize(('answer', 'script', 'names_mount', 'could_not_ask'), DF_ANSWERS, ids=[row[0] for row in DF_ANSWERS])
def test_a_full_filesystem_is_named_when_df_answers_in_the_shape_it_was_asked_for(
    answer: str, script: str, names_mount: bool, could_not_ask: bool, fake_bin: Path, tmp_path: Path
) -> None:
    """Which filesystem filled up is the actionable half — `~` and `/nix` and a
    Docker volume fill for different reasons and are cleared different ways."""
    executable(fake_bin, 'df', f'#!/bin/sh\n{script}\n')

    found = diagnose._no_space(tmp_path / 'ntfy')

    assert found.cause, 'a diagnosis that says nothing is worse than none'
    assert ('/mnt/data' in found.cause) is names_mount, f'df answered with {answer}'
    assert ('12K' in found.cause) is names_mount, f'df answered with {answer}'
    assert bool(found.unavailable) is could_not_ask, f'df answered with {answer}'


def test_a_missing_df_is_reported_as_a_question_that_could_not_be_asked(fake_bin: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The distinction the module turns on. "the filesystem is full" with nothing
    beside it reads as a measurement on a machine where nothing was measured."""
    monkeypatch.setenv('PATH', str(fake_bin))

    found = diagnose._no_space(Path('/var/lib/x'))

    assert found.cause
    assert len(found.unavailable) == 1
    assert 'df' in found.unavailable[0]


def test_an_enospc_failure_is_routed_to_the_probe_that_explains_it(fake_bin: Path, tmp_path: Path) -> None:
    """`No space left` is the third marker in `WRITE_FAILURES` and the path is read
    out of the quoted subject, so the dispatch is what makes any of the above
    reachable from a real provider failure. The provider's own message stays the
    first line, because it is what the run actually reported.
    """
    executable(fake_bin, 'df', '#!/bin/sh\nprintf "Mounted on Avail\\n/mnt/data 0\\n"\n')
    target = tmp_path / 'ntfy'
    message = f"[Errno 28] No space left on device: '{target}'"

    explained = diagnose.explain('ghrelease/ntfy', message).splitlines()

    assert explained[0] == message
    assert '/mnt/data' in explained[1]
    assert 'ntfy' in explained[1]
