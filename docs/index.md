# Welcome to Dotfiles

A cross-platform, modular dotfiles repository designed for developer productivity, aesthetic consistency, and long-term maintainability. Supports macOS, Ubuntu (WSL), and Arch Linux with 31 carefully curated CLI tools, synchronized themes, and intelligent automation.

## What You'll Find Here

This documentation enables you to:

- **Install** dotfiles on a fresh system in 15 minutes
- **Understand** the architecture and design decisions
- **Customize** themes, tools, and workflows to your preferences
- **Contribute** improvements and test changes safely
- **Return** after a year away and be productive in a day

## Quick Start Paths

=== "New User"
    **Goal**: Get dotfiles installed and working

    1. [Quick Start Guide](getting-started/quickstart.md) - One-command installation
    2. [First Configuration](getting-started/first-config.md) - Initial setup steps
    3. [Tool Discovery](configuration/tools.md) - Explore what's installed

=== "Returning User"
    **Goal**: Refresh on how everything works

    1. [Architecture Overview](architecture/index.md) - How it all fits together
    2. [Theme System](architecture/themes.md) - Switching themes
    3. [Platform Differences](reference/platforms.md) - Platform-specific quirks

=== "Customizer"
    **Goal**: Tailor dotfiles to your preferences

    1. [Themes & Colors](configuration/themes.md) - Available themes and customization
    2. [Tools & CLI](configuration/tools.md) - Adding or removing tools
    3. [Shell Configuration](configuration/shell.md) - Zsh, aliases, functions

=== "Developer"
    **Goal**: Contribute or test changes

    1. [Testing Guide](development/testing.md) - VM-based testing framework
    2. [Project Phases](development/phases.md) - Development history
    3. [Master Plan](development/master-plan.md) - Project vision and roadmap

## Architecture at a Glance

```text
dotfiles/
├── common/              # Shared configurations (all platforms)
├── macos/              # macOS-specific overrides
├── wsl/                # WSL Ubuntu overrides
├── arch/               # Arch Linux overrides (future)
├── taskfiles/          # Taskfile automation (130+ tasks)
└── symlinks            # Intelligent symlink manager
```

**Key Principles**:

- **Cross-platform consistency** via version managers (uv, nvm)
- **DRY architecture** - shared base, minimal platform overrides
- **Discovery over tracking** - tool awareness without complexity
- **Testing-first** - VM framework for safe iteration

## Feature Highlights

!!! success "31 Curated CLI Tools"
    Modern replacements for classic Unix tools: bat, eza, fd, ripgrep, fzf, zoxide, yazi, lazygit, and more.

!!! info "Synchronized Themes"
    Base16 themes synchronized across tmux, bat, fzf, and shell via tinty. Parallel system for Ghostty's 600+ themes.

!!! tip "Intelligent Automation"
    130+ Taskfile tasks for installation, updates, theme management, and testing across all platforms.

!!! example "Tool Discovery System"
    `tools` command with 8 subcommands: search tools by tags, explore categories, discover random tools, see usage examples.

## Common Tasks

| Task | Command | Reference |
|------|---------|-----------|
| Install dotfiles | `bash scripts/install/macos-setup.sh` | [Installation Guide](getting-started/installation.md) |
| List all tasks | `task --list` | [Taskfile Reference](reference/taskfile.md) |
| Switch theme | `theme-sync apply base16-rose-pine` | [Theme Configuration](configuration/themes.md) |
| Explore tools | `tools random` | [Tool Discovery](configuration/tools.md) |
| Test on Ubuntu | `multipass launch --name dotfiles-test` | [Testing Guide](development/testing.md) |
| Update all packages | `task update` | [Taskfile Reference](reference/taskfile.md) |

## Project Status

**Phases 1-6 Complete** (as of 2025-11-04):

1. ✅ Package Management - uv for Python, nvm for Node.js
2. ✅ Tool Registry - 31 tools documented with examples
3. ✅ Installation Automation - Taskfile with 130+ tasks
4. ✅ Theme Synchronization - tinty + theme-sync command
5. ✅ Tool Discovery - `tools` command for exploration
6. ✅ Cross-Platform Expansion - VM testing framework

**Coming in Phase 7**: CI/CD integration with automated testing on GitHub Actions

## Need Help?

- **Installation Issues**: [Troubleshooting Guide](reference/troubleshooting.md)
- **Platform Differences**: [Platform Reference](reference/platforms.md)
- **Tool Questions**: [Tool Registry](reference/tools.md)
- **Customization**: [Configuration Section](configuration/themes.md)

---

**Ready to start?** → [Quick Start Guide](getting-started/quickstart.md)
