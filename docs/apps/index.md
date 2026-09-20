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

## Pages

- [Theme and font](theme.md) — two standalone tools; why every deployed config points at `current`
  rather than at a theme, so switching one is not a commit
- [Notes](notes.md) — a four-verb wrapper over `zk`; where the notebook lives, and why this repo
  configures it without carrying it
- [doit](doit.md) — the menu suite that left this repo; where it lives now, and how a machine gets it
- [Refcheck](refcheck.md) — the reference validator written against this repo; how it installs here,
  and the deliberately broken fixtures that keep it honest
- [Backup](backup.md) — choosing between `packup`, which makes one archive that stands alone, and
  `safekeep`, which snapshots what a config declares
- [Safekeep](safekeep.md) — a pointer to the repo that owns it, and why the one app holding a data
  format outside the machine had to leave
- [Work Monitor](work-monitor.md) — Arch only; driving the spare HDMI output to a second desk
  without Hyprland adopting it as a permanent display
- [zsh-startup](zsh-startup.md) — timing this machine's interactive shell, and why there is no
  threshold to fail against
- [WSL disk and speed](wsl-disk-and-speed.md) — `wsl-tools`; when to rebuild the distro's disk for
  a reclaim, and when to delete it instead to prove the machine is reproducible

## Three tools are documented as system components instead

`dotfiles` is in [Management Interface](../architecture/management-interface.md),
`packages` in [Package Management](../architecture/package-management.md), and
`tmux-sessions` in [tmux Sessions](../architecture/tmux-sessions.md). Each is a
part of the system its page describes rather than a tool standing on its own.
Explaining the system is what explains the tool, so splitting one off into an
apps page would leave both halves incomplete.
