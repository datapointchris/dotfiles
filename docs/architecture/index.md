---
icon: material/city
---

# Architecture

How the dotfiles repository is organized and why.

## Structure

```text
dotfiles/
├── platforms/           # Platform configurations (what gets deployed)
│   ├── common/          # Shared configs (all platforms)
│   ├── macos/           # macOS-specific overrides
│   ├── wsl/             # WSL Ubuntu overrides
│   ├── arch/            # Arch Linux overrides
│   └── ubuntu/          # Ubuntu server overrides
├── apps/                # Personal CLI applications (shell scripts)
│   ├── common/          # Cross-platform: menu, notes, backup-dirs, patterns
│   └── macos/           # macOS-specific tools
├── management/          # Repository management
│   ├── machines/        # Machine manifests (what to install per computer)
│   ├── shell/           # Modular shell aliases and functions (build source)
│   │   ├── aliases/     # Alias group files (core.sh, platform-*.sh)
│   │   └── functions/   # Function group files (core.sh, git.sh, fzf.sh, ...)
│   ├── symlinks/        # Symlinks manager (Python)
│   ├── common/          # Shared installers and libraries
│   ├── {platform}/      # Platform-specific install scripts
│   └── packages.yml     # Package definitions
├── Taskfile.yml         # Task automation
└── docs/                # MkDocs documentation
```

**External tools** (installed from GitHub, not in this repo):

- `sess`, `toolbox`: Go apps via `go install github.com/datapointchris/...`
- `theme`, `font`: Bash tools cloned to `~/.local/share/`

## Symlink System

Two-layer approach: common base + platform overlay.

**How it works**:

1. Links `platforms/common/` configs to `$HOME`
2. Overlays platform-specific files (auto-detected: macos, wsl, arch, or ubuntu)
3. Links apps from `apps/{platform}/` to `~/.local/bin/`
4. Excludes generated shell files (aliases.sh, functions.sh) -- these are built by `build-shell.sh`

**Common commands**:

```bash
task symlinks:link      # Deploy all symlinks
task symlinks:check     # Verify symlinks are correct
task symlinks:show      # Show all symlinks
task symlinks:relink    # Complete refresh (remove and recreate)
```

**Example results**:

- `platforms/common/.config/zsh/.zshrc` → `~/.config/zsh/.zshrc`
- `platforms/macos/.gitconfig` → `~/.gitconfig` (overrides common)
- `apps/common/menu` → `~/.local/bin/menu`

## Package Management

**System Packages**: Homebrew (macOS), apt (Ubuntu/WSL), pacman (Arch)

**Language Versions**: uv (Python), nvm (Node.js)

**Why separate**: Version managers provide cross-platform consistency and project-specific versions without system conflicts.

## Machine Manifests

Installation is driven by machine manifests in `management/machines/`. Each manifest defines exactly what gets installed:

```yaml
# management/machines/arch-personal-workstation.yml
machine: arch-personal-workstation
platform: arch

function_groups: [core, git, python, aws, docker, network, reference, node, fzf]
alias_groups: [core]

system_packages: true
go: true
go_tools: [task, cheat, terraform-docs, ...]
github_releases: [fzf, neovim, lazygit, yazi, ...]
custom_installers: [bats, awscli, claude-code, ...]
rust: true
nvm: true
# ... etc
```

Run installation with: `bash install.sh --machine arch-personal-workstation`

## Shell Build System

Shell aliases and functions are modular source files in `management/shell/` that get concatenated into single output files based on the machine manifest:

- **Source**: `management/shell/aliases/*.sh` and `management/shell/functions/*.sh`
- **Builder**: `management/shell/build-shell.sh`
- **Output**: `~/.local/shell/aliases.sh` and `~/.local/shell/functions.sh`

The manifest `function_groups` and `alias_groups` fields control which modules are included. Platform-specific groups (e.g., `platform-arch`) are added automatically based on the `platform` field.

## Platform Detection

**Shell** (`platforms/common/.config/zsh/.zshrc`):

```sh
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
elif [[ -f /proc/version ]] && grep -q Microsoft /proc/version; then
    # WSL
elif [[ -f /etc/arch-release ]]; then
    # Arch
elif [[ -f /etc/lsb-release ]] && grep -q Ubuntu /etc/lsb-release; then
    # Ubuntu
fi
```

**Install script**: Platform is read from the machine manifest via `manifest_field "platform"` rather than auto-detected.

## Configuration Layers

Configurations use inheritance: shared base with platform overrides.

**Example: Git Config**

macOS (`platforms/macos/.gitconfig`):

```gitconfig
[core]
    editor = code --wait
[credential]
    helper = osxkeychain
```

WSL (`platforms/wsl/.gitconfig`):

```gitconfig
[core]
    editor = nvim
[credential]
    helper = /mnt/c/Program\\ Files/Git/mingw64/bin/git-credential-wincred.exe
```

**Example: Neovim**

Common (`platforms/common/.config/nvim/`): Base LSP, core plugins, keybindings

Platform-specific (optional): AI plugins (CodeCompanion for macOS), platform LSP configs

## Design Decisions

**Symlinks over Stow**: Custom tool provides better two-layer linking, clearer error messages, platform awareness.

**Taskfile over Makefile**: Cross-platform consistency, better syntax for complex commands, modular includes, self-documenting.

**Version Managers for Languages**: Same Node/Python versions across platforms, project-specific versions, no system conflicts.

**Unified Theme System**: The `theme` CLI generates consistent configs for ghostty, tmux, btop, and Neovim from a single `theme.yml` source file per theme.

## Advantages

**Minimal Duplication**: Only platform differences exist in platform directories.

**Clear Separation**: platforms/common/ for shared, platform dirs for quirks only, apps/ for tools, management/ for repo tooling.

**Easy Maintenance**: Update shared config once, all platforms benefit.

**Testable**: Each platform can be tested independently with Docker containers.

## Trade-offs

**Symlink Complexity**: Two-layer system adds complexity, but `symlinks` tool handles it with clear errors.

**Platform Knowledge**: Need to know whether to edit `platforms/common/` or platform dir. Experience makes this clear.

See [Platform Differences](../reference/platforms/differences.md) for platform-specific quirks.

## Deep Dives

<div class="grid cards" markdown>

- :material-package-variant: **[Package Management](package-management.md)**

    System vs language version managers

- :material-routes: **[PATH Ordering Strategy](path-ordering-strategy.md)**

    Tool precedence and environment setup

- :material-tools: **[Tool Composition](tool-composition.md)**

    How tools work together

</div>
