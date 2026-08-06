---
icon: material/apps
---

# Apps

Personal CLI tools. Every one has `--help`, which is the reference for its flags
and verbs; the pages here cover the parts `--help` cannot — why a tool exists,
what it deliberately does not do, and how it fits the rest.

Only tools with something to explain have a page. `eza ~/.local/bin` is the list
of what is actually installed, and `toolbox list` is the searchable version.

## Finding and choosing

- **[Menu](menu.md)** — federated search across tools, functions, aliases and keybindings
- **[Menu Next](menu-next.md)** — what to do now, drawn from weighted pursuits
- **[Toolbox](toolbox.md)** — the installed-tool registry and its `--brief` nudge
- **[Workflows](workflows.md)** — the reference/recipe card format, and when a card is worth writing

## Backup and integrity

- **[Backup](backup.md)** — `backmeup` archives versus `backup-incremental` snapshots
- **[Safekeep](safekeep.md)** — moved to its own repo; the page records why, and the manifest consequence
- **[Refcheck](refcheck.md)** — broken-reference validation, and why it runs here

## Appearance

- **[Theme](theme.md)** — which dotfiles-managed configs `theme apply` rewrites
- **[Font](font.md)** — the same, for fonts
- **[Work Monitor](work-monitor.md)** — Arch-only; the Dell hotplug behaviour behind it

## Documented elsewhere

`dotfiles` is in [Management Interface](../architecture/management-interface.md),
`packages` in [Package Management](../architecture/package-management.md), and
`tmux-sessions` in [tmux Sessions](../architecture/tmux-sessions.md), because
each is a component of the system that page describes rather than a standalone
tool.
