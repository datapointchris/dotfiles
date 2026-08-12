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

import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from dotfiles.effects import Output
from dotfiles.effects import run
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

LAZY_LOCK = Path('.config/nvim/lazy-lock.json')
LAZY_STATE = Path('.local/share/nvim/lazy')
"""lazy's own two paths: what it recorded installing, and where it put it."""

SESSION = 'dotfiles-tpm-install'


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
    sourced = tuple(_expand(target, home) for path in base for target in _matches(SOURCE_LINE, path))
    return tuple(path for path in base + sourced if path.is_file())


def declared(home: Path) -> tuple[str, ...]:
    """Every plugin the tmux config names, by the directory name TPM gives it.

    `user/plugin`, `user/plugin.git` and `git://host/user/plugin.git` all land in a
    directory called `plugin`: basename, minus the `.git`, which is
    `plugin_name_helper`. Order is the config's and duplicates collapse, so a
    plugin named twice is one row rather than two.
    """
    names: list[str] = []
    for path in configs(home):
        for plugin in _matches(PLUGIN_LINE, path):
            name = plugin.rsplit('/', 1)[-1].removesuffix('.git')
            if name and name not in names:
                names.append(name)
    return tuple(names)


def uninstalled(names: tuple[str, ...], plugins_dir: Path) -> tuple[str, ...]:
    """Which of these plugins TPM has not cloned, by the test TPM itself applies.

    A checkout rather than a directory: `plugin_already_installed` is `[ -d ] && cd
    && git remote`, and an interrupted clone leaves the first true and the second
    false. Statted rather than shelled out to, because this runs on every `check`,
    including the unattended one on the timer, and `git remote` per plugin is a
    subprocess per plugin to answer a question a `.git` entry already answers.
    """
    return tuple(name for name in names if not (plugins_dir / name / '.git').exists())


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
    """
    config = user_config(home)
    if reason := blocked(home, plugins_dir):
        return Result(False, f'{reason}. {_diagnostics(config, plugins_dir)}')

    installer = plugins_dir / 'tpm' / 'bin' / 'install_plugins'
    with tempfile.TemporaryDirectory(prefix='dotfiles-tpm-') as scratch:
        socket = Path(scratch) / f'tmux-{os.getuid()}' / 'default'
        socket.parent.mkdir(mode=0o700)
        environment = {'TMUX_TMPDIR': scratch, 'TERM': os.environ.get('TERM') or 'xterm'}
        detached = ('TMUX', 'TMUX_PANE')

        started = run(['tmux', '-S', str(socket), 'new-session', '-d', '-s', SESSION], env=environment, unset=detached, output=Output.QUIET)
        if not started.ok:
            reason = started.transcript.strip()
            return Result(False, f'could not start a tmux server to install into: {reason}. {_diagnostics(config, plugins_dir)}')

        try:
            run(
                ['tmux', '-S', str(socket), 'set-environment', '-g', 'TMUX_PLUGIN_MANAGER_PATH', f'{plugins_dir}/'],
                env=environment,
                unset=detached,
                output=Output.QUIET,
            )
            installed = run([str(installer)], env=environment, unset=detached, show=_tpm_line)
        finally:
            run(['tmux', '-S', str(socket), 'kill-server'], env=environment, unset=detached, output=Output.QUIET)

    if not installed.ok:
        said = installed.transcript.strip() or f'TPM exited {installed.returncode}'
        return Result(False, f'TPM plugin installation failed (exit {installed.returncode}): {said}. {_diagnostics(config, plugins_dir)}')
    return Result(True, f'TPM installed the plugins {config.name} declares')


def _diagnostics(config: Path, plugins_dir: Path) -> str:
    """The three facts every TPM failure turns out to need.

    Read on another machine days later, "TPM failed" is undiagnosable without
    which tmux, which config it was reading, and where it was installing — and
    every failure above is some version of "tmux did not tell TPM what it needed".
    """
    version = run(['tmux', '-V'], output=Output.QUIET)
    reported = version.transcript.strip() if version.ok else 'not installed'
    return f'tmux: {reported}; config: {config} ({"present" if config.is_file() else "MISSING"}); plugins: {plugins_dir}'


def _tpm_line(line: str) -> str | None:
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
        )

    synced = run(['nvim', '--headless', '-c', 'Lazy! sync', '-c', 'qa'], show=_lazy_line)
    if not synced.ok:
        return Result(False, synced.transcript.strip() or f'lazy exited {synced.returncode}')
    return Result(True, 'lazy synced the plugins the Neovim config declares')


def _lazy_line(line: str) -> str | None:
    """The one line lazy prints as each plugin's task starts, and nothing else.

    Its headless output is every plugin's raw git and build spew, which is far too
    much to watch — and sending all of it to a file left a fresh install cloning
    fifty repos with nothing on screen for minutes. The escape codes go first
    because lazy colours its own prefix, and the filter cannot see the ` | `
    separating prefix from message until they are gone.
    """
    plain = re.sub(r'\033\[[0-9;]*m', '', line)
    return f'  {plain.split(" | Running task")[0]}\n' if ' | Running task' in plain else None


# ─────────────────────────────────────────────────────────────────────────────


def listed(names: tuple[str, ...], limit: int = 4) -> str:
    """Enough names to recognise the problem by, and a count for the rest.

    A fresh machine is missing every plugin lazy knows about, and a row naming
    fifty of them is a row nobody reads to the end.
    """
    shown = ', '.join(names[:limit])
    return shown if len(names) <= limit else f'{shown} and {len(names) - limit} more'


def _matches(pattern: re.Pattern[str], path: Path) -> tuple[str, ...]:
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


def _expand(target: str, home: Path) -> Path:
    """A sourced path as tmux resolves it, which is `~` and `$HOME` and nothing else.

    `_manual_expansion` in TPM does exactly these two, and does them by hand for
    the same reason this does: the string comes out of a config file rather than
    out of a shell, so nothing has expanded it already.
    """
    for prefix in ('~', '$HOME'):
        if target.startswith(prefix):
            return home / target[len(prefix) :].lstrip('/')
    return Path(target)
