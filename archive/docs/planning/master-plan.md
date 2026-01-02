# Dotfiles Modernization Master Plan

**Date Created**: 2025-11-03
**Status**: Planning Phase
**Goal**: Create a clean, cross-platform, easily installable dotfiles system focused on developer ergonomics, productivity, and joy

---

## Executive Summary

This plan outlines a comprehensive reorganization of the dotfiles repository to achieve:

1. **Clean package management**: System tools via package managers (brew/apt/pacman), languages via specialized managers (uv/nvm)
2. **Cross-platform simplicity**: Support macOS, Ubuntu WSL, Arch Linux, and Git Bash with minimal complexity
3. **Easy installation**: Task-based automation for straightforward, repeatable installs
4. **Theme synchronization**: Unified colorschemes across terminal, editors, and CLI tools
5. **Tool discovery**: Dynamic documentation and usage tracking to maximize tool utilization
6. **Minimal complexity**: Separate platform-specific logic over complex conditional branching

---

## Philosophy & Core Principles

### Developer Ergonomics, Productivity, and Joy

The ultimate purpose of these dotfiles is to create an environment that:

- **Reduces friction** in daily development tasks
- **Increases productivity** through smart automation and tooling
- **Brings joy** to the development experience through beautiful, consistent aesthetics

### Package Management Philosophy

**System Package Managers** (brew, apt, pacman):

- System utilities: bat, eza, fd, ripgrep, fzf, tmux, neovim
- Infrastructure tools: docker, terraform, awscli
- GUI applications (macOS casks)
- Compiled libraries and dependencies

**Language-Specific Version Managers**:

- **Python**: uv (cross-platform, fast, modern)
- **Node/npm**: nvm (cross-platform, industry standard)
- **Go**: Manual installation or gvm if needed
- **Ruby**: rbenv if needed

**Why This Split**:

- Cross-platform consistency for language runtimes
- Easy project-specific version management (.python-version, .nvmrc)
- System tools benefit from native package manager integration
- Clear separation of concerns

### Installation Philosophy

- **Prefer simplicity over cleverness**: Separate install scripts per platform rather than complex conditional logic
- **Idempotent operations**: Can run install scripts multiple times safely
- **Modular task structure**: Use Taskfile to organize installation into logical, independent tasks
- **Graceful degradation**: Missing optional tools shouldn't break installation

### Documentation Philosophy

- **Comprehensive yet concise**: Document the "why" behind decisions
- **Dynamic and discoverable**: Tools should be documented and discoverable from the command line
- **Learning-focused**: Help users learn about installed tools and encourage usage

---

## Current State Analysis

### Strengths

1. **Well-organized architecture**: Common/platform separation works well
2. **Comprehensive tool selection**: Wide range of modern CLI tools installed
3. **Custom symlink management**: More sophisticated than GNU Stow
4. **Existing documentation**: Good foundation in README and CLAUDE.md
5. **Cross-platform support**: Already supports macOS and WSL

### Issues to Address

1. **Package manager confusion**:
   - Node installed via brew conflicts with nvm strategy
   - markdownlint-cli duplicated in brew and npm
   - Multiple Python versions (3.10, 3.11, 3.12, 3.13, 3.14) via brew

2. **PATH ordering problems**:
   - /usr/bin before /usr/local/bin (system tools prioritized over brew)
   - GNU coreutils in PATH can cause build issues

3. **Installation complexity**:
   - Manual installation steps scattered across README
   - No unified install script
   - Platform-specific instructions hard to follow

4. **Missing features**:
   - No theme synchronization across tools
   - No tool discovery/usage tracking
   - No dynamic documentation system
   - No Taskfile for automation

5. **Scattered tool list**:
   - README lists tools but not organized by category
   - Hard to see what's installed for what purpose

---

## Problem-Specific Solutions

### 1. Package Manager Migration

#### Node.js Management

**Current State**: Node was installed via brew (now removed), npm globals in ~/.local/share/npm

**Solution**:

```bash
# nvm is already installed at ~/.config/nvm
# Add to .zshrc (already present in lines 336-338)

# Install latest LTS Node
nvm install --lts
nvm alias default lts/*

# Verify installation
node --version
npm --version

# Migrate npm global packages
npm install -g \
  markdownlint-cli \
  bash-language-server \
  prettier \
  @fsouza/prettierd \
  vscode-langservers-extracted \
  typescript-language-server \
  typescript \
  yaml-language-server \
  gh-actions-language-server \
  eslint
```

#### Python Management

**Current State**: uv installed and working, multiple brew Python versions

**Action**: Keep python@3.12 or python@3.13 in brew ONLY if needed as dependency for other brew packages. Otherwise, let uv manage all Python installations.

**Verification**:

```bash
# Check if Python is required by brew packages
brew uses --installed python@3.12
brew uses --installed python@3.13

# If nothing depends on them, remove
brew uninstall python@3.10 python@3.11 python@3.14
# Keep one version if brew packages depend on it
```

#### Shell Completions

**Current State**: uv shell completion not active in .zshrc

**Solution**: Add to .zshrc in the "TERMINAL APPS" section:

```bash
# ---------- uv ---------- #
eval "$(uv generate-shell-completion zsh)"
```

### 2. PATH Ordering Fixes

**Current Problem** (lines 280-284 in .zshrc):

```bash
add_path "/usr/local/sbin"
add_path "/usr/local/bin"
add_path "/usr/bin"  # This prepends, making /usr/bin FIRST
```

**Solution**: Reverse the order so brew tools take precedence:

```bash
# Add system bin first (will end up last in PATH)
add_path "/usr/bin"
# Add brew bins (will take precedence)
add_path "/usr/local/bin"
add_path "/usr/local/sbin"
```

**GNU Coreutils Consideration**:

The brew doctor warning about GNU coreutils states: "Putting non-prefixed coreutils in your path can cause GMP builds to fail."

**Options**:

1. **Remove GNU coreutils from PATH** (recommended for Intel Mac): macOS tools are sufficient for most use
2. **Keep them but add a flag to disable**: Add environment variable to toggle
3. **Accept the warning**: Only affects specific builds (GMP)

**Recommendation**: Add a toggle to .zshrc:

```bash
# Set to true if you need GNU coreutils (rare on Intel Mac)
USE_GNU_COREUTILS=${USE_GNU_COREUTILS:-false}

if [[ "$USE_GNU_COREUTILS" == "true" ]] && [[ "$OSTYPE" == "darwin"* ]]; then
    gnu_paths=(
        "/usr/local/opt/coreutils/libexec/gnubin"
        "/usr/local/opt/gnu-sed/libexec/gnubin"
        "/usr/local/opt/gnu-tar/libexec/gnubin"
        "/usr/local/opt/grep/libexec/gnubin"
    )
    for gnu_path in "${gnu_paths[@]}"; do
        [[ -d "$gnu_path" ]] && export PATH="$gnu_path:$PATH"
    done
fi
```

### 3. Tool Categorization System

Create a comprehensive tool taxonomy to organize the 100+ installed tools:

#### System Utilities

- **File Management**: bat, eza, fd, yazi, tree
- **Search**: ripgrep, fzf, grep
- **Process Management**: htop, btop, watch, supervisor
- **Network**: curl, wget, nmap, watch
- **Archive**: 7zip, tar, zip

#### Development Tools

- **Version Control**: git, gh, lazygit, git-delta, git-secrets
- **Editors**: neovim, vim
- **Terminal**: tmux, tmuxinator, terminal-notifier
- **Shell**: zsh, zsh-syntax-highlighting

#### Programming Languages & Runtimes

- **Python**: uv (version manager), python via uv
- **Node**: nvm (version manager), node via nvm
- **Ruby**: ruby (system)
- **Go**: go
- **Lua**: lua, luajit, luarocks
- **Other**: scala, sbcl (lisp)

#### Language Servers (via npm)

- bash-language-server
- typescript-language-server
- yaml-language-server
- vscode-langservers-extracted
- gh-actions-language-server

#### Linters & Formatters

**Python** (via uv):

- ruff
- basedpyright
- mypy
- codespell

**JavaScript/TypeScript** (via npm):

- eslint
- prettier
- prettierd

**Shell**:

- shellcheck (brew)
- shfmt (brew)

**Markdown**:

- markdownlint-cli (npm)
- mdformat (uv)

**Other**:

- stylua (cargo) - Lua formatter
- taplo (brew) - TOML formatter
- sqlfluff (uv) - SQL linter

#### Infrastructure & DevOps

- **Containers**: docker, docker-compose, lazydocker, oxker
- **Orchestration**: terraform, terraform-docs, terraform-ls, terraformer, terrascan, tflint
- **Cloud**: awscli
- **Security**: trivy, gitleaks (if using)
- **Database**: postgresql@16, dbeaver-community

#### Media & Graphics

- **Video**: ffmpeg, mpv, yt-dlp
- **Images**: imagemagick
- **Graphics**: graphviz, gource

#### macOS-Specific

- **Window Management**: aerospace, borders
- **Menubar**: sketchybar
- **System**: duti, mkcert, mas
- **Productivity**: alfred, bettertouchtool

#### Fun/Demo Tools

- **Entertainment**: cmatrix, figlet, pipes-sh, sl
- **Documentation**: glow, pandoc, tlrc

---

## Installation Strategy

### Overview

Use **Taskfile** (inspired by dkarter/dotfiles) to create modular, platform-specific installation automation.

**Benefits of Taskfile**:

- Better syntax than Makefiles
- Cross-platform (unlike some Makefile features)
- Built-in dependency management
- Can include other taskfiles (modular organization)
- Self-documenting with descriptions

### Directory Structure

```text
dotfiles/
├── Taskfile.yml                 # Main taskfile with includes
├── taskfiles/
│   ├── macos.yml               # macOS-specific tasks
│   ├── wsl.yml                 # WSL Ubuntu-specific tasks
│   ├── arch.yml                # Arch Linux-specific tasks
│   ├── brew.yml                # Homebrew tasks (auto-commits Brewfile)
│   ├── nvm.yml                 # Node.js installation via nvm
│   ├── uv.yml                  # Python tools via uv
│   ├── npm.yml                 # npm global packages
│   ├── shell.yml               # Shell plugins and configuration
│   ├── symlinks.yml            # Symlink management
│   ├── fonts.yml               # Font installation
│   └── themes.yml              # Theme synchronization
├── scripts/
│   ├── install/                # Installation scripts
│   │   ├── macos-setup.sh     # macOS bootstrap
│   │   ├── wsl-setup.sh       # WSL bootstrap
│   │   └── arch-setup.sh      # Arch bootstrap
│   └── utils/                  # Utility scripts
│       ├── tool-discovery.sh  # List installed tools
│       └── usage-tracker.sh   # Track tool usage
└── docs/
    ├── tools/                  # Per-tool documentation
    │   ├── bat.md
    │   ├── eza.md
    │   └── ... (one per major tool)
    └── TOOL_LIST.md           # Categorized tool inventory
```

### Main Taskfile Structure

```yaml
# Taskfile.yml
version: '3'

includes:
  macos:
    taskfile: ./taskfiles/macos.yml
    optional: true
  wsl:
    taskfile: ./taskfiles/wsl.yml
    optional: true
  arch:
    taskfile: ./taskfiles/arch.yml
    optional: true
  brew:
    taskfile: ./taskfiles/brew.yml
  nvm:
    taskfile: ./taskfiles/nvm.yml
  uv:
    taskfile: ./taskfiles/uv.yml
  npm:
    taskfile: ./taskfiles/npm.yml
  shell:
    taskfile: ./taskfiles/shell.yml
  symlinks:
    taskfile: ./taskfiles/symlinks.yml
  fonts:
    taskfile: ./taskfiles/fonts.yml
  themes:
    taskfile: ./taskfiles/themes.yml

tasks:
  default:
    desc: Show available tasks
    cmds:
      - task --list

  install:
    desc: Full installation for current platform
    cmds:
      - task: detect-platform
      - task: install:{{.PLATFORM}}

  detect-platform:
    internal: true
    cmds:
      - |
        if [[ "$OSTYPE" == "darwin"* ]]; then
          echo "PLATFORM=macos" >> $TASKFILE_TEMP
        elif [[ -f /proc/version ]] && grep -q Microsoft /proc/version; then
          echo "PLATFORM=wsl" >> $TASKFILE_TEMP
        elif [[ -f /etc/arch-release ]]; then
          echo "PLATFORM=arch" >> $TASKFILE_TEMP
        else
          echo "PLATFORM=unknown" >> $TASKFILE_TEMP
        fi

  install:macos:
    desc: Install everything for macOS
    cmds:
      - task: brew:install
      - task: nvm:install
      - task: npm:install-globals
      - task: uv:install-tools
      - task: symlinks:link
      - task: shell:install-plugins
      - task: fonts:install
      - task: themes:install
      - echo "✓ macOS installation complete!"

  install:wsl:
    desc: Install everything for WSL
    cmds:
      - task: wsl:install-packages
      - task: nvm:install
      - task: npm:install-globals
      - task: uv:install-tools
      - task: symlinks:link
      - task: shell:install-plugins
      - task: themes:install
      - echo "✓ WSL installation complete!"

  install:arch:
    desc: Install everything for Arch Linux
    cmds:
      - task: arch:install-packages
      - task: nvm:install
      - task: npm:install-globals
      - task: uv:install-tools
      - task: symlinks:link
      - task: shell:install-plugins
      - task: themes:install
      - echo "✓ Arch installation complete!"

  sync:
    desc: Sync changes after git pull
    cmds:
      - task: symlinks:relink
      - task: shell:reload
      - echo "✓ Sync complete!"

  update:
    desc: Update all package managers and tools
    cmds:
      - task: brew:update
      - task: nvm:update
      - task: npm:update
      - task: uv:update
      - echo "✓ All updates complete!"
```

