"""The two plugin managers this repo invokes but whose lists it does not declare.

TPM and lazy.nvim each own a list living where nothing here reads it as a
declaration — tmux's is `@plugin` lines in `tmux.conf`, Neovim's is lua — so
neither has a `packages.yml` section and neither can be planned per plugin. What
converts is the *invocation*: one row each, whose repair is handing control to
the manager that owns the list.

**The two are asked different questions, and the asymmetry is the whole module.**
TPM's list is readable, in the one format it exists in, so the tmux row is
measured: which of the declared plugins are on disk. lazy's is lua, and asking
lazy instead costs an nvim startup that *installs* — `install.missing` defaults
to true and `lazy/core/loader.lua:41` acts on it inside `setup()`, with no
headless exemption — so an observation that asked would be a write, which
`observe` may not be. The nvim row therefore reports what lazy has recorded doing
here and says so, rather than guessing at a list it cannot read.

Neither manager is asked whether its plugins are *behind*. TPM has no such verb,
and lazy's costs the same startup as everything else here.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import signal
import tempfile
from itertools import chain
from pathlib import Path

from dotfiles.effects import Output
from dotfiles.effects import run
from dotfiles.providers import Kind
from dotfiles.providers import Result

PLUGIN_LINE = re.compile(r"""^\s*set(?:-option)?\s+-g\s+@plugin\s+['"]?([^'"\s]+)""")
SOURCE_LINE = re.compile(r"""^\s*source(?:-file)?\s+(?:-q\s+)?['"]?([^'"\s]+)""")
"""Read rather than parsed, because tmux.conf has no parser to prefer.

tmux itself is no help: `@plugin` is set once per plugin and a running server
keeps only the last, which is why TPM greps the file instead of asking. These two
patterns are `tpm_plugins_list_helper` and `_sourced_files` in
`scripts/helpers/plugin_functions.sh`, in the same shape and against the same
lines, so the two readers cannot disagree about what the config declares.
"""

COMMIT = re.compile(r'[0-9a-f]{40}')
"""A full commit, the only ref after `#` that pins rather than names a branch."""

LAZY_LOCK = Path('.config/nvim/lazy-lock.json')
LAZY_STATE = Path('.local/share/nvim/lazy')
"""lazy's own two paths: what it recorded installing, and where it put it."""

SESSION = 'dotfiles-tpm-install'

REAP_TIMEOUT = 10.0
"""How long `kill-server` gets before the throwaway is taken by signal instead.

Asking is not installing, so the deadline `effects.run` refuses to a stream is
the right shape here: a server that has not acknowledged in ten seconds is not
going to.
"""


# ─────────────────────────────────────────────────────────────────────────────
# tmux, through TPM
# ─────────────────────────────────────────────────────────────────────────────


def user_config(home: Path) -> Path:
    """The tmux config TPM will read, by TPM's own priority rather than ours."""
    xdg = home / '.config' / 'tmux' / 'tmux.conf'
    return xdg if xdg.is_file() else home / '.tmux.conf'


def configs(home: Path) -> tuple[Path, ...]:
    """Every file TPM takes plugin lines from, in its order.

    `/etc/tmux.conf` and the user's, then the files those two `source` — which is
    `_tmux_conf_contents "full"`. One level deep because TPM is one level deep: it
    derives the sourced list from the base contents and does not recurse into what
    those files source in turn.
    """
    base = (Path('/etc/tmux.conf'), user_config(home))
    targets = chain.from_iterable(matches(SOURCE_LINE, path) for path in base)
    sourced = tuple(expand(target, home) for target in targets)
    return tuple(path for path in base + sourced if path.is_file())


def name_of(plugin: str) -> str:
    """The directory TPM clones a plugin line into.

    `user/plugin`, `user/plugin.git`, `git://host/user/plugin.git` and
    `user/plugin#branch` all land in a directory called `plugin`. `install_plugins`
    splits the `#branch` off first, then `plugin_name_helper` takes the basename
    minus the `.git`.
    """
    return plugin.partition('#')[0].rsplit('/', 1)[-1].removesuffix('.git')


def declared(home: Path) -> tuple[str, ...]:
    """Every plugin the tmux config names, by the directory name TPM gives it.

    Order is the config's and duplicates collapse, so a plugin named twice is one
    row rather than two.
    """
    names: list[str] = []
    for path in configs(home):
        for plugin in matches(PLUGIN_LINE, path):
            name = name_of(plugin)
            if name and name not in names:
                names.append(name)
    return tuple(names)


