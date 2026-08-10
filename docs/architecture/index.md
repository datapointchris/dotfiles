---
icon: material/city
---

# Architecture

How the dotfiles repository is organized and why.

**External tools** (installed from GitHub, not in this repo):

- `toolbox`: Go app via `go install github.com/datapointchris/toolbox`
- `sesh`: Go app via `go install github.com/joshmedeski/sesh/v2`
- `theme`, `font`: Bash tools cloned to `~/.local/share/`

## Symlink System

A common base plus one overlay per coordinate axis, across three trees:
`configs/` into `$HOME`, `apps/` into `~/.local/bin/`, `shell/` into
`~/.local/shell/`. Which overlays a machine loads is decided by its coordinates
rather than by a platform string, so the Wayland tree lives once under
`display/wayland/` regardless of which Linux is underneath it, and the apt
helpers reach the Ubuntu work box as well as the LXC.

Driven through `dotfiles symlinks`, which works from any directory; `task` is equivalent
but only from inside the repo — see [Management Interface](management-interface.md).
The layer scheme, and why two overlays may never claim one target, is
[Symlinks Manager](../reference/tools/symlinks.md).

## Package Management

**System Packages**: Homebrew (macOS), apt (Ubuntu/WSL, and generic Debian/Ubuntu LXCs), pacman (Arch)

**Language runtimes**: each through its own version manager — uv, rustup, the go tarball, and fnm for Node. None is subscribed to: a machine gets Go because it declared `go_tools` and Rust because it declared `cargo_packages`, so the runtime is derived from the tool lists that need it and `install/packages.yml` carries only its version floor.

**Why separate**: Version managers provide cross-platform consistency and project-specific versions without system conflicts.

## Machine Manifests

Installation is driven by machine manifests in `install/manifests/`. Each manifest defines exactly what gets installed. Every installed tool is declared as a name in a list; the name must resolve to a catalog entry in `install/packages.yml`. `dotfiles machines check` enforces this bidirectionally (every name → an entry, every entry → a name that references it or a warning).

```yaml
# install/manifests/archlinux-personal-workstation.yml
machine: archlinux-personal-workstation
platform: archlinux

function_groups: [core, git, python, aws, docker, network, reference, node, fzf]
alias_groups: [core]

system_packages: workstation   # or `core` for a minimal server (linux-lxc-server)
go_tools: [task, cheat, terraform-docs, ...]
github_releases: [fzf, neovim, lazygit, yazi, tree-sitter, tenv, ...]
custom_installers: [bats, awscli, claude-code, terraform-ls, ...]
cargo_packages: [bat, fd-find, eza, zoxide, ...]
npm_globals: [typescript-language-server, prettier, ...]
uv_tools: [ruff, mypy, basedpyright, ...]
git_uv_tools: [refcheck, indy, ...]
# ... etc
```

Runtime installation is **derived from list presence**, not from explicit booleans. A non-empty `go_tools:` list triggers the Go runtime install; a non-empty `npm_globals:` list triggers nvm + Node; `uv_tools:` or `git_uv_tools:` triggers uv. The deprecated `go: true` / `rust: true` / `nvm: true` / `uv: true` / `tenv: true` gates were removed in the Phase 1.6 cleanup — the manifest loader refuses any manifest that still sets them, naming the replacement.

Run installation with `bash install.sh --machine archlinux-personal-workstation`
for the CLI, then the `dotfiles apply --machine ...` it prints for the machine.

## Shell Source Files

Shell functions and aliases live in `shell/`, deployed via symlinks — no build step required.

- **Shared**: `shell/common/` → `~/.local/shell/`
- **Per coordinate**: `shell/<axis>/<value>/` → `~/.local/shell/<axis>/<value>/`, keeping the path so a sourced file says which coordinate asked for it
- **Machine-local**: `~/.local/shell/local.sh` — a real file that exists in no repo, described below

`.zshrc` sources `common/` and then loops over the six `DOTFILES_*` variables in
`~/.env`, sourcing every `.sh` in each overlay it finds and `local.sh` last. An
overlay directory that does not exist is skipped, which is most of them: an axis
earns a directory only where something actually differs along it.

The axes replaced a single fused `PLATFORM` string, which could not say that the apt helpers belong to Ubuntu-on-WSL *and* to the Debian LXC, or that the Wayland config belongs to any Linux running it rather than to Arch. A `MACHINE_ROLE` axis (work, personal, server) was tried alongside `PLATFORM` and removed before the split: it was rendered from the same manifest, so it carried no information `MACHINE` did not, and it declared three values while shipping a single file that served a single machine. That file was employer infrastructure, which the machine-local overlay handles instead — a better fit, because that code was never shareable in the first place.

### The machine-local overlay

`~/.local/shell/local.sh` is shell code this repo declares but deliberately never contains, for the work box's employer infrastructure — internal hostnames, share paths, Okta profiles. It is a real file among the symlinks, sourced last so it can build on what the coordinate overlays exported.

The repo knows it exists without knowing its contents. `install/flags.yml` declares it as a `required_files` entry narrowed to one machine, so `dotfiles env apply` names the path in the generated `~/.env` — which is what tells a rebuild where the file goes — and `dotfiles check` reports it missing. That is the same split as the `required:` values beside it, one level up: a required file rather than a required value.

