"""The runtimes and the plugins, measured through the two nouns that own them.

Both resources are planned from something other than a subscription, which is what
this module is mostly about. A machine gets Go because it declared `go_tools`, and
the `runtimes` section carries only the floor — so every assertion here about
*which* runtime is wanted names the section that pulled it in rather than the
runtime. The plugin managers are the same shape from the other side: TPM's row
exists because the `tmux_plugins` clone was planned, and lazy's because the
manifest names a feature with no catalog section behind it.

**PATH is narrowed to the sandbox wherever absence is the measurement.** The
harness leaves `/usr/bin:/bin` behind its own bin so `git` and `sh` resolve, and a
developer box with `rustc` or `node` there answers "the runtime is missing"
differently from a CI runner. `only_the_sandbox_on_path` is the seam that settles
it, and it is the real one — `$PATH` is what `shutil.which` reads.

**`tmux` is shadowed wherever a TPM row is measured**, for the same reason and with
one extra: `pluginsync.blocked` reports the *first* unmet precondition, so a box
with tmux and a box without produce two different sentences for one state.

Nothing here installs and nothing reaches upstream. The one runtime install that
would — a missing toolchain under a run that is not `--offline` — is asserted as
the network attempt it is, through the guard.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from dotfiles.vocabulary import ExitCode
from matrix.harness import REFUSED
from matrix.harness import Invocation
from matrix.harness import ReachedTheNetwork
from matrix.harness import Sandbox
from matrix.harness import git_checkout
from matrix.harness import unwrapped

# ─────────────────────────────────────────────────────────────────────────────
# The declarations these tests are written against
# ─────────────────────────────────────────────────────────────────────────────

RUNTIMES: dict[str, Any] = {
    'runtimes': {
        'rust': {'install_method': 'rustup', 'version': '1.90'},
        'node': {'install_method': 'fnm'},
    },
    'go_tools': [{'name': 'task', 'package': 'github.com/go-task/task/v3/cmd/task'}],
    'cargo_packages': [{'name': 'ripgrep', 'command': 'rg'}],
    'npm_globals': {'lsp': [{'name': 'bash-language-server'}]},
}
"""One catalog carrying a tool for each runtime, and a floor for one of them.

`version` rather than `min_version`, which is the only constraint `Runtime`
honours — `catalog.Entry.problems` refuses a constraint nothing reads, and the
resource takes `min_version or version` as the floor either way.

Rust is the runtime the floor is declared for because `rustc` is answered by
`PATH` and nothing else. Go declares `installed_at=/usr/local/go/bin/go`, an
absolute path outside any sandbox, so a floor asserted against Go would be
asserted against whatever the developer's `/usr/local` holds.
"""

PLUGINS: dict[str, Any] = {
    'shell_plugins': [{'name': 'forgit', 'repo': 'https://github.com/wfxr/forgit.git'}],
    'tmux_plugins': {'tpm': {'repo': 'https://github.com/tmux-plugins/tpm', 'install_dir': '~/.config/tmux/plugins/tpm'}},
    'yazi_plugins': [{'name': 'git', 'repo': 'https://github.com/yazi-rs/plugins', 'subdirectory': 'git.yazi'}],
}

BARE: dict[str, Any] = {'machine': 'box', 'platform': 'linux'}

RUNTIME_ROWS = ('uv-toolchain/uv', 'go-toolchain/go', 'rust-toolchain/rust', 'node-toolchain/node')
PLUGIN_ROWS = ('shell-plugin/forgit', 'tpm/tpm', 'tmux-sync/tpm', 'yazi-plugin/git', 'nvim-sync/lazy')
"""Every address either resource can print, so a row's absence is asserted as
directly as its presence. A test naming only what it expects passes just as well
against a run that printed twice as much."""

RECORDS_ARGV = '#!/bin/sh\nprintf "%s\\n" "$*" >> "$RECORDED_ARGV"\nexit 1\n'
"""A binary that writes down how it was called and then fails.

The only way to prove a *network* command was reached without letting it reach
one. Exiting 1 keeps the caller on its failure path, which is where the run
records what it tried.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def only_the_sandbox_on_path(sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch) -> None:
    """Drop `/usr/bin:/bin`, so a runtime is absent unless this test installed it.

    The harness keeps them for `git` and `sh`, which is right for its baseline and
    wrong for every assertion that a runtime is missing: `rustc` and `node` are
    ordinary system packages, so the same test answers one way at a desk and
    another on a runner. `/bin/sh` stays reachable regardless — the stubs name it
    absolutely in their shebang — and a `git` that is no longer findable exits 127,
    which `effects.run` already treats as an answer.
    """
    monkeypatch.setenv('PATH', str(sandbox.bin))