def repository(source: str) -> str:
    """`owner/repo`, lowercased, from a plugin line or from the remote TPM wrote.

    TPM clones `owner/repo` as `https://git::@github.com/owner/repo`, so a checkout's
    remote never matches the line that declared it as text. Every spelling ends in
    the same two path segments once `.git` is gone and an SSH `host:owner` colon
    reads as a slash.
    """
    path = source.strip().removesuffix('/').removesuffix('.git').replace(':', '/')
    return '/'.join(path.split('/')[-2:]).lower()


def origin(checkout: Path) -> tuple[str, str | None]:
    """The remote a checkout was cloned from, and the branch it has out.

    Read out of `.git` rather than asked of git, for the reason `uninstalled` gives.
    The branch is None on a detached HEAD, which is how a checkout is pinned by
    hand, and an unreadable checkout has no remote to compare.
    """
    try:
        config = (checkout / '.git' / 'config').read_text()
        head = (checkout / '.git' / 'HEAD').read_text().strip()
    except OSError:
        return '', None
    url, section = '', ''
    for line in (raw.strip() for raw in config.splitlines()):
        if line.startswith('['):
            section = line
        elif section == '[remote "origin"]' and line.partition('=')[0].strip() == 'url':
            url = line.partition('=')[2].strip()
    branch = head.removeprefix('ref: refs/heads/') if head.startswith('ref: refs/heads/') else None
    return url, branch


def replaced(home: Path, plugins_dir: Path) -> tuple[str, ...]:
    """Checkouts cloned from another repository, or another branch, than the line
    that declares them now.

    TPM decides a plugin is installed by its directory alone, so a line moved to a
    fork of the same name finds the old checkout and installs nothing: a
    `user/tmux-resurrect#branch` line in place of `tmux-plugins/tmux-resurrect`
    leaves upstream running. `sync_tmux` sets each of these aside before TPM runs, so
    TPM clones the declared one. TPM itself is dotfiles' clone, never TPM's.
    """
    found: list[str] = []
    for path in configs(home):
        for plugin in matches(PLUGIN_LINE, path):
            name = name_of(plugin)
            checkout = plugins_dir / name
            if name in ('', 'tpm') or name in found or not (checkout / '.git').exists():
                continue
            url, branch = origin(checkout)
            if not url:
                continue
            source, _, wanted = plugin.partition('#')
            other_branch = wanted and not COMMIT.fullmatch(wanted) and branch is not None and branch != wanted
            if repository(url) != repository(source) or other_branch:
                found.append(name)
    return tuple(found)


def pinned(home: Path) -> dict[str, tuple[str, str]]:
    """Plugins the config pins to a commit, by TPM's directory name: the source and
    the commit.

    TPM's `#` takes a branch or a tag, which `git clone -b` accepts, and a commit it
    cannot. So a full commit after `#` is a pin `hold_pins` keeps, and TPM, finding
    the checkout already there, never tries to clone it.
    """
    found: dict[str, tuple[str, str]] = {}
    for path in configs(home):
        for plugin in matches(PLUGIN_LINE, path):
            source, _, ref = plugin.partition('#')
            name = name_of(plugin)
            if COMMIT.fullmatch(ref) and name not in found:
                found[name] = (source, ref)
    return found


def held_commit(checkout: Path) -> str:
    """The commit a detached checkout has out, read out of `.git` for the reason
    `uninstalled` gives. A branch checkout reads as '', since a pin is held detached.
    """
    try:
        head = (checkout / '.git' / 'HEAD').read_text().strip()
    except OSError:
        return ''
    return head if COMMIT.fullmatch(head) else ''


def off_pin(home: Path, plugins_dir: Path) -> tuple[str, ...]:
    """Pinned plugins whose checkout has another commit out than the config pins."""
    return tuple(
        name
        for name, (_, commit) in pinned(home).items()
        if (plugins_dir / name / '.git').exists() and held_commit(plugins_dir / name) != commit
    )


def clone_url(source: str) -> str:
    """Where TPM would clone a plugin line from: the line itself where it is a URL,
    and GitHub's anonymous form of `owner/repo` otherwise, which `clone_plugin`
    falls back to so a clone never stops to ask for a password."""
    return source if '://' in source or source.startswith('git@') else f'https://git::@github.com/{source}'