### Example: brew.yml

```yaml
# taskfiles/brew.yml
version: '3'

tasks:
  install:
    desc: Install Homebrew if not present
    platforms: [darwin]
    cmds:
      - |
        if ! command -v brew &> /dev/null; then
          echo "Installing Homebrew..."
          /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        else
          echo "✓ Homebrew already installed"
        fi

  bundle:
    desc: Install all packages from Brewfile
    platforms: [darwin]
    deps: [install]
    dir: '{{.ROOT_DIR}}'
    cmds:
      - brew bundle --no-lock
      - task: commit-brewfile

  commit-brewfile:
    desc: Auto-commit Brewfile if changed
    dir: '{{.ROOT_DIR}}'
    cmds:
      - |
        if [[ -n $(git status --porcelain Brewfile) ]]; then
          git add Brewfile
          git commit -m "chore(brew): update Brewfile"
          echo "✓ Committed Brewfile changes"
        else
          echo "✓ No Brewfile changes"
        fi

  update:
    desc: Update Homebrew and all packages
    platforms: [darwin]
    cmds:
      - brew update
      - brew upgrade
      - brew cleanup
      - echo "✓ Homebrew updated"
```

### Example: nvm.yml

```yaml
# taskfiles/nvm.yml
version: '3'

vars:
  NVM_DIR: '{{.HOME}}/.config/nvm'

tasks:
  install:
    desc: Install nvm if not present
    cmds:
      - |
        if [[ ! -d "{{.NVM_DIR}}" ]]; then
          echo "Installing nvm..."
          curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash
          export NVM_DIR="{{.NVM_DIR}}"
          [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
        else
          echo "✓ nvm already installed"
        fi

  install-node:
    desc: Install Node.js LTS via nvm
    deps: [install]
    cmds:
      - |
        export NVM_DIR="{{.NVM_DIR}}"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
        nvm install --lts
        nvm alias default lts/*
        nvm use default
        echo "✓ Node.js LTS installed"

  update:
    desc: Update nvm and Node.js
    cmds:
      - |
        export NVM_DIR="{{.NVM_DIR}}"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
        nvm install --lts --reinstall-packages-from=current
        nvm alias default lts/*
        echo "✓ Node.js updated"
```

### Example: npm.yml

```yaml
# taskfiles/npm.yml
version: '3'

vars:
  GLOBALS:
    - markdownlint-cli
    - bash-language-server
    - prettier
    - '@fsouza/prettierd'
    - vscode-langservers-extracted
    - typescript-language-server
    - typescript
    - yaml-language-server
    - gh-actions-language-server
    - eslint

tasks:
  install-globals:
    desc: Install all npm global packages
    cmds:
      - |
        export NVM_DIR="$HOME/.config/nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
        echo "Installing npm global packages..."
        npm install -g {{.GLOBALS | join " "}}
        echo "✓ npm globals installed"

  update:
    desc: Update all npm global packages
    cmds:
      - |
        export NVM_DIR="$HOME/.config/nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
        npm update -g
        echo "✓ npm globals updated"
```

### Platform-Specific Install Scripts

Create lightweight bootstrap scripts that install the minimal requirements before running Taskfile:

#### scripts/install/macos-setup.sh

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "======================================"
echo "macOS Bootstrap"
echo "======================================"

# Install Homebrew if not present
if ! command -v brew &> /dev/null; then
    echo "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Install Taskfile via brew
if ! command -v task &> /dev/null; then
    echo "Installing Taskfile..."
    brew install go-task
fi

# Run main installation
echo "Running task install:macos..."
task install:macos

echo "======================================"
echo "✓ macOS setup complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "  1. Restart your terminal"
echo "  2. Run 'task --list' to see available commands"
echo "  3. Run 'tools-list' to see installed tools"
```

#### scripts/install/wsl-setup.sh

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "======================================"
echo "WSL Ubuntu Bootstrap"
echo "======================================"

# Update package lists
sudo apt update

# Install essential packages
sudo apt install -y curl git build-essential

# Install Taskfile
if ! command -v task &> /dev/null; then
    echo "Installing Taskfile..."
    sh -c "$(curl --location https://taskfile.dev/install.sh)" -- -d -b ~/.local/bin
fi

# Run main installation
echo "Running task install:wsl..."
task install:wsl

echo "======================================"
echo "✓ WSL setup complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "  1. Edit /etc/zsh/zshenv with: export ZSHDOTDIR=\"\$HOME/.config/zsh\""
echo "  2. Restart your terminal"
echo "  3. Run 'task --list' to see available commands"
```

---

## Theme Synchronization System

### Inspiration from External Dotfiles

Based on analysis of hamvocke, joshmedeski dotfiles and rootloops/tinty projects:

**Key Insights**:

1. **Rootloops/Tinty**: Web-based theme generator that exports to multiple formats
2. **Tinted Theming**: Base16/Base24 theme specification with templates for 100+ applications
3. **Hamvocke approach**: Define colors at terminal level, applications inherit
4. **Joshmedeski approach**: Unified Catppuccin theme with automatic light/dark switching