def declares(sandbox: Sandbox, **gates: Any) -> None:
    """The plugin catalog, with this machine subscribing to exactly `gates`."""
    sandbox.declare(packages=PLUGINS, manifest={**BARE, **gates})


def reached_through(caught: pytest.ExceptionInfo[BaseException], module: str) -> bool:
    """Whether the guarded request came from this module rather than some other.

    "A run reached the network" is a weak claim on its own: an `apply` refreshes
    currency as well as installing, so a raise could as easily have come from the
    release lookup as from the runtime being asked for. The frame is what says
    which, and it is what makes these two assertions about `needed_by` rather than
    about the guard.
    """
    return any(Path(entry.path).name == module for entry in caught.traceback)


def reported(ran: Invocation, addresses: tuple[str, ...]) -> set[str]:
    """Which of the resource's addresses this run printed a row for.

    Both kinds count. A finding and an examined item are the two things a row can
    be, they print in the same columns, and which one an address earns is the
    verdict's business rather than the selection's — so this answers *what was
    selected*, which is the question every gate test here is asking.

    Never handed a `--json` run: that path emits the document and prints no rows
    at all, so this would answer the empty set for a walk that measured everything.
    """
    rows = unwrapped(ran.stderr)
    return {address for address in addresses if address in rows}


def tpm_installed(sandbox: Sandbox) -> Path:
    """TPM where the declaration says, as a checkout rather than a bare directory.

    The `.git` matters: without it the plugins resource reports TPM as present and
    unmanaged — right, and a different finding from the one a TPM test is about.
    """
    plugins = sandbox.home / '.config' / 'tmux' / 'plugins'
    (plugins / 'tpm' / 'bin').mkdir(parents=True)
    (plugins / 'tpm' / '.git').mkdir()
    installer = plugins / 'tpm' / 'bin' / 'install_plugins'
    installer.write_text('#!/bin/sh\nexit 0\n')
    installer.chmod(0o755)
    return plugins


def tmux_conf(sandbox: Sandbox, plugin: str = 'tmux-plugins/tmux-yank') -> Path:
    config = sandbox.home / '.config' / 'tmux' / 'tmux.conf'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(f"set -g @plugin '{plugin}'\n")
    return config


def lazy_lockfile(sandbox: Sandbox, plugin: str = 'gitsigns.nvim') -> None:
    lock = sandbox.home / '.config' / 'nvim' / 'lazy-lock.json'
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(f'{{"{plugin}": {{"commit": "a"}}}}')


# ─────────────────────────────────────────────────────────────────────────────
# A runtime is wanted because a section resolved, never because it was declared
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ('subscribes', 'wanted'),
    [
        ({}, ('uv-toolchain/uv',)),
        ({'go_tools': ['task']}, ('uv-toolchain/uv', 'go-toolchain/go')),
        ({'cargo_packages': ['ripgrep']}, ('uv-toolchain/uv', 'rust-toolchain/rust')),
        ({'npm_globals': ['bash-language-server']}, ('uv-toolchain/uv', 'node-toolchain/node')),
        (
            {'go_tools': ['task'], 'cargo_packages': ['ripgrep'], 'npm_globals': ['bash-language-server']},
            RUNTIME_ROWS,
        ),
    ],
    ids=['declares-nothing', 'go_tools', 'cargo_packages', 'npm_globals', 'every-tool-section'],
)
def test_a_runtime_is_planned_by_the_tool_section_that_needs_it(
    sandbox: Sandbox,
    monkeypatch: pytest.MonkeyPatch,
    cli: Callable[..., Invocation],
    subscribes: dict[str, Any],
    wanted: tuple[str, ...],
) -> None:
    """The whole derivation, from the front door. No manifest boolean names a
    runtime — those were removed because one could be set with no tools at all —
    so the tool list is the only thing that decides."""
    only_the_sandbox_on_path(sandbox, monkeypatch)
    sandbox.declare(packages=RUNTIMES, manifest={**BARE, **subscribes})

    ran = cli('toolchains', 'plan')

    assert reported(ran, RUNTIME_ROWS) == set(wanted)