def hold_pins(home: Path, plugins_dir: Path) -> list[str]:
    """Put every pinned plugin at its commit, cloning it first where it is missing.

    A fetch by commit rather than by branch, because TPM's clone holds one branch
    and the pin may sit on another. Submodules follow, as TPM's `--recursive` clone
    has them. Returns a sentence per plugin it could not put there. A clone that
    failed is removed, so TPM's own attempt, and the next run, start clean.
    """
    quiet = {'GIT_TERMINAL_PROMPT': '0'}
    failed: list[str] = []
    for name, (source, commit) in pinned(home).items():
        checkout = plugins_dir / name
        if held_commit(checkout) == commit:
            continue
        fresh = not (checkout / '.git').exists()
        if fresh:
            got = run(['git', 'clone', '--quiet', '--no-checkout', clone_url(source), str(checkout)], env=quiet, output=Output.QUIET)
        else:
            got = run(['git', '-C', str(checkout), 'fetch', '--quiet', 'origin', commit], env=quiet, output=Output.QUIET)
        if got.ok:
            got = run(
                ['git', '-C', str(checkout), '-c', 'advice.detachedHead=false', 'checkout', '--quiet', '--detach', commit],
                env=quiet,
                output=Output.QUIET,
            )
        if got.ok and (checkout / '.gitmodules').is_file():
            got = run(
                ['git', '-C', str(checkout), 'submodule', 'update', '--init', '--recursive', '--quiet'], env=quiet, output=Output.QUIET
            )
        if not got.ok:
            failed.append(f'{name} could not be put at {commit[:12]}: {got.transcript.strip() or f"git exited {got.returncode}"}')
            if fresh:
                shutil.rmtree(checkout, ignore_errors=True)
    return failed


def set_aside(names: tuple[str, ...], plugins_dir: Path) -> Path | None:
    """Move each checkout `replaced` names out of TPM's sight, so TPM clones the
    declared one in its place and `settle` can put the old one back.

    Beside the plugins directory rather than in it, where `clean_plugins` would
    remove it as undeclared.
    """
    if not names:
        return None
    aside = Path(tempfile.mkdtemp(prefix='.dotfiles-replaced-', dir=plugins_dir.parent))
    try:
        for name in names:
            (plugins_dir / name).rename(aside / name)
    except OSError:
        settle(aside, plugins_dir)
        raise
    return aside


def settle(aside: Path | None, plugins_dir: Path) -> tuple[str, ...]:
    """Drop each set-aside checkout whose replacement arrived, and put back the
    ones whose replacement did not. Returns the names put back.

    A network outage or a deleted branch would otherwise leave tmux with no plugin
    at all where it had a working one.
    """
    if aside is None:
        return ()
    restored: list[str] = []
    for old in sorted(aside.iterdir()):
        new = plugins_dir / old.name
        if (new / '.git').exists():
            shutil.rmtree(old)
            continue
        if new.exists():
            shutil.rmtree(new)
        old.rename(new)
        restored.append(old.name)
    aside.rmdir()
    return tuple(restored)


def uninstalled(names: tuple[str, ...], plugins_dir: Path) -> tuple[str, ...]:
    """Which of these plugins TPM has not cloned, by the test TPM itself applies.

    A checkout rather than a directory: `plugin_already_installed` is `[ -d ] && cd
    && git remote`, and an interrupted clone leaves the first true and the second
    false. Statted rather than shelled out to, because this runs on every `check`,
    including the unattended one on the timer, and `git remote` per plugin is a
    subprocess per plugin to answer a question a `.git` entry already answers.
    """
    return tuple(name for name in names if not (plugins_dir / name / '.git').exists())


def undeclared(names: tuple[str, ...], plugins_dir: Path) -> tuple[str, ...]:
    """Checkouts TPM cloned that the config no longer names, which `clean_plugins` removes.

    TPM loads only what the config declares, so one of these never runs. Nothing
    else removes it, so a plugin dropped from tmux.conf would stay on every machine
    that ever cloned it. `tpm` is left out by name: dotfiles clones it, not TPM.
    """
    if not plugins_dir.is_dir():
        return ()
    found = (entry.name for entry in plugins_dir.iterdir() if (entry / '.git').exists())
    return tuple(sorted(name for name in found if name != 'tpm' and name not in names))