### Proposed System

#### Goals

1. **Single source of truth** for color schemes
2. **Synchronized themes** across terminal, neovim, tmux, bat, eza, fzf, lazygit, etc.
3. **Multiple theme support** with easy switching
4. **Light/dark mode awareness** (macOS automatic switching)

#### Architecture

```text
dotfiles/
├── themes/
│   ├── config.toml              # Theme manager config
│   ├── current -> rose-pine/    # Symlink to active theme
│   ├── rose-pine/
│   │   ├── theme.toml           # Theme definition (base16 format)
│   │   ├── ghostty.conf         # Ghostty colors
│   │   ├── tmux.conf            # Tmux colors
│   │   ├── bat.conf             # Bat theme
│   │   └── fzf.zsh              # FZF colors
│   ├── catppuccin-mocha/
│   │   └── ...
│   └── gruvbox-dark/
│       └── ...
└── common/.config/
    ├── ghostty/config
    │   └── source = ~/dotfiles/themes/current/ghostty.conf
    ├── tmux/tmux.conf
    │   └── source = ~/dotfiles/themes/current/tmux.conf
    └── zsh/.zshrc
        └── source ~/dotfiles/themes/current/fzf.zsh
```

#### Implementation Plan

1. **Install tinty** (Rust-based theme manager):

```bash
cargo install tinted-theming/tinty
# or
brew install tinty
```

1. **Create theme templates** for each tool:
   - Use tinty's template system for auto-generation
   - Manually create for tools without tinty support

1. **Theme switching command**:

```bash
# Switch theme
theme-set rose-pine

# List available themes
theme-list

# Reload current theme in all running applications
theme-reload
```

1. **Integration with system appearance** (macOS):

```bash
# In ~/.config/zsh/.zshrc
if [[ "$OSTYPE" == "darwin"* ]]; then
    # Check if dark mode is enabled
    if defaults read -g AppleInterfaceStyle &> /dev/null; then
        theme-set-variant dark
    else
        theme-set-variant light
    fi
fi
```

1. **Favorite themes list** (matching across all tools):

```toml
# themes/favorites.toml
[favorites]
themes = [
    "rose-pine",
    "rose-pine-moon",
    "catppuccin-mocha",
    "catppuccin-macchiato",
    "gruvbox-dark",
    "nord",
    "tokyo-night"
]

[mappings]
ghostty = "rose-pine"
neovim = "rose-pine"
tmux = "rose-pine"
bat = "rose-pine"
```

#### Supported Applications

**Primary** (high priority):

- Ghostty (terminal)
- Neovim (editor)
- Tmux (multiplexer)
- Bat (file viewer)
- Eza (ls colors)
- FZF (fuzzy finder)
- Lazygit (git TUI)

**Secondary** (nice to have):

- Yazi (file manager)
- Delta (git diff)
- Btop (system monitor)

### Taskfile Integration

```yaml
# taskfiles/themes.yml
version: '3'

tasks:
  install:
    desc: Install tinty theme manager
    cmds:
      - cargo install tinted-theming/tinty || brew install tinty
      - task: generate-templates

  generate-templates:
    desc: Generate theme files for all applications
    cmds:
      - tinty build

  set:
    desc: Set active theme (usage: task themes:set THEME=rose-pine)
    cmds:
      - tinty apply {{.THEME}}
      - task: reload

  reload:
    desc: Reload theme in all running applications
    cmds:
      - tmux source-file ~/.config/tmux/tmux.conf || true
      - # Ghostty will auto-reload
      - # Neovim users need to :colorscheme rose-pine
      - echo "✓ Theme reloaded"

  list:
    desc: List available themes
    cmds:
      - tinty list
```

---

## Tool Discovery & Usage Tracking System

### Goals

1. **Dynamic tool documentation**: View tool info from command line
2. **Usage tracking**: Keep count of how often tools are used
3. **Reminder system**: Suggest underutilized tools
4. **Learning aid**: Help remember what tools you have and when to use them

### Implementation

#### 1. Tool Registry

Create a structured registry of all installed tools:

```yaml
# docs/tools/registry.yml
tools:
  bat:
    category: file-viewer
    description: "Syntax-highlighting cat replacement"
    usage: "bat <file>"
    examples:
      - "bat README.md"
      - "bat -n --theme='gruvbox-dark' file.rs"
    see_also: [eza, less]
    tags: [cli, productivity]

  eza:
    category: file-management
    description: "Modern ls replacement with git integration"
    usage: "eza [options] [path]"
    examples:
      - "eza -la"
      - "eza --tree --level=2"
      - "eza --git-ignore"
    see_also: [bat, fd, tree]
    tags: [cli, productivity, git]

  ripgrep:
    category: search
    description: "Ultra-fast recursive search tool"
    usage: "rg [pattern] [path]"
    examples:
      - "rg 'function' ."
      - "rg -t py 'import' src/"
      - "rg -i 'error' --context 3"
    see_also: [fzf, fd, grep]
    tags: [cli, search, productivity]

  # ... all other tools
```

#### 2. Command-Line Tool Discovery

Create a command `tools` with subcommands:

```bash
#!/usr/bin/env bash
# ~/.local/bin/tools

CMD="${1:-list}"

case "$CMD" in
    list)
        # List all tools by category
        cat ~/.config/tools/registry.yml | yq '.tools | keys | .[]' | sort
        ;;

    categories)
        # List categories
        cat ~/.config/tools/registry.yml | yq '.tools | group_by(.category) | .[].category | select(. != null) | unique | .[]'
        ;;

    show)
        # Show details for a specific tool
        TOOL="$2"
        yq ".tools.$TOOL" ~/.config/tools/registry.yml | bat --language yaml
        ;;

    search)
        # Search tools by tag or description
        QUERY="$2"
        yq ".tools | to_entries | .[] | select(.value.description or .value.tags[] | contains(\"$QUERY\")) | .key" ~/.config/tools/registry.yml
        ;;

    random)
        # Show a random tool (for discovery)
        TOOLS=($(yq '.tools | keys | .[]' ~/.config/tools/registry.yml))
        RANDOM_TOOL=${TOOLS[$RANDOM % ${#TOOLS[@]}]}
        echo "💡 Have you tried: $RANDOM_TOOL"
        yq ".tools.$RANDOM_TOOL" ~/.config/tools/registry.yml | bat --language yaml
        ;;

    *)
        echo "Usage: tools [list|categories|show <name>|search <query>|random]"
        ;;
esac
```

