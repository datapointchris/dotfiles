# Dotfiles

Modern, cross-platform dotfiles emphasizing **developer ergonomics, productivity, and joy**.

## ✨ Features

- **100+ curated development tools** with discovery system
- **Cross-platform** (macOS Intel, Ubuntu WSL, Arch Linux)
- **Clean package management** (brew/apt/pacman for system, uv/nvm for languages)
- **Modern CLI replacements** (bat, eza, fd, ripgrep, fzf, zoxide)
- **Native Neovim LSP** with 10+ language servers
- **Shared config architecture** with platform-specific overrides

## 🚀 Quick Start

**Clone and symlink**:

```bash
git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
cd ~/dotfiles
./symlinks.sh link macos     # or: wsl, arch
```

**Discover installed tools**:

```bash
tools list          # See all 100+ tools
tools show bat      # Learn about specific tools
tools search git    # Find tools by keyword
tools random        # Discover something new!
```

**For full installation and setup**, see:

- 📖 **[Master Plan](docs/MASTER_PLAN.md)** - Complete modernization roadmap & installation
- 📋 **[Tool List](docs/TOOL_LIST.md)** - All 100+ tools categorized
- 🎨 **[Theme Strategy](docs/THEME_SYNC_STRATEGY.md)** - Color scheme synchronization
- ⚙️ **[CLAUDE.md](CLAUDE.md)** - AI assistant context & package philosophy

## 📂 Architecture

```text
dotfiles/
├── common/         # Shared configs (zsh, nvim, tmux, etc.)
├── macos/          # macOS-specific configs and overrides
├── wsl/            # WSL Ubuntu-specific configs
├── docs/           # Comprehensive documentation
├── scripts/        # Utility scripts and automation
└── symlinks.sh     # Symlink management tool
```

**Key principle**: DRY configuration with platform-specific customization when needed.

## 📦 Package Management

This setup uses a **clear separation** between system and language tools:

| Type | Manager | Purpose |
|------|---------|---------|
| **System Tools** | brew/apt/pacman | bat, eza, fd, ripgrep, tmux, neovim, docker, etc. |
| **Python** | uv | Version management, tools (ruff, mypy, etc.) |
| **Node.js** | nvm | Version management, npm globals (LSPs, formatters) |

**Why this split?** Cross-platform consistency, project-specific versions, clean separation of concerns.

See [CLAUDE.md](CLAUDE.md) for detailed philosophy.

## 🔧 Tool Discovery

The `tools` command helps you discover and learn about installed tools:

```bash
tools list              # List all documented tools
tools show ripgrep      # Detailed info: usage, examples, why use it
tools search python     # Find Python-related tools
tools random            # Discover a random tool (learn something new!)
tools categories        # Show all categories
```

**30+ tools documented** in the registry with usage examples, tips, and cross-references.

## 🔗 Symlink Management

The `symlinks.sh` script manages all configuration symlinks:

```bash
./symlinks.sh link macos        # Create symlinks for macOS
./symlinks.sh relink macos      # Update symlinks after file changes
./symlinks.sh unlink macos      # Remove all symlinks
```

**Critical**: After adding/removing files in dotfiles, run `./symlinks.sh relink <platform>`

## 🎨 Theme System

**Current**: Individual theme configs per application

**Future** (Phase 4): Unified theme synchronization across:

- Terminal (Ghostty)
- Neovim (17 curated colorschemes including flexoki-moon variants)
- Tmux, Bat, FZF, Eza, Lazygit

See [Theme Strategy](docs/THEME_SYNC_STRATEGY.md) for tinty vs custom Rust implementation plan.

## 🛠️ Installation

### Prerequisites

- **macOS**: Homebrew, uv, nvm
- **WSL/Ubuntu**: apt, uv, nvm, cargo
- **Arch**: pacman, uv, nvm, cargo

### macOS Quick Setup

```bash
# Install Homebrew (if not present)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install core tools
brew install bat eza fd ripgrep fzf zoxide neovim tmux git gh

# Install language managers
brew install --cask uv
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash

# Clone and link
git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
cd ~/dotfiles
./symlinks.sh link macos

# Restart terminal
```

**For complete installation**, see [Master Plan - Installation Strategy](docs/MASTER_PLAN.md#installation-strategy)

### WSL/Ubuntu Setup

See [Master Plan - WSL Installation](docs/MASTER_PLAN.md#installing-in-wsl-ubuntu)

### Arch Setup

See [Master Plan - Arch Installation](docs/MASTER_PLAN.md#arch-linux-installation)

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| [MASTER_PLAN.md](docs/MASTER_PLAN.md) | Complete modernization roadmap (7 phases) |
| [TOOL_LIST.md](docs/TOOL_LIST.md) | All 100+ tools categorized by type |
| [THEME_SYNC_STRATEGY.md](docs/THEME_SYNC_STRATEGY.md) | Theme synchronization approach |
| [CLAUDE.md](CLAUDE.md) | AI assistant context & philosophies |
| [PHASE_1_COMPLETE.md](docs/PHASE_1_COMPLETE.md) | Phase 1 completion summary |
| [tools/registry.yml](docs/tools/registry.yml) | Detailed tool database (YAML) |

## 🎯 Current Status

**Phase 1: Foundation** ✅ Complete

- ✅ Package management (uv/nvm working)
- ✅ PATH fixed (Homebrew before system)
- ✅ Shell completions (uv, task, nvm)
- ✅ npm globals migrated (11 packages)
- ✅ Taskfile installed
- ✅ Documentation created

**Phase 2: Documentation** ✅ Complete

- ✅ Tool registry (30+ tools documented)
- ✅ Tool discovery command (`tools`)
- ✅ Categorized tool list (100+ tools)
- ✅ README simplified

**Next**: Phase 3 - Installation Automation (Taskfile-based install)

## 💡 Key Highlights

### Neovim Setup

- Native LSP configuration (Neovim 0.11+)
- 10+ language servers (TypeScript, Python, Bash, YAML, etc.)
- CodeCompanion integration with Claude 3.5 Sonnet
- Custom colorscheme manager (17 themes with per-project persistence)

### Shell Configuration

- Custom ZSH prompt with git status and AWS context
- zoxide for smart directory jumping
- fzf with file/directory preview
- Syntax highlighting and vi-mode

### Modern CLI Tools

- **bat**: cat with syntax highlighting
- **eza**: ls with git integration and icons
- **fd**: find that respects .gitignore
- **ripgrep**: fastest grep alternative
- **yazi**: terminal file manager with preview

## 🤝 Contributing

This is a personal dotfiles repository, but feel free to:

- Take inspiration for your own dotfiles
- Suggest improvements via issues
- Share interesting tools or configurations

## 📝 License

MIT License - see repository for details

---

**Tip**: Run `tools random` daily to discover tools you might have forgotten about!
