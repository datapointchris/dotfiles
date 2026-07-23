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
| **ripgrep**    | ✅    | ✅     | ✅   | cargo-binstall (all platforms)          |
| **neovim**     | ✅    | ✅     | ✅   | GitHub releases (all platforms)         |
| **lazygit**    | ✅    | ✅     | ✅   | GitHub releases (all platforms)         |
| **yazi**       | ✅    | ✅     | ✅   | GitHub releases (all platforms)         |
| **fzf**        | ✅    | ✅     | ✅   | GitHub releases (all platforms)         |
| **atuin**      | ✅    | ✅     | ✅   | GitHub releases (Linux); brew (macOS)   |
| **tmux**       | ✅    | ✅     | ✅   | System package manager                  |
| **aerospace**  | ✅    | ❌     | ❌   | macOS-only window manager (cask)        |
| **borders**    | ✅    | ❌     | ❌   | macOS-only (JankyBorders)               |

**Legend**:

- ✅ Native package manager support
- ⚠️ Alternative installation required
- ❌ Not available or not applicable

**atuin** is the one split-method tool. It uses GitHub releases on Linux like fzf and neovim, but
macOS falls back to Homebrew: atuin publishes no Intel-macOS release binary (only Apple Silicon), and
`cargo binstall` would compile it from source. brew's bottle covers both Mac architectures, so all
Macs use it while every other platform uses the uniform GitHub-releases install.

## Version Managers

### Node.js and npm (system package)

Node.js is installed as a **system package**, not through a version manager. There
is no per-project version switching, and a static-PATH install keeps `node`/`npm`
available to non-interactive shells (scripts, editors, agents) — which a shell-function
manager like nvm cannot do.

```bash
# macOS
brew install node

# Arch Linux
sudo pacman -S nodejs npm
```

**Configuration**:

npm's global prefix is set to `~/.local/share/npm` by an XDG-located user config
at `~/.config/npm/npmrc` (deployed from `configs/common/.config/npm/npmrc`).
`.zshrc` exports `NPM_CONFIG_USERCONFIG` to point npm at that file for interactive
shells, and the npm-globals installer exports the same variable so non-interactive
bash sees it too. This keeps globally-installed tools (LSPs, formatters) in
`~/.local/share/npm/bin` — a user-writable location — independent of the Node.js
package itself. On Arch, where system npm's default prefix is `/usr`, this is
what makes `npm install -g` work without sudo.

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

    - [ ] Cargo-binstall tools installed (ripgrep, bat, fd, eza, zoxide, delta, broot)
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
