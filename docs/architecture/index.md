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

Two-layer approach: common base + platform overlay.

**How it works**:

1. Links `configs/common/` configs to `$HOME`
2. Overlays platform-specific files (auto-detected: macos, wsl, arch, or generic linux)
3. Links apps from `apps/{platform}/` to `~/.local/bin/`
4. Links shell source files from `shell/{platform}/` to `~/.local/shell/`

**Common commands** (the `dotfiles` CLI works from any directory; `task` is equivalent
but only from inside the repo — see [Management Interface](management-interface.md)):

```bash
dotfiles link               # Deploy all symlinks
dotfiles relink             # Complete refresh (remove and recreate)
dotfiles update             # Update everything (or a subset: --mine, --no-system)
dotfiles doctor             # Health check: symlinks + package-manifest drift
dotfiles symlinks check     # Verify symlinks are correct
dotfiles symlinks show      # Show all symlinks
```

**Example results**:

- `configs/common/.config/zsh/.zshrc` → `~/.config/zsh/.zshrc`
- `configs/macos/.config/git/platform.gitconfig` → `~/.config/git/platform.gitconfig` (adds to common)
- `apps/common/menu` → `~/.local/bin/menu`

## Package Management

**System Packages**: Homebrew (macOS), apt (Ubuntu/WSL, and generic Debian/Ubuntu LXCs), pacman (Arch)

**Language runtimes**: managed per language via `install/packages.yml` — version managers where useful (uv, rustup, go) or system packages otherwise (Node.js)

**Why separate**: Version managers provide cross-platform consistency and project-specific versions without system conflicts.

## Machine Manifests

Installation is driven by machine manifests in `install/manifests/`. Each manifest defines exactly what gets installed. Every installed tool is declared as a name in a list; the name must resolve to a catalog entry in `install/packages.yml`. `packages verify` enforces this bidirectionally (every name → an entry, every entry → a name that references it or a warning).

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

Runtime installation is **derived from list presence**, not from explicit booleans. A non-empty `go_tools:` list triggers the Go runtime install; a non-empty `npm_globals:` list triggers nvm + Node; `uv_tools:` or `git_uv_tools:` triggers uv. The deprecated `go: true` / `rust: true` / `nvm: true` / `uv: true` / `tenv: true` gates were removed in the Phase 1.6 cleanup — `packages verify` flags any manifest that still sets them.

Run installation with: `bash install.sh --machine archlinux-personal-workstation`

## Shell Source Files

Shell functions and aliases live in `shell/` organized by platform, deployed via symlinks — no build step required.

- **Cross-platform**: `shell/common/functions.sh` and `shell/common/aliases.sh` → `~/.local/shell/`
- **Platform-specific**: `shell/{platform}/{platform}.sh` (macos, arch, wsl, linux, windows) → `~/.local/shell/{platform}.sh`
- **Role-specific**: `shell/roles/{role}.sh` (work, personal, server) → `~/.local/shell/roles/{role}.sh`
- **`.zshrc` sources them explicitly** using the `$PLATFORM` and `$MACHINE_ROLE` env vars: `source "$SHELL_DIR/$PLATFORM.sh"` then `source "$SHELL_DIR/roles/$MACHINE_ROLE.sh"`

Platform answers *which OS*, role answers *what the machine is for*, and they are deliberately independent — employer infrastructure belongs to the work role, not to WSL, and a personal WSL box would want none of it. The role overlay loads second so it can build on what the platform exported.

A role overlay does not have to live in this repo. `.zshrc`, `menu`, and the symlink manager all guard on the file existing, and `relink` only removes symlinks that resolve into the repo — so a real file at `~/.local/shell/roles/<role>.sh` survives every relink untouched. That is the supported way to keep employer-specific shell code off a synced repo entirely, backed up with `safekeep` instead.

Unlike a platform overlay, **every** role file is linked on every machine and `MACHINE_ROLE` selects one at shell startup, so changing a machine's role is a `~/.env` edit rather than a relink. A role with nothing to add ships no file at all; the source is guarded, like an optional platform overlay.

Windows Git Bash cannot follow symlinks across the WSL boundary, so `install/wsl/sync-windows-shell.sh` copies the files instead and writes the `.bashrc` that loads them. The load order is the `SHELL_FILES` array in that script, which is also its copy manifest. The generated `.bashrc` sources each file separately: a broken file then costs only itself and names itself on the way out. An earlier version concatenated everything into one `combined.sh` for startup speed, which measured at ~0.1ms of saved file opens against a ~60ms startup, and turned one syntax error into a shell with no aliases or functions at all.

## Platform Detection

**Shell** (`configs/common/.config/zsh/.zshrc`):

```sh
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
elif [[ -f /proc/version ]] && grep -q Microsoft /proc/version; then
    # WSL
elif [[ -f /etc/arch-release ]]; then
    # Arch
else
    # generic Debian/Ubuntu Linux → the `linux` platform (LXCs, small boxes)
fi
```

**Install script**: Platform is read from the machine manifest via `manifest_field "platform"` rather than auto-detected.

## Configuration Layers

Configurations use inheritance: shared base with platform overrides.

**Example: Git Config**

Git reads both `~/.config/git/config` and `~/.gitconfig`, in that order, and the repo uses the
split deliberately. Everything shared — delta, the nvim mergetool, aliases, `pull.rebase` — ships
from `configs/common/.config/git/config`, which git loads natively with no include wiring. Each
platform adds only what genuinely differs through `configs/<platform>/.config/git/platform.gitconfig`:
the `gh` credential helper path, and `core.autocrlf` on WSL. That file is pulled in by an include
at the end of the common config and is ignored while absent, so a platform needing nothing ships
nothing.

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

## Deep Dives

<div class="grid cards" markdown>

- :material-package-variant: **[Package Management](package-management.md)**

    System vs language version managers

- :material-tools: **[Tool Composition](tool-composition.md)**

    How tools work together

</div>
