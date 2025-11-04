# Installation Guide

Comprehensive platform-specific installation instructions for macOS, Ubuntu (WSL), and Arch Linux.

## Overview

The installation process uses **bootstrap scripts** that handle prerequisites, then delegates to **Taskfile** for the main installation. This two-step approach keeps bootstrap scripts simple while allowing complex installation logic in taskfiles.

**Installation Flow**:

```mermaid
graph LR
    A[Bootstrap Script] --> B[Install Package Manager]
    B --> C[Install Taskfile]
    C --> D[Run task install-*]
    D --> E[Install All Tools]
    E --> F[Configure System]
    F --> G[Setup Themes]
```

## macOS Installation

### Prerequisites

- macOS 11+ (Big Sur or later)
- Command Line Tools (installed automatically)
- ~10 GB free disk space (for Homebrew packages)
- Internet connection

### Step-by-Step

#### 1. Clone Repository

```bash
git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
cd ~/dotfiles
```

#### 2. Run Bootstrap Script

```bash
bash scripts/install/macos-setup.sh
```

**What it does**:

1. **Detects macOS platform** (exits if not macOS)
2. **Installs Homebrew** (if not present)
   - Downloads from official source
   - Adds to PATH for current session
3. **Installs Taskfile** via `brew install go-task`
4. **Runs `task install-macos`**:
   - Installs all Brewfile packages (~100 packages)
   - Installs nvm and Node.js LTS
   - Installs npm global packages (LSPs, formatters)
   - Installs uv and Python tools
   - Creates symlinks via `./symlinks link macos`
   - Installs theme system (tinty)
   - Configures shell

**Duration**: 20-30 minutes (Homebrew downloads and compiles packages)

#### 3. Post-Installation

```bash
# Restart terminal
exec zsh

# Or close and reopen terminal
```

#### 4. Verify Installation

```bash
# Check Homebrew
brew --version

# Check tools command
tools list

# Check theme system
theme-sync current

# Verify Node.js
node --version

# Verify Python
uv --version
```

### macOS-Specific Notes

!!! info "Homebrew Location"
    - Intel Mac: `/usr/local`
    - Apple Silicon: `/opt/homebrew`
    - Scripts detect automatically

!!! warning "GNU Coreutils"
    GNU coreutils are installed with `g` prefix (`gls`, `gsed`, `gtar`) and NOT added to PATH by default. This prevents conflicts with BSD tools and follows Homebrew best practices.

!!! tip "Xcode Command Line Tools"
    If prompted to install Command Line Tools during Homebrew installation, accept. This is a one-time setup.

---

## Ubuntu / WSL Installation

### Prerequisites

- Ubuntu 20.04+ or WSL 2
- `sudo` access
- ~5 GB free disk space
- Internet connection

### Step-by-Step

#### 1. Clone Repository

```bash
git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
cd ~/dotfiles
```

#### 2. Run Bootstrap Script

```bash
bash scripts/install/wsl-setup.sh
```

**What it does**:

1. **Detects WSL environment** (checks `/proc/version`)
2. **Updates apt** and installs essentials
   - git, curl, wget, build-essential, ca-certificates
3. **Installs Taskfile** via install script to `~/.local/bin`
4. **Runs `task install-wsl`**:
   - Installs apt packages (bat, fd, ripgrep, fzf, etc.)
   - Creates binary symlinks (batcat → bat, fdfind → fd)
   - Installs Rust/Cargo (for eza, yazi, git-delta)
   - Installs nvm and Node.js LTS
   - Installs npm global packages
   - Installs uv and Python tools
   - Creates symlinks via `./symlinks link wsl`
   - Installs theme system (tinty via cargo)
   - Configures WSL-specific settings

**Duration**: 15-20 minutes

#### 3. Configure Zsh Environment

**Set ZSHDOTDIR** (if not already set):

```bash
# Check if already set
cat /etc/zsh/zshenv

# If empty or doesn't have ZSHDOTDIR, add it:
echo 'export ZSHDOTDIR="$HOME/.config/zsh"' | sudo tee -a /etc/zsh/zshenv
```

#### 4. Restart WSL (if wsl.conf was modified)

```powershell
# From Windows PowerShell
wsl.exe --shutdown
```

Then relaunch WSL.

#### 5. Verify Installation

```bash
# Check Taskfile
task --version

# Check tools
tools list

# Verify symlinks
which bat      # Should be ~/.local/bin/bat
which fd       # Should be ~/.local/bin/fd

# Verify Rust tools
which eza
which yazi

# Check themes
theme-sync current
```

### Ubuntu-Specific Notes

!!! warning "Binary Name Differences"
    Ubuntu installs some packages with different binary names:

    - `bat` package → `batcat` binary (symlink created to `bat`)
    - `fd-find` package → `fdfind` binary (symlink created to `fd`)

    The installation handles this automatically.

!!! info "Cargo-Installed Tools"
    These tools need Rust/Cargo on Ubuntu (not available via apt):

    - **eza** (modern ls)
    - **yazi** (file manager)
    - **git-delta** (git diff viewer)

!!! tip "WSL Configuration"
    The installation creates `/etc/wsl.conf` with:

    ```ini
    [boot]
    systemd=true

    [interop]
    appendWindowsPath=false

    [user]
    default=chris
    ```

    Restart WSL after this is created.

