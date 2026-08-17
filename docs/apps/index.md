---
icon: material/apps
---

# Apps

Personal CLI tools. Every one has `--help`, which is the reference for its flags
and verbs; the pages here cover the parts `--help` cannot — why a tool exists,
what it deliberately does not do, and how it fits the rest.

Only tools with something to explain have a page. `eza ~/.local/bin` is the list
of what is actually installed, and `doit kit list` is the searchable version.

## Finding and choosing

- **[Doit](doit.md)** — moved to its own repo; the page records why, and what stayed behind here

## Backup and integrity

- **[Backup](backup.md)** — `packup` archives versus `safekeep` snapshots
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
