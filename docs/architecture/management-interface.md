# Management Interface

How you drive this repository: a `dotfiles` CLI that works from anywhere, a `task`
front door for work inside the repo, and one shared implementation underneath both.

## Layering

Two front doors sit over the same scripts, so neither can drift from the other:

```text
dotfiles <verb>          task <verb>
        \                   /
         install/ops/*.sh          composite operations
         update.sh / install.sh    the two standalone drivers
         symlinks/ · parse_packages.py · install/common/*
```

`install/ops/` holds the operations that take more than one step — resolving the
platform, layering `common` under a platform overlay, ordering an unlink, running the
WSL shell sync, guarding a test suite, running mkdocs through `uv`. Anything that is
already a single command is invoked directly by both front doors with no wrapper.

Platform detection belongs to those scripts, which source
`install/platform-detection.sh`. Do not reintroduce it into `Taskfile.yml`.

## The `dotfiles` CLI

`apps/common/dotfiles`, deployed to `~/.local/bin` by the symlink manager along with
every other app. It resolves the repository by following its own symlink, so every
verb works from any directory.

```bash
dotfiles                       # help
dotfiles update [GROUP...]     # see "Selective updates" below
dotfiles install --machine NAME
dotfiles link | relink         # aliases for the two symlink verbs actually typed
dotfiles symlinks <verb>       # link, relink, unlink, check, show
dotfiles doctor                # broken symlinks + package-manifest drift
dotfiles test [SUITE]          # all, unit, integration, watch
dotfiles docs <verb>           # serve, build, deploy
dotfiles windows <verb>        # WSL only: setup, bundle, offline, sync
dotfiles pull                  # pull, relinking when deployed files changed
dotfiles status | path | edit
```

`dotfiles pull` relinks automatically when the pulled diff touched `apps/`, `configs/`,
or `shell/`. A pull that adds a config without relinking leaves the machine stale, and
relink is idempotent, so there is no reason to defer it.

The command table at the top of the script is the single source of truth for both help
output and dispatch; `tests/apps/dotfiles.bats` fails if the two disagree.

First-run bootstrap on a bare machine still uses `./install.sh` directly — the CLI's
symlink does not exist until the repo has been deployed once.

## Selective updates

`update.sh` owns a registry of phases, each belonging to a group. The CLI passes its
arguments straight through, so `task update -- --no-system` behaves identically.

| Group | Contents | Notes |
|---|---|---|
| `system` | brew/mas, apt, pacman/yay/flatpak | Needs sudo, dominates the runtime |
| `languages` | Go toolchain, rustup, uv | The managers themselves |
| `tools` | go, cargo, uv, npm, GitHub releases, custom installers | The installed binaries |
| `plugins` | shell, tmux, Neovim | |

```bash
dotfiles update                  # everything
dotfiles update tools plugins    # named groups only
dotfiles update --no-system      # skip the sudo-gated, slowest group
dotfiles update --mine           # only tools owned by datapointchris
dotfiles update --list           # every group and its phases
dotfiles update --dry-run
```

`--mine` narrows each phase to packages whose GitHub owner is `datapointchris`, and
skips the phases that have no owner to filter on rather than silently running them in
full. Ownership is derived from whichever field carries it — `repo`, `github_repo`, or a
Go import path in `package` — not from a `personal` tag, because a tag has to be
remembered on every new tool and silently excludes whatever it misses.

Updates are manifest-aware when `MACHINE` is set in `~/.env`, so a machine only updates
what it actually installs. Failures are collected through `run_installer` into a report
printed at the end, the same machinery `install.sh` uses.

The phase registry is also the seam the unit tests use: `UPDATE_SOURCE_ONLY=true source
update.sh` exposes `selected_phase_names` without running anything, so selection is
tested without resolving package lists.

## Why there is a CLI now

A standalone `dotfiles` CLI was considered in July 2026 and deliberately not built, on
the grounds that it would "only re-wrap existing scripts for a cosmetic rename —
maintenance cost with no capability gain." That reasoning was later reversed, because
two capabilities turned out to be missing rather than merely renamed:

**`task` cannot run from outside the repository.** Task discovers `Taskfile.yml` by
walking up from the working directory, so every management action was gated behind a
`cd`. This is structural, not cosmetic — no amount of Taskfile work fixes it.

**`update.sh` had no argument surface at all.** Its final line was a bare `main`, so
there was no way to skip the sudo-gated system phase or to refresh only your own tools.
Selective update did not exist anywhere in the repository.

It is bash, in this repository, rather than a Go binary with a release pipeline. The
CLI's entire job is invoking scripts that only exist inside the cloned repo, so a
separately-distributed binary could never function on its own — goreleaser and
`goselfupdate` would buy a distribution channel that cannot be used. `git pull` is
already the update mechanism, which is what `dotfiles pull` wraps.

## Ownership

| Concern | Owner |
|---|---|
| Machine bootstrap | `install.sh` (`--machine`, sudo; inherently one-shot) |
| Updating | `update.sh` — phase registry, groups, manifest and owner filtering |
| Composite operations | `install/ops/` — shared by both front doors |
| Symlink management | `symlinks/cli.py` |
| Package queries | `install/parse_packages.py` — types, manifests, owners |
| Manifest drift | `packages verify` |
| Tool discovery | `toolbox` (across all installed tools) |
| Cross-repo operations | `forge` |

The `apps/` scripts (`menu`, `notes`, `backmeup`, `safekeep`, …) remain **independent
user tools** with their own identity and `toolbox` discovery. Folding them into
`dotfiles <subcommand>` would be a regression, not a consolidation.
