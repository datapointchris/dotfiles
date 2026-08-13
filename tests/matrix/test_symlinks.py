"""The repo deployed into `$HOME`, driven through the front door.

`tests/resources/test_symlinks.py` already pins the resource: what the repo
declares, what one link's verdict is, and what `perform` writes. This module asks
the questions only the CLI can answer — which **verb** reports a given
destination, which **exit code** a caller branches on, what `--force`, `--machine`
and `--json` change, and what `apply` writes versus what it walks past.

The axis worth reading first is the destination. One declared file, and every
thing that can be sitting where it belongs — from which the split between `plan`
and `check` falls out: a link this manager could repair is *drift* and belongs to
`plan`, and a target it must not touch is an *Issue* and belongs to `check`.
Neither verb reports both, which is why a row asserts each of the four numbers
rather than one exit code.
"""

from __future__ import annotations

import dataclasses as dc
import json
from collections.abc import Callable
from pathlib import Path

import pytest

from dotfiles.vocabulary import ExitCode
from matrix.harness import REFUSED
from matrix.harness import Invocation
from matrix.harness import Sandbox
from matrix.harness import resource
from matrix.harness import unwrapped

REPO_COPY = 'the repo copy\n'
SOMEBODY_ELSE = 'somebody else wrote this\n'

DECLARED = 'configs/common/.config/app/app.conf'
"""The one path this module deploys, nested so a parent directory has to be made.

Under `.config/` rather than at `~/.bashrc`, and that is not cosmetic: a foreign
target byte-identical to `/etc/skel/<name>` is adopted without `--force`, so a
test using a filename `useradd` also ships would answer differently on Debian
than on Arch. Nothing puts an `app.conf` in `/etc/skel`.
"""

MACOS = {'machine': 'mac', 'platform': 'macos'}
"""A second machine, differing from `box` on four of the six axes.

macOS rather than Arch because the two Linux bundles differ only in package
manager and display stack — and the Wayland one makes `apply` run `hyprctl
reload`, which on this developer's box reaches the compositor he is looking at.
"""