**Usage examples**:

```bash
tools list                  # List all tools
tools categories            # List categories
tools show bat              # Show bat documentation
tools search git            # Find tools related to git
tools random                # Discover a random tool
```

#### 3. Usage Tracking

Track tool usage in a local SQLite database:

```bash
# ~/.local/bin/track-usage (called via shell alias wrapper)
#!/usr/bin/env bash

DB="$HOME/.local/share/tools/usage.db"
mkdir -p "$(dirname "$DB")"

# Initialize database if it doesn't exist
sqlite3 "$DB" "CREATE TABLE IF NOT EXISTS usage (
    tool TEXT PRIMARY KEY,
    count INTEGER DEFAULT 0,
    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);"

# Update usage count
TOOL="$1"
sqlite3 "$DB" "
    INSERT INTO usage (tool, count, last_used) VALUES ('$TOOL', 1, CURRENT_TIMESTAMP)
    ON CONFLICT(tool) DO UPDATE SET
        count = count + 1,
        last_used = CURRENT_TIMESTAMP;
"
```

**Integration via shell aliases**:

```bash
# In ~/.shell/aliases.sh
# Wrap commonly-used commands to track usage

function bat() {
    track-usage bat
    command bat "$@"
}

function rg() {
    track-usage ripgrep
    command rg "$@"
}

function eza() {
    track-usage eza
    command eza "$@"
}

# ... wrap other tools
```

#### 4. Usage Stats Command

```bash
#!/usr/bin/env bash
# ~/.local/bin/tools-stats

DB="$HOME/.local/share/tools/usage.db"

case "${1:-summary}" in
    summary)
        echo "=== Tool Usage Summary ==="
        sqlite3 -column -header "$DB" "
            SELECT
                tool,
                count as uses,
                datetime(last_used, 'localtime') as last_used
            FROM usage
            ORDER BY count DESC
            LIMIT 20;
        "
        ;;

    unused)
        echo "=== Tools You Haven't Used Recently ==="
        # Compare registry with usage DB to find unused tools
        comm -23 \
            <(yq '.tools | keys | .[]' ~/.config/tools/registry.yml | sort) \
            <(sqlite3 "$DB" "SELECT tool FROM usage WHERE last_used > datetime('now', '-30 days')" | sort)
        ;;

    recommendations)
        echo "💡 Try these underutilized tools:"
        sqlite3 -column "$DB" "
            SELECT tool, count
            FROM usage
            WHERE count < 5
            ORDER BY RANDOM()
            LIMIT 5;
        "
        ;;
esac
```

**Usage**:

```bash
tools-stats                 # Show top 20 used tools
tools-stats unused          # Show tools not used in 30 days
tools-stats recommendations # Get recommendations
```

#### 5. Shell Integration

Add to `.zshrc`:

```bash
# Show a random tool tip on shell startup (10% chance)
if (( RANDOM % 10 == 0 )); then
    echo "\n$(color_cyan '💡 Tool Tip:')"
    tools random
    echo ""
fi

# Show unused tools reminder once per week
LAST_REMINDER="$HOME/.local/state/tools/last-reminder"
if [[ ! -f "$LAST_REMINDER" ]] || [[ $(find "$LAST_REMINDER" -mtime +7) ]]; then
    echo "\n$(color_yellow '📊 Tool Usage Reminder:')"
    tools-stats unused | head -5
    touch "$LAST_REMINDER"
fi
```

---

## Implementation Timeline & Steps

### Phase 1: Foundation (Week 1)

**Step 1: Fix Immediate Issues** ✅

- [x] Uninstall brew node (already done)
- [ ] Fix PATH ordering in .zshrc
- [ ] Add uv shell completion to .zshrc
- [ ] Configure nvm properly
- [ ] Test that nvm and uv work correctly

**Step 2: Install Taskfile**

- [ ] `brew install go-task` (macOS)
- [ ] Create basic Taskfile.yml structure
- [ ] Test `task --list`

**Step 3: Migrate npm globals**

- [ ] Source nvm in current shell
- [ ] `nvm install --lts`
- [ ] `nvm alias default lts/*`
- [ ] Install all npm global packages
- [ ] Verify language servers work in neovim

**Verification**:

```bash
which node  # Should show nvm path
which npm   # Should show nvm path
node --version
npm --version
```

### Phase 2: Documentation (Week 1-2)

**Step 4: Create Tool Registry**

- [ ] Create `docs/tools/registry.yml`
- [ ] Document top 20 most-used tools first
- [ ] Add categories and tags
- [ ] Create the `tools` command script

**Step 5: Organize Tool List**

- [ ] Create `docs/TOOL_LIST.md` with categorization
- [ ] List all tools by category (system, dev, languages, etc.)
- [ ] Note which tools are installed by which package manager

**Step 6: Update CLAUDE.md**

- [ ] Add package management philosophy section
- [ ] Document the uv + nvm strategy
- [ ] Add tool discovery commands
- [ ] Include installation instructions reference

### Phase 3: Installation Automation (Week 2)

**Step 7: Create Taskfiles**

- [ ] `taskfiles/brew.yml` - Homebrew tasks
- [ ] `taskfiles/nvm.yml` - Node.js installation
- [ ] `taskfiles/npm.yml` - npm global packages
- [ ] `taskfiles/uv.yml` - Python tool installation
- [ ] `taskfiles/shell.yml` - Shell plugin installation
- [ ] `taskfiles/symlinks.yml` - Symlink management
- [ ] `taskfiles/fonts.yml` - Font installation

**Step 8: Create Platform-Specific Taskfiles**

- [ ] `taskfiles/macos.yml` - macOS-specific tasks
- [ ] `taskfiles/wsl.yml` - WSL-specific tasks
- [ ] `taskfiles/arch.yml` - Arch-specific tasks (prep for future)

**Step 9: Create Bootstrap Scripts**

- [ ] `scripts/install/macos-setup.sh`
- [ ] `scripts/install/wsl-setup.sh`
- [ ] `scripts/install/arch-setup.sh` (minimal prep)

**Step 10: Test Installation**

- [ ] Test on a fresh macOS user account (if possible)
- [ ] Test on WSL
- [ ] Fix any issues discovered
- [ ] Document any manual steps still required