It is restored by `safekeep`, not installed, so it is legitimately absent between `dotfiles apply` and the restore step of a rebuild. Both consumers guard on the file existing, and `relink` only removes symlinks that resolve into the repo, so a real file there survives every relink untouched.

The split to hold to is mechanism versus values: mounting a Windows share is a WSL capability, so `mount-cifs` lives in `shell/host/wsl/wsl.sh` and takes the share as an argument. Only the wrappers naming actual hosts go in `local.sh`.

Windows Git Bash cannot follow symlinks across the WSL boundary, so `install/wsl/sync-windows-shell.sh` copies the files instead and writes the `.bashrc` that loads them. The load order is the `SHELL_FILES` array in that script, which is also its copy manifest. The generated `.bashrc` sources each file separately: a broken file then costs only itself and names itself on the way out. An earlier version concatenated everything into one `combined.sh` for startup speed, which measured at ~0.1ms of saved file opens against a ~60ms startup, and turned one syntax error into a shell with no aliases or functions at all.

## What a machine is, and who says so

Nothing detects it. `MACHINE` is the one hand-chosen value; it selects a
manifest, and the manifest declares where the machine sits on each of the six
axes in `src/dotfiles/coordinates.py`. `dotfiles env apply` writes those
coordinates into `~/.env` as `DOTFILES_PKG`, `DOTFILES_OS` and their four
siblings, which is what every shell and every overlay reads.

Detection was tried and is what the declaration replaced: a wsl manifest whose
`~/.env` was missing fell back to a guess and deployed the linux shell overlay
for a whole install. A guess also cannot answer half the axes — nothing on a box
knows whether it is on employer or fleet network, or whether it is meant to be a
workstation or a server.

`dotfiles machines show <name>` prints the resolved tuple for any manifest,
including ones this machine is not.

## Configuration Layers

Configurations use inheritance: a shared base with coordinate overlays on top.

**Example: Git Config**

Git reads both `~/.config/git/config` and `~/.gitconfig`, in that order, and the repo uses the
split deliberately. Everything shared — delta, the nvim mergetool, aliases, `pull.rebase` — ships
from `configs/common/.config/git/config`, which git loads natively with no include wiring. One
coordinate adds what genuinely differs, through `configs/host/wsl/.config/git/overlay.gitconfig`:
`core.autocrlf`, because a checkout on the Linux side is edited from Windows tools too. That file
is pulled in by an include at the end of the common config and is ignored while absent, so every
other machine ships nothing.

The `gh` credential helper used to be in that overlay and is now common, which is what collapsed
three near-identical files into one. It was per-platform only because it named an absolute path —
`/usr/bin/gh` on Linux, `/usr/local/bin/gh` on an Intel Mac, and `/opt/homebrew/bin/gh` on an Apple
Silicon one, a distinction no platform string draws. `gh` unqualified resolves everywhere git runs
here.

Identity is the exception, and it is not in this repo at all. `user.name` and `user.email` differ
per *machine* rather than per platform — a machine that hosts both employer and personal
repositories needs a different default from one that hosts only personal work — so they belong in
`~/.gitconfig`, which git reads last and which nothing here writes. The common config sets
`user.useConfigOnly = true` so that a machine without one fails loudly rather than inventing an
author from the hostname. Scoping identity per repository on a mixed machine is a
`~/.gitconfig` concern too, and `includeIf "hasconfig:remote.*.url:..."` keys on the remote rather
than the checkout path, so it survives a repo being cloned somewhere unexpected.

**Example: Neovim**

Common (`configs/common/.config/nvim/`): Base LSP, core plugins, keybindings

Platform-specific (optional): platform LSP configs

## Design Decisions

**Symlinks over Stow**: Custom tool provides better two-layer linking, clearer error messages, platform awareness.

**Taskfile over Makefile**: Cross-platform consistency, better syntax for complex commands, modular includes, self-documenting.

**Version Managers for Languages**: Same Node/Python versions across platforms, project-specific versions, no system conflicts.

**Unified Theme System**: The `theme` CLI generates consistent configs for ghostty, tmux, btop, and Neovim from a single `theme.yml` source file per theme.

## The cost of the layering

The two-layer scheme buys one shared edit reaching every platform, and charges
one recurring question: does this belong in `configs/common/` or in the platform
directory? Getting it wrong is quiet — a setting lands in `common/` that only
one OS can honour, and the others carry it harmlessly until the day one does
not.

The test is whether the *other* platforms would want it if they could run it. A
`.gitconfig` alias belongs in common even though only one machine uses that
remote; a Homebrew path does not, because it is meaningless elsewhere rather
than merely unused. See
[Platform Differences](../reference/platforms/differences.md).

## Where to go next

The sidebar lists every architecture page; these are the three that answer the
questions asked most often.

[Management Interface](management-interface.md) is the one to read first — the
two front doors, why `plan` and `check` are different questions, and what
`~/.env` decides.
[Package Management](package-management.md) is which installer a tool gets and
why. [Observability](observability.md) is what a run leaves behind and who reads
it, which is where to start when something reported a machine wrongly.