@pytest.fixture(autouse=True)
def the_epilogue_cannot_leave_this_sandbox(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the three things `deploy.epilogue` writes at this test's machine.

    `symlinks apply` ends in `deploy.epilogue`, which is not reached by `$HOME`
    the way everything else is: `GIT_CONFIG_ENTRY` and `HOME_GITCONFIG` are
    `Path.home()` evaluated at *import*, and `tests/cli/test_deploy.py` imports
    `dotfiles.deploy` at collection time — before any sandbox exists. Under
    `pytest tests/` they therefore name the real home, and this module's applies
    would create `~/.config/git/config` on a fresh CI runner and unlink a real
    `~/.gitconfig` that happened to be a link.

    There is no knob to set instead. This is the seam `harness.rebind` already
    re-derives for `core.DOTFILES_DIR` and `core.TARGET_DIR`, and the same
    two attributes are already rebound by `tests/cli/test_deploy.py` for the same
    reason — it belongs in the harness, and until it lives there it belongs here
    rather than in the real home.

    `hyprctl` is the third: `PATH` keeps `/usr/bin` behind the sandbox, so a
    Wayland machine's `apply` finds the real compositor and reloads it. That one
    *is* a real seam — a binary on `PATH` — and it answers no.
    """
    from dotfiles import deploy

    monkeypatch.setattr(deploy, 'GIT_CONFIG_ENTRY', sandbox.home / '.config' / 'git' / 'config')
    monkeypatch.setattr(deploy, 'HOME_GITCONFIG', sandbox.home / '.gitconfig')
    sandbox.shadow('hyprctl', REFUSED)


# ─────────────────────────────────────────────────────────────────────────────
# The eight things that can be where a declared link belongs
# ─────────────────────────────────────────────────────────────────────────────


def declare(sandbox: Sandbox, relative: str = DECLARED, content: str = REPO_COPY) -> Path:
    """Put a file in the repo, in whichever directory the path names."""
    source = sandbox.repo / relative
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(content)
    return source


def destination(sandbox: Sandbox, relative: str = DECLARED) -> Path:
    """Where that file lands, derived the way `sources()` derives it."""
    return sandbox.home / Path(relative).relative_to('configs/common')


def elsewhere(sandbox: Sandbox) -> Path:
    """A file somebody else manages, outside the repo entirely."""
    outside = sandbox.root / 'elsewhere'
    outside.mkdir(exist_ok=True)
    theirs = outside / 'their.conf'
    theirs.write_text(SOMEBODY_ELSE)
    return theirs


def is_the_repo_copy(sandbox: Sandbox) -> bool:
    return destination(sandbox).is_symlink() and destination(sandbox).read_text() == REPO_COPY


def is_untouched_foreign_content(sandbox: Sandbox) -> bool:
    return not destination(sandbox).is_symlink() and destination(sandbox).read_text() == SOMEBODY_ELSE


def is_untouched_foreign_link(sandbox: Sandbox) -> bool:
    return destination(sandbox).is_symlink() and destination(sandbox).read_text() == SOMEBODY_ELSE


def is_untouched_directory(sandbox: Sandbox) -> bool:
    return destination(sandbox).is_dir() and not destination(sandbox).is_symlink()


def is_gone(sandbox: Sandbox) -> bool:
    return not destination(sandbox).exists() and not destination(sandbox).is_symlink()


Arrange = Callable[[Sandbox, Callable[..., Invocation]], None]


def nothing_deployed(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    declare(sandbox)


def already_deployed(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    declare(sandbox)
    cli('symlinks', 'apply')


def pointing_elsewhere_in_the_repo(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    declare(sandbox)
    target = destination(sandbox)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(sandbox.repo / 'pyproject.toml')


def dangling_into_the_repo(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    declare(sandbox)
    target = destination(sandbox)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(sandbox.repo / 'configs' / 'common' / 'deleted.conf')


def a_plain_file(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    declare(sandbox)
    target = destination(sandbox)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(SOMEBODY_ELSE)


def a_link_out_of_the_repo(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    declare(sandbox)
    target = destination(sandbox)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(elsewhere(sandbox))


def a_directory(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    declare(sandbox)
    destination(sandbox).mkdir(parents=True)


def the_source_is_gone(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    declare(sandbox)
    cli('symlinks', 'apply')
    (sandbox.repo / DECLARED).unlink()


@dc.dataclass(frozen=True)
class Destination:
    """One state of `$HOME`, and every verb's answer to it.

    All four numbers on one row, because the split between the verbs is the thing
    being asserted: a row that recorded only `plan`'s exit code would pass just as
    well if `check` had reported the same finding twice.
    """

    arrange: Arrange
    plan: ExitCode
    pending: int
    check: ExitCode
    attention: int
    after_apply: Callable[[Sandbox], bool]
    repaired: bool
    """Whether `apply` wrote anything. A refusal is not a failure and does not
    move the exit code, so this is the only thing separating the two halves."""


DESTINATIONS: dict[str, Destination] = {
    'nothing-is-deployed': Destination(nothing_deployed, ExitCode.DRIFT, 1, ExitCode.CONVERGED, 0, is_the_repo_copy, True),
    'the-link-is-already-right': Destination(already_deployed, ExitCode.CONVERGED, 0, ExitCode.CONVERGED, 0, is_the_repo_copy, False),
    'a-link-elsewhere-in-the-repo': Destination(
        pointing_elsewhere_in_the_repo, ExitCode.DRIFT, 1, ExitCode.CONVERGED, 0, is_the_repo_copy, True
    ),
    'a-link-dangling-into-the-repo': Destination(dangling_into_the_repo, ExitCode.DRIFT, 1, ExitCode.CONVERGED, 0, is_the_repo_copy, True),
    'a-plain-file': Destination(a_plain_file, ExitCode.CONVERGED, 0, ExitCode.ISSUE, 1, is_untouched_foreign_content, False),
    'a-link-out-of-the-repo': Destination(
        a_link_out_of_the_repo, ExitCode.CONVERGED, 0, ExitCode.ISSUE, 1, is_untouched_foreign_link, False
    ),
    'a-directory': Destination(a_directory, ExitCode.CONVERGED, 0, ExitCode.ISSUE, 1, is_untouched_directory, False),
    'the-source-is-gone': Destination(the_source_is_gone, ExitCode.DRIFT, 1, ExitCode.CONVERGED, 0, is_gone, True),
}
"""Every destination, and which verb owns it.

A repairable state is `plan`'s and exits 1 there while `check` says nothing is
wrong; a foreign one is `check`'s and exits 3 there while `plan` says there is
nothing to change. `the-source-is-gone` is `plan`'s as well, which is the row that
is not obvious: an orphan is a link nothing declares, and pruning it is still work
`apply` can do.
"""


def wrote(ran: Invocation) -> list[str]:
    """What one `apply --json` actually did, off the run record it emitted."""
    return [row['address'] for row in (ran.document or {}).get('outcomes', []) if row['action'] == 'done']


@pytest.mark.parametrize('state', list(DESTINATIONS), ids=list(DESTINATIONS))
def test_plan_owns_a_repairable_destination_and_check_owns_a_foreign_one(
    state: str, sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """Which verb owns a destination, and the number a caller branches on.

    Both verbs against one arrangement, because the contract is the *split*.
    `plan` answers 0 or 1 and `check` answers 0 or 3, so a state reported by both
    would be indistinguishable from one reported by neither without asserting the
    pair.
    """
    row = DESTINATIONS[state]
    row.arrange(sandbox, cli)

    planned = cli('symlinks', 'plan', '--json')
    checked = cli('symlinks', 'check', '--json')

    assert (planned.exit_code, resource(planned, 'symlinks')['pending']) == (row.plan, row.pending)
    assert (checked.exit_code, resource(checked, 'symlinks')['attention']) == (row.check, row.attention)


@pytest.mark.parametrize('state', list(DESTINATIONS), ids=list(DESTINATIONS))
def test_apply_repairs_what_it_owns_and_walks_past_what_it_does_not(state: str, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """What `apply` writes, and that refusing to write is not a failure.

    Every row exits 0. A foreign target is a finding `apply` reports and cannot
    act on, and exiting non-zero for it would make every freshly-adopted machine
    look like a failed install.
    """
    row = DESTINATIONS[state]
    row.arrange(sandbox, cli)

    ran = cli('symlinks', 'apply', '--json')

    assert ran.exit_code == ExitCode.CONVERGED
    assert bool(wrote(ran)) is row.repaired
    assert row.after_apply(sandbox)


def test_a_refused_target_is_named_with_the_way_out_of_it(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The advice, not the bare flag. A reader meets this from a composite `apply`
    or a `check`, neither of which takes `--force`."""
    a_plain_file(sandbox, cli)

    ran = cli('symlinks', 'check')

    assert 'was not created by this manager' in ran.output
    assert 'dotfiles symlinks apply --force' in ran.output


# ─────────────────────────────────────────────────────────────────────────────
# --force
# ─────────────────────────────────────────────────────────────────────────────

ADOPTABLE = ['a-plain-file', 'a-link-out-of-the-repo']


@pytest.mark.parametrize('state', ADOPTABLE, ids=ADOPTABLE)
def test_force_adopts_the_foreign_targets_a_plain_apply_refuses(state: str, sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The deliberate answer to a refusal, for adopting a machine that already had
    dotfiles of its own. Per run rather than per path: it takes every foreign
    target in the run."""
    DESTINATIONS[state].arrange(sandbox, cli)

    ran = cli('symlinks', 'apply', '--force', '--json')

    assert ran.exit_code == ExitCode.CONVERGED
    assert wrote(ran) == [f'symlinks/{DECLARED}']
    assert is_the_repo_copy(sandbox)


def test_force_cannot_replace_a_directory_and_says_so_as_a_failure(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """A directory is adoptable under `--force` and then unlinkable, so the refusal
    that would have been a finding becomes an attempted write that the filesystem
    refused. Exit 3 rather than 0, which is the honest answer — something was tried
    and did not work."""
    a_directory(sandbox, cli)

    ran = cli('symlinks', 'apply', '--force', '--json')

    assert ran.exit_code == ExitCode.ISSUE
    assert [row['action'] for row in ran.document['outcomes'] if row['address'].endswith(DECLARED)] == ['planned', 'failed']
    assert is_untouched_directory(sandbox)


def test_force_never_reaches_a_name_project_scripts_declares(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The two compete for one path in `~/.local/bin` and the declaration wins.
    There is no state of the machine in which replacing the running console script
    with an `apps/` file is right, so the flag must not reach it."""
    (sandbox.repo / 'pyproject.toml').write_text(
        '[project]\nname = "synthetic"\nversion = "0.0.0"\n\n[project.scripts]\ndotfiles = "dotfiles.main:app"\n'
    )
    declare(sandbox, 'apps/common/dotfiles', 'the bash front door\n')
    declare(sandbox, 'apps/common/notes', 'the notes app\n')
    installed = sandbox.home / '.local' / 'bin' / 'dotfiles'
    installed.parent.mkdir(parents=True)
    installed.write_text('the installed console script\n')

    ran = cli('symlinks', 'apply', '--force', '--json')

    assert wrote(ran) == ['symlinks/apps/common/notes']
    assert installed.read_text() == 'the installed console script\n'


# ─────────────────────────────────────────────────────────────────────────────
# unlink
# ─────────────────────────────────────────────────────────────────────────────


def test_unlink_refuses_without_force_and_writes_nothing(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """A usage error rather than a finding: it is the caller who has not said what
    they meant, and the machine is untouched either way."""
    already_deployed(sandbox, cli)

    ran = cli('symlinks', 'unlink')

    assert ran.exit_code == ExitCode.USAGE
    assert 'leaving the machine unconfigured' in ran.stderr
    assert is_the_repo_copy(sandbox)


def test_unlink_with_force_removes_this_repos_links_and_only_those(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Containment by path component, not string prefix. The inverse of `apply`,
    so what it must not take is exactly what `apply` refuses to write."""
    already_deployed(sandbox, cli)
    theirs = sandbox.home / 'their.conf'
    theirs.symlink_to(elsewhere(sandbox))
    kept = sandbox.home / 'not-a-link.conf'
    kept.write_text(SOMEBODY_ELSE)

    ran = cli('symlinks', 'unlink', '--force')

    assert ran.exit_code == ExitCode.CONVERGED
    assert is_gone(sandbox)
    assert theirs.is_symlink()
    assert kept.read_text() == SOMEBODY_ELSE


def test_what_unlink_removes_apply_puts_back(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The pair, in one test, because neither half means anything alone."""
    already_deployed(sandbox, cli)
    cli('symlinks', 'unlink', '--force')

    ran = cli('symlinks', 'apply', '--json')

    assert wrote(ran) == [f'symlinks/{DECLARED}']
    assert is_the_repo_copy(sandbox)


# ─────────────────────────────────────────────────────────────────────────────
# --machine
# ─────────────────────────────────────────────────────────────────────────────


def two_machines(sandbox: Sandbox) -> None:
    """`box` is apt on Linux; `mac` is brew on Darwin. One variant each."""
    sandbox.declare(manifest=MACOS, machine='mac')
    sandbox.declare()
    declare(sandbox, 'configs/pkg/apt/.config/apt.conf', 'apt\n')
    declare(sandbox, 'configs/pkg/brew/.config/brew.conf', 'brew\n')


@pytest.mark.parametrize(
    ('argv', 'wanted', 'unwanted'),
    [
        ((), '.config/apt.conf', '.config/brew.conf'),
        (('--machine', 'mac'), '.config/brew.conf', '.config/apt.conf'),
    ],
    ids=['the-machine-in-the-environment', 'the-machine-named-on-the-line'],
)
def test_the_machine_decides_which_variant_is_deployed(
    argv: tuple[str, ...], wanted: str, unwanted: str, sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """`--machine` selects a manifest, and the manifest is the only thing that says
    where the machine sits on each axis. Nothing is detected."""
    two_machines(sandbox)

    ran = cli('symlinks', 'apply', *argv, '--json')

    assert [Path(row['address']).name for row in ran.document['outcomes'] if row['action'] == 'done'] == [Path(wanted).name]
    assert (sandbox.home / wanted).is_symlink()
    assert not (sandbox.home / unwanted).exists()


def test_show_lists_the_named_machines_links_rather_than_this_ones(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    two_machines(sandbox)

    ran = cli('symlinks', 'show', '--machine', 'mac')

    assert 'configs/pkg/brew/.config/brew.conf' in ran.stderr
    assert 'configs/pkg/apt' not in ran.stderr


def test_apply_reports_an_unknown_machine_as_a_usage_error(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """`apply_machine` catches it, names the manifest it looked for, and lists what
    it could have been. Writing nothing is the other half of the answer."""
    declare(sandbox)

    ran = cli('symlinks', 'apply', '--machine', 'nosuch')

    assert ran.exit_code == ExitCode.USAGE
    assert 'nosuch: has no manifest' in unwrapped(ran.stderr)
    assert 'Available: box' in unwrapped(ran.stderr)
    assert not destination(sandbox).exists()


READ_VERBS = [('plan',), ('check',), ('show',), ('unlink', '--force')]


@pytest.mark.parametrize('verb', READ_VERBS, ids=[argv[0] for argv in READ_VERBS])
def test_an_unknown_machine_is_a_usage_error_on_every_leaf(verb: tuple[str, ...], cli: Callable[..., Invocation]) -> None:
    """A name that matches no manifest is the caller mistyping, which is exit 2.

    `apply` answered first — with the manifest it looked for and the names it could
    have been — so the information existed and only the read verbs could not reach
    it. A traceback is the one answer a caller cannot branch on, and it is what
    `dotfiles symlinks plan --machine <typo>` printed.
    """
    assert cli('symlinks', *verb, '--machine', 'nosuch', catch_exceptions=True).exit_code == ExitCode.USAGE


# ─────────────────────────────────────────────────────────────────────────────
# --json
# ─────────────────────────────────────────────────────────────────────────────

MACHINE_READABLE = [('plan',), ('check',), ('apply',)]


@pytest.mark.parametrize('verb', MACHINE_READABLE, ids=[argv[0] for argv in MACHINE_READABLE])
def test_json_puts_a_document_on_stdout_and_every_diagnostic_on_stderr(
    verb: tuple[str, ...], sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """The machine contract the two consoles exist for. One stray row on stdout
    turns a caller's parse into a syntax error rather than the warning it was.

    Asserted as "stdout parses whole and is nothing but the document", not as "a
    diagnostic sentence is absent from stdout". The sentence was the proxy and it
    stopped meaning what it said the moment the document started carrying the
    findings: `was not created by this manager` is now a `detail` field inside the
    document, which is the finding arriving through the door built for it rather
    than a row leaking onto the wrong stream. A row that did leak still fails
    this — it makes stdout unparseable, which is the harm either way.
    """
    a_plain_file(sandbox, cli)

    ran = cli('symlinks', *verb, '--json')

    assert json.loads(ran.stdout) == ran.document


def test_the_read_verbs_emit_the_interchange_document_and_apply_emits_the_run_record(
    sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """Deliberately two shapes. The read verbs answer the versioned interchange
    document, whichever door they were entered through and however many resources
    the walk turned out to cover; a run record is a transcript of what one `apply`
    did, and it is what `report show --json` prints back for the same run."""
    nothing_deployed(sandbox, cli)
    planned = cli('symlinks', 'plan', '--json')

    assert planned.document['verb'] == 'plan'
    assert resource(planned, 'symlinks')['address'] == 'symlinks'
    assert cli('symlinks', 'apply', '--json').document['verb'] == 'apply'


WITHOUT_JSON = [('show',), ('unlink', '--force')]


@pytest.mark.parametrize('verb', WITHOUT_JSON, ids=[argv[0] for argv in WITHOUT_JSON])
def test_the_two_leaves_that_are_not_reconcile_verbs_take_no_json(verb: tuple[str, ...], cli: Callable[..., Invocation]) -> None:
    """Neither answers a verdict, so neither has a document to emit. Asserted
    rather than assumed: a caller scripting `--json` across the noun needs the
    refusal to be a usage error and not an ignored flag."""
    ran = cli('symlinks', *verb, '--json', catch_exceptions=True)

    assert ran.exit_code == ExitCode.USAGE
    assert ran.document is None


def test_only_apply_files_a_run_record(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The resource leaves are not the composite verbs. `dotfiles plan` opens a run
    and files it; `dotfiles symlinks plan` measures one resource and prints."""
    nothing_deployed(sandbox, cli)

    cli('symlinks', 'plan')
    cli('symlinks', 'check')
    assert sandbox.run_files == []

    cli('symlinks', 'apply')
    assert len(sandbox.filed_records) == 1


# ─────────────────────────────────────────────────────────────────────────────
# show
# ─────────────────────────────────────────────────────────────────────────────


def test_show_marks_every_declared_link_and_names_the_orphans_under_them(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Declared rather than discovered, so a link that was never deployed appears
    here too — which a walk of `$HOME` could not do.

    On stderr in full: this is a listing rather than a verdict, and it exits 0
    whatever it finds.
    """
    declare(sandbox, 'configs/common/.config/kept.conf')
    declare(sandbox, 'configs/common/.config/gone.conf')
    declare(sandbox)
    cli('symlinks', 'apply')
    (sandbox.repo / 'configs' / 'common' / '.config' / 'gone.conf').unlink()

    ran = cli('symlinks', 'show')

    assert ran.exit_code == ExitCode.CONVERGED
    assert ran.stdout == ''
    assert f'→ {DECLARED} →' in ran.stderr
    assert 'gone.conf (source gone)' in ran.stderr


# ─────────────────────────────────────────────────────────────────────────────
# Four faults, each pinned as it behaves and again as it should
# ─────────────────────────────────────────────────────────────────────────────


def collides(sandbox: Sandbox) -> Path:
    """One relative path declared in two variants, which `box` selects both of."""
    declare(sandbox, 'configs/common/.config/app/app.conf', 'from common\n')
    declare(sandbox, 'configs/pkg/apt/.config/app/app.conf', 'from apt\n')
    return destination(sandbox)


def test_a_collision_stops_the_apply_before_it_writes_anything(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Two directories claiming one destination is an error, and an error stops the
    run rather than converging part of it.

    It used to deploy both. `declared()` appends without deduplicating, so two links
    were planned at one target and `perform` ran both in order — the later one won,
    the next `plan` reported the loser as ordinary drift and repaired it, unseating
    the winner, and the file alternated between the two on every run for ever while
    `check` reported a healthy machine.

    Refusing before the walk rather than skipping the one target: a machine
    converged against a declaration nobody can satisfy is in a state neither the
    repo nor the run describes, and the caller finds out one resource at a time.
    """
    target = collides(sandbox)

    ran = cli('apply', '--json', catch_exceptions=True)

    assert ran.exit_code == ExitCode.ISSUE
    assert not target.exists()


def test_a_collision_names_both_directories_that_declared_it(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The message has to say which two, because the repair is deleting one of them
    and nothing else in the run points at either."""
    collides(sandbox)

    ran = cli('machines', 'check', '--json', catch_exceptions=True)

    said = ' '.join(finding['message'] for finding in ran.document)
    assert 'common' in said
    assert 'pkg/apt' in said
    assert '.config/app/app.conf' in said


def test_a_check_that_found_an_undeployed_link_does_not_say_it_is_deployed(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The detail counts what is in place, so it cannot claim a link the same run
    found missing.

    It read `all N declared symlinks are deployed` — the declared count with the
    word attached. `check` is right to report converged, because a missing link is
    `plan`'s drift and not something wrong; the detail was the false half, and it
    is the half a reader keeps.
    """
    nothing_deployed(sandbox, cli)

    detail = resource(cli('symlinks', 'check', '--json'), 'symlinks')['detail']

    assert detail == '0 of 1 declared symlinks in place'
    assert 'deployed' not in detail


def test_show_says_a_fully_deployed_machine_has_nothing_undeployed(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """`show` reports a healthy machine as having an undeployed link.

    One declared link, correctly deployed, and one orphan beside it. The trailer
    counted the verdict dict, which holds a row per drifted link *and* a row per
    orphan, so it read `1 declared, 1 not deployed as declared` — saying the one
    declared link did not land. An orphan is by definition not declared — that is why it is
    pruned rather than repaired — so it cannot be part of this count. Reading the
    line the obvious way sends someone looking for a deployment failure that is not
    there.
    """
    declare(sandbox, 'configs/common/.config/kept.conf')
    declare(sandbox, 'configs/common/.config/gone.conf')
    cli('symlinks', 'apply')
    (sandbox.repo / 'configs' / 'common' / '.config' / 'gone.conf').unlink()

    assert '1 declared, 0 not deployed as declared' in cli('symlinks', 'show').stderr


def test_an_apply_deploys_a_link_declared_since_the_last_one_in_this_process(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """A file added to the repo between two applies used to be refused, with a
    message saying the repo no longer declares it — the opposite of true.

    `observe` re-reads the repo every run, so the change was planned correctly.
    `perform` is handed a `Change` rather than the observation and looks the link up
    in `_index`, whose cache key is the Session — equal by value across the two
    runs, so the second got the first's answer, found no link at that address, and
    fell into the branch for pruning an orphan. The run exited 0 and reported
    converged, having deployed nothing.

    Not reachable from a shell, where one process runs one apply. Reachable from
    anything driving the CLI in process, which is this suite — so the fixture that
    would have caught it was also the thing that could trigger it.
    """
    already_deployed(sandbox, cli)
    declare(sandbox, 'configs/common/.config/added.conf')

    ran = cli('symlinks', 'apply', '--json')

    assert (sandbox.home / '.config' / 'added.conf').is_symlink()
    assert 'nothing in the repo declares this link any more' not in ran.stderr


# ─────────────────────────────────────────────────────────────────────────────
# The epilogue, which belongs to this verb and not to the walk
# ─────────────────────────────────────────────────────────────────────────────


def test_apply_leaves_git_an_entry_point_that_is_not_a_link_into_the_repo(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """git follows a symlink when writing, so an entry point linked into the
    checkout takes `git config --global user.email` with it. `apply` writes a real
    file there, and does it whether or not the pass deployed anything."""
    entry = sandbox.home / '.config' / 'git' / 'config'

    cli('symlinks', 'apply')

    assert entry.is_file()
    assert not entry.is_symlink()
    assert 'common.gitconfig' in entry.read_text()


def test_apply_retires_an_empty_home_gitconfig_that_would_outrank_the_entry_point(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """git prefers `~/.gitconfig` over `~/.config/git/config` for reads and writes
    both, so one left behind silently outranks the whole include chain."""
    (sandbox.home / '.gitconfig').write_text('[core]\n\tpager = less\n')

    cli('symlinks', 'apply')

    assert not (sandbox.home / '.gitconfig').exists()


def test_a_home_gitconfig_holding_an_identity_is_reported_rather_than_deleted(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """An address is never deleted. On a fleet machine the repo already ships it,
    so the advice is to delete the file by hand rather than rescue it."""
    (sandbox.home / '.gitconfig').write_text('[user]\n\temail = someone@example.invalid\n')

    ran = cli('symlinks', 'apply')

    assert (sandbox.home / '.gitconfig').is_file()
    assert 'someone@example.invalid' in ran.stderr