---

## Arch Linux Installation

### Prerequisites

- Arch Linux (base installation complete)
- `sudo` access
- ~3 GB free disk space
- Internet connection

### Step-by-Step

#### 1. Clone Repository

```bash
git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
cd ~/dotfiles
```

#### 2. Run Bootstrap Script

```bash
bash scripts/install/arch-setup.sh
```

**What it does**:

1. **Detects Arch Linux** (checks `/etc/arch-release`)
2. **Updates pacman** database
3. **Installs essential packages**
   - git, curl, wget, base-devel
4. **Installs Taskfile** via `pacman -S go-task`
5. **Runs `task install-arch`**:
   - Installs pacman packages (bat, eza, fd, ripgrep, etc.)
   - Installs yay AUR helper
   - Installs nvm and Node.js LTS
   - Installs npm global packages
   - Installs uv and Python tools
   - Creates symlinks via `./symlinks link arch`
   - Installs theme system (tinty)
   - Configures pacman (color, parallel downloads)

**Duration**: 15-20 minutes

#### 3. Post-Installation

```bash
# Restart terminal
exec zsh

# Or close and reopen terminal
```

#### 4. Verify Installation

```bash
# Check pacman configuration
cat /etc/pacman.conf | grep -E "Color|ParallelDownloads"

# Check yay (AUR helper)
yay --version

# Check tools
tools list

# Check themes
theme-sync current

# Verify Node.js
node --version

# Verify Python
uv --version
```

### Arch-Specific Notes

!!! info "AUR Helper (yay)"
    The installation installs `yay` for accessing the Arch User Repository (AUR). This provides access to thousands of additional packages.

    ```bash
    # Search AUR
    yay -Ss <package>

    # Install from AUR
    yay -S <package>
    ```

!!! tip "pacman Configuration"
    The installation enables:

    - **Color output** for better readability
    - **Parallel downloads** for faster updates

    You can adjust these in `/etc/pacman.conf`.

!!! warning "Rolling Release"
    Arch is a rolling release distro. Updates can be frequent. Test major updates in a VM first using the [Testing Guide](../development/testing.md).

---

## Manual Installation (Advanced)

If you prefer manual installation or need to customize:

### 1. Install Prerequisites

=== "macOS"
    ```bash
    # Install Homebrew
    /bin/bash -c "$(curl -fsSL <https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh>)"

    # Install Taskfile
    brew install go-task
    ```

=== "Ubuntu"
    ```bash
    # Update and install essentials
    sudo apt update
    sudo apt install -y git curl wget build-essential

    # Install Taskfile
    sh -c "$(curl --location https://taskfile.dev/install.sh)" -- -d -b ~/.local/bin
    ```

=== "Arch"
    ```bash
    # Update and install essentials
    sudo pacman -Sy
    sudo pacman -S --needed git curl wget base-devel go-task
    ```

### 2. Clone Repository

```bash
git clone https://github.com/datapointchris/dotfiles.git ~/dotfiles
cd ~/dotfiles
```

### 3. Run Platform-Specific Task

```bash
# macOS
task install-macos

# Ubuntu / WSL
task install-wsl

# Arch Linux
task install-arch
```

### 4. Or Run Individual Tasks

```bash
# See all available tasks
task --list

# Install specific components
task brew:install-all    # macOS only
task nvm:install        # All platforms
task npm:install-all    # All platforms
task uv:install-all     # All platforms
task symlinks:link      # All platforms
task themes:install     # All platforms
```

---

## Troubleshooting Installation

### General Issues

**Installation hangs or times out**:

- Check internet connection
- Restart installation
- For Homebrew, sometimes restarting terminal helps

**Permission denied errors**:

```bash
# Ensure directories exist and are writable
mkdir -p ~/.local/bin
chmod 755 ~/.local/bin
```

**Command not found after installation**:

```bash
# Reload shell configuration
source ~/.zshrc

# Or restart terminal
exec zsh
```

### Platform-Specific Issues

=== "macOS"
    **Homebrew installs to wrong location**:

    Check your Mac architecture and Homebrew location:
    ```bash
    uname -m                    # x86_64 (Intel) or arm64 (Apple Silicon)
    brew --prefix               # Should match architecture
    ```

    **Xcode license not accepted**:
    ```bash
    sudo xcodebuild -license accept
    ```

=== "Ubuntu / WSL"
    **apt update fails**:
    ```bash
    # Fix broken packages
    sudo apt --fix-broken install
    sudo apt update
    ```

    **Cargo install fails**:
    ```bash
    # Reinstall Rust
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
    ```

=== "Arch"
    **pacman database lock**:
    ```bash
    # Remove lock file (only if pacman is not running)
    sudo rm /var/lib/pacman/db.lck
    ```

    **yay build fails**:
    ```bash
    # Ensure base-devel is installed
    sudo pacman -S --needed base-devel
    ```

**More help**: [Troubleshooting Guide](../reference/troubleshooting.md)

---

## Next Steps

Installation complete! Now:

1. [First Configuration](first-config.md) - Set up Git identity, choose theme
2. [Tool Discovery](../configuration/tools.md) - Explore the 31 installed tools
3. [Architecture Overview](../architecture/index.md) - Understand how it all works

**Questions?** → [Troubleshooting Guide](../reference/troubleshooting.md)
