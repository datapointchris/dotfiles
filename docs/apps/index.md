---
icon: material/apps
---

# Apps

Personal CLI tools, each carrying its own `--help`. That help is the reference
for flags and verbs. A page here exists only where there is something `--help`
cannot say — why the tool exists, what it deliberately does not do, and how it
couples to the rest of this repo.

The sidebar lists those pages. For the tools themselves, `eza ~/.local/bin`
is what this machine actually has installed, and `doit kit list` is the
searchable roster across the fleet.

## Three tools are documented as system components instead

`dotfiles` is in [Management Interface](../architecture/management-interface.md),
`packages` in [Package Management](../architecture/package-management.md), and
`tmux-sessions` in [tmux Sessions](../architecture/tmux-sessions.md). Each is a
part of the system its page describes rather than a tool standing on its own.
Explaining the system is what explains the tool, so splitting one off into an
apps page would leave both halves incomplete.
