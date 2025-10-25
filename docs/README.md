# Dotfiles Documentation

This directory contains comprehensive documentation for understanding, setting up, and maintaining this cross-platform dotfiles repository.

## Quick Start

1. **Setup**: See [Setup Guide](./setup.md) for installation and initial configuration
2. **Neovim**: See [Neovim Guide](./neovim/) for comprehensive editor configuration
3. **Environment**: See [Environment Setup](./environment-setup.md) for platform configuration
4. **Troubleshooting**: See [Troubleshooting](./troubleshooting.md) for common issues

## Documentation Structure

### Core Configuration

- [**Neovim/**](./neovim/) - Complete Neovim configuration documentation
- [Environment Setup](./environment-setup.md) - Platform-specific environment configuration
- [Setup Guide](./setup.md) - Initial installation and configuration
- [Troubleshooting](./troubleshooting.md) - Common issues and solutions

### Specialized Topics

- [AI Integration](./ai.md) - CodeCompanion and Copilot setup
- [Corporate Environment](./corporate.md) - Solutions for restricted networks
- [LSP Configuration](./lsp.md) - Legacy LSP documentation (see neovim/ for current)
- [Dotfiles Management Analysis](./dotfiles-management-analysis.md) - Architecture decisions

### Development

- [Examples](./examples/) - MkDocs examples and reference material

## Architecture Overview

This is a **cross-platform dotfiles repository** using a layered configuration approach:

```text
├── common/              # Shared configurations (base layer)
├── macos/              # macOS-specific overrides (overlay)
├── wsl/                # WSL-specific overrides (overlay)
├── symlinks            # Universal symlink manager
└── docs/               # This documentation
```

### Key Principles

- **DRY (Don't Repeat Yourself)** - Shared configs in `common/`, platform-specific overrides only
- **Native tooling** - Prefer system tools over plugin managers (no Mason, minimal plugins)
- **Full control** - Custom solutions where possible, well-documented decisions
- **Corporate-friendly** - Works in restricted environments without external dependencies

## Configuration Highlights

### Neovim (Primary Focus)

- **Native LSP** with 20+ language servers (no nvim-lspconfig)
- **Custom colorscheme manager** with git-based project persistence
- **Unified formatter system** matching pre-commit hooks
- **AI integration** with environment-based enabling
- **Cross-platform compatibility** with smart platform detection

### Shell & Terminal

- **ZSH** with custom prompt and AWS integration
- **Enhanced CLI tools** (zoxide, fzf, fd, eza, bat, yazi)
- **tmux** configuration with smart keybindings
- **Platform-aware** configurations

### Development Tools

- **Git** with platform-specific credential helpers
- **Pre-commit hooks** for code quality
- **LSP servers** for 20+ languages
- **Debugging tools** and workflow optimizations

## Quick Navigation

| Topic | Documentation |
|-------|---------------|
| **Neovim Complete Guide** | [neovim/](./neovim/) |
| **Colorscheme Management** | [neovim/colorscheme-manager.md](./neovim/colorscheme-manager.md) |
| **Formatting System** | [neovim/formatter.md](./neovim/formatter.md) |
| **LSP Configuration** | [neovim/lsp.md](./neovim/lsp.md) |
| **Platform Setup** | [environment-setup.md](./environment-setup.md) |
| **Corporate Networks** | [corporate.md](./corporate.md) |
