# Task Reference

`task --list-all` from inside the repo is the list. It is generated from the
Taskfile and cannot go stale, which a copy here would.

## Philosophy

**Tasks orchestrate, they do not wrap.** A task exists to coordinate a
multi-step workflow. An operation that is already one command keeps its native
command — wrapping `brew upgrade` in `task brew-upgrade` adds a name to
remember and nothing else.

**Logic lives in shell, not YAML.** Installation logic sits in `install/`, where
it can be tested and read without counting indentation. The Taskfile calls those
scripts. This is why the Taskfile stays short as the install grows.

**Platform detection is not reimplemented per task.** A machine's coordinates
come from its manifest through `src/dotfiles/coordinates.py`, so no task and no
script asks `uname` what it is running on.

## Two front doors, one implementation

`task <verb>` works from inside the repo; `dotfiles <verb>` works from anywhere.
Both reach `src/dotfiles/`, so neither is the "real" one and they cannot drift.
Use whichever is closer to hand — `dotfiles` when you are in another project,
`task` when you are already here. See
[Management Interface](../../architecture/management-interface.md).

What `task` keeps for itself is the work that is about the repo rather than the
machine: the test suite and the docs site. Those have no place in a CLI whose job
is managing an installed machine.

## Windows setup (from WSL)

`windows:bundle` downloads the Windows `.exe` for each shell tool from GitHub
releases into a single archive that can be carried to a network-restricted
machine, where `windows:offline` installs them without touching the network.
Use that pair when winget is blocked; otherwise `windows:setup` handles
everything online.

`windows:sync` copies the shell files across, and is the one of these a WSL box
no longer has to remember: `dotfiles apply` performs the same sync through the
`windows-shell` row in `install/system.yml`, and `dotfiles check` reports a
Windows tree that has drifted. The task remains for syncing without a full apply.

The Git Bash side gets copies rather than symlinks because Windows cannot follow
a symlink across the WSL boundary — see
[Architecture](../../architecture/index.md#shell-source-files).

## Installation is not a task

Full installation runs through `install.sh` and the `dotfiles apply` it prints,
not through Task, because it needs sudo and a `--machine` argument:

```sh
./install.sh --machine macos-personal-workstation
dotfiles apply --machine macos-personal-workstation
```

See [Rebuilding a Machine](../rebuilding-a-machine.md).
