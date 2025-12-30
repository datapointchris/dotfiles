# Tool Availability

Tool support, version managers, and platform-specific quirks.

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

nvm directory: `~/.config/nvm` (consistent across platforms)

Shell integration (added to `.zshrc`):

```bash
export NVM_DIR="$HOME/.config/nvm"
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

Theme management uses the `theme` CLI from `apps/common/theme/`:

```bash
theme list                  # List available themes
theme apply rose-pine       # Apply theme
theme preview               # Interactive fzf preview
theme current               # Show current theme
```

**Configuration** (consistent across all platforms):

- Themes: `apps/common/theme/themes/`
- Generated configs: copied to `~/.config/{app}/themes/current.conf`
- Theme history: `apps/common/theme/data/history-{platform}.jsonl`

## Platform-Specific Quirks

=== "macOS"

    **GNU Coreutils**:

    - Installed with `g` prefix: `gls`, `gsed`, `gtar`, `ggrep`
    - Prevents conflicts with BSD utils
    - NOT added to PATH by default (follows Homebrew best practices)

    **Homebrew Location**:

    - Intel Mac: `/usr/local`
    - Apple Silicon: `/opt/homebrew`
    - Scripts should detect automatically

    **macOS-Specific Aliases**:

    - `backup-important` - Backs up critical directories to ~/Documents (iCloud synced)
      - Directories: .claude, learning, notes, obsession, code
      - Uses the universal `backup-dirs` utility
      - See [Backup Dirs](../../apps/backup-dirs.md) for details

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
    - [ ] All Brewfile packages install
    - [ ] Casks install correctly
    - [ ] Symlinks created in expected locations
    - [ ] GNU coreutils NOT in PATH by default

=== "Ubuntu/WSL"

    - [ ] bat and fd symlinks created
    - [ ] Cargo tools install (eza, yazi, git-delta)
    - [ ] ~/.local/bin in PATH
    - [ ] WSL-specific config applied (/etc/wsl.conf)
    - [ ] systemd enabled if needed

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