def blocked(home: Path, plugins_dir: Path) -> str:
    """Why TPM cannot run right now, or '' where it can.

    Three preconditions, and **every one of them is supplied by an earlier stage of
    the same run**: tmux is a system package, TPM is the clone one stage before
    this, and the config arrives with the symlink pass. So this is read twice and
    means something different each time. At plan time it makes the row a change
    `apply` *can* make — "impossible right now" and "impossible" are different
    claims, and a fresh machine measured before its symlink pass has not yet been
    handed the plugin list. At execute time it is the live re-check, and a
    precondition the earlier stage failed to deliver is a `REFUSED` outcome rather
    than a bad write.

    Reading the config's *absence* this way is the whole reason it exists. Treating
    an undeployed `tmux.conf` as "declares no plugins" would make a fresh install
    plan nothing, install nothing, and report a converged machine whose plugins
    arrive one `apply` later.
    """
    if not shutil.which('tmux'):
        return (
            'tmux is not installed, so there is nothing for TPM to install into; '
            'run `dotfiles system apply` (or the full `dotfiles apply`) to install it first'
        )
    installer = plugins_dir / 'tpm' / 'bin' / 'install_plugins'
    if not installer.is_file():
        return f'TPM is not at {installer}; it clones one stage before this — run `dotfiles plugins apply` again and it resolves itself'

    # TPM reads the plugin list out of this file directly rather than out of tmux,
    # so without it TPM installs nothing and exits 0 — a success that deploys no
    # plugins, on a machine whose symlink pass has not run.
    config = user_config(home)
    if config.is_file():
        return ''
    return (
        f'no tmux config at {config}, so TPM has no plugin list to read; '
        'run `dotfiles symlinks apply` (or the full `dotfiles apply`) to deploy it first'
    )


def reap(socket: Path, environment: dict[str, str], detached: tuple[str, ...]) -> None:
    """Take the throwaway by signal where `kill-server` did not take it at all.

    `kill-server` is processed on the same command queue a blocking `run-shell`
    occupies, so a server whose config load has wedged never sees the request —
    and the client still exits 0, which is why the leak reads as clean cleanup.

    What the survivor costs is paid by a different tool. `tmux-continuum` arms
    its autosave only while it believes it is the only server, counting
    *processes* named `tmux`, so one leaked throwaway silently stops the user's
    real sessions being snapshotted from the next config reload onward. Measured
    2026-08-19: a survivor from 2026-08-13 cost four days of them.

    The socket is in a directory `mkdtemp` made for this call alone, so it names
    these processes and no others.
    """
    found = run(['pgrep', '-f', str(socket)], env=environment, unset=detached, output=Output.QUIET, timeout=REAP_TIMEOUT)
    for line in found.transcript.split():
        with contextlib.suppress(ValueError, OSError, PermissionError):
            os.kill(int(line), signal.SIGKILL)


def sync_tmux(home: Path, plugins_dir: Path) -> Result:
    """Hand TPM its list, on a tmux server that is not the user's.

    Every line of the setup below is a failure that happened. TPM takes its install
    path from `TMUX_PLUGIN_MANAGER_PATH` on a running server and expects the tpm
    bootstrap line in tmux.conf to have set it; relying on that chain from an
    installer is what broke, because a server already running from before the
    config was linked leaves the variable unset and TPM aborts with "not configured
    in tmux.conf" — naming the one thing that is usually fine. It is set directly
    here, which is the override tpm documents.

    The server is a throwaway on its own socket, because TPM shells out to a bare
    `tmux` and a session appearing in the user's live server is one tmux-resurrect
    is free to snapshot. `-S` is passed on every call as well as `TMUX_TMPDIR`
    being set: cleanup runs `kill-server`, and one unset variable is the difference
    between that sentence ending at the throwaway and ending at the user's
    sessions. `$TMUX` has to be *unset* rather than overridden — it names the live
    server, it outranks `TMUX_TMPDIR`, and with it set a fresh `TMUX_TMPDIR` still
    lists the live server's sessions.

    A checkout from another source than the config names is set aside rather than
    deleted, and put back if its replacement does not arrive, so a clone that fails
    leaves the plugin that worked.
    """
    config = user_config(home)
    if reason := blocked(home, plugins_dir):
        return Result(False, f'{reason}. {diagnostics(config, plugins_dir)}', kind=Kind.PREREQUISITE_MISSING)

    swapped = replaced(home, plugins_dir)
    try:
        aside = set_aside(swapped, plugins_dir)
    except OSError as error:
        return Result(
            False,
            f'could not set {listed(swapped)} aside to clone again from the source {config.name} names: {error}',
            kind=Kind.COMMAND_FAILED,
        )
    try:
        result = install_declared(home, plugins_dir, config, swapped)
    finally:
        restored = settle(aside, plugins_dir)
    if restored:
        back = f'{listed(restored)} could not be cloned from the source {config.name} names, so the checkout it replaced is back'
        return Result(False, f'{back}. {result.detail}', kind=Kind.COMMAND_FAILED)
    return result