### Phase 4: Theme Synchronization (Week 3)

**Step 11: Research & Choose Theme System**

- [ ] Evaluate tinty vs manual approach
- [ ] Choose 5-7 favorite themes to support
- [ ] Test theme generation for all primary apps

**Step 12: Implement Theme System**

- [ ] Install tinty
- [ ] Create `themes/` directory structure
- [ ] Generate theme files for: Ghostty, Neovim, Tmux, Bat, FZF, Eza
- [ ] Create `theme-set` command
- [ ] Create `taskfiles/themes.yml`

**Step 13: Test Theme Switching**

- [ ] Switch between multiple themes
- [ ] Verify all applications update correctly
- [ ] Test automatic light/dark mode switching (macOS)
- [ ] Document in CLAUDE.md

### Phase 5: Tool Discovery System (Week 3-4)

**Step 14: Build Tool Discovery**

- [ ] Complete registry.yml with all tools
- [ ] Create `tools` command with all subcommands
- [ ] Test search and discovery features

**Step 15: Implement Usage Tracking**

- [ ] Create SQLite database schema
- [ ] Create `track-usage` script
- [ ] Wrap commonly-used commands in aliases
- [ ] Create `tools-stats` command

**Step 16: Shell Integration**

- [ ] Add random tool tips to shell startup
- [ ] Add weekly unused tools reminder
- [ ] Test and tune notification frequency

### Phase 6: Cross-Platform Expansion (Week 4+)

**Step 17: WSL Refinement**

- [ ] Test full installation on WSL
- [ ] Document any WSL-specific quirks
- [ ] Ensure theme system works on WSL

**Step 18: Arch Linux Prep**

- [ ] Create basic arch.yml taskfile
- [ ] Document Arch-specific package names
- [ ] Create arch-setup.sh bootstrap script
- [ ] Test when ready to set up Arch

**Step 19: Git Bash Support (Optional)**

- [ ] Identify which aliases/functions are most useful
- [ ] Create minimal .bashrc for Git Bash
- [ ] Document limitations

### Phase 7: Polish & Maintenance (Ongoing)

**Step 20: Documentation Cleanup**

- [ ] Update README.md with new installation flow
- [ ] Create CONTRIBUTING.md for future changes
- [ ] Add troubleshooting section
- [ ] Create changelog

**Step 21: Cleanup & Deduplication**

- [ ] Review all installed tools - remove duplicates
- [ ] Remove tools that are no longer used
- [ ] Consolidate similar functionality

**Step 22: Advanced Features (Optional)**

- [ ] Add pre-commit hooks for auto-committing Brewfile
- [ ] Create update notifications
- [ ] Add dotfiles update script

---

## Testing Strategy

### Test Checklist

For each platform (macOS, WSL, Arch):

**Installation Tests**:

- [ ] Fresh install from scratch completes without errors
- [ ] All symlinks are created correctly
- [ ] All package managers are installed
- [ ] All tools are accessible in PATH
- [ ] Shell plugins load correctly
- [ ] Language servers work in neovim

**Functionality Tests**:

- [ ] nvm can switch Node versions
- [ ] uv can create virtual environments
- [ ] Themes switch correctly across all apps
- [ ] Tool discovery commands work
- [ ] Usage tracking records correctly
- [ ] task --list shows all tasks

**Idempotency Tests**:

- [ ] Running install twice doesn't break anything
- [ ] Symlink relinking works correctly
- [ ] Package updates don't cause conflicts

### Testing Environments

**macOS**:

- Primary: Test on current system
- Optional: Create a new user account for clean testing

**WSL**:

- Test on existing WSL installation
- Consider: Fresh WSL instance if possible

**Arch**:

- Test when Arch system is set up
- Use VM for early testing if needed

---

## Brewfile Organization

Clean up and organize your Brewfile with clear categories:

