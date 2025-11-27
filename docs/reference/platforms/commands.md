# Command Reference

Package manager commands and environment configuration across platforms.

## Package Manager Commands

### Installation Commands

| Action                   | macOS (brew)           | Ubuntu (apt)             | Arch (pacman)          |
| ------------------------ | ---------------------- | ------------------------ | ---------------------- |
| **Update package lists** | `brew update`          | `sudo apt update`        | `sudo pacman -Sy`      |
| **Install package**      | `brew install <pkg>`   | `sudo apt install <pkg>` | `sudo pacman -S <pkg>` |
| **Remove package**       | `brew uninstall <pkg>` | `sudo apt remove <pkg>`  | `sudo pacman -R <pkg>` |
| **Upgrade all**          | `brew upgrade`         | `sudo apt upgrade`       | `sudo pacman -Syu`     |
| **Search packages**      | `brew search <query>`  | `apt search <query>`     | `pacman -Ss <query>`   |
| **Show package info**    | `brew info <pkg>`      | `apt show <pkg>`         | `pacman -Si <pkg>`     |
| **List installed**       | `brew list`            | `apt list --installed`   | `pacman -Q`            |
| **Clean cache**          | `brew cleanup`         | `sudo apt autoclean`     | `sudo pacman -Sc`      |

### Package Manager Features

| Feature                    | macOS (brew) | Ubuntu (apt)  | Arch (pacman)     |
| -------------------------- | ------------ | ------------- | ----------------- |
| **GUI Applications**       | ✅ Casks     | ❌            | ❌                |
| **Taps (3rd party repos)** | ✅           | ✅ (PPAs)     | ✅ (AUR)          |
| **Binary packages**        | ✅           | ✅            | ✅                |
| **Source builds**          | ✅ (rare)    | ❌            | ✅ (AUR)          |
| **Automatic updates**      | ❌           | ✅ (optional) | ❌                |
| **Parallel downloads**     | ✅           | ❌            | ✅ (configurable) |

## PATH Configuration

### Default PATH Order

=== "macOS"

    ```bash
    /usr/local/bin      # Homebrew (Intel Mac)
    /usr/local/sbin
    /usr/bin            # System binaries
    /bin
    /usr/sbin
    /sbin
    ```

=== "Ubuntu/WSL"

    ```bash
    /usr/local/bin
    /usr/bin            # System binaries
    /bin
    ~/.local/bin        # User binaries (important for our symlinks)
    ```

=== "Arch Linux"

    ```bash
    /usr/local/bin
    /usr/bin            # System binaries
    /bin
    ~/.local/bin        # User binaries
    ```

### Version Manager Paths

These paths are added by version managers (nvm, uv) and take precedence:

```bash
# nvm (Node.js)
~/.config/nvm/versions/node/<version>/bin

# uv (Python)
~/.local/bin        # uv tools installed here

# Rust/Cargo
~/.cargo/bin
```

## Shell Configuration

### Shell Config File Locations

| Platform   | Shell | Main Config            |
| ---------- | ----- | ---------------------- |
| **macOS**  | zsh   | `~/.config/zsh/.zshrc` |
| **Ubuntu** | zsh   | `~/.config/zsh/.zshrc` |
| **Arch**   | zsh   | `~/.config/zsh/.zshrc` |

### ZSHDOTDIR Configuration

All platforms use `~/.config/zsh/.zshrc` via ZSHDOTDIR.

=== "macOS"

    Set in terminal emulator or user environment.

=== "Ubuntu/WSL & Arch"

    Set in `/etc/zsh/zshenv`:

    ```bash
    # /etc/zsh/zshenv
    export ZSHDOTDIR="$HOME/.config/zsh"
    ```

## Installation Prerequisites

### Minimal Prerequisites by Platform

=== "macOS"

    - Xcode Command Line Tools (installed with Homebrew)
    - Homebrew

=== "Ubuntu/WSL"

    - `build-essential` (gcc, g++, make)
    - `curl`, `wget`
    - `git`
    - `ca-certificates`, `gnupg`

=== "Arch Linux"

    - `base-devel` (gcc, make, etc.)
    - `curl`, `wget`
    - `git`