def install_declared(home: Path, plugins_dir: Path, config: Path, swapped: tuple[str, ...]) -> Result:
    """Hold the pinned plugins at their commits, then run TPM's install and clean."""
    moved = off_pin(home, plugins_dir)
    unheld = hold_pins(home, plugins_dir)
    if unheld:
        return Result(False, f'{"; ".join(unheld)}. {diagnostics(config, plugins_dir)}', kind=Kind.COMMAND_FAILED)

    installer = plugins_dir / 'tpm' / 'bin' / 'install_plugins'
    cleaner = plugins_dir / 'tpm' / 'bin' / 'clean_plugins'
    cleaned = None
    with tempfile.TemporaryDirectory(prefix='dotfiles-tpm-') as scratch:
        socket = Path(scratch) / f'tmux-{os.getuid()}' / 'default'
        socket.parent.mkdir(mode=0o700)
        environment = {'TMUX_TMPDIR': scratch, 'TERM': os.environ.get('TERM') or 'xterm'}
        detached = ('TMUX', 'TMUX_PANE')

        started = run(['tmux', '-S', str(socket), 'new-session', '-d', '-s', SESSION], env=environment, unset=detached, output=Output.QUIET)
        if not started.ok:
            reason = started.transcript.strip()
            return Result(
                False,
                f'could not start a tmux server to install into: {reason}. {diagnostics(config, plugins_dir)}',
                kind=Kind.COMMAND_FAILED,
            )

        try:
            run(
                ['tmux', '-S', str(socket), 'set-environment', '-g', 'TMUX_PLUGIN_MANAGER_PATH', f'{plugins_dir}/'],
                env=environment,
                unset=detached,
                output=Output.QUIET,
            )
            installed = run([str(installer)], env=environment, unset=detached, show=tpm_line)
            # On the same throwaway, because clean_plugins asks a bare `tmux` for
            # the plugin path exactly as the installer does.
            if installed.ok and undeclared(declared(home), plugins_dir):
                cleaned = run([str(cleaner)], env=environment, unset=detached, show=tpm_line)
        finally:
            run(
                ['tmux', '-S', str(socket), 'kill-server'],
                env=environment,
                unset=detached,
                output=Output.QUIET,
                timeout=REAP_TIMEOUT,
            )
            reap(socket, environment, detached)

    if not installed.ok:
        said = installed.transcript.strip() or f'TPM exited {installed.returncode}'
        return Result(
            False,
            f'TPM plugin installation failed (exit {installed.returncode}): {said}. {diagnostics(config, plugins_dir)}',
            kind=Kind.COMMAND_FAILED,
        )
    if cleaned is not None and not cleaned.ok:
        said = cleaned.transcript.strip() or f'TPM exited {cleaned.returncode}'
        failed = f'TPM could not remove the plugins {config.name} no longer declares (exit {cleaned.returncode})'
        return Result(
            False,
            f'{failed}: {said}. {diagnostics(config, plugins_dir)}',
            kind=Kind.COMMAND_FAILED,
        )
    removed = ' and removed the ones it no longer does' if cleaned is not None else ''
    recloned = f', cloning {listed(swapped)} again from the source it now names' if swapped else ''
    held = f', with {listed(moved)} moved to the commit it pins' if moved else ''
    return Result(True, f'TPM installed the plugins {config.name} declares{recloned}{held}{removed}', kind=Kind.APPLIED)


def diagnostics(config: Path, plugins_dir: Path) -> str:
    """The three facts every TPM failure turns out to need.

    Read on another machine days later, "TPM failed" is undiagnosable without
    which tmux, which config it was reading, and where it was installing — and
    every failure above is some version of "tmux did not tell TPM what it needed".
    """
    version = run(['tmux', '-V'], output=Output.QUIET)
    reported = version.transcript.strip() if version.ok else 'not installed'
    return f'tmux: {reported}; config: {config} ({"present" if config.is_file() else "MISSING"}); plugins: {plugins_dir}'


