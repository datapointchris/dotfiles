# Dotfiles

Cross-platform dotfiles that work across macOS, WSL Ubuntu, and Arch Linux. Because maintaining three separate configs is nobody's idea of a good time.

## What This Is

A dotfiles setup that prioritizes shared configuration with platform-specific overrides only when absolutely necessary. Includes a bunch of modern CLI tools, a theme system that actually works, and some custom tools to keep everything organized.

Quick stats: ~100 CLI tools, shared zsh/tmux/neovim configs, automated theme switching, and a discovery system so you can actually remember what you installed.

## Quick Start

Clone and run the setup script for your platform:

```bash
git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
cd ~/dotfiles

# Pick your poison
bash install/macos-setup.sh    # macOS
bash install/wsl-setup.sh      # WSL Ubuntu
bash install/arch-setup.sh     # Arch Linux
```

Already have Homebrew and Task installed? Just run `task install`.

See the [quickstart guide](https://datapointchris.github.io/dotfiles/getting-started/quickstart/) for details.

## Structure

```text
dotfiles/
├── platforms/        # System configurations (deployed to $HOME)
│   ├── common/       # Shared configs (zsh, nvim, tmux, git)
│   ├── macos/        # macOS-specific overrides
│   ├── wsl/          # WSL Ubuntu-specific overrides
│   └── arch/         # Arch Linux-specific overrides
├── apps/             # Personal CLI applications
│   ├── common/       # Cross-platform tools (menu, notes, toolbox, theme-sync)
│   ├── macos/        # macOS-specific tools
│   └── sess/         # Session manager (Go)
├── management/       # Repository management
│   ├── symlinks/     # Symlinks manager (Python)
│   ├── taskfiles/    # Task automation (modular)
│   ├── packages.yml  # Package definitions
│   └── *.sh          # Platform bootstrap scripts
└── docs/             # Documentation (because future you will forget)
```

The core philosophy: write configs once in `platforms/common/`, override only what's platform-specific.

## Package Management

This setup uses different package managers for different purposes, because that's apparently the world we live in:

| What | How | Examples |
|------|-----|----------|
| System utilities | brew / apt / pacman | bat, eza, fd, ripgrep, tmux, neovim |
| Python | uv | version management, ruff, mypy, etc. |
| Node.js | nvm | version management, LSPs, formatters |

Why the split? Cross-platform consistency, project-specific versions, and keeping system packages separate from development tools.

See [CLAUDE.md](CLAUDE.md) for the full philosophy (it's longer than it needs to be, but comprehensive).

## Tool Discovery

Installed something six months ago and forgot about it? The `toolbox` command has you covered:

```bash
toolbox list              # See everything
toolbox show ripgrep      # Details, examples, why you installed it
toolbox search git        # Find git-related tools
toolbox random            # Discover something you forgot existed
```

Currently 31 tools documented in the registry with usage examples and tips. More getting added as I remember they exist.

## Common Tasks

```bash
# Themes
theme-sync favorites                    # See your favorite themes
theme-sync apply base16-gruvbox-dark   # Switch themes

# Package updates
task update                             # Update everything

# Symlinks
task symlinks:link                      # Deploy configs (also: relink, check, unlink)

# Discovery
toolbox search python                   # Find Python tools
```

Run `task --list` to see all available tasks.

## Symlink Management

The `symlinks` tool manages deploying configs from the repo to their actual locations. Written in Python because shell scripts for path manipulation are a recipe for sadness.

**Important**: After adding or removing files in the repo, run `task symlinks:link` to update symlinks. Otherwise Neovim will complain about missing modules and you'll spend 20 minutes debugging before remembering this note.

## Theme System

Uses tinty for Base16 theme management across tmux, bat, fzf, and the shell. The `theme-sync` command wraps tinty with some conveniences:

- `theme-sync favorites` - Quick access to 12 hand-picked themes
- `theme-sync apply <theme>` - Actually apply the theme
- `theme-sync current` - See what you're currently using
- `theme-sync random` - Feeling adventurous

Theme persists across sessions. Neovim has its own theme manager (because integration is hard).

## Documentation

Full docs are available at [datapointchris.github.io/dotfiles](https://datapointchris.github.io/dotfiles):

- [Quickstart](https://datapointchris.github.io/dotfiles/getting-started/quickstart/) - Get running in 15 minutes
- [Installation](https://datapointchris.github.io/dotfiles/getting-started/installation/) - Detailed install guide
- [Architecture](https://datapointchris.github.io/dotfiles/architecture/) - How everything fits together
- [Tool Reference](https://datapointchris.github.io/dotfiles/reference/tools/) - All the tools
- [Troubleshooting](https://datapointchris.github.io/dotfiles/reference/troubleshooting/) - When things break

There's also a [learnings](https://datapointchris.github.io/dotfiles/learnings/) section with extracted wisdom from bugs I've fixed and things I've figured out.

## Some Highlights

**Neovim**: Native LSP with 10+ language servers, CodeCompanion for Claude integration, custom colorscheme manager with 17 themes.

**Shell**: Custom ZSH prompt with git status, zoxide for smart directory jumping, fzf with preview, syntax highlighting, vi-mode.

**Modern CLI replacements**: bat (cat with syntax highlighting), eza (ls with git integration), fd (find that respects .gitignore), ripgrep (grep but faster), yazi (terminal file manager).

**Task automation**: Modular Taskfile system with separate files for brew, npm, uv, symlinks, etc. Makes it easy to add new automation without creating a monolithic mess.

## Contributing

This is a personal dotfiles repo, but you're welcome to:

- Steal ideas for your own setup
- Open issues if you spot something broken
- Suggest tools or improvements

## License

MIT - do whatever you want with it

---

**Tip**: Running `tools random` occasionally is a good way to rediscover tools you installed and immediately forgot about.
