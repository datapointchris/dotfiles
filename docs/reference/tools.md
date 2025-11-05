# Tool Reference

Quick reference for installed tools. For detailed info, use `tools show <name>`.

## Package Management

**System Tools**: brew (macOS), apt (Ubuntu), pacman (Arch)

**Python**: uv

**Node.js**: nvm

## Dotfiles Management

**symlinks**: Cross-platform dotfiles symlink manager

```sh
symlinks link common        # Link common base layer
symlinks link macos         # Link platform overlay
symlinks relink macos       # Complete refresh (unlink + link)
symlinks check              # Check for broken symlinks
```

Supports layered architecture (common base + platform overlay) with intelligent conflict detection. See `tools/symlinks/README.md` for full documentation.

## Core Tools by Category

**File Management**: bat, eza, fd, tree, yazi, duf

**Search**: ripgrep, fzf, grep, jq

**Navigation**: zoxide

**Version Control**: git, gh, lazygit, git-delta

**Editors**: neovim

**Terminal**: tmux, ghostty (macOS), wezterm

**Language Servers**: typescript-language-server, basedpyright, lua-language-server, bash-language-server, yaml-language-server, and more

**Linters/Formatters**: ruff, mypy, eslint, prettier, markdownlint

**Build Tools**: task (go-task), make, cmake

**Container/Cloud**: docker, kubectl, awscli, terraform

**System**: htop, btop, ncdu, tldr

## Usage

```sh
tools list              # List all tools
tools show <name>       # Detailed info
tools search <query>    # Search by keyword
tools categories        # List categories
```

## Installation

System tools installed via Brewfile (macOS) or taskfiles (Ubuntu/Arch).

Python tools: `uv tool install <name>`

Node tools: `npm install -g <name>`

See [Installation Guide](../getting-started/installation.md) for details.