```ruby
# Brewfile

# ============================================
# TAPS (Third-party repositories)
# ============================================
tap "homebrew/bundle"
tap "homebrew/cask-fonts"

# ============================================
# SYSTEM UTILITIES
# ============================================

# File Management
brew "bat"              # Syntax-highlighting cat
brew "eza"              # Modern ls replacement
brew "fd"               # Fast find alternative
brew "tree"             # Directory tree viewer
brew "yazi"             # Terminal file manager
brew "duf"              # Modern df alternative
brew "duti"             # File association manager

# Search & Text Processing
brew "ripgrep"          # Ultra-fast grep
brew "fzf"              # Fuzzy finder
brew "grep"             # GNU grep
brew "gnu-sed"          # GNU sed
brew "jq"               # JSON processor

# Archive & Compression
brew "sevenzip"         # 7zip compression
brew "gnu-tar"          # GNU tar

# Process & System Monitoring
brew "htop"             # Interactive process viewer
brew "watch"            # Execute program periodically
brew "coretemp"         # CPU temperature monitoring

# Network Utilities
brew "curl"             # Transfer data with URLs
brew "wget"             # File retrieval
brew "nmap"             # Network exploration

# ============================================
# DEVELOPMENT TOOLS
# ============================================

# Version Control
brew "git"              # Version control
brew "gh"               # GitHub CLI
brew "git-delta"        # Enhanced git diff
brew "git-secrets"      # Prevent committing secrets
brew "lazygit"          # Git TUI

# Editors & Core Dev Tools
brew "neovim"           # Modern vim
brew "tmux"             # Terminal multiplexer
brew "coreutils"        # GNU coreutils
brew "findutils"        # GNU findutils

# Terminal Enhancement
brew "zsh-syntax-highlighting"  # ZSH syntax highlighting
brew "zoxide"           # Smarter cd command
brew "glow"             # Markdown renderer
brew "tlrc"             # TLDR pages (community man pages)
brew "tokei"            # Code statistics

# Task Management
brew "task"             # Task runner (go-task)

# ============================================
# PROGRAMMING LANGUAGES & RUNTIMES
# ============================================
# Note: Node managed by nvm, Python managed by uv

# Go
brew "go"               # Go programming language

# Ruby
brew "ruby"             # Ruby programming language

# Lua
brew "lua"              # Lua language
brew "luajit"           # LuaJIT compiler
brew "luarocks"         # Lua package manager
brew "lua-language-server"  # Lua LSP

# Scala/JVM
brew "sbt"              # Scala build tool
brew "openjdk"          # OpenJDK

# Other
brew "sbcl"             # Steel Bank Common Lisp

# ============================================
# LINTERS, FORMATTERS & CODE QUALITY
# Note: Language servers installed via npm, Python tools via uv
# ============================================

brew "shellcheck"       # Shell script linter
brew "shfmt"            # Shell script formatter
brew "actionlint"       # GitHub Actions linter
brew "codespell"        # Spell checker for code
brew "taplo"            # TOML formatter/linter

# ============================================
# INFRASTRUCTURE & DEVOPS
# ============================================

# Containers
brew "docker-compose"   # Docker container orchestration

# Terraform Ecosystem
brew "terraform"        # Infrastructure as code
brew "terraform-docs"   # Generate terraform docs
brew "terraform-ls"     # Terraform language server
brew "terraformer"      # Terraform state management
brew "terrascan"        # Terraform security scanner
brew "tflint"           # Terraform linter

# AWS
brew "awscli"           # AWS command line

# Container Management TUIs
brew "lazydocker"       # Docker TUI
brew "oxker"            # Docker container manager

# Security
brew "trivy"            # Container vulnerability scanner
brew "mkcert"           # Local SSL certificates
brew "gnupg"            # GPG encryption

# Monitoring
brew "supervisor"       # Process control system

# ============================================
# DATABASES
# ============================================

brew "postgresql@16"    # PostgreSQL database
brew "pgloader"         # PostgreSQL migration tool

# ============================================
# MEDIA & GRAPHICS
# ============================================

brew "ffmpeg"           # Video processing
brew "mpv"              # Media player
brew "yt-dlp"           # YouTube downloader
brew "imagemagick"      # Image processing
brew "graphviz"         # Graph visualization
brew "gource"           # Repository visualization

# ============================================
# MACOS WINDOW MANAGEMENT & PRODUCTIVITY
# ============================================

cask "aerospace"        # Tiling window manager
brew "borders"          # Window border highlights
brew "sketchybar"       # Custom menubar

# ============================================
# MACOS APPLICATIONS
# ============================================

cask "alfred"           # Launcher
cask "bettertouchtool"  # Input customization
cask "docker"           # Docker Desktop
cask "dbeaver-community" # Database GUI
cask "discord"          # Chat
cask "iterm2"           # Terminal emulator
cask "macs-fan-control" # Fan control
cask "michaelvillar-timer" # Timer app
cask "multipass"        # Ubuntu VM manager
cask "obsidian"         # Note taking
cask "slack"            # Team chat
cask "zoom"             # Video conferencing

# ============================================
# FUN / DEMO TOOLS
# ============================================

brew "cmatrix"          # Matrix effect
brew "figlet"           # ASCII art text
brew "pipes-sh"         # Animated pipes
brew "sl"               # Steam locomotive joke

# ============================================
# FONTS
# ============================================

# Install nerd fonts for terminal icons
# cask "font-fira-code-nerd-font"
# cask "font-jetbrains-mono-nerd-font"
# cask "font-meslo-lg-nerd-font"
```

---

## File Changes Summary

### Files to Create

1. **Taskfiles**:
   - `Taskfile.yml`
   - `taskfiles/brew.yml`
   - `taskfiles/nvm.yml`
   - `taskfiles/npm.yml`
   - `taskfiles/uv.yml`
   - `taskfiles/shell.yml`
   - `taskfiles/symlinks.yml`
   - `taskfiles/fonts.yml`
   - `taskfiles/themes.yml`
   - `taskfiles/macos.yml`
   - `taskfiles/wsl.yml`
   - `taskfiles/arch.yml`

2. **Scripts**:
   - `scripts/install/macos-setup.sh`
   - `scripts/install/wsl-setup.sh`
   - `scripts/install/arch-setup.sh`
   - `scripts/utils/tool-discovery.sh` (the `tools` command)
   - `scripts/utils/usage-tracker.sh` (the `track-usage` command)
   - `scripts/utils/tools-stats.sh` (the `tools-stats` command)
   - `scripts/utils/theme-set.sh` (theme switching)

3. **Documentation**:
   - `docs/MASTER_PLAN.md` (this document)
   - `docs/TOOL_LIST.md` (categorized tool inventory)
   - `docs/tools/registry.yml` (tool registry database)
   - `docs/INSTALLATION.md` (simplified installation guide)
   - Update `docs/changelog.md` with all changes

4. **Theme System**:
   - `themes/config.toml`
   - `themes/favorites.toml`
   - Create theme directories and files

5. **Brewfile**:
   - Reorganize with clear categories and comments

### Files to Modify

1. **Shell Configuration**:
   - `common/.config/zsh/.zshrc`:
     - Fix PATH ordering (lines 280-284)
     - Add uv shell completion
     - Add GNU coreutils toggle
     - Add theme system integration
     - Add tool discovery integration

2. **Documentation**:
   - `README.md`: Update with new installation instructions
   - `CLAUDE.md`: Add package management philosophy

3. **Symlinks**:
   - Potentially update `symlinks.sh` if needed for taskfile integration

### Files to Remove/Deprecate

1. **Packages**:
   - Brew: python@3.10, python@3.11, python@3.14 (conditional on dependencies)
   - Brew: markdownlint-cli (use npm version)

2. **Documentation**:
   - Consider consolidating scattered installation instructions

---

## Success Criteria

The modernization will be considered successful when:

### Installation

- [ ] Can clone repo and run a single command to install everything on each platform
- [ ] Installation is idempotent (can run multiple times safely)
- [ ] Clear error messages if something goes wrong
- [ ] Installation takes < 30 minutes on fresh system

### Package Management

- [ ] No package conflicts or duplicate tools
- [ ] Clear separation: system tools (brew/apt) vs languages (uv/nvm)
- [ ] All language servers and dev tools work correctly
- [ ] Can update all tools with single command: `task update`

### Cross-Platform

- [ ] Same workflow on macOS and WSL
- [ ] Platform-specific configs are minimal and obvious
- [ ] Arch Linux setup documented and ready to use

### Themes

- [ ] Can switch themes with one command
- [ ] All primary applications reflect theme change
- [ ] 5-7 favorite themes available and tested
- [ ] Theme persists across terminal restarts

### Tool Discovery

