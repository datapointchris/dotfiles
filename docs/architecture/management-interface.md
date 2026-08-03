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

## Selective installs and updates

`install.sh` and `update.sh` share one phase registry, `install/phases.sh`, so both take
the same selectors and flags and differ only in the verb. The CLI passes its arguments
straight through, so `task update -- --no-system` behaves identically.

| Group | Contents | Notes |
| --- | --- | --- |
| `system` | brew/mas, apt, pacman/yay/flatpak | Needs sudo, dominates the runtime |
| `languages` | Go toolchain, rustup, uv | The managers themselves |
| `tools` | go, cargo, uv, npm, GitHub releases, custom installers | The installed binaries |
| `config` | symlink deployment, zsh setup | Install only — nothing to update |
| `plugins` | shell, tmux, Neovim | |

A selector is a group name **or** a phase name; `--list` prints every phase under its
group, and each one shown is selectable. Listing names that could not be given as
arguments was the original discoverability bug.

```bash
dotfiles update                  # everything
dotfiles update tools plugins    # named groups
dotfiles update go-tools         # a single phase
dotfiles update --no-system      # skip the sudo-gated, slowest group
dotfiles update --mine           # only tools owned by datapointchris
dotfiles install --mine          # install those tools, no brew or casks
dotfiles install --list --dry-run
```

`--mine` narrows each phase to packages whose GitHub owner is `datapointchris`, and
skips the phases that have no owner to filter on rather than silently running them in
full. Ownership is derived from whichever field carries it — `repo`, `github_repo`, or a
Go import path in `package` — not from a `personal` tag, because a tag has to be
remembered on every new tool and silently excludes whatever it misses.

`dotfiles install --mine` is the command that matters most in practice: a newly released
personal tool has to be installed before any self-updater can maintain it, and those
tools span four sections (`go_tools`, `github_releases`, `custom_installers`,
`git_uv_tools`), so owner is the only selector that reaches all of them at once.

Both commands are manifest-aware when `MACHINE` is set in `~/.env`. The narrowing is
built once in `install/common/lib/package-query.sh` and read by every tool script, which
is what makes `--mine` reach cargo, uv, and npm — before that each script hand-rolled
the filter block and only `go-tools.sh` honoured the owner.

The phase registry is also the seam the unit tests use: sourcing either script exposes
`selected_phase_names` without running anything — `main` is guarded on
`BASH_SOURCE[0] == $0` in both — so selection is tested without resolving package lists.

### Update never installs

`update` reconciles what is on the machine; `install` creates. That line used to be
drawn by accident rather than intent: `go install @latest`, `cargo binstall`, and the
release installers all create as a side effect of upgrading, while `uv tool upgrade` and
`<tool> upgrade` cannot. Whether `dotfiles update` installed a newly declared tool came
down to which section of `packages.yml` it had been added to.

Every phase now skips a tool it finds missing, records it through
`install/common/lib/missing-tools.sh`, and the run ends with what was declared but not
installed. Reported rather than silently fixed, so adding a tool on one machine and
pulling on another still surfaces — which is the job the accidental behaviour was doing.

`packages missing` answers the same question on demand, and is what `doctor` calls. It
is deliberately separate from `packages verify`, which runs on every commit: `verify`
compares `packages.yml` against the manifests and installer scripts, and a machine
part-way through a rollout is not a repo defect that should fail a commit.

### What a phase is allowed to claim

A per-tool line must be derived from observed state: a version or ref that changed, or a
non-zero exit. It may never be derived from "the command returned", because
`uv tool upgrade`, `cargo binstall`, `npm update -g`, and `git pull --quiet` all exit 0
whether or not anything changed. Each of those phases snapshots the installed version
through `install/common/lib/installed-versions.sh` before and after, and reports
`already at latest`, `updated: <before> → <after>`, or a failure from the difference.

A phase-level line reports only that the phase completed, and is worded so — `Homebrew
update completed`, not `Homebrew packages updated` — because a system package manager
offers no cheap way to tell a no-op from real work.

Where a tool already reports its own outcome accurately, the installer delegates instead
of re-deriving one. `theme.sh --update` and `font.sh --update` run `theme upgrade` /
`font upgrade`, let their output through, and propagate the exit code. The earlier
version matched a sentinel string against their output and always missed, printing
`theme upgraded` on every run; it also ended in an unconditional `exit 0`, so a genuine
failure never reached the report.

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
| --- | --- |
| Machine bootstrap | `install.sh` (`--machine`, sudo) |
| Installing and updating | `install.sh` / `update.sh` over the shared `install/phases.sh` registry |
| Phase selection | `install/phases.sh` — groups, phases, `--mine`, `--skip`, `--dry-run` |
| Package query narrowing | `install/common/lib/package-query.sh` — manifest and owner filters |
| Composite operations | `install/ops/` — shared by both front doors |
| Symlink management | `symlinks/cli.py` |
| Package queries | `install/parse_packages.py` — types, manifests, owners |
| Registry drift | `packages verify` — packages.yml vs manifests vs scripts |
| Machine drift | `packages missing` — this machine vs what its manifest declares |
| Tool discovery | `toolbox` (across all installed tools) |
| Cross-repo operations | `forge` |

The `apps/` scripts (`menu`, `notes`, `backmeup`, `safekeep`, …) remain **independent
user tools** with their own identity and `toolbox` discovery. Folding them into
`dotfiles <subcommand>` would be a regression, not a consolidation.
