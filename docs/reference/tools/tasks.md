# Task Reference

`task --list-all` from inside the repo is the list. It is generated from the
Taskfile and cannot go stale, which a copy here would.

## Philosophy

**Tasks orchestrate, they do not wrap.** A task exists to coordinate a
multi-step workflow. An operation that is already one command keeps its native
command — wrapping `brew upgrade` in `task brew-upgrade` adds a name to
remember and nothing else.

**Logic lives in code, not YAML.** Installation logic sits in `src/dotfiles/`,
where it can be tested and read without counting indentation. The Taskfile calls
into it. This is why the Taskfile stays short as the install grows.

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

Bootstrapping a machine from nothing is the one thing neither front door starts.
See [Rebuilding a Machine](../rebuilding-a-machine.md).
