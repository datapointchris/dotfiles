# Architecture

How the dotfiles repository is organized and why.

## Structure

```text
dotfiles/
├── platforms/          # System configurations
│   ├── common/         # Shared configs (all platforms)
│   ├── macos/          # macOS-specific overrides
│   ├── wsl/            # WSL Ubuntu overrides
│   └── arch/           # Arch Linux overrides
├── apps/               # Personal CLI applications
│   ├── common/         # Cross-platform tools
│   ├── macos/          # macOS-specific tools
│   └── sess/           # Session manager (Go)
└── management/         # Repository tooling
    ├── symlinks/       # Symlink management tool
    ├── taskfiles/      # Task automation
    ├── packages.yml    # Package definitions
    └── *.sh            # Bootstrap scripts
```

## Symlink System

Two-layer approach: common base + platform overlay.

**Step 1**: Link common files

```sh
symlinks link common
```

Links `platforms/common/` to `$HOME`:

```text
platforms/common/.config/zsh/.zshrc → ~/.config/zsh/.zshrc
platforms/common/.config/tmux/tmux.conf → ~/.config/tmux/tmux.conf
```

**Step 2**: Overlay platform files

```sh
symlinks link macos
```

Overlays platform-specific files:

```text
platforms/macos/.gitconfig → ~/.gitconfig  (overrides common if it existed)
platforms/macos/.profile → ~/.profile
```

Platform files override common files when both exist.

**Step 3**: Link apps

```sh
# Apps are linked to ~/.local/bin/ automatically
```

Symlinks applications:

```text
apps/common/menu → ~/.local/bin/menu
apps/common/notes → ~/.local/bin/notes
apps/common/toolbox → ~/.local/bin/toolbox
apps/common/theme-sync → ~/.local/bin/theme-sync
```

## Package Management

**System Packages**: Homebrew (macOS), apt (Ubuntu), pacman (Arch)

**Language Versions**: uv (Python), nvm (Node.js)

**Why separate**: Version managers provide cross-platform consistency and project-specific versions without system conflicts.

## Platform Detection

**Shell** (`platforms/common/.config/zsh/.zshrc`):

```sh
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
elif [[ -f /proc/version ]] && grep -q Microsoft /proc/version; then
    # WSL
elif [[ -f /etc/arch-release ]]; then
    # Arch
fi
```

**Taskfile** (`Taskfile.yml`):

```yaml
vars:
  PLATFORM:
    sh: |
      if [ "$(uname)" = "Darwin" ]; then
        echo "macos"
      elif [ -f /etc/arch-release ]; then
        echo "arch"
      else
        echo "linux"
      fi
```

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

**Separate Theme Systems**: Ghostty has 600+ themes with live preview. tinty provides Base16 sync across tmux/bat/fzf/shell. Both run in parallel for flexibility.

## Advantages

**Minimal Duplication**: Only platform differences exist in platform directories.

**Clear Separation**: platforms/common/ for shared, platform dirs for quirks only, apps/ for tools, management/ for repo tooling.

**Easy Maintenance**: Update shared config once, all platforms benefit.

**Testable**: Each platform can be tested independently with VMs.

## Trade-offs

**Symlink Complexity**: Two-layer system adds complexity, but `symlinks` tool handles it with clear errors.

**Platform Knowledge**: Need to know whether to edit `platforms/common/` or platform dir. Experience makes this clear.

See [Platform Differences](../reference/platforms.md) for platform-specific quirks.
