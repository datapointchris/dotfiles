# Task Reference

`task --list-all` from inside the repo is the list. It is generated from the
Taskfile and cannot go stale, which a copy here would.

## Philosophy

**Tasks orchestrate, they do not wrap.** A task exists to coordinate a
multi-step workflow. An operation that is already one command keeps its native
command — wrapping `brew upgrade` in `task brew-upgrade` adds a name to
remember and nothing else.

**Logic lives in code, not YAML.** Installation logic sits in `src/dotfiles/`,
where it can be tested and read without counting indentation, and the `dotfiles`
CLI is its entry point. This is why the Taskfile stays short as the install
grows.

**Platform detection is not reimplemented per task.** A machine's coordinates
come from its manifest through `src/dotfiles/coordinates.py`, so no task and no
script asks `uname` what it is running on.

## A machine operation is a `dotfiles` command, never a task

Everything that reads or changes a machine is a `dotfiles` command, which works
from any directory. A task renaming one would be a second name for the same
operation, and two names for one operation drift apart. See
[Management Interface](../../architecture/management-interface.md).

What `task` keeps is the work about the repo rather than the machine: setup, the
test suite and the docs site. Those have no place in a CLI whose job is managing
an installed machine. Publishing the docs site is CI's, on every push to `main`.

Bootstrapping a machine from nothing starts neither, because `dotfiles` is not
installed yet. See [Rebuilding a Machine](../rebuilding-a-machine.md).
