# Platform Differences Reference

This document provides a comprehensive reference for platform-specific differences across macOS, Ubuntu (WSL), and Arch Linux. Understanding these differences ensures smooth cross-platform dotfiles management.

## Quick Reference

| Aspect                | macOS                                                     | Ubuntu/WSL                            | Arch Linux             |
| --------------------- | --------------------------------------------------------- | ------------------------------------- | ---------------------- |
| **Package Manager**   | brew                                                      | apt                                   | pacman                 |
| **Update Command**    | `brew update && brew upgrade`                             | `sudo apt update && sudo apt upgrade` | `sudo pacman -Syu`     |
| **Install Command**   | `brew install <pkg>`                                      | `sudo apt install <pkg>`              | `sudo pacman -S <pkg>` |
| **Homebrew Location** | `/usr/local` (Intel) <br> `/opt/homebrew` (Apple Silicon) | N/A                                   | N/A                    |
| **Shell Config**      | `~/.config/zsh/.zshrc`                                    | `~/.config/zsh/.zshrc`                | `~/.config/zsh/.zshrc` |
| **PATH Priority**     | brew bins → system                                        | system → local                        | system → local         |

---

## Package Name Differences

Many tools have different package names across platforms. This table maps the tool name to its package name on each platform.

| Tool Name     | macOS (brew) | Ubuntu (apt)     | Arch (pacman) | Notes                              |
| ------------- | ------------ | ---------------- | ------------- | ---------------------------------- |
| **bat**       | `bat`        | `bat`            | `bat`         | Ubuntu installs as `batcat` binary |
| **eza**       | `eza`        | via cargo        | `eza`         | Not in Ubuntu apt repos            |
| **fd**        | `fd`         | `fd-find`        | `fd`          | Ubuntu installs as `fdfind` binary |
| **ripgrep**   | `ripgrep`    | `ripgrep`        | `ripgrep`     | All platforms use `rg` binary      |
| **fzf**       | `fzf`        | `fzf`            | `fzf`         | ✅ Consistent                      |
| **zoxide**    | `zoxide`     | `zoxide`         | `zoxide`      | ✅ Consistent                      |
| **neovim**    | `neovim`     | `neovim`         | `neovim`      | All use `nvim` binary              |
| **tmux**      | `tmux`       | `tmux`           | `tmux`        | ✅ Consistent                      |
| **lazygit**   | `lazygit`    | via snap/release | `lazygit`     | Ubuntu needs manual install        |
| **yazi**      | `yazi`       | via cargo        | `yazi`        | Ubuntu needs cargo install         |
| **git-delta** | `git-delta`  | via cargo        | `git-delta`   | Ubuntu needs cargo install         |
| **jq**        | `jq`         | `jq`             | `jq`          | ✅ Consistent                      |
| **yq**        | `yq`         | snap or binary   | `yq`          | Ubuntu via snap or manual          |
| **htop**      | `htop`       | `htop`           | `htop`        | ✅ Consistent                      |
| **tree**      | `tree`       | `tree`           | `tree`        | ✅ Consistent                      |
| **go-task**   | `go-task`    | via script       | `go-task`     | Binary name: `task`                |

### Binary Name Differences

Some packages install with different binary names:

**Ubuntu-Specific**:

- `bat` package → `batcat` binary (needs symlink to `bat`)
- `fd-find` package → `fdfind` binary (needs symlink to `fd`)

**Solution** (implemented in `taskfiles/wsl.yml`):

```bash
# Create symlinks for differently-named packages
mkdir -p ~/.local/bin
ln -sf /usr/bin/batcat ~/.local/bin/bat
ln -sf /usr/bin/fdfind ~/.local/bin/fd
```

---

## Package Manager Comparison

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

---

## Tool Availability by Platform

