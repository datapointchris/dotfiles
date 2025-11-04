# Quick Start

Get dotfiles installed and running in 15 minutes.

## Prerequisites

Choose your platform:

=== "macOS"
    - macOS (Intel or Apple Silicon)
    - Command Line Tools (installed automatically with Homebrew)
    - Internet connection

=== "Ubuntu / WSL"
    - Ubuntu 20.04+ or WSL 2
    - `sudo` access
    - Internet connection

=== "Arch Linux"
    - Arch Linux (base installation complete)
    - `sudo` access
    - Internet connection

## One-Command Installation

### macOS

```bash
git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
cd ~/dotfiles
bash scripts/install/macos-setup.sh
```

**What it does**:

1. Installs Homebrew (if not present)
2. Installs Taskfile (go-task)
3. Runs full macOS installation (brew → nvm → npm → uv → themes)

**Time**: ~20-30 minutes (Homebrew installs many packages)

### Ubuntu / WSL

```bash
git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
cd ~/dotfiles
bash scripts/install/wsl-setup.sh
```

**What it does**:

1. Updates apt and installs essentials
2. Installs Rust/Cargo (for some tools)
3. Installs Taskfile
4. Runs full WSL installation

**Time**: ~15-20 minutes

!!! warning "WSL Configuration"
    If you haven't set `ZSHDOTDIR`, add this to `/etc/zsh/zshenv`:
    ```bash
    echo 'export ZSHDOTDIR="$HOME/.config/zsh"' | sudo tee -a /etc/zsh/zshenv
    ```

### Arch Linux

```bash
git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
cd ~/dotfiles
bash scripts/install/arch-setup.sh
```

**What it does**:

1. Updates pacman database
2. Installs essential packages
3. Installs yay AUR helper
4. Runs full Arch installation

**Time**: ~15-20 minutes

## Verify Installation

After installation completes, verify everything works:

```bash
# List all available tasks
task --list

# List all 31 installed tools
tools list

# Check current theme
theme-sync current

# Verify shell config loaded
echo $PATH | tr ':' '\n'  # Should show ~/.local/bin early
```

**Expected output**:

```text
✅ task command available
✅ tools command shows 31 tools
✅ theme-sync shows current theme (base16-rose-pine)
✅ PATH includes ~/.local/bin
```

## First Steps

### 1. Restart Your Terminal

```bash
# macOS / Arch
exec zsh

# Or close and reopen terminal
```

### 2. Explore Installed Tools

```bash
# Show all 31 tools
tools list

# Get detailed info about a tool
tools show bat

# Search for git-related tools
tools search git

# Discover a random tool
tools random
```

### 3. Try a Theme

```bash
# List favorite themes
theme-sync favorites

# Switch to a different theme
theme-sync apply base16-gruvbox-dark-hard

# Return to default
theme-sync apply base16-rose-pine
```

### 4. Run Some Tasks

```bash
# Show all available tasks
task --list

# Update all packages
task update

# Verify installation
task verify
```

## What Got Installed?

### Package Managers

- **Homebrew** (macOS): System packages, GUI apps
- **apt** (Ubuntu): System packages
- **pacman** (Arch): System packages
- **yay** (Arch): AUR helper

### Version Managers

- **nvm**: Node.js version management
- **uv**: Python version management and tools
- **cargo**: Rust package manager (Ubuntu)

### Core Tools (31 Total)

**File Management**: bat, eza, fd, yazi, tree

**Search**: ripgrep, fzf, zoxide

**Version Control**: git, gh, lazygit, git-delta

**Editors**: neovim

**Terminal**: tmux, ghostty (macOS)

**And more**: See [Tool Registry](../reference/tools.md)

### Theme System

- **tinty**: Base16 theme manager
- **theme-sync**: Command-line theme switching
- **12 favorite themes** pre-configured

### Automation

- **Taskfile**: 130+ tasks for common operations
- **symlinks**: Intelligent symlink manager

## Troubleshooting

### Command Not Found

**Symptom**: `bash: tools: command not found`

**Fix**: Reload shell or check PATH

```bash
source ~/.zshrc
echo $PATH | grep ".local/bin"
```

### Homebrew Installation Hangs

**Symptom**: Homebrew install takes > 30 minutes

**Fix**: Check internet connection, restart installation

```bash
# Kill hung process
pkill -f brew

# Restart
bash scripts/install/macos-setup.sh
```

### Permission Denied

**Symptom**: Cannot write to directory

**Fix**: Ensure ~/.local/bin exists and is writable

```bash
mkdir -p ~/.local/bin
chmod 755 ~/.local/bin
```

**More help**: [Troubleshooting Guide](../reference/troubleshooting.md)

## Next Steps

Now that installation is complete:

1. **Configure Git Identity**: [First Configuration](first-config.md)
2. **Understand the Architecture**: [Architecture Overview](../architecture/index.md)
3. **Customize Your Setup**: [Configuration Guide](../configuration/themes.md)
4. **Learn the Tools**: [Tool Discovery](../configuration/tools.md)

---

**Having issues?** → [Troubleshooting Guide](../reference/troubleshooting.md)

**Want to understand how it works?** → [Architecture Overview](../architecture/index.md)