def test_declaring_a_runtime_in_the_catalog_puts_it_on_no_machine(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation]
) -> None:
    """`runtimes` is read for floors and subscribed to by nobody, which is what
    `registry.UNPROVIDED` says about it. A machine declaring no tools gets uv and
    nothing else, however many rows the catalog carries."""
    only_the_sandbox_on_path(sandbox, monkeypatch)
    sandbox.declare(packages=RUNTIMES, manifest=BARE)

    listed = cli('toolchains', 'plan')
    counted = cli('toolchains', 'plan', '--json')

    assert reported(listed, RUNTIME_ROWS) == {'uv-toolchain/uv'}
    assert counted.exit_code == ExitCode.CONVERGED
    assert counted.document['pending'] == 0


def test_a_machine_that_needs_a_runtime_it_lacks_is_drift_rather_than_an_issue(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation]
) -> None:
    """The pair the two verbs exist to separate, and the counts are not the split.

    Both documents report one pending item, because `pending` is what the walk
    measured rather than what this verb keeps. The verdict is where the two part:
    a missing runtime is what `apply` is for, so `check` — which runs unattended on
    a timer — reports the machine as having nothing wrong with it and exits 0.
    """
    only_the_sandbox_on_path(sandbox, monkeypatch)
    sandbox.declare(packages=RUNTIMES, manifest={**BARE, 'cargo_packages': ['ripgrep']})

    planned = cli('toolchains', 'plan', '--json')
    checked = cli('toolchains', 'check', '--json')

    assert (planned.exit_code, planned.document['verdict']) == (ExitCode.DRIFT, 'drift')
    assert (checked.exit_code, checked.document['verdict']) == (ExitCode.CONVERGED, 'converged')
    assert planned.document['pending'] == checked.document['pending'] == 1
    assert planned.document['attention'] == checked.document['attention'] == 0


# ─────────────────────────────────────────────────────────────────────────────
# What the runtime reported, against the floor the catalog declares
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ('reports', 'code', 'pending', 'unmeasured'),
    [
        (None, ExitCode.DRIFT, 1, 0),
        ('rustc 1.89.0 (90b35a623 2026-01-14)', ExitCode.DRIFT, 1, 0),
        ('rustc 1.90.0 (90b35a623 2026-01-14)', ExitCode.CONVERGED, 0, 0),
        ('rustc 1.97.1 (8bab26f4f 2026-07-14)', ExitCode.CONVERGED, 0, 0),
        ('rustc: unknown build', ExitCode.CONVERGED, 0, 1),
    ],
    ids=['absent', 'below-the-floor', 'at-the-floor', 'above-the-floor', 'no-version-in-it'],
)
def test_a_runtime_is_measured_against_the_floor_its_catalog_row_declares(
    sandbox: Sandbox,
    monkeypatch: pytest.MonkeyPatch,
    cli: Callable[..., Invocation],
    reports: str | None,
    code: ExitCode,
    pending: int,
    unmeasured: int,
) -> None:
    """A version that cannot be read is unmeasured rather than stale, and neither
    verb's answer: reporting it as too old would be a guess dressed as a
    measurement, and it must not move an exit code."""
    only_the_sandbox_on_path(sandbox, monkeypatch)
    sandbox.declare(packages=RUNTIMES, manifest={**BARE, 'cargo_packages': ['ripgrep']})
    if reports is not None:
        sandbox.installed('rustc', reports)

    ran = cli('toolchains', 'plan', '--json')

    assert ran.exit_code == code
    assert ran.document['pending'] == pending
    assert ran.document['unmeasured'] == unmeasured


def test_a_runtime_on_path_that_will_not_answer_counts_as_absent(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation]
) -> None:
    """A half-extracted tarball leaves the binary in place with `which` satisfied by
    it, which is not what an installed runtime looks like."""
    only_the_sandbox_on_path(sandbox, monkeypatch)
    sandbox.declare(packages=RUNTIMES, manifest={**BARE, 'cargo_packages': ['ripgrep']})
    sandbox.shadow('rustc', REFUSED)

    ran = cli('toolchains', 'plan')

    assert ran.exit_code == ExitCode.DRIFT
    assert 'would not report a version' in unwrapped(ran.stderr)