- [ ] Can list all installed tools from command line
- [ ] Can search tools by category or tag
- [ ] Usage tracking works for wrapped commands
- [ ] Get useful recommendations for underutilized tools

### Documentation

- [ ] CLAUDE.md reflects current architecture
- [ ] README has clear quickstart
- [ ] Tool registry has at least top 30 tools documented
- [ ] Changelog documents all major changes

### Developer Experience

- [ ] Faster workflow (less time fighting tools)
- [ ] More awareness of available tools
- [ ] Enjoyable aesthetic (consistent themes)
- [ ] Confidence in making changes (good docs, idempotent installs)

---

## Risk Mitigation

### Backup Strategy

Before starting implementation:

1. **Git commit all current changes**: Ensure clean working tree
2. **Create backup branch**: `git checkout -b backup/pre-modernization`
3. **Tag current state**: `git tag pre-modernization-2025-11-03`
4. **Test restoration**: Verify you can restore if needed

### Incremental Rollout

Implement changes in phases:

1. Start with non-destructive additions (Taskfile, docs)
2. Test each phase before moving to next
3. Keep current system working while building new
4. Switch over only when new system is fully tested

### Rollback Plan

If something breaks:

1. **Phase 1 issues**: Can revert shell config changes easily
2. **Phase 2-3 issues**: Old installation process still documented
3. **Phase 4+ issues**: New features are additions, don't break old workflow
4. **Nuclear option**: `git reset --hard backup/pre-modernization`

---

## Future Enhancements

### After Core Implementation

**Advanced Tool Discovery**:

- Web dashboard for tool statistics
- AI-powered tool recommendations based on project type
- Integration with dotfiles for sharing tool configs

**Theme System Enhancements**:

- More applications supported
- Custom theme creation wizard
- Theme preview before applying
- Per-project theme settings

**Installation Improvements**:

- Interactive installer with choices
- Minimal vs full installation options
- Auto-detection of existing tools
- Progress bars and better UX

**Cross-Platform Expansion**:

- Windows (PowerShell) support
- FreeBSD support
- Container-based testing for all platforms

**Maintenance Automation**:

- Automated Brewfile cleanup (remove unused)
- Automated tool version updates with changelog
- Security scanning of installed tools
- Health check command to verify all tools work

---

## Questions Resolved ✅

**Date Resolved**: 2025-11-03

### 1. Theme System

**Decision**: Two-phase approach

- **Phase 4 (Week 3)**: Use tinty for immediate results with Base16-compatible themes (rose-pine, gruvbox, kanagawa, etc.)
- **Future**: Build custom Rust `theme-sync` tool as learning project for full control over all 17 curated neovim colorschemes

**Rationale**:

- Tinty works with ~60% of current themes (Base16-compatible subset)
- Custom Rust tool provides excellent learning opportunity
- Full control over exact colorschemes
- See `docs/THEME_SYNC_STRATEGY.md` for detailed analysis

### 2. GNU Coreutils

**Decision**: Keep with g-prefix (standard macOS approach)

- GNU tools available as `gls`, `gsed`, `gtar`, `ggrep`
- macOS system tools remain default
- No PATH conflicts or GMP build issues

**Implementation**: Remove from front of PATH, keep installed with g-prefix

### 3. Python Brew Packages

**Decision**: Keep only if required by brew dependencies

- Run `brew uses --installed python@X.XX` to check dependencies
- Remove orphaned Python versions
- Prefer uv-managed Python for all development work
- If possible, configure brew to use uv-installed Python (needs research)

**Action**: Audit and clean up in Phase 1

### 4. Tool Tracking

**Decision**: Track commonly-used tools only, keep it simple

- No complex function wrapping that makes configs hard to read
- Focus on discovery (reminding about oxker, shell functions, etc.)
- Lightweight tracking for ~20-30 most useful tools
- Emphasize tool discovery over heavy tracking

**Philosophy**: Fun and helpful, not at expense of clean, maintainable config

### 5. Installation Testing

**Decision**: VM-based automated testing with error-fixing loop

- Create automated test environment for macOS, WSL, Arch
- Loop: install → capture errors → fix scripts → repeat
- Aim for flawless installation on target OSes
- Advanced feature, but worth the investment

**Implementation**: Phase 6-7, may use Docker/VM automation

### 6. Arch Linux

**Decision**: Prep as we go

- Create arch.yml taskfile alongside macos/wsl
- Document Arch-specific package names
- User may have Arch system soon, want to be ready
- Iterate and improve Arch support over time

**Note**: Not blocking, but include in planning

### 7. Git Bash

**Decision**: Priority for convenience features, shouldn't complicate main configs

- Include git aliases and convenience functions
- Shell utility functions that work in bash
- Minimal .bashrc for Git Bash on Windows
- Keep separate from main platform configs
- Don't add complexity to macos/wsl/arch setups for Git Bash compatibility

**Approach**: Create simple `gitbash/.bashrc` with subset of features

### 8. Homebrew Location (Bonus)

**Clarification**: `/usr/local` is correct for Intel Mac

- Cellar is standard Homebrew directory structure
- `/opt/homebrew` is only for Apple Silicon
- No migration needed ✅

---

## Appendix: Reference Links

### External Dotfiles Analyzed

- Josh Medeski: <https://github.com/joshmedeski/dotfiles>
- dkarter: <https://github.com/dkarter/dotfiles>
- hamvocke: <https://github.com/hamvocke/dotfiles>

### Theme Systems

- Rootloops: <https://rootloops.sh/>
- Tinty: <https://github.com/tinted-theming/tinty>
- Tinted Shell: <https://github.com/tinted-theming/tinted-shell>
- Base16: <https://github.com/tinted-theming/home>

### Tools

- Taskfile: <https://taskfile.dev/>
- uv: <https://github.com/astral-sh/uv>
- nvm: <https://github.com/nvm-sh/nvm>

### Current Dotfiles

- Repository: <https://github.com/datapointchris/dotfiles>
- CLAUDE.md: In-depth project context
- README.md: Current installation guide

---

## Next Steps

1. **Review this plan** thoroughly
2. **Answer questions** in "Questions to Resolve" section
3. **Create backup** branch and tag
4. **Begin Phase 1**: Fix immediate issues (PATH, nvm, uv)
5. **Proceed incrementally** through remaining phases

---

*Document Version: 1.0*
*Last Updated: 2025-11-03*
*Status: Ready for Review*
