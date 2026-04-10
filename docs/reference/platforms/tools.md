# Tool Availability

Tool support, version managers, and platform-specific quirks.

## Tool Availability by Platform

| Tool           | macOS | Ubuntu | Arch | Installation Method                     |
| -------------- | ----- | ------ | ---- | --------------------------------------- |
| **bat**        | ✅    | ✅     | ✅   | cargo-binstall (all platforms)          |
| **eza**        | ✅    | ✅     | ✅   | cargo-binstall (all platforms)          |
| **fd**         | ✅    | ✅     | ✅   | cargo-binstall (all platforms)          |
| **zoxide**     | ✅    | ✅     | ✅   | cargo-binstall (all platforms)          |
| **git-delta**  | ✅    | ✅     | ✅   | cargo-binstall (all platforms)          |
| **oxker**      | ✅    | ✅     | ✅   | cargo-binstall (all platforms)          |
| **broot**      | ✅    | ✅     | ✅   | cargo-binstall (all platforms)          |
| **neovim**     | ✅    | ✅     | ✅   | GitHub releases (all platforms)         |
| **lazygit**    | ✅    | ✅     | ✅   | GitHub releases (all platforms)         |
| **yazi**       | ✅    | ✅     | ✅   | GitHub releases (all platforms)         |
| **fzf**        | ✅    | ✅     | ✅   | GitHub releases (all platforms)         |
| **ripgrep**    | ✅    | ✅     | ✅   | System package manager                  |
| **tmux**       | ✅    | ✅     | ✅   | System package manager                  |
| **aerospace**  | ✅    | ❌     | ❌   | macOS-only window manager (cask)        |
| **borders**    | ✅    | ❌     | ❌   | macOS-only (JankyBorders)               |

**Legend**:

- ✅ Native package manager support
- ⚠️ Alternative installation required
- ❌ Not available or not applicable

## Version Managers

### Node.js and npm (via nvm)

nvm provides **consistent Node.js management** across all platforms.

**All Platforms**:

```bash
# Install nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash

# Install Node.js LTS
nvm install --lts
nvm alias default lts/*
```

**Configuration**:

nvm directory: `~/.local/share/nvm` (consistent across platforms)

Shell integration (added to `.zshrc`):

```bash
export NVM_DIR="$HOME/.local/share/nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
```

### Python (via uv)

uv provides **consistent Python management** across all platforms.

**All Platforms**:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Tool Installation**:

```bash
# Same commands on all platforms
uv tool install ruff
uv tool install mypy
uv tool install basedpyright
uv tool install sqlfluff
uv tool install mdformat
```

Tools installed to: `~/.local/bin` (consistent across platforms)

### Theme System

Theme management uses the `theme` CLI (installed to `~/.local/bin/theme`):

```bash
theme list                  # List available themes
theme apply rose-pine       # Apply theme
theme preview               # Interactive fzf preview
theme current               # Show current theme
theme upgrade               # Update to latest version
```

**Locations**:

- Installed: `~/.local/share/theme/` (cloned from GitHub)
- Development: `~/tools/theme/`
- Data: `~/.config/theme/` (history, rejected themes)
- Themes: `~/.local/share/theme/themes/`

## Platform-Specific Quirks

=== "macOS"

    **GNU Coreutils**:

    - Installed via Homebrew with unprefixed names prepended to PATH
    - GNU takes precedence over BSD in both interactive shells and scripts
    - Use GNU syntax: `sed -i` NOT `sed -i ''`

    **Homebrew Location**:

    - Intel Mac: `/usr/local`
    - Apple Silicon: `/opt/homebrew`
    - Scripts should detect automatically

    **macOS-Specific Tools**:

    - `aerospace` - Tiling window manager
    - `borders` - Window border highlights (JankyBorders)

=== "Ubuntu/WSL"

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

    **Font Installation**:

    Fonts are installed to Windows automatically (no manual steps):

    - Directory: `%LOCALAPPDATA%\Microsoft\Windows\Fonts` (user fonts, no admin)
    - Registry: `HKCU:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts`
    - Fontconfig: Configured to see Windows fonts via `fontconfig-setup.sh`

    The `font` CLI and `fc-list` both see Windows-installed fonts.

    **Snap Packages**:

    - Some tools only available via snap
    - Snap integration varies

=== "Arch Linux"

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

## Testing Checklist

When testing installations, verify these platform-specific items:

=== "macOS"

    - [ ] Homebrew location correct for architecture
    - [ ] All system packages install
    - [ ] Casks install correctly
    - [ ] Symlinks created in expected locations
    - [ ] GNU coreutils prepended to PATH (unprefixed)

=== "Ubuntu/WSL"

    - [ ] Cargo-binstall tools installed (bat, fd, eza, zoxide, delta, broot)
    - [ ] GitHub release tools installed (neovim, lazygit, yazi, fzf)
    - [ ] ~/.local/bin in PATH
    - [ ] WSL-specific config applied (/etc/wsl.conf)
    - [ ] systemd enabled if needed
    - [ ] Fonts installed to Windows user fonts directory
    - [ ] `font list` shows installed fonts

=== "Arch Linux"

    - [ ] yay AUR helper installed
    - [ ] pacman.conf configured (color, parallel downloads)
    - [ ] All packages install without conflicts
    - [ ] Symlinks created correctly
    - [ ] Services enabled if needed

## Troubleshooting

### Package Not Found

!!! warning "Symptoms"
    Package doesn't exist in repos

!!! tip "Solutions"
    === "macOS"

        Check if it's a cask:
        ```bash
        brew search --cask <pkg>
        ```

    === "Ubuntu/WSL"

        May need PPA or cargo install

    === "Arch Linux"

        Check AUR:
        ```bash
        yay -Ss <pkg>
        ```

### Binary Not in PATH

!!! warning "Symptoms"
    Command not found after install

!!! tip "Solutions"
    1. Check installation location: `which <command>`
    2. Verify PATH: `echo $PATH | tr ':' '\n'`
    3. Reload shell: `source ~/.zshrc`
    4. Check symlinks: `ls -la ~/.local/bin`

### Permission Denied

!!! warning "Symptoms"
    Can't install or write files

!!! tip "Solutions"
    - Ensure ~/.local/bin exists: `mkdir -p ~/.local/bin`
    - Check ownership: `ls -la ~/.local`
    - Fix permissions: `chmod 755 ~/.local/bin`