def test_a_go_on_path_cannot_satisfy_the_toolchain_a_fixed_path_answers_for(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation]
) -> None:
    """Go declares `installed_at`, so the question is where it was unpacked and not
    what `which` finds. A container picked up Arch's `go` package transitively,
    `which go` answered `/usr/sbin/go`, and the toolchain reported itself installed
    while `/usr/local/go` did not exist — so every Go tool built against a runtime
    this repo had not put there.

    Asserted as the version that must *not* appear, which is the one claim that
    holds on both kinds of machine: `/usr/local/go` is outside every sandbox, so
    whether Go is present here is the developer's business and whether this stub
    answered for it is not.
    """
    only_the_sandbox_on_path(sandbox, monkeypatch)
    sandbox.declare(packages=RUNTIMES, manifest={**BARE, 'go_tools': ['task']})
    sandbox.installed('go', 'go version go9.9.9 linux/amd64')

    ran = cli('toolchains', 'plan')

    assert 'go-toolchain/go' in unwrapped(ran.stderr)
    assert 'go9.9.9' not in unwrapped(ran.stderr)


def test_the_runtimes_that_install_under_home_ask_for_no_password(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation]
) -> None:
    """Go is the one runtime whose repair escalates, because it is unpacked over
    `/usr/local/go`; rust, node and uv install under `$HOME`. `privileged` is a
    static fact on the change, which is what lets a read-only verb state the count
    without acquiring anything — and a plan of two missing runtimes states nought.
    """
    only_the_sandbox_on_path(sandbox, monkeypatch)
    sandbox.declare(packages=RUNTIMES, manifest={**BARE, 'cargo_packages': ['ripgrep'], 'npm_globals': ['bash-language-server']})

    ran = cli('toolchains', 'plan', '--json')

    assert ran.document['pending'] == 2
    assert ran.document['privileged'] == 0


# ─────────────────────────────────────────────────────────────────────────────
# Applying a runtime: what is offline, what is refused, what reaches upstream
# ─────────────────────────────────────────────────────────────────────────────


def test_a_converged_machine_applies_its_toolchains_without_installing_anything(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation]
) -> None:
    """uv is ungated and planned everywhere, so this is the smallest real apply
    there is — and it has to be a no-op, or every other row here would be measuring
    the baseline."""
    only_the_sandbox_on_path(sandbox, monkeypatch)

    assert cli('toolchains', 'apply').exit_code == ExitCode.CONVERGED


def test_applying_a_missing_runtime_is_stopped_at_the_network_it_would_reach(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation]
) -> None:
    """rustup is served from an unversioned URL, so installing rust starts by
    fetching whatever is at it. The guard is the assertion: an online apply of an
    absent runtime is a download, and there is nothing local it could have used.

    Rust rather than Go, for the reason `RUNTIMES` gives — Go is answered by an
    absolute path outside any sandbox, so whether it is missing here is a fact
    about the developer's `/usr/local`.
    """
    only_the_sandbox_on_path(sandbox, monkeypatch)
    sandbox.declare(packages=RUNTIMES, manifest={**BARE, 'cargo_packages': ['ripgrep']})

    with pytest.raises(ReachedTheNetwork) as reached:
        cli('toolchains', 'apply')

    assert reached_through(reached, 'toolchain.py')


def test_an_offline_apply_with_no_staged_bundle_says_so_and_stops(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation]
) -> None:
    """The bundle directory is deliberately absent until a test stages one, because
    `_stage_bundle` reads an existing directory as already-staged."""
    only_the_sandbox_on_path(sandbox, monkeypatch)
    sandbox.declare(packages=RUNTIMES, manifest={**BARE, 'cargo_packages': ['ripgrep']})

    ran = cli('toolchains', 'apply', '--offline')

    assert ran.exit_code == ExitCode.ISSUE
    assert 'offline needs a staged bundle' in unwrapped(ran.stderr)


@pytest.mark.parametrize(
    ('subscribes', 'helper', 'code', 'says'),
    [
        ({'cargo_packages': ['ripgrep']}, None, ExitCode.CONVERGED, 'https://sh.rustup.rs'),
        ({'npm_globals': ['bash-language-server']}, 'fnm', ExitCode.CONVERGED, 'nodejs.org'),
        ({'npm_globals': ['bash-language-server']}, None, ExitCode.ISSUE, 'fnm is not on PATH'),
    ],
    ids=['rustup-is-not-staged', 'node-is-not-staged', 'node-without-the-fnm-that-fetches-it'],
)
def test_an_offline_runtime_is_refused_where_nothing_stages_it_and_fails_where_its_manager_is_gone(
    sandbox: Sandbox,
    monkeypatch: pytest.MonkeyPatch,
    cli: Callable[..., Invocation],
    subscribes: dict[str, Any],
    helper: str | None,
    code: ExitCode,
    says: str,
) -> None:
    """A refusal wrote nothing and must not move the exit code; a failure must.

    The bundle stages neither rustup nor Node, and that costs an offline machine
    nothing it could have had — the cargo and npm providers take their packages
    from the bundle rather than from a compiler. `fnm` missing is the other kind:
    nothing about the world said no, this machine is simply not in a state where
    the runtime can be installed at all.
    """
    only_the_sandbox_on_path(sandbox, monkeypatch)
    sandbox.stage_bundle({'lazygit': '0.45.0'})
    sandbox.declare(packages=RUNTIMES, manifest={**BARE, **subscribes})
    if helper:
        sandbox.installed(helper)

    ran = cli('toolchains', 'apply', '--offline')

    assert ran.exit_code == code
    assert says in unwrapped(ran.output)


