# Tool Availability

What is installed on a machine is `toolbox list`, or
`packages list --section=<section>` for one install method. This page covers
only the tools where the *choice* of method needed a decision, and the
per-platform quirks that decision produced.

## The one split-method tool

**atuin** installs from GitHub releases on Linux like fzf and neovim, but macOS
falls back to Homebrew. It publishes no Intel-macOS release binary — only Apple
Silicon — and `cargo binstall` would fall through to compiling from source.
brew's bottle covers both Mac architectures, so every Mac uses it while every
other platform takes the uniform GitHub-releases path.

## Version Managers

### Node.js and npm (via fnm)

Node.js versions come from **fnm**, installed as a cargo package. Repos across the
portfolio pin different versions in `.nvmrc` — several want 24, meso wants 26 — and
running the wrong one is not a subtle failure: ichrisbirch's frontend suite dies
outright on 26 with `localStorage is undefined`.

`install/common/language-managers/node.sh` installs the fleet default and links it
as fnm's `default` alias. `.zshenv` puts `~/.local/share/fnm/aliases/default/bin`
on PATH ahead of everything else, so scripts, editors, agents and pre-commit hooks
resolve `node` to that version without any shell integration. `.zshrc` layers
`fnm env --use-on-cd` over it, so entering a directory with an `.nvmrc` switches.

This is the arrangement nvm could not provide: nvm is a shell function defined in
`.zshrc`, so it never existed in a non-interactive shell. fnm is a binary, so the
default alias and `fnm exec` work anywhere. Removing nvm on the grounds that
per-project switching was unused was the wrong diagnosis of a real problem.

The brew/pacman `node` package stays installed, but only as the bootstrap npm the
installer needs before fnm has fetched anything.

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
