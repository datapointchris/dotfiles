# Dotfiles AI Agent Instructions

## Architecture Overview

This is a **cross-platform dotfiles repository** using a shared configuration architecture with platform-specific customizations. The core design principle is DRY (Don't Repeat Yourself) through intelligent symlink management.

### Directory Structure

```text
├── shared/              # Common configurations for all platforms
├── macos/              # macOS-specific configurations and overrides
├── wsl/                # WSL/Ubuntu-specific configurations
├── symlinks            # Universal symlink manager (replaces GNU Stow)
└── docs/               # MkDocs documentation
```

**Key Pattern**: Shared configurations are symlinked FROM `shared/` TO platform directories, then platform directories are symlinked TO `$HOME`.

## Critical Symlink Workflow

The `./symlinks` script is the **central management tool** - never use GNU Stow or manual linking:

```bash
# Step 1: Link shared configs to platform directories
./symlinks shared

# Step 2: Link platform configs to $HOME
./symlinks macos        # or wsl, ubuntu, arch
```

**Important**: Always use `./symlinks shared show` and `./symlinks <platform> show` to verify symlink state before making changes.

## Platform Differentiation Patterns

### macOS-specific (`macos/`)

- Uses VS Code as git editor (`core.editor = code --wait`)
- OSX Keychain credential helper
- iTerm2 configurations and color schemes
- Homebrew-based dependency paths

### WSL-specific (`wsl/`)

- Uses Neovim as git editor (`core.editor = nvim`)
- Windows credential manager integration
- Git includeIf for `~/code/` directory
- WSL-specific clipboard integration with `win32yank.exe`

### Shared configurations (`shared/.config/`)

- ZSH with custom prompt featuring Nerd Font icons
- Enhanced CLI tools (zoxide, fzf, fd, eza, bat, yazi)
- tmux, neofetch, zellij configurations
- AWS-aware prompt with credential expiration display

## ZSH Configuration Architecture

The ZSH setup in `shared/.config/zsh/` features:

- **Custom prompt** (`prompt.zsh`) with git status, AWS context, virtual environments
- **Platform detection** that auto-configures paths and plugin locations
- **Plugin system** that gracefully handles package manager vs manual installations
- **History optimization** with intelligent search and deduplication

Key aliases follow smart navigation patterns:

- `z` (zoxide), `..` (up directory), `dots` (dotfiles), `dl` (downloads)
- Enhanced commands: `ls`→`eza`, `cat`→`bat`, `find`→`fd`

## Development Workflow

### Quality Assurance

- **Pre-commit hooks**: Configured in `.pre-commit-config.yaml`
  - ShellCheck for bash scripts
  - MarkdownLint for documentation
  - StyLua for Lua configurations
  - JSON5/YAML/TOML validation

### Documentation

- **MkDocs** setup (`mkdocs.yml`) with Material theme
- Documentation in `docs/` with examples and diagrams
- README.md contains comprehensive installation guides per platform

### Testing

- `TESTING.ipynb` - Jupyter notebook for interactive development/debugging
- `TESTING.sh` - Bash testing utilities (currently contains experimental code)

## Platform-Specific Installation Patterns

Each platform has different dependency management:

**macOS**: Homebrew + manual Nerd Font installation
**WSL/Ubuntu**: Mix of apt, cargo, manual builds (fzf, yazi, lazygit)
**Package linking**: Ubuntu requires symlinks for `fd`→`fdfind`, `bat`→`batcat`

## Critical Files to Understand

- `symlinks` - Core symlink management logic with safety checks
- `shared/.config/zsh/.zshrc` - Primary shell configuration
- `shared/.config/zsh/prompt.zsh` - Custom prompt with AWS integration
- Platform-specific `.gitconfig` files showing credential/editor differences
- `.pre-commit-config.yaml` - Quality gates for all changes

## AWS Integration

The custom prompt includes intelligent AWS context display:

- Reads `$AWS_PROFILE`, `$AWS_REGION`, expiration times
- Supports aws-vault and AWSume credential managers
- Shows `☁️ profile@region [2h15m]` format with expiration warnings

## Common Patterns When Contributing

1. **Always test symlink operations** with `show` before `link`/`unlink`
2. **Platform differences go in platform directories**, shared configs in `shared/`
3. **Use relative paths in symlinks** - the script handles this automatically
4. **Run pre-commit** hooks before submitting changes
5. **Update documentation** in both README.md and `docs/` for major changes

## Key Dependencies to Understand

**Required**: zsh, git, Nerd Font, zoxide, fzf, fd, eza, bat, ripgrep, delta
**Platform-specific**: Different package managers and installation methods
**Optional but featured**: yazi, tmux, neovim, gh CLI