| Tool           | macOS   | Ubuntu    | Arch      | Installation Method                 |
| -------------- | ------- | --------- | --------- | ----------------------------------- |
| **bat**        | ✅ brew | ✅ apt    | ✅ pacman | Native package managers             |
| **eza**        | ✅ brew | ⚠️ cargo  | ✅ pacman | Ubuntu needs Rust                   |
| **fd**         | ✅ brew | ✅ apt    | ✅ pacman | Different package name on Ubuntu    |
| **ripgrep**    | ✅ brew | ✅ apt    | ✅ pacman | Consistent across platforms         |
| **fzf**        | ✅ brew | ✅ apt    | ✅ pacman | Consistent across platforms         |
| **zoxide**     | ✅ brew | ✅ apt    | ✅ pacman | Consistent across platforms         |
| **neovim**     | ✅ brew | ✅ apt    | ✅ pacman | Consistent across platforms         |
| **tmux**       | ✅ brew | ✅ apt    | ✅ pacman | Consistent across platforms         |
| **lazygit**    | ✅ brew | ⚠️ manual | ✅ pacman | Ubuntu needs snap or manual install |
| **yazi**       | ✅ brew | ⚠️ cargo  | ✅ pacman | Ubuntu needs Rust                   |
| **git-delta**  | ✅ brew | ⚠️ cargo  | ✅ pacman | Ubuntu needs Rust                   |
| **aerospace**  | ✅ cask | ❌        | ❌        | macOS-only window manager           |
| **borders**    | ✅ brew | ❌        | ❌        | macOS-only                          |
| **sketchybar** | ✅ brew | ❌        | ❌        | macOS-only                          |

**Legend**:

- ✅ Native package manager support
- ⚠️ Alternative installation required
- ❌ Not available or not applicable

---

## PATH Configuration

### Default PATH Order

**macOS**:

```bash
/usr/local/bin      # Homebrew (Intel Mac)
/usr/local/sbin
/usr/bin            # System binaries
/bin
/usr/sbin
/sbin
```

**Ubuntu/WSL**:

```bash
/usr/local/bin
/usr/bin            # System binaries
/bin
~/.local/bin        # User binaries (important for our syml inks)
```

**Arch Linux**:

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

---

## Shell Configuration

### Shell Config File Locations

| Platform   | Shell | Main Config            |
| ---------- | ----- | ---------------------- |
| **macOS**  | zsh   | `~/.config/zsh/.zshrc` |
| **Ubuntu** | zsh   | `~/.config/zsh/.zshrc` |
| **Arch**   | zsh   | `~/.config/zsh/.zshrc` |

### ZSHDOTDIR Configuration

All platforms use `~/.config/zsh/.zshrc` via ZSHDOTDIR.

**macOS**: Set in terminal emulator or user environment.

**Ubuntu/WSL and Arch**: Set in `/etc/zsh/zshenv`:

```bash
# /etc/zsh/zshenv
export ZSHDOTDIR="$HOME/.config/zsh"
```

---

## Installation Prerequisites

### Minimal Prerequisites by Platform

**macOS**:

- Xcode Command Line Tools (installed with Homebrew)
- Homebrew

**Ubuntu/WSL**:

- `build-essential` (gcc, g++, make)
- `curl`, `wget`
- `git`
- `ca-certificates`, `gnupg`

**Arch Linux**:

- `base-devel` (gcc, make, etc.)
- `curl`, `wget`
- `git`

---

## Rust/Cargo Installation

Some tools require Rust/Cargo, especially on Ubuntu where they're not available via apt.

**All Platforms**:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source "$HOME/.cargo/env"
```

### Cargo-Installed Tools

On **Ubuntu**, these tools need cargo install:

- `eza` (modern ls)
- `yazi` (file manager)
- `git-delta` (git diff viewer)

```bash
cargo install eza yazi-fm git-delta
```

On **macOS** and **Arch**, these are available via native package managers.

---

## Theme System (tinty)

| Platform   | Installation Method                        |
| ---------- | ------------------------------------------ |
| **macOS**  | `brew install tinted-theming/tinted/tinty` |
| **Ubuntu** | `cargo install tinty` (after Rust install) |
| **Arch**   | `yay -S tinty` or `cargo install tinty`    |

### Configuration

Theme configuration is **consistent across all platforms**:

- Config: `~/.config/tinty/config.toml`
- Theme files: `~/.local/share/tinted-theming/tinty/`
- Command: `tinty apply <theme>`

---

## Node.js and npm (via nvm)

nvm provides **consistent Node.js management** across all platforms.

**All Platforms**:

```bash
# Install nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash

# Install Node.js LTS
nvm install --lts
nvm alias default lts/*
```

### nvm Configuration

nvm directory: `~/.config/nvm` (consistent across platforms)

Shell integration (added to `.zshrc`):

```bash
export NVM_DIR="$HOME/.config/nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
```

---

## Python (via uv)

uv provides **consistent Python management** across all platforms.

**All Platforms**:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Python Tool Installation

```bash
# Same commands on all platforms
uv tool install ruff
uv tool install mypy
uv tool install basedpyright
uv tool install sqlfluff
uv tool install mdformat
```

Tools installed to: `~/.local/bin` (consistent across platforms)

---

## Platform-Specific Quirks

### macOS Quirks

**GNU Coreutils**:

- Installed with `g` prefix: `gls`, `gsed`, `gtar`, `ggrep`
- Prevents conflicts with BSD utils
- NOT added to PATH by default (follows Homebrew best practices)

**Homebrew Location**:

- Intel Mac: `/usr/local`
- Apple Silicon: `/opt/homebrew`
- Scripts should detect automatically

### Ubuntu/WSL Quirks

**WSL-Specific Configuration** (`/etc/wsl.conf`):

```ini
[boot]
systemd=true

[interop]
appendWindowsPath=false

[user]
default=chris
```

**Binary Name Symlinks**:

- `batcat` → `bat` (created during install)
- `fdfind` → `fd` (created during install)

**Snap Packages**:

- Some tools only available via snap
- Snap integration varies

### Arch Linux Quirks

**AUR Helper** (yay):

- Required for AUR packages
- Installed during setup
- Command: `yay -S <package>`

**pacman Configuration**:

- Enable color output
- Enable parallel downloads
- Configured automatically during install

**Rolling Release**:

- More frequent updates
- May encounter breaking changes
- Test updates in VM first

---

## Testing Checklist

When testing installations, verify these platform-specific items:

### macOS Testing

- [ ] Homebrew location correct for architecture
- [ ] All Brewfile packages install
- [ ] Casks install correctly
- [ ] Symlinks created in expected locations
- [ ] GNU coreutils NOT in PATH by default

### Ubuntu/WSL Testing

- [ ] bat and fd symlinks created
- [ ] Cargo tools install (eza, yazi, git-delta)
- [ ] ~/.local/bin in PATH
- [ ] WSL-specific config applied (/etc/wsl.conf)
- [ ] systemd enabled if needed

### Arch Linux Testing

- [ ] yay AUR helper installed
- [ ] pacman.conf configured (color, parallel downloads)
- [ ] All packages install without conflicts
- [ ] Symlinks created correctly
- [ ] Services enabled if needed

---

## Troubleshooting

### Package Not Found

**Symptoms**: Package doesn't exist in repos

**Solutions**:

- **macOS**: Check if it's a cask: `brew search --cask <pkg>`
- **Ubuntu**: May need PPA or cargo install
- **Arch**: Check AUR: `yay -Ss <pkg>`

### Binary Not in PATH

**Symptoms**: Command not found after install

**Solutions**:

1. Check installation location: `which <command>`
2. Verify PATH: `echo $PATH | tr ':' '\n'`
3. Reload shell: `source ~/.zshrc`
4. Check symlinks: `ls -la ~/.local/bin`

### Permission Denied

**Symptoms**: Can't install or write files

**Solutions**:

- Ensure ~/.local/bin exists: `mkdir -p ~/.local/bin`
- Check ownership: `ls -la ~/.local`
- Fix permissions: `chmod 755 ~/.local/bin`

---

## Summary

Key takeaways for cross-platform compatibility:

1. **Use version managers** (nvm, uv) for language runtimes - consistent across platforms
2. **Check package names** - some differ (bat, fd on Ubuntu)
3. **Handle binary name differences** - create symlinks when needed
4. **Test on all platforms** - use VMs to catch issues early
5. **Document quirks** - update this file as you discover platform-specific behavior

The dotfiles are designed with these differences in mind, using taskfiles to abstract platform-specific logic while maintaining a consistent user experience.