# ─────────────────────────────────────────────────────────────────────────────
# Browsing the declaration: list and show
# ─────────────────────────────────────────────────────────────────────────────


def test_the_toolchain_list_is_the_runtimes_section_and_nothing_else(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    sandbox.declare(packages=RUNTIMES, manifest=BARE)

    ran = cli('toolchains', 'list', '--json')

    assert ran.exit_code == ExitCode.CONVERGED
    assert sorted(row['name'] for row in ran.document) == ['node', 'rust']
    assert {row['section'] for row in ran.document} == {'runtimes'}


def test_a_toolchain_nothing_declares_is_refused_rather_than_answered_emptily(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """`USAGE`, because naming a toolchain that exists is what fixes it.

    It answered a bare 1 until `declaration.main` stopped signalling through
    `sys.exit` — argparse's convention, where 1 means failed, arriving in a tool
    where 1 means the machine has drift.
    """
    sandbox.declare(packages=RUNTIMES, manifest=BARE)

    ran = cli('toolchains', 'show', 'haskell', catch_exceptions=True)

    assert ran.exit_code == ExitCode.USAGE
    assert 'no package named haskell' in unwrapped(ran.stderr)


def test_showing_a_toolchain_prints_the_runtimes_row_it_names(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    sandbox.declare(packages=RUNTIMES, manifest=BARE)

    ran = cli('toolchains', 'show', 'rust')

    assert ran.exit_code == ExitCode.CONVERGED
    assert 'Section:     runtimes' in ran.stdout


def test_toolchains_show_is_scoped_to_the_runtimes_it_is_the_noun_for(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """`dotfiles toolchains show ripgrep` should say that no runtime is called that,
    the way `toolchains list` already refuses to list anything but runtimes. A noun
    whose `show` ignores its own scope makes the address vocabulary a suggestion.
    """
    sandbox.declare(packages=RUNTIMES, manifest=BARE)

    assert cli('toolchains', 'show', 'ripgrep', catch_exceptions=True).exit_code != ExitCode.CONVERGED


def test_the_plugin_list_covers_every_plugin_section_the_resource_owns(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """A declared plugin that `plugins plan` reports and `plugins apply` clones has
    to be nameable by `plugins list`, or the list is a different roster from the
    resource under the same noun."""
    sandbox.declare(packages=PLUGINS, manifest={**BARE, 'shell_plugins': True, 'tmux_plugins': True, 'yazi_plugins': True})

    ran = cli('plugins', 'list', '--json')

    assert sorted(row['name'] for row in ran.document) == ['forgit', 'git', 'tpm']


# ─────────────────────────────────────────────────────────────────────────────
# Which plugins a machine is planned, and by which gate
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ('gates', 'wanted'),
    [
        ({}, ()),
        ({'shell_plugins': True}, ('shell-plugin/forgit',)),
        ({'tmux_plugins': True}, ('tpm/tpm', 'tmux-sync/tpm')),
        ({'yazi_plugins': True}, ('yazi-plugin/git',)),
        ({'nvim_plugins': True}, ('nvim-sync/lazy',)),
        ({'shell_plugins': True, 'tmux_plugins': True, 'yazi_plugins': True, 'nvim_plugins': True}, PLUGIN_ROWS),
    ],
    ids=['declines-everything', 'shell_plugins', 'tmux_plugins', 'yazi_plugins', 'nvim_plugins', 'every-gate'],
)
def test_a_plugin_row_exists_because_its_own_gate_says_so(
    sandbox: Sandbox,
    cli: Callable[..., Invocation],
    gates: dict[str, Any],
    wanted: tuple[str, ...],
) -> None:
    """Four gates of three kinds. The clones are catalog subscriptions, TPM's sync
    is gated by the *section* its manager is declared in rather than by a boolean of
    its own, and lazy's is a manifest feature because there is no section to
    subscribe to."""
    sandbox.shadow('tmux')
    declares(sandbox, **gates)

    ran = cli('plugins', 'plan')

    assert reported(ran, PLUGIN_ROWS) == set(wanted)


def test_the_tmux_sync_disappears_with_the_clone_that_provides_its_manager(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """TPM installs the plugins, so a machine without TPM has nothing to sync — and
    the sync reads the gate on the clone rather than the same boolean a second
    time."""
    sandbox.shadow('tmux')
    declares(sandbox, tmux_plugins=False, shell_plugins=True)

    ran = cli('plugins', 'plan')

    assert reported(ran, PLUGIN_ROWS) == {'shell-plugin/forgit'}


def test_a_machine_declining_every_plugin_converges_under_all_three_verbs(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    declares(sandbox)

    assert [cli('plugins', verb).exit_code for verb in ('plan', 'check', 'apply')] == [ExitCode.CONVERGED] * 3


def test_an_uncloned_plugin_is_drift_and_a_plugin_installed_by_something_else_is_an_issue(
    sandbox: Sandbox, cli: Callable[..., Invocation]
) -> None:
    """The two halves of the split, in one declaration. A missing checkout is what
    `apply` is for; a directory that is present and is not a checkout can only be
    repaired by deleting whatever is there, so it is a person's."""
    declares(sandbox, shell_plugins=True, yazi_plugins=True)
    unmanaged = sandbox.home / '.config' / 'zsh' / 'plugins' / 'forgit'
    unmanaged.mkdir(parents=True)
    (unmanaged / 'forgit.plugin.zsh').write_text('# put here by something else\n')

    planned = cli('plugins', 'plan', '--json')
    checked = cli('plugins', 'check', '--json')
    advised = cli('plugins', 'check')

    assert planned.exit_code == ExitCode.DRIFT
    assert (planned.document['pending'], planned.document['attention']) == (1, 1)
    assert checked.exit_code == ExitCode.ISSUE
    assert 'present, but not a git checkout, so nothing here can update it' in unwrapped(advised.stderr)
    assert 'and re-run to clone it, or drop the entry if another tool owns this plugin' in unwrapped(advised.stderr)


# ─────────────────────────────────────────────────────────────────────────────
# The two managers that own lists this repo cannot read
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ('cloned', 'deployed', 'installed', 'code', 'says'),
    [
        (False, False, False, ExitCode.DRIFT, 'TPM is not at'),
        (True, False, False, ExitCode.DRIFT, 'no tmux config at'),
        (True, True, False, ExitCode.DRIFT, 'plugins tmux.conf declares are not installed: tmux-yank'),
        (True, True, True, ExitCode.CONVERGED, 'nothing pending'),
    ],
    ids=['tpm-not-cloned', 'config-not-deployed', 'plugin-not-installed', 'nothing-pending'],
)
def test_the_tmux_sync_reports_the_first_precondition_an_earlier_stage_owes_it(
    sandbox: Sandbox,
    cli: Callable[..., Invocation],
    cloned: bool,
    deployed: bool,
    installed: bool,
    code: ExitCode,
    says: str,
) -> None:
    """Every precondition here is supplied by an earlier stage of the same run, so
    "impossible right now" is a change rather than a fault. Reading an undeployed
    `tmux.conf` as "declares no plugins" is the bug the middle row exists to stop:
    a fresh machine would plan nothing, install nothing, and report itself
    converged with its plugins arriving one apply later.
    """
    sandbox.shadow('tmux')
    declares(sandbox, tmux_plugins=True)
    plugins = tpm_installed(sandbox) if cloned else sandbox.home / '.config' / 'tmux' / 'plugins'
    if deployed:
        tmux_conf(sandbox)
    if installed:
        (plugins / 'tmux-yank' / '.git').mkdir(parents=True)

    ran = cli('plugins', 'plan')

    assert ran.exit_code == code
    assert 'tmux-sync/tpm' in unwrapped(ran.stderr)
    assert says in unwrapped(ran.stderr)


@pytest.mark.parametrize(
    ('recorded', 'on_disk', 'code', 'says'),
    [
        (False, False, ExitCode.DRIFT, 'lazy has not synced on this machine'),
        (True, False, ExitCode.DRIFT, 'plugins lazy recorded installing are not on disk: gitsigns.nvim'),
        (True, True, ExitCode.CONVERGED, 'nothing pending'),
    ],
    ids=['never-synced', 'record-without-the-checkout', 'nothing-pending'],
)
def test_the_nvim_sync_answers_from_lazys_own_record_rather_than_from_its_lua(
    sandbox: Sandbox,
    cli: Callable[..., Invocation],
    recorded: bool,
    on_disk: bool,
    code: ExitCode,
    says: str,
) -> None:
    """The spec is lua and its only reader is nvim, whose startup *installs* what it
    finds missing — so asking would be a write, which an observation may not be. A
    plugin added to the spec and not yet cloned is therefore invisible here, and
    deliberately: lazy repairs that case itself the next time the editor opens.
    """
    declares(sandbox, nvim_plugins=True)
    if recorded:
        lazy_lockfile(sandbox)
    if on_disk:
        (sandbox.home / '.local' / 'share' / 'nvim' / 'lazy' / 'gitsigns.nvim').mkdir(parents=True)

    ran = cli('plugins', 'plan')

    assert ran.exit_code == code
    assert 'nvim-sync/lazy' in unwrapped(ran.stderr)
    assert says in unwrapped(ran.stderr)


def test_a_sync_whose_program_is_absent_is_refused_rather_than_failed(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation]
) -> None:
    """Neovim arrives from an earlier stage of the same run, so a machine without it
    is not a failed apply — it is an apply that could not get to this row yet. A
    refusal wrote nothing, so the run still converges."""
    only_the_sandbox_on_path(sandbox, monkeypatch)
    declares(sandbox, nvim_plugins=True)

    ran = cli('plugins', 'apply')

    assert ran.exit_code == ExitCode.CONVERGED
    assert 'neovim is not installed' in unwrapped(ran.output)


def test_the_tmux_sync_hands_tpm_its_list_on_a_server_that_is_not_the_users(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """The repair is the invocation, which is the whole of what this row stands
    for: there is nothing per plugin to plan, because TPM's list is `@plugin` lines
    in a config file rather than a `packages.yml` section."""
    sandbox.shadow('tmux')
    declares(sandbox, tmux_plugins=True)
    tpm_installed(sandbox)
    tmux_conf(sandbox)

    ran = cli('plugins', 'apply')

    assert ran.exit_code == ExitCode.CONVERGED
    assert 'TPM installed the plugins tmux.conf declares' in unwrapped(ran.output)


# ─────────────────────────────────────────────────────────────────────────────
# Cloning, which is what `plugins apply` mostly is
# ─────────────────────────────────────────────────────────────────────────────


def test_applying_clones_each_declared_plugin_to_the_path_its_program_reads(sandbox: Sandbox, cli: Callable[..., Invocation]) -> None:
    """Three destinations from one mechanism: `.zshrc` sources one, yazi appends
    the `.yazi` suffix to another, and TPM is told its own path because it has to
    agree with it."""
    upstream = git_checkout(sandbox.root / 'forgit', {'forgit.plugin.zsh': '# forgit\n'})
    monorepo = git_checkout(sandbox.root / 'yazi-plugins', {'git.yazi/main.lua': '-- git\n', 'chmod.yazi/main.lua': '-- chmod\n'})
    sandbox.declare(
        packages={
            'shell_plugins': [{'name': 'forgit', 'repo': str(upstream)}],
            'yazi_plugins': [{'name': 'git', 'repo': str(monorepo), 'subdirectory': 'git.yazi'}],
        },
        manifest={**BARE, 'shell_plugins': True, 'yazi_plugins': True},
    )

    ran = cli('plugins', 'apply')

    assert ran.exit_code == ExitCode.CONVERGED
    assert (sandbox.home / '.config' / 'zsh' / 'plugins' / 'forgit' / 'forgit.plugin.zsh').read_text() == '# forgit\n'
    assert (sandbox.home / '.config' / 'yazi' / 'plugins' / 'git.yazi' / 'main.lua').read_text() == '-- git\n'
    assert not (sandbox.home / '.config' / 'yazi' / 'plugins' / 'git.yazi' / 'chmod.yazi').exists()
    assert cli('plugins', 'plan').exit_code == ExitCode.CONVERGED


def test_an_offline_plugins_apply_refuses_the_clone_nothing_staged(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation]
) -> None:
    """`--offline` means this run does not reach the network, and a plugin nothing
    staged is a refusal — the same answer rustup and Node get one resource over. A
    refusal writes nothing and leaves the run converged; what happens instead is an
    attempted clone and a failed apply."""
    only_the_sandbox_on_path(sandbox, monkeypatch)
    attempts = sandbox.root / 'git-argv'
    monkeypatch.setenv('RECORDED_ARGV', str(attempts))
    sandbox.stage_bundle({'lazygit': '0.45.0'})
    sandbox.shadow('git', RECORDS_ARGV)
    declares(sandbox, shell_plugins=True)

    cli('plugins', 'apply', '--offline')

    assert 'clone' not in attempts.read_text()


# ─────────────────────────────────────────────────────────────────────────────
# A section's runtime, reached through the section rather than named
# ─────────────────────────────────────────────────────────────────────────────


def test_narrowing_a_write_to_a_section_reaches_the_runtime_that_section_needs(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation]
) -> None:
    """`registry.serving` is what puts the runtime in the selection: narrowing to
    `cargo_packages` and dropping rust asks for something that cannot install, and
    did — `cargo binstall bat` exiting 127 with `cargo: No such file or directory`.

    The network guard is the proof the runtime was reached. Nothing here is
    installable offline, so an apply that got as far as rustup is an apply that
    honoured `needed_by`.
    """
    only_the_sandbox_on_path(sandbox, monkeypatch)
    sandbox.declare(packages=RUNTIMES, manifest={**BARE, 'cargo_packages': ['ripgrep']})
    sandbox.installed('rg', 'ripgrep 14.1.1')

    with pytest.raises(ReachedTheNetwork) as reached:
        cli('packages', 'apply', '--source', 'cargo_packages')

    assert reached_through(reached, 'toolchain.py')


def test_narrowing_a_read_to_a_section_reports_the_runtime_it_selected(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation]
) -> None:
    """A preview that cannot express the write's scope is not a rehearsal of it.
    The runtime is in the selection deliberately, so it belongs in the answer —
    either as a second row or folded into the one that is printed."""
    only_the_sandbox_on_path(sandbox, monkeypatch)
    sandbox.declare(packages=RUNTIMES, manifest={**BARE, 'cargo_packages': ['ripgrep']})
    sandbox.installed('rg', 'ripgrep 14.1.1')

    ran = cli('packages', 'plan', '--source', 'cargo_packages', '--json')

    assert ran.exit_code == ExitCode.DRIFT


# ─────────────────────────────────────────────────────────────────────────────
# The verbs themselves
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize('resource', ['toolchains', 'plugins'], ids=['toolchains', 'plugins'])
@pytest.mark.parametrize('verb', ['plan', 'check'], ids=['plan', 'check'])
def test_a_read_verb_puts_its_document_alone_on_stdout(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation], resource: str, verb: str
) -> None:
    """The machine contract both nouns share. One stray diagnostic on stdout turns a
    `--json` parse into a syntax error rather than the warning it was."""
    only_the_sandbox_on_path(sandbox, monkeypatch)
    sandbox.declare(packages=RUNTIMES, manifest={**BARE, 'cargo_packages': ['ripgrep'], 'shell_plugins': True})

    ran = cli(resource, verb, '--json')

    assert ran.document is not None
    assert ran.document['address'] == resource
    assert ran.stdout.strip().startswith('{')


@pytest.mark.parametrize('resource', ['toolchains', 'plugins'], ids=['toolchains', 'plugins'])
def test_a_bare_resource_is_a_usage_error_rather_than_a_verdict(cli: Callable[..., Invocation], resource: str) -> None:
    """Neither noun does anything on its own, and a caller has to be able to tell
    "you did not say which verb" from "it ran and found nothing"."""
    assert cli(resource, catch_exceptions=True).exit_code == ExitCode.USAGE


@pytest.mark.parametrize('resource', ['toolchains', 'plugins'], ids=['toolchains', 'plugins'])
def test_a_resource_scoped_check_leaves_the_machines_own_status_alone(
    sandbox: Sandbox, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Invocation], resource: str
) -> None:
    """One part of the machine answered for is not the machine answered for.

    `dotfiles check` files a run record and writes the status document the shell
    nudge and the scheduled unit read; a check narrowed to one noun writes neither.
    It has to be that way round — a converged `toolchains check` overwriting the
    status would report the whole machine healthy on the strength of one resource.
    """
    only_the_sandbox_on_path(sandbox, monkeypatch)

    cli(resource, 'check')

    assert sandbox.run_files == []
    assert not sandbox.status_file.exists()

    cli('check')

    assert len(sandbox.filed_records) == 1
    assert sandbox.status_file.is_file()