def tpm_line(line: str) -> str | None:
    """What TPM says, minus its own bootstrap.

    TPM reports on every plugin it considered, including itself — and tpm.sh has
    already logged its own bootstrap by the time this runs, so echoing that line
    reports the same event twice.
    """
    return None if '"tpm"' in line else line


# ─────────────────────────────────────────────────────────────────────────────
# Neovim, through lazy.nvim
# ─────────────────────────────────────────────────────────────────────────────


def recorded(home: Path) -> tuple[str, ...] | None:
    """What lazy last wrote to its lockfile, or None if it has never written one.

    None is not an empty list. A machine where lazy has never run has no lockfile,
    which is the state a fresh install is in and the whole reason the sync happens
    during `apply` rather than being left to the first `nvim`.
    """
    try:
        locked = json.loads((home / LAZY_LOCK).read_text())
    except (OSError, ValueError):
        return None
    return tuple(sorted(locked)) if isinstance(locked, dict) else None


def unsynced(home: Path) -> tuple[str, ...]:
    """Plugins the lockfile names that are not on disk.

    Measured against lazy's record rather than against its spec, because the spec
    is lua. So a plugin *added* to the spec and not yet installed is invisible
    here, and deliberately: lazy installs what it is missing on startup, which
    makes that case one nvim owns and repairs without being asked.
    """
    if (locked := recorded(home)) is None:
        return ()
    return tuple(name for name in locked if not (home / LAZY_STATE / name).is_dir())


def sync_nvim() -> Result:
    """`Lazy! sync`, which is install, clean and update in one act.

    Bang-suffixed and `qa`-terminated because this is headless: without the bang
    lazy waits, and without the quit nvim never exits.
    """
    if not shutil.which('nvim'):
        return Result(
            False,
            'neovim is not installed, so lazy has nothing to sync into; '
            'run `dotfiles packages apply` (or the full `dotfiles apply`) to install it first',
            kind=Kind.PREREQUISITE_MISSING,
        )

    synced = run(['nvim', '--headless', '-c', 'Lazy! sync', '-c', 'qa'], show=lazy_line)
    if not synced.ok:
        return Result(False, synced.transcript.strip() or f'lazy exited {synced.returncode}', kind=Kind.COMMAND_FAILED)
    return Result(True, 'lazy synced the plugins the Neovim config declares', kind=Kind.APPLIED)


def lazy_line(line: str) -> str | None:
    """The one line lazy prints as each plugin's task starts, and nothing else.

    Its headless output is every plugin's raw git and build spew, which is far too
    much to watch — and sending all of it to a file left a fresh install cloning
    fifty repos with nothing on screen for minutes. The escape codes go first
    because lazy colors its own prefix, and the filter cannot see the ` | `
    separating prefix from message until they are gone.
    """
    plain = re.sub(r'\033\[[0-9;]*m', '', line)
    return f'  {plain.split(" | Running task")[0]}\n' if ' | Running task' in plain else None


# ─────────────────────────────────────────────────────────────────────────────


def listed(names: tuple[str, ...], limit: int = 4) -> str:
    """Enough names to recognize the problem by, and a count for the rest.

    A fresh machine is missing every plugin lazy knows about, and a row naming
    fifty of them is a row nobody reads to the end.
    """
    shown = ', '.join(names[:limit])
    return shown if len(names) <= limit else f'{shown} and {len(names) - limit} more'


def matches(pattern: re.Pattern[str], path: Path) -> tuple[str, ...]:
    """Every capture of `pattern` in a file that may not be there.

    Missing is the ordinary case rather than an error: `/etc/tmux.conf` exists on
    almost no machine, and the user's config is absent on one whose symlink pass
    has not run.
    """
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return ()
    return tuple(found.group(1) for line in lines if (found := pattern.match(line)))


def expand(target: str, home: Path) -> Path:
    """A sourced path as tmux resolves it, which is `~` and `$HOME` and nothing else.

    `_manual_expansion` in TPM does exactly these two, and does them by hand for
    the same reason this does: the string comes out of a config file rather than
    out of a shell, so nothing has expanded it already.
    """
    for prefix in ('~', '$HOME'):
        if target.startswith(prefix):
            return home / target[len(prefix) :].lstrip('/')
    return Path(target)
