# Management Interface

How you drive this repository — and why it is a `task` front door, not a bespoke CLI.

## The front door: `task`

All day-to-day management runs through [Task](https://taskfile.dev). `task --list`
is the discoverable index; the everyday verbs live at the top level:

```bash
task install -- --machine NAME   # bootstrap a machine (wraps install.sh; needs sudo)
task update                      # update everything (wraps update.sh)
task link                        # create symlinks           (→ symlinks:link)
task relink                      # rebuild symlinks idempotently (→ symlinks:relink)
task doctor                      # health check: symlinks + package-manifest drift
```

The namespaced tasks (`symlinks:*`, `test:*`, `docs:*`, `windows:*`) remain for the
less-common operations. `install` and `update` front the two standalone scripts;
`link`/`relink` delegate to their `symlinks:*` equivalents; `doctor` aggregates
`symlinks check` and `packages verify`.

## Why not a dedicated `dotfiles` CLI

A standalone `dotfiles` binary (Go or Python) was considered and **deliberately not
built**. The management surface is already consolidated and manifest-driven, so a CLI
would only re-wrap existing scripts for a cosmetic rename — maintenance cost with no
capability gain.

What already exists:

| Concern | Owner |
|---|---|
| Machine bootstrap | `install.sh` (`--machine`, sudo; inherently one-shot) |
| Updating everything | `update.sh`, driven by `packages.yml` via `parse_packages.py` |
| Symlink management | `symlinks/cli.py` (idempotent, the one operation that warranted a real CLI) |
| Manifest drift | `packages verify` |
| Tool discovery | `toolbox` (across all installed tools) |
| Cross-repo operations | `forge` (dies + ad-hoc commands) |

The `apps/` scripts (`menu`, `notes`, `backmeup`, `safekeep`, …) are **independent user
tools** with their own identity and `toolbox` discovery. Folding them into
`dotfiles <subcommand>` would be a regression, not a consolidation.

The single-entry-point ergonomics the CLI idea was chasing are delivered by promoting
`task` to the front door — an afternoon's work in `Taskfile.yml`, not a new binary with
its own release pipeline. This follows the repository's "prefer industry-standard
defaults, no cruft that only matters at scale" principle.
